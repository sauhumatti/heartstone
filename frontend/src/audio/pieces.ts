// The game's music: four short pieces, written out. Two play in the menus (the inn), two
// during a match. Each piece is sections of chords with a tune, played several times in a
// row with a different arrangement each time; the accompanying parts are written as
// patterns over the chords. Instruments are recorded ones (see music.ts and
// scripts/make_music_samples.py).
import { at, barChords, type Chord, dice, type Ev, harmonyBelow, tonesIn, tune, voiceLead } from './score';

/** The percussion, as notes of one kit (music.ts maps them to recordings). */
export const KIT = {
  frame: 36,
  frame2: 37,
  frameMute: 38,
  frameMute2: 39,
  frameHand: 40,
  tamb: 41,
  tambShake: 42,
  tambRoll: 43,
  bdrum: 44,
  timp: 45,
  timpLow: 46,
} as const;

type Put = (inst: string, midi: number, at: number, len: number, vel: number) => void;
interface Where {
  /** Bar within the section, from 0. */
  bar: number;
  bars: number;
  rnd: () => number;
}
type Part = (c: Chord, at: number, len: number, put: Put, where: Where) => void;

interface Section {
  chords: string[];
  tune?: string;
}

interface Pass {
  s: string;
  lead?: string;
  harmony?: string;
  /** Octaves to move the tune by (the horn plays it an octave down). */
  octave?: number;
  parts: string[];
  /** Overall loudness of the pass, 1 = full. */
  dyn?: number;
}

export interface Piece {
  id: string;
  title: string;
  scene: 'menu' | 'match';
  /** Seconds per unit (an eighth note in all four pieces). */
  unit: number;
  /** Units per bar. */
  bar: number;
  sections: Record<string, Section>;
  form: Pass[];
  /** The accompanying parts; made fresh for every playing, as some remember the last chord. */
  parts: () => Record<string, Part>;
}

/** How each instrument's notes are held: bowed and blown notes run on a little, plucks ring. */
const LEGATO: Record<string, number> = { violin: 1.04, flute: 1.02, recorder: 0.97, horn: 1.05, vlnEns: 1.08, celloEns: 1.08 };
/** Wind and bowed parts land a little behind the beat, as players do; plucks are tighter. */
const LOOSE: Record<string, number> = { violin: 0.012, flute: 0.01, recorder: 0.008, horn: 0.015, vlnEns: 0.02, celloEns: 0.02 };

// ---------------------------------------------------------------------------
// Parts shared by more than one piece
// ---------------------------------------------------------------------------

function strings(lo: number, hi: number, vel: number, inst = 'vlnEns'): Part {
  let prev: number[] | null = null;
  return (c, a, len, put) => {
    const v = voiceLead(c, prev, lo, hi, 3);
    prev = v;
    v.forEach((n, i) => put(inst, n, a, len, vel - i * 0.03));
  };
}

const celloRoot = (vel: number): Part => (c, a, len, put) => put('celloEns', at(c.bass, 36), a, len, vel);

const hornPad: Part = (c, a, len, put) => {
  const r = at(c.root, 45);
  put('horn', r, a, len, 0.42);
  if (r + 7 <= 64) put('horn', r + 7, a + 0.05, len, 0.34);
};

const harpEnd: Part = (c, a, _len, put) => {
  put('harp', at(c.bass, 38), a, 8, 0.75);
  tonesIn(c, 55, 76).slice(0, 6).forEach((n, i) => put('harp', n, a + 0.12 * (i + 1), 8, 0.5));
};

const celloEnd: Part = (c, a, _len, put) => put('celloEns', at(c.bass, 36), a, 10, 0.4);

// ---------------------------------------------------------------------------
// 1. The Lantern Inn: a jig in D, 6/8
// ---------------------------------------------------------------------------

