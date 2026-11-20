// @vitest-environment jsdom
/**
 * S-H2, Find your crew (lane F; L-CREW/5–9, C-CREW-DECK, V-ACC.teamup/8, J-TEAMUP/1–2): the deck from GET /api/crew,
 * Next as a pass and Previous as its undo, the end of the deck with "See them again" and "Undo last pass", nothing
 * yet, the filter panel with live counts and the chips, "Your crews", and Team up through the sheet with "Keep
 * looking". Also lane D's Deck with and without the optional `onPastEnd` (BLD-F036). Copy from reference/copy/Crew.md.
 * Synthetic people only: the pack's fictional cast (Kavya asks, Ravi leads) and made-up colleagues.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/motion/spark", () => ({ sparkBurst: vi.fn() }));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: ({ href, children, ...rest }: { href: string; children?: unknown }) =>
      h("a", { href, ...rest }, children as never),
  };
});

const { CREW_COPY, CrewScreen, crewUrl, filtersFrom, leadFirst, statusLabel } =
  await import("@/app/crew/crew-screen");
const { Deck } = await import("@/components/ui/deck");

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// --- Fixtures (synthetic) --------------------------------------------------------------------------------------
const RAVI = {
  id: "p-ravi",
  name: "Ravi Nair",
  first_name: "Ravi",
  initials: "RN",
  area: "Investor service",
};
const SANJAY = {
  id: "p-sanjay",
  name: "Sanjay Pillai",
  first_name: "Sanjay",
  initials: "SP",
  area: "Operations",
};
const DIVYA = {
  id: "p-divya",
  name: "Divya Shah",
  first_name: "Divya",
  initials: "DS",
  area: "Investor service",
};
const KAVYA = { id: "p-kavya", name: "Kavya Iyer", first_name: "Kavya", initials: "KI" };

function card(id: string, title: string, lead: typeof RAVI, extra: Record<string, unknown> = {}) {
  return {
    id,
    title,
    status: "with_review_desk",
    area: lead.area,
    city: "Hyderabad",
    shared_at: "2026-11-14T10:00:00+05:30",
    lead,
    crew_faces: [lead],
    crew_count: 4,
    in_their_words: "Investors get a code, not a reason, and then they call us.",
    looking_for: "Someone who takes these calls at a branch every day.",
    hue: 1,
    reason_kind: "close_to_yours",
    reason: "Same R07 SMS as your idea from Saturday",
    ...extra,
  };
}
const C1 = card("IDEA-2026-001412", "Rejection SMS codes confuse investors", RAVI);
const C2 = card("IDEA-2026-001415", "No script for calls about rejections", SANJAY, {
  status: "picked",
  city: "Mumbai",
  reason_kind: "close_to_yours",
  reason: "The calls your idea is about",
});
const C3 = card("IDEA-2026-001420", "Branch queue times are not tracked anywhere", DIVYA, {
  status: "checking",
  city: "Chennai",
  reason_kind: "same_area",
  reason: "Your area, Investor service",
  looking_for: undefined,
});

const GROUPS = [
  {
    key: "location",
    label: "Location",
    options: [
      { value: "Hyderabad", label: "Hyderabad", count: 1, active: false },
      { value: "Mumbai", label: "Mumbai", count: 1, active: false },
    ],
  },
  { key: "category", label: "Category", options: [] },
  { key: "status", label: "Idea status", options: [] },
  { key: "team_size", label: "Team size", options: [] },
  { key: "looking_for", label: "Looking for", options: [] },
];

function deckBody(items = [C1, C2, C3], extra: Record<string, unknown> = {}) {
  return {
    items,
    total: items.length,
    counts: {},
    filters: GROUPS,
    active: [],
    deck_total: items.length,
    state: items.length ? "cards" : "everyone_seen",
    joined: 0,
    pending: 0,
    passed: 0,
    asked: 0,
    last_passed: null,
    your_crews: { items: [], teamed_link: "/my-ideas?list=teamed" },
    ...extra,
  };
}

// --- A fetch that answers by method and path -------------------------------------------------------------------
type Answer = { status?: number; body?: unknown; wait?: Promise<void> };
let routes: Record<string, Answer | ((body: unknown) => Answer)> = {};
let calls: { key: string; body: unknown }[] = [];

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const key = `${init.method ?? "GET"} ${url}`;
      const body = typeof init.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
      calls.push({ key, body });
      const route = routes[key];
      const a: Answer = typeof route === "function" ? route(body) : (route ?? { status: 404, body: {} });
      if (a.wait) await a.wait;
      const status = a.status ?? 200;
      return { ok: status >= 200 && status < 300, status, json: () => Promise.resolve(a.body) };
    }),
  );
}
const posts = () => calls.filter((c) => !c.key.startsWith("GET ")).map((c) => c.key);

let host: HTMLElement;
let root: Root;

beforeEach(() => {
  calls = [];
  routes = {
    "GET /api/crew": { body: deckBody() },
    "POST /api/crew/pass": (b) => ({ body: { passed: 1, last_passed: (b as { idea_id: string }).idea_id } }),
    "POST /api/crew/pass/undo": { body: { passed: 0, last_passed: null, restored: C1.id, card: C1 } },
    "POST /api/crew/pass/reset": { body: { reset: 3, passed: 0, last_passed: null } },
  };
  mockFetch();
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = "";
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

async function settle() {
  for (let i = 0; i < 3; i++) {
    await act(async () => {
      await new Promise((r) => setTimeout(r, 0));
    });
  }
}

async function mount() {
  await act(async () => root.render(createElement(CrewScreen)));
  await settle();
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const page = () => text(document.body);
function nameOf(el: Element): string {
  return el.getAttribute("aria-label") ?? text(el);
}
const buttons = () => Array.from(document.querySelectorAll<HTMLButtonElement>("button"));
const button = (name: string) => buttons().find((b) => nameOf(b) === name);
const links = () => Array.from(document.querySelectorAll<HTMLAnchorElement>("a"));
/** The card in front: the only one not hidden from screen readers. */
const front = () =>
  Array.from(document.querySelectorAll<HTMLElement>(".dcard")).find(
    (d) => d.getAttribute("aria-hidden") !== "true",
  );
