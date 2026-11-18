"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";

import { IdeaPreviewDialog } from "@/components/preview/idea-preview";
import { QuestionsCard } from "@/components/review/qcard";
import { Status } from "@/components/status";
import { useTeamUpSheet } from "@/components/teamup/teamup-sheet";
import { Avatar } from "@/components/ui/avatar";
import { Button, ButtonLink, buttonClass } from "@/components/ui/button";
import { Pill } from "@/components/ui/pill";
import { Track } from "@/components/ui/track";
import type {
  DecisionForViewerResponse,
  PostAction,
  SharedRow,
  SharerAnswer,
  SharerQuestionSetResponse,
  SharerView,
  SimilarTile,
} from "@/lib/contracts/api";
import type { FileItem } from "@/lib/contracts/entities";

import { capital, decisionSentence, type Decided } from "./decision";
import { AskToJoin } from "./join-build";
import { BackLink, backToList, CopyRef, useWay } from "./parts";
import { toTrack, type StageWords } from "./track";

const TRY_AGAIN = "We can't do that just now. Please try again in a minute.";
// The decision's or the questions' part could not be read: Status.md draws no error line, so one neutral line
// fits both (BLD-E012)
// NOT DRAWN (BLD-E044): HR sign-off
const PART_FAILED = "We can't load this just now. Please try again in a minute.";
type SheetName = "hidden" | "fix";

/** A native dialog: focus moves in on open, Escape closes it, focus returns to the opener (V-ACC.visual/11). */
function Sheet({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const id = useId();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  const close = (el: Element) => el.closest("dialog")?.close();
  return (
    <dialog
      ref={ref}
      className="ip-dialog"
      aria-labelledby={id}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) close(e.currentTarget);
      }}
    >
      <div className="ip-dialog-in">
        <div className="ip-dialog-top">
          <h2 id={id} className="ip-h2">
            {title}
          </h2>
          <button type="button" className="ip-x" aria-label="Close" onClick={(e) => close(e.currentTarget)}>
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path
                d="M6 6l12 12M18 6 6 18"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
        {children}
      </div>
    </dialog>
  );
}

function Answers({ answers }: { answers?: SharerAnswer[] }) {
  if (!answers?.length) return null;
  return (
    <ul className="ip-answers">
      {answers.map((a) => (
        <li key={a.id}>
          <p className="ip-ans-line">{a.line}</p>
          <p className="ip-ans-text">{a.text}</p>
        </li>
      ))}
    </ul>
  );
}

const FIGURE_ORDER = ["hours", "cost", "revenue", "reliance"];

function figuresOf(f: Record<string, string> | undefined): string[] {
  if (!f) return [];
  return FIGURE_ORDER.filter((k) => f[k]).map((k) => f[k]!);
}

/** What it's worth: the sharer's figures, and the reviewer's next to them with the note (L-WORTH/3). */
function Worth({ row }: { row: SharedRow }) {
  const mine = figuresOf(row.figures?.sharer);
  const rev = row.figures?.reviewer;
  return (
    <>
      <p className="ip-val">{row.value}</p>
      {mine.length ? <p className="ip-fig">{mine.join(", ")}</p> : null}
      {rev ? (
        <div className="ip-rev">
          {rev.by_line ? <p className="ip-rev-by">{rev.by_line}</p> : null}
          <p className="ip-fig">{figuresOf(rev).join(", ")}</p>
          {rev.note ? <p className="ip-rev-note">“{rev.note}”</p> : null}
        </div>
      ) : null}
    </>
  );
}

const FILE_BADGE: Record<string, string> = {
  image: "JPG",
  pdf: "PDF",
  sheet: "XLS",
  doc: "DOC",
  audio: "AUDIO",
};

function fileSize(f: FileItem): string {
  const bits: string[] = [];
  if (f.pages) bits.push(`${f.pages} page${f.pages === 1 ? "" : "s"}`);
  if (f.size)
    bits.push(
      f.size >= 1_000_000
        ? `${(f.size / 1_000_000).toFixed(1)} MB`
        : `${Math.max(1, Math.round(f.size / 1000))} KB`,
    );
  return bits.join(", ");
}

