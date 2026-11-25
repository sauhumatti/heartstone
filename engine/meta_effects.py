"""Rules for Lanternfall's expansion deck cards."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.catalog import COLLECTIBLE_CARDS, CardDef, get_card
from engine.models import SecretInstance

if TYPE_CHECKING:
    from engine.game import GameEngine
    from engine.models import Minion, PlayerState


TRIALS = {
    "LF_M21": (3, "LF_M21t"),
    "LF_M22": (6, "LF_M22t"),
}

TARGET_RULES = {
    "LF_M14": "ENEMY_CHARACTER",
    "LF_M33": "ENEMY_MINION",
}


def trial_view(player: PlayerState) -> Optional[dict]:
    if player.trial_card is None:
        return None
    from engine.expansions.helpers import QUEST_DEFS
    if player.trial_card in TRIALS:
        goal, _ = TRIALS[player.trial_card]
    elif player.trial_card in QUEST_DEFS:
        goal, _ = QUEST_DEFS[player.trial_card]
    else:
        return None
    return {"name": get_card(player.trial_card).name, "progress": player.trial_progress, "goal": goal}


def _summon_from_deck(engine: GameEngine, seat: str, index: int) -> None:
    p = engine.state.players[seat]
    if len(p.board) < 7:
        card = p.deck.pop(index)
        engine.emit("deck_remove", seat=seat)
        engine.summon_minion(seat, card.card_id)


def on_minion_played(engine: GameEngine, seat: str, card: CardDef) -> None:
    p = engine.state.players[seat]
    if card.race == "ELEMENTAL":
        p.elemental_this_turn = True
    elif card.race == "PIRATE" and not p.first_pirate_played:
        p.first_pirate_played = True
        index = next((i for i, ci in enumerate(p.deck) if ci.card_id == "LF_M12"), None)
        if index is not None:
            _summon_from_deck(engine, seat, index)

    trial = p.trial_card
    if trial == "LF_M21":
        count = p.trial_minions.get(card.id, 0) + 1
        p.trial_minions[card.id] = count
        p.trial_progress = max(p.trial_progress, count)
    elif trial == "LF_M22" and card.has_mechanic("TAUNT"):
        p.trial_progress += 1
    else:
        return
    goal, reward = TRIALS[trial]
    if p.trial_progress >= goal:
        engine.add_log(f"{p.name} completed {get_card(trial).name}.", seat=seat)
        p.trial_card = None
        engine.emit("trial", seat=seat, trial=None)
        engine.add_card_to_hand(seat, reward)
    else:
        engine.emit("trial", seat=seat, trial=trial_view(p))


def on_spell_resolved(engine: GameEngine, seat: str, card: CardDef) -> None:
    p = engine.state.players[seat]
    p.spells_played += 1
    if card.has_mechanic("SECRET"):
        p.secrets_played += 1
    if card.cost >= 4:
        for minion in list(p.board):
            if minion.card_id == "LF_M20" and not minion.silenced and minion.health > 0:
                engine.summon_minion(seat, "LF_M20t")


def on_hero_power(engine: GameEngine, seat: str) -> None:
    p = engine.state.players[seat]
    for oracle in list(p.board):
        if oracle.card_id == "LF_M04" and not oracle.silenced:
            for totem in p.board:
                if totem.race == "TOTEM":
                    engine.add_enchantment(totem.uid, oracle.card_id, oracle.name, atk=1)


def end_minion_turn(engine: GameEngine, seat: str, minion: Minion) -> None:
    if minion.card_id != "LF_M16" or not minion.attacks_this_turn:
        return
    p = engine.state.players[seat]
    candidates = [i for i, ci in enumerate(p.deck) if get_card(ci.card_id).race == "MURLOC"]
    if candidates:
        _summon_from_deck(engine, seat, engine.rng.choice(candidates))


def cast(engine: GameEngine, seat: str, cid: str, target: Optional[str], combo: bool) -> None:
    p = engine.state.players[seat]
    name = get_card(cid).name
    if cid in TRIALS:
        p.trial_card = cid
        p.trial_progress = 0
        p.trial_minions.clear()
        engine.emit("trial", seat=seat, trial=trial_view(p))
    elif cid == "LF_M01" and p.weapon:
        p.weapon.attack_bonus += 2
        if combo and p.board:
            engine.add_enchantment(engine.rng.choice(p.board).uid, cid, name, atk=2)
    elif cid == "LF_M05" and p.fallen_minions:
        minion = engine.summon_minion(seat, p.fallen_minions[-1])
        if minion:
            engine.add_enchantment(minion.uid, cid, name, set_hp=2)
    elif cid == "LF_M14":
        engine.deal_damage(target, engine.calc_spell_damage(seat, 2), source_seat=seat, source_name=name)
        engine.summon_jade_golem(seat)
    elif cid == "LF_M21t":
        p.echo_sigil = True
    elif cid == "LF_M23":
        for _ in range(2):
            engine.summon_minion(seat, "LF_M23t")
    elif cid == "LF_M30":
        opp = engine.state.players[engine.other_seat(seat)]
        count = min(3, len(opp.board))
        for minion in p.board + opp.board:
            engine.destroy_minion(minion.uid)
        for _ in range(count):
            engine.draw_card(seat)
    elif cid == "LF_M37":
        for minion in sorted(p.board, key=lambda m: m.attack, reverse=True)[:2]:
            engine.add_card_to_hand(seat, minion.card_id)
    elif cid == "LF_M39":
        from data.meta_decks import EXPANSIONS, card_in_era
        era = engine.state.deck_era if engine.state.deck_era in EXPANSIONS else "ungoro"
        for minion in list(p.board):
            cost = get_card(minion.card_id).cost + 1
            options = [
                card.id for card in COLLECTIBLE_CARDS.values()
                if card.type == "MINION" and card.cost == cost and card_in_era(card.id, era)
            ]
            if options:
                engine.transform_minion(minion.uid, engine.rng.choice(options))
        engine.apply_heal(seat, f"hero_{seat}", 2)


def battlecry(engine: GameEngine, seat: str, cid: str, minion: Optional[Minion], target: Optional[str], combo: bool) -> None:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]
    name = get_card(cid).name
    if cid == "LF_M03":
        for _ in range(min(2, 5 - len(p.secrets))):
            active = {sec.card_id for sec in p.secrets}
            candidates = [i for i, ci in enumerate(p.deck) if ci.card_id not in active and get_card(ci.card_id).has_mechanic("SECRET")]
            if not candidates:
                break
            card = get_card(p.deck.pop(engine.rng.choice(candidates)).card_id)
            sec = SecretInstance(engine._new_uid("sec"), card.id, card.card_class, card.name)
            p.secrets.append(sec)
            engine.emit("deck_remove", seat=seat)
            engine.emit("secret_add", seat=seat, uid=sec.uid, card_class=sec.card_class)
    elif cid in ("LF_M06", "LF_M07", "LF_M33"):
        p.sigils += 1
        if cid == "LF_M33" and combo and target:
            engine.deal_damage(target, 2, source_seat=seat, source_name=name, source_minion=minion)
    elif cid == "LF_M08":
        for _ in range(3 + 2 * p.sigils):
            targets = engine.living_enemy_characters(seat)
            if not targets or engine.state.phase == "GAME_OVER":
                break
            engine.deal_damage(engine.rng.choice(targets), 1, source_seat=seat, source_name=name, source_minion=minion)
    elif cid == "LF_M09":
        fallen = list(dict.fromkeys(p.fallen_deathrattles))
        for card_id in engine.rng.sample(fallen, min(3, len(fallen))):
            engine.summon_minion(seat, card_id)
    elif cid == "LF_M10":
        p.hero.armor += 5 if p.sigils >= 2 else 3
    elif cid == "LF_M11":
        engine.apply_heal(seat, f"hero_{seat}", 3)
        if p.sigils >= 2:
            for _ in range(2):
                engine.draw_card(seat)
    elif cid == "LF_M17" and engine.has_no_duplicates_in_deck(seat):
        for m in list(opp.board):
            engine.deal_damage(m.uid, 2, source_seat=seat, source_name=name, source_minion=minion)
        engine.draw_card(seat)
    elif cid == "LF_M18":
        for ci in [ci for ci in p.hand if get_card(ci.card_id).type == "MINION"][:2]:
            ci.attack_mod += 1
            ci.health_mod += 1
            card = get_card(ci.card_id)
            engine.emit("hand_buff", seat=seat, uid=ci.uid, attack=card.attack + ci.attack_mod, health=card.health + ci.health_mod)
    elif cid == "LF_M22t":
        p.hero.hero_power_id = "LF_M22p"
        p.hero.hero_power_used = False
    elif cid == "LF_M24":
        for m in p.board:
            if m != minion and m.race == "MURLOC":
                engine.add_enchantment(m.uid, cid, name, atk=1, add_keywords={"DIVINE_SHIELD"})
    elif cid == "LF_M25":
        targets = [m for m in p.board if m != minion and m.attack < 3] + [m for m in opp.board if m.attack > 3]
        for m in targets:
            engine.add_enchantment(m.uid, cid, name, atk=3 - m.attack)
    elif cid == "LF_M27":
        engine.add_card_to_hand(seat, "LF_M27t")
    elif cid == "LF_M28" and minion and p.elemental_last_turn:
        engine.add_enchantment(minion.uid, cid, name, add_keywords={"DIVINE_SHIELD"})
    elif cid == "LF_M29" and p.elemental_last_turn:
        engine.deal_damage(f"hero_{opp_seat}", 4, source_seat=seat, source_name=name, source_minion=minion)
        engine.apply_heal(seat, f"hero_{seat}", 4)
    elif cid == "LF_M34" and minion and any(get_card(ci.card_id).race == "BEAST" for ci in p.hand):
        engine.add_enchantment(minion.uid, cid, name, add_keywords={"STEALTH"})
    elif cid == "LF_M35" and p.weapon and any(m != minion and m.race == "PIRATE" for m in p.board):
        p.weapon.attack_bonus += 1
    elif cid == "LF_M36":
        for m in p.board + opp.board:
            if m != minion:
                engine.deal_damage(m.uid, 2, source_seat=seat, source_name=name, source_minion=minion)
    elif cid == "LF_M38":
        for _ in range(2):
            engine.summon_minion(seat, cid)
    elif cid == "LF_M40":
        for _ in range(min(3, p.spells_played // 3)):
            effect = engine.rng.randrange(3)
            if effect == 0:
                for enemy in engine.living_enemy_characters(seat):
                    engine.deal_damage(enemy, 1, source_seat=seat, source_name=name, source_minion=minion)
            elif effect == 1:
                engine.draw_card(seat)
            else:
                engine.summon_minion(seat, "LF_M20t")
            if engine.state.phase == "GAME_OVER":
                break
    elif cid == "LF_M41" and minion and engine.has_dragon_in_hand(seat):
        engine.add_enchantment(minion.uid, cid, name, atk=1, add_keywords={"CHARGE"})
