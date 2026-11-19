/**
 * S-H2, Find your crew, in a real browser at phone width (lane F; L-CREW, C-CREW-DECK, V-ACC.teamup/8, J-TEAMUP/1–2):
 * the screen on the dev-only page /kit/crew, with GET /api/crew, the passes, the preview and the team-up calls
 * answered by this spec (no seeded ideas). axe on the cards, the filter panel, the end of the deck and nothing yet
 * (lane D's helper, which settles motion first and checks reflow at 320px); the deck and the filter chips by
 * keyboard; 44px targets; Keep looking after a send. DEC-126 (WF-03b): after a send the card reads "Requested" and
 * goes to the end of the deck; "Withdraw" under it (its contrast, focus ring and target measured) turns it back to
 * "Team up" in place; axe on the Requested state at 375px and at 1440px; reduced motion. Synthetic people only: the
 * pack's fictional cast (Kavya asks, Ravi leads) and made-up colleagues.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page, type Route } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, settleMotion, signIn } from "./helpers";

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
const KAVYA = { id: "p-kavya", name: "Kavya Iyer", first_name: "Kavya", initials: "KI" };

const C1 = {
  id: "IDEA-2026-001412",
  title: "Rejection SMS codes confuse investors",
  status: "with_review_desk",
  area: "Investor service",
  city: "Hyderabad",
  shared_at: "2026-11-14T10:00:00+05:30",
  lead: RAVI,
  crew_faces: [RAVI, { id: "p-as", name: "Anil Sood", first_name: "Anil", initials: "AS" }],
  crew_count: 4,
  in_their_words: "Investors get a code, not a reason, and then they call us.",
  looking_for: "Someone who takes these calls at a branch every day.",
  hue: 1,
  reason_kind: "close_to_yours",
  reason: "Same R07 SMS as your idea from Saturday",
};
const C2 = {
  ...C1,
  id: "IDEA-2026-001415",
  title: "No script for calls about rejections",
  status: "picked",
  area: "Operations",
  city: "Mumbai",
  lead: SANJAY,
  crew_faces: [SANJAY],
  crew_count: 2,
  in_their_words: "Every agent explains a rejection differently, so investors call back.",
  looking_for: "Real examples of what investors ask on these calls.",
  hue: 2,
  reason: "The calls your idea is about",
};
const GROUPS = [
  {
    key: "location",
    label: "Location",
    options: [
      { value: "Hyderabad", label: "Hyderabad", count: 1, active: false },
      { value: "Mumbai", label: "Mumbai", count: 1, active: false },
    ],
  },
  {
    key: "category",
    label: "Category",
    options: [
      { value: "Investor service", label: "Investor service", count: 1, active: false },
      { value: "Operations", label: "Operations", count: 1, active: false },
    ],
  },
  {
    key: "status",
    label: "Idea status",
    options: [
      { value: "with_review_desk", label: "With the review desk", count: 1, active: false },
      { value: "picked", label: "Picked", count: 1, active: false },
    ],
  },
  {
    key: "team_size",
    label: "Team size",
    options: [
      { value: "lead_only", label: "Just the lead", count: 0, active: false },
      { value: "two_to_three", label: "2 to 3 people", count: 1, active: false },
      { value: "four_plus", label: "4 or more", count: 1, active: false },
    ],
  },
  {
    key: "looking_for",
    label: "Looking for",
    options: [{ value: "Branch staff", label: "Branch staff", count: 1, active: false }],
  },
];

function deck(items: unknown[], extra: Record<string, unknown> = {}) {
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

/** The crew deck and its passes, answered here; `first` is what the first GET /api/crew returns. */
async function answerCrew(page: Page, first: Record<string, unknown>) {
  let passed = 0;
  await page.route(/\/api\/crew(\?.*)?$/, (route: Route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("location") === "Hyderabad") {
      return route.fulfill({
        json: {
          ...deck([C1]),
          active: [{ key: "location", value: "Hyderabad", label: "Hyderabad" }],
        },
      });
    }
    return route.fulfill({ json: first });
  });
  await page.route(/\/api\/crew\/pass(\/(undo|reset))?$/, (route: Route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/undo")) {
      passed = Math.max(0, passed - 1);
      return route.fulfill({ json: { passed, last_passed: null, restored: C2.id, card: C2 } });
    }
    if (path.endsWith("/reset")) {
      passed = 0;
      return route.fulfill({ json: { reset: 2, passed: 0, last_passed: null } });
    }
    passed += 1;
    return route.fulfill({ json: { passed, last_passed: C2.id } });
  });
}

