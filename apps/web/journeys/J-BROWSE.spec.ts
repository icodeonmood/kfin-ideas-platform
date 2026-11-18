/**
 * J-BROWSE: browse, open, come back to the same place (1pc-handoff/03-journeys/J-BROWSE.md; rules S-07.return,
 * P-ROUTES.state). Hand-offs only; the detail is in V-ACC.browse.
 * Copy: reference/copy/MyIdeas.md (S-07, "Back from an idea"), Status.md (S-06 breadcrumb), Desk.md (S-R1),
 * Inbox.md (S-H5), Wall.md (S-WALL), Idea.md (S-09 "Back to the Wall").
 * Cast: Tanvi browses her ideas, her Inbox and the Wall; Harish the review desk; Naveen opens Tanvi's shared link.
 * Seed: read only. Rows open T5 (Tanvi's, with the desk), Z1 (with Harish, waiting on Zoya), T6's questions in the
 * Inbox (its answer screen is opened, nothing sent) and A1 from the Wall: being built, one of only two in Kindling's
 * Being built card (up to three each, S-WALL.kindling), so it is always drawn, never behind "Show 5 more".
 */
import { expect, type Locator, type Page } from "@playwright/test";

import { carriedFor, ideaUrl, seeded, signInAs, snap, step } from "./lib";

const SEARCH = "Redemption"; // T5: "Redemption status is not visible to the branch"

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * A row's link on My ideas: the title, or "{action} : {title}" (MyIdeas.md Controls). Looked for in the page's
 * main area only: the shell's sidebar lists the same idea under "Your ideas" with a link of the same shape.
 */
function rowLink(page: Page, title: string): Locator {
  return page
    .getByRole("main")
    .getByRole("link", { name: new RegExp(`(?:^|: )${esc(title)}$`) })
    .first();
}

const carried = carriedFor<{ list: string }>("J-BROWSE");

function listUrl(): string {
  if (!carried.list)
    throw new Error("J-BROWSE/1 did not leave the list's URL; run the journey from the start");
  return carried.list;
}

