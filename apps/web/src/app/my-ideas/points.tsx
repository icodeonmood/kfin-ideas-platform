import { day } from "@/lib/dates";
import type { MyPoints } from "@/server/points";

const pts = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

/** Your points (DEC-078): only you see them, and they never decide who becomes a One. */
export function PointsPanel({ points }: { points: MyPoints | null }) {
  return (
    <section className="points-panel" aria-labelledby="mi-points">
      <h2 id="mi-points">Your points</h2>
      <p className="muted">Only you see your points. They never decide who becomes a One.</p>
      {points === null ? (
        <p className="notice">We can&apos;t load your points just now.</p>
      ) : (
        <>
          <p className="points-total">
            <span className="points-number">{pts(points.total)}</span> points so far,{" "}
            {pts(points.last_12_months)} in the last 12 months.
          </p>
          {points.recent.length ? (
            <ul className="plain-list">
              {points.recent.map((r, i) => (
                <li key={`${r.on}-${i}`}>
                  {r.what}: <strong>+{pts(r.points)}</strong> <span className="muted">{day(r.on)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p>Share your first idea and your points start here.</p>
          )}
          {points.coming_soon.length ? (
            <p className="muted">Coming soon: points for {points.coming_soon.join(", ").toLowerCase()}.</p>
          ) : null}
        </>
      )}
    </section>
  );
}
