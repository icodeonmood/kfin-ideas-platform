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

test("7-8: the review desk and desk decisions", async ({ browser }) => {
  const desk = await as(browser, DEMO.desk);
  await desk.goto("/review");
  await expect(desk.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(desk.locator("table tbody tr, .crew-cards li").first()).toBeVisible();
  await expectNoSeriousAxeIssues(desk);
  const member = await as(browser, DEMO.member);
  await member.goto("/desk-decisions");
  await expect(
    member
      .getByText("Explain transaction rejections to distributors in plain words", { exact: false })
      .first(),
  ).toBeVisible();
  await expectNoSeriousAxeIssues(member);
});

test("9: the console's three waiting states", async ({ browser }) => {
  const chair = await as(browser, DEMO.chair);
  await chair.goto("/ones/console");
  await expect(
    chair
      .locator("li.proposal", { hasText: "Vikram Bhat" })
      .getByRole("button", { name: "Approve as chair" }),
  ).toBeVisible();
  await expect(chair.locator("li.proposal", { hasText: "Farhan Qureshi" })).toContainText("Tier 1 to Tier 2");
  await expect(chair.locator("li.proposal", { hasText: "Suresh Patil" })).toContainText(
    "Ready for the admin member",
  );
  await expectNoSeriousAxeIssues(chair);
  const admin = await as(browser, DEMO.admin);
  await admin.goto("/ones/console");
  await expect(
    admin
      .locator("li.proposal", { hasText: "Suresh Patil" })
      .getByRole("button", { name: "Carry out and send" }),
  ).toBeVisible();
  const ceo = await as(browser, DEMO.ceo);
  await ceo.goto("/ones/console");
  await expect(ceo.getByRole("heading", { level: 2, name: "Propose a One" })).toBeVisible();
});

test("10-12: leaderboard, manager view and the office screen", async ({ browser }) => {
  const ananya = await as(browser, DEMO.one);
  await ananya.goto("/ones/leaderboard");
  await expect(ananya.getByRole("cell", { name: "Rohit Menon" })).toBeVisible();
  await expectNoSeriousAxeIssues(ananya);
  const rahul = await as(browser, DEMO.manager);
  await rahul.goto("/my-team");
  await expect(rahul.getByRole("cell", { name: "Kavya Menon" })).toBeVisible();
  await expectNoSeriousAxeIssues(rahul);
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
