"""Campaign Mode encounter rules: boss passives, opening boards, banter, and player Lantern Relics.

All state lives in `PlayerState.extra_flags`, so existing saves and non-campaign matches are
completely untouched.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from engine.game import GameEngine


def _boss_say(engine: "GameEngine", text: str) -> None:
    if not text:
        return
    prev = (engine.state.last_emote or {}).get("id") or 0
    eid = max(int(time.time() * 1000), int(prev) + 1)
    p2 = engine.state.players["p2"]
    engine.state.last_emote = {
        "id": eid,
        "seat": "p2",
        "name": p2.name,
        "text": text,
    }


def setup_campaign(
    engine: "GameEngine",
    *,
    p1_relic: str = "none",
    p1_relic_name: str = "",
    p1_relic_text: str = "",
    p2_passive: str = "",
    p2_passive_power: int = 1,
    p2_passive_name: str = "",
    p2_passive_text: str = "",
    p2_opening_board: Optional[list[str]] = None,
    p2_intro_quote: str = "",
    p2_mid_quote: str = "",
) -> None:
    p1 = engine.state.players["p1"]
    p2 = engine.state.players["p2"]

    if p1_relic and p1_relic != "none":
        p1.extra_flags["relic"] = p1_relic
        p1.extra_flags["relic_name"] = p1_relic_name
        p1.extra_flags["relic_text"] = p1_relic_text

    if p2_passive:
        p2.extra_flags["boss_passive"] = p2_passive
        p2.extra_flags["boss_power"] = max(1, int(p2_passive_power))
        p2.extra_flags["boss_passive_name"] = p2_passive_name
        p2.extra_flags["boss_passive_text"] = p2_passive_text
        p2.extra_flags["boss_turns"] = 0

    if p2_intro_quote:
        p2.extra_flags["boss_intro"] = p2_intro_quote
        p2.extra_flags["boss_intro_said"] = False
    if p2_mid_quote:
        p2.extra_flags["boss_mid_quote"] = p2_mid_quote
        p2.extra_flags["boss_mid_said"] = False

    for cid in p2_opening_board or []:
        if len(p2.board) >= 7:
            break
        if cid == "JADE_GOLEM":
            m = engine.summon_jade_golem("p2")
        else:
            m = engine.summon_minion("p2", cid, trigger_summon=False)
        if m is not None:
            m.summoned_this_turn = False


def hero_power_cost_mod(engine: "GameEngine", seat: str, cost: int) -> int:
    p = engine.state.players[seat]
    if seat == "p1" and p.extra_flags.get("relic") == "satchel":
        return max(1, cost - 1)
    return cost


def on_turn_start(engine: "GameEngine", seat: str) -> None:
    if engine.state.phase != "PLAY" or engine.state.deck_era != "campaign":
        return

    p1 = engine.state.players["p1"]
    p2 = engine.state.players["p2"]

    # Boss opening taunt on Turn 1
    if not p2.extra_flags.get("boss_intro_said") and p2.extra_flags.get("boss_intro"):
        p2.extra_flags["boss_intro_said"] = True
        _boss_say(engine, str(p2.extra_flags["boss_intro"]))

    if seat == "p1":
        relic = p1.extra_flags.get("relic")
        if relic == "emberheart" and p1.hero.hp < p1.hero.max_hp:
            healed = engine.apply_heal("p1", "hero_p1", 2)
            if healed > 0:
                engine.add_log(f"Emberheart Flask restored {healed} Health to {p1.name}.", seat="p1")
        elif relic == "crown" and p1.board:
            target = engine.rng.choice(p1.board)
            engine.add_enchantment(target.uid, "LF_CROWN", "Crown of First Light", atk=1, hp=1)
            engine.add_log(f"Crown of First Light blessed {target.name} (+1/+1).", seat="p1")
        return

    # Boss start-of-turn passives
    passive = p2.extra_flags.get("boss_passive")
    if not passive:
        return
    power = max(1, int(p2.extra_flags.get("boss_power", 1)))
    p2.extra_flags["boss_turns"] = int(p2.extra_flags.get("boss_turns", 0)) + 1
    bturn = p2.extra_flags["boss_turns"]

    if passive == "shadow_coin":
        cap = 4 + (power - 1)
        if len(p2.hand) <= cap:
            engine.add_card_to_hand("p2", "GAME_005")
            engine.add_log(f"{p2.name}'s Shadow Coin slipped The Coin into hand.", seat="p2")
    elif passive == "silver_oath":
        summoned = 0
        for _ in range(power):
            if len(p2.board) >= 7:
                break
            if engine.summon_minion("p2", "VAN_CS2_101t"):
                summoned += 1
        if summoned:
            engine.add_log(f"{p2.name}'s Silver Oath rallied {summoned} Silver Hand Recruit(s).", seat="p2")
    elif passive == "storm_surge":
        if p2.overloaded > 0:
            cleared = min(p2.overloaded, power)
            p2.overloaded -= cleared
            p2.mana = min(10, p2.mana + cleared)
            engine.add_log(f"{p2.name}'s Storm Surge cleared {cleared} Overloaded Mana.", seat="p2")
    elif passive == "jade_bloom":
        should_summon = (bturn % 2 == 0) if power == 1 else (bturn >= 2 and len(p2.board) < 5)
        if should_summon and len(p2.board) < 7:
            g = engine.summon_jade_golem("p2")
            if g:
                engine.add_log(f"{p2.name}'s Jade Bloom sculpted a {g.attack}/{g.max_health} Jade Golem!", seat="p2")
    elif passive == "eclipse_aura":
        if len(p2.board) < 5:
            m = engine.summon_minion("p2", "VAN_CS2_065")
            if m and power > 1:
                engine.add_enchantment(m.uid, "LF_ECLIPSE", "Eclipse Aura", hp=1)
            if m:
                engine.add_log(f"{p2.name}'s Eclipse Aura summoned a Voidwalker.", seat="p2")


def on_turn_end(engine: "GameEngine", seat: str) -> None:
    if engine.state.phase != "PLAY" or engine.state.deck_era != "campaign":
        return

    p1 = engine.state.players["p1"]
    p2 = engine.state.players["p2"]

    if seat == "p1":
        if p1.extra_flags.get("relic") == "tinderbox" and p1.mana > 0:
            p1.hero.armor += 1
            engine.add_log(f"Tinderbox Charm forged +1 Armor from unspent Mana.", seat="p1")
        return

    passive = p2.extra_flags.get("boss_passive")
    if not passive:
        return
    power = max(1, int(p2.extra_flags.get("boss_power", 1)))

    if passive == "iron_guard":
        p2.hero.armor += power
        engine.add_log(f"{p2.name}'s Iron Guard forged +{power} Armor.", seat="p2")
    elif passive == "cinder_bolt":
        for _ in range(power):
            if engine.state.phase == "GAME_OVER":
                break
            targets = ["hero_p1"] + [m.uid for m in p1.board if m.health > 0]
            tid = engine.rng.choice(targets)
            engine.deal_damage(tid, 1, source_seat="p2", source_name=p2.extra_flags.get("boss_passive_name") or "Cinder Bolt")
    elif passive == "scrap_assembly":
        mechs = [m for m in p2.board if m.race == "MECHANICAL"]
        if mechs:
            target = engine.rng.choice(mechs)
            engine.add_enchantment(target.uid, "LF_SCRAP", "Scrap Assembly", atk=power, hp=power)
            engine.add_log(f"{p2.name}'s Scrap Assembly upgraded {target.name} (+{power}/+{power}).", seat="p2")
    elif passive == "crypt_call":
        summoned = 0
        for _ in range(power):
            if len(p2.board) >= 7:
                break
            if engine.summon_minion("p2", "FP1_002t"):
                summoned += 1
        if summoned:
            engine.add_log(f"{p2.name}'s Crypt Call raised {summoned} Spectral Spider(s).", seat="p2")
    elif passive == "dragon_breath":
        amt = power + 1  # 2 normal, 3 heroic
        engine.apply_heal("p2", "hero_p2", amt)
        for m in list(p2.board):
            engine.apply_heal("p2", m.uid, amt)
        engine.add_log(f"{p2.name}'s Twilight Mend restored {amt} Health to friendly characters.", seat="p2")
    elif passive == "wild_pack":
        beasts = [m for m in p2.board if m.race == "BEAST"]
        if beasts:
            target = engine.rng.choice(beasts)
            engine.add_enchantment(target.uid, "LF_PACK", "Call of the Pack", atk=power, hp=1)
            engine.add_log(f"{p2.name}'s Call of the Pack emboldened {target.name} (+{power}/+1).", seat="p2")
    elif passive == "hollow_siphon":
        engine.deal_damage("hero_p1", power, source_seat="p2", source_name="Hollow Siphon")
        if engine.state.phase != "GAME_OVER":
            engine.apply_heal("p2", "hero_p2", power)
    elif passive == "broadside":
        if p2.weapon is not None:
            dmg = 2 if power == 1 else 3
            engine.deal_damage("hero_p1", dmg, source_seat="p2", source_name="Broadside")
    elif passive == "eclipse_aura":
        engine.deal_damage("hero_p1", power, source_seat="p2", source_name="Eclipse Drain")
        if engine.state.phase != "GAME_OVER":
            engine.apply_heal("p2", "hero_p2", power)


def on_boss_damaged(engine: "GameEngine") -> None:
    if engine.state.phase != "PLAY" or engine.state.deck_era != "campaign":
        return
    p2 = engine.state.players["p2"]
    if p2.extra_flags.get("boss_mid_said"):
        return
    quote = p2.extra_flags.get("boss_mid_quote")
    if quote and 0 < p2.hero.hp <= (p2.hero.max_hp // 2):
        p2.extra_flags["boss_mid_said"] = True
        _boss_say(engine, str(quote))


def campaign_view(engine: "GameEngine") -> Optional[dict[str, Any]]:
    if engine.state.deck_era != "campaign":
        return None
    p1 = engine.state.players["p1"]
    p2 = engine.state.players["p2"]
    bp = p2.extra_flags.get("boss_passive")
    relic = p1.extra_flags.get("relic")
    if not bp and not relic:
        return None
    return {
        "boss_passive": bp or "",
        "boss_passive_name": p2.extra_flags.get("boss_passive_name") or "",
        "boss_passive_text": p2.extra_flags.get("boss_passive_text") or "",
        "relic": relic or "none",
        "relic_name": p1.extra_flags.get("relic_name") or "",
        "relic_text": p1.extra_flags.get("relic_text") or "",
    }
