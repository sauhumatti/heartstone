"""Blackrock Mountain (BRM) expansion card implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.catalog import get_card
from engine.expansions.helpers import collectible_pool, replace_hero
from engine.models import ChooseOption

if TYPE_CHECKING:
    from engine.catalog import CardDef
    from engine.game import GameEngine
    from engine.models import CardInstance, Minion

TARGET_RULES: dict[str, str] = {
    "BRM_003": "ANY",  # Dragon's Breath
    "BRM_029": "LEGENDARY_MINION",  # Rend Blackhand (only when holding a Dragon)
    "BRM_030t": "ANY",  # Tail Swipe (token)
}

DRAGON_ONLY_TARGET_CARDS: set[str] = {
    "BRM_029",  # Rend Blackhand
}

CHOOSE_ONE_OPTIONS: dict[str, tuple[ChooseOption, ...]] = {
    "BRM_010": (  # Druid of the Flame
        ChooseOption("Firecat Form", "Transform into a 5/2 Beast.", "NONE"),
        ChooseOption("Fire Hawk Form", "Transform into a 2/5 Beast.", "NONE"),
    ),
}

DEATHRATTLE_CARDS: set[str] = {
    "BRM_027",  # Majordomo Executus
}

AURA_CARDS: set[str] = {
    "BRM_009",  # Volcanic Lumberer
    "BRM_025",  # Volcanic Drake
}

_CASTS_WHEN_DRAWN_IDS = frozenset({"LOE_110t", "GVG_056t", "AT_035t"})


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
    sd = lambda base: engine.calc_spell_damage(seat, base)

    if cid == "BRM_003":  # Dragon's Breath
        engine.deal_damage(target_id, sd(4), source_seat=seat, source_name="Dragon's Breath")
        return True
    if cid == "BRM_005":  # Demonwrath
        dmg = sd(2)
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                if m.race != "DEMON":
                    engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Demonwrath")
        return True
    if cid == "BRM_017":  # Resurrect
        if p.fallen_minions and len(p.board) < 7:
            engine.summon_minion(seat, engine.rng.choice(p.fallen_minions))
        return True
    if cid == "BRM_030t":  # Tail Swipe (token)
        engine.deal_damage(target_id, sd(4), source_seat=seat, source_name="Tail Swipe")
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

    if cid == "BRM_008":  # Dark Iron Skulker
        for m in list(opp.board):
            if not m.damaged:
                engine.deal_damage(
                    m.uid, 2, source_seat=seat, source_name="Dark Iron Skulker", source_minion=minion
                )
        return True
    if cid == "BRM_010":  # Druid of the Flame
        if minion is not None:
            if engine.has_fandral(seat):
                new_m = engine.transform_minion(minion.uid, "BRM_010t")
                if new_m:
                    engine.add_enchantment(new_m.uid, cid, "Druid of the Flame", hp=3)
            else:
                form_id = "BRM_010t" if (choose or 0) == 0 else "BRM_010t2"
                engine.transform_minion(minion.uid, form_id)
        return True
    if cid == "BRM_012":  # Fireguard Destroyer
        if minion is not None:
            gain = engine.rng.randint(1, 4)
            engine.add_enchantment(minion.uid, cid, "Fireguard Destroyer", atk=gain)
        return True
    if cid == "BRM_014":  # Core Rager
        if minion is not None and len(p.hand) == 0:
            engine.add_enchantment(minion.uid, cid, "Core Rager", atk=3, hp=3)
        return True
    if cid == "BRM_018":  # Dragon Consort
        p.next_dragon_cost_mod += 2
        return True
    if cid == "BRM_024":  # Drakonid Crusher
        if minion is not None and opp.hero.hp <= 15:
            engine.add_enchantment(minion.uid, cid, "Drakonid Crusher", atk=3, hp=3)
        return True
    if cid == "BRM_026":  # Hungry Dragon
        pool = collectible_pool(card_type="MINION", cost=1)
        if pool:
            engine.summon_minion(opp_seat, engine.rng.choice(pool))
        return True
    if cid == "BRM_029":  # Rend Blackhand
        if target_id and engine.has_dragon_in_hand(seat):
            engine.destroy_minion(target_id)
        return True
    if cid == "BRM_030":  # Nefarian
        pool = collectible_pool(hero_class=opp.hero.card_class, card_type="SPELL", include_neutral=False)
        for _ in range(2):
            if pool:
                engine.add_card_to_hand(seat, engine.rng.choice(pool))
            else:
                engine.add_card_to_hand(seat, "BRM_030t")
        return True
    return False


def trigger_deathrattle(
    engine: GameEngine,
    seat: str,
    cid: str,
    orig_pos: int,
    dead_minion: Optional[Minion] = None,
) -> bool:
    if cid == "BRM_027":  # Majordomo Executus
        replace_hero(engine, seat, "Ragnaros the Firelord", 8, "BRM_027p", is_ragnaros=True)
        return True
    return False


def trigger_hero_power(
    engine: GameEngine, seat: str, hp_id: str, target_id: Optional[str]
) -> bool:
    if hp_id == "BRM_027p":  # DIE, INSECT!
        cands = engine.living_enemy_characters(seat)
        if cands:
            dmg = 8 * engine.velen_multiplier(seat)
            engine.deal_damage(engine.rng.choice(cands), dmg, source_seat=seat, source_name="DIE, INSECT!")
        return True
    return False


def on_damage_minion(
    engine: GameEngine,
    m: Minion,
    amount: int,
    source_seat: Optional[str],
    source_minion: Optional[Minion],
) -> None:
    if m.silenced:
        return
    if m.card_id == "BRM_016":  # Axe Flinger
        opp_seat = engine.other_seat(m.owner)
        engine.deal_damage(
            f"hero_{opp_seat}", 2, source_seat=m.owner, source_name="Axe Flinger", source_minion=m
        )
    elif m.card_id == "BRM_019" and m.health > 0:  # Grim Patron
        owner_p = engine.state.players[m.owner]
        if len(owner_p.board) < 7:
            idx = owner_p.board.index(m) + 1 if m in owner_p.board else None
            engine.summon_minion(m.owner, "BRM_019", pos=idx)
    elif m.card_id == "BRM_022":  # Dragon Egg
        owner_p = engine.state.players[m.owner]
        if len(owner_p.board) < 7:
            idx = owner_p.board.index(m) + 1 if m in owner_p.board else None
            engine.summon_minion(m.owner, "BRM_022t", pos=idx)


def on_spell_cast(
    engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]
) -> None:
    if target_id and not target_id.startswith("hero_"):
        m = engine.find_minion(target_id)
        if m and m.owner == seat and not m.silenced and m.card_id == "BRM_020":  # Dragonkin Sorcerer
            engine.add_enchantment(m.uid, "BRM_020", "Dragonkin Sorcerer", atk=1, hp=1)


def on_draw(engine: GameEngine, seat: str, ci: CardInstance) -> bool:
    if ci.card_id in _CASTS_WHEN_DRAWN_IDS:
        return False
    p = engine.state.players[seat]
    chroms = sum(1 for m in p.board if not m.silenced and m.card_id == "BRM_031")  # Chromaggus
    for _ in range(chroms):
        # Leave 1 slot for the drawn card itself (which give_card_instance_to_hand adds right after)
        if len(p.hand) + 1 < 10:
            engine.add_card_to_hand(seat, ci.card_id)
    return False


def get_card_cost(engine: GameEngine, seat: str, ci: CardInstance, cost: int) -> int:
    card = get_card(ci.card_id)
    p = engine.state.players[seat]
    if ci.card_id in ("BRM_003", "BRM_009", "BRM_025"):  # Dragon's Breath / Volcanic Lumberer / Volcanic Drake
        died = sum(len(pl.dead_minions_this_turn) for pl in engine.state.players.values())
        cost -= died
    if card.type == "MINION" and card.race == "DRAGON" and p.next_dragon_cost_mod:
        cost -= p.next_dragon_cost_mod
    return cost
