/**
 * S-ONE (a One's dashboard, /one) and S-H6 (Profile and settings, /profile), lane E: V-ACC.visual/4 (axe and reflow
 * on every listed state), keyboard order and focus (V-ACC.visual/11), the field rules of V-FIELDS.one, and the
 * empty, error and moment states S-ONE.md and S-H6.md list. J-ONE/4 and J-ONE/6 hand-offs are lane G's journeys; the
 * same steps are checked here on this suite's own fixtures.
 *
 * Fixtures: synthetic people from `make seed` (never the pack's demo cast, non-negotiable 11). A test makes its
 * person a One straight in the dev database the way the worker reads it (`ones`, `one_number_history`, and for the
 * moment a carried-out `tier_up` with its `one_glow_ups` row), and removes it after itself; settings rows are put
 * back as they were. Each Playwright worker takes its own person, so parallel tests never share one.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { Client } from "pg";

import { expectNoSeriousAxeIssues, openAccountMenu, PERSONAS, signIn, switchIsOn } from "./helpers";

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

/** The first row, which the query always returns. */
async function row<T>(text: string, values: unknown[] = []): Promise<T> {
  const [first] = await sql<T>(text, values);
  if (!first) throw new Error("expected a row");
  return first;
}

const isPhone = (info: TestInfo) => info.project.name !== "desktop";

type Synthetic = { emp: string; name: string; email: string };

/** The synthetic HR file `make seed` loads; personas and the first managers (below 60) are left alone. */
function syntheticPeople(): Synthetic[] {
  const csv = readFileSync(path.resolve(process.cwd(), "../../.data/hr/synthetic-hr.csv"), "utf8");
  return csv
    .trim()
    .split("\n")
    .slice(1)
    .map((line) => line.split(","))
    .map(([emp, name, email]) => ({ emp: emp!, name: name!, email: email! }))
    .filter((p) => Number(p.emp.slice(4)) >= 60)
    .sort((a, b) => b.emp.localeCompare(a.emp)); // from the top, away from the old Ones suite's picks
}

type Me = { id: string; name: string; emp: string };

/** Signs `page` in as this worker's own synthetic person, one who is not a One. */
async function signInFresh(page: Page, info: TestInfo): Promise<Me> {
  const people = syntheticPeople();
  for (let attempt = 0; attempt < 6; attempt++) {
    const p = people[(info.parallelIndex * 6 + attempt) % people.length]!;
    const one = await sql(
      "SELECT 1 FROM ones o JOIN users u ON u.id = o.user_id WHERE lower(u.email) = lower($1)",
      [p.email],
    );
    if (one.length) continue;
    await signIn(page, p.emp);
    const body = (await (await page.request.get("/api/me/profile")).json()) as {
      person: { id: string; name: string };
    };
    return { id: body.person.id, name: body.person.name, emp: p.emp };
  }
  throw new Error("no synthetic person left who is not a One");
}

const FREE = `SELECT g FROM generate_series(600, 999) AS g
  WHERE g NOT IN (SELECT number FROM ones WHERE number IS NOT NULL)
    AND g NOT IN (SELECT number FROM one_number_history WHERE rests_until > now())
    AND g NOT IN (SELECT number FROM one_legend_numbers)
  ORDER BY random() LIMIT 1`;

/** The figures a shipped fix's team entered, as the worker stores a One's own measures (synthetic). */
const MEASURES = {
  time: { amount: 620, unit: "hours a month", line: "Fewer bounced-debit cases" },
  money: { amount: 1_800_000, unit: "rupees a year", finance_confirmed: true },
  effort: { amount: 3, unit: "fewer steps", line: "Per new mandate" },
  scale: { amount: 41, unit: "branches", line: "Using it every day" },
};

type One = { oneId: string; number: number };