const lanternInn: Piece = {
  id: 'lantern-inn',
  title: 'The Lantern Inn',
  scene: 'menu',
  unit: 60 / 96 / 3,
  bar: 6,
  sections: {
    intro: { chords: ['D', 'D', 'G', 'A'] },
    A: {
      chords: ['D', 'G', 'D', 'A', 'D', 'G', 'A7', 'D'],
      tune:
        'A4:1 D5:1 E5:1 F#5:2> D5:1 | G5:1 F#5:1 E5:1 D5:2 B4:1 | A4:1 D5:1 F#5:1 A5:2> F#5:1 | E5:2 C#5:1 A4:3 |' +
        'A4:1 D5:1 E5:1 F#5:2> A5:1 | B5:2 A5:1 G5:2 E5:1 | E5:1 G5:1 E5:1 C#5:2 E5:1 | D5:5 r:1',
    },
    B: {
      chords: ['G', 'D', 'G', 'A', 'Bm', 'G', 'A7', 'D'],
      tune:
        'B5:2> G5:1 D5:2 G5:1 | A5:2> F#5:1 D5:2 F#5:1 | G5:1 A5:1 B5:1 A5:2 G5:1 | F#5:1 E5:1 D5:1 C#5:2 A4:1 |' +
        'B4:1 D5:1 F#5:1 B5:2> A5:1 | G5:1 F#5:1 E5:1 D5:2 B4:1 | A4:1 C#5:1 E5:1 A5:2> G5:1 | F#5:2 E5:1 D5:3',
    },
    turn: { chords: ['Bm', 'G', 'Em', 'A'] },
    end: { chords: ['D', 'D'] },
  },
  form: [
    { s: 'intro', parts: ['harp', 'pizz'], dyn: 0.75 },
    { s: 'A', lead: 'recorder', parts: ['harp', 'pizz', 'frame'], dyn: 0.82 },
    { s: 'A', lead: 'violin', harmony: 'recorder', parts: ['harp', 'strum', 'pizz', 'frame', 'tamb'], dyn: 0.88 },
    { s: 'B', lead: 'violin', parts: ['harp', 'pad', 'pizz', 'frame'], dyn: 0.85 },
    { s: 'B', lead: 'recorder', harmony: 'violin', parts: ['harp', 'strum', 'pizz', 'frame', 'tamb'], dyn: 0.92 },
    { s: 'turn', parts: ['harp', 'low'], dyn: 0.7 },
    { s: 'A', lead: 'flute', parts: ['harp', 'strum', 'pizz', 'frame'], dyn: 0.85 },
    { s: 'B', lead: 'violin', harmony: 'flute', parts: ['harp', 'strum', 'pizz', 'pad', 'frame', 'tamb'], dyn: 0.95 },
    { s: 'A', lead: 'recorder', harmony: 'violin', parts: ['harp', 'strum', 'pizz', 'frame', 'tamb'], dyn: 1 },
    { s: 'end', parts: ['harpEnd', 'strumEnd', 'frameEnd'], dyn: 0.9 },
  ],
  parts: () => {
    let upper: number[] | null = null;
    let strumV: number[] | null = null;
    return {
      // Bass on the two big beats, the chord answering in between: the lilt of a jig.
      harp: (c, a, len, put) => {
        const v = voiceLead(c, upper, 62, 76, 3);
        upper = v;
        const bass = at(c.bass, 38);
        put('harp', bass, a, 3, 0.7);
        put('harp', v[1], a + 1, 2, 0.4);
        put('harp', v[2], a + 2, 1.5, 0.36);
        if (len >= 6) {
          put('harp', at(c.root + 7, bass + 1), a + 3, 3, 0.55);
          put('harp', v[0], a + 4, 2, 0.38);
          put('harp', v[1], a + 5, 1.5, 0.34);
        }
      },
      strum: (c, a, len, put) => {
        const v = voiceLead(c, strumV, 52, 71, 4);
        strumV = v;
        v.forEach((n, i) => put('strum', n, a + i * 0.06, 2.6, 0.42));
      },
      pizz: (c, a, len, put) => {
        const r = at(c.bass, 38);
        put('celloPizz', r, a, 1, 0.72);
        if (len >= 6) put('celloPizz', at(c.root + 7, r - 5), a + 3, 1, 0.55);
      },
      frame: (_c, a, len, put, w) => {
        put('kit', KIT.frame, a, 2, 0.62);
        if (len >= 6) put('kit', KIT.frame2, a + 3, 2, 0.45);
        if (len >= 6 && w.bar % 2 === 1) put('kit', KIT.frameMute, a + 5, 1, 0.28);
        if (w.bar === w.bars - 1) put('kit', KIT.frameMute2, a + 4, 1, 0.3);
      },
      tamb: (_c, a, len, put, w) => {
        for (const u of [2, 5]) if (u < len) put('kit', KIT.tamb, a + u, 1, 0.13 + w.rnd() * 0.05);
        if (w.bar % 4 === 3) put('kit', KIT.tambShake, a + 3, 1.5, 0.12);
      },
      pad: strings(62, 77, 0.3),
      low: celloRoot(0.4),
      harpEnd,
      strumEnd: (c, a, _len, put) => voiceLead(c, null, 52, 71, 4).forEach((n, i) => put('strum', n, a + i * 0.08, 6, 0.5)),
      frameEnd: (_c, a, _len, put) => put('kit', KIT.frame, a, 4, 0.55),
    };
  },
};

