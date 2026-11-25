"""Goblins vs Gnomes (GVG) expansion card implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.catalog import COLLECTIBLE_CARDS, CardDef, get_card
from engine.expansions import helpers
from engine.models import CardInstance, ChooseOption, Minion, SecretInstance, Weapon

if TYPE_CHECKING:
    from engine.game import GameEngine

SPARE_PARTS: tuple[str, ...] = (
    "PART_001",
    "PART_002",
    "PART_003",
    "PART_004",
    "PART_005",
    "PART_006",
    "PART_007",
)

# Authentic Hearthstone Fire-school spells available in the catalog (for Soot Spewer).
FIRE_SPELLS: tuple[str, ...] = (
    "VAN_CS2_029",  # Fireball
    "VAN_CS2_032",  # Flamestrike
    "VAN_EX1_279",  # Pyroblast
    "GVG_001",      # Flamecannon
    "BRM_003",      # Dragon's Breath
    "AT_001",       # Flame Lance
    "LOE_002",      # Forgotten Torch
    "OG_086",       # Forbidden Flame
    "KAR_076",      # Firelands Portal
    "CFM_065",      # Volcanic Potion
    "UNG_018",      # Flame Geyser
    "UNG_948",      # Molten Reflection
    "UNG_955",      # Meteor
    "VAN_EX1_537",  # Explosive Shot
    "VAN_EX1_610",  # Explosive Trap
    "VAN_EX1_241",  # Lava Burst
    "BRM_011",      # Lava Shock
    "UNG_025",      # Volcano
    "CFM_662",      # Dragonfire Potion
    "VAN_EX1_303",  # Shadowflame
    "VAN_CS2_062",  # Hellfire
    "VAN_EX1_308",  # Soulfire
    "VAN_EX1_596",  # Demonfire
    "CFM_094",      # Felfire Potion
)

# Real Hearthstone durabilities for GVG weapons whose catalog durability field is 0.
_GVG_WEAPON_DURABILITY: dict[str, int] = {
    "GVG_024": 3,  # Cogmaster's Wrench (1/3)
    "GVG_043": 2,  # Glaivezooka (2/2)
    "GVG_054": 2,  # Ogre Warmaul (4/2)
    "GVG_059": 3,  # Coghammer (2/3)
}


def _fix_gvg_weapon_durability(weapon: Optional[Weapon]) -> None:
    if not weapon or weapon.extra_data.get("gvg_dur_fixed"):
        return
    real_dur = _GVG_WEAPON_DURABILITY.get(weapon.card_id)
    if real_dur and get_card(weapon.card_id).durability == 0:
        weapon.durability = real_dur
        weapon.max_durability = real_dur
    weapon.extra_data["gvg_dur_fixed"] = True


def _has_deathrattle(m: Minion) -> bool:
    from engine.effects import DEATHRATTLE_CARDS as ALL_DR_CARDS

    if m.silenced or m.has_keyword("DORMANT"):
        return False
    return m.card_id in ALL_DR_CARDS or any(e.extra_deathrattle for e in m.enchantments)


def _check_siege_engine_armor(engine: GameEngine) -> None:
    """Trigger Siege Engine (GVG_086) whenever its owner's Armor increases."""
    for s in ("p1", "p2"):
        pl = engine.state.players[s]
        cur_armor = pl.hero.armor
        for m in list(pl.board):
            if m.card_id != "GVG_086":
                continue
            prev_armor = m.extra_data.get("siege_last_armor")
            if prev_armor is None:
                m.extra_data["siege_last_armor"] = cur_armor
                continue
            if cur_armor != prev_armor:
                m.extra_data["siege_last_armor"] = cur_armor
                if cur_armor > prev_armor and not m.silenced and not m.has_keyword("DORMANT"):
                    engine.add_enchantment(m.uid, "GVG_086", "Siege Engine", atk=1)


# ---------------------------------------------------------------------------
# REGISTRIES
# ---------------------------------------------------------------------------

TARGET_RULES: dict[str, str] = {
    # Spells
    "GVG_012": "ANY",            # Light of the Naaru
    "GVG_019": "MINION",         # Demonheart
    "GVG_031": "ENEMY_MINION",   # Recycle
    "GVG_041a": "MINION",        # Call the Guardians (Dark Wispers token)
    "GVG_052": "MINION",         # Crush
    "GVG_073": "MINION",         # Cobra Shot
    # Targeted Battlecries
    "GVG_011": "MINION",         # Shrinkmeister
    "GVG_014": "MINION",         # Vol'jin
    "GVG_055": "FRIENDLY_MECH",  # Screwjank Clunker
    "GVG_083": "FRIENDLY_MECH",  # Upgraded Repair Bot
    "GVG_108": "FRIENDLY_MINION",  # Recombobulator
    "GVG_120": "BEAST",          # Hemet Nesingwary
}

CHOOSE_ONE_OPTIONS: dict[str, tuple[ChooseOption, ...]] = {
    "GVG_030": (  # Anodized Robo Cub
        ChooseOption("Attack Mode", "+1 Attack.", "NONE"),
        ChooseOption("Tank Mode", "+1 Health.", "NONE"),
    ),
    "GVG_032": (  # Grove Tender
        ChooseOption("Gift of Mana", "Give each player a Mana Crystal.", "NONE"),
        ChooseOption("Gift of Cards", "Each player draws a card.", "NONE"),
    ),
    "GVG_041": (  # Dark Wispers
        ChooseOption("Nature's Defense", "Summon 5 Wisps.", "NONE"),
        ChooseOption("Call the Guardians", "Give a minion +5/+5 and Taunt.", "MINION"),
    ),
}

