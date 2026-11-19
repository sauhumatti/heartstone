// Low-level effects on the board. The board is laid out at a fixed logical size
// and scaled to the window, so every position here is in board units.
export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
  cx: number;
  cy: number;
}

const EASE_OUT = 'cubic-bezier(.2,.8,.2,1)';
const EASE_IN = 'cubic-bezier(.6,0,.9,.4)';
const EASE_BACK = 'cubic-bezier(.3,1.5,.5,1)';

export const ease = { out: EASE_OUT, in: EASE_IN, back: EASE_BACK };

/** Resolves when the animation ends. If the page's clock is not advancing (a
 *  throttled tab), it is finished by hand so nothing hangs at its first frame. */
export function settle(a: Animation, total: number): Promise<void> {
  return new Promise<void>((resolve) => {
    let done = false;
    const end = () => {
      if (done) return;
      done = true;
      window.clearTimeout(timer);
      resolve();
    };
    const timer = window.setTimeout(() => {
      try {
        if (a.playState !== 'finished' && a.playState !== 'idle') a.finish();
      } catch {
        /* nothing to finish */
      }
      end();
    }, total + 150);
    a.finished.then(end, end);
  });
}

export function reducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

export class Fx {
  /** 1 = normal. Below 1 plays faster. */
  speed = 1;

  constructor(
    public root: HTMLElement,
    public layer: HTMLElement,
  ) {}

  get scale(): number {
    const w = this.root.offsetWidth;
    return w ? this.root.getBoundingClientRect().width / w : 1;
  }

  ms(d: number): number {
    return Math.max(0, d * this.speed);
  }

  sleep(d: number): Promise<void> {
    return new Promise((r) => window.setTimeout(r, this.ms(d)));
  }

