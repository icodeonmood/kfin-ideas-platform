/**
 * The Ones, end to end (DEC-034 to DEC-087): a One is inducted through the proposal API (the console page is
 * retired, DEC-106, R21; lane A's admin path replaces the proposals); the new One chooses a number and writes a
 * brief; the committee writes a few words at /ones/write/:id and a tier up plays the glow-up once on S-ONE with
 * them; the One's Showcase brief and the committee's printable copy at /ones/showcase/:id (mapping/screens.md:111-112);
 * the office screen (the Ones on Home are in home.spec.ts). axe on every page. Synthetic people only: each run picks a synthetic
 * employee who is not a One yet.
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

  test("J-ONE/6 S-ONE mapping/screens.md:112: the committee writes a few words at /ones/write/:id, and the tier up plays the glow-up once on S-ONE with them", async ({
    browser,
  }) => {
    const core = await as(browser, PERSONAS.core);
    const up = await api(core, "POST", "/api/ones/proposals", {
      kind: "tier_up",
      one_id: oneId,
      tier_to: 2,
      reason: "Synthetic test: shipped and measured",
    });
    expect(up.status).toBe(201);
    const pid = Number(up.body.id);

    // Someone who is neither invited nor on the committee is told so, and gets no form.
    const someone = await as(browser, PERSONAS.contributor);
    await someone.goto(`/ones/write/${pid}`);
    await expect(someone.getByText("This invitation isn't open, or isn't for you.")).toBeVisible();
    await expect(someone.getByRole("textbox", { name: "Your message" })).toHaveCount(0);

    // The committee writes on the page the invitation links to (comms/render.py `links.write`).
    await core.goto(`/ones/write/${pid}`);
    await expect(core.getByRole("heading", { level: 1, name: /^A few words for / })).toBeVisible();
    await expect(core.getByText(/They are moving to Glow\./)).toBeVisible();
    await expectNoSeriousAxeIssues(core);
    await core.getByRole("textbox", { name: "Your message" }).fill("Synthetic test: well done on all of it.");
    await core.getByRole("button", { name: "Send your message" }).click();
    await expect(core.getByText("Thank you. Your message is saved.")).toBeVisible();
    await expect(core.getByRole("textbox", { name: "Your message" })).toHaveCount(0);
    await expectNoSeriousAxeIssues(core);

    const chair = await as(browser, CHAIR);
    expect(
      (await api(chair, "POST", `/api/ones/proposals/${pid}/decide`, { verdict: "approve", how: "chair" }))
        .status,
    ).toBe(200);
    const admin = await as(browser, PERSONAS.admin);
    expect((await api(admin, "POST", `/api/ones/proposals/${pid}/carry-out`)).status).toBe(200);

    // The words feed S-ONE's "Messages for you", with the writer named (S-ONE.states showGlowUp).
    const one = await as(browser, subject.id);
    await one.goto("/one");
    const dialog = one.getByRole("dialog", { name: /your spark is hotter/ });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("heading", { name: "Messages for you" })).toBeVisible();
    await expect(dialog.getByText("Synthetic test: well done on all of it.")).toBeVisible({
      timeout: 10_000,
    });
    await expect(dialog.getByText(/^From the core committee: /)).toBeVisible();
    await expectNoSeriousAxeIssues(one);
    await dialog.getByRole("button", { name: "Back to my dashboard" }).click();
    await expect(dialog).toBeHidden();
    await one.reload();
    await expect(one.getByRole("heading", { level: 1, name: /^You're No\. \d+$/ })).toBeVisible();
    await expect(one.getByRole("dialog")).toHaveCount(0);
  });

  // The One writes the Showcase brief in S-ONE's sheet; the leaderboard is on the Wall (BLD-E042).
  test("BLD-E042 mapping/screens.md:111: the committee reads and prints the One's Showcase brief at /ones/showcase/:id; nobody else opens it", async ({
    browser,
  }) => {
    const one = await as(browser, subject.id);
    await one.goto("/one");
    await one.getByRole("button", { name: "Your Showcase brief" }).click();
    const sheet = one.getByRole("dialog", { name: "Your Showcase brief" });
    await sheet
      .getByRole("textbox", { name: /^Delivery timelines/ })
      .fill("Synthetic test: pilot in January, every AMC by March");
    await sheet.getByRole("button", { name: "Save your brief" }).click();
    await expect(sheet.getByRole("status")).toHaveText("Saved. The committee sees your latest version.");

    const core = await as(browser, PERSONAS.core);
    await core.goto(`/ones/showcase/${oneId}`);
    await expect(core.getByRole("heading", { level: 1, name: /^Showcase brief: No\. \d+, / })).toBeVisible();
    await expect(core.getByText("Synthetic test: pilot in January, every AMC by March")).toBeVisible();
    await expect(core.getByRole("heading", { level: 2, name: "Delivery timelines" })).toBeVisible();
    await expect(core.getByRole("button", { name: "Print" })).toBeVisible();
    await expectNoSeriousAxeIssues(core);

    // The page rule (policy/rbac.yaml `/ones/showcase view_ones_console`) sends anyone else home, the One
    // included, and the API agrees.
    for (const page of [await as(browser, PERSONAS.contributor), one]) {
      await page.goto(`/ones/showcase/${oneId}`);
      await expect(page).not.toHaveURL(/\/ones\/showcase\//);
      expect((await page.request.get(`/api/ones/${oneId}/showcase`)).status()).toBe(403);
    }
  });

  // The old home carousel retired with S-03 (BLD-C143); the Ones' fan on Home is checked in home.spec.ts.
  test("the office screen", async ({ browser }) => {
    const someone = await as(browser, PERSONAS.contributor);
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
