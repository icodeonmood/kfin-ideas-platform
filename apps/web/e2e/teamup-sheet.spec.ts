/**
 * C-SHEET-TEAMUP in a real browser at phone width (lane F, BLD-F074): the sheet on the dev-only page /kit/team-up,
 * opened from an idea and from a draft on Check it. axe on compose, on the Check it choice and on sent (lane D's
 * helper, which settles motion first and checks reflow at 320px); the dropdown and the radios by keyboard; touch
 * targets; focus back to what stands where "Team up" was. The spec answers the sheet's team-up calls itself, so it
 * needs no seeded idea. Synthetic people only: the pack's fictional cast (Kavya asks, Ravi leads).
 */
import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

const IDEA = "IDEA-2026-001412";
const TITLE = "Rejection SMS codes confuse investors";
const RAVI = {
  id: "p-ravi",
  name: "Ravi Nair",
  first_name: "Ravi",
  initials: "RN",
  area: "Investor service",
};
const KAVYA = { id: "p-kavya", name: "Kavya Iyer", first_name: "Kavya", initials: "KI" };
const DRAFTED =
  "I’m in Investor service (Senior executive). I shared “Investors call to ask why a redemption was rejected”, which is close to yours, and I can bring what I learned from it.";
const NOTE =
  "I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07. I can bring the call log and real examples of what investors ask.";
const OWN = [
  {
    id: "IDEA-2026-001481",
    title: "Investors call to ask why a redemption was rejected",
    status: "with_review_desk",
    meta: "IDEA-2026-001481, with the review desk",
  },
  {
    id: "IDEA-2026-001502",
    title: "No script for calls about rejections",
    status: "shared",
    meta: "IDEA-2026-001502, shared",
  },
];
const WAITING = {
  state: "waiting",
  line: "Waiting for Ravi",
  detail: "Ravi reads your note, then approves or declines. You’ll hear in your Inbox.",
  action: { label: "Withdraw", op: "withdraw" },
};

/** The sheet's calls for IDEA (A-API.team-up), answered here. */
async function answerTeamUp(page: Page) {
  await page.route(`**/api/ideas/${IDEA}/team-up/draft-note`, (route) =>
    route.fulfill({
      json: {
        note: DRAFTED,
        own_ideas: OWN,
        idea: { id: IDEA, title: TITLE },
        lead: RAVI,
        min_chars: 30,
        max_chars: 600,
      },
    }),
  );
  await page.route(`**/api/ideas/${IDEA}/team-up`, (route) => {
    const req = route.request();
    if (req.method() !== "POST") {
      return route.fulfill({
        json: {
          idea_id: IDEA,
          lead: RAVI,
          me: null,
          crew_count: 4,
          can_request: true,
          why_not: null,
          request: null,
          after: null,
        },
      });
    }
    const body = req.postDataJSON() as { note: string };
    return route.fulfill({
      status: 201,
      json: {
        id: "req-e2e",
        request: "teamup",
        idea_id: IDEA,
        from: KAVYA,
        note: body.note,
        brought: [],
        state: "sent",
        sent_at: "2026-11-17T10:30:00+05:30",
        after: WAITING,
      },
    });
  });
}

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "the viewport is set here; one project is enough");
  await answerTeamUp(page);
  await signIn(page, PERSONAS.contributor);
  await page.goto("/kit/team-up");
  await expect(page.getByRole("heading", { level: 1, name: "Team up sheet" })).toBeVisible();
});

