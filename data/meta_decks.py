"""Lanternfall expansion pools and their curated deck recipes."""

from __future__ import annotations

from collections import Counter

from data.meta_recipes import RECIPES
from engine.catalog import COLLECTIBLE_BY_NAME, COLLECTIBLE_CARDS, CardDef, validate_deck

EXPANSIONS = {
    "gvg": "Goblins vs Gnomes",
    "tgt": "The Grand Tournament",
    "old_gods": "Whispers of the Old Gods",
    "gadgetzan": "Mean Streets of Gadgetzan",
    "ungoro": "Journey to Un'Goro",
}

SETS = {
    "gvg": {"VAN", "FP1", "GVG"},
    "tgt": {"VAN", "FP1", "GVG", "BRM", "AT"},
    "old_gods": {"VAN", "BRM", "AT", "LOE", "OG"},
    "gadgetzan": {"VAN", "BRM", "AT", "LOE", "OG", "KAR", "CFM"},
    "ungoro": {"VAN", "OG", "KAR", "CFM"},
}

# Original cards enter when their deck roles first appear. The Recruit payoff
# follows the early pool; the other original support stays available afterward.
ORIGINAL_FIRST = {
    "LF_001": "gadgetzan", "LF_002": "gadgetzan", "LF_003": "gvg",
    "LF_004": "old_gods", "LF_005": "gvg", "LF_006": "gvg", "LF_007": "gvg",
    **{f"LF_M{i:02d}": "gvg" for i in (1, 37)},
    **{f"LF_M{i:02d}": "tgt" for i in (2, 3, 4, 5, 41)},
    **{f"LF_M{i:02d}": "old_gods" for i in (6, 7, 8, 9, 10, 11, 33, 34, 36, 40)},
    **{f"LF_M{i:02d}": "gadgetzan" for i in (12, 13, 14, 15, 16, 17, 18, 19, 20, 35)},
    **{f"LF_M{i:02d}": "ungoro" for i in (*range(21, 33), 38, 39)},
}
ORIGINAL_LAST = {"LF_007": "tgt", "LF_M02": "tgt", "LF_M04": "gadgetzan", "LF_M37": "tgt", "LF_M41": "gadgetzan"}
HALL_OF_FAME = {
    COLLECTIBLE_BY_NAME[name].id for name in (
        "Azure Drake", "Conceal", "Ice Lance", "Power Overwhelming",
        "Ragnaros the Firelord", "Sylvanas Windrunner",
    )
}


def card_in_era(card_id: str, era: str) -> bool:
    if era not in EXPANSIONS:
        return False
    if card_id in ORIGINAL_FIRST:
        eras = list(EXPANSIONS)
        return eras.index(ORIGINAL_FIRST[card_id]) <= eras.index(era) <= eras.index(ORIGINAL_LAST.get(card_id, "ungoro"))
    if era in ("old_gods", "gadgetzan", "ungoro") and card_id == COLLECTIBLE_BY_NAME["Old Murk-Eye"].id:
        return False
    if era == "ungoro" and card_id in HALL_OF_FAME:
        return False
    return card_id.split("_", 1)[0] in SETS[era]


def _card_names(names: str) -> list[str]:
    return names.split(";") if names else []


