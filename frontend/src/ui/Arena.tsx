import React, { useEffect, useMemo, useState } from 'react';
import { fetchAgentInfo } from '../api';
import {
  ARENA_DECK_SIZE,
  ARENA_MAX_LOSSES,
  ARENA_MAX_WINS,
  ARENA_POOLS,
  GUARANTEED_RARE_PICKS,
  arenaKeyFor,
  chooseRunHero,
  claimRunRewards,
  draftOpponentDeck,
  levelForArenaWins,
  pickDraftCard,
  retireArenaRun,
  startNewRun,
  type ArenaKey,
  type ArenaPoolId,
} from '../arena/rules';
import { updateArenaState, useArenaState } from '../arena/store';
import { grantArenaReward } from '../progress/rules';
import { updateProfile, useProfile } from '../progress/store';
import { sfx } from '../sound';
import type { AgentInfo, CardDef, GameSummary, HeroMeta, Level, OpponentMode } from '../types';
import { Art, CardFace, classColor, pretty } from './pieces';

interface ArenaProps {
  heroes: Record<string, HeroMeta>;
  cards: CardDef[];
  games: GameSummary[];
  serverUp: boolean;
  levels: Level[];
  onStartMatch: (opts: {
    heroClass: string;
    deck: string[];
    deckName: string;
    opponentClass: string;
    opponentDeck: string[];
    opponentDeckName: string;
    opponentName: string;
    p2Mode: OpponentMode;
    level?: string;
    agentModel?: string;
  }) => Promise<void>;
  onResumeMatch: (gameId: string) => Promise<void>;
  onOpenPack: () => void;
  onBack: () => void;
}

const KeyIcon: React.FC<{ wins: number }> = ({ wins }) => {
  const tone = wins >= 12 ? '#ffd86b' : wins >= 8 ? '#f4b545' : wins >= 4 ? '#c9d7ea' : '#b7895c';
  return (
    <svg className="arena-key-svg" viewBox="0 0 64 64" fill="none" aria-hidden="true" style={{ color: tone }}>
      <circle cx="24" cy="24" r="13" stroke="currentColor" strokeWidth="3.2" fill="currentColor" fillOpacity="0.14" />
      <circle cx="24" cy="24" r="5" fill="currentColor" />
      <path d="M33.5 33.5 55 55M44 44l6-6M49 49l5-5" stroke="currentColor" strokeWidth="3.6" strokeLinecap="round" />
    </svg>
  );
};

