from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from engine.game import GameEngine
    from engine.models import Minion


@dataclass(frozen=True)
class ChooseOption:
    label: str
    description: str
    target_rule: str = "NONE"


@dataclass(frozen=True)
class CardScript:
    target_rule: str = "NONE"
    choose_options: tuple[ChooseOption, ...] = ()
    is_pure_keyword: bool = False


# Target rules:
# NONE, ANY, MINION, FRIENDLY_MINION, ENEMY_MINION, FRIENDLY_CHARACTER, ENEMY_CHARACTER,
# HERO, ENEMY_HERO, FRIENDLY_BEAST, UNDAMAGED_MINION, DAMAGED_MINION, DAMAGED_ENEMY_MINION,
# MINION_ATK_LE_3, MINION_ATK_GE_5, MINION_ATK_GE_7, ENEMY_MINION_ATK_LE_2,
# ENEMY_MINION_ATK_LE_3, ENEMY_TAUNT, MURLOC, DEMON


CHOOSE_ONE_OPTIONS: dict[str, tuple[ChooseOption, ...]] = {
    "VAN_EX1_160": (  # Power of the Wild
        ChooseOption("Leader of the Pack", "Give your minions +1/+1.", "NONE"),
        ChooseOption("Summon a Panther", "Summon a 3/2 Panther.", "NONE"),
    ),
    "VAN_EX1_154": (  # Wrath
        ChooseOption("Solar Wrath", "Deal 3 damage to a minion.", "MINION"),
        ChooseOption("Nature's Wrath", "Deal 1 damage to a minion. Draw a card.", "MINION"),
    ),
    "VAN_EX1_155": (  # Mark of Nature
        ChooseOption("Tiger's Fury", "Give a minion +4 Attack.", "MINION"),
        ChooseOption("Thick Hide", "Give a minion +4 Health and Taunt.", "MINION"),
    ),
    "VAN_EX1_166": (  # Keeper of the Grove
        ChooseOption("Moonfire", "Deal 2 damage.", "ANY"),
        ChooseOption("Dispel", "Silence a minion.", "MINION"),
    ),
    "VAN_EX1_165": (  # Druid of the Claw
        ChooseOption("Cat Form", "Charge (4/4).", "NONE"),
        ChooseOption("Bear Form", "+2 Health and Taunt (4/6).", "NONE"),
    ),
    "VAN_EX1_164": (  # Nourish
        ChooseOption("Rampant Growth", "Gain 2 Mana Crystals.", "NONE"),
        ChooseOption("Enrich", "Draw 3 cards.", "NONE"),
    ),
    "VAN_NEW1_007": (  # Starfall
        ChooseOption("Starlord", "Deal 5 damage to a minion.", "MINION"),
        ChooseOption("Stellar Drift", "Deal 2 damage to all enemy minions.", "NONE"),
    ),
    "VAN_NEW1_008": (  # Ancient of Lore
        ChooseOption("Ancient Teachings", "Draw 2 cards.", "NONE"),
        ChooseOption("Ancient Secrets", "Restore 5 Health.", "ANY"),
    ),
    "VAN_EX1_178": (  # Ancient of War
        ChooseOption("Uproot", "+5 Attack (10/5).", "NONE"),
        ChooseOption("Rooted", "+5 Health and Taunt (5/10 Taunt).", "NONE"),
    ),
    "VAN_EX1_573": (  # Cenarius
        ChooseOption("Demigod's Favor", "Give your other minions +2/+2.", "NONE"),
        ChooseOption("Shan'do's Lesson", "Summon two 2/2 Treants with Taunt.", "NONE"),
    ),
    "AT_037": (  # Living Roots
        ChooseOption("Grasping Roots", "Deal 2 damage.", "ANY"),
        ChooseOption("One with the Trees", "Summon two 1/1 Saplings.", "NONE"),
    ),
    "OG_047": (  # Feral Rage
        ChooseOption("Evolve Spines", "Give your hero +4 Attack this turn.", "NONE"),
        ChooseOption("Evolve Scales", "Gain 8 Armor.", "NONE"),
    ),
    "CFM_602": (  # Jade Idol
        ChooseOption("Summon a Jade Golem", "Summon a Jade Golem.", "NONE"),
        ChooseOption("Shuffle 3 copies", "Shuffle 3 copies of Jade Idol into your deck.", "NONE"),
    ),
}


TARGET_RULES: dict[str, str] = {
    "LF_004": "FRIENDLY_PRINTED_DEATHRATTLE",
    # Spells
    "VAN_CS2_008": "ANY",  # Moonfire
    "VAN_EX1_161": "MINION",  # Naturalize
    "VAN_EX1_578": "MINION",  # Savagery
    "VAN_CS2_009": "MINION",  # Mark of the Wild
    "VAN_CS2_007": "ANY",  # Healing Touch
    "VAN_CS2_012": "ENEMY_CHARACTER",  # Swipe
    "VAN_EX1_173": "ANY",  # Starfire
    "VAN_CS2_084": "MINION",  # Hunter's Mark
    "VAN_DS1_185": "ANY",  # Arcane Shot
    "VAN_EX1_549": "FRIENDLY_BEAST",  # Bestial Wrath
    "VAN_EX1_539": "ANY",  # Kill Command
    "VAN_EX1_537": "MINION",  # Explosive Shot
    "VAN_CS2_031": "ANY",  # Ice Lance
    "VAN_CS2_024": "ANY",  # Frostbolt
    "VAN_EX1_275": "MINION",  # Cone of Cold
    "VAN_CS2_029": "ANY",  # Fireball
    "VAN_CS2_022": "MINION",  # Polymorph
    "VAN_EX1_279": "ANY",  # Pyroblast
    "VAN_CS2_087": "MINION",  # Blessing of Might
    "VAN_EX1_363": "MINION",  # Blessing of Wisdom
    "VAN_EX1_371": "MINION",  # Hand of Protection
    "VAN_EX1_360": "MINION",  # Humility
    "VAN_CS2_089": "ANY",  # Holy Light
    "VAN_CS2_092": "MINION",  # Blessing of Kings
    "VAN_CS2_094": "ANY",  # Hammer of Wrath
    "VAN_EX1_355": "MINION",  # Blessed Champion
    "VAN_EX1_365": "ANY",  # Holy Wrath
    "VAN_EX1_354": "ANY",  # Lay on Hands
    "VAN_EX1_332": "MINION",  # Silence
    "VAN_CS1_130": "ANY",  # Holy Smite
    "VAN_CS1_129": "MINION",  # Inner Fire
    "VAN_CS2_004": "MINION",  # Power Word: Shield
    "VAN_CS2_236": "MINION",  # Divine Spirit
    "VAN_CS2_234": "MINION_ATK_LE_3",  # Shadow Word: Pain
    "VAN_EX1_622": "MINION_ATK_GE_5",  # Shadow Word: Death
    "VAN_EX1_334": "ENEMY_MINION_ATK_LE_3",  # Shadow Madness
    "VAN_EX1_624": "ANY",  # Holy Fire
    "VAN_CS1_113": "ENEMY_MINION",  # Mind Control
    "VAN_CS2_072": "UNDAMAGED_MINION",  # Backstab
    "VAN_EX1_144": "FRIENDLY_MINION",  # Shadowstep
    "VAN_CS2_073": "MINION",  # Cold Blood
    "VAN_EX1_126": "ENEMY_MINION",  # Betrayal
    "VAN_EX1_124": "ANY",  # Eviscerate
    "VAN_EX1_581": "ENEMY_MINION",  # Sap
    "VAN_EX1_278": "ANY",  # Shiv
    "VAN_CS2_076": "ENEMY_MINION",  # Assassinate
    "VAN_CS2_041": "MINION",  # Ancestral Healing
    "VAN_EX1_245": "MINION",  # Earth Shock
    "VAN_CS2_037": "ENEMY_CHARACTER",  # Frost Shock
    "VAN_EX1_238": "ANY",  # Lightning Bolt
    "VAN_CS2_045": "FRIENDLY_CHARACTER",  # Rockbiter Weapon
    "VAN_CS2_038": "MINION",  # Ancestral Spirit
    "VAN_CS2_039": "MINION",  # Windfury
    "VAN_EX1_241": "ANY",  # Lava Burst
    "VAN_NEW1_003": "DEMON",  # Sacrificial Pact
    "VAN_EX1_308": "ANY",  # Soulfire
    "VAN_CS2_063": "ENEMY_MINION",  # Corruption
    "VAN_EX1_302": "MINION",  # Mortal Coil
    "VAN_EX1_316": "FRIENDLY_MINION",  # Power Overwhelming
    "VAN_EX1_596": "MINION",  # Demonfire
    "VAN_CS2_061": "ANY",  # Drain Life
    "VAN_CS2_057": "MINION",  # Shadow Bolt
    "VAN_EX1_303": "FRIENDLY_MINION",  # Shadowflame
    "VAN_EX1_320": "ANY",  # Bane of Doom
    "VAN_EX1_309": "MINION",  # Siphon Soul
    "VAN_EX1_607": "MINION",  # Inner Rage
    "VAN_CS2_108": "DAMAGED_ENEMY_MINION",  # Execute
    "VAN_EX1_410": "MINION",  # Shield Slam
    "VAN_CS2_104": "DAMAGED_MINION",  # Rampage
    "VAN_EX1_391": "MINION",  # Slam
    "VAN_CS2_103": "FRIENDLY_MINION",  # Charge
    "VAN_EX1_408": "ANY",  # Mortal Strike
    # Token Spells
    "EX1_014t": "MINION",  # Bananas
    "VAN_DREAM_04": "MINION",  # Dream
    "VAN_DREAM_05": "MINION",  # Nightmare
    "PRO_001b": "ANY",  # Rogues Do It...
    # Hero Powers
    "VAN_HERO_08bp": "ANY",  # Fireblast
    "VAN_HERO_09bp": "ANY",  # Lesser Heal
    "EX1_625t": "ANY",  # Mind Spike
    "EX1_625t2": "ANY",  # Mind Shatter
    # Minions / Weapons with Targeted Battlecries / Combos
    "VAN_DS1_070": "FRIENDLY_BEAST",  # Houndmaster
    "VAN_EX1_362": "FRIENDLY_MINION",  # Argent Protector
    "VAN_EX1_382": "ENEMY_MINION",  # Aldor Peacekeeper
    "VAN_EX1_091": "ENEMY_MINION_ATK_LE_2",  # Cabal Shadow Priest
    "VAN_EX1_623": "FRIENDLY_MINION",  # Temple Enforcer
    "VAN_EX1_133": "ANY",  # Perdition's Blade
    "VAN_EX1_134": "ANY",  # SI:7 Agent (only when combo!)
    "VAN_NEW1_014": "FRIENDLY_MINION",  # Master of Disguise
    "VAN_NEW1_005": "MINION",  # Kidnapper (only when combo!)
    "VAN_EX1_587": "FRIENDLY_MINION",  # Windspeaker
    "VAN_CS2_042": "ANY",  # Fire Elemental
    "VAN_EX1_603": "MINION",  # Cruel Taskmaster
    "VAN_CS2_188": "MINION",  # Abusive Sergeant
    "VAN_CS2_189": "ANY",  # Elven Archer
    "VAN_NEW1_017": "MURLOC",  # Hungry Crab
    "VAN_EX1_011": "ANY",  # Voodoo Doctor
    "VAN_EX1_059": "MINION",  # Crazed Alchemist
    "VAN_CS2_203": "MINION",  # Ironbeak Owl
    "VAN_EX1_049": "FRIENDLY_MINION",  # Youthful Brewmaster
    "VAN_EX1_005": "MINION_ATK_GE_7",  # Big Game Hunter
    "VAN_CS2_117": "ANY",  # Earthen Ring Farseer
    "VAN_CS2_141": "ANY",  # Ironforge Rifleman
    "VAN_EX1_019": "FRIENDLY_MINION",  # Shattered Sun Cleric
    "VAN_EX1_057": "FRIENDLY_MINION",  # Ancient Brewmaster
    "VAN_EX1_046": "MINION",  # Dark Iron Dwarf
    "VAN_EX1_048": "MINION",  # Spellbreaker
    "VAN_EX1_564": "MINION",  # Faceless Manipulator
    "VAN_CS2_150": "ANY",  # Stormpike Commando
    "VAN_EX1_283": "ANY",  # Frost Elemental
    "VAN_EX1_002": "ENEMY_TAUNT",  # The Black Knight
    "VAN_EX1_561": "HERO",  # Alexstrasza
    # Golden Era Spells & Spare Parts
    "GVG_015": "ANY",  # Darkbomb
    "GVG_045": "MINION",  # Imp-losion
    "BRM_013": "ANY",  # Quick Shot
    "AT_004": "MINION",  # Arcane Blast
    "KAR_076": "ANY",  # Firelands Portal
    "AT_064": "ANY",  # Bash
    "BRM_007": "MINION",  # Gang Up
    "GVG_010": "MINION",  # Velen's Chosen
    "LOE_104": "ENEMY_MINION",  # Entomb
    "GVG_038": "ANY",  # Crackle
    "BRM_011": "ANY",  # Lava Shock
    "PART_001": "MINION",  # Armor Plating
    "PART_002": "FRIENDLY_MINION",  # Time Rewinder
    "PART_003": "MINION",  # Rusty Horn
    "PART_004": "FRIENDLY_MINION",  # Finicky Cloakfield
    "PART_005": "MINION",  # Emergency Coolant
    "PART_006": "MINION",  # Reversing Switch
    "PART_007": "MINION",  # Whirling Blades
    # Golden Era Minions
    "LOE_017": "MINION",  # Keeper of Uldaman
    "BRM_034": "ANY",  # Blackwing Corruptor (only when holding a Dragon!)
    # Upgraded Hero Powers
    "AT_132_MAGE": "ANY",  # Fireblast Rank 2
    "AT_132_PRIEST": "ANY",  # Heal
}

