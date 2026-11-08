/**
 * The review console in the browser (B6, AT-B6-02): a colleague's idea reaches the queue; the reviewer opens it
 * and sees the person's words beside the confirmed canvas with provenance marks, the proposals with confidence,
 * the candidates and the history; a decision saves. axe clean on the queue and the item screen.
 */
import { expect, test } from "@playwright/test";

import { QUESTIONS } from "../src/lib/canvas/model";
import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

test("a reviewer opens an item, sees every panel and saves a decision (AT-B6-02)", async ({
  browser,
}, testInfo) => {
  test.setTimeout(90_000);
  const ctxA = await browser.newContext();
  const a = await ctxA.newPage();
  await signIn(a, PERSONAS.contributor);
  await a.goto("/share");
  await a.getByRole("button", { name: "Start a quick capture" }).click();
  await a.waitForURL(/\/share\/[0-9a-f-]{36}$/);
  const words = `Courier slips for NAV files are signed twice at the ${testInfo.project.name} desk, adding a day each week.`;
  await a.getByLabel(QUESTIONS.quick_noticed.label).fill(words);
  await a
    .getByRole("group", { name: QUESTIONS.quick_who.label })
    .getByRole("checkbox", { name: "Investors" })
    .check();
  await a
    .getByRole("group", { name: new RegExp(QUESTIONS.quick_value.label) })
    .getByRole("radio", { name: "Not sure yet" })
    .check();
  for (const label of [/no investor or customer personal data/, /my own work/, /I accept the terms/]) {
    await a.getByRole("checkbox", { name: label }).check();
  }
  await a.getByRole("button", { name: "Share your idea" }).click();
  await a.waitForURL(/\/done$/);
  const ideaId = /IDEA-\d{4}-\d{6}/.exec(await a.getByRole("heading", { level: 1 }).innerText())![0];
  await expect(a.getByRole("heading", { level: 3, name: "Your summary is ready" })).toBeVisible({
    timeout: 20_000,
  });
  await a.getByRole("button", { name: "Looks right" }).click();
  await a.getByRole("button", { name: /share mine as a new idea|Share my idea/ }).click();
  await expect(a.getByRole("heading", { level: 3, name: "Your idea is with the review desk" })).toBeVisible();
  await ctxA.close();

  const ctxR = await browser.newContext();
  const r = await ctxR.newPage();
  await signIn(r, PERSONAS.reviewer);
  await r.goto("/review");
  await expectNoSeriousAxeIssues(r);
  await r.getByRole("link", { name: ideaId }).click();
  await r.waitForURL(/\/review\/\d+$/);
  for (const panel of ["Submission", "Proposals", "Evidence", "History", "Actions"]) {
    await expect(r.getByRole("heading", { level: 2, name: panel })).toBeVisible();
  }
  await expect(r.locator(".original")).toContainText("Courier slips for NAV files");
  await expect(r.getByText("(from the person)").first()).toBeVisible();
  await expect(r.getByText(/\(suggested/).first()).toBeVisible(); // suggested, or suggested and accepted
  await expect(r.getByText(/confidence 0\.\d/).first()).toBeVisible();
  await expectNoSeriousAxeIssues(r);
  // A hold asks first (B6 review): one click alone never takes an idea out of the queue.
  await r.getByRole("button", { name: "Hold as spam" }).click();
  await expect(r.getByRole("button", { name: "Yes, hold as spam" })).toBeVisible();
  await expectNoSeriousAxeIssues(r);
  await r.getByRole("button", { name: "Cancel" }).click();
  await expect(r.getByRole("button", { name: "Hold as spam" })).toBeVisible();
  await r.getByRole("button", { name: "Save decision" }).click();
  await expect(r.getByRole("status").filter({ hasText: "Decision saved" })).toBeVisible();
  await expect(r.getByText("This item has been decided.")).toBeVisible();
  await ctxR.close();
});
