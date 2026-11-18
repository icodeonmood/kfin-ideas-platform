/**
 * S-08, an idea's conversation, in a real browser at phone width (lane F, BLD-F066): the screen on the dev-only page
 * /kit/conversation with made-up content ("Ravi's idea, after teaming up"). axe on the screen, on the box's error,
 * on the @mention list and on the side panel as a sheet (lane D's helper settles motion first and checks reflow at
 * 320px); the mention picker and the sheet by keyboard; touch targets; the timeline as a log. The look pass from lane
 * D's QA (BLD-F078 to F081): the phone's one-row box and the line under the title at 375px, and at 1440px the header
 * row, the solid box with the page's colour under it, and opening at the newest entry. The spec answers the screen's
 * calls itself, so it needs no seeded idea. Synthetic people only: the pack's fictional cast.
 */
import { inflateSync } from "node:zlib";

import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, expectNoSidewaysScroll, PERSONAS, settleMotion, signIn } from "./helpers";

const IDEA = "IDEA-2026-001412";
const TITLE = "Rejection SMS codes confuse investors";
const ADITI = "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b02";
const KAVYA = {
  id: "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b04",
  name: "Kavya Menon",
  first_name: "Kavya",
  initials: "KM",
};
const HELLO = "Thanks @Aditi Sharma for the call list.";
const MINE = "6c1f6a0e-0000-4000-8000-000000000009";

/** Kavya's message as read back: as sent, or once removed (L-CONVO/10). */
function hello(removed: boolean) {
  return {
    type: "message",
    id: MINE,
    from: KAVYA,
    from_label: "You",
    you: true,
    text: removed ? "Message removed" : HELLO,
    files: [],
    at: "2026-11-17T10:12:00+05:30",
    at_label: "Today, 10:12 am",
    mentions: removed ? [] : [{ id: ADITI, name: "Aditi Sharma", first_name: "Aditi", initials: "AS" }],
    mentions_you: false,
    removed,
    ...(removed ? {} : { can_remove_until: "2999-11-17T10:17:00+05:30" }),
  };
}

/** The conversation as read again after Kavya's message: the kit's view plus that message. */
function afterHello(base: Record<string, unknown>, removed = false) {
  const entries = (base.entries as unknown[]) ?? [];
  return { ...base, entries: [...entries, hello(removed)] };
}

/** The screen's calls for IDEA (A-API.inbox), answered here. Returns what was posted. */
async function answerConversation(page: Page, base: Record<string, unknown>) {
  const posted: unknown[] = [];
  await page.route(`**/api/ideas/${IDEA}/conversation/messages`, async (route) => {
    const body = route.request().postDataJSON() as { text: string };
    posted.push(body);
    if (!body.text.trim()) {
      return route.fulfill({
        status: 422,
        json: {
          error: { code: "empty_message", message: "Write a message or attach a file first.", field: "text" },
        },
      });
    }
    return route.fulfill({ status: 201, json: { entry: hello(false), hidden: 0 } });
  });
  let removed = false;
  await page.route(`**/api/ideas/${IDEA}/conversation/messages/*`, (route) => {
    removed = true;
    return route.fulfill({ json: { entry: hello(true) } });
  });
  await page.route(`**/api/ideas/${IDEA}/conversation`, (route) =>
    route.fulfill({ json: posted.length ? afterHello(base, removed) : base }),
  );
  return posted;
}

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "the viewport is set here; one project is enough");
  await signIn(page, PERSONAS.contributor);
});

async function open(page: Page) {
  await page.goto("/kit/conversation");
  await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
}

/** /ideas/:id/conversation is a task screen on a phone (lane D, F-SPACE.shell): the shell marks it data-mode="task" and
 * draws no tab bar. The kit is not a task path, so it takes that shape here; the box measures it again (BLD-F068). */
async function taskScreen(page: Page) {
  await page.evaluate(() => {
    document.querySelector(".shell")?.setAttribute("data-mode", "task");
    const tabs = document.querySelector<HTMLElement>(".ptabs");
    if (tabs) tabs.style.display = "none";
    window.dispatchEvent(new Event("resize"));
  });
  await expect
    .poll(() =>
      page.evaluate(() => document.querySelector<HTMLElement>(".cv")?.style.getPropertyValue("--cv-at")),
    )
    .toBe("0px");
}

