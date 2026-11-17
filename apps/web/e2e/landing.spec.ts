/**
 * S-01 Landing (V-ACC.share/1, S-01.rules/1-5): the signed-out front door. Reduced motion is on so axe reads the
 * page as it settles (F-MOTION.reduced: every screen simply appears).
 */
import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, OIDC_AUTHORIZE, PERSONAS, signIn, WEB_HOST } from "./helpers";

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
});

const phone = (name: string) => name === "phone-360";

test("S-01.layout, S-01.rules/2,4,5: signed out, / is Landing; the promise comes from configuration; axe and 320 px", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(page).toHaveURL((url) => url.pathname === "/");
  await expect(
    page.getByRole("heading", { level: 1, name: "Every fix starts with someone who noticed." }),
  ).toBeVisible();
  await page.locator("body").press("Tab");
  await expect(page.getByRole("link", { name: "Skip to main content" })).toBeFocused();
  // rules/promises.md review.decide_by_working_days (BLD-A181), in each board's words
  await expect(
    page.getByText(
      phone(testInfo.project.name)
        ? "Within 5 working days, with a reason"
        : "The review desk, within 5 working days",
    ),
  ).toBeVisible();
  // details/summary: the first question is open, the rest closed; a question opens with the keyboard
  const first = page.locator("details").filter({ hasText: "Do I need to know how to fix it?" });
  await expect(first).toHaveAttribute("open", "");
  const ones = page.locator("details").filter({ hasText: "Who are the Ones?" });
  await expect(ones).not.toHaveAttribute("open", "");
  await ones.locator("summary").focus();
  await page.keyboard.press("Enter");
  await expect(ones).toHaveAttribute("open", "");
  await expect(page.getByText("Part of The Garage")).toBeVisible();
  // The Ones slab: the three most recent with public briefs, or none at all (S-01.rules/3)
  expect(await page.locator(".ld-one").count()).toBeLessThanOrEqual(3);
  // no shell when signed out
  await expect(page.getByRole("navigation", { name: "Main" })).toHaveCount(0);
  await expectNoSeriousAxeIssues(page);
});

test("S-01.rules/1: a signed-in person who opens / gets Home, not Landing", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/");
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Every fix starts with someone who noticed." })).toHaveCount(
    0,
  );
});

async function finishMockSignIn(page: Page, username: string) {
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[type="submit"]').click();
  await page.waitForURL((url) => url.host === WEB_HOST && !url.pathname.startsWith("/auth/"));
  if (new URL(page.url()).pathname === "/privacy-notice") {
    await page.getByRole("button", { name: /I have read this/ }).click();
    await page.waitForURL((url) => url.pathname !== "/privacy-notice");
  }
}

test("V-ACC.share/1 (AC1), L-AUTH.rules/1,4: Share a problem tries silent single sign-on and lands on Tell it, never on the sign-in form", async ({
  page,
}) => {
  const visited: URL[] = [];
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame()) visited.push(new URL(frame.url()));
  });
  await page.goto("/");
  await page.getByRole("link", { name: "Share a problem" }).first().click();
  await page.waitForURL((url) => url.href.startsWith(OIDC_AUTHORIZE));
  // Silent: the provider is asked to show nothing. The dev mock shows its form anyway, standing in for KFintech's
  // single sign-on answering at once.
  expect(new URL(page.url()).searchParams.get("prompt")).toBe("none");
  await finishMockSignIn(page, PERSONAS.contributor);
  await expect(page).toHaveURL((url) => url.pathname === "/share");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  // The only S-02 on the way was "Signing you in", never the form (S-02.purpose).
  const signInPages = visited.filter((u) => u.host === WEB_HOST && u.pathname === "/sign-in");
  expect(signInPages.length).toBeGreaterThan(0);
  for (const u of signInPages) expect(u.searchParams.get("signing")).toBe("1");
});
