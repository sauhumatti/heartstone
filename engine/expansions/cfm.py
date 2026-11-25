"""Mean Streets of Gadgetzan (CFM) expansion card implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.catalog import CardDef, get_card
from engine.expansions.helpers import (
    KAZAKUS_EFFECTS_BY_COST,
    buff_hand_card,
    buff_hand_minions,
    cast_kazakus_effect,
    collectible_pool,
    evolve_minion,
    remove_from_deck,
    start_kazakus,
    summon_from_deck,
)
from engine.models import CardInstance, ChooseOption, Minion, PendingChoice

if TYPE_CHECKING:
    from engine.game import GameEngine


KABAL_POTIONS: tuple[str, ...] = (
    "CFM_021",  # Freezing Potion
    "CFM_065",  # Volcanic Potion
    "CFM_094",  # Felfire Potion
    "CFM_603",  # Potion of Madness
    "CFM_604",  # Greater Healing Potion
    "CFM_608",  # Blastcrystal Potion
    "CFM_611",  # Bloodfury Potion
    "CFM_620",  # Potion of Polymorph
    "CFM_661",  # Pint-Size Potion
    "CFM_662",  # Dragonfire Potion
)


TARGET_RULES: dict[str, str] = {
    # Spells
    "CFM_021": "ENEMY_CHARACTER",        # Freezing Potion
    "CFM_603": "ENEMY_MINION_ATK_LE_2",  # Potion of Madness
    "CFM_604": "FRIENDLY_CHARACTER",     # Greater Healing Potion
    "CFM_608": "MINION",                 # Blastcrystal Potion
    "CFM_611": "MINION",                 # Bloodfury Potion
    "CFM_690": "ANY",                    # Jade Shuriken
    "CFM_707": "ANY",                    # Jade Lightning
    # Minions (Targeted Battlecries / Combos)
    "CFM_061": "ANY",                    # Jinyu Waterspeaker
    "CFM_063": "MINION",                 # Kooky Chemist
    "CFM_067": "MINION",                 # Hozen Healer
    "CFM_335": "ANY",                    # Dispatch Kodo
    "CFM_626": "FRIENDLY_MINION",        # Kabal Talonpriest
    "CFM_647": "ANY",                    # Blowgill Sniper
    "CFM_657": "MINION",                 # Kabal Songstealer
    "CFM_659": "ANY",                    # Gadgetzan Socialite
    "CFM_660": "FRIENDLY_MINION",        # Manic Soulcaster
    "CFM_667": "ENEMY_MINION",           # Bomb Squad
    "CFM_672": "FRIENDLY_MINION",        # Madam Goya
    "CFM_693": "FRIENDLY_MINION",        # Gadgetzan Ferryman (Combo only)
    "CFM_694": "FRIENDLY_MINION",        # Shadow Sensei
    "CFM_816": "FRIENDLY_BEAST",         # Virmen Sensei
    "CFM_855": "MINION",                 # Defias Cleaner
}

CHOOSE_ONE_OPTIONS: dict[str, tuple[ChooseOption, ...]] = {
    "CFM_308": (  # Kun the Forgotten King
        ChooseOption("Forgotten Armor", "Gain 10 Armor.", "NONE"),
        ChooseOption("Forgotten Mana", "Refresh your Mana Crystals.", "NONE"),
    ),
}

COMBO_ONLY_TARGET_CARDS: set[str] = {
    "CFM_693",  # Gadgetzan Ferryman
}

PURE_KEYWORD_CARDS: set[str] = {
    "CFM_300",  # Public Defender (Taunt)
    "CFM_636",  # Shadow Rager (Stealth)
    "CFM_653",  # Hired Gun (Taunt)
    "CFM_665",  # Worgen Greaser (vanilla)
    "CFM_666",  # Grook Fu Master (Windfury)
    "CFM_815",  # Wickerflame Burnbristle (Taunt, Divine Shield, Lifesteal)
    "CFM_854",  # Ancient of Blossoms (Taunt)
}

DEATHRATTLE_CARDS: set[str] = {
    "CFM_095",  # Weasel Tunneler
    "CFM_120",  # Mistress of Mixtures
    "CFM_316",  # Rat Pack
    "CFM_324",  # White Eyes
    "CFM_336",  # Shaky Zipgunner
    "CFM_341",  # Sergeant Sally
    "CFM_646",  # Backstreet Leper
    "CFM_667",  # Bomb Squad
    "CFM_691",  # Jade Swarmer
    "CFM_759",  # Meanstreet Marshal
}

SECRET_CARDS: set[str] = {
    "CFM_026",  # Hidden Cache
    "CFM_620",  # Potion of Polymorph
    "CFM_800",  # Getaway Kodo
}

AURA_CARDS: set[str] = {
    "CFM_039",  # Street Trickster (Spell Damage +2)
    "CFM_325",  # Small-Time Buccaneer
    "CFM_652",  # Second-Rate Bruiser
    "CFM_670",  # Mayor Noggenfogger
    "CFM_760",  # Kabal Crystal Runner
}


def can_play_card(engine: GameEngine, seat: str, ci: CardInstance) -> Optional[tuple[bool, str]]:
    p = engine.state.players[seat]
    if ci.card_id == "CFM_310" and len(p.board) >= 7:  # Call in the Finishers
        return False, "Your board is full."
    if ci.card_id == "CFM_603" and len(p.board) >= 7:  # Potion of Madness
        return False, "Your board is full."
    return None


def cast_spell(
    engine: GameEngine,
    seat: str,
    cid: str,
    target_id: Optional[str],
    choose: Optional[int],
    was_combo: bool,
    card_instance: Optional[CardInstance] = None,
) -> bool:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]
    sd = lambda base: engine.calc_spell_damage(seat, base)
    sh = lambda base: engine.calc_spell_healing(seat, base)

    if cid == "CFM_021":  # Freezing Potion
        if target_id:
            engine.freeze_character(target_id)
        return True

    if cid == "CFM_065":  # Volcanic Potion
        dmg = sd(2)
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Volcanic Potion")
        return True

    if cid == "CFM_094":  # Felfire Potion
        dmg = sd(5)
        targets = ["hero_p1", "hero_p2"] + [
            m.uid for s in ("p1", "p2") for m in engine.state.players[s].board
        ]
        for tid in targets:
            engine.deal_damage(tid, dmg, source_seat=seat, source_name="Felfire Potion")
        return True

    if cid == "CFM_305":  # Smuggler's Run
        buff_hand_minions(engine, seat, atk=1, hp=1)
        return True

    if cid == "CFM_310":  # Call in the Finishers
        for _ in range(4):
            engine.summon_minion(seat, "CFM_310t")
        return True

    if cid == "CFM_313":  # Finders Keepers
        pool = collectible_pool(hero_class=p.hero.card_class, mechanic="OVERLOAD")
        if not pool:
            pool = collectible_pool(mechanic="OVERLOAD")
        engine.start_discover(seat, cid, pool)
        return True

    if cid == "CFM_334":  # Smuggler's Crate
        buff_hand_minions(engine, seat, atk=2, hp=2, predicate=lambda c: c.race == "BEAST", count=1)
        return True

    if cid == "CFM_603":  # Potion of Madness
        if target_id:
            m = engine.find_minion(target_id)
            if m and len(p.board) < 7:
                orig_owner = m.owner
                engine.steal_minion(m.uid, seat)
                engine.add_enchantment(
                    m.uid,
                    cid,
                    "Potion of Madness",
                    add_keywords={"CHARGE"},
                    temp_until_eot=True,
                    temp_owner_revert=orig_owner,
                )
        return True

    if cid == "CFM_604":  # Greater Healing Potion
        if target_id:
            engine.apply_heal(seat, target_id, sh(12), from_spell_or_power=True)
        engine.draw_card(seat)
        return True

    if cid == "CFM_608":  # Blastcrystal Potion
        if target_id:
            engine.destroy_minion(target_id)
        if p.max_mana > 0:
            p.max_mana -= 1
            p.mana = min(p.mana, p.max_mana)
        return True

    if cid == "CFM_611":  # Bloodfury Potion
        if target_id:
            m = engine.find_minion(target_id)
            if m:
                hp_bonus = 3 if m.race == "DEMON" else 0
                engine.add_enchantment(m.uid, cid, "Bloodfury Potion", atk=3, hp=hp_bonus)
        return True

    if cid == "CFM_614":  # Mark of the Lotus
        for m in list(p.board):
            engine.add_enchantment(m.uid, cid, "Mark of the Lotus", atk=1, hp=1)
        return True

    if cid == "CFM_616":  # Pilfered Power
        if p.max_mana >= 10:
            engine.add_card_to_hand(seat, "CS2_013t")
        else:
            p.max_mana = min(10, p.max_mana + len(p.board))
        return True

    if cid in ("CFM_621t", "CFM_621t14", "CFM_621t15"):  # Kazakus Potions
        effs = list(card_instance.custom_effects) if card_instance and card_instance.custom_effects else []
        if not effs:
            tier = {"CFM_621t": 1, "CFM_621t14": 5, "CFM_621t15": 10}[cid]
            effs = engine.rng.sample(list(KAZAKUS_EFFECTS_BY_COST[tier]), 2)
        for eff_id in effs:
            cast_kazakus_effect(engine, seat, eff_id)
        return True

    if cid == "CFM_623":  # Greater Arcane Missiles
        dmg = sd(3)
        for _ in range(3):
            cands = engine.living_enemy_characters(seat)
            if not cands:
                break
            engine.deal_damage(
                engine.rng.choice(cands), dmg, source_seat=seat, source_name="Greater Arcane Missiles"
            )
            engine.resolve_deaths()
        return True

    if cid == "CFM_630":  # Counterfeit Coin
        p.mana = min(10, p.mana + 1)
        return True

    if cid == "CFM_661":  # Pint-Size Potion
        for m in list(opp.board):
            engine.add_enchantment(m.uid, cid, "Pint-Size Potion", atk=-3, temp_until_eot=True)
        return True

    if cid == "CFM_662":  # Dragonfire Potion
        dmg = sd(5)
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                if m.race != "DRAGON":
                    engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Dragonfire Potion")
        return True

    if cid == "CFM_690":  # Jade Shuriken
        if target_id:
            engine.deal_damage(target_id, sd(3), source_seat=seat, source_name="Jade Shuriken")
        if was_combo:
            engine.summon_jade_golem(seat)
        return True

    if cid == "CFM_696":  # Devolve
        for m in list(opp.board):
            if get_card(m.card_id).cost > 0:
                evolve_minion(engine, m, delta=-1)
        return True

    if cid == "CFM_707":  # Jade Lightning
        if target_id:
            engine.deal_damage(target_id, sd(3), source_seat=seat, source_name="Jade Lightning")
        engine.summon_jade_golem(seat)
        return True

    if cid == "CFM_716":  # Sleep with the Fishes
        dmg = sd(3)
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                if m.damaged:
                    engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Sleep with the Fishes")
        return True

    if cid == "CFM_752":  # Stolen Goods
        taunts = [
            i for i, ci in enumerate(p.deck)
            if (c := get_card(ci.card_id)).type == "MINION" and c.has_mechanic("TAUNT")
        ]
        if taunts:
            ci = remove_from_deck(engine, seat, engine.rng.choice(taunts))
            drawn = engine.give_card_instance_to_hand(seat, ci, origin="deck")
            if drawn:
                buff_hand_card(engine, seat, drawn, atk=2, hp=2)
        return True

    if cid == "CFM_811":  # Lunar Visions
        for _ in range(2):
            drawn = engine.draw_card(seat)
            if drawn and get_card(drawn.card_id).type == "MINION":
                buff_hand_card(engine, seat, drawn, cost_mod=-2)
        return True

    if cid == "CFM_905":  # Small-Time Recruits
        for _ in range(3):
            one_drops = [
                i for i, ci in enumerate(p.deck)
                if (c := get_card(ci.card_id)).type == "MINION" and c.cost == 1
            ]
            if not one_drops:
                break
            ci = remove_from_deck(engine, seat, engine.rng.choice(one_drops))
            engine.give_card_instance_to_hand(seat, ci, origin="deck")
        return True

    if cid == "CFM_940":  # I Know a Guy
        pool = collectible_pool(hero_class=p.hero.card_class, card_type="MINION", mechanic="TAUNT")
        if not pool:
            pool = collectible_pool(card_type="MINION", mechanic="TAUNT")
        engine.start_discover(seat, cid, pool, choice_type="DISCOVER_I_KNOW_A_GUY")
        return True

    return False


def resolve_pending_choice(
    engine: GameEngine, seat: str, pc: PendingChoice, picked: CardInstance, option_index: int
) -> bool:
    if pc.choice_type == "DISCOVER_I_KNOW_A_GUY":
        added = engine.give_card_instance_to_hand(seat, picked, origin="choice")
        if added:
            buff_hand_card(engine, seat, added, atk=1, hp=2)
        engine.add_log(
            f"{engine.state.players[seat].name} discovered {get_card(picked.card_id).name} (+1/+2).",
            seat=seat,
        )
        return True
    return False


def trigger_battlecry(
    engine: GameEngine,
    seat: str,
    cid: str,
    minion: Optional[Minion],
    target_id: Optional[str],
    choose: Optional[int],
    was_combo: bool,
    card_instance: Optional[CardInstance] = None,
) -> bool:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]

    if cid == "CFM_020":  # Raza the Chained
        if engine.has_no_duplicates_in_deck(seat):
            p.raza_active = True
            engine.add_log(f"{p.name}'s Hero Power costs (0) for the rest of the game!", seat=seat)
        return True

    if cid == "CFM_061":  # Jinyu Waterspeaker
        if target_id:
            engine.apply_heal(seat, target_id, 6)
        return True

    if cid == "CFM_062":  # Grimestreet Protector
        if minion and minion in p.board:
            idx = p.board.index(minion)
            for ni in (idx - 1, idx + 1):
                if 0 <= ni < len(p.board):
                    engine.add_enchantment(
                        p.board[ni].uid, cid, "Grimestreet Protector", add_keywords={"DIVINE_SHIELD"}
                    )
        return True

    if cid == "CFM_063":  # Kooky Chemist
        if target_id:
            m = engine.find_minion(target_id)
            if m:
                cur_atk = max(0, m.attack)
                cur_hp = max(0, m.health)
                engine.add_enchantment(m.uid, cid, "Kooky Chemist", set_atk=cur_hp, set_hp=cur_atk)
        return True

    if cid == "CFM_066":  # Kabal Lackey
        p.extra_flags["cfm_next_secret_cost_1"] = True
        return True

    if cid == "CFM_067":  # Hozen Healer
        if target_id:
            m = engine.find_minion(target_id)
            if m:
                engine.apply_heal(seat, m.uid, m.max_health)
        return True

    if cid == "CFM_308":  # Kun the Forgotten King
        both = engine.has_fandral(seat)
        if both or choose == 0:
            p.hero.armor += 10
        if both or choose == 1:
            p.mana = p.max_mana
        return True

    if cid == "CFM_312":  # Jade Chieftain
        idx = p.board.index(minion) + 1 if minion and minion in p.board else None
        jg = engine.summon_jade_golem(seat, pos=idx)
        if jg:
            engine.add_enchantment(jg.uid, cid, "Jade Chieftain", add_keywords={"TAUNT"})
        return True

    if cid == "CFM_315":  # Alleycat
        idx = p.board.index(minion) + 1 if minion and minion in p.board else None
        engine.summon_minion(seat, "CFM_315t", pos=idx)
        return True

    if cid == "CFM_321":  # Grimestreet Informant
        pool = collectible_pool(allowed_classes=("HUNTER", "PALADIN", "WARRIOR"))
        engine.start_discover(seat, cid, pool)
        return True

    if cid == "CFM_328":  # Fight Promoter
        if any(m.health >= 6 for m in p.board):
            engine.draw_card(seat)
            engine.draw_card(seat)
        return True

    if cid == "CFM_335":  # Dispatch Kodo
        if minion and target_id and minion.attack > 0:
            engine.deal_damage(
                target_id, minion.attack, source_seat=seat, source_name="Dispatch Kodo", source_minion=minion
            )
        return True

    if cid == "CFM_338":  # Trogg Beastrager
        buff_hand_minions(engine, seat, atk=1, hp=1, predicate=lambda c: c.race == "BEAST", count=1)
        return True

    if cid == "CFM_342":  # Luckydo Buccaneer
        if minion and p.weapon and p.weapon.total_attack >= 3:
            engine.add_enchantment(minion.uid, cid, "Luckydo Buccaneer", atk=4, hp=4)
        return True

    if cid == "CFM_610":  # Crystalweaver
        for m in list(p.board):
            if m.race == "DEMON" and (not minion or m.uid != minion.uid):
                engine.add_enchantment(m.uid, cid, "Crystalweaver", atk=1, hp=1)
        return True

    if cid == "CFM_617":  # Celestial Dreamer
        if minion and any(m.uid != minion.uid and m.attack >= 5 for m in p.board):
            engine.add_enchantment(minion.uid, cid, "Celestial Dreamer", atk=2, hp=2)
        return True

    if cid == "CFM_619":  # Kabal Chemist
        engine.add_card_to_hand(seat, engine.rng.choice(KABAL_POTIONS))
        return True

    if cid == "CFM_621":  # Kazakus
        if engine.has_no_duplicates_in_deck(seat):
            start_kazakus(engine, seat)
        return True

    if cid == "CFM_626":  # Kabal Talonpriest
        if target_id:
            engine.add_enchantment(target_id, cid, "Kabal Talonpriest", hp=3)
        return True

    if cid == "CFM_643":  # Hobart Grapplehammer
        if p.weapon is not None:
            buff_hand_minions(engine, seat, atk=2, hp=2)
            for ci in p.deck:
                if get_card(ci.card_id).type == "MINION":
                    ci.attack_mod += 2
                    ci.health_mod += 2
            engine.add_log(
                f"Hobart Grapplehammer gave all minions in {p.name}'s hand and deck +2/+2.",
                seat=seat,
            )
        return True

    if cid == "CFM_647":  # Blowgill Sniper
        if target_id:
            engine.deal_damage(target_id, 1, source_seat=seat, source_name="Blowgill Sniper", source_minion=minion)
        return True

    if cid == "CFM_648":  # Big-Time Racketeer
        idx = p.board.index(minion) + 1 if minion and minion in p.board else None
        engine.summon_minion(seat, "CFM_648t", pos=idx)
        return True

    if cid == "CFM_649":  # Kabal Courier
        pool = collectible_pool(allowed_classes=("MAGE", "PRIEST", "WARLOCK"))
        engine.start_discover(seat, cid, pool)
        return True

    if cid == "CFM_650":  # Grimscale Chum
        buff_hand_minions(engine, seat, atk=1, hp=1, predicate=lambda c: c.race == "MURLOC", count=1)
        return True

    if cid == "CFM_651":  # Naga Corsair
        if p.weapon:
            p.weapon.attack_bonus += 1
        return True

    if cid == "CFM_655":  # Toxic Sewer Ooze
        if opp.weapon:
            opp.weapon.durability -= 1
            if opp.weapon.durability <= 0:
                engine.destroy_weapon(opp_seat)
        return True

    if cid == "CFM_656":  # Streetwise Investigator
        for m in opp.board:
            engine.break_stealth(m)
        return True

    if cid == "CFM_657":  # Kabal Songstealer
        if target_id:
            engine.silence_minion(target_id)
        return True

    if cid == "CFM_659":  # Gadgetzan Socialite
        if target_id:
            engine.apply_heal(seat, target_id, 2)
        return True

    if cid == "CFM_660":  # Manic Soulcaster
        if target_id:
            m = engine.find_minion(target_id)
            if m:
                engine.shuffle_into_deck(seat, m.card_id, count=1)
        return True

    if cid == "CFM_667":  # Bomb Squad
        if target_id:
            engine.deal_damage(target_id, 5, source_seat=seat, source_name="Bomb Squad", source_minion=minion)
        return True

    if cid == "CFM_668":  # Doppelgangster
        if minion:
            for tok in ("CFM_668t", "CFM_668t2"):
                idx = p.board.index(minion) + 1 if minion in p.board else None
                copy_m = engine.summon_minion(seat, tok, pos=idx)
                if copy_m:
                    engine.copy_minion_into(minion, copy_m)
        return True

    if cid == "CFM_671":  # Cryomancer
        if minion and (opp.hero.frozen or any(m.frozen for m in opp.board)):
            engine.add_enchantment(minion.uid, cid, "Cryomancer", atk=2, hp=2)
        return True

    if cid == "CFM_672":  # Madam Goya
        if target_id:
            m = engine.find_minion(target_id)
            if m:
                match_id = m.card_id
                while len(p.board) < 7:
                    idx = next((i for i, ci in enumerate(p.deck) if ci.card_id == match_id), None)
                    if idx is None:
                        break
                    summon_from_deck(engine, seat, idx)
        return True

    if cid == "CFM_685":  # Don Han'Cho
        buff_hand_minions(engine, seat, atk=5, hp=5, count=1)
        return True

    if cid == "CFM_687":  # Inkmaster Solia
        if engine.has_no_duplicates_in_deck(seat):
            p.extra_flags["cfm_solia_free_spell"] = True
        return True

    if cid == "CFM_688":  # Spiked Hogrider
        if minion and any(m.has_keyword("TAUNT") for m in opp.board):
            engine.add_enchantment(minion.uid, cid, "Spiked Hogrider", add_keywords={"CHARGE"})
        return True

    if cid == "CFM_693":  # Gadgetzan Ferryman
        if was_combo and target_id:
            m = engine.find_minion(target_id)
            if m:
                engine.bounce_minion(m)
        return True

    if cid == "CFM_694":  # Shadow Sensei
        chosen: Optional[Minion] = None
        if target_id:
            m = engine.find_minion(target_id)
            if m and m.owner == seat and m.has_keyword("STEALTH"):
                chosen = m
        if chosen is None:
            stealthed = [
                bm for bm in p.board
                if (not minion or bm.uid != minion.uid) and bm.has_keyword("STEALTH")
            ]
            if stealthed:
                chosen = engine.rng.choice(stealthed)
        if chosen:
            engine.add_enchantment(chosen.uid, cid, "Shadow Sensei", atk=2, hp=2)
        return True

    if cid == "CFM_699":  # Seadevil Stinger
        p.next_murloc_costs_health = True
        return True

    if cid == "CFM_717":  # Jade Claws (Weapon Battlecry)
        engine.summon_jade_golem(seat)
        return True

    if cid == "CFM_750":  # Krul the Unshackled
        if engine.has_no_duplicates_in_deck(seat):
            while len(p.board) < 7:
                idx = next(
                    (
                        i
                        for i, ci in enumerate(p.hand)
                        if (c := get_card(ci.card_id)).type == "MINION" and c.race == "DEMON"
                    ),
                    None,
                )
                if idx is None:
                    break
                engine.summon_minion_from_hand(seat, idx, len(p.board))
        return True

    if cid == "CFM_751":  # Abyssal Enforcer
        targets = ["hero_p1", "hero_p2"] + [
            m.uid
            for s in ("p1", "p2")
            for m in engine.state.players[s].board
            if not minion or m.uid != minion.uid
        ]
        for tid in targets:
            engine.deal_damage(tid, 3, source_seat=seat, source_name="Abyssal Enforcer", source_minion=minion)
        return True

    if cid == "CFM_753":  # Grimestreet Outfitter
        buff_hand_minions(engine, seat, atk=1, hp=1)
        return True

    if cid == "CFM_755":  # Grimestreet Pawnbroker
        weapons = [ci for ci in p.hand if get_card(ci.card_id).type == "WEAPON"]
        if weapons:
            ci = engine.rng.choice(weapons)
            buff_hand_card(engine, seat, ci, atk=1, hp=1)
        return True

    if cid == "CFM_790":  # Dirty Rat
        if len(opp.board) < 7:
            minions = [i for i, ci in enumerate(opp.hand) if get_card(ci.card_id).type == "MINION"]
            if minions:
                engine.summon_minion_from_hand(opp_seat, engine.rng.choice(minions), len(opp.board))
        return True

    if cid == "CFM_806":  # Wrathion
        for _ in range(30):
            if not p.deck:
                engine.draw_card(seat)
                break
            top_race = get_card(p.deck[0].card_id).race
            engine.draw_card(seat)
            if engine.state.phase != "PLAY" or top_race != "DRAGON":
                break
        return True

    if cid == "CFM_809":  # Tanaris Hogchopper
        if minion and len(opp.hand) == 0:
            engine.add_enchantment(minion.uid, cid, "Tanaris Hogchopper", add_keywords={"CHARGE"})
        return True

    if cid == "CFM_810":  # Leatherclad Hogleader
        if minion and len(opp.hand) >= 6:
            engine.add_enchantment(minion.uid, cid, "Leatherclad Hogleader", add_keywords={"CHARGE"})
        return True

    if cid == "CFM_816":  # Virmen Sensei
        if target_id:
            engine.add_enchantment(target_id, cid, "Virmen Sensei", atk=3, hp=3)
        return True

    if cid == "CFM_852":  # Lotus Agents
        pool = collectible_pool(allowed_classes=("DRUID", "ROGUE", "SHAMAN"))
        engine.start_discover(seat, cid, pool)
        return True

    if cid == "CFM_853":  # Grimestreet Smuggler
        buff_hand_minions(engine, seat, atk=1, hp=1, count=1)
        return True

    if cid == "CFM_855":  # Defias Cleaner
        from engine.effects import DEATHRATTLE_CARDS as ALL_DR_CARDS

        def has_dr(m: Minion) -> bool:
            return not m.silenced and (
                m.card_id in ALL_DR_CARDS or any(e.extra_deathrattle for e in m.enchantments)
            )

        target_m = engine.find_minion(target_id) if target_id else None
        if target_m and has_dr(target_m):
            engine.silence_minion(target_m.uid)
        else:
            dr_minions = [
                bm
                for s in (opp_seat, seat)
                for bm in engine.state.players[s].board
                if (not minion or bm.uid != minion.uid) and has_dr(bm)
            ]
            if dr_minions:
                engine.silence_minion(dr_minions[0].uid)
        return True

    return False


def trigger_deathrattle(
    engine: GameEngine, seat: str, cid: str, orig_pos: int, dead_minion: Optional[Minion] = None
) -> bool:
    opp_seat = engine.other_seat(seat)

    if cid == "CFM_095":  # Weasel Tunneler
        engine.shuffle_into_deck(opp_seat, "CFM_095", count=1)
        return True

    if cid == "CFM_120":  # Mistress of Mixtures
        engine.apply_heal(seat, f"hero_{seat}", 4)
        engine.apply_heal(seat, f"hero_{opp_seat}", 4)
        return True

    if cid == "CFM_316":  # Rat Pack
        cnt = max(0, dead_minion.attack) if dead_minion else 2
        for _ in range(min(cnt, 7)):
            engine.summon_minion(seat, "CFM_316t", pos=orig_pos)
        return True

    if cid == "CFM_324":  # White Eyes
        engine.shuffle_into_deck(seat, "CFM_324t", count=1)
        return True

    if cid == "CFM_336":  # Shaky Zipgunner
        buff_hand_minions(engine, seat, atk=2, hp=2, count=1)
        return True

    if cid == "CFM_341":  # Sergeant Sally
        dmg = max(0, dead_minion.attack) if dead_minion else 1
        if dmg > 0:
            for m in list(engine.state.players[opp_seat].board):
                engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Sergeant Sally")
        return True

    if cid == "CFM_646":  # Backstreet Leper
        engine.deal_damage(f"hero_{opp_seat}", 2, source_seat=seat, source_name="Backstreet Leper")
        return True

    if cid == "CFM_667":  # Bomb Squad
        engine.deal_damage(f"hero_{seat}", 5, source_seat=seat, source_name="Bomb Squad")
        return True

    if cid == "CFM_691":  # Jade Swarmer
        engine.summon_jade_golem(seat, pos=orig_pos)
        return True

    if cid == "CFM_759":  # Meanstreet Marshal
        if dead_minion and dead_minion.attack >= 2:
            engine.draw_card(seat)
        return True

    return False


def on_start_turn(engine: GameEngine, seat: str) -> None:
    p = engine.state.players[seat]
    p.extra_flags.pop("cfm_next_secret_cost_1", None)
    p.extra_flags.pop("cfm_solia_free_spell", None)
    p.extra_flags.pop("cfm_attacking_weapon", None)


def on_eot_both(engine: GameEngine, active_seat: str) -> None:
    p = engine.state.players[active_seat]
    p.extra_flags.pop("cfm_next_secret_cost_1", None)
    p.extra_flags.pop("cfm_solia_free_spell", None)
    p.extra_flags.pop("cfm_attacking_weapon", None)


def on_sot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    if minion.silenced:
        return
    if minion.card_id == "CFM_609":  # Fel Orc Soulfiend
        engine.deal_damage(
            minion.uid, 2, source_seat=seat, source_name="Fel Orc Soulfiend", source_minion=minion
        )


def on_eot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    if minion.silenced:
        return
    cid = minion.card_id
    if cid == "CFM_639":  # Grimestreet Enforcer
        buff_hand_minions(engine, seat, atk=1, hp=1)
    elif cid == "CFM_654":  # Friendly Bartender
        engine.apply_heal(seat, f"hero_{seat}", 1)
    elif cid == "CFM_663":  # Kabal Trafficker
        demons = collectible_pool(card_type="MINION", race="DEMON")
        if demons:
            engine.add_card_to_hand(seat, engine.rng.choice(demons))
    elif cid == "CFM_754":  # Grimy Gadgeteer
        buff_hand_minions(engine, seat, atk=2, hp=2, count=1)


def on_card_played(engine: GameEngine, seat: str, card: CardDef, ci: CardInstance) -> None:
    p = engine.state.players[seat]
    if card.type == "SPELL":
        if card.has_mechanic("SECRET") and p.extra_flags.get("cfm_next_secret_cost_1"):
            p.extra_flags["cfm_next_secret_cost_1"] = False
        if p.extra_flags.get("cfm_solia_free_spell"):
            p.extra_flags["cfm_solia_free_spell"] = False
    elif card.type == "WEAPON":
        if (card.durability == 0 and card.health) or ci.attack_mod or ci.health_mod:
            p.extra_flags["cfm_weapon_init"] = (card.id, card.durability, card.health, ci.attack_mod, ci.health_mod)


def on_minion_played(engine: GameEngine, seat: str, card: CardDef, minion: Optional[Minion]) -> None:
    # Patches the Pirate: After you play a Pirate, summon this minion from your deck.
    if card.race == "PIRATE":
        p = engine.state.players[seat]
        while len(p.board) < 7:
            idx = next((i for i, ci in enumerate(p.deck) if ci.card_id == "CFM_637"), None)
            if idx is None:
                break
            engine.add_log("I'm in charge now! Patches the Pirate leaps from the deck!", seat=seat)
            summon_from_deck(engine, seat, idx)


def on_minion_summoned(engine: GameEngine, seat: str, minion: Minion) -> None:
    p = engine.state.players[seat]
    # Blubber Baron: Whenever you summon a Battlecry minion while this is in your hand, gain +1/+1.
    if get_card(minion.card_id).has_mechanic("BATTLECRY"):
        for ci in p.hand:
            if ci.card_id == "CFM_064":
                buff_hand_card(engine, seat, ci, atk=1, hp=1)

    # Unlicensed Apothecary: After you summon a minion, deal 5 damage to your hero.
    for bm in list(p.board):
        if not bm.silenced and bm.card_id == "CFM_900" and bm.uid != minion.uid:
            engine.deal_damage(
                f"hero_{seat}", 5, source_seat=seat, source_name="Unlicensed Apothecary", source_minion=bm
            )


def on_spell_cast(engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]) -> None:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]

    # Red Mana Wyrm: Whenever you cast a spell, gain +2 Attack.
    for m in list(p.board):
        if not m.silenced and m.card_id == "CFM_060":
            engine.add_enchantment(m.uid, "CFM_060", "Red Mana Wyrm", atk=2)

    # Burgly Bully: Whenever your opponent casts a spell, add a Coin to your hand.
    for m in list(opp.board):
        if not m.silenced and m.card_id == "CFM_669":
            engine.add_card_to_hand(opp_seat, "GAME_005")


def on_after_spell(engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]) -> None:
    p = engine.state.players[seat]
    # Auctionmaster Beardo: After you cast a spell, refresh your Hero Power.
    if any(not m.silenced and m.card_id == "CFM_807" for m in p.board):
        p.hero.hero_power_used = False
        p.hero.hero_power_uses_this_turn = 0


def on_damage_minion(
    engine: GameEngine, m: Minion, amount: int, source_seat: Optional[str], source_minion: Optional[Minion]
) -> None:
    # Alley Armorsmith: Whenever this minion deals damage, gain that much Armor.
    if source_minion and not source_minion.silenced and source_minion.card_id == "CFM_756" and amount > 0:
        engine.state.players[source_minion.owner].hero.armor += amount


def on_damage_hero(
    engine: GameEngine, target_seat: str, amount: int, source_seat: Optional[str], source_minion: Optional[Minion]
) -> None:
    # Alley Armorsmith: Whenever this minion deals damage, gain that much Armor.
    if source_minion and not source_minion.silenced and source_minion.card_id == "CFM_756" and amount > 0:
        engine.state.players[source_minion.owner].hero.armor += amount


def on_heal(engine: GameEngine, caster_seat: str, target_id: str, amount: int, healed_minion: bool) -> None:
    if not healed_minion:
        return
    # Mana Geode: Overheal / healed -> Summon a 2/2 Crystal.
    m = engine.find_minion(target_id)
    if m and not m.silenced and m.card_id == "CFM_606":
        board = engine.state.players[m.owner].board
        idx = board.index(m) + 1 if m in board else None
        engine.summon_minion(m.owner, "CFM_606t", pos=idx)


def on_death(engine: GameEngine, dead_minion: Minion, orig_pos: int) -> None:
    # Backroom Bouncer: Whenever a friendly minion dies, gain +1 Attack.
    for m in list(engine.state.players[dead_minion.owner].board):
        if not m.silenced and m.card_id == "CFM_658":
            engine.add_enchantment(m.uid, "CFM_658", "Backroom Bouncer", atk=1)


def on_draw(engine: GameEngine, seat: str, ci: CardInstance) -> bool:
    # Daring Reporter: Whenever your opponent draws a card, gain +1/+1.
    opp_seat = engine.other_seat(seat)
    for m in list(engine.state.players[opp_seat].board):
        if not m.silenced and m.card_id == "CFM_851":
            engine.add_enchantment(m.uid, "CFM_851", "Daring Reporter", atk=1, hp=1)
    return False


def on_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> tuple[str, bool]:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]

    # Track attacking weapon before durability consumption (Piranha Launcher / Brass Knuckles)
    if attacker_id == f"hero_{seat}" and p.weapon:
        p.extra_flags["cfm_attacking_weapon"] = p.weapon.card_id
    else:
        p.extra_flags.pop("cfm_attacking_weapon", None)

    atk_m = None if attacker_id.startswith("hero_") else engine.find_minion(attacker_id)
    if atk_m and not atk_m.silenced:
        if atk_m.card_id == "CFM_781":  # Shaku, the Collector
            pool = collectible_pool(other_class_of=p.hero.card_class)
            if pool:
                engine.add_card_to_hand(seat, engine.rng.choice(pool))
        elif atk_m.card_id == "CFM_808":  # Genzo, the Shark
            for s in (seat, opp_seat):
                pl = engine.state.players[s]
                to_draw = max(0, 3 - len(pl.hand))
                for _ in range(to_draw):
                    if engine.state.phase != "PLAY":
                        break
                    engine.draw_card(s)

    # Mayor Noggenfogger: All targets are chosen randomly.
    has_noggen = any(
        not bm.silenced and bm.card_id == "CFM_670"
        for s in ("p1", "p2")
        for bm in engine.state.players[s].board
    )
    if has_noggen:
        taunts = [
            em.uid
            for em in opp.board
            if em.has_keyword("TAUNT")
            and not em.has_keyword("STEALTH")
            and not em.has_keyword("DORMANT")
            and not em.immune_this_turn
        ]
        if taunts:
            cands = taunts
        else:
            cands = []
            if not opp.hero.immune_this_turn and not opp.hero.immune_aura:
                cands.append(f"hero_{opp_seat}")
            for em in opp.board:
                if not em.has_keyword("STEALTH") and not em.has_keyword("DORMANT") and not em.immune_this_turn:
                    cands.append(em.uid)
        if cands:
            target_id = engine.rng.choice(cands)

    return target_id, False


def on_after_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> None:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)

    if attacker_id == f"hero_{seat}":
        wep_id = p.extra_flags.pop("cfm_attacking_weapon", None)
        if wep_id == "CFM_337":  # Piranha Launcher
            engine.summon_minion(seat, "CFM_337t")
        elif wep_id == "CFM_631":  # Brass Knuckles
            buff_hand_minions(engine, seat, atk=1, hp=1, count=1)
        return

    atk_m = engine.find_minion(attacker_id)
    if not atk_m or atk_m.silenced:
        return

    cid = atk_m.card_id
    if not target_id.startswith("hero_"):
        def_m = engine.find_minion(target_id)
        if cid == "CFM_025" and atk_m.health > 0:  # Wind-up Burglebot
            engine.draw_card(seat)
        elif cid == "CFM_333" and atk_m.attack > 0:  # Knuckles
            engine.deal_damage(
                f"hero_{opp_seat}", atk_m.attack, source_seat=seat, source_name="Knuckles", source_minion=atk_m
            )
        elif cid == "CFM_344" and def_m and def_m.health <= 0:  # Finja, the Flying Star
            for _ in range(2):
                if len(p.board) >= 7:
                    break
                murlocs = [i for i, ci in enumerate(p.deck) if get_card(ci.card_id).race == "MURLOC"]
                if not murlocs:
                    break
                summon_from_deck(engine, seat, engine.rng.choice(murlocs))
        elif cid == "CFM_634" and atk_m.health > 0 and def_m and def_m.health <= 0:  # Lotus Assassin
            engine.add_enchantment(atk_m.uid, cid, "Lotus Assassin", add_keywords={"STEALTH"})
    else:
        if cid == "CFM_697" and atk_m.health > 0:  # Lotus Illusionist
            pool = collectible_pool(card_type="MINION", cost=6)
            if pool:
                engine.transform_minion(atk_m.uid, engine.rng.choice(pool))


def recompute_auras(engine: GameEngine) -> None:
    for s in ("p1", "p2"):
        pl = engine.state.players[s]

        # Apply weapon durability fix (CFM_337/CFM_631/CFM_717) & weapon handbuff (Grimestreet Pawnbroker)
        init = pl.extra_flags.get("cfm_weapon_init")
        if init and pl.weapon and pl.weapon.card_id == init[0]:
            pl.extra_flags.pop("cfm_weapon_init", None)
            _, dur, health, atk_mod, hp_mod = init
            if dur == 0 and health:
                pl.weapon.durability = health
                pl.weapon.max_durability = health
            if atk_mod:
                pl.weapon.attack_bonus += atk_mod
            if hp_mod:
                pl.weapon.durability += hp_mod
                pl.weapon.max_durability += hp_mod

        for m in pl.board:
            if m.silenced:
                continue
            if m.card_id == "CFM_039":  # Street Trickster (Spell Damage +2; catalog base is 1)
                m.spell_damage += 1
            elif m.card_id == "CFM_325" and pl.weapon is not None:  # Small-Time Buccaneer
                m.aura_atk_bonus += 2
                m.attack += 2


def get_card_cost(engine: GameEngine, seat: str, ci: CardInstance, cost: int) -> int:
    p = engine.state.players[seat]
    opp = engine.state.players[engine.other_seat(seat)]
    cid = ci.card_id
    card = get_card(cid)

    if cid == "CFM_652":  # Second-Rate Bruiser
        if len(opp.board) >= 3:
            cost -= 2
    elif cid == "CFM_760":  # Kabal Crystal Runner
        cost -= 2 * p.secrets_played

    if card.type == "SPELL":
        if p.extra_flags.get("cfm_solia_free_spell"):
            return 0
        if card.has_mechanic("SECRET") and p.extra_flags.get("cfm_next_secret_cost_1"):
            return min(cost, 1)

    return cost


def trigger_secrets_on_minion_played(engine: GameEngine, def_seat: str, summoned: Minion) -> None:
    p = engine.state.players[def_seat]
    for sec in list(p.secrets):
        if sec.card_id == "CFM_026":  # Hidden Cache
            engine._reveal_secret(def_seat, sec)
            buff_hand_minions(engine, def_seat, atk=2, hp=2, count=1)
        elif sec.card_id == "CFM_620":  # Potion of Polymorph
            if summoned in engine.state.players[summoned.owner].board:
                engine._reveal_secret(def_seat, sec)
                engine.transform_minion(summoned.uid, "CFM_621_m5")


def trigger_secrets_on_death(engine: GameEngine, def_seat: str, dead_m: Minion, orig_pos: int) -> None:
    p = engine.state.players[def_seat]
    for sec in list(p.secrets):
        if sec.card_id == "CFM_800":  # Getaway Kodo
            engine._reveal_secret(def_seat, sec)
            engine.add_card_to_hand(def_seat, dead_m.card_id)
            break
