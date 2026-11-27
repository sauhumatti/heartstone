"""Shared mechanics and event-safe primitives for expansion card implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

from engine.catalog import COLLECTIBLE_CARDS, CardDef, get_card
from engine.models import CardInstance, Minion, PendingChoice, SecretInstance

if TYPE_CHECKING:
    from engine.game import GameEngine


ADAPT_OPTIONS: tuple[str, ...] = (
    "UNG_999t2",   # Living Spores: Deathrattle: Summon two 1/1 Plants.
    "UNG_999t3",   # Flaming Claws: +3 Attack
    "UNG_999t4",   # Rocky Carapace: +3 Health
    "UNG_999t5",   # Liquid Membrane: Elusive
    "UNG_999t6",   # Massive: Taunt
    "UNG_999t7",   # Lightning Speed: Windfury
    "UNG_999t8",   # Crackling Shield: Divine Shield
    "UNG_999t10",  # Shrouding Mist: Stealth until your next turn
    "UNG_999t13",  # Poison Spit: Poisonous
    "UNG_999t14",  # Volcanic Might: +1/+1
)

KAZAKUS_COST_OPTIONS: tuple[str, ...] = ("CFM_621t11", "CFM_621t12", "CFM_621t13")
KAZAKUS_EFFECTS_BY_COST: dict[int, tuple[str, ...]] = {
    1: ("CFM_621t2", "CFM_621t3", "CFM_621t4", "CFM_621t5", "CFM_621t6", "CFM_621t8", "CFM_621t9", "CFM_621t10", "CFM_621t37"),
    5: ("CFM_621t16", "CFM_621t17", "CFM_621t18", "CFM_621t19", "CFM_621t20", "CFM_621t21", "CFM_621t22", "CFM_621t23", "CFM_621t24", "CFM_621t38"),
    10: ("CFM_621t25", "CFM_621t26", "CFM_621t27", "CFM_621t28", "CFM_621t29", "CFM_621t30", "CFM_621t31", "CFM_621t32", "CFM_621t33", "CFM_621t39"),
}
KAZAKUS_POTION_ID: dict[int, str] = {1: "CFM_621t", 5: "CFM_621t14", 10: "CFM_621t15"}

QUEST_DEFS: dict[str, tuple[int, str]] = {
    "UNG_028": (6, "UNG_028t"),   # Open the Waygate -> Time Warp
    "UNG_067": (4, "UNG_067t1"),  # The Caverns Below -> Crystal Core
    "UNG_116": (5, "UNG_116t"),   # Jungle Giants -> Barnabus the Stomper
    "UNG_829": (6, "UNG_829t1"),  # Lakkari Sacrifice -> Nether Portal
    "UNG_920": (7, "UNG_920t1"),  # The Marsh Queen -> Queen Carnassa
    "UNG_934": (7, "UNG_934t1"),  # Fire Plume's Heart -> Sulfuras
    "UNG_940": (7, "UNG_940t8"),  # Awaken the Makers -> Amara, Warden of Hope
    "UNG_942": (10, "UNG_942t"),  # Unite the Murlocs -> Megafin
    "UNG_954": (6, "UNG_954t1"),  # The Last Kaleidosaur -> Galvadon
}


def collectible_pool(
    *,
    hero_class: Optional[str] = None,
    allowed_classes: Optional[tuple[str, ...]] = None,
    other_class_of: Optional[str] = None,
    card_type: Optional[str] = None,
    race: Optional[str] = None,
    cost: Optional[int] = None,
    min_cost: Optional[int] = None,
    max_cost: Optional[int] = None,
    rarity: Optional[str] = None,
    mechanic: Optional[str] = None,
    prefix: Optional[str] = None,
    include_neutral: bool = True,
    predicate: Optional[Callable[[CardDef], bool]] = None,
) -> list[str]:
    out: list[str] = []
    for cid, c in COLLECTIBLE_CARDS.items():
        if hero_class is not None:
            if include_neutral:
                if not c.allowed_for_class(hero_class):
                    continue
            else:
                if c.card_class != hero_class and hero_class not in c.classes:
                    continue
        if allowed_classes is not None:
            if c.card_class not in allowed_classes and not any(cl in c.classes for cl in allowed_classes):
                continue
        if other_class_of is not None:
            if c.card_class in ("NEUTRAL", other_class_of):
                continue
        if card_type is not None and c.type != card_type:
            continue
        if race is not None and c.race != race:
            continue
        if cost is not None and c.cost != cost:
            continue
        if min_cost is not None and c.cost < min_cost:
            continue
        if max_cost is not None and c.cost > max_cost:
            continue
        if rarity is not None and c.rarity != rarity:
            continue
        if mechanic is not None and not c.has_mechanic(mechanic):
            continue
        if prefix is not None and not cid.startswith(prefix):
            continue
        if predicate is not None and not predicate(c):
            continue
        out.append(cid)
    return out


def remove_from_deck(engine: GameEngine, seat: str, index: int) -> CardInstance:
    p = engine.state.players[seat]
    ci = p.deck.pop(index)
    engine.emit("deck_remove", seat=seat)
    return ci


def remove_from_hand(engine: GameEngine, seat: str, index: int) -> CardInstance:
    p = engine.state.players[seat]
    ci = p.hand.pop(index)
    engine.emit("hand_remove", seat=seat, uid=ci.uid, hand_index=index)
    return ci


def summon_from_deck(engine: GameEngine, seat: str, index: int, pos: Optional[int] = None) -> Optional[Minion]:
    p = engine.state.players[seat]
    if len(p.board) >= 7:
        return None
    ci = remove_from_deck(engine, seat, index)
    return engine.summon_minion(seat, ci.card_id, pos=pos, hand_card=ci)


def put_secret_into_play(engine: GameEngine, seat: str, card_id: str) -> bool:
    p = engine.state.players[seat]
    if len(p.secrets) >= 5 or any(s.card_id == card_id for s in p.secrets):
        return False
    scard = get_card(card_id)
    sec = SecretInstance(engine._new_uid("sec"), scard.id, scard.card_class, scard.name)
    p.secrets.append(sec)
    engine.emit("secret_add", seat=seat, uid=sec.uid, card_class=scard.card_class)
    return True


def buff_hand_card(
    engine: GameEngine, seat: str, ci: CardInstance, atk: int = 0, hp: int = 0, cost_mod: int = 0
) -> None:
    ci.attack_mod += atk
    ci.health_mod += hp
    ci.cost_mod += cost_mod
    card = get_card(ci.card_id)
    if card.attack is not None and card.health is not None and (atk or hp):
        engine.emit(
            "hand_buff",
            seat=seat,
            uid=ci.uid,
            attack=card.attack + ci.attack_mod,
            health=card.health + ci.health_mod,
        )


def buff_hand_minions(
    engine: GameEngine,
    seat: str,
    atk: int = 0,
    hp: int = 0,
    predicate: Optional[Callable[[CardDef], bool]] = None,
    count: Optional[int] = None,
) -> list[CardInstance]:
    p = engine.state.players[seat]
    cands = [
        ci for ci in p.hand
        if (c := get_card(ci.card_id)).type == "MINION" and (predicate is None or predicate(c))
    ]
    if not cands:
        return []
    targets = cands if count is None else engine.rng.sample(cands, min(count, len(cands)))
    for ci in targets:
        buff_hand_card(engine, seat, ci, atk=atk, hp=hp)
    return targets


def buff_cthun(engine: GameEngine, seat: str, atk: int = 0, hp: int = 0, taunt: bool = False) -> None:
    p = engine.state.players[seat]
    p.cthun_atk += atk
    p.cthun_hp += hp
    if taunt:
        p.cthun_taunt = True
    for m in p.board:
        if m.card_id == "OG_280":
            kws = {"TAUNT"} if taunt else None
            engine.add_enchantment(m.uid, "OG_280", "C'Thun Buff", atk=atk, hp=hp, add_keywords=kws)
    for ci in p.hand:
        if ci.card_id == "OG_280":
            buff_hand_card(engine, seat, ci, atk=atk, hp=hp)
    if atk or hp or taunt:
        engine.add_log(f"{p.name}'s C'Thun is now {p.cthun_atk}/{p.cthun_hp}.", seat=seat)


def reveal_joust(engine: GameEngine, seat: str, label: str = "Joust") -> tuple[bool, Optional[int]]:
    """Joust: reveal a random minion from each deck; `seat` wins if its card costs more.
    No minion in its own deck loses, none in the other deck wins. Both cards are shown
    to both players (a `joust` event) and stay in their decks.
    Returns (won, index in `seat`'s deck of the card it revealed)."""
    p = engine.state.players[seat]
    opp = engine.state.players[engine.other_seat(seat)]
    my_m = [(i, get_card(ci.card_id)) for i, ci in enumerate(p.deck) if get_card(ci.card_id).type == "MINION"]
    op_m = [get_card(ci.card_id) for ci in opp.deck if get_card(ci.card_id).type == "MINION"]
    if not my_m:
        engine.add_log(f"{label}: {p.name} had no minions and lost.", seat=seat)
        engine.emit("joust", seat=seat, mine=None, theirs=None, won=False)
        return False, None
    idx, mine = engine.rng.choice(my_m)
    if not op_m:
        engine.add_log(f"{label}: {p.name} revealed {mine.name} ({mine.cost}) and won!", seat=seat)
        engine.emit("joust", seat=seat, mine=mine.to_dict(), theirs=None, won=True)
        return True, idx
    theirs = engine.rng.choice(op_m)
    won = mine.cost > theirs.cost
    engine.add_log(
        f"{label}: {mine.name} ({mine.cost}) vs {theirs.name} ({theirs.cost}) -> {'Won!' if won else 'Lost.'}",
        seat=seat,
    )
    engine.emit("joust", seat=seat, mine=mine.to_dict(), theirs=theirs.to_dict(), won=won)
    return won, idx


def joust(engine: GameEngine, seat: str) -> bool:
    return reveal_joust(engine, seat)[0]


def evolve_minion(engine: GameEngine, minion: Minion, delta: int = 1) -> Optional[Minion]:
    cur_cost = get_card(minion.card_id).cost
    target_cost = max(0, cur_cost + delta)
    pool = collectible_pool(card_type="MINION", cost=target_cost)
    if not pool:
        return minion
    return engine.transform_minion(minion.uid, engine.rng.choice(pool))


def trigger_minion_deathrattle(engine: GameEngine, minion: Minion) -> None:
    from engine.effects import trigger_deathrattle
    board = engine.state.players[minion.owner].board
    pos = board.index(minion) if minion in board else len(board)
    trigger_deathrattle(engine, minion, pos)


def start_adapt(
    engine: GameEngine,
    seat: str,
    target_uids: list[str],
    source_card_id: str,
    remaining: int = 1,
) -> None:
    if not target_uids or remaining <= 0:
        return
    picked = engine.rng.sample(list(ADAPT_OPTIONS), 3)
    opts = [CardInstance(uid=engine._new_uid("c"), card_id=cid) for cid in picked]
    engine.state.pending_choice = PendingChoice(
        seat=seat,
        choice_type="ADAPT",
        source_card_id=source_card_id,
        options=opts,
        meta={"target_uids": list(target_uids), "remaining": remaining},
    )


def apply_adapt_option(engine: GameEngine, seat: str, adapt_id: str, target_uids: list[str]) -> None:
    for uid in target_uids:
        m = engine.find_minion(uid)
        if not m:
            continue
        if adapt_id == "UNG_999t2":  # Living Spores
            engine.add_enchantment(uid, adapt_id, "Living Spores", extra_deathrattle="SUMMON:UNG_999t2t1:2")
        elif adapt_id == "UNG_999t3":  # Flaming Claws
            engine.add_enchantment(uid, adapt_id, "Flaming Claws", atk=3)
        elif adapt_id == "UNG_999t4":  # Rocky Carapace
            engine.add_enchantment(uid, adapt_id, "Rocky Carapace", hp=3)
        elif adapt_id == "UNG_999t5":  # Liquid Membrane
            engine.add_enchantment(uid, adapt_id, "Liquid Membrane", add_keywords={"ELUSIVE"})
        elif adapt_id == "UNG_999t6":  # Massive
            engine.add_enchantment(uid, adapt_id, "Massive", add_keywords={"TAUNT"})
        elif adapt_id == "UNG_999t7":  # Lightning Speed
            engine.add_enchantment(uid, adapt_id, "Lightning Speed", add_keywords={"WINDFURY"})
        elif adapt_id == "UNG_999t8":  # Crackling Shield
            engine.add_enchantment(uid, adapt_id, "Crackling Shield", add_keywords={"DIVINE_SHIELD"})
        elif adapt_id == "UNG_999t10":  # Shrouding Mist
            engine.add_enchantment(uid, adapt_id, "Shrouding Mist", add_keywords={"STEALTH"})
            m.stealth_until_sot_of = seat
        elif adapt_id == "UNG_999t13":  # Poison Spit
            engine.add_enchantment(uid, adapt_id, "Poison Spit", add_keywords={"POISONOUS"})
        elif adapt_id == "UNG_999t14":  # Volcanic Might
            engine.add_enchantment(uid, adapt_id, "Volcanic Might", atk=1, hp=1)


def advance_quest(engine: GameEngine, seat: str, quest_id: str, delta: int = 1) -> None:
    p = engine.state.players[seat]
    if p.trial_card != quest_id or quest_id not in QUEST_DEFS:
        return
    p.trial_progress += delta
    goal, reward_id = QUEST_DEFS[quest_id]
    if p.trial_progress >= goal:
        engine.add_log(f"{p.name} completed {get_card(quest_id).name}!", seat=seat)
        p.trial_card = None
        engine.emit("trial", seat=seat, trial=None)
        engine.add_card_to_hand(seat, reward_id)
    else:
        from engine.meta_effects import trial_view
        engine.emit("trial", seat=seat, trial=trial_view(p))


def start_kazakus(engine: GameEngine, seat: str) -> None:
    opts = [CardInstance(uid=engine._new_uid("c"), card_id=cid) for cid in KAZAKUS_COST_OPTIONS]
    engine.state.pending_choice = PendingChoice(
        seat=seat,
        choice_type="KAZAKUS_COST",
        source_card_id="CFM_621",
        options=opts,
        meta={},
    )


def resolve_kazakus_choice(engine: GameEngine, seat: str, pc: PendingChoice, picked: CardInstance) -> bool:
    ct = pc.choice_type
    if ct == "KAZAKUS_COST":
        cost_map = {"CFM_621t11": 1, "CFM_621t12": 5, "CFM_621t13": 10}
        tier = cost_map.get(picked.card_id, 5)
        pool = list(KAZAKUS_EFFECTS_BY_COST[tier])
        choices = engine.rng.sample(pool, 3)
        opts = [CardInstance(uid=engine._new_uid("c"), card_id=cid) for cid in choices]
        engine.state.pending_choice = PendingChoice(
            seat=seat,
            choice_type="KAZAKUS_EFFECT1",
            source_card_id="CFM_621",
            options=opts,
            meta={"tier": tier},
        )
        return True
    if ct == "KAZAKUS_EFFECT1":
        tier = int(pc.meta.get("tier", 5))
        first = picked.card_id
        pool = [cid for cid in KAZAKUS_EFFECTS_BY_COST[tier] if cid != first]
        choices = engine.rng.sample(pool, 3)
        opts = [CardInstance(uid=engine._new_uid("c"), card_id=cid) for cid in choices]
        engine.state.pending_choice = PendingChoice(
            seat=seat,
            choice_type="KAZAKUS_EFFECT2",
            source_card_id="CFM_621",
            options=opts,
            meta={"tier": tier, "first": first},
        )
        return True
    if ct == "KAZAKUS_EFFECT2":
        tier = int(pc.meta.get("tier", 5))
        first = pc.meta.get("first", "")
        second = picked.card_id
        potion_id = KAZAKUS_POTION_ID[tier]
        ci = CardInstance(
            uid=engine._new_uid("c"),
            card_id=potion_id,
            custom_effects=[e for e in (first, second) if e],
        )
        engine.give_card_instance_to_hand(seat, ci, origin="created")
        return True
    return False


def cast_kazakus_effect(engine: GameEngine, seat: str, eff_id: str) -> None:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]
    sd = lambda b: engine.calc_spell_damage(seat, b)

    # Damage single random enemy (Heart of Fire)
    if eff_id in ("CFM_621t2", "CFM_621t16", "CFM_621t25"):
        dmg = { "CFM_621t2": 3, "CFM_621t16": 5, "CFM_621t25": 8 }[eff_id]
        cands = engine.living_enemy_characters(seat)
        if cands:
            engine.deal_damage(engine.rng.choice(cands), sd(dmg), source_seat=seat, source_name="Kazakus Potion")
    # Armor (Stonescale Oil)
    elif eff_id in ("CFM_621t3", "CFM_621t17", "CFM_621t26"):
        p.hero.armor += {"CFM_621t3": 4, "CFM_621t17": 7, "CFM_621t26": 10}[eff_id]
    # AoE minions (Felbloom)
    elif eff_id in ("CFM_621t4", "CFM_621t18", "CFM_621t29"):
        dmg = {"CFM_621t4": 2, "CFM_621t18": 4, "CFM_621t29": 6}[eff_id]
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                engine.deal_damage(m.uid, sd(dmg), source_seat=seat, source_name="Kazakus Potion")
    # Freeze enemy minions (Icecap)
    elif eff_id in ("CFM_621t5", "CFM_621t19", "CFM_621t27"):
        cnt = {"CFM_621t5": 1, "CFM_621t19": 2, "CFM_621t27": 3}[eff_id]
        cands = [m for m in opp.board if not m.frozen] or list(opp.board)
        for m in engine.rng.sample(cands, min(cnt, len(cands))):
            engine.freeze_character(m.uid)
    # Draw cards (Kingsblood)
    elif eff_id in ("CFM_621t6", "CFM_621t22", "CFM_621t30"):
        cnt = {"CFM_621t6": 1, "CFM_621t22": 2, "CFM_621t30": 3}[eff_id]
        for _ in range(cnt):
            engine.draw_card(seat)
    # Add random Demons (Shadow Oil)
    elif eff_id in ("CFM_621t8", "CFM_621t23", "CFM_621t31"):
        cnt = {"CFM_621t8": 1, "CFM_621t23": 2, "CFM_621t31": 3}[eff_id]
        demons = collectible_pool(card_type="MINION", race="DEMON")
        for _ in range(cnt):
            if demons:
                engine.add_card_to_hand(seat, engine.rng.choice(demons))
    # Give friendly minions Health (Goldthorn)
    elif eff_id in ("CFM_621t9", "CFM_621t24", "CFM_621t32"):
        hp = {"CFM_621t9": 2, "CFM_621t24": 4, "CFM_621t32": 6}[eff_id]
        for m in list(p.board):
            engine.add_enchantment(m.uid, "CFM_621t", "Goldthorn", hp=hp)
    # Summon Demon (Netherbloom)
    elif eff_id in ("CFM_621t10", "CFM_621t20", "CFM_621t28"):
        tok = {"CFM_621t10": "CFM_621_m4", "CFM_621t20": "CFM_621_m2", "CFM_621t28": "CFM_621_m3"}[eff_id]
        engine.summon_minion(seat, tok)
    # Resurrect friendly minions (Ichor of Undeath)
    elif eff_id in ("CFM_621t37", "CFM_621t38", "CFM_621t39"):
        cnt = {"CFM_621t37": 1, "CFM_621t38": 2, "CFM_621t39": 3}[eff_id]
        if p.fallen_minions:
            for cid in engine.rng.sample(p.fallen_minions, min(cnt, len(p.fallen_minions))):
                engine.summon_minion(seat, cid)
    # Polymorph Sheep (Mystic Wool)
    elif eff_id == "CFM_621t21":
        if opp.board:
            engine.transform_minion(engine.rng.choice(opp.board).uid, "CFM_621_m5")
    elif eff_id == "CFM_621t33":
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                engine.transform_minion(m.uid, "CFM_621_m5")


