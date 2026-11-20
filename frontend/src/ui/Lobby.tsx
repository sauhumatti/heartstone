import React, { useEffect, useState } from 'react';
import { fetchAgentInfo } from '../api';
import { startRuntime } from '../local/client';
import { HAS_SERVER } from '../paths';
import type { AgentInfo, DeckInfo, GameSummary, HeroMeta, Level, OpponentMode } from '../types';
import { formatDelta, nextRating, OPPONENTS, opponentOf } from '../progress/rules';
import { useProfile } from '../progress/store';
import { runtimeLine, useRuntime } from './Offline';
import { Art, classColor, pretty } from './pieces';

interface LobbyProps {
  heroes: Record<string, HeroMeta>;
  decks: DeckInfo[];
  games: GameSummary[];
  /** Can the game server be reached? Without it the only opponent is the one on this device. */
  serverUp: boolean;
  /** How strong the opponent on this device can play. */
  levels: Level[];
  standardLevel: string;
  onStartGame: (opts: {
    p1Name: string;
    p1DeckId: string;
    p2Mode: OpponentMode;
    p2DeckChoice: string;
    agentModel?: string;
    level?: string;
  }) => Promise<void>;
  onResumeGame: (gameId: string) => void;
  onOpenDeckbuilder: () => void;
  onBack: () => void;
}

const NAME_KEY = 'player_name';
const MODE_KEY = 'opponent_mode';
const MODEL_KEY = 'agent_model';
const LEVEL_KEY = 'device_level';

const MODE_LABEL: Record<string, string> = {
  agent_vs_human: 'vs Antigravity',
  cli_vs_human: 'vs command line',
  bot_vs_human: 'vs bot',
  ai_vs_human: 'on this device',
};

function storedMode(): OpponentMode | null {
  const v = localStorage.getItem(MODE_KEY);
  return v === 'bot' || v === 'agent' || v === 'cli' || v === 'device' ? v : null;
}

