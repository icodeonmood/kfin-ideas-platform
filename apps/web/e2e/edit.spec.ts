/**
 * S-06B "Edit after sharing" in the browser (BLD-C164): the page in its drawn states passes axe (WCAG 2.1 AA, colour
 * contrast included) with no sideways scroll, on a laptop and on a phone (V-ACC, S-06B.rules/5), and the boards'
 * "Announced" lines are live regions: "Unsaved changes", "Confirmed when you shared it. …", "Checked", "Checking for
 * personal details", the file and link messages, "Saved at …" and "Saved. The review desk will see the latest
 * version." The page and the shell are real; the idea's own API answers are synthetic and served by `page.route`, so
 * the screen is checked whatever the seed holds. The journeys (J-RECOVER/7–10 and /15 on S-06B) walk the real routes.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

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

/**
 * QA ONLY, lane D's branch d/qa-nowrap-phone-1, never merged: S-06B's in-page phone dock (`div.dock.ed-dock`, main
 * before BLD-C241) with lane C's nowrap fix. When the dock's lines are taller than 45% of a short screen, the dock
 * keeps one column and scrolls inside; nothing wraps into a second column off its right edge. Closed at 320x640 and
 * 360x640, Cancel's confirm at 320x568, and the dock at rest at 320x568. Synthetic data only.
 */
const QA_SHOTS = join(__dirname, "..", "test-results", "qa-shots");
type QaBox = { top: number; bottom: number; left: number; right: number; height: number; width: number };
async function qaDock(page: Page) {
  return page.evaluate(() => {
    const box = (el: Element | null | undefined): QaBox | null => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height, width: r.width };
    };
    const html = document.documentElement;
    const dock = document.querySelector<HTMLElement>(".dock.ed-dock");
    const acts = dock?.querySelector(".ed-acts");
    const cs = dock ? getComputedStyle(dock) : null;
    // The dock's first line in the flow (an empty live region is absolute and takes no room)
    const first = dock ? [...dock.children].find((c) => getComputedStyle(c).position !== "absolute") : undefined;
    return {
      justify: cs?.justifyContent ?? "",
      padTop: cs ? parseFloat(cs.paddingTop) + parseFloat(cs.borderTopWidth) : 0,
      first: box(first),
      vw: window.innerWidth,
      vh: window.innerHeight,
      sideways: html.scrollWidth - html.clientWidth,
      wrap: cs?.flexWrap ?? "",
      dir: cs?.flexDirection ?? "",
      dock: box(dock),
      inner: dock
        ? { sw: dock.scrollWidth, cw: dock.clientWidth, sh: dock.scrollHeight, ch: dock.clientHeight, st: dock.scrollTop }
        : null,
      acts: box(acts),
      cancel: box(acts?.querySelector("a")),
      save: box(acts?.querySelector("button")),
      msg: box(dock?.querySelector(".bmsg")),
    };
  });
}

async function qaOpen(page: Page, save?: { status: number; json: object }) {
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await serveIdea(page, PAGE, save);
  await page.goto(`/ideas/${REF}/edit`);
  await expect(page.getByRole("heading", { level: 1, name: "Edit your problem" })).toBeVisible();
  // The page's arrival moves its box, which holds main's in-page fixed dock until it ends (BLD-D028's reason)
  await settleMotion(page);
}

async function qaChangeTitle(page: Page) {
  await page.getByRole("button", { name: "Change title" }).click();
  await page.getByRole("textbox", { name: "Title" }).fill("Investors call about a redemption not processed");
  await page.getByRole("textbox", { name: "Title" }).press("Enter");
}

const CLOSED = {
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
};

