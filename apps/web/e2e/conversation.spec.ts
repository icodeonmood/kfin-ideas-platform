/**
 * S-08, an idea's conversation, in a real browser at phone width (lane F, BLD-F066): the screen on the dev-only page
 * /kit/conversation with made-up content ("Ravi's idea, after teaming up"). axe on the screen, on the box's error,
 * on the @mention list and on the side panel as a sheet (lane D's helper settles motion first and checks reflow at
 * 320px); the mention picker and the sheet by keyboard; touch targets; the timeline as a log. The spec answers the
 * screen's calls itself, so it needs no seeded idea. Synthetic people only: the pack's fictional cast.
 */
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

test("S-08 at 375px: the compact bar, the timeline as a log, the labelled box and who sees it; axe; no sideways scroll", async ({
  page,
}) => {
  await open(page);
  const log = page.getByRole("log", { name: "Conversation" });
  await expect(log).toContainText("Ravi Nair approved your team-up request. Today, 10:05 am");
  await expect(log).toContainText("Welcome to the crew, Kavya.");
  const box = page.getByRole("textbox", { name: "Message the crew" });
  await expect(box).toBeVisible();
  await expect(page.getByText("The crew and the review desk see this conversation.")).toBeVisible();
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
