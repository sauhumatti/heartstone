import React, { useEffect, useMemo, useState } from 'react';
import { fetchAgentInfo } from '../api';
import {
  ALL_CAMPAIGN_BOSSES,
  CAMPAIGN_CHAPTERS,
  CAMPAIGN_RELICS,
  HEROIC_GRAND_REWARD,
  RELIC_BY_ID,
  bossById,
  chapterById,
  type CampaignBoss,
  type CampaignDifficulty,
  type RelicId,
} from '../campaign/data';
import {
  bossStatsFor,
  canClaimChapter,
  canClaimHeroicGrand,
  claimChapterReward,
  claimHeroicGrandReward,
  isBossCleared,
  isBossPurist,
  isBossUnlocked,
  isCampaignComplete,
  isChapterCleared,
  isChapterUnlocked,
  isHeroicUnlockedForChapter,
  isRelicUnlocked,
  nextPlayableBoss,
  resetCampaignState,
} from '../campaign/rules';
import { updateCampaignState, useCampaignState } from '../campaign/store';
import { grantCampaignReward } from '../progress/rules';
import { updateProfile, useProfile } from '../progress/store';
import { sfx } from '../sound';
import type { AgentInfo, CardDef, DeckInfo, GameSummary, HeroMeta, OpponentMode } from '../types';
import { Art, classColor, pretty } from './pieces';

interface CampaignProps {
  heroes: Record<string, HeroMeta>;
  cards: CardDef[];
  decks: DeckInfo[];
  games: GameSummary[];
  serverUp: boolean;
  onStartBoss: (opts: {
    boss: CampaignBoss;
    difficulty: CampaignDifficulty;
    relicId: RelicId;
    deck: DeckInfo;
    p2Mode: OpponentMode;
    agentModel?: string;
  }) => Promise<void>;
  onResumeMatch: (gameId: string) => Promise<void>;
  onOpenDeckbuilder: () => void;
  onOpenPack: () => void;
  onBack: () => void;
}

interface RewardNotice {
  title: string;
  packs: number;
  embers: number;
  relicName?: string;
  cosmeticName?: string;
}

const LEVEL_LABEL: Record<'easy' | 'normal' | 'hard', string> = {
  easy: 'Apprentice AI',
  normal: 'Adept AI',
  hard: 'Master AI',
};

