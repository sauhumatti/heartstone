from __future__ import annotations

from typing import Any, Optional


def resolve_target(view: dict[str, Any], raw: Optional[str]) -> Optional[str]:
    """Turn a command-line alias (hero, enemy_hero, m0, e2) into a character id."""
    if raw is None:
        return None
    val = raw.strip()
    me = view["me"]
    opp = view["opponent"]
    lower = val.lower()
    if lower in ("hero", "me", "my_hero"):
        return me["hero"]["id"]
    if lower in ("enemy_hero", "opp", "opp_hero", "face", "enemy"):
        return opp["hero"]["id"]
    if lower.startswith("m") and lower[1:].isdigit():
        idx = int(lower[1:])
        if 0 <= idx < len(me["board"]):
            return me["board"][idx]["uid"]
    if lower.startswith("e") and lower[1:].isdigit():
        idx = int(lower[1:])
        if 0 <= idx < len(opp["board"]):
            return opp["board"][idx]["uid"]
    return val


def alias_of(view: dict[str, Any], uid: str) -> str:
    """The reverse: how a character is called on the command line."""
    me = view["me"]
    opp = view["opponent"]
    if uid == me["hero"]["id"]:
        return "hero"
    if uid == opp["hero"]["id"]:
        return "enemy_hero"
    for i, m in enumerate(me["board"]):
        if m["uid"] == uid:
            return f"m{i}"
    for i, m in enumerate(opp["board"]):
        if m["uid"] == uid:
            return f"e{i}"
    return uid


