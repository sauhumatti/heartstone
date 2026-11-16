import React, { useEffect, useState } from 'react';
import {
  createGame,
  deleteDeck,
  fetchCatalog,
  fetchDecks,
  fetchGames,
  fetchGameState,
  saveDeck,
} from './api';
import { BoardView } from './components/BoardView';
import { DeckbuilderView } from './components/DeckbuilderView';
import { LobbyView } from './components/LobbyView';
import { MainMenuView } from './components/MainMenuView';
import { sfx } from './sound';
import type { CardDef, DeckInfo, GameStateView, GameSummary, HeroMeta } from './types';

export const App: React.FC = () => {
  const [view, setView] = useState<'menu' | 'lobby' | 'deckbuilder' | 'board'>('menu');
  const [heroes, setHeroes] = useState<Record<string, HeroMeta>>({});
  const [cards, setCards] = useState<CardDef[]>([]);
  const [decks, setDecks] = useState<DeckInfo[]>([]);
  const [games, setGames] = useState<GameSummary[]>([]);
  const [activeGameId, setActiveGameId] = useState<string | null>(null);
  const [activeState, setActiveState] = useState<GameStateView | null>(null);
  const [showHowTo, setShowHowTo] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [sfxEnabled, setSfxEnabled] = useState(sfx.enabled);
  const [sfxVol, setSfxVol] = useState(sfx.volume);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const loadLobbyData = async () => {
    try {
      const [cat, dks, gms] = await Promise.all([fetchCatalog(), fetchDecks(), fetchGames()]);
      setHeroes(cat.heroes);
      setCards(cat.cards);
      setDecks(dks);
      setGames(gms.games);
    } catch (e: any) {
      setErr(e.message || 'Failed to connect to local game server');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLobbyData();
  }, []);

  const toggleSfx = () => {
    const next = !sfxEnabled;
    sfx.setEnabled(next);
    setSfxEnabled(next);
  };

  const handleStartGame = async (opts: {
    p1Name: string;
    p1DeckId: string;
    p2Mode: 'cli' | 'bot';
    p2DeckChoice: string;
  }) => {
    const res = await createGame({
      p1_name: opts.p1Name,
      p1_deck_id: opts.p1DeckId,
      p2_mode: opts.p2Mode,
      p2_deck_choice: opts.p2DeckChoice,
    });
    setActiveGameId(res.game_id);
    setActiveState(res.state);
    setView('board');
    sfx.turnStart();
  };

  const handleResumeGame = async (gid: string) => {
    const st = await fetchGameState(gid, 'p1');
    setActiveGameId(gid);
    setActiveState(st);
    setView('board');
  };

  const handleSaveDeck = async (payload: {
    id?: string;
    name: string;
    hero_class: string;
    cards: string[];
  }) => {
    await saveDeck(payload);
    setDecks(await fetchDecks());
  };

  const handleDeleteDeck = async (deckId: string) => {
    await deleteDeck(deckId);
    setDecks(await fetchDecks());
  };

  const refreshGamesAndGo = async (target: 'menu' | 'lobby') => {
    setView(target);
    try {
      setGames((await fetchGames()).games);
    } catch {
      // ignore
    }
  };

  if (loading) {
    return <div className="loading-screen">Opening the Tavern Doors...</div>;
  }

  return (
    <div className="app-root">
      {err && <div className="error-banner" style={{ margin: '0.75rem' }}>{err}</div>}

      {view === 'menu' && (
        <MainMenuView
          cardsCount={cards.length}
          games={games}
          sfxEnabled={sfxEnabled}
          onToggleSfx={toggleSfx}
          onGoPlay={() => refreshGamesAndGo('lobby')}
          onGoCollection={() => setView('deckbuilder')}
          onOpenHowTo={() => setShowHowTo(true)}
          onOpenSettings={() => setShowSettings(true)}
          onResumeGame={handleResumeGame}
        />
      )}

      {view === 'lobby' && (
        <LobbyView
          heroes={heroes}
          decks={decks}
          games={games}
          onStartGame={handleStartGame}
          onResumeGame={handleResumeGame}
          onOpenDeckbuilder={() => setView('deckbuilder')}
          onBackToMenu={() => refreshGamesAndGo('menu')}
        />
      )}

      {view === 'deckbuilder' && (
        <DeckbuilderView
          heroes={heroes}
          cards={cards}
          decks={decks}
          onSaveDeck={handleSaveDeck}
          onDeleteDeck={handleDeleteDeck}
          onBack={() => refreshGamesAndGo('menu')}
        />
      )}

      {view === 'board' && activeGameId && activeState && (
        <BoardView
          gameId={activeGameId}
          initialState={activeState}
          heroes={heroes}
          onLeaveToLobby={() => refreshGamesAndGo('lobby')}
          onLeaveToMenu={() => refreshGamesAndGo('menu')}
        />
      )}

      {/* How to Play Modal */}
      {showHowTo && (
        <div className="modal-backdrop" onClick={() => setShowHowTo(false)}>
          <div className="modal-card modal-wide" style={{ textAlign: 'left' }} onClick={(e) => e.stopPropagation()}>
            <h2 style={{ color: 'var(--gold-bright)', marginTop: 0 }}>📜 Playing Classic Hearthstone vs Antigravity</h2>
            <p>
              This tavern faithfully recreates the <strong>2014 Basic + Classic</strong> card pool (all 382 collectible cards,
              9 classic heroes, Secrets, Choose One, Overload, Auras, and Weapons) with <strong>zero online play</strong>.
            </p>
            <ul style={{ lineHeight: 1.7 }}>
              <li><strong>You (Player 1):</strong> Play in this browser — mulligan opening cards, drag/click ready minions to attack, choose board placement slots (<code>+</code>), and end your turn.</li>
              <li><strong>Antigravity (Player 2):</strong> Plays via the local <code>./hs</code> CLI or HTTP API using strict Fog of War (cannot see your hand, deck order, or secret identities).</li>
              <li><strong>Solo Practice:</strong> Switch to <em>Practice Bot</em> anytime in the Duel Lobby or via the in-game <code>⚙ Menu</code>.</li>
            </ul>
            <div style={{ textAlign: 'right' }}>
              <button className="btn-primary" onClick={() => setShowHowTo(false)}>Got It</button>
            </div>
          </div>
        </div>
      )}

      {/* Game Options Modal */}
      {showSettings && (
        <div className="modal-backdrop" onClick={() => setShowSettings(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h2 style={{ color: 'var(--gold-bright)', marginTop: 0 }}>⚙ Game Options</h2>
            <div className="game-menu-actions">
              <button className="tavern-btn" onClick={toggleSfx}>
                {sfxEnabled ? '🔊 Tavern Sound Effects: ON' : '🔇 Tavern Sound Effects: OFF'}
              </button>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', textAlign: 'left', fontSize: '0.88rem' }}>
                <span>Volume: {Math.round(sfxVol * 100)}%</span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={sfxVol}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setSfxVol(v);
                    sfx.setVolume(v);
                  }}
                />
              </label>
              <button
                className="tavern-btn"
                onClick={() => {
                  sfx.unlockSync();
                  sfx.victory();
                }}
              >
                🎵 Test Sound Fanfare
              </button>
            </div>
            <div style={{ marginTop: '1rem' }}>
              <button className="btn-primary" onClick={() => setShowSettings(false)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
