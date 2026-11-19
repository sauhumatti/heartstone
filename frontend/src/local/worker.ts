// The game engine on this device. Python (Pyodide) runs the very same engine
// the server runs, here in a worker so the page never waits for it. The page
// asks for things by name and gets the replies the server would give; when
// the opponent moves, the worker tells the page without being asked.
import { matches } from './db';
import type { FromWorker, InitMessage, RuntimeProgress, ToWorker } from './protocol';

const scope = self as unknown as {
  postMessage(msg: FromWorker): void;
  onmessage: ((e: MessageEvent<ToWorker>) => void) | null;
  importScripts(...urls: string[]): void;
  fetch: typeof fetch;
  loadPyodide?: (opts: { indexURL: string }) => Promise<any>;
};

// The Python side: engine/local.py does the work, this only opens its door.
const GLUE = `
import sys, json
sys.path.insert(0, "/app")
from engine.local import LocalHost
host = LocalHost()
call = host.call
save = host.save
def restore(buf):
    return json.dumps(host.restore(bytes(buf.to_py())))
`;

/** Requests that change a match: it is saved afterwards, and the opponent may be up. */
const CHANGES = new Set(['create_game', 'mulligan', 'play', 'choose', 'attack', 'power', 'end_turn', 'concede', 'emote', 'set_level']);
/** Matches kept on the device; older ones are dropped. */
const KEEP = 8;

let pyCall: ((method: string, args: string) => string) | null = null;
let pySave: ((gameId: string) => any) | null = null;
/** For each match, the last moment the page has been told about. */
const told = new Map<string, number>();
const moving = new Set<string>();

function report(progress: RuntimeProgress): void {
  scope.postMessage({ progress });
}

function ask<T = any>(method: string, args: Record<string, unknown> = {}): T {
  if (!pyCall) throw new Error('The game engine is not running.');
  const out = JSON.parse(pyCall(method, JSON.stringify(args)));
  if (out.error !== undefined) {
    if (out.detail) console.error(`[engine] ${method}: ${out.detail}`);
    if (typeof out.gone === 'string') {
      // A match kept from before an update broke and the engine let it go: forget it here too.
      told.delete(out.gone);
      void matches.remove(out.gone).catch(() => undefined);
      scope.postMessage({ notice: out.error, gone: out.gone });
    }
    throw new Error(out.error);
  }
  return out.ok as T;
}

async function boot(m: InitMessage): Promise<void> {
  const at = (path: string) => new URL(path, m.base).href;
  // Count the big files as they arrive, so the page can show how far along it is.
  const sizes = new Map(m.runtimeFiles.filter((f) => !f.path.endsWith('.js')).map((f) => [at(f.path), f.bytes]));
  const total = [...sizes.values()].reduce((a, b) => a + b, 0);
  let loaded = 0;
  let open = sizes.size;
  const plain = scope.fetch.bind(scope);
  scope.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const res = await plain(input, init);
    const href = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    if (!res.body || !sizes.has(href)) return res;
    const reader = res.body.getReader();
    const counted = new ReadableStream<Uint8Array>({
      async pull(controller) {
        const { done, value } = await reader.read();
        if (done) {
          controller.close();
          open -= 1;
          if (open <= 0) report({ phase: 'starting' });
          return;
        }
        loaded += value.byteLength;
        report({ phase: 'download', loaded: Math.min(loaded, total), total });
        controller.enqueue(value);
      },
      cancel(reason) {
        return reader.cancel(reason);
      },
    });
    return new Response(counted, { status: res.status, statusText: res.statusText, headers: res.headers });
  }) as typeof fetch;

  report({ phase: 'download', loaded: 0, total });
  let py: any;
  try {
    scope.importScripts(at(`${m.runtimeDir}pyodide.js`));
    py = await scope.loadPyodide!({ indexURL: at(m.runtimeDir) });
  } finally {
    scope.fetch = plain;
  }

  report({ phase: 'cards' });
  const res = await plain(at(m.engine));
  if (!res.ok) throw new Error(`engine pack: ${res.status}`);
  const pack: { files: Record<string, string> } = await res.json();
  for (const [path, text] of Object.entries(pack.files)) {
    const dir = `/app/${path.slice(0, path.lastIndexOf('/'))}`;
    py.FS.mkdirTree(dir);
    py.FS.writeFile(`/app/${path}`, text);
  }
  py.runPython(GLUE);
  pyCall = py.globals.get('call');
  pySave = py.globals.get('save');

  // Bring back the matches this device was keeping.
  const restore: (blob: Uint8Array) => string = py.globals.get('restore');
  const rows = (await matches.all()).sort((a, b) => b.updated - a.updated);
  for (const [i, row] of rows.entries()) {
    const back = i < KEEP ? JSON.parse(restore(row.blob)) : null;
    if (!back) await matches.remove(row.id);
  }
  // Matches that could not be brought back (unreadable, or left behind by an update): say so once.
  for (const notice of ask<{ notices: string[] }>('take_notices').notices) scope.postMessage({ notice });
  report({ phase: 'ready' });
}

