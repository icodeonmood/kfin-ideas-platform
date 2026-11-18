/**
 * The signed-in shell (C-SIDEBAR, C-PHONE-TABS; AT-B2-06, AT-B2-07). On desktop the sidebar shows "Share a problem",
 * Home, Wall and Inbox for everyone, plus Review desk for a reviewer and Ones Committee for the committee (S-R4, and the core committee until Monday); the
 * account menu holds the account links for the person's roles, the P shortcut and Sign out. On a phone the tab bar is
 * Home, My ideas, Share, Wall and Inbox for everyone. axe reports no serious or critical issues on the shell pages;
 * every item works by keyboard with a visible focus ring.
 * Needs `make seed` (personas) and the running stack.
 */
import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { Client } from "pg";

import {
  expectNoSeriousAxeIssues,
  navLabels,
  openAccountMenu,
  PERSONAS,
  PHONE_TABS,
  signIn,
} from "./helpers";

const BASE = ["Share a problem", "Home", "Find your crew", "Wall", "Inbox"];
const isPhone = (info: TestInfo) => info.project.name === "phone-360";

test.describe("C-SIDEBAR and C-PHONE-TABS: the shell by role (AT-B2-06)", () => {
  const cases: Array<[keyof typeof PERSONAS, string[]]> = [
    ["contributor", BASE],
    ["reviewer", [...BASE, "Review desk"]],
    ["core", [...BASE, "Ones Committee"]], // committee_window until the old roles go on Monday (BLD-B238)
    ["admin", BASE],
  ];
  for (const [persona, expected] of cases) {
    test(`C-SIDEBAR.anatomy: ${persona} sees the items for their roles`, async ({ page }, info) => {
      await signIn(page, PERSONAS[persona]);
      expect(await navLabels(page)).toEqual(isPhone(info) ? PHONE_TABS : expected);
    });
  }

  test("C-SIDEBAR.rules/1: the current page is marked, and Home only on its own path", async ({ page }) => {
    await signIn(page, PERSONAS.contributor);
    await page.goto("/wall");
    const nav = page.getByRole("navigation", { name: "Main" });
    await expect(nav.getByRole("link", { name: "Wall", exact: true })).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(nav.getByRole("link", { name: "Home", exact: true })).not.toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  test("S-H6.rules/3: the account menu holds the role's links, the P shortcut and Sign out", async ({
    page,
  }) => {
    await signIn(page, PERSONAS.admin);
    await openAccountMenu(page);
    await expect(page.getByRole("link", { name: "Admin" })).toHaveAttribute("href", "/admin");
    await expect(page.getByRole("link", { name: "Delivery" })).toBeVisible();
    const shortcut = page.getByRole("switch", { name: "The P shortcut" });
    await expect(shortcut).toHaveAttribute("aria-checked", "true");
    await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
    await expectNoSeriousAxeIssues(page);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: /^Your account, / })).toBeFocused();
    await expect(page.getByRole("button", { name: "Sign out" })).toHaveCount(0);
  });

  test("C-SIDEBAR.fold: the sidebar folds to icons, names each icon, and remembers", async ({
    page,
  }, info) => {
    test.skip(isPhone(info), "the sidebar is a desktop control");
    await signIn(page, PERSONAS.contributor);
    await page.getByRole("button", { name: "Fold the side bar" }).click();
    const open = page.getByRole("button", { name: "Open the side bar" });
    await expect(open).toHaveAttribute("aria-expanded", "false");
    // Folded, My ideas joins the icons and every item keeps its name for a screen reader.
    await expect(
      page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "My ideas" }),
    ).toBeVisible();
    await expectNoSeriousAxeIssues(page);
    await page.reload();
    await expect(open).toBeVisible();
    await open.click();
    await expect(page.getByRole("button", { name: "Fold the side bar" })).toBeVisible();
  });

  test("F-A11Y.shortcuts: P opens Share a problem, but not while typing", async ({ page }, info) => {
    test.skip(isPhone(info), "the P shortcut is for a keyboard at a desk");
    await signIn(page, PERSONAS.contributor);
    await page.goto("/wall");
    // The shortcut listens once the page has hydrated; press again until it has.
    await expect(async () => {
      await page.keyboard.press("p");
      await page.waitForURL((url) => url.pathname === "/share", { timeout: 1_000 });
    }).toPass({ timeout: 15_000 });
  });

  test("C-PHONE-TABS, F-SPACE.shell: a phone gives the page its full width whatever the saved fold", async ({
    page,
  }, info) => {
    test.skip(!isPhone(info), "the sidebar's width applies on a desk");
    await signIn(page, PERSONAS.contributor);
    await page.goto("/wall");
    const main = page.locator("main#main");
    // "auto" is the first visit (no choice yet); "folded" and "open" are a choice saved on a desk.
    for (const fold of ["auto", "folded", "open"]) {
      await page.evaluate((f) => document.documentElement.setAttribute("data-fold", f), fold);
      await expect
        .poll(async () => (await main.boundingBox())?.x ?? Infinity, {
          message: `main's left edge, fold ${fold}`,
        })
        .toBeLessThanOrEqual(24);
    }
  });
});