PURE_KEYWORD_CARDS: set[str] = {
    "GVG_018",  # Queen of Pain (Lifesteal)
    "GVG_064",  # Puddlestomper (vanilla Murloc)
    "GVG_065",  # Ogre Brute (Forgetful — native in game.py)
    "GVG_066",  # Dunemaul Shaman (Windfury, Overload, Forgetful)
    "GVG_070",  # Salty Dog (vanilla Pirate)
    "GVG_071",  # Lost Tallstrider (vanilla Beast)
    "GVG_079",  # Force-Tank MAX (Divine Shield)
    "GVG_081",  # Gilblin Stalker (Stealth)
    "GVG_084",  # Flying Machine (Windfury)
    "GVG_088",  # Ogre Ninja (Stealth, Forgetful)
    "GVG_091",  # Arcane Nullifier X-21 (Taunt, Elusive)
    "GVG_093",  # Target Dummy (Taunt)
    "GVG_098",  # Gnomeregan Infantry (Charge, Taunt)
    "GVG_109",  # Mini-Mage (Stealth, Spell Damage +1)
}

COMBO_ONLY_TARGET_CARDS: set[str] = set()
DRAGON_ONLY_TARGET_CARDS: set[str] = set()
CONDITIONAL_TARGET_RULES: dict = {}

DEATHRATTLE_CARDS: set[str] = {
    "GVG_035",  # Malorne
    "GVG_056",  # Iron Juggernaut
    "GVG_078",  # Mechanical Yeti
    "GVG_105",  # Piloted Sky Golem
    "GVG_114",  # Sneed's Old Shredder
    "GVG_115",  # Toshley
}

SECRET_CARDS: set[str] = set()

AURA_CARDS: set[str] = {
    "GVG_021",  # Mal'Ganis
    "GVG_024",  # Cogmaster's Wrench
    "GVG_046",  # King of Beasts
    "GVG_051",  # Warbot
    "GVG_087",  # Steamwheedle Sniper (native in game.py)
    "GVG_095",  # Goblin Sapper
    "GVG_112",  # Mogor the Ogre (native in game.py)
    "GVG_121",  # Clockwork Giant
    "GVG_122",  # Wee Spellstopper
}


# ---------------------------------------------------------------------------
# PLAYABILITY & COST HOOKS
# ---------------------------------------------------------------------------

def can_play_card(engine: GameEngine, seat: str, ci: CardInstance) -> Optional[tuple[bool, str]]:
    cid = ci.card_id
    opp = engine.state.players[engine.other_seat(seat)]
    if cid in ("GVG_001", "GVG_047"):  # Flamecannon / Sabotage
        if not any(not m.has_keyword("DORMANT") for m in opp.board):
            return False, "Requires an enemy minion."
    elif cid == "GVG_050":  # Bouncing Blade
        if not any(
            not m.has_keyword("DORMANT")
            for s in ("p1", "p2")
            for m in engine.state.players[s].board
        ):
            return False, "Requires a minion on the battlefield."
    return None


