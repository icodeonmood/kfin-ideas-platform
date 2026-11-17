/**
 * S-05 "Check it, then send it" in the browser (BLD-C136): every part, the preview, the fix sheet and the Send
 * part's messages pass axe (WCAG 2.1 AA, colour contrast included) with no sideways scroll, on a laptop and on a
 * phone (V-ACC, S-05.phone). The page and the shell are real; the draft's own API answers are synthetic and served
 * by `page.route`, so the screen is checked before the draft, similar-ideas, files and team-up routes reach main
 * from their branches. The journeys (J-SHARE/7–11, J-SIMILAR, J-RECOVER) walk the real routes.
 */
import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

const DRAFT = "5d0c9a1e-7b2f-4c3d-8e9f-a1b2c3d4e5f6";
const ME = { id: "u-syn", name: "Kavya Menon", first_name: "Kavya", initials: "KM" };
const RAVI = { id: "u-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" };

const DRAFT_BODY = {
  id: DRAFT,
  owner_id: ME.id,
  channel: "web",
  messages: [],
  parts: {
    title: { state: "filled", value: "Investors call to ask why a redemption was rejected" },
    summary: {
      state: "filled",
      value:
        "The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch.",
    },
    often: { state: "filled", value: "About 40 calls a day at one branch" },
    who: { state: "filled", value: [] },
    value: { state: "filled", value: [] },
    area: { state: "filled", value: "Investor service" },
    similar: { state: "filled", value: [] },
  },
  hidden: [{ id: "h1", kind: "folio", masked: "Folio ••••89", state: "hidden" }],
  sorting: {},
  files: [
    {
      id: "f1",
      kind: "file",
      name: "rejection-sms-screenshot.png",
      type: "image/png",
      size: 86016,
      state: "checked",
      added_by: ME,
      added_at: "2026-11-17T08:00:00Z",
    },
    {
      id: "f2",
      kind: "file",
      name: "branch-call-log-nov.pdf",
      type: "application/pdf",
      size: 143360,
      state: "personal_data_found",
      problem: "Found a phone number on page 2. Nobody can open it until it’s hidden.",
      added_by: ME,
      added_at: "2026-11-17T08:01:00Z",
    },
    {
      id: "l1",
      kind: "link",
      name: "https://intranet.kfintech.example/rejection-codes",
      type: "link",
      state: "ok",
      link_scope: "internal",
      added_by: ME,
      added_at: "2026-11-17T08:02:00Z",
    },
  ],
  step: "check:1",
  saved_at: "2026-11-17T08:08:00Z",
  saved_on: { device: "laptop", this_device: true },
  ready: true,
  min_chars: 30,
  char_count: 180,
};

const SORTING = {
  affects: {
    value: ["Investors", "KFin teams"],
    source: "suggested",
    why: null,
    why_line: "Suggested because you mentioned investors and the branch.",
  },
  kind: {
    value: "problem",
    source: "suggested",
    why: null,
    why_line: "Suggested because you described something that goes wrong today.",
  },
  area: {
    value: "Investor service",
    source: "suggested",
    why: null,
    why_line: "Suggested because it’s about investors and the SMS they get.",
  },
  brings: { value: ["saves_time", "saves_cost"], source: "suggested", why: null, why_line: null },
  confirmed: false,
  complete: true,
  confirmed_at: null,
  rail: "Suggested, not confirmed yet",
  summary: "Not confirmed yet",
  note: "These are suggestions from your words. Not confirmed yet.",
  problem: null,
};

const MATCHES = [
  {
    idea: {
      id: "IDEA-2026-001412",
      title: "Rejection SMS codes confuse investors",
      status: "with_review_desk",
      area: "Investor service",
      city: "Hyderabad",
      shared_at: "2026-11-09T10:00:00+05:30",
      lead: RAVI,
      crew_faces: [RAVI, { id: "u-aditi", name: "Aditi Sharma", first_name: "Aditi", initials: "AS" }],
      crew_count: 4,
      in_their_words: "Investors get a code, not a reason, and then they call us.",
      looking_for: "Someone who takes these calls at a branch.",
      hue: 1,
    },
    strength: "close",
    reason: "Close match: same SMS, same calls",
  },
  {
    idea: {
      id: "IDEA-2026-001398",
      title: "No script for calls about rejections",
      status: "picked",
      area: "Operations",
      city: "Mumbai",
      shared_at: "2026-11-05T10:00:00+05:30",
      lead: { id: "u-sunita", name: "Sunita Pillai", first_name: "Sunita", initials: "SP" },
      crew_faces: [{ id: "u-sunita", name: "Sunita Pillai", first_name: "Sunita", initials: "SP" }],
      crew_count: 2,
      in_their_words: "Branch staff have no words to explain a rejection code.",
      hue: 2,
    },
    strength: "related",
    reason: "Related: the calls you describe",
  },
];

