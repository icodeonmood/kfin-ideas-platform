"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState, type FormEvent, type ReactNode } from "react";

import { day } from "@/lib/dates";
import { BANNERS, BECAUSE } from "@/lib/killswitch-routes";
import { measureList } from "@/lib/measures";
import type { ConsoleOne, OnesConsole, Proposal } from "@/server/ones";

type Viewer = {
  id: string;
  chair: boolean;
  committee: boolean;
  ceo: boolean;
  admin: boolean;
  propose: boolean;
};

const TIERS = ["Spark", "Glow", "Flame", "Blaze", "White heat", "Blue flame", "Star"];
const UNITS: Record<string, string[]> = {
  time: ["hours a month", "days a year"],
  money: ["rupees a year", "rupees a month"],
  effort: ["errors avoided a month", "corrections avoided a month", "calls avoided a month"],
  scale: ["investors", "distributors", "colleagues", "transactions a month", "folios a month"],
};
const ERRORS: Record<string, string> = {
  forbidden: "You can't do that from your role.",
  chair_only: "Only the chair can approve alone. Record a meeting majority instead.",
  own_proposal: "Someone else has to do this: it's your own proposal, or about you.",
  not_open: "This has already been decided.",
  not_approved: "This needs the chair's or a meeting's approval first.",
  committee_message_required:
    "The core committee's message for this One is needed before it can be carried out.",
  meeting_date_required: "Please give the date of the meeting.",
  meeting_date_not_valid: "The meeting date must be in the last 90 days, not in the future.",
  person_not_found: "We can't find anyone with that email address.",
  already_a_one: "That person is already a One.",
  already_proposed: "There is already an open proposal like this for that person.",
  idea_not_theirs: "That idea isn't theirs, or the idea ID is wrong.",
  tier_not_valid: "Pick a tier above (for a tier up) or below (for a tier down) their current tier.",
  already_a_legend: "Their number is already retired in their honour.",
  legend_this_year: "A legend number has already been retired this year.",
  nothing_to_announce: "Everyone inducted has already been announced.",
  award_given: "That award has already been given this year.",
  personal_data: "Please take out any personal details (numbers, addresses, investor names).",
  text_needs_review: "Please reword this: it reads as off-topic or unkind, so we can't save it as it is.",
  names_not_allowed: "Leave out the names of colleagues and clients: everyone will see this.",
  try_again: "Someone else took that number in the same moment. Please try again.",
  ones_paused: `${BANNERS["ones.public"]} ${BECAUSE.announcementWaitsForOnes}`,
  paused: "This is paused for now. Please try again later.",
  text_too_short: "Please write at least a short sentence.",
  text_too_long: "That's too long. Please shorten it.",
  checks_unavailable: "We can't check text just now. Please try again in a few minutes.",
  not_invited: "Only invited colleagues can write a message.",
  already_written: "You've already written a message for this.",
};

async function send(url: string, body: Record<string, unknown>, method = "POST"): Promise<string | null> {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).catch(() => null);
  if (res?.ok) return null;
  const code = res ? String(((await res.json().catch(() => ({}))) as { error?: string }).error ?? "") : "";
  return ERRORS[code] ?? "That didn't work. Please try again.";
}

function useAction(onDone: (message: string) => void) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function run(url: string, body: Record<string, unknown>, done: string, method = "POST") {
    if (busy) return false;
    setBusy(true);
    const err = await send(url, body, method);
    setBusy(false);
    setError(err ?? "");
    if (!err) onDone(done);
    return !err;
  }
  return { error, busy, run };
}

function Err({ text }: { text: string }) {
  return text ? (
    <p className="field-error" role="alert">
      {text}
    </p>
  ) : null;
}

function TextField({
  label,
  hint,
  value,
  onChange,
  rows = 2,
}: {
  label: string;
  hint?: string;
  value: string;
  onChange: (v: string) => void;
  rows?: number;
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
      <textarea
        id={id}
        rows={rows}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-describedby={hint ? `${id}-hint` : undefined}
      />
    </div>
  );
}

