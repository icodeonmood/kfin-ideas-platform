/**
 * S-08's "+" in a real browser (lane F, BLD-F095; DEC-124, walk item WF-01; S-08.layout/3, C-PROMPT.attach, C-FILE):
 * on the dev-only page /kit/conversation, as the sharer (`?view=questions`, `composer.can_attach`) and as the crew
 * (the default view, which may not attach, BLD-F063). The "+" first in the box's tool row; the picker with Home's
 * words, axe with it open at 375px and 1440px; Escape back to the "+"; a small synthetic text file through the picker's
 * "browse" goes to POST /api/files with the idea's reference and `for: "conversation"`, its row in the box turns
 * Checked as the screen asks again, and it goes with the message, which then shows the file with View on
 * /api/files/:id/view. The spec answers the screen's calls itself, so it needs no seeded idea and nothing reaches the
 * worker. Synthetic people, words and files only.
 */
import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, settleMotion, signIn } from "./helpers";

const IDEA = "IDEA-2026-001412";
const TITLE = "Rejection SMS codes confuse investors";
const PLUS = "Add files, a folder or a link";
const LINK_LINE =
  "SharePoint, Teams and 1% Club links are marked internal. Anything else is marked external.";
const FILE_ID = "ATT-2026-000901";
const NAME = "branch-call-log.md";
const WORDS = "The call log for week 47.";
const KAVYA = {
  id: "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b04",
  name: "Kavya Menon",
  first_name: "Kavya",
  initials: "KM",
};
const DESK = { id: "", name: "The review desk", first_name: "The review desk", initials: "" };
const CONFIG = {
  limit_mb: 25,
  types: ["pdf", "md", "png", "xlsx"],
  help_text: "PDF, Markdown, images or Excel or a whole folder, up to 25 MB each.",
};

/** The file as `POST /api/files` and `GET /api/files/:id` answer for its uploader (A-API.files). */
function fileItem(state: "checking" | "checked") {
  return {
    id: FILE_ID,
    kind: "file",
    name: NAME,
    type: "text/markdown",
    size: 41,
    state,
    added_by: KAVYA,
    added_at: "2026-11-21T10:10:00+05:30",
    ...(state === "checked" ? { view_url: `/api/files/${FILE_ID}/view` } : {}),
  };
}

/** Kavya's message with her file, as the worker returns it (BLD-F095: View opens through /api/files/:id/view). */
function sent() {
  return {
    type: "message",
    id: "6c1f6a0e-0000-4000-8000-000000000019",
    from: KAVYA,
    from_label: "You",
    you: true,
    text: WORDS,
    files: [{ ...fileItem("checked"), type: "MD" }],
    at: "2026-11-21T10:12:00+05:30",
    at_label: "Today, 10:12 am",
    mentions: [],
    mentions_you: false,
    removed: false,
  };
}

/** Kavya's own idea as she reads it again after sending: she may attach (BLD-F063). */
function sharerView(entries: unknown[]) {
  return {
    idea: { id: IDEA, title: TITLE, status: "needs_you", meta: `${IDEA}, needs you` },
    audience: "you_and_desk",
    header: { whose: "Your idea", line: "Your idea, shared Monday 9 November" },
    participants: [
      { person: DESK, label: "The review desk", doing: "Reviewing it", you: false },
      { person: KAVYA, label: "You", doing: "Shared the idea", you: true },
    ],
    entries,
    composer: {
      placeholder: "Message the review desk",
      visibility: "Only you and the review desk see this conversation.",
      can_attach: true,
    },
  };
}

/** The screen's calls, answered here. Returns how many files were posted and the messages posted. The fields of each
 * upload are read in the page as it sends them (`fields`), since a request carrying a file may not hand its body to
 * the route. */