# These support lists are ordered by tactical role, not aggregate card strength.
# The named core in each recipe is always included before using these lists.
ROLE_SUPPORT = {
    "rush": "Leper Gnome;Abusive Sergeant;Worgen Infiltrator;Argent Squire;Knife Juggler;Dire Wolf Alpha;Wolfrider;Argent Commander",
    "board": "Haunted Creeper;Piloted Shredder;Harvest Golem;Knife Juggler;Chillwind Yeti;Defender of Argus;Loatheb;Azure Drake",
    "combo": "Bloodmage Thalnos;Loot Hoarder;Novice Engineer;Acolyte of Pain;Azure Drake;Gnomish Inventor",
    "control": "Acidic Swamp Ooze;Doomsayer;Acolyte of Pain;Sludge Belcher;Antique Healbot;Stampeding Kodo;Cairne Bloodhoof;Ysera",
    "ramp": "Doomsayer;Earthen Ring Farseer;Chillwind Yeti;Sludge Belcher;Skyfire Drake;Sunwalker;Ysera;Farwood Titan",
    "mech": "Clockwork Gnome;Cogmaster;Mechwarper;Annoy-o-Tron;Harvest Golem;Spider Tank;Piloted Shredder;Fel Reaver",
    "freeze": "Loot Hoarder;Doomsayer;Acolyte of Pain;Bloodmage Thalnos;Mad Scientist;Antique Healbot;Alexstrasza",
    "death": "Emberglass Cocoon;Haunted Creeper;Loot Hoarder;Harvest Golem;Piloted Shredder;Cairne Bloodhoof;Sylvanas Windrunner",
    "murloc": "Murloc Tidecaller;Murloc Tidehunter;Murloc Warleader;Grimscale Oracle;Bluegill Warrior;Coldlight Seer;Knife Juggler;Marshfen Prowler",
    "pirate": "Southsea Deckhand;Breakwater Runaway;Bloodsail Raider;Dread Corsair;Southsea Captain;Bloodsail Corsair;Captain Greenskin",
    "totem": "Haunted Creeper;Knife Juggler;Defender of Argus;Harvest Golem;Azure Drake;Piloted Shredder",
    "jade": "Jade Spirit;Aya Blackpaw;Bloodmage Thalnos;Defender of Argus;Loot Hoarder;Chillwind Yeti",
    "elemental": "Spark Courier;Kiln Guard;Frost Elemental;Earthen Ring Farseer;Loot Hoarder;Defender of Argus;Chillwind Yeti",
    "secrets": "Secretkeeper;Mad Scientist;Loot Hoarder;Knife Juggler;Haunted Creeper;Azure Drake;Piloted Shredder",
    "dragon": "Faerie Dragon;Blackwing Technician;Twilight Guardian;Blackwing Corruptor;Azure Drake;Twilight Drake;Skyfire Drake",
    "beast": "River Crocolisk;Haunted Creeper;Bloodfen Raptor;Jungle Panther;Stranglethorn Tiger;Oasis Snapjaw",
    "weapon": "Southsea Deckhand;Bloodsail Raider;Dread Corsair;Loot Hoarder;Acolyte of Pain;Harrison Jones",
    "token": "Argent Squire;Haunted Creeper;Emberglass Cocoon;Knife Juggler;Dire Wolf Alpha;Silver Hand Knight;Defender of Argus",
    "singleton": "Acidic Swamp Ooze;Bloodmage Thalnos;Doomsayer;Acolyte of Pain;Earthen Ring Farseer;Refreshment Vendor;Twilight Drake;Cairne Bloodhoof;Ysera",
    "mill": "Youthful Brewmaster;Ancient Brewmaster;Doomsayer;Coldlight Oracle;Deathlord;Sludge Belcher;Antique Healbot;Earthen Ring Farseer",
    "trial": "Youthful Brewmaster;Novice Engineer;Gnomish Inventor;Shieldbearer;Sen'jin Shieldmasta;Frostwolf Grunt;Sunwalker",
}
STAPLES = {
    "DRUID": "Innervate;Wild Growth;Wrath;Swipe;Power of the Wild;Savage Roar;Keeper of the Grove;Druid of the Claw;Living Roots;Feral Rage;Nourish;Ancient of Lore;Cenarius",
    "HUNTER": "Tracking;Arcane Shot;Animal Companion;Kill Command;Quick Shot;Unleash the Hounds;Eaglehorn Bow;Webspinner;Kindly Grandmother;Houndmaster;Savannah Highmane;Emberfield Stalker;Hunter's Mark",
    "MAGE": "Frostbolt;Fireball;Arcane Intellect;Mana Wyrm;Arcane Missiles;Sorcerer's Apprentice;Firelands Portal;Polymorph;Flamestrike;Blizzard;Water Elemental",
    "PALADIN": "Truesilver Champion;Consecration;Equality;Aldor Peacekeeper;Shielded Minibot;Muster for Battle;Argent Protector;Tirion Fordring;Keeper of Uldaman;Solemn Vigil;Guardian of Kings",
    "PRIEST": "Northshire Cleric;Power Word: Shield;Shadow Word: Pain;Shadow Word: Death;Circle of Healing;Auchenai Soulpriest;Holy Nova;Entomb;Lightbomb;Cabal Shadow Priest;Velen's Chosen",
    "ROGUE": "Backstab;Eviscerate;Sap;SI:7 Agent;Fan of Knives;Deadly Poison;Preparation;Shiv;Tomb Pillager;Edwin VanCleef;Assassinate;Sprint",
    "SHAMAN": "Lightning Bolt;Flametongue Totem;Feral Spirit;Hex;Lightning Storm;Earth Shock;Fire Elemental;Mana Tide Totem;Totem Golem;Thing from Below;Maelstrom Portal",
    "WARLOCK": "Mortal Coil;Dark Peddler;Imp Gang Boss;Darkbomb;Flame Imp;Voidwalker;Soulfire;Doomguard;Siphon Soul;Hellfire;Shadowflame;Power Overwhelming",
    "WARRIOR": "Fiery War Axe;Execute;Slam;Armorsmith;Whirlwind;Cruel Taskmaster;Shield Block;Death's Bite;Ravaging Ghoul;Grommash Hellscream;Bash;Shield Slam;Brawl",
}
NEUTRAL_SUPPORT = "Loot Hoarder;Acidic Swamp Ooze;Faerie Dragon;Acolyte of Pain;Earthen Ring Farseer;Chillwind Yeti;Sen'jin Shieldmasta;Defender of Argus;Azure Drake;Cairne Bloodhoof;Gnomish Inventor;Stampeding Kodo;Sunwalker;Spellbreaker"

