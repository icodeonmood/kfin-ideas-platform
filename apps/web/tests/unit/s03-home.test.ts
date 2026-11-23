// @vitest-environment jsdom
/**
 * S-03 Home against a mocked A-API (BLD-C143 to C147). J-SHARE/v1 as far as the browser goes: the question, the box
 * named "Say it in your own words", "Continue to Share a problem" once there are words, and sending makes the draft
 * with the words (POST /api/drafts, one Idempotency-Key) and opens S-04B on it, never the empty S-04. J-TRACK/2: Needs
 * you carries the desk's questions with the clock and "Answer the questions" into S-R3. J-RESUME/2: the side bar's
 * Drafts read "Friday, on your phone" and open S-04B. The None, One and Several states of each section, with the
 * boards' words (reference/copy/Home.md). C-PROMPT.voice on Home (WF-02, BLD-C220): the round voice button in the
 * empty box, on Share's capture (mocked, as s04-review-fixes.test.ts does). Synthetic words only.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  CrewCard,
  CrewDeckResponse,
  DraftListItem,
  MyIdeaRow,
  SharerQuestionSetResponse,
} from "@/lib/contracts";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: push, refresh: vi.fn() }) }));
// The request the server sees, for the shell's device (BLD-C147): headers and cookies set per test.
const request = { headers: new Headers(), cookies: new Map<string, string>() };
vi.mock("next/headers", () => ({
  headers: async () => request.headers,
  cookies: async () => ({
    get: (name: string) =>
      request.cookies.has(name) ? { name, value: request.cookies.get(name)! } : undefined,
  }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
    createElement("a", { href, ...rest }, children as never),
}));
// Share's capture (`useVoiceCapture`), as s04-review-fixes.test.ts mocks it, with a small store so a test can move it
// to recording, done, failed or blocked and Home draws the new state. `start` asks for the draft inside the tap, as
// the real capture does (`resolveDraft`, BLD-C127).
const voice = vi.hoisted(() => {
  const subs = new Set<() => void>();
  const v = {
    state: { status: "idle", notice: null } as unknown,
    options: null as { fetch?: unknown; resolveDraft?: () => Promise<string | null> } | null,
    set(next: unknown) {
      v.state = next;
      for (const f of subs) f();
    },
    subscribe(f: () => void) {
      subs.add(f);
      return () => void subs.delete(f);
    },
    start: vi.fn(async () => {
      await v.options?.resolveDraft?.();
    }),
    stop: vi.fn(),
    reset: vi.fn(() => v.set({ status: "idle", notice: null })),
    noticeShown: vi.fn(),
  };
  return v;
});
vi.mock("@/lib/use-voice-capture", async () => {
  const { useSyncExternalStore } = await import("react");
  return {
    useVoiceCapture: (_draftId: string, options?: typeof voice.options) => {
      voice.options = options ?? null;
      const state = useSyncExternalStore(
        voice.subscribe,
        () => voice.state,
        () => voice.state,
      );
      return {
        state,
        start: voice.start,
        stop: voice.stop,
        reset: voice.reset,
        noticeShown: voice.noticeShown,
      };
    },
  };
});

const { HomeScreen, HOME_COPY } = await import("@/app/home/home");
const { keepFailedSets, loadCrew, loadMine, loadOnes, loadSets, readSets } = await import("@/lib/home/data");
const { askingDevice, draftRows } = await import("@/server/shell");
const { DEVICE_COOKIE } = await import("@/lib/compose/client");
const { MIC_BLOCKED } = await import("@/lib/voice-capture");
const { BANNERS } = await import("@/lib/killswitch-routes");

const NEW_DRAFT = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d";
const WORDS =
  "Branch staff retype the same nominee details into two screens for every new folio. It takes ten minutes each time.";

function row(over: Partial<MyIdeaRow> & { id: string; title: string }): MyIdeaRow {
  return {
    ref: over.id,
    list: "yours",
    href: `/ideas/${over.id}`,
    meta: `${over.id}, Shared Saturday 14 November`,
    pill: { status: "with_review_desk", label: "With the review desk", variant: "blue" },
    track: null,
    next_step: { sentence: "", action: { label: "See it", style: "line", accessible_name: "See it" } },
    group: "with_review_desk",
    activity_at: "2026-11-14T06:00:00.000Z",
    ...over,
  } as MyIdeaRow;
}

const NEEDS = row({
  id: "IDEA-2026-001481",
  title: "Synthetic: investors call to ask why a redemption was not processed",
  pill: { status: "needs_you", label: "Needs you", variant: "warn" },
  group: "needs_you",
});
const PICKED = row({
  id: "IDEA-2026-001471",
  title: "Synthetic: plain words for transaction messages",
  pill: { status: "picked", label: "Picked", variant: "blue" },
  group: "picked_and_building",
});
const BUILT = row({
  id: "IDEA-2026-001468",
  title: "Synthetic: track couriered redemption forms",
  pill: { status: "being_built", label: "Being built", variant: "blue" },
  group: "picked_and_building",
});
const DRAFT_ROW = row({ id: NEW_DRAFT, title: "Synthetic draft", group: "drafts", ref: null });

function mine(items: MyIdeaRow[], counts: Partial<Record<string, number>> = {}) {
  const shared = items.filter((r) => r.group !== "drafts");
  return {
    items,
    total: items.length,
    counts: {
      all: items.length,
      drafts: items.length - shared.length,
      needs_you: shared.filter((r) => r.group === "needs_you").length,
      ...counts,
    },
  };
}

const SET: NonNullable<SharerQuestionSetResponse> = {
  id: "qs-1",
  idea_id: NEEDS.id,
  by: { id: "u-9", name: "Harish Rao", first_name: "Harish", initials: "HR", city: null, area: null },
  state: "seen",
  time_to_answer: null,
  sent_at: "2026-11-16T05:00:00.000Z",
  seen_at: null,
  due_at: new Date(Date.now() + 3 * 86_400_000 + 3_600_000).toISOString(),
  answered_at: null,
  extended_times: 0,
  reminded_at: null,
  count: 2,
  answered: 0,
  overdue: false,
  questions: [
    {
      id: "q-1",
      seq: 1,
      part: "often",
      part_name: "How often",
      text: "Is it at one branch, or across Hyderabad?",
      suggested: false,
      answer: null,
    },
    {
      id: "q-2",
      seq: 2,
      part: "evidence",
      part_name: "Proof",
      text: "Can you add a screenshot of the message, with the folio hidden?",
      suggested: false,
      answer: null,
    },
  ],
  idea: { id: NEEDS.id, title: NEEDS.title },
  countdown: { seconds: 0, count: "3 days", variant: "normal" },
  deadline: "Answer by Thursday 19 November, 6 pm",
  progress: "0 of 2 answered",
  send_label: "Answer at least one question",
} as unknown as NonNullable<SharerQuestionSetResponse>;

function person(id: string, name: string, initials: string) {
  return { id, name, first_name: name.split(" ")[0]!, initials };
}

const CREW: CrewCard = {
  id: "IDEA-2026-001490",
  title: "Synthetic: message codes confuse investors",
  status: "with_review_desk",
  area: "Investor service",
  city: "Hyderabad",
  shared_at: "2026-11-14T06:00:00.000Z",
  lead: person("p-1", "Ravi Nair", "RN"),
  crew_faces: [person("p-2", "Asha Shetty", "AS"), person("p-3", "Pooja Kumar", "PK")],
  crew_count: 4,
  in_their_words: "Investors get a code, not a reason, and then they call us.",
  hue: 1,
  reason_kind: "close_to_yours",
  reason: "Same code as your idea from Saturday",
} as CrewCard;

/** Lane F's `GET /api/crew?limit=3` answer as the worker sends it (`crew/deck.py`), with only `cards` in `items`. */
function crewDeck(cards: CrewCard[], total = cards.length): CrewDeckResponse {
  return {
    items: cards,
    total,
    counts: { "location:Hyderabad": total },
    filters: [],
    active: [],
    deck_total: total,
    state: total ? "cards" : "nothing_yet",
    asked: 0,
    last_passed: null,
    joined: 0,
    pending: 0,
    passed: 0,
  };
}

type Answer = { status: number; body?: unknown };
type Routes = Record<string, (init?: RequestInit) => Answer | Promise<Answer>>;

function fakeFetch(routes: Routes) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const f = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    const hit = Object.entries(routes).find(
      ([k]) => url === k || url.startsWith(`${k}?`) || url.startsWith(k),
    );
    const out = hit ? await hit[1](init) : { status: 404, body: { error: "not_found" } };
    return new Response(out.body === undefined ? null : JSON.stringify(out.body), {
      status: out.status,
      headers: { "Content-Type": "application/json" },
    });
  });
  return { f, calls };
}