// ---------------------------------------------------------------------------
// 2. Hearthside: a slow waltz in E minor, 3/4
// ---------------------------------------------------------------------------

const hearthside: Piece = {
  id: 'hearthside',
  title: 'Hearthside',
  scene: 'menu',
  unit: 60 / 84 / 2,
  bar: 6,
  sections: {
    intro: { chords: ['Em', 'C', 'Am', 'B7'] },
    A: {
      chords: ['Em', 'C', 'G', 'D', 'Em', 'C', 'Am:4 B7:2', 'Em'],
      tune: 'B4:4 E5:2 | G5:4 E5:2 | D5:3 C5:1 B4:2 | A4:4 F#4:2 | B4:4 E5:2 | G5:3 A5:1 G5:2 | E5:2 C5:2 D#5:2 | E5:6',
    },
    B: {
      chords: ['C', 'D', 'Bm', 'Em', 'Am', 'D', 'G:4 B7:2', 'Em'],
      tune: 'E5:2 G5:2 C6:2 | B5:3 A5:1 F#5:2 | D5:4 F#5:2 | G5:4 B4:2 | A4:2 C5:2 E5:2 | F#5:3 E5:1 D5:2 | B4:2 D5:2 D#5:2 | E5:6',
    },
    end: { chords: ['Em', 'Em'] },
  },
  form: [
    { s: 'intro', parts: ['harp', 'low'], dyn: 0.72 },
    { s: 'A', lead: 'flute', parts: ['harp', 'low'], dyn: 0.78 },
    { s: 'A', lead: 'violin', harmony: 'flute', parts: ['harp', 'low', 'pad'], dyn: 0.84 },
    { s: 'B', lead: 'flute', harmony: 'violin', parts: ['harp', 'low', 'pad', 'hand'], dyn: 0.9 },
    { s: 'A', lead: 'recorder', parts: ['harp', 'low'], dyn: 0.8 },
    { s: 'B', lead: 'violin', harmony: 'flute', parts: ['harp', 'low', 'pad'], dyn: 0.94 },
    { s: 'A', lead: 'flute', harmony: 'recorder', parts: ['harp', 'low', 'hand'], dyn: 0.84 },
    { s: 'end', parts: ['harpEnd', 'celloEnd'], dyn: 0.8 },
  ],
  parts: () => {
    let upper: number[] | null = null;
    return {
      // Oom-pah-pah: a low note, then the chord twice, softly rolled.
      harp: (c, a, len, put) => {
        const v = voiceLead(c, upper, 59, 72, 3);
        upper = v;
        put('harp', at(c.bass, 40), a, len, 0.68);
        for (const u of [2, 4]) {
          if (u >= len) continue;
          v.forEach((n, i) => put('harp', n, a + u + i * 0.05, 2, 0.34));
        }
      },
      low: celloRoot(0.36),
      pad: strings(62, 76, 0.2),
      hand: (_c, a, len, put, w) => {
        if (len < 6) return;
        put('kit', KIT.frameHand, a, 1, 0.3);
        if (w.bar % 2 === 1) put('kit', KIT.frameMute, a + 4, 1, 0.18);
      },
      harpEnd,
      celloEnd,
    };
  },
};

// ---------------------------------------------------------------------------
// 3. Duel by Lanternlight: A minor, 4/4, a cello ostinato under a long tune
// ---------------------------------------------------------------------------

