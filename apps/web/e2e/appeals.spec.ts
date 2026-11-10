/**
 * Appeals and the fairness reports in the browser (§4.12, §3.8): a preliminary review declines a group; a
 * contributor appeals it from the Appeals page; the panel chair reads the blind materials and records that the
 * decision stands; the contributor sees the outcome; an admin opens the fairness and calibration reports. axe clean
 * on every new screen at desktop width and at 360 px. Desktop project only: the switches and the cycle are shared.
 */
import { expect, test, type Browser } from "@playwright/test";

import { as, axeBoth, CHAIR, MEMBERS, officeWords, setSwitch, toRevealedRound } from "./committee-helpers";
import { PERSONAS, type SwitchState } from "./helpers";
import { withSwitchLock } from "./switch-lock";

// Not sign-in personas, from two LOBs, and neither reports to a committee member.
const CONTRIBUTORS: [string, string] = ["SYN-00032", "SYN-00058"];
const SWITCHES = ["committee.flow", "clusters.batch", "appeals.filing"];

test("a declined group is appealed and the panel records the outcome", async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "shared switches and cycle; the 360 px check is inside");
  test.setTimeout(900_000); // includes waiting for the other specs that flip `clusters.batch`
  await withSwitchLock("clusters.batch", () => appealFlow(browser));
});

async function appealFlow(browser: Browser) {
  const before: Array<[string, SwitchState]> = [];
  for (const s of SWITCHES) before.push([s, await setSwitch(browser, s, "on")]);
  try {
    const { cluster, roundHref } = await toRevealedRound(browser, CONTRIBUTORS, officeWords(29), "1", false);
    const chair = await as(browser, CHAIR);
    await chair.page.goto(roundHref);
    await chair.page.getByLabel("Outcome").selectOption("declined");
    await chair.page.getByLabel("Reason", { exact: true }).selectOption("LOW_VALUE");
    await chair.page
      .getByLabel(/Note for the colleagues/)
      .fill("Not enough value for KFintech right now, given the effort it needs.");
    await chair.page.getByRole("button", { name: "Record the decision" }).click();
    await expect(chair.page.getByRole("status").filter({ hasText: "Decided." })).toBeVisible();
    await chair.close();

    // The contributor appeals from the Appeals page.
    const c = await as(browser, CONTRIBUTORS[0]);
    await c.page.goto("/appeals");
    await expect(c.page.getByRole("heading", { level: 3, name: new RegExp(cluster) })).toBeVisible();
    await axeBoth(c.page);
    const item = c.page
      .getByRole("listitem")
      .filter({ has: c.page.getByRole("heading", { name: new RegExp(cluster) }) });
    await item.getByRole("checkbox", { name: /grouped with ideas it does not belong with/ }).check();
    await item
      .getByLabel(/Your statement/)
      .fill(
        "The committee read this as one branch's problem; it happens at every branch that takes paper forms.",
      );
    await item.getByRole("checkbox", { name: /10-minute hearing/ }).check();
    await item.getByRole("button", { name: "Send my appeal" }).click();
    // The page refreshes: the form gives way to the appeal's state.
    const sent = c.page.getByText(/Your appeal APL-\d{4}-\d{4} is with the panel/).first();
    await expect(sent).toBeVisible();
    const appeal = /APL-\d{4}-\d{4}/.exec(await sent.innerText())![0];
    await c.close();

    // The panel: whoever chairs it records the outcome; the page is checked once.
    let decided = false;
    for (const who of MEMBERS) {
      const m = await as(browser, who);
      await m.page.goto("/appeals");
      if (await m.page.getByRole("link", { name: new RegExp(appeal) }).count()) {
        await m.page.getByRole("link", { name: new RegExp(appeal) }).click();
        await m.page.waitForURL(new RegExp(`/appeals/${appeal}$`));
        await expect(m.page.getByText("The colleagues asked for a 10-minute hearing.")).toBeVisible();
        const form = m.page.getByRole("button", { name: "Record the outcome" });
        if (await form.count()) {
          await axeBoth(m.page);
          await m.page.getByRole("radio", { name: "The decision stands" }).check();
          await m.page
            .getByLabel(/Reasons \(the colleagues read these/)
            .fill("The committee did see the problem at every branch; the value is still too small for now.");
          await form.click();
          await expect(m.page.getByRole("status").filter({ hasText: "Recorded." })).toBeVisible();
          decided = true;
        }
      }
      await m.close();
      if (decided) break;
    }
    expect(decided).toBe(true);

    const back = await as(browser, CONTRIBUTORS[0]);
    await back.page.goto("/appeals");
    await expect(back.page.getByText(`Your appeal ${appeal} was heard: the decision stands.`)).toBeVisible();
    await back.close();

    // The fairness and calibration reports, counts only.
    const admin = await as(browser, PERSONAS.admin);
    await admin.page.goto("/reports");
    await expect(
      admin.page.getByRole("heading", { level: 1, name: "Fairness and calibration" }),
    ).toBeVisible();
    await axeBoth(admin.page);
    await admin.close();
  } finally {
    for (const [s, state] of before) await setSwitch(browser, s, state); // as we found them (DEC-088)
  }
}
