from __future__ import annotations

import copy
import inspect
import random
import subprocess
import sys
import time
import unittest
from pathlib import Path

from data.starter_decks import STARTER_DECKS
from engine import ai
from engine.bot import run_bot_mulligan, run_bot_turn
from engine.catalog import CARDS
from engine.game import GameEngine
from engine.models import SecretInstance

CLASSES = sorted(STARTER_DECKS.keys())
ROOT = Path(__file__).resolve().parent.parent
NO_LIMIT = 600_000  # milliseconds: the search then stops at its own size, so play repeats exactly


def new_game(c1: str = "MAGE", c2: str = "WARRIOR", seed: int = 7) -> GameEngine:
    return GameEngine.create_game(
        p1_name="P1", p1_class=c1, p1_deck=STARTER_DECKS[c1]["cards"], p1_deck_name=c1,
        p2_name="P2", p2_class=c2, p2_deck=STARTER_DECKS[c2]["cards"], p2_deck_name=c2,
        mode="bot_vs_human", rng_seed=seed,
    )


def other(seat: str) -> str:
    return "p2" if seat == "p1" else "p1"


def play_out(eng: GameEngine, levels: dict[str, str], seed: int = 1, max_turns: int = 160, on_step=None) -> None:
    """Both seats played by the AI until the game ends."""
    rngs = {"p1": random.Random(seed), "p2": random.Random(seed + 1)}
    for seat in ("p1", "p2"):
        while ai.step(eng, seat, levels[seat], NO_LIMIT, rngs[seat]):
            if on_step:
                on_step(seat)
    for _ in range(max_turns):
        if eng.state.phase != "PLAY":
            return
        seat = eng.state.active_seat
        steps = 0
        while ai.step(eng, seat, levels[seat], NO_LIMIT, rngs[seat]):
            steps += 1
            if on_step:
                on_step(seat)
            assert steps <= ai.MAX_DECISIONS_PER_TURN + 2, "a turn that does not end"
        assert eng.state.phase != "PLAY" or eng.state.active_seat != seat, "the AI stopped without ending its turn"


def midgame(seed: int, turns: int, c1: str, c2: str) -> GameEngine:
    """A position some turns into a game the AI played against itself."""
    eng = new_game(c1, c2, seed)
    rng = random.Random(seed)
    for seat in ("p1", "p2"):
        while ai.step(eng, seat, "normal", NO_LIMIT, rng):
            pass
    for _ in range(turns):
        if eng.state.phase != "PLAY":
            break
        seat = eng.state.active_seat
        while ai.step(eng, seat, "normal", NO_LIMIT, rng):
            pass
    ai.forget()
    return eng


def plain_minions() -> list:
    """Pieces with numbers and nothing else, picked by what they are rather than by name."""
    out = [c for c in CARDS.values() if c.type == "MINION" and c.collectible and not c.mechanics and not c.text and (c.attack or 0) >= 2]
    return sorted(out, key=lambda c: (c.cost, c.id))


def guard_minion():
    """A piece whose only ability is that it must be attacked first."""
    out = [c for c in CARDS.values() if c.type == "MINION" and c.collectible and tuple(c.mechanics) == ("TAUNT",) and 2 <= (c.health or 0) <= 4]
    return sorted(out, key=lambda c: (c.health, c.id))[0]


def cleared(seed: int = 3) -> tuple[GameEngine, str]:
    """A game at the start of a turn with empty boards and empty hands, and whose turn it is."""
    eng = new_game("WARRIOR", "WARRIOR", seed)
    eng.submit_mulligan("p1", [])
    eng.submit_mulligan("p2", [])
    seat = eng.state.active_seat
    for s in ("p1", "p2"):
        p = eng.state.players[s]
        p.hand.clear()
        p.board.clear()
        p.secrets.clear()
        p.weapon = None
    me = eng.state.players[seat]
    me.mana = me.max_mana = 0  # nothing but the pieces on the board to decide about
    eng.recompute_auras()
    return eng, seat


def put(eng: GameEngine, seat: str, card, ready: bool = True):
    m = eng.summon_minion(seat, card.id)
    m.summoned_this_turn = not ready
    eng.recompute_auras()
    return m


