"use client";

/**
 * S-H2B inside C-INBOX-READER: a team-up or merge request open in the lead's Inbox. The request (the note in full,
 * any idea brought) is read from lane F's `GET /api/team-up/:id` when the item opens, never carried by the item
 * (L-NOTIFY/3); the answer goes to lane F's `POST /api/team-up/:id/answer`, which tells the requester and takes the
 * item off "Needs you". Words: CrewRequest.md, with the board's she/her as the requester's first name or "their"
 * (BLD-E008, listed for HR in BLD-A207); lane F's own words when its response carries them.
 */
import Link from "next/link";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { IDEA_STATUS_LABEL, type IdeaStatus } from "@/lib/contracts";
import type { Action, InboxEntry } from "@/server/inbox";

type Answer = "decline" | "team_only" | "merge";

type Brought = {
  id: string;
  title: string;
  status: IdeaStatus;
  summary?: string;
  byline?: string;
};

/** Lane F's own words for the lead's reader (`GET /team-up/:id` `reader`, BLD-F015); ours when it sends none. */
type Words = { note_heading?: string; brought_heading?: string; open_label?: string; explain?: string };

/** How a request ended, as the reader shows it in place (S-H2B.states). `state` picks the bar: "Say hello" after
 * an approval, "Next" after a decline, nothing once the requester withdrew or the idea closed. */
export type Result = {
  state: string;
  text: string;
  sayHello?: { label: string; to: string };
};

export type Request = {
  id: string;
  note: string;
  /** What the lead may read of what was brought: items with a title only (BLD-F022). */
  brought: Brought[];
  /** How many items lane F listed, the shrunken ones too: its words count them. */
  listed: number;
  /** E-ENUMS.teamup: sent, approved_team_only, approved_merged, declined, withdrawn, closed. */
  state: string;
  words: Words;
  /** An answered request shows its result in place (S-H2B.states). */
  answered: Result | null;
  /** The lead's own reason, when they declined with one. */
  reason?: string;
};

export type RequestView = { body: ReactNode; bar: ReactNode };

const NOT_FOUND = "We couldn’t find that.";
const CANT_SHOW = "We can't show this request just now. Please try again in a minute.";
const CANT_SEND = "We couldn't send that just now. Please try again in a minute.";

/** The answer an item's op stands for: the bare `merge` lane F registers (BLD-A188), or `teamup.answer.merge`. */
export function answerOf(op: string | undefined): Answer | null {
  const last = (op ?? "").split(".").pop();
  return last === "decline" || last === "team_only" || last === "merge" ? last : null;
}

function firstName(item: InboxEntry): string {
  return item.from === "system" ? "" : item.from.first_name || item.from.name.split(" ")[0] || "";
}

function btnClass(style: Action["style"]): string {
  return `btn ${style === "primary" ? "btn-primary" : style === "text" ? "btn-quiet" : "btn-secondary"}`;
}

function Bar({ children }: { children: ReactNode }) {
  return (
    <div className="ibx-bar">
      <div className="ibx-bar-in">{children}</div>
    </div>
  );
}

function text(v: unknown): string | undefined {
  return typeof v === "string" ? v : undefined;
}

function errorOf(body: unknown): { code?: string; message?: string } {
  const e = (body as { error?: { code?: unknown; message?: unknown } } | null)?.error;
  return { code: text(e?.code), message: text(e?.message) || undefined };
}

/** What was brought, as the lead may read it: an item lane F shrank to `{id, title: "", status}` (a draft no longer
 * waiting, or an idea its sharer withdrew, BLD-F022) is not shown at all. */
export function readBrought(raw: unknown): Brought[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((b: Record<string, unknown>) =>
    typeof b?.id === "string" && typeof b.title === "string" && b.title.trim()
      ? [
          {
            id: b.id,
            title: b.title,
            status: b.status as IdeaStatus,
            summary: text(b.summary),
            byline: text(b.byline),
          },
        ]
      : [],
  );
}

