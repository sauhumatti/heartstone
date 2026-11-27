import React, { useMemo, useState } from 'react';
import {
  ALL_CAMPAIGN_RIVALS,
  CAMPAIGN_CHAPTERS,
  CAMPAIGN_PROLOGUE,
  HERO_STARTER_PITCH,
  chapterById,
  rivalById,
  type CampaignRival,
} from '../campaign/data';
import {
  CAMPAIGN_DECK_SIZE,
  advanceFromIntro,
  clearNewCards,
  completeChapterInterlude,
  currentChapter,
  currentRival,
  isChapterCleared,
  isRivalDefeated,
  pickRewardCard,
  resetCampaignState,
  saveCampaignDeck,
  startCampaignWithHero,
  validateCampaignDeck,
} from '../campaign/rules';
import { updateCampaignState, useCampaignState } from '../campaign/store';
import { grantCampaignReward } from '../progress/rules';
import { updateProfile, useProfile } from '../progress/store';
import { sfx } from '../sound';
import type { CardDef, DeckInfo, GameSummary, HeroMeta } from '../types';
import { Art, CardFace, classColor, pretty } from './pieces';

interface CampaignProps {
  heroes: Record<string, HeroMeta>;
  cards: CardDef[];
  decks: DeckInfo[];
  games: GameSummary[];
  onStartDuel: (opts: {
    rival: CampaignRival;
    heroClass: string;
    playerDeck: string[];
  }) => Promise<void>;
  onResumeMatch: (gameId: string) => Promise<void>;
  onOpenPack: () => void;
  onBack: () => void;
}

const LEVEL_LABEL: Record<'easy' | 'normal' | 'hard', string> = {
  easy: 'Apprentice',
  normal: 'Adept',
  hard: 'Master',
};

const TIER_BADGE: Record<string, string> = {
  class: 'Class Spoils',
  rare: 'Hall Spoils',
  epic: 'Champion Spoils',
  legendary: '★ Guaranteed Legendary',
  consolation: 'Deck Adaptation',
};

