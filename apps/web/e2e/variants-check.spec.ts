import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues } from "./helpers";
import { isPhone, personWithFlag, removeFlagRows, sql } from "./variants-lib";

/**
 * S2 "Check first" on S-05 (P-DECISIONS.experiments, L-SIMILAR "Flag S2"; BLD-C176), with the flag forced to the
 * alternative for a new synthetic person through a flag_assignments row the test creates and removes. As in
 * check-it.spec.ts the draft's own answers are synthetic and served by `page.route`, with a close match on top, so the
 * comparison is certain to come first; the page, the shell and the flag (lane A's reader, the exposure on S-05) are
 * real. Desktop: the similar ideas are part 1 of the rail, then your words. Phone: "Is it one of these?" before the
 * rest, and "Mine is different" carries on. axe on each state. Synthetic only.
 */

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
      view_url: "/api/files/f1/view",
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

type Sent = { event?: string; outcome?: string; flag?: string };

function watchEvents(page: Page): Sent[] {
  const sent: Sent[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && new URL(r.url()).pathname === "/api/flags/events")
      sent.push(r.postDataJSON() as Sent);
  });
  return sent;
}

let userId: string | null = null;
test.afterEach(async () => {
  await removeFlagRows(userId);
  userId = null;
});

test("S-05 S2 Check first: on a close match the comparison comes first, then your words; axe clean", async ({
  page,
}, info) => {
  userId = await personWithFlag(page, "s2", info);
  const sent = watchEvents(page);
  await serveDraft(page);
  await page.goto(`/share/${DRAFT}/check`);

  if (isPhone(page)) {
    await expect(page.getByRole("heading", { level: 2, name: "Is it one of these?" })).toBeVisible();
    await expect(
      page.getByText(
        "Something very close was shared on 9 November. Adding yours to it gets both decided together, and you’re credited.",
      ),
    ).toBeVisible();
    await expect(page.getByText("IDEA-2026-001412, shared 9 November")).toBeVisible();
    await expect(page.getByRole("button", { name: "Team up" })).toBeVisible();
    await expectNoSeriousAxeIssues(page);
    await page.getByRole("button", { name: "Mine is different" }).click();
    await expect(page.getByRole("heading", { level: 2, name: "Is it one of these?" })).toHaveCount(0);
    await expect(page.getByRole("heading", { level: 2, name: "Your problem" })).toBeVisible();
    await expect
      .poll(() => sent.map((s) => `${s.event}:${s.outcome}`))
      .toContain("s2.compare:mine_is_different");
  } else {
    await expect(
      page.getByRole("heading", { level: 1, name: "Has someone raised this already?" }),
    ).toBeVisible();
    await expect(page.getByText("Check it, part 1 of 6")).toBeVisible();
    const rail = page.getByRole("navigation", { name: "Check it" }).getByRole("button");
    await expect(rail.first()).toHaveAccessibleName(/^1 Similar ideas/);
    await expect(rail.nth(1)).toHaveAccessibleName(/^2 Your words/);
    await expect(page.getByRole("link", { name: "Back to your words" })).toHaveAttribute(
      "href",
      `/share/${DRAFT}`,
    );
    await expectNoSeriousAxeIssues(page);
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Is this how you’d put it?" })).toBeVisible();
    await expect(page.getByText("Check it, part 2 of 6")).toBeVisible();
    await expect
      .poll(() => sent.map((s) => `${s.event}:${s.outcome}`))
      .toEqual(["s2.check:opened", "s2.compare:shown", "s2.compare:moved_on"]);
  }
  // Lane A's reader logged the exposure on the server as S-05 rendered
  const seen = await sql<{ variant: string }>(
    "SELECT variant FROM flag_exposures WHERE user_id = $1 AND flag_key = 's2' AND screen = 'S-05'",
    [userId],
  );
  expect(seen.map((r) => r.variant)).toEqual(["alternative"]);
});
