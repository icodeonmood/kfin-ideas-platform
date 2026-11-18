/**
 * J-TEAMUP: find your crew and team up (1pc-handoff/03-journeys/J-TEAMUP.md). Hand-offs only; the detail of each screen
 * is in V-ACC.teamup.
 * Copy: reference/copy/Crew.md (S-H2, C-CREW-DECK and the sheet), Idea.md (S-09 "Team up on this idea"),
 * CrewRequest.md (S-H2B), Inbox.md (S-H5), MyIdeas.md (S-07 Teamed up), Messages.md (S-08 after teaming up).
 * BLD-E008: a board's she/her for a run-time person reads as their first name, or they/their where the name would
 * repeat; those lines accept either.
 * Cast: Kavya (the one who teams up) is Tanvi on the crew deck (row 1) and Bhavesh for the request (rows 2 to 6);
 * Ravi (lead) is Rekha.
 * Seed: J-TEAMUP may change Tanvi's crew-deck passes (row 1 passes one card) and answer the team-up request waiting on
 * Rekha: Bhavesh's on R1, sent with no idea brought. Row 2 withdraws it so the sheet can be written again, row 3 sends
 * the new note, Rekha approves it (row 4), and the two talk in R1's conversation (row 6). R1 is shared with
 * J-SIMILAR (lib SEED): both only add requests, crew and messages, and nobody decides it, so no row here depends on
 * whether R1 is picked. Row 1 ends with the sheet open from a card, which is where row 2 starts.
 */
import { expect, type Page } from "@playwright/test";

import { ideaUrl, seeded, signInAs, snap, step } from "./lib";

const DAY = String.raw`[A-Z][a-z]+day \d{1,2} [A-Z][a-z]+`;

/** Bhavesh's note to Rekha (row 3), which Rekha reads word for word (row 4). Synthetic. */
const NOTE =
  "I run the courier desk and see the returned SIP letters every week. I can bring the monthly count and examples.";
