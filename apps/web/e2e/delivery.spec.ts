/**
 * Delivery (BLD-115 to BLD-122): the screens load for the people who may see them, say what is coming soon, and
 * pass axe. Lenses and learning are retired (DEC-106, R12, R13). The flows themselves are covered by the worker's
 * stack tests (services/worker/tests/test_delivery.py) and the demo tour.
 */
import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

test("the admin sees Delivery with its coming-soon note", async ({ page }) => {
  await signIn(page, PERSONAS.admin);
  await page.goto("/delivery");
  await expect(page.getByRole("heading", { level: 1, name: "Delivery" })).toBeVisible();
  await expect(page.getByText("Live sync with the delivery pipeline: coming soon")).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});

test("an employee sees only their own deliveries", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/delivery");
  await expect(page.getByRole("heading", { level: 2, name: "Your deliveries" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Picked, waiting for a handover" })).toHaveCount(
    0,
  );
  await expectNoSeriousAxeIssues(page);
});

test("a delivery that is not yours is not found", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  const res = await page.request.get("/api/delivery/999999999");
  expect(res.status()).toBe(404);
  expect(await res.json()).toEqual({ error: "not_found" });
});
