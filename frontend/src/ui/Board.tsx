// The match screen. Laid out on a fixed logical table that is scaled to the
// screen (see layout.ts), so positions and animations are the same everywhere.
import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { actions, fetchLevels, sendEmote } from '../api';
import { useSession } from '../game/useSession';
import { artOf } from '../progress/art';
import { DEFAULT_WORN, formatDelta, type MatchRecord, type OpponentKind, opponentOf, PACK_STEPS, RANKS, recordMatch, skipMatch, titleText, weakerOf } from '../progress/rules';
import { getProfile, updateProfile, useProfile } from '../progress/store';
import { sfx } from '../sound';
import type { BoardMinion, GameStateView, HandCard, HeroMeta, HeroView, Level, OpponentMode, WeaponView } from '../types';
import { useFit, useImmersive } from './layout';
import { Art, CardBack, CardFace, type CardLike, classColor, Icon, MinionTile, minionAsCard, Num } from './pieces';
import { PackIcon, PackMeter, RankBadge, RankLine } from './progressBits';

const SLOT_PITCH = 142;
/** How long a finger rests on a piece before its card is shown. */
const LONG_PRESS_MS = 380;
const EMOTES = ['Hello', 'Good move', 'Thanks', 'Oops', 'Good game'];

interface BoardProps {
  gameId: string;
  initialState: GameStateView;
  heroes: Record<string, HeroMeta>;
  onLeaveToLobby: () => void;
  onLeaveToMenu: () => void;
  /** Open a pack, over the table. */
  onOpenPack: () => void;
}

type Targeting =
  | { kind: 'attack'; source: string; valid: string[]; drag: boolean }
  | { kind: 'power'; valid: string[]; drag: boolean }
  | { kind: 'play'; card: HandCard; pos?: number; choose?: number; valid: string[]; drag: boolean };

interface Held {
  uid: string;
  pos?: number;
  dx: number;
  dy: number;
  minion: boolean;
}

interface Preview {
  card: CardLike;
  live?: { attack: number; health: number; baseAttack: number; baseHealth: number; damaged: boolean };
  notes: string[];
  x: number;
  y: number;
  /** Shown large in the middle: touch has no hover, so this is how a card is read. */
  big?: boolean;
}

/** Width of a card shown large: as tall as the table allows, leaving room for a note under it. */
function bigCardWidth(tableHeight: number): number {
  return Math.round(((tableHeight - 150) * 5) / 7);
}

function heroArt(h: HeroView): string {
  return `hero_${h.is_jaraxxus ? 'JARAXXUS' : h.card_class}`;
}

