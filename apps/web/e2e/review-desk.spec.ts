/**
 * The review side in the browser (J-REVIEW, J-COMMITTEE, J-TRACK answer): V-ACC.review, V-ACC.committee and the
 * sharer's Answer screen. Ideas are written straight into this run's database for the seeded sharer, because the
 * share journey is another lane's; everything after that goes through the screens. Synthetic data only.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Browser, type Page } from "@playwright/test";
import { Client } from "pg";

import {
  expectNoSeriousAxeIssues,
  expectNoSidewaysScroll,
  navLabels,
  PERSONAS,
  PHONE_TABS,
  signIn,
} from "./helpers";
import { carrying, storageCarries, storageNames, watchRequestUrls } from "./search-words";

const DATABASE_URL =
  process.env.E2E_DATABASE_URL || "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable";
const REASON = "A clear problem, a real number and a simple fix for the branch team.";
/** Core committee personas no other spec signs in as, one per project since both run at once: each holds the
 * committee role for this spec only. */
const COMMITTEE_MEMBER: Record<string, string> = { desktop: "SYN-00010", "phone-360": "SYN-00009" };
const NOTE = "The SMS vendor changes in March; this goes with that work, not before.";

async function db<T>(fn: (c: Client) => Promise<T>): Promise<T> {
  const c = new Client({ connectionString: DATABASE_URL });
  await c.connect();
  try {
    return await fn(c);
  } finally {
    await c.end();
  }
}

/** Sign a persona in and return their user id and contributor code (one is made if they have none yet). */
async function person(browser: Browser, persona: string): Promise<{ page: Page; id: string; code: string }> {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await signIn(page, persona);
  const me = (await (await page.request.get("/api/me")).json()) as { email: string };
  const { id, code } = await db(async (c) => {
    const u = await c.query<{ id: string }>("SELECT id FROM users WHERE email = $1", [me.email]);
    const userId = u.rows[0]!.id;
    await c.query(
      "INSERT INTO contributor_map (contributor_code, user_id) VALUES ('CTR-' || substr(md5(random()::text), 1, 6), $1) " +
        "ON CONFLICT (user_id) DO NOTHING",
      [userId],
    );
    const m = await c.query<{ contributor_code: string }>(
      "SELECT contributor_code FROM contributor_map WHERE user_id = $1",
      [userId],
    );
    return { id: userId, code: m.rows[0]!.contributor_code };
  });
  return { page, id, code };
}

/** A shared idea on the desk for `code`, with its sharer as crew lead. */
async function sharedIdea(
  code: string,
  title: string,
  summary = "Investors call the branch because the rejection SMS gives a code, not a reason.",
): Promise<string> {
  return db(async (c) => {
    const r = await c.query<{ idea_id: string; id: string }>(
      "INSERT INTO ideas (idea_id, contributor_code, status, title, summary, often, affects, area, city, kind, " +
        "shared_at, decide_by, edit_closes_at) VALUES (next_idea_ref(), $1, 'with_review_desk', $2, $3, " +
        "'About 40 calls a day at one branch.', ARRAY['Investors'], 'Investor service', 'Hyderabad', 'problem', " +
        "now(), now() + interval '5 days', now() + interval '3 days') RETURNING idea_id, id",
      [code, title, summary],
    );
    await c.query(
      "INSERT INTO crew_members (idea_uuid, contributor_code, role, via) VALUES ($1, $2, 'lead', 'shared')",
      [r.rows[0]!.id, code],
    );
    return r.rows[0]!.idea_id;
  });
}

