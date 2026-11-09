/**
 * A One's own spark, in their tier colour (DEC-039, DEC-075). Decorative: it always sits next to their number and
 * tier in words. Optionally with the two zeros, so it reads as their own 1% Club mark.
 */
import { sparkFor } from "@/lib/spark";

export function OneSpark({
  inductionNo,
  colour,
  size = 72,
  zeros = false,
  className,
}: {
  inductionNo: number;
  colour: string;
  size?: number;
  zeros?: boolean;
  className?: string;
}) {
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
    .map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`)
    .join(" ");
  const gap = 8 + s.ember * 60;
  const ember = [head[0] + dir[0] * gap, head[1] + dir[1] * gap];
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 100 100"
      aria-hidden="true"
      focusable="false"
    >
      {zeros ? (
        <>
          <circle cx="24" cy="26" r="13" fill="none" stroke="currentColor" strokeWidth="5" />
          <circle cx="76" cy="76" r="13" fill="none" stroke="currentColor" strokeWidth="5" />
        </>
      ) : null}
      <polygon points={points} fill={colour} />
      <circle cx={ember[0]!.toFixed(1)} cy={ember[1]!.toFixed(1)} r="3.5" fill={colour} />
    </svg>
  );
}