test("C-SHEET-TEAMUP.compose at 375px: a bottom sheet with 44px targets; axe; Tab to the dropdown, Space ticks an idea, Escape closes the list only", async ({
  page,
}) => {
  await page.getByRole("button", { name: `Team up on ${TITLE}` }).click();
  const sheet = page.getByRole("dialog", { name: "Team up with Ravi" });
  await expect(sheet).toBeVisible();
  const note = sheet.getByRole("textbox", { name: "Your note to Ravi" });
  await expect(note).toBeFocused();
  await expect(note).toHaveValue(DRAFTED);
  await expect(sheet).toContainText("We drafted this from your idea. Change anything you like.");

  // Phone: the sheet sits on the bottom edge, full width (C-SHEET-TEAMUP.compose, "bottom sheet on phone").
  // Full width is the page's own width: the desktop browser keeps a scrollbar gutter beside it.
  const box = (await sheet.boundingBox())!;
  const pageWidth = await page.evaluate(() => document.documentElement.clientWidth);
  expect(box.x).toBeLessThan(1);
  expect(Math.abs(box.width - pageWidth)).toBeLessThan(2);
  expect(Math.abs(box.y + box.height - 812)).toBeLessThan(2);
  // Touch targets (F-A11Y): the cross, the dropdown and Send are 44px or more each way.
  for (const name of ["Close without sending", "Bring your ideas along: None picked", "Send to Ravi"]) {
    const b = (await sheet.getByRole("button", { name, exact: true }).boundingBox())!;
    expect(b.height, name).toBeGreaterThanOrEqual(44);
    expect(b.width, name).toBeGreaterThanOrEqual(44);
  }
  await expectNoSeriousAxeIssues(page);

  // The dropdown by keyboard (C-DROPDOWN/5).
  await page.keyboard.press("Tab");
  const field = sheet.getByRole("button", { name: "Bring your ideas along: None picked" });
  await expect(field).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(field).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("Tab");
  const first = sheet.getByRole("checkbox", { name: /^Investors call to ask why a redemption was rejected/ });
  await expect(first).toBeFocused();
  await page.keyboard.press("Space");
  await expect(first).toBeChecked();
  await expect(sheet).toContainText("Ravi sees your name, your note and the idea you bring.");
  await expectNoSeriousAxeIssues(page);
  await page.keyboard.press("Escape");
  const picked = sheet.getByRole("button", { name: `Bring your ideas along: ${OWN[0]!.title}` });
  await expect(picked).toBeFocused();
  await expect(picked).toHaveAttribute("aria-expanded", "false");
  await expect(sheet).toBeVisible();

  // On to Send, then round to the cross: focus stays in the sheet.
  await page.keyboard.press("Tab");
  await expect(sheet.getByRole("button", { name: "Send to Ravi" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(sheet.getByRole("button", { name: "Close without sending" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(page.getByRole("button", { name: `Team up on ${TITLE}` })).toBeFocused();
});

test("C-SHEET-TEAMUP Check it at 375px: the draft's choice is one tab stop, arrows pick, each says what it does; axe", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Team up from your draft" }).click();
  const sheet = page.getByRole("dialog", { name: "Team up with Ravi" });
  await expect(sheet.getByRole("textbox", { name: "Your note to Ravi" })).toBeFocused();
  const group = sheet.getByRole("group", { name: "Your draft" });
  const keep = group.getByRole("radio", { name: "Keep mine separate" });
  const merge = group.getByRole("radio", { name: "Ask Ravi to merge mine in" });
  await expect(keep).toBeChecked();
  await expect(sheet.getByRole("button", { name: /^Bring your ideas along/ })).toHaveCount(0);

  await page.keyboard.press("Tab");
  await expect(keep).toBeFocused();
  await page.keyboard.press("ArrowUp");
  await expect(merge).toBeFocused();
  await expect(merge).toBeChecked();
  await expect(sheet).toContainText(
    "Ravi decides. If Ravi accepts, yours joins that idea with credit to you. If not, you send yours on its own.",
  );
  await expect(sheet).toContainText("Ravi sees your name, your note and the idea you bring.");
  await expectNoSeriousAxeIssues(page);

  await page.keyboard.press("Tab");
  await expect(sheet.getByRole("button", { name: "Send to Ravi" })).toBeFocused();
});

test("C-SHEET-TEAMUP.sent at 375px: Sent to Ravi with the note back; axe; Done returns focus to Waiting for Ravi", async ({
  page,
}) => {
  await page.getByRole("button", { name: `Team up on ${TITLE}` }).click();
  const sheet = page.getByRole("dialog", { name: "Team up with Ravi" });
  await sheet.getByRole("textbox", { name: "Your note to Ravi" }).fill(NOTE);
  await expect(sheet).toContainText("Looks good.");
  await sheet.getByRole("button", { name: "Send to Ravi" }).click();

  await expect(sheet.getByRole("status")).toContainText("Sent to Ravi");
  await expect(sheet).toContainText(
    "Ravi reads your note, then approves or declines. You’ll hear in your Inbox.",
  );
  await expect(sheet).toContainText(NOTE);
  await expect(sheet.getByRole("button", { name: "Withdraw request" })).toBeVisible();
  const done = sheet.getByRole("button", { name: "Done" });
  await expect(done).toBeFocused();
  await expectNoSeriousAxeIssues(page);

  // The host re-drew "Team up" as "Waiting for Ravi" while the sheet was open; focus lands there (WCAG 2.4.3).
  await page.keyboard.press("Enter");
  await expect(sheet).toBeHidden();
  await expect(page.getByRole("button", { name: "Waiting for Ravi" })).toBeFocused();
});
