// The start of a match: who is met (Versus), then the opening hand and its swap (OpeningHand).
import React, { useEffect, useLayoutEffect, useRef } from 'react';
import { sfx } from '../sound';
import type { HandCard, HeroMeta, HeroView } from '../types';
import { Art, CardBack, CardFace, classColor, pretty } from './pieces';

/** How long the versus card stays up unless it is tapped away. */
export const VERSUS_MS = 2800;

const HALF_FLIP = 170;
const FLY = 430;
const STAGGER = 110;
const SETTLE = 380;
export const SHUFFLE_MS = 820;
export const HOLD_MS = 750;

/** Swapped cards: turn over, then fly into the deck, one after another. */
export const outMs = (n: number) => 2 * HALF_FLIP + FLY + STAGGER * Math.max(0, n - 1) + 80;
/** New cards: fly out of the deck, then turn face up. */
export const inMs = (n: number) => Math.max(SETTLE, FLY + 2 * HALF_FLIP + STAGGER * Math.max(0, n - 1)) + 80;

export type MullStage = 'out' | 'shuffle' | 'in' | 'hold';

/** The opening hand while its swap is being shown. */
export interface MullShow {
  /** The hand as it was dealt. */
  before: HandCard[];
  /** Indices (in `before`) of the cards sent back. */
  picks: number[];
  /** The hand after the swap: kept cards first, new ones after them (the engine's order). */
  after: HandCard[] | null;
  stage: MullStage;
}

function heroArt(h: HeroView): string {
  return `hero_${h.is_jaraxxus ? 'JARAXXUS' : h.card_class}`;
}

interface Side {
  hero: HeroView;
  name: string;
  deck_name?: string;
}

export const Versus: React.FC<{ me: Side; opp: Side; heroes: Record<string, HeroMeta>; onDone: () => void }> = ({ me, opp, heroes, onDone }) => {
  useEffect(() => {
    sfx.cue('cardPlay');
    const t = window.setTimeout(onDone, VERSUS_MS);
    return () => window.clearTimeout(t);
  }, [onDone]);
  const side = (s: Side, mine: boolean) => {
    const color = classColor(heroes, s.hero.card_class);
    return (
      <div className={`vs-side ${mine ? 'vs-mine' : 'vs-theirs'}`} style={{ ['--class' as any]: color }}>
        <div className="vs-portrait">
          <Art id={heroArt(s.hero)} alt={s.hero.name} tint={color} />
        </div>
        <strong className="vs-hero">{s.hero.name}</strong>
        <span className="vs-class">{pretty(s.hero.card_class)}</span>
        <span className="vs-player">{s.name}</span>
      </div>
    );
  };
  return (
    <div className="overlay versus" role="dialog" aria-label={`${me.hero.name} against ${opp.hero.name}`} onClick={onDone}>
      {side(me, true)}
      <div className="vs-mark" aria-hidden="true">
        VS
      </div>
      {side(opp, false)}
      <span className="vs-skip">Tap to continue</span>
    </div>
  );
};

interface OpeningHandProps {
  hand: HandCard[];
  heroes: Record<string, HeroMeta>;
  opp: HeroView;
  goesFirst: boolean;
  myBack?: string;
  busy: boolean;
  swap: Set<number>;
  show: MullShow | null;
  onToggle: (index: number) => void;
  onSubmit: () => void;
}

