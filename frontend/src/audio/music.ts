// The music: written pieces (pieces.ts) played on recorded instruments with Tone.js.
// The samples are CC0 recordings from Versilian Studios' VSCO 2 Community Edition and
// Community Sample Library (scripts/make_music_samples.py makes the small files in
// public/music/). Two pieces belong to the menus and two to matches; they take turns,
// and each playing is arranged a little differently. In a match a drum layer rises as a
// hero gets closer to falling, and the tune steps back a little on the other side's turn.
// Tone.js is loaded only when music first plays, so it never delays the game.
import type { Engine } from './engine';
import { KIT, PIECES, type Piece, render } from './pieces';
import type { Ev } from './score';

export interface MusicState {
  scene: 'menu' | 'match' | 'off';
  /** In a match: is it the player's own turn? */
  myTurn: boolean;
  /** 0 = calm, 1 = a hero is about to fall. */
  danger: number;
}

type ToneNS = typeof import('tone');

interface Mix {
  /** Level in dB. */
  vol: number;
  pan: number;
  /** Share sent to the reverb. */
  rev: number;
  attack?: number;
  release?: number;
  /** Carries tunes: steps back on the other side's turn. */
  lead?: boolean;
  /** Hz below which the instrument is thinned, so the low end stays clear. */
  lowCut?: number;
  /** Hz above which it is softened. */
  highCut?: number;
}

const MIX: Record<string, Mix> = {
  harp: { vol: -14, pan: -0.22, rev: 0.3, release: 1.4, lowCut: 110 },
  strum: { vol: -19, pan: 0.32, rev: 0.2, release: 0.8, lowCut: 160 },
  recorder: { vol: -7, pan: 0.12, rev: 0.3, attack: 0.025, release: 0.22, lead: true },
  violin: { vol: -8, pan: 0.18, rev: 0.34, attack: 0.04, release: 0.3, lead: true },
  flute: { vol: -8, pan: 0.08, rev: 0.36, attack: 0.04, release: 0.3, lead: true },
  horn: { vol: -9, pan: -0.3, rev: 0.42, attack: 0.07, release: 0.5, lead: true },
  vlnEns: { vol: -12, pan: 0.26, rev: 0.45, attack: 0.18, release: 1.0, lowCut: 180 },
  celloEns: { vol: -19, pan: -0.12, rev: 0.25, attack: 0.25, release: 1.2, lowCut: 55 },
  celloPizz: { vol: -11, pan: -0.08, rev: 0.14, release: 0.5, lowCut: 50 },
  kit: { vol: -13, pan: 0, rev: 0.18, release: 1.5, highCut: 6500 },
  kitX: { vol: -13, pan: 0, rev: 0.1, release: 1.5, lowCut: 45 },
};

const KIT_FILES: Record<number, string> = {
  [KIT.frame]: 'frame',
  [KIT.frame2]: 'frame2',
  [KIT.frameMute]: 'frameMute',
  [KIT.frameMute2]: 'frameMute2',
  [KIT.frameHand]: 'frameHand',
  [KIT.tamb]: 'tamb',
  [KIT.tambShake]: 'tambShake',
  [KIT.tambRoll]: 'tambRoll',
  [KIT.bdrum]: 'bdrum',
  [KIT.timp]: 'timp',
  [KIT.timpLow]: 'timpLow',
};

const NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
const noteName = (m: number) => `${NAMES[m % 12]}${Math.floor(m / 12) - 1}`;

interface SampleList {
  pitched: Record<string, Record<string, string>>;
  hits: Record<string, string>;
}

/** The band: one sampler per instrument, each on its own channel, all into one room. */
interface Rig {
  play(e: Ev, when: number): void;
  /** 0..1, how loud the danger drums are. */
  setDanger(v: number): void;
  setTurn(mine: boolean): void;
  fade(to: number, seconds: number): void;
}

