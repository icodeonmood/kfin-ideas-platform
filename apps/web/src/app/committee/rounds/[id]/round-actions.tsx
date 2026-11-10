"use client";

/** Blind scoring (§4.6): score once, declare a conflict, revise once after reveal; the chair reveals and decides. */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

type Dimension = { name: string; label: string; weight: number; anchors: Record<string, string> };

export type RoundView = {
  id: string;
  body: string;
  lob_id: string | null;
  state: string;
  closes_at: string;
  cluster: {
    id: string;
    name: string | null;
    summary: { problem?: string; solution?: { text: string; credit: string[] }[] } | null;
    ideas: { contributor: string; one_line: string | null }[];
  };
  impact: { annual_net_benefit: number | null; payback_months: number | null };
  suggested_band: number | null;
  evidence_type: string | null;
  confidence_multiplier: number;
  dimensions: Dimension[];
  my_scores: Record<string, { value: number; first: number; revised: boolean; comment: string | null }>;
  my_flag: { reason: string; status: string } | null;
  /** Set when the member has a conflict on the group: the rest of the view is then left out. */
  conflict: string | null;
  progress: { scored: number; voting: number; quorum_met: boolean };
  chair: boolean;
  outcome: string | null;
  revealed?: {
    medians: Record<string, number> | null;
    ranges: Record<string, number> | null;
    flags: Record<string, string[]> | null;
    final_score: number | null;
    ai: Record<string, { value: number; rationale: string }>;
    thresholds: { shortlist: number; nomination: number };
  };
};

const ERRORS: Record<string, string> = {
  not_eligible:
    "You can't score this one: you've stepped aside, or a conflict flag waits for an admin to clear it.",
  already_scored: "You've already scored this group. You can revise once after the reveal.",
  every_dimension_required: "Please score every dimension.",
  financial_within_one_level: "Financial value can move at most one level from the suggested band.",
  reason_required: "Please give a reason for moving financial value from the suggested band.",
  reason_too_short: "Please give a little more detail.",
  not_ready_to_reveal: "Not everyone has scored, and the deadline with quorum hasn't come yet.",
  already_revised: "You've already revised once.",
  reason_code_required: "Please choose a reason.",
  own_idea: "You can't decide on a group that holds an idea you shared or joined.",
  conflict_of_interest: "You have a conflict on this group, so you can't take part in its review.",
  bad_scores: "Change at least one score first.",
  below_nomination_threshold: "The score is below the nomination threshold.",
  chair_only: "Only the chair can do this.",
};

const OUTCOMES_CORE: [string, string][] = [
  ["shortlisted", "Shortlist: invite them to present"],
  ["parked", "Park"],
  ["declined", "Decline"],
];
const OUTCOMES_LOB: [string, string][] = [
  ["nominated", "Nominate to the core committee"],
  ["parked", "Park"],
  ["declined", "Decline"],
];
const CODES: Record<string, [string, string][]> = {
  parked: [
    ["NOT_FEASIBLE_NOW", "Can't be done well today"],
    ["INSUFFICIENT_EVIDENCE", "Needs more evidence"],
    ["CAPACITY", "Worth doing, no capacity now"],
  ],
  declined: [
    ["LOW_VALUE", "Not enough value now"],
    ["NOT_FEASIBLE_NOW", "Can't be done well today"],
    ["REG_CONFLICT", "Conflicts with a regulation or contract"],
    ["OUT_OF_SCOPE", "Outside this programme"],
  ],
};

