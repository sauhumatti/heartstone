// The Road to First Light: 5 chapters, 15 unique boss encounters with live boss passives,
// opening boards, signature cards, mid-fight banter, and 5 unlockable Lantern Relics.

export type RelicId = 'none' | 'tinderbox' | 'pendulum' | 'emberheart' | 'satchel' | 'crown';
export type CampaignDifficulty = 'normal' | 'heroic';
export type BossPassiveId =
  | 'iron_guard'
  | 'cinder_bolt'
  | 'shadow_coin'
  | 'scrap_assembly'
  | 'crypt_call'
  | 'silver_oath'
  | 'dragon_breath'
  | 'wild_pack'
  | 'storm_surge'
  | 'hollow_siphon'
  | 'jade_bloom'
  | 'broadside'
  | 'eclipse_aura';

export interface CampaignRelic {
  id: RelicId;
  name: string;
  effect: string;
  shortEffect: string;
  flavor: string;
  /** Chapter id that unlocks this relic when cleared (null = available from the start). */
  unlockChapterId: string | null;
  p1Hp: number;
  p1Armor: number;
  p1BonusMana: number;
  p1BonusCards: number;
}

export interface CampaignBoss {
  id: string;
  chapterId: string;
  order: number; // 1..15
  name: string;
  epithet: string;
  heroClass: string;
  /** Builtin deck id from the card catalog (starter_* or meta_*). */
  deckId: string;
  /** Suggested builtin counter deck for quick 1-click setup. */
  recommendedDeckId: string;
  /** Card id whose artwork represents this boss. */
  portraitCardId: string;
  /** Three iconic cards featured in this boss's deck. */
  signatureCards: string[];
  isChapterBoss?: boolean;
  hp: number;
  armor: number;
  bonusMana?: number;
  level: 'easy' | 'normal' | 'hard';
  heroicHp: number;
  heroicArmor: number;
  heroicBonusMana?: number;
  passiveId: BossPassiveId;
  passiveName: string;
  passivePower: number;
  heroicPassivePower: number;
  passiveText: string;
  heroicPassiveText: string;
  openingBoard?: string[];
  heroicOpeningBoard?: string[];
  openingBoardLabel?: string;
  heroicOpeningBoardLabel?: string;
  introQuote: string;
  midQuote: string;
  defeatQuote: string;
  tip: string;
}

export interface ChapterReward {
  packs: number;
  embers: number;
  relicId: RelicId;
  cosmeticId?: string;
  cosmeticName?: string;
}

export interface CampaignChapter {
  id: string;
  number: number;
  roman: string;
  title: string;
  eraLabel: string;
  subtitle: string;
  lore: string;
  accent: string;
  bosses: CampaignBoss[];
  reward: ChapterReward;
}

export const HEROIC_GRAND_REWARD = {
  packs: 3,
  embers: 250,
} as const;

export const CAMPAIGN_RELICS: CampaignRelic[] = [
  {
    id: 'none',
    name: 'No Relic',
    effect: 'Standard 30 Health duel — pure skill. Earns a ★ Purist medal on victory!',
    shortEffect: 'Pure Duel (earns ★ Purist medal)',
    flavor: 'Just your cards and a steady hand.',
    unlockChapterId: null,
    p1Hp: 30,
    p1Armor: 0,
    p1BonusMana: 0,
    p1BonusCards: 0,
  },
  {
    id: 'tinderbox',
    name: 'Tinderbox Charm',
    effect: 'Start with +5 Armor, and gain +1 Armor whenever you end a turn with unspent Mana.',
    shortEffect: '+5 Armor · +1 Armor on unspent Mana',
    flavor: 'A brass spark-case pulled from the tavern hearth.',
    unlockChapterId: 'ch1',
    p1Hp: 30,
    p1Armor: 5,
    p1BonusMana: 0,
    p1BonusCards: 0,
  },
  {
    id: 'pendulum',
    name: 'Clockwork Pendulum',
    effect: 'Begin Turn 1 with +1 extra Mana Crystal so you seize the board early.',
    shortEffect: '+1 starting Mana Crystal',
    flavor: 'Ticks one beat ahead of the foundry bells.',
    unlockChapterId: 'ch2',
    p1Hp: 30,
    p1Armor: 0,
    p1BonusMana: 1,
    p1BonusCards: 0,
  },
  {
    id: 'emberheart',
    name: 'Emberheart Flask',
    effect: 'Start with 35 Max Health, and restore 2 Health to your hero at the start of each turn.',
    shortEffect: '35 Max HP · Restore 2 HP each turn',
    flavor: 'Warm ash-wine poured only for tournament victors.',
    unlockChapterId: 'ch3',
    p1Hp: 35,
    p1Armor: 0,
    p1BonusMana: 0,
    p1BonusCards: 0,
  },
  {
    id: 'satchel',
    name: 'Starlight Satchel',
    effect: 'Draw +1 extra opening card, and your Hero Power costs (1) Mana.',
    shortEffect: '+1 opening card · Hero Power costs 1',
    flavor: 'Always seems to hold the answer you packed last night.',
    unlockChapterId: 'ch4',
    p1Hp: 30,
    p1Armor: 0,
    p1BonusMana: 0,
    p1BonusCards: 1,
  },
  {
    id: 'crown',
    name: 'Crown of First Light',
    effect: '35 Max Health, +5 Armor, +1 opening card, and give a random friendly minion +1/+1 each turn.',
    shortEffect: '35 HP, +5 Armor, +1 Card · Random minion +1/+1 each turn',
    flavor: 'Forged when the Spire lantern blazed across every harbour.',
    unlockChapterId: 'ch5',
    p1Hp: 35,
    p1Armor: 5,
    p1BonusMana: 0,
    p1BonusCards: 1,
  },
];

