from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from data.starter_decks import STARTER_DECKS
from engine.catalog import validate_deck

VAR_DIR = Path(__file__).resolve().parent.parent / "var"
DECKS_FILE = VAR_DIR / "decks.json"


def _ensure_var() -> None:
    VAR_DIR.mkdir(parents=True, exist_ok=True)


def list_custom_decks() -> list[dict[str, Any]]:
    _ensure_var()
    if not DECKS_FILE.exists():
        return []
    try:
        return json.loads(DECKS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def list_all_decks() -> list[dict[str, Any]]:
    starters = [
        d | {"builtin": True}
        for d in STARTER_DECKS.values()
    ]
    custom = [d | {"builtin": False} for d in list_custom_decks()]
    return starters + custom


def get_deck_by_id(deck_id: str) -> dict[str, Any] | None:
    for d in list_all_decks():
        if d["id"] == deck_id:
            return d
    return None


def save_custom_deck(name: str, hero_class: str, cards: list[str], deck_id: str | None = None) -> dict[str, Any]:
    ok, msg = validate_deck(hero_class, cards)
    if not ok:
        raise ValueError(msg)
    clean_name = (name or "").strip()[:48] or f"Custom {hero_class.title()}"
    decks = list_custom_decks()
    if deck_id:
        for d in decks:
            if d["id"] == deck_id:
                d["name"] = clean_name
                d["hero_class"] = hero_class
                d["cards"] = list(cards)
                _write_decks(decks)
                return d | {"builtin": False}
    new_deck = {
        "id": f"custom_{uuid.uuid4().hex[:8]}",
        "name": clean_name,
        "hero_class": hero_class,
        "description": "Custom 30-card Classic deck.",
        "cards": list(cards),
    }
    decks.append(new_deck)
    _write_decks(decks)
    return new_deck | {"builtin": False}


def delete_custom_deck(deck_id: str) -> bool:
    decks = list_custom_decks()
    new_decks = [d for d in decks if d["id"] != deck_id]
    if len(new_decks) == len(decks):
        return False
    _write_decks(new_decks)
    return True


def _write_decks(decks: list[dict[str, Any]]) -> None:
    _ensure_var()
    DECKS_FILE.write_text(json.dumps(decks, indent=2), encoding="utf-8")
