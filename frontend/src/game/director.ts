// The director turns a beat (one action's events) into motion on the board.
// Each handler decides when its events are folded into the displayed state
// (`apply`), so numbers change at the moment of impact, not before or after.
import { creatureKind, creatureSize } from '../audio/creatures';
import type { CueName, CueOpts } from '../audio/cues';
import type { Beat, BoardMinion, CardDef, GameEvent, GameStateView, Seat } from '../types';
import { ease, settle, type Box, type Fx } from './fx';

export interface StageCard {
  key: number;
  /** null shows a face-down card (an opponent's secret). */
  card: CardDef | null;
  cardClass?: string;
  seat: Seat;
  tone: 'play' | 'secret' | 'burn' | 'discard' | 'counter';
  label?: string;
}

export interface Sounds {
  /** Play one of the game's sound cues (see src/audio/cues.ts). */
  cue(name: CueName, opts?: CueOpts): void;
}

export interface DirectorApi {
  fx: Fx;
  viewer: Seat;
  view(): GameStateView;
  /** Fold events into what is on screen; moved pieces slide into place. */
  apply(events: GameEvent[]): void;
  /** How fast to play: 1 is normal, more is slower. The other side's moves get more time. */
  speedFor(mine: boolean): number;
  setStage(card: StageCard | null): void;
  banner(text: string, kind: 'mine' | 'theirs'): void;
  colorOf(seat: Seat | undefined | null): string;
  sound: Sounds;
}

const IMPACT = new Set(['damage', 'shield_break', 'immune', 'freeze']);
/** Events that are somebody doing something; what follows them is its consequence. */
const ACTIONS = new Set(['play', 'attack', 'hero_power', 'turn_start', 'turn_end', 'mulligan', 'concede']);
const PARALLEL = new Set([
  'damage',
  'heal',
  'death',
  'remove',
  'summon',
  'buff',
  'freeze',
  'destroy',
  'shield_break',
  'immune',
  'secret_destroy',
]);

function subject(ev: GameEvent): string {
  return String(ev.target ?? ev.minion?.uid ?? ev.uid ?? ev.seq);
}

/** Split a beat into steps: an attack with its impact, area effects together. */
export function groupEvents(events: GameEvent[]): GameEvent[][] {
  const groups: GameEvent[][] = [];
  let i = 0;
  while (i < events.length) {
    const ev = events[i];
    const g = [ev];
    let j = i + 1;
    if (ev.t === 'attack') {
      const ids = new Set([ev.attacker, ev.target]);
      while (j < events.length && IMPACT.has(events[j].t) && ids.has(events[j].target)) g.push(events[j++]);
    } else if (PARALLEL.has(ev.t)) {
      const seen = new Set([subject(ev)]);
      while (j < events.length && events[j].t === ev.t && !seen.has(subject(events[j]))) {
        seen.add(subject(events[j]));
        g.push(events[j++]);
      }
    }
    groups.push(g);
    i = j;
  }
  return groups;
}

const RED = '#ff5d6c';
const GREEN = '#58e0a0';
const GOLD = '#ffd97a';
const ICE = '#9fe3ff';
const VIOLET = '#b79bff';

export class Director {
  /** Where the current card's effects come from (the shown card, a power...). */
  private origin: Box | null = null;
  /** Where a played minion card was last seen, so the minion can land from it. */
  private playBox: Box | null = null;
  private stageKey = 0;
  private stageOpen = false;
  private held: Animation[] = [];
  /** Whose action is being shown right now. */
  private actorMine = true;

  /** True while the other side's move is on screen (it is given more time). */
  get showingTheirs(): boolean {
    return !this.actorMine;
  }

  constructor(private api: DirectorApi) {}

  private get fx(): Fx {
    return this.api.fx;
  }

  private q(sel: string): HTMLElement | null {
    return this.fx.root.querySelector<HTMLElement>(sel);
  }

  private el(id: string | null | undefined): HTMLElement | null {
    return id ? this.q(`[data-uid="${id}"]`) : null;
  }

