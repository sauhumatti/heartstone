// Persistence for the player's current Arena run and lifetime Arena stats.
import { useSyncExternalStore } from 'react';
import { emptyArenaState, restoreArenaState, type ArenaState } from './rules';

const KEY = 'lf_arena_v1';

let current: ArenaState | null = null;
const listeners = new Set<() => void>();

function read(): ArenaState {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return restoreArenaState(JSON.parse(raw));
  } catch {
    /* ignore corrupted or unavailable storage */
  }
  return emptyArenaState();
}

export function getArenaState(): ArenaState {
  if (!current) current = read();
  return current;
}

export function updateArenaState(change: (s: ArenaState) => ArenaState): ArenaState {
  const before = getArenaState();
  const after = change(before);
  if (after === before) return before;
  current = after;
  try {
    localStorage.setItem(KEY, JSON.stringify(after));
  } catch {
    /* storage full or disabled */
  }
  listeners.forEach((fn) => fn());
  return after;
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key !== KEY) return;
    current = read();
    listeners.forEach((fn) => fn());
  });
}

export function useArenaState(): ArenaState {
  return useSyncExternalStore(subscribe, getArenaState, getArenaState);
}
