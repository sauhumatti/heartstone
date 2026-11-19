// The list of everything the game needs to run with no server, written at
// build time (see frontend/offline.plugin.ts).
import { url } from '../paths';
import type { CardDef, DeckInfo, HeroMeta, Level } from '../types';
import type { FileEntry } from './protocol';

export interface OfflineManifest {
  version: string;
  bundled: boolean;
  runtime: { version: string; dir: string; files: FileEntry[] };
  engine: FileEntry;
  catalog: FileEntry;
  shell: FileEntry[];
  art: FileEntry[];
  sfx: FileEntry[];
}

/** What the menus need: asked of the engine when the game was built. */
export interface LocalCatalog {
  heroes: Record<string, HeroMeta>;
  cards: CardDef[];
  decks: DeckInfo[];
  levels: Level[];
  default_level: string;
}

export const MANIFEST_PATH = 'offline/manifest.json';

let manifest: Promise<OfflineManifest> | null = null;
let catalog: Promise<LocalCatalog> | null = null;

async function getJson<T>(path: string, fresh: boolean): Promise<T> {
  const res = await fetch(url(path), fresh ? { cache: 'no-cache' } : undefined);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return (await res.json()) as T;
}

export function offlineManifest(again = false): Promise<OfflineManifest> {
  if (!manifest || again) {
    const asked = getJson<OfflineManifest>(MANIFEST_PATH, true);
    manifest = asked;
    asked.catch(() => {
      if (manifest === asked) manifest = null; // not reachable now; ask again next time
    });
  }
  return manifest;
}

export function localCatalog(): Promise<LocalCatalog> {
  if (!catalog) {
    const asked = offlineManifest().then((m) => getJson<LocalCatalog>(m.catalog.path, false));
    catalog = asked;
    asked.catch(() => {
      if (catalog === asked) catalog = null;
    });
  }
  return catalog;
}
