import { Status } from "@/components/status";
import { day } from "@/lib/dates";
import type { MyPoints } from "@/server/points";

/** "a, b and c": the worker sends each item already worded to follow "points for". */
export function listWords(items: string[]): string {
  return items.length < 2
    ? (items[0] ?? "")
    : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

const pts = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

/** Your points (DEC-078): only you see them, and they never decide who becomes a One. */
export function PointsPanel({ points }: { points: MyPoints | null }) {
  return (
    <section className="glass points-panel" aria-labelledby="mi-points">
      <h2 id="mi-points" className="t-h2">
        Your points
      </h2>
      <p className="muted">Only you see your points. They never decide who becomes a One.</p>
      {points === null ? (
        <Status kind="error" role={null} title={<>We can&apos;t load your points just now.</>} />
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
            <p className="soon-pill">
              <strong>Coming soon:</strong> points for {listWords(points.coming_soon)}.
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
