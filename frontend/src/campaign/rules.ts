// Pure Campaign progression, starter deck building, card rewards, and personal deck editing rules.
// Every match is a fair 30 HP vs 30 HP duel; progression revolves around growing your Campaign
// collection and upgrading your 30-card Campaign deck as you travel through the 5 Halls.
import type { CardDef, OpponentMode } from '../types';
import {
  ALL_CAMPAIGN_RIVALS,
  CAMPAIGN_CHAPTERS,
  chapterById,
  rivalById,
  type CampaignChapter,
  type CampaignRival,
} from './data';

export const CAMPAIGN_DECK_SIZE = 30;

export type CampaignPhase = 'intro' | 'choose_hero' | 'road' | 'rewards' | 'chapter_clear' | 'complete';

export interface CardRewardOffer {
  id: string;
  label: string;
  tier: 'class' | 'rare' | 'epic' | 'legendary' | 'consolation';
  choices: string[];
}

export interface ActiveCampaignMatch {
  gameId: string;
  rivalId: string;
}

export interface CampaignState {
  v: 2;
  phase: CampaignPhase;
  heroClass: string | null;
  /** Personal Campaign card collection: cardId -> copies owned (1..2, max 1 for Legendary). */
  collection: Record<string, number>;
  /** Player's current 30-card Campaign deck (array of card IDs). */
  deck: string[];
  /** Newly won card IDs not yet inspected in the Deck Workshop. */
  newCards: string[];
  /** Defeated rival IDs. */
  defeatedRivals: string[];
  /** Rivals where a first-loss consolation card offer was already granted. */
  consolationRivals: string[];
  /** Chapters whose completion story + profile pack rewards were claimed. */
  claimedChapters: string[];
  /** Pending card reward picks to choose before continuing. */
  pendingRewards: CardRewardOffer[];
  /** Chapter id awaiting the Chapter Clear story screen (after rewards are picked). */
  pendingChapterClear: string | null;
  activeMatch: ActiveCampaignMatch | null;
  wins: number;
  losses: number;
  preferredOpponent: OpponentMode;
  seenGames: string[];
}

const KEEP_SEEN = 120;

export function emptyCampaignState(): CampaignState {
  return {
    v: 2,
    phase: 'intro',
    heroClass: null,
    collection: {},
    deck: [],
    newCards: [],
    defeatedRivals: [],
    consolationRivals: [],
    claimedChapters: [],
    pendingRewards: [],
    pendingChapterClear: null,
    activeMatch: null,
    wins: 0,
    losses: 0,
    preferredOpponent: 'device',
    seenGames: [],
  };
}

export function cardAllowedForHero(card: CardDef, heroClass: string): boolean {
  if (!card.collectible) return false;
  if (card.classes && card.classes.length > 0) return card.classes.includes(heroClass);
  return card.card_class === heroClass || card.card_class === 'NEUTRAL';
}

export function maxCopiesOf(card: CardDef): number {
  return card.rarity === 'LEGENDARY' ? 1 : 2;
}

/** Deterministic PRNG for reproducible starter decks & reward rolls. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0 || 1;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Score a Basic/Common Classic card for building a balanced, fun humble starter deck. */
function starterCardScore(card: CardDef, heroClass: string, variant = 0): number {
  let s = card.card_class === heroClass ? 8 : 3;
  if (card.type === 'MINION') {
    const atk = card.attack ?? 0;
    const hp = card.health ?? 0;
    const expected = card.cost * 2 + 1;
    s += (atk + hp - expected) * 1.4;
    if (card.mechanics.includes('CANT_ATTACK')) s -= 12;
    if (card.mechanics.includes('TAUNT') || card.mechanics.includes('BATTLECRY') || card.mechanics.includes('DIVINE_SHIELD')) {
      s += 1.5;
    }
  } else if (card.type === 'WEAPON') {
    s += 4.5;
  } else {
    s += 2.2;
  }
  // Prefer playable mana range 1..7 for starter decks
  if (card.cost === 0) s -= 4;
  if (card.cost >= 8) s -= 3;
  // Deterministic slight tie-breaker for rival starter variants
  if (variant > 0) {
    let h = variant * 2654435761;
    for (let i = 0; i < card.id.length; i++) h = Math.imul(h ^ card.id.charCodeAt(i), 1597334677);
    s += ((h >>> 0) % 100) / 35;
  }
  return s;
}

