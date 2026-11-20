export interface HeroMeta {
  card_class: string;
  name: string;
  hero_power_id: string;
  title: string;
  color: string;
}

export interface CardDef {
  id: string;
  name: string;
  card_class: string;
  type: 'MINION' | 'SPELL' | 'WEAPON' | 'HERO_POWER';
  cost: number;
  attack: number | null;
  health: number | null;
  durability: number | null;
  rarity: 'FREE' | 'COMMON' | 'RARE' | 'EPIC' | 'LEGENDARY';
  race: string | null;
  collectible: boolean;
  text: string;
  mechanics: string[];
  spell_damage: number;
  overload: number;
}

export interface DeckInfo {
  id: string;
  name: string;
  hero_class: string;
  description?: string;
  cards: string[];
  builtin: boolean;
  era?: 'classic' | 'golden' | string;
  /** Kept on this device rather than on the server. */
  device?: boolean;
}

export interface ChooseOption {
  index: number;
  label: string;
  description: string;
  target_rule: string;
  valid_targets: string[];
  playable: boolean;
}

export interface HandCard {
  index: number;
  uid: string;
  card_id: string;
  name: string;
  card_class: string;
  type: 'MINION' | 'SPELL' | 'WEAPON';
  rarity: 'FREE' | 'COMMON' | 'RARE' | 'EPIC' | 'LEGENDARY';
  race: string | null;
  base_cost: number;
  cost: number;
  attack: number | null;
  health: number | null;
  durability: number | null;
  text: string;
  mechanics: string[];
  overload: number;
  can_play: boolean;
  unplayable_reason: string;
  target_rule: string;
  target_required: boolean;
  valid_targets: string[];
  choose_options: ChooseOption[];
  combo_glow: boolean;
}

export interface BoardMinion {
  uid: string;
  card_id: string;
  name: string;
  owner: 'p1' | 'p2';
  card_class: string;
  cost: number;
  attack: number;
  health: number;
  max_health: number;
  base_attack: number;
  base_health: number;
  race: string | null;
  rarity: string;
  text: string;
  keywords: string[];
  silenced: boolean;
  frozen: boolean;
  damaged: boolean;
  immune: boolean;
  spell_damage: number;
  can_attack: boolean;
  summoned_this_turn: boolean;
  attacks_this_turn: number;
  enchantments: string[];
  legal_attack_targets?: string[];
}

export interface WeaponView {
  uid: string;
  card_id: string;
  name: string;
  attack: number;
  durability: number;
  max_durability: number;
  windfury: boolean;
  text: string;
}

export interface HeroPowerView {
  id: string;
  name: string;
  cost: number;
  text: string;
  used: boolean;
  can_use?: boolean;
  target_rule?: string;
  valid_targets?: string[];
}

export interface HeroView {
  id: string;
  card_class: string;
  name: string;
  hp: number;
  max_hp: number;
  armor: number;
  attack: number;
  frozen: boolean;
  immune: boolean;
  is_jaraxxus: boolean;
  can_attack?: boolean;
  legal_attack_targets?: string[];
  hero_power: HeroPowerView;
}

export interface SecretView {
  uid: string;
  card_class: string;
  card_id?: string;
  name?: string;
}

export interface LogEntry {
  id: number;
  turn: number;
  seat: string | null;
  text: string;
}

export interface GameStateView {
  game_id: string;
  /** Sequence number of the last beat folded into this view. */
  seq: number;
  /** `ai_vs_human` is a match on this device against the built-in opponent. */
  mode: 'cli_vs_human' | 'bot_vs_human' | 'agent_vs_human' | 'ai_vs_human' | 'friend_vs_human';
  phase: 'WAITING_FOR_P2_DECK' | 'MULLIGAN' | 'PLAY' | 'GAME_OVER';
  viewer_seat: 'p1' | 'p2';
  active_seat: 'p1' | 'p2';
  your_turn: boolean;
  turn_number: number;
  winner: 'p1' | 'p2' | 'draw' | null;
  nozdormu_active: boolean;
  turn_started_at: number;
  pending_choice: {
    choice_type: string;
    source_card_id: string;
    options: (CardDef & { uid: string })[];
  } | null;
  waiting_for_opponent_choice: boolean;
  last_emote: {
    id: number;
    seat: 'p1' | 'p2';
    name: string;
    text: string;
  } | null;
  me: {
    seat: 'p1' | 'p2';
    name: string;
    deck_name: string;
    mulligan_done: boolean;
    mana: number;
    max_mana: number;
    overloaded: number;
    pending_overload: number;
    deck_count: number;
    hand_count: number;
    fatigue: number;
    combo_active: boolean;
    cards_played_this_turn: number;
    spell_damage: number;
    hero: HeroView;
    weapon: WeaponView | null;
    secrets: SecretView[];
    board: BoardMinion[];
    hand: HandCard[];
  };
  opponent: {
    seat: 'p1' | 'p2';
    name: string;
    deck_name: string;
    mulligan_done: boolean;
    mana: number;
    max_mana: number;
    overloaded: number;
    pending_overload: number;
    deck_count: number;
    hand_count: number;
    fatigue: number;
    spell_damage: number;
    hero: HeroView;
    weapon: WeaponView | null;
    secrets: SecretView[];
    board: BoardMinion[];
  };
  log: LogEntry[];
}

export interface GameSummary {
  game_id: string;
  mode: GameStateView['mode'];
  phase: string;
  turn_number: number;
  active_seat: string;
  winner: string | null;
  p1: { name: string; hero_class: string; hp: number };
  p2: { name: string; hero_class: string; hp: number };
  is_latest: boolean;
  viewer_seat?: Seat;
  /** Matches on this device: how strong the opponent plays. */
  level?: string;
}

/** One structured engine event (see engine/game.py `emit`). */
export interface GameEvent {
  seq: number;
  t: string;
  seat?: 'p1' | 'p2';
  target?: string | null;
  [key: string]: any;
}

/** Everything one action caused, plus the view once it has resolved. */
export interface Beat {
  seq: number;
  prev: number;
  events: GameEvent[];
  state: GameStateView;
}

/** `beats` is null when the server cannot replay from the caller's position. */
export interface StatePayload {
  state: GameStateView;
  beats: Beat[] | null;
  agent?: AgentStatus | null;
}

/** Whoever thinks in the other seat: the outside agent (agent_vs_human) or the on-device opponent (ai_vs_human). */
export interface AgentStatus {
  model: string;
  label: string;
  thinking: boolean;
  /** The outside agent is writing an answer to something said at the table. */
  typing?: boolean;
  error: string;
  /** Grows with every change on the server; a lower number is an older status. */
  rev: number;
}

export interface AgentInfo {
  available: boolean;
  default: string;
  models: { id: string; label: string }[];
}

/** `device` is the built-in opponent on this device; the others need the server. */
export type OpponentMode = 'bot' | 'agent' | 'cli' | 'device' | 'friend';

/** How strong the on-device opponent plays. */
export interface Level {
  id: string;
  label: string;
  /** What the opponent is called at this level. */
  name: string;
}

export type Seat = 'p1' | 'p2';
