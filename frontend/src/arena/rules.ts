// Pure Arena draft, run progression, key & reward rules (no DOM, no I/O).
import type { CardDef, OpponentMode } from '../types';

export const ARENA_DECK_SIZE = 30;
export const ARENA_MAX_WINS = 12;
export const ARENA_MAX_LOSSES = 3;
export const GUARANTEED_RARE_PICKS = new Set([1, 10, 20, 30]);

export type ArenaPoolId = 'wild' | 'classic' | 'gvg' | 'tgt' | 'old_gods' | 'gadgetzan' | 'ungoro';

export interface ArenaPoolOption {
  id: ArenaPoolId;
  label: string;
  note: string;
}

export const ARENA_POOLS: ArenaPoolOption[] = [
  { id: 'wild', label: 'All Expansions', note: 'Every card from Classic through Un’Goro & Lanternfall' },
  { id: 'classic', label: 'Classic', note: 'Original Basic & Classic set only' },
  { id: 'gvg', label: 'Goblins vs Gnomes', note: 'Classic, Naxxramas & GvG' },
  { id: 'tgt', label: 'The Grand Tournament', note: 'Classic through TGT' },
  { id: 'old_gods', label: 'Old Gods', note: 'Classic, Blackrock, TGT, Explorers & Old Gods' },
  { id: 'gadgetzan', label: 'Gadgetzan', note: 'Classic through Mean Streets of Gadgetzan' },
  { id: 'ungoro', label: 'Journey to Un’Goro', note: 'Classic, Old Gods, Karazhan, Gadgetzan & Un’Goro' },
];

const POOL_PREFIXES: Record<Exclude<ArenaPoolId, 'wild'>, Set<string>> = {
  classic: new Set(['VAN']),
  gvg: new Set(['VAN', 'FP1', 'GVG']),
  tgt: new Set(['VAN', 'FP1', 'GVG', 'BRM', 'AT']),
  old_gods: new Set(['VAN', 'BRM', 'AT', 'LOE', 'LOEA10', 'OG']),
  gadgetzan: new Set(['VAN', 'BRM', 'AT', 'LOE', 'LOEA10', 'OG', 'KAR', 'CFM']),
  ungoro: new Set(['VAN', 'OG', 'KAR', 'CFM', 'UNG']),
};

export interface ArenaKey {
  wins: number;
  name: string;
  packs: number;
  embers: number;
}

export const ARENA_KEYS: ArenaKey[] = [
  { wins: 0, name: 'Novice Key', packs: 0, embers: 15 },
  { wins: 1, name: 'Apprentice Key', packs: 0, embers: 25 },
  { wins: 2, name: 'Journeyman Key', packs: 0, embers: 40 },
  { wins: 3, name: 'Copper Key', packs: 1, embers: 20 },
  { wins: 4, name: 'Silver Key', packs: 1, embers: 35 },
  { wins: 5, name: 'Gold Key', packs: 1, embers: 50 },
  { wins: 6, name: 'Platinum Key', packs: 1, embers: 70 },
  { wins: 7, name: 'Diamond Key', packs: 1, embers: 90 },
  { wins: 8, name: 'Champion Key', packs: 2, embers: 50 },
  { wins: 9, name: 'Ruby Key', packs: 2, embers: 75 },
  { wins: 10, name: 'Frostborn Key', packs: 2, embers: 100 },
  { wins: 11, name: 'Molten Key', packs: 2, embers: 125 },
  { wins: 12, name: 'Lightforge Key', packs: 3, embers: 150 },
];

export function arenaKeyFor(wins: number): ArenaKey {
  const clamped = Math.max(0, Math.min(ARENA_MAX_WINS, Math.floor(wins)));
  return ARENA_KEYS[clamped];
}

export type ArenaPhase = 'picking_hero' | 'drafting' | 'playing' | 'complete';

export interface ArenaHistoryEntry {
  gameId: string;
  opponentClass: string;
  opponentName: string;
  result: 'win' | 'loss' | 'draw';
}

export interface ArenaRun {
  id: string;
  pool: ArenaPoolId;
  phase: ArenaPhase;
  heroChoices: string[];
  heroClass: string | null;
  deck: string[];
  currentChoices: string[];
  wins: number;
  losses: number;
  activeGameId: string | null;
  activeOpponentClass: string | null;
  activeOpponentName: string | null;
  history: ArenaHistoryEntry[];
  claimed: boolean;
  startedAt: number;
}

