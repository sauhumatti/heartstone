// The score. Nothing is recorded and nothing loops: the music is composed as
// it plays, from a few rules, and it listens to the match. Plucked strings
// carry it: a low one spreads the chords, a higher one plays a short tune that
// returns, changed a little, over each new chord. A quiet organ-like bed sits
// underneath, a bell marks some of the changes, and a frame drum comes in when
// the other side is to move or a hero is in danger.
import { CHIME_HZ, hz } from './bank';
import type { Engine } from './engine';

export interface MusicState {
  scene: 'menu' | 'match' | 'off';
  /** In a match: is it the player's own turn? */
  myTurn: boolean;
  /** 0 = calm, 1 = a hero is about to fall. */
  danger: number;
}

interface Chord {
  /** Bass note, MIDI. */
  root: number;
  /** Pitch classes that belong to the chord (C = 0). */
  tones: number[];
}

// D Dorian: D E F G A B C. Minor, but with a raised sixth that keeps it from sounding sad.
const SCALE = [2, 4, 5, 7, 9, 11, 0];
const CHORDS: Record<string, Chord> = {
  Dm9: { root: 38, tones: [2, 5, 9, 0, 4] },
  Fmaj7: { root: 41, tones: [5, 9, 0, 4] },
  Cmaj7: { root: 36, tones: [0, 4, 7, 11] },
  G: { root: 43, tones: [7, 11, 2, 9] },
  Am7: { root: 45, tones: [9, 0, 4, 7] },
  Em7: { root: 40, tones: [4, 7, 11, 2] },
};
/** Every string note the score can ask for, so they can be built before the music needs them. */
export function scoreNotes(): number[] {
  const out: number[] = [];
  for (let n = 48; n <= 86; n++) if (SCALE.includes(n % 12)) out.push(n);
  return out;
}

const PROGRESSIONS: Record<'menu' | 'match', string[][]> = {
  menu: [
    ['Dm9', 'Fmaj7', 'Cmaj7', 'G'],
    ['Dm9', 'Am7', 'Fmaj7', 'Cmaj7'],
  ],
  match: [
    ['Dm9', 'Am7', 'Fmaj7', 'G'],
    ['Dm9', 'Cmaj7', 'G', 'Am7'],
    ['Fmaj7', 'G', 'Em7', 'Am7'],
  ],
};
/** Each chord lasts this many bars of four beats. */
const BARS_PER_CHORD = 2;
const SLOTS_PER_BAR = 8;
/** How likely each eighth note of a bar is to be played, before density. */
const WEIGHT = [1, 0.3, 0.55, 0.35, 0.8, 0.3, 0.6, 0.45];
/** A phrase of four bars breathes: busy, easing, busiest, resting. */
const PHRASE = [1, 0.8, 1.15, 0.45];

export class Music {
  private state: MusicState = { scene: 'off', myTurn: true, danger: 0 };
  private applied: MusicState = { ...this.state };
  private next = 0;
  private slot = 0;
  private progression: string[] = PROGRESSIONS.menu[0];
  private chordIndex = -1;
  private chord: Chord = CHORDS.Dm9;
  /** The tune: for each eighth note of two bars, a step on the chord's ladder of notes, or a rest. */
  private motif: (number | null)[] = [];
  private motifAge = 0;
  private padVoicing: number[] = [];
  private padBus: GainNode;
  private padFilter: BiquadFilterNode;
  private timer: number | null = null;
  private live: { stop: (when: number) => void }[] = [];

  constructor(
    private engine: Engine,
    private rand: () => number = Math.random,
  ) {
    const ctx = engine.ctx;
    this.padFilter = ctx.createBiquadFilter();
    this.padFilter.type = 'lowpass';
    this.padFilter.frequency.value = 1100;
    this.padFilter.Q.value = 0.4;
    this.padBus = engine.musicInput(0.5);
    this.padBus.gain.value = 0.68;
    this.padFilter.connect(this.padBus);
  }

  setState(next: Partial<MusicState>): void {
    this.state = { ...this.state, ...next };
  }