class Contract(unittest.TestCase):
    def setUp(self) -> None:
        ai.forget()
        for k in ai.STATS:
            ai.STATS[k] = 0

    def test_the_agreed_interface(self) -> None:
        self.assertEqual(ai.LEVELS, ("easy", "normal", "hard"))
        params = inspect.signature(ai.step).parameters
        self.assertEqual(list(params), ["engine", "seat", "level", "budget_ms", "rng"])
        self.assertEqual(params["level"].default, "normal")
        self.assertEqual(params["budget_ms"].default, 700)
        self.assertIsNone(params["rng"].default)

    def test_loads_without_the_server(self) -> None:
        code = (
            "import sys; import engine.ai; "
            "bad = [m for m in sys.modules if m.split('.')[0] in ('server', 'fastapi', 'uvicorn', 'pydantic', 'requests')]; "
            "assert not bad, bad"
        )
        subprocess.run([sys.executable, "-c", code], cwd=ROOT, check=True)

    def test_one_step_is_one_beat(self) -> None:
        eng = new_game("HUNTER", "MAGE", 11)
        seen = {"seq": eng.state.cp_seq}

        def one_beat(_seat: str) -> None:
            st = eng.state
            self.assertGreater(st.cp_seq, seen["seq"], "a step that changed nothing")
            self.assertEqual(st.checkpoints[-1]["prev"], seen["seq"], "a step closed more than one beat")
            self.assertFalse(st.pending_events)
            seen["seq"] = st.cp_seq

        play_out(eng, {"p1": "normal", "p2": "hard"}, on_step=one_beat)
        self.assertEqual(eng.state.phase, "GAME_OVER")

    def test_false_when_there_is_nothing_to_decide(self) -> None:
        eng = new_game("PRIEST", "ROGUE", 5)
        rng = random.Random(1)
        self.assertTrue(ai.step(eng, "p1", "normal", NO_LIMIT, rng))  # its mulligan
        self.assertFalse(ai.step(eng, "p1", "normal", NO_LIMIT, rng))  # waiting for the other seat's
        self.assertTrue(ai.step(eng, "p2", "normal", NO_LIMIT, rng))
        self.assertEqual(eng.state.phase, "PLAY")
        active = eng.state.active_seat
        waiting = other(active)
        before = (eng.state.cp_seq, eng.serialize_for_seat("p1"), eng.serialize_for_seat("p2"))
        for level in ai.LEVELS:
            self.assertFalse(ai.step(eng, waiting, level, NO_LIMIT, rng))
        self.assertEqual(before, (eng.state.cp_seq, eng.serialize_for_seat("p1"), eng.serialize_for_seat("p2")))
        eng.concede(active)
        self.assertFalse(ai.step(eng, "p1", "normal", NO_LIMIT, rng))
        self.assertFalse(ai.step(eng, "p2", "normal", NO_LIMIT, rng))

    def test_waiting_for_a_deck_is_not_its_move(self) -> None:
        eng = GameEngine.create_game("P1", "MAGE", STARTER_DECKS["MAGE"]["cards"], "MAGE", rng_seed=1)
        self.assertEqual(eng.state.phase, "WAITING_FOR_P2_DECK")
        self.assertFalse(ai.step(eng, "p2"))
        self.assertFalse(ai.step(eng, "p1"))

    def test_an_unknown_level_plays_as_normal(self) -> None:
        eng = new_game(seed=2)
        self.assertTrue(ai.step(eng, "p1", "impossible", NO_LIMIT, random.Random(1)))

    def test_never_raises_when_its_own_thinking_fails(self) -> None:
        eng = midgame(4, 5, "DRUID", "PALADIN")
        seat = eng.state.active_seat
        real = ai._plan
        ai._plan = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("broken"))
        try:
            self.assertTrue(ai.step(eng, seat, "normal", NO_LIMIT, random.Random(1)))
        finally:
            ai._plan = real
        self.assertEqual(eng.state.active_seat, other(seat), "the fallback is to end the turn")
        self.assertEqual(ai.STATS["fallbacks"], 1)

    def test_a_refused_plan_is_thought_over(self) -> None:
        eng = midgame(6, 6, "WARLOCK", "SHAMAN")
        seat = eng.state.active_seat
        real = ai._plan
        calls = {"n": 0}

        def stale(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                return [(("attack", "e_does_not_exist", f"hero_{other(seat)}"), ())], True
            return real(*a, **k)

        ai._plan = stale
        try:
            self.assertTrue(ai.step(eng, seat, "normal", NO_LIMIT, random.Random(1)))
        finally:
            ai._plan = real
        self.assertEqual(calls["n"], 2)
        self.assertEqual(ai.STATS["refused"], 1)
        self.assertEqual(ai.STATS["fallbacks"], 0)

    def test_a_turn_cannot_go_on_for_ever(self) -> None:
        eng = midgame(8, 9, "HUNTER", "WARLOCK")
        seat = eng.state.active_seat
        cap = ai.MAX_DECISIONS_PER_TURN
        ai.MAX_DECISIONS_PER_TURN = 1
        try:
            steps = 0
            while ai.step(eng, seat, "normal", NO_LIMIT, random.Random(1)):
                steps += 1
                self.assertLessEqual(steps, 2)
        finally:
            ai.MAX_DECISIONS_PER_TURN = cap
        self.assertNotEqual(eng.state.active_seat, seat)

    def test_a_small_budget_still_gives_a_legal_move(self) -> None:
        eng = midgame(10, 10, "MAGE", "HUNTER")
        seat = eng.state.active_seat
        for level in ai.LEVELS:
            e = copy.deepcopy(eng)
            ai.forget()
            t = time.perf_counter()
            self.assertTrue(ai.step(e, seat, level, 1, random.Random(1)))
            self.assertLess(time.perf_counter() - t, 0.5)
        self.assertEqual(ai.STATS["fallbacks"], 0)


class FullGames(unittest.TestCase):
    def setUp(self) -> None:
        ai.forget()
        for k in ai.STATS:
            ai.STATS[k] = 0

    def test_every_deck_against_every_deck_at_every_level(self) -> None:
        """81 pairings, both seats, the levels going round: no error, no fallback, every game ends."""
        mixes = [("normal", "hard"), ("hard", "easy"), ("easy", "normal"), ("normal", "normal"), ("hard", "hard"), ("easy", "easy")]
        games = 0
        for i, c1 in enumerate(CLASSES):
            for j, c2 in enumerate(CLASSES):
                a, b = mixes[(i * len(CLASSES) + j) % len(mixes)]
                eng = new_game(c1, c2, seed=100 + i * 9 + j)
                play_out(eng, {"p1": a, "p2": b}, seed=i * 9 + j)
                self.assertEqual(eng.state.phase, "GAME_OVER", f"{c1} ({a}) v {c2} ({b}) did not end")
                self.assertIn(eng.state.winner, ("p1", "p2", "draw"))
                games += 1
        self.assertEqual(games, 81)
        self.assertEqual(ai.STATS["errors"], 0)
        self.assertEqual(ai.STATS["fallbacks"], 0)

    def test_the_same_seed_plays_the_same_game(self) -> None:
        def record(seed: int) -> list:
            ai.forget()
            eng = new_game("SHAMAN", "DRUID", 21)
            play_out(eng, {"p1": "hard", "p2": "normal"}, seed=seed)
            return [(c["seq"], [e["t"] for e in c["events"]]) for c in eng.state.checkpoints] + [eng.state.winner, eng.state.turn_number]

        self.assertEqual(record(3), record(3))

    def test_normal_beats_the_practice_bot(self) -> None:
        """Twenty games, decks and seats going round. In the arena it wins about nine in ten."""
        wins = 0
        for g in range(20):
            c1, c2 = CLASSES[g % len(CLASSES)], CLASSES[(g * 4 + 3) % len(CLASSES)]
            eng = new_game(c1, c2, seed=500 + g // 2)
            mine = "p1" if g % 2 == 0 else "p2"
            rng = random.Random(g)

            def act(seat: str) -> None:
                if seat == mine:
                    while ai.step(eng, seat, "normal", NO_LIMIT, rng):
                        pass
                elif eng.state.phase == "MULLIGAN":
                    run_bot_mulligan(eng, seat)
                else:
                    run_bot_turn(eng, seat)

            act("p1")
            act("p2")
            for _ in range(160):
                if eng.state.phase != "PLAY":
                    break
                act(eng.state.active_seat)
            self.assertEqual(eng.state.phase, "GAME_OVER")
            wins += eng.state.winner == mine
        self.assertGreaterEqual(wins, 14)

    def test_normal_thinks_quickly(self) -> None:
        eng = new_game("WARLOCK", "PALADIN", 9)
        spent = []

        def timed_out(eng_: GameEngine) -> None:
            rng = random.Random(2)
            for seat in ("p1", "p2"):
                while ai.step(eng_, seat, "normal", NO_LIMIT, rng):
                    pass
            for _ in range(160):
                if eng_.state.phase != "PLAY":
                    return
                seat = eng_.state.active_seat
                while True:
                    t = time.perf_counter()
                    acted = ai.step(eng_, seat, "normal", NO_LIMIT, rng)
                    if not acted:
                        break
                    spent.append(time.perf_counter() - t)

        timed_out(eng)
        self.assertEqual(eng.state.phase, "GAME_OVER")
        # generous: the machine running the tests may be busy; in the arena it is about 5 ms
        self.assertLess(sum(spent) / len(spent), 0.15)


class Judgement(unittest.TestCase):
    def setUp(self) -> None:
        ai.forget()

    def finish_turn(self, eng: GameEngine, seat: str, level: str) -> None:
        rng = random.Random(1)
        steps = 0
        while ai.step(eng, seat, level, NO_LIMIT, rng):
            steps += 1
            self.assertLess(steps, 30)

    def test_takes_the_win_on_the_board(self) -> None:
        """Two pieces can finish the enemy hero together; a tempting trade must not distract."""
        plain = plain_minions()
        small = next(c for c in plain if c.attack == 3)
        big = max(plain, key=lambda c: (c.attack or 0) + (c.health or 0))
        for level in ("normal", "hard"):
            ai.forget()
            eng, seat = cleared()
            foe = other(seat)
            put(eng, seat, small)
            put(eng, seat, small)
            put(eng, foe, big)  # worth killing, but not now
            eng.state.players[foe].hero.hp = 6
            eng.state.players[foe].hero.armor = 0
            self.finish_turn(eng, seat, level)
            self.assertEqual(eng.state.phase, "GAME_OVER", level)
            self.assertEqual(eng.state.winner, seat, level)

    def test_clears_the_guard_first_when_that_wins(self) -> None:
        """The win needs the right order: one piece removes the guard, the others go for the hero."""
        plain = plain_minions()
        small = next(c for c in plain if c.attack == 3)
        guard = guard_minion()
        breaker = next(c for c in plain if (c.attack or 0) >= (guard.health or 0))
        for level in ("normal", "hard"):
            ai.forget()
            eng, seat = cleared()
            foe = other(seat)
            put(eng, seat, small)
            put(eng, seat, breaker)
            put(eng, seat, small)
            put(eng, foe, guard)
            eng.state.players[foe].hero.hp = 6
            eng.state.players[foe].hero.armor = 0
            self.finish_turn(eng, seat, level)
            self.assertEqual(eng.state.winner, seat, level)

    def test_does_not_throw_the_game_away(self) -> None:
        """With nothing to gain it still ends the turn rather than doing harm to itself."""
        for level in ai.LEVELS:
            ai.forget()
            eng, seat = cleared()
            hp = eng.state.players[seat].hero.hp
            self.finish_turn(eng, seat, level)
            self.assertEqual(eng.state.active_seat, other(seat))
            self.assertEqual(eng.state.players[seat].hero.hp, hp)


class FairPlay(unittest.TestCase):
    """What the AI cannot see must not change what it does."""

    def setUp(self) -> None:
        ai.forget()

    def reshuffled(self, eng: GameEngine, seat: str, seed: int) -> GameEngine:
        """The same position as far as `seat` can tell: everything hidden from it is different."""
        twin = copy.deepcopy(eng)
        rng = random.Random(seed)
        me = twin.state.players[seat]
        opp = twin.state.players[other(seat)]
        rng.shuffle(me.deck)  # the order of its own deck
        pool = opp.hand + opp.deck  # which of the opponent's unseen cards are in hand
        rng.shuffle(pool)
        opp.hand, opp.deck = pool[: len(opp.hand)], pool[len(opp.hand):]
        # which secrets the opponent has in play (it sees only that there are some)
        secrets = sorted((c for c in CARDS.values() if "SECRET" in c.mechanics), key=lambda c: c.id)
        opp.secrets = [
            SecretInstance(uid=s.uid, card_id=pick.id, card_class=s.card_class, name=pick.name)
            for s, pick in zip(opp.secrets, rng.sample(secrets, len(opp.secrets)))
        ]
        twin.rng = random.Random(seed + 99)  # what the real dice will roll
        twin.state.log = []
        return twin

    def test_hidden_cards_do_not_change_the_move(self) -> None:
        checked = with_secrets = 0
        secrets = sorted((c for c in CARDS.values() if "SECRET" in c.mechanics), key=lambda c: c.id)
        for n, (c1, c2) in enumerate([("MAGE", "HUNTER"), ("PALADIN", "WARLOCK"), ("HUNTER", "MAGE"), ("ROGUE", "PRIEST"),
                                      ("DRUID", "SHAMAN"), ("WARRIOR", "PALADIN"), ("MAGE", "MAGE"), ("SHAMAN", "HUNTER")]):
            for turns in (3, 6, 9, 12):
                eng = midgame(40 + n, turns, c1, c2)
                if eng.state.phase != "PLAY":
                    continue
                seat = eng.state.active_seat
                if turns % 6 == 0:
                    # the opponent holds secrets here: the AI may count them, not know them
                    foe = eng.state.players[other(seat)]
                    for i, card in enumerate(secrets[n: n + 2]):
                        foe.secrets.append(SecretInstance(uid=f"sec_t{i}", card_id=card.id, card_class=foe.hero.card_class, name=card.name))
                with_secrets += bool(eng.state.players[other(seat)].secrets)
                for level in ("normal", "hard"):
                    ai.forget()
                    expected = ai.decide(eng, seat, level, NO_LIMIT, random.Random(5))
                    for k in range(3):
                        twin = self.reshuffled(eng, seat, 1000 * n + 10 * turns + k)
                        ai.forget()
                        got = ai.decide(twin, seat, level, NO_LIMIT, random.Random(5))
                        self.assertEqual(expected, got, f"{c1} v {c2} after {turns} turns, {level}")
                    checked += 1
        self.assertGreater(checked, 40)
        self.assertGreater(with_secrets, 0, "no position had an enemy secret in it: the check is too weak")

    def test_the_opening_hand_is_chosen_without_peeking(self) -> None:
        eng = new_game("MAGE", "ROGUE", 31)
        for seat in ("p1", "p2"):
            expected = ai.decide(eng, seat, "normal", NO_LIMIT, random.Random(5))
            twin = self.reshuffled(eng, seat, 77)
            self.assertEqual(expected, ai.decide(twin, seat, "normal", NO_LIMIT, random.Random(5)))

    def test_thinking_leaves_the_game_alone(self) -> None:
        eng = midgame(12, 8, "WARLOCK", "DRUID")
        seat = eng.state.active_seat

        def picture(e: GameEngine) -> tuple:
            st = e.state
            return (
                e.serialize_for_seat("p1"), e.serialize_for_seat("p2"), st.seq, st.cp_seq, len(st.checkpoints), len(st.log), st.next_uid,
                [[c.uid for c in st.players[s].deck] for s in ("p1", "p2")], e.rng.getstate(),
            )

        before = picture(eng)
        for level in ai.LEVELS:
            ai.forget()
            self.assertIsNotNone(ai.decide(eng, seat, level, NO_LIMIT, random.Random(1)))
        self.assertEqual(before, picture(eng))

    def test_imagined_games_hold_none_of_the_hidden_cards_in_place(self) -> None:
        """The copy it thinks on: no enemy secrets, and the real game's dice are not in it."""
        eng = midgame(47, 9, "MAGE", "HUNTER")
        seat = eng.state.active_seat
        opp = eng.state.players[other(seat)]
        opp.secrets.append(SecretInstance(uid="sec_x", card_id=next(c.id for c in CARDS.values() if "SECRET" in c.mechanics), card_class=opp.hero.card_class, name="?"))
        sim = ai._imagine(eng, seat, random.Random(1))
        self.assertEqual(sim.state.players[other(seat)].secrets, [])
        self.assertIsNot(sim.rng, eng.rng)
        self.assertEqual(sim.state.checkpoints, [])
        self.assertEqual(sim.state.log, [])
        self.assertEqual(len(sim.state.players[other(seat)].hand), len(opp.hand))
        self.assertEqual(sorted(c.uid for c in sim.state.players[seat].hand), sorted(c.uid for c in eng.state.players[seat].hand))


if __name__ == "__main__":
    unittest.main()
