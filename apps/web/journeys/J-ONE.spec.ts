/**
 * J-ONE: an idea ships and its sharer becomes a One (1pc-handoff/03-journeys/J-ONE.md). The pack has no V-ACC for
 * it; lane G's draft V-ACC.one/1–6 holds the detail once the product lead confirms it. These steps check hand-offs.
 * Copy: reference/copy/Status.md (C-TRACK stage), Wall.md, Office.md, OneDashboard.md, Home.md (The Ones).
 * Seed: V1 (Varun, One No. 11, Tier 3) shipped 40 days ago, measured at 30 days, money confirmed by Finance; S1
 * (Siddharth, One No. 21, inducted 10 days ago) measured at 30 and 90 days; D1 measured at 90 days; I1 measured
 * at 30 days with money Finance has not confirmed. Seven Ones in all. Posts by Varun, Dinesh, Siddharth, Indira.
 * Dinesh (One No. 8) has a tier rise from 4 to 5 waiting to be shown (lane E, e716585). The founding Ones (Gopal,
 * Aparna, Rekha, Dinesh) are inducted on the founding day, 1 Nov 2026 10:00 IST, 0 to 3 minutes after it (BLD-E073).
 */
import { expect } from "@playwright/test";

import { dayLabelIST, ideaUrl, seeded, signInAs, step } from "./lib";

/** club_seed.FOUNDING_DAY (OneDashboard.md:36): 1 Nov 2026, 10:00 India time. */
const FOUNDING_DAY = Date.parse("2026-11-01T10:00:00+05:30");
/** Dinesh's number window ends 30 days after his induction, 3 minutes after the founding day (L-ONES.rules/2;
 * wall/ones.py _closed: open while now <= swap_until). 1 Dec 2026, 10:03 IST. */
const DINESH_WINDOW_ENDS = new Date(FOUNDING_DAY + 3 * 60_000 + 30 * 86_400_000);

step(
  "J-ONE/1",
  "S-06",
  "A shipped idea: the sharer's track reaches Shipped and the Wall lists it as shipped",
  { needs: ["S-06", "C-TRACK", "S-WALL", "L-WALL", "L-DECIDE", "L-IMPACT"] },
  async ({ page }) => {
    const v1 = await seeded("V1");
    expect(v1.status).toBe("shipped");
    await signInAs(page, "varun");
    await page.goto(ideaUrl(v1));
    await expect(page.getByRole("heading", { level: 1 })).toContainText(v1.title);
    // C-TRACK.anatomy: a stage's state is its read-out suffix; at Shipped every stage is done and none is "now".
    const track = page.getByRole("list", { name: "Where it is" }).filter({ visible: true });
    await expect(track.getByText("Shipped, done", { exact: true })).toBeVisible();
    await expect(track.getByText(/, now$/)).toHaveCount(0);
    await page.goto("/wall");
    await expect(page.getByRole("heading", { level: 1, name: "Wall" })).toBeVisible();
    await expect(page.getByRole("link", { name: v1.title }).first()).toBeVisible();
  },
);

step(
  "J-ONE/1b",
  "S-ADMIN",
  "Choosing a picked idea's build team, the admin sees who asked to join it, oldest first",
  // S-ADMIN is not drawn (L-DECIDE.after OPEN); the list is lane A's BLD-A226. The seed's J1 is picked with no team,
  // and its sharer asked to join a day before the load (L-DECIDE.rules/6, DEC-111, BLD-E059).
  { needs: ["L-DECIDE"] },
  async ({ page }) => {
    const j1 = await seeded("J1");
    expect(j1.ref, "J1 is picked, so it has a reference").toBeTruthy();
    await signInAs(page, "kunal");
    await page.goto("/admin");
    const form = page.getByRole("region", { name: "Picked ideas: choose the build team" });
    const idea = form.getByLabel("Idea", { exact: true });
    const asked = form.getByRole("list", { name: "Asked to join" });
    // The select is controlled, so a choice made before the page hydrates is lost: choose until the list follows it.
    await expect(async () => {
      await idea.selectOption(j1.ref as string);
      await expect(idea).toHaveValue(j1.ref as string, { timeout: 1_000 });
      await expect(asked).toBeVisible({ timeout: 2_000 });
    }).toPass({ timeout: 20_000 });
    // programme/view.py: "{name}, asked {D Mon YYYY}" in India time.
    await expect(asked.getByRole("listitem").first()).toHaveText(
      /^Jatin Khurana, asked \d{1,2} [A-Z][a-z]{2} \d{4}$/,
    );
    await expect(form.getByText("No one has asked to join yet.")).toHaveCount(0);
  },
);

