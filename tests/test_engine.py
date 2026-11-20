from __future__ import annotations

import inspect
import re
import unittest

from data.starter_decks import STARTER_DECKS
from engine import effects, game
from engine.bot import run_bot_mulligan, run_bot_turn
from engine.catalog import CARDS, COLLECTIBLE_BY_NAME, COLLECTIBLE_CARDS, validate_deck
from engine.game import GameEngine, GameError
from engine.models import CardInstance


def make_test_engine(
    p1_class: str = "MAGE",
    p2_class: str = "WARRIOR",
    seed: int = 42,
    skip_mulligan: bool = True,
) -> GameEngine:
    eng = GameEngine.create_game(
        p1_name="Human",
        p1_class=p1_class,
        p1_deck=STARTER_DECKS[p1_class]["cards"],
        p1_deck_name=STARTER_DECKS[p1_class]["name"],
        p2_name="Antigravity",
        p2_class=p2_class,
        p2_deck=STARTER_DECKS[p2_class]["cards"],
        p2_deck_name=STARTER_DECKS[p2_class]["name"],
        rng_seed=seed,
    )
    if skip_mulligan:
        eng.submit_mulligan("p1", [])
        eng.submit_mulligan("p2", [])
    return eng


def cid_of(name: str) -> str:
    return COLLECTIBLE_BY_NAME[name].id


def give_hand(eng: GameEngine, seat: str, name: str) -> int:
    ci = CardInstance(uid=eng._new_uid("c"), card_id=cid_of(name))
    eng.state.players[seat].hand.append(ci)
    return len(eng.state.players[seat].hand) - 1


def set_turn(eng: GameEngine, seat: str, mana: int = 10) -> None:
    eng.state.active_seat = seat
    p = eng.state.players[seat]
    p.mana = mana
    p.max_mana = mana
    p.hero.hero_power_used = False
    p.hero.attacks_this_turn = 0
    for m in p.board:
        m.summoned_this_turn = False
        m.attacks_this_turn = 0
    eng.recompute_auras()


class TestCatalogAndCoverage(unittest.TestCase):
    def test_all_382_collectible_cards_handled(self) -> None:
        self.assertEqual(len(COLLECTIBLE_CARDS), 460)
        combined = inspect.getsource(effects) + "\n" + inspect.getsource(game)
        missing = [
            (cid, c.name)
            for cid, c in COLLECTIBLE_CARDS.items()
            if cid not in effects.PURE_KEYWORD_CARDS and cid not in combined
        ]
        self.assertEqual(missing, [])

    def test_all_referenced_ids_exist(self) -> None:
        for mod in (effects, game):
            src = inspect.getsource(mod)
            ids = set(re.findall(r'"((?:VAN_|EX1_|CS[12]_|NEW1_|DS1_|DREAM_|PRO_|Mekka|GAME_|hexfrog|tt_|FP1_|GVG_|BRM_|AT_|LOE_|OG_|KAR_|CFM_|PART_)[^"]+)"', src))
            for cid in ids:
                if cid == "GAME_OVER" or "{" in cid:
                    continue
                self.assertIn(cid, CARDS, f"Missing card {cid}")

    def test_starter_decks_valid(self) -> None:
        self.assertEqual(len(STARTER_DECKS), 9)
        for cls, d in STARTER_DECKS.items():
            ok, msg = validate_deck(cls, d["cards"])
            self.assertTrue(ok, msg)


