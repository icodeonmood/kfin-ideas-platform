"use client";

/**
 * C-PREVIEW: a quick look at someone else's idea without leaving the screen (BLD-C100 to BLD-C104).
 *
 * Opened from "Preview" or an idea's title on Check it (`S-04`, `S-04B`, `S-05`), Status (`S-06`), crew cards (lane F)
 * and the reviewer's similar ideas (`S-R2`, lane B). Two views:
 * - sharer: "They’re looking for", the note and "Team up" (C-PREVIEW.anatomy/4, /6, /7);
 * - reviewer: "Next to {name}’s", a three-row comparison, and "Merge".
 *
 * Behaviour (C-PREVIEW.behaviour, F-MOTION.focus): mounted at the page root through a portal; focus moves inside on
 * open, is trapped there, and returns to the opener on close; Escape, the cross and a click on the backdrop close it.
 * The footer button closes the preview first, then hands the idea to the caller, which opens C-SHEET-TEAMUP or
 * C-SHEET-MERGE.
 *
 * Privacy (non-negotiable 7, DEC-104): it shows only what `IdeaPreview` carries. `in_their_words` is already masked
 * by the API; nothing else about the idea is fetched or shown, and the comparison rows show only for reviewers.
 */
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type JSX,
  type KeyboardEvent,
} from "react";
import { createPortal } from "react-dom";

import type { IdeaPreview } from "@/lib/contracts";
import { ONEPC } from "@/lib/contracts/enums.gen";

import "./idea-preview.css";

type Compare = NonNullable<IdeaPreview["compare"]>;

export interface IdeaPreviewDialogProps {
  ideaId: string;
  /** sharer: "They’re looking for" + note + "Team up"; reviewer: "Next to {name}’s" comparison + "Merge". */
  view: "sharer" | "reviewer";
  open: boolean;
  /** Called on Escape, the cross, the backdrop and before `onPrimary`; focus returns to the opener on close. */
  onClose(): void;
  /** The footer button: the preview closes first, then the caller opens C-SHEET-TEAMUP or C-SHEET-MERGE. */
  onPrimary?(ideaId: string): void;
  /** Replaces the button with a green status, e.g. "Waiting for Ravi", "Merged". */
  primaryDone?: string;
  /** The "Why it matches" blue-wash line. */
  matchReason?: string;
  /**
   * Reviewer view: "Next to {name}’s" (rows from `IdeaPreview.compare` and `IdeaPreview.compare_with`). Without it
   * the name comes from `compare_with.owner`.
   */
  compareWith?: { name: string };
  /** The idea this one is compared with, sent as `?compare_with=`; the route adds `compare_with` for reviewers. */
  compareWithId?: string;
  /** Optional prefetched data; otherwise GET /api/ideas/:id/preview. */
  preview?: IdeaPreview;
  /** The sharer's note ends "Your draft stays yours." (Check it, the default) or "Your idea stays yours." (Status). */
  yours?: "draft" | "idea";
  /** Where "Open the full idea" goes. Defaults to the idea's page. */
  fullHref?: string;
}

/** The words on the pop-up, from the board (C-PREVIEW.anatomy and the prototype's pop-up). No gendered pronouns. */
export const PREVIEW_COPY = {
  close: "Close the preview",
  problemTheirs: "The problem, in their words",
  problemOf: (first: string) => `The problem, in ${first}’s words`,
  lookingFor: "They’re looking for",
  nextTo: (name: string) => `Next to ${name}’s`,
  tableLabel: (first: string, name: string) => `${first}’s idea next to ${name}’s`,
  part: "Part",
  column: (first: string) => `${first}’s`,
  rows: { often: "How often", who: "Who it affects", worth: "What it’s worth" },
  notGiven: "Not given",
  crew: (lead: string, count: number) =>
    count > 1 ? `${lead} leads it, ${count} on its crew` : `${lead} leads it`,
  note: {
    draft: "Teaming up adds you to their crew. Your draft stays yours.",
    idea: "Teaming up adds you to their crew. Your idea stays yours.",
  },
  full: "Open the full idea",
  teamUp: "Team up",
  teamUpOn: (title: string) => `Team up on ${title}`,
  merge: "Merge",
  mergeWith: (title: string) => `Merge with ${title}`,
  shared: (when: string) => `Shared ${when}`,
  loading: "Loading the idea",
  failed: "This idea did not load",
  failedHelp: "Check your connection, then try again.",
  retry: "Try again",
} as const;

const ROWS = ["often", "who", "worth"] as const;

