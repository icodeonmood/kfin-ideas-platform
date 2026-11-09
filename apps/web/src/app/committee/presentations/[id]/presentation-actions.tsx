"use client";

/** The session and the decision (§4.7): the chair marks it presented, members seal their assessments, the chair
 * collates, asks the assistant to draft the reasons, edits them and records the decision. */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

type Theme = { theme: string; count: number; members: string[] };

export type CommitteePresentation = {
  id: string;
  cluster_id: string;
  state: string;
  slot_at: string | null;
  cluster: { name: string | null; summary: { problem?: string } | null };
  qna_notes: string | null;
  assessed: number;
  members: number;
  my_assessment: Record<string, unknown> | null;
  dimensions: { name: string; label: string; anchors: Record<string, string> }[];
  sheet: {
    tallies: Record<string, number>;
    medians: Record<string, number>;
    route_prefs: Record<string, number>;
    themes: { strengths: Theme[]; concerns: Theme[] } | null;
    conditions: { text: string; members: string[] }[] | null;
    divergence_flags: string[];
    sponsors_willing: number;
    final_score: number | null;
  } | null;
  decision: { id: string; outcome: string } | null;
  chair: boolean;
  sponsor_options: { id: string; name: string; willing: boolean }[];
};

const ERRORS: Record<string, string> = {
  already_assessed: "Your assessment is already sealed.",
  every_dimension_1_to_5: "Please score every dimension.",
  vote_required: "Please choose your vote.",
  conditions_required: "Please add the conditions for your accept.",
  not_ready_to_collate: "Not everyone has assessed, and the deadline with quorum hasn't come yet.",
  collate_first: "Please collate the assessments first.",
  no_majority: "Accepting needs a majority of the members who assessed (a tie needs your casting vote).",
  route_required: "Please choose the route.",
  sponsor_required: "Please name a sponsor.",
  reason_code_required: "Please choose a reason.",
  reason_too_short: "Please write a little more.",
  reason_required: "Please write the reason.",
  assistant_unavailable: "The assistant is unavailable. Please write the reasons yourself.",
  own_idea: "You can't take part in deciding a group that holds an idea you shared or joined.",
  chair_only: "Only the chair can do this.",
};

const VOTES: [string, string][] = [
  ["accept", "Accept"],
  ["accept_with_conditions", "Accept with conditions"],
  ["park", "Park"],
  ["decline", "Decline"],
];
const ROUTES: [string, string][] = [
  ["build", "Build"],
  ["reuse", "Reuse"],
  ["buy", "Buy"],
  ["partner", "Partner"],
];