async function answer(page: Page) {
  const uploads: number[] = [];
  const posted: unknown[] = [];
  await page.addInitScript(() => {
    const w = window as unknown as { __uploads: Record<string, string>[] };
    w.__uploads = [];
    const send = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
      const body = init?.body;
      if (/\/api\/files$/.test(url) && body instanceof FormData) {
        const out: Record<string, string> = {};
        body.forEach((v, k) => {
          out[k] = typeof v === "string" ? v : v.name;
        });
        w.__uploads.push(out);
      }
      return send(input, init);
    };
  });
  // Lane B's card reads its set; refused here, so the plain entry shows (BLD-F065)
  await page.route(`**/api/ideas/${IDEA}/question-set*`, (route) =>
    route.fulfill({ status: 404, json: { error: { code: "not_found", message: "" } } }),
  );
  await page.route("**/api/config/uploads", (route) => route.fulfill({ json: CONFIG }));
  await page.route("**/api/files", (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    uploads.push(1);
    return route.fulfill({ status: 201, json: fileItem("checking") });
  });
  // The check finishes: the screen asks again (C-FILE.row polling) and reads it checked
  await page.route(`**/api/files/${FILE_ID}`, (route) =>
    route.request().method() === "DELETE"
      ? route.fulfill({ status: 204 })
      : route.fulfill({ json: fileItem("checked") }),
  );
  await page.route(`**/api/ideas/${IDEA}/conversation/messages`, (route) => {
    posted.push(route.request().postDataJSON());
    return route.fulfill({ status: 201, json: { entry: sent(), hidden: 0 } });
  });
  await page.route(`**/api/ideas/${IDEA}/conversation`, (route) =>
    route.fulfill({ json: sharerView(posted.length ? [sent()] : []) }),
  );
  return { uploads, posted };
}

async function openAsSharer(page: Page) {
  await page.goto("/kit/conversation?view=questions");
  await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
}

/** The "+" opens the picker it names (aria-controls); the picker, as Home draws it, without the link line. */
async function openPicker(page: Page) {
  const plus = page.getByRole("button", { name: PLUS });
  await expect(plus).toHaveAttribute("aria-expanded", "false");
  await plus.click();
  await expect(plus).toHaveAttribute("aria-expanded", "true");
  const id = await plus.getAttribute("aria-controls");
  expect(id, 'the "+" names the picker it opens').toBeTruthy();
  const picker = page.locator(`[id="${id ?? ""}"]`);
  await expect(picker.getByText(/^Drop files or a folder here, or/)).toBeVisible();
  for (const label of ["browse", "Choose a folder", "Add link"]) {
    await expect(picker.getByRole("button", { name: label, exact: true })).toBeVisible();
  }
  await expect(
    picker.getByRole("textbox", { name: "Or paste a link to a page, file or idea" }),
  ).toBeVisible();
  await expect(picker.getByText(LINK_LINE)).toHaveCount(0); // a link goes into the words here, never a row
  return picker;
}

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }, info) => {
  test.skip(info.project.name !== "desktop", "the viewport is set here; one project is enough");
  await signIn(page, PERSONAS.contributor);
});

