from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "cards.json"


@dataclass(frozen=True)
class HeroDef:
    card_class: str
    name: str
    hero_power_id: str
    title: str
    color: str


HEROES: dict[str, HeroDef] = {
    "WARRIOR": HeroDef("WARRIOR", "Garrosh Hellscream", "VAN_HERO_01bp", "Warchief", "#b83b2b"),
    "SHAMAN": HeroDef("SHAMAN", "Thrall", "VAN_HERO_02bp", "Farseer", "#2358b8"),
    "ROGUE": HeroDef("ROGUE", "Valeera Sanguinar", "VAN_HERO_03bp", "Shadowblade", "#3d424b"),
    "PALADIN": HeroDef("PALADIN", "Uther Lightbringer", "VAN_HERO_04bp", "Silver Hand", "#d49b27"),
    "HUNTER": HeroDef("HUNTER", "Rexxar", "VAN_HERO_05bp", "Beastmaster", "#2b7a3d"),
    "DRUID": HeroDef("DRUID", "Malfurion Stormrage", "VAN_HERO_06bp", "Archdruid", "#8b5224"),
    "WARLOCK": HeroDef("WARLOCK", "Gul'dan", "VAN_HERO_07bp", "Shadow Council", "#6b3896"),
    "MAGE": HeroDef("MAGE", "Jaina Proudmoore", "VAN_HERO_08bp", "Archmage", "#2b88c9"),
    "PRIEST": HeroDef("PRIEST", "Anduin Wrynn", "VAN_HERO_09bp", "High Priest", "#b8bdc7"),
}


@dataclass(frozen=True)
class CardDef:
    id: str
    name: str
    card_class: str
    type: str  # MINION, SPELL, WEAPON, HERO_POWER
    cost: int
    attack: Optional[int]
    health: Optional[int]
    durability: Optional[int]
    rarity: str
    race: Optional[str]
    collectible: bool
    text: str
    mechanics: tuple[str, ...] = field(default_factory=tuple)
    spell_damage: int = 0
    overload: int = 0
    classes: tuple[str, ...] = field(default_factory=tuple)

    def has_mechanic(self, mech: str) -> bool:
        return mech in self.mechanics

    def allowed_for_class(self, hero_class: str) -> bool:
        if self.classes:
            return hero_class in self.classes
        return self.card_class in (hero_class, "NEUTRAL")

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "card_class": self.card_class,
            "type": self.type,
            "cost": self.cost,
            "attack": self.attack,
            "health": self.health,
            "durability": self.durability,
            "rarity": self.rarity,
            "race": self.race,
            "collectible": self.collectible,
            "text": self.text,
            "mechanics": list(self.mechanics),
            "spell_damage": self.spell_damage,
            "overload": self.overload,
        }
        if self.classes:
            d["classes"] = list(self.classes)
        return d


_PLACEHOLDER = re.compile(r"\s*\{\d+\}")


def clean_text(text: str) -> str:
    """Card text without the source data's unfilled placeholders:
    "Summon a{1} {0} Jade Golem." reads "Summon a Jade Golem."."""
    if "{" not in text:
        return text
    return re.sub(r" {2,}", " ", _PLACEHOLDER.sub("", text)).strip()


def _load_cards() -> dict[str, CardDef]:
    raw = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    out: dict[str, CardDef] = {}
    for cid, d in raw.items():
        out[cid] = CardDef(
            id=d["id"],
            name=d["name"],
            card_class=d["card_class"],
            type=d["type"],
            cost=int(d.get("cost") or 0),
            attack=d.get("attack"),
            health=d.get("health"),
            durability=d.get("durability"),
            rarity=d.get("rarity", "FREE"),
            race=d.get("race"),
            collectible=bool(d.get("collectible")),
            text=clean_text(d.get("text") or ""),
            mechanics=tuple(d.get("mechanics") or ()),
            spell_damage=int(d.get("spell_damage") or 0),
            overload=int(d.get("overload") or 0),
            classes=tuple(d.get("classes") or ()),
        )
    return out


CARDS: dict[str, CardDef] = _load_cards()
COLLECTIBLE_CARDS: dict[str, CardDef] = {
    cid: c for cid, c in CARDS.items() if c.collectible
}
COLLECTIBLE_BY_NAME: dict[str, CardDef] = {
    c.name: c for c in COLLECTIBLE_CARDS.values()
}


def get_card(card_id: str) -> CardDef:
    return CARDS[card_id]


def validate_deck(hero_class: str, card_ids: list[str], allow_duplicates: bool = False) -> tuple[bool, str]:
    if hero_class not in HEROES:
        return False, f"Invalid hero class: {hero_class}"
    if len(card_ids) != 30:
        return False, f"Deck must contain exactly 30 cards (got {len(card_ids)})"
    counts: dict[str, int] = {}
    for cid in card_ids:
        card = COLLECTIBLE_CARDS.get(cid)
        if not card:
            return False, f"Unknown or non-collectible card ID: {cid}"
        if not card.allowed_for_class(hero_class):
            allowed = "/".join(card.classes) if card.classes else card.card_class
            return False, f"{card.name} belongs to {allowed}, not {hero_class}"
        if not allow_duplicates:
            counts[cid] = counts.get(cid, 0) + 1
            limit = 1 if card.rarity == "LEGENDARY" else 2
            if counts[cid] > limit:
                return False, f"Too many copies of {card.name} (max {limit})"
    return True, "ok"
