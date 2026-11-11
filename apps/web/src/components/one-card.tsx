/**
 * One card for the wall, the home carousel, The Ember and the office screens (DEC-068), drawn as the back of the
 * One's jersey (DEC-099). The number runs from a pale core to the tier's heat with a glow behind it, so it reads at
 * every tier: a tier colour is light and fill, never text (DEC-098). The name only if they said yes, else
 * "One No. 17"; the impact brief once the committee approved it.
 *
 * The parent element carries the jersey itself: spread `jerseyProps(one)` on it (class, tier, tilt).
 */
import { measureList, oneName } from "@/lib/measures";
import type { PublicOne } from "@/server/ones";

export function oneTag(o: Pick<PublicOne, "founding" | "stage" | "way_in">) {
  if (o.founding) return o.stage ? `Founding One. ${o.stage}` : "Founding One";
  return o.stage ?? o.way_in;
}

export function jerseyProps(one: Pick<PublicOne, "tier">, className = "") {
  return {
    className: `jersey ${className}`.trim(),
    "data-tier": String(Math.min(7, Math.max(1, one.tier))),
    "data-tilt": "7",
  };
}

export function OneCardBody({ one }: { one: PublicOne }) {
  const measures = measureList(one.measures);
  const tag = oneTag(one);
  return (
    <>
      {tag ? <p className="jersey-flag">{tag}</p> : null}
      <h3 className="jersey-name">{oneName(one.number, one.name)}</h3>
      <p className="jersey-num">
        <span className="vh">Number {one.number}</span>
        <span aria-hidden="true">{one.number}</span>
      </p>
      <span className="jersey-bar" aria-hidden="true" />
      {one.line ? <p className="jersey-line">{one.line}</p> : null}
      {one.brief ? (
        <p className="jersey-brief">{one.brief}</p>
      ) : (
        <p className="jersey-muted">Their impact brief is on its way.</p>
      )}
      <p className="jersey-meta">
        <span>
          <span className="swatch" aria-hidden="true" />
          Tier {one.tier}, {one.tier_name}
        </span>
      </p>
      {measures.length ? (
        <ul className="jersey-measures" aria-label="Measured impact">
          {measures.map(([label, words]) => (
            <li key={label}>
              <span>{label}:</span> {words}
            </li>
          ))}
        </ul>
      ) : null}
    </>
  );
}
