import React from 'react';
import type { BoardMinion, CardDef, HandCard } from '../types';
import { CardArt } from './CardArt';

const RARITY_COLORS: Record<string, string> = {
  FREE: '#7d8590',
  COMMON: '#f0f6fc',
  RARE: '#2f81f7',
  EPIC: '#a371f7',
  LEGENDARY: '#f79c1d',
};

interface FullCardProps {
  card: CardDef | HandCard;
  compact?: boolean;
  selected?: boolean;
  replaced?: boolean;
  onClick?: () => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  countBadge?: number;
}

export const FullCard: React.FC<FullCardProps> = ({
  card,
  compact = false,
  selected = false,
  replaced = false,
  onClick,
  onMouseEnter,
  onMouseLeave,
  countBadge,
}) => {
  const isHand = 'can_play' in card;
  const handCard = isHand ? (card as HandCard) : null;
  const playable = handCard ? handCard.can_play : false;
  const comboGlow = handCard ? handCard.combo_glow : false;
  const cost = handCard ? handCard.cost : card.cost;
  const baseCost = handCard ? handCard.base_cost : card.cost;
  const costClass =
    cost < baseCost ? 'stat-buffed' : cost > baseCost ? 'stat-debuffed' : '';

  const rarityColor = RARITY_COLORS[card.rarity] || '#7d8590';
  const cls = [
    'hs-card',
    `hs-class-${card.card_class.toLowerCase()}`,
    compact ? 'hs-card-compact' : '',
    playable ? 'hs-card-playable' : '',
    playable && comboGlow ? 'hs-card-combo' : '',
    selected ? 'hs-card-selected' : '',
    replaced ? 'hs-card-replaced' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={cls}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      title={handCard && !playable && handCard.unplayable_reason ? handCard.unplayable_reason : card.text}
    >
      <div className={`mana-gem ${costClass}`}>{cost}</div>
      {countBadge !== undefined && countBadge > 0 && (
        <div className="deck-count-badge">x{countBadge}</div>
      )}
      <div className="hs-card-portrait">
        <CardArt
          cardId={isHand ? (card as HandCard).card_id : (card as CardDef).id}
          name={card.name}
          cardClass={card.card_class}
          type={card.type}
          race={card.race}
          mechanics={card.mechanics}
          rarity={card.rarity}
        />
      </div>
      <div className="hs-card-banner">{card.name}</div>
      <div className="rarity-jewel" style={{ backgroundColor: rarityColor }} />
      <div className="hs-card-text">
        {card.text || (card.type === 'MINION' ? 'No special text.' : '')}
      </div>
      {card.race && <div className="hs-card-race">{card.race}</div>}
      {card.type === 'MINION' && (
        <>
          <div className="stat-gem stat-atk">{card.attack ?? 0}</div>
          <div className="stat-gem stat-hp">{card.health ?? 0}</div>
        </>
      )}
      {card.type === 'WEAPON' && (
        <>
          <div className="stat-gem stat-wep-atk">{card.attack ?? 0}</div>
          <div className="stat-gem stat-wep-dur">{card.durability ?? 0}</div>
        </>
      )}
      {replaced && <div className="mulligan-x">REPLACE</div>}
    </div>
  );
};

interface MinionTokenProps {
  minion: BoardMinion;
  isFriendly: boolean;
  isSelectedAttacker: boolean;
  isValidTarget: boolean;
  onClick?: () => void;
  onHover?: (m: BoardMinion | null) => void;
}

export const MinionToken: React.FC<MinionTokenProps> = ({
  minion,
  isFriendly,
  isSelectedAttacker,
  isValidTarget,
  onClick,
  onHover,
}) => {
  const hasTaunt = minion.keywords.includes('TAUNT');
  const hasShield = minion.keywords.includes('DIVINE_SHIELD');
  const hasStealth = minion.keywords.includes('STEALTH');
  const hasWindfury = minion.keywords.includes('WINDFURY');
  const hasElusive = minion.keywords.includes('ELUSIVE');
  const hasDeathrattle = minion.keywords.includes('DEATHRATTLE');

  const atkClass =
    minion.attack > minion.base_attack
      ? 'stat-buffed'
      : minion.attack < minion.base_attack
        ? 'stat-debuffed'
        : '';
  const hpClass = minion.damaged
    ? 'stat-debuffed'
    : minion.max_health > minion.base_health
      ? 'stat-buffed'
      : '';

  const cls = [
    'board-minion',
    hasTaunt ? 'minion-taunt' : '',
    hasShield ? 'minion-shield' : '',
    hasStealth ? 'minion-stealth' : '',
    minion.frozen ? 'minion-frozen' : '',
    minion.silenced ? 'minion-silenced' : '',
    isFriendly && minion.can_attack ? 'minion-ready' : '',
    isSelectedAttacker ? 'minion-selected' : '',
    isValidTarget ? 'minion-targetable' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={cls}
      onClick={onClick}
      onMouseEnter={() => onHover?.(minion)}
      onMouseLeave={() => onHover?.(null)}
    >
      <div className="minion-art-wrap">
        <CardArt
          cardId={minion.card_id}
          name={minion.name}
          cardClass="NEUTRAL"
          type="MINION"
          race={minion.race}
          mechanics={minion.keywords}
          rarity={minion.rarity}
        />
      </div>
      <div className="minion-name">{minion.name}</div>
      <div className="minion-badges">
        {hasTaunt && <span title="Taunt">🛡</span>}
        {hasWindfury && <span title="Windfury">⚡</span>}
        {hasElusive && <span title="Elusive">✨</span>}
        {hasDeathrattle && !minion.silenced && <span title="Deathrattle">💀</span>}
        {minion.spell_damage > 0 && <span title={`Spell Damage +${minion.spell_damage}`}>🔮+{minion.spell_damage}</span>}
        {minion.silenced && <span title="Silenced">🔇</span>}
      </div>
      <div className={`stat-gem stat-atk ${atkClass}`}>{minion.attack}</div>
      <div className={`stat-gem stat-hp ${hpClass}`}>{minion.health}</div>
    </div>
  );
};
