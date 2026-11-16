from __future__ import annotations

import asyncio
import random
from typing import Any, Optional

from fastapi import WebSocket

from data.starter_decks import STARTER_DECKS
from engine.bot import run_bot_mulligan, run_bot_turn
from engine.catalog import HEROES, validate_deck
from engine.game import GameEngine, GameError
from server.storage import get_deck_by_id


class ManagedGame:
    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.cond = asyncio.Condition()
        self.sockets: dict[str, set[WebSocket]] = {"p1": set(), "p2": set()}
        self.version: int = 1


class GameManager:
    def __init__(self) -> None:
        self.games: dict[str, ManagedGame] = {}
        self.latest_game_id: Optional[str] = None

    def resolve_game_id(self, game_id: str) -> str:
        if game_id == "latest":
            if not self.latest_game_id or self.latest_game_id not in self.games:
                raise GameError("No active games found.")
            return self.latest_game_id
        if game_id not in self.games:
            raise GameError(f"Game '{game_id}' not found.")
        return game_id

    def get_managed(self, game_id: str) -> ManagedGame:
        gid = self.resolve_game_id(game_id)
        return self.games[gid]

    def list_games(self) -> list[dict[str, Any]]:
        out = []
        for gid, mg in sorted(
            self.games.items(),
            key=lambda kv: kv[1].engine.state.created_at,
            reverse=True,
        ):
            st = mg.engine.state
            p1 = st.players["p1"]
            p2 = st.players["p2"]
            out.append({
                "game_id": gid,
                "mode": st.mode,
                "phase": st.phase,
                "turn_number": st.turn_number,
                "active_seat": st.active_seat,
                "winner": st.winner,
                "p1": {
                    "name": p1.name,
                    "hero_class": p1.hero.card_class,
                    "hp": p1.hero.hp,
                },
                "p2": {
                    "name": p2.name,
                    "hero_class": p2.hero.card_class,
                    "hp": p2.hero.hp,
                },
                "is_latest": gid == self.latest_game_id,
            })
        return out

    async def create_game(
        self,
        p1_name: str = "Player",
        p1_deck_id: Optional[str] = None,
        p1_class: Optional[str] = None,
        p1_cards: Optional[list[str]] = None,
        p2_mode: str = "cli",  # "cli" | "bot"
        p2_deck_choice: str = "random",  # "await_cli" | "random" | deck_id
        p2_name: Optional[str] = None,
    ) -> ManagedGame:
        if p1_deck_id:
            d1 = get_deck_by_id(p1_deck_id)
            if not d1:
                raise GameError(f"Deck '{p1_deck_id}' not found.")
            p1_class = d1["hero_class"]
            p1_cards = d1["cards"]
            p1_deck_name = d1["name"]
        else:
            if not p1_class or not p1_cards:
                d1 = STARTER_DECKS["MAGE"]
                p1_class = d1["hero_class"]
                p1_cards = d1["cards"]
                p1_deck_name = d1["name"]
            else:
                ok, msg = validate_deck(p1_class, p1_cards)
                if not ok:
                    raise GameError(msg)
                p1_deck_name = f"Custom {p1_class.title()}"

        mode = "bot_vs_human" if p2_mode == "bot" else "cli_vs_human"
        opp_name = p2_name or ("Practice Bot" if mode == "bot_vs_human" else "Antigravity")

        p2_class: Optional[str] = None
        p2_cards: Optional[list[str]] = None
        p2_deck_name = ""

        if p2_deck_choice == "await_cli" and mode == "cli_vs_human":
            pass
        elif p2_deck_choice == "random" or (p2_deck_choice == "await_cli" and mode == "bot_vs_human"):
            cls = random.choice(list(HEROES.keys()))
            d2 = STARTER_DECKS[cls]
            p2_class = d2["hero_class"]
            p2_cards = d2["cards"]
            p2_deck_name = d2["name"]
        else:
            d2 = get_deck_by_id(p2_deck_choice)
            if not d2:
                # Also allow passing a class name directly like "WARRIOR"
                upper = p2_deck_choice.upper()
                if upper in STARTER_DECKS:
                    d2 = STARTER_DECKS[upper]
                else:
                    raise GameError(f"Opponent deck '{p2_deck_choice}' not found.")
            p2_class = d2["hero_class"]
            p2_cards = d2["cards"]
            p2_deck_name = d2["name"]

        eng = GameEngine.create_game(
            p1_name=p1_name or "Player",
            p1_class=p1_class,
            p1_deck=p1_cards,
            p1_deck_name=p1_deck_name,
            p2_name=opp_name,
            p2_class=p2_class,
            p2_deck=p2_cards,
            p2_deck_name=p2_deck_name,
            mode=mode,
        )
        mg = ManagedGame(eng)
        self.games[eng.state.game_id] = mg
        self.latest_game_id = eng.state.game_id

        if mode == "bot_vs_human" and eng.state.phase == "MULLIGAN":
            run_bot_mulligan(eng, "p2")

        await self.notify(mg)
        return mg

    async def maybe_step_bot(self, mg: ManagedGame) -> None:
        eng = mg.engine
        if eng.state.mode != "bot_vs_human":
            return
        if eng.state.phase == "MULLIGAN" and not eng.state.players["p2"].mulligan_done:
            run_bot_mulligan(eng, "p2")
        if eng.state.phase == "PLAY" and eng.state.active_seat == "p2":
            run_bot_turn(eng, "p2")

    @staticmethod
    def is_seat_ready_to_act(eng: GameEngine, seat: str) -> bool:
        st = eng.state
        if st.phase == "GAME_OVER":
            return True
        if st.phase == "WAITING_FOR_P2_DECK":
            return seat == "p2"
        if st.phase == "MULLIGAN":
            return not st.players[seat].mulligan_done
        if st.phase == "PLAY":
            if st.pending_choice is not None:
                return st.pending_choice.seat == seat
            return st.active_seat == seat
        return False

    async def notify(self, mg: ManagedGame) -> None:
        mg.version += 1
        async with mg.cond:
            mg.cond.notify_all()
        for seat in ("p1", "p2"):
            if not mg.sockets[seat]:
                continue
            payload = {"type": "state", "state": mg.engine.serialize_for_seat(seat)}
            dead: list[WebSocket] = []
            for ws in list(mg.sockets[seat]):
                try:
                    await ws.send_json(payload)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                mg.sockets[seat].discard(ws)

    async def wait_for_turn(self, game_id: str, seat: str, timeout: float = 45.0) -> tuple[bool, dict[str, Any]]:
        mg = self.get_managed(game_id)
        if self.is_seat_ready_to_act(mg.engine, seat):
            return True, mg.engine.serialize_for_seat(seat)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.5, min(timeout, 120.0))
        async with mg.cond:
            while not self.is_seat_ready_to_act(mg.engine, seat):
                rem = deadline - loop.time()
                if rem <= 0:
                    return False, mg.engine.serialize_for_seat(seat)
                try:
                    await asyncio.wait_for(mg.cond.wait(), timeout=rem)
                except asyncio.TimeoutError:
                    return (
                        self.is_seat_ready_to_act(mg.engine, seat),
                        mg.engine.serialize_for_seat(seat),
                    )
        return True, mg.engine.serialize_for_seat(seat)
