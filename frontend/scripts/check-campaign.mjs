// Checks the Campaign data & progression rules (src/campaign/data.ts & rules.ts).
// Run with `npm run test:campaign`.
import { build } from 'esbuild';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const dir = mkdtempSync(join(tmpdir(), 'campaign-'));
const outData = join(dir, 'data.mjs');
const outRules = join(dir, 'rules.mjs');

await build({
  entryPoints: [join(here, '../src/campaign/data.ts')],
  outfile: outData,
  bundle: true,
  format: 'esm',
  platform: 'node',
  logLevel: 'silent',
});
await build({
  entryPoints: [join(here, '../src/campaign/rules.ts')],
  outfile: outRules,
  bundle: true,
  format: 'esm',
  platform: 'node',
  logLevel: 'silent',
});

const D = await import(pathToFileURL(outData).href);
const R = await import(pathToFileURL(outRules).href);

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

// Pull real catalog card IDs and builtin deck IDs from Python engine.
const repoRoot = join(here, '../..');
const catalogJson = execFileSync(
  'python3',
  [
    '-c',
    'import json; from data.starter_decks import ALL_BUILTIN_DECKS; from engine.catalog import COLLECTIBLE_CARDS; print(json.dumps({"decks": {d["id"]: d["hero_class"] for d in ALL_BUILTIN_DECKS}, "cards": list(COLLECTIBLE_CARDS.keys())}))',
  ],
  { cwd: repoRoot, encoding: 'utf8' },
);
const catalog = JSON.parse(catalogJson);
const cardSet = new Set(catalog.cards);

test('5 chapters, 15 unique bosses, every deck, signature card, counter deck & portrait exists in catalog', () => {
  assert.equal(D.CAMPAIGN_CHAPTERS.length, 5);
  assert.equal(D.ALL_CAMPAIGN_BOSSES.length, 15);
  assert.equal(new Set(D.ALL_CAMPAIGN_BOSSES.map((b) => b.id)).size, 15);
  D.ALL_CAMPAIGN_BOSSES.forEach((b, i) => {
    assert.equal(b.order, i + 1);
    assert.ok(catalog.decks[b.deckId], `missing deck ${b.deckId} for ${b.id}`);
    assert.ok(catalog.decks[b.recommendedDeckId], `missing recommended deck ${b.recommendedDeckId} for ${b.id}`);
    assert.equal(catalog.decks[b.deckId], b.heroClass, `class mismatch on ${b.id}`);
    assert.ok(cardSet.has(b.portraitCardId), `missing portrait card ${b.portraitCardId} for ${b.id}`);
    assert.equal(b.signatureCards.length, 3, `expected 3 signature cards for ${b.id}`);
    for (const sc of b.signatureCards) assert.ok(cardSet.has(sc), `missing signature card ${sc} for ${b.id}`);
    assert.ok(b.passiveId && b.passiveName && b.passiveText && b.heroicPassiveText, `missing passive for ${b.id}`);
    assert.ok(b.introQuote && b.midQuote && b.defeatQuote, `missing quotes for ${b.id}`);
    assert.ok(b.heroicHp > b.hp, `heroic HP should exceed normal HP for ${b.id}`);
  });
});

test('purist medal, best turn records, next boss chaining, and campaign reset', () => {
  let st = R.emptyCampaignState();
  st = R.attachCampaignMatch(st, 'g_purist', 'ch1_bouncer', 'normal', 'none', 'starter_mage');
  const out = R.recordCampaignMatchResult(st, 'g_purist', 'win', { turnNumber: 8, heroClass: 'MAGE' });
  assert.ok(out && out.won && out.puristEarned);
  assert.equal(out.nextBoss?.id, 'ch1_hearthwitch');
  assert.equal(out.state.bossRecords.ch1_bouncer.bestTurns, 8);
  assert.equal(out.state.bossRecords.ch1_bouncer.bestClass, 'MAGE');
  assert.equal(R.isBossPurist(out.state, 'ch1_bouncer'), true);
  const reset = R.resetCampaignState({ ...out.state, selectedDeckId: 'starter_mage' });
  assert.equal(reset.clearedNormal.length, 0);
  assert.equal(reset.clearedPurist.length, 0);
  assert.equal(reset.selectedDeckId, 'starter_mage');
});

