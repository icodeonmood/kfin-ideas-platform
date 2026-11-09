/**
 * Delivery, lenses and learning (BLD-115 to BLD-122): the screens load for the people who may see them, send
 * everyone else home, say what is coming soon, and pass axe. The flows themselves are covered by the worker's
 * stack tests (services/worker/tests/test_delivery.py) and the demo tour.
 */
import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

test("the admin sees Delivery, Lenses and Learning, each with its coming-soon notes", async ({ page }) => {
  await signIn(page, PERSONAS.admin);
  await page.goto("/delivery");
  await expect(page.getByRole("heading", { level: 1, name: "Delivery" })).toBeVisible();
  await expect(page.getByText("Live sync with the delivery pipeline: coming soon")).toBeVisible();
  await expectNoSeriousAxeIssues(page);

  await page.goto("/lenses");
  await expect(page.getByRole("heading", { level: 1, name: "Lenses" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "People around each group" })).toBeVisible();
  // BLD-139: the real section, with approved themes or "No approved themes yet." (the demo seeds one set).
  const themes = page.getByRole("heading", { level: 3, name: "Recurring friction themes for each role" });
  await expect(themes).toBeVisible();
  await expect(
    page
      .getByText("No approved themes yet.")
      .or(page.getByRole("table", { name: /friction themes by role/ })),
  ).toBeVisible();
  await expect(page.getByText("Recurring friction themes for each role: coming soon")).toHaveCount(0);
  await expectNoSeriousAxeIssues(page);

  await page.goto("/admin");
  await page.getByRole("link", { name: "Learning reports and proposals" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Learning" })).toBeVisible();
  await expect(page.getByText("Switching a kind to automatic: off at launch")).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});

test("an employee sees only their own deliveries and is sent home from Lenses and Learning", async ({
  page,
}) => {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/delivery");
  await expect(page.getByRole("heading", { level: 2, name: "Your deliveries" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Picked, waiting for a handover" })).toHaveCount(
    0,
  );
  await expectNoSeriousAxeIssues(page);
  for (const path of ["/lenses", "/learning"]) {
    await page.goto(path);
    await expect(page).toHaveURL((url) => url.pathname === "/");
  }
  const res = await page.request.get("/api/lenses");
  expect(res.status()).toBe(403);
});

test("a delivery that is not yours is not found", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  const res = await page.request.get("/api/delivery/999999999");
  expect(res.status()).toBe(404);
  expect(await res.json()).toEqual({ error: "not_found" });
});
