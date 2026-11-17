/**
 * The Ones, end to end (DEC-034 to DEC-087): a One is inducted through the proposal API (the console page is
 * retired, DEC-106, R21; lane A's admin path replaces the proposals); the new One chooses a number and writes a
 * brief; a tier up plays the glow-up once; the Showcase brief, the leaderboard, the home carousel and the office
 * screen. axe on every page. Synthetic people only: each run picks a synthetic employee who is not a One yet.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Browser, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

const CHAIR = "SYN-00006";

type Person = { id: string; name: string; email: string };

function syntheticPeople(): Person[] {
  const csv = readFileSync(path.resolve(process.cwd(), "../../.data/hr/synthetic-hr.csv"), "utf8");
  return csv
    .trim()
    .split("\n")
    .slice(1)
    .map((line) => line.split(","))
    .map(([id, name, email]) => ({ id: id!, name: name!, email: email! }))
    .filter((p) => Number(p.id.slice(4)) >= 60); // never a persona, and not the first few managers
}

async function as(browser: Browser, username: string): Promise<Page> {
  const page = await (await browser.newContext()).newPage();
  await signIn(page, username);
  return page;
}

async function api(page: Page, method: "GET" | "POST", url: string, data?: Record<string, unknown>) {
  const res =
    method === "GET" ? await page.request.get(url) : await page.request.post(url, { data: data ?? {} });
  return { status: res.status(), body: (await res.json().catch(() => ({}))) as Record<string, unknown> };
}

/** Propose a sponsored One for a synthetic person who is not a One yet; returns them and the proposal id. */
async function proposeSomeone(core: Page): Promise<{ person: Person; proposal: number }> {
  const people = syntheticPeople().sort(() => Math.random() - 0.5);
  for (const person of people.slice(0, 25)) {
    const r = await api(core, "POST", "/api/ones/proposals", {
      kind: "include",
      way_in: "sponsored",
      email: person.email,
      title: "Synthetic test: a reconciliation check every AMC uses",
      reason: "Synthetic test citation: rebuilt a check that saves rework every week",
    });
    if (r.status === 201) return { person, proposal: Number(r.body.id) };
  }
  throw new Error("no synthetic person left to propose");
}

test.describe.serial("a new One, from proposal to glow-up", () => {
  let subject: Person;
  let oneId = 0;

  // One run at a time: the projects would otherwise race to choose numbers for the same shared One.
  // The 360 px check is inside the dashboard test.
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "one run at a time; the 360 px check is inside");
  });

  test("the committee proposes, the chair approves and the admin carries it out (API)", async ({
    browser,
  }) => {
    const core = await as(browser, PERSONAS.core);
    const { person, proposal } = await proposeSomeone(core);
    subject = person;

    const chair = await as(browser, CHAIR);
    expect(
      (
        await api(chair, "POST", `/api/ones/proposals/${proposal}/decide`, {
          verdict: "approve",
          how: "chair",
        })
      ).status,
    ).toBe(200);
    const admin = await as(browser, PERSONAS.admin);
    expect((await api(admin, "POST", `/api/ones/proposals/${proposal}/carry-out`)).status).toBe(200);

    const roster = (await api(admin, "GET", "/api/ones/console")).body as {
      ones: { id: number; email: string }[];
    };
    oneId = roster.ones.find((o) => o.email === subject.email)!.id;
    expect(oneId).toBeGreaterThan(0);
  });

  // A One's dashboard, their number, brief and glow-up left My ideas for S-ONE at /one (S-07 replaces the old
  // /my-ideas); their tests go with that screen.

  test("the Showcase brief, the leaderboard and the office screen", async ({ browser }) => {
    const one = await as(browser, subject.id);
    await one.goto("/my-ideas/showcase");
    await one.getByLabel("Delivery timelines").fill("Synthetic test: pilot in January, every AMC by March");
    await one.getByRole("button", { name: "Save your brief" }).click();
    await expect(
      one.getByRole("status").filter({ hasText: "Saved. The committee sees your latest version." }),
    ).toHaveText("Saved. The committee sees your latest version.");
    await expectNoSeriousAxeIssues(one);
    await one.goto("/ones/leaderboard");
    await expect(one.getByRole("heading", { level: 2, name: "People" })).toBeVisible();
    await expectNoSeriousAxeIssues(one);

    const core = await as(browser, PERSONAS.core);
    await core.goto(`/ones/showcase/${oneId}`);
    await expect(core.getByText("Synthetic test: pilot in January, every AMC by March")).toBeVisible();
    await expect(core.getByRole("button", { name: "Print" })).toBeVisible();
    await expectNoSeriousAxeIssues(core);

    const someone = await as(browser, PERSONAS.contributor);
    await someone.goto("/ones/leaderboard");
    await expect(someone.getByText("The leaderboard is for Ones.")).toBeVisible();
    await someone.goto("/");
    await expect(someone.getByRole("heading", { name: "What the Ones are up to" })).toBeVisible();
    await someone.getByRole("button", { name: "Next One" }).click();
    await expectNoSeriousAxeIssues(someone);
    await someone.goto("/constellation");
    await expect(someone.getByRole("heading", { level: 1, name: "The Ones" })).toBeVisible();
    await expect(someone.getByRole("navigation", { name: "Main" })).toHaveCount(0); // a wall display has no chrome
    await expectNoSeriousAxeIssues(someone);
  });
});

test("nobody outside the committee, the CEO or admin reads the console's data", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  expect((await page.request.get("/api/ones/console")).status()).toBe(403);
});
