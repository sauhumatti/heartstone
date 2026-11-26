"""The game with no server: one player on one device, the other seat played
by the built-in opponent.

Online, server/manager.py and server/app.py sit between the engine and the
page. Here this module does their job, minus the network: it starts matches,
answers every action with the same `{state, beats, agent}` reply the server
gives, moves the opponent one decision at a time, and turns a match into
bytes and back so it survives the app being closed.

It imports nothing but the engine and the standard library, so it runs under
Pyodide in a browser exactly as it runs here. `call()` takes and returns JSON
text, which is all the JavaScript side needs.
"""
from __future__ import annotations

import hashlib
import json
import pickle
import random
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from data.meta_decks import META_POOLS
from data.starter_decks import ALL_BUILTIN_DECKS, STARTER_DECKS, opponent_decks
from engine.bot import run_bot_mulligan, run_bot_turn
from engine.catalog import COLLECTIBLE_CARDS, HEROES, validate_deck
from engine.game import GameEngine, GameError

try:  # the opponent proper; without it (or if it cannot load here) the practice bot plays
    from engine import ai as _ai
except Exception:  # pragma: no cover - depends on what is installed
    _ai = None

MODE = "ai_vs_human"
ID_PREFIX = "local_"
PLAYER = "p1"
OPPONENT = "p2"

# Bump when what `save()` writes changes; older saves are then dropped on restore.
SAVE_VERSION = 1

# What the player is told when a kept match has to be let go.
GONE_UNREADABLE = "A saved match could not be read and was removed."
GONE_OLDER = "A saved match was made by an older version of the game and could not be continued, so it was removed."

_engine_tag: Optional[str] = None


def engine_tag() -> str:
    """A fingerprint of the rules as installed (the engine's and the cards' files).

    A kept match remembers the tag it was saved under. After an update the tag differs, and
    such a match is handled with care: if it stumbles, it is dropped instead of left stuck.
    """
    global _engine_tag
    if _engine_tag is None:
        h = hashlib.sha256()
        root = Path(__file__).resolve().parent.parent
        try:
            for folder in ("engine", "data"):
                for f in sorted((root / folder).iterdir()):
                    if f.suffix in (".py", ".json"):
                        h.update(f.name.encode())
                        h.update(f.read_bytes())
            _engine_tag = h.hexdigest()[:16]
        except OSError:
            _engine_tag = "unknown"
    return _engine_tag
# One decision may be followed by this many more in the same turn before the turn is ended for it.
MAX_STEPS_PER_TURN = 60

# How each level is shown. How long it may think about one decision is the opponent's
# own figure (`ai.SUGGESTED_BUDGET_MS`); the numbers here are only used without it.
_LEVEL_INFO: dict[str, dict[str, Any]] = {
    "easy": {"label": "Easy", "name": "Apprentice", "budget_ms": 250},
    "normal": {"label": "Normal", "name": "Adept", "budget_ms": 700},
    "hard": {"label": "Hard", "name": "Master", "budget_ms": 1500},
}
DEFAULT_LEVEL = "normal"


def level_ids() -> tuple[str, ...]:
    ids = tuple(getattr(_ai, "LEVELS", ())) if _ai is not None else ()
    return ids or tuple(_LEVEL_INFO)


def level_info(level: str) -> dict[str, Any]:
    info = dict(_LEVEL_INFO.get(level) or {"label": level.title(), "name": level.title(), "budget_ms": 700})
    suggested = getattr(_ai, "SUGGESTED_BUDGET_MS", None) if _ai is not None else None
    if isinstance(suggested, dict) and level in suggested:
        info["budget_ms"] = suggested[level]
    return {"id": level, **info}


def _drop_plan(game_id: str) -> None:
    """The opponent keeps its plan for the turn by game id; let go of it when the match is over or replaced."""
    drop = getattr(_ai, "forget", None) if _ai is not None else None
    if drop is not None:
        try:
            drop(game_id)
        except Exception:
            traceback.print_exc()