# Combo minions that ONLY need a target if Combo is already active when played
COMBO_ONLY_TARGET_CARDS = {"VAN_EX1_134", "VAN_NEW1_005"}
# Dragon-holding minions that ONLY need a target if holding a Dragon
DRAGON_ONLY_TARGET_CARDS = {"BRM_034"}

PURE_KEYWORD_CARDS = {
    "VAN_CS2_232",  # Ironbark Protector
    "VAN_EX1_543",  # King Krush
    "VAN_CS2_091",  # Light's Justice
    "VAN_CS2_080",  # Assassin's Blade
    "VAN_EX1_250",  # Earth Elemental
    "VAN_NEW1_010",  # Al'Akir the Windlord
    "VAN_CS2_065",  # Voidwalker
    "VAN_CS2_106",  # Fiery War Axe
    "VAN_NEW1_011",  # Kor'kron Elite
    "VAN_CS2_112",  # Arcanite Reaper
    "VAN_CS2_231",  # Wisp
    "VAN_EX1_008",  # Argent Squire
    "VAN_CS1_042",  # Goldshire Footman
    "VAN_CS2_168",  # Murloc Raider
    "VAN_EX1_405",  # Shieldbearer
    "VAN_CS2_171",  # Stonetusk Boar
    "VAN_EX1_010",  # Worgen Infiltrator
    "VAN_CS2_169",  # Young Dragonhawk
    "VAN_EX1_045",  # Ancient Watcher
    "VAN_CS2_172",  # Bloodfen Raptor
    "VAN_CS2_173",  # Bluegill Warrior
    "VAN_NEW1_023",  # Faerie Dragon
    "VAN_CS2_121",  # Frostwolf Grunt
    "VAN_CS2_142",  # Kobold Geomancer
    "VAN_CS2_120",  # River Crocolisk
    "VAN_EX1_582",  # Dalaran Mage
    "VAN_CS2_125",  # Ironfur Grizzly
    "VAN_EX1_017",  # Jungle Panther
    "VAN_CS2_118",  # Magma Rager
    "VAN_EX1_020",  # Scarlet Crusader
    "VAN_CS2_127",  # Silverback Patriarch
    "VAN_EX1_021",  # Thrallmar Farseer
    "VAN_CS2_124",  # Wolfrider
    "VAN_CS2_182",  # Chillwind Yeti
    "VAN_EX1_396",  # Mogu'shan Warden
    "VAN_CS2_119",  # Oasis Snapjaw
    "VAN_CS2_197",  # Ogre Magi
    "VAN_CS2_179",  # Sen'jin Shieldmasta
    "VAN_EX1_023",  # Silvermoon Guardian
    "VAN_CS2_131",  # Stormwind Knight
    "VAN_CS2_187",  # Booty Bay Bodyguard
    "VAN_CS1_069",  # Fen Creeper
    "VAN_EX1_028",  # Stranglethorn Tiger
    "VAN_CS2_155",  # Archmage
    "VAN_EX1_067",  # Argent Commander
    "VAN_CS2_200",  # Boulderfist Ogre
    "VAN_CS2_162",  # Lord of the Arena
    "VAN_CS2_213",  # Reckless Rocketeer
    "VAN_EX1_032",  # Sunwalker
    "VAN_EX1_033",  # Windfury Harpy
    "VAN_CS2_201",  # Core Hound
    "VAN_CS2_161",  # Ravenholdt Assassin
    "VAN_CS2_186",  # War Golem
    "VAN_EX1_563",  # Malygos
    "VAN_EX1_243",  # Dust Devil
    "GVG_044",  # Spider Tank
    "GVG_085",  # Annoy-o-Tron
    "GVG_058",  # Shielded Minibot
    "GVG_037",  # Whirling Zap-o-matic
    "AT_052",  # Totem Golem
    "OG_024",  # Flamewreathed Faceless
}

SECRET_CARDS = {
    "LF_002",
    "VAN_EX1_610", "VAN_EX1_611", "VAN_EX1_533", "VAN_EX1_554", "VAN_EX1_609",
    "VAN_EX1_287", "VAN_EX1_289", "VAN_EX1_295", "VAN_EX1_294", "VAN_tt_010", "VAN_EX1_594",
    "VAN_EX1_132", "VAN_EX1_130", "VAN_EX1_136", "VAN_EX1_379",
}

AURA_CARDS = {
    "LF_001", "LF_006",
    "VAN_DS1_175", "VAN_DS1_178", "VAN_EX1_608", "VAN_EX1_565", "VAN_CS2_221",
    "VAN_EX1_508", "VAN_CS2_146", "VAN_EX1_162", "VAN_EX1_616", "VAN_EX1_076",
    "VAN_EX1_507", "VAN_CS2_122", "VAN_NEW1_027", "VAN_EX1_062", "VAN_CS2_227",
    "VAN_CS2_222", "VAN_EX1_591", "VAN_EX1_335", "VAN_EX1_350", "VAN_EX1_315",
    "VAN_EX1_586", "VAN_EX1_105", "VAN_EX1_620", "VAN_NEW1_022",
    "VAN_EX1_009", "VAN_EX1_393", "VAN_EX1_412", "VAN_EX1_390", "VAN_EX1_414",
    "VAN_EX1_560",  # Nozdormu (15s turn visual indicator)
    "GVG_006", "GVG_013", "LOE_077", "OG_044", "OG_028", "KAR_063",
}

SPECIAL_TRIGGER_CARDS = {
    "VAN_EX1_531", "VAN_CS2_237", "VAN_NEW1_012", "VAN_EX1_274", "VAN_EX1_559",
    "VAN_CS2_235", "VAN_EX1_341", "VAN_EX1_522", "VAN_EX1_575", "VAN_EX1_258",
    "VAN_CS2_059", "VAN_EX1_402", "VAN_EX1_604", "VAN_EX1_084", "VAN_EX1_001",
    "VAN_EX1_509", "VAN_EX1_080", "VAN_EX1_004", "VAN_NEW1_021", "VAN_NEW1_019",
    "VAN_EX1_100", "VAN_EX1_055", "VAN_NEW1_037", "VAN_EX1_557", "VAN_NEW1_020",
    "VAN_EX1_007", "VAN_EX1_006", "VAN_EX1_102", "VAN_EX1_170", "VAN_tt_004",
    "VAN_EX1_597", "VAN_EX1_044", "VAN_EX1_595", "VAN_NEW1_026", "VAN_EX1_095",
    "VAN_EX1_399", "VAN_NEW1_040", "VAN_EX1_614", "VAN_EX1_249", "VAN_NEW1_038",
    "VAN_EX1_298", "VAN_EX1_572", "VAN_CS2_033",
    "FP1_005", "FP1_013", "GVG_016", "BRM_028", "BRM_006", "GVG_002", "BRM_002", "LOE_018",
}

DEATHRATTLE_CARDS = {
    "LF_003", "LF_005",
    "VAN_EX1_534", "VAN_EX1_383", "VAN_EX1_029", "VAN_EX1_012", "VAN_EX1_096",
    "VAN_EX1_556", "VAN_EX1_097", "VAN_EX1_110", "VAN_EX1_016", "VAN_EX1_577",
    "FP1_001", "FP1_002", "FP1_004", "FP1_009", "FP1_012", "GVG_076", "GVG_082",
    "GVG_096", "GVG_110t", "CFM_902", "AT_038", "FP1_011", "KAR_005", "LOE_012",
}

WEAPON_CARDS = {
    "VAN_EX1_536", "VAN_DS1_188", "VAN_CS2_091", "VAN_EX1_366", "VAN_CS2_097",
    "VAN_EX1_133", "VAN_CS2_080", "VAN_EX1_247", "VAN_EX1_567", "VAN_CS2_106",
    "VAN_CS2_112", "VAN_EX1_411",
    "FP1_021", "GVG_036", "KAR_063",
}

SPARE_PARTS = [
    "PART_001", "PART_002", "PART_003", "PART_004", "PART_005", "PART_006", "PART_007",
]

BASIC_HERO_POWERS = [
    "VAN_HERO_01bp", "VAN_HERO_02bp", "VAN_HERO_03bp",
    "VAN_HERO_04bp", "VAN_HERO_05bp", "VAN_HERO_06bp",
    "VAN_HERO_07bp", "VAN_HERO_08bp", "VAN_HERO_09bp",
]

UPGRADED_HERO_POWERS = {
    "VAN_HERO_01bp": "AT_132_WARRIOR",
    "VAN_HERO_02bp": "AT_132_SHAMAN",
    "VAN_HERO_03bp": "AT_132_ROGUE",
    "VAN_HERO_04bp": "AT_132_PALADIN",
    "VAN_HERO_05bp": "AT_132_HUNTER",
    "VAN_HERO_06bp": "AT_132_DRUID",
    "VAN_HERO_07bp": "AT_132_WARLOCK",
    "VAN_HERO_08bp": "AT_132_MAGE",
    "VAN_HERO_09bp": "AT_132_PRIEST",
}


BANE_OF_DOOM_DEMONS = [
    "VAN_CS2_059",  # Blood Imp
    "VAN_CS2_065",  # Voidwalker
    "VAN_EX1_319",  # Flame Imp
    "VAN_EX1_306",  # Felstalker
    "VAN_EX1_301",  # Felguard
    "VAN_EX1_304",  # Void Terror
    "VAN_EX1_313",  # Pit Lord
    "VAN_EX1_310",  # Doomguard
    "VAN_CS2_064",  # Dread Infernal
    "VAN_EX1_614",  # Illidan Stormrage
    "VAN_EX1_323",  # Lord Jaraxxus
]

HORDE_WARRIORS = [
    "VAN_CS2_121",  # Frostwolf Grunt
    "VAN_CS2_179",  # Sen'jin Shieldmasta
    "VAN_EX1_390",  # Tauren Warrior
    "VAN_EX1_021",  # Thrallmar Farseer
    "VAN_EX1_023",  # Silvermoon Guardian
    "VAN_EX1_110",  # Cairne Bloodhoof
]

DREAM_CARDS = [
    "VAN_DREAM_01",  # Laughing Sister
    "VAN_DREAM_02",  # Ysera Awakens
    "VAN_DREAM_03",  # Emerald Drake
    "VAN_DREAM_04",  # Dream
    "VAN_DREAM_05",  # Nightmare
]

GELBIN_INVENTIONS = ["Mekka1", "Mekka2", "Mekka3", "Mekka4"]
ETC_POWER_CHORDS = ["PRO_001a", "PRO_001b", "VAN_PRO_001c"]
BASIC_TOTEMS = ["VAN_CS2_050", "VAN_CS2_051", "VAN_CS2_052", "VAN_NEW1_009"]
ANIMAL_COMPANIONS = ["VAN_NEW1_032", "VAN_NEW1_033", "VAN_NEW1_034"]


def _choose_druid_of_claw(engine: GameEngine, seat: str, minion: Minion, choose: int) -> None:
    # Replace in place with transformed form
    form_id = "VAN_EX1_165t1" if choose == 0 else "VAN_EX1_165t2"
    board = engine.state.players[seat].board
    if minion in board:
        idx = board.index(minion)
        board.pop(idx)
        engine.summon_minion(seat, form_id, pos=idx, trigger_summon=False, replaces=minion.uid)


def _spell_dmg(engine: GameEngine, seat: str, base: int) -> int:
    return engine.calc_spell_damage(seat, base)


def _spell_heal(engine: GameEngine, seat: str, base: int) -> int:
    return engine.calc_spell_healing(seat, base)


def _deal_spell_or_heal_hero(engine: GameEngine, seat: str, target_id: str, amount: int) -> None:
    engine.apply_heal(seat, target_id, _spell_heal(engine, seat, amount), from_spell_or_power=True)


# ---------------------------------------------------------------------------
# SPELL HANDLERS
# ---------------------------------------------------------------------------

