"""Immune granted for "this turn" ends when the turn ends, for minions as for heroes."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("GAME_NO_PERSIST", "1")

from tests.test_agent import duel, plain_minions  # noqa: E402


class TestImmuneThisTurn(unittest.TestCase):
    def test_minion_immune_ends_with_the_turn(self) -> None:
        eng = duel()
        seat = eng.state.active_seat
        other = eng.other_seat(seat)
        mine = eng.summon_minion(seat, plain_minions()[0])
        mine.immune_this_turn = True
        self.assertTrue(eng.serialize_for_seat(seat)["me"]["board"][0]["immune"])

        eng.end_turn(seat)

        self.assertFalse(mine.immune_this_turn)
        theirs = eng.serialize_for_seat(other)["opponent"]["board"]
        self.assertFalse(theirs[0]["immune"])

    def test_an_immune_minion_can_be_hit_on_the_opponents_turn(self) -> None:
        eng = duel()
        seat = eng.state.active_seat
        other = eng.other_seat(seat)
        mine = eng.summon_minion(seat, plain_minions()[0])
        mine.immune_this_turn = True
        eng.end_turn(seat)
        hp = mine.health
        eng.deal_damage(mine.uid, 1, source_seat=other, source_name="Some Spell")
        self.assertEqual(mine.health, hp - 1)


if __name__ == "__main__":
    unittest.main()