export interface ArenaStats {
  bestWins: number;
  totalRuns: number;
  totalWins: number;
  twelveWinRuns: number;
}

export interface ArenaState {
  v: 1;
  run: ArenaRun | null;
  stats: ArenaStats;
  preferredOpponent: OpponentMode;
  preferredLevel: string; // 'auto' | 'easy' | 'normal' | 'hard'
}

export function emptyArenaState(): ArenaState {
  return {
    v: 1,
    run: null,
    stats: { bestWins: 0, totalRuns: 0, totalWins: 0, twelveWinRuns: 0 },
    preferredOpponent: 'device',
    preferredLevel: 'auto',
  };
}

export function cardAllowedForClass(card: CardDef, heroClass: string): boolean {
  if (card.classes && card.classes.length > 0) return card.classes.includes(heroClass);
  return card.card_class === heroClass || card.card_class === 'NEUTRAL';
}

export function cardAllowedInArenaPool(card: CardDef, pool: ArenaPoolId): boolean {
  if (!card.collectible) return false;
  if (card.mechanics.includes('QUEST') || card.mechanics.includes('TRIAL')) return false;
  if (pool === 'wild') return true;
  const prefix = card.id.split('_')[0];
  return POOL_PREFIXES[pool].has(prefix);
}

function rarityBucket(card: CardDef): 'COMMON' | 'RARE' | 'EPIC' | 'LEGENDARY' {
  return card.rarity === 'FREE' ? 'COMMON' : card.rarity;
}

export function rollRarity(pickNumber: number, rand: () => number = Math.random): 'COMMON' | 'RARE' | 'EPIC' | 'LEGENDARY' {
  const r = rand();
  if (GUARANTEED_RARE_PICKS.has(pickNumber)) {
    if (r < 0.7) return 'RARE';
    if (r < 0.9) return 'EPIC';
    return 'LEGENDARY';
  }
  if (r < 0.7) return 'COMMON';
  if (r < 0.91) return 'RARE';
  if (r < 0.98) return 'EPIC';
  return 'LEGENDARY';
}

function cardWeight(card: CardDef, heroClass: string): number {
  const isClass = card.card_class === heroClass || Boolean(card.classes?.includes(heroClass));
  let w = isClass ? 2.0 : 1.0;
  if (card.type === 'SPELL' || card.type === 'WEAPON') w *= 1.3;
  return w;
}

export function offerHeroes(heroClasses: string[], rand: () => number = Math.random): string[] {
  const copy = [...heroClasses];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy.slice(0, 3);
}

export function offerArenaPick(
  cards: CardDef[],
  heroClass: string,
  pickNumber: number,
  pool: ArenaPoolId,
  rand: () => number = Math.random,
): string[] {
  const eligible = cards.filter((c) => cardAllowedForClass(c, heroClass) && cardAllowedInArenaPool(c, pool));
  const rarity = rollRarity(pickNumber, rand);
  let bucket = eligible.filter((c) => rarityBucket(c) === rarity);
  if (bucket.length < 3) bucket = eligible;

  const remaining = [...bucket];
  const chosen: string[] = [];
  for (let k = 0; k < 3 && remaining.length > 0; k++) {
    const weights = remaining.map((c) => cardWeight(c, heroClass));
    const total = weights.reduce((a, b) => a + b, 0);
    let roll = rand() * total;
    let pickIdx = remaining.length - 1;
    for (let i = 0; i < remaining.length; i++) {
      roll -= weights[i];
      if (roll <= 0) {
        pickIdx = i;
        break;
      }
    }
    chosen.push(remaining.splice(pickIdx, 1)[0].id);
  }
  return chosen;
}

function scoreArenaCard(card: CardDef, countsByCost: number[]): number {
  const target = [1, 4, 7, 6, 5, 3, 2, 2];
  const bucket = Math.min(7, Math.max(0, card.cost));
  let score = (target[bucket] - countsByCost[bucket]) * 1.4;
  if (card.type === 'MINION') {
    const stats = (card.attack ?? 0) + (card.health ?? 0);
    const expected = card.cost * 2 + 1;
    score += (stats - expected) * 0.9;
    if (card.mechanics.includes('TAUNT') || card.mechanics.includes('DIVINE_SHIELD') || card.mechanics.includes('BATTLECRY')) {
      score += 0.8;
    }
    if (card.mechanics.includes('CANT_ATTACK')) score -= 3.0;
  } else if (card.type === 'WEAPON') {
    score += 2.2;
  } else {
    score += 0.9;
  }
  if (card.card_class !== 'NEUTRAL') score += 0.5;
  return score;
}