/** Makes `userId` an active One: inducted 2 days ago with the number window open, or 40 days ago with it closed. */
async function makeOne(
  userId: string,
  o: { tier: number; open?: boolean; measures?: object; glowFrom?: number } = { tier: 1 },
): Promise<One> {
  for (let attempt = 0; ; attempt++) {
    try {
      const { n } = await row<{ n: number }>("SELECT next_number('ONE', '') AS n");
      const { g } = await row<{ g: number }>(FREE);
      const open = o.open ?? true;
      const { id } = await row<{ id: string }>(
        `INSERT INTO ones (induction_no, user_id, number, way_in, tier, measures, inducted_at, swap_until)
         VALUES ($1, $2, $3, 'sponsored', $4, $5, now() - $6::interval, now() + $7::interval) RETURNING id`,
        [
          n,
          userId,
          g,
          o.tier,
          JSON.stringify(o.measures ?? {}),
          open ? "2 days" : "40 days",
          open ? "28 days" : "-10 days",
        ],
      );
      await sql(
        "INSERT INTO one_number_history (one_id, number, how, from_at) VALUES ($1, $2, 'allocated', now())",
        [id, g],
      );
      if (o.glowFrom) {
        const { pid } = await row<{ pid: string }>(
          `INSERT INTO one_proposals (kind, one_id, subject_user_id, tier_to, proposed_by, state, approval,
             decided_by, decided_at, carried_out_by, carried_out_at)
           VALUES ('tier_up', $1, $2, $3, $2, 'carried_out', 'chair', $2, now(), $2, now()) RETURNING id AS pid`,
          [id, userId, o.tier],
        );
        await sql(
          "INSERT INTO one_glow_ups (one_id, proposal_id, tier_from, tier_to) VALUES ($1, $2, $3, $4)",
          [id, pid, o.glowFrom, o.tier],
        );
      }
      return { oneId: id, number: g };
    } catch (e) {
      if (attempt >= 3) throw e; // a number or a person taken in the same moment by another test: try again
    }
  }
}

/** Removes the One and all that hangs off it (history, moment, proposal, Showcase brief cascade with it). */
async function dropOne(one: One | undefined) {
  if (one) await sql("DELETE FROM ones WHERE id = $1", [one.oneId]);
}

/** The person's settings rows as they are, to put back after a test that flips switches: a row that was there gets
 * its values back, a row the test made goes. */
async function keepSettings(userId: string): Promise<() => Promise<void>> {
  const before = new Map<string, Record<string, unknown> | undefined>();
  for (const table of ["person_settings", "comms_prefs"]) {
    const [r] = await sql<{ r: Record<string, unknown> }>(
      `SELECT row_to_json(t) AS r FROM ${table} t WHERE user_id = $1`,
      [userId],
    );
    before.set(table, r?.r);
  }
  return async () => {
    for (const [table, row] of before) {
      if (!row) {
        await sql(`DELETE FROM ${table} WHERE user_id = $1`, [userId]);
        continue;
      }
      const cols = Object.keys(row).filter((c) => c !== "user_id");
      await sql(
        `INSERT INTO ${table} SELECT * FROM json_populate_record(null::${table}, $1)
         ON CONFLICT (user_id) DO UPDATE SET ${cols.map((c) => `${c} = EXCLUDED.${c}`).join(", ")}`,
        [row],
      );
    }
  };
}

/** Another person, not a One, to hold a number the test then asks for. */
async function someoneElse(not: string): Promise<string> {
  const [row] = await sql<{ id: string }>(
    "SELECT id FROM users WHERE active AND id <> $1 AND id NOT IN (SELECT user_id FROM ones) ORDER BY random() LIMIT 1",
    [not],
  );
  return row!.id;
}

