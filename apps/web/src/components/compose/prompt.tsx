"use client";
/**
 * C-PROMPT: the box where a problem is told (S-04, S-04B; BLD-C124). The person's words stay exactly as typed; a
 * mirror behind the text underlines each hidden detail (C-HIDDEN.where/1) and the phrase a draft part came from.
 * Enter sends, Shift and Enter adds a line (C-PROMPT.keys). Speaking (C-PROMPT.voice) runs on `useVoiceCapture`:
 * recording starts only when the person presses the mic, the words appear in the box as they are heard, and the
 * blocked warning sits under the box as an alert. Copy is the boards' (reference/copy/Compose.md, PhoneCompose.md).
 * The tool row reads, from the left: the "+" (`attach`, DEC-124), Move to Review with its readiness line in Capture
 * first (`move`, DEC-125), the key hint, then the mic and the round button at the right. Files show as rows above the
 * words (`files`) and the picker opens between the words and the tool row (`picker`), as the Home board draws them.
 */
import { forwardRef, useEffect, useId, useState, type ReactNode } from "react";

import {
  IconArrowUp,
  IconCall,
  IconLoop,
  IconMic,
  IconMicOff,
  IconScreens,
  IconStop,
  IconWave,
} from "@/components/compose/icons";
import type { HiddenSpan } from "@/lib/contracts";
import { segments } from "@/lib/compose/hidden";
import { VOICE_LISTENING, type VoiceCaptureState } from "@/lib/voice-capture";
import { VOICE_EN_LABEL } from "@/lib/voice-stream";

export const PROMPT_COPY = {
  firstLabel: "Describe the problem",
  firstPlaceholder:
    "For example: when a redemption is rejected, the SMS only gives a code, so investors call the branch to ask what it means.",
  firstPlaceholderPhone:
    "For example: the rejection SMS only gives a code, so investors call the branch to ask what it means.",
  moreLabel: "Add a detail, like how often it happens or what you tried",
  keys: "Enter starts your draft. Shift and Enter for a new line.",
  help: "Say it in whichever language feels most natural to you.",
  tapToSpeak: "Tap to start speaking",
  notRecording: "Not recording until you do",
  speakInstead: "Speak instead",
  sayInstead: "Say it instead",
  stopAndUse: "Stop, and use what you said",
  typeOrSpeak: "Type or speak first",
  micBlocked: "Microphone blocked",
  startersLabel: "Or start from one of these",
} as const;

/** C-PROMPT.anatomy/3: the label, and the opener it puts in the box (the prototype's own words). */
export const STARTERS: { label: string; opener: string; icon: ReactNode }[] = [
  {
    label: "A step customers keep calling about",
    opener: "Customers keep calling us about ",
    icon: <IconCall />,
  },
  {
    label: "Something we redo by hand every month",
    opener: "Every month we redo this by hand: ",
    icon: <IconLoop />,
  },
  {
    label: "A screen that asks for the same thing twice",
    opener: "This screen asks for the same thing twice: ",
    icon: <IconScreens />,
  },
];

/** The phone's four sentence starters (PhoneCompose.md, state Empty). */
export const PHONE_STARTERS = [
  "Every day I have to",
  "Investors keep calling us about",
  "We find out too late when",
  "It takes too long to",
] as const;

export type PromptVoice = {
  state: VoiceCaptureState;
  start(): void;
  stop(): void;
  /** The screen showed VOICE_NOTICE (the hook marks it seen only after that). */
  noticeShown(): void;
};

