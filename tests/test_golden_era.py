from __future__ import annotations

import unittest

from data.starter_decks import THEME_DECKS
from engine.bot import run_bot_mulligan, run_bot_turn
from engine.catalog import COLLECTIBLE_BY_NAME, validate_deck
from engine.game import GameEngine
from engine.models import CardInstance


def _make_engine(p1_class: str = "WARLOCK", p2_class: str = "MAGE", seed: int = 42) -> GameEngine:
    d1 = next(d for d in THEME_DECKS if d["hero_class"] == p1_class)
    d2 = next(d for d in THEME_DECKS if d["hero_class"] == p2_class)
    eng = GameEngine.create_game(
        p1_name="P1",
        p1_class=p1_class,
        p1_deck=d1["cards"],
        p1_deck_name=d1["name"],
        p2_name="P2",
        p2_class=p2_class,
        p2_deck=d2["cards"],
        p2_deck_name=d2["name"],
        mode="bot_vs_human",
        rng_seed=seed,
    )
    eng.submit_mulligan("p1", [])
    eng.submit_mulligan("p2", [])
    if eng.state.active_seat != "p1":
        eng.end_turn("p2")
    eng.state.players["p1"].mana = 10
    eng.state.players["p1"].max_mana = 10
    return eng


def _give(eng: GameEngine, seat: str, name: str) -> int:
    cid = COLLECTIBLE_BY_NAME[name].id
    p = eng.state.players[seat]
    p.hand.append(CardInstance(uid=eng._new_uid("c"), card_id=cid))
    return len(p.hand) - 1


