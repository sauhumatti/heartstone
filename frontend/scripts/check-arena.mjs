// Checks the Arena draft, run progression, key & reward rules (src/arena/rules.ts).
import { build } from 'esbuild';
import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const dir = mkdtempSync(join(tmpdir(), 'arena-'));
const arenaOut = join(dir, 'arena.mjs');
const progOut = join(dir, 'progress.mjs');
await build({ entryPoints: [join(here, '../src/arena/rules.ts')], outfile: arenaOut, bundle: true, format: 'esm', platform: 'node', logLevel: 'silent' });
await build({ entryPoints: [join(here, '../src/progress/rules.ts')], outfile: progOut, bundle: true, format: 'esm', platform: 'node', logLevel: 'silent' });
const A = await import(pathToFileURL(arenaOut).href);
const P = await import(pathToFileURL(progOut).href);

const rawCards = JSON.parse(readFileSync(join(here, '../../data/cards.json'), 'utf8'));
const cards = Object.values(rawCards).filter((c) => c.collectible);
const heroes = ['DRUID', 'HUNTER', 'MAGE', 'PALADIN', 'PRIEST', 'ROGUE', 'SHAMAN', 'WARLOCK', 'WARRIOR'];

const dice = (seed) => () => {
  seed = (seed * 1664525 + 1013904223) >>> 0;
  return seed / 4294967296;
};

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

test('drafts 30 cards with guaranteed rare+ milestones and excludes quests', () => {
  const rng = dice(11);
  let run = A.startNewRun(heroes, 'wild', 1000, rng);
  assert.equal(run.phase, 'picking_hero');
  assert.equal(run.heroChoices.length, 3);
  assert.equal(new Set(run.heroChoices).size, 3);

  run = A.chooseRunHero(run, run.heroChoices[0], cards, rng);
  assert.equal(run.phase, 'drafting');
  const byId = new Map(cards.map((c) => [c.id, c]));

  for (let i = 1; i <= 30; i++) {
    assert.equal(run.currentChoices.length, 3);
    assert.equal(new Set(run.currentChoices).size, 3);
    for (const cid of run.currentChoices) {
      const c = byId.get(cid);
      assert.ok(c);
      assert.ok(A.cardAllowedForClass(c, run.heroClass));
      assert.ok(!c.mechanics.includes('QUEST') && !c.mechanics.includes('TRIAL'));
      if (A.GUARANTEED_RARE_PICKS.has(i)) {
        assert.ok(['RARE', 'EPIC', 'LEGENDARY'].includes(c.rarity), `pick ${i} got ${c.rarity}`);
      }
    }
    run = A.pickDraftCard(run, run.currentChoices[0], cards, rng);
  }
  assert.equal(run.phase, 'playing');
  assert.equal(run.deck.length, 30);
});

test('run ends at 12 wins or 3 losses, draws do not count, results are idempotent', () => {
  const rng = dice(22);
  let run = A.startNewRun(heroes, 'ungoro', 1000, rng);
  run = A.chooseRunHero(run, run.heroChoices[0], cards, rng);
  for (let i = 0; i < 30; i++) run = A.pickDraftCard(run, run.currentChoices[0], cards, rng);

  // Draw keeps 0-0
  run = A.attachArenaMatch(run, 'g_draw', 'MAGE', 'Arena Mage');
  run = A.recordArenaMatchResult(run, 'g_draw', 'draw');
  assert.deepEqual([run.wins, run.losses, run.phase], [0, 0, 'playing']);

  // Duplicate gameId is ignored
  run = A.recordArenaMatchResult(run, 'g_draw', 'loss');
  assert.deepEqual([run.wins, run.losses], [0, 0]);

  // 12 wins completes run with Lightforge Key
  for (let w = 1; w <= 12; w++) {
    run = A.attachArenaMatch(run, `g_w${w}`, 'WARRIOR', 'Arena Warrior');
    run = A.recordArenaMatchResult(run, `g_w${w}`, 'win');
  }
  assert.deepEqual([run.wins, run.losses, run.phase], [12, 0, 'complete']);
  assert.equal(A.arenaKeyFor(run.wins).name, 'Lightforge Key');

  // Claiming rewards updates stats and profile packs/embers once
  const st0 = { ...A.emptyArenaState(), run };
  const claimed = A.claimRunRewards(st0);
  assert.ok(claimed);
  assert.equal(claimed.key.packs, 3);
  assert.equal(claimed.key.embers, 150);
  assert.equal(claimed.state.stats.bestWins, 12);
  assert.equal(claimed.state.stats.twelveWinRuns, 1);
  assert.equal(A.claimRunRewards(claimed.state), null);

  const prof = P.grantArenaReward(P.newProfile(1000), claimed.key.packs, claimed.key.embers);
  assert.deepEqual([prof.packs, prof.embers], [3, 150]);
});

test('3 losses completes run and opponent drafter produces valid 30-card decks', () => {
  const rng = dice(33);
  let run = A.startNewRun(heroes, 'classic', 1000, rng);
  run = A.chooseRunHero(run, run.heroChoices[0], cards, rng);
  for (let i = 0; i < 30; i++) run = A.pickDraftCard(run, run.currentChoices[0], cards, rng);
  for (let l = 1; l <= 3; l++) {
    run = A.attachArenaMatch(run, `g_l${l}`, 'PRIEST', 'Arena Priest');
    run = A.recordArenaMatchResult(run, `g_l${l}`, 'loss');
  }
  assert.equal(run.phase, 'complete');
  assert.equal(run.losses, 3);

  const opp = A.draftOpponentDeck(cards, heroes, 'wild', 8, rng);
  assert.equal(opp.cards.length, 30);
  assert.ok(heroes.includes(opp.heroClass));
  assert.equal(A.levelForArenaWins(1, 'auto'), 'easy');
  assert.equal(A.levelForArenaWins(4, 'auto'), 'normal');
  assert.equal(A.levelForArenaWins(9, 'auto'), 'hard');
});

console.log(`arena rules: ${checks} checks passed`);