export type PromptProps = {
  value: string;
  onChange(value: string): void;
  onSend(): void;
  /** Ctrl or ⌘ with Enter: on to Check it, when the draft is ready (C-PROMPT.keys/2). */
  onModEnter?(): void;
  /** The send button's name: "Start my draft", "Add to your draft", "Queue it for your draft". */
  sendLabel: string;
  label: string;
  placeholder: string;
  /** Show "Enter starts your draft. Shift and Enter for a new line." once there is text (first message only). */
  keyHint?: boolean;
  /** Hidden details in the box's text, when the text is what was saved. */
  spans?: HiddenSpan[] | null;
  /** The phrase a focused draft part came from, underlined in the box. */
  source?: { start: number; end: number } | null;
  voice?: PromptVoice | null;
  device: "desktop" | "phone";
  /** The empty first box: the round button is the microphone, with "Tap to start speaking" (S-04.empty/1). */
  micFirst?: boolean;
  /** The English copy of a voice note in another language, under the box (L-DRAFT.voice/4); one line per note
   * when the box holds several (BLD-C150). */
  english?: string | readonly string[] | null;
  /** C-PROMPT.anatomy/2: the "+" that opens the attach picker (DEC-124, C-FILE.uploader), first in the tool row. */
  attach?: ReactNode;
  /** C-PROMPT.attach: the files and links in the box, as rows above the words (the Home board's `attachments`). */
  files?: ReactNode;
  /** The attach picker, open between the words and the tool row (Home.md, `attachments=Picker open`). */
  picker?: ReactNode;
  /** Capture first (DEC-125): "Move to Review" and its readiness line, after the "+" in the tool row. */
  move?: ReactNode;
  /** Lines under the box (help, starters), in the screen's words. */
  children?: ReactNode;
  className?: string;
  sending?: boolean;
  /** Home (S-03): with words in the box the round button is a link on to Tell it, named by `sendLabel`
   * ("Continue to Share a problem", Home.md); a click sends (`onSend`) instead of following it. */
  sendHref?: string;
};

function Mirror({
  text,
  spans,
  source,
}: {
  text: string;
  spans?: HiddenSpan[] | null;
  source?: PromptProps["source"];
}) {
  const segs = segments(text, spans ?? []);
  return (
    <div className="mirror" aria-hidden="true">
      {segs.map((s) => {
        const src = source && s.at < source.end && s.at + s.text.length > source.start;
        const cls = [s.kind ? "pii" : "", src ? "src" : ""].filter(Boolean).join(" ");
        return cls ? (
          <span key={s.at} className={cls}>
            {s.text}
          </span>
        ) : (
          <span key={s.at}>{s.text}</span>
        );
      })}
      {"​"}
    </div>
  );
}

