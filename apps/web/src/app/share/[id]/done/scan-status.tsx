"use client";

/**
 * The scan as the submitter watches it (§4.2, AT-B4-09/10): the current step in words, then what happens next.
 * Plain words only: never "rejected", "duplicate" or "already solved".
 */
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Crew, type Ready } from "./crew";
import { FollowUp } from "./follow-up";

type Span = { field: string; quote: string; label: string };
type Status = {
  state: "queued" | "running" | "waiting" | "done" | "manual";
  step: "queued" | "gatekeeper" | "canvas_assist" | "matching" | "done";
  outcome: "ready" | "blocked" | "redirect" | "held" | "redirected" | null;
  idea_id: string;
  blocked?: { spans: Span[]; investor_context: boolean; can_contest: boolean };
  redirect?: {
    team: string;
    url: string | null;
    message: string;
    override_label: string;
    override_reason_min_chars: number;
  };
  ready?: Ready;
  stage: string;
  final?: string;
  question?: { text: string; due: string };
  can_disagree?: boolean;
};

const FINAL: Record<string, { title: string; text: string }> = {
  scanned: {
    title: "Your idea is with the review desk",
    text: "You will hear from us within 5 working days.",
  },
  merged: { title: "You have teamed up", text: "We have added you to the idea. You will hear at each step." },
  adoption_requested: {
    title: "We have asked the team that runs it",
    text: "They will get in touch about taking it to your area.",
  },
  withdrawn: {
    title: "Your idea is withdrawn",
    text: "Thanks for sharing it. You can share a new idea any time.",
  },
};
const MOVED_ON = { title: "Your idea has moved on", text: "Track where it is in My ideas." };
FINAL.needs_info = { title: "The review desk has a question", text: "Your answer helps them decide sooner." };
FINAL.reviewed = { title: "Your idea has been reviewed", text: "Check Messages for what happens next." };
FINAL.in_cluster = {
  title: "Your idea is grouped with similar ones",
  text: "Check Messages for what happens next.",
};

const STEPS = [
  { key: "gatekeeper", text: "Checking for personal details" },
  { key: "canvas_assist", text: "Drafting a summary and suggestions" },
  { key: "matching", text: "Looking for colleagues on the same thing" },
] as const;

const FIELD_LABELS: Record<string, string> = {
  one_line: "Say it in one line",
  details: "Tell us more",
  kind: "What kind of idea is it",
  "who.segments": "Who feels it",
  "who.frequency_or_reach": "How often, or how many",
  "who.today_alternative": "What people do today",
  "value.category": "Cost or revenue",
  "value.play": "How it creates value",
  "value.estimate": "A rough figure: hours or rupees",
  "value.estimate.hours_saved_per_month": "Hours saved a month",
  "value.estimate.inr_saved_per_year": "Rupees saved a year",
  "value.estimate.inr_revenue_one_time": "One-time revenue in rupees",
  "value.estimate.inr_revenue_per_year": "Revenue a year in rupees",
  "value.estimate.clients_who_would_pay": "Clients who would pay",
  "value.estimate.note": "How you worked out the numbers",
  "value.basis": "What your guess is based on",
  "ecosystem.solved_elsewhere": "Solved anywhere else",
  "ecosystem.our_advantage": "Why KFintech",
  "solution.approach": "Your fix",
  "solution.needs": "What it needs",
  "solution.risks": "Risks",
  visibility_reason: "Why committees only",
};
const label = (path: string) =>
  FIELD_LABELS[path] ?? (path.startsWith("ecosystem.references") ? "Your research" : "Your answers");

