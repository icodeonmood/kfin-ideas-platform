/**
 * J-TRACK: the sharer tracks an idea, answers the desk and reads the decision (1pc-handoff/03-journeys/J-TRACK.md).
 * Hand-offs only; the detail of each screen is in V-ACC.track.
 * Copy: reference/copy/Status.md (S-06), Inbox.md (S-H5), Home.md (S-03 Needs you), Answer.md (S-R3), Messages.md
 * (S-08), Wall.md. Teams is off (DEC-105): only in-app surfaces are checked, and a line that names Teams or email is
 * checked up to the sentence before. BLD-E008: a board's she/her for a run-time person reads as their first name or
 * "their". The board's straight double quotes around a title are matched with either straight or curly quotes.
 * Cast: Kavya (sharer) is Tanvi, Meera (reviewer) the record's reviewer, Rohan (committee) Manoj, Arjun's build team
 * Gopal's.
 * Seed: T5 (with the desk, not opened, edit open) for the edit window and the withdraw variation; T6 (Harish's three
 * questions, seen, the first answer saved but not sent, a reminder in the Inbox) is answered; T7 (picked 5 days ago)
 * and T8 (not now) for the decision; T9 (not picked, reversed to picked by Manoj) for the committee; A1 (Aparna's,
 * being built, Gopal asks her to check something) for the build team; V1 (Varun's, shipped, measured) for the end.
 * T7, T8, T9, A1 and V1 are read only.
 */
import { expect, type Locator, type Page } from "@playwright/test";

import { ideaUrl, seeded, signInAs, step, type Person } from "./lib";

// --- Patterns for run-time parts of the copy ----------------------------------------------------------------------------

const DAY = String.raw`[A-Z][a-z]+day \d{1,2} [A-Z][a-z]+`; // "Wednesday 16 December"
const DAY_Y = String.raw`${DAY}(?: \d{4})?`; // "Tuesday 16 February 2027"
const TIME = String.raw`\d{1,2}(?::\d{2})? (?:am|pm)`; // "11:20 am", "6 pm"
const LEFT = String.raw`(?:\d+ days?|\d{2}:\d{2}) left`; // "3 days left", "07:38 left"
const OPEN_Q = `["“]`;
const CLOSE_Q = `["”]`;

/** T6's three questions from Harish (club_seed `_review`), in order, with the part each answer goes to. */
const T6_QUESTIONS = [
  "How many folios were held last month?",
  "Which teams see the hold first?",
  "Is there a report that shows the holds?",
] as const;
/** Saved by Tanvi before the journey (not sent); goes with the answers she sends in J-TRACK/4. */
const SAVED_ANSWER = "About 120, mostly in one region.";
/** What Tanvi types for question 2 in J-TRACK/4 and finds under its part in J-TRACK/5. */
const TYPED_ANSWER = "The new folio desk sees the hold first, then the KYC team a day later.";

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** The part of the Wall under a heading: the region it names, or else the innermost section that holds it. */
function wallPart(page: Page, heading: RegExp): Locator {
  return page
    .getByRole("region", { name: heading })
    .or(
      page
        .locator("section")
        .filter({ has: page.getByRole("heading", { name: heading }) })
        .last(),
    )
    .first();
}

/** The text of `loc` once it matches `re`: its first group, or the whole match when `re` has no group. */
async function capture(loc: Locator, re: RegExp): Promise<string> {
  await expect(loc).toHaveText(re);
  const m = (await loc.innerText()).replace(/\s+/g, " ").trim().match(re);
  if (!m) throw new Error(`no match for ${re}`);
  return m[1] ?? m[0];
}

/** An Inbox item, by the start of its accessible name: "{sender} {what}, {idea title}, …" (Inbox.md Controls). */
function inboxItem(page: Page, sender: string, what: string, title: string): Locator {
  return page.getByRole("button", { name: new RegExp(`^${esc(sender)} ${what}, ${esc(title)}, `) });
}

async function openInbox(page: Page, who: Person, tab?: RegExp): Promise<void> {
  await signInAs(page, who);
  await page.goto("/inbox");
  await expect(page.getByRole("heading", { level: 1, name: "Inbox" })).toBeVisible();
  if (tab) {
    await page.getByRole("tab", { name: tab }).click();
    await expect(page.getByRole("tab", { name: tab, selected: true })).toBeVisible();
  }
}

// --- J-TRACK.steps ---------------------------------------------------------------------------------------------------

