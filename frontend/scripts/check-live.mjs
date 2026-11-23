// Checks moves made while animations play (src/game/live.ts): run with `npm run test:live`.
// No browser and no engine are needed.
import { build } from 'esbuild';
import assert from 'node:assert/strict';
import { mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const out = join(mkdtempSync(join(tmpdir(), 'live-')), 'live.mjs');
await build({ entryPoints: [join(here, '../src/game/live.ts')], outfile: out, bundle: true, format: 'esm', platform: 'node', logLevel: 'silent' });
const L = await import(pathToFileURL(out).href);

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

const card = (uid, over = {}) => ({
  uid, index: 0, can_play: false, unplayable_reason: 'Not enough mana.', target_rule: 'NONE', target_required: false,
  valid_targets: [], choose_options: [], combo_glow: false, ...over,
});
const minion = (uid, over = {}) => ({ uid, can_attack: false, legal_attack_targets: [], ...over });
const state = (seq, me, over = {}) => ({
  seq, phase: 'PLAY', your_turn: true, pending_choice: null,
  me: { hand: [], board: [], ...me, hero: { id: 'hero_p1', can_attack: false, legal_attack_targets: [], hero_power: { id: 'hp', used: false, can_use: true }, ...(me.hero || {}) } },
  ...over,
});

test('the same state is left as it is', () => {
  const s = state(5, { hand: [card('a')] });
  assert.equal(L.withLiveRules(s, s), s);
  assert.equal(L.withLiveRules(s, state(5, {})), s);
});

test('what may be done comes from the newest state, what is shown stays', () => {
  const shown = state(5, { hand: [card('a', { cost: 2 }), card('b')], board: [minion('m1'), minion('m2', { attack: 3 })] });
  const now = state(7, {
    hand: [card('b', { can_play: true, unplayable_reason: '', valid_targets: ['m9'] })],
    board: [minion('m2', { can_attack: true, legal_attack_targets: ['hero_p2'], attack: 9 })],
    hero: { hero_power: { id: 'hp', used: true, can_use: false } },
  });
  const v = L.withLiveRules(shown, now);
  assert.equal(v.seq, 5);
  assert.deepEqual(v.me.hand.map((c) => [c.uid, c.can_play]), [['a', false], ['b', true]]);
  assert.equal(v.me.hand[0].cost, 2, 'a card already played still shows until the show plays it');
  assert.deepEqual(v.me.hand[1].valid_targets, ['m9']);
  assert.deepEqual(v.me.board.map((m) => [m.uid, m.can_attack]), [['m1', false], ['m2', true]]);
  assert.equal(v.me.board[1].attack, 3, 'stats are the shown ones');
  assert.equal(v.me.hero.hero_power.used, true);
  assert.equal(v.me.hero.hero_power.can_use, false);
});

test('a new hero power cannot be used from the old one', () => {
  const v = L.withLiveRules(state(1, {}), state(2, { hero: { hero_power: { id: 'other', used: false, can_use: true } } }));
  assert.equal(v.me.hero.hero_power.can_use, false);
});

test('moves wait for a choice and for the turn', () => {
  assert.equal(L.movable(state(1, {})), true);
  assert.equal(L.movable(state(1, {}, { pending_choice: { options: [] } })), false);
  assert.equal(L.movable(state(1, {}, { your_turn: false })), false);
  assert.equal(L.movable(state(1, {}, { phase: 'GAME_OVER' })), false);
});

test('a place in the row is kept beside the same neighbours', () => {
  const row = (...u) => u.map((uid) => ({ uid }));
  assert.equal(L.placeIn(undefined, ['a'], row('a')), 0);
  // put at the end: the end, even after other minions joined
  assert.equal(L.placeIn(1, ['a'], row('a', 'x')), 2);
  // right of a, which is still there
  assert.equal(L.placeIn(1, ['a', 'b'], row('x', 'a', 'b')), 2);
  // a died: left of b
  assert.equal(L.placeIn(1, ['a', 'b'], row('b')), 0);
  // all neighbours gone
  assert.equal(L.placeIn(1, ['a', 'b'], row('x', 'y')), 0);
  assert.equal(L.placeIn(0, ['a'], row('x', 'a')), 1);
});

if (!process.exitCode) console.log(`moves while animating: ${checks} checks passed`);
