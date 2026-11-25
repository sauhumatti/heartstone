"""Whispers of the Old Gods (OG) expansion card implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.catalog import HEROES, CardDef, get_card
from engine.expansions import helpers
from engine.models import CardInstance, ChooseOption, Minion, PendingChoice

if TYPE_CHECKING:
    from engine.game import GameEngine


TOXIN_CARDS: tuple[str, ...] = (
    "OG_080b",  # Kingsblood Toxin
    "OG_080c",  # Bloodthistle Toxin
    "OG_080d",  # Briarthorn Toxin
    "OG_080e",  # Fadeleaf Toxin
    "OG_080f",  # Firebloom Toxin
)

TARGET_RULES: dict[str, str] = {
    # Spells
    "OG_023": "MINION",           # Primal Fusion
    "OG_048": "MINION",           # Mark of Y'Shaarj
    "OG_061": "ANY",              # On the Hunt
    "OG_081": "MINION",           # Shatter (destroys if Frozen)
    "OG_086": "MINION",           # Forbidden Flame
    "OG_094": "MINION",           # Power Word: Tentacles
    "OG_176": "ANY",              # Shadow Strike (deals 5 if undamaged)
    "OG_198": "ANY",              # Forbidden Healing
    "OG_206": "MINION",           # Stormcrack
    "OG_223": "MINION",           # Divine Strength
    "OG_314": "MINION",           # Blood To Ichor
    # Toxin Token Spells
    "OG_080c": "FRIENDLY_MINION", # Bloodthistle Toxin
    "OG_080d": "MINION",          # Briarthorn Toxin
    "OG_080e": "FRIENDLY_MINION", # Fadeleaf Toxin
    "OG_080f": "ANY",             # Firebloom Toxin
    # Targeted Battlecry Minions
    "OG_102": "FRIENDLY_MINION",      # Darkspeaker
    "OG_162": "ANY",                  # Disciple of C'Thun
    "OG_174": "FRIENDLY_MINION",      # Faceless Shambler
    "OG_234": "ANY",                  # Darkshire Alchemist
    "OG_282": "MINION",               # Blade of C'Thun
    "OG_291": "FRIENDLY_MINION",      # Shadowcaster
    "OG_309": "FRIENDLY_DEATHRATTLE", # Princess Huhuran
    "OG_328": "FRIENDLY_MINION",      # Master of Evolution
}

CHOOSE_ONE_OPTIONS: dict[str, tuple[ChooseOption, ...]] = {
    "OG_195": (  # Wisps of the Old Gods
        ChooseOption("Many Wisps", "Summon seven 1/1 Wisps.", "NONE"),
        ChooseOption("Big Wisps", "Give your minions +2/+2.", "NONE"),
    ),
    "OG_202": (  # Mire Keeper
        ChooseOption("Y'Shaarj's Strength", "Summon a 2/2 Slime.", "NONE"),
        ChooseOption("Y'Shaarj's Magic", "Gain an empty Mana Crystal.", "NONE"),
    ),
}

PURE_KEYWORD_CARDS: set[str] = {
    "OG_141",  # Faceless Behemoth
    "OG_142",  # Eldritch Horror
    "OG_145",  # Psych-o-Tron
    "OG_152",  # Grotesque Dragonhawk
    "OG_153",  # Bog Creeper
    "OG_247",  # Twisted Worgen
    "OG_248",  # Am'gam Rager
    "OG_325",  # Carrion Grub
    "OG_326",  # Duskboar
    "OG_327",  # Squirming Tentacle
    "OG_340",  # Soggoth the Slitherer
}

DEATHRATTLE_CARDS: set[str] = {
    "OG_080",  # Xaril, Poisoned Mind
    "OG_109",  # Darkshire Librarian
    "OG_120",  # Anomalus
    "OG_147",  # Corrupted Healbot
    "OG_151",  # Tentacle of N'Zoth
    "OG_158",  # Zealous Initiate
    "OG_179",  # Fiery Bat
    "OG_216",  # Infested Wolf
    "OG_221",  # Selfless Hero
    "OG_241",  # Possessed Villager
    "OG_249",  # Infested Tauren
    "OG_256",  # Spawn of N'Zoth
    "OG_267",  # Southsea Squidface
    "OG_272",  # Twilight Summoner
    "OG_317",  # Deathwing, Dragonlord
    "OG_323",  # Polluted Hoarder
    "OG_330",  # Undercity Huckster
    "OG_335",  # Shifting Shade
}

AURA_CARDS: set[str] = {
    "OG_034",  # Silithid Swarmer
    "OG_082",  # Evolved Kobold (Spell Damage +2)
    "OG_150",  # Aberrant Berserker
    "OG_209",  # Hallazeal the Ascended
    "OG_218",  # Bloodhoof Brave
    "OG_322",  # Blackwater Pirate
}


def _fix_weapon_durability(engine: GameEngine, seat: str, card_id: str) -> None:
    """Fix durability for weapons whose catalog entry stores durability in health."""
    p = engine.state.players[seat]
    w = p.weapon
    if not w or w.card_id != card_id:
        return
    cdef = get_card(card_id)
    if (cdef.durability or 0) <= 0 and (cdef.health or 0) > 1 and w.durability == 1:
        w.durability = cdef.health or 1
        w.max_durability = w.durability


def _auto_resolve_pending_choices(engine: GameEngine, limit: int = 5) -> None:
    """Resolve any pending choices created by randomly cast spells (Yogg/Servant)."""
    for _ in range(limit):
        pc = engine.state.pending_choice
        if not pc or not pc.options:
            break
        engine.resolve_pending_choice(pc.seat, engine.rng.randrange(len(pc.options)))


def _trigger_hallazeal_lifesteal(
    engine: GameEngine, source_seat: Optional[str], amount: int, source_minion: Optional[Minion]
) -> None:
    if not source_seat or amount <= 0 or source_minion is not None or engine._combat:
        return
    p = engine.state.players[source_seat]
    if not p.extra_flags.get("og_casting_spell") or p.extra_flags.get("og_hallazeal_healing"):
        return
    if not any(not bm.silenced and bm.card_id == "OG_209" for bm in p.board):
        return
    p.extra_flags["og_hallazeal_healing"] = True
    try:
        engine.apply_heal(source_seat, f"hero_{source_seat}", amount, from_spell_or_power=True)
    finally:
        p.extra_flags["og_hallazeal_healing"] = False


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
    sd = lambda b: engine.calc_spell_damage(seat, b)

    if cid == "OG_023":  # Primal Fusion
        if target_id:
            totems = sum(1 for bm in p.board if bm.race == "TOTEM")
            if totems > 0:
                engine.add_enchantment(target_id, cid, "Primal Fusion", atk=totems, hp=totems)
        return True

    if cid == "OG_027":  # Evolve
        for m in list(p.board):
            if m in p.board:
                helpers.evolve_minion(engine, m, 1)
        return True

    if cid == "OG_045":  # Infest
        for m in list(p.board):
            engine.add_enchantment(m.uid, cid, "Infest", extra_deathrattle="ADD_RANDOM_BEAST")
        return True

    if cid == "OG_048":  # Mark of Y'Shaarj
        m = engine.find_minion(target_id)
        if m:
            engine.add_enchantment(m.uid, cid, "Mark of Y'Shaarj", atk=2, hp=2)
            if m.race == "BEAST":
                engine.draw_card(seat)
        return True

    if cid == "OG_061":  # On the Hunt
        if target_id:
            engine.deal_damage(target_id, sd(1), source_seat=seat, source_name="On the Hunt")
        engine.summon_minion(seat, "OG_061t")
        return True

    if cid == "OG_072":  # Journey Below
        pool = helpers.collectible_pool(hero_class=p.hero.card_class, mechanic="DEATHRATTLE")
        if pool:
            engine.start_discover(seat, cid, pool, choice_type="DISCOVER")
        return True

    if cid == "OG_073":  # Thistle Tea
        drawn = engine.draw_card(seat)
        if drawn is not None:
            for _ in range(2):
                engine.add_card_to_hand(seat, drawn.card_id)
        return True

    # Xaril Toxin Spells
    if cid == "OG_080b":  # Kingsblood Toxin
        engine.draw_card(seat)
        return True

    if cid == "OG_080c":  # Bloodthistle Toxin
        m = engine.find_minion(target_id)
        if m:
            engine.bounce_minion(m, cost_mod_delta=-2)
        return True

    if cid == "OG_080d":  # Briarthorn Toxin
        if target_id:
            engine.add_enchantment(target_id, cid, "Briarthorn Toxin", atk=3)
        return True

    if cid == "OG_080e":  # Fadeleaf Toxin
        m = engine.find_minion(target_id)
        if m:
            engine.add_enchantment(m.uid, cid, "Fadeleaf Toxin", add_keywords={"STEALTH"})
            m.stealth_until_sot_of = seat
        return True

    if cid == "OG_080f":  # Firebloom Toxin
        if target_id:
            engine.deal_damage(target_id, sd(2), source_seat=seat, source_name="Firebloom Toxin")
        return True

    if cid == "OG_081":  # Shatter
        m = engine.find_minion(target_id)
        if m and m.frozen:
            engine.destroy_minion(m.uid)
        return True

    if cid == "OG_086":  # Forbidden Flame
        spent = p.mana
        p.mana = 0
        if target_id:
            dmg = sd(spent)
            if dmg > 0:
                engine.deal_damage(target_id, dmg, source_seat=seat, source_name="Forbidden Flame")
        return True

    if cid == "OG_090":  # Cabalist's Tome
        pool = helpers.collectible_pool(hero_class="MAGE", include_neutral=False, card_type="SPELL")
        if pool:
            for _ in range(3):
                engine.add_card_to_hand(seat, engine.rng.choice(pool))
        return True

    if cid == "OG_094":  # Power Word: Tentacles
        if target_id:
            engine.add_enchantment(target_id, cid, "Power Word: Tentacles", atk=2, hp=6)
        return True

    if cid == "OG_100":  # Shadow Word: Horror
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                if m.attack <= 2:
                    engine.destroy_minion(m.uid)
        return True

    if cid == "OG_101":  # Forbidden Shaping
        spent = p.mana
        p.mana = 0
        pool = helpers.collectible_pool(card_type="MINION", cost=spent)
        if pool:
            engine.summon_minion(seat, engine.rng.choice(pool))
        return True

    if cid == "OG_104":  # Embrace the Shadow
        p.embrace_shadow_this_turn = True
        engine.add_log(f"{p.name}'s healing effects deal damage this turn.", seat=seat)
        return True

    if cid == "OG_114":  # Forbidden Ritual
        spent = p.mana
        p.mana = 0
        for _ in range(spent):
            if len(p.board) >= 7:
                break
            engine.summon_minion(seat, "OG_114a")
        return True

    if cid == "OG_116":  # Spreading Madness (ImmuneToSpellpower)
        for _ in range(13):
            cands: list[str] = []
            for s in ("p1", "p2"):
                pl = engine.state.players[s]
                if pl.hero.hp > 0:
                    cands.append(f"hero_{s}")
                cands.extend(bm.uid for bm in pl.board if bm.health > 0)
            if not cands:
                break
            engine.deal_damage(engine.rng.choice(cands), 1, source_seat=seat, source_name="Spreading Madness")
        return True

    if cid == "OG_118":  # Renounce Darkness
        other_classes = [cl for cl in HEROES if cl != "WARLOCK"]
        new_class = engine.rng.choice(other_classes)
        p.hero.hero_power_id = HEROES[new_class].hero_power_id
        p.hero.hero_power_used = False
        p.hero.hero_power_uses_this_turn = 0
        pool = helpers.collectible_pool(hero_class=new_class, include_neutral=False)
        if pool:
            # Keep CardInstance uids intact so hand_count and journal events stay synced
            for ci in p.hand:
                if get_card(ci.card_id).card_class == "WARLOCK":
                    ci.card_id = engine.rng.choice(pool)
                    ci.cost_mod -= 1
            for ci in p.deck:
                if get_card(ci.card_id).card_class == "WARLOCK":
                    ci.card_id = engine.rng.choice(pool)
                    ci.cost_mod -= 1
        engine.add_log(f"{p.name} renounced Darkness and became {new_class.title()}!", seat=seat)
        return True

    if cid == "OG_176":  # Shadow Strike
        if target_id:
            if target_id.startswith("hero_"):
                tseat = target_id.split("_")[1]
                h = engine.state.players[tseat].hero
                if h.hp >= h.max_hp:
                    engine.deal_damage(target_id, sd(5), source_seat=seat, source_name="Shadow Strike")
            else:
                m = engine.find_minion(target_id)
                if m and not m.damaged:
                    engine.deal_damage(target_id, sd(5), source_seat=seat, source_name="Shadow Strike")
        return True

    if cid == "OG_195":  # Wisps of the Old Gods
        both = engine.has_fandral(seat)
        if both or choose == 0:
            for _ in range(7):
                if len(p.board) >= 7:
                    break
                engine.summon_minion(seat, "OG_195c")
        if both or choose == 1:
            for m in list(p.board):
                engine.add_enchantment(m.uid, cid, "Wisps of the Old Gods", atk=2, hp=2)
        return True

    if cid == "OG_198":  # Forbidden Healing
        spent = p.mana
        p.mana = 0
        if target_id and spent > 0:
            amt = engine.calc_spell_healing(seat, spent * 2)
            engine.apply_heal(seat, target_id, amt, from_spell_or_power=True)
        return True

    if cid == "OG_206":  # Stormcrack
        if target_id:
            engine.deal_damage(target_id, sd(4), source_seat=seat, source_name="Stormcrack")
        return True

    if cid == "OG_223":  # Divine Strength
        if target_id:
            engine.add_enchantment(target_id, cid, "Divine Strength", atk=1, hp=2)
        return True

    if cid == "OG_239":  # DOOM!
        victims = [
            bm
            for s in ("p1", "p2")
            for bm in list(engine.state.players[s].board)
            if not bm.has_keyword("DORMANT")
        ]
        count = len(victims)
        for bm in victims:
            engine.destroy_minion(bm.uid)
        engine.resolve_deaths()
        for _ in range(count):
            if engine.state.phase != "PLAY":
                break
            engine.draw_card(seat)
        return True

    if cid == "OG_273":  # Stand Against Darkness
        for _ in range(5):
            if len(p.board) >= 7:
                break
            engine.summon_minion(seat, "VAN_CS2_101t")
        return True

    if cid == "OG_311":  # A Light in the Darkness
        pool = helpers.collectible_pool(hero_class="PALADIN", include_neutral=False, card_type="MINION")
        if pool:
            engine.start_discover(seat, cid, pool, choice_type="DISCOVER_OG_311")
        return True

    if cid == "OG_314":  # Blood To Ichor
        if target_id:
            m = engine.find_minion(target_id)
            engine.deal_damage(target_id, sd(1), source_seat=seat, source_name="Blood To Ichor")
            if m and m.health > 0 and engine.find_minion(m.uid) is not None:
                engine.summon_minion(seat, "OG_314b")
        return True

    return False


# ---------------------------------------------------------------------------
# BATTLECRIES & COMBOS (MINIONS & WEAPONS)
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

    if cid == "OG_006":  # Vilefin Inquisitor
        p.hero.hero_power_id = "OG_006b"
        p.hero.hero_power_used = False
        p.hero.hero_power_uses_this_turn = 0
        engine.add_log(f"{p.name}'s Hero Power became The Tidal Hand!", seat=seat)
        return True

    if cid == "OG_026":  # Eternal Sentinel
        unlocked = p.overloaded
        if unlocked > 0:
            p.mana = min(p.max_mana, p.mana + unlocked)
        p.overloaded = 0
        p.pending_overload = 0
        if unlocked > 0:
            engine.add_log(f"Eternal Sentinel unlocked {unlocked} Overloaded Mana Crystal(s).", seat=seat)
        return True

    if cid in ("OG_031", "OG_033"):  # Hammer of Twilight / Tentacles for Arms durability fix
        _fix_weapon_durability(engine, seat, cid)
        return True

    if cid == "OG_051":  # Forbidden Ancient
        spent = p.mana
        p.mana = 0
        if minion and spent > 0:
            engine.add_enchantment(minion.uid, cid, "Forbidden Ancient", atk=spent, hp=spent)
        return True

    if cid == "OG_070":  # Bladed Cultist
        if was_combo and minion:
            engine.add_enchantment(minion.uid, cid, "Bladed Cultist", atk=1, hp=1)
        return True

    if cid == "OG_080":  # Xaril, Poisoned Mind
        engine.add_card_to_hand(seat, engine.rng.choice(TOXIN_CARDS))
        return True

    if cid == "OG_083":  # Twilight Flamecaller
        for bm in list(opp.board):
            engine.deal_damage(bm.uid, 1, source_seat=seat, source_name="Twilight Flamecaller", source_minion=minion)
        return True

    if cid == "OG_087":  # Servant of Yogg-Saron
        pool = helpers.collectible_pool(card_type="SPELL", min_cost=5)
        if pool:
            helpers.cast_random_spell(engine, seat, engine.rng.choice(pool))
            _auto_resolve_pending_choices(engine)
        return True

    if cid == "OG_096":  # Twilight Darkmender
        if p.cthun_atk >= 10:
            engine.apply_heal(seat, f"hero_{seat}", 10, from_spell_or_power=True)
        return True

    if cid == "OG_102":  # Darkspeaker
        if minion and target_id:
            t = engine.find_minion(target_id)
            if t and t.uid != minion.uid:
                m_atk, m_hp = minion.attack, max(1, minion.health)
                t_atk, t_hp = t.attack, max(1, t.health)
                engine.add_enchantment(minion.uid, cid, "Darkspeaker", set_atk=t_atk, set_hp=t_hp)
                engine.add_enchantment(t.uid, cid, "Darkspeaker", set_atk=m_atk, set_hp=m_hp)
        return True

    if cid == "OG_109":  # Darkshire Librarian
        engine.discard_random(seat)
        return True

    if cid == "OG_121":  # Cho'gall
        returned = list(p.discarded_cards)
        p.discarded_cards.clear()
        for dcid in returned:
            ci = engine.add_card_to_hand(seat, dcid)
            if ci is not None:
                ci.extra_data["costs_health"] = True
        return True

    if cid == "OG_122":  # Mukla, Tyrant of the Vale
        for _ in range(2):
            engine.add_card_to_hand(seat, "EX1_014t")
        return True

    if cid == "OG_131":  # Twin Emperor Vek'lor
        if p.cthun_atk >= 10:
            idx = p.board.index(minion) + 1 if minion and minion in p.board else None
            engine.summon_minion(seat, "OG_319", pos=idx)
        return True

    if cid == "OG_133":  # N'Zoth, the Corruptor
        pool = list(p.fallen_deathrattles)
        engine.rng.shuffle(pool)
        for dcid in pool:
            if len(p.board) >= 7:
                break
            engine.summon_minion(seat, dcid)
        return True

    if cid == "OG_134":  # Yogg-Saron, Hope's End
        spell_count = len(p.spells_cast_by_id)
        pool = helpers.collectible_pool(card_type="SPELL")
        if pool and spell_count > 0:
            for _ in range(spell_count):
                if engine.state.phase != "PLAY":
                    break
                if minion and (minion not in p.board or minion.silenced or minion.health <= 0):
                    break
                helpers.cast_random_spell(engine, seat, engine.rng.choice(pool))
                _auto_resolve_pending_choices(engine)
        return True

    if cid == "OG_156":  # Bilefin Tidehunter
        idx = p.board.index(minion) + 1 if minion and minion in p.board else None
        engine.summon_minion(seat, "OG_156a", pos=idx)
        return True

    if cid == "OG_161":  # Corrupted Seer
        for s in ("p1", "p2"):
            for bm in list(engine.state.players[s].board):
                if bm.race != "MURLOC":
                    engine.deal_damage(bm.uid, 2, source_seat=seat, source_name="Corrupted Seer", source_minion=minion)
        return True

    if cid == "OG_162":  # Disciple of C'Thun
        if target_id:
            engine.deal_damage(target_id, 2, source_seat=seat, source_name="Disciple of C'Thun", source_minion=minion)
        helpers.buff_cthun(engine, seat, atk=2, hp=2)
        return True

    if cid == "OG_174":  # Faceless Shambler
        if minion and target_id:
            t = engine.find_minion(target_id)
            if t and t.uid != minion.uid:
                engine.add_enchantment(
                    minion.uid, cid, "Faceless Shambler", set_atk=t.attack, set_hp=max(1, t.health)
                )
        return True

    if cid == "OG_188":  # Klaxxi Amber-Weaver
        if minion and p.cthun_atk >= 10:
            engine.add_enchantment(minion.uid, cid, "Klaxxi Amber-Weaver", hp=5)
        return True

    if cid == "OG_202":  # Mire Keeper
        both = engine.has_fandral(seat)
        if both or choose == 0:
            idx = p.board.index(minion) + 1 if minion and minion in p.board else None
            engine.summon_minion(seat, "OG_202c", pos=idx)
        if both or choose == 1:
            if p.max_mana < 10:
                p.max_mana = min(10, p.max_mana + 1)
        return True

    if cid == "OG_207":  # Faceless Summoner
        pool = helpers.collectible_pool(card_type="MINION", cost=3)
        if pool:
            idx = p.board.index(minion) + 1 if minion and minion in p.board else None
            engine.summon_minion(seat, engine.rng.choice(pool), pos=idx)
        return True

    if cid == "OG_220":  # Malkorok
        pool = helpers.collectible_pool(card_type="WEAPON")
        if pool:
            wid = engine.rng.choice(pool)
            engine.equip_weapon(seat, wid)
            _fix_weapon_durability(engine, seat, wid)
        return True

    if cid == "OG_222":  # Rallying Blade
        _fix_weapon_durability(engine, seat, cid)
        for bm in list(p.board):
            if bm.has_keyword("DIVINE_SHIELD"):
                engine.add_enchantment(bm.uid, cid, "Rallying Blade", atk=1, hp=1)
        return True

    if cid == "OG_234":  # Darkshire Alchemist
        if target_id:
            engine.apply_heal(seat, target_id, 5, from_spell_or_power=True)
        return True

    if cid == "OG_254":  # Eater of Secrets
        cnt = len(opp.secrets)
        if cnt > 0:
            engine.destroy_secrets(opp_seat)
            if minion:
                engine.add_enchantment(minion.uid, cid, "Eater of Secrets", atk=cnt, hp=cnt)
        return True

    if cid == "OG_255":  # Doomcaller
        helpers.buff_cthun(engine, seat, atk=2, hp=2)
        if p.cthun_dead:
            engine.shuffle_into_deck(seat, "OG_280", count=1)
            p.cthun_dead = False
        return True

    if cid == "OG_280":  # C'Thun
        dmg = minion.attack if minion else p.cthun_atk
        for _ in range(max(0, dmg)):
            cands = engine.living_enemy_characters(seat)
            if not cands:
                break
            engine.deal_damage(engine.rng.choice(cands), 1, source_seat=seat, source_name="C'Thun", source_minion=minion)
        return True

    if cid == "OG_281":  # Beckoner of Evil
        helpers.buff_cthun(engine, seat, atk=2, hp=2)
        return True

    if cid == "OG_282":  # Blade of C'Thun
        if target_id:
            t = engine.find_minion(target_id)
            if t and (not minion or t.uid != minion.uid):
                t_atk = max(0, t.attack)
                t_hp = max(0, t.health)
                engine.destroy_minion(t.uid)
                helpers.buff_cthun(engine, seat, atk=t_atk, hp=t_hp)
        return True

    if cid == "OG_283":  # C'Thun's Chosen
        helpers.buff_cthun(engine, seat, atk=3, hp=3)
        return True

    if cid == "OG_284":  # Twilight Geomancer
        helpers.buff_cthun(engine, seat, atk=1, hp=1, taunt=True)
        return True

    if cid == "OG_291":  # Shadowcaster
        if target_id:
            t = engine.find_minion(target_id)
            if t and (not minion or t.uid != minion.uid):
                cdef = get_card(t.card_id)
                ci = CardInstance(
                    uid=engine._new_uid("c"),
                    card_id=t.card_id,
                    cost_mod=1 - cdef.cost,
                    attack_mod=1 - (cdef.attack or 0),
                    health_mod=1 - (cdef.health or 1),
                )
                engine.give_card_instance_to_hand(seat, ci, origin="created")
        return True

    if cid == "OG_292":  # Forlorn Stalker
        helpers.buff_hand_minions(
            engine, seat, atk=1, hp=1, predicate=lambda c: c.has_mechanic("DEATHRATTLE")
        )
        return True

    if cid == "OG_293":  # Dark Arakkoa
        helpers.buff_cthun(engine, seat, atk=4, hp=4)
        return True

    if cid == "OG_295":  # Cult Apothecary
        cnt = len(opp.board)
        if cnt > 0:
            engine.apply_heal(seat, f"hero_{seat}", 2 * cnt, from_spell_or_power=True)
        return True

    if cid == "OG_301":  # Ancient Shieldbearer
        if p.cthun_atk >= 10:
            p.hero.armor += 10
        return True

    if cid == "OG_309":  # Princess Huhuran
        if target_id:
            t = engine.find_minion(target_id)
            if t and (not minion or t.uid != minion.uid):
                helpers.trigger_minion_deathrattle(engine, t)
        return True

    if cid == "OG_312":  # N'Zoth's First Mate
        engine.equip_weapon(seat, "OG_058")
        _fix_weapon_durability(engine, seat, "OG_058")
        return True

    if cid == "OG_315":  # Bloodsail Cultist
        if p.weapon and any(bm.race == "PIRATE" and (not minion or bm.uid != minion.uid) for bm in p.board):
            p.weapon.attack_bonus += 1
            p.weapon.durability += 1
            p.weapon.max_durability += 1
            engine.recompute_auras()
        return True

    if cid == "OG_316":  # Herald Volazj
        others = [bm for bm in list(p.board) if not minion or bm.uid != minion.uid]
        for bm in others:
            if len(p.board) >= 7:
                break
            clone = engine.summon_minion(seat, bm.card_id)
            if clone:
                engine.add_enchantment(clone.uid, cid, "Herald Volazj", set_atk=1, set_hp=1)
        return True

    if cid == "OG_320":  # Midnight Drake
        if minion and len(p.hand) > 0:
            engine.add_enchantment(minion.uid, cid, "Midnight Drake", atk=len(p.hand))
        return True

    if cid == "OG_328":  # Master of Evolution
        if target_id:
            t = engine.find_minion(target_id)
            if t and (not minion or t.uid != minion.uid):
                helpers.evolve_minion(engine, t, 1)
        return True

    if cid == "OG_337":  # Cyclopian Horror
        cnt = len(opp.board)
        if minion and cnt > 0:
            engine.add_enchantment(minion.uid, cid, "Cyclopian Horror", hp=cnt)
        return True

    if cid == "OG_339":  # Skeram Cultist
        helpers.buff_cthun(engine, seat, atk=2, hp=2)
        return True

    return False


# ---------------------------------------------------------------------------
# DEATHRATTLES (MINIONS & WEAPONS)
# ---------------------------------------------------------------------------


def trigger_deathrattle(
    engine: GameEngine, seat: str, cid: str, orig_pos: int, dead_minion: Optional[Minion] = None
) -> bool:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]

    if cid == "OG_080":  # Xaril, Poisoned Mind
        engine.add_card_to_hand(seat, engine.rng.choice(TOXIN_CARDS))
        return True

    if cid == "OG_109":  # Darkshire Librarian
        engine.draw_card(seat)
        return True

    if cid == "OG_120":  # Anomalus
        for s in ("p1", "p2"):
            for bm in list(engine.state.players[s].board):
                engine.deal_damage(bm.uid, 8, source_seat=seat, source_name="Anomalus")
        return True

    if cid == "OG_147":  # Corrupted Healbot
        engine.apply_heal(seat, f"hero_{opp_seat}", 8, from_spell_or_power=True)
        return True

    if cid == "OG_151":  # Tentacle of N'Zoth
        for s in ("p1", "p2"):
            for bm in list(engine.state.players[s].board):
                engine.deal_damage(bm.uid, 1, source_seat=seat, source_name="Tentacle of N'Zoth")
        return True

    if cid == "OG_158":  # Zealous Initiate
        if p.board:
            engine.add_enchantment(engine.rng.choice(p.board).uid, cid, "Zealous Initiate", atk=1, hp=1)
        return True

    if cid == "OG_179":  # Fiery Bat
        cands = engine.living_enemy_characters(seat)
        if cands:
            engine.deal_damage(engine.rng.choice(cands), 1, source_seat=seat, source_name="Fiery Bat")
        return True

    if cid == "OG_216":  # Infested Wolf
        for _ in range(2):
            engine.summon_minion(seat, "OG_216a", pos=orig_pos)
        return True

    if cid == "OG_221":  # Selfless Hero
        cands = [bm for bm in p.board if not bm.has_keyword("DIVINE_SHIELD")]
        if cands:
            engine.add_enchantment(
                engine.rng.choice(cands).uid, cid, "Selfless Hero", add_keywords={"DIVINE_SHIELD"}
            )
        return True

    if cid == "OG_241":  # Possessed Villager
        engine.summon_minion(seat, "OG_241a", pos=orig_pos)
        return True

    if cid == "OG_249":  # Infested Tauren
        engine.summon_minion(seat, "OG_249a", pos=orig_pos)
        return True

    if cid == "OG_256":  # Spawn of N'Zoth
        for bm in list(p.board):
            engine.add_enchantment(bm.uid, cid, "Spawn of N'Zoth", atk=1, hp=1)
        return True

    if cid == "OG_267":  # Southsea Squidface
        if p.weapon:
            p.weapon.attack_bonus += 2
            engine.recompute_auras()
        return True

    if cid == "OG_272":  # Twilight Summoner
        engine.summon_minion(seat, "OG_272t", pos=orig_pos)
        return True

    if cid == "OG_317":  # Deathwing, Dragonlord
        while len(p.board) < 7:
            idx = next(
                (
                    i
                    for i, ci in enumerate(p.hand)
                    if (c := get_card(ci.card_id)).type == "MINION" and c.race == "DRAGON"
                ),
                None,
            )
            if idx is None:
                break
            engine.summon_minion_from_hand(seat, idx, len(p.board))
        return True

    if cid == "OG_323":  # Polluted Hoarder
        engine.draw_card(seat)
        return True

    if cid == "OG_330":  # Undercity Huckster
        pool = helpers.collectible_pool(hero_class=opp.hero.card_class, include_neutral=False)
        if pool:
            engine.add_card_to_hand(seat, engine.rng.choice(pool))
        return True

    if cid == "OG_335":  # Shifting Shade
        if opp.deck:
            engine.add_card_to_hand(seat, engine.rng.choice(opp.deck).card_id)
        return True

    return False


def trigger_weapon_deathrattle(engine: GameEngine, seat: str, cid: str) -> bool:
    if cid == "OG_031":  # Hammer of Twilight
        engine.summon_minion(seat, "OG_031a")
        return True
    if cid == "OG_033":  # Tentacles for Arms
        engine.add_card_to_hand(seat, "OG_033")
        return True
    return False


# ---------------------------------------------------------------------------
# HERO POWERS & PENDING CHOICES
# ---------------------------------------------------------------------------


def trigger_hero_power(engine: GameEngine, seat: str, hp_id: str, target_id: Optional[str]) -> bool:
    if hp_id == "OG_006b":  # The Tidal Hand (Vilefin Inquisitor)
        engine.summon_minion(seat, "OG_006a")
        return True
    return False


def resolve_pending_choice(
    engine: GameEngine, seat: str, pc: PendingChoice, picked: CardInstance, option_index: int
) -> bool:
    if pc.choice_type == "DISCOVER_OG_311":  # A Light in the Darkness
        picked.attack_mod += 2
        picked.health_mod += 2
        engine.give_card_instance_to_hand(seat, picked, origin="choice")
        engine.add_log(f"{engine.state.players[seat].name} discovered a +2/+2 Paladin minion.", seat=seat)
        return True
    return False


# ---------------------------------------------------------------------------
# TURN, BOARD, SPELL, DAMAGE, HEAL, DEATH & ATTACK TRIGGERS
# ---------------------------------------------------------------------------


def on_start_turn(engine: GameEngine, seat: str) -> None:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    p.extra_flags["og_casting_spell"] = False

    # Shifter Zerus & Nerubian Prophet in hand
    minion_pool: Optional[list[str]] = None
    for ci in p.hand:
        if ci.card_id == "OG_123" or ci.extra_data.get("shifter_zerus"):
            ci.extra_data["shifter_zerus"] = True
            if minion_pool is None:
                minion_pool = helpers.collectible_pool(card_type="MINION")
            if minion_pool:
                ci.card_id = engine.rng.choice(minion_pool)
        elif ci.card_id == "OG_138":
            ci.cost_mod -= 1

    # Nat, the Darkfisher on opponent's board
    for bm in list(engine.state.players[opp_seat].board):
        if not bm.silenced and bm.card_id == "OG_338":
            if engine.rng.random() < 0.5:
                engine.draw_card(seat)


def on_sot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    if minion.silenced:
        return
    p = engine.state.players[seat]
    cid = minion.card_id

    if cid == "OG_200":  # Validated Doomsayer
        engine.add_enchantment(minion.uid, cid, "Validated Doomsayer", set_atk=7)
    elif cid == "OG_271":  # Scaled Nightmare
        if minion.attack > 0:
            engine.add_enchantment(minion.uid, cid, "Scaled Nightmare", atk=minion.attack)
    elif cid == "OG_290":  # Ancient Harbinger
        idxs = [
            i
            for i, ci in enumerate(p.deck)
            if (c := get_card(ci.card_id)).type == "MINION" and c.cost == 10
        ]
        if idxs:
            ci = helpers.remove_from_deck(engine, seat, engine.rng.choice(idxs))
            engine.give_card_instance_to_hand(seat, ci, origin="deck")


def on_eot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    if minion.silenced:
        return
    p = engine.state.players[seat]
    cid = minion.card_id

    if cid == "OG_042":  # Y'Shaarj, Rage Unbound
        if len(p.board) < 7:
            idxs = [i for i, ci in enumerate(p.deck) if get_card(ci.card_id).type == "MINION"]
            if idxs:
                helpers.summon_from_deck(engine, seat, engine.rng.choice(idxs))
    elif cid == "OG_173":  # Blood of The Ancient One
        bloods = [bm for bm in p.board if bm.card_id == "OG_173" and not bm.silenced]
        if len(bloods) >= 2:
            first, second = bloods[0], bloods[1]
            engine.remove_minion(second)
            engine.transform_minion(first.uid, "OG_173a")
            engine.add_log("Two Bloods merged into The Ancient One!", seat=seat)
    elif cid == "OG_229":  # Ragnaros, Lightlord
        cands: list[str] = []
        if p.hero.hp < p.hero.max_hp:
            cands.append(f"hero_{seat}")
        cands.extend(bm.uid for bm in p.board if bm.damaged)
        if cands:
            engine.apply_heal(seat, engine.rng.choice(cands), 8, from_spell_or_power=True)
    elif cid == "OG_286":  # Twilight Elder
        helpers.buff_cthun(engine, seat, atk=1, hp=1)


def on_eot_both(engine: GameEngine, active_seat: str) -> None:
    for s in ("p1", "p2"):
        engine.state.players[s].extra_flags["og_casting_spell"] = False


def on_card_played(engine: GameEngine, seat: str, card: CardDef, ci: CardInstance) -> None:
    engine.state.players[seat].extra_flags["og_casting_spell"] = False


def on_inspire(engine: GameEngine, seat: str) -> None:
    engine.state.players[seat].extra_flags["og_casting_spell"] = False


def on_minion_summoned(engine: GameEngine, seat: str, minion: Minion) -> None:
    p = engine.state.players[seat]
    for bm in list(p.board):
        if bm.silenced or bm.uid == minion.uid or bm not in p.board:
            continue
        if bm.card_id == "OG_113":  # Darkshire Councilman
            engine.add_enchantment(bm.uid, bm.card_id, "Darkshire Councilman", atk=1)
        elif bm.card_id == "OG_310":  # Steward of Darkshire
            if minion in p.board and minion.health == 1 and not minion.has_keyword("DIVINE_SHIELD"):
                engine.add_enchantment(
                    minion.uid, bm.card_id, "Steward of Darkshire", add_keywords={"DIVINE_SHIELD"}
                )
        elif bm.card_id == "OG_313":  # Addled Grizzly
            if minion in p.board and minion.race == "BEAST":
                engine.add_enchantment(minion.uid, bm.card_id, "Addled Grizzly", atk=1, hp=1)


def on_spell_cast(engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]) -> None:
    engine.state.players[seat].extra_flags["og_casting_spell"] = True


def on_after_spell(engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]) -> None:
    p = engine.state.players[seat]
    p.extra_flags["og_casting_spell"] = False
    for bm in list(p.board):
        if bm not in p.board or bm.silenced or bm.health <= 0:
            continue
        if bm.card_id == "OG_085":  # Demented Frostcaller
            cands = [t for t in engine.living_enemy_characters(seat) if not engine.is_frozen(t)]
            if cands:
                engine.freeze_character(engine.rng.choice(cands))
        elif bm.card_id == "OG_303":  # Cult Sorcerer
            helpers.buff_cthun(engine, seat, atk=1, hp=1)


def on_damage_minion(
    engine: GameEngine, m: Minion, amount: int, source_seat: Optional[str], source_minion: Optional[Minion]
) -> None:
    if amount <= 0:
        return
    if not m.silenced:
        if m.card_id == "OG_318":  # Hogger, Doom of Elwynn
            board = engine.state.players[m.owner].board
            pos = board.index(m) + 1 if m in board else None
            engine.summon_minion(m.owner, "OG_318t", pos=pos)
        elif m.card_id == "OG_321":  # Crazed Worshipper
            helpers.buff_cthun(engine, m.owner, atk=1, hp=1)
    _trigger_hallazeal_lifesteal(engine, source_seat, amount, source_minion)


def on_damage_hero(
    engine: GameEngine, target_seat: str, amount: int, source_seat: Optional[str], source_minion: Optional[Minion]
) -> None:
    if amount <= 0:
        return
    _trigger_hallazeal_lifesteal(engine, source_seat, amount, source_minion)


def on_heal(engine: GameEngine, caster_seat: str, target_id: str, amount: int, healed_minion: bool) -> None:
    if amount <= 0:
        return
    for s in ("p1", "p2"):
        for bm in list(engine.state.players[s].board):
            if not bm.silenced and bm.card_id == "OG_334":  # Hooded Acolyte
                helpers.buff_cthun(engine, s, atk=1, hp=1)


def on_death(engine: GameEngine, dead_minion: Minion, orig_pos: int) -> None:
    for s in ("p1", "p2"):
        for bm in list(engine.state.players[s].board):
            if not bm.silenced and bm.card_id == "OG_302":  # Usher of Souls
                helpers.buff_cthun(engine, s, atk=1, hp=1)


def on_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> tuple[str, bool]:
    engine.state.players[seat].extra_flags["og_casting_spell"] = False
    return target_id, False


def on_after_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> None:
    if attacker_id.startswith("hero_") or target_id.startswith("hero_"):
        return
    atk_m = engine.find_minion(attacker_id)
    if not atk_m or atk_m.silenced or atk_m.health <= 0:
        return
    def_m = engine.find_minion(target_id)
    killed = def_m is None or def_m.health <= 0
    if not killed:
        return
    if atk_m.card_id == "OG_300":  # The Boogeymonster
        engine.add_enchantment(atk_m.uid, "OG_300", "The Boogeymonster", atk=2, hp=2)
    elif atk_m.card_id == "OG_308":  # Giant Sand Worm
        atk_m.attacks_this_turn = max(0, atk_m.attacks_this_turn - 1)


# ---------------------------------------------------------------------------
# AURAS & COST MODIFIERS
# ---------------------------------------------------------------------------


def recompute_auras(engine: GameEngine) -> None:
    for s in ("p1", "p2"):
        pl = engine.state.players[s]
        for m in pl.board:
            if m.silenced:
                continue
            cid = m.card_id
            if cid == "OG_034":  # Silithid Swarmer
                if pl.hero.attacks_this_turn == 0:
                    m.keywords.add("CANT_ATTACK")
                else:
                    m.keywords.discard("CANT_ATTACK")
            elif cid == "OG_082":  # Evolved Kobold (catalog has sp=1, card is Spell Damage +2)
                m.spell_damage += 1
            elif cid == "OG_150" and m.damage > 0:  # Aberrant Berserker
                m.attack += 2
            elif cid == "OG_218" and m.damage > 0:  # Bloodhoof Brave
                m.attack += 3


def get_card_cost(engine: GameEngine, seat: str, ci: CardInstance, cost: int) -> int:
    if get_card(ci.card_id).type == "WEAPON":
        pirates = sum(
            1
            for bm in engine.state.players[seat].board
            if not bm.silenced and bm.card_id == "OG_322"
        )
        cost -= 2 * pirates
    return cost
