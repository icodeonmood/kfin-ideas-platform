/**
 * The Ember, private points and the journey page (BLD-128, BLD-130): the screens load for the people who may
 * see them, send everyone else home, keep drafts out of sight, and pass axe. The flows themselves are covered by
 * the worker's stack tests (test_ember.py, test_points.py).
 */
import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, openAccountMenu, PERSONAS, signIn } from "./helpers";

test("everyone reads The Ember's archive from the account menu; only the chair and admins write it", async ({
  page,
}) => {
  await signIn(page, PERSONAS.contributor);
  await openAccountMenu(page);
  await page.getByRole("link", { name: "The Ember" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "The Ember" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Work on this month's issue" })).toHaveCount(0);
  await expectNoSeriousAxeIssues(page);
  await page.goto("/ember/compose");
  await expect(page).toHaveURL(/\/$/); // sent home
});

test("an admin opens Write The Ember", async ({ page }) => {
  await signIn(page, PERSONAS.admin);
  await page.goto("/ember/compose");
  await expect(page.getByRole("heading", { level: 1, name: /Write The Ember/ })).toBeVisible();
  // The demo draft's note waits for the chair's approval, so there is nothing to send yet (BLD-134).
  await expect(page.getByRole("button", { name: "Send to everyone" })).toHaveCount(0);
  await expectNoSeriousAxeIssues(page);
});

test("My ideas shows your own points, and the journey page explains the steps", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/my-ideas");
  await expect(page.getByRole("heading", { level: 2, name: "Your points" })).toBeVisible();
  await expect(page.getByText("Only you see your points.")).toBeVisible();
  await page.getByRole("link", { name: "How an idea becomes a One" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "How an idea becomes a One" })).toBeVisible();
  await expect(page.getByRole("img", { name: /orange spark landing/ })).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});
