// What a player earns by playing: a rating, a rank, and packs of things to wear.
// Everything here is a pure function of a profile; where the profile is kept is
// store.ts's business, and the pictures are art.ts's. Nothing here knows a card.

export const START_RATING = 1000;
export const RATING_FLOOR = 100;
/** Wins needed to fill the meter that gives a pack. */
export const PACK_STEPS = 3;
/** What a pack holds. */
export const PACK_SIZE = 3;

// ---- opponents ------------------------------------------------------------------------------

export type OpponentKind = 'easy' | 'normal' | 'hard' | 'bot' | 'agent';

/**
 * How strong each opponent is taken to be, and how far a win over it moves the pack meter.
 * The spacing follows scripts/ai_arena.py: the hard level beats the normal one about two
 * times in three, the practice bot is a little stronger than the easy level, and the normal
 * level almost never loses to the easy one.
 */
export const OPPONENTS: Record<OpponentKind, { name: string; rating: number; steps: number }> = {
  easy: { name: 'Easy', rating: 800, steps: 1 },
  bot: { name: 'Practice bot', rating: 875, steps: 1 },
  normal: { name: 'Normal', rating: 1150, steps: 1 },
  agent: { name: 'Agent', rating: 1200, steps: 1 },
  hard: { name: 'Hard', rating: 1300, steps: 2 },
};

/**
 * Who a match was against, for the rating. `mode` is the match's mode as the engine names it,
 * `level` the on-device opponent's level. A match against the command line is not rated: the
 * other seat is whoever types.
 */
export function opponentOf(mode: string, level?: string | null): OpponentKind | null {
  if (mode === 'ai_vs_human') return level === 'easy' || level === 'hard' ? level : 'normal';
  if (mode === 'bot_vs_human') return 'bot';
  if (mode === 'agent_vs_human') return 'agent';
  return null;
}

/** Of two opponents met in one match (it can change hands midway), the one that counts: the weaker. */
export function weakerOf(a: OpponentKind | null, b: OpponentKind | null): OpponentKind | null {
  if (a === null || b === null) return null;
  return OPPONENTS[a].rating <= OPPONENTS[b].rating ? a : b;
}

// ---- rating ---------------------------------------------------------------------------------

export type Result = 'win' | 'loss' | 'draw';

const SCORE: Record<Result, number> = { win: 1, draw: 0.5, loss: 0 };

/** The share of points a player rated `own` is expected to take from one rated `other`. */
export function expectedScore(own: number, other: number): number {
  return 1 / (1 + Math.pow(10, (other - own) / 400));
}

/** How far one match can move a rating: more while the rating is still finding its place. */
export function kFactor(played: number): number {
  return played < 10 ? 40 : 24;
}

export function nextRating(rating: number, other: number, result: Result, played: number): number {
  const moved = rating + kFactor(played) * (SCORE[result] - expectedScore(rating, other));
  return Math.max(RATING_FLOOR, Math.round(moved * 100) / 100);
}

// ---- ranks ----------------------------------------------------------------------------------

export interface Rank {
  id: string;
  name: string;
  /** The rating it starts at. */
  min: number;
}

// A new player starts in the middle of the third rank, so a first loss costs no rank.
export const RANKS: Rank[] = [
  { id: 'spark', name: 'Spark', min: 0 },
  { id: 'wick', name: 'Wick', min: 850 },
  { id: 'candle', name: 'Candle', min: 950 },
  { id: 'lamp', name: 'Lamp', min: 1050 },
  { id: 'lantern', name: 'Lantern', min: 1150 },
  { id: 'beacon', name: 'Beacon', min: 1250 },
  { id: 'lighthouse', name: 'Lighthouse', min: 1350 },
  { id: 'daystar', name: 'Daystar', min: 1450 },
];

export function rankIndex(rating: number): number {
  let at = 0;
  for (let i = 0; i < RANKS.length; i++) if (rating >= RANKS[i].min) at = i;
  return at;
}

export interface RankProgress {
  index: number;
  rank: Rank;
  next: Rank | null;
  /** How far through this rank the rating is, 0 to 1 (1 at the top rank). */
  fraction: number;
  /** Rating points to the next rank, rounded up; 0 at the top. */
  toNext: number;
}

