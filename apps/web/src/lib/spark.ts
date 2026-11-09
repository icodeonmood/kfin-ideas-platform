/**
 * A One's own spark (docs/BRAND.md section 4, DEC-039): drawn from their permanent induction number, never from
 * anything personal, so it stays theirs if they change their jersey number. The same number always gives the
 * same spark and the same place in the constellation.
 */
const hash = (n: number, salt = 0) => Math.imul(n + salt, 2654435761) >>> 0;

export type Spark = { angle: number; length: number; ember: number; x: number; y: number };

export function sparkFor(inductionNo: number): Spark {
  const h = hash(inductionNo);
  const g = hash(inductionNo, 97);
  return {
    angle: 38 + (h % 34), // degrees above the horizon, 38 to 71
    length: 0.55 + ((h >>> 8) % 41) / 100, // share of the full length, 0.55 to 0.95
    ember: 0.04 + ((h >>> 16) % 8) / 100, // gap before the ember, as a share
    x: 0.04 + (g % 920) / 1000, // place in the sky, 0.04 to 0.96 across
    y: 0.06 + ((g >>> 12) % 700) / 1000, // and 0.06 to 0.76 down, leaving room for words below
  };
}
