/**
 * S-H3 "Share another way" (/share/other-ways) and S-H4 "What happens after you share" (/how-it-works). Email and
 * Teams intake are built and switched off until IT approves them (DEC-105). Every check of the look runs axe and
 * the 320 px reflow check (V-ACC.visual/4, BLD-A163).
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn, switchIsOn } from "./helpers";

/** The review promise the company repo was seeded with (rules/promises.md, BLD-A181). */
function decideByWorkingDays(): number {
  const text = readFileSync(path.resolve(process.cwd(), "../../seed/company-repo/rules/promises.md"), "utf8");
  const m = text.match(/decide_by_working_days:\s*(\d+)/);
  if (!m?.[1]) throw new Error("rules/promises.md has no review.decide_by_working_days");
  return Number(m[1]);
}

test.describe("S-H3: Share another way", () => {
  test("S-H3, DEC-105, V-ACC.visual/4: with email and Teams off, each says Coming soon and nothing can arrive", async ({
    page,
  }) => {
    test.skip(
      (await switchIsOn("intake.email")) || (await switchIsOn("intake.teams")),
      "an intake switch is on in this database",
    );
    await signIn(page, PERSONAS.contributor);
    await page.goto("/share/other-ways");
    await expect(page.getByRole("link", { name: "Home" }).last()).toHaveAttribute("href", "/home");
    await expect(page.getByRole("heading", { level: 1, name: "Share another way" })).toBeVisible();
    await expect(
      page.getByText("Each one lands here as a draft. Nothing is sent until you check it."),
    ).toBeVisible();
    await expect(page.getByRole("heading", { level: 2 })).toHaveText([
      "Forward it from Outlook Coming soon",
      "Message it in Teams Coming soon",
      "Use the 1% Club app Coming soon",
    ]);
    await expect(
      page.getByText("Forward the thread that shows the problem. Your note on top becomes the draft."),
    ).toBeVisible();
    await expect(page.getByText("Chat with 1% Club in Teams. Paste screenshots straight in.")).toBeVisible();
    await expect(page.getByText("Share from your phone, typed or spoken, in any language.")).toBeVisible();
    await expect(page.getByText("Android and iOS")).toBeVisible();
    // The ways in that are off show no address, steps or button (L-AUDIT.flags).
    await expect(page.getByRole("button", { name: "Copy the address" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Open in Outlook" })).toHaveCount(0);
    await expect(page.getByRole("link", { name: "Open in Teams" })).toHaveCount(0);
    await expect(page.getByText("First time? Add it once:")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "Arrived from elsewhere" })).toHaveCount(0);
    await expectNoSeriousAxeIssues(page);
  });

  test("S-H3.rules/2, L-NOTIFY/7: 'Tell me when it's out' is kept for the person", async ({ page }, info) => {
    // One person per project, so the two projects never press the same person's button at once.
    await signIn(page, info.project.name === "desktop" ? PERSONAS.contributor : PERSONAS.reviewer);
    await page.goto("/share/other-ways");
    const ask = page.getByRole("button", { name: "Tell me when it’s out" });
    const told = page.getByRole("button", { name: "We’ll tell you when it’s out" });
    await expect(ask.or(told)).toBeVisible();
    if (await told.isVisible()) {
      await told.click(); // a retry starts from wherever the last run left it
      await expect(ask).toHaveAttribute("aria-pressed", "false");
    }
    await ask.click();
    await expect(told).toHaveAttribute("aria-pressed", "true");
    await expectNoSeriousAxeIssues(page);
    await page.reload();
    await expect(told).toHaveAttribute("aria-pressed", "true");
    await told.click();
    await expect(ask).toHaveAttribute("aria-pressed", "false");
    await page.reload();
    await expect(ask).toBeVisible();
  });
});

test.describe("S-H4: What happens after you share", () => {
  test("S-H4/1-3, V-ACC.visual/4: five stages with their promises from configuration, and one way on", async ({
    page,
  }) => {
    await signIn(page, PERSONAS.contributor);
    await page.goto("/how-it-works");
    await expect(page.getByRole("heading", { level: 1, name: "What happens after you share" })).toBeVisible();
    const stages = page.getByRole("list").filter({ has: page.getByRole("heading", { name: "Shared" }) });
    await expect(stages.getByRole("heading", { level: 2 })).toHaveText([
      "Shared",
      "Checked and matched",
      "Reviewed",
      "Built",
      "Shipped",
    ]);
    const days = decideByWorkingDays();
    await expect(page.getByText(`Within ${days} working ${days === 1 ? "day" : "days"}`)).toBeVisible();
    await expect(page.getByText("About two minutes")).toBeVisible();
    await expect(page.getByText("Automatic, minutes")).toBeVisible();
    await expect(page.getByText("Depends on the fix")).toBeVisible();
    await expect(page.getByText("After it’s live")).toBeVisible();
    await expect(
      page.getByText(
        "The review desk may ask you questions, each with a clear time to answer. You get a decision with a reason.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Share your first problem" })).toHaveAttribute(
      "href",
      "/share",
    );
    await expectNoSeriousAxeIssues(page);
  });

  test.describe("with reduced motion", () => {
    test.use({ reducedMotion: "reduce" });
    test("S-H4/4, V-ACC.visual/6: the track appears complete, and nothing moves", async ({ page }) => {
      await signIn(page, PERSONAS.contributor);
      await page.goto("/how-it-works");
      await expect(page.getByRole("heading", { level: 2, name: "Shipped" })).toBeVisible();
      const moving = await page.evaluate(
        () =>
          document
            .getAnimations()
            .filter(
              (a) => a.playState === "running" && (a.effect as KeyframeEffect | null)?.target?.closest(".hw"),
            ).length,
      );
      expect(moving).toBe(0);
    });
  });
});
