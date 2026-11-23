// One match as the browser sees it: follows it, queues incoming beats and
// plays them back in order, one animation at a time.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { artUrl, followGame } from '../api';
import { sfx } from '../sound';
import type { AgentStatus, Beat, CardDef, GameEvent, GameStateView, HeroMeta, Seat, StatePayload } from '../types';
import { Director, type StageCard } from './director';
import { Fx, reducedMotion } from './fx';
import { movable, withLiveRules } from './live';
import { applyEvents } from './reduce';

export interface HistoryEntry {
  key: number;
  seat: Seat;
  kind: 'play' | 'power' | 'secret';
  card: CardDef | null;
  cardClass: string;
  artId: string | null;
  name: string;
  text: string;
}

export interface BannerState {
  key: number;
  text: string;
  kind: 'mine' | 'theirs';
}

type QueueItem = { beat: Beat } | { jump: GameStateView };

const warmed = new Set<string>();

/** Start loading the art a beat is about to show, so it is there when the card appears. */
function warmArt(beat: Beat): void {
  for (const ev of beat.events) {
    const id: string | undefined = ev.card?.id ?? ev.minion?.card_id ?? ev.weapon?.card_id;
    if (!id || warmed.has(id)) continue;
    warmed.add(id);
    const img = new Image();
    img.src = artUrl(id);
  }
}

const SPEED_KEY = 'game_speed';

/** Builds an action's request when its turn to be sent comes: `now` is the newest state then. */
export type Send = (since: number, now: GameStateView) => Promise<StatePayload>;

