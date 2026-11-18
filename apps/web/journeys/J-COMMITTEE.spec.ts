/**
 * J-COMMITTEE: the Ones Committee reviews a decision (1pc-handoff/03-journeys/J-COMMITTEE.md).
 * Copy: reference/copy/Committee.md (S-R4), reference/copy/Status.md (S-06 committee line, "Reversed" state).
 * Seed: Manoj is on the committee. C1 (picked 10 days ago) is extended, F1 (not picked 3 days ago) is reversed,
 * J1 (picked 38 days ago) has expired, T7 (picked 5 days ago) is read.
 */
import { expect, type Page } from "@playwright/test";

import { addMonthsIST, dayIST, decisionWindow, ideaUrl, nextCloseIST, seeded, signInAs, step } from "./lib";

const EXPLANATION =
  "The review desk decides on the committee’s behalf, and the sharer hears at once. For 30 days after, you can " +
  "reverse a decision, with a note the sharer reads. Extend a window 30 days at a time, up to 3 months. Then it " +
  "expires and the decision stands.";

async function openCommittee(page: Page) {
  await signInAs(page, "manoj");
  await page.goto("/committee");
  await expect(page.getByRole("heading", { level: 1, name: "Ones Committee" })).toBeVisible();
}

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function rowFor(page: Page, title: string) {
  return page.getByRole("row", { name: new RegExp(esc(title)) });
}

