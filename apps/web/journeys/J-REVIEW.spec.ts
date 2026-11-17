/**
 * J-REVIEW: a reviewer reads an idea and decides (1pc-handoff/03-journeys/J-REVIEW.md). Hand-offs only; the detail of
 * each screen is in V-ACC.review (lane B).
 * Copy: reference/copy/Desk.md (S-R1), DeskIdea.md (S-R2, C-LISTEN, C-WORTH, C-PREVIEW, C-SHEET-MERGE), Status.md and
 * Inbox.md (what the sharer reads). BLD-E008: the boards' she/her for the sharer reads as the sharer's first name.
 * Cast: Kavya (sharer) is the record's sharer, Meera (reviewer) the record's reviewer, Ravi the other idea's sharer.
 * Seed: J-REVIEW changes only its own records (lib SEED); R1 is J-SIMILAR's and J-TEAMUP's and is never touched here.
 * P1 (Pallavi's, with the desk, never opened, one question Lavanya queued and never sent) walks the main path and is
 * picked. It fits "decide without asking" as L-REVIEW defines it: a queued question is the reviewer's alone, so P1 is
 * in To review with "No questions asked"; its panel is Asking, whose way on is "Decide without asking"
 * (asking → deciding), and the queued question is dropped when the decision is sent.
 * The ask path (A1 to A3) needs a record of its own at the same stage, and none is left: Z1's questions are sent and
 * B1's answered, and the boards take "Ask about this" and "Ask … first" away in both states (DeskIdea.md "Sent,
 * waiting", "Answered"). So A1 to A3 are GAP-SEED until lane E seeds P1's twin; their bodies are written for P1's
 * queued set and move to that record. Z1 (Zoya's, with Harish, questions overdue) is the clock (A4); B1 (Bhavesh's,
 * with Lavanya, both answered) has its answers read (A5). The merge previews Z1 from T6's page (T6 is J-TRACK's and
 * lists Z1 as similar; read only here). No two J-REVIEW ideas list each other as similar: GAP-SEED (M3).
 */
import { expect, type Browser, type Locator, type Page, type TestInfo } from "@playwright/test";

import { ideaUrl, seeded, signInAs, snap, step, type Person, type StepRef } from "./lib";

// --- Patterns for run-time parts of the copy ----------------------------------------------------------------------------

const DAY = String.raw`[A-Z][a-z]+day \d{1,2} [A-Z][a-z]+`; // "Wednesday 16 December"
const DAY_Y = String.raw`${DAY}(?: \d{4})?`; // "Tuesday 16 February 2027"
const TIME = String.raw`\d{1,2}(?::\d{2})? (?:am|pm)`; // "11:20 am", "6 pm"
const REF = String.raw`IDEA-\d{4}-\d{6}`;
const COUNTDOWN = String.raw`(?:\d+ days?|\d{2}:\d{2})`; // "3 days", "07:38"

/** The reason Lavanya gives when she picks P1 (J-REVIEW/6); Pallavi reads it word for word (J-REVIEW/6, /7). */
const REASON =
  "Distributors re-send these papers because the check list is kept in two places. One list fixes it.";
const WORTH_NOTE =
  "Every distributor desk re-checks these papers, so I counted the hours across all of them.";
const WORTH_HOURS = "40 to 60";

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** S-R2 for an idea (P-ROUTES.screens: `/desk/ideas/:id`, the reference once shared). */
function deskUrl(idea: { ref: string | null; uuid: string }): string {
  return `/desk/ideas/${idea.ref ?? idea.uuid}`;
}

function rowFor(page: Page, title: string): Locator {
  return page.getByRole("row", { name: new RegExp(esc(title)) });
}

/** A control the board draws as a link and a lane may build as a button (or the other way round). */
function action(scope: Page | Locator, name: string): Locator {
  return scope.getByRole("button", { name, exact: true }).or(scope.getByRole("link", { name, exact: true }));
}

/** "Ask about How often" on the board; "Ask about this" inside the part's own region is the same control. */
function askAbout(page: Page, part: string): Locator {
  return page
    .getByRole("button", { name: `Ask about ${part}`, exact: true })
    .or(page.getByRole("region", { name: part, exact: true }).getByRole("button", { name: /^Ask/ }));
}

/** The text of `loc` once it matches `re`: its first group, or the whole match when `re` has no group. */
async function capture(loc: Locator, re: RegExp): Promise<string> {
  await expect(loc).toHaveText(re);
  const m = (await loc.innerText()).replace(/\s+/g, " ").trim().match(re);
  if (!m) throw new Error(`no match for ${re}`);
  return m[1] ?? m[0];
}