/** The team-up sheet's calls for C1 (A-API.team-up), answered here. */
async function answerTeamUp(page: Page) {
  await page.route(`**/api/ideas/${C1.id}/team-up/draft-note`, (route) =>
    route.fulfill({
      json: {
        note: "I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07.",
        own_ideas: [],
        idea: { id: C1.id, title: C1.title },
        lead: RAVI,
        min_chars: 30,
        max_chars: 600,
      },
    }),
  );
  await page.route(`**/api/ideas/${C1.id}/team-up`, (route) => {
    const req = route.request();
    if (req.method() !== "POST") {
      return route.fulfill({
        json: {
          idea_id: C1.id,
          lead: RAVI,
          me: null,
          crew_count: 4,
          can_request: true,
          why_not: null,
          request: null,
          after: null,
        },
      });
    }
    const body = req.postDataJSON() as { note: string };
    return route.fulfill({
      status: 201,
      json: {
        id: "req-e2e",
        request: "teamup",
        idea_id: C1.id,
        from: KAVYA,
        note: body.note,
        brought: [],
        state: "sent",
        sent_at: "2026-11-18T10:30:00+05:30",
        after: { state: "waiting", line: "Waiting for Ravi", action: { label: "Withdraw", op: "withdraw" } },
      },
    });
  });
}

async function open(page: Page) {
  await page.goto("/kit/crew");
  await expect(page.getByRole("heading", { level: 1, name: "Find your crew" })).toBeAttached();
}

/** C1 as the server sends it after a reload once Kavya has asked (DEC-126): last in the deck, with its request. */
const C1_ASKED = { ...C1, request: { id: "req-e2e", kind: "teamup" } };
const ASKED_ROW = {
  id: C1.id,
  title: C1.title,
  status: C1.status,
  lead: RAVI,
  state: "waiting",
  label: "Waiting for Ravi",
  request_id: "req-e2e",
  at: "2026-11-18T10:30:00+05:30",
};
const REQUESTED = `Requested: you asked to team up on ${C1.title}`;
const WITHDRAW = `Withdraw your request to team up on ${C1.title}`;
const TEAM_UP_C1 = `Team up on ${C1.title}: send Ravi a note`;

/** `DELETE /api/team-up/req-e2e` (L-TEAMUP.rules/3), answered here; resolves with each call's method. */
async function answerWithdraw(page: Page) {
  const seen: string[] = [];
  await page.route("**/api/team-up/req-e2e", (route) => {
    seen.push(route.request().method());
    return route.fulfill({
      json: { id: "req-e2e", request: "teamup", idea_id: C1.id, state: "withdrawn", after: null },
    });
  });
  return seen;
}

/** WCAG contrast of an element's text against the first opaque background behind it. */
async function contrastOf(page: Page, name: string): Promise<number> {
  return page.getByRole("button", { name, exact: true }).evaluate((el) => {
    const rgb = (c: string) => (c.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number);
    const lum = (c: number[]) => {
      const f = (v: number) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * f(c[0] ?? 0) + 0.7152 * f(c[1] ?? 0) + 0.0722 * f(c[2] ?? 0);
    };
    let at: Element | null = el;
    let bg = "rgb(255, 255, 255)";
    while (at) {
      const c = getComputedStyle(at).backgroundColor;
      if (c && c !== "transparent" && !/rgba\(.*,\s*0\)$/.test(c)) {
        bg = c;
        break;
      }
      at = at.parentElement;
    }
    const a = lum(rgb(getComputedStyle(el).color));
    const b = lum(rgb(bg));
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  });
}

/**
 * DEC-126 on a card asked about before this visit: Requested is greyed, inactive but focusable and read out;
 * Withdraw under it is sub-text grey at 4.5:1 or better, with the shared 2px focus ring and a 44px target. axe on
 * this state. Then Withdraw turns it back to Team up where it stands, with focus on it, and Your crews drops it.
 */
