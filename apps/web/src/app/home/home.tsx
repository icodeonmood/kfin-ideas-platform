"use client";
/**
 * S-03 Home (`/home`, BLD-C143): ask first. The question as the heading, the prompt box (C-PROMPT, the same one Tell
 * it uses) with the help line and the starters, "Jump back in", then Needs you, Your ideas, Find your crew, Or share
 * from where you already are, and The Ones (S-03.sections). A first visit replaces the first three with "What
 * happens after you share". Copy word for word from reference/copy/Home.md and PhoneHome.md.
 *
 * Sending from the box (P-ROUTES.graph, V-ACC.share/3): `POST /api/drafts { text }` makes the draft with the words as
 * its first message, and the person lands on S-04B on that draft; they never see the empty S-04. Enter sends; Shift
 * and Enter adds a line (C-PROMPT.keys). A starter puts its opener in the box and does not send.
 * Attach (C-PROMPT.attach, DEC-124, BLD-C214): the "+" first in the box's tool row. Home has no draft until it sends,
 * so the first file makes it, with the same call Share a problem's first send makes (`POST /api/drafts`), once; the
 * file goes into it and its row stays in the box. Sending then adds the words to THAT draft as its first message and
 * opens it, never a new one. Left unsent, it stays a private draft like any other.
 * Speaking (C-PROMPT.voice, walk item WF-02, BLD-C220): while the box is empty its round button is the microphone,
 * with "Tap to start speaking" and "Not recording until you do" beside it (Home.dc.html, PhoneHome.dc.html). It is
 * Share's own capture (`useVoiceCapture`), which asks for the draft inside the tap from the same create-once draft the
 * first file makes, so a file and a note always share one draft. A finished note goes into that draft at once, after
 * any typed words, and the person lands on S-04B on it, as after typing. The microphone is allowed for this site on
 * every page (DEC-128).
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { Prompt, PROMPT_COPY, STARTERS } from "@/components/compose/prompt";
import { QuestionsCard } from "@/components/review/qcard";
import { useTeamUpSheet, type TeamUpSent } from "@/components/teamup/teamup-sheet";
import { ButtonLink } from "@/components/ui/button";
import { Deck } from "@/components/ui/deck";
import { FieldMsg } from "@/components/ui/field";
import { OnesFan, OnesNext, OnesPost } from "@/components/ui/ones-fan";
import { Pill, type PillVariant } from "@/components/ui/pill";
import { SkeletonRows } from "@/components/ui/skeleton";
import { DraftClient, DraftError, newClientId } from "@/lib/compose/client";
import type { CrewCard, MyIdeaRow } from "@/lib/contracts";
import { COUNTS_EVENT } from "@/lib/inbox-events";
import { useVoiceCapture } from "@/lib/use-voice-capture";
import type { VoiceCaptureState, VoiceNote } from "@/lib/voice-capture";
import {
  cheer,
  keepFailedSets,
  loadCrew,
  loadMine,
  loadOnes,
  loadSets,
  readSets,
  type FetchLike,
  type HomeMine,
  type HomePost,
  type NeedsCard,
} from "@/lib/home/data";

import { useBoxFiles } from "../share/box-files";
import { COMPOSE_COPY, voiceFailedLine } from "../share/compose";

import { CrewCardView, requestDropped, requestedLast, shownAsColleague } from "./crew-card";

export const HOME_COPY = {
  question: (name: string) => `What keeps getting in your way, ${name}?`,
  questionFirst: (name: string) => `What gets in your way at work, ${name}?`,
  questionPhone: "What’s in your way?",
  questionPhoneFirst: "What gets in your way?",
  label: "Say it in your own words",
  placeholder: "Describe what's getting in your way",
  send: "Continue to Share a problem",
  help: PROMPT_COPY.help,
  phoneStarter: { label: "A wait that makes customers give up", opener: "Customers give up waiting when " },
  jump: "Jump back in",
  start: "Start here",
  allMine: "All my ideas",
  seeWall: "See the Wall",
  drafts: "Drafts",
  yourIdeas: "Your ideas",
  findCrew: "Find your crew",
  shareAnother: "Share another way",
  otherWays: "Other ways",
  whatNext: "What happens next",
  theWall: "The Wall",
  needs: "Needs you",
  needsAll: (n: number) => `All ${n} in Inbox`,
  openInbox: "Open the Inbox",
  needsNone: "Nothing needs you right now.",
  needsNoneMore: "When the review desk or a build team asks you something, it shows up here.",
  needsNonePhone: "Questions from the review desk or a build team show up here.",
  ideasOne: "Anything else slowing you or a customer down? Say it in the box at the top.",
  ideasNoneTitle: "No ideas yet",
  ideasNone:
    "Anything that slows you or a customer down counts. Say it in the box at the top, in your own words.",
  ideasNonePhone:
    "Anything that slows you or a customer down counts. Say it in the box below, in your own words.",
  ideasNoneAction: "Share your first problem",
  seeAll: "See all",
  crewNoneTitle: "No one close to yours yet",
  crewNone: "When someone shares an idea near yours or in your area, it shows up here so you can team up.",
  browseWall: "Browse the Wall",
  crewLabel: "Ideas close to yours",
  ways: "Or share from where you already are",
  waysPhone: "Or share from where you are",
  waysIntro: "Each one lands here as a draft. Nothing is sent until you check it.",
  outlook: "Forward it from Outlook",
  outlookBody: "Forward the thread that shows the problem. Your note on top becomes the draft.",
  teams: "Message it in Teams",
  teamsAddr: "1% Club",
  teamsBody: "Type or paste into a chat with 1% Club. Screenshots go straight in.",
  app: "Use the 1% Club app",
  soon: "Coming soon",
  appAddr: "Android and iOS",
  appBody: "Share from your phone, typed or spoken, in any language.",
  ones: "The Ones",
  onesSub: "Fixes that shipped, from the people behind them.",
  onesNoneTitle: "No Ones yet",
  onesNone: "When a shared fix ships and its result is measured, the people behind it are posted here first.",
  nextOne: "The next One could be you",
  nextOneBody: "Every fix here started with one person saying what kept going wrong.",
  share: "Share a problem",
  how: "What happens after you share",
  stages: [
    { n: "Shared", w: "You, about two minutes" },
    { n: "Checked and matched", w: "Automatic. Personal details hidden" },
    { n: "Reviewed", w: "Within 5 working days, with a reason" },
    { n: "Built", w: "If picked. You can join the team" },
    { n: "Shipped", w: "Then we measure what changed" },
  ],
  tooLong: "That's a lot for one go. Send this part, then carry on.",
  offline: "Unsaved, you’re offline",
  // A refused send shows the server's own words (DRAFT_MESSAGES); the pack draws no line of Home's own for a failed
  // send (C-PROMPT, V-FIELDS.tellit), so none is invented here (listed as a copy gap, BLD-C144).
  /** C-SKELETON/7's polite line; not drawn on the boards (listed for HR). */
  loadingNeeds: "Loading what needs you",
  loadingIdeas: "Loading your ideas",
  loadingCrew: "Loading ideas close to yours",
  loadingOnes: "Loading the Ones",
} as const;