const baseRoutes = (over: Routes = {}): Routes => ({
  "/api/me/ideas": () => ({ status: 200, body: mine([NEEDS, PICKED, BUILT, DRAFT_ROW]) }),
  [`/api/ideas/${NEEDS.id}/question-set`]: () => ({ status: 200, body: SET }),
  "/api/crew": () => ({ status: 200, body: crewDeck([CREW]) }),
  "/api/ones/posts": () => ({ status: 200, body: [] }),
  ...over,
});

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  push.mockReset();
  voice.state = { status: "idle", notice: null };
  voice.options = null;
  voice.start.mockClear();
  voice.stop.mockClear();
  voice.reset.mockClear();
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

async function flush() {
  for (let i = 0; i < 6; i++) await act(async () => await Promise.resolve());
}

async function show(
  routes: Routes,
  props: {
    firstVisit?: boolean;
    outlookAddress?: string | null;
    waysOn?: { email: boolean; teams: boolean };
  } = {},
) {
  const { f, calls } = fakeFetch(routes);
  await act(async () => {
    root.render(createElement(HomeScreen, { firstName: "Kavya", fetchImpl: f, ...props }));
  });
  await flush();
  return calls;
}

const text = () => host.textContent ?? "";
const link = (name: string) =>
  [...host.querySelectorAll("a")].find(
    (a) => (a.getAttribute("aria-label") ?? a.textContent ?? "").replace(/\s+/g, " ").trim() === name,
  );
const heading = (level: number) => [...host.querySelectorAll(`h${level}`)].map((h) => h.textContent?.trim());

function type(value: string) {
  const ta = host.querySelector("textarea") as HTMLTextAreaElement;
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
  act(() => {
    setter.call(ta, value);
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  });
  return ta;
}

describe("S-03.hero: ask first (BLD-C143, C144)", () => {
  it("S-03.hero/1-2: the returning question as the heading, the box and its help line, three starters", async () => {
    await show(baseRoutes());
    expect(host.querySelector("h1 .hm-dt")?.textContent).toBe("What keeps getting in your way, Kavya?");
    const ta = host.querySelector("textarea")!;
    expect(host.querySelector(`label[for="${ta.id}"]`)?.textContent).toBe("Say it in your own words");
    expect(ta.getAttribute("placeholder")).toBe("Describe what's getting in your way");
    expect(text()).toContain("Say it in whichever language feels most natural to you.");
    for (const s of [
      "A step customers keep calling about",
      "Something we redo by hand every month",
      "A screen that asks for the same thing twice",
      "A wait that makes customers give up",
    ])
      expect(text()).toContain(s);
  });

  it("S-03.hero/1: a first visit asks the first-visit question and shows Start here and the five stages", async () => {
    await show(baseRoutes(), { firstVisit: true });
    expect(host.querySelector("h1 .hm-dt")?.textContent).toBe("What gets in your way at work, Kavya?");
    expect(host.querySelector("h1 .hm-ph")?.textContent).toBe("What gets in your way?");
    expect(heading(2)).toContain("Start here");
    expect(heading(2)).toContain("What happens after you share");
    expect(heading(2)).not.toContain("Needs you");
    expect(link("What happens next5")?.getAttribute("href")).toBe("/how-it-works");
    for (const s of HOME_COPY.stages) expect(text()).toContain(`${s.n}${s.w}`);
  });

  it("C-PROMPT.anatomy/3: a starter puts its opener in the box and does not send", async () => {
    const calls = await show(baseRoutes());
    const starter = [...host.querySelectorAll("button")].find(
      (b) => b.textContent === "A step customers keep calling about",
    )!;
    act(() => starter.click());
    await flush();
    expect((host.querySelector("textarea") as HTMLTextAreaElement).value).toBe(
      "Customers keep calling us about ",
    );
    expect(calls.some((c) => c.init?.method === "POST")).toBe(false);
  });

  it("J-SHARE/v1, V-ACC.share/3: Continue to Share a problem makes the draft with the words and opens S-04B on it", async () => {
    const created: { body: unknown; key: string | null }[] = [];
    await show(
      baseRoutes({
        "/api/drafts": (init) => {
          created.push({
            body: JSON.parse(String(init?.body)),
            key: new Headers(init?.headers).get("Idempotency-Key"),
          });
          return { status: 201, body: { draft: { id: NEW_DRAFT, messages: [] }, run_id: "r-1" } };
        },
      }),
    );
    expect(link("Continue to Share a problem")).toBeUndefined(); // nothing typed: the round button waits
    type(WORDS);
    const go = link("Continue to Share a problem")!;
    expect(go).toBeDefined();
    act(() => go.click());
    await flush();
    expect(created).toHaveLength(1);
    expect(created[0]!.body).toMatchObject({ channel: "web", text: WORDS, via: "typed" });
    expect(created[0]!.key).toBeTruthy();
    expect(push).toHaveBeenCalledWith(`/share/${NEW_DRAFT}`);
    expect(push).not.toHaveBeenCalledWith("/share");
  });

  it("C-PROMPT.keys/1: Enter sends from Home too; Shift and Enter does not", async () => {
    let posts = 0;
    await show(
      baseRoutes({
        "/api/drafts": () => {
          posts += 1;
          return { status: 201, body: { draft: { id: NEW_DRAFT, messages: [] }, run_id: null } };
        },
      }),
    );
    const ta = type(WORDS);
    act(() => {
      ta.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", shiftKey: true, bubbles: true }));
    });
    await flush();
    expect(posts).toBe(0);
    act(() => {
      ta.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });
    await flush();
    expect(posts).toBe(1);
    expect(push).toHaveBeenCalledWith(`/share/${NEW_DRAFT}`);
  });

  it("A refused send keeps the words and says why; offline says so", async () => {
    await show(
      baseRoutes({
        "/api/drafts": () => ({
          status: 403,
          body: { error: { code: "forbidden", message: "Not allowed." } },
        }),
      }),
    );
    type(WORDS);
    act(() => link("Continue to Share a problem")!.click());
    await flush();
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("Not allowed.");
    expect((host.querySelector("textarea") as HTMLTextAreaElement).value).toBe(WORDS);
    expect(push).not.toHaveBeenCalled();
  });
  it("J-SHARE/v1, C-PROMPT: a middle click or Space on the send link sends here, never an empty S-04 in a new tab", async () => {
    const keys: (string | null)[] = [];
    await show(
      baseRoutes({
        "/api/drafts": (init) => {
          keys.push(new Headers(init?.headers).get("Idempotency-Key"));
          return { status: 201, body: { draft: { id: NEW_DRAFT, messages: [] }, run_id: null } };
        },
      }),
    );
    type(WORDS);
    const go = link("Continue to Share a problem")!;
    const middle = new MouseEvent("auxclick", { button: 1, bubbles: true, cancelable: true });
    act(() => void go.dispatchEvent(middle));
    await flush();
    expect(middle.defaultPrevented).toBe(true);
    expect(keys).toHaveLength(1);
    expect(push).toHaveBeenLastCalledWith(`/share/${NEW_DRAFT}`);

    push.mockReset();
    act(() => root.unmount());
    root = createRoot(host);
    await show(
      baseRoutes({
        "/api/drafts": (init) => {
          keys.push(new Headers(init?.headers).get("Idempotency-Key"));
          return { status: 201, body: { draft: { id: NEW_DRAFT, messages: [] }, run_id: null } };
        },
      }),
    );
    type(WORDS);
    const space = new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true });
    act(() => void link("Continue to Share a problem")!.dispatchEvent(space));
    await flush();
    expect(space.defaultPrevented).toBe(true);
    expect(keys).toHaveLength(2);
    expect(push).toHaveBeenCalledWith(`/share/${NEW_DRAFT}`);
  });

  it("A refused send with no words from the server keeps the words, says nothing invented, and frees the box", async () => {
    let posts = 0;
    await show(
      baseRoutes({
        "/api/drafts": () => {
          posts += 1;
          return { status: 400, body: {} }; // a refusal (not retried) that carries no message
        },
      }),
    );
    type(WORDS);
    act(() => link("Continue to Share a problem")!.click());
    await flush();
    expect(posts).toBe(1);
    // No alert says anything (the voice notices' alert region stays mounted, empty, BLD-C220).
    expect([...host.querySelectorAll('[role="alert"]')].map((a) => a.textContent).join("")).toBe("");
    expect(text()).not.toContain("Something went wrong");
    expect((host.querySelector("textarea") as HTMLTextAreaElement).value).toBe(WORDS);
    expect(link("Continue to Share a problem")).toBeDefined(); // not stuck sending
    expect(push).not.toHaveBeenCalled();
  });

  it("J-SHARE/v1: if opening S-04B fails, the box is free again and sending once more opens the same draft", async () => {
    const keys: (string | null)[] = [];
    await show(
      baseRoutes({
        "/api/drafts": (init) => {
          keys.push(new Headers(init?.headers).get("Idempotency-Key"));
          return { status: 201, body: { draft: { id: NEW_DRAFT, messages: [] }, run_id: null } };
        },
      }),
    );
    push.mockImplementationOnce(() => {
      throw new Error("navigation failed");
    });
    type(WORDS);
    act(() => link("Continue to Share a problem")!.click());
    await flush();
    expect(push).toHaveBeenCalledTimes(1);
    const again = link("Continue to Share a problem");
    expect(again).toBeDefined(); // the box is not stuck sending
    act(() => again!.click());
    await flush();
    expect(push).toHaveBeenCalledTimes(2);
    expect(push).toHaveBeenLastCalledWith(`/share/${NEW_DRAFT}`);
    expect(keys).toHaveLength(2);
    expect(keys[1]).toBe(keys[0]); // the same Idempotency-Key, so the same draft
  });
});

