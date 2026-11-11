/**
 * One issue of The Ember (DEC-062, DEC-070, BLD-128), in the order it reads: impact first, because impact is what
 * makes the next person share an idea. Everything here is what everyone may already see; empty sections say so.
 */
import { jerseyProps, OneCardBody } from "@/components/one-card";
import { measureList } from "@/lib/measures";
import type { EmberIssue, EmberOne } from "@/server/ember";
import type { PublicOne } from "@/server/ones";

const asCard = (o: EmberOne): PublicOne => ({
  ...o,
  induction_no: o.number,
  way_in: o.founding ? "Founding One" : "One",
  stage: null,
});

function Ones({ ones, id, title, empty }: { ones: EmberOne[]; id: string; title: string; empty: string }) {
  return (
    <section className="ones-band" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {ones.length ? (
        <ul className="one-cards">
          {ones.map((o) => (
            <li key={o.number} {...jerseyProps(asCard(o))}>
              <OneCardBody one={asCard(o)} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="lead-dark">{empty}</p>
      )}
    </section>
  );
}

export function IssueView({ issue }: { issue: EmberIssue }) {
  const picked = issue.picked_in_month ? "Picked this month" : "Picked so far";
  const shipped = [
    ...issue.shipped.map((s) => ({ label: s.label, words: s.words })),
    ...issue.results.map((r) => ({
      label: r.label,
      words: `Measured at ${r.mark}: ${measureList(r.measures)
        .map(([k, v]) => `${k} ${v}`)
        .join(", ")}`,
    })),
  ];
  return (
    <>
      <Ones
        ones={issue.impact}
        id="e-impact"
        title="Impact created by Ones"
        empty="Results arrive 30 and 90 days after something ships."
      />
      <Ones ones={issue.new_ones} id="e-new" title="New Ones" empty="No new Ones this month." />

      <section aria-labelledby="e-shipped">
        <h2 id="e-shipped">Shipped, with results</h2>
        {shipped.length ? (
          <ul className="plain-list">
            {shipped.map((s, i) => (
              <li key={`${s.label}-${i}`}>
                <strong>{s.label}</strong>
                <br />
                <span className="muted">{s.words}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Nothing shipped this month.</p>
        )}
      </section>

      <section aria-labelledby="e-lob">
        <h2 id="e-lob">Ideas in and picked</h2>
        {issue.by_lob.length ? (
          <div className="table-wrap">
            <table className="table">
              <caption className="visually-hidden">
                Ideas shared this month and {picked.toLowerCase()}, by line of business
              </caption>
              <thead>
                <tr>
                  <th scope="col">Line of business</th>
                  <th scope="col">Shared this month</th>
                  <th scope="col">{picked}</th>
                </tr>
              </thead>
              <tbody>
                {issue.by_lob.map((r) => (
                  <tr key={r.lob}>
                    <th scope="row">{r.lob}</th>
                    <td>Shared: {r.shared}</td>
                    <td>Picked: {r.picked}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="muted">No ideas shared this month.</p>
        )}
        {issue.coming_soon.length ? (
          <p className="notice">Coming soon: {issue.coming_soon.join("; ")}.</p>
        ) : null}
      </section>

      <section aria-labelledby="e-note">
        <h2 id="e-note">What the committee looks for</h2>
        {issue.note ? (
          <figure className="ember-note">
            <blockquote>
              <p>{issue.note}</p>
            </blockquote>
            <figcaption className="muted">Chair, 1% Club core committee</figcaption>
          </figure>
        ) : (
          <p className="muted">The chair&apos;s note is still to come.</p>
        )}
      </section>

      {issue.managers.length ? (
        <section aria-labelledby="e-managers">
          <h2 id="e-managers">Thank you, managers</h2>
          <p>Their teams shared the most this month: {issue.managers.join(", ")}.</p>
        </section>
      ) : null}
    </>
  );
}
