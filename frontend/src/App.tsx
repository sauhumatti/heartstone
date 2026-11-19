import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  checkServer,
  createGame,
  deleteDeck,
  fetchCatalog,
  fetchDecks,
  fetchGames,
  fetchGameState,
  fetchLevels,
  isLocalGame,
  saveDeck,
  serverIsUp,
  watchServer,
} from './api';
import { BRAND } from './branding';
import { LOCAL_NOTICE } from './local/client';
import { checkOffline } from './local/offline';
import { sfx } from './sound';
import type { CardDef, DeckInfo, GameStateView, GameSummary, HeroMeta, Level, OpponentMode } from './types';
import { Board } from './ui/Board';
import { Deckbuilder } from './ui/Deckbuilder';
import { Lobby } from './ui/Lobby';
import { Menu } from './ui/Menu';
import { EngineStarting } from './ui/Offline';
import { PackOpening } from './ui/PackOpening';
import { Rewards } from './ui/Rewards';

type View = 'menu' | 'lobby' | 'deckbuilder' | 'rewards' | 'board';

export const App: React.FC = () => {
  const [view, setView] = useState<View>('menu');
  const [heroes, setHeroes] = useState<Record<string, HeroMeta>>({});
  const [cards, setCards] = useState<CardDef[]>([]);
  const [decks, setDecks] = useState<DeckInfo[]>([]);
  const [games, setGames] = useState<GameSummary[]>([]);
  const [match, setMatch] = useState<{ id: string; state: GameStateView } | null>(null);
  const [showHowTo, setShowHowTo] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  /** A pack is being opened: over whatever screen asked for it. */
  const [openingPack, setOpeningPack] = useState(false);
  const [sfxOn, setSfxOn] = useState(sfx.enabled);
  const [sfxVol, setSfxVol] = useState(sfx.volume);
  const [musicOn, setMusicOn] = useState(sfx.musicEnabled);
  const [musicVol, setMusicVol] = useState(sfx.musicVolume);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  /** When the on-device engine last had something to tell the player (see LOCAL_NOTICE below). */
  const noticeAt = useRef(0);
  /** Can the game server be reached? Without it the game is played on this device. */
  const [serverUp, setServerUp] = useState(serverIsUp);
  const [levels, setLevels] = useState<{ levels: Level[]; standard: string }>({ levels: [], standard: 'normal' });
  /** A match on this device is being opened: the engine may still be starting. */
  const [engineWait, setEngineWait] = useState(false);

  // The cards come from the server when it is there, otherwise from the copy on this device.
  const load = useCallback(async () => {
    setLoading(true);
    setErr('');
    try {
      await checkServer();
      const cat = await fetchCatalog();
      const [dks, gms, lv] = await Promise.all([fetchDecks(), fetchGames(), fetchLevels()]);
      setHeroes(cat.heroes);
      setCards(cat.cards);
      setDecks(dks);
      setGames(gms.games);
      setLevels(lv);
    } catch {
      setCards([]);
    } finally {
      setLoading(false);
    }
    void checkOffline();
  }, []);

  useEffect(() => {
    document.title = BRAND.title;
    void load();
    // The connection coming or going changes who can be played against.
    const recheck = () => void checkServer();
    window.addEventListener('online', recheck);
    window.addEventListener('offline', recheck);
    const stop = watchServer(setServerUp);
    return () => {
      window.removeEventListener('online', recheck);
      window.removeEventListener('offline', recheck);
      stop();
    };
  }, [load]);

  useEffect(() => {
    sfx.setMusicScene(view === 'board' ? 'match' : 'menu');
  }, [view]);

  const go = async (target: 'menu' | 'lobby') => {
    setView(target);
    setMatch(null);
    try {
      // The server may have come or gone since the last look.
      const was = serverIsUp();
      if ((await checkServer()) !== was) setDecks(await fetchDecks());
      setGames((await fetchGames()).games);
    } catch {
      /* the lists just stay as they were */
    }
  };

  // The on-device engine could not continue a kept match (after an update, say): tell the
  // player, and leave the table if it was the match on screen.
  const openMatch = match?.id;
  useEffect(() => {
    const onNotice = (e: Event) => {
      const { message, gone } = (e as CustomEvent<{ message: string; gone?: string }>).detail;
      noticeAt.current = Date.now();
      setErr(message);
      if (gone && gone === openMatch) void go('menu');
      else if (!openMatch) void fetchGames().then((g) => setGames(g.games)).catch(() => undefined);
    };
    window.addEventListener(LOCAL_NOTICE, onNotice);
    return () => window.removeEventListener(LOCAL_NOTICE, onNotice);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [openMatch]);

  const startGame = async (opts: {
    p1Name: string;
    p1DeckId: string;
    p2Mode: OpponentMode;
    p2DeckChoice: string;
    agentModel?: string;
    level?: string;
  }) => {
    setEngineWait(opts.p2Mode === 'device');
    try {
      const res = await createGame({
        p1_name: opts.p1Name,
        p1_deck_id: opts.p1DeckId,
        p2_mode: opts.p2Mode,
        p2_deck_choice: opts.p2DeckChoice,
        p2_agent_model: opts.agentModel,
        level: opts.level,
      });
      setMatch({ id: res.game_id, state: res.state });
      setView('board');
    } finally {
      setEngineWait(false);
    }
  };

  const resumeGame = async (gameId: string) => {
    setEngineWait(isLocalGame(gameId));
    try {
      const res = await fetchGameState(gameId);
      setMatch({ id: gameId, state: res.state });
      setView('board');
    } catch (e: any) {
      // If the engine has just said why (a kept match an update left behind), its words stay.
      if (Date.now() - noticeAt.current > 4000) setErr(e?.message || 'That match is no longer available.');
      void fetchGames()
        .then((g) => setGames(g.games))
        .catch(() => undefined);
    } finally {
      setEngineWait(false);
    }
  };

  if (loading) {
    return (
      <div className="screen loading">
        <span>{BRAND.title}</span>
      </div>
    );
  }

  if (!cards.length) {
    // Neither the server nor a copy on this device: there is nothing to show yet.
    return (
      <div className="screen loading">
        <div className="retry">
          <span>{BRAND.title}</span>
          <p className="note">The game server cannot be reached, and the game is not stored on this device yet.</p>
          <button type="button" className="btn primary" onClick={() => void load()}>
            Try again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      {err && (
        <div className="alert floating" role="alert">
          {err}
          <button type="button" className="link" onClick={() => setErr('')}>
            Dismiss
          </button>
        </div>
      )}

      <EngineStarting waiting={engineWait} />

      {view === 'menu' && (
        <Menu
          cards={cards}
          classCount={Object.keys(heroes).length}
          games={games}
          serverUp={serverUp}
          onPlay={() => go('lobby')}
          onCollection={() => setView('deckbuilder')}
          onRewards={() => setView('rewards')}
          onOpenPack={() => setOpeningPack(true)}
          onHowTo={() => setShowHowTo(true)}
          onSettings={() => setShowSettings(true)}
          onResume={resumeGame}
        />
      )}

      {view === 'lobby' && (
        <Lobby
          heroes={heroes}
          decks={decks}
          games={games}
          serverUp={serverUp}
          levels={levels.levels}
          standardLevel={levels.standard}
          onStartGame={startGame}
          onResumeGame={resumeGame}
          onOpenDeckbuilder={() => setView('deckbuilder')}
          onBack={() => go('menu')}
        />
      )}

      {view === 'deckbuilder' && (
        <Deckbuilder
          heroes={heroes}
          cards={cards}
          decks={decks}
          onSaveDeck={async (payload) => {
            await saveDeck(payload);
            setDecks(await fetchDecks());
          }}
          onDeleteDeck={async (deckId) => {
            await deleteDeck(deckId);
            setDecks(await fetchDecks());
          }}
          onBack={() => go('menu')}
        />
      )}

      {view === 'rewards' && <Rewards onBack={() => go('menu')} onOpenPack={() => setOpeningPack(true)} />}

      {view === 'board' && match && (
        <Board
          key={match.id}
          gameId={match.id}
          initialState={match.state}
          heroes={heroes}
          onLeaveToLobby={() => go('lobby')}
          onLeaveToMenu={() => go('menu')}
          onOpenPack={() => setOpeningPack(true)}
        />
      )}

      {openingPack && <PackOpening onClose={() => setOpeningPack(false)} />}

      {showHowTo && (
        <div className="modal" onClick={() => setShowHowTo(false)}>
          <div className="sheet sheet-text" onClick={(e) => e.stopPropagation()}>
            <h2>How to play</h2>
            <ul>
              <li>
                <b>Play a card:</b> drag it onto the table, or click it. Drag a minion between two others to choose its place.
              </li>
              <li>
                <b>Aim:</b> a card or power that needs a target shows an arrow. Release (or click) on a glowing target. Right-click or Esc cancels.
              </li>
              <li>
                <b>Attack:</b> drag from a glowing minion or your hero to an enemy, or click the attacker and then the target.
              </li>
              <li>
                <b>Look closer:</b> hover any minion, weapon, power or recent play to see the full card.
              </li>
              <li>
                <b>End your turn</b> with the button on the right. It lights up when nothing is left to do.
              </li>
              <li>
                <b>Rating and lanterns:</b> every match against an opponent moves your rating, and the rating sets your rank. Three wins earn a
                paper lantern, and so does each rank you reach for the first time; light it to find card backs, tables and titles to wear. Open
                them from the menu.
              </li>
              <li>
                <b>Opponent:</b> “This device” is a built-in opponent with three levels that needs no connection. With the game server there are
                also the practice bot, which plays at once, Antigravity (Gemini 4 Hydrogen), which thinks for a few seconds per move and sees only
                what a player would, and manual mode, which leaves the other seat to whoever types <code>./hs</code> commands.
              </li>
            </ul>
            <button type="button" className="btn primary" onClick={() => setShowHowTo(false)}>
              Got it
            </button>
          </div>
        </div>
      )}

      {showSettings && (
        <div className="modal" onClick={() => setShowSettings(false)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h2>Settings</h2>
            <div className="menu-list">
              <button
                type="button"
                className="btn"
                onClick={() => {
                  sfx.setMusicEnabled(!musicOn);
                  setMusicOn(!musicOn);
                }}
              >
                Music: {musicOn ? 'on' : 'off'}
              </button>
              <label className="field">
                <span>Music volume {Math.round(musicVol * 100)}%</span>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={musicVol}
                  onChange={(e) => {
                    const v = Number(e.target.value);
                    setMusicVol(v);
                    sfx.setMusicVolume(v);
                  }}
                />
              </label>
              <button
                type="button"
                className="btn"
                onClick={() => {
                  sfx.setEnabled(!sfxOn);
                  setSfxOn(!sfxOn);
                }}
              >
                Sound effects: {sfxOn ? 'on' : 'off'}
              </button>
              <label className="field">
                <span>Effects volume {Math.round(sfxVol * 100)}%</span>
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
              <button type="button" className="btn primary" onClick={() => setShowSettings(false)}>
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
