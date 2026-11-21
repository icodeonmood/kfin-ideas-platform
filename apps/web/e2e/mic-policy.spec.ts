import { expect, test } from "@playwright/test";

import { PERSONAS, signIn } from "./helpers";

/**
 * DEC-128, C-PROMPT.voice (BLD-C221): the microphone is allowed for the app's own origin on every page. A
 * Permissions-Policy is fixed when the document loads, and the app's links and `router.push` are client-side routes
 * that keep the first page's document. So a person who opens Home and follows "Share a problem" in the main
 * navigation must still be able to use the microphone on Share. Chromium's fake microphone, granted for this file's
 * own browser (as variants-voice.spec.ts); the contributor persona from `make seed`. Synthetic only: the stream is
 * opened and stopped at once, nothing is recorded or sent.
 */
test.use({
  permissions: ["microphone"],
  launchOptions: {
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
      "--autoplay-policy=no-user-gesture-required",
    ],
  },
});

type Marked = Window & { __micPolicyDocument?: string };

test("DEC-128, C-PROMPT.voice: from Home, Share a problem by a client-side route can still open the microphone", async ({
  page,
}) => {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/home");
  await expect(page.getByRole("navigation", { name: "Main" }).first()).toBeVisible();
  // Mark the document Home loaded: the route below must keep it, or this would test /share's own header instead.
  await page.evaluate(() => {
    (window as Marked).__micPolicyDocument = "home";
  });

  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "Share a problem", exact: true })
    .first()
    .click();
  await page.waitForURL((url) => url.pathname === "/share" || url.pathname.startsWith("/share/"));
  expect(await page.evaluate(() => (window as Marked).__micPolicyDocument)).toBe("home");

  const got = await page.evaluate(() =>
    navigator.mediaDevices.getUserMedia({ audio: true }).then(
      (s) => {
        s.getTracks().forEach((t) => t.stop());
        return "ok";
      },
      (e) => (e as { name?: string })?.name ?? String(e),
    ),
  );
  expect(got).toBe("ok");
});