describe("S-03.sections (BLD-C143, C145, C146)", () => {
  it("Jump back in: Your ideas, Find your crew and Share another way with their counts and links", async () => {
    await show(baseRoutes());
    expect(heading(2)).toContain("Jump back in");
    expect(link("All my ideas")?.getAttribute("href")).toBe("/my-ideas");
    expect(link("Your ideas3")?.getAttribute("href")).toBe("/my-ideas");
    expect(link("RNASPKFind your crew1")?.getAttribute("href")).toBe("/crew");
    expect(link("Share another way3")?.getAttribute("href")).toBe("/share/other-ways");
  });

  it("J-TRACK/2, V-ACC.track/3: Needs you carries the questions, the clock and Answer the questions into S-R3", async () => {
    await show(baseRoutes());
    expect(heading(2)).toContain("Needs you");
    expect(text()).toContain("2 questions from the review desk");
    expect(text()).toContain(`Asked about "${NEEDS.title}"`); // DEC-111: the title names the desk; never the reviewer
    expect(text()).not.toContain("Harish from the review desk");
    expect(text()).toMatch(/[34] days left/); // calendar days in office time (lib/desk/countdown)
    expect(text()).toContain("Question 1 Is it at one branch, or across Hyderabad?");
    expect(link("Answer the questions")?.getAttribute("href")).toBe(`/ideas/${NEEDS.id}/answer`);
    expect(link("Open the Inbox")?.getAttribute("href")).toBe("/inbox"); // one item: "Open the Inbox"
    expect(host.querySelector("textarea[id] ~ textarea")).toBeNull(); // no free-text answer box on Home
  });

  it("Needs you, several: All N in Inbox", async () => {
    await show(
      baseRoutes({
        "/api/me/ideas": () => ({ status: 200, body: mine([NEEDS, PICKED], { needs_you: 3 }) }),
      }),
    );
    expect(link("All 3 in Inbox")?.getAttribute("href")).toBe("/inbox");
  });

  it("Needs you, none: the status line and Open the Inbox", async () => {
    await show(baseRoutes({ "/api/me/ideas": () => ({ status: 200, body: mine([PICKED]) }) }));
    const status = [...host.querySelectorAll('[role="status"]')].find((s) =>
      s.textContent?.includes("Nothing needs you right now."),
    );
    expect(status?.querySelector(".hm-dt")?.textContent).toBe(
      "When the review desk or a build team asks you something, it shows up here.",
    );
    expect(link("Open the Inbox")?.getAttribute("href")).toBe("/inbox");
  });

  it("Needs you and Your ideas: a failed read shows no state, never Nothing needs you or No ideas yet", async () => {
    await show(
      baseRoutes({ "/api/me/ideas": () => ({ status: 500, body: { error: { code: "worker_error" } } }) }),
    );
    expect(heading(2)).toContain("Needs you");
    expect(heading(2)).toContain("Your ideas");
    expect(text()).not.toContain(HOME_COPY.needsNone);
    expect(text()).not.toContain(HOME_COPY.ideasNoneTitle);
    expect(text()).not.toContain(HOME_COPY.loadingNeeds);
    expect(text()).not.toContain(HOME_COPY.loadingIdeas);
    expect(host.querySelector(".qcard")).toBeNull();
    expect(link("Open the Inbox")?.getAttribute("href")).toBe("/inbox");
    expect(link("Your ideas")?.getAttribute("href")).toBe("/my-ideas"); // the Jump back in card, with no count
    expect(link("Your ideas0")).toBeUndefined();
  });

  it("Needs you: something needs the person but no card can be drawn, so the Inbox link alone", async () => {
    await show(baseRoutes({ [`/api/ideas/${NEEDS.id}/question-set`]: () => ({ status: 200, body: null }) }));
    expect(host.querySelector(".qcard")).toBeNull();
    expect(text()).not.toContain(HOME_COPY.needsNone);
    expect(link("Open the Inbox")?.getAttribute("href")).toBe("/inbox");

    act(() => root.unmount());
    root = createRoot(host);
    await show(
      baseRoutes({
        "/api/me/ideas": () => ({ status: 200, body: mine([NEEDS, PICKED], { needs_you: 3 }) }),
        [`/api/ideas/${NEEDS.id}/question-set`]: () => ({ status: 500 }),
      }),
    );
    expect(text()).not.toContain(HOME_COPY.needsNone);
    expect(link("All 3 in Inbox")?.getAttribute("href")).toBe("/inbox");
  });

  it("Your ideas, several: title, reference line and status pill, never the drafts", async () => {
    await show(baseRoutes());
    const items = [...host.querySelectorAll(".hm-idea")];
    expect(items).toHaveLength(3);
    expect(items[0]!.textContent).toContain(NEEDS.title);
    expect(items[0]!.textContent).toContain("IDEA-2026-001481, Shared Saturday 14 November");
    expect(items[0]!.querySelector(".pill")?.textContent).toBe("Needs you");
    expect(text()).not.toContain("Synthetic draft");
    expect(text()).not.toContain(HOME_COPY.ideasOne);
  });

  it("Your ideas, one: the row and the nudge back to the box", async () => {
    await show(baseRoutes({ "/api/me/ideas": () => ({ status: 200, body: mine([PICKED]) }) }));
    expect(host.querySelectorAll(".hm-idea")).toHaveLength(1);
    expect(text()).toContain("Anything else slowing you or a customer down? Say it in the box at the top.");
    expect(link("Your ideas1")).toBeDefined();
  });

  it("Your ideas, none: No ideas yet and Share your first problem", async () => {
    await show(baseRoutes({ "/api/me/ideas": () => ({ status: 200, body: mine([]) }) }));
    expect(heading(3)).toContain("No ideas yet");
    expect(text()).toContain(
      "Anything that slows you or a customer down counts. Say it in the box at the top, in your own words.",
    );
    expect(link("Share your first problem")?.getAttribute("href")).toBe("/share");
    expect(link("Your ideas0")).toBeDefined();
  });

  it("Find your crew: the card without They're looking for, Team up named for the idea and its lead, See all", async () => {
    await show(baseRoutes());
    expect(link("See all")?.getAttribute("href")).toBe("/crew");
    const card = host.querySelector(".hm-pcard")!;
    // F-TYPE (BLD-D015): the hue is "hue1"/"hue2", as on lane F's card. "h1" is the page-heading style, whose
    // tracking every line on the card inherited, running the words together (lane G's walk, J-ONE/5, J-TRACK/2).
    expect(card.classList.contains("hue1")).toBe(true);
    expect([...card.classList].filter((c) => /^(h[1-3]|d1)$/.test(c))).toEqual([]);
    expect(card.textContent).toContain("With the review desk");
    expect(card.textContent).toContain("Investor service, Hyderabad");
    expect(card.textContent).toContain("Same code as your idea from Saturday");
    expect(card.textContent).toContain("The problem, in their words");
    expect(card.textContent).toContain("Ravi Nair and 3 others on it");
    expect(card.textContent).not.toContain("They're looking for");
    expect(
      card.querySelector(`button[aria-label="Team up on ${CREW.title}, with Ravi Nair"]`)?.textContent,
    ).toContain("Team up");
    expect(text()).toContain("Idea 1 of 1");
  });

  it("Find your crew, none: a read that found no one shows the empty state and Browse the Wall", async () => {
    await show(baseRoutes({ "/api/crew": () => ({ status: 200, body: crewDeck([]) }) }));
    const status = [...host.querySelectorAll('[role="status"]')].find((s) =>
      s.textContent?.includes("No one close to yours yet"),
    );
    expect(status?.textContent).toContain(
      "When someone shares an idea near yours or in your area, it shows up here so you can team up.",
    );
    expect(link("Browse the Wall")?.getAttribute("href")).toBe("/wall");
    expect(link("Find your crew0")?.getAttribute("href")).toBe("/crew");
  });

  it("Find your crew, failed read (BLD-C146): no state at all, never No one close to yours yet; no count on Jump back in", async () => {
    for (const failed of [
      () => ({ status: 500, body: { error: { code: "unavailable", message: "" } } }),
      () => ({ status: 503, body: { error: { code: "paused", message: "" } } }),
      () => ({ status: 200, body: { error: "not a deck" } }),
    ]) {
      act(() => root.unmount());
      root = createRoot(host);
      await show(baseRoutes({ "/api/crew": failed }));
      expect(heading(2)).toContain("Find your crew");
      expect(text()).not.toContain(HOME_COPY.crewNoneTitle);
      expect(text()).not.toContain(HOME_COPY.loadingCrew);
      expect(host.querySelector(".hm-pcard")).toBeNull();
      expect(link("Browse the Wall")).toBeUndefined();
      expect(link("See all")?.getAttribute("href")).toBe("/crew");
      expect(link("Find your crew")?.getAttribute("href")).toBe("/crew"); // the Jump back in card, no count
    }
  });

  it("Find your crew from lane F's deck (DEC-104): only what the card carries; a hidden lead is A colleague with no face", async () => {
    const hidden = { id: "p3f9a1c2b7d40", name: "A colleague", first_name: "A colleague", initials: "" };
    const quiet: CrewCard = {
      ...CREW,
      id: "IDEA-2026-001495",
      title: "Synthetic: nominee change asks for Folio ••••89 twice",
      city: "",
      lead: hidden,
      crew_faces: [hidden, person("p-4", "Meera Iyer", "MI")],
      crew_count: 2,
      in_their_words: "Investors are asked for the same form at two branches.",
      reason: "In Investor service, like yours",
      looking_for: "Branch staff, operations",
    } as CrewCard;
    const calls = await show(
      baseRoutes({ "/api/crew": () => ({ status: 200, body: crewDeck([quiet, CREW], 5) }) }),
    );
    expect(calls.filter((c) => c.url.startsWith("/api/crew")).map((c) => c.url)).toEqual([
      "/api/crew?limit=3",
    ]);
    const card = host.querySelector(".hm-pcard")!;
    expect(card.getAttribute("aria-label")).toBe(quiet.title);
    expect(card.querySelector(".hm-pc-top .meta")?.textContent).toBe("Investor service"); // no empty city
    expect(card.textContent).toContain("In Investor service, like yours");
    expect(card.textContent).toContain("Investors are asked for the same form at two branches.");
    expect(card.textContent).not.toContain("They're looking for");
    expect(card.textContent).not.toContain("Branch staff, operations");
    expect(card.textContent).toContain("A colleague and 1 other on it"); // counted, though not drawn
    // No face for A colleague: an empty circle would still be a tab stop named "A colleague"
    const faces = [...card.querySelectorAll(".crew-face")];
    expect(faces.map((f) => [f.getAttribute("aria-label"), f.textContent])).toEqual([["Meera Iyer", "MI"]]);
    expect(card.querySelectorAll('[tabindex="0"][role="img"]')).toHaveLength(1);
    expect(
      card.querySelector(`button[aria-label="Team up on ${quiet.title}, with a colleague"]`),
    ).not.toBeNull();
    expect(text()).toContain("Idea 1 of 2");
    // Jump back in: the deck's total, and faces only for people with initials (no blank face for A colleague)
    const jump = link("MIFind your crew5");
    expect(jump?.getAttribute("href")).toBe("/crew");
    expect([...jump!.querySelectorAll(".hm-jface")].map((f) => f.textContent)).toEqual(["MI"]);
  });

  it("Or share from where you already are: three tiles, the app Coming soon", async () => {
    await show(baseRoutes(), {
      outlookAddress: "share@1pc.kfintech.example",
      waysOn: { email: true, teams: true },
    });
    expect(text()).toContain("Each one lands here as a draft. Nothing is sent until you check it.");
    expect(text()).toContain("Forward it from Outlook");
    expect(text()).toContain("share@1pc.kfintech.example");
    expect(text()).toContain("Message it in Teams");
    expect(text()).toContain("Type or paste into a chat with 1% Club. Screenshots go straight in.");
    expect(text()).toContain("Use the 1% Club app Coming soon");
    expect(text()).toContain("Share from your phone, typed or spoken, in any language.");
  });

  it("The Ones, none: No Ones yet; See the Wall", async () => {
    await show(baseRoutes());
    expect(text()).toContain("Fixes that shipped, from the people behind them.");
    expect(text()).toContain("No Ones yet");
    expect(text()).toContain(
      "When a shared fix ships and its result is measured, the people behind it are posted here first.",
    );
    expect(link("See the Wall")?.getAttribute("href")).toBe("/wall");
  });

  it("The Ones, one: the post and The next One could be you", async () => {
    const post = {
      id: "post-1",
      one: {
        number: 1,
        person: person("p-7", "Rohit Menon", "RM"),
        tier: 4,
        tier_name: "Blaze",
        flag: "earned",
        brief: "",
      },
      text: "Synthetic: wrong bank details are now caught before the first SIP debit.",
      ago: "2d",
      shipped: true,
      adopted_by: 3,
      figure: { value: "1,240", line: "failed debits avoided last quarter" },
      likes: 214,
      liked: false,
      comments: 18,
      thread_to: "/ideas/IDEA-2026-001400",
    };
    await show(baseRoutes({ "/api/ones/posts": () => ({ status: 200, body: [post] }) }));
    expect(text()).toContain("Rohit Menon");
    expect(text()).toContain("The next One could be you");
    expect(text()).toContain("Every fix here started with one person saying what kept going wrong.");
  });

  it("C-ONES-FAN on Home: the arrows move through the posts and the cheer toggles, saved with the server", async () => {
    const post = (id: string, name: string, initials: string, likes: number) => ({
      id,
      one: {
        number: 3,
        person: person(`p-${id}`, name, initials),
        tier: 2,
        tier_name: "Spark",
        flag: "earned",
        brief: "",
      },
      text: `Synthetic: a fix by ${name}.`,
      ago: "1d",
      shipped: true,
      adopted_by: 0,
      figure: { value: "40", line: "calls avoided last month" },
      likes,
      liked: false,
      comments: 2,
      thread_to: "/ideas/IDEA-2026-001401",
    });
    const likes: { url: string; body: unknown }[] = [];
    await show(
      baseRoutes({
        "/api/ones/posts": (init) => {
          if (init?.method !== "PUT")
            return {
              status: 200,
              body: [post("post-a", "Rekha Saxena", "RS", 12), post("post-b", "Varun Chopra", "VC", 5)],
            };
          const body = JSON.parse(String(init.body)) as { liked: boolean };
          likes.push({ url: "post-a", body });
          return { status: 200, body: { likes: body.liked ? 13 : 12 } };
        },
      }),
    );
    const fan = host.querySelector('[role="region"][aria-label="The Ones"]')!;
    expect(fan).not.toBeNull();
    const pos = () => fan.querySelector(".fan-pos")?.textContent;
    const prev = fan.querySelector('button[aria-label="Previous post"]') as HTMLButtonElement;
    const next = fan.querySelector('button[aria-label="Next post"]') as HTMLButtonElement;
    expect(pos()).toBe("Post 1 of 2");
    expect(prev.getAttribute("aria-disabled")).toBe("true");
    act(() => next.click());
    expect(pos()).toBe("Post 2 of 2");
    expect(next.getAttribute("aria-disabled")).toBe("true");
    act(() => prev.click());
    expect(pos()).toBe("Post 1 of 2");

    const cheer = () =>
      [...fan.querySelectorAll<HTMLButtonElement>("button.opost-cheer")].find((b) =>
        b.textContent?.includes("Rekha Saxena"),
      )!;
    expect(cheer().textContent?.replace(/\s+/g, " ").trim()).toContain("Cheer Rekha Saxena’s fix,");
    expect(cheer().getAttribute("aria-pressed")).toBe("false");
    act(() => cheer().click());
    await flush();
    expect(cheer().getAttribute("aria-pressed")).toBe("true");
    expect(cheer().textContent).toContain("13");
    act(() => cheer().click());
    await flush();
    expect(cheer().getAttribute("aria-pressed")).toBe("false");
    expect(likes.map((l) => l.body)).toEqual([{ liked: true }, { liked: false }]);
  });
});

