"""Modular expansion card registry & hook dispatcher for all 9 expansions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Optional

from engine.expansions import brm, cfm, gvg, kara, loe, naxx, og, tgt, ungoro

if TYPE_CHECKING:
    from engine.catalog import CardDef
    from engine.effects import ChooseOption
    from engine.game import GameEngine
    from engine.models import CardInstance, Minion, PendingChoice, SecretInstance

MODULES = (naxx, gvg, brm, tgt, loe, og, kara, cfm, ungoro)


def collect_dict(attr: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for mod in MODULES:
        val = getattr(mod, attr, None)
        if val:
            out.update(val)
    return out


def collect_set(attr: str) -> set[str]:
    out: set[str] = set()
    for mod in MODULES:
        val = getattr(mod, attr, None)
        if val:
            out.update(val)
    return out


TARGET_RULES: dict[str, str] = collect_dict("TARGET_RULES")
CHOOSE_ONE_OPTIONS: dict[str, tuple[Any, ...]] = collect_dict("CHOOSE_ONE_OPTIONS")
PURE_KEYWORD_CARDS: set[str] = collect_set("PURE_KEYWORD_CARDS")
COMBO_ONLY_TARGET_CARDS: set[str] = collect_set("COMBO_ONLY_TARGET_CARDS")
DRAGON_ONLY_TARGET_CARDS: set[str] = collect_set("DRAGON_ONLY_TARGET_CARDS")
CONDITIONAL_TARGET_RULES: dict[str, Callable[..., str]] = collect_dict("CONDITIONAL_TARGET_RULES")
DEATHRATTLE_CARDS: set[str] = collect_set("DEATHRATTLE_CARDS")
SECRET_CARDS: set[str] = collect_set("SECRET_CARDS")
AURA_CARDS: set[str] = collect_set("AURA_CARDS")


def cast_spell(
    engine: GameEngine,
    seat: str,
    cid: str,
    target_id: Optional[str],
    choose: Optional[int],
    was_combo: bool,
    card_instance: Optional[CardInstance] = None,
) -> bool:
    for mod in MODULES:
        fn = getattr(mod, "cast_spell", None)
        if fn and fn(engine, seat, cid, target_id, choose, was_combo, card_instance):
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
    for mod in MODULES:
        fn = getattr(mod, "trigger_battlecry", None)
        if fn and fn(engine, seat, cid, minion, target_id, choose, was_combo, card_instance):
            return True
    return False


def trigger_deathrattle(
    engine: GameEngine, seat: str, cid: str, orig_pos: int, dead_minion: Optional[Minion] = None
) -> bool:
    for mod in MODULES:
        fn = getattr(mod, "trigger_deathrattle", None)
        if fn and fn(engine, seat, cid, orig_pos, dead_minion):
            return True
    return False


def trigger_weapon_deathrattle(engine: GameEngine, seat: str, cid: str) -> bool:
    for mod in MODULES:
        fn = getattr(mod, "trigger_weapon_deathrattle", None)
        if fn and fn(engine, seat, cid):
            return True
    return False


def trigger_hero_power(engine: GameEngine, seat: str, hp_id: str, target_id: Optional[str]) -> bool:
    for mod in MODULES:
        fn = getattr(mod, "trigger_hero_power", None)
        if fn and fn(engine, seat, hp_id, target_id):
            return True
    return False


def on_inspire(engine: GameEngine, seat: str) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_inspire", None)
        if fn:
            fn(engine, seat)


def on_sot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_sot_minion", None)
        if fn:
            fn(engine, seat, minion)


def on_eot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_eot_minion", None)
        if fn:
            fn(engine, seat, minion)


def on_eot_both(engine: GameEngine, active_seat: str) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_eot_both", None)
        if fn:
            fn(engine, active_seat)


def on_minion_summoned(engine: GameEngine, seat: str, minion: Minion) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_minion_summoned", None)
        if fn:
            fn(engine, seat, minion)


def on_minion_played(engine: GameEngine, seat: str, card: CardDef, minion: Optional[Minion]) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_minion_played", None)
        if fn:
            fn(engine, seat, card, minion)


def on_card_played(engine: GameEngine, seat: str, card: CardDef, ci: CardInstance) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_card_played", None)
        if fn:
            fn(engine, seat, card, ci)


def on_spell_cast(engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_spell_cast", None)
        if fn:
            fn(engine, seat, card, target_id)


def on_after_spell(engine: GameEngine, seat: str, card: CardDef, target_id: Optional[str]) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_after_spell", None)
        if fn:
            fn(engine, seat, card, target_id)


def on_damage_minion(
    engine: GameEngine, m: Minion, amount: int, source_seat: Optional[str], source_minion: Optional[Minion]
) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_damage_minion", None)
        if fn:
            fn(engine, m, amount, source_seat, source_minion)


def on_damage_hero(
    engine: GameEngine, target_seat: str, amount: int, source_seat: Optional[str], source_minion: Optional[Minion]
) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_damage_hero", None)
        if fn:
            fn(engine, target_seat, amount, source_seat, source_minion)


def on_heal(engine: GameEngine, caster_seat: str, target_id: str, amount: int, healed_minion: bool) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_heal", None)
        if fn:
            fn(engine, caster_seat, target_id, amount, healed_minion)


def on_death(engine: GameEngine, dead_minion: Minion, orig_pos: int) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_death", None)
        if fn:
            fn(engine, dead_minion, orig_pos)


def on_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> tuple[str, bool]:
    aborted = False
    for mod in MODULES:
        fn = getattr(mod, "on_attack", None)
        if fn:
            target_id, ab = fn(engine, seat, attacker_id, target_id)
            if ab:
                return target_id, True
    return target_id, aborted


def on_after_attack(engine: GameEngine, seat: str, attacker_id: str, target_id: str) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_after_attack", None)
        if fn:
            fn(engine, seat, attacker_id, target_id)


def on_discard(engine: GameEngine, seat: str, ci: CardInstance) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_discard", None)
        if fn:
            fn(engine, seat, ci)


def on_draw(engine: GameEngine, seat: str, ci: CardInstance) -> bool:
    for mod in MODULES:
        fn = getattr(mod, "on_draw", None)
        if fn and fn(engine, seat, ci):
            return True
    return False


def on_divine_shield_lost(engine: GameEngine, m: Minion) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_divine_shield_lost", None)
        if fn:
            fn(engine, m)


def on_secret_revealed(engine: GameEngine, owner_seat: str, sec: SecretInstance) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_secret_revealed", None)
        if fn:
            fn(engine, owner_seat, sec)


def on_start_turn(engine: GameEngine, seat: str) -> None:
    for mod in MODULES:
        fn = getattr(mod, "on_start_turn", None)
        if fn:
            fn(engine, seat)


def recompute_auras(engine: GameEngine) -> None:
    for mod in MODULES:
        fn = getattr(mod, "recompute_auras", None)
        if fn:
            fn(engine)


def get_card_cost(engine: GameEngine, seat: str, ci: CardInstance, cost: int) -> int:
    for mod in MODULES:
        fn = getattr(mod, "get_card_cost", None)
        if fn:
            cost = fn(engine, seat, ci, cost)
    return cost


def get_hero_power_cost(engine: GameEngine, seat: str, cost: int) -> int:
    for mod in MODULES:
        fn = getattr(mod, "get_hero_power_cost", None)
        if fn:
            cost = fn(engine, seat, cost)
    return cost


def get_hero_power_max_uses(engine: GameEngine, seat: str) -> int:
    mx = 1
    for mod in MODULES:
        fn = getattr(mod, "get_hero_power_max_uses", None)
        if fn:
            mx = max(mx, fn(engine, seat))
    return mx


def can_play_card(engine: GameEngine, seat: str, ci: CardInstance) -> Optional[tuple[bool, str]]:
    for mod in MODULES:
        fn = getattr(mod, "can_play_card", None)
        if fn:
            res = fn(engine, seat, ci)
            if res is not None:
                return res
    return None


def trigger_secrets_on_minion_played(engine: GameEngine, def_seat: str, summoned: Minion) -> None:
    for mod in MODULES:
        fn = getattr(mod, "trigger_secrets_on_minion_played", None)
        if fn:
            fn(engine, def_seat, summoned)


def trigger_secrets_on_attack(engine: GameEngine, def_seat: str, attacker_id: str, target_id: str) -> tuple[str, bool]:
    for mod in MODULES:
        fn = getattr(mod, "trigger_secrets_on_attack", None)
        if fn:
            target_id, ab = fn(engine, def_seat, attacker_id, target_id)
            if ab:
                return target_id, True
    return target_id, False


def trigger_secrets_on_spell(engine: GameEngine, def_seat: str, card: CardDef, target_id: Optional[str]) -> bool:
    for mod in MODULES:
        fn = getattr(mod, "trigger_secrets_on_spell", None)
        if fn and fn(engine, def_seat, card, target_id):
            return True
    return False


def trigger_secrets_on_death(engine: GameEngine, def_seat: str, dead_m: Minion, orig_pos: int) -> None:
    for mod in MODULES:
        fn = getattr(mod, "trigger_secrets_on_death", None)
        if fn:
            fn(engine, def_seat, dead_m, orig_pos)


def trigger_secrets_on_sot(engine: GameEngine, seat: str) -> None:
    for mod in MODULES:
        fn = getattr(mod, "trigger_secrets_on_sot", None)
        if fn:
            fn(engine, seat)


def trigger_secrets_on_hero_power(engine: GameEngine, def_seat: str) -> None:
    for mod in MODULES:
        fn = getattr(mod, "trigger_secrets_on_hero_power", None)
        if fn:
            fn(engine, def_seat)


def resolve_pending_choice(
    engine: GameEngine, seat: str, pc: PendingChoice, picked: CardInstance, option_index: int
) -> bool:
    from engine.expansions.helpers import apply_adapt_option, resolve_kazakus_choice, start_adapt

    if pc.choice_type == "ADAPT":
        target_uids = list(pc.meta.get("target_uids") or [])
        remaining = int(pc.meta.get("remaining", 1))
        apply_adapt_option(engine, seat, picked.card_id, target_uids)
        engine.add_log(f"{engine.state.players[seat].name} adapted with {picked.card_id}.", seat=seat)
        if remaining > 1:
            alive = [u for u in target_uids if engine.find_minion(u)]
            if alive:
                start_adapt(engine, seat, alive, pc.source_card_id, remaining=remaining - 1)
        return True
    if pc.choice_type.startswith("KAZAKUS_"):
        return resolve_kazakus_choice(engine, seat, pc, picked)
    for mod in MODULES:
        fn = getattr(mod, "resolve_pending_choice", None)
        if fn and fn(engine, seat, pc, picked, option_index):
            return True
    return False