async function click(el: Element | undefined) {
  expect(el, "element to click").toBeTruthy();
  await act(async () => (el as HTMLElement).click());
  await settle();
}

/** Every card in the pile, in deck order, by title (only the front one is in the reading order). */
const slots = () => Array.from(document.querySelectorAll<HTMLElement>(".dcard"));
const slotTitles = () => slots().map((d) => text(d.querySelector(".crew-tb")));
/** Let requestAnimationFrame callbacks run (focus moves after the deck redraws). */
async function frames() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 40));
  });
}

/** The team-up sheet's calls for C1, answered here: a send makes request req-1, waiting for Ravi. */
function answerTeamUp() {
  routes[`GET /api/ideas/${C1.id}/team-up`] = {
    body: {
      idea_id: C1.id,
      lead: RAVI,
      me: null,
      crew_count: 4,
      can_request: true,
      why_not: null,
      request: null,
      after: null,
    },
  };
  routes[`GET /api/ideas/${C1.id}/team-up/draft-note`] = {
    body: {
      note: "I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07.",
      own_ideas: [],
      idea: { id: C1.id, title: C1.title },
      lead: RAVI,
      min_chars: 30,
      max_chars: 600,
    },
  };
  routes["GET /api/me"] = {
    body: { name: "Kavya Iyer", email: "kavya@example.test", contributor_code: "CTR-0a1b2c" },
  };
  routes[`POST /api/ideas/${C1.id}/team-up`] = (b) => ({
    status: 201,
    body: {
      id: "req-1",
      request: "teamup",
      idea_id: C1.id,
      from: KAVYA,
      note: (b as { note: string }).note,
      brought: [],
      state: "sent",
      sent_at: "2026-11-18T10:30:00+05:30",
      after: { state: "waiting", line: "Waiting for Ravi", action: { label: "Withdraw", op: "withdraw" } },
    },
  });
}

