// Build step for playing with no server. It adds to the build:
//
//   py/<version>/…              the Python runtime (Pyodide), served from our own files
//   offline/engine-<hash>.json  the game engine's own source (engine/ and data/), unchanged
//   offline/catalog-<hash>.json the cards, heroes, starter decks and opponent levels, for the menus
//   offline/manifest.json       every file a device must hold to play offline, with sizes
//   bundle.json                 this build's version, when it is one an installed app can update to
//
// The engine pack is made from the same files the server runs, at build time,
// so the two cannot drift apart. With VITE_BUNDLED=1 (the packaged app) the
// card art is copied in as well, so nothing at all is fetched from a server.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { cpSync, existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import type { Plugin } from 'vite';

const RUNTIME_FILES = ['pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json'];

interface Entry {
  path: string;
  bytes: number;
}

function listDir(dir: string, prefix: string, keep: (name: string) => boolean): Entry[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter(keep)
    .sort()
    .map((name) => ({ path: prefix + name, bytes: statSync(path.join(dir, name)).size }));
}

export function offline(): Plugin {
  const frontend = __dirname;
  const repo = path.resolve(frontend, '..');
  const bundled = process.env.VITE_BUNDLED === '1';
  let outDir = path.join(frontend, 'dist');

  const enginePack = (): string => {
    const files: Record<string, string> = {};
    const walk = (relDir: string): void => {
      const absDir = path.join(repo, relDir);
      for (const name of readdirSync(absDir).sort()) {
        if (name === '__pycache__' || name.startsWith('.')) continue;
        const rel = `${relDir}/${name}`;
        const abs = path.join(repo, rel);
        if (statSync(abs).isDirectory()) walk(rel);
        else if (name.endsWith('.py') || name.endsWith('.json')) files[rel] = readFileSync(abs, 'utf8');
      }
    };
    for (const dir of ['engine', 'data']) walk(dir);
    return JSON.stringify({ files });
  };

  // Asked of the engine itself, so the menus show exactly what a match will use.
  const catalog = (): string =>
    execFileSync(
      'python3',
      [
        '-c',
        'import json\nfrom engine import local\nh = local.LocalHost()\nprint(json.dumps({**local.catalog(), "decks": local.starter_decks(), **h.info()}))',
      ],
      { cwd: repo, env: { ...process.env, PYTHONPATH: repo }, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 },
    ).trim();

  return {
    name: 'offline-play',
    apply: 'build',
    enforce: 'post',
    configResolved(config) {
      outDir = path.resolve(config.root, config.build.outDir);
    },
    generateBundle(_options, bundle) {
      const pyDir = path.join(frontend, 'node_modules', 'pyodide');
      const pyVersion: string = JSON.parse(readFileSync(path.join(pyDir, 'package.json'), 'utf8')).version;
      const runtimeDir = `py/${pyVersion}/`;
      const runtime: Entry[] = [];
      for (const name of RUNTIME_FILES) {
        const source = readFileSync(path.join(pyDir, name));
        this.emitFile({ type: 'asset', fileName: runtimeDir + name, source });
        runtime.push({ path: runtimeDir + name, bytes: source.length });
      }

      const pack = enginePack();
      const cat = catalog();
      const tag = createHash('sha256').update(pyVersion).update(pack).update(cat).digest('hex').slice(0, 10);
      const engine = { path: `offline/engine-${tag}.json`, bytes: Buffer.byteLength(pack) };
      const catalogFile = { path: `offline/catalog-${tag}.json`, bytes: Buffer.byteLength(cat) };
      this.emitFile({ type: 'asset', fileName: engine.path, source: pack });
      this.emitFile({ type: 'asset', fileName: catalogFile.path, source: cat });

      // The app itself: what this build produced, plus the fixed files beside it.
      const shell: Entry[] = [];
      for (const [name, item] of Object.entries(bundle)) {
        if (name.startsWith('py/') || name.startsWith('offline/') || name.endsWith('.map') || name === 'index.html') continue;
        const body = item.type === 'chunk' ? item.code : item.source;
        shell.push({ path: name, bytes: typeof body === 'string' ? Buffer.byteLength(body) : body.length });
      }
      const pub = path.join(frontend, 'public');
      shell.push(...listDir(path.join(pub, 'icons'), 'icons/', () => true));
      if (existsSync(path.join(pub, 'favicon.svg'))) shell.push({ path: 'favicon.svg', bytes: statSync(path.join(pub, 'favicon.svg')).size });
      shell.sort((a, b) => a.path.localeCompare(b.path));

      const art = listDir(path.join(repo, 'assets', 'art'), 'art/', (n) => n.endsWith('.webp'));
      // Sound clips and the music's instrument recordings (one folder per instrument).
      const sfx = listDir(path.join(pub, 'sfx'), 'sfx/', (n) => n.endsWith('.mp3'));
      const music = path.join(pub, 'music');
      sfx.push(...listDir(music, 'music/', (n) => n.endsWith('.json')));
      if (existsSync(music)) for (const d of readdirSync(music).sort()) {
        if (statSync(path.join(music, d)).isDirectory()) sfx.push(...listDir(path.join(music, d), `music/${d}/`, (n) => n.endsWith('.mp3')));
      }

      // A build made as an update for installed apps says which one it is (scripts/release.sh
      // sets the version: a date and time, later for every release). The app compares it with
      // what the server offers, and the menu shows it.
      const bundleVersion = String(process.env.VITE_BUNDLE_VERSION || '');
      if (bundled && bundleVersion) {
        if (!/^[0-9]{1,20}$/.test(bundleVersion)) throw new Error(`VITE_BUNDLE_VERSION must be digits, got "${bundleVersion}"`);
        this.emitFile({ type: 'asset', fileName: 'bundle.json', source: JSON.stringify({ version: bundleVersion }) });
      }

      const manifest = { bundled, runtime: { version: pyVersion, dir: runtimeDir, files: runtime }, engine, catalog: catalogFile, shell, art, sfx };
      const version = createHash('sha256').update(JSON.stringify(manifest)).digest('hex').slice(0, 12);
      this.emitFile({ type: 'asset', fileName: 'offline/manifest.json', source: JSON.stringify({ version, ...manifest }) });
    },
    closeBundle() {
      // The packaged app has no server to ask for pictures.
      if (bundled) cpSync(path.join(repo, 'assets', 'art'), path.join(outDir, 'art'), { recursive: true });
    },
  };
}
