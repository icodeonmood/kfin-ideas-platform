import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, settleMotion, signIn } from "./helpers";

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

/**
 * QA ONLY, lane D's branch d/qa-train25-1, never merged: BLD-C243 on train 25 (9107c0bf). Home's "Tap to start
 * speaking" hint goes while the picker is open (the prompt carries `picking`, no :has()) and comes back after Escape
 * or after the "+" closes it, when nothing was typed; with words in the box it stays gone. Desk at 1440 and 1024, the
 * phone at 360 and 320. Screenshots and measures go to test-results/qa-shots. Synthetic data only.
 */
const QA_SHOTS = join(__dirname, "..", "test-results", "qa-shots");

test("QA (lane D, never merged): BLD-C243, Home's hint is gone over the open picker and back after Escape or close", async ({
  page,
}, info) => {
  test.setTimeout(240_000);
  mkdirSync(QA_SHOTS, { recursive: true });
  const log: Record<string, unknown> = {};
  const sizes =
    info.project.name === "phone-360"
      ? ([
          [360, 740],
          [320, 640],
        ] as const)
      : ([
          [1440, 900],
          [1024, 768],
        ] as const);
  await signInFresh(page, "P");
  const prompt = page.locator(".hm-prompt");
  const hint = prompt.locator(".vhint");
  const plus = prompt.getByRole("button", { name: "Add files, a folder or a link", exact: true });
  const picker = page.locator(".fpick.cpick");
  const words = page.getByRole("textbox", { name: "Say it in your own words" });
  const seen = async (name: string) => {
    await settleMotion(page);
    const g = await page.evaluate(() => {
      const p = document.querySelector(".hm-prompt");
      const h = p?.querySelector(".vhint");
      const r = h?.getBoundingClientRect();
      const k = document.querySelector(".fpick.cpick")?.getBoundingClientRect();
      return {
        picking: !!p?.classList.contains("picking"),
        hint: h ? getComputedStyle(h).display : "absent",
        hintBox: r ? { top: r.top, bottom: r.bottom, left: r.left, right: r.right } : null,
        picker: k ? { top: k.top, bottom: k.bottom, left: k.left, right: k.right } : null,
        sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    log[name] = g;
    await page.screenshot({ path: join(QA_SHOTS, `${name}.png`) });
    expect.soft(g.sideways, `${name}: no sideways scroll`).toBeLessThanOrEqual(0);
    return g;
  };

  for (const [w, h] of sizes) {
    const at = `c243-${w}x${h}`;
    await page.setViewportSize({ width: w, height: h });
    await page.goto("/home");
    await expect(words).toBeVisible();

    // At rest, nothing typed: the hint shows and the prompt is not picking
    await expect(hint).toBeVisible();
    const rest = await seen(`${at}-1-rest`);
    expect.soft(rest.picking, `${at}: not picking at rest`).toBe(false);

    // The picker open: the prompt picks, the hint is gone; axe
    await plus.click();
    await expect(plus).toHaveAttribute("aria-expanded", "true");
    await expect(picker).toBeVisible();
    await expect(prompt).toHaveClass(/(^|\s)picking(\s|$)/);
    await expect(hint).toBeHidden();
    const open = await seen(`${at}-2-open`);
    expect.soft(open.hint, `${at}: the hint is display none over the open picker`).toBe("none");
    await expectNoSeriousAxeIssues(page);

    // Escape: the picker goes, focus on the "+", the hint is back
    await picker.getByRole("button", { name: "Choose a folder", exact: true }).focus();
    await page.keyboard.press("Escape");
    await expect(picker).toHaveCount(0);
    await expect(plus).toBeFocused();
    await expect(prompt).not.toHaveClass(/(^|\s)picking(\s|$)/);
    await expect(hint).toBeVisible();
    await seen(`${at}-3-after-escape`);

    // The "+" opens and closes it: the hint goes and comes back
    await plus.click();
    await expect(picker).toBeVisible();
    await expect(hint).toBeHidden();
    await plus.click();
    await expect(picker).toHaveCount(0);
    await expect(prompt).not.toHaveClass(/(^|\s)picking(\s|$)/);
    await expect(hint).toBeVisible();
    await seen(`${at}-4-after-close`);

    // With words in the box the hint stays gone, picker open or closed
    await words.fill("Synthetic: branch staff retype the same nominee details twice.");
    await expect(hint).toHaveCount(0);
    await plus.click();
    await expect(picker).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(picker).toHaveCount(0);
    await expect(hint).toHaveCount(0);
    await seen(`${at}-5-typed`);
  }
  writeFileSync(join(QA_SHOTS, `c243-${info.project.name}.json`), JSON.stringify(log, null, 2));
});
