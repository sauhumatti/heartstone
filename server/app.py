from __future__ import annotations

import hashlib
import os
import re
import secrets
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.requests import HTTPConnection

from data.starter_decks import STARTER_DECKS
from engine.catalog import COLLECTIBLE_CARDS, HEROES, validate_deck
from engine.cli_format import format_state_for_cli
from engine.game import GameError
from engine.local import engine_tag
from server import agent as outside_agent
from server import updates as app_updates
from server.manager import SAVE_MAX_AGE_SECONDS, GameManager, ManagedGame
from server.storage import delete_custom_deck, get_deck_by_id, list_all_decks, save_custom_deck

app = FastAPI(title="Hearthstone Classic Local Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=2048)


class AppGateOnly:
    """What comes in through the app's own door reaches the update routes and nothing else.

    The site's login gate lets requests for /cardgame/api/app/* through without a password and
    marks them with an X-App-Gate header. Whatever such a request's path turns out to be once it
    is here, only /api/app/* is answered; everything else is a 404, as if it did not exist.
    """

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] in ("http", "websocket") and any(name == b"x-app-gate" for name, _ in scope["headers"]):
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            if not scope["path"].startswith("/api/app/"):
                await send({"type": "http.response.start", "status": 404, "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"detail":"Not found"}'})
                return
        await self.inner(scope, receive, send)


app.add_middleware(AppGateOnly)


# The friends' door: a host without the site's password (Caddy marks its requests with
# X-Friend-Gate). Through it an invited friend can open the game, join with the invitation and
# play that match, and nothing else: no new matches, no deck changes, no other matches.
FRIEND_GATE = "x-friend-gate"
_FRIEND_GET = re.compile(r"^/api/(health|cards|decks|agent|games)$|^/api/games/[A-Za-z0-9_-]{1,64}/state$")
_FRIEND_POST = re.compile(
    r"^/api/games/[A-Za-z0-9_-]{1,64}/(join|mulligan|play|choose|attack|power|end_turn|concede|emote)$"
)
_FRIEND_WS = re.compile(r"^/ws/[A-Za-z0-9_-]{1,64}/p[12]$")


def _friend_door_allows(scope: Any) -> bool:
    path = scope["path"]
    if scope["type"] == "websocket":
        return bool(_FRIEND_WS.match(path))
    method = scope.get("method", "GET")
    if method in ("GET", "HEAD"):
        if path.startswith("/api/") or path.startswith("/ws/"):
            return bool(_FRIEND_GET.match(path))
        return not path.lower().endswith(".apk")  # the game itself, but not the app download
    return method == "POST" and bool(_FRIEND_POST.match(path))


class FriendGateOnly:
    def __init__(self, inner: Any) -> None:
        self.inner = inner

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] in ("http", "websocket") and any(name == FRIEND_GATE.encode() for name, _ in scope["headers"]):
            if not _friend_door_allows(scope):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                    return
                await send({"type": "http.response.start", "status": 404, "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"detail":"Not found"}'})
                return
        await self.inner(scope, receive, send)


app.add_middleware(FriendGateOnly)


@app.middleware("http")
async def prevent_match_caching(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    path = request.url.path.removeprefix(request.scope.get("root_path", "").rstrip("/"))
    if path == "/api/games" or path.startswith("/api/games/"):
        response.headers["Cache-Control"] = "private, no-store"
    return response

VAR_DIR = Path(__file__).resolve().parent.parent / "var"
manager = GameManager(persist_dir=None if os.environ.get("GAME_NO_PERSIST") else VAR_DIR / "games")
# FRONTEND_DIST lets a second instance serve another build (for trying one out beside the live one).
FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST") or Path(__file__).resolve().parent.parent / "frontend" / "dist").resolve()
ASSETS_ART_DIR = Path(__file__).resolve().parent.parent / "assets" / "art"
ASSETS_ART_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_AUDIO_DIR = Path(__file__).resolve().parent.parent / "assets" / "audio"
ASSETS_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Request Models
# ---------------------------------------------------------------------------

class DeckSaveRequest(BaseModel):
    id: Optional[str] = None
    name: str
    hero_class: str
    cards: list[str]


class CreateGameRequest(BaseModel):
    p1_name: str = "Player"
    p1_deck_id: Optional[str] = None
    p1_class: Optional[str] = None
    p1_cards: Optional[list[str]] = None
    p2_mode: str = "cli"  # "cli" | "bot" | "agent" | "friend"
    p2_deck_choice: str = "random"  # "await_cli" | "random" | deck_id | class
    p2_name: Optional[str] = None
    p2_agent_model: Optional[str] = None


class P2DeckRequest(BaseModel):
    deck_id: Optional[str] = None
    hero_class: Optional[str] = None
    cards: Optional[list[str]] = None


class FriendJoinRequest(P2DeckRequest):
    invite: str = Field(max_length=64)
    name: str = Field(default="Friend", max_length=24)


class MulliganRequest(BaseModel):
    seat: str = "p1"
    since: Optional[int] = None
    replace_indices: list[int] = Field(default_factory=list)


class PlayCardRequest(BaseModel):
    seat: str = "p1"
    since: Optional[int] = None
    hand_index: int
    pos: Optional[int] = None
    target_id: Optional[str] = None
    choose: Optional[int] = None


class ChooseRequest(BaseModel):
    seat: str = "p1"
    since: Optional[int] = None
    option_index: int


class AttackRequest(BaseModel):
    seat: str = "p1"
    since: Optional[int] = None
    attacker_id: str
    target_id: str


class HeroPowerRequest(BaseModel):
    seat: str = "p1"
    since: Optional[int] = None
    target_id: Optional[str] = None


class SeatOnlyRequest(BaseModel):
    seat: str = "p1"
    since: Optional[int] = None


class EmoteRequest(BaseModel):
    seat: str = "p1"
    message: str = Field(min_length=1, max_length=160)


class SwitchModeRequest(BaseModel):
    mode: str  # "cli" | "bot" | "agent"
    since: Optional[int] = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _validate_seat(seat: str) -> str:
    if seat not in ("p1", "p2"):
        raise HTTPException(status_code=400, detail="Seat must be 'p1' or 'p2'")
    return seat


def _key_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _matches(token: str, stored_hash: Optional[str]) -> bool:
    return bool(stored_hash and token and secrets.compare_digest(_key_hash(token), stored_hash))


def _cookie_name(mg: ManagedGame, seat: str) -> str:
    return f"lanternfall_{mg.engine.state.game_id}_{seat}"


def _has_seat(conn: HTTPConnection, mg: ManagedGame, seat: str) -> bool:
    return _matches(conn.cookies.get(_cookie_name(mg, seat), ""), mg.friend_keys.get(seat))


def _via_friend_door(conn: HTTPConnection) -> bool:
    return FRIEND_GATE in conn.headers


def _public_origin(conn: HTTPConnection) -> str:
    scheme = "https" if conn.url.scheme in ("https", "wss") else "http"
    setting = "CARDGAME_FRIEND_ORIGIN" if _via_friend_door(conn) else "CARDGAME_PUBLIC_ORIGIN"
    return os.environ.get(setting, f"{scheme}://{conn.url.netloc}").rstrip("/")


def _same_origin(conn: HTTPConnection) -> bool:
    origin = conn.headers.get("origin")
    return origin is None or origin == _public_origin(conn)


def _set_seat_cookie(request: Request, response: Response, mg: ManagedGame, seat: str, token: str) -> None:
    response.set_cookie(
        _cookie_name(mg, seat), token, max_age=SAVE_MAX_AGE_SECONDS, httponly=True,
        secure=_public_origin(request).startswith("https://"), samesite="strict",
        path="/" if _via_friend_door(request) else os.environ.get("CARDGAME_COOKIE_PATH", "/"),
    )


def _game(game_id: str) -> ManagedGame:
    if game_id == "latest":
        # Keep the legacy CLI alias working and require an explicit id for friend matches.
        candidates = (mg for mg in manager.games.values() if mg.engine.state.mode != "friend_vs_human")
        latest = max(candidates, key=lambda mg: mg.engine.state.created_at, default=None)
        if latest is None:
            raise GameError("No active games found.")
        return latest
    return manager.get_managed(game_id)


def _seat_game(conn: HTTPConnection, game_id: str, seat: str) -> ManagedGame:
    _validate_seat(seat)
    mg = _game(game_id)
    if _via_friend_door(conn) and mg.engine.state.mode != "friend_vs_human":
        raise HTTPException(status_code=404, detail="Match or seat not found.")
    if mg.engine.state.mode == "friend_vs_human" and (not _same_origin(conn) or not _has_seat(conn, mg, seat)):
        raise HTTPException(status_code=404, detail="Match or seat not found.")
    return mg


def _legacy_game(game_id: str) -> ManagedGame:
    mg = _game(game_id)
    if mg.engine.state.mode == "friend_vs_human":
        raise HTTPException(status_code=404, detail="Match not found.")
    return mg


def _payload(mg: Any, seat: str, since: Optional[int] = None) -> dict[str, Any]:
    """Current view plus the beats the caller has not seen yet. `beats` is null
    when the caller's position is unknown and it should jump to `state`."""
    manager.kick_agent(mg)  # if everybody is waiting for the outside agent, it starts now
    return {
        "state": mg.engine.serialize_for_seat(seat),
        "beats": mg.engine.beats_for_seat(seat, since),
        "agent": manager.agent_status(mg),
    }


@app.get("/api/agent")
def agent_info() -> dict[str, Any]:
    """Whether an outside agent can take the other seat, and with which models."""
    return {
        "available": outside_agent.agent_command() is not None,
        "default": outside_agent.DEFAULT_MODEL,
        "models": [{"id": k, "label": v} for k, v in outside_agent.MODELS.items()],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

# The rules this server is running: a fingerprint of the engine's files as they were when it
# started. scripts/release.sh compares it with the files on disk and restarts the server when
# they differ, so the server and the engine packed for devices are always the same rules.
ENGINE_TAG = engine_tag()


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "cards_count": len(COLLECTIBLE_CARDS), "engine": ENGINE_TAG}


@app.get("/api/cards")
def get_cards() -> dict[str, Any]:
    return {
        "heroes": {
            k: {
                "card_class": v.card_class,
                "name": v.name,
                "hero_power_id": v.hero_power_id,
                "title": v.title,
                "color": v.color,
            }
            for k, v in HEROES.items()
        },
        "cards": [c.to_dict() for c in sorted(COLLECTIBLE_CARDS.values(), key=lambda x: (x.cost, x.name))],
    }


@app.get("/api/decks")
def get_decks() -> dict[str, Any]:
    return {"decks": list_all_decks()}


@app.post("/api/decks")
def create_or_update_deck(req: DeckSaveRequest) -> dict[str, Any]:
    try:
        deck = save_custom_deck(req.name, req.hero_class, req.cards, deck_id=req.id)
        return {"deck": deck}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/decks/{deck_id}")
def remove_deck(deck_id: str) -> dict[str, Any]:
    if not delete_custom_deck(deck_id):
        raise HTTPException(status_code=404, detail="Custom deck not found")
    return {"deleted": True}


@app.get("/api/games")
async def list_games(request: Request) -> dict[str, Any]:
    games = []
    for summary in manager.list_games():
        if _via_friend_door(request) and summary["mode"] != "friend_vs_human":
            continue
        if summary["mode"] == "friend_vs_human":
            mg = manager.games[summary["game_id"]]
            seat = next((seat for seat in ("p1", "p2") if _has_seat(request, mg, seat)), None)
            if seat is None:
                continue
            summary["viewer_seat"] = seat
        summary["is_latest"] = not games
        games.append(summary)
    return {"games": games, "latest_game_id": games[0]["game_id"] if games else None}


@app.post("/api/games")
async def create_game(req: CreateGameRequest, request: Request, response: Response) -> dict[str, Any]:
    friend = req.p2_mode == "friend"
    if friend and not _same_origin(request):
        raise HTTPException(status_code=403, detail="Open the game site directly to create a friend match.")
    host_token = secrets.token_urlsafe(32) if friend else ""
    invite = secrets.token_urlsafe(32) if friend else ""
    name = (req.p1_name.strip()[:24] or "Player") if friend else req.p1_name
    try:
        mg = await manager.create_game(
            p1_name=name,
            p1_deck_id=req.p1_deck_id,
            p1_class=req.p1_class,
            p1_cards=req.p1_cards,
            p2_mode=req.p2_mode,
            p2_deck_choice=req.p2_deck_choice,
            p2_name="Friend" if friend else req.p2_name,
            p2_agent_model=req.p2_agent_model,
            friend_keys={"p1": _key_hash(host_token), "invite": _key_hash(invite)} if friend else None,
        )
        payload = {"game_id": mg.engine.state.game_id, **_payload(mg, "p1", 0)}
        if friend:
            _set_seat_cookie(request, response, mg, "p1", host_token)
            payload["invite"] = invite
            friend_origin = os.environ.get("CARDGAME_FRIEND_ORIGIN", "").rstrip("/")
            if friend_origin:  # the friend opens the game through the door without the password
                payload["invite_url"] = f"{friend_origin}/#invite={mg.engine.state.game_id}.{invite}"
        return payload
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/join")
async def join_friend(game_id: str, req: FriendJoinRequest, request: Request, response: Response) -> dict[str, Any]:
    mg = manager.games.get(game_id)
    if (
        mg is None or mg.engine.state.mode != "friend_vs_human" or not _same_origin(request)
        or not _matches(req.invite, mg.friend_keys.get("invite"))
    ):
        raise HTTPException(status_code=404, detail="This invite is invalid or has already been used.")
    if mg.engine.state.phase != "WAITING_FOR_P2_DECK":
        raise HTTPException(status_code=409, detail="This match is closed.")

    if req.deck_id:
        deck = get_deck_by_id(req.deck_id)
        if not deck:
            raise HTTPException(status_code=400, detail="That deck was not found.")
        hero_class, cards, deck_name = deck["hero_class"], deck["cards"], deck["name"]
    else:
        hero_class, cards, deck_name = req.hero_class or "", req.cards or [], "Custom deck"
    ok, message = validate_deck(hero_class, cards)
    if not ok:
        raise HTTPException(status_code=400, detail=message)

    # Commit the deck and consume the invite before yielding, so two requests cannot claim it.
    token = secrets.token_urlsafe(32)
    mg.engine.state.players["p2"].name = req.name.strip() or "Friend"
    mg.engine.set_p2_deck(hero_class, cards, deck_name)
    mg.friend_keys["p2"] = _key_hash(token)
    del mg.friend_keys["invite"]
    await manager.notify(mg)
    _set_seat_cookie(request, response, mg, "p2", token)
    return {"game_id": game_id, **_payload(mg, "p2")}


@app.get("/api/games/{game_id}/state")
async def get_game_state(
    game_id: str, request: Request, seat: str = Query("p1"), since: Optional[int] = Query(None)
) -> dict[str, Any]:
    try:
        mg = _seat_game(request, game_id, seat)
        return _payload(mg, seat, since)
    except GameError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/games/{game_id}/cli_text")
def get_cli_text(game_id: str, seat: str = Query("p2")) -> dict[str, Any]:
    _validate_seat(seat)
    try:
        mg = _legacy_game(game_id)
        view = mg.engine.serialize_for_seat(seat)
        return {"text": format_state_for_cli(view), "state": view}
    except GameError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/games/{game_id}/wait")
async def wait_for_turn(
    game_id: str,
    seat: str = Query("p2"),
    timeout: float = Query(45.0),
) -> dict[str, Any]:
    _validate_seat(seat)
    try:
        mg = _legacy_game(game_id)
        ready, state = await manager.wait_for_turn(mg.engine.state.game_id, seat, timeout=timeout)
        return {
            "ready": ready,
            "text": format_state_for_cli(state),
            "state": state,
        }
    except GameError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/games/{game_id}/p2_deck")
async def set_p2_deck(game_id: str, req: P2DeckRequest) -> dict[str, Any]:
    try:
        mg = _legacy_game(game_id)
        if req.deck_id:
            d = get_deck_by_id(req.deck_id)
            if not d:
                raise GameError(f"Deck '{req.deck_id}' not found.")
            mg.engine.set_p2_deck(d["hero_class"], d["cards"], d["name"])
        elif req.hero_class and req.cards:
            mg.engine.set_p2_deck(req.hero_class, req.cards, f"Custom {req.hero_class.title()}")
        elif req.hero_class:
            cls = req.hero_class.upper()
            if cls not in STARTER_DECKS:
                raise GameError(f"Unknown hero class '{cls}'")
            d = STARTER_DECKS[cls]
            mg.engine.set_p2_deck(d["hero_class"], d["cards"], d["name"])
        else:
            raise GameError("Provide deck_id or hero_class.")
        await manager.notify(mg)
        return {"state": mg.engine.serialize_for_seat("p2")}
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/mulligan")
async def submit_mulligan(game_id: str, req: MulliganRequest, request: Request) -> dict[str, Any]:
    try:
        mg = _seat_game(request, game_id, req.seat)
        mg.engine.submit_mulligan(req.seat, req.replace_indices)
        await manager.maybe_step_bot(mg)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/play")
async def play_card(game_id: str, req: PlayCardRequest, request: Request) -> dict[str, Any]:
    try:
        mg = _seat_game(request, game_id, req.seat)
        mg.engine.play_card(
            req.seat,
            req.hand_index,
            pos=req.pos,
            target_id=req.target_id,
            choose=req.choose,
        )
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/choose")
async def resolve_choice(game_id: str, req: ChooseRequest, request: Request) -> dict[str, Any]:
    try:
        mg = _seat_game(request, game_id, req.seat)
        mg.engine.resolve_pending_choice(req.seat, req.option_index)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/attack")
async def attack(game_id: str, req: AttackRequest, request: Request) -> dict[str, Any]:
    try:
        mg = _seat_game(request, game_id, req.seat)
        mg.engine.attack(req.seat, req.attacker_id, req.target_id)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/power")
async def use_hero_power(game_id: str, req: HeroPowerRequest, request: Request) -> dict[str, Any]:
    try:
        mg = _seat_game(request, game_id, req.seat)
        mg.engine.use_hero_power(req.seat, target_id=req.target_id)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/end_turn")
async def end_turn(game_id: str, req: SeatOnlyRequest, request: Request) -> dict[str, Any]:
    try:
        mg = _seat_game(request, game_id, req.seat)
        mg.engine.end_turn(req.seat)
        await manager.maybe_step_bot(mg)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/concede")
async def concede(game_id: str, req: SeatOnlyRequest, request: Request) -> dict[str, Any]:
    try:
        mg = _seat_game(request, game_id, req.seat)
        mg.engine.concede(req.seat)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/emote")
async def emote(game_id: str, req: EmoteRequest, request: Request) -> dict[str, Any]:
    try:
        mg = _seat_game(request, game_id, req.seat)
        message = " ".join(req.message.split())
        if not message:
            raise GameError("Nothing to say.")
        mg.engine.send_emote(req.seat, message)
        manager.heard(mg, req.seat)
        await manager.notify(mg)
        return {"ok": True}
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/switch_mode")
async def switch_mode(game_id: str, req: SwitchModeRequest) -> dict[str, Any]:
    if req.mode not in ("cli", "bot", "agent"):
        raise HTTPException(status_code=400, detail="Mode must be 'cli', 'bot' or 'agent'")
    try:
        mg = _legacy_game(game_id)
        mg.engine.state.mode = {"bot": "bot_vs_human", "agent": "agent_vs_human"}.get(req.mode, "cli_vs_human")
        if req.mode == "agent" and not mg.engine.state.agent_model:
            mg.engine.state.agent_model = outside_agent.DEFAULT_MODEL
        mg.engine.state.players["p2"].name = "Practice Bot" if req.mode == "bot" else "Antigravity"
        await manager.maybe_step_bot(mg)
        await manager.notify(mg)
        return _payload(mg, "p1", req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/{game_id}/{seat}")
async def game_ws(websocket: WebSocket, game_id: str, seat: str) -> None:
    if seat not in ("p1", "p2"):
        await websocket.close(code=4000)
        return
    try:
        mg = _seat_game(websocket, game_id, seat)
    except (GameError, HTTPException):
        await websocket.close(code=4004)
        return

    since: Optional[int] = None
    raw_since = websocket.query_params.get("since")
    if raw_since is not None and raw_since.lstrip("-").isdigit():
        since = int(raw_since)

    await websocket.accept()
    try:
        await websocket.send_json({"type": "state", **_payload(mg, seat, since)})
        # Registered with the position it has now seen; notify() sends what follows.
        mg.sockets[seat][websocket] = mg.engine.state.cp_seq
        while True:
            # Keep connection alive; ignore pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        mg.sockets[seat].pop(websocket, None)


# ---------------------------------------------------------------------------
# Updates for the installed app (server/updates.py): token only
# ---------------------------------------------------------------------------

app.include_router(app_updates.router)


# ---------------------------------------------------------------------------
# Static Frontend Serving (SPA)
# ---------------------------------------------------------------------------

app.mount("/art", StaticFiles(directory=ASSETS_ART_DIR), name="art")
app.mount("/audio", StaticFiles(directory=ASSETS_AUDIO_DIR), name="audio")

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}")
def serve_spa(full_path: str) -> Any:
    if full_path.startswith("api/") or full_path.startswith("ws/") or full_path.startswith("art/") or full_path.startswith("audio/"):
        raise HTTPException(status_code=404, detail="Not found")
    # Only files inside the build folder: a path with ".." in it must not walk out of it.
    candidate = (FRONTEND_DIST / full_path).resolve()
    if full_path and candidate.is_relative_to(FRONTEND_DIST) and candidate.is_file():
        return FileResponse(candidate)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "message": "Frontend build not found yet. Build frontend with `cd frontend && npm run build`."
    }
