/**
 * S-02 Sign in and L-AUTH (S-02.states, L-AUTH.rules/1,2,4,5,8, BLD-E002). Single sign-on only while the email
 * route waits for InfoSec. Reduced motion is on so axe reads each state as it settles.
 */
import { randomUUID } from "node:crypto";

import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, expireSession, PERSONAS, signIn, switchIsOn, WEB_HOST } from "./helpers";

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
});

test("S-02.states Enter email, BLD-E002: while the email route is off, only single sign-on shows", async ({
  page,
}) => {
  test.skip(await switchIsOn("auth.email_code"), "the email route is on in this database");
  await page.goto("/sign-in");
  await expect(page.getByRole("heading", { level: 1, name: "Sign in to 1% Club" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Use single sign-on" })).toBeVisible();
  await expect(page.getByLabel("Work email")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Send code" })).toHaveCount(0);
  await expect(page.getByText("1% Club, a KFintech programme")).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});

test("BLD-E002, §7.6: the email-code routes answer 503 while auth.email_code is off", async ({ request }) => {
  test.skip(await switchIsOn("auth.email_code"), "the email route is on in this database");
  for (const path of ["/auth/code/send", "/auth/code/verify"]) {
    const res = await request.post(path, { data: { email: "someone@kfintech.example", code: "123456" } });
    expect(res.status(), path).toBe(503);
    expect(await res.json()).toMatchObject({ error: "paused", switch: "auth.email_code" });
  }
});

test("S-02.states Signing you in: names where the person lands next, and continues by itself", async ({
  page,
}) => {
  // Hold the page on this state: the start of single sign-on answers "no content", so the browser stays.
  await page.route("**/auth/sso/start**", (route) => route.fulfill({ status: 204 }));
  await page.goto("/sign-in?signing=1&to=%2Fshare");
  await expect(page.getByRole("heading", { level: 1, name: "Signing you in" })).toBeVisible();
  const next = page.getByRole("status").filter({ hasText: "Next: Share a problem" });
  await expect(next).toContainText("You land in the box with the cursor ready. Nothing to find again.");
  await expect(page.getByRole("link", { name: "Continue" })).toHaveAttribute("href", "/share");
  await expectNoSeriousAxeIssues(page);
});

test("S-02.states Could not sign in, L-AUTH.rules/8: a failure carries a reference and a way to try again", async ({
  page,
}) => {
  await page.goto("/auth/callback?error=temporarily_unavailable");
  await expect(page).toHaveURL(/\/sign-in\?failed=SSO-[0-9A-F]{4}&at=\d+$/);
  const ref = new URL(page.url()).searchParams.get("failed")!;
  await expect(page.getByRole("heading", { level: 1, name: "We couldn't sign you in" })).toBeVisible();
  // Next.js has its own route announcer, so find this alert by its words.
  const alert = page.getByRole("alert").filter({ hasText: "Your KFintech account didn't answer in time." });
  await expect(alert).toContainText("This is usually a short network hiccup on the office Wi-Fi or VPN.");
  await expect(alert).toContainText("Nothing you typed is lost.");
  await expect(page.getByText(new RegExp(`${ref}, \\d{1,2}:\\d{2} (am|pm)`))).toBeVisible();
  await expect(page.getByRole("link", { name: "Try again" })).toHaveAttribute("href", "/auth/sso/start");
  if (!(await switchIsOn("auth.email_code"))) {
    await expect(page.getByRole("link", { name: "get a code by email instead" })).toHaveCount(0);
  }
  await expectNoSeriousAxeIssues(page);
});

test("L-AUTH.rules/4: where the person was going survives the round trip to the identity provider", async ({
  page,
}) => {
  await page.goto("/wall");
  await expect(page).toHaveURL(/\/sign-in\?next=%2Fwall/);
  await page.getByRole("button", { name: "Use single sign-on" }).click();
  await page.locator('input[name="username"]').fill(PERSONAS.contributor);
  await page.locator('input[type="submit"]').click();
  await page.waitForURL((url) => url.host === WEB_HOST && !url.pathname.startsWith("/auth/"));
  if (new URL(page.url()).pathname === "/privacy-notice") {
    await page.getByRole("button", { name: /I have read this/ }).click();
  }
  await page.waitForURL((url) => url.pathname === "/wall");
});

test("S-02.states Session expired mid-draft, L-AUTH.rules/4,5: sign in again and carry on at the draft", async ({
  page,
}) => {
  await signIn(page, PERSONAS.contributor);
  await expireSession(page);
  const draft = `/share/${randomUUID()}`;
  await page.goto(draft);
  await expect(page).toHaveURL((url) => url.pathname === "/sign-in");
  await expect(page.getByRole("heading", { level: 1, name: "Sign in again to carry on" })).toBeVisible();
  await expect(
    page.getByText(
      "KFintech apps sign everyone out after 8 hours. Your draft is safe, exactly as you left it.",
    ),
  ).toBeVisible();
  await expect(page.getByText(/Trouble signing in\? Call the IT service desk/)).toBeVisible();
  await expectNoSeriousAxeIssues(page);
  await page.getByRole("button", { name: "Use single sign-on" }).click();
  await page.locator('input[name="username"]').fill(PERSONAS.contributor);
  await page.locator('input[type="submit"]').click();
  await page.waitForURL((url) => url.host === WEB_HOST && !url.pathname.startsWith("/auth/"));
  expect(new URL(page.url()).pathname).toBe(draft);
});

test("signed out of the app, the shell's sign-out leaves no expired-draft state behind", async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL(/\/signed-out/);
  await expect(page.getByRole("heading", { level: 1, name: "You have signed out" })).toBeVisible();
  await page.goto(`/sign-in?next=${encodeURIComponent(`/share/${randomUUID()}`)}`);
  await expect(page.getByRole("heading", { level: 1, name: "Sign in to 1% Club" })).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});
