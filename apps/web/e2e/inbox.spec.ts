/**
 * S-H5 Inbox with C-INBOX-READER (L-INBOX): the tabs and their counts, the first item open on desktop, opening an
 * item marks it read and every count drops at once, arrow keys move through the list, an open ask cannot be
 * archived, a done one can, Mark all read; on a phone the list is the screen and an item is its own screen, with its
 * own h1. axe and the 320 px reflow check on every state (V-ACC.visual/4, BLD-A163).
 *
 * Each test signs in a fresh synthetic person (SYN-16<worker><4 random digits>, outside the seed's range, so the
 * desktop and phone workers never share one) and writes four synthetic Inbox items for them straight into the dev
 * database, as `notify.post` would. The `inbox` fixture removes the person and everything that hangs off them
 * (items, sessions, the privacy acceptance, the contributor code) before it signs them in and again when the test
 * ends, pass or fail. Items carry IDs and enums only; the worker renders their words from the HR templates.
 */
import { randomInt } from "node:crypto";

import { test as base, expect, type Page } from "@playwright/test";
import { Client } from "pg";

import { expectNoSeriousAxeIssues, signIn } from "./helpers";

const DATABASE_URL =
  process.env.E2E_DATABASE_URL || "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable";

type Person = { syn: string; email: string; name: string };

/** A synthetic person no other worker can draw: the worker's own two digits, then four random ones. */
function synPerson(worker: number): Person {
  const n = `16${String(worker % 100).padStart(2, "0")}${String(randomInt(10_000)).padStart(4, "0")}`;
  return { syn: `SYN-${n}`, email: `inbox.${n}.e2e@kfintech.example`, name: `Inbox Tester ${n}` };
}

async function withDb<T>(run: (db: Client) => Promise<T>): Promise<T> {
  const db = new Client({ connectionString: DATABASE_URL });
  await db.connect();
  try {
    return await run(db);
  } finally {
    await db.end();
  }
}

/** Deletes the person and their rows. Their items, sessions, privacy acceptance, contributor code and preferences
 * go with them (each references users ON DELETE CASCADE); they are named here too, so a test never leaves one. */
async function removePerson(email: string): Promise<void> {
  await withDb(async (db) => {
    await db.query("BEGIN");
    try {
      const { rows } = await db.query("SELECT id FROM users WHERE lower(email) = $1", [email]);
      const ids = rows.map((r: { id: string }) => String(r.id));
      if (ids.length) {
        for (const table of [
          "notifications",
          "sessions",
          "privacy_acceptances",
          "comms_prefs",
          "contributor_map",
        ])
          await db.query(`DELETE FROM ${table} WHERE user_id = ANY($1::uuid[])`, [ids]);
        await db.query("DELETE FROM users WHERE id = ANY($1::uuid[])", [ids]);
      }
      await db.query("COMMIT");
    } catch (err) {
      await db.query("ROLLBACK");
      throw err;
    }
  });
}

/** Signs the person in and writes their four items: the desk's questions (needs you, unread, newest), a mention
 * (read), a stage move from 1% Club (unread) and a decision (read, two weeks ago). Returns their users.id. */
