/**
 * J-SIMILAR: someone raised it already; a merge request, or go it alone (1pc-handoff/03-journeys/J-SIMILAR.md).
 * Hand-offs only; the detail of each screen is in V-ACC.similar.
 * Copy: reference/copy/ComposeResume.md (S-04B), Review.md (S-05 "Similar ideas" and the merge states), Crew.md and
 * C-SHEET-TEAMUP (the sheet), CrewRequest.md (S-H2B), DeskIdea.md and Status.md (the desk merge). BLD-E008: a board's
 * she/her for a run-time person reads as their first name, or they/their where the name would repeat; those lines
 * accept either.
 * Cast: Kavya (sharer) is Tanvi, Ravi (lead) Rekha, Meera (reviewer) Lavanya.
 * Seed: T2 (Tanvi's draft at Check it, close to Rekha's R1, a merge request waiting on Rekha) is J-SIMILAR's with that
 * request. Row 3 withdraws the seeded request and sends a "Keep mine separate" team-up; row 4b swaps it for a merge
 * request; Rekha merges it (6a), so Tanvi joins R1's crew. R1 is shared with J-TEAMUP: both only add requests and
 * crew to it, and nobody decides it, so no row here depends on whether R1 is picked. Team up only (6b) and Decline
 * (6c) need requests of their own: GAP-SEED. Row 7 reads the desk merge of T11 into R2 (read only).
 * Rekha's Inbox keeps the requests Tanvi withdrew, newest first (L-INBOX.rules/4): rows 5 and 6a open the newest.
 */
import { expect, type Locator, type Page } from "@playwright/test";

import { draftUrl, ideaUrl, seeded, signInAs, snap, step } from "./lib";

const REF = String.raw`IDEA-\d{4}-\d{6}`;

/** What Tanvi writes to Rekha: kept separate (row 3), then asking to merge (row 4b, read by Rekha in row 5). */
const NOTE_KEEP =
  "I see the failed SIP SMS calls at the Hyderabad branch too and can share how many we take each day.";
const NOTE_MERGE =
  "Mine is the same failed SIP debit with no reason. Please take my words and the twenty calls a day into yours.";

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Check it, part 3 for T2 (S-05), opened by its step button. */
async function similarPart(page: Page): Promise<{ t2: string; r1Title: string; r1Ref: string }> {
  const t2 = await seeded("T2");
  const r1 = await seeded("R1");
  await signInAs(page, "tanvi");
  await page.goto(draftUrl(t2, "/check"));
  await page.getByRole("button", { name: /^(?:\d )?Similar ideas\b/ }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Has someone raised this already?" }),
  ).toBeVisible();
  return { t2: t2.title, r1Title: r1.title, r1Ref: r1.ref ?? "" };
}

/** The team-up sheet (C-SHEET-TEAMUP) from R1's tile, with the Check it choice. */
async function openSheet(page: Page, r1Title: string): Promise<Locator> {
  await page.getByRole("button", { name: `Team up on ${r1Title}` }).click();
  const sheet = page.getByRole("dialog", { name: "Team up with Rekha" });
  await expect(sheet).toBeVisible();
  return sheet;
}

/** Withdraws whatever request T2 has waiting on Rekha, so the draft is back to normal (L-MERGE.request/8). */
async function withdrawWaiting(page: Page): Promise<void> {
  const withdraw = page.getByRole("button", { name: /^Withdraw( the request)?$/ }).first();
  await withdraw.click();
  await expect(page.getByRole("button", { name: /^Withdraw( the request)?$/ })).toHaveCount(0);
}

// --- J-SIMILAR.steps ---------------------------------------------------------------------------------------------

step(
  "J-SIMILAR/1",
  "S-04B",
  "A quiet line in the draft says similar ideas were found",
  { needs: ["S-04B", "C-DRAFT-PANEL", "L-SIMILAR"] },
  async ({ page }) => {
    const t2 = await seeded("T2");
    await signInAs(page, "tanvi");
    await page.goto(draftUrl(t2));
    await expect(page.getByRole("heading", { level: 2, name: "Your draft" })).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^\d+ similar ideas? Colleagues raised something close$/ }),
    ).toBeVisible();
    await expect(page.getByText(/^\d+ similar ideas?$/).first()).toBeVisible();
  },
);

