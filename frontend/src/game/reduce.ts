// Display-state reducer: folds one engine event into the view the player is
// looking at, so the board can change step by step while a beat plays back.
// It only has to be right enough to animate against; the beat's own snapshot
// replaces the result when the beat ends.
import type { BoardMinion, GameEvent, GameStateView, HandCard, Seat } from '../types';

type Side = GameStateView['me'] | GameStateView['opponent'];

function sideOf(v: GameStateView, seat: Seat | undefined): Side | null {
  if (!seat) return null;
  return v.me.seat === seat ? v.me : v.opponent.seat === seat ? v.opponent : null;
}

function findMinion(v: GameStateView, uid: string | null | undefined): BoardMinion | null {
  if (!uid) return null;
  return v.me.board.find((m) => m.uid === uid) || v.opponent.board.find((m) => m.uid === uid) || null;
}

function dropMinion(v: GameStateView, uid: string | null | undefined): void {
  if (!uid) return;
  v.me.board = v.me.board.filter((m) => m.uid !== uid);
  v.opponent.board = v.opponent.board.filter((m) => m.uid !== uid);
}

function heroSeat(id: string | null | undefined): Seat | null {
  return id === 'hero_p1' ? 'p1' : id === 'hero_p2' ? 'p2' : null;
}

function provisionalHandCard(ev: GameEvent, index: number): HandCard {
  const c = ev.card;
  return {
    index,
    uid: ev.uid,
    card_id: c.id,
    name: c.name,
    card_class: c.card_class,
    type: c.type,
    rarity: c.rarity,
    race: c.race,
    base_cost: c.cost,
    cost: c.cost,
    attack: c.attack,
    health: c.health,
    durability: c.durability,
    text: c.text,
    mechanics: c.mechanics || [],
    overload: c.overload || 0,
    can_play: false,
    unplayable_reason: '',
    target_rule: 'NONE',
    target_required: false,
    valid_targets: [],
    choose_options: [],
    combo_glow: false,
  };
}

function addToMyHand(v: GameStateView, ev: GameEvent, final: GameStateView | null): void {
  if (!ev.uid || !ev.card || v.me.hand.some((c) => c.uid === ev.uid)) return;
  const known = final?.me.hand.find((c) => c.uid === ev.uid);
  const card = known ? { ...known } : provisionalHandCard(ev, v.me.hand.length);
  // Nothing is playable until the beat has resolved.
  card.can_play = false;
  v.me.hand.push(card);
  v.me.hand.forEach((c, i) => (c.index = i));
}

function removeFromMyHand(v: GameStateView, uid: string | undefined): void {
  if (!uid) return;
  v.me.hand = v.me.hand.filter((c) => c.uid !== uid);
  v.me.hand.forEach((c, i) => (c.index = i));
}

