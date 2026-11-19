"""Write the beats of a few bot-vs-bot matches as JSON (one seat's view) to stdout.

Used by `npm run test:reducer` to check the web client's reducer against real engine output:
    PYTHONPATH=. python3 scripts/dump_beats.py | node frontend/scripts/check-reducer.mjs
"""
from __future__ import annotations

import json
import sys

from data.starter_decks import STARTER_DECKS
from engine.bot import run_bot_mulligan, run_bot_turn
from engine.game import GameEngine

SEAT = "p1"


def strip(view: dict) -> dict:
    return {k: v for k, v in view.items() if k != "log"}


def play(c1: str, c2: str, seed: int) -> dict:
    eng = GameEngine.create_game(
        p1_name="P1",
        p1_class=c1,
        p1_deck=STARTER_DECKS[c1]["cards"],
        p1_deck_name=c1,
        p2_name="P2",
        p2_class=c2,
        p2_deck=STARTER_DECKS[c2]["cards"],
        p2_deck_name=c2,
        mode="bot_vs_human",
        rng_seed=seed,
    )
    start = strip(eng.state.checkpoints[0]["views"][SEAT])
    beats: list[dict] = []
    seen = eng.state.cp_seq

    def drain() -> None:
        nonlocal seen
        for b in eng.beats_for_seat(SEAT, seen) or []:
            beats.append({"seq": b["seq"], "prev": b["prev"], "events": b["events"], "state": strip(b["state"])})
            seen = b["seq"]

    run_bot_mulligan(eng, "p1")
    drain()
    run_bot_mulligan(eng, "p2")
    drain()
    for _ in range(120):
        if eng.state.phase != "PLAY":
            break
        run_bot_turn(eng, eng.state.active_seat)
        drain()
    return {"name": f"{c1} vs {c2} #{seed}", "start": start, "beats": beats}


def main() -> None:
    classes = sorted(STARTER_DECKS)
    games = [play(c, classes[(i + 3) % len(classes)], 500 + i) for i, c in enumerate(classes)]
    json.dump(games, sys.stdout)


if __name__ == "__main__":
    main()
