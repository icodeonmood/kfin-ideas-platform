/**
 * Weekly grouping in the browser (§4.4 B): an admin switches `clusters.batch` on; two colleagues' ideas that say
 * the same thing are reviewed; the desk runs the grouping, opens the proposal, sees every panel and approves it.
 * axe clean on the queue panel and the proposal screen, at desktop width and at 360 px.
 *
 * Desktop project only: a second run started by the phone project at the same time would replace this run's
 * proposals (a new run supersedes open ones), so the 360 px check is done inside this test.
 */
import { expect, test, type Page } from "@playwright/test";

import { QUESTIONS } from "../src/lib/canvas/model";
import { expectNoSeriousAxeIssues, PERSONAS, setSwitch, signIn, waitUntilIndexed } from "./helpers";
import { nameTheGroup, openProposalHolding, runGroupingNow } from "./proposals";
import { withSwitchLock } from "./switch-lock";

async function share(page: Page, words: string): Promise<string> {
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
  return ideaId;
}

test("the desk runs the weekly grouping and approves a proposal", async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "one run at a time; the 360 px check is inside");
  test.setTimeout(900_000); // includes waiting for committee.spec, which flips the same switch
  await withSwitchLock("clusters.batch", async () => {
    // Ordinary office words picked at random for this run, with little shared filler, so the dev database's
    // earlier runs never group with these two (dev embeddings measure word overlap, BLD-003) and nothing reads
    // as a name to the personal-data checks.
    const vocab = ["ledger", "voucher", "mandate", "payout", "register", "cheque", "courier", "stamp", "receipt",
    "batch", "slip", "tray", "binder", "scanner", "printer", "envelope", "token", "queue", "drawer", "stapler",
    "folder", "ribbon", "barcode", "label", "tally", "roster", "docket", "challan", "manifest", "bundle", "carton",
    "seal", "clip", "pouch", "logbook", "almirah", "dispatch", "acknowledgement", "photocopy", "signature"]; // prettier-ignore
    let seed = Date.now();
    const pick = () => {
      seed = (seed * 1103515245 + 12345) % 2147483648;
      return vocab.splice(seed % vocab.length, 1)[0];
    };
    const made = Array.from({ length: 7 }, pick);
    const words = (where: string) =>
      `${made.join(" ")} pile up at the ${where} counter; ${made.slice(0, 4).join(" ")} again tomorrow.`;

    const before = await setSwitch(browser, "clusters.batch", "on");
    try {
      const ctxA = await browser.newContext();
      const a = await ctxA.newPage();
      await signIn(a, PERSONAS.contributor);
      const first = await share(a, words("Hyderabad"));
      const second = await share(a, words("Chennai"));
      await ctxA.close();

      const ctxR = await browser.newContext();
      const r = await ctxR.newPage();
      await signIn(r, PERSONAS.reviewer);
      for (const ideaId of [first, second]) {
        await r.goto("/review");
        await r.getByRole("link", { name: ideaId }).click();
        await r.waitForURL(/\/review\/\d+$/);
        await r.getByRole("button", { name: "Save decision" }).click();
        await expect(r.getByRole("status").filter({ hasText: "Decision saved" })).toBeVisible();
      }

      // The ideas reach the index through the repo writer within seconds; the run is a background job.
      await r.goto("/review");
      await expect(r.getByRole("heading", { level: 2, name: "Weekly grouping" })).toBeVisible();
      await expectNoSeriousAxeIssues(r);
      // Switch states are cached for 10 seconds (BLD-006): press until the desk confirms a run.
      // A run only takes ideas already in the index: wait for both, or the run can start without them.
      for (const ideaId of [first, second]) await waitUntilIndexed(ideaId);
      await runGroupingNow(r);
      await openProposalHolding(r, [first, second]);
      await r.waitForURL(/\/review\/clusters\/\d+$/);
      for (const panel of ["What the batch found", "Suggested summary", "Members", "Actions"]) {
        await expect(r.getByRole("heading", { level: 2, name: panel })).toBeVisible();
      }
      for (const ideaId of [first, second]) {
        await expect(r.getByRole("link", { name: ideaId })).toBeVisible();
      }
      await expectNoSeriousAxeIssues(r);
      await nameTheGroup(r, "Ledger matched by hand");
      await r.getByRole("button", { name: "Approve this group" }).click();
      await expect(
        r.getByRole("status").filter({ hasText: /Approved\. The group is CL-\d{4}\./ }),
      ).toBeVisible();
      await expect(r.getByText(/This proposal was approved: CL-\d{4}/)).toBeVisible();
      await expectNoSeriousAxeIssues(r);
      await r.setViewportSize({ width: 360, height: 740 });
      await expectNoSeriousAxeIssues(r);
      await r.goto("/review");
      await expectNoSeriousAxeIssues(r);
      await ctxR.close();
    } finally {
      await setSwitch(browser, "clusters.batch", before); // as we found it (DEC-088)
    }
  });
});