def get_card_cost(engine: GameEngine, seat: str, ci: CardInstance, cost: int) -> int:
    cid = ci.card_id
    if cid == "GVG_052":  # Crush
        if any(m.damaged for m in engine.state.players[seat].board):
            cost -= 4
    elif cid == "GVG_121":  # Clockwork Giant
        opp = engine.state.players[engine.other_seat(seat)]
        cost -= len(opp.hand)
    return cost


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

    if cid == "GVG_001":  # Flamecannon
        cands = [m for m in opp.board if m.health > 0 and not m.has_keyword("DORMANT")]
        if cands:
            engine.deal_damage(engine.rng.choice(cands).uid, sd(4), source_seat=seat, source_name="Flamecannon")
        return True

    if cid == "GVG_005":  # Echo of Medivh
        for m in list(p.board):
            if not m.has_keyword("DORMANT"):
                engine.add_card_to_hand(seat, m.card_id)
        return True

    if cid == "GVG_012":  # Light of the Naaru
        if target_id:
            heal_amt = engine.calc_spell_healing(seat, 3)
            engine.apply_heal(seat, target_id, heal_amt, from_spell_or_power=True)
            if target_id.startswith("hero_"):
                th = engine.state.players[target_id.split("_")[1]].hero
                still_damaged = th.hp > 0 and th.hp < th.max_hp
            else:
                tm = engine.find_minion(target_id)
                still_damaged = bool(tm and tm.health > 0 and tm.damaged)
            if still_damaged:
                engine.summon_minion(seat, "VAN_EX1_001")  # Lightwarden
        return True

    if cid == "GVG_017":  # Call Pet
        drawn = engine.draw_card(seat)
        if drawn and get_card(drawn.card_id).race == "BEAST":
            drawn.cost_mod -= 4
        return True

    if cid == "GVG_019":  # Demonheart
        if target_id:
            tm = engine.find_minion(target_id)
            if tm:
                if tm.owner == seat and tm.race == "DEMON":
                    engine.add_enchantment(tm.uid, cid, "Demonheart", atk=5, hp=5)
                else:
                    engine.deal_damage(tm.uid, sd(5), source_seat=seat, source_name="Demonheart")
        return True

    if cid == "GVG_022":  # Tinker's Sharpsword Oil
        if p.weapon:
            p.weapon.attack_bonus += 3
            engine.recompute_auras()
        if was_combo:
            cands = [m for m in p.board if not m.has_keyword("DORMANT")]
            if cands:
                engine.add_enchantment(
                    engine.rng.choice(cands).uid, cid, "Tinker's Sharpsword Oil", atk=3
                )
        return True

    if cid == "GVG_026":  # Feign Death
        for m in list(p.board):
            if m in p.board and _has_deathrattle(m):
                helpers.trigger_minion_deathrattle(engine, m)
        return True

    if cid == "GVG_028t" or cid == "GVG_COIN":  # Gallywix's Coin / The Coin
        p.mana = min(10, p.mana + 1)
        return True

    if cid == "GVG_029":  # Ancestor's Call
        for s in (seat, opp_seat):
            pl = engine.state.players[s]
            if len(pl.board) >= 7:
                continue
            min_indices = [i for i, hci in enumerate(pl.hand) if get_card(hci.card_id).type == "MINION"]
            if min_indices:
                pick_idx = engine.rng.choice(min_indices)
                engine.summon_minion_from_hand(s, pick_idx, len(pl.board))
        return True

    if cid == "GVG_031":  # Recycle
        if target_id:
            tm = engine.find_minion(target_id)
            if tm:
                tm_owner = tm.owner
                tm_cid = tm.card_id
                engine.remove_minion(tm)
                engine.shuffle_into_deck(tm_owner, tm_cid)
        return True

    if cid == "GVG_033":  # Tree of Life
        for s in ("p1", "p2"):
            pl = engine.state.players[s]
            engine.apply_heal(seat, f"hero_{s}", pl.hero.max_hp, from_spell_or_power=True)
            for m in list(pl.board):
                if not m.has_keyword("DORMANT"):
                    engine.apply_heal(seat, m.uid, m.max_health, from_spell_or_power=True)
        return True

    if cid == "GVG_041":  # Dark Wispers
        both = engine.has_fandral(seat)
        if both or choose == 0:
            for _ in range(5):
                engine.summon_minion(seat, "VAN_CS2_231")  # Wisp
        if both or choose == 1:
            buff_uid = target_id
            if not buff_uid and both:
                cands = [m for m in p.board if not m.has_keyword("DORMANT")]
                if cands:
                    buff_uid = engine.rng.choice(cands).uid
            if buff_uid:
                engine.add_enchantment(
                    buff_uid, cid, "Dark Wispers", atk=5, hp=5, add_keywords={"TAUNT"}
                )
        return True

    if cid == "GVG_041a":  # Call the Guardians (token)
        if target_id:
            engine.add_enchantment(
                target_id, cid, "Call the Guardians", atk=5, hp=5, add_keywords={"TAUNT"}
            )
        return True

    if cid == "GVG_041b":  # Nature's Defense (token)
        for _ in range(5):
            engine.summon_minion(seat, "VAN_CS2_231")
        return True

    if cid == "GVG_047":  # Sabotage
        cands = [m for m in opp.board if m.health > 0 and not m.has_keyword("DORMANT")]
        if cands:
            engine.destroy_minion(engine.rng.choice(cands).uid)
        if was_combo and opp.weapon:
            engine.destroy_weapon(opp_seat)
        return True

    if cid == "GVG_050":  # Bouncing Blade
        dmg = sd(1)
        for _ in range(80):
            cands = [
                m
                for s in ("p1", "p2")
                for m in engine.state.players[s].board
                if m.health > 0
                and not m.has_keyword("DORMANT")
                and not m.immune_this_turn
                and not (engine.state.players[s].commanding_shout_active and m.health <= 1)
            ]
            if not cands:
                break
            tgt = engine.rng.choice(cands)
            engine.deal_damage(tgt.uid, dmg, source_seat=seat, source_name="Bouncing Blade")
            if any(m.health <= 0 for s in ("p1", "p2") for m in engine.state.players[s].board):
                break
        return True

    if cid == "GVG_052":  # Crush
        if target_id:
            engine.destroy_minion(target_id)
        return True

    if cid == "GVG_056t":  # Burrowing Mine (if cast directly from hand)
        engine.deal_damage(f"hero_{seat}", 10, source_seat=seat, source_name="Burrowing Mine")
        return True

    if cid == "GVG_057":  # Seal of Light
        engine.apply_heal(seat, f"hero_{seat}", engine.calc_spell_healing(seat, 4), from_spell_or_power=True)
        p.hero.temp_attack += 2
        engine.recompute_auras()
        return True

    if cid == "GVG_073":  # Cobra Shot
        dmg = sd(3)
        if target_id:
            engine.deal_damage(target_id, dmg, source_seat=seat, source_name="Cobra Shot")
        engine.deal_damage(f"hero_{opp_seat}", dmg, source_seat=seat, source_name="Cobra Shot")
        return True

    return False


