/**
 * J-COMMITTEE: the Ones Committee reviews a decision (1pc-handoff/03-journeys/J-COMMITTEE.md).
 * Copy: reference/copy/Committee.md (S-R4), reference/copy/Status.md (S-06 committee line, "Reversed" state).
 * Seed: Manoj is on the committee. C1 (picked 10 days ago) is extended, F1 (not picked 3 days ago) is reversed,
 * J1 (picked 38 days ago) has expired, T7 (picked 5 days ago) is read.
 * Roles (/4, DEC-121, BLD-B270): Manoj holds `committee` and nothing else, Kunal `admin` and nothing else (club_seed
 * PEOPLE). F2 (J-REVIEW's, still with the desk when this file runs) is read only here.
 */
import { expect, type Locator, type Page } from "@playwright/test";

import {
  addMonthsIST,
  dayIST,
  decisionWindow,
  ideaUrl,
  nextCloseIST,
  seeded,
  signInAs,
  snap,
  step,
} from "./lib";

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

// Review (or See it) opens the decision in a second row below the summary row: the reason, the window, then Extend
// or the limit line, and Reverse (S-R4). The button names that panel in aria-controls, so what the panel holds is
// read there, never in the summary row, where a missing button would pass unseen.
async function openPanel(page: Page, title: string, action: "Review" | "See it"): Promise<Locator> {
  const button = rowFor(page, title).getByRole("button", { name: new RegExp(`^${action}`) });
  const id = await button.getAttribute("aria-controls");
  expect(id, `${action} names the panel it opens`).toBeTruthy();
  await button.click();
  const panel = page.locator(`[id="${id}"]`);
  await expect(panel).toBeVisible();
  return panel;
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
    const panel = await openPanel(page, c1.title, "Review");
    // The seed extended C1 once, so this is its second extension.
    await expect(row).toContainText("Extended once");
    const extend = panel.getByRole("button", { name: `Extend to ${newDate}`, exact: true });
    const until = esc(newDate);
    await extend.click();
    await expect(row).toContainText("Extended twice"); // when.times: "once", "twice", then "N times"
    await expect(row).toContainText(new RegExp(`Until ${until}`));
    // At the 3-month date nothing more can be added: in the open panel the limit line stands where Extend was
    // (S-R4.rules/2). The line is checked first, so the panel is known to be there when no Extend is found in it.
    await expect(panel.getByText("At the 3-month limit", { exact: true })).toBeVisible();
    await expect(panel.getByRole("button", { name: /^Extend to / })).toHaveCount(0);
    // With nothing left to add, the window line drops "You can extend it…" (BLD-B268); newDate is the 3-month date.
    await expect(
      panel.getByText(`Open until ${newDate}. When it closes, the decision stands.`, { exact: true }),
    ).toBeVisible();

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
    // See it opens the panel; a closed window offers neither Extend nor Reverse there.
    const panel = await openPanel(page, j1.title, "See it");
    await expect(panel.getByRole("button", { name: /^Extend to / })).toHaveCount(0);
    await expect(panel.getByRole("button", { name: "Reverse the decision" })).toHaveCount(0);
  },
);

step(
  "J-COMMITTEE/4",
  "S-R2",
  "A committee-only member reads an idea with the desk and its Listen, with no desk action; an admin-only user is refused",
  { needs: ["S-R2", "L-COMMITTEE", "C-LISTEN", "L-LISTEN", "P-PRODUCT.privacy"] },
  async ({ page, browser }, info) => {
    // F2 (Faisal's, with Lavanya, opened, not decided, J2 listed as similar): still with the desk here, as files run
    // alphabetically and J-REVIEW/M3 merges it later. Not Manoj's (L-COMMITTEE.rules/9), and only read: his S-R2
    // never opens an idea (the open needs work_review_queue), and the decision he tries below is empty.
    const f2 = await seeded("F2");
    const j2 = await seeded("J2");
    const ref = f2.ref ?? f2.uuid;
    const at = `/desk/ideas/${ref}`;
    await signInAs(page, "manoj");
    await page.goto(at);
    await expect(page).toHaveURL((url) => url.pathname === at);
    await expect(page.getByRole("heading", { level: 1, name: f2.title })).toBeVisible();
    // C-LISTEN: the strip, its heading and Play (ready or not: "Play the whole idea", then "…, {length}")
    const listen = page.getByRole("region", { name: "Listen to the whole idea", exact: true });
    await expect(
      listen.getByRole("heading", { name: "Listen to the whole idea", exact: true }),
    ).toBeVisible();
    await expect(listen.getByRole("button", { name: /^Play the whole idea/ })).toBeVisible();
    // The similar idea is there to read, so a missing Merge below is his role, not an empty list
    const j2Row = page
      .locator(".ri-sim-row")
      .filter({ has: page.getByRole("button", { name: j2.title, exact: true }) });
    await expect(j2Row.getByRole("button", { name: `Preview ${j2.title}`, exact: true })).toBeVisible();
    // Desk actions are the review desk's (can_act needs REVIEWERS): none of what Lavanya sees on this page
    // (reviewer-idea.tsx: the bar's Decide, Ask Faisal first, each part's Ask about this, the worth controls, Merge)
    await expect(page.getByRole("button", { name: "Decide on this idea", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^Ask \S+ first/ })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^(?:Ask about this|Asking), / })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^(?:Revise|Change) what it’s worth$/ })).toHaveCount(0);
    // The worth line tells its reader to decide or revise, so it is the review desk's alone (BLD-B270 follow-up)
    await expect(page.getByText(/sees your figures next to/)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Revise and recategorise", exact: true })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /^Merge with / })).toHaveCount(0);
    // C-SIDEBAR unchanged: the Ones Committee, and no Review desk
    const nav = page.getByRole("navigation", { name: "Main" }).filter({ visible: true });
    await expect(nav.getByRole("link", { name: /^Ones Committee/ })).toBeVisible();
    await expect(nav.getByRole("link", { name: /^Review desk/ })).toHaveCount(0);
    // L-LISTEN: the desk's script answers him; a write is refused at the proxy (an empty decision: nothing to decide)
    expect((await page.request.get(`/api/desk/ideas/${ref}/listen`)).status()).toBe(200);
    const write = await page.request.post(`/api/desk/ideas/${ref}/decision`, { data: {} });
    expect(write.status(), `decision: ${await write.text()}`).toBe(403);

    // P-PRODUCT.privacy: an admin on neither the desk nor the committee passes the web's gate and the worker refuses
    // him: S-R1 sends him to `/`, which is Home for anyone signed in (BLD-C143); S-R2 is not found; Listen is 403.
    const admin = await (await browser.newContext()).newPage();
    try {
      await signInAs(admin, "kunal");
      await admin.goto("/desk");
      await expect(admin).toHaveURL((url) => url.pathname === "/home");
      await expect(admin.getByRole("heading", { level: 1, name: "Review desk" })).toHaveCount(0);
      const notFound = await admin.goto(at);
      expect(notFound?.status()).toBe(404);
      await expect(admin.getByRole("heading", { name: "This page could not be found." })).toBeVisible();
      await expect(admin.getByRole("heading", { level: 1, name: f2.title })).toHaveCount(0);
      const refused = await admin.request.get(`/api/desk/ideas/${ref}/listen`);
      expect(refused.status(), `listen: ${await refused.text()}`).toBe(403);
    } finally {
      await snap(admin, info, "J-COMMITTEE/4", "S-R2", "kunal");
      await admin.context().close();
    }
  },
);