const duel: Piece = {
  id: 'duel',
  title: 'Duel by Lanternlight',
  scene: 'match',
  unit: 60 / 96 / 2,
  bar: 8,
  sections: {
    intro: { chords: ['Am', 'Am', 'F', 'E'] },
    A: {
      chords: ['Am', 'Am', 'F', 'G', 'Am', 'Am', 'Dm', 'E'],
      tune: 'A4:6 C5:2 | B4:4 A4:2 G4:2 | F4:2 A4:2 C5:4 | B4:4 D5:2 G4:2 | E5:6> D5:2 | C5:4 B4:2 A4:2 | F5:4> E5:2 D5:2 | E5:8',
    },
    A2: {
      chords: ['Am', 'Am', 'F', 'G', 'Am', 'F', 'E', 'Am'],
      tune: 'A4:6 C5:2 | B4:4 A4:2 G4:2 | F4:2 A4:2 C5:4 | D5:4 B4:2 G4:2 | E5:4 A5:4> | G5:2 F5:2 E5:2 D5:2 | E5:4 D5:2 B4:2 | A4:8',
    },
    B: {
      chords: ['F', 'G', 'Em', 'Am', 'F', 'G', 'E', 'E'],
      tune: 'A4:2 C5:2 F5:4> | G5:3 F5:1 E5:2 D5:2 | E5:4 B4:4 | C5:3 B4:1 A4:4 | A4:2 C5:2 F5:4> | G5:3 A5:1 B5:4 | G#5:4> E5:4 | E5:6 r:2',
    },
    bridge: { chords: ['Am', 'Am', 'F', 'E'] },
    end: { chords: ['Am', 'Am'] },
  },
  form: [
    { s: 'intro', parts: ['ost', 'pad'], dyn: 0.75 },
    { s: 'A', lead: 'vlnEns', parts: ['ost', 'low', 'drum'], dyn: 0.8 },
    { s: 'A2', lead: 'violin', harmony: 'vlnEns', parts: ['ost', 'low', 'pad', 'drum', 'harp'], dyn: 0.85 },
    { s: 'B', lead: 'vlnEns', parts: ['ost', 'horn', 'drum', 'harp', 'more'], dyn: 0.9 },
    { s: 'bridge', parts: ['ost', 'pad', 'build'], dyn: 0.85 },
    { s: 'A', lead: 'horn', octave: -1, parts: ['ost', 'pad', 'drum', 'more'], dyn: 0.9 },
    { s: 'A2', lead: 'flute', harmony: 'violin', parts: ['ost', 'low', 'pad', 'drum', 'harp', 'more'], dyn: 0.92 },
    { s: 'B', lead: 'violin', harmony: 'vlnEns', parts: ['ost', 'horn', 'pad', 'drum', 'more'], dyn: 1 },
    { s: 'end', parts: ['ostEnd', 'timpEnd', 'padEnd'], dyn: 0.85 },
  ],
  parts: () => {
    let upper: number[] | null = null;
    const OST = [0, 0, 7, 0, 12, 0, 7, 0];
    const OST_VEL = [0.78, 0.42, 0.52, 0.42, 0.66, 0.42, 0.52, 0.48];
    return {
      // Eighth notes that never stop: the root, its fifth and octave, plucked.
      ost: (c, a, len, put) => {
        const r = at(c.bass, 36);
        for (let u = 0; u < len; u++) put('celloPizz', r + OST[u % 8], a + u, 0.9, OST_VEL[u % 8]);
      },
      low: celloRoot(0.34),
      pad: strings(60, 76, 0.28),
      horn: hornPad,
      // Harp on the off-beats, climbing through the chord.
      harp: (c, a, len, put) => {
        const v = voiceLead(c, upper, 64, 79, 3);
        upper = v;
        for (let u = 1, k = 0; u < len; u += 2, k++) put('harp', v[k % 3], a + u, 1.5, 0.28);
      },
      drum: (_c, a, len, put, w) => {
        put('kit', KIT.frame, a, 2, 0.62);
        if (len >= 8) put('kit', KIT.frame2, a + 4, 2, 0.45);
        if (len >= 8) put('kit', KIT.frameMute, a + 7, 1, 0.26);
        if (w.bar % 4 === 3 && len >= 8) {
          put('kit', KIT.frameMute2, a + 6, 1, 0.32);
          put('kit', KIT.frameMute, a + 6.5, 0.5, 0.28);
        }
      },
      // The layer that rises when a hero is in danger (its level follows the match).
      more: (_c, a, len, put, w) => {
        put('kitX', KIT.bdrum, a, 3, 0.62);
        if (len >= 8) put('kitX', KIT.timp, a + 4, 3, 0.42);
        if (w.bar % 4 === 3 && len >= 8) {
          put('kitX', KIT.timp, a + 6, 1, 0.45);
          put('kitX', KIT.timp, a + 7, 1, 0.55);
        }
      },
      build: (_c, a, len, put, w) => {
        const v = 0.35 + 0.12 * w.bar;
        put('kit', KIT.timpLow, a, 3, v);
        if (w.bar === w.bars - 1) for (const u of [4, 5, 6, 7]) if (u < len) put('kit', KIT.timp, a + u, 1, v * 0.8 + u * 0.03);
      },
      ostEnd: (c, a, _len, put) => put('celloPizz', at(c.bass, 36), a, 2, 0.8),
      timpEnd: (_c, a, _len, put) => put('kit', KIT.timpLow, a, 6, 0.6),
      padEnd: (c, a, _len, put) => voiceLead(c, null, 57, 72, 3).forEach((n) => put('vlnEns', n, a, 12, 0.3)),
    };
  },
};

