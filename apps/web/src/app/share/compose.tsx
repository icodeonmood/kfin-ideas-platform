"use client";
/**
 * Tell it: S-04 (`/share`, a new problem) and S-04B (`/share/:draftId`, the conversation), one screen that morphs on
 * the first message (BLD-C126). Copy word for word from reference/copy/Compose.md, ComposeResume.md, PhoneCompose.md
 * and PhoneComposeResume.md.
 *
 * S-04: the calm prompt on its own, the draft's slots quietly beside it. The words are saved as they are typed
 * (L-DRAFT.autosave/1): the draft is made on the first pause, and the box is its first message from then on, so the
 * parts form while the person types. "Start my draft" (Enter) opens the conversation on that draft.
 * S-04B: the person's messages, the receipt after the last one, the box pinned at the bottom ("Add to your draft"),
 * and the draft panel. Each message carries its own client_id on every try; one that cannot go waits on this device
 * with its client_id and `at`, and goes when the browser is back online (L-DRAFT.autosave/7).
 * Voice (C-PROMPT.voice, DEC-108): `useVoiceCapture`; a finished note goes into the draft as a message with its
 * stream, so the server keeps the English copy with it. Into an empty S-04 box it is the first message at once; after
 * typed words it waits in the box, editable, and goes as its own message after the typed one; a second note while one
 * waits does the same after it (BLD-C150).
 * Team up from a similar idea's preview opens lane F's own sheet (`useTeamUpSheet`, C-SHEET-TEAMUP) with this draft,
 * so "Keep mine separate" or a merge request goes with it (J-SIMILAR/3–5, BLD-C129).
 * Flags (P-DECISIONS.experiments, BLD-C170 to C179), handed in by the page, never picked here: S1 "Interview" asks
 * up to three skippable questions after the first telling, its place kept with the draft, then builds the draft once;
 * S3 "Voice first" starts listening at once on a phone's empty S-04 once the page is shown and the microphone is
 * allowed, with "Type instead" and "Stop, 0:14" in the dock. Without `flags` (and with both at their default) the
 * screen is exactly the default.
 */
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type MouseEvent } from "react";

import { IconDevice, IconLaptop, IconMail, IconPencil } from "@/components/compose/icons";
import {
  DraftPanel,
  PANEL_COPY,
  readinessOf,
  type PanelHandle,
  type PanelInterview,
  type Readiness,
} from "@/components/compose/draft-panel";
import { InterviewCard, soFarLine } from "@/components/compose/interview";
import { Prompt, PROMPT_COPY, Starters } from "@/components/compose/prompt";
import { Dock } from "@/components/shell/phone";
import { Taskbar, type SaveState } from "@/components/shell/taskbar";
import { teamUpOpener, useTeamUpSheet } from "@/components/teamup/teamup-sheet";
import { Button, ButtonLink } from "@/components/ui/button";
import { FieldMsg } from "@/components/ui/field";
import type {
  Device,
  Draft,
  DraftListItem,
  DraftStreamEvent,
  HiddenSpan,
  Message,
  ShowReason,
} from "@/lib/contracts";
import {
  backInBox,
  boxParts,
  DraftClient,
  DraftError,
  englishFor,
  firstEnd,
  messagesFor,
  newClientId,
  spokenAfterFirst,
  type HeldNote,
  type InterviewResponse,
  type InterviewStep,
  type Outgoing,
} from "@/lib/compose/client";
import { quoteRange, segments } from "@/lib/compose/hidden";
import {
  applyEvent,
  fromDraft,
  giveUp,
  loseStream,
  withDraft,
  withDraftAfterLoss,
  type Live,
} from "@/lib/compose/live";
import {
  NO_INTERVIEW,
  nextQuestion,
  type ComposeFlags,
  type InterviewPlace,
  type InterviewQuestion,
} from "@/lib/flags";
import { flagEvent } from "@/lib/flags-client";
import { BANNERS } from "@/lib/killswitch-routes";
import { useVoiceCapture } from "@/lib/use-voice-capture";
import type { VoiceCaptureState, VoiceNote } from "@/lib/voice-capture";

export const COMPOSE_COPY = {
  title: "Share a problem",
  close: "Save and close",
  question: (name: string) => `What keeps getting in your way, ${name}?`,
  questionPhone: "What’s getting in your way?",
  helpPhone:
    "What happens, who it affects, how often. Any language. At least 30 characters, and no fix needed.",
  privacyPhone: "Nothing is shared until you send it. Saved as you go, here and on your computer.",
  stepPhone: "Step 1 of 3",
  stepNowPhone: "Tell it",
  nextPhone: "Next: check it",
  start: "Start my draft",
  add: "Add to your draft",
  more: "Add a detail any time. It goes straight into the draft.",
  working: "Working through your words. You can already add more.",
  you: "You",
  edit: "Edit",
  done: "Done",
  existing: (day: string, title: string) => `You have a draft from ${day}: ${title}.`,
  existingLine: (line: string) => `${line} Continue it here, or start a new one below.`,
  continueDraft: "Continue that draft",
  continuePhone: "Continue it",
  startNew: "Start a new one",
  pickedUp: "Picked up where you left off.",
  startNewInstead: "Start a new one instead",
  emailNote: "We turned it into this draft. Nothing has been sent.",
  queued: "Queued. Goes in once the one above is done.",
  tooLong: "That's a lot for one go. Send this part, then carry on.",
  /** A note paused or unavailable: every voice-off line reads the same, the product lead's decision of 18 Nov (BLD-C149). */
  voicePaused: BANNERS["capture.voice"], // the voice-off line from the one source (BLD-157)
  /** A note that failed because the session ended: L-AUTH.states "Session expired mid-draft" (SignIn.md). */
  signInAgain: "Sign in again to carry on",
  enough: "Enough to work with",
  moreChars: (n: number) => `${n} more ${n === 1 ? "character" : "characters"}`,
  /** S3 "Voice first": the dock while listening (PhoneCompose.md, state Speaking; "Stop" before any words are
   * heard, PhoneCompose.dc.html). */
  typeInstead: "Type instead",
  stop: "Stop",
  stopAt: (seconds: number) => `Stop, ${clock(seconds)}`,
} as const;

/** "0:14": minutes and seconds of a voice note so far. */
export function clock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** S3: whether the browser already allows the microphone. Never asks: with no answer, or "prompt", it is no. */
export async function micAllowed(): Promise<boolean> {
  try {
    const status = await navigator.permissions?.query({ name: "microphone" as PermissionName });
    return status?.state === "granted";
  } catch {
    return false;
  }
}

/** S3's second metric: for each voice note going with this send, whether its words are as heard or were changed
 * first (codes only, BLD-C175). A note already sent as S-04's first message is as heard while the box still holds
 * its words. */
export function noteOutcomes(box: string, notes: readonly HeldNote[]): ("as_heard" | "corrected")[] {
  const out: ("as_heard" | "corrected")[] = [];
  for (const n of notes)
    if (n.prefix === null) out.push(box.includes(n.text.trim()) ? "as_heard" : "corrected");
  for (const p of boxParts(box, notes))
    if (p.note) out.push(!p.whole && p.text.trim() === p.note.text.trim() ? "as_heard" : "corrected");
  return out;
}