export const Prompt = forwardRef<HTMLTextAreaElement, PromptProps>(function Prompt(props, ref) {
  const {
    value,
    onChange,
    onSend,
    onModEnter,
    sendLabel,
    label,
    placeholder,
    keyHint,
    spans,
    source,
    voice,
    device,
    micFirst,
    english,
    attach,
    files,
    picker,
    move,
    children,
    className,
    sending,
    sendHref,
  } = props;
  const id = useId();
  // Typed once (BLD-C240): the hint never comes back after the box is cleared, as the board's `!draft && !typed`.
  const [typed, setTyped] = useState(false);
  const v = voice?.state ?? null;
  const status = v?.status ?? "idle";
  const recording = status === "recording" || status === "sending" || status === "asking";
  const blocked = v?.status === "blocked" ? v : null;
  const has = value.trim().length > 0;
  const notice = v?.status === "idle" ? v.notice : null;
  const live = v && (v.status === "recording" || v.status === "sending") ? v.text : "";
  const shown = recording && live ? (value ? `${value.replace(/\s+$/, "")} ${live}` : live) : value;

  useEffect(() => {
    if (notice) voice?.noticeShown();
  }, [notice, voice]);

  const micLabel = blocked
    ? PROMPT_COPY.micBlocked
    : recording
      ? PROMPT_COPY.stopAndUse
      : device === "phone"
        ? PROMPT_COPY.sayInstead
        : PROMPT_COPY.speakInstead;
  const roundIsMic = Boolean(voice) && micFirst && !has && !recording && !blocked;
  const canSend = has && !recording && !sending;
  const englishLines = english ? (typeof english === "string" ? [english] : english) : [];

  const mic = voice ? (
    <button
      type="button"
      className={`mic2${recording ? " stop" : ""}${blocked ? " blk" : ""}${roundIsMic ? " hid" : ""}`}
      aria-pressed={recording}
      aria-busy={status === "asking" || status === "sending" ? true : undefined}
      aria-label={micLabel}
      title={micLabel}
      onClick={() => (recording ? voice.stop() : voice.start())}
    >
      {blocked ? <IconMicOff /> : <IconMic />}
    </button>
  ) : null;

  return (
    <div className={`cbox prompt${className ? ` ${className}` : ""}`}>
      {files}
      <div className="tx">
        {/* The mirror sizes the box: with no words yet it holds the placeholder, so the example is never cut. */}
        <Mirror
          text={shown || placeholder}
          spans={recording || !shown ? null : spans}
          source={recording || !shown ? null : source}
        />
        <label className="vh" htmlFor={id}>
          {label}
        </label>
        <textarea
          ref={ref}
          id={id}
          className="ta"
          value={shown}
          placeholder={placeholder}
          readOnly={recording}
          aria-describedby={`${id}-help`}
          onChange={(e) => {
            setTyped(true);
            onChange(e.target.value);
          }}
          onKeyDown={(e) => {
            if (e.key !== "Enter" || e.nativeEvent.isComposing) return;
            if (e.metaKey || e.ctrlKey) {
              e.preventDefault();
              onModEnter?.();
              return;
            }
            if (e.shiftKey) return;
            e.preventDefault();
            if (canSend) onSend();
          }}
          rows={2}
        />
      </div>
      {picker}
      <div className={`cfoot${attach || move ? " tools" : ""}`}>
        {attach}
        {move}
        <p className="cnt" id={`${id}-help`}>
          {recording ? VOICE_LISTENING : has && keyHint ? PROMPT_COPY.keys : null}
        </p>
        <span className="vh" role="status">
          {status === "recording" ? VOICE_LISTENING : ""}
        </span>
        {mic}
        <span className="sendw">
          {roundIsMic && !typed ? (
            <span className="vhint" aria-hidden="true">
              <b>{PROMPT_COPY.tapToSpeak}</b>
              <span>{PROMPT_COPY.notRecording}</span>
            </span>
          ) : null}
          {roundIsMic && voice ? (
            <button
              type="button"
              className="send voice"
              aria-label={PROMPT_COPY.tapToSpeak}
              title={PROMPT_COPY.tapToSpeak}
              onClick={() => voice.start()}
            >
              <IconWave className="wave" />
            </button>
          ) : sendHref && canSend ? (
            <a
              href={sendHref}
              className="send on"
              aria-label={sendLabel}
              title={sendLabel}
              onClick={(e) => {
                e.preventDefault(); // the words go with it, so never an empty Tell it in a new tab (P-ROUTES.graph)
                onSend();
              }}
              onAuxClick={(e) => {
                if (e.button !== 1) return; // a middle click sends here too, never a new tab with an empty S-04
                e.preventDefault();
                onSend();
              }}
              onKeyDown={(e) => {
                if (e.key !== " ") return; // Enter is the link's own click; Space sends as on a button
                e.preventDefault();
                onSend();
              }}
            >
              <IconArrowUp className="arrow" />
            </a>
          ) : (
            <button
              type="button"
              className={`send${canSend ? " on" : " dim"}`}
              aria-label={recording || blocked ? PROMPT_COPY.typeOrSpeak : sendLabel}
              title={recording || blocked ? PROMPT_COPY.typeOrSpeak : sendLabel}
              aria-disabled={canSend ? undefined : true}
              onClick={() => {
                if (canSend) onSend();
              }}
            >
              {recording ? <IconStop className="stopi" /> : <IconArrowUp className="arrow" />}
            </button>
          )}
        </span>
      </div>
      {englishLines.length ? (
        <div className="cen">
          <p className="cen-l">{VOICE_EN_LABEL}</p>
          {englishLines.map((line, i) => (
            <p key={i} className="cen-t">
              {line}
            </p>
          ))}
        </div>
      ) : null}
      {blocked ? (
        <div className="blkn" role="alert">
          <IconMicOff />
          <div>
            <p className="blkn-t">{blocked.title}</p>
            <p className="blkn-b">{blocked.body}</p>
          </div>
        </div>
      ) : null}
      {notice ? <p className="vnotice">{notice}</p> : null}
      {children}
    </div>
  );
});

export function Starters({ onPick, device }: { onPick(opener: string): void; device: "desktop" | "phone" }) {
  if (device === "phone") {
    return (
      <div className="hstarters ph" role="group" aria-label={PROMPT_COPY.startersLabel}>
        {PHONE_STARTERS.map((s) => (
          <button key={s} type="button" className="chip nx" onClick={() => onPick(`${s} `)}>
            {s}…
          </button>
        ))}
      </div>
    );
  }
  return (
    <div className="hstarters" role="group" aria-label={PROMPT_COPY.startersLabel}>
      {STARTERS.map((s) => (
        <button key={s.label} type="button" className="hstarter" onClick={() => onPick(s.opener)}>
          {s.icon}
          <span>{s.label}</span>
        </button>
      ))}
    </div>
  );
}
