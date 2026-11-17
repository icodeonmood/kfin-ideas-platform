/**
 * S-07, My ideas (copy: reference/copy/MyIdeas.md, PhoneMyIdeas.md; data A-API.my-ideas): V-ACC.browse/1-2 and
 * V-ACC.visual/4 on My ideas, the states S-07 lists, its keyboard order and the phone board. The list is read on the
 * server, so the tests read Tanvi's ideas on the 1% Club seed (e2e/club.ts) and change nothing. The first-time empty
 * state needs no seed: a new synthetic person signs in and is removed afterwards. Lane G's J-BROWSE walks the same
 * hand-offs on main.
 */
import { expect, test, type Page } from "@playwright/test";

import { CLUB, clubLoaded, esc, IDEAS, NO_SEED, removePerson, seededIdea } from "./club";
import { expectNoSeriousAxeIssues, signIn } from "./helpers";

const isPhone = (name: string) => name.startsWith("phone");
/** A list change waits for the server's next view; generous, so a cold server never fails a step that works. */
const soon = expect.configure({ timeout: 15_000 });
let seed = false;

test.beforeAll(async () => {
  seed = await clubLoaded();
});

async function open(page: Page, path = "/my-ideas") {
  await signIn(page, CLUB.tanvi);
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1, name: "My ideas" })).toBeVisible();
}

/** A row's title link: "{title}", never the action's "{action}: {title}". */
const titleLink = (page: Page, title: string) =>
  page.getByRole("link", { name: new RegExp(`^${esc(title)}$`) }).first();

const here = (page: Page) => {
  const u = new URL(page.url());
  return u.pathname + u.search;
};