/** C-PROMPT.states, the phone's live count (PhoneCompose.md: "30 more characters", then "Enough to work with"). */
export function countLine(chars: number, min: number = MIN_CHARS): string {
  return chars >= min ? COMPOSE_COPY.enough : COMPOSE_COPY.moreChars(min - chars);
}

/** C-PROMPT.voice, a note that failed (BLD-C127): signed out → the sign-in line; paused or unavailable → the paused
 * line; any other reason (no microphone, an old browser, audio suspended, too many this hour, a lost stream) has no
 * line in the pack, so nothing is invented and the mic is simply ready again (listed for HR). */
export function voiceFailedLine(reason: string): "sign_in" | "paused" | null {
  if (reason === "signed_out") return "sign_in";
  if (["paused", "unavailable", "voice_paused", "voice_unavailable"].includes(reason)) return "paused";
  return null;
}

const MIN_CHARS = 30; // V-FIELDS.tellit/1
const MAX_MESSAGE = 5000; // V-FIELDS.tellit/2
const CREATE_PAUSE_MS = 1000; // L-DRAFT.autosave/1: from the first keystroke after a 1-second pause
const SAVE_PAUSE_MS = 1500; // within 2 seconds of the person stopping
const GIVE_UP_TICK_MS = 1000; // C-DRAFT-LOADER.failure/1 is checked once a second
const RECONNECTS = 2; // the browser's own reconnects allowed before the stream counts as lost
const NO_RUN_MS = 20_000; // a stream that never sends its run while parts wait counts as lost
const RECOVER_MS = 3000; // after a lost stream, the draft is read again this often while the server builds…
const RECOVER_TRIES = 20; // …for about a minute

/** Drafts this tab opened from S-04's "Start my draft": no "Picked up where you left off." on those. */
const handedOver = new Set<string>();

type Pending = Outgoing & { queued: boolean };

function useIsPhone(): boolean {
  const [phone, setPhone] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 640px)");
    const on = () => setPhone(mq.matches);
    on();
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return phone;
}

function isEditable(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false;
  return t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName);
}

function Words({ text, spans, quote }: { text: string; spans: HiddenSpan[]; quote: string | null }) {
  const src = quoteRange(text, quote);
  return (
    <p className="btx">
      {segments(text, spans).map((s) => {
        const hit = src && s.at < src.end && s.at + s.text.length > src.start;
        const cls = [s.kind ? "pii" : "", hit ? "src" : ""].filter(Boolean).join(" ");
        return cls ? (
          <span key={s.at} className={cls}>
            {s.text}
          </span>
        ) : (
          <span key={s.at}>{s.text}</span>
        );
      })}
    </p>
  );
}

