// @vitest-environment jsdom
/**
 * V-ACC for the walk's WF-03b on Home (DEC-126 (6), BLD-C219; S-03.sections/3, C-CREW-DECK.states, L-CREW/1 and /3),
 * against a mocked A-API. Home's crew card draws lane F's `RequestedAction` where "Team up" was once the person has
 * asked to join the idea, as Find your crew (S-H2) does:
 * - after a send through the team-up sheet the card reads "Requested", inactive but focusable and read out, with
 *   "Withdraw" under it as its own quiet link; the card goes to the end of Home's deck and the deck follows it, so the
 *   sheet hands focus back to "Requested" when it closes;
 * - after a withdraw, from the card or from the sheet, "Team up" is back where the card stands, with focus on it, and
 *   no card moves;
 * - after a reload, a card that arrives with `request` (last, BLD-F094) draws "Requested".
 * Desktop and phone: the markup is one, and the phone's look is CSS (lane G's walk reads it). axe on each state.
 * Synthetic people only: the pack's fictional cast (Kavya asks, Ravi leads) and made-up colleagues.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CrewCard, CrewDeckResponse } from "@/lib/contracts";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("@/lib/motion/spark", () => ({ sparkBurst: vi.fn() }));
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: push, refresh: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
    createElement("a", { href, ...rest }, children as never),
}));

const { HomeScreen } = await import("@/app/home/home");
const { requestDropped, requestedLast } = await import("@/app/home/crew-card");

// --- Fixtures (synthetic) --------------------------------------------------------------------------------------
const RAVI = { id: "p-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" };
const SANJAY = { id: "p-sanjay", name: "Sanjay Pillai", first_name: "Sanjay", initials: "SP" };
const DIVYA = { id: "p-divya", name: "Divya Shah", first_name: "Divya", initials: "DS" };
const KAVYA = { id: "p-kavya", name: "Kavya Iyer", first_name: "Kavya", initials: "KI" };

function card(id: string, title: string, lead: typeof RAVI, extra: Partial<CrewCard> = {}): CrewCard {
  return {
    id,
    title,
    status: "with_review_desk",
    area: "Investor service",
    city: "Hyderabad",
    shared_at: "2026-11-14T10:00:00+05:30",
    lead,
    crew_faces: [lead],
    crew_count: 3,
    in_their_words: "Investors get a code, not a reason, and then they call us.",
    hue: 1,
    reason_kind: "close_to_yours",
    reason: "Same R07 SMS as your idea from Saturday",
    ...extra,
  } as CrewCard;
}
const A = card("IDEA-2026-001412", "Status SMS codes confuse investors", RAVI);
const B = card("IDEA-2026-001415", "No script for calls about redemption delays", SANJAY, { hue: 2 });
const C = card("IDEA-2026-001420", "Branch queue times are not tracked anywhere", DIVYA);

const TEAM_UP_A = "Team up on Status SMS codes confuse investors, with Ravi Nair";
const REQUESTED_A = "Requested: you asked to team up on Status SMS codes confuse investors";
const WITHDRAW_A = "Withdraw your request to team up on Status SMS codes confuse investors";

/** Lane F's `GET /api/crew?limit=3` answer (BLD-F094: a requested card comes last). */
function crewDeck(cards: CrewCard[]): CrewDeckResponse {
  return {
    items: cards,
    total: cards.length,
    counts: { "location:Hyderabad": cards.length },
    filters: [],
    active: [],
    deck_total: cards.length,
    state: cards.length ? "cards" : "nothing_yet",
    asked: cards.filter((c) => c.request).length,
    last_passed: null,
    joined: 0,
    pending: 0,
    passed: 0,
  };
}

// --- A mocked A-API, by method and path (Home's reads and the team-up sheet's calls) ----------------------------
type Answer = { status: number; body: unknown };
let routes: Record<string, Answer | ((body: unknown) => Answer)>;
let calls: { key: string; body: unknown }[];

const fakeFetch = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
  const url = String(input);
  const key = `${(init.method ?? "GET").toUpperCase()} ${url.split("?")[0]}`;
  const body = typeof init.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
  calls.push({ key, body });
  const route = routes[key];
  const a: Answer =
    typeof route === "function"
      ? route(body)
      : (route ?? { status: 404, body: { error: { code: "not_found", message: "" } } });
  return new Response(JSON.stringify(a.body), {
    status: a.status,
    headers: { "Content-Type": "application/json" },
  });
});
const posts = () => calls.filter((c) => !c.key.startsWith("GET ")).map((c) => c.key);