export const Campaign: React.FC<CampaignProps> = ({
  heroes,
  cards,
  decks,
  games,
  serverUp,
  onStartBoss,
  onResumeMatch,
  onOpenDeckbuilder,
  onOpenPack,
  onBack,
}) => {
  const campaign = useCampaignState();
  const profile = useProfile();

  const initialFocus = useMemo(() => {
    const claimableCh = CAMPAIGN_CHAPTERS.find((c) => canClaimChapter(campaign, c.id));
    if (claimableCh) return { chapterId: claimableCh.id, bossId: claimableCh.bosses[claimableCh.bosses.length - 1].id };
    const next = nextPlayableBoss(campaign, campaign.difficulty);
    return { chapterId: next.chapterId, bossId: next.id };
  }, []);

  const [chapterId, setChapterId] = useState<string>(initialFocus.chapterId);
  const [bossId, setBossId] = useState<string>(initialFocus.bossId);
  const [deckFilter, setDeckFilter] = useState<'all' | 'custom' | 'classic' | 'expansion'>('all');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [rewardNotice, setRewardNotice] = useState<RewardNotice | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [agentInfo, setAgentInfo] = useState<AgentInfo | null>(null);

  useEffect(() => {
    if (!serverUp) {
      setAgentInfo(null);
      return;
    }
    fetchAgentInfo()
      .then((info) => setAgentInfo(info))
      .catch(() => setAgentInfo(null));
  }, [serverUp]);

  const cardById = useMemo(() => {
    const m: Record<string, CardDef> = {};
    for (const c of cards) m[c.id] = c;
    return m;
  }, [cards]);

  const chapter = chapterById(chapterId) || CAMPAIGN_CHAPTERS[0];
  const boss = bossById(bossId) || chapter.bosses[0];

  const heroicUnlocked = isHeroicUnlockedForChapter(campaign, chapter.id);
  const activeDifficulty: CampaignDifficulty = campaign.difficulty === 'heroic' && heroicUnlocked ? 'heroic' : 'normal';
  const bossUnlocked = isBossUnlocked(campaign, boss.id);
  const bossClearedNormal = isBossCleared(campaign, boss.id, 'normal');
  const bossClearedHeroic = isBossCleared(campaign, boss.id, 'heroic');
  const bossPurist = isBossPurist(campaign, boss.id);
  const stats = bossStatsFor(boss, activeDifficulty);

  const normalClearedCount = useMemo(
    () => ALL_CAMPAIGN_BOSSES.filter((b) => isBossCleared(campaign, b.id, 'normal')).length,
    [campaign],
  );
  const heroicClearedCount = useMemo(
    () => ALL_CAMPAIGN_BOSSES.filter((b) => isBossCleared(campaign, b.id, 'heroic')).length,
    [campaign],
  );
  const puristCount = campaign.clearedPurist.length;
  const campaignCompleted = isCampaignComplete(campaign, 'normal');
  const heroicCompleted = isCampaignComplete(campaign, 'heroic');
  const progressPct = Math.round((normalClearedCount / ALL_CAMPAIGN_BOSSES.length) * 100);

  // Deck list grouping & selection
  const customDecks = useMemo(() => decks.filter((d) => !d.builtin), [decks]);
  const classicDecks = useMemo(() => decks.filter((d) => d.builtin && d.era === 'classic'), [decks]);
  const expansionDecks = useMemo(() => decks.filter((d) => d.builtin && d.era !== 'classic'), [decks]);

  const visibleDecks = useMemo(() => {
    if (deckFilter === 'custom') return customDecks.length ? customDecks : decks;
    if (deckFilter === 'classic') return classicDecks.length ? classicDecks : decks;
    if (deckFilter === 'expansion') return expansionDecks.length ? expansionDecks : decks;
    return [...customDecks, ...classicDecks, ...expansionDecks];
  }, [deckFilter, customDecks, classicDecks, expansionDecks, decks]);

  const selectedDeck: DeckInfo | undefined = useMemo(() => {
    if (campaign.selectedDeckId) {
      const found = decks.find((d) => d.id === campaign.selectedDeckId);
      if (found) return found;
    }
    return customDecks[0] || classicDecks[0] || decks[0];
  }, [campaign.selectedDeckId, decks, customDecks, classicDecks]);

  const recommendedDeck = useMemo(
    () => decks.find((d) => d.id === boss.recommendedDeckId),
    [decks, boss.recommendedDeckId],
  );

  const activeLiveGame = useMemo(() => {
    if (!campaign.activeMatch) return null;
    const g = games.find((x) => x.game_id === campaign.activeMatch?.gameId && x.phase !== 'GAME_OVER');
    return g ? { game: g, meta: campaign.activeMatch } : null;
  }, [campaign.activeMatch, games]);

  const bossDeck = useMemo(() => decks.find((d) => d.id === boss.deckId), [decks, boss.deckId]);
  const signatureCards = useMemo(
    () => boss.signatureCards.map((cid) => cardById[cid]).filter((c): c is CardDef => Boolean(c)),
    [boss.signatureCards, cardById],
  );

  const effectiveMode: OpponentMode =
    !serverUp
      ? 'device'
      : campaign.preferredOpponent === 'agent' && !agentInfo?.available
        ? 'device'
        : campaign.preferredOpponent;

  const selectChapter = (nextChapterId: string) => {
    const ch = chapterById(nextChapterId);
    if (!ch) return;
    setChapterId(nextChapterId);
    const target = ch.bosses.find((b) => isBossUnlocked(campaign, b.id) && !isBossCleared(campaign, b.id, 'normal')) || ch.bosses[0];
    setBossId(target.id);
    setErr('');
  };

  const handleEquipRelic = (relicId: RelicId) => {
    if (!isRelicUnlocked(campaign, relicId)) return;
    sfx.uiClick();
    updateCampaignState((cur) => ({ ...cur, equippedRelic: relicId }));
  };

  const handleSetDifficulty = (diff: CampaignDifficulty) => {
    if (diff === 'heroic' && !heroicUnlocked) return;
    sfx.uiClick();
    updateCampaignState((cur) => ({ ...cur, difficulty: diff }));
  };

  const handleClaimChapter = (cid: string) => {
    let claimed: ReturnType<typeof claimChapterReward> = null;
    updateCampaignState((cur) => {
      claimed = claimChapterReward(cur, cid);
      return claimed ? claimed.state : cur;
    });
    if (!claimed) return;
    const { chapter: ch, reward } = claimed as NonNullable<ReturnType<typeof claimChapterReward>>;
    updateProfile((p) => grantCampaignReward(p, reward.packs, reward.embers, reward.cosmeticId));
    sfx.cue('victory');
    setRewardNotice({
      title: `Chapter ${ch.roman} Cleared — ${ch.title}`,
      packs: reward.packs,
      embers: reward.embers,
      relicName: RELIC_BY_ID[reward.relicId]?.name,
      cosmeticName: reward.cosmeticName,
    });
  };

  const handleClaimHeroicGrand = () => {
    let claimed: ReturnType<typeof claimHeroicGrandReward> = null;
    updateCampaignState((cur) => {
      claimed = claimHeroicGrandReward(cur);
      return claimed ? claimed.state : cur;
    });
    if (!claimed) return;
    updateProfile((p) => grantCampaignReward(p, HEROIC_GRAND_REWARD.packs, HEROIC_GRAND_REWARD.embers));
    sfx.cue('victory');
    setRewardNotice({
      title: 'Heroic Campaign Conquered!',
      packs: HEROIC_GRAND_REWARD.packs,
      embers: HEROIC_GRAND_REWARD.embers,
    });
  };

  const handleLaunch = async () => {
    if (!bossUnlocked || !selectedDeck) return;
    setBusy(true);
    setErr('');
    try {
      const relicId = isRelicUnlocked(campaign, campaign.equippedRelic) ? campaign.equippedRelic : 'none';
      await onStartBoss({
        boss,
        difficulty: activeDifficulty,
        relicId,
        deck: selectedDeck,
        p2Mode: effectiveMode,
        agentModel: effectiveMode === 'agent' ? agentInfo?.default : undefined,
      });
    } catch (e: any) {
      setErr(e?.message || 'Could not start boss encounter.');
    } finally {
      setBusy(false);
    }
  };

  const activeRelic = RELIC_BY_ID[isRelicUnlocked(campaign, campaign.equippedRelic) ? campaign.equippedRelic : 'none'];
  const chapterClaimable = canClaimChapter(campaign, chapter.id);
  const chapterClaimed = campaign.claimedChapters.includes(chapter.id);
  const chapterClearedNormal = isChapterCleared(campaign, chapter.id, 'normal');
  const bossRec = campaign.bossRecords[boss.id];

  return (
    <div className="screen campaign-screen">
      <header className="topbar">
        <button type="button" className="btn ghost" onClick={onBack}>
          ← Menu
        </button>
        <h1>Campaign · The Road to First Light</h1>
        <div className="top-actions">
          <span className="pill campaign-progress-pill">
            {normalClearedCount}/{ALL_CAMPAIGN_BOSSES.length} Bosses
            {heroicClearedCount > 0 && ` · ★ ${heroicClearedCount} Heroic`}
            {puristCount > 0 && ` · ◇ ${puristCount} Purist`}
          </span>
          {profile.packs > 0 && (
            <button type="button" className="btn primary" onClick={onOpenPack}>
              Light Lantern ({profile.packs})
            </button>
          )}
          {normalClearedCount > 0 && (
            <button type="button" className="btn ghost" onClick={() => setConfirmReset(true)} title="Restart campaign progression">
              Reset
            </button>
          )}
        </div>
      </header>

      {/* Journey Progress Bar */}
      <div className="campaign-journey-bar" aria-label={`Campaign completion ${progressPct}%`}>
        <div className="journey-meta">
          <span>Journey to First Light</span>
          <strong>
            {progressPct}% Complete ({normalClearedCount}/{ALL_CAMPAIGN_BOSSES.length})
          </strong>
        </div>
        <div className="journey-track">
          <div className="journey-fill" style={{ width: `${progressPct}%` }} />
        </div>
      </div>

      {err && (
        <div className="alert" role="alert">
          {err}
          <button type="button" className="link" onClick={() => setErr('')}>
            Dismiss
          </button>
        </div>
      )}

      {/* Active boss battle resume banner */}
      {activeLiveGame && (
        <div className="campaign-banner is-live">
          <div>
            <strong>Battle in progress: {bossById(activeLiveGame.meta.bossId)?.name || 'Campaign Boss'}</strong>
            <span>
              {activeLiveGame.meta.difficulty === 'heroic' ? 'Heroic' : 'Normal'} · Turn {activeLiveGame.game.turn_number || 1}
            </span>
          </div>
          <button
            type="button"
            className="btn primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await onResumeMatch(activeLiveGame.game.game_id);
              } finally {
                setBusy(false);
              }
            }}
          >
            Resume Battle
          </button>
        </div>
      )}

      {/* Campaign Victory / Heroic Grand Completion Banner */}
      {campaignCompleted && (
        <div className={`campaign-banner ${heroicCompleted ? 'is-heroic' : 'is-complete'}`}>
          <div>
            <strong>
              {heroicCompleted
                ? '★ Heroic Champion of Lanternfall ★'
                : 'First Light Restored — Campaign Complete!'}
            </strong>
            <span>
              {heroicCompleted
                ? `All ${ALL_CAMPAIGN_BOSSES.length} bosses conquered on Heroic difficulty.`
                : `All ${ALL_CAMPAIGN_BOSSES.length} bosses defeated. Challenge Heroic Mode (${heroicClearedCount}/${ALL_CAMPAIGN_BOSSES.length}) for the grand reward!`}
            </span>
          </div>
          {canClaimHeroicGrand(campaign) && (
            <button type="button" className="btn primary" onClick={handleClaimHeroicGrand}>
              Claim Heroic Reward (+{HEROIC_GRAND_REWARD.packs} Lanterns, +{HEROIC_GRAND_REWARD.embers} Embers)
            </button>
          )}
        </div>
      )}

      {/* Chapter Journey Strip */}
      <div className="campaign-chapters" role="tablist" aria-label="Campaign Chapters">
        {CAMPAIGN_CHAPTERS.map((ch) => {
          const unlocked = isChapterUnlocked(campaign, ch.id);
          const cleared = isChapterCleared(campaign, ch.id, 'normal');
          const clearedH = isChapterCleared(campaign, ch.id, 'heroic');
          const claimable = canClaimChapter(campaign, ch.id);
          const count = ch.bosses.filter((b) => isBossCleared(campaign, b.id, 'normal')).length;
          return (
            <button
              key={ch.id}
              type="button"
              role="tab"
              aria-selected={ch.id === chapter.id}
              className={`campaign-ch-tab ${ch.id === chapter.id ? 'is-active' : ''} ${!unlocked ? 'is-locked' : ''} ${cleared ? 'is-cleared' : ''} ${claimable ? 'has-reward' : ''}`}
              style={{ ['--ch-accent' as any]: ch.accent }}
              onClick={() => selectChapter(ch.id)}
            >
              <span className="ch-top">
                <span className="ch-roman">Chapter {ch.roman}</span>
                <span className="ch-badge">
                  {claimable ? 'Reward!' : clearedH ? '★ Heroic' : cleared ? 'Cleared' : unlocked ? `${count}/3` : 'Locked'}
                </span>
              </span>
              <strong>{ch.title}</strong>
              <span className="ch-era">{ch.eraLabel}</span>
            </button>
          );
        })}
      </div>

      {/* Main 2-column Workspace */}
      <div className="campaign-grid">
        {/* Left: Chapter Lore, Rewards, and Boss Path */}
        <section className="panel campaign-map">
          <div className="campaign-ch-head" style={{ ['--ch-accent' as any]: chapter.accent }}>
            <div>
              <div className="campaign-kicker">
                Chapter {chapter.roman} · {chapter.eraLabel}
              </div>
              <h2>{chapter.title}</h2>
              <p className="campaign-lore">{chapter.lore}</p>
            </div>
            <div className="campaign-diff-toggle" aria-label="Difficulty">
              <button
                type="button"
                className={`seg-btn ${activeDifficulty === 'normal' ? 'is-active' : ''}`}
                onClick={() => handleSetDifficulty('normal')}
              >
                Normal
              </button>
              <button
                type="button"
                className={`seg-btn ${activeDifficulty === 'heroic' ? 'is-active' : ''}`}
                disabled={!heroicUnlocked}
                title={heroicUnlocked ? 'Boosted Boss HP, Armor, stronger Passive & Master AI' : `Clear Chapter ${chapter.roman} on Normal to unlock Heroic`}
                onClick={() => handleSetDifficulty('heroic')}
              >
                {heroicUnlocked ? '★ Heroic' : 'Heroic (Locked)'}
              </button>
            </div>
          </div>

          {/* Boss Encounter Cards */}
          <div className="campaign-boss-list">
            {chapter.bosses.map((b, idx) => {
              const unlocked = isBossUnlocked(campaign, b.id);
              const clearedN = isBossCleared(campaign, b.id, 'normal');
              const clearedH = isBossCleared(campaign, b.id, 'heroic');
              const purist = isBossPurist(campaign, b.id);
              const bStats = bossStatsFor(b, activeDifficulty);
              const isSelected = b.id === boss.id;
              const isNext = unlocked && !clearedN;
              return (
                <button
                  key={b.id}
                  type="button"
                  className={`campaign-boss-card ${isSelected ? 'is-selected' : ''} ${b.isChapterBoss ? 'is-finale' : ''} ${!unlocked ? 'is-locked' : ''} ${clearedN ? 'is-cleared' : ''}`}
                  style={{ ['--class' as any]: classColor(heroes, b.heroClass) }}
                  onClick={() => {
                    setBossId(b.id);
                    setErr('');
                  }}
                >
                  <div className="cb-portrait">
                    <Art id={b.portraitCardId} />
                    <span className="cb-step">{b.order}</span>
                  </div>
                  <div className="cb-info">
                    <div className="cb-head">
                      <strong>{b.name}</strong>
                      <span className="cb-status">
                        {clearedH
                          ? '★ Heroic'
                          : clearedN
                            ? purist
                              ? 'Defeated · ◇ Purist'
                              : 'Defeated ✓'
                            : isNext
                              ? 'Next Boss'
                              : unlocked
                                ? 'Ready'
                                : `Defeat Boss #${b.order - 1}`}
                      </span>
                    </div>
                    <div className="cb-epithet">{b.epithet}</div>
                    <div className="cb-passive-mini">⚡ {b.passiveName}</div>
                    <div className="cb-stats">
                      <span>{pretty(b.heroClass)}</span>
                      <span>♥ {bStats.hp} HP</span>
                      {bStats.armor > 0 && <span>🛡 {bStats.armor} Armor</span>}
                      {bStats.bonusMana > 0 && <span>◆ +{bStats.bonusMana} Mana</span>}
                      <span>{LEVEL_LABEL[bStats.level]}</span>
                    </div>
                  </div>
                  {idx < chapter.bosses.length - 1 && <span className="cb-connector" aria-hidden="true" />}
                </button>
              );
            })}
          </div>

          {/* Chapter Reward Chest */}
          <div className={`campaign-chest ${chapterClaimable ? 'is-ready' : ''} ${chapterClaimed ? 'is-claimed' : ''}`}>
            <div className="chest-info">
              <span className="chest-label">Chapter {chapter.roman} Completion Reward</span>
              <div className="chest-loot">
                <span>✦ {chapter.reward.packs} {chapter.reward.packs === 1 ? 'Lantern Pack' : 'Lantern Packs'}</span>
                <span>🔥 {chapter.reward.embers} Embers</span>
                <span>❖ Relic: {RELIC_BY_ID[chapter.reward.relicId].name}</span>
                {chapter.reward.cosmeticName && <span>♛ Title: {chapter.reward.cosmeticName}</span>}
              </div>
            </div>
            <div className="chest-action">
              {chapterClaimable ? (
                <button type="button" className="btn primary" onClick={() => handleClaimChapter(chapter.id)}>
                  Claim Reward
                </button>
              ) : chapterClaimed ? (
                <span className="pill">Claimed ✓</span>
              ) : (
                <span className="pill">
                  {chapterClearedNormal ? 'Ready' : `${chapter.bosses.filter((b) => isBossCleared(campaign, b.id, 'normal')).length}/3 Bosses`}
                </span>
              )}
            </div>
          </div>
        </section>

        {/* Right: Boss Dossier, Signature Cards, Relic Loadout, Deck Picker & Launch */}
        <aside className="panel campaign-dossier">
          <div className="dossier-banner" style={{ ['--class' as any]: classColor(heroes, boss.heroClass) }}>
            <div className="dossier-art">
              <Art id={boss.portraitCardId} />
            </div>
            <div className="dossier-title">
              <span className="dossier-kicker">
                Encounter {boss.order} of {ALL_CAMPAIGN_BOSSES.length} · {activeDifficulty === 'heroic' ? '★ HEROIC' : 'NORMAL'}
              </span>
              <h2>{boss.name}</h2>
              <p className="dossier-epithet">{boss.epithet}</p>
              <div className="dossier-badges">
                <span className="pill">{pretty(boss.heroClass)}</span>
                <span className="pill">♥ {stats.hp} HP</span>
                {stats.armor > 0 && <span className="pill">🛡 {stats.armor} Armor</span>}
                {stats.bonusMana > 0 && <span className="pill">◆ +{stats.bonusMana} Mana</span>}
                <span className="pill">{LEVEL_LABEL[stats.level]}</span>
              </div>
            </div>
          </div>

          {/* Boss Special Passive & Opening Board */}
          <div className={`dossier-passive ${activeDifficulty === 'heroic' ? 'is-heroic' : ''}`}>
            <div className="dp-head">
              <strong>⚡ Boss Power: {boss.passiveName}</strong>
              {stats.openingBoardLabel && <span className="dp-board-tag">{stats.openingBoardLabel}</span>}
            </div>
            <p>{stats.passiveText}</p>
          </div>

          <blockquote className="dossier-quote">
            “{bossClearedNormal ? boss.defeatQuote : boss.introQuote}”
          </blockquote>

          {/* Boss Signature Cards */}
          {signatureCards.length > 0 && (
            <div className="dossier-section">
              <div className="dossier-section-head">
                <h3>Signature Threats{bossDeck ? ` · ${bossDeck.name}` : ''}</h3>
              </div>
              <div className="sig-cards-row">
                {signatureCards.map((c) => (
                  <div key={c.id} className="sig-card-chip" title={c.text || c.name}>
                    <div className="sig-card-art">
                      <Art id={c.id} />
                      <span className="sig-card-cost">{c.cost}</span>
                    </div>
                    <div className="sig-card-meta">
                      <strong>{c.name}</strong>
                      <span>
                        {c.type === 'MINION'
                          ? `${c.attack ?? 0}/${c.health ?? 0}`
                          : c.type === 'WEAPON'
                            ? `${c.attack ?? 0}/${c.durability ?? 0} Weapon`
                            : 'Spell'}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="dossier-tip">
            <strong>Scout’s Tip:</strong> {boss.tip}
          </div>

          {/* Lantern Relic Loadout */}
          <div className="dossier-section">
            <div className="dossier-section-head">
              <h3>Lantern Relic</h3>
              <span className="muted">{activeRelic.name}</span>
            </div>
            <div className="relic-grid">
              {CAMPAIGN_RELICS.map((r) => {
                const unlocked = isRelicUnlocked(campaign, r.id);
                const equipped = activeRelic.id === r.id;
                const reqCh = r.unlockChapterId ? chapterById(r.unlockChapterId) : null;
                return (
                  <button
                    key={r.id}
                    type="button"
                    disabled={!unlocked}
                    className={`relic-card ${equipped ? 'is-equipped' : ''} ${!unlocked ? 'is-locked' : ''}`}
                    onClick={() => handleEquipRelic(r.id)}
                    title={unlocked ? r.flavor : `Clear Chapter ${reqCh?.roman ?? ''} to unlock`}
                  >
                    <div className="relic-top">
                      <strong>{r.name}</strong>
                      <span>{equipped ? 'Equipped' : unlocked ? 'Ready' : `Ch. ${reqCh?.roman ?? ''}`}</span>
                    </div>
                    <p>{unlocked ? r.effect : `Unlock by clearing Chapter ${reqCh?.roman ?? ''}`}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Player Deck Picker */}
          <div className="dossier-section">
            <div className="dossier-section-head">
              <h3>Your Deck</h3>
              <div className="deck-head-links">
                {recommendedDeck && selectedDeck?.id !== recommendedDeck.id && (
                  <button
                    type="button"
                    className="link"
                    onClick={() => {
                      setDeckFilter('all');
                      updateCampaignState((cur) => ({ ...cur, selectedDeckId: recommendedDeck.id }));
                    }}
                  >
                    Use counter ({recommendedDeck.name})
                  </button>
                )}
                <button type="button" className="link" onClick={onOpenDeckbuilder}>
                  Build deck →
                </button>
              </div>
            </div>
            <div className="deck-filter-row">
              {(['all', 'custom', 'classic', 'expansion'] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`chip-btn ${deckFilter === f ? 'is-active' : ''}`}
                  disabled={f === 'custom' && customDecks.length === 0}
                  onClick={() => setDeckFilter(f)}
                >
                  {f === 'all'
                    ? 'All'
                    : f === 'custom'
                      ? `Custom (${customDecks.length})`
                      : f === 'classic'
                        ? 'Classic'
                        : 'Expansions'}
                </button>
              ))}
            </div>
            <select
              className="campaign-deck-select"
              aria-label="Choose your campaign deck"
              value={selectedDeck?.id || ''}
              onChange={(e) => {
                const id = e.target.value;
                updateCampaignState((cur) => ({ ...cur, selectedDeckId: id }));
              }}
            >
              {visibleDecks.map((d) => (
                <option key={d.id} value={d.id}>
                  [{pretty(d.hero_class)}] {d.name}
                  {!d.builtin ? ' ★ Custom' : d.era_name ? ` (${d.era_name})` : ''}
                </option>
              ))}
            </select>
            {selectedDeck && (
              <div className="selected-deck-meta" style={{ ['--class' as any]: classColor(heroes, selectedDeck.hero_class) }}>
                <span className="deck-class-dot" />
                <span>
                  <b>{heroes[selectedDeck.hero_class]?.name || pretty(selectedDeck.hero_class)}</b> · {selectedDeck.description || `${selectedDeck.cards.length} cards`}
                </span>
              </div>
            )}
          </div>

          {/* Opponent engine choice when server is connected */}
          {serverUp && (
            <div className="dossier-section">
              <div className="dossier-section-head">
                <h3>Opponent Engine</h3>
              </div>
              <div className="deck-filter-row">
                {(
                  [
                    { id: 'device', label: 'Built-in AI' },
                    { id: 'bot', label: 'Practice Bot' },
                    ...(agentInfo?.available ? [{ id: 'agent', label: 'Antigravity AI' }] : []),
                  ] as { id: OpponentMode; label: string }[]
                ).map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    className={`chip-btn ${effectiveMode === m.id ? 'is-active' : ''}`}
                    onClick={() => updateCampaignState((cur) => ({ ...cur, preferredOpponent: m.id }))}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Launch Button & Mastery Record */}
          <div className="dossier-launch">
            <button
              type="button"
              className="btn primary campaign-fight-btn"
              disabled={busy || !bossUnlocked || !selectedDeck}
              onClick={() => void handleLaunch()}
            >
              {!bossUnlocked
                ? `Locked — Defeat ${bossById(ALL_CAMPAIGN_BOSSES[boss.order - 2]?.id || '')?.name || 'Previous Boss'} first`
                : busy
                  ? 'Preparing encounter…'
                  : activeDifficulty === 'heroic'
                    ? bossClearedHeroic
                      ? `Rematch Heroic ${boss.name}`
                      : `Challenge Heroic ${boss.name}`
                    : bossClearedNormal
                      ? `Rematch ${boss.name}`
                      : `Challenge ${boss.name}`}
            </button>
            {(campaign.attempts[boss.id] > 0 || bossRec) && (
              <p className="dossier-attempts">
                Attempts: {campaign.attempts[boss.id] || 0}
                {bossRec?.bestTurns ? ` · Best win: Turn ${bossRec.bestTurns}` : ''}
                {bossRec?.bestClass ? ` (${pretty(bossRec.bestClass)})` : ''}
                {bossPurist ? ' · ◇ Purist' : ''}
                {bossClearedHeroic ? ' · ★ Heroic' : ''}
              </p>
            )}
          </div>
        </aside>
      </div>

      {/* Reward Claim Modal */}
      {rewardNotice && (
        <div className="modal" onClick={() => setRewardNotice(null)}>
          <div className="sheet campaign-reward-sheet" onClick={(e) => e.stopPropagation()}>
            <h2>{rewardNotice.title}</h2>
            <p className="sheet-sub">Your spoils have been added to your Lanternfall profile.</p>
            <div className="reward-loot-list">
              <div className="reward-loot-item">
                <b>+{rewardNotice.packs}</b> {rewardNotice.packs === 1 ? 'Lantern Pack' : 'Lantern Packs'}
              </div>
              <div className="reward-loot-item">
                <b>+{rewardNotice.embers}</b> Embers
              </div>
              {rewardNotice.relicName && (
                <div className="reward-loot-item is-relic">
                  Unlocked Relic: <b>{rewardNotice.relicName}</b>
                </div>
              )}
              {rewardNotice.cosmeticName && (
                <div className="reward-loot-item is-relic">
                  Earned Gilded Title: <b>{rewardNotice.cosmeticName}</b>
                </div>
              )}
            </div>
            <div className="menu-list">
              {profile.packs > 0 && (
                <button
                  type="button"
                  className="btn primary"
                  onClick={() => {
                    setRewardNotice(null);
                    onOpenPack();
                  }}
                >
                  Light a Lantern ({profile.packs})
                </button>
              )}
              <button type="button" className="btn" onClick={() => setRewardNotice(null)}>
                Continue Campaign
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Confirm Reset Modal */}
      {confirmReset && (
        <div className="modal" onClick={() => setConfirmReset(false)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h2>Reset Campaign?</h2>
            <p className="sheet-sub">
              This resets your boss clears, Heroic badges, and unlocked Campaign Relics back to Chapter I. Your Lantern Packs, Embers, and Cosmetics stay safe.
            </p>
            <div className="menu-list">
              <button
                type="button"
                className="btn danger"
                onClick={() => {
                  updateCampaignState((cur) => resetCampaignState(cur));
                  setChapterId('ch1');
                  setBossId('ch1_bouncer');
                  setConfirmReset(false);
                }}
              >
                Reset Campaign Progress
              </button>
              <button type="button" className="btn" onClick={() => setConfirmReset(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
