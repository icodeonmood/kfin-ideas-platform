import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, signIn } from "./helpers";

/**
 * WF-02 on Home (S-03, C-PROMPT.voice; BLD-C220), against the local stack. The empty box's round button is the
 * microphone, a sound wave named "Tap to start speaking", with "Tap to start speaking" and "Not recording until you
 * do" beside it on a laptop and on a phone, as Home.dc.html and PhoneHome.dc.html draw them; axe clean. With words in
 * the box the round button sends again and the small microphone takes over. With the microphone refused, a tap shows
 * the blocked warning under the box and typing still works (as J-RECOVER/4 on Share).
 * Reduced motion keeps the hint from fading after its six seconds (compose.css), so the check never races the
 * animation. A finished note landing on S-04B needs a fake note from the speech service, which no e2e helper gives
 * yet; lane G's journey covers it. Chromium's fake microphone, granted for this file's own browser (as
 * variants-voice.spec.ts); a new synthetic person per run, so nothing seeded changes. Synthetic words only.
 */
test.use({
  permissions: ["microphone"],
  reducedMotion: "reduce",
  launchOptions: {
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
      "--autoplay-policy=no-user-gesture-required",
    ],
  },
});

const WORDS = "Synthetic: branch staff retype the same nominee details into two screens for every new folio.";

async function signInFresh(page: Page, tag: string) {
  const id = `SYN-E${tag}${Date.now().toString(36).toUpperCase()}`;
  await signIn(page, id, {
    employeeId: id,
    email: `${id.toLowerCase()}@kfintech.example`,
    name: "Synthetic Voicer",
  });
}

test("V-ACC S-03, C-PROMPT.voice: the empty box shows the round voice button and both hint lines; with words it sends again", async ({
  page,
}) => {
  await signInFresh(page, "V");
  await page.goto("/home");
  const round = page.getByRole("button", { name: "Tap to start speaking", exact: true });
  await expect(round).toBeVisible();
  const hint = page.locator(".hm-prompt .vhint");
  await expect(hint).toBeVisible();
  await expect(hint.locator("b")).toHaveText("Tap to start speaking");
  await expect(hint.locator("span")).toHaveText("Not recording until you do");
  await expectNoSeriousAxeIssues(page);

  await page.getByRole("textbox", { name: "Say it in your own words" }).fill(WORDS);
  await expect(round).toHaveCount(0);
  await expect(hint).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Continue to Share a problem" })).toBeVisible();
  // The small microphone reads "Say it instead" on a phone, as the phone boards draw it (BLD-C232, review nit 7).
  const phone = (page.viewportSize()?.width ?? 1440) <= 640;
  const small = phone ? "Say it instead" : "Speak instead";
  await expect(page.getByRole("button", { name: small, exact: true })).toBeVisible();
});

test("C-PROMPT.voice on Home: with the microphone refused, a tap shows the blocked warning and typing still works", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const refuse = async (): Promise<MediaStream> => {
      throw new DOMException("Permission denied", "NotAllowedError");
    };
    if (navigator.mediaDevices) navigator.mediaDevices.getUserMedia = refuse;
  });
  await signInFresh(page, "B");
  await page.goto("/home");
  await page.getByRole("button", { name: "Tap to start speaking", exact: true }).click();
  // C-PROMPT.voice "Blocked", in the laptop's or the phone's words (MIC_BLOCKED).
  await expect(
    page.getByRole("alert").filter({
      hasText: /(Your browser has blocked the microphone\.|The microphone is off for this app\.)/,
    }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Microphone blocked", exact: true })).toBeVisible();
  const box = page.getByRole("textbox", { name: "Say it in your own words" });
  await expect(box).toBeEditable();
  await box.fill(WORDS);
  await expect(page.getByRole("link", { name: "Continue to Share a problem" })).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});
