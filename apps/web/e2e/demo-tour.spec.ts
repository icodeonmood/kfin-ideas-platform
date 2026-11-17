/**
 * The demo walkthrough (docs/DEMO.md), checked page by page with axe. Opt-in: it needs `make demo` first, so it
 * runs only with DEMO_TOUR=1 (`DEMO_TOUR=1 npx playwright test e2e/demo-tour.spec.ts`). It never closes the
 * glow-up, so the demo stays ready for a person to walk through.
 */
import { expect, test, type Browser, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, signIn } from "./helpers";

test.skip(!process.env.DEMO_TOUR, "run after `make demo` with DEMO_TOUR=1");
test.describe.configure({ mode: "serial" });

const DEMO = {
  employee: "DEMO-00001",
  desk: "DEMO-00002",
  member: "DEMO-00003",
  chair: "DEMO-00004",
  ceo: "DEMO-00005",
  admin: "DEMO-00006",
  manager: "DEMO-00007",
  one: "DEMO-00008",
  founding: "DEMO-00009",
  pm: "DEMO-00013",
  fixer: "DEMO-00017",
} as const;

async function as(browser: Browser, username: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await signIn(page, username);
  return page;
}

test("1-3: home carousel, share an idea, Find your crew", async ({ browser }) => {
  const kavya = await as(browser, DEMO.employee);
  await kavya.goto("/");
  await expect(kavya.getByRole("heading", { name: "What the Ones are up to" })).toBeVisible();
  await expectNoSeriousAxeIssues(kavya);
  await kavya.goto("/share");
  await expect(kavya.getByRole("heading", { level: 1 })).toBeVisible();
  await kavya.goto("/my-ideas");
  await kavya
    .getByRole("link", { name: /Catch missing bank fields|Your idea IDEA-/ })
    .first()
    .click();
  await expect(kavya.getByText("Colleagues are on this").first()).toBeVisible();
  await expectNoSeriousAxeIssues(kavya);
  await kavya.goto("/inbox");
  await expect(kavya.locator(".inbox li").first()).toBeVisible();
});

test("4: My ideas as a One: the tier dashboard and the glow-up", async ({ browser }) => {
  const ananya = await as(browser, DEMO.one);
  await ananya.goto("/my-ideas");
  const dialog = ananya.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: /your spark is hotter/ })).toBeVisible();
  await expect(dialog.getByText("Glow suits you", { exact: false })).toBeVisible({ timeout: 10_000 });
  await expectNoSeriousAxeIssues(ananya);
  const founding = await as(browser, DEMO.founding);
  await founding.goto("/my-ideas");
  await expect(founding.getByRole("heading", { level: 2, name: "You're No. 1" })).toBeVisible();
  await expectNoSeriousAxeIssues(founding);
});

test("5-6: the wall and an idea page", async ({ browser }) => {
  const kavya = await as(browser, DEMO.employee);
  await kavya.goto("/wall");
  const ones = kavya.locator(".ones-band");
  await expect(ones.getByText("Rohit Menon")).toBeVisible();
  await expect(ones.getByText("One No. 3")).toBeVisible();
  await expectNoSeriousAxeIssues(kavya);
  await kavya
    .getByRole("link", {
      name: /status page for every investor service request|Check bank details|One status page/,
    })
    .first()
    .click();
  await expect(kavya.getByRole("heading", { level: 1 })).toBeVisible();
  await expectNoSeriousAxeIssues(kavya);
});

// Desk decisions (step 8) is retired (DEC-106, R10); lane B rebuilds the committee window on /committee.
test("7: the review desk", async ({ browser }) => {
  const desk = await as(browser, DEMO.desk);
  await desk.goto("/desk"); // S-R1 (the old /review redirects here)
  await expect(desk.getByRole("heading", { level: 1 })).toBeVisible();
  // The demo seeds no question sets, so the default tab, Waiting on the sharer, can be empty (A10): a row on it, or
  // the tab's own empty line, then a row on To review or the same empty line there
  await expect(desk.locator("table tbody tr, .crew-cards li, .emp").first()).toBeVisible();
  await desk.getByRole("tab", { name: /^To review/ }).click();
  await expect(desk.locator("table tbody tr, .crew-cards li, .emp").first()).toBeVisible();
  await expectNoSeriousAxeIssues(desk);
});

// The Ones console (step 9) is retired (DEC-106, R21).
// The manager view (step 11) is retired (DEC-106, R12).
test("10, 12: leaderboard and the office screen", async ({ browser }) => {
  const ananya = await as(browser, DEMO.one);
  await ananya.goto("/ones/leaderboard");
  await expect(ananya.getByRole("cell", { name: "Rohit Menon" })).toBeVisible();
  await expectNoSeriousAxeIssues(ananya);
  const rahul = await as(browser, DEMO.manager);
  await rahul.goto("/constellation");
  await expect(rahul.getByRole("heading", { level: 1, name: "The Ones" })).toBeVisible();
  await expectNoSeriousAxeIssues(rahul);
});

test("13-14: the launch screen and the kill switches", async ({ browser }) => {
  const admin = await as(browser, DEMO.admin);
  await admin.goto("/launch");
  await expect(admin.getByRole("heading", { level: 1, name: "Launch screen" })).toBeVisible();
  await admin.goto("/admin");
  await expect(admin.getByText("ones.public")).toBeVisible();
  await expectNoSeriousAxeIssues(admin);
});

test("15-21: delivery (read only, so the demo stays ready; lenses and learning retired, DEC-106)", async ({
  browser,
}) => {
  const meera = await as(browser, DEMO.member);
  await meera.goto("/delivery");
  await expect(
    meera.getByRole("heading", { level: 2, name: "Picked, waiting for a handover" }),
  ).toBeVisible();
  await expect(meera.getByRole("button", { name: "Start the handover" }).first()).toBeVisible();
  await expect(meera.getByText("Live sync with the delivery pipeline: coming soon")).toBeVisible();
  await expectNoSeriousAxeIssues(meera);

  const ceo = await as(browser, DEMO.ceo);
  await ceo.goto("/delivery");
  await ceo.getByRole("link", { name: /why an SIP registration is stuck/ }).click();
  await expect(ceo.getByRole("button", { name: "Approve the pack" })).toBeVisible();
  await expectNoSeriousAxeIssues(ceo);
  await ceo.goto("/delivery");
  await ceo.getByRole("link", { name: /brokerage statements/ }).click();
  await expect(ceo.getByRole("button", { name: "Confirm these results" })).toBeVisible();
  await expectNoSeriousAxeIssues(ceo);

  const deepa = await as(browser, DEMO.pm);
  await deepa.goto("/delivery");
  await deepa.getByRole("link", { name: /nominee details from CKYC/ }).click();
  await expect(deepa.getByRole("heading", { level: 3, name: "Record the current step" })).toBeVisible();
  await expectNoSeriousAxeIssues(deepa);

  const vikram = await as(browser, DEMO.fixer);
  await vikram.goto("/delivery");
  await vikram.getByRole("link", { name: /change-of-bank requests/ }).click();
  await expect(vikram.getByRole("heading", { level: 2, name: "Action plan" })).toBeVisible();
  await expect(vikram.getByText("Overdue.")).toBeVisible();
  await expectNoSeriousAxeIssues(vikram);

  const sana = await as(browser, DEMO.admin);
  await sana.goto("/delivery");
  await sana.getByRole("link", { name: /where each service request is/ }).click();
  await expect(sana.getByRole("button", { name: "Finance has confirmed the money" })).toBeVisible();
  await expectNoSeriousAxeIssues(sana);
});