  /** A piece on the table as it is shown right now. */
  private piece(uid: string | null | undefined): BoardMinion | undefined {
    if (!uid) return undefined;
    const v = this.api.view();
    return v.me.board.find((m) => m.uid === uid) ?? v.opponent.board.find((m) => m.uid === uid);
  }

  /** Where on the table something is, from left (-1) to right (1): its sound comes from there. */
  private pan(box: Box | null | undefined): number {
    if (!box) return 0;
    const w = this.fx.root.offsetWidth || 1600;
    return Math.max(-0.8, Math.min(0.8, ((box.cx / w) * 2 - 1) * 0.85));
  }

  /** Animate and keep the end state until the beat is over. */
  private hold(el: Element | null, keyframes: Keyframe[], duration: number, easing = ease.out): Promise<void> {
    if (!el) return Promise.resolve();
    try {
      const a = (el as HTMLElement).animate(keyframes, { duration: this.fx.ms(duration), easing, fill: 'forwards' });
      this.held.push(a);
      return settle(a, this.fx.ms(duration));
    } catch {
      return Promise.resolve();
    }
  }

  private release(): void {
    this.held.forEach((a) => {
      try {
        a.cancel();
      } catch {
        /* already gone */
      }
    });
    this.held = [];
    // Belt-and-suspenders: ensure no board piece is ever left displaced or elevated after a beat or reset.
    this.fx.root.querySelectorAll<HTMLElement>('[data-uid]').forEach((el) => {
      el.getAnimations?.().forEach((an) => {
        if (an.id === 'lunge' || an.id === 'flip') an.cancel();
      });
      if (el.style.zIndex) el.style.zIndex = '';
      if (el.dataset.lunging) delete el.dataset.lunging;
    });
  }

  async playBeat(beat: Beat): Promise<void> {
    this.origin = null;
    this.playBox = null;
    for (const group of groupEvents(beat.events)) {
      const lead = group[0];
      if (ACTIONS.has(lead.t) && lead.seat) this.actorMine = lead.seat === this.api.viewer;
      // You chose your own moves; the other side's need time to be read.
      this.fx.speed = this.api.speedFor(this.actorMine);
      let applied = false;
      const apply = () => {
        if (applied) return;
        applied = true;
        this.api.apply(group);
      };
      try {
        await this.run(group, apply);
      } catch (err) {
        console.warn('animation step failed', group[0]?.t, err);
      }
      apply();
    }
    await this.closeStage();
    this.release();
  }

  /** Skip the show: used when the tab is hidden or the queue is far behind. */
  reset(): void {
    this.release();
    this.fx.clear();
    if (this.stageOpen) {
      this.api.setStage(null);
      this.stageOpen = false;
    }
    this.origin = null;
    this.playBox = null;
  }

  // --- the card shown beside the board while it resolves ---------------------

  private async openStage(card: Omit<StageCard, 'key'>, from: Box | null, duration = 340): Promise<Box | null> {
    this.api.setStage({ ...card, key: ++this.stageKey });
    this.stageOpen = true;
    const el = this.q('[data-stage]');
    const to = this.fx.box(el);
    if (el && to && from) {
      await this.fx.anim(
        el,
        [
          {
            translate: `${from.cx - to.cx}px ${from.cy - to.cy}px`,
            scale: Math.max(0.2, Math.min(1.2, from.w / to.w)),
            opacity: 0.5,
          },
          { translate: '0 0', scale: 1, opacity: 1 },
        ],
        { duration },
      );
    } else if (el) {
      await this.fx.anim(el, [{ scale: 0.6, opacity: 0 }, { scale: 1, opacity: 1 }], { duration: 220 });
    }
    return this.fx.box(el);
  }

