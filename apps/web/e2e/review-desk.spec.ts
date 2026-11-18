/**
 * The review side in the browser (J-REVIEW, J-COMMITTEE, J-TRACK answer): V-ACC.review, V-ACC.committee and the
 * sharer's Answer screen. Ideas are written straight into this run's database for the seeded sharer, because the
 * share journey is another lane's; everything after that goes through the screens. Synthetic data only.
 */
import { expect, test, type Browser, type Page } from "@playwright/test";
import { Client } from "pg";

import { expectNoSeriousAxeIssues, expectNoSidewaysScroll, PERSONAS, signIn } from "./helpers";

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
