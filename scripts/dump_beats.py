"""Write the beats of a few bot-vs-bot matches as JSON (one seat's view) to stdout.

Used by `npm run test:reducer` to check the web client's reducer against real engine output:
    PYTHONPATH=. python3 scripts/dump_beats.py | node frontend/scripts/check-reducer.mjs
"""
from __future__ import annotations

import json
import sys

from data.starter_decks import STARTER_DECKS, THEME_DECKS
from engine.bot import run_bot_mulligan, run_bot_turn
from engine.game import GameEngine

def strip(view: dict) -> dict:
    return {k: v for k, v in view.items() if k != "log"}


def play(d1: dict, d2: dict, seed: int, seat: str = "p1") -> dict:
    eng = GameEngine.create_game(
        p1_name="P1",
        p1_class=d1["hero_class"],
        p1_deck=d1["cards"],
        p1_deck_name=d1["name"],
        p2_name="P2",
        p2_class=d2["hero_class"],
        p2_deck=d2["cards"],
        p2_deck_name=d2["name"],
        mode="bot_vs_human",
        rng_seed=seed,
    )
    start = strip(eng.state.checkpoints[0]["views"][seat])
    beats: list[dict] = []
    seen = eng.state.cp_seq

    def drain() -> None:
        nonlocal seen
        for b in eng.beats_for_seat(seat, seen) or []:
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
    return {"name": f"{d1['name']} vs {d2['name']} #{seed} ({seat})", "start": start, "beats": beats}


def main() -> None:
    starters = [STARTER_DECKS[cls] for cls in sorted(STARTER_DECKS)]
    games = [play(d, starters[(i + 3) % len(starters)], 500 + i) for i, d in enumerate(starters)]
    golden = {d["id"]: d for d in THEME_DECKS}
    # This seed triggers both the Demon from hand and the trap reveal.
    for seat in ("p1", "p2"):
        games.append(play(golden["golden_demon_warlock"], golden["golden_trap_hunter"], 511, seat))
    json.dump(games, sys.stdout)


if __name__ == "__main__":
    main()
