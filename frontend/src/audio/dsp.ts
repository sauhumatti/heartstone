// Small signal-processing toolkit. Everything here is plain arithmetic on
// Float32Arrays, so the game's sounds can be built (and tested) without a browser.
export type Buf = Float32Array;

const TAU = Math.PI * 2;

/** Deterministic random numbers: the same seed always gives the same sound. */
export function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function silence(sr: number, seconds: number): Buf {
  return new Float32Array(Math.max(1, Math.round(sr * seconds)));
}

export function white(sr: number, seconds: number, rand: () => number): Buf {
  const out = silence(sr, seconds);
  for (let i = 0; i < out.length; i++) out[i] = rand() * 2 - 1;
  return out;
}

/** Noise with more weight in the lows (falls 3 dB per octave): softer, more like air or paper. */
export function pink(sr: number, seconds: number, rand: () => number): Buf {
  const out = silence(sr, seconds);
  let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
  for (let i = 0; i < out.length; i++) {
    const w = rand() * 2 - 1;
    b0 = 0.99886 * b0 + w * 0.0555179;
    b1 = 0.99332 * b1 + w * 0.0750759;
    b2 = 0.969 * b2 + w * 0.153852;
    b3 = 0.8665 * b3 + w * 0.3104856;
    b4 = 0.55 * b4 + w * 0.5329522;
    b5 = -0.7616 * b5 - w * 0.016898;
    out[i] = b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362;
    b6 = w * 0.115926;
  }
  // Same peak level as white noise, so the two can be swapped in a recipe.
  let m = 0;
  for (let i = 0; i < out.length; i++) m = Math.max(m, Math.abs(out[i]));
  for (let i = 0; i < out.length; i++) out[i] /= m || 1;
  return out;
}

type Curve = number | ((t: number) => number);
const at = (c: Curve, t: number) => (typeof c === 'number' ? c : c(t));

/** State-variable filter whose cutoff may move over time (t in seconds). */
export function filter(x: Buf, sr: number, mode: 'lp' | 'bp' | 'hp', cutoff: Curve, q = 0.707): Buf {
  const out = new Float32Array(x.length);
  let ic1 = 0;
  let ic2 = 0;
  let g = 0, k = 1 / q, a1 = 0, a2 = 0, a3 = 0;
  for (let i = 0; i < x.length; i++) {
    if ((i & 15) === 0) {
      const fc = Math.min(sr * 0.45, Math.max(20, at(cutoff, i / sr)));
      g = Math.tan((Math.PI * fc) / sr);
      a1 = 1 / (1 + g * (g + k));
      a2 = g * a1;
      a3 = g * a2;
    }
    const v3 = x[i] - ic2;
    const v1 = a1 * ic1 + a2 * v3;
    const v2 = ic2 + a2 * ic1 + a3 * v3;
    ic1 = 2 * v1 - ic1;
    ic2 = 2 * v2 - ic2;
    out[i] = mode === 'lp' ? v2 : mode === 'bp' ? v1 : x[i] - k * v1 - v2;
  }
  return out;
}

/** Multiply by a curve of time. */
export function shape(x: Buf, sr: number, gain: (t: number) => number): Buf {
  const out = new Float32Array(x.length);
  for (let i = 0; i < x.length; i++) out[i] = x[i] * gain(i / sr);
  return out;
}

/** Rise in `attack` seconds, then fall away exponentially (reaching -60 dB after `t60`). */
export function pluckEnv(attack: number, t60: number): (t: number) => number {
  const r = Math.log(1000) / Math.max(0.001, t60);
  return (t) => (t < attack ? t / attack : Math.exp(-r * (t - attack)));
}

/** Rise, hold, fall: for swells and breaths. */
export function swellEnv(attack: number, hold: number, release: number): (t: number) => number {
  return (t) => {
    if (t < attack) return Math.sin((t / attack) * Math.PI * 0.5) ** 2;
    if (t < attack + hold) return 1;
    const u = (t - attack - hold) / release;
    return u >= 1 ? 0 : Math.cos(u * Math.PI * 0.5) ** 2;
  };
}

export interface Partial {
  /** Frequency in Hz. */
  f: number;
  /** Level. */
  a: number;
  /** Seconds until it has faded by 60 dB. */
  t60: number;
}

