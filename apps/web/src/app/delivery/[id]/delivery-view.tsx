"use client";

import Link from "next/link";
import { useId, useState, type FormEvent, type ReactNode } from "react";

import { day } from "@/lib/dates";
import { measureText, MEASURE_LABELS } from "@/lib/measures";
import type {
  Checkins,
  DeliveryDetail,
  EvidenceFile,
  Measurement,
  Milestone,
  PackDraft,
  Writeup,
  WriteupPart,
} from "@/server/delivery";

import { ERRORS, Err, missingText, Status, useAction, useDone } from "../actions";

const PRODUCT_WORDS: Record<string, string> = {
  iris: "IRIS",
  lamf: "Loans against mutual funds",
  guardian: "Guardian",
  "api-marketplace": "API marketplace",
  "ai-tooling": "AI tooling",
  "sif-aif-pms": "SIF, AIF and PMS",
  "mf-central": "MF Central",
  other: "Other",
};
const FEATURE_WORDS: Record<string, string> = {
  "kfintech-product": "A change to a KFintech product",
  "ai-tooling": "An internal AI tool",
};
const TIER_WORDS: Record<string, string> = { standard: "Standard", express: "Express (low risk)" };
const TRACK_WORDS: Record<string, string> = {
  build: "Build",
  fix: "Non-tech fix",
  procurement: "Buy or partner",
};
const CHECKLIST: [string, string, (d: DeliveryDetail, featureType: string) => boolean][] = [
  ["working_group_formed", "The working group is formed", () => true],
  ["baseline_captured", "The baseline number is captured", () => true],
  ["build_slot_confirmed", "A build slot is confirmed", (d) => d.track !== "fix"],
  [
    "dev_slot_confirmed",
    "A development slot is confirmed (product changes only)",
    (d, featureType) => d.track !== "fix" && featureType === "kfintech-product",
  ],
];
const MARK_WORDS = { day_30: "Results at 30 days", day_90: "Results at 90 days" } as const;
const KEYS = ["time", "money", "effort", "scale"] as const;

export function DeliveryView({ d }: { d: DeliveryDetail }) {
  const { status, done } = useDone();
  const building = d.track !== "fix";
  const started = !["drafting", "awaiting_sponsor"].includes(d.state);
  return (
    <>
      <p>
        <Link href="/delivery">Back to Delivery</Link>
      </p>
      <h1>{d.label}</h1>
      <p className="lead">
        {d.subject_id}. {d.track_words}. {d.state_words}
        {d.state === "in_delivery" && d.phase_words ? `: ${d.phase_words}` : ""}.
        {d.outcome
          ? ` ${d.outcome === "target_met" ? "It met its target." : "It closed short of its target."}`
          : ""}
      </p>
      <Status text={status} />
      <dl className="crew-facts">
        <div>
          <dt>Owner</dt>
          <dd>{d.owner?.name ?? "Not named yet"}</dd>
        </div>
        <div>
          <dt>Sponsor</dt>
          <dd>{d.sponsor?.name ?? "Not named yet"}</dd>
        </div>
        {building ? (
          <div>
            <dt>Delivery PM</dt>
            <dd>{d.pm?.name ?? "Not named yet"}</dd>
          </div>
        ) : null}
        {d.sponsor_approved_at ? (
          <div>
            <dt>Sponsor approved</dt>
            <dd>{day(d.sponsor_approved_at)}</dd>
          </div>
        ) : null}
      </dl>

      <section aria-labelledby="s-pack">
        <h2 id="s-pack">Handover pack</h2>
        {d.can.edit ? <PackForm d={d} onDone={done} /> : <PackSummary d={d} />}
        {d.missing.length && !started ? (
          <p className="notice">Still needed before the sponsor can approve: {missingText(d.missing)}.</p>
        ) : null}
        <PackActions d={d} onDone={done} />
      </section>

      {started && building ? (
        <section aria-labelledby="s-status">
          <h2 id="s-status">Where the build is</h2>
          <p>
            {d.phase_words ?? "Not started"}
            {d.gate_status === "blocked"
              ? `. Blocked${d.blocked_since ? ` since ${day(d.blocked_since)}` : ""}.`
              : "."}
            {d.link_state === "linked" ? " Linked to the delivery pipeline's page." : ""}
            {d.link_state === "manual" ? " Steps are recorded here by hand." : ""}
          </p>
          <p className="coming-soon coming-soon-light">Live sync with the delivery pipeline: coming soon</p>
          {d.can.set_phase ? <PhaseForm d={d} onDone={done} /> : null}
          {d.can.link ? <LinkForm d={d} onDone={done} /> : null}
        </section>
      ) : null}

      {started && !building ? <FixTrack d={d} onDone={done} /> : null}

      {d.measurements.length ? (
        <section aria-labelledby="s-results">
          <h2 id="s-results">Results</h2>
          <p className="muted">
            The owner fills these in at 30 and 90 days. The sponsor confirms them. Money shows on the wall
            only after Finance confirms it.
          </p>
          {d.measurements.map((m) => (
            <MeasurementCard key={m.mark} d={d} m={m} onDone={done} />
          ))}
        </section>
      ) : null}

      {d.writeup ? <WriteupSection d={d} w={d.writeup} onDone={done} /> : null}

      {started || d.evidence.length ? <EvidenceSection d={d} onDone={done} /> : null}
    </>
  );
}