export function rankProgress(rating: number): RankProgress {
  const index = rankIndex(rating);
  const rank = RANKS[index];
  const next = RANKS[index + 1] ?? null;
  if (!next) return { index, rank, next, fraction: 1, toNext: 0 };
  // The lowest rank has no floor of its own: it is measured over the last stretch below the next.
  const from = index === 0 ? next.min - 100 : rank.min;
  const fraction = Math.max(0, Math.min(1, (rating - from) / (next.min - from)));
  return { index, rank, next, fraction, toNext: Math.max(1, Math.ceil(next.min - rating)) };
}

// ---- things to wear -------------------------------------------------------------------------

export type CosmeticKind = 'back' | 'table' | 'title';
export type Tier = 'paper' | 'glass' | 'gilt';

/**
 * The three kinds of find. `weight` is how often a place in a pack goes to the tier (out of
 * 100), `embers` what a second copy turns into, `price` what one costs in embers.
 */
export const TIERS: Record<Tier, { name: string; weight: number; embers: number; price: number }> = {
  paper: { name: 'Paper', weight: 60, embers: 5, price: 30 },
  glass: { name: 'Glass', weight: 30, embers: 10, price: 60 },
  gilt: { name: 'Gilded', weight: 10, embers: 25, price: 120 },
};

export interface Cosmetic {
  id: string;
  kind: CosmeticKind;
  name: string;
  /** Absent on the three every player starts with. */
  tier?: Tier;
}

export const DEFAULT_WORN: Record<CosmeticKind, string> = { back: 'back_default', table: 'table_default', title: 'title_none' };

export const COSMETICS: Cosmetic[] = [
  { id: 'back_default', kind: 'back', name: 'Lantern Diamond' },
  { id: 'back_ember', kind: 'back', name: 'Ember Lattice', tier: 'paper' },
  { id: 'back_moth', kind: 'back', name: 'Moth Wing', tier: 'paper' },
  { id: 'back_tide', kind: 'back', name: 'Tidewater', tier: 'paper' },
  { id: 'back_moss', kind: 'back', name: 'Fern and Brass', tier: 'paper' },
  { id: 'back_ink', kind: 'back', name: 'Inkwell', tier: 'paper' },
  { id: 'back_crane', kind: 'back', name: 'Paper Crane', tier: 'glass' },
  { id: 'back_frost', kind: 'back', name: 'Frost Glass', tier: 'glass' },
  { id: 'back_coil', kind: 'back', name: 'Copper Works', tier: 'glass' },
  { id: 'back_bloom', kind: 'back', name: 'Night Bloom', tier: 'glass' },
  { id: 'back_chart', kind: 'back', name: 'Star Chart', tier: 'gilt' },
  { id: 'back_dawn', kind: 'back', name: 'Daybreak', tier: 'gilt' },

  { id: 'table_default', kind: 'table', name: 'Night Felt' },
  { id: 'table_oak', kind: 'table', name: 'Old Oak', tier: 'paper' },
  { id: 'table_slate', kind: 'table', name: 'Slate', tier: 'paper' },
  { id: 'table_sand', kind: 'table', name: 'Raked Sand', tier: 'glass' },
  { id: 'table_moss', kind: 'table', name: 'Moss Stone', tier: 'glass' },
  { id: 'table_velvet', kind: 'table', name: 'Wine Velvet', tier: 'gilt' },

  { id: 'title_none', kind: 'title', name: 'No title' },
  { id: 'title_lamplighter', kind: 'title', name: 'Lamplighter', tier: 'paper' },
  { id: 'title_night_owl', kind: 'title', name: 'Night Owl', tier: 'paper' },
  { id: 'title_wick_trimmer', kind: 'title', name: 'Wick Trimmer', tier: 'paper' },
  { id: 'title_moth_friend', kind: 'title', name: 'Friend of Moths', tier: 'paper' },
  { id: 'title_early_riser', kind: 'title', name: 'Early Riser', tier: 'paper' },
  { id: 'title_regular', kind: 'title', name: 'Table Regular', tier: 'paper' },
  { id: 'title_flame_keeper', kind: 'title', name: 'Keeper of the Flame', tier: 'glass' },
  { id: 'title_lantern_bearer', kind: 'title', name: 'Lantern Bearer', tier: 'glass' },
  { id: 'title_storm_lamp', kind: 'title', name: 'Storm Lamp', tier: 'glass' },
  { id: 'title_scholar', kind: 'title', name: 'Midnight Scholar', tier: 'glass' },
  { id: 'title_first_light', kind: 'title', name: 'First Light', tier: 'gilt' },
  { id: 'title_harbour_light', kind: 'title', name: 'Harbour Light', tier: 'gilt' },
];

