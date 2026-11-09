/**
 * Your lens (BLD-135): a private page for every signed-in person, linked from My ideas, counts only. The counting
 * itself is covered by the worker's stack test (test_lens_mine.py).
 */
import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

test("anyone opens their own lens from My ideas, and it passes axe", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/my-ideas");
  await page.getByRole("link", { name: /Your lens/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Your lens" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Groups you are part of" })).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});
