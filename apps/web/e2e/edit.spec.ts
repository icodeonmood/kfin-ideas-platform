/**
 * S-06B "Edit after sharing" in the browser (BLD-C164): the page in its drawn states passes axe (WCAG 2.1 AA, colour
 * contrast included) with no sideways scroll, on a laptop and on a phone (V-ACC, S-06B.rules/5), and the boards'
 * "Announced" lines are live regions: "Unsaved changes", "Confirmed when you shared it. …", "Checked", "Checking for
 * personal details", the file and link messages, "Saved at …" and "Saved. The review desk will see the latest
 * version." The page and the shell are real; the idea's own API answers are synthetic and served by `page.route`, so
 * the screen is checked whatever the seed holds. The journeys (J-RECOVER/7–10 and /15 on S-06B) walk the real routes.
 */
import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, settleMotion, signIn } from "./helpers";

const REF = "IDEA-2026-001481";
const UUID = "7c1d2e3f-4a5b-4c6d-8e9f-0a1b2c3d4e5f";
const ME = { id: "u-syn", name: "Kavya Menon", first_name: "Kavya", initials: "KM" };
const SAVED = "Saved. The review desk will see the latest version.";

const PAGE = {
  screen: "S-06B",
  id: UUID,
  ref: REF,
  status: "with_review_desk",
  kind: "problem",
  bar: {
    title: `Edit ${REF}`,
    line: "Shared Saturday 14 November. You can edit until the review desk opens it, at the latest Tuesday 17 November.",
    back: { label: "Back to your idea", to: `/ideas/${REF}` },
  },
  window: {
    open: true,
    closes_at: "2026-11-17T10:00:00+05:30",
    countdown: { label: "3 days left", variant: "neutral", until: "2026-11-17T10:00:00+05:30" },
  },
  fields: {
    title: "Investors call to ask why a redemption was rejected",
    summary:
      "The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.",
    often: "About 40 calls a day at one branch",
  },
  hidden: [
    { id: "a1b2c3d4-0000-4000-8000-000000000001", kind: "folio", masked: "Folio ••••89", state: "hidden" },
  ],
  sorting: {
    affects: {
      value: ["Investors", "KFin teams"],
      source: "confirmed",
      why: null,
      why_line: "Suggested because you mentioned investors and the branch.",
    },
    kind: {
      value: "problem",
      source: "confirmed",
      why: null,
      why_line: "Suggested because you described something that goes wrong today.",
    },
    area: {
      value: "Investor service",
      source: "confirmed",
      why: null,
      why_line: "Suggested because it’s about investors and the SMS they get.",
    },
    brings: { value: ["saves_time", "saves_cost"], source: "confirmed", why: null, why_line: null },
    confirmed: true,
    complete: true,
    confirmed_at: "2026-11-14T10:00:00+05:30",
    rail: "Investor service, saves time, saves cost",
    summary: "Investor service, affecting investors and KFin teams, saves time, saves cost",
    note: "Confirmed when you shared it. You can still change any of these.",
    problem: null,
  },
  fix: null,
  helpers: { picks: [], text: null, line: "Not said", part: { rail: "Optional" } },
  files: [] as unknown[],
  prompts: {},
  side: [
    {
      when: "Straight away",
      line: "The review desk sees the latest version. Earlier versions are kept on the timeline.",
    },
    {
      when: "At the latest Tuesday 17 November",
      line: "Editing closes when the review desk opens it. After that, you can add a note for them instead.",
    },
    { when: "By Friday 20 November", line: "The review desk decides, and tells you why." },
  ],
  declaration: {
    version: "1pc-2026-11",
    text: "By saving, you confirm there’s no customer personal data in it or its files, and it’s your own work or you’ve credited others.",
  },
  versions: { count: 1, summary: "1 version. Sorting confirmed." },
};

/** Edit.md `evidence=Added` and `evidence=Personal data found`, with a link kept as typed (BLD-E001). */
const FILES = [
  {
    id: "f1",
    kind: "file",
    name: "rejection-sms-screenshot.png",
    type: "image/png",
    size: 86016,
    state: "checked",
    added_by: ME,
    added_at: "2026-11-15T08:00:00Z",
  },
  {
    id: "f2",
    kind: "file",
    name: "branch-call-log-nov.pdf",
    type: "application/pdf",
    size: 143360,
    state: "personal_data_found",
    problem: "Found a phone number on page 2. Only you, the review desk and the Ones Committee can open it.",
    added_by: ME,
    added_at: "2026-11-15T08:01:00Z",
  },
  {
    id: "l1",
    kind: "link",
    name: "https://intranet.kfintech.example/rejection-codes",
    type: "link",
    state: "ok",
    link_scope: "internal",
    added_by: ME,
    added_at: "2026-11-15T08:02:00Z",
  },
];