class TestCoreRulesAndFairPlay(unittest.TestCase):
    def test_mulligan_coin_and_fair_play_fog_of_war(self) -> None:
        eng = make_test_engine(skip_mulligan=False, seed=7)
        self.assertEqual(eng.state.phase, "MULLIGAN")
        first = eng.state.first_seat
        second = eng.other_seat(first)
        self.assertEqual(len(eng.state.players[first].hand), 3)
        self.assertEqual(len(eng.state.players[second].hand), 4)

        eng.submit_mulligan("p1", [0])
        eng.submit_mulligan("p2", [1, 2])
        self.assertEqual(eng.state.phase, "PLAY")
        self.assertEqual(eng.state.active_seat, first)
        # First player drew 1 card on T1 -> 4 cards; second player received The Coin -> 5 cards
        self.assertEqual(len(eng.state.players[first].hand), 4)
        self.assertEqual(len(eng.state.players[second].hand), 5)
        self.assertTrue(any(c.card_id == "GAME_005" for c in eng.state.players[second].hand))

        # Check Fog of War on p2's serialized view
        p2_view = eng.serialize_for_seat("p2")
        self.assertNotIn("hand", p2_view["opponent"])
        self.assertNotIn("deck", p2_view["opponent"])
        self.assertEqual(p2_view["opponent"]["hand_count"], len(eng.state.players["p1"].hand))

        # Put secret on P1 and ensure P2 doesn't see its name or card_id
        set_turn(eng, "p1", mana=10)
        idx = give_hand(eng, "p1", "Ice Block")
        eng.play_card("p1", idx)
        p2_view = eng.serialize_for_seat("p2")
        self.assertEqual(len(p2_view["opponent"]["secrets"]), 1)
        sec_info = p2_view["opponent"]["secrets"][0]
        self.assertEqual(sec_info["card_class"], "MAGE")
        self.assertNotIn("card_id", sec_info)
        self.assertNotIn("name", sec_info)

    def test_overload_fatigue_and_hand_burn(self) -> None:
        eng = make_test_engine()
        set_turn(eng, "p1", mana=5)
        idx = give_hand(eng, "p1", "Feral Spirit")  # Overload 2
        eng.play_card("p1", idx)
        self.assertEqual(len(eng.state.players["p1"].board), 2)
        self.assertEqual(eng.state.players["p1"].pending_overload, 2)
        eng.end_turn("p1")
        eng.end_turn("p2")
        # Now P1 has max_mana 6, overloaded 2 -> 4 mana
        self.assertEqual(eng.state.players["p1"].overloaded, 2)
        self.assertEqual(eng.state.players["p1"].mana, 4)

        # Fatigue & hand limit
        eng.state.players["p1"].deck.clear()
        hp_before = eng.state.players["p1"].hero.hp
        eng.draw_card("p1")
        self.assertEqual(eng.state.players["p1"].hero.hp, hp_before - 1)
        eng.draw_card("p1")
        self.assertEqual(eng.state.players["p1"].hero.hp, hp_before - 3)

        # Hand limit 10
        while len(eng.state.players["p1"].hand) < 10:
            give_hand(eng, "p1", "Wisp")
        res = eng.add_card_to_hand("p1", cid_of("Fireball"))
        self.assertIsNone(res)
        self.assertEqual(len(eng.state.players["p1"].hand), 10)


