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
 * the new note, Rekha approves it (row 4), and the two talk in R1's conversation (row 6). Row 3b (DEC-126) finds that
 * request on Bhavesh's crew deck as "Requested", withdraws it there and sends the same note again, so row 4 reads the
 * newest request; its passes on the way are put back with "See them again" (he has no seeded passes). Row 3c does the
 * same on Bhavesh's Home crew card (DEC-126 (6), BLD-C219), where Next passes nothing. R1 is shared with
 * J-SIMILAR (lib SEED): both only add requests, crew and messages, and nobody decides it, so no row here depends on
 * whether R1 is picked. Row 1 ends with the sheet open from a card, which is where row 2 starts. Rows 6b and 6c
 * (DEC-124, walk item WF-01): Rekha sends a file and a link with the "+" in R1's conversation, the crew reads it, and
 * the review desk finds the file there but not among S-R2's attachments (BLD-B274); files are made here (lib pdfWith).
 */
import { expect, type Page } from "@playwright/test";

import {
  addFile,
  carriedFor,
  expectNoSeriousAxeIssues,
  ideaUrl,
  openPicker,
  PLUS,
  runSeconds,
  seeded,
  signInAs,
  snap,
  step,
} from "./lib";

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

/** A crew card's reason for being shown (L-CREW/2; deck.py builds every one of these shapes). */
const CREW_REASON =
  /(?: as your idea from .+|, like your idea from .+|^Close to your idea from .+|^They need someone in .+|^Your area, .+|^Same office as you, .+)$/;

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
    // Row 1's "why it is shown": each card's reason line, in one of L-CREW's shapes (services/worker/crew/deck.py:
    // close_reason, touches_reason, area_reason, office_reason; Crew.md "Same office as you, Hyderabad").
    await expect(page.getByText(CREW_REASON).first()).toBeVisible();
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
  "J-TEAMUP/3b",
  "S-H2",
  "Find your crew after the request: R1 is last as Requested, still last after a reload; Withdraw brings Team up back in its place, and the note goes again",
  { needs: ["S-H2", "C-CREW-DECK", "L-CREW", "C-SHEET-TEAMUP", "L-TEAMUP"], changes: ["R1"] }, // withdraws row 3's request and sends it again
  async ({ page }, info) => {
    info.setTimeout(120_000); // a pass per card on the way to R1, each with its 620 ms flight
    const r1 = await seeded("R1");
    const requested = page.getByRole("button", { name: `Requested: you asked to team up on ${r1.title}` });
    const withdraw = page.getByRole("button", { name: `Withdraw your request to team up on ${r1.title}` });
    const teamUp = page.getByRole("button", {
      name: new RegExp(`^Team up on ${esc(r1.title)}: send Rekha a note$`),
    });
    const position = page.getByText(/^Idea \d+ of \d+$/);
    await signInAs(page, "bhavesh");
    await page.goto("/crew");
    await expect(page.getByRole("heading", { level: 1, name: "Find your crew" })).toBeVisible();

    // DEC-126 (2): the idea asked about comes after every other card, and stays last after a reload (L-CREW/3).
    const total = Number((await position.innerText()).replace(/^Idea \d+ of /, ""));
    await expect(page.locator(".dcard").last()).toContainText(r1.title);
    await page.reload();
    await expect(position).toHaveText(`Idea 1 of ${total}`);
    await expect(page.locator(".dcard").last()).toContainText(r1.title);

    // Next is a pass (L-CREW/6): Bhavesh passes the cards in front of R1; "See them again" puts them back below.
    for (let n = 2; n <= total; n++) {
      await page.getByRole("button", { name: "Next idea" }).click();
      await expect(position).toHaveText(`Idea ${n} of ${total}`);
    }
    // (1) "Requested", greyed and inactive but still read out as its state; (3) "Withdraw" under it.
    await expect(requested).toBeVisible();
    await expect(requested).toHaveAttribute("aria-disabled", "true");
    await expect(withdraw).toBeVisible();
    await expectNoSeriousAxeIssues(page);

    // (4) Withdraw: "Team up" again in the same place, with focus on it, and the card does not move.
    await withdraw.click();
    await expect(teamUp).toBeVisible();
    await expect(teamUp).toBeFocused();
    await expect(requested).toHaveCount(0);
    await expect(position).toHaveText(`Idea ${total} of ${total}`);
    await expectNoSeriousAxeIssues(page);

    // The same note again from the card's sheet (it opens on a drafted note), so row 4 reads NOTE word for word.
    await teamUp.click();
    const sheet = page.getByRole("dialog", { name: "Team up with Rekha" });
    await sheet.getByRole("textbox").fill(NOTE);
    await sheet.getByRole("button", { name: "Send to Rekha" }).click();
    await expect(sheet).toContainText("Sent to Rekha");
    await sheet.getByRole("button", { name: "Keep looking" }).click();
    // R1 was the last card, so the deck ends; "See them again" puts back every pass made above.
    await expect(page.getByRole("heading", { level: 2, name: "That's everyone for now" })).toBeVisible();
    await page.getByRole("button", { name: "See them again" }).click();
    await expect(position).toHaveText(`Idea 1 of ${total}`);
    await expect(page.getByText("None passed")).toBeVisible();
    await expect(page.locator(".dcard").last()).toContainText(r1.title);
    await expect(page.locator(".dcard").last()).toContainText("Requested");
  },
);

