// The mixing desk: plays sounds from the bank (made in code) and recorded clips
// through one shared room, with separate levels for effects and music and a
// limiter so nothing ever clips. Works on any audio context, live or offline
// (offline is how sounds are checked).
import { pluckNote, sample, variantsOf } from './bank';
import CLIP_TAKES from './clips.json';
import { roomImpulse } from './dsp';

/** How many takes each recorded clip has (written by scripts/make_sfx.py). */
export const CLIPS: Record<string, number> = CLIP_TAKES;
const RETRY_MS = 30_000;

export interface Shot {
  /** Level, 1 = the sound's full level. */
  gain?: number;
  /** Playback speed: 2 is an octave up. */
  rate?: number;
  /** Left to right, -1..1. */
  pan?: number;
  /** If set, the sound travels to this position while it plays. */
  panTo?: number;
  /** Seconds from now (or from `when`). */
  at?: number;
  /** How much of it is sent into the room, 0..1. */
  room?: number;
  /** Do not vary the pitch slightly on each play. */
  exact?: boolean;
  /** Which take to use; by default they rotate. */
  variant?: number;
}

export class Engine {
  readonly ctx: BaseAudioContext;
  readonly sfx: GainNode;
  readonly music: GainNode;
  private duck: GainNode;
  private roomIn: GainNode;
  private master: GainNode;
  private buffers = new Map<string, AudioBuffer>();
  private turn = new Map<string, number>();
  private rand: () => number;
  private clips = new Map<string, AudioBuffer[]>();
  /** Clips being fetched or tried lately, and when each may be tried again. */
  private asked = new Map<string, number>();
  /** Where a recorded clip's file is. Unset (as in offline checks) there are no clips, only the bank. */
  public locate: ((file: string) => string) | null = null;

  constructor(ctx: BaseAudioContext, random: () => number = Math.random) {
    this.ctx = ctx;
    this.rand = random;

    const limiter = ctx.createDynamicsCompressor();
    limiter.threshold.value = -9;
    limiter.knee.value = 9;
    limiter.ratio.value = 8;
    limiter.attack.value = 0.003;
    limiter.release.value = 0.22;
    this.master = ctx.createGain();
    this.master.gain.value = 0.9;
    limiter.connect(this.master).connect(ctx.destination);

    this.sfx = ctx.createGain();
    this.sfx.connect(limiter);

    this.music = ctx.createGain();
    this.duck = ctx.createGain();
    this.music.connect(this.duck).connect(limiter);

    // One room for everything: it is what makes separate sounds belong together.
    const [l, r] = roomImpulse(ctx.sampleRate, 1.7, 7);
    const ir = ctx.createBuffer(2, l.length, ctx.sampleRate);
    ir.getChannelData(0).set(l);
    ir.getChannelData(1).set(r);
    const room = ctx.createConvolver();
    room.normalize = true;
    room.buffer = ir;
    this.roomIn = ctx.createGain();
    const roomOut = ctx.createGain();
    roomOut.gain.value = 0.55;
    this.roomIn.connect(room).connect(roomOut).connect(limiter);
  }

  get now(): number {
    return this.ctx.currentTime;
  }

  private toBuffer(key: string, make: () => Float32Array): AudioBuffer {
    let buf = this.buffers.get(key);
    if (!buf) {
      const data = make();
      buf = this.ctx.createBuffer(1, data.length, this.ctx.sampleRate);
      buf.getChannelData(0).set(data);
      this.buffers.set(key, buf);
    }
    return buf;
  }

  /** Build a sound ahead of time so its first use is instant. */
  warm(name: string): void {
    for (let v = 0; v < variantsOf(name); v++) this.toBuffer(`${name}:${v}`, () => sample(name, this.ctx.sampleRate, v));
  }

  /** Build a string note ahead of time (the music's notes are otherwise made as they first occur). */
  warmPluck(midi: number): void {
    this.toBuffer(`pluck:${midi}`, () => pluckNote(this.ctx.sampleRate, midi));
  }

