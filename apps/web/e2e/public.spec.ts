/**
 * Public pages in the browser (B7, AT-B7-01/02/03/05): an idea the desk has reviewed reaches the wall as its
 * neutral summary; My ideas shows its stage and next step; the idea page shows the owner their canvas and the
 * timeline, and shows a colleague only the summary. axe clean and keyboard use on the wall, My ideas and the
 * idea page.
 */
import { expect, test, type Page } from "@playwright/test";

import { QUESTIONS } from "../src/lib/canvas/model";
import { confirmQuickCapture, expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

async function shareQuickIdea(page: Page, words: string): Promise<string> {
  await page.goto("/share");
  await page.getByRole("button", { name: "Start a quick capture" }).click();
  await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
  await page.getByLabel(QUESTIONS.quick_noticed.label).fill(words);
  await confirmQuickCapture(page);
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
  return ideaId;
}

// Its review step drove the old desk at /review ("Save decision"), retired for S-R1 and S-R2 (now a redirect to /desk);
// P-REPO.screens lists this test for a rewrite with S-06 and S-09 (lane E), so it waits for that rewrite.
test.fixme("a reviewed idea reaches the wall, My ideas and its page, each as §3.1 allows (AT-B7-01..05)", async ({
  browser,
}, testInfo) => {
  test.setTimeout(180_000);
  const words = `Branch scanners for KYC forms jam every afternoon at the ${testInfo.project.name} counter, so forms wait overnight.`;

  // The person shares an idea; My ideas shows it with the desk's due date.
  const ctxA = await browser.newContext();
  const a = await ctxA.newPage();
  await signIn(a, PERSONAS.contributor);
  const ideaId = await shareQuickIdea(a, words);
  await a.goto("/my-ideas");
  const mine = a.getByRole("listitem").filter({ hasText: ideaId });
  await expect(mine).toContainText("With the review desk");
  await expect(mine).toContainText(/The review desk decides by \w{3}, \d{1,2} \w{3},? \d{4}/);
  await expectNoSeriousAxeIssues(a);

  // The review desk accepts it.
  const ctxR = await browser.newContext();
  const r = await ctxR.newPage();
  await signIn(r, PERSONAS.reviewer);
  await r.goto("/review");
  await r.getByRole("link", { name: ideaId }).click();
  await r.getByRole("button", { name: "Save decision" }).click();
  await expect(r.getByText("This item has been decided.")).toBeVisible();
  await ctxR.close();

  // The owner opens the idea page from My ideas with the keyboard: their canvas and the timeline.
  await a.goto("/my-ideas");
  const link = a.getByRole("listitem").filter({ hasText: ideaId }).getByRole("link");
  await link.focus();
  await a.keyboard.press("Enter");
  await a.waitForURL(new RegExp(`/ideas/${ideaId}$`));
  await expect(a.getByRole("heading", { level: 2, name: "Your canvas" })).toBeVisible();
  await expect(a.getByText("Reviewed.", { exact: false }).first()).toBeVisible();
  await expect
    .poll(
      async () => {
        await a.reload();
        return a.getByText("Reviewed by the review desk").count();
      },
      { timeout: 30_000 },
    )
    .toBeGreaterThan(0); // the repo writer has written the idea file's history
  await expect(a.getByText("Shared", { exact: true })).toBeVisible();
  await expectNoSeriousAxeIssues(a);
  await ctxA.close();

  // A colleague sees it on the wall as a short summary only, and its page without the person's words.
  const ctxB = await browser.newContext();
  const b = await ctxB.newPage();
  await signIn(b, testInfo.project.name === "desktop" ? "SYN-00031" : "SYN-00032");
  await b.goto("/wall");
  await expect(b.getByRole("heading", { level: 2, name: "Recent ideas" })).toBeVisible();
  await expect(b.getByRole("heading", { level: 2, name: "Already running" })).toBeVisible();
  await expectNoSeriousAxeIssues(b);
  await expect(b.getByText(words)).toHaveCount(0);
  const onWall = b.locator(`a[href="/ideas/${ideaId}"]`);
  // Reviewed and open to everyone: on the wall as its summary (the wall is rebuilt at most every 30 seconds).
  await expect
    .poll(
      async () => {
        await b.reload();
        return onWall.count();
      },
      { timeout: 45_000, intervals: [2_000, 5_000] },
    )
    .toBe(1);
  await onWall.focus();
  await b.keyboard.press("Enter");
  await b.waitForURL(new RegExp(`/ideas/${ideaId}$`));
  await expect(b.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(b.getByText(words)).toHaveCount(0);
  await expect(b.getByRole("heading", { level: 2, name: "Your canvas" })).toHaveCount(0);
  await expect(b.getByText(/The person's own words stay with them/)).toBeVisible();
  await expectNoSeriousAxeIssues(b);
  await b.getByRole("link", { name: "Back to the wall" }).focus();
  await b.keyboard.press("Enter");
  await b.waitForURL(/\/wall$/);
  await ctxB.close();
});