/** GET /api/ideas/:id/preview (A-API.idea-preview), with `?compare_with=` when the caller compares two ideas. */
export function previewUrl(ideaId: string, compareWithId?: string): string {
  const base = `/api/ideas/${encodeURIComponent(ideaId)}/preview`;
  return compareWithId ? `${base}?compare_with=${encodeURIComponent(compareWithId)}` : base;
}

/** "2 November", India time (the reviewer's meta line). */
export function sharedOn(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00+05:30` : iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "long", timeZone: "Asia/Kolkata" });
}

const noSubscribe = () => () => {};

export function IdeaPreviewDialog(props: IdeaPreviewDialogProps): JSX.Element | null {
  // Portals need the page: render nothing on the server and in the first hydration pass.
  const onClient = useSyncExternalStore(
    noSubscribe,
    () => true,
    () => false,
  );
  if (!props.open || !onClient) return null;
  // Keyed so a different idea starts from a clean fetch.
  return createPortal(
    <PreviewDialog key={`${props.ideaId}|${props.compareWithId ?? ""}`} {...props} />,
    document.body,
  );
}

// ---------------------------------------------------------------------------------------------------------------
// Data (BLD-C103)
// ---------------------------------------------------------------------------------------------------------------
type Load<T> = { state: "loading" } | { state: "ready"; data: T } | { state: "error" };

function isPreview(x: unknown): x is IdeaPreview {
  if (!x || typeof x !== "object") return false;
  const p = x as Partial<IdeaPreview>;
  return (
    typeof p.id === "string" &&
    typeof p.title === "string" &&
    typeof p.in_their_words === "string" &&
    !!p.lead &&
    typeof p.lead.name === "string"
  );
}

/** Fetches one preview while `url` is set. The component is keyed by the URL's inputs, so it never changes. */
function usePreview(url: string | null, attempt: number): Load<IdeaPreview> {
  const [load, setLoad] = useState<Load<IdeaPreview>>({ state: "loading" });
  useEffect(() => {
    if (!url) return;
    const ac = new AbortController();
    fetch(url, { headers: { accept: "application/json" }, credentials: "same-origin", signal: ac.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((body: unknown) => setLoad(isPreview(body) ? { state: "ready", data: body } : { state: "error" }))
      .catch(() => {
        // IDs only, and nothing logged: the pop-up shows its own message (non-negotiable 3).
        if (!ac.signal.aborted) setLoad({ state: "error" });
      });
    return () => ac.abort();
  }, [url, attempt]);
  return load;
}

// ---------------------------------------------------------------------------------------------------------------
// The dialog (BLD-C100)
// ---------------------------------------------------------------------------------------------------------------
const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function reducedMotion(): boolean {
  return (
    typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function PreviewDialog(props: IdeaPreviewDialogProps) {
  const { ideaId, view, onClose, onPrimary, compareWithId } = props;
  const titleId = useId();
  const boxRef = useRef<HTMLElement>(null);
  const backRef = useRef<HTMLDivElement>(null);
  const closing = useRef(false);
  const [attempt, setAttempt] = useState(0);

  const fetched = usePreview(props.preview ? null : previewUrl(ideaId, compareWithId), attempt);
  const load: Load<IdeaPreview> = props.preview ? { state: "ready", data: props.preview } : fetched;

  // Focus in on open, trapped while open, back to the opener on close (F-MOTION.focus/1, /2). One effect, so the
  // guard is gone before focus goes back.
  useLayoutEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const box = boxRef.current;
    box?.focus({ preventScroll: true });
    const keepInside = (e: FocusEvent) => {
      if (box && e.target instanceof Node && !box.contains(e.target)) box.focus({ preventScroll: true });
    };
    document.addEventListener("focusin", keepInside);
    const root = document.documentElement;
    const overflow = root.style.overflow;
    root.style.overflow = "hidden";
    return () => {
      document.removeEventListener("focusin", keepInside);
      root.style.overflow = overflow;
      if (opener && opener.isConnected) opener.focus({ preventScroll: true });
    };
  }, []);

  /** Leaving is faster than arriving (F-MOTION.tokens): 180ms, accelerate out; instant with reduced motion. */
  const dismiss = useCallback(
    (then?: () => void) => {
      if (closing.current) return;
      closing.current = true;
      const done = () => {
        onClose();
        then?.();
      };
      const box = boxRef.current;
      const back = backRef.current;
      if (!box || typeof box.animate !== "function" || reducedMotion()) return done();
      const timing: KeyframeAnimationOptions = {
        duration: 180,
        easing: "cubic-bezier(.3,0,.8,.15)",
        fill: "forwards",
      };
      Promise.all([
        box.animate([{ opacity: 1 }, { opacity: 0, transform: "translateY(10px) scale(.97)" }], timing)
          .finished,
        back?.animate([{ opacity: 1 }, { opacity: 0 }], timing).finished,
      ]).then(done, done);
    },
    [onClose],
  );

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      dismiss();
      return;
    }
    if (e.key !== "Tab") return;
    const box = boxRef.current;
    if (!box) return;
    const items = Array.from(box.querySelectorAll<HTMLElement>(FOCUSABLE));
    const first = items[0];
    const last = items[items.length - 1];
    if (!first || !last) {
      e.preventDefault();
      box.focus();
      return;
    }
    const active = document.activeElement;
    if (e.shiftKey && (active === first || active === box)) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && (active === last || !box.contains(active))) {
      e.preventDefault();
      first.focus();
    }
  };

  return (
    <div className="pvwrap" onKeyDown={onKeyDown}>
      <div className="pvback" ref={backRef} aria-hidden="true" onClick={() => dismiss()} />
      <section
        ref={boxRef}
        className="pvm"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-busy={load.state === "loading" ? true : undefined}
        tabIndex={-1}
        data-view={view}
      >
        <button type="button" className="pvx" aria-label={PREVIEW_COPY.close} onClick={() => dismiss()}>
          <CloseIcon />
        </button>
        {load.state === "loading" ? (
          <Loading titleId={titleId} />
        ) : load.state === "error" ? (
          <Failed
            titleId={titleId}
            onRetry={() => {
              setAttempt((n) => n + 1);
            }}
          />
        ) : (
          <PreviewBody
            {...props}
            p={load.data}
            titleId={titleId}
            onPrimaryClick={onPrimary ? () => dismiss(() => onPrimary(ideaId)) : undefined}
          />
        )}
      </section>
    </div>
  );
}

function Loading({ titleId }: { titleId: string }) {
  return (
    <>
      <div className="pvband">
        <span className="pvsk" style={{ width: 120 }} aria-hidden="true" />
        <h2 id={titleId} className="pvt">
          <span className="vh">{PREVIEW_COPY.loading}</span>
          <span className="pvsk" style={{ width: "80%", height: 24 }} aria-hidden="true" />
        </h2>
      </div>
      <div className="pvbody">
        <div className="pvsec" aria-hidden="true">
          <span className="pvsk" style={{ width: "40%" }} />
          <span className="pvsk" style={{ width: "90%" }} />
        </div>
      </div>
      <div className="pvf" />
    </>
  );
}

function Failed({ titleId, onRetry }: { titleId: string; onRetry(): void }) {
  return (
    <>
      <div className="pvband">
        <h2 id={titleId} className="pvt">
          {PREVIEW_COPY.failed}
        </h2>
      </div>
      <div className="pvbody">
        <div className="pvsec">
          <p className="pverr" role="alert">
            {PREVIEW_COPY.failedHelp}
          </p>
        </div>
      </div>
      <div className="pvf">
        {/* TODO(lane D, BLD-C100): swap to <Button variant="line"> from @/components/ui/button. */}
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          {PREVIEW_COPY.retry}
        </button>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------------------------------------------
// What it shows (BLD-C101 sharer, BLD-C102 reviewer)
// ---------------------------------------------------------------------------------------------------------------
function PreviewBody({
  p,
  titleId,
  view,
  matchReason,
  compareWith,
  primaryDone,
  onPrimaryClick,
  yours = "draft",
  fullHref,
}: IdeaPreviewDialogProps & {
  p: IdeaPreview;
  titleId: string;
  onPrimaryClick?: () => void;
}) {
  const reviewer = view === "reviewer";
  const first = p.lead.first_name || p.lead.name;
  const where = [p.area, p.city].filter(Boolean).join(", ");
  const when = reviewer ? sharedOn(p.shared_at) : "";
  const meta = reviewer && when ? `${where}. ${PREVIEW_COPY.shared(when)}` : where;
  const status = ONEPC.enums.idea_status.labels[p.status];
  // "Next to Kavya’s": the caller's name for the other idea's sharer, else the route's `compare_with.owner`.
  const other = p.compare_with;
  const otherName = compareWith?.name || other?.owner.first_name || other?.owner.name;

  return (
    <>
      <div className={p.hue === 2 ? "pvband hue2" : "pvband hue1"}>
        <div className="pvtop">
          {/* TODO(lane D, BLD-C100): swap to <StatusPill status={p.status} /> (band variant) from @/components/ui/pill. */}
          <span className="pill">
            <i aria-hidden="true" />
            {status}
          </span>
          <p className="pvref">{p.id}</p>
        </div>
        <h2 id={titleId} className="pvt">
          {p.title}
        </h2>
        {meta ? <p className="pvmeta">{meta}</p> : null}
      </div>

      <div className="pvbody">
        {matchReason ? (
          <p className="pvwhy">
            <SparkIcon />
            <span>{matchReason}</span>
          </p>
        ) : null}

        <div className="pvsec">
          <h3 className="pvl">{reviewer ? PREVIEW_COPY.problemOf(first) : PREVIEW_COPY.problemTheirs}</h3>
          <p className="pva">{p.in_their_words}</p>
        </div>

        {!reviewer && p.looking_for ? (
          <div className="pvsec">
            <h3 className="pvl">{PREVIEW_COPY.lookingFor}</h3>
            <p className="pva">{p.looking_for}</p>
          </div>
        ) : null}

        {reviewer && otherName ? (
          <CompareTable first={first} name={otherName} mine={p.compare ?? {}} theirs={other ?? {}} />
        ) : null}

        <Crew p={p} />

        {!reviewer ? <p className="pvnote">{PREVIEW_COPY.note[yours]}</p> : null}
      </div>

      <div className="pvf">
        {/* TODO(lane D, BLD-C100): swap to the text variant of <Button href> from @/components/ui/button. */}
        <a className="tb pvfull" href={fullHref ?? `/ideas/${encodeURIComponent(p.id)}`}>
          {PREVIEW_COPY.full}
        </a>
        {primaryDone ? (
          <p className="pvok" role="status">
            <CheckIcon />
            {primaryDone}
          </p>
        ) : onPrimaryClick ? (
          // TODO(lane D, BLD-C100): swap to <Button variant="primary" icon={…}> from @/components/ui/button.
          <button
            type="button"
            className="btn btn-primary pvjoin"
            aria-label={reviewer ? PREVIEW_COPY.mergeWith(p.title) : PREVIEW_COPY.teamUpOn(p.title)}
            onClick={onPrimaryClick}
          >
            {reviewer ? null : <TeamIcon />}
            {reviewer ? PREVIEW_COPY.merge : PREVIEW_COPY.teamUp}
          </button>
        ) : null}
      </div>
    </>
  );
}

/** Reviewer's comparison: How often, Who it affects, What it’s worth; one column per idea (C-PREVIEW.anatomy/4). */
function CompareTable({
  first,
  name,
  mine,
  theirs,
}: {
  first: string;
  name: string;
  mine: Compare;
  theirs: Compare;
}) {
  return (
    <div className="pvsec pvcmp">
      <h3 className="pvl">{PREVIEW_COPY.nextTo(name)}</h3>
      <div className="pvtab" role="table" aria-label={PREVIEW_COPY.tableLabel(first, name)}>
        <div className="pvtr pvth" role="row">
          <span role="columnheader">
            <span className="vh">{PREVIEW_COPY.part}</span>
          </span>
          <span role="columnheader">{PREVIEW_COPY.column(first)}</span>
          <span role="columnheader">{PREVIEW_COPY.column(name)}</span>
        </div>
        {ROWS.map((k) => (
          <div className="pvtr" role="row" key={k}>
            <span role="rowheader">{PREVIEW_COPY.rows[k]}</span>
            <span role="cell">{mine[k] || PREVIEW_COPY.notGiven}</span>
            <span role="cell">{theirs[k] || PREVIEW_COPY.notGiven}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Faces and "Ravi Nair leads it, 4 on its crew" (C-PREVIEW.anatomy/5). */
function Crew({ p }: { p: IdeaPreview }) {
  const faces = p.crew_faces.slice(0, 4);
  return (
    <div className="pvcrew">
      {faces.length ? (
        // TODO(lane D, BLD-C100): swap to <CrewFaces> from @/components/ui/avatar.
        <span className="pvavs">
          {faces.map((f, i) => (
            <span key={f.id} className={`pvav t${(i % 4) + 1}`} role="img" aria-label={f.name} title={f.name}>
              {f.initials}
            </span>
          ))}
        </span>
      ) : null}
      <span>{PREVIEW_COPY.crew(p.lead.name, p.crew_count)}</span>
    </div>
  );
}

function CloseIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

function SparkIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6" />
    </svg>
  );
}

function TeamIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20c.7-3.4 3.3-5.5 6.5-5.5s5.8 2.1 6.5 5.5M18 8v6M15 11h6" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </svg>
  );
}
