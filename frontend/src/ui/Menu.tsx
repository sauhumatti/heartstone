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
  onPlay: () => void;
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

export const Menu: React.FC<MenuProps> = ({ cards, classCount, games, serverUp, onPlay, onCollection, onRewards, onOpenPack, onHowTo, onSettings, onResume }) => {
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
        <p className="menu-kicker">{BRAND.tagline}</p>
        <h1 className="menu-title">{BRAND.title}</h1>
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
        <nav className="menu-nav">
          <button type="button" className="menu-item primary" onClick={onPlay}>
            <strong>Play</strong>
            <span>
              {serverUp ? 'Against the built-in opponent, Gemini 4 Hydrogen, the practice bot or the command line' : 'Against the built-in opponent, on this device'}
            </span>
          </button>
          {live && (
            <button type="button" className="menu-item" onClick={() => onResume(live.game_id)}>
              <strong>Resume match</strong>
              <span>
                {live.p1.hero_class.toLowerCase()} vs {live.p2.hero_class.toLowerCase()}
                {live.turn_number > 0 ? ` · turn ${live.turn_number}` : ''}
              </span>
            </button>
          )}
          <button type="button" className="menu-item" onClick={onCollection}>
            <strong>Collection</strong>
            <span>Browse the cards and build decks</span>
          </button>
          <div className="menu-row">
            <button type="button" className="menu-item small" onClick={onHowTo}>
              <strong>How to play</strong>
            </button>
            <button type="button" className="menu-item small" onClick={onSettings}>
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