test('S-08.layout/3, C-PROMPT.attach at 375px: the sharer\'s "+" opens the picker (axe), Escape goes back to it, and a file uploads for the conversation and goes with the message', async ({
  page,
}) => {
  const { uploads, posted } = await answer(page);
  await openAsSharer(page);
  const plus = page.getByRole("button", { name: PLUS });
  await expect(plus).toHaveAttribute("title", PLUS);
  // DEC-124: first in the box's tool row; on a phone the one row is the "+", the pill and Send (BLD-F078)
  await expect(page.locator("form.cv-box .cfoot").locator("button, a").first()).toHaveAttribute(
    "aria-label",
    PLUS,
  );
  await settleMotion(page);
  const row = await page.evaluate(() => {
    const r = (el: Element | null) => el!.getBoundingClientRect().toJSON() as DOMRect;
    const form = document.querySelector("form.cv-box")!;
    return {
      plus: r(form.querySelector(".attach-btn")),
      field: r(form.querySelector(".cv-field")),
      send: r(form.querySelector(".cv-send")),
    };
  });
  expect(row.plus.width).toBeGreaterThanOrEqual(44); // F-SPACE.targets: a touch target
  expect(row.plus.height).toBeGreaterThanOrEqual(44);
  expect(row.plus.right).toBeLessThanOrEqual(row.field.left);
  expect(row.field.right).toBeLessThanOrEqual(row.send.left);
  expect(Math.abs(row.plus.bottom - row.send.bottom)).toBeLessThanOrEqual(1); // one row

  const picker = await openPicker(page);
  await expectNoSeriousAxeIssues(page);
  await picker.getByRole("textbox", { name: "Or paste a link to a page, file or idea" }).focus();
  await page.keyboard.press("Escape");
  await expect(picker).toHaveCount(0);
  await expect(plus).toBeFocused();

  // A small synthetic text file through "browse" (C-FILE.uploader): POST /api/files for the conversation
  await openPicker(page);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "browse", exact: true }).click();
  await (
    await chooser
  ).setFiles({ name: NAME, mimeType: "text/markdown", buffer: Buffer.from("Calls about R07: 40 a day.") });
  const file = page.getByRole("list", { name: "Your files" }).getByRole("listitem").filter({ hasText: NAME });
  await expect(file).toBeVisible();
  await expect(file.getByText("Checked", { exact: true })).toBeVisible({ timeout: 15_000 });
  await expect(file.getByRole("button", { name: `Remove ${NAME}` })).toBeVisible();
  expect(uploads).toHaveLength(1);
  const fields = await page.evaluate(() => (window as unknown as { __uploads: unknown[] }).__uploads);
  expect(fields).toEqual([{ idea_id: IDEA, for: "conversation", file: NAME }]);
  await expectNoSeriousAxeIssues(page);

  // It goes with the message (L-CONVO/7), leaves the box, and shows on the message with View
  await page.getByRole("textbox", { name: "Message the review desk" }).fill(WORDS);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  const onMessage = page.getByRole("list", { name: "Files in your message" });
  await expect(onMessage).toContainText(NAME);
  await expect(onMessage.getByRole("link", { name: `View ${NAME}` })).toHaveAttribute(
    "href",
    `/api/files/${FILE_ID}/view`,
  );
  expect(posted).toEqual([{ text: WORDS, mentions: [], file_ids: [FILE_ID] }]);
  await expect(page.getByRole("list", { name: "Your files" })).toHaveCount(0);
  await expect(page.getByRole("textbox", { name: "Message the review desk" })).toHaveValue("");
});