def cast_spell(engine: GameEngine, seat: str, card_id: str, target_id: Optional[str], choose: Optional[int], was_combo: bool) -> None:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]
    sd = lambda base: _spell_dmg(engine, seat, base)
    sh = lambda base: _spell_heal(engine, seat, base)

    # --- Token / Neutral Spells ---
    if card_id == "GAME_005":  # The Coin
        p.mana = min(10, p.mana + 1)
    elif card_id == "CS2_013t":  # Excess Mana
        engine.draw_card(seat)
    elif card_id == "EX1_014t":  # Bananas
        engine.add_enchantment(target_id, card_id, "Bananas", atk=1, hp=1)
    elif card_id == "VAN_DREAM_02":  # Ysera Awakens
        targets = ["hero_p1", "hero_p2"] + [
            m.uid for s in ("p1", "p2") for m in engine.state.players[s].board if m.card_id != "VAN_EX1_572"
        ]
        dmg = sd(5)
        for tid in targets:
            engine.deal_damage(tid, dmg, source_seat=seat, source_name="Ysera Awakens")
    elif card_id == "VAN_DREAM_04":  # Dream
        m = engine.find_minion(target_id)
        if m:
            engine.bounce_minion(m)
    elif card_id == "VAN_DREAM_05":  # Nightmare
        engine.add_enchantment(target_id, card_id, "Nightmare", atk=5, hp=5, destroy_at_owner_sot=seat)
    elif card_id == "PRO_001a":  # I Am Murloc
        cnt = engine.rng.choice([3, 4, 5])
        for _ in range(cnt):
            engine.summon_minion(seat, "PRO_001at")
    elif card_id == "PRO_001b":  # Rogues Do It...
        engine.deal_damage(target_id, sd(4), source_seat=seat, source_name="Rogues Do It...")
        engine.draw_card(seat)
    elif card_id == "VAN_PRO_001c":  # Power of the Horde
        engine.summon_minion(seat, engine.rng.choice(HORDE_WARRIORS))

    # --- DRUID ---
    elif card_id == "VAN_EX1_169":  # Innervate
        p.mana = min(10, p.mana + 2)
    elif card_id == "VAN_CS2_008":  # Moonfire
        engine.deal_damage(target_id, sd(1), source_seat=seat, source_name="Moonfire")
    elif card_id == "VAN_CS2_005":  # Claw
        p.hero.temp_attack += 2
        p.hero.armor += 2
    elif card_id == "VAN_EX1_161":  # Naturalize
        engine.destroy_minion(target_id)
        engine.draw_card(opp_seat)
        engine.draw_card(opp_seat)
    elif card_id == "VAN_EX1_578":  # Savagery
        engine.deal_damage(target_id, sd(p.hero.attack), source_seat=seat, source_name="Savagery")
    elif card_id == "VAN_CS2_009":  # Mark of the Wild
        engine.add_enchantment(target_id, card_id, "Mark of the Wild", atk=2, hp=2, add_keywords={"TAUNT"})
    elif card_id == "VAN_EX1_160":  # Power of the Wild
        both = engine.has_fandral(seat)
        if both or choose == 1:
            engine.summon_minion(seat, "EX1_160t")
        if both or choose == 0:
            for m in list(p.board):
                engine.add_enchantment(m.uid, card_id, "Leader of the Pack", atk=1, hp=1)
    elif card_id == "VAN_CS2_013":  # Wild Growth
        if p.max_mana >= 10:
            engine.add_card_to_hand(seat, "CS2_013t")
        else:
            p.max_mana = min(10, p.max_mana + 1)
    elif card_id == "VAN_EX1_154":  # Wrath
        both = engine.has_fandral(seat)
        if both:
            engine.deal_damage(target_id, sd(4), source_seat=seat, source_name="Wrath")
            engine.draw_card(seat)
        elif choose == 0:
            engine.deal_damage(target_id, sd(3), source_seat=seat, source_name="Wrath")
        else:
            engine.deal_damage(target_id, sd(1), source_seat=seat, source_name="Wrath")
            engine.draw_card(seat)
    elif card_id == "VAN_CS2_007":  # Healing Touch
        engine.apply_heal(seat, target_id, sh(8), from_spell_or_power=True)
    elif card_id == "VAN_EX1_155":  # Mark of Nature
        both = engine.has_fandral(seat)
        if both:
            engine.add_enchantment(target_id, card_id, "Mark of Nature", atk=4, hp=4, add_keywords={"TAUNT"})
        elif choose == 0:
            engine.add_enchantment(target_id, card_id, "Mark of Nature", atk=4)
        else:
            engine.add_enchantment(target_id, card_id, "Mark of Nature", hp=4, add_keywords={"TAUNT"})
    elif card_id == "VAN_CS2_011":  # Savage Roar
        p.hero.temp_attack += 2
        for m in list(p.board):
            engine.add_enchantment(m.uid, card_id, "Savage Roar", atk=2, temp_until_eot=True)
    elif card_id == "VAN_EX1_570":  # Bite
        p.hero.temp_attack += 4
        p.hero.armor += 4
    elif card_id == "VAN_EX1_158":  # Soul of the Forest
        for m in list(p.board):
            engine.add_enchantment(m.uid, card_id, "Soul of the Forest", extra_deathrattle="TREANT")
    elif card_id == "VAN_CS2_012":  # Swipe
        main_dmg = sd(4)
        splash_dmg = sd(1)
        all_enemies = [f"hero_{opp_seat}"] + [m.uid for m in opp.board]
        engine.deal_damage(target_id, main_dmg, source_seat=seat, source_name="Swipe")
        for tid in all_enemies:
            if tid != target_id:
                engine.deal_damage(tid, splash_dmg, source_seat=seat, source_name="Swipe")
    elif card_id == "VAN_EX1_164":  # Nourish
        both = engine.has_fandral(seat)
        if both or choose == 0:
            p.max_mana = min(10, p.max_mana + 2)
            p.mana = min(10, p.mana + 2)
        if both or choose == 1:
            for _ in range(3):
                engine.draw_card(seat)
    elif card_id == "VAN_NEW1_007":  # Starfall
        both = engine.has_fandral(seat)
        if (both or choose == 0) and target_id:
            engine.deal_damage(target_id, sd(5), source_seat=seat, source_name="Starfall")
        if both or choose == 1:
            dmg = sd(2)
            for m in list(opp.board):
                engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Starfall")
    elif card_id == "VAN_EX1_571":  # Force of Nature
        for _ in range(3):
            m = engine.summon_minion(seat, "VAN_EX1_tk9b")
            if m:
                engine.add_enchantment(m.uid, card_id, "Force of Nature", destroy_at_eot=True)
    elif card_id == "VAN_EX1_173":  # Starfire
        engine.deal_damage(target_id, sd(5), source_seat=seat, source_name="Starfire")
        engine.draw_card(seat)

    # --- HUNTER ---
    elif card_id == "VAN_CS2_084":  # Hunter's Mark
        engine.add_enchantment(target_id, card_id, "Hunter's Mark", set_hp=1)
    elif card_id == "VAN_DS1_185":  # Arcane Shot
        engine.deal_damage(target_id, sd(2), source_seat=seat, source_name="Arcane Shot")
    elif card_id == "VAN_EX1_549":  # Bestial Wrath
        m = engine.find_minion(target_id)
        if m:
            engine.add_enchantment(m.uid, card_id, "Bestial Wrath", atk=2, temp_until_eot=True)
            m.immune_this_turn = True
    elif card_id == "VAN_EX1_544":  # Flare
        for s in ("p1", "p2"):
            for m in engine.state.players[s].board:
                m.base_keywords.discard("STEALTH")
                for e in m.enchantments:
                    e.add_keywords.discard("STEALTH")
                m.stealth_until_sot_of = None
        if opp.secrets:
            engine.destroy_secrets(opp.seat)
            engine.add_log("All enemy Secrets were destroyed by Flare.")
        engine.draw_card(seat)
    elif card_id == "VAN_DS1_184":  # Tracking
        top = p.deck[:3]
        p.deck = p.deck[3:]
        if len(top) == 1:
            engine.give_card_instance_to_hand(seat, top[0])
        elif len(top) > 1:
            from engine.models import PendingChoice
            engine.state.pending_choice = PendingChoice(
                seat=seat,
                choice_type="TRACKING",
                source_card_id=card_id,
                options=top,
            )
    elif card_id == "VAN_NEW1_031":  # Animal Companion
        engine.summon_minion(seat, engine.rng.choice(ANIMAL_COMPANIONS))
    elif card_id == "VAN_EX1_617":  # Deadly Shot
        if opp.board:
            chosen = engine.rng.choice(opp.board)
            engine.destroy_minion(chosen.uid)
    elif card_id == "VAN_EX1_539":  # Kill Command
        has_beast = any(m.race == "BEAST" for m in p.board)
        dmg = sd(5 if has_beast else 3)
        engine.deal_damage(target_id, dmg, source_seat=seat, source_name="Kill Command")
    elif card_id == "VAN_EX1_538":  # Unleash the Hounds
        count = len(opp.board)
        for _ in range(count):
            engine.summon_minion(seat, "EX1_538t")
    elif card_id == "VAN_DS1_183":  # Multi-Shot
        targets = engine.rng.sample(list(opp.board), min(2, len(opp.board)))
        dmg = sd(3)
        for m in targets:
            engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Multi-Shot")
    elif card_id == "VAN_EX1_537":  # Explosive Shot
        m = engine.find_minion(target_id)
        if m:
            owner_board = engine.state.players[m.owner].board
            idx = owner_board.index(m)
            adj = []
            if idx - 1 >= 0:
                adj.append(owner_board[idx - 1].uid)
            if idx + 1 < len(owner_board):
                adj.append(owner_board[idx + 1].uid)
            engine.deal_damage(m.uid, sd(5), source_seat=seat, source_name="Explosive Shot")
            splash = sd(2)
            for aid in adj:
                engine.deal_damage(aid, splash, source_seat=seat, source_name="Explosive Shot")

    # --- MAGE ---
    elif card_id == "VAN_EX1_277":  # Arcane Missiles
        missiles = sd(3)
        for _ in range(missiles):
            cands = engine.living_enemy_characters(seat)
            if not cands:
                break
            t = engine.rng.choice(cands)
            engine.deal_damage(t, 1, source_seat=seat, source_name="Arcane Missiles")
            engine.resolve_deaths()
    elif card_id == "VAN_CS2_031":  # Ice Lance
        if engine.is_frozen(target_id):
            engine.deal_damage(target_id, sd(4), source_seat=seat, source_name="Ice Lance")
        else:
            engine.freeze_character(target_id)
    elif card_id == "VAN_CS2_027":  # Mirror Image
        for _ in range(2):
            engine.summon_minion(seat, "VAN_CS2_mirror")
    elif card_id == "VAN_CS2_025":  # Arcane Explosion
        dmg = sd(1)
        for m in list(opp.board):
            engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Arcane Explosion")
    elif card_id == "VAN_CS2_024":  # Frostbolt
        engine.deal_damage(target_id, sd(3), source_seat=seat, source_name="Frostbolt")
        engine.freeze_character(target_id)
    elif card_id == "VAN_CS2_023":  # Arcane Intellect
        engine.draw_card(seat)
        engine.draw_card(seat)
    elif card_id == "VAN_CS2_026":  # Frost Nova
        for m in list(opp.board):
            engine.freeze_character(m.uid)
    elif card_id == "VAN_EX1_275":  # Cone of Cold
        m = engine.find_minion(target_id)
        if m:
            owner_board = engine.state.players[m.owner].board
            idx = owner_board.index(m)
            targets = [m.uid]
            if idx - 1 >= 0:
                targets.append(owner_board[idx - 1].uid)
            if idx + 1 < len(owner_board):
                targets.append(owner_board[idx + 1].uid)
            dmg = sd(1)
            for tid in targets:
                engine.deal_damage(tid, dmg, source_seat=seat, source_name="Cone of Cold")
                engine.freeze_character(tid)
    elif card_id == "VAN_CS2_029":  # Fireball
        engine.deal_damage(target_id, sd(6), source_seat=seat, source_name="Fireball")
    elif card_id == "VAN_CS2_022":  # Polymorph
        engine.transform_minion(target_id, "VAN_CS2_tk1")
    elif card_id == "VAN_CS2_028":  # Blizzard
        dmg = sd(2)
        for m in list(opp.board):
            engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Blizzard")
            engine.freeze_character(m.uid)
    elif card_id == "VAN_CS2_032":  # Flamestrike
        dmg = sd(4)
        for m in list(opp.board):
            engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Flamestrike")
    elif card_id == "VAN_EX1_279":  # Pyroblast
        engine.deal_damage(target_id, sd(10), source_seat=seat, source_name="Pyroblast")

    # --- PALADIN ---
    elif card_id == "VAN_CS2_087":  # Blessing of Might
        engine.add_enchantment(target_id, card_id, "Blessing of Might", atk=3)
    elif card_id == "VAN_EX1_363":  # Blessing of Wisdom
        engine.add_enchantment(target_id, card_id, "Blessing of Wisdom", blessing_of_wisdom_owner=seat)
    elif card_id == "VAN_EX1_371":  # Hand of Protection
        engine.add_enchantment(target_id, card_id, "Hand of Protection", add_keywords={"DIVINE_SHIELD"})
    elif card_id == "VAN_EX1_360":  # Humility
        engine.add_enchantment(target_id, card_id, "Humility", set_atk=1)
    elif card_id == "VAN_EX1_619":  # Equality
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                engine.add_enchantment(m.uid, card_id, "Equality", set_hp=1)
    elif card_id == "VAN_CS2_089":  # Holy Light
        engine.apply_heal(seat, target_id, sh(6), from_spell_or_power=True)
    elif card_id == "VAN_EX1_349":  # Divine Favor
        diff = len(opp.hand) - len(p.hand)
        for _ in range(max(0, diff)):
            engine.draw_card(seat)
    elif card_id == "VAN_CS2_092":  # Blessing of Kings
        engine.add_enchantment(target_id, card_id, "Blessing of Kings", atk=4, hp=4)
    elif card_id == "VAN_CS2_093":  # Consecration
        dmg = sd(2)
        for tid in [f"hero_{opp_seat}"] + [m.uid for m in opp.board]:
            engine.deal_damage(tid, dmg, source_seat=seat, source_name="Consecration")
    elif card_id == "VAN_CS2_094":  # Hammer of Wrath
        engine.deal_damage(target_id, sd(3), source_seat=seat, source_name="Hammer of Wrath")
        engine.draw_card(seat)
    elif card_id == "VAN_EX1_355":  # Blessed Champion
        m = engine.find_minion(target_id)
        if m:
            engine.add_enchantment(m.uid, card_id, "Blessed Champion", atk=m.attack)
    elif card_id == "VAN_EX1_365":  # Holy Wrath
        drawn = engine.draw_card(seat)
        base_cost = 0
        if drawn:
            from engine.catalog import get_card
            base_cost = get_card(drawn.card_id).cost
        engine.deal_damage(target_id, sd(base_cost), source_seat=seat, source_name="Holy Wrath")
    elif card_id == "VAN_EX1_384":  # Avenging Wrath
        missiles = sd(8)
        for _ in range(missiles):
            cands = engine.living_enemy_characters(seat)
            if not cands:
                break
            t = engine.rng.choice(cands)
            engine.deal_damage(t, 1, source_seat=seat, source_name="Avenging Wrath")
            engine.resolve_deaths()
    elif card_id == "VAN_EX1_354":  # Lay on Hands
        engine.apply_heal(seat, target_id, sh(8), from_spell_or_power=True)
        for _ in range(3):
            engine.draw_card(seat)

    # --- PRIEST ---
    elif card_id == "VAN_EX1_621":  # Circle of Healing
        heal_amt = sh(4)
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                engine.apply_heal(seat, m.uid, heal_amt, from_spell_or_power=True)
    elif card_id == "VAN_EX1_332":  # Silence
        engine.silence_minion(target_id)
    elif card_id == "VAN_CS1_130":  # Holy Smite
        engine.deal_damage(target_id, sd(2), source_seat=seat, source_name="Holy Smite")
    elif card_id == "VAN_CS1_129":  # Inner Fire
        m = engine.find_minion(target_id)
        if m:
            engine.add_enchantment(m.uid, card_id, "Inner Fire", set_atk=max(0, m.health))
    elif card_id == "VAN_CS2_003":  # Mind Vision
        if opp.hand:
            copied = engine.rng.choice(opp.hand)
            engine.add_card_to_hand(seat, copied.card_id)
    elif card_id == "VAN_CS2_004":  # Power Word: Shield
        engine.add_enchantment(target_id, card_id, "Power Word: Shield", hp=2)
        engine.draw_card(seat)
    elif card_id == "VAN_CS2_236":  # Divine Spirit
        m = engine.find_minion(target_id)
        if m:
            engine.add_enchantment(m.uid, card_id, "Divine Spirit", hp=max(0, m.health))
    elif card_id == "VAN_DS1_233":  # Mind Blast
        engine.deal_damage(f"hero_{opp_seat}", sd(5), source_seat=seat, source_name="Mind Blast")
    elif card_id == "VAN_CS2_234":  # Shadow Word: Pain
        engine.destroy_minion(target_id)
    elif card_id == "VAN_EX1_622":  # Shadow Word: Death
        engine.destroy_minion(target_id)
    elif card_id == "VAN_EX1_625":  # Shadowform
        if p.hero.shadowform_level == 0:
            p.hero.shadowform_level = 1
            p.hero.hero_power_id = "EX1_625t"
        else:
            p.hero.shadowform_level = 2
            p.hero.hero_power_id = "EX1_625t2"
        p.hero.hero_power_used = False
    elif card_id == "VAN_EX1_339":  # Thoughtsteal
        if opp.deck:
            k = min(2, len(opp.deck))
            picks = engine.rng.sample(opp.deck, k)
            for ci in picks:
                engine.add_card_to_hand(seat, ci.card_id)
    elif card_id == "VAN_EX1_626":  # Mass Dispel
        for m in list(opp.board):
            engine.silence_minion(m.uid)
        engine.draw_card(seat)
    elif card_id == "VAN_EX1_345":  # Mindgames
        from engine.catalog import get_card
        minions_in_deck = [ci for ci in opp.deck if get_card(ci.card_id).type == "MINION"]
        if minions_in_deck:
            pick = engine.rng.choice(minions_in_deck)
            engine.summon_minion(seat, pick.card_id)
        else:
            engine.summon_minion(seat, "VAN_EX1_345t")
    elif card_id == "VAN_EX1_334":  # Shadow Madness
        m = engine.find_minion(target_id)
        if m and m.owner == opp_seat and len(p.board) < 7:
            engine.steal_minion(m.uid, seat)
            engine.add_enchantment(
                m.uid, card_id, "Shadow Madness",
                add_keywords={"CHARGE"}, temp_until_eot=True, temp_owner_revert=opp_seat,
            )
    elif card_id == "VAN_CS1_112":  # Holy Nova
        dmg = sd(2)
        heal = sh(2)
        for tid in [f"hero_{opp_seat}"] + [m.uid for m in opp.board]:
            engine.deal_damage(tid, dmg, source_seat=seat, source_name="Holy Nova")
        for tid in [f"hero_{seat}"] + [m.uid for m in p.board]:
            engine.apply_heal(seat, tid, heal, from_spell_or_power=True)
    elif card_id == "VAN_EX1_624":  # Holy Fire
        engine.deal_damage(target_id, sd(5), source_seat=seat, source_name="Holy Fire")
        engine.apply_heal(seat, f"hero_{seat}", sh(5), from_spell_or_power=True)
    elif card_id == "VAN_CS1_113":  # Mind Control
        engine.steal_minion(target_id, seat)

    # --- ROGUE ---
    elif card_id == "VAN_CS2_072":  # Backstab
        engine.deal_damage(target_id, sd(2), source_seat=seat, source_name="Backstab")
    elif card_id == "VAN_EX1_145":  # Preparation
        p.next_spell_cost_mod = max(p.next_spell_cost_mod, 3)
    elif card_id == "VAN_EX1_144":  # Shadowstep
        m = engine.find_minion(target_id)
        if m:
            engine.bounce_minion(m, cost_mod_delta=-2)
    elif card_id == "VAN_CS2_073":  # Cold Blood
        atk = 4 if was_combo else 2
        engine.add_enchantment(target_id, card_id, "Cold Blood", atk=atk)
    elif card_id == "VAN_EX1_128":  # Conceal
        for m in list(p.board):
            engine.add_enchantment(m.uid, card_id, "Conceal", add_keywords={"STEALTH"})
            m.stealth_until_sot_of = seat
    elif card_id == "VAN_CS2_074":  # Deadly Poison
        if p.weapon:
            p.weapon.attack_bonus += 2
    elif card_id == "VAN_CS2_075":  # Sinister Strike
        engine.deal_damage(f"hero_{opp_seat}", sd(3), source_seat=seat, source_name="Sinister Strike")
    elif card_id == "VAN_EX1_126":  # Betrayal
        m = engine.find_minion(target_id)
        if m and m.attack > 0:
            board = engine.state.players[m.owner].board
            idx = board.index(m)
            adj = []
            if idx - 1 >= 0:
                adj.append(board[idx - 1].uid)
            if idx + 1 < len(board):
                adj.append(board[idx + 1].uid)
            for aid in adj:
                engine.deal_damage(aid, m.attack, source_seat=m.owner, source_name=m.name, source_minion=m)
    elif card_id == "VAN_CS2_233":  # Blade Flurry
        if p.weapon:
            dmg = sd(p.weapon.total_attack)
            engine.destroy_weapon(seat)
            for tid in [f"hero_{opp_seat}"] + [m.uid for m in opp.board]:
                engine.deal_damage(tid, dmg, source_seat=seat, source_name="Blade Flurry")
    elif card_id == "VAN_EX1_124":  # Eviscerate
        dmg = sd(4 if was_combo else 2)
        engine.deal_damage(target_id, dmg, source_seat=seat, source_name="Eviscerate")
    elif card_id == "VAN_EX1_581":  # Sap
        m = engine.find_minion(target_id)
        if m:
            engine.bounce_minion(m)
    elif card_id == "VAN_EX1_278":  # Shiv
        engine.deal_damage(target_id, sd(1), source_seat=seat, source_name="Shiv")
        engine.draw_card(seat)
    elif card_id == "VAN_EX1_129":  # Fan of Knives
        dmg = sd(1)
        for m in list(opp.board):
            engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Fan of Knives")
        engine.draw_card(seat)
    elif card_id == "VAN_EX1_137":  # Headcrack
        engine.deal_damage(f"hero_{opp_seat}", sd(2), source_seat=seat, source_name="Headcrack")
        if was_combo:
            p.headcrack_return_eot = True
    elif card_id == "VAN_CS2_076":  # Assassinate
        engine.destroy_minion(target_id)
    elif card_id == "VAN_NEW1_004":  # Vanish
        # Bounce in play order (we iterate combined boards)
        all_minions = list(p.board) + list(opp.board)
        for m in all_minions:
            engine.bounce_minion(m)
    elif card_id == "VAN_CS2_077":  # Sprint
        for _ in range(4):
            engine.draw_card(seat)

    # --- SHAMAN ---
    elif card_id == "VAN_CS2_041":  # Ancestral Healing
        m = engine.find_minion(target_id)
        if m:
            engine.apply_heal(seat, m.uid, m.max_health, from_spell_or_power=True)
            engine.add_enchantment(m.uid, card_id, "Ancestral Healing", add_keywords={"TAUNT"})
    elif card_id == "VAN_EX1_244":  # Totemic Might
        for m in list(p.board):
            if m.race == "TOTEM":
                engine.add_enchantment(m.uid, card_id, "Totemic Might", hp=2)
    elif card_id == "VAN_EX1_245":  # Earth Shock
        engine.silence_minion(target_id)
        engine.deal_damage(target_id, sd(1), source_seat=seat, source_name="Earth Shock")
    elif card_id == "VAN_EX1_251":  # Forked Lightning
        targets = engine.rng.sample(list(opp.board), min(2, len(opp.board)))
        dmg = sd(2)
        for m in targets:
            engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Forked Lightning")
    elif card_id == "VAN_CS2_037":  # Frost Shock
        engine.deal_damage(target_id, sd(1), source_seat=seat, source_name="Frost Shock")
        engine.freeze_character(target_id)
    elif card_id == "VAN_EX1_238":  # Lightning Bolt
        engine.deal_damage(target_id, sd(3), source_seat=seat, source_name="Lightning Bolt")
    elif card_id == "VAN_CS2_045":  # Rockbiter Weapon
        if target_id == f"hero_{seat}":
            p.hero.temp_attack += 3
        else:
            engine.add_enchantment(target_id, card_id, "Rockbiter Weapon", atk=3, temp_until_eot=True)
    elif card_id == "VAN_CS2_038":  # Ancestral Spirit
        engine.add_enchantment(target_id, card_id, "Ancestral Spirit", extra_deathrattle="RESUMMON")
    elif card_id == "VAN_CS2_039":  # Windfury
        engine.add_enchantment(target_id, card_id, "Windfury", add_keywords={"WINDFURY"})
    elif card_id == "VAN_CS2_053":  # Far Sight
        drawn = engine.draw_card(seat)
        if drawn:
            drawn.cost_mod -= 3
    elif card_id == "VAN_EX1_248":  # Feral Spirit
        for _ in range(2):
            engine.summon_minion(seat, "VAN_EX1_tk11")
    elif card_id == "VAN_EX1_246":  # Hex
        engine.transform_minion(target_id, "hexfrog")
    elif card_id == "VAN_EX1_241":  # Lava Burst
        engine.deal_damage(target_id, sd(5), source_seat=seat, source_name="Lava Burst")
    elif card_id == "VAN_EX1_259":  # Lightning Storm
        for m in list(opp.board):
            dmg = sd(engine.rng.choice([2, 3]))
            engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Lightning Storm")
    elif card_id == "VAN_CS2_046":  # Bloodlust
        for m in list(p.board):
            engine.add_enchantment(m.uid, card_id, "Bloodlust", atk=3, temp_until_eot=True)

    # --- WARLOCK ---
    elif card_id == "VAN_NEW1_003":  # Sacrificial Pact
        if target_id == f"hero_{seat}" or target_id == f"hero_{opp_seat}":
            tseat = target_id.split("_")[1]
            engine.state.players[tseat].hero.hp = 0
        else:
            engine.destroy_minion(target_id)
        engine.apply_heal(seat, f"hero_{seat}", sh(5), from_spell_or_power=True)
    elif card_id == "VAN_EX1_308":  # Soulfire
        engine.deal_damage(target_id, sd(4), source_seat=seat, source_name="Soulfire")
        engine.discard_random(seat)
    elif card_id == "VAN_CS2_063":  # Corruption
        engine.add_enchantment(target_id, card_id, "Corruption", destroy_at_owner_sot=seat)
    elif card_id == "VAN_EX1_302":  # Mortal Coil
        m = engine.find_minion(target_id)
        if m:
            engine.deal_damage(m.uid, sd(1), source_seat=seat, source_name="Mortal Coil")
            if m.health <= 0:
                engine.draw_card(seat)
    elif card_id == "VAN_EX1_316":  # Power Overwhelming
        engine.add_enchantment(target_id, card_id, "Power Overwhelming", atk=4, hp=4, destroy_at_eot=True)
    elif card_id == "VAN_EX1_596":  # Demonfire
        m = engine.find_minion(target_id)
        if m:
            if m.owner == seat and m.race == "DEMON":
                engine.add_enchantment(m.uid, card_id, "Demonfire", atk=2, hp=2)
            else:
                engine.deal_damage(m.uid, sd(2), source_seat=seat, source_name="Demonfire")
    elif card_id == "VAN_CS2_061":  # Drain Life
        engine.deal_damage(target_id, sd(2), source_seat=seat, source_name="Drain Life")
        engine.apply_heal(seat, f"hero_{seat}", sh(2), from_spell_or_power=True)
    elif card_id == "VAN_EX1_317":  # Sense Demons
        from engine.catalog import get_card
        for _ in range(2):
            demons = [i for i, ci in enumerate(p.deck) if get_card(ci.card_id).race == "DEMON"]
            if demons:
                idx = engine.rng.choice(demons)
                ci = p.deck.pop(idx)
                engine.give_card_instance_to_hand(seat, ci)
            else:
                engine.add_card_to_hand(seat, "EX1_317t")
    elif card_id == "VAN_CS2_057":  # Shadow Bolt
        engine.deal_damage(target_id, sd(4), source_seat=seat, source_name="Shadow Bolt")
    elif card_id == "VAN_CS2_062":  # Hellfire
        dmg = sd(3)
        for tid in ["hero_p1", "hero_p2"] + [m.uid for s in ("p1", "p2") for m in engine.state.players[s].board]:
            engine.deal_damage(tid, dmg, source_seat=seat, source_name="Hellfire")
    elif card_id == "VAN_EX1_303":  # Shadowflame
        m = engine.find_minion(target_id)
        if m:
            dmg = sd(m.attack)
            engine.destroy_minion(m.uid)
            for em in list(opp.board):
                engine.deal_damage(em.uid, dmg, source_seat=seat, source_name="Shadowflame")
    elif card_id == "VAN_EX1_320":  # Bane of Doom
        m = engine.find_minion(target_id)
        engine.deal_damage(target_id, sd(3), source_seat=seat, source_name="Bane of Doom")
        died = False
        if m and m.health <= 0:
            died = True
        elif target_id.startswith("hero_"):
            tseat = target_id.split("_")[1]
            died = engine.state.players[tseat].hero.hp <= 0
        if died:
            engine.summon_minion(seat, engine.rng.choice(BANE_OF_DOOM_DEMONS))
    elif card_id == "VAN_EX1_309":  # Siphon Soul
        engine.destroy_minion(target_id)
        engine.apply_heal(seat, f"hero_{seat}", sh(3), from_spell_or_power=True)
    elif card_id == "VAN_EX1_312":  # Twisting Nether
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                engine.destroy_minion(m.uid)

    # --- WARRIOR ---
    elif card_id == "VAN_EX1_607":  # Inner Rage
        engine.deal_damage(target_id, sd(1), source_seat=seat, source_name="Inner Rage")
        engine.add_enchantment(target_id, card_id, "Inner Rage", atk=2)
    elif card_id == "VAN_CS2_108":  # Execute
        engine.destroy_minion(target_id)
    elif card_id == "VAN_EX1_410":  # Shield Slam
        engine.deal_damage(target_id, sd(p.hero.armor), source_seat=seat, source_name="Shield Slam")
    elif card_id == "VAN_EX1_409":  # Upgrade!
        if p.weapon:
            p.weapon.attack_bonus += 1
            p.weapon.durability += 1
            p.weapon.max_durability += 1
        else:
            engine.equip_weapon(seat, "EX1_409t")
    elif card_id == "VAN_EX1_400":  # Whirlwind
        dmg = sd(1)
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Whirlwind")
    elif card_id == "VAN_EX1_392":  # Battle Rage
        count = 1 if p.hero.hp < p.hero.max_hp else 0
        count += sum(1 for m in p.board if m.damaged)
        for _ in range(count):
            engine.draw_card(seat)
    elif card_id == "VAN_CS2_114":  # Cleave
        targets = engine.rng.sample(list(opp.board), min(2, len(opp.board)))
        dmg = sd(2)
        for m in targets:
            engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Cleave")
    elif card_id == "VAN_NEW1_036":  # Commanding Shout
        p.commanding_shout_active = True
        engine.draw_card(seat)
    elif card_id == "VAN_CS2_105":  # Heroic Strike
        p.hero.temp_attack += 4
    elif card_id == "VAN_CS2_104":  # Rampage
        engine.add_enchantment(target_id, card_id, "Rampage", atk=3, hp=3)
    elif card_id == "VAN_EX1_391":  # Slam
        m = engine.find_minion(target_id)
        if m:
            engine.deal_damage(m.uid, sd(2), source_seat=seat, source_name="Slam")
            if m.health > 0:
                engine.draw_card(seat)
    elif card_id == "VAN_CS2_103":  # Charge
        engine.add_enchantment(target_id, card_id, "Charge", atk=2, add_keywords={"CHARGE"})
    elif card_id == "VAN_EX1_606":  # Shield Block
        p.hero.armor += 5
        engine.draw_card(seat)
    elif card_id == "VAN_EX1_408":  # Mortal Strike
        base = 6 if p.hero.hp <= 12 else 4
        engine.deal_damage(target_id, sd(base), source_seat=seat, source_name="Mortal Strike")
    elif card_id == "VAN_EX1_407":  # Brawl
        all_m = list(p.board) + list(opp.board)
        if len(all_m) > 1:
            survivor = engine.rng.choice(all_m)
            for m in all_m:
                if m.uid != survivor.uid:
                    engine.destroy_minion(m.uid)

    # --- GOLDEN ERA SPELLS & SPARE PARTS ---
    elif card_id == "PART_001":  # Armor Plating
        engine.add_enchantment(target_id, card_id, "Armor Plating", hp=1)
    elif card_id == "PART_002":  # Time Rewinder
        m = engine.find_minion(target_id)
        if m:
            engine.bounce_minion(m)
    elif card_id == "PART_003":  # Rusty Horn
        engine.add_enchantment(target_id, card_id, "Rusty Horn", add_keywords={"TAUNT"})
    elif card_id == "PART_004":  # Finicky Cloakfield
        m = engine.find_minion(target_id)
        if m:
            engine.add_enchantment(m.uid, card_id, "Finicky Cloakfield", add_keywords={"STEALTH"})
            m.stealth_until_sot_of = seat
    elif card_id == "PART_005":  # Emergency Coolant
        engine.freeze_character(target_id)
    elif card_id == "PART_006":  # Reversing Switch
        m = engine.find_minion(target_id)
        if m:
            old_atk, old_hp = m.attack, m.health
            engine.add_enchantment(m.uid, card_id, "Reversing Switch", set_atk=old_hp, set_hp=old_atk)
            m.damage = 0
            if old_atk <= 0:
                engine.destroy_minion(m.uid)
    elif card_id == "PART_007":  # Whirling Blades
        engine.add_enchantment(target_id, card_id, "Whirling Blades", atk=1)
    elif card_id == "GVG_015":  # Darkbomb
        engine.deal_damage(target_id, sd(3), source_seat=seat, source_name="Darkbomb")
    elif card_id == "GVG_045":  # Imp-losion
        base = engine.rng.randint(2, 4)
        dealt = engine.deal_damage(target_id, sd(base), source_seat=seat, source_name="Imp-losion")
        for _ in range(dealt):
            engine.summon_minion(seat, "BRM_006t")
    elif card_id == "AT_037":  # Living Roots
        both = engine.has_fandral(seat)
        if (both or choose == 0) and target_id:
            engine.deal_damage(target_id, sd(2), source_seat=seat, source_name="Living Roots")
        if both or choose == 1:
            for _ in range(2):
                engine.summon_minion(seat, "AT_037t")
    elif card_id == "OG_047":  # Feral Rage
        both = engine.has_fandral(seat)
        if both or choose == 0:
            p.hero.temp_attack += 4
        if both or choose == 1:
            p.hero.armor += 8
    elif card_id == "CFM_602":  # Jade Idol
        both = engine.has_fandral(seat)
        if both or choose == 0:
            engine.summon_jade_golem(seat)
        if both or choose == 1:
            engine.shuffle_into_deck(seat, "CFM_602", count=3)
    elif card_id == "CFM_713":  # Jade Blossom
        engine.summon_jade_golem(seat)
        if p.max_mana < 10:
            p.max_mana = min(10, p.max_mana + 1)
    elif card_id == "BRM_013":  # Quick Shot
        engine.deal_damage(target_id, sd(3), source_seat=seat, source_name="Quick Shot")
        if len(p.hand) == 0:
            engine.draw_card(seat)
    elif card_id == "OG_211":  # Call of the Wild
        for comp_id in ANIMAL_COMPANIONS:
            engine.summon_minion(seat, comp_id)
    elif card_id == "GVG_003":  # Unstable Portal
        from engine.catalog import COLLECTIBLE_CARDS
        minions = [c.id for c in COLLECTIBLE_CARDS.values() if c.type == "MINION"]
        if minions:
            engine.add_card_to_hand(seat, engine.rng.choice(minions), cost_mod=-3)
    elif card_id == "AT_004":  # Arcane Blast (double bonus from Spell Damage)
        sd_bonus = sum(m.spell_damage for m in p.board)
        velen = engine.velen_multiplier(seat)
        dmg = (2 + 2 * sd_bonus) * velen
        engine.deal_damage(target_id, dmg, source_seat=seat, source_name="Arcane Blast")
    elif card_id == "KAR_076":  # Firelands Portal
        engine.deal_damage(target_id, sd(5), source_seat=seat, source_name="Firelands Portal")
        from engine.catalog import COLLECTIBLE_CARDS
        five_drops = [c.id for c in COLLECTIBLE_CARDS.values() if c.type == "MINION" and c.cost == 5]
        if five_drops:
            engine.summon_minion(seat, engine.rng.choice(five_drops))
    elif card_id == "BRM_015":  # Revenge
        base = 3 if p.hero.hp <= 12 else 1
        dmg = sd(base)
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Revenge")
    elif card_id == "AT_064":  # Bash
        engine.deal_damage(target_id, sd(3), source_seat=seat, source_name="Bash")
        p.hero.armor += 3
    elif card_id == "BRM_007":  # Gang Up
        m = engine.find_minion(target_id)
        if m:
            engine.shuffle_into_deck(seat, m.card_id, count=3)
    elif card_id == "GVG_061":  # Muster for Battle
        for _ in range(3):
            engine.summon_minion(seat, "VAN_CS2_101t")
        engine.equip_weapon(seat, "VAN_CS2_091")
    elif card_id == "BRM_001":  # Solemn Vigil
        engine.draw_card(seat)
        engine.draw_card(seat)
    elif card_id == "LOE_026":  # Anyfin Can Happen
        dead = list(engine.state.dead_murlocs)
        if dead:
            engine.rng.shuffle(dead)
            for mid in dead[:7]:
                if len(p.board) >= 7:
                    break
                engine.summon_minion(seat, mid)
    elif card_id == "GVG_008":  # Lightbomb
        sd_bonus = sum(m.spell_damage for m in p.board)
        velen = engine.velen_multiplier(seat)
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                dmg = (m.attack + sd_bonus) * velen
                if dmg > 0:
                    engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Lightbomb")
    elif card_id == "GVG_010":  # Velen's Chosen
        engine.add_enchantment(target_id, card_id, "Velen's Chosen", atk=2, hp=4, spell_damage=1)
    elif card_id == "LOE_104":  # Entomb
        m = engine.find_minion(target_id)
        if m:
            cid_copy = m.card_id
            engine.remove_minion(m)
            engine.shuffle_into_deck(seat, cid_copy, count=1)
    elif card_id == "GVG_038":  # Crackle
        base = engine.rng.randint(3, 6)
        engine.deal_damage(target_id, sd(base), source_seat=seat, source_name="Crackle")
    elif card_id == "BRM_011":  # Lava Shock
        engine.deal_damage(target_id, sd(2), source_seat=seat, source_name="Lava Shock")
        unlocked = p.overloaded
        p.overloaded = 0
        p.pending_overload = 0
        if unlocked > 0:
            p.mana = min(p.max_mana, p.mana + unlocked)
    elif card_id == "KAR_073":  # Maelstrom Portal
        dmg = sd(1)
        for m in list(opp.board):
            engine.deal_damage(m.uid, dmg, source_seat=seat, source_name="Maelstrom Portal")
        from engine.catalog import COLLECTIBLE_CARDS
        one_drops = [c.id for c in COLLECTIBLE_CARDS.values() if c.type == "MINION" and c.cost == 1]
        if one_drops:
            engine.summon_minion(seat, engine.rng.choice(one_drops))