class TestAurasCombatAndKeywords(unittest.TestCase):
    def test_stormwind_health_aura_and_crazed_alchemist(self) -> None:
        eng = make_test_engine()
        set_turn(eng, "p1", mana=10)
        sw = eng.summon_minion("p1", cid_of("Stormwind Champion"))
        yeti = eng.summon_minion("p1", cid_of("Chillwind Yeti"))
        self.assertEqual((yeti.attack, yeti.health, yeti.max_health), (5, 6, 6))
        # Deal 1 damage to Yeti -> 5/5 out of 6
        eng.deal_damage(yeti.uid, 1)
        self.assertEqual(yeti.health, 5)
        # Destroy Stormwind Champion -> Yeti clamps to 4/5 (damage resets to 0!)
        eng.destroy_minion(sw.uid)
        eng.resolve_deaths()
        self.assertEqual((yeti.attack, yeti.health, yeti.max_health), (4, 5, 5))

        # Crazed Alchemist on damaged 4/2 (4/5 with 3 damage) -> becomes 2/4 full health
        eng.deal_damage(yeti.uid, 3)
        self.assertEqual((yeti.attack, yeti.health), (4, 2))
        idx = give_hand(eng, "p1", "Crazed Alchemist")
        eng.play_card("p1", idx, target_id=yeti.uid)
        self.assertEqual((yeti.attack, yeti.health, yeti.max_health), (2, 4, 4))

    def test_taunt_stealth_elusive_divine_shield_poison(self) -> None:
        eng = make_test_engine()
        set_turn(eng, "p1", mana=10)
        taunt_m = eng.summon_minion("p2", cid_of("Sen'jin Shieldmasta"))
        other_m = eng.summon_minion("p2", cid_of("Chillwind Yeti"))
        stealth_taunt = eng.summon_minion("p2", cid_of("Chillwind Yeti"))
        eng.add_enchantment(stealth_taunt.uid, "test", "StealthTaunt", add_keywords={"STEALTH", "TAUNT"})
        faerie = eng.summon_minion("p2", cid_of("Faerie Dragon"))

        boar = eng.summon_minion("p1", cid_of("Stonetusk Boar"))
        legal = eng.get_legal_attack_targets("p1", boar.uid)
        # Only visible taunt should be legal attack target (not stealth_taunt, not other_m, not hero)
        self.assertEqual(legal, [taunt_m.uid])

        # Elusive Faerie Dragon cannot be targeted by Fireball, CAN be targeted by Elven Archer
        fb_targets = eng.get_valid_targets("p1", "ANY", is_spell_or_power=True)
        self.assertNotIn(faerie.uid, fb_targets)
        bc_targets = eng.get_valid_targets("p1", "ANY", is_spell_or_power=False)
        self.assertIn(faerie.uid, bc_targets)

        # Divine Shield absorbs damage and prevents Poisonous kill
        cobra = eng.summon_minion("p1", cid_of("Emperor Cobra"))
        cobra.summoned_this_turn = False
        squire = eng.summon_minion("p2", cid_of("Sunwalker"))
        # Remove taunt on taunt_m so only Sunwalker has taunt
        eng.silence_minion(taunt_m.uid)
        eng.attack("p1", cobra.uid, squire.uid)
        self.assertIn(squire, eng.state.players["p2"].board)
        self.assertFalse(squire.has_keyword("DIVINE_SHIELD"))

        # Attacking again kills Sunwalker via Poisonous even though Cobra only has 2 atk
        cobra2 = eng.summon_minion("p1", cid_of("Emperor Cobra"))
        cobra2.summoned_this_turn = False
        eng.attack("p1", cobra2.uid, squire.uid)
        self.assertNotIn(squire, eng.state.players["p2"].board)

    def test_gorehowl_truesilver_longbow(self) -> None:
        eng = make_test_engine("WARRIOR", "MAGE")
        set_turn(eng, "p1", mana=10)
        idx = give_hand(eng, "p1", "Gorehowl")
        eng.play_card("p1", idx)
        yeti = eng.summon_minion("p2", cid_of("Chillwind Yeti"))
        eng.attack("p1", "hero_p1", yeti.uid)
        self.assertNotIn(yeti, eng.state.players["p2"].board)
        # Gorehowl loses 1 Attack instead of 1 Durability when hitting a minion
        self.assertIsNotNone(eng.state.players["p1"].weapon)
        self.assertEqual(eng.state.players["p1"].weapon.total_attack, 6)
        self.assertEqual(eng.state.players["p1"].weapon.durability, 1)

        # Next turn hit hero -> weapon breaks
        set_turn(eng, "p1", mana=10)
        eng.attack("p1", "hero_p1", "hero_p2")
        self.assertEqual(eng.state.players["p2"].hero.hp, 24)
        self.assertIsNone(eng.state.players["p1"].weapon)


