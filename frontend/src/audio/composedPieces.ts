// Six additional pieces composed with code using `tonal` (scales, modes, Roman-numeral
// progressions, voice-leading, and countermelodies) for Lanternfall's acoustic Tone.js band:
//   Menu:  "Copper & Cider" (G Mixolydian reel), "Amber Dusk" (F major evening ballad)
//   Arena: "Hall of Keys" (D Dorian 3/4 guild march), "The Gilded Wager" (E Dorian 6/8 gambit)
//   Match: "March of the Anvil" (E minor 4/4 battle march), "Storm Over the Spire" (G minor 6/8 duel)
import {
  arpeggioHarpPart,
  descantPart,
  hornCallPart,
  type MotifStep,
  ostinatoPart,
  realizeMotifs,
  rhythmicStrumPart,
  romanBars,
  walkingBassPart,
} from './compose';
import { at, KIT, type Piece, tonesIn, voiceLead } from './score';

const makeStrings = (lo: number, hi: number, vel: number, inst = 'vlnEns') => {
  let prev: number[] | null = null;
  return (c: Parameters<ReturnType<Piece['parts']>[string]>[0], a: number, len: number, put: Parameters<ReturnType<Piece['parts']>[string]>[3]) => {
    const v = voiceLead(c, prev, lo, hi, 3);
    prev = v;
    v.forEach((n, i) => put(inst, n, a, len, vel - i * 0.03));
  };
};

const celloDrone = (vel: number, lo = 36) => (
  c: Parameters<ReturnType<Piece['parts']>[string]>[0],
  a: number,
  len: number,
  put: Parameters<ReturnType<Piece['parts']>[string]>[3],
) => put('celloEns', at(c.bass, lo), a, len, vel);

const harpRing = (
  c: Parameters<ReturnType<Piece['parts']>[string]>[0],
  a: number,
  _len: number,
  put: Parameters<ReturnType<Piece['parts']>[string]>[3],
) => {
  put('harp', at(c.bass, 38), a, 8, 0.72);
  tonesIn(c, 54, 76).slice(0, 6).forEach((n, i) => put('harp', n, a + 0.12 * (i + 1), 8, 0.48));
};

// ---------------------------------------------------------------------------
// 5. Copper & Cider (menu): lively G Mixolydian tavern reel, 4/4 (112 BPM)
// ---------------------------------------------------------------------------

const copperChordsA = romanBars('G', ['I', 'bVII', 'I', 'V', 'I', 'bVII', 'IV:4 V:4', 'I']);
const copperChordsB = romanBars('G', ['vi', 'IV', 'I', 'V', 'vi', 'bVII', 'IV:4 V:4', 'I']);

const copperTuneA: MotifStep[][] = [
  [[0, 2, true], [2, 1], [3, 1], [4, 2, true], [2, 2]],
  [[6, 2, true], [5, 1], [4, 1], [3, 2], [2, 2]],
  [[0, 1], [1, 1], [2, 1], [4, 1], [5, 2, true], [4, 2]],
  [[4, 2], [2, 2], [1, 4]],
  [[0, 2, true], [2, 1], [4, 1], [7, 2, true], [6, 2]],
  [[5, 2, true], [4, 1], [3, 1], [2, 2], [4, 2]],
  [[3, 2], [4, 2], [2, 2], [1, 2]],
  [[0, 6, true], ['r', 2]],
];

const copperTuneB: MotifStep[][] = [
  [[5, 3, true], [4, 1], [2, 2], [5, 2]],
  [[3, 3, true], [4, 1], [5, 2], [3, 2]],
  [[4, 2, true], [5, 1], [6, 1], [7, 2, true], [4, 2]],
  [[4, 2], [2, 2], [1, 3], ['r', 1]],
  [[5, 2, true], [6, 1], [7, 1], [5, 2], [4, 2]],
  [[6, 3, true], [5, 1], [4, 2], [2, 2]],
  [[3, 2], [5, 2], [4, 2], [1, 2]],
  [[0, 6, true], ['r', 2]],
];