class TestGoldenEraDecksAndMechanics(unittest.TestCase):
    def test_all_13_theme_decks_are_valid(self) -> None:
        self.assertEqual(len(THEME_DECKS), 13)
        for d in THEME_DECKS:
            ok, msg = validate_deck(d["hero_class"], d["cards"])
            self.assertTrue(ok, f"{d['id']}: {msg}")
        renolock = next(d for d in THEME_DECKS if d["id"] == "golden_renolock")
        self.assertEqual(len(set(renolock["cards"])), 30)

    def test_reno_jackson_heals_only_without_duplicates(self) -> None:
        eng = _make_engine("WARLOCK", "MAGE")
        p1 = eng.state.players["p1"]
        # Force duplicate in deck
        p1.deck = [CardInstance("d1", "VAN_CS2_029"), CardInstance("d2", "VAN_CS2_029")]
        p1.hero.hp = 5
        idx = _give(eng, "p1", "Reno Jackson")
        eng.play_card("p1", idx)
        self.assertEqual(p1.hero.hp, 5)

        # Unique deck -> full heal
        p1.mana = 10
        p1.deck = [CardInstance("d3", "VAN_CS2_029"), CardInstance("d4", "VAN_CS2_024")]
        idx = _give(eng, "p1", "Reno Jackson")
        eng.play_card("p1", idx)
        self.assertEqual(p1.hero.hp, 30)

    def test_brann_doubles_battlecry(self) -> None:
        eng = _make_engine("WARLOCK", "MAGE")
        p1 = eng.state.players["p1"]
        p1.hero.hp = 10
        eng.summon_minion("p1", "LOE_077")  # Brann Bronzebeard
        idx = _give(eng, "p1", "Antique Healbot")
        eng.play_card("p1", idx)
        self.assertEqual(p1.hero.hp, 26)  # +8 twice!

    def test_dark_peddler_discovers_1_cost_card(self) -> None:
        eng = _make_engine("WARLOCK", "MAGE")
        p1 = eng.state.players["p1"]
        p1.hand.clear()
        idx = _give(eng, "p1", "Dark Peddler")
        eng.play_card("p1", idx)
        self.assertIsNotNone(eng.state.pending_choice)
        self.assertEqual(eng.state.pending_choice.choice_type, "DISCOVER")
        self.assertEqual(len(eng.state.pending_choice.options), 3)
        eng.resolve_pending_choice("p1", 0)
        self.assertIsNone(eng.state.pending_choice)
        self.assertEqual(len(p1.hand), 1)

    def test_jade_golems_and_fandral_jade_idol(self) -> None:
        eng = _make_engine("DRUID", "WARRIOR")
        p1 = eng.state.players["p1"]
        deck_before = len(p1.deck)
        eng.summon_minion("p1", "OG_044")  # Fandral Staghelm
        idx = _give(eng, "p1", "Jade Idol")
        eng.play_card("p1", idx, choose=0)
        # Fandral summons a 1/1 Jade Golem AND shuffles 3 Jade Idols!
        self.assertEqual(len(p1.deck), deck_before + 3)
        self.assertEqual(p1.jade_counter, 1)
        golems = [m for m in p1.board if m.name == "Jade Golem"]
        self.assertEqual(len(golems), 1)
        self.assertEqual((golems[0].attack, golems[0].health), (1, 1))

        idx2 = _give(eng, "p1", "Jade Blossom")
        eng.play_card("p1", idx2)
        self.assertEqual(p1.jade_counter, 2)
        golems = [m for m in p1.board if m.name == "Jade Golem"]
        self.assertEqual((golems[-1].attack, golems[-1].health), (2, 2))

    def test_justicar_trueheart_upgrades_hero_power(self) -> None:
        eng = _make_engine("WARRIOR", "MAGE")
        p1 = eng.state.players["p1"]
        idx = _give(eng, "p1", "Justicar Trueheart")
        eng.play_card("p1", idx)
        self.assertEqual(p1.hero.hero_power_id, "AT_132_WARRIOR")
        eng.use_hero_power("p1")
        self.assertEqual(p1.hero.armor, 4)

    def test_sir_finley_replaces_hero_power(self) -> None:
        eng = _make_engine("SHAMAN", "MAGE")
        p1 = eng.state.players["p1"]
        old_hp = p1.hero.hero_power_id
        idx = _give(eng, "p1", "Sir Finley Mrrgglton")
        eng.play_card("p1", idx)
        self.assertIsNotNone(eng.state.pending_choice)
        self.assertEqual(eng.state.pending_choice.choice_type, "DISCOVER_HERO_POWER")
        chosen_hp = eng.state.pending_choice.options[0].card_id
        self.assertNotEqual(chosen_hp, old_hp)
        eng.resolve_pending_choice("p1", 0)
        self.assertEqual(p1.hero.hero_power_id, chosen_hp)

    def test_anyfin_can_happen_revives_dead_murlocs(self) -> None:
        eng = _make_engine("PALADIN", "WARRIOR")
        m1 = eng.summon_minion("p1", "VAN_CS2_173")  # Bluegill Warrior
        m2 = eng.summon_minion("p1", "VAN_EX1_507")  # Murloc Warleader
        eng.destroy_minion(m1.uid)
        eng.destroy_minion(m2.uid)
        eng.resolve_deaths()
        self.assertEqual(len(eng.state.players["p1"].board), 0)

        idx = _give(eng, "p1", "Anyfin Can Happen")
        eng.play_card("p1", idx)
        names = sorted(m.name for m in eng.state.players["p1"].board)
        self.assertEqual(names, ["Bluegill Warrior", "Murloc Warleader"])

    def test_loatheb_taxes_enemy_spells(self) -> None:
        eng = _make_engine("WARLOCK", "MAGE")
        idx = _give(eng, "p1", "Loatheb")
        eng.play_card("p1", idx)
        eng.end_turn("p1")
        p2 = eng.state.players["p2"]
        fb_idx = _give(eng, "p2", "Fireball")
        self.assertEqual(eng.get_card_cost("p2", p2.hand[fb_idx]), 9)  # 4 + 5!

    def test_emperor_thaurissan_and_kelthuzad(self) -> None:
        eng = _make_engine("DRUID", "WARRIOR")
        p1 = eng.state.players["p1"]
        p1.hand.clear()
        ci = CardInstance(eng._new_uid("c"), COLLECTIBLE_BY_NAME["Swipe"].id)
        p1.hand.append(ci)
        eng.summon_minion("p1", "BRM_028")  # Emperor Thaurissan
        eng.summon_minion("p1", "FP1_013")  # Kel'Thuzad
        yeti = eng.summon_minion("p1", "VAN_CS2_182")
        eng.destroy_minion(yeti.uid)
        eng.resolve_deaths()
        eng.end_turn("p1")
        self.assertEqual(eng.get_card_cost("p1", ci), 3)  # Swipe 4 -> 3
        self.assertTrue(any(m.card_id == "VAN_CS2_182" for m in p1.board))

    def test_tunnel_trogg_and_overload_and_thing_from_below(self) -> None:
        eng = _make_engine("SHAMAN", "MAGE")
        p1 = eng.state.players["p1"]
        trogg = eng.summon_minion("p1", "LOE_018")
        idx = _give(eng, "p1", "Totem Golem")
        eng.play_card("p1", idx)
        self.assertEqual(trogg.attack, 2)  # 1 + 1 Overload
        tfb_idx = _give(eng, "p1", "Thing from Below")
        self.assertEqual(eng.get_card_cost("p1", p1.hand[tfb_idx]), 5)  # 1 Totem summoned!

    def test_deaths_bite_weapon_deathrattle_and_gang_up_and_entomb(self) -> None:
        eng = _make_engine("WARRIOR", "PRIEST")
        p1 = eng.state.players["p1"]
        opp_m = eng.summon_minion("p2", "VAN_CS2_182")  # 4/5 Yeti
        eng.equip_weapon("p1", "FP1_021")  # Death's Bite
        eng.destroy_weapon("p1")
        self.assertEqual(opp_m.health, 4)

        # Entomb removes enemy minion and shuffles it into caster's deck
        deck_n = len(p1.deck)
        idx = _give(eng, "p1", "Entomb")
        eng.play_card("p1", idx, target_id=opp_m.uid)
        self.assertEqual(len(eng.state.players["p2"].board), 0)
        self.assertEqual(len(p1.deck), deck_n + 1)

    def test_dragon_synergy_and_drakonid_operative(self) -> None:
        eng = _make_engine("PRIEST", "WARRIOR")
        p1 = eng.state.players["p1"]
        p1.hand.clear()
        _give(eng, "p1", "Ysera")  # Dragon in hand
        idx = _give(eng, "p1", "Drakonid Operative")
        eng.play_card("p1", idx)
        self.assertIsNotNone(eng.state.pending_choice)
        self.assertEqual(eng.state.pending_choice.choice_type, "DISCOVER")
        eng.resolve_pending_choice("p1", 0)
        self.assertIsNone(eng.state.pending_choice)

    def test_all_13_theme_decks_complete_bot_matches_cleanly(self) -> None:
        for i, d1 in enumerate(THEME_DECKS):
            d2 = THEME_DECKS[(i + 5) % len(THEME_DECKS)]
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
                rng_seed=200 + i,
            )
            run_bot_mulligan(eng, "p1")
            run_bot_mulligan(eng, "p2")
            for _ in range(90):
                if eng.state.phase != "PLAY":
                    break
                run_bot_turn(eng, eng.state.active_seat)
            self.assertIn(eng.state.phase, ("PLAY", "GAME_OVER"))


if __name__ == "__main__":
    unittest.main()
