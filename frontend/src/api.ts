// Everything the app asks of "the game", whichever way the answer comes: from
// the game server over the network, or from the engine running on this device
// (src/local). A match made on this device has an id that says so; the rest of
// the app never needs to know which kind it is talking to.
import { callLocal, isLocalGame, localGames, onLocalPush } from './local/client';
import { deleteDeviceDeck, deviceDecks, isDeviceDeck, recalledServerDecks, rememberServerDecks, saveDeviceDeck } from './local/decks';
import { localCatalog } from './local/manifest';
import { artUrl, HAS_SERVER, serverUrl, url, wsUrl } from './paths';
import type { AgentInfo, CardDef, DeckInfo, GameStateView, GameSummary, HeroMeta, Level, OpponentMode, Seat, StatePayload } from './types';

export { artUrl, url, wsUrl };
export { isLocalGame };

// ---------------------------------------------------------------------------
// The server, and whether it can be reached
// ---------------------------------------------------------------------------

let serverUp: boolean | null = null;
const serverWatchers = new Set<(up: boolean) => void>();

function setServer(up: boolean): boolean {
  if (serverUp !== up) {
    serverUp = up;
    serverWatchers.forEach((fn) => fn(up));
  }
  return up;
}

/** As far as is known: can the game server be reached? (False until `checkServer` has said so.) */
export function serverIsUp(): boolean {
  return serverUp === true;
}

export function watchServer(fn: (up: boolean) => void): () => void {
  serverWatchers.add(fn);
  return () => {
    serverWatchers.delete(fn);
  };
}

/**
 * Ask the server whether it is there. Anything but its own "ok" counts as no:
 * no connection, a timeout, a login page in front of it, somebody else's page.
 */
export async function checkServer(): Promise<boolean> {
  if (!HAS_SERVER) return setServer(false);
  const stop = new AbortController();
  const timer = window.setTimeout(() => stop.abort(), 4000);
  try {
    const res = await fetch(serverUrl('api/health'), { signal: stop.signal, cache: 'no-store' });
    const data = res.ok ? await res.json() : null;
    return setServer(Boolean(data && data.status === 'ok'));
  } catch {
    return setServer(false);
  } finally {
    window.clearTimeout(timer);
  }
}

async function apiJson<T>(path: string, opts?: RequestInit): Promise<T> {
  if (!HAS_SERVER) throw new Error('This copy of the game plays on this device only.');
  let res: Response;
  try {
    res = await fetch(serverUrl(path), {
      headers: { 'Content-Type': 'application/json' },
      ...opts,
    });
  } catch {
    throw new Error('Cannot reach the game server.');
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error((data && data.detail) || `Request failed (${res.status})`);
  }
  if (data === null) throw new Error('The game server sent something unexpected.');
  return data as T;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return apiJson<T>(path, { method: 'POST', body: JSON.stringify(body) });
}

// ---------------------------------------------------------------------------
// Cards and decks
// ---------------------------------------------------------------------------

let cardsKnown: CardDef[] = [];
let decksKnown: DeckInfo[] = [];

/** The cards and heroes: from the server when it is there, otherwise the copy that came with the app. */
export async function fetchCatalog(): Promise<{ heroes: Record<string, HeroMeta>; cards: CardDef[] }> {
  let cat: { heroes: Record<string, HeroMeta>; cards: CardDef[] } | null = null;
  if (serverIsUp()) {
    try {
      cat = await apiJson('api/cards');
    } catch {
      /* fall through to the stored copy */
    }
  }
  if (!cat) cat = await localCatalog();
  cardsKnown = cat.cards;
  return { heroes: cat.heroes, cards: cat.cards };
}

const FALLBACK_LEVELS: Level[] = [
  { id: 'easy', label: 'Easy', name: 'Apprentice' },
  { id: 'normal', label: 'Normal', name: 'Adept' },
  { id: 'hard', label: 'Hard', name: 'Master' },
];

/** How strong the on-device opponent can play. */
export async function fetchLevels(): Promise<{ levels: Level[]; standard: string }> {
  try {
    const cat = await localCatalog();
    if (cat.levels?.length) return { levels: cat.levels, standard: cat.default_level };
  } catch {
    /* the engine has the same list; this is only for the labels */
  }
  return { levels: FALLBACK_LEVELS, standard: 'normal' };
}

/**
 * Every deck that can be played: the starter decks, the ones kept on the
 * server (a remembered copy when it cannot be reached) and the ones kept on
 * this device.
 */
