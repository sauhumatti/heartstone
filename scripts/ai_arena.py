#!/usr/bin/env python3
"""Play the on-device opponent against itself or the practice bot and count the wins.

    python3 scripts/ai_arena.py normal bot --games 100
    python3 scripts/ai_arena.py hard normal --games 100 --workers 3
    python3 scripts/ai_arena.py normal easy --games 40 --budget 150     # as on a slow device
    python3 scripts/ai_arena.py normal normal --a-set W_HERO=8,lv.width=6   # try a change against the present AI

Players: easy, normal, hard (engine/ai.py) and bot (the practice bot, engine/bot.py).
Games come in pairs: the same decks and the same shuffle, with the two players swapping seats,
so neither the decks nor going first favours one of them. Decks rotate through every starter deck.

--a-set / --b-set change the first / second player's AI for this run only: NAME=value sets a
weight in engine/ai.py, lv.NAME=value a setting of that player's level.
"""
from __future__ import annotations

import argparse
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.starter_decks import STARTER_DECKS  # noqa: E402
from engine import ai  # noqa: E402
from engine.bot import run_bot_mulligan, run_bot_turn  # noqa: E402
from engine.game import GameEngine  # noqa: E402

CLASSES = sorted(STARTER_DECKS)
PLAYERS = ("easy", "normal", "hard", "bot")
MAX_TURNS = 140