const copperReel: Piece = {
  id: 'copper-reel',
  title: 'Copper & Cider',
  scene: 'menu',
  unit: 60 / 112 / 2,
  bar: 8,
  sections: {
    intro: { chords: romanBars('G', ['I', 'bVII', 'IV', 'I']) },
    A: {
      chords: copperChordsA,
      tune: realizeMotifs('G4', 'mixolydian', copperTuneA, { minMidi: 65, maxMidi: 82 }),
    },
    B: {
      chords: copperChordsB,
      tune: realizeMotifs('G4', 'mixolydian', copperTuneB, { minMidi: 65, maxMidi: 84 }),
    },
    end: { chords: romanBars('G', ['I', 'I']) },
  },
  form: [
    { s: 'intro', parts: ['strum', 'bass', 'frame'], dyn: 0.76 },
    { s: 'A', lead: 'recorder', parts: ['harp', 'bass', 'frame'], dyn: 0.84 },
    { s: 'A', lead: 'violin', harmony: 'recorder', parts: ['harp', 'strum', 'bass', 'frame', 'tamb'], dyn: 0.9 },
    { s: 'B', lead: 'flute', parts: ['harp', 'pad', 'bass', 'frame', 'descant'], dyn: 0.86 },
    { s: 'B', lead: 'violin', harmony: 'flute', parts: ['harp', 'strum', 'bass', 'frame', 'tamb'], dyn: 0.94 },
    { s: 'A', lead: 'recorder', harmony: 'violin', parts: ['harp', 'strum', 'bass', 'frame', 'tamb', 'descant'], dyn: 0.98 },
    { s: 'end', parts: ['harpEnd', 'strumEnd', 'frameEnd'], dyn: 0.88 },
  ],
  parts: () => ({
    harp: arpeggioHarpPart({ bassLo: 38, lo: 55, hi: 76, pattern: [0, 2, 3, 2, 1, 3, 4, 2], vel: 0.56, noteLen: 1.8 }),
    strum: rhythmicStrumPart([
      { at: 0, dur: 2.2, vel: 0.44 },
      { at: 3, dur: 1.5, vel: 0.34 },
      { at: 4, dur: 2.0, vel: 0.42 },
      { at: 6, dur: 1.4, vel: 0.32 },
    ]),
    bass: walkingBassPart('G', 'mixolydian', { lo: 38, stepUnit: 2, vel: 0.72 }),
    descant: descantPart('flute', 'G', 'mixolydian', { lo: 67, hi: 81, rhythm: [[0, 4], [4, 4]], vel: 0.36 }),
    pad: makeStrings(62, 76, 0.25),
    frame: (_c, a, len, put, w) => {
      put('kit', KIT.frame, a, 2, 0.58);
      if (len >= 8) put('kit', KIT.frameMute, a + 2, 1, 0.26);
      if (len >= 8) put('kit', KIT.frame2, a + 4, 2, 0.48);
      if (len >= 8 && w.bar % 2 === 1) put('kit', KIT.frameMute2, a + 6, 1, 0.3);
      if (len >= 8 && w.bar === w.bars - 1) put('kit', KIT.frameHand, a + 7, 1, 0.34);
    },
    tamb: (_c, a, len, put, w) => {
      for (const u of [2, 6]) if (u < len) put('kit', KIT.tamb, a + u, 1, 0.14 + w.rnd() * 0.04);
      if (w.bar % 4 === 3 && len >= 8) put('kit', KIT.tambRoll, a + 4, 3, 0.14);
    },
    harpEnd: harpRing,
    strumEnd: (c, a, _len, put) => voiceLead(c, null, 55, 72, 4).forEach((n, i) => put('strum', n, a + i * 0.07, 6, 0.5)),
    frameEnd: (_c, a, _len, put) => put('kit', KIT.frame, a, 4, 0.55),
  }),
};

// ---------------------------------------------------------------------------
// 6. Amber Dusk (menu): warm F major / D minor hearth ballad, 4/4 (76 BPM)
// ---------------------------------------------------------------------------

const amberChordsA = romanBars('F', ['I', 'vi', 'IV', 'V', 'I', 'iii', 'ii:4 V7:4', 'I']);
const amberChordsB = romanBars('F', ['IV', 'I', 'vi', 'V', 'IV', 'ii', 'I:4 V:4', 'I']);