test('BLD-F063 at 375px: a crew reader\'s box has no "+" and no file input; the pill starts at the content edge', async ({
  page,
}) => {
  await page.goto("/kit/conversation");
  await expect(page.getByRole("heading", { level: 1, name: TITLE })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Message the crew" })).toBeVisible();
  await expect(page.getByRole("button", { name: PLUS })).toHaveCount(0);
  await expect(page.locator('form.cv-box input[type="file"]')).toHaveCount(0);
  await expect(page.locator("form.cv-box").getByRole("button")).toHaveCount(1); // Send
});

test("WCAG 1.4.10, S-08.layout/3, BLD-F095 at 320 x 256 (400% zoom): with the picker open the box stays under the phone bar and scrolls inside itself, so focus on Choose a folder and browse is in view", async ({
  page,
}) => {
  await answer(page);
  await openAsSharer(page);
  await page.setViewportSize({ width: 320, height: 256 });
  await openPicker(page);
  await settleMotion(page);
  for (const name of ["Choose a folder", "browse"]) {
    const button = page.getByRole("button", { name, exact: true });
    await button.focus();
    await expect(button).toBeFocused();
    await expect(button, name).toBeInViewport();
  }
  // The capped box: its top is on screen, below the phone bar, and it scrolls inside itself (lane D's QA)
  const at = await page.evaluate(() => {
    const form = document.querySelector<HTMLElement>("form.cv-box")!;
    const bar = document.querySelector(".pnav")?.getBoundingClientRect();
    return {
      top: form.getBoundingClientRect().top,
      bar: bar ? bar.bottom : 0,
      overflow: getComputedStyle(form).overflowY,
    };
  });
  expect(at.top).toBeGreaterThanOrEqual(0);
  expect(at.top).toBeGreaterThanOrEqual(at.bar - 1);
  expect(at.overflow).toBe("auto");
});

test("WCAG 1.4.10, WCAG 2.4.7, L-CONVO/6, S-08.layout/3, BLD-F095 at 375px: with a file in the box the @mention list opens in full above it, never cut off by the box", async ({
  page,
}) => {
  await answer(page);
  // A hello first: the read after it brings a crew member to mention (the kit's sharer view has none)
  const ADITI = {
    id: "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b02",
    name: "Aditi Sharma",
    first_name: "Aditi",
    initials: "AS",
  };
  const hello = { ...sent(), id: "6c1f6a0e-0000-4000-8000-000000000020", text: "Hello, crew.", files: [] };
  await page.route(`**/api/ideas/${IDEA}/conversation/messages`, (route) =>
    route.fulfill({ status: 201, json: { entry: hello, hidden: 0 } }),
  );
  await page.route(`**/api/ideas/${IDEA}/conversation`, (route) =>
    route.fulfill({
      json: {
        ...sharerView([hello]),
        participants: [
          { person: DESK, label: "The review desk", doing: "Reviewing it", you: false },
          { person: ADITI, label: "Aditi Sharma", doing: "On the crew", you: false },
          { person: KAVYA, label: "You", doing: "Shared the idea", you: true },
        ],
      },
    }),
  );
  await openAsSharer(page);
  const box = page.getByRole("textbox", { name: "Message the review desk" });
  await box.fill("Hello, crew.");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.getByText("Hello, crew.", { exact: true })).toBeVisible();

  // One file row in the box
  await openPicker(page);
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "browse", exact: true }).click();
  await (
    await chooser
  ).setFiles({ name: NAME, mimeType: "text/markdown", buffer: Buffer.from("Calls about R07: 40 a day.") });
  const file = page.getByRole("list", { name: "Your files" }).getByRole("listitem").filter({ hasText: NAME });
  await expect(file.getByText("Checked", { exact: true })).toBeVisible({ timeout: 15_000 });

  // "@" opens the list above the pill, as the mention tests open it; the box lifts its cap while it is open
  await box.click();
  await page.keyboard.type("@");
  const list = page.getByRole("listbox", { name: "People to mention" });
  await expect(list).toBeVisible();
  await expect(list.getByRole("option").first()).toContainText("Aditi Sharma");
  await expect(list.getByRole("option").first()).toBeInViewport();
  await expect(page.locator("form.cv-box")).toHaveCSS("overflow-y", "visible");
  // Closed again, the cap is back (lane D's QA: the picker and files scroll inside the box on a short screen)
  await page.keyboard.press("Escape");
  await expect(list).toHaveCount(0);
  await expect(page.locator("form.cv-box")).toHaveCSS("overflow-y", "auto");
});

test.describe('S-08\'s "+" at 1440px (Messages.jpg)', () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test('S-08.layout/3 at 1440px: the "+" sits with who sees it and Send under the words; the picker opens between them; axe with it open', async ({
    page,
  }) => {
    await answer(page);
    await openAsSharer(page);
    await expect(page.locator("form.cv-box .cfoot").locator("button, a").first()).toHaveAttribute(
      "aria-label",
      PLUS,
    );
    const picker = await openPicker(page);
    await settleMotion(page);
    const at = await page.evaluate(() => {
      const r = (el: Element | null) => el!.getBoundingClientRect().toJSON() as DOMRect;
      const form = document.querySelector("form.cv-box")!;
      return {
        field: r(form.querySelector(".cv-field")),
        pick: r(form.querySelector(".cv-pick")),
        plus: r(form.querySelector(".attach-btn")),
        sees: r(form.querySelector(".cv-sees")),
        send: r(form.querySelector(".cv-send")),
      };
    });
    expect(at.pick.top).toBeGreaterThanOrEqual(at.field.bottom);
    expect(at.plus.top).toBeGreaterThanOrEqual(at.pick.bottom);
    expect(at.plus.right).toBeLessThanOrEqual(at.sees.left);
    expect(at.sees.right).toBeLessThanOrEqual(at.send.left);
    await expect(page.locator("form.cv-box .cv-sees")).toHaveText(
      "Only you and the review desk see this conversation.",
    );
    await expectNoSeriousAxeIssues(page);
    await expect(picker).toBeVisible();
  });
});
