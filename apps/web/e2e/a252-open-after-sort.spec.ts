/**
 * BLD-A252 (J-BROWSE/4, S-R1.rules/4, S-07.return): a row opened at once after a sort or a search opens its idea, and
 * Back returns to the list with that row. The click came right after a change that writes the list's address in
 * place; now and then the row's link did nothing (journeys J-BROWSE/4, review-desk.spec.ts's search test). Each test
 * makes the change and clicks the row's link with no wait between, on both widths lane D checks (desktop and
 * phone-360). The desk's idea is written straight into this run's database for the seeded sharer, as
 * review-desk.spec.ts does; My ideas reads Tanvi's ideas on the 1% Club seed and changes nothing. Synthetic data only.
 */
import { expect, test, type Browser, type Locator, type Page } from "@playwright/test";
import { Client } from "pg";

import { CLUB, clubLoaded, esc, NO_SEED, seededIdea } from "./club";
import { PERSONAS, signIn } from "./helpers";

const DATABASE_URL =
  process.env.E2E_DATABASE_URL || "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable";
/** The idea page has this long to open after the click (the flake: it never did). */
const OPENS = { timeout: 10_000 };
/** A list change waits for the server's next view; generous, so a cold server never fails a step that works. */
const soon = expect.configure({ timeout: 15_000 });

const isPhone = (name: string) => name.startsWith("phone");
const here = (page: Page) => {
  const u = new URL(page.url());
  return u.pathname + u.search;
};

async function db<T>(fn: (c: Client) => Promise<T>): Promise<T> {
  const c = new Client({ connectionString: DATABASE_URL });
  await c.connect();
  try {
    return await fn(c);
  } finally {
    await c.end();
  }
}

/** The seeded sharer's contributor code (one is made if they have none yet), signed in on a page of their own. */
async function sharerCode(browser: Browser): Promise<string> {
  const ctx = await browser.newContext();
  try {
    const page = await ctx.newPage();
    await signIn(page, PERSONAS.contributor);
    const me = (await (await page.request.get("/api/me")).json()) as { email: string };
    return await db(async (c) => {
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
      return m.rows[0]!.contributor_code;
    });
  } finally {
    await ctx.close();
  }
}

/** A shared idea on the desk for `code`, with its sharer as crew lead. */
async function sharedIdea(code: string, title: string): Promise<string> {
  return db(async (c) => {
    const r = await c.query<{ idea_id: string; id: string }>(
      "INSERT INTO ideas (idea_id, contributor_code, status, title, summary, often, affects, area, city, kind, " +
        "shared_at, decide_by, edit_closes_at) VALUES (next_idea_ref(), $1, 'with_review_desk', $2, $3, " +
        "'About 40 calls a day at one branch.', ARRAY['Investors'], 'Investor service', 'Hyderabad', 'problem', " +
        "now(), now() + interval '5 days', now() + interval '3 days') RETURNING idea_id, id",
      [code, title, "Investors call the branch because the folio statement shows a code, not a reason."],
    );
    await c.query(
      "INSERT INTO crew_members (idea_uuid, contributor_code, role, via) VALUES ($1, $2, 'lead', 'shared')",
      [r.rows[0]!.id, code],
    );
    return r.rows[0]!.idea_id;
  });
}

/**
 * The reviewer on the desk, its list read once on arrival: that read comes from the page's own code, so the page has
 * hydrated and a click from here on is the page's, not the browser's.
 */
async function openDesk(page: Page, link: Locator): Promise<void> {
  await signIn(page, PERSONAS.reviewer);
  const arrived = page.waitForResponse(
    (r) => new URL(r.url()).pathname === "/api/desk" && r.request().method() === "GET" && r.ok(),
  );
  await page.goto("/desk?tab=to_review&sort=time_left");
  await arrived;
  await expect(page.getByRole("heading", { level: 1, name: "Review desk" })).toBeVisible();
  await expect(link).toBeVisible();
}