export const RELIC_BY_ID: Record<RelicId, CampaignRelic> = Object.fromEntries(
  CAMPAIGN_RELICS.map((r) => [r.id, r]),
) as Record<RelicId, CampaignRelic>;

export const CAMPAIGN_CHAPTERS: CampaignChapter[] = [
  {
    id: 'ch1',
    number: 1,
    roman: 'I',
    title: 'The Dimming Tavern',
    eraLabel: 'Classic Era',
    subtitle: 'Prove your nerve at the hearthside tables',
    lore: 'The harbour lanterns have begun to sputter. Before anyone will grant you passage to the Spire, you must clear the tables of the old inn.',
    accent: '#e8a849',
    reward: {
      packs: 1,
      embers: 50,
      relicId: 'tinderbox',
    },
    bosses: [
      {
        id: 'ch1_bouncer',
        chapterId: 'ch1',
        order: 1,
        name: 'Bram the Bouncer',
        epithet: 'Keeper of the Oak Door',
        heroClass: 'WARRIOR',
        deckId: 'starter_warrior',
        recommendedDeckId: 'starter_mage',
        portraitCardId: 'VAN_EX1_414',
        signatureCards: ['VAN_EX1_414', 'VAN_EX1_298', 'VAN_EX1_110'],
        hp: 25,
        armor: 0,
        level: 'easy',
        heroicHp: 35,
        heroicArmor: 5,
        passiveId: 'iron_guard',
        passiveName: 'Tavern Plate',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'At the end of his turn, gains +1 Armor.',
        heroicPassiveText: 'At the end of his turn, gains +2 Armor.',
        heroicOpeningBoard: ['VAN_EX1_402'],
        heroicOpeningBoardLabel: 'Starts with an Armorsmith (1/4)',
        introQuote: 'No seat by the fire until you can take a swing and stay upright.',
        midQuote: 'Hmph—alright, you actually hit harder than you look!',
        defeatQuote: 'Hah! Alright, alright—the hearth table is yours.',
        tip: 'Bram relies on weapons and Execute. Keep minions healthy and punish slow Armor turns.',
      },
      {
        id: 'ch1_hearthwitch',
        chapterId: 'ch1',
        order: 2,
        name: 'Hearthwitch Maren',
        epithet: 'Mistress of Cinder & Frost',
        heroClass: 'MAGE',
        deckId: 'starter_mage',
        recommendedDeckId: 'starter_hunter',
        portraitCardId: 'VAN_EX1_559',
        signatureCards: ['VAN_EX1_559', 'VAN_EX1_279', 'VAN_EX1_284'],
        hp: 28,
        armor: 0,
        level: 'easy',
        heroicHp: 38,
        heroicArmor: 5,
        passiveId: 'cinder_bolt',
        passiveName: 'Hearth Sparks',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'At the end of her turn, hurls a spark dealing 1 damage to a random enemy.',
        heroicPassiveText: 'At the end of her turn, hurls 2 sparks dealing 1 damage each to random enemies.',
        introQuote: 'Watch the sparks closely—one blink and your board turns to ash.',
        midQuote: 'Careful now… the hearth burns hottest right before it dies!',
        defeatQuote: 'Well played. You read my spells better than most regulars.',
        tip: 'Expect Flamestrike on Turn 7 and Mirror Entity traps—test Secrets with small minions first.',
      },
      {
        id: 'ch1_blackwick',
        chapterId: 'ch1',
        order: 3,
        name: 'Captain Blackwick',
        epithet: 'Chapter Boss · Shadow of the Quay',
        heroClass: 'ROGUE',
        deckId: 'starter_rogue',
        recommendedDeckId: 'starter_paladin',
        portraitCardId: 'VAN_EX1_613',
        signatureCards: ['VAN_EX1_613', 'VAN_EX1_116', 'VAN_EX1_145'],
        isChapterBoss: true,
        hp: 30,
        armor: 5,
        level: 'normal',
        heroicHp: 40,
        heroicArmor: 10,
        passiveId: 'shadow_coin',
        passiveName: 'Smuggler’s Coin',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'At the start of his turn, if he has 4 or fewer cards, slips The Coin into his hand.',
        heroicPassiveText: 'At the start of his turn, if he has 5 or fewer cards, slips The Coin into his hand.',
        introQuote: 'Coins on the table, stranger. Let us see if your deck cuts deep enough.',
        midQuote: 'Tch—clever tricks. Time to spend the whole purse!',
        defeatQuote: 'Take the pass to the Foundry, then. You have earned the road.',
        tip: 'Blackwick uses extra Coins to trigger SI:7 Agent and huge Edwin VanCleef turns. Hold removal or Taunts!',
      },
    ],
  },
  {
    id: 'ch2',
    number: 2,
    roman: 'II',
    title: 'The Clockwork Foundry',
    eraLabel: 'Naxxramas & GvG',
    subtitle: 'Outlast brass contraptions and restless relics',
    lore: 'Beneath the hills, gears groan and ancient crypts rattle. The Foundry holds the oil needed to relight the beacon—if you can survive its wardens.',
    accent: '#63b4e8',
    reward: {
      packs: 1,
      embers: 75,
      relicId: 'pendulum',
    },
    bosses: [
      {
        id: 'ch2_sprocket',
        chapterId: 'ch2',
        order: 4,
        name: 'Tinker-Chief Sprocket',
        epithet: 'Architect of Brasswork',
        heroClass: 'MAGE',
        deckId: 'meta_gvg_mage_1',
        recommendedDeckId: 'meta_gvg_paladin_1',
        portraitCardId: 'GVG_110',
        signatureCards: ['GVG_110', 'GVG_004', 'GVG_096'],
        hp: 30,
        armor: 0,
        level: 'normal',
        heroicHp: 40,
        heroicArmor: 5,
        passiveId: 'scrap_assembly',
        passiveName: 'Scrap Assembly',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'At the end of his turn, gives a random friendly Mech +1/+1.',
        heroicPassiveText: 'At the end of his turn, gives a random friendly Mech +2/+2.',
        openingBoard: ['GVG_082'],
        heroicOpeningBoard: ['GVG_082'],
        openingBoardLabel: 'Starts with a Clockwork Gnome (2/1)',
        heroicOpeningBoardLabel: 'Starts with a Clockwork Gnome (2/1)',
        introQuote: 'Step aside! My Mechwarpers are calibrated to crush organic decks in six turns!',
        midQuote: 'Warning! Boiler pressure critical—overclocking all Mechs!',
        defeatQuote: 'My springs! My gears! Fine—the foundry gate is unlocked!',
        tip: 'Clear every Mech immediately so neither Scrap Assembly nor Goblin Blastmage can snowball.',
      },
      {
        id: 'ch2_widow',
        chapterId: 'ch2',
        order: 5,
        name: 'Widow of the Crypt',
        epithet: 'Curator of the Reliquary',
        heroClass: 'PRIEST',
        deckId: 'meta_gvg_priest_2',
        recommendedDeckId: 'meta_gvg_shaman_1',
        portraitCardId: 'FP1_013',
        signatureCards: ['FP1_013', 'VAN_EX1_016', 'VAN_EX1_110'],
        hp: 32,
        armor: 0,
        level: 'normal',
        heroicHp: 42,
        heroicArmor: 5,
        passiveId: 'crypt_call',
        passiveName: 'Crypt Call',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'At the end of her turn, summons a 1/1 Spectral Spider.',
        heroicPassiveText: 'At the end of her turn, summons two 1/1 Spectral Spiders.',
        openingBoard: ['FP1_002'],
        heroicOpeningBoard: ['FP1_002'],
        openingBoardLabel: 'Starts with a Haunted Creeper (1/2)',
        heroicOpeningBoardLabel: 'Starts with a Haunted Creeper (1/2)',
        introQuote: 'What breaks in this hall rarely stays broken for long.',
        midQuote: 'The tomb answers back… rise again, my children!',
        defeatQuote: 'Even the reliquary grows quiet when the light burns bright enough.',
        tip: 'Her sticky Deathrattles snowball behind Kel’Thuzad. Pack AoE clears or Silence and pressure before Turn 8.',
      },
      {
        id: 'ch2_overlord',
        chapterId: 'ch2',
        order: 6,
        name: 'Ironclad Overlord',
        epithet: 'Chapter Boss · Warden of the Iron Vault',
        heroClass: 'WARRIOR',
        deckId: 'meta_gvg_warrior_1',
        recommendedDeckId: 'meta_gvg_druid_2',
        portraitCardId: 'VAN_EX1_298',
        signatureCards: ['VAN_EX1_298', 'VAN_EX1_414', 'VAN_EX1_407'],
        isChapterBoss: true,
        hp: 35,
        armor: 5,
        level: 'normal',
        heroicHp: 45,
        heroicArmor: 10,
        passiveId: 'iron_guard',
        passiveName: 'Iron Vault',
        passivePower: 2,
        heroicPassivePower: 4,
        passiveText: 'At the end of his turn, forges +2 Armor.',
        heroicPassiveText: 'At the end of his turn, forges +4 Armor.',
        openingBoard: ['VAN_EX1_402'],
        heroicOpeningBoard: ['VAN_EX1_402'],
        openingBoardLabel: 'Starts with an Armorsmith (1/4)',
        heroicOpeningBoardLabel: 'Starts with an Armorsmith (1/4)',
        introQuote: 'Steel outlasts flame. Pour all your fury against these walls—I will still stand.',
        midQuote: 'A crack in the bastion? Impossible! Seal the plates!',
        defeatQuote: 'The vault yields. Carry the Pendulum upward, challenger.',
        tip: 'Kill the opening Armorsmith early, avoid overcommitting into Brawl, and watch for Shield Slam & Grommash.',
      },
    ],
  },
  {
    id: 'ch3',
    number: 3,
    roman: 'III',
    title: 'The Ember Tourney',
    eraLabel: 'Blackrock & Grand Tournament',
    subtitle: 'Best the champions of dragonfire and oath',
    lore: 'At the high plateau, knights and dragon-speakers hold the Ember Tourney. Only a champion may claim the Emberheart Flask and cross the ridge.',
    accent: '#f07152',
    reward: {
      packs: 2,
      embers: 100,
      relicId: 'emberheart',
    },
    bosses: [
      {
        id: 'ch3_kael',
        chapterId: 'ch3',
        order: 7,
        name: 'Flamecaller Kael',
        epithet: 'Duelist of the Brazier',
        heroClass: 'MAGE',
        deckId: 'meta_tgt_mage_1',
        recommendedDeckId: 'meta_tgt_warrior_2',
        portraitCardId: 'BRM_002',
        signatureCards: ['AT_004', 'VAN_CS2_028', 'VAN_EX1_284'],
        hp: 32,
        armor: 0,
        level: 'normal',
        heroicHp: 42,
        heroicArmor: 5,
        passiveId: 'cinder_bolt',
        passiveName: 'Brazier Volley',
        passivePower: 2,
        heroicPassivePower: 3,
        passiveText: 'At the end of his turn, launches 2 fireballs dealing 1 damage each to random enemies.',
        heroicPassiveText: 'At the end of his turn, launches 3 fireballs dealing 1 damage each to random enemies.',
        introQuote: 'Every spell feeds the next—can your line endure a storm of sparks?',
        midQuote: 'You survived the first volley? Let us turn up the furnace!',
        defeatQuote: 'My braziers are spent. The Tourney stands in awe.',
        tip: 'Remove Mana Wyrm and Flamewaker immediately—high-Health minions shrug off his Brazier Volley.',
      },
      {
        id: 'ch3_seraphine',
        chapterId: 'ch3',
        order: 8,
        name: 'Marshal Seraphine',
        epithet: 'Banner of the Oathbox',
        heroClass: 'PALADIN',
        deckId: 'meta_tgt_paladin_1',
        recommendedDeckId: 'meta_tgt_mage_2',
        portraitCardId: 'VAN_EX1_383',
        signatureCards: ['LF_M03', 'GVG_061', 'VAN_EX1_382'],
        hp: 35,
        armor: 0,
        level: 'normal',
        heroicHp: 45,
        heroicArmor: 5,
        passiveId: 'silver_oath',
        passiveName: 'Silver Banner',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'At the start of her turn, summons a 1/1 Silver Hand Recruit.',
        heroicPassiveText: 'At the start of her turn, summons two 1/1 Silver Hand Recruits.',
        introQuote: 'Stand fast, recruits! Hidden oaths shield every step we take.',
        midQuote: 'Hold the line! Sound the horn for the vanguard!',
        defeatQuote: 'A noble victory. You have earned the respect of the Silver Banner.',
        tip: 'Pack sweepers for her endless Recruits and sequence attacks carefully when Oathbox Marshal pulls Secrets.',
      },
      {
        id: 'ch3_valdris',
        chapterId: 'ch3',
        order: 9,
        name: 'Wyrmlord Valdris',
        epithet: 'Chapter Boss · Keeper of Twilight Wings',
        heroClass: 'PRIEST',
        deckId: 'meta_tgt_priest_1',
        recommendedDeckId: 'meta_tgt_druid_1',
        portraitCardId: 'VAN_EX1_572',
        signatureCards: ['VAN_EX1_572', 'GVG_008', 'AT_017'],
        isChapterBoss: true,
        hp: 38,
        armor: 5,
        level: 'hard',
        heroicHp: 48,
        heroicArmor: 10,
        passiveId: 'dragon_breath',
        passiveName: 'Twilight Mend',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'At the end of his turn, restores 2 Health to himself and all friendly minions.',
        heroicPassiveText: 'At the end of his turn, restores 3 Health to himself and all friendly minions.',
        openingBoard: ['BRM_004'],
        heroicOpeningBoard: ['BRM_004'],
        openingBoardLabel: 'Starts with a Twilight Whelp (2/1)',
        heroicOpeningBoardLabel: 'Starts with a Twilight Whelp (2/1)',
        introQuote: 'Dragons remember every flame that ever died. Show me why yours deserves to live.',
        midQuote: 'You wound a dragon-speaker? Twilight, mend my wings!',
        defeatQuote: 'The ridge opens before you. Drink from the Emberheart and press on.',
        tip: 'Finish damaged Dragons completely—Twilight Mend heals surviving minions every single turn!',
      },
    ],
  },
  {
    id: 'ch4',
    number: 4,
    roman: 'IV',
    title: 'Whispers of the Deep',
    eraLabel: 'Explorers & Old Gods',
    subtitle: 'Brave the sunken ruins and ancient sigils',
    lore: 'Beyond the mountain lies the drowned basin, where forbidden bells toll and the Hollow Sovereign hoards ancient relics beneath dark waters.',
    accent: '#9d7bf0',
    reward: {
      packs: 2,
      embers: 125,
      relicId: 'satchel',
    },
    bosses: [
      {
        id: 'ch4_vesper',
        chapterId: 'ch4',
        order: 10,
        name: 'Bellkeeper Vesper',
        epithet: 'Huntswoman of the Last Bell',
        heroClass: 'HUNTER',
        deckId: 'meta_old_gods_hunter_3',
        recommendedDeckId: 'meta_old_gods_paladin_1',
        portraitCardId: 'VAN_EX1_534',
        signatureCards: ['LF_M09', 'VAN_EX1_534', 'VAN_EX1_016'],
        hp: 35,
        armor: 0,
        level: 'normal',
        heroicHp: 45,
        heroicArmor: 5,
        passiveId: 'wild_pack',
        passiveName: 'Call of the Pack',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'At the end of her turn, gives a random friendly Beast +1/+1.',
        heroicPassiveText: 'At the end of her turn, gives a random friendly Beast +2/+1.',
        introQuote: 'Hear the chime? Every beast you fell rises once more for the hunt.',
        midQuote: 'Ring the bronze bell—let the pack tear through!',
        defeatQuote: 'The bell falls silent… move quickly before the tide turns.',
        tip: 'Keep Beasts off her board so Call of the Pack fizzles, and save answers for Savannah Highmane.',
      },
      {
        id: 'ch4_kor',
        chapterId: 'ch4',
        order: 11,
        name: 'Stormshaper Kor',
        epithet: 'Voice of the Rift',
        heroClass: 'SHAMAN',
        deckId: 'meta_old_gods_shaman_1',
        recommendedDeckId: 'meta_old_gods_warrior_3',
        portraitCardId: 'OG_024',
        signatureCards: ['VAN_EX1_567', 'VAN_EX1_248', 'VAN_EX1_241'],
        hp: 38,
        armor: 0,
        level: 'hard',
        heroicHp: 48,
        heroicArmor: 5,
        passiveId: 'storm_surge',
        passiveName: 'Storm Surge',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'At the start of his turn, unlocks 1 Overloaded Mana Crystal.',
        heroicPassiveText: 'At the start of his turn, unlocks up to 2 Overloaded Mana Crystals.',
        introQuote: 'Thunder answers power—no matter the cost tomorrow!',
        midQuote: 'The sky splits open! Feel the full weight of the storm!',
        defeatQuote: 'The squall breaks. Your footing held where others washed away.',
        tip: 'Storm Surge removes his Overload downside—mulligan hard for early removal, Taunts, and healing.',
      },
      {
        id: 'ch4_sovereign',
        chapterId: 'ch4',
        order: 12,
        name: 'The Hollow Sovereign',
        epithet: 'Chapter Boss · Collector of Sigils',
        heroClass: 'WARLOCK',
        deckId: 'meta_old_gods_warlock_2',
        recommendedDeckId: 'meta_old_gods_druid_1',
        portraitCardId: 'LOE_011',
        signatureCards: ['LF_M08', 'VAN_EX1_323', 'VAN_EX1_572'],
        isChapterBoss: true,
        hp: 40,
        armor: 8,
        level: 'hard',
        heroicHp: 50,
        heroicArmor: 12,
        passiveId: 'hollow_siphon',
        passiveName: 'Hollow Siphon',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'At the end of his turn, drains 1 Health from your hero.',
        heroicPassiveText: 'At the end of his turn, drains 2 Health from your hero.',
        openingBoard: ['VAN_CS2_065'],
        heroicOpeningBoard: ['VAN_CS2_065'],
        openingBoardLabel: 'Starts with a Voidwalker (1/3 Taunt)',
        heroicOpeningBoardLabel: 'Starts with a Voidwalker (1/3 Taunt)',
        introQuote: 'A single copy of every secret, and a colossus waiting in the dark.',
        midQuote: 'Your warmth leaks away… the sigils are nearly aligned!',
        defeatQuote: 'My hoard shatters… take the Starlight Satchel and face the Spire.',
        tip: 'Emberheart Flask counters Hollow Siphon nicely. Expect Reno Jackson to heal him once—keep board pressure ready.',
      },
    ],
  },
  {
    id: 'ch5',
    number: 5,
    roman: 'V',
    title: 'The Last Spire',
    eraLabel: 'Gadgetzan & Un’Goro Finale',
    subtitle: 'Reclaim the beacon at the top of the world',
    lore: 'The syndicate captains and the Warden of the Eclipse hold the great lighthouse dark. Defeat the Spire’s final defenders to restore First Light.',
    accent: '#ffd86b',
    reward: {
      packs: 3,
      embers: 200,
      relicId: 'crown',
      cosmeticId: 'title_first_light',
      cosmeticName: 'First Light',
    },
    bosses: [
      {
        id: 'ch5_vex',
        chapterId: 'ch5',
        order: 13,
        name: 'Boss Don Vex',
        epithet: 'Lotus Magnate of the Wilds',
        heroClass: 'DRUID',
        deckId: 'meta_ungoro_druid_2',
        recommendedDeckId: 'meta_ungoro_paladin_1',
        portraitCardId: 'CFM_902',
        signatureCards: ['CFM_902', 'OG_044', 'VAN_EX1_095'],
        hp: 40,
        armor: 0,
        level: 'hard',
        heroicHp: 50,
        heroicArmor: 5,
        passiveId: 'jade_bloom',
        passiveName: 'Jade Bloom',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'Every 2nd boss turn, sculpts a growing Jade Golem.',
        heroicPassiveText: 'Every boss turn after Turn 1, sculpts a growing Jade Golem (up to 5 minions).',
        openingBoard: ['JADE_GOLEM'],
        heroicOpeningBoard: ['JADE_GOLEM'],
        openingBoardLabel: 'Starts with a 1/1 Jade Golem',
        heroicOpeningBoardLabel: 'Starts with a 1/1 Jade Golem',
        introQuote: 'Every stone you shatter only pays for a bigger one. That is good business.',
        midQuote: 'Alright, you want to rush the ledger? Send out the heavy Jade!',
        defeatQuote: 'Tch… bad investment. Go bother the Admiral upstairs.',
        tip: 'Jade Bloom accelerates his Golems automatically—Clockwork Pendulum or fast tempo decks shine here.',
      },
      {
        id: 'ch5_admiral',
        chapterId: 'ch5',
        order: 14,
        name: 'Pyreclaw Admiral',
        epithet: 'Scourge of the Sky-Dock',
        heroClass: 'WARRIOR',
        deckId: 'meta_ungoro_warrior_1',
        recommendedDeckId: 'meta_ungoro_paladin_3',
        portraitCardId: 'VAN_NEW1_024',
        signatureCards: ['VAN_NEW1_024', 'LF_M12', 'VAN_NEW1_027'],
        hp: 40,
        armor: 5,
        level: 'hard',
        heroicHp: 50,
        heroicArmor: 10,
        passiveId: 'broadside',
        passiveName: 'Sky-Dock Broadside',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'At the end of his turn, if he has a weapon equipped, fires cannons for 2 damage to your hero.',
        heroicPassiveText: 'At the end of his turn, if he has a weapon equipped, fires cannons for 3 damage to your hero.',
        introQuote: 'All hands! Cut the ropes and sink this lantern-bearer before Turn 6!',
        midQuote: 'Man the starboard cannons! We go down swinging!',
        defeatQuote: 'Hull’s breached! The Spire staircase is yours—good luck with the Warden.',
        tip: 'Destroy his weapons or out-heal Broadside with Emberheart Flask & Taunts until his hand runs dry.',
      },
      {
        id: 'ch5_eclipse',
        chapterId: 'ch5',
        order: 15,
        name: 'Warden of the Eclipse',
        epithet: 'Final Boss · Keeper of the Dark Spire',
        heroClass: 'WARLOCK',
        deckId: 'meta_ungoro_warlock_3',
        recommendedDeckId: 'meta_ungoro_mage_3',
        portraitCardId: 'VAN_EX1_323',
        signatureCards: ['VAN_EX1_323', 'LF_006', 'LF_M30'],
        isChapterBoss: true,
        hp: 45,
        armor: 10,
        level: 'hard',
        heroicHp: 55,
        heroicArmor: 15,
        heroicBonusMana: 1,
        passiveId: 'eclipse_aura',
        passiveName: 'Eclipse Dominion',
        passivePower: 1,
        heroicPassivePower: 2,
        passiveText: 'Summons a 1/3 Voidwalker each turn (max 5 minions) and drains 1 Health from your hero at end of turn.',
        heroicPassiveText: 'Summons a 1/4 Voidwalker each turn (max 5 minions) and drains 2 Health from your hero at end of turn.',
        openingBoard: ['VAN_CS2_065'],
        heroicOpeningBoard: ['VAN_CS2_065', 'VAN_CS2_065'],
        openingBoardLabel: 'Starts with a Voidwalker (1/3 Taunt)',
        heroicOpeningBoardLabel: 'Starts with two Voidwalkers (1/3 Taunt)',
        introQuote: 'The world sleeps easier in shadow. Come, then—try to spark the Spire against the Ashfall.',
        midQuote: 'A stubborn spark! Let the Eclipse swallow the sky!',
        defeatQuote: 'The glass ignites… First Light returns to Lanternfall. The beacon is yours!',
        tip: 'Bring your strongest Relic and value engine. Avoid dumping your whole hand into Ashen Reckoning, and push lethal before Jaraxxus takes over.',
      },
    ],
  },
];

export const ALL_CAMPAIGN_BOSSES: CampaignBoss[] = CAMPAIGN_CHAPTERS.flatMap((c) => c.bosses);

export function bossById(id: string): CampaignBoss | undefined {
  return ALL_CAMPAIGN_BOSSES.find((b) => b.id === id);
}

export function chapterById(id: string): CampaignChapter | undefined {
  return CAMPAIGN_CHAPTERS.find((c) => c.id === id);
}
