// Persistence for the player's Campaign progress, relics, and active boss encounter.
import { useSyncExternalStore } from 'react';
import { emptyCampaignState, restoreCampaignState, type CampaignState } from './rules';

const KEY = 'lf_campaign_v1';

let current: CampaignState | null = null;
const listeners = new Set<() => void>();

function read(): CampaignState {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return restoreCampaignState(JSON.parse(raw));
  } catch {
    /* ignore corrupted or unavailable storage */
  }
  return emptyCampaignState();
}

export function getCampaignState(): CampaignState {
  if (!current) current = read();
  return current;
}

export function updateCampaignState(change: (s: CampaignState) => CampaignState): CampaignState {
  const before = getCampaignState();
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

export function useCampaignState(): CampaignState {
  return useSyncExternalStore(subscribe, getCampaignState, getCampaignState);
}
