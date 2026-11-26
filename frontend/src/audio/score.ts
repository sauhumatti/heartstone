// Written music, turned into notes: chord symbols, tunes in a short text form, and the parts
// that accompany them. Nothing here makes sound (that is music.ts), so the pieces can be
// checked without a browser (scripts/check-music.mjs).

/** One note to play: when and how long in seconds from the start of the piece. */
export interface Ev {
  t: number;
  inst: string;
  midi: number;
  dur: number;
  vel: number;
}

export interface Chord {
  /** Pitch class of the root, C = 0. */
  root: number;
  /** Intervals above the root. */
  ivs: number[];
  /** Pitch class of the bass, when it is not the root (C/E). */
  bass: number;
}

const PC: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const QUALITY: Record<string, number[]> = {
  '': [0, 4, 7],
  m: [0, 3, 7],
  '7': [0, 4, 7, 10],
  m7: [0, 3, 7, 10],
  maj7: [0, 4, 7, 11],
  sus4: [0, 5, 7],
  sus2: [0, 2, 7],
  dim: [0, 3, 6],
  add9: [0, 4, 7, 14],
  madd9: [0, 3, 7, 14],
};

function pitchClass(name: string): number {
  const base = PC[name[0]];
  if (base === undefined) throw new Error(`not a note: ${name}`);
  let pc = base;
  for (const ch of name.slice(1)) pc += ch === '#' ? 1 : ch === 'b' ? -1 : 0;
  return (pc + 12) % 12;
}

export function chord(symbol: string): Chord {
  const [main, slash] = symbol.split('/');
  const m = /^([A-G][#b]?)(.*)$/.exec(main);
  if (!m || !(m[2] in QUALITY)) throw new Error(`unknown chord: ${symbol}`);
  const root = pitchClass(m[1]);
  return { root, ivs: QUALITY[m[2]], bass: slash ? pitchClass(slash) : root };
}

/** Does this chord contain the pitch (any octave)? */
export function inChord(c: Chord, midi: number): boolean {
  return c.ivs.some((iv) => (c.root + iv) % 12 === ((midi % 12) + 12) % 12);
}

/** The chord's notes from `lo` to `hi`, lowest first. */
export function tonesIn(c: Chord, lo: number, hi: number): number[] {
  const out: number[] = [];
  for (let n = lo; n <= hi; n++) if (inChord(c, n)) out.push(n);
  return out;
}

/** The lowest note at or above `lo` with this pitch class. */
export function at(pc: number, lo: number): number {
  return lo + ((pc - lo) % 12 + 12) % 12;
}

/** Scientific pitch to MIDI: C4 = 60, F#5 = 78, Bb3 = 58. */
export function midi(name: string): number {
  const m = /^([A-G][#b]?)(-?\d)$/.exec(name);
  if (!m) throw new Error(`not a pitch: ${name}`);
  return 12 * (Number(m[2]) + 1) + pitchClass(m[1]);
}

/** A bar of chords: "Am" fills the bar, "Am E" splits it evenly, "Am:4 E:2" in units. */
export function barChords(text: string, barUnits: number): { c: Chord; at: number; len: number }[] {
  const parts = text.trim().split(/\s+/);
  const explicit = parts.every((p) => p.includes(':'));
  let pos = 0;
  return parts.map((p) => {
    const [sym, len] = p.split(':');
    const units = explicit ? Number(len) : barUnits / parts.length;
    const item = { c: chord(sym), at: pos, len: units };
    pos += units;
    return item;
  });
}

export interface TuneNote {
  /** In units from the start of the tune. */
  at: number;
  len: number;
  midi: number;
  accent: boolean;
}

/**
 * A tune: bars split by "|", notes as pitch:units ("D5:2", "F#5:1", "Bb4:3"), "r:2" a rest,
 * "-:2" holds the previous note longer, a trailing ">" accents a note. Every bar must add up
 * to the bar's length; the check script holds the pieces to that.
 */
export function tune(text: string, barUnits: number): { notes: TuneNote[]; bars: number; errors: string[] } {
  const notes: TuneNote[] = [];
  const errors: string[] = [];
  const bars = text.split('|').map((b) => b.trim()).filter(Boolean);
  let pos = 0;
  bars.forEach((bar, i) => {
    let sum = 0;
    for (const tok of bar.split(/\s+/)) {
      const accent = tok.endsWith('>');
      const [p, l] = tok.replace(/>$/, '').split(':');
      const len = Number(l);
      if (!Number.isFinite(len) || len <= 0) {
        errors.push(`bar ${i + 1}: bad length in "${tok}"`);
        continue;
      }
      if (p === '-') {
        if (notes.length) notes[notes.length - 1].len += len;
      } else if (p !== 'r') {
        notes.push({ at: pos + sum, len, midi: midi(p), accent });
      }
      sum += len;
    }
    if (Math.abs(sum - barUnits) > 1e-6) errors.push(`bar ${i + 1} ("${bar}") is ${sum} units, not ${barUnits}`);
    pos += barUnits;
  });
  return { notes, bars: bars.length, errors };
}

/** A small seeded random source, so a piece can be rebuilt the same way for a check. */
export function dice(seed: number): () => number {
  let s = seed >>> 0 || 1;
  return () => {
    s ^= s << 13;
    s ^= s >>> 17;
    s ^= s << 5;
    return ((s >>> 0) % 1_000_000) / 1_000_000;
  };
}

/** The chord voicing nearest to the last one, `count` notes between lo and hi. */
export function voiceLead(c: Chord, prev: number[] | null, lo: number, hi: number, count = 3): number[] {
  const pool = tonesIn(c, lo, hi);
  let best: number[] = [];
  let bestCost = Infinity;
  for (let i = 0; i + count <= pool.length; i++) {
    const v = pool.slice(i, i + count);
    // Close voicings only: the notes within an octave and a fourth.
    if (v[v.length - 1] - v[0] > 17) continue;
    const cost = prev ? v.reduce((s, n, k) => s + Math.abs(n - (prev[k] ?? prev[prev.length - 1])), 0) : Math.abs(v[0] - (lo + hi) / 2);
    if (cost < bestCost) {
      bestCost = cost;
      best = v;
    }
  }
  return best.length ? best : pool.slice(0, count);
}

/** A second voice under a tune: the nearest chord note a third to a sixth below each note. */
export function harmonyBelow(n: number, c: Chord): number | null {
  for (let d = 3; d <= 9; d++) if (inChord(c, n - d)) return n - d;
  return null;
}

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

export type Put = (inst: string, midi: number, at: number, len: number, vel: number) => void;
export interface Where {
  /** Bar within the section, from 0. */
  bar: number;
  bars: number;
  rnd: () => number;
}
export type Part = (c: Chord, at: number, len: number, put: Put, where: Where) => void;

export interface Section {
  chords: string[];
  tune?: string;
}

export interface Pass {
  s: string;
  lead?: string;
  harmony?: string;
  /** Octaves to move the tune by (the horn plays it an octave down). */
  octave?: number;
  parts: string[];
  /** Overall loudness of the pass, 1 = full. */
  dyn?: number;
}

export type MusicScene = 'menu' | 'arena' | 'match';

export interface Piece {
  id: string;
  title: string;
  scene: MusicScene;
  /** Seconds per unit (an eighth note in these pieces). */
  unit: number;
  /** Units per bar. */
  bar: number;
  sections: Record<string, Section>;
  form: Pass[];
  /** The accompanying parts; made fresh for every playing, as some remember the last chord. */
  parts: () => Record<string, Part>;
}