export function Compose({
  firstName,
  draftId: givenId,
  startNew = false,
  flags = null,
  interviewPlace = null,
}: {
  firstName: string;
  draftId: string | null;
  /** `/share?new=1`: "Start a new one instead", so no offer of the earlier draft. */
  startNew?: boolean;
  /** S1 and S3 as the server decided them for this person (P-DECISIONS.experiments). Null: the default, and no
   * exposure is logged. */
  flags?: ComposeFlags | null;
  /** S1: where this draft's questions stand, kept with the draft (S-04B). */
  interviewPlace?: InterviewPlace | null;
}) {
  const router = useRouter();
  const phone = useIsPhone();
  const device = phone ? "phone" : "desktop";
  const client = useMemo(() => new DraftClient(), []);
  const conversation = givenId !== null; // S-04B

  const [draftId, setDraftId] = useState<string | null>(givenId);
  const idRef = useRef<string | null>(givenId);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [live, setLive] = useState<Live>(() => fromDraft(null));
  const [loadError, setLoadError] = useState<string | null>(null);
  const [box, setBox] = useState("");
  const [save, setSave] = useState<SaveState>("idle");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  /** The server's words for `savedAt`, read with it: "Saved Monday, 10:59 pm" on an earlier day (BLD-C192). */
  const [savedLabel, setSavedLabel] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [existing, setExisting] = useState<DraftListItem | null>(null);
  /** S-04B.layout/4: "Last saved on your phone, Friday 8:42 pm." and the device it names, as they were when the
   * draft was opened, or null when there is no "Picked up" line. Saves made here afterwards do not change it
   * (BLD-C158). `earlier` holds the messages it was picked up with: they read "Friday, 8:42 pm, on your phone"
   * (S-04B.layout/1, BLD-C185). */
  const [pickedUp, setPickedUp] = useState<{
    line: string;
    device: Device | null;
    earlier: ReadonlySet<string>;
  } | null>(null);
  const [pending, setPending] = useState<Pending[]>([]);
  const [streamRun, setStreamRun] = useState<string | null>(null);
  const [quote, setQuote] = useState<string | null>(null);
  // The voice notes waiting in the box, in the order spoken; each goes as its own message (BLD-C150).
  const [voiceNotes, setVoiceNotes] = useState<HeldNote[]>([]);
  const panelRef = useRef<PanelHandle>(null);
  const [elsewhere, setElsewhere] = useState<string | null>(null);
  const [netTick, setNetTick] = useState(0);
  // S-04: the offer of an earlier draft has been looked for (S3 listens only once it is known there is none).
  const [recentChecked, setRecentChecked] = useState(startNew || givenId !== null);
  // S1 "Interview" (BLD-C172).
  const interviewOn = Boolean(flags?.interview);
  const [place, setPlace] = useState<InterviewPlace>(interviewPlace ?? NO_INTERVIEW);
  const [ivBusy, setIvBusy] = useState(false);
  const [ivError, setIvError] = useState<string | null>(null);
  const [ivMoved, setIvMoved] = useState(false);
  const ivAsked = useRef<{ start: boolean; finish: boolean }>({ start: false, finish: false });
  const answerKeys = useRef<Partial<Record<InterviewQuestion, string>>>({});

  // S-04's box is the draft's first message once saved.
  const firstMid = useRef<string | null>(null);
  const savedText = useRef<string | null>(null);
  const [savedBox, setSavedBox] = useState<string | null>(null);
  const markSaved = useCallback((text: string | null) => {
    savedText.current = text;
    setSavedBox(text);
  }, []);
  const [boxSpans, setBoxSpans] = useState<HiddenSpan[] | null>(null);
  const createKey = useRef<string>(newClientId());
  const chain = useRef<Promise<void>>(Promise.resolve());
  const boxRef = useRef<HTMLTextAreaElement>(null);

  const adopt = useCallback((d: Draft, runId?: string | null) => {
    setDraft(d);
    setLive((l) => withDraft(l, d));
    if (d.saved_at) {
      setSavedAt(d.saved_at);
      setSavedLabel(d.saved_labels?.status ?? null);
    }
    if (runId) setStreamRun(runId);
  }, []);

  const failed = useCallback((err: unknown) => {
    if (err instanceof DraftError) {
      if (err.offline) {
        setSave("offline");
        return;
      }
      if (err.code === "open_elsewhere") {
        setElsewhere(err.text); // and the task bar stops saying "Saving…": these words are not saved yet
      } else {
        setProblem(err.text);
      }
    } else {
      setProblem(null);
    }
    setSave("changed");
  }, []);

  // The router of the latest render, for the load below, which runs once per draft.
  const routerRef = useRef(router);
  useEffect(() => {
    routerRef.current = router;
  });

  // ── loading ─────────────────────────────────────────────────────────────────────────────────────────────────
  useEffect(() => {
    let gone = false;
    if (givenId) {
      client
        .get(givenId, true)
        .then((d) => {
          if (gone) return;
          // Merged into another idea: nothing more to tell, so Check it shows it read-only (J-SIMILAR/6a, BLD-C155).
          // The page sends it there first; this covers a page that could not tell.
          if (d.merged_into) {
            routerRef.current.replace(`/share/${encodeURIComponent(givenId)}/check`);
            return;
          }
          adopt(d, d.run?.state === "running" ? d.run.id : null);
          setSave("saved");
          const ageMs = Date.now() - new Date(d.saved_at).getTime();
          const back =
            !handedOver.has(givenId) &&
            d.run?.state !== "running" &&
            (!d.saved_on?.this_device || ageMs > 2 * 60_000);
          setPickedUp(
            back
              ? {
                  line: d.saved_labels?.resume ?? "",
                  device: d.saved_on?.device ?? null,
                  earlier: new Set(d.messages.map((m) => m.id)),
                }
              : null,
          );
          const waiting = client.outbox(givenId);
          if (waiting.length) setPending(waiting.map((m) => ({ ...m, queued: true })));
        })
        .catch((err) => {
          if (gone) return;
          setLoadError(err instanceof DraftError && err.text ? err.text : null);
          if (err instanceof DraftError && err.offline) setSave("offline");
        });
    } else if (!startNew) {
      client
        .recent()
        .then((list) => {
          if (!gone && list[0]) setExisting(list[0]);
        })
        .catch(() => undefined) // the offer is a convenience; the box works without it
        .finally(() => {
          if (!gone) setRecentChecked(true);
        });
    }
    return () => {
      gone = true;
    };
  }, [givenId, startNew, client, adopt]);

  // ── the stream: one run at a time, from its start (A-API.draft-stream `?run=`) ───────────────────────────────
  // C-DRAFT-LOADER.failure: a part past 10 × its mean is given up; a stream that is closed, sends the server's
  // `error`, keeps failing to reconnect or ends while parts wait is lost, and every part still out fails. Either way
  // the draft is read again, and again every few seconds while the server is still building, so no slot waits on a
  // stream that will never come (J-RECOVER).
  const liveRef = useRef(live);
  useEffect(() => {
    liveRef.current = live;
  }, [live]);
  useEffect(() => {
    if (!draftId || !streamRun) return;
    let closed = false; // this effect is gone (a newer run, or the screen)
    let settled = false; // done or lost: nothing more from this stream
    let errors = 0;
    let poll: ReturnType<typeof setTimeout> | null = null;
    let tick: ReturnType<typeof setInterval> | null = null;
    let es: EventSource | null = null;
    const opened = Date.now();

    const reread = (lost: boolean, left: number) => {
      client.get(draftId).then(
        (d) => {
          if (closed) return;
          setDraft(d);
          setLive((l) => (lost ? withDraftAfterLoss(l, d) : withDraft(l, d)));
          // S-04's box: the saved message's spans, as the web edge converted them (BLD-C121).
          const first = d.messages.find((m) => m.id === firstMid.current);
          if (first) setBoxSpans(first.spans ?? null);
          if (d.run?.state === "running" && left > 1)
            poll = setTimeout(() => reread(lost, left - 1), RECOVER_MS);
        },
        () => {
          if (!closed && left > 1) poll = setTimeout(() => reread(lost, left - 1), RECOVER_MS);
        },
      );
    };
    const finish = () => {
      settled = true;
      es?.close();
      if (tick) clearInterval(tick);
    };
    const lose = () => {
      if (settled || closed) return;
      finish();
      setLive((l) => loseStream(l, Date.now()));
      reread(true, RECOVER_TRIES);
    };

    if (typeof EventSource === "undefined") {
      reread(false, RECOVER_TRIES); // no stream in this browser: the parts arrive by reading the draft
      return () => {
        closed = true;
        if (poll) clearTimeout(poll);
      };
    }
    const source = new EventSource(
      `/api/drafts/${encodeURIComponent(draftId)}/stream?run=${encodeURIComponent(streamRun)}`,
    );
    es = source;
    const on = (name: DraftStreamEvent["event"]) => (e: MessageEvent<string>) => {
      if (settled) return;
      let data: unknown;
      try {
        data = JSON.parse(e.data);
      } catch {
        return;
      }
      errors = 0;
      setLive((l) => applyEvent(l, { event: name, data } as DraftStreamEvent, Date.now()));
      if (name === "done") {
        finish();
        reread(false, 1);
      }
    };
    for (const name of ["run", "hidden", "part", "receipt", "done"] as const)
      source.addEventListener(name, on(name));
    source.addEventListener("end", () => {
      if (liveRef.current.running) lose();
      else finish();
    });
    source.addEventListener("error", (e) => {
      // The server's own `event: error` carries data; a dropped connection does not, and the browser tries again.
      const said = typeof (e as MessageEvent).data === "string";
      if (said || source.readyState === 2 || ++errors > RECONNECTS) lose();
    });
    tick = setInterval(() => {
      if (settled || closed) return;
      const now = Date.now();
      const l = liveRef.current;
      if (!l.running) return;
      if (!l.loader) {
        if (now - opened > NO_RUN_MS) lose();
        return;
      }
      const next = giveUp(l, now);
      if (next === l) return;
      setLive((cur) => giveUp(cur, now));
      if (!next.running) {
        finish();
        reread(true, RECOVER_TRIES);
      }
    }, GIVE_UP_TICK_MS);
    return () => {
      closed = true;
      finish();
      if (poll) clearTimeout(poll);
    };
  }, [draftId, streamRun, client]);

  // ── the outbox: back online, the waiting messages go, in order ───────────────────────────────────────────────
  const flush = useCallback(async () => {
    const id = idRef.current;
    if (!id || !client.outbox(id).length) return;
    setSave("saving");
    const { sent, refused } = await client.flush(id);
    const left = client.outbox(id);
    setPending((p) =>
      p.filter((m) => left.some((x) => x.clientId === m.clientId)).map((m) => ({ ...m, queued: true })),
    );
    const last = sent[sent.length - 1];
    if (last) adopt(last.draft, last.run_id);
    if (refused.length) {
      setBox((b) => [b, ...refused.map((r) => r.message.text)].filter(Boolean).join("\n"));
      setProblem(refused[0]!.error.text);
    }
    setSave(left.length ? "offline" : refused.length ? "changed" : "saved");
  }, [client, adopt]);

  useEffect(() => {
    const offline = () => setSave("offline");
    const online = () => {
      setSave((s) => (s === "offline" ? (savedAt ? "saved" : "idle") : s));
      void flush();
      setNetTick((n) => n + 1); // S-04's autosave tries again
    };
    window.addEventListener("offline", offline);
    window.addEventListener("online", online);
    if (navigator.onLine && draftId && client.outbox(draftId).length) void flush();
    return () => {
      window.removeEventListener("offline", offline);
      window.removeEventListener("online", online);
    };
  }, [flush, client, draftId, conversation, savedAt]);

  // ── S-04: the box saves itself ─────────────────────────────────────────────────────────────────────────────
  const saveBox = useCallback(
    (text: string): Promise<void> => {
      const run = async () => {
        const words = text.trim();
        if (!words || text === savedText.current) return;
        setSave("saving");
        try {
          let id = idRef.current;
          if (!id) {
            const made = await client.create(createKey.current, text);
            id = made.draft.id;
            idRef.current = id;
            setDraftId(id);
            firstMid.current = made.draft.messages[0]?.id ?? null;
            setBoxSpans(made.draft.messages[0]?.spans ?? null);
            adopt(made.draft, made.run_id);
          } else if (firstMid.current) {
            const out = await client.editMessage(id, firstMid.current, text);
            setBoxSpans(out.message?.spans ?? null);
            adopt(out.draft, out.run_id);
          } else {
            const out = await client.addMessage(id, { clientId: newClientId(), text, via: "typed" });
            firstMid.current = out.message?.id ?? null;
            setBoxSpans(out.message?.spans ?? null);
            adopt(out.draft, out.run_id);
          }
          markSaved(text);
          setProblem(null);
          setSave("saved");
        } catch (err) {
          failed(err);
        }
      };
      chain.current = chain.current.then(run, run);
      return chain.current;
    },
    [client, adopt, failed, markSaved],
  );

  // A note waiting after the typed words (BLD-C150) is not part of the first message: only what was typed saves.
  const boxTyped = box.slice(0, firstEnd(box, voiceNotes));
  useEffect(() => {
    if (conversation || !boxTyped.trim() || boxTyped === savedText.current) return;
    const t = setTimeout(
      () => {
        if (typeof navigator !== "undefined" && navigator.onLine === false) setSave("offline");
        else void saveBox(boxTyped);
      },
      firstMid.current ? SAVE_PAUSE_MS : CREATE_PAUSE_MS,
    );
    return () => clearTimeout(t);
  }, [boxTyped, conversation, saveBox, netTick]);

  // ── voice ─────────────────────────────────────────────────────────────────────────────────────────────────
  const ensureDraft = useCallback(async (): Promise<string | null> => {
    if (idRef.current) return idRef.current;
    try {
      const made = await client.create(createKey.current);
      idRef.current = made.draft.id;
      setDraftId(made.draft.id);
      adopt(made.draft, made.run_id);
      return made.draft.id;
    } catch (err) {
      failed(err);
      return null;
    }
  }, [client, adopt, failed]);

  const voiceOptions = useMemo(
    () => ({ fetch: client.fetch, resolveDraft: ensureDraft }),
    [client, ensureDraft],
  );
  // S-04 starts with no draft: the hook asks for one inside the press, and keeps the same capture throughout.
  const voice = useVoiceCapture(givenId ?? "", voiceOptions);

  /** A finished note. S-04 with an empty box: it becomes the first message at once, with its stream, so the draft
   * forms "as if typed" and the English copy stays with it (C-PROMPT.voice "Stopped"). Otherwise its words join the
   * box, and go with "Add to your draft" (S-04B) or the box's autosave (S-04). */
  const takeNote = useCallback(
    (note: VoiceNote) => {
      const words = note.text;
      if (!words.trim()) return;
      const first = !conversation && !firstMid.current && !savedText.current && !box.trim();
      if (voiceNotes.some((n) => n.streamId === note.streamId)) return; // taken already
      if (!first) {
        // BLD-C150: the note waits after the typed words, editable, and goes as its own message. A second note
        // while one waits joins after it with its own stream and English copy.
        const prefix = box.trim() ? box.replace(/\s+$/, "") : "";
        setVoiceNotes((held) => [
          ...held,
          { streamId: note.streamId, text: words, textEn: note.textEn, prefix },
        ]);
        setBox(prefix ? `${prefix} ${words}` : words);
        return;
      }
      setVoiceNotes([{ streamId: note.streamId, text: words, textEn: note.textEn, prefix: null }]);
      setBox(words);
      markSaved(words); // the autosave waits for this post rather than racing it
      const run = async () => {
        const id = idRef.current ?? (await ensureDraft());
        if (!id) return;
        setSave("saving");
        try {
          const out = await client.addMessage(id, {
            clientId: newClientId(),
            text: words,
            via: "voice",
            streamId: note.streamId,
          });
          firstMid.current = out.message?.id ?? null;
          setBoxSpans(out.message?.spans ?? null);
          adopt(out.draft, out.run_id);
          setSave("saved");
        } catch (err) {
          markSaved(null); // the box's autosave takes the words instead, once it can
          failed(err);
          setNetTick((n) => n + 1);
        }
      };
      chain.current = chain.current.then(run, run);
    },
    [box, voiceNotes, conversation, client, adopt, failed, ensureDraft, markSaved],
  );

  const handled = useRef<VoiceCaptureState | null>(null);
  const { state: voiceState, reset: voiceReset } = voice;
  useEffect(() => {
    const s = voiceState;
    if (handled.current === s) return;
    // Taken on the next tick, once per state: the capture is an outside system telling the screen what it heard.
    const t = setTimeout(() => {
      if (handled.current === s) return;
      handled.current = s;
      if (s.status === "done") {
        takeNote(s.note);
        voiceReset();
      } else if (s.status === "paused" && s.note) {
        takeNote(s.note);
      } else if (s.status === "failed" && s.text.trim()) {
        const heard = s.text;
        setBox((b) => (b.trim() ? `${b.replace(/\s+$/, "")} ${heard}` : heard)); // nothing heard is lost
      }
    }, 0);
    return () => clearTimeout(t);
  }, [voiceState, voiceReset, takeNote]);

  // ── S3 "Voice first" (BLD-C175): on a phone's empty S-04, listening starts at once, once the page is shown, no
  // earlier draft is offered and the browser already allows the microphone; otherwise the phone starts with typing,
  // exactly as the default does. Kill switches beat the flag: the page says "voice_off" when voice cannot run. ──
  const screen = conversation ? "S-04B" : "S-04";
  const voiceFirst = phone ? (flags?.voiceFirst ?? null) : null;
  const listenTried = useRef(false);
  const autoListen = useRef<"waiting" | "logged" | null>(null);
  const live$ = useRef({ box, status: voice.state.status });
  useEffect(() => {
    live$.current = { box, status: voice.state.status };
  });
  const { start: voiceStart, stop: voiceStop } = voice;
  useEffect(() => {
    // A phone's new S-04 (no earlier draft offered), with the flags handed in, in either variant.
    if (listenTried.current || !flags || !phone || conversation || !recentChecked || existing) return;
    let gone = false;
    const begin = () => {
      if (gone || listenTried.current) return;
      listenTried.current = true;
      // The exposure: only the browser knows this is a phone (lane A's reader logs it, BLD-C173).
      flagEvent("s3", "s3.exposure", "shown", "S-04");
      if (!voiceFirst) return;
      if (voiceFirst === "voice_off") {
        flagEvent("s3", "s3.listen", "voice_off", "S-04");
        return;
      }
      void micAllowed().then((ok) => {
        if (!ok) {
          flagEvent("s3", "s3.listen", "no_permission", "S-04");
          return;
        }
        // Not if the person has begun typing or speaking meanwhile, or the tab went away again.
        if (live$.current.box.trim() || live$.current.status !== "idle") return;
        if (document.visibilityState !== "visible") return;
        autoListen.current = "waiting";
        void voiceStart();
      });
    };
    if (document.visibilityState === "visible") {
      begin();
      return () => {
        gone = true;
      };
    }
    // A tab opened in the background never listens: it starts when the person first looks at it (BLD-C175).
    const onShow = () => {
      if (document.visibilityState !== "visible") return;
      document.removeEventListener("visibilitychange", onShow);
      begin();
    };
    document.addEventListener("visibilitychange", onShow);
    return () => {
      gone = true;
      document.removeEventListener("visibilitychange", onShow);
    };
  }, [flags, phone, voiceFirst, conversation, recentChecked, existing, voiceStart]);
  useEffect(() => {
    if (autoListen.current !== "waiting") return;
    const s = voiceState.status;
    if (s === "recording") {
      autoListen.current = "logged";
      flagEvent("s3", "s3.listen", "started", "S-04", idRef.current);
    } else if (s === "failed" || s === "blocked" || s === "paused") {
      autoListen.current = "logged";
      flagEvent("s3", "s3.listen", "failed", "S-04", idRef.current);
    }
  }, [voiceState]);
  const listening =
    voiceFirst === "listen" && ["asking", "recording", "sending"].includes(voice.state.status);
  const typeInstead = () => {
    voiceStop();
    flagEvent("s3", "s3.listen", "typed_instead", screen, idRef.current);
    requestAnimationFrame(() => boxRef.current?.focus());
  };

  // ── sending ───────────────────────────────────────────────────────────────────────────────────────────────
  const send = useCallback(async () => {
    const text = box.trim();
    if (!text) return;
    const out = messagesFor(box, voiceNotes);
    if (out.some((m) => m.text.length > MAX_MESSAGE)) {
      setProblem(COMPOSE_COPY.tooLong);
      return;
    }
    setProblem(null);
    const held = voiceNotes;
    // S3's second metric, on a phone with the flags in play: each voice note going now, as heard or corrected.
    const notesSent = flags && phone ? noteOutcomes(box, held) : [];
    const logNotes = (id: string) => {
      for (const outcome of notesSent) flagEvent("s3", "s3.note", outcome, screen, id);
    };

    if (!conversation) {
      // S-04: the typed words are already the first message (saved as typed, or a voice note posted when it
      // finished); each note waiting after them goes now as its own message (BLD-C150), then the
      // conversation opens.
      const typed = box.slice(0, firstEnd(box, held));
      const spoken = spokenAfterFirst(box, held);
      await saveBox(typed);
      await chain.current;
      const id = idRef.current;
      if (!id || !firstMid.current || savedText.current !== typed) return; // not saved yet (offline): every word stays
      for (let i = 0; i < spoken.length; i += 1) {
        setSave("saving");
        try {
          const sent = await client.addMessage(id, spoken[i]!);
          adopt(sent.draft, sent.run_id);
          setSave("saved");
        } catch (err) {
          // The notes that did not go stay in the box, each with its stream; the ones that went are not sent twice.
          const back = backInBox(typed, spoken.slice(i), held);
          setBox(back.box);
          setVoiceNotes(back.notes);
          failed(err);
          return;
        }
      }
      setVoiceNotes([]);
      logNotes(id);
      handedOver.add(id);
      router.push(`/share/${id}`);
      return;
    }

    // S-04B: each message with its own client_id on every try, in order; what cannot go yet waits, in order.
    const id = idRef.current;
    if (!id) return;
    setBox("");
    setVoiceNotes([]);
    setPending((p) => [...p, ...out.map((m) => ({ ...m, queued: false }))]);
    setSave("saving");
    for (let i = 0; i < out.length; i += 1) {
      const m = out[i]!;
      try {
        const sent = await client.addMessage(id, m);
        setPending((p) => p.filter((x) => x.clientId !== m.clientId));
        adopt(sent.draft, sent.run_id);
      } catch (err) {
        const rest = out.slice(i);
        if (
          err instanceof DraftError &&
          (err.offline || err.status >= 500 || err.status === 408 || err.status === 429)
        ) {
          const kept = rest.map((x) => client.queue(id, x));
          setPending((p) =>
            p.map((x) => {
              const k = kept.find((y) => y.clientId === x.clientId);
              return k ? { ...k, queued: true } : x;
            }),
          );
          setSave("offline");
          return;
        }
        // Refused: the words that did not go come back to the box, each note still waiting with its own stream.
        setPending((p) => p.filter((x) => !rest.some((r) => r.clientId === x.clientId)));
        const back = backInBox("", rest, held);
        setBox((b) => (b ? `${back.box}\n${b}` : back.box));
        setVoiceNotes(back.notes);
        failed(err);
        return;
      }
    }
    logNotes(id);
    setSave(client.outbox(id).length ? "offline" : "saved");
  }, [box, voiceNotes, conversation, client, adopt, failed, saveBox, router, flags, phone, screen]);

  // ── Team up from a similar idea (C-PREVIEW → lane F's C-SHEET-TEAMUP; J-SIMILAR/3–5) ───────────────────────
  const [waiting, setWaiting] = useState<Record<string, string>>({});
  const refresh = useCallback(() => {
    const id = idRef.current;
    if (id)
      client.get(id).then(
        (d) => adopt(d),
        () => undefined,
      );
  }, [client, adopt]);
  const teamUp = useTeamUpSheet({
    onSent: (sent) => {
      setWaiting((w) => ({ ...w, [sent.ideaId]: sent.after?.line ?? "" }));
      refresh();
    },
    onWithdrawn: (sent) => {
      setWaiting((w) => Object.fromEntries(Object.entries(w).filter(([k]) => k !== sent.ideaId)));
      refresh();
    },
    draftId: draftId ?? undefined,
    draftTitle: typeof live.parts.title.value === "string" ? live.parts.title.value : undefined,
  });

  // ── S1 "Interview" (BLD-C172): after the first telling, up to three skippable questions, then the draft ───────
  // The questions start on S-04B for a draft just told on this device (from S-04's "Start my draft" or Home), never
  // on one picked up later (ComposeResume.md draws the default there); a reload or another device carries on from
  // the place the server keeps. Each answer goes into the draft through the messages path, kept without building;
  // the last question, or moving on, builds it once.
  const told = (draft?.char_count ?? 0) >= (draft?.min_chars ?? MIN_CHARS);
  const question = interviewOn && conversation ? nextQuestion(place) : null;
  useEffect(() => {
    const id = draft?.id;
    if (!interviewOn || !conversation || !id || !told || pickedUp || place.started || place.ended) return;
    if (ivAsked.current.start) return;
    ivAsked.current.start = true;
    client.interview(id, { action: "start" }).then(
      (out) => setPlace(out.interview),
      () => setPlace((p) => (p.started ? p : { ...p, started: true })), // asked anyway; the first answer starts it
    );
  }, [interviewOn, conversation, draft?.id, told, pickedUp, place.started, place.ended, client]);
  // The flag turned off with answers waiting: they are built now, so nothing waits for a build that will not come.
  useEffect(() => {
    const id = draft?.id;
    if (interviewOn || !id || ivAsked.current.finish) return;
    if (!place.started || place.ended || !Object.values(place.done).includes("answered")) return;
    ivAsked.current.finish = true;
    client.interview(id, { action: "finish" }).then(
      (out) => {
        setPlace(out.interview);
        if (out.draft) adopt(out.draft, out.run_id);
      },
      () => undefined,
    );
  }, [interviewOn, draft?.id, place, client, adopt]);

  const ivStep = useCallback(
    async (step: InterviewStep): Promise<InterviewResponse | null> => {
      const id = idRef.current;
      if (!id) return null;
      setIvBusy(true);
      setIvError(null);
      try {
        const out = await client.interview(id, step);
        setIvMoved(true);
        setPlace(out.interview);
        if (out.draft) adopt(out.draft, out.run_id);
        else if (out.run_id) setStreamRun(out.run_id);
        if (out.interview.ended) requestAnimationFrame(() => boxRef.current?.focus());
        return out;
      } catch (err) {
        // The server's own words under the question; offline, the task bar says so ("Unsaved, you're offline").
        if (err instanceof DraftError && err.offline) setSave("offline");
        else setIvError(err instanceof DraftError ? err.text : null);
        return null;
      } finally {
        setIvBusy(false);
      }
    },
    [client, adopt],
  );
  /** "Move to Review" while questions wait: the draft is built with what was answered, then on to Check it. It goes
   * only once the server says the questions are over; if that fails, the person stays, with the failure's words under
   * the question and the button still there, so no answer is left waiting for a build (BLD-C172). */
  const moveDuringQuestions = (e: MouseEvent<HTMLAnchorElement>) => {
    const href = draftId ? `/share/${draftId}/check` : null;
    if (!question || !href) return;
    e.preventDefault();
    if (ivBusy) return;
    void ivStep({ action: "finish" }).then((out) => {
      if (out?.interview.ended) router.push(href);
    });
  };
  const oftenWords = live.parts.often.value;
  const interviewCard = question ? (
    <InterviewCard
      key={question}
      question={question}
      business={draft?.sorting?.kind?.value === "business_idea"}
      suggestion={typeof oftenWords === "string" && oftenWords.trim() ? oftenWords : null}
      busy={ivBusy}
      error={ivError}
      headingLevel={phone ? 3 : 2}
      focusOnShow={ivMoved}
      onAnswer={(text) => {
        const clientId = (answerKeys.current[question] ??= newClientId());
        void ivStep({ action: "answer", question, text, clientId });
      }}
      onSkip={() => void ivStep({ action: "skip", question })}
    />
  ) : null;
  const panelInterview: PanelInterview | null = !interviewOn
    ? null
    : !conversation
      ? { stage: "intro" }
      : question
        ? { stage: "asking", card: phone ? interviewCard : null, soFar: soFarLine(live) }
        : null;

  // ── keys: P focuses the box (C-PROMPT.keys/3) ─────────────────────────────────────────────────────────────
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        (e.key === "p" || e.key === "P") &&
        !e.metaKey &&
        !e.ctrlKey &&
        !e.altKey &&
        !isEditable(e.target)
      ) {
        e.preventDefault();
        boxRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!conversation) boxRef.current?.focus(); // S-04.empty/1: focus is in the box
  }, [conversation]);

  // The newest words and the receipt stay in view as the conversation grows.
  const threadRef = useRef<HTMLDivElement>(null);
  const lastCount = (draft?.messages.length ?? 0) + pending.length;
  useEffect(() => {
    const el = threadRef.current;
    if (el && typeof el.scrollTo === "function") el.scrollTo({ top: el.scrollHeight });
  }, [lastCount, live.receipt]);

  // ── what the screen shows ─────────────────────────────────────────────────────────────────────────────────
  const messages: Message[] = draft?.messages ?? [];
  // S-04B.layout/2: each message keeps its own receipt, as the draft read keeps it (BLD-C184). Between a run's end
  // on the stream and the read that follows, the last message shows the receipt the stream just gave; so does a
  // read that keeps only the latest receipt.
  const perMessage = messages.some((m) => Array.isArray(m.receipt));
  const streamedOnly = !live.running && draft?.run?.state === "running";
  const receiptFor = (m: Message, last: boolean): string[] =>
    last && (streamedOnly || !perMessage) && live.receipt.length ? live.receipt : (m.receipt ?? []);
  const chars = conversation ? (draft?.char_count ?? 0) : Math.max(box.trim().length, draft?.char_count ?? 0);
  const minChars = draft?.min_chars ?? MIN_CHARS;
  const sendingDetail = pending.length > 0;
  // DEC-118 (BLD-C195): "Move to Review" waits only for the minimum and for nothing building, on the phone's dock as
  // in the panel. A run the stream lost or gave up on has stopped building here, as a failed run has on the worker.
  const readiness: Readiness = readinessOf({
    chars,
    minChars,
    sending: sendingDetail,
    running: live.running,
    saved: Boolean(draftId) && !draft?.merged_into && (draft?.char_count ?? 0) >= minChars,
  });
  const checkHref = draftId ? `/share/${draftId}/check` : null;
  const hiddenActions = draftId
    ? {
        show: async (hid: string, reason: ShowReason) => {
          const d = await client.showHidden(draftId, hid, reason);
          setLive((l) => ({ ...l, hidden: l.hidden.map((x) => (x.id === d.id ? d : x)) }));
        },
        hide: async (hid: string) => {
          const d = await client.hideHidden(draftId, hid);
          setLive((l) => ({ ...l, hidden: l.hidden.map((x) => (x.id === d.id ? d : x)) }));
        },
      }
    : null;
  const changePart = draftId
    ? async (part: Parameters<DraftClient["setPart"]>[1], value: unknown) => {
        const out = await client.setPart(draftId, part, { value });
        adopt(out.draft, out.run_id);
      }
    : undefined;
  const boxIsSaved = boxTyped === savedBox;
  const hasWords = box.trim().length > 0 || Boolean(draftId);
  // Each note's English copy shows while its words are as heard (DEC-108): changed, the server keeps no copy.
  const english = englishFor(box, voiceNotes);
  const failedVoice = voice.state.status === "failed" ? voiceFailedLine(voice.state.reason) : null;
  const signInHref = `/sign-in?next=${encodeURIComponent(draftId ? `/share/${draftId}` : "/share")}`;
  const count = countLine(conversation ? chars + box.trim().length : box.trim().length, minChars);

  const prompt = (
    <Prompt
      ref={boxRef}
      value={box}
      onChange={(v) => {
        setBox(v);
        if (!v.trim()) setVoiceNotes([]); // an emptied box holds no note any more
        if (problem) setProblem(null);
      }}
      onSend={() => void send()}
      onModEnter={() => {
        if (readiness === "ready" && checkHref) router.push(checkHref);
      }}
      sendLabel={conversation ? COMPOSE_COPY.add : COMPOSE_COPY.start}
      label={conversation ? PROMPT_COPY.moreLabel : PROMPT_COPY.firstLabel}
      placeholder={
        conversation
          ? PROMPT_COPY.moreLabel
          : phone
            ? PROMPT_COPY.firstPlaceholderPhone
            : PROMPT_COPY.firstPlaceholder
      }
      keyHint={!conversation}
      spans={!conversation && boxIsSaved ? boxSpans : null}
      // C-PROMPT.anatomy/2: the attach button (C-FILE.uploader) mounts in `attach` once POST /api/files lands
      // (c/files-2); a later round passes it here (BLD-C124, P-GAPS).
      source={!conversation ? quoteRange(box, quote) : null}
      voice={{
        state: voice.state,
        start: () => void voice.start(),
        stop: voice.stop,
        noticeShown: voice.noticeShown,
      }}
      device={device}
      micFirst={!conversation}
      english={english}
    >
      {problem ? <FieldMsg>{problem}</FieldMsg> : null}
      {/* Both regions stay mounted, so a notice that appears in them is announced (WCAG 4.1.3). */}
      <div className="vlive" role="status">
        {voice.state.status === "paused" ? <p className="vnotice">{voice.state.banner}</p> : null}
      </div>
      <div className="vlive" role="alert">
        {failedVoice === "paused" ? (
          <p className="vnotice">{COMPOSE_COPY.voicePaused}</p>
        ) : failedVoice === "sign_in" ? (
          <p className="vnotice">
            <a href={signInHref}>{COMPOSE_COPY.signInAgain}</a>
          </p>
        ) : null}
      </div>
    </Prompt>
  );

  const taskbar = (
    <Taskbar
      title={conversation ? COMPOSE_COPY.title : ""}
      step="tell"
      steps={conversation}
      save={save}
      savedAt={savedAt}
      savedLabel={savedLabel}
      closeHref="/"
      closeLabel={COMPOSE_COPY.close}
    />
  );

  if (conversation && loadError !== null && !draft) {
    return (
      <div className="cz has">
        {taskbar}
        <p className="cz-gone" role="alert">
          {loadError}
        </p>
      </div>
    );
  }

  return (
    <div className={`cz${conversation ? " has" : " start"}${!hasWords && !existing ? " blank" : ""}`}>
      {conversation || hasWords || existing ? taskbar : null}
      <p className="pstep ph-only">
        {COMPOSE_COPY.stepPhone} <b>{COMPOSE_COPY.stepNowPhone}</b>
        <span className="pnext">{COMPOSE_COPY.nextPhone}</span>
      </p>
      {elsewhere ? (
        <div className="ban" role="alert">
          <p className="bt">{elsewhere}</p>
          <div className="ba">
            <Button
              variant="line"
              size="sm"
              onClick={() => {
                const id = idRef.current;
                if (!id) return;
                client
                  .get(id, true)
                  .then((d) => {
                    adopt(d);
                    setElsewhere(null);
                    setSave(savedText.current === boxTyped ? "saved" : "changed");
                    setNetTick((n) => n + 1); // S-04's box saves again now that this device is the editor
                  })
                  .catch(failed);
              }}
            >
              {COMPOSE_COPY.continueDraft}
            </Button>
          </div>
        </div>
      ) : null}
      <div className="cmain">
        <section className="convo" aria-label="Tell it">
          {conversation ? (
            <>
              <div
                ref={threadRef}
                className="thread"
                role="log"
                aria-label="Your words and what the draft did"
                tabIndex={0}
              >
                <div className="tin">
                  {pickedUp !== null && draft ? (
                    <div className="ban" role="region" aria-label="Your draft">
                      <span className="ic" aria-hidden="true">
                        <SavedOnIcon device={pickedUp.device} size={16} />
                      </span>
                      <p className="bt">{COMPOSE_COPY.pickedUp}</p>
                      <p className="bm">{pickedUp.line}</p>
                      <div className="ba">
                        <button type="button" className="tb" onClick={() => router.push("/share?new=1")}>
                          {COMPOSE_COPY.startNewInstead}
                        </button>
                      </div>
                    </div>
                  ) : null}
                  {/* The phone board's heading and help on this state (PhoneComposeResume.md, default). */}
                  <div className="chero ph-only">
                    <h1 className="cq">{COMPOSE_COPY.questionPhone}</h1>
                    <p className="cql">{COMPOSE_COPY.helpPhone}</p>
                  </div>
                  {draft?.origin && "label" in draft.origin ? (
                    <div className="ban blue" role="region" aria-label="From your email">
                      <span className="ic" aria-hidden="true">
                        <IconMail />
                      </span>
                      <p className="bt">{String((draft.origin as { label?: unknown }).label ?? "")}</p>
                      <p className="bm">{COMPOSE_COPY.emailNote}</p>
                    </div>
                  ) : null}
                  {messages.map((m, i) => (
                    <MessageItem
                      key={m.id}
                      message={m}
                      when={pickedUp?.earlier.has(m.id) ? (m.at_label_earlier ?? m.at_label) : m.at_label}
                      quote={quote}
                      onEdit={async (text) => {
                        if (!draftId) return;
                        const out = await client.editMessage(draftId, m.id, text);
                        adopt(out.draft, out.run_id);
                      }}
                      last={i === messages.length - 1 && pending.length === 0}
                      receipt={
                        question ? [] : receiptFor(m, i === messages.length - 1 && pending.length === 0)
                      }
                      suggestions={question ? [] : live.suggestions}
                      running={live.running}
                      onSuggestion={(s) => {
                        // A suggestion does what it says: "Change the title" opens the title (behaviour/5).
                        if (s === PANEL_COPY.changeTitle && changePart) panelRef.current?.editTitle();
                        else boxRef.current?.focus();
                      }}
                    />
                  ))}
                  {pending.map((m) => (
                    <div key={m.clientId} className="msg me queued">
                      <div className="bub">
                        <p className="btx">{m.text}</p>
                      </div>
                      {m.queued ? <p className="qtag">{COMPOSE_COPY.queued}</p> : null}
                    </div>
                  ))}
                  {/* On a phone the card is in the draft's sheet (PhoneCompose.md). */}
                  {question && !phone ? <div className="ivg">{interviewCard}</div> : null}
                </div>
              </div>
              <div className="cdock">
                {prompt}
                <p className="phint">
                  {live.running || sendingDetail ? COMPOSE_COPY.working : COMPOSE_COPY.more}
                </p>
                <p className="ccount ph-only">{count}</p>
                <p className="cpriv ph-only">{COMPOSE_COPY.privacyPhone}</p>
              </div>
            </>
          ) : (
            <div className="stage2">
              <div className="chero">
                <h1 className="cq dk-only">{COMPOSE_COPY.question(firstName)}</h1>
                <h1 className="cq ph-only">{COMPOSE_COPY.questionPhone}</h1>
                <p className="cql ph-only">{COMPOSE_COPY.helpPhone}</p>
              </div>
              {existing && !hasWordsTyped(box) ? (
                <div className="ban" role="region" aria-label="Your earlier draft">
                  <span className="ic" aria-hidden="true">
                    <SavedOnIcon device={existing.saved_on?.device ?? null} />
                  </span>
                  <p className="bt">
                    {COMPOSE_COPY.existing(existing.saved_labels?.prompt_day ?? "", existing.title)}
                  </p>
                  <p className="bm">
                    <span className="dk-only">
                      {COMPOSE_COPY.existingLine(existing.saved_labels?.prompt_line ?? "")}
                    </span>
                    <span className="ph-only">{existing.saved_labels?.prompt_line ?? ""}</span>
                  </p>
                  <div className="ba">
                    <Button variant="line" size="sm" onClick={() => router.push(`/share/${existing.id}`)}>
                      {phone ? COMPOSE_COPY.continuePhone : COMPOSE_COPY.continueDraft}
                    </Button>
                    <button
                      type="button"
                      className="tb"
                      onClick={() => {
                        setExisting(null);
                        boxRef.current?.focus();
                      }}
                    >
                      {COMPOSE_COPY.startNew}
                    </button>
                  </div>
                </div>
              ) : null}
              {prompt}
              <p className="hpnote dk-only">{PROMPT_COPY.help}</p>
              <p className="ccount ph-only">{count}</p>
              {!box.trim() && !existing ? (
                <Starters
                  device={device}
                  onPick={(opener) => {
                    setBox(opener);
                    requestAnimationFrame(() => {
                      const el = boxRef.current;
                      if (!el) return;
                      el.focus();
                      el.setSelectionRange(opener.length, opener.length);
                    });
                  }}
                />
              ) : null}
              <p className="cpriv ph-only">{COMPOSE_COPY.privacyPhone}</p>
            </div>
          )}
        </section>
        {/* Said once when the words become enough, not on every key (C-PROMPT.states). */}
        <p className="vh ph-only" aria-live="polite">
          {count === COMPOSE_COPY.enough ? count : ""}
        </p>
        <DraftPanel
          ref={panelRef}
          live={live}
          readiness={readiness}
          moveHref={checkHref}
          hidden={hiddenActions}
          onChangePart={changePart}
          onFocusQuote={setQuote}
          phone={phone}
          offline={save === "offline"}
          onBlocked={() => boxRef.current?.focus()}
          teamUp={{ open: teamUp.open, waiting, opener: teamUpOpener }}
          interview={panelInterview}
          onMove={question ? moveDuringQuestions : undefined}
        />
        {teamUp.sheet}
      </div>
      {phone && listening ? (
        // S3 "Voice first": while listening the dock holds "Type instead" and the stop with its count (PhoneCompose.md,
        // state Speaking).
        <Dock>
          <div className="vdock">
            <button type="button" className="tb tinst" onClick={typeInstead}>
              {COMPOSE_COPY.typeInstead}
            </button>
            <Button
              size="full"
              className="stopb"
              busy={voice.state.status === "sending"}
              onClick={voiceStop}
              icon={<span className="stopsq" aria-hidden="true" />}
            >
              {voice.state.status === "recording" && voice.state.text.trim()
                ? COMPOSE_COPY.stopAt(voice.state.seconds)
                : COMPOSE_COPY.stop}
            </Button>
          </div>
        </Dock>
      ) : phone ? (
        <Dock>
          {readiness === "ready" && checkHref ? (
            <ButtonLink href={checkHref} size="full" onClick={question ? moveDuringQuestions : undefined}>
              {PANEL_COPY.move}
            </ButtonLink>
          ) : (
            <Button size="full" disabled onDisabledClick={() => boxRef.current?.focus()}>
              {PANEL_COPY.move}
            </Button>
          )}
        </Dock>
      ) : null}
    </div>
  );
}