// ---------------------------------------------------------------------------
// 4. The Turning Card: D minor, 6/8, flowing harp under a violin
// ---------------------------------------------------------------------------

const turningCard: Piece = {
  id: 'turning-card',
  title: 'The Turning Card',
  scene: 'match',
  unit: 60 / 66 / 3,
  bar: 6,
  sections: {
    intro: { chords: ['Dm', 'Dm', 'C', 'A'] },
    A: {
      chords: ['Dm', 'Dm', 'C', 'C', 'Bb', 'C', 'Dm', 'A'],
      tune: 'D5:3 E5:2 F5:1 | A5:4> G5:1 F5:1 | G5:3 E5:2 C5:1 | E5:6 | D5:3 F5:2 D5:1 | E5:3 G5:2 E5:1 | F5:2 E5:1 D5:2 C5:1 | C#5:6',
    },
    A2: {
      chords: ['Dm', 'Dm', 'C', 'C', 'Bb', 'Gm', 'A7', 'Dm'],
      tune: 'D5:3 E5:2 F5:1 | A5:4> G5:1 F5:1 | G5:2 A5:1 G5:2 E5:1 | C5:6 | F5:3 D5:2 Bb4:1 | D5:3 G5:2 Bb4:1 | A4:2 C#5:1 E5:2 G5:1 | D5:6',
    },
    B: {
      chords: ['F', 'C', 'Dm', 'Bb', 'F', 'C', 'Bb', 'A'],
      tune: 'C5:2 F5:1 A5:3> | G5:3 E5:2 C5:1 | F5:2 E5:1 D5:3 | D5:2 C5:1 Bb4:3 | A4:2 C5:1 F5:3 | E5:2 G5:1 C6:3> | Bb5:2 A5:1 G5:2 F5:1 | E5:3 C#5:3',
    },
    end: { chords: ['Dm', 'Dm'] },
  },
  form: [
    { s: 'intro', parts: ['harp', 'low'], dyn: 0.74 },
    { s: 'A', lead: 'violin', parts: ['harp', 'low', 'drum'], dyn: 0.8 },
    { s: 'A2', lead: 'flute', parts: ['harp', 'low', 'pad', 'drum'], dyn: 0.82 },
    { s: 'B', lead: 'violin', harmony: 'flute', parts: ['harp', 'pad', 'horn', 'drum', 'more'], dyn: 0.9 },
    { s: 'A', lead: 'violin', harmony: 'vlnEns', parts: ['harp', 'low', 'pad', 'drum', 'more'], dyn: 0.9 },
    { s: 'B', lead: 'flute', harmony: 'violin', parts: ['harp', 'low', 'horn', 'drum', 'more'], dyn: 0.95 },
    { s: 'A2', lead: 'violin', parts: ['harp', 'low', 'pad', 'drum'], dyn: 0.85 },
    { s: 'end', parts: ['harpEnd', 'celloEnd'], dyn: 0.8 },
  ],
  parts: () => ({
    // Six eighths up and back through the chord, every bar.
    harp: (c, a, len, put) => {
      const r = at(c.bass, 50);
      const third = c.ivs[1];
      const run = [r, r + 7, r + 12, r + 12 + third, r + 12, r + 7];
      const vel = [0.58, 0.38, 0.44, 0.48, 0.4, 0.36];
      for (let u = 0; u < len; u++) put('harp', run[u % 6], a + u, 2.2, vel[u % 6]);
    },
    low: celloRoot(0.36),
    pad: strings(60, 74, 0.26),
    horn: hornPad,
    drum: (_c, a, len, put) => {
      put('kit', KIT.frame, a, 2, 0.42);
      if (len >= 6) put('kit', KIT.frameMute, a + 3, 1, 0.24);
    },
    more: (_c, a, len, put, w) => {
      if (w.bar % 2 === 0) put('kitX', KIT.bdrum, a, 3, 0.55);
      if (w.bar % 4 === 3 && len >= 6) {
        put('kitX', KIT.timp, a + 3, 1.5, 0.4);
        put('kitX', KIT.timp, a + 4.5, 1.5, 0.5);
      }
    },
    harpEnd,
    celloEnd,
  }),
};

