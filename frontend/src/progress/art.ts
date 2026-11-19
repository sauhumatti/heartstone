// The pictures of the rewards (scripts/generate_cosmetics.py makes them). They are
// part of the build, so they are there offline and inside an installed app.
import { RANKS } from './rules';

const files = import.meta.glob('./art/*.webp', { eager: true, query: '?url', import: 'default' }) as Record<string, string>;

/** The picture of a thing to wear, a rank or the pack lantern, by its name; none for what is drawn in code. */
export function artOf(name: string): string | undefined {
  return files[`./art/${name}.webp`];
}

export function rankArt(index: number): string | undefined {
  const rank = RANKS[Math.max(0, Math.min(RANKS.length - 1, index))];
  return artOf(`rank_${rank.id}`);
}