// --- Pure helpers ----------------------------------------------------------------------------------------------
describe("S-H2 helpers (L-CREW/5)", () => {
  it("crewUrl keeps the panel's key order and repeats a key per value", () => {
    expect(crewUrl({})).toBe("/api/crew");
    expect(crewUrl({ status: ["picked"], location: ["Hyderabad", "Pune"] })).toBe(
      "/api/crew?location=Hyderabad&location=Pune&status=picked",
    );
    expect(
      filtersFrom([
        { key: "location", value: "Pune", label: "Pune" },
        { key: "location", value: "Hyderabad", label: "Hyderabad" },
      ]),
    ).toEqual({ location: ["Pune", "Hyderabad"] });
  });

  it("a lead who hid their name is 'the lead' in a sentence (BLD-F042)", () => {
    expect(leadFirst({ first_name: "Ravi", initials: "RN" })).toBe("Ravi");
    expect(leadFirst({ first_name: "A colleague", initials: "" })).toBe("the lead");
    expect(CREW_COPY.teamUpOn("Rejection SMS codes confuse investors", "the lead")).toBe(
      "Team up on Rejection SMS codes confuse investors: send the lead a note",
    );
  });

  it("a just-shared idea reads Shared on the card (BLD-F030); the rest keep their status words", () => {
    expect(statusLabel("checking")).toBe("Shared");
    expect(statusLabel("with_review_desk")).toBe("With the review desk");
    expect(statusLabel("picked")).toBe("Picked");
  });

  it("the words that count", () => {
    expect(CREW_COPY.count(5)).toBe("5 ideas close to yours");
    expect(CREW_COPY.count(1)).toBe("1 idea close to yours");
    expect(CREW_COPY.show(2)).toBe("Show 2 ideas");
    expect(CREW_COPY.endBody(1)).toBe(
      "You asked to team up on 1 idea. New ideas close to yours show up here.",
    );
    expect(CREW_COPY.endBody(0)).toBe("New ideas close to yours show up here.");
    expect(
      CREW_COPY.crewRow("Rejection SMS codes confuse investors", {
        state: "waiting",
        label: "Waiting for Ravi",
      }),
    ).toBe("Rejection SMS codes confuse investors, waiting for Ravi. Open the idea.");
    expect(
      CREW_COPY.crewRow("Rejection SMS codes confuse investors", { state: "on_crew", label: "On the crew" }),
    ).toBe("Rejection SMS codes confuse investors, you’re on the crew. Open the idea.");
  });
});

