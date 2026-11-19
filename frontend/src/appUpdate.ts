// Updates of the installed (Android) app, as the page sees them.
//
// The work is done by the app itself (mobile/…/update: asking the server,
// downloading, checking and unpacking a newer version of this page, and
// showing it at the next start). This file asks for that work and keeps the
// one piece of state the menu shows. In a browser, or in an app built
// without updates, everything here is a quiet no-op and the state is 'off'.
//
// Two kinds of update exist. Nearly always it is a new *bundle*: this page
// with its engine, art and sound, swapped in by the app. Rarely it is a new
// *app*, which has to be downloaded and installed by hand.
import { BUNDLED } from './paths';

/** What is installed and shown right now. */
export interface Installed {
  /** The app: "0.2.0". */
  appVersion: string;
  /** The bundle on screen: a date and time as digits, "202611162300". */
  bundle: string;
  /** An update that did not start and was removed at this start; empty if none. */
  rolledBack: string;
}

export type UpdateState =
  /** Not an installed app (or one built without updates): nothing is shown. */
  | { status: 'off' }
  | ({ status: 'idle' } & Installed)
  | ({ status: 'checking' } & Installed)
  | ({ status: 'current' } & Installed)
  /** A newer bundle exists; waiting for a yes because the connection may cost money. */
  | ({ status: 'available'; version: string; bytes: number } & Installed)
  | ({ status: 'downloading'; version: string; received: number; total: number } & Installed)
  /** Downloaded and checked: it is used from the next start. */
  | ({ status: 'ready'; version: string } & Installed)
  | ({ status: 'failed'; code: string; reason: string } & Installed)
  /** A newer app exists; `needed` when the newest bundle will not run on this one. */
  | ({ status: 'app'; versionName: string; bytes: number; needed: boolean } & Installed);

interface NativeInfo {
  enabled?: boolean;
  shell?: { versionCode: number; versionName: string };
  bundle?: string;
  pending?: string;
  rolledBack?: string;
  online?: boolean;
  metered?: boolean;
  latest?: { version?: string; size?: number; newer?: boolean; runsHere?: boolean; staged?: boolean };
  latestShell?: { versionCode?: number; versionName?: string; size?: number; newer?: boolean };
}

interface Bridge {
  nativePromise(plugin: string, method: string, options?: unknown): Promise<any>;
  addListener?(plugin: string, event: string, callback: (data: any) => void): unknown;
}

const PLUGIN = 'AppUpdater';

function bridge(): Bridge | null {
  if (!BUNDLED || typeof window === 'undefined') return null;
  const cap = (window as any).Capacitor;
  return cap && typeof cap.nativePromise === 'function' ? (cap as Bridge) : null;
}

/** Why something failed, in words for the menu. The app sends a code; unknown ones fall back to its own sentence. */
const REASONS: Record<string, string> = {
  offline: 'no connection to the update server',
  refused: 'the update server did not accept this app',
  server: 'the update server gave an answer that made no sense',
  checksum: 'the download arrived damaged',
  size: 'the download was not the size it should be',
  archive: 'the update could not be unpacked',
  space: 'not enough free space on this device',
  cancelled: 'the download was stopped',
  busy: 'a download is already running',
};

let state: UpdateState = { status: 'off' };
let installed: Installed = { appVersion: '', bundle: '', rolledBack: '' };
const watchers = new Set<(s: UpdateState) => void>();
let listening = false;

function set(next: UpdateState): void {
  state = next;
  watchers.forEach((w) => w(state));
}

export function updateState(): UpdateState {
  return state;
}

export function watchUpdates(fn: (s: UpdateState) => void): () => void {
  watchers.add(fn);
  return () => {
    watchers.delete(fn);
  };
}

function takeInfo(info: NativeInfo): void {
  installed = {
    appVersion: info.shell?.versionName ?? installed.appVersion,
    bundle: info.bundle ?? installed.bundle,
    rolledBack: info.rolledBack ?? installed.rolledBack,
  };
}