test("QA (lane D, never merged): S-06B's phone dock keeps one column and scrolls inside on short screens (lane C nowrap)", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "phone-360", "phone only");
  test.setTimeout(120_000);
  mkdirSync(QA_SHOTS, { recursive: true });
  const log: Record<string, unknown> = {};

  /** Measures and shoots the dock, then scrolls it to its end and checks Cancel and Save changes are inside it. */
  const check = async (name: string) => {
    await settleMotion(page);
    await page.locator(".dock.ed-dock").evaluate((el) => el.scrollTo(0, 0));
    const g = await qaDock(page);
    log[name] = g;
    await page.screenshot({ path: join(QA_SHOTS, `${name}.png`) });
    expect.soft(g.wrap, `${name}: the dock never wraps`).toBe("nowrap");
    // Overflow goes down, where the dock scrolls to it; never up past its top edge, where nothing can
    expect
      .soft(g.first!.top, `${name}: the first line starts inside the dock, under its padding`)
      .toBeGreaterThanOrEqual(g.dock!.top + g.padTop - 0.5);
    if (g.msg) {
      expect.soft(g.msg.top, `${name}: the message's top is in the dock`).toBeGreaterThanOrEqual(g.dock!.top);
    }
    expect.soft(Math.abs((g.dock?.bottom ?? 0) - g.vh), `${name}: on the screen's foot`).toBeLessThan(1);
    expect.soft(g.dock!.height, `${name}: within 45% of the screen`).toBeLessThanOrEqual(g.vh * 0.45 + 1);
    expect.soft(g.inner!.sw, `${name}: nothing sideways inside the dock`).toBeLessThanOrEqual(g.inner!.cw);
    expect.soft(g.acts!.left, `${name}: the buttons start inside the dock`).toBeGreaterThanOrEqual(g.dock!.left);
    expect.soft(g.acts!.right, `${name}: the buttons end inside the dock`).toBeLessThanOrEqual(g.dock!.right + 0.5);
    expect.soft(g.sideways, `${name}: no sideways scroll on the page`).toBeLessThanOrEqual(0);
    // Scrolled to its end, the dock shows Cancel and Save changes in full
    await page.locator(".dock.ed-dock").evaluate((el) => el.scrollTo(0, el.scrollHeight));
    const e = await qaDock(page);
    log[`${name}-end`] = e;
    await page.screenshot({ path: join(QA_SHOTS, `${name}-end.png`) });
    for (const [what, b] of [
      ["Cancel", e.cancel],
      ["Save changes", e.save],
    ] as const) {
      if (!b) continue; // Cancel is not there once saved
      expect.soft(b.top, `${name}: ${what} is in the dock's view at its end`).toBeGreaterThanOrEqual(e.dock!.top - 0.5);
      expect.soft(b.bottom, `${name}: ${what} is in the dock's view at its end`).toBeLessThanOrEqual(e.dock!.bottom + 0.5);
      expect.soft(b.right, `${name}: ${what} is not off the dock's right edge`).toBeLessThanOrEqual(e.dock!.right + 0.5);
    }
    await expectNoSeriousAxeIssues(page);
    return g;
  };

  /** Keyboard: focusing the dock's control brings it into the dock's view (scrolled back to the top first). */
  const focusSeen = async (name: string, control: "Cancel" | "Save changes") => {
    await page.locator(".dock.ed-dock").evaluate((el) => el.scrollTo(0, 0));
    const target =
      control === "Cancel"
        ? page.locator(".ed-dock").getByRole("link", { name: "Cancel" })
        : page.locator(".ed-dock").getByRole("button", { name: "Save changes" });
    await target.focus();
    const g = await qaDock(page);
    const b = control === "Cancel" ? g.cancel : g.save;
    log[`${name}-focus`] = g;
    expect.soft(b!.bottom, `${name}: focused ${control} is in the dock's view`).toBeLessThanOrEqual(g.dock!.bottom + 0.5);
    expect.soft(b!.top, `${name}: focused ${control} is in the dock's view`).toBeGreaterThanOrEqual(g.dock!.top - 0.5);
  };

  await signIn(page, PERSONAS.contributor);

  // Closed, the tallest line: 320x640 and 360x640
  for (const [w, h] of [
    [320, 640],
    [360, 640],
  ] as const) {
    await page.setViewportSize({ width: w, height: h });
    await qaOpen(page, CLOSED);
    await qaChangeTitle(page);
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.locator(".ed-dock .bmsg.bad")).toBeVisible();
    await check(`01-closed-${w}x${h}`);
    await focusSeen(`01-closed-${w}x${h}`, "Cancel");
  }

  // At rest, then Cancel's confirm, at 320x568
  await page.setViewportSize({ width: 320, height: 568 });
  await qaOpen(page);
  await check("02-rest-320x568");
  await qaChangeTitle(page);
  await page.locator(".ed-dock").getByRole("link", { name: "Cancel" }).click();
  await expect(page.locator(".ed-dock .bmsg.warn")).toBeVisible();
  await check("03-confirm-320x568");
  await focusSeen("03-confirm-320x568", "Save changes");

  writeFileSync(join(QA_SHOTS, "nowrap-phone.json"), JSON.stringify(log, null, 2));
});