async function freshInbox(page: Page, person: Person): Promise<string> {
  await signIn(page, person.syn, { email: person.email, name: person.name });
  return withDb(async (db) => {
    const me = await db.query("SELECT id FROM users WHERE lower(email) = $1", [person.email]);
    const userId = String(me.rows[0]?.id ?? "");
    if (!userId) throw new Error(`no user for ${person.syn}`);
    const other = await db.query(
      "SELECT id FROM users WHERE id <> $1 AND active AND name IS NOT NULL ORDER BY id LIMIT 1",
      [userId],
    );
    const sender = String(other.rows[0].id);
    const rows: [string, string | null, boolean, boolean, string, string | null, object, object[]][] = [
      // kind, from, needs you, read, created, due, refs, actions
      [
        "decision",
        sender,
        false,
        true,
        "14 days",
        null,
        { choice: "pick" },
        [{ label: "Read the decision", to: "/my-ideas", style: "primary" }],
      ],
      [
        "stage_moved",
        null,
        false,
        false,
        "2 days",
        null,
        { to: "being_built" },
        [{ label: "Open the idea", to: "/my-ideas", style: "primary" }],
      ],
      [
        "mention",
        sender,
        false,
        true,
        "1 hour",
        null,
        {},
        [{ label: "Open the conversation", to: "/my-ideas", style: "primary" }],
      ],
      [
        "questions",
        sender,
        true,
        false,
        "1 minute",
        "3 days",
        { count: 3 },
        [{ label: "Answer the questions", to: "/my-ideas", style: "primary" }],
      ],
    ];
    for (const [kind, from, needs, read, ago, due, refs, actions] of rows) {
      await db.query(
        "INSERT INTO notifications (user_id, channel, template, event, payload, urgency, state, created_at, sent_at, " +
          "read_at, kind, from_user_id, needs_you, due_at, actions) VALUES ($1, 'in_app', $2, $3, $4, 'immediate', " +
          "$5, now() - $6::interval, now() - $6::interval, CASE WHEN $7 THEN now() END, $8, $9, $10, " +
          "now() + $11::interval, $12)",
        [
          userId,
          `inbox/${kind}`,
          `inbox.${kind}`,
          JSON.stringify(refs),
          read ? "read" : "sent",
          ago,
          read,
          kind,
          from,
          needs,
          due,
          JSON.stringify(actions),
        ],
      );
    }
    return userId;
  });
}

/** `inbox()` signs in a fresh person with four items and returns their users.id. The person is removed before the
 * first insert (a run that was killed may have left one) and after the test, whether it passed or failed. */
const test = base.extend<{ inbox: () => Promise<string> }>({
  // `provide` is Playwright's `use`, named so the React hooks lint does not read it as React's `use`.
  inbox: async ({ page }, provide, testInfo) => {
    const person = synPerson(testInfo.parallelIndex);
    await removePerson(person.email);
    try {
      await provide(() => freshInbox(page, person));
    } finally {
      await removePerson(person.email);
    }
  },
});

const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1280) < 760;
const tab = (page: Page, name: RegExp) => page.getByRole("tab", { name });
const row = (page: Page, what: RegExp) => page.getByRole("button", { name: what });