test("V-ACC.review/1, /4–6, /9 and V-ACC.committee/1–2, /4: from the desk to a decision to the committee", async ({
  browser,
}, testInfo) => {
  test.setTimeout(120_000);
  const sharer = await person(browser, PERSONAS.contributor);
  const reviewer = await person(browser, PERSONAS.reviewer);
  const title = `Rejection SMS codes need plain words (${testInfo.project.name} ${Date.now()})`;
  const ideaId = await sharedIdea(sharer.code, title);
  const r = reviewer.page;

  // S-R1: the idea is on the desk under To review
  await r.goto("/desk?tab=to_review");
  await expect(r.getByRole("heading", { level: 1, name: "Review desk" })).toBeVisible();
  await expect(r.getByRole("link", { name: title, exact: true })).toBeVisible();
  await expectNoSeriousAxeIssues(r);
  await expectNoSidewaysScroll(r);

  // S-R2, V-ACC.review/1: the panel opens on Review this idea with one button; Ask is folded away
  await r.getByRole("link", { name: title, exact: true }).click();
  await r.waitForURL(new RegExp(`/desk/ideas/${ideaId}$`));
  await expect(r.getByRole("heading", { name: "Review this idea" })).toBeVisible();
  await expect(r.getByRole("button", { name: "Decide on this idea" })).toBeVisible();
  await expect(r.getByRole("button", { name: /Ask .* first/ })).toHaveAttribute("aria-expanded", "false");
  await expectNoSeriousAxeIssues(r);

  // V-ACC.review/6: Ask about this queues that part's suggestion and changes the bar
  const howOften = r.getByRole("region", { name: "How often" });
  await howOften.getByRole("button", { name: "Ask about this, How often" }).click();
  await expect(howOften.getByRole("button", { name: "Asking, How often" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(r.getByRole("button", { name: /^Ask .* first/ })).toContainText("1 question ready");
  await expect(r.getByRole("button", { name: /Send 1 question to / })).toBeVisible();
  await expect(r.getByRole("button", { name: "Decide without asking" })).toBeVisible();

  // V-ACC.review/5 and /9: Back returns; nothing is sent without a choice and a reason of a line
  await r.getByRole("button", { name: "Decide without asking" }).click();
  await expect(r.getByRole("heading", { name: "Decide on this idea" })).toBeVisible();
  await r.getByRole("button", { name: /Send decision to / }).click();
  await expect(r.getByText("Choose Pick, Not now or Not picked first.")).toBeVisible();
  await expect(r.getByRole("radio", { name: /^Pick/ })).toBeFocused(); // V-FIELDS/3
  await r.getByRole("radio", { name: /^Pick/ }).check();
  await r.getByRole("textbox", { name: "Why are you picking it?" }).fill("Too short");
  await r.getByRole("button", { name: /Send decision to / }).click();
  await expect(r.getByText(/a reason of at least a line, 30 characters or more/)).toBeVisible();
  await expect(r.getByRole("textbox", { name: "Why are you picking it?" })).toBeFocused();

  // L-DECIDE.rules/4 (BLD-B236): a word the product never says warns once, with a plainer way; nothing is sent
  const reason = r.getByRole("textbox", { name: "Why are you picking it?" });
  await reason.fill(`${REASON} It is a duplicate of nothing else we run.`);
  await r.getByRole("button", { name: /Send decision to / }).click();
  await expect(r.getByText(/The product never says “duplicate”/)).toBeVisible();
  await expect(r.getByRole("button", { name: "Send anyway" })).toBeVisible();

  // V-ACC.review/4: Pick with a reason; the sharer has it at once; a 30-day window is open
  await reason.fill(REASON);
  await expect(r.getByRole("button", { name: "Send anyway" })).toHaveCount(0);
  await r.getByRole("button", { name: /Send decision to / }).click();
  await expect(r.getByRole("heading", { name: /Decision sent to / })).toBeVisible();
  await expect(r.getByText(/^Today, .*has it now\.$/)).toBeVisible();
  await expect(r.getByText("Open, 30 days left")).toBeVisible();
  await expect(r.getByText(/^Open until .* When the window closes, the decision stands\.$/)).toBeVisible();
  await expectNoSeriousAxeIssues(r);
  // S-R1, Desk.md: Decided this week lists it, with "Open: {title}"
  await r.goto("/desk?tab=decided");
  await expect(r.getByRole("link", { name: `Open: ${title}` })).toHaveAttribute(
    "href",
    `/desk/ideas/${ideaId}`,
  );
  const sharerSees = (await (await sharer.page.request.get(`/api/ideas/${ideaId}/decision`)).json()) as {
    decision: { label: string; reason: string };
  };
  expect(sharerSees.decision).toMatchObject({ label: "Picked", reason: REASON });

  // S-R4, V-ACC.committee/1, /2, /4: listed with the reason; extend; reverse, final. The committee role is granted for
  // this spec and taken back after it (grants are read on every request).
  const member = await person(browser, COMMITTEE_MEMBER[testInfo.project.name] ?? "SYN-00010");
  await db((c) =>
    c.query(
      "INSERT INTO role_grants (user_id, role) SELECT $1, 'committee' WHERE NOT EXISTS (" +
        "SELECT 1 FROM role_grants WHERE user_id = $1 AND role = 'committee')",
      [member.id],
    ),
  );
  try {
    const m = member.page;
    await m.goto("/committee");
    await expect(m.getByRole("heading", { level: 1, name: "Ones Committee" })).toBeVisible();
    const row = m.getByRole("rowgroup").filter({ hasText: title });
    await expect(row.getByText(REASON)).toBeVisible();
    await expect(row.getByText("30 days left")).toBeVisible();
    await expectNoSeriousAxeIssues(m);
    await row.getByRole("button", { name: `Review the decision on ${title}` }).click();
    await row.getByRole("button", { name: /^Extend to / }).click();
    await expect(row.getByText(/Extended once/)).toBeVisible();
    await row.getByRole("button", { name: "Reverse the decision" }).click();
    const form = m.getByRole("dialog", { name: "Reverse the decision" });
    await expect(form).toBeVisible();
    await expectNoSeriousAxeIssues(m);
    await form.getByRole("radio", { name: /^Not picked/ }).check();
    await form
      .getByRole("textbox", {
        name: /^Your note to .*: why the committee is changing it, in words .* will understand$/,
      })
      .fill(NOTE);
    const sent = m.waitForResponse((r) => r.request().method() === "POST" && r.url().includes("/reverse"));
    await form.getByRole("button", { name: /Reverse and tell / }).click();
    const reply = await sent;
    expect(reply.status(), `reverse: ${await reply.text()}`).toBe(200);
    // the reversal is sent and the window tab reloaded without the row before moving to Reversed (S-R4.rules/3)
    await expect(form).toBeHidden();
    const listed = await m.request.get("/api/committee?tab=reversed&sort=closing");
    expect(listed.status(), "the committee's Reversed list").toBe(200);
    expect(JSON.stringify(await listed.json()), "the server lists it under Reversed").toContain(title);
    await expect(m.getByRole("rowgroup").filter({ hasText: title })).toHaveCount(0);
    await m.getByRole("tab", { name: /Reversed/ }).click();
    const reversed = m.getByRole("row", { name: new RegExp(title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) });
    await expect(reversed).toContainText(/Now: Not picked by .+, \w+day \d{1,2} \w+/);
    await expect(reversed).toContainText(/Reversed \w+day \d{1,2} \w+\. Final\. .+ has the note\./);
    await expect(reversed.getByRole("button", { name: `See it, the decision on ${title}` })).toBeVisible();
    const after = (await (await sharer.page.request.get(`/api/ideas/${ideaId}/decision`)).json()) as {
      reversal: { to: string; note: string };
    };
    expect(after.reversal).toMatchObject({ to: "not_picked", note: NOTE });
  } finally {
    await db((c) =>
      c.query("DELETE FROM role_grants WHERE user_id = $1 AND role = 'committee'", [member.id]),
    );
  }
});

test("S-R3: the sharer answers the desk's questions one at a time and sends (V-ACC.review/7–8)", async ({
  browser,
}, testInfo) => {
  test.setTimeout(120_000);
  const sharer = await person(browser, PERSONAS.contributor);
  const reviewer = await person(browser, PERSONAS.reviewer);
  const title = `Courier slips are signed twice (${testInfo.project.name} ${Date.now()})`;
  const ideaId = await sharedIdea(sharer.code, title);

  // V-ACC.review/7: the reviewer sends two questions with 3 days
  const sent = await reviewer.page.request.post(`/api/desk/ideas/${ideaId}/question-sets`, {
    data: {
      questions: [
        { part: "often", text: "Is it 40 calls a day at one branch, or across Hyderabad?" },
        { part: "evidence", text: "Can you add a screenshot of the SMS, with the folio hidden?" },
      ],
      time_to_answer: "3d",
    },
  });
  expect(sent.status()).toBe(201);
  await reviewer.page.goto("/desk?tab=waiting");
  const deskRow = reviewer.page.getByRole("row").filter({ hasText: title });
  await expect(deskRow.getByText(/0 of 2 answered|Not seen yet/)).toBeVisible();
  await expect(deskRow.getByText(/to answer$/)).toBeVisible();
  // S-R1.layout/4, S-R2.panel/3, C-PILL.rules/3: the desk row's clock and the waiting panel's are the board's
  // countdown (Desk .due, a clock in place of the dot)
  await expect(deskRow.locator(".due")).toHaveText(/to answer$/);
  await reviewer.page.goto(`/desk/ideas/${ideaId}`);
  await expect(reviewer.page.locator(".ri-clock .due")).toHaveText(/to answer$/);

  // J-TRACK/3 C-QCARD.places S-H5: the questions reach the sharer's Inbox as the card, under the reader's own
  // header, and the button in the reader's foot opens the Answer screen
  const s = sharer.page;
  await s.goto("/inbox?tab=needs_you");
  await s.getByRole("button", { name: `asked you 2 questions, ${title}` }).click();
  const reader = s.locator(".ibx-read");
  await expect(reader.locator(".qcard-inbox")).toBeVisible();
  await expect(reader.getByText("Is it 40 calls a day at one branch, or across Hyderabad?")).toBeVisible();
  await expect(reader.getByText(/^Answer by .+\.$/)).toHaveCount(1);
  await expect(reader.getByRole("link", { name: "Open the conversation" })).toHaveAttribute(
    "href",
    `/ideas/${ideaId}/conversation`,
  );
  await expectNoSeriousAxeIssues(s);
  await reader.getByRole("link", { name: "Answer the questions" }).click();

  // S-R3: one question at a time, skip, check and send
  await expect(s).toHaveURL(new RegExp(`/ideas/${ideaId}/answer$`));
  await expect(s.getByRole("heading", { name: "Answer the review desk" })).toBeVisible();
  // S-R3.layout/1, C-PILL.rules/3: the review bar's clock is the Answer board's countdown
  await expect(s.locator(".ans-due .due")).toHaveText(/left to answer$/);
  await expect(s.getByRole("button", { name: "Question 1, not answered yet" })).toBeVisible();
  await expectNoSeriousAxeIssues(s);
  await expectNoSidewaysScroll(s);
  // B3: the first save is dropped; the screen says so, tries again on its own, and the message clears once saved
  let dropped = false;
  await s.route("**/api/questions/*/answer", (route) => {
    if (dropped) return route.fallback();
    dropped = true;
    return route.abort();
  });
  await s.getByRole("textbox", { name: "Your answer to question 1" }).fill("Our Hyderabad branch alone.");
  await expect(s.getByText("Couldn’t save that. Try again.")).toBeVisible();
  await expect(s.getByText(/· Saved$/)).toBeVisible({ timeout: 15_000 });
  await expect(s.getByText("Couldn’t save that. Try again.")).toHaveCount(0);
  await s.unroute("**/api/questions/*/answer");
  await s.getByRole("button", { name: "Next" }).click();
  await expect(s.getByRole("button", { name: "Question 1, answered" })).toBeVisible();
  await s.getByRole("button", { name: "Skip for now" }).click();
  await expect(s.getByRole("heading", { name: "Check your answers" })).toBeVisible();
  await expect(s.getByText("Not answered. It stays open until the deadline.")).toBeVisible();
  await expect(s.getByRole("button", { name: "Change your answer to question 1" })).toBeVisible();
  await s.getByRole("button", { name: /Send 1 answer to / }).click();
  await expect(s.getByRole("heading", { name: "Your answers are with the review desk" })).toBeVisible();
  // The Sent list is the server's own copy of each answer (B3)
  await expect(s.getByText("Our Hyderabad branch alone.", { exact: true })).toBeVisible();
  await expect(s.getByText(/^Sent to .+, \d{1,2}(?::\d{2})? (?:am|pm)$/)).toBeVisible();
  await expect(s.getByRole("link", { name: "See your idea" })).toHaveAttribute("href", `/ideas/${ideaId}`);
  await expectNoSeriousAxeIssues(s);
  await expectNoSidewaysScroll(s);

  // V-ACC.review/8: the answer is under its part on the reviewer's page
  await reviewer.page.goto(`/desk/ideas/${ideaId}`);
  await expect(reviewer.page.getByText("Our Hyderabad branch alone.")).toBeVisible();
});

test('S-R3, C-FILE.row, L-QUESTIONS.answer, BLD-B275: a file-only answer through the "+" is checked, listed and sent', async ({
  browser,
}, testInfo) => {
  test.setTimeout(120_000);
  const NAME = "branch-call-log.md"; // a small synthetic text file (.md: .txt is not an allowed type)
  const sharer = await person(browser, PERSONAS.contributor);
  const reviewer = await person(browser, PERSONAS.reviewer);
  const title = `Rejection SMS gives a code only (${testInfo.project.name} ${Date.now()})`;
  const ideaId = await sharedIdea(sharer.code, title);
  const sent = await reviewer.page.request.post(`/api/desk/ideas/${ideaId}/question-sets`, {
    data: {
      questions: [{ part: "evidence", text: "Can you add the branch call log for last week?" }],
      time_to_answer: "3d",
    },
  });
  expect(sent.status()).toBe(201);

  const s = sharer.page;
  await s.goto(`/ideas/${ideaId}/answer`);
  // C-PROMPT.anatomy/2, DEC-124: the "+" in the box's tool row, with the board's name
  const plus = s.getByRole("button", { name: "Add files, a folder or a link" });
  await expect(plus).toBeVisible();
  await expect(s.getByRole("button", { name: "Skip for now" })).toBeVisible();
  // The upload makes the answer's row first (an empty save), then carries its id and never `for` (BLD-B274)
  const upload = s.waitForRequest((r) => r.url().endsWith("/api/files") && r.method() === "POST");
  const chooser = s.waitForEvent("filechooser");
  await plus.click();
  await (
    await chooser
  ).setFiles({ name: NAME, mimeType: "text/markdown", buffer: Buffer.from("The call log for week 47.") });
  const form = (await upload).postDataBuffer()?.toString("latin1") ?? "";
  expect(form).toContain('name="answer_id"');
  expect(form).not.toContain('name="for"');
  await expect(plus).toBeFocused(); // focus stays on the "+" after picking
  // C-FILE.row: the row, named by its file, reaches Checked as the screen asks again
  const row = s.getByRole("list", { name: "Your files" }).getByRole("listitem").filter({ hasText: NAME });
  await expect(row.getByText("Checked", { exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(row.getByRole("button", { name: `Remove ${NAME}` })).toBeVisible();
  // A file and no words is answered (the worker's _has_content)
  await expect(s.getByRole("button", { name: "Question 1, answered" })).toBeVisible();
  await expectNoSeriousAxeIssues(s);
  await s.getByRole("button", { name: "Next" }).click();
  await expect(s.getByRole("heading", { name: "Check your answers" })).toBeVisible();
  await expect(s.getByText("One file attached.", { exact: true })).toBeVisible();
  await s.getByRole("button", { name: /Send 1 answer to / }).click();
  await expect(s.getByRole("heading", { name: "Your answers are with the review desk" })).toBeVisible();
  await expect(s.getByText("One file attached.", { exact: true })).toBeVisible();
  const held = await db((c) =>
    c.query<{ purpose: string; sent: boolean }>(
      "SELECT a.purpose, an.sent_at IS NOT NULL AS sent FROM attachments a JOIN answers an ON an.id = a.answer_id " +
        "JOIN ideas i ON i.id = a.idea_uuid WHERE i.idea_id = $1",
      [ideaId],
    ),
  );
  expect(held.rows).toEqual([{ purpose: "idea", sent: true }]);
});

test("V-ACC.review/14: a reviewer opening their own idea cannot act on it", async ({ browser }, testInfo) => {
  const reviewer = await person(browser, PERSONAS.reviewer);
  const title = `A reviewer's own idea (${testInfo.project.name} ${Date.now()})`;
  const ideaId = await sharedIdea(reviewer.code, title);
  await reviewer.page.goto(`/desk/ideas/${ideaId}`);
  await expect(reviewer.page.getByRole("heading", { name: "Your own idea" })).toBeVisible();
  await expect(reviewer.page.getByRole("button", { name: "Decide on this idea" })).toHaveCount(0);
  await expect(reviewer.page.getByRole("button", { name: /^Ask about / })).toHaveCount(0);
});

/** Ideas the "Hide this" test made. Removed after it with what a hide leaves behind: the sharer's Inbox item, the
 * values sealed in the vault under the idea's hide scope (DRAFT-<uuid>), then the idea, whose rows go with it
 * (BLD-B247). */
const hideMade: string[] = [];
test.afterEach(async () => {
  if (!hideMade.length) return;
  const refs = hideMade.splice(0);
  await db(async (c) => {
    const ids = (
      await c.query<{ id: string }>("SELECT id::text AS id FROM ideas WHERE idea_id = ANY($1)", [refs])
    ).rows.map((r) => r.id);
    if (!ids.length) return;
    await c.query("DELETE FROM notifications WHERE idea_uuid = ANY($1::uuid[])", [ids]);
    await c.query("DELETE FROM pseudonym_vault WHERE scope_id = ANY($1)", [ids.map((id) => `DRAFT-${id}`)]);
    await c.query("DELETE FROM ideas WHERE id = ANY($1::uuid[])", [ids]);
  });
});

/** Select `words` inside the one text of a part that offers "Hide this", as a reviewer's drag would. */
async function selectIn(p: Page, part: string, words: string) {
  await p
    .getByRole("region", { name: part })
    .locator("[data-hide-key]")
    .first()
    .evaluate((el, w) => {
      const node = el.firstChild as Text;
      const at = node.data.indexOf(w);
      const range = document.createRange();
      range.setStart(node, at);
      range.setEnd(node, at + w.length);
      const sel = document.getSelection()!;
      sel.removeAllRanges();
      sel.addRange(range);
    }, words);
}

test("L-HIDE.rules/7, J-REVIEW/2–3: a reviewer hides a name the checks missed, and every copy reads masked", async ({
  browser,
}, testInfo) => {
  const sharer = await person(browser, PERSONAS.contributor);
  const reviewer = await person(browser, PERSONAS.reviewer);
  const title = `A missed name on the desk (${testInfo.project.name} ${Date.now()})`;
  const ideaId = await sharedIdea(
    sharer.code,
    title,
    "Investors call the branch because the rejection SMS gives a code. Lakshmi Narayanan called four times.",
  );
  hideMade.push(ideaId);
  const r = reviewer.page;
  await r.goto(`/desk/ideas/${ideaId}`);
  const problem = r.getByRole("region", { name: "The problem" });

  // too little selected: refused in plain words, nothing changes
  await selectIn(r, "The problem", "a ");
  await problem.getByRole("button", { name: "Hide this" }).click();
  await expect(problem.getByRole("alert")).toHaveText("Select at least 3 letters or numbers.");

  // the name: masked at once, the page read again
  await selectIn(r, "The problem", "Lakshmi Narayanan");
  await problem.getByRole("button", { name: "Hide this" }).click();
  await expect(problem).toContainText("••••an called four times.");
  await expect(problem).not.toContainText("Lakshmi Narayanan");
  await expect(problem.getByRole("button", { name: "Hide this" })).toHaveCount(0);
  await expectNoSeriousAxeIssues(r);
});

test("L-HIDE.rules/7, J-REVIEW/2–3: a reviewer hides a number mid-text from the keyboard alone (WCAG 2.1.1, 4.1.3)", async ({
  browser,
}, testInfo) => {
  const sharer = await person(browser, PERSONAS.contributor);
  const reviewer = await person(browser, PERSONAS.reviewer);
  const title = `A missed number on the desk (${testInfo.project.name} ${Date.now()})`;
  const ideaId = await sharedIdea(
    sharer.code,
    title,
    "Ring 9876501234 back: investors call the branch because the rejection SMS gives a code.",
  );
  hideMade.push(ideaId);
  const r = reviewer.page;
  await r.goto(`/desk/ideas/${ideaId}`);
  const problem = r.getByRole("region", { name: "The problem" });
  const text = problem.getByRole("group", { name: "The problem, text" });
  await text.focus();

  // the caret moves with the arrows (the first one starts it at the text's start), then Shift extends from there
  for (let i = 0; i < "Ring ".length; i += 1) await r.keyboard.press("ArrowRight");
  for (let i = 0; i < "9876501234".length; i += 1) await r.keyboard.press("Shift+ArrowRight");
  await expect.poll(() => r.evaluate(() => document.getSelection()?.toString())).toBe("9876501234");
  const hideButton = problem.getByRole("button", { name: "Hide this" });
  await expect(hideButton).toBeVisible();
  await expect(r.getByText("Hide this is next. Press Tab.", { exact: true })).toBeAttached();

  // Enter moves to "Hide this"; Enter there hides exactly the selected number
  await r.keyboard.press("Enter");
  await expect(hideButton).toBeFocused();
  const posted = r.waitForRequest((req) => req.method() === "POST" && req.url().endsWith(`/${ideaId}/hide`));
  await r.keyboard.press("Enter");
  expect((await posted).postDataJSON()).toMatchObject({
    start: 5,
    end: 15,
    units: "utf16",
    selected: "9876501234",
  });
  await expect(problem).not.toContainText("9876501234");
  await expect(problem).toContainText("••••34 back: investors call the branch");
  await expect(r.getByText("Hidden from everyone.", { exact: true })).toBeAttached();
  await expect(text).toBeFocused();
  await expectNoSeriousAxeIssues(r);
});

/** C-SORTS: "Decide by" pressed on a desktop; on a phone the one cycler reads "Sorted by decide by". */
async function expectDecideBy(p: Page): Promise<void> {
  const wide = p.getByRole("button", { name: "Decide by", exact: true });
  if (await wide.isVisible()) await expect(wide).toHaveAttribute("aria-pressed", "true");
  else await expect(p.getByRole("button", { name: "Sorted by decide by", exact: true })).toBeVisible();
}

test("DEC-110, S-R1.rules/4 (J-BROWSE/4, /6): the desk's search stays in the tab; no request URL and no address holds it", async ({
  browser,
}, testInfo) => {
  test.setTimeout(120_000);
  const sharer = await person(browser, PERSONAS.contributor);
  const reviewer = await person(browser, PERSONAS.reviewer);
  // A word no other idea on the desk holds, so the search finds this one alone
  const words = `Zebra${Date.now() % 100_000}Kestrel`;
  const title = `${words} branch form needs a plain reason (${testInfo.project.name})`;
  const ideaId = await sharedIdea(sharer.code, title);
  const r = reviewer.page;
  const asked = watchRequestUrls(r);
  const box = r.getByRole("searchbox", { name: "Search the desk" });
  const link = r.getByRole("link", { name: title, exact: true });
  await r.goto("/desk?tab=to_review&sort=decide_by");
  await expect(r.getByRole("heading", { level: 1, name: "Review desk" })).toBeVisible();
  const kept = await storageNames(r);
  await expect(box).toHaveAttribute("autocomplete", "off");
  await box.fill(words);
  await box.press("Enter");
  await expect(link).toBeVisible();
  await expect(r.getByRole("link", { name: /Rejection SMS codes need plain words/ })).toHaveCount(0);
  expect(new URL(r.url()).search).toBe("?tab=to_review&sort=decide_by");

  // Browser Back from the idea: the same tab, sort and search, the row focused
  await link.click();
  await r.waitForURL(new RegExp(`/desk/ideas/${ideaId}$`));
  await r.goBack();
  await expect(box).toHaveValue(words);
  await expect(link).toBeFocused();
  await expect(r.getByRole("tab", { name: /^To review/, selected: true })).toBeVisible();
  await expectDecideBy(r);

  // The page's own Back link brings the search back too (J-BROWSE/3, "browser or the page's own link")
  await link.click();
  await r.waitForURL(new RegExp(`/desk/ideas/${ideaId}$`));
  await r.locator(".ri-head a.back").click();
  await r.waitForURL(/\/desk\?/);
  await expect(box).toHaveValue(words);
  await expect(link).toBeVisible();

  // A reload keeps it
  await r.reload();
  await expect(box).toHaveValue(words);
  await expect(link).toBeVisible();
  await expect(r.getByRole("tab", { name: /^To review/, selected: true })).toBeVisible();

  // Not one request URL held the words, raw or encoded; nothing new in localStorage or a cookie
  expect(asked.filter(carrying(words))).toEqual([]);
  expect(carrying(words)(r.url())).toBe(false);
  expect(await storageNames(r)).toEqual(kept);
  expect(await storageCarries(r, words)).toBe(false);

  // The link pasted into another browser: the tab and sort apply, the search does not (J-BROWSE/6)
  const other = await person(browser, PERSONAS.reviewer);
  await other.page.goto(r.url());
  await expect(other.page.getByRole("tab", { name: /^To review/, selected: true })).toBeVisible();
  await expectDecideBy(other.page);
  await expect(other.page.getByRole("searchbox", { name: "Search the desk" })).toHaveValue("");
  await other.page.context().close();
});

test("DEC-121, S-R2: a committee-only member opens the reviewer's idea and its Listen", async ({
  browser,
}, testInfo) => {
  test.setTimeout(120_000);
  const sharer = await person(browser, PERSONAS.contributor);
  const reviewer = await person(browser, PERSONAS.reviewer);
  const title = `Branch slips ask for the same form twice (${testInfo.project.name} ${Date.now()})`;
  const ideaId = await sharedIdea(sharer.code, title);
  // A decided idea, as the Ones Committee meets it (J-COMMITTEE/1–2): the reviewer opens it and picks it
  await reviewer.page.goto(`/desk/ideas/${ideaId}`);
  const decided = await reviewer.page.request.post(`/api/desk/ideas/${ideaId}/decision`, {
    data: { choice: "pick", reason: REASON },
  });
  expect(decided.status(), `decision: ${await decided.text()}`).toBe(201);
  // An idea still with the desk, with a similar idea beside it: the reviewer is offered Decide, Ask, worth and Merge
  // on it (S-R2.panel, S-R2.similar), so the committee member's zero below is the role at work, not an empty page
  const onDesk = `Branch slips ask for the PAN twice (${testInfo.project.name} ${Date.now()})`;
  const onDeskId = await sharedIdea(sharer.code, onDesk);
  const similar = `Branch slips repeat the address box (${testInfo.project.name} ${Date.now()})`;
  const similarId = await sharedIdea(sharer.code, similar);
  await db((c) =>
    c.query(
      "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason) SELECT a.id, b.id, 'close', " +
        "'Same branch slip' FROM ideas a, ideas b WHERE a.idea_id = $1 AND b.idea_id = $2",
      [onDeskId, similarId],
    ),
  );
  await reviewer.page.goto(`/desk/ideas/${onDeskId}`);
  await expect(reviewer.page.getByRole("button", { name: "Decide on this idea" })).toBeVisible();
  await expect(reviewer.page.getByRole("button", { name: `Merge with ${similar}` })).toBeVisible();

  // A synthetic member who holds `committee` and nothing else (BLD-B270): made on this first sign-in, so no other
  // spec signs in as them. The role is given for this test and taken back after it (grants are read on every
  // request); only the grant this test inserted is deleted.
  const id = `SYN-C${Date.now().toString(36).toUpperCase()}${testInfo.project.name === "desktop" ? "D" : "P"}`;
  const ctx = await browser.newContext();
  const m = await ctx.newPage();
  await signIn(m, id, {
    employeeId: id,
    email: `${id.toLowerCase()}@kfintech.example`,
    name: "Synthetic Committee Member",
  });
  const me = (await (await m.request.get("/api/me")).json()) as { email: string };
  const grant = await db(
    async (c) =>
      (
        await c.query<{ id: string }>(
          "INSERT INTO role_grants (user_id, role) SELECT id, 'committee' FROM users WHERE email = $1 " +
            "RETURNING id::text AS id",
          [me.email],
        )
      ).rows[0]!.id,
  );
  try {
    const held = await db((c) =>
      c.query<{ role: string }>(
        "SELECT g.role FROM role_grants g JOIN users u ON u.id = g.user_id WHERE u.email = $1 " +
          "AND (g.valid_to IS NULL OR g.valid_to > now())",
        [me.email],
      ),
    );
    expect(held.rows.map((r) => r.role)).toEqual(["committee"]);

    // S-R2 opens for them, with the strip "Listen to the whole idea", and no desk action
    await m.goto(`/desk/ideas/${ideaId}`);
    await expect(m).toHaveURL(new RegExp(`/desk/ideas/${ideaId}$`));
    await expect(m.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expect(m.getByRole("heading", { name: "Listen to the whole idea" })).toBeVisible();
    await expect(m.getByRole("button", { name: "Decide on this idea" })).toHaveCount(0);
    // C-LISTEN, L-LISTEN: the desk's script answers them
    const listen = await m.request.get(`/api/desk/ideas/${ideaId}/listen`);
    expect(listen.status(), `listen: ${await listen.text()}`).toBe(200);
    // BLD-B270, S-R2: on the idea still with the desk they read it, and are offered none of the desk's actions
    // (`can_act` holds only for the review desk)
    await m.goto(`/desk/ideas/${onDeskId}`);
    await expect(m.getByRole("heading", { level: 1, name: onDesk })).toBeVisible();
    await expect(m.getByRole("heading", { name: "Review this idea" })).toBeVisible();
    await expect(m.getByRole("button", { name: "Decide on this idea" })).toHaveCount(0);
    await expect(m.getByRole("button", { name: /^Ask about this/ })).toHaveCount(0);
    await expect(m.getByRole("button", { name: /^Ask .* first/ })).toHaveCount(0);
    await expect(m.getByRole("button", { name: /what it’s worth$/ })).toHaveCount(0);
    await expect(m.getByRole("button", { name: /^Merge with / })).toHaveCount(0);
    // C-SIDEBAR: their sidebar is as before (Ones Committee, no Review desk); a phone's tabs are everyone's
    await m.goto("/home");
    expect(await navLabels(m)).toEqual(
      testInfo.project.name === "phone-360"
        ? PHONE_TABS
        : ["Share a problem", "Home", "Find your crew", "Wall", "Inbox", "Ones Committee"],
    );
  } finally {
    await db((c) => c.query("DELETE FROM role_grants WHERE id = $1::bigint", [grant]));
    await ctx.close();
  }
});

test("BLD-B272, S-R2.panel, J-REVIEW/A1: a queued question is still there after a reload, and removing it is kept too", async ({
  browser,
}, testInfo) => {
  test.setTimeout(90_000);
  const sharer = await person(browser, PERSONAS.contributor);
  const reviewer = await person(browser, PERSONAS.reviewer);
  const title = `Nominee page goes missing from branch slips (${testInfo.project.name} ${Date.now()})`;
  const ideaId = await sharedIdea(sharer.code, title);
  const similar = `Branch slips drop the nominee page (${testInfo.project.name} ${Date.now()})`;
  const similarId = await sharedIdea(sharer.code, similar);
  await db((c) =>
    c.query(
      "INSERT INTO similar_links (idea_uuid, other_idea_uuid, strength, reason) SELECT a.id, b.id, 'close', " +
        "'Same branch slip' FROM ideas a, ideas b WHERE a.idea_id = $1 AND b.idea_id = $2",
      [ideaId, similarId],
    ),
  );
  const r = reviewer.page;
  const queueSaved = () =>
    r.waitForResponse(
      (res) =>
        res.request().method() === "PUT" &&
        new URL(res.url()).pathname === `/api/desk/ideas/${ideaId}/question-sets/queued`,
    );
  await r.goto(`/desk/ideas/${ideaId}`);
  await expect(r.getByRole("heading", { name: "Review this idea" })).toBeVisible();

  // BLD-B273, F-SPACE.targets (WCAG 2.5.8): S-R2's Similar ideas keep every target 24 × 24 px or spaced clear
  await expect(r.getByRole("button", { name: `Merge with ${similar}` })).toBeAttached();
  const targets = await new AxeBuilder({ page: r }).include(".ri-sim").withRules(["target-size"]).analyze();
  expect(
    targets.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`),
    "S-R2 Similar ideas, target size",
  ).toEqual([]);

  // Ask about this queues the part's suggestion; the page saves the queue once the changes pause
  const howOften = r.getByRole("region", { name: "How often" });
  const saved = queueSaved();
  await howOften.getByRole("button", { name: "Ask about this, How often" }).click();
  await expect(r.getByRole("button", { name: /^Ask .* first/ })).toContainText("1 question ready");
  expect((await saved).status(), "the queue is saved").toBe(200);

  // Back on the page later, the question is still queued, ready to send (the Ask section folded, S-R2.panel/2)
  await r.reload();
  await expect(r.getByRole("heading", { name: "Review this idea" })).toBeVisible();
  await expect(r.getByRole("button", { name: /^Ask .* first/ })).toContainText("1 question ready");
  await expect(r.getByRole("button", { name: /^Ask .* first/ })).toHaveAttribute("aria-expanded", "false");
  await expect(r.getByRole("button", { name: /Send 1 question to / })).toBeVisible();
  await expect(howOften.getByRole("button", { name: "Asking, How often" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expectNoSeriousAxeIssues(r);

  // Removing it is saved the same way: the next visit opens with nothing queued
  await r.getByRole("button", { name: /^Ask .* first/ }).click();
  const removed = queueSaved();
  await r.getByRole("button", { name: /^Remove: / }).click();
  expect((await removed).status(), "the emptied queue is saved").toBe(200);
  await r.reload();
  await expect(r.getByRole("button", { name: "Decide on this idea" })).toBeVisible();
  await expect(r.getByRole("button", { name: /^Ask .* first/ })).not.toContainText("ready");
});
