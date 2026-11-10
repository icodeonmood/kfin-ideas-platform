/**
 * AT-B2-06: navigation shows: everyone — Share an idea, My ideas, Wall, Messages (B6); review desk — plus Review; core
 * committee — plus Committee (Desk decisions while the committee flow is paused, BLD-227), Ones, Delivery and
 * Lenses; admin — plus Ones, Delivery, Lenses and Admin (the Ones console, DEC-040; delivery and lenses, BLD-115 to
 * BLD-122). My ideas links to committee decisions and appeals while the committee flow runs.
 * AT-B2-07: axe reports no serious or critical issues on the shell pages; every navigation item works by
 * keyboard with a visible focus ring.
 * Needs `make seed` (personas) and the running stack.
 */
import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, navLabels, PERSONAS, signIn, switchIsOn } from "./helpers";

const BASE = ["Share an idea", "My ideas", "Wall", "Messages"];

test.describe("navigation by role (AT-B2-06)", () => {
  // The core committee's second item follows the committee flow switch (BLD-227); it is on from day one (DEC-088).
  const deskOrCommittee = async () => ((await switchIsOn("committee.flow")) ? "Committee" : "Desk decisions");
  const cases: Array<[keyof typeof PERSONAS, () => Promise<string[]>]> = [
    ["contributor", async () => BASE],
    ["reviewer", async () => [...BASE, "Review"]],
    ["core", async () => [...BASE, await deskOrCommittee(), "Ones", "Delivery", "Lenses"]],
    ["admin", async () => [...BASE, "Ones", "Delivery", "Lenses", "Admin"]],
  ];
  // Another spec may flip the committee flow while this runs, and the menu reads switches through a 10-second cache:
  // compare the page and the database again (with a reload) until they agree.
  for (const [persona, expected] of cases) {
    test(`${persona} sees the menu for their roles`, async ({ page }) => {
      await signIn(page, PERSONAS[persona]);
      await expect(async () => {
        await page.reload();
        expect(await navLabels(page)).toEqual(await expected());
      }).toPass({ timeout: 20_000, intervals: [1_000, 2_000, 5_000] });
    });
  }

  test("My ideas links to committee decisions and appeals while the committee flow or appeals run", async ({
    page,
  }) => {
    await signIn(page, PERSONAS.contributor);
    const link = page.getByRole("link", { name: "Committee decisions on your ideas, and appeals" });
    let shown = false;
    await expect(async () => {
      await page.goto("/my-ideas");
      shown = (await switchIsOn("committee.flow")) || (await switchIsOn("appeals.filing"));
      await expect(link).toHaveCount(shown ? 1 : 0, { timeout: 1_000 });
    }).toPass({ timeout: 20_000, intervals: [1_000, 2_000, 5_000] });
    if (shown) {
      await expect(link).toHaveAttribute("href", "/appeals");
      await link.click();
      await expect(page.getByRole("heading", { level: 1, name: "Appeals" })).toBeVisible();
      await expectNoSeriousAxeIssues(page);
    }
  });
});

test("every navigation item works by keyboard with a visible focus ring (AT-B2-07)", async ({ page }) => {
  await signIn(page, PERSONAS.admin);
  const links = page.getByRole("navigation", { name: "Main" }).getByRole("link");
  // The admin sees every item but Review and Desk decisions: the four for everyone, the Ones console, Delivery,
  // Lenses and Admin.
  expect(await navLabels(page)).toEqual([...BASE, "Ones", "Delivery", "Lenses", "Admin"]);
  await expect(links.filter({ hasText: "Ones" })).toHaveAttribute("href", "/ones/console");
  const count = await links.count();
  expect(count).toBe(8);
  for (let i = 0; i < count; i++) {
    await page.goto("/");
    const target = links.nth(i);
    const href = await target.getAttribute("href");
    // Tab from the top of the page until this link has focus: proves it is reachable in order.
    await page.locator("body").press("Tab");
    for (
      let presses = 0;
      presses < 16 && !(await target.evaluate((el) => el === document.activeElement));
      presses++
    ) {
      await page.keyboard.press("Tab");
    }
    await expect(target).toBeFocused();
    const ring = await target.evaluate((el) => {
      const s = getComputedStyle(el);
      return { style: s.outlineStyle, width: parseFloat(s.outlineWidth) };
    });
    expect(ring.style).not.toBe("none");
    expect(ring.width).toBeGreaterThanOrEqual(2);
    await page.keyboard.press("Enter");
    await page.waitForURL((url) => url.pathname === href);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(
      page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: await target.innerText() }),
    ).toHaveAttribute("aria-current", "page");
  }
});

test.describe("axe on the shell pages (AT-B2-07)", () => {
  const pages: Array<[keyof typeof PERSONAS, string[]]> = [
    ["contributor", ["/", "/share", "/my-ideas", "/wall"]],
    ["reviewer", ["/review"]],
    ["core", ["/desk-decisions"]],
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

  test("public pages: sign in and signed out", async ({ page }) => {
    for (const path of ["/sign-in", "/signed-out"]) {
      await page.goto(path);
      await expectNoSeriousAxeIssues(page);
    }
  });
});

test("first sign-in shows the privacy notice, then the shell (AT-B2-01 in the browser)", async ({ page }) => {
  const id = `SYN-E${Date.now().toString(36).toUpperCase()}`;
  await page.goto("/sign-in");
  await page.getByRole("link", { name: "Sign in with your KFintech account" }).click();
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
  await page.waitForURL((url) => url.pathname === "/");
  expect(await navLabels(page)).toEqual(BASE);
});

test("people without the role are sent home from Review and Admin", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  for (const path of ["/review", "/admin", "/desk-decisions"]) {
    await page.goto(path);
    await expect(page).toHaveURL(/\/$/);
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
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL(/\/signed-out/);
  await page.goto("/my-ideas");
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fmy-ideas/);
});
