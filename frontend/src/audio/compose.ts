// Algorithmic composition & music theory toolkit powered by `tonal`.
// Uses Tonal's scales, modes, Roman-numeral progressions, chords, and intervals to
// generate harmonically valid melodies, walking basslines, harp arpeggios,
// countermelodies, and rhythmic grooves for Lanternfall's Tone.js acoustic ensemble.
import { Chord as TChord, Note as TNote, Progression, Scale } from 'tonal';
import { at, type Chord, tonesIn, voiceLead } from './score';

export type Put = (inst: string, midi: number, at: number, len: number, vel: number) => void;
export interface Where {
  bar: number;
  bars: number;
  rnd: () => number;
}
export type Part = (c: Chord, at: number, len: number, put: Put, where: Where) => void;

/** Normalize a Tonal chord symbol into the set supported by score.ts. */
function normalizeChordSymbol(sym: string): string {
  const [rawMain, slash] = sym.split('/');
  const m = /^([A-G][#b]?)(.*)$/.exec(rawMain.trim());
  if (!m) return sym;
  const root = m[1];
  const q = m[2];
  let mapped = '';
  if (q === '' || q === 'M' || q === 'maj') mapped = '';
  else if (q === 'm' || q === 'min') mapped = 'm';
  else if (q === '7') mapped = '7';
  else if (q === 'm7' || q === 'min7') mapped = 'm7';
  else if (q === 'maj7' || q === 'M7') mapped = 'maj7';
  else if (q === 'sus4') mapped = 'sus4';
  else if (q === 'sus2') mapped = 'sus2';
  else if (q === 'dim' || q === 'o' || q === 'm7b5') mapped = 'dim';
  else if (q === 'add9') mapped = 'add9';
  else if (q === 'madd9') mapped = 'madd9';
  else if (q.startsWith('m')) mapped = 'm';
  else mapped = '';
  return slash ? `${root}${mapped}/${slash}` : `${root}${mapped}`;
}

/**
 * Convert Roman numerals in a key (via Tonal `Progression.fromRomanNumerals`) into
 * bar chord strings accepted by `score.ts`.
 * Supports split bars like `"IV:4 V7:2"` or `"i VII"`.
 */
export function romanBars(tonic: string, bars: string[]): string[] {
  return bars.map((bar) =>
    bar
      .trim()
      .split(/\s+/)
      .map((tok) => {
        const [rn, len] = tok.split(':');
        const resolved = Progression.fromRomanNumerals(tonic, [rn])[0] || rn;
        const clean = normalizeChordSymbol(resolved);
        return len ? `${clean}:${len}` : clean;
      })
      .join(' '),
  );
}

/** Format a MIDI note number as scientific pitch (`C4`, `F#5`, `Bb4`) via Tonal. */
export function midiToPitch(m: number): string {
  const raw = TNote.fromMidiSharps(Math.round(m));
  return raw || 'C4';
}

/** Return the MIDI pitch of scale degree `deg` (0-indexed, may be negative or >= 7) in a Tonal scale. */
export function scaleDegreeMidi(tonicWithOctave: string, mode: string, deg: number): number {
  const stepFn = Scale.steps(`${tonicWithOctave} ${mode}`);
  const noteName = stepFn(deg);
  const m = TNote.midi(noteName);
  if (m === null) throw new Error(`Tonal could not resolve degree ${deg} of ${tonicWithOctave} ${mode}`);
  return m;
}

/**
 * One step in a scale-degree melodic motif:
 *   [degree, units, accent?]
 * Use `'r'` for rest, `'-'` to tie/extend the previous note.
 */
export type MotifStep = [number | 'r' | '-', number, boolean?];

/**
 * Realize bars of scale-degree motifs into a `score.ts` tune string using Tonal's scale engine.
 * Optionally transposes each bar by `barOffsets[bar]` scale degrees and clamps into `[minMidi, maxMidi]`.
 */
export function realizeMotifs(
  tonicWithOctave: string,
  mode: string,
  bars: MotifStep[][],
  opts: { barOffsets?: number[]; minMidi?: number; maxMidi?: number; chordSymbols?: string[]; snapStrongBeats?: boolean } = {},
): string {
  const { barOffsets = [], minMidi = 48, maxMidi = 88, chordSymbols, snapStrongBeats = false } = opts;
  return bars
    .map((steps, bi) => {
      const offset = barOffsets[bi] ?? 0;
      const barChordNotes = chordSymbols?.[bi]
        ? new Set(
            TChord.get(chordSymbols[bi].split(/\s+/)[0].split(':')[0])
              .notes.map((n) => TNote.chroma(n))
              .filter((x): x is number => x !== undefined),
          )
        : null;

      let pos = 0;
      return steps
        .map(([deg, len, accent]) => {
          const atBeat = pos;
          pos += len;
          if (deg === 'r') return `r:${len}`;
          if (deg === '-') return `-:${len}`;
          let m = scaleDegreeMidi(tonicWithOctave, mode, deg + offset);
          while (m < minMidi) m += 12;
          while (m > maxMidi) m -= 12;
          // On strong downbeats, optionally gently snap non-chord tones to nearest scale-chord tone.
          if (snapStrongBeats && atBeat === 0 && barChordNotes && barChordNotes.size > 0 && !barChordNotes.has(m % 12)) {
            for (const delta of [1, -1, 2, -2]) {
              const cand = scaleDegreeMidi(tonicWithOctave, mode, deg + offset + delta);
              if (cand >= minMidi && cand <= maxMidi && barChordNotes.has(cand % 12)) {
                m = cand;
                break;
              }
            }
          }
          return `${midiToPitch(m)}:${len}${accent ? '>' : ''}`;
        })
        .join(' ');
    })
    .join(' | ');
}

/**
 * Generate a walking pizzicato bassline that connects chord roots via Tonal scale steps
 * on the final beat of each bar.
 */
export function walkingBassPart(
  tonic: string,
  mode: string,
  opts: { lo?: number; stepUnit?: number; vel?: number; inst?: string } = {},
): Part {
  const { lo = 36, stepUnit = 2, vel = 0.68, inst = 'celloPizz' } = opts;
  const scaleChromas = new Set(
    Scale.get(`${tonic} ${mode}`)
      .notes.map((n) => TNote.chroma(n))
      .filter((x): x is number => x !== undefined),
  );
  return (c, a, len, put, w) => {
    const r = at(c.bass, lo);
    const fifth = at(c.root + 7, r - 5);
    const third = at(c.root + (c.ivs[1] ?? 4), r);
    const beats = Math.floor(len / stepUnit);
    for (let i = 0; i < beats; i++) {
      const u = i * stepUnit;
      if (i === 0) {
        put(inst, r, a + u, stepUnit * 0.9, vel);
      } else if (i === 1) {
        put(inst, third <= r + 7 ? third : fifth, a + u, stepUnit * 0.85, vel * 0.78);
      } else if (i === beats - 1) {
        // Approach step in the piece's Tonal scale
        const dir = w.bar % 2 === 0 ? 1 : -1;
        let walk = fifth + dir;
        if (!scaleChromas.has(((walk % 12) + 12) % 12)) walk = fifth + dir * 2;
        put(inst, Math.max(lo, Math.min(lo + 19, walk)), a + u, stepUnit * 0.85, vel * 0.75);
      } else {
        put(inst, fifth, a + u, stepUnit * 0.85, vel * 0.84);
      }
    }
  };
}

/** Flowing harp arpeggio generator supporting 4/4 (8 units), 3/4 (6 units), and 6/8 (6 units). */
export function arpeggioHarpPart(opts: {
  bassLo?: number;
  lo?: number;
  hi?: number;
  pattern: number[];
  vel?: number;
  noteLen?: number;
}): Part {
  const { bassLo = 40, lo = 52, hi = 76, pattern, vel = 0.56, noteLen = 2.4 } = opts;
  return (c, a, len, put) => {
    const bass = at(c.bass, bassLo);
    const chordTones = tonesIn(c, lo, hi);
    const pool = [bass, ...chordTones];
    if (pool.length < 2) return;
    for (let u = 0; u < len; u++) {
      const idx = pattern[u % pattern.length];
      if (idx < 0) continue;
      const note = pool[Math.min(idx, pool.length - 1)];
      const accent = u === 0 ? 1.0 : u === Math.floor(len / 2) ? 0.85 : 0.68;
      put('harp', note, a + u, noteLen, vel * accent);
    }
  };
}

/** Syncopated tavern lute/guitar strum pattern using smooth voice leading. */
export function rhythmicStrumPart(hits: { at: number; dur: number; vel: number; spread?: number }[], lo = 52, hi = 72): Part {
  let prev: number[] | null = null;
  return (c, a, len, put) => {
    const v = voiceLead(c, prev, lo, hi, 4);
    prev = v;
    for (const h of hits) {
      if (h.at >= len) continue;
      const spread = h.spread ?? 0.05;
      v.forEach((n, i) => put('strum', n, a + h.at + i * spread, Math.min(h.dur, len - h.at + 0.5), h.vel));
    }
  };
}

/**
 * Algorithmic lyrical countermelody / descant voice constrained to the current chord & Tonal scale.
 * Moves smoothly by step or gentle leap in contrary/complementary rhythm to the main melody.
 */
export function descantPart(
  inst: string,
  tonic: string,
  mode: string,
  opts: { lo: number; hi: number; rhythm: [number, number][]; vel?: number },
): Part {
  const { lo, hi, rhythm, vel = 0.5 } = opts;
  const scaleChromas = new Set(
    Scale.get(`${tonic} ${mode}`)
      .notes.map((n) => TNote.chroma(n))
      .filter((x): x is number => x !== undefined),
  );
  let lastNote = Math.round((lo + hi) / 2);
  return (c, a, len, put, w) => {
    const chordPool = tonesIn(c, lo, hi);
    if (!chordPool.length) return;
    rhythm.forEach(([offset, dur], idx) => {
      if (offset >= len) return;
      // Pick a chord tone near lastNote, alternating gentle rise & fall across bars
      const target = idx === 0 ? lastNote + (w.bar % 2 === 0 ? 3 : -2) : lastNote + (idx % 2 === 1 ? -2 : 2);
      let chosen = chordPool[0];
      let bestDist = Infinity;
      for (const cand of chordPool) {
        if (!scaleChromas.has(((cand % 12) + 12) % 12)) continue;
        const d = Math.abs(cand - target) + (cand === lastNote ? 2.5 : 0);
        if (d < bestDist) {
          bestDist = d;
          chosen = cand;
        }
      }
      lastNote = chosen;
      put(inst, chosen, a + offset, Math.min(dur, len - offset), vel * (idx === 0 ? 1 : 0.86));
    });
  };
}

/** Driving battle ostinato on `celloPizz` with dynamic pattern & accents. */
export function ostinatoPart(
  intervals: number[],
  vels: number[],
  opts: { lo?: number; inst?: string; dur?: number } = {},
): Part {
  const { lo = 36, inst = 'celloPizz', dur = 0.9 } = opts;
  return (c, a, len, put) => {
    const r = at(c.bass, lo);
    for (let u = 0; u < len; u++) {
      const iv = intervals[u % intervals.length];
      if (iv < 0) continue;
      put(inst, r + iv, a + u, dur, vels[u % vels.length]);
    }
  };
}

/** Martial horn call / fanfare part that voices noble fifths & octaves in horn range (43–60). */
export function hornCallPart(hits: { at: number; dur: number; vel: number; addFifth?: boolean }[]): Part {
  return (c, a, len, put) => {
    const r = at(c.root, 45);
    for (const h of hits) {
      if (h.at >= len) continue;
      put('horn', r, a + h.at, Math.min(h.dur, len - h.at), h.vel);
      if (h.addFifth && r + 7 <= 62) {
        put('horn', r + 7, a + h.at + 0.04, Math.min(h.dur, len - h.at), h.vel * 0.8);
      }
    }
  };
}