def parse_changes(text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for part in filter(None, (text or "").split(",")):
        name, _, raw = part.partition("=")
        value: float = float(raw)
        out[name.strip()] = int(value) if value == int(value) and "." not in raw else value
    return out


class Changed:
    """The AI with one player's changes in place, put back afterwards."""

    def __init__(self, level: str, changes: dict[str, float]):
        self.level = level
        self.changes = changes
        self.before: list[tuple] = []

    def __enter__(self) -> None:
        for name, value in self.changes.items():
            if name.startswith("lv."):
                lv = ai._LEVELS[self.level]
                self.before.append((lv, name[3:], lv[name[3:]]))
                lv[name[3:]] = value
            else:
                self.before.append((None, name, getattr(ai, name)))
                setattr(ai, name, value)

    def __exit__(self, *exc: object) -> None:
        for holder, name, value in reversed(self.before):
            if holder is None:
                setattr(ai, name, value)
            else:
                holder[name] = value
        self.before.clear()


def play(job: tuple) -> dict:
    """One game. Returns who won and how long each side thought."""
    index, seats, players, c1, c2, seed, budget = job  # seats: seat -> "a" | "b"; players: slot -> (name, changes)
    eng = GameEngine.create_game(
        "P1", c1, STARTER_DECKS[c1]["cards"], c1, "P2", c2, STARTER_DECKS[c2]["cards"], c2,
        mode="bot_vs_human", rng_seed=seed,
    )
    rngs = {s: random.Random(seed * 7919 + i) for i, s in enumerate(("p1", "p2"))}
    stats = {s: {"decisions": 0, "time": 0.0, "worst": 0.0, "turns": 0, "turn_time": 0.0, "worst_turn": 0.0} for s in ("p1", "p2")}

    def act(seat: str) -> None:
        who, changes = players[seats[seat]]
        st = stats[seat]
        if who == "bot":
            if eng.state.phase == "MULLIGAN":
                run_bot_mulligan(eng, seat)
            else:
                run_bot_turn(eng, seat)
            return
        in_play = eng.state.phase == "PLAY"
        turn_time = 0.0
        with Changed(who, changes):
            while True:
                t = time.perf_counter()
                acted = ai.step(eng, seat, level=who, budget_ms=budget, rng=rngs[seat])
                dt = time.perf_counter() - t
                if not acted:
                    break
                st["decisions"] += 1
                st["time"] += dt
                st["worst"] = max(st["worst"], dt)
                turn_time += dt
        if in_play:
            st["turns"] += 1
            st["turn_time"] += turn_time
            st["worst_turn"] = max(st["worst_turn"], turn_time)

    act("p1")
    act("p2")
    for _ in range(MAX_TURNS):
        if eng.state.phase != "PLAY":
            break
        before = (eng.state.turn_number, eng.state.active_seat)
        act(eng.state.active_seat)
        if eng.state.phase == "PLAY" and (eng.state.turn_number, eng.state.active_seat) == before:
            eng.end_turn(eng.state.active_seat)  # a player that would not move: do not hang the arena
    ai.forget(eng.state.game_id)
    winner = eng.state.winner if eng.state.phase == "GAME_OVER" else "draw"
    counts = dict(ai.STATS)
    for k in ai.STATS:
        ai.STATS[k] = 0
    return {"index": index, "winner": winner, "seats": seats, "turns": eng.state.turn_number, "stats": stats, "counts": counts}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a", choices=PLAYERS)
    ap.add_argument("b", choices=PLAYERS)
    ap.add_argument("--games", type=int, default=100)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--budget", type=float, default=60000, help="milliseconds per decision (default: no practical limit, so results repeat)")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--a-set", default="", metavar="NAME=VALUE,...", help="changes to the first player's AI")
    ap.add_argument("--b-set", default="", metavar="NAME=VALUE,...", help="changes to the second player's AI")
    args = ap.parse_args()

    players = {"a": (args.a, parse_changes(args.a_set)), "b": (args.b, parse_changes(args.b_set))}
    label = {
        slot: name + (" [" + ",".join(f"{k}={v}" for k, v in changes.items()) + "]" if changes else "")
        for slot, (name, changes) in players.items()
    }
    if label["a"] == label["b"]:
        label = {"a": label["a"] + " (first)", "b": label["b"] + " (second)"}

    pairs = [(c1, c2) for c1 in CLASSES for c2 in CLASSES]
    random.Random(args.seed).shuffle(pairs)
    jobs = []
    for g in range(args.games):
        c1, c2 = pairs[(g // 2) % len(pairs)]
        seed = args.seed * 100_000 + g // 2
        seats = {"p1": "a", "p2": "b"} if g % 2 == 0 else {"p1": "b", "p2": "a"}
        jobs.append((g, seats, players, c1, c2, seed, args.budget))

    t0 = time.time()
    if args.workers > 1:
        with Pool(args.workers) as pool:
            results = pool.map(play, jobs, chunksize=2)
    else:
        results = [play(j) for j in jobs]

    wins = {"a": 0, "b": 0}
    draws = 0
    turns = 0
    counts: dict[str, int] = {}
    agg = {slot: {"decisions": 0, "time": 0.0, "worst": 0.0, "turns": 0, "turn_time": 0.0, "worst_turn": 0.0} for slot in ("a", "b")}
    for r in results:
        for k, v in r["counts"].items():
            counts[k] = counts.get(k, 0) + v
        turns += r["turns"]
        if r["winner"] in ("p1", "p2"):
            wins[r["seats"][r["winner"]]] += 1
        else:
            draws += 1
        for seat, slot in r["seats"].items():
            s, a = r["stats"][seat], agg[slot]
            for k in ("decisions", "time", "turns", "turn_time"):
                a[k] += s[k]
            a["worst"] = max(a["worst"], s["worst"])
            a["worst_turn"] = max(a["worst_turn"], s["worst_turn"])

    n = len(results)
    print(f"{label['a']} vs {label['b']}: {n} games, {turns / n:.1f} turns a game, {time.time() - t0:.0f} s")
    for slot in ("a", "b"):
        print(f"  {label[slot]:<8s} won {wins[slot]:3d}  ({100 * (wins[slot] + draws / 2) / n:.1f}% counting a draw as half)")
    print(f"  draws {draws}")
    for slot in ("a", "b"):
        a = agg[slot]
        if players[slot][0] == "bot" or not a["decisions"]:
            continue
        print(
            f"  {label[slot]:<8s} thinking: {1000 * a['time'] / a['decisions']:.1f} ms a decision (worst {1000 * a['worst']:.0f} ms), "
            f"{1000 * a['turn_time'] / max(1, a['turns']):.0f} ms a turn (worst {1000 * a['worst_turn']:.0f} ms), "
            f"{a['decisions'] / max(1, a['turns']):.1f} decisions a turn"
        )
    if any(counts.values()):
        print(
            f"  AI internals: {counts['plans']} plans, {counts['imagined'] / max(1, counts['plans']):.0f} imagined moves a plan, "
            f"{counts['refused']} planned moves refused, {counts['errors']} errors, {counts['fallbacks']} fallbacks"
        )


if __name__ == "__main__":
    main()