class TestSecretsAndComplexCards(unittest.TestCase):
    def test_mage_and_hunter_and_paladin_secrets(self) -> None:
        eng = make_test_engine("MAGE", "HUNTER")
        # P2 sets Explosive Trap, Freezing Trap, Snipe
        set_turn(eng, "p2", mana=10)
        for name in ("Explosive Trap", "Freezing Trap", "Snipe"):
            idx = give_hand(eng, "p2", name)
            eng.play_card("p2", idx)

        # P1 plays Chillwind Yeti (4/5) -> Snipe deals 4 dmg -> 4/1!
        set_turn(eng, "p1", mana=10)
        yeti_idx = give_hand(eng, "p1", "Chillwind Yeti")
        eng.play_card("p1", yeti_idx)
        yeti = eng.state.players["p1"].board[0]
        self.assertEqual(yeti.health, 1)

        # P1 attacks P2 hero with Yeti -> Explosive Trap deals 2 -> Yeti dies before attack lands & Freezing Trap didn't bounce dead minion? Wait: Explosive runs before Freezing if played first!
        eng.summon_minion("p1", cid_of("Boulderfist Ogre"))
        ogre = eng.state.players["p1"].board[1]
        ogre.summoned_this_turn = False
        yeti.summoned_this_turn = False
        eng.attack("p1", yeti.uid, "hero_p2")
        self.assertNotIn(yeti, eng.state.players["p1"].board)
        self.assertEqual(ogre.health, 5)  # took 2 from Explosive Trap

        # Ogre attacks P2 hero -> Freezing Trap returns Ogre to P1 hand costing 8
        eng.attack("p1", ogre.uid, "hero_p2")
        self.assertNotIn(ogre, eng.state.players["p1"].board)
        bounced = [c for c in eng.state.players["p1"].hand if c.card_id == cid_of("Boulderfist Ogre")]
        self.assertEqual(len(bounced), 1)
        self.assertEqual(eng.get_card_cost("p1", bounced[0]), 8)

    def test_ice_block_counterspell_spellbender(self) -> None:
        eng = make_test_engine("MAGE", "MAGE")
        set_turn(eng, "p2", mana=10)
        eng.state.players["p2"].hero.hp = 5
        for name in ("Counterspell", "Ice Block"):
            idx = give_hand(eng, "p2", name)
            eng.play_card("p2", idx)

        set_turn(eng, "p1", mana=10)
        # First Fireball countered by Counterspell
        idx1 = give_hand(eng, "p1", "Fireball")
        eng.play_card("p1", idx1, target_id="hero_p2")
        self.assertEqual(eng.state.players["p2"].hero.hp, 5)

        # Second Fireball triggers Ice Block -> P2 survives at 5 HP & becomes Immune
        idx2 = give_hand(eng, "p1", "Fireball")
        eng.play_card("p1", idx2, target_id="hero_p2")
        self.assertEqual(eng.state.players["p2"].hero.hp, 5)
        self.assertTrue(eng.state.players["p2"].hero.immune_this_turn)

    def test_jaraxxus_sacrificial_pact_and_shadowform(self) -> None:
        eng = make_test_engine("WARLOCK", "WARLOCK")
        set_turn(eng, "p2", mana=10)
        j_idx = give_hand(eng, "p2", "Lord Jaraxxus")
        eng.play_card("p2", j_idx)
        self.assertTrue(eng.state.players["p2"].hero.is_jaraxxus)
        self.assertEqual(eng.state.players["p2"].hero.hp, 15)
        self.assertEqual(eng.state.players["p2"].weapon.total_attack, 3)

        # P1 uses Sacrificial Pact on opponent Lord Jaraxxus -> instant win!
        set_turn(eng, "p1", mana=10)
        sp_idx = give_hand(eng, "p1", "Sacrificial Pact")
        eng.play_card("p1", sp_idx, target_id="hero_p2")
        self.assertEqual(eng.state.phase, "GAME_OVER")
        self.assertEqual(eng.state.winner, "p1")

    def test_tracking_choose_one_and_deathrattle_chain(self) -> None:
        eng = make_test_engine("DRUID", "PRIEST")
        set_turn(eng, "p1", mana=10)
        # Tracking
        t_idx = give_hand(eng, "p1", "Tracking")
        deck_before = len(eng.state.players["p1"].deck)
        eng.play_card("p1", t_idx)
        self.assertIsNotNone(eng.state.pending_choice)
        eng.resolve_pending_choice("p1", 1)
        self.assertIsNone(eng.state.pending_choice)
        self.assertEqual(len(eng.state.players["p1"].deck), deck_before - 3)

        # Choose One: Druid of the Claw Bear Form
        dotc = give_hand(eng, "p1", "Druid of the Claw")
        eng.play_card("p1", dotc, choose=1)
        bear = eng.state.players["p1"].board[-1]
        self.assertEqual((bear.attack, bear.health), (4, 6))
        self.assertTrue(bear.has_keyword("TAUNT"))

        # Sylvanas + Abomination chain
        abom = eng.summon_minion("p1", cid_of("Abomination"))
        abom.damage = 3  # 4/1
        sylv = eng.summon_minion("p2", cid_of("Sylvanas Windrunner"))
        sylv.damage = 3  # 5/2
        yeti = eng.summon_minion("p1", cid_of("Chillwind Yeti"))
        eng.destroy_minion(abom.uid)
        eng.resolve_deaths()
        # Abomination deals 2 to all -> kills Sylvanas -> Sylvanas steals Yeti!
        self.assertIn(yeti, eng.state.players["p2"].board)
        self.assertEqual(yeti.owner, "p2")

    def test_buffing_silenced_minion_works(self) -> None:
        eng = make_test_engine("WARLOCK", "MAGE")
        set_turn(eng, "p1", mana=10)
        m = eng.summon_minion("p1", cid_of("Ancient Watcher"))
        eng.silence_minion(m.uid)
        self.assertTrue(m.silenced)
        self.assertEqual(m.attack, 4)

        # Abusive Sergeant (+2 Attack this turn) must apply to a silenced minion
        sgt_idx = give_hand(eng, "p1", "Abusive Sergeant")
        eng.play_card("p1", sgt_idx, target_id=m.uid)
        self.assertEqual(m.attack, 6)

        # Velen's Chosen (+2/+4 and Spell Damage +1) must also apply to a silenced minion
        vc_idx = give_hand(eng, "p1", "Velen's Chosen")
        eng.play_card("p1", vc_idx, target_id=m.uid)
        self.assertEqual((m.attack, m.max_health, m.spell_damage), (8, 9, 1))
        self.assertEqual(eng.calc_spell_damage("p1", 2), 3)

        # End turn expires only Abusive Sergeant's temp buff, keeping Velen's Chosen
        eng.end_turn("p1")
        self.assertEqual((m.attack, m.max_health, m.spell_damage), (6, 9, 1))

    def test_freeze_persists_when_attacking_water_elemental(self) -> None:
        eng = make_test_engine("WARRIOR", "MAGE")
        we = eng.summon_minion("p2", cid_of("Water Elemental"))  # 3/6
        yeti = eng.summon_minion("p1", cid_of("Chillwind Yeti"))  # 4/5
        eng.equip_weapon("p1", cid_of("Fiery War Axe"))
        set_turn(eng, "p1", mana=10)

        # Minion attacks Water Elemental -> gets frozen AND stays frozen after ending THIS turn
        eng.attack("p1", yeti.uid, we.uid)
        self.assertTrue(yeti.frozen)
        # Hero attacks Water Elemental -> gets frozen AND stays frozen after ending THIS turn
        eng.attack("p1", "hero_p1", we.uid)
        self.assertTrue(eng.state.players["p1"].hero.frozen)

        eng.end_turn("p1")
        self.assertTrue(yeti.frozen)
        self.assertTrue(eng.state.players["p1"].hero.frozen)

        # Opponent passes -> p1's next turn starts: STILL frozen and cannot attack
        eng.end_turn("p2")
        self.assertTrue(yeti.frozen)
        self.assertTrue(eng.state.players["p1"].hero.frozen)
        self.assertEqual(eng.get_legal_attack_targets("p1", yeti.uid), [])
        self.assertEqual(eng.get_legal_attack_targets("p1", "hero_p1"), [])

        # After p1 misses their attack and ends their NEXT turn -> both thaw!
        eng.end_turn("p1")
        self.assertFalse(yeti.frozen)
        self.assertFalse(eng.state.players["p1"].hero.frozen)

    def test_bot_vs_bot_full_game(self) -> None:
        eng = make_test_engine("MAGE", "WARRIOR", seed=123, skip_mulligan=False)
        run_bot_mulligan(eng, "p1")
        run_bot_mulligan(eng, "p2")
        for _ in range(120):
            if eng.state.phase == "GAME_OVER":
                break
            run_bot_turn(eng, eng.state.active_seat)
        self.assertEqual(eng.state.phase, "GAME_OVER")
        self.assertIn(eng.state.winner, ("p1", "p2", "draw"))


if __name__ == "__main__":
    unittest.main()