async function requestedThenWithdraw(page: Page) {
  const seen = await answerWithdraw(page);
  await answerCrew(
    page,
    deck([C2, C1_ASKED], {
      asked: 1,
      pending: 1,
      your_crews: { items: [ASKED_ROW], teamed_link: "/my-ideas?list=teamed" },
    }),
  );
  await open(page);
  await page.getByRole("button", { name: "Next idea" }).click();
  await expect(page.getByText("Idea 2 of 2")).toBeAttached();
  const requested = page.getByRole("button", { name: REQUESTED, exact: true });
  await expect(requested).toBeVisible();
  await expect(requested).toHaveAttribute("aria-disabled", "true");
  await expect(requested).not.toHaveAttribute("disabled");
  await expect(requested).toHaveText("Requested");
  // Inactive: a click opens nothing (dispatched: Playwright waits for an aria-disabled button to be enabled).
  await requested.dispatchEvent("click");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  const withdraw = page.getByRole("button", { name: WITHDRAW, exact: true });
  await expect(withdraw).toHaveText("Withdraw");
  expect(await contrastOf(page, WITHDRAW)).toBeGreaterThanOrEqual(4.5);
  const look = await withdraw.evaluate((el) => {
    const c = getComputedStyle(el);
    return { line: c.textDecorationLine, size: parseFloat(c.fontSize), weight: c.fontWeight };
  });
  expect(look.line).toContain("underline");
  expect(look.size).toBeLessThanOrEqual(14);
  expect(Number(look.weight)).toBeLessThanOrEqual(400);
  const box = (await withdraw.boundingBox())!;
  expect(box.height).toBeGreaterThanOrEqual(44);
  expect(box.width).toBeGreaterThanOrEqual(44);
  // By keyboard: Requested is a tab stop, then Withdraw, with the visible focus ring.
  await requested.focus();
  await expect(requested).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(withdraw).toBeFocused();
  const ring = await withdraw.evaluate((el) => {
    const c = getComputedStyle(el);
    return { style: c.outlineStyle, width: parseFloat(c.outlineWidth) };
  });
  expect(ring).toEqual({ style: "solid", width: 2 });
  await expect(
    page.getByRole("link", { name: `${C1.title}, waiting for Ravi. Open the idea.` }),
  ).toBeVisible();
  await expectNoSeriousAxeIssues(page);

  await page.keyboard.press("Enter");
  const teamUp = page.getByRole("button", { name: TEAM_UP_C1 });
  await expect(teamUp).toBeFocused();
  expect(seen).toEqual(["DELETE"]);
  await expect(page.getByText("Idea 2 of 2")).toBeAttached();
  await expect(page.getByRole("button", { name: REQUESTED })).toHaveCount(0);
  await expect(page.getByRole("link", { name: `${C1.title}, waiting for Ravi. Open the idea.` })).toHaveCount(
    0,
  );
  await expect(page.getByText("Ideas you team up on show here.")).toBeVisible();
}

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "the viewport is set here; one project is enough");
  await signIn(page, PERSONAS.contributor);
});

test("S-H2 cards at 375px: the front card in words, 44px targets, axe; Next passes, Previous brings it back (L-CREW/6)", async ({
  page,
}) => {
  await answerCrew(page, deck([C1, C2]));
  await answerTeamUp(page);
  await open(page);
  const region = page.getByRole("region", { name: "Ideas close to yours" });
  await expect(region).toContainText("Same R07 SMS as your idea from Saturday");
  await expect(page.getByText("2 ideas close to yours")).toBeVisible();
  await expect(page.getByText("Idea 1 of 2")).toBeAttached();
  await settleMotion(page);
  for (const name of [
    "Team up on Rejection SMS codes confuse investors: send Ravi a note",
    "Next idea",
    "Previous idea",
    "Filters",
  ]) {
    const b = (await page.getByRole("button", { name, exact: true }).boundingBox())!;
    expect(b.height, name).toBeGreaterThanOrEqual(44);
    expect(b.width, name).toBeGreaterThanOrEqual(44);
  }
  await expectNoSeriousAxeIssues(page);

  // Next passes the front card and the next one is in front; only the front card is in the reading order.
  const pass = page.waitForRequest((r) => r.url().endsWith("/api/crew/pass") && r.method() === "POST");
  await page.getByRole("button", { name: "Next idea" }).click();
  expect((await pass).postDataJSON()).toEqual({ idea_id: C1.id });
  await expect(page.getByText("Idea 2 of 2")).toBeAttached();
  await expect(
    page.getByRole("button", { name: "Team up on No script for calls about rejections: send Sanjay a note" }),
  ).toBeVisible();
  await expect(page.getByText("1 passed")).toBeVisible();

  // ← goes back: the card passed last comes out again, and its pass is undone.
  const undo = page.waitForRequest((r) => r.url().endsWith("/api/crew/pass/undo"));
  await region.getByRole("button", { name: "Previous idea" }).focus();
  await page.keyboard.press("ArrowLeft");
  await undo;
  await expect(page.getByText("Idea 1 of 2")).toBeAttached();
  await expect(page.getByText("None passed")).toBeVisible();
});