# ---------------------------------------------------------------------------
# BATTLECRY / COMBO / CHOOSE ONE HANDLERS ON MINIONS & WEAPONS
# ---------------------------------------------------------------------------

def trigger_battlecry(
    engine: GameEngine,
    seat: str,
    card_id: str,
    minion: Optional[Minion],
    target_id: Optional[str],
    choose: Optional[int],
    was_combo: bool,
) -> None:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    opp = engine.state.players[opp_seat]

    # --- Choose One Minions ---
    if card_id == "VAN_EX1_166":  # Keeper of the Grove
        both = engine.has_fandral(seat)
        if (both or choose == 0) and target_id:
            engine.deal_damage(target_id, 2, source_seat=seat, source_name="Keeper of the Grove", source_minion=minion)
        if (both or choose == 1) and target_id and not target_id.startswith("hero_"):
            engine.silence_minion(target_id)
    elif card_id == "VAN_EX1_165":  # Druid of the Claw
        if minion is not None:
            if engine.has_fandral(seat):
                engine.add_enchantment(minion.uid, card_id, "Druid of the Claw", hp=2, add_keywords={"CHARGE", "TAUNT"})
            else:
                _choose_druid_of_claw(engine, seat, minion, choose or 0)
    elif card_id == "VAN_NEW1_008":  # Ancient of Lore
        both = engine.has_fandral(seat)
        if both or choose == 0:
            engine.draw_card(seat)
            engine.draw_card(seat)
        if (both or choose == 1) and target_id:
            engine.apply_heal(seat, target_id, 5, from_spell_or_power=False)
    elif card_id == "VAN_EX1_178":  # Ancient of War
        if minion:
            both = engine.has_fandral(seat)
            if both:
                engine.add_enchantment(minion.uid, card_id, "Ancient of War", atk=5, hp=5, add_keywords={"TAUNT"})
            elif choose == 0:
                engine.add_enchantment(minion.uid, card_id, "Uproot", atk=5)
            else:
                engine.add_enchantment(minion.uid, card_id, "Rooted", hp=5, add_keywords={"TAUNT"})
    elif card_id == "VAN_EX1_573":  # Cenarius
        both = engine.has_fandral(seat)
        if both or choose == 1:
            for _ in range(2):
                engine.summon_minion(seat, "EX1_573t")
        if both or choose == 0:
            for m in list(p.board):
                if minion and m.uid != minion.uid:
                    engine.add_enchantment(m.uid, card_id, "Demigod's Favor", atk=2, hp=2)

    # --- Class Battlecry / Combo Minions & Weapons ---
    elif card_id == "VAN_DS1_070" and target_id:  # Houndmaster
        engine.add_enchantment(target_id, card_id, "Houndmaster", atk=2, hp=2, add_keywords={"TAUNT"})
    elif card_id == "VAN_EX1_612":  # Kirin Tor Mage
        p.next_secret_free = True
    elif card_id == "VAN_EX1_362" and target_id:  # Argent Protector
        engine.add_enchantment(target_id, card_id, "Argent Protector", add_keywords={"DIVINE_SHIELD"})
    elif card_id == "VAN_EX1_382" and target_id:  # Aldor Peacekeeper
        engine.add_enchantment(target_id, card_id, "Aldor Peacekeeper", set_atk=1)
    elif card_id == "VAN_CS2_088":  # Guardian of Kings
        engine.apply_heal(seat, f"hero_{seat}", 6)
    elif card_id == "VAN_EX1_091" and target_id:  # Cabal Shadow Priest
        if len(p.board) < 7:
            engine.steal_minion(target_id, seat)
    elif card_id == "VAN_EX1_623" and target_id:  # Temple Enforcer
        engine.add_enchantment(target_id, card_id, "Temple Enforcer", hp=3)
    elif card_id == "VAN_EX1_131" and was_combo:  # Defias Ringleader
        idx = p.board.index(minion) + 1 if minion in p.board else None
        engine.summon_minion(seat, "EX1_131t", pos=idx)
    elif card_id == "VAN_EX1_613" and was_combo and minion:  # Edwin VanCleef
        prior = max(0, p.cards_played_this_turn - 1)
        if prior > 0:
            engine.add_enchantment(minion.uid, card_id, "Edwin VanCleef", atk=2 * prior, hp=2 * prior)
    elif card_id == "VAN_EX1_133" and target_id:  # Perdition's Blade (Weapon Battlecry + Combo)
        dmg = 2 if was_combo else 1
        engine.deal_damage(target_id, dmg, source_seat=seat, source_name="Perdition's Blade")
    elif card_id == "VAN_EX1_134" and was_combo and target_id:  # SI:7 Agent
        engine.deal_damage(target_id, 2, source_seat=seat, source_name="SI:7 Agent", source_minion=minion)
    elif card_id == "VAN_NEW1_014" and target_id:  # Master of Disguise
        engine.add_enchantment(target_id, card_id, "Master of Disguise", add_keywords={"STEALTH"})
    elif card_id == "VAN_NEW1_005" and was_combo and target_id:  # Kidnapper
        m = engine.find_minion(target_id)
        if m:
            engine.bounce_minion(m)
    elif card_id == "VAN_EX1_587" and target_id:  # Windspeaker
        engine.add_enchantment(target_id, card_id, "Windspeaker", add_keywords={"WINDFURY"})
    elif card_id == "VAN_CS2_042" and target_id:  # Fire Elemental
        engine.deal_damage(target_id, 3, source_seat=seat, source_name="Fire Elemental", source_minion=minion)
    elif card_id == "VAN_EX1_319":  # Flame Imp
        engine.deal_damage(f"hero_{seat}", 3, source_seat=seat, source_name="Flame Imp", source_minion=minion)
    elif card_id == "VAN_EX1_306":  # Felstalker
        engine.discard_random(seat)
    elif card_id == "VAN_EX1_301":  # Felguard
        if p.max_mana > 0:
            p.max_mana -= 1
            p.mana = min(p.mana, p.max_mana)
    elif card_id == "VAN_EX1_304" and minion:  # Void Terror
        idx = p.board.index(minion) if minion in p.board else -1
        if idx >= 0:
            neighbors = []
            if idx - 1 >= 0:
                neighbors.append(p.board[idx - 1])
            if idx + 1 < len(p.board):
                neighbors.append(p.board[idx + 1])
            atk_gain = sum(max(0, n.attack) for n in neighbors)
            hp_gain = sum(max(0, n.health) for n in neighbors)
            for n in neighbors:
                engine.destroy_minion(n.uid)
            if atk_gain or hp_gain:
                engine.add_enchantment(minion.uid, card_id, "Void Terror", atk=atk_gain, hp=hp_gain)
    elif card_id == "VAN_EX1_313":  # Pit Lord
        engine.deal_damage(f"hero_{seat}", 5, source_seat=seat, source_name="Pit Lord", source_minion=minion)
    elif card_id == "VAN_EX1_310":  # Doomguard
        engine.discard_random(seat)
        engine.discard_random(seat)
    elif card_id == "VAN_CS2_064":  # Dread Infernal
        for tid in ["hero_p1", "hero_p2"] + [
            m.uid for s in ("p1", "p2") for m in engine.state.players[s].board if not minion or m.uid != minion.uid
        ]:
            engine.deal_damage(tid, 1, source_seat=seat, source_name="Dread Infernal", source_minion=minion)
    elif card_id == "VAN_EX1_323":  # Lord Jaraxxus
        if minion and minion in p.board:
            engine.remove_minion(minion)
        p.hero.name = "Lord Jaraxxus"
        p.hero.hp = 15
        p.hero.max_hp = 15
        p.hero.is_jaraxxus = True
        p.hero.hero_power_id = "VAN_EX1_tk33"
        p.hero.hero_power_used = False
        engine.equip_weapon(seat, "EX1_323w")
    elif card_id == "VAN_EX1_603" and target_id:  # Cruel Taskmaster
        engine.deal_damage(target_id, 1, source_seat=seat, source_name="Cruel Taskmaster", source_minion=minion)
        engine.add_enchantment(target_id, card_id, "Cruel Taskmaster", atk=2)
    elif card_id == "VAN_EX1_398":  # Arathi Weaponsmith
        engine.equip_weapon(seat, "EX1_398t")

    # --- Neutral Battlecry Minions ---
    elif card_id == "VAN_CS2_188" and target_id:  # Abusive Sergeant
        engine.add_enchantment(target_id, card_id, "Abusive Sergeant", atk=2, temp_until_eot=True)
    elif card_id == "VAN_NEW1_025":  # Bloodsail Corsair
        if opp.weapon:
            opp.weapon.durability -= 1
            if opp.weapon.durability <= 0:
                engine.destroy_weapon(opp_seat)
    elif card_id == "VAN_CS2_189" and target_id:  # Elven Archer
        engine.deal_damage(target_id, 1, source_seat=seat, source_name="Elven Archer", source_minion=minion)
    elif card_id == "VAN_NEW1_017" and target_id and minion:  # Hungry Crab
        engine.destroy_minion(target_id)
        engine.add_enchantment(minion.uid, card_id, "Hungry Crab", atk=2, hp=2)
    elif card_id == "VAN_EX1_011" and target_id:  # Voodoo Doctor
        engine.apply_heal(seat, target_id, 2)
    elif card_id == "VAN_EX1_066":  # Acidic Swamp Ooze
        if opp.weapon:
            engine.destroy_weapon(opp_seat)
    elif card_id == "VAN_NEW1_018" and minion:  # Bloodsail Raider
        if p.weapon and p.weapon.total_attack > 0:
            engine.add_enchantment(minion.uid, card_id, "Bloodsail Raider", atk=p.weapon.total_attack)
    elif card_id == "VAN_NEW1_016":  # Captain's Parrot
        from engine.catalog import get_card
        pirates = [i for i, ci in enumerate(p.deck) if get_card(ci.card_id).race == "PIRATE"]
        if pirates:
            ci = p.deck.pop(engine.rng.choice(pirates))
            engine.give_card_instance_to_hand(seat, ci)
    elif card_id == "VAN_EX1_059" and target_id:  # Crazed Alchemist
        m = engine.find_minion(target_id)
        if m:
            cur_atk = max(0, m.attack)
            cur_hp = max(0, m.health)
            engine.add_enchantment(m.uid, card_id, "Crazed Alchemist", set_atk=cur_hp, set_hp=cur_atk)
    elif card_id == "VAN_CS2_203" and target_id:  # Ironbeak Owl
        engine.silence_minion(target_id)
    elif card_id == "VAN_EX1_082":  # Mad Bomber
        for _ in range(3):
            cands = ["hero_p1", "hero_p2"] + [
                m.uid for s in ("p1", "p2") for m in engine.state.players[s].board if not minion or m.uid != minion.uid
            ]
            if not cands:
                break
            t = engine.rng.choice(cands)
            engine.deal_damage(t, 1, source_seat=seat, source_name="Mad Bomber", source_minion=minion)
            engine.resolve_deaths()
    elif card_id == "VAN_NEW1_029":  # Millhouse Manastorm
        opp.enemy_spells_free_next_turn = True
    elif card_id == "VAN_EX1_506":  # Murloc Tidehunter
        idx = p.board.index(minion) + 1 if minion in p.board else None
        engine.summon_minion(seat, "VAN_EX1_506a", pos=idx)
    elif card_id == "VAN_EX1_015":  # Novice Engineer
        engine.draw_card(seat)
    elif card_id == "VAN_EX1_058" and minion:  # Sunfury Protector
        idx = p.board.index(minion) if minion in p.board else -1
        if idx >= 0:
            for ni in (idx - 1, idx + 1):
                if 0 <= ni < len(p.board):
                    engine.add_enchantment(p.board[ni].uid, card_id, "Sunfury Protector", add_keywords={"TAUNT"})
    elif card_id == "VAN_EX1_049" and target_id:  # Youthful Brewmaster
        m = engine.find_minion(target_id)
        if m:
            engine.bounce_minion(m)
    elif card_id == "VAN_EX1_089":  # Arcane Golem
        opp.max_mana = min(10, opp.max_mana + 1)
        opp.mana = min(10, opp.mana + 1)
    elif card_id == "VAN_EX1_005" and target_id:  # Big Game Hunter
        engine.destroy_minion(target_id)
    elif card_id == "VAN_EX1_590" and minion:  # Blood Knight
        popped = 0
        for s in ("p1", "p2"):
            for m in engine.state.players[s].board:
                if m.has_keyword("DIVINE_SHIELD"):
                    engine.strip_divine_shield(m)
                    popped += 1
        if popped > 0:
            engine.add_enchantment(minion.uid, card_id, "Blood Knight", atk=3 * popped, hp=3 * popped)
    elif card_id == "VAN_EX1_050":  # Coldlight Oracle
        for _ in range(2):
            engine.draw_card(seat)
        for _ in range(2):
            engine.draw_card(opp_seat)
    elif card_id == "VAN_EX1_103":  # Coldlight Seer
        for s in ("p1", "p2"):
            for m in engine.state.players[s].board:
                if (not minion or m.uid != minion.uid) and m.race == "MURLOC":
                    engine.add_enchantment(m.uid, card_id, "Coldlight Seer", hp=2)
    elif card_id == "VAN_CS2_117" and target_id:  # Earthen Ring Farseer
        engine.apply_heal(seat, target_id, 3)
    elif card_id == "VAN_CS2_181" and minion:  # Injured Blademaster
        engine.deal_damage(minion.uid, 4, source_seat=seat, source_name="Injured Blademaster", source_minion=minion)
    elif card_id == "VAN_CS2_141" and target_id:  # Ironforge Rifleman
        engine.deal_damage(target_id, 1, source_seat=seat, source_name="Ironforge Rifleman", source_minion=minion)
    elif card_id == "VAN_EX1_014":  # King Mukla
        engine.add_card_to_hand(opp_seat, "EX1_014t")
        engine.add_card_to_hand(opp_seat, "EX1_014t")
    elif card_id == "VAN_EX1_085":  # Mind Control Tech
        if len(opp.board) >= 4 and len(p.board) < 7:
            stolen = engine.rng.choice(opp.board)
            engine.steal_minion(stolen.uid, seat)
    elif card_id == "VAN_CS2_196":  # Razorfen Hunter
        idx = p.board.index(minion) + 1 if minion in p.board else None
        engine.summon_minion(seat, "VAN_CS2_boar", pos=idx)
    elif card_id == "VAN_EX1_019" and target_id:  # Shattered Sun Cleric
        engine.add_enchantment(target_id, card_id, "Shattered Sun Cleric", atk=1, hp=1)
    elif card_id == "VAN_EX1_083":  # Tinkmaster Overspark
        others = [m for s in ("p1", "p2") for m in engine.state.players[s].board if not minion or m.uid != minion.uid]
        if others:
            chosen = engine.rng.choice(others)
            form = engine.rng.choice(["VAN_EX1_tk28", "VAN_EX1_tk29"])
            engine.transform_minion(chosen.uid, form)
    elif card_id == "VAN_EX1_057" and target_id:  # Ancient Brewmaster
        m = engine.find_minion(target_id)
        if m:
            engine.bounce_minion(m)
    elif card_id == "VAN_EX1_584" and minion:  # Ancient Mage
        idx = p.board.index(minion) if minion in p.board else -1
        if idx >= 0:
            for ni in (idx - 1, idx + 1):
                if 0 <= ni < len(p.board):
                    engine.add_enchantment(p.board[ni].uid, card_id, "Ancient Mage", spell_damage=1)
    elif card_id == "VAN_EX1_046" and target_id:  # Dark Iron Dwarf
        engine.add_enchantment(target_id, card_id, "Dark Iron Dwarf", atk=2, temp_until_eot=True)
    elif card_id == "VAN_EX1_093" and minion:  # Defender of Argus
        idx = p.board.index(minion) if minion in p.board else -1
        if idx >= 0:
            for ni in (idx - 1, idx + 1):
                if 0 <= ni < len(p.board):
                    engine.add_enchantment(p.board[ni].uid, card_id, "Defender of Argus", atk=1, hp=1, add_keywords={"TAUNT"})
    elif card_id == "VAN_EX1_025":  # Dragonling Mechanic
        idx = p.board.index(minion) + 1 if minion in p.board else None
        engine.summon_minion(seat, "EX1_025t", pos=idx)
    elif card_id == "VAN_CS2_147":  # Gnomish Inventor
        engine.draw_card(seat)
    elif card_id == "VAN_EX1_116":  # Leeroy Jenkins
        for _ in range(2):
            engine.summon_minion(opp_seat, "EX1_116t")
    elif card_id == "VAN_EX1_048" and target_id:  # Spellbreaker
        engine.silence_minion(target_id)
    elif card_id == "VAN_EX1_043" and minion:  # Twilight Drake
        extra = len(p.hand)
        if extra > 0:
            engine.add_enchantment(minion.uid, card_id, "Twilight Drake", hp=extra)
    elif card_id == "VAN_EX1_284":  # Azure Drake
        engine.draw_card(seat)
    elif card_id == "VAN_NEW1_024":  # Captain Greenskin
        if p.weapon:
            p.weapon.attack_bonus += 1
            p.weapon.durability += 1
            p.weapon.max_durability += 1
    elif card_id == "VAN_DS1_055":  # Darkscale Healer
        for tid in [f"hero_{seat}"] + [m.uid for m in p.board]:
            engine.apply_heal(seat, tid, 2)
    elif card_id == "VAN_PRO_001":  # Elite Tauren Chieftain
        engine.add_card_to_hand(seat, engine.rng.choice(ETC_POWER_CHORDS))
        engine.add_card_to_hand(opp_seat, engine.rng.choice(ETC_POWER_CHORDS))
    elif card_id == "VAN_EX1_564" and target_id and minion:  # Faceless Manipulator
        src = engine.find_minion(target_id)
        if src:
            engine.copy_minion_into(src, minion)
    elif card_id == "VAN_CS2_226" and minion:  # Frostwolf Warlord
        others = sum(1 for m in p.board if m.uid != minion.uid)
        if others > 0:
            engine.add_enchantment(minion.uid, card_id, "Frostwolf Warlord", atk=others, hp=others)
    elif card_id == "VAN_EX1_558":  # Harrison Jones
        if opp.weapon:
            dur = opp.weapon.durability
            engine.destroy_weapon(opp_seat)
            for _ in range(dur):
                engine.draw_card(seat)
    elif card_id == "VAN_EX1_593":  # Nightblade
        engine.deal_damage(f"hero_{opp_seat}", 3, source_seat=seat, source_name="Nightblade", source_minion=minion)
    elif card_id == "VAN_CS2_151":  # Silver Hand Knight
        idx = p.board.index(minion) + 1 if minion in p.board else None
        engine.summon_minion(seat, "VAN_CS2_152", pos=idx)
    elif card_id == "VAN_NEW1_041":  # Stampeding Kodo
        cands = [m for m in opp.board if m.attack <= 2]
        if cands:
            engine.destroy_minion(engine.rng.choice(cands).uid)
    elif card_id == "VAN_CS2_150" and target_id:  # Stormpike Commando
        engine.deal_damage(target_id, 2, source_seat=seat, source_name="Stormpike Commando", source_minion=minion)
    elif card_id == "VAN_EX1_283" and target_id:  # Frost Elemental
        engine.freeze_character(target_id)
    elif card_id == "VAN_EX1_112":  # Gelbin Mekkatorque
        idx = p.board.index(minion) + 1 if minion in p.board else None
        engine.summon_minion(seat, engine.rng.choice(GELBIN_INVENTIONS), pos=idx)
    elif card_id == "VAN_EX1_583":  # Priestess of Elune
        engine.apply_heal(seat, f"hero_{seat}", 4)
    elif card_id == "VAN_EX1_002" and target_id:  # The Black Knight
        engine.destroy_minion(target_id)
    elif card_id == "VAN_EX1_561" and target_id:  # Alexstrasza
        tseat = target_id.split("_")[1]
        engine.state.players[tseat].hero.hp = 15
    elif card_id == "VAN_EX1_562":  # Onyxia
        while len(p.board) < 7:
            engine.summon_minion(seat, "EX1_116t")
    elif card_id == "VAN_NEW1_030":  # Deathwing
        for s in ("p1", "p2"):
            for m in list(engine.state.players[s].board):
                if not minion or m.uid != minion.uid:
                    engine.destroy_minion(m.uid)
        engine.discard_hand(seat)

    elif card_id == "LF_004" and minion and target_id:  # Graveglass Mimic
        target = engine.find_minion(target_id)
        if target and target.card_id in DEATHRATTLE_CARDS and not target.silenced:
            engine.add_enchantment(
                minion.uid, card_id, target.name, add_keywords={"DEATHRATTLE"},
                extra_deathrattle=f"COPY:{target.card_id}",
            )
    elif card_id == "LF_007":  # Banner Captain
        for recruit in p.board:
            if recruit.card_id == "VAN_CS2_101t":
                engine.add_enchantment(recruit.uid, card_id, "Banner Captain", atk=1, hp=2)
    # --- GOLDEN ERA BATTLECRIES ---
    elif card_id == "FP1_030":  # Loatheb
        opp.enemy_spell_cost_mod_next_turn += 5
    elif card_id == "GVG_069":  # Antique Healbot
        engine.apply_heal(seat, f"hero_{seat}", 8)
    elif card_id == "GVG_110":  # Dr. Boom
        if minion and minion in p.board:
            idx = p.board.index(minion)
            engine.summon_minion(seat, "GVG_110t", pos=idx)
            idx2 = p.board.index(minion) + 1 if minion in p.board else None
            engine.summon_minion(seat, "GVG_110t", pos=idx2)
        else:
            for _ in range(2):
                engine.summon_minion(seat, "GVG_110t")
    elif card_id == "BRM_033" and minion:  # Blackwing Technician
        if engine.has_dragon_in_hand(seat):
            engine.add_enchantment(minion.uid, card_id, "Blackwing Technician", atk=1, hp=1)
    elif card_id == "BRM_034" and target_id:  # Blackwing Corruptor
        if engine.has_dragon_in_hand(seat):
            engine.deal_damage(target_id, 3, source_seat=seat, source_name="Blackwing Corruptor", source_minion=minion)
    elif card_id == "AT_017" and minion:  # Twilight Guardian
        if engine.has_dragon_in_hand(seat):
            engine.add_enchantment(minion.uid, card_id, "Twilight Guardian", atk=1, add_keywords={"TAUNT"})
    elif card_id == "AT_111":  # Refreshment Vendor
        engine.apply_heal(seat, f"hero_{seat}", 4)
        engine.apply_heal(seat, f"hero_{opp_seat}", 4)
    elif card_id == "AT_132":  # Justicar Trueheart
        upgraded = UPGRADED_HERO_POWERS.get(p.hero.hero_power_id)
        if upgraded:
            p.hero.hero_power_id = upgraded
            p.hero.hero_power_used = False
            engine.add_log(f"{p.name}'s Hero Power is upgraded!", seat=seat)
    elif card_id == "LOE_011":  # Reno Jackson
        if engine.has_no_duplicates_in_deck(seat):
            engine.apply_heal(seat, f"hero_{seat}", p.hero.max_hp)
    elif card_id == "LOE_076":  # Sir Finley Mrrgglton
        pool = [hp for hp in BASIC_HERO_POWERS if hp != p.hero.hero_power_id]
        engine.start_discover(seat, card_id, pool, choice_type="DISCOVER_HERO_POWER")
    elif card_id == "CFM_715":  # Jade Spirit
        idx = p.board.index(minion) + 1 if minion and minion in p.board else None
        engine.summon_jade_golem(seat, pos=idx)
    elif card_id == "CFM_902":  # Aya Blackpaw
        idx = p.board.index(minion) + 1 if minion and minion in p.board else None
        engine.summon_jade_golem(seat, pos=idx)
    elif card_id == "LOE_023":  # Dark Peddler
        from engine.catalog import COLLECTIBLE_CARDS
        pool = [
            c.id for c in COLLECTIBLE_CARDS.values()
            if c.cost == 1 and c.card_class in (p.hero.card_class, "NEUTRAL")
        ]
        engine.start_discover(seat, card_id, pool, choice_type="DISCOVER")
    elif card_id == "AT_038":  # Darnassus Aspirant
        if p.max_mana < 10:
            p.max_mana = min(10, p.max_mana + 1)
    elif card_id == "CFM_343":  # Jade Behemoth
        idx = p.board.index(minion) + 1 if minion and minion in p.board else None
        engine.summon_jade_golem(seat, pos=idx)
    elif card_id == "GVG_004":  # Goblin Blastmage
        if engine.has_mech_on_board(seat):
            for _ in range(4):
                cands = engine.living_enemy_characters(seat)
                if not cands:
                    break
                engine.deal_damage(engine.rng.choice(cands), 1, source_seat=seat, source_name="Goblin Blastmage", source_minion=minion)
    elif card_id == "GVG_053":  # Shieldmaiden
        p.hero.armor += 5
    elif card_id == "OG_276":  # Ravaging Ghoul
        for s in ("p1", "p2"):
            for bm in list(engine.state.players[s].board):
                if not minion or bm.uid != minion.uid:
                    engine.deal_damage(bm.uid, 1, source_seat=seat, source_name="Ravaging Ghoul", source_minion=minion)
    elif card_id == "LOE_017" and target_id:  # Keeper of Uldaman
        m = engine.find_minion(target_id)
        if m:
            engine.add_enchantment(m.uid, card_id, "Keeper of Uldaman", set_atk=3, set_hp=3)
            m.damage = 0
    elif card_id == "BRM_004" and minion:  # Twilight Whelp
        if engine.has_dragon_in_hand(seat):
            engine.add_enchantment(minion.uid, card_id, "Twilight Whelp", hp=2)
    elif card_id == "AT_116" and minion:  # Wyrmrest Agent
        if engine.has_dragon_in_hand(seat):
            engine.add_enchantment(minion.uid, card_id, "Wyrmrest Agent", atk=1, add_keywords={"TAUNT"})
    elif card_id == "CFM_605":  # Drakonid Operative
        if engine.has_dragon_in_hand(seat) and opp.deck:
            seen: set[str] = set()
            pool = []
            for ci in opp.deck:
                if ci.card_id not in seen:
                    seen.add(ci.card_id)
                    pool.append(ci.card_id)
            engine.start_discover(seat, card_id, pool, choice_type="DISCOVER")