# ---------------------------------------------------------------------------
# BATTLECRIES & CHOOSE ONE MINIONS & WEAPONS
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

    # Fix 0-durability catalog values on GVG weapons when equipped
    if cid in _GVG_WEAPON_DURABILITY and p.weapon and p.weapon.card_id == cid:
        _fix_gvg_weapon_durability(p.weapon)

    if cid == "GVG_009":  # Shadowbomber
        engine.deal_damage("hero_p1", 3, source_seat=seat, source_name="Shadowbomber", source_minion=minion)
        engine.deal_damage("hero_p2", 3, source_seat=seat, source_name="Shadowbomber", source_minion=minion)
        return True

    if cid == "GVG_011":  # Shrinkmeister
        if target_id:
            engine.add_enchantment(target_id, cid, "Shrinkmeister", atk=-3, temp_until_eot=True)
        return True

    if cid == "GVG_014":  # Vol'jin
        if minion and target_id and target_id != minion.uid:
            tm = engine.find_minion(target_id)
            if tm and engine.find_minion(minion.uid):
                my_hp = max(1, minion.health)
                their_hp = max(1, tm.health)
                engine.add_enchantment(minion.uid, cid, "Vol'jin", set_hp=their_hp)
                engine.add_enchantment(tm.uid, cid, "Vol'jin", set_hp=my_hp)
        return True

    if cid == "GVG_023":  # Goblin Auto-Barber
        if p.weapon:
            p.weapon.attack_bonus += 1
            engine.recompute_auras()
        return True

    if cid in ("GVG_024", "GVG_054"):  # Cogmaster's Wrench / Ogre Warmaul (durability fixed above)
        engine.recompute_auras()
        return True

    if cid == "GVG_030":  # Anodized Robo Cub
        if minion and engine.find_minion(minion.uid):
            both = engine.has_fandral(seat)
            if both:
                engine.add_enchantment(minion.uid, cid, "Anodized Robo Cub", atk=1, hp=1)
            elif choose == 0:
                engine.add_enchantment(minion.uid, cid, "Attack Mode", atk=1)
            else:
                engine.add_enchantment(minion.uid, cid, "Tank Mode", hp=1)
        return True

    if cid == "GVG_032":  # Grove Tender
        both = engine.has_fandral(seat)
        if both or choose == 0:
            for s in (seat, opp_seat):
                pl = engine.state.players[s]
                if pl.max_mana < 10:
                    pl.max_mana += 1
                    pl.mana = min(10, pl.mana + 1)
        if both or choose == 1:
            engine.draw_card(seat)
            engine.draw_card(opp_seat)
        return True

    if cid == "GVG_042":  # Neptulon
        murlocs = helpers.collectible_pool(card_type="MINION", race="MURLOC")
        if murlocs:
            for _ in range(4):
                engine.add_card_to_hand(seat, engine.rng.choice(murlocs))
        return True

    if cid == "GVG_043":  # Glaivezooka
        cands = [m for m in p.board if not m.has_keyword("DORMANT")]
        if cands:
            engine.add_enchantment(engine.rng.choice(cands).uid, cid, "Glaivezooka", atk=1)
        return True

    if cid == "GVG_048":  # Metaltooth Leaper
        for m in list(p.board):
            if (not minion or m.uid != minion.uid) and m.race == "MECHANICAL" and not m.has_keyword("DORMANT"):
                engine.add_enchantment(m.uid, cid, "Metaltooth Leaper", atk=2)
        return True

    if cid == "GVG_055":  # Screwjank Clunker
        if target_id:
            engine.add_enchantment(target_id, cid, "Screwjank Clunker", atk=2, hp=2)
        return True

    if cid == "GVG_056":  # Iron Juggernaut
        engine.shuffle_into_deck(opp_seat, "GVG_056t")
        return True

    if cid == "GVG_059":  # Coghammer
        cands = [m for m in p.board if not m.has_keyword("DORMANT")]
        if cands:
            engine.add_enchantment(
                engine.rng.choice(cands).uid,
                cid,
                "Coghammer",
                add_keywords={"DIVINE_SHIELD", "TAUNT"},
            )
        return True

    if cid == "GVG_060":  # Quartermaster
        for m in list(p.board):
            if m.card_id == "VAN_CS2_101t":
                engine.add_enchantment(m.uid, cid, "Quartermaster", atk=2, hp=2)
        return True

    if cid == "GVG_074":  # Kezan Mystic
        if opp.secrets:
            stealable = [
                sec for sec in opp.secrets if not any(s.card_id == sec.card_id for s in p.secrets)
            ]
            sec = engine.rng.choice(stealable or opp.secrets)
            opp.secrets.remove(sec)
            engine.emit("secret_destroy", seat=opp_seat, uid=sec.uid)
            if helpers.put_secret_into_play(engine, seat, sec.card_id):
                engine.add_log(f"Kezan Mystic stole an enemy Secret!", seat=seat)
            else:
                engine.add_log(f"Kezan Mystic destroyed a duplicate enemy Secret!", seat=seat)
        return True

    if cid == "GVG_080":  # Druid of the Fang
        if minion and engine.find_minion(minion.uid):
            has_beast = any(
                bm.uid != minion.uid and bm.race == "BEAST" and not bm.has_keyword("DORMANT")
                for bm in p.board
            )
            if has_beast:
                engine.transform_minion(minion.uid, "GVG_080t")
        return True

    if cid == "GVG_083":  # Upgraded Repair Bot
        if target_id:
            engine.add_enchantment(target_id, cid, "Upgraded Repair Bot", hp=4)
        return True

    if cid == "GVG_090":  # Madder Bomber
        for _ in range(6):
            cands: list[str] = []
            for s in ("p1", "p2"):
                pl = engine.state.players[s]
                if pl.hero.hp > 0:
                    cands.append(f"hero_{s}")
                for bm in pl.board:
                    if bm.health > 0 and (not minion or bm.uid != minion.uid) and not bm.has_keyword("DORMANT"):
                        cands.append(bm.uid)
            if not cands:
                break
            engine.deal_damage(
                engine.rng.choice(cands), 1, source_seat=seat, source_name="Madder Bomber", source_minion=minion
            )
        return True

    if cid == "GVG_092":  # Gnomish Experimenter
        drawn = engine.draw_card(seat)
        if drawn and drawn in p.hand and get_card(drawn.card_id).type == "MINION":
            idx = p.hand.index(drawn)
            helpers.remove_from_hand(engine, seat, idx)
            engine.add_card_to_hand(seat, "GVG_092t")
            engine.add_log("Gnomish Experimenter transformed the drawn minion into a Chicken!", seat=seat)
        return True

    if cid == "GVG_097":  # Lil' Exorcist
        if minion and engine.find_minion(minion.uid):
            cnt = sum(1 for em in opp.board if _has_deathrattle(em))
            if cnt > 0:
                engine.add_enchantment(minion.uid, cid, "Lil' Exorcist", atk=cnt, hp=cnt)
        return True

    if cid == "GVG_099":  # Bomb Lobber
        cands = [m for m in opp.board if m.health > 0 and not m.has_keyword("DORMANT")]
        if cands:
            engine.deal_damage(
                engine.rng.choice(cands).uid, 4, source_seat=seat, source_name="Bomb Lobber", source_minion=minion
            )
        return True

    if cid == "GVG_101":  # Scarlet Purifier
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                if _has_deathrattle(m):
                    engine.deal_damage(m.uid, 2, source_seat=seat, source_name="Scarlet Purifier", source_minion=minion)
        return True

    if cid == "GVG_102":  # Tinkertown Technician
        if minion and engine.find_minion(minion.uid) and engine.has_mech_on_board(seat, exclude_uid=minion.uid):
            engine.add_enchantment(minion.uid, cid, "Tinkertown Technician", atk=1, hp=1)
            engine.add_card_to_hand(seat, engine.rng.choice(SPARE_PARTS))
        return True

    if cid == "GVG_107":  # Enhance-o Mechano
        for m in list(p.board):
            if (not minion or m.uid != minion.uid) and not m.has_keyword("DORMANT"):
                kw = engine.rng.choice(["WINDFURY", "TAUNT", "DIVINE_SHIELD"])
                engine.add_enchantment(m.uid, cid, "Enhance-o Mechano", add_keywords={kw})
        return True

    if cid == "GVG_108":  # Recombobulator
        if target_id and (not minion or target_id != minion.uid):
            tm = engine.find_minion(target_id)
            if tm:
                helpers.evolve_minion(engine, tm, delta=0)
        return True

    if cid == "GVG_115":  # Toshley
        engine.add_card_to_hand(seat, engine.rng.choice(SPARE_PARTS))
        return True

    if cid == "GVG_119":  # Blingtron 3000
        weapons = helpers.collectible_pool(card_type="WEAPON")
        if weapons:
            for s in (seat, opp_seat):
                wid = engine.rng.choice(weapons)
                engine.equip_weapon(s, wid)
                _fix_gvg_weapon_durability(engine.state.players[s].weapon)
        return True

    if cid == "GVG_120":  # Hemet Nesingwary
        if target_id:
            engine.destroy_minion(target_id)
        return True

    if cid == "GVG_123":  # Soot Spewer
        if minion and engine.has_mech_on_board(seat, exclude_uid=minion.uid):
            hero_cls = p.hero.card_class
            class_fire = [
                fid for fid in FIRE_SPELLS if fid in COLLECTIBLE_CARDS and COLLECTIBLE_CARDS[fid].allowed_for_class(hero_cls)
            ]
            pool = class_fire or [fid for fid in FIRE_SPELLS if fid in COLLECTIBLE_CARDS]
            if pool:
                engine.add_card_to_hand(seat, engine.rng.choice(pool))
        return True

    return False


