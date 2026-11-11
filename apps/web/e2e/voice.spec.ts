/**
 * Voice notes in quick capture (DEC-096): off, the panel says they are coming soon; on, a person records with the
 * keyboard, plays it back, turns it into text, and the text lands in the box (SPEECH_MODE=fake gives a fixed
 * sample sentence). Chromium's fake microphone stands in for a real one. capture.voice is put back as it was
 * found, under a lock so the two projects never flip it at the same time (BLD-155).
 */
import { expect, test, type Browser, type Page } from "@playwright/test";

import { QUESTIONS } from "../src/lib/canvas/model";
import { VOICE_COMING_SOON, VOICE_DONE, VOICE_NEW, VOICE_START } from "../src/app/share/[id]/voice-logic";
import { expectNoSeriousAxeIssues, PERSONAS, restoreSwitches, setSwitch, signIn } from "./helpers";
import { withSwitchLock } from "./switch-lock";

const FAKE_SAMPLE = "Branch staff type every change of bank form twice";

async function quickCapture(browser: Browser): Promise<Page> {
  const ctx = await browser.newContext({ permissions: ["microphone"] });
  const page = await ctx.newPage();
  await signIn(page, PERSONAS.contributor);
  await page.goto("/share");
  await page.getByRole("button", { name: "Start a quick capture" }).click();
  await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
  return page;
}

test.use({
  launchOptions: { args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] },
});

test("voice notes off: coming soon, no recorder, the box still works (DEC-096)", async ({ browser }) => {
  await withSwitchLock("capture.voice", async () => {
    const before = await setSwitch(browser, "capture.voice", "off");
    try {
      const page = await quickCapture(browser);
      const panel = page.getByRole("group", { name: "Or record a voice note" });
      await expect(panel.getByText(VOICE_COMING_SOON)).toBeVisible();
      await expect(panel.getByText(VOICE_NEW)).toBeVisible();
      await expect(panel.getByRole("button")).toHaveCount(0);
      await expect(page.getByLabel(QUESTIONS.quick_noticed.label)).toBeEditable();
      await expectNoSeriousAxeIssues(page);
      await page.context().close();
    } finally {
      await restoreSwitches(browser, [["capture.voice", before]]);
    }
  });
});

test("voice notes on: record by keyboard, play back, turn it into text in the box (DEC-096)", async ({
  browser,
}) => {
  test.setTimeout(180_000);
  await withSwitchLock("capture.voice", async () => {
    const before = await setSwitch(browser, "capture.voice", "on");
    try {
      const page = await quickCapture(browser);
      const panel = page.getByRole("group", { name: "Or record a voice note" });
      // The web app reads switches through a 10-second cache.
      await expect
        .poll(
          async () => {
            await page.reload();
            return panel.getByRole("button", { name: VOICE_START }).count();
          },
          { timeout: 20_000 },
        )
        .toBe(1);
      await expect(panel.getByText(VOICE_NEW)).toBeVisible();
      await panel.getByRole("button", { name: VOICE_START }).focus();
      await page.keyboard.press("Enter");
      const stop = panel.getByRole("button", { name: "Stop recording" });
      await expect(stop).toBeFocused();
      await expect(panel.getByRole("timer")).toContainText("of 3:00");
      await expect(
        page.getByRole("status").filter({ hasText: "Recording. You have up to 3 minutes." }),
      ).toBeAttached();
      await page.waitForTimeout(2_000);
      await page.keyboard.press("Enter");
      await expect(panel.getByLabel("Play back your voice note")).toBeVisible();
      const turn = panel.getByRole("button", { name: "Turn it into text" });
      await expect(turn).toBeFocused();
      await expectNoSeriousAxeIssues(page);
      await page.keyboard.press("Enter");
      // The visible note, not the live region that says the same thing.
      await expect(panel.locator("p.muted", { hasText: VOICE_DONE })).toBeVisible({ timeout: 120_000 });
      await expect(page.getByLabel(QUESTIONS.quick_noticed.label)).toHaveValue(new RegExp(FAKE_SAMPLE));
      await expect(panel.getByRole("button", { name: "Record another voice note" })).toBeFocused();
      await page.context().close();
    } finally {
      await restoreSwitches(browser, [["capture.voice", before]]);
    }
  });
});