/** C-SORTS to "Decide by": the pressed button on a desktop, the one cycler on a phone ("Sorted by time left"). */
async function deskSortButton(page: Page): Promise<Locator> {
  const wide = page.getByRole("button", { name: "Decide by", exact: true });
  return (await wide.isVisible())
    ? wide
    : page.getByRole("button", { name: "Sorted by time left", exact: true });
}

async function expectDecideBy(page: Page): Promise<void> {
  const wide = page.getByRole("button", { name: "Decide by", exact: true });
  if (await wide.isVisible()) await expect(wide).toHaveAttribute("aria-pressed", "true");
  else await expect(page.getByRole("button", { name: "Sorted by decide by", exact: true })).toBeVisible();
}

test.describe("BLD-A252 on the review desk (S-R1)", () => {
  test("BLD-A252, J-BROWSE/4, S-R1.rules/4: a sort and then a row's link at once opens the idea; Back returns to the row", async ({
    page,
    browser,
  }, info) => {
    test.setTimeout(120_000);
    const title = `Folio statement shows a code, not a reason (${info.project.name} ${Date.now()}-${info.repeatEachIndex})`;
    const ideaId = await sharedIdea(await sharerCode(browser), title);
    const link = page.getByRole("main").getByRole("link", { name: title, exact: true });
    await openDesk(page, link);
    const sort = await deskSortButton(page);

    // The sort writes the desk's address in place; the row is clicked before its list comes back
    await sort.click();
    await link.click();
    await page.waitForURL(new RegExp(`/desk/ideas/${esc(ideaId)}$`), OPENS);

    await page.goBack();
    await soon.poll(() => here(page)).toBe("/desk?tab=to_review&sort=decide_by");
    await expect(link).toBeFocused();
    await expect(page.getByRole("tab", { name: /^To review/, selected: true })).toBeVisible();
    await expectDecideBy(page);
  });

  test("BLD-A252, J-BROWSE/4, DEC-110: a search and then a row's link at once opens the idea; Back returns to the row and the search", async ({
    page,
    browser,
  }, info) => {
    test.setTimeout(120_000);
    // A word no other idea on the desk holds, so the search finds this one alone
    const words = `Zebra${Date.now() % 100_000}Heron${info.repeatEachIndex}`;
    const title = `${words} folio statement needs a plain reason (${info.project.name})`;
    const ideaId = await sharedIdea(await sharerCode(browser), title);
    const link = page.getByRole("main").getByRole("link", { name: title, exact: true });
    await openDesk(page, link);
    const box = page.getByRole("searchbox", { name: "Search the desk" });

    // The search writes the desk's address in place; the row is clicked before the searched list comes back
    await box.fill(words);
    await box.press("Enter");
    await link.click();
    await page.waitForURL(new RegExp(`/desk/ideas/${esc(ideaId)}$`), OPENS);

    await page.goBack();
    await soon.poll(() => here(page)).toBe("/desk?tab=to_review&sort=time_left");
    await expect(box).toHaveValue(words);
    await expect(link).toBeFocused();
  });
});

