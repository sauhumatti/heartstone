from __future__ import annotations

import unittest

from data.starter_decks import STARTER_DECKS
from engine.bot import run_bot_mulligan, run_bot_turn
from engine.game import GameEngine

CLASSES = sorted(STARTER_DECKS.keys())


def new_game(c1: str = "MAGE", c2: str = "WARRIOR", seed: int = 7) -> GameEngine:
    return GameEngine.create_game(
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


def play_out(eng: GameEngine, max_turns: int = 120) -> None:
    run_bot_mulligan(eng, "p1")
    run_bot_mulligan(eng, "p2")
    for _ in range(max_turns):
        if eng.state.phase != "PLAY":
            break
        run_bot_turn(eng, eng.state.active_seat)


def shape(view: dict) -> dict:
    """The part of a view the events must be able to explain on their own."""
    me, opp = view["me"], view["opponent"]
    return {
        "board": {
            me["seat"]: [m["uid"] for m in me["board"]],
            opp["seat"]: [m["uid"] for m in opp["board"]],
        },
        "hand": {me["seat"]: me["hand_count"], opp["seat"]: opp["hand_count"]},
        "weapon": {me["seat"]: bool(me["weapon"]), opp["seat"]: bool(opp["weapon"])},
        "secrets": {me["seat"]: len(me["secrets"]), opp["seat"]: len(opp["secrets"])},
    }


def apply_event(s: dict, ev: dict) -> None:
    """Reference reducer: the same structural rules the web client uses."""
    t = ev["t"]
    seat = ev.get("seat")
    boards = s["board"]

    def drop(uid: str) -> None:
        for b in boards.values():
            if uid in b:
                b.remove(uid)

    if t == "summon":
        boards[seat].insert(ev["pos"], ev["minion"]["uid"])
    elif t == "transform":
        drop(ev["target"])
        boards[seat].insert(ev["pos"], ev["minion"]["uid"])
    elif t in ("death", "remove"):
        drop(ev["target"])
    elif t == "steal":
        drop(ev["target"])
        boards[seat].append(ev["target"])
    elif t == "bounce":
        drop(ev["target"])
        s["hand"][seat] += 1
    elif t in ("draw", "card_added"):
        s["hand"][seat] += 1
    elif t in ("play", "discard"):
        s["hand"][seat] -= 1
    elif t == "weapon_equip":
        s["weapon"][seat] = True
    elif t == "weapon_destroy":
        s["weapon"][seat] = False
    elif t == "secret_add":
        s["secrets"][seat] += 1
    elif t in ("secret_reveal", "secret_destroy"):
        s["secrets"][seat] -= 1


class TestEventJournal(unittest.TestCase):
    def test_new_game_has_an_opening_beat(self) -> None:
        eng = new_game()
        beats = eng.beats_for_seat("p1", 0)
        self.assertIsNotNone(beats)
        self.assertEqual(len(beats), 1)
        self.assertEqual(beats[0]["events"][0]["t"], "game_start")
        self.assertEqual(beats[0]["state"]["seq"], eng.state.cp_seq)

    def test_beats_are_contiguous_and_ordered(self) -> None:
        eng = new_game(seed=3)
        play_out(eng, max_turns=12)
        beats = eng.beats_for_seat("p1", 0)
        self.assertIsNotNone(beats)
        prev, last_seq = 0, 0
        for b in beats:
            self.assertEqual(b["prev"], prev)
            for ev in b["events"]:
                self.assertGreater(ev["seq"], last_seq)
                last_seq = ev["seq"]
            self.assertEqual(b["seq"], last_seq)
            self.assertEqual(b["state"]["seq"], b["seq"])
            prev = b["seq"]
        self.assertEqual(prev, eng.state.cp_seq)
        self.assertEqual(eng.beats_for_seat("p1", eng.state.cp_seq), [])

    def test_unknown_or_stale_position_asks_for_resync(self) -> None:
        eng = new_game(seed=5)
        play_out(eng)
        self.assertIsNone(eng.beats_for_seat("p1", None))
        self.assertIsNone(eng.beats_for_seat("p1", 0))  # trimmed long ago
        self.assertIsNone(eng.beats_for_seat("p1", eng.state.cp_seq - 1))  # mid-beat

    def test_failed_action_leaves_no_beat(self) -> None:
        eng = new_game(seed=11)
        run_bot_mulligan(eng, "p1")
        run_bot_mulligan(eng, "p2")
        before = eng.state.cp_seq
        waiting = eng.other_seat(eng.state.active_seat)
        with self.assertRaises(ValueError):
            eng.end_turn(waiting)
        self.assertEqual(eng.state.cp_seq, before)
        self.assertEqual(eng.state.pending_events, [])

    def test_events_explain_every_structural_change(self) -> None:
        """Replaying a beat's events on the previous snapshot must give the
        board order, hand sizes, weapons and secrets of the next snapshot."""
        games = 0
        for i, c1 in enumerate(CLASSES):
            for j, c2 in enumerate(CLASSES):
                eng = new_game(c1, c2, seed=100 + i * 9 + j)
                seen = 0
                prev_shape = None

                def drain() -> None:
                    nonlocal seen, prev_shape
                    for cp in eng.state.checkpoints:
                        if cp["seq"] <= seen:
                            continue
                        for seat in ("p1", "p2"):
                            beat_events = cp["events"]
                            want = shape(cp["views"][seat])
                            if prev_shape is not None:
                                got = {
                                    k: {s: (list(v) if isinstance(v, list) else v) for s, v in d.items()}
                                    for k, d in prev_shape.items()
                                }
                                for ev in beat_events:
                                    apply_event(got, ev)
                                self.assertEqual(
                                    got,
                                    want,
                                    f"{c1} vs {c2}, beat {cp['seq']}: "
                                    f"{[e['t'] for e in beat_events]}",
                                )
                        prev_shape = shape(cp["views"]["p1"])
                        seen = cp["seq"]

                drain()
                run_bot_mulligan(eng, "p1")
                drain()
                run_bot_mulligan(eng, "p2")
                drain()
                for _ in range(120):
                    if eng.state.phase != "PLAY":
                        break
                    run_bot_turn(eng, eng.state.active_seat)
                    drain()
                games += 1
        self.assertEqual(games, len(CLASSES) ** 2)

    def test_game_over_is_announced_exactly_once(self) -> None:
        eng = new_game(seed=21)
        play_out(eng)
        self.assertEqual(eng.state.phase, "GAME_OVER")
        eng.concede("p1")  # no-op after the end
        overs = [e for cp in eng.state.checkpoints for e in cp["events"] if e["t"] == "game_over"]
        self.assertEqual(len(overs), 1)
        self.assertEqual(overs[0]["winner"], eng.state.winner)


class TestEventFogOfWar(unittest.TestCase):
    def test_opponent_draws_and_secrets_stay_hidden(self) -> None:
        secret_seen = False
        for seed in range(40, 52):
            eng = new_game("MAGE", "HUNTER", seed=seed)
            play_out(eng, max_turns=40)
            for cp in eng.state.checkpoints:
                for viewer in ("p1", "p2"):
                    beat = next(
                        b for b in eng.beats_for_seat(viewer, cp["prev"]) if b["seq"] == cp["seq"]
                    )
                    for raw, ev in zip(cp["events"], beat["events"]):
                        mine = raw.get("seat") == viewer
                        if raw["t"] in ("draw", "card_added"):
                            self.assertEqual("card" in ev, mine)
                            self.assertEqual("uid" in ev, mine)
                        elif raw["t"] == "play" and raw["secret"]:
                            secret_seen = True
                            if mine:
                                self.assertEqual(ev["card"]["id"], raw["card"]["id"])
                            else:
                                self.assertIsNone(ev["card"])
                                self.assertNotIn("uid", ev)
                                self.assertEqual(ev["card_class"], raw["card_class"])
                        else:
                            self.assertEqual(ev, raw)
        self.assertTrue(secret_seen, "no secret was played in the sampled games")

    def test_redaction_does_not_alter_the_stored_journal(self) -> None:
        eng = new_game(seed=8)
        play_out(eng, max_turns=6)
        eng.beats_for_seat("p2", eng.state.checkpoints[0]["prev"])
        draws = [e for cp in eng.state.checkpoints for e in cp["events"] if e["t"] == "draw"]
        self.assertTrue(draws)
        self.assertTrue(all("card" in e and "uid" in e for e in draws))


if __name__ == "__main__":
    unittest.main()


class TestEveryCardIsExplained(unittest.TestCase):
    def test_each_collectible_card_emits_a_complete_beat(self) -> None:
        from engine.catalog import COLLECTIBLE_BY_NAME, COLLECTIBLE_CARDS
        from engine.effects import CHOOSE_ONE_OPTIONS
        from engine.models import CardInstance

        def by(name: str) -> str:
            return COLLECTIBLE_BY_NAME[name].id

        checked = 0
        for cid, card in sorted(COLLECTIBLE_CARDS.items()):
            options = (0, 1) if cid in CHOOSE_ONE_OPTIONS else (None,)
            for choose in options:
                eng = new_game("MAGE", "WARRIOR", seed=99)
                eng.submit_mulligan("p1", [])
                eng.submit_mulligan("p2", [])
                eng.state.active_seat = "p1"
                p1 = eng.state.players["p1"]
                p1.mana = p1.max_mana = 10
                p1.hero.armor = 5
                eng.equip_weapon("p1", by("Fiery War Axe"))
                eng.equip_weapon("p2", by("Arcanite Reaper"))
                f1 = eng.summon_minion("p1", by("River Crocolisk"))
                eng.summon_minion("p1", by("Blood Imp"))
                eng.summon_minion("p1", by("Bluegill Warrior"))
                f1.damage = 1
                e1 = eng.summon_minion("p2", by("Sen'jin Shieldmasta"))
                e1.damage = 1
                eng.summon_minion("p2", by("Core Hound"))
                eng.summon_minion("p2", by("Shieldbearer"))
                eng.summon_minion("p2", by("Murloc Raider"))
                p1.hand.append(CardInstance(uid=eng._new_uid("c"), card_id=cid, cost_mod=-20))
                eng.recompute_auras()
                eng.state.pending_events.clear()
                before = shape(eng.serialize_for_seat("p1"))
                mark = eng.state.cp_seq

                if choose is None:
                    rule = eng.get_target_rule(cid, None, False)
                else:
                    rule = CHOOSE_ONE_OPTIONS[cid][choose].target_rule
                targets = eng.get_valid_targets("p1", rule, is_spell_or_power=(card.type == "SPELL"))
                eng.play_card("p1", len(p1.hand) - 1, target_id=targets[0] if targets else None, choose=choose)
                if eng.state.pending_choice:
                    eng.resolve_pending_choice("p1", 0)

                for cp in eng.state.checkpoints:
                    if cp["seq"] <= mark:
                        continue
                    for ev in cp["events"]:
                        apply_event(before, ev)
                self.assertEqual(
                    before,
                    shape(eng.serialize_for_seat("p1")),
                    f"{card.name} ({cid}, choose={choose})",
                )
                checked += 1
        self.assertGreaterEqual(checked, len(COLLECTIBLE_CARDS))