# ---------------------------------------------------------------------------
# DEATHRATTLES
# ---------------------------------------------------------------------------

def trigger_deathrattle(
    engine: GameEngine, seat: str, cid: str, orig_pos: int, dead_minion: Optional[Minion] = None
) -> bool:
    opp_seat = engine.other_seat(seat)

    if cid == "GVG_035":  # Malorne: Go Dormant. Revive after 2 friendly Beasts die.
        dormant_m = engine.summon_minion(seat, "GVG_035", pos=orig_pos, trigger_summon=False)
        if dormant_m:
            dormant_m.extra_data["malorne_dormant"] = 2
            engine.add_enchantment(dormant_m.uid, "GVG_035", "Dormant", add_keywords={"DORMANT"})
            engine.add_log("Malorne went Dormant! Revives after 2 friendly Beasts die.", seat=seat)
        return True

    if cid == "GVG_056":  # Iron Juggernaut
        engine.shuffle_into_deck(opp_seat, "GVG_056t")
        return True

    if cid == "GVG_078":  # Mechanical Yeti
        engine.add_card_to_hand(seat, engine.rng.choice(SPARE_PARTS))
        engine.add_card_to_hand(opp_seat, engine.rng.choice(SPARE_PARTS))
        return True

    if cid == "GVG_105":  # Piloted Sky Golem
        pool = helpers.collectible_pool(card_type="MINION", cost=4)
        if pool:
            engine.summon_minion(seat, engine.rng.choice(pool), pos=orig_pos)
        return True

    if cid == "GVG_114":  # Sneed's Old Shredder
        pool = helpers.collectible_pool(card_type="MINION", rarity="LEGENDARY")
        if pool:
            engine.summon_minion(seat, engine.rng.choice(pool), pos=orig_pos)
        return True

    if cid == "GVG_115":  # Toshley
        engine.add_card_to_hand(seat, engine.rng.choice(SPARE_PARTS))
        return True

    return False


