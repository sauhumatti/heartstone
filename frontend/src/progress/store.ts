// Where the profile is kept: on this device, under one key. A browser and an
// installed app each keep their own; nothing is sent anywhere.
import { useSyncExternalStore } from 'react';
import { newProfile, type Profile, restore } from './rules';

/** The number is the shape of what is stored: a different shape gets a different key. */
const KEY = 'lf_progress_v1';

let current: Profile | null = null;
const listeners = new Set<() => void>();

function read(): Profile {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return restore(JSON.parse(raw), Date.now());
  } catch {
    /* nothing kept, storage switched off, or not readable: start afresh */
  }
  return newProfile(Date.now());
}

export function getProfile(): Profile {
  if (!current) current = read();
  return current;
}

/** Changes the profile and keeps it. `change` answers the same profile to change nothing. */
export function updateProfile(change: (p: Profile) => Profile): Profile {
  const before = getProfile();
  const after = change(before);
  if (after === before) return before;
  current = after;
  try {
    localStorage.setItem(KEY, JSON.stringify(after));
  } catch {
    /* storage full or switched off: the profile lives for this visit only */
  }
  listeners.forEach((fn) => fn());
  return after;
}

function subscribe(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

// The game open in another tab changed the profile: take its word for it.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key !== KEY) return;
    current = read();
    listeners.forEach((fn) => fn());
  });
}

export function useProfile(): Profile {
  return useSyncExternalStore(subscribe, getProfile, getProfile);
}