const KB = 1024;
const size = (bytes: number) =>
  bytes >= KB * KB ? `${(bytes / (KB * KB)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / KB))} KB`;

function EvidenceSection({ d, onDone }: { d: DeliveryDetail; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const [uploadError, setUploadError] = useState("");
  const [uploading, setUploading] = useState(false);
  const inputId = useId();
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const input = form.elements.namedItem("file") as HTMLInputElement | null;
    const file = input?.files?.[0];
    if (!file) {
      setUploadError(ERRORS.file_required ?? "Choose a file first.");
      return;
    }
    setUploading(true);
    const body = new FormData();
    body.set("file", file);
    const res = await fetch(`/api/delivery/${d.id}/evidence`, { method: "POST", body }).catch(() => null);
    setUploading(false);
    if (res?.ok) {
      setUploadError("");
      form.reset();
      onDone("File added. It opens once the checks finish.");
      return;
    }
    const out = res ? ((await res.json().catch(() => ({}))) as { error?: string }) : {};
    setUploadError(ERRORS[String(out.error ?? "")] ?? "That didn't work. Please try again.");
  }
  return (
    <section aria-labelledby="s-evidence">
      <h2 id="s-evidence">Evidence</h2>
      <p className="muted">
        Files that back the numbers. Every file is checked for viruses and personal details before anyone can
        open it.
      </p>
      {d.evidence.length ? (
        <ul className="timeline">
          {d.evidence.map((f) => (
            <EvidenceRow key={f.id} d={d} f={f} busy={busy} run={run} />
          ))}
        </ul>
      ) : (
        <p className="muted">No files yet.</p>
      )}
      <Err text={error} />
      {d.can.add_evidence ? (
        <form className="stack-form" onSubmit={upload}>
          <label htmlFor={inputId}>Add a file</label>
          <input id={inputId} name="file" type="file" />
          <div className="button-row">
            <button type="submit" className="button button-secondary" disabled={uploading}>
              {uploading ? "Adding…" : "Add the file"}
            </button>
          </div>
          <Err text={uploadError} />
        </form>
      ) : null}
    </section>
  );
}

function EvidenceRow({
  d,
  f,
  busy,
  run,
}: {
  d: DeliveryDetail;
  f: EvidenceFile;
  busy: boolean;
  run: (url: string, body: Record<string, unknown>, done: string, method?: string) => Promise<boolean>;
}) {
  return (
    <li>
      {f.can_open ? <a href={`/api/delivery/${d.id}/evidence/${f.id}`}>{f.name}</a> : <span>{f.name}</span>}{" "}
      <span className="muted">
        ({size(f.bytes)}. {f.state_words}
        {f.rejection_words ? `: ${f.rejection_words}` : ""})
      </span>
      {f.can_remove ? (
        <>
          {" "}
          <button
            type="button"
            className="link-button"
            disabled={busy}
            aria-label={`Remove ${f.name}`}
            onClick={() => run(`/api/delivery/${d.id}/evidence/${f.id}`, {}, "File removed.", "DELETE")}
          >
            Remove
          </button>
        </>
      ) : null}
    </li>
  );
}

