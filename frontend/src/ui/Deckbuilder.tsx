import React, { useMemo, useState } from 'react';
import type { CardDef, DeckInfo, HeroMeta } from '../types';
import { CardFace, classColor, pretty } from './pieces';

interface DeckbuilderProps {
  heroes: Record<string, HeroMeta>;
  cards: CardDef[];
  decks: DeckInfo[];
  onSaveDeck: (payload: { id?: string; name: string; hero_class: string; cards: string[] }) => Promise<void>;
  onDeleteDeck: (deckId: string) => Promise<void>;
  onBack: () => void;
}

const DECK_SIZE = 30;
const RARITIES = ['FREE', 'COMMON', 'RARE', 'EPIC', 'LEGENDARY'];

export const Deckbuilder: React.FC<DeckbuilderProps> = ({ heroes, cards, decks, onSaveDeck, onDeleteDeck, onBack }) => {
  const classes = Object.keys(heroes);
  const [heroClass, setHeroClass] = useState<string>(classes[0] || '');
  const [scope, setScope] = useState<'BOTH' | 'CLASS' | 'NEUTRAL'>('BOTH');
  const [cost, setCost] = useState<number | null>(null);
  const [rarity, setRarity] = useState('ALL');
  const [search, setSearch] = useState('');
  const [deckName, setDeckName] = useState('New deck');
  const [editingId, setEditingId] = useState<string | undefined>(undefined);
  const [deckCards, setDeckCards] = useState<string[]>([]);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  /** On a phone the deck is a drawer at the bottom of the screen. */
  const [drawerOpen, setDrawerOpen] = useState(false);

  const byId = useMemo(() => {
    const map: Record<string, CardDef> = {};
    for (const c of cards) map[c.id] = c;
    return map;
  }, [cards]);

  const counts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const id of deckCards) m[id] = (m[id] || 0) + 1;
    return m;
  }, [deckCards]);

  const shown = useMemo(() => {
    const q = search.trim().toLowerCase();
    return cards.filter((c) => {
      if (scope === 'BOTH' && c.card_class !== heroClass && c.card_class !== 'NEUTRAL') return false;
      if (scope === 'CLASS' && c.card_class !== heroClass) return false;
      if (scope === 'NEUTRAL' && c.card_class !== 'NEUTRAL') return false;
      if (cost !== null && (cost === 7 ? c.cost < 7 : c.cost !== cost)) return false;
      if (rarity !== 'ALL' && c.rarity !== rarity) return false;
      if (q) {
        const hay = `${c.name} ${c.text} ${c.race || ''} ${c.mechanics.join(' ')} ${c.type}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [cards, heroClass, scope, cost, rarity, search]);

  const entries = useMemo(
    () =>
      Object.entries(counts)
        .map(([id, count]) => ({ card: byId[id], count }))
        .filter((x) => Boolean(x.card))
        .sort((a, b) => a.card.cost - b.card.cost || a.card.name.localeCompare(b.card.name)),
    [counts, byId],
  );

  const curve = useMemo(() => {
    const buckets = [0, 0, 0, 0, 0, 0, 0, 0];
    for (const id of deckCards) {
      const c = byId[id];
      if (c) buckets[Math.min(7, c.cost)]++;
    }
    return buckets;
  }, [deckCards, byId]);
  const tallest = Math.max(1, ...curve);

  const reset = () => {
    setErr('');
    setMsg('');
  };

  const pickClass = (cls: string) => {
    setHeroClass(cls);
    setEditingId(undefined);
    setDeckCards([]);
    setDeckName(`New ${pretty(cls)} deck`);
    reset();
  };

  const add = (card: CardDef) => {
    reset();
    if (deckCards.length >= DECK_SIZE) return setErr(`A deck holds ${DECK_SIZE} cards.`);
    const max = card.rarity === 'LEGENDARY' ? 1 : 2;
    if ((counts[card.id] || 0) >= max) return setErr(`${card.name}: at most ${max} in a deck.`);
    setDeckCards([...deckCards, card.id]);
  };

  const removeOne = (cardId: string) => {
    const idx = deckCards.indexOf(cardId);
    if (idx < 0) return;
    const next = [...deckCards];
    next.splice(idx, 1);
    setDeckCards(next);
  };

  const load = (d: DeckInfo) => {
    setHeroClass(d.hero_class);
    setDeckCards([...d.cards]);
    setEditingId(d.builtin ? undefined : d.id);
    setDeckName(d.builtin ? `${d.name} (copy)` : d.name);
    setErr('');
    setMsg(`Loaded ${d.name}.`);
  };

  const save = async () => {
    reset();
    try {
      await onSaveDeck({ id: editingId, name: deckName, hero_class: heroClass, cards: deckCards });
      setMsg('Saved.');
    } catch (e: any) {
      setErr(e?.message || 'Could not save.');
    }
  };

  const color = classColor(heroes, heroClass);

  return (
    <div className="screen page" style={{ ['--class' as any]: color }}>
      <header className="page-head">
        <button type="button" className="btn ghost" onClick={onBack}>
          ← Menu
        </button>
        <h1>Collection</h1>
        <span className="page-count">{shown.length} cards</span>
      </header>

      <div className="builder">
        <section className="panel builder-main">
          <div className="class-tabs">
            {classes.map((cls) => (
              <button
                key={cls}
                type="button"
                className={cls === heroClass ? 'is-on' : ''}
                style={{ ['--class' as any]: classColor(heroes, cls) }}
                onClick={() => pickClass(cls)}
              >
                {pretty(cls)}
              </button>
            ))}
          </div>

          <div className="filters">
            <div className="seg">
              <button type="button" className={scope === 'BOTH' ? 'is-on' : ''} onClick={() => setScope('BOTH')}>
                All
              </button>
              <button type="button" className={scope === 'CLASS' ? 'is-on' : ''} onClick={() => setScope('CLASS')}>
                {pretty(heroClass)}
              </button>
              <button type="button" className={scope === 'NEUTRAL' ? 'is-on' : ''} onClick={() => setScope('NEUTRAL')}>
                Neutral
              </button>
            </div>
            <div className="cost-row" aria-label="Cost">
              {[0, 1, 2, 3, 4, 5, 6, 7].map((n) => (
                <button key={n} type="button" className={cost === n ? 'is-on' : ''} onClick={() => setCost(cost === n ? null : n)}>
                  {n === 7 ? '7+' : n}
                </button>
              ))}
            </div>
            <select value={rarity} onChange={(e) => setRarity(e.target.value)} aria-label="Rarity">
              <option value="ALL">Any rarity</option>
              {RARITIES.map((r) => (
                <option key={r} value={r}>
                  {pretty(r)}
                </option>
              ))}
            </select>
            <input type="search" placeholder="Search name, text, type…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>

          <div className="card-grid">
            {shown.map((c) => (
              <button key={c.id} type="button" className="grid-card" onClick={() => add(c)} data-click-sound>
                <CardFace card={c} heroes={heroes} lazy />
                {counts[c.id] ? <span className="grid-count">×{counts[c.id]}</span> : null}
              </button>
            ))}
            {shown.length === 0 && <p className="note">Nothing matches these filters.</p>}
          </div>
        </section>

        <aside className={`panel builder-side ${drawerOpen ? 'is-open' : ''}`}>
          <button type="button" className="drawer-handle" onClick={() => setDrawerOpen((v) => !v)} aria-expanded={drawerOpen}>
            {deckName || 'Deck'}
            <span>
              {deckCards.length} / {DECK_SIZE} <i>▲</i>
            </span>
          </button>
          <input className="deck-name" type="text" value={deckName} maxLength={48} onChange={(e) => setDeckName(e.target.value)} aria-label="Deck name" />
          <div className="deck-meter">
            <strong>{deckCards.length}</strong> / {DECK_SIZE}
            <div className="deck-meter-bar">
              <i style={{ width: `${(deckCards.length / DECK_SIZE) * 100}%` }} />
            </div>
          </div>

          <div className="curve" aria-label="Cost curve">
            {curve.map((n, i) => (
              <div key={i} className="curve-col">
                <span>{n || ''}</span>
                <div>
                  <i style={{ height: `${(n / tallest) * 100}%` }} />
                </div>
                <em>{i === 7 ? '7+' : i}</em>
              </div>
            ))}
          </div>

          <ul className="deck-list">
            {entries.map(({ card, count }) => (
              <li key={card.id}>
                <button type="button" onClick={() => removeOne(card.id)} title="Remove one" data-click-sound>
                  <span className="dl-cost">{card.cost}</span>
                  <span className="dl-name">{card.name}</span>
                  <span className="dl-qty">{count > 1 ? `×${count}` : ''}</span>
                </button>
              </li>
            ))}
            {entries.length === 0 && <li className="note">Click cards to add them.</li>}
          </ul>

          {err && <div className="alert">{err}</div>}
          {msg && <div className="alert ok">{msg}</div>}

          <div className="builder-actions">
            <button type="button" className="btn primary" onClick={save} disabled={deckCards.length !== DECK_SIZE}>
              Save deck
            </button>
            <button type="button" className="btn ghost" onClick={() => setDeckCards([])}>
              Clear
            </button>
            {editingId && (
              <button
                type="button"
                className="btn danger"
                onClick={async () => {
                  await onDeleteDeck(editingId);
                  setEditingId(undefined);
                  setDeckCards([]);
                }}
              >
                Delete
              </button>
            )}
          </div>

          <h3>Start from a deck</h3>
          <div className="template-list">
            {decks.map((d) => (
              <button key={d.id} type="button" onClick={() => load(d)} style={{ ['--class' as any]: classColor(heroes, d.hero_class) }}>
                <i />
                {d.name}
                {!d.builtin && <em>custom</em>}
              </button>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
};
