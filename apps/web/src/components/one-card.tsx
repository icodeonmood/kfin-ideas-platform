/**
 * One card for the wall, the home carousel and the office screens (DEC-068). The number in the One's tier colour
 * on Graphite; the name only if they said yes, else "One No. 17"; the impact brief once the committee approved it.
 */
import { measureList, oneName } from "@/lib/measures";
import type { PublicOne } from "@/server/ones";

export function oneTag(o: Pick<PublicOne, "founding" | "stage" | "way_in">) {
  if (o.founding) return o.stage ? `Founding One. ${o.stage}` : "Founding One";
  return o.stage ?? o.way_in;
}

export function OneCardBody({ one }: { one: PublicOne }) {
  const measures = measureList(one.measures);
  return (
    <>
      <div className="one-card-top">
        <p className="one-number" style={{ color: one.tier_colour }}>
          <span className="visually-hidden">Number </span>
          {one.number}
        </p>
        <p className="one-tag">{oneTag(one)}</p>
      </div>
      <h3 className="one-name">{oneName(one.number, one.name)}</h3>
      {one.line ? <p className="one-line">{one.line}</p> : null}
      {one.brief ? (
        <p className="one-brief">{one.brief}</p>
      ) : (
        <p className="one-muted">Their impact brief is on its way.</p>
      )}
      <p className="one-tier">
        <span className="tier-dot" style={{ background: one.tier_colour }} aria-hidden="true" />
        Tier {one.tier}, {one.tier_name}
      </p>
      {measures.length ? (
        <ul className="measure-chips" aria-label="Measured impact">
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
