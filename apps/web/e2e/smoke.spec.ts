import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues } from "./helpers";

test("signed-out visitors land on sign in, which is keyboard reachable and passes axe", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/sign-in\?next=%2F/);
  await expect(page.getByRole("heading", { level: 1, name: "Sign in" })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await expectNoSeriousAxeIssues(page);
});

test("health endpoint answers 200", async ({ request }) => {
  const res = await request.get("/api/health");
  expect(res.status()).toBe(200);
  expect(await res.json()).toEqual({ status: "ok" });
});