function readResult(result: unknown, hello: unknown, state = ""): Result | null {
  const r = result as { text?: unknown; state?: unknown } | null;
  if (typeof r?.text !== "string" || !r.text) return null;
  const h = hello as { label?: unknown; to?: unknown } | null;
  return {
    state: text(r.state) ?? state,
    text: r.text,
    sayHello:
      typeof h?.label === "string" && typeof h.to === "string" ? { label: h.label, to: h.to } : undefined,
  };
}

/** Lane F's `GET /api/team-up/:id` body (f/teamup-4) as the reader uses it. */
export function readRequest(data: unknown, requestId: string): Request {
  const top = (data ?? {}) as Record<string, unknown>;
  // `request` is lane F's kind ("teamup" or "merge"); an older shape nested the request under it.
  const r = (typeof top.request === "object" && top.request ? top.request : top) as Record<string, unknown>;
  const words = (typeof r.reader === "object" && r.reader ? r.reader : {}) as Words;
  const state = text(r.state) ?? "sent";
  return {
    id: String(r.id ?? requestId),
    note: text(r.note) ?? "",
    brought: readBrought(r.brought),
    listed: Array.isArray(r.brought) ? r.brought.length : 0,
    state,
    words,
    answered: readResult(r.result, r.say_hello, state),
    reason: text(r.lead_reason) || undefined,
  };
}

/** A request that could not be read: a 404 says lane F's "We couldn’t find that." and offers no retry. */
export function loadFailure(status: number, body: unknown): string {
  return status === 404 ? (errorOf(body).message ?? NOT_FOUND) : CANT_SHOW;
}

function quoted(reason: string): string {
  return `“${reason}”${/[.!?]$/.test(reason.trimEnd()) ? "" : "."}`;
}

/**
 * The line a request that is no longer waiting shows in place. Lane F's result line when its response has one;
 * otherwise S-H2B.states (CrewRequest.md) in BLD-E008's words, and lane F's own words for a request the requester
 * withdrew or an idea that closed (its `not_waiting` and `idea_closed` lines).
 */
export function endedLine(req: Request, first: string): Result | null {
  if (req.answered) return req.answered;
  const who = first || "They";
  const brings = req.brought.length > 0;
  switch (req.state) {
    case "approved_merged":
      return {
        state: "merged",
        text: `Merged. ${first ? `${first}’s` : "Their"} idea is now part of yours, and they are on your crew, credited. We’ve told them.`,
      };
    case "approved_team_only":
      return {
        state: "teamed_up",
        text: brings
          ? `Teamed up. ${who} is on your crew. Their idea stays separate, and they send it on its own. We’ve told them.`
          : `Teamed up. ${who} is on your crew. We’ve told them.`,
      };
    case "declined":
      return {
        state: "declined",
        text: `Declined. ${req.reason ? `${who} sees your reason: ${quoted(req.reason)}` : `We’ve told ${first || "them"}.`}${brings ? " They can send theirs on its own." : ""}`,
      };
    case "withdrawn":
      return { state: "withdrawn", text: `${who} withdrew this request.` };
    case "closed":
      return { state: "closed", text: "This idea is no longer open to team up." };
    default:
      return null;
  }
}

/** A refused answer. The request ended while it was open (409 `not_waiting`: the requester withdrew it, or its
 * draft was sent or archived, BLD-F024; `idea_closed`): it ends in place with lane F's line. Anything else is an
 * error the lead can try again. */
export function refusedAnswer(
  status: number,
  body: unknown,
  first: string,
): { ended: Result } | { error: string } {
  const { code, message } = errorOf(body);
  if (status === 409 && code === "not_waiting") {
    return { ended: { state: "withdrawn", text: message ?? `${first || "They"} withdrew this request.` } };
  }
  if (status === 409 && code === "idea_closed") {
    return { ended: { state: "closed", text: message ?? "This idea is no longer open to team up." } };
  }
  return { error: message ?? CANT_SEND };
}

