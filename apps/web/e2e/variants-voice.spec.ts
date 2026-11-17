import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues } from "./helpers";
import { events, isPhone, personWithFlag, removeFlagRows } from "./variants-lib";

/**
 * S3 "Voice first" on a phone's S-04 with the microphone already allowed (P-DECISIONS.experiments, BLD-C175): the
 * page listens at once, the dock holds "Type instead" and "Stop", and "Type instead" stops listening and puts focus
 * in the box. Chromium's fake microphone, granted for this file's own browser; the flag forced to the alternative for
 * a new synthetic person through a flag_assignments row the test creates and removes. Synthetic only.
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

test.describe("S3 Voice first on a phone, the microphone allowed (P-DECISIONS.experiments)", () => {
  let userId: string | null = null;
  test.afterEach(async () => {
    await removeFlagRows(userId);
    userId = null;
  });

  test("S-04 listens at once with Type instead and Stop in the dock; Type instead puts focus in the box", async ({
    page,
  }, info) => {
    test.skip(!isPhone(page), "S3 is the phone's");
    userId = await personWithFlag(page, "s3", info);
    await page.goto("/share?new=1");
    const typeInstead = page.getByRole("button", { name: "Type instead" });
    await expect(typeInstead).toBeVisible({ timeout: 15_000 });
    await expect(page.getByRole("button", { name: /^Stop(, \d+:\d\d)?$/ })).toBeVisible();
    await expect(page.getByRole("button", { name: "Move to Review" })).toHaveCount(0);
    await expectNoSeriousAxeIssues(page);
    await typeInstead.click();
    const box = page.getByRole("textbox", { name: /^(Describe the problem|For example: )/ });
    await expect(box).toBeFocused();
    await expect(page.getByRole("button", { name: "Type instead" })).toHaveCount(0);
    await expect.poll(() => events(userId!, "s3")).toContain("s3.listen:typed_instead");
  });
});