export const PIECES: Piece[] = [lanternInn, hearthside, duel, turningCard];

/** A piece as notes in seconds: a new arrangement detail (timing, touch) for every seed. */
export function render(p: Piece, seed: number): { events: Ev[]; seconds: number; errors: string[] } {
  const rnd = dice(seed);
  const parts = p.parts();
  const events: Ev[] = [];
  const errors: string[] = [];
  let barAt = 0;
  for (const pass of p.form) {
    const sec = p.sections[pass.s];
    if (!sec) {
      errors.push(`no section ${pass.s}`);
      continue;
    }
    const dyn = pass.dyn ?? 1;
    const bars = sec.chords.length;
    const segs = sec.chords.map((text) => barChords(text, p.bar));
    sec.chords.forEach((_t, bar) => {
      for (const seg of segs[bar]) {
        for (const name of pass.parts) {
          const part = parts[name];
          if (!part) {
            errors.push(`${p.id}: no part ${name}`);
            continue;
          }
          part(seg.c, seg.at, seg.len, (inst, m, a, len, vel) => {
            events.push({ t: (barAt + bar) * p.bar + a, inst, midi: m, dur: len, vel: Math.min(1, vel * dyn) });
          }, { bar, bars, rnd });
        }
      }
    });
    if (sec.tune && pass.lead) {
      const tn = tune(sec.tune, p.bar);
      errors.push(...tn.errors.map((e) => `${p.id} ${pass.s}: ${e}`));
      if (tn.bars !== bars) errors.push(`${p.id} ${pass.s}: tune has ${tn.bars} bars, chords ${bars}`);
      const shift = 12 * (pass.octave ?? 0);
      for (const n of tn.notes) {
        const bar = Math.floor(n.at / p.bar);
        const within = n.at - bar * p.bar;
        const seg = (segs[bar] ?? []).filter((s) => s.at <= within + 1e-6).pop();
        // Phrases lean forward to their middle and settle at the end.
        const arc = 0.9 + 0.1 * Math.sin(Math.PI * ((bar % 4) + 0.5) / 4);
        const vel = (n.accent ? 0.86 : 0.72) * arc * dyn;
        events.push({ t: barAt * p.bar + n.at, inst: pass.lead, midi: n.midi + shift, dur: n.len, vel });
        if (pass.harmony && seg && n.len >= 1) {
          const h = harmonyBelow(n.midi, seg.c);
          if (h !== null) events.push({ t: barAt * p.bar + n.at, inst: pass.harmony, midi: h + shift, dur: n.len, vel: vel * 0.62 });
        }
      }
    }
    barAt += bars;
  }
  // Units to seconds, with the small unevenness of people playing.
  for (const e of events) {
    const loose = LOOSE[e.inst] ?? 0.006;
    e.t = Math.max(0, e.t * p.unit + (rnd() - 0.35) * loose);
    e.dur = e.dur * p.unit * (LEGATO[e.inst] ?? 1);
    e.vel = Math.max(0.05, Math.min(1, e.vel * (0.94 + rnd() * 0.12)));
  }
  events.sort((x, y) => x.t - y.t);
  return { events, seconds: barAt * p.bar * p.unit, errors };
}