async function buildRig(T: ToneNS, base: string, list: SampleList, out: unknown): Promise<Rig> {
  const master = new T.Gain(0);
  const tone = new T.Filter({ frequency: 10500, type: 'lowpass', rolloff: -12 });
  const warmth = new T.EQ3({ low: 1.5, mid: 0, high: -1.5 });
  master.chain(warmth, tone);
  tone.connect(out as never);
  const reverb = new T.Reverb({ decay: 3.2, preDelay: 0.022, wet: 1 });
  await reverb.ready;
  const reverbIn = new T.Gain(1);
  // The room gets no low end (that is what made it muddy) and no hiss.
  reverbIn.chain(new T.Filter({ frequency: 280, type: 'highpass' }), new T.Filter({ frequency: 6500, type: 'lowpass' }), reverb, master);

  const samplers: Record<string, InstanceType<ToneNS['Sampler']>> = {};
  const channels: Record<string, InstanceType<ToneNS['Channel']>> = {};
  const add = (name: string, urls: Record<string, string>) => {
    const mix = MIX[name];
    const ch = new T.Channel({ volume: mix.vol, pan: mix.pan });
    const s = new T.Sampler({ urls, baseUrl: base, attack: mix.attack ?? 0, release: mix.release ?? 0.6 });
    let last: InstanceType<ToneNS['ToneAudioNode']> = s;
    if (mix.lowCut) last = last.connect(new T.Filter({ frequency: mix.lowCut, type: 'highpass' }));
    if (mix.highCut) last = last.connect(new T.Filter({ frequency: mix.highCut, type: 'lowpass' }));
    last.connect(ch);
    ch.connect(master);
    const send = new T.Gain(mix.rev);
    ch.connect(send);
    send.connect(reverbIn);
    samplers[name] = s;
    channels[name] = ch;
  };
  for (const [inst, notes] of Object.entries(list.pitched)) if (MIX[inst]) add(inst, notes);
  const kit: Record<string, string> = {};
  for (const [midi, file] of Object.entries(KIT_FILES)) if (list.hits[file]) kit[noteName(Number(midi))] = list.hits[file];
  add('kit', kit);
  add('kitX', kit);
  await T.loaded();

  return {
    play(e, when) {
      const s = samplers[e.inst];
      if (!s) return;
      try {
        if (e.inst === 'kit' || e.inst === 'kitX') s.triggerAttack(noteName(e.midi), when, e.vel);
        else s.triggerAttackRelease(noteName(e.midi), e.dur, when, e.vel);
      } catch {
        /* a note that cannot be played is skipped */
      }
    },
    setDanger(v) {
      const d = Math.max(0, Math.min(1, v));
      channels.kitX.volume.rampTo(MIX.kitX.vol - 14 + 16 * d, 1.5);
    },
    setTurn(mine) {
      for (const [name, mix] of Object.entries(MIX)) if (mix.lead) channels[name]?.volume.rampTo(mix.vol - (mine ? 0 : 2.5), 1.2);
    },
    fade(to, seconds) {
      master.gain.cancelScheduledValues(T.now());
      master.gain.rampTo(to, seconds);
    },
  };
}

const LEVEL = 2.4;
/** Seconds of quiet between two pieces. */
const GAP = 3;

export class Music {
  public running = false;
  private rig: Rig | null = null;
  private booting: Promise<void> | null = null;
  private state: MusicState = { scene: 'menu', myTurn: true, danger: 0 };
  /** The scene the playing piece belongs to. */
  private playing: 'menu' | 'match' | null = null;
  private queue: Ev[] = [];
  private qi = 0;
  private startAt = 0;
  private endAt = 0;
  private timer: number | null = null;
  private turn: Record<'menu' | 'match', number> = { menu: Math.floor(Math.random() * 2), match: Math.floor(Math.random() * 2) };
  private generation = 0;

  constructor(
    private engine: Engine,
    private locate: (file: string) => string = (f) => `music/${f}`,
  ) {}

  setState(s: MusicState): void {
    const before = this.state;
    this.state = { ...s };
    if (!this.rig) return;
    if (s.danger !== before.danger) this.rig.setDanger(s.scene === 'match' ? s.danger : 0);
    if (s.myTurn !== before.myTurn) this.rig.setTurn(s.myTurn || s.scene !== 'match');
    if (this.running && s.scene !== 'off' && this.playing && s.scene !== this.playing) this.change();
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    void this.boot().then(() => {
      if (this.running && !this.playing) this.next();
    });
  }

