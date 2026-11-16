/**
 * The idea canvas in the browser (B3): AT-B3-01 (quick capture submits; full canvas wording, "why we ask"; the
 * example links are retired, DEC-106, R16), AT-B3-02 (errors tied to fields), AT-B3-03 (browser half of the pattern check), AT-B3-04
 * (autosave and its pause), AT-B3-05 (strength meter guides, never blocks), AT-B3-09 (keyboard only, axe,
 * 200% zoom and 360 px). Signs in as the seeded contributor persona.
 */
import { expect, test, type Locator, type Page } from "@playwright/test";

import { MIC_HINT, QUESTIONS, QUICK_STRENGTH_NOTE } from "../src/lib/canvas/model";
import {
  confirmQuickCapture,
  expectNoSeriousAxeIssues,
  PERSONAS,
  restoreSwitches,
  setSwitch,
  signIn,
} from "./helpers";
import { withSwitchLock } from "./switch-lock";

const DETAILS =
  "Three people re-check every SIP form by hand for missing bank or nominee fields before keying it in.";

// Synthetic values built at run time; never literals that look like real identifiers.
const pick = (s: string) => s[Math.floor(Math.random() * s.length)]!;
const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
const syntheticPan = () =>
  pick(LETTERS) +
  pick(LETTERS) +
  pick(LETTERS) +
  "P" +
  pick(LETTERS) +
  String(1000 + Math.floor(Math.random() * 8999)) +
  pick(LETTERS);

async function start(page: Page, mode: "quick" | "full") {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/share");
  await page
    .getByRole("button", { name: mode === "quick" ? "Start a quick capture" : "Start the full canvas" })
    .click();
  await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
}

async function declare(page: Page) {
  for (const label of [/no investor or customer personal data/, /my own work/, /I accept the terms/]) {
    await page.getByRole("checkbox", { name: label }).check();
  }
}

