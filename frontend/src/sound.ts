// Hybrid Lyria MP3 audio engine (rotating music playlists + low-latency decoded SFX)

const SFX_IDS = [
  'ui_click',
  'card_play',
  'spell_chime',
  'attack_clash',
  'hero_power',
  'turn_horn',
  'victory_fanfare',
  'defeat_stinger',
] as const;

type SfxId = (typeof SFX_IDS)[number];
type MusicScene = 'tavern' | 'battle' | 'none';

export interface MusicTrack {
  id: string;
  title: string;
}

const PLAYLISTS: Record<'tavern' | 'battle', MusicTrack[]> = {
  tavern: [
    { id: 'tavern_theme', title: 'Tavern Hearth' },
    { id: 'tavern_hearth_jig', title: 'Celtic Inn Jig' },
    { id: 'tavern_arcane_tome', title: 'Arcane Spellbook' },
    { id: 'tavern_evening_ale', title: 'Fireside Waltz' },
  ],
  battle: [
    { id: 'battle_theme', title: 'Clash of Champions' },
    { id: 'battle_storm_horns', title: 'Stormwind Horns' },
    { id: 'battle_arcane_duel', title: 'Archmage Duel' },
    { id: 'battle_dragon_march', title: 'Dragonflight March' },
  ],
};

class TavernSound {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private buffers = new Map<string, AudioBuffer>();
  private loadingBuffers = new Set<string>();

  private musicEl: HTMLAudioElement | null = null;
  private musicScene: MusicScene = 'none';
  private trackOrders: Record<'tavern' | 'battle', MusicTrack[]> = {
    tavern: [...PLAYLISTS.tavern],
    battle: [...PLAYLISTS.battle],
  };
  private trackIndices: Record<'tavern' | 'battle', number> = {
    tavern: 0,
    battle: 0,
  };
  private trackListeners = new Set<(track: MusicTrack | null) => void>();
  private userUnlocked = false;

  public enabled: boolean = localStorage.getItem('hs_sfx') !== 'off';
  public volume: number = Number(localStorage.getItem('hs_sfx_vol') ?? '0.8');
  public musicEnabled: boolean = localStorage.getItem('hs_music') !== 'off';
  public musicVolume: number = Number(localStorage.getItem('hs_music_vol') ?? '0.35');

  constructor() {
    this.shuffleOrder('tavern');
    this.shuffleOrder('battle');
    if (typeof window !== 'undefined') {
      const unlock = () => {
        this.userUnlocked = true;
        this.unlockSync();
      };
      window.addEventListener('pointerdown', unlock, { passive: true });
      window.addEventListener('keydown', unlock, { passive: true });
      window.addEventListener(
        'click',
        (ev) => {
          const target = ev.target as HTMLElement | null;
          if (!target) return;
          if (target.closest('button, .deck-card, .deck-list-row')) {
            this.uiClick();
          }
        },
        { passive: true },
      );
    }
  }

  private shuffleOrder(scene: 'tavern' | 'battle', avoidId?: string): void {
    const arr = [...PLAYLISTS[scene]];
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    if (avoidId && arr.length > 1 && arr[0].id === avoidId) {
      [arr[0], arr[1]] = [arr[1], arr[0]];
    }
    this.trackOrders[scene] = arr;
    this.trackIndices[scene] = 0;
  }

  public getCurrentTrack(): MusicTrack | null {
    if (this.musicScene === 'none') return null;
    const list = this.trackOrders[this.musicScene];
    const idx = this.trackIndices[this.musicScene] % list.length;
    return list[idx] || null;
  }

  public subscribeTrack(fn: (track: MusicTrack | null) => void): () => void {
    this.trackListeners.add(fn);
    fn(this.getCurrentTrack());
    return () => {
      this.trackListeners.delete(fn);
    };
  }

  private emitTrack(): void {
    const cur = this.getCurrentTrack();
    this.trackListeners.forEach((fn) => fn(cur));
  }