/** The tab and sort, which the URL keeps. */
async function expectTabAndSort(page: Page): Promise<void> {
  await expect(page.getByRole("tab", { name: /^Yours/, selected: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Date shared" })).toHaveAttribute("aria-pressed", "true");
}

/** Tab, sort and the search, which the tab's own memory keeps (DEC-110). */
async function expectListState(page: Page): Promise<void> {
  await expectTabAndSort(page);
  await expect(page.getByRole("searchbox", { name: /^Search/ })).toHaveValue(SEARCH);
}

async function search(page: Page): Promise<void> {
  await page.getByRole("searchbox", { name: /^Search/ }).fill(SEARCH);
  await page.getByRole("searchbox", { name: /^Search/ }).press("Enter");
}

/**
 * A tab or sort click on the review desk, and the list it asks for: done when the server's list for the address the
 * click wrote (tab and sort, lib/desk/address.ts) is the table's, row for row. The read is a GET without a search
 * (desk-view.tsx readList; a search would POST, DEC-110), and its rows land after the click: until then a row's link can
 * still move under the pointer (the FLIP reorder), so a row is clicked only once this returns.
 */
async function deskRead(page: Page, click: () => Promise<void>): Promise<void> {
  const [res] = await Promise.all([
    page.waitForResponse((r) => {
      const asked = new URL(r.url());
      const shown = new URL(page.url());
      return (
        asked.pathname === "/api/desk" &&
        r.ok() &&
        asked.searchParams.get("tab") === shown.searchParams.get("tab") &&
        asked.searchParams.get("sort") === shown.searchParams.get("sort")
      );
    }),
    click(),
  ]);
  const order = ((await res.json()) as { items: { idea_id: string }[] }).items.map((i) => i.idea_id);
  await expect
    .poll(() =>
      page
        .getByRole("main")
        .locator("tbody tr[data-row]")
        .evaluateAll((rows) => rows.map((r) => r.getAttribute("data-row"))),
    )
    .toEqual(order);
}

/** Every address the page asks for, so a step can check the search words never appear in one (DEC-110). */
function recordRequests(page: Page): string[] {
  const urls: string[] = [];
  page.on("request", (request) => {
    const url = request.url();
    try {
      urls.push(decodeURIComponent(url));
    } catch {
      urls.push(url);
    }
  });
  return urls;
}

step(
  "J-BROWSE/1",
  "S-07",
  "My ideas: the tab and sort are kept in the URL and the search in the tab's memory, so a reload shows the same list (DEC-110)",
  { needs: ["S-07", "P-ROUTES"] },
  async ({ page }) => {
    const t5 = await seeded("T5");
    const asked = recordRequests(page);
    await signInAs(page, "tanvi");
    await page.goto("/my-ideas");
    await expect(page.getByRole("heading", { level: 1, name: "My ideas" })).toBeVisible();
    await page.getByRole("tab", { name: /^Yours/ }).click();
    await page.getByRole("button", { name: "Date shared" }).click();
    await search(page);
    await expect(rowLink(page, t5.title)).toBeVisible();
    carried.list = new URL(page.url()).pathname + new URL(page.url()).search;

    await page.reload();
    await expectListState(page);
    await expect(rowLink(page, t5.title)).toBeVisible();
    // DEC-110: search words never leave the tab, so no address the page used carries them.
    expect(asked.filter((url) => url.toLowerCase().includes(SEARCH.toLowerCase()))).toEqual([]);
  },
);

step(
  "J-BROWSE/2",
  "S-06",
  "Opening a row lands on the idea, whose breadcrumb names the list it came from",
  { needs: ["S-07", "S-06", "P-ROUTES"], after: ["J-BROWSE/1"] },
  async ({ page }) => {
    const t5 = await seeded("T5");
    await signInAs(page, "tanvi");
    await page.goto(listUrl());
    await rowLink(page, t5.title).click();
    await page.waitForURL(new RegExp(`${esc(ideaUrl(t5))}$`));
    await expect(page.getByRole("heading", { level: 1, name: t5.title })).toBeVisible();
    await expect(page.getByRole("link", { name: /^My ideas/ }).first()).toBeVisible();
  },
);

step(
  "J-BROWSE/3",
  "S-07",
  "Back returns to the same tab, sort and search; the row opened has focus; Back where you were: Yours.",
  { needs: ["S-07", "S-06", "P-ROUTES"], after: ["J-BROWSE/1"] },
  async ({ page }) => {
    const t5 = await seeded("T5");
    await signInAs(page, "tanvi");
    await page.goto(listUrl());
    await search(page); // a fresh tab: the search lives in the tab's memory, not the URL (DEC-110)
    await rowLink(page, t5.title).click();
    await page.waitForURL(new RegExp(`${esc(ideaUrl(t5))}$`));
    await page.goBack();
    await expect.poll(() => new URL(page.url()).pathname + new URL(page.url()).search).toBe(listUrl());
    await expect(page.getByText("Back where you were: Yours.")).toBeVisible();
    await expectListState(page);
    await expect(rowLink(page, t5.title)).toBeFocused();
  },
);

step(
  "J-BROWSE/4",
  "S-R1",
  "The same on the review desk (tab, sort and the opened row) and in the Inbox (tab and the open item)",
  { needs: ["S-R1", "S-R2", "C-TABS", "C-SORTS", "S-H5", "C-INBOX-READER", "S-R3", "P-ROUTES"] },
  async ({ page, browser }, info) => {
    const z1 = await seeded("Z1");
    const t6 = await seeded("T6");
    await signInAs(page, "harish");
    await page.goto("/desk");
    await deskRead(page, () => page.getByRole("tab", { name: /^Waiting on the sharer/ }).click());
    await deskRead(page, () => page.getByRole("button", { name: "Decide by" }).click());
    await page.getByRole("link", { name: z1.title, exact: true }).first().click();
    await page.waitForURL(/\/desk\/ideas\//);
    await page.goBack();
    await expect(page.getByRole("tab", { name: /^Waiting on the sharer/, selected: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Decide by" })).toHaveAttribute("aria-pressed", "true");
    // J-BROWSE row 4, "the open item is restored": the row that was opened has focus again (S-R1.rules/4).
    await expect(page.getByRole("link", { name: z1.title, exact: true }).first()).toBeFocused();

    const context = await browser.newContext();
    const sharer = await context.newPage();
    try {
      await signInAs(sharer, "tanvi");
      await sharer.goto("/inbox");
      await sharer.getByRole("tab", { name: /^Needs you/ }).click();
      const item = sharer.getByRole("button", {
        name: new RegExp(`^The review desk asked you 3 questions, ${esc(t6.title)}, `),
      });
      await item.click();
      await sharer.getByRole("link", { name: "Answer the questions" }).click();
      await sharer.waitForURL(new RegExp(`${esc(ideaUrl(t6, "/answer"))}$`));
      await sharer.goBack();
      await expect(sharer.getByRole("tab", { name: /^Needs you/, selected: true })).toBeVisible();
      await expect(item).toHaveAttribute("aria-pressed", "true");
    } finally {
      await snap(sharer, info, "J-BROWSE/4", "S-H5", "tanvi");
      await context.close();
    }
  },
);

step(
  "J-BROWSE/5",
  "S-09",
  "From the Wall: the idea's Back link says Back to the Wall and returns to the same sort and scroll",
  { needs: ["S-WALL", "S-09", "P-ROUTES"] },
  async ({ page }) => {
    const a1 = await seeded("A1");
    await signInAs(page, "tanvi");
    await page.goto("/wall");
    await expect(page.getByRole("heading", { level: 1, name: "Wall" })).toBeVisible();
    await page.getByRole("button", { name: "Popular", exact: true }).click();
    await expect(page.getByRole("button", { name: "Popular", exact: true })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    // Scroll on purpose, so the card sits near the top of the window and the page is well down from the top; the
    // click then needs no scrolling of its own, and the position to come back to is this one.
    const link = page.getByRole("link", { name: a1.title, exact: true }).first();
    await link.evaluate((el) => window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 120));
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(200);
    const y = await page.evaluate(() => window.scrollY);
    await link.click();
    await page.waitForURL(new RegExp(`${esc(ideaUrl(a1))}$`));
    await expect(page.getByRole("heading", { level: 1, name: a1.title })).toBeVisible();

    await page.getByRole("link", { name: "Back to the Wall" }).click();
    await page.waitForURL(/\/wall(\?|#|$)/);
    await expect(page.getByRole("button", { name: "Popular", exact: true })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(y - 80);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThan(y + 80);
  },
);

step(
  "J-BROWSE/6",
  "S-07",
  "A shared link to a filtered list reproduces the tab and sort, for what each person may see; the search stays behind (DEC-110)",
  { needs: ["S-07", "P-ROUTES"], after: ["J-BROWSE/1"] },
  async ({ page, browser }, info) => {
    const t5 = await seeded("T5");
    await signInAs(page, "tanvi");
    await page.goto(listUrl());
    await expectTabAndSort(page);
    await expect(page.getByRole("searchbox", { name: /^Search/ })).toHaveValue("");
    await expect(rowLink(page, t5.title)).toBeVisible();

    // Someone else opening the same link gets the same tab and sort over their own ideas: never Tanvi's, and never
    // Tanvi's search words (DEC-110).
    const context = await browser.newContext();
    const other = await context.newPage();
    try {
      await signInAs(other, "naveen");
      await other.goto(listUrl());
      await expect(other.getByRole("heading", { level: 1, name: "My ideas" })).toBeVisible();
      await expect(other.getByRole("searchbox", { name: /^Search/ })).toHaveValue("");
      await expect(other.getByRole("button", { name: "Date shared" })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      await expect(rowLink(other, t5.title)).toHaveCount(0);
    } finally {
      await snap(other, info, "J-BROWSE/6", "S-07", "naveen");
      await context.close();
    }
  },
);
