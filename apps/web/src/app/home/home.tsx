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
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import { CrewCardView } from "@/components/home/crew-shim";
// Lane B's C-QCARD until it is on main; then this one line becomes "@/components/review/qcard" (BLD-C145).
import { QuestionsCard } from "@/components/home/qcard-shim";
import { Prompt, PROMPT_COPY, STARTERS } from "@/components/compose/prompt";
// Lane F's sheet until team-up is on main; then this one line becomes "@/components/teamup/teamup-sheet" (BLD-C129).
import { useTeamUpSheet } from "@/components/compose/teamup-shim";
import { ButtonLink } from "@/components/ui/button";
import { Deck } from "@/components/ui/deck";
import { FieldMsg } from "@/components/ui/field";
import { OnesFan, OnesPost } from "@/components/ui/ones-fan";
import { Pill, type PillVariant } from "@/components/ui/pill";
import { SkeletonRows } from "@/components/ui/skeleton";
import { DraftClient, DraftError, newClientId } from "@/lib/compose/client";
import type { CrewCard, MyIdeaRow } from "@/lib/contracts";
import {
  cheer,
  loadCrew,
  loadMine,
  loadOnes,
  loadSets,
  type FetchLike,
  type HomeMine,
  type HomePost,
  type OpenSet,
} from "@/lib/home/data";

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
  failed: "Something went wrong. Please try again.",
  /** C-SKELETON/7's polite line; not drawn on the boards (listed for HR). */
  loadingNeeds: "Loading what needs you",
  loadingIdeas: "Loading your ideas",
  loadingCrew: "Loading ideas close to yours",
  loadingOnes: "Loading the Ones",
} as const;

const MAX_MESSAGE = 5000; // V-FIELDS.tellit/2

const WAYS_COUNT = 3;

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
  fetchImpl,
}: {
  firstName: string;
  firstVisit?: boolean;
  /** The 1% Club mailbox, when IT has given it (L-DRAFT.channels); otherwise the tile says only how. */
  outlookAddress?: string | null;
  /** Tests pass a fake; the screen uses the browser's. */
  fetchImpl?: FetchLike;
}) {
  const router = useRouter();
  const f = useMemo<FetchLike>(() => fetchImpl ?? ((input, init) => fetch(input, init)), [fetchImpl]);
  const client = useMemo(() => new DraftClient({ fetch: f as typeof fetch }), [f]);

  // ── the box ─────────────────────────────────────────────────────────────────────────────────────────────────
  const [box, setBox] = useState("");
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<{ text: string; kind: "error" | "warn" } | null>(null);
  const createKey = useRef<string>("");
  const boxRef = useRef<HTMLTextAreaElement>(null);

  const send = useCallback(async () => {
    const text = box.trim();
    if (!text || sending) return;
    if (text.length > MAX_MESSAGE) {
      setProblem({ text: HOME_COPY.tooLong, kind: "error" });
      return;
    }
    setProblem(null);
    setSending(true);
    if (!createKey.current) createKey.current = newClientId(); // one draft per send, however often it is retried
    try {
      const made = await client.create(createKey.current, box);
      router.push(`/share/${made.draft.id}`);
    } catch (err) {
      setSending(false);
      if (err instanceof DraftError && err.offline) setProblem({ text: HOME_COPY.offline, kind: "warn" });
      else setProblem({ text: (err instanceof DraftError && err.text) || HOME_COPY.failed, kind: "error" });
    }
  }, [box, sending, client, router]);

  const pick = (opener: string) => {
    setBox(opener);
    setProblem(null);
    createKey.current = "";
    requestAnimationFrame(() => {
      const el = boxRef.current;
      if (!el) return;
      el.focus();
      el.setSelectionRange(opener.length, opener.length);
    });
  };

  // ── the sections ──────────────────────────────────────────────────────────────────────────────────────────────
  const [mine, setMine] = useState<Loaded<HomeMine | null>>({ state: "loading" });
  const [sets, setSets] = useState<Loaded<{ ideaId: string; set: OpenSet }[]>>({ state: "loading" });
  const [crew, setCrew] = useState<Loaded<{ total: number; top: CrewCard[] } | null>>({ state: "loading" });
  const [ones, setOnes] = useState<Loaded<HomePost[] | null>>({ state: "loading" });
  const [crewAt, setCrewAt] = useState(0);
  const teamUp = useTeamUpSheet({ doneLabel: "Done" });

  useEffect(() => {
    let gone = false;
    void loadMine(f).then(async (m) => {
      if (gone) return;
      setMine({ state: "ready", value: m });
      const found = m && !firstVisit ? await loadSets(f, m.needs.rows) : [];
      if (!gone) setSets({ state: "ready", value: found });
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

  const ideas = mine.state === "ready" ? (mine.value?.ideas ?? { total: 0, top: [] }) : null;
  const needs = mine.state === "ready" ? (mine.value?.needs ?? { total: 0, rows: [] }) : null;
  const draftCount = mine.state === "ready" ? (mine.value?.drafts ?? 0) : 0;
  const crewData = crew.state === "ready" ? (crew.value ?? { total: 0, top: [] }) : null;
  const crewFaces = (crewData?.top[0] ? [crewData.top[0].lead, ...crewData.top[0].crew_faces] : [])
    .filter((p, i, all) => all.findIndex((q) => q.id === p.id) === i)
    .slice(0, 3)
    .map((p) => p.initials);
  const openSets = sets.state === "ready" ? sets.value : null;
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
          >
            {problem ? <FieldMsg kind={problem.kind}>{problem.text}</FieldMsg> : null}
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
            {openSets === null ? (
              <SkeletonRows what={HOME_COPY.loadingNeeds} rows={2} />
            ) : openSets.length ? (
              <ul className={`hm-needs${openSets.length === 1 ? " one" : ""}`}>
                {openSets.map(({ ideaId, set }) => (
                  <li key={set.id}>
                    <QuestionsCard ideaId={ideaId} set={set} variant="home" />
                  </li>
                ))}
              </ul>
            ) : (
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
              {ideas === null ? (
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
              {crewData === null ? (
                <SkeletonRows what={HOME_COPY.loadingCrew} rows={3} />
              ) : crewData.top.length ? (
                <div className="hm-crewbox">
                  <Deck
                    label={HOME_COPY.crewLabel}
                    index={crewAt}
                    onIndexChange={setCrewAt}
                    cards={crewData.top.map((c) => (
                      <CrewCardView key={c.id} card={c} onTeamUp={teamUp.open} />
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
          <li className="card hm-way">
            <span className="hm-way-ic">
              <WayIcon kind="mail" />
            </span>
            <h3 className="h3">
              <Link href={HOME_LINKS.ways}>{HOME_COPY.outlook}</Link>
            </h3>
            {outlookAddress ? <p className="hm-addr">{outlookAddress}</p> : null}
            <p className="meta">{HOME_COPY.outlookBody}</p>
          </li>
          <li className="card hm-way">
            <span className="hm-way-ic">
              <WayIcon kind="chat" />
            </span>
            <h3 className="h3">
              <Link href={HOME_LINKS.ways}>{HOME_COPY.teams}</Link>
            </h3>
            <p className="hm-addr">{HOME_COPY.teamsAddr}</p>
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
                <article className="opost hm-o-next" data-tier="0">
                  <p className="hm-o-nt">{HOME_COPY.nextOne}</p>
                  <p className="hm-o-np">{HOME_COPY.nextOneBody}</p>
                  <Link href={HOME_LINKS.share} className="hm-o-more">
                    {HOME_COPY.share}
                  </Link>
                </article>
              }
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