def format_state_for_cli(view: dict[str, Any]) -> str:
    me = view["me"]
    opp = view["opponent"]
    my_h = me["hero"]
    opp_h = opp["hero"]

    lines: list[str] = []
    header = (
        f"=== GAME {view['game_id']} | Phase: {view['phase']} | Turn: {view['turn_number']} | "
        f"Active: {view['active_seat']} ({'YOUR TURN' if view['your_turn'] else 'OPPONENT TURN'}) ==="
    )
    lines.append(header)
    if view["phase"] == "GAME_OVER":
        lines.append(f"*** GAME OVER! Winner: {view['winner']} ***")

    # Opponent summary (fair play: only public stats!)
    opp_wep = (
        f" | Wep: {opp['weapon']['name']} {opp['weapon']['attack']}/{opp['weapon']['durability']}"
        if opp["weapon"]
        else ""
    )
    opp_sec = f" | Secrets: {len(opp['secrets'])} ({', '.join(s['card_class'] for s in opp['secrets'])})" if opp["secrets"] else ""
    opp_arm = f"+{opp_h['armor']}arm" if opp_h["armor"] else ""
    opp_flags = []
    if opp_h["frozen"]:
        opp_flags.append("FROZEN")
    if opp_h["immune"]:
        opp_flags.append("IMMUNE")
    opp_fstr = f" [{' '.join(opp_flags)}]" if opp_flags else ""

    lines.append(
        f"OPPONENT ({opp['name']} - {opp_h['name']} / {opp_h['card_class']}): "
        f"HP {opp_h['hp']}/{opp_h['max_hp']}{opp_arm}{opp_fstr} | "
        f"Mana {opp['mana']}/{opp['max_mana']} | Hand: {opp['hand_count']} | Deck: {opp['deck_count']}"
        f"{opp_wep}{opp_sec}  [target: enemy_hero]"
    )

    # Opponent board
    if opp["board"]:
        lines.append("  Enemy Board:")
        for idx, m in enumerate(opp["board"]):
            kw = ",".join(m["keywords"])
            flags = []
            if kw:
                flags.append(kw)
            if m["frozen"]:
                flags.append("FROZEN")
            if m["silenced"]:
                flags.append("SILENCED")
            if m["damaged"]:
                flags.append("DMG")
            if m["race"]:
                flags.append(m["race"])
            fstr = f" [{' | '.join(flags)}]" if flags else ""
            txt = f" — {m['text']}" if m["text"] else ""
            lines.append(f"    e{idx} ({m['uid']}): {m['name']} {m['attack']}/{m['health']}(max {m['max_health']}){fstr}{txt}")
    else:
        lines.append("  Enemy Board: (empty)")

    lines.append("-" * 76)

    # My board
    if me["board"]:
        lines.append("  Your Board:")
        for idx, m in enumerate(me["board"]):
            kw = ",".join(m["keywords"])
            flags = []
            if kw:
                flags.append(kw)
            if m["frozen"]:
                flags.append("FROZEN")
            if m["silenced"]:
                flags.append("SILENCED")
            if m["damaged"]:
                flags.append("DMG")
            if m["race"]:
                flags.append(m["race"])
            ready = "READY" if m["can_attack"] else "wait"
            fstr = f" [{' | '.join(flags)}]" if flags else ""
            txt = f" — {m['text']}" if m["text"] else ""
            lines.append(f"    m{idx} ({m['uid']}): {m['name']} {m['attack']}/{m['health']}(max {m['max_health']}) [{ready}]{fstr}{txt}")
    else:
        lines.append("  Your Board: (empty)")

    # My hero & status
    my_wep = (
        f" | Wep: {me['weapon']['name']} {me['weapon']['attack']}/{me['weapon']['durability']}"
        if me["weapon"]
        else ""
    )
    my_sec = f" | Secrets: [{', '.join(s['name'] for s in me['secrets'])}]" if me["secrets"] else ""
    my_arm = f"+{my_h['armor']}arm" if my_h["armor"] else ""
    ov_str = f" (Overload next: {me['pending_overload']})" if me["pending_overload"] else ""
    sd_str = f" | SpellDmg +{me['spell_damage']}" if me["spell_damage"] else ""
    hp_info = my_h["hero_power"]
    hp_state = "READY" if hp_info["can_use"] else ("USED" if hp_info["used"] else "locked")
    hero_atk = f" | HeroAtk {my_h['attack']} ({'READY' if my_h['can_attack'] else 'wait'})" if my_h["attack"] > 0 else ""

    lines.append(
        f"YOU ({me['name']} - {my_h['name']} / {my_h['card_class']}): "
        f"HP {my_h['hp']}/{my_h['max_hp']}{my_arm} | Mana {me['mana']}/{me['max_mana']}{ov_str} | "
        f"Deck: {me['deck_count']} | Combo: {'YES' if me['combo_active'] else 'no'}{sd_str}{hero_atk}{my_wep}{my_sec}  [target: hero]"
    )
    lines.append(f"  Hero Power (2m) [{hp_state}]: {hp_info['name']} — {hp_info['text']}")

    # Pending choice (Tracking)
    if view.get("pending_choice"):
        pc = view["pending_choice"]
        lines.append(f"*** PENDING CHOICE ({pc['choice_type']}): pick with `hs pick <0|1|2>` ***")
        for i, opt in enumerate(pc["options"]):
            lines.append(f"    [{i}] ({opt['cost']}m) {opt['name']} — {opt['text']}")

    # Hand
    lines.append(f"  Your Hand ({len(me['hand'])}/10):")
    for c in me["hand"]:
        play_tag = "PLAY" if c["can_play"] else "----"
        stats = ""
        if c["type"] == "MINION":
            stats = f" {c['attack']}/{c['health']}"
        elif c["type"] == "WEAPON":
            stats = f" {c['attack']}/{c['durability']} Wep"
        choose_info = ""
        if c["choose_options"]:
            opts = "; ".join(f"{o['index']}:{o['label']}" for o in c["choose_options"])
            choose_info = f" [Choose: {opts}]"
        tgt_info = f" (needs target: {c['target_rule']})" if c["target_required"] else ""
        lines.append(
            f"    [{c['index']}] [{play_tag}] ({c['cost']}m) {c['name']} [{c['type']}{stats}] — {c['text']}{choose_info}{tgt_info}"
        )

    # Recent log
    if view.get("log"):
        lines.append("  Recent Events:")
        for entry in view["log"][-8:]:
            lines.append(f"    - {entry['text']}")

    return "\n".join(lines)
