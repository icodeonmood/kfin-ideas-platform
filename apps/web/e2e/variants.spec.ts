import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, settleMotion } from "./helpers";
import { events, isPhone, personWithFlag, removeFlagRows, sql } from "./variants-lib";

/**
 * P-DECISIONS.experiments on Tell it, against the local stack (BLD-C170 to C175). Each test signs in a new synthetic
 * person, forces the flag to the alternative for them through an explicit flag_assignments row it creates, and
 * removes that row, their exposures and their events when it ends, pass or fail. Flags ship at 0 %, so everyone
 * else, every other spec included, sees the default.
 *
 *   S1 "Interview" (S-04, S-04B): the intro lists the three questions; after the first telling the questions come one
 *   at a time with "Skip this one"; the place is kept with the draft across a reload; then the draft. axe clean on
 *   each state, desktop and phone.
 *   S3 "Voice first" (phone S-04): without the microphone allowed, the phone starts with typing (with it allowed:
 *   variants-voice.spec.ts, which needs its own browser).
 *
 * Synthetic words only.
 */

const WORDS =
  "Synthetic: the redemption SMS only gives a code, so investors call the branch to ask what it means.";

test.describe("S1 Interview (P-DECISIONS.experiments, L-DRAFT.parts/10, V-ACC.share/15)", () => {
  let userId: string | null = null;
  test.afterEach(async () => {
    await removeFlagRows(userId);
    userId = null;
  });

  test("S-04, S-04B: the intro, then three skippable questions kept with the draft, then the draft; axe clean", async ({
    page,
  }, info) => {
    userId = await personWithFlag(page, "s1", info);
    await page.goto("/share?new=1");
    await expect(
      page.getByText("Tell it in your words first. Then three short questions, each one skippable."),
    ).toBeAttached();
    if (!isPhone(page)) {
      await expect(page.getByText("Who feels it most?")).toBeVisible();
      await expectNoSeriousAxeIssues(page);
    }

    const box = page.getByRole("textbox", { name: /^(Describe the problem|For example: )/ });
    await box.fill(WORDS);
    await expect(page.getByText("Enter starts your draft. Shift and Enter for a new line.")).toBeVisible();
    await box.press("Enter");
    await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
    const draftPath = new URL(page.url()).pathname;

    const card = page.getByRole("group", { name: "How often does it happen, roughly?" });
    await expect(card).toBeVisible();
    await expect(card.getByText("Question 1 of 3. Skip any of them.")).toBeVisible();
    if (isPhone(page)) await expect(page.getByText("3 quick questions, then your draft")).toBeVisible();
    else
      await expect(
        page.getByText("Tell it in your words first. Then three short questions, each one skippable."),
      ).toBeVisible();
    await expectNoSeriousAxeIssues(page);

    await card
      .getByRole("textbox", { name: "How often does it happen, roughly?" })
      .fill("About 20 times a week at one branch");
    await card.getByRole("button", { name: "Next question" }).click();
    const who = page.getByRole("group", { name: "Who feels it most?" });
    await expect(who.getByText("Question 2 of 3. Skip any of them.")).toBeVisible();
    await expect(who.getByRole("textbox", { name: "Who feels it most?" })).toBeFocused();
    // The answer is in the conversation as the person's own words
    await expect(page.getByText("About 20 times a week at one branch", { exact: true })).toBeVisible();

    // Nothing is lost on reload: the place is kept with the draft
    await page.reload();
    await expect(page.getByRole("group", { name: "Who feels it most?" })).toBeVisible();

    await page
      .getByRole("group", { name: "Who feels it most?" })
      .getByRole("button", { name: "Skip this one" })
      .click();
    const size = page.getByRole("group", { name: "Any rough size?" });
    await expect(size.getByRole("button", { name: "Show my draft" })).toBeVisible();
    await settleMotion(page);
    await expectNoSeriousAxeIssues(page);
    await size.getByRole("button", { name: "Skip this one" }).click();
    await expect(page.getByRole("group", { name: /Question|rough size/ })).toHaveCount(0);
    expect(new URL(page.url()).pathname).toBe(draftPath);

    expect(await events(userId, "s1")).toEqual([
      "s1.start:started",
      "s1.often:answered",
      "s1.who:skipped",
      "s1.size:skipped",
      "s1.end:finished",
    ]);
    const seen = await sql<{ screen: string; variant: string }>(
      "SELECT DISTINCT screen, variant FROM flag_exposures WHERE user_id = $1 AND flag_key = 's1' ORDER BY screen",
      [userId],
    );
    expect(seen).toEqual([
      { screen: "S-04", variant: "alternative" },
      { screen: "S-04B", variant: "alternative" },
    ]);
  });
});

test.describe("S3 Voice first on a phone, the microphone not allowed yet (P-DECISIONS.experiments)", () => {
  let userId: string | null = null;
  test.afterEach(async () => {
    await removeFlagRows(userId);
    userId = null;
  });

  test("S-04 starts with typing exactly as the default does; the exposure and the reason are logged", async ({
    page,
  }, info) => {
    test.skip(!isPhone(page), "S3 is the phone's");
    userId = await personWithFlag(page, "s3", info);
    await page.goto("/share?new=1");
    const box = page.getByRole("textbox", { name: /^(Describe the problem|For example: )/ });
    await expect(box).toBeVisible();
    await expect.poll(() => events(userId!, "s3")).toEqual(["s3.listen:no_permission"]);
    await expect(page.getByRole("button", { name: "Type instead" })).toHaveCount(0);
    await expect(box).toBeEditable();
    await expect(page.getByRole("button", { name: "Move to Review" })).toBeVisible();
    await expectNoSeriousAxeIssues(page);
    // The phone's own exposure, sent once the screen knows it is a phone (lane A's reader logs it, BLD-C173)
    await expect
      .poll(async () =>
        (
          await sql<{ variant: string }>(
            "SELECT variant FROM flag_exposures WHERE user_id = $1 AND flag_key = 's3' AND screen = 'S-04'",
            [userId!],
          )
        ).map((r) => r.variant),
      )
      .toEqual(["alternative"]);
  });
});