step(
  "J-COMMITTEE/1",
  "S-R4",
  "In the window lists each decision with the reason as the sharer read it",
  { needs: ["S-R4", "L-COMMITTEE", "C-TABS", "C-SORTS"] },
  async ({ page }) => {
    const t7 = await seeded("T7");
    await openCommittee(page);
    await expect(page.getByText(EXPLANATION)).toBeVisible();
    await expect(page.getByRole("tab", { name: /In the window/, selected: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Closing soonest" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    // Carried from J-REVIEW/6: the reviewer's decision, its reason word for word, and the window it opened.
    const row = rowFor(page, t7.title);
    await expect(row).toContainText(`${t7.ref}, Tanvi Deshmukh, Investor service, Hyderabad`);
    await expect(row).toContainText("Picked");
    await expect(row).toContainText(/by Harish from the review desk, \w+day \d{1,2} \w+/);
    await expect(row).toContainText("25 days left");
    await expect(row.getByRole("button", { name: "Review" })).toBeVisible();
  },
);

step(
  "J-COMMITTEE/2",
  "S-R4",
  "Review opens the row: the reason, the window, Extend and Reverse",
  { needs: ["S-R4", "L-COMMITTEE"] },
  async ({ page }) => {
    const c1 = await seeded("C1");
    // The window's end as stored, and its limit worked out from the decision: 3 months on India's calendar
    // (L-COMMITTEE.rules/2, BLD-B258). A date outside this year carries its year (Committee.md: "up to Tuesday 16
    // February 2027"); dayIST() decides that from today in India, as desk/when.py day() does.
    const { opensAt, closesAt } = await decisionWindow(c1);
    const until = dayIST(closesAt);
    const cap = dayIST(addMonthsIST(opensAt, 3));
    await openCommittee(page);
    await rowFor(page, c1.title).getByRole("button", { name: "Review" }).click();
    await expect(page.getByText("The review desk’s reason, as Charulata read it")).toBeVisible();
    await expect(
      page.getByText(
        `Open until ${until}. You can extend it 30 days at a time, up to ${cap}. When it closes, the decision stands.`,
        { exact: true },
      ),
    ).toBeVisible();
    // Extend's target by the rule (BLD-B263): C1 was extended once, so this one reaches the 3-month date itself.
    const next = nextCloseIST(opensAt, closesAt);
    expect(next, "C1 starts extended once, below its limit").not.toBeNull();
    await expect(
      page.getByRole("button", { name: `Extend to ${dayIST(next as Date)}`, exact: true }),
    ).toBeEnabled();
    await expect(page.getByRole("button", { name: "Reverse the decision" })).toBeEnabled();
  },
);

step(
  "J-COMMITTEE/3a",
  "S-R4",
  "Extend moves the window 30 days and the sharer sees the new date",
  { needs: ["S-R4", "L-COMMITTEE", "S-06"], changes: ["C1"] },
  async ({ page, browser }) => {
    const c1 = await seeded("C1");
    const { opensAt, closesAt } = await decisionWindow(c1);
    const next = nextCloseIST(opensAt, closesAt);
    expect(next, "C1 starts extended once, below its limit").not.toBeNull();
    const newDate = dayIST(next as Date);
    // Closing 60 days in, the next 30 would stop 0 to 2 days short of the 3-month date, so it goes to that date.
    expect((next as Date).getTime()).toBe(addMonthsIST(opensAt, 3).getTime());
    await openCommittee(page);
    const row = rowFor(page, c1.title);
    await row.getByRole("button", { name: "Review" }).click();
    // The seed extended C1 once, so this is its second extension.
    await expect(row).toContainText("Extended once");
    const extend = page.getByRole("button", { name: `Extend to ${newDate}`, exact: true });
    const until = esc(newDate);
    await extend.click();
    await expect(row).toContainText("Extended twice"); // when.times: "once", "twice", then "N times"
    await expect(row).toContainText(new RegExp(`Until ${until}`));
    // At the 3-month date nothing more can be added: the limit line stands where Extend was (S-R4.rules/2).
    await expect(page.getByRole("button", { name: /^Extend to / })).toHaveCount(0);
    await expect(page.getByText("At the 3-month limit", { exact: true }).first()).toBeVisible();

    // Hand-off: the sharer's page shows the same new date in the committee line (S-06.states, Status.md).
    const sharer = await (await browser.newContext()).newPage();
    await signInAs(sharer, "charulata");
    await sharer.goto(ideaUrl(c1));
    await expect(
      sharer.getByText(
        new RegExp(
          `^The Ones Committee can review this decision until ${until}\\. If they change it, their note comes to your Inbox\\. After that, it stands\\.$`,
        ),
      ),
    ).toBeVisible();
    await sharer.context().close();
  },
);

step(
  "J-COMMITTEE/3b",
  "S-R4",
  "Reverse with a note: final, the row moves to Reversed and the sharer reads the note",
  { needs: ["S-R4", "L-COMMITTEE", "S-06", "L-NOTIFY"], changes: ["F1"] },
  async ({ page, browser }) => {
    const f1 = await seeded("F1");
    const note = "We want to try this at two branches on pension days before deciding for every branch.";
    await openCommittee(page);
    await rowFor(page, f1.title).getByRole("button", { name: "Review" }).click();
    await page.getByRole("button", { name: "Reverse the decision" }).click();
    const form = page.getByRole("dialog", { name: "Reverse the decision" });
    await expect(form).toContainText(`On “${f1.title}”.`);
    await expect(form).toContainText(
      "Faisal reads your note at once, and Harish from the review desk sees it too.",
    );
    await expect(form).toContainText(
      "This is final. The review desk’s decision stays on record, next to yours.",
    );
    await form.getByRole("radio", { name: /^Picked/ }).click();
    await form
      .getByRole("textbox", { name: "Why the committee is changing it, in words Faisal will understand" })
      .fill(note);
    await form.getByRole("button", { name: "Reverse and tell Faisal" }).click();

    await page.getByRole("tab", { name: /Reversed/ }).click();
    const row = rowFor(page, f1.title);
    await expect(row).toContainText(/Now: Picked by Manoj Agarwal, \w+day \d{1,2} \w+/);
    await expect(row).toContainText(/Reversed \w+day \d{1,2} \w+\. Final\. Faisal has the note\./);
    await expect(row.getByRole("button", { name: "See it" })).toBeVisible();

    // Hand-off: the sharer's page takes the new decision, with the note word for word and "This is final."
    const sharer = await (await browser.newContext()).newPage();
    await signInAs(sharer, "faisal");
    await sharer.goto(ideaUrl(f1));
    await expect(sharer.getByText("The Ones Committee changed the decision to picked")).toBeVisible();
    await expect(sharer.getByText("The committee’s note to you")).toBeVisible();
    await expect(sharer.locator("blockquote").filter({ hasText: note })).toBeVisible();
    // And the conversation card carries it as the Ones Committee's message (S-06.layout/8, BLD-E058).
    await expect(
      sharer.getByRole("complementary", { name: "The conversation and similar ideas" }).getByText(note),
    ).toBeVisible();
    await expect(sharer.getByText(/^This is final\./)).toBeVisible();
    await sharer.context().close();
  },
);

step(
  "J-COMMITTEE/3c",
  "S-R4",
  "A window that closed with nothing done is under Expired and the decision stands",
  { needs: ["S-R4", "L-COMMITTEE"] },
  async ({ page }) => {
    const j1 = await seeded("J1");
    await openCommittee(page);
    await page.getByRole("tab", { name: /Expired/ }).click();
    const row = rowFor(page, j1.title);
    await expect(row).toContainText(/Expired \w+day \d{1,2} \w+\. After 30 days\. The decision stands\./);
    await expect(row.getByRole("button", { name: "See it" })).toBeVisible();
    await expect(row.getByRole("button", { name: /^Extend to / })).toHaveCount(0);
  },
);