describe("S-03.sections/4: the ways in follow intake.email and intake.teams (DEC-105, BLD-A192, BLD-C183)", () => {
  const way = (name: "email" | "teams") => host.querySelector(`.hm-way[data-way="${name}"]`) as HTMLElement;
  // The tile's blocks (heading, address, line), one space between them
  const wayText = (name: "email" | "teams") =>
    [...way(name).children]
      .map((c) => c.textContent ?? "")
      .filter(Boolean)
      .join(" ")
      .replace(/\s+/g, " ")
      .trim();
  const wayLinks = (name: "email" | "teams") => [...way(name).querySelectorAll("a, button")];
  const ADDRESS = "share@1pc.kfintech.example";

  it("J-RESUME/2, J-ONE/5: both off, both rows read Coming soon, with no link and no address", async () => {
    await show(baseRoutes(), { outlookAddress: null, waysOn: { email: false, teams: false } });
    expect(wayText("email")).toBe(
      "Forward it from Outlook Coming soon Forward the thread that shows the problem. Your note on top becomes the draft.",
    );
    expect(wayText("teams")).toBe(
      "Message it in Teams Coming soon Type or paste into a chat with 1% Club. Screenshots go straight in.",
    );
    expect(wayLinks("email")).toHaveLength(0);
    expect(wayLinks("teams")).toHaveLength(0);
    expect(link("Forward it from Outlook")).toBeUndefined();
    expect(link("Message it in Teams")).toBeUndefined();
    expect(way("email").querySelector(".hm-addr")).toBeNull();
    expect(way("teams").querySelector(".hm-addr")).toBeNull();
    // The section's heading, intro and the app's tile are as drawn
    expect(text()).toContain("Each one lands here as a draft. Nothing is sent until you check it.");
    expect(text()).toContain("Use the 1% Club app Coming soon");
  });

  it("J-TRACK/2: an unknown switch counts as off (the screen's default is off)", async () => {
    await show(baseRoutes());
    expect(wayText("email")).toContain("Forward it from Outlook Coming soon");
    expect(wayText("teams")).toContain("Message it in Teams Coming soon");
    expect(wayLinks("email")).toHaveLength(0);
    expect(wayLinks("teams")).toHaveLength(0);
  });

  it("both on: unchanged, each heading links to Share another way, with the address and 1% Club", async () => {
    await show(baseRoutes(), { outlookAddress: ADDRESS, waysOn: { email: true, teams: true } });
    expect(link("Forward it from Outlook")?.getAttribute("href")).toBe("/share/other-ways");
    expect(link("Message it in Teams")?.getAttribute("href")).toBe("/share/other-ways");
    expect(wayText("email")).toBe(
      `Forward it from Outlook ${ADDRESS} Forward the thread that shows the problem. Your note on top becomes the draft.`,
    );
    expect(wayText("teams")).toBe(
      "Message it in Teams 1% Club Type or paste into a chat with 1% Club. Screenshots go straight in.",
    );
    expect(way("email").querySelector(".pill")).toBeNull();
    expect(way("teams").querySelector(".pill")).toBeNull();
  });

  it("email on, Teams off: Outlook is live; Teams reads Coming soon with no Teams link", async () => {
    await show(baseRoutes(), { outlookAddress: ADDRESS, waysOn: { email: true, teams: false } });
    expect(link("Forward it from Outlook")?.getAttribute("href")).toBe("/share/other-ways");
    expect(wayText("email")).toContain(ADDRESS);
    expect(wayText("email")).not.toContain("Coming soon");
    expect(wayText("teams")).toContain("Message it in Teams Coming soon");
    expect(wayLinks("teams")).toHaveLength(0);
    expect(link("Message it in Teams")).toBeUndefined();
  });

  it("email off, Teams on: Outlook reads Coming soon with no link; Teams is live", async () => {
    await show(baseRoutes(), { outlookAddress: null, waysOn: { email: false, teams: true } });
    expect(wayText("email")).toContain("Forward it from Outlook Coming soon");
    expect(wayLinks("email")).toHaveLength(0);
    expect(link("Message it in Teams")?.getAttribute("href")).toBe("/share/other-ways");
    expect(wayText("teams")).toContain("Message it in Teams 1% Club");
    expect(wayText("teams")).not.toContain("Coming soon");
  });
});