/** What Bhavesh says once he is on the crew (row 6). */
const HELLO =
  "Hello Rekha, thanks for having me. I will add last month's returned SIP letters here by Friday.";

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** R1's page for Bhavesh (S-09), at its "Team up on this idea" section. */
async function r1ForBhavesh(page: Page): Promise<{ title: string; ref: string; url: string }> {
  const r1 = await seeded("R1");
  await signInAs(page, "bhavesh");
  await page.goto(ideaUrl(r1));
  await expect(page.getByRole("heading", { level: 1, name: r1.title })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Team up on this idea" })).toBeVisible();
  return { title: r1.title, ref: r1.ref ?? "", url: ideaUrl(r1) };
}

step(
  "J-TEAMUP/1",
  "S-H2",
  "Find your crew: ideas close to hers, each with why it is shown; Next passes, Team up is the way on",
  { needs: ["S-H2", "C-CREW-DECK", "L-CREW"] },
  async ({ page }) => {
    await signInAs(page, "tanvi");
    await page.goto("/crew");
    await expect(page.getByRole("heading", { level: 1, name: "Find your crew" })).toBeVisible();
    await expect(page.getByText("Ideas close to yours. Team up, or pass.")).toBeVisible();
    await expect(page.getByText(/^\d+ ideas? close to yours$/)).toBeVisible();
    await expect(page.getByText("The problem, in their words").first()).toBeVisible();
    // No "They're looking for" check here: the line is the sharer's own "Who would help" answer, else their picks, and
    // it is hidden when neither was given (BLD-F031; AI drafting is off at launch, DEC-105). Lane F's tests own it.
    const total = (await page.getByText(/^Idea 1 of \d+$/).innerText()).replace(/^Idea 1 of /, "");
    await expect(
      page.getByRole("button", { name: /^Team up on .+: send [A-Z][a-z]+ a note$/ }).first(),
    ).toBeVisible();
    // L-CREW: Next on a card is a pass (C-CREW-DECK.behaviour/4).
    await page.getByRole("button", { name: "Next idea" }).click();
    await expect(page.getByText(`Idea 2 of ${total}`)).toBeVisible();
    await expect(page.getByText(/^\d+ passed$/).first()).toBeVisible();

    // The hand-off to row 2: Team up on the card in front opens the sheet (Crew.md "view=Request"). Nothing is sent.
    await page
      .getByRole("button", { name: /^Team up on .+: send [A-Z][a-z]+ a note$/ })
      .first()
      .click();
    const sheet = page.getByRole("dialog", { name: /^Team up with [A-Z][a-z]+$/ });
    await expect(sheet).toBeVisible();
    await expect(sheet).toContainText(/[A-Z][a-z]+ leads “.+” and decides who joins\./);
    await expect(sheet.getByRole("button", { name: /^Send to [A-Z][a-z]+$/ })).toBeVisible();
  },
);

step(
  "J-TEAMUP/2",
  "S-09",
  "The sheet: Team up with Rekha, the drafted note, Bring your ideas along with none picked, Send to Rekha",
  { needs: ["S-09", "C-SHEET-TEAMUP", "L-TEAMUP"], changes: ["R1"] }, // withdraws the seeded request on R1
  async ({ page }) => {
    const r1 = await r1ForBhavesh(page);
    // The seeded request waits on Rekha; withdrawn, the card is back to Team up (C-SHEET-TEAMUP.after).
    await expect(page.getByText("Waiting for Rekha", { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Withdraw", exact: true }).click();
    await page.getByRole("button", { name: "Team up", exact: true }).click();

    const sheet = page.getByRole("dialog", { name: "Team up with Rekha" });
    await expect(sheet).toContainText(
      `Rekha leads “${r1.title}” and decides who joins. Tell Rekha what you bring.`,
    );
    await expect(sheet).toContainText("Your note to Rekha");
    await expect(sheet).toContainText("We drafted this from your idea. Change anything you like.");
    await expect(sheet.getByRole("textbox")).not.toHaveValue("");
    await expect(sheet.getByRole("button", { name: "Bring your ideas along: None picked" })).toBeVisible();
    await expect(sheet).toContainText("Rekha sees your name, your note.");
    await expect(sheet.getByRole("button", { name: "Send to Rekha" })).toBeEnabled();
  },
);

step(
  "J-TEAMUP/3",
  "S-09",
  "Send to Rekha: Sent to Rekha with the note shown back; the card reads Waiting for Rekha, with Withdraw",
  { needs: ["S-09", "C-SHEET-TEAMUP", "L-TEAMUP"], changes: ["R1"] }, // a new request on R1
  async ({ page }) => {
    await r1ForBhavesh(page);
    await page.getByRole("button", { name: "Team up", exact: true }).click();
    const sheet = page.getByRole("dialog", { name: "Team up with Rekha" });
    await sheet.getByRole("textbox").fill(NOTE);
    await expect(sheet).toContainText("Looks good.");
    await sheet.getByRole("button", { name: "Send to Rekha" }).click();

    await expect(sheet).toContainText("Sent to Rekha");
    await expect(sheet).toContainText(
      "Rekha reads your note, then approves or declines. You’ll hear in your Inbox.",
    );
    await expect(sheet).toContainText(NOTE);
    await expect(sheet.getByRole("button", { name: "Withdraw request" })).toBeVisible();
    await sheet.getByRole("button", { name: "Done" }).click();
    await expect(page.getByText("Waiting for Rekha", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Withdraw", exact: true })).toBeVisible();
  },
);

step(
  "J-TEAMUP/4",
  "S-H2B",
  "Rekha reads Bhavesh's note word for word in her Inbox and approves",
  { needs: ["S-H2B", "S-H5", "L-INBOX", "L-TEAMUP"], changes: ["R1"] }, // Bhavesh joins R1's crew
  async ({ page }) => {
    const r1 = await seeded("R1");
    await signInAs(page, "rekha");
    await page.goto("/inbox");
    // The request withdrawn in row 2 may still be listed; newest first (L-INBOX.rules/4), so row 3's is the first.
    await page
      .getByRole("button", {
        name: new RegExp(`^Bhavesh Patel asks to team up(?: [^,]+)?, ${esc(r1.title)}, `),
      })
      .first()
      .click();
    await expect(page.getByText(NOTE, { exact: true })).toBeVisible();
    // L-TEAMUP.rules/6: no idea brought, so Approve (team up only) or Decline.
    await expect(page.getByRole("button", { name: "Decline", exact: true })).toBeEnabled();
    await expect(page.getByRole("button", { name: "Merge it", exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Approve", exact: true }).click();
    await expect(page.getByText(/^Teamed up\. Bhavesh is on your crew\./).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Say hello to Bhavesh" })).toHaveAttribute(
      "href",
      // BLD-F069: "Say hello" may end in #say-hello, which puts the cursor in the message box on S-08.
      new RegExp(`${esc(ideaUrl(r1, "/conversation"))}(?:#say-hello)?$`),
    );
  },
);

step(
  "J-TEAMUP/5",
  "S-H5",
  "Bhavesh's Inbox says Rekha approved; R1 is under My ideas, Teamed up; Say hello opens the conversation",
  { needs: ["S-H5", "C-INBOX-READER", "L-INBOX", "L-TEAMUP", "S-07"] },
  async ({ page }) => {
    const r1 = await seeded("R1");
    await signInAs(page, "bhavesh");
    await page.goto("/inbox");
    await page
      .getByRole("button", {
        name: new RegExp(`^Rekha Saxena approved your team-up request, ${esc(r1.title)}, `),
      })
      .click();
    await expect(page.getByRole("link", { name: "Say hello" })).toHaveAttribute(
      "href",
      // BLD-F069: "Say hello" may end in #say-hello, which puts the cursor in the message box on S-08.
      new RegExp(`${esc(ideaUrl(r1, "/conversation"))}(?:#say-hello)?$`),
    );

    await page.goto("/my-ideas");
    await page.getByRole("tab", { name: /^Teamed up/ }).click();
    await expect(
      page.getByText(new RegExp(`^Rekha Saxena’s idea, you teamed up ${DAY}, ${esc(r1.ref ?? "")}$`)),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: new RegExp(esc(r1.title)) }).first()).toBeVisible();
  },
);

step(
  "J-TEAMUP/6",
  "S-08",
  "Both in the idea's conversation: what Bhavesh writes is what Rekha reads",
  { needs: ["S-08", "L-CONVO", "L-TEAMUP"], changes: ["R1"] }, // a message in R1's conversation
  async ({ page, browser }, info) => {
    const r1 = await seeded("R1");
    await signInAs(page, "bhavesh");
    await page.goto(ideaUrl(r1, "/conversation"));
    await expect(page.getByText(/^Rekha Saxena approved your team-up request\./).first()).toBeVisible();
    await expect(page.getByText("The crew and the review desk see this conversation.")).toBeVisible();
    await page.getByRole("textbox", { name: "Message the crew" }).fill(HELLO);
    await page.getByRole("button", { name: "Send", exact: true }).click();
    await expect(page.getByText(HELLO, { exact: true })).toBeVisible();

    const context = await browser.newContext();
    const lead = await context.newPage();
    try {
      await signInAs(lead, "rekha");
      await lead.goto(ideaUrl(r1, "/conversation"));
      await expect(lead.getByText(HELLO, { exact: true })).toBeVisible();
      await expect(lead.getByText("Bhavesh Patel", { exact: true }).first()).toBeVisible();
    } finally {
      await snap(lead, info, "J-TEAMUP/6", "S-08", "rekha");
      await context.close();
    }
  },
);