/**
 * Builds an honest, well-curved 30-card Classic Basic & Common starter deck (15 pairs = 30 cards,
 * zero Rares/Epics/Legendaries) for either the player or an early Tavern rival.
 */
export function buildStarterDeck(heroClass: string, cards: CardDef[], variant = 0): string[] {
  const pool = cards.filter(
    (c) =>
      cardAllowedForHero(c, heroClass) &&
      c.id.startsWith('VAN_') &&
      (c.rarity === 'FREE' || c.rarity === 'COMMON'),
  );
  // Target 15 pairs across mana buckets: [0-1, 2, 3, 4, 5, 6+]
  const bucketTargets = [2, 3, 3, 3, 2, 2]; // 15 pairs = 30 cards
  const bucketOf = (cost: number) => (cost <= 1 ? 0 : cost >= 6 ? 5 : cost - 1);

  const ranked = [...pool].sort(
    (a, b) => starterCardScore(b, heroClass, variant) - starterCardScore(a, heroClass, variant) || a.id.localeCompare(b.id),
  );

  const chosen: CardDef[] = [];
  const chosenIds = new Set<string>();
  const bucketCounts = [0, 0, 0, 0, 0, 0];

  // First pass: pick up to 9 class pairs respecting curve
  for (const c of ranked) {
    if (chosen.length >= 15) break;
    if (c.card_class !== heroClass) continue;
    const b = bucketOf(c.cost);
    if (bucketCounts[b] >= bucketTargets[b]) continue;
    if (chosen.filter((x) => x.card_class === heroClass).length >= 9) break;
    chosen.push(c);
    chosenIds.add(c.id);
    bucketCounts[b] += 1;
  }

  // Second pass: fill remaining curve slots from best available (class or neutral)
  for (const c of ranked) {
    if (chosen.length >= 15) break;
    if (chosenIds.has(c.id)) continue;
    const b = bucketOf(c.cost);
    if (bucketCounts[b] >= bucketTargets[b]) continue;
    chosen.push(c);
    chosenIds.add(c.id);
    bucketCounts[b] += 1;
  }

  // Fallback if any bucket was sparse
  for (const c of ranked) {
    if (chosen.length >= 15) break;
    if (chosenIds.has(c.id)) continue;
    chosen.push(c);
    chosenIds.add(c.id);
  }

  const deck: string[] = [];
  for (const c of chosen) {
    deck.push(c.id, c.id);
  }
  return deck.slice(0, CAMPAIGN_DECK_SIZE);
}

export function deckToCollection(deck: string[]): Record<string, number> {
  const col: Record<string, number> = {};
  for (const id of deck) col[id] = (col[id] || 0) + 1;
  return col;
}

export function startCampaignWithHero(state: CampaignState, heroClass: string, cards: CardDef[]): CampaignState {
  const deck = buildStarterDeck(heroClass, cards, 0);
  return {
    ...emptyCampaignState(),
    phase: 'road',
    heroClass,
    deck,
    collection: deckToCollection(deck),
    preferredOpponent: state.preferredOpponent,
  };
}

export function advanceFromIntro(state: CampaignState): CampaignState {
  if (state.phase !== 'intro') return state;
  return { ...state, phase: 'choose_hero' };
}

export function isRivalDefeated(state: CampaignState, rivalId: string): boolean {
  return state.defeatedRivals.includes(rivalId);
}

export function currentRival(state: CampaignState): CampaignRival {
  const next = ALL_CAMPAIGN_RIVALS.find((r) => !state.defeatedRivals.includes(r.id));
  return next || ALL_CAMPAIGN_RIVALS[ALL_CAMPAIGN_RIVALS.length - 1];
}

export function currentChapter(state: CampaignState): CampaignChapter {
  if (state.pendingChapterClear) {
    const ch = chapterById(state.pendingChapterClear);
    if (ch) return ch;
  }
  const rival = currentRival(state);
  return chapterById(rival.chapterId) || CAMPAIGN_CHAPTERS[0];
}

export function isChapterCleared(state: CampaignState, chapterId: string): boolean {
  const ch = chapterById(chapterId);
  if (!ch) return false;
  return ch.rivals.every((r) => state.defeatedRivals.includes(r.id));
}

