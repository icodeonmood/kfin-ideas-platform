"use client";

/**
 * S-R2 The idea, for the reviewer. Left: listen, attachments and artefacts, the idea part by part with questions and
 * answers under each, what it's worth, what merged-in ideas brought, similar ideas. Right: the panel, sticky, in its
 * working states (L-REVIEW.panel): reviewing (asking first is optional and folded away), sent, answered, deciding,
 * decided. The words are the worker's (A-API.conventions/6) or the board's, with names for the sharer (BLD-E008).
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useReducer, useRef, useState, type RefObject } from "react";

import { IdeaPreviewDialog } from "@/components/preview/idea-preview";
import { ListenPlayer } from "@/components/review/listen-player";
import { MergeSheet } from "@/components/review/merge-sheet";
import { WorthEditor, WorthView } from "@/components/review/worth";
import { Button } from "@/components/ui/button";
import { ChoiceChips } from "@/components/ui/chips";
import { Field, FieldMsg } from "@/components/ui/field";
import { Pill, type PillVariant } from "@/components/ui/pill";
import { QuestionBox } from "@/components/ui/question-box";
import type {
  DecisionChoice,
  IdeaPart,
  ReturnIn,
  ReviewerArtefact,
  ReviewerContribution,
  ReviewerIdeaResponse,
  ReviewerPanel,
  ReviewerPart,
  ReviewerQuestion,
  ReviewerSimilar,
  SuggestedQuestionsResponse,
  TimeToAnswer,
  WorthFigures,
  WorthTile,
} from "@/lib/contracts";
import { countdown, countdownLabel, nextTickMs } from "@/lib/desk/countdown";
import { CUSTOMER_DETAIL, fileHref, openFileName } from "@/lib/desk/files";
import { bottomBar, initialPanel, panelReducer, readyLine, storedQueue } from "@/lib/desk/panel";
import { call, type ApiError } from "@/lib/desk/reply";
import { answerDue, clockLabel, dayLabel, deadlineLabel } from "@/lib/desk/when";
import { sparkBurst } from "@/lib/motion/spark";

export type ReviewPromises = {
  reasonMin: number;
  mergeNoteMin: number;
  answerDays: number[];
  answerDefaultDays: number;
  deadlineHour: number;
  extendDays: number;
  returnMonths: number[];
  returnDefaultMonths: number;
  windowDays: number;
  windowMaxMonths: number;
};

const PARTS: { value: IdeaPart; label: string }[] = [
  { value: "summary", label: "The problem" },
  { value: "often", label: "How often" },
  { value: "who", label: "Who it affects" },
  { value: "cost", label: "What it’s worth" },
  { value: "evidence", label: "Attached" },
  { value: "fix", label: "Fix" },
];
const PART_NAME = Object.fromEntries(PARTS.map((p) => [p.value, p.label])) as Record<IdeaPart, string>;
/** "Ask about The problem", and "Ask about what it’s worth" in the board's own case. */
const ASK_NAME: Record<IdeaPart, string> = { ...PART_NAME, cost: "what it’s worth" };
const TIMES: TimeToAnswer[] = ["1d", "3d", "1w"];
const RETURNS: ReturnIn[] = ["1m", "3m", "6m"];
const PILL: Record<string, PillVariant> = { blue: "blue", warn: "warn", ok: "ok", neutral: "neutral" };
const DECISION_PILL: Record<DecisionChoice, PillVariant> = {
  pick: "blue",
  not_now: "warn",
  not_picked: "neutral",
};
const SEND_ANYWAY = "Send anyway";

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}
function daysWord(n: number) {
  return n === 7 ? "1 week" : plural(n, "day");
}
function monthsWord(n: number) {
  return plural(n, "month");
}
/** "Today, 4:32 pm" or "Friday 13 November, 4:32 pm". */
function whenSaid(at: string | Date, now: Date) {
  const today = dayLabel(at, now) === dayLabel(now, now);
  return `${today ? "Today" : dayLabel(at, now)}, ${clockLabel(at)}`;
}

/** A desk action; a paused feature or a bare refusal shows its banner or the failure line (non-negotiable 9). */
function send<T>(url: string, method: "POST" | "PUT", body?: unknown) {
  return call<T>(url, { method, body });
}

/** V-FIELDS/3: focus a field that blocks a send, in the middle of the view so no sticky bar covers it. */
function toField(el: HTMLElement | null | undefined) {
  if (!el) return;
  el.scrollIntoView({ block: "center", behavior: "smooth" });
  el.focus({ preventScroll: true });
}

/** The time now, refreshed on each whole minute: every countdown label can only change then. */
function useMinute(): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const tick = () => {
      setNow(new Date());
      timer = setTimeout(tick, nextTickMs());
    };
    timer = setTimeout(tick, nextTickMs());
    return () => clearTimeout(timer);
  }, []);
  return now;
}

/**
 * The page is read again after each send, and a new state mounts a fresh panel (page.tsx keys it by state), so the
 * focus asked for by S-R2.rules/4 is carried across that remount here.
 */
let focusPanelOnMount = false;
let carried: { ideaId: string; banner: string; at: number } | null = null;
/** A carried banner is for the new read straight after a merge, never for a later visit to the same idea. */
const CARRY_MS = 15_000;
function refreshInto(router: ReturnType<typeof useRouter>) {
  focusPanelOnMount = true;
  router.refresh();
}

