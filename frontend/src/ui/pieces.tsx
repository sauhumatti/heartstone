// The game's pieces: card faces, card backs, board minions, stat badges.
import React, { useEffect, useState } from 'react';
import { artUrl } from '../api';
import type { BoardMinion, CardDef, HandCard, HeroMeta } from '../types';

export const NEUTRAL_COLOR = '#8f8a7d';

export function classColor(heroes: Record<string, HeroMeta>, cardClass: string | undefined | null): string {
  return (cardClass && heroes[cardClass]?.color) || NEUTRAL_COLOR;
}

export function pretty(word: string): string {
  if (word === 'MECHANICAL') return 'Mech';
  return word
    .toLowerCase()
    .split('_')
    .map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w))
    .join(' ');
}

/** Card art with a quiet patterned fallback when an image is missing. */
export const Art: React.FC<{ id: string | null | undefined; alt?: string; tint?: string; lazy?: boolean }> = ({
  id,
  alt = '',
  tint,
  lazy = false,
}) => {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [id]);
  if (!id || failed) {
    return <div className="art-missing" style={{ ['--tint' as any]: tint || NEUTRAL_COLOR }} aria-hidden="true" />;
  }
  // Pieces in a match load at once so they are there when they animate in; long lists load as they scroll into view.
  return (
    <img className="art" src={artUrl(id)} alt={alt} draggable={false} loading={lazy ? 'lazy' : 'eager'} onError={() => setFailed(true)} />
  );
};

/** A number that pops whenever it changes. */
export const Num: React.FC<{ value: number | string; tone?: 'up' | 'down' | '' }> = ({ value, tone = '' }) => (
  <span key={String(value)} className={`num ${tone}`}>
    {value}
  </span>
);

type Glyph = 'windfury' | 'death' | 'spark' | 'eye' | 'mute' | 'bolt' | 'aura' | 'sleep' | 'lock' | 'no';

const GLYPHS: Record<Glyph, React.ReactNode> = {
  windfury: <path d="M5 8l5 4-5 4M12 8l5 4-5 4" />,
  death: (
    <>
      <path d="M6 11a6 6 0 1112 0c0 2-1 3.4-2 4.2V18H8v-2.8C7 14.400 6 13 6 11z" />
      <path d="M10 18v2M14 18v2" />
      <circle cx="9.800" cy="11.200" r="1.100" fill="currentColor" stroke="none" />
      <circle cx="14.200" cy="11.200" r="1.100" fill="currentColor" stroke="none" />
    </>
  ),
  spark: <path d="M12 3l1.800 6.200L20 12l-6.200 1.800L12 21l-1.800-7.200L4 12l6.200-2.800z" />,
  eye: (
    <>
      <path d="M3 12s3.500-6 9-6 9 6 9 6-3.500 6-9 6-9-6-9-6z" />
      <path d="M4 20L20 4" />
    </>
  ),
  mute: (
    <>
      <path d="M4 6h16v9H11l-4 4v-4H4z" />
      <path d="M9 8.500l6 4M15 8.500l-6 4" />
    </>
  ),
  bolt: <path d="M13 3L6 13h5l-1 8 8-11h-5z" />,
  aura: (
    <>
      <circle cx="12" cy="12" r="3" />
      <circle cx="12" cy="12" r="8" strokeDasharray="3 3" />
    </>
  ),
  sleep: <path d="M8 7h6l-6 6h6M15 13h4l-4 4h4" />,
  lock: (
    <>
      <rect x="6" y="11" width="12" height="9" rx="2" />
      <path d="M9 11V8a3 3 0 016 0v3" />
    </>
  ),
  no: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M6.500 17.500l11-11" />
    </>
  ),
};

export const Icon: React.FC<{ name: Glyph; title?: string }> = ({ name, title }) => (
  <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" role={title ? 'img' : undefined} aria-label={title} aria-hidden={title ? undefined : true}>
    {title && <title>{title}</title>}
    {GLYPHS[name]}
  </svg>
);

/** The back of a card: drawn here, the same for both players. */
/**
 * The back of a card. `art` is a picture to wear in place of the drawn one
 * (see progress/): the opponent's cards and a player who has chosen none keep the drawn back.
 */