test.describe("S-H5 Inbox", () => {
  test("S-H5.layout V-ACC.track/8 V-ACC.visual/4: tabs and counts, the first item open, opening it drops every count at once", async ({
    page,
    inbox,
  }) => {
    test.skip(isPhone(page), "desktop layout; the phone has its own test");
    await inbox();
    await page.goto("/inbox");
    await expect(page.getByRole("heading", { level: 1, name: "Inbox" })).toBeVisible();
    for (const name of [/^All 4$/, /^Needs you 1$/, /^Archived 0$/])
      await expect(tab(page, name)).toBeVisible();
    await expect(tab(page, /^All 4$/)).toHaveAttribute("aria-selected", "true");
    for (const group of ["Today", "This week", "Earlier"]) {
      await expect(page.getByRole("heading", { level: 2, name: group })).toBeVisible();
    }

    // S-H5.rules/2: the first item of the tab is open on desktop; opening it marked it read (S-H5.rules/4).
    const questions = row(page, /^.+ from the review desk asked you 3 questions, /);
    await expect(questions).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("Questions from the review desk", { exact: true })).toBeVisible();
    await expect(page.getByText("1 of 4", { exact: true })).toBeVisible();
    await expect(page.getByText(/^3 days left$|^2 days left$/).first()).toBeVisible();
    await expect(page.getByText("1 unread", { exact: true })).toBeVisible();
    await expect(tab(page, /^Unread 1$/)).toBeVisible();
    await expectNoSeriousAxeIssues(page);

    // V-ACC.visual/12: the forward action is a primary button at the bottom right of the reader.
    const answer = page.getByRole("link", { name: "Answer the questions" });
    await expect(answer).toHaveAttribute("href", "/my-ideas");
    const reader = page.getByRole("region", { name: "Reader" });
    const [a, r] = [await answer.boundingBox(), await reader.boundingBox()];
    expect(a && r && r.x + r.width - (a.x + a.width)).toBeLessThan(r!.width / 3);
    expect(a && r && r.y + r.height - (a.y + a.height)).toBeLessThan(120);

    // Opening the stage move from 1% Club drops the unread count to 0 everywhere on the page.
    await row(page, /^1% Club moved your idea to Being built, /).click();
    await expect(page.getByText("0 unread", { exact: true })).toBeVisible();
    await expect(tab(page, /^Unread 0$/)).toBeVisible();

    // Needs you holds the open ask only; Unread is empty; each state is axe clean.
    await tab(page, /^Needs you 1$/).click();
    await expect(row(page, /asked you 3 questions/)).toBeVisible();
    await expect(row(page, /picked your idea/)).toHaveCount(0);
    await expectNoSeriousAxeIssues(page);
    await tab(page, /^Unread 0$/).click();
    await expect(page.getByText("Nothing here.", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Pick something on the left to read it here.", { exact: true }),
    ).toBeVisible();
    await expectNoSeriousAxeIssues(page);
  });

  test("S-H5.rules/2 L-INBOX.rules/5: arrow keys move, Enter opens; an open ask stays, a done item archives", async ({
    page,
    inbox,
  }) => {
    test.skip(isPhone(page), "desktop layout; the phone has its own test");
    await inbox();
    await page.goto("/inbox");
    const questions = row(page, /asked you 3 questions/);
    await expect(questions).toHaveAttribute("aria-pressed", "true");

    // Arrow keys move through the list; Enter opens (S-H5.rules/2).
    await questions.focus();
    await page.keyboard.press("ArrowDown");
    const mention = row(page, /mentioned you, /);
    await expect(mention).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(mention).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("2 of 4", { exact: true })).toBeVisible();

    // An item that still needs the person is not archived (L-INBOX.rules/5). Archive is marked unavailable
    // (aria-disabled) but still says why when pressed, so it is pressed from the keyboard.
    await questions.click();
    await page.getByRole("button", { name: "Archive" }).focus();
    await page.keyboard.press("Enter");
    await expect(
      page.getByText("This still needs you, so it stays in your Inbox until it's done.", { exact: true }),
    ).toBeVisible();
    await expect(tab(page, /^Archived 0$/)).toBeVisible();

    // A decision can be archived: it leaves All and is under Archived.
    await row(page, /picked your idea, /).click();
    await page.getByRole("button", { name: "Archive" }).click();
    await expect(tab(page, /^All 3$/)).toBeVisible();
    await expect(tab(page, /^Archived 1$/)).toBeVisible();
    await expect(row(page, /picked your idea, /)).toHaveCount(0);
    await tab(page, /^Archived 1$/).click();
    await expect(row(page, /picked your idea, /)).toBeVisible();
    await expectNoSeriousAxeIssues(page);

    // Mark unread on the open item, then Mark all read. Archiving opened the next item, the stage move, so nothing
    // is unread here and Mark all read is unavailable (aria-disabled) until something is.
    await tab(page, /^All 3$/).click();
    await expect(page.getByText("0 unread", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Mark unread" }).click();
    await expect(page.getByText("1 unread", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Mark all read" }).click();
    await expect(page.getByText("0 unread", { exact: true })).toBeVisible();
  });

  test("S-H5.rules/6 V-ACC.visual/4: on a phone the list is the screen and an item opens as its own screen", async ({
    page,
    inbox,
  }) => {
    test.skip(!isPhone(page), "phone layout");
    await inbox();
    await page.goto("/inbox");
    await expect(page.getByRole("heading", { level: 1, name: "Inbox" })).toBeVisible();
    await expect(page.getByText("2 unread", { exact: true })).toBeVisible();
    // Nothing opens on its own: the reader is not on screen.
    await expect(page.getByRole("region", { name: "Reader" })).toBeHidden();
    await expectNoSeriousAxeIssues(page);

    await row(page, /asked you 3 questions/).click();
    await expect(page.getByText("Questions from the review desk", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: "Inbox" })).toBeHidden();
    // The item is its own screen, so its title is the screen's h1 (WCAG 2.1 AA).
    await expect(page.getByRole("heading", { level: 1, name: "asked you 3 questions" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Answer the questions" })).toBeVisible();
    await expectNoSeriousAxeIssues(page);

    await page.getByRole("button", { name: "Inbox", exact: true }).click();
    await expect(page.getByText("1 unread", { exact: true })).toBeVisible();
    await expect(tab(page, /^Unread 1$/)).toBeVisible();
  });

  test("S-H5, C-INBOX-READER, P-ROUTES.state (J-BROWSE/4, /6): the tab and the open item stay in the address, so Back and a reload come to the same view", async ({
    page,
    inbox,
  }) => {
    await inbox();
    await page.goto("/inbox");
    await tab(page, /^Needs you 1$/).click();
    await expect(page).toHaveURL(/\/inbox\?tab=needs_you$/);
    const questions = row(page, /asked you 3 questions/);
    await questions.click();
    await expect(page).toHaveURL(/\/inbox\?tab=needs_you&item=\d+$/);
    const here = page.url();

    await page.getByRole("link", { name: "Answer the questions" }).click();
    await page.waitForURL(/\/my-ideas/);
    await page.goBack();
    await expect(page).toHaveURL(here);
    if (isPhone(page)) {
      // The item the person had open is its own screen again, the list hidden behind it (S-H5.rules/6); the
      // screen's own Back returns to the list, on the same tab, and the address lets the item go.
      await expect(page.getByRole("heading", { level: 1, name: "asked you 3 questions" })).toBeVisible();
      await page.getByRole("button", { name: "Inbox", exact: true }).click();
      await expect(tab(page, /^Needs you/)).toHaveAttribute("aria-selected", "true");
      await expect(page).toHaveURL(/\/inbox\?tab=needs_you$/);
    } else {
      await expect(tab(page, /^Needs you/)).toHaveAttribute("aria-selected", "true");
      await expect(questions).toHaveAttribute("aria-pressed", "true");
    }

    await page.reload();
    await expect(tab(page, /^Needs you/)).toHaveAttribute("aria-selected", "true");
    if (!isPhone(page)) await expect(questions).toHaveAttribute("aria-pressed", "true");

    // An unknown tab or an item that is not the person's opens the default view, with no error.
    await page.goto("/inbox?tab=starred&item=999999999");
    await expect(tab(page, /^All 4$/)).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { level: 1, name: "Inbox" })).toBeVisible();
  });

  test("S-H2B route: /inbox/:itemId opens the Inbox with that item open", async ({ page, inbox }) => {
    const userId = await inbox();
    const { rows } = await withDb((db) =>
      db.query("SELECT id FROM notifications WHERE user_id = $1 AND kind = 'mention'", [userId]),
    );
    await page.goto(`/inbox/${rows[0].id}`);
    if (isPhone(page)) {
      // On a phone the item opens as its own screen (S-H5.rules/6): the list is hidden and the title is the h1.
      await expect(page.getByRole("heading", { level: 1, name: "mentioned you" })).toBeVisible();
    } else {
      await expect(row(page, /mentioned you, /)).toHaveAttribute("aria-pressed", "true");
    }
    await expect(page.getByRole("link", { name: "Open the conversation" })).toBeVisible();
  });
});