/** The team-up sheet's calls for A: a send makes request req-1, waiting for Ravi (as lane F's crew-screen test). */
function answerTeamUp() {
  routes[`GET /api/ideas/${A.id}/team-up`] = {
    status: 200,
    body: {
      idea_id: A.id,
      lead: RAVI,
      me: null,
      crew_count: 3,
      can_request: true,
      why_not: null,
      request: null,
      after: null,
    },
  };
  routes[`GET /api/ideas/${A.id}/team-up/draft-note`] = {
    status: 200,
    body: {
      note: "I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07.",
      own_ideas: [],
      idea: { id: A.id, title: A.title },
      lead: RAVI,
      min_chars: 30,
      max_chars: 600,
    },
  };
  routes["GET /api/me"] = {
    status: 200,
    body: { name: "Kavya Iyer", email: "kavya@example.test", contributor_code: "CTR-0a1b2c" },
  };
  routes[`POST /api/ideas/${A.id}/team-up`] = (b) => ({
    status: 201,
    body: {
      id: "req-1",
      request: "teamup",
      idea_id: A.id,
      from: KAVYA,
      note: (b as { note: string }).note,
      brought: [],
      state: "sent",
      sent_at: "2026-11-21T10:30:00+05:30",
      after: { state: "waiting", line: "Waiting for Ravi", action: { label: "Withdraw", op: "withdraw" } },
    },
  });
}

function answerWithdraw(id: string, kind: "teamup" | "merge" = "teamup") {
  routes[`DELETE /api/team-up/${id}`] = {
    status: 200,
    body: { id, request: kind, idea_id: A.id, state: "withdrawn", after: null },
  };
}

let phone = false;
let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  calls = [];
  routes = {
    "GET /api/me/ideas": { status: 200, body: { items: [], total: 0, counts: {} } },
    "GET /api/ones/posts": { status: 200, body: [] },
  };
  phone = false;
  push.mockReset();
  const mem = new Map<string, string>();
  const store = {
    getItem: (k: string) => mem.get(k) ?? null,
    setItem: (k: string, v: string) => void mem.set(k, String(v)),
    removeItem: (k: string) => void mem.delete(k),
    clear: () => mem.clear(),
  };
  vi.stubGlobal("localStorage", store);
  Object.defineProperty(window, "localStorage", { value: store, configurable: true });
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: phone, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  );
  vi.stubGlobal(
    "EventSource",
    class {
      addEventListener() {}
      close() {}
    },
  );
  vi.stubGlobal("fetch", fakeFetch);
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
});

/** Let the chained reads settle (each macrotask runs every pending microtask). */
async function settle() {
  for (let i = 0; i < 4; i++) {
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
  }
}
/** Let requestAnimationFrame callbacks run (focus moves after the card is drawn again). */
async function frames() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 40));
  });
}

