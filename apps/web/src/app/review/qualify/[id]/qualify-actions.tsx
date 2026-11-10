"use client";

/** The desk's qualify actions (§4.5): confirm each gate, save the impact estimate, record Finance's check, finish. */
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

export type QualifyView = {
  id: number;
  cluster_id: string;
  state: string;
  stage: string | null;
  due_at: string | null;
  final: Record<string, unknown> | null;
  cluster: {
    id: string;
    name: string | null;
    summary: { problem?: string } | null;
    lobs: string[];
    scope: string | null;
    contributors: number;
  };
  gates: {
    gate: string;
    label: string;
    proposed: string | null;
    evidence: Record<string, unknown>;
    result: string | null;
    detail: string | null;
    note: string | null;
    confirmed_by: string | null;
  }[];
  impact: {
    fields: Record<string, number | string | string[]>;
    units: Record<string, string>;
    basis: Record<string, string>;
    annual_net_benefit: number | null;
    payback_months: number | null;
    finance_required: boolean;
    finance_validated_by: string | null;
    saved_by: string | null;
  };
};

const ERRORS: Record<string, string> = {
  own_idea:
    "You cannot qualify a group that holds an idea you shared or joined. Another reviewer will take it.",
  note_required: "Please add a note: a stop, or conditions, need one.",
  compliance_outcome_required: "Please choose what the compliance check found.",
  gates_not_confirmed: "Please confirm all four gates first.",
  impact_not_saved: "Please save the impact estimate first.",
  finance_check_pending: "Finance needs to check these numbers first (₹25 lakh or more).",
  bad_evidence_type: "Please choose how the numbers are backed.",
  personal_data: "Please take out personal details first.",
  already_decided: "This group has already been qualified.",
  cluster_moved_on: "This group has moved on since you opened it.",
};

const LABELS: Record<string, string> = {
  capex_inr: "One-time spend (₹)",
  opex_inr_per_year: "Running cost (₹ a year)",
  one_time_revenue_inr: "One-time revenue (₹)",
  one_time_saving_inr: "One-time saving (₹)",
  recurring_revenue_inr_per_year: "Recurring revenue (₹ a year)",
  recurring_saving_inr_per_year: "Recurring cost saving (₹ a year)",
  hours_saved_per_month: "Hours saved (a month)",
  clients_who_would_pay: "Clients who would pay",
  weeks_to_first_benefit: "Weeks to first benefit",
  effort_person_weeks: "Effort (person-weeks)",
  dependencies: "Dependencies (count)",
};

const inr = (n: number | null) => (n === null ? "—" : `₹${Math.round(n).toLocaleString("en-IN")}`);