function FileTile({ f }: { f: FileItem }) {
  const ext = (f.name.split(".").pop() ?? "").toUpperCase();
  return (
    <li className="ip-file">
      <span className="ip-badge" aria-hidden="true">
        {FILE_BADGE[f.kind] ?? (ext.slice(0, 4) || "FILE")}
      </span>
      <span className="ip-file-t">
        <span className="ip-file-n">{f.name}</span>
        <span className="ip-file-m">
          {[fileSize(f), f.state === "checked" || f.state === "hidden_checked" ? "Checked" : null]
            .filter(Boolean)
            .join(" · ")}
        </span>
      </span>
      {f.view_url ? (
        <a className="ip-file-v" href={f.view_url} aria-label={`View ${f.name}`}>
          View
        </a>
      ) : null}
    </li>
  );
}

function ReversalCard({ d }: { d: Decided }) {
  const r = d.lines?.reversal;
  if (!r || !d.reversal) return null;
  return (
    <div className="ip-rcard">
      <div className="ip-r-by">
        <Avatar initials={d.reversal.by.initials} size={32} ring="neutral" />
        <p>{r.from_line}</p>
      </div>
      <h2 className="ip-r-h">{r.title}</h2>
      {d.reversal.note ? (
        <figure className="ip-quote">
          <blockquote>“{d.reversal.note}”</blockquote>
          <figcaption>{r.note_heading}</figcaption>
        </figure>
      ) : null}
      <p className="ip-was">
        {r.was_line} <span>{r.was_by_line}</span>
      </p>
      <p className="ip-final">{r.final_line}</p>
    </div>
  );
}