/** The accessible names of what has focus, one Tab after another (V-ACC.visual/11, F-A11Y). */
async function tabNames(page: Page, count: number): Promise<string[]> {
  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    await page.keyboard.press("Tab");
    out.push(
      await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el) return "";
        const label = (el as HTMLInputElement).labels?.[0]?.textContent;
        if (label) return label.replace(/\s+/g, " ").trim();
        const by = el.getAttribute("aria-labelledby");
        if (by)
          return by
            .split(" ")
            .map((id) => document.getElementById(id)?.textContent?.trim() ?? "")
            .join(" ");
        return (el.getAttribute("aria-label") || el.textContent || "").replace(/\s+/g, " ").trim();
      }),
    );
  }
  return out;
}

// --- S-ONE ---------------------------------------------------------------------------------------------------------

test.describe("S-ONE, a One's dashboard", () => {
  let one: One | undefined;
  let other: One | undefined;
  test.afterEach(async () => {
    await dropOne(one);
    await dropOne(other);
    one = undefined;
    other = undefined;
  });

  test("V-ACC.visual/4 S-ONE.layout: the hero, Your number, Your impact brief, Impact so far and More for Ones, axe clean", async ({
    page,
  }, info) => {
    const me = await signInFresh(page, info);
    one = await makeOne(me.id, { tier: 4, measures: MEASURES });
    await page.goto("/one");
    const main = page.locator("main");
    await expect(
      page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "My ideas" }),
    ).toHaveAttribute("href", "/my-ideas");
    await expect(page.getByRole("navigation", { name: "Breadcrumb" })).toContainText("Your One dashboard");
    const h1 = page.getByRole("heading", { level: 1, name: `You're No. ${one.number}` });
    await expect(h1).toBeVisible();
    await expect(main.getByText(/^Tier 4, Blaze\. One since \d{1,2} [A-Z][a-z]{2} \d{4}\.$/)).toBeVisible();
    await expect(main.getByText(`Your number ${one.number}`)).toBeVisible();
    await expect(main.getByText(me.name, { exact: true })).toBeVisible();

    await expect(page.getByRole("heading", { level: 2, name: "Your number" })).toBeVisible();
    await expect(
      main.getByText(
        new RegExp(
          `^Keep No\\. ${one.number}, or choose any free number from 1 to 999 until \\d{1,2} [A-Z][a-z]{2} \\d{4}\\. First come, first served\\. After that, it's yours\\.$`,
        ),
      ),
    ).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Number you'd like" })).toHaveValue(String(one.number));
    await expect(page.getByRole("button", { name: "Save my number" })).toBeVisible();

    // Empty: no approved brief yet (BLD-E041); the button to propose one is there.
    await expect(page.getByRole("heading", { level: 2, name: "Your impact brief" })).toBeVisible();
    await expect(main.getByText("No brief on the Wall yet.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Propose a new brief" })).toBeVisible();

    await expect(page.getByRole("heading", { level: 2, name: "Impact so far" })).toBeVisible();
    await expect(main.getByText("Measured 30 and 90 days after your idea ships.")).toBeVisible();
    for (const words of [
      "620 hours a month",
      "Fewer bounced-debit cases",
      "₹18 lakh a year",
      "Finance confirmed",
      "3 fewer steps",
      "Per new mandate",
      "41 branches",
      "Using it every day",
    ])
      await expect(main.getByText(words, { exact: true })).toBeVisible();

    await expect(page.getByRole("heading", { level: 2, name: "More for Ones" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Your Showcase brief" })).toBeVisible();
    await expect(page.getByRole("link", { name: "The Ones leaderboard" })).toHaveAttribute(
      "href",
      "/wall?ones=leaderboard#ones",
    );
    await expect(page.getByRole("dialog")).toHaveCount(0);

    // S-ONE.rules/5: one column on a phone, the hero first.
    if (isPhone(info)) {
      const hero = await main.locator(".on-jersey").boundingBox();
      const head = await h1.boundingBox();
      expect(hero!.y).toBeLessThan(head!.y);
    }
    await expectNoSeriousAxeIssues(page);
  });

  test("L-IMPACT/4 S-ONE.states: a measure not in yet reads Being measured", async ({ page }, info) => {
    const me = await signInFresh(page, info);
    one = await makeOne(me.id, { tier: 1, measures: { time: MEASURES.time } });
    await page.goto("/one");
    await expect(page.getByText("620 hours a month", { exact: true })).toBeVisible();
    await expect(page.locator("main").getByText("Being measured", { exact: true })).toHaveCount(3);
    await expectNoSeriousAxeIssues(page);
  });

  test("S-ONE.rules/1 BLD-E040: someone who is not a One goes to Profile, and only a One's menu lists the dashboard", async ({
    page,
  }, info) => {
    const me = await signInFresh(page, info);
    await page.goto("/one");
    await expect(page).toHaveURL(/\/profile$/);
    await expect(page.getByRole("heading", { level: 1, name: me.name })).toBeVisible();
    await page.goto("/");
    await openAccountMenu(page);
    await expect(page.getByRole("link", { name: "Your profile and settings" })).toHaveAttribute(
      "href",
      "/profile",
    );
    await expect(page.getByRole("link", { name: "Your One dashboard" })).toHaveCount(0);

    one = await makeOne(me.id, { tier: 2 });
    await page.goto("/");
    await openAccountMenu(page);
    await expect(page.getByRole("link", { name: "Your One dashboard" })).toHaveAttribute("href", "/one");
    await page.getByRole("link", { name: "Your One dashboard" }).click();
    await expect(page.getByRole("heading", { level: 1, name: `You're No. ${one.number}` })).toBeVisible();
  });

  test("J-ONE/4 V-FIELDS.one/1-2 S-ONE.layout/3: inside 30 days the One keeps or swaps the number", async ({
    page,
  }, info) => {
    const me = await signInFresh(page, info);
    one = await makeOne(me.id, { tier: 1 });
    other = await makeOne(await someoneElse(me.id), { tier: 1 });
    await page.goto("/one");
    const field = page.getByRole("textbox", { name: "Number you'd like" });
    const save = page.getByRole("button", { name: "Save my number" });

    await field.fill("0");
    await save.click();
    await expect(page.getByText("Pick a number from 1 to 999.")).toBeVisible();
    await expect(field).toBeFocused();
    await expect(field).toHaveAttribute("aria-invalid", "true");

    await field.fill(String(other.number));
    await save.click();
    await expect(
      page.getByText(
        new RegExp(`^No\\. ${other.number} is taken\\. Free numbers near it: \\d+, \\d+, \\d+\\.$`),
      ),
    ).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: `You're No. ${one.number}` })).toBeVisible();
    await expectNoSeriousAxeIssues(page);

    const { g } = await row<{ g: number }>(FREE);
    await field.fill(String(g));
    await save.click();
    await expect(page.getByRole("heading", { level: 1, name: `You're No. ${g}` })).toBeVisible();
    await expect(page.getByText(/is taken/)).toHaveCount(0);
    await expect(page.getByText(new RegExp(`^Keep No\\. ${g}, or choose`))).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: `You're No. ${g}` })).toBeVisible();
    await expect(field).toHaveValue(String(g));
  });

  test("V-FIELDS.one/3: once the 30 days are over the field is replaced by the number for good", async ({
    page,
  }, info) => {
    const me = await signInFresh(page, info);
    one = await makeOne(me.id, { tier: 3, open: false });
    await page.goto("/one");
    await expect(page.getByText(`No. ${one.number} is yours for good.`, { exact: true })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Number you'd like" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Save my number" })).toHaveCount(0);
    await expectNoSeriousAxeIssues(page);
  });

  test("J-ONE/4 L-ONES.rules/5 V-FIELDS.one/4: the One proposes a new brief for the programme team", async ({
    page,
  }, info) => {
    const me = await signInFresh(page, info);
    one = await makeOne(me.id, { tier: 1 });
    await page.goto("/one");
    const open = page.getByRole("button", { name: "Propose a new brief" });
    await open.click();
    const box = page.getByRole("textbox", { name: "Your new brief" });
    await expect(box).toBeFocused();
    await page.getByRole("button", { name: "Cancel" }).click();
    await expect(open).toBeFocused();

    await open.click();
    await box.fill("Too short.");
    await expect(page.getByText("10 of 140 characters")).toBeVisible();
    await page.getByRole("button", { name: "Send for approval" }).click();
    await expect(page.getByText("Keep it to one sentence, up to 140 characters.")).toBeVisible();
    await expect(box).toBeFocused();
    await expectNoSeriousAxeIssues(page);

    await box.fill("Synthetic test teams stop reprocessing mandate forms by hand.");
    await page.getByRole("button", { name: "Send for approval" }).click();
    await expect(
      page.getByRole("status").filter({
        hasText: "Your new brief is with the programme team. It goes on the Wall once they approve it.",
      }),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Propose a new brief" })).toBeFocused();
    await page.reload();
    await expect(
      page.getByText("Your new brief is with the programme team. It goes on the Wall once they approve it."),
    ).toBeVisible();
  });

  test("J-ONE/6 S-ONE.states showGlowUp S-ONE.rules/3 V-ACC.visual/11: a tier rise plays its moment once", async ({
    page,
  }, info) => {
    const me = await signInFresh(page, info);
    one = await makeOne(me.id, { tier: 2, glowFrom: 1, measures: { time: MEASURES.time } });
    await page.goto("/one");
    const moment = page.getByRole("dialog", { name: `No. ${one.number}, your spark is hotter` });
    await expect(moment).toBeVisible();
    await expect(moment).toContainText("Tier 1, Spark to Tier 2, Glow");
    await expect(moment).toContainText("From Tier 1, Spark to Tier 2, Glow");
    await expect(moment).toContainText("Your story so far");
    for (const label of ["Ideas shared", "Picked or being built", "Shipped"])
      await expect(moment.getByText(label, { exact: true })).toBeVisible();
    await expect(moment.getByRole("heading", { level: 2 })).toBeFocused();
    await expectNoSeriousAxeIssues(page);

    // Escape closes it; focus comes back to the page's heading; the dashboard shows the new tier.
    await page.keyboard.press("Escape");
    await expect(moment).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 1, name: `You're No. ${one.number}` })).toBeFocused();
    await expect(page.locator("main").getByText(/^Tier 2, Glow\. One since/)).toBeVisible();
    await expect(page.getByText("620 hours a month", { exact: true })).toBeVisible();

    // It never plays again (marked seen as it showed).
    await expect
      .poll(
        async () =>
          (await sql("SELECT 1 FROM one_glow_ups WHERE one_id = $1 AND seen_at IS NULL", [one!.oneId]))
            .length,
      )
      .toBe(0);
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: `You're No. ${one.number}` })).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("S-ONE.rules/3 F-MOTION/4: under reduced motion the moment appears already settled; Back to my dashboard closes it", async ({
    page,
  }, info) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    const me = await signInFresh(page, info);
    one = await makeOne(me.id, { tier: 5, glowFrom: 4 });
    await page.goto("/one");
    const moment = page.getByRole("dialog", { name: `No. ${one.number}, your spark is hotter` });
    await expect(moment).toBeVisible();
    await expect(moment).toContainText("From Tier 4, Blaze to Tier 5, White heat");
    const moving = await moment.evaluate(
      (el) => el.getAnimations({ subtree: true }).filter((a) => a.playState === "running").length,
    );
    expect(moving).toBe(0);
    await moment.getByRole("button", { name: "Back to my dashboard" }).click();
    await expect(moment).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 1, name: `You're No. ${one.number}` })).toBeFocused();
  });

  test("BLD-E042 V-ACC.visual/11: Your Showcase brief opens as a sheet, saves, and Escape returns focus", async ({
    page,
  }, info) => {
    const me = await signInFresh(page, info);
    one = await makeOne(me.id, { tier: 1 });
    await page.goto("/one");
    const opener = page.getByRole("button", { name: "Your Showcase brief" });

    // Error: the brief cannot be read.
    await page.route("**/api/me/one/showcase", (r) =>
      r.request().method() === "GET"
        ? r.fulfill({ status: 503, json: { error: "showcase_unavailable" } })
        : r.fallback(),
    );
    await opener.click();
    const sheet = page.getByRole("dialog", { name: "Your Showcase brief" });
    await expect(
      sheet.getByText("We can't load your Showcase brief just now. Please try again in a minute."),
    ).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(sheet).toHaveCount(0);
    await expect(opener).toBeFocused();
    await page.unroute("**/api/me/one/showcase");

    await opener.click();
    await expect(sheet.getByRole("heading", { level: 2, name: "Your Showcase brief" })).toBeFocused();
    for (const label of [
      "The idea",
      "Proposed impact",
      "Current progress",
      "Impact created so far",
      "Delivery timelines",
      "The team, or your solo profile",
      "Help or sponsorship needed",
    ])
      await expect(sheet.getByRole("textbox", { name: new RegExp(`^${label}`) })).toBeVisible();
    await sheet
      .getByRole("textbox", { name: /^Delivery timelines/ })
      .fill("Synthetic test: pilot in January, every AMC by March");
    await expectNoSeriousAxeIssues(page);
    await sheet.getByRole("button", { name: "Save your brief" }).click();
    await expect(sheet.getByRole("status")).toHaveText("Saved. The committee sees your latest version.");
    await sheet.getByRole("button", { name: "Close" }).click();
    await expect(sheet).toHaveCount(0);
    await expect(opener).toBeFocused();
  });

  test("V-ACC.visual/11 F-A11Y: the keyboard walks the dashboard in reading order", async ({
    page,
  }, info) => {
    test.skip(isPhone(info), "the reading order is the same; the desktop run checks it");
    const me = await signInFresh(page, info);
    one = await makeOne(me.id, { tier: 1 });
    await page.goto("/one");
    await page.locator("main").getByRole("link", { name: "My ideas" }).focus();
    expect(await tabNames(page, 5)).toEqual([
      "Number you'd like",
      "Save my number",
      "Propose a new brief",
      "Your Showcase brief",
      "The Ones leaderboard",
    ]);
    // Enter in the field saves, as a form does.
    await page.getByRole("textbox", { name: "Number you'd like" }).fill("0");
    await page.keyboard.press("Enter");
    await expect(page.getByText("Pick a number from 1 to 999.")).toBeVisible();
  });
});

