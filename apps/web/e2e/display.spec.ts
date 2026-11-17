/**
 * The wall displays (L-DISPLAY): the launch screen (S-LAUNCH, /display/launch) and the office screen (S-OFFICE,
 * /display/office). For the display role, and admins until that role can be granted (BLD-A190). Every check of
 * the look runs axe and the 320 px reflow check (V-ACC.visual/4, BLD-A163); reduced motion means nothing moves
 * after first paint (V-ACC.visual/6). Timed parts run on Playwright's clock. Synthetic Ones only.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

/** The address the stack was started with: the environment, else the repo's .env, else the dev default. */
function configuredBaseUrl(): string {
  if (process.env.APP_BASE_URL) return process.env.APP_BASE_URL;
  try {
    const env = readFileSync(path.resolve(process.cwd(), "../../.env"), "utf8");
    const m = env.match(/^APP_BASE_URL=(\S+)/m);
    if (m?.[1]) return m[1];
  } catch {
    // no .env next to the repo: the dev default below
  }
  return "http://localhost:3000";
}

/** Animations still moving (finished ones that hold their last frame do not count). */
const running = (page: Page) =>
  page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running").length);
const allFinished = (page: Page) =>
  page.evaluate(() => document.getAnimations().every((a) => a.playState === "finished"));

test.describe("S-LAUNCH: the launch screen", () => {
  test.use({ reducedMotion: "reduce" });

  test("L-DISPLAY.launch/5: nobody but the display role and admins opens it", async ({ page }) => {
    await signIn(page, PERSONAS.reviewer);
    await page.goto("/display/launch");
    await expect(page).toHaveURL((url) => url.pathname === "/");
  });

  test("S-LAUNCH/2, V-ACC.visual/4: the operator frame, Start first, axe clean", async ({ page }) => {
    await signIn(page, PERSONAS.admin);
    await page.goto("/display/launch");
    await expect(page.getByText("1% Club · inauguration, Friday 20 November")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: "Launch screen" })).toBeVisible();
    await expect(
      page.getByText(/^For the lamp lighting on Friday 20 November\. Put this page/),
    ).toBeVisible();
    await expect(page.getByText(/^It runs for about thirty seconds, with a bell/)).toBeVisible();
    await expect(page.getByRole("button", { name: "Start" })).toBeFocused();
    await expect(page.getByRole("button", { name: "Full screen" })).toBeVisible();
    const beats = page.getByRole("list", { name: "What plays after Start" }).getByRole("listitem");
    await expect(beats).toHaveText([
      "0:00Black, and the bell",
      "0:04The spark rises",
      "0:08The two zeros arrive",
      "0:141% Club",
      "0:16The tagline",
      "0:30The invitation and QR code stay",
    ]);
    // The page behind the screen is out of the reading and tab order: display paths get no chrome (BLD-D011), and
    // anything else outside the display is inert (L-DISPLAY).
    await expect(page.locator("header:not([inert]):not([inert] *)")).toHaveCount(0);
    await expectNoSeriousAxeIssues(page);
  });

  test("S-LAUNCH/4, V-ACC.visual/6: with reduced motion Start shows the invitation at once, and nothing moves", async ({
    page,
  }) => {
    await signIn(page, PERSONAS.admin);
    await page.goto("/display/launch");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { level: 1, name: "1% Club" })).toBeVisible();
    await expect(page.getByText("1% spark. 99% sweat.", { exact: true })).toBeVisible();
    await expect(page.getByText("You bring the spark.", { exact: true })).toBeVisible();
    await expect(page.getByText("Scan the code to share your idea.", { exact: true })).toBeVisible();
    const qr = page.getByRole("img", { name: /^QR code for / });
    await expect(qr).toHaveAttribute("aria-label", `QR code for ${new URL(configuredBaseUrl()).toString()}`);
    expect(await running(page)).toBe(0);
    await expectNoSeriousAxeIssues(page);

    // S-LAUNCH/6: Escape does not stop it; a reload returns to the operator frame.
    await page.keyboard.press("Escape");
    await expect(page.getByRole("heading", { level: 1, name: "1% Club" })).toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: "Launch screen" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Start" })).toBeFocused();
  });

  test.describe("the timed sequence", () => {
    test.use({ reducedMotion: "no-preference" });

    test("S-LAUNCH/3, L-DISPLAY.launch/2: each beat in order, to the invitation, which stays", async ({
      page,
    }) => {
      await signIn(page, PERSONAS.admin);
      await page.clock.install();
      await page.goto("/display/launch");
      await page.getByRole("button", { name: "Start" }).click();

      // Nothing is in the reading order before its moment.
      await expect(page.getByRole("heading", { level: 1, name: "1% Club" })).toHaveCount(0);
      await expect(page.locator(".dl-spark")).not.toHaveClass(/is-on/);

      await page.clock.runFor(4_100); // 0:04 the spark rises
      await expect(page.locator(".dl-spark")).toHaveClass(/is-on/);
      await expect(page.locator(".dl-zero").first()).not.toHaveClass(/is-on/);
      await page.keyboard.press("Escape"); // leaves full screen only (S-LAUNCH/6): the sequence carries on

      await page.clock.runFor(4_000); // 0:08 the two zeros
      await expect(page.locator(".dl-zero").first()).toHaveClass(/is-on/);
      await expect(page.getByRole("heading", { level: 1, name: "1% Club" })).toHaveCount(0);

      await page.clock.runFor(6_000); // 0:14 the name
      await expect(page.getByRole("heading", { level: 1, name: "1% Club" })).toBeVisible();
      await expect(page.locator(".dl-tagline")).toHaveAttribute("aria-hidden", "true");

      await page.clock.runFor(2_000); // 0:16 the tagline
      await expect(page.locator(".dl-tagline")).not.toHaveAttribute("aria-hidden", "true");
      await expect(page.getByRole("img", { name: /^QR code for/ })).toHaveCount(0);

      await page.clock.runFor(13_000); // 0:29 the QR frame draws; the invitation lands at 0:30 and stays
      await expect(page.getByRole("img", { name: /^QR code for/ })).toBeVisible();
      await expect(page.getByText("You bring the spark.", { exact: true })).toBeVisible();
      await page.clock.runFor(60_000);
      await expect(page.getByText("You bring the spark.", { exact: true })).toBeVisible();

      // CSS animations run on real time, not the test clock: let the builds finish before checking contrast.
      await expect.poll(() => allFinished(page), { timeout: 10_000 }).toBe(true);
      await expectNoSeriousAxeIssues(page);
    });
  });
});