const BY_ID = new Map(COSMETICS.map((c) => [c.id, c]));

export function cosmetic(id: string): Cosmetic | undefined {
  return BY_ID.get(id);
}

/** Everything a pack can hold. */
export const FINDABLE: Cosmetic[] = COSMETICS.filter((c) => c.tier);

// ---- the profile ----------------------------------------------------------------------------

/** One rated match, as the result screen and the history show it. */
export interface MatchRecord {
  id: string;
  at: number;
  opponent: OpponentKind;
  result: Result;
  before: number;
  after: number;
  rankBefore: number;
  rankAfter: number;
  /** A rank reached for the first time. */
  newBest: boolean;
  meterBefore: number;
  meterAfter: number;
  /** Steps the win added to the pack meter. */
  steps: number;
  /** Packs this match gave (a full meter, a new best rank). */
  packs: number;
}

export interface Profile {
  v: 1;
  createdAt: number;
  rating: number;
  played: number;
  wins: number;
  losses: number;
  draws: number;
  /** Wins in a row, now. */
  streak: number;
  /** The highest rank reached, as an index into RANKS. */
  bestRank: number;
  /** Steps on the pack meter, below PACK_STEPS. */
  meter: number;
  /** Packs not opened yet. */
  packs: number;
  opened: number;
  embers: number;
  /** Ids of what has been found (the three everyone has are not listed). */
  owned: string[];
  worn: Record<CosmeticKind, string>;
  /** The last rated matches, newest first. */
  matches: MatchRecord[];
  /** Ids of matches already counted, newest first: a match is counted once. */
  seen: string[];
}

const KEEP_MATCHES = 40;
const KEEP_SEEN = 400;

export function newProfile(now: number): Profile {
  return {
    v: 1,
    createdAt: now,
    rating: START_RATING,
    played: 0,
    wins: 0,
    losses: 0,
    draws: 0,
    streak: 0,
    bestRank: rankIndex(START_RATING),
    meter: 0,
    packs: 0,
    opened: 0,
    embers: 0,
    owned: [],
    worn: { ...DEFAULT_WORN },
    matches: [],
    seen: [],
  };
}

const num = (v: unknown, fallback: number, min = 0, max = Number.MAX_SAFE_INTEGER): number =>
  typeof v === 'number' && Number.isFinite(v) ? Math.max(min, Math.min(max, v)) : fallback;

export function owns(p: Profile, id: string): boolean {
  const c = BY_ID.get(id);
  return Boolean(c) && (!c!.tier || p.owned.includes(id));
}

/**
 * A profile read back from the device, made whole: anything missing or of the wrong shape
 * falls back to a fresh profile's value, so an old or damaged one never breaks the game.
 */
export function restore(raw: unknown, now: number): Profile {
  const fresh = newProfile(now);
  if (!raw || typeof raw !== 'object') return fresh;
  const r = raw as Record<string, unknown>;
  const rating = num(r.rating, fresh.rating, RATING_FLOOR, 4000);
  const owned = Array.isArray(r.owned) ? Array.from(new Set(r.owned.filter((id): id is string => typeof id === 'string' && Boolean(BY_ID.get(id)?.tier)))) : [];
  const p: Profile = {
    v: 1,
    createdAt: num(r.createdAt, now),
    rating,
    played: Math.floor(num(r.played, 0)),
    wins: Math.floor(num(r.wins, 0)),
    losses: Math.floor(num(r.losses, 0)),
    draws: Math.floor(num(r.draws, 0)),
    streak: Math.floor(num(r.streak, 0)),
    bestRank: Math.floor(num(r.bestRank, rankIndex(rating), rankIndex(Math.max(rating, START_RATING)), RANKS.length - 1)),
    meter: Math.floor(num(r.meter, 0, 0, PACK_STEPS - 1)),
    packs: Math.floor(num(r.packs, 0, 0, 999)),
    opened: Math.floor(num(r.opened, 0)),
    embers: Math.floor(num(r.embers, 0)),
    owned,
    worn: { ...DEFAULT_WORN },
    matches: Array.isArray(r.matches) ? (r.matches.filter((m) => m && typeof m === 'object' && typeof (m as MatchRecord).id === 'string') as MatchRecord[]).slice(0, KEEP_MATCHES) : [],
    seen: Array.isArray(r.seen) ? r.seen.filter((id): id is string => typeof id === 'string').slice(0, KEEP_SEEN) : [],
  };
  const worn = (r.worn && typeof r.worn === 'object' ? r.worn : {}) as Record<string, unknown>;
  for (const kind of Object.keys(DEFAULT_WORN) as CosmeticKind[]) {
    const id = worn[kind];
    if (typeof id === 'string' && BY_ID.get(id)?.kind === kind && owns(p, id)) p.worn[kind] = id;
  }
  return p;
}

