// Small pieces the menu, the result screen and the rewards screen share.
import React from 'react';
import { artOf, rankArt } from '../progress/art';
import { type Cosmetic, PACK_STEPS, RANKS, rankProgress, TIERS } from '../progress/rules';
import { CardBack } from './pieces';

export const RankBadge: React.FC<{ index: number; className?: string }> = ({ index, className = '' }) => {
  const src = rankArt(index);
  const name = RANKS[index]?.name ?? '';
  return src ? (
    <img className={`rank-badge ${className}`} src={src} alt={name} draggable={false} />
  ) : (
    <span className={`rank-badge rank-badge-plain ${className}`} role="img" aria-label={name}>
      {name.slice(0, 1)}
    </span>
  );
};

/** Rank, rating and how far it is to the next rank. */
export const RankLine: React.FC<{ rating: number; className?: string }> = ({ rating, className = '' }) => {
  const at = rankProgress(rating);
  return (
    <div className={`rank-line ${className}`}>
      <div className="rank-line-top">
        <strong>{at.rank.name}</strong>
        <span className="rank-rating">{Math.round(rating)}</span>
      </div>
      <div className="rank-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(at.fraction * 100)}>
        <i style={{ width: `${Math.round(at.fraction * 100)}%` }} />
      </div>
      <div className="rank-line-foot">{at.next ? `${at.toNext} to ${at.next.name}` : 'The highest rank'}</div>
    </div>
  );
};

/** The three steps to the next pack. `fresh` steps were just earned and light up. */
export const PackMeter: React.FC<{ meter: number; fresh?: number }> = ({ meter, fresh = 0 }) => (
  <span className="pack-meter" role="img" aria-label={`${meter} of ${PACK_STEPS} wins towards the next pack`}>
    {Array.from({ length: PACK_STEPS }).map((_, i) => (
      <i key={i} className={i < meter ? (i >= meter - fresh ? 'on fresh' : 'on') : ''} />
    ))}
  </span>
);

/** The sealed lantern a pack is. */
export const PackIcon: React.FC<{ className?: string }> = ({ className = '' }) => {
  const src = artOf('pack_sealed');
  return src ? <img className={`pack-icon ${className}`} src={src} alt="" draggable={false} /> : <span className={`pack-icon pack-icon-plain ${className}`} />;
};

/** One thing to wear, drawn as what it is: a card back, a patch of table, or a title. */
export const CosmeticView: React.FC<{ item: Cosmetic; className?: string }> = ({ item, className = '' }) => {
  if (item.kind === 'back') return <CardBack className={`cos cos-back ${className}`} art={item.tier ? artOf(item.id) : undefined} />;
  if (item.kind === 'table') {
    const src = item.tier ? artOf(item.id) : undefined;
    return <div className={`cos cos-table ${src ? 'has-art' : ''} ${className}`} style={src ? { ['--felt-art' as any]: `url(${src})` } : undefined} />;
  }
  return (
    <div className={`cos cos-title ${item.tier ? '' : 'is-none'} ${className}`}>
      <span>{item.name}</span>
    </div>
  );
};

export const TierTag: React.FC<{ item: Cosmetic }> = ({ item }) =>
  item.tier ? <span className={`tier-tag tier-${item.tier}`}>{TIERS[item.tier].name}</span> : <span className="tier-tag tier-own">Yours from the start</span>;

export const KIND_NAME: Record<Cosmetic['kind'], string> = { back: 'Card back', table: 'Table', title: 'Title' };