export function isCampaignComplete(state: CampaignState): boolean {
  return ALL_CAMPAIGN_RIVALS.every((r) => state.defeatedRivals.includes(r.id));
}

export function campaignSummary(state: CampaignState): string {
  const total = ALL_CAMPAIGN_RIVALS.length;
  const done = state.defeatedRivals.length;
  if (!state.heroClass || state.phase === 'intro' || state.phase === 'choose_hero') {
    return 'Begin the 5-hall story · build your deck from starter to legend';
  }
  if (state.pendingRewards.length > 0) {
    return `${done}/${total} rivals · Card rewards waiting!`;
  }
  if (state.pendingChapterClear) {
    const ch = chapterById(state.pendingChapterClear);
    return `Chapter ${ch?.roman ?? ''} Complete · Claim chapter reward`;
  }
  if (isCampaignComplete(state)) {
    return `Campaign Complete · ${state.wins}W–${state.losses}L · Champion of First Light`;
  }
  const r = currentRival(state);
  const ch = chapterById(r.chapterId);
  return `Chapter ${ch?.roman ?? 'I'} · ${done}/${total} rivals · Next: ${r.name}`;
}

// ---------------------------------------------------------------------------
// Card reward generation & picking
// ---------------------------------------------------------------------------

function cardInChapterPool(card: CardDef, chapter: CampaignChapter): boolean {
  const prefix = card.id.split('_')[0];
  return chapter.rewardPrefixes.includes(prefix);
}

function pickWeightedUnique(
  candidates: CardDef[],
  heroClass: string,
  count: number,
  rand: () => number,
): string[] {
  const pool = [...candidates];
  const chosen: string[] = [];
  for (let k = 0; k < count && pool.length > 0; k++) {
    const weights = pool.map((c) => {
      const isClass = c.card_class === heroClass || Boolean(c.classes?.includes(heroClass));
      return isClass ? 2.4 : 1.0;
    });
    const total = weights.reduce((a, b) => a + b, 0);
    let roll = rand() * total;
    let idx = pool.length - 1;
    for (let i = 0; i < pool.length; i++) {
      roll -= weights[i];
      if (roll <= 0) {
        idx = i;
        break;
      }
    }
    chosen.push(pool.splice(idx, 1)[0].id);
  }
  return chosen;
}

function eligibleRewardPool(
  cards: CardDef[],
  heroClass: string,
  collection: Record<string, number>,
  exclude: Set<string>,
): CardDef[] {
  return cards.filter(
    (c) =>
      cardAllowedForHero(c, heroClass) &&
      !exclude.has(c.id) &&
      (collection[c.id] || 0) < maxCopiesOf(c),
  );
}

export function generateRivalRewards(
  state: CampaignState,
  rival: CampaignRival,
  cards: CardDef[],
  seed: number = Date.now(),
): CardRewardOffer[] {
  const heroClass = state.heroClass;
  if (!heroClass) return [];
  const chapter = chapterById(rival.chapterId) || CAMPAIGN_CHAPTERS[0];
  const rand = mulberry32(seed);
  const used = new Set<string>();
  const offers: CardRewardOffer[] = [];

  const drawOffer = (
    id: string,
    label: string,
    tier: CardRewardOffer['tier'],
    filterFn: (c: CardDef) => boolean,
    fallbackFn: (c: CardDef) => boolean,
  ) => {
    const base = eligibleRewardPool(cards, heroClass, state.collection, used);
    let pool = base.filter(filterFn);
    if (pool.length < 3) pool = base.filter(fallbackFn);
    if (pool.length < 3) pool = base;
    const choices = pickWeightedUnique(pool, heroClass, 3, rand);
    if (choices.length > 0) {
      choices.forEach((cid) => used.add(cid));
      offers.push({ id, label, tier, choices });
    }
  };

  if (rival.isChampion) {
    drawOffer(
      `${rival.id}_epic`,
      `${chapter.eraLabel} Spoils · Choose an Epic or Rare`,
      'epic',
      (c) => cardInChapterPool(c, chapter) && (c.rarity === 'EPIC' || c.rarity === 'RARE'),
      (c) => c.rarity === 'EPIC' || c.rarity === 'RARE',
    );
    drawOffer(
      `${rival.id}_legend`,
      `${rival.name}’s Lockbox · Choose a Legendary`,
      'legendary',
      (c) => cardInChapterPool(c, chapter) && c.rarity === 'LEGENDARY',
      (c) => c.rarity === 'LEGENDARY',
    );
  } else {
    drawOffer(
      `${rival.id}_class`,
      `${chapter.eraLabel} Spoils · Choose a Class Card`,
      'class',
      (c) => cardInChapterPool(c, chapter) && (c.card_class === heroClass || Boolean(c.classes?.includes(heroClass))),
      (c) => c.card_class === heroClass || Boolean(c.classes?.includes(heroClass)),
    );
    drawOffer(
      `${rival.id}_rare`,
      `${chapter.eraLabel} Spoils · Choose a Rare or Epic`,
      'rare',
      (c) => cardInChapterPool(c, chapter) && (c.rarity === 'RARE' || c.rarity === 'EPIC'),
      (c) => c.rarity === 'RARE' || c.rarity === 'EPIC',
    );
  }

  return offers;
}

