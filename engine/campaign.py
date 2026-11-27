"""Campaign Mode rival banter hooks.

Campaign matches are standard, balanced 30 HP vs 30 HP duels. This module only handles
optional flavor dialogue (opening line & mid-match emote) stored in `extra_flags`.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.game import GameEngine


def _rival_say(engine: "GameEngine", text: str) -> None:
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
    p2_intro_quote: str = "",
    p2_mid_quote: str = "",
) -> None:
    p2 = engine.state.players["p2"]
    if p2_intro_quote:
        p2.extra_flags["rival_intro"] = p2_intro_quote
        p2.extra_flags["rival_intro_said"] = False
    if p2_mid_quote:
        p2.extra_flags["rival_mid_quote"] = p2_mid_quote
        p2.extra_flags["rival_mid_said"] = False


def on_turn_start(engine: "GameEngine", _seat: str) -> None:
    if engine.state.phase != "PLAY" or engine.state.deck_era != "campaign":
        return
    p2 = engine.state.players["p2"]
    if not p2.extra_flags.get("rival_intro_said") and p2.extra_flags.get("rival_intro"):
        p2.extra_flags["rival_intro_said"] = True
        _rival_say(engine, str(p2.extra_flags["rival_intro"]))


def on_rival_damaged(engine: "GameEngine") -> None:
    if engine.state.phase != "PLAY" or engine.state.deck_era != "campaign":
        return
    p2 = engine.state.players["p2"]
    if p2.extra_flags.get("rival_mid_said"):
        return
    quote = p2.extra_flags.get("rival_mid_quote")
    if quote and 0 < p2.hero.hp <= (p2.hero.max_hp // 2):
        p2.extra_flags["rival_mid_said"] = True
        _rival_say(engine, str(quote))