# ---------------------------------------------------------------------------
# DEATHRATTLES
# ---------------------------------------------------------------------------

def _trigger_printed_deathrattle(engine: GameEngine, seat: str, cid: str, orig_pos: int) -> None:
    from engine.catalog import get_card

    opp_seat = engine.other_seat(seat)
    if cid == "VAN_EX1_534":  # Savannah Highmane
        for _ in range(2):
            engine.summon_minion(seat, "EX1_534t", pos=orig_pos)
    elif cid == "VAN_EX1_383":  # Tirion Fordring
        engine.equip_weapon(seat, "EX1_383t")
    elif cid == "VAN_EX1_029":  # Leper Gnome
        engine.deal_damage(f"hero_{opp_seat}", 2, source_seat=seat, source_name="Leper Gnome")
    elif cid in ("VAN_EX1_012", "VAN_EX1_096"):  # Bloodmage Thalnos / Loot Hoarder
        engine.draw_card(seat)
    elif cid == "VAN_EX1_556":  # Harvest Golem
        engine.summon_minion(seat, "VAN_skele21", pos=orig_pos)
    elif cid == "VAN_EX1_097":  # Abomination
        for tid in ["hero_p1", "hero_p2"] + [
            m.uid for s in ("p1", "p2") for m in engine.state.players[s].board
        ]:
            engine.deal_damage(tid, 2, source_seat=seat, source_name="Abomination")
    elif cid == "VAN_EX1_110":  # Cairne Bloodhoof
        engine.summon_minion(seat, "VAN_EX1_110t", pos=orig_pos)
    elif cid == "VAN_EX1_016":  # Sylvanas Windrunner
        opp = engine.state.players[opp_seat]
        if opp.board and len(engine.state.players[seat].board) < 7:
            stolen = engine.rng.choice(opp.board)
            engine.steal_minion(stolen.uid, seat)
    elif cid == "VAN_EX1_577":  # The Beast
        engine.summon_minion(opp_seat, "VAN_EX1_finkle")
    # --- GOLDEN ERA DEATHRATTLES ---
    elif cid == "FP1_001":  # Zombie Chow
        engine.apply_heal(seat, f"hero_{opp_seat}", 5)
    elif cid == "FP1_002":  # Haunted Creeper
        for _ in range(2):
            engine.summon_minion(seat, "FP1_002t", pos=orig_pos)
    elif cid == "FP1_004":  # Mad Scientist
        p_owner = engine.state.players[seat]
        if len(p_owner.secrets) < 5:
            from engine.models import SecretInstance
            active_ids = {s.card_id for s in p_owner.secrets}
            sec_indices = [
                i for i, ci in enumerate(p_owner.deck)
                if get_card(ci.card_id).has_mechanic("SECRET") and ci.card_id not in active_ids
            ]
            if sec_indices:
                pick_i = engine.rng.choice(sec_indices)
                sec_ci = p_owner.deck.pop(pick_i)
                scard = get_card(sec_ci.card_id)
                sec_inst = SecretInstance(
                    uid=engine._new_uid("sec"),
                    card_id=scard.id,
                    card_class=scard.card_class,
                    name=scard.name,
                )
                p_owner.secrets.append(sec_inst)
                engine.emit("secret_add", seat=seat, uid=sec_inst.uid, card_class=scard.card_class)
                engine.add_log(f"Mad Scientist put a Secret into play for {p_owner.name}.", seat=seat)
    elif cid == "FP1_009":  # Deathlord
        opp = engine.state.players[opp_seat]
        if len(opp.board) < 7:
            min_indices = [i for i, ci in enumerate(opp.deck) if get_card(ci.card_id).type == "MINION"]
            if min_indices:
                pick_i = engine.rng.choice(min_indices)
                m_ci = opp.deck.pop(pick_i)
                engine.summon_minion(opp_seat, m_ci.card_id)
    elif cid == "FP1_012":  # Sludge Belcher
        engine.summon_minion(seat, "FP1_012t", pos=orig_pos)
    elif cid == "GVG_076":  # Explosive Sheep
        for s in ("p1", "p2"):
            for bm in list(engine.state.players[s].board):
                engine.deal_damage(bm.uid, 2, source_seat=seat, source_name="Explosive Sheep")
    elif cid == "GVG_082":  # Clockwork Gnome
        engine.add_card_to_hand(seat, engine.rng.choice(SPARE_PARTS))
    elif cid == "GVG_096":  # Piloted Shredder
        from engine.catalog import COLLECTIBLE_CARDS
        two_drops = [c.id for c in COLLECTIBLE_CARDS.values() if c.type == "MINION" and c.cost == 2]
        if two_drops:
            engine.summon_minion(seat, engine.rng.choice(two_drops), pos=orig_pos)
    elif cid == "GVG_110t":  # Boom Bot
        cands = engine.living_enemy_characters(seat)
        if cands:
            dmg = engine.rng.randint(1, 4)
            engine.deal_damage(engine.rng.choice(cands), dmg, source_seat=seat, source_name="Boom Bot")
    elif cid == "CFM_902":  # Aya Blackpaw
        engine.summon_jade_golem(seat, pos=orig_pos)
    elif cid == "AT_038":  # Darnassus Aspirant
        p_owner = engine.state.players[seat]
        if p_owner.max_mana > 0:
            p_owner.max_mana = max(0, p_owner.max_mana - 1)
            p_owner.mana = min(p_owner.mana, p_owner.max_mana)
    elif cid == "FP1_011":  # Webspinner
        from engine.catalog import COLLECTIBLE_CARDS
        beasts = [c.id for c in COLLECTIBLE_CARDS.values() if c.type == "MINION" and c.race == "BEAST"]
        if beasts:
            engine.add_card_to_hand(seat, engine.rng.choice(beasts))
    elif cid == "KAR_005":  # Kindly Grandmother
        engine.summon_minion(seat, "KAR_005a", pos=orig_pos)
    elif cid == "LOE_012":  # Tomb Pillager
        engine.add_card_to_hand(seat, "GAME_005")
    elif cid == "LF_003":  # Emberglass Cocoon
        engine.summon_minion(seat, "LF_003t", pos=orig_pos)
    elif cid == "LF_005":  # Lanternbound Herald
        candidates = [
            i for i, ci in enumerate(engine.state.players[seat].hand)
            if (card := get_card(ci.card_id)).type == "MINION" and card.race == "DEMON" and card.cost >= 5
        ]
        if candidates:
            engine.summon_minion_from_hand(seat, engine.rng.choice(candidates), orig_pos)


