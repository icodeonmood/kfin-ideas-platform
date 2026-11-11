"use client";

/**
 * The idea canvas (§4.1): quick capture or the full six sections. A thinking aid, not a form: each question
 * says why we ask, links to an example, and the strength meter guides without ever blocking.
 * Native controls only, so the whole canvas works by keyboard and with a screen reader (AT-B3-09).
 */
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  CHOICES,
  ESTIMATE_FIELDS,
  MIC_HINT,
  QUESTIONS,
  QUICK_DECLARATION,
  QUICK_DECLARATION_COVERS,
  wordCount,
  type Canvas,
  type Mode,
} from "@/lib/canvas/model";
import {
  blocks,
  parseFigure,
  personalData,
  QUICK_DECLARATION_FIELD,
  strengthPanel,
  validate,
  type CanvasLimits,
  type FieldError,
  type PersonalDataHit,
  type StrengthRubric,
} from "@/lib/canvas/rules";

import { Attachments, type AttachmentItem, type AttachmentLimits } from "./attachments";
import { insertTranscript } from "./voice-logic";
import { VoiceRecorder } from "./voice-recorder";

type Example = { slug: string; section: string };
type Props = {
  id: string;
  mode: Mode;
  initial: Canvas;
  limits: CanvasLimits;
  rubric: StrengthRubric;
  examples: Example[];
  kfinDomains: string[];
  attachments: AttachmentItem[];
  attachmentLimits: AttachmentLimits;
  /** `capture.mic_hint` (DEC-096): suggest the phone keyboard's mic under the quick capture box. */
  micHint: boolean;
  /** `capture.voice` (DEC-096): record a voice note that becomes text in the box; off shows "coming soon". */
  voice: boolean;
};

const fid = (path: string) => "f-" + path.replace(/[.]/g, "-");
const SAVE_DELAY_MS = 1500;

/** Immutable update of a nested canvas path ("value.estimate.note"). */
function setPath(c: Canvas, path: string, value: unknown): Canvas {
  const next = structuredClone(c) as unknown as Record<string, unknown>;
  const keys = path.split(".");
  let node = next;
  for (const k of keys.slice(0, -1)) node = node[k] as Record<string, unknown>;
  node[keys.at(-1)!] = value;
  return next as unknown as Canvas;
}

const POINT_LABELS: Record<string, string> = {
  what_it_is: "What it is",
  who_it_touches: "Who it touches",
  whats_it_worth: "What it's worth",
  evidence: "Evidence",
  solved_elsewhere: "Solved elsewhere",
};

