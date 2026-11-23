// Moves made while animations play: the board on screen runs behind the match, so what may be
// done, and where a card goes, are read from the newest state. Pure, so it can be checked
// without a browser (scripts/check-live.mjs).
import type { GameStateView } from '../types';

/**
 * The board being shown runs behind the match while animations play. What the player may do
 * is read from the newest state instead, laid over what is shown, so a move can be made
 * (and is sent) at once instead of after the show has caught up.
 */
export function withLiveRules(shown: GameStateView, now: GameStateView): GameStateView {
  if (now === shown || now.seq <= shown.seq) return shown;
  const hand = new Map(now.me.hand.map((c) => [c.uid, c]));
  const board = new Map(now.me.board.map((m) => [m.uid, m]));
  const hero = now.me.hero;
  const power = hero.hero_power;
  const samePower = power.id === shown.me.hero.hero_power.id;
  return {
    ...shown,
    me: {
      ...shown.me,
      hand: shown.me.hand.map((c) => {
        const n = hand.get(c.uid);
        if (!n) return { ...c, can_play: false, unplayable_reason: '', combo_glow: false };
        return {
          ...c,
          can_play: n.can_play,
          unplayable_reason: n.unplayable_reason,
          target_rule: n.target_rule,
          target_required: n.target_required,
          valid_targets: n.valid_targets,
          choose_options: n.choose_options,
          combo_glow: n.combo_glow,
        };
      }),
      board: shown.me.board.map((m) => {
        const n = board.get(m.uid);
        return { ...m, can_attack: Boolean(n?.can_attack), legal_attack_targets: n?.legal_attack_targets ?? [] };
      }),
      hero: {
        ...shown.me.hero,
        can_attack: hero.can_attack,
        legal_attack_targets: hero.legal_attack_targets,
        hero_power: samePower
          ? { ...shown.me.hero.hero_power, used: power.used, can_use: power.can_use, target_rule: power.target_rule, valid_targets: power.valid_targets }
          : { ...shown.me.hero.hero_power, can_use: false },
      },
    },
  };
}

/** True while the newest state lets this player make a move (whatever is still being shown). */
export function movable(now: GameStateView): boolean {
  return now.phase === 'PLAY' && now.your_turn && !now.pending_choice;
}

/**
 * A place in the row as it was shown, as a place in the row as it is now (which may already hold
 * more or fewer minions): beside the same neighbour; a card put at the end goes to the end.
 */
export function placeIn(pos: number | undefined, shown: string[], now: { uid: string }[]): number {
  if (pos === undefined) return 0;
  const uids = now.map((m) => m.uid);
  if (pos >= shown.length) return uids.length;
  for (let i = pos - 1; i >= 0; i--) {
    const at = uids.indexOf(shown[i]);
    if (at >= 0) return at + 1;
  }
  for (let i = pos; i < shown.length; i++) {
    const at = uids.indexOf(shown[i]);
    if (at >= 0) return at;
  }
  return 0;
}