def trigger_deathrattle(engine: GameEngine, dead_minion: Minion, orig_pos: int) -> None:
    seat = dead_minion.owner
    if not dead_minion.silenced:
        _trigger_printed_deathrattle(engine, seat, dead_minion.card_id, orig_pos)

    # Enchantment deathrattles (removed on Silence, so only present if unsilenced!)
    for ench in dead_minion.enchantments:
        if ench.extra_deathrattle == "TREANT":
            engine.summon_minion(seat, "EX1_158t", pos=orig_pos)
        elif ench.extra_deathrattle == "RESUMMON":
            engine.summon_minion(seat, dead_minion.card_id, pos=orig_pos)
        elif ench.extra_deathrattle and ench.extra_deathrattle.startswith("COPY:"):
            _trigger_printed_deathrattle(engine, seat, ench.extra_deathrattle.removeprefix("COPY:"), orig_pos)


def trigger_weapon_deathrattle(engine: GameEngine, seat: str, weapon_card_id: str) -> None:
    if weapon_card_id == "FP1_021":  # Death's Bite
        for s in ("p1", "p2"):
            for bm in list(engine.state.players[s].board):
                engine.deal_damage(bm.uid, 1, source_seat=seat, source_name="Death's Bite")
    elif weapon_card_id == "GVG_036":  # Powermace
        p = engine.state.players[seat]
        mechs = [m for m in p.board if m.race == "MECHANICAL"]
        if mechs:
            engine.add_enchantment(engine.rng.choice(mechs).uid, weapon_card_id, "Powermace", atk=2, hp=2)


