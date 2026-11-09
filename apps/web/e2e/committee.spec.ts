/**
 * The committee flow in the browser (§4.5–§4.7): with `committee.flow` and `clusters.batch` on, two colleagues'
 * ideas are reviewed and grouped; the desk qualifies the group; the chair opens a cycle; the committee scores it
 * blind; the chair shortlists; a contributor accepts the invitation; the chair records the session; members seal
 * their assessments; the chair collates and decides. axe clean on every new screen, at desktop width and at 360 px.
 * Desktop project only: the switches and the cycle are shared, so two projects at once would race.
 */
import { expect, test, type Browser, type Page } from "@playwright/test";

import { QUESTIONS } from "../src/lib/canvas/model";
import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";
import { openProposalHolding } from "./proposals";
import { withSwitchLock } from "./switch-lock";

const CHAIR = "SYN-00006";
const MEMBERS = ["SYN-00007", "SYN-00008", "SYN-00009", "SYN-00010"];

async function as(browser: Browser, who: string): Promise<{ page: Page; close: () => Promise<void> }> {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await signIn(page, who);
  return { page, close: () => ctx.close() };
}

async function setSwitch(browser: Browser, name: string, state: "on" | "off") {
  const { page, close } = await as(browser, PERSONAS.admin);
  await page.goto("/admin");
  const row = page.getByRole("row", { name: new RegExp(name.replace(".", "\\.")) });
  const action = state === "on" ? "Switch on" : "Switch off";
  const toggle = row.getByRole("button", { name: `${action}: ${name}` });
  if (await toggle.isVisible()) {
    await toggle.click();
    await row.getByLabel("Reason for this change").fill(`e2e test: committee flow ${state}`);
    await row.getByRole("button", { name: action, exact: true }).click();
    await expect(row.getByText(state === "on" ? "On" : "Off", { exact: true })).toBeVisible();
  }
  await close();
}

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

/** Every score is a choice (nothing is pre-selected): the suggested financial level where there is one. */
async function chooseScores(page: Page, submit: string, value: string) {
  const form = page.locator("form").filter({ has: page.getByRole("button", { name: submit }) });
  for (const group of await form.getByRole("group").all()) {
    const hint = /suggested: (\d)/.exec(await group.innerText());
    await group.getByRole("radio", { name: hint ? hint[1] : value, exact: true }).check();
  }
}

async function axeBoth(page: Page) {
  await expectNoSeriousAxeIssues(page);
  const size = page.viewportSize();
  await page.setViewportSize({ width: 360, height: 740 });
  await expectNoSeriousAxeIssues(page);
  if (size) await page.setViewportSize(size);
}

test("from a group of ideas to a committee decision", async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "shared switches and cycle; the 360 px check is inside");
  test.setTimeout(900_000); // includes waiting for clusters.spec, which flips the same switch
  await withSwitchLock("clusters.batch", () => committeeFlow(browser));
});