test("V-ACC.teamup/8 at 375px: passing every card ends the deck with counts, See them again and Undo last pass; axe", async ({
  page,
}) => {
  await answerCrew(page, deck([C1, C2], { asked: 1 }));
  await open(page);
  await page.getByRole("button", { name: "Next idea" }).click();
  await page.getByRole("button", { name: "Next idea" }).click();
  const end = page.getByRole("status").filter({ hasText: "That's everyone for now" });
  await expect(end).toContainText("You asked to team up on 1 idea. New ideas close to yours show up here.");
  await expect(page.getByRole("button", { name: "See them again" })).toBeVisible();
  await expect(page.getByText("2 passed")).toBeVisible();
  await expectNoSeriousAxeIssues(page);

  await page.getByRole("button", { name: "Undo last pass" }).click();
  await expect(
    page.getByRole("button", { name: "Team up on No script for calls about rejections: send Sanjay a note" }),
  ).toBeVisible();
  await expect(page.getByText("1 passed")).toBeVisible();
});

test("L-CREW/8 at 375px: nothing yet with Browse the Wall; axe", async ({ page }) => {
  await answerCrew(page, deck([], { state: "nothing_yet" }));
  await open(page);
  await expect(page.getByRole("heading", { name: "No crews to join yet" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Browse the Wall" })).toHaveAttribute("href", "/wall");
  await expectNoSeriousAxeIssues(page);
});

test("L-CREW/5 at 375px: Filter ideas by keyboard, live counts, Show N ideas, the chip removes it; axe on the panel", async ({
  page,
}) => {
  await answerCrew(page, deck([C1, C2]));
  await open(page);
  const filters = page.getByRole("button", { name: "Filters", exact: true });
  await filters.click();
  await expect(filters).toHaveAttribute("aria-expanded", "true");
  const panel = page.getByRole("dialog", { name: "Filter ideas" });
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("button", { name: "Close filters" })).toBeFocused();
  await expect(panel.getByRole("group", { name: "Location" })).toBeVisible();
  await expectNoSeriousAxeIssues(page);

  await page.keyboard.press("Tab");
  const hyd = panel.getByRole("button", { name: /^Hyderabad/ });
  await expect(hyd).toBeFocused();
  await page.keyboard.press("Space");
  await expect(hyd).toHaveAttribute("aria-pressed", "true");
  await expect(panel.getByRole("status")).toHaveText("1 idea matches");
  await panel.getByRole("button", { name: "Show 1 idea" }).click();
  await expect(panel).toBeHidden();
  await expect(page.getByText("1 idea close to yours")).toBeVisible();
  await expect(page.getByRole("button", { name: "Remove filter: Hyderabad" })).toBeVisible();

  await page.getByRole("button", { name: "Remove filter: Hyderabad" }).click();
  await expect(page.getByText("2 ideas close to yours")).toBeVisible();

  // Escape closes the panel and focus goes back to Filters.
  await filters.click();
  await expect(panel).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  await expect(filters).toBeFocused();
});

test("J-TEAMUP/1–2 at 375px: Team up sends, Keep looking moves on, Your crews lists Waiting for Ravi; axe", async ({
  page,
}) => {
  await answerCrew(page, deck([C1, C2]));
  await answerTeamUp(page);
  await open(page);
  await page
    .getByRole("button", { name: "Team up on Rejection SMS codes confuse investors: send Ravi a note" })
    .click();
  const sheet = page.getByRole("dialog", { name: "Team up with Ravi" });
  await expect(sheet).toBeVisible();
  await sheet.getByRole("button", { name: "Send to Ravi" }).click();
  await expect(sheet.getByRole("status")).toContainText("Sent to Ravi");
  await sheet.getByRole("button", { name: "Keep looking" }).click();
  await expect(sheet).toBeHidden();
  // DEC-126: nothing passed; the card asked about goes to the end and the next one is in front, with focus.
  await expect(page.getByText("Idea 1 of 2")).toBeAttached();
  await expect(
    page.getByRole("button", { name: "No script for calls about rejections. Preview the idea" }),
  ).toBeFocused();
  const row = page.getByRole("link", {
    name: "Rejection SMS codes confuse investors, waiting for Ravi. Open the idea.",
  });
  await expect(row).toHaveAttribute("href", `/ideas/${C1.id}`);
  await expect(page.getByRole("listitem").filter({ has: row })).toContainText("Ravi Nair, Investor service");
  await expectNoSeriousAxeIssues(page);
  // At the end of the deck it reads Requested; Next on a card just asked about only moves on.
  await page.getByRole("button", { name: "Next idea" }).click();
  await expect(page.getByText("Idea 2 of 2")).toBeAttached();
  await expect(page.getByRole("button", { name: REQUESTED, exact: true })).toHaveAttribute(
    "aria-disabled",
    "true",
  );
  await expect(page.getByRole("button", { name: WITHDRAW, exact: true })).toBeVisible();
});

test("DEC-126 at 375px: a card asked about reads Requested, with Withdraw at 4.5:1, its focus ring and target; axe on the Requested state; Withdraw brings Team up back in place", async ({
  page,
}) => {
  await requestedThenWithdraw(page);
});

test("DEC-126 at 375px with reduced motion: after a send the card goes to the end without the flight", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await answerCrew(page, deck([C1, C2]));
  await answerTeamUp(page);
  await open(page);
  await page.getByRole("button", { name: TEAM_UP_C1 }).click();
  const sheet = page.getByRole("dialog", { name: "Team up with Ravi" });
  await sheet.getByRole("button", { name: "Send to Ravi" }).click();
  await sheet.getByRole("button", { name: "Keep looking" }).click();
  await expect(sheet).toBeHidden();
  await expect(page.getByText("Idea 1 of 2")).toBeAttached();
  await expect(page.locator(".crew-fly")).toHaveCount(0);
  await expect(page.locator(".dcard").last()).toContainText(C1.title);
  await expect(page.locator(".dcard").last()).toContainText("Requested");
});

test.describe("at 1440px", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("DEC-126 at 1440px: Requested and Withdraw on the card, measured; axe on the Requested state; Withdraw brings Team up back in place", async ({
    page,
  }) => {
    await requestedThenWithdraw(page);
  });
});

