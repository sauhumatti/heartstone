import React, { useEffect, useMemo, useState } from 'react';
import { BRAND } from '../branding';
import { HAS_SERVER } from '../paths';
import { PACK_STEPS, rankIndex } from '../progress/rules';
import { useProfile } from '../progress/store';
import type { CardDef, GameSummary } from '../types';
import { AppUpdateLine } from './AppUpdate';
import { OfflineLine } from './Offline';
import { Art } from './pieces';
import { PackIcon, PackMeter, RankBadge, RankLine } from './progressBits';

interface MenuProps {
  cards: CardDef[];
  classCount: number;
  games: GameSummary[];
  /** Can the game server be reached? Without it there is only the opponent on this device. */
  serverUp: boolean;
  campaignSummary?: string;
  campaignHighlight?: boolean;
  arenaSummary?: string;
  onCampaign: () => void;
  onPlay: () => void;
  onArena: () => void;
  onCollection: () => void;
  onRewards: () => void;
  onOpenPack: () => void;
  onHowTo: () => void;
  onSettings: () => void;
  onResume: (gameId: string) => void;
}

/** Chrome's own install dialog, offered while the browser says the game can be installed. */
function useInstallPrompt(): (() => void) | null {
  const [event, setEvent] = useState<any>(null);
  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setEvent(e);
    };
    const onInstalled = () => setEvent(null);
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);
  if (!event) return null;
  return () => {
    event.prompt();
    void event.userChoice?.finally(() => setEvent(null));
  };
}

/** Deterministic pick so the wall does not reshuffle on every render. */
function pickWall(cards: CardDef[], count: number): CardDef[] {
  const pool = cards.filter((c) => c.type === 'MINION');
  if (!pool.length) return [];
  const out: CardDef[] = [];
  let seed = 7;
  for (let i = 0; i < count; i++) {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    out.push(pool[seed % pool.length]);
  }
  return out;
}

/** Lanternfall diamond crest — echoed from the card backs and favicon. */
const LanternCrest: React.FC = () => (
  <div className="menu-crest" aria-hidden="true">
    <span className="crest-rule" />
    <svg className="crest-mark" viewBox="0 0 64 64" fill="none">
      <path d="M32 6 50 32 32 58 14 32Z" stroke="currentColor" strokeWidth="1.75" opacity="0.7" />
      <path d="M32 15 43 32 32 49 21 32Z" fill="currentColor" fillOpacity="0.18" stroke="currentColor" strokeWidth="1.75" />
      <circle cx="32" cy="32" r="4" fill="#ffe5a3" />
      <path d="M32 1v4M32 59v4M6 32h4M54 32h4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" opacity="0.65" />
    </svg>
    <span className="crest-rule" />
  </div>
);

type MenuGlyph = 'campaign' | 'play' | 'arena' | 'resume' | 'collection' | 'guide' | 'settings';

const MenuEmblem: React.FC<{ kind: MenuGlyph }> = ({ kind }) => (
  <span className="menu-emblem" aria-hidden="true">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {kind === 'campaign' && (
        <>
          <path d="M4 19.5V5.5l5.5-2 5 2 5.5-2v14l-5.5 2-5-2-5.5 2Z" />
          <path d="M9.5 3.5v14M14.5 5.5v14" />
        </>
      )}
      {kind === 'play' && (
        <>
          <path d="M12 2.5 20.5 12 12 21.5 3.5 12Z" />
          <path d="M10 8.5 16 12l-6 3.5Z" fill="currentColor" stroke="none" />
        </>
      )}
      {kind === 'arena' && (
        <>
          <path d="M5 19 19 5M14.5 5H19v4.5M5 5l14 14M9.5 19H5v-4.5" />
        </>
      )}
      {kind === 'resume' && (
        <>
          <path d="M12 3 19.5 12 12 21 4.5 12Z" />
          <circle cx="12" cy="12" r="2.7" fill="currentColor" stroke="none" />
        </>
      )}
      {kind === 'collection' && (
        <>
          <rect x="4" y="5" width="11" height="15" rx="2" />
          <path d="M9 5V4a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-1" />
        </>
      )}
      {kind === 'guide' && (
        <>
          <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H12v17H6.5A2.5 2.5 0 0 0 4 21.5Z" />
          <path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H12v17h5.5A2.5 2.5 0 0 1 20 21.5Z" />
        </>
      )}
      {kind === 'settings' && (
        <>
          <circle cx="12" cy="12" r="3.2" />
          <path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.5 5.5l1.7 1.7M16.8 16.8l1.7 1.7M18.5 5.5l-1.7 1.7M7.2 16.8l-1.7 1.7" />
        </>
      )}
    </svg>
  </span>
);

