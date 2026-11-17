"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState, type CSSProperties, type FormEvent } from "react";

import { CountOnce } from "@/components/count-once";
import { buttonClass } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import type { NumberWindow, OneDashboardResponse, TierMoment } from "@/lib/contracts/api";
import type { Impact } from "@/lib/contracts/entities";

import { GlowUp } from "./glow-up";
import {
  BEING_MEASURED,
  BRIEF_CANCEL,
  BRIEF_FIELD,
  BRIEF_SEND,
  briefCount,
  briefProblem,
  MSG_BRIEF_PENDING,
  MSG_NO_BRIEF,
  MSG_OUT_OF_RANGE,
  MSG_SAVE_FAILED,
  splitFigure,
  wholeNumber,
} from "./rules";
import { ShowcaseSheet } from "./showcase-sheet";

const MEASURES: { key: keyof Impact; label: string }[] = [
  { key: "time", label: "Time" },
  { key: "money", label: "Money" },
  { key: "effort", label: "Effort" },
  { key: "scale", label: "Scale" },
];

const tierVar = (tier: number) => ({ "--on-tier": `var(--tier-${tier})` }) as CSSProperties;

function Chevron() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="m6 3.5 4.5 4.5L6 12.5" />
    </svg>
  );
}

function Crumbs() {
  return (
    <nav aria-label="Breadcrumb" className="on-crumb">
      <ol role="list">
        <li>
          <Link href="/my-ideas">My ideas</Link>
        </li>
        <li aria-current="page">
          <span aria-hidden="true" className="on-sep">
            /
          </span>
          Your One dashboard
        </li>
      </ol>
    </nav>
  );
}

/** S-ONE.layout/3, V-FIELDS.one/1–3: keep or swap the number inside the window, then it is theirs for good. */
function NumberCard({ win, onSaved }: { win: NumberWindow; onSaved: (next: NumberWindow) => void }) {
  const hintId = useId();
  const input = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState(String(win.number));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const n = wholeNumber(value);
    if (n === null) {
      setError(MSG_OUT_OF_RANGE);
      input.current?.focus();
      return;
    }
    setBusy(true);
    const res = await fetch("/api/one/number", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ number: n }),
    }).catch(() => null);
    const body = (await res?.json().catch(() => null)) as {
      number_window?: NumberWindow;
      error?: { code?: string; message?: string };
    } | null;
    setBusy(false);
    if (res?.ok && body?.number_window) {
      setError(null);
      setValue(String(body.number_window.number));
      onSaved(body.number_window);
      return;
    }
    if (body?.error?.code === "window_closed") {
      onSaved({
        ...win,
        open: false,
        locked_label: body.error.message || `No. ${win.number} is yours for good.`,
      });
      return;
    }
    setError(body?.error?.message || MSG_SAVE_FAILED);
    input.current?.focus();
  };

  return (
    <section className="card on-card" aria-labelledby="on-num-h">
      <h2 id="on-num-h" className="on-t4">
        Your number
      </h2>
      {win.open ? (
        <form onSubmit={save} noValidate>
          <p id={hintId} className="body on-hint">
            {win.keep_label}
          </p>
          <div className="on-fld">
            <Field label="Number you'd like" error={error}>
              {(ctl) => (
                <div className="on-numrow">
                  <input
                    {...ctl}
                    ref={input}
                    className={`${ctl.className} on-numin num`}
                    inputMode="numeric"
                    autoComplete="off"
                    maxLength={3}
                    value={value}
                    aria-describedby={[hintId, ctl["aria-describedby"]].filter(Boolean).join(" ")}
                    onChange={(e) => {
                      setValue(e.target.value);
                      if (error) setError(null);
                    }}
                  />
                  <button type="submit" className={buttonClass("primary")} aria-busy={busy || undefined}>
                    Save my number
                  </button>
                </div>
              )}
            </Field>
          </div>
        </form>
      ) : (
        <p className="on-locked">{win.locked_label ?? `No. ${win.number} is yours for good.`}</p>
      )}
    </section>
  );
}

/** S-ONE.layout/4, L-ONES.rules/5: the brief on the Wall, and a new one proposed for the programme team. */
function BriefCard({ brief, onProposed }: { brief: OneDashboardResponse["brief"]; onProposed: () => void }) {
  const opener = useRef<HTMLButtonElement>(null);
  const box = useRef<HTMLTextAreaElement>(null);
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // The field takes focus when the person opens it, and the button takes it back when the field closes
  // (V-ACC.visual/11). After the render, so the element is there to take it.
  const refocus = useRef(false);
  useEffect(() => {
    if (open) box.current?.focus();
    else if (refocus.current) {
      refocus.current = false;
      opener.current?.focus();
    }
  }, [open]);

  const close = () => {
    refocus.current = true;
    setOpen(false);
    setError(null);
  };

  const send = async (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const problem = briefProblem(text);
    if (problem) {
      setError(problem);
      box.current?.focus();
      return;
    }
    setBusy(true);
    const res = await fetch("/api/one/brief", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    }).catch(() => null);
    const body = (await res?.json().catch(() => null)) as { error?: { message?: string } } | null;
    setBusy(false);
    if (res?.ok) {
      setText("");
      onProposed();
      close();
      return;
    }
    setError(body?.error?.message || MSG_SAVE_FAILED);
    box.current?.focus();
  };

  return (
    <section className="card on-card" aria-labelledby="on-brief-h">
      <div className="on-row">
        <h2 id="on-brief-h" className="on-t4">
          Your impact brief
        </h2>
        {brief.text ? <Pill variant="ok">On the wall</Pill> : null}
      </div>
      {brief.text ? <p className="on-brief">{brief.text}</p> : <p className="body on-hint">{MSG_NO_BRIEF}</p>}
      <p className="body on-hint" role="status">
        {brief.pending ? MSG_BRIEF_PENDING : ""}
      </p>
      {open ? (
        <form className="on-briefform" onSubmit={send} noValidate>
          <Field label={BRIEF_FIELD} help={briefCount(text.length)} error={error} multiline>
            {(ctl) => (
              <textarea
                {...ctl}
                ref={box}
                rows={3}
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                  if (error) setError(null);
                }}
              />
            )}
          </Field>
          <div className="btn-row on-actions">
            <button type="button" className={buttonClass("text")} onClick={close}>
              {BRIEF_CANCEL}
            </button>
            <button type="submit" className={buttonClass("line")} aria-busy={busy || undefined}>
              {BRIEF_SEND}
            </button>
          </div>
        </form>
      ) : (
        <div className="on-actions">
          <button ref={opener} type="button" className={buttonClass("line")} onClick={() => setOpen(true)}>
            Propose a new brief
          </button>
        </div>
      )}
    </section>
  );
}

