/**
 * The minimal admin page (lane A; J-ONE steps 1, 2, 3 and 6; L-DECIDE.after, L-IMPACT, L-AUDIT; BLD-A210). It is
 * staff-facing but still WCAG 2.1 AA (non-negotiable 10): every part runs axe and the 320 px reflow check. Each part
 * shows only to the people who may use it; the server checks again (tests/unit/admin-routes.test.ts and the worker's
 * test_1pc_admin_programme.py cover the actions). These checks change nothing.
 */
import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

test("L-AUDIT: an admin sees the programme, the experiments, the switches and roles, and it passes axe", async ({
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
  await expectNoSeriousAxeIssues(page);
});

test("DEC-106: an empty Founding One form says what is missing, tied to the field", async ({ page }) => {
  await signIn(page, PERSONAS.admin);
  await page.goto("/admin");
  await page.getByRole("button", { name: "Mark Founding One" }).click();
  const email = page.getByRole("textbox", { name: "Work email" }).first();
  await expect(page.getByText("Enter a work email.")).toBeVisible();
  await expect(email).toHaveAttribute("aria-invalid", "true");
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
