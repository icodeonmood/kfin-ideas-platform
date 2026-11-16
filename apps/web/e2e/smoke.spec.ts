import { expect, request as playwrightRequest, test } from "@playwright/test";

import { expectNoSeriousAxeIssues } from "./helpers";

test("signed-out visitors on a page land on sign in, which is keyboard reachable and passes axe", async ({
  page,
}) => {
  await page.goto("/my-ideas");
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fmy-ideas/);
  await expect(page.getByRole("heading", { level: 1, name: "Sign in to 1% Club" })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  await expectNoSeriousAxeIssues(page);
});

test("health endpoint answers 200", async ({ request }) => {
  const res = await request.get("/api/health");
  expect(res.status()).toBe(200);
  expect(await res.json()).toEqual({ status: "ok" });
});

test("the email marks load with no session, as a mail client fetches them", async ({ baseURL }) => {
  const fresh = await playwrightRequest.newContext({ baseURL, storageState: { cookies: [], origins: [] } });
  for (const mark of ["email-mark-ink@2x.png", "email-mark-white@2x.png"]) {
    // ink on paper, white for mail apps in dark mode (DEC-101)
    const res = await fresh.get(`/brand/${mark}`, { maxRedirects: 0 });
    expect(res.status(), mark).toBe(200);
    expect(res.headers()["content-type"]).toContain("image/png");
  }
  await fresh.dispose();
});
