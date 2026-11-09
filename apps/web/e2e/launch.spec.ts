/**
 * The lamp-lighting launch screen (DEC-046, DEC-050): admin only, keyboard operable, axe clean before and after
 * the reveal. Reduced motion jumps straight to the final frame, which is what this test checks.
 */
import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

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
  await expect(page).toHaveURL((url) => url.pathname === "/");
});