const SEND = {
  id: DRAFT,
  rows: [
    {
      key: "title",
      label: "Title",
      value: "Investors call to ask why a redemption was rejected",
      ok: true,
      step: "check:1",
    },
    { key: "sorting", label: "Sorting", value: "Not confirmed yet", ok: false, step: "check:2" },
    { key: "similar", label: "Similar ideas", value: "2 similar ideas found", ok: true, step: "check:3" },
    { key: "proof", label: "Proof", value: "2 files, 1 link", ok: true, step: "check:4" },
    { key: "fix", label: "Your fix", value: "None added", ok: true, step: "check:5" },
    { key: "helpers", label: "Who would help", value: "Not said", ok: true, step: "check:6" },
  ],
  declaration: {
    version: "2026-11-17",
    text: "By submitting, you confirm there’s no customer personal data in it or its files, and it’s your own work or you’ve credited others.",
  },
  button: "Submit",
  ready: false,
  problems: [{ code: "sorting_unconfirmed", message: "Confirm the sorting first, or change any of it." }],
  go_to: { label: "Go to the sorting", step: "check:2" },
};

/** The draft's API, synthetic: only this test's browser sees these answers. */
async function serveDraft(page: Page) {
  await page.route(`**/api/drafts/${DRAFT}**`, (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();
    if (url.pathname === `/api/drafts/${DRAFT}`) {
      return route.fulfill({ json: method === "GET" ? DRAFT_BODY : {} });
    }
    if (url.pathname.endsWith("/sorting")) return route.fulfill({ json: SORTING });
    if (url.pathname.endsWith("/merge-request"))
      return route.fulfill({ json: { state: "none", after: null } });
    if (url.pathname.endsWith("/send")) return route.fulfill({ json: SEND });
    return route.fulfill({ status: 404, json: { error: { code: "not_found", message: "" } } });
  });
  await page.route(`**/api/ideas/${DRAFT}/similar**`, (route) =>
    route.fulfill({ json: route.request().method() === "GET" ? MATCHES : { kept_separate: true } }),
  );
}

async function openCheckIt(page: Page) {
  await signIn(page, PERSONAS.contributor);
  await serveDraft(page);
  await page.goto(`/share/${DRAFT}/check`);
  await expect(page.getByRole("heading", { level: 1, name: "Is this how you’d put it?" })).toBeVisible();
}

async function part(page: Page, label: string) {
  await page.getByRole("button", { name: new RegExp(`^(?:\\d )?${label}\\b`) }).click();
}

test("S-05 V-ACC: each part of Check it, the preview, the fix sheet and the Send messages pass axe (BLD-C136)", async ({
  page,
}, info) => {
  test.skip(info.project.name === "phone-360", "a phone shows Check it as one page: the next test");
  await openCheckIt(page);
  await expect(page.getByText("Check it, part 1 of 6")).toBeVisible();
  await expect(page.getByText("Folio ••••89").first()).toBeVisible();
  await expectNoSeriousAxeIssues(page);

  await part(page, "Sorting");
  await expect(page.getByRole("heading", { level: 1, name: "Is it sorted right?" })).toBeVisible();
  await expect(page.getByRole("radio", { name: "A problem to fix" })).toBeChecked();
  await expectNoSeriousAxeIssues(page);

  await part(page, "Similar ideas");
  await expect(page.getByText("Yours, not sent yet")).toBeVisible();
  await expectNoSeriousAxeIssues(page);
  await page.getByRole("button", { name: "Preview Rejection SMS codes confuse investors" }).click();
  const preview = page.getByRole("dialog");
  await expect(preview).toContainText("Teaming up adds you to their crew. Your draft stays yours.");
  await expectNoSeriousAxeIssues(page);
  await page.keyboard.press("Escape");
  await expect(preview).toHaveCount(0);

  await part(page, "Proof");
  await expect(
    page.getByText("Found a phone number on page 2. Nobody can open it until it’s hidden."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Hide it for me" })).toBeVisible();
  await expect(page.getByText(/couldn[’']t open this link/)).toHaveCount(0);
  await expectNoSeriousAxeIssues(page);

  await part(page, "Your fix");
  await page.getByRole("button", { name: "Add your fix" }).click();
  const sheet = page.getByRole("dialog", { name: "Your fix" });
  await expect(sheet).toContainText("0 of 5 ready for the review desk");
  await expectNoSeriousAxeIssues(page);
  await sheet.getByRole("button", { name: "Cancel" }).click();
  await expect(sheet).toHaveCount(0);

  await part(page, "Who would help");
  await expect(page.getByRole("heading", { level: 1, name: "Who would help?" })).toBeVisible();
  await expectNoSeriousAxeIssues(page);

  await part(page, "Send it");
  await expect(page.getByRole("heading", { level: 1, name: "Ready to send?" })).toBeVisible();
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText("Confirm the sorting first, or change any of it.")).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});

test("S-05.phone V-ACC: on a phone Check it is one page with the same parts, and passes axe (BLD-C136)", async ({
  page,
}, info) => {
  if (info.project.name === "desktop") await page.setViewportSize({ width: 390, height: 844 });
  await signIn(page, PERSONAS.contributor);
  await serveDraft(page);
  await page.goto(`/share/${DRAFT}/check`);
  await expect(page.getByRole("heading", { level: 1, name: "Check it, then send it" })).toBeVisible();
  for (const h of ["Your problem", "Is this sorted right?", "Already raised?", "Anything that shows it?"]) {
    await expect(page.getByRole("heading", { level: 2, name: h })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "Submit" })).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});
