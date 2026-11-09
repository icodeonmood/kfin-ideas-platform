import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";
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

export async function navLabels(page: Page): Promise<string[]> {
  return page.getByRole("navigation", { name: "Main" }).getByRole("link").allInnerTexts();
}

/** The dev database (`make e2e` passes it from `.env`; BLD-200). Read-only use: tests only wait on it. */
const DATABASE_URL =
  process.env.E2E_DATABASE_URL || "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable";

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
