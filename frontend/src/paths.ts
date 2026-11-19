// Where things are. The page's own files (art, sounds, the offline engine) are
// always relative to the page, so the game works at "/" and under any
// sub-path. The game server is the same place unless the build names another
// (VITE_SERVER_URL), which is how a packaged app reaches it.

/** A packaged app: every file is inside it, nothing is fetched to make it work offline. */
export const BUNDLED: boolean = import.meta.env.VITE_BUNDLED === '1';

const named = String(import.meta.env.VITE_SERVER_URL || '').trim();
const SERVER_URL = named && !named.endsWith('/') ? `${named}/` : named;

/** Is there a game server this build could talk to at all? A packaged app without a named one has none. */
export const HAS_SERVER: boolean = !BUNDLED || SERVER_URL !== '';

export function url(path: string): string {
  return new URL(path, document.baseURI).toString();
}

export function serverUrl(path: string): string {
  return new URL(path, SERVER_URL || document.baseURI).toString();
}

export function artUrl(id: string): string {
  return url(`art/${id}.webp`);
}

export function wsUrl(path: string): string {
  const u = new URL(path, SERVER_URL || document.baseURI);
  u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
  return u.toString();
}