const MAX_MESSAGE = 5000; // V-FIELDS.tellit/2

const WAYS_COUNT = 3;

/** Section 4's ways in that have their own switch (BLD-C183). */
export type WaysOn = { email: boolean; teams: boolean };
const WAYS_OFF: WaysOn = { email: false, teams: false };
/** Needs you's re-reads: one at a time, and a burst of Inbox events within this long of a read's start brings at
 * most one more read after it. */
export const REREAD_GAP_MS = 250;

/** Where each "Jump back in" card and section link goes (P-ROUTES.screens). */
export const HOME_LINKS = {
  myIdeas: "/my-ideas",
  drafts: "/my-ideas?filter=drafts",
  crew: "/crew",
  ways: "/share/other-ways",
  inbox: "/inbox",
  wall: "/wall",
  how: "/how-it-works",
  share: "/share",
} as const;

/** A note that failed because the session ended: sign in again and come back to Home (L-AUTH.states). */
const HOME_SIGN_IN = `/sign-in?next=${encodeURIComponent("/home")}`;

type Loaded<T> = { state: "loading" } | { state: "ready"; value: T };

const PILL_FOR: Record<string, PillVariant> = {
  neutral: "neutral",
  blue: "blue",
  warn: "warn",
  ok: "ok",
  bad: "bad",
};

function IconClock() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="12" cy="13" r="8" />
      <path d="M12 9v4l2.5 2M9.5 2.5h5" />
    </svg>
  );
}

function WayIcon({ kind }: { kind: "mail" | "chat" | "app" }) {
  const common = {
    width: 24,
    height: 24,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinejoin: "round" as const,
    strokeLinecap: "round" as const,
    "aria-hidden": true,
    focusable: false,
  };
  if (kind === "mail")
    return (
      <svg {...common}>
        <rect x="3" y="5" width="18" height="14" rx="2" />
        <path d="m3.5 6.5 8.5 6.5 8.5-6.5" />
      </svg>
    );
  if (kind === "chat")
    return (
      <svg {...common}>
        <path d="M4 5h16v11H9l-5 4z" />
        <path d="M8 9.5h8M8 12.5h5" />
      </svg>
    );
  return (
    <svg {...common}>
      <rect x="7" y="2.5" width="10" height="19" rx="2.5" />
      <path d="M11 18.5h2" />
    </svg>
  );
}

/** Desktop and phone words for one place; the other is display:none, so only one is ever read out. */
function Words({ desk, phone }: { desk: ReactNode; phone: ReactNode }) {
  return (
    <>
      <span className="hm-dt">{desk}</span>
      <span className="hm-ph">{phone}</span>
    </>
  );
}

