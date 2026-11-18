"use client";
/**
 * C-DRAFT-PANEL: the draft as a live document beside the conversation (BLD-C125). Fixed slots so nothing jumps:
 * the title and summary, the four facts as tiles (How often, Who it affects, What it's worth, Area), the hidden
 * details bar (C-HIDDEN), the similar-ideas line (C-PREVIEW on demand), and "Move to Review" pinned to the bottom
 * with its readiness line. The loader (C-DRAFT-LOADER) sits at the top while parts build; each part shows its own
 * skeleton. "Change" opens a part in place; the person's own value is pinned and reads "Your call" (L-DRAFT.pins).
 * On a phone the panel is a bottom sheet that peeks with the title and the loader's tube (C-DRAFT-PANEL.behaviour/6);
 * while parts build the peek reads "Building your draft" and the loader's line (PhoneComposeResume.md, loader=Held for
 * review), and Escape closes the open sheet. Each part that lands is said once in a polite live region, on both
 * layouts (behaviour/2). "Change" is a real disclosure: `aria-expanded`, and focus comes back to it after Done or
 * Escape. One part is edited at a time; `editTitle()` opens the title from a receipt's "Change the title".
 */
import {
  forwardRef,
  useEffect,
  useId,
  useImperativeHandle,
  useRef,
  useState,
  type MouseEvent,
  type ReactNode,
  type RefObject,
} from "react";

import { HiddenDetails, type HiddenActions } from "@/components/compose/hidden";
import { INTERVIEW_COPY, InterviewIntro } from "@/components/compose/interview";
import { DraftLoader, useLoaderClock } from "@/components/compose/draft-loader";
import { IdeaPreviewDialog } from "@/components/preview/idea-preview";
import { IconTick } from "@/components/shell/icons";
import { Button, ButtonLink } from "@/components/ui/button";
import { MultiChips } from "@/components/ui/chips";
import { Field } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { BRINGS_LABEL, type Brings, type DraftPartKey, type Part, type SimilarMatch } from "@/lib/contracts";
import { allIn, hasValue, type Live } from "@/lib/compose/live";
import { LOADER_TITLE, loaderLine } from "@/lib/compose/loader";

export const PANEL_COPY = {
  heading: "Your draft",
  forms: "Forms as you write",
  updating: "Updating",
  upToDate: "Up to date",
  titleWaiting: "Your title appears here",
  waiting: "Waiting for your words",
  titleWhy: "From your first sentence.",
  yourCall: "Your call",
  change: "Change",
  failed: "Couldn't work this out. Add it yourself.",
  fewWords: "Give it a few words.",
  done: "Done",
  move: "Move to Review",
  similarSub: "Colleagues raised something close",
  preview: "Preview",
  phonePeekEmpty: "Forms here as you write. Tap to see it.",
  /** PhoneCompose.md, state Speaking: the peek's line while the draft updates and the run's parts are not known. */
  phoneUpdating: "Updating your draft",
  /** PhoneCompose.md, state Offline. */
  phoneOffline: "Paused while you’re offline",
  /** L-SIMILAR.failure, C-DRAFT-LOADER.failure/2; the same characters as Check it's (c/sort-submit, check.py). */
  similarFailed: "Couldn’t check for similar ideas. The review desk will.",
  /** A receipt's suggestion that opens the title (C-DRAFT-PANEL.behaviour/5). */
  changeTitle: "Change the title",
} as const;

/** S-04.rules/2: the line under "Move to Review". */
export const READINESS = {
  start: "Start your draft first. It forms from your words.",
  more: "Your draft needs a little more first.",
  working: "Still working through your words.",
  finishing: "Finishing your last detail first.",
  ready: "Looks right? Check the sorting and send it.",
} as const;
export type Readiness = keyof typeof READINESS;

/** S-04.rules/2 and L-DRAFT.parts/3, /7: which line "Move to Review" shows. Ready only once nothing is building and the
 * draft has its title, summary and area (`ready`, the worker's `ready`, BLD-C083). A run that ends with the title or
 * the area waiting for words stays at "Your draft needs a little more first."; How often, Who it affects and What
 * it's worth may wait without holding it (L-DRAFT.parts/7, BLD-C157). */