export function generateConsolationReward(
  state: CampaignState,
  rival: CampaignRival,
  cards: CardDef[],
  seed: number = Date.now(),
): CardRewardOffer | null {
  const heroClass = state.heroClass;
  if (!heroClass) return null;
  const chapter = chapterById(rival.chapterId) || CAMPAIGN_CHAPTERS[0];
  const rand = mulberry32(seed);
  const base = eligibleRewardPool(cards, heroClass, state.collection, new Set());
  let pool = base.filter(
    (c) => (cardInChapterPool(c, chapter) || c.id.startsWith('VAN_')) && (c.rarity === 'COMMON' || c.rarity === 'RARE'),
  );
  if (pool.length < 3) pool = base;
  const choices = pickWeightedUnique(pool, heroClass, 3, rand);
  if (!choices.length) return null;
  return {
    id: `${rival.id}_consolation`,
    label: 'Lesson Learned · Pick a Card to Strengthen Your Deck',
    tier: 'consolation',
    choices,
  };
}

export function pickRewardCard(state: CampaignState, cardId: string, cards: CardDef[]): CampaignState {
  if (!state.pendingRewards.length) return state;
  const [head, ...rest] = state.pendingRewards;
  if (!head.choices.includes(cardId)) return state;
  const card = cards.find((c) => c.id === cardId);
  const cap = card ? maxCopiesOf(card) : 2;
  const currentQty = state.collection[cardId] || 0;
  const nextQty = Math.min(cap, currentQty + 1);
  const nextCollection = { ...state.collection, [cardId]: nextQty };
  const nextNew = state.newCards.includes(cardId) ? state.newCards : [cardId, ...state.newCards];

  const doneRewards = rest.length === 0;
  let nextPhase: CampaignPhase = state.phase;
  if (doneRewards) {
    if (state.pendingChapterClear) nextPhase = 'chapter_clear';
    else if (isCampaignComplete(state)) nextPhase = 'complete';
    else nextPhase = 'road';
  }

  return {
    ...state,
    collection: nextCollection,
    newCards: nextNew,
    pendingRewards: rest,
    phase: nextPhase,
  };
}

// ---------------------------------------------------------------------------
// Match tracking & chapter completion
// ---------------------------------------------------------------------------

export function attachCampaignMatch(state: CampaignState, gameId: string, rivalId: string): CampaignState {
  return {
    ...state,
    activeMatch: { gameId, rivalId },
  };
}

export interface CampaignMatchOutcome {
  state: CampaignState;
  rival: CampaignRival;
  won: boolean;
  earnedRewards: number;
  chapterJustCompleted: CampaignChapter | null;
  campaignJustCompleted: boolean;
}

