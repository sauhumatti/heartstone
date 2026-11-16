import React, { useEffect, useMemo, useState } from 'react';
import {
  attackTarget,
  concedeGame,
  endTurn,
  fetchGameState,
  playCard,
  resolveChoice,
  sendEmote,
  submitMulligan,
  switchMode,
  useHeroPower,
} from '../api';
import type { BoardMinion, GameStateView, HandCard, HeroMeta } from '../types';
import { FullCard, MinionToken } from './CardView';

interface BoardViewProps {
  gameId: string;
  initialState: GameStateView;
  heroes: Record<string, HeroMeta>;
  onLeaveToLobby: () => void;
}

interface PendingPlayState {
  card: HandCard;
  choose?: number;
  pos?: number;
  needsSlot: boolean;
  targetRule: string;
  validTargets: string[];
}

export const BoardView: React.FC<BoardViewProps> = ({
  gameId,
  initialState,
  heroes,
  onLeaveToLobby,
}) => {
  const [state, setState] = useState<GameStateView>(initialState);
  const [mulliganSwap, setMulliganSwap] = useState<Set<number>>(new Set());
  const [selectedAttacker, setSelectedAttacker] = useState<string | null>(null);
  const [pendingPlay, setPendingPlay] = useState<PendingPlayState | null>(null);
  const [usingPower, setUsingPower] = useState(false);
  const [hoveredMinion, setHoveredMinion] = useState<BoardMinion | null>(null);
  const [showLog, setShowLog] = useState(true);
  const [showEmotes, setShowEmotes] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [busy, setBusy] = useState(false);

  // Sync WebSocket + fallback polling safety
  useEffect(() => {
    let alive = true;
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;

    const connect = () => {
      if (!alive) return;
      ws = new WebSocket(`${proto}://${window.location.host}/ws/${gameId}/p1`);
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'state' && msg.state && alive) {
            setState(msg.state);
          }
        } catch {
          // ignore malformed packet
        }
      };
      ws.onclose = () => {
        if (alive) {
          reconnectTimer = window.setTimeout(connect, 1500);
        }
      };
    };
    connect();

    const pollId = window.setInterval(async () => {
      if (!alive) return;
      try {
        const fresh = await fetchGameState(gameId, 'p1');
        if (alive) setState(fresh);
      } catch {
        // ignore transient errors
      }
    }, 5000);

    return () => {
      alive = false;
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      window.clearInterval(pollId);
      ws?.close();
    };
  }, [gameId]);

  // ESC cancels targeting/selection
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedAttacker(null);
        setPendingPlay(null);
        setUsingPower(false);
        setErrorMsg('');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const clearSelection = () => {
    setSelectedAttacker(null);
    setPendingPlay(null);
    setUsingPower(false);
    setErrorMsg('');
  };

  const runAction = async (fn: () => Promise<GameStateView | void>) => {
    setBusy(true);
    setErrorMsg('');
    try {
      const next = await fn();
      if (next) setState(next);
      clearSelection();
    } catch (e: any) {
      setErrorMsg(e.message || 'Action failed');
    } finally {
      setBusy(false);
    }
  };

  // Compute active valid target IDs for highlighting
  const activeTargetSet = useMemo(() => {
    const s = new Set<string>();
    if (selectedAttacker) {
      if (selectedAttacker === state.me.hero.id) {
        (state.me.hero.legal_attack_targets || []).forEach((t) => s.add(t));
      } else {
        const m = state.me.board.find((x) => x.uid === selectedAttacker);
        (m?.legal_attack_targets || []).forEach((t) => s.add(t));
      }
    } else if (usingPower) {
      (state.me.hero.hero_power.valid_targets || []).forEach((t) => s.add(t));
    } else if (pendingPlay && !pendingPlay.needsSlot) {
      pendingPlay.validTargets.forEach((t) => s.add(t));
    }
    return s;
  }, [selectedAttacker, usingPower, pendingPlay, state]);

  const isTargetValid = (tid: string) => activeTargetSet.has(tid);

  // Hand card click -> choose one / slot / target / immediate play
  const handleHandCardClick = (c: HandCard) => {
    if (!state.your_turn || busy || state.pending_choice) return;
    if (!c.can_play) {
      setErrorMsg(c.unplayable_reason || 'Cannot play this card right now.');
      return;
    }
    clearSelection();

    if (c.choose_options.length > 0) {
      setPendingPlay({
        card: c,
        needsSlot: false,
        targetRule: 'CHOOSE',
        validTargets: [],
      });
      return;
    }

    const needsSlot = c.type === 'MINION' && state.me.board.length > 0;
    if (needsSlot || c.target_required) {
      setPendingPlay({
        card: c,
        needsSlot,
        targetRule: c.target_rule,
        validTargets: c.valid_targets,
      });
      return;
    }

    runAction(() => playCard(gameId, { hand_index: c.index, pos: 0 }));
  };

  const handleChooseOnePick = (optIdx: number) => {
    if (!pendingPlay) return;
    const opt = pendingPlay.card.choose_options[optIdx];
    if (!opt || !opt.playable) return;
    const c = pendingPlay.card;
    const needsSlot = c.type === 'MINION' && state.me.board.length > 0;
    const needsTarget = opt.target_rule !== 'NONE' && opt.valid_targets.length > 0;

    if (needsSlot || needsTarget) {
      setPendingPlay({
        card: c,
        choose: optIdx,
        needsSlot,
        targetRule: opt.target_rule,
        validTargets: opt.valid_targets,
      });
    } else {
      runAction(() => playCard(gameId, { hand_index: c.index, choose: optIdx, pos: 0 }));
    }
  };

  const handleSlotPick = (pos: number) => {
    if (!pendingPlay || !pendingPlay.needsSlot) return;
    const needsTarget = pendingPlay.validTargets.length > 0 && pendingPlay.targetRule !== 'NONE';
    if (needsTarget) {
      setPendingPlay({ ...pendingPlay, pos, needsSlot: false });
    } else {
      runAction(() =>
        playCard(gameId, {
          hand_index: pendingPlay.card.index,
          pos,
          choose: pendingPlay.choose,
        }),
      );
    }
  };

  const handleTargetClick = (tid: string) => {
    if (busy || !isTargetValid(tid)) return;
    if (selectedAttacker) {
      runAction(() => attackTarget(gameId, selectedAttacker, tid));
    } else if (usingPower) {
      runAction(() => useHeroPower(gameId, tid));
    } else if (pendingPlay && !pendingPlay.needsSlot) {
      runAction(() =>
        playCard(gameId, {
          hand_index: pendingPlay.card.index,
          pos: pendingPlay.pos,
          target_id: tid,
          choose: pendingPlay.choose,
        }),
      );
    }
  };

  const handleFriendlyMinionClick = (m: BoardMinion) => {
    if (isTargetValid(m.uid)) {
      handleTargetClick(m.uid);
      return;
    }
    if (!state.your_turn || busy || state.pending_choice) return;
    if (m.can_attack) {
      clearSelection();
      setSelectedAttacker(m.uid);
    }
  };

  const handleFriendlyHeroClick = () => {
    if (isTargetValid(state.me.hero.id)) {
      handleTargetClick(state.me.hero.id);
      return;
    }
    if (!state.your_turn || busy || state.pending_choice) return;
    if (state.me.hero.can_attack) {
      clearSelection();
      setSelectedAttacker(state.me.hero.id);
    }
  };

  const handleHeroPowerClick = () => {
    if (!state.your_turn || busy || state.pending_choice) return;
    const hp = state.me.hero.hero_power;
    if (!hp.can_use) return;
    clearSelection();
    if (hp.target_rule && hp.target_rule !== 'NONE') {
      setUsingPower(true);
    } else {
      runAction(() => useHeroPower(gameId));
    }
  };

  const toggleMulliganIdx = (idx: number) => {
    const next = new Set(mulliganSwap);
    if (next.has(idx)) next.delete(idx);
    else next.add(idx);
    setMulliganSwap(next);
  };

  const oppHeroColor = heroes[state.opponent.hero.card_class]?.color || '#666';
  const myHeroColor = heroes[state.me.hero.card_class]?.color || '#666';

  const guidanceText = useMemo(() => {
    if (selectedAttacker) return 'Select an attack target (ESC to cancel)';
    if (usingPower) return `Select target for ${state.me.hero.hero_power.name} (ESC to cancel)`;
    if (pendingPlay) {
      if (pendingPlay.needsSlot) {
        return `Choose board slot (+) for ${pendingPlay.card.name} (ESC to cancel)`;
      }
      if (pendingPlay.targetRule !== 'NONE' && pendingPlay.targetRule !== 'CHOOSE') {
        return `Select target for ${pendingPlay.card.name} (ESC to cancel)`;
      }
    }
    return '';
  }, [selectedAttacker, usingPower, pendingPlay, state.me.hero.hero_power.name]);

  const oppHeroImg = `/art/hero_${state.opponent.hero.is_jaraxxus ? 'JARAXXUS' : state.opponent.hero.card_class}.webp`;
  const myHeroImg = `/art/hero_${state.me.hero.is_jaraxxus ? 'JARAXXUS' : state.me.hero.card_class}.webp`;

  return (
    <div className="board-shell">
      <div
        className="board-main"
        style={{
          backgroundImage: `linear-gradient(180deg, rgba(22,14,9,0.72), rgba(22,14,9,0.58), rgba(22,14,9,0.78)), url('/art/board_bg.webp')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }}
      >
        {/* Top Opponent Bar */}
        <div className="player-strip opponent-strip">
          <div className="strip-left">
            <div className="deck-pill" title="Opponent Deck">
              🃏 Deck: {state.opponent.deck_count}
              {state.opponent.fatigue > 0 && <span className="fatigue-tag">Fatigue {state.opponent.fatigue}</span>}
            </div>
            <div className="mana-readout">
              💎 {state.opponent.mana}/{state.opponent.max_mana}
              {state.opponent.overloaded > 0 && <span className="overload-tag">🔒{state.opponent.overloaded}</span>}
            </div>
            <div className="opp-hand-backs" title={`Opponent holds ${state.opponent.hand_count} card(s)`}>
              {Array.from({ length: state.opponent.hand_count }).map((_, i) => (
                <img key={i} src="/art/card_back.webp" alt="Card Back" className="card-back-mini" />
              ))}
              <span className="hand-cnt-label">{state.opponent.hand_count}</span>
            </div>
          </div>

          <div className="hero-cluster">
            {state.opponent.weapon && (
              <div className="weapon-badge" title={state.opponent.weapon.text}>
                <img src={`/art/${state.opponent.weapon.card_id}.webp`} alt="" className="wep-thumb" />
                <div className="wep-name">{state.opponent.weapon.name}</div>
                <div className="wep-stats">⚔ {state.opponent.weapon.attack} / 🛡 {state.opponent.weapon.durability}</div>
              </div>
            )}

            <div
              className={[
                'hero-portrait',
                state.active_seat === 'p2' && state.phase === 'PLAY' ? 'hero-active' : '',
                isTargetValid(state.opponent.hero.id) ? 'hero-targetable' : '',
                state.opponent.hero.frozen ? 'hero-frozen' : '',
                state.opponent.hero.immune ? 'hero-immune' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              style={{
                borderColor: oppHeroColor,
                backgroundImage: `linear-gradient(180deg, rgba(16,11,8,0.22) 0%, rgba(16,11,8,0.82) 100%), url('${oppHeroImg}')`,
                backgroundSize: 'cover',
                backgroundPosition: 'center top',
              }}
              onClick={() => handleTargetClick(state.opponent.hero.id)}
            >
              <div className="hero-class-tag" style={{ backgroundColor: oppHeroColor }}>
                {state.opponent.hero.card_class}
              </div>
              <div className="hero-name">{state.opponent.hero.name}</div>
              <div className="hero-sub">{state.opponent.name}</div>
              {state.opponent.hero.attack > 0 && (
                <div className="hero-atk-gem">{state.opponent.hero.attack}</div>
              )}
              {state.opponent.hero.armor > 0 && (
                <div className="hero-armor-gem">{state.opponent.hero.armor}</div>
              )}
              <div className="hero-hp-gem">{state.opponent.hero.hp}</div>

              {state.opponent.secrets.length > 0 && (
                <div className="secrets-orbit">
                  {state.opponent.secrets.map((sec) => (
                    <span
                      key={sec.uid}
                      className={`secret-orb secret-${sec.card_class.toLowerCase()}`}
                      title={`Secret (${sec.card_class})`}
                    >
                      ?
                    </span>
                  ))}
                </div>
              )}

              {state.last_emote && state.last_emote.seat === 'p2' && (
                <div className="emote-bubble" key={state.last_emote.id}>
                  {state.last_emote.text}
                </div>
              )}
            </div>

            <div
              className="hero-power-box disabled"
              title={state.opponent.hero.hero_power.text}
              style={{
                backgroundImage: `linear-gradient(180deg, rgba(20,14,10,0.35), rgba(20,14,10,0.85)), url('/art/${state.opponent.hero.hero_power.id}.webp')`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
              }}
            >
              <div className="hp-cost">2</div>
              <div className="hp-title">{state.opponent.hero.hero_power.name}</div>
              <div className="hp-status">{state.opponent.hero.hero_power.used ? 'Used' : 'Ready'}</div>
            </div>
          </div>

          <div className="strip-right">
            <span className="game-id-chip">Game #{state.game_id}</span>
            <span className="mode-chip">
              {state.mode === 'cli_vs_human' ? 'vs Antigravity (CLI)' : 'vs Practice Bot'}
            </span>
          </div>
        </div>

        {/* Enemy Board */}
        <div className="battlefield-row enemy-board">
          {state.opponent.board.length === 0 ? (
            <div className="board-empty-hint">Enemy Battlefield</div>
          ) : (
            state.opponent.board.map((m) => (
              <MinionToken
                key={m.uid}
                minion={m}
                isFriendly={false}
                isSelectedAttacker={false}
                isValidTarget={isTargetValid(m.uid)}
                onClick={() => handleTargetClick(m.uid)}
                onHover={setHoveredMinion}
              />
            ))
          )}
        </div>

        {/* Center Divider & Turn Controls */}
        <div className="center-divider">
          <div className="turn-status">
            {state.phase === 'PLAY' && (
              <span className={state.your_turn ? 'turn-badge mine' : 'turn-badge theirs'}>
                {state.your_turn
                  ? `TURN ${state.turn_number} · YOUR TURN`
                  : state.mode === 'cli_vs_human'
                    ? `TURN ${state.turn_number} · WAITING FOR ANTIGRAVITY (./hs)`
                    : `TURN ${state.turn_number} · BOT TURN`}
              </span>
            )}
            {state.nozdormu_active && <span className="noz-badge">⏳ Nozdormu Active (15s)</span>}
            {guidanceText && (
              <span className="guidance-badge">
                {guidanceText}{' '}
                <button className="btn-link" onClick={clearSelection}>
                  Cancel
                </button>
              </span>
            )}
            {errorMsg && <span className="inline-error">{errorMsg}</span>}
          </div>

          <div className="center-actions">
            {state.phase === 'PLAY' && (
              <button
                className={state.your_turn ? 'btn-end-turn active' : 'btn-end-turn'}
                disabled={!state.your_turn || busy || Boolean(state.pending_choice)}
                onClick={() => runAction(() => endTurn(gameId))}
              >
                {state.your_turn ? 'End Turn' : "Opponent's Turn"}
              </button>
            )}
            <button className="btn-xs" onClick={() => setShowLog((v) => !v)}>
              {showLog ? 'Hide Log' : 'Show Log'}
            </button>
            <div className="emote-wrap">
              <button className="btn-xs" onClick={() => setShowEmotes((v) => !v)}>
                Emote
              </button>
              {showEmotes && (
                <div className="emote-menu">
                  {['Greetings', 'Well Played', 'Thanks', 'Oops', 'Threaten'].map((msg) => (
                    <button
                      key={msg}
                      onClick={() => {
                        setShowEmotes(false);
                        sendEmote(gameId, msg);
                      }}
                    >
                      {msg}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button
              className="btn-xs"
              title="Toggle between Antigravity CLI opponent and instant Practice Bot"
              onClick={() =>
                runAction(() => switchMode(gameId, state.mode === 'cli_vs_human' ? 'bot' : 'cli'))
              }
            >
              {state.mode === 'cli_vs_human' ? 'Switch to Bot' : 'Switch to CLI'}
            </button>
            <button
              className="btn-xs btn-danger-xs"
              onClick={() => runAction(() => concedeGame(gameId))}
            >
              Concede
            </button>
            <button className="btn-xs" onClick={onLeaveToLobby}>
              Lobby
            </button>
          </div>
        </div>

        {/* Friendly Board (with optional + insertion slots when playing a minion) */}
        <div className="battlefield-row friendly-board">
          {pendingPlay?.needsSlot && (
            <button className="slot-inserter" onClick={() => handleSlotPick(0)} title="Place here">
              +
            </button>
          )}
          {state.me.board.length === 0 && !pendingPlay?.needsSlot && (
            <div className="board-empty-hint">Your Battlefield</div>
          )}
          {state.me.board.map((m, idx) => (
            <React.Fragment key={m.uid}>
              <MinionToken
                minion={m}
                isFriendly
                isSelectedAttacker={selectedAttacker === m.uid}
                isValidTarget={isTargetValid(m.uid)}
                onClick={() => handleFriendlyMinionClick(m)}
                onHover={setHoveredMinion}
              />
              {pendingPlay?.needsSlot && (
                <button
                  className="slot-inserter"
                  onClick={() => handleSlotPick(idx + 1)}
                  title="Place here"
                >
                  +
                </button>
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Bottom Player Hero & Mana Tray */}
        <div className="player-strip friendly-strip">
          <div className="strip-left">
            <div className="deck-pill">
              🃏 Deck: {state.me.deck_count}
              {state.me.fatigue > 0 && <span className="fatigue-tag">Fatigue {state.me.fatigue}</span>}
            </div>
            {state.me.spell_damage > 0 && (
              <div className="sd-pill">🔮 Spell Damage +{state.me.spell_damage}</div>
            )}
            {state.me.combo_active && <div className="combo-pill">⚡ Combo Ready</div>}
          </div>

          <div className="hero-cluster">
            {state.me.weapon && (
              <div className="weapon-badge" title={state.me.weapon.text}>
                <img src={`/art/${state.me.weapon.card_id}.webp`} alt="" className="wep-thumb" />
                <div className="wep-name">{state.me.weapon.name}</div>
                <div className="wep-stats">⚔ {state.me.weapon.attack} / 🛡 {state.me.weapon.durability}</div>
              </div>
            )}

            <div
              className={[
                'hero-portrait',
                state.your_turn ? 'hero-active' : '',
                state.me.hero.can_attack ? 'hero-can-attack' : '',
                selectedAttacker === state.me.hero.id ? 'minion-selected' : '',
                isTargetValid(state.me.hero.id) ? 'hero-targetable' : '',
                state.me.hero.frozen ? 'hero-frozen' : '',
                state.me.hero.immune ? 'hero-immune' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              style={{
                borderColor: myHeroColor,
                backgroundImage: `linear-gradient(180deg, rgba(16,11,8,0.22) 0%, rgba(16,11,8,0.82) 100%), url('${myHeroImg}')`,
                backgroundSize: 'cover',
                backgroundPosition: 'center top',
              }}
              onClick={handleFriendlyHeroClick}
            >
              <div className="hero-class-tag" style={{ backgroundColor: myHeroColor }}>
                {state.me.hero.card_class}
              </div>
              <div className="hero-name">{state.me.hero.name}</div>
              <div className="hero-sub">{state.me.name}</div>
              {state.me.hero.attack > 0 && <div className="hero-atk-gem">{state.me.hero.attack}</div>}
              {state.me.hero.armor > 0 && <div className="hero-armor-gem">{state.me.hero.armor}</div>}
              <div className="hero-hp-gem">{state.me.hero.hp}</div>

              {state.me.secrets.length > 0 && (
                <div className="secrets-orbit">
                  {state.me.secrets.map((sec) => (
                    <span
                      key={sec.uid}
                      className={`secret-orb secret-${sec.card_class.toLowerCase()}`}
                      title={sec.name}
                    >
                      ?
                    </span>
                  ))}
                </div>
              )}

              {state.last_emote && state.last_emote.seat === 'p1' && (
                <div className="emote-bubble" key={state.last_emote.id}>
                  {state.last_emote.text}
                </div>
              )}
            </div>

            <button
              type="button"
              className={
                state.me.hero.hero_power.can_use ? 'hero-power-box ready' : 'hero-power-box disabled'
              }
              style={{
                backgroundImage: `linear-gradient(180deg, rgba(20,14,10,0.35), rgba(20,14,10,0.85)), url('/art/${state.me.hero.hero_power.id}.webp')`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
              }}
              onClick={handleHeroPowerClick}
              title={state.me.hero.hero_power.text}
            >
              <div className="hp-cost">2</div>
              <div className="hp-title">{state.me.hero.hero_power.name}</div>
              <div className="hp-status">
                {state.me.hero.hero_power.used
                  ? 'Used'
                  : state.me.hero.hero_power.can_use
                    ? 'Click'
                    : 'Locked'}
              </div>
            </button>
          </div>

          <div className="mana-tray">
            <div className="mana-numbers">
              {state.me.mana}/{state.me.max_mana}
              {state.me.pending_overload > 0 && (
                <span className="overload-tag" title="Locked next turn">
                  Next 🔒{state.me.pending_overload}
                </span>
              )}
            </div>
            <div className="mana-gems">
              {Array.from({ length: state.me.max_mana }).map((_, i) => {
                const filled = i < state.me.mana;
                const overloaded = !filled && i >= state.me.max_mana - state.me.overloaded;
                return (
                  <span
                    key={i}
                    className={
                      filled ? 'crystal filled' : overloaded ? 'crystal overloaded' : 'crystal empty'
                    }
                  >
                    {overloaded ? '🔒' : '◆'}
                  </span>
                );
              })}
            </div>
          </div>
        </div>

        {/* Player Hand */}
        <div className="hand-tray">
          {state.me.hand.map((c) => (
            <FullCard
              key={c.uid}
              card={c}
              selected={pendingPlay?.card.uid === c.uid}
              onClick={() => handleHandCardClick(c)}
            />
          ))}
        </div>
      </div>

      {/* Side Panel: Hovered Minion Inspector & Combat Log */}
      {(showLog || hoveredMinion) && (
        <aside className="board-sidebar">
          {hoveredMinion && (
            <div className="inspector-box">
              <div className="inspector-title">
                {hoveredMinion.name} ({hoveredMinion.attack}/{hoveredMinion.health})
              </div>
              {hoveredMinion.race && <div className="inspector-race">{hoveredMinion.race}</div>}
              <div className="inspector-text">
                {hoveredMinion.silenced ? 'Silenced.' : hoveredMinion.text || 'No card text.'}
              </div>
              {hoveredMinion.enchantments.length > 0 && (
                <div className="inspector-ench">
                  <strong>Enchantments:</strong> {hoveredMinion.enchantments.join(', ')}
                </div>
              )}
            </div>
          )}

          {showLog && (
            <div className="combat-log">
              <h4>Combat Log</h4>
              <div className="log-entries">
                {[...state.log].reverse().map((entry) => (
                  <div key={entry.id} className="log-row">
                    {entry.text}
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>
      )}

      {/* Waiting for Antigravity P2 Deck Overlay */}
      {state.phase === 'WAITING_FOR_P2_DECK' && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h2>Waiting for Antigravity to Choose a Deck</h2>
            <p>
              Game <code>{state.game_id}</code> is ready. Antigravity can pick a deck via CLI:
            </p>
            <pre className="code-block">./hs deck MAGE</pre>
            <button className="btn-secondary" onClick={onLeaveToLobby}>
              Back to Lobby
            </button>
          </div>
        </div>
      )}

      {/* Mulligan Overlay */}
      {state.phase === 'MULLIGAN' && (
        <div className="modal-backdrop">
          <div className="modal-card modal-wide">
            {!state.me.mulligan_done ? (
              <>
                <h2>Opening Hand Mulligan</h2>
                <p className="muted">
                  Click cards you want to replace before the match begins.
                  {state.me.hand.length === 4 ? ' (You are going 2nd and will receive The Coin!)' : ' (You are going 1st.)'}
                </p>
                <div className="mulligan-cards">
                  {state.me.hand.map((c) => (
                    <FullCard
                      key={c.uid}
                      card={c}
                      replaced={mulliganSwap.has(c.index)}
                      onClick={() => toggleMulliganIdx(c.index)}
                    />
                  ))}
                </div>
                <div className="modal-actions">
                  <button
                    className="btn-primary btn-lg"
                    disabled={busy}
                    onClick={() =>
                      runAction(() => submitMulligan(gameId, Array.from(mulliganSwap)))
                    }
                  >
                    Confirm Mulligan ({mulliganSwap.size} replaced)
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2>Mulligan Submitted!</h2>
                <p className="muted">
                  Waiting for {state.opponent.name} to finish mulligan (<code>./hs mulligan ...</code>)...
                </p>
              </>
            )}
          </div>
        </div>
      )}

      {/* Choose One Modal */}
      {pendingPlay && pendingPlay.targetRule === 'CHOOSE' && (
        <div className="modal-backdrop" onClick={clearSelection}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h3>Choose One — {pendingPlay.card.name}</h3>
            <div className="choose-grid">
              {pendingPlay.card.choose_options.map((opt) => (
                <button
                  key={opt.index}
                  className={opt.playable ? 'choose-option-btn' : 'choose-option-btn disabled'}
                  disabled={!opt.playable}
                  onClick={() => handleChooseOnePick(opt.index)}
                >
                  <div className="choose-title">{opt.label}</div>
                  <div className="choose-desc">{opt.description}</div>
                </button>
              ))}
            </div>
            <button className="btn-secondary" onClick={clearSelection} style={{ marginTop: '1rem' }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Tracking / Pending Choice Modal */}
      {state.pending_choice && (
        <div className="modal-backdrop">
          <div className="modal-card modal-wide">
            <h2>Tracking — Choose a Card to Draw</h2>
            <p className="muted">The other two cards will be discarded.</p>
            <div className="mulligan-cards">
              {state.pending_choice.options.map((opt, idx) => (
                <FullCard
                  key={opt.uid}
                  card={opt}
                  onClick={() => runAction(() => resolveChoice(gameId, idx))}
                />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Game Over Modal */}
      {state.phase === 'GAME_OVER' && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <h2>
              {state.winner === 'p1'
                ? '🏆 VICTORY!'
                : state.winner === 'p2'
                  ? '💀 DEFEAT'
                  : '⚔ DRAW'}
            </h2>
            <p className="muted">
              {state.winner === 'p1'
                ? 'You defeated your opponent!'
                : state.winner === 'p2'
                  ? `${state.opponent.name} won the match.`
                  : 'Both heroes fell simultaneously.'}
            </p>
            <div className="modal-actions">
              <button className="btn-primary" onClick={onLeaveToLobby}>
                Return to Lobby
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