const amberTuneA: MotifStep[][] = [
  [[2, 3, true], [3, 1], [4, 2], [2, 2]],
  [[0, 4], [2, 2], [1, 2]],
  [[3, 3, true], [4, 1], [5, 2], [3, 2]],
  [[4, 6], ['r', 2]],
  [[7, 3, true], [6, 1], [5, 2], [4, 2]],
  [[2, 4], [4, 2], [2, 2]],
  [[1, 2], [2, 2], [3, 2], [1, 2]],
  [[0, 6, true], ['r', 2]],
];

const amberTuneB: MotifStep[][] = [
  [[5, 4, true], [6, 2], [5, 2]],
  [[4, 3, true], [2, 1], [0, 4]],
  [[2, 2], [3, 2], [4, 2, true], [5, 2]],
  [[4, 6], ['r', 2]],
  [[5, 3, true], [4, 1], [3, 2], [2, 2]],
  [[1, 4], [3, 2], [1, 2]],
  [[2, 2], [4, 2], [1, 2], [4, 2]],
  [[0, 6, true], ['r', 2]],
];

const amberDusk: Piece = {
  id: 'amber-dusk',
  title: 'Amber Dusk',
  scene: 'menu',
  unit: 60 / 76 / 2,
  bar: 8,
  sections: {
    intro: { chords: romanBars('F', ['I', 'IV', 'vi', 'V']) },
    A: {
      chords: amberChordsA,
      tune: realizeMotifs('F4', 'major', amberTuneA, { minMidi: 60, maxMidi: 82 }),
    },
    B: {
      chords: amberChordsB,
      tune: realizeMotifs('F4', 'major', amberTuneB, { minMidi: 60, maxMidi: 84 }),
    },
    end: { chords: romanBars('F', ['IV', 'I']) },
  },
  form: [
    { s: 'intro', parts: ['harp', 'low'], dyn: 0.72 },
    { s: 'A', lead: 'flute', parts: ['harp', 'low'], dyn: 0.78 },
    { s: 'A', lead: 'violin', parts: ['harp', 'low', 'pad', 'descant'], dyn: 0.84 },
    { s: 'B', lead: 'flute', harmony: 'violin', parts: ['harp', 'low', 'horn', 'hand'], dyn: 0.88 },
    { s: 'A', lead: 'horn', octave: -1, parts: ['harp', 'pad', 'low'], dyn: 0.82 },
    { s: 'B', lead: 'violin', harmony: 'flute', parts: ['harp', 'low', 'pad', 'horn', 'hand'], dyn: 0.92 },
    { s: 'end', parts: ['harpEnd', 'celloEnd'], dyn: 0.78 },
  ],
  parts: () => ({
    harp: arpeggioHarpPart({ bassLo: 41, lo: 53, hi: 74, pattern: [0, 1, 2, 3, 2, 4, 3, 2], vel: 0.54, noteLen: 3.0 }),
    low: celloDrone(0.36, 36),
    pad: makeStrings(60, 74, 0.22),
    horn: hornCallPart([{ at: 0, dur: 6, vel: 0.36, addFifth: true }]),
    descant: descantPart('flute', 'F', 'major', { lo: 65, hi: 79, rhythm: [[2, 4], [6, 2]], vel: 0.36 }),
    hand: (_c, a, len, put, w) => {
      put('kit', KIT.frameHand, a, 1.5, 0.26);
      if (len >= 8 && w.bar % 2 === 1) put('kit', KIT.frameMute, a + 4, 1, 0.18);
    },
    harpEnd: harpRing,
    celloEnd: celloDrone(0.38, 36),
  }),
};

// ---------------------------------------------------------------------------
// 7. Hall of Keys (arena): noble D Dorian guild march, 3/4 (104 BPM)
// ---------------------------------------------------------------------------

const keysChordsA = romanBars('D', ['i', 'bVII', 'IV', 'i', 'bIII', 'bVII', 'V7', 'i']);
const keysChordsB = romanBars('D', ['bIII', 'IV', 'i', 'bVII', 'IV', 'i', 'bVII:4 V7:2', 'i']);

const keysTuneA: MotifStep[][] = [
  [[0, 2, true], [2, 2], [4, 2]],
  [[3, 3, true], [2, 1], [1, 2]],
  [[5, 4, true], [4, 2]],
  [[4, 4], [2, 2]],
  [[2, 2, true], [4, 2], [6, 2]],
  [[5, 3, true], [4, 1], [3, 2]],
  [[4, 2, true], [2, 2], [1, 2]],
  [[0, 5, true], ['r', 1]],
];

