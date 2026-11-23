/**
 * Lane D's phone QA of BLD-B275 on BLD-D028 (S-R3, C-PHONE-TABS.dock, F-SPACE.cta). QA BRANCH ONLY, NEVER MERGED: it
 * takes screenshots of the Answer screen at 360 and 320 px and measures the "+", its focus ring and a file row against
 * the dock, so lane D can check the layout on CI instead of the demo database. Synthetic data only.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Browser, type Page } from "@playwright/test";
import { Client } from "pg";

import { PERSONAS, signIn } from "./helpers";

const DATABASE_URL =
  process.env.E2E_DATABASE_URL || "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable";
const SHOTS = join(__dirname, "..", "test-results", "qa-shots");
/** The global focus ring (offer.css :focus-visible): 2px wide, 3px off the edge. */
const RING = 5;

async function db<T>(fn: (c: Client) => Promise<T>): Promise<T> {
  const c = new Client({ connectionString: DATABASE_URL });
  await c.connect();
  try {
    return await fn(c);
  } finally {
    await c.end();
  }
}

/** As review-desk.spec.ts: sign a persona in and return their contributor code (one is made if they have none). */
async function person(browser: Browser, persona: string): Promise<{ page: Page; code: string }> {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await signIn(page, persona);
  const me = (await (await page.request.get("/api/me")).json()) as { email: string };
  const code = await db(async (c) => {
    const u = await c.query<{ id: string }>("SELECT id FROM users WHERE email = $1", [me.email]);
    const userId = u.rows[0]!.id;
    await c.query(
      "INSERT INTO contributor_map (contributor_code, user_id) VALUES ('CTR-' || substr(md5(random()::text), 1, 6), $1) " +
        "ON CONFLICT (user_id) DO NOTHING",
      [userId],
    );
    const m = await c.query<{ contributor_code: string }>(
      "SELECT contributor_code FROM contributor_map WHERE user_id = $1",
      [userId],
    );
    return m.rows[0]!.contributor_code;
  });
  return { page, code };
}

/** As review-desk.spec.ts: a shared idea on the desk for `code`, with its sharer as crew lead. */
async function sharedIdea(code: string, title: string): Promise<string> {
  return db(async (c) => {
    const r = await c.query<{ idea_id: string; id: string }>(
      "INSERT INTO ideas (idea_id, contributor_code, status, title, summary, often, affects, area, city, kind, " +
        "shared_at, decide_by, edit_closes_at) VALUES (next_idea_ref(), $1, 'with_review_desk', $2, $3, " +
        "'About 40 calls a day at one branch.', ARRAY['Investors'], 'Investor service', 'Hyderabad', 'problem', " +
        "now(), now() + interval '5 days', now() + interval '3 days') RETURNING idea_id, id",
      [code, title, "Investors call the branch because the rejection SMS gives a code, not a reason."],
    );
    await c.query(
      "INSERT INTO crew_members (idea_uuid, contributor_code, role, via) VALUES ($1, $2, 'lead', 'shared')",
      [r.rows[0]!.id, code],
    );
    return r.rows[0]!.idea_id;
  });
}

type Box = { top: number; bottom: number; left: number; right: number; height: number; width: number };
type Geo = {
  vw: number;
  vh: number;
  scrollY: number;
  scrollMax: number;
  sideways: number;
  dockInSlot: boolean;
  dockH: string;
  dataDock: boolean;
  mainPad: string;
  dock: Box | null;
  plus: Box | null;
  focused: { name: string; box: Box } | null;
  sheet: Box | null;
  rows: Box[];
};

/** Where the dock, the "+", the focused element, the sheet and each file row are on the screen now. */
function geo(page: Page): Promise<Geo> {
  return page.evaluate(() => {
    const box = (el: Element | null) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height, width: r.width };
    };
    const html = document.documentElement;
    const dock = document.querySelector('[role="group"][aria-label="Move between questions"]');
    const main = document.querySelector("main#main");
    const active = document.activeElement;
    return {
      vw: window.innerWidth,
      vh: window.innerHeight,
      scrollY: window.scrollY,
      scrollMax: html.scrollHeight - window.innerHeight,
      sideways: html.scrollWidth - html.clientWidth,
      dockInSlot: !!dock?.parentElement?.matches("main#main > .dock-root"),
      dockH: html.style.getPropertyValue("--dock-h"),
      dataDock: html.hasAttribute("data-dock"),
      mainPad: main ? getComputedStyle(main).paddingBottom : "",
      dock: box(dock),
      plus: box(document.querySelector('button[aria-label="Attach files to this answer"]')),
      focused:
        active && active !== document.body
          ? { name: active.getAttribute("aria-label") ?? active.textContent?.trim() ?? "", box: box(active)! }
          : null,
      sheet: box(document.querySelector(".panel.ans-sheet")),
      rows: [...document.querySelectorAll('[aria-label="Your files"] li')].map((li) => box(li)!),
    };
  });
}

/** Tab forward until the focused element's name matches, at most 40 presses. */
async function tabTo(page: Page, name: RegExp): Promise<void> {
  for (let i = 0; i < 40; i++) {
    await page.keyboard.press("Tab");
    const now = await page.evaluate(() => document.activeElement?.getAttribute("aria-label") ?? "");
    if (name.test(now)) return;
  }
  throw new Error(`Tab never reached ${name}`);
}