/** The banner's mark follows the device its line names: the drawn phone, or a laptop (BLD-C185). A line that
 * names no device keeps the phone the boards draw. */
function SavedOnIcon({ device, size }: { device: Device | null; size?: number }) {
  return device === "laptop" ? <IconLaptop size={size} /> : <IconDevice size={size} />;
}

function hasWordsTyped(box: string): boolean {
  return box.trim().length > 0;
}

function MessageItem({
  message,
  when,
  quote,
  onEdit,
  last,
  receipt,
  suggestions,
  running,
  onSuggestion,
}: {
  message: Message;
  /** "Just now", or "Friday, 8:42 pm, on your phone" for a message picked up from a saved draft. */
  when: string | undefined;
  quote: string | null;
  onEdit(text: string): Promise<void>;
  last: boolean;
  receipt: string[];
  suggestions: string[];
  running: boolean;
  onSuggestion(s: string): void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(message.text);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function done() {
    const words = text.trim();
    if (!words) {
      setError("Give it a few words.");
      return;
    }
    setBusy(true);
    try {
      await onEdit(text);
      setEditing(false);
      setError(null);
    } catch (err) {
      setError(err instanceof DraftError ? err.text : null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="msg me">
        <div className="bub">
          {editing ? (
            <>
              <label className="vh" htmlFor={`edit-${message.id}`}>
                {COMPOSE_COPY.edit}
              </label>
              <textarea
                id={`edit-${message.id}`}
                className="cmore"
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    setEditing(false);
                    setText(message.text);
                  }
                }}
              />
              {error ? <FieldMsg>{error}</FieldMsg> : null}
              <div className="edf">
                <button
                  type="button"
                  className="rdone"
                  aria-busy={busy || undefined}
                  onClick={() => void done()}
                >
                  {COMPOSE_COPY.done}
                </button>
              </div>
            </>
          ) : (
            <Words text={message.text} spans={message.spans ?? []} quote={quote} />
          )}
          {message.text_en ? (
            <div className="cen">
              <p className="cen-l">{message.text_en_label}</p>
              <p className="cen-t">{message.text_en}</p>
            </div>
          ) : null}
        </div>
        <div className="mact">
          <span className="who">{COMPOSE_COPY.you}</span>
          <span className="meta">{when}</span>
          {editing ? null : (
            <button
              type="button"
              className="tb mt-edit"
              onClick={() => {
                setText(message.text);
                setEditing(true);
              }}
            >
              <IconPencil />
              {COMPOSE_COPY.edit}
            </button>
          )}
        </div>
      </div>
      {receipt.length && !(last && running) ? (
        <div className="sysg">
          {receipt.map((line) => (
            <div key={line} className="msg sys">
              <span className="sdot" aria-hidden="true" />
              <p>{line}</p>
            </div>
          ))}
          {last && suggestions.length ? (
            <div className="nexts">
              {suggestions.slice(0, 2).map((s) => (
                <button key={s} type="button" className="chip nx" onClick={() => onSuggestion(s)}>
                  {s}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </>
  );
}