describe("S-03.sections/1: Needs you follows the Inbox without a reload (BLD-C145, polish round)", () => {
  const SECOND = row({
    id: "IDEA-2026-001477",
    title: "Synthetic: nominee forms sent back for one missing date",
    pill: { status: "needs_you", label: "Needs you", variant: "warn" },
    group: "needs_you",
  });
  const SECOND_SET = { ...SET, id: "qs-2", idea_id: SECOND.id, idea: { id: SECOND.id, title: SECOND.title } };
  const reads = (calls: { url: string }[], path: string) =>
    calls.filter((c) => c.url.startsWith(path)).length;

  it("L-INBOX.rules/3: one inbox:counts event re-reads Needs you once; the count and cards update, the box keeps its words and focus", async () => {
    const { COUNTS_EVENT } = await import("@/lib/inbox-events");
    let ideas = mine([NEEDS, SECOND, PICKED], { needs_you: 3 });
    const calls = await show(
      baseRoutes({
        "/api/me/ideas": () => ({ status: 200, body: ideas }),
        [`/api/ideas/${SECOND.id}/question-set`]: () => ({ status: 200, body: SECOND_SET }),
      }),
    );
    expect(link("All 3 in Inbox")?.getAttribute("href")).toBe("/inbox");
    expect(host.querySelectorAll(".qcard")).toHaveLength(2);
    const ta = type(WORDS);
    act(() => ta.focus());
    const before = {
      mine: reads(calls, "/api/me/ideas"),
      crew: reads(calls, "/api/crew"),
      ones: reads(calls, "/api/ones"),
    };

    ideas = mine([NEEDS, PICKED], { needs_you: 1 }); // the second idea's questions were answered in the Inbox
    await act(async () => {
      window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail: { unread: 0, needs_you: 1 } }));
    });
    await flush();

    expect(reads(calls, "/api/me/ideas")).toBe(before.mine + 1);
    expect(reads(calls, "/api/crew")).toBe(before.crew); // only Needs you is read again
    expect(reads(calls, "/api/ones")).toBe(before.ones);
    expect(link("All 3 in Inbox")).toBeUndefined();
    expect(link("Open the Inbox")?.getAttribute("href")).toBe("/inbox");
    expect(host.querySelectorAll(".qcard")).toHaveLength(1);
    expect(text()).not.toContain(SECOND.title);
    expect((host.querySelector("textarea") as HTMLTextAreaElement).value).toBe(WORDS);
    expect(document.activeElement).toBe(host.querySelector("textarea"));
    expect(text()).not.toContain(HOME_COPY.loadingNeeds);
  });

  it("S-03.sections/1: the last item answered shows Nothing needs you right now", async () => {
    const { COUNTS_EVENT } = await import("@/lib/inbox-events");
    let ideas = mine([NEEDS, PICKED]);
    await show(baseRoutes({ "/api/me/ideas": () => ({ status: 200, body: ideas }) }));
    expect(host.querySelectorAll(".qcard")).toHaveLength(1);
    ideas = mine([PICKED]);
    await act(async () => {
      window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail: { unread: 0 } }));
    });
    await flush();
    expect(host.querySelector(".qcard")).toBeNull();
    expect(text()).toContain(HOME_COPY.needsNone);
  });

  it("A failed re-read keeps what is shown: no empty state, no loading rows", async () => {
    const { COUNTS_EVENT } = await import("@/lib/inbox-events");
    let fail = false;
    await show(
      baseRoutes({
        "/api/me/ideas": () =>
          fail
            ? { status: 500, body: { error: { code: "worker_error" } } }
            : { status: 200, body: mine([NEEDS, PICKED], { needs_you: 3 }) },
      }),
    );
    fail = true;
    await act(async () => {
      window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail: { unread: 0 } }));
    });
    await flush();
    expect(link("All 3 in Inbox")?.getAttribute("href")).toBe("/inbox");
    expect(host.querySelectorAll(".qcard")).toHaveLength(1);
    expect(text()).not.toContain(HOME_COPY.needsNone);
    expect(text()).not.toContain(HOME_COPY.loadingNeeds);
    expect(host.querySelectorAll(".hm-idea")).toHaveLength(2);
  });

  it("A question set that fails on a re-read keeps its card; every set failing keeps every card", async () => {
    const { COUNTS_EVENT } = await import("@/lib/inbox-events");
    let second = (): { status: number; body?: unknown } => ({ status: 200, body: SECOND_SET });
    let first = (): { status: number; body?: unknown } => ({ status: 200, body: SET });
    const calls = await show(
      baseRoutes({
        "/api/me/ideas": () => ({ status: 200, body: mine([NEEDS, SECOND, PICKED], { needs_you: 2 }) }),
        [`/api/ideas/${NEEDS.id}/question-set`]: () => first(),
        [`/api/ideas/${SECOND.id}/question-set`]: () => second(),
      }),
    );
    const cards = () => [...host.querySelectorAll(".qcard")].map((c) => c.textContent ?? "");
    expect(cards()).toHaveLength(2);
    const reread = async () => {
      await act(async () => {
        window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail: { unread: 0 } }));
      });
      await flush();
      await act(async () => await new Promise((r) => setTimeout(r, 300))); // past the gap between re-reads
    };

    second = () => ({ status: 503, body: { error: { code: "paused", message: "" } } });
    await reread();
    expect(reads(calls, `/api/ideas/${SECOND.id}/question-set`)).toBe(2);
    expect(cards()).toHaveLength(2);
    expect(cards()[1]).toContain(SECOND.title);

    first = () => ({ status: 500 });
    await reread();
    expect(cards()).toHaveLength(2);
    expect(link("All 2 in Inbox")?.getAttribute("href")).toBe("/inbox");
    expect(text()).not.toContain(HOME_COPY.needsNone);

    first = () => ({ status: 200, body: null }); // read, and no open set any more: that card goes
    await reread();
    expect(cards()).toHaveLength(1);
    expect(cards()[0]).toContain(SECOND.title);
  });

  it("A burst of Inbox events brings at most two reads: one at once, one after it with the latest", async () => {
    const { COUNTS_EVENT } = await import("@/lib/inbox-events");
    let ideas = mine([NEEDS, SECOND, PICKED], { needs_you: 2 });
    const calls = await show(
      baseRoutes({
        "/api/me/ideas": () => ({ status: 200, body: ideas }),
        [`/api/ideas/${SECOND.id}/question-set`]: () => ({ status: 200, body: SECOND_SET }),
      }),
    );
    const first = reads(calls, "/api/me/ideas");
    ideas = mine([NEEDS, PICKED], { needs_you: 1 });
    await act(async () => {
      for (let i = 0; i < 6; i++)
        window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail: { unread: i } }));
    });
    await flush();
    expect(reads(calls, "/api/me/ideas")).toBe(first + 1);
    await act(async () => {
      for (let i = 0; i < 3; i++)
        window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail: { unread: i } }));
    });
    await act(async () => await new Promise((r) => setTimeout(r, 400)));
    await flush();
    expect(reads(calls, "/api/me/ideas")).toBe(first + 2);
    expect(host.querySelectorAll(".qcard")).toHaveLength(1);
    expect(link("Open the Inbox")?.getAttribute("href")).toBe("/inbox");
    await act(async () => await new Promise((r) => setTimeout(r, 400)));
    expect(reads(calls, "/api/me/ideas")).toBe(first + 2); // nothing more queued
  });

  it("pageshow from the back/forward cache re-reads Needs you; an ordinary pageshow does not", async () => {
    let ideas = mine([NEEDS, PICKED]);
    const calls = await show(baseRoutes({ "/api/me/ideas": () => ({ status: 200, body: ideas }) }));
    const first = reads(calls, "/api/me/ideas");
    ideas = mine([PICKED]);
    await act(async () => {
      window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: false }));
    });
    await flush();
    expect(reads(calls, "/api/me/ideas")).toBe(first);
    expect(host.querySelectorAll(".qcard")).toHaveLength(1);
    await act(async () => {
      window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true }));
    });
    await flush();
    expect(reads(calls, "/api/me/ideas")).toBe(first + 1);
    expect(host.querySelector(".qcard")).toBeNull();
    expect(text()).toContain(HOME_COPY.needsNone);
  });

  it("A first visit shows no Needs you, so the event reads nothing", async () => {
    const { COUNTS_EVENT } = await import("@/lib/inbox-events");
    const calls = await show(baseRoutes(), { firstVisit: true });
    const first = reads(calls, "/api/me/ideas");
    await act(async () => {
      window.dispatchEvent(new CustomEvent(COUNTS_EVENT, { detail: { unread: 0 } }));
    });
    await flush();
    expect(reads(calls, "/api/me/ideas")).toBe(first);
  });
});