def catalog() -> dict[str, Any]:
    """The card list and the heroes, as GET /api/cards gives them."""
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


def starter_decks() -> list[dict[str, Any]]:
    return [d | {"builtin": True} for d in ALL_BUILTIN_DECKS]


def _starter_by_id(deck_id: str) -> Optional[dict[str, Any]]:
    for d in ALL_BUILTIN_DECKS:
        if d["id"] == deck_id:
            return d
    return STARTER_DECKS.get(deck_id.upper())


class _Match:
    def __init__(self, engine: GameEngine, level: str):
        self.engine = engine
        self.level = level
        # What the page is told about the opponent; `rev` grows with every change.
        self.status: dict[str, Any] = {"thinking": False, "error": "", "rev": 0.0}
        self.turn_seen = -1
        self.steps_this_turn = 0
        self.touched = time.time()
        # Brought back from a save made under other rules (an update came in between).
        self.older = False


class LocalHost:
    """Every match played on this device."""

    def __init__(self, think: Optional[Callable[..., bool]] = None) -> None:
        self.matches: dict[str, _Match] = {}
        self.latest_game_id: Optional[str] = None
        # Why kept matches were let go, for the page to tell the player once.
        self.discarded: list[str] = []
        # How the opponent makes one decision; tests swap this.
        self._think = think or (getattr(_ai, "step", None) if _ai is not None else None)

    # -- lookups ---------------------------------------------------------------

    def _get(self, game_id: str) -> _Match:
        if game_id == "latest":
            game_id = self.latest_game_id or ""
        m = self.matches.get(game_id)
        if m is None:
            raise GameError(f"Game '{game_id}' not found.")
        return m

    def info(self) -> dict[str, Any]:
        return {
            "levels": [level_info(lv) for lv in level_ids()],
            "default_level": DEFAULT_LEVEL if DEFAULT_LEVEL in level_ids() else level_ids()[0],
            # False means the full opponent is missing and the practice bot plays every level.
            "ai": self._think is not None,
            "save_version": SAVE_VERSION,
            "engine": engine_tag(),
        }

    def take_notices(self) -> dict[str, Any]:
        """What happened to kept matches that could not be continued; each sentence is handed out once."""
        notices, self.discarded = list(dict.fromkeys(self.discarded)), []
        return {"notices": notices}

    def catalog(self) -> dict[str, Any]:
        return catalog()

    def decks(self) -> dict[str, Any]:
        return {"decks": starter_decks()}

    def validate_deck(self, hero_class: str, cards: list[str]) -> dict[str, Any]:
        ok, msg = validate_deck(hero_class, list(cards))
        return {"ok": ok, "message": msg}

    def summary(self, game_id: str) -> dict[str, Any]:
        return self._summary_of(self._get(game_id))

    def _summary_of(self, m: _Match) -> dict[str, Any]:
        st = m.engine.state
        p1, p2 = st.players["p1"], st.players["p2"]
        return {
            "game_id": st.game_id,
            "mode": st.mode,
            "phase": st.phase,
            "turn_number": st.turn_number,
            "active_seat": st.active_seat,
            "winner": st.winner,
            "p1": {"name": p1.name, "hero_class": p1.hero.card_class, "hp": p1.hero.hp},
            "p2": {"name": p2.name, "hero_class": p2.hero.card_class, "hp": p2.hero.hp},
            "is_latest": st.game_id == self.latest_game_id,
            "level": m.level,
            "created_at": st.created_at,
            "updated_at": m.touched,
        }

    def games(self) -> dict[str, Any]:
        order = sorted(self.matches, key=lambda g: self.matches[g].engine.state.created_at, reverse=True)
        return {"games": [self.summary(g) for g in order], "latest_game_id": self.latest_game_id}

    # -- replies -----------------------------------------------------------------

    def _agent(self, m: _Match) -> dict[str, Any]:
        info = level_info(m.level)
        thinking = self._pending(m)
        if m.status["thinking"] != thinking:
            m.status["thinking"] = thinking
            # Wall-clock based, like the server's, so the order also holds after a restore.
            m.status["rev"] = max(time.time(), m.status["rev"] + 0.001)
        return {
            "model": m.level,
            "label": info["name"],
            "thinking": thinking,
            "typing": False,  # the on-device opponent does not chat
            "error": m.status["error"],
            "rev": m.status["rev"],
        }

    def _payload(self, m: _Match, since: Optional[int]) -> dict[str, Any]:
        """What the server's `_payload` returns: the view, the beats not seen yet, the opponent's status."""
        return {
            "state": m.engine.serialize_for_seat(PLAYER),
            "beats": m.engine.beats_for_seat(PLAYER, since),
            "agent": self._agent(m),
        }

    def state(self, game_id: str, since: Optional[int] = None) -> dict[str, Any]:
        return self._payload(self._get(game_id), since)

    # -- starting a match ----------------------------------------------------------

    @staticmethod
    def _deck(
        deck_id: Optional[str],
        hero_class: Optional[str],
        cards: Optional[list[str]],
        name: Optional[str],
        allow_duplicates: bool = False,
    ) -> tuple[str, list[str], str]:
        if hero_class and cards:
            ok, msg = validate_deck(hero_class, list(cards), allow_duplicates=allow_duplicates)
            if not ok:
                raise GameError(msg)
            return hero_class, list(cards), (name or f"Custom {hero_class.title()}")
        if deck_id:
            d = _starter_by_id(deck_id)
            if d is None:
                raise GameError(f"Deck '{deck_id}' not found.")
            return d["hero_class"], list(d["cards"]), d["name"]
        d = STARTER_DECKS["MAGE"]
        return d["hero_class"], list(d["cards"]), d["name"]

    def create_game(
        self,
        p1_name: str = "Player",
        p1_deck_id: Optional[str] = None,
        p1_class: Optional[str] = None,
        p1_cards: Optional[list[str]] = None,
        p1_deck_name: Optional[str] = None,
        p2_deck_choice: str = "random",
        p2_class: Optional[str] = None,
        p2_cards: Optional[list[str]] = None,
        p2_deck_name: Optional[str] = None,
        p2_name: Optional[str] = None,
        level: str = DEFAULT_LEVEL,
        seed: Optional[int] = None,
        arena: bool = False,
        campaign: bool = False,
        p1_hp: int = 30,
        p1_armor: int = 0,
        p1_bonus_mana: int = 0,
        p1_bonus_cards: int = 0,
        p2_hp: int = 30,
        p2_armor: int = 0,
        p2_bonus_mana: int = 0,
        p1_relic: str = "none",
        p1_relic_name: str = "",
        p1_relic_text: str = "",
        p2_passive: str = "",
        p2_passive_power: int = 1,
        p2_passive_name: str = "",
        p2_passive_text: str = "",
        p2_opening_board: Optional[list[str]] = None,
        p2_intro_quote: str = "",
        p2_mid_quote: str = "",
    ) -> dict[str, Any]:
        if level not in level_ids():
            level = DEFAULT_LEVEL if DEFAULT_LEVEL in level_ids() else level_ids()[0]
        c1, d1, n1 = self._deck(p1_deck_id, p1_class, p1_cards, p1_deck_name, allow_duplicates=arena)
        first_deck = _starter_by_id(p1_deck_id) if p1_deck_id and not (p1_class and p1_cards) else None
        era = "arena" if arena else ("campaign" if campaign else (first_deck.get("era", "") if first_deck else ("" if p1_cards else "classic")))
        meta = era in META_POOLS
        if p2_class and p2_cards:
            if meta:
                raise GameError("Choose an opponent deck from the same expansion.")
            c2, d2, n2 = self._deck(None, p2_class, p2_cards, p2_deck_name, allow_duplicates=(arena or campaign))
        elif p2_deck_choice in ("", "random", "await_cli"):
            rng = random.Random(seed) if seed is not None else random
            pick_d = rng.choice(opponent_decks(era))
            c2, d2, n2 = self._deck(pick_d["id"], None, None, None)
        else:
            second_deck = _starter_by_id(p2_deck_choice)
            if meta and (not second_deck or second_deck.get("era") != era):
                raise GameError("Choose an opponent deck from the same expansion.")
            c2, d2, n2 = self._deck(p2_deck_choice, None, None, None)

        boss_name = (p2_name or "").strip()[:32] or None
        eng = GameEngine.create_game(
            p1_name=(p1_name or "Player").strip()[:24] or "Player",
            p1_class=c1,
            p1_deck=d1,
            p1_deck_name=n1,
            p2_name=boss_name or level_info(level)["name"],
            p2_class=c2,
            p2_deck=d2,
            p2_deck_name=n2,
            mode=MODE,
            game_id=ID_PREFIX + uuid.uuid4().hex[:8],
            rng_seed=seed,
            deck_era=era,
            p1_hp=p1_hp,
            p1_armor=p1_armor,
            p1_bonus_mana=p1_bonus_mana,
            p1_bonus_cards=p1_bonus_cards,
            p2_hp=p2_hp,
            p2_armor=p2_armor,
            p2_bonus_mana=p2_bonus_mana,
            p2_hero_name=boss_name if campaign else None,
            p1_relic=p1_relic,
            p1_relic_name=p1_relic_name,
            p1_relic_text=p1_relic_text,
            p2_passive=p2_passive,
            p2_passive_power=p2_passive_power,
            p2_passive_name=p2_passive_name,
            p2_passive_text=p2_passive_text,
            p2_opening_board=p2_opening_board,
            p2_intro_quote=p2_intro_quote,
            p2_mid_quote=p2_mid_quote,
        )
        m = _Match(eng, level)
        self.matches[eng.state.game_id] = m
        self.latest_game_id = eng.state.game_id
        return {"game_id": eng.state.game_id, **self._payload(m, 0)}

    # -- the player's actions --------------------------------------------------------

    def _acted(self, m: _Match, since: Optional[int]) -> dict[str, Any]:
        m.touched = time.time()
        if m.engine.state.phase == "GAME_OVER":
            _drop_plan(m.engine.state.game_id)
        return self._payload(m, since)

    def mulligan(self, game_id: str, since: Optional[int] = None, replace_indices: Optional[list[int]] = None) -> dict[str, Any]:
        m = self._get(game_id)
        m.engine.submit_mulligan(PLAYER, list(replace_indices or []))
        return self._acted(m, since)

    def play(
        self,
        game_id: str,
        since: Optional[int] = None,
        hand_index: int = 0,
        pos: Optional[int] = None,
        target_id: Optional[str] = None,
        choose: Optional[int] = None,
    ) -> dict[str, Any]:
        m = self._get(game_id)
        m.engine.play_card(PLAYER, hand_index, pos=pos, target_id=target_id, choose=choose)
        return self._acted(m, since)

    def choose(self, game_id: str, since: Optional[int] = None, option_index: int = 0) -> dict[str, Any]:
        m = self._get(game_id)
        m.engine.resolve_pending_choice(PLAYER, option_index)
        return self._acted(m, since)

    def attack(self, game_id: str, since: Optional[int] = None, attacker_id: str = "", target_id: str = "") -> dict[str, Any]:
        m = self._get(game_id)
        m.engine.attack(PLAYER, attacker_id, target_id)
        return self._acted(m, since)

    def power(self, game_id: str, since: Optional[int] = None, target_id: Optional[str] = None) -> dict[str, Any]:
        m = self._get(game_id)
        m.engine.use_hero_power(PLAYER, target_id=target_id)
        return self._acted(m, since)

    def end_turn(self, game_id: str, since: Optional[int] = None) -> dict[str, Any]:
        m = self._get(game_id)
        m.engine.end_turn(PLAYER)
        return self._acted(m, since)

    def concede(self, game_id: str, since: Optional[int] = None) -> dict[str, Any]:
        m = self._get(game_id)
        m.engine.concede(PLAYER)
        return self._acted(m, since)

    def emote(self, game_id: str, message: str = "") -> dict[str, Any]:
        m = self._get(game_id)
        m.engine.send_emote(PLAYER, message)
        m.touched = time.time()
        return {"ok": True}

    def set_level(self, game_id: str, level: str, since: Optional[int] = None) -> dict[str, Any]:
        """Change how strong the opponent plays, mid-match."""
        m = self._get(game_id)
        if level not in level_ids():
            raise GameError(f"Unknown level '{level}'.")
        if level != m.level:
            m.level = level
            m.engine.state.players[OPPONENT].name = level_info(level)["name"]
            m.status["rev"] = max(time.time(), m.status["rev"] + 0.001)
        return self._acted(m, since)

    # -- the opponent ------------------------------------------------------------------

    @staticmethod
    def _pending(m: _Match) -> bool:
        st = m.engine.state
        if st.phase == "MULLIGAN":
            return not st.players[OPPONENT].mulligan_done
        if st.phase == "PLAY":
            if st.pending_choice is not None:
                return st.pending_choice.seat == OPPONENT
            return st.active_seat == OPPONENT
        return False

    def opponent_pending(self, game_id: str) -> bool:
        """Is everybody waiting for the opponent?"""
        return self._pending(self._get(game_id))

    def opponent_step(self, game_id: str) -> bool:
        """Let the opponent make one decision. False when it had nothing to decide.

        Call it in a loop and send the page what happened after each step, so its
        moves are seen one at a time.
        """
        m = self._get(game_id)
        if not self._pending(m):
            return False
        eng = m.engine
        st = eng.state
        if st.turn_number != m.turn_seen:
            m.turn_seen = st.turn_number
            m.steps_this_turn = 0
        m.steps_this_turn += 1
        mark = (st.seq, st.phase, st.active_seat, st.pending_choice is None)
        problem = ""
        if self._think is None:
            self._bot(m)
        elif m.steps_this_turn > MAX_STEPS_PER_TURN:
            problem = "it could not finish its turn"
        else:
            try:
                acted = self._think(eng, OPPONENT, level=m.level, budget_ms=level_info(m.level)["budget_ms"])
                if not acted or (st.seq, st.phase, st.active_seat, st.pending_choice is None) == mark:
                    problem = "it did not move"
            except Exception as exc:  # the match must go on whatever happens in there
                traceback.print_exc()
                problem = f"it stopped ({type(exc).__name__})"
        if problem and self._pending(m):
            self._bot(m)
        if m.status["error"] != problem:
            m.status["error"] = problem
            m.status["rev"] = max(time.time(), m.status["rev"] + 0.001)
        m.touched = time.time()
        if st.phase == "GAME_OVER":
            _drop_plan(st.game_id)
        return True

    def _bot(self, m: _Match) -> None:
        """The practice bot makes this decision (in play: the rest of the turn)."""
        eng = m.engine
        st = eng.state
        try:
            if st.phase == "MULLIGAN":
                run_bot_mulligan(eng, OPPONENT)
            elif st.phase == "PLAY" and st.pending_choice is not None:
                eng.resolve_pending_choice(OPPONENT, 0)
            elif st.phase == "PLAY":
                try:
                    run_bot_turn(eng, OPPONENT)
                finally:
                    # Whatever happened in there, the player must get the turn back.
                    if st.phase == "PLAY" and st.pending_choice is None and st.active_seat == OPPONENT:
                        eng.end_turn(OPPONENT)
        except GameError:
            traceback.print_exc()

    def run_opponent(self, game_id: str, limit: int = 400) -> int:
        """Let the opponent decide until it is the player's move again. Returns the number of decisions."""
        n = 0
        while n < limit and self.opponent_step(game_id):
            n += 1
        return n

    # -- keeping a match -----------------------------------------------------------------

    def save(self, game_id: str) -> bytes:
        m = self._get(game_id)
        return pickle.dumps(
            {
                "v": SAVE_VERSION,
                "engine": engine_tag(),
                "state": m.engine.state,
                "rng": m.engine.rng.getstate(),
                "level": m.level,
                "status": dict(m.status),
                "touched": m.touched,
            },
            protocol=4,
        )

    def restore(self, blob: bytes) -> Optional[dict[str, Any]]:
        """Bring back a match written by `save()`. Returns its summary, or None if it cannot be used.

        Only ever given what this same app stored on this device. It never raises: a save that
        cannot be read, or that an update has left behind, is refused, and `take_notices()` says why.
        """
        try:
            data = pickle.loads(bytes(blob))
        except Exception:
            # not a save at all, or one naming things this version of the game no longer has
            self.discarded.append(GONE_UNREADABLE if not blob or bytes(blob[:1]) != b"\x80" else GONE_OLDER)
            return None
        try:
            if not isinstance(data, dict) or data.get("v") != SAVE_VERSION:
                self.discarded.append(GONE_OLDER)
                return None
            eng = GameEngine(data["state"])
            eng.rng.setstate(data["rng"])
            gid = eng.state.game_id
            if not gid.startswith(ID_PREFIX) or eng.state.mode != MODE:
                self.discarded.append(GONE_UNREADABLE)
                return None
            level = data.get("level") if data.get("level") in level_ids() else level_ids()[0]
            m = _Match(eng, level)
            m.status.update(data.get("status") or {})
            m.touched = float(data.get("touched") or time.time())
            m.older = data.get("engine") != engine_tag()
            # Everything the page asks first must work; a save that no longer fits fails here.
            json.dumps(self._payload(m, None))
            self._pending(m)
            self._summary_of(m)
        except Exception:
            self.discarded.append(GONE_OLDER)
            return None
        _drop_plan(gid)  # a plan made for the match this one replaces must not be followed
        self.matches[gid] = m
        newest = max(self.matches, key=lambda g: self.matches[g].engine.state.created_at)
        self.latest_game_id = newest
        return self.summary(gid)

    def forget(self, game_id: str) -> dict[str, Any]:
        self.matches.pop(game_id, None)
        _drop_plan(game_id)
        if self.latest_game_id == game_id:
            self.latest_game_id = max(self.matches, key=lambda g: self.matches[g].engine.state.created_at) if self.matches else None
        return {"ok": True}

    # -- the JSON door -------------------------------------------------------------------

    _OPEN = (
        "info", "catalog", "decks", "validate_deck", "games", "summary", "state", "create_game",
        "mulligan", "play", "choose", "attack", "power", "end_turn", "concede", "emote", "set_level",
        "opponent_pending", "opponent_step", "forget", "take_notices",
    )

    def call(self, method: str, args_json: str = "{}") -> str:
        """Run one method from JSON arguments. Always answers with JSON text:
        `{"ok": result}`, or `{"error": message}` when the game refuses the request."""
        if method not in self._OPEN:
            return json.dumps({"error": f"Unknown request '{method}'."})
        try:
            args = json.loads(args_json or "{}")
            return json.dumps({"ok": getattr(self, method)(**args)})
        except GameError as exc:
            return json.dumps({"error": str(exc)})
        except Exception as exc:
            traceback.print_exc()
            gone = self._drop_if_older(args_json)
            if gone:
                # `gone` tells the page the match no longer exists, so it can leave the table
                return json.dumps({"error": GONE_OLDER, "gone": gone, "detail": f"{type(exc).__name__}: {exc}"})
            return json.dumps({"error": "The game engine ran into a problem.", "detail": f"{type(exc).__name__}: {exc}"})

    def _drop_if_older(self, args_json: str) -> Optional[str]:
        """A match kept from before an update has just broken: let it go rather than leave it stuck."""
        try:
            game_id = json.loads(args_json or "{}").get("game_id")
            if game_id == "latest":
                game_id = self.latest_game_id
            m = self.matches.get(game_id) if isinstance(game_id, str) else None
            if m is None or not m.older:
                return None
            self.forget(game_id)
            return game_id
        except Exception:
            return None
