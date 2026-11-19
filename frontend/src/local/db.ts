// Matches played on this device are kept in the browser's own database, so
// they are still there after the app is closed. The worker saves and restores
// them; the page only reads their summaries to list them.
import type { GameSummary } from '../types';

export interface SavedMatch {
  id: string;
  /** The whole match, as the engine wrote it. */
  blob: Uint8Array;
  summary: GameSummary;
  updated: number;
}

const NAME = 'local-play';
const STORE = 'matches';

function open(): Promise<IDBDatabase | null> {
  return new Promise((resolve) => {
    try {
      const req = indexedDB.open(NAME, 1);
      req.onupgradeneeded = () => {
        req.result.createObjectStore(STORE, { keyPath: 'id' });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
      req.onblocked = () => resolve(null);
    } catch {
      resolve(null); // no database here (some private windows): matches are simply not kept
    }
  });
}

async function run<T>(mode: IDBTransactionMode, ask: (store: IDBObjectStore) => IDBRequest<T>): Promise<T | null> {
  const db = await open();
  if (!db) return null;
  try {
    return await new Promise<T | null>((resolve) => {
      const tx = db.transaction(STORE, mode);
      const req = ask(tx.objectStore(STORE));
      let value: T | null = null;
      req.onsuccess = () => {
        value = req.result;
      };
      tx.oncomplete = () => resolve(value);
      tx.onerror = () => resolve(null);
      tx.onabort = () => resolve(null);
    });
  } catch {
    return null;
  } finally {
    db.close();
  }
}

export const matches = {
  async all(): Promise<SavedMatch[]> {
    return (await run<SavedMatch[]>('readonly', (s) => s.getAll())) ?? [];
  },
  async put(row: SavedMatch): Promise<void> {
    await run('readwrite', (s) => s.put(row));
  },
  async remove(id: string): Promise<void> {
    await run('readwrite', (s) => s.delete(id));
  },
};