export function QualifyActions({ id, view, mayAct }: { id: string; view: QualifyView; mayAct: boolean }) {
  const router = useRouter();
  const statusRef = useRef<HTMLParagraphElement>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; error: boolean } | null>(null);
  const [fields, setFields] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.keys(view.impact.units).map((k) => [k, String(view.impact.fields[k] ?? "")])),
  );
  const [evidenceType, setEvidenceType] = useState(String(view.impact.fields.evidence_type ?? "estimate"));
  const [gate, setGate] = useState(view.gates.find((g) => !g.result)?.gate ?? "evidence");
  const [result, setResult] = useState("pass");
  const [detail, setDetail] = useState("clear");
  const [note, setNote] = useState("");
  const open = ["open", "in_progress"].includes(view.state);

  async function send(body: Record<string, unknown>, done: string) {
    setBusy(true);
    setMessage(null);
    const res = await fetch(`/api/review/qualify/${id}`, {
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
            text:
              out?.banner ??
              ERRORS[String(out?.error)] ??
              "That did not go through. Please check the form and try again.",
            error: true,
          },
    );
    statusRef.current?.focus();
    if (res?.ok) router.refresh();
  }

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

  if (!open || !mayAct)
    return (
      <section aria-labelledby="q-actions" className="panel">
        <h2 id="q-actions">Actions</h2>
        {status}
        <p>
          {!open
            ? `This group has been qualified: ${String(view.final?.stage ?? "").replace(/_/g, " ")}.`
            : "Only the review desk qualifies groups."}
        </p>
      </section>
    );

  const isConflict = gate === "no_conflict";
  return (
    <section aria-labelledby="q-actions" className="panel">
      <h2 id="q-actions">Actions</h2>
      {status}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send(
            { action: "confirm_gate", gate, result, detail: isConflict ? detail : undefined, note },
            "Gate confirmed.",
          );
        }}
      >
        <h3>Confirm a gate</h3>
        <div className="field">
          <label htmlFor="q-gate">Gate</label>
          <select id="q-gate" value={gate} onChange={(e) => setGate(e.target.value)}>
            {view.gates.map((g) => (
              <option key={g.gate} value={g.gate}>
                {g.label}
              </option>
            ))}
          </select>
        </div>
        {isConflict ? (
          <div className="field">
            <label htmlFor="q-detail">What the compliance check found</label>
            <select id="q-detail" value={detail} onChange={(e) => setDetail(e.target.value)}>
              <option value="clear">Clear</option>
              <option value="clear_with_conditions">Clear, with conditions</option>
              <option value="conflict">A conflict</option>
            </select>
          </div>
        ) : (
          <fieldset>
            <legend>Your call</legend>
            <label>
              <input
                type="radio"
                name="q-result"
                value="pass"
                checked={result === "pass"}
                onChange={() => setResult("pass")}
              />{" "}
              Passes
            </label>
            <label>
              <input
                type="radio"
                name="q-result"
                value="fail"
                checked={result === "fail"}
                onChange={() => setResult("fail")}
              />{" "}
              Stops here
            </label>
          </fieldset>
        )}
        <div className="field">
          <label htmlFor="q-note">Note (needed for a stop or for conditions)</label>
          <textarea
            id="q-note"
            rows={2}
            maxLength={1000}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
        <button type="submit" className="button" disabled={busy}>
          Confirm this gate
        </button>
      </form>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          const out: Record<string, number | string> = { evidence_type: evidenceType };
          for (const [k, v] of Object.entries(fields)) if (v.trim() !== "") out[k] = Number(v);
          void send({ action: "save_impact", fields: out }, "Impact estimate saved.");
        }}
      >
        <h3>Impact estimate</h3>
        <p className="muted">
          Started from the contributors&apos; own figures (the largest given for each). Annual net benefit:{" "}
          {inr(view.impact.annual_net_benefit)}; payback: {view.impact.payback_months ?? "—"} months.
          {view.impact.finance_required
            ? view.impact.finance_validated_by
              ? ` Finance checked these numbers (${view.impact.finance_validated_by}).`
              : " At ₹25 lakh or more, Finance checks these numbers."
            : ""}
        </p>
        {Object.keys(view.impact.units).map((k) => (
          <div className="field" key={k}>
            <label htmlFor={`q-${k}`}>{LABELS[k] ?? k}</label>
            <input
              id={`q-${k}`}
              inputMode="decimal"
              value={fields[k] ?? ""}
              onChange={(e) => setFields({ ...fields, [k]: e.target.value })}
            />
          </div>
        ))}
        <div className="field">
          <label htmlFor="q-evidence">How the numbers are backed</label>
          <select id="q-evidence" value={evidenceType} onChange={(e) => setEvidenceType(e.target.value)}>
            <option value="data_backed">Data</option>
            <option value="estimate">An estimate</option>
            <option value="anecdote">An anecdote</option>
          </select>
        </div>
        <button type="submit" className="button button-secondary" disabled={busy}>
          Save the estimate
        </button>
        {view.impact.finance_required && !view.impact.finance_validated_by ? (
          <button
            type="button"
            className="button button-secondary"
            disabled={busy}
            onClick={() => void send({ action: "finance_validated" }, "Finance's check recorded.")}
          >
            Finance has checked these numbers
          </button>
        ) : null}
      </form>

      <h3>Finish</h3>
      <p className="muted">
        All four gates passed: the group goes to its committee for scoring. A gate that stops it: the
        contributors are told why, in plain words.
      </p>
      <button
        type="button"
        className="button"
        disabled={busy}
        onClick={() => void send({ action: "complete" }, "Done.")}
      >
        Finish qualifying
      </button>
    </section>
  );
}
