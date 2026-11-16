from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from data.starter_decks import STARTER_DECKS
from engine.catalog import COLLECTIBLE_CARDS, HEROES
from engine.cli_format import format_state_for_cli
from engine.game import GameError
from server.manager import GameManager
from server.storage import delete_custom_deck, get_deck_by_id, list_all_decks, save_custom_deck

app = FastAPI(title="Hearthstone Classic Local Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = GameManager()
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


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
    p2_mode: str = "cli"  # "cli" | "bot"
    p2_deck_choice: str = "random"  # "await_cli" | "random" | deck_id | class
    p2_name: Optional[str] = None


class P2DeckRequest(BaseModel):
    deck_id: Optional[str] = None
    hero_class: Optional[str] = None
    cards: Optional[list[str]] = None


class MulliganRequest(BaseModel):
    seat: str = "p1"
    replace_indices: list[int] = Field(default_factory=list)


class PlayCardRequest(BaseModel):
    seat: str = "p1"
    hand_index: int
    pos: Optional[int] = None
    target_id: Optional[str] = None
    choose: Optional[int] = None


class ChooseRequest(BaseModel):
    seat: str = "p1"
    option_index: int


class AttackRequest(BaseModel):
    seat: str = "p1"
    attacker_id: str
    target_id: str


class HeroPowerRequest(BaseModel):
    seat: str = "p1"
    target_id: Optional[str] = None


class SeatOnlyRequest(BaseModel):
    seat: str = "p1"


class EmoteRequest(BaseModel):
    seat: str = "p1"
    message: str


class SwitchModeRequest(BaseModel):
    mode: str  # "cli" | "bot"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _validate_seat(seat: str) -> str:
    if seat not in ("p1", "p2"):
        raise HTTPException(status_code=400, detail="Seat must be 'p1' or 'p2'")
    return seat


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "cards_count": len(COLLECTIBLE_CARDS)}


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
        )
        return {"game_id": mg.engine.state.game_id, "state": mg.engine.serialize_for_seat("p1")}
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/games/{game_id}/state")
def get_game_state(game_id: str, seat: str = Query("p1")) -> dict[str, Any]:
    _validate_seat(seat)
    try:
        mg = manager.get_managed(game_id)
        return {"state": mg.engine.serialize_for_seat(seat)}
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
        return {"state": mg.engine.serialize_for_seat(req.seat)}
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
        return {"state": mg.engine.serialize_for_seat(req.seat)}
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/choose")
async def resolve_choice(game_id: str, req: ChooseRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
        mg.engine.resolve_pending_choice(req.seat, req.option_index)
        await manager.notify(mg)
        return {"state": mg.engine.serialize_for_seat(req.seat)}
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/attack")
async def attack(game_id: str, req: AttackRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
        mg.engine.attack(req.seat, req.attacker_id, req.target_id)
        await manager.notify(mg)
        return {"state": mg.engine.serialize_for_seat(req.seat)}
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/power")
async def use_hero_power(game_id: str, req: HeroPowerRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
        mg.engine.use_hero_power(req.seat, target_id=req.target_id)
        await manager.notify(mg)
        return {"state": mg.engine.serialize_for_seat(req.seat)}
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
        return {"state": mg.engine.serialize_for_seat(req.seat)}
    except GameError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/games/{game_id}/concede")
async def concede(game_id: str, req: SeatOnlyRequest) -> dict[str, Any]:
    _validate_seat(req.seat)
    try:
        mg = manager.get_managed(game_id)
        mg.engine.concede(req.seat)
        await manager.notify(mg)
        return {"state": mg.engine.serialize_for_seat(req.seat)}
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
    if req.mode not in ("cli", "bot"):
        raise HTTPException(status_code=400, detail="Mode must be 'cli' or 'bot'")
    try:
        mg = manager.get_managed(game_id)
        mg.engine.state.mode = "bot_vs_human" if req.mode == "bot" else "cli_vs_human"
        mg.engine.state.players["p2"].name = "Practice Bot" if req.mode == "bot" else "Antigravity"
        await manager.maybe_step_bot(mg)
        await manager.notify(mg)
        return {"state": mg.engine.serialize_for_seat("p1")}
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

    await websocket.accept()
    mg.sockets[seat].add(websocket)
    try:
        await websocket.send_json({"type": "state", "state": mg.engine.serialize_for_seat(seat)})
        while True:
            # Keep connection alive; ignore pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        mg.sockets[seat].discard(websocket)


# ---------------------------------------------------------------------------
# Static Frontend Serving (SPA)
# ---------------------------------------------------------------------------

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}")
def serve_spa(full_path: str) -> Any:
    if full_path.startswith("api/") or full_path.startswith("ws/"):
        raise HTTPException(status_code=404, detail="Not found")
    candidate = FRONTEND_DIST / full_path
    if full_path and candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return {
        "message": "Frontend build not found yet. Build frontend with `cd frontend && npm run build`."
    }