test("QA (lane D, never merged): S-R3 on a phone with BLD-D028's dock, C-PHONE-TABS.dock, F-SPACE.cta, WCAG 2.4.7, 1.4.10", async ({
  browser,
}, testInfo) => {
  test.skip(testInfo.project.name !== "phone-360", "phone only");
  test.setTimeout(120_000);
  mkdirSync(SHOTS, { recursive: true });
  const NAME = "branch-call-log.md";
  const log: Record<string, Geo> = {};
  const sharer = await person(browser, PERSONAS.contributor);
  const reviewer = await person(browser, PERSONAS.reviewer);
  const ideaId = await sharedIdea(sharer.code, `Rejection SMS gives a code only (lane D QA ${Date.now()})`);
  const sent = await reviewer.page.request.post(`/api/desk/ideas/${ideaId}/question-sets`, {
    data: {
      questions: [{ part: "evidence", text: "Can you add the branch call log for last week?" }],
      time_to_answer: "3d",
    },
  });
  expect(sent.status()).toBe(201);

  const s = sharer.page;
  await s.setViewportSize({ width: 360, height: 740 });
  await s.goto(`/ideas/${ideaId}/answer`);
  const plus = s.getByRole("button", { name: "Attach files to this answer" });
  await expect(plus).toBeVisible();
  await expect(s.locator("html[data-dock]")).toHaveCount(1);

  // 1. On arrival: the dock in the shell's slot, fixed at the foot, --dock-h its own height
  const arrive = (log["01-arrive-360"] = await geo(s));
  await s.screenshot({ path: join(SHOTS, "01-arrive-360.png") });
  expect.soft(arrive.vw).toBe(360);
  expect.soft(arrive.dockInSlot, "the dock is in main#main > .dock-root").toBe(true);
  expect
    .soft(Math.abs((arrive.dock?.bottom ?? 0) - arrive.vh), "the dock sits on the screen's foot")
    .toBeLessThan(1);
  expect.soft(arrive.dockH).toBe(`${Math.ceil(arrive.dock?.height ?? 0)}px`);

  // 2. Scrolled to the foot: the "+" and the sheet end above the dock
  await s.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  const foot = (log["02-foot-360"] = await geo(s));
  await s.screenshot({ path: join(SHOTS, "02-foot-360.png") });
  expect.soft(foot.plus!.bottom, 'the "+" ends above the dock').toBeLessThanOrEqual(foot.dock!.top);
  expect.soft(foot.sheet!.bottom, "the sheet ends above the dock").toBeLessThanOrEqual(foot.dock!.top);

  // 3. From the top by keyboard: the browser scrolls the focused "+" and its ring clear of the dock
  await s.evaluate(() => window.scrollTo(0, 0));
  await tabTo(s, /^Attach files to this answer$/);
  const focus = (log["03-plus-focus-360"] = await geo(s));
  await s.screenshot({ path: join(SHOTS, "03-plus-focus-360.png") });
  expect
    .soft(focus.focused!.box.bottom + RING, 'the "+"\'s ring ends above the dock')
    .toBeLessThanOrEqual(focus.dock!.top);
  expect.soft(focus.focused!.box.top - RING).toBeGreaterThanOrEqual(0);

  // 4. A file picked: its row, and its Remove reached by keyboard, clear of the dock
  const chooser = s.waitForEvent("filechooser");
  await plus.click();
  await (
    await chooser
  ).setFiles({ name: NAME, mimeType: "text/markdown", buffer: Buffer.from("The call log for week 47.") });
  const row = s.getByRole("list", { name: "Your files" }).getByRole("listitem").filter({ hasText: NAME });
  await expect(row.getByText("Checked", { exact: true })).toBeVisible({ timeout: 30_000 });
  await s.evaluate(() => window.scrollTo(0, 0));
  await tabTo(s, new RegExp(`^Remove ${NAME.replace(".", "\\.")}$`));
  const file = (log["04-file-row-360"] = await geo(s));
  await s.screenshot({ path: join(SHOTS, "04-file-row-360.png") });
  expect
    .soft(file.focused!.box.bottom + RING, "Remove's ring ends above the dock")
    .toBeLessThanOrEqual(file.dock!.top);
  await s.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  const fileFoot = (log["05-file-foot-360"] = await geo(s));
  await s.screenshot({ path: join(SHOTS, "05-file-foot-360.png") });
  for (const r of fileFoot.rows)
    expect.soft(r.bottom, "each file row ends above the dock").toBeLessThanOrEqual(fileFoot.dock!.top);

  // 5. At 320 px (WCAG 1.4.10): no sideways scroll, the dock still on the foot and within the screen
  await s.setViewportSize({ width: 320, height: 640 });
  await s.evaluate(() => window.scrollTo(0, 0));
  await expect(plus).toBeVisible();
  const narrow = (log["06-arrive-320"] = await geo(s));
  await s.screenshot({ path: join(SHOTS, "06-arrive-320.png") });
  await s.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  const narrowFoot = (log["07-foot-320"] = await geo(s));
  await s.screenshot({ path: join(SHOTS, "07-foot-320.png") });
  expect.soft(narrow.sideways, "no sideways scroll at 320").toBeLessThanOrEqual(0);
  expect.soft(narrow.dock!.right).toBeLessThanOrEqual(320);
  expect.soft(narrowFoot.plus!.bottom).toBeLessThanOrEqual(narrowFoot.dock!.top);
  for (const r of narrowFoot.rows) expect.soft(r.bottom).toBeLessThanOrEqual(narrowFoot.dock!.top);

  writeFileSync(join(SHOTS, "s-r3-phone.json"), JSON.stringify(log, null, 2));
});
