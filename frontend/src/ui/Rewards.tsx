// The rewards screen: where the player stands (rating and rank), the packs
// waiting to be opened, and everything found so far, to put on.
import React, { useState } from 'react';
import {
  buy,
  type Cosmetic,
  type CosmeticKind,
  COSMETICS,
  FINDABLE,
  formatDelta,
  OPPONENTS,
  owns,
  PACK_STEPS,
  priceOf,
  RANKS,
  rankIndex,
  wear,
} from '../progress/rules';
import { updateProfile, useProfile } from '../progress/store';
import { CosmeticView, PackIcon, PackMeter, RankBadge, RankLine, TierTag } from './progressBits';

const TABS: { kind: CosmeticKind; label: string }[] = [
  { kind: 'back', label: 'Card backs' },
  { kind: 'table', label: 'Tables' },
  { kind: 'title', label: 'Titles' },
];

const RESULT_WORD = { win: 'Won', loss: 'Lost', draw: 'Drew' } as const;

export const Rewards: React.FC<{ onBack: () => void; onOpenPack: () => void }> = ({ onBack, onOpenPack }) => {
  const p = useProfile();
  const [tab, setTab] = useState<CosmeticKind>('back');
  const [asking, setAsking] = useState<Cosmetic | null>(null);
  const at = rankIndex(p.rating);
  const found = FINDABLE.filter((c) => p.owned.includes(c.id)).length;
  const items = COSMETICS.filter((c) => c.kind === tab);

  return (
    <div className="screen page rewards">
      <header className="page-head">
        <button type="button" className="btn ghost" onClick={onBack}>
          ← Menu
        </button>
        <h1>Rewards</h1>
        <span className="page-count">
          {found} of {FINDABLE.length} found · <span className="embers">{p.embers} embers</span>
        </span>
      </header>

      <div className="rewards-top">
        <section className="panel standing">
          <RankBadge index={at} className="standing-badge" />
          <div className="standing-main">
            <RankLine rating={p.rating} />
            <p className="standing-record">
              {p.played === 0
                ? 'No rated match yet. Every match against an opponent counts, except the command line.'
                : `${p.wins} won · ${p.losses} lost${p.draws ? ` · ${p.draws} drawn` : ''}${p.streak > 1 ? ` · ${p.streak} wins in a row` : ''} · best rank ${RANKS[p.bestRank].name}`}
            </p>
          </div>
          <ol className="ladder" aria-label="The ranks">
            {RANKS.map((r, i) => (
              <li key={r.id} className={i === at ? 'is-here' : i <= p.bestRank ? 'is-reached' : ''} title={i === 0 ? `Below ${RANKS[1].min}` : `From ${r.min}`}>
                <RankBadge index={i} />
                <span>{r.name}</span>
                <small>{i === 0 ? `< ${RANKS[1].min}` : r.min}</small>
              </li>
            ))}
          </ol>
        </section>

        <section className="panel packs">
          <PackIcon className={p.packs > 0 ? 'is-ready' : ''} />
          <div className="packs-main">
            <h2>{p.packs === 0 ? 'No lantern to light' : p.packs === 1 ? '1 lantern to light' : `${p.packs} lanterns to light`}</h2>
            <p>
              <PackMeter meter={p.meter} /> {PACK_STEPS - p.meter} more {PACK_STEPS - p.meter === 1 ? 'win' : 'wins'} for the next one
            </p>
            <p className="note">
              Three wins earn a lantern (a win over {OPPONENTS.hard.name} counts twice), and so does every rank reached for the first time. Each holds
              three things to wear.
            </p>
            <button type="button" className="btn primary" disabled={p.packs < 1} onClick={onOpenPack}>
              Light a lantern
            </button>
          </div>
        </section>
      </div>

      <section className="panel wardrobe">
        <div className="wardrobe-head">
          <div className="seg">
            {TABS.map((t) => (
              <button key={t.kind} type="button" className={tab === t.kind ? 'is-on' : ''} onClick={() => setTab(t.kind)}>
                {t.label}
              </button>
            ))}
          </div>
          <span className="note">Second copies turn into embers. Embers buy what is still missing.</span>
        </div>
        <div className={`wardrobe-grid kind-${tab}`}>
          {items.map((item) => {
            const mine = owns(p, item.id);
            const worn = p.worn[item.kind] === item.id;
            const price = priceOf(p, item.id);
            return (
              <div key={item.id} className={`ware ${mine ? 'is-mine' : 'is-missing'} ${worn ? 'is-worn' : ''}`}>
                <button
                  type="button"
                  className="ware-pick"
                  disabled={!mine || worn}
                  onClick={() => updateProfile((cur) => wear(cur, item.id))}
                  aria-label={mine ? (worn ? `${item.name}, in use` : `Use ${item.name}`) : `${item.name}, not found yet`}
                >
                  <CosmeticView item={item} />
                </button>
                <strong>{item.name}</strong>
                <TierTag item={item} />
                {worn ? (
                  <span className="ware-state">In use</span>
                ) : mine ? (
                  <button type="button" className="btn small" onClick={() => updateProfile((cur) => wear(cur, item.id))}>
                    Use
                  </button>
                ) : (
                  <button type="button" className="btn small" disabled={price === null || p.embers < price} onClick={() => setAsking(item)}>
                    {price} embers
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {p.matches.length > 0 && (
        <section className="panel match-history">
          <h2>Last matches</h2>
          <ul>
            {p.matches.slice(0, 8).map((m) => (
              <li key={m.id} className={`is-${m.result}`}>
                <span>
                  {RESULT_WORD[m.result]} against {OPPONENTS[m.opponent].name}
                </span>
                <span className="history-delta">{formatDelta(m.before, m.after)}</span>
                <span className="history-after">{Math.round(m.after)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {asking && (
        <div className="modal" onClick={() => setAsking(null)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <h2>Get {asking.name}?</h2>
            <p className="sheet-sub">
              It costs {priceOf(p, asking.id)} of your {p.embers} embers.
            </p>
            <div className="menu-list">
              <button
                type="button"
                className="btn primary"
                onClick={() => {
                  updateProfile((cur) => wear(buy(cur, asking.id), asking.id));
                  setAsking(null);
                }}
              >
                Get it and use it
              </button>
              <button type="button" className="btn" onClick={() => setAsking(null)}>
                Not now
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