async function openDesk(page: Page, who: Person, tab: RegExp): Promise<void> {
  await signInAs(page, who);
  await page.goto("/desk");
  await expect(page.getByRole("heading", { level: 1, name: "Review desk" })).toBeVisible();
  await page.getByRole("tab", { name: tab }).click();
  await expect(page.getByRole("tab", { name: tab, selected: true })).toBeVisible();
}

/** The other person in a step (the sharer reading what the reviewer sent), in a context of their own. */
async function asOther(
  browser: Browser,
  info: TestInfo,
  who: Person,
  at: { ref: StepRef; screen: string },
  fn: (page: Page) => Promise<void>,
): Promise<void> {
  const context = await browser.newContext();
  const other = await context.newPage();
  try {
    await signInAs(other, who);
    await fn(other);
  } finally {
    await snap(other, info, at.ref, at.screen, who);
    await context.close();
  }
}

// --- J-REVIEW.main: decide without asking (P1, Lavanya; Pallavi shared it) ---------------------------------------------

/** The panel's way into Deciding: "Decide on this idea", or "Decide without asking" while P1's question is queued. */
function decideButton(page: Page): Locator {
  return page.getByRole("button", { name: /^(?:Decide on this idea|Decide without asking)$/ }).first();
}

step(
  "J-REVIEW/1",
  "S-R1",
  "To review lists the idea with its clock; Open lands on the idea and the sharer's edit window is closed",
  { needs: ["S-R1", "S-R2", "L-REVIEW", "C-TABS", "C-SORTS", "S-06", "L-SUBMIT"], changes: ["P1"] },
  async ({ page, browser }, info) => {
    const p1 = await seeded("P1");
    await openDesk(page, "lavanya", /^To review/);
    await expect(page.getByRole("button", { name: "Time left" })).toHaveAttribute("aria-pressed", "true");
    const row = rowFor(page, p1.title);
    await expect(row).toContainText("Pallavi Joshi, Distributor services, Mumbai");
    // Lavanya's queued question is hers alone until sent, so nothing has been asked (L-REVIEW.queue, L-QUESTIONS).
    await expect(row).toContainText("No questions asked");
    await expect(row).toContainText(new RegExp(`${COUNTDOWN} to decide|Overdue by`));
    await expect(row).toContainText(new RegExp(DAY));

    await action(row, `Open: ${p1.title}`).click();
    await page.waitForURL(new RegExp(`${esc(deskUrl(p1))}$`));
    await expect(page.getByRole("heading", { level: 1, name: p1.title })).toBeVisible();
    // The row's sharer line carries into the heading block (S-R2.layout/2); BLD-E008 for the board's "by her".
    await expect(
      page
        .getByText(
          new RegExp(
            `^Shared ${DAY} by Pallavi Joshi, Distributor services, Mumbai\\. Sorting confirmed by (?:Pallavi|them): a problem to fix, Distributor services, saves time\\.$`,
          ),
        )
        .first(),
    ).toBeVisible();

    // L-REVIEW.open/1: P1 was never opened; now it is, the sharer's page is closed to edits and points to the conversation.
    await asOther(browser, info, "pallavi", { ref: "J-REVIEW/1", screen: "S-06" }, async (sharer) => {
      await sharer.goto(ideaUrl(p1));
      await expect(
        sharer
          .getByText(
            new RegExp(
              `^The review desk opened it on ${DAY}, so the idea itself can’t be changed now\\. Write to them in the conversation\\.$`,
            ),
          )
          .first(),
      ).toBeVisible();
      await expect(sharer.getByRole("button", { name: "Withdraw" })).toHaveCount(0);
    });
  },
);