async function showHome(items: CrewCard[], device: "desk" | "phone" = "desk") {
  phone = device === "phone";
  routes["GET /api/crew"] = { status: 200, body: crewDeck(items) };
  await act(async () => {
    root.render(createElement(HomeScreen, { firstName: "Kavya", fetchImpl: fakeFetch as typeof fetch }));
  });
  await settle();
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const nameOf = (el: Element) => el.getAttribute("aria-label") ?? text(el);
const buttons = () => Array.from(document.querySelectorAll<HTMLButtonElement>("button"));
const button = (name: string) => buttons().find((b) => nameOf(b) === name);
const crewSection = () => host.querySelector<HTMLElement>("#hm-crew")!;
/** Every card in Home's pile, in deck order (only the front one is in the reading order). */
const slots = () => Array.from(crewSection().querySelectorAll<HTMLElement>(".dcard"));
const order = () => slots().map((d) => text(d.querySelector(".hm-pc-t")));
const front = () => slots().find((d) => d.getAttribute("aria-hidden") !== "true");
const sheet = () => document.querySelector<HTMLElement>('[role="dialog"]');

async function click(el: Element | null | undefined) {
  expect(el, "element to click").toBeTruthy();
  await act(async () => (el as HTMLElement).click());
  await settle();
}

/** Team up on A from Home's deck and send the note; the sheet stays on its sent step. */
async function sendOnA() {
  const teamUp = button(TEAM_UP_A)!;
  expect(teamUp).toBeTruthy();
  teamUp.focus(); // a pointer click focuses the button; the sheet remembers it as its opener
  await click(teamUp);
  expect(sheet(), "the team-up sheet").toBeTruthy();
  await click(
    Array.from(sheet()!.querySelectorAll("button")).find((b) => text(b).startsWith("Send to Ravi")),
  );
  expect(posts()).toEqual([`POST /api/ideas/${A.id}/team-up`]);
}

async function axeSerious(): Promise<string[]> {
  const axe = (await import("axe-core")).default;
  const result = await axe.run(crewSection(), {
    rules: { "color-contrast": { enabled: false } },
    resultTypes: ["violations"],
  });
  return result.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

/** "Requested" as DEC-126 (1) draws it: Team up's look and place, greyed, inactive, focusable and read out. */
function expectRequested(requested: HTMLButtonElement | undefined) {
  expect(requested, "Requested").toBeTruthy();
  expect(text(requested)).toBe("Requested");
  expect(requested!.getAttribute("aria-disabled")).toBe("true");
  expect(requested!.hasAttribute("disabled")).toBe(false);
  expect(requested!.classList.contains("is-inactive")).toBe(true);
  expect(requested!.classList.contains("btn-primary")).toBe(true);
  expect(requested!.classList.contains("btn-full")).toBe(true);
  expect(requested!.getAttribute("data-teamup-opener")).toBe(A.id);
  // "Withdraw" is its own quiet link under it, never inside it (DEC-126 (3), BLD-D019).
  const withdraw = button(WITHDRAW_A)!;
  expect(withdraw).toBeTruthy();
  expect(text(withdraw)).toBe("Withdraw");
  expect(withdraw.className).toBe("link-quiet");
  expect(requested!.contains(withdraw)).toBe(false);
  expect(withdraw.parentElement).toBe(requested!.parentElement);
  expect(requested!.parentElement!.classList.contains("tu-req")).toBe(true);
  // Team up's place: the card's foot, after the crew line.
  expect(requested!.closest(".hm-pc-foot")).toBeTruthy();
  expect(button(TEAM_UP_A)).toBeUndefined();
}

for (const device of ["desk", "phone"] as const) {
  describe(`S-03 crew card, DEC-126 (WF-03b, BLD-C219), ${device}`, () => {
    it(`V-ACC S-03.sections/3, C-CREW-DECK.states, DEC-126 (1)-(3) (${device}): Team up is marked as the sheet's opener; after a send the card reads Requested with Withdraw under it, goes to the end, and the sheet hands focus back to Requested`, async () => {
      answerTeamUp();
      await showHome([A, B, C], device);
      expect(order()).toEqual([A.title, B.title, C.title]);
      expect(text(crewSection())).toContain("Idea 1 of 3");
      expect(button(TEAM_UP_A)!.getAttribute("data-teamup-opener")).toBe(A.id);
      expect(await axeSerious()).toEqual([]);

      await sendOnA();
      // DEC-126 (2): straight away the card is last; the others keep their order; the deck follows it.
      expect(order()).toEqual([B.title, C.title, A.title]);
      expect(text(front())).toContain(A.title);
      expect(text(crewSection())).toContain("Idea 3 of 3");

      await click(Array.from(sheet()!.querySelectorAll("button")).find((b) => text(b) === "Done"));
      await frames();
      expect(sheet()).toBeNull();
      const requested = button(REQUESTED_A);
      expectRequested(requested);
      expect(front()!.contains(requested!)).toBe(true);
      expect(document.activeElement).toBe(requested); // WCAG 2.4.3: back where Team up was
      expect(await axeSerious()).toEqual([]);

      // Inactive: a click does nothing (no sheet, no call).
      const before = calls.length;
      await click(requested);
      expect(calls.length).toBe(before);
      expect(sheet()).toBeNull();
    });

    it(`V-ACC DEC-126 (4) (${device}): Withdraw on the card turns it back to Team up where it stands, focused; the order is unchanged`, async () => {
      answerTeamUp();
      answerWithdraw("req-1");
      await showHome([A, B, C], device);
      await sendOnA();
      await click(Array.from(sheet()!.querySelectorAll("button")).find((b) => text(b) === "Done"));
      await frames();

      const withdraw = button(WITHDRAW_A)!;
      withdraw.focus();
      await click(withdraw);
      await frames();
      expect(posts()).toEqual([`POST /api/ideas/${A.id}/team-up`, "DELETE /api/team-up/req-1"]);
      expect(order()).toEqual([B.title, C.title, A.title]);
      expect(text(crewSection())).toContain("Idea 3 of 3");
      const teamUp = button(TEAM_UP_A)!;
      expect(teamUp).toBeTruthy();
      expect(text(teamUp)).toBe("Team up");
      expect(teamUp.hasAttribute("aria-disabled")).toBe(false);
      expect(teamUp.getAttribute("data-teamup-opener")).toBe(A.id);
      expect(front()!.contains(teamUp)).toBe(true);
      expect(document.activeElement).toBe(teamUp);
      expect(button(REQUESTED_A)).toBeUndefined();
      expect(button(WITHDRAW_A)).toBeUndefined();
      expect(await axeSerious()).toEqual([]);
    });

    it(`V-ACC DEC-126 (2), BLD-F094 (${device}): after a reload a card that arrives with its request, last, draws Requested; Withdraw keeps it where it is`, async () => {
      answerWithdraw("mr-3", "merge");
      await showHome([B, { ...A, request: { id: "mr-3", kind: "merge" } }], device);
      expect(order()).toEqual([B.title, A.title]);
      expect(text(crewSection())).toContain("Idea 1 of 2");
      expect(await axeSerious()).toEqual([]);

      await click(button("Next idea"));
      expect(text(front())).toContain(A.title);
      expectRequested(button(REQUESTED_A));
      expect(await axeSerious()).toEqual([]);

      const withdraw = button(WITHDRAW_A)!;
      withdraw.focus();
      await click(withdraw);
      await frames();
      // Either kind withdraws through the same call (BLD-F038).
      expect(posts()).toEqual(["DELETE /api/team-up/mr-3"]);
      expect(order()).toEqual([B.title, A.title]);
      expect(document.activeElement).toBe(button(TEAM_UP_A));
      expect(front()!.contains(button(TEAM_UP_A)!)).toBe(true);
    });
  });
}

describe("S-03 crew card and the team-up sheet (DEC-126, BLD-C219)", () => {
  it("C-SHEET-TEAMUP: Withdraw request in the sheet turns the card back to Team up where it stands, and focus comes back to it", async () => {
    answerTeamUp();
    answerWithdraw("req-1");
    await showHome([A, B, C]);
    await sendOnA();
    await click(buttons().find((b) => text(b).startsWith("Withdraw request")));
    await frames();
    expect(sheet()).toBeNull();
    expect(posts()).toEqual([`POST /api/ideas/${A.id}/team-up`, "DELETE /api/team-up/req-1"]);
    expect(order()).toEqual([B.title, C.title, A.title]);
    const teamUp = button(TEAM_UP_A)!;
    expect(teamUp).toBeTruthy();
    expect(front()!.contains(teamUp)).toBe(true);
    expect(document.activeElement).toBe(teamUp);
    expect(button(REQUESTED_A)).toBeUndefined();
  });

  it("a card that is already last stays last after a send; the deck shows it", async () => {
    answerTeamUp();
    await showHome([B, A]);
    await click(button("Next idea"));
    await sendOnA();
    expect(order()).toEqual([B.title, A.title]);
    expect(text(crewSection())).toContain("Idea 2 of 2");
    expect(text(front())).toContain(A.title);
  });
});

describe("requestedLast and requestDropped (DEC-126 (2), (4); BLD-C219)", () => {
  const sent = { ideaId: A.id, id: "req-1", kind: "teamup" as const };

  it("requestedLast puts the card asked about last with its request; the others keep their order", () => {
    const top = requestedLast([A, B, C], sent);
    expect(top.map((c) => c.id)).toEqual([B.id, C.id, A.id]);
    expect(top[2]!.request).toEqual({ id: "req-1", kind: "teamup" });
    expect(top[0]).toBe(B);
    expect(A.request).toBeUndefined(); // the card read is not changed
  });

  it("requestedLast leaves the deck as it is when the card is not in it", () => {
    const deck = [B, C];
    expect(requestedLast(deck, sent)).toBe(deck);
  });

  it("requestDropped drops the request in place; nothing moves", () => {
    const deck = [B, C, { ...A, request: { id: "req-1", kind: "teamup" as const } }];
    const top = requestDropped(deck, A.id);
    expect(top.map((c) => c.id)).toEqual([B.id, C.id, A.id]);
    expect(top[2]!.request).toBeUndefined();
    expect(top[0]).toBe(B);
    expect(requestDropped([B, C], A.id)).toEqual([B, C]);
  });
});

describe("Home's styles for the requested card (BLD-D019, BLD-C219)", () => {
  const read = (rel: string) => readFileSync(path.resolve(__dirname, "../../src", rel), "utf8");

  it("Requested and Withdraw take lane D's shared classes; Home keeps no scoped copy of them", () => {
    const home = read("app/home/home.css");
    expect(home).not.toMatch(/\.(link-quiet|is-inactive|tu-req)\b/);
    expect(read("app/offer.css")).toMatch(/\n\.link-quiet \{/);
    expect(read("app/offer.css")).toMatch(/\n\.btn\.is-inactive,/);
    expect(read("components/teamup/teamup-sheet.css")).toMatch(/\n\.tu-req \{/);
  });

  it("the Ones' companion rules lane D's BLD-D020 left unused are gone from home.css", () => {
    expect(read("app/home/home.css")).not.toMatch(/\.hm-o-(next|nt|np|more)\b/);
  });
});