export function ScanStatus({ id, initial }: { id: string; initial: Status | null }) {
  const router = useRouter();
  const [status, setStatus] = useState<Status | null>(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reason, setReason] = useState("");
  const [overriding, setOverriding] = useState(false);
  const outcomeRef = useRef<HTMLHeadingElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const [unreachable, setUnreachable] = useState(false);
  const failures = useRef(0);
  const inFlight = useRef(false);
  const running = !status || status.state === "queued" || status.state === "running";
  const waiting = status?.state === "waiting";

  // Live progress over server-sent events while `scan.live` is on (§8, week 3). Any error (switch off, a proxy
  // that buffers, an old browser) closes it for this page and the polling below takes over. A stream the server
  // ends while the scan is still moving (it closes every 5 minutes) is opened again.
  const [sseOff, setSseOff] = useState(false);
  const [sseRound, setSseRound] = useState(0);
  const streamOff = sseOff || typeof EventSource === "undefined"; // only used in effects (client side)
  useEffect(() => {
    if ((!running && !waiting) || streamOff) return;
    const source = new EventSource(`/api/submissions/${id}/scan-events`);
    source.addEventListener("status", (e) => {
      failures.current = 0;
      setUnreachable(false);
      setStatus(JSON.parse((e as MessageEvent<string>).data) as Status);
    });
    source.addEventListener("end", () => {
      source.close();
      setSseRound((n) => n + 1);
    });
    source.onerror = () => {
      source.close();
      setSseOff(true);
    };
    return () => source.close();
  }, [id, running, waiting, streamOff, sseRound]);

  useEffect(() => {
    if ((!running && !waiting) || !streamOff) return;
    const timer = setInterval(
      async () => {
        if (inFlight.current) return; // one request at a time
        inFlight.current = true;
        const res = await fetch(`/api/submissions/${id}/scan-status`, { cache: "no-store" }).catch(
          () => null,
        );
        inFlight.current = false;
        if (res?.ok) {
          failures.current = 0;
          setUnreachable(false);
          setStatus((await res.json()) as Status);
        } else if (++failures.current >= 5) {
          setUnreachable(true);
        }
      },
      running ? 1500 : 30_000,
    );
    return () => clearInterval(timer);
  }, [id, running, waiting, streamOff]);

  const outcomeKey = status?.state === "done" ? `${status.outcome}:${status.final ?? ""}` : status?.state;
  useEffect(() => {
    if (outcomeKey && outcomeKey !== "queued" && outcomeKey !== "running") outcomeRef.current?.focus();
  }, [outcomeKey]);

  async function refresh() {
    const res = await fetch(`/api/submissions/${id}/scan-status`, { cache: "no-store" }).catch(() => null);
    if (res?.ok) setStatus((await res.json()) as Status);
  }

  async function choose(choice: string, extra: Record<string, string> = {}) {
    setBusy(true);
    setError("");
    const res = await fetch(`/api/submissions/${id}/scan-choice`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ choice, ...extra }),
    }).catch(() => null);
    const body = (await res?.json().catch(() => null)) as { next?: string | null; error?: string } | null;
    setBusy(false);
    if (!res?.ok) {
      setError(
        body?.error === "reason_too_short"
          ? `Please tell us a little more (at least ${status?.redirect?.override_reason_min_chars ?? 15} characters).`
          : body?.error === "personal_data"
            ? "Please take out personal details from your reason."
            : "We couldn't save that just now. Please try again.",
      );
      return;
    }
    if (body?.next) {
      router.push(body.next);
      return;
    }
    setOverriding(false);
    const next = await fetch(`/api/submissions/${id}/scan-status`, { cache: "no-store" }).catch(() => null);
    if (next?.ok) setStatus((await next.json()) as Status);
    titleRef.current?.focus(); // the button that had focus is gone; land somewhere that says where we are
  }

  const currentIndex = STEPS.findIndex((s) => s.key === status?.step);
  return (
    <section aria-labelledby="scan-title" className="glass scan">
      <h2 id="scan-title" ref={titleRef} tabIndex={-1}>
        Where your idea is now
      </h2>
      {/* Always in the page, so screen readers announce each change of text. */}
      <p role="status" aria-live="polite" className="muted">
        {unreachable
          ? "We can't reach the checks right now. Your idea is saved; this page keeps trying."
          : running
            ? currentIndex >= 0
              ? `${STEPS[currentIndex]!.text}…`
              : "Starting the checks…"
            : ""}
      </p>
      {running ? (
        <>
          <ol className="scan-steps">
            {STEPS.map((s, i) => {
              const done = currentIndex > i || status?.step === "done";
              const now = currentIndex === i;
              return (
                <li
                  key={s.key}
                  className={done ? "done" : now ? "now" : "todo"}
                  aria-current={now ? "step" : undefined}
                >
                  <span aria-hidden="true">{done ? "✓ " : now ? "… " : "○ "}</span>
                  {s.text}
                  <span className="visually-hidden">
                    {done ? " (done)" : now ? " (in progress)" : " (next)"}
                  </span>
                </li>
              );
            })}
          </ol>
        </>
      ) : null}

      {status?.state === "waiting" || status?.state === "manual" ? (
        <div className="scan-notice">
          <h3 ref={outcomeRef} tabIndex={-1}>
            Your idea is saved
          </h3>
          <p>We&apos;ll email you within the hour to confirm the summary and any matches.</p>
        </div>
      ) : null}

      {status?.state === "done" && status.outcome === "ready" && status.final ? (
        <div className="scan-notice">
          <h3 ref={outcomeRef} tabIndex={-1}>
            {(FINAL[status.final] ?? MOVED_ON).title}
          </h3>
          <p>{(FINAL[status.final] ?? MOVED_ON).text}</p>
          <FollowUp id={id} question={status.question ?? null} onChanged={refresh} />
        </div>
      ) : null}

      {status?.state === "done" && status.outcome === "ready" && status.ready ? (
        <Crew id={id} ready={status.ready} labelFor={label} headingRef={outcomeRef} onChanged={refresh} />
      ) : null}

      {status?.state === "done" && status.outcome === "blocked" && status.blocked ? (
        <div className="scan-notice scan-notice-error">
          <h3 ref={outcomeRef} tabIndex={-1}>
            Please take out some details first
          </h3>
          <p>
            Investor and customer details must not be on this platform. Your idea can go ahead once these are
            removed.
          </p>
          <ul>
            {status.blocked.spans.map((s, i) => (
              <li key={i}>
                <strong>{label(s.field)}:</strong> “{s.quote}” looks like {s.label}.
              </li>
            ))}
          </ul>
          <div className="btn-row">
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => void choose("edit")}
            >
              Edit my idea
            </button>
          </div>
          <p className="muted">Please edit these details out.</p>
        </div>
      ) : null}

      {status?.state === "done" && status.outcome === "redirect" && status.redirect ? (
        <div className="scan-notice">
          <h3 ref={outcomeRef} tabIndex={-1}>
            Where to take this: {status.redirect.team}
          </h3>
          <p>{status.redirect.message}</p>
          {status.redirect.url ? (
            <p>
              <a href={status.redirect.url} target="_blank" rel="noopener noreferrer">
                Go to {status.redirect.team} (opens in a new tab)
              </a>
            </p>
          ) : null}
          <div className="btn-row">
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => void choose("take_redirect")}
            >
              I&apos;ll take it there
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              aria-expanded={overriding}
              aria-controls="override-form"
              onClick={() => setOverriding((v) => !v)}
            >
              {status.redirect.override_label}
            </button>
          </div>
          {overriding ? (
            <form
              id="override-form"
              onSubmit={(e) => {
                e.preventDefault();
                void choose("is_an_idea", { reason });
              }}
            >
              <div className="field">
                <label htmlFor="override-reason">Tell us why it is an idea</label>
                <p id="override-reason-hint" className="hint">
                  At least {status.redirect.override_reason_min_chars} characters. No personal details,
                  please.
                </p>
                <textarea
                  id="override-reason"
                  rows={3}
                  value={reason}
                  aria-describedby="override-reason-hint"
                  onChange={(e) => setReason(e.target.value)}
                />
              </div>
              <button type="submit" className="btn btn-primary" disabled={busy}>
                Carry on with my idea
              </button>
            </form>
          ) : null}
        </div>
      ) : null}

      {status?.state === "done" && status.outcome === "held" ? (
        <div className="scan-notice">
          <h3 ref={outcomeRef} tabIndex={-1}>
            Thanks. The review desk will look at this first
          </h3>
          <p>You will hear from us within 5 working days.</p>
        </div>
      ) : null}

      {status?.state === "done" && status.outcome === "redirected" ? (
        <div className="scan-notice">
          <h3 ref={outcomeRef} tabIndex={-1}>
            Thanks for taking it to the right team
          </h3>
          <p>If you spot a pattern worth changing, share it as an idea any time.</p>
        </div>
      ) : null}

      {error ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