def cast_random_spell(engine: GameEngine, seat: str, spell_id: str) -> None:
    """Cast a spell with random valid target/choose (for Yogg-Saron, Servant, Primalist)."""
    from engine.effects import CHOOSE_ONE_OPTIONS, cast_spell
    card = get_card(spell_id)
    if card.type != "SPELL":
        return
    if card.has_mechanic("SECRET"):
        put_secret_into_play(engine, seat, spell_id)
        return
    choose: Optional[int] = None
    if spell_id in CHOOSE_ONE_OPTIONS:
        choose = engine.rng.choice([0, 1])
        rule = CHOOSE_ONE_OPTIONS[spell_id][choose].target_rule
    else:
        rule = engine.get_target_rule(spell_id, None, False, seat=seat)
    target_id: Optional[str] = None
    if rule != "NONE":
        vt = engine.get_valid_targets(seat, rule, is_spell_or_power=True)
        if not vt:
            return
        target_id = engine.rng.choice(vt)
    engine.add_log(f"Randomly cast {card.name}!", seat=seat)
    cast_spell(engine, seat, spell_id, target_id, choose, False)
    engine.resolve_deaths()
    engine.recompute_auras()


def replace_hero(
    engine: GameEngine, seat: str, name: str, max_hp: int, hero_power_id: str, is_ragnaros: bool = False
) -> None:
    p = engine.state.players[seat]
    p.hero.name = name
    p.hero.max_hp = max_hp
    p.hero.hp = max_hp
    p.hero.armor = 0
    p.hero.hero_power_id = hero_power_id
    p.hero.hero_power_used = False
    p.hero.hero_power_uses_this_turn = 0
    p.hero.is_ragnaros = is_ragnaros
    engine.add_log(f"{p.name}'s hero became {name}!", seat=seat)
