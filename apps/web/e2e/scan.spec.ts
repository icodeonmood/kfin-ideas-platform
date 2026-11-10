/**
 * The scan in the browser (B4): the waiting screen names each step and ends in a plain-words outcome
 * (AT-B4-09/10 screens), the redirect card offers "No, this is an idea" with a reason (AT-B4-07 screens), and
 * any gatekeeper block, investor ones included, offers "This is not personal data" (BLD-082 option B).
 * axe runs on each state. Fake mode: keyword rules pick the outcome (BLD-073).
 */
import { expect, test, type Page } from "@playwright/test";

import { QUESTIONS } from "../src/lib/canvas/model";
import { confirmQuickCapture, expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

async function quickCapture(page: Page, noticed: string) {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/share");
  await page.getByRole("button", { name: "Start a quick capture" }).click();
  await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
  await page.getByLabel(QUESTIONS.quick_noticed.label).fill(noticed);
  await confirmQuickCapture(page);
  await page.getByRole("button", { name: "Share your idea" }).click();
  await page.waitForURL(/\/done$/);
}

test("the waiting screen ends with the summary and suggestions (AT-B4-09 screen)", async ({ page }) => {
  await quickCapture(
    page,
    "Branch staff photocopy every SIP mandate twice before couriering it, which costs a day for each batch.",
  );
  await expect(page.getByRole("heading", { level: 2, name: "Where your idea is now" })).toBeVisible();
  const ready = page.getByRole("heading", { level: 3, name: "Your summary is ready" });
  await expect(ready).toBeVisible({ timeout: 20_000 });
  await expect(ready).toBeFocused();
  await expect(page.getByText("We suggested answers for some questions you left blank:")).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});

test("an IT issue gets a redirect card, and 'No, this is an idea' carries on (AT-B4-07 screen)", async ({
  page,
}) => {
  await quickCapture(
    page,
    "My laptop VPN is not working since Monday and IT has not called me back about it.",
  );
  const card = page.getByRole("heading", { level: 3, name: "Where to take this: IT helpdesk" });
  await expect(card).toBeVisible({ timeout: 20_000 });
  await expectNoSeriousAxeIssues(page);
  await page.getByRole("button", { name: "No, this is an idea" }).click();
  await page.getByLabel("Tell us why it is an idea").fill("Too short");
  await page.getByRole("button", { name: "Carry on with my idea" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "at least 15 characters" })).toBeVisible();
  await page
    .getByLabel("Tell us why it is an idea")
    .fill("VPN drops cost the whole ops floor about two hours every day");
  await page.getByRole("button", { name: "Carry on with my idea" }).click();
  await expect(page.getByRole("heading", { level: 3, name: "Your summary is ready" })).toBeVisible({
    timeout: 20_000,
  });
  await expectNoSeriousAxeIssues(page);
});

test("an investor block can be contested and the idea carries on (BLD-082 option B)", async ({ page }) => {
  await quickCapture(
    page,
    "The investor Pranav Menon called five times because the SIP registration slipped twice this month.",
  );
  const blocked = page.getByRole("heading", { level: 3, name: "Please take out some details first" });
  await expect(blocked).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: "Edit my idea" })).toBeVisible();
  await expect(page.getByText("the review desk checks these details first")).toBeVisible();
  await expectNoSeriousAxeIssues(page);
  await page.getByRole("button", { name: "This is not personal data" }).click();
  await expect(page.getByRole("heading", { level: 3, name: "Your summary is ready" })).toBeVisible({
    timeout: 20_000,
  });
  await expectNoSeriousAxeIssues(page);
});