step(
  "J-TEAMUP/3c",
  "S-03",
  "Home's crew card after the request: R1 is last as Requested, still last after a reload; Withdraw brings Team up back in its place, and the note again hands focus back to Requested",
  {
    needs: ["S-03", "C-CREW-DECK", "L-CREW", "C-SHEET-TEAMUP", "L-TEAMUP", "BLD-C219"],
    changes: ["R1"], // withdraws row 3b's request and sends it again
    after: ["J-TEAMUP/3b"],
  },
  async ({ page }) => {
    const r1 = await seeded("R1");
    // Home's "Find your crew" (S-03.sections/3): its deck's cards are `.dcard`; only the front one is read out.
    const crew = page.locator("#hm-crew");
    const position = crew.getByText(/^Idea \d+ of \d+$/);
    const requested = crew.getByRole("button", { name: `Requested: you asked to team up on ${r1.title}` });
    const withdraw = crew.getByRole("button", { name: `Withdraw your request to team up on ${r1.title}` });
    const teamUp = crew.getByRole("button", {
      name: new RegExp(`^Team up on ${esc(r1.title)}, with Rekha\\b`),
    });
    await signInAs(page, "bhavesh");
    await page.goto("/home");

    // DEC-126 (2), (6), BLD-F094 (4): Home's short read ends with the idea asked about, after a reload too.
    await expect(position).toHaveText(/^Idea 1 of \d+$/);
    const total = Number((await position.innerText()).replace(/^Idea 1 of /, ""));
    await expect(crew.locator(".dcard").last()).toContainText(r1.title);
    await page.reload();
    await expect(position).toHaveText(`Idea 1 of ${total}`);
    await expect(crew.locator(".dcard").last()).toContainText(r1.title);

    // Next on Home only moves the deck; nothing is passed (BLD-C219's tests: no call).
    for (let n = 2; n <= total; n++) {
      await crew.getByRole("button", { name: "Next idea" }).click();
      await expect(position).toHaveText(`Idea ${n} of ${total}`);
    }
    // (1), (3): "Requested" in Team up's place, greyed and inactive but still read out, with "Withdraw" under it.
    await expect(requested).toBeVisible();
    await expect(requested).toHaveAttribute("aria-disabled", "true");
    await expect(withdraw).toBeVisible();
    await expect(teamUp).toHaveCount(0);
    await expectNoSeriousAxeIssues(page);

    // (4) Withdraw: Team up again where the card stands, with focus on it; the card does not move.
    await withdraw.click();
    await expect(teamUp).toBeVisible();
    await expect(teamUp).toBeFocused();
    await expect(requested).toHaveCount(0);
    await expect(position).toHaveText(`Idea ${total} of ${total}`);
    await expectNoSeriousAxeIssues(page);

    // The same note again from Home's sheet, so row 4 reads NOTE. Done hands focus back to "Requested" (WCAG 2.4.3),
    // on the card in front, which is still the last.
    await teamUp.click();
    const sheet = page.getByRole("dialog", { name: "Team up with Rekha" });
    await sheet.getByRole("textbox").fill(NOTE);
    await sheet.getByRole("button", { name: "Send to Rekha" }).click();
    await expect(sheet).toContainText("Sent to Rekha");
    await sheet.getByRole("button", { name: "Done" }).click();
    await expect(sheet).toHaveCount(0);
    await expect(requested).toBeFocused();
    await expect(position).toHaveText(`Idea ${total} of ${total}`);
    await expect(crew.locator(".dcard").last()).toContainText(r1.title);
    await expectNoSeriousAxeIssues(page);
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
    // The requests withdrawn in rows 2, 3b and 3c may still be listed; newest first (L-INBOX.rules/4), so the one row
    // 3c sent is the first.
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

// --- Walk item WF-01 in the conversation: S-08's "+" (DEC-124, BLD-F095) ------------------------------------------

/** Rekha's message with her file and a link (row 6b). Synthetic words and a synthetic SharePoint address. */
const WITH_FILE = "Here are the branch notes on failed SIP debits, and the reasons page we keep.";
const REASONS_LINK = "https://synthetic.sharepoint.com/sites/branch-ops/sip-debit-reasons";
/** S-08's line on a file with a customer detail found: it can't go in the conversation (DEC-107, BLD-F095). */
const HAS_DETAIL =
  "This file has a customer detail in it, so it can’t be sent in the conversation. Remove it to send your message.";
/**
 * DEC-129 (the product lead, 22 Nov): the crew opens the idea's checked conversation files, as P-PRODUCT.privacy says
 * (BLD-F062 lifted). A file with a customer detail found never reaches the crew (DEC-127), and the crew has no "+".
 */
const CREW_SEES_FILES = true;

/** A file's row in S-08's box (C-FILE.row): the list "Your files" (a link goes into the words, so no link rows). */
function convoRow(page: Page, name: string) {
  return page.getByRole("list", { name: "Your files" }).getByRole("listitem").filter({ hasText: name });
}

step(
  "J-TEAMUP/6b",
  "S-08",
  'Rekha\'s "+" in the conversation: a checked file and a link go with her message, a file with a customer detail stays out, and the crew reads the message and opens the checked file',
  {
    needs: ["S-08", "C-PROMPT.attach", "C-FILE", "L-CONVO", "BLD-F095"],
    changes: ["R1"],
    after: ["J-TEAMUP/6"],
  },
  async ({ page, browser }, info) => {
    info.setTimeout(150_000); // two files through their checks (up to 30 s each) and three axe runs
    const r1 = await seeded("R1");
    const carried = carriedFor<{ file: string }>("J-TEAMUP");
    const name = `branch-sip-debit-notes-${runSeconds()}.pdf`;
    const found = `courier-callback-${runSeconds()}.pdf`;
    carried.file = name;
    const box = page.getByRole("textbox", { name: "Message the crew" });

    await signInAs(page, "rekha");
    await page.goto(ideaUrl(r1, "/conversation"));
    await expect(page.getByText(HELLO, { exact: true })).toBeVisible();
    // DEC-124: the "+" comes first in the box's tool row (BLD-F095: `.cv-row.cfoot`), for the sharer (BLD-F063).
    await expect(page.locator(".cfoot").getByRole("button").first()).toHaveAccessibleName(PLUS);
    await expect(page.getByRole("button", { name: PLUS })).toHaveAttribute("title", PLUS);

    // The picker, with Home's words; a link goes into the words, so it has no internal or external line.
    await box.fill(WITH_FILE);
    const picker = await openPicker(page);
    await expect(picker.getByText(/^Drop files or a folder here, or/)).toBeVisible();
    for (const label of ["browse", "Choose a folder", "Add link"]) {
      await expect(picker.getByRole("button", { name: label, exact: true })).toBeVisible();
    }
    await expectNoSeriousAxeIssues(page);
    const link = picker.getByRole("textbox", { name: "Or paste a link to a page, file or idea" });
    await link.focus();
    await expect(link).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(picker).toHaveCount(0);
    await expect(page.getByRole("button", { name: PLUS })).toBeFocused();

    // A link goes into the words as typed, never a row and never fetched (non-negotiable 8).
    const again = await openPicker(page);
    await again.getByRole("textbox", { name: "Or paste a link to a page, file or idea" }).fill(REASONS_LINK);
    await again.getByRole("button", { name: "Add link", exact: true }).click();
    await expect(box).toHaveValue(new RegExp(`^${esc(WITH_FILE)} ${esc(REASONS_LINK)}\\s*$`));

    // A checked file is a row in the box; one with a customer detail (a synthetic number, as J-RECOVER/8) can't go.
    await addFile(page, name, "Failed SIP debits by reason, branch notes, week 47.");
    await expect(convoRow(page, name).getByText("Checked", { exact: true })).toBeVisible({ timeout: 30_000 });
    await addFile(page, found, "Investor called back on 9800000012 about the failed debit.");
    await expect(convoRow(page, found).getByText(HAS_DETAIL, { exact: true })).toBeVisible({
      timeout: 30_000,
    });
    await convoRow(page, found)
      .getByRole("button", { name: `Remove ${found}` })
      .click();
    await expect(convoRow(page, found)).toHaveCount(0);

    // Send: the words with the link, and the file on the message with View (L-CONVO/7); the box is empty again.
    await page.getByRole("button", { name: "Send", exact: true }).click();
    const onMessage = page.getByRole("list", { name: "Files in your message" }).last();
    await expect(onMessage.getByRole("link", { name: `View ${name}` })).toHaveAttribute(
      "href",
      /^\/api\/files\/ATT-\d{4}-\d{6}\/view$/,
    );
    await expect(page.getByText(REASONS_LINK).last()).toBeVisible();
    await expect(page.getByRole("list", { name: "Your files" })).toHaveCount(0);
    await expect(box).toHaveValue("");
    await expect(page.getByText(found)).toHaveCount(0);
    await expectNoSeriousAxeIssues(page);

    // The crew: the message, no "+" (BLD-F063), and the checked file (DEC-129).
    const context = await browser.newContext();
    const crew = await context.newPage();
    try {
      await signInAs(crew, "bhavesh");
      await crew.goto(ideaUrl(r1, "/conversation"));
      await expect(crew.getByText(WITH_FILE).last()).toBeVisible();
      await expect(crew.getByRole("button", { name: PLUS })).toHaveCount(0);
      if (CREW_SEES_FILES) {
        const view = crew.getByRole("link", { name: `View ${name}` });
        await expect(view).toBeVisible();
        const href = (await view.getAttribute("href")) ?? "";
        expect(href, "the crew's View names the file").toMatch(/^\/api\/files\/ATT-\d{4}-\d{6}\/view$/);
        expect((await crew.request.get(href)).status(), "the crew opens a checked file").toBe(200);
        // DEC-127: the file with a customer detail never reaches the crew (it can't be sent, BLD-F095).
        await expect(crew.getByText(found)).toHaveCount(0);
      } else {
        await expect(crew.getByText(name)).toHaveCount(0);
      }
      await expectNoSeriousAxeIssues(crew);
    } finally {
      await snap(crew, info, "J-TEAMUP/6b", "S-08", "bhavesh");
      await context.close();
    }
  },
);

step(
  "J-TEAMUP/6c",
  "S-R2",
  "The review desk has the \"+\" in the conversation and reads Rekha's file there; S-R2's attachments leave it out",
  {
    needs: ["S-08", "L-CONVO", "BLD-F095", "S-R2", "BLD-B274"],
    changes: ["R1"], // opening S-R2 may mark R1 as read by the desk
    after: ["J-TEAMUP/6b"],
  },
  async ({ page }) => {
    const r1 = await seeded("R1");
    const name = carriedFor<{ file: string }>("J-TEAMUP").file;
    expect(name, "row 6b names the file it sent").toBeTruthy();

    await signInAs(page, "lavanya");
    await page.goto(ideaUrl(r1, "/conversation"));
    // BLD-F063, BLD-B270: the review desk may attach, and reads the files on a message.
    await expect(page.getByRole("button", { name: PLUS })).toBeVisible();
    await expect(page.getByRole("link", { name: `View ${name ?? ""}` })).toBeVisible();

    // BLD-B274: a conversation file is not one of the idea's attachments on S-R2.
    await page.goto(`/desk/ideas/${r1.ref ?? r1.uuid}`);
    await expect(page.getByRole("heading", { name: "Attachments and artefacts" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Attached", exact: true })).toBeVisible();
    await expect(page.getByText(name ?? "")).toHaveCount(0);
  },
);