/** Draft a 30-card Arena deck for an opponent whose drafting sharpens at higher win counts. */
export function draftOpponentDeck(
  cards: CardDef[],
  heroClasses: string[],
  pool: ArenaPoolId,
  wins: number,
  rand: () => number = Math.random,
): { heroClass: string; cards: string[] } {
  const byId = new Map(cards.map((c) => [c.id, c]));
  const heroClass = heroClasses[Math.floor(rand() * heroClasses.length)] || 'MAGE';
  const deck: string[] = [];
  const countsByCost = [0, 0, 0, 0, 0, 0, 0, 0];
  const noise = Math.max(0.2, 2.8 - wins * 0.22);

  for (let pick = 1; pick <= ARENA_DECK_SIZE; pick++) {
    const opts = offerArenaPick(cards, heroClass, pick, pool, rand);
    let best = opts[0];
    let bestScore = -Infinity;
    for (const cid of opts) {
      const card = byId.get(cid);
      if (!card) continue;
      const sc = scoreArenaCard(card, countsByCost) + (rand() * 2 - 1) * noise;
      if (sc > bestScore) {
        bestScore = sc;
        best = cid;
      }
    }
    if (best) {
      deck.push(best);
      const picked = byId.get(best);
      if (picked) countsByCost[Math.min(7, Math.max(0, picked.cost))]++;
    }
  }
  return { heroClass, cards: deck };
}

/** Recommended on-device AI level for a given win count when set to Auto-scaling. */
export function levelForArenaWins(wins: number, preferredLevel: string): string {
  if (preferredLevel === 'easy' || preferredLevel === 'normal' || preferredLevel === 'hard') return preferredLevel;
  if (wins <= 2) return 'easy';
  if (wins <= 6) return 'normal';
  return 'hard';
}

export function startNewRun(
  heroClasses: string[],
  pool: ArenaPoolId,
  now: number = Date.now(),
  rand: () => number = Math.random,
): ArenaRun {
  return {
    id: `arena_${now.toString(36)}_${Math.floor(rand() * 1e6).toString(36)}`,
    pool,
    phase: 'picking_hero',
    heroChoices: offerHeroes(heroClasses, rand),
    heroClass: null,
    deck: [],
    currentChoices: [],
    wins: 0,
    losses: 0,
    activeGameId: null,
    activeOpponentClass: null,
    activeOpponentName: null,
    history: [],
    claimed: false,
    startedAt: now,
  };
}

export function chooseRunHero(run: ArenaRun, heroClass: string, cards: CardDef[], rand: () => number = Math.random): ArenaRun {
  if (run.phase !== 'picking_hero' || !run.heroChoices.includes(heroClass)) return run;
  return {
    ...run,
    phase: 'drafting',
    heroClass,
    deck: [],
    currentChoices: offerArenaPick(cards, heroClass, 1, run.pool, rand),
  };
}

export function pickDraftCard(run: ArenaRun, cardId: string, cards: CardDef[], rand: () => number = Math.random): ArenaRun {
  if (run.phase !== 'drafting' || !run.heroClass || !run.currentChoices.includes(cardId)) return run;
  const nextDeck = [...run.deck, cardId];
  if (nextDeck.length >= ARENA_DECK_SIZE) {
    return {
      ...run,
      deck: nextDeck,
      currentChoices: [],
      phase: 'playing',
    };
  }
  return {
    ...run,
    deck: nextDeck,
    currentChoices: offerArenaPick(cards, run.heroClass, nextDeck.length + 1, run.pool, rand),
  };
}

export function attachArenaMatch(run: ArenaRun, gameId: string, opponentClass: string, opponentName: string): ArenaRun {
  if (run.phase !== 'playing') return run;
  return {
    ...run,
    activeGameId: gameId,
    activeOpponentClass: opponentClass,
    activeOpponentName: opponentName,
  };
}