export function useSession(gameId: string, initial: GameStateView, heroes: Record<string, HeroMeta>) {
  const [view, setView] = useState<GameStateView>(initial);
  /** The newest state known: the shown one catches up with it as the animations play. */
  const [ahead, setAhead] = useState<GameStateView>(initial);
  const [playing, setPlaying] = useState(false);
  const [pending, setPending] = useState(0);
  /** End turn has been sent and not answered yet: no more moves are taken meanwhile. */
  const [passing, setPassing] = useState(0);
  const [stage, setStageState] = useState<StageCard | null>(null);
  const [banner, setBanner] = useState<BannerState | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [error, setError] = useState('');
  const [online, setOnline] = useState(true);
  const [agent, setAgent] = useState<AgentStatus | null>(null);
  const [fast, setFastState] = useState(() => localStorage.getItem(SPEED_KEY) === 'fast');

  const viewRef = useRef(initial);
  const latest = useRef(initial);
  const queue = useRef<QueueItem[]>([]);
  const queuedSeq = useRef(initial.seq);
  const running = useRef(false);
  const alive = useRef(true);
  const fxRef = useRef<Fx | null>(null);
  const directorRef = useRef<Director | null>(null);
  const finalRef = useRef<GameStateView | null>(null);
  const keyRef = useRef(0);
  const heroesRef = useRef(heroes);
  heroesRef.current = heroes;
  const fastRef = useRef(fast);
  fastRef.current = fast;
  /** Actions go out one at a time, in the order they were made. */
  const sending = useRef<Promise<unknown>>(Promise.resolve());
  /** Moves made after one that was refused were planned on it: they are dropped. */
  const plan = useRef(0);

  const viewer: Seat = initial.viewer_seat;

  const commit = useCallback((next: GameStateView) => {
    viewRef.current = next;
    flushSync(() => setView(next));
  }, []);

  const historyFrom = useCallback((events: GameEvent[]): HistoryEntry[] => {
    const out: HistoryEntry[] = [];
    for (const ev of events) {
      if (ev.t === 'play') {
        const c: CardDef | null = ev.card;
        out.push({
          key: ++keyRef.current,
          seat: ev.seat!,
          kind: ev.secret ? 'secret' : 'play',
          card: c,
          cardClass: ev.card_class,
          artId: c ? c.id : null,
          name: c ? c.name : 'Secret',
          text: c ? c.text : '',
        });
      } else if (ev.t === 'hero_power') {
        out.push({
          key: ++keyRef.current,
          seat: ev.seat!,
          kind: 'power',
          card: null,
          cardClass: '',
          artId: ev.id,
          name: ev.name,
          text: '',
        });
      }
    }
    return out;
  }, []);

  const pushHistory = useCallback(
    (events: GameEvent[]) => {
      const adds = historyFrom(events);
      if (adds.length) setHistory((h) => [...adds.reverse(), ...h].slice(0, 7));
    },
    [historyFrom],
  );

  const apply = useCallback(
    (events: GameEvent[]) => {
      const fx = fxRef.current;
      const before = fx?.snapshot();
      const next = applyEvents(viewRef.current, events, finalRef.current);
      viewRef.current = next;
      flushSync(() => {
        setView(next);
        pushHistory(events);
      });
      if (fx && before) fx.flip(before);
    },
    [pushHistory],
  );

  const pump = useCallback(async () => {
    if (running.current) return;
    running.current = true;
    setPlaying(true);
    try {
      while (queue.current.length && alive.current) {
        const item = queue.current.shift()!;
        const fx = fxRef.current;
        const director = directorRef.current;
        if ('jump' in item) {
          director?.reset();
          commit(item.jump);
          continue;
        }
        const beat = item.beat;
        const skip = !fx || !director || document.hidden || reducedMotion() || queue.current.length > 16;
        if (skip) {
          director?.reset();
          pushHistory(beat.events);
          commit(beat.state);
          continue;
        }
        finalRef.current = beat.state;
        await director.playBeat(beat);
        finalRef.current = null;
        if (!alive.current) return;
        const before = fx.snapshot();
        commit(beat.state);
        fx.flip(before);
        // A pause between the other side's moves, so each reads as its own decision.
        if (queue.current.length && director.showingTheirs) await fx.sleep(600);
      }
      // Idle: show the newest state we hold (covers emotes and other silent changes).
      if (alive.current && latest.current !== viewRef.current && latest.current.seq >= viewRef.current.seq) {
        commit(latest.current);
      }
    } finally {
      running.current = false;
      if (alive.current) setPlaying(false);
    }
    if (queue.current.length && alive.current) void pump();
  }, [commit, pushHistory, viewer]);

  const ingest = useCallback(
    (p: StatePayload) => {
      if (!p || !p.state || p.state.seq < latest.current.seq) return;
      if (p.agent !== undefined) {
        const next = p.agent;
        // Replies and pushes can arrive out of order: never go back to an older status.
        setAgent((cur) => (cur && next && next.rev <= cur.rev ? cur : next));
      }
      latest.current = p.state;
      setAhead(p.state);
      const jumpTo = (state: GameStateView) => {
        queue.current.push({ jump: state });
        queuedSeq.current = state.seq;
      };
      if (p.beats === null || p.beats === undefined) {
        if (p.state.seq !== queuedSeq.current) jumpTo(p.state);
      } else {
        let broken = false;
        for (const b of p.beats) {
          if (b.seq <= queuedSeq.current) continue;
          if (b.prev !== queuedSeq.current) {
            broken = true;
            break;
          }
          warmArt(b);
          queue.current.push({ beat: b });
          queuedSeq.current = b.seq;
        }
        if (broken || p.state.seq > queuedSeq.current) jumpTo(p.state);
      }
      void pump();
    },
    [pump],
  );

  // Follow the match, wherever it lives (the server, or the engine on this device).
  useEffect(() => {
    alive.current = true;
    const stop = followGame(gameId, viewer, () => queuedSeq.current, ingest, setOnline);
    return () => {
      alive.current = false;
      stop();
    };
  }, [gameId, viewer, ingest]);

  // Coming back to a hidden tab: drop whatever animation state was left half way.
  useEffect(() => {
    const onVis = () => {
      if (!document.hidden && !running.current) {
        directorRef.current?.reset();
      }
    };
    document.addEventListener('visibilitychange', onVis);
    return () => document.removeEventListener('visibilitychange', onVis);
  }, []);

  const bind = useCallback(
    (root: HTMLElement | null, layer: HTMLElement | null) => {
      if (!root || !layer) {
        fxRef.current = null;
        directorRef.current = null;
        return;
      }
      const fx = new Fx(root, layer);
      fxRef.current = fx;
      directorRef.current = new Director({
        fx,
        viewer,
        view: () => viewRef.current,
        apply,
        // Your own moves waiting behind this one: the show hurries to catch up with them.
        speedFor: (mine) => (fastRef.current ? 0.55 : 1) * (mine ? (queue.current.length ? 0.6 : 1) : 1.4),
        setStage: (card) => flushSync(() => setStageState(card)),
        banner: (text, kind) => setBanner({ key: ++keyRef.current, text, kind }),
        colorOf: (seat) => {
          const v = viewRef.current;
          const side = seat === v.me.seat ? v.me : seat === v.opponent.seat ? v.opponent : null;
          return (side && heroesRef.current[side.hero.card_class]?.color) || '#f4b545';
        },
        sound: sfx,
      });
    },
    [apply, viewer],
  );

  /**
   * Send an action. Actions queue: each goes out once the one before it has been answered, built
   * against the newest state then. Resolves false (and sets `error`) if it was refused, or dropped
   * because one made before it was refused.
   */
  const act = useCallback(
    (send: Send, opts: { endsTurn?: boolean } = {}): Promise<boolean> => {
      const made = plan.current;
      setPending((n) => n + 1);
      if (opts.endsTurn) setPassing((n) => n + 1);
      setError('');
      const run = async (): Promise<boolean> => {
        try {
          if (made !== plan.current || !alive.current) return false;
          ingest(await send(queuedSeq.current, latest.current));
          return true;
        } catch (e: any) {
          plan.current++;
          setError(e?.message || 'That did not work.');
          sfx.error();
          return false;
        } finally {
          setPending((n) => n - 1);
          if (opts.endsTurn) setPassing((n) => n - 1);
        }
      };
      const done = sending.current.then(run, run);
      sending.current = done;
      return done;
    },
    [ingest],
  );

  const setFast = useCallback((v: boolean) => {
    localStorage.setItem(SPEED_KEY, v ? 'fast' : 'normal');
    setFastState(v);
  }, []);

  const shown = useMemo(() => withLiveRules(view, ahead), [view, ahead]);
  const ready = movable(ahead) && passing === 0;

  return useMemo(
    () => ({
      /** The board as shown, with what may be done read from the newest state. */
      view: shown,
      viewer,
      /** The newest state lets this player move now (moves can be made while animations play). */
      ready,
      playing,
      /** True while input should wait: something is animating or in flight. */
      busy: playing || pending > 0,
      stage,
      banner,
      history,
      error,
      online,
      agent,
      fast,
      setFast,
      setError,
      clearBanner: () => setBanner(null),
      act,
      bind,
      fx: fxRef,
    }),
    [shown, ready, viewer, playing, pending, stage, banner, history, error, online, agent, fast, setFast, act, bind],
  );
}

export type Session = ReturnType<typeof useSession>;