export async function fetchDecks(): Promise<DeckInfo[]> {
  let base: DeckInfo[] | null = null;
  if (serverIsUp()) {
    try {
      base = (await apiJson<{ decks: DeckInfo[] }>('api/decks')).decks;
      rememberServerDecks(base);
    } catch {
      /* fall through */
    }
  }
  if (!base) base = [...(await localCatalog()).decks, ...recalledServerDecks()];
  decksKnown = [...base, ...deviceDecks()];
  return decksKnown;
}

/** Saved on the server when it is there, otherwise on this device. */
export async function saveDeck(payload: { id?: string; name: string; hero_class: string; cards: string[] }): Promise<DeckInfo> {
  if (!isDeviceDeck(payload.id) && serverIsUp()) {
    const res = await post<{ deck: DeckInfo }>('api/decks', payload);
    return res.deck;
  }
  // A server deck changed while the server is away becomes a new deck on this device.
  return saveDeviceDeck({ ...payload, id: isDeviceDeck(payload.id) ? payload.id : undefined }, cardsKnown);
}

export async function deleteDeck(deckId: string): Promise<void> {
  if (isDeviceDeck(deckId)) {
    deleteDeviceDeck(deckId);
    return;
  }
  await apiJson(`api/decks/${deckId}`, { method: 'DELETE' });
}

export async function fetchAgentInfo(): Promise<AgentInfo> {
  return apiJson('api/agent');
}

// ---------------------------------------------------------------------------
// Matches
// ---------------------------------------------------------------------------

/** Matches on this device and on the server together, this device's first. */
export async function fetchGames(): Promise<{ games: GameSummary[]; latest_game_id: string | null }> {
  const here = await localGames().catch(() => [] as GameSummary[]);
  let there: { games: GameSummary[]; latest_game_id: string | null } = { games: [], latest_game_id: null };
  if (serverIsUp()) {
    try {
      there = await apiJson('api/games');
    } catch {
      /* only this device's matches then */
    }
  }
  return { games: [...here, ...there.games], latest_game_id: there.latest_game_id };
}

/** How a chosen deck is named to the on-device engine: starter decks by id, the others by their cards. */
function deckForEngine(seat: 'p1' | 'p2', deckId: string): Record<string, unknown> {
  const deck = decksKnown.find((d) => d.id === deckId);
  if (!deck || deck.builtin) return seat === 'p1' ? { p1_deck_id: deckId } : { p2_deck_choice: deckId };
  return { [`${seat}_class`]: deck.hero_class, [`${seat}_cards`]: deck.cards, [`${seat}_deck_name`]: deck.name };
}

export async function createGame(payload: {
  p1_name: string;
  p1_deck_id: string;
  p2_mode: OpponentMode;
  p2_deck_choice: string;
  p2_agent_model?: string;
  level?: string;
}): Promise<{ game_id: string; invite?: string; invite_url?: string } & StatePayload> {
  if (payload.p2_mode === 'device') {
    return callLocal('create_game', {
      p1_name: payload.p1_name,
      ...deckForEngine('p1', payload.p1_deck_id),
      ...(payload.p2_deck_choice === 'random' ? { p2_deck_choice: 'random' } : deckForEngine('p2', payload.p2_deck_choice)),
      level: payload.level,
    });
  }
  const { level: _level, ...body } = payload;
  const mine = decksKnown.find((d) => d.id === payload.p1_deck_id);
  if (mine?.device) {
    // The server has never seen a deck kept on this device: send the cards themselves.
    return post('api/games', { ...body, p1_deck_id: undefined, p1_class: mine.hero_class, p1_cards: mine.cards });
  }
  return post('api/games', body);
}

export async function joinFriend(gameId: string, invite: string, deckId: string, name: string): Promise<StatePayload> {
  const deck = decksKnown.find((d) => d.id === deckId);
  return post(`api/games/${gameId}/join`, {
    invite,
    name,
    ...(deck?.device ? { hero_class: deck.hero_class, cards: deck.cards } : { deck_id: deckId }),
  });
}

/** Friend invitations use cookies and are available on the hosted web client. */
export function canPlayFriends(): boolean {
  return new URL(serverUrl('api/games')).origin === window.location.origin;
}

export async function fetchGameState(gameId: string, seat: Seat = 'p1', since?: number): Promise<StatePayload> {
  if (isLocalGame(gameId)) return callLocal('state', { game_id: gameId, since: since ?? null });
  const q = since === undefined ? '' : `&since=${since}`;
  return apiJson(`api/games/${gameId}/state?seat=${seat}${q}`);
}