// --- S-H6 ----------------------------------------------------------------------------------------------------------

test.describe("S-H6, Profile and settings", () => {
  let one: One | undefined;
  let putBack: (() => Promise<void>) | undefined;
  test.afterEach(async () => {
    await dropOne(one);
    one = undefined;
    await putBack?.();
    putBack = undefined;
  });

  test("V-ACC.visual/4 S-H6.layout: the head, Your points, On the Wall and How we reach you, axe clean", async ({
    page,
  }, info) => {
    const me = await signInFresh(page, info);
    await page.goto("/profile");
    await expect(page.getByRole("heading", { level: 1, name: me.name })).toBeVisible();
    await expect(
      page
        .locator("main")
        .getByText(/Tier \d, [A-Z][a-z ]+\.$/)
        .first(),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Your One dashboard" })).toHaveCount(0);

    await expect(page.getByRole("heading", { level: 2, name: "Your points" })).toBeVisible();
    await expect(page.locator(".pf-num")).toHaveText(/^\d[\d,]*$/);
    await expect(
      page.getByText("Only you see your points. They never decide who becomes a One."),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "How points and tiers work" })).toHaveAttribute(
      "href",
      "/how-it-works",
    );

    await expect(page.getByRole("heading", { level: 2, name: "On the Wall" })).toBeVisible();
    const wall = page.getByRole("switch", { name: "Show my name next to my ideas" });
    await expect(wall).toHaveAttribute("aria-checked", "true");
    await expect(wall).toHaveAccessibleDescription(
      "Your name shows on the Wall next to your shared ideas. It applies to every idea you share, and you can change it here any time.",
    );

    await expect(page.getByRole("heading", { level: 2, name: "How we reach you" })).toBeVisible();
    const email = page.getByRole("switch", { name: "Email" });
    await expect(email).toHaveAttribute("aria-checked", "true");
    await expect(email).toHaveAccessibleDescription("The same updates, for your records.");
    const reminders = page.getByRole("switch", { name: "Reminders before a question is due" });
    await expect(reminders).toHaveAccessibleDescription("A day before, and again two hours before.");
    const teams = page.getByRole("switch", { name: /^Teams messages/ });
    await expect(teams).toHaveAccessibleDescription(
      "When the review desk asks you something, or one of your ideas moves a stage.",
    );
    if (!(await switchIsOn("comms.teams"))) {
      // DEC-105: Teams waits on IT. The switch shows, off, and cannot be turned on.
      await expect(teams).toHaveAttribute("aria-disabled", "true");
      await expect(teams).toHaveAttribute("aria-checked", "false");
      await expect(page.getByText("Coming soon")).toBeVisible();
      await teams.focus();
      await page.keyboard.press("Space");
      await expect(teams).toHaveAttribute("aria-checked", "false");
    }
    await expectNoSeriousAxeIssues(page);
  });

  test("S-H6.rules/1-2, 5: each switch saves at once, says its new state and keeps it", async ({
    page,
  }, info) => {
    const me = await signInFresh(page, info);
    putBack = await keepSettings(me.id);
    await page.goto("/profile");
    const wall = page.getByRole("switch", { name: "Show my name next to my ideas" });
    await wall.click();
    await expect(wall).toHaveAttribute("aria-checked", "false");
    const hidden =
      "Your ideas show on the Wall without your name. It applies to every idea you share, and you can change it here any time.";
    await expect(page.getByRole("status").filter({ hasText: hidden })).toBeVisible();
    await expect(wall).toHaveAccessibleDescription(hidden);
    await expectNoSeriousAxeIssues(page);

    const email = page.getByRole("switch", { name: "Email" });
    await email.focus();
    await page.keyboard.press("Space");
    await expect(email).toHaveAttribute("aria-checked", "false");
    await expect
      .poll(
        async () =>
          (await sql<{ email: boolean }>("SELECT email FROM comms_prefs WHERE user_id = $1", [me.id]))[0]
            ?.email,
      )
      .toBe(false);

    await page.reload();
    await expect(wall).toHaveAttribute("aria-checked", "false");
    await expect(email).toHaveAttribute("aria-checked", "false");
    await expect(page.getByRole("button", { name: /^Save/ })).toHaveCount(0); // no Save button (S-H6.rules/1)
    await wall.click();
    await expect(wall).toHaveAttribute("aria-checked", "true");
    // The save has landed before the settings are put back
    await expect
      .poll(
        async () =>
          (
            await sql<{ v: boolean }>(
              "SELECT show_name_on_wall AS v FROM person_settings WHERE user_id = $1",
              [me.id],
            )
          )[0]?.v,
      )
      .toBe(true);
  });

  test("S-H6.rules/1 V-FIELDS.one/5: a failed save flips the switch back with the message under it", async ({
    page,
  }, info) => {
    await signInFresh(page, info);
    await page.goto("/profile");
    await page.route("**/api/me/settings", (r) =>
      r.fulfill({
        status: 503,
        json: { error: { code: "try_again", message: "Couldn't save that. Try again.", field: "reminders" } },
      }),
    );
    const reminders = page.getByRole("switch", { name: "Reminders before a question is due" });
    await reminders.click();
    await expect(page.getByText("Couldn't save that. Try again.")).toBeVisible();
    await expect(reminders).toHaveAttribute("aria-checked", "true");
    await expect(reminders).toHaveAccessibleDescription(
      "A day before, and again two hours before. Couldn't save that. Try again.",
    );
    await expectNoSeriousAxeIssues(page);
  });

  test("S-H6.rules/4: a One sees a link to their One dashboard", async ({ page }, info) => {
    const me = await signInFresh(page, info);
    one = await makeOne(me.id, { tier: 2 });
    await page.goto("/profile");
    await expect(page.locator("main").getByText(/Tier 2, Glow\.$/)).toBeVisible();
    const link = page.getByRole("link", { name: "Your One dashboard" });
    await expect(link).toHaveAttribute("href", "/one");
    await link.click();
    await expect(page.getByRole("heading", { level: 1, name: `You're No. ${one.number}` })).toBeVisible();
  });

  test("DEC-108 BLD-E043: How should we refer to you? saves at once on lane C's contract", async ({
    page,
  }, info) => {
    await signInFresh(page, info);
    const sent: unknown[] = [];
    let fail = false;
    await page.route("**/api/me/refer-as", async (r) => {
      if (r.request().method() === "GET") return r.fulfill({ json: { refer_as: "unset" } });
      const body = r.request().postDataJSON() as { refer_as: string };
      sent.push(body);
      if (fail) return r.fulfill({ status: 400, json: { error: "refer_as_invalid" } });
      return r.fulfill({ json: { refer_as: body.refer_as } });
    });
    await page.goto("/profile");
    const group = page.getByRole("radiogroup", { name: "How should we refer to you?" });
    await expect(page.getByRole("heading", { level: 2, name: "How should we refer to you?" })).toBeVisible();
    await expect(
      page.getByText("We use this only to word the English copy of your voice notes."),
    ).toBeVisible();
    await expect(group.getByRole("radio", { name: "Prefer not to say" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    await group.getByRole("radio", { name: "They" }).click();
    await expect(group.getByRole("radio", { name: "They" })).toHaveAttribute("aria-checked", "true");
    await expect.poll(() => sent).toEqual([{ refer_as: "they" }]);
    await expectNoSeriousAxeIssues(page);

    fail = true;
    await group.getByRole("radio", { name: "She" }).click();
    await expect(page.getByText("Couldn't save that. Try again.")).toBeVisible();
    await expect(group.getByRole("radio", { name: "They" })).toHaveAttribute("aria-checked", "true");
  });

  test("BLD-E043: until lane C's route answers, the question stays out of the way", async ({
    page,
  }, info) => {
    await signInFresh(page, info);
    await page.route("**/api/me/refer-as", (r) => r.fulfill({ status: 404, json: { error: "not_found" } }));
    await page.goto("/profile");
    await expect(page.getByRole("heading", { level: 2, name: "How we reach you" })).toBeVisible();
    await expect(page.getByRole("radiogroup", { name: "How should we refer to you?" })).toHaveCount(0);
  });

  test("V-ACC.visual/11 S-H6.rules/5: the keyboard walks Profile in reading order", async ({
    page,
  }, info) => {
    test.skip(isPhone(info), "the reading order is the same; the desktop run checks it");
    await signInFresh(page, info);
    await page.route("**/api/me/refer-as", (r) => r.fulfill({ status: 404, json: {} }));
    await page.goto("/profile");
    await page.getByRole("link", { name: "How points and tiers work" }).focus();
    const names = await tabNames(page, 4);
    expect(names).toEqual([
      "Show my name next to my ideas",
      expect.stringMatching(/^Teams messages/),
      "Email",
      "Reminders before a question is due",
    ]);
  });
});

// Kept apart: the contributor persona is never a One in the seed.
test("S-ONE.rules/1: the contributor persona is sent from /one to Profile", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/one");
  await expect(page).toHaveURL(/\/profile$/);
  await expect(page.getByRole("heading", { level: 2, name: "Your points" })).toBeVisible();
});
