import type { CardDef, DeckInfo, GameStateView, GameSummary, HeroMeta } from './types';

async function apiJson<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data as T;
}

export async function fetchCatalog(): Promise<{ heroes: Record<string, HeroMeta>; cards: CardDef[] }> {
  return apiJson('/api/cards');
}

export async function fetchDecks(): Promise<DeckInfo[]> {
  const res = await apiJson<{ decks: DeckInfo[] }>('/api/decks');
  return res.decks;
}

export async function saveDeck(payload: { id?: string; name: string; hero_class: string; cards: string[] }): Promise<DeckInfo> {
  const res = await apiJson<{ deck: DeckInfo }>('/api/decks', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  return res.deck;
}

export async function deleteDeck(deckId: string): Promise<void> {
  await apiJson(`/api/decks/${deckId}`, { method: 'DELETE' });
}

export async function fetchGames(): Promise<{ games: GameSummary[]; latest_game_id: string | null }> {
  return apiJson('/api/games');
}

export async function createGame(payload: {
  p1_name: string;
  p1_deck_id: string;
  p2_mode: 'cli' | 'bot';
  p2_deck_choice: string;
}): Promise<{ game_id: string; state: GameStateView }> {
  return apiJson('/api/games', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchGameState(gameId: string, seat = 'p1'): Promise<GameStateView> {
  const res = await apiJson<{ state: GameStateView }>(`/api/games/${gameId}/state?seat=${seat}`);
  return res.state;
}

export async function submitMulligan(gameId: string, replaceIndices: number[]): Promise<GameStateView> {
  const res = await apiJson<{ state: GameStateView }>(`/api/games/${gameId}/mulligan`, {
    method: 'POST',
    body: JSON.stringify({ seat: 'p1', replace_indices: replaceIndices }),
  });
  return res.state;
}

export async function playCard(
  gameId: string,
  payload: { hand_index: number; pos?: number; target_id?: string; choose?: number },
): Promise<GameStateView> {
  const res = await apiJson<{ state: GameStateView }>(`/api/games/${gameId}/play`, {
    method: 'POST',
    body: JSON.stringify({ seat: 'p1', ...payload }),
  });
  return res.state;
}

export async function resolveChoice(gameId: string, optionIndex: number): Promise<GameStateView> {
  const res = await apiJson<{ state: GameStateView }>(`/api/games/${gameId}/choose`, {
    method: 'POST',
    body: JSON.stringify({ seat: 'p1', option_index: optionIndex }),
  });
  return res.state;
}

export async function attackTarget(gameId: string, attackerId: string, targetId: string): Promise<GameStateView> {
  const res = await apiJson<{ state: GameStateView }>(`/api/games/${gameId}/attack`, {
    method: 'POST',
    body: JSON.stringify({ seat: 'p1', attacker_id: attackerId, target_id: targetId }),
  });
  return res.state;
}

export async function useHeroPower(gameId: string, targetId?: string): Promise<GameStateView> {
  const res = await apiJson<{ state: GameStateView }>(`/api/games/${gameId}/power`, {
    method: 'POST',
    body: JSON.stringify({ seat: 'p1', target_id: targetId }),
  });
  return res.state;
}

export async function endTurn(gameId: string): Promise<GameStateView> {
  const res = await apiJson<{ state: GameStateView }>(`/api/games/${gameId}/end_turn`, {
    method: 'POST',
    body: JSON.stringify({ seat: 'p1' }),
  });
  return res.state;
}

export async function concedeGame(gameId: string): Promise<GameStateView> {
  const res = await apiJson<{ state: GameStateView }>(`/api/games/${gameId}/concede`, {
    method: 'POST',
    body: JSON.stringify({ seat: 'p1' }),
  });
  return res.state;
}

export async function sendEmote(gameId: string, message: string): Promise<void> {
  await apiJson(`/api/games/${gameId}/emote`, {
    method: 'POST',
    body: JSON.stringify({ seat: 'p1', message }),
  });
}

export async function switchMode(gameId: string, mode: 'cli' | 'bot'): Promise<GameStateView> {
  const res = await apiJson<{ state: GameStateView }>(`/api/games/${gameId}/switch_mode`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  });
  return res.state;
}