test.describe("S-07 on the 1% Club seed", () => {
  test.describe.configure({ timeout: 90_000 });
  test.beforeEach(() => test.skip(!seed, NO_SEED));

  test("S-07.layout, S-07.rows, V-ACC.visual/4: every idea with where it is and one next step; axe clean", async ({
    page,
  }, info) => {
    await open(page);
    await expect(page.getByRole("tab", { name: /^Yours/, selected: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: /^Teamed up/, selected: false })).toBeVisible();
    // Each action names its idea (S-07.rows): the questions go to S-R3, a withdrawn idea restores in place
    await expect(page.getByRole("link", { name: `Answer the questions: ${IDEAS.T6}` })).toHaveAttribute(
      "href",
      /\/ideas\/IDEA-\d{4}-\d{6}\/answer$/,
    );
    await expect(page.getByRole("button", { name: `Restore it: ${IDEAS.T10}` })).toBeVisible();
    await expect(page.getByRole("link", { name: `See where it is: ${IDEAS.T5}` })).toHaveAttribute(
      "href",
      /from=my-ideas&back=/,
    );
    await expect(page.getByRole("link", { name: `Read the decision: ${IDEAS.T9}` })).toBeVisible();
    await expect(page.getByText("Needs you", { exact: true }).first()).toBeVisible();
    if (isPhone(info.project.name)) {
      await expect(page.getByRole("radiogroup", { name: "Filter" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Sorted by latest activity" })).toBeVisible();
      await expect(page.getByRole("button", { name: "Copy link" })).toBeVisible();
    } else {
      await expect(
        page.getByText("Everything you’ve shared or teamed up on, where it is and what happens next."),
      ).toBeVisible();
      await expect(
        page.getByRole("searchbox", { name: "Search your ideas, or ask a question" }),
      ).toBeVisible();
      await expect(page.getByRole("button", { name: "Latest activity" })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
    }
    await expectNoSeriousAxeIssues(page);
  });

  test("S-07.return, V-ACC.browse/1 (J-BROWSE/1-3): filter, sort and search in the URL; Back restores them, the row is focused, washed and announced", async ({
    page,
  }, info) => {
    test.skip(
      isPhone(info.project.name),
      "the filter panel is the desktop board's; the phone's chips are below",
    );
    const t5 = await seededIdea("T5");
    await open(page);
    await page.getByRole("button", { name: "Filter" }).click();
    await page
      .getByRole("group", { name: "Narrow your search" })
      .getByRole("button", { name: /^With the review desk/ })
      .click();
    await soon.poll(() => here(page)).toBe("/my-ideas?filter=with_review_desk");
    // The filter panel stays open for another pick; Escape closes it (C-SEARCH)
    await page.keyboard.press("Escape");
    await expect(page.getByRole("group", { name: "Narrow your search" })).toBeHidden();
    await page.getByRole("button", { name: "Date shared" }).click();
    await soon.poll(() => here(page)).toBe("/my-ideas?filter=with_review_desk&sort=shared");
    const box = page.getByRole("searchbox", { name: /^Search/ });
    await box.fill("Redemption");
    await box.press("Enter");
    await soon.poll(() => here(page)).toBe("/my-ideas?filter=with_review_desk&sort=shared&q=Redemption");
    const list = here(page);
    await expect(titleLink(page, t5.title)).toBeVisible();
    await expect(
      page
        .getByRole("status")
        .filter({ hasText: /Redemption/ })
        .first(),
    ).toBeVisible();

    // Opening grows from the row; the idea's own address is clean once it has read where the person came from
    await titleLink(page, t5.title).click();
    await page.waitForURL(new RegExp(`/ideas/${esc(t5.ref)}$`));
    await expect(page.getByRole("heading", { level: 1, name: t5.title })).toBeVisible();

    await page.goBack();
    await soon.poll(() => here(page)).toBe(list);
    await expect(page.getByText("Back where you were: Yours.")).toBeVisible();
    await expect(titleLink(page, t5.title)).toBeFocused();
    await expect(page.locator(`[data-row="${t5.ref}"]`)).toHaveClass(/is-back/);
    await expect(page.getByRole("button", { name: "Remove the filter: With the review desk" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Date shared" })).toHaveAttribute("aria-pressed", "true");
    await expect(box).toHaveValue("Redemption");

    // The page's own way back (S-06's breadcrumb names the filter) lands on the same view and row
    await titleLink(page, t5.title).click();
    await page.waitForURL(new RegExp(`/ideas/${esc(t5.ref)}$`));
    await page.getByRole("link", { name: "My ideas, With the review desk" }).click();
    await page.waitForURL(/\/my-ideas\?/);
    await soon.poll(() => here(page)).toBe(list);
    await expect(titleLink(page, t5.title)).toBeFocused();
    await expect(page.getByText("Back where you were: Yours.")).toBeVisible();
  });

  test("S-07.return: Back returns to the same scroll position", async ({ page }) => {
    const t8 = await seededIdea("T8");
    await page.setViewportSize({ width: 1280, height: 600 });
    await open(page);
    const link = titleLink(page, t8.title);
    await link.evaluate((el) => window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY - 200));
    await soon.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(200);
    const top = await link.evaluate((el) => Math.round(el.getBoundingClientRect().top));
    await link.click();
    await page.waitForURL(new RegExp(`/ideas/${esc(t8.ref)}$`));
    await page.goBack();
    await expect(link).toBeFocused();
    await expect
      .poll(() => link.evaluate((el) => Math.round(el.getBoundingClientRect().top)))
      .toBeGreaterThan(top - 40);
    await expect
      .poll(() => link.evaluate((el) => Math.round(el.getBoundingClientRect().top)))
      .toBeLessThan(top + 40);
  });

  test("V-ACC.browse/2: a new sort re-orders the rows and is in the URL", async ({ page }, info) => {
    await open(page);
    const titles = () => page.locator(".mi-list .mi-t").allInnerTexts();
    const before = await titles();
    if (isPhone(info.project.name)) {
      await page.getByRole("button", { name: "Sorted by latest activity" }).click();
      await expect(page.getByRole("button", { name: "Sorted by date shared" })).toBeVisible();
      await soon.poll(() => here(page)).toBe("/my-ideas?sort=shared");
    } else {
      await page.getByRole("button", { name: "Stage", exact: true }).click();
      await expect(page.getByRole("button", { name: "Stage", exact: true })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
      await soon.poll(() => here(page)).toBe("/my-ideas?sort=stage");
    }
    await soon.poll(titles).not.toEqual(before);
    expect([...(await titles())].sort()).toEqual([...before].sort());
  });

  test("S-07.states filter, J-BROWSE/6: a filter with nothing in it says so and offers the way out", async ({
    page,
  }, info) => {
    await open(page, "/my-ideas?filter=shipped");
    await expect(page.getByRole("heading", { name: "Nothing shipped yet." })).toBeVisible();
    await expect(
      page.getByText("Ideas land here once they ship and their effect is measured."),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "See 1 in Teamed up" })).toBeVisible();
    if (isPhone(info.project.name)) {
      await expect(page.getByRole("radio", { name: /^Shipped/ })).toHaveAttribute("aria-checked", "true");
    }
    await expectNoSeriousAxeIssues(page);
    await page.getByRole("button", { name: "Show all ideas" }).click();
    await soon.poll(() => here(page)).toBe("/my-ideas");
    await expect(titleLink(page, IDEAS.T5)).toBeVisible();
  });

  test("S-07.states list: Teamed up shows colleagues' ideas, which open S-09 with Back to My ideas", async ({
    page,
  }, info) => {
    const r2 = await seededIdea("R2");
    await open(page);
    await page.getByRole("tab", { name: /^Teamed up/ }).click();
    await soon.poll(() => here(page)).toBe("/my-ideas?list=teamed");
    await expect(page.getByRole("tab", { name: /^Teamed up/, selected: true })).toBeVisible();
    await expect(page.getByText(/Rekha Saxena’s idea, you teamed up/)).toBeVisible();
    await expectNoSeriousAxeIssues(page);
    await page.getByRole("link", { name: `Open the idea: ${r2.title}` }).click();
    await page.waitForURL(new RegExp(`/ideas/${esc(r2.ref)}$`));
    await expect(page.getByRole("heading", { level: 1, name: r2.title })).toBeVisible();
    await page.getByRole("link", { name: "Back to My ideas" }).click();
    await soon.poll(() => here(page)).toBe("/my-ideas?list=teamed");
    await expect(page.getByRole("tab", { name: /^Teamed up/, selected: true })).toBeVisible();
    await expect(
      page.getByText(
        isPhone(info.project.name) ? /^Back where you were: All,/ : "Back where you were: Teamed up.",
      ),
    ).toBeVisible();
  });

  test("S-07.states view=Loading: three skeleton rows while the next view comes", async ({ page }) => {
    await open(page);
    // Hold the next view's server answer for a moment, so the loading state can be seen
    await page.route("**/my-ideas?**", async (route) => {
      if (route.request().headers()["rsc"]) await new Promise((r) => setTimeout(r, 1_500));
      await route.continue();
    });
    await page.getByRole("tab", { name: /^Teamed up/ }).click();
    await expect(page.getByRole("status").filter({ hasText: "Loading your ideas" })).toBeAttached();
    await expect(page.locator(".mi-panel .sk-row")).toHaveCount(3);
    await soon(page.getByRole("link", { name: /^Open the idea: / }).first()).toBeVisible();
    await expect(page.locator(".mi-panel .sk-row")).toHaveCount(0);
  });

  test("S-07 keyboard: search, Filter, the tabs, the sorts, then each row's title and action in reading order", async ({
    page,
  }, info) => {
    test.skip(isPhone(info.project.name), "the desktop board's order; the phone's chips are checked above");
    await open(page);
    await page.getByRole("searchbox", { name: /^Search/ }).focus();
    const seen: string[] = [];
    for (let i = 0; i < 18; i++) {
      await page.keyboard.press("Tab");
      seen.push(
        await page.evaluate(() => {
          const el = document.activeElement as HTMLElement | null;
          return `${el?.getAttribute("role") ?? el?.tagName.toLowerCase()}:${(el?.getAttribute("aria-label") ?? el?.textContent ?? "").trim()}`;
        }),
      );
    }
    const at = (re: RegExp) => seen.findIndex((s) => re.test(s));
    expect(at(/^button:Filter$/), seen.join(" | ")).toBeGreaterThanOrEqual(0);
    expect(at(/^tab:Yours/)).toBeGreaterThan(at(/^button:Filter$/));
    expect(at(/^button:Latest activity$/)).toBeGreaterThan(at(/^tab:Yours/));
    // The first row: its title, then its action, which names the idea
    const firstTitle = at(/^a:/);
    expect(firstTitle, seen.join(" | ")).toBeGreaterThan(at(/^button:Stage$/));
    expect(seen[firstTitle + 1]).toMatch(/^a:.+: /);
    // The tabs move with the arrow keys (C-TABS)
    await page.getByRole("tab", { name: /^Yours/ }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("tab", { name: /^Teamed up/ })).toBeFocused();
  });

  test("S-07.phone, J-BROWSE/3 (PhoneMyIdeas): chips with counts; Back says where you were", async ({
    page,
  }, info) => {
    test.skip(!isPhone(info.project.name), "PhoneMyIdeas");
    const t5 = await seededIdea("T5");
    await page.setViewportSize({ width: 390, height: 844 });
    await open(page);
    const chips = page.getByRole("radiogroup", { name: "Filter" });
    await expect(chips.getByRole("radio", { name: /^All\s*10$/ })).toHaveAttribute("aria-checked", "true");
    await chips.getByRole("radio", { name: /^With the desk/ }).click();
    await soon.poll(() => here(page)).toBe("/my-ideas?filter=with_review_desk");
    await expect(titleLink(page, t5.title)).toBeVisible();
    await titleLink(page, t5.title).click();
    await page.waitForURL(new RegExp(`/ideas/${esc(t5.ref)}$`));
    await page.goBack();
    await expect(page.getByText("Back where you were: With the desk, latest activity first.")).toBeVisible();
    await expect(titleLink(page, t5.title)).toBeFocused();
    await expectNoSeriousAxeIssues(page);
  });
});

test("S-07.states view=Empty (first time): nothing shared yet, and the way to share the first problem", async ({
  page,
}, info) => {
  const n = 17900 + (isPhone(info.project.name) ? 1 : 0);
  const email = `screens.${n}.1pc@kfintech.example`;
  try {
    await signIn(page, `SYN-${n}`, { email, name: "Screens Empty" });
    await page.goto("/my-ideas");
    await expect(page.getByRole("heading", { level: 1, name: "My ideas" })).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "Nothing shared yet" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Share your first problem" })).toHaveAttribute(
      "href",
      "/share",
    );
    if (isPhone(info.project.name)) {
      await expect(
        page.getByText(
          "Spot something that keeps going wrong? Say it in your own words, typed or spoken. It takes about two minutes.",
        ),
      ).toBeVisible();
    } else {
      await expect(
        page.getByText(
          "Spot something that keeps going wrong? Say it in your own words. It takes about two minutes, and you’ll see it here with where it is and what happens next.",
        ),
      ).toBeVisible();
      await expect(page.getByText("or press P anywhere")).toBeVisible();
    }
    await expect(page.getByRole("tablist")).toHaveCount(0);
    await expectNoSeriousAxeIssues(page);
  } finally {
    await removePerson(email);
  }
});
