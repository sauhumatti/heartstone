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
import type { CardDef, DeckInfo, GameStateView, GameSummary, HeroMeta } from './types';

export const App: React.FC = () => {
  const [view, setView] = useState<'lobby' | 'deckbuilder' | 'board'>('lobby');
  const [heroes, setHeroes] = useState<Record<string, HeroMeta>>({});
  const [cards, setCards] = useState<CardDef[]>([]);
  const [decks, setDecks] = useState<DeckInfo[]>([]);
  const [games, setGames] = useState<GameSummary[]>([]);
  const [activeGameId, setActiveGameId] = useState<string | null>(null);
  const [activeState, setActiveState] = useState<GameStateView | null>(null);
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

  const goLobby = async () => {
    setView('lobby');
    setActiveGameId(null);
    setActiveState(null);
    setGames((await fetchGames()).games);
  };

  if (loading) {
    return <div className="loading-screen">Loading Classic Hearthstone Tavern...</div>;
  }

  return (
    <div className="app-root">
      <header className="top-bar">
        <div className="brand" onClick={goLobby} style={{ cursor: 'pointer' }}>
          <span className="brand-swirl">✦</span>
          <span>HEARTHSTONE</span>
          <span className="brand-tag">CLASSIC 2014 · LOCAL</span>
        </div>
        <nav className="top-nav">
          <button
            className={view === 'lobby' ? 'nav-btn active' : 'nav-btn'}
            onClick={goLobby}
          >
            Tavern Lobby
          </button>
          <button
            className={view === 'deckbuilder' ? 'nav-btn active' : 'nav-btn'}
            onClick={() => setView('deckbuilder')}
          >
            Collection ({cards.length})
          </button>
          {activeGameId && (
            <button
              className={view === 'board' ? 'nav-btn active' : 'nav-btn'}
              onClick={() => setView('board')}
            >
              Active Match #{activeGameId}
            </button>
          )}
        </nav>
      </header>

      {err && <div className="error-banner" style={{ margin: '1rem' }}>{err}</div>}

      <main className="main-content">
        {view === 'lobby' && (
          <LobbyView
            heroes={heroes}
            decks={decks}
            games={games}
            onStartGame={handleStartGame}
            onResumeGame={handleResumeGame}
            onOpenDeckbuilder={() => setView('deckbuilder')}
          />
        )}
        {view === 'deckbuilder' && (
          <DeckbuilderView
            heroes={heroes}
            cards={cards}
            decks={decks}
            onSaveDeck={handleSaveDeck}
            onDeleteDeck={handleDeleteDeck}
            onBack={goLobby}
          />
        )}
        {view === 'board' && activeGameId && activeState && (
          <BoardView
            gameId={activeGameId}
            initialState={activeState}
            heroes={heroes}
            onLeaveToLobby={goLobby}
          />
        )}
      </main>
    </div>
  );
};
