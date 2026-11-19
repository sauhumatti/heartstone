// The sound bank: every raw sound in the game, built from scratch when first
// needed. The palette is a night table by lantern light: paper and card, wood,
// a small bronze bell, glass, a frame drum, air. No recordings, no beeps.
import {
  type Buf,
  crackle,
  fadeIn,
  fadeOut,
  filter,
  gain,
  glide,
  grains,
  mix,
  modal,
  normalize,
  pink,
  pluckEnv,
  reverse,
  rng,
  shape,
  sing,
  string,
  swellEnv,
  trim,
  warm,
  white,
} from './dsp';

interface Recipe {
  /** How many different takes exist, so a repeated sound never repeats exactly. */
  variants: number;
  make: (sr: number, v: number) => Buf;
}

/** Bring a layer to full level before mixing, so the gains in a recipe mean what they say. */
const unit = (b: Buf): Buf => normalize(b, 1);

/** The bell's own pitch; other notes are made by playing it faster or slower. */
export const CHIME_HZ = 880;
export const GLOW_HZ = 440;

const bell = (sr: number, v: number): Buf => {
  const f = CHIME_HZ;
  const dt = 1 + (v - 1) * 0.0015; // each take is tuned a hair differently
  const partial = (ratio: number, a: number, t60: number) => [
    { f: f * ratio * dt, a, t60 },
    // a close twin makes each partial beat slowly, as cast bronze does
    { f: f * ratio * dt * 1.0022, a: a * 0.5, t60: t60 * 0.9 },
  ];
  const struck = modal(sr, 2.0, [
    { f: f * 0.5, a: 0.2, t60: 1.9 },
    ...partial(1, 1, 1.7),
    ...partial(2, 0.45, 1.05),
    ...partial(2.76, 0.34, 0.8),
    ...partial(3.0, 0.16, 0.7),
    ...partial(4.07, 0.16, 0.45),
    ...partial(5.4, 0.1, 0.3),
    ...partial(6.8, 0.06, 0.2),
  ]);
  const tap = unit(shape(filter(white(sr, 0.03, rng(40 + v)), sr, 'bp', 3600, 1.0), sr, pluckEnv(0.0006, 0.014)));
  return mix(sr, [{ buf: unit(struck) }, { buf: tap, gain: 0.2 }]);
};

