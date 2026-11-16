import React, { useMemo, useState } from 'react';
import type { CardDef, DeckInfo, HeroMeta } from '../types';
import { FullCard } from './CardView';

interface DeckbuilderViewProps {
  heroes: Record<string, HeroMeta>;
  cards: CardDef[];
  decks: DeckInfo[];
  onSaveDeck: (payload: { id?: string; name: string; hero_class: string; cards: string[] }) => Promise<void>;
  onDeleteDeck: (deckId: string) => Promise<void>;
  onBack: () => void;
}

export const DeckbuilderView: React.FC<DeckbuilderViewProps> = ({
  heroes,
  cards,
  decks,
  onSaveDeck,
  onDeleteDeck,
  onBack,
}) => {
  const [heroClass, setHeroClass] = useState<string>('MAGE');
  const [classTab, setClassTab] = useState<string>('CLASS_AND_NEUTRAL');
  const [manaFilter, setManaFilter] = useState<string>('ALL');
  const [rarityFilter, setRarityFilter] = useState<string>('ALL');
  const [search, setSearch] = useState('');
  const [deckName, setDeckName] = useState('My Classic Mage');
  const [editingId, setEditingId] = useState<string | undefined>(undefined);
  const [deckCards, setDeckCards] = useState<string[]>([]);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const cardById = useMemo(() => {
    const map: Record<string, CardDef> = {};
    for (const c of cards) map[c.id] = c;
    return map;
  }, [cards]);

  const cardCounts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const id of deckCards) m[id] = (m[id] || 0) + 1;
    return m;
  }, [deckCards]);

  const filteredCards = useMemo(() => {
    const q = search.trim().toLowerCase();
    return cards.filter((c) => {
      if (classTab === 'CLASS_AND_NEUTRAL') {
        if (c.card_class !== heroClass && c.card_class !== 'NEUTRAL') return false;
      } else if (classTab === 'CLASS_ONLY') {
        if (c.card_class !== heroClass) return false;
      } else if (classTab === 'NEUTRAL_ONLY') {
        if (c.card_class !== 'NEUTRAL') return false;
      }
      if (manaFilter !== 'ALL') {
        const m = Number(manaFilter);
        if (m === 7 ? c.cost < 7 : c.cost !== m) return false;
      }
      if (rarityFilter !== 'ALL' && c.rarity !== rarityFilter) return false;
      if (q) {
        const hay = `${c.name} ${c.text} ${c.race || ''} ${c.mechanics.join(' ')} ${c.type}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [cards, heroClass, classTab, manaFilter, rarityFilter, search]);

  const sortedDeckEntries = useMemo(() => {
    return Object.entries(cardCounts)
      .map(([id, count]) => ({ card: cardById[id], count }))
      .filter((x) => Boolean(x.card))
      .sort((a, b) => a.card.cost - b.card.cost || a.card.name.localeCompare(b.card.name));
  }, [cardCounts, cardById]);

  const manaCurve = useMemo(() => {
    const buckets = [0, 0, 0, 0, 0, 0, 0, 0];
    for (const id of deckCards) {
      const c = cardById[id];
      if (!c) continue;
      buckets[Math.min(7, c.cost)]++;
    }
    return buckets;
  }, [deckCards, cardById]);

  const switchHeroClass = (cls: string) => {
    setHeroClass(cls);
    setEditingId(undefined);
    setDeckCards([]);
    setDeckName(`My Classic ${cls.charAt(0) + cls.slice(1).toLowerCase()}`);
    setErr('');
    setMsg('');
  };

  const addCardToDeck = (card: CardDef) => {
    setErr('');
    setMsg('');
    if (deckCards.length >= 30) {
      setErr('Deck already has 30 cards.');
      return;
    }
    const cur = cardCounts[card.id] || 0;
    const maxCopies = card.rarity === 'LEGENDARY' ? 1 : 2;
    if (cur >= maxCopies) {
      setErr(`Max ${maxCopies} copy/copies of ${card.name}.`);
      return;
    }
    setDeckCards([...deckCards, card.id]);
  };

  const removeOneFromDeck = (cardId: string) => {
    const idx = deckCards.indexOf(cardId);
    if (idx >= 0) {
      const next = [...deckCards];
      next.splice(idx, 1);
      setDeckCards(next);
    }
  };

  const loadTemplate = (d: DeckInfo) => {
    setHeroClass(d.hero_class);
    setDeckCards([...d.cards]);
    if (d.builtin) {
      setEditingId(undefined);
      setDeckName(`${d.name} (Copy)`);
    } else {
      setEditingId(d.id);
      setDeckName(d.name);
    }
    setErr('');
    setMsg(`Loaded "${d.name}"`);
  };

  const handleSave = async () => {
    setErr('');
    setMsg('');
    try {
      await onSaveDeck({ id: editingId, name: deckName, hero_class: heroClass, cards: deckCards });
      setMsg('Deck saved!');
    } catch (e: any) {
      setErr(e.message || 'Save failed');
    }
  };

  const maxBucket = Math.max(1, ...manaCurve);

  return (
    <div
      className="tavern-stage"
      style={{
        backgroundImage: `linear-gradient(180deg, rgba(20,13,8,0.76), rgba(15,9,5,0.92)), url('/art/book_bg.webp')`,
      }}
    >
      <div className="stage-topbar">
        <button className="btn-secondary" onClick={onBack}>
          ← Back
        </button>
        <div className="stage-title">📖 CLASSIC COLLECTION &amp; DECKBUILDER (382 CARDS)</div>
        <div style={{ width: 90 }} />
      </div>
    <div className="deckbuilder-layout">
      <div className="collection-pane tavern-panel">
        <div className="panel-header">
          <div>
            <h2>Spellbook &amp; Minion Tome</h2>
            <p className="muted">Click any card to add it to your 30-card deck.</p>
          </div>
        </div>

        <div className="filters-bar">
          <div className="class-tabs">
            {Object.keys(heroes).map((cls) => (
              <button
                key={cls}
                type="button"
                className={heroClass === cls ? 'pill active' : 'pill'}
                onClick={() => switchHeroClass(cls)}
              >
                {cls}
              </button>
            ))}
          </div>

          <div className="subfilters">
            <select value={classTab} onChange={(e) => setClassTab(e.target.value)}>
              <option value="CLASS_AND_NEUTRAL">{heroClass} + Neutral</option>
              <option value="CLASS_ONLY">{heroClass} Only</option>
              <option value="NEUTRAL_ONLY">Neutral Only</option>
            </select>
            <select value={manaFilter} onChange={(e) => setManaFilter(e.target.value)}>
              <option value="ALL">All Mana</option>
              {[0, 1, 2, 3, 4, 5, 6].map((n) => (
                <option key={n} value={String(n)}>{n} Mana</option>
              ))}
              <option value="7">7+ Mana</option>
            </select>
            <select value={rarityFilter} onChange={(e) => setRarityFilter(e.target.value)}>
              <option value="ALL">All Rarities</option>
              <option value="FREE">Basic (Free)</option>
              <option value="COMMON">Common</option>
              <option value="RARE">Rare</option>
              <option value="EPIC">Epic</option>
              <option value="LEGENDARY">Legendary</option>
            </select>
            <input
              type="text"
              placeholder="Search name, text, tribe, keyword..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="collection-grid">
          {filteredCards.map((c) => (
            <FullCard
              key={c.id}
              card={c}
              compact
              countBadge={cardCounts[c.id]}
              onClick={() => addCardToDeck(c)}
            />
          ))}
        </div>
      </div>

      <aside className="deck-sidebar tavern-panel">
        <h3>Deck ({deckCards.length} / 30)</h3>
        <input
          type="text"
          value={deckName}
          onChange={(e) => setDeckName(e.target.value)}
          placeholder="Deck Name"
        />

        <div className="mana-curve">
          {manaCurve.map((cnt, i) => (
            <div key={i} className="curve-col">
              <div className="curve-cnt">{cnt || ''}</div>
              <div className="curve-bar-wrap">
                <div className="curve-bar" style={{ height: `${(cnt / maxBucket) * 100}%` }} />
              </div>
              <div className="curve-lbl">{i === 7 ? '7+' : i}</div>
            </div>
          ))}
        </div>

        <div className="deck-list">
          {sortedDeckEntries.map(({ card, count }) => (
            <button
              key={card.id}
              type="button"
              className="deck-list-row"
              onClick={() => removeOneFromDeck(card.id)}
              title="Click to remove 1 copy"
            >
              <span className="dl-cost">{card.cost}</span>
              <span className="dl-name">{card.name}</span>
              <span className="dl-qty">{count === 2 ? 'x2' : card.rarity === 'LEGENDARY' ? '★' : ''}</span>
            </button>
          ))}
        </div>

        {err && <div className="error-banner">{err}</div>}
        {msg && <div className="ok-banner">{msg}</div>}

        <div className="deck-actions">
          <button className="btn-primary" onClick={handleSave} disabled={deckCards.length !== 30}>
            Save Deck ({deckCards.length}/30)
          </button>
          <button className="btn-secondary" onClick={() => setDeckCards([])}>
            Clear
          </button>
          {editingId && (
            <button
              className="btn-danger"
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

        <div className="section-label" style={{ marginTop: '1rem' }}>Load / Edit Existing Deck</div>
        <div className="template-list">
          {decks.map((d) => (
            <button key={d.id} type="button" className="template-btn" onClick={() => loadTemplate(d)}>
              {d.hero_class}: {d.name} {d.builtin ? '' : '(Custom)'}
            </button>
          ))}
        </div>
      </aside>
    </div>
    </div>
  );
};