const keysTuneB: MotifStep[][] = [
  [[6, 3, true], [5, 1], [4, 2]],
  [[5, 4, true], [3, 2]],
  [[4, 2, true], [2, 2], [0, 2]],
  [[3, 4], [1, 2]],
  [[5, 2, true], [6, 2], [7, 2]],
  [[7, 3, true], [5, 1], [4, 2]],
  [[3, 2], [2, 2], [1, 2]],
  [[0, 5, true], ['r', 1]],
];

const hallOfKeys: Piece = {
  id: 'hall-of-keys',
  title: 'Hall of Keys',
  scene: 'arena',
  unit: 60 / 104 / 2,
  bar: 6,
  sections: {
    intro: { chords: romanBars('D', ['i', 'bVII', 'IV', 'i']) },
    A: {
      chords: keysChordsA,
      tune: realizeMotifs('D5', 'dorian', keysTuneA, { minMidi: 66, maxMidi: 82 }),
    },
    B: {
      chords: keysChordsB,
      tune: realizeMotifs('D5', 'dorian', keysTuneB, { minMidi: 66, maxMidi: 86 }),
    },
    end: { chords: romanBars('D', ['i', 'i']) },
  },
  form: [
    { s: 'intro', parts: ['harp', 'pizz', 'frame'], dyn: 0.78 },
    { s: 'A', lead: 'recorder', parts: ['harp', 'pizz', 'frame'], dyn: 0.84 },
    { s: 'A', lead: 'violin', harmony: 'recorder', parts: ['harp', 'pizz', 'pad', 'frame', 'tamb'], dyn: 0.9 },
    { s: 'B', lead: 'flute', parts: ['harp', 'pizz', 'horn', 'frame', 'descant'], dyn: 0.92 },
    { s: 'B', lead: 'violin', harmony: 'flute', parts: ['harp', 'strum', 'pizz', 'horn', 'frame', 'tamb'], dyn: 0.96 },
    { s: 'A', lead: 'horn', octave: -2, parts: ['harp', 'pizz', 'pad', 'frame'], dyn: 0.88 },
    { s: 'A', lead: 'violin', harmony: 'recorder', parts: ['harp', 'strum', 'pizz', 'horn', 'frame', 'tamb'], dyn: 1 },
    { s: 'end', parts: ['harpEnd', 'hornEnd', 'timpEnd'], dyn: 0.9 },
  ],
  parts: () => ({
    harp: arpeggioHarpPart({ bassLo: 38, lo: 53, hi: 76, pattern: [0, 2, 3, 1, 4, 2], vel: 0.56, noteLen: 2.0 }),
    pizz: walkingBassPart('D', 'dorian', { lo: 38, stepUnit: 2, vel: 0.7 }),
    strum: rhythmicStrumPart([
      { at: 0, dur: 2.0, vel: 0.4 },
      { at: 4, dur: 1.6, vel: 0.34 },
    ]),
    pad: makeStrings(62, 76, 0.25),
    horn: hornCallPart([{ at: 0, dur: 4, vel: 0.44, addFifth: true }]),
    descant: descantPart('violin', 'D', 'dorian', { lo: 62, hi: 78, rhythm: [[0, 3], [3, 3]], vel: 0.36 }),
    frame: (_c, a, len, put, w) => {
      put('kit', KIT.frame, a, 2, 0.56);
      if (len >= 6) put('kit', KIT.frameMute, a + 2, 1, 0.28);
      if (len >= 6) put('kit', KIT.frame2, a + 4, 1.5, 0.4);
      if (len >= 6 && w.bar === w.bars - 1) put('kit', KIT.timp, a + 4, 2, 0.36);
    },
    tamb: (_c, a, len, put, w) => {
      if (len >= 6) put('kit', KIT.tamb, a + 2, 1, 0.14 + w.rnd() * 0.04);
      if (len >= 6 && w.bar % 2 === 1) put('kit', KIT.tambShake, a + 4, 1.5, 0.12);
    },
    harpEnd: harpRing,
    hornEnd: hornCallPart([{ at: 0, dur: 6, vel: 0.5, addFifth: true }]),
    timpEnd: (_c, a, _len, put) => put('kit', KIT.timpLow, a, 5, 0.5),
  }),
};