export const Board: React.FC<BoardProps> = ({ gameId, initialState, heroes, onLeaveToLobby, onLeaveToMenu, onOpenPack }) => {
  const s = useSession(gameId, initialState, heroes);
  const { view, busy } = s;
  const me = view.me;
  const opp = view.opponent;
  const { fit, safeRef } = useFit();
  const L = fit.layout;
  useImmersive(fit.touch);

  const tableRef = useRef<HTMLDivElement | null>(null);
  const layerRef = useRef<HTMLDivElement | null>(null);
  const arrowRef = useRef<SVGGElement | null>(null);
  const arrowPathRef = useRef<SVGPathElement | null>(null);
  const arrowLineRef = useRef<SVGPathElement | null>(null);
  const arrowHeadRef = useRef<SVGGElement | null>(null);

  const [targeting, setTargeting] = useState<Targeting | null>(null);
  const [dragUid, setDragUid] = useState<string | null>(null);
  const [insertAt, setInsertAt] = useState<number | null>(null);
  const [dragOver, setDragOver] = useState(false);
  /** A card enlarged by a tap (touch has no hover). */
  const [zoomUid, setZoomUid] = useState<string | null>(null);
  const [held, setHeld] = useState<Held | null>(null);
  const [chooser, setChooser] = useState<{ card: HandCard; pos?: number } | null>(null);
  const [swap, setSwap] = useState<Set<number>>(new Set());
  const [preview, setPreview] = useState<Preview | null>(null);
  const [showMenu, setShowMenu] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [showEmotes, setShowEmotes] = useState(false);
  const [emote, setEmote] = useState<GameStateView['last_emote']>(null);
  const [sfxOn, setSfxOn] = useState(sfx.enabled);
  const [musicOn, setMusicOn] = useState(sfx.musicEnabled);
  const [hint, setHint] = useState('');
  const [levels, setLevels] = useState<Level[]>([]);
  useEffect(() => {
    let alive = true;
    if (initialState.mode === 'ai_vs_human') void fetchLevels().then((l) => alive && setLevels(l.levels));
    return () => {
      alive = false;
    };
  }, [initialState.mode]);

  const targetingRef = useRef<Targeting | null>(null);
  targetingRef.current = targeting;
  const pointer = useRef<{ x: number; y: number } | null>(null);
  const pressAt = useRef<{ x: number; y: number } | null>(null);
  const hoverTarget = useRef<string | null>(null);
  const previewTimer = useRef<number | null>(null);
  /** Set while the current touch has turned into a long press (it must not also act). */
  const longPressed = useRef(false);
  /** Set when a touch was spent on putting an enlarged card away: the click it ends in must not act either. */
  const swallowClick = useRef(false);
  const hintTimer = useRef<number | null>(null);

  const { bind } = s;
  useLayoutEffect(() => {
    bind(tableRef.current, layerRef.current);
    return () => bind(null, null);
  }, [bind]);

  const canAct = view.phase === 'PLAY' && view.your_turn && !busy && !view.pending_choice;
  const q = useCallback((sel: string) => tableRef.current?.querySelector<HTMLElement>(sel) ?? null, []);

  const flashHint = useCallback((text: string) => {
    setHint(text);
    if (hintTimer.current) window.clearTimeout(hintTimer.current);
    hintTimer.current = window.setTimeout(() => setHint(''), 2600);
  }, []);

  // --- the score follows the match ---------------------------------------------
  const lowestHero = Math.min(me.hero.hp + me.hero.armor, opp.hero.hp + opp.hero.armor);
  useEffect(() => {
    sfx.setMusicState({
      myTurn: view.your_turn || view.phase !== 'PLAY',
      danger: view.phase === 'PLAY' ? Math.max(0, Math.min(1, (13 - lowestHero) / 10)) : 0,
      over: view.phase === 'GAME_OVER',
    });
  }, [view.phase, view.your_turn, lowestHero]);

  // --- what the player wears -----------------------------------------------------
  const profile = useProfile();
  const myBack = profile.worn.back === DEFAULT_WORN.back ? undefined : artOf(profile.worn.back);
  const tableArt = profile.worn.table === DEFAULT_WORN.table ? undefined : artOf(profile.worn.table);
  const myTitle = titleText(profile);

  // --- what the match is worth ---------------------------------------------------
  // The other seat can change hands during a match (and the on-device opponent its level):
  // the match counts as one against the weakest of them. `undefined` is "not known yet".
  const level = s.agent?.model;
  const weakest = useRef<OpponentKind | null | undefined>(undefined);
  useEffect(() => {
    if (view.phase === 'GAME_OVER') return;
    if (view.mode === 'ai_vs_human' && !level) return;
    const now = opponentOf(view.mode, level);
    weakest.current = weakest.current === undefined ? now : weakerOf(weakest.current, now);
  }, [view.mode, view.phase, level]);

  /** This match as the rating counted it; null while it is not counted (or is not rated). */
  const [record, setRecord] = useState<MatchRecord | null>(null);
  const finished = view.phase === 'GAME_OVER' && !s.playing;
  useEffect(() => {
    if (!finished || record || !view.winner) return;
    // Opened already finished: the on-device opponent's level arrives a moment later.
    if (weakest.current === undefined && view.mode === 'ai_vs_human' && !level) return;
    const opponent = weakest.current === undefined ? opponentOf(view.mode, level) : weakest.current;
    if (!opponent) return;
    const result = view.winner === view.me.seat ? 'win' : view.winner === 'draw' ? 'draw' : 'loss';
    // A match that ended before this device kept a rating is only looked at, never counted.
    const old = view.turn_started_at > 0 && view.turn_started_at * 1000 < getProfile().createdAt;
    let made: MatchRecord | null = null;
    updateProfile((cur) => {
      if (old) return skipMatch(cur, gameId);
      const counted = recordMatch(cur, { id: gameId, opponent, result, at: Date.now() });
      made = counted.record;
      return counted.profile;
    });
    setRecord(made);
  }, [finished, record, level, gameId, view.winner, view.mode, view.me.seat, view.turn_started_at]);

  // --- emote bubbles ---------------------------------------------------------
  const lastEmoteId = useRef<number | null>(initialState.last_emote?.id ?? null);
  useEffect(() => {
    const e = view.last_emote;
    if (!e || e.id === lastEmoteId.current) return;
    lastEmoteId.current = e.id;
    setEmote(e);
    const t = window.setTimeout(() => setEmote((cur) => (cur && cur.id === e.id ? null : cur)), 4200);
    return () => window.clearTimeout(t);
  }, [view.last_emote]);

  // --- hover preview ---------------------------------------------------------
  const hidePreview = useCallback(() => {
    if (previewTimer.current) window.clearTimeout(previewTimer.current);
    previewTimer.current = null;
    setPreview(null);
  }, []);

  const showPreview = useCallback(
    (e: React.PointerEvent, build: () => Omit<Preview, 'x' | 'y'> | null) => {
      if (e.pointerType === 'touch') return;
      const el = e.currentTarget as HTMLElement;
      if (previewTimer.current) window.clearTimeout(previewTimer.current);
      previewTimer.current = window.setTimeout(() => {
        const fx = s.fx.current;
        const b = fx?.box(el);
        const data = build();
        if (!b || !data) return;
        const w = 236;
        const h = 330;
        let x = b.x + b.w + 14;
        if (x + w > L.w - 12) x = b.x - w - 14;
        const y = Math.max(14, Math.min(L.h - h - 14, b.cy - h / 2));
        setPreview({ ...data, x, y });
      }, 380);
    },
    [s.fx, L],
  );

  /** A card shown as large as the table allows, in the middle of the rows. */
  const showBig = useCallback(
    (data: Omit<Preview, 'x' | 'y'> | null) => {
      if (!data) return;
      const w = bigCardWidth(L.h);
      setPreview({ ...data, big: true, x: L.rowCx - w / 2, y: (L.h - (w * 7) / 5) / 2 });
    },
    [L],
  );

  /** Touch: resting a finger on a piece shows its card until the finger lifts. */
  const pressPreview = (e: React.PointerEvent, build: () => Omit<Preview, 'x' | 'y'> | null) => {
    if (e.pointerType !== 'touch') return;
    const start = { x: e.clientX, y: e.clientY };
    longPressed.current = false;
    const stop = () => {
      window.clearTimeout(timer);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onEnd);
      window.removeEventListener('pointercancel', onEnd);
    };
    const onMove = (ev: PointerEvent) => {
      // Before the card shows, a moving finger is a drag, not a look. Once it shows, keep
      // listening for the lift: otherwise the card would stay up with nothing to take it down.
      if (!longPressed.current && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) > 12) stop();
    };
    const onEnd = () => {
      stop();
      if (!longPressed.current) return;
      hidePreview();
      // Stays set just long enough for the click that follows this release to be ignored.
      window.setTimeout(() => (longPressed.current = false), 80);
    };
    const timer = window.setTimeout(() => {
      longPressed.current = true;
      showBig(build());
    }, LONG_PRESS_MS);
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onEnd);
    window.addEventListener('pointercancel', onEnd);
  };

  const minionPreview = (m: BoardMinion) => (): Omit<Preview, 'x' | 'y'> => ({
    card: minionAsCard(m),
    live: { attack: m.attack, health: m.health, baseAttack: m.base_attack, baseHealth: m.base_health, damaged: m.damaged },
    notes: [
      m.frozen ? 'Frozen' : '',
      m.silenced ? 'Silenced' : '',
      m.immune ? 'Immune' : '',
      ...Array.from(new Set(m.enchantments)).map((n) => `Affected by ${n}`),
    ].filter(Boolean),
  });

  // --- targeting arrow -------------------------------------------------------
  const drawArrow = useCallback(() => {
    const t = targetingRef.current;
    const fx = s.fx.current;
    const g = arrowRef.current;
    const path = arrowPathRef.current;
    const head = arrowHeadRef.current;
    if (!t || !fx || !g || !path || !head) return;
    const srcEl =
      t.kind === 'attack'
        ? q(`[data-uid="${t.source}"]`)
        : t.kind === 'power'
          ? q(`[data-power="${me.seat}"]`)
          : q(`[data-card="${t.card.uid}"] .card`);
    const sb = fx.box(srcEl);
    if (!sb) return;
    let end = pointer.current ?? { x: sb.cx, y: sb.cy - 150 };
    let locked = false;
    const hov = hoverTarget.current;
    if (hov && t.valid.includes(hov)) {
      const hb = fx.box(q(`[data-uid="${hov}"]`));
      if (hb) {
        end = { x: hb.cx, y: hb.cy };
        locked = true;
      }
    }
    const sx = sb.cx;
    const sy = sb.cy;
    const dist = Math.hypot(end.x - sx, end.y - sy);
    const mx = (sx + end.x) / 2;
    const my = Math.min(sy, end.y) - Math.min(130, 24 + dist * 0.2);
    const d = `M ${sx} ${sy} Q ${mx} ${my} ${end.x} ${end.y}`;
    path.setAttribute('d', d);
    arrowLineRef.current?.setAttribute('d', d);
    const ang = (Math.atan2(end.y - my, end.x - mx) * 180) / Math.PI;
    head.setAttribute('transform', `translate(${end.x} ${end.y}) rotate(${ang})`);
    g.classList.toggle('locked', locked);
    g.style.opacity = dist > 24 ? '1' : '0';
  }, [me.seat, q, s.fx]);

  const cancelAll = useCallback(() => {
    setTargeting(null);
    setHeld(null);
    setChooser(null);
    setDragUid(null);
    setInsertAt(null);
    setDragOver(false);
    setZoomUid(null);
    hoverTarget.current = null;
  }, []);

  // --- sending actions -------------------------------------------------------
  const { act } = s;

  const submitPlay = useCallback(
    async (card: HandCard, pos: number | undefined, choose: number | undefined, targetId: string | undefined, drop?: Held) => {
      setTargeting(null);
      setChooser(null);
      setHeld((cur) => drop ?? cur ?? { uid: card.uid, pos, dx: 0, dy: 0, minion: card.type === 'MINION' });
      const ok = await act((since) =>
        actions.play(gameId, since, { hand_index: card.index, pos: pos ?? 0, target_id: targetId, choose }),
      );
      if (!ok) setHeld(null);
    },
    [act, gameId],
  );

  /** Carry on with a play once its position (and option) is known. */
  const continuePlay = useCallback(
    (card: HandCard, pos: number | undefined, choose: number | undefined, rule: string, valid: string[], drop?: Held) => {
      if (rule !== 'NONE' && valid.length > 0) {
        if (drop) setHeld(drop);
        setTargeting({ kind: 'play', card, pos, choose, valid, drag: false });
        return;
      }
      void submitPlay(card, pos, choose, undefined, drop);
    },
    [submitPlay],
  );

  const beginPlay = useCallback(
    (card: HandCard, pos?: number, drop?: Held) => {
      if (!canAct) return;
      if (!card.can_play) {
        flashHint(card.unplayable_reason || 'That card cannot be played right now.');
        sfx.error();
        return;
      }
      hidePreview();
      if (card.choose_options.length > 0) {
        if (drop) setHeld(drop);
        setChooser({ card, pos });
        return;
      }
      continuePlay(card, pos, undefined, card.target_rule, card.valid_targets, drop);
    },
    [canAct, continuePlay, flashHint, hidePreview],
  );

  const resolveTarget = useCallback(
    (tid: string) => {
      const t = targetingRef.current;
      if (!t || !t.valid.includes(tid)) return false;
      if (t.kind === 'attack') {
        setTargeting(null);
        void act((since) => actions.attack(gameId, since, t.source, tid));
      } else if (t.kind === 'power') {
        setTargeting(null);
        void act((since) => actions.power(gameId, since, tid));
      } else {
        void submitPlay(t.card, t.pos, t.choose, tid);
      }
      hoverTarget.current = null;
      return true;
    },
    [act, gameId, submitPlay],
  );

  // While something is being aimed: follow the pointer, resolve on release.
  useEffect(() => {
    if (!targeting) return;
    const onMove = (e: PointerEvent) => {
      const fx = s.fx.current;
      if (!fx) return;
      pointer.current = fx.point(e.clientX, e.clientY);
      const under = document.elementFromPoint(e.clientX, e.clientY)?.closest<HTMLElement>('[data-uid]');
      hoverTarget.current = under?.dataset.uid ?? null;
      drawArrow();
    };
    const onUp = (e: PointerEvent) => {
      const t = targetingRef.current;
      if (!t || !t.drag) return;
      if (longPressed.current) {
        // The press was a look at the card, not the start of an attack.
        longPressed.current = false;
        cancelAll();
        return;
      }
      const under = document.elementFromPoint(e.clientX, e.clientY)?.closest<HTMLElement>('[data-uid]');
      const tid = under?.dataset.uid;
      if (tid && resolveTarget(tid)) return;
      const p = pressAt.current;
      if (p && Math.hypot(e.clientX - p.x, e.clientY - p.y) < 10) {
        // A plain click on the source: keep aiming, pick the target with a click.
        setTargeting({ ...t, drag: false });
        return;
      }
      cancelAll();
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') cancelAll();
    };
    const onContext = (e: MouseEvent) => {
      e.preventDefault();
      cancelAll();
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('keydown', onKey);
    window.addEventListener('contextmenu', onContext);
    drawArrow();
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('contextmenu', onContext);
    };
  }, [targeting, drawArrow, resolveTarget, cancelAll, s.fx]);

  // Escape opens the menu when nothing is being aimed.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || targetingRef.current) return;
      if (chooser || held) cancelAll();
      else setShowMenu((v) => !v);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [chooser, held, cancelAll]);

  // Anything pending is dropped when the turn or phase moves on.
  useEffect(() => {
    if (!view.your_turn || view.phase !== 'PLAY') {
      setTargeting(null);
      setChooser(null);
      setDragUid(null);
      setInsertAt(null);
    }
  }, [view.your_turn, view.phase]);

  // A card being read that has left the hand has nothing left to show.
  useEffect(() => {
    if (zoomUid && !me.hand.some((c) => c.uid === zoomUid)) {
      setZoomUid(null);
      hidePreview();
    }
  }, [zoomUid, me.hand, hidePreview]);

  // A held card that has left the hand has been played.
  useEffect(() => {
    if (held && !me.hand.some((c) => c.uid === held.uid)) setHeld(null);
  }, [held, me.hand]);

  // --- attacking -------------------------------------------------------------
  const startAttack = (e: React.PointerEvent, source: string, valid: string[] | undefined, able: boolean | undefined) => {
    const cur = targetingRef.current;
    // While picking an attack target by click, pressing another attacker switches to it.
    const switching = cur?.kind === 'attack' && !cur.drag && cur.source !== source;
    if (e.button !== 0 || (cur && !switching) || !canAct || !able || !valid?.length) return;
    e.preventDefault();
    hidePreview();
    pressAt.current = { x: e.clientX, y: e.clientY };
    pointer.current = s.fx.current?.point(e.clientX, e.clientY) ?? null;
    hoverTarget.current = null;
    setTargeting({ kind: 'attack', source, valid, drag: true });
  };

  const clickCharacter = (uid: string) => {
    if (longPressed.current) return; // that touch was a look at the piece, not a choice of target
    const t = targetingRef.current;
    if (!t || t.drag) return;
    if (t.kind === 'attack' && (t.source === uid || uid === me.hero.id || me.board.some((m) => m.uid === uid))) return;
    if (!resolveTarget(uid)) {
      flashHint('That is not a valid target.');
      sfx.error();
    }
  };

  const clickPower = () => {
    if (longPressed.current) return; // that touch was a look at the card
    if (targetingRef.current || !canAct) return;
    const hp = me.hero.hero_power;
    if (!hp.can_use) {
      flashHint(hp.used ? 'Already used this turn.' : 'Not enough mana.');
      return;
    }
    hidePreview();
    if (hp.target_rule && hp.target_rule !== 'NONE' && (hp.valid_targets?.length ?? 0) > 0) {
      pointer.current = null;
      setTargeting({ kind: 'power', valid: hp.valid_targets || [], drag: false });
    } else {
      void act((since) => actions.power(gameId, since));
    }
  };

  // --- dragging a card out of the hand -----------------------------------------
  const insertIndexAt = useCallback(
    (x: number) => {
      const n = me.board.length;
      const left = L.rowCx - ((n + 1) * SLOT_PITCH) / 2;
      return Math.max(0, Math.min(n, Math.floor((x - left) / SLOT_PITCH)));
    },
    [me.board.length, L],
  );

  const onCardPointerDown = (e: React.PointerEvent, card: HandCard) => {
    if (e.button !== 0 || targetingRef.current || chooser || held) return;
    const el = e.currentTarget as HTMLElement;
    const fx = s.fx.current;
    if (!fx) return;
    const start = { x: e.clientX, y: e.clientY };
    const touch = e.pointerType === 'touch';
    const k = fx.scale;
    // A finger wobbles. On touch a press becomes a drag only after a clear move, and only a real
    // pull up out of the hand (not a tap that slipped) can put the card on the table.
    const slop = touch ? 12 / k : 9;
    const pull = touch ? L.cardW * 1.4 * 0.45 : 0;
    let active = false;
    let over = false;
    let insert: number | null = null;
    let dx = 0;
    let dy = 0;
    // A card that only needs a target is aimed straight from the hand.
    const aimed = card.type !== 'MINION' && card.choose_options.length === 0 && card.target_required;

    const cleanup = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      window.removeEventListener('pointercancel', onCancel);
    };
    const reset = () => {
      el.style.translate = '';
      setDragUid(null);
      setInsertAt(null);
      setDragOver(false);
    };
    const onMove = (ev: PointerEvent) => {
      dx = (ev.clientX - start.x) / k;
      dy = (ev.clientY - start.y) / k;
      if (!active) {
        if (Math.hypot(dx, dy) < slop) return;
        if (!canAct || !card.can_play) {
          cleanup();
          // the look at a card is over once a finger starts pulling one, even one that cannot be played
          setZoomUid(null);
          hidePreview();
          if (view.your_turn && !busy) {
            flashHint(card.unplayable_reason || 'That card cannot be played right now.');
            sfx.error();
          }
          return;
        }
        active = true;
        hidePreview();
        setZoomUid(null);
        setDragUid(card.uid);
      }
      const p = fx.point(ev.clientX, ev.clientY);
      const pulled = !touch || -dy >= pull;
      if (aimed) {
        if (p.y < L.playLine + 70 && pulled) {
          // Leave the card lifted in the hand and aim from it.
          cleanup();
          reset();
          pressAt.current = null;
          pointer.current = p;
          hoverTarget.current = null;
          setTargeting({ kind: 'play', card, valid: card.valid_targets, drag: true });
        } else {
          el.style.translate = `${dx}px ${dy}px`;
        }
        return;
      }
      el.style.translate = `${dx}px ${dy}px`;
      const nowOver = p.y < L.playLine && pulled;
      const nowInsert = nowOver && card.type === 'MINION' ? insertIndexAt(p.x) : null;
      if (nowOver !== over || nowInsert !== insert) {
        over = nowOver;
        insert = nowInsert;
        setInsertAt(nowInsert);
        setDragOver(nowOver);
      }
    };
    const onUp = () => {
      cleanup();
      if (!active) {
        if (touch) {
          // Touch has no hover, so a tap is only ever a look: it shows the card large, and a tap
          // on the same card puts it away again. Playing takes a drag onto the table or the Play
          // button beside the enlarged card; a tap never plays. The click this tap ends in is spent
          // too: by now the enlarged card may be what lies under the finger.
          swallowClick.current = true;
          if (zoomUid === card.uid) {
            setZoomUid(null);
            hidePreview();
          } else {
            setZoomUid(card.uid);
            showBig({ card, notes: [] });
          }
          return;
        }
        setZoomUid(null);
        hidePreview();
        // A mouse click: quick play (minions go to the right end of the row).
        if (card.can_play && canAct) beginPlay(card, card.type === 'MINION' ? me.board.length : undefined);
        else if (view.your_turn && !busy && view.phase === 'PLAY') {
          flashHint(card.unplayable_reason || 'That card cannot be played right now.');
        }
        return;
      }
      if (over) {
        const drop: Held = { uid: card.uid, pos: insert ?? undefined, dx, dy, minion: card.type === 'MINION' };
        reset();
        beginPlay(card, insert ?? undefined, drop);
        return;
      }
      reset();
    };
    const onCancel = () => {
      cleanup();
      reset();
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onCancel);
  };

  // --- derived view bits -----------------------------------------------------
  const validSet = useMemo(() => new Set(targeting?.valid ?? []), [targeting]);
  const aiming = Boolean(targeting);
  const heldInHand = held && me.hand.some((c) => c.uid === held.uid) ? held : null;
  const gapAt = insertAt ?? (heldInHand && heldInHand.minion && heldInHand.pos !== undefined ? heldInHand.pos : null);
  const liftedUid = targeting?.kind === 'play' ? targeting.card.uid : chooser?.card.uid ?? zoomUid;
  /** The hand card being read after a tap, as it is now (its cost and whether it can be played may change). */
  const zoomCard = zoomUid ? me.hand.find((c) => c.uid === zoomUid) : undefined;
  const zoomPlayable = Boolean(zoomCard && zoomCard.can_play && canAct);
  const previewNotes = !preview
    ? []
    : zoomCard
      ? [
          zoomPlayable
            ? 'Press Play or drag the card onto the table. Tap anywhere to put it back.'
            : (view.your_turn && view.phase === 'PLAY' && zoomCard.unplayable_reason) || 'Tap anywhere to put it back.',
        ]
      : preview.notes;

  const nothingLeft =
    canAct &&
    !me.hand.some((c) => c.can_play) &&
    !me.board.some((m) => m.can_attack) &&
    !me.hero.can_attack &&
    !me.hero.hero_power.can_use;

  const agentMode = view.mode === 'agent_vs_human';
  /** A match on this device, against the built-in opponent. */
  const deviceMode = view.mode === 'ai_vs_human';
  const agentName = s.agent?.label || (deviceMode ? opp.name : 'Gemini 4 Hydrogen');
  const agentThinking = (agentMode || deviceMode) && Boolean(s.agent?.thinking) && view.phase !== 'GAME_OVER';
  const currentMode: OpponentMode = deviceMode ? 'device' : agentMode ? 'agent' : view.mode === 'bot_vs_human' ? 'bot' : 'cli';
  const opponentTitle = deviceMode
    ? `Against ${opp.name}, on this device`
    : agentMode
      ? `Against Antigravity (${agentName})`
      : currentMode === 'bot'
        ? 'Against the practice bot'
        : 'Against the command line';
  // Who plays the other seat can be changed mid-match on the server; on this device, how strong it plays.
  const handOver: { mode: OpponentMode; label: string }[] = deviceMode
    ? []
    : (
        [
          { mode: 'agent', label: 'Opponent: Antigravity' },
          { mode: 'bot', label: 'Opponent: practice bot' },
          { mode: 'cli', label: 'Opponent: command line' },
        ] as { mode: OpponentMode; label: string }[]
      ).filter((o) => o.mode !== currentMode);
  const otherLevels = deviceMode ? levels.filter((l) => l.id !== s.agent?.model) : [];

  const myColor = classColor(heroes, me.hero.card_class);
  const oppColor = classColor(heroes, opp.hero.card_class);

  const guidance = s.error
    ? { text: s.error, tone: 'bad' }
    : hint
      ? { text: hint, tone: 'bad' }
      : targeting
        ? {
            text:
              (targeting.kind === 'attack'
                ? 'Choose what to attack'
                : targeting.kind === 'power'
                  ? `Choose a target for ${me.hero.hero_power.name}`
                  : `Choose a target for ${targeting.card.name}`) + (fit.touch && !targeting.drag ? ' (tap the table to cancel)' : ''),
            tone: 'info',
          }
        : agentMode && s.agent?.error && !busy && view.phase === 'PLAY'
            ? { text: `${opp.name} did not answer (${s.agent.error}) The practice bot stepped in.`, tone: 'bad' }
            : deviceMode && s.agent?.error && !busy && view.phase === 'PLAY'
              ? { text: `${opp.name} got stuck (${s.agent.error}); the practice bot finished its move.`, tone: 'bad' }
            : view.phase === 'PLAY' && !view.your_turn && !busy && view.mode === 'cli_vs_human'
              ? { text: `Waiting for ${opp.name} (./hs)`, tone: 'wait' }
              : view.waiting_for_opponent_choice
            ? { text: `${opp.name} is choosing…`, tone: 'wait' }
            : !s.online
              ? { text: 'Connection lost, retrying…', tone: 'bad' }
              : null;

  const handStyle = (i: number, n: number): React.CSSProperties => {
    const mid = (n - 1) / 2;
    const step = n <= 1 ? 0 : Math.min(L.handStep, L.handSpread / (n - 1));
    const off = (i - mid) * step;
    const rot = (i - mid) * (n > 7 ? 2.1 : 3.1);
    const drop = Math.pow(Math.abs(i - mid), 2) * (n > 7 ? 1.0 : 1.8);
    return { left: `${L.handCx + off - L.cardW / 2}px`, top: `${L.handTop + drop}px`, ['--rot' as any]: `${rot}deg`, zIndex: 10 + i };
  };

  const oppBackStyle = (i: number, n: number): React.CSSProperties => {
    const mid = (n - 1) / 2;
    const step = n <= 1 ? 0 : Math.min(44, 300 / (n - 1));
    return { left: `${(i - mid) * step - 42}px`, ['--rot' as any]: `${(mid - i) * 2}deg`, top: `${-Math.pow(Math.abs(i - mid), 2) * 0.7}px` };
  };

  const renderHero = (side: typeof me | typeof opp, mine: boolean) => {
    const h = side.hero;
    const color = mine ? myColor : oppColor;
    const active = view.phase === 'PLAY' && view.active_seat === side.seat;
    const cls = [
      'hero',
      mine ? 'hero-mine' : 'hero-theirs',
      active ? 'is-active' : '',
      validSet.has(h.id) ? 'is-targetable' : '',
      aiming && !validSet.has(h.id) ? 'is-dimmed' : '',
      mine && h.can_attack && canAct && !aiming ? 'is-ready' : '',
      targeting?.kind === 'attack' && targeting.source === h.id ? 'is-selected' : '',
      h.frozen ? 'is-frozen' : '',
      h.immune ? 'is-immune' : '',
      h.attack > 0 ? 'has-attack' : '',
      view.phase === 'GAME_OVER' && h.hp <= 0 ? 'is-defeated' : '',
    ]
      .filter(Boolean)
      .join(' ');
    return (
      <div
        className={cls}
        data-uid={h.id}
        style={{ ['--class' as any]: color }}
        onPointerDown={mine ? (e) => startAttack(e, h.id, h.legal_attack_targets, h.can_attack) : undefined}
        onClick={() => clickCharacter(h.id)}
      >
        <div className="hero-art">
          <Art id={heroArt(h)} alt={h.name} tint={color} />
        </div>
        <div className="hero-frost" />
        <div className="hero-label">
          <strong>{h.name}</strong>
          <span>
            {side.name}
            {mine && myTitle ? ` · ${myTitle}` : ''}
          </span>
        </div>
        {side.secrets.length > 0 && (
          <div className="hero-secrets">
            {side.secrets.map((sec) => (
              <span
                key={sec.uid}
                className="seal"
                data-secret={sec.uid}
                style={{ ['--class' as any]: classColor(heroes, sec.card_class) }}
                title={sec.name || 'Secret'}
              >
                <i>?</i>
              </span>
            ))}
          </div>
        )}
        {h.attack > 0 && (
          <div className="badge atk">
            <Num value={h.attack} />
          </div>
        )}
        {h.armor > 0 && (
          <div className="badge armor">
            <Num value={h.armor} />
          </div>
        )}
        <div className="badge hp big">
          <Num value={Math.max(0, h.hp)} tone={h.hp < h.max_hp ? 'down' : ''} />
        </div>
        {!mine && agentThinking && (
          <div className="thinking" title={`${agentName} is thinking`}>
            <i />
            <i />
            <i />
          </div>
        )}
        {emote && emote.seat === side.seat && (
          <div className="emote" key={`emote-${emote.id}`}>
            {emote.text}
          </div>
        )}
      </div>
    );
  };

  const renderWeapon = (w: WeaponView | null, seat: string, color: string) =>
    w ? (
      <div
        className="weapon"
        data-weapon={seat}
        style={{ ['--class' as any]: color }}
        onPointerDown={(e) => pressPreview(e, () => ({
            card: {
              card_id: w.card_id,
              name: w.name,
              card_class: seat === me.seat ? me.hero.card_class : opp.hero.card_class,
              type: 'WEAPON',
              cost: 0,
              attack: w.attack,
              health: null,
              durability: w.durability,
              rarity: 'FREE',
              race: null,
              text: w.text,
              mechanics: w.windfury ? ['WINDFURY'] : [],
            },
            notes: [],
          }))}
            onPointerEnter={(e) =>
          showPreview(e, () => ({
            card: {
              card_id: w.card_id,
              name: w.name,
              card_class: seat === me.seat ? me.hero.card_class : opp.hero.card_class,
              type: 'WEAPON',
              cost: 0,
              attack: w.attack,
              health: null,
              durability: w.durability,
              rarity: 'FREE',
              race: null,
              text: w.text,
              mechanics: w.windfury ? ['WINDFURY'] : [],
            },
            notes: [],
          }))
        }
        onPointerLeave={hidePreview}
      >
        <div className="weapon-art">
          <Art id={w.card_id} alt={w.name} />
        </div>
        <div className="badge atk">
          <Num value={w.attack} />
        </div>
        <div className="badge dur">
          <Num value={w.durability} />
        </div>
      </div>
    ) : (
      <div className="weapon weapon-empty" aria-hidden="true" />
    );

  const renderMana = (side: typeof me | typeof opp, mine: boolean) => (
    <div className={`mana ${mine ? 'mana-mine' : 'mana-theirs'}`}>
      <div className="mana-num">
        <Num value={side.mana} />
        <span className="mana-max">/{side.max_mana}</span>
      </div>
      <div className="mana-pips">
        {Array.from({ length: 10 }).map((_, i) => {
          const locked = i >= side.max_mana - side.overloaded && i < side.max_mana;
          const st = i >= side.max_mana ? 'none' : i < side.mana ? 'full' : locked ? 'locked' : 'spent';
          return <i key={i} className={`pip pip-${st}`} style={{ transitionDelay: `${i * 28}ms` }} />;
        })}
      </div>
      {side.pending_overload > 0 && (
        <div className="mana-note" title="Locked next turn">
          <Icon name="lock" /> {side.pending_overload} next turn
        </div>
      )}
    </div>
  );

  const renderDeck = (side: typeof me | typeof opp) => (
    <div
      className={`deck ${side.seat === me.seat ? 'deck-mine' : 'deck-theirs'} ${side.deck_count === 0 ? 'deck-empty' : ''}`}
      data-deck={side.seat}
      title={`${side.deck_count} cards left`}
    >
      {side.deck_count > 2 && <CardBack className="deck-layer l3" art={side.seat === me.seat ? myBack : undefined} />}
      {side.deck_count > 1 && <CardBack className="deck-layer l2" art={side.seat === me.seat ? myBack : undefined} />}
      {side.deck_count > 0 ? <CardBack className="deck-layer l1" art={side.seat === me.seat ? myBack : undefined} /> : <div className="deck-slot" />}
      <div className="deck-count">
        <Num value={side.deck_count} />
      </div>
      {side.fatigue > 0 && <div className="deck-fatigue">Fatigue {side.fatigue}</div>}
    </div>
  );

  const renderRow = (side: typeof me | typeof opp, mine: boolean) => {
    const tiles = side.board.map((m) => (
      <MinionTile
        key={m.uid}
        minion={m}
        friendly={mine}
        ready={mine && m.can_attack && canAct && !aiming}
        selected={targeting?.kind === 'attack' && targeting.source === m.uid}
        targetable={validSet.has(m.uid)}
        dimmed={aiming && !validSet.has(m.uid) && !(targeting?.kind === 'attack' && targeting.source === m.uid)}
        onPointerDown={(e) => {
          pressPreview(e, minionPreview(m));
          if (mine) startAttack(e, m.uid, m.legal_attack_targets, m.can_attack);
        }}
        onClick={() => clickCharacter(m.uid)}
        onEnter={(e) => showPreview(e, minionPreview(m))}
        onLeave={hidePreview}
      />
    ));
    if (mine && gapAt !== null) {
      tiles.splice(Math.min(gapAt, tiles.length), 0, <div key="gap" className="slot slot-gap" aria-hidden="true" />);
    }
    return (
      <div className={`row ${mine ? 'row-mine' : 'row-theirs'} ${mine && insertAt !== null ? 'is-dropzone' : ''}`}>
        {tiles}
        {side.board.length === 0 && gapAt === null && <div className="row-empty" />}
      </div>
    );
  };

  const stageSeatMine = s.stage?.seat === me.seat;

  return (
    <div
      className={`arena ${aiming ? 'is-aiming' : ''}`}
      data-playing={s.playing ? 'yes' : 'no'}
      style={{ ['--mine' as any]: myColor, ['--theirs' as any]: oppColor }}
      // A long press reads a card here; the browser's own menu (save image…) must not open over it.
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="safe-area" ref={safeRef} aria-hidden="true" />
      {fit.upright && (
        <div className="rotate-hint" role="status">
          <svg viewBox="0 0 64 64" aria-hidden="true">
            <rect x="22" y="8" width="20" height="36" rx="4" />
            <path d="M12 50a22 22 0 0 0 38 6M50 56l1-9M50 56l-9-1" />
          </svg>
          <strong>Turn your phone sideways</strong>
          <span>The table needs the long side.</span>
        </div>
      )}
      <div
        className={`table layout-${L.name} ${fit.touch ? 'is-touch' : ''} ${fit.ui > 1.15 ? 'is-small' : ''}`}
        ref={tableRef}
        style={{
          width: L.w,
          height: L.h,
          transform: `translate(${fit.x}px, ${fit.y}px) scale(${fit.k})`,
          ['--ui' as any]: fit.ui.toFixed(3),
        }}
        onPointerDownCapture={(e) => {
          swallowClick.current = false;
          // A card shown large is being read. The next touch only puts it away, whatever it lands
          // on: a piece, the hero power, End turn. (The hand looks after its own taps, which never
          // play, and the Play button is the one way through.)
          if (!preview?.big) return;
          if ((e.target as HTMLElement).closest('.preview-play,[data-card]')) return;
          e.stopPropagation();
          swallowClick.current = true;
          setZoomUid(null);
          hidePreview();
        }}
        onClickCapture={(e) => {
          if (!swallowClick.current) return;
          swallowClick.current = false;
          e.stopPropagation();
          e.preventDefault();
        }}
        onClick={(e) => {
          if ((e.target as HTMLElement).closest('[data-uid],[data-card],[data-power],button,.popover,.preview')) return;
          setShowEmotes(false);
          setZoomUid(null);
          hidePreview();
          const t = targetingRef.current;
          if (t && !t.drag) cancelAll();
        }}
      >
        <div className={`felt ${tableArt ? 'has-art' : ''}`} style={tableArt ? { ['--felt-art' as any]: `url(${tableArt})` } : undefined} aria-hidden="true">
          <div className="lane lane-theirs" />
          <div className="lane lane-mine" />
          <div className="midline" />
        </div>

        {/* ---- opponent ---- */}
        <div className="opp-hand" data-zone="opphand">
          {Array.from({ length: opp.hand_count }).map((_, i) => (
            <CardBack key={i} className="opp-card" data-oppcard={i} data-flip={`o:${i}`} style={oppBackStyle(i, opp.hand_count)} />
          ))}
        </div>
        <div className="cluster cluster-theirs">
          {renderWeapon(opp.weapon, opp.seat, oppColor)}
          {renderHero(opp, false)}
          <div
            className={`power power-theirs ${opp.hero.hero_power.used ? 'is-used' : ''}`}
            data-power={opp.seat}
            style={{ ['--class' as any]: oppColor }}
            onPointerDown={(e) => pressPreview(e, () => ({
                card: {
                  card_id: opp.hero.hero_power.id,
                  name: opp.hero.hero_power.name,
                  card_class: opp.hero.card_class,
                  type: 'HERO_POWER',
                  cost: opp.hero.hero_power.cost,
                  attack: null,
                  health: null,
                  durability: null,
                  rarity: 'FREE',
                  race: null,
                  text: opp.hero.hero_power.text,
                  mechanics: [],
                },
                notes: [],
              }))}
            onPointerEnter={(e) =>
              showPreview(e, () => ({
                card: {
                  card_id: opp.hero.hero_power.id,
                  name: opp.hero.hero_power.name,
                  card_class: opp.hero.card_class,
                  type: 'HERO_POWER',
                  cost: opp.hero.hero_power.cost,
                  attack: null,
                  health: null,
                  durability: null,
                  rarity: 'FREE',
                  race: null,
                  text: opp.hero.hero_power.text,
                  mechanics: [],
                },
                notes: [],
              }))
            }
            onPointerLeave={hidePreview}
          >
            <Art id={opp.hero.hero_power.id} alt={opp.hero.hero_power.name} />
            <span className="power-cost">{opp.hero.hero_power.cost}</span>
          </div>
        </div>
        {renderMana(opp, false)}
        {renderDeck(opp)}
        {renderRow(opp, false)}

        {/* ---- centre band ---- */}
        <div className="band">
          {guidance &&<div className={`guide guide-${guidance.tone}`}>{guidance.text}</div>}
          {me.spell_damage > 0 && (
            <div className="status-chip">
              <Icon name="spark" /> Spell damage +{me.spell_damage}
            </div>
          )}
        </div>
        {view.phase === 'PLAY' && (
          <button
            type="button"
            className={`end-turn ${view.your_turn ? 'mine' : 'theirs'} ${nothingLeft ? 'is-done' : ''}`}
            disabled={!canAct || aiming}
            onClick={() => {
              cancelAll();
              void act((since) => actions.endTurn(gameId, since));
            }}
          >
            {view.your_turn ? 'End turn' : 'Their turn'}
          </button>
        )}

        {/* ---- you ---- */}
        {renderRow(me, true)}
        <div className="cluster cluster-mine">
          {renderWeapon(me.weapon, me.seat, myColor)}
          {renderHero(me, true)}
          <button
            type="button"
            className={`power power-mine ${me.hero.hero_power.can_use && canAct ? 'is-ready' : ''} ${me.hero.hero_power.used ? 'is-used' : ''} ${targeting?.kind === 'power' ? 'is-selected' : ''}`}
            data-power={me.seat}
            style={{ ['--class' as any]: myColor }}
            onClick={clickPower}
            onPointerDown={(e) => pressPreview(e, () => ({
                card: {
                  card_id: me.hero.hero_power.id,
                  name: me.hero.hero_power.name,
                  card_class: me.hero.card_class,
                  type: 'HERO_POWER',
                  cost: me.hero.hero_power.cost,
                  attack: null,
                  health: null,
                  durability: null,
                  rarity: 'FREE',
                  race: null,
                  text: me.hero.hero_power.text,
                  mechanics: [],
                },
                notes: me.hero.hero_power.used ? ['Used this turn'] : [],
              }))}
            onPointerEnter={(e) =>
              showPreview(e, () => ({
                card: {
                  card_id: me.hero.hero_power.id,
                  name: me.hero.hero_power.name,
                  card_class: me.hero.card_class,
                  type: 'HERO_POWER',
                  cost: me.hero.hero_power.cost,
                  attack: null,
                  health: null,
                  durability: null,
                  rarity: 'FREE',
                  race: null,
                  text: me.hero.hero_power.text,
                  mechanics: [],
                },
                notes: me.hero.hero_power.used ? ['Used this turn'] : [],
              }))
            }
            onPointerLeave={hidePreview}
          >
            <Art id={me.hero.hero_power.id} alt={me.hero.hero_power.name} />
            <span className="power-cost">{me.hero.hero_power.cost}</span>
          </button>
        </div>
        {renderMana(me, true)}
        {renderDeck(me)}

        {/* ---- recent plays ---- */}
        <div className="history" aria-label="Recent plays">
          {s.history.slice(0, 5).map((h) => (
            <div
              key={h.key}
              className={`hist ${h.seat === me.seat ? 'mine' : 'theirs'} hist-${h.kind}`}
              onPointerDown={(e) => pressPreview(e, () =>
                  h.card
                    ? { card: h.card, notes: [h.seat === me.seat ? 'You played this' : `${opp.name} played this`] }
                    : null)}
            onPointerEnter={(e) =>
                showPreview(e, () =>
                  h.card
                    ? { card: h.card, notes: [h.seat === me.seat ? 'You played this' : `${opp.name} played this`] }
                    : null,
                )
              }
              onPointerLeave={hidePreview}
            >
              {h.kind === 'secret' && !h.card ? <span className="hist-q">?</span> : <Art id={h.artId} alt={h.name} />}
            </div>
          ))}
        </div>

        {/* ---- the card being resolved ---- */}
        {s.stage && (
          <div className={`stage stage-${s.stage.tone} ${stageSeatMine ? 'mine' : 'theirs'}`} data-stage key={`stage-${s.stage.key}`}>
            {s.stage.card ? (
              <CardFace card={s.stage.card} heroes={heroes} />
            ) : (
              <CardBack className="stage-back" art={stageSeatMine ? myBack : undefined} style={{ ['--class' as any]: classColor(heroes, s.stage.cardClass) }} />
            )}
            {s.stage.label && <div className="stage-label">{s.stage.label}</div>}
          </div>
        )}

        {/* ---- your hand ---- */}
        <div className={`hand ${dragUid || aiming || chooser ? 'no-hover' : ''}`} data-zone="hand">
          {(view.phase === 'MULLIGAN' && !me.mulligan_done ? [] : me.hand).map((c, i) => {
            const isHeld = heldInHand?.uid === c.uid;
            const cls = [
              'hand-slot',
              c.can_play && canAct ? 'is-playable' : '',
              c.can_play && canAct && c.combo_glow ? 'is-combo' : '',
              dragUid === c.uid ? 'is-dragging' : '',
              dragUid === c.uid && dragOver ? 'is-over-board' : '',
              isHeld ? 'is-held' : '',
              liftedUid === c.uid && !isHeld ? 'is-lifted' : '',
            ]
              .filter(Boolean)
              .join(' ');
            const st = handStyle(i, me.hand.length);
            if (isHeld) st.translate = `${heldInHand!.dx}px ${heldInHand!.dy}px`;
            return (
              <div
                key={c.uid}
                className={cls}
                data-card={c.uid}
                data-flip={`c:${c.uid}`}
                style={st}
                onPointerDown={(e) => onCardPointerDown(e, c)}
                onPointerEnter={() => {
                  if (!dragUid && !aiming) sfx.cardHover();
                }}
              >
                <CardFace card={c} heroes={heroes} />
              </div>
            );
          })}
        </div>

        {/* ---- aiming ---- */}
        {targeting && (
          <svg className="arrow-layer" viewBox={`0 0 ${L.w} ${L.h}`} width={L.w} height={L.h} aria-hidden="true">
            <g ref={arrowRef} className="arrow" style={{ opacity: 0 }}>
              <path ref={arrowPathRef} className="arrow-glow" />
              <path ref={arrowLineRef} className="arrow-line" />
              <g ref={arrowHeadRef} className="arrow-head">
                <path d="M -26 -15 L 6 0 L -26 15 L -17 0 Z" />
                <circle r="30" />
              </g>
            </g>
          </svg>
        )}

        {/* ---- hover preview ---- */}
        {/* (a finger resting on one of your own ready pieces also starts aiming: the look still shows) */}
        {preview && !dragUid && (!aiming || (preview.big && !zoomUid)) && (
          <div
            className={`preview ${preview.big ? 'preview-big' : ''} ${zoomCard ? 'is-zoom' : ''}`}
            style={{ left: preview.x, top: preview.y, ['--pw' as any]: `${preview.big ? bigCardWidth(L.h) : 236}px` }}
          >
            <CardFace card={zoomCard ?? preview.card} heroes={heroes} live={preview.live} />
            {zoomCard && zoomPlayable && (
              <button
                type="button"
                className="btn primary preview-play"
                onClick={() => {
                  const card = zoomCard;
                  setZoomUid(null);
                  beginPlay(card, card.type === 'MINION' ? me.board.length : undefined);
                }}
              >
                Play
              </button>
            )}
            {previewNotes.length > 0 && (
              <ul className="preview-notes">
                {previewNotes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* ---- turn banner ---- */}
        {s.banner && (
          <div
            className={`banner banner-${s.banner.kind}`}
            key={`banner-${s.banner.key}`}
            aria-live="polite"
            onAnimationEnd={(e) => {
              if (e.target === e.currentTarget) s.clearBanner();
            }}
          >
            <span>{s.banner.text}</span>
          </div>
        )}

        <div className="fx-layer" ref={layerRef} aria-hidden="true" />

        {/* ---- corner controls ---- */}
        <div className="corner">
          <button type="button" className="chip-btn" onClick={() => setShowMenu(true)} title="Menu (Esc)">
            Menu
          </button>
          <button type="button" className={`chip-btn ${showLog ? 'on' : ''}`} onClick={() => setShowLog((v) => !v)}>
            Log
          </button>
          <div className="emote-box">
            <button type="button" className="chip-btn" onClick={() => setShowEmotes((v) => !v)}>
              Say
            </button>
            {showEmotes && (
              <div className="popover">
                {EMOTES.map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => {
                      setShowEmotes(false);
                      void sendEmote(gameId, m).catch(() => undefined);
                    }}
                  >
                    {m}
                  </button>
                ))}
              </div>
            )}
          </div>

        </div>
        {showLog && (
          <aside className="log">
            <header>
              <strong>Log</strong>
              <button type="button" className="chip-btn" onClick={() => setShowLog(false)}>
                Close
              </button>
            </header>
            <ol>
              {[...view.log].reverse().map((entry) => (
                <li key={entry.id} className={entry.seat === me.seat ? 'mine' : entry.seat ? 'theirs' : ''}>
                  {entry.text}
                </li>
              ))}
            </ol>
          </aside>
        )}

        {/* ---- choose one ---- */}
        {chooser && (
          <div className="overlay overlay-light" onClick={cancelAll}>
            <div className="sheet" onClick={(e) => e.stopPropagation()}>
              <h2>{chooser.card.name}</h2>
              <p className="sheet-sub">Choose one</p>
              <div className="options">
                {chooser.card.choose_options.map((opt) => (
                  <button
                    key={opt.index}
                    type="button"
                    className="option"
                    disabled={!opt.playable}
                    onClick={() => {
                      const { card, pos } = chooser;
                      setChooser(null);
                      continuePlay(card, pos, opt.index, opt.target_rule, opt.valid_targets);
                    }}
                  >
                    <strong>{opt.label}</strong>
                    <span>{opt.description}</span>
                  </button>
                ))}
              </div>
              <button type="button" className="btn ghost" onClick={cancelAll}>
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* ---- pick a card ---- */}
        {view.pending_choice && !s.playing && (
          <div className="overlay">
            <div className="sheet sheet-wide">
              <h2>
                {view.pending_choice.choice_type === 'DISCOVER_HERO_POWER'
                  ? 'Discover a Hero Power'
                  : view.pending_choice.choice_type === 'TOTEM'
                    ? 'Choose a Totem'
                    : view.pending_choice.choice_type === 'DISCOVER'
                      ? 'Discover a card'
                      : 'Choose a card'}
              </h2>
              <p className="sheet-sub">
                {view.pending_choice.choice_type === 'DISCOVER_HERO_POWER'
                  ? 'Replace your current Hero Power.'
                  : view.pending_choice.choice_type === 'TOTEM'
                    ? 'Summon it onto the battlefield.'
                    : view.pending_choice.choice_type === 'DISCOVER'
                      ? 'Add one to your hand.'
                      : 'The others are discarded.'}
              </p>
              <div className="card-row">
                {view.pending_choice.options.map((opt, idx) => (
                  <button
                    key={opt.uid}
                    type="button"
                    className="pick"
                    disabled={busy}
                    onClick={() => void act((since) => actions.choose(gameId, since, idx))}
                  >
                    <CardFace card={opt} heroes={heroes} />
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ---- waiting for the other side's deck ---- */}
        {view.phase === 'WAITING_FOR_P2_DECK' && (
          <div className="overlay">
            <div className="sheet">
              <h2>{agentMode ? 'Choosing a deck' : 'Waiting for a deck'}</h2>
              {agentMode ? (
                <p className="sheet-sub">{agentName} is picking the deck it will play.</p>
              ) : (
                <>
                  <p className="sheet-sub">
                    Match <code>{view.game_id}</code> is ready. The opponent picks a deck from the command line:
                  </p>
                  <pre className="code">./hs deck MAGE</pre>
                </>
              )}
              <button type="button" className="btn ghost" onClick={onLeaveToLobby}>
                Back to lobby
              </button>
            </div>
          </div>
        )}

        {/* ---- opening hand ---- */}
        {view.phase === 'MULLIGAN' && (!me.mulligan_done || !opp.mulligan_done) && (
          <div className="overlay">
            <div className="sheet sheet-wide">
              {!me.mulligan_done ? (
                <>
                  <h2>Opening hand</h2>
                  <p className="sheet-sub">
                    Tap the cards you want to swap. {me.hand.length >= 4 ? 'You go second.' : 'You go first.'}
                  </p>
                  <div className="card-row">
                    {me.hand.map((c) => (
                      <button
                        key={c.uid}
                        type="button"
                        className={`pick ${swap.has(c.index) ? 'is-swapped' : ''}`}
                        onClick={() =>
                          setSwap((cur) => {
                            const next = new Set(cur);
                            if (next.has(c.index)) next.delete(c.index);
                            else next.add(c.index);
                            return next;
                          })
                        }
                      >
                        <CardFace card={c} heroes={heroes} />
                        <span className="pick-tag">Swap</span>
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="btn primary"
                    disabled={busy}
                    onClick={() => {
                      const picks = Array.from(swap);
                      setSwap(new Set());
                      void act((since) => actions.mulligan(gameId, since, picks));
                    }}
                  >
                    {swap.size ? `Swap ${swap.size} and start` : 'Keep all and start'}
                  </button>
                </>
              ) : (
                <>
                  <h2>Hand locked in</h2>
                  <p className="sheet-sub">
                    {agentMode
                      ? `${agentName} is looking at its opening hand…`
                      : `Waiting for ${opp.name}${view.mode === 'cli_vs_human' ? ' (./hs mulligan …)' : ''}.`}
                  </p>
                </>
              )}
            </div>
          </div>
        )}

        {/* ---- result ---- */}
        {view.phase === 'GAME_OVER' && !s.playing && (
          <div className={`overlay result ${view.winner === me.seat ? 'won' : view.winner === 'draw' ? 'drawn' : 'lost'}`}>
            <div className="result-body">
              <h1>{view.winner === me.seat ? 'Victory' : view.winner === 'draw' ? 'Draw' : 'Defeat'}</h1>
              <p>
                {view.winner === me.seat
                  ? `${opp.hero.name} has fallen.`
                  : view.winner === 'draw'
                    ? 'Both heroes fell at once.'
                    : `${opp.name} takes this one.`}
              </p>
              {record && (
                <div className={`result-progress ${record.newBest ? 'is-rank-up' : ''}`}>
                  {record.newBest && (
                    <div className="result-rankup">
                      New rank: <strong>{RANKS[record.rankAfter].name}</strong>
                    </div>
                  )}
                  <div className="result-standing">
                    <RankBadge index={record.rankAfter} />
                    <RankLine rating={record.after} />
                    <span className={`result-delta ${record.after < record.before ? 'down' : 'up'}`}>{formatDelta(record.before, record.after)}</span>
                  </div>
                  <div className="result-packs">
                    <PackIcon className={record.packs > 0 ? 'is-ready' : ''} />
                    <PackMeter meter={record.meterAfter} fresh={record.packs > 0 ? record.meterAfter : record.steps} />
                    <span>
                      {record.packs > 0
                        ? record.packs === 1
                          ? 'A lantern earned'
                          : `${record.packs} lanterns earned`
                        : `${PACK_STEPS - record.meterAfter} more ${PACK_STEPS - record.meterAfter === 1 ? 'win' : 'wins'} for a lantern`}
                    </span>
                  </div>
                </div>
              )}
              <div className="result-actions">
                {record && profile.packs > 0 && (
                  <button type="button" className="btn primary" onClick={onOpenPack}>
                    Light a lantern{profile.packs > 1 ? ` (${profile.packs})` : ''}
                  </button>
                )}
                <button type="button" className={`btn ${record && profile.packs > 0 ? '' : 'primary'}`} onClick={onLeaveToLobby}>
                  Play again
                </button>
                <button type="button" className="btn ghost" onClick={onLeaveToMenu}>
                  Main menu
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ---- menu ---- */}
        {showMenu && (
          <div className="overlay" onClick={() => setShowMenu(false)}>
            <div className="sheet" onClick={(e) => e.stopPropagation()}>
              <h2>Paused</h2>
              <p className="sheet-sub">
                {opponentTitle} · match <code>{view.game_id}</code>
              </p>
              <div className="menu-list">
                <button type="button" className="btn primary" onClick={() => setShowMenu(false)}>
                  Resume
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    sfx.setMusicEnabled(!musicOn);
                    setMusicOn(!musicOn);
                  }}
                >
                  Music: {musicOn ? 'on' : 'off'}
                </button>
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    sfx.setEnabled(!sfxOn);
                    setSfxOn(!sfxOn);
                  }}
                >
                  Sound effects: {sfxOn ? 'on' : 'off'}
                </button>
                <button type="button" className="btn" onClick={() => s.setFast(!s.fast)}>
                  Animations: {s.fast ? 'fast' : 'normal'}
                </button>
                {view.phase !== 'GAME_OVER' &&
                  handOver.map((o) => (
                    <button
                      key={o.mode}
                      type="button"
                      className="btn"
                      onClick={() => {
                        setShowMenu(false);
                        void act((since) => actions.switchMode(gameId, since, o.mode));
                      }}
                    >
                      {o.label}
                    </button>
                  ))}
                {view.phase !== 'GAME_OVER' &&
                  otherLevels.map((l) => (
                    <button
                      key={l.id}
                      type="button"
                      className="btn"
                      onClick={() => {
                        setShowMenu(false);
                        void act((since) => actions.setLevel(gameId, since, l.id));
                      }}
                    >
                      Opponent: {l.label.toLowerCase()} ({l.name})
                    </button>
                  ))}
                {view.phase !== 'GAME_OVER' && (
                  <button
                    type="button"
                    className="btn danger"
                    onClick={() => {
                      setShowMenu(false);
                      cancelAll();
                      void act((since) => actions.concede(gameId, since));
                    }}
                  >
                    Concede
                  </button>
                )}
                <button type="button" className="btn ghost" onClick={onLeaveToLobby}>
                  Lobby
                </button>
                <button type="button" className="btn ghost" onClick={onLeaveToMenu}>
                  Main menu
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