step(
  "J-ONE/2",
  "S-WALL",
  "Measured figures reach the Wall's live fixes and totals; money only once Finance confirms",
  { needs: ["S-WALL", "L-WALL", "L-IMPACT"] },
  async ({ page }) => {
    const v1 = await seeded("V1");
    const i1 = await seeded("I1");
    await signInAs(page, "naveen");
    await page.goto("/wall");
    await expect(page.getByText("What shipped ideas have changed so far.")).toBeVisible();
    await expect(
      page.getByText(
        "Measured 30 and 90 days after each idea ships, and confirmed by Finance where money is involved.",
      ),
    ).toBeVisible();
    // Totals: the latest confirmed figures of V1 (620), S1 (140 at 90 days), D1 (110), I1 (70); money only V1's.
    const totals = page.locator("main");
    await expect(totals).toContainText(/940\s*Hours saved a month/);
    await expect(totals).toContainText(/₹18 lakh\s*Saved a year, Finance confirmed/);
    await expect(totals).toContainText(/4\s*Fixes shipped and measured/);
    await expect(totals).toContainText(/58,600\s*Distributors reached by a shipped fix/);
    const v1Row = page.getByRole("row", { name: new RegExp(v1.title) });
    await expect(v1Row).toContainText("620 hours a month saved; bounced payouts down by a third");
    await expect(v1Row).toContainText("30 days");
    await expect(page.getByRole("row", { name: new RegExp(i1.title) })).toContainText(
      "Returned transfer requests down by a quarter",
    );
    // I1's ₹6 lakh is not confirmed by Finance, so it shows nowhere on the Wall (L-IMPACT/3).
    await expect(page.getByText("₹6 lakh")).toHaveCount(0);
  },
);

step(
  "J-ONE/3",
  "S-WALL",
  "New Ones show on the Wall's The Ones and on the office screen, with number, tier and brief",
  { needs: ["S-WALL", "L-ONES", "S-OFFICE", "L-DISPLAY"] },
  async ({ page, browser }) => {
    await signInAs(page, "naveen");
    await page.goto("/wall");
    await expect(page.getByRole("heading", { level: 2, name: "The Ones" })).toBeVisible();
    await expect(
      page.getByText(
        "Colleagues whose ideas shipped and made a measured difference. Each One keeps a number, and their tier warms as their impact grows.",
      ),
    ).toBeVisible();
    const varun = page.getByRole("article").filter({ hasText: "Varun Chopra" });
    await expect(varun).toContainText("11");
    await expect(varun).toContainText("Tier 3, Flame");
    await expect(varun).toContainText("Stopped wrong bank details before a payout goes out.");

    const display = await (await browser.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
    await signInAs(display, "office");
    await display.goto("/display/office");
    await expect(
      display.getByText("7 Ones so far. Each one shipped something that changed how we work."),
    ).toBeVisible();
    await expect(display.getByText("No. 11 · Varun")).toBeVisible();
    await display.context().close();
  },
);

step(
  "J-ONE/3b",
  "S-ONE",
  "The new One finds their number and tier on their dashboard (no Inbox item at launch, BLD-A186)",
  { needs: ["S-ONE", "L-ONES"] },
  async ({ page }) => {
    // Varun was inducted 8 days ago on V1. The number and tier match the Wall's The Ones (J-ONE/3).
    await signInAs(page, "varun");
    await page.goto("/one");
    await expect(page.getByRole("heading", { level: 1, name: "You're No. 11" })).toBeVisible();
    await expect(page.getByText(/^Tier 3, Flame\. One since \d{1,2} [A-Z][a-z]{2} \d{4}\.$/)).toBeVisible();
    await expect(page.getByText("Stopped wrong bank details before a payout goes out.")).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "Impact so far" })).toBeVisible();
  },
);

step(
  "J-ONE/4",
  "S-ONE",
  "The new One's dashboard: keep or swap the number within 30 days, and propose a brief",
  { needs: ["S-ONE", "L-ONES"], changes: ["S1"] },
  async ({ page }) => {
    await signInAs(page, "siddharth");
    await page.goto("/one");
    await expect(page.getByRole("heading", { level: 1, name: "You're No. 21" })).toBeVisible();
    await expect(page.getByText("Tier 1, Spark").first()).toBeVisible();
    await expect(
      page.getByText(
        /^Keep No\. 21, or choose any free number from 1 to 999 until \d{1,2} [A-Z][a-z]{2} \d{4}\. First come, first served\. After that, it's yours\.$/,
      ),
    ).toBeVisible();
    // The brief on the Wall is the one on the dashboard.
    await expect(page.getByText("Online forms that fill the city from the pin code.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Propose a new brief" })).toBeVisible();
    await page.getByRole("textbox", { name: "Number you'd like" }).fill("77");
    await page.getByRole("button", { name: "Save my number" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "You're No. 77" })).toBeVisible();
  },
);

