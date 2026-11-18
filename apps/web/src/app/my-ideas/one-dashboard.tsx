"use client";

/**
 * A One's own dashboard on My ideas (DEC-067, DEC-073, DEC-075, DEC-078): their number and tier in the tier's
 * colour on Zed, the 30-day window to choose a number, their impact brief (the committee approves it), measured
 * impact; private points are on My ideas for everyone (BLD-130). After a tier change the glow-up plays once (DEC-084).
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";

import { OneSpark } from "@/components/one-spark";
import { day } from "@/lib/dates";
import { measureList } from "@/lib/measures";
import type { MyOne } from "@/server/ones";

import { GlowUp } from "./glow-up";

const ERRORS: Record<string, string> = {
  number_taken: "That number is taken, or resting after someone retired it. Please try another.",
  number_out_of_range: "Numbers run from 1 to 999.",
  swap_window_closed: "The 30 days to choose a number have passed. Your number is yours now.",
  legend_number: "Your number has been retired in your honour, so it stays yours.",
  text_too_long: "Please keep your brief to 30 words or fewer.",
  text_too_short: "Please write at least a short sentence.",
  personal_data: "Please take out any personal details (numbers, addresses, investor names) and try again.",
  text_needs_review: "Please reword this: it reads as off-topic or unkind, so we can't save it as it is.",
  names_not_allowed: "Leave out the names of colleagues and clients: everyone will see this.",
  checks_unavailable: "We can't check text just now. Please try again in a few minutes.",
};

async function send(url: string, body: Record<string, unknown>) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => null);
  if (res?.ok) return null;
  const code = res ? String(((await res.json().catch(() => ({}))) as { error?: string }).error ?? "") : "";
  return ERRORS[code] ?? "That didn't work. Please try again.";
}

export function OneDashboard({ one }: { one: MyOne }) {
  const router = useRouter();
  const [number, setNumber] = useState(String(one.number ?? ""));
  const [brief, setBrief] = useState("");
  const [status, setStatus] = useState("");
  const [numberError, setNumberError] = useState("");
  const [briefError, setBriefError] = useState("");
  const numberId = useId();
  const briefId = useId();
  const words = brief.trim() ? brief.trim().split(/\s+/).length : 0;
  const measures = measureList(one.measures);

  if (!one.active) {
    return (
      <section
        className="one-dashboard band stage"
        data-theme="zed"
        data-tier={String(Math.min(7, Math.max(1, one.tier)))}
        aria-labelledby="od-title"
      >
        <h2 id="od-title" className="t-display">
          You were a One
        </h2>
        <p className="lead-dark">
          Your spark stays in the sky at Tier {one.tier}, {one.tier_name}. A new idea can bring you back.
        </p>
      </section>
    );
  }

  return (
    <section
      className="one-dashboard band stage"
      data-theme="zed"
      data-glow="1"
      data-tier={String(Math.min(7, Math.max(1, one.tier)))}
      aria-labelledby="od-title"
    >
      {one.glow_up ? <GlowUp glow={one.glow_up} number={one.number} inductionNo={one.induction_no} /> : null}
      <div className="one-hero">
        <div className="jersey jersey-lg one-jersey" data-tilt="6">
          <p className="jersey-num">
            <span className="visually-hidden">Your number </span>
            {one.number}
          </p>
          <span className="jersey-bar" aria-hidden="true" />
        </div>
        <div className="one-hero-copy">
          <OneSpark inductionNo={one.induction_no} colour={one.tier_colour} size={72} zeros />
          <h2 id="od-title" className="t-display">
            You&apos;re No. {one.number}
          </h2>
          <p className="lead-dark">
            <span className="swatch" aria-hidden="true" />
            Tier {one.tier}, {one.tier_name}. {one.way_in} since {day(one.since)}.
          </p>
          {one.line ? (
            <p className="lead-dark">
              {one.line}
              {one.stage ? `. ${one.stage}.` : ""}
            </p>
          ) : null}
        </div>
      </div>
      <p role="status" aria-live="polite" className="sr-status">
        {status}
      </p>

      {one.can_swap ? (
        <form
          className="glass one-section"
          onSubmit={async (e) => {
            e.preventDefault();
            const n = Number(number);
            if (!Number.isInteger(n) || n < 1 || n > 999) {
              setNumberError(ERRORS.number_out_of_range!);
              return;
            }
            const err = await send("/api/me/one/number", { number: n });
            setNumberError(err ?? "");
            if (!err) {
              setStatus(`You're now No. ${n}.`);
              router.refresh();
            }
          }}
        >
          <h3>Your number</h3>
          <p className="hint" id={`${numberId}-hint`}>
            Keep No. {one.number}, or choose any free number from 1 to 999 until {day(one.swap_until)}. First
            come, first served. After that, it&apos;s yours.
          </p>
          <label htmlFor={numberId}>Number you&apos;d like</label>
          <input
            id={numberId}
            inputMode="numeric"
            value={number}
            onChange={(e) => setNumber(e.target.value.replace(/[^0-9]/g, "").slice(0, 3))}
            aria-describedby={`${numberId}-hint${numberError ? ` ${numberId}-err` : ""}`}
            aria-invalid={numberError ? true : undefined}
            className="input number-input"
          />
          {numberError ? (
            <p className="field-error" id={`${numberId}-err`}>
              {numberError}
            </p>
          ) : null}
          <div className="btn-row">
            <button type="submit" className="btn btn-primary">
              Choose this number
            </button>
          </div>
        </form>
      ) : null}

      <div className="glass one-section">
        <h3>Your impact brief</h3>
        {one.brief ? <p>{one.brief}</p> : <p className="muted">No brief on the wall yet.</p>}
        {one.brief_pending ? <p className="muted">Your new brief is with the core committee.</p> : null}
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const err = await send("/api/me/one/brief", { text: brief });
            setBriefError(err ?? "");
            if (!err) {
              setBrief("");
              setStatus("Your brief is with the core committee.");
              router.refresh();
            }
          }}
        >
          <label htmlFor={briefId}>{one.brief ? "Propose a new brief" : "Write your brief"}</label>
          <p className="hint" id={`${briefId}-hint`}>
            What changes if your idea works, in 30 words or fewer. Start with &quot;If this works:&quot;. The
            committee approves it before it shows. {words}/30 words.
          </p>
          <textarea
            className="textarea"
            id={briefId}
            rows={3}
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            aria-describedby={`${briefId}-hint${briefError ? ` ${briefId}-err` : ""}`}
            aria-invalid={briefError ? true : undefined}
          />
          {briefError ? (
            <p className="field-error" id={`${briefId}-err`}>
              {briefError}
            </p>
          ) : null}
          <div className="btn-row">
            <button type="submit" className="btn btn-primary">
              Send to the committee
            </button>
          </div>
        </form>
      </div>

      <div className="glass one-section">
        <h3>Impact so far</h3>
        {measures.length ? (
          <ul className="jersey-measures">
            {measures.map(([label, words]) => (
              <li key={label}>
                <span>{label}:</span> {words}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">Measured 30 and 90 days after your idea ships.</p>
        )}
      </div>

      <div className="glass one-section">
        <h3>More for Ones</h3>
        <ul>
          <li>
            <Link href="/one">Your Showcase brief</Link>
            {one.showcase_updated ? ` (updated ${day(one.showcase_updated)})` : ""}
          </li>
          <li>
            <Link href="/wall?ones=leaderboard#ones">The Ones leaderboard</Link>
          </li>
        </ul>
      </div>
    </section>
  );
}
