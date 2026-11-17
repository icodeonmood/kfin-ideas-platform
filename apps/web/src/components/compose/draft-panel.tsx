"use client";
/**
 * C-DRAFT-PANEL: the draft as a live document beside the conversation (BLD-C125). Fixed slots so nothing jumps:
 * the title and summary, the four facts as tiles (How often, Who it affects, What it's worth, Area), the hidden
 * details bar (C-HIDDEN), the similar-ideas line (C-PREVIEW on demand), and "Move to Review" pinned to the bottom
 * with its readiness line. The loader (C-DRAFT-LOADER) sits at the top while parts build; each part shows its own
 * skeleton. "Change" opens a part in place; the person's own value is pinned and reads "Your call" (L-DRAFT.pins).
 * On a phone the panel is a bottom sheet that peeks with the title and the loader's tube (C-DRAFT-PANEL.behaviour/6).
 */
import { useId, useState, type ReactNode } from "react";

import { HiddenDetails, type HiddenActions } from "@/components/compose/hidden";
import { DraftLoader } from "@/components/compose/draft-loader";
import { IdeaPreviewDialog } from "@/components/preview/idea-preview";
import { IconTick } from "@/components/shell/icons";
import { Button, ButtonLink } from "@/components/ui/button";
import { MultiChips } from "@/components/ui/chips";
import { Field } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { BRINGS_LABEL, type Brings, type DraftPartKey, type Part, type SimilarMatch } from "@/lib/contracts";
import { hasValue, type Live } from "@/lib/compose/live";

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
  phoneUpdating: "Updating your draft",
  phoneOffline: "Paused while you’re offline",
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

type FactKey = "often" | "who" | "value" | "area";
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

export type PanelProps = {
  live: Live;
  /** The words have reached the point where parts form (L-DRAFT.parts/3); before that, slots wait. */
  readiness: Readiness;
  /** "Move to Review": where it goes once ready. */
  moveHref: string | null;
  onMove?(): void;
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
};

export function panelStatus(live: Live): string {
  if (live.running) return PANEL_COPY.updating;
  const any = (["title", "often", "who", "value", "area"] as const).some((k) => hasValue(live.parts[k]));
  return any ? PANEL_COPY.upToDate : PANEL_COPY.forms;
}

export function DraftPanel(props: PanelProps) {
  const { live, readiness, moveHref, onMove, phone, offline } = props;
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  const status = panelStatus(live);
  const ready = readiness === "ready" && Boolean(moveHref);
  const title = live.parts.title;

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

  const body = (
    <>
      <DraftLoader run={live.loader} done={!live.running} phone={false} />
      <div className="cvb">
        <TitleSlot {...props} />
        <dl className="rows">
          {FACTS.map((f) => (
            <FactRow key={f.key} fact={f} {...props} />
          ))}
        </dl>
        {props.hidden ? (
          <HiddenDetails details={live.hidden} actions={props.hidden} onFocusDetail={props.onFocusDetail} />
        ) : null}
        <Similar part={live.parts.similar} updating={live.updating.includes("similar")} />
      </div>
    </>
  );

  if (phone) {
    const peekTitle = hasValue(title) ? String(title.value) : PANEL_COPY.heading;
    const peekLine = offline
      ? PANEL_COPY.phoneOffline
      : live.running
        ? PANEL_COPY.phoneUpdating
        : hasValue(title)
          ? peekSummary(live)
          : PANEL_COPY.phonePeekEmpty;
    return (
      <section className={`dsheet${open ? " open" : ""}`} aria-label={PANEL_COPY.heading}>
        <button
          type="button"
          className="dpeek"
          aria-expanded={open}
          aria-controls={bodyId}
          onClick={() => setOpen((v) => !v)}
        >
          <span className="dpeek-t">{peekTitle}</span>
          <span className="dpeek-s">{peekLine}</span>
        </button>
        <DraftLoader run={live.loader} done={!live.running} phone />
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
      {body}
      <footer className="cvf">
        <p className="cvfn">{READINESS[readiness]}</p>
        {move}
      </footer>
    </section>
  );
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

function TitleSlot(props: PanelProps) {
  const { live } = props;
  const title = live.parts.title;
  const summary = live.parts.summary;
  const [editing, setEditing] = useState(false);
  const updating = live.updating.includes("title");
  if (editing && props.onChangePart) {
    return (
      <div className="tslot">
        <PartEditor
          label="Title"
          initial={hasValue(title) ? String(title.value) : ""}
          maxLength={70}
          onCancel={() => setEditing(false)}
          onSave={async (v) => {
            await props.onChangePart?.("title", v);
            setEditing(false);
          }}
        />
      </div>
    );
  }
  return (
    <>
      <div
        className="tslot"
        onFocus={() => props.onFocusQuote?.(title.source_quote ?? null)}
        onBlur={() => props.onFocusQuote?.(null)}
      >
        {updating ? (
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
        {props.onChangePart && !updating && (hasValue(title) || title.state === "failed") ? (
          <button type="button" className="tb" aria-expanded={false} onClick={() => setEditing(true)}>
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

function FactRow({ fact, ...props }: PanelProps & { fact: { key: FactKey; label: string } }) {
  const p = props.live.parts[fact.key] as Part<unknown>;
  const [editing, setEditing] = useState(false);
  const updating = props.live.updating.includes(fact.key);
  const filled = hasValue(p);
  let content: ReactNode;
  if (editing && props.onChangePart) {
    content = (
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
        onCancel={() => setEditing(false)}
        onSave={async (v) => {
          const value = fact.key === "who" && typeof v === "string" ? [v] : v;
          await props.onChangePart?.(fact.key, value);
          setEditing(false);
        }}
      />
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
  return (
    <div
      className="row"
      onFocus={() => props.onFocusQuote?.(p.source_quote ?? null)}
      onBlur={() => props.onFocusQuote?.(null)}
    >
      <dt>{fact.label}</dt>
      <dd>
        {content}
        {props.onChangePart && !editing && !updating && (filled || p.state === "failed") ? (
          <button type="button" className="tb" aria-expanded={false} onClick={() => setEditing(true)}>
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

function Similar({ part, updating }: { part: Part<SimilarMatch[]>; updating: boolean }) {
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
              <Button variant="line" size="sm" className="spv" onClick={() => setPreview(m)}>
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
        />
      ) : null}
    </div>
  );
}
