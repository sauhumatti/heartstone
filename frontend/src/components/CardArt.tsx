import React from 'react';

const CLASS_THEMES: Record<string, { bg1: string; bg2: string; accent: string }> = {
  MAGE: { bg1: '#15325c', bg2: '#091529', accent: '#56c2ff' },
  HUNTER: { bg1: '#1d4727', bg2: '#0b1e10', accent: '#7cd966' },
  WARRIOR: { bg1: '#5c1e18', bg2: '#240b09', accent: '#f06449' },
  PALADIN: { bg1: '#5e4616', bg2: '#241a07', accent: '#ffd35c' },
  PRIEST: { bg1: '#49505e', bg2: '#1b1f27', accent: '#e8eef7' },
  ROGUE: { bg1: '#2b2d38', bg2: '#0f1016', accent: '#a8b3cf' },
  SHAMAN: { bg1: '#1b2b61', bg2: '#0a1029', accent: '#5e96ff' },
  WARLOCK: { bg1: '#3e1e59', bg2: '#170924', accent: '#c96eff' },
  DRUID: { bg1: '#4d3119', bg2: '#1f1207', accent: '#e09145' },
  NEUTRAL: { bg1: '#3b322b', bg2: '#191410', accent: '#d1b075' },
};

function hashStr(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

interface CardArtProps {
  cardId: string;
  name: string;
  cardClass: string;
  type: string;
  race?: string | null;
  mechanics?: string[];
  rarity?: string;
}

export const CardArt: React.FC<CardArtProps> = ({
  cardId,
  name,
  cardClass,
  type,
  race,
  mechanics = [],
  rarity,
}) => {
  const theme = CLASS_THEMES[cardClass] || CLASS_THEMES.NEUTRAL;
  const h = hashStr(cardId + name);
  const cx = 36 + (h % 28);
  const cy = 28 + ((h >> 5) % 24);
  const rot = (h >> 10) % 360;
  const gradId = `cg-${cardId.replace(/[^a-zA-Z0-9_-]/g, '')}-${h % 997}`;

  const isSecret = mechanics.includes('SECRET');
  const lowerName = name.toLowerCase();

  let motif: React.ReactNode = null;
  if (type === 'WEAPON') {
    motif = (
      <g stroke={theme.accent} strokeWidth="2.5" fill="none" strokeLinecap="round">
        <path d="M26 62 L68 18" />
        <path d="M58 18 L68 18 L68 28" />
        <path d="M31 47 L43 59" strokeWidth="3.5" />
        <circle cx="24" cy="64" r="3" fill={theme.accent} />
      </g>
    );
  } else if (isSecret) {
    motif = (
      <g>
        <circle cx="50" cy="40" r="21" fill="none" stroke={theme.accent} strokeWidth="2" strokeDasharray="4 3" />
        <text x="50" y="49" textAnchor="middle" fill={theme.accent} fontSize="28" fontWeight="bold" fontFamily="Georgia, serif">
          ?
        </text>
      </g>
    );
  } else if (race === 'DRAGON') {
    motif = (
      <g fill={theme.accent} opacity="0.9">
        <path d="M20 52 C28 30, 42 22, 50 32 C58 22, 72 30, 80 52 C68 42, 58 44, 50 56 C42 44, 32 42, 20 52 Z" />
        <circle cx="50" cy="24" r="5" />
      </g>
    );
  } else if (race === 'BEAST') {
    motif = (
      <g stroke={theme.accent} strokeWidth="3" strokeLinecap="round" fill="none">
        <path d="M30 22 C36 36, 36 46, 32 58" />
        <path d="M44 18 C48 34, 48 48, 44 62" />
        <path d="M58 18 C60 34, 58 48, 55 60" />
        <path d="M70 24 C70 36, 68 46, 64 56" />
      </g>
    );
  } else if (race === 'DEMON') {
    motif = (
      <g fill="none" stroke={theme.accent} strokeWidth="2.8" strokeLinecap="round">
        <path d="M30 20 C24 34, 34 42, 42 40" />
        <path d="M70 20 C76 34, 66 42, 58 40" />
        <polygon points="50,32 60,56 40,56" fill={theme.accent} opacity="0.7" />
      </g>
    );
  } else if (race === 'MURLOC') {
    motif = (
      <g fill={theme.accent} opacity="0.9">
        <ellipse cx="50" cy="44" rx="18" ry="13" />
        <path d="M36 31 L42 20 L48 30 L54 18 L60 30 L65 22 L66 34 Z" />
        <circle cx="43" cy="41" r="3" fill="#0d1117" />
        <circle cx="57" cy="41" r="3" fill="#0d1117" />
      </g>
    );
  } else if (race === 'PIRATE') {
    motif = (
      <g stroke={theme.accent} strokeWidth="2.4" fill="none">
        <circle cx="50" cy="36" r="14" />
        <path d="M50 22 L50 56 M38 36 L62 36" />
        <path d="M36 52 Q50 64 64 52" />
      </g>
    );
  } else if (race === 'TOTEM') {
    motif = (
      <g fill={theme.accent} opacity="0.88">
        <rect x="40" y="18" width="20" height="44" rx="4" />
        <rect x="33" y="25" width="34" height="8" rx="2" />
        <circle cx="50" cy="42" r="4" fill={theme.bg2} />
      </g>
    );
  } else if (type === 'SPELL') {
    const isFire = lowerName.includes('fire') || lowerName.includes('pyro') || lowerName.includes('flame') || lowerName.includes('lava');
    const isFrost = lowerName.includes('frost') || lowerName.includes('ice') || lowerName.includes('blizzard') || lowerName.includes('cone');
    if (isFire) {
      motif = (
        <path
          d="M50 14 C62 28, 70 36, 64 52 C60 61, 40 61, 36 52 C30 38, 40 28, 50 14 Z"
          fill="#ff8a3d"
          stroke="#ffd27d"
          strokeWidth="2"
        />
      );
    } else if (isFrost) {
      motif = (
        <g stroke="#9ce7ff" strokeWidth="2.4" strokeLinecap="round">
          <line x1="50" y1="16" x2="50" y2="64" />
          <line x1="28" y1="28" x2="72" y2="52" />
          <line x1="72" y1="28" x2="28" y2="52" />
        </g>
      );
    } else {
      motif = (
        <g stroke={theme.accent} strokeWidth="2" fill="none">
          <polygon points="50,16 68,48 32,48" />
          <polygon points="50,58 68,26 32,26" opacity="0.7" />
          <circle cx="50" cy="38" r="6" fill={theme.accent} opacity="0.85" />
        </g>
      );
    }
  } else {
    // Stylized minion crest
    motif = (
      <g stroke={theme.accent} strokeWidth="2" fill="none">
        <path d="M50 16 L66 26 L62 52 L50 62 L38 52 L34 26 Z" fill={theme.accent} fillOpacity="0.16" />
        <circle cx="50" cy="37" r="9" fill={theme.accent} fillOpacity="0.65" />
        {mechanics.includes('TAUNT') && (
          <path d="M30 22 L50 14 L70 22 L68 48 L50 64 L32 48 Z" stroke="#ffd875" strokeWidth="2" />
        )}
      </g>
    );
  }

  return (
    <svg viewBox="0 0 100 76" className="card-art-svg" aria-hidden="true">
      <defs>
        <radialGradient id={gradId} cx="50%" cy="42%" r="65%">
          <stop offset="0%" stopColor={theme.bg1} />
          <stop offset="100%" stopColor={theme.bg2} />
        </radialGradient>
      </defs>
      <rect width="100" height="76" fill={`url(#${gradId})`} />
      <g transform={`rotate(${rot} 50 38)`} opacity="0.22">
        <circle cx={cx} cy={cy} r="28" fill="none" stroke={theme.accent} strokeWidth="1" />
        <line x1="0" y1={cy} x2="100" y2={cy} stroke={theme.accent} strokeWidth="0.7" />
      </g>
      {motif}
      {rarity === 'LEGENDARY' && (
        <path d="M36 12 L42 6 L50 11 L58 6 L64 12 Z" fill="#ffbe3b" opacity="0.9" />
      )}
    </svg>
  );
};