test("S-08 at 375px: the compact bar, the timeline as a log, the labelled box and who sees it; axe; no sideways scroll", async ({
  page,
}) => {
  await open(page);
  const log = page.getByRole("log", { name: "Conversation" });
  await expect(log).toContainText("Ravi Nair approved your team-up request. Today, 10:05 am");
  await expect(log).toContainText("Welcome to the crew, Kavya.");
  const box = page.getByRole("textbox", { name: "Message the crew" });
  await expect(box).toBeVisible();
  // PhoneMessages (BLD-F078): who sees it is under the title, beside the faces, and on the page once (strict)
  await expect(page.getByText("The crew and the review desk see this conversation.")).toBeVisible();
  await expect(page.locator("header .cv-seen")).toContainText(
    "The crew and the review desk see this conversation.",
  );
  await expect(page.locator("form.cv-box .cv-sees")).toHaveCount(0);
  // No attach control for the crew (BLD-F063), and none yet for anyone (BLD-F064).
  await expect(page.getByRole("button", { name: "Attach a file" })).toHaveCount(0);
  // Touch targets (F-A11Y): Send and the "i" are 44px or more each way, measured once the shell has arrived (its
  // entrance scales the page a hair: run 44153802713 read Send at 43.87px mid-arrival).
  await settleMotion(page);
  for (const name of ["Send", "Who is in this conversation"]) {
    const b = (await page.getByRole("button", { name, exact: true }).boundingBox())!;
    expect(b.height, name).toBeGreaterThanOrEqual(44);
    expect(b.width, name).toBeGreaterThanOrEqual(44);
  }
  await expectNoSeriousAxeIssues(page);
  await expectNoSidewaysScroll(page);
});

test("BLD-F078, PhoneMessages at 375px on the route's task screen: the box is one row about 90px tall (an empty attach slot, the pill, a round 44px Send named Send, its focus ring visible); who sees it sits under the title; axe", async ({
  page,
}) => {
  await open(page);
  await taskScreen(page);
  await settleMotion(page);
  const form = page.locator("form.cv-box");
  const row = await page.evaluate(() => {
    const r = (el: Element | null) => el!.getBoundingClientRect();
    const form = document.querySelector("form.cv-box")!;
    const send = form.querySelector(".cv-send")!;
    const s = getComputedStyle(send);
    return {
      form: r(form).toJSON() as DOMRect,
      field: r(form.querySelector(".cv-field")).toJSON() as DOMRect,
      send: r(send).toJSON() as DOMRect,
      radius: s.borderTopLeftRadius,
      fill: s.backgroundColor,
    };
  });
  // One row, about 90px with the room under it at the very bottom (PhoneMessages' dock)
  expect(row.form.height).toBeLessThanOrEqual(96);
  expect(row.form.bottom).toBeCloseTo(812, 0);
  expect(row.send.width).toBeCloseTo(44, 0);
  expect(row.send.height).toBeCloseTo(44, 0);
  expect(row.radius).toBe("50%");
  expect(row.fill).toBe("rgb(17, 17, 17)"); // ink
  expect(row.field.height).toBeCloseTo(44, 0);
  expect(row.field.top).toBeCloseTo(row.send.top, 0); // side by side on one row
  expect(row.field.right).toBeLessThan(row.send.left);
  // The attach slot is left empty (BLD-F064): the pill starts 44px and a gap in from the dock's edge
  expect(row.field.left).toBeGreaterThanOrEqual(12 + 44);
  await expect(form.getByRole("button")).toHaveCount(1);
  const send = page.getByRole("button", { name: "Send", exact: true });
  await expect(send).toBeVisible();
  // The header's line, under the title, beside the faces
  const title = (await page.getByRole("heading", { level: 1 }).boundingBox())!;
  const seen = page.locator("header .cv-seen");
  const line = (await seen.boundingBox())!;
  expect(line.y).toBeGreaterThanOrEqual(title.y + title.height);
  await expect(seen.locator(".cv-faces .av")).toHaveCount(4);
  // The focus ring shows on the round Send (F-A11Y; WCAG 2.4.7)
  await page.getByRole("textbox", { name: "Message the crew" }).focus();
  await page.keyboard.press("Tab");
  await expect(send).toBeFocused();
  const ring = await send.evaluate((el) => {
    const s = getComputedStyle(el);
    return { style: s.outlineStyle, width: Number.parseFloat(s.outlineWidth) };
  });
  expect(ring.style).not.toBe("none");
  expect(ring.width).toBeGreaterThanOrEqual(2);
  await expectNoSeriousAxeIssues(page);
  await expectNoSidewaysScroll(page);
});

test("S-08.rules/2 at 375px: Send with nothing typed says so under the box, announced, and the box is marked; axe", async ({
  page,
}) => {
  await open(page);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  // Within the conversation: Next's route announcer is an alert too (run 44153802713).
  const alert = page.getByRole("region", { name: "Conversation" }).getByRole("alert");
  await expect(alert).toHaveText("Write a message or attach a file first.");
  const box = page.getByRole("textbox", { name: "Message the crew" });
  await expect(box).toBeFocused();
  await expect(box).toHaveAttribute("aria-invalid", "true");
  // BLD-F078: the error sits just above the one row, inside the pinned box, and the row stays one row
  await settleMotion(page);
  const err = (await alert.boundingBox())!;
  const field = (await page.locator("form.cv-box .cv-field").boundingBox())!;
  const send = (await page.getByRole("button", { name: "Send", exact: true }).boundingBox())!;
  expect(err.y + err.height).toBeLessThanOrEqual(field.y);
  expect(Math.abs(send.y + send.height - (field.y + field.height))).toBeLessThanOrEqual(1);
  await expectNoSeriousAxeIssues(page);
});

