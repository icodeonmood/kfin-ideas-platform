/**
 * S-08, an idea's conversation, in a real browser at phone width (lane F, BLD-F066): the screen on the dev-only page
 * /kit/conversation with made-up content ("Ravi's idea, after teaming up"). axe on the screen, on the box's error,
 * on the @mention list and on the side panel as a sheet (lane D's helper settles motion first and checks reflow at
 * 320px); the mention picker and the sheet by keyboard; touch targets; the timeline as a log. The spec answers the
 * screen's calls itself, so it needs no seeded idea. Synthetic people only: the pack's fictional cast.
 */
import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, expectNoSidewaysScroll, PERSONAS, signIn } from "./helpers";

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

/** The conversation as read again after Kavya's message: the kit's view plus that message. */
function afterHello(base: Record<string, unknown>) {
  const entries = (base.entries as unknown[]) ?? [];
  return {
    ...base,
    entries: [
      ...entries,
      {
        type: "message",
        id: "6c1f6a0e-0000-4000-8000-000000000009",
        from: KAVYA,
        from_label: "You",
        you: true,
        text: HELLO,
        files: [],
        at: "2026-11-17T10:12:00+05:30",
        at_label: "Today, 10:12 am",
        mentions: [{ id: ADITI, name: "Aditi Sharma", first_name: "Aditi", initials: "AS" }],
        mentions_you: false,
        removed: false,
        can_remove_until: "2999-11-17T10:17:00+05:30",
      },
    ],
  };
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
    return route.fulfill({ status: 201, json: { entry: null, hidden: 0 } });
  });
  await page.route(`**/api/ideas/${IDEA}/conversation`, (route) =>
    route.fulfill({ json: posted.length ? afterHello(base) : base }),
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
  // Touch targets (F-A11Y): Send and the "i" are 44px or more each way.
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
  const alert = page.getByRole("alert");
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