// --- The screen --------------------------------------------------------------------------------------------------
describe("S-H2 Find your crew", () => {
  it("S-H2.layout, C-CREW-DECK.card: title, count, the front card with its reason, Team up for the lead, the side card", async () => {
    await mount();
    expect(text(document.querySelector("h1"))).toBe("Find your crew");
    expect(page()).toContain("Ideas close to yours. Team up, or pass.");
    expect(page()).toContain("3 ideas close to yours");
    const f = front()!;
    expect(text(f)).toContain("With the review desk");
    expect(text(f)).toContain("Rejection SMS codes confuse investors");
    expect(text(f)).toContain("Investor service, Hyderabad");
    expect(text(f)).toContain("Same R07 SMS as your idea from Saturday");
    expect(text(f)).toContain("The problem, in their words");
    expect(text(f)).toContain("They're looking for");
    expect(text(f)).toContain("Ravi Nair and 3 others on it");
    expect(button("Team up on Rejection SMS codes confuse investors: send Ravi a note")).toBeTruthy();
    expect(page()).toContain("Idea 1 of 3");
    expect(text(document.querySelector("aside"))).toContain("Your crews");
    expect(page()).toContain("Ideas you team up on show here.");
    expect(page()).toContain("None passed");
    expect(
      links()
        .find((a) => text(a) === "All your crews in My ideas")
        ?.getAttribute("href"),
    ).toBe("/my-ideas?list=teamed");
    expect(calls[0]?.key).toBe("GET /api/crew");
  });

  it("L-CREW/6: Next passes the front card; Previous brings it back with an undo", async () => {
    await mount();
    await click(button("Next idea"));
    expect(posts()).toEqual(["POST /api/crew/pass"]);
    expect(calls.find((c) => c.key === "POST /api/crew/pass")?.body).toEqual({ idea_id: C1.id });
    expect(text(front())).toContain("No script for calls about rejections");
    expect(page()).toContain("1 passed");
    expect(page()).toContain("Idea 2 of 3");

    await click(button("Previous idea"));
    expect(posts()).toEqual(["POST /api/crew/pass", "POST /api/crew/pass/undo"]);
    expect(text(front())).toContain("Rejection SMS codes confuse investors");
    expect(page()).toContain("None passed");
  });

  it("V-ACC.teamup/8: passing every card ends the deck with counts, See them again and Undo last pass", async () => {
    routes["GET /api/crew"] = { body: deckBody(undefined, { asked: 1 }) };
    let n = 0;
    routes["POST /api/crew/pass"] = (b) => ({
      body: { passed: ++n, last_passed: (b as { idea_id: string }).idea_id },
    });
    routes["POST /api/crew/pass/undo"] = {
      body: { passed: 2, last_passed: C2.id, restored: C3.id, card: C3 },
    };
    await mount();
    expect(text(front())).toContain("Rejection SMS codes confuse investors");
    await click(button("Next idea"));
    await click(button("Next idea"));
    // The last card: Next stays available and ends the deck (BLD-F036).
    expect(button("Next idea")?.getAttribute("aria-disabled")).toBeNull();
    await click(button("Next idea"));
    expect(posts()).toEqual(["POST /api/crew/pass", "POST /api/crew/pass", "POST /api/crew/pass"]);
    const end = document.querySelector('.crew-end[role="status"]');
    expect(text(end)).toContain("That's everyone for now");
    expect(text(end)).toContain("You asked to team up on 1 idea. New ideas close to yours show up here.");
    expect(button("See them again")).toBeTruthy();
    expect(page()).toContain("3 passed");

    await click(button("Undo last pass"));
    expect(posts().at(-1)).toBe("POST /api/crew/pass/undo");
    expect(text(front())).toContain("Branch queue times are not tracked anywhere");
    expect(text(front())).toContain("Shared");
    expect(page()).toContain("2 passed");
  });

  it("L-CREW/6: See them again resets every pass and deals the deck again", async () => {
    routes["GET /api/crew"] = { body: deckBody([], { state: "everyone_seen", passed: 5, asked: 1 }) };
    await mount();
    expect(page()).toContain("That's everyone for now");
    expect(page()).toContain("5 passed");
    routes["GET /api/crew"] = { body: deckBody() };
    await click(button("See them again"));
    expect(posts()).toEqual(["POST /api/crew/pass/reset"]);
    expect(calls.filter((c) => c.key === "GET /api/crew")).toHaveLength(2);
    expect(text(front())).toContain("Rejection SMS codes confuse investors");
    expect(page()).toContain("None passed");
  });

  it("L-CREW/8: nothing yet, with Browse the Wall and no Filters", async () => {
    routes["GET /api/crew"] = { body: deckBody([], { state: "nothing_yet" }) };
    await mount();
    const zero = document.querySelector('.crew-end[role="status"]');
    expect(text(zero)).toContain("No crews to join yet");
    expect(text(zero)).toContain(
      "We look for ideas close to the problems you've shared. Share one and we'll show you people working on the same thing, or browse the Wall for ideas you can help with.",
    );
    expect(
      links()
        .find((a) => text(a) === "Browse the Wall")
        ?.getAttribute("href"),
    ).toBe("/wall");
    expect(button("Filters")).toBeUndefined();
  });

  it("a deck that did not load says so and tries again", async () => {
    routes["GET /api/crew"] = { status: 503, body: {} };
    await mount();
    expect(text(document.querySelector('[role="alert"]'))).toContain("These ideas did not load");
    routes["GET /api/crew"] = { body: deckBody() };
    await click(button("Try again"));
    expect(text(front())).toContain("Rejection SMS codes confuse investors");
  });

  it("L-CREW/5: the filter panel counts live, Show N ideas applies, the chip removes it", async () => {
    await mount();
    const filters = button("Filters")!;
    expect(filters.getAttribute("aria-expanded")).toBe("false");
    expect(filters.getAttribute("aria-haspopup")).toBe("dialog");
    await click(filters);
    const panel = document.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(text(document.getElementById(panel.getAttribute("aria-labelledby")!))).toBe("Filter ideas");
    expect(document.activeElement).toBe(button("Close filters"));
    const hyd = Array.from(panel.querySelectorAll("button")).find((b) => text(b).startsWith("Hyderabad"))!;
    expect(hyd.getAttribute("aria-pressed")).toBe("false");

    const one = {
      ...deckBody([C1]),
      active: [{ key: "location", value: "Hyderabad", label: "Hyderabad" }],
      filters: [
        { ...GROUPS[0], options: [{ ...GROUPS[0]!.options[0], active: true }, GROUPS[0]!.options[1]] },
        ...GROUPS.slice(1),
      ],
    };
    routes["GET /api/crew?location=Hyderabad"] = { body: one };
    await click(hyd);
    expect(calls.at(-1)?.key).toBe("GET /api/crew?location=Hyderabad");
    expect(text(panel.querySelector('[role="status"]'))).toBe("1 idea matches");
    await click(button("Show 1 idea"));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(page()).toContain("1 idea close to yours");
    const withCount = buttons().find((b) => b.getAttribute("aria-haspopup") === "dialog");
    expect(text(withCount)).toBe("Filters1");
    expect(text(front())).toContain("Rejection SMS codes confuse investors");

    await click(button("Remove filter: Hyderabad"));
    expect(calls.at(-1)?.key).toBe("GET /api/crew");
    expect(page()).toContain("3 ideas close to yours");
  });

  it("only the latest read changes the deck: an older answer that comes back last is ignored", async () => {
    let n = 0;
    let release: () => void = () => undefined;
    const late = new Promise<void>((r) => {
      release = r;
    });
    routes["GET /api/crew"] = () => {
      n += 1;
      if (n === 1)
        return {
          body: { ...deckBody([C1]), active: [{ key: "location", value: "Hyderabad", label: "Hyderabad" }] },
        };
      if (n === 2) return { wait: late, body: deckBody([C2]) };
      return { body: deckBody() };
    };
    await mount();
    expect(page()).toContain("1 idea close to yours");
    await click(button("Remove filter: Hyderabad")); // its answer is held back
    await click(buttons().find((b) => text(b) === "Clear all" && b.closest(".crew-fact")));
    expect(page()).toContain("3 ideas close to yours");
    release();
    await settle();
    expect(page()).toContain("3 ideas close to yours");
    expect(text(front())).toContain("Rejection SMS codes confuse investors");
  });

  it("L-CREW/9: Your crews lists the lead, the state and the idea link", async () => {
    routes["GET /api/crew"] = {
      body: deckBody(undefined, {
        your_crews: {
          items: [
            {
              id: "IDEA-2026-001399",
              title: "Nominee updates bounce between two teams",
              status: "with_review_desk",
              lead: RAVI,
              state: "waiting",
              label: "Waiting for Ravi",
              request_id: "req-9",
              at: "2026-11-17T10:00:00+05:30",
            },
          ],
          teamed_link: "/my-ideas?list=teamed",
        },
      }),
    };
    await mount();
    const row = links().find((a) => a.getAttribute("href") === "/ideas/IDEA-2026-001399")!;
    expect(row.getAttribute("aria-label")).toBe(
      "Nominee updates bounce between two teams, waiting for Ravi. Open the idea.",
    );
    expect(text(row.closest("li"))).toContain("Ravi Nair, Investor service");
    expect(text(row.closest("li"))).toContain("Waiting for Ravi");
    // The link shows only the title, so its label starts with what is seen (axe label-content-name-mismatch).
    expect(text(row)).toBe("Nominee updates bounce between two teams");
    expect(page()).not.toContain("Ideas you team up on show here.");
  });

  it("J-TEAMUP/1–2, DEC-126: Team up sends through the sheet; the card reads Requested, Keep looking sends it to the end, Your crews lists it", async () => {
    answerTeamUp();
    await mount();
    await click(button("Team up on Rejection SMS codes confuse investors: send Ravi a note"));
    const sheet = document.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(sheet).toBeTruthy();
    await click(Array.from(sheet.querySelectorAll("button")).find((b) => text(b).startsWith("Send to Ravi")));
    expect(posts()).toEqual([`POST /api/ideas/${C1.id}/team-up`]);
    expect(page()).toContain("Sent to Ravi");
    await click(button("Keep looking"));
    await frames();
    // Nothing is passed; the card asked about goes to the end of the deck and the next card comes to the front,
    // with focus on it (WCAG 2.4.3). The request is in Your crews, "Waiting for Ravi" (DEC-126 (5)).
    expect(posts()).toEqual([`POST /api/ideas/${C1.id}/team-up`]);
    expect(text(front())).toContain("No script for calls about rejections");
    expect(page()).toContain("Idea 1 of 3");
    expect(document.activeElement).toBe(button("No script for calls about rejections. Preview the idea"));
    expect(slotTitles()).toEqual([C2.title, C3.title, C1.title]);
    const row = links().find((a) => a.getAttribute("href") === `/ideas/${C1.id}`)!;
    expect(row.getAttribute("aria-label")).toBe(
      "Rejection SMS codes confuse investors, waiting for Ravi. Open the idea.",
    );
    expect(text(row.closest("li"))).toContain("Ravi Nair, Investor service");
    // At the end it reads Requested: greyed, inactive but focusable and read out, marked as where Team up was.
    const last = slots()[2]!;
    const requested = last.querySelector<HTMLButtonElement>("[data-teamup-opener]")!;
    expect(text(requested)).toBe("Requested");
    expect(requested.getAttribute("aria-disabled")).toBe("true");
    expect(requested.hasAttribute("disabled")).toBe(false);
    expect(requested.classList.contains("is-inactive")).toBe(true);
    expect(requested.getAttribute("aria-label")).toBe(
      "Requested: you asked to team up on Rejection SMS codes confuse investors",
    );
    const withdraw = last.querySelector<HTMLButtonElement>(".link-quiet")!;
    expect(text(withdraw)).toBe("Withdraw");
    expect(withdraw.getAttribute("aria-label")).toBe(
      "Withdraw your request to team up on Rejection SMS codes confuse investors",
    );
    expect(requested.contains(withdraw)).toBe(false);
  });

  it("DEC-126: Next on a card just asked about only moves on, at the end of the deck too (no pass)", async () => {
    answerTeamUp();
    await mount();
    await click(button("Team up on Rejection SMS codes confuse investors: send Ravi a note"));
    const sheet = document.querySelector<HTMLElement>('[role="dialog"]')!;
    await click(Array.from(sheet.querySelectorAll("button")).find((b) => text(b).startsWith("Send to Ravi")));
    await click(button("Keep looking"));
    await click(button("Next idea"));
    await click(button("Next idea"));
    expect(page()).toContain("Idea 3 of 3");
    expect(text(front())).toContain(C1.title);
    const before = posts().length;
    await click(button("Next idea"));
    expect(posts().slice(before)).toEqual([]);
    expect(page()).toContain("That's everyone for now");
    expect(page()).toContain("You asked to team up on 1 idea.");
  });

  it("DEC-126: with reduced motion the card just moves; otherwise a copy of it flies to the back, out of reach", async () => {
    for (const reduce of [false, true]) {
      vi.stubGlobal(
        "matchMedia",
        vi.fn((q: string) => ({ matches: reduce && q.includes("reduce"), media: q })),
      );
      answerTeamUp();
      await mount();
      await click(button("Team up on Rejection SMS codes confuse investors: send Ravi a note"));
      const sheet = document.querySelector<HTMLElement>('[role="dialog"]')!;
      await click(
        Array.from(sheet.querySelectorAll("button")).find((b) => text(b).startsWith("Send to Ravi")),
      );
      await click(button("Keep looking"));
      const fly = document.querySelector<HTMLElement>(".crew-fly");
      expect(slotTitles()).toEqual([C2.title, C3.title, C1.title]);
      if (reduce) {
        expect(fly).toBeNull();
      } else {
        expect(fly).toBeTruthy();
        expect(fly!.getAttribute("aria-hidden")).toBe("true");
        expect(fly!.hasAttribute("inert")).toBe(true);
        expect(fly!.closest(".dcard")).toBe(front());
        expect(text(fly)).toContain("Requested");
        expect(fly!.querySelectorAll("[data-teamup-opener], a, button:not(.crew-tb)").length).toBe(0);
        await act(async () => {
          await new Promise((r) => setTimeout(r, 950));
        });
        expect(document.querySelector(".crew-fly")).toBeNull();
      }
      await act(async () => root.unmount());
      document.body.innerHTML = "";
      host = document.createElement("div");
      document.body.append(host);
      root = createRoot(host);
      calls = [];
    }
  });

  it("DEC-126 after a reload: a requested card reads Requested; Withdraw turns it back to Team up in place, focus on Team up, Your crews drops it", async () => {
    const C1R = { ...C1, request: { id: "req-9", kind: "teamup" } };
    routes["GET /api/crew"] = {
      body: deckBody([C2, C1R], {
        asked: 1,
        pending: 1,
        your_crews: {
          items: [
            {
              id: C1.id,
              title: C1.title,
              status: "with_review_desk",
              lead: RAVI,
              state: "waiting",
              label: "Waiting for Ravi",
              request_id: "req-9",
              at: "2026-11-17T10:00:00+05:30",
            },
          ],
          teamed_link: "/my-ideas?list=teamed",
        },
      }),
    };
    routes["DELETE /api/team-up/req-9"] = {
      body: { id: "req-9", request: "teamup", idea_id: C1.id, state: "withdrawn", after: null },
    };
    await mount();
    expect(slotTitles()).toEqual([C2.title, C1.title]);
    await click(button("Next idea"));
    expect(text(front())).toContain(C1.title);
    const requested = button("Requested: you asked to team up on Rejection SMS codes confuse investors")!;
    expect(requested.getAttribute("aria-disabled")).toBe("true");
    // Inactive: a click does nothing (no sheet, no call).
    const before = calls.length;
    await click(requested);
    expect(calls.length).toBe(before);
    expect(document.querySelector('[role="dialog"]')).toBeNull();

    const withdraw = button("Withdraw your request to team up on Rejection SMS codes confuse investors")!;
    withdraw.focus();
    await click(withdraw);
    await frames();
    expect(posts()).toEqual(["POST /api/crew/pass", "DELETE /api/team-up/req-9"]);
    // Back to Team up, where it stands (still the last card, still in front), with focus on it.
    expect(page()).toContain("Idea 2 of 2");
    const teamUp = button("Team up on Rejection SMS codes confuse investors: send Ravi a note")!;
    expect(teamUp).toBeTruthy();
    expect(front()!.contains(teamUp)).toBe(true);
    expect(document.activeElement).toBe(teamUp);
    expect(slotTitles()).toEqual([C2.title, C1.title]);
    expect(links().find((a) => a.getAttribute("href") === `/ideas/${C1.id}`)).toBeUndefined();
    expect(page()).toContain("Ideas you team up on show here.");
    // Asked about no more: Next passes it now.
    await click(button("Next idea"));
    expect(posts().slice(-1)).toEqual(["POST /api/crew/pass"]);
    expect(page()).toContain("New ideas close to yours show up here.");
    expect(page()).not.toContain("You asked to team up");
  });

  it("DEC-126, BLD-F094: after a reload, Next on a requested card passes it like any other card", async () => {
    const merged = { ...C1, request: { id: "req-9", kind: "merge" } };
    routes["GET /api/crew"] = { body: deckBody([merged], { asked: 1 }) };
    await mount();
    expect(button("Requested: you asked to team up on Rejection SMS codes confuse investors")).toBeTruthy();
    await click(button("Next idea"));
    expect(calls.filter((c) => c.key === "POST /api/crew/pass").map((c) => c.body)).toEqual([
      { idea_id: C1.id },
    ]);
    expect(page()).toContain("You asked to team up on 1 idea.");
  });

  it("DEC-126: a withdraw that fails says why, and the card stays Requested", async () => {
    const asked = { ...C1, request: { id: "req-9", kind: "teamup" } };
    routes["GET /api/crew"] = { body: deckBody([asked]) };
    routes["DELETE /api/team-up/req-9"] = {
      status: 409,
      body: { error: { code: "not_waiting", message: "This request has already been answered." } },
    };
    await mount();
    await click(button("Withdraw your request to team up on Rejection SMS codes confuse investors"));
    expect(text(front()!.querySelector('[role="alert"]'))).toBe("This request has already been answered.");
    expect(button("Requested: you asked to team up on Rejection SMS codes confuse investors")).toBeTruthy();
  });

  it("C-SHEET-TEAMUP: Withdraw request in the sheet turns the card back to Team up, where it is", async () => {
    answerTeamUp();
    routes["DELETE /api/team-up/req-1"] = {
      body: { id: "req-1", request: "teamup", idea_id: C1.id, state: "withdrawn", after: null },
    };
    await mount();
    await click(button("Team up on Rejection SMS codes confuse investors: send Ravi a note"));
    const sheet = document.querySelector<HTMLElement>('[role="dialog"]')!;
    await click(Array.from(sheet.querySelectorAll("button")).find((b) => text(b).startsWith("Send to Ravi")));
    // Its busy label shares the button ("Withdrawing…"), so the text starts with the name.
    await click(buttons().find((b) => text(b).startsWith("Withdraw request")));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(slotTitles()).toEqual([C1.title, C2.title, C3.title]);
    expect(text(front())).toContain(C1.title);
    expect(button("Team up on Rejection SMS codes confuse investors: send Ravi a note")).toBeTruthy();
    expect(links().find((a) => a.getAttribute("href") === `/ideas/${C1.id}`)).toBeUndefined();
  });

  it("C-PREVIEW from a card: the title opens the preview with the card's reason", async () => {
    await mount();
    await click(button("Rejection SMS codes confuse investors. Preview the idea"));
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
    expect(dialog).toBeTruthy();
    expect(text(dialog)).toContain("Same R07 SMS as your idea from Saturday");
  });
});