step(
  "J-SIMILAR/2",
  "S-05",
  "Check it, part 3: hers first, then the matches; Preview opens the closest, with Rekha's crew",
  { needs: ["S-05", "C-SIMGRID", "C-PREVIEW", "L-SIMILAR"] },
  async ({ page }) => {
    const { t2, r1Title, r1Ref } = await similarPart(page);
    await expect(page.getByText("Yours, not sent yet").first()).toBeVisible();
    await expect(page.getByText(t2, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(`${r1Ref}, Investor service, Hyderabad`).first()).toBeVisible();
    await expect(page.getByText("Close match: the same failed SIP debit").first()).toBeVisible();

    await page.getByRole("button", { name: `Preview ${r1Title}` }).click();
    const preview = page.getByRole("dialog");
    await expect(preview).toContainText(r1Title);
    await expect(preview).toContainText("The problem, in their words");
    await expect(preview).toContainText(/Rekha Saxena leads it, \d+ on its crew/);
    await expect(preview).toContainText("Teaming up adds you to their crew. Your draft stays yours.");
    // The seeded request is still waiting, so the footer's one button is replaced by its status (C-PREVIEW/7).
    await expect(preview).toContainText("Waiting for Rekha");
    await preview.getByRole("button", { name: "Close the preview" }).click();
  },
);

step(
  "J-SIMILAR/3",
  "S-05",
  "The sheet from the tile: a note of 30+ characters, Ask Rekha to merge mine in or Keep mine separate, Send",
  {
    needs: ["S-05", "C-SIMGRID", "C-SHEET-TEAMUP", "L-MERGE", "L-TEAMUP"],
    changes: ["T2", "R1"], // the team-up request goes to R1
  },
  async ({ page }) => {
    const { r1Title } = await similarPart(page);
    await withdrawWaiting(page);
    const sheet = await openSheet(page, r1Title);
    await expect(sheet).toContainText(
      `Rekha leads “${r1Title}” and decides who joins. Tell Rekha what you bring.`,
    );
    await expect(sheet).toContainText("We drafted this from your idea. Change anything you like.");
    await expect(sheet.getByRole("radio", { name: /^Ask Rekha to merge mine in/ })).toBeVisible();
    await sheet.getByRole("radio", { name: /^Keep mine separate/ }).click();
    await sheet.getByRole("textbox").fill(NOTE_KEEP);
    await expect(sheet).toContainText("Looks good.");
    await sheet.getByRole("button", { name: "Send to Rekha" }).click();

    // C-SHEET-TEAMUP.sent: the sheet changes in place and shows the note back.
    await expect(sheet).toContainText("Sent to Rekha");
    await expect(sheet).toContainText(
      "Rekha reads your note, then approves or declines. You’ll hear in your Inbox.",
    );
    await expect(sheet).toContainText(NOTE_KEEP);
  },
);

step(
  "J-SIMILAR/4a",
  "S-05",
  "Kept separate: the tile waits for Rekha, nothing is held, and Submit stays available",
  { needs: ["S-05", "C-SIMGRID", "L-SIMILAR", "L-TEAMUP", "L-SUBMIT"], changes: ["T2"] },
  async ({ page }) => {
    await similarPart(page);
    await expect(page.getByText("Waiting for Rekha", { exact: true }).first()).toBeVisible();
    await expect(page.getByText(/^Waiting for Rekha to accept the merge\./)).toHaveCount(0);
    await page.getByRole("button", { name: /^(?:\d )?Send it\b/ }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Ready to send?" })).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Submit" }).or(page.getByRole("link", { name: "Submit" })),
    ).toBeEnabled();
  },
);

step(
  "J-SIMILAR/4b",
  "S-05",
  "Asks Rekha to merge: Sent to Rekha, the draft is held, Submit is unavailable, the request can be withdrawn",
  { needs: ["S-05", "C-SIMGRID", "C-SHEET-TEAMUP", "L-MERGE"], changes: ["T2", "R1"] },
  async ({ page }) => {
    const { r1Title } = await similarPart(page);
    await withdrawWaiting(page);
    const sheet = await openSheet(page, r1Title);
    await sheet.getByRole("radio", { name: /^Ask Rekha to merge mine in/ }).click();
    await expect(sheet).toContainText(
      "Rekha decides. If Rekha accepts, yours joins that idea with credit to you. If not, you send yours on its own.",
    );
    await sheet.getByRole("textbox").fill(NOTE_MERGE);
    await sheet.getByRole("button", { name: "Send to Rekha" }).click();
    await expect(sheet).toContainText("Sent to Rekha");
    await sheet.getByRole("button", { name: "Done" }).click();

    // L-MERGE.request/4: held.
    await expect(
      page.getByRole("button", { name: /Similar ideas Waiting on Rekha to merge$/ }),
    ).toBeVisible();
    await expect(
      page.getByText(
        "Waiting for Rekha to accept the merge. If Rekha declines, you can send yours on its own.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Withdraw the request" })).toBeVisible();
    await page.getByRole("button", { name: /^(?:\d )?Send it\b/ }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Ready to send?" })).toBeVisible();
    // Unavailable: Submit is left out, or drawn disabled. Either way nothing here sends it.
    await expect(
      page
        .getByRole("button", { name: "Submit", disabled: false })
        .or(page.getByRole("link", { name: "Submit", disabled: false })),
    ).toHaveCount(0);
  },
);

