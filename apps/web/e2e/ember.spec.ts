/**
 * The Ember, private points and the journey page (BLD-128, BLD-130): the screens load for the people who may
 * see them, send everyone else home, keep drafts out of sight, and pass axe. The flows themselves are covered by
 * the worker's stack tests (test_ember.py, test_points.py).
 */
import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, openAccountMenu, PERSONAS, signIn } from "./helpers";

test("everyone reads The Ember's archive; only the chair and admins write it, and only they see it in the account menu (BLD-D021)", async ({
  page,
}) => {
  await signIn(page, PERSONAS.contributor);
  await openAccountMenu(page);
  // Everyone else reads it from the Wall's Ember section (S-WALL.ember); the archive itself stays open to all.
  await expect(page.locator(".acct-menu")).toBeVisible();
  await expect(page.locator(".acct-menu").getByRole("link", { name: "The Ember", exact: true })).toHaveCount(
    0,
  );
  await page.keyboard.press("Escape");
  await page.goto("/ember");
  await expect(page.getByRole("heading", { level: 1, name: "The Ember" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Work on this month's issue" })).toHaveCount(0);
  await expectNoSeriousAxeIssues(page);
  await page.goto("/ember/compose");
  await expect(page).toHaveURL(/\/home$/); // sent home (Home is S-03 at /home, BLD-C143)
});

test("an admin opens Write The Ember", async ({ page }) => {
  await signIn(page, PERSONAS.admin);
  await page.goto("/ember/compose");
  await expect(page.getByRole("heading", { level: 1, name: /Write The Ember/ })).toBeVisible();
  // The demo draft's note waits for the chair's approval, so there is nothing to send yet (BLD-134).
  await expect(page.getByRole("button", { name: "Send to everyone" })).toHaveCount(0);
  await expectNoSeriousAxeIssues(page);
});

test("the journey page explains the steps", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/journey");
  await expect(page.getByRole("heading", { level: 1, name: "How an idea becomes a One" })).toBeVisible();
  await expect(page.getByRole("img", { name: /orange spark landing/ })).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});
