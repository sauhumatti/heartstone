// "Make available offline": puts everything the game needs on the device (the
// app itself, the engine and its runtime, all card art, the sound clips), so
// it opens and plays with no connection. The service worker (public/sw.js)
// then answers from what is stored here.
import { BUNDLED, url } from '../paths';
import { MANIFEST_PATH, offlineManifest, type OfflineManifest } from './manifest';
import type { FileEntry } from './protocol';

// The same names public/sw.js uses.
const SHELL = 'shell-v1';
const ART = 'art-v1';
const OFFLINE = 'offline-v1';
const DONE_KEY = 'offline_version';
const AT_ONCE = 6;

export type OfflineState =
  /** A packaged app: everything is inside it already. */
  | { status: 'bundled' }
  /** This browser (or an insecure page) cannot keep the game. */
  | { status: 'unsupported' }
  | { status: 'none'; bytes: number }
  | { status: 'working'; done: number; total: number }
  | { status: 'ready' }
  | { status: 'failed'; message: string };

let state: OfflineState = BUNDLED ? { status: 'bundled' } : { status: 'unsupported' };
const watchers = new Set<(s: OfflineState) => void>();
let working: Promise<void> | null = null;

export function offlineState(): OfflineState {
  return state;
}

export function watchOffline(fn: (s: OfflineState) => void): () => void {
  watchers.add(fn);
  return () => {
    watchers.delete(fn);
  };
}

function set(next: OfflineState): void {
  state = next;
  watchers.forEach((fn) => fn(next));
}

function supported(): boolean {
  return typeof caches !== 'undefined' && 'serviceWorker' in navigator && window.isSecureContext;
}

function plan(m: OfflineManifest): { entry: FileEntry; cache: string }[] {
  return [
    ...m.shell.map((entry) => ({ entry, cache: SHELL })),
    ...m.runtime.files.map((entry) => ({ entry, cache: OFFLINE })),
    { entry: m.engine, cache: OFFLINE },
    { entry: m.catalog, cache: OFFLINE },
    ...m.art.map((entry) => ({ entry, cache: ART })),
    ...m.sfx.map((entry) => ({ entry, cache: ART })),
  ];
}

function sizeOf(m: OfflineManifest): number {
  return plan(m).reduce((sum, j) => sum + j.entry.bytes, 0);
}

/** Work out where this device stands. Called once when the app opens. */
export async function checkOffline(): Promise<OfflineState> {
  if (BUNDLED) return state;
  if (!supported()) {
    set({ status: 'unsupported' });
    return state;
  }
  if (working) return state;
  const stored = localStorage.getItem(DONE_KEY);
  try {
    const m = await offlineManifest();
    if (!stored) set({ status: 'none', bytes: sizeOf(m) });
    else if (stored === m.version) set({ status: 'ready' });
    else void makeAvailableOffline(); // a newer build: fetch what changed, quietly
  } catch {
    // The list cannot be had right now (no connection): what is stored is what there is.
    set(stored ? { status: 'ready' } : { status: 'unsupported' });
  }
  return state;
}

/** Store the whole game on this device. Safe to call again: only what is missing is fetched. */
export function makeAvailableOffline(): Promise<void> {
  if (working) return working;
  working = (async () => {
    if (!supported()) throw new Error('This browser cannot keep the game for offline play.');
    const m = await offlineManifest(true);
    const open = new Map<string, Cache>();
    for (const name of [SHELL, ART, OFFLINE]) open.set(name, await caches.open(name));

    const missing: { entry: FileEntry; cache: string }[] = [];
    for (const job of plan(m)) {
      if (!(await open.get(job.cache)!.match(url(job.entry.path)))) missing.push(job);
    }
    const total = missing.reduce((sum, j) => sum + j.entry.bytes, 0);
    let done = 0;
    set({ status: 'working', done, total });

    let next = 0;
    const worker = async (): Promise<void> => {
      while (next < missing.length) {
        const job = missing[next++];
        const res = await fetch(url(job.entry.path));
        if (!res.ok) throw new Error(`${job.entry.path} (${res.status})`);
        await open.get(job.cache)!.put(url(job.entry.path), res);
        done += job.entry.bytes;
        set({ status: 'working', done, total });
      }
    };
    await Promise.all(Array.from({ length: AT_ONCE }, worker));

    // The page itself, under the address the service worker looks it up by, and the list last.
    const page = await fetch(url('./'), { cache: 'no-cache' });
    if (!page.ok) throw new Error(`the page (${page.status})`);
    await open.get(SHELL)!.put(url('./'), page);
    await open.get(OFFLINE)!.put(url(MANIFEST_PATH), new Response(JSON.stringify(m), { headers: { 'Content-Type': 'application/json' } }));

    // Engine and runtime files of an earlier build are no longer needed.
    const wanted = new Set([url(MANIFEST_PATH), url(m.engine.path), url(m.catalog.path), ...m.runtime.files.map((f) => url(f.path))]);
    for (const req of await open.get(OFFLINE)!.keys()) {
      if (!wanted.has(req.url)) await open.get(OFFLINE)!.delete(req);
    }

    localStorage.setItem(DONE_KEY, m.version);
    // Ask the browser not to clear this when it runs short of space.
    void navigator.storage?.persist?.().catch(() => false);
    set({ status: 'ready' });
  })()
    .catch((err: any) => {
      const stored = localStorage.getItem(DONE_KEY);
      // An update that did not finish leaves the earlier copy in place and usable.
      set(stored ? { status: 'ready' } : { status: 'failed', message: String(err?.message || err) });
    })
    .finally(() => {
      working = null;
    });
  return working;
}
