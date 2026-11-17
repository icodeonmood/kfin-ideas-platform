"use client";

/**
 * The programme team's part of the admin page (lane A; J-ONE steps 1, 2, 3 and 6): choose a build team, mark an idea
 * shipped (L-DECIDE.after), enter the 30- and 90-day figures and confirm money for Finance (L-IMPACT), and look
 * after the Ones (L-ONES admin path, DEC-106). The pack does not draw this page (L-DECIDE.after and L-IMPACT/8
 * OPEN): it is a plain, accessible page. Every action is checked and audited on the server.
 */
import { useCallback, useId, useState } from "react";

import { TIER_NAME } from "@/lib/contracts";

import { send, type Problem } from "./send";
import { WallRemovals, type Removal } from "./wall-removals";

export type IdeaRow = {
  idea_ref: string;
  title: string;
  team: string | null;
  lead: string | null;
  since: string | null;
  since_label: string | null;
};
export type DueRow = {
  id: number;
  idea_ref: string;
  title: string;
  mark: Mark;
  check: string;
  due_at: string;
  due_label: string;
  overdue: boolean;
};
type Figure = { amount: number; unit?: string; line?: string };
export type EnteredRow = {
  id: number;
  idea_ref: string;
  title: string;
  mark: Mark;
  check: string;
  results: { time?: Figure; money?: Figure; effort?: Figure; scale?: Figure; sentence?: string };
  has_money: boolean;
  finance_confirmed: boolean;
  entered_by_me: boolean;
};
export type OneRow = {
  id: number;
  number: number;
  tier: number;
  founding: boolean;
  idea_ref: string | null;
  name: string;
  email: string;
  since: string;
};
export type ProgrammeView = {
  can: { programme: boolean; wall: boolean };
  off_wall: Removal[];
  picked?: IdeaRow[];
  being_built?: IdeaRow[];
  shipped?: IdeaRow[];
  due?: DueRow[];
  entered?: EnteredRow[];
  ones?: OneRow[];
  scale_nouns?: string[];
};
type Mark = "day_30" | "day_90";

const rupees = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const number = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 2 });

export function Programme({ initial }: { initial: ProgrammeView }) {
  const [view, setView] = useState<ProgrammeView>(initial);
  const [message, setMessage] = useState("");
  const reload = useCallback(async (text: string) => {
    setMessage(text);
    const res = await fetch("/api/admin/programme", { cache: "no-store" });
    if (res.ok) setView((await res.json()) as ProgrammeView);
  }, []);

  return (
    <>
      <p role="status" aria-live="polite" className="sr-status">
        {message}
      </p>
      {view.can.programme ? (
        <>
          <BuildTeam picked={view.picked ?? []} onDone={reload} />
          <Shipping beingBuilt={view.being_built ?? []} onDone={reload} />
          <Impact
            shipped={view.shipped ?? []}
            due={view.due ?? []}
            entered={view.entered ?? []}
            nouns={view.scale_nouns ?? []}
            onDone={reload}
          />
          <Ones ones={view.ones ?? []} onDone={reload} />
        </>
      ) : null}
      {view.can.wall ? <WallRemovals removals={view.off_wall} onDone={reload} /> : null}
    </>
  );
}

/** An error under a field: announced, and tied to the field by aria-describedby. */
export function FieldError({ id, problem, field }: { id: string; problem: Problem | null; field: string }) {
  if (!problem || (problem.field ?? "form") !== field) return null;
  return (
    <p id={id} role="alert" className="field-error">
      {problem.message}
    </p>
  );
}

const described = (problem: Problem | null, field: string, id: string) =>
  problem && (problem.field ?? "form") === field
    ? { "aria-invalid": true as const, "aria-describedby": id }
    : {};

// --- J-ONE step 1: choose the build team -------------------------------------------------------------------------