// --- Lane D's Deck: the optional onPastEnd (BLD-F036) -------------------------------------------------------------
describe("C-CREW-DECK Deck onPastEnd", () => {
  const cards = [createElement("p", { key: "a" }, "A"), createElement("p", { key: "b" }, "B")];

  it("without it, Next is unavailable on the last card and does nothing (unchanged)", async () => {
    const onIndexChange = vi.fn();
    await act(async () =>
      root.render(createElement(Deck, { label: "Deck", cards, index: 1, onIndexChange })),
    );
    expect(button("Next idea")?.getAttribute("aria-disabled")).toBe("true");
    await click(button("Next idea"));
    expect(onIndexChange).not.toHaveBeenCalled();
  });

  it("with it, Next and → on the last card call it instead of moving", async () => {
    const onIndexChange = vi.fn();
    const onPastEnd = vi.fn();
    await act(async () =>
      root.render(createElement(Deck, { label: "Deck", cards, index: 1, onIndexChange, onPastEnd })),
    );
    expect(button("Next idea")?.getAttribute("aria-disabled")).toBeNull();
    await click(button("Next idea"));
    const region = document.querySelector('[role="region"]')!;
    await act(async () => {
      region.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    });
    expect(onPastEnd).toHaveBeenCalledTimes(2);
    expect(onIndexChange).not.toHaveBeenCalled();
  });
});
