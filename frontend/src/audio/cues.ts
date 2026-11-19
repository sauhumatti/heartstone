// What each moment of the game sounds like: every cue is a small arrangement
// of sounds from the bank (made in code) and recorded clips (creature voices,
// the heavier combat and magic effects). A clip that is not on the device yet
// is replaced by its code-made stand-in. `pan` places a cue left to right
// where it happens on the table, `amount` scales it (damage dealt, the size of
// what landed).
import { CHIME_HZ, GLOW_HZ, hz } from './bank';
import type { Engine } from './engine';

export interface CueOpts {
  /** -1 (left) .. 1 (right). */
  pan?: number;
  /** Where a travelling sound ends up. */
  to?: number;
  /** Damage, or the size of a piece (attack + health). */
  amount?: number;
  /** A legendary piece: it gets a flourish. */
  rare?: boolean;
  /** For turn cues: is it the player's own turn? */
  mine?: boolean;
  /** For creature voices: which kind of creature (see creatures.ts). */
  kind?: string;
  /** Seconds to wait before it sounds. */
  at?: number;
}

type Cue = (e: Engine, o: CueOpts, t: number) => void;

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));
const bell = (midi: number) => hz(midi) / CHIME_HZ;
const voice = (midi: number) => hz(midi) / GLOW_HZ;

