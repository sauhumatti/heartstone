// Checks the Story Campaign data, starter deck generation, card rewards, deck editing,
// and progression rules (src/campaign/data.ts & rules.ts). Run with `npm run test:campaign`.
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

// Pull real catalog cards and builtin decks from Python engine.
const repoRoot = join(here, '../..');
const catalogJson = execFileSync(
  'python3',
  [
    '-c',
    'import json; from data.starter_decks import ALL_BUILTIN_DECKS; from engine.local import catalog; cat = catalog(); print(json.dumps({"decks": {d["id"]: d["hero_class"] for d in ALL_BUILTIN_DECKS}, "cards": cat["cards"], "heroes": list(cat["heroes"].keys())}))',
  ],
  { cwd: repoRoot, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 },
);
const catalog = JSON.parse(catalogJson);
const cards = catalog.cards;
const cardById = new Map(cards.map((c) => [c.id, c]));

test('5 chapters, 15 unique rivals, every deck & portrait card exists in catalog', () => {
  assert.equal(D.CAMPAIGN_CHAPTERS.length, 5);
  assert.equal(D.ALL_CAMPAIGN_RIVALS.length, 15);
  assert.equal(new Set(D.ALL_CAMPAIGN_RIVALS.map((r) => r.id)).size, 15);
  assert.equal(D.CAMPAIGN_PROLOGUE.length, 3);
  D.ALL_CAMPAIGN_RIVALS.forEach((r, i) => {
    assert.equal(r.order, i + 1);
    if (r.deckId !== 'humble_starter') {
      assert.ok(catalog.decks[r.deckId], `missing deck ${r.deckId} for ${r.id}`);
      assert.equal(catalog.decks[r.deckId], r.heroClass, `class mismatch on ${r.id}`);
    } else {
      const built = R.buildStarterDeck(r.heroClass, cards, r.starterVariant || 1);
      assert.equal(built.length, 30);
    }
    assert.ok(cardById.has(r.portraitCardId), `missing portrait card ${r.portraitCardId} for ${r.id}`);
    assert.ok(r.introQuote && r.midQuote && r.defeatQuote, `missing quotes for ${r.id}`);
  });
});

test('all 9 classes build valid 30-card Basic & Common starter decks', () => {
  for (const cls of catalog.heroes) {
    const st = R.startCampaignWithHero(R.emptyCampaignState(), cls, cards);
    assert.equal(st.phase, 'road');
    assert.equal(st.deck.length, 30, `starter deck size for ${cls}`);
    const check = R.validateCampaignDeck(st, st.deck, cards);
    assert.equal(check.ok, true, `invalid starter deck for ${cls}: ${check.error}`);
    for (const id of st.deck) {
      const c = cardById.get(id);
      assert.ok(c.rarity === 'FREE' || c.rarity === 'COMMON', `starter card ${c.name} should be Basic/Common`);
    }
  }
});

test('winning rivals grants card rewards, unlocks deck upgrades, and advances chapters', () => {
  let st = R.emptyCampaignState();
  assert.equal(st.phase, 'intro');
  st = R.advanceFromIntro(st);
  assert.equal(st.phase, 'choose_hero');
  st = R.startCampaignWithHero(st, 'MAGE', cards);

  // First loss grants 1 consolation pick to help refine deck
  st = R.attachCampaignMatch(st, 'g_loss', 'r1_bram');
  const lossOut = R.recordCampaignMatchResult(st, 'g_loss', 'loss', cards, 11);
  assert.ok(lossOut && !lossOut.won && lossOut.earnedRewards === 1);
  st = lossOut.state;
  assert.equal(st.phase, 'rewards');
  const consolationCard = st.pendingRewards[0].choices[0];
  st = R.pickRewardCard(st, consolationCard, cards);
  assert.equal(st.phase, 'road');
  assert.ok((st.collection[consolationCard] || 0) >= 1);

  // Swap newly earned card into the 30-card Campaign deck
  const edited = [consolationCard, ...st.deck.slice(1)];
  const check = R.validateCampaignDeck(st, edited, cards);
  assert.equal(check.ok, true, check.error);
  st = R.saveCampaignDeck(st, edited, cards);
  assert.equal(st.newCards.length, 0);
  assert.equal(st.deck[0], consolationCard);

  // Clear all 15 rivals through the full campaign
  for (let i = 0; i < D.ALL_CAMPAIGN_RIVALS.length; i++) {
    const rival = D.ALL_CAMPAIGN_RIVALS[i];
    assert.equal(R.currentRival(st).id, rival.id);
    st = R.attachCampaignMatch(st, `g_win_${i}`, rival.id);
    const out = R.recordCampaignMatchResult(st, `g_win_${i}`, 'win', cards, 100 + i);
    assert.ok(out && out.won && out.earnedRewards === 2);
    st = out.state;
    assert.equal(st.phase, 'rewards');
    if (rival.isChampion) {
      assert.equal(st.pendingRewards[1].tier, 'legendary');
      const legCard = cardById.get(st.pendingRewards[1].choices[0]);
      assert.equal(legCard.rarity, 'LEGENDARY');
    }
    while (st.pendingRewards.length > 0) {
      st = R.pickRewardCard(st, st.pendingRewards[0].choices[0], cards);
    }
    if (rival.isChampion) {
      assert.equal(st.phase, 'chapter_clear');
      const interlude = R.completeChapterInterlude(st);
      assert.ok(interlude && interlude.newlyClaimed);
      st = interlude.state;
    }
  }

  assert.equal(R.isCampaignComplete(st), true);
  assert.equal(st.phase, 'complete');
  assert.equal(st.claimedChapters.length, 5);
  assert.ok(Object.values(st.collection).reduce((a, b) => a + b, 0) >= 60);
});

test('restoreCampaignState drops stale v1 data and preserves valid v2 state', () => {
  const fromV1 = R.restoreCampaignState({ v: 1, clearedNormal: ['ch1_bouncer'] });
  assert.equal(fromV1.v, 2);
  assert.equal(fromV1.phase, 'intro');

  const started = R.startCampaignWithHero(R.emptyCampaignState(), 'ROGUE', cards);
  const restored = R.restoreCampaignState(JSON.parse(JSON.stringify(started)));
  assert.equal(restored.heroClass, 'ROGUE');
  assert.equal(restored.deck.length, 30);
  assert.equal(restored.phase, 'road');
});

if (!process.exitCode) console.log(`campaign rules: ${checks} checks passed`);