// ---- a finished match -----------------------------------------------------------------------

export interface FinishedMatch {
  id: string;
  opponent: OpponentKind;
  result: Result;
  /** When it was counted, in milliseconds. */
  at: number;
}

/**
 * Counts a finished match: the rating moves, a win moves the pack meter, a full meter and a
 * rank reached for the first time each give a pack. A match already counted changes nothing
 * and answers the record made the first time (or none, once that is forgotten).
 */
export function recordMatch(p: Profile, m: FinishedMatch): { profile: Profile; record: MatchRecord | null } {
  if (p.seen.includes(m.id)) return { profile: p, record: p.matches.find((r) => r.id === m.id) ?? null };

  const other = OPPONENTS[m.opponent];
  const after = nextRating(p.rating, other.rating, m.result, p.played);
  const rankBefore = rankIndex(p.rating);
  const rankAfter = rankIndex(after);
  const newBest = rankAfter > p.bestRank;
  const steps = m.result === 'win' ? other.steps : 0;
  const filled = p.meter + steps;
  const packs = Math.floor(filled / PACK_STEPS) + (newBest ? 1 : 0);
  const record: MatchRecord = {
    id: m.id,
    at: m.at,
    opponent: m.opponent,
    result: m.result,
    before: p.rating,
    after,
    rankBefore,
    rankAfter,
    newBest,
    meterBefore: p.meter,
    meterAfter: filled % PACK_STEPS,
    steps,
    packs,
  };
  const profile: Profile = {
    ...p,
    rating: after,
    played: p.played + 1,
    wins: p.wins + (m.result === 'win' ? 1 : 0),
    losses: p.losses + (m.result === 'loss' ? 1 : 0),
    draws: p.draws + (m.result === 'draw' ? 1 : 0),
    streak: m.result === 'win' ? p.streak + 1 : 0,
    bestRank: Math.max(p.bestRank, rankAfter),
    meter: filled % PACK_STEPS,
    packs: p.packs + packs,
    matches: [record, ...p.matches].slice(0, KEEP_MATCHES),
    seen: [m.id, ...p.seen].slice(0, KEEP_SEEN),
  };
  return { profile, record };
}

/** A match that is not to be counted (it ended before this profile began, say) is only remembered. */
export function skipMatch(p: Profile, id: string): Profile {
  return p.seen.includes(id) ? p : { ...p, seen: [id, ...p.seen].slice(0, KEEP_SEEN) };
}

// ---- packs ----------------------------------------------------------------------------------

export interface Find {
  id: string;
  /** Not owned before this pack. */
  isNew: boolean;
  /** What a second copy turned into. */
  embers: number;
}

/** One thing from `pool`: first the tier, by the tiers' weights, then any one thing of that tier. */
function draw(pool: Cosmetic[], rng: () => number): Cosmetic {
  const tiers = (Object.keys(TIERS) as Tier[]).filter((tier) => pool.some((c) => c.tier === tier));
  const total = tiers.reduce((sum, tier) => sum + TIERS[tier].weight, 0);
  let at = rng() * total;
  let tier = tiers[tiers.length - 1];
  for (const one of tiers) {
    at -= TIERS[one].weight;
    if (at < 0) {
      tier = one;
      break;
    }
  }
  const of = pool.filter((c) => c.tier === tier);
  return of[Math.min(of.length - 1, Math.floor(rng() * of.length))];
}

