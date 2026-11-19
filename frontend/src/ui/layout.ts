// The match is drawn on a fixed logical table that is scaled to the screen.
// Two tables exist: the standard 16:9 one, and a wide one for phones held
// sideways (and other very wide screens) that puts the heroes beside the rows,
// so nothing is letterboxed and every piece comes out larger.
import { useLayoutEffect, useRef, useState } from 'react';

export interface Layout {
  name: 'standard' | 'wide';
  w: number;
  h: number;
  /** Horizontal centre of the two minion rows. */
  rowCx: number;
  handCx: number;
  handTop: number;
  cardW: number;
  handStep: number;
  handSpread: number;
  /** Above this line a dragged card counts as being over the board. */
  playLine: number;
}

export const LAYOUTS: Record<Layout['name'], Layout> = {
  standard: { name: 'standard', w: 1600, h: 900, rowCx: 800, handCx: 800, handTop: 724, cardW: 150, handStep: 118, handSpread: 700, playLine: 590 },
  wide: { name: 'wide', w: 1600, h: 740, rowCx: 870, handCx: 870, handTop: 490, cardW: 168, handStep: 128, handSpread: 760, playLine: 440 },
};

/** From this width-to-height ratio on, the wide table fills the screen better. */
const WIDE_FROM = 1.95;

export interface Fit {
  layout: Layout;
  /** Screen pixels per table unit. */
  k: number;
  x: number;
  y: number;
  /** How much controls and text are enlarged so they stay usable on a small screen. */
  ui: number;
  touch: boolean;
  /** A phone held upright: the table would be too small to play on. */
  upright: boolean;
}

export function isTouchDevice(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches;
}

export function computeFit(box: { left: number; top: number; width: number; height: number }, touch: boolean): Fit {
  const w = Math.max(1, box.width);
  const h = Math.max(1, box.height);
  const layout = w / h >= WIDE_FROM ? LAYOUTS.wide : LAYOUTS.standard;
  const k = Math.min(w / layout.w, h / layout.h);
  return {
    layout,
    k,
    x: box.left + (w - layout.w * k) / 2,
    y: box.top + (h - layout.h * k) / 2,
    ui: Math.max(1, Math.min(1.8, 0.9 / k)),
    touch,
    upright: touch && h > w * 1.1,
  };
}

/** Fits the table into the part of the screen that is free of notches and system bars. */
export function useFit() {
  const safeRef = useRef<HTMLDivElement | null>(null);
  const [fit, setFit] = useState<Fit>(() =>
    computeFit({ left: 0, top: 0, width: window.innerWidth, height: window.innerHeight }, isTouchDevice()),
  );
  useLayoutEffect(() => {
    const measure = () => {
      const r = safeRef.current?.getBoundingClientRect();
      const box = r && r.width > 0 ? r : { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
      setFit(computeFit(box, isTouchDevice()));
    };
    measure();
    const ro = typeof ResizeObserver !== 'undefined' && safeRef.current ? new ResizeObserver(measure) : null;
    if (ro && safeRef.current) ro.observe(safeRef.current);
    window.addEventListener('resize', measure);
    window.addEventListener('orientationchange', measure);
    return () => {
      ro?.disconnect();
      window.removeEventListener('resize', measure);
      window.removeEventListener('orientationchange', measure);
    };
  }, []);
  return { fit, safeRef };
}

/**
 * While a match is on screen on a phone or tablet: go full screen, turn the
 * screen sideways and keep it awake. Each of these may be refused by the
 * browser; the match works without them.
 */
export function useImmersive(active: boolean): void {
  useLayoutEffect(() => {
    if (!active) return;
    // The packaged app is full screen, sideways and awake by its own means.
    if (document.documentElement.classList.contains('in-android-app')) return;
    let enteredFullscreen = false;
    let wake: { release: () => Promise<void> } | null = null;
    let gone = false;
    const orientation = (screen as any).orientation;

    const enter = async () => {
      try {
        const standalone = window.matchMedia('(display-mode: standalone), (display-mode: fullscreen)').matches;
        if (!standalone && !document.fullscreenElement && document.documentElement.requestFullscreen) {
          await document.documentElement.requestFullscreen({ navigationUI: 'hide' });
          enteredFullscreen = true;
        }
      } catch {
        /* needs a tap, or is not allowed here */
      }
      try {
        await orientation?.lock?.('landscape');
      } catch {
        /* only possible full screen or installed */
      }
    };
    const keepAwake = async () => {
      try {
        if (!gone && document.visibilityState === 'visible') wake = await (navigator as any).wakeLock?.request('screen');
      } catch {
        /* not supported or not allowed */
      }
    };
    void enter();
    void keepAwake();
    document.addEventListener('visibilitychange', keepAwake);

    return () => {
      gone = true;
      document.removeEventListener('visibilitychange', keepAwake);
      void wake?.release().catch(() => undefined);
      try {
        orientation?.unlock?.();
      } catch {
        /* nothing was locked */
      }
      if (enteredFullscreen && document.fullscreenElement) void document.exitFullscreen().catch(() => undefined);
    };
  }, [active]);
}
