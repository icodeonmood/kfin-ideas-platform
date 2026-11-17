/**
 * Messages (B6, AT-B6-08 in the browser): after sharing an idea the person finds "Your idea is in" in Messages,
 * can open it by keyboard, and it is marked read. axe clean.
 */
import { expect, test } from "@playwright/test";

import { shareQuickly, expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

test("the submitted message lands in Messages and opens by keyboard", async ({ page }) => {
  test.setTimeout(60_000);
  await signIn(page, PERSONAS.contributor);
  const shared = await shareQuickly(
    page,
    "Mandate scans are re-uploaded twice because the first upload times out on slow branch links.",
  );
  await page.goto(`/share/${shared}/done`);
  await page.waitForURL(/\/done$/);
  const ideaId = /IDEA-\d{4}-\d{6}/.exec(await page.getByRole("heading", { level: 1 }).innerText())![0];
  await expect(page.getByRole("heading", { level: 3, name: "Your summary is ready" })).toBeVisible({
    timeout: 20_000,
  });
  await page.getByRole("button", { name: "Looks right" }).click();
  await page.getByRole("button", { name: /share mine as a new idea|Share my idea/ }).click();
  await expect(
    page.getByRole("heading", { level: 3, name: "Your idea is with the review desk" }),
  ).toBeVisible();

  await expect(async () => {
    await page.goto("/inbox");
    await expect(page.getByRole("button", { name: new RegExp(`Your idea is in: ${ideaId}`) })).toBeVisible({
      timeout: 1_000,
    });
  }).toPass({ timeout: 20_000 }); // the comms job routes within a couple of seconds
  await expectNoSeriousAxeIssues(page);
  const subject = page.getByRole("button", { name: new RegExp(`Your idea is in: ${ideaId}`) });
  await subject.focus();
  await page.keyboard.press("Enter");
  await expect(subject).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByText(/What happens next/).first()).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});
