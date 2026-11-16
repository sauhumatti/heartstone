// Pure Web Audio API tavern SFX synthesizer (zero external audio files needed)

class TavernSound {
  private ctx: AudioContext | null = null;
  public enabled: boolean = localStorage.getItem('hs_sfx') !== 'off';

  private ensureCtx(): AudioContext | null {
    if (!this.enabled) return null;
    if (!this.ctx && typeof window !== 'undefined') {
      const AC = window.AudioContext || (window as any).webkitAudioContext;
      if (AC) this.ctx = new AC();
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
    return this.ctx;
  }

  public setEnabled(val: boolean): void {
    this.enabled = val;
    localStorage.setItem('hs_sfx', val ? 'on' : 'off');
  }

  private tone(freq: number, dur: number, type: OscillatorType = 'triangle', gain = 0.08, slideTo?: number): void {
    const ctx = this.ensureCtx();
    if (!ctx) return;
    const now = ctx.currentTime;
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, now);
    if (slideTo) {
      osc.frequency.exponentialRampToValueAtTime(slideTo, now + dur);
    }
    g.gain.setValueAtTime(gain, now);
    g.gain.exponentialRampToValueAtTime(0.001, now + dur);
    osc.connect(g);
    g.connect(ctx.destination);
    osc.start(now);
    osc.stop(now + dur + 0.02);
  }

  public cardHover(): void {
    this.tone(420, 0.04, 'sine', 0.025, 520);
  }

  public cardPlay(): void {
    this.tone(170, 0.14, 'triangle', 0.11, 95);
    setTimeout(() => this.tone(330, 0.09, 'sine', 0.05), 35);
  }

  public spellCast(): void {
    this.tone(520, 0.22, 'sine', 0.07, 880);
    setTimeout(() => this.tone(780, 0.18, 'triangle', 0.05, 1120), 60);
  }

  public attack(): void {
    this.tone(140, 0.16, 'sawtooth', 0.11, 55);
    setTimeout(() => this.tone(240, 0.08, 'square', 0.05, 110), 25);
  }

  public heroPower(): void {
    this.tone(440, 0.18, 'sine', 0.07, 660);
  }

  public turnStart(): void {
    this.tone(392, 0.14, 'triangle', 0.07);
    setTimeout(() => this.tone(523.25, 0.24, 'triangle', 0.08), 110);
  }

  public victory(): void {
    [523.25, 659.25, 783.99, 1046.5].forEach((f, i) => {
      setTimeout(() => this.tone(f, 0.35, 'triangle', 0.08), i * 110);
    });
  }

  public defeat(): void {
    [293.66, 261.63, 220.0, 174.61].forEach((f, i) => {
      setTimeout(() => this.tone(f, 0.35, 'sawtooth', 0.06), i * 140);
    });
  }
}

export const sfx = new TavernSound();