test.describe("BLD-A252 on My ideas (S-07)", () => {
  test.describe.configure({ timeout: 90_000 });
  let seed = false;
  test.beforeAll(async () => {
    seed = await clubLoaded();
  });
  test.beforeEach(() => test.skip(!seed, NO_SEED));

  /** A row's title link in the page's own list (the sidebar lists the same idea under "Your ideas"). */
  const titleLink = (page: Page, title: string) =>
    page.getByRole("main").getByRole("link", { name: new RegExp(`^${esc(title)}$`) });

  /** My ideas' sorts in the order the phone's one cycler steps through them (ideapage/mine.py SORTS). */
  const SORTS = ["latest", "shared", "stage"] as const;
  type Sort = (typeof SORTS)[number];
  const LABEL: Record<Sort, string> = { latest: "Latest activity", shared: "Date shared", stage: "Stage" };
  const address = (sort: Sort) => (sort === "latest" ? "/my-ideas" : `/my-ideas?sort=${sort}`);

  /**
   * C-SORTS on My ideas, the control that picks `to` from the sort on screen: its button on a desktop; on a phone the
   * one cycler, which names the sort before it ("Sorted by stage") and moves to the next.
   */
  function sortTo(page: Page, to: Sort, phone: boolean): Locator {
    if (!phone) return page.getByRole("button", { name: LABEL[to], exact: true });
    const before = SORTS[(SORTS.indexOf(to) + SORTS.length - 1) % SORTS.length]!;
    return page.getByRole("button", { name: `Sorted by ${LABEL[before].toLowerCase()}`, exact: true });
  }

  /** Signs Tanvi in on My ideas sorted by `sort` and waits for that view's answer. The address takes each sort from
   * the page's own code, so once it has, the page has hydrated. On a phone the cycler steps there one sort at a time. */
  async function openSorted(page: Page, sort: Exclude<Sort, "latest">, phone: boolean): Promise<void> {
    await signIn(page, CLUB.tanvi);
    await page.goto("/my-ideas");
    await expect(page.getByRole("heading", { level: 1, name: "My ideas" })).toBeVisible();
    const answered = page.waitForResponse(
      (r) =>
        new URL(r.url()).pathname === "/api/me/ideas" &&
        r.request().method() === "POST" &&
        r.ok() &&
        (JSON.parse(r.request().postData() ?? "{}") as { sort?: string }).sort === sort,
    );
    const path = phone ? SORTS.slice(1, SORTS.indexOf(sort) + 1) : [sort];
    for (const step of path) {
      // A click before the page has hydrated does nothing: it is tried again until the address takes the sort
      await expect(async () => {
        if (here(page) !== address(step)) await sortTo(page, step, phone).click({ timeout: 5_000 });
        expect(here(page)).toBe(address(step));
      }).toPass({ timeout: 30_000 });
    }
    await answered;
  }

  test("BLD-A252, J-BROWSE/4, S-07.return: a sort and then a row's link at once opens the idea; Back returns to the row", async ({
    page,
  }, info) => {
    const phone = isPhone(info.project.name);
    const t5 = await seededIdea("T5");
    const link = titleLink(page, t5.title);
    // From the sort just before "Latest activity" in the phone's cycle, so one press of either control gets there
    await openSorted(page, "stage", phone);
    await expect(link).toBeVisible();
    const latest = sortTo(page, "latest", phone);

    // The sort writes My ideas' address in place; the row is clicked before its list comes back
    await latest.click();
    await link.click();
    await page.waitForURL(new RegExp(`/ideas/${esc(t5.ref)}$`), OPENS);

    await page.goBack();
    await soon.poll(() => here(page)).toBe("/my-ideas");
    await expect(link).toBeFocused();
    await expect(
      page.getByText(
        phone ? "Back where you were: All, latest activity first." : "Back where you were: Yours.",
      ),
    ).toBeVisible();
  });

  test("BLD-A252, J-BROWSE/4, DEC-110: a search and then a row's link at once opens the idea; Back returns to the row and the search", async ({
    page,
  }, info) => {
    test.skip(
      isPhone(info.project.name),
      "the search bar is the desktop board's; the phone opens it from a search (PhoneMyIdeas)",
    );
    const t5 = await seededIdea("T5");
    const link = titleLink(page, t5.title);
    await openSorted(page, "shared", false);
    const box = page.getByRole("searchbox", { name: /^Search/ });

    // The search writes My ideas' address in place and fades the list through loading rows; the row's link is
    // clicked as soon as the searched list shows it
    await box.fill("Redemption");
    await box.press("Enter");
    await link.click();
    await page.waitForURL(new RegExp(`/ideas/${esc(t5.ref)}$`), OPENS);

    await page.goBack();
    await soon.poll(() => here(page)).toBe("/my-ideas?sort=shared");
    await expect(box).toHaveValue("Redemption");
    await expect(link).toBeFocused();
  });
});