export const OpeningHand: React.FC<OpeningHandProps> = ({ hand, heroes, opp, goesFirst, myBack, busy, swap, show, onToggle, onSubmit }) => {
  const rowRef = useRef<HTMLDivElement | null>(null);
  const deckRef = useRef<HTMLDivElement | null>(null);
  /** Animations that hold cards where the show left them (cancelled when it ends). */
  const held = useRef<Animation[]>([]);
  /** Where the kept cards stood before the new hand was laid out. */
  const keptAt = useRef(new Map<string, DOMRect>());

  const stage = show?.stage ?? null;
  const cards = show ? (show.after && (stage === 'in' || stage === 'hold') ? show.after : show.before) : hand;
  const oppColor = classColor(heroes, opp.card_class);

  useEffect(() => {
    if (show) return;
    held.current.forEach((a) => a.cancel());
    held.current = [];
  }, [show]);

  useLayoutEffect(() => {
    if (!show) return;
    const row = rowRef.current;
    const deck = deckRef.current;
    const top = deck?.lastElementChild as HTMLElement | null;
    if (!row || !deck || !top) return;
    const scale = row.getBoundingClientRect().width / (row.offsetWidth || 1) || 1;
    const els = Array.from(row.querySelectorAll<HTMLElement>('[data-mull]'));
    const keep = (a: Animation) => held.current.push(a);
    const timers: number[] = [];
    const later = (ms: number, fn: () => void) => timers.push(window.setTimeout(fn, ms));
    const d = top.getBoundingClientRect();
    /** The transform that puts a card in the row on top of the deck. */
    const onDeck = (el: HTMLElement) => {
      const r = el.getBoundingClientRect();
      const dx = (d.left + d.width / 2 - (r.left + r.width / 2)) / scale;
      const dy = (d.top + d.height / 2 - (r.top + r.height / 2)) / scale;
      return `translate(${dx}px, ${dy}px) scale(${d.width / r.width}) rotate(-4deg)`;
    };
    const faceOf = (el: HTMLElement) => el.querySelector<HTMLElement>('.mull-face');
    const backOf = (el: HTMLElement) => el.querySelector<HTMLElement>('.mull-back');

    if (stage === 'out') {
      let n = 0;
      for (const el of els) {
        if (!show.picks.includes(Number(el.dataset.index))) continue;
        const delay = n++ * STAGGER;
        const face = faceOf(el);
        const back = backOf(el);
        const target = onDeck(el);
        if (face) keep(face.animate([{ transform: 'rotateY(0deg)' }, { transform: 'rotateY(90deg)' }], { duration: HALF_FLIP, delay, easing: 'ease-in', fill: 'forwards' }));
        if (back) keep(back.animate([{ transform: 'rotateY(-90deg)' }, { transform: 'rotateY(0deg)' }], { duration: HALF_FLIP, delay: delay + HALF_FLIP, easing: 'ease-out', fill: 'both' }));
        keep(
          el.animate(
            [
              { transform: 'none', opacity: 1 },
              { transform: target, opacity: 1, offset: 0.9 },
              { transform: target, opacity: 0 },
            ],
            { duration: FLY, delay: delay + 2 * HALF_FLIP, easing: 'cubic-bezier(.55,0,.25,1)', fill: 'both' },
          ),
        );
        later(delay + 2 * HALF_FLIP, () => sfx.cue('draw'));
      }
    } else if (stage === 'shuffle') {
      keptAt.current = new Map(els.filter((el) => !show.picks.includes(Number(el.dataset.index))).map((el) => [el.dataset.mull!, el.getBoundingClientRect()]));
      const layers = Array.from(deck.children) as HTMLElement[];
      const swing = (el: HTMLElement | undefined, dir: number) =>
        el?.animate(
          [
            { transform: 'none' },
            { transform: `translate(${dir * 46}px, -8px) rotate(${dir * 9}deg)` },
            { transform: 'none' },
            { transform: `translate(${-dir * 40}px, -6px) rotate(${-dir * 7}deg)` },
            { transform: 'none' },
          ],
          { duration: SHUFFLE_MS - 60, easing: 'ease-in-out' },
        );
      swing(layers[layers.length - 1], 1);
      swing(layers[layers.length - 2], -1);
      sfx.cue('shuffle');
    } else if (stage === 'in') {
      const before = new Set(show.before.map((c) => c.uid));
      let n = 0;
      for (const el of els) {
        const uid = el.dataset.mull!;
        if (before.has(uid)) {
          // A kept card slides to where it now stands.
          const was = keptAt.current.get(uid);
          const r = el.getBoundingClientRect();
          if (was && (Math.abs(was.left - r.left) > 1 || Math.abs(was.top - r.top) > 1)) {
            const dx = (was.left - r.left) / scale;
            const dy = (was.top - r.top) / scale;
            el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }], { duration: SETTLE, easing: 'cubic-bezier(.3,.7,.3,1)' });
          }
          continue;
        }
        const delay = n++ * STAGGER;
        const face = faceOf(el);
        const back = backOf(el);
        keep(el.animate([{ transform: onDeck(el) }, { transform: 'none' }], { duration: FLY, delay, easing: 'cubic-bezier(.3,.6,.25,1)', fill: 'both' }));
        if (back) keep(back.animate([{ transform: 'rotateY(0deg)' }, { transform: 'rotateY(-90deg)' }], { duration: HALF_FLIP, delay: delay + FLY, easing: 'ease-in', fill: 'both' }));
        if (face) keep(face.animate([{ transform: 'rotateY(90deg)' }, { transform: 'rotateY(0deg)' }], { duration: HALF_FLIP, delay: delay + FLY + HALF_FLIP, easing: 'ease-out', fill: 'both' }));
        later(delay, () => sfx.cue('draw'));
      }
    }
    return () => timers.forEach((t) => window.clearTimeout(t));
    // Each stage is shown once, when it begins.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  const swapped = (c: HandCard) => (show ? stage === 'out' && show.picks.includes(c.index) : swap.has(c.index));
  const n = show?.picks.length ?? 0;
  const sub = !show
    ? 'Tap the cards you want to swap.'
    : stage === 'hold'
      ? 'Your opening hand.'
      : stage === 'in'
        ? `Drawing ${n === 1 ? 'a new card' : `${n} new cards`}…`
        : `Shuffling ${n === 1 ? 'a card' : `${n} cards`} back into your deck…`;

  return (
    <div className="sheet sheet-wide mull-sheet">
      <h2>Opening hand</h2>
      <p className="sheet-sub">
        Against{' '}
        <strong className="mull-against" style={{ color: oppColor }}>
          {opp.name} · {pretty(opp.card_class)}
        </strong>
        . {goesFirst ? 'You go first.' : 'You go second.'} <span aria-live="polite">{sub}</span>
      </p>
      <div className={`card-row mull-row ${show ? 'is-showing' : ''}`} ref={rowRef}>
        {cards.map((c) => (
          <button
            key={c.uid}
            type="button"
            data-mull={c.uid}
            data-index={c.index}
            className={`pick ${swapped(c) ? 'is-swapped' : ''}`}
            disabled={!!show}
            onClick={() => onToggle(c.index)}
          >
            <div className="mull-face">
              <CardFace card={c} heroes={heroes} />
            </div>
            <CardBack className="mull-back" art={myBack} />
            {!show && <span className="pick-tag">Swap</span>}
          </button>
        ))}
      </div>
      <button type="button" className={`btn primary ${show ? 'is-hidden' : ''}`} disabled={busy || !!show} onClick={onSubmit}>
        {swap.size ? `Swap ${swap.size} and start` : 'Keep all and start'}
      </button>
      <div className={`mull-deck ${show ? 'is-showing' : ''}`} ref={deckRef} aria-hidden="true">
        <CardBack art={myBack} />
        <CardBack art={myBack} />
        <CardBack art={myBack} />
      </div>
    </div>
  );
};