export function readinessOf(s: {
  chars: number;
  minChars: number;
  /** A detail is still on its way from this device. */
  sending: boolean;
  running: boolean;
  ready: boolean;
}): Readiness {
  if (!s.chars || s.chars < s.minChars) return "more";
  if (s.sending) return "finishing";
  if (s.running) return "working";
  // Nothing is building: a failed part waits for the person (C-DRAFT-LOADER.failure/1).
  return s.ready ? "ready" : "more";
}

type FactKey = "often" | "who" | "value" | "area";
type EditKey = FactKey | "title";
const FACTS: { key: FactKey; label: string }[] = [
  { key: "often", label: "How often" },
  { key: "who", label: "Who it affects" },
  { key: "value", label: "What it’s worth" },
  { key: "area", label: "Area" },
];

const BRINGS_ORDER: Brings[] = [
  "saves_time",
  "saves_cost",
  "earns_revenue",
  "less_outside_tools",
  "not_sure",
];

export function factText(key: FactKey | "title", p: Part<unknown>): string {
  const v = p.value;
  if (key === "value" && Array.isArray(v))
    return v.map((b) => BRINGS_LABEL[b as Brings] ?? String(b)).join(", ");
  if (Array.isArray(v)) return v.join(", ");
  return typeof v === "string" ? v : "";
}

/** Flag S1 "Interview" (BLD-C172): before the first telling the panel lists the three questions, and on desktop it
 * keeps listing them while they are asked in the conversation; the phone's sheet holds the card; then the panel is
 * the draft as usual. */
export type PanelInterview = { stage: "intro" } | { stage: "asking"; card: ReactNode; soFar: string };

export type PanelProps = {
  live: Live;
  /** The words have reached the point where parts form (L-DRAFT.parts/3); before that, slots wait. */
  readiness: Readiness;
  /** "Move to Review": where it goes once ready. */
  moveHref: string | null;
  /** Called on "Move to Review" before it goes; `preventDefault()` keeps it here (S1 builds the draft first). */
  onMove?(e: MouseEvent<HTMLAnchorElement>): void;
  /** Set and pin a part (PATCH /api/drafts/:id/parts/:part). Rejects with the refusal's words, if any. */
  onChangePart?(part: DraftPartKey | "summary", value: unknown): Promise<void>;
  hidden: HiddenActions | null;
  onFocusDetail?(id: string | null): void;
  /** A filled part was focused: underline its phrase in the person's text (C-DRAFT-PANEL.behaviour/3). */
  onFocusQuote?(quote: string | null): void;
  /** The empty preview on S-04 before any words (S-04.empty/2): no status beyond "Forms as you write". */
  quiet?: boolean;
  phone?: boolean;
  offline?: boolean;
  /** Focus the box when "Move to Review" is pressed while it cannot go yet (C-BUTTON.states/4). */
  onBlocked?(): void;
  /** Team up from a similar idea's preview (lane F's sheet, C-SHEET-TEAMUP): `open` is C-PREVIEW's `onPrimary`;
   * `waiting` holds, per idea, the line to show once a request is sent ("" when the sheet gave none). */
  teamUp?: {
    open(ideaId: string): void;
    waiting: Record<string, string>;
    /** Lane F's `teamUpOpener`: marks where focus returns when the sheet closes (WCAG 2.4.3, BLD-F074). */
    opener?(ideaId: string): Record<string, string>;
  };
  /** Flag S1 "Interview"; absent or null is the default, the live draft. */
  interview?: PanelInterview | null;
};

export type PanelHandle = {
  /** Opens the title's editor (and the sheet, on a phone): a receipt's "Change the title". */
  editTitle(): void;
};

/** C-DRAFT-PANEL.behaviour/2: the part that landed last, said once ("How often: About 15 times a week …"). */
export function landedLine(live: Live): string {
  const answered = live.loader?.answered ?? {};
  let key: EditKey | "similar" | null = null;
  let at = -Infinity;
  for (const [k, t] of Object.entries(answered)) {
    if (typeof t === "number" && t >= at && !live.updating.includes(k as never)) {
      key = k as EditKey | "similar";
      at = t;
    }
  }
  if (!key) return "";
  const p = live.parts[key] as Part<unknown>;
  const label = key === "title" ? "Title" : key === "similar" ? "" : FACTS.find((f) => f.key === key)!.label;
  if (p.state === "failed")
    return key === "similar" ? PANEL_COPY.similarFailed : `${label}: ${PANEL_COPY.failed}`;
  if (!hasValue(p)) return "";
  if (key === "similar") {
    const n = Array.isArray(p.value) ? p.value.length : 0;
    return `${n} similar ${n === 1 ? "idea" : "ideas"}`;
  }
  return `${label}: ${factText(key, p)}`;
}

