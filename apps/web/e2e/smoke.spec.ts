import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("home page loads, is keyboard reachable and has no serious or critical axe issues", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(blocking.map((v) => v.id)).toEqual([]);
});

test("health endpoint answers 200", async ({ request }) => {
  const res = await request.get("/api/health");
  expect(res.status()).toBe(200);
  expect(await res.json()).toEqual({ status: "ok" });
});
