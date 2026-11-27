"""The Grand Tournament (AT) expansion card implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from engine.catalog import CardDef, get_card
from engine.expansions import helpers
from engine.models import CardInstance, ChooseOption, Minion

if TYPE_CHECKING:
    from engine.game import GameEngine


BASIC_TOTEMS: tuple[str, ...] = (
    "VAN_CS2_050",  # Searing Totem
    "VAN_CS2_051",  # Stoneclaw Totem
    "VAN_CS2_052",  # Wrath of Air Totem
    "VAN_NEW1_009",  # Healing Totem
)

TGT_WEAPONS_WITH_HEALTH_DURABILITY: frozenset[str] = frozenset({
    "AT_034",  # Poisoned Blade (1/3)
    "AT_050",  # Charged Hammer (2/3)
    "AT_065",  # King's Defender (3/2)
    "AT_077",  # Argent Lance (2/2)
})


TARGET_RULES: dict[str, str] = {
    # Spells
    "AT_001": "MINION",           # Flame Lance
    "AT_005": "MINION",           # Polymorph: Boar
    "AT_013": "MINION",           # Power Word: Glory
    "AT_015": "ENEMY_MINION",     # Convert
    "AT_024": "DEMON",            # Demonfuse
    "AT_044": "MINION",           # Mulch
    "AT_048": "ANY",              # Healing Wave
    "AT_055": "ANY",              # Flash Heal
    "AT_056": "MINION",           # Powershot
    "AT_074": "MINION",           # Seal of Champions
    # Hero Power
    "AT_050t": "ANY",             # Lightning Jolt
    # Targeted Battlecry / Combo minions
    "AT_030": "ANY",              # Undercity Valiant (Combo only)
    "AT_040": "FRIENDLY_BEAST",   # Wildwalker
    "AT_057": "FRIENDLY_BEAST",   # Stablemaster
    "AT_069": "MINION",           # Sparring Partner
    "AT_084": "FRIENDLY_MINION",  # Lance Carrier
    "AT_096": "FRIENDLY_MECH",    # Clockwork Knight
    "AT_103": "ANY",              # North Sea Kraken
    "AT_106": "DEMON",            # Light's Champion
}

CHOOSE_ONE_OPTIONS: dict[str, tuple[ChooseOption, ...]] = {
    "AT_042": (  # Druid of the Saber
        ChooseOption("Lion Form", "Transform into a 2/1 with Charge.", "NONE"),
        ChooseOption("Panther Form", "Transform into a 3/2 with Stealth.", "NONE"),
    ),
}

COMBO_ONLY_TARGET_CARDS: set[str] = {
    "AT_030",  # Undercity Valiant
}

DRAGON_ONLY_TARGET_CARDS: set[str] = set()

CONDITIONAL_TARGET_RULES: dict[str, Callable[..., str]] = {
    # Gormok the Impaler: only targets if you have at least 4 other minions on board
    "AT_122": lambda eng, seat, _ex: "ANY" if len(eng.state.players[seat].board) >= 4 else "NONE",
}

PURE_KEYWORD_CARDS: set[str] = {
    "AT_020",  # Fearsome Doomguard
    "AT_087",  # Argent Horserider
    "AT_088",  # Mogor's Champion (FORGETFUL handled natively by GameEngine)
    "AT_092",  # Ice Rager
    "AT_093",  # Frigid Snobold
    "AT_095",  # Silent Knight
    "AT_097",  # Tournament Attendee
    "AT_101",  # Pit Fighter
    "AT_102",  # Captured Jormungar
    "AT_114",  # Evil Heckler
    "AT_125",  # Icehowl (CANT_ATTACK_HERO handled natively by GameEngine)
}

DEATHRATTLE_CARDS: set[str] = {
    "AT_009",   # Rhonin
    "AT_019",   # Dreadsteed
    "AT_036",   # Anub'arak
    "AT_036t",  # Nerubian (summons Anub'arak)
    "AT_123",   # Chillmaw
    "AT_128",   # The Skeleton Knight
}

SECRET_CARDS: set[str] = {
    "AT_002",  # Effigy
    "AT_060",  # Bear Trap
    "AT_073",  # Competitive Spirit
}

AURA_CARDS: set[str] = {
    "AT_003",  # Fallen Hero
    "AT_006",  # Dalaran Aspirant
    "AT_008",  # Coldarra Drake
    "AT_027",  # Wilfred Fizzlebang
    "AT_041",  # Knight of the Wild
    "AT_045",  # Aviana
    "AT_070",  # Skycap'n Kragg
    "AT_075",  # Warhorse Trainer
    "AT_080",  # Garrison Commander
    "AT_085",  # Maiden of the Lake
    "AT_120",  # Frost Giant
}


def _summon_vanilla_nerubian(engine: GameEngine, seat: str) -> Optional[Minion]:
    m = engine.summon_minion(seat, "AT_036t")
    if m:
        m.base_keywords.discard("DEATHRATTLE")
        m.extra_data["vanilla_nerubian"] = True
        engine.recompute_auras()
    return m


def _buff_friendly_totems(engine: GameEngine, seat: str) -> None:
    p = engine.state.players[seat]
    for m in list(p.board):
        if m.race == "TOTEM":
            engine.add_enchantment(m.uid, "AT_049", "Thunder Bluff Valiant", atk=2)


def _summon_random_legendary(engine: GameEngine, seat: str) -> None:
    pool = helpers.collectible_pool(card_type="MINION", rarity="LEGENDARY")
    if pool:
        engine.summon_minion(seat, engine.rng.choice(pool))


# ---------------------------------------------------------------------------
# SPELLS
# ---------------------------------------------------------------------------

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

    if cid == "AT_001":  # Flame Lance
        engine.deal_damage(target_id, sd(25), source_seat=seat, source_name="Flame Lance")
        return True

    if cid == "AT_005":  # Polymorph: Boar
        engine.transform_minion(target_id, "AT_005t")
        return True

    if cid == "AT_013":  # Power Word: Glory
        engine.add_enchantment(target_id, cid, f"Power Word: Glory ({seat})")
        return True

    if cid == "AT_015":  # Convert
        m = engine.find_minion(target_id)
        if m:
            base_cost = get_card(m.card_id).cost
            engine.add_card_to_hand(seat, m.card_id, cost_mod=1 - base_cost)
        return True

    if cid == "AT_016":  # Confuse
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                old_atk = max(0, m.attack)
                old_hp = max(0, m.health)
                engine.add_enchantment(m.uid, cid, "Confuse", set_atk=old_hp, set_hp=old_atk)
                if old_atk <= 0:
                    engine.destroy_minion(m.uid)
        return True

    if cid == "AT_022":  # Fist of Jaraxxus
        cands = engine.living_enemy_characters(seat)
        if cands:
            engine.deal_damage(engine.rng.choice(cands), sd(4), source_seat=seat, source_name="Fist of Jaraxxus")
        return True

    if cid == "AT_024":  # Demonfuse
        if target_id and not target_id.startswith("hero_"):
            engine.add_enchantment(target_id, cid, "Demonfuse", atk=3, hp=3)
        return True

    if cid == "AT_025":  # Dark Bargain
        targets = engine.rng.sample(list(opp.board), min(2, len(opp.board)))
        for m in targets:
            engine.destroy_minion(m.uid)
        engine.discard_random(seat)
        engine.discard_random(seat)
        return True

    if cid == "AT_033":  # Burgle
        pool = helpers.collectible_pool(hero_class=opp.hero.card_class, include_neutral=False)
        if pool:
            for _ in range(3):
                engine.add_card_to_hand(seat, engine.rng.choice(pool))
        return True

    if cid == "AT_035":  # Beneath the Grounds
        engine.shuffle_into_deck(opp_seat, "AT_035t", count=3)
        return True

    if cid == "AT_035t":  # Nerubian Ambush! (if played directly from hand)
        _summon_vanilla_nerubian(engine, opp_seat)
        return True

    if cid == "AT_043":  # Astral Communion
        engine.discard_hand(seat)
        if p.max_mana >= 10:
            engine.add_card_to_hand(seat, "CS2_013t")
        else:
            p.max_mana = 10
            p.mana = max(0, 10 - p.overloaded)
        return True

    if cid == "AT_044":  # Mulch
        engine.destroy_minion(target_id)
        pool = helpers.collectible_pool(card_type="MINION")
        if pool:
            engine.add_card_to_hand(opp_seat, engine.rng.choice(pool))
        return True

    if cid == "AT_048":  # Healing Wave
        amt = 16 if helpers.joust(engine, seat) else 8
        engine.apply_heal(seat, target_id, sh(amt), from_spell_or_power=True)
        return True

    if cid == "AT_051":  # Elemental Destruction
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                dmg = sd(engine.rng.randint(4, 5))
                engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Elemental Destruction")
        return True

    if cid == "AT_053":  # Ancestral Knowledge
        engine.draw_card(seat)
        engine.draw_card(seat)
        return True

    if cid == "AT_055":  # Flash Heal
        engine.apply_heal(seat, target_id, sh(5), from_spell_or_power=True)
        return True

    if cid == "AT_056":  # Powershot
        m = engine.find_minion(target_id)
        if m:
            owner_board = engine.state.players[m.owner].board
            if m in owner_board:
                idx = owner_board.index(m)
                targets = [m.uid]
                if idx - 1 >= 0:
                    targets.append(owner_board[idx - 1].uid)
                if idx + 1 < len(owner_board):
                    targets.append(owner_board[idx + 1].uid)
                dmg = sd(2)
                for tid in targets:
                    engine.deal_damage(tid, dmg, source_seat=seat, source_name="Powershot")
        return True

    if cid == "AT_061":  # Lock and Load
        p.lock_and_load_count += 1
        return True

    if cid == "AT_062":  # Ball of Spiders
        for _ in range(3):
            engine.summon_minion(seat, "FP1_011")
        return True

    if cid == "AT_068":  # Bolster
        for m in list(p.board):
            if m.has_keyword("TAUNT"):
                engine.add_enchantment(m.uid, cid, "Bolster", atk=2, hp=2)
        return True

    if cid == "AT_074":  # Seal of Champions
        engine.add_enchantment(target_id, cid, "Seal of Champions", atk=3, add_keywords={"DIVINE_SHIELD"})
        return True

    if cid == "AT_078":  # Enter the Coliseum
        for s in ("p1", "p2"):
            board = [m for m in engine.state.players[s].board if not m.has_keyword("DORMANT")]
            if len(board) > 1:
                max_atk = max(m.attack for m in board)
                top = [m for m in board if m.attack == max_atk]
                survivor = engine.rng.choice(top)
                for m in board:
                    if m.uid != survivor.uid:
                        engine.destroy_minion(m.uid)
        return True

    return False


# ---------------------------------------------------------------------------
# BATTLECRIES / COMBOS / CHOOSE ONE MINIONS / WEAPON BATTLECRIES
# ---------------------------------------------------------------------------

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

    if cid == "AT_007":  # Spellslinger
        spells = helpers.collectible_pool(card_type="SPELL")
        if spells:
            engine.add_card_to_hand(seat, engine.rng.choice(spells), cost_mod=-2)
            engine.add_card_to_hand(opp_seat, engine.rng.choice(spells))
        return True

    if cid == "AT_010":  # Ram Wrangler
        if any(m.race == "BEAST" for m in p.board):
            beasts = helpers.collectible_pool(card_type="MINION", race="BEAST")
            if beasts:
                engine.summon_minion(seat, engine.rng.choice(beasts))
        return True

    if cid == "AT_012":  # Spawn of Shadows
        engine.deal_damage(f"hero_{seat}", 4, source_seat=seat, source_name="Spawn of Shadows", source_minion=minion)
        engine.deal_damage(f"hero_{opp_seat}", 4, source_seat=seat, source_name="Spawn of Shadows", source_minion=minion)
        return True

    if cid == "AT_018":  # Confessor Paletress
        _summon_random_legendary(engine, seat)
        return True

    if cid == "AT_028":  # Shado-Pan Rider
        if was_combo and minion:
            engine.add_enchantment(minion.uid, cid, "Shado-Pan Rider", atk=4)
        return True

    if cid == "AT_030":  # Undercity Valiant
        if was_combo and target_id:
            engine.deal_damage(target_id, 1, source_seat=seat, source_name="Undercity Valiant", source_minion=minion)
        return True

    if cid == "AT_032":  # Shady Dealer
        if minion and any(m.uid != minion.uid and m.race == "PIRATE" for m in p.board):
            engine.add_enchantment(minion.uid, cid, "Shady Dealer", atk=1, hp=1)
        return True

    if cid == "AT_040":  # Wildwalker
        if target_id:
            engine.add_enchantment(target_id, cid, "Wildwalker", hp=3)
        return True

    if cid == "AT_042":  # Druid of the Saber
        if minion:
            if engine.has_fandral(seat):
                new_m = engine.transform_minion(minion.uid, "AT_042t2")
                if new_m:
                    engine.add_enchantment(new_m.uid, cid, "Druid of the Saber", add_keywords={"CHARGE"})
            else:
                form_id = "AT_042t" if choose == 0 else "AT_042t2"
                engine.transform_minion(minion.uid, form_id)
        return True

    if cid == "AT_046":  # Tuskarr Totemic
        idx = p.board.index(minion) + 1 if minion and minion in p.board else None
        engine.summon_minion(seat, engine.rng.choice(BASIC_TOTEMS), pos=idx)
        return True

    if cid == "AT_047":  # Draenei Totemcarver
        if minion:
            totems = sum(1 for m in p.board if m.uid != minion.uid and m.race == "TOTEM")
            if totems > 0:
                engine.add_enchantment(minion.uid, cid, "Draenei Totemcarver", atk=totems, hp=totems)
        return True

    if cid == "AT_049":  # Thunder Bluff Valiant
        _buff_friendly_totems(engine, seat)
        return True

    if cid == "AT_054":  # The Mistcaller
        helpers.buff_hand_minions(engine, seat, atk=1, hp=1)
        for ci in p.deck:
            if get_card(ci.card_id).type == "MINION":
                ci.attack_mod += 1
                ci.health_mod += 1
        return True

    if cid == "AT_057":  # Stablemaster
        if target_id:
            m = engine.find_minion(target_id)
            if m:
                m.immune_this_turn = True
        return True

    if cid == "AT_058":  # King's Elekk
        won, idx = helpers.reveal_joust(engine, seat, label="King's Elekk Joust")
        if won and idx is not None:
            drawn_ci = helpers.remove_from_deck(engine, seat, idx)
            engine.give_card_instance_to_hand(seat, drawn_ci, origin="deck")
        return True

    if cid == "AT_065":  # King's Defender
        if p.weapon and p.weapon.card_id == "AT_065":
            if any(m.has_keyword("TAUNT") for m in p.board):
                p.weapon.durability += 1
                p.weapon.max_durability += 1
        return True

    if cid == "AT_069":  # Sparring Partner
        if target_id:
            engine.add_enchantment(target_id, cid, "Sparring Partner", add_keywords={"TAUNT"})
        return True

    if cid == "AT_071":  # Alexstrasza's Champion
        if minion and engine.has_dragon_in_hand(seat):
            engine.add_enchantment(minion.uid, cid, "Alexstrasza's Champion", atk=1, add_keywords={"CHARGE"})
        return True

    if cid == "AT_072":  # Varian Wrynn
        for _ in range(3):
            if not p.deck:
                engine.draw_card(seat)
                continue
            top_card = get_card(p.deck[0].card_id)
            if top_card.type == "MINION" and len(p.board) < 7:
                helpers.summon_from_deck(engine, seat, 0)
            else:
                engine.draw_card(seat)
        return True

    if cid == "AT_077":  # Argent Lance
        if p.weapon and p.weapon.card_id == "AT_077":
            if helpers.joust(engine, seat):
                p.weapon.durability += 1
                p.weapon.max_durability += 1
        return True

    if cid == "AT_079":  # Mysterious Challenger
        active_ids = {s.card_id for s in p.secrets}
        while len(p.secrets) < 5:
            candidates = [
                i for i, ci in enumerate(p.deck)
                if get_card(ci.card_id).has_mechanic("SECRET") and ci.card_id not in active_ids
            ]
            if not candidates:
                break
            pick_idx = engine.rng.choice(candidates)
            sec_ci = helpers.remove_from_deck(engine, seat, pick_idx)
            if helpers.put_secret_into_play(engine, seat, sec_ci.card_id):
                active_ids.add(sec_ci.card_id)
        return True

    if cid == "AT_081":  # Eadric the Pure
        for m in list(opp.board):
            engine.add_enchantment(m.uid, cid, "Eadric the Pure", set_atk=1)
        return True

    if cid == "AT_084":  # Lance Carrier
        if target_id:
            engine.add_enchantment(target_id, cid, "Lance Carrier", atk=2)
        return True

    if cid == "AT_086":  # Saboteur
        opp.enemy_hero_power_cost_mod_next_turn += 5
        return True

    if cid == "AT_094":  # Flame Juggler
        cands = engine.living_enemy_characters(seat)
        if cands:
            engine.deal_damage(engine.rng.choice(cands), 1, source_seat=seat, source_name="Flame Juggler", source_minion=minion)
        return True

    if cid == "AT_096":  # Clockwork Knight
        if target_id:
            engine.add_enchantment(target_id, cid, "Clockwork Knight", atk=1, hp=1)
        return True

    if cid == "AT_098":  # Sideshow Spelleater
        p.hero.hero_power_id = opp.hero.hero_power_id
        p.hero.hero_power_used = False
        p.hero.hero_power_uses_this_turn = 0
        engine.add_log(f"{p.name} copied {opp.name}'s Hero Power ({get_card(p.hero.hero_power_id).name})!", seat=seat)
        return True

    if cid == "AT_103":  # North Sea Kraken
        if target_id:
            engine.deal_damage(target_id, 4, source_seat=seat, source_name="North Sea Kraken", source_minion=minion)
        return True

    if cid == "AT_104":  # Tuskarr Jouster
        if helpers.joust(engine, seat):
            engine.apply_heal(seat, f"hero_{seat}", 7)
        return True

    if cid == "AT_105":  # Injured Kvaldir
        if minion:
            engine.deal_damage(minion.uid, 3, source_seat=seat, source_name="Injured Kvaldir", source_minion=minion)
        return True

    if cid == "AT_106":  # Light's Champion
        if target_id and not target_id.startswith("hero_"):
            engine.silence_minion(target_id)
        return True

    if cid == "AT_108":  # Armored Warhorse
        if minion and helpers.joust(engine, seat):
            engine.add_enchantment(minion.uid, cid, "Armored Warhorse", add_keywords={"CHARGE"})
        return True

    if cid == "AT_112":  # Master Jouster
        if minion and helpers.joust(engine, seat):
            engine.add_enchantment(minion.uid, cid, "Master Jouster", add_keywords={"TAUNT", "DIVINE_SHIELD"})
        return True

    if cid == "AT_115":  # Fencing Coach
        p.next_hero_power_cost_mod -= 2
        return True

    if cid == "AT_117":  # Master of Ceremonies
        if minion and any(m.uid != minion.uid and m.spell_damage > 0 for m in p.board):
            engine.add_enchantment(minion.uid, cid, "Master of Ceremonies", atk=2, hp=2)
        return True

    if cid == "AT_118":  # Grand Crusader
        pool = helpers.collectible_pool(hero_class="PALADIN", include_neutral=False)
        if pool:
            engine.add_card_to_hand(seat, engine.rng.choice(pool))
        return True

    if cid == "AT_122":  # Gormok the Impaler
        if target_id and sum(1 for m in p.board if not minion or m.uid != minion.uid) >= 4:
            engine.deal_damage(target_id, 4, source_seat=seat, source_name="Gormok the Impaler", source_minion=minion)
        return True

    if cid == "AT_133":  # Gadgetzan Jouster
        if minion and helpers.joust(engine, seat):
            engine.add_enchantment(minion.uid, cid, "Gadgetzan Jouster", atk=1, hp=1)
        return True

    return False


# ---------------------------------------------------------------------------
# DEATHRATTLES (MINION & WEAPON)
# ---------------------------------------------------------------------------

def trigger_deathrattle(
    engine: GameEngine, seat: str, cid: str, orig_pos: int, dead_minion: Optional[Minion] = None
) -> bool:
    p = engine.state.players[seat]

    if cid == "AT_009":  # Rhonin
        for _ in range(3):
            engine.add_card_to_hand(seat, "VAN_EX1_277")
        return True

    if cid == "AT_019":  # Dreadsteed
        p.extra_flags["dreadsteed_eot"] = p.extra_flags.get("dreadsteed_eot", 0) + 1
        return True

    if cid == "AT_036":  # Anub'arak
        engine.summon_minion(seat, "AT_036t", pos=orig_pos)
        return True

    if cid == "AT_036t":  # Nerubian (from Anub'arak vs Beneath the Grounds)
        if dead_minion and dead_minion.extra_data.get("vanilla_nerubian"):
            return True
        engine.summon_minion(seat, "AT_036", pos=orig_pos)
        return True

    if cid == "AT_123":  # Chillmaw
        if engine.has_dragon_in_hand(seat):
            for s in ("p1", "p2"):
                for m in list(engine.state.players[s].board):
                    engine.deal_damage(m.uid, 3, source_seat=seat, source_name="Chillmaw")
        return True

    if cid == "AT_128":  # The Skeleton Knight
        if helpers.joust(engine, seat):
            engine.add_card_to_hand(seat, "AT_128")
        return True

    return False


def trigger_weapon_deathrattle(engine: GameEngine, seat: str, cid: str) -> bool:
    if cid == "AT_050":  # Charged Hammer
        p = engine.state.players[seat]
        p.hero.hero_power_id = "AT_050t"
        p.hero.hero_power_used = False
        p.hero.hero_power_uses_this_turn = 0
        engine.add_log(f"{p.name}'s Hero Power became Lightning Jolt!", seat=seat)
        return True
    return False


# ---------------------------------------------------------------------------
# HERO POWER OVERRIDES (Lightning Jolt, Fallen Hero, Wilfred Fizzlebang, Poisoned Blade)
# ---------------------------------------------------------------------------

def trigger_hero_power(engine: GameEngine, seat: str, hp_id: str, target_id: Optional[str]) -> bool:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    velen_mult = engine.velen_multiplier(seat)
    fallen_bonus = sum(1 for m in p.board if not m.silenced and m.card_id == "AT_003")
    has_wilfred = any(not m.silenced and m.card_id == "AT_027" for m in p.board)

    # Poisoned Blade: Rogue Hero Power gives +1 Attack instead of replacing it
    if hp_id in ("VAN_HERO_03bp", "AT_132_ROGUE") and p.weapon and p.weapon.card_id == "AT_034":
        p.weapon.attack_bonus += 1
        engine.recompute_auras()
        return True

    # Lightning Jolt (from Charged Hammer)
    if hp_id == "AT_050t":
        if target_id:
            engine.deal_damage(
                target_id,
                (2 + fallen_bonus) * velen_mult,
                source_seat=seat,
                source_name="Lightning Jolt",
            )
        return True

    # Warlock Hero Power with Wilfred Fizzlebang and/or Fallen Hero
    if hp_id == "VAN_HERO_07bp" and (fallen_bonus > 0 or has_wilfred):
        engine.deal_damage(
            f"hero_{seat}",
            (2 + fallen_bonus) * velen_mult,
            source_seat=seat,
            source_name="Life Tap",
        )
        drawn = engine.draw_card(seat)
        if has_wilfred and drawn:
            drawn.cost_mod = -get_card(drawn.card_id).cost
        return True

    if hp_id == "AT_132_WARLOCK" and has_wilfred:
        drawn = engine.draw_card(seat)
        if drawn:
            drawn.cost_mod = -get_card(drawn.card_id).cost
        return True

    # Damaging Hero Powers boosted by Fallen Hero
    if fallen_bonus > 0:
        if hp_id == "VAN_HERO_05bp":  # Steady Shot
            engine.deal_damage(f"hero_{opp_seat}", (2 + fallen_bonus) * velen_mult, source_seat=seat, source_name="Steady Shot")
            return True
        if hp_id == "AT_132_HUNTER":  # Ballista Shot
            engine.deal_damage(f"hero_{opp_seat}", (3 + fallen_bonus) * velen_mult, source_seat=seat, source_name="Ballista Shot")
            return True
        if hp_id == "VAN_HERO_08bp":  # Fireblast
            if target_id:
                engine.deal_damage(target_id, (1 + fallen_bonus) * velen_mult, source_seat=seat, source_name="Fireblast")
            return True
        if hp_id == "AT_132_MAGE":  # Fireblast Rank 2
            if target_id:
                engine.deal_damage(target_id, (2 + fallen_bonus) * velen_mult, source_seat=seat, source_name="Fireblast Rank 2")
            return True
        if hp_id == "EX1_625t":  # Mind Spike
            if target_id:
                engine.deal_damage(target_id, (2 + fallen_bonus) * velen_mult, source_seat=seat, source_name="Mind Spike")
            return True
        if hp_id == "EX1_625t2":  # Mind Shatter
            if target_id:
                engine.deal_damage(target_id, (3 + fallen_bonus) * velen_mult, source_seat=seat, source_name="Mind Shatter")
            return True
        if hp_id in ("VAN_HERO_09bp", "AT_132_PRIEST") and engine.has_auchenai(seat):
            base = 4 if hp_id == "AT_132_PRIEST" else 2
            if target_id:
                engine.deal_damage(target_id, (base + fallen_bonus) * velen_mult, source_seat=seat, source_name="Auchenai Soulpriest")
            return True

    return False


# ---------------------------------------------------------------------------
# INSPIRE
# ---------------------------------------------------------------------------

def on_inspire(engine: GameEngine, seat: str) -> None:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)

    # Poisoned Blade also gains +1 Attack from non-Rogue Hero Powers
    if p.weapon and p.weapon.card_id == "AT_034" and p.hero.hero_power_id not in ("VAN_HERO_03bp", "AT_132_ROGUE"):
        p.weapon.attack_bonus += 1

    for m in list(p.board):
        if m not in p.board or m.silenced:
            continue
        cid = m.card_id

        if cid == "AT_006":  # Dalaran Aspirant
            engine.add_enchantment(m.uid, cid, "Dalaran Aspirant", spell_damage=1)
        elif cid == "AT_012":  # Spawn of Shadows
            engine.deal_damage(f"hero_{seat}", 4, source_seat=seat, source_name="Spawn of Shadows", source_minion=m)
            engine.deal_damage(f"hero_{opp_seat}", 4, source_seat=seat, source_name="Spawn of Shadows", source_minion=m)
        elif cid == "AT_018":  # Confessor Paletress
            _summon_random_legendary(engine, seat)
        elif cid == "AT_023":  # Void Crusher
            for s in (seat, opp_seat):
                alive = [bm for bm in engine.state.players[s].board if bm.health > 0 and not bm.has_keyword("DORMANT")]
                if alive:
                    engine.destroy_minion(engine.rng.choice(alive).uid)
        elif cid == "AT_039":  # Savage Combatant
            p.hero.temp_attack += 2
        elif cid == "AT_049":  # Thunder Bluff Valiant
            _buff_friendly_totems(engine, seat)
        elif cid == "AT_059":  # Brave Archer
            if len(p.hand) == 0:
                engine.deal_damage(f"hero_{opp_seat}", 2, source_seat=seat, source_name="Brave Archer", source_minion=m)
        elif cid == "AT_066":  # Orgrimmar Aspirant
            if p.weapon:
                p.weapon.attack_bonus += 1
        elif cid == "AT_076":  # Murloc Knight
            pool = helpers.collectible_pool(card_type="MINION", race="MURLOC")
            if pool:
                engine.summon_minion(seat, engine.rng.choice(pool))
        elif cid == "AT_082":  # Lowly Squire
            engine.add_enchantment(m.uid, cid, "Lowly Squire", atk=1)
        elif cid == "AT_083":  # Dragonhawk Rider
            engine.add_enchantment(m.uid, cid, "Dragonhawk Rider", add_keywords={"WINDFURY"}, temp_until_eot=True)
        elif cid == "AT_089":  # Boneguard Lieutenant
            engine.add_enchantment(m.uid, cid, "Boneguard Lieutenant", hp=1)
        elif cid == "AT_090":  # Mukla's Champion
            for fm in list(p.board):
                if fm.uid != m.uid:
                    engine.add_enchantment(fm.uid, cid, "Mukla's Champion", atk=1, hp=1)
        elif cid == "AT_091":  # Tournament Medic
            engine.apply_heal(seat, f"hero_{seat}", 2)
        elif cid == "AT_099":  # Kodorider
            engine.summon_minion(seat, "AT_099t")
        elif cid == "AT_100":  # Silver Hand Regent
            engine.summon_minion(seat, "VAN_CS2_101t")
        elif cid == "AT_109":  # Argent Watchman
            engine.add_enchantment(m.uid, cid, "Argent Watchman", remove_keywords={"CANT_ATTACK"}, temp_until_eot=True)
        elif cid == "AT_110":  # Coliseum Manager
            if m in p.board:
                engine.bounce_minion(m)
        elif cid == "AT_113":  # Recruiter
            engine.add_card_to_hand(seat, "VAN_CS2_152")
        elif cid == "AT_119":  # Kvaldir Raider
            engine.add_enchantment(m.uid, cid, "Kvaldir Raider", atk=2, hp=2)
        elif cid == "AT_127":  # Nexus-Champion Saraad
            spells = helpers.collectible_pool(card_type="SPELL")
            if spells:
                engine.add_card_to_hand(seat, engine.rng.choice(spells))


# ---------------------------------------------------------------------------
# BOARD / TRIGGER / TURN HOOKS
# ---------------------------------------------------------------------------

def on_eot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    if minion.card_id == "AT_063t":  # Dreadscale
        opp_seat = engine.other_seat(seat)
        opp = engine.state.players[opp_seat]
        for tid in [f"hero_{opp_seat}"] + [em.uid for em in list(opp.board)]:
            engine.deal_damage(tid, 1, source_seat=seat, source_name="Dreadscale", source_minion=minion)


def on_eot_both(engine: GameEngine, active_seat: str) -> None:
    # Dreadsteed end-of-turn resummons
    for s in ("p1", "p2"):
        pl = engine.state.players[s]
        cnt = pl.extra_flags.pop("dreadsteed_eot", 0)
        for _ in range(cnt):
            engine.summon_minion(s, "AT_019")


def on_minion_summoned(engine: GameEngine, seat: str, minion: Minion) -> None:
    if minion.race == "BEAST":
        p = engine.state.players[seat]
        p.extra_flags["beasts_summoned"] = p.extra_flags.get("beasts_summoned", 0) + 1


def on_card_played(engine: GameEngine, seat: str, card: CardDef, ci: CardInstance) -> None:
    if card.has_mechanic("BATTLECRY"):
        for m in list(engine.state.players[seat].board):
            if not m.silenced and m.card_id == "AT_121":  # Crowd Favorite
                engine.add_enchantment(m.uid, "AT_121", "Crowd Favorite", atk=1, hp=1)


def on_spell_cast(engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]) -> None:
    p = engine.state.players[seat]

    # Lock and Load
    if p.lock_and_load_count > 0:
        pool = helpers.collectible_pool(hero_class="HUNTER", include_neutral=False)
        if pool:
            for _ in range(p.lock_and_load_count):
                engine.add_card_to_hand(seat, engine.rng.choice(pool))

    # Fjola Lightbane & Eydis Darkbane (whenever you target this minion with a spell)
    if target_id and not target_id.startswith("hero_"):
        m = engine.find_minion(target_id)
        if m and m.owner == seat and not m.silenced:
            if m.card_id == "AT_129":  # Fjola Lightbane
                engine.add_enchantment(m.uid, "AT_129", "Fjola Lightbane", add_keywords={"DIVINE_SHIELD"})
            elif m.card_id == "AT_131":  # Eydis Darkbane
                cands = engine.living_enemy_characters(seat)
                if cands:
                    engine.deal_damage(engine.rng.choice(cands), 3, source_seat=seat, source_name="Eydis Darkbane", source_minion=m)


def on_damage_minion(
    engine: GameEngine, m: Minion, amount: int, source_seat: Optional[str], source_minion: Optional[Minion]
) -> None:
    if amount <= 0:
        return
    # Wrathguard: whenever this minion takes damage, also deal that amount to your hero
    if not m.silenced and m.card_id == "AT_026":
        engine.deal_damage(
            f"hero_{m.owner}",
            amount,
            source_seat=source_seat,
            source_name="Wrathguard",
            source_minion=m,
        )
    # Acidmaw: whenever an enemy minion takes damage, destroy it
    opp_seat = engine.other_seat(m.owner)
    if any(not bm.silenced and bm.card_id == "AT_063" for bm in engine.state.players[opp_seat].board):
        engine.destroy_minion(m.uid)


def on_damage_hero(
    engine: GameEngine, target_seat: str, amount: int, source_seat: Optional[str], source_minion: Optional[Minion]
) -> None:
    if amount <= 0:
        return
    p = engine.state.players[target_seat]
    # Bolf Ramshield: whenever your hero takes damage, this minion takes it instead
    bolf = next((m for m in p.board if not m.silenced and m.card_id == "AT_124" and m.health > 0), None)
    if bolf is not None:
        hero = p.hero
        hp_restore = min(amount, max(0, hero.max_hp - hero.hp))
        hero.hp += hp_restore
        armor_restore = amount - hp_restore
        if armor_restore > 0:
            hero.armor += armor_restore
        engine.deal_damage(
            bolf.uid,
            amount,
            source_seat=source_seat,
            source_name="Bolf Ramshield",
            source_minion=source_minion,
        )


def on_heal(engine: GameEngine, caster_seat: str, target_id: str, amount: int, healed_minion: bool) -> None:
    for s in ("p1", "p2"):
        for bm in list(engine.state.players[s].board):
            if not bm.silenced and bm.card_id == "AT_011":  # Holy Champion
                engine.add_enchantment(bm.uid, "AT_011", "Holy Champion", atk=2)


def on_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> tuple[str, bool]:
    if not attacker_id.startswith("hero_"):
        atk_m = engine.find_minion(attacker_id)
        if atk_m:
            # Cutpurse: whenever this minion attacks a hero, add The Coin to your hand
            if target_id.startswith("hero_") and not atk_m.silenced and atk_m.card_id == "AT_031":
                engine.add_card_to_hand(seat, "GAME_005")
            # Power Word: Glory: whenever enchanted minion attacks, restore 4 Health to caster's hero
            for e in list(atk_m.enchantments):
                if e.source_card_id == "AT_013":
                    owner = "p1" if "(p1)" in e.source_name else "p2" if "(p2)" in e.source_name else seat
                    engine.apply_heal(owner, f"hero_{owner}", 4)
    return target_id, False


def on_after_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> None:
    # Magnataur Alpha: also damages minions adjacent to target
    if not attacker_id.startswith("hero_") and not target_id.startswith("hero_"):
        atk_m = engine.find_minion(attacker_id)
        def_m = engine.find_minion(target_id)
        if atk_m and not atk_m.silenced and atk_m.card_id == "AT_067" and def_m:
            opp_board = engine.state.players[def_m.owner].board
            if def_m in opp_board:
                idx = opp_board.index(def_m)
                adj = []
                if idx - 1 >= 0:
                    adj.append(opp_board[idx - 1].uid)
                if idx + 1 < len(opp_board):
                    adj.append(opp_board[idx + 1].uid)
                for aid in adj:
                    engine.deal_damage(aid, atk_m.attack, source_seat=seat, source_name="Magnataur Alpha", source_minion=atk_m)

    # Bear Trap: Secret: After your hero is attacked, summon a 3/3 Bear with Taunt
    def_seat = engine.other_seat(seat)
    if target_id == f"hero_{def_seat}":
        def_p = engine.state.players[def_seat]
        if len(def_p.board) < 7:
            for sec in list(def_p.secrets):
                if sec.card_id == "AT_060":
                    engine._reveal_secret(def_seat, sec)
                    engine.summon_minion(def_seat, "VAN_CS2_125")
                    break


def on_discard(engine: GameEngine, seat: str, ci: CardInstance) -> None:
    # Tiny Knight of Evil: whenever you discard a card, gain +2/+1
    for m in list(engine.state.players[seat].board):
        if not m.silenced and m.card_id == "AT_021":
            engine.add_enchantment(m.uid, "AT_021", "Tiny Knight of Evil", atk=2, hp=1)

    # Fist of Jaraxxus: when you discard this, deal 4 damage to a random enemy
    if ci.card_id == "AT_022":
        cands = engine.living_enemy_characters(seat)
        if cands:
            dmg = engine.calc_spell_damage(seat, 4)
            engine.deal_damage(engine.rng.choice(cands), dmg, source_seat=seat, source_name="Fist of Jaraxxus")


def on_draw(engine: GameEngine, seat: str, ci: CardInstance) -> bool:
    p = engine.state.players[seat]

    # Nerubian Ambush! (Casts When Drawn)
    if ci.card_id == "AT_035t":
        opp_seat = engine.other_seat(seat)
        _summon_vanilla_nerubian(engine, opp_seat)
        engine.add_log(
            f"Nerubian Ambush! Summoned a 4/4 Nerubian for {engine.state.players[opp_seat].name}.",
            seat=opp_seat,
        )
        return True

    # Shadowfiend: whenever you draw a card, reduce its Cost by (1)
    sf_cnt = sum(1 for m in p.board if not m.silenced and m.card_id == "AT_014")
    if sf_cnt > 0:
        ci.cost_mod -= sf_cnt

    # Sea Reaver: when you draw this, deal 1 damage to your minions
    if ci.card_id == "AT_130":
        for m in list(p.board):
            engine.deal_damage(m.uid, 1, source_seat=seat, source_name="Sea Reaver")
        engine.resolve_deaths()

    return False


# ---------------------------------------------------------------------------
# AURAS, COSTS, HERO POWER LIMITS, PLAYABILITY
# ---------------------------------------------------------------------------

def recompute_auras(engine: GameEngine) -> None:
    for s in ("p1", "p2"):
        pl = engine.state.players[s]
        board = pl.board

        # Fix durability on TGT weapons whose catalog durability=0 & health=durability,
        # and trigger Buccaneer (+1 Attack) the first time any newly equipped weapon is seen.
        if pl.weapon is not None:
            w = pl.weapon
            if not w.extra_data.get("tgt_init"):
                w.extra_data["tgt_init"] = True
                if w.card_id in TGT_WEAPONS_WITH_HEALTH_DURABILITY:
                    cdef = get_card(w.card_id)
                    if cdef.durability == 0 and cdef.health:
                        w.durability = cdef.health
                        w.max_durability = cdef.health
                buccaneers = sum(1 for m in board if not m.silenced and m.card_id == "AT_029")
                if buccaneers > 0:
                    w.attack_bonus += buccaneers

        # Dalaran Aspirant: inherent Spell Damage +1 (catalog has spell_damage=0)
        for m in board:
            if not m.silenced and m.card_id == "AT_006":
                m.spell_damage += 1

        # Warhorse Trainer: Your Silver Hand Recruits have +2 Attack and Taunt
        trainers = sum(1 for m in board if not m.silenced and m.card_id == "AT_075")
        if trainers > 0:
            bonus = 2 * trainers
            for m in board:
                if m.card_id == "VAN_CS2_101t":
                    m.aura_atk_bonus += bonus
                    m.attack = max(0, m.attack + bonus)
                    m.keywords.add("TAUNT")


def get_card_cost(engine: GameEngine, seat: str, ci: CardInstance, cost: int) -> int:
    p = engine.state.players[seat]
    cid = ci.card_id
    card = get_card(cid)

    if cid == "AT_041":  # Knight of the Wild
        cost -= p.extra_flags.get("beasts_summoned", 0)
    elif cid == "AT_070":  # Skycap'n Kragg
        cost -= sum(1 for m in p.board if m.race == "PIRATE")
    elif cid == "AT_120":  # Frost Giant
        cost -= p.hero_power_uses_total

    # Aviana: Your minions cost (1)
    if card.type == "MINION":
        if any(not m.silenced and m.card_id == "AT_045" for m in p.board):
            cost = 1

    return cost


def get_hero_power_cost(engine: GameEngine, seat: str, cost: int) -> int:
    p = engine.state.players[seat]
    if any(not m.silenced and m.card_id == "AT_085" for m in p.board):  # Maiden of the Lake
        cost = 1 + p.next_hero_power_cost_mod + p.enemy_hero_power_cost_mod_this_turn
    return cost


def get_hero_power_max_uses(engine: GameEngine, seat: str) -> int:
    board = engine.state.players[seat].board
    if any(not m.silenced and m.card_id == "AT_008" for m in board):  # Coldarra Drake
        return 999
    if any(not m.silenced and m.card_id == "AT_080" for m in board):  # Garrison Commander
        return 2
    return 1


def can_play_card(engine: GameEngine, seat: str, ci: CardInstance) -> Optional[tuple[bool, str]]:
    p = engine.state.players[seat]
    opp = engine.state.players[engine.other_seat(seat)]
    if ci.card_id == "AT_025" and len(opp.board) < 2:  # Dark Bargain
        return False, "Requires at least 2 enemy minions."
    if ci.card_id == "AT_062" and len(p.board) >= 7:  # Ball of Spiders
        return False, "Your board is full."
    return None


# ---------------------------------------------------------------------------
# SECRETS (Effigy, Competitive Spirit; Bear Trap is in on_after_attack)
# ---------------------------------------------------------------------------

def trigger_secrets_on_death(engine: GameEngine, def_seat: str, dead_m: Minion, orig_pos: int) -> None:
    p = engine.state.players[def_seat]
    if len(p.board) >= 7:
        return
    for sec in list(p.secrets):
        if sec.card_id == "AT_002":  # Effigy
            engine._reveal_secret(def_seat, sec)
            cost = get_card(dead_m.card_id).cost
            pool = helpers.collectible_pool(card_type="MINION", cost=cost)
            if pool:
                engine.summon_minion(def_seat, engine.rng.choice(pool), pos=orig_pos)
            break


def trigger_secrets_on_sot(engine: GameEngine, seat: str) -> None:
    p = engine.state.players[seat]
    if not p.board:
        return
    for sec in list(p.secrets):
        if sec.card_id == "AT_073":  # Competitive Spirit
            engine._reveal_secret(seat, sec)
            for m in list(p.board):
                engine.add_enchantment(m.uid, "AT_073", "Competitive Spirit", atk=1, hp=1)
            break
