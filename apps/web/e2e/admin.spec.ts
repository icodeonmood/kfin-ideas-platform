/**
 * The minimal admin page (lane A; J-ONE steps 1, 2, 3 and 6; L-DECIDE.after, L-IMPACT, L-AUDIT; BLD-A210). It is
 * staff-facing but still WCAG 2.1 AA (non-negotiable 10): every part runs axe and the 320 px reflow check. Each part
 * shows only to the people who may use it; the server checks again (tests/unit/admin-routes.test.ts and the worker's
 * test_1pc_admin_programme.py cover the actions). These checks change nothing.
 */
import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

/**
 * What on the page reaches past a 320 px screen (F-SPACE.breakpoints, WCAG 1.4.10): the outermost such parts, named
 * by tag, class and their section's heading only. The shared reflow check says how far the page scrolls; this says
 * which part does it.
 */
async function pastTheScreen(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const main = document.querySelector("main");
    if (!main) return ["no main"];
    const edge = document.documentElement.clientWidth;
    const past = (el: Element) => {
      const box = el.getBoundingClientRect();
      return box.width > 0 && box.right > edge + 0.5 ? Math.round(box.right - edge) : 0;
    };
    const found: string[] = [];
    for (const el of main.querySelectorAll("*")) {
      const by = past(el);
      const parent = el.parentElement;
      if (!by || (parent && parent !== main && past(parent))) continue;
      const css =
        typeof el.className === "string" && el.className ? `.${el.className.split(" ").join(".")}` : "";
      const part = el.closest("section")?.querySelector("h2")?.textContent ?? "";
      found.push(`${el.tagName.toLowerCase()}${css}, ${by}px past, in "${part}"`);
    }
    return found.slice(0, 10);
  });
}

test("L-AUDIT, F-SPACE.breakpoints: an admin sees the programme, the experiments, the switches and roles; nothing passes a 320 px screen, and it passes axe", async ({
  page,
}) => {
  await signIn(page, PERSONAS.admin);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { level: 1, name: "Admin" })).toBeVisible();
  for (const name of [
    "Picked ideas: choose the build team", // J-ONE/1
    "Being built: mark shipped", // J-ONE/1
    "What shipped ideas changed", // J-ONE/2 and /6
    "The Ones", // J-ONE/3: Founding Ones and removal
    "Take an idea off the Wall", // DEC-106
    "Experiments", // L-AUDIT.flags
    "Kill switches",
    "Voice notes",
  ]) {
    await expect(page.getByRole("heading", { level: 2, name, exact: true })).toBeVisible();
  }
  // DEC-108: voice goes through Sarvam and is on at launch.
  await expect(page.getByText(/Voice notes are turned into text by Sarvam/)).toBeVisible();
  await expect(page.getByRole("heading", { level: 3, name: "S1" })).toBeVisible();
  // J-ONE/2 on the 1% Club seed: a figure saved in the seed's older form reads as words, never "NaN".
  await expect(page.locator("#impact")).not.toContainText("NaN");
  const size = page.viewportSize() ?? { width: 1280, height: 720 };
  await page.setViewportSize({ width: 320, height: size.height });
  try {
    await expect.poll(() => pastTheScreen(page), { timeout: 3_000 }).toEqual([]);
  } finally {
    await page.setViewportSize(size);
  }
  await expectNoSeriousAxeIssues(page);
});

test("DEC-106, C-FIELD-MSG.behaviour/3: an empty Founding One form says what is missing, tied to the field", async ({
  page,
}) => {
  await signIn(page, PERSONAS.admin);
  await page.goto("/admin");
  // Its own form: "Lead's work email" (choose a build team) and each experiment's "Work email" use the same words.
  const form = page.getByRole("form", { name: "Mark a Founding One" });
  await form.getByRole("button", { name: "Mark Founding One" }).click();
  const email = form.getByRole("textbox", { name: "Work email", exact: true });
  await expect(form.getByRole("alert")).toHaveText("Enter a work email.");
  await expect(email).toHaveAttribute("aria-invalid", "true");
  await expect(email).toHaveAccessibleDescription("Enter a work email.");
  await expectNoSeriousAxeIssues(page);
});

test("L-AUDIT.permissions: the review desk sees only Take off the Wall", async ({ page }) => {
  await signIn(page, PERSONAS.reviewer);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { level: 2, name: "Take an idea off the Wall" })).toBeVisible();
  for (const name of ["Picked ideas: choose the build team", "The Ones", "Experiments", "Kill switches"]) {
    await expect(page.getByRole("heading", { level: 2, name, exact: true })).toHaveCount(0);
  }
  await expectNoSeriousAxeIssues(page);
});