function SectionHead({
  id,
  title,
  link,
}: {
  id: string;
  title: ReactNode;
  link?: { href: string; label: string };
}) {
  return (
    <div className="hm-shead">
      <h2 id={id} className="h2">
        {title}
      </h2>
      {link ? (
        <Link href={link.href} className="hm-more">
          {link.label}
        </Link>
      ) : null}
    </div>
  );
}

function JumpCard({
  href,
  title,
  count,
  faces,
}: {
  href: string;
  title: string;
  count?: number;
  faces?: string[];
}) {
  return (
    <Link href={href} className="hm-jc">
      {faces && faces.length ? (
        <span className="hm-jfaces" aria-hidden="true">
          {faces.map((f, i) => (
            <span key={`${f}-${i}`} className={`hm-jface t${i + 1}`}>
              {f}
            </span>
          ))}
        </span>
      ) : null}
      <span className="hm-jt">{title}</span>
      {count === undefined ? null : <span className="hm-jm">{count}</span>}
    </Link>
  );
}

function IdeaRow({ row }: { row: MyIdeaRow }) {
  return (
    <li className="hm-idea">
      <div className="hm-idea-b">
        <p className="hm-it">
          <Link href={row.href}>{row.title}</Link>
        </p>
        <p className="meta">{row.meta}</p>
      </div>
      <Pill variant={PILL_FOR[row.pill.variant] ?? "neutral"}>{row.pill.label}</Pill>
    </li>
  );
}