  private getOrCreateCtx(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    if (!this.ctx) {
      const AC = window.AudioContext || (window as any).webkitAudioContext;
      if (!AC) return null;
      this.ctx = new AC();
      this.master = this.ctx.createGain();
      this.master.gain.value = this.enabled ? this.volume : 0;
      this.master.connect(this.ctx.destination);
      this.preloadSfx();
    }
    return this.ctx;
  }

  private preloadSfx(): void {
    const ctx = this.ctx;
    if (!ctx) return;
    for (const id of SFX_IDS) {
      if (this.buffers.has(id) || this.loadingBuffers.has(id)) continue;
      this.loadingBuffers.add(id);
      fetch(`/audio/${id}.mp3`)
        .then((res) => (res.ok ? res.arrayBuffer() : Promise.reject(new Error('missing'))))
        .then((buf) => ctx.decodeAudioData(buf))
        .then((decoded) => {
          this.buffers.set(id, decoded);
        })
        .catch(() => {
          // Graceful fallback to synth if unavailable
        });
    }
  }

  public unlockSync(): void {
    const ctx = this.getOrCreateCtx();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
    this.syncMusicPlayback();
  }

  public setEnabled(val: boolean): void {
    this.enabled = val;
    localStorage.setItem('hs_sfx', val ? 'on' : 'off');
    if (this.master && this.ctx) {
      this.master.gain.setValueAtTime(val ? this.volume : 0, this.ctx.currentTime);
    }
    if (val) {
      this.unlockSync();
      this.uiClick();
    }
  }

  public setVolume(val: number): void {
    this.volume = Math.max(0, Math.min(1, val));
    localStorage.setItem('hs_sfx_vol', String(this.volume));
    if (this.master && this.ctx) {
      this.master.gain.setValueAtTime(this.enabled ? this.volume : 0, this.ctx.currentTime);
    }
  }

  public setMusicEnabled(val: boolean): void {
    this.musicEnabled = val;
    localStorage.setItem('hs_music', val ? 'on' : 'off');
    this.syncMusicPlayback();
  }

  public setMusicVolume(val: number): void {
    this.musicVolume = Math.max(0, Math.min(1, val));
    localStorage.setItem('hs_music_vol', String(this.musicVolume));
    if (this.musicEl) {
      this.musicEl.volume = this.musicEnabled ? this.musicVolume : 0;
    }
  }

  public setMusicScene(scene: MusicScene): void {
    if (this.musicScene === scene) return;
    this.musicScene = scene;
    this.syncMusicPlayback(true);
    this.emitTrack();
  }

  public nextTrack(): void {
    if (this.musicScene === 'none') return;
    const scene = this.musicScene;
    const list = this.trackOrders[scene];
    const nextIdx = this.trackIndices[scene] + 1;
    if (nextIdx >= list.length) {
      const lastId = list[list.length - 1]?.id;
      this.shuffleOrder(scene, lastId);
    } else {
      this.trackIndices[scene] = nextIdx;
    }
    this.userUnlocked = true;
    this.syncMusicPlayback(true);
    this.emitTrack();
  }

  private syncMusicPlayback(forceReload = false): void {
    if (typeof window === 'undefined') return;
    if (!this.musicEnabled || this.musicScene === 'none') {
      if (this.musicEl) this.musicEl.pause();
      return;
    }
    const track = this.getCurrentTrack();
    if (!track) return;
    const targetSrc = `/audio/${track.id}.mp3`;

    if (!this.musicEl || forceReload) {
      if (this.musicEl) {
        this.musicEl.onended = null;
        this.musicEl.pause();
      }
      const el = new Audio(targetSrc);
      el.loop = false;
      el.volume = this.musicVolume;
      el.onended = () => {
        this.nextTrack();
      };
      this.musicEl = el;
    }

    this.musicEl.volume = this.musicVolume;
    if (this.userUnlocked && this.musicEl.paused) {
      this.musicEl.play().catch(() => {});
    }
  }