# ---------------------------------------------------------------------------
# BOARD & TURN TRIGGERS
# ---------------------------------------------------------------------------

def on_start_turn(engine: GameEngine, seat: str) -> None:
    # Micro Machine: At the start of each turn, gain +1 Attack.
    for s in ("p1", "p2"):
        for m in list(engine.state.players[s].board):
            if not m.silenced and m.card_id == "GVG_103":
                engine.add_enchantment(m.uid, "GVG_103", "Micro Machine", atk=1)
    _check_siege_engine_armor(engine)


def on_sot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    if minion.silenced:
        return
    if minion.card_id == "GVG_111":  # Mimiron's Head
        p = engine.state.players[seat]
        mechs = [bm for bm in list(p.board) if bm.race == "MECHANICAL" and not bm.has_keyword("DORMANT")]
        if len(mechs) >= 3:
            engine.add_log("Mimiron's Head destroys all your Mechs and forms V-07-TR-0N!", seat=seat)
            for bm in mechs:
                engine.destroy_minion(bm.uid)
            engine.resolve_deaths()
            engine.summon_minion(seat, "GVG_111t")


def on_eot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    if minion.silenced:
        return
    cid = minion.card_id
    p = engine.state.players[seat]

    if cid == "GVG_020":  # Fel Cannon
        cands = [
            bm
            for s in ("p1", "p2")
            for bm in engine.state.players[s].board
            if bm.race != "MECHANICAL" and bm.health > 0 and not bm.has_keyword("DORMANT")
        ]
        if cands:
            engine.deal_damage(
                engine.rng.choice(cands).uid, 2, source_seat=seat, source_name="Fel Cannon", source_minion=minion
            )
    elif cid == "GVG_027":  # Iron Sensei
        others = [
            fm
            for fm in p.board
            if fm.uid != minion.uid and fm.race == "MECHANICAL" and not fm.has_keyword("DORMANT")
        ]
        if others:
            engine.add_enchantment(engine.rng.choice(others).uid, cid, "Iron Sensei", atk=2, hp=2)
    elif cid == "GVG_039":  # Vitality Totem
        engine.apply_heal(seat, f"hero_{seat}", 4)
    elif cid == "GVG_089":  # Illuminator
        if p.secrets:
            engine.apply_heal(seat, f"hero_{seat}", 4)


def on_eot_both(engine: GameEngine, active_seat: str) -> None:
    # Anima Golem: At the end of each turn, destroy this minion if it's your only one.
    for s in ("p1", "p2"):
        board = engine.state.players[s].board
        for m in list(board):
            if not m.silenced and m.card_id == "GVG_077":
                others = [bm for bm in board if bm.uid != m.uid and bm.health > 0]
                if not others:
                    engine.destroy_minion(m.uid)

    # Jeeves: At the end of each player's turn, that player draws until they have 3 cards.
    active_p = engine.state.players[active_seat]
    for s in ("p1", "p2"):
        for m in list(engine.state.players[s].board):
            if not m.silenced and m.card_id == "GVG_094":
                to_draw = max(0, 3 - len(active_p.hand))
                for _ in range(to_draw):
                    if engine.state.phase != "PLAY":
                        break
                    engine.draw_card(active_seat)

    _check_siege_engine_armor(engine)


def on_minion_summoned(engine: GameEngine, seat: str, minion: Minion) -> None:
    p = engine.state.players[seat]
    if minion.card_id == "GVG_086":  # Initialize Siege Engine armor baseline
        minion.extra_data["siege_last_armor"] = p.hero.armor

    if minion.race == "PIRATE":
        for bm in list(p.board):
            if bm.silenced or bm.uid == minion.uid:
                continue
            if bm.card_id == "GVG_025":  # One-eyed Cheat
                engine.add_enchantment(bm.uid, "GVG_025", "One-eyed Cheat", add_keywords={"STEALTH"})
            elif bm.card_id == "GVG_075":  # Ship's Cannon
                cands = engine.living_enemy_characters(seat)
                if cands:
                    engine.deal_damage(
                        engine.rng.choice(cands), 2, source_seat=seat, source_name="Ship's Cannon", source_minion=bm
                    )

    if minion.race == "MECHANICAL":
        for bm in list(p.board):
            if not bm.silenced and bm.card_id == "GVG_062" and bm.uid != minion.uid:  # Cobalt Guardian
                engine.add_enchantment(bm.uid, "GVG_062", "Cobalt Guardian", add_keywords={"DIVINE_SHIELD"})


def on_minion_played(engine: GameEngine, seat: str, card: CardDef, minion: Optional[Minion]) -> None:
    p = engine.state.players[seat]
    # Hobgoblin: Whenever you play a 1-Attack minion, give it +2/+2.
    if minion and minion in p.board and card.attack == 1:
        for bm in list(p.board):
            if not bm.silenced and bm.card_id == "GVG_104" and bm.uid != minion.uid:
                engine.add_enchantment(minion.uid, "GVG_104", "Hobgoblin", atk=2, hp=2)
    _check_siege_engine_armor(engine)