export const RECIPES: Record<string, Recipe> = {
  // ---- paper and card ----
  /** A card moving through the air. */
  swish: {
    variants: 4,
    make: (sr, v) => {
      const n = pink(sr, 0.22, rng(11 + v));
      const top = 4600 + v * 350;
      const swept = filter(n, sr, 'bp', (t) => 1700 + (top - 1700) * Math.sin(Math.min(1, t / 0.17) * Math.PI), 0.85);
      return filter(shape(swept, sr, swellEnv(0.05, 0.012, 0.13)), sr, 'lp', 7000, 0.7);
    },
  },
  /** A card's edge snapping against a thumb. */
  flick: {
    variants: 4,
    make: (sr, v) => {
      const noise = filter(filter(white(sr, 0.07, rng(21 + v)), sr, 'hp', 1300 + v * 150, 0.8), sr, 'lp', 6500, 0.7);
      const snap = shape(noise, sr, pluckEnv(0.0008, 0.045));
      const paper = modal(sr, 0.07, [
        { f: 1350 + v * 70, a: 0.5, t60: 0.035 },
        { f: 2280 + v * 90, a: 0.3, t60: 0.025 },
      ]);
      return mix(sr, [{ buf: snap }, { buf: paper, gain: 0.7 }]);
    },
  },
  /** A card landing flat on felt. */
  slap: {
    variants: 3,
    make: (sr, v) => {
      const body = shape(glide(sr, 0.16, 230 + v * 14, 150, 0.02), sr, pluckEnv(0.002, 0.11));
      const paper = unit(shape(filter(pink(sr, 0.1, rng(31 + v)), sr, 'bp', 1500, 0.6), sr, pluckEnv(0.001, 0.07)));
      return filter(mix(sr, [{ buf: body, gain: 0.4 }, { buf: paper, gain: 1 }]), sr, 'lp', 5200, 0.7);
    },
  },

  // ---- wood ----
  /** The smallest wooden tick: buttons. */
  tick: {
    variants: 3,
    make: (sr, v) => {
      const wood = modal(sr, 0.08, [
        { f: 640 + v * 30, a: 0.8, t60: 0.05 },
        { f: 1180 + v * 60, a: 1, t60: 0.04 },
        { f: 2210 + v * 80, a: 0.4, t60: 0.022 },
      ]);
      const tap = unit(shape(filter(white(sr, 0.02, rng(45 + v)), sr, 'bp', 2600, 0.9), sr, pluckEnv(0.0005, 0.008)));
      return mix(sr, [{ buf: unit(wood) }, { buf: tap, gain: 0.3 }]);
    },
  },
  /** A knuckle on the table. */
  knock: {
    variants: 3,
    make: (sr, v) => {
      const wood = modal(
        sr,
        0.22,
        [
          { f: 186 + v * 9, a: 0.8, t60: 0.14 },
          { f: 296 + v * 14, a: 1, t60: 0.13 },
          { f: 571 + v * 20, a: 0.7, t60: 0.085 },
          { f: 1124, a: 0.35, t60: 0.05 },
          { f: 1850, a: 0.12, t60: 0.03 },
        ],
        0.003,
      );
      const skin = unit(shape(filter(pink(sr, 0.04, rng(51 + v)), sr, 'lp', 1800, 0.7), sr, pluckEnv(0.001, 0.02)));
      return mix(sr, [{ buf: unit(wood) }, { buf: skin, gain: 0.25 }]);
    },
  },
  /** Something heavy set down on the table. */
  thud: {
    variants: 3,
    make: (sr, v) => {
      const body = shape(glide(sr, 0.24, 138 + v * 8, 62, 0.035), sr, pluckEnv(0.003, 0.15));
      const dust = unit(shape(filter(pink(sr, 0.14, rng(61 + v)), sr, 'bp', 900, 0.6), sr, pluckEnv(0.002, 0.09)));
      const edge = unit(shape(filter(white(sr, 0.03, rng(65 + v)), sr, 'bp', 2700, 0.8), sr, pluckEnv(0.0005, 0.014)));
      const wood = modal(sr, 0.14, [
        { f: 243, a: 0.6, t60: 0.07 },
        { f: 488, a: 0.5, t60: 0.06 },
        { f: 905, a: 0.3, t60: 0.045 },
      ]);
      return warm(mix(sr, [{ buf: body, gain: 0.42 }, { buf: dust, gain: 0.9 }, { buf: unit(wood), gain: 0.6 }, { buf: edge, gain: 0.45 }]), 1.4);
    },
  },

  // ---- blows ----
  /** A blow landing: body and a short crack. */
  hit: {
    variants: 3,
    make: (sr, v) => {
      const body = shape(glide(sr, 0.18, 270 + v * 18, 88, 0.026), sr, pluckEnv(0.001, 0.12));
      const r = rng(71 + v);
      const smack = unit(shape(filter(pink(sr, 0.1, r), sr, 'bp', 880 + v * 70, 0.7), sr, pluckEnv(0.0008, 0.06)));
      const crack = unit(shape(filter(white(sr, 0.07, r), sr, 'bp', 2700 + v * 200, 0.8), sr, pluckEnv(0.0004, 0.035)));
      return warm(mix(sr, [{ buf: body, gain: 0.34 }, { buf: smack, gain: 0.9 }, { buf: crack, gain: 0.85 }]), 1.5);
    },
  },
  /** Metal meeting metal. */
  blade: {
    variants: 3,
    make: (sr, v) => {
      const base = 1480 + v * 130;
      const ratios = [1, 1.47, 2.09, 2.56, 3.14, 3.93, 4.71, 5.62];
      const ring = modal(
        sr,
        0.4,
        ratios.flatMap((r, i) => [
          { f: base * r, a: 0.8 / (1 + i * 0.22), t60: 0.3 / (1 + i * 0.3) },
          // a close twin of each partial makes the ring shimmer instead of whistle
          { f: base * r * 1.006, a: 0.4 / (1 + i * 0.22), t60: 0.24 / (1 + i * 0.3) },
        ]),
      );
      const scrape = unit(shape(filter(white(sr, 0.09, rng(81 + v)), sr, 'bp', 4800, 1.2), sr, pluckEnv(0.001, 0.055)));
      return filter(mix(sr, [{ buf: unit(ring), gain: 0.7 }, { buf: scrape, gain: 0.6 }]), sr, 'lp', 9500, 0.7);
    },
  },

  // ---- air ----
  /** Something flying past. */
  whoosh: {
    variants: 3,
    make: (sr, v) => {
      const r = rng(91 + v);
      const n = pink(sr, 0.4, r);
      const arc = (t: number) => Math.sin(Math.min(1, t / 0.36) * Math.PI);
      const body = filter(n, sr, 'bp', (t) => 260 + (1100 + v * 120) * arc(t), 1.1);
      const air = filter(n, sr, 'bp', (t) => 700 + 2600 * arc(t), 1.6);
      // turbulence: the level wavers slowly, as moving air does (slowly: fast wavering would sound like grit)
      const waver = unit(filter(white(sr, 0.4, r), sr, 'lp', 22, 0.7));
      const blend = mix(sr, [{ buf: unit(body) }, { buf: unit(air), gain: 0.4 }]);
      const moved = new Float32Array(blend.length);
      for (let i = 0; i < blend.length; i++) moved[i] = blend[i] * (1 + 0.3 * (waver[i] || 0));
      return filter(shape(moved, sr, swellEnv(0.13, 0.03, 0.22)), sr, 'lp', 6000, 0.7);
    },
  },
  /** A piece crumbling away: bits dropping on the table, then quiet. */
  fall: {
    variants: 2,
    make: (sr, v) => {
      const r = rng(101 + v);
      const bits = grains(sr, 0.5, 16, r, (i) => {
        const f = 420 + r() * 1700;
        return {
          buf: modal(sr, 0.08, [
            { f, a: 1, t60: 0.03 + r() * 0.04 },
            { f: f * 2.3, a: 0.4, t60: 0.02 },
          ]),
          at: 0.02 + Math.pow(i / 16, 1.6) * 0.38 + r() * 0.02,
          gain: (0.9 - (i / 16) * 0.6) * (0.5 + r() * 0.5),
        };
      });
      const dust = unit(shape(filter(pink(sr, 0.5, r), sr, 'bp', (t) => 1500 * Math.exp(-t * 4) + 380, 0.9), sr, pluckEnv(0.01, 0.38)));
      const settle = shape(filter(pink(sr, 0.2, r), sr, 'lp', 420, 0.7), sr, pluckEnv(0.004, 0.14));
      return mix(sr, [{ buf: unit(bits), gain: 0.8 }, { buf: dust, gain: 0.6 }, { buf: unit(settle), gain: 0.25 }]);
    },
  },

  // ---- bronze and glass ----
  /** The lantern bell. Pitched at CHIME_HZ. */
  chime: { variants: 3, make: bell },
  /** The bell heard backwards: something hidden, something arriving. */
  swell: {
    variants: 2,
    make: (sr, v) => {
      const b = bell(sr, v).slice(0, Math.round(sr * 0.62));
      return fadeOut(fadeIn(reverse(b), sr, 0.3), sr, 0.02);
    },
  },
  /** A pane breaking into pieces. */
  glass: {
    variants: 2,
    make: (sr, v) => {
      const r = rng(111 + v);
      const burst = unit(shape(filter(filter(white(sr, 0.12, r), sr, 'hp', 2400, 0.8), sr, 'lp', 9000, 0.7), sr, pluckEnv(0.0006, 0.07)));
      const shards = grains(sr, 0.5, 14, r, () => ({
        buf: modal(sr, 0.4, [{ f: 1900 + r() * 4700, a: 1, t60: 0.1 + r() * 0.28 }], 0.002),
        at: Math.pow(r(), 1.5) * 0.16,
        gain: 0.25 + r() * 0.35,
      }));
      return mix(sr, [{ buf: burst, gain: 0.55 }, { buf: unit(shards), gain: 0.8 }]);
    },
  },
  /** Ice taking hold: fine cracks gathering, then a clear ring. */
  frost: {
    variants: 2,
    make: (sr, v) => {
      const r = rng(121 + v);
      const cracks = grains(sr, 0.6, 22, r, (i) => {
        const f = 2600 + r() * 3600;
        return {
          buf: modal(sr, 0.07, [{ f, a: 1, t60: 0.025 + r() * 0.04 }], 0.0015),
          at: 0.42 * Math.pow(i / 22, 0.7) + r() * 0.015,
          gain: 0.25 + 0.5 * (i / 22) * r(),
        };
      });
      const ring = modal(
        sr,
        0.5,
        [
          { f: 2093 + v * 40, a: 1, t60: 0.42 },
          { f: 2101 + v * 40, a: 0.6, t60: 0.36 },
          { f: 3136, a: 0.5, t60: 0.3 },
          { f: 4186, a: 0.25, t60: 0.2 },
        ],
        0.004,
      );
      const hush = unit(shape(filter(pink(sr, 0.55, r), sr, 'bp', (t) => 1800 + 2600 * (t / 0.55), 1.4), sr, swellEnv(0.3, 0.02, 0.2)));
      return mix(sr, [{ buf: unit(cracks), gain: 0.6 }, { buf: unit(ring), gain: 0.5, at: 0.36 }, { buf: hush, gain: 0.22 }]);
    },
  },
  /** Embers: a card burning up. */
  ember: {
    variants: 2,
    make: (sr, v) => {
      const r = rng(131 + v);
      const pops = filter(crackle(sr, 0.75, (t) => 130 * Math.exp(-t * 2.4) + 14, r), sr, 'bp', 2300, 1.4);
      const roar = shape(filter(pink(sr, 0.75, r), sr, 'bp', (t) => 1500 * Math.exp(-t * 2) + 520, 0.6), sr, swellEnv(0.05, 0.1, 0.55));
      return mix(sr, [{ buf: pops, gain: 3 }, { buf: roar, gain: 0.5 }]);
    },
  },

  // ---- warmth ----
  /** A soft sung tone: mending, a blessing. Pitched at GLOW_HZ. */
  glow: {
    variants: 2,
    make: (sr, v) => {
      const f = GLOW_HZ;
      const env = swellEnv(0.11, 0.14, 0.6);
      // two nearly pure voices a few cents apart: round, not brassy
      const a = sing(sr, 0.9, f, [1, 0.22, 0.07, 0.02], 5.2, 0.004, 141 + v);
      const b = sing(sr, 0.9, f * 1.004, [1, 0.18, 0.05], 4.7, 0.004, 147 + v);
      const air = sing(sr, 0.9, f * 2.003, [0.5, 0.06], 5.6, 0.003, 151 + v);
      const voice = filter(mix(sr, [{ buf: a }, { buf: b, gain: 0.8 }, { buf: air, gain: 0.35 }]), sr, 'lp', 3200, 0.6);
      const breath = unit(filter(pink(sr, 0.9, rng(149 + v)), sr, 'bp', 2100, 1.0));
      return shape(mix(sr, [{ buf: unit(voice) }, { buf: breath, gain: 0.035 }]), sr, env);
    },
  },

  // ---- skin ----
  /** A frame drum, struck once. */
  drum: {
    variants: 2,
    make: (sr, v) => {
      const f = 72 + v * 4;
      const body = shape(glide(sr, 0.5, f * 1.8, f, 0.045), sr, pluckEnv(0.002, 0.3));
      const skin = modal(sr, 0.4, [
        { f: f * 1.59, a: 0.4, t60: 0.3 },
        { f: f * 2.14, a: 0.35, t60: 0.22 },
        { f: f * 2.65, a: 0.3, t60: 0.17 },
        { f: f * 3.6, a: 0.25, t60: 0.12 },
        { f: f * 4.9, a: 0.18, t60: 0.08 },
        // the "tok" of the hand on the rim: what a small speaker reproduces
        { f: 415, a: 0.5, t60: 0.07 },
        { f: 688, a: 0.3, t60: 0.05 },
      ]);
      const r = rng(151 + v);
      const palm = unit(shape(filter(pink(sr, 0.07, r), sr, 'bp', 1100, 0.6), sr, pluckEnv(0.001, 0.045)));
      const slap = unit(shape(filter(white(sr, 0.04, r), sr, 'bp', 3200, 0.8), sr, pluckEnv(0.0005, 0.02)));
      return warm(mix(sr, [{ buf: body, gain: 0.42 }, { buf: unit(skin), gain: 0.7 }, { buf: palm, gain: 0.75 }, { buf: slap, gain: 0.35 }]), 1.5);
    },
  },
};