export function OnesConsoleView({ data, viewer }: { data: OnesConsole; viewer: Viewer }) {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const done = (message: string) => {
    setStatus(message);
    router.refresh();
  };
  const open = data.proposals.filter((p) => p.state === "proposed" || p.state === "approved");
  const closed = data.proposals.filter((p) => !(p.state === "proposed" || p.state === "approved"));
  const unannounced = data.ones.filter((o) => o.status === "active" && !o.announced).length;
  return (
    <div className="console-grid">
      <div>
        <h1>Ones</h1>
        <p className="lead">
          {data.active} active. The last number the system gave was {data.last_allocated || "none yet"}.
          {data.resting.length
            ? ` Resting: ${data.resting.map((r) => `No. ${r.number} until ${day(r.until)}`).join(", ")}.`
            : ""}
        </p>
        <p className="coming-soon coming-soon-light">Automatic tiers and lapse proposals: coming soon</p>
        <p role="status" aria-live="polite" className="sr-status">
          {status}
        </p>
      </div>

      <section aria-labelledby="c-waiting">
        <h2 id="c-waiting">Waiting on someone</h2>
        {open.length ? (
          <ul className="crew-cards" style={{ listStyle: "none", padding: 0 }}>
            {open.map((p) => (
              <ProposalCard key={p.id} p={p} viewer={viewer} onDone={done} />
            ))}
          </ul>
        ) : (
          <p className="muted">Nothing is waiting.</p>
        )}
      </section>

      {viewer.propose ? <ProposeForm onDone={done} /> : null}

      <section aria-labelledby="c-roster">
        <h2 id="c-roster">The roster</h2>
        <div className="table-wrap">
          <table className="table">
            <caption className="visually-hidden">Every One, active first</caption>
            <thead>
              <tr>
                <th scope="col">No.</th>
                <th scope="col">Name</th>
                <th scope="col">Way in</th>
                <th scope="col">Tier</th>
                <th scope="col">Since</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.ones.map((o) => (
                <RosterRow key={o.id} o={o} viewer={viewer} onDone={done} />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {viewer.admin ? (
        <section aria-labelledby="c-admin">
          <h2 id="c-admin">Screens and announcements</h2>
          <AdminTools mode={data.screen_mode} unannounced={unannounced} onDone={done} />
        </section>
      ) : null}

      <section aria-labelledby="c-night">
        <h2 id="c-night">The Ones Night</h2>
        <p className="muted">
          Every 20 November: tier-ups announced, impact awards for time, money, effort and scale, and one
          legend number retired for good.
        </p>
        {data.awards.length ? (
          <ul>
            {data.awards.map((a) => (
              <li key={`${a.year}-${a.category}`}>
                {a.year}, {a.category}: {a.name}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No awards marked yet.</p>
        )}
        {data.legends.length ? (
          <p>Legend numbers: {data.legends.map((l) => `No. ${l.number}`).join(", ")}</p>
        ) : null}
      </section>

      {closed.length ? (
        <section aria-labelledby="c-closed">
          <h2 id="c-closed">Recently decided</h2>
          <ul>
            {closed.map((p) => (
              <li key={p.id}>
                {p.kind_words} for {p.subject ?? "a One"}: {STATE_WORDS[p.state]}
                {p.decided_at ? ` on ${day(p.decided_at)}` : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

const STATE_WORDS: Record<Proposal["state"], string> = {
  proposed: "waiting for the chair or a meeting majority",
  approved: "approved, waiting for the admin member",
  declined: "declined",
  carried_out: "carried out",
  withdrawn: "withdrawn",
};

function ProposalCard({ p, viewer, onDone }: { p: Proposal; viewer: Viewer; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const [meeting, setMeeting] = useState("");
  const [message, setMessage] = useState("");
  const [peer, setPeer] = useState("");
  const dateId = useId();
  const peerId = useId();
  const tierChange = p.kind === "tier_up" || p.kind === "tier_down";
  const mine = p.proposed_by_id === viewer.id;
  const url = `/api/ones/proposals/${p.id}`;
  const approved =
    p.approval === "chair" ? `the chair (${p.decided_by})` : `a meeting majority on ${p.meeting_on}`;
  return (
    <li className="proposal">
      <p className="meta">
        {p.kind_words}
        {p.way_in ? `, ${p.way_in.toLowerCase()}` : ""}.{" "}
        {p.state === "proposed"
          ? "Needs the chair or a meeting majority"
          : `Approved by ${approved}. Ready for the admin member`}
      </p>
      <h3>
        {p.subject}
        {tierChange && p.tier_to ? `: Tier ${p.tier_from} to Tier ${p.tier_to}, ${p.tier_to_name}` : ""}
      </h3>
      {p.text ? <p>{p.kind === "impact_brief" ? `Brief: ${p.text}` : `What they built: ${p.text}`}</p> : null}
      {p.idea_id ? <p>Idea: {p.idea_id}</p> : null}
      {p.reason ? <p>&quot;{p.reason}&quot;</p> : null}
      <p className="meta">
        Proposed by {p.proposed_by} on {day(p.proposed_at)}
      </p>
      {tierChange ? (
        <p className="meta">
          Messages:{" "}
          {p.messages.length ? p.messages.map((m) => `${m.from} (${m.name})`).join(", ") : "none yet"}.
          {p.invited.length ? ` Invited: ${p.invited.join(", ")}.` : ""}
          {!p.committee_message ? " The committee's message is still needed." : ""}
        </p>
      ) : null}
      {p.kind === "remove" ? (
        <p className="preview">
          Message preview: &quot;Thank you, {p.subject?.split(" ")[0]}. The core committee has closed your
          membership. Your number rests for six months, and a new idea can bring you back.&quot;
        </p>
      ) : null}

      {p.state === "proposed" && (viewer.chair || viewer.committee) ? (
        <div className="button-row">
          {viewer.chair && !mine ? (
            <>
              <button
                type="button"
                className="button"
                disabled={busy}
                onClick={() => run(`${url}/decide`, { verdict: "approve", how: "chair" }, "Approved.")}
              >
                Approve as chair
              </button>
              <button
                type="button"
                className="button button-secondary"
                disabled={busy}
                onClick={() => run(`${url}/decide`, { verdict: "decline", how: "chair" }, "Declined.")}
              >
                Decline as chair
              </button>
            </>
          ) : null}
          {viewer.committee ? (
            <form
              className="inline-form"
              onSubmit={(e: FormEvent) => {
                e.preventDefault();
                void run(
                  `${url}/decide`,
                  { verdict: "approve", how: "majority", meeting_on: meeting },
                  "Majority recorded.",
                );
              }}
            >
              <label htmlFor={dateId}>Meeting date</label>
              <input id={dateId} type="date" value={meeting} onChange={(e) => setMeeting(e.target.value)} />
              <button type="submit" className="button button-secondary" disabled={busy}>
                Record a meeting majority
              </button>
            </form>
          ) : null}
        </div>
      ) : null}

      {tierChange && (viewer.committee || viewer.ceo) && p.state !== "carried_out" ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void run(
              `${url}/messages`,
              { from: viewer.committee ? "committee" : "ceo", text: message },
              "Message saved.",
            ).then((ok) => ok && setMessage(""));
          }}
        >
          <TextField
            label={
              viewer.committee
                ? "The committee's message to them (required)"
                : "Your message to them (optional)"
            }
            hint="They read it in their glow-up and in the email. No personal details."
            value={message}
            onChange={setMessage}
          />
          <button type="submit" className="button button-secondary" disabled={busy}>
            Save the message
          </button>
        </form>
      ) : null}

      {tierChange && viewer.committee && p.state !== "carried_out" ? (
        <form
          className="inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            void run(`${url}/invites`, { email: peer }, "Colleague invited.").then((ok) => ok && setPeer(""));
          }}
        >
          <label htmlFor={peerId}>Invite a colleague to write (email)</label>
          <input id={peerId} type="email" value={peer} onChange={(e) => setPeer(e.target.value)} />
          <button type="submit" className="button button-secondary" disabled={busy}>
            Invite
          </button>
        </form>
      ) : null}

      {p.state === "approved" && viewer.admin ? (
        <div className="button-row">
          <button
            type="button"
            className="button"
            disabled={busy || (tierChange && !p.committee_message)}
            onClick={() => run(`${url}/carry-out`, {}, "Carried out. The message is on its way.")}
          >
            Carry out and send
          </button>
          {tierChange && !p.committee_message ? (
            <p className="hint">Waiting for the committee&apos;s message.</p>
          ) : null}
        </div>
      ) : null}

      {mine ? (
        <button
          type="button"
          className="link-button"
          disabled={busy}
          onClick={() => run(`${url}/withdraw`, {}, "Withdrawn.")}
        >
          Withdraw this proposal
        </button>
      ) : null}
      <Err text={error} />
    </li>
  );
}

function ProposeForm({ onDone }: { onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const [email, setEmail] = useState("");
  const [wayIn, setWayIn] = useState("sponsored");
  const [ideaId, setIdeaId] = useState("");
  const [title, setTitle] = useState("");
  const [reason, setReason] = useState("");
  const emailId = useId();
  const ideaFieldId = useId();
  return (
    <section aria-labelledby="c-propose">
      <h2 id="c-propose">Propose a One</h2>
      <form
        className="stack-form"
        onSubmit={(e) => {
          e.preventDefault();
          void run(
            "/api/ones/proposals",
            { kind: "include", email, way_in: wayIn, idea_id: ideaId, title, reason },
            "Proposed. It now needs the chair or a meeting majority.",
          ).then((ok) => {
            if (ok) {
              setEmail("");
              setIdeaId("");
              setTitle("");
              setReason("");
            }
          });
        }}
      >
        <div>
          <label htmlFor={emailId}>Their work email</label>
          <input
            id={emailId}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <fieldset className="field">
          <legend>Way in</legend>
          {(
            [
              ["sponsored", "Sponsored: you vouch for work they did"],
              ["founding", "Founding One: past work KFintech already shipped"],
              ["accepted_idea", "Accepted idea: the committee accepted it after their presentation"],
            ] as const
          ).map(([value, label]) => (
            <label key={value} className="choice">
              <input
                type="radio"
                name="way_in"
                value={value}
                checked={wayIn === value}
                onChange={() => setWayIn(value)}
              />
              {label}
            </label>
          ))}
        </fieldset>
        {wayIn === "accepted_idea" ? (
          <div>
            <label htmlFor={ideaFieldId}>Idea ID</label>
            <input
              id={ideaFieldId}
              value={ideaId}
              onChange={(e) => setIdeaId(e.target.value)}
              placeholder="IDEA-2026-000123"
            />
          </div>
        ) : (
          <TextField label="What they built, in one line" value={title} onChange={setTitle} rows={1} />
        )}
        <TextField
          label="Citation"
          hint="Why they belong in the 1% Club, in a sentence or two. No personal details."
          value={reason}
          onChange={setReason}
        />
        <div className="actions">
          <button type="submit" className="button" disabled={busy}>
            Propose
          </button>
        </div>
        <Err text={error} />
      </form>
    </section>
  );
}

function RosterRow({ o, viewer, onDone }: { o: ConsoleOne; viewer: Viewer; onDone: (m: string) => void }) {
  const status =
    o.status === "retired"
      ? `Retired ${o.retired_at ? day(o.retired_at) : ""}`
      : o.lapsed
        ? `Lapsed on ${day(o.lapses_on)}`
        : "Active";
  return (
    <tr>
      <td>{o.number ?? "–"}</td>
      <td>
        {o.name}
        {o.brief ? <div className="muted">{o.brief}</div> : null}
      </td>
      <td>{o.way_in}</td>
      <td>
        <span className="swatch" style={{ background: o.tier_colour }} aria-hidden="true" />
        {o.tier}, {o.tier_name}
        {o.legend_number ? ". Legend number" : ""}
      </td>
      <td>{day(o.since)}</td>
      <td>{status}</td>
      <td>
        {o.status === "active" ? (
          <details>
            <summary>Actions for {o.name}</summary>
            <OneActions o={o} viewer={viewer} onDone={onDone} />
          </details>
        ) : null}
        <Link href={`/ones/showcase/${o.id}`}>
          Showcase brief{o.showcase_updated ? "" : " (not started)"}
        </Link>
      </td>
    </tr>
  );
}

function OneActions({ o, viewer, onDone }: { o: ConsoleOne; viewer: Viewer; onDone: (m: string) => void }) {
  const { error, busy, run } = useAction(onDone);
  const [kind, setKind] = useState<"remove" | "tier_up" | "tier_down" | "legend">("tier_up");
  const [tierTo, setTierTo] = useState(String(Math.min(7, o.tier + 1)));
  const [reason, setReason] = useState("");
  const [measures, setMeasures] = useState<
    Record<string, { value: string; unit: string; finance_confirmed?: boolean }>
  >(
    Object.fromEntries(
      Object.keys(UNITS).map((k) => {
        const m = o.measures[k as keyof typeof o.measures];
        return [
          k,
          {
            value: m ? String(m.value) : "",
            unit: m?.unit ?? UNITS[k]![0]!,
            finance_confirmed: m?.finance_confirmed,
          },
        ];
      }),
    ),
  );
  const [award, setAward] = useState("time");
  const kindId = useId();
  const tierId = useId();
  const awardId = useId();
  const blocks: ReactNode[] = [];
  if (viewer.committee) {
    blocks.push(
      <form
        key="propose"
        className="stack-form"
        onSubmit={(e) => {
          e.preventDefault();
          const body: Record<string, unknown> = { kind, one_id: o.id, reason };
          if (kind === "tier_up" || kind === "tier_down") body.tier_to = Number(tierTo);
          void run("/api/ones/proposals", body, "Proposed.").then((ok) => ok && setReason(""));
        }}
      >
        <label htmlFor={kindId}>Propose</label>
        <select id={kindId} value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
          <option value="tier_up">A tier up</option>
          <option value="tier_down">A tier down</option>
          <option value="remove">Removal</option>
          <option value="legend">Retiring their number as a legend</option>
        </select>
        {kind === "tier_up" || kind === "tier_down" ? (
          <>
            <label htmlFor={tierId}>New tier</label>
            <select id={tierId} value={tierTo} onChange={(e) => setTierTo(e.target.value)}>
              {TIERS.map((name, i) => (
                <option key={name} value={i + 1}>
                  {i + 1}, {name}
                </option>
              ))}
            </select>
          </>
        ) : null}
        <TextField
          label="Reason"
          hint="It goes with the proposal, and to them for a removal."
          value={reason}
          onChange={setReason}
        />
        <button type="submit" className="button button-secondary" disabled={busy}>
          Propose
        </button>
      </form>,
    );
  }
  if (viewer.admin) {
    blocks.push(
      <form
        key="measures"
        className="stack-form"
        onSubmit={(e) => {
          e.preventDefault();
          const out: Record<string, unknown> = {};
          for (const [k, m] of Object.entries(measures)) {
            if (m.value.trim())
              out[k] = {
                value: Number(m.value),
                unit: m.unit,
                finance_confirmed: m.finance_confirmed === true,
              };
          }
          void run(`/api/ones/${o.id}/measures`, { measures: out }, "Measures saved.", "PUT");
        }}
      >
        <h3>Measured impact</h3>
        {Object.keys(UNITS).map((k) => (
          <MeasureRow
            key={k}
            name={k}
            m={measures[k]!}
            onChange={(m) => setMeasures((x) => ({ ...x, [k]: m }))}
          />
        ))}
        <p className="hint">
          Now:{" "}
          {measureList(o.measures)
            .map(([l, w]) => `${l}: ${w}`)
            .join(". ") || "nothing measured yet"}
          .
        </p>
        <button type="submit" className="button button-secondary" disabled={busy}>
          Save measures
        </button>
      </form>,
      <form
        key="award"
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          void run(`/api/ones/${o.id}/awards`, { category: award }, "Award marked.");
        }}
      >
        <label htmlFor={awardId}>The Ones Night award</label>
        <select id={awardId} value={award} onChange={(e) => setAward(e.target.value)}>
          <option value="time">Time</option>
          <option value="money">Money</option>
          <option value="effort">Effort</option>
          <option value="scale">Scale</option>
        </select>
        <button type="submit" className="button button-secondary" disabled={busy}>
          Mark the award
        </button>
      </form>,
    );
  }
  return (
    <div className="stack-form">
      {blocks.length ? blocks : <p className="muted">Nothing for your role here.</p>}
      <Err text={error} />
    </div>
  );
}

function MeasureRow({
  name,
  m,
  onChange,
}: {
  name: string;
  m: { value: string; unit: string; finance_confirmed?: boolean };
  onChange: (m: { value: string; unit: string; finance_confirmed?: boolean }) => void;
}) {
  const id = useId();
  const label = name[0]!.toUpperCase() + name.slice(1);
  return (
    <div className="inline-form">
      <label htmlFor={`${id}-v`}>{label}</label>
      <input
        id={`${id}-v`}
        inputMode="numeric"
        value={m.value}
        onChange={(e) => onChange({ ...m, value: e.target.value.replace(/[^0-9]/g, "") })}
        style={{ maxWidth: "9rem" }}
      />
      <label htmlFor={`${id}-u`} className="visually-hidden">
        {label} unit
      </label>
      <select id={`${id}-u`} value={m.unit} onChange={(e) => onChange({ ...m, unit: e.target.value })}>
        {UNITS[name]!.map((u) => (
          <option key={u}>{u}</option>
        ))}
      </select>
      {name === "money" ? (
        <label>
          <input
            type="checkbox"
            checked={m.finance_confirmed === true}
            onChange={(e) => onChange({ ...m, finance_confirmed: e.target.checked })}
          />{" "}
          Finance confirmed
        </label>
      ) : null}
    </div>
  );
}

function AdminTools({
  mode,
  unannounced,
  onDone,
}: {
  mode: string;
  unannounced: number;
  onDone: (m: string) => void;
}) {
  const { error, busy, run } = useAction(onDone);
  return (
    <div className="stack-form">
      <p>
        Office screens show the {mode === "ambient" ? "ambient" : "static"} sky.{" "}
        <button
          type="button"
          className="button button-secondary"
          disabled={busy}
          onClick={() =>
            run(
              "/api/ones/screen-mode",
              { mode: mode === "ambient" ? "static" : "ambient" },
              "Screen mode changed.",
              "PUT",
            )
          }
        >
          {mode === "ambient" ? "Back to the static sky" : "Switch to ambient mode"}
        </button>{" "}
        <Link href="/constellation">Open the screen</Link>
      </p>
      <p>
        {unannounced
          ? `${unannounced} new ${unannounced === 1 ? "One hasn't" : "Ones haven't"} been announced yet.`
          : "Everyone is announced."}{" "}
        <button
          type="button"
          className="button"
          disabled={busy || !unannounced}
          onClick={() => run("/api/ones/announce", {}, "Announced to everyone.")}
        >
          Announce new Ones
        </button>
      </p>
      <Err text={error} />
    </div>
  );
}