export type AnswerButton = { answer: Answer; label: string; style: Action["style"] };

/** The item's answers in footer order. With nothing brought there is nothing to merge: "Decline" and "Approve"
 * (S-H2B.rules/3), whatever the item offered when it was sent. */
export function answerButtons(actions: Action[], brings: boolean): AnswerButton[] {
  return actions.flatMap((a) => {
    const answer = answerOf(a.op);
    if (!answer || (!brings && answer === "merge")) return [];
    if (!brings && answer === "team_only") return [{ answer, label: "Approve", style: "primary" as const }];
    return [{ answer, label: a.label, style: a.style }];
  });
}

/** The words over the request: the note, anything brought, and while it waits the explanation of the answers. */
export function RequestBody({
  req,
  failure,
  first,
  waiting,
  shown,
  declining,
  reason,
  onReason,
  error,
}: {
  req: Request | null;
  failure: string;
  first: string;
  waiting: boolean;
  shown: Result | null;
  declining: boolean;
  reason: string;
  onReason: (value: string) => void;
  error: string;
}) {
  const brought = req?.brought ?? [];
  // Lane F's words count every item it listed; they fit only when every one of them is shown.
  const w: Words =
    req && req.listed === brought.length ? req.words : { note_heading: req?.words.note_heading };
  const many = brought.length > 1;
  return (
    <div className="ibx-req">
      {failure ? <p className="ibx-foot">{failure}</p> : null}
      {req ? (
        <>
          <h3 className="ibx-sh">{w.note_heading ?? (first ? `${first}’s note` : "The note")}</h3>
          <p className="ibx-note">{req.note}</p>
          {brought.length ? (
            <>
              <h3 className="ibx-sh">
                {w.brought_heading ??
                  `${many ? "The ideas" : "The idea"} ${first || "they"} asks you to merge into yours`}
              </h3>
              {brought.map((b) => (
                <div key={b.id} className="ibx-card">
                  {IDEA_STATUS_LABEL[b.status] ? (
                    <span className="ibx-pill">{IDEA_STATUS_LABEL[b.status]}</span>
                  ) : null}
                  <p className="ibx-ct">{b.title}</p>
                  {b.byline ? <p className="ibx-cm">{b.byline}</p> : null}
                  {b.summary ? <p className="ibx-cs">{b.summary}</p> : null}
                  <Link className="ibx-cl" href={`/ideas/${b.id}`}>
                    {w.open_label ?? (first ? `Open ${first}’s idea` : "Open the idea")}
                  </Link>
                </div>
              ))}
            </>
          ) : null}
          {waiting ? (
            <p className="ibx-foot">
              {w.explain ??
                (brought.length
                  ? `Merge it, and their idea joins yours: ${first} is on your crew and credited on it. Team up only puts ${first} on your crew and keeps their idea separate. Decline, and ${first} sends theirs on its own, with your reason if you give one.`
                  : `Approve, and ${first} joins your crew. Decline, and they see your reason if you give one.`)}
            </p>
          ) : null}
          {declining && waiting ? (
            <div className="ibx-field">
              <label htmlFor="ibx-reason">Tell {first || "them"} why, if you like</label>
              <textarea id="ibx-reason" rows={3} value={reason} onChange={(e) => onReason(e.target.value)} />
            </div>
          ) : null}
        </>
      ) : null}
      {shown?.text ? (
        <p className="ibx-result" role="status">
          {shown.text}
        </p>
      ) : null}
      {error ? (
        <p className="ibx-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** The request view for the open item, or null when the item is not a request the lead can answer here. */
export function useRequest(
  item: InboxEntry | null,
  onAnswered: (item: InboxEntry) => void | Promise<void>,
  onNext: () => void,
): RequestView | null {
  const requestId = item?.kind === "teamup_request" ? item.body.request_id : undefined;
  const [req, setReq] = useState<Request | null>(null);
  const [failure, setFailure] = useState("");
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState("");
  const [outcome, setOutcome] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Once per item: the reader keys the open item, so each request starts from nothing.
  useEffect(() => {
    if (!requestId) return;
    let live = true;
    void fetch(`/api/team-up/${encodeURIComponent(requestId)}`, { cache: "no-store" })
      .then(async (res) => {
        const data: unknown = await res.json().catch(() => null);
        if (!live) return;
        if (res.ok) setReq(readRequest(data, requestId));
        else setFailure(loadFailure(res.status, data));
      })
      .catch(() => live && setFailure(CANT_SHOW));
    return () => {
      live = false;
    };
  }, [requestId]);

  const send = useCallback(
    async (answer: Answer) => {
      if (!item || !requestId) return;
      setBusy(true);
      setError("");
      const res = await fetch(`/api/team-up/${encodeURIComponent(requestId)}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          answer === "decline" && reason.trim() ? { answer, reason: reason.trim() } : { answer },
        ),
      }).catch(() => null);
      setBusy(false);
      const data: unknown = await res?.json().catch(() => null);
      if (!res?.ok) {
        const refused = refusedAnswer(res?.status ?? 0, data, firstName(item));
        if ("error" in refused) {
          setError(refused.error);
          return;
        }
        // It ended while it was open: shown in place, nothing brought is read any more, and the item has left
        // "Needs you" (lane F resolved it), so every count is fetched again and the shell hears it.
        setOutcome(refused.ended);
        setReq((r) => (r ? { ...r, state: refused.ended.state, brought: [] } : r));
        setDeclining(false);
        await onAnswered(item);
        return;
      }
      const body = data as { result?: unknown; say_hello?: unknown } | null;
      setOutcome(readResult(body?.result, body?.say_hello, answer) ?? { state: answer, text: "" });
      setDeclining(false);
      await onAnswered(item);
    },
    [item, requestId, reason, onAnswered],
  );

  if (!item || !requestId) return null;
  const first = firstName(item);
  const shown = outcome ?? (req ? endedLine(req, first) : null);
  const waiting = req?.state === "sent" && !shown;
  const buttons = answerButtons(item.actions, (req?.brought.length ?? 0) > 0);

  const body = (
    <RequestBody
      req={req}
      failure={failure}
      first={first}
      waiting={waiting}
      shown={shown}
      declining={declining}
      reason={reason}
      onReason={setReason}
      error={error}
    />
  );

  let bar: ReactNode = null;
  if (shown?.sayHello) {
    bar = (
      <Bar>
        <Link className="btn btn-primary" href={shown.sayHello.to}>
          {shown.sayHello.label}
        </Link>
      </Bar>
    );
  } else if (shown && shown.state !== "withdrawn" && shown.state !== "closed") {
    bar = (
      <Bar>
        <button type="button" className="btn btn-primary" onClick={onNext}>
          Next
        </button>
      </Bar>
    );
  } else if (waiting && declining) {
    bar = (
      <Bar>
        <button type="button" className="btn btn-quiet" disabled={busy} onClick={() => setDeclining(false)}>
          Back
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy}
          onClick={() => void send("decline")}
        >
          Decline the request
        </button>
      </Bar>
    );
  } else if (waiting && buttons.length) {
    bar = (
      <Bar>
        {buttons.map((b) => (
          <button
            key={b.answer}
            type="button"
            className={btnClass(b.style)}
            disabled={busy}
            onClick={() => (b.answer === "decline" ? setDeclining(true) : void send(b.answer))}
          >
            {b.label}
          </button>
        ))}
      </Bar>
    );
  }
  return { body, bar };
}

export function TeamUpRequest({ view }: { view: RequestView }) {
  return <>{view.body}</>;
}
