"use client";

/**
 * After the scan (§4.2 steps 4 and 7): the person checks the canvas ("Looks right"), then Find your crew.
 * Match cards show only what the server sends: heading, neutral summary, area, stage, colleague count and, for
 * solutions, the owning team. Never another person's text, file or name. Platform words only: "Already running",
 * "Team up", never "duplicate" or "already solved".
 */
import { useEffect, useRef, useState } from "react";

import { BANNERS } from "@/lib/killswitch-routes";

export type MatchCard = {
  ref: string | null;
  kind: "idea" | "cluster" | "solution" | "decision" | "with_desk";
  label: "same" | "related";
  heading: string;
  summary?: string | null;
  area?: string | null;
  stage?: string;
  colleagues?: number | null;
  owning_lob?: string | null;
};
export type Ready = {
  /** Each suggestion with the person's own words it came from (DEC-095). */
  suggested: { path: string; value: unknown; quotes?: string[] }[];
  /** Questions left blank because the person did not say. */
  left_blank?: string[];
  /** The basic assumptions behind the suggested figures, in plain words (DEC-097). */
  assumptions?: string[];
  neutral_summary: string;
  next_best: string[];
  matches: MatchCard[];
  matches_hidden?: boolean;
  card: { one_line: string | null; details: string | null };
  confirmed: boolean;
};

const ERRORS: Record<string, string> = {
  context_too_short: "Please add at least 30 characters about your context.",
  one_line_required: "Please add a line on how yours is different.",
  personal_data: "Please take out personal details first.",
  one_line_too_long: "Please keep the one line to 20 words or fewer.",
  details_too_short: "Please tell us a little more (at least 50 characters).",
  own_idea: "That idea is yours already.",
  already_on_it: "You are already on this one.",
  checks_unavailable: "We can't check that just now. Please try again in a few minutes.",
  changed_meanwhile: "Something changed while you were working. Please check the page and try again.",
};

function show(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ").replace(/_/g, " ");
  if (value && typeof value === "object") return Object.values(value).filter(Boolean).join(", ");
  return String(value ?? "").replace(/_/g, " ");
}