async function committeeFlow(browser: Browser) {
  const vocab = ["ledger", "voucher", "mandate", "payout", "register", "cheque", "courier", "stamp", "receipt", "batch",
    "slip", "tray", "binder", "scanner", "printer", "envelope", "token", "queue", "drawer", "stapler", "folder", "ribbon",
    "barcode", "label", "tally", "roster", "docket", "challan", "manifest", "bundle", "carton", "seal"]; // prettier-ignore
  let seed = Date.now() + 17;
  const pick = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return vocab.splice(seed % vocab.length, 1)[0];
  };
  const made = Array.from({ length: 7 }, pick);
  const words = (where: string) =>
    `${made.join(" ")} pile up at the ${where} counter; ${made.slice(0, 4).join(" ")} again tomorrow.`;

  for (const s of ["committee.flow", "clusters.batch"]) await setSwitch(browser, s, "on");
  try {
    // Two colleagues' ideas, reviewed and grouped.
    const a = await as(browser, PERSONAS.contributor);
    const first = await share(a.page, words("Pune"));
    await a.close();
    const b = await as(browser, "SYN-00016");
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
    const runButton = r.getByRole("button", { name: "Run the grouping now" });
    await expect(async () => {
      await r.goto("/review");
      await expect(runButton).toBeVisible({ timeout: 1_000 });
    }).toPass({ timeout: 30_000, intervals: [2_000] });
    await runButton.click();
    await openProposalHolding(r, [first, second]);
    await r.getByRole("button", { name: "Approve this group" }).click();
    await expect(r.getByRole("status").filter({ hasText: /The group is (CL-\d{4})/ })).toBeVisible();
    const cluster = /CL-\d{4}/.exec(await r.getByRole("status").innerText())![0];

    // Qualify: four gates, the impact estimate, finish. The item comes from a job after the approval commits.
    const qualifyRow = r.getByRole("row").filter({ hasText: cluster });
    await expect(async () => {
      await r.goto("/review?type=qualify");
      await expect(qualifyRow).toHaveCount(1, { timeout: 1_000 });
    }).toPass({ timeout: 30_000, intervals: [1_000] });
    await qualifyRow.getByRole("link").click();
    await r.waitForURL(/\/review\/qualify\/\d+$/);
    await axeBoth(r);
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
    await axeBoth(chair.page);
    await chair.page.getByRole("button", { name: "Open the cycle" }).click();
    await expect(chair.page.getByRole("status").filter({ hasText: /Cycle CYC-/ })).toBeVisible();
    await chair.page.goto("/committee");
    const roundLink = chair.page.getByRole("link", { name: new RegExp(`\\(${cluster}\\)`) });
    const roundHref = await roundLink.getAttribute("href");
    for (const who of [CHAIR, ...MEMBERS]) {
      const m = await as(browser, who);
      await m.page.goto(roundHref!);
      if (who === MEMBERS[0]) await axeBoth(m.page);
      await chooseScores(m.page, "Seal my scores", "4");
      await m.page.getByRole("button", { name: "Seal my scores" }).click();
      await expect(m.page.getByRole("status").filter({ hasText: "Your scores are sealed." })).toBeVisible();
      await m.close();
    }
    await chair.page.goto(roundHref!);
    await expect(chair.page.getByRole("heading", { level: 2, name: "Revealed" })).toBeVisible();
    await chair.page
      .getByLabel(/Why shortlist below the threshold/)
      .fill("Strong pain at every branch; worth hearing in person.")
      .catch(() => undefined);
    await chair.page.getByRole("button", { name: "Record the decision" }).click();
    await expect(chair.page.getByRole("status").filter({ hasText: "Decided." })).toBeVisible();

    // A contributor accepts the invitation (the message links straight to it).
    await chair.page.goto("/committee");
    const presLink = chair.page.getByRole("link", { name: new RegExp(`PRS-\\d{4}-\\d{4} \\(${cluster}\\)`) });
    const presentation = /PRS-\d{4}-\d{4}/.exec(await presLink.innerText())![0];
    const c = await as(browser, PERSONAS.contributor);
    await c.page.goto(`/presentations/${presentation}`);
    await axeBoth(c.page);
    await c.page.getByRole("button", { name: "Accept the invitation" }).click();
    await expect(c.page.getByRole("status").filter({ hasText: "Accepted." })).toBeVisible();
    await c.close();

    // The session, sealed assessments, collation and the decision.
    await chair.page.goto(`/committee/presentations/${presentation}`);
    await axeBoth(chair.page);
    await chair.page
      .getByLabel("Questions and answers")
      .fill("Asked about AMC form differences; a pilot is proposed.");
    await chair.page.getByRole("button", { name: "They presented" }).click();
    await expect(chair.page.getByRole("status").filter({ hasText: "Marked as presented." })).toBeVisible();
    for (const who of [CHAIR, ...MEMBERS]) {
      const m = await as(browser, who);
      await m.page.goto(`/committee/presentations/${presentation}`);
      await chooseScores(m.page, "Seal my assessment", "4");
      await m.page.getByLabel("Your vote").selectOption("accept");
      await m.page.getByLabel("Strengths (up to 3, one per line)").fill("The pain is felt at every branch");
      await m.page.getByLabel(/willing to sponsor/).check();
      await m.page.getByRole("button", { name: "Seal my assessment" }).click();
      await expect(
        m.page.getByRole("status").filter({ hasText: "Your assessment is sealed." }),
      ).toBeVisible();
      await m.close();
    }
    await chair.page.goto(`/committee/presentations/${presentation}`);
    await chair.page.getByRole("button", { name: "Collate the assessments" }).click();
    await expect(chair.page.getByRole("heading", { level: 2, name: "Decision sheet" })).toBeVisible();
    await chair.page.getByLabel("Sponsor").selectOption({ index: 1 });
    await chair.page.getByRole("button", { name: "Ask the assistant to draft the reasons" }).click();
    await expect(chair.page.getByLabel("Reason, in plain words")).not.toHaveValue("");
    await chair.page.getByRole("button", { name: "Record the decision" }).click();
    await expect(chair.page.getByRole("status").filter({ hasText: "Decided." })).toBeVisible();
    await expect(chair.page.getByText(/Decision DEC-\d{4}-\d{4}: picked/)).toBeVisible();
    await axeBoth(chair.page);
    await chair.close();
  } finally {
    for (const s of ["committee.flow", "clusters.batch"]) await setSwitch(browser, s, "off");
  }
}