  private async closeStage(into?: Box | null): Promise<void> {
    if (!this.stageOpen) return;
    const el = this.q('[data-stage]');
    const b = this.fx.box(el);
    if (el && b) {
      const frames: Keyframe[] = into
        ? [
            { translate: '0 0', scale: 1, opacity: 1 },
            { translate: `${into.cx - b.cx}px ${into.cy - b.cy}px`, scale: 0.16, opacity: 0.2 },
          ]
        : [
            { translate: '0 0', scale: 1, opacity: 1 },
            { translate: '0 -16px', scale: 0.94, opacity: 0 },
          ];
      await this.fx.anim(el, frames, { duration: into ? 300 : 170, fill: 'forwards', easing: into ? ease.in : ease.out });
    }
    this.api.setStage(null);
    this.stageOpen = false;
  }

  // --- shared reactions -------------------------------------------------------

  /** `nth` > 0: another hit on the same target at the same moment; its number is set beside the first. */
  private showHit(ev: GameEvent, skipShakeFor?: string | null, nth = 0): void {
    const e = this.el(ev.target);
    const b = this.fx.box(e);
    if (!e || !b) return;
    if (ev.t === 'damage') {
      const at = nth ? { ...b, cx: b.cx + (nth % 2 ? 34 : -34) * Math.ceil(nth / 2), cy: b.cy - 18 * nth } : b;
      this.fx.floater(at, `−${ev.amount}`, 'dmg');
      this.fx.flash(e, RED, 280);
      if (ev.target !== skipShakeFor) void this.fx.shake(e, Math.min(14, 5 + ev.amount));
      this.fx.sparks(b, '#ffc2a8', 6, 54);
      if (String(ev.target).startsWith('hero_') && ev.amount >= 5) this.fx.screenShake(Math.min(12, 3 + ev.amount * 0.6));
    } else if (ev.t === 'shield_break') {
      this.fx.ring(b, GOLD, 200, 520);
      this.fx.shards(b, '#ffe9a8', 8);
      this.fx.floater(b, 'Blocked', 'note');
      this.api.sound.cue('shield', { pan: this.pan(b) });
    } else if (ev.t === 'immune') {
      this.fx.floater(b, 'Immune', 'note');
      this.fx.ring(b, GOLD, 170, 420);
      this.api.sound.cue('immune', { pan: this.pan(b) });
    } else if (ev.t === 'freeze') {
      this.fx.flash(e, ICE, 520);
      this.fx.ring(b, ICE, 170, 520);
      this.api.sound.cue('freeze', { pan: this.pan(b) });
    }
  }

  private pop(el: Element | null, duration = 320): Promise<void> {
    return this.fx.anim(
      el,
      [
        { scale: 0.3, opacity: 0 },
        { scale: 1.1, opacity: 1, offset: 0.7 },
        { scale: 1, opacity: 1 },
      ],
      { duration },
    );
  }

  // --- one step ---------------------------------------------------------------

