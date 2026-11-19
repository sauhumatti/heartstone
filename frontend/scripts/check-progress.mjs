// Checks the rules of rating, ranks and packs (src/progress/rules.ts): run with
// `npm run test:progress`. No browser and no engine are needed.
import { build } from 'esbuild';
import assert from 'node:assert/strict';
import { mkdtempSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const out = join(mkdtempSync(join(tmpdir(), 'progress-')), 'rules.mjs');
await build({ entryPoints: [join(here, '../src/progress/rules.ts')], outfile: out, bundle: true, format: 'esm', platform: 'node', logLevel: 'silent' });
const R = await import(pathToFileURL(out).href);

let checks = 0;
const test = (name, fn) => {
  try {
    fn();
    checks += 1;
  } catch (e) {
    console.error(`FAILED: ${name}\n${e.stack || e}`);
    process.exitCode = 1;
  }
};

/** A repeatable stand-in for Math.random. */
const dice = (seed) => () => {
  seed = (seed * 1664525 + 1013904223) >>> 0;
  return seed / 4294967296;
};

const fresh = () => R.newProfile(1000);
const play = (p, id, opponent, result) => R.recordMatch(p, { id, opponent, result, at: 2000 });

test('a new profile starts at 1000, as a Candle, with nothing', () => {
  const p = fresh();
  assert.equal(p.rating, 1000);
  assert.equal(R.RANKS[p.bestRank].name, 'Candle');
  assert.deepEqual([p.packs, p.meter, p.embers, p.owned.length], [0, 0, 0, 0]);
  assert.deepEqual(p.worn, R.DEFAULT_WORN);
});

test('the rating moves by Elo: K 40 for ten matches, then 24', () => {
  assert.equal(R.kFactor(0), 40);
  assert.equal(R.kFactor(9), 40);
  assert.equal(R.kFactor(10), 24);
  assert.ok(Math.abs(R.expectedScore(1000, 1000) - 0.5) < 1e-9);
  assert.equal(R.nextRating(1000, 1000, 'win', 0), 1020);
  assert.equal(R.nextRating(1000, 1000, 'loss', 0), 980);
  assert.equal(R.nextRating(1000, 1000, 'draw', 0), 1000);
  assert.equal(R.nextRating(1000, 1000, 'win', 10), 1012);
  // Beating a much weaker opponent is worth little, losing to it costs a lot.
  const up = R.nextRating(1400, 800, 'win', 50) - 1400;
  const down = 1400 - R.nextRating(1400, 800, 'loss', 50);
  assert.ok(up > 0 && up < 1 && down > 23, `${up} ${down}`);
});

test('the rating never falls below the floor', () => {
  assert.equal(R.nextRating(100.2, 800, 'loss', 50), 100);
  let p = { ...fresh(), rating: 100 };
  p = play(p, 'a', 'easy', 'loss').profile;
  assert.equal(p.rating, 100);
});

test('ranks follow the rating', () => {
  assert.equal(R.RANKS.length, 8);
  assert.equal(R.RANKS[R.rankIndex(100)].name, 'Spark');
  assert.equal(R.RANKS[R.rankIndex(849.99)].name, 'Spark');
  assert.equal(R.RANKS[R.rankIndex(850)].name, 'Wick');
  assert.equal(R.RANKS[R.rankIndex(1449)].name, 'Lighthouse');
  assert.equal(R.RANKS[R.rankIndex(2000)].name, 'Daystar');
  // A new player stands in the middle of a rank: one loss does not cost it.
  assert.equal(R.rankIndex(R.nextRating(R.START_RATING, R.OPPONENTS.easy.rating, 'loss', 0)), R.rankIndex(R.START_RATING));
  const mid = R.rankProgress(1000);
  assert.equal(mid.rank.name, 'Candle');
  assert.equal(mid.next.name, 'Lamp');
  assert.equal(mid.fraction, 0.5);
  assert.equal(mid.toNext, 50);
  const top = R.rankProgress(1600);
  assert.deepEqual([top.next, top.fraction, top.toNext], [null, 1, 0]);
  const low = R.rankProgress(800);
  assert.equal(low.fraction, 0.5);
});

test('who the opponent is', () => {
  assert.equal(R.opponentOf('ai_vs_human', 'easy'), 'easy');
  assert.equal(R.opponentOf('ai_vs_human', 'hard'), 'hard');
  assert.equal(R.opponentOf('ai_vs_human', undefined), 'normal');
  assert.equal(R.opponentOf('bot_vs_human'), 'bot');
  assert.equal(R.opponentOf('agent_vs_human'), 'agent');
  assert.equal(R.opponentOf('cli_vs_human'), null);
  assert.equal(R.weakerOf('hard', 'easy'), 'easy');
  assert.equal(R.weakerOf('hard', null), null);
  assert.ok(R.OPPONENTS.easy.rating < R.OPPONENTS.bot.rating && R.OPPONENTS.bot.rating < R.OPPONENTS.normal.rating && R.OPPONENTS.normal.rating < R.OPPONENTS.hard.rating);
});

test('a match is counted exactly once', () => {
  const first = play(fresh(), 'g1', 'normal', 'win');
  assert.equal(first.profile.played, 1);
  assert.ok(first.profile.rating > 1000);
  const again = play(first.profile, 'g1', 'normal', 'loss');
  assert.equal(again.profile, first.profile);
  assert.deepEqual(again.record, first.record);
  assert.equal(first.record.before, 1000);
  assert.equal(first.record.after, first.profile.rating);
});

test('three wins give a pack; a loss or a draw moves nothing on the meter', () => {
  let p = fresh();
  p = play(p, 'a', 'easy', 'win').profile;
  p = play(p, 'b', 'easy', 'loss').profile;
  p = play(p, 'c', 'easy', 'draw').profile;
  assert.deepEqual([p.meter, p.packs], [1, 0]);
  p = play(p, 'd', 'easy', 'win').profile;
  const third = play(p, 'e', 'easy', 'win');
  assert.deepEqual([third.profile.meter, third.profile.packs], [0, 1]);
  assert.deepEqual([third.record.meterBefore, third.record.meterAfter, third.record.steps, third.record.packs], [2, 0, 1, 1]);
  assert.deepEqual([third.profile.wins, third.profile.losses, third.profile.draws, third.profile.streak], [3, 1, 1, 2]);
});

test('a win over the hard level counts double, and what is left over is kept', () => {
  let p = { ...fresh(), bestRank: 7 };
  p = play(p, 'a', 'hard', 'win').profile;
  assert.deepEqual([p.meter, p.packs], [2, 0]);
  p = play(p, 'b', 'hard', 'win').profile;
  assert.deepEqual([p.meter, p.packs], [1, 1]);
});

test('a rank reached for the first time gives a pack, once', () => {
  let p = { ...fresh(), rating: 1045, played: 20 };
  const up = play(p, 'a', 'hard', 'win');
  assert.equal(R.RANKS[up.record.rankAfter].name, 'Lamp');
  assert.equal(up.record.newBest, true);
  assert.equal(up.profile.packs, 1);
  assert.equal(up.profile.bestRank, 3);
  // Falling back and climbing again is no new best.
  p = { ...up.profile, rating: 1045, meter: 0 };
  const again = play(p, 'b', 'hard', 'win');
  assert.equal(again.record.newBest, false);
  assert.equal(again.profile.packs, 1);
});

test('a pack holds three different things and takes one pack', () => {
  for (let seed = 1; seed <= 200; seed++) {
    const p = { ...fresh(), packs: 2 };
    const { profile, finds } = R.openPack(p, dice(seed));
    assert.equal(finds.length, 3);
    assert.equal(new Set(finds.map((f) => f.id)).size, 3);
    assert.ok(finds.every((f) => R.cosmetic(f.id)?.tier), 'only findable things');
    assert.ok(finds.every((f) => f.isNew && f.embers === 0));
    assert.deepEqual([profile.packs, profile.opened, profile.owned.length], [1, 1, 3]);
  }
});

test('no pack, nothing to open', () => {
  const p = fresh();
  const { profile, finds } = R.openPack(p, dice(1));
  assert.equal(profile, p);
  assert.equal(finds.length, 0);
});

test('while something is missing every pack has something new; second copies become embers', () => {
  for (let seed = 1; seed <= 40; seed++) {
    const rng = dice(seed);
    let p = { ...fresh(), packs: 500 };
    let opened = 0;
    while (p.owned.length < R.FINDABLE.length) {
      const before = p;
      const { profile, finds } = R.openPack(p, rng);
      opened += 1;
      assert.ok(finds.some((f) => f.isNew), `seed ${seed}: pack ${opened} had nothing new`);
      for (const f of finds) {
        assert.equal(f.isNew, !before.owned.includes(f.id));
        assert.equal(f.embers, f.isNew ? 0 : R.TIERS[R.cosmetic(f.id).tier].embers);
      }
      assert.equal(profile.embers - before.embers, finds.reduce((s, f) => s + f.embers, 0));
      p = profile;
      assert.ok(opened <= R.FINDABLE.length, 'the collection completes');
    }
    assert.equal(new Set(p.owned).size, p.owned.length);
    // With everything owned a pack is all embers.
    const { profile, finds } = R.openPack(p, rng);
    assert.ok(finds.every((f) => !f.isNew && f.embers > 0));
    assert.equal(profile.owned.length, R.FINDABLE.length);
  }
});

test('the rarer tiers turn up less often', () => {
  const rng = dice(7);
  const seen = { paper: 0, glass: 0, gilt: 0 };
  for (let i = 0; i < 3000; i++) {
    const p = { ...fresh(), packs: 1, owned: R.FINDABLE.map((c) => c.id) };
    for (const f of R.openPack(p, rng).finds) seen[R.cosmetic(f.id).tier] += 1;
  }
  assert.ok(seen.paper > seen.glass && seen.glass > seen.gilt && seen.gilt > 0, JSON.stringify(seen));
});

test('embers buy a missing thing, once, and only with enough', () => {
  const id = 'back_chart';
  let p = { ...fresh(), embers: 119 };
  assert.equal(R.priceOf(p, id), 120);
  assert.equal(R.buy(p, id), p);
  p = { ...p, embers: 150 };
  const bought = R.buy(p, id);
  assert.deepEqual([bought.embers, bought.owned], [30, [id]]);
  assert.equal(R.priceOf(bought, id), null);
  assert.equal(R.buy(bought, id), bought);
  assert.equal(R.priceOf(p, 'back_default'), null);
  assert.equal(R.priceOf(p, 'nonsense'), null);
});

test('only what is owned can be worn', () => {
  let p = fresh();
  assert.equal(R.wear(p, 'back_ember'), p);
  p = { ...p, owned: ['back_ember', 'title_night_owl'] };
  p = R.wear(p, 'back_ember');
  assert.equal(p.worn.back, 'back_ember');
  assert.equal(R.titleText(p), '');
  p = R.wear(p, 'title_night_owl');
  assert.equal(R.titleText(p), 'Night Owl');
  p = R.wear(p, 'back_default');
  assert.equal(p.worn.back, 'back_default');
  assert.equal(R.wear(p, 'nonsense'), p);
});

test('a kept profile is made whole again, whatever was stored', () => {
  for (const junk of [null, 5, 'x', [], {}, { rating: 'high', owned: 'all', worn: 3, matches: {}, seen: 7 }]) {
    const p = R.restore(junk, 1000);
    assert.equal(p.rating, 1000);
    assert.deepEqual(p.worn, R.DEFAULT_WORN);
    assert.deepEqual([p.owned, p.matches, p.seen], [[], [], []]);
  }
  const kept = R.restore(
    { rating: 1234.5, played: 12, meter: 9, packs: 2, embers: 15, owned: ['back_ember', 'back_ember', 'back_default', 'gone'], worn: { back: 'back_moth', table: 'table_oak', title: 'title_none' }, seen: ['a', 4, 'b'], bestRank: 1 },
    1000,
  );
  assert.equal(kept.rating, 1234.5);
  assert.deepEqual(kept.owned, ['back_ember']);
  assert.equal(kept.meter, R.PACK_STEPS - 1);
  // Not owned, so not worn; the best rank is never below where the rating stands.
  assert.deepEqual(kept.worn, R.DEFAULT_WORN);
  assert.deepEqual(kept.seen, ['a', 'b']);
  assert.equal(kept.bestRank, R.rankIndex(1234.5));
  // A round trip through storage changes nothing.
  const played = play({ ...fresh(), packs: 1 }, 'g', 'hard', 'win').profile;
  const opened = R.openPack(played, dice(3)).profile;
  assert.deepEqual(R.restore(JSON.parse(JSON.stringify(opened)), 5), opened);
});

test('a match that is only remembered changes nothing else', () => {
  const p = fresh();
  const s = R.skipMatch(p, 'old');
  assert.deepEqual({ ...s, seen: [] }, p);
  assert.equal(play(s, 'old', 'easy', 'win').profile, s);
  assert.equal(R.skipMatch(s, 'old'), s);
});

test('rating changes read well', () => {
  assert.equal(R.formatDelta(1000, 1020), '+20');
  assert.equal(R.formatDelta(1000, 980.4), '−20');
  assert.equal(R.formatDelta(1400, 1400.6), '+0.6');
  assert.equal(R.formatDelta(1000, 1000), '+0');
});

test('the catalogue is what the game promises', () => {
  const count = (kind) => R.COSMETICS.filter((c) => c.kind === kind).length;
  assert.deepEqual([count('back'), count('table'), count('title')], [12, 6, 13]);
  assert.equal(new Set(R.COSMETICS.map((c) => c.id)).size, R.COSMETICS.length);
  for (const id of Object.values(R.DEFAULT_WORN)) assert.equal(R.cosmetic(id).tier, undefined);
  // Every picture the catalogue and the ranks name is in the build.
  const art = new Set(readdirSync(join(here, '../src/progress/art')).map((f) => f.replace(/\.webp$/, '')));
  for (const c of R.FINDABLE) if (c.kind !== 'title') assert.ok(art.has(c.id), `no picture for ${c.id}`);
  for (const r of R.RANKS) assert.ok(art.has(`rank_${r.id}`), `no badge for ${r.id}`);
  assert.ok(art.has('pack_sealed'), 'no picture of the pack');
});

if (!process.exitCode) console.log(`progress rules: ${checks} checks passed`);