/** The header, in the boards' drawn states (Compose.md, ComposeResume.md): "Updating" while a run builds, and only
 * then; once nothing is building, "Up to date" when any part shows a value (all six in, maths/7, or a run that ended
 * with a part still waiting for words, BLD-C157), and "Forms as you write" before any. */
export function panelStatus(live: Live): string {
  if (live.running) return PANEL_COPY.updating;
  const any = (["title", "often", "who", "value", "area"] as const).some((k) => hasValue(live.parts[k]));
  return any ? PANEL_COPY.upToDate : PANEL_COPY.forms;
}

export const DraftPanel = forwardRef<PanelHandle, PanelProps>(function DraftPanel(props, ref) {
  const { live, readiness, moveHref, onMove, phone, offline } = props;
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<EditKey | null>(null);
  const peekRef = useRef<HTMLButtonElement>(null);
  const bodyId = useId();
  const status = panelStatus(live);
  const ready = readiness === "ready" && Boolean(moveHref);
  const title = live.parts.title;
  const now = useLoaderClock(live.loader, !live.running);
  const iv = props.interview ?? null;
  const asking = iv?.stage === "asking" ? iv : null;
  // The phone's sheet opens on the first question (PhoneCompose.md, `simulatorS1=Interview`), once.
  const openedForQuestions = useRef(false);
  useEffect(() => {
    if (!phone || !asking || openedForQuestions.current) return;
    openedForQuestions.current = true;
    setOpen(true);
  }, [phone, asking]);
  // "All 6 parts are in" only when every part shows a value or asks to be added; never because the run ended.
  const all = allIn(live);

  useImperativeHandle(
    ref,
    () => ({
      editTitle: () => {
        if (!props.onChangePart) return;
        setOpen(true);
        setEditing("title");
      },
    }),
    [props.onChangePart],
  );

  const move =
    ready && moveHref ? (
      <ButtonLink href={moveHref} size="full" className="cvgo" onClick={onMove}>
        {PANEL_COPY.move}
      </ButtonLink>
    ) : (
      <Button size="full" className="cvgo" disabled onDisabledClick={props.onBlocked}>
        {PANEL_COPY.move}
      </Button>
    );

  const slots = { ...props, editing, setEditing };
  const questions = iv ? (
    <div className="cvb">
      {iv.stage === "intro" ? (
        <InterviewIntro />
      ) : phone && asking ? (
        <>
          <div className="dhead">
            <span className={`dstat${live.running ? " ing" : ""}`} role="status">
              <i aria-hidden="true" />
              {status}
            </span>
            <button
              type="button"
              className="tb"
              onClick={() => {
                setOpen(false);
                peekRef.current?.focus();
              }}
            >
              {INTERVIEW_COPY.done}
            </button>
          </div>
          {asking.soFar ? <p className="rcpt">{asking.soFar}</p> : null}
          {asking.card}
        </>
      ) : (
        // Desktop: the questions are in the conversation; the panel keeps saying what they are (Compose.md).
        <InterviewIntro />
      )}
    </div>
  ) : null;
  const body = questions ?? (
    <>
      {/* On a phone the one loader is the tube under the peek (C-DRAFT-LOADER.anatomy/3). */}
      {phone ? null : <DraftLoader run={live.loader} done={all} ended={!live.running} phone={false} />}
      <div className="cvb">
        <TitleSlot {...slots} />
        <dl className="rows">
          {FACTS.map((f) => (
            <FactRow key={f.key} fact={f} {...slots} />
          ))}
        </dl>
        {props.hidden ? (
          <HiddenDetails details={live.hidden} actions={props.hidden} onFocusDetail={props.onFocusDetail} />
        ) : null}
        <Similar
          part={live.parts.similar}
          updating={live.updating.includes("similar")}
          teamUp={props.teamUp}
        />
      </div>
    </>
  );
  const landed = (
    <p className="vh" aria-live="polite">
      {iv ? "" : landedLine(live)}
    </p>
  );

  if (phone) {
    // While S1's questions wait, the draft is not shown yet: no loader, and the peek says what comes next.
    const building = !iv && live.running && live.loader !== null;
    const titled = iv?.stage !== "intro" && hasValue(title);
    const peekTitle = building ? LOADER_TITLE : titled ? String(title.value) : PANEL_COPY.heading;
    const peekLine = offline
      ? PANEL_COPY.phoneOffline
      : building && live.loader
        ? loaderLine(live.loader, now)
        : live.running
          ? PANEL_COPY.phoneUpdating
          : asking
            ? INTERVIEW_COPY.peek
            : titled
              ? peekSummary(live)
              : PANEL_COPY.phonePeekEmpty;
    return (
      <section
        className={`dsheet${open ? " open" : ""}`}
        aria-label={PANEL_COPY.heading}
        onKeyDown={(e) => {
          if (e.key !== "Escape" || !open) return;
          e.stopPropagation();
          setOpen(false);
          peekRef.current?.focus();
        }}
      >
        <button
          ref={peekRef}
          type="button"
          className="dpeek"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={() => setOpen((v) => !v)}
        >
          <span className="dpeek-t">{peekTitle}</span>
          <span className="dpeek-s">{peekLine}</span>
        </button>
        <DraftLoader run={iv ? null : live.loader} done={all} ended={!live.running} phone now={now} />
        {landed}
        <div id={bodyId} className="dsheet-b" hidden={!open}>
          <h2 className="cvt">{PANEL_COPY.heading}</h2>
          {body}
        </div>
      </section>
    );
  }

  return (
    <section className="canvas" aria-labelledby={`${bodyId}-h`}>
      <header className="cvh">
        <h2 className="cvt" id={`${bodyId}-h`}>
          {PANEL_COPY.heading}
        </h2>
        <span
          className={`dstat${live.running ? " ing" : status === PANEL_COPY.forms ? " idle" : ""}`}
          role="status"
        >
          <i aria-hidden="true" />
          {status}
        </span>
      </header>
      {landed}
      {body}
      <footer className="cvf">
        <p className="cvfn">{READINESS[readiness]}</p>
        {move}
      </footer>
    </section>
  );
});

