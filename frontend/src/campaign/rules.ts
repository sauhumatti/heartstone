// Pure Campaign progression, unlocking, mastery, relic, and reward rules (no DOM, no I/O).
import type { OpponentMode } from '../types';
import {
  ALL_CAMPAIGN_BOSSES,
  CAMPAIGN_CHAPTERS,
  CAMPAIGN_RELICS,
  HEROIC_GRAND_REWARD,
  RELIC_BY_ID,
  bossById,
  chapterById,
  type CampaignBoss,
  type CampaignChapter,
  type CampaignDifficulty,
  type CampaignRelic,
  type ChapterReward,
  type RelicId,
} from './data';

export interface ActiveCampaignMatch {
  gameId: string;
  bossId: string;
  difficulty: CampaignDifficulty;
  relicId: RelicId;
  deckId?: string;
}

export interface BossRecord {
  wins: number;
  bestTurns: number | null;
  bestClass: string | null;
}

export interface CampaignState {
  v: 1;
  clearedNormal: string[];
  clearedHeroic: string[];
  /** Bosses defeated with No Relic equipped (Purist feat). */
  clearedPurist: string[];
  claimedChapters: string[];
  claimedHeroicGrand: boolean;
  equippedRelic: RelicId;
  selectedDeckId: string | null;
  difficulty: CampaignDifficulty;
  preferredOpponent: OpponentMode;
  activeMatch: ActiveCampaignMatch | null;
  attempts: Record<string, number>;
  bossRecords: Record<string, BossRecord>;
  seenGames: string[];
}

const KEEP_SEEN = 120;

export function emptyCampaignState(): CampaignState {
  return {
    v: 1,
    clearedNormal: [],
    clearedHeroic: [],
    clearedPurist: [],
    claimedChapters: [],
    claimedHeroicGrand: false,
    equippedRelic: 'none',
    selectedDeckId: null,
    difficulty: 'normal',
    preferredOpponent: 'device',
    activeMatch: null,
    attempts: {},
    bossRecords: {},
    seenGames: [],
  };
}

export function isBossCleared(state: CampaignState, bossId: string, difficulty: CampaignDifficulty = 'normal'): boolean {
  if (difficulty === 'heroic') return state.clearedHeroic.includes(bossId);
  return state.clearedNormal.includes(bossId) || state.clearedHeroic.includes(bossId);
}

export function isBossPurist(state: CampaignState, bossId: string): boolean {
  return state.clearedPurist.includes(bossId);
}

export function isBossUnlocked(state: CampaignState, bossId: string): boolean {
  const idx = ALL_CAMPAIGN_BOSSES.findIndex((b) => b.id === bossId);
  if (idx < 0) return false;
  if (idx === 0) return true;
  const prev = ALL_CAMPAIGN_BOSSES[idx - 1];
  return isBossCleared(state, prev.id, 'normal');
}

export function isChapterUnlocked(state: CampaignState, chapterId: string): boolean {
  const ch = chapterById(chapterId);
  if (!ch || !ch.bosses.length) return false;
  return isBossUnlocked(state, ch.bosses[0].id);
}

export function isChapterCleared(
  state: CampaignState,
  chapterId: string,
  difficulty: CampaignDifficulty = 'normal',
): boolean {
  const ch = chapterById(chapterId);
  if (!ch) return false;
  return ch.bosses.every((b) => isBossCleared(state, b.id, difficulty));
}

export function isHeroicUnlockedForChapter(state: CampaignState, chapterId: string): boolean {
  return isChapterCleared(state, chapterId, 'normal');
}

export function isCampaignComplete(state: CampaignState, difficulty: CampaignDifficulty = 'normal'): boolean {
  return ALL_CAMPAIGN_BOSSES.every((b) => isBossCleared(state, b.id, difficulty));
}

export function unlockedRelics(state: CampaignState): CampaignRelic[] {
  return CAMPAIGN_RELICS.filter((r) => r.unlockChapterId === null || isChapterCleared(state, r.unlockChapterId, 'normal'));
}

export function isRelicUnlocked(state: CampaignState, relicId: RelicId): boolean {
  const relic = RELIC_BY_ID[relicId];
  if (!relic) return false;
  return relic.unlockChapterId === null || isChapterCleared(state, relic.unlockChapterId, 'normal');
}

export function canClaimChapter(state: CampaignState, chapterId: string): boolean {
  return isChapterCleared(state, chapterId, 'normal') && !state.claimedChapters.includes(chapterId);
}

export function canClaimHeroicGrand(state: CampaignState): boolean {
  return isCampaignComplete(state, 'heroic') && !state.claimedHeroicGrand;
}

