// The Road to First Light: a well-paced, deck-building Campaign across 5 Halls (15 fair 30 HP duels).
// Players begin with a humble Basic/Common starter deck, defeat escalating rival decks, earn
// card picks after each victory, and build their own 30-card deck to claim First Light.

export interface PrologueBeat {
  kicker: string;
  title: string;
  body: string;
}

export const CAMPAIGN_PROLOGUE: PrologueBeat[] = [
  {
    kicker: 'Prologue · Lanternfall Harbour',
    title: 'The Lamps Are Growing Dim',
    body: 'Across the five halls of Lanternfall, the harbour lights have begun to gutter. Once a generation, a challenger walks the Circuit—from the waterfront inn to the High Spire—to prove a deck worthy of relighting First Light.',
  },
  {
    kicker: 'Your Deck · Your Journey',
    title: 'Start Humble, Grow Strong',
    body: 'You begin with a worn tavern deck of Basics and Commons. Every rival you defeat opens cards from their hall—Rares, Epics, and Legends—for you to draft and weave into your own 30-card deck.',
  },
  {
    kicker: 'The Code of the Circuit',
    title: 'Fair Tables, Honest Duels',
    body: 'No rigged hands, no inflated Health, no parlor tricks. Every match along the Road is a straight 30-Health duel—your growing deck and sharp play against fifteen rival duelists.',
  },
];

export const HERO_STARTER_PITCH: Record<string, { style: string; summary: string }> = {
  MAGE: { style: 'Spells & Tempo', summary: 'Frostbolt, Fireball, and crisp board control.' },
  WARRIOR: { style: 'Weapons & Steel', summary: 'Fiery War Axe, sturdy Taunts, and Execute.' },
  HUNTER: { style: 'Beasts & Pressure', summary: 'Steady Shot, Animal Companion, and Kill Command.' },
  PALADIN: { style: 'Buffs & Shields', summary: 'Truesilver Champion, Consecration, and Blessing of Kings.' },
  PRIEST: { style: 'Healing & Value', summary: 'Northshire Cleric, Shadow Words, and durable minions.' },
  ROGUE: { style: 'Combos & Blades', summary: 'Backstab, Deadly Poison, and swift tempo swings.' },
  SHAMAN: { style: 'Totems & Elements', summary: 'Flametongue Totem, Hex, and Fire Elemental.' },
  WARLOCK: { style: 'Swarm & Tap', summary: 'Life Tap card draw, cheap demons, and Hellfire.' },
  DRUID: { style: 'Ramp & Giants', summary: 'Wild Growth, Swipe, and towering late-game minions.' },
};

export interface CampaignRival {
  id: string;
  chapterId: string;
  order: number; // 1..15
  name: string;
  title: string;
  heroClass: string;
  /** Builtin deck id, or 'humble_starter' for early fair Basic/Common decks. */
  deckId: string;
  /** Variant seed when deckId === 'humble_starter'. */
  starterVariant?: number;
  deckLabel: string;
  portraitCardId: string;
  isChampion?: boolean;
  level: 'easy' | 'normal' | 'hard';
  storyLine: string;
  introQuote: string;
  midQuote: string;
  defeatQuote: string;
}

export interface CampaignChapter {
  id: string;
  number: number;
  roman: string;
  title: string;
  eraLabel: string;
  /** Card ID prefixes unlocked in this chapter's card reward pool. */
  rewardPrefixes: string[];
  introText: string;
  outroText: string;
  accent: string;
  rewardPacks: number;
  rewardEmbers: number;
  cosmeticId?: string;
  cosmeticName?: string;
  rivals: CampaignRival[];
}

