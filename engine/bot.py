from __future__ import annotations

import random
from typing import Optional

from engine.game import GameEngine, GameError


def run_bot_mulligan(engine: GameEngine, seat: str) -> None:
    p = engine.state.players[seat]
    if p.mulligan_done or engine.state.phase != "MULLIGAN":
        return
    view = engine.serialize_for_seat(seat)
    replace = [c["index"] for c in view["me"]["hand"] if c["cost"] > 3]
    engine.submit_mulligan(seat, replace)


def _pick_target(view: dict, valid_targets: list[str], card_name: str, rule: str) -> Optional[str]:
    if not valid_targets:
        return None
    opp = view["opponent"]
    me = view["me"]
    enemy_hero = opp["hero"]["id"]
    my_hero = me["hero"]["id"]
    enemy_minions = {m["uid"]: m for m in opp["board"]}
    my_minions = {m["uid"]: m for m in me["board"]}

    # Beneficial buffs / heals
    beneficial_keywords = (
        "Blessing", "Mark of", "Power Word", "Divine Spirit", "Inner Fire",
        "Shattered Sun", "Houndmaster", "Argent Protector", "Temple Enforcer",
        "Windspeaker", "Windfury", "Rockbiter", "Charge", "Cold Blood",
        "Ancestral Healing", "Ancestral Spirit", "Power Overwhelming",
        "Dark Iron Dwarf", "Abusive Sergeant", "Master of Disguise", "Rampage",
        "Bananas", "Demonfire", "Bestial Wrath", "Hand of Protection",
        "Lesser Heal", "Healing Touch", "Holy Light", "Lay on Hands",
        "Voodoo Doctor", "Earthen Ring", "Ancient Secrets",
    )
    is_beneficial = any(k in card_name for k in beneficial_keywords)
    if is_beneficial:
        friendly = [t for t in valid_targets if t == my_hero or t in my_minions]
        if friendly:
            # Prefer damaged target for heals, else highest attack minion
            if "Heal" in card_name or "Light" in card_name or "Secrets" in card_name or "Voodoo" in card_name or "Earthen" in card_name:
                dmg_m = [t for t in friendly if t in my_minions and my_minions[t]["damaged"]]
                if dmg_m:
                    return max(dmg_m, key=lambda t: my_minions[t]["attack"])
                if my_hero in friendly:
                    return my_hero
            m_choices = [t for t in friendly if t in my_minions]
            if m_choices:
                return max(m_choices, key=lambda t: my_minions[t]["attack"] + my_minions[t]["health"])
            return friendly[0]

    # Bounce friendly battlecry minions? Avoid bouncing enemy unless Sap/Kidnapper
    if card_name in ("Shadowstep", "Youthful Brewmaster", "Ancient Brewmaster"):
        m_choices = [t for t in valid_targets if t in my_minions]
        if m_choices:
            return min(m_choices, key=lambda t: my_minions[t]["attack"] + my_minions[t]["health"])

    # Offensive / removal -> prefer enemy targets
    enemies = [t for t in valid_targets if t == enemy_hero or t in enemy_minions]
    if enemies:
        # Lethal on enemy hero check
        if enemy_hero in enemies and opp["hero"]["hp"] <= 6:
            return enemy_hero
        e_minions = [t for t in enemies if t in enemy_minions]
        if e_minions:
            return max(e_minions, key=lambda t: enemy_minions[t]["attack"] * 2 + enemy_minions[t]["health"])
        return enemy_hero

    return valid_targets[0]