/** "70 to 150" back out of "70 to 150 hours a month", for the editor's fields. */
function typed(figure: { text: string } | undefined): string | undefined {
  return figure?.text.replace(/ (?:hours? )?a month$/, "").replace(/ a month$/, "");
}

export function ReviewerIdea({
  page,
  suggested,
  numbers,
}: {
  page: ReviewerIdeaResponse;
  suggested: SuggestedQuestionsResponse;
  numbers: ReviewPromises;
}) {
  const router = useRouter();
  const first = page.sharer.first_name;
  const idea = page.idea;
  const timeCodes = Object.fromEntries(
    TIMES.map((t, i) => [t, numbers.answerDays[i] ?? [1, 3, 7][i]!]),
  ) as Record<TimeToAnswer, number>;
  const defaultTime = TIMES[numbers.answerDays.indexOf(numbers.answerDefaultDays)] ?? "3d";
  const serverState: "reviewing" | "sent" | "answered" | "decided" =
    page.panel.state === "merged" ? "reviewing" : page.panel.state;
  // J-REVIEW/A1: the reviewer’s own stored set is the starting queue, ready to send (BLD-B244)
  const stored =
    page.can_act && (page.panel.state === "reviewing" || page.panel.state === "answered")
      ? storedQueue(page.panel.queued)
      : null;
  const [panel, dispatch] = useReducer(panelReducer, initialPanel(serverState, defaultTime, stored));
  const [editingWorth, setEditingWorth] = useState(false);
  const [tiles, setTiles] = useState<WorthTile[]>(page.worth.tiles);
  const [revised, setRevised] = useState(page.worth.revised);
  // The reviewer's own figures and note, once saved here, so "Change what it’s worth" opens on them (L-WORTH/2)
  const [mine, setMine] = useState<(WorthFigures & { note: string | null }) | null>(null);
  const [kind, setKind] = useState(idea.kind);
  const [area, setArea] = useState(idea.area);
  const [previewing, setPreviewing] = useState<ReviewerSimilar | null>(null);
  const [merging, setMerging] = useState<string | null>(null);
  const [banner, setBanner] = useState<string | null>(() =>
    carried?.ideaId === idea.id && Date.now() - carried.at < CARRY_MS ? carried.banner : null,
  );
  const [mergedIds, setMergedIds] = useState<Set<string>>(
    () => new Set(page.similar.filter((s) => s.merged).map((s) => s.idea_id)),
  );
  const [errors, setErrors] = useState<{ choice?: string; reason?: string; form?: string }>({});
  const [wording, setWording] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [reminded, setReminded] = useState(false);
  const title = useRef<HTMLHeadingElement>(null);
  const firstRender = useRef(true);
  const worthRef = useRef<HTMLDivElement>(null);
  const similarTitle = useRef<HTMLHeadingElement>(null);
  const sendButton = useRef<HTMLButtonElement>(null);
  const choices = useRef<HTMLFieldSetElement>(null);
  const reasonBox = useRef<HTMLTextAreaElement>(null);
  const now = useMinute();

  // The carried banner shows once
  useEffect(() => {
    carried = null;
  }, [idea.id]);

  // L-REVIEW.open/1: page.tsx opens the idea for a reviewer before it is read (J-REVIEW/1).

  // S-R2.rules/4: focus moves to the panel's title on every state change, including the one a new read brings.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      if (!focusPanelOnMount) return;
      focusPanelOnMount = false;
    }
    title.current?.focus();
  }, [panel.state]);

  const suggestionFor = (part: IdeaPart) => suggested.find((s) => s.part === part)?.text ?? null;
  const queuedFor = (part: IdeaPart) => panel.queued.filter((q) => q.part === part);
  const asking = page.can_act && panel.state === "reviewing";

  function spark() {
    if (sendButton.current) sparkBurst(sendButton.current); // S-R2.rules/3
  }

  async function sendQuestions() {
    setBusy(true);
    const r = await send(`/api/desk/ideas/${encodeURIComponent(idea.id)}/question-sets`, "POST", {
      questions: panel.queued.map((q) => ({ part: q.part, text: q.text, suggested: q.suggested })),
      time_to_answer: panel.timeToAnswer,
    });
    setBusy(false);
    if (!r.ok) return setErrors({ form: r.error.message });
    spark();
    dispatch({ type: "questions_sent" });
    refreshInto(router);
  }

  // L-DECIDE.rules/4, BLD-B236: a reason holding a word the product never says to a sharer comes back once as a
  // 422 wording_check with the words and a plainer way to say each; "Send anyway" sends it as written.
  async function sendDecision(wordingOk = false) {
    setErrors({});
    setWording(null);
    setBusy(true);
    const r = await send(`/api/desk/ideas/${encodeURIComponent(idea.id)}/decision`, "POST", {
      choice: panel.choice ?? undefined,
      reason: panel.reason,
      return_in: panel.choice === "not_now" ? panel.returnIn : undefined,
      joined_with: panel.choice === "pick" ? (panel.joinWith ?? undefined) : undefined,
      wording_ok: wordingOk || undefined,
    });
    setBusy(false);
    if (!r.ok) {
      const e = r.error;
      if (e.code === "wording_check") {
        setWording(e);
        return toField(reasonBox.current);
      }
      // V-FIELDS/3: the field that blocks takes focus, scrolled clear of the panel's bar
      if (e.field === "choice") {
        setErrors({ choice: e.message });
        return toField(choices.current?.querySelector("input"));
      }
      if (e.field === "reason") {
        setErrors({ reason: e.message });
        return toField(reasonBox.current);
      }
      return setErrors({ form: e.message });
    }
    spark();
    dispatch({ type: "decision_sent" });
    refreshInto(router);
  }

  async function giveMoreTime(setId: string) {
    const r = await send(`/api/question-sets/${encodeURIComponent(setId)}/extend`, "POST");
    if (r.ok) router.refresh();
    else setErrors({ form: r.error.message });
  }

  async function remind(setId: string) {
    const r = await send(`/api/question-sets/${encodeURIComponent(setId)}/remind`, "POST");
    if (r.ok) setReminded(true);
    else setErrors({ form: r.error.message });
  }

  function openWorth() {
    setEditingWorth(true);
    worthRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  const due = answerDue(now, panel.timeToAnswer, timeCodes, numbers.deadlineHour);
  const afterDecideBy = page.decide_by.at ? due > new Date(page.decide_by.at) : false;
  const bar = bottomBar(panel, first);
  const reasonLength = panel.reason.trim().length;
  const reasonLabels: Record<DecisionChoice, string> = {
    pick: "Why are you picking it?",
    not_now: "Why not now, and what would change it?",
    not_picked: "Why isn’t it going ahead?",
  };
  const returnMonths = numbers.returnMonths[RETURNS.indexOf(panel.returnIn)] ?? 3;
  const returnDate = new Date(now);
  returnDate.setMonth(returnDate.getMonth() + returnMonths);
  const windowCloses = new Date(now.getTime() + numbers.windowDays * 86_400_000);
  const joinable = page.similar.filter(
    (s) => !mergedIds.has(s.idea_id) && !["merged", "withdrawn"].includes(s.status),
  );
  const allQuestions = page.parts.flatMap((x) => x.questions);

  return (
    <div className="ri">
      <div className="ri-head">
        <Link href="/desk" className="back">
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
            <path
              d="M9 2.5 4.5 7 9 11.5"
              stroke="currentColor"
              strokeWidth="1.6"
              fill="none"
              strokeLinecap="round"
            />
          </svg>
          Review desk
        </Link>
        <p className="ri-ref">
          <Pill variant={PILL[idea.pill] ?? "blue"}>{idea.status_label}</Pill>
          <span className="meta">{idea.id}</span>
        </p>
        <h1 className="h1 ri-title">{idea.title}</h1>
        <p className="meta ri-line">{idea.heading}</p>
      </div>

      <div className="ri-cols">
        <div className="ri-left">
          <ListenPlayer ideaId={idea.id} decided={!page.can_act && page.panel.state === "decided"} />

          <Artefacts
            artefacts={page.artefacts}
            canCompare={page.similar.length > 0}
            ownWords={page.own_words}
            onCompare={() => {
              similarTitle.current?.scrollIntoView({ behavior: "smooth", block: "start" });
              similarTitle.current?.focus({ preventScroll: true });
            }}
          />

          <section className="card ri-parts" aria-label="The idea, part by part">
            {page.parts.map((part) => {
              const queued = queuedFor(part.part);
              return (
                <section key={part.part} className="ri-part" aria-labelledby={`part-${part.part}`}>
                  <div className="ri-part-h">
                    <h2 id={`part-${part.part}`} className="h3">
                      {part.name}
                    </h2>
                    {part.part === "cost" && page.can_act ? (
                      <Button
                        variant="text"
                        aria-expanded={editingWorth}
                        aria-controls="ri-worth"
                        onClick={() => setEditingWorth(true)}
                      >
                        Revise and recategorise
                      </Button>
                    ) : null}
                    {asking ? (
                      <Button
                        variant="line"
                        size="sm"
                        className={queued.length ? "ri-asking" : undefined}
                        aria-label={`Ask about ${ASK_NAME[part.part]}`}
                        aria-pressed={queued.length > 0}
                        onClick={() =>
                          dispatch({
                            type: "ask_about",
                            part: part.part,
                            suggestion: suggestionFor(part.part),
                          })
                        }
                      >
                        {queued.length ? "Asking" : "Ask about this"}
                      </Button>
                    ) : null}
                  </div>
                  {part.part === "cost" ? (
                    <div ref={worthRef} id="ri-worth">
                      {editingWorth ? (
                        <WorthEditor
                          ideaId={idea.id}
                          sharerFirstName={first}
                          kind={kind}
                          area={area}
                          tiles={tiles}
                          initial={
                            mine
                              ? {
                                  hours: typed(mine.hours_month),
                                  cost: typed(mine.cost_month),
                                  revenue: typed(mine.revenue_month),
                                  tools: mine.outside_tools,
                                  note: mine.note ?? undefined,
                                }
                              : // After a reload the figures are the revised tiles; the note is the revision's
                                // (L-WORTH/2)
                                { note: page.worth.revision?.note ?? undefined }
                          }
                          onCancel={() => setEditingWorth(false)}
                          onSaved={(saved) => {
                            setTiles(saved.tiles);
                            setRevised(true);
                            setMine(saved.reviewer);
                            setKind(saved.kind);
                            setArea(saved.area);
                            setEditingWorth(false);
                          }}
                        />
                      ) : (
                        <WorthView kind={kind} area={area} tiles={tiles} />
                      )}
                    </div>
                  ) : (
                    <p className="body ri-part-t">{part.text || <span className="muted">Not given.</span>}</p>
                  )}
                  {queued.map((q) => (
                    <div key={q.key} className="note ri-q ri-q-draft">
                      <span className="meta">You’ll ask</span>
                      <p className="body">{q.text}</p>
                    </div>
                  ))}
                  {part.questions.map((q) => (
                    <AskedQuestion key={q.id} q={q} />
                  ))}
                </section>
              );
            })}
          </section>

          {page.contributions.length ? <Contributions contributions={page.contributions} /> : null}

          {page.similar.length ? (
            <section className="card ri-sim" aria-labelledby="sim-t">
              <h2 id="sim-t" className="h3" ref={similarTitle} tabIndex={-1}>
                Similar ideas
              </h2>
              <p className="meta">
                The same problem, raised by others. Merge them so one team builds one fix.
              </p>
              {banner ? (
                <p className="note ri-banner" role="status">
                  {banner}
                </p>
              ) : null}
              <ul className="ri-sim-list">
                {page.similar.map((s) => (
                  <li key={s.idea_id} className="ri-sim-row">
                    <span className="ri-sim-b">
                      <button
                        type="button"
                        className="ri-sim-t"
                        aria-haspopup="dialog"
                        onClick={() => setPreviewing(s)}
                      >
                        {s.title}
                      </button>
                      <span className="meta">{s.meta}</span>
                      <span className="meta">{matchLine(s)}</span>
                    </span>
                    <Button
                      variant="text"
                      aria-haspopup="dialog"
                      aria-label={`Preview ${s.title}`}
                      onClick={() => setPreviewing(s)}
                    >
                      Preview
                    </Button>
                    {mergedIds.has(s.idea_id) ? (
                      <Pill variant="neutral">Merged</Pill>
                    ) : page.can_act ? (
                      <Button
                        variant="line"
                        size="sm"
                        aria-label={`Merge with ${s.title}`}
                        onClick={() => setMerging(s.idea_id)}
                      >
                        Merge
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>

        <aside className="panel ri-panel" aria-labelledby="panel-t">
          <div className="ri-panel-in">
            {!page.can_act && page.own ? (
              <>
                <h2 id="panel-t" ref={title} tabIndex={-1} className="h3">
                  Your own idea
                </h2>
                <p className="meta">Another reviewer decides on it. You can read it here.</p>
              </>
            ) : page.panel.state === "merged" ? (
              <>
                <h2 id="panel-t" ref={title} tabIndex={-1} className="h3">
                  Merged with another idea
                </h2>
                <p className="meta">The review desk now decides on the idea it joined.</p>
              </>
            ) : panel.state === "decided" ? (
              <Decided panel={page.panel} first={first} titleRef={title} now={now} />
            ) : panel.state === "deciding" ? (
              <>
                <h2 id="panel-t" ref={title} tabIndex={-1} className="h3">
                  Decide on this idea
                </h2>
                <p className="meta">{first} reads your decision and your reason as soon as you send it.</p>
                <fieldset
                  ref={choices}
                  className="ri-choices"
                  aria-describedby={errors.choice ? "choice-err" : undefined}
                >
                  <legend className="vh">Your decision</legend>
                  {(
                    [
                      ["pick", "Pick", "Take it forward. A build team is chosen next."],
                      ["not_now", "Not now", "Right problem, wrong time. It comes back on a date you set."],
                      [
                        "not_picked",
                        "Not picked",
                        `It won’t go ahead. Say what happens to ${first}’s words.`,
                      ],
                    ] as [DecisionChoice, string, string][]
                  ).map(([value, label, line]) => (
                    <label key={value} className={`choice${panel.choice === value ? " on" : ""}`}>
                      <input
                        type="radio"
                        name="decision"
                        value={value}
                        checked={panel.choice === value}
                        onChange={() => dispatch({ type: "choose", choice: value })}
                      />
                      <span>
                        <strong>{label}</strong> <span className="meta">{line}</span>
                      </span>
                    </label>
                  ))}
                  {errors.choice ? <FieldMsg id="choice-err">{errors.choice}</FieldMsg> : null}
                </fieldset>
                {panel.choice === "pick" && joinable.length ? (
                  <div className="chips ri-join">
                    {joinable.slice(0, 2).map((s) => (
                      <button
                        key={s.idea_id}
                        type="button"
                        className="chip"
                        aria-pressed={panel.joinWith === s.idea_id}
                        onClick={() =>
                          dispatch({
                            type: "join_with",
                            ideaId: panel.joinWith === s.idea_id ? null : s.idea_id,
                          })
                        }
                      >
                        Join it with {s.idea_id}
                      </button>
                    ))}
                  </div>
                ) : null}
                {panel.choice === "not_now" ? (
                  <>
                    <ChoiceChips
                      label="Look at it again in"
                      options={RETURNS.map((r, i) => ({
                        value: r,
                        label: monthsWord(numbers.returnMonths[i] ?? [1, 3, 6][i]!),
                      }))}
                      value={panel.returnIn}
                      onChange={(v) => dispatch({ type: "set_return", returnIn: v as ReturnIn })}
                    />
                    <p className="meta">
                      Comes back to you and {first} on {dayLabel(returnDate, now)}
                    </p>
                  </>
                ) : null}
                <Field
                  label={panel.choice ? reasonLabels[panel.choice] : "Your reason"}
                  multiline
                  help={
                    <>
                      <span className="help-l">{first} reads this word for word.</span>
                      {reasonLength < numbers.reasonMin ? (
                        <span className="help-l">
                          {reasonLength} of at least {numbers.reasonMin} characters
                        </span>
                      ) : null}
                    </>
                  }
                  error={errors.reason}
                  warning={wording?.message}
                >
                  {(p) => (
                    <textarea
                      {...p}
                      ref={reasonBox}
                      rows={4}
                      maxLength={1000}
                      value={panel.reason}
                      onChange={(e) => {
                        setWording(null);
                        dispatch({ type: "type_reason", text: e.target.value });
                      }}
                    />
                  )}
                </Field>
                {wording ? (
                  <div className="ri-wording">
                    {/* The message names every word and the plainer way for the first; the rest are listed */}
                    {(wording.suggestions ?? []).length > 1 ? (
                      <ul className="ri-wording-l" aria-label="Plainer ways to say it">
                        {(wording.suggestions ?? []).slice(1).map((w) => (
                          <li key={w.word} className="meta">
                            For &quot;{w.word}&quot;, {w.suggestion}.
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    <Button variant="line" size="sm" busy={busy} onClick={() => void sendDecision(true)}>
                      {SEND_ANYWAY}
                    </Button>
                  </div>
                ) : null}
                <p className="meta ri-shield">
                  The Ones Committee can review it for {numbers.windowDays} days. Until{" "}
                  {dayLabel(windowCloses, now)} they can reverse it, with a note that goes to {first}. After
                  that, it stands.
                </p>
              </>
            ) : panel.state === "sent" && page.panel.state === "sent" ? (
              <SentOrAnswered
                p={page.panel}
                titleRef={title}
                questions={allQuestions}
                now={now}
                reminded={reminded}
                extendDays={numbers.extendDays}
                onMore={() => void giveMoreTime(page.panel.state === "sent" ? page.panel.set_id : "")}
                onRemind={() => void remind(page.panel.state === "sent" ? page.panel.set_id : "")}
              />
            ) : panel.state === "answered" && page.panel.state === "answered" ? (
              <SentOrAnswered p={page.panel} titleRef={title} questions={allQuestions} now={now} />
            ) : panel.state === "sent" ? (
              // Just sent: the page's new read, with the clock, is on its way
              <h2 id="panel-t" ref={title} tabIndex={-1} className="h3">
                Waiting on {first}
              </h2>
            ) : (
              <>
                <h2 id="panel-t" ref={title} tabIndex={-1} className="h3">
                  Review this idea
                </h2>
                <p className="meta">
                  {revised
                    ? `You’ve revised what it’s worth. ${first} sees your figures next to theirs when you decide.`
                    : page.worth.line}
                </p>
                {page.can_act ? (
                  <>
                    <Button variant="text" className="ri-revise" onClick={openWorth}>
                      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                        <path
                          d="M2 12l1-3 6.5-6.5 2 2L5 11z"
                          stroke="currentColor"
                          strokeWidth="1.3"
                          fill="none"
                        />
                      </svg>
                      {revised ? "Change what it’s worth" : "Revise what it’s worth"}
                    </Button>
                    <div className="ri-ask">
                      <button
                        type="button"
                        className="ri-ask-h"
                        aria-expanded={panel.askOpen}
                        aria-controls="ask-body"
                        onClick={() => dispatch({ type: "toggle_ask" })}
                      >
                        <span>Ask {first} first</span>{" "}
                        <span className="meta">
                          Optional
                          {readyLine(panel) ? <span className="ri-ready"> {readyLine(panel)}</span> : null}
                        </span>
                      </button>
                      {panel.askOpen ? (
                        <div id="ask-body" className="ri-ask-b">
                          <p className="meta">
                            Only if something is unclear. Ask in your own words; each question is pinned to
                            its part of the idea, so {first} answers it right there.
                          </p>
                          <QuestionBox
                            label={`What would you like to ask ${first}?`}
                            parts={PARTS}
                            pinned={panel.draft.part}
                            onPinned={(part) => dispatch({ type: "pin_question", part: part as IdeaPart })}
                            onAdd={(q, part) => {
                              dispatch({ type: "pin_question", part: part as IdeaPart });
                              dispatch({ type: "type_question", text: q, guessed: part as IdeaPart });
                              dispatch({ type: "add_question" });
                            }}
                          />
                          {panel.queued.length ? (
                            <div className="ri-queued">
                              <h3 className="label">
                                Your questions <span className="meta">{panel.queued.length}</span>
                              </h3>
                              <ul>
                                {panel.queued.map((q) => (
                                  <li key={q.key}>
                                    <span className="chip">{PART_NAME[q.part]}</span>
                                    <span className="body">{q.text}</span>
                                    <button
                                      type="button"
                                      className="qx"
                                      aria-label={`Remove: ${q.text}`}
                                      onClick={() => dispatch({ type: "remove_question", key: q.key })}
                                    >
                                      <span aria-hidden="true">×</span>
                                    </button>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ) : null}
                          {suggested.length ? (
                            <div className="ri-sugg">
                              <h3 className="label">Suggested from this idea</h3>
                              <ul>
                                {suggested
                                  .filter((s) => !panel.queued.some((q) => q.text === s.text))
                                  .map((s) => (
                                    <li key={s.text}>
                                      <button
                                        type="button"
                                        className="qsug"
                                        aria-label={`Add: ${s.text}`}
                                        onClick={() =>
                                          dispatch({ type: "add_suggestion", part: s.part, text: s.text })
                                        }
                                      >
                                        <span aria-hidden="true">+</span> {s.text}{" "}
                                        <span className="meta">{PART_NAME[s.part]}</span>
                                      </button>
                                    </li>
                                  ))}
                              </ul>
                            </div>
                          ) : null}
                          <ChoiceChips
                            label="Time to answer"
                            options={TIMES.map((t) => ({ value: t, label: daysWord(timeCodes[t]) }))}
                            value={panel.timeToAnswer}
                            onChange={(v) => dispatch({ type: "set_time", time: v as TimeToAnswer })}
                          />
                          <p className="meta">
                            {first} has until {deadlineLabel(due, now)}.
                          </p>
                          {afterDecideBy ? (
                            <FieldMsg kind="warn">
                              That’s after you decide, so you’d need to move your date.
                            </FieldMsg>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  </>
                ) : null}
              </>
            )}
            {errors.form ? <FieldMsg kind="error">{errors.form}</FieldMsg> : null}
          </div>

          {page.can_act && bar.primary ? (
            <div className="ri-bar">
              {bar.secondary ? (
                <Button
                  variant={panel.state === "deciding" ? "line" : "text"}
                  onClick={() => dispatch({ type: panel.state === "deciding" ? "back" : "decide" })}
                >
                  {bar.secondary}
                </Button>
              ) : null}
              <Button
                ref={sendButton}
                variant="primary"
                size={bar.secondary ? "regular" : "full"}
                busy={busy}
                onClick={() => {
                  if (panel.state === "deciding") void sendDecision();
                  else if (panel.queued.length && panel.state === "reviewing") void sendQuestions();
                  else dispatch({ type: "decide" });
                }}
              >
                {bar.primary}
              </Button>
            </div>
          ) : null}
          {page.can_act && panel.state === "answered" ? (
            <div className="ri-bar-foot">
              <span className="meta">
                {page.panel.state === "answered" ? page.panel.decide_by_line : null}
              </span>
              <Button variant="line" size="sm" onClick={() => dispatch({ type: "follow_up" })}>
                Ask a follow-up
              </Button>
            </div>
          ) : null}
        </aside>
      </div>

      {/* S-R2.rules/5: the preview and the merge sheet mount at the page root */}
      <IdeaPreviewDialog
        ideaId={previewing?.idea_id ?? ""}
        view="reviewer"
        open={previewing !== null}
        onClose={() => setPreviewing(null)}
        onPrimary={page.can_act ? (id) => setMerging(id) : undefined}
        primaryDone={previewing && mergedIds.has(previewing.idea_id) ? "Merged" : undefined}
        matchReason={previewing ? matchLine(previewing) : undefined}
        compareWith={{ name: first }}
        compareWithId={idea.id}
        fullHref={previewing ? `/desk/ideas/${encodeURIComponent(previewing.idea_id)}` : undefined}
      />
      {merging ? (
        <MergeSheet
          ideaId={idea.id}
          otherId={merging}
          onClose={() => setMerging(null)}
          onMerged={(m) => {
            setBanner(m.banner);
            setMergedIds((s) => new Set(s).add(merging));
            setMerging(null);
            // When this idea is the one that joined, its status changes and the page mounts afresh: the banner
            // stays (C-SHEET-MERGE.after)
            carried = { ideaId: idea.id, banner: m.banner, at: Date.now() };
            router.refresh();
          }}
        />
      ) : null}
    </div>
  );
}

/** The match line under a similar idea and in its preview: "Close match: …" or "Related: …" (DeskIdea board). */
function matchLine(s: ReviewerSimilar): string {
  return `${s.strength === "close" ? "Close match" : "Related"}: ${s.reason}`;
}

/** A file's own row: its badge, name, line, the customer-detail label (DEC-107) and "Open" where a route can open
 * it (`fileHref`, BLD-B243). Seam: lane C's "Hide this" (a blacked-out copy, C-HIDDEN) joins "Open" here once it is
 * served for the desk. */
function FileArtefact({ a }: { a: ReviewerArtefact }) {
  const ext = (a.title.split(".").pop() ?? "").toUpperCase().slice(0, 4);
  const href = fileHref(a);
  return (
    <li className="tile ri-art">
      <span className="fbadge ri-art-ic ri-art-file" aria-hidden="true">
        {ext}
      </span>
      <span className="ri-art-b">
        <strong>{a.title}</strong>
        <span className="meta">{a.line}</span>
        {a.customer_detail ? (
          <span>
            <Pill variant="warn">{CUSTOMER_DETAIL}</Pill>
          </span>
        ) : null}
      </span>
      {href ? (
        <a className="tb blue" href={href} aria-label={openFileName(a.title, Boolean(a.customer_detail))}>
          {a.action}
        </a>
      ) : null}
    </li>
  );
}

function OwnWords({
  words,
  open,
  id,
}: {
  words: ReviewerIdeaResponse["own_words"];
  open: boolean;
  id: string;
}) {
  return open ? (
    <div id={id} className="well ri-words">
      {words.map((m) => (
        <p key={m.seq} className="body">
          {m.text}
        </p>
      ))}
    </div>
  ) : null;
}

/** S-R2.left/2: "Everything that came with the idea": files, the sharer's own words, similar ideas found, draft history. */
function Artefacts({
  artefacts,
  canCompare,
  ownWords,
  onCompare,
}: {
  artefacts: ReviewerArtefact[];
  ownWords: ReviewerIdeaResponse["own_words"];
  /** "Compare" scrolls to Similar ideas; with none listed there it is not shown. */
  canCompare: boolean;
  onCompare: () => void;
}) {
  const [wordsOpen, setWordsOpen] = useState(false);
  return (
    <section className="card ri-arts" aria-labelledby="arts-t">
      <div className="ri-card-h">
        <h2 id="arts-t" className="h3">
          Attachments and artefacts
        </h2>
        <span className="meta">Everything that came with the idea</span>
      </div>
      <ul className="ri-arts-list">
        {artefacts.map((a, i) =>
          a.kind === "file" ? (
            <FileArtefact key={`file-${a.id ?? i}`} a={a} />
          ) : (
            <li key={`${a.kind}-${i}`} className="tile ri-art">
              <span className={`fbadge ri-art-ic ri-art-${a.kind}`} aria-hidden="true" />
              <span className="ri-art-b">
                <strong>{a.title}</strong>
                <span className="meta">{a.line}</span>
              </span>
              {a.kind === "own_words" ? (
                <Button
                  variant="text-blue"
                  aria-expanded={wordsOpen}
                  aria-controls="ri-own-words"
                  onClick={() => setWordsOpen((o) => !o)}
                >
                  {a.action}
                </Button>
              ) : a.kind === "similar_found" && canCompare ? (
                <Button variant="text-blue" onClick={onCompare}>
                  {a.action}
                </Button>
              ) : // Draft history ("See changes") opens once A-API's idea versions route is served; until then
              // the row says how many versions there are and what changed.
              null}
            </li>
          ),
        )}
      </ul>
      <OwnWords words={ownWords} open={wordsOpen} id="ri-own-words" />
    </section>
  );
}

/** A question the desk asked, under its part: who asked and when, its state, the words, then the answer. */
function AskedQuestion({ q }: { q: ReviewerQuestion }) {
  return (
    <div className="ri-q">
      <p className="meta">{q.asked_line}</p>
      <p className="meta ri-q-state">{q.state}</p>
      <p className="body ri-q-t">{q.text}</p>
      {q.answer ? (
        <div className="ri-a">
          <p className="meta">{q.answer.line}</p>
          <p className="body">{q.answer.text}</p>
          {q.answer.files.length ? (
            <ul className="ri-a-files" aria-label="Files with this answer">
              {q.answer.files.map((f) => (
                <li key={f.id} className="meta">
                  <span>{f.name}</span>
                  {f.hidden ? <span>{f.hidden}</span> : null}
                  {f.customer_detail ? <Pill variant="warn">{CUSTOMER_DETAIL}</Pill> : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function ContributionPart({ part }: { part: ReviewerPart }) {
  if (!part.text && !part.questions.length) return null;
  return (
    <div className="ri-part">
      <p className="label">{part.name}</p>
      {part.text ? <p className="body ri-part-t">{part.text}</p> : null}
      {part.questions.map((q) => (
        <AskedQuestion key={q.id} q={q} />
      ))}
    </div>
  );
}

/** L-MERGE.effects/3: what each idea merged into this one brought, under its sharer's first name. */
function Contributions({ contributions }: { contributions: ReviewerContribution[] }) {
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  return (
    <section className="card ri-contribs" aria-labelledby="contribs-t">
      <h2 id="contribs-t" className="h3">
        Merged into this idea
      </h2>
      {contributions.map((c) => {
        const wordsId = `ri-words-${c.idea_id}`;
        const wordsOpen = open.has(c.idea_id);
        return (
          <section key={c.idea_id} className="ri-contrib" aria-labelledby={`contrib-${c.idea_id}`}>
            <h3 id={`contrib-${c.idea_id}`} className="h3">
              {c.label}
            </h3>
            <p className="meta">{c.title}</p>
            {c.parts.map((p) => (
              <ContributionPart key={p.part} part={p} />
            ))}
            {c.files.length || c.own_words.length ? (
              <ul className="ri-arts-list">
                {c.files.map((f, i) => (
                  <FileArtefact key={`file-${f.id ?? i}`} a={f} />
                ))}
                {c.own_words.length ? (
                  <li className="tile ri-art">
                    <span className="fbadge ri-art-ic ri-art-own_words" aria-hidden="true" />
                    <span className="ri-art-b">
                      <strong>{c.sharer.first_name}’s own words</strong>
                    </span>
                    <Button
                      variant="text-blue"
                      aria-expanded={wordsOpen}
                      aria-controls={wordsId}
                      onClick={() =>
                        setOpen((s) => {
                          const next = new Set(s);
                          if (next.has(c.idea_id)) next.delete(c.idea_id);
                          else next.add(c.idea_id);
                          return next;
                        })
                      }
                    >
                      Read<span className="vh"> {c.sharer.first_name}’s own words</span>
                    </Button>
                  </li>
                ) : null}
              </ul>
            ) : null}
            <OwnWords words={c.own_words} open={wordsOpen} id={wordsId} />
          </section>
        );
      })}
    </section>
  );
}

function SentOrAnswered({
  p,
  titleRef,
  questions,
  now,
  reminded,
  extendDays,
  onMore,
  onRemind,
}: {
  p: Extract<ReviewerPanel, { state: "sent" | "answered" }>;
  titleRef: RefObject<HTMLHeadingElement | null>;
  questions: ReviewerQuestion[];
  now: Date;
  reminded?: boolean;
  extendDays?: number;
  onMore?: () => void;
  onRemind?: () => void;
}) {
  // The clock ticks here as on the desk (L-QUESTIONS.clock/1): "3 days to answer", "07:38 to answer", "Overdue by …"
  const live = countdown(p.due_at, now);
  const answeredAt = questions
    .map((q) => q.answer?.at)
    .filter((t): t is string => Boolean(t))
    .sort()
    .pop();
  return (
    <>
      <h2 id="panel-t" ref={titleRef} tabIndex={-1} className="h3">
        {p.title}
      </h2>
      {p.state === "sent" ? (
        <>
          <p className="ri-clock">
            <Pill variant={live.variant === "normal" ? "neutral" : live.variant}>
              {countdownLabel(live, "to answer")}
            </Pill>
          </p>
          <p className="meta">{p.sent_line}</p>
        </>
      ) : (
        <>
          {p.spare_line ? <p className="body">{p.spare_line}</p> : null}
          {answeredAt ? <p className="meta">{whenSaid(answeredAt, now)}</p> : null}
        </>
      )}
      <ul className="ri-sent-qs">
        {questions.map((q) => (
          <li key={q.id}>
            <span className="body">{q.text}</span>
            <span className="meta">{q.state}</span>
          </li>
        ))}
      </ul>
      {p.state === "sent" && onMore && onRemind ? (
        <div className="ri-sent-acts">
          <Button variant="text" onClick={onMore}>
            Give {extendDays ?? 2} more {(extendDays ?? 2) === 1 ? "day" : "days"}
          </Button>
          <Button variant="line" size="sm" disabled={reminded} onClick={onRemind}>
            {reminded ? "Reminded, just now" : "Send a reminder"}
          </Button>
        </div>
      ) : null}
    </>
  );
}

/** S-R2.panel/6 Decided, in the reviewer's words from the worker (ReviewerDecisionLines), with the committee's window
 * as it stands: open with its progress, or reversed with the committee's note, or closed. */
function Decided({
  panel,
  first,
  titleRef,
  now,
}: {
  panel: ReviewerPanel;
  first: string;
  titleRef: RefObject<HTMLHeadingElement | null>;
  now: Date;
}) {
  if (panel.state !== "decided") {
    // Just sent: the page's new read is on its way
    return (
      <h2 id="panel-t" ref={titleRef} tabIndex={-1} className="h3">
        Decision sent to {first}
      </h2>
    );
  }
  const { decision: d, lines } = panel;
  const choice = d.decision.choice;
  const opens = new Date(d.window.opens_at).getTime();
  const closes = new Date(d.window.closes_at).getTime();
  const progress = closes > opens ? Math.min(1, Math.max(0, (now.getTime() - opens) / (closes - opens))) : 1;
  const open = d.window.state === "open" || d.window.state === "extended";
  return (
    <>
      <h2 id="panel-t" ref={titleRef} tabIndex={-1} className="h3">
        {lines.title}
      </h2>
      <p className="ri-decided">
        {choice ? <Pill variant={DECISION_PILL[choice]}>{d.decision.label}</Pill> : null}
        <span className="meta">{lines.sent_line}</span>
      </p>
      {choice === "not_now" && d.return_at ? (
        <p className="meta">
          Comes back to you and {first} on {dayLabel(d.return_at, now)}
        </p>
      ) : null}
      <h3 className="label">{lines.reason_heading}</h3>
      <blockquote className="well ri-reason">{d.decision.reason}</blockquote>
      <h3 className="label">{lines.committee_heading}</h3>
      {d.reversal ? (
        <>
          <p className="body">
            {d.reversal.now_line} {d.reversal.now_by_line}
          </p>
          <blockquote className="well ri-reason">{d.reversal.note}</blockquote>
          <p className="meta">
            {d.reversal.reversed_line}. {d.reversal.final_line}
          </p>
        </>
      ) : (
        <>
          {lines.window_state ? <p className="body">{lines.window_state}</p> : null}
          {open ? (
            <div className="ri-progress" aria-hidden="true">
              <i style={{ width: `${progress * 100}%` }} />
            </div>
          ) : null}
          {lines.window_line ? (
            <p className="meta">{lines.window_line}</p>
          ) : d.window.closed_line ? (
            <p className="meta">{d.window.closed_line}</p>
          ) : null}
        </>
      )}
    </>
  );
}