async function keep(gameId: string): Promise<void> {
  if (!pySave) return;
  try {
    const proxy = pySave(gameId);
    const blob: Uint8Array = proxy.toJs();
    proxy.destroy();
    await matches.put({ id: gameId, blob, summary: ask('summary', { game_id: gameId }), updated: Date.now() });
  } catch (err) {
    console.error('[engine] could not save the match', err); // a failed save must never stop the match
  }
}

async function prune(): Promise<void> {
  const rows = (await matches.all()).sort((a, b) => b.updated - a.updated);
  for (const row of rows.slice(KEEP)) {
    await matches.remove(row.id);
    try {
      ask('forget', { game_id: row.id });
    } catch {
      /* it was not loaded */
    }
  }
}

/** Tell the page what has happened in a match since it last heard. */
function push(gameId: string): void {
  const payload = ask('state', { game_id: gameId, since: told.get(gameId) ?? null });
  told.set(gameId, payload.state.seq);
  scope.postMessage({ push: gameId, payload });
}

const breathe = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

/** The opponent decides, one decision at a time, and each is shown as it is made. */
async function moveOpponent(gameId: string): Promise<void> {
  if (moving.has(gameId)) return;
  moving.add(gameId);
  try {
    while (ask<boolean>('opponent_pending', { game_id: gameId })) {
      await breathe(); // let a request from the page (conceding, say) in between two decisions
      if (!ask<boolean>('opponent_step', { game_id: gameId })) break;
      push(gameId);
      await keep(gameId);
    }
  } catch (err) {
    console.error('[engine] the opponent could not move', err);
  } finally {
    moving.delete(gameId);
  }
}

scope.onmessage = async (e) => {
  const m = e.data;
  if (m.kind === 'init') {
    try {
      await boot(m);
      scope.postMessage({ id: m.id, ok: true });
    } catch (err: any) {
      const message = String(err?.message || err);
      report({ phase: 'failed', message });
      scope.postMessage({ id: m.id, error: message });
    }
    return;
  }
  let gameId = typeof m.args.game_id === 'string' ? m.args.game_id : '';
  try {
    const out = ask(m.method, m.args);
    if (out && typeof out.game_id === 'string') gameId = out.game_id;
    if (gameId && out && out.state) told.set(gameId, out.state.seq);
    scope.postMessage({ id: m.id, ok: out });
  } catch (err: any) {
    scope.postMessage({ id: m.id, error: String(err?.message || err) });
    return;
  }
  if (!gameId) return;
  if (CHANGES.has(m.method)) {
    if (m.method === 'emote') push(gameId);
    await keep(gameId);
    if (m.method === 'create_game') await prune();
  }
  // Also after a plain look at the match: a match opened again may be waiting for the opponent.
  if (CHANGES.has(m.method) || m.method === 'state') void moveOpponent(gameId);
};
