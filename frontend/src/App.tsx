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
  joinFriend,
  saveDeck,
  serverIsUp,
  watchServer,
} from './api';
import { arenaKeyFor, attachArenaMatch } from './arena/rules';
import { updateArenaState, useArenaState } from './arena/store';
import { BRAND } from './branding';
import { RELIC_BY_ID, bossById, type CampaignBoss, type CampaignDifficulty, type RelicId } from './campaign/data';
import { attachCampaignMatch, bossStatsFor, campaignSummary, isRelicUnlocked, unclaimedChapterCount } from './campaign/rules';
import { getCampaignState, updateCampaignState, useCampaignState } from './campaign/store';
import { LOCAL_NOTICE } from './local/client';
import { checkOffline } from './local/offline';
import { sfx } from './sound';
import type { CardDef, DeckInfo, GameStateView, GameSummary, HeroMeta, Level, OpponentMode, Seat } from './types';
import { url } from './paths';
import { Arena } from './ui/Arena';
import { Board } from './ui/Board';
import { Campaign } from './ui/Campaign';
import { Deckbuilder } from './ui/Deckbuilder';
import { Lobby } from './ui/Lobby';
import { Menu } from './ui/Menu';
import { EngineStarting } from './ui/Offline';
import { PackOpening } from './ui/PackOpening';
import { Rewards } from './ui/Rewards';
import { SoundSettings } from './ui/SoundSettings';
import { pretty } from './ui/pieces';

type View = 'menu' | 'campaign' | 'lobby' | 'arena' | 'deckbuilder' | 'rewards' | 'board';
const PENDING_INVITE = 'lanternfall.pendingInvite';

function takeInvite() {
  const fragment = window.location.hash.slice(1);
  if (fragment.startsWith('invite=')) {
    window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search);
    sessionStorage.setItem(PENDING_INVITE, fragment);
  }
  const stored = sessionStorage.getItem(PENDING_INVITE) || '';
  const params = new URLSearchParams(stored);
  const match = /^([a-f0-9]{8})\.([A-Za-z0-9_-]{43})$/.exec(params.get('invite') || '');
  return match ? { id: match[1], token: match[2], era: params.get('era') || undefined } : null;
}