  private playBuffer(id: SfxId, fallbackFn: () => void, gainScale = 1.0): void {
    if (!this.enabled) return;
    const ctx = this.getOrCreateCtx();
    const buf = this.buffers.get(id);
    if (!ctx || !this.master || !buf) {
      fallbackFn();
      return;
    }
    const trigger = () => {
      if (!this.master) return;
      const src = ctx.createBufferSource();
      src.buffer = buf;
      const g = ctx.createGain();
      g.gain.value = gainScale;
      src.connect(g);
      g.connect(this.master);
      src.start(0);
    };
    if (ctx.state === 'suspended') {
      ctx.resume().then(trigger).catch(() => {});
    } else {
      trigger();
    }
  }

  private scheduleNote(
    ctx: AudioContext,
    freq: number,
    dur: number,
    type: OscillatorType,
    gainAmt: number,
    slideTo?: number,
    delaySec = 0,
  ): void {
    if (!this.master) return;
    const t0 = ctx.currentTime + delaySec;
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t0);
    if (slideTo) {
      osc.frequency.exponentialRampToValueAtTime(Math.max(20, slideTo), t0 + dur);
    }
    g.gain.setValueAtTime(0.001, t0);
    g.gain.linearRampToValueAtTime(gainAmt, t0 + 0.012);
    g.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
    osc.connect(g);
    g.connect(this.master);
    osc.start(t0);
    osc.stop(t0 + dur + 0.03);
  }

  private tone(
    freq: number,
    dur: number,
    type: OscillatorType = 'triangle',
    gainAmt = 0.24,
    slideTo?: number,
    delaySec = 0,
  ): void {
    if (!this.enabled) return;
    const ctx = this.getOrCreateCtx();
    if (!ctx) return;
    if (ctx.state === 'suspended') {
      ctx
        .resume()
        .then(() => this.scheduleNote(ctx, freq, dur, type, gainAmt, slideTo, delaySec))
        .catch(() => {});
    } else {
      this.scheduleNote(ctx, freq, dur, type, gainAmt, slideTo, delaySec);
    }
  }

  public uiClick(): void {
    this.playBuffer('ui_click', () => this.tone(480, 0.055, 'triangle', 0.16, 320), 0.75);
  }

  public cardHover(): void {
    this.tone(540, 0.04, 'sine', 0.07, 680);
  }

  public cardPlay(): void {
    this.playBuffer(
      'card_play',
      () => {
        this.tone(185, 0.16, 'triangle', 0.34, 92);
        this.tone(370, 0.11, 'sine', 0.2, 260, 0.03);
      },
      0.95,
    );
  }

  public spellCast(): void {
    this.playBuffer(
      'spell_chime',
      () => {
        this.tone(520, 0.25, 'sine', 0.24, 940);
        this.tone(780, 0.22, 'triangle', 0.18, 1260, 0.05);
      },
      0.9,
    );
  }

  public attack(): void {
    this.playBuffer(
      'attack_clash',
      () => {
        this.tone(150, 0.18, 'sawtooth', 0.28, 55);
        this.tone(260, 0.1, 'square', 0.15, 110, 0.02);
      },
      1.0,
    );
  }

  public heroPower(): void {
    this.playBuffer(
      'hero_power',
      () => {
        this.tone(440, 0.22, 'triangle', 0.24, 660);
        this.tone(880, 0.16, 'sine', 0.14, undefined, 0.05);
      },
      0.9,
    );
  }

  public turnStart(): void {
    this.playBuffer(
      'turn_horn',
      () => {
        this.tone(392, 0.16, 'triangle', 0.26);
        this.tone(523.25, 0.28, 'triangle', 0.3, undefined, 0.11);
      },
      0.9,
    );
  }

  public victory(): void {
    this.playBuffer(
      'victory_fanfare',
      () => {
        [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => {
          this.tone(f, 0.36, 'triangle', 0.26, undefined, i * 0.11);
        });
      },
      0.95,
    );
  }

  public defeat(): void {
    this.playBuffer(
      'defeat_stinger',
      () => {
        [293.66, 261.63, 220.0, 174.61].forEach((f, i) => {
          this.tone(f, 0.36, 'sawtooth', 0.2, undefined, i * 0.14);
        });
      },
      0.95,
    );
  }
}

export const sfx = new TavernSound();