function failed(err: any): void {
  const code = String(err?.code || 'server');
  set({ status: 'failed', code, reason: REASONS[code] ?? String(err?.message || 'the update did not work'), ...installed });
}

async function download(version: string, bytes: number): Promise<void> {
  const b = bridge();
  if (!b) return;
  set({ status: 'downloading', version, received: 0, total: bytes, ...installed });
  if (!listening && b.addListener) {
    listening = true;
    b.addListener(PLUGIN, 'progress', (p: { received?: number; total?: number }) => {
      if (state.status !== 'downloading') return;
      set({ ...state, received: Number(p?.received) || 0, total: Number(p?.total) || state.total });
    });
  }
  try {
    // the app fetches whatever is newest at that moment, which may already be a later one
    const done: { pending?: string } | undefined = await b.nativePromise(PLUGIN, 'download', {});
    set({ status: 'ready', version: String(done?.pending || version), ...installed });
  } catch (err) {
    failed(err);
  }
}

/**
 * Ask the server whether there is something newer. A newer bundle is fetched
 * at once on a connection that is not metered; on mobile data the menu asks
 * first. `quiet` is the look at start-up: if the server cannot be reached
 * then, nothing is said about it.
 */
export async function checkForUpdates(quiet = false): Promise<void> {
  const b = bridge();
  if (!b || state.status === 'off' || state.status === 'checking' || state.status === 'downloading') return;
  set({ status: 'checking', ...installed });
  let info: NativeInfo;
  try {
    info = await b.nativePromise(PLUGIN, 'check', {});
  } catch (err: any) {
    if (quiet && String(err?.code) === 'offline') set({ status: 'idle', ...installed });
    else failed(err);
    return;
  }
  takeInfo(info);
  const latest = info.latest ?? {};
  const app = info.latestShell ?? {};
  const version = String(latest.version || '');
  const bytes = Number(latest.size) || 0;
  if (latest.newer && latest.runsHere) {
    if (latest.staged) set({ status: 'ready', version, ...installed });
    else if (info.metered) set({ status: 'available', version, bytes, ...installed });
    else await download(version, bytes);
  } else if (app.newer || (latest.newer && !latest.runsHere)) {
    set({ status: 'app', versionName: String(app.versionName || ''), bytes: Number(app.size) || 0, needed: Boolean(latest.newer && !latest.runsHere), ...installed });
  } else {
    set({ status: 'current', ...installed });
  }
}

/** The player said yes to a download on a metered connection. */
export async function downloadUpdate(): Promise<void> {
  if (state.status !== 'available') return;
  await download(state.version, state.bytes);
}

/** Show the downloaded bundle now (the page reloads). Only offered on the menu, never during a match. */
export function restartForUpdate(): void {
  void bridge()
    ?.nativePromise(PLUGIN, 'restart', {})
    .catch(() => undefined);
}

/** Open the newer app's download in the phone's browser. */
export async function openAppDownload(): Promise<void> {
  try {
    await bridge()?.nativePromise(PLUGIN, 'openShell', {});
  } catch (err) {
    failed(err);
  }
}

/**
 * Call once when the page has started. It tells the app that this bundle
 * works (a new one that never says so is dropped at the next start), reads
 * what is installed, and looks for an update if there is a connection.
 */
export async function startAppUpdates(): Promise<void> {
  const b = bridge();
  if (!b) return;
  let info: NativeInfo;
  try {
    info = await b.nativePromise(PLUGIN, 'ready', {});
  } catch {
    return; // an app without the updater: stay 'off'
  }
  if (!info || info.enabled === false) return;
  takeInfo(info);
  if (info.pending) set({ status: 'ready', version: String(info.pending), ...installed });
  else set({ status: 'idle', ...installed });
  if (info.online !== false && state.status === 'idle') await checkForUpdates(true);
}

/** "202611162300" as "2026-11-16 23:00"; anything else as it is. */
export function bundleLabel(version: string): string {
  const m = /^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})$/.exec(version);
  return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}` : version;
}
