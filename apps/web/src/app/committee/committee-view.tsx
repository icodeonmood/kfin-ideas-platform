"use client";

/**
 * S-R4 Ones Committee (L-COMMITTEE): In the window, Reversed and Expired. A row opens in place to read the reason as
 * the sharer read it, extend the window 30 days at a time, or reverse the decision once with a note. Extend acts in
 * place (S-R4.rules/2); a reversal moves the row to Reversed (S-R4.rules/3).
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ChoiceChips } from "@/components/ui/chips";
import { Empty } from "@/components/ui/empty";
import { Field, FieldMsg } from "@/components/ui/field";
import { Pill, type PillVariant } from "@/components/ui/pill";
import { Sorts } from "@/components/ui/sorts";
import { Tabs, tabPanelProps } from "@/components/ui/tabs";
import type {
  CommitteeResponse,
  CommitteeRow,
  CommitteeSort,
  CommitteeTab,
  DecisionChoice,
  ReturnIn,
  ReversingWordsResponse,
} from "@/lib/contracts";
import { call } from "@/lib/desk/reply";
import { sparkBurst } from "@/lib/motion/spark";

const TABS: { value: CommitteeTab; label: string }[] = [
  { value: "window", label: "In the window" },
  { value: "reversed", label: "Reversed" },
  { value: "expired", label: "Expired" },
];
const SORTS: { value: CommitteeSort; label: string }[] = [
  { value: "closing", label: "Closing soonest" },
  { value: "decided", label: "Decided" },
  { value: "area", label: "Area" },
];
const PILL: Record<DecisionChoice, PillVariant> = { pick: "blue", not_now: "warn", not_picked: "neutral" };
const RETURNS: ReturnIn[] = ["1m", "3m", "6m"];
// Not drawn on the board (empty tabs): wording for HR's sign-off (docs/hr-wording/lane-b.md).
const EMPTY: Record<CommitteeTab, { title: string; line: string }> = {
  window: {
    title: "No decisions in the window",
    line: "Each desk decision shows here for 30 days after it is made.",
  },
  reversed: {
    title: "Nothing reversed",
    line: "A decision the committee changes shows here, with its note.",
  },
  expired: {
    title: "Nothing expired yet",
    line: "When a window closes, the decision stands and moves here.",
  },
};

/** A committee action. A paused committee (committee.flow off, 503) shows its banner; a refusal the web gives with a
 * bare code (401, 403) shows F-COPY's failure line; the worker's own refusals show its words (non-negotiable 9). */
function post<T>(url: string, body?: unknown) {
  return call<T>(url, { method: "POST", body });
}

/** The reversal's four lines on one row (S-R4.states, Committee board): each on its own line, and read as sentences,
 * "Now: Picked by Rohan Mehta, Friday 13 November. Reversed Friday 13 November. Final. Kavya has the note." */
function ReversalLines({ reversal }: { reversal: NonNullable<CommitteeRow["reversal"]> }) {
  return (
    <>
      <span className="body cm-line">
        {reversal.now_line} <span className="meta cm-line">{reversal.now_by_line}</span>
      </span>{" "}
      <span className="meta cm-line">
        {reversal.reversed_line}
        <span className="vh">.</span>
      </span>{" "}
      <span className="meta cm-line">{reversal.final_line}</span>
    </>
  );
}