export function recordCampaignMatchResult(
  state: CampaignState,
  gameId: string,
  result: 'win' | 'loss' | 'draw',
  cards: CardDef[],
  seed: number = Date.now(),
): CampaignMatchOutcome | null {
  const active = state.activeMatch;
  if (!active || active.gameId !== gameId) return null;
  if (state.seenGames.includes(gameId)) return null;

  const rival = rivalById(active.rivalId);
  if (!rival) return null;

  const won = result === 'win';
  const lost = result === 'loss';
  const wasDefeated = state.defeatedRivals.includes(rival.id);
  const wasChapterCleared = isChapterCleared(state, rival.chapterId);
  const wasCampaignComplete = isCampaignComplete(state);

  const defeatedRivals = won && !wasDefeated ? [...state.defeatedRivals, rival.id] : state.defeatedRivals;
  let pendingRewards = [...state.pendingRewards];
  let consolationRivals = state.consolationRivals;

  if (won && !wasDefeated) {
    pendingRewards = [...pendingRewards, ...generateRivalRewards(state, rival, cards, seed)];
  } else if (lost && !wasDefeated && !state.consolationRivals.includes(rival.id)) {
    const consolation = generateConsolationReward(state, rival, cards, seed);
    if (consolation) {
      pendingRewards = [...pendingRewards, consolation];
      consolationRivals = [...consolationRivals, rival.id];
    }
  }

  const nextBase: CampaignState = {
    ...state,
    defeatedRivals,
    consolationRivals,
    pendingRewards,
    activeMatch: null,
    wins: state.wins + (won ? 1 : 0),
    losses: state.losses + (lost ? 1 : 0),
    seenGames: [gameId, ...state.seenGames].slice(0, KEEP_SEEN),
  };

  const chapterNowCleared = isChapterCleared(nextBase, rival.chapterId);
  const chapterJustCompleted = !wasChapterCleared && chapterNowCleared ? chapterById(rival.chapterId) ?? null : null;
  const campaignJustCompleted = !wasCampaignComplete && isCampaignComplete(nextBase);

  const pendingChapterClear = chapterJustCompleted
    ? chapterJustCompleted.id
    : nextBase.pendingChapterClear;

  const phase: CampaignPhase =
    pendingRewards.length > 0
      ? 'rewards'
      : pendingChapterClear
        ? 'chapter_clear'
        : isCampaignComplete(nextBase)
          ? 'complete'
          : 'road';

  const nextState: CampaignState = {
    ...nextBase,
    pendingChapterClear,
    phase,
  };

  return {
    state: nextState,
    rival,
    won,
    earnedRewards: pendingRewards.length - state.pendingRewards.length,
    chapterJustCompleted,
    campaignJustCompleted,
  };
}

export function completeChapterInterlude(
  state: CampaignState,
): { state: CampaignState; chapter: CampaignChapter; newlyClaimed: boolean } | null {
  const cid = state.pendingChapterClear;
  if (!cid) return null;
  const chapter = chapterById(cid);
  if (!chapter) return null;
  const newlyClaimed = !state.claimedChapters.includes(cid);
  const claimedChapters = newlyClaimed ? [...state.claimedChapters, cid] : state.claimedChapters;
  const phase: CampaignPhase = isCampaignComplete(state) ? 'complete' : 'road';
  return {
    chapter,
    newlyClaimed,
    state: {
      ...state,
      claimedChapters,
      pendingChapterClear: null,
      phase,
    },
  };
}

// ---------------------------------------------------------------------------
// Campaign Deck Editing (restricted to player's unlocked Campaign Collection!)
// ---------------------------------------------------------------------------

export function validateCampaignDeck(state: CampaignState, deck: string[], cards: CardDef[]): { ok: boolean; error: string } {
  if (!state.heroClass) return { ok: false, error: 'Choose a hero first.' };
  if (deck.length !== CAMPAIGN_DECK_SIZE) {
    return { ok: false, error: `Deck must have exactly ${CAMPAIGN_DECK_SIZE} cards (currently ${deck.length}).` };
  }
  const byId = new Map(cards.map((c) => [c.id, c]));
  const counts: Record<string, number> = {};
  for (const id of deck) {
    const c = byId.get(id);
    if (!c) return { ok: false, error: `Unknown card ${id}.` };
    if (!cardAllowedForHero(c, state.heroClass)) return { ok: false, error: `${c.name} cannot be used by this class.` };
    counts[id] = (counts[id] || 0) + 1;
    const owned = state.collection[id] || 0;
    if (counts[id] > owned) return { ok: false, error: `You only own ${owned} copy of ${c.name} in your Campaign collection.` };
    if (counts[id] > maxCopiesOf(c)) return { ok: false, error: `Too many copies of ${c.name}.` };
  }
  return { ok: true, error: '' };
}

export function saveCampaignDeck(state: CampaignState, deck: string[], cards: CardDef[]): CampaignState {
  const check = validateCampaignDeck(state, deck, cards);
  if (!check.ok) return state;
  return {
    ...state,
    deck: [...deck],
    newCards: [],
  };
}