export const CAMPAIGN_CHAPTERS: CampaignChapter[] = [
  {
    id: 'ch1',
    number: 1,
    roman: 'I',
    title: 'The Lantern Inn',
    eraLabel: 'Classic Hall',
    rewardPrefixes: ['VAN'],
    introText:
      'Rain drums on the inn windows while the harbour regulars test newcomers at the oak tables. Win three honest matches here to earn your Circuit writ and Classic card rewards.',
    outroText:
      'Captain Blackwick slides the brass Foundry pass across the felt. Your starter deck already carries sharper steel—and the road climbs upward.',
    accent: '#e8a849',
    rewardPacks: 1,
    rewardEmbers: 50,
    rivals: [
      {
        id: 'r1_bram',
        chapterId: 'ch1',
        order: 1,
        name: 'Bram the Regular',
        title: 'Hearthside Brawler',
        heroClass: 'WARRIOR',
        deckId: 'humble_starter',
        starterVariant: 1,
        deckLabel: 'Tavern Warrior (Basic & Common)',
        portraitCardId: 'VAN_CS2_106',
        level: 'easy',
        storyLine: 'Bram plays a straightforward tavern Warrior deck—weapons, Taunts, and honest minions.',
        introQuote: 'Pull up a chair! Let us see how your starter deck holds up.',
        midQuote: 'Hah—alright, you actually know how to trade!',
        defeatQuote: 'Fair win! Take your pick from the inn’s spare cards.',
      },
      {
        id: 'r2_maren',
        chapterId: 'ch1',
        order: 2,
        name: 'Maren the Spark',
        title: 'Apprentice Pyromancer',
        heroClass: 'MAGE',
        deckId: 'humble_starter',
        starterVariant: 2,
        deckLabel: 'Hearth Mage (Basic & Common)',
        portraitCardId: 'VAN_CS2_029',
        level: 'easy',
        storyLine: 'Maren favors Fireballs, Frostbolts, and Water Elementals—watch out for Turn 7 Flamestrike.',
        introQuote: 'Mind the embers—I have been practicing my spell curve all week!',
        midQuote: 'Ooh, close one… time to bring out the big spells!',
        defeatQuote: 'Nicely done! Your deck is already coming together.',
      },
      {
        id: 'r3_blackwick',
        chapterId: 'ch1',
        order: 3,
        name: 'Captain Blackwick',
        title: 'Inn Champion',
        heroClass: 'ROGUE',
        deckId: 'starter_rogue',
        deckLabel: 'Classic Tempo Rogue',
        portraitCardId: 'VAN_EX1_613',
        isChampion: true,
        level: 'easy',
        storyLine: 'The inn’s sharpest card-player pilots a full Classic Rogue list with combos and blades.',
        introQuote: 'Beat me on the level, newcomer, and the road to the Foundry is yours.',
        midQuote: 'Not bad at all. Let us see how you answer a proper combo.',
        defeatQuote: 'Well played. Pick a Legend from the inn’s lockbox—you earned it.',
      },
    ],
  },
  {
    id: 'ch2',
    number: 2,
    roman: 'II',
    title: 'The Brass Foundry',
    eraLabel: 'Naxxramas & GvG',
    rewardPrefixes: ['FP1', 'GVG'],
    introText:
      'Lantern oil and clockwork gears fill the Foundry halls. Here the duelists wield sticky Deathrattles and swift Mechs—defeat them to add Naxxramas and GvG cards to your deck.',
    outroText:
      'The heavy foundry doors grind open toward the mountain trail. Your deck now hums with clockwork and crypt relics alike.',
    accent: '#63b4e8',
    rewardPacks: 1,
    rewardEmbers: 75,
    rivals: [
      {
        id: 'r4_sprocket',
        chapterId: 'ch2',
        order: 4,
        name: 'Tinker Sprocket',
        title: 'Foundry Machinist',
        heroClass: 'MAGE',
        deckId: 'meta_gvg_mage_1',
        deckLabel: 'Brasswork Mech Mage',
        portraitCardId: 'GVG_110',
        level: 'easy',
        storyLine: 'Sprocket floods early with discounted Mechs and Goblin Blastmage.',
        introQuote: 'Fresh off the workbench—let us test my Mechs against your new cards!',
        midQuote: 'Hold on! My springs are still warming up!',
        defeatQuote: 'Back to the drawing board! Take some Foundry parts for your trouble.',
      },
      {
        id: 'r5_vesper',
        chapterId: 'ch2',
        order: 5,
        name: 'Sister Vesper',
        title: 'Reliquary Keeper',
        heroClass: 'PRIEST',
        deckId: 'meta_gvg_priest_2',
        deckLabel: 'Ember Reliquary Priest',
        portraitCardId: 'FP1_013',
        level: 'normal',
        storyLine: 'Vesper’s Deathrattle minions stick to the board and build toward Kel’Thuzad.',
        introQuote: 'A steady hand beats haste in the Reliquary. Show me your patience.',
        midQuote: 'A sharp push—let us see if you can clear what rises next.',
        defeatQuote: 'Gracefully won. The Reliquary offers its rarest cards to the victor.',
      },
      {
        id: 'r6_ironvault',
        chapterId: 'ch2',
        order: 6,
        name: 'Foreman Ironvault',
        title: 'Foundry Champion',
        heroClass: 'WARRIOR',
        deckId: 'meta_gvg_warrior_1',
        deckLabel: 'Iron Vault Control Warrior',
        portraitCardId: 'VAN_EX1_298',
        isChampion: true,
        level: 'normal',
        storyLine: 'Ironvault stacks Armor, sweeps with Brawl, and closes with heavy late-game threats.',
        introQuote: 'Many challengers crack against the Iron Vault. Let us test your curve.',
        midQuote: 'Hmph—a real dent in the steel. Good match!',
        defeatQuote: 'You broke the Vault cleanly. Choose a Foundry Legend and head for the ridge.',
      },
    ],
  },
  {
    id: 'ch3',
    number: 3,
    roman: 'III',
    title: 'The High Tourney',
    eraLabel: 'Blackrock & Grand Tournament',
    rewardPrefixes: ['BRM', 'AT'],
    introText:
      'Pennants snap in the mountain wind at the High Tourney. Spell-slingers, Oathbox knights, and Dragon-speakers await—each victory unlocks Blackrock and Tournament cards.',
    outroText:
      'The pavilion erupts as Valdris bows. With Tournament cards reforging your list, only the Drowned Archive stands between you and the Spire.',
    accent: '#f07152',
    rewardPacks: 2,
    rewardEmbers: 100,
    rivals: [
      {
        id: 'r7_kael',
        chapterId: 'ch3',
        order: 7,
        name: 'Duelist Kael',
        title: 'Brazier Arcanist',
        heroClass: 'MAGE',
        deckId: 'meta_tgt_mage_1',
        deckLabel: 'Flamewake Tempo Mage',
        portraitCardId: 'BRM_002',
        level: 'normal',
        storyLine: 'Kael pairs cheap spells with Flamewaker and Mana Wyrm for explosive mid-game turns.',
        introQuote: 'The crowd loves fireworks—let us give them a match to remember!',
        midQuote: 'Clever counter! Time to chain my best spells!',
        defeatQuote: 'A dazzling duel. You have earned the crowd’s cheer—and new cards.',
      },
      {
        id: 'r8_seraphine',
        chapterId: 'ch3',
        order: 8,
        name: 'Marshal Seraphine',
        title: 'Oathbox Knight',
        heroClass: 'PALADIN',
        deckId: 'meta_tgt_paladin_1',
        deckLabel: 'Oathbox Secrets Paladin',
        portraitCardId: 'VAN_EX1_383',
        level: 'normal',
        storyLine: 'Seraphine layers Secrets and Muster for Battle to control every trade.',
        introQuote: 'Honor on the table, challenger. Watch your step around hidden oaths.',
        midQuote: 'Well struck! The Silver Banner does not yield easily.',
        defeatQuote: 'A clean triumph. May these Tourney cards serve your deck well.',
      },
      {
        id: 'r9_valdris',
        chapterId: 'ch3',
        order: 9,
        name: 'Valdris the Scaled',
        title: 'Tourney Champion',
        heroClass: 'PRIEST',
        deckId: 'meta_tgt_priest_1',
        deckLabel: 'Twilight Dragon Priest',
        portraitCardId: 'VAN_EX1_572',
        isChampion: true,
        level: 'normal',
        storyLine: 'Valdris curves stout Twilight Dragons into Lightbomb and Ysera.',
        introQuote: 'Dragons reward discipline and tight deckbuilding. Show me what you have crafted.',
        midQuote: 'Impressive—your list truly has teeth!',
        defeatQuote: 'The Tourney crown is yours. Claim a Dragon-age Legend before descending.',
      },
    ],
  },
  {
    id: 'ch4',
    number: 4,
    roman: 'IV',
    title: 'The Drowned Archive',
    eraLabel: 'Explorers & Old Gods',
    rewardPrefixes: ['LOE', 'LOEA10', 'OG'],
    introText:
      'Torchlight flickers off sunken stonework in the Drowned Archive. Master duelists here field Explorers and Old Gods strategies—only a finely tuned deck will carry you through.',
    outroText:
      'Curator Renwick shuts his ledger with a grin and unlocks the sea-lift to the High Spire. Your deck is now battle-tested against the toughest halls in the realm.',
    accent: '#9d7bf0',
    rewardPacks: 2,
    rewardEmbers: 125,
    rivals: [
      {
        id: 'r10_harlan',
        chapterId: 'ch4',
        order: 10,
        name: 'Tracker Harlan',
        title: 'Bellkeeper of the Reef',
        heroClass: 'HUNTER',
        deckId: 'meta_old_gods_hunter_3',
        deckLabel: 'Bellkeeper Midrange Hunter',
        portraitCardId: 'VAN_EX1_534',
        level: 'normal',
        storyLine: 'Harlan backs sticky Beasts and Savannah Highmane with Keeper of the Last Bell.',
        introQuote: 'Long way from the inn, isn’t it? Let us see how your deck handles the wilds.',
        midQuote: 'Good read—but the hunt isn’t over yet!',
        defeatQuote: 'Sharp play. Pick your spoils from the Archive shelves.',
      },
      {
        id: 'r11_kor',
        chapterId: 'ch4',
        order: 11,
        name: 'Stormcaller Kor',
        title: 'Tidebreaker Shaman',
        heroClass: 'SHAMAN',
        deckId: 'meta_old_gods_shaman_1',
        deckLabel: 'Groundbreak Overload Shaman',
        portraitCardId: 'OG_024',
        level: 'hard',
        storyLine: 'Kor opens fiercely with Tunnel Trogg, Totem Golem, and Doomhammer burst.',
        introQuote: 'Fast tempo, hard hits—if your early curve is shaky, the tide takes you!',
        midQuote: 'You weathered the opening squall? Respect!',
        defeatQuote: 'Steady as bedrock. Take what you need from the Archive vault.',
      },
      {
        id: 'r12_renwick',
        chapterId: 'ch4',
        order: 12,
        name: 'Curator Renwick',
        title: 'Archive Champion',
        heroClass: 'WARLOCK',
        deckId: 'meta_old_gods_warlock_2',
        deckLabel: 'Reno Sigils Warlock',
        portraitCardId: 'LOE_011',
        isChampion: true,
        level: 'hard',
        storyLine: 'Renwick runs a rich singleton deck with Reno Jackson, board clears, and Lantern Colossus.',
        introQuote: 'One copy of thirty curated treasures—let us compare our craftsmanship.',
        midQuote: 'Aha! Good thing I packed Reno for a rainy day.',
        defeatQuote: 'Masterful. Take an Explorer or Old Gods Legend—the Spire awaits!',
      },
    ],
  },
  {
    id: 'ch5',
    number: 5,
    roman: 'V',
    title: 'The Spire Circuit',
    eraLabel: 'Karazhan, Gadgetzan & Un’Goro',
    rewardPrefixes: ['KAR', 'CFM', 'UNG'],
    introText:
      'High above the harbour fog sits the glass dome of the Spire. Three Master duelists guard the final table—defeat them all with the deck you built along the Road to relight First Light.',
    outroText:
      'A warm gold flame blooms inside the Spire lens and spills across the entire bay. From a humble tavern starter to a champion’s list—you have completed the Road to First Light.',
    accent: '#ffd86b',
    rewardPacks: 3,
    rewardEmbers: 200,
    cosmeticId: 'title_first_light',
    cosmeticName: 'First Light',
    rivals: [
      {
        id: 'r13_vex',
        chapterId: 'ch5',
        order: 13,
        name: 'Don Vex',
        title: 'Lotus Magnate',
        heroClass: 'DRUID',
        deckId: 'meta_ungoro_druid_2',
        deckLabel: 'Jade Through the Wilds Druid',
        portraitCardId: 'CFM_902',
        level: 'hard',
        storyLine: 'Don Vex ramps into endlessly scaling Jade Golems and Aya Blackpaw.',
        introQuote: 'Made it all the way to the Spire? Let us see if your deck can outpace Jade.',
        midQuote: 'Hmph—alright, time to bring out the big Golems.',
        defeatQuote: 'Clean win. Take a Spire card or two—you’ll want them upstairs.',
      },
      {
        id: 'r14_pyreclaw',
        chapterId: 'ch5',
        order: 14,
        name: 'Admiral Pyreclaw',
        title: 'Sky-Dock Duelist',
        heroClass: 'WARRIOR',
        deckId: 'meta_ungoro_warrior_1',
        deckLabel: 'Wilds Pirate Rush Warrior',
        portraitCardId: 'VAN_NEW1_024',
        level: 'hard',
        storyLine: 'Pyreclaw tests your deck’s defensive resilience with relentless Pirates and upgraded weapons.',
        introQuote: 'All sails set! Let us see if your list survives six turns of steel!',
        midQuote: 'Still standing? Tough hull you’ve built there!',
        defeatQuote: 'Fair winds to you, challenger. Keeper Solenne awaits at the lantern table.',
      },
      {
        id: 'r15_solenne',
        chapterId: 'ch5',
        order: 15,
        name: 'Keeper Solenne',
        title: 'Grand Champion of the Spire',
        heroClass: 'WARLOCK',
        deckId: 'meta_ungoro_warlock_3',
        deckLabel: 'Ashfall Control Warlock',
        portraitCardId: 'VAN_EX1_323',
        isChampion: true,
        level: 'hard',
        storyLine: 'The reigning Keeper pilots a deep Control Warlock deck—sweeps, Demons, and Lord Jaraxxus.',
        introQuote: 'Fourteen rivals behind you, and one honest table left. Show me the deck you built.',
        midQuote: 'Magnificent! This is the finest match the Spire has seen in years.',
        defeatQuote: 'The glass ignites… First Light is yours, Champion of Lanternfall!',
      },
    ],
  },
];

export const ALL_CAMPAIGN_RIVALS: CampaignRival[] = CAMPAIGN_CHAPTERS.flatMap((c) => c.rivals);

export function rivalById(id: string): CampaignRival | undefined {
  return ALL_CAMPAIGN_RIVALS.find((r) => r.id === id);
}

export function chapterById(id: string): CampaignChapter | undefined {
  return CAMPAIGN_CHAPTERS.find((c) => c.id === id);
}