export function unclaimedChapterCount(state: CampaignState): number {
  let n = CAMPAIGN_CHAPTERS.filter((c) => canClaimChapter(state, c.id)).length;
  if (canClaimHeroicGrand(state)) n += 1;
  return n;
}

export function nextPlayableBoss(state: CampaignState, difficulty: CampaignDifficulty = 'normal'): CampaignBoss {
  if (difficulty === 'heroic') {
    const nextHeroic = ALL_CAMPAIGN_BOSSES.find(
      (b) => isHeroicUnlockedForChapter(state, b.chapterId) && !isBossCleared(state, b.id, 'heroic'),
    );
    if (nextHeroic) return nextHeroic;
  }
  const nextNormal = ALL_CAMPAIGN_BOSSES.find((b) => isBossUnlocked(state, b.id) && !isBossCleared(state, b.id, 'normal'));
  return nextNormal || ALL_CAMPAIGN_BOSSES[ALL_CAMPAIGN_BOSSES.length - 1];
}

export function nextBossAfter(bossId: string): CampaignBoss | null {
  const idx = ALL_CAMPAIGN_BOSSES.findIndex((b) => b.id === bossId);
  if (idx < 0 || idx + 1 >= ALL_CAMPAIGN_BOSSES.length) return null;
  return ALL_CAMPAIGN_BOSSES[idx + 1];
}

export function bossStatsFor(
  boss: CampaignBoss,
  difficulty: CampaignDifficulty,
): {
  hp: number;
  armor: number;
  bonusMana: number;
  level: 'easy' | 'normal' | 'hard';
  passivePower: number;
  passiveText: string;
  openingBoard: string[];
  openingBoardLabel?: string;
} {
  if (difficulty === 'heroic') {
    return {
      hp: boss.heroicHp,
      armor: boss.heroicArmor,
      bonusMana: boss.heroicBonusMana ?? 0,
      level: 'hard',
      passivePower: boss.heroicPassivePower,
      passiveText: boss.heroicPassiveText,
      openingBoard: boss.heroicOpeningBoard ?? boss.openingBoard ?? [],
      openingBoardLabel: boss.heroicOpeningBoardLabel ?? boss.openingBoardLabel,
    };
  }
  return {
    hp: boss.hp,
    armor: boss.armor,
    bonusMana: boss.bonusMana ?? 0,
    level: boss.level,
    passivePower: boss.passivePower,
    passiveText: boss.passiveText,
    openingBoard: boss.openingBoard ?? [],
    openingBoardLabel: boss.openingBoardLabel,
  };
}

export function campaignSummary(state: CampaignState): string {
  const total = ALL_CAMPAIGN_BOSSES.length;
  const normalCount = ALL_CAMPAIGN_BOSSES.filter((b) => isBossCleared(state, b.id, 'normal')).length;
  const heroicCount = ALL_CAMPAIGN_BOSSES.filter((b) => isBossCleared(state, b.id, 'heroic')).length;
  const unclaimed = unclaimedChapterCount(state);

  if (normalCount === 0) return `5 chapters · ${total} unique bosses · unlock Lantern Relics`;
  if (unclaimed > 0) {
    return `${normalCount}/${total} bosses · ${unclaimed} chapter ${unclaimed === 1 ? 'reward' : 'rewards'} ready!`;
  }
  if (heroicCount >= total) return `100% Complete · ${total}/${total} Heroic Crowned`;
  if (normalCount >= total) {
    return heroicCount > 0 ? `Campaign Complete · ${heroicCount}/${total} Heroic` : 'Campaign Complete · Heroic Mode unlocked';
  }
  const next = nextPlayableBoss(state, 'normal');
  const ch: CampaignChapter | undefined = chapterById(next.chapterId);
  return `Chapter ${ch?.roman ?? 'I'} · ${normalCount}/${total} bosses · Next: ${next.name}`;
}

export function attachCampaignMatch(
  state: CampaignState,
  gameId: string,
  bossId: string,
  difficulty: CampaignDifficulty,
  relicId: RelicId,
  deckId?: string,
): CampaignState {
  return {
    ...state,
    activeMatch: { gameId, bossId, difficulty, relicId, deckId },
  };
}

export interface CampaignMatchOutcome {
  state: CampaignState;
  boss: CampaignBoss;
  difficulty: CampaignDifficulty;
  relicId: RelicId;
  deckId?: string;
  won: boolean;
  newlyCleared: boolean;
  puristEarned: boolean;
  nextBoss: CampaignBoss | null;
  chapterJustCompleted: CampaignChapter | null;
  campaignJustCompleted: boolean;
}