export const CUES = {
  // ---- interface ----
  uiClick: (e, _o, t) => e.play('tick', { gain: 0.3, room: 0.04 }, t),
  cardHover: (e, _o, t) => e.play('flick', { gain: 0.06, rate: 1.25, room: 0 }, t),
  error: (e, _o, t) => {
    e.play('knock', { gain: 0.32, rate: 0.72, room: 0.08 }, t);
    e.play('knock', { gain: 0.26, rate: 0.64, room: 0.08, at: 0.11 }, t);
  },

  // ---- cards ----
  draw: (e, o, t) => {
    e.play('swish', { gain: 0.36, pan: o.pan, panTo: (o.pan ?? 0) * 0.3 }, t);
    e.play('flick', { gain: 0.26, pan: (o.pan ?? 0) * 0.3, at: 0.1 }, t);
  },
  cardAdded: (e, o, t) => {
    e.play('flick', { gain: 0.26, pan: o.pan }, t);
    e.play('chime', { gain: 0.1, rate: bell(88), room: 0.6, pan: o.pan }, t);
  },
  cardPlay: (e, o, t) => e.play('swish', { gain: 0.42, rate: 0.84, pan: o.pan, panTo: o.to }, t),
  spellCast: (e, o, t) => {
    if (!e.clip('magicCast', { gain: 0.4, pan: o.pan, room: 0.3 }, t)) {
      e.play('whoosh', { gain: 0.3, rate: 1.18, pan: o.pan }, t);
      e.play('glow', { gain: 0.09, rate: voice(76), pan: o.pan, room: 0.4 }, t);
    }
    e.play('chime', { gain: 0.17, rate: bell([81, 84, 86, 88][Math.floor((o.amount ?? 0) % 4)]), room: 0.65, pan: o.pan, at: 0.07 }, t);
  },
  shuffle: (e, _o, t) => {
    // a riffle: the cards fall faster and faster, never evenly, then the deck is squared on the table
    let at = 0;
    for (let i = 0; i < 11; i++) {
      e.play(i % 3 === 2 ? 'swish' : 'flick', { gain: 0.12 + ((i * 7) % 5) * 0.025, rate: 0.85 + i * 0.03, pan: -0.25 + i * 0.05, at, room: 0.12 }, t);
      at += 0.06 - i * 0.003 + ((i * 13) % 7) * 0.003;
    }
    e.play('slap', { gain: 0.42, at: at + 0.05 }, t);
    e.play('knock', { gain: 0.16, rate: 1.1, at: at + 0.06 }, t);
  },
  burn: (e, o, t) => {
    if (!e.clip('fireBurst', { gain: 0.46, pan: o.pan }, t)) e.play('ember', { gain: 0.6, pan: o.pan }, t);
  },
  discard: (e, o, t) => {
    e.play('swish', { gain: 0.32, rate: 0.72, pan: o.pan }, t);
    if (!e.clip('fireBurst', { gain: 0.26, rate: 1.1, pan: o.pan, at: 0.05 }, t)) e.play('ember', { gain: 0.28, pan: o.pan, at: 0.05 }, t);
  },
  bounce: (e, o, t) => {
    e.play('swish', { gain: 0.38, rate: 1.3, pan: o.pan, panTo: o.to }, t);
    e.play('flick', { gain: 0.2, pan: o.to ?? o.pan, at: 0.13 }, t);
  },

  // ---- pieces arriving and leaving ----
  land: (e, o, t) => {
    const size = clamp((o.amount ?? 4) / 14, 0, 1);
    e.play('thud', { gain: 0.42 + 0.4 * size, rate: 1.22 - 0.36 * size, pan: o.pan }, t);
    e.play('slap', { gain: 0.4, pan: o.pan, at: 0.004 }, t);
    if (size > 0.55) e.play('drum', { gain: 0.3 * size, rate: 0.9, pan: o.pan, at: 0.01 }, t);
    if (o.rare) {
      [74, 78, 81].forEach((n, i) => e.play('chime', { gain: 0.15, rate: bell(n), room: 0.75, pan: o.pan, at: 0.09 + i * 0.07, exact: true }, t));
      e.duckMusic(0.55, 0.9, t);
    }
  },
  death: (e, o, t) => e.play('fall', { gain: 0.5, pan: o.pan }, t),
  destroy: (e, o, t) => {
    if (e.clip('destroyFx', { gain: 0.44, pan: o.pan }, t)) return;
    e.play('whoosh', { gain: 0.28, rate: 0.62, pan: o.pan }, t);
    e.play('knock', { gain: 0.28, rate: 0.6, pan: o.pan, at: 0.12 }, t);
  },
  transform: (e, o, t) => {
    if (!e.clip('transformFx', { gain: 0.42, pan: o.pan }, t)) {
      e.play('whoosh', { gain: 0.3, rate: 1.5, pan: o.pan }, t);
      e.play('glass', { gain: 0.16, rate: 1.2, pan: o.pan, at: 0.1 }, t);
    }
    e.play('chime', { gain: 0.12, rate: bell(85), room: 0.6, pan: o.pan, at: 0.14 }, t);
  },
  steal: (e, o, t) => {
    if (!e.clip('stealFx', { gain: 0.4, pan: o.pan, panTo: o.to, room: 0.4 }, t)) e.play('swell', { gain: 0.3, pan: o.pan, panTo: o.to }, t);
    e.play('swish', { gain: 0.24, rate: 0.8, pan: o.to ?? o.pan, at: 0.5 }, t);
  },

  // ---- creature voices: recorded clips, one set for each kind of creature ----
  creatureEnter: (e, o, t) => {
    if (!o.kind) return;
    const size = clamp((o.amount ?? 4) / 14, 0, 1);
    // just after the piece lands, so the voice is not buried under the thud
    e.clip(`${o.kind}-enter`, { gain: 0.3 + 0.22 * size, rate: 1.07 - 0.14 * size, pan: o.pan, room: 0.24, at: (o.at ?? 0) + 0.09 }, t);
  },
  creatureAttack: (e, o, t) => {
    if (!o.kind) return;
    const size = clamp((o.amount ?? 4) / 14, 0, 1);
    e.clip(`${o.kind}-attack`, { gain: 0.32 + 0.16 * size, rate: 1.07 - 0.14 * size, pan: o.pan, panTo: o.to, at: o.at }, t);
  },
  creatureDeath: (e, o, t) => {
    if (!o.kind) return;
    const size = clamp((o.amount ?? 4) / 14, 0, 1);
    e.clip(`${o.kind}-death`, { gain: 0.34 + 0.16 * size, rate: 1.07 - 0.14 * size, pan: o.pan, room: 0.3, at: (o.at ?? 0) + 0.03 }, t);
  },

  // ---- blows ----
  attack: (e, o, t) => {
    const a = clamp(o.amount ?? 2, 0, 9);
    e.play('blade', { gain: 0.3 + a * 0.012, pan: o.pan }, t);
    e.play('hit', { gain: 0.46 + a * 0.045, rate: 1.1 - a * 0.03, pan: o.pan, at: 0.006 }, t);
    if (a >= 6) {
      e.play('drum', { gain: 0.45, rate: 0.84, pan: o.pan }, t);
      e.duckMusic(0.5, 0.5, t);
    }
  },
  projectile: (e, o, t) => e.play('whoosh', { gain: 0.3, rate: 1.36, pan: o.pan, panTo: o.to }, t),
  hit: (e, o, t) => {
    const a = clamp(o.amount ?? 1, 0, 10);
    e.play('hit', { gain: 0.42 + a * 0.048, rate: 1.14 - a * 0.03, pan: o.pan }, t);
    if (a >= 5 && !e.clip('heavyImpact', { gain: 0.3 + (a - 5) * 0.045, pan: o.pan }, t)) e.play('thud', { gain: 0.26, rate: 0.95, pan: o.pan }, t);
    if (a >= 8) {
      e.play('drum', { gain: 0.3, rate: 0.86, pan: o.pan }, t);
      e.duckMusic(0.45, 0.6, t);
    }
  },
  shield: (e, o, t) => {
    if (!e.clip('shieldBreak', { gain: 0.46, pan: o.pan }, t)) e.play('glass', { gain: 0.46, pan: o.pan }, t);
    e.play('chime', { gain: 0.1, rate: bell(96), room: 0.5, pan: o.pan }, t);
  },
  immune: (e, o, t) => {
    e.play('chime', { gain: 0.15, rate: bell(98), room: 0.4, pan: o.pan }, t);
    e.play('tick', { gain: 0.2, pan: o.pan }, t);
  },
  weaponEquip: (e, o, t) => {
    if (!e.clip('weaponDraw', { gain: 0.42, pan: o.pan }, t)) e.play('blade', { gain: 0.34, rate: 0.78, pan: o.pan }, t);
    e.play('slap', { gain: 0.3, pan: o.pan }, t);
  },
  weaponBreak: (e, o, t) => {
    if (e.clip('weaponSnap', { gain: 0.42, pan: o.pan }, t)) return;
    e.play('blade', { gain: 0.28, rate: 1.24, pan: o.pan }, t);
    e.play('glass', { gain: 0.22, rate: 0.82, pan: o.pan, at: 0.03 }, t);
  },

  // ---- changes of state ----
  heal: (e, o, t) => {
    if (!e.clip('healing', { gain: 0.4, pan: o.pan, room: 0.4 }, t)) {
      e.play('glow', { gain: 0.2, rate: voice(69), pan: o.pan, room: 0.4 }, t);
      e.play('glow', { gain: 0.17, rate: voice(76), pan: o.pan, room: 0.4, at: 0.14 }, t);
    }
    e.play('chime', { gain: 0.09, rate: bell(88), room: 0.7, pan: o.pan, at: 0.27 }, t);
  },
  buff: (e, o, t) => {
    [88, 92, 95].forEach((n, i) => e.play('chime', { gain: 0.2, rate: bell(n), room: 0.6, pan: o.pan, at: i * 0.07, exact: true }, t));
  },
  debuff: (e, o, t) => {
    e.play('glow', { gain: 0.14, rate: voice(65), pan: o.pan }, t);
    e.play('glow', { gain: 0.14, rate: voice(62), pan: o.pan, at: 0.13 }, t);
  },
  freeze: (e, o, t) => {
    if (!e.clip('iceFreeze', { gain: 0.46, pan: o.pan }, t)) e.play('frost', { gain: 0.46, pan: o.pan }, t);
  },
  silence: (e, o, t) => {
    if (e.clip('silenceFx', { gain: 0.4, pan: o.pan }, t)) return;
    e.play('whoosh', { gain: 0.24, rate: 0.7, pan: o.pan }, t);
    e.play('glow', { gain: 0.12, rate: voice(64), pan: o.pan, at: 0.03 }, t);
  },
  heroPower: (e, o, t) => {
    if (!e.clip('powerBurst', { gain: 0.42, pan: o.pan }, t)) {
      e.play('whoosh', { gain: 0.28, rate: 0.96, pan: o.pan }, t);
      e.play('glow', { gain: 0.13, rate: voice(73), pan: o.pan, room: 0.4 }, t);
    }
    e.play('knock', { gain: 0.24, rate: 0.9, pan: o.pan, at: 0.02 }, t);
  },

  // ---- secrets ----
  secret: (e, o, t) => {
    if (e.clip('secretSet', { gain: 0.4, pan: o.pan, room: 0.45 }, t)) return;
    e.play('swell', { gain: 0.28, pan: o.pan, room: 0.5 }, t);
    e.play('knock', { gain: 0.22, rate: 1.3, pan: o.pan, at: 0.6 }, t);
  },
  secretReveal: (e, o, t) => {
    if (!e.clip('trapSpring', { gain: 0.44, pan: o.pan }, t)) e.play('knock', { gain: 0.3, pan: o.pan }, t);
    e.play('chime', { gain: 0.28, rate: bell(76), room: 0.8, pan: o.pan, exact: true }, t);
    e.play('chime', { gain: 0.2, rate: bell(83), room: 0.8, pan: o.pan, at: 0.12, exact: true }, t);
    e.duckMusic(0.55, 0.8, t);
  },
  counter: (e, o, t) => {
    if (e.clip('fizzle', { gain: 0.44, pan: o.pan }, t)) return;
    e.play('glass', { gain: 0.3, rate: 0.72, pan: o.pan }, t);
    e.play('knock', { gain: 0.3, rate: 0.66, pan: o.pan, at: 0.05 }, t);
  },

  // ---- the turn ----
  turnStart: (e, o, t) => {
    if (o.mine) {
      e.play('drum', { gain: 0.3 }, t);
      e.play('chime', { gain: 0.28, rate: bell(74), room: 0.75, exact: true }, t);
      e.play('chime', { gain: 0.24, rate: bell(81), room: 0.75, at: 0.17, exact: true }, t);
    } else {
      e.play('drum', { gain: 0.24, rate: 0.9 }, t);
      e.play('knock', { gain: 0.2, rate: 0.8, at: 0.01 }, t);
      e.play('chime', { gain: 0.09, rate: bell(74), room: 0.75, exact: true }, t);
    }
  },
  turnEnd: (e, _o, t) => e.play('knock', { gain: 0.28, rate: 0.9, pan: 0.6 }, t),
  fatigue: (e, o, t) => {
    e.play('drum', { gain: 0.5, rate: 0.74, pan: o.pan }, t);
    if (!e.clip('fatigueFx', { gain: 0.4, pan: o.pan, at: 0.02 }, t)) e.play('fall', { gain: 0.28, rate: 0.7, pan: o.pan, at: 0.04 }, t);
  },

  // ---- the end ----
  victory: (e, _o, t) => {
    e.duckMusic(0.15, 3.5, t);
    e.play('drum', { gain: 0.5 }, t);
    // a rising spread of the home chord turned major, then the bell on top: an arrival, not a jingle
    [50, 57, 62, 66, 69, 74].forEach((n, i) => e.pluck(n, { gain: 0.34 - i * 0.02, at: i * 0.14, pan: -0.3 + i * 0.12, room: 0.6 }, t, true));
    [62, 66, 69].forEach((n) => e.play('glow', { gain: 0.12, rate: voice(n), room: 0.6, at: 0.86, exact: true }, t));
    e.play('drum', { gain: 0.4, rate: 0.9, at: 0.86 }, t);
    [81, 86].forEach((n, i) => e.play('chime', { gain: 0.2, rate: bell(n), room: 0.85, at: 0.9 + i * 0.22, exact: true }, t));
  },
  defeat: (e, _o, t) => {
    e.duckMusic(0.15, 3.5, t);
    e.play('drum', { gain: 0.5, rate: 0.76 }, t);
    [74, 72, 69, 65, 62].forEach((n, i) => e.pluck(n, { gain: 0.3, at: i * 0.21, room: 0.5 }, t, true));
    [62, 69, 65].forEach((n) => e.play('glow', { gain: 0.11, rate: voice(n), room: 0.6, at: 0.95, exact: true }, t));
    e.play('drum', { gain: 0.4, rate: 0.7, at: 1.05 }, t);
    e.play('fall', { gain: 0.25, rate: 0.7, at: 1.1 }, t);
  },
} satisfies Record<string, Cue>;

export type CueName = keyof typeof CUES;

/** Raw sounds worth building before they are first needed. */
export const WARM_FIRST = ['tick', 'flick', 'swish', 'slap', 'thud', 'hit', 'knock', 'chime', 'drum', 'whoosh', 'blade', 'glow', 'fall'];