export function CommitteeView({
  initial,
  tab: firstTab,
  sort: firstSort,
  open: firstOpen,
  noteMin,
  returnMonths,
}: {
  initial: CommitteeResponse;
  tab: CommitteeTab;
  sort: CommitteeSort;
  /** A row to open in place, from the sidebar's "Closing soonest" (S-R4.rules/4). */
  open?: string | null;
  noteMin: number;
  returnMonths: number[];
}) {
  const router = useRouter();
  const [data, setData] = useState(initial);
  const [tab, setTab] = useState(firstTab);
  const [sort, setSort] = useState(firstSort);
  const [open, setOpen] = useState<string | null>(
    firstOpen && initial.items.some((r) => r.window_id === firstOpen) ? firstOpen : null,
  );
  const reverseTitle = useRef<HTMLHeadingElement>(null);
  const sendButton = useRef<HTMLButtonElement>(null);
  const [reversing, setReversing] = useState<ReversingWordsResponse | null>(null);
  const [to, setTo] = useState<DecisionChoice | null>(null);
  const [returnIn, setReturnIn] = useState<ReturnIn>("3m");
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<{ to?: string; note?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);
  // A4: one action at a time per row, so a double click extends once (and the reversal is sent once)
  const [pending, setPending] = useState<ReadonlySet<string>>(() => new Set());
  const inFlight = useRef(new Set<string>());
  // The tab and sort on screen now, and the latest list request: a reload that finishes late never puts back an
  // older tab or list (S-R4.rules/3, after a reversal the person may already be on Reversed).
  const view = useRef<{ tab: CommitteeTab; sort: CommitteeSort }>({ tab: firstTab, sort: firstSort });
  const latest = useRef(0);

  // The reversing form takes focus when it opens in place (F-MOTION.focus).
  useEffect(() => {
    if (reversing) reverseTitle.current?.focus();
  }, [reversing]);

  async function load(nextTab: CommitteeTab, nextSort: CommitteeSort) {
    view.current = { tab: nextTab, sort: nextSort };
    const request = ++latest.current;
    setTab(nextTab);
    setSort(nextSort);
    setOpen(null);
    setReversing(null);
    router.replace(`/committee?tab=${nextTab}&sort=${nextSort}`, { scroll: false });
    const res = await fetch(`/api/committee?tab=${nextTab}&sort=${nextSort}`);
    if (!res.ok) return;
    const next = (await res.json()) as CommitteeResponse;
    if (request === latest.current) setData(next);
  }

  function replaceRow(row: CommitteeRow) {
    setData((d) => ({ ...d, items: d.items.map((r) => (r.window_id === row.window_id ? row : r)) }));
  }

  /** Runs `act` for a row unless an action for that row is already on its way. */
  async function once(windowId: string, act: () => Promise<void>) {
    if (inFlight.current.has(windowId)) return;
    inFlight.current.add(windowId);
    setPending(new Set(inFlight.current));
    try {
      await act();
    } finally {
      inFlight.current.delete(windowId);
      setPending(new Set(inFlight.current));
    }
  }

  function extend(row: CommitteeRow) {
    return once(row.window_id, async () => {
      setErrors({});
      const r = await post<CommitteeRow>(
        `/api/committee/windows/${encodeURIComponent(row.window_id)}/extend`,
      );
      if (r.ok) replaceRow(r.body);
      else setErrors({ form: r.error.message });
    });
  }

  async function startReverse(row: CommitteeRow) {
    setErrors({});
    setTo(null);
    setNote("");
    const r = await call<ReversingWordsResponse>(
      `/api/committee/windows/${encodeURIComponent(row.window_id)}/reversing`,
    );
    if (r.ok) setReversing(r.body);
    else setErrors({ form: r.status === 503 ? r.error.message : "This decision can’t be reversed now." });
  }

  function reverse(row: CommitteeRow) {
    return once(row.window_id, async () => {
      setErrors({});
      setBusy(true);
      const r = await post<CommitteeRow>(
        `/api/committee/windows/${encodeURIComponent(row.window_id)}/reverse`,
        {
          to: row.kind === "merge" ? undefined : (to ?? undefined),
          note,
          return_in: to === "not_now" ? returnIn : undefined,
        },
      );
      setBusy(false);
      if (!r.ok) {
        const e = r.error;
        if (e.field === "to") return setErrors({ to: e.message });
        if (e.field === "note") return setErrors({ note: e.message });
        return setErrors({ form: e.message });
      }
      if (sendButton.current) sparkBurst(sendButton.current); // S-R4.rules/3
      setReversing(null);
      setOpen(null);
      await load(view.current.tab, view.current.sort); // the row moves to Reversed and the counts follow (S-R4.rules/3)
    });
  }

  const tabs = TABS.map((t) => ({ ...t, count: data.counts[t.value] }));
  const empty = EMPTY[tab];

  return (
    <div className="rd cm arrive">
      <header className="rd-head">
        <h1 className="h1">Ones Committee</h1>
        <p className="body rd-summary" role="status">
          {data.summary}
        </p>
        <p className="meta cm-explain">{data.explanation}</p>
      </header>

      <div className="rd-bar">
        <Tabs
          id="committee"
          label="Ones Committee"
          tabs={tabs}
          value={tab}
          onChange={(t) => void load(t as CommitteeTab, sort)}
        />
        <Sorts options={SORTS} value={sort} onChange={(s) => void load(tab, s as CommitteeSort)} />
      </div>

      <section {...tabPanelProps("committee", tab)} className="rd-panel">
        {data.items.length === 0 ? (
          <Empty title={empty.title} align="left" level={2}>
            {empty.line}
          </Empty>
        ) : (
          <table className="rd-table cm-table">
            <thead>
              <tr>
                <th scope="col">Idea</th>
                <th scope="col">The review desk’s decision</th>
                <th scope="col">Your window</th>
                <th scope="col">
                  <span className="vh">Action</span>
                </th>
              </tr>
            </thead>
            {data.items.map((row) => {
              const isOpen = open === row.window_id;
              return (
                <tbody key={row.window_id} className={isOpen ? "cm-open" : undefined}>
                  <tr>
                    <td className="rd-idea">
                      <Link href={`/ideas/${encodeURIComponent(row.idea.id)}`} className="rd-title">
                        {row.idea.title}
                      </Link>
                      <span className="meta">{row.idea.meta}</span>
                    </td>
                    <td className="cm-dec">
                      {row.decision.choice ? (
                        <Pill variant={PILL[row.decision.choice]}>{row.decision.label}</Pill>
                      ) : (
                        <Pill variant="neutral">{row.decision.label}</Pill>
                      )}
                      <span className="meta">{row.decision.by_line}</span>
                      <p className="body cm-reason">{row.decision.reason}</p>
                    </td>
                    <td className="cm-win">
                      {row.reversal ? (
                        <ReversalLines reversal={row.reversal} />
                      ) : row.window.closed_line ? (
                        <span className="meta">{row.window.closed_line}</span>
                      ) : (
                        <>
                          {row.window.extended ? <Pill variant="blue">Extended</Pill> : null}
                          <span className="body">{row.window.left}</span>
                          <span className="meta">
                            {row.window.until}
                            {row.window.extended ? `. ${row.window.extended}` : ""}
                          </span>
                        </>
                      )}
                    </td>
                    <td className="rd-act">
                      {/* "Review the decision on …" as the board names it; "See it" keeps its own words at the
                          front of the name (WCAG 2.5.3), where the board has "See the decision on …". The name is
                          an aria-label: a hidden span is laid out as a block and would put a space before the
                          comma ("See it , the decision on …"). */}
                      <Button
                        variant="line"
                        size="sm"
                        aria-expanded={isOpen}
                        aria-controls={`cm-${row.window_id}`}
                        aria-label={`${row.action}${row.action === "Review" ? " the decision on " : ", the decision on "}${row.idea.title}`}
                        onClick={() => {
                          setOpen(isOpen ? null : row.window_id);
                          setReversing(null);
                          setErrors({});
                        }}
                      >
                        {row.action}
                      </Button>
                    </td>
                  </tr>
                  {isOpen ? (
                    <tr className="cm-detail">
                      <td colSpan={4} id={`cm-${row.window_id}`}>
                        {reversing ? (
                          // Reversing opens in place, as a non-modal dialog the board names "Reverse the decision"
                          <form
                            className="cm-reverse"
                            role="dialog"
                            aria-labelledby={`cm-rev-${row.window_id}`}
                            onSubmit={(e) => {
                              e.preventDefault();
                              void reverse(row);
                            }}
                          >
                            <h2
                              id={`cm-rev-${row.window_id}`}
                              className="h3"
                              ref={reverseTitle}
                              tabIndex={-1}
                            >
                              {reversing.title}
                            </h2>
                            <p className="body">{reversing.intro}</p>
                            {reversing.options.length ? (
                              <fieldset
                                className="ri-choices"
                                aria-describedby={errors.to ? "cm-to-err" : undefined}
                              >
                                <legend className="label">Change it to</legend>
                                {reversing.options.map((o) => (
                                  <label key={o.to} className={`choice${to === o.to ? " on" : ""}`}>
                                    <input
                                      type="radio"
                                      name="to"
                                      value={o.to}
                                      checked={to === o.to}
                                      onChange={() => setTo(o.to)}
                                    />
                                    <span>
                                      <strong>{o.label}</strong>
                                      <span className="meta">{o.line}</span>
                                    </span>
                                  </label>
                                ))}
                                {errors.to ? (
                                  <FieldMsg id="cm-to-err" kind="error">
                                    {errors.to}
                                  </FieldMsg>
                                ) : null}
                              </fieldset>
                            ) : null}
                            {to === "not_now" ? (
                              <ChoiceChips
                                label="Look at it again in"
                                options={RETURNS.map((r, i) => {
                                  const n = returnMonths[i] ?? [1, 3, 6][i]!;
                                  return { value: r, label: `${n} month${n === 1 ? "" : "s"}` };
                                })}
                                value={returnIn}
                                onChange={(v) => setReturnIn(v as ReturnIn)}
                              />
                            ) : null}
                            <Field
                              label={reversing.note_label}
                              multiline
                              help={
                                // The board's help line stays; the count is a line of its own until the note is
                                // long enough (S-R4.states, A8)
                                <>
                                  <span className="help-l">{reversing.note_help}</span>
                                  {note.trim().length < noteMin ? (
                                    <span className="help-l">
                                      {note.trim().length} of at least {noteMin} characters
                                    </span>
                                  ) : null}
                                </>
                              }
                              error={errors.note}
                            >
                              {(p) => (
                                // The board's box asks "Why the committee is changing it, in words Kavya will
                                // understand"; the visible label leads the name (WCAG 2.5.3).
                                <textarea
                                  {...p}
                                  rows={3}
                                  maxLength={1000}
                                  value={note}
                                  placeholder={`Why the committee is changing it, in words ${row.sharer.first_name} will understand`}
                                  aria-label={`${reversing.note_label}: why the committee is changing it, in words ${row.sharer.first_name} will understand`}
                                  onChange={(e) => setNote(e.target.value)}
                                />
                              )}
                            </Field>
                            <p className="meta">{reversing.final_line}</p>
                            <div className="cm-acts">
                              <Button type="button" variant="line" onClick={() => setReversing(null)}>
                                Back
                              </Button>
                              <Button
                                ref={sendButton}
                                type="submit"
                                variant="primary"
                                busy={busy || pending.has(row.window_id)}
                                busyLabel="Sending…"
                              >
                                {reversing.send_label}
                              </Button>
                            </div>
                          </form>
                        ) : (
                          <div className="cm-review">
                            <h2 className="label">{row.decision.reason_heading}</h2>
                            <blockquote className="well ri-reason">{row.decision.reason}</blockquote>
                            {row.reversal ? (
                              <>
                                <p className="body">
                                  {row.reversal.now_line} {row.reversal.now_by_line}
                                </p>
                                <blockquote className="well ri-reason">{row.reversal.note}</blockquote>
                                <p className="meta">
                                  {row.reversal.reversed_line}. {row.reversal.final_line}
                                </p>
                              </>
                            ) : (
                              <p className="meta">{row.window.open_line ?? row.window.closed_line}</p>
                            )}
                            {row.window.state === "open" || row.window.state === "extended" ? (
                              <div className="cm-acts">
                                {row.can_extend && row.window.extend_to ? (
                                  <Button
                                    variant="line"
                                    busy={pending.has(row.window_id)}
                                    onClick={() => void extend(row)}
                                  >
                                    {row.window.extend_to}
                                  </Button>
                                ) : row.window.limit_line ? (
                                  <span className="meta">{row.window.limit_line}</span>
                                ) : null}
                                {row.can_reverse ? (
                                  <Button variant="line" onClick={() => void startReverse(row)}>
                                    Reverse the decision
                                  </Button>
                                ) : null}
                              </div>
                            ) : null}
                          </div>
                        )}
                        {errors.form ? (
                          <FieldMsg kind="error">
                            <span role="alert">{errors.form}</span>
                          </FieldMsg>
                        ) : null}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              );
            })}
          </table>
        )}
      </section>
    </div>
  );
}