const cache = new Map<string, Buf>();

/** One take of a sound at the given sample rate, built on first use. */
export function sample(name: string, sr: number, variant = 0): Buf {
  const recipe = RECIPES[name];
  if (!recipe) throw new Error(`unknown sound: ${name}`);
  const v = ((variant % recipe.variants) + recipe.variants) % recipe.variants;
  const key = `${name}:${v}:${sr}`;
  let buf = cache.get(key);
  if (!buf) {
    buf = trim(normalize(recipe.make(sr, v), 0.9), sr);
    cache.set(key, buf);
  }
  return buf;
}

/** MIDI note number to Hz. */
export function hz(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

/** A plucked string at an exact pitch: the music's main voice. */
export function pluckNote(sr: number, midi: number): Buf {
  const key = `pluck:${midi}:${sr}`;
  let buf = cache.get(key);
  if (!buf) {
    const f = hz(midi);
    // Higher strings are a little duller and die sooner, as on a real instrument.
    const height = Math.max(0, Math.min(1, (midi - 50) / 36));
    const len = 2.6 - height * 1.1;
    // two strings a few cents apart, as on a lute's paired course: fuller and less glassy than one
    const one = string(sr, len, f, { bright: 0.5 - height * 0.15, t60: 2.6 - height * 1.3, pick: 0.21, seed: midi });
    const two = string(sr, len, f * 1.0028, { bright: 0.42 - height * 0.12, t60: 2.3 - height * 1.2, pick: 0.27, seed: midi + 300 });
    const strings = mix(sr, [{ buf: one }, { buf: two, gain: 0.8, at: 0.004 }]);
    // the wooden body: it answers the pluck with a short low bloom
    const body = mix(sr, [
      { buf: filter(strings, sr, 'bp', 190, 1.6), gain: 0.5 },
      { buf: filter(strings, sr, 'bp', 410, 1.8), gain: 0.3 },
    ]);
    const soft = filter(mix(sr, [{ buf: strings }, { buf: body }]), sr, 'lp', 4600 - height * 1200, 0.6);
    // a rounded start instead of a hard click
    buf = trim(normalize(fadeIn(soft, sr, 0.003), 0.85), sr);
    cache.set(key, buf);
  }
  return buf;
}

export function variantsOf(name: string): number {
  return RECIPES[name]?.variants ?? 1;
}