test("S-08 L-CONVO/6 at 375px: the @mention list by keyboard, the id sent, and the message read back; axe with the list open", async ({
  page,
}) => {
  const posted = await answerConversation(page, kitView());
  await open(page);
  const box = page.getByRole("textbox", { name: "Message the crew" });
  await box.click();
  await page.keyboard.type("Thanks @");
  const list = page.getByRole("listbox", { name: "People to mention" });
  await expect(list).toBeVisible();
  await expect(list.getByRole("option")).toHaveCount(3); // never the reader
  for (const [n, name] of ["Ravi Nair", "Aditi Sharma", "Prakash Kumar"].entries()) {
    await expect(list.getByRole("option").nth(n)).toContainText(name);
  }
  await expect(page.getByText("3 people to mention. Use the up and down arrows, then Enter.")).toBeAttached();
  await expectNoSeriousAxeIssues(page);
  await page.keyboard.press("ArrowDown");
  await expect(list.getByRole("option", { name: /Aditi Sharma/ })).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("Enter");
  await expect(list).toBeHidden();
  await expect(box).toHaveValue("Thanks @Aditi Sharma ");
  await page.keyboard.type("for the call list.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText(HELLO, { exact: true })).toBeVisible();
  expect(posted).toEqual([{ text: HELLO, mentions: [ADITI] }]);
  await expect(box).toHaveValue("");
  await expectNoSeriousAxeIssues(page);

  // L-CONVO/10: Remove goes with the message, so focus lands on its line, now "Message removed" (WCAG 2.4.3).
  await page.getByRole("button", { name: "Remove your message from Today, 10:12 am" }).click();
  const line = page.locator(`[id="entry-${MINE}"]`);
  await expect(line).toContainText("Message removed");
  await expect(line).toBeFocused();
  await expect(page.getByRole("button", { name: /^Remove your message/ })).toHaveCount(0);
});

test("S-08.rules/4 at 375px: the 'i' opens In this conversation as a sheet; Escape closes it and focus goes back; axe", async ({
  page,
}) => {
  await open(page);
  const info = page.getByRole("button", { name: "Who is in this conversation" });
  await expect(page.getByRole("heading", { level: 2, name: "In this conversation" })).toBeHidden();
  await info.click();
  await expect(info).toHaveAttribute("aria-expanded", "true");
  const sheet = page.getByRole("complementary", { name: "In this conversation" });
  await expect(sheet).toBeVisible();
  await expect(sheet).toContainText("Aditi Sharma");
  await expect(sheet).toContainText("On the crew");
  await expect(sheet.getByRole("button", { name: "Close" })).toBeFocused();
  await expectNoSeriousAxeIssues(page);
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await expect(info).toBeFocused();
});

/** Meera's 3 questions as lane B's `GET /ideas/:id/question-set` sends them to Kavya (BLD-B249). */
const SET_ID = "6c1f6a0e-0000-4000-8000-000000000013";
function sharerSet() {
  const MEERA = {
    id: "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b05",
    name: "Meera Iyer",
    first_name: "Meera",
    initials: "MI",
  };
  const parts = [
    ["summary", "The problem", "Is it mostly R07, or all rejection codes?"],
    ["often", "How often", "Is the 40 calls a day at one branch, or across Hyderabad?"],
    ["evidence", "Attached", "Can you add a screenshot of the SMS, with the folio hidden?"],
  ];
  return {
    id: SET_ID,
    idea_id: IDEA,
    idea: { id: IDEA, title: TITLE },
    by: { ...MEERA, city: null, area: null },
    state: "seen",
    time_to_answer: "3d",
    sent_at: "2026-11-16T11:20:00+05:30",
    seen_at: "2026-11-16T12:05:00+05:30",
    due_at: new Date(Date.now() + 3 * 86_400_000).toISOString(),
    answered_at: null,
    extended_times: 0,
    reminded_at: null,
    count: 3,
    answered: 0,
    overdue: false,
    questions: parts.map(([part, part_name, text], i) => ({
      id: `6c1f6a0e-0000-4000-8000-00000000002${i}`,
      seq: i + 1,
      part,
      part_name,
      text,
      suggested: false,
      answer: null,
    })),
    countdown: { label: "3 days left to answer", variant: "normal" },
    deadline: "Answer by Thursday 19 November, 6 pm",
    progress: "0 of 3 answered",
    send_label: "Answer at least one question",
  };
}

test("C-QCARD.places S-08 at 375px (BLD-B249, J-TRACK/3): the sharer's open questions are lane B's card, read by the entry's set; axe; no sideways scroll", async ({
  page,
}) => {
  const reads: string[] = [];
  await page.route(`**/api/ideas/${IDEA}/question-set*`, (route) => {
    reads.push(new URL(route.request().url()).search);
    return route.fulfill({ json: sharerSet() });
  });
  await page.goto("/kit/conversation?view=questions");
  await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
  const card = page.getByRole("article", { name: "Meera has 3 questions about your idea" });
  await expect(card).toBeVisible();
  expect([...new Set(reads)]).toEqual([`?set_id=${SET_ID}`]); // only the entry's own set
  await expect(card).toContainText("Is the 40 calls a day at one branch, or across Hyderabad?");
  await expect(card).toContainText("Answer goes to How often");
  await expect(card).toContainText("and each answer is added to its part of your idea.");
  // S-08.rules/1: Answer the questions on the card and in the line above the box, both to S-R3
  const answer = page.getByRole("link", { name: "Answer the questions" });
  await expect(answer).toHaveCount(2);
  await expect(card.getByRole("link", { name: "Answer the questions" })).toHaveAttribute(
    "href",
    `/ideas/${IDEA}/answer`,
  );
  await settleMotion(page);
  await expectNoSeriousAxeIssues(page);
  await expectNoSidewaysScroll(page);
});

/** The kit's people and box, so the stand-in GET can answer with Kavya's message after she sends it. */
function kitView(): Record<string, unknown> {
  return {
    idea: { id: IDEA, title: TITLE, status: "with_review_desk", meta: `${IDEA}, with the review desk` },
    audience: "crew_and_desk",
    header: { whose: "The idea", line: "Ravi Nair’s idea, Investor service, Hyderabad" },
    participants: [
      {
        person: {
          id: "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b01",
          name: "Ravi Nair",
          first_name: "Ravi",
          initials: "RN",
        },
        label: "Ravi Nair",
        doing: "Shared the idea",
        you: false,
      },
      {
        person: { id: ADITI, name: "Aditi Sharma", first_name: "Aditi", initials: "AS" },
        label: "Aditi Sharma",
        doing: "On the crew",
        you: false,
      },
      {
        person: {
          id: "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b03",
          name: "Prakash Kumar",
          first_name: "Prakash",
          initials: "PK",
        },
        label: "Prakash Kumar",
        doing: "On the crew",
        you: false,
      },
      { person: KAVYA, label: "You", doing: "Joined today", you: true },
    ],
    entries: [],
    composer: {
      placeholder: "Message the crew",
      visibility: "The crew and the review desk see this conversation.",
      can_attach: false,
    },
  };
}

/** Twelve messages back and forth after the kit's lines, then Kavya's: long enough to scroll at 375 × 812. */
function longView(): Record<string, unknown> {
  const base = kitView();
  const people = (base.participants as { person: { id: string }; label: string }[]).filter(
    (p) => p.label !== "You",
  );
  const entries: unknown[] = [
    {
      type: "event",
      id: "6c1f6a0e-0000-4000-8000-000000000101",
      code: "teamup.approved_team_only",
      text: "Ravi Nair approved your team-up request. Today, 10:05 am",
      at: "2026-11-17T10:05:00+05:30",
    },
  ];
  for (let i = 0; i < 12; i++) {
    const p = people[i % people.length]!;
    entries.push({
      type: "message",
      id: `6c1f6a0e-0000-4000-8000-0000000002${String(i).padStart(2, "0")}`,
      from: p.person,
      from_label: p.label,
      you: false,
      text: `Call log, day ${i + 1}: most callers asked why the redemption did not go through, and what R07 means.`,
      files: [],
      at: "2026-11-17T10:07:00+05:30",
      at_label: "Today, 10:07 am",
      mentions: [],
      mentions_you: false,
      removed: false,
    });
  }
  return { ...base, entries };
}

/** The box, the tab bar (on the kit the shell still shows one) and the last line of the timeline, as laid out. */
async function layout(page: Page) {
  return page.evaluate(() => {
    const rect = (el: Element | null) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, height: r.height };
    };
    const tabs = document.querySelector(".ptabs");
    return {
      viewport: window.innerHeight,
      scrollY: window.scrollY,
      box: rect(document.querySelector("form.cv-box"))!,
      tabs: tabs && getComputedStyle(tabs).display !== "none" ? rect(tabs) : null,
      last: rect(document.querySelector(".cv-conv > li:last-child"))!,
    };
  });
}

