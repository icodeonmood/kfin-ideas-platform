import AxeBuilder from "@axe-core/playwright";
import { expect, type Browser, type Page } from "@playwright/test";
import { Client } from "pg";

/** Personas from `make seed` (BLD-039). */
export const PERSONAS = {
  contributor: "SYN-00017",
  reviewer: "SYN-00002",
  core: "SYN-00007",
  admin: "SYN-00001",
} as const;

/** Where this run's stack listens (`make e2e` passes both from `.env`; BLD-200). */
const WEB_HOST = new URL(process.env.E2E_BASE_URL || "http://localhost:3000").host;
const OIDC_AUTHORIZE = `${(process.env.OIDC_ISSUER || "http://localhost:8090/default").replace(/\/$/, "")}/authorize`;

/** Real sign-in through the mock IdP's form; accepts the privacy notice if it is shown. */
export async function signIn(page: Page, username: string, claims?: Record<string, string>) {
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in with your KFintech account" }).click();
  await page.waitForURL((url) => url.href.startsWith(OIDC_AUTHORIZE));
  await page.locator('input[name="username"]').fill(username);
  if (claims) await page.locator('textarea[name="claims"]').fill(JSON.stringify(claims));
  await page.locator('input[type="submit"]').click();
  await page.waitForURL((url) => url.host === WEB_HOST && !url.pathname.startsWith("/auth/"));
  if (new URL(page.url()).pathname === "/privacy-notice") {
    await page.getByRole("button", { name: /I have read this/ }).click();
    await page.waitForURL((url) => url.pathname !== "/privacy-notice");
  }
}

export async function expectNoSeriousAxeIssues(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
  expect(blocking, `axe on ${page.url()}`).toEqual([]);
}

/**
 * Quick capture's one confirmation (DEC-094): a single tick covers the three declarations. The category is
 * optional and saved as "Not sure yet", and nothing else is required, so this is all a quick share needs after the
 * box is filled.
 */
export async function confirmQuickCapture(page: Page) {
  await page.getByRole("checkbox", { name: /in this idea or its files, it is my own work/ }).check();
}

export type SwitchState = "on" | "off";

/**
 * Set a kill switch through the admin screen, as an admin would, and return the state it was in, so a test can put
 * it back exactly as it found it (`finally`). Since DEC-088 every feature starts on, so a test must never leave a
 * switch off just because it once was the default.
 */
export async function setSwitch(browser: Browser, name: string, state: SwitchState): Promise<SwitchState> {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await signIn(page, PERSONAS.admin);
  await page.goto("/admin");
  const row = page.getByRole("row", { name: new RegExp(name.replaceAll(".", "\\.")) });
  const action = state === "on" ? "Switch on" : "Switch off";
  const toggle = row.getByRole("button", { name: `${action}: ${name}` });
  await expect(row).toBeVisible(); // the row is there before we read which button it offers
  let before: SwitchState = state;
  if (await toggle.isVisible()) {
    before = state === "on" ? "off" : "on";
    await toggle.click();
    await row.getByLabel("Reason for this change").fill(`e2e test: ${name} ${state}`);
    await row.getByRole("button", { name: action, exact: true }).click();
    await expect(row.getByText(state === "on" ? "On" : "Off", { exact: true })).toBeVisible();
  }
  await ctx.close();
  return before;
}

/** Put switches back as `setSwitch` found them, newest first, trying every one even if one fails. */
export async function restoreSwitches(browser: Browser, before: Array<[string, SwitchState]>): Promise<void> {
  let first: unknown;
  for (const [name, state] of [...before].reverse()) {
    try {
      await setSwitch(browser, name, state);
    } catch (e) {
      first ??= e;
    }
  }
  if (first) throw first;
}

export async function navLabels(page: Page): Promise<string[]> {
  return page.getByRole("navigation", { name: "Main" }).getByRole("link").allInnerTexts();
}

/** The dev database (`make e2e` passes it from `.env`; BLD-200). Read-only use: tests only wait on it. */
const DATABASE_URL =
  process.env.E2E_DATABASE_URL || "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable";

/** Whether a kill switch is on, read from the dev database (one row; writes nothing). */
export async function switchIsOn(name: string): Promise<boolean> {
  const client = new Client({ connectionString: DATABASE_URL });
  await client.connect();
  try {
    const { rows } = await client.query("SELECT state FROM kill_switches WHERE name = $1", [name]);
    return rows[0]?.state === "on";
  } finally {
    await client.end();
  }
}

/**
 * Wait until the search index holds an idea's card (repo writer, then indexer), instead of a fixed sleep: under
 * load the two together can take longer than any fixed wait, and usually take far less. Reads one row; writes
 * nothing.
 */
export async function waitUntilIndexed(ideaId: string, timeoutMs = 45_000): Promise<void> {
  const client = new Client({ connectionString: DATABASE_URL });
  await client.connect();
  try {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const { rowCount } = await client.query(
        "SELECT 1 FROM ideas i JOIN chunks c ON c.repo_path = i.repo_path AND c.file_type = 'idea' " +
          "WHERE i.idea_id = $1 LIMIT 1",
        [ideaId],
      );
      if (rowCount) return;
      if (Date.now() > deadline) throw new Error(`${ideaId} was not indexed within ${timeoutMs / 1000} s`);
      await new Promise((r) => setTimeout(r, 500));
    }
  } finally {
    await client.end();
  }
}