  private start(buffer: AudioBuffer, dest: AudioNode, when: number, s: Shot): void {
    const ctx = this.ctx;
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    const rate = (s.rate ?? 1) * (s.exact ? 1 : 1 + (this.rand() - 0.5) * 0.05);
    src.playbackRate.value = rate;
    const g = ctx.createGain();
    g.gain.value = s.gain ?? 1;
    const pan = ctx.createStereoPanner();
    pan.pan.value = Math.max(-1, Math.min(1, s.pan ?? 0));
    if (s.panTo !== undefined) {
      pan.pan.setValueAtTime(pan.pan.value, when);
      pan.pan.linearRampToValueAtTime(Math.max(-1, Math.min(1, s.panTo)), when + buffer.duration / rate);
    }
    src.connect(g).connect(pan);
    pan.connect(dest);
    const room = s.room ?? 0.18;
    if (room > 0) {
      const send = ctx.createGain();
      send.gain.value = room;
      pan.connect(send).connect(this.roomIn);
    }
    src.start(when);
  }

  /** Play a sound from the bank as an effect. */
  play(name: string, s: Shot = {}, when = this.now): void {
    const n = variantsOf(name);
    const v = s.variant ?? (this.turn.get(name) ?? Math.floor(this.rand() * n)) % n;
    this.turn.set(name, v + 1);
    const buffer = this.toBuffer(`${name}:${v}`, () => sample(name, this.ctx.sampleRate, v));
    this.start(buffer, this.sfx, when + (s.at ?? 0), s);
  }

  /** Fetch a recorded clip's takes so it is ready when needed. Safe to call again and again. */
  async loadClip(name: string): Promise<void> {
    const takes = CLIPS[name];
    if (!takes || !this.locate || this.clips.has(name)) return;
    if ((this.asked.get(name) ?? 0) > Date.now()) return;
    this.asked.set(name, Infinity);
    const loaded: AudioBuffer[] = [];
    for (let v = 0; v < takes; v++) {
      try {
        const res = await fetch(this.locate(`${name}-${v}.mp3`));
        if (!res.ok) throw new Error(String(res.status));
        loaded.push(await this.ctx.decodeAudioData(await res.arrayBuffer()));
      } catch {
        /* a take that cannot be had is simply not used */
      }
    }
    if (loaded.length) this.clips.set(name, loaded);
    // nothing came (offline?): leave it for a while, then a later use may try again
    this.asked.set(name, loaded.length ? Infinity : Date.now() + RETRY_MS);
  }

  /**
   * Play a recorded clip as an effect. Returns false when the clip is not on
   * the device yet, so the caller can play its code-made stand-in instead.
   */
  clip(name: string, s: Shot = {}, when = this.now): boolean {
    const takes = this.clips.get(name);
    if (!takes) {
      void this.loadClip(name);
      return false;
    }
    const v = s.variant ?? (this.turn.get(name) ?? Math.floor(this.rand() * takes.length)) % takes.length;
    this.turn.set(name, v + 1);
    this.start(takes[v % takes.length], this.sfx, when + (s.at ?? 0), s);
    return true;
  }

  /** Play a sound from the bank as part of the music. */
  voice(name: string, s: Shot, when: number): void {
    const buffer = this.toBuffer(`${name}:${s.variant ?? 0}`, () => sample(name, this.ctx.sampleRate, s.variant ?? 0));
    this.start(buffer, this.music, when + (s.at ?? 0), { exact: true, ...s });
  }

  /** A plucked string at a MIDI pitch, as part of the music (or an effect, with `asEffect`). */
  pluck(midi: number, s: Shot, when: number, asEffect = false): void {
    const buffer = this.toBuffer(`pluck:${midi}`, () => pluckNote(this.ctx.sampleRate, midi));
    this.start(buffer, asEffect ? this.sfx : this.music, when + (s.at ?? 0), { exact: true, ...s });
  }

  /** Pull the music down for a moment so a big sound has room. */
  duckMusic(amount = 0.5, seconds = 0.6, when = this.now): void {
    const g = this.duck.gain;
    g.cancelScheduledValues(when);
    g.setValueAtTime(g.value, when);
    g.linearRampToValueAtTime(amount, when + 0.03);
    g.setTargetAtTime(1, when + 0.03 + seconds * 0.4, seconds * 0.35);
  }

  setSfxLevel(v: number): void {
    this.sfx.gain.setTargetAtTime(v, this.now, 0.03);
  }

  setMusicLevel(v: number, seconds = 0.4): void {
    this.music.gain.setTargetAtTime(v, this.now, seconds / 3);
  }

  /** Input for sustained music voices (the pad): into the music and a share into the room. */
  musicInput(room = 0.4): GainNode {
    const g = this.ctx.createGain();
    g.connect(this.music);
    const send = this.ctx.createGain();
    send.gain.value = room;
    g.connect(send).connect(this.roomIn);
    return g;
  }
}
