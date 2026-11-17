"use client";

/**
 * S-H2B inside C-INBOX-READER: a team-up or merge request open in the lead's Inbox. The request (the note in full,
 * any idea brought) is read from lane F's `GET /api/team-up/:id` when the item opens, never carried by the item
 * (L-NOTIFY/3); the answer goes to lane F's `POST /api/team-up/:id/answer`, which tells the requester and takes the
 * item off "Needs you". Words: CrewRequest.md, with the board's she/her as the requester's first name or "their"
 * (BLD-E008, listed for HR in BLD-A207).
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

type Request = {
  id: string;
  note: string;
  brought: Brought[];
  state: string;
  words: Words;
  /** An answered request shows its result in place (S-H2B.states). */
  answered: Result | null;
};

type Result = { text: string; sayHello?: { label: string; to: string } };

export type RequestView = { body: ReactNode; bar: ReactNode };

/** The answer an item's op stands for: lane F's `teamup.answer.merge`, or the bare `merge`. */
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

function readBrought(raw: unknown): Brought[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((b: Record<string, unknown>) =>
    typeof b?.id === "string" && typeof b.title === "string"
      ? [
          {
            id: b.id,
            title: b.title,
            status: b.status as IdeaStatus,
            summary: typeof b.summary === "string" ? b.summary : undefined,
            byline: typeof b.byline === "string" ? b.byline : undefined,
          },
        ]
      : [],
  );
}

function readResult(result: unknown, hello: unknown): Result | null {
  const text = (result as { text?: unknown } | null)?.text;
  if (typeof text !== "string" || !text) return null;
  const h = hello as { label?: unknown; to?: unknown } | null;
  return {
    text,
    sayHello:
      typeof h?.label === "string" && typeof h.to === "string" ? { label: h.label, to: h.to } : undefined,
  };
}

/** The request view for the open item, or null when the item is not a request the lead can answer here. */
export function useRequest(
  item: InboxEntry | null,
  onAnswered: (item: InboxEntry) => void | Promise<void>,
  onNext: () => void,
): RequestView | null {
  const requestId = item?.kind === "teamup_request" ? item.body.request_id : undefined;
  const [req, setReq] = useState<Request | null | "failed">(null);
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Once per item: the reader keys the open item, so each request starts from nothing.
  useEffect(() => {
    if (!requestId) return;
    let live = true;
    void fetch(`/api/team-up/${encodeURIComponent(requestId)}`, { cache: "no-store" })
      .then(async (res) => {
        if (!res.ok) throw new Error(String(res.status));
        const data = (await res.json()) as Record<string, unknown>;
        const r = (typeof data.request === "object" && data.request ? data.request : data) as Record<
          string,
          unknown
        >;
        const words = (typeof r.reader === "object" && r.reader ? r.reader : {}) as Words;
        return {
          id: String(r.id ?? requestId),
          note: typeof r.note === "string" ? r.note : "",
          brought: readBrought(r.brought),
          state: typeof r.state === "string" ? r.state : "sent",
          words,
          answered: readResult(r.result, r.say_hello),
        };
      })
      .then((r) => live && setReq(r))
      .catch(() => live && setReq("failed"));
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
      const data = (await res?.json().catch(() => null)) as {
        result?: { text?: string };
        say_hello?: { label?: string; to?: string } | null;
        error?: { message?: string };
      } | null;
      if (!res?.ok) {
        setError(data?.error?.message ?? "We couldn't send that just now. Please try again in a minute.");
        return;
      }
      setResult(readResult(data?.result, data?.say_hello) ?? { text: "" });
      setDeclining(false);
      await onAnswered(item);
    },
    [item, requestId, reason, onAnswered],
  );

  if (!item || !requestId) return null;
  const first = firstName(item);
  const loaded = req && req !== "failed" ? req : null;
  const shown = result ?? loaded?.answered ?? null;
  const waiting = loaded?.state === "sent" && !shown;
  const w = loaded?.words ?? {};
  const many = (loaded?.brought.length ?? 0) > 1;
  const ops = item.actions.filter((a) => answerOf(a.op));

  const body = (
    <div className="ibx-req">
      {req === "failed" ? (
        <p className="ibx-foot">We can&apos;t show this request just now. Please try again in a minute.</p>
      ) : null}
      {loaded ? (
        <>
          <h3 className="ibx-sh">{w.note_heading ?? (first ? `${first}’s note` : "The note")}</h3>
          <p className="ibx-note">{loaded.note}</p>
          {loaded.brought.length ? (
            <>
              <h3 className="ibx-sh">
                {w.brought_heading ??
                  `${many ? "The ideas" : "The idea"} ${first || "they"} asks you to merge into yours`}
              </h3>
              {loaded.brought.map((b) => (
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
                (loaded.brought.length
                  ? `Merge it, and their idea joins yours: ${first} is on your crew and credited on it. Team up only puts ${first} on your crew and keeps their idea separate. Decline, and ${first} sends theirs on its own, with your reason if you give one.`
                  : `Approve, and ${first} is on your crew. Decline, and ${first} hears your reason if you give one.`)}
            </p>
          ) : null}
          {declining ? (
            <div className="ibx-field">
              <label htmlFor="ibx-reason">Tell {first || "them"} why, if you like</label>
              <textarea id="ibx-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
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

  let bar: ReactNode = null;
  if (shown) {
    bar = (
      <Bar>
        {shown.sayHello ? (
          <Link className="btn btn-primary" href={shown.sayHello.to}>
            {shown.sayHello.label}
          </Link>
        ) : (
          <button type="button" className="btn btn-primary" onClick={onNext}>
            Next
          </button>
        )}
      </Bar>
    );
  } else if (declining) {
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
  } else if (waiting && ops.length) {
    bar = (
      <Bar>
        {ops.map((a) => {
          const answer = answerOf(a.op)!;
          return (
            <button
              key={a.label}
              type="button"
              className={btnClass(a.style)}
              disabled={busy}
              onClick={() => (answer === "decline" ? setDeclining(true) : void send(answer))}
            >
              {a.label}
            </button>
          );
        })}
      </Bar>
    );
  }
  return { body, bar };
}

export function TeamUpRequest({ view }: { view: RequestView }) {
  return <>{view.body}</>;
}
