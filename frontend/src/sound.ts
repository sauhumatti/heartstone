// The game's sound, as the rest of the app sees it: play a cue, set the mood,
// change the levels. The music and the light sounds are made in code; creature
// voices and the heavier effects are short recorded clips (see src/audio).
import { url } from './api';
import { CUES, type CueName, type CueOpts, WARM_FIRST } from './audio/cues';
import { CLIPS, Engine } from './audio/engine';
import { Music, type MusicState, scoreNotes } from './audio/music';

type Scene = MusicState['scene'];

class Sound {
  public enabled: boolean = localStorage.getItem('hs_sfx') !== 'off';
  public volume: number = Number(localStorage.getItem('hs_sfx_vol') ?? '0.8');
  public musicEnabled: boolean = localStorage.getItem('hs_music') !== 'off';
  public musicVolume: number = Number(localStorage.getItem('hs_music_vol') ?? '0.5');

  private ctx: AudioContext | null = null;
  private engine: Engine | null = null;
  private score: Music | null = null;
  private unlocked = false;
  private mood: MusicState = { scene: 'menu', myTurn: true, danger: 0 };

  constructor() {
    if (typeof window === 'undefined') return;
    // Browsers only let a page make sound after the first tap or key.
    const unlock = () => {
      this.unlocked = true;
      this.wake();
    };
    window.addEventListener('pointerdown', unlock, { passive: true });
    window.addEventListener('keydown', unlock, { passive: true });
    window.addEventListener(
      'click',
      (ev) => {
        const target = ev.target as HTMLElement | null;
        if (target?.closest('button, [data-click-sound]')) this.cue('uiClick');
      },
      { passive: true },
    );
    // Silent while the tab is in the background.
    document.addEventListener('visibilitychange', () => {
      if (!this.ctx) return;
      if (document.hidden) void this.ctx.suspend().catch(() => undefined);
      else this.wake();
    });
  }

  private wake(): Engine | null {
    if (!this.unlocked) return null;
    if (!this.ctx) {
      const AC: typeof AudioContext | undefined = window.AudioContext || (window as any).webkitAudioContext;
      if (!AC) return null;
      this.ctx = new AC({ latencyHint: 'interactive' });
      this.engine = new Engine(this.ctx);
      this.engine.locate = (file) => url(`sfx/${file}`);
      this.score = new Music(this.engine);
      this.engine.setSfxLevel(this.enabled ? this.volume : 0);
      this.engine.setMusicLevel(this.musicVolume);
      // Build the common sounds and the music's notes a few at a time, so nothing is late
      // (or makes the screen stutter) the first time it is needed.
      const queue: (string | number)[] = [...WARM_FIRST, ...scoreNotes()];
      const step = () => {
        const next = queue.shift();
        if (next === undefined || !this.engine) return;
        if (typeof next === 'number') this.engine.warmPluck(next);
        else this.engine.warm(next);
        window.setTimeout(step, 45);
      };
      window.setTimeout(step, 200);
      // Then bring in the recorded clips, two at a time; until one is here its cue plays a stand-in.
      const clips = Object.keys(CLIPS);
      const fetchNext = (): void => {
        const name = clips.shift();
        if (name === undefined || !this.engine) return;
        void this.engine.loadClip(name).then(fetchNext);
      };
      window.setTimeout(() => {
        fetchNext();
        fetchNext();
      }, 1200);
    }
    if (this.ctx.state === 'suspended' && !document.hidden) void this.ctx.resume().catch(() => undefined);
    this.syncMusic();
    return this.engine;
  }

  private syncMusic(): void {
    const score = this.score;
    if (!score) return;
    const wanted = this.musicEnabled && this.mood.scene !== 'off';
    score.setState(this.mood);
    if (wanted && !score.running) score.start();
    else if (!wanted && score.running) score.stop();
  }

  /** Play one of the game's cues. */
  public cue(name: CueName, opts: CueOpts = {}): void {
    if (!this.enabled) return;
    const engine = this.wake();
    if (!engine || this.ctx?.state !== 'running') return;
    try {
      CUES[name](engine, opts, engine.now);
    } catch {
      /* a sound must never break the game */
    }
  }

  // The few cues the interface itself plays.
  public uiClick(): void {
    this.cue('uiClick');
  }

  public cardHover(): void {
    this.cue('cardHover');
  }

  public error(): void {
    this.cue('error');
  }

  /** Where the player is: the menus, a match, or nowhere that wants music. */
  public setMusicScene(scene: Scene | 'tavern' | 'battle' | 'none'): void {
    const next: Scene = scene === 'tavern' ? 'menu' : scene === 'battle' ? 'match' : scene === 'none' ? 'off' : scene;
    this.mood = { ...this.mood, scene: next };
    this.syncMusic();
  }

  /** How the match stands: whose turn it is and how close a hero is to falling. */
  public setMusicState(state: Partial<Pick<MusicState, 'myTurn' | 'danger'>> & { over?: boolean }): void {
    const { over, ...rest } = state;
    this.mood = { ...this.mood, ...rest, scene: over ? 'off' : this.mood.scene === 'off' ? 'match' : this.mood.scene };
    this.syncMusic();
  }

  public setEnabled(val: boolean): void {
    this.enabled = val;
    localStorage.setItem('hs_sfx', val ? 'on' : 'off');
    this.engine?.setSfxLevel(val ? this.volume : 0);
    if (val) this.cue('uiClick');
  }

  public setVolume(val: number): void {
    this.volume = Math.max(0, Math.min(1, val));
    localStorage.setItem('hs_sfx_vol', String(this.volume));
    this.engine?.setSfxLevel(this.enabled ? this.volume : 0);
  }

  public setMusicEnabled(val: boolean): void {
    this.musicEnabled = val;
    localStorage.setItem('hs_music', val ? 'on' : 'off');
    this.wake();
    this.syncMusic();
  }

  public setMusicVolume(val: number): void {
    this.musicVolume = Math.max(0, Math.min(1, val));
    localStorage.setItem('hs_music_vol', String(this.musicVolume));
    this.engine?.setMusicLevel(this.musicVolume);
  }
}

export const sfx = new Sound();
export type { CueName, CueOpts };
