// Decks kept on this device: the ones built while the server could not be
// reached (or in a packaged app that has no server), and a copy of the
// server's decks as last seen, so they can still be played offline.
import type { CardDef, DeckInfo } from '../types';

const DEVICE_KEY = 'device_decks';
const SEEN_KEY = 'server_decks_seen';
export const DEVICE_PREFIX = 'device_';

function read(key: string): DeckInfo[] {
  try {
    const list = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export function isDeviceDeck(id: string | undefined): boolean {
  return Boolean(id && id.startsWith(DEVICE_PREFIX));
}

export function deviceDecks(): DeckInfo[] {
  return read(DEVICE_KEY).map((d) => ({ ...d, builtin: false, device: true }));
}

/** The server's own decks as last seen, for when it cannot be reached. */
export function rememberServerDecks(decks: DeckInfo[]): void {
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify(decks.filter((d) => !d.builtin)));
  } catch {
    /* storage full or blocked: they are just not remembered */
  }
}

export function recalledServerDecks(): DeckInfo[] {
  return read(SEEN_KEY).map((d) => ({ ...d, builtin: false }));
}

/** The deck rules, as engine/catalog.py `validate_deck` has them (the engine checks again when a match starts). */
export function deckProblem(heroClass: string, ids: string[], cards: CardDef[]): string | null {
  if (ids.length !== 30) return `Deck must contain exactly 30 cards (got ${ids.length})`;
  const byId = new Map(cards.map((c) => [c.id, c]));
  const counts = new Map<string, number>();
  for (const id of ids) {
    const card = byId.get(id);
    if (!card) return `Unknown or non-collectible card ID: ${id}`;
    const allowed = card.classes && card.classes.length > 0
      ? card.classes.includes(heroClass)
      : card.card_class === heroClass || card.card_class === 'NEUTRAL';
    if (!allowed) return `${card.name} belongs to ${card.classes?.join('/') || card.card_class}, not ${heroClass}`;
    const n = (counts.get(id) ?? 0) + 1;
    counts.set(id, n);
    const limit = card.rarity === 'LEGENDARY' ? 1 : 2;
    if (n > limit) return `Too many copies of ${card.name} (max ${limit})`;
  }
  return null;
}

export function saveDeviceDeck(payload: { id?: string; name: string; hero_class: string; cards: string[] }, cards: CardDef[]): DeckInfo {
  const problem = deckProblem(payload.hero_class, payload.cards, cards);
  if (problem) throw new Error(problem);
  const list = read(DEVICE_KEY);
  const name = payload.name.trim().slice(0, 48) || `Custom ${payload.hero_class[0]}${payload.hero_class.slice(1).toLowerCase()}`;
  const id = isDeviceDeck(payload.id) && list.some((d) => d.id === payload.id) ? payload.id! : `${DEVICE_PREFIX}${Date.now().toString(36)}${Math.floor(Math.random() * 1296).toString(36)}`;
  const deck: DeckInfo = { id, name, hero_class: payload.hero_class, description: 'Custom deck, kept on this device.', cards: [...payload.cards], builtin: false, device: true };
  const next = list.filter((d) => d.id !== id);
  next.push(deck);
  localStorage.setItem(DEVICE_KEY, JSON.stringify(next));
  return deck;
}

export function deleteDeviceDeck(id: string): void {
  localStorage.setItem(DEVICE_KEY, JSON.stringify(read(DEVICE_KEY).filter((d) => d.id !== id)));
}