step(
  "J-TRACK/1",
  "S-06",
  "With the review desk: the reference, when the desk looks, and Edit or Withdraw while the window is open",
  { needs: ["S-06", "C-TRACK", "L-SUBMIT"] },
  async ({ page }) => {
    const t5 = await seeded("T5");
    await signInAs(page, "tanvi");
    await page.goto(ideaUrl(t5));
    await expect(page.getByRole("heading", { level: 1, name: t5.title })).toBeVisible();
    await expect(page.getByText(t5.ref ?? "", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("With the review desk", { exact: true }).first()).toBeVisible();
    await expect(
      page.getByText(new RegExp(`^The review desk will look at it by ${DAY}\\.`)).first(),
    ).toBeVisible();
    // L-SUBMIT.edit: open until the desk opens it, at most 3 days, with the countdown.
    await expect(
      page
        .getByText(
          new RegExp(
            `^Open to changes until ${DAY}\\. Edit or withdraw it any time before the review desk opens it\\.`,
          ),
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByText(new RegExp(`^${LEFT}$`)).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Edit it" })).toHaveAttribute(
      "href",
      new RegExp(`${esc(ideaUrl(t5, "/edit"))}$`),
    );
    await expect(page.getByRole("button", { name: "Withdraw" })).toBeVisible();
  },
);

step(
  "J-TRACK/2",
  "S-H5",
  "The desk's questions reach the Inbox's Needs you and Home's Needs you, each with the countdown",
  { needs: ["S-H5", "C-INBOX-READER", "L-INBOX", "L-QUESTIONS", "L-NOTIFY", "S-03"] },
  async ({ page }) => {
    const t6 = await seeded("T6");
    await openInbox(page, "tanvi", /^Needs you/);
    const item = inboxItem(page, "Harish from the review desk", "asked you 3 questions", t6.title);
    await expect(item).toContainText(new RegExp(LEFT));
    await item.click();
    await expect(page.getByText("Questions from the review desk", { exact: true }).first()).toBeVisible();
    for (const q of T6_QUESTIONS) await expect(page.getByText(q, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(new RegExp(`^Answer by ${DAY}, ${TIME}\\.$`)).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Answer the questions" })).toBeVisible();

    // Home's Needs you carries the same questions and the same clock (S-03, Home.md).
    await page.goto("/home");
    await expect(page.getByRole("heading", { level: 2, name: "Needs you" })).toBeVisible();
    await expect(page.getByText("3 questions from the review desk").first()).toBeVisible();
    await expect(
      page
        .getByText(
          new RegExp(`^Harish from the review desk asked about ${OPEN_Q}${esc(t6.title)}${CLOSE_Q}$`),
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByText(T6_QUESTIONS[0], { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Answer the questions" }).first()).toHaveAttribute(
      "href",
      new RegExp(`${esc(ideaUrl(t6, "/answer"))}$`),
    );
  },
);

step(
  "J-TRACK/3",
  "S-06",
  "The questions are a card on the idea and in its conversation, with one deadline; the idea is closed to edits",
  { needs: ["S-06", "C-QCARD", "L-SUBMIT", "L-QUESTIONS", "S-08", "L-CONVO"] },
  async ({ page }) => {
    const t6 = await seeded("T6");
    await signInAs(page, "tanvi");
    await page.goto(ideaUrl(t6));
    await expect(page.getByText("Needs you", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Harish has 3 questions for you", { exact: true })).toBeVisible();
    for (const q of T6_QUESTIONS) await expect(page.getByText(q, { exact: true }).first()).toBeVisible();
    const deadline = await capture(
      page.getByText(/^Answer by .*One at a time, typed or spoken\.$/).first(),
      new RegExp(`^Answer by (${DAY}, ${TIME})\\. One at a time, typed or spoken\\.$`),
    );
    // L-SUBMIT.edit/5: opened by the desk, so locked; no Withdraw.
    await expect(
      page
        .getByText(
          new RegExp(
            `^The review desk opened it on ${DAY}, so the idea itself can’t be changed now\\. Write to them in the conversation\\.$`,
          ),
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Withdraw" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Answer the questions" }).first()).toHaveAttribute(
      "href",
      new RegExp(`${esc(ideaUrl(t6, "/answer"))}$`),
    );

    // The conversation shows the same card and the same deadline (S-08, Messages.md).
    await page.getByRole("link", { name: "Open the conversation" }).first().click();
    await page.waitForURL(new RegExp(`${esc(ideaUrl(t6, "/conversation"))}$`));
    await expect(page.getByText("Harish has 3 questions about your idea", { exact: true })).toBeVisible();
    await expect(
      page.getByText(
        `Answer by ${deadline}. One at a time, typed or spoken, and each answer is added to its part of your idea.`,
      ),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Answer the questions" }).first()).toBeVisible();
  },
);

step(
  "J-TRACK/4",
  "S-R3",
  "Answers one at a time: the saved answer, a typed one and a skip; Send 2 answers to Harish",
  { needs: ["S-R3", "L-QUESTIONS"], changes: ["T6"] },
  async ({ page }) => {
    const t6 = await seeded("T6");
    await signInAs(page, "tanvi");
    await page.goto(ideaUrl(t6, "/answer"));
    await expect(page.getByRole("heading", { level: 1, name: "Answer the review desk" })).toBeVisible();
    await expect(
      page
        .getByText(
          new RegExp(
            `^Harish from the review desk has 3 questions about ${OPEN_Q}${esc(t6.title)}${CLOSE_Q}\\. Answer them one at a time\\. Skip any you can’t answer yet and come back before you send\\.$`,
          ),
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Question 1, answered" })).toBeVisible();

    await page.getByRole("button", { name: "Question 2, not answered yet" }).click();
    await expect(page.getByText(T6_QUESTIONS[1], { exact: true }).first()).toBeVisible();
    const box = page.getByRole("textbox", {
      name: /^(Your answer to question 2|Type your answer, or tap the mic and say it)$/,
    });
    await box.fill(TYPED_ANSWER);
    await box.press("Enter");
    await expect(page.getByText(T6_QUESTIONS[2], { exact: true }).first()).toBeVisible();
    await page.getByRole("button", { name: "Skip for now" }).click();
    await page.getByRole("button", { name: "Check your answers and send" }).click();

    // Checking: what she gave, word for word, and what stays open.
    await expect(page.getByText("Check your answers", { exact: true }).first()).toBeVisible();
    await expect(page.getByText(SAVED_ANSWER, { exact: true })).toBeVisible();
    await expect(page.getByText(TYPED_ANSWER, { exact: true })).toBeVisible();
    await expect(page.getByText("Not answered. It stays open until the deadline.")).toBeVisible();
    await page.getByRole("button", { name: "Send 2 answers to Harish" }).click();

    await expect(page.getByText(new RegExp(`^Sent to Harish, ${TIME}$`)).first()).toBeVisible();
    await expect(page.getByText("Your answers are with the review desk", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "See your idea" })).toHaveAttribute(
      "href",
      new RegExp(`${esc(ideaUrl(t6))}$`),
    );
  },
);

step(
  "J-TRACK/5",
  "S-06",
  "Sent. Harish has your answers: each answer under its part of the idea",
  { needs: ["S-06", "L-QUESTIONS", "S-R3"] },
  async ({ page }) => {
    const t6 = await seeded("T6");
    await signInAs(page, "tanvi");
    await page.goto(ideaUrl(t6));
    await expect(page.getByText(/^Sent\. Harish has your answers\./).first()).toBeVisible();
    await expect(
      page.getByText(/Each answer was added to its part of your idea, under What you shared\./).first(),
    ).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "What you shared" })).toBeVisible();
    // The answers from J-TRACK/4, word for word, each with where it came from (S-06.layout/5).
    await expect(page.getByText(SAVED_ANSWER, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(TYPED_ANSWER, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(new RegExp(`^From your answer to Harish, ${DAY}$`))).toHaveCount(2);
    await expect(page.getByRole("link", { name: "Open the conversation" }).first()).toBeVisible();
  },
);

step(
  "J-TRACK/6",
  "S-H5",
  "A reminder before the deadline: the Inbox item says how long is left and leads to Answer the questions",
  { needs: ["S-H5", "C-INBOX-READER", "L-INBOX", "L-QUESTIONS", "L-NOTIFY"] },
  async ({ page }) => {
    const t6 = await seeded("T6");
    await openInbox(page, "tanvi");
    // L-INBOX.kinds "Answer reminder" (row text NOT DRAWN: "1 day left to answer Meera's questions"), from 1% Club.
    const item = inboxItem(
      page,
      "1% Club",
      String.raw`(?:\d+ days?|\d+ hours?) left to answer Harish[’']s questions`,
      t6.title,
    );
    await expect(item).toBeVisible();
    await item.click();
    await expect(page.getByRole("link", { name: "Answer the questions" })).toHaveAttribute(
      "href",
      new RegExp(`${esc(ideaUrl(t6, "/answer"))}$`),
    );
  },
);

step(
  "J-TRACK/7",
  "S-06",
  "The decision arrives in the Inbox and the idea's page shows it with the reason word for word",
  { needs: ["S-H5", "C-INBOX-READER", "L-INBOX", "S-06", "L-DECIDE"] },
  async ({ page }) => {
    const t7 = await seeded("T7");
    const t8 = await seeded("T8");
    await openInbox(page, "tanvi");
    await inboxItem(page, "Harish from the review desk", "picked your idea", t7.title).click();
    await page.getByRole("link", { name: "Read the decision" }).click();
    await page.waitForURL(new RegExp(`${esc(ideaUrl(t7))}$`));

    await expect(page.getByText("Picked", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Picked. A team is being chosen to build it.").first()).toBeVisible();
    await expect(
      page
        .getByText(
          new RegExp(
            `^Harish from the review desk picked it on ${DAY}\\. The build team is chosen by ${DAY}\\.$`,
          ),
        )
        .first(),
    ).toBeVisible();
    // L-DECIDE.rules/3, BLD-E004: the reason, word for word, in the app.
    await expect(
      page
        .getByText(
          "This is a clear problem with a simple fix. The wording needs compliance sign-off, which the team can get.",
        )
        .first(),
    ).toBeVisible();

    // Not now names the date it comes back.
    await page.goto(ideaUrl(t8));
    await expect(
      page.getByText(new RegExp(`^Not now\\. The review desk looks at it again on ${DAY_Y}\\.$`)).first(),
    ).toBeVisible();
    await expect(
      page
        .getByText(
          "The right idea, but fees need a pricing policy first. We will look again once that is in place.",
        )
        .first(),
    ).toBeVisible();
  },
);

step(
  "J-TRACK/8",
  "S-06",
  "The committee's window on the page; a reversal arrives with the note and the new decision, final",
  { needs: ["S-06", "L-COMMITTEE", "S-H5", "C-INBOX-READER", "L-INBOX"] },
  async ({ page }) => {
    const t7 = await seeded("T7");
    const t9 = await seeded("T9");
    await signInAs(page, "tanvi");
    await page.goto(ideaUrl(t7));
    await expect(
      page
        .getByText(
          new RegExp(
            `^The Ones Committee can review this decision until ${DAY}\\. If they change it, their note comes to your Inbox\\. After that, it stands\\.$`,
          ),
        )
        .first(),
    ).toBeVisible();

    // The reversal: Inbox → Read the note → the page with the new decision (S-06 "Reversed by the Ones Committee").
    await page.goto("/inbox");
    await inboxItem(
      page,
      "Manoj Agarwal from the Ones Committee",
      "reversed a decision on your idea",
      t9.title,
    ).click();
    await page.getByRole("link", { name: "Read the note" }).click();
    await page.waitForURL(new RegExp(`${esc(ideaUrl(t9))}$`));
    await expect(page.getByText("The Ones Committee changed the decision to picked").first()).toBeVisible();
    await expect(
      page
        .getByText(
          "“We can ask the exchange to move the reminder. Failed dividends cost more than the change.”",
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByText("The committee’s note to you").first()).toBeVisible();
    await expect(page.getByText(new RegExp(`Lavanya from the review desk, ${DAY}`)).first()).toBeVisible();
    await expect(page.getByText(/^This is final\./).first()).toBeVisible();
  },
);

step(
  "J-TRACK/9",
  "S-08",
  "Picked and building: the build team asks the sharer to check something by a date, in the conversation",
  { needs: ["S-H5", "C-INBOX-READER", "L-INBOX", "S-08", "L-CONVO", "L-DECIDE"] },
  async ({ page }) => {
    const a1 = await seeded("A1");
    await openInbox(page, "aparna", /^Needs you/);
    const item = inboxItem(page, "Gopal Iyengar", "asked you to check new messages", a1.title);
    await expect(item).toContainText(/By [A-Z][a-z]{2}, \d{1,2} [A-Z][a-z]{2}/);
    await item.click();
    await page.getByRole("link", { name: "Open the conversation" }).click();
    await page.waitForURL(new RegExp(`${esc(ideaUrl(a1, "/conversation"))}$`));

    await expect(page.getByRole("heading", { level: 1, name: a1.title })).toBeVisible();
    await expect(page.getByText("Your idea, being built by Gopal Iyengar’s team").first()).toBeVisible();
    await expect(
      page
        .getByText("The first pre-filled forms are ready to try. Please check them before Thursday.")
        .first(),
    ).toBeVisible();
    await expect(
      page.getByText("You, the build team and the review desk see this conversation."),
    ).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Message the build team" })).toBeVisible();
  },
);

step(
  "J-TRACK/10",
  "S-06",
  "Shipped and measured: the track ends at Shipped, the Wall carries the measured difference, and the sharer is a One",
  { needs: ["S-06", "C-TRACK", "S-WALL", "L-WALL", "L-IMPACT", "L-ONES"] },
  async ({ page }) => {
    const v1 = await seeded("V1");
    await signInAs(page, "varun");
    await page.goto(ideaUrl(v1));
    await expect(page.getByRole("heading", { level: 1, name: v1.title })).toBeVisible();
    // C-TRACK.anatomy: a stage's state is its read-out suffix; at Shipped every stage is done and none is "now".
    const track = page.getByRole("list", { name: "Where it is" }).filter({ visible: true });
    await expect(track.getByText("Shipped, done", { exact: true })).toBeVisible();
    await expect(track.getByText(/, now$/)).toHaveCount(0);

    // S-WALL.impact: the live-fixes table, with the measured sentence and when it was measured.
    await page.goto("/wall");
    const impact = wallPart(
      page,
      /^(?:The Ones leaderboard|What shipped ideas (?:have )?changed(?: so far)?\.?)$/,
    );
    const row = impact.getByRole("row", { name: new RegExp(esc(v1.title)) });
    await expect(
      row.getByText("620 hours a month saved; bounced payouts down by a third", { exact: true }),
    ).toBeVisible();
    await expect(row).toContainText("30 days");

    // S-WALL.ones: Varun's card, his number beside his name ("No. 11", or the big 11 over it), and his brief.
    const ones = wallPart(page, /^The Ones$/);
    await expect(ones.getByText("Varun Chopra", { exact: true })).toBeVisible();
    await expect(ones).toContainText(
      /(?:^|\s|No\.\s?)11\s+Varun Chopra\b|\bVarun Chopra\b\W{0,3}No\.\s?11\b/,
      { useInnerText: true },
    );
    await expect(
      ones.getByText("Stopped wrong bank details before a payout goes out.", { exact: true }),
    ).toBeVisible();
  },
);

// --- Variation: withdraw at step 1, then restore -------------------------------------------------------------------------

step(
  "J-TRACK/v1",
  "S-06",
  "Withdraw while the window is open: back in your drafts, nobody else sees it; Restore it shares it again (Checking, then with the review desk)",
  { needs: ["S-06", "L-SUBMIT"], changes: ["T5"] },
  async ({ page }) => {
    const t5 = await seeded("T5");
    await signInAs(page, "tanvi");
    await page.goto(ideaUrl(t5));
    // S-06.rules/2: confirms in place on the card, with an optional reason and "Withdraw it".
    await page.getByRole("button", { name: "Withdraw" }).click();
    await page.getByRole("button", { name: "Withdraw it" }).click();

    await expect(page.getByText("Withdrawn", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Withdrawn. It’s back in your drafts.").first()).toBeVisible();
    await expect(
      page
        .getByText(
          "Nobody else can see it now. No reason given. Restoring shares it again as it was, and the review desk gets it back.",
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByText("Withdrawn before review").first()).toBeVisible();

    await page.getByRole("button", { name: "Restore it" }).click();
    // L-SUBMIT.withdraw/3 and its lifecycle: restored, it is shared again (Checking) with the same reference, and one
    // submit.check job, run by this stack's worker (WORKER_ROLES has jobs), hands it to the review desk.
    await expect(page.getByText(/^(?:Checking|With the review desk)$/).first()).toBeVisible();
    await expect(page.getByText(t5.ref ?? "", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Restore it" })).toHaveCount(0);
    await expect
      .poll(
        async () => {
          await page.reload();
          return page.getByText("With the review desk", { exact: true }).first().isVisible();
        },
        { timeout: 120_000, intervals: [5_000] },
      )
      .toBe(true);
  },
);