def on_spell_cast(engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]) -> None:
    opp_seat = engine.other_seat(seat)
    p = engine.state.players[seat]
    opp = engine.state.players[opp_seat]

    # Gazlowe: Whenever you cast a 1-Cost spell, add a random Mech to your hand.
    if card.cost == 1:
        mechs = helpers.collectible_pool(card_type="MINION", race="MECHANICAL")
        if mechs:
            for bm in list(p.board):
                if not bm.silenced and bm.card_id == "GVG_117":
                    engine.add_card_to_hand(seat, engine.rng.choice(mechs))

    # Opponent spell triggers: Gallywix, Stonesplinter Trogg, Burly Rockjaw Trogg, Troggzor
    for bm in list(opp.board):
        if bm.silenced:
            continue
        if bm.card_id == "GVG_028" and card.id != "GVG_028t":  # Trade Prince Gallywix
            engine.add_card_to_hand(opp_seat, card.id)
            engine.add_card_to_hand(seat, "GVG_028t")
        elif bm.card_id == "GVG_067":  # Stonesplinter Trogg
            engine.add_enchantment(bm.uid, "GVG_067", "Stonesplinter Trogg", atk=1)
        elif bm.card_id == "GVG_068":  # Burly Rockjaw Trogg
            engine.add_enchantment(bm.uid, "GVG_068", "Burly Rockjaw Trogg", atk=2)
        elif bm.card_id == "GVG_118":  # Troggzor the Earthinator
            engine.summon_minion(opp_seat, "GVG_068")


def on_after_spell(engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]) -> None:
    _check_siege_engine_armor(engine)


def on_inspire(engine: GameEngine, seat: str) -> None:
    _check_siege_engine_armor(engine)


def on_secret_revealed(engine: GameEngine, owner_seat: str, sec: SecretInstance) -> None:
    _check_siege_engine_armor(engine)


def on_damage_minion(
    engine: GameEngine, m: Minion, amount: int, source_seat: Optional[str], source_minion: Optional[Minion]
) -> None:
    if amount > 0 and not m.silenced:
        if m.card_id == "GVG_034":  # Mech-Bear-Cat
            engine.add_card_to_hand(m.owner, engine.rng.choice(SPARE_PARTS))
        elif m.card_id == "GVG_049":  # Gahz'rilla
            if m.attack > 0:
                engine.add_enchantment(m.uid, "GVG_049", "Gahz'rilla", atk=m.attack)
    _check_siege_engine_armor(engine)


def on_damage_hero(
    engine: GameEngine, target_seat: str, amount: int, source_seat: Optional[str], source_minion: Optional[Minion]
) -> None:
    # Floating Watcher: Whenever your hero takes damage on your turn, gain +2/+2.
    if amount > 0 and target_seat == engine.state.active_seat:
        for bm in list(engine.state.players[target_seat].board):
            if not bm.silenced and bm.card_id == "GVG_100":
                engine.add_enchantment(bm.uid, "GVG_100", "Floating Watcher", atk=2, hp=2)
    _check_siege_engine_armor(engine)


def on_heal(engine: GameEngine, caster_seat: str, target_id: str, amount: int, healed_minion: bool) -> None:
    # Shadowboxer: Whenever a minion is healed, deal 1 damage to a random enemy.
    if healed_minion and amount > 0:
        for s in ("p1", "p2"):
            for bm in list(engine.state.players[s].board):
                if not bm.silenced and bm.card_id == "GVG_072":
                    cands = engine.living_enemy_characters(s)
                    if cands:
                        engine.deal_damage(
                            engine.rng.choice(cands), 1, source_seat=s, source_name="Shadowboxer", source_minion=bm
                        )


def on_death(engine: GameEngine, dead_minion: Minion, orig_pos: int) -> None:
    owner_seat = dead_minion.owner
    opp_seat = engine.other_seat(owner_seat)
    owner_p = engine.state.players[owner_seat]
    opp_p = engine.state.players[opp_seat]

    # Bolvar Fordragon: Whenever a friendly minion dies while this is in your hand, gain +1 Attack.
    for ci in owner_p.hand:
        if ci.card_id == "GVG_063":
            helpers.buff_hand_card(engine, owner_seat, ci, atk=1)

    # Siltfin Spiritwalker: Whenever another friendly Murloc dies, draw a card.
    if dead_minion.race == "MURLOC":
        for bm in list(owner_p.board):
            if not bm.silenced and bm.card_id == "GVG_040" and bm.uid != dead_minion.uid:
                engine.draw_card(owner_seat)

    # Junkbot: Whenever a friendly Mech dies, gain +2/+2.
    if dead_minion.race == "MECHANICAL":
        for bm in list(owner_p.board):
            if not bm.silenced and bm.card_id == "GVG_106" and bm.uid != dead_minion.uid:
                engine.add_enchantment(bm.uid, "GVG_106", "Junkbot", atk=2, hp=2)

    # Dormant Malorne: Revive after 2 friendly Beasts die.
    if dead_minion.race == "BEAST":
        for bm in list(owner_p.board):
            if bm.card_id == "GVG_035" and bm.has_keyword("DORMANT") and bm.extra_data.get("malorne_dormant", 0) > 0:
                rem = bm.extra_data["malorne_dormant"] - 1
                bm.extra_data["malorne_dormant"] = rem
                if rem <= 0:
                    bm.enchantments = [e for e in bm.enchantments if "DORMANT" not in e.add_keywords]
                    bm.summoned_this_turn = True
                    engine.recompute_auras()
                    engine.add_log("Malorne awakened from Dormant!", seat=owner_seat)

    # Mekgineer Thermaplugg: Whenever an enemy minion dies, summon a Leper Gnome.
    for bm in list(opp_p.board):
        if not bm.silenced and bm.card_id == "GVG_116":
            engine.summon_minion(opp_seat, "VAN_EX1_029")


