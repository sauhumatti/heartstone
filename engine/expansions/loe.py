"""League of Explorers (LOE) expansion card implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.catalog import get_card
from engine.expansions.helpers import (
    collectible_pool,
    put_secret_into_play,
    remove_from_deck,
    remove_from_hand,
    summon_from_deck,
)
from engine.models import CardInstance, ChooseOption, PendingChoice

if TYPE_CHECKING:
    from engine.catalog import CardDef
    from engine.game import GameEngine
    from engine.models import Minion

TARGET_RULES: dict[str, str] = {
    "LOE_002": "ANY",  # Forgotten Torch
    "LOE_002t": "ANY",  # Roaring Torch (token)
    "LOE_019": "FRIENDLY_DEATHRATTLE",  # Unearthed Raptor
    "LOE_105": "MINION",  # Explorer's Hat
    "LOEA16_3": "MINION",  # Lantern of Power (Rafaam artifact)
}

CHOOSE_ONE_OPTIONS: dict[str, tuple[ChooseOption, ...]] = {
    "LOE_115": (  # Raven Idol
        ChooseOption("Break Free", "Discover a minion.", "NONE"),
        ChooseOption("Awakened", "Discover a spell.", "NONE"),
    ),
}

PURE_KEYWORD_CARDS: set[str] = {
    "LOEA10_3",  # Murloc Tinyfin
    "LOE_010",  # Pit Snake (Poisonous)
    "LOE_022",  # Fierce Monkey (Taunt)
}

DEATHRATTLE_CARDS: set[str] = {
    "LOE_046",  # Huge Toad
    "LOE_050",  # Mounted Raptor
    "LOE_061",  # Anubisath Sentinel
    "LOE_089",  # Wobbling Runts
}

SECRET_CARDS: set[str] = {
    "LOE_021",  # Dart Trap
    "LOE_027",  # Sacred Trial
}

AURA_CARDS: set[str] = {
    "LOE_038",  # Naga Sea Witch
    "LOE_051",  # Jungle Moonkin
    "LOE_107",  # Eerie Statue
    "LOE_119",  # Animated Armor
}


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

    if cid == "LOE_COIN":  # The Coin (token)
        p.mana = min(10, p.mana + 1)
        return True
    if cid == "LOE_002":  # Forgotten Torch
        engine.deal_damage(target_id, sd(3), source_seat=seat, source_name="Forgotten Torch")
        engine.shuffle_into_deck(seat, "LOE_002t", count=1)
        return True
    if cid == "LOE_002t":  # Roaring Torch (token)
        engine.deal_damage(target_id, sd(6), source_seat=seat, source_name="Roaring Torch")
        return True
    if cid == "LOE_007":  # Curse of Rafaam
        engine.add_card_to_hand(opp_seat, "LOE_007t")
        return True
    if cid == "LOE_007t":  # Cursed! (token — paying 2 mana removes it from hand)
        return True
    if cid == "LOE_008":  # Eye of Hakkar (token)
        active = {s.card_id for s in p.secrets}
        sec_idxs = [
            i for i, ci in enumerate(opp.deck)
            if get_card(ci.card_id).has_mechanic("SECRET") and ci.card_id not in active
        ]
        if sec_idxs and len(p.secrets) < 5:
            ci = remove_from_deck(engine, opp_seat, engine.rng.choice(sec_idxs))
            put_secret_into_play(engine, seat, ci.card_id)
        return True
    if cid == "LOE_019t":  # Map to the Golden Monkey (token)
        engine.shuffle_into_deck(seat, "LOE_019t2", count=1)
        engine.draw_card(seat)
        return True
    if cid == "LOE_105":  # Explorer's Hat
        engine.add_enchantment(
            target_id, cid, "Explorer's Hat", atk=1, hp=1, extra_deathrattle="ADD_HAND:LOE_105"
        )
        return True
    if cid == "LOE_110t":  # Ancient Curse (if cast from hand, does nothing)
        return True
    if cid == "LOE_111":  # Excavated Evil
        dmg = sd(3)
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Excavated Evil")
        engine.shuffle_into_deck(opp_seat, "LOE_111", count=1)
        return True
    if cid == "LOE_113":  # Everyfin is Awesome
        for m in list(p.board):
            engine.add_enchantment(m.uid, cid, "Everyfin is Awesome", atk=2, hp=2)
        return True
    if cid == "LOE_115":  # Raven Idol
        both = engine.has_fandral(seat)
        if both:
            pool_m = collectible_pool(hero_class=p.hero.card_class, card_type="MINION")
            if pool_m:
                picked = engine.rng.sample(pool_m, min(3, len(pool_m)))
                opts = [CardInstance(uid=engine._new_uid("c"), card_id=c) for c in picked]
                engine.state.pending_choice = PendingChoice(
                    seat=seat,
                    choice_type="RAVEN_IDOL_FANDRAL",
                    source_card_id="LOE_115",
                    options=opts,
                )
        elif (choose or 0) == 0:
            pool = collectible_pool(hero_class=p.hero.card_class, card_type="MINION")
            engine.start_discover(seat, cid, pool, choice_type="DISCOVER")
        else:
            pool = collectible_pool(hero_class=p.hero.card_class, card_type="SPELL")
            engine.start_discover(seat, cid, pool, choice_type="DISCOVER")
        return True
    if cid == "LOE_115a":  # Break Free (token)
        pool = collectible_pool(hero_class=p.hero.card_class, card_type="MINION")
        engine.start_discover(seat, cid, pool, choice_type="DISCOVER")
        return True
    if cid == "LOE_115b":  # Awakened (token)
        pool = collectible_pool(hero_class=p.hero.card_class, card_type="SPELL")
        engine.start_discover(seat, cid, pool, choice_type="DISCOVER")
        return True
    if cid == "LOEA16_3":  # Lantern of Power (Rafaam artifact)
        engine.add_enchantment(target_id, cid, "Lantern of Power", atk=10, hp=10)
        return True
    if cid == "LOEA16_4":  # Timepiece of Horror (Rafaam artifact)
        for _ in range(10):
            cands = engine.living_enemy_characters(seat)
            if not cands:
                break
            engine.deal_damage(engine.rng.choice(cands), 1, source_seat=seat, source_name="Timepiece of Horror")
            engine.resolve_deaths()
        return True
    if cid == "LOEA16_5":  # Mirror of Doom (Rafaam artifact)
        while len(p.board) < 7:
            if not engine.summon_minion(seat, "LOEA16_5t"):
                break
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

    if cid == "LOE_003":  # Ethereal Conjurer
        pool = collectible_pool(hero_class=p.hero.card_class, card_type="SPELL")
        engine.start_discover(seat, cid, pool, choice_type="DISCOVER")
        return True
    if cid == "LOE_006":  # Museum Curator
        pool = collectible_pool(hero_class=p.hero.card_class, mechanic="DEATHRATTLE")
        if pool:
            engine.start_discover(seat, cid, pool, choice_type="MUSEUM_CURATOR")
        return True
    if cid == "LOE_019":  # Unearthed Raptor
        if minion and target_id:
            target = engine.find_minion(target_id)
            if target and not target.silenced:
                from engine.effects import DEATHRATTLE_CARDS as ALL_DR_CARDS

                if target.card_id in ALL_DR_CARDS:
                    engine.add_enchantment(
                        minion.uid,
                        cid,
                        target.name,
                        add_keywords={"DEATHRATTLE"},
                        extra_deathrattle=f"COPY:{target.card_id}",
                    )
                for ench in list(target.enchantments):
                    if ench.extra_deathrattle:
                        engine.add_enchantment(
                            minion.uid,
                            cid,
                            ench.source_name,
                            add_keywords={"DEATHRATTLE"},
                            extra_deathrattle=ench.extra_deathrattle,
                        )
        return True
    if cid == "LOE_019t2":  # Golden Monkey (token)
        legs = collectible_pool(card_type="MINION", rarity="LEGENDARY")
        if legs:
            hand_n = len(p.hand)
            for i in range(hand_n - 1, -1, -1):
                remove_from_hand(engine, seat, i)
            for _ in range(hand_n):
                engine.add_card_to_hand(seat, engine.rng.choice(legs))
            deck_n = len(p.deck)
            for i in range(deck_n - 1, -1, -1):
                remove_from_deck(engine, seat, i)
            for _ in range(deck_n):
                engine.shuffle_into_deck(seat, engine.rng.choice(legs), count=1)
        return True
    if cid == "LOE_020":  # Desert Camel
        for s in (seat, opp_seat):
            pl = engine.state.players[s]
            if len(pl.board) < 7:
                idxs = [
                    i for i, ci in enumerate(pl.deck)
                    if (c := get_card(ci.card_id)).type == "MINION" and c.cost == 1
                ]
                if idxs:
                    summon_from_deck(engine, s, engine.rng.choice(idxs))
        return True
    if cid == "LOE_029":  # Jeweled Scarab
        pool = collectible_pool(hero_class=p.hero.card_class, cost=3)
        engine.start_discover(seat, cid, pool, choice_type="DISCOVER")
        return True
    if cid == "LOE_039":  # Gorillabot A-3
        if engine.has_mech_on_board(seat, exclude_uid=minion.uid if minion else None):
            pool = collectible_pool(hero_class=p.hero.card_class, race="MECHANICAL")
            engine.start_discover(seat, cid, pool, choice_type="DISCOVER")
        return True
    if cid == "LOE_047":  # Tomb Spider
        pool = collectible_pool(hero_class=p.hero.card_class, race="BEAST")
        engine.start_discover(seat, cid, pool, choice_type="DISCOVER")
        return True
    if cid == "LOE_073":  # Fossilized Devilsaur
        if minion and any(m.uid != minion.uid and m.race == "BEAST" for m in p.board):
            engine.add_enchantment(minion.uid, cid, "Fossilized Devilsaur", add_keywords={"TAUNT"})
        return True
    if cid == "LOE_079":  # Elise Starseeker
        engine.shuffle_into_deck(seat, "LOE_019t", count=1)
        return True
    if cid == "LOE_092":  # Arch-Thief Rafaam
        engine.start_discover(seat, cid, ["LOEA16_3", "LOEA16_4", "LOEA16_5"], choice_type="DISCOVER")
        return True
    if cid == "LOE_110":  # Ancient Shade
        engine.shuffle_into_deck(seat, "LOE_110t", count=1)
        return True
    if cid == "LOE_116":  # Reliquary Seeker
        if minion:
            others = sum(1 for m in p.board if m.uid != minion.uid)
            if others >= 6:
                engine.add_enchantment(minion.uid, cid, "Reliquary Seeker", atk=4, hp=4)
        return True
    if cid == "LOE_118":  # Cursed Blade (fix 3 durability from catalog health field)
        if p.weapon and p.weapon.card_id == "LOE_118" and p.weapon.durability == 1:
            p.weapon.durability = p.weapon.max_durability = 3
        return True
    return False


def trigger_deathrattle(
    engine: GameEngine,
    seat: str,
    cid: str,
    orig_pos: int,
    dead_minion: Optional[Minion] = None,
) -> bool:
    p = engine.state.players[seat]
    if cid == "LOE_046":  # Huge Toad
        cands = engine.living_enemy_characters(seat)
        if cands:
            engine.deal_damage(engine.rng.choice(cands), 1, source_seat=seat, source_name="Huge Toad")
        return True
    if cid == "LOE_050":  # Mounted Raptor
        pool = collectible_pool(card_type="MINION", cost=1)
        if pool:
            engine.summon_minion(seat, engine.rng.choice(pool), pos=orig_pos)
        return True
    if cid == "LOE_061":  # Anubisath Sentinel
        alive = [m for m in p.board if m.health > 0 and not m.has_keyword("DORMANT")]
        if alive:
            engine.add_enchantment(engine.rng.choice(alive).uid, cid, "Anubisath Sentinel", atk=3, hp=3)
        return True
    if cid == "LOE_089":  # Wobbling Runts
        for tok in ("LOE_089t", "LOE_089t2", "LOE_089t3"):
            engine.summon_minion(seat, tok, pos=orig_pos)
        return True
    return False


def on_start_turn(engine: GameEngine, seat: str) -> None:
    p = engine.state.players[seat]
    curses = sum(1 for ci in p.hand if ci.card_id == "LOE_007t")
    if curses > 0:
        opp_seat = engine.other_seat(seat)
        for _ in range(curses):
            engine.deal_damage(f"hero_{seat}", 2, source_seat=opp_seat, source_name="Cursed!")


def on_eot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    p = engine.state.players[seat]
    if minion.card_id == "LOE_009":  # Obsidian Destroyer
        idx = p.board.index(minion) + 1 if minion in p.board else None
        engine.summon_minion(seat, "LOE_009t", pos=idx)
    elif minion.card_id == "LOE_024t":  # Rolling Boulder (token)
        if minion in p.board:
            idx = p.board.index(minion)
            if idx > 0:
                engine.destroy_minion(p.board[idx - 1].uid)


def on_minion_played(
    engine: GameEngine, seat: str, card: CardDef, minion: Optional[Minion]
) -> None:
    if not card.has_mechanic("BATTLECRY"):
        return
    p = engine.state.players[seat]
    for bm in list(p.board):
        if not bm.silenced and bm.card_id == "LOE_016" and (not minion or bm.uid != minion.uid):
            cands = engine.living_enemy_characters(seat)
            if cands:
                engine.deal_damage(
                    engine.rng.choice(cands),
                    2,
                    source_seat=seat,
                    source_name="Rumbling Elemental",
                    source_minion=bm,
                )


def on_spell_cast(
    engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]
) -> None:
    p = engine.state.players[seat]
    # Track friendly minion target for Djinni of Zephyrs (even if spell bounces/kills it)
    if target_id and not target_id.startswith("hero_"):
        tm = engine.find_minion(target_id)
        if tm and tm.owner == seat:
            p.extra_flags["_djinni_target"] = target_id
        else:
            p.extra_flags.pop("_djinni_target", None)
    else:
        p.extra_flags.pop("_djinni_target", None)

    # Summoning Stone
    stones = [bm for bm in list(p.board) if not bm.silenced and bm.card_id == "LOE_086"]
    if stones:
        pool = collectible_pool(card_type="MINION", cost=card.cost)
        if pool:
            for bm in stones:
                if bm in p.board and len(p.board) < 7:
                    idx = p.board.index(bm) + 1
                    engine.summon_minion(seat, engine.rng.choice(pool), pos=idx)


def on_after_spell(
    engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]
) -> None:
    p = engine.state.players[seat]
    saved_target = p.extra_flags.pop("_djinni_target", None)
    if p.extra_flags.get("_djinni_recursing"):
        return
    if not target_id or target_id != saved_target:
        return
    djinnis = [
        bm for bm in list(p.board)
        if not bm.silenced and bm.card_id == "LOE_053" and bm.uid != target_id and bm.health > 0
    ]
    if not djinnis:
        return
    from engine.effects import CHOOSE_ONE_OPTIONS as ALL_CHOOSE, cast_spell as core_cast_spell

    choose_val = 0 if card.id in ALL_CHOOSE else None
    p.extra_flags["_djinni_recursing"] = True
    try:
        for dj in djinnis:
            if dj in p.board and dj.health > 0:
                core_cast_spell(engine, seat, card.id, dj.uid, choose_val, False)
    finally:
        p.extra_flags.pop("_djinni_recursing", None)


def on_damage_hero(
    engine: GameEngine,
    target_seat: str,
    amount: int,
    source_seat: Optional[str],
    source_minion: Optional[Minion],
) -> None:
    p = engine.state.players[target_seat]
    has_animated_armor = any(not m.silenced and m.card_id == "LOE_119" for m in p.board)
    if has_animated_armor:
        if amount > 1:
            refund = amount - 1
            if p.hero.armor > 0:
                p.hero.armor += refund
            else:
                hp_refund = min(refund, max(0, p.hero.max_hp - p.hero.hp))
                p.hero.hp += hp_refund
                if refund > hp_refund:
                    p.hero.armor += refund - hp_refund
        return

    # Cursed Blade: double all damage dealt to your hero
    if amount > 0 and p.weapon and p.weapon.card_id == "LOE_118" and p.hero.hp > 0:
        if not p.extra_flags.get("_cursed_blade_recursing"):
            p.extra_flags["_cursed_blade_recursing"] = True
            try:
                engine.deal_damage(
                    f"hero_{target_seat}",
                    amount,
                    source_seat=source_seat,
                    source_name="Cursed Blade",
                )
            finally:
                p.extra_flags.pop("_cursed_blade_recursing", None)


def on_draw(engine: GameEngine, seat: str, ci: CardInstance) -> bool:
    if ci.card_id == "LOE_110t":  # Ancient Curse
        engine.add_log(f"Ancient Curse deals 7 damage to {engine.state.players[seat].name}!", seat=seat)
        engine.deal_damage(f"hero_{seat}", 7, source_seat=seat, source_name="Ancient Curse")
        return True
    return False


def recompute_auras(engine: GameEngine) -> None:
    # Eerie Statue: Can't attack unless it's the only minion on the battlefield
    total_minions = sum(len(engine.state.players[s].board) for s in ("p1", "p2"))
    if total_minions > 1:
        for s in ("p1", "p2"):
            for m in engine.state.players[s].board:
                if not m.silenced and m.card_id == "LOE_107":
                    m.keywords.add("CANT_ATTACK")

    # Jungle Moonkin: Both players have Spell Damage +2 (catalog has base_spell_damage=1)
    for s in ("p1", "p2"):
        board = engine.state.players[s].board
        opp_board = engine.state.players[engine.other_seat(s)].board
        moonkins = [m for m in board if not m.silenced and m.card_id == "LOE_051"]
        for mk in moonkins:
            mk.spell_damage += max(0, 2 - mk.base_spell_damage)
        if moonkins and opp_board:
            opp_board[0].spell_damage += 2 * len(moonkins)


def get_card_cost(engine: GameEngine, seat: str, ci: CardInstance, cost: int) -> int:
    p = engine.state.players[seat]
    if ci.card_id == "LOE_113":  # Everyfin is Awesome
        murlocs = sum(1 for m in p.board if m.race == "MURLOC")
        cost -= murlocs
    if any(not m.silenced and m.card_id == "LOE_038" for m in p.board):  # Naga Sea Witch
        return 5
    return cost


def trigger_secrets_on_minion_played(
    engine: GameEngine, def_seat: str, summoned: Minion
) -> None:
    p = engine.state.players[def_seat]
    opp = engine.state.players[summoned.owner]
    if summoned not in opp.board or len(opp.board) < 4:
        return
    for sec in list(p.secrets):
        if sec.card_id == "LOE_027":  # Sacred Trial
            engine._reveal_secret(def_seat, sec)
            engine.destroy_minion(summoned.uid)
            break


def trigger_secrets_on_hero_power(engine: GameEngine, def_seat: str) -> None:
    p = engine.state.players[def_seat]
    for sec in list(p.secrets):
        if sec.card_id == "LOE_021":  # Dart Trap
            engine._reveal_secret(def_seat, sec)
            cands = engine.living_enemy_characters(def_seat)
            if cands:
                engine.deal_damage(engine.rng.choice(cands), 5, source_seat=def_seat, source_name="Dart Trap")
            break


def resolve_pending_choice(
    engine: GameEngine, seat: str, pc: PendingChoice, picked: CardInstance, option_index: int
) -> bool:
    p = engine.state.players[seat]
    if pc.choice_type == "MUSEUM_CURATOR":
        picked.cost_mod -= 1
        engine.give_card_instance_to_hand(seat, picked, origin="choice")
        engine.add_log(
            f"{p.name} discovered {get_card(picked.card_id).name} (costs 1 less).", seat=seat
        )
        return True
    if pc.choice_type == "RAVEN_IDOL_FANDRAL":
        engine.give_card_instance_to_hand(seat, picked, origin="choice")
        pool_s = collectible_pool(hero_class=p.hero.card_class, card_type="SPELL")
        engine.start_discover(seat, "LOE_115", pool_s, choice_type="DISCOVER")
        return True
    return False