export function CanvasForm(props: Props) {
  const router = useRouter();
  const [canvas, setCanvas] = useState<Canvas>(props.initial);
  const [errors, setErrors] = useState<FieldError[]>([]);
  const [figureErrors, setFigureErrors] = useState<Record<string, string>>({});
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [savedAt, setSavedAt] = useState<string>("");
  const [submitState, setSubmitState] = useState<"idle" | "sending" | "failed">("idle");
  const [files, setFiles] = useState<AttachmentItem[]>(props.attachments);
  const summaryRef = useRef<HTMLDivElement>(null);
  // The last answers the server has; autosave sends whatever differs (even if typing continued mid-save).
  const lastSaved = useRef(JSON.stringify(props.initial));
  const saveChain = useRef<Promise<void>>(Promise.resolve());

  const hits = useMemo(() => personalData(canvas, props.kfinDomains), [canvas, props.kfinDomains]);
  const blocked = blocks(hits);
  const cleanFiles = files.filter((f) => f.state === "clean").length;
  const panel = useMemo(
    () => strengthPanel(canvas, props.rubric, cleanFiles),
    [canvas, props.rubric, cleanFiles],
  );
  const isQuick = props.mode === "quick";

  const update = (path: string, value: unknown) => setCanvas((c) => setPath(c, path, value));

  // Autosave (§4.1 step 2): pauses while a blocking personal-data match is showing.
  useEffect(() => {
    const json = JSON.stringify(canvas);
    if (blocked || json === lastSaved.current) return;
    const timer = setTimeout(() => {
      // One save at a time, in order: a slow earlier save can never land after (and undo) a later one.
      saveChain.current = saveChain.current.then(async () => {
        if (json === lastSaved.current) return;
        setSaveState("saving");
        const res = await fetch(`/api/submissions/${props.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ canvas: JSON.parse(json) }),
        }).catch(() => null);
        if (res?.ok) {
          lastSaved.current = json;
          setSaveState("saved");
          setSavedAt(
            new Date().toLocaleTimeString("en-IN", {
              hour: "2-digit",
              minute: "2-digit",
              timeZone: "Asia/Kolkata",
            }),
          );
        } else {
          setSaveState("error");
        }
      });
    }, SAVE_DELAY_MS);
    return () => clearTimeout(timer);
  }, [canvas, blocked, props.id]);

  const errorFor = (path: string) =>
    errors.find((e) => e.field === path)?.message ?? figureErrors[path] ?? undefined;
  const hitsFor = (path: string) => hits.filter((h) => h.field === path);

  async function share(event: React.FormEvent) {
    event.preventDefault();
    const found = validate(canvas, props.limits);
    setErrors(found);
    if (found.length || blocked || Object.keys(figureErrors).length) {
      setSubmitState("idle");
      requestAnimationFrame(() => summaryRef.current?.focus());
      return;
    }
    setSubmitState("sending");
    const res = await fetch(`/api/submissions/${props.id}/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ canvas }),
    }).catch(() => null);
    if (res?.status === 202) {
      router.push(`/share/${props.id}/done`);
      return;
    }
    const body = (await res?.json().catch(() => null)) as { error?: string; details?: FieldError[] } | null;
    if (body?.error === "invalid" && body.details) setErrors(body.details);
    setSubmitState("failed");
    requestAnimationFrame(() => summaryRef.current?.focus());
  }

  const blockedFields = [...new Set(hits.filter((h) => h.match.action === "block").map((h) => h.field))];
  const problems = [
    ...errors.map((e) => ({ href: `#${fid(e.field)}`, text: e.message })),
    ...Object.entries(figureErrors).map(([path, text]) => ({ href: `#${fid(path)}`, text })),
    ...blockedFields.map((f) => ({
      href: `#${fid(f)}`,
      text: "Remove the investor or customer details highlighted here before you share.",
    })),
  ];

  const example = (slug: string) => {
    const ex = props.examples.find((e) => e.slug === slug);
    return ex ? (
      <p className="example-link">
        <a href={`/share/examples/${slug}`} target="_blank" rel="noopener">
          What good looks like<span className="visually-hidden"> for {ex.section} (opens in a new tab)</span>
        </a>
      </p>
    ) : null;
  };

  const text = (path: string, label: string, why: string, opts: Partial<TextProps> = {}) => (
    <TextField
      path={path}
      label={label}
      why={why}
      value={String(
        path.split(".").reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], canvas) ?? "",
      )}
      onChange={(v) => update(path, v)}
      hits={hitsFor(path)}
      error={errorFor(path)}
      {...opts}
    />
  );

  return (
    <form onSubmit={share} noValidate className="canvas" aria-labelledby="canvas-title">
      <h1 id="canvas-title">{isQuick ? "Quick capture" : "Share an idea"}</h1>
      <p className="lead">
        {isQuick
          ? "One box, about a minute. Say it your way and add files if you have them. You can add more later, and the assistant will suggest the rest for you to check."
          : "Six short sections. Better answers make your idea faster to review and stronger in committee. A missing answer never stops you sharing."}
      </p>

      {problems.length && submitState !== "sending" ? (
        <div
          className="summary error-summary"
          role="alert"
          tabIndex={-1}
          ref={summaryRef}
          aria-labelledby="summary-title"
        >
          <h2 id="summary-title" className="summary-title">
            {problems.length === 1
              ? "One thing to fix before you share"
              : `${problems.length} things to fix before you share`}
          </h2>
          <ul>
            {problems.map((p) => (
              <li key={p.href + p.text}>
                <a href={p.href}>{p.text}</a>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {submitState === "failed" && !problems.length ? (
        <p role="alert" className="notice notice-error" ref={summaryRef} tabIndex={-1}>
          We couldn&apos;t share that just now. Your answers are saved; please try again.
        </p>
      ) : null}

      <div className="canvas-layout">
        <div className="canvas-sections">
          {isQuick ? (
            <section aria-labelledby="quick-title" className="glass canvas-section">
              <h2 id="quick-title">Your idea</h2>
              {text("details", QUESTIONS.quick_noticed.label, "", {
                multiline: true,
                required: true,
                hint: `${QUESTIONS.quick_noticed.why} At least ${props.limits.details_min_chars} characters.`,
              })}
              {props.micHint ? (
                <p className="hint" id="quick-mic-hint">
                  {MIC_HINT}
                </p>
              ) : null}
              <VoiceRecorder
                ideaId={props.id}
                enabled={props.voice}
                onTranscript={(heard) =>
                  setCanvas((c) => setPath(c, "details", insertTranscript(c.details, heard)))
                }
              />
              <Attachments
                ideaId={props.id}
                files={files}
                onChange={setFiles}
                limits={props.attachmentLimits}
              />
              <details className="more-details">
                <summary>Add more if you like</summary>
                <Choices
                  type="radio"
                  path="value.category"
                  label={QUESTIONS.quick_value.label}
                  why={QUESTIONS.quick_value.why}
                  options={CHOICES.category}
                  values={canvas.value.category ? [canvas.value.category] : []}
                  onChange={(v) => update("value.category", v[0] ?? null)}
                  error={errorFor("value.category")}
                />
              </details>
            </section>
          ) : (
            <>
              <section aria-labelledby="s1-title" className="glass canvas-section">
                <h2 id="s1-title">1. What is it?</h2>
                {example("what-is-it")}
                <Choices
                  type="radio"
                  path="kind"
                  label={QUESTIONS.kind.label}
                  why={QUESTIONS.kind.why}
                  options={CHOICES.kind}
                  values={canvas.kind ? [canvas.kind] : []}
                  onChange={(v) => update("kind", v[0] ?? null)}
                  error={errorFor("kind")}
                  required
                />
                {text("one_line", QUESTIONS.one_line.label, QUESTIONS.one_line.why, {
                  required: true,
                  counter: `${wordCount(canvas.one_line)} of ${props.limits.one_line_max_words} words`,
                })}
                {text("details", QUESTIONS.details.label, QUESTIONS.details.why, {
                  multiline: true,
                  required: true,
                  hint: `At least ${props.limits.details_min_chars} characters, in any language.`,
                })}
              </section>

              <section aria-labelledby="s2-title" className="glass canvas-section">
                <h2 id="s2-title">2. Who does it touch?</h2>
                {example("who-it-touches")}
                <Choices
                  type="checkbox"
                  path="who.segments"
                  label={QUESTIONS.segments.label}
                  why={QUESTIONS.segments.why}
                  options={CHOICES.segments}
                  values={canvas.who.segments}
                  onChange={(v) => update("who.segments", v)}
                />
                <Choices
                  type="radio"
                  path="who.frequency_or_reach"
                  label={QUESTIONS.frequency_or_reach.label}
                  why={QUESTIONS.frequency_or_reach.why}
                  options={CHOICES.frequency}
                  values={canvas.who.frequency_or_reach ? [canvas.who.frequency_or_reach] : []}
                  onChange={(v) => update("who.frequency_or_reach", v[0] ?? "")}
                />
                {text(
                  "who.today_alternative",
                  QUESTIONS.today_alternative.label,
                  QUESTIONS.today_alternative.why,
                  {
                    multiline: true,
                  },
                )}
              </section>

              <section aria-labelledby="s3-title" className="glass canvas-section">
                <h2 id="s3-title">3. What&apos;s it worth to KFintech?</h2>
                {example("whats-it-worth")}
                <Choices
                  type="radio"
                  path="value.category"
                  label={QUESTIONS.category.label}
                  why={QUESTIONS.category.why}
                  options={CHOICES.category}
                  values={canvas.value.category ? [canvas.value.category] : []}
                  onChange={(v) => update("value.category", v[0] ?? null)}
                  error={errorFor("value.category")}
                  required
                />
                <Choices
                  type="radio"
                  path="value.play"
                  label={QUESTIONS.play.label}
                  why={QUESTIONS.play.why}
                  options={CHOICES.play}
                  values={canvas.value.play ? [canvas.value.play] : []}
                  onChange={(v) => update("value.play", v[0] ?? null)}
                />
                <fieldset className="field" aria-describedby="estimate-why">
                  <legend>{QUESTIONS.estimate.label}</legend>
                  <p id="estimate-why" className="why">
                    Why we ask: {QUESTIONS.estimate.why}
                  </p>
                  <div className="estimates">
                    {ESTIMATE_FIELDS.map(([key, label]) => (
                      <Figure
                        key={key}
                        path={`value.estimate.${key}`}
                        label={label}
                        value={canvas.value.estimate[key]}
                        error={figureErrors[`value.estimate.${key}`]}
                        onChange={(raw) => {
                          const parsed = parseFigure(raw);
                          const path = `value.estimate.${key}`;
                          setFigureErrors((e) => {
                            const next = { ...e };
                            if (parsed === "invalid")
                              next[path] = `${label}: please enter a number, for example 50000.`;
                            else delete next[path];
                            return next;
                          });
                          if (parsed !== "invalid") update(path, parsed);
                        }}
                      />
                    ))}
                  </div>
                </fieldset>
                <Choices
                  type="radio"
                  path="value.basis"
                  label={QUESTIONS.basis.label}
                  why={QUESTIONS.basis.why}
                  options={CHOICES.basis}
                  values={canvas.value.basis ? [canvas.value.basis] : []}
                  onChange={(v) => update("value.basis", v[0] ?? null)}
                />
              </section>

              <section aria-labelledby="s4-title" className="glass canvas-section">
                <h2 id="s4-title">4. Has anyone solved this?</h2>
                {example("solved-elsewhere")}
                <Choices
                  type="radio"
                  path="ecosystem.solved_elsewhere"
                  label={QUESTIONS.solved_elsewhere.label}
                  why={QUESTIONS.solved_elsewhere.why}
                  options={CHOICES.solved}
                  values={canvas.ecosystem.solved_elsewhere ? [canvas.ecosystem.solved_elsewhere] : []}
                  onChange={(v) => update("ecosystem.solved_elsewhere", v[0] ?? null)}
                />
                {text("ecosystem.our_advantage", QUESTIONS.our_advantage.label, QUESTIONS.our_advantage.why, {
                  multiline: true,
                  hint:
                    (canvas.kind === "business_idea"
                      ? "Committees look for this first in business ideas. "
                      : "") + QUESTIONS.our_advantage.prompts,
                })}
              </section>

              <section aria-labelledby="s5-title" className="glass canvas-section">
                <h2 id="s5-title">5. Your solution</h2>
                {example("your-solution")}
                {text("solution.approach", QUESTIONS.approach.label, QUESTIONS.approach.why, {
                  multiline: true,
                  required: canvas.kind === "problem_with_solution",
                })}
                {text("solution.needs", QUESTIONS.needs.label, QUESTIONS.needs.why, { multiline: true })}
                {text("solution.risks", QUESTIONS.risks.label, QUESTIONS.risks.why, { multiline: true })}
              </section>

              <section aria-labelledby="s6-title" className="glass canvas-section">
                <h2 id="s6-title">6. Your research</h2>
                {example("your-research")}
                <p className="why">Why we ask: {QUESTIONS.research.why}</p>
                <References
                  value={canvas.ecosystem.references}
                  hits={hits}
                  onChange={(refs) => update("ecosystem.references", refs)}
                />
                <Attachments
                  ideaId={props.id}
                  files={files}
                  onChange={setFiles}
                  limits={props.attachmentLimits}
                />
              </section>
            </>
          )}

          <section aria-labelledby="before-title" className="glass canvas-section">
            <h2 id="before-title">Before you share</h2>
            <Choices
              type="radio"
              path="visibility"
              label={QUESTIONS.visibility.label}
              why=""
              options={[
                ["org", "Everyone at KFintech"],
                ["committee", "Committees only"],
              ]}
              values={[canvas.visibility]}
              onChange={(v) => update("visibility", v[0] ?? "org")}
              required
            />
            {canvas.visibility === "committee"
              ? text("visibility_reason", "Why committees only?", "", { multiline: true, required: true })
              : null}
            {isQuick ? (
              <QuickDeclaration
                checked={Object.values(canvas.declarations).every(Boolean)}
                onChange={(on) =>
                  update("declarations", { no_personal_data: on, own_work_or_credited: on, ip_terms: on })
                }
                error={errorFor(QUICK_DECLARATION_FIELD)}
              />
            ) : (
              <fieldset className="field" id={fid("declarations")}>
                <legend>
                  Please confirm <span className="req">(required)</span>
                </legend>
                {CHOICES.declarations.map(([key, label]) => {
                  const path = `declarations.${key}`;
                  const error = errorFor(path);
                  return (
                    <div key={key} className="choice-row">
                      <label className="choice">
                        <input
                          id={fid(path)}
                          type="checkbox"
                          checked={canvas.declarations[key]}
                          onChange={(e) => update(path, e.target.checked)}
                          aria-invalid={error ? true : undefined}
                          aria-describedby={error ? `${fid(path)}-error` : undefined}
                        />
                        {label}
                      </label>
                      {error ? (
                        <p id={`${fid(path)}-error`} className="field-error">
                          {error}
                        </p>
                      ) : null}
                    </div>
                  );
                })}
              </fieldset>
            )}
          </section>

          <div className="submit-row">
            <button type="submit" className="btn btn-primary btn-lg" disabled={submitState === "sending"}>
              {submitState === "sending" ? "Sharing…" : "Share your idea"}
            </button>
            <p className="save-status" role="status" aria-live="polite">
              {blocked
                ? "Autosave is paused until the highlighted personal details are removed."
                : saveState === "saving"
                  ? "Saving…"
                  : saveState === "saved"
                    ? `Draft saved at ${savedAt}.`
                    : saveState === "error"
                      ? "We couldn't save your draft just now. Keep going; we'll try again."
                      : "Your draft saves as you type."}
            </p>
          </div>
        </div>

        {panel.kind === "note" ? (
          <aside className="glass strength" aria-label="What happens next">
            <p>{panel.note}</p>
          </aside>
        ) : (
          <aside className="glass strength" aria-labelledby="strength-title">
            <h2 id="strength-title">How ready is this for a committee?</h2>
            <p className="strength-score" aria-live="polite">
              <strong>{panel.strength.score} of 5</strong>
            </p>
            <span className="slashes strength-slashes" aria-hidden="true">
              {[0, 1, 2, 3, 4].map((i) => (
                <i key={i} className="slash" data-state={i < panel.strength.score ? undefined : "empty"} />
              ))}
            </span>
            <ul className="strength-points">
              {Object.entries(panel.strength.points).map(([key, done]) => (
                <li key={key} className={done ? "done" : "todo"}>
                  <span className="visually-hidden">{done ? "Done: " : "Not yet: "}</span>
                  <span aria-hidden="true">{done ? "✓ " : "○ "}</span>
                  {POINT_LABELS[key]}
                </li>
              ))}
            </ul>
            {panel.strength.nextBest.length ? (
              <>
                <h3>Most useful next</h3>
                <ol>
                  {panel.strength.nextBest.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ol>
              </>
            ) : (
              <p>This looks ready. You can still add more.</p>
            )}
            <p className="muted">This guides you; it never stops you sharing.</p>
          </aside>
        )}
      </div>
    </form>
  );
}

// ---- fields ------------------------------------------------------------------------------------------------

type TextProps = {
  path: string;
  label: string;
  why: string;
  value: string;
  onChange: (v: string) => void;
  hits: PersonalDataHit[];
  error?: string;
  multiline?: boolean;
  required?: boolean;
  hint?: string;
  counter?: string;
};

function TextField(p: TextProps) {
  const id = fid(p.path);
  const describedBy = [
    p.why ? `${id}-why` : "",
    p.hint ? `${id}-hint` : "",
    p.counter ? `${id}-counter` : "",
    p.hits.length ? `${id}-pd` : "",
    p.error ? `${id}-error` : "",
  ]
    .filter(Boolean)
    .join(" ");
  const invalid = Boolean(p.error) || p.hits.some((h) => h.match.action === "block");
  const common = {
    id,
    value: p.value,
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => p.onChange(e.target.value),
    "aria-describedby": describedBy || undefined,
    "aria-invalid": invalid || undefined,
    "aria-required": p.required || undefined,
  };
  return (
    <div className="field">
      <label htmlFor={id}>
        {p.label}
        {p.required ? <span className="req"> (required)</span> : null}
      </label>
      {p.why ? (
        <p id={`${id}-why`} className="why">
          Why we ask: {p.why}
        </p>
      ) : null}
      {p.hint ? (
        <p id={`${id}-hint`} className="hint">
          {p.hint}
        </p>
      ) : null}
      {p.multiline ? <textarea rows={4} {...common} /> : <input type="text" {...common} />}
      {p.counter ? (
        <p id={`${id}-counter`} className="hint">
          {p.counter}
        </p>
      ) : null}
      <PersonalDataNote id={`${id}-pd`} hits={p.hits} text={p.value} />
      {p.error ? (
        <p id={`${id}-error`} className="field-error">
          {p.error}
        </p>
      ) : null}
    </div>
  );
}

/** The browser's level-1 check (§4.1 step 1): shows the person what to remove, in their own text. */
function PersonalDataNote({ id, hits, text }: { id: string; hits: PersonalDataHit[]; text: string }) {
  if (!hits.length) return null;
  return (
    <div id={id} className="pd-note">
      {hits.map((h) => (
        <p
          key={`${h.match.patternId}-${h.match.start}`}
          className={h.match.action === "block" ? "pd-block" : "pd-warn"}
        >
          {h.match.action === "block"
            ? `This looks like ${article(h.match.label)} ${h.match.label}: `
            : `This looks like ${article(h.match.label)} ${h.match.label}: `}
          <mark>{text.slice(h.match.start, h.match.end)}</mark>.{" "}
          {h.match.action === "block"
            ? "Investor and customer details can't be shared here. Please remove it."
            : "That's fine for work contacts. Only keep it if it's needed."}
        </p>
      ))}
    </div>
  );
}

/**
 * Quick capture's one confirmation (DEC-094): a single tick confirms all three declarations, and the full text of
 * each sits in a disclosure right under it.
 */
function QuickDeclaration(p: { checked: boolean; onChange: (on: boolean) => void; error?: string }) {
  const id = fid(QUICK_DECLARATION_FIELD);
  return (
    <fieldset className="field">
      <legend>
        Please confirm <span className="req">(required)</span>
      </legend>
      <div className="choice-row">
        <label className="choice">
          <input
            id={id}
            type="checkbox"
            checked={p.checked}
            onChange={(e) => p.onChange(e.target.checked)}
            aria-invalid={p.error ? true : undefined}
            aria-describedby={[`${id}-covers-note`, p.error ? `${id}-error` : ""].filter(Boolean).join(" ")}
          />
          {QUICK_DECLARATION}
        </label>
        <p id={`${id}-covers-note`} className="hint">
          {QUICK_DECLARATION_COVERS}
        </p>
        {p.error ? (
          <p id={`${id}-error`} className="field-error">
            {p.error}
          </p>
        ) : null}
      </div>
      <details className="more-details" id={`${id}-covers`}>
        <summary>What this covers</summary>
        <ul>
          {CHOICES.declarations.map(([key, label]) => (
            <li key={key}>{label}</li>
          ))}
        </ul>
      </details>
    </fieldset>
  );
}

const article = (label: string) => (/^[AEIOU]/i.test(label) ? "an" : "a");

function Choices(p: {
  type: "radio" | "checkbox";
  path: string;
  label: string;
  why: string;
  options: ReadonlyArray<readonly [string, string]>;
  values: readonly string[];
  onChange: (values: string[]) => void;
  error?: string;
  required?: boolean;
}) {
  const id = fid(p.path);
  const describedBy = [p.why ? `${id}-why` : "", p.error ? `${id}-error` : ""].filter(Boolean).join(" ");
  return (
    <fieldset className="field" aria-describedby={describedBy || undefined}>
      <legend>
        {p.label}
        {p.required ? <span className="req"> (required)</span> : null}
      </legend>
      {p.why ? (
        <p id={`${id}-why`} className="why">
          Why we ask: {p.why}
        </p>
      ) : null}
      <div className="choices">
        {p.options.map(([value, label], i) => (
          <label key={value} className="choice">
            <input
              id={i === 0 ? id : `${id}-${value}`}
              type={p.type}
              name={p.path}
              value={value}
              checked={p.values.includes(value)}
              aria-invalid={p.error ? true : undefined}
              onChange={(e) => {
                if (p.type === "radio") p.onChange([value]);
                else
                  p.onChange(e.target.checked ? [...p.values, value] : p.values.filter((v) => v !== value));
              }}
            />
            {label}
          </label>
        ))}
      </div>
      {p.error ? (
        <p id={`${id}-error`} className="field-error">
          {p.error}
        </p>
      ) : null}
    </fieldset>
  );
}

function Figure(p: {
  path: string;
  label: string;
  value: number | null;
  error?: string;
  onChange: (raw: string) => void;
}) {
  const id = fid(p.path);
  const [raw, setRaw] = useState(p.value === null ? "" : String(p.value));
  return (
    <div className="figure">
      <label htmlFor={id}>{p.label}</label>
      <input
        id={id}
        type="text"
        inputMode="numeric"
        value={raw}
        onChange={(e) => {
          setRaw(e.target.value);
          p.onChange(e.target.value);
        }}
        aria-invalid={p.error ? true : undefined}
        aria-describedby={p.error ? `${id}-error` : undefined}
      />
      {p.error ? (
        <p id={`${id}-error`} className="field-error">
          {p.error}
        </p>
      ) : null}
    </div>
  );
}

function References(p: {
  value: Canvas["ecosystem"]["references"];
  hits: PersonalDataHit[];
  onChange: (refs: Canvas["ecosystem"]["references"]) => void;
}) {
  const set = (i: number, patch: Partial<Canvas["ecosystem"]["references"][number]>) =>
    p.onChange(p.value.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  return (
    <fieldset className="field">
      <legend>Links and notes</legend>
      <p className="hint">
        Links are stored as you give them and opened by people, never fetched automatically. Up to 20.
      </p>
      {p.value.map((ref, i) => {
        const path = `ecosystem.references.${i}.value`;
        const id = fid(path);
        const refHits = p.hits.filter((h) => h.field === path);
        return (
          <div key={i} className="reference-row">
            <div>
              <label htmlFor={`${id}-kind`}>Type</label>
              <select
                id={`${id}-kind`}
                value={ref.kind}
                onChange={(e) => set(i, { kind: e.target.value as "link" | "note" })}
              >
                <option value="link">Link</option>
                <option value="note">Note</option>
              </select>
            </div>
            <div>
              <label htmlFor={`${id}-player`}>Who</label>
              <select
                id={`${id}-player`}
                value={ref.player ?? ""}
                onChange={(e) => set(i, { player: (e.target.value || null) as never })}
              >
                <option value="">Not sure</option>
                {CHOICES.player.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </div>
            <div className="reference-value">
              <label htmlFor={id}>{ref.kind === "link" ? "Link" : "Note"}</label>
              <input
                id={id}
                type="text"
                value={ref.value}
                onChange={(e) => set(i, { value: e.target.value })}
                aria-describedby={refHits.length ? `${id}-pd` : undefined}
              />
              <PersonalDataNote id={`${id}-pd`} hits={refHits} text={ref.value} />
            </div>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => p.onChange(p.value.filter((_, j) => j !== i))}
              aria-label={`Remove ${ref.kind} ${i + 1}`}
            >
              Remove
            </button>
          </div>
        );
      })}
      {p.value.length < 20 ? (
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => p.onChange([...p.value, { kind: "link", value: "", player: null }])}
        >
          Add a link or note
        </button>
      ) : null}
    </fieldset>
  );
}