describe("lib/home/data (BLD-C143, C145, C146)", () => {
  it("loadMine: shared ideas only, the total from counts, the ideas that need the person", async () => {
    const { f } = fakeFetch(baseRoutes());
    const m = await loadMine(f);
    expect(m?.ideas.total).toBe(3);
    expect(m?.ideas.top.map((r) => r.id)).toEqual([NEEDS.id, PICKED.id, BUILT.id]);
    expect(m?.needs.rows.map((r) => r.id)).toEqual([NEEDS.id]);
    expect(m?.drafts).toBe(1);
  });

  it("readSets and keepFailedSets: a failed read is marked and keeps its card; all failed keeps the list", async () => {
    const { f } = fakeFetch({
      [`/api/ideas/${NEEDS.id}/question-set`]: () => ({ status: 503 }),
      [`/api/ideas/${PICKED.id}/question-set`]: () => ({ status: 200, body: null }),
    });
    const got = await readSets(f, [NEEDS, PICKED]);
    expect(got).toEqual([
      { ideaId: NEEDS.id, set: null, failed: true },
      { ideaId: PICKED.id, set: null, failed: false },
    ]);
    const before = [{ ideaId: NEEDS.id, set: SET }];
    expect(keepFailedSets(before, got)).toEqual(before);
    expect(keepFailedSets(before, [got[0]!])).toBeNull();
    expect(keepFailedSets(before, [])).toEqual([]);
    expect(keepFailedSets(before, [{ ideaId: NEEDS.id, set: null, failed: false }])).toEqual([]);
  });

  it("loadSets: an idea with no open set is left out", async () => {
    const { f } = fakeFetch({ [`/api/ideas/${NEEDS.id}/question-set`]: () => ({ status: 200, body: null }) });
    expect(await loadSets(f, [NEEDS])).toEqual([]);
  });

  it("loadCrew asks for three; loadOnes takes a list; both null when the route cannot be read", async () => {
    const { f, calls } = fakeFetch(baseRoutes());
    expect((await loadCrew(f))?.top).toHaveLength(1);
    expect(calls.at(-1)?.url).toBe("/api/crew?limit=3");
    const none = fakeFetch({});
    expect(await loadCrew(none.f)).toBeNull();
    expect(await loadOnes(none.f)).toBeNull();
  });
});

describe("C-SIDEBAR Drafts (J-RESUME/2, BLD-C147)", () => {
  const item = (id: string, sidebar: string, archived = false): DraftListItem =>
    ({
      id,
      title: "Synthetic: address change form filled twice",
      saved_at: "2026-11-17T10:00:00.000Z",
      saved_on: { device: "phone", this_device: false },
      saved_labels: { sidebar } as DraftListItem["saved_labels"],
      step: "tell",
      char_count: 120,
      channel: "web",
      archived,
    }) as DraftListItem;

  it("up to two, each with when and where it was saved, opening S-04B on that draft", () => {
    const rows = draftRows([
      item("a1b2c3d4-0000-4000-8000-000000000001", "Today, on your phone"),
      item("a1b2c3d4-0000-4000-8000-000000000002", "Yesterday, on this laptop", true),
      item("a1b2c3d4-0000-4000-8000-000000000003", "Friday, on your phone"),
      item("a1b2c3d4-0000-4000-8000-000000000004", "Thursday, on your phone"),
    ]);
    expect(rows).toEqual([
      {
        href: "/share/a1b2c3d4-0000-4000-8000-000000000001",
        title: "Synthetic: address change form filled twice",
        meta: "Today, on your phone",
        tone: "draft",
      },
      {
        href: "/share/a1b2c3d4-0000-4000-8000-000000000003",
        title: "Synthetic: address change form filled twice",
        meta: "Friday, on your phone",
        tone: "draft",
      },
    ]);
    expect(draftRows(null)).toEqual([]);
  });
});