export const App: React.FC = () => {
  const [view, setView] = useState<View>('menu');
  const [invitation, setInvitation] = useState(takeInvite);
  const [heroes, setHeroes] = useState<Record<string, HeroMeta>>({});
  const [cards, setCards] = useState<CardDef[]>([]);
  const [decks, setDecks] = useState<DeckInfo[]>([]);
  const [games, setGames] = useState<GameSummary[]>([]);
  const [match, setMatch] = useState<{ id: string; state: GameStateView } | null>(null);
  const [showHowTo, setShowHowTo] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  /** A pack is being opened: over whatever screen asked for it. */
  const [openingPack, setOpeningPack] = useState(false);
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
    const openInvite = () => {
      if (!window.location.hash.startsWith('#invite=')) return;
      setInvitation(takeInvite());
      setMatch(null);
      setView('menu');
    };
    window.addEventListener('hashchange', openInvite);
    return () => window.removeEventListener('hashchange', openInvite);
  }, []);

  useEffect(() => {
    sfx.setMusicScene(view === 'board' ? 'match' : view === 'arena' || view === 'campaign' ? 'arena' : 'menu');
  }, [view]);

  const campaignState = useCampaignState();
  const campaignLine = campaignSummary(campaignState);
  const campaignHasReward = unclaimedChapterCount(campaignState) > 0 || Boolean(campaignState.activeMatch);

  const arenaState = useArenaState();
  const arenaSummary = (() => {
    const r = arenaState.run;
    if (!r) return undefined;
    if (r.phase === 'picking_hero') return 'Choose your hero to begin draft';
    if (r.phase === 'drafting') return `Drafting ${pretty(r.heroClass || '')} · ${r.deck.length}/30`;
    if (r.phase === 'complete') return r.claimed ? undefined : `${r.wins}–${r.losses} · Claim ${arenaKeyFor(r.wins).name}`;
    return `${pretty(r.heroClass || '')} · ${r.wins}–${r.losses} (${arenaKeyFor(r.wins).name})`;
  })();

  const go = async (target: 'menu' | 'campaign' | 'lobby' | 'arena') => {
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
      if (res.invite) {
        const deck = decks.find((d) => d.id === opts.p1DeckId);
        const era = deck?.era_name && deck.era ? `&era=${encodeURIComponent(deck.era)}` : '';
        sessionStorage.setItem(`lanternfall.invite.${res.game_id}`, res.invite_url || url(`./#invite=${res.game_id}.${res.invite}${era}`));
      }
      setMatch({ id: res.game_id, state: res.state });
      setView('board');
    } finally {
      setEngineWait(false);
    }
  };

  const startArenaMatch = async (opts: {
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
  }) => {
    setEngineWait(opts.p2Mode === 'device');
    try {
      const res = await createGame({
        p1_name: 'Player',
        p1_class: opts.heroClass,
        p1_cards: opts.deck,
        p1_deck_name: opts.deckName,
        p2_mode: opts.p2Mode,
        p2_class: opts.opponentClass,
        p2_cards: opts.opponentDeck,
        p2_deck_name: opts.opponentDeckName,
        p2_name: opts.opponentName,
        p2_agent_model: opts.agentModel,
        level: opts.level,
        arena: true,
      });
      updateArenaState((cur) =>
        cur.run ? { ...cur, run: attachArenaMatch(cur.run, res.game_id, opts.opponentClass, opts.opponentName) } : cur,
      );
      setMatch({ id: res.game_id, state: res.state });
      setView('board');
    } finally {
      setEngineWait(false);
    }
  };

  const startCampaignBoss = async (opts: {
    boss: CampaignBoss;
    difficulty: CampaignDifficulty;
    relicId: RelicId;
    deck: DeckInfo;
    p2Mode: OpponentMode;
    agentModel?: string;
  }) => {
    setEngineWait(opts.p2Mode === 'device');
    try {
      const stats = bossStatsFor(opts.boss, opts.difficulty);
      const relic = RELIC_BY_ID[opts.relicId] || RELIC_BY_ID.none;
      const bossDeck = decks.find((d) => d.id === opts.boss.deckId);
      const res = await createGame({
        p1_name: 'Player',
        ...(opts.deck.builtin
          ? { p1_deck_id: opts.deck.id }
          : { p1_class: opts.deck.hero_class, p1_cards: opts.deck.cards, p1_deck_name: opts.deck.name }),
        p2_mode: opts.p2Mode,
        ...(bossDeck
          ? { p2_class: bossDeck.hero_class, p2_cards: bossDeck.cards, p2_deck_name: bossDeck.name }
          : { p2_deck_choice: opts.boss.deckId }),
        p2_name: opts.boss.name,
        p2_agent_model: opts.agentModel,
        level: stats.level,
        campaign: true,
        p1_hp: relic.p1Hp,
        p1_armor: relic.p1Armor,
        p1_bonus_mana: relic.p1BonusMana,
        p1_bonus_cards: relic.p1BonusCards,
        p2_hp: stats.hp,
        p2_armor: stats.armor,
        p2_bonus_mana: stats.bonusMana,
        p1_relic: relic.id,
        p1_relic_name: relic.id === 'none' ? '' : relic.name,
        p1_relic_text: relic.id === 'none' ? '' : relic.shortEffect,
        p2_passive: opts.boss.passiveId,
        p2_passive_power: stats.passivePower,
        p2_passive_name: opts.boss.passiveName,
        p2_passive_text: stats.passiveText,
        p2_opening_board: stats.openingBoard,
        p2_intro_quote: opts.boss.introQuote,
        p2_mid_quote: opts.boss.midQuote,
      });
      updateCampaignState((cur) => attachCampaignMatch(cur, res.game_id, opts.boss.id, opts.difficulty, opts.relicId, opts.deck.id));
      setMatch({ id: res.game_id, state: res.state });
      setView('board');
    } finally {
      setEngineWait(false);
    }
  };

  const quickLaunchCampaign = async (opts: {
    bossId: string;
    difficulty: CampaignDifficulty;
    relicId: RelicId;
    deckId?: string;
  }) => {
    const boss = bossById(opts.bossId);
    if (!boss) return;
    const st = getCampaignState();
    const deck =
      decks.find((d) => d.id === (opts.deckId || st.selectedDeckId)) ||
      decks.find((d) => !d.builtin) ||
      decks.find((d) => d.id === boss.recommendedDeckId) ||
      decks[0];
    if (!deck) return;
    const relicId = isRelicUnlocked(st, opts.relicId) ? opts.relicId : 'none';
    const mode: OpponentMode = serverUp && st.preferredOpponent === 'bot' ? 'bot' : 'device';
    await startCampaignBoss({
      boss,
      difficulty: opts.difficulty,
      relicId,
      deck,
      p2Mode: mode,
    });
  };

  const resumeGame = async (gameId: string, seat: Seat = 'p1') => {
    setEngineWait(isLocalGame(gameId));
    try {
      const res = await fetchGameState(gameId, seat);
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

  const acceptInvite = async (name: string, deckId: string) => {
    if (!invitation) return;
    const { id, token } = invitation;
    const res = await joinFriend(id, token, deckId, name);
    sessionStorage.removeItem(PENDING_INVITE);
    setInvitation(null);
    setMatch({ id, state: res.state });
    setView('board');
  };

  const dismissInvite = () => {
    sessionStorage.removeItem(PENDING_INVITE);
    setInvitation(null);
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

      {view === 'menu' && !invitation && (
        <Menu
          cards={cards}
          classCount={Object.keys(heroes).length}
          games={games}
          serverUp={serverUp}
          campaignSummary={campaignLine}
          campaignHighlight={campaignHasReward}
          arenaSummary={arenaSummary}
          onCampaign={() => go('campaign')}
          onPlay={() => go('lobby')}
          onArena={() => go('arena')}
          onCollection={() => setView('deckbuilder')}
          onRewards={() => setView('rewards')}
          onOpenPack={() => setOpeningPack(true)}
          onHowTo={() => setShowHowTo(true)}
          onSettings={() => setShowSettings(true)}
          onResume={(id) => resumeGame(id, games.find((g) => g.game_id === id)?.viewer_seat)}
        />
      )}

      {view === 'campaign' && !invitation && (
        <Campaign
          heroes={heroes}
          cards={cards}
          decks={decks}
          games={games}
          serverUp={serverUp}
          onStartBoss={startCampaignBoss}
          onResumeMatch={(id) => resumeGame(id, 'p1')}
          onOpenDeckbuilder={() => setView('deckbuilder')}
          onOpenPack={() => setOpeningPack(true)}
          onBack={() => go('menu')}
        />
      )}

      {view === 'arena' && !invitation && (
        <Arena
          heroes={heroes}
          cards={cards}
          games={games}
          serverUp={serverUp}
          levels={levels.levels}
          onStartMatch={startArenaMatch}
          onResumeMatch={(id) => resumeGame(id, 'p1')}
          onOpenPack={() => setOpeningPack(true)}
          onBack={() => go('menu')}
        />
      )}

      {(view === 'lobby' || invitation) && (
        <Lobby
          heroes={heroes}
          decks={decks}
          games={games}
          serverUp={serverUp}
          levels={levels.levels}
          standardLevel={levels.standard}
          inviteEra={invitation?.era}
          onJoinFriend={invitation ? acceptInvite : undefined}
          onStartGame={startGame}
          onResumeGame={resumeGame}
          onOpenDeckbuilder={() => setView('deckbuilder')}
          onBack={invitation ? dismissInvite : () => go('menu')}
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
          inviteLink={sessionStorage.getItem(`lanternfall.invite.${match.id}`) || undefined}
          heroes={heroes}
          onLeaveToLobby={() => go('lobby')}
          onLeaveToCampaign={() => go('campaign')}
          onQuickCampaign={quickLaunchCampaign}
          onLeaveToArena={() => go('arena')}
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
              <SoundSettings />
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
