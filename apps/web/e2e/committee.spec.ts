/**
 * The committee flow in the browser (§4.5–§4.7): with `committee.flow` and `clusters.batch` on, two colleagues'
 * ideas are reviewed and grouped; the desk qualifies the group; the chair opens a cycle; the committee scores it
 * blind; the chair shortlists; a contributor accepts the invitation; the chair records the session; members seal
 * their assessments; the chair collates and decides. axe clean on every new screen, at desktop width and at 360 px.
 * Desktop project only: the switches and the cycle are shared, so two projects at once would race.
 */
import { expect, test, type Browser } from "@playwright/test";

import {
  as,
  axeBoth,
  CHAIR,
  chooseScores,
  MEMBERS,
  officeWords,
  setSwitch,
  toRevealedRound,
} from "./committee-helpers";
import { withSwitchLock } from "./switch-lock";

// Two colleagues from different LOBs who are not sign-in personas: accepting gives them working-group grants,
// which would change what a persona sees in other specs. Neither reports to a committee member.
const CONTRIBUTORS: [string, string] = ["SYN-00031", "SYN-00057"];

test("from a group of ideas to a committee decision", async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "shared switches and cycle; the 360 px check is inside");
  test.setTimeout(900_000); // includes waiting for the other specs that flip the same switch
  await withSwitchLock("clusters.batch", () => committeeFlow(browser));
});

async function committeeFlow(browser: Browser) {
  for (const s of ["committee.flow", "clusters.batch"]) await setSwitch(browser, s, "on");
  try {
    const { cluster, roundHref } = await toRevealedRound(browser, CONTRIBUTORS, officeWords(17), "4", true);
    const chair = await as(browser, CHAIR);
    await chair.page.goto(roundHref);
    await chair.page
      .getByLabel(/Why shortlist below the threshold/)
      .fill("Strong pain at every branch; worth hearing in person.")
      .catch(() => undefined);
    await chair.page.getByRole("button", { name: "Record the decision" }).click();
    await expect(chair.page.getByRole("status").filter({ hasText: "Decided." })).toBeVisible();

    // A contributor accepts the invitation (the message links straight to it).
    await chair.page.goto("/committee");
    const presLink = chair.page.getByRole("link", { name: new RegExp(`PRS-\\d{4}-\\d{4} \\(${cluster}\\)`) });
    const presentation = /PRS-\d{4}-\d{4}/.exec(await presLink.innerText())![0];
    const c = await as(browser, CONTRIBUTORS[0]);
    await c.page.goto(`/presentations/${presentation}`);
    await axeBoth(c.page);
    await c.page.getByRole("button", { name: "Accept the invitation" }).click();
    await expect(c.page.getByRole("status").filter({ hasText: "Accepted." })).toBeVisible();
    await c.close();

    // The session, sealed assessments, collation and the decision.
    await chair.page.goto(`/committee/presentations/${presentation}`);
    await axeBoth(chair.page);
    await chair.page
      .getByLabel("Questions and answers")
      .fill("Asked about AMC form differences; a pilot is proposed.");
    await chair.page.getByRole("button", { name: "They presented" }).click();
    await expect(chair.page.getByRole("status").filter({ hasText: "Marked as presented." })).toBeVisible();
    for (const who of [CHAIR, ...MEMBERS]) {
      const m = await as(browser, who);
      await m.page.goto(`/committee/presentations/${presentation}`);
      await chooseScores(m.page, "Seal my assessment", "4");
      await m.page.getByLabel("Your vote").selectOption("accept");
      await m.page.getByLabel("Strengths (up to 3, one per line)").fill("The pain is felt at every branch");
      await m.page.getByLabel(/willing to sponsor/).check();
      await m.page.getByRole("button", { name: "Seal my assessment" }).click();
      await expect(
        m.page.getByRole("status").filter({ hasText: "Your assessment is sealed." }),
      ).toBeVisible();
      await m.close();
    }
    await chair.page.goto(`/committee/presentations/${presentation}`);
    await chair.page.getByRole("button", { name: "Collate the assessments" }).click();
    await expect(chair.page.getByRole("heading", { level: 2, name: "Decision sheet" })).toBeVisible();
    await chair.page.getByLabel("Sponsor").selectOption({ index: 1 });
    await chair.page.getByRole("button", { name: "Ask the assistant to draft the reasons" }).click();
    await expect(chair.page.getByLabel("Reason, in plain words")).not.toHaveValue("");
    await chair.page.getByRole("button", { name: "Record the decision" }).click();
    await expect(chair.page.getByRole("status").filter({ hasText: "Decided." })).toBeVisible();
    await expect(chair.page.getByText(/Decision DEC-\d{4}-\d{4}: picked/)).toBeVisible();
    await axeBoth(chair.page);
    await chair.close();
  } finally {
    for (const s of ["committee.flow", "clusters.batch"]) await setSwitch(browser, s, "off");
  }
}