/** One action, sent to wherever the match lives. */
function act(g: string, seat: Seat, since: number, action: string, args: Record<string, unknown> = {}): Promise<StatePayload> {
  if (isLocalGame(g)) return callLocal(action, { game_id: g, since, ...args });
  return post<StatePayload>(`api/games/${g}/${action}`, { seat, since, ...args });
}

/** Actions answer with the beats the caller has not seen yet (`since`). */
export const actions = {
  mulligan: (g: string, seat: Seat, since: number, replaceIndices: number[]) => act(g, seat, since, 'mulligan', { replace_indices: replaceIndices }),
  play: (g: string, seat: Seat, since: number, p: { hand_index: number; pos?: number; target_id?: string; choose?: number }) => act(g, seat, since, 'play', p),
  choose: (g: string, seat: Seat, since: number, optionIndex: number) => act(g, seat, since, 'choose', { option_index: optionIndex }),
  attack: (g: string, seat: Seat, since: number, attackerId: string, targetId: string) =>
    act(g, seat, since, 'attack', { attacker_id: attackerId, target_id: targetId }),
  power: (g: string, seat: Seat, since: number, targetId?: string) => act(g, seat, since, 'power', { target_id: targetId }),
  endTurn: (g: string, seat: Seat, since: number) => act(g, seat, since, 'end_turn'),
  concede: (g: string, seat: Seat, since: number) => act(g, seat, since, 'concede'),
  /** Server matches only: who plays the other seat. */
  switchMode: (g: string, since: number, mode: OpponentMode) => post<StatePayload>(`api/games/${g}/switch_mode`, { mode, since }),
  /** Matches on this device only: how strong the opponent plays. */
  setLevel: (g: string, since: number, level: string) => callLocal<StatePayload>('set_level', { game_id: g, since, level }),
};

export async function sendEmote(gameId: string, seat: Seat, message: string): Promise<void> {
  if (isLocalGame(gameId)) await callLocal('emote', { game_id: gameId, message });
  else await post(`api/games/${gameId}/emote`, { seat, message });
}

/**
 * Follow a match: `onPayload` gets everything that happens in it from now on.
 * `since()` is the last moment the caller has seen. Returns how to stop.
 *
 * On the server this is a WebSocket for pushes with polling as a safety net
 * (and as the only channel behind a proxy that cannot carry WebSockets). On
 * this device the engine simply says so when the opponent has moved.
 */
export function followGame(
  gameId: string,
  seat: 'p1' | 'p2',
  since: () => number,
  onPayload: (p: StatePayload) => void,
  onReachable: (ok: boolean) => void,
): () => void {
  let alive = true;

  if (isLocalGame(gameId)) {
    const stop = onLocalPush(gameId, (p) => alive && onPayload(p));
    // Look once: this also lets the opponent carry on if the match was closed mid-turn.
    callLocal<StatePayload>('state', { game_id: gameId, since: since() })
      .then((p) => alive && onPayload(p))
      .catch(() => undefined);
    onReachable(true);
    return () => {
      alive = false;
      stop();
    };
  }

  let ws: WebSocket | null = null;
  let wsOpen = false;
  let retry: number | null = null;
  let failures = 0;

  const connect = () => {
    if (!alive) return;
    try {
      ws = new WebSocket(wsUrl(`ws/${gameId}/${seat}?since=${since()}`));
    } catch {
      return;
    }
    ws.onopen = () => {
      wsOpen = true;
      failures = 0;
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'state') onPayload(msg);
      } catch {
        /* ignore a malformed packet */
      }
    };
    ws.onclose = () => {
      wsOpen = false;
      failures += 1;
      if (alive) retry = window.setTimeout(connect, Math.min(15000, 1200 * failures));
    };
  };
  connect();

  let pollTimer: number | null = null;
  const poll = async () => {
    if (!alive) return;
    try {
      const p = await fetchGameState(gameId, seat, since());
      if (alive) onPayload(p);
      onReachable(true);
    } catch {
      onReachable(false);
    }
    if (alive) pollTimer = window.setTimeout(poll, wsOpen ? 6000 : 1200);
  };
  pollTimer = window.setTimeout(poll, 1500);

  return () => {
    alive = false;
    if (retry) window.clearTimeout(retry);
    if (pollTimer) window.clearTimeout(pollTimer);
    ws?.close();
  };
}

export type { GameStateView };
