/**
 * The Ones, end to end (DEC-034 to DEC-087): the committee proposes, the chair approves, the admin member carries
 * it out; the new One chooses a number and writes a brief; a tier up plays the glow-up once; the Showcase brief,
 * the leaderboard, the home carousel and the office screen. axe on every page. Synthetic people only: each run
 * picks a synthetic employee who is not a One yet.
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

  test("the committee proposes, the chair approves and the admin carries it out", async ({ browser }) => {
    const core = await as(browser, PERSONAS.core);
    const { person } = await proposeSomeone(core);
    subject = person;

    const chair = await as(browser, CHAIR);
    await chair.goto("/ones/console");
    await expect(chair.getByRole("heading", { level: 1, name: "Ones" })).toBeVisible();
    await expectNoSeriousAxeIssues(chair);
    const card = chair.locator("li.proposal", { hasText: subject.name });
    await card.getByRole("button", { name: "Approve as chair" }).click();
    await expect(chair.getByRole("status")).toHaveText("Approved.");

    const admin = await as(browser, PERSONAS.admin);
    await admin.goto("/ones/console");
    await admin
      .locator("li.proposal", { hasText: subject.name })
      .getByRole("button", { name: "Carry out and send" })
      .click();
    await expect(admin.getByRole("status")).toHaveText("Carried out. The message is on its way.");
    await expectNoSeriousAxeIssues(admin);

    const roster = (await api(admin, "GET", "/api/ones/console")).body as {
      ones: { id: number; email: string }[];
    };
    oneId = roster.ones.find((o) => o.email === subject.email)!.id;
    expect(oneId).toBeGreaterThan(0);
  });

  test("the new One sees their dashboard, chooses a number and writes a brief", async ({ browser }) => {
    const one = await as(browser, subject.id);
    await one.goto("/my-ideas");
    await expect(one.getByRole("heading", { level: 2, name: /^You're No\. \d+$/ })).toBeVisible();
    // Points are live now (BLD-147, BLD-148), so the dashboard no longer carries a "Coming soon" line.
    await expect(one.getByText("Your number", { exact: true }).first()).toBeVisible();
    await expect(one.getByText("Your impact brief", { exact: true }).first()).toBeVisible();
    await expectNoSeriousAxeIssues(one);

    await one.getByLabel("Number you'd like").fill(String(700 + Math.floor(Math.random() * 290)));
    await one.getByRole("button", { name: "Choose this number" }).click();
    const dashboard = one.locator(".one-dashboard");
    await expect(dashboard.getByRole("status").or(dashboard.locator(".field-error"))).toContainText(
      /You're now No\.|taken/,
    );

    await one
      .getByLabel(/Write your brief|Propose a new brief/)
      .fill("If this works: synthetic test teams stop reprocessing by hand.");
    await one.getByRole("button", { name: "Send to the committee" }).click();
    await expect(dashboard.getByRole("status")).toHaveText("Your brief is with the core committee.");

    const chair = await as(browser, CHAIR);
    const proposals = (await api(chair, "GET", "/api/ones/console")).body as {
      proposals: { id: number; kind: string; state: string; one_id: number }[];
    };
    const brief = proposals.proposals.find(
      (p) => p.kind === "impact_brief" && p.one_id === oneId && p.state === "proposed",
    )!;
    expect(
      (
        await api(chair, "POST", `/api/ones/proposals/${brief.id}/decide`, {
          verdict: "approve",
          how: "chair",
        })
      ).status,
    ).toBe(200);

    const wall = await as(browser, PERSONAS.contributor);
    await wall.goto("/wall");
    await expect(wall.getByRole("heading", { level: 2, name: "The Ones" })).toBeVisible();
    await expect(
      wall.getByText("If this works: synthetic test teams stop reprocessing by hand.").first(),
    ).toBeVisible();
    await expectNoSeriousAxeIssues(wall);
  });

  test("a tier up plays the glow-up once, with the committee's message", async ({ browser }) => {
    const core = await as(browser, PERSONAS.core);
    const up = await api(core, "POST", "/api/ones/proposals", {
      kind: "tier_up",
      one_id: oneId,
      tier_to: 2,
      reason: "Synthetic test: shipped and measured",
    });
    expect(up.status).toBe(201);
    const pid = Number(up.body.id);
    expect(
      (
        await api(core, "POST", `/api/ones/proposals/${pid}/messages`, {
          from: "committee",
          text: "Synthetic test: well done on all of it.",
        })
      ).status,
    ).toBe(201);
    const chair = await as(browser, CHAIR);
    expect(
      (await api(chair, "POST", `/api/ones/proposals/${pid}/decide`, { verdict: "approve", how: "chair" }))
        .status,
    ).toBe(200);
    const admin = await as(browser, PERSONAS.admin);
    expect((await api(admin, "POST", `/api/ones/proposals/${pid}/carry-out`)).status).toBe(200);

    const one = await as(browser, subject.id);
    await one.goto("/my-ideas");
    const dialog = one.getByRole("dialog");
    await expect(dialog.getByRole("heading", { name: /your spark is hotter/ })).toBeVisible();
    await expect(dialog.getByText("Synthetic test: well done on all of it.")).toBeVisible({
      timeout: 10_000,
    });
    await expectNoSeriousAxeIssues(one);
    await dialog.getByRole("button", { name: /to my dashboard/ }).click();
    await expect(dialog).toBeHidden();
    await one.reload();
    await expect(one.getByRole("heading", { level: 2, name: /^You're No\. \d+$/ })).toBeVisible();
    await expect(one.getByRole("dialog")).toHaveCount(0);
  });

  test("the Showcase brief, the leaderboard and the office screen", async ({ browser }) => {
    const one = await as(browser, subject.id);
    await one.goto("/my-ideas/showcase");
    await one.getByLabel("Delivery timelines").fill("Synthetic test: pilot in January, every AMC by March");
    await one.getByRole("button", { name: "Save your brief" }).click();
    await expect(one.getByRole("status")).toHaveText("Saved. The committee sees your latest version.");
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
    await expect(someone.locator(".site-header")).toHaveAttribute("inert", "");
    await expectNoSeriousAxeIssues(someone);
  });
});

test("nobody outside the committee, the CEO or admin opens the console", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/ones/console");
  await expect(page).toHaveURL((url) => url.pathname === "/");
  expect((await page.request.get("/api/ones/console")).status()).toBe(403);
});
