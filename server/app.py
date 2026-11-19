from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from data.starter_decks import STARTER_DECKS
from engine.catalog import COLLECTIBLE_CARDS, HEROES
from engine.cli_format import format_state_for_cli
from engine.game import GameError
from engine.local import engine_tag
from server import agent as outside_agent
from server import updates as app_updates
from server.manager import GameManager
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
        if scope["type"] == "http" and not scope["path"].startswith("/api/app/"):
            if any(name == b"x-app-gate" for name, _value in scope["headers"]):
                await send({"type": "http.response.start", "status": 404, "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body", "body": b'{"detail":"Not found"}'})
                return
        await self.inner(scope, receive, send)


app.add_middleware(AppGateOnly)

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
    p2_mode: str = "cli"  # "cli" (someone on ./hs) | "bot" | "agent" (the Antigravity CLI is asked)
    p2_deck_choice: str = "random"  # "await_cli" | "random" | deck_id | class
    p2_name: Optional[str] = None
    p2_agent_model: Optional[str] = None


class P2DeckRequest(BaseModel):
    deck_id: Optional[str] = None
    hero_class: Optional[str] = None
    cards: Optional[list[str]] = None


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
    message: str


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
def list_games() -> dict[str, Any]:
    return {"games": manager.list_games(), "latest_game_id": manager.latest_game_id}


@app.post("/api/games")
async def create_game(req: CreateGameRequest) -> dict[str, Any]:
    try:
        mg = await manager.create_game(
            p1_name=req.p1_name,
            p1_deck_id=req.p1_deck_id,
            p1_class=req.p1_class,
            p1_cards=req.p1_cards,
            p2_mode=req.p2_mode,
            p2_deck_choice=req.p2_deck_choice,
            p2_name=req.p2_name,
            p2_agent_model=req.p2_agent_model,
        )
        return {"game_id": mg.engine.state.game_id, **_payload(mg, "p1", 0)}
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/games/{game_id}/state")
async def get_game_state(
    game_id: str, seat: str = Query("p1"), since: Optional[int] = Query(None)
) -> dict[str, Any]:
    _validate_seat(seat)
    try:
        mg = manager.get_managed(game_id)
        return _payload(mg, seat, since)
    except GameError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/games/{game_id}/cli_text")
def get_cli_text(game_id: str, seat: str = Query("p2")) -> dict[str, Any]:
    _validate_seat(seat)
    try:
        mg = manager.get_managed(game_id)
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
        ready, state = await manager.wait_for_turn(game_id, seat, timeout=timeout)
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
        mg = manager.get_managed(game_id)
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
async def submit_mulligan(game_id: str, req: MulliganRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
        mg.engine.submit_mulligan(req.seat, req.replace_indices)
        await manager.maybe_step_bot(mg)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/play")
async def play_card(game_id: str, req: PlayCardRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
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
async def resolve_choice(game_id: str, req: ChooseRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
        mg.engine.resolve_pending_choice(req.seat, req.option_index)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/attack")
async def attack(game_id: str, req: AttackRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
        mg.engine.attack(req.seat, req.attacker_id, req.target_id)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/power")
async def use_hero_power(game_id: str, req: HeroPowerRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
        mg.engine.use_hero_power(req.seat, target_id=req.target_id)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/end_turn")
async def end_turn(game_id: str, req: SeatOnlyRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
        mg.engine.end_turn(req.seat)
        await manager.maybe_step_bot(mg)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/concede")
async def concede(game_id: str, req: SeatOnlyRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
        mg.engine.concede(req.seat)
        await manager.notify(mg)
        return _payload(mg, req.seat, req.since)
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/emote")
async def emote(game_id: str, req: EmoteRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
        mg.engine.send_emote(req.seat, req.message)
        await manager.notify(mg)
        return {"ok": True}
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/switch_mode")
async def switch_mode(game_id: str, req: SwitchModeRequest) -> dict[str, Any]:
    if req.mode not in ("cli", "bot", "agent"):
        raise HTTPException(status_code=400, detail="Mode must be 'cli', 'bot' or 'agent'")
    try:
        mg = manager.get_managed(game_id)
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
        mg = manager.get_managed(game_id)
    except GameError:
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