/** The idea's edit API, synthetic: only this test's browser sees these answers. */
async function serveIdea(page: Page, body: object = PAGE, save?: { status: number; json: object }) {
  await page.route(`**/api/ideas/${REF}/edit`, (route) => {
    if (route.request().method() === "GET") return route.fulfill({ json: body });
    return route.fulfill(
      save ?? {
        json: {
          version: { n: 2, changed_fields: ["title"], at: "2026-11-15T08:09:00Z" },
          changed_fields: ["title"],
          saved_label: "Saved at 1:39 pm",
          message: SAVED,
          next: { to: `/ideas/${REF}`, replace: true },
        },
      },
    );
  });
}

async function openEdit(page: Page, body: object = PAGE, save?: { status: number; json: object }) {
  await signIn(page, PERSONAS.contributor);
  await serveIdea(page, body, save);
  await page.goto(`/ideas/${REF}/edit`);
  await expect(page.getByRole("heading", { level: 1, name: "Edit your problem" })).toBeVisible();
}

test("S-06B V-ACC: the edit page, its files, the fix sheet, Cancel's confirm and Saved pass axe (BLD-C164)", async ({
  page,
}, info) => {
  test.skip(info.project.name === "phone-360", "a phone has its own layout: the next test");
  await openEdit(page, { ...PAGE, files: FILES });
  await expect(page.getByText(`Edit ${REF}`)).toBeVisible();
  await expect(page.getByText("Folio ••••89").first()).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: /^Saved$/ })).toBeVisible();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Confirmed when you shared it. You can still change any of these." }),
  ).toBeVisible();
  await expect(
    page.getByRole("alert").filter({
      hasText:
        "Found a phone number on page 2. Only you, the review desk and the Ones Committee can open it.",
    }),
  ).toBeVisible();
  // "Hide it for me" waits for `files.blackout`, off at launch (DEC-107, BLD-C064): shown only while it is on.
  const status = (await (await page.request.get("/api/status")).json()) as {
    paused: Array<{ switch: string }>;
  };
  const blackoutOn = !status.paused.some((p) => p.switch === "files.blackout");
  await expect(page.getByRole("button", { name: "Hide it for me" })).toHaveCount(blackoutOn ? 1 : 0);
  await expect(page.getByText(/couldn[’']t open this link/)).toHaveCount(0);
  await expectNoSeriousAxeIssues(page);

  // Edit in place: the bar says so, nothing is sent yet.
  await page.getByRole("button", { name: "Change the title" }).click();
  await page.getByRole("textbox", { name: "Title" }).fill("Investors call about a redemption not processed");
  await page.getByRole("textbox", { name: "Title" }).press("Enter");
  await expect(page.getByRole("status").filter({ hasText: "Unsaved changes" })).toBeVisible();

  await page.getByRole("button", { name: "Add your fix" }).click();
  const sheet = page.getByRole("dialog", { name: "Your fix" });
  await expect(sheet).toContainText("0 of 5 ready for the review desk");
  await expectNoSeriousAxeIssues(page);
  await sheet.getByRole("button", { name: "Cancel" }).click();
  await expect(sheet).toHaveCount(0);

  await page.getByRole("link", { name: "Cancel" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Nothing changes for anyone else until you save." }),
  ).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/ideas/${REF}/edit$`));
  await expectNoSeriousAxeIssues(page);

  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByRole("status").filter({ hasText: SAVED })).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: /^Saved at \d{1,2}:\d{2} (am|pm)$/ }),
  ).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});

test("S-06B.rules/2 V-ACC: the desk opened it meanwhile: the refusal, the changes kept, Open the conversation (BLD-C164)", async ({
  page,
}, info) => {
  test.skip(info.project.name === "phone-360", "the same states on a phone: the next test");
  await openEdit(page, PAGE, {
    status: 409,
    json: {
      error: {
        code: "edit_window_closed",
        message:
          "The review desk has just opened it, so it can’t be changed now. Your changes are kept below. Send them as a message instead.",
        opened_by_desk_at: "2026-11-16T10:00:00+05:30",
        to: `/ideas/${REF}/conversation`,
      },
    },
  });
  await page.getByRole("button", { name: "Change how often" }).click();
  await page.getByRole("textbox", { name: "How often" }).fill("About 50 calls a day at one branch");
  await page.getByRole("textbox", { name: "How often" }).press("Enter");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "The review desk has just opened it" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Open the conversation" })).toHaveAttribute(
    "href",
    `/ideas/${REF}/conversation`,
  );
  await expect(page.getByText("About 50 calls a day at one branch")).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});

test("S-06B.rules/5 V-ACC: on a phone the edit page is one column with Save changes in the dock, and passes axe (BLD-C164)", async ({
  page,
}, info) => {
  if (info.project.name === "desktop") await page.setViewportSize({ width: 390, height: 844 });
  await openEdit(page);
  for (const h of [
    "Your problem",
    "Is this sorted right?",
    "Anything that shows it?",
    "Your fix",
    "What happens when you save",
  ]) {
    await expect(page.getByRole("heading", { level: 2, name: h })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "Not personal? Show it" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Change title" })).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: "Add a photo or file A screenshot of the SMS, a call log, or a report with the time or money it costs",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Save changes" })).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});

test("BLD-D035, C-PHONE-TABS.dock, S-06B: at 320 × 640 the capped dock is one column; the shared dock, capped with no page rules, stays one column and scrolls to both ends", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "phone-360", "the dock is fixed to the foot on a phone only");
  await page.setViewportSize({ width: 320, height: 640 });
  await openEdit(page);
  // An unsaved change, then Cancel: the confirm joins the declaration and the buttons in the dock
  await page.getByRole("button", { name: "Change title" }).click();
  const title = page.getByRole("textbox", { name: "Title" });
  await title.fill("Investors call about a redemption not processed");
  await title.press("Enter");
  await expect(page.getByRole("status").filter({ hasText: "Unsaved changes" })).toBeVisible();
  // The dock's Cancel (the task bar at the top has its own)
  await page.locator(".dock.ed-dock").getByRole("link", { name: "Cancel" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Nothing changes for anyone else until you save." }),
  ).toBeVisible();
  await settleMotion(page);

  // S-06B's dock, capped at 45% of the window: every line in it and the buttons' row share one left edge
  const capped = await page.locator(".dock.ed-dock").evaluate((el) => {
    const shown = [...el.children].filter(
      (c) => getComputedStyle(c).position !== "absolute" && c.getBoundingClientRect().height > 0,
    );
    return {
      count: shown.length,
      lefts: [...new Set(shown.map((c) => Math.round(c.getBoundingClientRect().left)))],
      height: el.getBoundingClientRect().height,
    };
  });
  expect(capped.count).toBeGreaterThanOrEqual(3); // the confirm, the declaration, Cancel and Save changes
  expect(capped.lefts, "one column").toHaveLength(1);
  expect(capped.height).toBeLessThanOrEqual(640 * 0.45 + 1);

  // The shared dock alone (no page class), capped the same way and given more than fits: one column, and both its
  // first button (at the foot) and its last (at the top) are reached by scrolling the dock
  const shared = await page.evaluate(() => {
    const dock = document.createElement("div");
    dock.className = "dock";
    dock.style.maxHeight = "160px";
    dock.style.overflowY = "auto";
    for (const n of [1, 2, 3, 4]) {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "btn";
      b.textContent = `Step ${n}`;
      dock.append(b);
    }
    document.body.append(dock);
    const buttons = [...dock.querySelectorAll("button")];
    const seen = (b: Element) => {
      const r = b.getBoundingClientRect();
      const box = dock.getBoundingClientRect();
      return r.top >= box.top - 0.5 && r.bottom <= box.bottom + 0.5;
    };
    const out = {
      lefts: [...new Set(buttons.map((b) => Math.round(b.getBoundingClientRect().left)))],
      overflows: dock.scrollHeight > dock.clientHeight,
      first: false,
      last: false,
    };
    // Both ends of the scroll, whichever sign the browser gives a reversed column's scrollTop
    for (const top of [dock.scrollHeight, -dock.scrollHeight]) {
      dock.scrollTop = top;
      out.first ||= seen(buttons[0]!);
      out.last ||= seen(buttons[buttons.length - 1]!);
    }
    dock.remove();
    return out;
  });
  expect(shared.overflows, "the cap bites").toBe(true);
  expect(shared.lefts, "one column").toHaveLength(1);
  expect(shared.first, "the first button, at the foot, is reached").toBe(true);
  expect(shared.last, "the last button, at the top, is reached").toBe(true);
  await expectNoSeriousAxeIssues(page);
});