# ---------------------------------------------------------------------------
# HERO POWERS
# ---------------------------------------------------------------------------

def trigger_hero_power(engine: GameEngine, seat: str, hp_id: str, target_id: Optional[str]) -> None:
    p = engine.state.players[seat]
    opp_seat = engine.other_seat(seat)
    velen_mult = engine.velen_multiplier(seat)

    if hp_id == "VAN_HERO_01bp":  # Armor Up!
        p.hero.armor += 2
    elif hp_id == "VAN_HERO_02bp":  # Totemic Call
        existing = {m.card_id for m in p.board}
        avail = [t for t in BASIC_TOTEMS if t not in existing]
        if avail:
            engine.summon_minion(seat, engine.rng.choice(avail))
    elif hp_id == "VAN_HERO_03bp":  # Dagger Mastery
        engine.equip_weapon(seat, "VAN_CS2_082")
    elif hp_id == "VAN_HERO_04bp":  # Reinforce
        engine.summon_minion(seat, "VAN_CS2_101t")
    elif hp_id == "VAN_HERO_05bp":  # Steady Shot
        engine.deal_damage(f"hero_{opp_seat}", 2 * velen_mult, source_seat=seat, source_name="Steady Shot")
    elif hp_id == "VAN_HERO_06bp":  # Shapeshift
        p.hero.temp_attack += 1
        p.hero.armor += 1
    elif hp_id == "VAN_HERO_07bp":  # Life Tap
        engine.deal_damage(f"hero_{seat}", 2 * velen_mult, source_seat=seat, source_name="Life Tap")
        engine.draw_card(seat)
    elif hp_id == "VAN_HERO_08bp":  # Fireblast
        if target_id:
            engine.deal_damage(target_id, 1 * velen_mult, source_seat=seat, source_name="Fireblast")
    elif hp_id == "VAN_HERO_09bp":  # Lesser Heal
        if target_id:
            engine.apply_heal(seat, target_id, 2 * velen_mult, from_spell_or_power=True)
    elif hp_id == "EX1_625t":  # Mind Spike (Shadowform 1)
        if target_id:
            engine.deal_damage(target_id, 2 * velen_mult, source_seat=seat, source_name="Mind Spike")
    elif hp_id == "EX1_625t2":  # Mind Shatter (Shadowform 2)
        if target_id:
            engine.deal_damage(target_id, 3 * velen_mult, source_seat=seat, source_name="Mind Shatter")
    elif hp_id == "VAN_EX1_tk33":  # INFERNO! (Jaraxxus)
        engine.summon_minion(seat, "VAN_EX1_tk34")
    # --- Upgraded Hero Powers (Justicar Trueheart) ---
    elif hp_id == "AT_132_WARRIOR":  # Tank Up!
        p.hero.armor += 4
    elif hp_id == "AT_132_SHAMAN":  # Totemic Slam
        if len(p.board) < 7:
            engine.start_discover(seat, hp_id, list(BASIC_TOTEMS), choice_type="TOTEM", count=4)
    elif hp_id == "AT_132_ROGUE":  # Poisoned Daggers
        engine.equip_weapon(seat, "AT_132_ROGUEt")
    elif hp_id == "AT_132_PALADIN":  # The Silver Hand
        for _ in range(2):
            engine.summon_minion(seat, "VAN_CS2_101t")
    elif hp_id == "AT_132_HUNTER":  # Ballista Shot
        engine.deal_damage(f"hero_{opp_seat}", 3 * velen_mult, source_seat=seat, source_name="Ballista Shot")
    elif hp_id == "AT_132_DRUID":  # Dire Shapeshift
        p.hero.temp_attack += 2
        p.hero.armor += 2
    elif hp_id == "AT_132_WARLOCK":  # Soul Tap
        engine.draw_card(seat)
    elif hp_id == "AT_132_MAGE":  # Fireblast Rank 2
        if target_id:
            engine.deal_damage(target_id, 2 * velen_mult, source_seat=seat, source_name="Fireblast Rank 2")
    elif hp_id == "AT_132_PRIEST":  # Heal
        if target_id:
            engine.apply_heal(seat, target_id, 4 * velen_mult, from_spell_or_power=True)
