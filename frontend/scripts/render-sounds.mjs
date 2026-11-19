// node scripts/render-sounds.mjs <outDir>
// Writes every raw sound of the bank as a WAV file, to listen to or measure them outside the game.
import { build } from 'esbuild';
import { mkdirSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const FRONT = join(dirname(fileURLToPath(import.meta.url)), '..');
const out = process.argv[2];
mkdirSync(out, { recursive: true });
const bundle = join(tmpdir(), `bank-${process.pid}.mjs`);
await build({ entryPoints: [join(FRONT, 'src/audio/bank.ts')], outfile: bundle, bundle: true, format: 'esm', platform: 'node', logLevel: 'silent' });
const bank = await import(pathToFileURL(bundle).href);
const SR = 44100;
function wav(samples, sr = SR) {
  const b = Buffer.alloc(44 + samples.length * 2);
  b.write('RIFF', 0); b.writeUInt32LE(36 + samples.length * 2, 4); b.write('WAVEfmt ', 8); b.writeUInt32LE(16, 16); b.writeUInt16LE(1, 20); b.writeUInt16LE(1, 22);
  b.writeUInt32LE(sr, 24); b.writeUInt32LE(sr * 2, 28); b.writeUInt16LE(2, 32); b.writeUInt16LE(16, 34); b.write('data', 36); b.writeUInt32LE(samples.length * 2, 40);
  for (let i = 0; i < samples.length; i++) b.writeInt16LE(Math.max(-32768, Math.min(32767, Math.round(samples[i] * 32767))), 44 + i * 2);
  return b;
}
const t0 = Date.now();
let n = 0;
for (const [name, r] of Object.entries(bank.RECIPES)) {
  for (let v = 0; v < r.variants; v++) { writeFileSync(join(out, `${name}-${v}.wav`), wav(bank.sample(name, SR, v))); n++; }
}
for (const midi of [50, 57, 62, 69, 74, 81]) { writeFileSync(join(out, `pluck-${midi}.wav`), wav(bank.pluckNote(SR, midi))); n++; }
console.log(`${n} files in ${Date.now() - t0} ms`);
