/**
 * The office screen's pure parts (S-OFFICE, L-DISPLAY.office), shared by the server, the screen and the tests.
 * The screen keeps its own earlier look (S-OFFICE/4): sizes here are the board's pixels at 1920×1080.
 */
import { measureText, type MeasureSet } from "./measures";
import { sparkFor } from "./spark";

/** One One on the office screen: the contract's `OneCard` plus the headline figure (A-API `GET /display/office`). */
export type OfficeOne = {
  number: number;
  induction_no: number;
  name: string | null;
  first_name: string | null;
  tier: number;
  tier_name: string;
  tier_colour: string;
  flag: "founding" | "one";
  brief: string | null;
  figure: string | null;
};

export type OfficeData = { paused: boolean; ones: OfficeOne[] };

/** What the worker gives for each One (`/internal/display/office`). */
export type PublicOneInput = {
  number: number | null;
  induction_no: number;
  name: string | null;
  first_name?: string | null;
  founding: boolean;
  tier: number;
  tier_name: string;
  tier_colour: string;
  brief: string | null;
  measures: MeasureSet | null;
};

/** Seconds per One: the board's `secondsPerOne`, 4 to 20, default 8 (L-DISPLAY.office/2). */
export const SECONDS_PER_ONE = { min: 4, max: 20, fallback: 8 } as const;

export type StarStyle = "sparks" | "dots";

const first = (raw: string | string[] | undefined) => (Array.isArray(raw) ? raw[0] : raw);

/** `?seconds=` on the screen's address, clamped to what the board allows. */
export function secondsPerOne(raw: string | string[] | undefined): number {
  const n = Number.parseInt(first(raw) ?? "", 10);
  if (!Number.isFinite(n)) return SECONDS_PER_ONE.fallback;
  return Math.min(SECONDS_PER_ONE.max, Math.max(SECONDS_PER_ONE.min, n));
}

/** `?stars=dots` picks "Glowing dots"; anything else is the default, each One's own spark (S-OFFICE/3). */
export const starStyle = (raw: string | string[] | undefined): StarStyle =>
  first(raw) === "dots" ? "dots" : "sparks";

const ORDER = ["time", "money", "effort", "scale"] as const;

/** The first measured figure, as a sentence: "620 hours a month given back." Money only once Finance confirmed it,
 * which the worker already enforces for everything public. */
export function headlineFigure(measures: MeasureSet | null | undefined): string | null {
  for (const key of ORDER) {
    const m = measures?.[key];
    if (m && Number.isFinite(m.value)) return `${measureText(key, m)}.`;
  }
  return null;
}

export function toOfficeOne(p: PublicOneInput): OfficeOne | null {
  if (p.number === null) return null; // a One without a number yet stays off the wall display
  const name = p.name?.trim() || null;
  return {
    number: p.number,
    induction_no: p.induction_no,
    name,
    first_name: name ? p.first_name?.trim() || (name.split(/\s+/)[0] ?? null) : null,
    tier: p.tier,
    tier_name: p.tier_name,
    tier_colour: p.tier_colour,
    flag: p.founding ? "founding" : "one",
    brief: p.brief?.trim() || null,
    figure: headlineFigure(p.measures),
  };
}

/** The rotation order: the order the Ones were inducted, so the Founding Ones come first. */
export function officeOrder(ones: PublicOneInput[]): OfficeOne[] {
  return ones
    .map(toOfficeOne)
    .filter((o): o is OfficeOne => o !== null)
    .sort((a, b) => a.induction_no - b.induction_no);
}

export const flagWords = (flag: OfficeOne["flag"]) => (flag === "founding" ? "Founding One" : "One");

export const tierLine = (o: Pick<OfficeOne, "tier" | "tier_name">) => `Tier ${o.tier} · ${o.tier_name}`;

export const lightLabel = (o: Pick<OfficeOne, "number" | "first_name">) =>
  o.first_name ? `No. ${o.number} · ${o.first_name}` : `No. ${o.number}`;

export const countLine = (n: number) =>
  `${n} ${n === 1 ? "One" : "Ones"} so far. Each one shipped something that changed how we work.`;

export const position = (index: number, total: number) => `${index + 1} of ${total}`;

/** The digits of a number, most significant first, for the rolling counter. */
export const digitsOf = (n: number) =>
  String(Math.max(0, Math.trunc(n)))
    .split("")
    .map(Number);

/**
 * Where a One's light sits, in per cent of the screen. Their place comes from their permanent induction number
 * (DEC-039, `sparkFor`), drawn into the right-hand field the board keeps clear of the words: 44 to 92 across,
 * 18 to 68 down.
 */
export function placeInSky(inductionNo: number): { x: number; y: number } {
  const p = sparkFor(inductionNo);
  const x = 44 + ((p.x - 0.04) / 0.92) * 48;
  const y = 18 + ((p.y - 0.06) / 0.7) * 50;
  return { x: Math.round(x * 100) / 100, y: Math.round(y * 100) / 100 };
}

/** A One's own spark in a 100×100 box, the same geometry as `OneSpark`. */
export function sparkShape(inductionNo: number): { points: string; ember: [number, number] } {
  const s = sparkFor(inductionNo);
  const a = (s.angle * Math.PI) / 180;
  const dir = [Math.cos(a), -Math.sin(a)] as const;
  const perp = [Math.sin(a), Math.cos(a)] as const;
  const tail = [10, 92] as const;
  const len = 78 * s.length;
  const head = [tail[0] + dir[0] * len, tail[1] + dir[1] * len] as const;
  const w = 6;
  const points = [
    tail,
    [head[0] + perp[0] * w, head[1] + perp[1] * w],
    [head[0] - perp[0] * w, head[1] - perp[1] * w],
  ]
    .map(([x, y]) => `${x!.toFixed(1)},${y!.toFixed(1)}`)
    .join(" ");
  const gap = 8 + s.ember * 60;
  return { points, ember: [head[0] + dir[0] * gap, head[1] + dir[1] * gap] };
}

export type Dust = { x: number; y: number; size: number; alpha: number; delay: number };

/** The background stars, the same 90 on every screen (the board's seeded field). */
export function dustField(count = 90): Dust[] {
  let seed = 7;
  const rnd = () => {
    seed = (seed * 9301 + 49297) % 233280;
    return seed / 233280;
  };
  const out: Dust[] = [];
  for (let k = 0; k < count; k++) {
    out.push({
      x: Number((rnd() * 100).toFixed(2)),
      y: Number((rnd() * 100).toFixed(2)),
      size: Number((1 + rnd() * 2).toFixed(1)),
      alpha: Number((0.18 + rnd() * 0.4).toFixed(2)),
      delay: Number((rnd() * 5).toFixed(2)),
    });
  }
  return out;
}

/** Sizes of a One's light, in board pixels (S-OFFICE board). */
export function lightSize(style: StarStyle, tier: number, current: boolean) {
  const box = style === "dots" ? (current ? 22 : 10) + tier * 2 : current ? 96 : 64;
  return {
    box,
    halo: style === "dots" ? 72 : box + 36,
    dotGlow: (current ? 40 : 14) + tier * 6,
    sparkGlow: current ? 14 : 5,
    opacity: current ? 1 : 0.8,
  };
}