test("quick capture: one box, files, one tick, and it shares (AT-B3-01, DEC-094)", async ({ page }) => {
  await start(page, "quick");
  await expect(page.getByRole("heading", { level: 1, name: "Quick capture" })).toBeVisible();
  // One visible question; the category waits, closed, under "Add more if you like".
  await expect(page.getByLabel(QUESTIONS.quick_noticed.label)).toBeVisible();
  await expect(page.getByText(QUESTIONS.quick_noticed.why, { exact: false })).toBeVisible();
  await expect(page.getByRole("group", { name: new RegExp(QUESTIONS.quick_value.label) })).toBeHidden();
  await expect(page.getByText("Add more if you like")).toBeVisible();
  // No score and no prompts for questions quick capture does not ask (BLD-C050).
  await expect(page.getByRole("complementary", { name: "What happens next" })).toHaveText(
    QUICK_STRENGTH_NOTE,
  );
  await expect(page.locator(".strength-score")).toHaveCount(0);
  // Files can be added here too, with the same checks as the full canvas.
  await expect(page.getByLabel("Attach a file (optional)")).toBeVisible();
  // One confirmation, not three.
  await expect(page.getByRole("checkbox", { name: /I accept the terms/ })).toHaveCount(0);
  await page.getByLabel(QUESTIONS.quick_noticed.label).fill(DETAILS);
  await expectNoSeriousAxeIssues(page);
  await page.getByRole("button", { name: "Share your idea" }).click();
  // Nothing ticked yet: the one error links to the one checkbox.
  const summary = page.getByRole("alert").filter({ hasText: "before you share" });
  await expect(summary).toBeFocused();
  await expect(summary.getByRole("link")).toHaveCount(1);
  await summary.getByRole("link", { name: "Please confirm this before you share." }).click();
  await expect(
    page.getByRole("checkbox", { name: /in this idea or its files, it is my own work/ }),
  ).toBeFocused();
  await confirmQuickCapture(page);
  await page.getByRole("button", { name: "Share your idea" }).click();
  await page.waitForURL(/\/done$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(/^Your idea is in: IDEA-\d{4}-\d{6}$/);
  await expectNoSeriousAxeIssues(page);
});

test("quick capture: the category is optional and can be chosen under Add more (DEC-094)", async ({
  page,
}) => {
  await start(page, "quick");
  await page.getByLabel(QUESTIONS.quick_noticed.label).fill(DETAILS);
  await page.getByText("Add more if you like").click();
  await page
    .getByRole("group", { name: new RegExp(QUESTIONS.quick_value.label) })
    .getByRole("radio", { name: "Cost saving" })
    .check();
  await confirmQuickCapture(page);
  await page.getByRole("button", { name: "Share your idea" }).click();
  await page.waitForURL(/\/done$/);
});

test("quick capture: the keyboard-mic tip follows capture.mic_hint (DEC-096)", async ({ browser }) => {
  await withSwitchLock("capture.mic_hint", async () => {
    const before = await setSwitch(browser, "capture.mic_hint", "on");
    try {
      const ctx = await browser.newContext();
      const page = await ctx.newPage();
      await start(page, "quick");
      await expect(page.getByText(MIC_HINT)).toBeVisible();
      await setSwitch(browser, "capture.mic_hint", "off");
      await expect
        .poll(
          async () => {
            await page.reload();
            return page.getByText(MIC_HINT).count();
          },
          { timeout: 20_000 },
        )
        .toBe(0);
      await expect(page.getByLabel(QUESTIONS.quick_noticed.label)).toBeVisible();
      await ctx.close();
    } finally {
      await restoreSwitches(browser, [["capture.mic_hint", before]]);
    }
  });
});

test("full canvas: six sections, exact questions and why-we-ask lines (AT-B3-01)", async ({ page }) => {
  await start(page, "full");
  for (const heading of [
    "1. What is it?",
    "2. Who does it touch?",
    "3. What's it worth to KFintech?",
    "4. Has anyone solved this?",
    "5. Your solution",
    "6. Your research",
    "Before you share",
  ]) {
    await expect(page.getByRole("heading", { level: 2, name: heading })).toBeVisible();
  }
  for (const key of [
    "kind",
    "one_line",
    "details",
    "segments",
    "frequency_or_reach",
    "today_alternative",
    "category",
    "play",
    "basis",
    "solved_elsewhere",
    "our_advantage",
    "approach",
    "needs",
    "risks",
  ] as const) {
    const q = QUESTIONS[key];
    await expect(page.getByText(q.label, { exact: false }).first(), key).toBeVisible();
    if (q.why) await expect(page.getByText(`Why we ask: ${q.why}`).first(), `${key} why`).toBeVisible();
  }
  await expect(page.getByRole("link", { name: /What good looks like/ })).toHaveCount(0);
  await expectNoSeriousAxeIssues(page);
});

test("required fields: errors are listed, tied to their fields and focusable (AT-B3-02)", async ({
  page,
}) => {
  await start(page, "full");
  await page.getByRole("button", { name: "Share your idea" }).click();
  const summary = page.getByRole("alert").filter({ hasText: "before you share" });
  await expect(summary).toBeFocused();
  await expect(summary.getByRole("link")).toHaveCount(7);
  const oneLine = page.getByLabel(/Say it in one line/);
  await expect(oneLine).toHaveAttribute("aria-invalid", "true");
  const describedBy = (await oneLine.getAttribute("aria-describedby")) ?? "";
  const errorId = describedBy.split(" ").find((id) => id.endsWith("-error"))!;
  await expect(page.locator(`#${errorId}`)).toHaveText("Say it in one line.");
  await summary.getByRole("link", { name: "Say it in one line." }).click();
  await expect(oneLine).toBeFocused();
  await expectNoSeriousAxeIssues(page);
});

test("personal data: highlighted as you type, autosave pauses, warn-only cases allowed (AT-B3-03, AT-B3-04)", async ({
  page,
}) => {
  await start(page, "full");
  const details = page.getByLabel(/^Tell us more/);
  await details.fill(`${DETAILS} Investor PAN ${syntheticPan()} called.`);
  await expect(page.getByText(/This looks like a PAN/)).toBeVisible();
  await expect(details).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByRole("status").filter({ hasText: "Autosave is paused" })).toBeVisible();
  await details.fill(`${DETAILS} The Aadhaar on the form was masked as XXXX XXXX 1234.`);
  await expect(page.getByText(/This looks like/)).toHaveCount(0);
  await expect(page.getByRole("status").filter({ hasText: /Draft saved at/ })).toBeVisible({
    timeout: 10_000,
  });
  await details.fill(`${DETAILS} Ask someone@kfintech.com for the sample.`);
  await expect(page.getByText(/That's fine for work contacts/)).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: /Draft saved at/ })).toBeVisible({
    timeout: 10_000,
  });
});