export function recordCampaignMatchResult(
  state: CampaignState,
  gameId: string,
  result: 'win' | 'loss' | 'draw',
  meta?: { turnNumber?: number; heroClass?: string },
): CampaignMatchOutcome | null {
  const active = state.activeMatch;
  if (!active || active.gameId !== gameId) return null;
  if (state.seenGames.includes(gameId)) return null;

  const boss = bossById(active.bossId);
  if (!boss) return null;

  const won = result === 'win';
  const wasChapterCleared = isChapterCleared(state, boss.chapterId, 'normal');
  const wasCampaignComplete = isCampaignComplete(state, 'normal');

  const clearedNormal =
    won && !state.clearedNormal.includes(boss.id) ? [...state.clearedNormal, boss.id] : state.clearedNormal;
  const clearedHeroic =
    won && active.difficulty === 'heroic' && !state.clearedHeroic.includes(boss.id)
      ? [...state.clearedHeroic, boss.id]
      : state.clearedHeroic;
  const puristEarned = won && active.relicId === 'none' && !state.clearedPurist.includes(boss.id);
  const clearedPurist = puristEarned ? [...state.clearedPurist, boss.id] : state.clearedPurist;

  const newlyCleared =
    won &&
    (active.difficulty === 'heroic'
      ? !state.clearedHeroic.includes(boss.id)
      : !state.clearedNormal.includes(boss.id));

  const prevRec = state.bossRecords[boss.id] || { wins: 0, bestTurns: null, bestClass: null };
  const turnNum = meta?.turnNumber && meta.turnNumber > 0 ? Math.floor(meta.turnNumber) : null;
  const nextRec: BossRecord = won
    ? {
        wins: prevRec.wins + 1,
        bestTurns: turnNum !== null && (prevRec.bestTurns === null || turnNum < prevRec.bestTurns) ? turnNum : prevRec.bestTurns,
        bestClass: meta?.heroClass || prevRec.bestClass,
      }
    : prevRec;

  const nextState: CampaignState = {
    ...state,
    clearedNormal,
    clearedHeroic,
    clearedPurist,
    activeMatch: null,
    attempts: {
      ...state.attempts,
      [boss.id]: (state.attempts[boss.id] || 0) + 1,
    },
    bossRecords: {
      ...state.bossRecords,
      [boss.id]: nextRec,
    },
    seenGames: [gameId, ...state.seenGames].slice(0, KEEP_SEEN),
  };

  const chapterNowCleared = isChapterCleared(nextState, boss.chapterId, 'normal');
  const chapterJustCompleted = !wasChapterCleared && chapterNowCleared ? chapterById(boss.chapterId) ?? null : null;
  const campaignJustCompleted = !wasCampaignComplete && isCampaignComplete(nextState, 'normal');
  const candidateNext = nextBossAfter(boss.id);
  const nextBoss =
    won &&
    candidateNext &&
    isBossUnlocked(nextState, candidateNext.id) &&
    (active.difficulty === 'normal' || isHeroicUnlockedForChapter(nextState, candidateNext.chapterId))
      ? candidateNext
      : null;

  return {
    state: nextState,
    boss,
    difficulty: active.difficulty,
    relicId: active.relicId,
    deckId: active.deckId,
    won,
    newlyCleared,
    puristEarned,
    nextBoss,
    chapterJustCompleted,
    campaignJustCompleted,
  };
}

export function claimChapterReward(
  state: CampaignState,
  chapterId: string,
): { state: CampaignState; chapter: CampaignChapter; reward: ChapterReward } | null {
  if (!canClaimChapter(state, chapterId)) return null;
  const chapter = chapterById(chapterId);
  if (!chapter) return null;
  const shouldEquip = state.equippedRelic === 'none' || chapter.reward.relicId === 'crown';
  return {
    chapter,
    reward: chapter.reward,
    state: {
      ...state,
      claimedChapters: [...state.claimedChapters, chapterId],
      equippedRelic: shouldEquip ? chapter.reward.relicId : state.equippedRelic,
    },
  };
}

export function claimHeroicGrandReward(
  state: CampaignState,
): { state: CampaignState; reward: typeof HEROIC_GRAND_REWARD } | null {
  if (!canClaimHeroicGrand(state)) return null;
  return {
    reward: HEROIC_GRAND_REWARD,
    state: {
      ...state,
      claimedHeroicGrand: true,
    },
  };
}