export function recordArenaMatchResult(
  run: ArenaRun,
  gameId: string,
  result: 'win' | 'loss' | 'draw',
  opponentClass?: string,
  opponentName?: string,
): ArenaRun {
  if (run.history.some((h) => h.gameId === gameId)) return run;
  if (run.activeGameId && run.activeGameId !== gameId) return run;

  const wins = run.wins + (result === 'win' ? 1 : 0);
  const losses = run.losses + (result === 'loss' ? 1 : 0);
  const done = wins >= ARENA_MAX_WINS || losses >= ARENA_MAX_LOSSES;

  return {
    ...run,
    wins,
    losses,
    phase: done ? 'complete' : run.phase,
    activeGameId: null,
    activeOpponentClass: null,
    activeOpponentName: null,
    history: [
      ...run.history,
      {
        gameId,
        opponentClass: opponentClass || run.activeOpponentClass || 'MAGE',
        opponentName: opponentName || run.activeOpponentName || 'Opponent',
        result,
      },
    ],
  };
}

export function retireArenaRun(run: ArenaRun): ArenaRun {
  if (run.phase === 'complete') return run;
  return {
    ...run,
    phase: 'complete',
    activeGameId: null,
    activeOpponentClass: null,
    activeOpponentName: null,
  };
}

export function claimRunRewards(state: ArenaState): { state: ArenaState; key: ArenaKey } | null {
  const run = state.run;
  if (!run || run.phase !== 'complete' || run.claimed) return null;
  const key = arenaKeyFor(run.wins);
  const stats: ArenaStats = {
    bestWins: Math.max(state.stats.bestWins, run.wins),
    totalRuns: state.stats.totalRuns + 1,
    totalWins: state.stats.totalWins + run.wins,
    twelveWinRuns: state.stats.twelveWinRuns + (run.wins >= ARENA_MAX_WINS ? 1 : 0),
  };
  return {
    key,
    state: {
      ...state,
      stats,
      run: { ...run, claimed: true },
    },
  };
}

export function restoreArenaState(raw: unknown): ArenaState {
  const base = emptyArenaState();
  if (!raw || typeof raw !== 'object') return base;
  const r = raw as Record<string, any>;
  const stats = r.stats && typeof r.stats === 'object'
    ? {
        bestWins: Number(r.stats.bestWins) || 0,
        totalRuns: Number(r.stats.totalRuns) || 0,
        totalWins: Number(r.stats.totalWins) || 0,
        twelveWinRuns: Number(r.stats.twelveWinRuns) || 0,
      }
    : base.stats;
  const preferredOpponent: OpponentMode =
    r.preferredOpponent === 'bot' || r.preferredOpponent === 'agent' || r.preferredOpponent === 'device'
      ? r.preferredOpponent
      : 'device';
  const preferredLevel = typeof r.preferredLevel === 'string' ? r.preferredLevel : 'auto';
  let run: ArenaRun | null = null;
  if (r.run && typeof r.run === 'object' && typeof r.run.id === 'string') {
    const rr = r.run;
    run = {
      id: rr.id,
      pool: ARENA_POOLS.some((p) => p.id === rr.pool) ? rr.pool : 'wild',
      phase:
        rr.phase === 'picking_hero' || rr.phase === 'drafting' || rr.phase === 'playing' || rr.phase === 'complete'
          ? rr.phase
          : 'picking_hero',
      heroChoices: Array.isArray(rr.heroChoices) ? rr.heroChoices.map(String) : [],
      heroClass: typeof rr.heroClass === 'string' ? rr.heroClass : null,
      deck: Array.isArray(rr.deck) ? rr.deck.map(String) : [],
      currentChoices: Array.isArray(rr.currentChoices) ? rr.currentChoices.map(String) : [],
      wins: Number(rr.wins) || 0,
      losses: Number(rr.losses) || 0,
      activeGameId: typeof rr.activeGameId === 'string' ? rr.activeGameId : null,
      activeOpponentClass: typeof rr.activeOpponentClass === 'string' ? rr.activeOpponentClass : null,
      activeOpponentName: typeof rr.activeOpponentName === 'string' ? rr.activeOpponentName : null,
      history: Array.isArray(rr.history) ? rr.history : [],
      claimed: Boolean(rr.claimed),
      startedAt: Number(rr.startedAt) || Date.now(),
    };
  }
  return { v: 1, run, stats, preferredOpponent, preferredLevel };
}