  private async run(group: GameEvent[], apply: () => void): Promise<void> {
    const { fx, viewer, sound } = this.api;
    const ev = group[0];
    const mine = ev.seat === viewer;

    switch (ev.t) {
      case 'turn_start': {
        await this.closeStage();
        apply();
        this.api.banner(mine ? 'Your turn' : 'Opponent’s turn', mine ? 'mine' : 'theirs');
        sound.cue('turnStart', { mine });
        await fx.sleep(mine ? 980 : 560);
        return;
      }

      case 'turn_end': {
        await this.closeStage();
        apply();
        await fx.sleep(140);
        return;
      }

      case 'mulligan': {
        apply();
        if (mine) {
          sound.cue('shuffle');
          await fx.sleep(260);
        }
        return;
      }

      case 'draw':
      case 'card_added': {
        const deck = fx.box(this.q(`[data-deck="${ev.seat}"]`));
        apply();
        sound.cue(ev.t === 'draw' ? 'draw' : 'cardAdded', { pan: this.pan(deck) });
        let el: HTMLElement | null;
        if (mine) {
          el = this.q(`[data-card="${ev.uid}"]`);
        } else {
          const backs = fx.root.querySelectorAll<HTMLElement>('[data-oppcard]');
          el = backs.length ? backs[backs.length - 1] : null;
        }
        const b = fx.box(el);
        if (el && b) {
          el.dataset.entering = '1';
          const done = () => delete el!.dataset.entering;
          if (ev.t === 'draw' && deck) {
            void fx
              .anim(
                el,
                [
                  { translate: `${deck.cx - b.cx}px ${deck.cy - b.cy}px`, scale: 0.55, opacity: 0.3 },
                  { opacity: 1, offset: 0.3 },
                  { translate: '0 0', scale: 1, opacity: 1 },
                ],
                { duration: mine ? 440 : 340 },
              )
              .then(done);
          } else {
            void this.pop(el, 340).then(done);
          }
        }
        await fx.sleep(mine ? 300 : 200);
        return;
      }

      case 'burn': {
        const deck = fx.box(this.q(`[data-deck="${ev.seat}"]`));
        await this.closeStage();
        apply();
        sound.cue('burn', { pan: this.pan(deck) });
        await this.openStage({ card: ev.card, seat: ev.seat!, tone: 'burn', label: 'Hand full' }, deck, 360);
        await fx.sleep(720);
        await this.closeStage();
        return;
      }

      case 'fatigue': {
        const deckEl = this.q(`[data-deck="${ev.seat}"]`);
        const deck = fx.box(deckEl);
        apply();
        if (deck) {
          fx.flash(deckEl, RED, 420);
          fx.floater(deck, 'Fatigue', 'note');
          sound.cue('fatigue', { pan: this.pan(deck) });
          void fx.shake(deckEl, 6);
          this.origin = deck;
        }
        await fx.sleep(280);
        return;
      }

      case 'play': {
        await this.closeStage();
        const type: string = ev.card_type;
        let from: Box | null;
        if (mine) {
          // The card face itself: it may be lifted or held away from its slot.
          from = fx.box(this.q(`[data-card="${ev.uid}"] .card`));
        } else {
          const backs = fx.root.querySelectorAll<HTMLElement>('[data-oppcard]');
          const idx = Math.max(0, Math.min(Number(ev.hand_index) || 0, backs.length - 1));
          from = fx.box(backs[idx]) || fx.box(this.q('[data-zone="opphand"]'));
        }

        if (ev.secret) {
          apply();
          sound.cue('secret', { pan: this.pan(from) });
          await this.openStage(
            { card: mine ? ev.card : null, cardClass: ev.card_class, seat: ev.seat!, tone: 'secret' },
            from,
            320,
          );
          await fx.sleep(mine ? 380 : 420);
          await this.closeStage(fx.box(this.el(`hero_${ev.seat}`)));
          return;
        }

        if (type === 'MINION' && mine) {
          // Your own minion goes straight from where you dropped it to the board.
          this.playBox = from;
          apply();
          sound.cue('cardPlay', { pan: this.pan(from) });
          return;
        }

        apply();
        if (type === 'SPELL') sound.cue('spellCast', { pan: this.pan(from), amount: ev.cost });
        else sound.cue('cardPlay', { pan: this.pan(from) });
        const shown = await this.openStage({ card: ev.card, seat: ev.seat!, tone: 'play' }, from, 340);
        await fx.sleep(mine ? (type === 'SPELL' ? 380 : 260) : type === 'MINION' ? 1000 : 1200);
        this.origin = shown;
        if (type === 'MINION') this.playBox = shown;
        const target = fx.box(this.el(ev.target));
        if (target && type !== 'MINION') fx.ring(target, this.api.colorOf(ev.seat), 180, 520);
        return;
      }

      case 'summon': {
        const landing = group.length === 1 && ev.from_hand && this.playBox ? this.playBox : null;
        if (landing && this.stageOpen) {
          this.api.setStage(null);
          this.stageOpen = false;
        }
        apply();
        const jobs = group.map(async (s) => {
          const el = this.el(s.minion.uid);
          const b = fx.box(el);
          if (!el || !b) return;
          el.dataset.entering = '1';
          if (landing) {
            await fx.anim(
              el,
              [
                {
                  translate: `${landing.cx - b.cx}px ${landing.cy - b.cy}px`,
                  scale: Math.max(0.8, Math.min(1.7, landing.w / b.w)),
                  opacity: 0.85,
                },
                { translate: '0 -6px', scale: 1.12, opacity: 1, offset: 0.72 },
                { translate: '0 0', scale: 1, opacity: 1 },
              ],
              { duration: 330, easing: 'cubic-bezier(.3,.7,.3,1)' },
            );
            fx.ring(b, this.api.colorOf(s.seat), 210, 480);
            fx.sparks({ cx: b.cx, cy: b.y + b.h }, '#e9dcc0', 7, 60);
            sound.cue('land', {
              pan: this.pan(b),
              amount: Number(s.minion.attack) + Number(s.minion.health),
              rare: s.minion.rarity === 'LEGENDARY',
            });
            sound.cue('creatureEnter', { pan: this.pan(b), amount: creatureSize(s.minion), kind: creatureKind(s.minion) });
          } else {
            // tokens appearing together land as one soft sound, not a pile of them
            if (s === group[0]) {
              sound.cue('land', { pan: this.pan(b), amount: (Number(s.minion.attack) + Number(s.minion.health)) * 0.5 });
              sound.cue('creatureEnter', { pan: this.pan(b), amount: creatureSize(s.minion), kind: creatureKind(s.minion) });
            }
            await this.pop(el, 330);
          }
          delete el.dataset.entering;
        });
        await Promise.all(jobs);
        this.playBox = null;
        await fx.sleep(70);
        return;
      }

      case 'attack': {
        const a = this.el(ev.attacker);
        const t = this.el(ev.target);
        const ab = fx.box(a);
        const tb = fx.box(t);
        if (!a || !ab || !tb) {
          apply();
          group.slice(1).forEach((h) => this.showHit(h));
          await fx.sleep(260);
          return;
        }
        await this.closeStage();
        const dx = tb.cx - ab.cx;
        const dy = tb.cy - ab.cy;
        const len = Math.hypot(dx, dy) || 1;
        // Stop short of the centre so the pieces meet edge to edge.
        const reach = Math.max(0.35, 1 - (tb.h * 0.42) / len);
        if (!mine) {
          // Show who is about to hit whom before it happens.
          fx.ring(ab, this.api.colorOf(ev.seat), 200, 520);
          fx.ring(tb, RED, 190, 520);
          await fx.sleep(300);
        }
        a.style.zIndex = '60';
        a.dataset.lunging = '1';
        const cancelLunge = () => {
          a.getAnimations?.().forEach((an) => {
            if (an.id === 'lunge') an.cancel();
          });
        };
        try {
          // a creature gives voice as it winds up; a hero's blow is only heard landing
          const attacker = this.piece(ev.attacker);
          if (attacker) sound.cue('creatureAttack', { pan: this.pan(ab), to: this.pan(tb), amount: creatureSize(attacker), kind: creatureKind(attacker) });
          await this.hold(
            a,
            [
              { translate: '0 0', scale: 1 },
              { translate: `${-dx * 0.07}px ${-dy * 0.07}px`, scale: 1.1 },
            ],
            150,
            ease.out,
          );
          await this.hold(
            a,
            [
              { translate: `${-dx * 0.07}px ${-dy * 0.07}px`, scale: 1.1 },
              { translate: `${dx * reach}px ${dy * reach}px`, scale: 1.12 },
            ],
            150,
            ease.in,
          );
          const hits = group.slice(1);
          const worst = Math.max(0, ...hits.filter((h) => h.t === 'damage').map((h) => Number(h.amount) || 0));
          sound.cue('attack', { pan: this.pan(tb), amount: worst });
          const contact = { cx: ab.cx + dx * (reach + 0.12), cy: ab.cy + dy * (reach + 0.12) };
          fx.burst(contact, '#fff6e0', 130);
          fx.sparks(contact, '#ffcf8a', 10, 80);
          apply();
          hits.forEach((h) => this.showHit(h, ev.attacker));
          if (worst >= 6) fx.screenShake(Math.min(11, 2 + worst * 0.7));
          // Start recoil back to resting place and release the held lunge frames on the same tick.
          const recoil = fx.anim(
            a,
            [
              { translate: `${dx * reach}px ${dy * reach}px`, scale: 1.12 },
              { translate: `${dx * (reach - 0.06)}px ${dy * (reach - 0.06)}px`, scale: 1.08, offset: 0.25 },
              { translate: '0 0', scale: 1 },
            ],
            { duration: 300, id: 'lunge' },
          );
          this.held.forEach((an) => {
            try {
              an.cancel();
            } catch {
              /* already gone */
            }
          });
          this.held = [];
          await recoil;
        } finally {
          cancelLunge();
          a.style.zIndex = '';
          delete a.dataset.lunging;
        }
        await fx.sleep(mine ? 90 : 320);
        return;
      }

      case 'damage': {
        const color = this.api.colorOf(ev.source_seat);
        let flown = false;
        const shots = group.map((d, i) => {
          const tb = fx.box(this.el(d.target));
          const src = (d.source && fx.box(this.el(d.source))) || this.origin || fx.box(this.el(`hero_${d.source_seat}`));
          if (!tb || !src || d.source === d.target) return Promise.resolve();
          if (!flown) sound.cue('projectile', { pan: this.pan(src), to: this.pan(tb) });
          flown = true;
          return fx.projectile(src, tb, color, i * 45).then(() => fx.burst(tb, color, 110));
        });
        await Promise.all(shots);
        apply();
        const hits = new Map<string, number>();
        group.forEach((d) => {
          const nth = hits.get(String(d.target)) ?? 0;
          hits.set(String(d.target), nth + 1);
          this.showHit(d, undefined, nth);
        });
        sound.cue('hit', {
          amount: Math.max(...group.map((d) => Number(d.amount) || 0)),
          pan: group.length === 1 ? this.pan(fx.box(this.el(ev.target))) : 0,
        });
        await fx.sleep(group.length > 1 ? 340 : 270);
        return;
      }

      case 'shield_break':
      case 'immune':
      case 'freeze': {
        apply();
        group.forEach((d) => this.showHit(d));
        await fx.sleep(240);
        return;
      }

      case 'heal': {
        apply();
        group.forEach((h) => {
          const e = this.el(h.target);
          const b = fx.box(e);
          if (!e || !b) return;
          fx.floater(b, `+${h.amount}`, 'heal');
          fx.flash(e, GREEN, 420);
          fx.ring(b, GREEN, 170, 520);
        });
        sound.cue('heal', { pan: this.pan(fx.box(this.el(ev.target))) });
        await fx.sleep(280);
        return;
      }

      case 'destroy': {
        group.forEach((d) => {
          const e = this.el(d.target);
          const b = fx.box(e);
          if (!e || !b) return;
          fx.flash(e, '#1b1030', 320);
          fx.ring(b, VIOLET, 180, 420);
        });
        sound.cue('destroy', { pan: this.pan(fx.box(this.el(ev.target))) });
        apply();
        await fx.sleep(200);
        return;
      }

      case 'death':
      case 'remove': {
        const jobs = group.map((d, i) => {
          const e = this.el(d.target);
          const b = fx.box(e);
          if (!e || !b) return Promise.resolve();
          if (ev.t === 'death') fx.shards(b, '#8b90a0', 7);
          return this.hold(
            e,
            [
              { scale: 1, opacity: 1, filter: 'grayscale(0) brightness(1)' },
              { scale: 1.05, opacity: 1, filter: 'grayscale(1) brightness(1.6)', offset: 0.22 },
              { scale: 0.72, opacity: 0, translate: '0 26px', rotate: `${i % 2 ? -7 : 7}deg`, filter: 'grayscale(1) brightness(.4)' },
            ],
            430,
          );
        });
        if (ev.t === 'death') {
          sound.cue('death', { pan: group.length === 1 ? this.pan(fx.box(this.el(ev.target))) : 0 });
          // when several fall together, two different voices are enough
          const voiced = new Set<string>();
          for (const d of group) {
            const fallen = this.piece(d.target);
            const kind = creatureKind(fallen);
            if (!kind || voiced.has(kind) || voiced.size >= 2) continue;
            sound.cue('creatureDeath', { pan: this.pan(fx.box(this.el(d.target))), amount: creatureSize(fallen), kind, at: voiced.size * 0.12 });
            voiced.add(kind);
          }
        }
        await Promise.all(jobs);
        apply();
        await fx.sleep(90);
        return;
      }

      case 'buff': {
        apply();
        const isHarmful = (b: GameEvent) => Number(b.atk) < 0 || Number(b.hp) < 0 || b.set_atk !== null || b.set_hp !== null;
        group.forEach((b) => {
          const e = this.el(b.target);
          const box = fx.box(e);
          if (!e || !box) return;
          const harmful = isHarmful(b);
          fx.flash(e, harmful ? VIOLET : GOLD, 380);
          fx.ring(box, harmful ? VIOLET : GOLD, 150, 420);
        });
        sound.cue(isHarmful(ev) ? 'debuff' : 'buff', { pan: group.length === 1 ? this.pan(fx.box(this.el(ev.target))) : 0 });
        await fx.sleep(200);
        return;
      }

      case 'silence': {
        const e = this.el(ev.target);
        const b = fx.box(e);
        if (e && b) {
          fx.flash(e, VIOLET, 480);
          fx.ring(b, VIOLET, 190, 520);
          fx.floater(b, 'Silenced', 'note');
          sound.cue('silence', { pan: this.pan(b) });
        }
        apply();
        await fx.sleep(280);
        return;
      }

      case 'transform':
      case 'morph': {
        const old = this.el(ev.target);
        if (old) {
          sound.cue('transform', { pan: this.pan(fx.box(old)) });
          fx.flash(old, '#ffffff', 360);
          await this.hold(old, [{ scale: 1, opacity: 1 }, { scale: 0.6, opacity: 0.4 }], 160, ease.in);
        }
        this.release();
        apply();
        const fresh = this.el(ev.minion?.uid);
        const fb = fx.box(fresh);
        if (fresh && fb) {
          fx.ring(fb, VIOLET, 190, 480);
          await this.pop(fresh, 300);
        }
        return;
      }

      case 'steal': {
        const e = this.el(ev.target);
        if (e) fx.flash(e, VIOLET, 420);
        sound.cue('steal', { pan: this.pan(fx.box(e)) });
        await fx.sleep(140);
        apply();
        await fx.sleep(340);
        return;
      }

      case 'bounce': {
        const e = this.el(ev.target);
        const b = fx.box(e);
        const hand = fx.box(this.q(mine ? '[data-zone="hand"]' : '[data-zone="opphand"]'));
        if (e && b && hand) {
          sound.cue('bounce', { pan: this.pan(b), to: this.pan(hand) });
          await this.hold(
            e,
            [
              { translate: '0 0', scale: 1, opacity: 1 },
              { translate: `${hand.cx - b.cx}px ${hand.cy - b.cy}px`, scale: 0.5, opacity: 0.2 },
            ],
            320,
            ease.in,
          );
        }
        apply();
        await fx.sleep(90);
        return;
      }

      case 'weapon_equip': {
        apply();
        const w = this.q(`[data-weapon="${ev.seat}"]`);
        const wb = fx.box(w);
        if (this.stageOpen) await this.closeStage(wb);
        if (w && wb) {
          fx.ring(wb, this.api.colorOf(ev.seat), 150, 420);
          await this.pop(w, 280);
        }
        sound.cue('weaponEquip', { pan: this.pan(wb) });
        return;
      }

      case 'weapon_destroy': {
        const w = this.q(`[data-weapon="${ev.seat}"]`);
        const wb = fx.box(w);
        if (w && wb) {
          sound.cue('weaponBreak', { pan: this.pan(wb) });
          fx.shards(wb, '#9aa3b5', 8);
          await this.hold(w, [{ scale: 1, opacity: 1, rotate: '0deg' }, { scale: 0.6, opacity: 0, rotate: '18deg' }], 260, ease.in);
        }
        apply();
        return;
      }

      case 'secret_add': {
        apply();
        await this.pop(this.q(`[data-secret="${ev.uid}"]`), 300);
        return;
      }

      case 'secret_reveal': {
        const from = fx.box(this.q(`[data-secret="${ev.uid}"]`)) || fx.box(this.el(`hero_${ev.seat}`));
        await this.closeStage();
        apply();
        sound.cue('secretReveal', { pan: this.pan(from) });
        const shown = await this.openStage({ card: ev.card, seat: ev.seat!, tone: 'secret', label: 'Secret' }, from, 320);
        if (shown) fx.ring(shown, GOLD, 320, 620);
        await fx.sleep(900);
        this.origin = shown;
        return;
      }

      case 'secret_destroy': {
        group.forEach((s) => {
          const b = fx.box(this.q(`[data-secret="${s.uid}"]`));
          if (b) fx.shards(b, GOLD, 5);
        });
        apply();
        await fx.sleep(160);
        return;
      }

      case 'countered': {
        const stage = this.q('[data-stage]');
        const sb = fx.box(stage);
        if (stage && sb) {
          sound.cue('counter', { pan: this.pan(sb) });
          fx.floater(sb, 'Countered', 'note');
          await fx.shake(stage, 10);
          await fx.sleep(320);
        }
        await this.closeStage();
        apply();
        return;
      }

      case 'discard': {
        sound.cue('discard', { pan: mine ? 0 : -0.5 });
        if (mine) {
          const e = this.q(`[data-card="${ev.uid}"]`);
          await this.hold(
            e,
            [
              { translate: '0 0', opacity: 1, filter: 'saturate(1)' },
              { translate: '0 -130px', opacity: 0, filter: 'saturate(0) brightness(.6)' },
            ],
            340,
          );
          apply();
          return;
        }
        const from = fx.box(this.q('[data-zone="opphand"]'));
        await this.closeStage();
        apply();
        await this.openStage({ card: ev.card, seat: ev.seat!, tone: 'discard', label: 'Discarded' }, from, 300);
        await fx.sleep(620);
        await this.closeStage();
        return;
      }

      case 'hero_power': {
        await this.closeStage();
        const p = this.q(`[data-power="${ev.seat}"]`);
        const pb = fx.box(p);
        apply();
        sound.cue('heroPower', { pan: this.pan(pb) });
        if (p && pb) {
          fx.ring(pb, this.api.colorOf(ev.seat), 170, 480);
          await fx.anim(p, [{ scale: 1 }, { scale: 1.2, offset: 0.4 }, { scale: 1 }], { duration: 300 });
          this.origin = pb;
        }
        const target = fx.box(this.el(ev.target));
        if (target) fx.ring(target, this.api.colorOf(ev.seat), 170, 480);
        return;
      }

      case 'game_over': {
        await this.closeStage();
        const losers: Seat[] = ev.winner === 'draw' ? ['p1', 'p2'] : ev.winner === 'p1' ? ['p2'] : ev.winner === 'p2' ? ['p1'] : [];
        await Promise.all(
          losers.map(async (seat) => {
            const h = this.el(`hero_${seat}`);
            const hb = fx.box(h);
            if (!h || !hb) return;
            await fx.shake(h, 14);
            fx.burst(hb, '#fff', 320);
            fx.shards(hb, RED, 18);
            fx.screenShake(12);
          }),
        );
        sound.cue(ev.winner === viewer ? 'victory' : 'defeat');
        await fx.sleep(520);
        apply();
        await fx.sleep(300);
        return;
      }

      default: {
        apply();
        return;
      }
    }
  }
}
