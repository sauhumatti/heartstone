"""One Night in Karazhan (KAR) expansion card implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from engine.catalog import get_card
from engine.expansions.helpers import collectible_pool, remove_from_deck

if TYPE_CHECKING:
    from engine.catalog import CardDef
    from engine.game import GameEngine
    from engine.models import CardInstance, Minion, PendingChoice

TARGET_RULES: dict[str, str] = {
    "KAR_013": "FRIENDLY_MINION",  # Purify
    "KAR_033": "ENEMY_MINION_ATK_LE_3",  # Book Wyrm (only when holding a Dragon)
    "KAR_041": "MINION",  # Moat Lurker
    "KAR_065": "FRIENDLY_BEAST",  # Menagerie Warden
    "KAR_075": "ANY",  # Moonglade Portal
    "KAR_077": "MINION",  # Silvermoon Portal
}

DRAGON_ONLY_TARGET_CARDS: set[str] = {
    "KAR_033",  # Book Wyrm
}


def _valet_target_rule(engine: GameEngine, seat: str, _exclude_uid: Optional[str] = None) -> str:
    return "ANY" if engine.state.players[seat].secrets else "NONE"


CONDITIONAL_TARGET_RULES: dict[str, Callable[..., str]] = {
    "KAR_092": _valet_target_rule,  # Medivh's Valet
}

PURE_KEYWORD_CARDS: set[str] = {
    "KAR_011",  # Pompous Thespian (Taunt)
    "KAR_300",  # Enchanted Raven
}

DEATHRATTLE_CARDS: set[str] = {
    "KAR_029",  # Runic Egg
    "KAR_041",  # Moat Lurker
    "KAR_094",  # Deadly Fork
}

SECRET_CARDS: set[str] = {
    "KAR_004",  # Cat Trick
}

AURA_CARDS: set[str] = {
    "KAR_006",  # Cloaked Huntress
    "KAR_711",  # Arcane Giant
    "KAR_712",  # Violet Illusionist
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
    opp = engine.state.players[engine.other_seat(seat)]

    if cid == "KAR_013":  # Purify
        engine.silence_minion(target_id)
        engine.draw_card(seat)
        return True
    if cid == "KAR_025":  # Kara Kazham!
        for tok in ("KAR_025a", "KAR_025b", "KAR_025c"):
            engine.summon_minion(seat, tok)
        return True
    if cid == "KAR_026":  # Protect the King!
        for _ in range(len(opp.board)):
            if not engine.summon_minion(seat, "KAR_026t"):
                break
        return True
    if cid == "KAR_075":  # Moonglade Portal
        engine.apply_heal(
            seat, target_id, engine.calc_spell_healing(seat, 6), from_spell_or_power=True
        )
        pool = collectible_pool(card_type="MINION", cost=6)
        if pool:
            engine.summon_minion(seat, engine.rng.choice(pool))
        return True
    if cid == "KAR_077":  # Silvermoon Portal
        engine.add_enchantment(target_id, cid, "Silvermoon Portal", atk=2, hp=2)
        pool = collectible_pool(card_type="MINION", cost=2)
        if pool:
            engine.summon_minion(seat, engine.rng.choice(pool))
        return True
    if cid == "KAR_091":  # Ironforge Portal
        p.hero.armor += 4
        pool = collectible_pool(card_type="MINION", cost=4)
        if pool:
            engine.summon_minion(seat, engine.rng.choice(pool))
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

    if cid == "KAR_009":  # Babbling Book
        pool = collectible_pool(hero_class="MAGE", card_type="SPELL", include_neutral=False)
        if pool:
            engine.add_card_to_hand(seat, engine.rng.choice(pool))
        return True
    if cid == "KAR_010":  # Nightbane Templar
        if engine.has_dragon_in_hand(seat):
            for _ in range(2):
                idx = p.board.index(minion) + 1 if minion and minion in p.board else None
                engine.summon_minion(seat, "KAR_010a", pos=idx)
        return True
    if cid == "KAR_028":  # Fool's Bane (fix 4 durability from catalog health field)
        if p.weapon and p.weapon.card_id == "KAR_028" and p.weapon.durability == 1:
            p.weapon.durability = p.weapon.max_durability = 4
        return True
    if cid == "KAR_030a":  # Pantry Spider
        idx = p.board.index(minion) + 1 if minion and minion in p.board else None
        engine.summon_minion(seat, "KAR_030", pos=idx)
        return True
    if cid == "KAR_033":  # Book Wyrm
        if target_id and engine.has_dragon_in_hand(seat):
            engine.destroy_minion(target_id)
        return True
    if cid == "KAR_037":  # Avian Watcher
        if minion and p.secrets:
            engine.add_enchantment(minion.uid, cid, "Avian Watcher", atk=1, hp=1, add_keywords={"TAUNT"})
        return True
    if cid == "KAR_041":  # Moat Lurker
        if target_id and minion:
            target = engine.find_minion(target_id)
            if target:
                t_cid, t_owner = target.card_id, target.owner
                engine.destroy_minion(target.uid)
                engine.add_enchantment(
                    minion.uid,
                    cid,
                    "Moat Lurker",
                    extra_deathrattle=f"MOAT:{t_cid}:{t_owner}",
                )
        return True
    if cid == "KAR_057":  # Ivory Knight
        pool = collectible_pool(hero_class=p.hero.card_class, card_type="SPELL")
        if pool:
            engine.start_discover(seat, cid, pool, choice_type="IVORY_KNIGHT")
        return True
    if cid == "KAR_061":  # The Curator
        for race in ("BEAST", "DRAGON", "MURLOC"):
            idxs = [i for i, ci in enumerate(p.deck) if get_card(ci.card_id).race == race]
            if idxs:
                ci = remove_from_deck(engine, seat, engine.rng.choice(idxs))
                engine.give_card_instance_to_hand(seat, ci, origin="deck")
        return True
    if cid == "KAR_062":  # Netherspite Historian
        if engine.has_dragon_in_hand(seat):
            pool = collectible_pool(hero_class=p.hero.card_class, race="DRAGON")
            engine.start_discover(seat, cid, pool, choice_type="DISCOVER")
        return True
    if cid == "KAR_065":  # Menagerie Warden
        if target_id and len(p.board) < 7:
            src = engine.find_minion(target_id)
            if src:
                idx = p.board.index(src) + 1 if src in p.board else None
                clone = engine.summon_minion(seat, src.card_id, pos=idx)
                if clone:
                    engine.copy_minion_into(src, clone)
                    clone.summoned_this_turn = True
                    clone.attacks_this_turn = 0
        return True
    if cid == "KAR_069":  # Swashburglar
        pool = collectible_pool(other_class_of=p.hero.card_class)
        if pool:
            engine.add_card_to_hand(seat, engine.rng.choice(pool))
        return True
    if cid == "KAR_070":  # Ethereal Peddler
        my_class = p.hero.card_class
        for ci in p.hand:
            c = get_card(ci.card_id)
            if c.card_class not in ("NEUTRAL", my_class):
                ci.cost_mod -= 2
        return True
    if cid == "KAR_092":  # Medivh's Valet
        if target_id and p.secrets:
            engine.deal_damage(
                target_id, 3, source_seat=seat, source_name="Medivh's Valet", source_minion=minion
            )
        return True
    if cid == "KAR_094a":  # Sharp Fork (token weapon — fix 2 durability from catalog health field)
        if p.weapon and p.weapon.card_id == "KAR_094a" and p.weapon.durability == 1:
            p.weapon.durability = p.weapon.max_durability = 2
        return True
    if cid == "KAR_095":  # Zoobot
        for race in ("BEAST", "DRAGON", "MURLOC"):
            cands = [m for m in p.board if m.race == race and (not minion or m.uid != minion.uid)]
            if cands:
                engine.add_enchantment(engine.rng.choice(cands).uid, cid, "Zoobot", atk=1, hp=1)
        return True
    if cid == "KAR_097":  # Medivh, the Guardian
        engine.equip_weapon(seat, "KAR_097t")
        if p.weapon and p.weapon.card_id == "KAR_097t" and p.weapon.durability == 1:
            p.weapon.durability = p.weapon.max_durability = 3
        return True
    if cid == "KAR_114":  # Barnes
        if len(p.board) < 7:
            minions = [ci for ci in p.deck if get_card(ci.card_id).type == "MINION"]
            if minions:
                pick = engine.rng.choice(minions)
                idx = p.board.index(minion) + 1 if minion and minion in p.board else None
                copy_m = engine.summon_minion(seat, pick.card_id, pos=idx)
                if copy_m:
                    engine.add_enchantment(copy_m.uid, cid, "Actor", set_atk=1, set_hp=1)
        return True
    if cid == "KAR_204":  # Onyx Bishop
        if p.fallen_minions and len(p.board) < 7:
            idx = p.board.index(minion) + 1 if minion and minion in p.board else None
            engine.summon_minion(seat, engine.rng.choice(p.fallen_minions), pos=idx)
        return True
    if cid == "KAR_702":  # Menagerie Magician
        for race in ("BEAST", "DRAGON", "MURLOC"):
            cands = [m for m in p.board if m.race == race and (not minion or m.uid != minion.uid)]
            if cands:
                engine.add_enchantment(
                    engine.rng.choice(cands).uid, cid, "Menagerie Magician", atk=2, hp=2
                )
        return True
    if cid == "KAR_710":  # Arcanosmith
        idx = p.board.index(minion) + 1 if minion and minion in p.board else None
        engine.summon_minion(seat, "KAR_710m", pos=idx)
        return True
    return False


def trigger_deathrattle(
    engine: GameEngine,
    seat: str,
    cid: str,
    orig_pos: int,
    dead_minion: Optional[Minion] = None,
) -> bool:
    if cid == "KAR_029":  # Runic Egg
        engine.draw_card(seat)
        return True
    if cid == "KAR_041":  # Moat Lurker (resummon is handled via MOAT enchantment)
        return True
    if cid == "KAR_094":  # Deadly Fork
        engine.add_card_to_hand(seat, "KAR_094a")
        return True
    return False


def on_start_turn(engine: GameEngine, seat: str) -> None:
    # Prince Malchezaar: Start of Game — add 5 extra Legendary minions to your deck
    p = engine.state.players[seat]
    if p.extra_flags.get("malchezaar_checked"):
        return
    p.extra_flags["malchezaar_checked"] = True
    has_malchezaar = any(ci.card_id == "KAR_096" for ci in p.deck) or any(
        ci.card_id == "KAR_096" for ci in p.hand
    )
    if not has_malchezaar:
        return
    existing = {ci.card_id for ci in p.deck} | {ci.card_id for ci in p.hand} | {"KAR_096"}
    pool = [
        cid
        for cid in collectible_pool(
            hero_class=p.hero.card_class, card_type="MINION", rarity="LEGENDARY"
        )
        if cid not in existing
    ]
    for lid in engine.rng.sample(pool, min(5, len(pool))):
        engine.shuffle_into_deck(seat, lid, count=1)
    engine.add_log(
        f"Prince Malchezaar shuffled 5 extra Legendary minions into {p.name}'s deck!", seat=seat
    )


def on_eot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    if minion.card_id == "KAR_044":  # Moroes
        p = engine.state.players[seat]
        idx = p.board.index(minion) + 1 if minion in p.board else None
        engine.summon_minion(seat, "KAR_044a", pos=idx)


def on_spell_cast(
    engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]
) -> None:
    from engine.effects import BASIC_TOTEMS

    p = engine.state.players[seat]
    for bm in list(p.board):
        if bm.silenced:
            continue
        if bm.card_id == "KAR_021":  # Wicked Witchdoctor
            if len(p.board) < 7:
                idx = p.board.index(bm) + 1 if bm in p.board else None
                engine.summon_minion(seat, engine.rng.choice(BASIC_TOTEMS), pos=idx)
        elif bm.card_id == "KAR_035":  # Priest of the Feast
            engine.apply_heal(seat, f"hero_{seat}", 3)


def on_after_spell(
    engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]
) -> None:
    p = engine.state.players[seat]
    for bm in list(p.board):
        if bm in p.board and not bm.silenced and bm.health > 0 and bm.card_id == "KAR_036":
            engine.add_enchantment(bm.uid, "KAR_036", "Arcane Anomaly", hp=1)

    if p.weapon and p.weapon.card_id == "KAR_097t":  # Atiesh
        pool = collectible_pool(card_type="MINION", cost=card.cost)
        if pool:
            engine.summon_minion(seat, engine.rng.choice(pool))
        p.weapon.durability -= 1
        if p.weapon.durability <= 0:
            engine.destroy_weapon(seat)


def on_after_attack(
    engine: GameEngine, seat: str, attacker_id: str, target_id: str
) -> None:
    if attacker_id == f"hero_{seat}":
        p = engine.state.players[seat]
        if p.weapon and p.weapon.card_id == "KAR_028":  # Fool's Bane: unlimited attacks
            p.hero.attacks_this_turn = 0


def on_discard(engine: GameEngine, seat: str, ci: CardInstance) -> None:
    p = engine.state.players[seat]
    if ci.card_id == "KAR_205":  # Silverware Golem
        engine.summon_minion(seat, "KAR_205")
    imps = sum(1 for bm in p.board if not bm.silenced and bm.card_id == "KAR_089")
    for _ in range(imps):
        engine.draw_card(seat)


def recompute_auras(engine: GameEngine) -> None:
    active = engine.state.active_seat
    p = engine.state.players[active]
    if any(not m.silenced and m.card_id == "KAR_712" for m in p.board):  # Violet Illusionist
        p.hero.immune_aura = True


def get_card_cost(engine: GameEngine, seat: str, ci: CardInstance, cost: int) -> int:
    card = get_card(ci.card_id)
    p = engine.state.players[seat]
    if ci.card_id == "KAR_711":  # Arcane Giant
        cost -= len(p.spells_cast_by_id)
    if card.has_mechanic("SECRET") and any(
        not m.silenced and m.card_id == "KAR_006" for m in p.board
    ):  # Cloaked Huntress
        return 0
    return cost


def trigger_secrets_on_spell(
    engine: GameEngine, def_seat: str, card: CardDef, target_id: Optional[str]
) -> bool:
    p = engine.state.players[def_seat]
    if len(p.board) >= 7:
        return False
    for sec in list(p.secrets):
        if sec.card_id == "KAR_004":  # Cat Trick
            engine._reveal_secret(def_seat, sec)
            engine.summon_minion(def_seat, "KAR_004a")
            return True
    return False


def resolve_pending_choice(
    engine: GameEngine, seat: str, pc: PendingChoice, picked: CardInstance, option_index: int
) -> bool:
    p = engine.state.players[seat]
    if pc.choice_type == "IVORY_KNIGHT":
        engine.give_card_instance_to_hand(seat, picked, origin="choice")
        heal_amt = get_card(picked.card_id).cost
        if heal_amt > 0:
            engine.apply_heal(seat, f"hero_{seat}", heal_amt)
        engine.add_log(
            f"{p.name} discovered a spell from Ivory Knight and restored {heal_amt} Health.",
            seat=seat,
        )
        return True
    return False