  get running(): boolean {
    return this.timer !== null;
  }

  /** Start composing in real time. */
  start(): void {
    if (this.timer !== null) return;
    this.next = this.engine.now + 0.12;
    this.slot = 0;
    this.chordIndex = -1;
    const tick = () => this.advance(this.engine.now + 0.75);
    tick();
    this.timer = window.setInterval(tick, 160);
  }

  /** Stop composing; what is sounding fades out. */
  stop(fade = 1.2): void {
    if (this.timer !== null) {
      window.clearInterval(this.timer);
      this.timer = null;
    }
    const when = this.engine.now;
    this.live.forEach((v) => v.stop(when + fade));
    this.live = [];
    this.padVoicing = [];
  }

  private tempo(): number {
    return this.applied.scene === 'menu' ? 58 : 70 + this.applied.danger * 8;
  }

  /** Write the music out up to the given time. Also used to render it offline. */
  advance(until: number): void {
    // After a pause (a hidden tab), carry on from now instead of catching up.
    if (this.next < this.engine.now - 0.25) this.next = this.engine.now + 0.1;
    while (this.next < until) {
      this.playSlot(this.next);
      this.next += 60 / this.tempo() / 2;
      this.slot++;
    }
  }

  private pick<T>(list: T[]): T {
    return list[Math.floor(this.rand() * list.length) % list.length];
  }

  private playSlot(t: number): void {
    const inBar = this.slot % SLOTS_PER_BAR;
    const bar = Math.floor(this.slot / SLOTS_PER_BAR);

    if (inBar === 0) {
      // Changes of mood wait for the bar line, so the music never lurches.
      const sceneChanged = this.applied.scene !== this.state.scene;
      this.applied = { ...this.state };
      this.shapePad(t);
      if (this.applied.scene === 'off') {
        this.live.forEach((v) => v.stop(t + 2));
        this.live = [];
        return;
      }
      if (sceneChanged || bar % BARS_PER_CHORD === 0) this.nextChord(t, sceneChanged);
    }
    if (this.applied.scene === 'off') return;

    const s = this.applied;
    const match = s.scene === 'match';
    const calmTurn = match && !s.myTurn;

    // --- the tune ---
    const barOfChord = bar % BARS_PER_CHORD;
    const step = this.motif[barOfChord * SLOTS_PER_BAR + inBar];
    const voices = match ? (s.myTurn ? 1 : 0.5) : 0.7;
    if (step !== null && step !== undefined && this.rand() < voices * (0.75 + 0.25 * PHRASE[bar % PHRASE.length])) {
      const ladder = this.ladder(calmTurn ? 55 : 62, calmTurn ? 76 : 86);
      const note = ladder[Math.max(0, Math.min(ladder.length - 1, step))];
      const accent = inBar === 0 ? 1 : inBar === 4 ? 0.88 : 0.6 + this.rand() * 0.2;
      this.engine.pluck(
        note,
        // played by a hand, not a clock: a little early or late, a little louder or softer
        { gain: (0.24 + this.rand() * 0.14) * accent, pan: 0.25 + (this.rand() - 0.5) * 0.3, room: 0.55, at: 0.025 + (this.rand() - 0.5) * 0.045 },
        t,
      );
    }

    // --- the accompaniment: the chord spread low, like a hand across a harp ---
    const spread = inBar === 0 || (inBar === 4 && (!calmTurn || this.rand() < 0.4));
    if (spread) {
      const low = this.ladder(48, 64);
      const count = inBar === 0 ? 3 : 2;
      const start = Math.floor(this.rand() * Math.max(1, low.length - count));
      for (let i = 0; i < count; i++) {
        const note = low[Math.min(low.length - 1, start + i)];
        this.engine.pluck(note, { gain: 0.13 + this.rand() * 0.07, pan: -0.35 + i * 0.12, room: 0.5, at: 0.01 + i * (0.05 + this.rand() * 0.05) }, t);
      }
    }

    // --- the bass: the root when the chord arrives, sometimes its fifth later ---
    if (inBar === 0 && barOfChord === 0) this.engine.pluck(this.chord.root + 12, { gain: 0.3, room: 0.25 }, t);
    else if (match && inBar === 4 && barOfChord === 1 && this.rand() < 0.5) this.engine.pluck(this.chord.root + 19, { gain: 0.2, room: 0.25 }, t);

    // --- the drum: waiting, and danger ---
    if (match) {
      const d = s.danger;
      const lag = this.rand() * 0.02;
      if (inBar === 0 && (calmTurn || d > 0.05)) this.engine.voice('drum', { gain: 0.14 + d * 0.2, rate: 0.92, room: 0.4, at: lag }, t);
      if (inBar === 4 && d > 0.3 && this.rand() < 0.85) this.engine.voice('drum', { gain: 0.08 + d * 0.16, rate: 1.0, room: 0.4, variant: 1, at: lag }, t);
      if (inBar === 7 && d > 0.65 && this.rand() < 0.6) this.engine.voice('drum', { gain: 0.07 + d * 0.1, rate: 1.12, room: 0.4, at: lag }, t);
      // a low figure rocking between two notes when things are tight: uneasy, not a metronome
      if (d > 0.4 && inBar % 2 === 0 && this.rand() < 0.82) {
        const note = inBar === 0 || inBar === 6 ? 50 : inBar === 4 ? 57 : 53;
        this.engine.pluck(note, { gain: (0.05 + d * 0.06) * (0.7 + this.rand() * 0.5), pan: -0.2, room: 0.3, at: this.rand() * 0.015 }, t);
      }
    }
  }