test('linear boss unlocking, idempotent match results, chapter rewards & relics', () => {
  let st = R.emptyCampaignState();
  assert.equal(R.isBossUnlocked(st, 'ch1_bouncer'), true);
  assert.equal(R.isBossUnlocked(st, 'ch1_hearthwitch'), false);
  assert.equal(R.isRelicUnlocked(st, 'none'), true);
  assert.equal(R.isRelicUnlocked(st, 'tinderbox'), false);

  // Loss increments attempt but does not unlock next boss.
  st = R.attachCampaignMatch(st, 'g_loss', 'ch1_bouncer', 'normal', 'none');
  const lost = R.recordCampaignMatchResult(st, 'g_loss', 'loss');
  assert.ok(lost && !lost.won);
  st = lost.state;
  assert.equal(st.attempts.ch1_bouncer, 1);
  assert.equal(R.isBossUnlocked(st, 'ch1_hearthwitch'), false);

  // Clear all 3 bosses of Chapter I.
  for (const [idx, bid] of ['ch1_bouncer', 'ch1_hearthwitch', 'ch1_blackwick'].entries()) {
    st = R.attachCampaignMatch(st, `g_ch1_${idx}`, bid, 'normal', 'none');
    const out = R.recordCampaignMatchResult(st, `g_ch1_${idx}`, 'win');
    assert.ok(out && out.won && out.newlyCleared);
    if (idx === 2) assert.equal(out.chapterJustCompleted?.id, 'ch1');
    st = out.state;
    // Duplicate recording is ignored.
    assert.equal(R.recordCampaignMatchResult(st, `g_ch1_${idx}`, 'win'), null);
  }

  assert.equal(R.isChapterCleared(st, 'ch1', 'normal'), true);
  assert.equal(R.isHeroicUnlockedForChapter(st, 'ch1'), true);
  assert.equal(R.isBossUnlocked(st, 'ch2_sprocket'), true);
  assert.equal(R.isRelicUnlocked(st, 'tinderbox'), true);
  assert.equal(R.canClaimChapter(st, 'ch1'), true);

  const claimed = R.claimChapterReward(st, 'ch1');
  assert.ok(claimed);
  assert.equal(claimed.reward.packs, 1);
  assert.equal(claimed.reward.relicId, 'tinderbox');
  assert.equal(claimed.state.equippedRelic, 'tinderbox');
  assert.equal(R.claimChapterReward(claimed.state, 'ch1'), null);
});

test('full normal + heroic completion unlocks Crown and Heroic grand reward', () => {
  let st = R.emptyCampaignState();
  for (const b of D.ALL_CAMPAIGN_BOSSES) {
    st = R.attachCampaignMatch(st, `n_${b.id}`, b.id, 'normal', 'none');
    const out = R.recordCampaignMatchResult(st, `n_${b.id}`, 'win');
    assert.ok(out);
    if (b.id === 'ch5_eclipse') assert.equal(out.campaignJustCompleted, true);
    st = out.state;
  }
  assert.equal(R.isCampaignComplete(st, 'normal'), true);
  assert.equal(R.isRelicUnlocked(st, 'crown'), true);
  assert.equal(R.canClaimHeroicGrand(st), false);

  for (const b of D.ALL_CAMPAIGN_BOSSES) {
    st = R.attachCampaignMatch(st, `h_${b.id}`, b.id, 'heroic', 'crown');
    const out = R.recordCampaignMatchResult(st, `h_${b.id}`, 'win');
    assert.ok(out && out.won);
    st = out.state;
  }
  assert.equal(R.isCampaignComplete(st, 'heroic'), true);
  assert.equal(R.canClaimHeroicGrand(st), true);
  const grand = R.claimHeroicGrandReward(st);
  assert.ok(grand && grand.reward.packs === 3 && grand.reward.embers === 250);
  assert.equal(R.canClaimHeroicGrand(grand.state), false);
});

test('restoreCampaignState safely sanitizes corrupt data and locked relics', () => {
  const safe = R.restoreCampaignState({
    clearedNormal: ['ch1_bouncer', 'not_a_boss'],
    equippedRelic: 'crown',
    difficulty: 'bogus',
  });
  assert.deepEqual(safe.clearedNormal, ['ch1_bouncer']);
  assert.equal(safe.equippedRelic, 'none');
  assert.equal(safe.difficulty, 'normal');
});

if (!process.exitCode) console.log(`campaign rules: ${checks} checks passed`);