export const Lobby: React.FC<LobbyProps> = ({
  heroes,
  decks,
  games,
  serverUp,
  levels,
  standardLevel,
  onStartGame,
  onResumeGame,
  onOpenDeckbuilder,
  onBack,
}) => {
  const [name, setName] = useState(() => localStorage.getItem(NAME_KEY) || 'Player');
  const [deckId, setDeckId] = useState<string>(decks[0]?.id || '');
  const [deckTab, setDeckTab] = useState<'all' | 'golden' | 'classic'>('golden');
  const [chosenMode, setMode] = useState<OpponentMode>(() => storedMode() ?? 'bot');
  const [agentInfo, setAgentInfo] = useState<AgentInfo | null>(null);
  const [agentModel, setAgentModel] = useState(() => localStorage.getItem(MODEL_KEY) || '');
  const [chosenLevel, setLevel] = useState(() => localStorage.getItem(LEVEL_KEY) || '');
  const [oppDeck, setOppDeck] = useState('random');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [showCli, setShowCli] = useState(false);
  const runtime = useRuntime();
  const profile = useProfile();

  // Every other opponent lives on the server.
  const mode: OpponentMode = serverUp ? chosenMode : 'device';
  const level = levels.some((l) => l.id === chosenLevel) ? chosenLevel : standardLevel;

  useEffect(() => {
    if (!serverUp) return;
    let alive = true;
    fetchAgentInfo()
      .then((info) => {
        if (!alive) return;
        setAgentInfo(info);
        setAgentModel((cur) => (info.models.some((m) => m.id === cur) ? cur : info.default));
        // With no choice made before, the agent is the opponent when it is there.
        if (!storedMode() && info.available) setMode('agent');
      })
      .catch(() => alive && setAgentInfo({ available: false, default: '', models: [] }));
    return () => {
      alive = false;
    };
  }, [serverUp]);

  // Playing on this device: start the engine now, so it is ready when the match starts.
  useEffect(() => {
    if (mode === 'device') void startRuntime().catch(() => undefined);
  }, [mode]);

  // A deck or an opponent's deck that is no longer on offer (the server went away) falls back.
  useEffect(() => {
    if (decks.length && !decks.some((d) => d.id === deckId)) setDeckId(decks[0].id);
    if (oppDeck !== 'random' && oppDeck !== 'await_cli' && !decks.some((d) => d.id === oppDeck)) setOppDeck('random');
  }, [decks, deckId, oppDeck]);

  const agentMissing = mode === 'agent' && agentInfo !== null && !agentInfo.available;
  // What the match is worth to the player's rating, against the opponent chosen.
  const rated = opponentOf(mode === 'device' ? 'ai_vs_human' : mode === 'bot' ? 'bot_vs_human' : mode === 'agent' ? 'agent_vs_human' : 'cli_vs_human', level);
  const stake = rated
    ? `Rated ${OPPONENTS[rated].rating}. A win is ${formatDelta(profile.rating, nextRating(profile.rating, OPPONENTS[rated].rating, 'win', profile.played))} to your rating, a loss ${formatDelta(profile.rating, nextRating(profile.rating, OPPONENTS[rated].rating, 'loss', profile.played))}.${OPPONENTS[rated].steps > 1 ? ' A win counts twice towards a lantern.' : ''}`
    : 'Not rated: this match does not move your rating or earn lanterns.';
  // The server knows its own decks and the starter decks; a deck kept on this device it has never seen.
  const theirDecks = mode === 'device' ? decks : decks.filter((d) => !d.device);

  const start = async () => {
    setBusy(true);
    setError('');
    const clean = name.trim() || 'Player';
    localStorage.setItem(NAME_KEY, clean);
    if (serverUp) localStorage.setItem(MODE_KEY, mode);
    if (agentModel) localStorage.setItem(MODEL_KEY, agentModel);
    if (mode === 'device') localStorage.setItem(LEVEL_KEY, level);
    const theirs = oppDeck === 'await_cli' && (mode === 'bot' || mode === 'device') ? 'random' : oppDeck;
    try {
      await onStartGame({
        p1Name: clean,
        p1DeckId: deckId,
        p2Mode: mode,
        p2DeckChoice: theirDecks.some((d) => d.id === theirs) || theirs === 'await_cli' ? theirs : 'random',
        agentModel: mode === 'agent' ? agentModel || undefined : undefined,
        level: mode === 'device' ? level : undefined,
      });
    } catch (e: any) {
      setError(e?.message || 'Could not start the match.');
    } finally {
      setBusy(false);
    }
  };

  const hasGolden = decks.some((d) => d.era === 'golden');
  const shownDecks = !hasGolden || deckTab === 'all'
    ? decks
    : deckTab === 'golden'
      ? decks.filter((d) => d.era === 'golden' || !d.builtin)
      : decks.filter((d) => d.era !== 'golden' && d.builtin);

  return (
    <div className="screen page">
      <header className="page-head">
        <button type="button" className="btn ghost" onClick={onBack}>
          ← Menu
        </button>
        <h1>New match</h1>
        <button type="button" className="btn ghost" onClick={onOpenDeckbuilder}>
          Collection
        </button>
      </header>

      <div className="lobby">
        <section className="panel">
          <div className="panel-head">
            <h2>Your deck</h2>
            {hasGolden && (
              <div className="seg" role="tablist" aria-label="Deck era">
                <button type="button" className={deckTab === 'golden' ? 'is-on' : ''} onClick={() => setDeckTab('golden')}>
                  Golden Era
                </button>
                <button type="button" className={deckTab === 'classic' ? 'is-on' : ''} onClick={() => setDeckTab('classic')}>
                  Classic
                </button>
                <button type="button" className={deckTab === 'all' ? 'is-on' : ''} onClick={() => setDeckTab('all')}>
                  All
                </button>
              </div>
            )}
          </div>
          <div className="deck-grid">
            {shownDecks.map((d) => {
              const color = classColor(heroes, d.hero_class);
              return (
                <button
                  key={d.id}
                  type="button"
                  className={`deck-tile ${d.id === deckId ? 'is-on' : ''}`}
                  style={{ ['--class' as any]: color }}
                  onClick={() => setDeckId(d.id)}
                >
                  <div className="deck-tile-art">
                    <Art id={`hero_${d.hero_class}`} tint={color} />
                  </div>
                  <span className="deck-tile-gem" aria-hidden="true" />
                  <div className="deck-tile-body">
                    <span className="deck-tile-class">
                      {pretty(d.hero_class)}
                      {!d.builtin ? <em>{d.device ? 'on this device' : 'custom'}</em> : d.era === 'golden' && deckTab === 'all' ? <em>Golden Era</em> : null}
                    </span>
                    <strong>{d.name}</strong>
                    <span className="deck-tile-desc">{d.description || `${d.cards.length} cards`}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        <aside className="panel lobby-side">
          <h2>Opponent</h2>
          {serverUp && (
            <div className="seg seg-wide seg-pairs" role="tablist">
              <button type="button" className={mode === 'device' ? 'is-on' : ''} onClick={() => setMode('device')}>
                This device
              </button>
              <button type="button" className={mode === 'agent' ? 'is-on' : ''} onClick={() => setMode('agent')}>
                Antigravity
              </button>
              <button type="button" className={mode === 'bot' ? 'is-on' : ''} onClick={() => setMode('bot')}>
                Practice bot
              </button>
              <button type="button" className={mode === 'cli' ? 'is-on' : ''} onClick={() => setMode('cli')}>
                Command line
              </button>
            </div>
          )}
          <p className="note">
            {mode === 'device'
              ? `${serverUp || !HAS_SERVER ? '' : 'The game server cannot be reached. '}A built-in opponent that plays on this device and needs no connection. It sees only what a player would see.`
              : mode === 'agent'
                ? 'Gemini 4 Hydrogen plays the other side through the Antigravity CLI. It sees only what a player would see and thinks for a few seconds per move.'
                : mode === 'bot'
                  ? 'A simple opponent on the server that plays its turns straight away. Good for trying decks.'
                  : 'The other seat is left open for whoever plays it through ./hs or the local HTTP API.'}
          </p>
          {mode === 'device' && levels.length > 0 && (
            <div className="seg seg-wide" role="tablist" aria-label="How strong it plays">
              {levels.map((l) => (
                <button key={l.id} type="button" className={l.id === level ? 'is-on' : ''} title={l.name} onClick={() => setLevel(l.id)}>
                  {l.label}
                </button>
              ))}
            </div>
          )}
          <p className="note stake">{stake}</p>
          {mode === 'device' && runtime.phase !== 'ready' && runtime.phase !== 'idle' && (
            <p className={runtime.phase === 'failed' ? 'alert' : 'note'}>{runtimeLine(runtime)}</p>
          )}
          {agentMissing && <div className="alert">The Antigravity CLI (agy) was not found on this machine.</div>}
          {mode === 'agent' && agentInfo && agentInfo.models.length > 0 && (
            <label className="field">
              <span>Model</span>
              <select value={agentModel} onChange={(e) => setAgentModel(e.target.value)}>
                {agentInfo.models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label className="field">
            <span>Their deck</span>
            <select value={oppDeck} onChange={(e) => setOppDeck(e.target.value)}>
              <option value="random">Random</option>
              {mode === 'agent' && <option value="await_cli">Let Gemini choose</option>}
              {mode === 'cli' && <option value="await_cli">Chosen from the command line (./hs deck …)</option>}
              {theirDecks.map((d) => (
                <option key={d.id} value={d.id}>
                  {pretty(d.hero_class)} · {d.name}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Your name</span>
            <input type="text" value={name} maxLength={24} onChange={(e) => setName(e.target.value)} />
          </label>

          {error && <div className="alert">{error}</div>}

          <button type="button" className="btn primary big" disabled={busy || !deckId || agentMissing} onClick={start}>
            {busy ? 'Dealing…' : 'Start match'}
          </button>

          {games.length > 0 && (
            <>
              <h3>Matches</h3>
              <ul className="match-list">
                {games.slice(0, 6).map((g) => (
                  <li key={g.game_id}>
                    <div>
                      <strong>
                        {pretty(g.p1.hero_class)} {g.p1.hp} · {pretty(g.p2.hero_class)} {g.p2.hp}
                      </strong>
                      <span>
                        {MODE_LABEL[g.mode] || g.mode} ·{' '}
                        {g.phase === 'GAME_OVER'
                          ? g.winner === 'p1'
                            ? 'won'
                            : g.winner === 'draw'
                              ? 'draw'
                              : 'lost'
                          : g.turn_number > 0
                            ? `turn ${g.turn_number}`
                            : 'starting'}
                      </span>
                    </div>
                    <button type="button" className="btn ghost small" onClick={() => onResumeGame(g.game_id)}>
                      {g.phase === 'GAME_OVER' ? 'View' : 'Resume'}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}

          {mode === 'cli' && (
            <button type="button" className="link" onClick={() => setShowCli((v) => !v)}>
              {showCli ? 'Hide' : 'Show'} command line reference
            </button>
          )}
          {mode === 'cli' && showCli && (
            <pre className="code">
              {`./hs wait                    wait for your turn
./hs status                  board and hand
./hs deck MAGE               choose a deck
./hs mulligan 0 2            swap opening cards
./hs play 0 --pos 1          play a card
./hs play 0 --target e0      play at a target
./hs attack m0 enemy_hero    attack
./hs power --target e0       hero power
./hs end                     end turn`}
            </pre>
          )}
        </aside>
      </div>
    </div>
  );
};