export const Campaign: React.FC<CampaignProps> = ({
  heroes,
  cards,
  games,
  onStartDuel,
  onResumeMatch,
  onOpenPack,
  onBack,
}) => {
  const campaign = useCampaignState();
  const profile = useProfile();

  const [introStep, setIntroStep] = useState(0);
  const [pickedHero, setPickedHero] = useState<string>('MAGE');
  const [editingDeck, setEditingDeck] = useState(false);
  const [draftDeck, setDraftDeck] = useState<string[]>([]);
  const [manaFilter, setManaFilter] = useState<number | null>(null);
  const [cardFilter, setCardFilter] = useState<'all' | 'class' | 'neutral' | 'new'>('all');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [confirmRestart, setConfirmRestart] = useState(false);

  const cardById = useMemo(() => {
    const m: Record<string, CardDef> = {};
    for (const c of cards) m[c.id] = c;
    return m;
  }, [cards]);

  const heroList = useMemo(() => Object.values(heroes), [heroes]);
  const chapter = currentChapter(campaign);
  const rival = currentRival(campaign);

  const activeLiveGame = useMemo(() => {
    if (!campaign.activeMatch) return null;
    const g = games.find((x) => x.game_id === campaign.activeMatch?.gameId && x.phase !== 'GAME_OVER');
    return g ? { game: g, rival: rivalById(campaign.activeMatch.rivalId) } : null;
  }, [campaign.activeMatch, games]);

  const totalOwnedCards = useMemo(
    () => Object.values(campaign.collection).reduce((a, b) => a + b, 0),
    [campaign.collection],
  );

  // --- Deck Workshop helpers ---
  const openDeckEditor = () => {
    setDraftDeck([...campaign.deck]);
    setManaFilter(null);
    setCardFilter(campaign.newCards.length > 0 ? 'new' : 'all');
    setErr('');
    setEditingDeck(true);
  };

  const draftCounts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const id of draftDeck) m[id] = (m[id] || 0) + 1;
    return m;
  }, [draftDeck]);

  const collectionCards = useMemo(() => {
    const newSet = new Set(campaign.newCards);
    const list = Object.entries(campaign.collection)
      .filter(([, qty]) => qty > 0)
      .map(([id, qty]) => ({ card: cardById[id], qty, isNew: newSet.has(id) }))
      .filter((x): x is { card: CardDef; qty: number; isNew: boolean } => Boolean(x.card));

    return list
      .filter((x) => {
        if (cardFilter === 'new' && !x.isNew) return false;
        if (cardFilter === 'class' && x.card.card_class === 'NEUTRAL') return false;
        if (cardFilter === 'neutral' && x.card.card_class !== 'NEUTRAL') return false;
        if (manaFilter !== null) {
          if (manaFilter === 6 ? x.card.cost < 6 : x.card.cost !== manaFilter) return false;
        }
        return true;
      })
      .sort((a, b) => Number(b.isNew) - Number(a.isNew) || a.card.cost - b.card.cost || a.card.name.localeCompare(b.card.name));
  }, [campaign.collection, campaign.newCards, cardById, cardFilter, manaFilter]);

  const draftEntries = useMemo(() => {
    return Object.entries(draftCounts)
      .map(([id, count]) => ({ card: cardById[id], count }))
      .filter((x): x is { card: CardDef; count: number } => Boolean(x.card))
      .sort((a, b) => a.card.cost - b.card.cost || a.card.name.localeCompare(b.card.name));
  }, [draftCounts, cardById]);

  const draftCurve = useMemo(() => {
    const buckets = [0, 0, 0, 0, 0, 0, 0, 0];
    for (const id of draftDeck) {
      const c = cardById[id];
      if (c) buckets[Math.min(7, Math.max(0, c.cost))]++;
    }
    return buckets;
  }, [draftDeck, cardById]);

  const addDraftCard = (cardId: string) => {
    const owned = campaign.collection[cardId] || 0;
    const inDeck = draftCounts[cardId] || 0;
    if (inDeck >= owned || draftDeck.length >= CAMPAIGN_DECK_SIZE) return;
    sfx.uiClick();
    setDraftDeck((prev) => [...prev, cardId]);
  };

  const removeDraftCard = (cardId: string) => {
    const idx = draftDeck.indexOf(cardId);
    if (idx < 0) return;
    sfx.uiClick();
    setDraftDeck((prev) => [...prev.slice(0, idx), ...prev.slice(idx + 1)]);
  };

  const handleSaveDeck = () => {
    const check = validateCampaignDeck(campaign, draftDeck, cards);
    if (!check.ok) {
      setErr(check.error);
      return;
    }
    sfx.uiClick();
    updateCampaignState((cur) => saveCampaignDeck(cur, draftDeck, cards));
    setEditingDeck(false);
    setErr('');
  };

  const handleLaunchDuel = async () => {
    if (!campaign.heroClass) return;
    const check = validateCampaignDeck(campaign, campaign.deck, cards);
    if (!check.ok) {
      setErr(check.error);
      openDeckEditor();
      return;
    }
    setBusy(true);
    setErr('');
    try {
      await onStartDuel({
        rival,
        heroClass: campaign.heroClass,
        playerDeck: campaign.deck,
      });
    } catch (e: any) {
      setErr(e?.message || 'Could not start duel.');
    } finally {
      setBusy(false);
    }
  };

  const handleContinueChapter = () => {
    let finished: ReturnType<typeof completeChapterInterlude> = null;
    updateCampaignState((cur) => {
      finished = completeChapterInterlude(cur);
      return finished ? finished.state : cur;
    });
    if (!finished) return;
    const { chapter: ch, newlyClaimed } = finished as NonNullable<ReturnType<typeof completeChapterInterlude>>;
    if (newlyClaimed) {
      updateProfile((p) => grantCampaignReward(p, ch.rewardPacks, ch.rewardEmbers, ch.cosmeticId));
      sfx.cue('victory');
    }
  };

  // =========================================================================
  // PHASE 1: STORY PROLOGUE INTRO
  // =========================================================================
  if (campaign.phase === 'intro') {
    const beat = CAMPAIGN_PROLOGUE[Math.min(introStep, CAMPAIGN_PROLOGUE.length - 1)];
    const isLast = introStep >= CAMPAIGN_PROLOGUE.length - 1;
    return (
      <div className="screen story-screen">
        <header className="topbar">
          <button type="button" className="btn ghost" onClick={onBack}>
            ← Menu
          </button>
          <h1>The Road to First Light</h1>
          <button
            type="button"
            className="btn ghost"
            onClick={() => updateCampaignState((cur) => advanceFromIntro(cur))}
          >
            Skip
          </button>
        </header>

        <div className="story-stage">
          <div className="story-card">
            <div className="story-kicker">{beat.kicker}</div>
            <h2>{beat.title}</h2>
            <p className="story-body">{beat.body}</p>
            <div className="story-dots" aria-hidden="true">
              {CAMPAIGN_PROLOGUE.map((_, i) => (
                <span key={i} className={i === introStep ? 'is-active' : i < introStep ? 'is-done' : ''} />
              ))}
            </div>
            <div className="story-actions">
              {introStep > 0 && (
                <button type="button" className="btn ghost" onClick={() => setIntroStep((s) => Math.max(0, s - 1))}>
                  Back
                </button>
              )}
              <button
                type="button"
                className="btn primary"
                onClick={() => {
                  sfx.uiClick();
                  if (isLast) updateCampaignState((cur) => advanceFromIntro(cur));
                  else setIntroStep((s) => s + 1);
                }}
              >
                {isLast ? 'Choose Your Hero →' : 'Continue →'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // PHASE 2: CHOOSE YOUR HERO & STARTER DECK
  // =========================================================================
  if (campaign.phase === 'choose_hero' || !campaign.heroClass) {
    const chosen = heroes[pickedHero] || heroList[0];
    const pitch = chosen ? HERO_STARTER_PITCH[chosen.card_class] : undefined;
    return (
      <div className="screen story-screen">
        <header className="topbar">
          <button type="button" className="btn ghost" onClick={onBack}>
            ← Menu
          </button>
          <h1>Choose Your Challenger</h1>
          <span className="pill">Starter Deck · 30 Basics & Commons</span>
        </header>

        <div className="story-choose-wrap">
          <p className="story-lead">
            Pick the hero who will carry your lantern across the Five Halls. You’ll begin with an honest 30-card starter deck and expand your collection after every match.
          </p>

          <div className="story-hero-grid">
            {heroList.map((h) => {
              const p = HERO_STARTER_PITCH[h.card_class];
              const selected = h.card_class === (chosen?.card_class || pickedHero);
              return (
                <button
                  key={h.card_class}
                  type="button"
                  className={`story-hero-card ${selected ? 'is-selected' : ''}`}
                  style={{ ['--class' as any]: classColor(heroes, h.card_class) }}
                  onClick={() => {
                    sfx.uiClick();
                    setPickedHero(h.card_class);
                  }}
                >
                  <div className="shc-art">
                    <Art id={`hero_${h.card_class}`} />
                  </div>
                  <div className="shc-text">
                    <span className="shc-class">{pretty(h.card_class)}</span>
                    <strong>{h.name}</strong>
                    {p && <span className="shc-style">{p.style}</span>}
                    {p && <p>{p.summary}</p>}
                  </div>
                </button>
              );
            })}
          </div>

          {chosen && (
            <div className="story-choose-bar">
              <div>
                <strong>
                  {chosen.name} · {pretty(chosen.card_class)}
                </strong>
                <span>{pitch?.summary || 'Balanced 30-card Basic & Common starter deck.'}</span>
              </div>
              <button
                type="button"
                className="btn primary"
                onClick={() => {
                  sfx.cue('victory');
                  updateCampaignState((cur) => startCampaignWithHero(cur, chosen.card_class, cards));
                }}
              >
                Begin Chapter I →
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // =========================================================================
  // PHASE 3: POST-DUEL CARD REWARD DRAFT
  // =========================================================================
  if (campaign.phase === 'rewards' && campaign.pendingRewards.length > 0) {
    const offer = campaign.pendingRewards[0];
    const remaining = campaign.pendingRewards.length;
    return (
      <div className="screen story-screen">
        <header className="topbar">
          <button type="button" className="btn ghost" onClick={onBack}>
            ← Menu
          </button>
          <h1>Card Rewards</h1>
          <span className="pill">
            {remaining} {remaining === 1 ? 'Pick Remaining' : 'Picks Remaining'}
          </span>
        </header>

        <div className="story-rewards-stage">
          <div className="rewards-header">
            <span className={`rewards-tier tier-${offer.tier}`}>{TIER_BADGE[offer.tier] || 'Card Reward'}</span>
            <h2>{offer.label}</h2>
            <p>Choose 1 card to add permanently to your Campaign collection.</p>
          </div>

          <div className="rewards-pick-row">
            {offer.choices.map((cid) => {
              const card = cardById[cid];
              if (!card) return null;
              const owned = campaign.collection[cid] || 0;
              return (
                <button
                  key={cid}
                  type="button"
                  className="reward-card-pick"
                  onClick={() => {
                    sfx.uiClick();
                    const wasLast = campaign.pendingRewards.length === 1;
                    const willInterlude = Boolean(campaign.pendingChapterClear);
                    updateCampaignState((cur) => pickRewardCard(cur, cid, cards));
                    if (wasLast && !willInterlude) {
                      // Smoothly invite player to slot their new cards in or return to road
                    }
                  }}
                >
                  <CardFace card={card} heroes={heroes} />
                  <span className="reward-card-owned">
                    {owned === 0 ? 'New to collection' : `Owned: ${owned} → ${owned + 1}`}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // PHASE 4: CHAPTER COMPLETE STORY INTERLUDE
  // =========================================================================
  if (campaign.phase === 'chapter_clear' && campaign.pendingChapterClear) {
    const clearedCh = chapterById(campaign.pendingChapterClear) || chapter;
    const nextCh = CAMPAIGN_CHAPTERS.find((c) => c.number === clearedCh.number + 1);
    return (
      <div className="screen story-screen">
        <header className="topbar">
          <button type="button" className="btn ghost" onClick={onBack}>
            ← Menu
          </button>
          <h1>Chapter {clearedCh.roman} Complete</h1>
          <span className="pill">{clearedCh.title}</span>
        </header>

        <div className="story-stage">
          <div className="story-card is-interlude" style={{ ['--ch-accent' as any]: clearedCh.accent }}>
            <div className="story-kicker">
              Chapter {clearedCh.roman} Cleared · {clearedCh.eraLabel}
            </div>
            <h2>{clearedCh.title}</h2>
            <p className="story-body">{clearedCh.outroText}</p>
            <div className="interlude-spoils">
              <span>✦ +{clearedCh.rewardPacks} {clearedCh.rewardPacks === 1 ? 'Lantern Pack' : 'Lantern Packs'}</span>
              <span>🔥 +{clearedCh.rewardEmbers} Embers</span>
              {clearedCh.cosmeticName && <span>♛ Title: {clearedCh.cosmeticName}</span>}
            </div>
            {nextCh && (
              <p className="interlude-next">
                Next Hall: <strong>Chapter {nextCh.roman} — {nextCh.title}</strong> ({nextCh.eraLabel} cards unlocked)
              </p>
            )}
            <div className="story-actions">
              <button type="button" className="btn primary" onClick={handleContinueChapter}>
                {nextCh ? `Continue to Chapter ${nextCh.roman} →` : 'Finish the Journey →'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // SUB-VIEW: CAMPAIGN DECK WORKSHOP (ONLY YOUR EARNED CAMPAIGN CARDS!)
  // =========================================================================
  if (editingDeck) {
    const maxBucket = Math.max(4, ...draftCurve);
    const valid = draftDeck.length === CAMPAIGN_DECK_SIZE;
    return (
      <div className="screen story-screen">
        <header className="topbar">
          <button
            type="button"
            className="btn ghost"
            onClick={() => {
              setEditingDeck(false);
              setErr('');
            }}
          >
            ← Back
          </button>
          <h1>Campaign Deck Workshop · {pretty(campaign.heroClass)}</h1>
          <div className="top-actions">
            <span className={`pill ${valid ? 'is-valid' : 'is-warn'}`}>
              {draftDeck.length} / {CAMPAIGN_DECK_SIZE} Cards
            </span>
            <button type="button" className="btn primary" disabled={!valid} onClick={handleSaveDeck}>
              Save Deck
            </button>
          </div>
        </header>

        {err && (
          <div className="alert" role="alert">
            {err}
          </div>
        )}

        <div className="workshop-grid">
          <section className="panel workshop-pool">
            <div className="workshop-filters">
              <div className="deck-filter-row">
                {(['all', 'new', 'class', 'neutral'] as const).map((f) => (
                  <button
                    key={f}
                    type="button"
                    className={`chip-btn ${cardFilter === f ? 'is-active' : ''}`}
                    disabled={f === 'new' && campaign.newCards.length === 0}
                    onClick={() => setCardFilter(f)}
                  >
                    {f === 'all'
                      ? `All (${totalOwnedCards})`
                      : f === 'new'
                        ? `New (${campaign.newCards.length})`
                        : f === 'class'
                          ? pretty(campaign.heroClass || '')
                          : 'Neutral'}
                  </button>
                ))}
              </div>
              <div className="deck-filter-row">
                <button
                  type="button"
                  className={`chip-btn ${manaFilter === null ? 'is-active' : ''}`}
                  onClick={() => setManaFilter(null)}
                >
                  Any Mana
                </button>
                {[1, 2, 3, 4, 5, 6].map((m) => (
                  <button
                    key={m}
                    type="button"
                    className={`chip-btn ${manaFilter === m ? 'is-active' : ''}`}
                    onClick={() => setManaFilter(manaFilter === m ? null : m)}
                  >
                    {m === 6 ? '6+' : m}
                  </button>
                ))}
              </div>
            </div>

            <div className="workshop-cards">
              {collectionCards.map(({ card, qty, isNew }) => {
                const used = draftCounts[card.id] || 0;
                const left = qty - used;
                const full = left <= 0 || draftDeck.length >= CAMPAIGN_DECK_SIZE;
                return (
                  <button
                    key={card.id}
                    type="button"
                    className={`workshop-card-btn ${full ? 'is-used' : ''} ${isNew ? 'is-new' : ''}`}
                    disabled={full}
                    onClick={() => addDraftCard(card.id)}
                    title={left > 0 ? `Add ${card.name} to deck` : `All owned copies (${qty}) are in your deck`}
                  >
                    {isNew && <span className="wc-new-badge">NEW</span>}
                    <CardFace card={card} heroes={heroes} />
                    <span className="wc-qty">
                      {used}/{qty} in deck
                    </span>
                  </button>
                );
              })}
              {collectionCards.length === 0 && (
                <p className="workshop-empty">No unlocked Campaign cards match this filter yet.</p>
              )}
            </div>
          </section>

          <aside className="panel workshop-deck">
            <div className="wd-head">
              <h3>Your Deck ({draftDeck.length}/{CAMPAIGN_DECK_SIZE})</h3>
              <span className="muted">Click a card to remove</span>
            </div>

            <div className="wd-curve" aria-label="Mana curve">
              {draftCurve.map((cnt, cost) => (
                <div key={cost} className="wd-bar-col">
                  <span className="wd-bar-cnt">{cnt || ''}</span>
                  <div className="wd-bar-track">
                    <div className="wd-bar-fill" style={{ height: `${Math.round((cnt / maxBucket) * 100)}%` }} />
                  </div>
                  <span className="wd-bar-cost">{cost === 7 ? '7+' : cost}</span>
                </div>
              ))}
            </div>

            <ul className="deck-list workshop-list">
              {draftEntries.map(({ card, count }) => (
                <li key={card.id}>
                  <button
                    type="button"
                    style={{ ['--class' as any]: classColor(heroes, card.card_class) }}
                    onClick={() => removeDraftCard(card.id)}
                  >
                    <span className="dl-cost">{card.cost}</span>
                    <span className="dl-name">{card.name}</span>
                    <span className="dl-qty">{count > 1 ? `×${count}` : card.rarity === 'LEGENDARY' ? '★' : ''}</span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      </div>
    );
  }

  // =========================================================================
  // PHASE 5: CAMPAIGN COMPLETE EPILOGUE
  // =========================================================================
  if (campaign.phase === 'complete') {
    const finalEntries = (() => {
      const m: Record<string, number> = {};
      for (const id of campaign.deck) m[id] = (m[id] || 0) + 1;
      return Object.entries(m)
        .map(([id, count]) => ({ card: cardById[id], count }))
        .filter((x): x is { card: CardDef; count: number } => Boolean(x.card))
        .sort((a, b) => a.card.cost - b.card.cost || a.card.name.localeCompare(b.card.name));
    })();

    return (
      <div className="screen story-screen">
        <header className="topbar">
          <button type="button" className="btn ghost" onClick={onBack}>
            ← Menu
          </button>
          <h1>Champion of First Light</h1>
          <span className="pill">
            15/15 Rivals · {campaign.wins}W–{campaign.losses}L
          </span>
        </header>

        <div className="story-stage">
          <div className="story-card is-finale">
            <div className="story-kicker">Journey Complete · {heroes[campaign.heroClass]?.name || pretty(campaign.heroClass)}</div>
            <h2>First Light Burns Again</h2>
            <p className="story-body">{CAMPAIGN_CHAPTERS[4].outroText}</p>

            <div className="finale-stats">
              <div>
                <b>15 / 15</b>
                <span>Rivals Defeated</span>
              </div>
              <div>
                <b>{campaign.wins}–{campaign.losses}</b>
                <span>Campaign Record</span>
              </div>
              <div>
                <b>{totalOwnedCards}</b>
                <span>Cards Collected</span>
              </div>
            </div>

            <div className="finale-deck-preview">
              <h3>Your Champion’s Deck ({pretty(campaign.heroClass)})</h3>
              <div className="finale-deck-chips">
                {finalEntries.map(({ card, count }) => (
                  <span key={card.id} className="finale-chip">
                    <i>{card.cost}</i> {card.name}
                    {count > 1 ? ` ×${count}` : ''}
                  </span>
                ))}
              </div>
            </div>

            <div className="story-actions">
              {profile.packs > 0 && (
                <button type="button" className="btn primary" onClick={onOpenPack}>
                  Light a Lantern ({profile.packs})
                </button>
              )}
              <button
                type="button"
                className={`btn ${profile.packs > 0 ? '' : 'primary'}`}
                onClick={() => updateCampaignState((cur) => resetCampaignState(cur))}
              >
                Start New Journey (Pick Another Hero)
              </button>
              <button type="button" className="btn ghost" onClick={onBack}>
                Main Menu
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // =========================================================================
  // MAIN PHASE: THE ROAD (CLEAN, WELL-PACED CURRENT CHAPTER & RIVAL)
  // =========================================================================
  const heroMeta = heroes[campaign.heroClass];
  const hasNewCards = campaign.newCards.length > 0;

  return (
    <div className="screen story-screen">
      <header className="topbar">
        <button type="button" className="btn ghost" onClick={onBack}>
          ← Menu
        </button>
        <h1>
          Chapter {chapter.roman} · {chapter.title}
        </h1>
        <div className="top-actions">
          <span className="pill">
            {campaign.defeatedRivals.length}/{ALL_CAMPAIGN_RIVALS.length} Rivals
          </span>
          {profile.packs > 0 && (
            <button type="button" className="btn" onClick={onOpenPack}>
              Lanterns ({profile.packs})
            </button>
          )}
          <button type="button" className="btn ghost" onClick={() => setConfirmRestart(true)}>
            New Run
          </button>
        </div>
      </header>

      {err && (
        <div className="alert" role="alert">
          {err}
          <button type="button" className="link" onClick={() => setErr('')}>
            Dismiss
          </button>
        </div>
      )}

      <div className="road-wrap">
        {/* Clean 5-Hall Milestone Stepper */}
        <ol className="road-halls" aria-label="Five Halls of Lanternfall">
          {CAMPAIGN_CHAPTERS.map((ch) => {
            const cleared = isChapterCleared(campaign, ch.id);
            const active = ch.id === chapter.id;
            return (
              <li
                key={ch.id}
                className={`${active ? 'is-active' : ''} ${cleared ? 'is-cleared' : ''}`}
                style={{ ['--ch-accent' as any]: ch.accent }}
              >
                <span className="rh-dot">{cleared ? '✓' : ch.roman}</span>
                <span className="rh-name">{ch.title}</span>
              </li>
            );
          })}
        </ol>

        {/* Chapter Story & 3-Rival Step Path */}
        <section className="panel road-chapter" style={{ ['--ch-accent' as any]: chapter.accent }}>
          <div className="rc-head">
            <span className="rc-era">
              Chapter {chapter.roman} of 5 · {chapter.eraLabel}
            </span>
            <p className="rc-story">{chapter.introText}</p>
          </div>

          <div className="rc-rivals">
            {chapter.rivals.map((r) => {
              const done = isRivalDefeated(campaign, r.id);
              const isCurrent = r.id === rival.id;
              return (
                <div
                  key={r.id}
                  className={`rc-node ${done ? 'is-done' : ''} ${isCurrent ? 'is-current' : 'is-locked'}`}
                  style={{ ['--class' as any]: classColor(heroes, r.heroClass) }}
                >
                  <div className="rc-node-art">
                    <Art id={r.portraitCardId} />
                    {done && <span className="rc-node-check">✓</span>}
                  </div>
                  <div className="rc-node-info">
                    <span className="rc-node-role">
                      {done ? 'Defeated' : isCurrent ? (r.isChampion ? 'Hall Champion' : 'Next Rival') : 'Ahead'}
                    </span>
                    <strong>{r.name}</strong>
                    <span>{pretty(r.heroClass)} · {LEVEL_LABEL[r.level]}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Current Rival Duel Spotlight — Focused, Two Clear Actions */}
        <section className="panel road-spotlight" style={{ ['--class' as any]: classColor(heroes, rival.heroClass) }}>
          <div className="rs-rival">
            <div className="rs-art">
              <Art id={rival.portraitCardId} />
            </div>
            <div className="rs-details">
              <div className="rs-kicker">
                Duel {rival.order} of {ALL_CAMPAIGN_RIVALS.length} · Fair 30 HP Match · {LEVEL_LABEL[rival.level]}
              </div>
              <h2>{rival.name}</h2>
              <p className="rs-deck">
                {rival.title} · <b>{rival.deckLabel}</b>
              </p>
              <p className="rs-story">{rival.storyLine}</p>
              <blockquote className="rs-quote">“{rival.introQuote}”</blockquote>
            </div>
          </div>

          <div className="rs-actions">
            {activeLiveGame ? (
              <button
                type="button"
                className="btn primary rs-duel-btn"
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
                Resume Duel vs {activeLiveGame.rival?.name || rival.name}
              </button>
            ) : (
              <button
                type="button"
                className="btn primary rs-duel-btn"
                disabled={busy}
                onClick={() => void handleLaunchDuel()}
              >
                {busy ? 'Setting the table…' : `Duel ${rival.name}`}
              </button>
            )}
            <button
              type="button"
              className={`btn rs-deck-btn ${hasNewCards ? 'is-glow' : ''}`}
              onClick={openDeckEditor}
            >
              Edit Campaign Deck
              {hasNewCards && (
                <span className="rs-new-pill">
                  +{campaign.newCards.length} new
                </span>
              )}
            </button>
          </div>

          <div className="rs-foot">
            <span>
              Playing as <b>{heroMeta?.name || pretty(campaign.heroClass)}</b> ({pretty(campaign.heroClass)}) ·{' '}
              <b>{campaign.deck.length}</b> cards in deck · <b>{totalOwnedCards}</b> cards in Campaign collection
            </span>
            <span>
              Record: <b>{campaign.wins}W–{campaign.losses}L</b>
              {hasNewCards && (
                <>
                  {' · '}
                  <button
                    type="button"
                    className="link"
                    onClick={() => updateCampaignState((cur) => clearNewCards(cur))}
                  >
                    Dismiss new badge
                  </button>
                </>
              )}
            </span>
          </div>
        </section>
      </div>

      {/* Confirm New Run Modal */}
      {confirmRestart && (
        <div className="modal" onClick={() => setConfirmRestart(false)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h2>Start a New Campaign?</h2>
            <p className="sheet-sub">
              You’ll choose a new hero and start fresh from Chapter I with a Basic & Common starter deck. Your Lantern Packs, Embers, and Cosmetics stay safe.
            </p>
            <div className="menu-list">
              <button
                type="button"
                className="btn danger"
                onClick={() => {
                  updateCampaignState((cur) => resetCampaignState(cur));
                  setConfirmRestart(false);
                }}
              >
                Start New Campaign
              </button>
              <button type="button" className="btn" onClick={() => setConfirmRestart(false)}>
                Keep Playing
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