function Withdraw({ action, onDone }: { action: PostAction; onDone: (line: string) => void }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const id = useId();
  const c = action.confirm;
  const opener = useRef<HTMLButtonElement>(null);
  const first = useRef<HTMLTextAreaElement>(null);
  if (!open || !c) {
    return (
      <Button
        ref={opener}
        variant="text"
        className="ip-card-act"
        onClick={() => {
          setOpen(true);
          requestAnimationFrame(() => first.current?.focus());
        }}
      >
        {action.label}
      </Button>
    );
  }
  const send = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setFailed(false);
    const reason = String(new FormData(e.currentTarget).get("reason") ?? "").trim();
    try {
      const res = await fetch(action.path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(reason ? { reason } : {}),
      });
      if (!res.ok) throw new Error(String(res.status));
      onDone(action.done);
    } catch {
      setFailed(true);
      setBusy(false);
    }
  };
  return (
    <form className="ip-confirm" onSubmit={send} aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`} className="ip-confirm-h">
        {c.heading}
      </h2>
      <p className="ip-confirm-l">{c.line}</p>
      <label className="ip-confirm-lab" htmlFor={`${id}-r`}>
        {c.reason_label} <span className="ip-opt">{c.reason_hint}</span>
      </label>
      <textarea
        ref={first}
        id={`${id}-r`}
        name="reason"
        rows={2}
        placeholder={c.placeholder}
        maxLength={2000}
      />
      {failed ? <Status kind="error" title={TRY_AGAIN} /> : null}
      <div className="ip-confirm-a">
        <Button
          type="button"
          variant="line"
          onClick={() => {
            setOpen(false);
            requestAnimationFrame(() => opener.current?.focus());
          }}
        >
          {c.cancel_label}
        </Button>
        <Button type="submit" disabled={busy}>
          {c.confirm_label}
        </Button>
      </div>
    </form>
  );
}

function SimilarCard({ similar }: { similar: SharerView["page"]["similar"] }) {
  const router = useRouter();
  const [preview, setPreview] = useState<SimilarTile | null>(null);
  // Lane F's C-SHEET-TEAMUP from a tile's "Team up" or from C-PREVIEW's; the tile stays, so focus comes back to it
  const teamUp = useTeamUpSheet({ onSent: () => router.refresh(), onWithdrawn: () => router.refresh() });
  if (!similar.tiles.length) return null;
  return (
    <section className="card ip-side-card" aria-labelledby="ip-sim-h">
      <h2 id="ip-sim-h" className="ip-h2">
        {similar.heading}
      </h2>
      <p className="ip-side-l">{similar.intro}</p>
      <ul className="ip-tiles">
        {similar.tiles.map((t) => (
          <li key={t.idea.id} className="ip-tile" data-handover="expand">
            <h3 className="ip-tile-t">
              <Link href={t.to}>{t.idea.title}</Link>
            </h3>
            <p className="ip-tile-m">{t.meta}</p>
            <Pill variant={t.pill.variant}>{t.pill.label}</Pill>
            <p className="ip-tile-r">{t.reason}</p>
            <div className="ip-tile-crew">
              <ul className="ip-faces" aria-hidden="true">
                {t.idea.crew_faces.slice(0, 4).map((p) => (
                  <li key={p.id}>
                    <Avatar initials={p.initials} size={28} ring="neutral" />
                  </li>
                ))}
              </ul>
              <span>{t.count_line}</span>
            </div>
            <div className="ip-tile-a">
              {t.actions.map((a) =>
                a.op === "preview" ? (
                  <Button
                    key={a.op}
                    variant="line"
                    size="sm"
                    aria-label={a.accessible_name}
                    aria-haspopup="dialog"
                    onClick={() => setPreview(t)}
                  >
                    {a.label}
                  </Button>
                ) : a.op === "team_up" ? (
                  <Button
                    key={a.op}
                    variant="primary"
                    size="sm"
                    aria-label={a.accessible_name}
                    aria-haspopup="dialog"
                    onClick={() => teamUp.open(t.idea.id)}
                  >
                    {a.label}
                  </Button>
                ) : null,
              )}
            </div>
          </li>
        ))}
      </ul>
      {preview ? (
        <IdeaPreviewDialog
          ideaId={preview.idea.id}
          view="sharer"
          open
          yours="idea"
          matchReason={preview.reason}
          fullHref={preview.to}
          onClose={() => setPreview(null)}
          onPrimary={teamUp.open}
        />
      ) : null}
      {teamUp.sheet}
    </section>
  );
}

/**
 * S-06, your idea's page (copy: reference/copy/Status.md, PhoneStatus.md): where it is, what happens next and by
 * when, and what the sharer can do now. The page's own words come from lane E's `GET /ideas/:id`; the decision, its
 * reason and the committee's window from lane B's `/decision`, the questions from lane B's `/question-set`
 * (BLD-E012). Nothing waits: the reference and the next step are there on the first paint (S-06.rules/1).
 */
export function SharerScreen({
  view,
  decision,
  questions,
  partFailed,
}: {
  view: SharerView;
  decision: DecisionForViewerResponse;
  questions: SharerQuestionSetResponse;
  partFailed: boolean;
}) {
  const router = useRouter();
  const { idea, page } = view;
  const [said, setSaid] = useState("");
  const title = useRef<HTMLHeadingElement>(null);
  // After Withdraw or Restore the button that was pressed is gone: focus goes to the idea's title once the page in
  // its new state has rendered, and the status line says what happened
  const focusTitle = useRef(false);
  useEffect(() => {
    if (!focusTitle.current) return;
    focusTitle.current = false;
    title.current?.focus();
  }, [view]);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [sheet, setSheet] = useState<{ name: SheetName; from: HTMLElement } | null>(null);
  const closeSheet = () => {
    sheet?.from.focus();
    setSheet(null);
  };

  const d = decision && !("stage_only" in decision) ? (decision as Decided) : null;
  const stages = (idea.stages ?? []) as unknown as StageWords[];
  const track = toTrack(stages);
  const reviewer = idea.review?.reviewer?.first_name ?? null;
  const ref = idea.ref ?? idea.id;
  const reversed = page.state === "reversed" && d?.lines?.reversal ? d : null;
  const qset = page.card_from === "question_set" || idea.has_open_questions ? questions : null;
  // Questions from the desk: lane B's C-QCARD leads the card (S-06.states). Answers sent with a question still open:
  // "Sent." leads and the card, partly answered, sits under it for the rest (BLD-E051).
  const asking = page.card_from === "question_set";
  const qcard = qset ? <QuestionsCard ideaId={ref} set={qset} variant="status" /> : null;

  const card: { lead: string; rest: string; phone_rest?: string } | null =
    page.card ??
    (page.card_from === "decision" && d ? decisionSentence(d, reviewer, stages) : null) ??
    (idea.next_step && !qset && !reversed ? { lead: idea.next_step.sentence, rest: "" } : null);
  const committee = d?.lines?.committee_line ?? null;
  // Status.md and PhoneStatus.md say the line about the review desk once, under "Open the conversation": the
  // decided line the API sends with the conversation, or else the window's line once the desk has the idea (it can't
  // be changed now). That line then leaves the track, so it is said once (BLD-E045).
  const conv = page.conversation;
  const closedWindow = conv && !conv.sub_line && page.window && !page.window.open ? page.window : null;
  const deskLine = conv ? (conv.sub_line ?? closedWindow?.line ?? null) : null;
  const windowLine: SharerView["page"]["window"] =
    (closedWindow ? null : page.window) ?? (committee ? { open: false, line: committee } : null);

  const done = (line: string) => {
    setSaid(line);
    focusTitle.current = true;
    router.refresh();
  };

  const restore = async (a: PostAction) => {
    setBusy(true);
    setFailed(false);
    try {
      const res = await fetch(a.path, { method: "POST", headers: { "Content-Type": "application/json" } });
      if (!res.ok) throw new Error(String(res.status));
      done(a.done);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };

  // The way back this visit was given, kept across a reload and the refresh after Withdraw (BLD-E021)
  const way = useWay({ label: page.breadcrumb.label, to: page.breadcrumb.to });
  const crumb = { ...page.breadcrumb, ...way };
  const backLabel = crumb.label === "Wall" ? "Back to the Wall" : `Back to ${crumb.label}`;
  const h = page.shared.hidden;
  const f = page.shared.fix;
  const at = page.shared.attached;

  return (
    <div className="ip ip-sharer">
      <nav className="ip-crumb ip-desk" aria-label="Breadcrumb">
        <ol>
          <li>
            <Link href={crumb.to} onClick={backToList(crumb.to)}>
              {crumb.label}
            </Link>
          </li>
          <li aria-current="page">{crumb.current}</li>
        </ol>
      </nav>
      <div className="ip-phone ip-ptop">
        <BackLink label={backLabel} to={crumb.to} />
        {/* PhoneStatus.md: the reference sits by the way back and copies itself */}
        <CopyRef value={ref} say={setSaid} />
      </div>

      <article className="ip-card" data-state={page.state} aria-labelledby="ip-title">
        <div className="ip-card-top">
          <Pill variant={page.pill.variant}>{page.pill.label}</Pill>
          <div className="ip-card-tools">
            {page.shared_label ? <span className="ip-card-date">{page.shared_label}</span> : null}
            {page.first_arrival && page.share_seconds_label ? (
              <span className="ip-card-date">{page.share_seconds_label}</span>
            ) : null}
            {page.actions.edit ? (
              <Link className="ip-card-icon" href={page.actions.edit.to} aria-label={page.actions.edit.label}>
                <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                  <path
                    d="M4 20h4L19 9l-4-4L4 16v4zM14 6l4 4"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinejoin="round"
                  />
                </svg>
              </Link>
            ) : null}
            {page.actions.withdraw ? <Withdraw action={page.actions.withdraw} onDone={done} /> : null}
          </div>
        </div>
        <h1 id="ip-title" ref={title} tabIndex={-1} className="ip-card-title">
          {idea.title}
        </h1>
        <p className="ip-card-ref ip-desk">{ref}</p>
        <p className="ip-card-ref ip-phone">{page.reference_line ?? ref}</p>
        <div className="ip-card-body">
          {asking ? qcard : null}
          {reversed ? <ReversalCard d={reversed} /> : null}
          {card && !asking && !reversed ? (
            // S-06.layout/2: the first clause in white, the rest dimmer and on its own line, as Status.md draws the
            // decided, answered and withdrawn states (J-TRACK/7, J-REVIEW/6); "Just shared" keeps one line
            <p className="ip-card-s">
              <span className="ip-lead">{card.lead}</span>{" "}
              {card.phone_rest ? (
                <>
                  <span className="ip-desk">{card.rest}</span>
                  <span className="ip-phone">{card.phone_rest}</span>
                </>
              ) : card.rest ? (
                <span className="ip-rest">{card.rest}</span>
              ) : null}
            </p>
          ) : null}
          {!asking ? qcard : null}
          {partFailed && !card && !qset ? <Status kind="error" title={PART_FAILED} /> : null}
          {page.merged ? (
            // The card's sentence already says where it went and by whom (S-06.rules/4): the note and the link
            <div className="ip-merged">
              {page.merged.note ? <p className="ip-merged-n">“{page.merged.note}”</p> : null}
              <ButtonLink href={page.merged.link.to} variant="soft">
                {page.merged.link.label}
              </ButtonLink>
            </div>
          ) : null}
          {page.actions.restore || page.actions.open_other ? (
            <div className="ip-card-acts">
              {page.actions.open_other ? (
                <ButtonLink href={page.actions.open_other.to} variant="soft">
                  {page.actions.open_other.label}
                </ButtonLink>
              ) : null}
              {page.actions.restore ? (
                <Button variant="soft" disabled={busy} onClick={() => void restore(page.actions.restore!)}>
                  {page.actions.restore.label}
                </Button>
              ) : null}
            </div>
          ) : null}
          {d ? (
            // L-DECIDE/6: "Ask to join the build team" after a Pick, then the line it leaves (J-REVIEW/6, BLD-E053)
            <AskToJoin
              ideaId={ref}
              d={d}
              say={setSaid}
              failed={setFailed}
              away={() => title.current?.focus()}
            />
          ) : null}
          {failed ? <Status kind="error" title={TRY_AGAIN} /> : null}
        </div>
      </article>
      <p className="vh" role="status">
        {said}
      </p>
      {/* TODO(lane E): live updates when the desk opens, asks or decides (S-06.rules/5, A-API.idea-events): no
          events endpoint in contracts/api.ts yet. */}

      {track ? (
        <section className="ip-sec ip-where" aria-labelledby="ip-where-h">
          <h2 id="ip-where-h" className="ip-h2">
            Where it is
          </h2>
          <Track stages={track} />
        </section>
      ) : null}

      {windowLine ? (
        <div className={windowLine.open ? "ip-window is-open" : "ip-window"}>
          {windowLine.phone_line ? (
            <p>
              <span className="ip-desk">{windowLine.line}</span>
              <span className="ip-phone">{windowLine.phone_line}</span>
            </p>
          ) : (
            <p>{windowLine.line}</p>
          )}
          {"countdown" in windowLine && windowLine.countdown ? (
            <Pill variant={windowLine.countdown.variant}>{windowLine.countdown.label}</Pill>
          ) : null}
        </div>
      ) : null}

      <div className="ip-cols">
        <div className="ip-main">
          {d?.decision.reason && !reversed ? (
            <section className="ip-sec ip-reason" aria-labelledby="ip-reason-h">
              <h2 id="ip-reason-h" className="ip-h2">
                {d.decision.reason_heading}
              </h2>
              <blockquote className="ip-reason-q">“{d.decision.reason}”</blockquote>
              <p className="ip-reason-by">{capital(d.decision.by_line)}</p>
            </section>
          ) : null}

          <section className="ip-sec" aria-labelledby="ip-shared-h">
            <h2 id="ip-shared-h" className="ip-h2">
              What you shared
            </h2>
            <p className="ip-intro">{page.shared.intro}</p>
            <dl className="ip-dl">
              {page.shared.rows.map((r) => (
                <div key={r.part} className="ip-dl-row">
                  <dt>{r.label}</dt>
                  <dd>
                    {r.part === "cost" && r.figures ? <Worth row={r} /> : <p className="ip-val">{r.value}</p>}
                    <Answers answers={r.answers} />
                  </dd>
                </div>
              ))}
              {h.chips.length ? (
                <div className="ip-dl-row">
                  <dt>Hidden</dt>
                  <dd>
                    <ul className="ip-chips">
                      {h.chips.map((c) => (
                        <li key={c} className="ip-chip">
                          {c}
                        </li>
                      ))}
                      {h.more > 0 ? (
                        <li>
                          <button
                            type="button"
                            className="ip-chip ip-chip-more"
                            aria-haspopup="dialog"
                            aria-label={h.more_accessible_name ?? `See all ${h.all.length} hidden details`}
                            onClick={(e) => setSheet({ name: "hidden", from: e.currentTarget })}
                          >
                            {h.more_label ?? `+${h.more} more`}
                          </button>
                        </li>
                      ) : null}
                    </ul>
                    <p className="ip-sub">{h.note}</p>
                  </dd>
                </div>
              ) : null}
              <div className="ip-dl-row">
                <dt>{at.label}</dt>
                <dd>
                  {at.files.length ? (
                    <ul className="ip-files">
                      {at.files.map((x) => (
                        <FileTile key={x.id} f={x} />
                      ))}
                    </ul>
                  ) : (
                    <p className="ip-val ip-mute">
                      {at.empty_line}
                      {at.add ? (
                        <>
                          {" "}
                          <Link href={at.add.to}>{at.add.label}</Link>
                        </>
                      ) : null}
                    </p>
                  )}
                  <Answers answers={at.answers} />
                </dd>
              </div>
              <div className="ip-dl-row">
                <dt>{f.label}</dt>
                <dd>
                  {f.text ? (
                    <>
                      <p className="ip-val ip-clamp">{f.text}</p>
                      {f.more_label ? (
                        <button
                          type="button"
                          className="ip-more"
                          aria-haspopup="dialog"
                          onClick={(e) => setSheet({ name: "fix", from: e.currentTarget })}
                        >
                          {f.more_label}
                        </button>
                      ) : null}
                    </>
                  ) : (
                    <p className="ip-val ip-mute">
                      {f.empty_line}
                      {f.add ? (
                        <>
                          {" "}
                          <Link href={f.add.to}>{f.add.label}</Link>
                        </>
                      ) : null}
                    </p>
                  )}
                  <Answers answers={f.answers} />
                </dd>
              </div>
            </dl>
          </section>
        </div>

        <aside className="ip-side" aria-label="The conversation and similar ideas">
          {conv ? (
            <section className="card ip-side-card" aria-labelledby="ip-conv-h">
              {/* The heading with "Open the conversation" beside it, then the line about the review desk, as
                  Status.md and PhoneStatus.md draw them; the link goes to S-08 */}
              <div className="ip-conv-head">
                <h2 id="ip-conv-h" className="ip-h2">
                  {conv.heading}
                </h2>
                <Link className={buttonClass("text")} href={conv.link.to}>
                  {conv.link.label}
                </Link>
              </div>
              {deskLine ? <p className="ip-side-l">{deskLine}</p> : null}
              {conv.empty_line ? (
                <p className="ip-side-l">
                  {conv.phone_empty_line ? (
                    <>
                      <span className="ip-desk">{conv.empty_line}</span>
                      <span className="ip-phone">{conv.phone_empty_line}</span>
                    </>
                  ) : (
                    conv.empty_line
                  )}
                </p>
              ) : null}
              {/* TODO(lane F): the conversation's latest entries (S-06.layout/8, L-CONVO): no entries field on
                  SharerView yet; the card carries the count, its lines and the link. */}
            </section>
          ) : null}
          <SimilarCard similar={page.similar} />
        </aside>
      </div>

      {h.all.length ? (
        <Sheet open={sheet?.name === "hidden"} onClose={closeSheet} title={h.note}>
          <ul className="ip-hidden-all">
            {h.all.map((x, i) => (
              <li key={`${x.masked}-${i}`}>
                <span className="ip-chip">{x.masked}</span> <span className="ip-sub">{x.where}</span>
              </li>
            ))}
          </ul>
        </Sheet>
      ) : null}
      {f.text ? (
        <Sheet open={sheet?.name === "fix"} onClose={closeSheet} title={f.label}>
          <p className="ip-val">{f.text}</p>
          {f.needs ? <p className="ip-sub">{f.needs}</p> : null}
        </Sheet>
      ) : null}
    </div>
  );
}
