from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Optional

import requests

from engine.cli_format import resolve_target

DEFAULT_URL = "http://127.0.0.1:8000"


def _req(method: str, url: str, json_body: Optional[dict] = None, params: Optional[dict] = None, timeout: float = 15.0) -> dict[str, Any]:
    try:
        r = requests.request(method, url, json=json_body, params=params, timeout=timeout)
    except requests.RequestException as e:
        print(f"Connection error: {e}", file=sys.stderr)
        sys.exit(2)
    if not r.ok:
        detail = r.text
        try:
            detail = r.json().get("detail", detail)
        except Exception:
            pass
        print(f"API error ({r.status_code}): {detail}", file=sys.stderr)
        sys.exit(1)
    return r.json()


def _resolve_target(view: dict[str, Any], raw: Optional[str]) -> Optional[str]:
    return resolve_target(view, raw)


def _print_cli_state(base: str, gid: str, seat: str, as_json: bool = False) -> dict[str, Any]:
    data = _req("GET", f"{base}/api/games/{gid}/cli_text", params={"seat": seat})
    if as_json:
        print(json.dumps(data["state"], indent=2))
    else:
        print(data["text"])
    return data["state"]


def main() -> None:
    parser = argparse.ArgumentParser(prog="hs", description="Hearthstone Classic Agent CLI (Player 2 / API)")
    parser.add_argument("--url", default=DEFAULT_URL, help="Server base URL")
    parser.add_argument("--game", default="latest", help="Game ID (default: latest)")
    parser.add_argument("--seat", default="p2", choices=["p1", "p2"], help="Seat to act as (default: p2)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON state")

    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("games", help="List active games")
    sub.add_parser("status", help="Show current fair-play board state")

    p_wait = sub.add_parser("wait", help="Wait until it is your turn to act")
    p_wait.add_argument("--timeout", type=float, default=45.0, help="Seconds to wait")

    p_deck = sub.add_parser("deck", help="Choose P2 deck if game is waiting for deck")
    p_deck.add_argument("deck_or_class", help="Class name (MAGE, WARRIOR, ...) or deck ID")

    p_mul = sub.add_parser("mulligan", help="Submit mulligan replacements (indices or 'none')")
    p_mul.add_argument("indices", nargs="*", help="0-based hand indices to replace, or 'none'")

    p_play = sub.add_parser("play", help="Play a card from hand")
    p_play.add_argument("hand_index", type=int, help="Hand index [0..9]")
    p_play.add_argument("--pos", type=int, default=None, help="Board insertion slot (0..7)")
    p_play.add_argument("--target", default=None, help="Target alias (enemy_hero, hero, e0, m0, or uid)")
    p_play.add_argument("--choose", type=int, choices=[0, 1], default=None, help="Choose One option (0 or 1)")

    p_pick = sub.add_parser("pick", help="Pick an option for pending choice (e.g. Tracking)")
    p_pick.add_argument("option_index", type=int)

    p_atk = sub.add_parser("attack", help="Attack with minion or hero")
    p_atk.add_argument("attacker", help="Attacker alias (hero, m0..m6, or uid)")
    p_atk.add_argument("target", help="Target alias (enemy_hero, e0..e6, or uid)")

    p_pow = sub.add_parser("power", help="Use Hero Power")
    p_pow.add_argument("--target", default=None, help="Target alias if targeted Hero Power")

    sub.add_parser("end", help="End turn")
    sub.add_parser("concede", help="Concede the match")

    p_emote = sub.add_parser("emote", help="Send a chat/emote message to the opponent")
    p_emote.add_argument("message", nargs="+")

    args = parser.parse_args()
    base = args.url.rstrip("/")
    gid = args.game
    seat = args.seat

    if args.cmd == "games":
        data = _req("GET", f"{base}/api/games")
        if args.json:
            print(json.dumps(data, indent=2))
            return
        games = data.get("games", [])
        if not games:
            print("No games running.")
            return
        for g in games:
            tag = " [LATEST]" if g["is_latest"] else ""
            print(
                f"{g['game_id']}{tag} | {g['mode']} | {g['phase']} | Turn {g['turn_number']} (Active: {g['active_seat']}) | "
                f"P1 {g['p1']['hero_class']}({g['p1']['hp']}hp) vs P2 {g['p2']['hero_class']}({g['p2']['hp']}hp)"
            )
        return

    if args.cmd == "status":
        _print_cli_state(base, gid, seat, as_json=args.json)
        return

    if args.cmd == "wait":
        data = _req("GET", f"{base}/api/games/{gid}/wait", params={"seat": seat, "timeout": args.timeout}, timeout=args.timeout + 10)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(f"[ready={data['ready']}]")
            print(data["text"])
        return

    if args.cmd == "deck":
        val = args.deck_or_class.strip()
        body = {"hero_class": val.upper()} if val.upper() in ("MAGE","HUNTER","WARRIOR","PALADIN","PRIEST","ROGUE","SHAMAN","WARLOCK","DRUID") else {"deck_id": val}
        _req("POST", f"{base}/api/games/{gid}/p2_deck", json_body=body)
        _print_cli_state(base, gid, seat, as_json=args.json)
        return

    if args.cmd == "mulligan":
        idxs: list[int] = []
        for tok in args.indices:
            if tok.lower() in ("none", "keep", "-"):
                continue
            idxs.append(int(tok))
        _req("POST", f"{base}/api/games/{gid}/mulligan", json_body={"seat": seat, "replace_indices": idxs})
        _print_cli_state(base, gid, seat, as_json=args.json)
        return

    if args.cmd == "play":
        state = _req("GET", f"{base}/api/games/{gid}/state", params={"seat": seat})["state"]
        tgt = _resolve_target(state, args.target)
        _req(
            "POST",
            f"{base}/api/games/{gid}/play",
            json_body={
                "seat": seat,
                "hand_index": args.hand_index,
                "pos": args.pos,
                "target_id": tgt,
                "choose": args.choose,
            },
        )
        _print_cli_state(base, gid, seat, as_json=args.json)
        return

    if args.cmd == "pick":
        _req("POST", f"{base}/api/games/{gid}/choose", json_body={"seat": seat, "option_index": args.option_index})
        _print_cli_state(base, gid, seat, as_json=args.json)
        return

    if args.cmd == "attack":
        state = _req("GET", f"{base}/api/games/{gid}/state", params={"seat": seat})["state"]
        atk_id = _resolve_target(state, args.attacker)
        tgt_id = _resolve_target(state, args.target)
        _req(
            "POST",
            f"{base}/api/games/{gid}/attack",
            json_body={"seat": seat, "attacker_id": atk_id, "target_id": tgt_id},
        )
        _print_cli_state(base, gid, seat, as_json=args.json)
        return

    if args.cmd == "power":
        state = _req("GET", f"{base}/api/games/{gid}/state", params={"seat": seat})["state"]
        tgt = _resolve_target(state, args.target)
        _req("POST", f"{base}/api/games/{gid}/power", json_body={"seat": seat, "target_id": tgt})
        _print_cli_state(base, gid, seat, as_json=args.json)
        return

    if args.cmd == "end":
        _req("POST", f"{base}/api/games/{gid}/end_turn", json_body={"seat": seat})
        _print_cli_state(base, gid, seat, as_json=args.json)
        return

    if args.cmd == "concede":
        _req("POST", f"{base}/api/games/{gid}/concede", json_body={"seat": seat})
        _print_cli_state(base, gid, seat, as_json=args.json)
        return

    if args.cmd == "emote":
        msg = " ".join(args.message)
        _req("POST", f"{base}/api/games/{gid}/emote", json_body={"seat": seat, "message": msg})
        print(f"Sent emote: {msg}")
        return


if __name__ == "__main__":
    main()
