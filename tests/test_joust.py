"""Jousts are shown to both players, and the shared Joust rule decides them."""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("GAME_NO_PERSIST", "1")

from engine.catalog import COLLECTIBLE_CARDS, clean_text, get_card  # noqa: E402
from engine.models import CardInstance  # noqa: E402
from tests.test_agent import duel  # noqa: E402

VANILLA = sorted(c.id for c in COLLECTIBLE_CARDS.values() if c.type == "MINION" and not c.text)
HIGH = next(i for i in VANILLA if get_card(i).cost >= 5)
LOW = next(i for i in VANILLA if get_card(i).cost == 1)
SPELL = next(c.id for c in COLLECTIBLE_CARDS.values() if c.type == "SPELL")
TUSKARR_JOUSTER = "AT_104"
KINGS_ELEKK = "AT_058"


def rig(eng, seat: str, card_id: str, n: int = 10) -> None:
    eng.state.players[seat].deck = [CardInstance(uid=eng._new_uid("c"), card_id=card_id) for _ in range(n)]


def play(card_id: str, mine: str, theirs: str):
    """Play `card_id` for the active seat with its deck all `mine` and the other all `theirs`."""
    eng = duel()
    seat = eng.state.active_seat
    other = eng.other_seat(seat)
    p = eng.state.players[seat]
    p.mana = p.max_mana = 10
    rig(eng, seat, mine)
    rig(eng, other, theirs)
    p.hand = [CardInstance(uid=eng._new_uid("c"), card_id=card_id)]
    since = eng.state.cp_seq
    eng.play_card(seat, 0)
    return eng, seat, other, since


def jousts(eng, viewer: str, since: int) -> list[dict]:
    return [e for b in eng.beats_for_seat(viewer, since) for e in b["events"] if e["t"] == "joust"]


class TestJoust(unittest.TestCase):
    def test_both_players_see_both_cards_and_the_result(self) -> None:
        eng, seat, other, since = play(TUSKARR_JOUSTER, HIGH, LOW)
        for viewer in (seat, other):
            (ev,) = jousts(eng, viewer, since)
            self.assertEqual(ev["seat"], seat)
            self.assertEqual(ev["mine"]["id"], HIGH)
            self.assertEqual(ev["theirs"]["id"], LOW)
            self.assertTrue(ev["won"])

    def test_the_cheaper_card_loses(self) -> None:
        eng, seat, _, since = play(TUSKARR_JOUSTER, LOW, HIGH)
        (ev,) = jousts(eng, seat, since)
        self.assertFalse(ev["won"])

    def test_no_minion_in_your_deck_loses(self) -> None:
        eng, seat, _, since = play(TUSKARR_JOUSTER, SPELL, LOW)
        (ev,) = jousts(eng, seat, since)
        self.assertIsNone(ev["mine"])
        self.assertFalse(ev["won"])

    def test_kings_elekk_draws_the_card_it_won_with(self) -> None:
        eng, seat, _, since = play(KINGS_ELEKK, HIGH, LOW)
        (ev,) = jousts(eng, seat, since)
        self.assertTrue(ev["won"])
        p = eng.state.players[seat]
        self.assertEqual([ci.card_id for ci in p.hand], [HIGH])
        self.assertEqual(len(p.deck), 9)


class TestCardText(unittest.TestCase):
    def test_unfilled_placeholders_are_dropped(self) -> None:
        self.assertEqual(clean_text("Battlecry: Summon a{1} {0} Jade Golem."), "Battlecry: Summon a Jade Golem.")
        self.assertEqual(clean_text("Summon two {0} Silver Hand Recruits."), "Summon two Silver Hand Recruits.")
        self.assertEqual(clean_text("Deal 2 damage."), "Deal 2 damage.")
        self.assertFalse([c.id for c in COLLECTIBLE_CARDS.values() if "{" in c.text])


class TestWeaponView(unittest.TestCase):
    def test_an_equipped_weapon_shows_its_printed_cost(self) -> None:
        eng = duel()
        seat = eng.state.active_seat
        weapon = next(c for c in COLLECTIBLE_CARDS.values() if c.type == "WEAPON" and c.cost >= 2 and not c.text)
        p = eng.state.players[seat]
        p.mana = p.max_mana = 10
        p.hand = [CardInstance(uid=eng._new_uid("c"), card_id=weapon.id)]
        eng.play_card(seat, 0)
        w = eng.serialize_for_seat(seat)["me"]["weapon"]
        self.assertEqual((w["cost"], w["rarity"], w["card_class"]), (weapon.cost, weapon.rarity, weapon.card_class))


if __name__ == "__main__":
    unittest.main()