function BuildTeam({ picked, onDone }: { picked: IdeaRow[]; onDone: (m: string) => Promise<void> }) {
  const id = useId();
  const [idea, setIdea] = useState("");
  const [name, setName] = useState("");
  const [lead, setLead] = useState("");
  const [members, setMembers] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);
  const chosen = idea || picked[0]?.idea_ref || "";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const out = await send("POST", `/api/admin/ideas/${chosen}/build-team`, {
      name,
      lead_email: lead,
      member_emails: members,
    });
    if (!out.ok) return setProblem(out.problem);
    setProblem(null);
    setIdea("");
    setName("");
    setLead("");
    setMembers("");
    await onDone(`${chosen} has its build team. It is now being built.`);
  }

  return (
    <section aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>Picked ideas: choose the build team</h2>
      <p className="muted">
        Choose a team and its lead for a picked idea. The idea moves to Being built, and the sharer sees it on
        their track.
      </p>
      {picked.length === 0 ? (
        <p>No picked idea is waiting for a team.</p>
      ) : (
        <form onSubmit={submit} noValidate className="stack-form" aria-labelledby={`${id}-form`}>
          <h3 id={`${id}-form`}>Choose a build team</h3>
          <FieldError id={`${id}-err-form`} problem={problem} field="form" />
          <label htmlFor={`${id}-idea`}>Idea</label>
          <select
            id={`${id}-idea`}
            value={chosen}
            onChange={(e) => setIdea(e.target.value)}
            {...described(problem, "idea", `${id}-err-idea`)}
          >
            {picked.map((p) => (
              <option key={p.idea_ref} value={p.idea_ref}>
                {p.idea_ref}: {p.title}
              </option>
            ))}
          </select>
          <FieldError id={`${id}-err-idea`} problem={problem} field="idea" />
          <label htmlFor={`${id}-name`}>Team name</label>
          <input
            id={`${id}-name`}
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="off"
            {...described(problem, "name", `${id}-err-name`)}
          />
          <FieldError id={`${id}-err-name`} problem={problem} field="name" />
          <label htmlFor={`${id}-lead`}>Lead&apos;s work email</label>
          <input
            id={`${id}-lead`}
            type="email"
            value={lead}
            onChange={(e) => setLead(e.target.value)}
            autoComplete="off"
            {...described(problem, "lead", `${id}-err-lead`)}
          />
          <FieldError id={`${id}-err-lead`} problem={problem} field="lead" />
          <label htmlFor={`${id}-members`}>Other members&apos; work emails</label>
          <p id={`${id}-members-hint`} className="hint">
            Separate them with commas. You can leave this empty.
          </p>
          <input
            id={`${id}-members`}
            value={members}
            onChange={(e) => setMembers(e.target.value)}
            autoComplete="off"
            aria-describedby={
              problem?.field === "members" ? `${id}-members-hint ${id}-err-members` : `${id}-members-hint`
            }
            aria-invalid={problem?.field === "members" ? true : undefined}
          />
          <FieldError id={`${id}-err-members`} problem={problem} field="members" />
          <div className="actions">
            <button type="submit" className="button">
              Choose team
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

// --- J-ONE step 1: mark shipped ------------------------------------------------------------------------------------

function Shipping({ beingBuilt, onDone }: { beingBuilt: IdeaRow[]; onDone: (m: string) => Promise<void> }) {
  const id = useId();
  return (
    <section aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>Being built: mark shipped</h2>
      <p className="muted">
        When the fix is live, mark it shipped. The sharer&apos;s track reaches Shipped, and its 30- and 90-day
        checks are set.
      </p>
      {beingBuilt.length === 0 ? (
        <p>No idea is being built right now.</p>
      ) : (
        <table className="table">
          <caption className="visually-hidden">Ideas being built</caption>
          <thead>
            <tr>
              <th scope="col">Idea</th>
              <th scope="col">Team</th>
              <th scope="col">Lead</th>
              <th scope="col">Being built since</th>
              <th scope="col">Shipped</th>
            </tr>
          </thead>
          <tbody>
            {beingBuilt.map((row) => (
              <tr key={row.idea_ref}>
                <th scope="row">
                  {row.idea_ref}
                  <div className="muted">{row.title}</div>
                </th>
                <td>{row.team ?? "—"}</td>
                <td>{row.lead ?? "—"}</td>
                <td>{row.since_label ?? "—"}</td>
                <td>
                  <ShipButton row={row} onDone={onDone} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function ShipButton({ row, onDone }: { row: IdeaRow; onDone: (m: string) => Promise<void> }) {
  const [asking, setAsking] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const errId = `ship-${row.idea_ref}-err`;
  if (!asking)
    return (
      <button type="button" className="button button-secondary" onClick={() => setAsking(true)}>
        Mark shipped<span className="visually-hidden">: {row.idea_ref}</span>
      </button>
    );
  return (
    <div className="inline-form" role="group" aria-label={`Mark ${row.idea_ref} shipped`}>
      <p>Is it live and in use?</p>
      {problem ? (
        <p id={errId} role="alert" className="field-error">
          {problem.message}
        </p>
      ) : null}
      <div className="actions">
        <button
          type="button"
          className="button"
          onClick={async () => {
            const out = await send("POST", `/api/admin/ideas/${row.idea_ref}/shipped`);
            if (!out.ok) return setProblem(out.problem);
            setAsking(false);
            await onDone(`${row.idea_ref} is shipped. Its 30- and 90-day checks are set.`);
          }}
        >
          Yes, it has shipped
        </button>
        <button type="button" className="button button-secondary" onClick={() => setAsking(false)}>
          Cancel
        </button>
      </div>
    </div>
  );
}

// --- J-ONE steps 2 and 6: the figures, and Finance ----------------------------------------------------------------

type Form = {
  idea: string;
  mark: Mark;
  hours: string;
  hoursLine: string;
  money: string;
  steps: string;
  perWhat: string;
  reach: string;
  noun: string;
  reachLine: string;
  sentence: string;
};
const EMPTY: Form = {
  idea: "",
  mark: "day_30",
  hours: "",
  hoursLine: "",
  money: "",
  steps: "",
  perWhat: "",
  reach: "",
  noun: "",
  reachLine: "",
  sentence: "",
};

function Impact({
  shipped,
  due,
  entered,
  nouns,
  onDone,
}: {
  shipped: IdeaRow[];
  due: DueRow[];
  entered: EnteredRow[];
  nouns: string[];
  onDone: (m: string) => Promise<void>;
}) {
  const id = useId();
  const [form, setForm] = useState<Form>(EMPTY);
  const [problem, setProblem] = useState<Problem | null>(null);
  const set = (key: keyof Form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }));
  const idea = form.idea || shipped[0]?.idea_ref || "";
  const noun = form.noun || nouns[0] || "";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const out = await send("PUT", `/api/admin/ideas/${idea}/measurements/${form.mark}`, {
      time: { amount: form.hours, line: form.hoursLine },
      money: { amount: form.money },
      effort: { amount: form.steps, line: form.perWhat },
      scale: { amount: form.reach, unit: noun, line: form.reachLine },
      sentence: form.sentence,
    });
    if (!out.ok) return setProblem(out.problem);
    setProblem(null);
    setForm(EMPTY);
    const made = (out.json.inducted as unknown[] | undefined)?.length ?? 0;
    const waits = out.json.waits_for_finance === true;
    await onDone(
      `Figures saved for ${idea}.` +
        (waits ? " The money figure shows once someone else confirms it for Finance." : "") +
        (made ? ` ${made === 1 ? "1 person is" : `${made} people are`} now Ones.` : ""),
    );
  }

  const field = (
    key: string,
    label: string,
    value: string,
    onChange: ReturnType<typeof set>,
    hint?: string,
  ) => (
    <>
      <label htmlFor={`${id}-${key}`}>{label}</label>
      {hint ? (
        <p id={`${id}-${key}-hint`} className="hint">
          {hint}
        </p>
      ) : null}
      <input
        id={`${id}-${key}`}
        value={value}
        onChange={onChange}
        inputMode={key.endsWith("amount") ? "decimal" : undefined}
        autoComplete="off"
        aria-invalid={problem?.field === key ? true : undefined}
        aria-describedby={
          [hint ? `${id}-${key}-hint` : "", problem?.field === key ? `${id}-err-${key}` : ""]
            .filter(Boolean)
            .join(" ") || undefined
        }
      />
      <FieldError id={`${id}-err-${key}`} problem={problem} field={key} />
    </>
  );

  return (
    <section aria-labelledby={`${id}-title`} id="impact">
      <h2 id={`${id}-title`}>What shipped ideas changed</h2>
      <p className="muted">
        Each shipped idea is measured 30 and 90 days after it ships. The team that runs the fix sends the
        figures; enter them here. Money shows only after someone else confirms it for Finance.
      </p>
      <h3>Due</h3>
      {due.length === 0 ? (
        <p>Nothing is due.</p>
      ) : (
        <table className="table">
          <caption className="visually-hidden">Measurements due</caption>
          <thead>
            <tr>
              <th scope="col">Idea</th>
              <th scope="col">Check</th>
              <th scope="col">Due</th>
            </tr>
          </thead>
          <tbody>
            {due.map((d) => (
              <tr key={d.id}>
                <th scope="row">
                  {d.idea_ref}
                  <div className="muted">{d.title}</div>
                </th>
                <td>{d.check}</td>
                <td>
                  {d.due_label}
                  {d.overdue ? <strong> (late)</strong> : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {shipped.length === 0 ? null : (
        <form onSubmit={submit} noValidate className="stack-form" aria-labelledby={`${id}-form`}>
          <h3 id={`${id}-form`}>Enter the figures</h3>
          <FieldError id={`${id}-err-form`} problem={problem} field="form" />
          <label htmlFor={`${id}-idea`}>Idea</label>
          <select
            id={`${id}-idea`}
            value={idea}
            onChange={set("idea")}
            {...described(problem, "idea", `${id}-err-idea`)}
          >
            {shipped.map((s) => (
              <option key={s.idea_ref} value={s.idea_ref}>
                {s.idea_ref}: {s.title}
              </option>
            ))}
          </select>
          <FieldError id={`${id}-err-idea`} problem={problem} field="idea" />
          <label htmlFor={`${id}-mark`}>Check</label>
          <select
            id={`${id}-mark`}
            value={form.mark}
            onChange={set("mark")}
            {...described(problem, "mark", `${id}-err-mark`)}
          >
            <option value="day_30">30 days after shipping</option>
            <option value="day_90">90 days after shipping</option>
          </select>
          <FieldError id={`${id}-err-mark`} problem={problem} field="mark" />
          <fieldset>
            <legend>Time saved</legend>
            {field("time.amount", "Hours saved a month", form.hours, set("hours"))}
            {field(
              "time.line",
              "What it means (optional)",
              form.hoursLine,
              set("hoursLine"),
              "For example: Fewer bounced-debit cases",
            )}
          </fieldset>
          <fieldset>
            <legend>Money</legend>
            {field(
              "money.amount",
              "Rupees saved or earned a year",
              form.money,
              set("money"),
              "Shows only after someone else confirms it for Finance.",
            )}
          </fieldset>
          <fieldset>
            <legend>Effort</legend>
            {field("effort.amount", "Steps removed", form.steps, set("steps"))}
            {field(
              "effort.line",
              "Per what (optional)",
              form.perWhat,
              set("perWhat"),
              "For example: Per new mandate",
            )}
          </fieldset>
          <fieldset>
            <legend>Scale</legend>
            {field("scale.amount", "How many use it or are reached by it", form.reach, set("reach"))}
            <label htmlFor={`${id}-noun`}>Who they are</label>
            <select
              id={`${id}-noun`}
              value={noun}
              onChange={set("noun")}
              {...described(problem, "scale.unit", `${id}-err-scale.unit`)}
            >
              {nouns.map((n) => (
                <option key={n} value={n}>
                  {n[0]?.toUpperCase()}
                  {n.slice(1)}
                </option>
              ))}
            </select>
            <FieldError id={`${id}-err-scale.unit`} problem={problem} field="scale.unit" />
            {field(
              "scale.line",
              "How they use it (optional)",
              form.reachLine,
              set("reachLine"),
              "For example: Using it every day",
            )}
          </fieldset>
          {field(
            "sentence",
            "In one plain sentence (optional)",
            form.sentence,
            set("sentence"),
            "For example: 620 hours a month saved; bounced first debits down by a third",
          )}
          <div className="actions">
            <button type="submit" className="button">
              Save the figures
            </button>
          </div>
        </form>
      )}

      <h3>Entered</h3>
      {entered.length === 0 ? (
        <p>No figures entered yet.</p>
      ) : (
        <table className="table">
          <caption className="visually-hidden">Figures entered, newest first</caption>
          <thead>
            <tr>
              <th scope="col">Idea</th>
              <th scope="col">Check</th>
              <th scope="col">Figures</th>
              <th scope="col">Finance</th>
            </tr>
          </thead>
          <tbody>
            {entered.map((m) => (
              <tr key={m.id}>
                <th scope="row">
                  {m.idea_ref}
                  <div className="muted">{m.title}</div>
                </th>
                <td>{m.check}</td>
                <td>
                  <Figures results={m.results} />
                </td>
                <td>
                  <FinanceCell m={m} onDone={onDone} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Figures({ results }: { results: EnteredRow["results"] }) {
  const lines: string[] = [];
  if (results.time) lines.push(`${number.format(results.time.amount)} hours a month`);
  if (results.money) lines.push(`₹${rupees.format(results.money.amount)} a year`);
  if (results.effort) lines.push(`${number.format(results.effort.amount)} fewer steps`);
  if (results.scale) lines.push(`${number.format(results.scale.amount)} ${results.scale.unit ?? ""}`.trim());
  return (
    <ul className="plain-list">
      {lines.map((l) => (
        <li key={l}>{l}</li>
      ))}
    </ul>
  );
}

function FinanceCell({ m, onDone }: { m: EnteredRow; onDone: (t: string) => Promise<void> }) {
  const [problem, setProblem] = useState<Problem | null>(null);
  if (!m.has_money) return <>No money figure</>;
  if (m.finance_confirmed) return <>Confirmed</>;
  if (m.entered_by_me) return <>Waiting. Someone else confirms figures you entered.</>;
  return (
    <>
      <button
        type="button"
        className="button button-secondary"
        onClick={async () => {
          const out = await send("POST", `/api/admin/ideas/${m.idea_ref}/measurements/${m.mark}/finance`);
          if (!out.ok) return setProblem(out.problem);
          const made = (out.json.inducted as unknown[] | undefined)?.length ?? 0;
          await onDone(
            `Finance's confirmation is recorded for ${m.idea_ref}.` +
              (made ? ` ${made === 1 ? "1 person is" : `${made} people are`} now Ones.` : ""),
          );
        }}
      >
        Confirm for Finance
        <span className="visually-hidden">
          : {m.idea_ref}, {m.check}
        </span>
      </button>
      {problem ? (
        <p role="alert" className="field-error">
          {problem.message}
        </p>
      ) : null}
    </>
  );
}

// --- J-ONE step 3: the Ones (Founding Ones, removing a One) -------------------------------------------------------

function Ones({ ones, onDone }: { ones: OneRow[]; onDone: (m: string) => Promise<void> }) {
  const id = useId();
  const [email, setEmail] = useState("");
  const [problem, setProblem] = useState<Problem | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const out = await send("POST", "/api/admin/ones/founding", { email });
    if (!out.ok) return setProblem(out.problem);
    setProblem(null);
    setEmail("");
    await onDone(`Marked as a Founding One, No. ${String(out.json.number)}.`);
  }

  return (
    <section aria-labelledby={`${id}-title`}>
      <h2 id={`${id}-title`}>The Ones</h2>
      <p className="muted">
        People become Ones on their own when an idea they are credited on is measured and confirmed. Here you
        mark Founding Ones and remove a One. Both are recorded with your name and the time.
      </p>
      {ones.length === 0 ? (
        <p>There are no Ones yet.</p>
      ) : (
        <table className="table">
          <caption className="visually-hidden">The Ones, by number</caption>
          <thead>
            <tr>
              <th scope="col">No.</th>
              <th scope="col">Name</th>
              <th scope="col">Tier</th>
              <th scope="col">Idea</th>
              <th scope="col">Remove</th>
            </tr>
          </thead>
          <tbody>
            {ones.map((o) => (
              <tr key={o.id}>
                <th scope="row">No. {o.number}</th>
                <td>
                  {o.name}
                  {o.founding ? <div className="muted">Founding One</div> : null}
                </td>
                <td>
                  Tier {o.tier}, {TIER_NAME[String(o.tier) as keyof typeof TIER_NAME]}
                </td>
                <td>{o.idea_ref ?? "—"}</td>
                <td>
                  <RemoveOne one={o} onDone={onDone} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <form onSubmit={submit} noValidate className="stack-form" aria-labelledby={`${id}-form`}>
        <h3 id={`${id}-form`}>Mark a Founding One</h3>
        <FieldError id={`${id}-err-form`} problem={problem} field="form" />
        <label htmlFor={`${id}-email`}>Work email</label>
        <input
          id={`${id}-email`}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoComplete="off"
          {...described(problem, "email", `${id}-err-email`)}
        />
        <FieldError id={`${id}-err-email`} problem={problem} field="email" />
        <div className="actions">
          <button type="submit" className="button">
            Mark Founding One
          </button>
        </div>
      </form>
    </section>
  );
}

function RemoveOne({ one, onDone }: { one: OneRow; onDone: (m: string) => Promise<void> }) {
  const [asking, setAsking] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const errId = `remove-one-${one.id}-err`;
  if (!asking)
    return (
      <button type="button" className="button button-secondary" onClick={() => setAsking(true)}>
        Remove
        <span className="visually-hidden">
          : No. {one.number}, {one.name}
        </span>
      </button>
    );
  return (
    <div className="inline-form" role="group" aria-label={`Remove No. ${one.number}, ${one.name}`}>
      <p>
        Remove No. {one.number}? Their card and posts leave the Wall, Home and the office screen. The number
        rests for six months.
      </p>
      {problem ? (
        <p id={errId} role="alert" className="field-error">
          {problem.message}
        </p>
      ) : null}
      <div className="actions">
        <button
          type="button"
          className="button"
          onClick={async () => {
            const out = await send("DELETE", `/api/admin/ones/${one.id}`);
            if (!out.ok) return setProblem(out.problem);
            setAsking(false);
            await onDone(`${one.name} is no longer a One. No. ${one.number} rests for six months.`);
          }}
        >
          Yes, remove
        </button>
        <button type="button" className="button button-secondary" onClick={() => setAsking(false)}>
          Cancel
        </button>
      </div>
    </div>
  );
}