/**
 * Opens one pack: three different things, each drawn tier first. While something is
 * still missing, at least one of the three is new; a thing already owned becomes embers.
 * `rng` answers numbers from 0 up to (not including) 1. With no pack to open, nothing happens.
 */
export function openPack(p: Profile, rng: () => number): { profile: Profile; finds: Find[] } {
  if (p.packs < 1) return { profile: p, finds: [] };
  const picked: Cosmetic[] = [];
  while (picked.length < PACK_SIZE) {
    picked.push(draw(FINDABLE.filter((c) => !picked.includes(c)), rng));
  }
  const missing = FINDABLE.filter((c) => !p.owned.includes(c.id));
  if (missing.length && !picked.some((c) => missing.includes(c))) {
    picked[Math.floor(rng() * PACK_SIZE) % PACK_SIZE] = draw(missing, rng);
  }
  const finds: Find[] = picked.map((c) => {
    const isNew = !p.owned.includes(c.id);
    return { id: c.id, isNew, embers: isNew ? 0 : TIERS[c.tier!].embers };
  });
  return {
    profile: {
      ...p,
      packs: p.packs - 1,
      opened: p.opened + 1,
      embers: p.embers + finds.reduce((sum, f) => sum + f.embers, 0),
      owned: [...p.owned, ...finds.filter((f) => f.isNew).map((f) => f.id)],
    },
    finds,
  };
}

/** What a missing thing costs in embers; null for what cannot be bought (owned, or unknown). */
export function priceOf(p: Profile, id: string): number | null {
  const c = BY_ID.get(id);
  return c?.tier && !p.owned.includes(id) ? TIERS[c.tier].price : null;
}

/** Buys a missing thing with embers. Without enough, or for something owned, nothing happens. */
export function buy(p: Profile, id: string): Profile {
  const price = priceOf(p, id);
  if (price === null || p.embers < price) return p;
  return { ...p, embers: p.embers - price, owned: [...p.owned, id] };
}

/** Puts on something owned. */
export function wear(p: Profile, id: string): Profile {
  const c = BY_ID.get(id);
  if (!c || !owns(p, id) || p.worn[c.kind] === id) return p;
  return { ...p, worn: { ...p.worn, [c.kind]: id } };
}

/** The title as shown beside a name: nothing for "no title". */
export function titleText(p: Profile): string {
  const c = BY_ID.get(p.worn.title);
  return c && c.tier ? c.name : '';
}

/** Grants packs and embers earned from a completed Arena run. */
export function grantArenaReward(p: Profile, packs: number, embers: number): Profile {
  const addPacks = Math.max(0, Math.floor(packs));
  const addEmbers = Math.max(0, Math.floor(embers));
  if (addPacks === 0 && addEmbers === 0) return p;
  return {
    ...p,
    packs: p.packs + addPacks,
    embers: p.embers + addEmbers,
  };
}

/** Grants packs, embers, and an optional guaranteed cosmetic earned from clearing a Campaign chapter. */
export function grantCampaignReward(p: Profile, packs: number, embers: number, cosmeticId?: string): Profile {
  let addPacks = Math.max(0, Math.floor(packs));
  let addEmbers = Math.max(0, Math.floor(embers));
  let owned = p.owned;
  let worn = p.worn;
  if (cosmeticId) {
    const item = BY_ID.get(cosmeticId);
    if (item && item.tier) {
      if (!p.owned.includes(cosmeticId)) {
        owned = [...p.owned, cosmeticId];
        if (item.kind === 'title' && p.worn.title === DEFAULT_WORN.title) {
          worn = { ...p.worn, title: cosmeticId };
        }
      } else {
        addEmbers += TIERS[item.tier].embers;
      }
    }
  }
  if (addPacks === 0 && addEmbers === 0 && owned === p.owned && worn === p.worn) return p;
  return {
    ...p,
    packs: p.packs + addPacks,
    embers: p.embers + addEmbers,
    owned,
    worn,
  };
}

/** How a rating change reads: whole points, or one decimal when it is less than a point. */
export function formatDelta(before: number, after: number): string {
  const d = after - before;
  const shown = Math.abs(d) >= 1 || d === 0 ? String(Math.round(Math.abs(d))) : Math.abs(d).toFixed(1);
  return `${d < 0 ? '−' : '+'}${shown}`;
}