async function tabTo(page: Page, target: ReturnType<Page["locator"]>) {
  await page.locator("body").press("Tab");
  for (
    let presses = 0;
    presses < 80 && !(await target.evaluate((el) => el === document.activeElement));
    presses++
  ) {
    await page.keyboard.press("Tab");
  }
  await expect(target).toBeFocused();
}

test("every shell item works by keyboard with a visible focus ring (AT-B2-07)", async ({ page }) => {
  test.setTimeout(90_000);
  await signIn(page, PERSONAS.reviewer);
  const items = page.getByRole("navigation", { name: "Main" }).locator(":is(.sb-new, .sb-i, .ptab):visible");
  const hrefs = await items.evaluateAll((els) => els.map((el) => el.getAttribute("href") ?? ""));
  expect(hrefs.length).toBeGreaterThanOrEqual(5);
  for (const href of hrefs) {
    await page.goto("/");
    const target = page
      .getByRole("navigation", { name: "Main" })
      .locator(`:is(.sb-new, .sb-i, .ptab)[href="${href}"]`);
    await tabTo(page, target);
    const ring = await target.evaluate((el) => {
      const s = getComputedStyle(el);
      return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) };
    });
    expect(ring.style).not.toBe("none");
    expect(ring.width).toBeGreaterThanOrEqual(2);
    await page.keyboard.press("Enter");
    await page.waitForURL((url) => url.pathname === href);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    // A task screen on a phone swaps the tab bar for its dock; everywhere else the item is marked current.
    const after = page
      .getByRole("navigation", { name: "Main" })
      .locator(`:is(.sb-new, .sb-i, .ptab)[href="${href}"]:visible`);
    if (await after.count()) await expect(after).toHaveAttribute("aria-current", "page");
  }
});

test.describe("axe on the shell pages (AT-B2-07)", () => {
  const pages: Array<[keyof typeof PERSONAS, string[]]> = [
    ["contributor", ["/", "/share", "/my-ideas", "/wall", "/inbox"]],
    ["reviewer", ["/desk"]], // S-R1; S-R4 has its axe run in review-desk.spec.ts with the committee role
    ["core", ["/desk", "/committee"]],
    ["admin", ["/admin"]],
  ];
  for (const [persona, paths] of pages) {
    test(`${persona}: ${paths.join(" ")}`, async ({ page }) => {
      // Four pages with axe, and the contributor persona's My ideas grows with every dev run: about 20 s alone,
      // over 30 s when the whole suite runs in parallel.
      test.setTimeout(60_000);
      await signIn(page, PERSONAS[persona]);
      for (const path of paths) {
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await expectNoSeriousAxeIssues(page);
      }
    });
  }

  test("public pages: sign in and Landing (S-01, S-02)", async ({ page }) => {
    for (const path of ["/sign-in", "/"]) {
      await page.goto(path);
      await expectNoSeriousAxeIssues(page);
    }
  });
});

test("first sign-in shows the privacy notice, then the shell (AT-B2-01 in the browser)", async ({ page }) => {
  const id = `SYN-E${Date.now().toString(36).toUpperCase()}`;
  await page.goto("/sign-in");
  await page.getByRole("button", { name: "Use single sign-on" }).click();
  await page.locator('input[name="username"]').fill(id);
  await page.locator('textarea[name="claims"]').fill(
    JSON.stringify({
      employeeId: id,
      email: `${id.toLowerCase()}@kfintech.example`,
      name: "Synthetic Newcomer",
    }),
  );
  await page.locator('input[type="submit"]').click();
  await page.waitForURL(/\/privacy-notice/);
  await expect(
    page.getByRole("heading", { level: 1, name: /How 1% Club uses your information/ }),
  ).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  await expectNoSeriousAxeIssues(page);
  await page.getByRole("button", { name: /I have read this/ }).click();
  await page.waitForURL((url) => url.pathname === "/home"); // Home is S-03 at /home (BLD-C143)
  expect(await navLabels(page)).toEqual(isPhone(test.info()) ? PHONE_TABS : BASE);
});