/** A suggested answer as people read it: rupees with Indian grouping (₹5,00,000), hours and clients with their unit. */
export function showSuggestion(path: string, value: unknown): string {
  if (typeof value === "number") {
    const n = value.toLocaleString("en-IN", { maximumFractionDigits: 1 });
    if (path.startsWith("value.estimate.inr_"))
      return `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
    if (path === "value.estimate.hours_saved_per_month")
      return `${n} ${value === 1 ? "hour" : "hours"} a month`;
    if (path === "value.estimate.clients_who_would_pay") return `${n} ${value === 1 ? "client" : "clients"}`;
    return n;
  }
  return show(value);
}

type Action = { ref: string | null; choice: string; label: string; needs?: "context" | "line" };

function actionsFor(card: MatchCard): Action[] {
  if (card.kind === "with_desk") return [];
  if (card.kind === "decision")
    return [{ ref: card.ref, choice: "something_changed", label: "Something has changed", needs: "line" }];
  if (card.kind === "solution")
    return [
      { ref: card.ref, choice: "team_up", label: "Team up to bring it to my area" },
      { ref: card.ref, choice: "different", label: "Mine is different", needs: "line" },
    ];
  if (card.label !== "same") return [];
  return [
    { ref: card.ref, choice: "team_up", label: "Team up with my context", needs: "context" },
    { ref: card.ref, choice: "different", label: "Mine is different", needs: "line" },
  ];
}

export function Crew({
  id,
  ready,
  labelFor,
  onChanged,
  headingRef,
}: {
  id: string;
  ready: Ready;
  labelFor: (path: string) => string;
  onChanged: () => Promise<void>;
  headingRef: React.RefObject<HTMLHeadingElement | null>;
}) {
  const [keep, setKeep] = useState<Record<string, boolean>>({});
  const [oneLine, setOneLine] = useState(ready.card.one_line ?? "");
  const [details, setDetails] = useState(ready.card.details ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Where the error belongs: the canvas check, a match card (its ref) or the page (BLD-C049).
  const [errorAt, setErrorAt] = useState<string>("page");
  const [note, setNote] = useState("");
  const [open, setOpen] = useState<Action | null>(null);
  const [text, setText] = useState("");
  const crewRef = useRef<HTMLHeadingElement>(null);
  const wantCrewFocus = useRef(false);

  // Opening "Mine is different" (or another choice that needs words) moves focus to its box (BLD-C049).
  useEffect(() => {
    if (open) document.getElementById(`crew-text-${open.ref}`)?.focus();
  }, [open]);

  // After "Looks right", move focus to Find your crew once it has rendered.
  useEffect(() => {
    if (ready.confirmed && wantCrewFocus.current) {
      wantCrewFocus.current = false;
      crewRef.current?.focus();
    }
  }, [ready.confirmed]);

  async function post(path: string, body: unknown, where = "page") {
    setBusy(true);
    setError("");
    setErrorAt(where);
    const res = await fetch(`/api/submissions/${id}/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch(() => null);
    const out = (await res?.json().catch(() => null)) as Record<string, unknown> | null;
    setBusy(false);
    if (!res?.ok) {
      setError(ERRORS[String(out?.error)] ?? "We couldn't save that just now. Please try again.");
      return null;
    }
    return out;
  }

  async function looksRight(event: React.FormEvent) {
    event.preventDefault();
    const body: Record<string, unknown> = { keep };
    if (oneLine !== (ready.card.one_line ?? "")) body.one_line = oneLine;
    if (details !== (ready.card.details ?? "")) body.details = details;
    const out = await post("confirm-card", body, "canvas");
    if (!out) return;
    setNote(
      out.rerun_match ? "You changed the text, so we looked again for colleagues on the same thing." : "",
    );
    wantCrewFocus.current = true;
    await onChanged();
  }

  async function choose(action: Action) {
    const out = await post(
      "choose",
      { choice: action.choice, ref: action.ref, text: action.needs ? text : "" },
      action.ref ?? "page",
    );
    if (!out) return;
    setOpen(null);
    setText("");
    await onChanged();
  }

  return (
    <div>
      <h3 ref={headingRef} tabIndex={-1}>
        Your summary is ready
      </h3>
      {ready.neutral_summary ? (
        <p>
          <strong>In short:</strong> {ready.neutral_summary}
        </p>
      ) : null}

      {!ready.confirmed ? (
        <form onSubmit={(e) => void looksRight(e)}>
          <h4>Check your canvas</h4>
          <div className="field">
            <label htmlFor="crew-one-line">Say it in one line</label>
            <p id="crew-one-line-hint" className="hint">
              20 words or fewer.
            </p>
            <input
              id="crew-one-line"
              type="text"
              value={oneLine}
              aria-describedby="crew-one-line-hint"
              onChange={(e) => setOneLine(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="crew-details">Tell us more</label>
            <textarea
              id="crew-details"
              rows={5}
              value={details}
              onChange={(e) => setDetails(e.target.value)}
            />
          </div>
          {ready.suggested.length ? (
            <>
              <p>We suggested answers for some questions you left blank:</p>
              {ready.suggested.map((s) => {
                const name = `keep-${s.path.replace(/\./g, "-")}`;
                const kept = keep[s.path] ?? true;
                // The value and the person's words behind it describe both choices (WCAG 1.3.1, 4.1.2).
                const valueId = `${name}-value`;
                const wordsId = `${name}-words`;
                const describedBy = s.quotes?.length ? `${valueId} ${wordsId}` : valueId;
                return (
                  <fieldset key={s.path} className="field suggestion">
                    <legend>{labelFor(s.path)}</legend>
                    <p id={valueId} className="suggested-value">
                      <span className="visually-hidden">Our suggestion: </span>
                      {showSuggestion(s.path, s.value)}
                    </p>
                    {s.quotes?.length ? (
                      <div
                        id={wordsId}
                        className="from-words"
                        role="group"
                        aria-labelledby={`${wordsId}-label`}
                      >
                        <p id={`${wordsId}-label`} className="hint">
                          From your words:
                        </p>
                        {s.quotes.map((q, i) => (
                          <blockquote key={i}>
                            <p>{q}</p>
                          </blockquote>
                        ))}
                      </div>
                    ) : null}
                    <label className="choice">
                      <input
                        type="radio"
                        name={name}
                        checked={kept}
                        aria-describedby={describedBy}
                        onChange={() => setKeep((k) => ({ ...k, [s.path]: true }))}
                      />
                      Keep this suggestion
                    </label>
                    <label className="choice">
                      <input
                        type="radio"
                        name={name}
                        checked={!kept}
                        aria-describedby={describedBy}
                        onChange={() => setKeep((k) => ({ ...k, [s.path]: false }))}
                      />
                      Leave it blank
                    </label>
                  </fieldset>
                );
              })}
              {ready.assumptions?.length ? (
                <div className="from-words" role="group" aria-labelledby="crew-assumptions">
                  <p id="crew-assumptions" className="hint">
                    Assumptions we made:
                  </p>
                  <ul>
                    {ready.assumptions.map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </>
          ) : null}
          {ready.left_blank?.length ? (
            <p className="hint">
              We left {ready.left_blank.length === 1 ? "this" : "these"} blank because you didn&apos;t say:{" "}
              {ready.left_blank.map(labelFor).join("; ")}. Add {ready.left_blank.length === 1 ? "it" : "them"}{" "}
              if you know, under &ldquo;Tell us more&rdquo;.
            </p>
          ) : null}
          {error && errorAt === "canvas" ? (
            <p className="field-error" role="alert">
              {error}
            </p>
          ) : null}
          <button type="submit" className="btn btn-primary" disabled={busy}>
            Looks right
          </button>
        </form>
      ) : (
        <section aria-labelledby="crew-title">
          <h3 id="crew-title" ref={crewRef} tabIndex={-1}>
            Find your crew
          </h3>
          <p className="muted" role="status" aria-live="polite">
            {note}
          </p>
          {ready.matches_hidden ? (
            <p>{BANNERS["matching.show"]}</p>
          ) : ready.matches.length ? (
            <ul className="crew-cards">
              {ready.matches.map((card, i) => (
                <li key={card.ref ?? `desk-${i}`} className="match crew-card">
                  <h4 id={`crew-card-${card.ref ?? "desk"}`}>{card.heading}</h4>
                  {card.kind !== "with_desk" ? (
                    <>
                      <p>{card.summary ?? "A related idea."}</p>
                      <dl className="facts crew-facts">
                        {card.area ? (
                          <div>
                            <dt>Area</dt>
                            <dd>{card.area}</dd>
                          </div>
                        ) : null}
                        {card.stage ? (
                          <div>
                            <dt>Where it is</dt>
                            <dd>{card.stage}</dd>
                          </div>
                        ) : null}
                        {card.colleagues ? (
                          <div>
                            <dt>Colleagues on it</dt>
                            <dd>{card.colleagues}</dd>
                          </div>
                        ) : null}
                        {card.owning_lob ? (
                          <div>
                            <dt>Team that runs it</dt>
                            <dd>{card.owning_lob}</dd>
                          </div>
                        ) : null}
                      </dl>
                      {actionsFor(card).length ? (
                        <div className="btn-row">
                          {actionsFor(card).map((a) => (
                            <button
                              key={a.choice}
                              type="button"
                              className="btn btn-secondary"
                              disabled={busy}
                              aria-describedby={`crew-card-${card.ref}`}
                              aria-expanded={
                                a.needs ? open?.ref === a.ref && open?.choice === a.choice : undefined
                              }
                              aria-controls={a.needs ? `crew-form-${card.ref}` : undefined}
                              onClick={() => {
                                if (a.needs) {
                                  setText("");
                                  setOpen(a);
                                } else void choose(a);
                              }}
                            >
                              {a.label}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <p className="muted">Listed for information. Nothing to do.</p>
                      )}
                      {open && open.ref === card.ref ? (
                        <form
                          id={`crew-form-${card.ref}`}
                          onSubmit={(e) => {
                            e.preventDefault();
                            void choose(open);
                          }}
                        >
                          <div className="field">
                            <label htmlFor={`crew-text-${card.ref}`}>
                              {open.needs === "context"
                                ? "What does your situation add? (at least 30 characters)"
                                : open.choice === "something_changed"
                                  ? "What has changed?"
                                  : "How is yours different?"}
                            </label>
                            <textarea
                              id={`crew-text-${card.ref}`}
                              rows={3}
                              value={text}
                              aria-invalid={error && errorAt === card.ref ? true : undefined}
                              aria-describedby={
                                error && errorAt === card.ref ? `crew-error-${card.ref}` : undefined
                              }
                              onChange={(e) => setText(e.target.value)}
                            />
                          </div>
                          <button type="submit" className="btn btn-primary" disabled={busy}>
                            {open.label}
                          </button>
                        </form>
                      ) : null}
                      {error && errorAt === card.ref ? (
                        <p id={`crew-error-${card.ref}`} className="field-error" role="alert">
                          {error}
                        </p>
                      ) : null}
                    </>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p>No one has raised this yet. You are the first.</p>
          )}
          <div className="btn-row">
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => void choose({ ref: null, choice: "new", label: "" })}
            >
              {ready.matches.length ? "None of these: share mine as a new idea" : "Share my idea"}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={busy}
              onClick={() => void choose({ ref: null, choice: "withdraw", label: "" })}
            >
              Withdraw my idea
            </button>
          </div>
        </section>
      )}
      {error && errorAt === "page" ? (
        <p className="field-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