def on_draw(engine: GameEngine, seat: str, ci: CardInstance) -> bool:
    if ci.card_id == "GVG_056t":  # Burrowing Mine (Casts When Drawn)
        engine.add_log(f"Burrowing Mine explodes! {engine.state.players[seat].name} takes 10 damage!", seat=seat)
        engine.deal_damage(f"hero_{seat}", 10, source_seat=engine.other_seat(seat), source_name="Burrowing Mine")
        return True

    if ci.card_id == "GVG_007":  # Flame Leviathan (stays in hand!)
        engine.add_log("Flame Leviathan deals 2 damage to all non-Mech characters!", seat=seat)
        engine.deal_damage("hero_p1", 2, source_seat=seat, source_name="Flame Leviathan")
        engine.deal_damage("hero_p2", 2, source_seat=seat, source_name="Flame Leviathan")
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                if m.race != "MECHANICAL":
                    engine.deal_damage(m.uid, 2, source_seat=seat, source_name="Flame Leviathan")
        engine.resolve_deaths()
        engine.recompute_auras()
        return False

    return False


def on_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> tuple[str, bool]:
    # Ogre Warmaul: 50% chance to attack the wrong enemy.
    if attacker_id == f"hero_{seat}":
        p = engine.state.players[seat]
        if p.weapon and p.weapon.card_id == "GVG_054" and engine.rng.random() < 0.5:
            opp_seat = engine.other_seat(seat)
            opp = engine.state.players[opp_seat]
            other_enemies = [
                eid
                for eid in ([f"hero_{opp_seat}"] + [em.uid for em in opp.board if not em.has_keyword("DORMANT")])
                if eid != target_id
            ]
            if other_enemies:
                target_id = engine.rng.choice(other_enemies)
                engine.add_log("Ogre Warmaul attacked the wrong enemy!", seat=seat)
    return target_id, False


def on_after_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> None:
    # Foe Reaper 4000: Also damages the minions next to whomever it attacks.
    if not target_id.startswith("hero_"):
        atk_m = engine.find_minion(attacker_id)
        if atk_m and not atk_m.silenced and atk_m.card_id == "GVG_113":
            def_m = engine.find_minion(target_id)
            if def_m:
                opp_board = engine.state.players[def_m.owner].board
                if def_m in opp_board:
                    idx = opp_board.index(def_m)
                    neighbors = []
                    if idx - 1 >= 0:
                        neighbors.append(opp_board[idx - 1])
                    if idx + 1 < len(opp_board):
                        neighbors.append(opp_board[idx + 1])
                    dmg = atk_m.attack
                    for nb in neighbors:
                        engine.deal_damage(
                            nb.uid, dmg, source_seat=seat, source_name="Foe Reaper 4000", source_minion=atk_m
                        )
    _check_siege_engine_armor(engine)


# ---------------------------------------------------------------------------
# DYNAMIC AURAS
# ---------------------------------------------------------------------------

def recompute_auras(engine: GameEngine) -> None:
    for s in ("p1", "p2"):
        pl = engine.state.players[s]
        opp = engine.state.players[engine.other_seat(s)]
        board = pl.board

        # Cogmaster's Wrench: +2 Attack while you have a Mech.
        # (Uses attack_bonus + extra_data flag because game.py resets weapon.aura_attack_bonus after this hook.)
        if pl.weapon and pl.weapon.card_id == "GVG_024":
            _fix_gvg_weapon_durability(pl.weapon)
            has_mech = engine.has_mech_on_board(s)
            had_bonus = bool(pl.weapon.extra_data.get("wrench_bonus", False))
            if has_mech and not had_bonus:
                pl.weapon.attack_bonus += 2
                pl.weapon.extra_data["wrench_bonus"] = True
            elif not has_mech and had_bonus:
                pl.weapon.attack_bonus -= 2
                pl.weapon.extra_data["wrench_bonus"] = False

        for idx, m in enumerate(board):
            if m.silenced:
                continue
            cid = m.card_id

            if cid == "GVG_021":  # Mal'Ganis: Hero Immune + other friendly Demons +2/+2
                pl.hero.immune_aura = True
                for t in board:
                    if t.uid != m.uid and t.race == "DEMON":
                        t.aura_atk_bonus += 2
                        t.aura_hp_bonus += 2
                        t.attack = max(0, t.attack + 2)
                        t.max_health += 2

            elif cid == "GVG_046":  # King of Beasts: +1 Attack for each other Beast you control
                other_beasts = sum(
                    1
                    for bm in board
                    if bm.uid != m.uid and bm.race == "BEAST" and not bm.has_keyword("DORMANT")
                )
                if other_beasts:
                    m.aura_atk_bonus += other_beasts
                    m.attack = max(0, m.attack + other_beasts)

            elif cid == "GVG_051":  # Warbot: +1 Attack while damaged
                if m.damage > 0:
                    m.aura_atk_bonus += 1
                    m.attack = max(0, m.attack + 1)

            elif cid == "GVG_095":  # Goblin Sapper: +4 Attack while opponent has >= 6 cards
                if len(opp.hand) >= 6:
                    m.aura_atk_bonus += 4
                    m.attack = max(0, m.attack + 4)

            elif cid == "GVG_111t":  # V-07-TR-0N: Mega-Windfury
                m.keywords.add("MEGA_WINDFURY")

            elif cid == "GVG_122":  # Wee Spellstopper: Adjacent minions have Elusive
                for ni in (idx - 1, idx + 1):
                    if 0 <= ni < len(board):
                        board[ni].keywords.add("ELUSIVE")
