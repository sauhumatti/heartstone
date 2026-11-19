// Which voice a piece has. The game only knows a piece's type tag; a piece
// without one (or with one that has no voice of its own) sounds like someone
// in armor: boots, gear and steel rather than a cry.
export type CreatureKind = 'beastSmall' | 'beastLarge' | 'dragon' | 'fiend' | 'construct' | 'idol' | 'folk';

interface Piece {
  race?: string | null;
  attack?: number | null;
  health?: number | null;
  max_health?: number | null;
}

const BY_TYPE: Record<string, CreatureKind> = {
  BEAST: 'beastLarge',
  DRAGON: 'dragon',
  DEMON: 'fiend',
  MECHANICAL: 'construct',
  TOTEM: 'idol',
};

/** A piece's size as the sound sees it: bigger pieces are louder and lower. */
export function creatureSize(piece: Piece | null | undefined): number {
  if (!piece) return 0;
  return Number(piece.attack ?? 0) + Number(piece.max_health ?? piece.health ?? 0);
}

export function creatureKind(piece: Piece | null | undefined): CreatureKind | undefined {
  if (!piece) return undefined;
  const kind = BY_TYPE[String(piece.race ?? '').toUpperCase()] ?? 'folk';
  if (kind === 'beastLarge' && creatureSize(piece) <= 6) return 'beastSmall';
  return kind;
}
