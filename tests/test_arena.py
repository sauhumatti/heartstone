from __future__ import annotations

import asyncio
import random
import unittest

from engine.arena import (
    ARENA_DECK_SIZE,
    GUARANTEED_RARE_PICKS,
    card_allowed_in_pool,
    draft_bot_deck,
    offer_heroes,
    offer_pick,
)
from engine.bot import run_bot_mulligan, run_bot_turn
from engine.catalog import COLLECTIBLE_BY_NAME, COLLECTIBLE_CARDS, validate_deck
from engine.game import GameEngine
from engine.local import LocalHost
from server.manager import GameManager


class TestArenaMode(unittest.TestCase):
    def test_validate_deck_allows_arena_duplicates(self) -> None:
        fireball = COLLECTIBLE_BY_NAME["Fireball"].id
        dr_boom = COLLECTIBLE_BY_NAME["Dr. Boom"].id
        deck = [fireball] * 25 + [dr_boom] * 5
        ok_std, _ = validate_deck("MAGE", deck)
        self.assertFalse(ok_std)
        ok_arena, msg = validate_deck("MAGE", deck, allow_duplicates=True)
        self.assertTrue(ok_arena, msg)

        # Wrong class cards are still rejected in Arena
        wrong = [COLLECTIBLE_BY_NAME["Execute"].id] + [fireball] * 29
        ok_wrong, _ = validate_deck("MAGE", wrong, allow_duplicates=True)
        self.assertFalse(ok_wrong)

    def test_arena_draft_rules_and_pools(self) -> None:
        rng = random.Random(42)
        heroes = offer_heroes(rng)
        self.assertEqual(len(heroes), 3)
        self.assertEqual(len(set(heroes)), 3)

        for pool in ("wild", "classic", "gvg", "tgt", "old_gods", "gadgetzan", "ungoro"):
            for pick in (1, 5, 10, 20, 30):
                opts = offer_pick("MAGE", pick, pool=pool, rng=rng)
                self.assertEqual(len(opts), 3)
                self.assertEqual(len(set(opts)), 3)
                cards = [COLLECTIBLE_CARDS[cid] for cid in opts]
                for c in cards:
                    self.assertTrue(c.allowed_for_class("MAGE"))
                    self.assertTrue(card_allowed_in_pool(c, pool))
                    self.assertFalse(c.has_mechanic("QUEST"))
                    self.assertFalse(c.has_mechanic("TRIAL"))
                if pick in GUARANTEED_RARE_PICKS:
                    for c in cards:
                        self.assertIn(c.rarity, ("RARE", "EPIC", "LEGENDARY"))

    def test_draft_bot_deck_plays_full_match_locally_and_on_server(self) -> None:
        rng = random.Random(77)
        c1, d1 = draft_bot_deck("MAGE", pool="wild", wins=5, rng=rng)
        c2, d2 = draft_bot_deck("PALADIN", pool="wild", wins=5, rng=rng)
        self.assertEqual(len(d1), ARENA_DECK_SIZE)
        self.assertEqual(len(d2), ARENA_DECK_SIZE)

        # 1. LocalHost (offline Pyodide engine) accepts Arena decks with >2 duplicates
        fb = COLLECTIBLE_BY_NAME["Fireball"].id
        dup_mage = [fb] * 4 + d1[4:]
        host = LocalHost()
        res = host.create_game(
            p1_name="ArenaTester",
            p1_class=c1,
            p1_cards=dup_mage,
            p1_deck_name="Arena Mage (5-1)",
            p2_class=c2,
            p2_cards=d2,
            p2_deck_name="Arena Paladin (5-1)",
            level="easy",
            seed=99,
            arena=True,
        )
        self.assertEqual(res["state"]["deck_era"], "arena")
        eng = host.matches[res["game_id"]].engine
        run_bot_mulligan(eng, "p1")
        run_bot_mulligan(eng, "p2")
        for _ in range(100):
            if eng.state.phase != "PLAY":
                break
            run_bot_turn(eng, eng.state.active_seat)
        self.assertEqual(eng.state.phase, "GAME_OVER")

        # 2. Server GameManager accepts Arena decks for both P1 and P2
        mgr = GameManager(persist_dir=None)
        mg = asyncio.run(
            mgr.create_game(
                p1_name="ArenaTester",
                p1_class=c1,
                p1_cards=dup_mage,
                p1_deck_name="Arena Mage (5-1)",
                p2_mode="bot",
                p2_class=c2,
                p2_cards=d2,
                p2_deck_name="Arena Paladin (5-1)",
                p2_name="Arena Paladin",
                arena=True,
            )
        )
        self.assertEqual(mg.engine.state.deck_era, "arena")
        self.assertEqual(mg.engine.state.players["p1"].deck_name, "Arena Mage (5-1)")
        self.assertEqual(mg.engine.state.players["p2"].deck_name, "Arena Paladin (5-1)")


if __name__ == "__main__":
    unittest.main()