  private nextChord(t: number, fresh: boolean): void {
    const scene = this.applied.scene === 'match' ? 'match' : 'menu';
    this.chordIndex++;
    if (fresh || this.chordIndex >= this.progression.length) {
      this.progression = this.pick(PROGRESSIONS[scene]);
      this.chordIndex = 0;
    }
    this.chord = CHORDS[this.progression[this.chordIndex]];
    this.playPad(t);
    if (fresh || !this.motif.length || this.motifAge >= 4) this.writeMotif();
    else this.varyMotif();
    this.motifAge++;

    // the bell answers some of the changes
    const chance = scene === 'menu' ? 0.5 : this.applied.myTurn ? 0.35 : 0.15;
    if (this.rand() < chance) {
      const note = this.nearest(this.pick(this.chord.tones), 76, 91, 84);
      this.engine.voice('chime', { rate: hz(note) / CHIME_HZ, gain: 0.14, room: 0.8, pan: (this.rand() - 0.5) * 0.8, at: 60 / this.tempo() }, t);
    }
  }

  /** The note of a pitch class that lies in [low, high] and is closest to `near`. */
  private nearest(pitchClass: number, low: number, high: number, near: number): number {
    let best = low;
    let bestDist = Infinity;
    for (let n = low; n <= high; n++) {
      if (((n % 12) + 12) % 12 !== pitchClass) continue;
      const d = Math.abs(n - near);
      if (d < bestDist) {
        best = n;
        bestDist = d;
      }
    }
    return best;
  }

  /** The notes the tune may use over the current chord, low to high: chord tones, with scale notes between. */
  private ladder(low: number, high: number): number[] {
    const out: number[] = [];
    for (let n = low; n <= high; n++) {
      const pc = n % 12;
      if (this.chord.tones.includes(pc) || (SCALE.includes(pc) && n % 2 === 0 && !this.chord.tones.includes((pc + 1) % 12))) out.push(n);
    }
    return out.length ? out : [low];
  }