// ---------------------------------------------------------------------------
// 8. The Gilded Wager (arena): clever E Dorian 6/8 gambit (88 BPM dotted-quarter)
// ---------------------------------------------------------------------------

const wagerChordsA = romanBars('E', ['i', 'IV', 'i', 'bVII', 'i', 'IV', 'bVII:3 V:3', 'i']);
const wagerChordsB = romanBars('E', ['bIII', 'bVII', 'IV', 'i', 'bIII', 'IV', 'V7', 'i']);

const wagerTuneA: MotifStep[][] = [
  [[0, 2, true], [2, 1], [4, 2, true], [3, 1]],
  [[5, 2, true], [4, 1], [2, 3]],
  [[0, 1], [2, 1], [4, 1], [6, 2, true], [4, 1]],
  [[3, 2], [2, 1], [1, 3]],
  [[0, 2, true], [4, 1], [7, 2, true], [6, 1]],
  [[5, 2, true], [3, 1], [2, 2], [4, 1]],
  [[3, 2], [1, 1], [4, 2], [1, 1]],
  [[0, 5, true], ['r', 1]],
];

const wagerTuneB: MotifStep[][] = [
  [[2, 2, true], [4, 1], [6, 2, true], [4, 1]],
  [[6, 2, true], [5, 1], [3, 3]],
  [[5, 2, true], [4, 1], [2, 2], [3, 1]],
  [[4, 3, true], [2, 2], [0, 1]],
  [[2, 1], [4, 1], [6, 1], [7, 2, true], [5, 1]],
  [[5, 2, true], [4, 1], [3, 2], [2, 1]],
  [[4, 3, true], [2, 2], [1, 1]],
  [[0, 5, true], ['r', 1]],
];

const gildedWager: Piece = {
  id: 'gilded-wager',
  title: 'The Gilded Wager',
  scene: 'arena',
  unit: 60 / 88 / 3,
  bar: 6,
  sections: {
    intro: { chords: romanBars('E', ['i', 'IV', 'bVII', 'i']) },
    A: {
      chords: wagerChordsA,
      tune: realizeMotifs('E4', 'dorian', wagerTuneA, { minMidi: 62, maxMidi: 84 }),
    },
    B: {
      chords: wagerChordsB,
      tune: realizeMotifs('E4', 'dorian', wagerTuneB, { minMidi: 62, maxMidi: 86 }),
    },
    end: { chords: romanBars('E', ['i', 'i']) },
  },
  form: [
    { s: 'intro', parts: ['ost', 'harp'], dyn: 0.76 },
    { s: 'A', lead: 'flute', parts: ['ost', 'harp', 'frame'], dyn: 0.84 },
    { s: 'A', lead: 'violin', harmony: 'flute', parts: ['ost', 'strum', 'harp', 'frame', 'tamb'], dyn: 0.9 },
    { s: 'B', lead: 'violin', parts: ['ost', 'harp', 'horn', 'pad', 'frame'], dyn: 0.92 },
    { s: 'B', lead: 'flute', harmony: 'violin', parts: ['ost', 'strum', 'harp', 'horn', 'frame', 'tamb'], dyn: 0.96 },
    { s: 'A', lead: 'recorder', harmony: 'violin', parts: ['ost', 'strum', 'harp', 'frame', 'tamb'], dyn: 0.98 },
    { s: 'end', parts: ['harpEnd', 'ostEnd', 'frameEnd'], dyn: 0.88 },
  ],
  parts: () => ({
    ost: ostinatoPart([0, -1, 7, 12, -1, 7], [0.74, 0, 0.48, 0.62, 0, 0.45], { lo: 40, dur: 1.0 }),
    harp: arpeggioHarpPart({ bassLo: 40, lo: 55, hi: 76, pattern: [0, 2, 4, 1, 3, 2], vel: 0.5, noteLen: 1.8 }),
    strum: rhythmicStrumPart([
      { at: 0, dur: 2.0, vel: 0.42 },
      { at: 3, dur: 2.0, vel: 0.36 },
    ]),
    pad: makeStrings(64, 78, 0.24),
    horn: hornCallPart([{ at: 0, dur: 5, vel: 0.42, addFifth: true }]),
    frame: (_c, a, len, put, w) => {
      put('kit', KIT.frame, a, 2, 0.58);
      if (len >= 6) put('kit', KIT.frame2, a + 3, 2, 0.44);
      if (len >= 6 && w.bar % 2 === 1) put('kit', KIT.frameMute, a + 5, 1, 0.28);
    },
    tamb: (_c, a, len, put, w) => {
      for (const u of [2, 5]) if (u < len) put('kit', KIT.tamb, a + u, 1, 0.13 + w.rnd() * 0.04);
      if (w.bar % 4 === 3 && len >= 6) put('kit', KIT.tambShake, a + 3, 2, 0.14);
    },
    harpEnd: harpRing,
    ostEnd: (c, a, _len, put) => put('celloPizz', at(c.bass, 40), a, 2, 0.78),
    frameEnd: (_c, a, _len, put) => put('kit', KIT.frame, a, 4, 0.55),
  }),
};