export function resetCampaignState(state: CampaignState): CampaignState {
  return {
    ...emptyCampaignState(),
    selectedDeckId: state.selectedDeckId,
    preferredOpponent: state.preferredOpponent,
  };
}

export function restoreCampaignState(raw: unknown): CampaignState {
  const base = emptyCampaignState();
  if (!raw || typeof raw !== 'object') return base;
  const r = raw as Record<string, any>;
  const validBossIds = new Set(ALL_CAMPAIGN_BOSSES.map((b) => b.id));
  const validChapterIds = new Set(CAMPAIGN_CHAPTERS.map((c) => c.id));

  const clearedNormal = Array.isArray(r.clearedNormal)
    ? Array.from(new Set(r.clearedNormal.filter((id: unknown): id is string => typeof id === 'string' && validBossIds.has(id))))
    : [];
  const clearedHeroic = Array.isArray(r.clearedHeroic)
    ? Array.from(new Set(r.clearedHeroic.filter((id: unknown): id is string => typeof id === 'string' && validBossIds.has(id))))
    : [];
  const clearedPurist = Array.isArray(r.clearedPurist)
    ? Array.from(new Set(r.clearedPurist.filter((id: unknown): id is string => typeof id === 'string' && validBossIds.has(id))))
    : [];
  const claimedChapters = Array.isArray(r.claimedChapters)
    ? Array.from(new Set(r.claimedChapters.filter((id: unknown): id is string => typeof id === 'string' && validChapterIds.has(id))))
    : [];
  const equippedRelic: RelicId =
    typeof r.equippedRelic === 'string' && r.equippedRelic in RELIC_BY_ID ? (r.equippedRelic as RelicId) : 'none';
  const difficulty: CampaignDifficulty = r.difficulty === 'heroic' ? 'heroic' : 'normal';
  const preferredOpponent: OpponentMode =
    r.preferredOpponent === 'bot' || r.preferredOpponent === 'agent' || r.preferredOpponent === 'device'
      ? r.preferredOpponent
      : 'device';

  let activeMatch: ActiveCampaignMatch | null = null;
  if (r.activeMatch && typeof r.activeMatch === 'object' && typeof r.activeMatch.gameId === 'string' && validBossIds.has(r.activeMatch.bossId)) {
    activeMatch = {
      gameId: r.activeMatch.gameId,
      bossId: r.activeMatch.bossId,
      difficulty: r.activeMatch.difficulty === 'heroic' ? 'heroic' : 'normal',
      relicId: typeof r.activeMatch.relicId === 'string' && r.activeMatch.relicId in RELIC_BY_ID ? r.activeMatch.relicId : 'none',
      deckId: typeof r.activeMatch.deckId === 'string' ? r.activeMatch.deckId : undefined,
    };
  }

  const attempts: Record<string, number> = {};
  if (r.attempts && typeof r.attempts === 'object') {
    for (const [k, v] of Object.entries(r.attempts)) {
      if (validBossIds.has(k) && typeof v === 'number' && Number.isFinite(v) && v >= 0) attempts[k] = Math.floor(v);
    }
  }

  const bossRecords: Record<string, BossRecord> = {};
  if (r.bossRecords && typeof r.bossRecords === 'object') {
    for (const [k, v] of Object.entries(r.bossRecords)) {
      if (validBossIds.has(k) && v && typeof v === 'object') {
        const rec = v as Record<string, any>;
        bossRecords[k] = {
          wins: typeof rec.wins === 'number' && Number.isFinite(rec.wins) && rec.wins >= 0 ? Math.floor(rec.wins) : 0,
          bestTurns: typeof rec.bestTurns === 'number' && Number.isFinite(rec.bestTurns) && rec.bestTurns > 0 ? Math.floor(rec.bestTurns) : null,
          bestClass: typeof rec.bestClass === 'string' ? rec.bestClass : null,
        };
      }
    }
  }

  const seenGames = Array.isArray(r.seenGames)
    ? r.seenGames.filter((id: unknown): id is string => typeof id === 'string').slice(0, KEEP_SEEN)
    : [];

  const next: CampaignState = {
    v: 1,
    clearedNormal,
    clearedHeroic,
    clearedPurist,
    claimedChapters,
    claimedHeroicGrand: Boolean(r.claimedHeroicGrand),
    equippedRelic,
    selectedDeckId: typeof r.selectedDeckId === 'string' ? r.selectedDeckId : null,
    difficulty,
    preferredOpponent,
    activeMatch,
    attempts,
    bossRecords,
    seenGames,
  };
  if (!isRelicUnlocked(next, next.equippedRelic)) next.equippedRelic = 'none';
  return next;
}