// S-R4, A9: the pack's committee persona (manoj in the journeys' seed). `make seed`, all CI loads, has no SYN-10004 at
// all, and the mock IdP sends no email without claims, so a bare sign-in was refused (no_email) and the page sent the
// test to sign in. The claims are the 1pc seed's own for Manoj (club_seed.py), so the same person signs in either
// way: the seed's row, found by employee ID, or one made on this first sign-in. The role is given for the test and
// taken back after it (grants are read on every request). The 1pc seed already gives SYN-10004 `committee` for
// J-COMMITTEE, so only a grant this test inserted is taken back: the insert returns its id, and `finally` deletes that
// one row, never the seed's. Desktop only: on a phone the role items live in the account menu.
test("S-R4, J-COMMITTEE/1: the committee role sees Ones Committee in the sidebar, and its page passes axe (C-SIDEBAR.anatomy)", async ({
  page,
}, info) => {
  test.skip(isPhone(info), "the sidebar is desktop's");
  const DATABASE_URL =
    process.env.E2E_DATABASE_URL || "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable";
  const run = async (sql: string, params: unknown[]): Promise<Array<{ id: string }>> => {
    const c = new Client({ connectionString: DATABASE_URL });
    await c.connect();
    try {
      return (await c.query<{ id: string }>(sql, params)).rows;
    } finally {
      await c.end();
    }
  };
  await signIn(page, "SYN-10004", {
    employeeId: "SYN-10004",
    email: "manoj.agarwal.1pc@kfintech.example",
    name: "Manoj Agarwal",
  });
  const meRes = await page.request.get("/api/me");
  expect(meRes.ok(), "SYN-10004 is signed in").toBe(true);
  const me = (await meRes.json()) as { email: string };
  const added = await run(
    "INSERT INTO role_grants (user_id, role) SELECT u.id, 'committee' FROM users u WHERE u.email = $1 AND NOT " +
      "EXISTS (SELECT 1 FROM role_grants g WHERE g.user_id = u.id AND g.role = 'committee' AND g.valid_to IS NULL) " +
      "RETURNING id::text AS id",
    [me.email],
  );
  try {
    await page.goto("/committee");
    await expect(page.getByRole("heading", { level: 1, name: "Ones Committee" })).toBeVisible();
    expect(await navLabels(page)).toEqual([...BASE, "Ones Committee"]);
    await expectNoSeriousAxeIssues(page);
  } finally {
    const mine = added[0];
    if (mine) await run("DELETE FROM role_grants WHERE id = $1::bigint", [mine.id]);
  }
});

test("people without the role are sent home from Review and Admin", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  for (const path of ["/review", "/admin", "/committee"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/home$/);
  }
});

test("an admin can switch a feature off and on with a reason, and it is shown as text", async ({ page }) => {
  await signIn(page, PERSONAS.admin);
  await page.goto("/admin");
  const row = page.getByRole("row", { name: /matching\.show/ });
  await expect(row.getByText("On", { exact: true })).toBeVisible();

  await row.getByRole("button", { name: "Switch off: matching.show" }).click();
  await row.getByRole("button", { name: "Switch off", exact: true }).click();
  await expect(row.getByText(/at least 10 characters/)).toBeVisible(); // reason required, error tied to the field
  await row.getByLabel("Reason for this change").fill("e2e test: kill switch round trip");
  await row.getByRole("button", { name: "Switch off", exact: true }).click();
  await expect(row.getByText("Off", { exact: true })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "matching.show is now off" })).toBeVisible();

  await row.getByRole("button", { name: "Switch on: matching.show" }).click();
  await row.getByLabel("Reason for this change").fill("e2e test: kill switch round trip done");
  await row.getByRole("button", { name: "Switch on", exact: true }).click();
  await expect(row.getByText("On", { exact: true })).toBeVisible();
});

test("sign out ends the session", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  await openAccountMenu(page);
  await page.getByRole("button", { name: "Sign out" }).click();
  // S-01 Landing (BLD-A179). Signed in, "/" is Home, so wait for Landing's own heading, not the address.
  await expect(
    page.getByRole("heading", { level: 1, name: "Every fix starts with someone who noticed." }),
  ).toBeVisible();
  await page.goto("/my-ideas");
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fmy-ideas/);
});