// ---------------------------------------------------------------------------
// 9. March of the Anvil (match): heroic E minor 4/4 battle march (108 BPM)
// ---------------------------------------------------------------------------

const anvilChordsA = romanBars('E', ['i', 'i', 'bVI', 'bVII', 'i', 'bVI', 'iv:4 V:4', 'i']);
const anvilChordsB = romanBars('E', ['bVI', 'bVII', 'i', 'bIII', 'iv', 'bVI', 'V', 'V7']);

const anvilTuneA: MotifStep[][] = [
  [[0, 3, true], [0, 1], [2, 2], [4, 2, true]],
  [[4, 4], [3, 2], [2, 2]],
  [[5, 3, true], [4, 1], [2, 2], [5, 2]],
  [[6, 4, true], [4, 2], [3, 2]],
  [[4, 3, true], [5, 1], [7, 2, true], [6, 2]],
  [[5, 4, true], [4, 2], [2, 2]],
  [[3, 2, true], [2, 2], [1, 2], [4, 2]],
  [[0, 6, true], ['r', 2]],
];

const anvilTuneB: MotifStep[][] = [
  [[5, 4, true], [7, 2], [6, 2]],
  [[6, 3, true], [5, 1], [4, 4]],
  [[4, 2, true], [5, 2], [7, 4, true]],
  [[6, 3, true], [4, 1], [2, 4]],
  [[3, 2, true], [4, 2], [5, 4, true]],
  [[5, 3, true], [4, 1], [2, 4]],
  [[4, 4, true], [6, 2], [4, 2]],
  [[4, 6, true], ['r', 2]],
];