test("S-08.rules/4, PhoneMessages at 375px: the bar reads Conversation; the box stays pinned at the bottom as the timeline scrolls, and the last line and a focused Remove clear it; axe", async ({
  page,
}) => {
  await answerConversation(page, longView());
  await open(page);
  // PhoneMessages.md: Back to the idea, then "Conversation" (the idea's title is the page's h1, under the bar)
  const bar = page.locator(".pnav");
  await expect(bar).toBeVisible();
  await expect(bar.locator(".pnav-t")).toHaveText("Conversation");
  await expect(bar.getByRole("link", { name: "The idea" })).toBeVisible();

  // A long conversation: send, and the read after it brings the twelve messages and Kavya's.
  const box = page.getByRole("textbox", { name: "Message the crew" });
  await box.fill("Thanks @Aditi Sharma for the call list.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText(HELLO, { exact: true })).toBeAttached();
  await expect(page.locator(".cv-conv > li")).toHaveCount(14);
  await page.locator("body").click({ position: { x: 4, y: 200 } }); // out of the box, so no keyboard is pretended
  await settleMotion(page);

  // Pinned: at the top, in the middle and at the end the box sits in the same place, on the tab bar here (the kit
  // keeps the shell's tab bar; on the real route lane D's shell takes it away and the box sits at the bottom).
  const seen: { top: number; bottom: number }[] = [];
  for (const where of ["top", "middle", "end"] as const) {
    await page.evaluate((w) => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      window.scrollTo(0, w === "top" ? 0 : w === "middle" ? max / 2 : max);
    }, where);
    const l = await layout(page);
    if (where === "top") expect(l.scrollY).toBe(0);
    else expect(l.scrollY, `${where}: the page scrolls`).toBeGreaterThan(200);
    const floor = l.tabs ? l.tabs.top : l.viewport;
    expect(
      Math.abs(l.box.bottom - floor),
      `${where}: the box sits on the tab bar or the bottom`,
    ).toBeLessThanOrEqual(1);
    expect(l.box.top, `${where}: the box is on screen`).toBeGreaterThan(l.viewport / 2);
    await expect(box).toBeInViewport();
    await expect(page.getByRole("button", { name: "Send", exact: true })).toBeInViewport();
    seen.push(l.box);
    if (where === "end") {
      // The last line is never under the box (S-08.rules/4)
      expect(l.last.bottom, "the last line clears the box").toBeLessThanOrEqual(l.box.top);
    }
  }
  expect(seen.every((b) => Math.abs(b.top - seen[0]!.top) <= 1)).toBe(true);

  // Focus not hidden (WCAG 2.4.11): from the top, focus moves to Remove on Kavya's message, the timeline's last
  // control; the page brings it out from under the box.
  await page.evaluate(() => window.scrollTo(0, 0));
  const remove = page.getByRole("button", { name: "Remove your message from Today, 10:12 am" });
  await remove.focus();
  await expect(remove).toBeFocused();
  const r = (await remove.boundingBox())!;
  const l = await layout(page);
  expect(r.y + r.height, "Remove clears the box").toBeLessThanOrEqual(l.box.top);
  expect(r.y).toBeGreaterThanOrEqual(0);

  await expectNoSeriousAxeIssues(page);
  await expectNoSidewaysScroll(page);
});

