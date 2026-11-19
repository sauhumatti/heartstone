from __future__ import annotations

import asyncio
import pickle
import random
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import WebSocket

from data.starter_decks import STARTER_DECKS
from engine.bot import run_bot_mulligan, run_bot_turn
from engine.catalog import HEROES, validate_deck
from engine.game import GameEngine, GameError
from server import agent as outside_agent
from server.storage import get_deck_by_id

# Bump when the saved state layout changes; older saves are discarded.
SAVE_VERSION = 1


class ManagedGame:
    def __init__(self, engine: GameEngine):
        self.engine = engine
        self.cond = asyncio.Condition()
        # socket -> last beat seq sent to it
        self.sockets: dict[str, dict[WebSocket, int]] = {"p1": {}, "p2": {}}
        self.version: int = 1
        # The outside agent's seat (agent_vs_human): the running turn and what to show about it.
        self.agent_task: Optional[asyncio.Task] = None
        # `rev` grows with every change, so a client can tell a newer status from a late one.
        self.agent: dict[str, Any] = {"thinking": False, "error": "", "rev": 0}

    def set_agent(self, **changes: Any) -> None:
        if any(self.agent.get(k) != v for k, v in changes.items()):
            self.agent.update(changes)
            # Wall-clock based, so the order also holds across a server restart.
            self.agent["rev"] = max(time.time(), self.agent["rev"] + 0.001)


# Saved games older than this are dropped at startup.
SAVE_MAX_AGE_SECONDS = 14 * 24 * 3600


