/**
 * The Ones, end to end (DEC-034 to DEC-087): the programme team marks a Founding One on lane A's admin path (the
 * console and the proposals API are retired, DEC-106, R21, BLD-E049); the committee writes a few words at
 * /ones/write/:id and a tier up plays the glow-up once on S-ONE with them; the One's Showcase brief and the
 * committee's printable copy at /ones/showcase/:id (mapping/screens.md:111-112); the home carousel and the office
 * screen. axe on every page. Synthetic people only: each run picks a synthetic employee who is not a One yet.
 *
 * With the proposals API gone, the tier up the committee writes for is put straight in the dev database the way the
 * worker reads it (`one_proposals`, then for the moment `one_glow_ups`), as one-profile.spec.ts does.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Browser, type Page } from "@playwright/test";
import { Client } from "pg";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

const DATABASE_URL =
  process.env.E2E_DATABASE_URL || "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable";

async function sql<T = Record<string, unknown>>(text: string, values: unknown[] = []): Promise<T[]> {
  const client = new Client({ connectionString: DATABASE_URL });
  await client.connect();
  try {
    return (await client.query(text, values)).rows as T[];
  } finally {
    await client.end();
  }
}

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

/** The signed-in person's own user id. */
async function userId(page: Page): Promise<string> {
  const body = (await (await page.request.get("/api/me/profile")).json()) as { person: { id: string } };
  return body.person.id;
}

/** Marks a synthetic person who is not a One yet as a Founding One on the admin path (lane A, DEC-106). */
async function markSomeone(admin: Page): Promise<{ person: Person; oneId: number; userId: string }> {
  const people = syntheticPeople().sort(() => Math.random() - 0.5);
  for (const person of people.slice(0, 25)) {
    const already = await sql(
      "SELECT 1 FROM ones o JOIN users u ON u.id = o.user_id WHERE lower(u.email) = lower($1)",
      [person.email],
    );
    if (already.length) continue;
    const r = await api(admin, "POST", "/api/admin/ones/founding", { email: person.email });
    if (r.status === 201) return { person, oneId: Number(r.body.one_id), userId: String(r.body.user_id) };
  }
  throw new Error("no synthetic person left to mark");
}

test.describe.serial("a new One, from the admin page to the glow-up", () => {
  let subject: Person;
  let subjectId = "";
  let oneId = 0;

  // One run at a time: the projects would otherwise race to choose numbers for the same shared One.
  // The 360 px check is inside the dashboard test.
  test.beforeEach(({}, testInfo) => {
    test.skip(testInfo.project.name !== "desktop", "one run at a time; the 360 px check is inside");
  });

  test("L-ONES BLD-E049: the programme team marks a Founding One on the admin path (the proposals API is retired)", async ({
    browser,
  }) => {
    const admin = await as(browser, PERSONAS.admin);
    const marked = await markSomeone(admin);
    subject = marked.person;
    subjectId = marked.userId;
    oneId = marked.oneId;
    expect(oneId).toBeGreaterThan(0);
  });

  // A One's dashboard, their number, brief and glow-up left My ideas for S-ONE at /one (S-07 replaces the old
  // /my-ideas); their tests go with that screen.

  test("J-ONE/6 S-ONE mapping/screens.md:112: the committee writes a few words at /ones/write/:id, and the tier up plays the glow-up once on S-ONE with them", async ({
    browser,
  }) => {
    // A tier up waiting for the committee's words, as the old proposals left it (BLD-E049).
    const core = await as(browser, PERSONAS.core);
    const [made] = await sql<{ pid: number }>(
      `INSERT INTO one_proposals (kind, one_id, subject_user_id, tier_to, proposed_by, proposed_at)
       VALUES ('tier_up', $1, $2, 2, $3, now()) RETURNING id AS pid`,
      [oneId, subjectId, await userId(core)],
    );
    const pid = made!.pid;

    // Someone who is neither invited nor on the committee is told so, and gets no form.
    const someone = await as(browser, PERSONAS.contributor);
    await someone.goto(`/ones/write/${pid}`);
    await expect(someone.getByText("This invitation isn't open, or isn't for you.")).toBeVisible();
    await expect(someone.getByRole("textbox", { name: "Your message" })).toHaveCount(0);

    // The committee writes on the page.
    await core.goto(`/ones/write/${pid}`);
    await expect(core.getByRole("heading", { level: 1, name: /^A few words for / })).toBeVisible();
    await expect(core.getByText(/They are moving to Glow\./)).toBeVisible();
    await expectNoSeriousAxeIssues(core);
    await core.getByRole("textbox", { name: "Your message" }).fill("Synthetic test: well done on all of it.");
    await core.getByRole("button", { name: "Send your message" }).click();
    await expect(core.getByText("Thank you. Your message is saved.")).toBeVisible();
    await expect(core.getByRole("textbox", { name: "Your message" })).toHaveCount(0);
    await expectNoSeriousAxeIssues(core);

    // The tier rises and its moment waits on S-ONE, the way the worker records a step up.
    await sql(
      `UPDATE one_proposals SET state = 'carried_out', approval = 'chair', decided_by = proposed_by,
         decided_at = now(), carried_out_by = proposed_by, carried_out_at = now() WHERE id = $1`,
      [pid],
    );
    await sql("UPDATE ones SET tier = 2 WHERE id = $1", [oneId]);
    await sql("INSERT INTO one_glow_ups (one_id, proposal_id, tier_from, tier_to) VALUES ($1, $2, 1, 2)", [
      oneId,
      pid,
    ]);

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

  test("the home carousel and the office screen", async ({ browser }) => {
    const someone = await as(browser, PERSONAS.contributor);
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

test("L-ONES BLD-E049 (DEC-106): the Ones console, the old leaderboard and the proposals API answer not found, even for the committee and admin", async ({
  browser,
}) => {
  for (const persona of [PERSONAS.core, PERSONAS.admin]) {
    const page = await as(browser, persona);
    expect((await page.request.get("/api/ones/console")).status()).toBe(404);
    expect((await page.request.get("/api/ones/leaderboard")).status()).toBe(404);
    expect((await page.request.post("/api/ones/proposals", { data: {} })).status()).toBe(404);
    expect((await page.request.post("/api/ones/proposals/1/carry-out", { data: {} })).status()).toBe(404);
  }
});
