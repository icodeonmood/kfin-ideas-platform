/**
 * Shared steps for the committee specs (committee.spec, appeals.spec): sign in as a persona or a synthetic
 * colleague, flip a shared switch from the admin page, share an idea, choose scores, axe at both widths, and the long
 * road from two shared ideas to a revealed preliminary review.
 */
import { expect, type Browser, type Page } from "@playwright/test";

import { QUESTIONS } from "../src/lib/canvas/model";
import { confirmQuickCapture, expectNoSeriousAxeIssues, PERSONAS, signIn, waitUntilIndexed } from "./helpers";

export { setSwitch } from "./helpers";
import { nameTheGroup, openProposalHolding, runGroupingNow } from "./proposals";

export const CHAIR = "SYN-00006";
export const MEMBERS = ["SYN-00007", "SYN-00008", "SYN-00009", "SYN-00010"];

export async function as(browser: Browser, who: string): Promise<{ page: Page; close: () => Promise<void> }> {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await signIn(page, who);
  return { page, close: () => ctx.close() };
}

export async function share(page: Page, words: string): Promise<string> {
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

/** Every score is a choice (nothing is pre-selected): the suggested financial level where there is one. */
export async function chooseScores(page: Page, submit: string, value: string) {
  const form = page.locator("form").filter({ has: page.getByRole("button", { name: submit }) });
  for (const group of await form.getByRole("group").all()) {
    const hint = /suggested: (\d)/.exec(await group.innerText());
    await group.getByRole("radio", { name: hint ? hint[1] : value, exact: true }).check();
  }
}

export async function axeBoth(page: Page) {
  await expectNoSeriousAxeIssues(page);
  const size = page.viewportSize();
  await page.setViewportSize({ width: 360, height: 740 });
  await expectNoSeriousAxeIssues(page);
  if (size) await page.setViewportSize(size);
}

/** Ordinary office words picked at random for this run, so earlier runs' ideas group apart from these. */
export function officeWords(salt: number): (where: string) => string {
  const vocab = ["ledger", "voucher", "mandate", "payout", "register", "cheque", "courier", "stamp", "receipt", "batch",
    "slip", "tray", "binder", "scanner", "printer", "envelope", "token", "queue", "drawer", "stapler", "folder", "ribbon",
    "barcode", "label", "tally", "roster", "docket", "challan", "manifest", "bundle", "carton", "seal"]; // prettier-ignore
  let seed = Date.now() + salt;
  const pick = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return vocab.splice(seed % vocab.length, 1)[0];
  };
  const made = Array.from({ length: 7 }, pick);
  return (where: string) =>
    `${made.join(" ")} pile up at the ${where} counter; ${made.slice(0, 4).join(" ")} again tomorrow.`;
}

/**
 * Two colleagues share, the desk reviews and groups their ideas, qualifies the group, the chair opens a cycle and
 * every member scores it at `value`. Returns once the chair sees the revealed round. With `axe`, the qualify page,
 * the committee page and the round page are checked at both widths. Run inside the `clusters.batch` lock, with
 * `committee.flow` and `clusters.batch` on.
 */
export async function toRevealedRound(
  browser: Browser,
  contributors: [string, string],
  words: (where: string) => string,
  value: string,
  axe: boolean,
): Promise<{ cluster: string; roundHref: string; ideas: [string, string] }> {
  const a = await as(browser, contributors[0]);
  const first = await share(a.page, words("Pune"));
  await a.close();
  const b = await as(browser, contributors[1]);
  const second = await share(b.page, words("Kochi"));
  await b.close();
  const desk = await as(browser, PERSONAS.reviewer);
  const r = desk.page;
  for (const ideaId of [first, second]) {
    await r.goto("/review");
    await r.getByRole("link", { name: ideaId }).click();
    await r.waitForURL(/\/review\/\d+$/);
    await r.getByRole("button", { name: "Save decision" }).click();
    await expect(r.getByRole("status").filter({ hasText: "Decision saved" })).toBeVisible();
  }
  // A run only takes ideas already in the index: wait for both, or the run can start without them.
  for (const ideaId of [first, second]) await waitUntilIndexed(ideaId);
  await runGroupingNow(r);
  await openProposalHolding(r, [first, second]);
  await nameTheGroup(r, "Paper forms pile up at the counter");
  await r.getByRole("button", { name: "Approve this group" }).click();
  await expect(r.getByRole("status").filter({ hasText: /The group is (CL-\d{4})/ })).toBeVisible();
  const cluster = /CL-\d{4}/.exec(
    await r
      .getByRole("status")
      .filter({ hasText: /The group is (CL-\d{4})/ })
      .innerText(),
  )![0];

  // Qualify: four gates, the impact estimate, finish. The item comes from a job after the approval commits.
  const qualifyRow = r.getByRole("row").filter({ hasText: cluster });
  await expect(async () => {
    await r.goto("/review?type=qualify");
    await expect(qualifyRow).toHaveCount(1, { timeout: 1_000 });
  }).toPass({ timeout: 30_000, intervals: [1_000] });
  await qualifyRow.getByRole("link").click();
  await r.waitForURL(/\/review\/qualify\/\d+$/);
  if (axe) await axeBoth(r);
  for (const gate of [
    "Evidence exists",
    "Not already running somewhere",
    "Not already planned",
    "No regulatory or IP conflict",
  ]) {
    await r.getByLabel("Gate", { exact: true }).selectOption({ label: gate });
    if (gate.startsWith("No regulatory"))
      await r.getByLabel("What the compliance check found").selectOption("clear");
    await r.getByRole("button", { name: "Confirm this gate" }).click();
    await expect(r.getByRole("status").filter({ hasText: "Gate confirmed." })).toBeVisible();
  }
  await r.getByLabel("Recurring cost saving (₹ a year)").fill("1800000");
  await r.getByRole("button", { name: "Save the estimate" }).click();
  await expect(r.getByRole("status").filter({ hasText: "Impact estimate saved." })).toBeVisible();
  await r.getByRole("button", { name: "Finish qualifying" }).click();
  await expect(r.getByRole("status").filter({ hasText: "Done." })).toBeVisible();
  await desk.close();

  // The chair opens a cycle; the committee scores blind.
  const chair = await as(browser, CHAIR);
  await chair.page.goto("/committee");
  if (axe) await axeBoth(chair.page);
  await chair.page.getByRole("button", { name: "Open the cycle" }).click();
  await expect(chair.page.getByRole("status").filter({ hasText: /Cycle CYC-/ })).toBeVisible();
  await chair.page.goto("/committee");
  const roundHref = (await chair.page
    .getByRole("link", { name: new RegExp(`\\(${cluster}\\)`) })
    .first()
    .getAttribute("href"))!;
  for (const who of [CHAIR, ...MEMBERS]) {
    const m = await as(browser, who);
    await m.page.goto(roundHref);
    if (axe && who === MEMBERS[0]) await axeBoth(m.page);
    await chooseScores(m.page, "Seal my scores", value);
    await m.page.getByRole("button", { name: "Seal my scores" }).click();
    await expect(m.page.getByRole("status").filter({ hasText: "Your scores are sealed." })).toBeVisible();
    await m.close();
  }
  await chair.page.goto(roundHref);
  await expect(chair.page.getByRole("heading", { level: 2, name: "Revealed" })).toBeVisible();
  await chair.close();
  return { cluster, roundHref, ideas: [first, second] };
}
