/**
 * Desk decisions and "Disagree with this?" in the browser (B6, AT-B6-06 and AT-B6-09 screens): a reviewer decides;
 * the person disagrees from their idea page; a core committee member sees the disagreement and reconsiders the
 * decision with a reason, taking the item back. axe clean.
 */
import { expect, test, type Browser } from "@playwright/test";

import { QUESTIONS } from "../src/lib/canvas/model";
import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

async function shareIdea(browser: Browser, words: string) {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await signIn(page, PERSONAS.contributor);
  await page.goto("/share");
  await page.getByRole("button", { name: "Start a quick capture" }).click();
  await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
  await page.getByLabel(QUESTIONS.quick_noticed.label).fill(words);
  await page
    .getByRole("group", { name: QUESTIONS.quick_who.label })
    .getByRole("checkbox", { name: "Investors" })
    .check();
  await page
    .getByRole("group", { name: new RegExp(QUESTIONS.quick_value.label) })
    .getByRole("radio", { name: "Not sure yet" })
    .check();
  for (const label of [/no investor or customer personal data/, /my own work/, /I accept the terms/]) {
    await page.getByRole("checkbox", { name: label }).check();
  }
  await page.getByRole("button", { name: "Share your idea" }).click();
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
  return { ctx, page, ideaId };
}

test("disagree, then the core committee reconsiders the desk's decision", async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const a = await shareIdea(
    browser,
    `Dividend warrants are re-printed by hand when the bank name changes, at the ${testInfo.project.name} centre.`,
  );

  const ctxR = await browser.newContext();
  const r = await ctxR.newPage();
  await signIn(r, PERSONAS.reviewer);
  await r.goto("/review");
  await r.getByRole("link", { name: a.ideaId }).click();
  await r.getByRole("button", { name: "Save decision" }).click();
  await expect(r.getByRole("status").filter({ hasText: "Decision saved" })).toBeVisible();
  await ctxR.close();

  await a.page.reload();
  await expect(a.page.getByRole("heading", { level: 3, name: "Your idea has been reviewed" })).toBeVisible();
  await a.page.getByRole("button", { name: "Disagree with this?" }).click();
  await a.page
    .getByLabel(/What should the committee know/)
    .fill("This also affects the SIF registry, not only MF");
  await a.page.getByRole("button", { name: "Send to the core committee" }).click();
  await expect(
    a.page.getByRole("status").filter({ hasText: "The core committee will look at it" }),
  ).toBeVisible();
  await expectNoSeriousAxeIssues(a.page);
  await a.ctx.close();

  const ctxC = await browser.newContext();
  const c = await ctxC.newPage();
  await signIn(c, PERSONAS.core);
  await c.goto("/desk-decisions");
  await expect(c.getByRole("heading", { level: 2, name: "People who disagree" })).toBeVisible();
  await expect(c.getByRole("link", { name: a.ideaId }).first()).toBeVisible();
  await expectNoSeriousAxeIssues(c);
  const card = c.locator(".crew-card").filter({ has: c.getByRole("link", { name: a.ideaId }) });
  await card.getByRole("button", { name: /Reconsider this/ }).click();
  await card.getByLabel("Why the committee should reconsider").fill("no");
  await card.getByRole("button", { name: "Take it back to decide myself" }).click();
  await expect(card.getByRole("alert")).toHaveText(/at least 10 characters/);
  await card
    .getByLabel("Why the committee should reconsider")
    .fill("The committee wants this looked at with the SIF registry work");
  await card.getByRole("button", { name: "Take it back to decide myself" }).click();
  await c.waitForURL(/\/review\/\d+$/);
  await expect(c.getByRole("button", { name: "Save decision" })).toBeVisible(); // the member now holds the item
  await ctxC.close();
});
