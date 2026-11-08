import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

/** Personas from `make seed` (BLD-039). */
export const PERSONAS = {
  contributor: "SYN-00017",
  reviewer: "SYN-00002",
  core: "SYN-00007",
  admin: "SYN-00001",
} as const;

/** Real sign-in through the mock IdP's form; accepts the privacy notice if it is shown. */
export async function signIn(page: Page, username: string, claims?: Record<string, string>) {
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in with your KFintech account" }).click();
  await page.waitForURL(/localhost:8090\/default\/authorize/);
  await page.locator('input[name="username"]').fill(username);
  if (claims) await page.locator('textarea[name="claims"]').fill(JSON.stringify(claims));
  await page.locator('input[type="submit"]').click();
  await page.waitForURL((url) => url.host === "localhost:3000" && !url.pathname.startsWith("/auth/"));
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