export const CardBack: React.FC<{ className?: string; style?: React.CSSProperties; art?: string } & React.HTMLAttributes<HTMLDivElement>> = ({
  className = '',
  style,
  art,
  ...rest
}) => (
  <div className={`cardback ${art ? 'has-art' : ''} ${className}`} style={style} {...rest}>
    {art ? (
      <img src={art} alt="" draggable={false} />
    ) : (
      <svg viewBox="0 0 60 84" preserveAspectRatio="none" aria-hidden="true">
        <rect x="4" y="4" width="52" height="76" rx="5" className="cb-line" />
        <path d="M30 14 L48 42 L30 70 L12 42 Z" className="cb-line" />
        <path d="M30 24 L41 42 L30 60 L19 42 Z" className="cb-fill" />
        <circle cx="30" cy="42" r="4.500" className="cb-glow" />
        <path d="M30 8v4M30 72v4M8 42h3M49 42h3" className="cb-line" />
      </svg>
    )}
  </div>
);

const KEYWORD_RE_CACHE = new Map<string, RegExp>();

/** Bold the leading "Keyword:" and any of the card's own mechanics in its text. */
export function richText(text: string, mechanics: string[] = []): React.ReactNode {
  if (!text) return null;
  const words = mechanics.map(pretty).filter((w) => w.length > 2);
  const key = words.join('|');
  let re = KEYWORD_RE_CACHE.get(key);
  if (!re) {
    const alt = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|');
    re = new RegExp(`(^[A-Z][A-Za-z ]{2,16}:${alt ? `|\\b(?:${alt})\\b` : ''})`, 'g');
    KEYWORD_RE_CACHE.set(key, re);
  }
  const parts = text.split(re);
  return parts.map((p, i) => (i % 2 === 1 ? <b key={i}>{p}</b> : <React.Fragment key={i}>{p}</React.Fragment>));
}

export type CardLike = Pick<CardDef, 'name' | 'card_class' | 'type' | 'cost' | 'attack' | 'health' | 'durability' | 'rarity' | 'race' | 'text' | 'mechanics'> & {
  id?: string;
  card_id?: string;
  base_cost?: number;
};

interface CardFaceProps {
  card: CardLike;
  heroes: Record<string, HeroMeta>;
  className?: string;
  lazy?: boolean;
  /** Current stats when they differ from the printed ones (a minion in play). */
  live?: { attack: number; health: number; baseAttack: number; baseHealth: number; damaged: boolean };
}

export const CardFace: React.FC<CardFaceProps> = ({ card, heroes, className = '', live, lazy = false }) => {
  const id = card.card_id || card.id || null;
  const color = classColor(heroes, card.card_class);
  const base = card.base_cost ?? card.cost;
  const costTone = card.cost < base ? 'up' : card.cost > base ? 'down' : '';
  const kind = [pretty(card.type), card.race ? pretty(card.race) : ''].filter(Boolean).join(' · ');
  const atk = live ? live.attack : card.attack ?? 0;
  const hp = live ? live.health : card.health ?? 0;
  const atkTone = live ? (live.attack > live.baseAttack ? 'up' : live.attack < live.baseAttack ? 'down' : '') : '';
  const hpTone = live ? (live.damaged ? 'down' : live.health > live.baseHealth ? 'up' : '') : '';

  return (
    <div
      className={`card card-${card.type.toLowerCase()} rarity-${card.rarity.toLowerCase()} ${className}`}
      style={{ ['--class' as any]: color }}
    >
      <div className="card-art">
        <Art id={id} alt="" tint={color} lazy={lazy} />
      </div>
      <div className="card-plate">
        <div className="card-name">{card.name}</div>
        <div className="card-text">{richText(card.text, card.mechanics)}</div>
        <div className="card-kind">{kind}</div>
      </div>
      <div className="card-edge" />
      <div className="card-cost">
        <Num value={card.cost} tone={costTone} />
      </div>
      <div className="card-rarity" title={pretty(card.rarity)} />
      {card.type === 'MINION' && (
        <>
          <div className="badge atk">
            <Num value={atk} tone={atkTone} />
          </div>
          <div className="badge hp">
            <Num value={hp} tone={hpTone} />
          </div>
        </>
      )}
      {card.type === 'WEAPON' && (
        <>
          <div className="badge atk">
            <Num value={card.attack ?? 0} />
          </div>
          <div className="badge dur">
            <Num value={card.durability ?? 0} />
          </div>
        </>
      )}
    </div>
  );
};