class GameManager:
    def __init__(self, persist_dir: Optional[Path] = None) -> None:
        self.games: dict[str, ManagedGame] = {}
        self.latest_game_id: Optional[str] = None
        self.persist_dir = persist_dir
        # How the outside agent is asked; tests swap this for a scripted one.
        self.ask_agent: outside_agent.Ask = outside_agent.ask_cli
        if persist_dir is not None:
            self._load_saved()

    # -- persistence: a match survives a server restart ----------------------

    def _save_path(self, game_id: str) -> Path:
        assert self.persist_dir is not None
        return self.persist_dir / f"{game_id}.pkl"

    def _save(self, mg: ManagedGame) -> None:
        if self.persist_dir is None:
            return
        try:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            path = self._save_path(mg.engine.state.game_id)
            tmp = path.with_suffix(".tmp")
            with tmp.open("wb") as fh:
                pickle.dump(
                    {"v": SAVE_VERSION, "state": mg.engine.state, "rng": mg.engine.rng.getstate()},
                    fh,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            tmp.replace(path)
        except Exception as exc:  # a failed save must never break the match
            print(f"[games] could not save {mg.engine.state.game_id}: {exc}")

    def _load_saved(self) -> None:
        assert self.persist_dir is not None
        if not self.persist_dir.exists():
            return
        now = time.time()
        for path in sorted(self.persist_dir.glob("*.pkl")):
            try:
                if now - path.stat().st_mtime > SAVE_MAX_AGE_SECONDS:
                    path.unlink()
                    continue
                # Only files this server wrote itself are ever read here.
                with path.open("rb") as fh:
                    data = pickle.load(fh)
                if data.get("v") != SAVE_VERSION:
                    path.unlink()
                    continue
                engine = GameEngine(data["state"])
                engine.rng.setstate(data["rng"])
                self.games[engine.state.game_id] = ManagedGame(engine)
            except Exception as exc:
                print(f"[games] skipping unreadable save {path.name}: {exc}")
        if self.games:
            self.latest_game_id = max(
                self.games, key=lambda gid: self.games[gid].engine.state.created_at
            )

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
        p2_agent_model: Optional[str] = None,
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

        mode = {"bot": "bot_vs_human", "agent": "agent_vs_human"}.get(p2_mode, "cli_vs_human")
        opp_name = p2_name or ("Practice Bot" if mode == "bot_vs_human" else "Antigravity")

        p2_class: Optional[str] = None
        p2_cards: Optional[list[str]] = None
        p2_deck_name = ""

        if p2_deck_choice == "await_cli" and mode != "bot_vs_human":
            pass  # the other side chooses: from the command line, or the agent is asked
        elif p2_deck_choice in ("random", "await_cli"):
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
        if mode == "agent_vs_human":
            eng.state.agent_model = p2_agent_model if p2_agent_model in outside_agent.MODELS else outside_agent.DEFAULT_MODEL
        mg = ManagedGame(eng)
        self.games[eng.state.game_id] = mg
        self.latest_game_id = eng.state.game_id

        if mode == "bot_vs_human" and eng.state.phase == "MULLIGAN":
            run_bot_mulligan(eng, "p2")

        await self.notify(mg)
        self.kick_agent(mg)
        return mg

    # -- the outside agent's seat ------------------------------------------------

    def agent_status(self, mg: ManagedGame) -> Optional[dict[str, Any]]:
        st = mg.engine.state
        if st.mode != "agent_vs_human":
            return None
        model = st.agent_model or outside_agent.DEFAULT_MODEL
        return {
            "model": model,
            "label": outside_agent.model_label(model),
            "thinking": bool(mg.agent["thinking"]),
            "error": mg.agent["error"],
            "rev": mg.agent["rev"],
        }

    def kick_agent(self, mg: ManagedGame) -> None:
        """Start the agent's turn if everybody is waiting for it. Safe to call any time."""
        st = mg.engine.state
        if st.mode != "agent_vs_human" or st.phase == "GAME_OVER":
            return
        if mg.agent_task is not None and not mg.agent_task.done():
            return
        if not outside_agent.wants_to_act(mg.engine):
            return
        if time.time() < mg.agent.get("retry_at", 0):
            return  # it just failed and nothing could stand in: do not hammer the CLI
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        # Marked as thinking right away, so the reply that triggered this already says so.
        mg.set_agent(thinking=True, error="")
        mg.agent_task = loop.create_task(self._run_agent(mg))

    async def _run_agent(self, mg: ManagedGame) -> None:
        eng = mg.engine
        model = eng.state.agent_model or outside_agent.DEFAULT_MODEL
        mg.set_agent(thinking=True, error="")
        await self.notify(mg)

        async def after_move() -> None:
            await self.notify(mg)

        def still_ours() -> bool:
            return eng.state.mode == "agent_vs_human" and eng.state.phase != "GAME_OVER"

        try:
            await outside_agent.take_turn(eng, model, after_move, ask=self.ask_agent, still_ours=still_ours)
        except outside_agent.AgentError as exc:
            mg.set_agent(error=str(exc))
            self._stand_in(mg)
        except Exception as exc:  # the match must go on whatever happens here
            print(f"[agent] {eng.state.game_id}: {exc!r}")
            mg.set_agent(error="The agent stopped unexpectedly.")
            self._stand_in(mg)
        finally:
            mg.set_agent(thinking=False)
            if mg.agent["error"] and outside_agent.wants_to_act(eng):
                mg.agent["retry_at"] = time.time() + 30
            await self.notify(mg)

    def _stand_in(self, mg: ManagedGame) -> None:
        """The agent could not decide: the practice bot makes this one decision so the match is not stuck."""
        eng = mg.engine
        st = eng.state
        if st.mode != "agent_vs_human" or not outside_agent.wants_to_act(eng):
            return
        try:
            if st.phase == "WAITING_FOR_P2_DECK":
                d = STARTER_DECKS[random.choice(list(HEROES.keys()))]
                eng.set_p2_deck(d["hero_class"], d["cards"], d["name"])
            elif st.phase == "MULLIGAN":
                run_bot_mulligan(eng, "p2")
            elif st.phase == "PLAY":
                eng.add_log(f"{st.players['p2'].name} did not answer; the practice bot played this turn.", seat="p2")
                run_bot_turn(eng, "p2")
        except GameError as exc:
            print(f"[agent] stand-in failed for {st.game_id}: {exc}")

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
        self._save(mg)
        async with mg.cond:
            mg.cond.notify_all()
        for seat in ("p1", "p2"):
            if not mg.sockets[seat]:
                continue
            state = mg.engine.serialize_for_seat(seat)
            dead: list[WebSocket] = []
            for ws, seen in list(mg.sockets[seat].items()):
                payload = {
                    "type": "state",
                    "state": state,
                    "beats": mg.engine.beats_for_seat(seat, seen),
                    "agent": self.agent_status(mg),
                }
                try:
                    await ws.send_json(payload)
                    mg.sockets[seat][ws] = state["seq"]
                except Exception:
                    dead.append(ws)
            for ws in dead:
                mg.sockets[seat].pop(ws, None)

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