def run_bot_turn(engine: GameEngine, seat: str) -> None:
    if engine.state.phase != "PLAY" or engine.state.active_seat != seat:
        return

    rng = random.Random()
    for _ in range(40):
        if engine.state.phase != "PLAY" or engine.state.active_seat != seat:
            return
        view = engine.serialize_for_seat(seat)

        if view.get("pending_choice"):
            opts = view["pending_choice"]["options"]
            best_i = min(range(len(opts)), key=lambda i: opts[i]["cost"])
            engine.resolve_pending_choice(seat, best_i)
            continue

        # 1. Play highest-cost playable card (prefer minions & board development, avoid Silencing own stuff etc.)
        playable = [c for c in view["me"]["hand"] if c["can_play"]]
        # Filter out self-harmful target-only cards (e.g. Assassinate/Shadow Word when only own minion valid? Assassinate is ENEMY_MINION so safe; Silence/Hex/Humility check!)
        chosen_play = None
        for c in sorted(playable, key=lambda x: (-x["cost"], x["type"] != "MINION")):
            if c["choose_options"]:
                valid_opts = [o for o in c["choose_options"] if o["playable"]]
                if not valid_opts:
                    continue
                opt = valid_opts[0]
                tgt = _pick_target(view, opt["valid_targets"], c["name"], opt["target_rule"])
                if opt["target_rule"] != "NONE" and tgt is None:
                    continue
                chosen_play = (c["index"], opt["index"], tgt)
                break
            else:
                tgt = _pick_target(view, c["valid_targets"], c["name"], c["target_rule"])
                # Avoid casting negative spells on friendly minions
                harmful_to_friendly = (
                    "Humility", "Polymorph", "Hex", "Silence", "Hunter's Mark",
                    "Fireball", "Frostbolt", "Pyroblast", "Moonfire", "Arcane Shot",
                    "Lightning Bolt", "Lava Burst", "Shadow Bolt", "Siphon Soul",
                    "Naturalize", "Mortal Coil", "Backstab", "Eviscerate", "Shiv",
                    "Earth Shock", "Ironbeak Owl", "Spellbreaker", "Keeper of the Grove",
                )
                if tgt and tgt in {m["uid"] for m in view["me"]["board"]} and any(h in c["name"] for h in harmful_to_friendly):
                    if c["type"] == "SPELL":
                        continue
                if tgt == view["me"]["hero"]["id"] and any(h in c["name"] for h in harmful_to_friendly):
                    if c["type"] == "SPELL":
                        continue
                if c["target_required"] and tgt is None:
                    continue
                chosen_play = (c["index"], None, tgt)
                break

        if chosen_play is not None:
            h_idx, ch, tgt = chosen_play
            try:
                engine.play_card(seat, h_idx, target_id=tgt, choose=ch)
                continue
            except GameError:
                pass

        # 2. Attack with ready minions & hero
        attacked = False
        for m in view["me"]["board"]:
            if m["can_attack"] and m["legal_attack_targets"]:
                tgts = m["legal_attack_targets"]
                enemy_hero = view["opponent"]["hero"]["id"]
                e_map = {em["uid"]: em for em in view["opponent"]["board"]}
                # Go face if lethal or favorable, else trade favorably
                total_board_atk = sum(bm["attack"] for bm in view["me"]["board"] if bm["can_attack"])
                if enemy_hero in tgts and total_board_atk >= view["opponent"]["hero"]["hp"] + view["opponent"]["hero"]["armor"]:
                    pick = enemy_hero
                else:
                    e_choices = [t for t in tgts if t in e_map]
                    if e_choices:
                        # Prefer killing high-attack minion where attacker survives or trades up
                        survivable = [t for t in e_choices if e_map[t]["health"] <= m["attack"] and e_map[t]["attack"] < m["health"]]
                        if survivable:
                            pick = max(survivable, key=lambda t: e_map[t]["attack"] + e_map[t]["health"])
                        elif enemy_hero in tgts:
                            pick = enemy_hero
                        else:
                            pick = max(e_choices, key=lambda t: e_map[t]["attack"])
                    else:
                        pick = tgts[0]
                engine.attack(seat, m["uid"], pick)
                attacked = True
                break
        if attacked:
            continue

        if view["me"]["hero"]["can_attack"] and view["me"]["hero"]["legal_attack_targets"]:
            tgts = view["me"]["hero"]["legal_attack_targets"]
            enemy_hero = view["opponent"]["hero"]["id"]
            pick = enemy_hero if enemy_hero in tgts else rng.choice(tgts)
            engine.attack(seat, view["me"]["hero"]["id"], pick)
            continue

        # 3. Hero Power
        hp_info = view["me"]["hero"]["hero_power"]
        if hp_info["can_use"]:
            tgt = _pick_target(view, hp_info["valid_targets"], hp_info["name"], hp_info["target_rule"])
            if hp_info["target_rule"] == "NONE" or tgt is not None:
                try:
                    engine.use_hero_power(seat, target_id=tgt)
                    continue
                except GameError:
                    pass

        break

    if engine.state.phase == "PLAY" and engine.state.active_seat == seat:
        engine.end_turn(seat)
