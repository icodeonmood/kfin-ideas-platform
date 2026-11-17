"use client";

/**
 * S-08, an idea's conversation (lane F; L-CONVO, Messages.md). The header, the timeline as a log, the box with its
 * @mention picker, and "In this conversation". The server works out every line, label and placeholder
 * (`GET /api/ideas/:id/conversation`, BLD-F059); this screen lays them out, sends and removes messages, and reads the
 * conversation again after each action (no live channel yet, BLD-F050).
 *
 * - The questions: for the sharer while the set is open, lane B's C-QCARD read from that set (BLD-B249); for anyone
 *   else, or until the set is read, a plain entry with the card's title, the sharer's deadline and "Answer the
 *   questions" (S-R3, S-08.rules/1, BLD-F065).
 * - Files: rows with View for the readers who may open them; no attach control until a conversation can take an
 *   upload (BLD-F064; who may attach is `composer.can_attach`, BLD-F063).
 * - Phone (S-08.rules/4): the compact bar with Back, the title and an "i" button that opens the side panel as a
 *   sheet; the box stays at the bottom.
 */
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { QuestionsCardFor } from "@/components/review/qcard-for";
import { PhoneBar } from "@/components/shell/phone";
import { Avatar } from "@/components/ui/avatar";
import { Button, ButtonLink, buttonClass } from "@/components/ui/button";
import { Empty } from "@/components/ui/empty";
import { FieldMsg } from "@/components/ui/field";
import { FileList, FileRow, fileKind } from "@/components/ui/file";
import { IDEA_STATUS, Pill } from "@/components/ui/pill";
import type { ConversationEntryView, ConversationView, FileItem } from "@/lib/contracts";

import {
  S08_COPY as C,
  errorText,
  fileSize,
  fileStatus,
  mentionAt,
  mentionChoices,
  mentionHint,
  mentionsIn,
  putMention,
  withMentions,
  type MentionQuery,
} from "./compose";
import "./conversation.css";

type Entry = ConversationEntryView;
type MessageEntry = Extract<Entry, { type: "message" }>;
type QuestionsEntry = Extract<Entry, { type: "questions" }>;
type AnswersEntry = Extract<Entry, { type: "answers" }>;
type EventEntry = Extract<Entry, { type: "event" }>;
type Mentionable = { id: string; name: string; first_name: string; initials: string; doing: string };

const enc = encodeURIComponent;

function cls(...names: (string | false | null | undefined)[]): string {
  return names.filter(Boolean).join(" ");
}