export function PresentationActions({ id, view }: { id: string; view: CommitteePresentation }) {
  const router = useRouter();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [notes, setNotes] = useState("");
  const [scores, setScores] = useState<Record<string, number>>(() =>
    Object.fromEntries(view.dimensions.map((d) => [d.name, 3])),
  );
  const [vote, setVote] = useState("accept");
  const [route, setRoute] = useState("build");
  const [strengths, setStrengths] = useState("");
  const [concerns, setConcerns] = useState("");
  const [conditions, setConditions] = useState("");
  const [sponsorWilling, setSponsorWilling] = useState(false);
  const [outcome, setOutcome] = useState("picked");
  const [code, setCode] = useState("");
  const [reason, setReason] = useState("");
  const [change, setChange] = useState("");
  const [sponsor, setSponsor] = useState("");
  const [casting, setCasting] = useState(false);
  const lines = (t: string) =>
    t
      .split("\n")
      .map((x) => x.trim())
      .filter(Boolean);

  async function send(body: Record<string, unknown>, done: string): Promise<Record<string, unknown> | null> {
    setBusy(true);
    setMessage(null);
    const res = await fetch(`/api/committee/presentations/${id}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as Record<string, unknown> | null;
    setBusy(false);
    setMessage(
      res?.ok
        ? { text: done, error: false }
        : { text: ERRORS[String(out?.error)] ?? "That did not go through. Please try again.", error: true },
    );
    statusRef.current?.focus();
    if (res?.ok && body.action !== "draft_reasons") router.refresh();
    return res?.ok ? out : null;
  }

  return (
    <section aria-labelledby="p-actions" className="panel">
      <h2 id="p-actions">Your part</h2>
      <p
        ref={statusRef}
        tabIndex={-1}
        role="status"
        aria-live="polite"
        className={message?.error ? "field-error" : "muted"}
      >
        {message?.text ?? ""}
      </p>
      {view.state === "held" ? (
        <p>
          {view.assessed} of {view.members} members have sealed their assessment.
        </p>
      ) : null}

      {view.chair && view.state === "scheduled" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send(
              { action: "held", qna_notes: notes },
              "Marked as presented. Assessments are open for 2 working days.",
            );
          }}
        >
          <h3>After the session</h3>
          <div className="field">
            <label htmlFor="p-notes">Questions and answers</label>
            <textarea
              id="p-notes"
              rows={4}
              maxLength={1000}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
          <button type="submit" className="button" disabled={busy}>
            They presented
          </button>
          <button
            type="button"
            className="button button-secondary"
            disabled={busy}
            onClick={() => void send({ action: "not_presented" }, "Parked as not presented.")}
          >
            They did not present
          </button>
        </form>
      ) : null}

      {view.state === "held" && !view.my_assessment ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send(
              { action: "assess", scores, vote, route_pref: route, strengths: lines(strengths), concerns: lines(concerns),
                conditions: lines(conditions), will_sponsor: sponsorWilling }, // prettier-ignore
              "Your assessment is sealed.",
            );
          }}
        >
          <h3>Your sealed assessment</h3>
          {view.dimensions.map((d) => (
            <fieldset key={d.name}>
              <legend>{d.label}</legend>
              {[1, 2, 3, 4, 5].map((v) => (
                <label key={v}>
                  <input
                    type="radio"
                    name={`a-${d.name}`}
                    checked={scores[d.name] === v}
                    onChange={() => setScores({ ...scores, [d.name]: v })}
                  />{" "}
                  {v}
                </label>
              ))}
            </fieldset>
          ))}
          <div className="field">
            <label htmlFor="a-vote">Your vote</label>
            <select id="a-vote" value={vote} onChange={(e) => setVote(e.target.value)}>
              {VOTES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="a-route">Preferred route</label>
            <select id="a-route" value={route} onChange={(e) => setRoute(e.target.value)}>
              {ROUTES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="a-strengths">Strengths (up to 3, one per line)</label>
            <textarea
              id="a-strengths"
              rows={3}
              value={strengths}
              onChange={(e) => setStrengths(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="a-concerns">Concerns (up to 3, one per line)</label>
            <textarea
              id="a-concerns"
              rows={3}
              value={concerns}
              onChange={(e) => setConcerns(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="a-conditions">Conditions (one per line)</label>
            <textarea
              id="a-conditions"
              rows={2}
              value={conditions}
              onChange={(e) => setConditions(e.target.value)}
            />
          </div>
          <label>
            <input
              type="checkbox"
              checked={sponsorWilling}
              onChange={(e) => setSponsorWilling(e.target.checked)}
            />{" "}
            I am willing to sponsor this
          </label>
          <button type="submit" className="button" disabled={busy}>
            Seal my assessment
          </button>
        </form>
      ) : null}

      {view.chair && view.state === "held" && !view.sheet ? (
        <button
          type="button"
          className="button"
          disabled={busy}
          onClick={() => void send({ action: "collate" }, "Collated.")}
        >
          Collate the assessments
        </button>
      ) : null}

      {view.chair && view.state === "held" && view.sheet ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send(
              { action: "decide", outcome, route, reason_code: code || undefined, plain_reason: reason, what_would_change: change,
                sponsor_id: sponsor || undefined, casting_vote: casting, conditions: view.sheet?.conditions?.map((c) => c.text) }, // prettier-ignore
              "Decided. The colleagues are told.",
            );
          }}
        >
          <h3>Decide</h3>
          <div className="field">
            <label htmlFor="d-outcome">Outcome</label>
            <select id="d-outcome" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
              <option value="picked">Accept (Picked)</option>
              <option value="parked">Park</option>
              <option value="declined">Decline</option>
            </select>
          </div>
          {outcome === "picked" ? (
            <>
              <div className="field">
                <label htmlFor="d-route">Route</label>
                <select id="d-route" value={route} onChange={(e) => setRoute(e.target.value)}>
                  {ROUTES.map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="d-sponsor">Sponsor</label>
                <select id="d-sponsor" value={sponsor} onChange={(e) => setSponsor(e.target.value)}>
                  <option value="">Choose a sponsor</option>
                  {view.sponsor_options.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name}
                      {o.willing ? " (willing to sponsor)" : ""}
                    </option>
                  ))}
                </select>
              </div>
              <label>
                <input type="checkbox" checked={casting} onChange={(e) => setCasting(e.target.checked)} /> Use
                my casting vote on a tie
              </label>
            </>
          ) : (
            <div className="field">
              <label htmlFor="d-code">Reason</label>
              <select id="d-code" value={code} onChange={(e) => setCode(e.target.value)}>
                <option value="">Choose a reason</option>
                {(outcome === "parked"
                  ? ["NOT_FEASIBLE_NOW", "INSUFFICIENT_EVIDENCE", "CAPACITY"]
                  : ["LOW_VALUE", "NOT_FEASIBLE_NOW", "REG_CONFLICT", "OUT_OF_SCOPE"]
                ).map((c) => (
                  <option key={c} value={c}>
                    {c.replace(/_/g, " ").toLowerCase()}
                  </option>
                ))}
              </select>
            </div>
          )}
          <button
            type="button"
            className="button button-secondary"
            disabled={busy}
            onClick={async () => {
              const out = await send(
                { action: "draft_reasons", outcome, reason_code: code || undefined },
                "Draft ready below. Edit it before you decide.",
              );
              const draft = out?.draft as { reason?: string; what_would_change?: string } | undefined;
              if (draft) {
                setReason(draft.reason ?? "");
                setChange(draft.what_would_change ?? "");
              }
            }}
          >
            Ask the assistant to draft the reasons
          </button>
          <div className="field">
            <label htmlFor="d-reason">Reason, in plain words</label>
            <textarea
              id="d-reason"
              rows={4}
              maxLength={1000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </div>
          {outcome !== "picked" ? (
            <div className="field">
              <label htmlFor="d-change">What would change this decision</label>
              <textarea
                id="d-change"
                rows={3}
                maxLength={1000}
                value={change}
                onChange={(e) => setChange(e.target.value)}
              />
            </div>
          ) : null}
          <button type="submit" className="button" disabled={busy}>
            Record the decision
          </button>
        </form>
      ) : null}

      {view.decision ? (
        <p>
          Decision {view.decision.id}: {view.decision.outcome}.
        </p>
      ) : null}
    </section>
  );
}
