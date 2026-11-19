// The page's side of the on-device engine: starts the worker when it is first
// needed, sends it requests, and hands on what it reports.
import type { GameSummary, StatePayload } from '../types';
import { matches } from './db';
import { offlineManifest } from './manifest';
import type { CallMessage, FromWorker, InitMessage, RuntimeProgress } from './protocol';

const ID_PREFIX = 'local_';
/** A window event: the engine has something to tell the player ({ message, gone? }). */
export const LOCAL_NOTICE = 'local-notice';

let worker: Worker | null = null;
let starting: Promise<void> | null = null;
let nextId = 1;
let progress: RuntimeProgress = { phase: 'idle' };
const waiting = new Map<number, { resolve(v: any): void; reject(e: Error): void }>();
const pushes = new Map<string, Set<(p: StatePayload) => void>>();
const watchers = new Set<(p: RuntimeProgress) => void>();

/** Was this match made on this device (rather than on the server)? */
export function isLocalGame(gameId: string): boolean {
  return gameId.startsWith(ID_PREFIX);
}

export function runtimeProgress(): RuntimeProgress {
  return progress;
}

/** Follow the engine getting ready. Returns how to stop following. */
export function watchRuntime(fn: (p: RuntimeProgress) => void): () => void {
  watchers.add(fn);
  return () => {
    watchers.delete(fn);
  };
}

function setProgress(next: RuntimeProgress): void {
  progress = next;
  watchers.forEach((fn) => fn(next));
}

function send<T>(msg: Omit<InitMessage, 'id'> | Omit<CallMessage, 'id'>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    if (!worker) {
      reject(new Error('The game engine is not running.'));
      return;
    }
    const id = nextId++;
    waiting.set(id, { resolve, reject });
    worker.postMessage({ ...msg, id });
  });
}

function onMessage(e: MessageEvent<FromWorker>): void {
  const m = e.data;
  if ('progress' in m) {
    setProgress(m.progress);
  } else if ('push' in m) {
    pushes.get(m.push)?.forEach((fn) => fn(m.payload as StatePayload));
  } else if ('notice' in m) {
    window.dispatchEvent(new CustomEvent(LOCAL_NOTICE, { detail: { message: m.notice, gone: m.gone } }));
  } else {
    const w = waiting.get(m.id);
    if (!w) return;
    waiting.delete(m.id);
    if ('error' in m) w.reject(new Error(m.error));
    else w.resolve(m.ok);
  }
}

function stop(message: string): void {
  worker?.terminate();
  worker = null;
  starting = null;
  waiting.forEach((w) => w.reject(new Error(message)));
  waiting.clear();
  setProgress({ phase: 'failed', message });
}

/** Start the engine on this device (once). The first start takes a few seconds. */
export function startRuntime(): Promise<void> {
  if (starting) return starting;
  starting = (async () => {
    setProgress({ phase: 'download', loaded: 0, total: 0 });
    let manifest;
    try {
      manifest = await offlineManifest();
    } catch {
      throw new Error('The game is not stored on this device yet. Connect once, then try again.');
    }
    worker = new Worker(new URL('./worker.ts', import.meta.url));
    worker.onmessage = onMessage;
    worker.onerror = (ev) => stop(ev.message || 'The game engine stopped.');
    await send({
      kind: 'init',
      base: document.baseURI,
      runtimeDir: manifest.runtime.dir,
      runtimeFiles: manifest.runtime.files,
      engine: manifest.engine.path,
    });
  })();
  starting.catch((err: any) => stop(String(err?.message || err)));
  return starting;
}

/** Ask the on-device engine for something (see `LocalHost` in engine/local.py). */
export async function callLocal<T>(method: string, args: Record<string, unknown> = {}): Promise<T> {
  await startRuntime();
  return send<T>({ kind: 'call', method, args });
}

/** Hear about a match whenever something happens in it unasked (the opponent moving). */
export function onLocalPush(gameId: string, fn: (p: StatePayload) => void): () => void {
  let set = pushes.get(gameId);
  if (!set) pushes.set(gameId, (set = new Set()));
  set.add(fn);
  return () => {
    set!.delete(fn);
  };
}

/** The matches kept on this device, newest first. Needs no running engine. */
export async function localGames(): Promise<GameSummary[]> {
  const rows = await matches.all();
  return rows.sort((a, b) => b.updated - a.updated).map((r) => ({ ...r.summary, is_latest: false }));
}