/** S-ONE.layout/5, L-IMPACT/4: the latest measured figures; a measure not in yet reads "Being measured". */
function ImpactSoFar({ impact }: { impact: Impact }) {
  return (
    <section className="on-sec" aria-labelledby="on-impact-h">
      <div className="on-sec-head">
        <h2 id="on-impact-h" className="d2">
          Impact so far
        </h2>
        <p className="body">Measured 30 and 90 days after your idea ships.</p>
      </div>
      <ul className="on-g4" role="list">
        {MEASURES.map(({ key, label }) => {
          const f = impact[key];
          const { big, unit } = f ? splitFigure(f.value) : { big: "", unit: "" };
          return (
            <li key={key}>
              <p className="on-eb">{label}</p>
              {f ? (
                <>
                  <p className="num on-fig">
                    <CountOnce value={big} />
                    {unit ? <span className="on-unit"> {unit}</span> : null}
                  </p>
                  <p className="on-note">{f.line}</p>
                </>
              ) : (
                <p className="on-wait">{BEING_MEASURED}</p>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/**
 * S-ONE: the hero (number card, "You're No. 1", tier line, the idea), Your number, Your impact brief, Impact so far
 * and More for Ones; the glow-up moment over it when a tier has just risen. One column on a phone, the hero first.
 */
export function OneScreen({ data }: { data: OneDashboardResponse }) {
  const heading = useRef<HTMLHeadingElement>(null);
  const showcaseOpener = useRef<HTMLButtonElement>(null);
  const [win, setWin] = useState(data.number_window);
  const [said, setSaid] = useState("");
  const [brief, setBrief] = useState(data.brief);
  const [moment, setMoment] = useState<TierMoment | null>(data.tier_moment);
  const [showcase, setShowcase] = useState(false);
  const { one } = data;
  const number = win.number;
  const name = one.person?.name ?? "";
  const idea = data.idea?.title ? data.idea.title.replace(/\s+$/, "") : "";

  return (
    <div className="on" style={tierVar(one.tier)}>
      <Crumbs />

      <section className="slab on-slab" aria-labelledby="on-h1">
        <div className="on-glow" aria-hidden="true" />
        <div className="on-hero">
          <div className="on-jersey">
            <div className="on-glow on-glow-card" aria-hidden="true" />
            <div className="on-jersey-in">
              <div className="on-flag">
                <span className="on-bar" aria-hidden="true" />
                <span>{one.flag_label}</span>
              </div>
              <p className="num on-big">
                <span className="vh">Your number </span>
                {number}
              </p>
              {name ? <p className="on-name">{name}</p> : null}
              <p className="on-tier">{one.tier_label}</p>
            </div>
          </div>
          <div className="on-head">
            <h1 id="on-h1" ref={heading} tabIndex={-1} className="d1 on-h1">
              {`You're No. ${number}`}
            </h1>
            <p className="on-since">
              <span className="on-dot" aria-hidden="true" />
              {data.since_line}
            </p>
            {idea ? (
              <div className="on-idea">
                <p className="on-ebd">Your idea</p>
                <p className="on-idea-t">{/[.!?]$/.test(idea) ? idea : `${idea}.`}</p>
              </div>
            ) : null}
          </div>
        </div>
      </section>
      <p className="vh" role="status">
        {said}
      </p>

      <div className="on-g2">
        <NumberCard
          win={win}
          onSaved={(next) => {
            setWin(next);
            if (next.number !== number) setSaid(`You're No. ${next.number}`);
          }}
        />
        <BriefCard brief={brief} onProposed={() => setBrief((b) => ({ ...b, pending: true }))} />
      </div>

      <ImpactSoFar impact={data.impact} />

      <section className="on-sec on-more" aria-labelledby="on-more-h">
        <h2 id="on-more-h" className="h3">
          More for Ones
        </h2>
        <ul role="list">
          <li>
            <button
              ref={showcaseOpener}
              type="button"
              className="on-link"
              aria-haspopup="dialog"
              onClick={() => setShowcase(true)}
            >
              Your Showcase brief <Chevron />
            </button>
          </li>
          <li>
            <Link href="/wall?ones=leaderboard#ones" className="on-link">
              The Ones leaderboard <Chevron />
            </Link>
          </li>
        </ul>
      </section>

      {showcase ? (
        <ShowcaseSheet
          onClose={() => {
            setShowcase(false);
            showcaseOpener.current?.focus();
          }}
        />
      ) : null}
      {moment ? (
        <GlowUp
          key={moment.id}
          moment={moment}
          number={number}
          onClose={() => {
            setMoment(null);
            heading.current?.focus();
          }}
        />
      ) : null}
    </div>
  );
}
