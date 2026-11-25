"""Curse of Naxxramas (FP1) expansion card implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from engine.catalog import get_card

if TYPE_CHECKING:
    from engine.catalog import CardDef
    from engine.game import GameEngine
    from engine.models import CardInstance, Minion, SecretInstance

TARGET_RULES: dict[str, str] = {
    "FP1_025": "MINION",  # Reincarnate
}

PURE_KEYWORD_CARDS: set[str] = {
    "FP1_008",  # Spectral Knight (Elusive)
    "FP1_010",  # Maexxna (Poisonous)
}

DEATHRATTLE_CARDS: set[str] = {
    "FP1_006",  # Deathcharger (token)
    "FP1_007",  # Nerubian Egg
    "FP1_014",  # Stalagg
    "FP1_015",  # Feugen
    "FP1_022",  # Voidcaller
    "FP1_023",  # Dark Cultist
    "FP1_024",  # Unstable Ghoul
    "FP1_026",  # Anub'ar Ambusher
    "FP1_029",  # Dancing Swords
}

SECRET_CARDS: set[str] = {
    "FP1_018",  # Duplicate
    "FP1_020",  # Avenge
}

AURA_CARDS: set[str] = {
    "FP1_017",  # Nerub'ar Weblord
    "FP1_031",  # Baron Rivendare
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
    if cid == "FP1_COIN":  # The Coin (token)
        p.mana = min(10, p.mana + 1)
        return True
    if cid == "FP1_019":  # Poison Seeds
        counts = {
            s: sum(1 for m in engine.state.players[s].board if not m.has_keyword("DORMANT"))
            for s in ("p1", "p2")
        }
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                engine.destroy_minion(m.uid)
        engine.resolve_deaths()
        for s in ("p1", "p2"):
            for _ in range(counts[s]):
                engine.summon_minion(s, "FP1_019t")
        return True
    if cid == "FP1_025":  # Reincarnate
        m = engine.find_minion(target_id)
        if m and get_card(m.card_id).rarity != "LEGENDARY":
            owner = m.owner
            owner_board = engine.state.players[owner].board
            orig_pos = owner_board.index(m) if m in owner_board else len(owner_board)
            m_cid = m.card_id
            engine.destroy_minion(m.uid)
            engine.resolve_deaths()
            engine.summon_minion(owner, m_cid, pos=orig_pos)
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
    if cid == "FP1_003":  # Echoing Ooze
        if minion is not None:
            minion.extra_data["echoing_ooze_eot"] = minion.extra_data.get("echoing_ooze_eot", 0) + 1
        return True
    if cid == "FP1_016":  # Wailing Soul
        for m in list(p.board):
            if not minion or m.uid != minion.uid:
                engine.silence_minion(m.uid)
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
    opp_seat = engine.other_seat(seat)
    if cid == "FP1_006":  # Deathcharger (token)
        engine.deal_damage(f"hero_{seat}", 3, source_seat=seat, source_name="Deathcharger")
        return True
    if cid == "FP1_007":  # Nerubian Egg
        engine.summon_minion(seat, "AT_036t", pos=orig_pos)
        return True
    if cid == "FP1_014":  # Stalagg
        if engine.state.feugen_died:
            engine.summon_minion(seat, "FP1_014t", pos=orig_pos)
        return True
    if cid == "FP1_015":  # Feugen
        if engine.state.stalagg_died:
            engine.summon_minion(seat, "FP1_014t", pos=orig_pos)
        return True
    if cid == "FP1_022":  # Voidcaller
        if len(p.board) < 7:
            demons = [
                i for i, ci in enumerate(p.hand)
                if (c := get_card(ci.card_id)).type == "MINION" and c.race == "DEMON"
            ]
            if demons:
                engine.summon_minion_from_hand(seat, engine.rng.choice(demons), orig_pos)
        return True
    if cid == "FP1_023":  # Dark Cultist
        alive = [m for m in p.board if m.health > 0 and not m.has_keyword("DORMANT")]
        if alive:
            engine.add_enchantment(engine.rng.choice(alive).uid, cid, "Dark Cultist", hp=3)
        return True
    if cid == "FP1_024":  # Unstable Ghoul
        for s in ("p1", "p2"):
            for bm in list(engine.state.players[s].board):
                engine.deal_damage(bm.uid, 1, source_seat=seat, source_name="Unstable Ghoul")
        return True
    if cid == "FP1_026":  # Anub'ar Ambusher
        alive = [m for m in p.board if m.health > 0 and not m.has_keyword("DORMANT")]
        if alive:
            engine.bounce_minion(engine.rng.choice(alive))
        return True
    if cid == "FP1_029":  # Dancing Swords
        engine.draw_card(opp_seat)
        return True
    return False


def on_sot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    if minion.silenced:
        return
    if minion.card_id == "FP1_027" and minion.damaged:  # Stoneskin Gargoyle
        engine.apply_heal(seat, minion.uid, minion.damage)


def on_eot_minion(engine: GameEngine, seat: str, minion: Minion) -> None:
    cnt = int(minion.extra_data.pop("echoing_ooze_eot", 0))
    if cnt > 0:
        p = engine.state.players[seat]
        for _ in range(cnt):
            if len(p.board) >= 7:
                break
            idx = p.board.index(minion) + 1 if minion in p.board else None
            clone = engine.summon_minion(seat, minion.card_id, pos=idx)
            if clone:
                engine.copy_minion_into(minion, clone)
                clone.extra_data.pop("echoing_ooze_eot", None)
                clone.summoned_this_turn = True
                clone.attacks_this_turn = 0


def on_minion_summoned(engine: GameEngine, seat: str, minion: Minion) -> None:
    from engine.effects import DEATHRATTLE_CARDS as ALL_DR_CARDS

    is_dr = not minion.silenced and (
        minion.card_id in ALL_DR_CARDS or minion.has_keyword("DEATHRATTLE")
    )
    if not is_dr:
        return
    p = engine.state.players[seat]
    for bm in list(p.board):
        if not bm.silenced and bm.card_id == "FP1_028" and bm.uid != minion.uid:  # Undertaker
            engine.add_enchantment(bm.uid, "FP1_028", "Undertaker", atk=1, hp=1)


def get_card_cost(engine: GameEngine, seat: str, ci: CardInstance, cost: int) -> int:
    card = get_card(ci.card_id)
    if card.type == "MINION" and card.has_mechanic("BATTLECRY"):
        weblords = sum(
            1
            for s in ("p1", "p2")
            for m in engine.state.players[s].board
            if not m.silenced and m.card_id == "FP1_017"
        )
        cost += 2 * weblords
    return cost


def trigger_secrets_on_death(
    engine: GameEngine, def_seat: str, dead_m: Minion, orig_pos: int
) -> None:
    p = engine.state.players[def_seat]
    for sec in list(p.secrets):
        if sec.card_id == "FP1_018":  # Duplicate
            engine._reveal_secret(def_seat, sec)
            engine.add_card_to_hand(def_seat, dead_m.card_id)
            engine.add_card_to_hand(def_seat, dead_m.card_id)
        elif sec.card_id == "FP1_020":  # Avenge
            alive = [m for m in p.board if m.health > 0 and not m.has_keyword("DORMANT")]
            if alive:
                engine._reveal_secret(def_seat, sec)
                target = engine.rng.choice(alive)
                engine.add_enchantment(target.uid, sec.card_id, "Avenge", atk=3, hp=2)
