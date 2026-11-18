/**
 * The lamp-lighting launch screen (DEC-046, DEC-050): admin only, keyboard operable, axe clean before and after
 * the reveal. Reduced motion jumps straight to the final frame; the full sequence runs on Playwright's clock.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

/** The address the stack was started with: the environment, else the repo's .env, else the dev default. */
function configuredBaseUrl(): string {
  if (process.env.APP_BASE_URL) return process.env.APP_BASE_URL;
  try {
    const env = readFileSync(path.resolve(process.cwd(), "../../.env"), "utf8");
    const m = env.match(/^APP_BASE_URL=(\S+)/m);
    if (m?.[1]) return m[1];
  } catch {
    // no .env next to the repo: the dev default below
  }
  return "http://localhost:3000";
}

test.use({ reducedMotion: "reduce" });

test("the admin runs the launch screen to the invitation and back", async ({ page }) => {
  await signIn(page, PERSONAS.admin);
  await page.goto("/launch");
  await expect(page.getByRole("heading", { level: 1, name: "Launch screen" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start" })).toBeFocused();
  await expectNoSeriousAxeIssues(page);

  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { level: 1, name: "1% Club" })).toBeVisible();
  await expect(page.getByText("1% spark. 99% sweat.", { exact: true })).toBeVisible();
  await expect(page.getByText("You bring the spark.", { exact: true })).toBeVisible();
  await expect(page.getByRole("img", { name: /^QR code for http/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Back to start" })).toBeFocused();
  await expectNoSeriousAxeIssues(page);

  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Start" })).toBeFocused();
});

test("nobody else can open the launch screen", async ({ page }) => {
  await signIn(page, PERSONAS.reviewer);
  await page.goto("/launch");
  await expect(page).toHaveURL((url) => url.pathname === "/home");
});

test.describe("the full timed sequence (review A6)", () => {
  test.use({ reducedMotion: "no-preference" });

  test("plays every step in order to the invitation, with the page behind it inert", async ({ page }) => {
    await signIn(page, PERSONAS.admin);
    await page.clock.install();
    await page.goto("/launch");
    await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0); // a wall display has no chrome
    await expect(page.locator(".skip-link")).toHaveAttribute("inert", "");
    await page.getByRole("button", { name: "Start" }).click();

    // Nothing is in the reading order before its moment.
    await expect(page.getByRole("heading", { level: 1, name: "1% Club" })).toHaveCount(0);
    await expect(page.locator(".launch-spark")).not.toHaveClass(/is-on/);

    await page.clock.runFor(4_100); // 0:04 the spark rises
    await expect(page.locator(".launch-spark")).toHaveClass(/is-on/);
    await expect(page.locator(".launch-zero").first()).not.toHaveClass(/is-on/);

    await page.clock.runFor(4_000); // 0:08 the zeros arrive
    await expect(page.locator(".launch-zero").first()).toHaveClass(/is-on/);
    await expect(page.getByRole("heading", { level: 1, name: "1% Club" })).toHaveCount(0);

    await page.clock.runFor(6_000); // 0:14 the name
    await expect(page.getByRole("heading", { level: 1, name: "1% Club" })).toBeVisible();
    await expect(page.locator(".launch-tagline")).toHaveAttribute("aria-hidden", "true");

    await page.clock.runFor(2_600); // 0:16.5 the tagline
    await expect(page.locator(".launch-tagline")).not.toHaveAttribute("aria-hidden", "true");
    await expect(page.locator(".launch-tagline")).toHaveClass(/is-on/);
    await expect(page.getByRole("img", { name: /^QR code for/ })).toHaveCount(0);

    await page.clock.runFor(14_000); // 0:30 the invitation, which stays
    const qr = page.getByRole("img", { name: /^QR code for/ });
    await expect(qr).toBeVisible();
    await expect(page.getByText("You bring the spark.", { exact: true })).toBeVisible();
    const expected = new URL(configuredBaseUrl()).toString();
    await expect(qr).toHaveAttribute("aria-label", `QR code for ${expected}`);
    if (!/localhost|127\.0\.0\.1/.test(expected)) {
      expect(await qr.getAttribute("aria-label")).not.toMatch(/localhost|127\.0\.0\.1/);
    }
    await expect(page.locator(".skip-link")).toHaveAttribute("inert", "");
    await expect(page.getByRole("button", { name: "Back to start" })).toBeFocused();
    // CSS transitions run on real time, not the test clock: let the fades finish before checking contrast.
    for (const part of [".launch-name", ".launch-tagline", ".launch-invite"]) {
      await expect(page.locator(part)).toHaveCSS("opacity", "1");
    }
    await expectNoSeriousAxeIssues(page);
  });
});