function CheckinSection({ d, c, onDone }: { d: DeliveryDetail; c: Checkins; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const [status, setStatus] = useState<string>("");
  const [note, setNote] = useState("");
  const groupId = useId();
  return (
    <>
      <h3>Friday check-in</h3>
      {c.recent.length ? (
        <ul className="timeline">
          {c.recent.map((r) => (
            <li key={r.week_of}>
              Week of {day(r.week_of)}: {r.status_words}
              {r.note ? `. ${r.note}` : "."}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">No check-ins yet.</p>
      )}
      {c.can_reply ? (
        <form
          className="stack-form"
          onSubmit={async (e) => {
            e.preventDefault();
            if (await run(`/api/delivery/${d.id}/checkin`, { status, note }, "Check-in saved.")) setNote("");
          }}
        >
          <fieldset>
            <legend id={groupId}>
              {c.replied_this_week ? "Update this week's check-in" : "How is it going this week?"}
            </legend>
            <div className="choices">
              {c.statuses.map((s) => (
                <label key={s.id} className="choice">
                  <input
                    type="radio"
                    name="checkin-status"
                    value={s.id}
                    checked={status === s.id}
                    onChange={() => setStatus(s.id)}
                  />{" "}
                  {s.words}
                </label>
              ))}
            </div>
          </fieldset>
          <Field label="A short note (optional)" hint="What changed, or what would unblock it.">
            {(id, hint) => (
              <textarea
                id={id}
                value={note}
                maxLength={400}
                rows={3}
                aria-describedby={hint}
                onChange={(e) => setNote(e.target.value)}
              />
            )}
          </Field>
          <div className="button-row">
            <button type="submit" className="button button-secondary" disabled={busy}>
              Save the check-in
            </button>
          </div>
          <Err text={error} />
        </form>
      ) : null}
    </>
  );
}

const WRITEUP_PARTS: { key: WriteupPart; label: string; hint: string; max: number; rows: number }[] = [
  { key: "title", label: "Title", hint: "What it is, in plain words.", max: 80, rows: 1 },
  {
    key: "what_it_does",
    label: "What it does",
    hint: "Two or three sentences. No client or investor details.",
    max: 600,
    rows: 4,
  },
  {
    key: "where_it_runs",
    label: "Where it runs",
    hint: "Line of business, system, team.",
    max: 300,
    rows: 2,
  },
  {
    key: "result",
    label: "The result",
    hint: "Before and after, if known: hours saved, errors avoided.",
    max: 400,
    rows: 3,
  },
  {
    key: "how_to_adopt",
    label: "How another team can adopt it",
    hint: "Who to talk to by role, never by name; what it needs; how much effort.",
    max: 600,
    rows: 4,
  },
];

/** The write-up other teams can adopt (BLD-133): the owner drafts and submits, the named sponsor approves or sends
 * it back. Approved, it is published as "Already running", so new ideas can team up with it. */
function WriteupSection({ d, w, onDone }: { d: DeliveryDetail; w: Writeup; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const [parts, setParts] = useState<Record<WriteupPart, string>>(
    w.parts ?? { title: "", what_it_does: "", where_it_runs: "", result: "", how_to_adopt: "" },
  );
  const [editing, setEditing] = useState(false);
  const save = (e: FormEvent) => {
    e.preventDefault();
    void run(`/api/delivery/${d.id}/writeup`, parts, "Write-up saved.", "PUT").then(
      (ok) => ok && setEditing(false),
    );
  };
  return (
    <section aria-labelledby="s-writeup">
      <h2 id="s-writeup">A write-up other teams can adopt</h2>
      <p className="muted">
        Status: {w.state_words}.
        {w.solution_id
          ? ` Published as ${w.solution_id}: people see it as "Already running" when they share a similar idea.`
          : ""}
      </p>
      {w.state === null && !editing ? (
        <p>
          Once it has shipped, write up what it does and how another team can use it. Everyone will be able to
          read it, so leave out names of colleagues and clients.
        </p>
      ) : null}
      {w.parts && !editing ? (
        <dl className="crew-facts">
          {WRITEUP_PARTS.map((f) => (
            <div key={f.key}>
              <dt>{f.label}</dt>
              <dd>{w.parts?.[f.key]}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {editing ? (
        <form className="stack-form" onSubmit={save}>
          {WRITEUP_PARTS.map((f) => (
            <Field key={f.key} label={f.label} hint={f.hint}>
              {(id, hint) =>
                f.rows === 1 ? (
                  <input
                    id={id}
                    type="text"
                    value={parts[f.key]}
                    maxLength={f.max}
                    aria-describedby={hint}
                    onChange={(e) => setParts({ ...parts, [f.key]: e.target.value })}
                  />
                ) : (
                  <textarea
                    id={id}
                    value={parts[f.key]}
                    maxLength={f.max}
                    rows={f.rows}
                    aria-describedby={hint}
                    onChange={(e) => setParts({ ...parts, [f.key]: e.target.value })}
                  />
                )
              }
            </Field>
          ))}
          <div className="button-row">
            <button type="submit" className="button" disabled={busy} aria-busy={busy}>
              Save the write-up
            </button>
            <button type="button" className="button button-secondary" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : null}
      {!editing ? (
        <div className="button-row">
          {w.can_edit ? (
            <button type="button" className="button button-secondary" onClick={() => setEditing(true)}>
              {w.parts ? "Edit the write-up" : "Write it up"}
            </button>
          ) : null}
          {w.can_submit ? (
            <button
              type="button"
              className="button"
              disabled={busy}
              aria-busy={busy}
              onClick={() => run(`/api/delivery/${d.id}/writeup/submit`, {}, "Sent to the sponsor.")}
            >
              Send to the sponsor
            </button>
          ) : null}
          {w.can_decide ? (
            <>
              <button
                type="button"
                className="button"
                disabled={busy}
                aria-busy={busy}
                onClick={() =>
                  run(
                    `/api/delivery/${d.id}/writeup/approve`,
                    {},
                    "Approved and published as Already running.",
                  )
                }
              >
                Approve and publish
              </button>
              <button
                type="button"
                className="button button-secondary"
                disabled={busy}
                onClick={() => run(`/api/delivery/${d.id}/writeup/send-back`, {}, "Sent back to the owner.")}
              >
                Send back for changes
              </button>
            </>
          ) : null}
        </div>
      ) : null}
      <Err text={error} />
    </section>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: (id: string, describedBy: string | undefined) => ReactNode;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id}>{label}</label>
      {hint ? (
        <p className="hint" id={`${id}-hint`}>
          {hint}
        </p>
      ) : null}
      {children(id, hint ? `${id}-hint` : undefined)}
    </div>
  );
}

function Select({
  label,
  value,
  options,
  words,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  words?: Record<string, string>;
  onChange: (v: string) => void;
}) {
  return (
    <Field label={label}>
      {(id) => (
        <select id={id} value={value} onChange={(e) => onChange(e.target.value)}>
          {options.map((o) => (
            <option key={o} value={o}>
              {words?.[o] ?? o}
            </option>
          ))}
        </select>
      )}
    </Field>
  );
}

function PackSummary({ d }: { d: DeliveryDetail }) {
  const p = d.pack;
  return (
    <dl className="crew-facts">
      <div>
        <dt>Success metric</dt>
        <dd>{d.metric ?? "Not set"}</dd>
      </div>
      <div>
        <dt>From and to</dt>
        <dd>
          {p.baseline ?? "?"} to {p.target ?? "?"} {p.unit ?? ""}
        </dd>
      </div>
      {d.track === "fix" ? (
        <div>
          <dt>Objective</dt>
          <dd>{d.objective ?? "Not set"}</dd>
        </div>
      ) : (
        <div>
          <dt>Product</dt>
          <dd>
            {PRODUCT_WORDS[p.product ?? ""] ?? "Not set"}, {FEATURE_WORDS[p.feature_type ?? ""] ?? ""}
          </dd>
        </div>
      )}
      <div>
        <dt>Spend reference</dt>
        <dd>{p.spend === "none" ? "No spend" : (p.spend ?? "Not set")}</dd>
      </div>
    </dl>
  );
}

function PackForm({ d, onDone }: { d: DeliveryDetail; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const p = d.pack;
  const [track, setTrack] = useState<string>(d.track);
  const [product, setProduct] = useState(p.product ?? "other");
  const [featureType, setFeatureType] = useState(p.feature_type ?? "kfintech-product");
  const [tier, setTier] = useState(p.compliance_tier ?? "standard");
  const [owner, setOwner] = useState(d.owner?.email ?? "");
  const [sponsor, setSponsor] = useState(d.sponsor?.email ?? "");
  const [pm, setPm] = useState(d.pm?.email ?? "");
  const [metric, setMetric] = useState(d.metric ?? "");
  const [objective, setObjective] = useState(d.objective ?? "");
  const [baseline, setBaseline] = useState(p.baseline == null ? "" : String(p.baseline));
  const [target, setTarget] = useState(p.target == null ? "" : String(p.target));
  const [unit, setUnit] = useState<string>(p.unit ?? d.options.metric_units[0] ?? "");
  const [spend, setSpend] = useState(p.spend === "none" ? "NONE" : (p.spend ?? ""));
  const [checklist, setChecklist] = useState<Record<string, boolean>>({ ...(p.checklist ?? {}) });
  const legendId = useId();
  const fix = track === "fix";
  const [drafting, setDrafting] = useState(false);
  const [draftNotes, setDraftNotes] = useState<string[] | null>(null);
  const [draftError, setDraftError] = useState("");

  /** The assistant proposes; the person checks every field and saves (BLD-138). Only empty text is filled. */
  async function askForDraft() {
    if (drafting) return;
    setDrafting(true);
    setDraftError("");
    const res = await fetch(`/api/delivery/${d.id}/pack-draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    }).catch(() => null);
    const out = (res ? await res.json().catch(() => ({})) : {}) as Partial<PackDraft> & {
      error?: string;
      banner?: string;
    };
    setDrafting(false);
    if (!res?.ok || !out.metric) {
      setDraftError(out.banner ?? ERRORS[String(out.error ?? "")] ?? ERRORS.assistant_unavailable ?? "");
      return;
    }
    if (!metric.trim()) setMetric(out.metric);
    if (out.unit) setUnit(out.unit);
    if (out.product) setProduct(out.product);
    if (out.feature_type) setFeatureType(out.feature_type);
    if (baseline === "" && out.baseline != null) setBaseline(String(out.baseline));
    if (target === "" && out.target != null) setTarget(String(out.target));
    if (fix && !objective.trim() && out.objective) setObjective(out.objective);
    setDraftNotes(out.notes ?? []);
  }

  function save(e: FormEvent) {
    e.preventDefault();
    const body: Record<string, unknown> = {
      track, product, feature_type: featureType, compliance_tier: tier, unit, baseline, target, spend, checklist,
      owner_email: owner, sponsor_email: sponsor, pm_email: fix ? "" : pm,
    }; // prettier-ignore
    if (metric.trim() && metric !== d.metric) body.metric = metric.trim();
    if (fix && objective.trim() && objective !== d.objective) body.objective = objective.trim();
    void run(`/api/delivery/${d.id}/pack`, body, "Pack saved.", "PUT");
  }

  return (
    <form className="stack-form" onSubmit={save} noValidate>
      <h3>Fill in the pack</h3>
      <p className="hint">
        Names are looked up by work email. Free text is checked for personal details before it is saved.
      </p>
      <div className="button-row">
        <button
          type="button"
          className="button button-secondary"
          disabled={drafting}
          aria-busy={drafting}
          onClick={() => void askForDraft()}
        >
          Draft it with the assistant
        </button>
      </div>
      <Err text={draftError} />
      {draftNotes ? (
        <div className="notice" role="status">
          <p>
            The assistant filled in the empty fields and suggested the unit, product and type from the idea.
            Check every field before you save. It never makes up numbers.
          </p>
          {draftNotes.length ? (
            <>
              <p>Questions to answer first:</p>
              <ul>
                {draftNotes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      ) : null}
      <Select
        label="Track"
        value={track}
        options={d.options.tracks}
        words={TRACK_WORDS}
        onChange={setTrack}
      />
      <Field
        label="Owner's work email"
        hint="The person who sees it through. They fill in the results later."
      >
        {(id, hint) => (
          <input
            id={id}
            type="email"
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
            aria-describedby={hint}
          />
        )}
      </Field>
      <Field label="Sponsor's work email" hint="A sponsor approves the pack and confirms the results.">
        {(id, hint) => (
          <input
            id={id}
            type="email"
            value={sponsor}
            onChange={(e) => setSponsor(e.target.value)}
            aria-describedby={hint}
          />
        )}
      </Field>
      {!fix ? (
        <Field label="Delivery PM's work email" hint="The person who records each step of the build.">
          {(id, hint) => (
            <input
              id={id}
              type="email"
              value={pm}
              onChange={(e) => setPm(e.target.value)}
              aria-describedby={hint}
            />
          )}
        </Field>
      ) : null}
      <Field
        label="Success metric"
        hint="What you will measure, in a few words. For example: minutes to reconcile one file."
      >
        {(id, hint) => (
          <input
            id={id}
            value={metric}
            maxLength={120}
            onChange={(e) => setMetric(e.target.value)}
            aria-describedby={hint}
          />
        )}
      </Field>
      <Field label="Starting number (baseline)">
        {(id) => (
          <input id={id} inputMode="decimal" value={baseline} onChange={(e) => setBaseline(e.target.value)} />
        )}
      </Field>
      <Field label="Target">
        {(id) => (
          <input id={id} inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} />
        )}
      </Field>
      <Select label="Unit" value={unit} options={d.options.metric_units} onChange={setUnit} />
      {fix ? (
        <Field label="Objective" hint="What will be different when this is fixed.">
          {(id, hint) => (
            <textarea
              id={id}
              rows={2}
              maxLength={400}
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              aria-describedby={hint}
            />
          )}
        </Field>
      ) : (
        <>
          <Select
            label="Product"
            value={product}
            options={d.options.products}
            words={PRODUCT_WORDS}
            onChange={setProduct}
          />
          <Select
            label="Type of change"
            value={featureType}
            options={d.options.feature_types}
            words={FEATURE_WORDS}
            onChange={setFeatureType}
          />
          <Select
            label="Compliance level"
            value={tier}
            options={d.options.compliance_tiers}
            words={TIER_WORDS}
            onChange={setTier}
          />
        </>
      )}
      <Field label="Spend reference" hint="The cost centre or budget code, or NONE if nothing is spent.">
        {(id, hint) => (
          <input
            id={id}
            value={spend}
            maxLength={31}
            onChange={(e) => setSpend(e.target.value)}
            aria-describedby={hint}
          />
        )}
      </Field>
      <fieldset className="field" aria-labelledby={legendId}>
        <legend id={legendId}>Ready to start</legend>
        {CHECKLIST.filter(([, , shown]) =>
          shown({ ...d, track: track as DeliveryDetail["track"] }, featureType),
        ).map(([key, words]) => (
          <label key={key} className="choice">
            <input
              type="checkbox"
              checked={Boolean(checklist[key])}
              onChange={(e) => setChecklist({ ...checklist, [key]: e.target.checked })}
            />{" "}
            {words}
          </label>
        ))}
      </fieldset>
      <div className="button-row">
        <button type="submit" className="button" disabled={busy}>
          Save the pack
        </button>
      </div>
      <Err text={error} />
    </form>
  );
}

function PackActions({ d, onDone }: { d: DeliveryDetail; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  if (!d.can.submit && !d.can.approve) {
    return d.state === "awaiting_sponsor" ? (
      <p>Sent to {d.sponsor?.name ?? "the sponsor"} for approval.</p>
    ) : null;
  }
  const url = `/api/delivery/${d.id}`;
  return (
    <div>
      <div className="button-row">
        {d.can.submit ? (
          <button
            type="button"
            className="button"
            disabled={busy}
            onClick={() => run(`${url}/submit`, {}, "Sent to the sponsor.")}
          >
            Send to the sponsor
          </button>
        ) : null}
        {d.can.approve ? (
          <>
            <button
              type="button"
              className="button"
              disabled={busy}
              onClick={() => run(`${url}/approve`, {}, "Approved. The work starts.")}
            >
              Approve the pack
            </button>
            <button
              type="button"
              className="button button-secondary"
              disabled={busy}
              onClick={() => run(`${url}/send-back`, {}, "Sent back to the owner.")}
            >
              Send it back to the owner
            </button>
          </>
        ) : null}
      </div>
      <Err text={error} />
    </div>
  );
}

function PhaseForm({ d, onDone }: { d: DeliveryDetail; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const [phase, setPhase] = useState<string>(d.phase ?? d.options.phases[0]?.id ?? "01-discover");
  const [gate, setGate] = useState<string>(d.gate_status ?? "clear");
  const words = Object.fromEntries(d.options.phases.map((p) => [p.id, p.words]));
  return (
    <form
      className="stack-form"
      onSubmit={(e) => {
        e.preventDefault();
        void run(`/api/delivery/${d.id}/phase`, { phase, gate_status: gate }, "Step recorded.");
      }}
    >
      <h3>Record the current step</h3>
      <Select
        label="Step"
        value={phase}
        options={d.options.phases.map((p) => p.id)}
        words={words}
        onChange={setPhase}
      />
      <Select
        label="Gate"
        value={gate}
        options={["clear", "blocked"]}
        words={{ clear: "Clear", blocked: "Blocked" }}
        onChange={setGate}
      />
      <p className="hint">Choosing Shipped opens the 30- and 90-day results.</p>
      <div className="button-row">
        <button type="submit" className="button" disabled={busy}>
          Save the step
        </button>
      </div>
      <Err text={error} />
    </form>
  );
}

function LinkForm({ d, onDone }: { d: DeliveryDetail; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const [page, setPage] = useState(d.pipeline_page_id ?? "");
  return (
    <form
      className="stack-form"
      onSubmit={(e) => {
        e.preventDefault();
        void run(`/api/delivery/${d.id}/link`, { page_id: page }, "Page linked.");
      }}
    >
      <h3>Link the pipeline page</h3>
      <Field
        label="Page ID"
        hint="The ID of this delivery's page in the delivery pipeline. Links are never opened."
      >
        {(id, hint) => (
          <input
            id={id}
            value={page}
            maxLength={64}
            onChange={(e) => setPage(e.target.value)}
            aria-describedby={hint}
          />
        )}
      </Field>
      <div className="button-row">
        <button type="submit" className="button button-secondary" disabled={busy}>
          Save the link
        </button>
      </div>
      <Err text={error} />
    </form>
  );
}

function FixTrack({ d, onDone }: { d: DeliveryDetail; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  return (
    <section aria-labelledby="s-plan">
      <h2 id="s-plan">Action plan</h2>
      {d.objective ? <p>Objective: {d.objective}</p> : null}
      {d.milestones.length ? (
        <ul className="timeline">
          {d.milestones.map((m) => (
            <MilestoneRow key={m.id} d={d} m={m} onDone={onDone} />
          ))}
        </ul>
      ) : (
        <p className="muted">No milestones yet.</p>
      )}
      {d.can.add_milestone ? <MilestoneForm d={d} onDone={onDone} /> : null}
      {d.checkins ? <CheckinSection d={d} c={d.checkins} onDone={onDone} /> : null}

      <h3>Completion</h3>
      {d.completion ? (
        <p>
          Before: {d.completion.before}, after: {d.completion.after} {d.completion.unit ?? ""}.
          {d.completion_notes ? ` ${d.completion_notes}` : ""}
          {d.state === "in_delivery" ? " Waiting for the sponsor." : ""}
        </p>
      ) : null}
      {d.can.complete ? <CompleteForm d={d} onDone={onDone} /> : null}
      {d.can.approve_completion ? (
        <div className="button-row">
          <button
            type="button"
            className="button"
            disabled={busy}
            onClick={() => run(`/api/delivery/${d.id}/approve-completion`, {}, "Approved. It's fixed.")}
          >
            Approve: it&apos;s fixed
          </button>
        </div>
      ) : null}
      <Err text={error} />
      <p className="muted">Add the files that back these numbers under Evidence below.</p>
    </section>
  );
}

function MilestoneRow({ d, m, onDone }: { d: DeliveryDetail; m: Milestone; onDone: (msg: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const next = m.status === "open" ? "done" : "open";
  return (
    <li>
      <strong>{m.title}</strong>, {m.owner ?? "the owner"}, due {day(m.due_on)}.{" "}
      {m.status === "done" ? "Done." : m.overdue ? "Overdue." : "Open."}
      {m.can_set && d.state === "in_delivery" ? (
        <>
          {" "}
          <button
            type="button"
            className="link-button"
            disabled={busy}
            onClick={() =>
              run(
                `/api/delivery/${d.id}/milestones/${m.id}`,
                { status: next },
                next === "done" ? "Marked done." : "Opened again.",
              )
            }
          >
            {next === "done" ? "Mark done" : "Open again"}
          </button>
        </>
      ) : null}
      <Err text={error} />
    </li>
  );
}

function MilestoneForm({ d, onDone }: { d: DeliveryDetail; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [owner, setOwner] = useState("");
  return (
    <form
      className="stack-form"
      onSubmit={async (e) => {
        e.preventDefault();
        if (
          await run(
            `/api/delivery/${d.id}/milestones`,
            { title, due_on: due, owner_email: owner },
            "Milestone added.",
          )
        ) {
          setTitle("");
          setDue("");
          setOwner("");
        }
      }}
    >
      <h3>Add a milestone</h3>
      <Field label="What will be done">
        {(id) => <input id={id} value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} />}
      </Field>
      <Field label="Due on">
        {(id) => <input id={id} type="date" value={due} onChange={(e) => setDue(e.target.value)} />}
      </Field>
      <Field label="Who does it (work email)" hint="Leave empty for the owner.">
        {(id, hint) => (
          <input
            id={id}
            type="email"
            value={owner}
            onChange={(e) => setOwner(e.target.value)}
            aria-describedby={hint}
          />
        )}
      </Field>
      <div className="button-row">
        <button type="submit" className="button button-secondary" disabled={busy}>
          Add the milestone
        </button>
      </div>
      <Err text={error} />
    </form>
  );
}

function CompleteForm({ d, onDone }: { d: DeliveryDetail; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const [before, setBefore] = useState(d.pack.baseline == null ? "" : String(d.pack.baseline));
  const [after, setAfter] = useState("");
  const [notes, setNotes] = useState("");
  return (
    <form
      className="stack-form"
      onSubmit={(e) => {
        e.preventDefault();
        void run(
          `/api/delivery/${d.id}/complete`,
          { before, after, ...(notes.trim() ? { notes: notes.trim() } : {}) },
          "Sent to the sponsor.",
        );
      }}
    >
      <h3>It&apos;s done: send the numbers</h3>
      <Field label={`Before (${d.pack.unit ?? "the metric"})`}>
        {(id) => (
          <input id={id} inputMode="decimal" value={before} onChange={(e) => setBefore(e.target.value)} />
        )}
      </Field>
      <Field label={`After (${d.pack.unit ?? "the metric"})`}>
        {(id) => (
          <input id={id} inputMode="decimal" value={after} onChange={(e) => setAfter(e.target.value)} />
        )}
      </Field>
      <Field label="Notes (optional)">
        {(id) => (
          <textarea
            id={id}
            rows={2}
            maxLength={600}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        )}
      </Field>
      <div className="button-row">
        <button type="submit" className="button" disabled={busy}>
          Send to the sponsor
        </button>
      </div>
      <Err text={error} />
    </form>
  );
}

function MeasurementCard({
  d,
  m,
  onDone,
}: {
  d: DeliveryDetail;
  m: Measurement;
  onDone: (msg: string) => void;
}) {
  const { error, busy, run } = useAction(onDone);
  const r = m.results;
  const filled = Boolean(m.filled_at);
  const url = `/api/delivery/${d.id}/measurements/${m.mark}`;
  return (
    <div className="card">
      <h3>{MARK_WORDS[m.mark]}</h3>
      <p className="meta">
        Due {day(m.due_at)}.{" "}
        {m.confirmed_at
          ? `Confirmed on ${day(m.confirmed_at)}.`
          : filled
            ? "Filled in, waiting for the sponsor."
            : "Not filled in yet."}
      </p>
      {filled ? (
        <ul>
          <li>
            {d.metric ?? "The metric"}: {r.metric_actual} {d.pack.unit ?? ""} (target {d.pack.target ?? "?"}).{" "}
            {r.target_met === true ? "Target met." : r.target_met === false ? "Not at target yet." : ""}
          </li>
          {r.capex_inr != null || r.opex_inr != null ? (
            <li>
              Cost: ₹{new Intl.NumberFormat("en-IN").format(r.capex_inr ?? 0)} one-time, ₹
              {new Intl.NumberFormat("en-IN").format(r.opex_inr ?? 0)} running.
            </li>
          ) : null}
          {r.adoption != null ? <li>People using it: {r.adoption}</li> : null}
          {KEYS.flatMap((k) => {
            const value = r[k];
            return value ? [[k, value] as const] : [];
          }).map(([k, value]) => (
            <li key={k}>
              {MEASURE_LABELS[k]}: {measureText(k, value)}
              {k === "money"
                ? m.finance_confirmed
                  ? ", confirmed by Finance"
                  : ", waiting for Finance"
                : ""}
            </li>
          ))}
          {m.notes ? <li>Notes: {m.notes}</li> : null}
        </ul>
      ) : null}
      <div className="button-row">
        {m.can_confirm ? (
          <button
            type="button"
            className="button"
            disabled={busy}
            onClick={() => run(`${url}/confirm`, {}, "Confirmed.")}
          >
            Confirm these results
          </button>
        ) : null}
        {m.can_finance_confirm ? (
          <button
            type="button"
            className="button button-secondary"
            disabled={busy}
            onClick={() => run(`${url}/finance`, {}, "Finance's confirmation recorded.")}
          >
            Finance has confirmed the money
          </button>
        ) : null}
      </div>
      <Err text={error} />
      {m.can_fill ? <FillForm d={d} m={m} onDone={onDone} /> : null}
    </div>
  );
}

function FillForm({ d, m, onDone }: { d: DeliveryDetail; m: Measurement; onDone: (msg: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const r = m.results;
  const [actual, setActual] = useState(r.metric_actual == null ? "" : String(r.metric_actual));
  const [capex, setCapex] = useState(r.capex_inr == null ? "" : String(r.capex_inr));
  const [opex, setOpex] = useState(r.opex_inr == null ? "" : String(r.opex_inr));
  const [adoption, setAdoption] = useState(r.adoption == null ? "" : String(r.adoption));
  const [notes, setNotes] = useState("");
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(KEYS.map((k) => [k, r[k] ? String(r[k]?.value) : ""])),
  );
  const [units, setUnits] = useState<Record<string, string>>(
    Object.fromEntries(KEYS.map((k) => [k, r[k]?.unit ?? d.options.measure_units[k][0] ?? ""])),
  );
  const legendId = useId();
  function save(e: FormEvent) {
    e.preventDefault();
    const body: Record<string, unknown> = {
      metric_actual: actual,
      capex_inr: capex,
      opex_inr: opex,
      adoption,
    };
    for (const k of KEYS) {
      const v = (values[k] ?? "").trim();
      if (v) body[k] = { value: Number(v), unit: units[k] };
    }
    if (notes.trim()) body.notes = notes.trim();
    void run(
      `/api/delivery/${d.id}/measurements/${m.mark}`,
      body,
      "Results saved. The sponsor is asked to confirm.",
      "PUT",
    );
  }
  return (
    <form className="stack-form" onSubmit={save} noValidate>
      <h3>{m.filled_at ? "Correct the results" : "Fill in the results"}</h3>
      <Field label={`${d.metric ?? "The metric"} now (${d.pack.unit ?? "number"})`}>
        {(id) => (
          <input id={id} inputMode="decimal" value={actual} onChange={(e) => setActual(e.target.value)} />
        )}
      </Field>
      <Field label="One-time cost so far (₹, optional)">
        {(id) => (
          <input id={id} inputMode="numeric" value={capex} onChange={(e) => setCapex(e.target.value)} />
        )}
      </Field>
      <Field label="Running cost a year (₹, optional)">
        {(id) => <input id={id} inputMode="numeric" value={opex} onChange={(e) => setOpex(e.target.value)} />}
      </Field>
      <Field label="People using it (optional)">
        {(id) => (
          <input id={id} inputMode="numeric" value={adoption} onChange={(e) => setAdoption(e.target.value)} />
        )}
      </Field>
      <fieldset className="field" aria-labelledby={legendId}>
        <legend id={legendId}>What it changed (shown with the Ones&apos; impact once confirmed)</legend>
        {KEYS.map((k) => (
          <div key={k} className="choice-row">
            <Field label={`${MEASURE_LABELS[k]} (optional)`}>
              {(id) => (
                <input
                  id={id}
                  inputMode="numeric"
                  value={values[k] ?? ""}
                  onChange={(e) => setValues({ ...values, [k]: e.target.value })}
                />
              )}
            </Field>
            <Select
              label={`${MEASURE_LABELS[k]} unit`}
              value={units[k] ?? ""}
              options={d.options.measure_units[k]}
              onChange={(v) => setUnits({ ...units, [k]: v })}
            />
          </div>
        ))}
      </fieldset>
      <Field label="Notes (optional)">
        {(id) => (
          <textarea
            id={id}
            rows={2}
            maxLength={600}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        )}
      </Field>
      <div className="button-row">
        <button type="submit" className="button" disabled={busy}>
          Save the results
        </button>
      </div>
      <Err text={error} />
    </form>
  );
}
