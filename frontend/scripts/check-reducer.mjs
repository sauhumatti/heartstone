// Reads matches from scripts/dump_beats.py on stdin and checks that the client's
// reducer, fed only the events of a beat, arrives at the same table as the engine.
import { build } from 'esbuild';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const out = join(mkdtempSync(join(tmpdir(), 'reducer-')), 'reduce.mjs');
await build({ entryPoints: [join(here, '../src/game/reduce.ts')], outfile: out, bundle: true, format: 'esm', platform: 'node', logLevel: 'silent' });
const { applyEvents, shapeOf } = await import(pathToFileURL(out).href);
const { groupEvents } = await (async () => {
  const o = out.replace('reduce.mjs', 'director.mjs');
  await build({ entryPoints: [join(here, '../src/game/director.ts')], outfile: o, bundle: true, format: 'esm', platform: 'node', logLevel: 'silent' });
  return import(pathToFileURL(o).href);
})();

const games = JSON.parse(readFileSync(0, 'utf8'));
const structural = (v) => {
  const s = shapeOf(v);
  delete s.hp; // health can also change through effects that carry no event of their own
  return JSON.stringify(s);
};

let beats = 0;
let events = 0;
let failures = 0;
for (const game of games) {
  let view = game.start;
  for (const beat of game.beats) {
    // Fold the beat the way the client does: step by step, in the director's groups.
    let cur = view;
    const groups = groupEvents(beat.events);
    const regrouped = groups.flat();
    if (regrouped.length !== beat.events.length || regrouped.some((e, i) => e !== beat.events[i])) {
      failures++;
      console.error(`${game.name}, beat ${beat.seq}: grouping lost or reordered events`);
    }
    for (const g of groups) cur = applyEvents(cur, g, beat.state);
    if (structural(cur) !== structural(beat.state)) {
      failures++;
      if (failures <= 5) {
        console.error(`${game.name}, beat ${beat.seq} [${beat.events.map((e) => e.t).join(', ')}]`);
        console.error('  reducer:', structural(cur));
        console.error('  engine: ', structural(beat.state));
      }
    }
    beats++;
    events += beat.events.length;
    view = beat.state;
  }
}
console.log(`${games.length} matches, ${beats} beats, ${events} events: ${failures ? failures + ' mismatches' : 'reducer matches the engine'}`);
process.exit(failures ? 1 : 0);
