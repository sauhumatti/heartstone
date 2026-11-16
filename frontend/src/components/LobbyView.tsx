import React, { useState } from 'react';
import type { DeckInfo, GameSummary, HeroMeta } from '../types';

interface LobbyViewProps {
  heroes: Record<string, HeroMeta>;
  decks: DeckInfo[];
  games: GameSummary[];
  onStartGame: (opts: {
    p1Name: string;
    p1DeckId: string;
    p2Mode: 'cli' | 'bot';
    p2DeckChoice: string;
  }) => Promise<void>;
  onResumeGame: (gameId: string) => void;
  onOpenDeckbuilder: () => void;
}

export const LobbyView: React.FC<LobbyViewProps> = ({
  heroes,
  decks,
  games,
  onStartGame,
  onResumeGame,
  onOpenDeckbuilder,
}) => {
  const [playerName, setPlayerName] = useState('Player');
  const [selectedDeckId, setSelectedDeckId] = useState<string>(decks[0]?.id || 'starter_mage');
  const [opponentMode, setOpponentMode] = useState<'cli' | 'bot'>('cli');
  const [p2DeckChoice, setP2DeckChoice] = useState<string>('random');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const handleStart = async () => {
    setBusy(true);
    setError('');
    try {
      await onStartGame({
        p1Name: playerName.trim() || 'Player',
        p1DeckId: selectedDeckId,
        p2Mode: opponentMode,
        p2DeckChoice,
      });
    } catch (e: any) {
      setError(e.message || 'Failed to create game');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="lobby-grid">
      <section className="tavern-panel">
        <div className="panel-header">
          <div>
            <h2>Enter the Tavern</h2>
            <p className="muted">Original 2014 Basic + Classic Hearthstone (382 cards). Local only, zero online play.</p>
          </div>
          <button className="btn-secondary" onClick={onOpenDeckbuilder}>
            Collection & Deckbuilder
          </button>
        </div>

        <div className="form-row">
          <label>
            Your Name
            <input
              type="text"
              value={playerName}
              onChange={(e) => setPlayerName(e.target.value)}
              maxLength={24}
              placeholder="Player"
            />
          </label>

          <label>
            Opponent
            <div className="mode-pills">
              <button
                type="button"
                className={opponentMode === 'cli' ? 'pill active' : 'pill'}
                onClick={() => setOpponentMode('cli')}
              >
                Antigravity (CLI / API)
              </button>
              <button
                type="button"
                className={opponentMode === 'bot' ? 'pill active' : 'pill'}
                onClick={() => setOpponentMode('bot')}
              >
                Practice Bot (Local AI)
              </button>
            </div>
          </label>
        </div>

        <div className="opponent-note">
          {opponentMode === 'cli' ? (
            <>
              <strong>Antigravity CLI/API Mode:</strong> You play in this browser while Antigravity inspects its fair-play
              board state and plays turns via <code>./hs</code> CLI or local HTTP API.
            </>
          ) : (
            <>
              <strong>Practice Bot Mode:</strong> Instant local AI opponent using the exact same rules engine for solo testing.
            </>
          )}
        </div>

        <div className="section-label">Choose Your Classic Deck ({decks.length} available)</div>
        <div className="deck-grid">
          {decks.map((d) => {
            const hero = heroes[d.hero_class];
            const active = d.id === selectedDeckId;
            return (
              <button
                key={d.id}
                type="button"
                className={active ? 'deck-card active' : 'deck-card'}
                style={{
                  borderColor: active ? hero?.color : undefined,
                  backgroundImage: `linear-gradient(180deg, rgba(20,14,10,0.45), rgba(20,14,10,0.92) 72%), url('/art/hero_${d.hero_class}.webp')`,
                  backgroundSize: 'cover',
                  backgroundPosition: 'center top',
                }}
                onClick={() => setSelectedDeckId(d.id)}
              >
                <div className="deck-card-top">
                  <span className="class-dot" style={{ backgroundColor: hero?.color || '#888' }} />
                  <span className="deck-class">{d.hero_class}</span>
                  {!d.builtin && <span className="tag-custom">Custom</span>}
                </div>
                <div className="deck-card-title">{d.name}</div>
                <div className="deck-card-hero">{hero?.name}</div>
                <div className="deck-card-desc">{d.description || '30-card Classic deck'}</div>
              </button>
            );
          })}
        </div>

        <div className="form-row" style={{ marginTop: '1rem' }}>
          <label>
            Opponent Deck Setup
            <select value={p2DeckChoice} onChange={(e) => setP2DeckChoice(e.target.value)}>
              <option value="random">Random Classic Deck (Instant Start)</option>
              {opponentMode === 'cli' && (
                <option value="await_cli">Let Antigravity Choose via CLI (./hs deck ...)</option>
              )}
              {decks.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.hero_class} — {d.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <div className="start-actions">
          <button className="btn-primary btn-lg" onClick={handleStart} disabled={busy}>
            {busy ? 'Creating Match...' : 'Start Match'}
          </button>
        </div>
      </section>

      <aside className="tavern-panel">
        <h3>Active & Recent Matches</h3>
        {games.length === 0 ? (
          <p className="muted">No active matches yet. Start one on the left!</p>
        ) : (
          <div className="games-list">
            {games.map((g) => (
              <div key={g.game_id} className="game-item">
                <div>
                  <div className="game-item-title">
                    {g.p1.hero_class} ({g.p1.hp} HP) vs {g.p2.hero_class} ({g.p2.hp} HP)
                  </div>
                  <div className="game-item-meta">
                    ID: <code>{g.game_id}</code> · {g.mode === 'cli_vs_human' ? 'vs Antigravity' : 'vs Bot'} ·{' '}
                    {g.phase} {g.turn_number > 0 ? `· Turn ${g.turn_number}` : ''}
                    {g.winner ? ` · Winner: ${g.winner}` : ''}
                  </div>
                </div>
                <button className="btn-secondary" onClick={() => onResumeGame(g.game_id)}>
                  Open
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="cli-cheatsheet">
          <h4>Antigravity CLI Quick Reference</h4>
          <code>./hs wait</code> — wait for your turn &amp; inspect board
          <br />
          <code>./hs status</code> — view fair-play P2 board &amp; hand
          <br />
          <code>./hs mulligan 0 2</code> — replace opening cards
          <br />
          <code>./hs play 0 --target e0</code> — play card (or <code>--choose 0</code>)
          <br />
          <code>./hs attack m0 enemy_hero</code> — attack target
          <br />
          <code>./hs power --target e0</code> — use Hero Power
          <br />
          <code>./hs end</code> — end turn
        </div>
      </aside>
    </div>
  );
};
