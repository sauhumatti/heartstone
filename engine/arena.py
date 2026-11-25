"""Arena draft & deck generator (shared rules for Python tests / bots / offline)."""

from __future__ import annotations

import random
from typing import Optional

from data.meta_decks import EXPANSIONS, card_in_era
from engine.catalog import COLLECTIBLE_CARDS, HEROES, CardDef, validate_deck

ARENA_DECK_SIZE = 30
ARENA_MAX_WINS = 12
ARENA_MAX_LOSSES = 3
GUARANTEED_RARE_PICKS = {1, 10, 20, 30}


def card_allowed_in_pool(card: CardDef, pool: str = "wild") -> bool:
    if not card.collectible:
        return False
    # Quests are excluded from Arena drafts (cannot reliably build around them in 30 random picks).
    if card.has_mechanic("QUEST") or card.has_mechanic("TRIAL"):
        return False
    if pool == "wild":
        return True
    if pool == "classic":
        return card.id.startswith("VAN_")
    if pool in EXPANSIONS:
        return card_in_era(card.id, pool)
    return True


def _rarity_bucket(card: CardDef) -> str:
    return "COMMON" if card.rarity == "FREE" else card.rarity


def roll_rarity(pick_number: int, rng: random.Random) -> str:
    r = rng.random()
    if pick_number in GUARANTEED_RARE_PICKS:
        if r < 0.70:
            return "RARE"
        if r < 0.90:
            return "EPIC"
        return "LEGENDARY"
    if r < 0.70:
        return "COMMON"
    if r < 0.91:
        return "RARE"
    if r < 0.98:
        return "EPIC"
    return "LEGENDARY"


def _card_weight(card: CardDef, hero_class: str) -> float:
    is_class = card.card_class == hero_class or hero_class in card.classes
    w = 2.0 if is_class else 1.0
    if card.type in ("SPELL", "WEAPON"):
        w *= 1.3
    return w


def offer_heroes(rng: Optional[random.Random] = None) -> list[str]:
    r = rng or random
    return r.sample(sorted(HEROES.keys()), 3)


def offer_pick(
    hero_class: str,
    pick_number: int,
    pool: str = "wild",
    rng: Optional[random.Random] = None,
) -> list[str]:
    r = rng or random
    eligible = [
        c for c in COLLECTIBLE_CARDS.values()
        if c.allowed_for_class(hero_class) and card_allowed_in_pool(c, pool)
    ]
    rarity = roll_rarity(pick_number, r)
    bucket = [c for c in eligible if _rarity_bucket(c) == rarity]
    if len(bucket) < 3:
        bucket = eligible
    chosen: list[str] = []
    remaining = list(bucket)
    for _ in range(min(3, len(remaining))):
        weights = [_card_weight(c, hero_class) for c in remaining]
        total = sum(weights)
        roll = r.random() * total
        acc = 0.0
        pick_idx = len(remaining) - 1
        for i, w in enumerate(weights):
            acc += w
            if roll <= acc:
                pick_idx = i
                break
        chosen.append(remaining.pop(pick_idx).id)
    return chosen


def _score_arena_card(card: CardDef, counts_by_cost: list[int], total_picked: int) -> float:
    # Target balanced Arena curve: peak at 2-4 mana, solid tempo minions + removal spells.
    target = (1, 4, 7, 6, 5, 3, 2, 2)
    bucket = min(7, max(0, card.cost))
    curve_need = target[bucket] - counts_by_cost[bucket]
    score = curve_need * 1.4
    if card.type == "MINION":
        stats = (card.attack or 0) + (card.health or 0)
        expected = card.cost * 2 + 1
        score += (stats - expected) * 0.9
        if card.has_mechanic("TAUNT") or card.has_mechanic("DIVINE_SHIELD") or card.has_mechanic("BATTLECRY"):
            score += 0.8
        if card.has_mechanic("CANT_ATTACK"):
            score -= 3.0
    elif card.type == "WEAPON":
        score += 2.2
    else:
        score += 0.9
    if card.card_class != "NEUTRAL":
        score += 0.5
    return score


def draft_bot_deck(
    hero_class: Optional[str] = None,
    pool: str = "wild",
    wins: int = 0,
    rng: Optional[random.Random] = None,
) -> tuple[str, list[str]]:
    """Draft a 30-card Arena deck for an opponent, scaling draft discipline with `wins`."""
    r = rng or random
    cls = hero_class if hero_class in HEROES else r.choice(sorted(HEROES.keys()))
    deck: list[str] = []
    counts_by_cost = [0] * 8
    noise = max(0.2, 2.8 - wins * 0.22)
    for pick in range(1, ARENA_DECK_SIZE + 1):
        opts = offer_pick(cls, pick, pool=pool, rng=r)
        best_cid = max(
            opts,
            key=lambda cid: _score_arena_card(COLLECTIBLE_CARDS[cid], counts_by_cost, pick - 1) + r.uniform(-noise, noise),
        )
        deck.append(best_cid)
        counts_by_cost[min(7, max(0, COLLECTIBLE_CARDS[best_cid].cost))] += 1
    ok, msg = validate_deck(cls, deck, allow_duplicates=True)
    assert ok, f"Invalid arena bot deck: {msg}"
    return cls, deck