type SlotProps = PanelProps & { editing: EditKey | null; setEditing(k: EditKey | null): void };

/** "Change" as a disclosure: focus comes back to its button (`button`) when its editor closes (Done or Escape). */
function useChange(
  key: EditKey,
  props: SlotProps,
  button: RefObject<HTMLButtonElement | null>,
): { open: boolean; editorId: string; toggle(): void; close(): void } {
  const back = useRef(false);
  const editorId = useId();
  const open = props.editing === key && Boolean(props.onChangePart);
  useEffect(() => {
    if (!open && back.current) {
      back.current = false;
      button.current?.focus();
    }
  }, [open, button]);
  return {
    open,
    editorId,
    toggle: () => props.setEditing(open ? null : key),
    close: () => {
      back.current = true;
      props.setEditing(null);
    },
  };
}

/** The phone peek's line: "Hid 3 details, 3 sortings, 2 similar ideas" (PhoneCompose.md). */
export function peekSummary(live: Live): string {
  const bits: string[] = [];
  const hid = live.hidden.filter((d) => d.state === "hidden").length;
  if (hid) bits.push(`Hid ${hid} ${hid === 1 ? "detail" : "details"}`);
  const sorts = (["who", "value", "area"] as const).filter((k) => hasValue(live.parts[k])).length;
  if (sorts) bits.push(`${sorts} ${sorts === 1 ? "sorting" : "sortings"}`);
  const sim = Array.isArray(live.parts.similar.value) ? live.parts.similar.value.length : 0;
  if (sim) bits.push(`${sim} similar ${sim === 1 ? "idea" : "ideas"}`);
  return bits.join(", ");
}

function Why({ part, fallback }: { part: Part<unknown>; fallback?: string }) {
  if (part.state === "pinned") return <span className="why pin">{PANEL_COPY.yourCall}</span>;
  const why = part.why ?? fallback;
  return why ? <span className="why">{why}</span> : null;
}

