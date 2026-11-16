import React from 'react';
import type { GameSummary } from '../types';

interface MainMenuViewProps {
  cardsCount: number;
  games: GameSummary[];
  sfxEnabled: boolean;
  musicEnabled: boolean;
  onToggleSfx: () => void;
  onToggleMusic: () => void;
  onGoPlay: () => void;
  onGoCollection: () => void;
  onOpenHowTo: () => void;
  onOpenSettings: () => void;
  onResumeGame: (gid: string) => void;
}

export const MainMenuView: React.FC<MainMenuViewProps> = ({
  cardsCount,
  games,
  sfxEnabled,
  musicEnabled,
  onToggleSfx,
  onToggleMusic,
  onGoPlay,
  onGoCollection,
  onOpenHowTo,
  onOpenSettings,
  onResumeGame,
}) => {
  const activeGames = games.filter((g) => g.phase !== 'GAME_OVER');

  return (
    <div
      className="tavern-menu-screen"
      style={{
        backgroundImage: `radial-gradient(circle at 50% 42%, rgba(20,12,7,0.35) 0%, rgba(12,7,4,0.88) 88%), url('/art/tavern_bg.webp')`,
      }}
    >
      <div className="tavern-box-frame">
        <div className="crest-halo">
          <img src="/art/tavern_crest.webp" alt="Hearthstone Classic Crest" className="tavern-crest-img" />
        </div>

        <h1 className="tavern-title">HEARTHSTONE</h1>
        <div className="tavern-subtitle">ORIGINAL CLASSIC EDITION · 2014 SET ({cardsCount} CARDS)</div>

        <div className="tavern-menu-buttons">
          <button className="tavern-btn tavern-btn-hero" onClick={onGoPlay}>
            <span className="tb-icon">⚔</span>
            <span className="tb-text">
              <strong>Play Duel</strong>
              <small>Challenge Antigravity (CLI / API) or Practice Bot</small>
            </span>
          </button>

          <button className="tavern-btn" onClick={onGoCollection}>
            <span className="tb-icon">📖</span>
            <span className="tb-text">
              <strong>My Collection &amp; Decks</strong>
              <small>Browse all 382 Basic + Classic cards &amp; build 30-card decks</small>
            </span>
          </button>

          {activeGames.length > 0 && (
            <button
              className="tavern-btn tavern-btn-resume"
              onClick={() => onResumeGame(activeGames[0].game_id)}
            >
              <span className="tb-icon">🔥</span>
              <span className="tb-text">
                <strong>Resume Match #{activeGames[0].game_id}</strong>
                <small>
                  {activeGames[0].p1.hero_class} vs {activeGames[0].p2.hero_class} · Turn {activeGames[0].turn_number}
                </small>
              </span>
            </button>
          )}

          <div className="tavern-btn-row">
            <button className="tavern-btn tavern-btn-half" onClick={onOpenHowTo}>
              <span>📜 How to Play</span>
            </button>
            <button className="tavern-btn tavern-btn-half" onClick={onOpenSettings}>
              <span>⚙ Game Options</span>
            </button>
          </div>
        </div>

        <div className="tavern-footer-strip">
          <span>🕯 Local Offline Tavern · Zero Online Play</span>
          <div style={{ display: 'flex', gap: '0.35rem' }}>
            <button type="button" className="btn-xs" onClick={onToggleMusic}>
              {musicEnabled ? '🎶 Music' : '🔇 Music'}
            </button>
            <button type="button" className="btn-xs" onClick={onToggleSfx}>
              {sfxEnabled ? '🔊 SFX' : '🔇 SFX'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