step(
  "J-SIMILAR/5",
  "S-H2B",
  "Rekha's Inbox: Tanvi's note word for word, a summary of her draft, and Decline, Team up only, Merge it",
  { needs: ["S-H2B", "S-H5", "L-INBOX", "L-TEAMUP", "L-MERGE"] },
  async ({ page }) => {
    const t2 = await seeded("T2");
    const r1 = await seeded("R1");
    await signInAs(page, "rekha");
    await page.goto("/inbox");
    // BLD-E008, BLD-E010: no seeded person chose how to be referred to, so "their" or Tanvi's name.
    await page
      .getByRole("button", {
        name: new RegExp(
          `^Tanvi Deshmukh asks to team up and merge (?:their|Tanvi’s) idea into yours, ${esc(r1.title)}, `,
        ),
      })
      .first()
      .click();
    await expect(page.getByText("Merge request", { exact: true }).first()).toBeVisible();
    await expect(page.getByText(NOTE_MERGE, { exact: true })).toBeVisible();
    await expect(page.getByText(t2.title, { exact: true }).first()).toBeVisible();
    await expect(
      page.getByText(/^Merge it, and (?:their|Tanvi’s) idea joins yours: /).first(),
    ).toBeVisible();
    for (const answer of ["Decline", "Team up only", "Merge it"]) {
      await expect(page.getByRole("button", { name: answer, exact: true })).toBeEnabled();
    }
  },
);

step(
  "J-SIMILAR/6a",
  "S-H2B",
  "Rekha merges it: Tanvi is on Rekha's crew, and her draft reads Merged into R1, with credit to her",
  { needs: ["S-H2B", "L-TEAMUP", "L-MERGE", "S-05"], changes: ["T2", "R1"] }, // Tanvi joins R1's crew
  async ({ page, browser }, info) => {
    const t2 = await seeded("T2");
    const r1 = await seeded("R1");
    await signInAs(page, "rekha");
    await page.goto("/inbox");
    await page
      .getByRole("button", {
        name: new RegExp(`^Tanvi Deshmukh asks to team up and merge .*, ${esc(r1.title)}, `),
      })
      .first()
      .click();
    await page.getByRole("button", { name: "Merge it", exact: true }).click();
    await expect(
      page
        .getByText(
          /^Merged\. Tanvi’s idea is now part of yours, and (?:Tanvi is|they are) on your crew, credited\. We’ve told (?:Tanvi|them)\.$/,
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Say hello to Tanvi" })).toBeVisible();

    // L-MERGE.request/5: what Tanvi reads on her draft.
    const context = await browser.newContext();
    const sharer = await context.newPage();
    try {
      await signInAs(sharer, "tanvi");
      await sharer.goto(draftUrl(t2, "/check"));
      await expect(sharer.getByText(`Merged into ${r1.ref}`, { exact: true }).first()).toBeVisible();
      await expect(
        sharer.getByText(
          `Rekha accepted. Yours is now part of ${r1.ref}, with credit to you. Nothing else to send.`,
        ),
      ).toBeVisible();
    } finally {
      await snap(sharer, info, "J-SIMILAR/6a", "S-05", "tanvi");
      await context.close();
    }
  },
);

step(
  "J-SIMILAR/6b",
  "S-H2B",
  "Rekha teams up only: Tanvi is on the crew, and her draft stays hers to send on its own",
  {
    needs: ["S-H2B", "L-TEAMUP", "L-MERGE", "S-05"],
    gapSeed:
      "a second draft with a merge request waiting on a lead, for Team up only (J-SIMILAR owns only T2's)",
  },
  async () => {},
);

step(
  "J-SIMILAR/6c",
  "S-H2B",
  "Rekha declines with a reason: Tanvi reads it, and the button becomes Send mine on its own",
  {
    needs: ["S-H2B", "L-TEAMUP", "L-MERGE", "S-05"],
    gapSeed: "a third draft with a merge request waiting on a lead, for Decline (J-SIMILAR owns only T2's)",
  },
  async () => {},
);

step(
  "J-SIMILAR/7",
  "S-R2",
  "Later, the review desk merged two separate ideas: the lead idea lists it as Merged, and its sharer's page says where it went",
  { needs: ["S-R2", "C-SHEET-MERGE", "L-MERGE", "S-06"] },
  async ({ page, browser }, info) => {
    const r2 = await seeded("R2");
    const t11 = await seeded("T11");
    await signInAs(page, "lavanya");
    await page.goto(`/desk/ideas/${r2.ref ?? r2.uuid}`);
    await expect(page.getByRole("heading", { level: 1, name: r2.title })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "Similar ideas" })).toBeVisible();
    await expect(page.getByText("Merged", { exact: true }).first()).toBeVisible();

    // L-MERGE.effects/1: the merged idea's page shows where it went, with the note, for its sharer.
    const context = await browser.newContext();
    const sharer = await context.newPage();
    try {
      await signInAs(sharer, "tanvi");
      await sharer.goto(ideaUrl(t11));
      await expect(
        sharer.getByText(new RegExp(`^Merged into ${esc(r2.ref ?? "")} by the review desk`)).first(),
      ).toBeVisible();
      await expect(
        sharer.getByText("Both ideas ask for one clear message after a failed debit.").first(),
      ).toBeVisible();
      await expect(sharer.getByRole("link", { name: new RegExp(REF) }).first()).toBeVisible();
    } finally {
      await snap(sharer, info, "J-SIMILAR/7", "S-06", "tanvi");
      await context.close();
    }
  },
);