function TitleSlot(props: SlotProps) {
  const { live } = props;
  const title = live.parts.title;
  const summary = live.parts.summary;
  const updating = live.updating.includes("title");
  const changeRef = useRef<HTMLButtonElement>(null);
  const change = useChange("title", props, changeRef);
  const canChange = Boolean(props.onChangePart) && !updating && (hasValue(title) || title.state === "failed");
  return (
    <>
      <div
        className="tslot"
        onFocus={() => props.onFocusQuote?.(title.source_quote ?? null)}
        onBlur={() => props.onFocusQuote?.(null)}
      >
        {change.open ? (
          <div id={change.editorId}>
            <PartEditor
              label="Title"
              initial={hasValue(title) ? String(title.value) : ""}
              maxLength={70}
              onCancel={change.close}
              onSave={async (v) => {
                await props.onChangePart?.("title", v);
                change.close();
              }}
            />
          </div>
        ) : updating ? (
          <span className="sk-group" aria-hidden="true">
            <Skeleton width="78%" height={18} tint />
            <Skeleton width="48%" height={18} tint />
          </span>
        ) : title.state === "failed" ? (
          <p className="wait">{PANEL_COPY.failed}</p>
        ) : hasValue(title) ? (
          <div>
            <h3 className="dt">{String(title.value)}</h3>
            <Why part={title} fallback={PANEL_COPY.titleWhy} />
          </div>
        ) : (
          <p className="wait dt-wait">{PANEL_COPY.titleWaiting}</p>
        )}
        {canChange || change.open ? (
          <button
            ref={changeRef}
            type="button"
            className="tb"
            aria-expanded={change.open}
            aria-controls={change.open ? change.editorId : undefined}
            onClick={change.toggle}
          >
            {PANEL_COPY.change}
            <span className="vh"> the title</span>
          </button>
        ) : null}
      </div>
      <div className="sslot">
        {updating ? (
          <span className="sk-group" aria-hidden="true">
            <Skeleton height={13} tint />
            <Skeleton width="92%" height={13} tint />
            <Skeleton width="50%" height={13} tint />
          </span>
        ) : hasValue(summary) ? (
          <p>{String(summary.value)}</p>
        ) : null}
      </div>
    </>
  );
}

function FactRow({ fact, ...props }: SlotProps & { fact: { key: FactKey; label: string } }) {
  const p = props.live.parts[fact.key] as Part<unknown>;
  const updating = props.live.updating.includes(fact.key);
  const filled = hasValue(p);
  const changeRef = useRef<HTMLButtonElement>(null);
  const change = useChange(fact.key, props, changeRef);
  let content: ReactNode;
  if (change.open) {
    content = (
      <div id={change.editorId}>
        <PartEditor
          label={fact.label}
          kind={fact.key === "value" ? "brings" : "text"}
          initial={
            fact.key === "value"
              ? Array.isArray(p.value)
                ? (p.value as string[])
                : []
              : filled
                ? factText(fact.key, p)
                : ""
          }
          onCancel={change.close}
          onSave={async (v) => {
            const value = fact.key === "who" && typeof v === "string" ? [v] : v;
            await props.onChangePart?.(fact.key, value);
            change.close();
          }}
        />
      </div>
    );
  } else if (updating) {
    content = <Skeleton width="70%" height={13} tint style={{ marginTop: 12 }} />;
  } else if (p.state === "failed") {
    content = <span className="wait">{PANEL_COPY.failed}</span>;
  } else if (filled) {
    content = (
      <>
        <span className="val">{factText(fact.key, p)}</span>
        <Why part={p} />
      </>
    );
  } else {
    content = <span className="wait">{PANEL_COPY.waiting}</span>;
  }
  const canChange = Boolean(props.onChangePart) && !updating && (filled || p.state === "failed");
  return (
    <div
      className="row"
      onFocus={() => props.onFocusQuote?.(p.source_quote ?? null)}
      onBlur={() => props.onFocusQuote?.(null)}
    >
      <dt>{fact.label}</dt>
      <dd>
        {content}
        {canChange || change.open ? (
          <button
            ref={changeRef}
            type="button"
            className="tb"
            aria-expanded={change.open}
            aria-controls={change.open ? change.editorId : undefined}
            onClick={change.toggle}
          >
            {PANEL_COPY.change}
            <span className="vh"> {fact.label}</span>
          </button>
        ) : null}
      </dd>
    </div>
  );
}