function newKey(): string {
  const c = globalThis.crypto;
  if (c && typeof c.randomUUID === "function") return c.randomUUID();
  return `convo-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

function reducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

function InfoIcon() {
  return (
    <svg width={22} height={22} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 8h.01" />
    </svg>
  ); // prettier-ignore
}

/** Words with one part of them linked: an event's reference ("It’s now part of IDEA-…"), or "Answer the questions"
 * inside the line above the box. */
function linkedText(text: string, label: string, href: string | undefined): ReactNode {
  if (!href) return text;
  const at = text.indexOf(label);
  if (at < 0)
    return (
      <>
        {text} <Link href={href}>{label}</Link>
      </>
    );
  return (
    <>
      {text.slice(0, at)}
      <Link href={href}>{label}</Link>
      {text.slice(at + label.length)}
    </>
  );
}

function Files({ files, label }: { files: FileItem[]; label: string }) {
  if (!files.length) return null;
  return (
    <FileList label={label}>
      {files.map((f) => {
        const st = fileStatus(f);
        return (
          <FileRow
            key={f.id}
            name={f.name}
            kind={fileKind(f.name)}
            size={fileSize(f.size)}
            status={st.status}
            statusText={st.text}
          >
            {f.view_url ? (
              <a className={buttonClass("text", "sm")} href={f.view_url} aria-label={`${C.view} ${f.name}`}>
                {C.view}
              </a>
            ) : null}
          </FileRow>
        );
      })}
    </FileList>
  );
}

export interface ConversationProps {
  /** The conversation as the server read it for this person. */
  initial: ConversationView;
  /** The reference the page was opened with (`IDEA-2026-001481`). */
  ideaId: string;
  /** The clock, for "Remove" while a message can still be removed; tests pass their own. */
  now?: () => number;
}

export function Conversation({ initial, ideaId, now = Date.now }: ConversationProps) {
  const [view, setView] = useState(initial);
  const [text, setText] = useState("");
  const [picked, setPicked] = useState<ReadonlyMap<string, string>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState<MentionQuery | null>(null);
  const [active, setActive] = useState(0);
  const [removing, setRemoving] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<{ id: string; text: string } | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  const box = useRef<HTMLTextAreaElement>(null);
  const caretAfter = useRef<number | null>(null);
  const keyRef = useRef<string | null>(null);
  // The "@" whose list Escape closed: it stays closed until a new "@" (a ref, so a select event in the same tick
  // reads it at once).
  const dismissed = useRef<number | null>(null);
  const logEnd = useRef<HTMLDivElement>(null);
  const infoButton = useRef<HTMLButtonElement>(null);
  const panelClose = useRef<HTMLButtonElement>(null);

  const uid = useId();
  const ids = {
    heading: `${uid}-h`,
    side: `${uid}-side`,
    panel: `${uid}-panel`,
    list: `${uid}-mentions`,
    error: `${uid}-err`,
    who: `${uid}-who`,
    option: (i: number) => `${uid}-opt-${i}`,
  };

  const base = `/api/ideas/${enc(ideaId)}/conversation`;
  const ideaHref = `/ideas/${enc(view.idea.id)}`;
  const status = Object.hasOwn(IDEA_STATUS, view.idea.status)
    ? IDEA_STATUS[view.idea.status as keyof typeof IDEA_STATUS]
    : null;

  const people: Mentionable[] = useMemo(
    () =>
      view.participants.filter((p) => !p.you && p.person.id).map((p) => ({ ...p.person, doing: p.doing })),
    [view.participants],
  );
  const choices = menu ? mentionChoices(people, menu.query) : [];
  const open = Boolean(menu && choices.length);
  const openQuestions = view.entries.find(
    (e): e is QuestionsEntry => e.type === "questions" && Boolean(e.answer_url),
  );

  // Put the caret after a picked name once the words are on screen.
  useEffect(() => {
    if (caretAfter.current === null || !box.current) return;
    box.current.focus();
    box.current.setSelectionRange(caretAfter.current, caretAfter.current);
    caretAfter.current = null;
  }, [text]);

  // Phone sheet: focus into it when it opens; Escape closes it and focus goes back to the "i" button.
  useEffect(() => {
    if (!panelOpen) return;
    panelClose.current?.focus();
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setPanelOpen(false);
      infoButton.current?.focus();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [panelOpen]);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(base, { cache: "no-store", headers: { Accept: "application/json" } });
      if (res.ok) setView((await res.json()) as ConversationView);
    } catch {
      // Keep what is on screen; the next action reads it again.
    }
  }, [base]);

  /** Put an entry the server returned on screen at once (its POST or DELETE answer), replacing it if it is there;
   * the read that follows confirms it, and if that read fails the entry stays. */
  function place(entry: unknown) {
    if (!entry || typeof entry !== "object" || typeof (entry as { id?: unknown }).id !== "string") return;
    const e = entry as Entry;
    setView((v) => {
      const at = v.entries.findIndex((x) => x.id === e.id);
      const entries = at < 0 ? [...v.entries, e] : v.entries.map((x, i) => (i === at ? e : x));
      return { ...v, entries, empty: e.type === "message" ? undefined : v.empty };
    });
  }

  function toBottom() {
    const el = logEnd.current;
    if (el && typeof el.scrollIntoView === "function") {
      el.scrollIntoView({ block: "end", behavior: reducedMotion() ? "auto" : "smooth" });
    }
  }

  function track(value: string, caret: number) {
    const q = mentionAt(value, caret);
    if (q && dismissed.current === q.start) {
      setMenu(null);
      return;
    }
    if (!q) dismissed.current = null;
    // The highlighted choice stays while the query does; a new query starts at the top.
    if (!q || !menu || q.start !== menu.start || q.query !== menu.query) setActive(0);
    setMenu(q);
  }

  function pick(p: Mentionable) {
    if (!menu || !box.current) return;
    const caret = box.current.selectionStart ?? text.length;
    const next = putMention(text, menu, caret, p);
    caretAfter.current = next.caret;
    keyRef.current = null;
    setText(next.text);
    setPicked((m) => new Map(m).set(p.id, p.name));
    setMenu(null);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (!open || !menu) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (i + step + choices.length) % choices.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      pick(choices[Math.min(active, choices.length - 1)]!);
    } else if (e.key === "Tab") {
      setMenu(null); // Tab leaves the box as it always does; the list closes behind it
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      dismissed.current = menu.start;
      setMenu(null);
    }
  }

  async function send(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    if (!text.trim()) {
      setError(C.empty);
      box.current?.focus();
      return;
    }
    setBusy(true);
    setError(null);
    keyRef.current ??= newKey();
    try {
      const res = await fetch(`${base}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": keyRef.current },
        body: JSON.stringify({ text, mentions: mentionsIn(text, picked) }),
      });
      const body: unknown = await res.json().catch(() => null);
      if (!res.ok) {
        setError(errorText(body));
        if (res.status === 409) await refresh(); // closed while it was open: show why, and where to write
        box.current?.focus();
        return;
      }
      // Sent: the words go, and the message the server returns shows at once, so nothing is sent twice even if
      // the read after it fails.
      keyRef.current = null;
      setText("");
      setPicked(new Map());
      setMenu(null);
      place((body as { entry?: unknown } | null)?.entry);
      await refresh();
      toBottom();
    } catch {
      setError(C.failed);
    } finally {
      setBusy(false);
    }
  }

  async function remove(entryId: string) {
    setRemoving(entryId);
    setRemoveError(null);
    try {
      const res = await fetch(`${base}/messages/${enc(entryId)}`, { method: "DELETE" });
      const body: unknown = await res.json().catch(() => null);
      if (!res.ok) {
        setRemoveError({ id: entryId, text: errorText(body, C.removeFailed) });
        return;
      }
      place((body as { entry?: unknown } | null)?.entry);
      // Remove goes with the message it removed: focus moves to that line, now "Message removed" (WCAG 2.4.3).
      document.getElementById(`entry-${entryId}`)?.focus();
      await refresh();
    } catch {
      setRemoveError({ id: entryId, text: C.removeFailed });
    } finally {
      setRemoving(null);
    }
  }

  function renderEvent(e: EventEntry) {
    return (
      <li key={e.id} id={`entry-${e.id}`} className="cv-ev">
        <span className="cv-evd" aria-hidden="true" />
        <p>{e.link ? linkedText(e.text, e.link.label, e.link.to) : e.text}</p>
      </li>
    );
  }

  function renderMessage(e: MessageEntry) {
    const until = e.can_remove_until ? Date.parse(e.can_remove_until) : NaN;
    const canRemove = e.you && !e.removed && Number.isFinite(until) && now() < until;
    const parts = withMentions(e.text, e.removed ? [] : e.mentions.map((m) => m.name));
    return (
      <li
        key={e.id}
        id={`entry-${e.id}`}
        className={cls("cv-msg", e.you && "me", e.mentions_you && "mentions-you")}
        tabIndex={-1}
      >
        <p className="cv-who">
          {e.you ? null : <Avatar initials={e.from.initials} size={28} />}
          <b>{e.from_label}</b>
          <span>{e.at_label}</span>
        </p>
        <p className={cls("cv-bub", e.removed && "removed")}>
          {parts.map((p, i) =>
            p.mention ? (
              <span key={i} className="cv-ment">
                {p.text}
              </span>
            ) : (
              p.text
            ),
          )}
        </p>
        <Files
          files={e.files}
          label={`Files in ${e.from_label === "You" ? "your" : `${e.from_label}’s`} message`}
        />
        {canRemove ? (
          <Button
            variant="text"
            size="sm"
            busy={removing === e.id}
            onClick={() => void remove(e.id)}
            aria-label={`${C.remove} your message from ${e.at_label}`}
          >
            {C.remove}
          </Button>
        ) : null}
        {removeError?.id === e.id ? <FieldMsg>{removeError.text}</FieldMsg> : null}
      </li>
    );
  }

  function plainQuestions(e: QuestionsEntry) {
    return (
      <div className={cls("cv-ask", !e.answer_url && "done")}>
        <p className="cv-askt">{e.title}</p>
        {e.deadline ? <p className="cv-askd">{e.deadline}</p> : null}
        <p className="cv-aska">
          {e.answer_url ? (
            <ButtonLink href={e.answer_url}>{C.answer}</ButtonLink>
          ) : (
            <Link href={ideaHref}>{C.seeOnIdea}</Link>
          )}
        </p>
      </div>
    );
  }

  function renderQuestions(e: QuestionsEntry) {
    return (
      <li key={e.id} id={`entry-${e.id}`} className="cv-msg wide">
        <p className="cv-who">
          <Avatar initials={e.by.initials} size={28} />
          <b>{e.by_label}</b>
          <span>{e.at_label}</span>
        </p>
        {e.answer_url ? (
          // BLD-B249: `answer_url` comes only to the sharer while the set is open; the card reads that set and
          // takes the conversation's words for its title and deadline (Messages.md)
          <QuestionsCardFor
            key={`${e.set_id}:${e.state}:${e.answered}`}
            ideaId={view.idea.id}
            setId={e.set_id}
            title={e.title}
            deadline={e.deadline}
            byline={false}
            fallback={plainQuestions(e)}
          />
        ) : (
          plainQuestions(e)
        )}
      </li>
    );
  }

  function renderAnswers(e: AnswersEntry) {
    return (
      <li key={e.id} id={`entry-${e.id}`} className="cv-msg me wide">
        <p className="cv-who">
          <span>{e.at_label}</span>
        </p>
        <div className="cv-ans">
          <p className="cv-anst">{e.title}</p>
          <ol className="cv-ansq">
            {e.answers.map((a) => (
              <li key={a.id}>
                <p className="cv-qa">{a.text}</p>
                {a.files.length ? (
                  <ul className="cv-afiles" aria-label={`Files with this answer`}>
                    {a.files.map((f) => (
                      <li key={f.id}>{f.view_url ? <a href={f.view_url}>{f.name}</a> : f.name}</li>
                    ))}
                  </ul>
                ) : null}
                <p className="cv-qp">
                  {C.addedTo} <b>{a.added_to_label}</b>
                </p>
              </li>
            ))}
          </ol>
        </div>
        {e.footer ? <p className="cv-foot">{e.footer}</p> : null}
      </li>
    );
  }

  function renderEntry(e: Entry) {
    if (e.type === "event") return renderEvent(e);
    if (e.type === "message") return renderMessage(e);
    if (e.type === "questions") return renderQuestions(e);
    return renderAnswers(e);
  }

  const composer = view.composer;
  const hint = open ? mentionHint(choices.length) : "";
  const described = [error ? ids.error : null, ids.who].filter(Boolean).join(" ");

  return (
    <div className="cv">
      <PhoneBar
        back={{ href: ideaHref, label: view.header.whose }}
        title={view.idea.title}
        actions={
          <button
            ref={infoButton}
            type="button"
            className="cv-info"
            aria-expanded={panelOpen}
            aria-controls={ids.panel}
            onClick={() => setPanelOpen((v) => !v)}
          >
            <InfoIcon />
            <span className="visually-hidden">{C.people}</span>
          </button>
        }
      />
      <header className="cv-head">
        <p className="back-row cv-back">
          <Link className="back" href={ideaHref}>
            {view.header.whose}
          </Link>
        </p>
        <p className="cv-meta">
          {status ? <Pill variant={status.pill}>{status.label}</Pill> : null}
          <span>{view.idea.id}</span>
        </p>
        <p className="cv-line">{view.header.line}</p>
        <h1 className="h1 cv-title">
          <Link href={ideaHref}>{view.idea.title}</Link>
        </h1>
      </header>

      <div className="cv-cols">
        <section className="cv-main" aria-labelledby={ids.heading}>
          <h2 id={ids.heading} className="cv-l">
            {C.heading}
          </h2>
          <div className="cv-log" role="log" aria-labelledby={ids.heading}>
            {view.entries.length ? <ol className="cv-conv">{view.entries.map(renderEntry)}</ol> : null}
            {view.empty ? (
              <div className="cv-empty">
                <Empty title={view.empty.title} align="center" level={3}>
                  {view.empty.body}
                </Empty>
              </div>
            ) : null}
            <div ref={logEnd} />
          </div>

          {composer.closed ? (
            <p className="cv-closed">{composer.closed}</p>
          ) : (
            <form className="cv-box" onSubmit={(e) => void send(e)} noValidate>
              {composer.questions_line ? (
                <p className="cv-hint">
                  {linkedText(composer.questions_line, C.answer, openQuestions?.answer_url)}
                </p>
              ) : null}
              <div className="cv-field">
                <textarea
                  ref={box}
                  className="cv-in"
                  rows={2}
                  value={text}
                  placeholder={composer.placeholder}
                  aria-label={composer.placeholder}
                  aria-describedby={described}
                  aria-invalid={error ? true : undefined}
                  aria-autocomplete="list"
                  aria-controls={open ? ids.list : undefined}
                  aria-activedescendant={open ? ids.option(Math.min(active, choices.length - 1)) : undefined}
                  onChange={(e) => {
                    keyRef.current = null;
                    setText(e.target.value);
                    if (error) setError(null);
                    track(e.target.value, e.target.selectionStart ?? e.target.value.length);
                  }}
                  onSelect={(e) => {
                    const t = e.currentTarget;
                    track(t.value, t.selectionStart ?? t.value.length);
                  }}
                  onKeyDown={onKeyDown}
                  onBlur={() => setMenu(null)}
                />
                {open ? (
                  <ul id={ids.list} className="cv-menu" role="listbox" aria-label={C.mentionList}>
                    {choices.map((p, i) => (
                      <li
                        key={p.id}
                        id={ids.option(i)}
                        role="option"
                        aria-selected={i === active}
                        className={i === active ? "on" : undefined}
                        onMouseDown={(ev) => {
                          ev.preventDefault(); // keep focus in the box
                          pick(p);
                        }}
                      >
                        <Avatar initials={p.initials} size={28} />
                        <span className="cv-menu-n">{p.name}</span>
                        <span className="cv-menu-d">{p.doing}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
              <p className="visually-hidden" aria-live="polite">
                {hint}
              </p>
              {error ? <FieldMsg id={ids.error}>{error}</FieldMsg> : null}
              <div className="cv-bar">
                <p id={ids.who} className="cv-sees">
                  {composer.visibility}
                </p>
                <Button type="submit" className="cv-send" busy={busy} busyLabel={C.sending}>
                  {C.send}
                </Button>
              </div>
            </form>
          )}
        </section>

        <aside id={ids.panel} className={cls("cv-side", panelOpen && "open")} aria-labelledby={ids.side}>
          <div className="cv-sidec">
            <div className="cv-side-top">
              <h2 id={ids.side} className="cv-side-h">
                {C.side}
              </h2>
              <button
                ref={panelClose}
                type="button"
                className={cls(buttonClass("text", "sm"), "cv-side-x")}
                onClick={() => {
                  setPanelOpen(false);
                  infoButton.current?.focus();
                }}
              >
                {C.close}
              </button>
            </div>
            <ul className="cv-ppl">
              {view.participants.map((p) => (
                <li key={`${p.person.id}-${p.label}`}>
                  <Avatar initials={p.person.initials} size={36} />
                  <span>
                    <b>{p.label}</b>
                    <span className="cv-doing">{p.doing}</span>
                  </span>
                </li>
              ))}
            </ul>
            <p className="cv-sidenote">{C.sideNote}</p>
          </div>
        </aside>
      </div>
    </div>
  );
}