export const Menu: React.FC<MenuProps> = ({
  cards,
  classCount,
  games,
  serverUp,
  campaignSummary,
  campaignHighlight,
  arenaSummary,
  onCampaign,
  onPlay,
  onArena,
  onCollection,
  onRewards,
  onOpenPack,
  onHowTo,
  onSettings,
  onResume,
}) => {
  const profile = useProfile();
  const wall = useMemo(() => pickWall(cards, 72), [cards]);
  const live = games.find((g) => g.phase !== 'GAME_OVER');
  const install = useInstallPrompt();

  return (
    <div className="screen menu">
      <div className="wall" aria-hidden="true">
        <div className="wall-grid">
          {wall.map((c, i) => (
            <div className="wall-tile" key={`${c.id}-${i}`}>
              <Art id={c.id} lazy />
            </div>
          ))}
        </div>
      </div>
      <div className="menu-body">
        <div className="menu-header">
          <LanternCrest />
          <p className="menu-kicker">{BRAND.tagline}</p>
          <h1 className="menu-title">{BRAND.title}</h1>
        </div>
        <div className="menu-standing">
          <button type="button" className="standing-chip" onClick={onRewards} title="Your rank, lanterns and things to wear">
            <RankBadge index={rankIndex(profile.rating)} />
            <RankLine rating={profile.rating} />
          </button>
          <button
            type="button"
            className={`pack-chip ${profile.packs > 0 ? 'is-ready' : ''}`}
            onClick={profile.packs > 0 ? onOpenPack : onRewards}
            title={profile.packs > 0 ? 'Light a lantern' : `${PACK_STEPS - profile.meter} more to win for a lantern`}
          >
            <PackIcon />
            {profile.packs > 0 ? (
              <span>
                <b>{profile.packs}</b> to light
              </span>
            ) : (
              <PackMeter meter={profile.meter} />
            )}
          </button>
        </div>
        <nav className="menu-nav" aria-label="Main menu">
          <button type="button" className={`menu-item primary ${campaignHighlight ? 'is-live' : ''}`} onClick={onCampaign}>
            <MenuEmblem kind="campaign" />
            <span className="menu-item-text">
              <strong>Campaign</strong>
              <span>{campaignSummary || 'Begin the 5-hall story · build your deck from starter to legend'}</span>
            </span>
            <span className="menu-item-pip" aria-hidden="true" />
          </button>
          <button type="button" className="menu-item" onClick={onPlay}>
            <MenuEmblem kind="play" />
            <span className="menu-item-text">
              <strong>Quick Play</strong>
              <span>
                {serverUp ? 'Play online or against a built-in opponent' : 'Against the built-in opponent, on this device'}
              </span>
            </span>
            <span className="menu-item-pip" aria-hidden="true" />
          </button>
          <button type="button" className={`menu-item ${arenaSummary ? 'is-live' : ''}`} onClick={onArena}>
            <MenuEmblem kind="arena" />
            <span className="menu-item-text">
              <strong>Arena</strong>
              <span>{arenaSummary || 'Draft a 30-card deck and battle to 12 wins'}</span>
            </span>
            <span className="menu-item-pip" aria-hidden="true" />
          </button>
          {live && (
            <button type="button" className="menu-item is-live" onClick={() => onResume(live.game_id)}>
              <MenuEmblem kind="resume" />
              <span className="menu-item-text">
                <strong>Resume match</strong>
                <span>
                  {live.p1.hero_class.toLowerCase()} vs {live.p2.hero_class.toLowerCase()}
                  {live.turn_number > 0 ? ` · turn ${live.turn_number}` : ''}
                </span>
              </span>
              <span className="menu-item-pip" aria-hidden="true" />
            </button>
          )}
          <button type="button" className="menu-item" onClick={onCollection}>
            <MenuEmblem kind="collection" />
            <span className="menu-item-text">
              <strong>Collection</strong>
              <span>Browse the cards and build decks</span>
            </span>
            <span className="menu-item-pip" aria-hidden="true" />
          </button>
          <div className="menu-row">
            <button type="button" className="menu-item small" onClick={onHowTo}>
              <MenuEmblem kind="guide" />
              <strong>How to play</strong>
            </button>
            <button type="button" className="menu-item small" onClick={onSettings}>
              <MenuEmblem kind="settings" />
              <strong>Settings</strong>
            </button>
          </div>
        </nav>
        <p className="menu-foot">
          {cards.length} cards · {classCount} classes
          {HAS_SERVER && !serverUp && ' · no connection to the game server'}
          <OfflineLine />
          {install && (
            <>
              {' · '}
              <button type="button" className="link" onClick={install}>
                Install as an app
              </button>
            </>
          )}
          <AppUpdateLine />
        </p>
      </div>
    </div>
  );
};