step(
  "J-REVIEW/2",
  "S-R2",
  "Reads the idea: listen, the sharer's own words, each part as shared",
  { needs: ["S-R2", "C-LISTEN", "L-LISTEN", "L-REVIEW"] },
  async ({ page }) => {
    const p1 = await seeded("P1");
    await signInAs(page, "lavanya");
    await page.goto(deskUrl(p1));
    await expect(page.getByText("Listen to the whole idea").first()).toBeVisible();
    await expect(page.getByRole("button", { name: /^Play the whole idea, / })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Attachments and artefacts" })).toBeVisible();
    await expect(page.getByText("Everything that came with the idea").first()).toBeVisible();

    // "Her own words" (BLD-E008): the sharer's words as written, before the draft.
    await expect(page.getByText(/^(?:Pallavi’s|Their) own words$/)).toBeVisible();
    await expect(
      page.getByText(/^As (?:Pallavi|they) wrote them on [A-Z][a-z]+, before the draft\./).first(),
    ).toBeVisible();
    await action(page, "Read").click();
    await expect(
      page.getByText("Distributors send the same empanelment papers two or three times."),
    ).toBeVisible();

    // The parts carry what the sharer gave; the way on is the panel.
    for (const part of ["The problem", "How often", "Who it affects", "What it’s worth", "Attached", "Fix"]) {
      await expect(page.getByRole("heading", { name: part, exact: true })).toBeVisible();
    }
    await expect(
      page
        .getByText(
          "Distributors are asked for empanelment papers they already sent, because the check list is kept in two places.",
        )
        .first(),
    ).toBeVisible();
    await expect(decideButton(page)).toBeVisible();
  },
);

step(
  "J-REVIEW/3",
  "S-R2",
  "Revise what it's worth: the reviewer's figures and note reach the sharer's Inbox and page",
  {
    needs: ["S-R2", "C-WORTH", "L-WORTH", "S-H5", "C-INBOX-READER", "L-INBOX", "S-06"],
    changes: ["P1"],
  },
  async ({ page, browser }, info) => {
    const p1 = await seeded("P1");
    await signInAs(page, "lavanya");
    await page.goto(deskUrl(p1));
    await page.getByRole("button", { name: /^(Revise|Change) what it’s worth$/ }).click();
    await expect(page.getByText("Pallavi sees what you changed, with your note.")).toBeVisible();
    await page.getByRole("textbox", { name: /hours a month/i }).fill(WORTH_HOURS);
    await page.getByRole("textbox", { name: /^Note/ }).fill(WORTH_NOTE);
    await page.getByRole("button", { name: "Save", exact: true }).click();

    // The board's "She sees your figures next to hers." (BLD-E008): "theirs", or the name where a lane kept it.
    await expect(
      page.getByText(
        /^You’ve revised what it’s worth\. Pallavi sees your figures next to (?:theirs|Pallavi’s) when you decide\.$/,
      ),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Change what it’s worth" })).toBeVisible();
    await expect(page.getByText(`${WORTH_HOURS} hours a month`).first()).toBeVisible();

    // L-WORTH/3–4: the sharer is told at once, and sees both figures with the note.
    await asOther(browser, info, "pallavi", { ref: "J-REVIEW/3", screen: "S-H5" }, async (sharer) => {
      await sharer.goto("/inbox");
      await sharer
        .getByRole("button", {
          name: new RegExp(
            `^Lavanya( from the review desk)? revised what your idea is worth, ${esc(p1.title)}`,
          ),
        })
        .click();
      await sharer.goto(ideaUrl(p1));
      await expect(sharer.getByText(`${WORTH_HOURS} hours a month`).first()).toBeVisible();
      await expect(sharer.getByText(WORTH_NOTE).first()).toBeVisible();
    });
  },
);

step(
  "J-REVIEW/4",
  "S-R2",
  "Similar ideas: each with its sharer and why it matches; Preview opens it in place; Merge is the way on",
  { needs: ["S-R2", "C-PREVIEW", "L-MERGE"] },
  async ({ page }) => {
    // T6 lists Z1 as similar (club_seed similar_links); both read only here.
    const t6 = await seeded("T6");
    const z1 = await seeded("Z1");
    await signInAs(page, "harish");
    await page.goto(deskUrl(t6));
    await expect(page.getByRole("heading", { level: 2, name: "Similar ideas" })).toBeVisible();
    await expect(
      page.getByText("The same problem, raised by others. Merge them so one team builds one fix.").first(),
    ).toBeVisible();
    await expect(
      page
        .getByText(new RegExp(`^${esc(z1.ref ?? "")}, Zoya Mirza, Sales, Mumbai\\. \\d+ on its crew$`))
        .first(),
    ).toBeVisible();
    await expect(page.getByText("Related: distributors waiting on us").first()).toBeVisible();

    await page.getByRole("button", { name: `Preview ${z1.title}` }).click();
    const preview = page.getByRole("dialog");
    await expect(preview).toContainText(z1.title);
    await preview.getByRole("button", { name: "Close the preview" }).click();
    await expect(preview).toBeHidden();
    await expect(page.getByRole("button", { name: `Merge with ${z1.title}` })).toBeEnabled();
  },
);

/** The board's "She sees your figures next to hers." after BLD-E008: "theirs", or the name where a lane kept it. */
const NEXT_TO_THEIRS = String.raw`Pallavi sees your figures next to (?:theirs|Pallavi’s)`;

step(
  "J-REVIEW/5",
  "S-R2",
  "Decide turns the panel to Deciding: three choices, the committee's window, Send; Back returns",
  { needs: ["S-R2", "L-REVIEW", "L-DECIDE"] },
  async ({ page }) => {
    const p1 = await seeded("P1");
    await signInAs(page, "lavanya");
    await page.goto(deskUrl(p1));
    await expect(page.getByRole("heading", { name: "Review this idea" })).toBeVisible();
    // After J-REVIEW/3 the line says what was revised; the board's line otherwise.
    await expect(
      page
        .getByText(
          new RegExp(
            `^(?:Clear enough\\? Decide now\\. If it’s worth more than Pallavi could put into numbers, revise what it’s worth first\\. ${NEXT_TO_THEIRS}\\.|You’ve revised what it’s worth\\. ${NEXT_TO_THEIRS} when you decide\\.)$`,
          ),
        )
        .first(),
    ).toBeVisible();
    // S-R2.panel.ask: collapsed by default, even with Lavanya's question queued.
    await expect(page.getByRole("button", { name: /^Ask Pallavi first/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );

    // With a question queued the panel is Asking, so the way on reads "Decide without asking" (L-REVIEW.panel).
    await decideButton(page).click();
    await expect(page.getByRole("heading", { name: "Decide on this idea" })).toBeVisible();
    await expect(
      page.getByText("Pallavi reads your decision and your reason as soon as you send it."),
    ).toBeVisible();
    await expect(
      page.getByRole("radio", { name: /^Pick\s*Take it forward\. A build team is chosen next\.$/ }),
    ).toBeVisible();
    await expect(
      page.getByRole("radio", {
        name: /^Not now\s*Right problem, wrong time\. It comes back on a date you set\.$/,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("radio", {
        name: /^Not picked\s*It won’t go ahead\. Say what happens to Pallavi’s words\.$/,
      }),
    ).toBeVisible();
    await expect(
      page
        .getByText(
          new RegExp(
            `^The Ones Committee can review it for 30 days\\. Until ${DAY_Y} they can reverse it, with a note that goes to Pallavi\\. After that, it stands\\.$`,
          ),
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Send decision to Pallavi" })).toBeVisible();
    // Back with nothing sent returns to where Lavanya came from (L-REVIEW.panel), the queued question kept.
    await page.getByRole("button", { name: "Back", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Review this idea" })).toBeVisible();
    await expect(decideButton(page)).toBeVisible();
  },
);

step(
  "J-REVIEW/6",
  "S-R2",
  "Pick with a reason and Send decision to Pallavi: Pallavi reads it at once, with the committee's date",
  { needs: ["S-R2", "L-DECIDE", "L-COMMITTEE", "S-06"], changes: ["P1"] },
  async ({ page, browser }, info) => {
    const p1 = await seeded("P1");
    await signInAs(page, "lavanya");
    await page.goto(deskUrl(p1));
    await decideButton(page).click();
    await page.getByRole("radio", { name: /^Pick/ }).click();
    await page.getByRole("textbox", { name: "Why are you picking it?" }).fill(REASON);
    await expect(page.getByText("Pallavi reads this word for word.")).toBeVisible();
    const until = await capture(
      page.getByText(/^The Ones Committee can review it for 30 days\./).first(),
      new RegExp(`Until (${DAY_Y}) they can reverse it`),
    );
    await page.getByRole("button", { name: "Send decision to Pallavi" }).click();
    await expect(page.getByRole("heading", { name: "Decision sent to Pallavi" })).toBeVisible();

    // L-DECIDE.rules/3, /5: the reason word for word, at once, in the app; the window's date as the reviewer saw it.
    await asOther(browser, info, "pallavi", { ref: "J-REVIEW/6", screen: "S-06" }, async (sharer) => {
      await sharer.goto(ideaUrl(p1));
      await expect(sharer.getByText("Picked. A team is being chosen to build it.").first()).toBeVisible();
      await expect(
        sharer.getByText(new RegExp(`^Lavanya from the review desk picked it on ${DAY}\\b.*\\.$`)).first(),
      ).toBeVisible();
      await expect(sharer.getByText(REASON).first()).toBeVisible();
      await expect(
        sharer
          .getByText(
            `The Ones Committee can review this decision until ${until}. If they change it, their note comes to your Inbox. After that, it stands.`,
          )
          .first(),
      ).toBeVisible();
      await expect(sharer.getByRole("button", { name: "Ask to join the build team" })).toBeVisible();
    });
  },
);

step(
  "J-REVIEW/7",
  "S-R2",
  "Decision sent to Pallavi with the committee's window; the idea is under Decided this week with the same date",
  { needs: ["S-R2", "S-R1", "L-DECIDE", "L-COMMITTEE", "L-REVIEW"] },
  async ({ page }) => {
    const p1 = await seeded("P1");
    await signInAs(page, "lavanya");
    await page.goto(deskUrl(p1));
    await expect(page.getByRole("heading", { name: "Decision sent to Pallavi" })).toBeVisible();
    await expect(
      page.getByText(new RegExp(`^Today, ${TIME}\\. Pallavi has it now\\.$`)).first(),
    ).toBeVisible();
    await expect(page.getByText("Your reason, as Pallavi reads it").first()).toBeVisible();
    await expect(page.getByText(REASON).first()).toBeVisible();
    await expect(page.getByText("Open, 30 days left").first()).toBeVisible();
    const until = await capture(
      page.getByText(/^Open until /).first(),
      new RegExp(
        `^Open until (${DAY_Y})\\. The committee can extend it, up to 3 months in all, to ${DAY_Y}\\. If they reverse it, Pallavi gets their note and you see it here\\. When the window closes, the decision stands\\.$`,
      ),
    );

    // L-REVIEW.queue: the decided idea and its window, on the desk.
    await page.goto("/desk");
    await page.getByRole("tab", { name: /^Decided this week/ }).click();
    const row = rowFor(page, p1.title);
    await expect(row).toContainText(/Picked, \d{1,2} [A-Z][a-z]+/);
    await expect(row).toContainText(`Ones Committee can review it until ${until}`);
  },
);

// --- J-REVIEW.ask: ask first (A1–A3 wait for a record of their own; Z1 for the clock; B1 for answers) ---------------

/** P1 walks the main path, so the ask path's first three rows wait for one like it (see the header). */
const ASK_GAP =
  "an idea of J-REVIEW's own at To review with nothing sent, like P1 (unopened, a question Lavanya queued): P1 walks " +
  "the main path now that R1 is J-SIMILAR's and J-TEAMUP's, Z1's questions are sent and B1's answered";

step(
  "J-REVIEW/A1",
  "S-R2",
  "Ask about this on a part opens Ask Pallavi first with that part's suggestion queued",
  { needs: ["S-R2", "L-QUESTIONS", "L-REVIEW"], changes: ["P1"], gapSeed: ASK_GAP },
  async ({ page }) => {
    const p1 = await seeded("P1");
    await signInAs(page, "lavanya");
    await page.goto(deskUrl(p1));
    await expect(page.getByRole("heading", { level: 1, name: p1.title })).toBeVisible();
    const askFirst = page.getByRole("button", { name: /^Ask Pallavi first/ });
    await askAbout(page, "How often").click();
    await expect(askFirst).toHaveAttribute("aria-expanded", "true");
    await expect(askAbout(page, "How often")).toHaveAttribute("aria-pressed", "true");
    await expect(
      page.getByText(
        "Only if something is unclear. Ask in your own words; each question is pinned to its part of the idea, so Pallavi answers it right there.",
      ),
    ).toBeVisible();
    // The question Lavanya queued before (seed) is still there, and How often's suggestion joined it (S-R2.rules/2):
    // at least those two, whatever else a lane queues with them; the header counts what is listed.
    await expect(
      page.getByRole("button", { name: "Remove: Which distributor segments re-send most?" }),
    ).toBeVisible();
    const removes = page.getByRole("button", { name: /^Remove: / });
    await expect.poll(() => removes.count()).toBeGreaterThanOrEqual(2);
    await expect(askFirst).toContainText(`${await removes.count()} questions ready`);
    await expect(page.getByRole("button", { name: "Decide without asking" })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Send \d+ questions? to Pallavi$/ })).toBeVisible();
  },
);

async function openAsk(page: Page): Promise<Locator> {
  const askFirst = page.getByRole("button", { name: /^Ask Pallavi first/ });
  if ((await askFirst.getAttribute("aria-expanded")) !== "true") await askFirst.click();
  await expect(askFirst).toHaveAttribute("aria-expanded", "true");
  return askFirst;
}

function questionBox(page: Page): Locator {
  return page.getByRole("textbox", {
    name: /^(What would you like to ask Pallavi\?|Your question for Pallavi)$/,
  });
}

/** Types a question in the reviewer's own words and adds it ("Add this question", S-R2.panel.ask). */
async function addQuestion(page: Page, text: string): Promise<void> {
  await questionBox(page).fill(text);
  await page.getByRole("button", { name: "Add this question" }).click();
  await expect(page.getByRole("button", { name: `Remove: ${text}` })).toBeVisible();
}

step(
  "J-REVIEW/A2",
  "S-R2",
  "Questions in the reviewer's own words, a suggestion added, the time to answer and its deadline before sending",
  { needs: ["S-R2", "L-QUESTIONS"], changes: ["P1"], gapSeed: ASK_GAP },
  async ({ page }) => {
    const p1 = await seeded("P1");
    const typed = "Which teams keep a second copy of the papers today?";
    await signInAs(page, "lavanya");
    await page.goto(deskUrl(p1));
    const askFirst = await openAsk(page);
    await addQuestion(page, typed);
    const removes = page.getByRole("button", { name: /^Remove: / });
    const before = await removes.count();
    await page
      .getByRole("button", { name: /^Add: / })
      .first()
      .click();
    await expect(removes).toHaveCount(before + 1);
    const n = before + 1;
    await expect(askFirst).toContainText(`${n} questions ready`);

    // L-QUESTIONS.ask/4: 3 days by default; the deadline follows the choice and shows before sending.
    await expect(page.getByRole("radio", { name: "3 days" })).toBeChecked();
    const deadline = page.getByText(/^Pallavi has until /).first();
    const threeDays = await capture(deadline, new RegExp(`^Pallavi has until (${DAY}, ${TIME})\\.`));
    await page.getByRole("radio", { name: "1 week" }).click();
    await expect(deadline).not.toContainText(threeDays);
    await page.getByRole("radio", { name: "3 days" }).click();
    await expect(deadline).toContainText(threeDays);
    await expect(page.getByRole("button", { name: `Send ${n} questions to Pallavi` })).toBeVisible();
  },
);

step(
  "J-REVIEW/A3",
  "S-R2",
  "Send the questions: Waiting on Pallavi, the desk row moves, and Pallavi's Inbox has the same deadline",
  {
    needs: ["S-R2", "S-R1", "L-QUESTIONS", "S-H5", "C-INBOX-READER", "C-QCARD", "L-INBOX"],
    changes: ["P1"],
    gapSeed: ASK_GAP,
  },
  async ({ page, browser }, info) => {
    const p1 = await seeded("P1");
    await signInAs(page, "lavanya");
    await page.goto(deskUrl(p1));
    await openAsk(page);
    await addQuestion(page, "Roughly how many papers come in twice each month?");
    await page.getByRole("radio", { name: "3 days" }).click();
    const deadline = await capture(
      page.getByText(/^Pallavi has until /).first(),
      new RegExp(`^Pallavi has until (${DAY}, ${TIME})\\.`),
    );
    const send = page.getByRole("button", { name: /^Send \d+ questions? to Pallavi$/ });
    const n = Number((await send.innerText()).match(/\d+/)?.[0]);
    await send.click();

    await expect(page.getByRole("heading", { name: "Waiting on Pallavi" })).toBeVisible();
    await expect(page.getByText(new RegExp(`^${COUNTDOWN} to answer$`)).first()).toBeVisible();
    await expect(page.getByText(new RegExp(`^Sent today, ${TIME}\\.`)).first()).toBeVisible();

    await page.goto("/desk");
    await page.getByRole("tab", { name: /^Waiting on the sharer/ }).click();
    const row = rowFor(page, p1.title);
    await expect(row).toContainText("Pallavi Joshi, Distributor services, Mumbai");
    await expect(row).toContainText(new RegExp(`Not seen yet|0 of ${n} answered`));
    await expect(row).toContainText(new RegExp(`${COUNTDOWN} to answer`));

    // L-QUESTIONS.ask/5: the sharer is told; the deadline is the one the reviewer saw before sending.
    await asOther(browser, info, "pallavi", { ref: "J-REVIEW/A3", screen: "S-H5" }, async (sharer) => {
      await sharer.goto("/inbox");
      await sharer.getByRole("tab", { name: /^Needs you/ }).click();
      await sharer
        .getByRole("button", {
          name: new RegExp(`^Lavanya from the review desk asked you ${n} questions?, ${esc(p1.title)}`),
        })
        .click();
      await expect(sharer.getByText(`Answer by ${deadline}.`).first()).toBeVisible();
      await expect(action(sharer, "Answer the questions").first()).toBeVisible();
    });
  },
);

step(
  "J-REVIEW/A4",
  "S-R1",
  "The clock: overdue on the desk and on the idea; Remind Zoya, then Give 2 more days",
  { needs: ["S-R1", "S-R2", "L-QUESTIONS", "L-REVIEW"], changes: ["Z1"] },
  async ({ page }) => {
    const z1 = await seeded("Z1");
    await openDesk(page, "harish", /^Waiting on the sharer/);
    const row = rowFor(page, z1.title);
    await expect(row).toContainText("Zoya Mirza, Sales, Mumbai");
    await expect(row).toContainText("Not seen yet");
    const overdue = await capture(
      row.getByText(/^Overdue by /).first(),
      /^Overdue by \d+ (?:minutes?|hours?|days?)$/,
    );
    await action(row, `Remind Zoya: ${z1.title}`).click();
    await expect(row).toContainText("Reminded, just now");

    // The idea's panel runs the same clock (L-QUESTIONS.clock/1, /3).
    await page.goto(deskUrl(z1));
    await expect(page.getByRole("heading", { name: "Waiting on Zoya" })).toBeVisible();
    await expect(page.getByText(overdue).first()).toBeVisible();
    await expect(page.getByText("Not answered yet").first()).toBeVisible();
    await page.getByRole("button", { name: "Give 2 more days" }).click();
    await expect(page.getByText(new RegExp(`^${COUNTDOWN} to answer$`)).first()).toBeVisible();
    // The desk's reminder was sent above; the panel offers it again or says it went (S-R1.rules/3, NOT DRAWN).
    await expect(page.getByRole("button", { name: /^(Send a reminder|Reminded, just now)$/ })).toBeVisible();
  },
);

step(
  "J-REVIEW/A5",
  "S-R2",
  "Answers back: Read answers opens each answer under its part; Decide on this idea and Back return here",
  { needs: ["S-R1", "S-R2", "L-QUESTIONS", "L-REVIEW"] },
  async ({ page }) => {
    const b1 = await seeded("B1");
    await openDesk(page, "lavanya", /^Answered, back to you/);
    const row = rowFor(page, b1.title);
    await expect(row).toContainText("Bhavesh Patel, Operations, Jaipur");
    await expect(row).toContainText(/Both answered/);
    await action(row, `Read answers: ${b1.title}`).click();
    await page.waitForURL(new RegExp(`${esc(deskUrl(b1))}$`));

    // L-QUESTIONS.answer/5: each answer under its part, with who and when.
    await expect(page.getByText("Around 60 a week.").first()).toBeVisible();
    await expect(page.getByText("Yes, one scan and a search box.").first()).toBeVisible();
    await expect(page.getByText(/^Bhavesh answered, /)).toHaveCount(2);
    const answered = page.getByRole("heading", { name: /^(All 2|Both) answered$/ });
    await expect(answered).toBeVisible();
    await expect(page.getByText(new RegExp(`^Decide by ${DAY}\\.$`)).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Ask a follow-up" })).toBeVisible();
    await page.getByRole("button", { name: "Decide on this idea" }).click();
    await expect(page.getByRole("heading", { name: "Decide on this idea" })).toBeVisible();
    await page.getByRole("button", { name: "Back", exact: true }).click();
    await expect(answered).toBeVisible();
  },
);

// --- J-REVIEW.merge: preview and merge (T6's page lists Z1; read only). The merge itself waits on the seed ------------

async function previewZ1(
  page: Page,
): Promise<{ preview: Locator; t6: string; z1Ref: string; z1Title: string }> {
  const t6 = await seeded("T6");
  const z1 = await seeded("Z1");
  await signInAs(page, "harish");
  await page.goto(deskUrl(t6));
  await page.getByRole("button", { name: `Preview ${z1.title}` }).click();
  const preview = page.getByRole("dialog");
  await expect(preview).toContainText(z1.title);
  return { preview, t6: t6.ref ?? "", z1Ref: z1.ref ?? "", z1Title: z1.title };
}

step(
  "J-REVIEW/M1",
  "S-R2",
  "Preview a similar idea next to the one under review, with Merge as its one button",
  { needs: ["S-R2", "C-PREVIEW"] },
  async ({ page }) => {
    const { preview, z1Ref } = await previewZ1(page);
    await expect(preview).toContainText(z1Ref);
    await expect(preview).toContainText("Related: distributors waiting on us");
    await expect(preview).toContainText("The problem, in their words");
    // The reviewer's view compares with the idea under review: T6's How often sits next to Z1's.
    await expect(preview).toContainText("Next to Tanvi’s");
    await expect(preview).toContainText("About 30 folios a week");
    await expect(preview).toContainText(/Zoya Mirza leads it, \d+ on its crew/);
    await expect(preview.getByRole("button", { name: "Merge", exact: true })).toBeVisible();
    await expect(preview.getByRole("button", { name: "Team up", exact: true })).toHaveCount(0);
  },
);

step(
  "J-REVIEW/M2",
  "S-R2",
  "Merge opens the sheet for the same idea: the earlier one leads, Team them up ticked, a note to both",
  { needs: ["S-R2", "C-PREVIEW", "C-SHEET-MERGE", "L-MERGE"] },
  async ({ page }) => {
    const { preview, t6, z1Ref } = await previewZ1(page);
    await preview.getByRole("button", { name: "Merge", exact: true }).click();
    // Z1 was shared before T6, so Zoya's leads by default (L-MERGE.desk/2).
    const sheet = page.getByRole("dialog", { name: `Merge with ${z1Ref}?` });
    await expect(sheet).toBeVisible();
    await expect(sheet).toContainText(
      "Tanvi’s idea joins Zoya’s. Both stay credited, and from now on the review desk decides on one idea.",
    );
    await expect(
      sheet.getByRole("radio", { name: new RegExp(`^Zoya’s leads, ${esc(z1Ref)}`) }),
    ).toBeChecked();
    await expect(
      sheet.getByRole("radio", { name: new RegExp(`^Tanvi’s leads, ${esc(t6)}`) }),
    ).not.toBeChecked();
    await expect(sheet.getByRole("checkbox", { name: /Team them up/ })).toBeChecked();
    await expect(sheet).toContainText("Tanvi joins Zoya’s crew without a request. Both are told why.");
    await expect(sheet).toContainText(
      "Both get it in their Inbox. The Ones Committee sees the merge for 30 days and can reverse it.",
    );
    await expect(sheet.getByRole("button", { name: "Merge and tell both" })).toBeEnabled();
    await sheet.getByRole("button", { name: "Close without merging" }).click();
    await expect(sheet).toBeHidden();
  },
);

step(
  "J-REVIEW/M3",
  "S-R2",
  "Merge and tell both: one idea survives, the banner says so, and the merged sharer's page points to it",
  {
    needs: ["S-R2", "C-SHEET-MERGE", "L-MERGE", "L-COMMITTEE", "S-06"],
    changes: ["B1"],
    gapSeed:
      "two J-REVIEW ideas on the desk that list each other as similar (a similar_links row from B1 to Z1 would do; " +
      "P1 is picked by then), so a desk merge changes only J-REVIEW records; today T6 lists Z1, and T6 is J-TRACK's",
  },
  async ({ page, browser }, info) => {
    const b1 = await seeded("B1");
    await signInAs(page, "lavanya");
    await page.goto(deskUrl(b1));
    await page
      .getByRole("button", { name: /^Merge with / })
      .first()
      .click();
    const sheet = page.getByRole("dialog", { name: new RegExp(`^Merge with ${REF}\\?$`) });
    await sheet
      .getByRole("textbox")
      .fill("You both see papers handled twice at the counter. One team, one fix.");
    await sheet.getByRole("button", { name: "Merge and tell both" }).click();
    await expect(
      page
        .getByText(
          new RegExp(
            `^Merged: [A-Z][a-z]+’s idea is now part of ${REF}, and both are credited\\. [A-Z][a-z]+ is on [A-Z][a-z]+’s crew\\. Both were told in their Inbox\\. The Ones Committee can reverse it within 30 days\\.$`,
          ),
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByText("Merged", { exact: true }).first()).toBeVisible();
    await asOther(browser, info, "bhavesh", { ref: "J-REVIEW/M3", screen: "S-06" }, async (sharer) => {
      await sharer.goto(ideaUrl(b1));
      await expect(
        sharer.getByText(/^Merged into IDEA-\d{4}-\d{6} by the review desk/).first(),
      ).toBeVisible();
    });
  },
);
