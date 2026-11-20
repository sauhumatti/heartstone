// Checks the written music (src/audio/pieces.ts): every bar adds up, every note is in its
// instrument's recorded range, no part is missing. Run with `npm run test:music`.
import { build } from 'esbuild';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const out = join(mkdtempSync(join(tmpdir(), 'music-')), 'pieces.mjs');
await build({ entryPoints: [join(here, '../src/audio/pieces.ts')], outfile: out, bundle: true, format: 'esm', platform: 'node', logLevel: 'silent' });
const { PIECES, render, KIT } = await import(pathToFileURL(out).href);
const samples = JSON.parse(readFileSync(join(here, '../public/music/samples.json'), 'utf8'));

const NAMES = { C: 0, 'C#': 1, D: 2, 'D#': 3, E: 4, F: 5, 'F#': 6, G: 7, 'G#': 8, A: 9, 'A#': 10, B: 11 };
const toMidi = (n) => { const m = /^([A-G]#?)(-?\d)$/.exec(n); return 12 * (Number(m[2]) + 1) + NAMES[m[1]]; };
// How far a recorded note may be bent to reach a written one before it sounds wrong.
const STRETCH = 5;
const range = {};
for (const [inst, notes] of Object.entries(samples.pitched)) {
  const ms = Object.keys(notes).map(toMidi);
  range[inst] = [Math.min(...ms) - STRETCH, Math.max(...ms) + STRETCH];
}
const kitNotes = new Set(Object.values(KIT));

let problems = 0;
for (const p of PIECES) {
  const { events, seconds, errors } = render(p, 1);
  for (const e of errors) { console.error(`${p.id}: ${e}`); problems++; }
  const byInst = {};
  for (const e of events) {
    byInst[e.inst] = (byInst[e.inst] || 0) + 1;
    if (e.inst === 'kit' || e.inst === 'kitX') {
      if (!kitNotes.has(e.midi)) { console.error(`${p.id}: kit note ${e.midi} has no recording`); problems++; }
      continue;
    }
    const r = range[e.inst];
    if (!r) { console.error(`${p.id}: no instrument ${e.inst}`); problems++; continue; }
    if (e.midi < r[0] || e.midi > r[1]) { console.error(`${p.id}: ${e.inst} note ${e.midi} outside ${r}`); problems++; }
    if (!(e.vel > 0 && e.vel <= 1) || !(e.dur > 0)) { console.error(`${p.id}: bad note ${JSON.stringify(e)}`); problems++; }
  }
  console.log(`${p.title.padEnd(22)} ${seconds.toFixed(0).padStart(4)} s  ${String(events.length).padStart(5)} notes  ${Object.entries(byInst).map(([k, v]) => `${k} ${v}`).join(', ')}`);
}
if (problems) { console.error(`${problems} problems`); process.exitCode = 1; } else console.log('music: all bars add up and every note is playable');