/** A struck object: a sum of ringing partials. Bells, wood, metal and glass differ only in the list. */
export function modal(sr: number, seconds: number, partials: Partial[], attack = 0.0015): Buf {
  const out = silence(sr, seconds);
  for (const p of partials) {
    if (p.f >= sr * 0.47) continue;
    const r = Math.log(1000) / p.t60;
    const w = (TAU * p.f) / sr;
    for (let i = 0; i < out.length; i++) {
      const t = i / sr;
      out[i] += p.a * Math.exp(-r * t) * Math.sin(w * i);
    }
  }
  const n = Math.max(1, Math.round(attack * sr));
  for (let i = 0; i < n && i < out.length; i++) out[i] *= i / n;
  return out;
}

/** A sustained, slightly wavering tone made of harmonics: closer to a voice or a bowed glass than to a beep. */
export function sing(sr: number, seconds: number, f: number, harmonics: number[], vibratoHz = 5, depth = 0.004, seed = 1): Buf {
  const out = silence(sr, seconds);
  const rand = rng(seed);
  const phases = harmonics.map(() => rand() * TAU);
  let wobble = 0;
  let phase = 0;
  for (let i = 0; i < out.length; i++) {
    const t = i / sr;
    // the vibrato comes in after the note has started, as a singer's does, and is never quite regular
    wobble += (rand() - 0.5) * 0.0004;
    wobble *= 0.9995;
    const vib = 1 + Math.min(1, t / 0.25) * depth * Math.sin(TAU * vibratoHz * t) + wobble;
    phase += (TAU * f * vib) / sr;
    let s = 0;
    for (let h = 0; h < harmonics.length; h++) s += harmonics[h] * Math.sin(phase * (h + 1) + phases[h]);
    out[i] = s;
  }
  return out;
}

/** Many tiny struck grains scattered in time: debris, ice, coins. `when` gives each grain's start. */
export function grains(sr: number, seconds: number, count: number, rand: () => number, grain: (i: number) => { buf: Buf; at: number; gain: number }): Buf {
  const layers = [{ buf: silence(sr, seconds) } as { buf: Buf; at?: number; gain?: number }];
  for (let i = 0; i < count; i++) layers.push(grain(i));
  void rand;
  return mix(sr, layers).slice(0, Math.round(sr * seconds));
}

/** A sine whose pitch glides from f0 to f1: the body of a thud or a drum. */
export function glide(sr: number, seconds: number, f0: number, f1: number, bend: number): Buf {
  const out = silence(sr, seconds);
  let phase = 0;
  for (let i = 0; i < out.length; i++) {
    const t = i / sr;
    const f = f1 + (f0 - f1) * Math.exp(-t / bend);
    phase += (TAU * f) / sr;
    out[i] = Math.sin(phase);
  }
  return out;
}

/** A plucked string (Karplus-Strong with a tuned delay). `bright` 0..1, `t60` is the ring time. */
export function string(sr: number, seconds: number, f: number, opts: { bright?: number; t60?: number; pick?: number; seed?: number } = {}): Buf {
  const { bright = 0.5, t60 = 2.2, pick = 0.18, seed = 1 } = opts;
  const out = silence(sr, seconds);
  const period = sr / f;
  const n = Math.floor(period);
  const frac = period - n;
  const line = new Float32Array(n + 2);
  const rand = rng(seed);
  // The pluck: a short burst of noise, darker for a soft touch.
  let lp = 0;
  const colour = 0.15 + 0.8 * bright;
  for (let i = 0; i < n; i++) {
    lp += colour * (rand() * 2 - 1 - lp);
    line[i] = lp;
  }
  // Where the string is plucked removes some harmonics.
  const off = Math.max(1, Math.round(n * pick));
  const excite = line.slice(0, n);
  for (let i = 0; i < n; i++) line[i] = excite[i] - 0.9 * excite[(i + off) % n];
  // Loss per trip round the string, chosen so the note rings for t60 seconds.
  const loss = Math.pow(10, -3 / (t60 * f));
  const damp = 0.5 - 0.42 * bright * 0.5; // averaging filter weight: lower = brighter
  let idx = 0;
  let prev = 0;
  let prevOut = 0;
  for (let i = 0; i < out.length; i++) {
    const a = line[idx];
    const b = line[(idx + 1) % n];
    const cur = a * (1 - frac) + b * frac;
    const y = loss * ((1 - damp) * cur + damp * prev);
    prev = cur;
    out[i] = cur;
    // a touch of the body: remove rumble
    line[idx] = y;
    idx = (idx + 1) % n;
    prevOut = cur;
  }
  void prevOut;
  return fadeOut(filter(out, sr, 'hp', 60, 0.7), sr, 0.03);
}