export const Arena: React.FC<ArenaProps> = ({
  heroes,
  cards,
  games,
  serverUp,
  levels,
  onStartMatch,
  onResumeMatch,
  onOpenPack,
  onBack,
}) => {
  const arena = useArenaState();
  const profile = useProfile();
  const run = arena.run;

  const [pool, setPool] = useState<ArenaPoolId>(run?.pool || 'wild');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [confirmRetire, setConfirmRetire] = useState(false);
  const [claimedKey, setClaimedKey] = useState<ArenaKey | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
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

  const byId = useMemo(() => {
    const m: Record<string, CardDef> = {};
    for (const c of cards) m[c.id] = c;
    return m;
  }, [cards]);

  const heroClasses = useMemo(() => Object.keys(heroes), [heroes]);

  const deckEntries = useMemo(() => {
    if (!run) return [];
    const counts: Record<string, number> = {};
    for (const id of run.deck) counts[id] = (counts[id] || 0) + 1;
    return Object.entries(counts)
      .map(([id, count]) => ({ card: byId[id], count }))
      .filter((x) => Boolean(x.card))
      .sort((a, b) => a.card.cost - b.card.cost || a.card.name.localeCompare(b.card.name));
  }, [run, byId]);

  const curve = useMemo(() => {
    const buckets = [0, 0, 0, 0, 0, 0, 0, 0];
    if (!run) return buckets;
    for (const id of run.deck) {
      const c = byId[id];
      if (c) buckets[Math.min(7, c.cost)]++;
    }
    return buckets;
  }, [run, byId]);
  const tallest = Math.max(1, ...curve);

  const typeCounts = useMemo(() => {
    let minions = 0;
    let spells = 0;
    let weapons = 0;
    if (run) {
      for (const id of run.deck) {
        const c = byId[id];
        if (!c) continue;
        if (c.type === 'MINION') minions++;
        else if (c.type === 'SPELL') spells++;
        else if (c.type === 'WEAPON') weapons++;
      }
    }
    return { minions, spells, weapons };
  }, [run, byId]);

  const liveMatch = useMemo(() => {
    if (!run?.activeGameId) return null;
    const found = games.find((g) => g.game_id === run.activeGameId);
    return found && found.phase !== 'GAME_OVER' ? found : null;
  }, [run, games]);

  const effectiveOpponent: OpponentMode =
    !serverUp && arena.preferredOpponent !== 'device'
      ? 'device'
      : arena.preferredOpponent === 'agent' && !agentInfo?.available
        ? 'device'
        : arena.preferredOpponent;

  const beginRun = () => {
    setErr('');
    setClaimedKey(null);
    setConfirmRetire(false);
    sfx.cue('uiClick');
    updateArenaState((s) => ({ ...s, run: startNewRun(heroClasses, pool) }));
  };

  const selectHero = (cls: string) => {
    setErr('');
    sfx.cue('uiClick');
    updateArenaState((s) => (s.run ? { ...s, run: chooseRunHero(s.run, cls, cards) } : s));
  };

  const selectCard = (cardId: string) => {
    setErr('');
    sfx.cue('cardPlay');
    updateArenaState((s) => (s.run ? { ...s, run: pickDraftCard(s.run, cardId, cards) } : s));
  };

  const queueMatch = async () => {
    if (!run || !run.heroClass || run.deck.length !== ARENA_DECK_SIZE) return;
    setBusy(true);
    setErr('');
    try {
      if (liveMatch) {
        await onResumeMatch(liveMatch.game_id);
        return;
      }
      const opp = draftOpponentDeck(cards, heroClasses, run.pool, run.wins);
      const recordTag = `${run.wins}-${run.losses}`;
      const level = effectiveOpponent === 'device' ? levelForArenaWins(run.wins, arena.preferredLevel) : undefined;
      const oppLabel =
        effectiveOpponent === 'device'
          ? `Arena ${pretty(opp.heroClass)} (${levels.find((l) => l.id === level)?.name || pretty(level || 'normal')})`
          : effectiveOpponent === 'agent'
            ? `Antigravity (${pretty(opp.heroClass)})`
            : `Arena ${pretty(opp.heroClass)}`;
      await onStartMatch({
        heroClass: run.heroClass,
        deck: run.deck,
        deckName: `Arena ${pretty(run.heroClass)} (${recordTag})`,
        opponentClass: opp.heroClass,
        opponentDeck: opp.cards,
        opponentDeckName: `Arena ${pretty(opp.heroClass)} (${recordTag})`,
        opponentName: oppLabel,
        p2Mode: effectiveOpponent,
        level,
        agentModel: effectiveOpponent === 'agent' ? agentInfo?.default : undefined,
      });
    } catch (e: any) {
      setErr(e?.message || 'Could not start Arena match.');
    } finally {
      setBusy(false);
    }
  };

  const handleRetire = () => {
    setConfirmRetire(false);
    sfx.cue('uiClick');
    updateArenaState((s) => (s.run ? { ...s, run: retireArenaRun(s.run) } : s));
  };

  const handleClaim = () => {
    let awarded: ArenaKey | null = null;
    updateArenaState((s) => {
      const res = claimRunRewards(s);
      if (!res) return s;
      awarded = res.key;
      return res.state;
    });
    if (awarded) {
      const key = awarded as ArenaKey;
      updateProfile((p) => grantArenaReward(p, key.packs, key.embers));
      setClaimedKey(key);
      sfx.cue('victory');
    }
  };

  const clearRun = () => {
    setClaimedKey(null);
    updateArenaState((s) => ({ ...s, run: null }));
  };

  const activeColor = run?.heroClass ? classColor(heroes, run.heroClass) : '#e6a844';
  const currentKey = arenaKeyFor(run?.wins ?? 0);
  const pickNumber = run ? run.deck.length + 1 : 1;
  const isGuaranteedRare = GUARANTEED_RARE_PICKS.has(pickNumber);
  const poolInfo = ARENA_POOLS.find((p) => p.id === (run?.pool || pool)) || ARENA_POOLS[0];

  const renderDeckSidebar = () => (
    <aside className={`panel builder-side ${drawerOpen ? 'is-open' : ''}`}>
      <button type="button" className="drawer-handle" onClick={() => setDrawerOpen((v) => !v)} aria-expanded={drawerOpen}>
        {run?.heroClass ? `Arena ${pretty(run.heroClass)}` : 'Drafted deck'}
        <span>
          {run?.deck.length || 0} / {ARENA_DECK_SIZE} <i>▲</i>
        </span>
      </button>
      <div className="arena-side-head">
        <strong>{run?.heroClass ? `Arena ${pretty(run.heroClass)}` : 'Arena Deck'}</strong>
        <span>{poolInfo.label}</span>
      </div>
      <div className="deck-meter">
        <strong>{run?.deck.length || 0}</strong> / {ARENA_DECK_SIZE}
        <div className="deck-meter-bar">
          <i style={{ width: `${((run?.deck.length || 0) / ARENA_DECK_SIZE) * 100}%` }} />
        </div>
      </div>

      <div className="curve" aria-label="Mana curve">
        {curve.map((n, i) => (
          <div key={i} className="curve-col">
            <span>{n || ''}</span>
            <div>
              <i style={{ height: `${(n / tallest) * 100}%` }} />
            </div>
            <em>{i === 7 ? '7+' : i}</em>
          </div>
        ))}
      </div>

      <div className="arena-types">
        <span>Minions <b>{typeCounts.minions}</b></span>
        <span>Spells <b>{typeCounts.spells}</b></span>
        <span>Weapons <b>{typeCounts.weapons}</b></span>
      </div>

      <ul className="deck-list">
        {deckEntries.map(({ card, count }) => (
          <li key={card.id}>
            <div className="arena-deck-row">
              <span className="dl-cost">{card.cost}</span>
              <span className="dl-name">{card.name}</span>
              <span className="dl-qty">{count > 1 ? `×${count}` : ''}</span>
            </div>
          </li>
        ))}
        {deckEntries.length === 0 && <li className="note">Pick cards on the left to build your 30-card Arena deck.</li>}
      </ul>
    </aside>
  );

  return (
    <div className="screen page arena-page" style={{ ['--class' as any]: activeColor }}>
      <header className="page-head">
        <button type="button" className="btn ghost" onClick={onBack}>
          ← Menu
        </button>
        <h1>Arena</h1>
        <span className="page-count">
          {arena.stats.totalRuns > 0
            ? `Best: ${arena.stats.bestWins} wins (${arenaKeyFor(arena.stats.bestWins).name})`
            : 'Draft 30 cards · Up to 12 wins'}
        </span>
      </header>

      {err && <div className="alert">{err}</div>}

      {/* ---- 1. Entry screen ---- */}
      {!run && (
        <div className="arena-entry panel">
          <div className="arena-entry-hero">
            <KeyIcon wins={Math.max(4, arena.stats.bestWins)} />
            <h2>Enter the Arena</h2>
            <p className="note">
              Choose 1 of 3 random heroes, draft a 30-card deck one pick at a time (duplicates allowed), and battle Arena-drafted opponents until
              12 wins or 3 losses. Earn Lanterns and Embers based on your final Key.
            </p>
          </div>

          <div className="arena-pool-grid" role="radiogroup" aria-label="Arena card pool">
            {ARENA_POOLS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                className={`arena-pool-btn ${pool === opt.id ? 'is-on' : ''}`}
                onClick={() => setPool(opt.id)}
              >
                <strong>{opt.label}</strong>
                <span>{opt.note}</span>
              </button>
            ))}
          </div>

          {arena.stats.totalRuns > 0 && (
            <div className="arena-stats-strip">
              <div>
                <span>Best run</span>
                <strong>{arena.stats.bestWins} wins</strong>
              </div>
              <div>
                <span>Total runs</span>
                <strong>{arena.stats.totalRuns}</strong>
              </div>
              <div>
                <span>Total wins</span>
                <strong>{arena.stats.totalWins}</strong>
              </div>
              <div>
                <span>12-win keys</span>
                <strong>{arena.stats.twelveWinRuns}</strong>
              </div>
            </div>
          )}

          <div className="arena-entry-actions">
            <button type="button" className="btn primary" onClick={beginRun}>
              Start Arena Run
            </button>
          </div>
        </div>
      )}

      {/* ---- 2. Choose 1 of 3 Heroes ---- */}
      {run && run.phase === 'picking_hero' && (
        <div className="arena-hero-pick panel">
          <div className="arena-stage-head">
            <h2>Choose your Hero</h2>
            <p className="note">Pool: {poolInfo.label} · Pick 1 of 3 classes to begin your 30-card draft.</p>
          </div>
          <div className="arena-hero-row">
            {run.heroChoices.map((cls) => {
              const h = heroes[cls];
              if (!h) return null;
              return (
                <button
                  key={cls}
                  type="button"
                  className="arena-hero-card"
                  style={{ ['--class' as any]: classColor(heroes, cls) }}
                  onClick={() => selectHero(cls)}
                >
                  <div className="arena-hero-art">
                    <Art id={`hero_${cls}`} />
                  </div>
                  <div className="arena-hero-meta">
                    <span className="arena-hero-class">{pretty(cls)}</span>
                    <strong>{h.name}</strong>
                    <em>{h.title}</em>
                  </div>
                </button>
              );
            })}
          </div>
          <div className="arena-hero-foot">
            <button type="button" className="btn ghost" onClick={clearRun}>
              Cancel run
            </button>
          </div>
        </div>
      )}

      {/* ---- 3. 30-Card Draft ---- */}
      {run && run.phase === 'drafting' && (
        <div className="builder arena-layout">
          <section className="panel arena-draft-main">
            <div className="arena-draft-head">
              <div>
                <h2>
                  Pick {pickNumber} of {ARENA_DECK_SIZE}
                </h2>
                <p className="note">
                  {isGuaranteedRare
                    ? 'Milestone pick — guaranteed Rare, Epic, or Legendary!'
                    : 'Choose 1 of 3 cards to add to your Arena deck.'}
                </p>
              </div>
              <span className={`arena-rarity-pill ${isGuaranteedRare ? 'is-milestone' : ''}`}>
                {run.currentChoices[0] && byId[run.currentChoices[0]]
                  ? pretty(byId[run.currentChoices[0]].rarity === 'FREE' ? 'COMMON' : byId[run.currentChoices[0]].rarity)
                  : 'Draft'}
              </span>
            </div>

            <div className="arena-pick-row">
              {run.currentChoices.map((cid) => {
                const card = byId[cid];
                if (!card) return null;
                return (
                  <button
                    key={cid}
                    type="button"
                    className="arena-pick-btn"
                    onClick={() => selectCard(cid)}
                    data-click-sound
                  >
                    <CardFace card={card} heroes={heroes} />
                    <span className="arena-pick-cta">Pick</span>
                  </button>
                );
              })}
            </div>

            <div className="arena-draft-foot">
              <button type="button" className="btn ghost" onClick={() => setConfirmRetire(true)}>
                Abandon draft
              </button>
            </div>
          </section>

          {renderDeckSidebar()}
        </div>
      )}

      {/* ---- 4. Run Hub (Playing or Complete) ---- */}
      {run && (run.phase === 'playing' || run.phase === 'complete') && (
        <div className="builder arena-layout">
          <section className="panel arena-hub-main">
            <div className="arena-scoreboard">
              <div className="arena-key-block">
                <KeyIcon wins={run.wins} />
                <div>
                  <span className="arena-key-kicker">
                    {run.phase === 'complete' ? 'Final Arena Key' : 'Current Arena Key'}
                  </span>
                  <h2>{currentKey.name}</h2>
                  <p className="note">
                    {run.wins} {run.wins === 1 ? 'Win' : 'Wins'} · {run.losses} {run.losses === 1 ? 'Loss' : 'Losses'}
                    {' · '}
                    Reward:{' '}
                    {currentKey.packs > 0 ? `${currentKey.packs} ${currentKey.packs === 1 ? 'Lantern' : 'Lanterns'} + ` : ''}
                    {currentKey.embers} Embers
                  </p>
                </div>
              </div>

              <div className="arena-pips-wrap">
                <div className="arena-win-pips" aria-label={`${run.wins} of ${ARENA_MAX_WINS} wins`}>
                  {Array.from({ length: ARENA_MAX_WINS }, (_, i) => (
                    <span key={i} className={`arena-win-pip ${i < run.wins ? 'is-on' : ''}`}>
                      {i + 1}
                    </span>
                  ))}
                </div>
                <div className="arena-loss-pips" aria-label={`${run.losses} of ${ARENA_MAX_LOSSES} losses`}>
                  {Array.from({ length: ARENA_MAX_LOSSES }, (_, i) => (
                    <span key={i} className={`arena-loss-pip ${i < run.losses ? 'is-on' : ''}`}>
                      ✕
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {run.phase === 'playing' ? (
              <>
                <div className="arena-opp-row">
                  <div className="arena-opp-group">
                    <label>Opponent</label>
                    <div className="seg">
                      <button
                        type="button"
                        className={effectiveOpponent === 'device' ? 'is-on' : ''}
                        onClick={() => updateArenaState((s) => ({ ...s, preferredOpponent: 'device' }))}
                      >
                        This device
                      </button>
                      {serverUp && (
                        <button
                          type="button"
                          className={effectiveOpponent === 'bot' ? 'is-on' : ''}
                          onClick={() => updateArenaState((s) => ({ ...s, preferredOpponent: 'bot' }))}
                        >
                          Practice bot
                        </button>
                      )}
                      {serverUp && agentInfo?.available && (
                        <button
                          type="button"
                          className={effectiveOpponent === 'agent' ? 'is-on' : ''}
                          onClick={() => updateArenaState((s) => ({ ...s, preferredOpponent: 'agent' }))}
                        >
                          Antigravity
                        </button>
                      )}
                    </div>
                  </div>

                  {effectiveOpponent === 'device' && (
                    <div className="arena-opp-group">
                      <label>Difficulty</label>
                      <div className="seg">
                        <button
                          type="button"
                          className={arena.preferredLevel === 'auto' ? 'is-on' : ''}
                          onClick={() => updateArenaState((s) => ({ ...s, preferredLevel: 'auto' }))}
                          title="Scales from Easy (0-2 wins) to Normal (3-6) to Hard (7+)"
                        >
                          Auto ({pretty(levelForArenaWins(run.wins, 'auto'))})
                        </button>
                        {levels.map((lv) => (
                          <button
                            key={lv.id}
                            type="button"
                            className={arena.preferredLevel === lv.id ? 'is-on' : ''}
                            onClick={() => updateArenaState((s) => ({ ...s, preferredLevel: lv.id }))}
                          >
                            {lv.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="arena-hub-actions">
                  <button type="button" className="btn primary" disabled={busy} onClick={() => void queueMatch()}>
                    {busy ? 'Starting match…' : liveMatch ? 'Resume Arena Match' : 'Play Next Match'}
                  </button>
                  <button type="button" className="btn ghost" disabled={busy} onClick={() => setConfirmRetire(true)}>
                    Retire Run
                  </button>
                </div>
              </>
            ) : (
              <div className="arena-complete-box">
                <h3>
                  {run.wins >= ARENA_MAX_WINS
                    ? '12 Wins! The Lightforge Key is yours!'
                    : `Run finished at ${run.wins}–${run.losses}`}
                </h3>
                {!run.claimed ? (
                  <>
                    <p className="note">
                      Open your {currentKey.name} chest to claim{' '}
                      {currentKey.packs > 0 ? (
                        <b>
                          {currentKey.packs} {currentKey.packs === 1 ? 'Lantern' : 'Lanterns'} and{' '}
                        </b>
                      ) : null}
                      <b>{currentKey.embers} Embers</b>.
                    </p>
                    <button type="button" className="btn primary" onClick={handleClaim}>
                      Claim {currentKey.name} Rewards
                    </button>
                  </>
                ) : (
                  <>
                    <p className="arena-reward-claimed">
                      Claimed:{' '}
                      {(claimedKey || currentKey).packs > 0
                        ? `${(claimedKey || currentKey).packs} ${(claimedKey || currentKey).packs === 1 ? 'Lantern' : 'Lanterns'} + `
                        : ''}
                      {(claimedKey || currentKey).embers} Embers added to your collection.
                    </p>
                    <div className="arena-hub-actions">
                      {profile.packs > 0 && (
                        <button type="button" className="btn primary" onClick={onOpenPack}>
                          Light a Lantern ({profile.packs})
                        </button>
                      )}
                      <button type="button" className={`btn ${profile.packs > 0 ? '' : 'primary'}`} onClick={clearRun}>
                        New Arena Run
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {run.history.length > 0 && (
              <div className="arena-history">
                <h3>Run Matches</h3>
                <ul>
                  {run.history.map((h, i) => (
                    <li key={h.gameId} className={`is-${h.result}`}>
                      <span className="ah-num">#{i + 1}</span>
                      <span className="ah-opp">{h.opponentName}</span>
                      <span className="ah-res">{h.result === 'win' ? 'Win' : h.result === 'loss' ? 'Loss' : 'Draw'}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>

          {renderDeckSidebar()}
        </div>
      )}

      {confirmRetire && run && (
        <div className="modal" onClick={() => setConfirmRetire(false)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h2>{run.phase === 'drafting' ? 'Abandon draft?' : 'Retire Arena run?'}</h2>
            <p className="sheet-sub">
              {run.phase === 'drafting'
                ? 'Your current draft will be discarded so you can start fresh.'
                : `You will finish at ${run.wins}–${run.losses} and claim the ${currentKey.name} rewards.`}
            </p>
            <div className="menu-list">
              <button
                type="button"
                className="btn danger"
                onClick={run.phase === 'drafting' ? () => { setConfirmRetire(false); clearRun(); } : handleRetire}
              >
                {run.phase === 'drafting' ? 'Abandon draft' : 'Retire & Claim Key'}
              </button>
              <button type="button" className="btn ghost" onClick={() => setConfirmRetire(false)}>
                Keep playing
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