export function RoundActions({ id, view }: { id: string; view: RoundView }) {
  const router = useRouter();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  // Nothing is pre-selected: every score is a choice the member makes (the suggested band is shown, not set).
  const [scores, setScores] = useState<Record<string, number | undefined>>(() =>
    Object.fromEntries((view.dimensions ?? []).map((d) => [d.name, view.my_scores?.[d.name]?.value])),
  );
  const [finReason, setFinReason] = useState("");
  const [outcome, setOutcome] = useState(view.body === "core" ? "shortlisted" : "nominated");
  const [code, setCode] = useState("");
  const [note, setNote] = useState("");
  const [below, setBelow] = useState("");
  const scored = Object.keys(view.my_scores ?? {}).length > 0;
  const revised = Object.values(view.my_scores ?? {}).some((s) => s.revised);

  async function send(body: Record<string, unknown>, done: string) {
    setBusy(true);
    setMessage(null);
    const res = await fetch(`/api/committee/rounds/${id}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as { error?: string; banner?: string } | null;
    setBusy(false);
    setMessage(
      res?.ok
        ? { text: done, error: false }
        : {
            text: out?.banner ?? ERRORS[String(out?.error)] ?? "That did not go through. Please try again.",
            error: true,
          },
    );
    statusRef.current?.focus();
    if (res?.ok) router.refresh();
  }

  const scoreFields = (view.dimensions ?? []).map((d) => (
    <fieldset key={d.name}>
      <legend>
        {d.label} (weight {d.weight})
      </legend>
      <p className="muted">
        1: {d.anchors["1"] ?? "very low"} · 3: {d.anchors["3"] ?? "middling"} · 5:{" "}
        {d.anchors["5"] ?? "very high"}
        {d.name === "financial_value" && view.suggested_band ? ` · suggested: ${view.suggested_band}` : ""}
      </p>
      {[1, 2, 3, 4, 5].map((v) => (
        <label key={v}>
          <input
            type="radio"
            name={`s-${d.name}`}
            value={v}
            checked={scores[d.name] === v}
            onChange={() => setScores({ ...scores, [d.name]: v })}
          />{" "}
          {v}
        </label>
      ))}
    </fieldset>
  ));

  const status = (
    <p
      ref={statusRef}
      tabIndex={-1}
      role="status"
      aria-live="polite"
      className={message?.error ? "field-error" : "muted"}
    >
      {message?.text ?? ""}
    </p>
  );
  const finMoved =
    view.suggested_band !== null &&
    scores.financial_value !== undefined &&
    scores.financial_value !== view.suggested_band;
  const say = (text: string) => {
    setMessage({ text, error: true });
    statusRef.current?.focus();
  };

  if (view.conflict) {
    return (
      <section aria-labelledby="r-actions" className="panel">
        <h2 id="r-actions">Your part</h2>
        {status}
        {view.state === "open" && (view.conflict === "flagged" || view.conflict === "manager") ? (
          <button
            type="button"
            className="button button-secondary"
            disabled={busy}
            onClick={() => void send({ action: "declare_conflict" }, "You have stepped aside.")}
          >
            I have a conflict: step aside
          </button>
        ) : (
          <p>There is nothing for you to do here.</p>
        )}
      </section>
    );
  }

  return (
    <section aria-labelledby="r-actions" className="panel">
      <h2 id="r-actions">Your part</h2>
      {status}
      <p>
        {view.progress.scored} of {view.progress.voting} members have scored
        {view.progress.quorum_met ? " (quorum met)" : ""}.
      </p>
      {view.my_flag?.status === "flagged" ? (
        <p className="notice">
          You are linked to an idea in this group. Step aside below, or ask an admin to clear the flag with a
          reason.
        </p>
      ) : null}
      {view.my_flag?.status === "recused" ? <p>You have stepped aside from this review.</p> : null}

      {view.state === "open" && !scored && view.my_flag?.status !== "recused" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (view.dimensions.some((d) => scores[d.name] === undefined)) {
              say(ERRORS.every_dimension_required!);
              return;
            }
            void send(
              { action: "score", scores, financial_reason: finMoved ? finReason : undefined },
              "Your scores are sealed.",
            );
          }}
        >
          <h3>Score this group</h3>
          {scoreFields}
          {finMoved ? (
            <div className="field">
              <label htmlFor="r-fin">Why financial value differs from the suggested band</label>
              <textarea
                id="r-fin"
                rows={2}
                maxLength={1000}
                value={finReason}
                onChange={(e) => setFinReason(e.target.value)}
              />
            </div>
          ) : null}
          <button type="submit" className="button" disabled={busy}>
            Seal my scores
          </button>
        </form>
      ) : null}

      {view.state === "open" && view.my_flag?.status !== "recused" ? (
        <button
          type="button"
          className="button button-secondary"
          disabled={busy}
          onClick={() => void send({ action: "declare_conflict" }, "You have stepped aside.")}
        >
          I have a conflict: step aside
        </button>
      ) : null}

      {view.state === "open" && (view.chair || view.body === "lob") ? (
        <button
          type="button"
          className="button button-secondary"
          disabled={busy}
          onClick={() => void send({ action: "reveal" }, "Scores revealed.")}
        >
          Reveal the scores
        </button>
      ) : null}

      {view.state === "revealed" && scored && !revised ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            const changed = Object.fromEntries(
              Object.entries(scores).filter(([k, v]) => v !== undefined && v !== view.my_scores[k]?.value),
            );
            if (Object.keys(changed).length === 0) {
              say(ERRORS.bad_scores!);
              return;
            }
            void send({ action: "revise", scores: changed }, "Revised. Both values are kept.");
          }}
        >
          <h3>Revise once after the reveal</h3>
          {scoreFields}
          <button type="submit" className="button button-secondary" disabled={busy}>
            Save my revision
          </button>
        </form>
      ) : null}

      {view.state === "revealed" && (view.chair || view.body === "lob") ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void send(
              {
                action: "decide",
                outcome,
                reason_code: code || undefined,
                note,
                below_threshold_reason: below || undefined,
              },
              "Decided. The colleagues are told.",
            );
          }}
        >
          <h3>Decide</h3>
          <div className="field">
            <label htmlFor="r-outcome">Outcome</label>
            <select
              id="r-outcome"
              value={outcome}
              onChange={(e) => {
                setOutcome(e.target.value);
                setCode(""); // the reasons differ by outcome
              }}
            >
              {(view.body === "core" ? OUTCOMES_CORE : OUTCOMES_LOB).map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
          </div>
          {CODES[outcome] ? (
            <>
              <div className="field">
                <label htmlFor="r-code">Reason</label>
                <select id="r-code" value={code} onChange={(e) => setCode(e.target.value)}>
                  <option value="">Choose a reason</option>
                  {CODES[outcome].map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="r-note">Note for the colleagues (at least 20 characters)</label>
                <textarea
                  id="r-note"
                  rows={3}
                  maxLength={1000}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>
            </>
          ) : null}
          {outcome === "shortlisted" &&
          (view.revealed?.final_score ?? 0) < (view.revealed?.thresholds.shortlist ?? 0) ? (
            <div className="field">
              <label htmlFor="r-below">Why shortlist below the threshold (at least 30 characters)</label>
              <textarea
                id="r-below"
                rows={2}
                maxLength={1000}
                value={below}
                onChange={(e) => setBelow(e.target.value)}
              />
            </div>
          ) : null}
          <button type="submit" className="button" disabled={busy}>
            Record the decision
          </button>
        </form>
      ) : null}
    </section>
  );
}
