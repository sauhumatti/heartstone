// Pure Web Audio API tavern SFX synthesizer with automatic browser autoplay unlock

class TavernSound {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  public enabled: boolean = localStorage.getItem('hs_sfx') !== 'off';
  public volume: number = Number(localStorage.getItem('hs_sfx_vol') ?? '0.75');

  constructor() {
    if (typeof window !== 'undefined') {
      const unlock = () => {
        this.unlockSync();
      };
      window.addEventListener('pointerdown', unlock, { passive: true });
      window.addEventListener('keydown', unlock, { passive: true });
      // Subtle tactile click on UI buttons
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

  private getOrCreateCtx(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    if (!this.ctx) {
      const AC = window.AudioContext || (window as any).webkitAudioContext;
      if (!AC) return null;
      this.ctx = new AC();
      this.master = this.ctx.createGain();
      this.master.gain.value = this.enabled ? this.volume : 0;
      this.master.connect(this.ctx.destination);
    }
    return this.ctx;
  }

  public unlockSync(): void {
    const ctx = this.getOrCreateCtx();
    if (!ctx) return;
    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => {});
    }
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
    this.tone(480, 0.055, 'triangle', 0.16, 320);
  }

  public cardHover(): void {
    this.tone(540, 0.045, 'sine', 0.09, 680);
  }

  public cardPlay(): void {
    this.tone(185, 0.16, 'triangle', 0.34, 92);
    this.tone(370, 0.11, 'sine', 0.2, 260, 0.03);
  }

  public spellCast(): void {
    this.tone(520, 0.25, 'sine', 0.24, 940);
    this.tone(780, 0.22, 'triangle', 0.18, 1260, 0.05);
  }

  public attack(): void {
    this.tone(150, 0.18, 'sawtooth', 0.28, 55);
    this.tone(260, 0.1, 'square', 0.15, 110, 0.02);
  }

  public heroPower(): void {
    this.tone(440, 0.22, 'triangle', 0.24, 660);
    this.tone(880, 0.16, 'sine', 0.14, undefined, 0.05);
  }

  public turnStart(): void {
    this.tone(392, 0.16, 'triangle', 0.26);
    this.tone(523.25, 0.28, 'triangle', 0.3, undefined, 0.11);
  }

  public victory(): void {
    [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => {
      this.tone(f, 0.36, 'triangle', 0.26, undefined, i * 0.11);
    });
  }

  public defeat(): void {
    [293.66, 261.63, 220.0, 174.61].forEach((f, i) => {
      this.tone(f, 0.36, 'sawtooth', 0.2, undefined, i * 0.14);
    });
  }
}

export const sfx = new TavernSound();