const ironMarch: Piece = {
  id: 'iron-march',
  title: 'March of the Anvil',
  scene: 'match',
  unit: 60 / 108 / 2,
  bar: 8,
  sections: {
    intro: { chords: romanBars('E', ['i', 'i', 'bVI', 'V']) },
    A: {
      chords: anvilChordsA,
      tune: realizeMotifs('E4', 'minor', anvilTuneA, { minMidi: 60, maxMidi: 84 }),
    },
    B: {
      chords: anvilChordsB,
      tune: realizeMotifs('E4', 'minor', anvilTuneB, { minMidi: 60, maxMidi: 86 }),
    },
    bridge: { chords: romanBars('E', ['bVI', 'bVII', 'iv', 'V']) },
    end: { chords: romanBars('E', ['i', 'i']) },
  },
  form: [
    { s: 'intro', parts: ['ost', 'drum', 'pad'], dyn: 0.78 },
    { s: 'A', lead: 'horn', octave: -1, parts: ['ost', 'low', 'drum'], dyn: 0.84 },
    { s: 'A', lead: 'vlnEns', harmony: 'violin', parts: ['ost', 'low', 'horn', 'drum', 'more'], dyn: 0.9 },
    { s: 'B', lead: 'violin', harmony: 'vlnEns', parts: ['ost', 'horn', 'harp', 'drum', 'more'], dyn: 0.94 },
    { s: 'bridge', parts: ['ost', 'pad', 'build'], dyn: 0.86 },
    { s: 'A', lead: 'violin', harmony: 'flute', parts: ['ost', 'low', 'horn', 'pad', 'drum', 'more', 'descant'], dyn: 0.96 },
    { s: 'B', lead: 'vlnEns', harmony: 'violin', parts: ['ost', 'low', 'horn', 'harp', 'drum', 'more'], dyn: 1 },
    { s: 'end', parts: ['ostEnd', 'hornEnd', 'timpEnd', 'padEnd'], dyn: 0.9 },
  ],
  parts: () => ({
    ost: ostinatoPart([0, 0, 7, 0, 0, 7, 12, 7], [0.8, 0.44, 0.56, 0.44, 0.72, 0.5, 0.64, 0.52], { lo: 40, dur: 0.9 }),
    low: celloDrone(0.38, 36),
    pad: makeStrings(60, 76, 0.28),
    horn: hornCallPart([
      { at: 0, dur: 3, vel: 0.46, addFifth: true },
      { at: 4, dur: 3.5, vel: 0.4, addFifth: true },
    ]),
    harp: arpeggioHarpPart({ bassLo: 40, lo: 55, hi: 79, pattern: [-1, 2, -1, 3, -1, 4, -1, 3], vel: 0.36, noteLen: 1.5 }),
    descant: descantPart('flute', 'E', 'minor', { lo: 67, hi: 84, rhythm: [[0, 4], [4, 2], [6, 2]], vel: 0.4 }),
    drum: (_c, a, len, put, w) => {
      put('kit', KIT.frame, a, 2, 0.64);
      if (len >= 8) put('kit', KIT.frameMute, a + 2, 1, 0.32);
      if (len >= 8) put('kit', KIT.frame2, a + 4, 2, 0.56);
      if (len >= 8) put('kit', KIT.frameMute2, a + 6, 1, 0.36);
      if (w.bar % 4 === 3 && len >= 8) {
        put('kit', KIT.frame, a + 7, 1, 0.5);
      }
    },
    more: (_c, a, len, put, w) => {
      put('kitX', KIT.bdrum, a, 3, 0.68);
      if (len >= 8) put('kitX', KIT.timp, a + 4, 2.5, 0.48);
      if (w.bar % 2 === 1 && len >= 8) put('kitX', KIT.bdrum, a + 6, 2, 0.52);
      if (w.bar % 4 === 3 && len >= 8) {
        put('kitX', KIT.timp, a + 5, 1, 0.46);
        put('kitX', KIT.timp, a + 6, 1, 0.54);
        put('kitX', KIT.timp, a + 7, 1, 0.62);
      }
    },
    build: (_c, a, len, put, w) => {
      const v = 0.38 + 0.13 * w.bar;
      put('kit', KIT.timpLow, a, 3, v);
      if (w.bar >= 2 && len >= 8) put('kit', KIT.timp, a + 4, 2, v * 0.9);
      if (w.bar === w.bars - 1 && len >= 8) {
        for (const u of [4, 5, 6, 7]) put('kit', KIT.timp, a + u, 1, Math.min(1, v * 0.85 + u * 0.03));
      }
    },
    ostEnd: (c, a, _len, put) => put('celloPizz', at(c.bass, 40), a, 2, 0.82),
    hornEnd: hornCallPart([{ at: 0, dur: 8, vel: 0.52, addFifth: true }]),
    timpEnd: (_c, a, _len, put) => put('kit', KIT.timpLow, a, 6, 0.66),
    padEnd: (c, a, _len, put) => voiceLead(c, null, 57, 74, 3).forEach((n) => put('vlnEns', n, a, 12, 0.34)),
  }),
};

// ---------------------------------------------------------------------------
// 10. Storm Over the Spire (match): urgent G minor 6/8 duel (82 BPM dotted-quarter)
// ---------------------------------------------------------------------------

const stormChordsA = romanBars('G', ['i', 'i', 'bVI', 'bVII', 'i', 'bVI', 'iv', 'V']);
const stormChordsB = romanBars('G', ['bIII', 'bVII', 'i', 'bVI', 'bIII', 'iv', 'V', 'V7']);

const stormTuneA: MotifStep[][] = [
  [[0, 2, true], [1, 1], [2, 2, true], [4, 1]],
  [[4, 3, true], [3, 2], [2, 1]],
  [[5, 2, true], [4, 1], [2, 2], [0, 1]],
  [[3, 4, true], [1, 2]],
  [[4, 2, true], [5, 1], [6, 2, true], [4, 1]],
  [[5, 3, true], [4, 2], [2, 1]],
  [[3, 2, true], [5, 1], [4, 2], [2, 1]],
  [[4, 5, true], ['r', 1]],
];

