/**
 * Find your crew in the browser (B5): check the canvas ("Looks right"), see a colleague's matching idea as a card
 * that carries no other person's text, file or name (AT-B5-05), team up with context (AT-B5-06), and the final
 * message. axe on each state. Fake mode: the judge labels by word overlap (BLD-083).
 */
import { expect, test, type Page } from "@playwright/test";

import { QUESTIONS } from "../src/lib/canvas/model";
import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

const SHARED = "Branch staff photocopy every SIP mandate twice before couriering the batch to Hyderabad";

async function quickCapture(page: Page, persona: string, noticed: string) {
  await signIn(page, persona);
  await page.goto("/share");
  await page.getByRole("button", { name: "Start a quick capture" }).click();
  await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
  await page.getByLabel(QUESTIONS.quick_noticed.label).fill(noticed);
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
  await expect(page.getByRole("heading", { level: 3, name: "Your summary is ready" })).toBeVisible({
    timeout: 20_000,
  });
}

test("a colleague's idea shows as a card with nothing of theirs on it; teaming up (AT-B5-05, AT-B5-06)", async ({
  browser,
}, testInfo) => {
  test.setTimeout(90_000);
  const stamp = Date.now().toString(36);
  // A sentence only this run's two ideas share. Earlier runs leave many look-alike ideas in the dev database,
  // including the joiner's own (which are never shown to them); without it they can crowd this pair out of
  // the top twenty candidates.
  const pair = `q${Math.random().toString(36).slice(2, 9)}`; // never contains `stamp`, which must not leak
  const together = `Forms for ${pair} queue at the ${pair} inward desk`;
  const theirs = `${SHARED}. ${together}. Pune team note ${stamp}: forms wait in the outward register for a day.`;
  const ctxA = await browser.newContext();
  const a = await ctxA.newPage();
  await quickCapture(a, PERSONAS.contributor, theirs);
  const theirName = (await a.locator(".account-name").innerText()).trim();
  const theirId = /IDEA-\d{4}-\d{6}/.exec(await a.getByRole("heading", { level: 1 }).innerText())![0];
  await a.getByRole("button", { name: "Looks right" }).click();
  await expect(a.getByRole("heading", { level: 3, name: "Find your crew" })).toBeFocused();
  await a.getByRole("button", { name: /share mine as a new idea|Share my idea/ }).click();
  await expect(a.getByRole("heading", { level: 3, name: "Your idea is with the review desk" })).toBeVisible();
  await ctxA.close();
  await new Promise((r) => setTimeout(r, 8_000)); // repo writer (1 s) then indexer (2 s) pick the idea up

  const ctxB = await browser.newContext();
  const b = await ctxB.newPage();
  // A different colleague per viewport, so the two runs never compete for the same join.
  const joiner = testInfo.project.name === "desktop" ? PERSONAS.reviewer : PERSONAS.core;
  await quickCapture(b, joiner, `${SHARED}. ${together}, and our branch sees the same delay.`);
  await expectNoSeriousAxeIssues(b);
  await b.getByRole("button", { name: "Looks right" }).click();
  const crew = b.getByRole("heading", { level: 3, name: "Find your crew" });
  await expect(crew).toBeFocused();
  const card = b.locator(".crew-card").filter({ hasText: "colleagues are on this" }).first();
  await expect(card).toBeVisible();
  const page = await b.locator("main").innerText();
  for (const forbidden of [stamp, "outward register", theirName, theirId, "SYN-"]) {
    expect(page, `page must not show ${forbidden}`).not.toContain(forbidden);
  }
  await expectNoSeriousAxeIssues(b);

  await card.getByRole("button", { name: "Team up with my context" }).click();
  await card.getByLabel(/What does your situation add/).fill("too short");
  await card.getByRole("button", { name: "Team up with my context" }).last().click();
  await expect(b.getByRole("alert").filter({ hasText: "at least 30 characters" })).toBeVisible();
  await card
    .getByLabel(/What does your situation add/)
    .fill("Jaipur sees the same with lumpsum forms every Monday");
  await card.getByRole("button", { name: "Team up with my context" }).last().click();
  await expect(b.getByRole("heading", { level: 3, name: "You have teamed up" })).toBeFocused();
  await expectNoSeriousAxeIssues(b);
  await ctxB.close();
});