export function isHandCard(c: CardDef | HandCard): c is HandCard {
  return 'can_play' in c;
}

/** A minion as a card, for the hover preview. */
export function minionAsCard(m: BoardMinion): CardLike {
  return {
    card_id: m.card_id,
    name: m.name,
    card_class: m.card_class,
    type: 'MINION',
    cost: m.cost,
    attack: m.attack,
    health: m.health,
    durability: null,
    rarity: m.rarity as CardDef['rarity'],
    race: m.race,
    text: m.text,
    mechanics: m.keywords,
  };
}

const CHIP_KEYWORDS: Record<string, Glyph> = {
  WINDFURY: 'windfury',
  DEATHRATTLE: 'death',
  ELUSIVE: 'eye',
  TRIGGER_VISUAL: 'bolt',
  AURA: 'aura',
  CANT_ATTACK: 'no',
};

interface MinionTileProps {
  minion: BoardMinion;
  friendly: boolean;
  ready: boolean;
  selected: boolean;
  targetable: boolean;
  dimmed: boolean;
  onPointerDown?: (e: React.PointerEvent) => void;
  onClick?: () => void;
  onEnter?: (e: React.PointerEvent) => void;
  onLeave?: () => void;
}

export const MinionTile: React.FC<MinionTileProps> = ({
  minion: m,
  friendly,
  ready,
  selected,
  targetable,
  dimmed,
  onPointerDown,
  onClick,
  onEnter,
  onLeave,
}) => {
    const has = (k: string) => m.keywords.includes(k);
    const atkTone = m.attack > m.base_attack ? 'up' : m.attack < m.base_attack ? 'down' : '';
    const hpTone = m.damaged ? 'down' : m.max_health > m.base_health ? 'up' : '';
    const asleep = friendly && m.summoned_this_turn && !ready && !has('CHARGE') && m.attack > 0;
    const cls = [
      'minion',
      has('TAUNT') ? 'is-guard' : '',
      has('DIVINE_SHIELD') ? 'is-shielded' : '',
      has('STEALTH') ? 'is-hidden' : '',
      m.frozen ? 'is-frozen' : '',
      m.silenced ? 'is-silenced' : '',
      m.immune ? 'is-immune' : '',
      m.rarity === 'LEGENDARY' ? 'is-legendary' : '',
      ready ? 'is-ready' : '',
      selected ? 'is-selected' : '',
      targetable ? 'is-targetable' : '',
      dimmed ? 'is-dimmed' : '',
    ]
      .filter(Boolean)
      .join(' ');

    return (
      <div
        className="slot"
        data-uid={m.uid}
        data-flip={`m:${m.uid}`}
        onPointerDown={onPointerDown}
        onClick={onClick}
        onPointerEnter={onEnter}
        onPointerLeave={onLeave}
      >
        <div className={cls}>
          <div className="minion-art">
            <Art id={m.card_id} alt={m.name} />
          </div>
          <div className="minion-frame" />
          <div className="minion-shield" />
          <div className="minion-frost" />
          <div className="minion-veil" />
          <div className="minion-chips">
            {Object.entries(CHIP_KEYWORDS).map(([k, g]) => (has(k) ? <Icon key={k} name={g} title={pretty(k)} /> : null))}
            {m.spell_damage > 0 && (
              <span className="chip-num">
                <Icon name="spark" title="Spell damage" />+{m.spell_damage}
              </span>
            )}
            {m.silenced && <Icon name="mute" title="Silenced" />}
            {asleep && <Icon name="sleep" title="Ready next turn" />}
          </div>
          <div className="badge atk">
            <Num value={m.attack} tone={atkTone} />
          </div>
          <div className="badge hp">
            <Num value={m.health} tone={hpTone} />
          </div>
        </div>
      </div>
    );
};