/** Sparse random ticks: embers, frost forming, dust. `rate` is ticks per second. */
export function crackle(sr: number, seconds: number, rate: Curve, rand: () => number): Buf {
  const out = silence(sr, seconds);
  for (let i = 0; i < out.length; i++) {
    if (rand() < at(rate, i / sr) / sr) out[i] = (rand() * 2 - 1) * (0.4 + 0.6 * rand());
  }
  return out;
}

export function gain(x: Buf, g: number): Buf {
  const out = new Float32Array(x.length);
  for (let i = 0; i < x.length; i++) out[i] = x[i] * g;
  return out;
}

/** Gentle saturation: rounds off peaks and adds warmth. */
export function warm(x: Buf, drive: number): Buf {
  const out = new Float32Array(x.length);
  const norm = Math.tanh(drive);
  for (let i = 0; i < x.length; i++) out[i] = Math.tanh(x[i] * drive) / norm;
  return out;
}

/** Sum several sounds; each may start later (`at`, seconds) and be scaled. */
export function mix(sr: number, layers: { buf: Buf; at?: number; gain?: number }[]): Buf {
  let len = 1;
  for (const l of layers) len = Math.max(len, Math.round((l.at || 0) * sr) + l.buf.length);
  const out = new Float32Array(len);
  for (const l of layers) {
    const o = Math.round((l.at || 0) * sr);
    const g = l.gain ?? 1;
    for (let i = 0; i < l.buf.length; i++) out[o + i] += l.buf[i] * g;
  }
  return out;
}

export function reverse(x: Buf): Buf {
  const out = new Float32Array(x.length);
  for (let i = 0; i < x.length; i++) out[i] = x[x.length - 1 - i];
  return out;
}

export function fadeOut(x: Buf, sr: number, seconds: number): Buf {
  const out = new Float32Array(x);
  const n = Math.min(out.length, Math.round(seconds * sr));
  for (let i = 0; i < n; i++) out[out.length - 1 - i] *= i / n;
  return out;
}

export function fadeIn(x: Buf, sr: number, seconds: number): Buf {
  const out = new Float32Array(x);
  const n = Math.min(out.length, Math.round(seconds * sr));
  for (let i = 0; i < n; i++) out[i] *= i / n;
  return out;
}

/** Play back at a different speed (and pitch) by linear interpolation. */
export function resample(x: Buf, rate: number): Buf {
  const out = new Float32Array(Math.max(1, Math.floor(x.length / rate)));
  for (let i = 0; i < out.length; i++) {
    const p = i * rate;
    const j = Math.floor(p);
    const f = p - j;
    out[i] = (x[j] || 0) * (1 - f) + (x[j + 1] || 0) * f;
  }
  return out;
}

export function peak(x: Buf): number {
  let m = 0;
  for (let i = 0; i < x.length; i++) m = Math.max(m, Math.abs(x[i]));
  return m;
}

/** Scale so the loudest sample sits at `level` and remove any constant offset. */
export function normalize(x: Buf, level = 0.9): Buf {
  let mean = 0;
  for (let i = 0; i < x.length; i++) mean += x[i];
  mean /= x.length;
  const out = new Float32Array(x.length);
  for (let i = 0; i < x.length; i++) out[i] = x[i] - mean;
  const p = peak(out) || 1;
  for (let i = 0; i < out.length; i++) out[i] *= level / p;
  return out;
}

/** Cut silence off the end so buffers are no longer than they sound. */
export function trim(x: Buf, sr: number, floor = 0.0008): Buf {
  let end = x.length - 1;
  while (end > 0 && Math.abs(x[end]) < floor) end--;
  return fadeOut(x.slice(0, Math.min(x.length, end + Math.round(sr * 0.01))), sr, 0.008);
}

/** A room to put everything in: decaying noise, darker as it fades. Returns left and right. */
export function roomImpulse(sr: number, seconds: number, seed: number): [Buf, Buf] {
  const make = (s: number): Buf => {
    const rand = rng(s);
    const n = white(sr, seconds, rand);
    const decay = shape(n, sr, (t) => Math.exp(-t * (6.9 / seconds)) * (t < 0.004 ? t / 0.004 : 1));
    // High frequencies die first, as in a real room with soft walls.
    const dark = filter(decay, sr, 'lp', (t) => 9000 * Math.exp(-t * 2.2) + 900, 0.6);
    return normalize(filter(dark, sr, 'hp', 180, 0.7), 0.5);
  };
  return [make(seed), make(seed + 101)];
}