describe("C-SIDEBAR Drafts on this device (J-RESUME/2, BLD-C147)", () => {
  beforeEach(() => {
    request.headers = new Headers();
    request.cookies.clear();
  });

  it("Home leaves the draft client's device id as a first-party cookie, the same id it sends as X-Device-Id", async () => {
    document.cookie = `${DEVICE_COOKIE}=; path=/; max-age=0`;
    await show(baseRoutes());
    const cookie = /(?:^|; )device_id=([A-Za-z0-9_-]{8,64})(?:;|$)/.exec(document.cookie);
    expect(cookie).not.toBeNull();
    let sent: string | null = null;
    await act(async () => {
      root.render(
        createElement(HomeScreen, {
          firstName: "Kavya",
          fetchImpl: fakeFetch(
            baseRoutes({
              "/api/drafts": (init) => {
                sent = new Headers(init?.headers).get("X-Device-Id");
                return { status: 201, body: { draft: { id: NEW_DRAFT, messages: [] }, run_id: null } };
              },
            }),
          ).f,
        }),
      );
    });
    await flush();
    type(WORDS);
    act(() => link("Continue to Share a problem")!.click());
    await flush();
    expect(sent).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(/(?:^|; )device_id=([A-Za-z0-9_-]{8,64})/.exec(document.cookie)![1]).toBe(sent);
  });

  it("the shell reads that cookie, so a draft saved on this laptop reads on this laptop; X-Device-Id wins", async () => {
    request.cookies.set(DEVICE_COOKIE, "laptopdevice01");
    expect(await askingDevice()).toEqual({ kind: "laptop", id: "laptopdevice01" });
    request.headers = new Headers({ "x-device-id": "headerdevice02" });
    expect(await askingDevice()).toEqual({ kind: "laptop", id: "headerdevice02" });
    request.headers = new Headers({ "user-agent": "Mozilla/5.0 (Linux; Android 14) Mobile" });
    request.cookies.set(DEVICE_COOKIE, "bad id with spaces");
    expect(await askingDevice()).toEqual({ kind: "phone", id: null });
  });
});

