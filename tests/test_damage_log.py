"""Damage from effects can be read back in the log with its amount; an attack is logged once, as the attack."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("GAME_NO_PERSIST", "1")

from tests.test_agent import duel, plain_minions  # noqa: E402


class TestDamageLog(unittest.TestCase):
    def test_an_effect_hit_is_logged_with_its_amount(self) -> None:
        eng = duel()
        target = eng.summon_minion("p2", plain_minions()[0])
        eng.deal_damage(target.uid, 1, source_seat="p1", source_name="Some Spell")
        eng.deal_damage("hero_p2", 3, source_seat="p1", source_name="Some Spell")
        hero = eng.state.players["p2"].hero.name
        lines = [e["text"] for e in eng.state.log[-2:]]
        self.assertEqual(lines, [f"Some Spell hit {target.name} for 1.", f"Some Spell hit {hero} for 3."])

    def test_an_attack_is_logged_once(self) -> None:
        eng = duel()
        if eng.state.active_seat != "p1":
            eng.end_turn("p2")
        attacker = eng.summon_minion("p1", plain_minions()[0])
        attacker.summoned_this_turn = False
        before = len(eng.state.log)
        eng.attack("p1", attacker.uid, "hero_p2")
        new = [e["text"] for e in eng.state.log[before:]]
        self.assertEqual(len(new), 1, new)
        self.assertIn("attacked", new[0])

    def test_unnamed_damage_adds_no_line(self) -> None:
        eng = duel()
        before = len(eng.state.log)
        eng.deal_damage("hero_p2", 2)
        self.assertEqual(len(eng.state.log), before)


if __name__ == "__main__":
    unittest.main()
