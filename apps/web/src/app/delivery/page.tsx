import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { day } from "@/lib/dates";
import { can } from "@/lib/rbac";
import { currentUser } from "@/server/auth/current";
import { deliveryConsole } from "@/server/delivery";

import { StartHandover } from "./start-handover";

export const metadata: Metadata = { title: "Delivery" };
export const dynamic = "force-dynamic";

const MARK_WORDS = { day_30: "30-day results", day_90: "90-day results" } as const;

/**
 * Delivery (§4.8 to §4.11): from a picked idea to a measured result. Committee members and admins see every
 * delivery and the picked ideas waiting for a handover; owners, sponsors and delivery PMs see their own.
 */
export default async function Page() {
  const me = await currentUser();
  if (!me) redirect("/sign-in");
  if (!can(me.roles, "work_delivery")) redirect("/");
  const data = await deliveryConsole(me).catch(() => null);
  return (
    <>
      <h1>Delivery</h1>
      <p className="lead">
        Picked ideas, from the handover pack to results at 30 and 90 days. Each step needs a person: the owner
        fills it in, the sponsor approves.
      </p>
      <p className="coming-soon coming-soon-light">Live sync with the delivery pipeline: coming soon</p>
      {!data ? (
        <p className="notice">We can&apos;t load deliveries just now. Please try again in a minute.</p>
      ) : (
        <>
          {data.can_start ? (
            <section aria-labelledby="d-waiting">
              <h2 id="d-waiting">Picked, waiting for a handover</h2>
              {data.waiting.length ? (
                <ul className="crew-cards" style={{ listStyle: "none", padding: 0 }}>
                  {data.waiting.map((w) => (
                    <li key={w.subject_id} className="card">
                      <p className="meta">{w.subject_id}</p>
                      <p>{w.label}</p>
                      <StartHandover subjectType={w.subject_type} subjectId={w.subject_id} />
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">Nothing picked is waiting.</p>
              )}
            </section>
          ) : null}

          <section aria-labelledby="d-list">
            <h2 id="d-list">{data.can_start ? "Every delivery" : "Your deliveries"}</h2>
            {data.deliveries.length ? (
              <div className="table-wrap">
                <table className="table">
                  <caption className="visually-hidden">Deliveries, most recently changed first</caption>
                  <thead>
                    <tr>
                      <th scope="col">Idea or group</th>
                      <th scope="col">Where it is</th>
                      <th scope="col">People</th>
                      <th scope="col">Next results</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.deliveries.map((d) => (
                      <tr key={d.id}>
                        <td>
                          <Link href={`/delivery/${d.id}`}>{d.label}</Link>
                          <br />
                          <span className="muted">
                            {d.subject_id}, {d.track_words.toLowerCase()} track
                          </span>
                        </td>
                        <td>
                          {d.state_words}
                          {d.phase_words && d.state === "in_delivery" ? `: ${d.phase_words}` : ""}
                          {d.blocked ? " (blocked)" : ""}
                          {d.outcome
                            ? `, ${d.outcome === "target_met" ? "target met" : "target not met"}`
                            : ""}
                        </td>
                        <td>
                          Owner: {d.owner ?? "not named yet"}
                          <br />
                          Sponsor: {d.sponsor ?? "not named yet"}
                        </td>
                        <td>
                          {d.next_measurement
                            ? `${MARK_WORDS[d.next_measurement.mark]}, due ${day(d.next_measurement.due_at)}${
                                d.next_measurement.filled ? ", waiting for the sponsor" : ""
                              }`
                            : "No results due"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="muted">
                {data.can_start
                  ? "No deliveries yet. Start one from a picked idea above."
                  : "You aren't named on any delivery yet. When you are, it shows here."}
              </p>
            )}
          </section>
        </>
      )}
    </>
  );
}