CURVES = {
    "rush": (7, 8, 7, 5, 3),
    "pirate": (7, 8, 7, 5, 3),
    "murloc": (7, 8, 7, 5, 3),
    "mech": (5, 8, 7, 6, 4),
    "token": (6, 8, 7, 5, 4),
    "beast": (5, 7, 7, 5, 6),
    "secrets": (4, 8, 8, 5, 5),
    "board": (5, 8, 6, 6, 5),
    "death": (4, 7, 6, 6, 7),
    "jade": (4, 6, 7, 6, 7),
    "dragon": (4, 6, 6, 6, 8),
    "totem": (5, 7, 7, 6, 5),
    "elemental": (5, 6, 6, 6, 7),
    "weapon": (5, 8, 7, 6, 4),
    "combo": (5, 8, 7, 5, 5),
    "freeze": (4, 8, 7, 4, 7),
    "mill": (4, 8, 7, 5, 6),
    "control": (4, 7, 6, 5, 8),
    "ramp": (4, 7, 5, 5, 9),
    "singleton": (4, 7, 6, 5, 8),
    "trial": (5, 8, 6, 5, 6),
}


def _build(era: str, hero_class: str, role: str, core: str) -> list[str]:
    singleton = role == "singleton"
    cards: list[CardDef] = []
    for choice in _card_names(core):
        single_copy = choice not in COLLECTIBLE_BY_NAME and choice.endswith("!")
        card = COLLECTIBLE_BY_NAME[choice.removesuffix("!") if single_copy else choice]
        if not card_in_era(card.id, era):
            raise ValueError(f"{card.name} is outside the {era} pool")
        copies = 1 if singleton or single_copy or card.rarity == "LEGENDARY" else 2
        cards.extend([card] * copies)

    # Keep reserve choices deterministic so deck lists are identical online and
    # in the packaged engine. Favor the archetype's support and fill its curve.
    names = dict.fromkeys(
        _card_names(ROLE_SUPPORT[role])[:5] + _card_names(STAPLES[hero_class])[:6]
        + _card_names(ROLE_SUPPORT[role])[5:] + _card_names(STAPLES[hero_class])[6:]
        + _card_names(NEUTRAL_SUPPORT)
    )
    candidates = [
        COLLECTIBLE_BY_NAME[name] for name in names
        if COLLECTIBLE_BY_NAME[name].card_class in (hero_class, "NEUTRAL")
        and card_in_era(COLLECTIBLE_BY_NAME[name].id, era)
    ]
    copies = Counter(c.id for c in cards)
    buckets = Counter(min(5, max(1, c.cost)) - 1 for c in cards)
    for i in range(len(cards), 30):
        best = None
        best_score = float("-inf")
        for priority, candidate in enumerate(candidates):
            limit = 1 if singleton or candidate.rarity == "LEGENDARY" else 2
            if copies[candidate.id] >= limit:
                continue
            bucket = min(5, max(1, candidate.cost)) - 1
            need = CURVES[role][bucket] - buckets[bucket]
            score = 2.5 * max(-3, need) - priority * 0.6
            if copies[candidate.id]:
                score -= 1.0
            if score > best_score:
                best, best_score = candidate, score
        if best is None:
            raise ValueError(f"Not enough support cards for {era} {hero_class} {role} at slot {i + 1}")
        cards.append(best)
        copies[best.id] += 1
        buckets[min(5, max(1, best.cost)) - 1] += 1

    result = [c.id for c in sorted(cards, key=lambda c: (c.cost, c.name))]
    valid, reason = validate_deck(hero_class, result)
    if not valid:
        raise ValueError(f"{era} {hero_class} {role}: {reason}")
    return result


def _expansion_decks() -> list[dict]:
    decks = []
    for era, label in EXPANSIONS.items():
        slots: Counter[str] = Counter()
        for row in RECIPES[era].strip().splitlines():
            hero_class, name, role, description, core = row.split("|")
            slots[hero_class] += 1
            decks.append({
                "id": f"meta_{era}_{hero_class.lower()}_{slots[hero_class]}",
                "name": name,
                "hero_class": hero_class,
                "era": era,
                "era_name": label,
                "description": description,
                "cards": _build(era, hero_class, role, core),
            })
    return decks


META_DECKS = _expansion_decks()
META_POOLS = {era: tuple(d for d in META_DECKS if d["era"] == era) for era in EXPANSIONS}
