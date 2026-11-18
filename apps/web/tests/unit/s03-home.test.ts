// @vitest-environment jsdom
/**
 * S-03 Home against a mocked A-API (BLD-C143 to C147). J-SHARE/v1 as far as the browser goes: the question, the box
 * named "Say it in your own words", "Continue to Share a problem" once there are words, and sending makes the draft
 * with the words (POST /api/drafts, one Idempotency-Key) and opens S-04B on it, never the empty S-04. J-TRACK/2: Needs
 * you carries the desk's questions with the clock and "Answer the questions" into S-R3. J-RESUME/2: the side bar's
 * Drafts read "Friday, on your phone" and open S-04B. The None, One and Several states of each section, with the
 * boards' words (reference/copy/Home.md). Synthetic words only.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CrewCard, DraftListItem, MyIdeaRow, SharerQuestionSetResponse } from "@/lib/contracts";

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

const { HomeScreen, HOME_COPY } = await import("@/app/home/home");
const { loadCrew, loadMine, loadOnes, loadSets } = await import("@/lib/home/data");
const { askingDevice, draftRows } = await import("@/server/shell");
const { DEVICE_COOKIE } = await import("@/lib/compose/client");

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

type Routes = Record<string, (init?: RequestInit) => { status: number; body?: unknown }>;

function fakeFetch(routes: Routes) {
  const calls: { url: string; init?: RequestInit }[] = [];
  const f = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, init });
    const hit = Object.entries(routes).find(
      ([k]) => url === k || url.startsWith(`${k}?`) || url.startsWith(k),
    );
    const out = hit ? hit[1](init) : { status: 404, body: { error: "not_found" } };
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
  "/api/crew": () => ({ status: 200, body: { items: [CREW], total: 1, joined: 0, pending: 0, passed: 0 } }),
  "/api/ones/posts": () => ({ status: 200, body: [] }),
  ...over,
});

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  push.mockReset();
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

async function show(routes: Routes, props: { firstVisit?: boolean; outlookAddress?: string | null } = {}) {
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
    expect(host.querySelector('[role="alert"]')).toBeNull();
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
    expect(text()).toContain(`Harish from the review desk asked about "${NEEDS.title}"`);
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

  it("Find your crew, none (or the crew route not there yet): the empty state and Browse the Wall", async () => {
    await show(baseRoutes({ "/api/crew": () => ({ status: 404 }) }));
    const status = [...host.querySelectorAll('[role="status"]')].find((s) =>
      s.textContent?.includes("No one close to yours yet"),
    );
    expect(status?.textContent).toContain(
      "When someone shares an idea near yours or in your area, it shows up here so you can team up.",
    );
    expect(link("Browse the Wall")?.getAttribute("href")).toBe("/wall");
  });

  it("Or share from where you already are: three tiles, the app Coming soon", async () => {
    await show(baseRoutes(), { outlookAddress: "share@1pc.kfintech.example" });
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

describe("lib/home/data (BLD-C143, C145, C146)", () => {
  it("loadMine: shared ideas only, the total from counts, the ideas that need the person", async () => {
    const { f } = fakeFetch(baseRoutes());
    const m = await loadMine(f);
    expect(m?.ideas.total).toBe(3);
    expect(m?.ideas.top.map((r) => r.id)).toEqual([NEEDS.id, PICKED.id, BUILT.id]);
    expect(m?.needs.rows.map((r) => r.id)).toEqual([NEEDS.id]);
    expect(m?.drafts).toBe(1);
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