function PartEditor({
  label,
  kind = "text",
  initial,
  maxLength,
  onSave,
  onCancel,
}: {
  label: string;
  kind?: "text" | "brings";
  initial: string | string[];
  maxLength?: number;
  onSave(value: unknown): Promise<void>;
  onCancel(): void;
}) {
  const [text, setText] = useState(typeof initial === "string" ? initial : "");
  const [picked, setPicked] = useState<string[]>(Array.isArray(initial) ? initial : []);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function done() {
    const value = kind === "brings" ? picked : text.trim();
    if ((kind === "brings" && !picked.length) || (kind === "text" && !text.trim())) {
      setError(PANEL_COPY.fewWords);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onSave(value);
    } catch (err) {
      setError(
        err instanceof Error && "text" in err && typeof err.text === "string"
          ? err.text
          : PANEL_COPY.fewWords,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="ed"
      onKeyDown={(e) => {
        if (e.key === "Escape") {
          e.stopPropagation();
          onCancel();
        }
      }}
    >
      {kind === "brings" ? (
        <>
          <MultiChips
            label={label}
            options={BRINGS_ORDER.map((b) => ({ value: b, label: BRINGS_LABEL[b] }))}
            values={picked}
            onChange={(v) => {
              // "Not sure yet" clears the others, and any other choice clears it (V-FIELDS.checkit/3)
              const added = v.find((x) => !picked.includes(x));
              setPicked(added === "not_sure" ? ["not_sure"] : v.filter((x) => x !== "not_sure"));
            }}
          />
          {error ? (
            <p className="fmsg field-msg" role="alert">
              <span className="fmsg-ic" aria-hidden="true" />
              <span>{error}</span>
            </p>
          ) : null}
        </>
      ) : (
        <Field label={label} error={error ?? undefined}>
          {(c) => (
            <input
              {...c}
              type="text"
              value={text}
              maxLength={maxLength}
              autoFocus
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  void done();
                }
              }}
            />
          )}
        </Field>
      )}
      <div className="edf">
        <button type="button" className="rdone" aria-busy={busy || undefined} onClick={() => void done()}>
          <span className="tk" aria-hidden="true">
            <IconTick size={12} />
          </span>
          {PANEL_COPY.done}
        </button>
      </div>
    </div>
  );
}

/** C-PREVIEW's green status once a team-up request is sent: the sheet's own line, or "Waiting for Ravi". */
export function waitingLine(
  m: SimilarMatch,
  waiting: Record<string, string> | undefined,
): string | undefined {
  if (!waiting || !(m.idea.id in waiting)) return undefined;
  return waiting[m.idea.id] || `Waiting for ${m.idea.lead.first_name}`;
}

function Similar({
  part,
  updating,
  teamUp,
}: {
  part: Part<SimilarMatch[]>;
  updating: boolean;
  teamUp?: PanelProps["teamUp"];
}) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<SimilarMatch | null>(null);
  const listId = useId();
  if (updating) {
    return (
      <div className="sim-sk" aria-hidden="true">
        <Skeleton width={120} height={22} tint />
        <Skeleton width="50%" height={12} tint />
      </div>
    );
  }
  if (part.state === "failed") return <p className="sim-f wait">{PANEL_COPY.similarFailed}</p>;
  const matches = Array.isArray(part.value) ? part.value : [];
  if (part.state !== "filled" || !matches.length) return null;
  const n = matches.length;
  return (
    <div className="sim">
      <button
        type="button"
        className="simb"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="simt">
          <b>{`${n} similar ${n === 1 ? "idea" : "ideas"}`}</b>
          <span>{PANEL_COPY.similarSub}</span>
        </span>
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
        >
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open ? (
        <ul className="siml" id={listId}>
          {matches.map((m) => (
            <li key={m.idea.id} className="sli">
              <span className="sit">
                <p className="st">{m.idea.title}</p>
                <p className="sm">{m.reason}</p>
              </span>
              {/* C-PREVIEW closes before the sheet opens, so this row's Preview is where focus comes back. */}
              <Button
                variant="line"
                size="sm"
                className="spv"
                onClick={() => setPreview(m)}
                {...(teamUp?.opener?.(m.idea.id) ?? {})}
              >
                {PANEL_COPY.preview}
                <span className="vh">: {m.idea.title}</span>
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
      {preview ? (
        <IdeaPreviewDialog
          ideaId={preview.idea.id}
          view="sharer"
          open
          preview={preview.idea}
          matchReason={preview.reason}
          yours="draft"
          onClose={() => setPreview(null)}
          onPrimary={teamUp?.open}
          primaryDone={waitingLine(preview, teamUp?.waiting)}
        />
      ) : null}
    </div>
  );
}