/** Mutates `v` (callers pass a copy). `final` is the beat's closing snapshot. */
export function applyEvent(v: GameStateView, ev: GameEvent, final: GameStateView | null = null): void {
  const mine = ev.seat === v.me.seat;
  const side = sideOf(v, ev.seat);

  switch (ev.t) {
    case 'mulligan': {
      if (!side) break;
      side.mulligan_done = true;
      if (mine && final) {
        // The swapped cards are only known from the snapshot. A swap keeps the hand
        // the same size; anything after that arrives through its own draw event.
        const size = v.me.hand.length;
        v.me.hand = final.me.hand.slice(0, size).map((c, i) => ({ ...c, index: i, can_play: false }));
      }
      break;
    }
    case 'turn_start': {
      v.phase = 'PLAY';
      v.active_seat = ev.seat!;
      v.your_turn = mine;
      v.turn_number = ev.turn;
      if (side) {
        side.mana = ev.mana;
        side.max_mana = ev.max_mana;
        side.overloaded = ev.overloaded;
        side.pending_overload = 0;
        side.hero.hero_power.used = false;
        side.board.forEach((m) => {
          m.summoned_this_turn = false;
          m.attacks_this_turn = 0;
        });
      }
      break;
    }
    case 'turn_end': {
      v.your_turn = false;
      v.me.board.forEach((m) => (m.can_attack = false));
      v.me.hero.can_attack = false;
      v.me.hero.hero_power.can_use = false;
      v.me.hand.forEach((c) => (c.can_play = false));
      break;
    }
    case 'draw':
    case 'card_added': {
      if (!side) break;
      side.hand_count += 1;
      if (ev.t === 'draw') side.deck_count = Math.max(0, side.deck_count - 1);
      if (mine) addToMyHand(v, ev, final);
      break;
    }
    case 'burn': {
      if (side && ev.origin === 'deck') side.deck_count = Math.max(0, side.deck_count - 1);
      break;
    }
    case 'fatigue': {
      if (side) side.fatigue = ev.amount;
      break;
    }
    case 'play': {
      if (!side) break;
      side.hand_count = Math.max(0, side.hand_count - 1);
      side.mana = ev.mana;
      if (mine) {
        removeFromMyHand(v, ev.uid);
        v.me.hand.forEach((c) => (c.can_play = false));
      }
      break;
    }
    case 'discard': {
      if (!side) break;
      side.hand_count = Math.max(0, side.hand_count - 1);
      if (mine) removeFromMyHand(v, ev.uid);
      break;
    }
    case 'summon': {
      if (!side || findMinion(v, ev.minion.uid)) break;
      const pos = Math.max(0, Math.min(ev.pos ?? side.board.length, side.board.length));
      side.board.splice(pos, 0, { ...ev.minion });
      break;
    }
    case 'transform': {
      dropMinion(v, ev.target);
      if (!side) break;
      const pos = Math.max(0, Math.min(ev.pos ?? side.board.length, side.board.length));
      side.board.splice(pos, 0, { ...ev.minion });
      break;
    }
    case 'morph':
    case 'buff':
    case 'silence': {
      const m = findMinion(v, ev.target);
      if (m && ev.minion) Object.assign(m, ev.minion, { can_attack: m.can_attack, legal_attack_targets: m.legal_attack_targets });
      break;
    }
    case 'death':
    case 'remove': {
      dropMinion(v, ev.target);
      break;
    }
    case 'steal': {
      dropMinion(v, ev.target);
      if (side) side.board.push({ ...ev.minion });
      break;
    }
    case 'bounce': {
      dropMinion(v, ev.target);
      if (!side) break;
      side.hand_count += 1;
      if (mine) addToMyHand(v, ev, final);
      break;
    }
    case 'attack': {
      const m = findMinion(v, ev.attacker);
      if (m) {
        m.attacks_this_turn += 1;
        m.can_attack = false;
      } else if (ev.attacker === v.me.hero.id) {
        v.me.hero.can_attack = false;
      }
      break;
    }
    case 'damage': {
      const hs = heroSeat(ev.target);
      if (hs) {
        const h = sideOf(v, hs)!.hero;
        h.hp = ev.hp;
        h.armor = ev.armor;
      } else {
        const m = findMinion(v, ev.target);
        if (m) {
          m.health = ev.health;
          m.damaged = true;
        }
      }
      break;
    }
    case 'heal': {
      const hs = heroSeat(ev.target);
      if (hs) {
        sideOf(v, hs)!.hero.hp = ev.hp;
      } else {
        const m = findMinion(v, ev.target);
        if (m) {
          m.health = ev.health;
          m.damaged = m.health < m.max_health;
        }
      }
      break;
    }
    case 'shield_break': {
      const m = findMinion(v, ev.target);
      if (m) m.keywords = m.keywords.filter((k) => k !== 'DIVINE_SHIELD');
      break;
    }
    case 'freeze': {
      const hs = heroSeat(ev.target);
      if (hs) sideOf(v, hs)!.hero.frozen = true;
      else {
        const m = findMinion(v, ev.target);
        if (m) m.frozen = true;
      }
      break;
    }
    case 'weapon_equip': {
      if (side) side.weapon = ev.weapon;
      break;
    }
    case 'weapon_destroy': {
      if (side) side.weapon = null;
      break;
    }
    case 'secret_add': {
      if (!side) break;
      if (!side.secrets.some((s) => s.uid === ev.uid)) {
        (side.secrets as { uid: string; card_class: string }[]).push({ uid: ev.uid, card_class: ev.card_class });
      }
      break;
    }
    case 'secret_reveal':
    case 'secret_destroy': {
      if (side) side.secrets = (side.secrets as any[]).filter((s) => s.uid !== ev.uid);
      break;
    }
    case 'hero_power': {
      if (!side) break;
      side.mana = ev.mana;
      side.hero.hero_power.used = true;
      if (mine) v.me.hero.hero_power.can_use = false;
      break;
    }
    case 'game_over': {
      v.phase = 'GAME_OVER';
      v.winner = ev.winner;
      v.your_turn = false;
      break;
    }
    default:
      break;
  }
}

export function applyEvents(
  view: GameStateView,
  events: GameEvent[],
  final: GameStateView | null = null,
): GameStateView {
  const next: GameStateView = structuredClone(view);
  for (const ev of events) applyEvent(next, ev, final);
  return next;
}

/** The structural part of a view that events alone must be able to explain. */
export function shapeOf(v: GameStateView) {
  return {
    board: {
      [v.me.seat]: v.me.board.map((m) => m.uid),
      [v.opponent.seat]: v.opponent.board.map((m) => m.uid),
    },
    hand: { [v.me.seat]: v.me.hand_count, [v.opponent.seat]: v.opponent.hand_count },
    myHand: v.me.hand.map((c) => c.uid),
    weapon: { [v.me.seat]: Boolean(v.me.weapon), [v.opponent.seat]: Boolean(v.opponent.weapon) },
    secrets: { [v.me.seat]: v.me.secrets.length, [v.opponent.seat]: v.opponent.secrets.length },
    hp: { [v.me.seat]: v.me.hero.hp, [v.opponent.seat]: v.opponent.hero.hp },
  };
}