  /** Write a new two-bar tune: a few notes, mostly moving by step, ending lower than it peaks. */
  private writeMotif(): void {
    const slots = SLOTS_PER_BAR * BARS_PER_CHORD;
    const motif: (number | null)[] = new Array(slots).fill(null);
    let step = 3 + Math.floor(this.rand() * 4);
    const busy = 0.42 + this.rand() * 0.16;
    for (let i = 0; i < slots; i++) {
      const strong = i % 4 === 0;
      if (this.rand() > (strong ? busy + 0.3 : busy * 0.75)) continue;
      const move = this.rand();
      // rise through the first bar, come back down in the second
      const lean = i < slots / 2 ? 0.58 : 0.36;
      step += move < 0.12 ? (this.rand() < 0.5 ? 2 : -2) : this.rand() < lean ? 1 : -1;
      step = Math.max(0, Math.min(11, step));
      motif[i] = step;
    }
    if (!motif.some((m) => m !== null)) motif[0] = step;
    // the last bar leaves room to breathe
    motif[slots - 1] = null;
    motif[slots - 2] = null;
    this.motif = motif;
    this.motifAge = 0;
  }

  /** The same tune again, a little different: one note moved, one added or dropped. */
  private varyMotif(): void {
    const m = [...this.motif];
    const played = m.map((v, i) => (v === null ? -1 : i)).filter((i) => i >= 0);
    if (played.length) {
      const i = this.pick(played);
      m[i] = Math.max(0, Math.min(11, (m[i] as number) + (this.rand() < 0.5 ? 1 : -1)));
    }
    const j = Math.floor(this.rand() * (m.length - 2));
    const here = m[j];
    if (here === null && this.rand() < 0.5) m[j] = m[played[0] ?? 0] ?? 4;
    else if (here !== null && played.length > 3 && this.rand() < 0.35) m[j] = null;
    this.motif = m;
  }

  // --- the pad: a few soft voices holding the chord ---

  private shapePad(t: number): void {
    const s = this.applied;
    const cutoff = s.scene === 'off' ? 500 : s.scene === 'menu' ? 2200 : s.myTurn ? 2600 - s.danger * 700 : 1400;
    this.padFilter.frequency.setTargetAtTime(cutoff, t, 1.2);
    // in a match the bed steps back, so the strings and the game's own sounds stay clear
    this.padBus.gain.setTargetAtTime(s.scene === 'match' ? 0.52 : 0.68, t, 1.5);
  }

  private playPad(t: number): void {
    const ctx = this.engine.ctx;
    const hold = (60 / this.tempo()) * 4 * BARS_PER_CHORD;
    // three chord tones in the middle, each as close as possible to where a voice already is
    const tones = this.chord.tones.slice(0, 4);
    const targets = this.padVoicing.length ? this.padVoicing : [55, 60, 64];
    const voicing = targets.map((near, i) => this.nearest(tones[(i + 1) % tones.length], 52, 68, near));
    this.padVoicing = voicing;
    const notes = [this.chord.root + 12, ...voicing];

    const old = this.live;
    this.live = [];
    old.forEach((v) => v.stop(t + 2.6));

    // each voice has its own place between the speakers
    const places = [-0.1, -0.55, 0.15, 0.6];
    notes.forEach((midi, i) => {
      const g = ctx.createGain();
      const level = i === 0 ? 0.055 : 0.075;
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(level, t + 1.7);
      const place = ctx.createStereoPanner();
      place.pan.value = places[i % places.length];
      g.connect(place).connect(this.padFilter);
      const oscs: OscillatorNode[] = [];
      const add = (type: OscillatorType, detune: number, octave: number) => {
        const o = ctx.createOscillator();
        o.type = type;
        o.frequency.value = hz(midi + octave * 12);
        o.detune.value = detune;
        o.connect(g);
        o.start(t);
        oscs.push(o);
      };
      if (i === 0) {
        add('sine', 0, 0);
        add('triangle', 4, 0);
      } else {
        // soft and hollow, like a small pipe organ heard from the next room
        add('triangle', -5, 0);
        add('triangle', 6, 0);
        add('sine', 3, 1);
      }
      this.live.push({
        stop: (when) => {
          g.gain.cancelScheduledValues(Math.max(t, when - 2.6));
          g.gain.setTargetAtTime(0, Math.max(t, when - 2.6), 0.8);
          oscs.forEach((o) => o.stop(when + 0.5));
        },
      });
    });
    void hold;
  }
}