test("S-08.rules/4, F-SPACE.shell at 375px on the route's task screen: no tab bar, so the box sits at the very bottom with the safe area only, and the last line clears it (BLD-F068)", async ({
  page,
}) => {
  await answerConversation(page, longView());
  await open(page);
  await page
    .getByRole("textbox", { name: "Message the crew" })
    .fill("Thanks @Aditi Sharma for the call list.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".cv-conv > li")).toHaveCount(14);
  // /ideas/:id/conversation is a task screen on a phone (lane D, F-SPACE.shell): the shell marks it data-mode="task"
  // and draws no tab bar. The kit is not a task path, so it takes that shape here; the box measures it again.
  await page.evaluate(() => {
    document.querySelector(".shell")?.setAttribute("data-mode", "task");
    const tabs = document.querySelector<HTMLElement>(".ptabs");
    if (tabs) tabs.style.display = "none";
    window.dispatchEvent(new Event("resize"));
  });
  await expect
    .poll(() =>
      page.evaluate(() => document.querySelector<HTMLElement>(".cv")?.style.getPropertyValue("--cv-at")),
    )
    .toBe("0px");
  await settleMotion(page);
  const vars = await page.evaluate(() => {
    const cv = document.querySelector<HTMLElement>(".cv")!;
    return {
      safe: cv.style.getPropertyValue("--cv-safe"),
      mainPad: getComputedStyle(document.querySelector("main")!).paddingBottom,
    };
  });
  expect(vars.safe).toBe("1"); // the box takes the safe area itself
  expect(vars.mainPad).toBe("120px"); // lane D's room for a task screen's dock
  for (const where of ["top", "end"] as const) {
    await page.evaluate(
      (w) => window.scrollTo(0, w === "top" ? 0 : document.documentElement.scrollHeight),
      where,
    );
    const l = await layout(page);
    expect(l.tabs).toBeNull();
    expect(
      Math.abs(l.box.bottom - l.viewport),
      `${where}: the box sits at the very bottom`,
    ).toBeLessThanOrEqual(1);
    if (where === "end") expect(l.last.bottom, "the last line clears the box").toBeLessThanOrEqual(l.box.top);
  }
  await expectNoSeriousAxeIssues(page);
  await expectNoSidewaysScroll(page);
});

test("L-MERGE.effects/6 at 375px: closed while open, a merged idea's closing line takes the box's place with no room kept under it (BLD-F068)", async ({
  page,
}) => {
  const closed = "This idea is now part of another one. Write in IDEA-2026-001481’s conversation.";
  await page.route(`**/api/ideas/${IDEA}/conversation/messages`, (route) =>
    route.fulfill({
      status: 409,
      json: { error: { code: "conversation_closed", message: "This conversation takes no new messages." } },
    }),
  );
  await page.route(`**/api/ideas/${IDEA}/conversation`, (route) =>
    route.fulfill({ json: { ...kitView(), composer: { ...(kitView().composer as object), closed } } }),
  );
  await open(page);
  await expect(page.locator(".cv")).toHaveAttribute("data-box", "open");
  await page.getByRole("textbox", { name: "Message the crew" }).fill("Thanks for the call list.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText(closed)).toBeVisible();
  await expect(page.locator("form.cv-box")).toHaveCount(0);
  await expect(page.locator(".cv")).toHaveAttribute("data-box", "closed");
  await settleMotion(page);
  const gap = await page.evaluate(() => {
    const main = document.querySelector("main")!;
    const note = document.querySelector(".cv-closed")!.getBoundingClientRect();
    const end = main.getBoundingClientRect().bottom;
    return {
      cvMain: getComputedStyle(document.querySelector(".cv-main")!).paddingBottom,
      below: end - note.bottom, // the closing line to the end of the page
      mainPad: Number.parseFloat(getComputedStyle(main).paddingBottom),
    };
  });
  expect(gap.cvMain).toBe("0px");
  // Under the closing line: only the shell's own padding (and the side panel's place, hidden on a phone)
  expect(gap.below).toBeLessThanOrEqual(gap.mainPad + 1);
  await expectNoSeriousAxeIssues(page);
});

test("S-08 at 375px: the box has no resize grip; it grows with its words to 120px, then scrolls (BLD-F068)", async ({
  page,
}) => {
  await open(page);
  const box = page.getByRole("textbox", { name: "Message the crew" });
  expect(await box.evaluate((el) => getComputedStyle(el).resize)).toBe("none");
  const one = (await box.boundingBox())!.height;
  await box.fill("Line one\nLine two\nLine three");
  const three = (await box.boundingBox())!.height;
  expect(three).toBeGreaterThan(one);
  await box.fill(Array.from({ length: 12 }, (_, i) => `Line ${i + 1}`).join("\n"));
  const many = await box.evaluate((el) => ({ h: el.getBoundingClientRect().height, sh: el.scrollHeight }));
  expect(many.h).toBeLessThanOrEqual(120.5);
  expect(many.sh).toBeGreaterThan(many.h); // past the cap it scrolls
  await box.fill("");
  expect((await box.boundingBox())!.height).toBeLessThanOrEqual(one + 0.5); // and shrinks back once sent or cleared
});

test("L-TEAMUP.rules/9 at 375px: a Say hello link (#say-hello) lands with the cursor in the box, and the hint comes off the address (BLD-F069); axe", async ({
  page,
}) => {
  await page.goto("/kit/conversation#say-hello");
  await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
  const box = page.getByRole("textbox", { name: "Message the crew" });
  await expect(box).toBeFocused();
  await expect(page).toHaveURL(/\/kit\/conversation$/);
  await expect(box).toBeInViewport();
  await settleMotion(page);
  await expectNoSeriousAxeIssues(page);

  // A reload, without the hint, leaves focus alone.
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
  await expect(box).not.toBeFocused();
});

test("L-TEAMUP.rules/9 with S-06B.rules/2 at 375px: words carried over from the edit page and a #say-hello arrival: the words wait in the box with the cursor at their end, and nothing is sent (BLD-F069, BLD-C165)", async ({
  page,
}) => {
  const words = "How often: About 50 calls a day at one branch";
  const writes: string[] = [];
  page.on("request", (r) => {
    if (r.method() !== "GET" && r.url().includes("/conversation")) writes.push(r.url());
  });
  // The edit page kept the words in this tab (S-06B "Open the conversation"); the arrival is one navigation.
  await page.addInitScript(
    ([key, w]) => {
      if (window.location.pathname === "/kit/conversation") window.sessionStorage.setItem(key, w);
    },
    [`1pc.conversation.prefill.${IDEA}`, words] as const,
  );
  await page.goto("/kit/conversation#say-hello");
  const box = page.getByRole("textbox", { name: "Message the crew" });
  await expect(box).toHaveValue(words);
  await expect(box).toBeFocused();
  expect(await box.evaluate((el: HTMLTextAreaElement) => [el.selectionStart, el.selectionEnd])).toEqual([
    words.length,
    words.length,
  ]);
  await expect(page).toHaveURL(/\/kit\/conversation$/);
  expect(
    await page.evaluate((key) => window.sessionStorage.getItem(key), `1pc.conversation.prefill.${IDEA}`),
  ).toBeNull();
  await page.keyboard.type(" and more");
  await expect(box).toHaveValue(`${words} and more`);
  expect(writes).toEqual([]);
});

test("BLD-F081 at 375px: a long conversation opens at its newest entry, just above the box, and focus stays where it was; with #say-hello the cursor is in the box as well", async ({
  page,
}) => {
  for (const hello of [true, false]) {
    await page.goto("about:blank"); // a new document each time: a hash alone would not load the screen again
    await page.goto(`/kit/conversation?view=long${hello ? "#say-hello" : ""}`);
    await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeAttached();
    const last = page.locator(".cv-conv > li:last-child");
    await expect(last).toContainText("Call log, day 12");
    // Measured once the screen has arrived: while lane D's arrival moves .cv, the pinned box is drawn relative to it
    // (a transformed ancestor), a little above its place (production build, CI run 44242807052)
    await settleMotion(page);
    await expect(last).toBeInViewport();
    const at = await page.evaluate(() => ({
      y: window.scrollY,
      end: document.documentElement.scrollHeight - window.innerHeight,
      last: document.querySelector(".cv-conv > li:last-child")!.getBoundingClientRect().bottom,
      box: document.querySelector("form.cv-box")!.getBoundingClientRect().top,
      focus: document.activeElement?.tagName,
    }));
    expect(at.y).toBeGreaterThan(0);
    expect(Math.abs(at.y - at.end)).toBeLessThanOrEqual(1);
    expect(at.last, "the newest entry clears the box").toBeLessThanOrEqual(at.box);
    if (hello) await expect(page.getByRole("textbox", { name: "Message the crew" })).toBeFocused();
    else expect(at.focus).toBe("BODY");
  }
  // A short conversation fits the window: it opens at the top
  await open(page);
  expect(await page.evaluate(() => window.scrollY)).toBe(0);
});

/** A screenshot's pixels (Chromium writes 8-bit RGB or RGBA, not interlaced): read with node's zlib, no package. */
function pixels(png: Buffer): { width: number; height: number; at: (x: number, y: number) => number[] } {
  let pos = 8;
  let width = 0;
  let height = 0;
  let bpp = 4;
  const data: Buffer[] = [];
  while (pos < png.length) {
    const len = png.readUInt32BE(pos);
    const type = png.toString("ascii", pos + 4, pos + 8);
    const chunk = png.subarray(pos + 8, pos + 8 + len);
    if (type === "IHDR") {
      width = chunk.readUInt32BE(0);
      height = chunk.readUInt32BE(4);
      bpp = chunk[9] === 2 ? 3 : 4;
    } else if (type === "IDAT") data.push(chunk);
    else if (type === "IEND") break;
    pos += 12 + len;
  }
  const raw = inflateSync(Buffer.concat(data));
  const stride = width * bpp;
  const out = Buffer.alloc(height * stride);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)]!;
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? out[y * stride + x - bpp]! : 0;
      const b = y > 0 ? out[(y - 1) * stride + x]! : 0;
      const c = x >= bpp && y > 0 ? out[(y - 1) * stride + x - bpp]! : 0;
      let v = raw[y * (stride + 1) + 1 + x]!;
      if (filter === 1) v += a;
      else if (filter === 2) v += b;
      else if (filter === 3) v += (a + b) >> 1;
      else if (filter === 4) {
        const p = a + b - c;
        const [pa, pb, pc] = [Math.abs(p - a), Math.abs(p - b), Math.abs(p - c)];
        v += pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      }
      out[y * stride + x] = v & 255;
    }
  }
  return { width, height, at: (x, y) => [...out.subarray(y * stride + x * bpp, y * stride + x * bpp + 3)] };
}