export function clearNewCards(state: CampaignState): CampaignState {
  if (!state.newCards.length) return state;
  return { ...state, newCards: [] };
}

export function resetCampaignState(state: CampaignState): CampaignState {
  return {
    ...emptyCampaignState(),
    phase: 'choose_hero',
    preferredOpponent: state.preferredOpponent,
  };
}

export function restoreCampaignState(raw: unknown): CampaignState {
  const base = emptyCampaignState();
  if (!raw || typeof raw !== 'object') return base;
  const r = raw as Record<string, any>;
  if (r.v !== 2) return base;

  const validRivals = new Set(ALL_CAMPAIGN_RIVALS.map((x) => x.id));
  const validChapters = new Set(CAMPAIGN_CHAPTERS.map((x) => x.id));
  const validPhases = new Set<CampaignPhase>(['intro', 'choose_hero', 'road', 'rewards', 'chapter_clear', 'complete']);

  const collection: Record<string, number> = {};
  if (r.collection && typeof r.collection === 'object') {
    for (const [k, v] of Object.entries(r.collection)) {
      if (typeof v === 'number' && Number.isFinite(v) && v >= 1) collection[k] = Math.min(2, Math.floor(v));
    }
  }

  const deck = Array.isArray(r.deck) ? r.deck.filter((id: unknown): id is string => typeof id === 'string') : [];
  const newCards = Array.isArray(r.newCards) ? Array.from(new Set(r.newCards.filter((id: unknown): id is string => typeof id === 'string'))) : [];
  const defeatedRivals = Array.isArray(r.defeatedRivals)
    ? Array.from(new Set(r.defeatedRivals.filter((id: unknown): id is string => typeof id === 'string' && validRivals.has(id))))
    : [];
  const consolationRivals = Array.isArray(r.consolationRivals)
    ? Array.from(new Set(r.consolationRivals.filter((id: unknown): id is string => typeof id === 'string' && validRivals.has(id))))
    : [];
  const claimedChapters = Array.isArray(r.claimedChapters)
    ? Array.from(new Set(r.claimedChapters.filter((id: unknown): id is string => typeof id === 'string' && validChapters.has(id))))
    : [];
  const pendingRewards: CardRewardOffer[] = Array.isArray(r.pendingRewards)
    ? r.pendingRewards.filter(
        (o: any) => o && typeof o.id === 'string' && typeof o.label === 'string' && Array.isArray(o.choices) && o.choices.length > 0,
      )
    : [];
  const pendingChapterClear =
    typeof r.pendingChapterClear === 'string' && validChapters.has(r.pendingChapterClear) ? r.pendingChapterClear : null;

  let activeMatch: ActiveCampaignMatch | null = null;
  if (r.activeMatch && typeof r.activeMatch === 'object' && typeof r.activeMatch.gameId === 'string' && validRivals.has(r.activeMatch.rivalId)) {
    activeMatch = { gameId: r.activeMatch.gameId, rivalId: r.activeMatch.rivalId };
  }

  const heroClass = typeof r.heroClass === 'string' ? r.heroClass : null;
  let phase: CampaignPhase = validPhases.has(r.phase) ? r.phase : heroClass ? 'road' : 'intro';
  if (!heroClass && phase !== 'intro' && phase !== 'choose_hero') phase = 'choose_hero';
  if (heroClass && pendingRewards.length > 0) phase = 'rewards';

  return {
    v: 2,
    phase,
    heroClass,
    collection,
    deck,
    newCards,
    defeatedRivals,
    consolationRivals,
    claimedChapters,
    pendingRewards,
    pendingChapterClear,
    activeMatch,
    wins: typeof r.wins === 'number' && Number.isFinite(r.wins) && r.wins >= 0 ? Math.floor(r.wins) : 0,
    losses: typeof r.losses === 'number' && Number.isFinite(r.losses) && r.losses >= 0 ? Math.floor(r.losses) : 0,
    preferredOpponent: r.preferredOpponent === 'bot' || r.preferredOpponent === 'agent' ? r.preferredOpponent : 'device',
    seenGames: Array.isArray(r.seenGames) ? r.seenGames.filter((id: unknown): id is string => typeof id === 'string').slice(0, KEEP_SEEN) : [],
  };
}