step(
  "J-ONE/5",
  "S-03",
  "A One's post about what changed is a card in Home's The Ones for everyone",
  { needs: ["S-03", "C-ONES-FAN", "L-ONES"] },
  async ({ page }) => {
    await signInAs(page, "naveen");
    await page.goto("/home");
    await expect(page.getByText("Fixes that shipped, from the people behind them.")).toBeVisible();
    const card = page.getByRole("article").filter({ hasText: "Varun Chopra" });
    await expect(card).toContainText("One No. 11, Tier 3, Flame");
    await expect(card).toContainText(
      "Payout checks are live at every branch. Bounced payouts are down by a third.",
    );
    await expect(card).toContainText("Adopted by 3 teams");
    await expect(card).toContainText(/620\s*hours a month saved/);
    await expect(card.getByRole("link", { name: /^Read the thread/ })).toBeVisible();
    await expect(page.getByRole("link", { name: "See the Wall" })).toBeVisible();
  },
);

step(
  "J-ONE/6",
  "S-ONE",
  "At 90 days the latest figures replace the 30-day ones on the dashboard",
  { needs: ["S-ONE", "L-ONES", "L-IMPACT"] },
  async ({ page }) => {
    await signInAs(page, "siddharth");
    await page.goto("/one");
    await expect(page.getByRole("heading", { level: 2, name: "Impact so far" })).toBeVisible();
    await expect(page.getByText("Measured 30 and 90 days after your idea ships.")).toBeVisible();
    await expect(page.getByText("140 hours a month")).toBeVisible();
    await expect(page.getByText("90 hours a month")).toHaveCount(0);
    await expect(page.getByText("2 fewer steps")).toBeVisible();
  },
);

step(
  "J-ONE/6b",
  "S-ONE",
  "A tier rise plays its moment once: your spark is hotter, with your story so far",
  { needs: ["S-ONE", "L-ONES"] },
  async ({ page }) => {
    // Seed (lane E, e716585): Dinesh, One No. 8, rose from Tier 4 to Tier 5 two days ago; the moment is unseen and
    // carries a note from the Ones Committee. Copy: OneDashboard.md, state showGlowUp=true.
    await signInAs(page, "dinesh");
    await page.goto("/one");
    const moment = page.getByRole("dialog", { name: "No. 8, your spark is hotter" });
    await expect(moment).toBeVisible();
    await expect(moment).toContainText("From Tier 4, Blaze to Tier 5, White heat");
    await expect(moment).toContainText("Your story so far");
    await expect(moment).toContainText("Ideas shared");
    await expect(moment).toContainText("Messages for you");
    await expect(moment).toContainText(/From the core committee: (Manoj Agarwal|Shalini Bose)/);
    await moment.getByRole("button", { name: "Back to my dashboard" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "You're No. 8" })).toBeVisible();
    await expect(page.getByText("Tier 5, White heat").first()).toBeVisible();
    // It plays once (L-ONES.rules/3): opening the dashboard again shows no moment.
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: "You're No. 8" })).toBeVisible();
    await expect(page.getByRole("dialog", { name: /your spark is hotter/ })).toHaveCount(0);
  },
);

step(
  "J-ONE/6c",
  "S-ONE",
  "A Founding One's dashboard dates from the founding day, and so does the number window (S-ONE.layout/2, S-ONE.layout/3)",
  { needs: ["S-ONE.layout", "L-ONES"] },
  async ({ page }) => {
    // Seed (lane E, BLD-E073): Dinesh was inducted 3 minutes after club_seed.FOUNDING_DAY, not a year before the
    // programme (the walk read "Founding One since 24 Nov 2025"). J-ONE/6b has played his moment, so the dashboard
    // opens on its own. Copy: OneDashboard.md:36 and :40; closed window: V-FIELDS.one/3 (a GAPS default, not drawn).
    await signInAs(page, "dinesh");
    const before = Date.now();
    await page.goto("/one");
    await expect(page.getByRole("heading", { level: 1, name: "You're No. 8" })).toBeVisible();
    const after = Date.now();
    await expect(
      page.getByText("Tier 5, White heat. Founding One since 1 Nov 2026.", { exact: true }),
    ).toBeVisible();
    // The worker reads its clock as it renders the page, between `before` and `after`: open while that is on or
    // before the end, which the line gives as the India day it falls on (wall/common.py day_label).
    const card = page.getByRole("region", { name: "Your number" });
    const keep = card.getByText(
      `Keep No. 8, or choose any free number from 1 to 999 until ${dayLabelIST(DINESH_WINDOW_ENDS)}. First come, first served. After that, it's yours.`,
      { exact: true },
    );
    const yours = card.getByText("No. 8 is yours for good.", { exact: true });
    const ends = DINESH_WINDOW_ENDS.getTime();
    if (after <= ends) {
      await expect(keep).toBeVisible();
      await expect(card.getByRole("textbox", { name: "Number you'd like" })).toBeVisible();
    } else if (before > ends) {
      await expect(yours).toBeVisible();
      await expect(card.getByText(/^Keep No\. 8, or choose/)).toHaveCount(0);
      await expect(card.getByRole("textbox", { name: "Number you'd like" })).toHaveCount(0);
    } else {
      await expect(keep.or(yours)).toBeVisible(); // rendered in the seconds the window closed: either is right
    }
  },
);