test.describe("S-08 at 1440px (Messages.jpg)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("BLD-F079: the stage pill, the reference and the line share one row, and the title runs the column's width; axe; no sideways scroll", async ({
    page,
  }) => {
    await open(page);
    await settleMotion(page);
    const head = await page.evaluate(() => {
      const r = (el: Element | null) => el!.getBoundingClientRect().toJSON() as DOMRect;
      const meta = document.querySelector("header .cv-meta")!;
      return {
        pill: r(meta.querySelector(".pill")),
        ref: r(meta.querySelector(".pill + span")),
        line: r(meta.querySelector(".cv-line")),
        title: r(document.querySelector("h1")),
        column: r(document.querySelector(".cv-main")),
      };
    });
    const mid = (b: DOMRect) => b.top + b.height / 2;
    expect(Math.abs(mid(head.ref) - mid(head.pill))).toBeLessThanOrEqual(2);
    expect(Math.abs(mid(head.line) - mid(head.pill))).toBeLessThanOrEqual(2);
    expect(head.line.left).toBeGreaterThan(head.ref.right);
    // The title is as wide as the timeline's column (it was 26ch, 628px; the board's column is about 705px)
    expect(head.title.width).toBeGreaterThanOrEqual(head.column.width - 1);
    expect(head.title.right).toBeLessThanOrEqual(head.column.right + 1);
    await expect(page.getByRole("heading", { level: 1, name: TITLE })).toHaveCount(1);
    expect(head.title.height).toBeLessThan(70); // "Rejection SMS codes confuse investors" on one line
    // Wider than a phone who sees it is in the box beside Send (Messages.jpg), not under the title, and on the page
    // once (lane G's journeys find it by its words, strict)
    await expect(page.locator("header .cv-seen")).toHaveCount(0);
    await expect(page.getByText("The crew and the review desk see this conversation.")).toBeVisible();
    await expect(page.locator("form.cv-box .cv-sees")).toHaveText(
      "The crew and the review desk see this conversation.",
    );
    const send = page.getByRole("button", { name: "Send", exact: true });
    await expect(send.locator('.btn-lbl:not([aria-hidden="true"]) .cv-send-t')).toBeVisible(); // the word, as drawn
    await expect(send.locator(".cv-send-ic")).toBeHidden(); // the arrow is the phone's
    await expectNoSeriousAxeIssues(page);
    await expectNoSidewaysScroll(page);
  });

  test("BLD-F080: the sticky box is solid, and nothing scrolling under it shows between it and the window's edge; axe", async ({
    page,
  }) => {
    await page.goto("/kit/conversation?view=long");
    await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeAttached();
    await settleMotion(page);
    // From the top: the box is stuck 20px above the edge with messages running under it
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    const at = await page.evaluate(() => {
      const form = document.querySelector("form.cv-box")!;
      const r = form.getBoundingClientRect();
      const s = getComputedStyle(form);
      const under = document.elementFromPoint(r.left + 40, window.innerHeight - 8);
      return {
        box: r.toJSON() as DOMRect,
        viewport: window.innerHeight,
        fill: s.backgroundColor,
        blur: s.backdropFilter,
        under: under?.closest(".cv-msg") ? "message" : (under?.tagName ?? null),
      };
    });
    expect(at.fill).toBe("rgb(255, 255, 255)");
    expect(at.blur).toBe("none");
    expect(Math.abs(at.viewport - at.box.bottom - 20)).toBeLessThanOrEqual(1);
    expect(at.under, "a message runs under the gap").toBe("message");
    // The gap from the box to the window's edge, across the box less 100px at each side (where its soft shadow rounds
    // off): the page's colour only, with that shadow fading through it evenly row by row; never a bubble's edge or a
    // word (a bubble is 600px at most, so its edge falls inside this strip)
    const clip = {
      x: Math.round(at.box.left + 100),
      y: Math.ceil(at.box.bottom) + 1,
      width: Math.round(at.box.width - 200),
      height: Math.floor(at.viewport - at.box.bottom) - 2,
    };
    const shot = pixels(await page.screenshot({ clip, animations: "disabled", caret: "hide" }));
    for (let y = 0; y < shot.height; y++) {
      const row = Array.from({ length: shot.width }, (_, x) => shot.at(x, y));
      for (let ch = 0; ch < 3; ch++) {
        const vals = row.map((p) => p[ch]!);
        expect(Math.max(...vals) - Math.min(...vals), `row ${y} of the gap is even`).toBeLessThanOrEqual(3);
      }
    }
    // and never lighter than the page's colour: a bubble or a card under it is white (the shadow only darkens)
    const paper = (await page.evaluate(() => getComputedStyle(document.body).backgroundColor))
      .match(/\d+/g)!
      .map(Number);
    for (let y = 0; y < shot.height; y++) {
      const p = shot.at(Math.floor(shot.width / 2), y);
      for (let ch = 0; ch < 3; ch++) expect(p[ch]!, `row ${y}`).toBeLessThanOrEqual(paper[ch]! + 1);
    }
    await expectNoSeriousAxeIssues(page);
  });

  test("BLD-F081: a long conversation opens at its newest entry, just above the box", async ({ page }) => {
    await page.goto("/kit/conversation?view=long");
    await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeAttached();
    const last = page.locator(".cv-conv > li:last-child");
    await expect(last).toContainText("Call log, day 12");
    await settleMotion(page); // measured once the screen has arrived
    await expect(last).toBeInViewport();
    const at = await page.evaluate(() => ({
      y: window.scrollY,
      end: document.documentElement.scrollHeight - window.innerHeight,
      last: document.querySelector(".cv-conv > li:last-child")!.getBoundingClientRect().bottom,
      box: document.querySelector("form.cv-box")!.getBoundingClientRect().top,
    }));
    expect(Math.abs(at.y - at.end)).toBeLessThanOrEqual(1);
    expect(at.last).toBeLessThanOrEqual(at.box);
  });
});