/** Three synthetic Ones the refresh brings in (numbers no seeded One wears). */
const SYNTHETIC = {
  paused: false,
  ones: [
    {
      number: 991,
      first_name: "Asha",
      name: "Asha Test",
      tier: 4,
      tier_name: "Blaze",
      tier_colour: "#FF0000",
    },
    {
      number: 992,
      first_name: "Vikram",
      name: "Vikram Test",
      tier: 2,
      tier_name: "Glow",
      tier_colour: "#FF4313",
    },
    { number: 993, first_name: null, name: null, tier: 7, tier_name: "Star", tier_colour: "#1E46D9" },
  ].map((o, k) => ({
    ...o,
    induction_no: 9001 + k,
    flag: k === 0 ? "founding" : "one",
    brief: "Synthetic test: a reconciliation check every team uses.",
    figure: "40 hours a month given back.",
  })),
};

test.describe("S-OFFICE: the office screen", () => {
  test.use({ reducedMotion: "reduce" });

  test("L-DISPLAY.office/1: nobody but the display role and admins opens it", async ({ page }) => {
    await signIn(page, PERSONAS.contributor);
    await page.goto("/display/office");
    await expect(page).toHaveURL((url) => url.pathname === "/");
    expect((await page.request.get("/api/display/office")).status()).toBe(403);
  });

  test("S-OFFICE/1-2, V-ACC.visual/4: the Ones as they are now, no chrome, axe clean", async ({ page }) => {
    await signIn(page, PERSONAS.admin);
    // 503 while `ones.public` is off (the route's kill switch, non-negotiable 9): the screen then rests.
    const api = await page.request.get("/api/display/office");
    expect([200, 503]).toContain(api.status());
    const data = (api.status() === 200 ? await api.json() : { paused: true, ones: [] }) as {
      paused: boolean;
      ones: unknown[];
    };
    await page.goto("/display/office");
    await expect(page.getByRole("region", { name: "The Ones, in the sky" })).toBeVisible();
    await expect(page.getByText("1% Club · KFintech")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: "The Ones" })).toBeVisible();
    await expect(page.getByText("1% spark. 99% sweat.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Pause the screen" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Full screen" })).toBeVisible();
    await expect(page.locator("header:not([inert]):not([inert] *)")).toHaveCount(0);
    if (!data.paused && data.ones.length) {
      await expect(page.getByText(`1 of ${data.ones.length}`)).toBeVisible();
      await expect(page.getByRole("list", { name: "The Ones" }).getByRole("listitem")).toHaveCount(
        data.ones.length,
      );
    }
    await expectNoSeriousAxeIssues(page);
  });

  test("S-OFFICE/5, L-DISPLAY.office/2 and /4: refreshes without a reload, rotates with reduced motion, nothing moves, Pause holds it", async ({
    page,
  }) => {
    await signIn(page, PERSONAS.admin);
    await page.route("**/api/display/office", (route) => route.fulfill({ json: SYNTHETIC }));
    await page.clock.install();
    await page.goto("/display/office?seconds=20");
    await page.evaluate(() => ((window as unknown as { __sameLoad: boolean }).__sameLoad = true));

    await page.clock.runFor(180_000); // the data refreshes every three minutes
    const lights = page.getByRole("list", { name: "The Ones" });
    await expect(lights.getByText("No. 991 · Asha")).toBeVisible();
    await expect(lights.getByText("No. 993", { exact: true })).toBeVisible(); // no name without their yes
    await expect(
      page.getByText("3 Ones so far. Each one shipped something that changed how we work."),
    ).toBeVisible();
    await expect(page.getByText("1 of 3")).toBeVisible();
    await expect(page.getByText("Asha Test", { exact: true })).toBeVisible();
    await expect(page.getByText("Founding One", { exact: true })).toBeVisible();
    await expect(page.getByText("Number 991")).toBeAttached();
    expect(await page.evaluate(() => (window as unknown as { __sameLoad?: boolean }).__sameLoad)).toBe(true);

    await page.clock.runFor(20_000);
    await expect(page.getByText("2 of 3")).toBeVisible();
    await expect(page.locator(".do-bub.is-on")).toHaveText("No. 992 · Vikram");
    expect(await running(page)).toBe(0);
    await expectNoSeriousAxeIssues(page);

    await page.getByRole("button", { name: "Pause the screen" }).click();
    await expect(page.getByRole("button", { name: "Play the screen" })).toBeVisible();
    await page.clock.runFor(60_000);
    await expect(page.getByText("2 of 3")).toBeVisible();
    await page.getByRole("button", { name: "Play the screen" }).click();
    await page.clock.runFor(20_000);
    await expect(page.getByText("3 of 3")).toBeVisible();
  });
});