  stop(): void {
    this.running = false;
    this.generation++;
    this.playing = null;
    this.queue = [];
    if (this.timer !== null) window.clearInterval(this.timer);
    this.timer = null;
    this.rig?.fade(0, 1.2);
  }

  private boot(): Promise<void> {
    if (!this.booting) {
      this.booting = (async () => {
        const T = await import('tone');
        // Tone plays on the game's own audio context, into the music level (so the volume
        // setting and the ducking under big effects keep working).
        T.setContext(new T.Context(this.engine.ctx as AudioContext));
        const list: SampleList = await (await fetch(this.locate('samples.json'))).json();
        this.rig = await buildRig(T, this.locate(''), list, this.engine.music);
        this.rig.setDanger(0);
      })().catch((err) => {
        console.warn('music could not start', err);
        this.booting = null;
        this.running = false;
      });
    }
    return this.booting;
  }

  /** Fade out what plays, then start the scene's music. */
  private change(): void {
    const gen = ++this.generation;
    this.rig?.fade(0, 1.4);
    this.queue = [];
    this.playing = null;
    window.setTimeout(() => {
      if (gen === this.generation && this.running) this.next();
    }, 1600);
  }

  private next(): void {
    const scene = this.state.scene;
    if (!this.rig || scene === 'off') return;
    const pieces = PIECES.filter((p) => p.scene === scene);
    const piece: Piece = pieces[this.turn[scene]++ % pieces.length];
    const { events, seconds } = render(piece, Math.floor(Math.random() * 1e9));
    const now = this.engine.ctx.currentTime;
    this.queue = events;
    this.qi = 0;
    this.startAt = now + 0.25;
    this.endAt = this.startAt + seconds;
    this.playing = scene;
    this.rig.setDanger(scene === 'match' ? this.state.danger : 0);
    this.rig.setTurn(this.state.myTurn || scene !== 'match');
    this.rig.fade(LEVEL, 0.8);
    if (this.timer === null) this.timer = window.setInterval(() => this.pump(), 120);
    this.pump();
  }

  private pump(): void {
    if (!this.running || !this.rig || !this.playing) return;
    const now = this.engine.ctx.currentTime;
    const horizon = now + 0.6;
    while (this.qi < this.queue.length && this.startAt + this.queue[this.qi].t < horizon) {
      const e = this.queue[this.qi++];
      this.rig.play(e, Math.max(now + 0.03, this.startAt + e.t));
    }
    // A breath between pieces, then the next one.
    if (this.qi >= this.queue.length && now > this.endAt + GAP) this.next();
  }
}

/**
 * Renders a piece without playing it, for checking how it sounds (the ?musiccheck page
 * hook below). Returns the left and right channels.
 */
export async function renderOffline(pieceId: string, seconds: number, base: string, seed = 7, danger = 0.5): Promise<Float32Array[]> {
  const T = await import('tone');
  const piece = PIECES.find((p) => p.id === pieceId);
  if (!piece) throw new Error(`no piece ${pieceId}`);
  const list: SampleList = await (await fetch(`${base}samples.json`)).json();
  const buffer = await T.Offline(async () => {
    const rig = await buildRig(T, base, list, T.getDestination());
    rig.fade(LEVEL, 0.01);
    rig.setDanger(danger);
    const { events } = render(piece, seed);
    for (const e of events) if (e.t < seconds) rig.play(e, 0.1 + e.t);
  }, seconds + 2, 2, 44100);
  return [buffer.getChannelData(0), buffer.getChannelData(1)];
}

if (typeof window !== 'undefined' && window.location?.search.includes('musiccheck')) {
  const w = window as unknown as { __musicRender: typeof renderOffline; __pieces: string[] };
  w.__musicRender = renderOffline;
  w.__pieces = PIECES.map((p) => p.id);
}