describe("S-03 C-PROMPT.voice: the round voice button in Home's empty box (WF-02, BLD-C220)", () => {
  const STREAM = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d";
  const NOTE = {
    streamId: STREAM,
    text: "Branch mein roz das log nominee badalne aate hain aur har baar do form bharne padte hain",
    spans: [],
    textEn: "Ten people come to the branch every day to change a nominee and fill two forms each time",
    enLabel: "Typed up in English",
    seconds: 6,
    endedBy: "person",
    hiddenCount: 0,
    translated: true,
    translationFailure: null,
    lang: "hi-IN",
    language: "Hindi",
    summary: "Voice message, 6 seconds, in Hindi",
  };
  const TYPED = "Synthetic: the nominee screen asks for the same details twice.";

  const button = (name: string) =>
    [...host.querySelectorAll<HTMLButtonElement>("button")].find(
      (b) => (b.getAttribute("aria-label") ?? b.textContent ?? "").replace(/\s+/g, " ").trim() === name,
    );
  const box = () => host.querySelector("textarea") as HTMLTextAreaElement;

  /** Let Home take a capture state (it does so on the next tick, as Share does) and finish what follows. */
  async function settle() {
    for (let i = 0; i < 6; i++) {
      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });
    }
  }
  async function hear(state: unknown) {
    await act(async () => voice.set(state));
    await settle();
  }
  async function tap(name: string) {
    await act(async () => button(name)!.click());
    await settle();
  }

  async function axeSerious(): Promise<string[]> {
    const axe = (await import("axe-core")).default;
    const result = await axe.run(host.querySelector<HTMLElement>(".hm-hero-in")!, {
      rules: { "color-contrast": { enabled: false } },
      resultTypes: ["violations"],
    });
    return result.violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
  }

  /** Home's draft: one create with no words (for the tap, or a first file), and the messages added to it. */
  function draftRoutes(answer?: (body: Record<string, unknown>) => { status: number; body?: unknown }) {
    const created: unknown[] = [];
    const messages: Record<string, unknown>[] = [];
    const keys: (string | null)[] = [];
    const routes = baseRoutes({
      [`/api/drafts/${NEW_DRAFT}/messages`]: (init) => {
        const body = JSON.parse(String(init?.body)) as Record<string, unknown>;
        messages.push(body);
        keys.push(new Headers(init?.headers).get("Idempotency-Key"));
        return (
          answer?.(body) ?? {
            status: 202,
            body: {
              run_id: "r-1",
              message: { id: `m-${messages.length}` },
              draft: { id: NEW_DRAFT, messages: [] },
            },
          }
        );
      },
      "/api/drafts": (init) => {
        created.push(JSON.parse(String(init?.body)));
        return { status: 201, body: { draft: { id: NEW_DRAFT, messages: [] }, run_id: null } };
      },
    });
    return { routes, created, messages, keys };
  }

  it("V-ACC S-03, C-PROMPT.voice: the empty box's round button is the microphone, a sound wave named Tap to start speaking, with both hint lines; axe", async () => {
    await show(baseRoutes());
    const round = button("Tap to start speaking")!;
    expect(round).toBeTruthy();
    expect(round.classList.contains("send")).toBe(true);
    expect(round.querySelector("svg.wave")).toBeTruthy();
    expect(round.textContent?.trim()).toBe(""); // no visible label
    const hint = host.querySelector(".prompt .vhint")!;
    expect(hint.getAttribute("aria-hidden")).toBe("true");
    expect(hint.querySelector("b")?.textContent).toBe("Tap to start speaking");
    expect(hint.querySelector("span")?.textContent).toBe("Not recording until you do");
    expect(hint.nextElementSibling).toBe(round);
    expect(host.querySelector(".prompt .mic2")!.classList.contains("hid")).toBe(true);
    expect(link("Continue to Share a problem")).toBeUndefined();
    expect(voice.start).not.toHaveBeenCalled(); // nothing records until the person taps
    expect(await axeSerious()).toEqual([]);
  });

  it("V-ACC S-03, C-PROMPT.voice: with words in the box the round button sends again, and the small microphone shows", async () => {
    await show(baseRoutes());
    type(WORDS);
    expect(button("Tap to start speaking")).toBeUndefined();
    expect(host.querySelector(".prompt .vhint")).toBeNull();
    expect(link("Continue to Share a problem")).toBeDefined();
    const mic = button("Speak instead")!;
    expect(mic.classList.contains("mic2")).toBe(true);
    expect(mic.classList.contains("hid")).toBe(false);
  });

  it("V-ACC S-03, C-PROMPT.voice, L-DRAFT.voice: a tap calls start, which asks for Home's draft inside the tap, made once with no words", async () => {
    const d = draftRoutes();
    await show(d.routes);
    await tap("Tap to start speaking");
    expect(voice.start).toHaveBeenCalledTimes(1);
    expect(d.created).toEqual([{ channel: "web" }]);
    expect(d.messages).toEqual([]);
    expect(push).not.toHaveBeenCalled();
  });

  it("V-ACC S-03, L-DRAFT.voice: recording shows Stop (axe); a finished note goes into the draft the tap made, as voice with its stream, and S-04B opens on it", async () => {
    const d = draftRoutes();
    await show(d.routes);
    await tap("Tap to start speaking");
    await hear({ status: "recording", seconds: 3, maxSeconds: 180, text: NOTE.text, spans: [] });
    const stop = button("Stop, and use what you said")!;
    expect(stop).toBeTruthy();
    expect(stop.getAttribute("aria-pressed")).toBe("true");
    expect(box().value).toBe(NOTE.text); // the words as they are heard
    expect(await axeSerious()).toEqual([]);
    await act(async () => stop.click());
    expect(voice.stop).toHaveBeenCalledTimes(1);

    await hear({ status: "done", note: NOTE });
    expect(d.created).toHaveLength(1);
    expect(d.messages.map((m) => [m.via, m.text, m.stream_id])).toEqual([["voice", NOTE.text, STREAM]]);
    expect(d.keys).toEqual([d.messages[0]!.client_id]);
    expect(voice.reset).toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith(`/share/${NEW_DRAFT}`);
    expect(push).toHaveBeenCalledTimes(1);
  });

  it("V-ACC S-03, L-DRAFT.voice: typed words go first, as typed, then the note as voice; one draft however often the microphone is tapped", async () => {
    const d = draftRoutes();
    await show(d.routes);
    await tap("Tap to start speaking");
    await hear({ status: "failed", reason: "no_microphone", text: "", spans: [] }); // no line, the mic is ready again
    type(TYPED);
    await tap("Speak instead");
    expect(voice.start).toHaveBeenCalledTimes(2);
    await hear({ status: "done", note: NOTE });
    expect(d.created).toHaveLength(1); // the draft the first tap made (or a first file: the same create-once draft)
    expect(d.messages.map((m) => [m.via, m.text, m.stream_id])).toEqual([
      ["typed", TYPED, undefined],
      ["voice", NOTE.text, STREAM],
    ]);
    expect(d.keys[0]).toBe(d.messages[0]!.client_id);
    expect(d.keys[1]).toBe(d.messages[1]!.client_id);
    expect(d.keys[0]).not.toBe(d.keys[1]);
    expect(push).toHaveBeenCalledWith(`/share/${NEW_DRAFT}`);
  });

  it("BLD-C220 review fix, L-DRAFT.voice: while a note goes in, a second note adds nothing and the microphone does not start", async () => {
    let release!: () => void;
    const held = new Promise<void>((r) => (release = r));
    const messages: unknown[] = [];
    const routes = baseRoutes({
      [`/api/drafts/${NEW_DRAFT}/messages`]: async (init) => {
        messages.push(JSON.parse(String(init?.body)));
        await held; // the first note's message is still going in
        const message = { id: `m-${messages.length}` };
        return { status: 202, body: { run_id: "r-1", message, draft: { id: NEW_DRAFT, messages: [] } } };
      },
      "/api/drafts": () => ({ status: 201, body: { draft: { id: NEW_DRAFT, messages: [] }, run_id: null } }),
    });
    await show(routes);
    await tap("Tap to start speaking");
    voice.start.mockClear();
    await hear({ status: "done", note: NOTE });
    expect(messages).toHaveLength(1);
    await hear({ status: "done", note: { ...NOTE, streamId: "1b2c3d4e-5f6a-4b7c-8d9e-0f1a2b3c4d5e" } });
    expect(messages).toHaveLength(1); // the second note added nothing
    await act(async () => button("Speak instead")?.click());
    expect(voice.start).not.toHaveBeenCalled(); // no new capture while one goes in
    release();
    await settle();
    expect(push).toHaveBeenCalledTimes(1);
  });

  it("BLD-C220 review fix, L-DRAFT.voice: after a note fails back into the box, the next note is taken as usual", async () => {
    let first = true;
    const d = draftRoutes(() => {
      if (!first) return undefined as never; // the route's usual answer
      first = false;
      return { status: 422, body: { error: { code: "too_long", message: "That message is too long." } } };
    });
    await show(d.routes);
    await tap("Tap to start speaking");
    await hear({ status: "done", note: NOTE });
    expect(box().value).toBe(NOTE.text);
    expect(push).not.toHaveBeenCalled();
    await hear({ status: "done", note: { ...NOTE, streamId: "1b2c3d4e-5f6a-4b7c-8d9e-0f1a2b3c4d5e" } });
    expect(d.messages.length).toBeGreaterThan(1); // taken: not stuck behind the failed one
    expect(push).toHaveBeenCalledWith(`/share/${NEW_DRAFT}`);
  });

  it("V-ACC S-03, L-DRAFT.voice: a note that cannot be added keeps its words in the box and says why; nothing opens", async () => {
    const d = draftRoutes(() => ({
      status: 422,
      body: { error: { code: "too_long", message: "That message is too long." } },
    }));
    await show(d.routes);
    await tap("Tap to start speaking");
    await hear({ status: "done", note: NOTE });
    expect(d.messages).toHaveLength(1);
    expect(box().value).toBe(NOTE.text);
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("That message is too long.");
    expect(push).not.toHaveBeenCalled();
    expect(link("Continue to Share a problem")).toBeDefined(); // not stuck sending
  });

  it("C-PROMPT.voice: a note that failed with words heard puts them in the box; signed out says Sign in again to carry on", async () => {
    await show(baseRoutes());
    await hear({ status: "failed", reason: "signed_out", text: NOTE.text, spans: [] });
    expect(box().value).toBe(NOTE.text);
    const again = link("Sign in again to carry on")!;
    expect(again.getAttribute("href")).toBe("/sign-in?next=%2Fhome");
    expect(again.closest('[role="alert"]')).toBeTruthy();
    expect(push).not.toHaveBeenCalled();
  });

  it("V-ACC S-03, C-PROMPT.voice: blocked shows the browser's words as an alert and the microphone as blocked; axe", async () => {
    await show(baseRoutes());
    await hear({ status: "blocked", device: "desktop", ...MIC_BLOCKED.desktop });
    const alert = host.querySelector('.blkn[role="alert"]')!;
    expect(alert.textContent).toContain(MIC_BLOCKED.desktop.title);
    expect(alert.textContent).toContain(MIC_BLOCKED.desktop.body);
    expect(button("Microphone blocked")).toBeTruthy();
    expect(button("Tap to start speaking")).toBeUndefined();
    expect(await axeSerious()).toEqual([]);
  });

  it("C-PROMPT.voice, kill switches: voice switched off shows the switch's own line, as on Share; typing still sends", async () => {
    await show(baseRoutes());
    await hear({
      status: "paused",
      banner: BANNERS["capture.voice"],
      switchName: "capture.voice",
      text: "",
      spans: [],
      note: null,
    });
    expect(host.querySelector('.vlive[role="status"]')?.textContent).toBe(BANNERS["capture.voice"]);
    expect(push).not.toHaveBeenCalled();
    type(WORDS);
    expect(link("Continue to Share a problem")).toBeDefined();
  });

  it("the hint shows on a phone, as PhoneHome draws it, and never over the open picker (Home.dc.html)", () => {
    const css = readFileSync(path.resolve(__dirname, "../../src/app/home/home.css"), "utf8");
    const phone = css.slice(css.indexOf("@media (max-width: 640px)"));
    expect(phone).toMatch(/\.hm \.cz \.hm-prompt \.vhint \{\s*display: flex;/);
    expect(css).toMatch(/\.hm \.cz \.hm-prompt:has\(\.cpick\) \.vhint \{\s*display: none;/);
  });

  it("BLD-C240, C-PROMPT.voice: once typed, the hint never comes back, even after the box is cleared; the round button is still the microphone", async () => {
    await show(baseRoutes());
    expect(host.querySelector(".prompt .vhint")).not.toBeNull();
    type(WORDS);
    expect(host.querySelector(".prompt .vhint")).toBeNull();
    type("");
    expect(host.querySelector(".prompt .vhint")).toBeNull(); // as the board's !draft && !typed
    expect(button("Tap to start speaking")).toBeDefined(); // the round button keeps roundIsMic
  });

  it("BLD-C240 (lane D): on a phone the hint goes while the words box has focus", () => {
    const css = readFileSync(path.resolve(__dirname, "../../src/app/home/home.css"), "utf8");
    const phone = css.slice(css.indexOf("@media (max-width: 640px)"));
    expect(phone).toMatch(/\.hm \.cz \.hm-prompt \.tx:focus-within ~ \.cfoot \.vhint \{\s*display: none;/);
    expect(phone).not.toMatch(/:has\(textarea/); // no :has(): Firefox 111, the floor, drops it
  });

  it("BLD-C240 (lane D): under reduced motion the hint still shows for the same time, then goes at once at 5.9 s", () => {
    const css = readFileSync(path.resolve(__dirname, "../../src/app/share/compose.css"), "utf8");
    const reduce = css.slice(css.indexOf("@media (prefers-reduced-motion: reduce)"));
    const off = reduce.slice(0, reduce.indexOf("animation: none;"));
    expect(off).not.toMatch(/\.cz \.vhint/); // not in the animation: none list
    expect(reduce).toMatch(/\.cz \.vhint \{\s*animation: czHintOut 0s linear 5\.9s forwards;/);
    // foundation.css's F-MOTION.reduced rule sets every animation-delay to 0s !important; the hint's own
    // !important keeps its 5.9 s, or it would be gone on arrival.
    const foundation = readFileSync(path.resolve(__dirname, "../../src/app/foundation.css"), "utf8");
    expect(foundation).toMatch(/animation-delay: 0s !important;/);
    expect(reduce).toMatch(/\.cz \.vhint \{[^}]*animation-delay: 5\.9s !important;/);
  });
});