test("autosave keeps a draft you can come back to (AT-B3-04)", async ({ page }) => {
  await start(page, "full");
  const url = page.url();
  await page.getByLabel(/Say it in one line/).fill("Registrations slip because forms are re-checked by hand");
  await expect(page.getByRole("status").filter({ hasText: /Draft saved at/ })).toBeVisible({
    timeout: 10_000,
  });
  await page.goto("/share");
  await expect(page.getByRole("heading", { name: "Your drafts" })).toBeVisible();
  await page.goto(url);
  await expect(page.getByLabel(/Say it in one line/)).toHaveValue(
    "Registrations slip because forms are re-checked by hand",
  );
});

test("strength meter scores 0-5, names the next two additions, never blocks (AT-B3-05)", async ({ page }) => {
  await start(page, "full");
  const score = page.locator(".strength-score");
  await expect(score).toHaveText("0 of 5");
  await page.getByLabel(/Say it in one line/).fill("SIP forms are re-checked by hand");
  await page.getByLabel(/^Tell us more/).fill(`${DETAILS} ${DETAILS}`);
  await expect(score).toHaveText("1 of 5");
  await expect(page.getByRole("heading", { name: "Most useful next" })).toBeVisible();
  await expect(page.locator(".strength ol li")).toHaveCount(2);
  await page.getByRole("radio", { name: "A problem I face" }).check();
  await page
    .getByRole("group", { name: new RegExp(QUESTIONS.category.label) })
    .getByRole("radio", { name: "Cost saving" })
    .check();
  await declare(page);
  await page.getByRole("button", { name: "Share your idea" }).click(); // a weak canvas still shares
  await page.waitForURL(/\/done$/);
});

/** Press Tab until `target` has focus: proves it is reachable in order, by keyboard alone. */
async function tabTo(page: Page, target: Locator, max = 120) {
  for (let i = 0; i < max; i++) {
    if (await target.evaluate((el) => el === document.activeElement)) return;
    await page.keyboard.press("Tab");
  }
  throw new Error("not reachable by Tab");
}

test("the whole canvas can be completed by keyboard alone (AT-B3-09)", async ({ page }) => {
  await start(page, "full");
  await page.locator("h1").click(); // a starting point; everything after is keyboard only
  await tabTo(page, page.getByRole("radio", { name: "A problem I face" }));
  await page.keyboard.press("Space");
  await tabTo(page, page.getByLabel(/Say it in one line/));
  await page.keyboard.type("Registrations slip because forms are re-checked by hand");
  await tabTo(page, page.getByLabel(/^Tell us more/));
  await page.keyboard.type(DETAILS);
  await tabTo(page, page.getByRole("radio", { name: "Cost saving" }));
  await page.keyboard.press("Space");
  for (const label of [/no investor or customer personal data/, /my own work/, /I accept the terms/]) {
    await tabTo(page, page.getByRole("checkbox", { name: label }));
    await page.keyboard.press("Space");
  }
  await tabTo(page, page.getByRole("button", { name: "Share your idea" }));
  await page.keyboard.press("Enter");
  await page.waitForURL(/\/done$/);
});

test("content survives 200% zoom: no sideways scrolling (AT-B3-09)", async ({ page }) => {
  await page.setViewportSize({ width: 640, height: 900 }); // a 1280 px screen at 200%
  await start(page, "full");
  await page.getByRole("button", { name: "Share your idea" }).click(); // include the error state
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await expectNoSeriousAxeIssues(page);
});

test("research files: upload, plain-words check result, remove; axe clean (AT-B3-06/07 UI)", async ({
  page,
}) => {
  await start(page, "full");
  const picker = page.getByLabel("Attach a file (optional)");
  await picker.setInputFiles({
    name: "volumes.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("week,forms\nW1,120\nW2,131\n"),
  });
  const list = page.getByRole("list", { name: "Attached files" });
  await expect(list.getByText("Checked. Ready for the committee.")).toBeVisible({ timeout: 60_000 });

  await picker.setInputFiles({
    name: "sample.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(`step,example\nverify,${syntheticPan()}\n`),
  });
  await expect(
    list.getByText(/Not accepted: this file has what looks like a PAN \(row 2, column B\)/),
  ).toBeVisible({
    timeout: 60_000,
  });
  await expectNoSeriousAxeIssues(page);

  await picker.setInputFiles({
    name: "tool.exe",
    mimeType: "application/octet-stream",
    buffer: Buffer.from("MZ...."),
  });
  await expect(page.getByText(/We can't take this type of file/)).toBeVisible();

  await list.getByRole("button", { name: "Remove sample.csv" }).click();
  await expect(page.getByRole("status").filter({ hasText: "sample.csv is removed." })).toBeVisible();
  await expect(list.getByRole("listitem")).toHaveCount(1);
});