const stormTuneB: MotifStep[][] = [
  [[6, 3, true], [5, 1], [4, 2]],
  [[3, 3, true], [4, 2], [6, 1]],
  [[7, 3, true], [6, 1], [5, 2]],
  [[5, 4, true], [4, 2]],
  [[2, 2, true], [4, 1], [6, 3, true]],
  [[5, 2, true], [3, 1], [2, 3]],
  [[4, 3, true], [2, 2], [1, 1]],
  [[4, 5, true], ['r', 1]],
];

const stormSpire: Piece = {
  id: 'storm-over-spire',
  title: 'Storm Over the Spire',
  scene: 'match',
  unit: 60 / 82 / 3,
  bar: 6,
  sections: {
    intro: { chords: romanBars('G', ['i', 'i', 'bVI', 'V']) },
    A: {
      chords: stormChordsA,
      tune: realizeMotifs('G4', 'minor', stormTuneA, { minMidi: 60, maxMidi: 86 }),
    },
    B: {
      chords: stormChordsB,
      tune: realizeMotifs('G4', 'minor', stormTuneB, { minMidi: 60, maxMidi: 86 }),
    },
    end: { chords: romanBars('G', ['i', 'i']) },
  },
  form: [
    { s: 'intro', parts: ['harp', 'ost', 'low'], dyn: 0.76 },
    { s: 'A', lead: 'violin', parts: ['harp', 'ost', 'drum'], dyn: 0.84 },
    { s: 'A', lead: 'vlnEns', harmony: 'violin', parts: ['harp', 'ost', 'low', 'horn', 'drum', 'more'], dyn: 0.9 },
    { s: 'B', lead: 'flute', harmony: 'violin', parts: ['harp', 'ost', 'pad', 'horn', 'drum', 'more'], dyn: 0.94 },
    { s: 'A', lead: 'horn', octave: -1, parts: ['harp', 'ost', 'pad', 'drum', 'more'], dyn: 0.9 },
    { s: 'B', lead: 'violin', harmony: 'vlnEns', parts: ['harp', 'ost', 'low', 'horn', 'drum', 'more', 'descant'], dyn: 1 },
    { s: 'end', parts: ['harpEnd', 'timpEnd', 'padEnd'], dyn: 0.88 },
  ],
  parts: () => ({
    // Galloping 6/8 cello ostinato + swirling harp arpeggio
    ost: ostinatoPart([0, 0, 7, 12, 7, 0], [0.76, 0.44, 0.52, 0.66, 0.5, 0.44], { lo: 38, dur: 0.9 }),
    harp: arpeggioHarpPart({ bassLo: 38, lo: 55, hi: 79, pattern: [0, 2, 3, 4, 3, 2], vel: 0.46, noteLen: 1.8 }),
    low: celloDrone(0.38, 36),
    pad: makeStrings(62, 77, 0.28),
    horn: hornCallPart([{ at: 0, dur: 5, vel: 0.44, addFifth: true }]),
    descant: descantPart('flute', 'G', 'minor', { lo: 67, hi: 84, rhythm: [[0, 3], [3, 3]], vel: 0.4 }),
    drum: (_c, a, len, put, w) => {
      put('kit', KIT.frame, a, 2, 0.6);
      if (len >= 6) put('kit', KIT.frame2, a + 3, 2, 0.48);
      if (len >= 6 && w.bar % 2 === 1) put('kit', KIT.frameMute, a + 5, 1, 0.3);
    },
    more: (_c, a, len, put, w) => {
      put('kitX', KIT.bdrum, a, 3, 0.65);
      if (len >= 6) put('kitX', KIT.timp, a + 3, 2, 0.48);
      if (w.bar % 4 === 3 && len >= 6) {
        put('kitX', KIT.timp, a + 4, 1, 0.5);
        put('kitX', KIT.timp, a + 5, 1, 0.6);
      }
    },
    harpEnd: harpRing,
    timpEnd: (_c, a, _len, put) => put('kit', KIT.timpLow, a, 6, 0.64),
    padEnd: (c, a, _len, put) => voiceLead(c, null, 58, 74, 3).forEach((n) => put('vlnEns', n, a, 12, 0.34)),
  }),
};

export const COMPOSED_PIECES: Piece[] = [
  copperReel,
  amberDusk,
  hallOfKeys,
  gildedWager,
  ironMarch,
  stormSpire,
];