// WCAG 2.5.8 (target size), docs/WCAG22_POST_LAUNCH.md row 4, BLD-F093: at rest nothing on the page sits over the
// Filters button, at desktop and at 360px. Only axe's target-size rule, on the filter bar; the gate itself stays at
// WCAG 2.1 AA (DEC-112) until lane A's BLD-A229. Axe's 2.2 inventory found the button partially obscured only after
// J-TEAMUP's click on Team up had scrolled the page, which puts it under the phone's sticky bar (`.pnav`).
for (const size of [
  { name: "desktop", width: 1280, height: 800 },
  { name: "360px", width: 360, height: 740 },
]) {
  test(`S-H2 WCAG 2.5.8 at ${size.name}: nothing sits over the Filters button; axe target-size passes`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: size.width, height: size.height });
    await answerCrew(page, deck([C1, C2]));
    await open(page);
    const filters = page.getByRole("button", { name: "Filters", exact: true });
    await expect(filters).toBeVisible();
    await settleMotion(page);
    const ownsItsMiddle = await filters.evaluate((el) => {
      const r = el.getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return hit !== null && el.contains(hit);
    });
    expect(ownsItsMiddle).toBe(true);
    const results = await new AxeBuilder({ page }).include(".crew-fbar").withRules(["target-size"]).analyze();
    expect(results.violations.flatMap((v) => v.nodes.map((n) => `${v.id} ${n.target.join(" ")}`))).toEqual(
      [],
    );
  });
}