  box(el: Element | null | undefined): Box | null {
    if (!el) return null;
    const k = this.scale;
    const R = this.root.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) return null;
    const x = (r.left - R.left) / k;
    const y = (r.top - R.top) / k;
    const w = r.width / k;
    const h = r.height / k;
    return { x, y, w, h, cx: x + w / 2, cy: y + h / 2 };
  }

  /** Board position of a pointer event. */
  point(clientX: number, clientY: number): { x: number; y: number } {
    const k = this.scale;
    const R = this.root.getBoundingClientRect();
    return { x: (clientX - R.left) / k, y: (clientY - R.top) / k };
  }

  /** Runs a Web Animation and resolves when it ends, is cancelled or times out. */
  anim(
    el: Element | null | undefined,
    keyframes: Keyframe[],
    opts: KeyframeAnimationOptions & { duration: number },
  ): Promise<void> {
    if (!el || !(el as HTMLElement).animate) return Promise.resolve();
    const duration = this.ms(opts.duration);
    const delay = this.ms(Number(opts.delay) || 0);
    let a: Animation;
    try {
      a = (el as HTMLElement).animate(keyframes, { easing: EASE_OUT, fill: 'none', ...opts, duration, delay });
    } catch {
      return Promise.resolve();
    }
    return settle(a, duration + delay);
  }

  spawn(className: string, at: { cx: number; cy: number }, size = 0): HTMLElement {
    const el = document.createElement('div');
    el.className = `fx ${className}`;
    el.style.left = `${at.cx}px`;
    el.style.top = `${at.cy}px`;
    if (size) {
      el.style.width = `${size}px`;
      el.style.height = `${size}px`;
    }
    this.layer.appendChild(el);
    return el;
  }

  private async once(el: HTMLElement, keyframes: Keyframe[], opts: KeyframeAnimationOptions & { duration: number }) {
    await this.anim(el, keyframes, { fill: 'forwards', ...opts });
    el.remove();
  }

  /** Number that pops over a character: damage, healing, a short word. */
  floater(at: Box, text: string, kind: 'dmg' | 'heal' | 'note' | 'buff' = 'dmg'): void {
    const el = this.spawn(`fx-floater fx-${kind}`, at);
    el.textContent = text;
    const big = kind === 'dmg' || kind === 'heal';
    void this.once(
      el,
      [
        { translate: '-50% -50%', scale: 0.3, opacity: 0 },
        { translate: '-50% -62%', scale: big ? 1.25 : 1.05, opacity: 1, offset: 0.16 },
        { translate: '-50% -66%', scale: 1, opacity: 1, offset: 0.3 },
        { translate: '-50% -80%', scale: 1, opacity: 1, offset: 0.78 },
        { translate: '-50% -120%', scale: 0.9, opacity: 0 },
      ],
      { duration: big ? 1050 : 800, easing: 'linear' },
    );
  }

  ring(at: { cx: number; cy: number }, color: string, size = 150, duration = 460): void {
    const el = this.spawn('fx-ring', at, size);
    el.style.setProperty('--c', color);
    void this.once(
      el,
      [
        { translate: '-50% -50%', scale: 0.25, opacity: 0.95 },
        { translate: '-50% -50%', scale: 1, opacity: 0 },
      ],
      { duration },
    );
  }

  burst(at: { cx: number; cy: number }, color: string, size = 120): void {
    const el = this.spawn('fx-burst', at, size);
    el.style.setProperty('--c', color);
    void this.once(
      el,
      [
        { translate: '-50% -50%', scale: 0.2, opacity: 1 },
        { translate: '-50% -50%', scale: 1, opacity: 0.9, offset: 0.35 },
        { translate: '-50% -50%', scale: 1.25, opacity: 0 },
      ],
      { duration: 380 },
    );
  }

  sparks(at: { cx: number; cy: number }, color: string, count = 9, reach = 70): void {
    for (let i = 0; i < count; i++) {
      const el = this.spawn('fx-spark', at);
      el.style.setProperty('--c', color);
      const ang = (Math.PI * 2 * i) / count + Math.random() * 0.7;
      const dist = reach * (0.55 + Math.random() * 0.7);
      const dx = Math.cos(ang) * dist;
      const dy = Math.sin(ang) * dist;
      void this.once(
        el,
        [
          { translate: '-50% -50%', scale: 1, opacity: 1 },
          { translate: `calc(-50% + ${dx}px) calc(-50% + ${dy + 18}px)`, scale: 0.2, opacity: 0 },
        ],
        { duration: 420 + Math.random() * 220 },
      );
    }
  }

  /** Shards flying off something that broke. */
  shards(at: Box, color: string, count = 10): void {
    for (let i = 0; i < count; i++) {
      const el = this.spawn('fx-shard', { cx: at.x + Math.random() * at.w, cy: at.y + Math.random() * at.h });
      el.style.setProperty('--c', color);
      const dx = (Math.random() - 0.5) * 220;
      const dy = 60 + Math.random() * 140;
      const rot = (Math.random() - 0.5) * 540;
      void this.once(
        el,
        [
          { translate: '-50% -50%', rotate: '0deg', opacity: 1 },
          { translate: `calc(-50% + ${dx * 0.5}px) calc(-50% - ${30 + Math.random() * 40}px)`, rotate: `${rot / 2}deg`, opacity: 1, offset: 0.3 },
          { translate: `calc(-50% + ${dx}px) calc(-50% + ${dy}px)`, rotate: `${rot}deg`, opacity: 0 },
        ],
        { duration: 700 + Math.random() * 250, easing: 'linear' },
      );
    }
  }

  /** A bolt from one point to another, with a slight arc. Resolves on impact. */
  async projectile(from: { cx: number; cy: number }, to: { cx: number; cy: number }, color: string, delay = 0): Promise<void> {
    const dx = to.cx - from.cx;
    const dy = to.cy - from.cy;
    const dist = Math.hypot(dx, dy);
    if (dist < 8) return;
    const duration = Math.min(520, 210 + dist * 0.32);
    const lift = Math.min(90, dist * 0.18);
    const angle = (Math.atan2(dy, dx) * 180) / Math.PI;
    const el = this.spawn('fx-bolt', from);
    el.style.setProperty('--c', color);
    el.style.rotate = `${angle}deg`;
    el.style.opacity = '0';
    await this.once(
      el,
      [
        { translate: '-50% -50%', scale: 0.4, opacity: 0 },
        { translate: `calc(-50% + ${dx * 0.12}px) calc(-50% + ${dy * 0.12 - lift * 0.5}px)`, scale: 1, opacity: 1, offset: 0.12 },
        { translate: `calc(-50% + ${dx * 0.55}px) calc(-50% + ${dy * 0.55 - lift}px)`, scale: 1.1, opacity: 1, offset: 0.55 },
        { translate: `calc(-50% + ${dx}px) calc(-50% + ${dy}px)`, scale: 0.9, opacity: 1 },
      ],
      { duration, delay, easing: 'cubic-bezier(.45,.05,.75,.6)' },
    );
  }

  shake(el: Element | null | undefined, strength = 8): Promise<void> {
    const s = strength;
    return this.anim(
      el,
      [
        { translate: '0 0' },
        { translate: `${-s}px ${s * 0.4}px` },
        { translate: `${s * 0.8}px ${-s * 0.3}px` },
        { translate: `${-s * 0.5}px ${s * 0.2}px` },
        { translate: `${s * 0.25}px 0` },
        { translate: '0 0' },
      ],
      { duration: 300, easing: 'linear' },
    );
  }

  /** Bright flash over an element (it was hit, healed, changed). */
  flash(el: Element | null | undefined, color = '#fff', duration = 300): void {
    const b = this.box(el);
    if (!b || !el) return;
    const f = this.spawn('fx-flash', b);
    f.style.width = `${b.w}px`;
    f.style.height = `${b.h}px`;
    f.style.setProperty('--c', color);
    f.style.borderRadius = getComputedStyle(el as HTMLElement).borderRadius || '12px';
    void this.once(
      f,
      [
        { translate: '-50% -50%', opacity: 0.85 },
        { translate: '-50% -50%', opacity: 0 },
      ],
      { duration },
    );
  }

  screenShake(strength = 6): void {
    const s = strength;
    void this.anim(
      this.root,
      [
        { translate: '0 0' },
        { translate: `${s}px ${-s * 0.6}px` },
        { translate: `${-s * 0.8}px ${s * 0.5}px` },
        { translate: `${s * 0.5}px ${s * 0.3}px` },
        { translate: `${-s * 0.3}px ${-s * 0.2}px` },
        { translate: '0 0' },
      ],
      { duration: 340, easing: 'linear' },
    );
  }

  // --- FLIP: things that changed place slide there instead of jumping --------

  snapshot(): Map<string, Box> {
    const map = new Map<string, Box>();
    this.root.querySelectorAll<HTMLElement>('[data-flip]').forEach((el) => {
      const b = this.box(el);
      if (b) map.set(el.dataset.flip!, b);
    });
    return map;
  }

  flip(before: Map<string, Box>, duration = 280): void {
    this.root.querySelectorAll<HTMLElement>('[data-flip]').forEach((el) => {
      const prev = before.get(el.dataset.flip!);
      // Pieces still flying in finish at their new place on their own.
      if (!prev || el.dataset.entering) return;
      el.getAnimations().forEach((a) => {
        if (a.id === 'flip') a.cancel();
      });
      const now = this.box(el);
      if (!now) return;
      const dx = prev.cx - now.cx;
      const dy = prev.cy - now.cy;
      if (Math.abs(dx) < 1.5 && Math.abs(dy) < 1.5) return;
      try {
        const a = el.animate([{ translate: `${dx}px ${dy}px` }, { translate: '0 0' }], {
          duration: this.ms(duration),
          easing: EASE_OUT,
        });
        a.id = 'flip';
      } catch {
        /* no animation support: the element is already in place */
      }
    });
  }

  clear(): void {
    this.layer.replaceChildren();
  }
}