export function HomeScreen({
  firstName,
  firstVisit = false,
  outlookAddress = null,
  waysOn = WAYS_OFF,
  fetchImpl,
}: {
  firstName: string;
  firstVisit?: boolean;
  /** The 1% Club mailbox, when IT has given it (L-DRAFT.channels); otherwise the tile says only how. */
  outlookAddress?: string | null;
  /** Which ways in are open, from the server's `intake.email` and `intake.teams` switches (DEC-105, BLD-C183).
   * Unknown counts as off, as on S-H3 (BLD-A192). */
  waysOn?: WaysOn;
  /** Tests pass a fake; the screen uses the browser's. */
  fetchImpl?: FetchLike;
}) {
  const router = useRouter();
  const f = useMemo<FetchLike>(() => fetchImpl ?? ((input, init) => fetch(input, init)), [fetchImpl]);
  const client = useMemo(() => new DraftClient({ fetch: f as typeof fetch }), [f]);
  // The browser's device id, also left as a cookie, so the side bar's Drafts can say "on this laptop" (BLD-C147).
  useEffect(() => void client.device(), [client]);

  // ── the box ─────────────────────────────────────────────────────────────────────────────────────────────────
  const [box, setBox] = useState("");
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<{ text: string; kind: "error" | "warn" } | null>(null);
  const createKey = useRef<string>("");
  const boxRef = useRef<HTMLTextAreaElement>(null);

  const refused = useCallback((err: unknown) => {
    if (err instanceof DraftError && err.offline) setProblem({ text: HOME_COPY.offline, kind: "warn" });
    else if (err instanceof DraftError && err.text) setProblem({ text: err.text, kind: "error" });
  }, []);

  // ── files in the box (C-PROMPT.attach, BLD-C214): the first file makes the draft, once ────────────────────────
  const [draftId, setDraftId] = useState<string | null>(null);
  const fileDraft = useRef<Promise<string | null> | null>(null);
  const fileDraftKey = useRef<string>("");
  const draftForFiles = useCallback((): Promise<string | null> => {
    if (fileDraft.current) return fileDraft.current;
    if (!fileDraftKey.current) fileDraftKey.current = newClientId(); // a retried create finds the same draft
    const made = client.create(fileDraftKey.current).then(
      (r) => {
        setDraftId(r.draft.id);
        return r.draft.id;
      },
      (err: unknown) => {
        fileDraft.current = null; // the next file tries again
        refused(err);
        return null;
      },
    );
    fileDraft.current = made;
    return made;
  }, [client, refused]);
  const files = useBoxFiles({ draftId, resolveDraft: draftForFiles });
  const settleFiles = files.settle;
  /** The words' message key when they go into the file's draft: one message however often the send is retried. */
  const messageKey = useRef<string>("");

  const send = useCallback(async () => {
    const text = box.trim();
    if (!text || sending) return;
    if (text.length > MAX_MESSAGE) {
      setProblem({ text: HOME_COPY.tooLong, kind: "error" });
      return;
    }
    setProblem(null);
    setSending(true);
    let id: string;
    try {
      const made = fileDraft.current ? await fileDraft.current : null;
      if (made) {
        // A file made the draft: the words go into THAT draft as its first message, never a new draft.
        if (!messageKey.current) messageKey.current = newClientId();
        await client.addMessage(made, { clientId: messageKey.current, text: box, via: "typed" });
        id = made;
      } else {
        if (!createKey.current) createKey.current = newClientId(); // one draft per send, however often it is retried
        id = (await client.create(createKey.current, box)).draft.id;
      }
    } catch (err) {
      setSending(false);
      refused(err);
      return;
    }
    await settleFiles(); // every file in the box is on the draft before Tell it reads it
    try {
      router.push(`/share/${id}`);
    } catch {
      // The draft is made; the box is free again, and sending once more opens the same draft (same key).
      setSending(false);
    }
  }, [box, sending, client, router, refused, settleFiles]);

  // ── speaking (C-PROMPT.voice, WF-02, BLD-C220): Share's capture with Home's create-once draft ─────────────────────
  const voiceOptions = useMemo(
    () => ({ fetch: client.fetch, resolveDraft: draftForFiles }),
    [client, draftForFiles],
  );
  // Home starts with no draft: the hook asks for one inside the tap (`draftForFiles`), as Share's S-04 does.
  const voice = useVoiceCapture("", voiceOptions);
  /** One message key per note, so a note is never added twice however it is retried. */
  const noteKeys = useRef(new Map<string, string>());
  // One take at a time (BLD-C220 review fix): set while a note goes in, cleared when it fails back into the box, kept
  // once the page moves on.
  const taking = useRef(false);

  /** A finished note: into the draft at once, after the typed words if any, then on to S-04B, as after typing. A
   * failure keeps the words in the box and says why, as `send()` does. */
  const takeNote = useCallback(
    async (note: VoiceNote) => {
      const words = note.text;
      if (!words.trim() || taking.current) return; // a second note while one goes in adds nothing
      taking.current = true;
      const typed = box.trim() ? box : "";
      const both = typed ? `${typed.replace(/\s+$/, "")} ${words}` : words;
      const keep = (rest: string, err: unknown) => {
        taking.current = false;
        setBox(rest);
        createKey.current = "";
        messageKey.current = "";
        setSending(false);
        refused(err);
      };
      setProblem(null);
      setSending(true);
      setBox(both); // what goes, while it goes
      const id = await draftForFiles(); // the draft the tap asked for (or a file made); it has said why if none
      if (!id) {
        keep(both, null);
        return;
      }
      if (typed) {
        // The typed words first, as their own message, with send()'s key: one message however often it is retried.
        if (!messageKey.current) messageKey.current = newClientId();
        try {
          await client.addMessage(id, { clientId: messageKey.current, text: typed, via: "typed" });
        } catch (err) {
          keep(both, err);
          return;
        }
      }
      let key = noteKeys.current.get(note.streamId);
      if (!key) {
        key = newClientId();
        noteKeys.current.set(note.streamId, key);
      }
      try {
        await client.addMessage(id, { clientId: key, text: words, via: "voice", streamId: note.streamId });
      } catch (err) {
        keep(words, err); // any typed words are on the draft already; the note's words come back to the box
        return;
      }
      await settleFiles(); // every file in the box is on the draft before Tell it reads it
      try {
        router.push(`/share/${id}`);
      } catch {
        taking.current = false;
        setSending(false);
      }
    },
    [box, client, draftForFiles, refused, router, settleFiles],
  );

  const handledVoice = useRef<VoiceCaptureState | null>(null);
  const { state: voiceState, reset: voiceReset } = voice;
  useEffect(() => {
    const s = voiceState;
    if (handledVoice.current === s) return;
    // Taken on the next tick, once per state, as Share does: the capture is an outside system telling Home what it
    // heard.
    const t = setTimeout(() => {
      if (handledVoice.current === s) return;
      handledVoice.current = s;
      if (s.status === "done") {
        void takeNote(s.note);
        voiceReset();
      } else if (s.status === "paused" && s.note) {
        void takeNote(s.note);
      } else if (s.status === "failed" && s.text.trim()) {
        const heard = s.text;
        setBox((b) => (b.trim() ? `${b.replace(/\s+$/, "")} ${heard}` : heard)); // nothing heard is lost
        createKey.current = "";
        messageKey.current = "";
      }
    }, 0);
    return () => clearTimeout(t);
  }, [voiceState, voiceReset, takeNote]);
  const failedVoice = voice.state.status === "failed" ? voiceFailedLine(voice.state.reason) : null;

  const pick = (opener: string) => {
    setBox(opener);
    setProblem(null);
    createKey.current = "";
    messageKey.current = "";
    requestAnimationFrame(() => {
      const el = boxRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(opener.length, opener.length);
    });
  };

  // ── the sections ──────────────────────────────────────────────────────────────────────────────────────────────
  const [mine, setMine] = useState<Loaded<HomeMine | null>>({ state: "loading" });
  const [sets, setSets] = useState<Loaded<NeedsCard[]>>({ state: "loading" });
  const [crew, setCrew] = useState<Loaded<{ total: number; top: CrewCard[] } | null>>({ state: "loading" });
  const [ones, setOnes] = useState<Loaded<HomePost[] | null>>({ state: "loading" });
  const [crewAt, setCrewAt] = useState(0);
  // DEC-126 (WF-03b, BLD-C219). After a send the card reads "Requested" with "Withdraw" and goes to the end of the
  // deck, where the server keeps it after a reload (BLD-F094); it stays there until the next read. The deck follows
  // it, so "Requested" is in front when the sheet closes and the sheet's focus comes back to it (WCAG 2.4.3). After a
  // withdraw, from the card or from the sheet, "Team up" is drawn again where the card stands: nothing moves.
  const crewIds = crew.state === "ready" ? (crew.value?.top.map((c) => c.id) ?? []) : [];
  const onTeamUpSent = (s: TeamUpSent) => {
    if (!crewIds.includes(s.ideaId)) return;
    setCrew((c) =>
      c.state === "ready" && c.value
        ? { state: "ready", value: { ...c.value, top: requestedLast(c.value.top, s) } }
        : c,
    );
    setCrewAt(crewIds.length - 1);
  };
  const onTeamUpWithdrawn = (s: TeamUpSent) => {
    setCrew((c) =>
      c.state === "ready" && c.value
        ? { state: "ready", value: { ...c.value, top: requestDropped(c.value.top, s.ideaId) } }
        : c,
    );
  };
  const teamUp = useTeamUpSheet({
    doneLabel: "Done",
    onSent: onTeamUpSent,
    onWithdrawn: onTeamUpWithdrawn,
  });
  // Each read of Needs you gets a number, and an older read never overwrites a newer one that is shown.
  const needsRead = useRef(0);
  const needsShown = useRef(0);

  useEffect(() => {
    let gone = false;
    const n = ++needsRead.current;
    void loadMine(f).then(async (m) => {
      if (gone || n < needsShown.current) return;
      needsShown.current = n;
      setMine({ state: "ready", value: m });
      const found = m && !firstVisit ? await loadSets(f, m.needs.rows) : [];
      if (!gone && n >= needsShown.current) setSets({ state: "ready", value: found });
    });
    if (!firstVisit)
      void loadCrew(f).then((c) => {
        if (!gone) setCrew({ state: "ready", value: c });
      });
    void loadOnes(f).then((o) => {
      if (!gone) setOnes({ state: "ready", value: o });
    });
    return () => {
      gone = true;
    };
  }, [f, firstVisit]);

  // Needs you again (S-03.sections/1, L-INBOX.rules/3): when the Inbox sends its counts (an item was answered,
  // opened or archived) and when the browser brings Home back from its back/forward cache, Home reads the same
  // `GET /api/me/ideas` and question sets it read on load. Only that part changes: the box, focus and scroll stay
  // as they are, and nothing goes back to loading. A read that fails keeps what is shown: a failed `/api/me/ideas`
  // keeps the section, and a question set that could not be read keeps that idea's card (all failing, every card).
  // One read at a time: events while one runs, or within REREAD_GAP_MS of its start, bring at most one more.
  useEffect(() => {
    if (firstVisit) return; // a first visit shows no Needs you
    let gone = false;
    const again = async () => {
      const n = ++needsRead.current;
      const m = await loadMine(f);
      if (gone || !m || n < needsShown.current) return;
      const reads = await readSets(f, m.needs.rows);
      if (gone || n < needsShown.current) return;
      needsShown.current = n;
      setMine({ state: "ready", value: m });
      setSets((prev) => {
        if (prev.state !== "ready") return { state: "ready", value: keepFailedSets([], reads) ?? [] };
        const kept = keepFailedSets(prev.value, reads);
        return kept === null ? prev : { state: "ready", value: kept };
      });
    };
    let busy = false;
    let more = false;
    let gap: ReturnType<typeof setTimeout> | undefined;
    const run = () => {
      busy = true;
      const started = Date.now();
      void again().finally(() => {
        gap = setTimeout(
          () => {
            busy = false;
            if (more && !gone) {
              more = false;
              run();
            }
          },
          Math.max(0, REREAD_GAP_MS - (Date.now() - started)),
        );
      });
    };
    const reread = () => {
      if (busy) more = true;
      else run();
    };
    const onShow = (e: PageTransitionEvent) => {
      if (e.persisted) reread();
    };
    window.addEventListener(COUNTS_EVENT, reread);
    window.addEventListener("pageshow", onShow);
    return () => {
      gone = true;
      clearTimeout(gap);
      window.removeEventListener(COUNTS_EVENT, reread);
      window.removeEventListener("pageshow", onShow);
    };
  }, [f, firstVisit]);

  const onCheer = async (post: HomePost) => {
    const liked = !post.liked;
    const swap = (likes: number) =>
      setOnes((o) =>
        o.state === "ready" && o.value
          ? { state: "ready", value: o.value.map((p) => (p.id === post.id ? { ...p, liked, likes } : p)) }
          : o,
      );
    swap(Math.max(0, post.likes + (liked ? 1 : -1)));
    const count = await cheer(f, post.id, liked);
    if (count !== null) swap(count);
  };

  // A failed read of the person's ideas is not an empty one: its sections show no state at all, never "No ideas yet"
  // or "Nothing needs you right now." (those are for a successful read that found nothing).
  const mineFailed = mine.state === "ready" && mine.value === null;
  const ideas = mine.state === "ready" ? (mine.value?.ideas ?? null) : null;
  const needs = mine.state === "ready" ? (mine.value?.needs ?? null) : null;
  const draftCount = mine.state === "ready" ? (mine.value?.drafts ?? 0) : 0;
  // A failed crew read is not an empty one: the section shows no state, never "No one close to yours yet".
  const crewFailed = crew.state === "ready" && crew.value === null;
  const crewData = crew.state === "ready" ? crew.value : null;
  // Faces only for people not shown as "A colleague" (DEC-104), who have no initials to draw.
  const crewFaces = (crewData?.top[0] ? [crewData.top[0].lead, ...crewData.top[0].crew_faces] : [])
    .filter((p, i, all) => !shownAsColleague(p) && all.findIndex((q) => q.id === p.id) === i)
    .slice(0, 3)
    .map((p) => p.initials);
  const openSets = sets.state === "ready" ? sets.value : null;
  // When something needs the person but no card can be drawn (no open set, or a build team's ask), Needs you shows
  // the Inbox link alone, never "Nothing needs you right now." beside it.
  const needTotal = needs ? Math.max(needs.total, openSets?.length ?? 0) : 0;

  const heading = firstVisit ? HOME_COPY.questionFirst(firstName) : HOME_COPY.question(firstName);
  const headingPhone = firstVisit ? HOME_COPY.questionPhoneFirst : HOME_COPY.questionPhone;

  return (
    <div className="hm">
      {/* ── the hero: one calm screen (S-03.rules/3) ── */}
      <section className="hm-hero" aria-labelledby="hm-q">
        <div className="hm-hero-in cz">
          <h1 id="hm-q" className="hm-hello">
            <Words desk={heading} phone={headingPhone} />
          </h1>
          <Prompt
            ref={boxRef}
            value={box}
            onChange={(v) => {
              setBox(v);
              if (problem) setProblem(null);
              createKey.current = "";
              messageKey.current = "";
            }}
            onSend={() => void send()}
            sendLabel={HOME_COPY.send}
            sendHref={HOME_LINKS.share}
            label={HOME_COPY.label}
            placeholder={HOME_COPY.placeholder}
            keyHint
            device="desktop"
            sending={sending}
            className="hm-prompt"
            attach={files.button}
            files={files.rows}
            picker={files.picker}
            voice={{
              state: voice.state,
              // No new note while one goes in or the words are sending (BLD-C220 review fix); called in the click.
              start: () => {
                if (!sending && !taking.current) void voice.start();
              },
              stop: voice.stop,
              noticeShown: voice.noticeShown,
            }}
            micFirst
          >
            {problem ? <FieldMsg kind={problem.kind}>{problem.text}</FieldMsg> : null}
            {/* Share's voice notices (C-PROMPT.voice): both regions stay mounted, so a notice that appears in them is
                announced (WCAG 4.1.3). */}
            <div className="vlive" role="status">
              {voice.state.status === "paused" ? <p className="vnotice">{voice.state.banner}</p> : null}
            </div>
            <div className="vlive" role="alert">
              {failedVoice === "paused" ? (
                <p className="vnotice">{COMPOSE_COPY.voicePaused}</p>
              ) : failedVoice === "sign_in" ? (
                <p className="vnotice">
                  <a href={HOME_SIGN_IN}>{COMPOSE_COPY.signInAgain}</a>
                </p>
              ) : null}
            </div>
          </Prompt>
          <p className="hm-pnote">{HOME_COPY.help}</p>
          <div className="hstarters hm-starters" role="group" aria-label={PROMPT_COPY.startersLabel}>
            {STARTERS.map((s) => (
              <button key={s.label} type="button" className="hstarter" onClick={() => pick(s.opener)}>
                {s.icon}
                <span>{s.label}</span>
              </button>
            ))}
            <button
              type="button"
              className="hstarter hm-ph-flex"
              onClick={() => pick(HOME_COPY.phoneStarter.opener)}
            >
              <IconClock />
              <span>{HOME_COPY.phoneStarter.label}</span>
            </button>
          </div>
        </div>

        <nav className="hm-jump" aria-labelledby="hm-jump-h">
          <div className="hm-jump-h">
            <h2 id="hm-jump-h" className="hm-jl">
              {firstVisit ? HOME_COPY.start : HOME_COPY.jump}
            </h2>
            <Link href={firstVisit ? HOME_LINKS.wall : HOME_LINKS.myIdeas} className="hm-jall hm-dt">
              {firstVisit ? HOME_COPY.seeWall : HOME_COPY.allMine}
            </Link>
          </div>
          <div className="hm-jcards">
            {firstVisit ? (
              <>
                <JumpCard href={HOME_LINKS.how} title={HOME_COPY.whatNext} count={HOME_COPY.stages.length} />
                <JumpCard href={HOME_LINKS.wall} title={HOME_COPY.theWall} />
                <JumpCard href={HOME_LINKS.ways} title={HOME_COPY.shareAnother} count={WAYS_COUNT} />
              </>
            ) : (
              <>
                {draftCount > 0 ? (
                  <span className="hm-ph-contents">
                    <JumpCard href={HOME_LINKS.drafts} title={HOME_COPY.drafts} count={draftCount} />
                  </span>
                ) : null}
                <JumpCard
                  href={HOME_LINKS.myIdeas}
                  title={HOME_COPY.yourIdeas}
                  count={ideas?.total ?? undefined}
                />
                <JumpCard
                  href={HOME_LINKS.crew}
                  title={HOME_COPY.findCrew}
                  count={crewData?.total ?? undefined}
                  faces={crewFaces}
                />
                <span className="hm-dt-contents">
                  <JumpCard href={HOME_LINKS.ways} title={HOME_COPY.shareAnother} count={WAYS_COUNT} />
                </span>
                <span className="hm-ph-contents">
                  <JumpCard href="#hm-ways" title={HOME_COPY.otherWays} count={WAYS_COUNT} />
                </span>
              </>
            )}
          </div>
        </nav>
      </section>

      {firstVisit ? (
        <section className="hm-sec" id="hm-how" aria-labelledby="hm-how-h">
          <h2 id="hm-how-h" className="h2">
            {HOME_COPY.how}
          </h2>
          <ol className="hm-how">
            {HOME_COPY.stages.map((s) => (
              <li key={s.n}>
                <p className="h3">{s.n}</p>
                <p className="meta">{s.w}</p>
              </li>
            ))}
          </ol>
        </section>
      ) : (
        <>
          {/* ── 1. Needs you ── */}
          <section className="hm-sec" id="hm-need" aria-labelledby="hm-need-h">
            <SectionHead
              id="hm-need-h"
              title={HOME_COPY.needs}
              link={{
                href: HOME_LINKS.inbox,
                label: needTotal > 1 ? HOME_COPY.needsAll(needTotal) : HOME_COPY.openInbox,
              }}
            />
            {mineFailed ? null : openSets === null || needs === null ? (
              <SkeletonRows what={HOME_COPY.loadingNeeds} rows={2} />
            ) : openSets.length ? (
              <ul className={`hm-needs${openSets.length === 1 ? " one" : ""}`}>
                {openSets.map(({ ideaId, set }) => (
                  <li key={set.id}>
                    <QuestionsCard ideaId={ideaId} set={set} variant="home" />
                  </li>
                ))}
              </ul>
            ) : needTotal > 0 ? null : (
              <div className="card hm-nclear" role="status">
                <span className="hm-nclear-i" aria-hidden="true">
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    focusable="false"
                  >
                    <path d="M5 12.5 10 17l9-10" />
                  </svg>
                </span>
                <p>
                  <b>{HOME_COPY.needsNone}</b>{" "}
                  <Words desk={HOME_COPY.needsNoneMore} phone={HOME_COPY.needsNonePhone} />
                </p>
              </div>
            )}
          </section>

          <div className="hm-grid">
            {/* ── 2. Your ideas ── */}
            <section id="hm-mine" aria-labelledby="hm-mine-h">
              <SectionHead
                id="hm-mine-h"
                title={HOME_COPY.yourIdeas}
                link={{ href: HOME_LINKS.myIdeas, label: HOME_COPY.allMine }}
              />
              {mineFailed ? null : ideas === null ? (
                <SkeletonRows what={HOME_COPY.loadingIdeas} rows={3} />
              ) : ideas.top.length ? (
                <>
                  <ul className="hm-list">
                    {ideas.top.map((row) => (
                      <IdeaRow key={row.id} row={row} />
                    ))}
                  </ul>
                  {ideas.top.length === 1 ? <p className="hm-ione meta">{HOME_COPY.ideasOne}</p> : null}
                </>
              ) : (
                <div className="card hm-iempty">
                  <h3 className="h3">{HOME_COPY.ideasNoneTitle}</h3>
                  <p className="body">
                    <Words desk={HOME_COPY.ideasNone} phone={HOME_COPY.ideasNonePhone} />
                  </p>
                  <div className="hm-acts">
                    <ButtonLink href={HOME_LINKS.share} variant="line" size="sm">
                      {HOME_COPY.ideasNoneAction}
                    </ButtonLink>
                  </div>
                </div>
              )}
            </section>

            {/* ── 3. Find your crew ── */}
            <section id="hm-crew" aria-labelledby="hm-crew-h">
              <SectionHead
                id="hm-crew-h"
                title={HOME_COPY.findCrew}
                link={{ href: HOME_LINKS.crew, label: HOME_COPY.seeAll }}
              />
              {crewFailed ? null : crewData === null ? (
                <SkeletonRows what={HOME_COPY.loadingCrew} rows={3} />
              ) : crewData.top.length ? (
                <div className="hm-crewbox">
                  <Deck
                    label={HOME_COPY.crewLabel}
                    index={crewAt}
                    onIndexChange={setCrewAt}
                    cards={crewData.top.map((c) => (
                      <CrewCardView
                        key={c.id}
                        card={c}
                        onTeamUp={teamUp.open}
                        onWithdrawn={onTeamUpWithdrawn}
                      />
                    ))}
                  />
                </div>
              ) : (
                <div className="card hm-cnone" role="status">
                  <h3 className="h3">{HOME_COPY.crewNoneTitle}</h3>
                  <p className="body">{HOME_COPY.crewNone}</p>
                  <div className="hm-acts">
                    <ButtonLink href={HOME_LINKS.wall} variant="line" size="sm">
                      {HOME_COPY.browseWall}
                    </ButtonLink>
                  </div>
                </div>
              )}
            </section>
          </div>
        </>
      )}

      {/* ── 4. Or share from where you already are ── */}
      <section className="hm-sec" id="hm-ways" aria-labelledby="hm-ways-h">
        <h2 id="hm-ways-h" className="h2">
          <Words desk={HOME_COPY.ways} phone={HOME_COPY.waysPhone} />
        </h2>
        <p className="meta hm-ways-intro">{HOME_COPY.waysIntro}</p>
        <ul className="hm-ways">
          {/* A way that is off reads as S-H3 draws it (BLD-A192, BLD-C183): its heading with "Coming soon" and its
              line, no link and no address, like the app's tile beside it. */}
          <li className="card hm-way" data-way="email">
            <span className="hm-way-ic">
              <WayIcon kind="mail" />
            </span>
            {waysOn.email ? (
              <>
                <h3 className="h3">
                  <Link href={HOME_LINKS.ways}>{HOME_COPY.outlook}</Link>
                </h3>
                {outlookAddress ? <p className="hm-addr">{outlookAddress}</p> : null}
              </>
            ) : (
              <h3 className="h3">
                {HOME_COPY.outlook} <Pill variant="soon">{HOME_COPY.soon}</Pill>
              </h3>
            )}
            <p className="meta">{HOME_COPY.outlookBody}</p>
          </li>
          <li className="card hm-way" data-way="teams">
            <span className="hm-way-ic">
              <WayIcon kind="chat" />
            </span>
            {waysOn.teams ? (
              <>
                <h3 className="h3">
                  <Link href={HOME_LINKS.ways}>{HOME_COPY.teams}</Link>
                </h3>
                <p className="hm-addr">{HOME_COPY.teamsAddr}</p>
              </>
            ) : (
              <h3 className="h3">
                {HOME_COPY.teams} <Pill variant="soon">{HOME_COPY.soon}</Pill>
              </h3>
            )}
            <p className="meta">{HOME_COPY.teamsBody}</p>
          </li>
          <li className="card hm-way">
            <span className="hm-way-ic">
              <WayIcon kind="app" />
            </span>
            <h3 className="h3">
              {HOME_COPY.app} <Pill variant="soon">{HOME_COPY.soon}</Pill>
            </h3>
            <p className="hm-addr">{HOME_COPY.appAddr}</p>
            <p className="meta">{HOME_COPY.appBody}</p>
          </li>
        </ul>
      </section>

      {/* ── 5. The Ones ── */}
      {ones.state === "ready" && ones.value === null ? null : (
        <section className="hm-slab" id="hm-ones" aria-labelledby="hm-ones-h">
          <div className="hm-o-head">
            <h2 id="hm-ones-h" className="h2 hm-o-title">
              {HOME_COPY.ones}
              <span>{HOME_COPY.onesSub}</span>
            </h2>
            <Link href={HOME_LINKS.wall} className="hm-more">
              {HOME_COPY.seeWall}
            </Link>
          </div>
          {ones.state === "loading" ? (
            <SkeletonRows what={HOME_COPY.loadingOnes} rows={2} />
          ) : (
            <OnesFan
              label={HOME_COPY.ones}
              empty={
                <div className="hm-o-empty">
                  <p className="hm-o-et">{HOME_COPY.onesNoneTitle}</p>
                  <p className="hm-o-ep">{HOME_COPY.onesNone}</p>
                </div>
              }
              companion={
                <OnesNext
                  title={HOME_COPY.nextOne}
                  body={HOME_COPY.nextOneBody}
                  action={HOME_COPY.share}
                  href={HOME_LINKS.share}
                />
              }
              people={new Set((ones.value ?? []).map((p) => p.one.number)).size}
              cards={(ones.value ?? []).map((p) => (
                <OnesPost
                  key={p.id}
                  name={p.one.person?.name ?? null}
                  initials={p.one.person?.initials ?? ""}
                  number={p.one.number}
                  tier={p.one.tier}
                  tierName={p.one.tier_name}
                  ago={p.ago}
                  sentence={p.text}
                  adopted={
                    p.adopted_by
                      ? `Adopted by ${p.adopted_by} team${p.adopted_by === 1 ? "" : "s"}`
                      : undefined
                  }
                  figure={p.figure.value}
                  unit={p.figure.line}
                  cheers={p.likes}
                  cheered={Boolean(p.liked)}
                  onCheer={() => void onCheer(p)}
                  replies={p.comments}
                  threadHref={p.thread_to}
                />
              ))}
            />
          )}
        </section>
      )}
      {teamUp.sheet}
    </div>
  );
}
