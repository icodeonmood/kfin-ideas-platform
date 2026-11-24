/**
 * The core components on the kit page (lane D; C-BUTTON, C-PILL, C-FIELD, C-FIELD-MSG, C-CHIP, C-TABS, C-SORTS,
 * C-TRACK, C-SKELETON, C-EMPTY, C-CARD; the walk's shared styles, BLD-D019: "Requested", the quiet link and the "+"
 * attach button, DEC-124 and DEC-126). axe at both widths, then each component's keyboard and state rules.
 * The kit exists in dev and test only.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, settleMotion, signIn } from "./helpers";

test.beforeEach(async ({ page }) => {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/kit");
  await expect(page.getByRole("heading", { level: 1, name: "Components" })).toBeVisible();
});

test("F-A11Y.rules: every component in its states passes axe", async ({ page }) => {
  await expectNoSeriousAxeIssues(page);
});

test("C-CHIP.behaviour/1: a single choice moves and selects with the arrow keys, one tab stop", async ({
  page,
}) => {
  const group = page.getByRole("radiogroup", { name: "Area" });
  const first = group.getByRole("radio", { name: /Investor service/ });
  await expect(first).toHaveAttribute("aria-checked", "true");
  await first.focus();
  await page.keyboard.press("ArrowRight");
  const second = group.getByRole("radio", { name: /Distributor service/ });
  await expect(second).toBeFocused();
  await expect(second).toHaveAttribute("aria-checked", "true");
  await expect(first).toHaveAttribute("aria-checked", "false");
  await expect(group.locator('[role="radio"][tabindex="0"]')).toHaveCount(1);
});

test("C-CHIP.behaviour/2: a multi choice toggles each chip with aria-pressed", async ({ page }) => {
  const cost = page
    .getByRole("group", { name: "What it would bring" })
    .getByRole("button", { name: "Saves cost" });
  await expect(cost).toHaveAttribute("aria-pressed", "false");
  await cost.click();
  await expect(cost).toHaveAttribute("aria-pressed", "true");
});

test("C-TABS/2 and C-TABS/5: arrow keys change tab; a tab with nothing in it shows its empty state", async ({
  page,
}) => {
  const yours = page.getByRole("tab", { name: /Yours/ });
  await yours.focus();
  await page.keyboard.press("ArrowRight");
  const teamed = page.getByRole("tab", { name: /Teamed up/ });
  await expect(teamed).toBeFocused();
  await expect(teamed).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: /Teamed up/ })).toContainText("Nothing teamed up yet");
  await expectNoSeriousAxeIssues(page);
});

test("C-SORTS.behaviour/1: exactly one sort option is on", async ({ page }, info) => {
  test.skip(info.project.name === "phone-360", "a phone cycles one button instead");
  const group = page.getByRole("group", { name: "Sort by" });
  await group.getByRole("button", { name: "Stage" }).click();
  await expect(group.getByRole("button", { name: "Stage" })).toHaveAttribute("aria-pressed", "true");
  await expect(group.locator('[aria-pressed="true"]')).toHaveCount(1);
});

test("C-BUTTON.states/4–5: disabled stays focusable; busy says so and keeps its width", async ({ page }) => {
  const disabled = page.getByRole("button", { name: "Move to Check it" });
  await expect(disabled).toHaveAttribute("aria-disabled", "true");
  await disabled.focus();
  await expect(disabled).toBeFocused();

  // Layout width, not boundingBox: the press scales the button to 0.97 and eases back (F-MOTION.inside), and a
  // bounding box read mid-ease is up to 1.2 px narrow on a phone though the button's own width never changed.
  const layoutWidth = (el: Element) => parseFloat(getComputedStyle(el).width);
  const send = page.getByRole("button", { name: "Send it" });
  const before = await send.evaluate(layoutWidth);
  await send.click();
  const busy = page.getByRole("button", { name: "Sending…" });
  await expect(busy).toHaveAttribute("aria-busy", "true");
  expect(Math.abs((await busy.evaluate(layoutWidth)) - before)).toBeLessThanOrEqual(1);
});

test("C-BUTTON.states, DEC-126: Requested is aria-disabled, stays focusable and a click does nothing; Withdraw is a quiet link with a visible focus", async ({
  page,
}) => {
  const foot = page.getByRole("group", { name: "A crew card’s foot" });
  await foot.getByRole("button", { name: "Team up" }).click();
  // The same button turns to Requested where Team up was, so focus stays on it (J-TEAMUP/3)
  const requested = foot.getByRole("button", { name: "Requested" });
  await expect(requested).toHaveAttribute("aria-disabled", "true");
  await expect(requested).not.toHaveAttribute("disabled");
  await expect(requested).toBeFocused();
  // Playwright waits for an aria-disabled button to be enabled, so the click is forced: it must change nothing
  await requested.click({ force: true });
  await expect(requested).toHaveText("Requested");
  await expect(requested).toHaveCSS("background-color", "rgb(228, 228, 224)");

  const withdraw = foot.getByRole("button", { name: "Withdraw" });
  await page.keyboard.press("Tab");
  await expect(withdraw).toBeFocused();
  await expect(withdraw).toHaveCSS("outline-style", "solid");
  await expect(withdraw).toHaveCSS("outline-width", "2px");
  await expect(withdraw).toHaveCSS("outline-color", "rgb(57, 93, 237)");
  await expect(withdraw).toHaveCSS("text-decoration-line", "underline");
  await expect(withdraw).toHaveCSS("color", "rgb(95, 95, 100)");
  const box = await withdraw.evaluate((el) => [el.clientWidth, el.clientHeight]);
  expect(box[0]).toBeGreaterThanOrEqual(24);
  expect(box[1]).toBeGreaterThanOrEqual(24);
  await expectNoSeriousAxeIssues(page);

  // Withdraw: back to Team up, focus on it, and Withdraw gone
  await page.keyboard.press("Enter");
  await expect(foot.getByRole("button", { name: "Team up" })).toBeFocused();
  await expect(withdraw).toHaveCount(0);
});

test("C-PROMPT.anatomy/2, DEC-124: the “+” attach button is first in the tool row, 44px, named exactly, and opens its picker", async ({
  page,
}) => {
  const name = "Add files, a folder or a link";
  const prompt = page.locator(".cz .prompt");
  const row = await prompt
    .locator(".cfoot button")
    .evaluateAll((els) => els.map((el) => el.getAttribute("aria-label")));
  expect(row).toEqual([name, "Speak instead", "Start my draft"]);

  const plus = prompt.getByRole("button", { name, exact: true });
  await expect(plus).toHaveAttribute("title", name);
  await expect(plus).toHaveAttribute("aria-expanded", "false");
  await expect(plus).toHaveAttribute("aria-controls", "k-picker");
  const mic = prompt.getByRole("button", { name: "Speak instead" });
  const size = (el: Element) => [getComputedStyle(el).width, getComputedStyle(el).height];
  expect(await plus.evaluate(size)).toEqual(["44px", "44px"]);
  expect(await plus.evaluate(size)).toEqual(await mic.evaluate(size));
  await expect(plus).toHaveCSS("color", "rgb(42, 42, 46)");

  await plus.click();
  await expect(plus).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByRole("group", { name })).toBeVisible();
  await expect(plus).toHaveCSS("background-color", "rgb(17, 17, 17)");
  await expectNoSeriousAxeIssues(page);
  await plus.click();
  await expect(plus).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByRole("group", { name })).toBeHidden();
});

test("C-FIELD.rules/2–4 and C-FIELD-MSG: the message shows under the field on blur and goes when fixed", async ({
  page,
}) => {
  const title = page.getByRole("textbox", { name: "Title" });
  await title.fill("Too short");
  await title.blur();
  const msg = page.getByRole("alert").filter({ hasText: "Add a few more words" });
  await expect(msg).toBeVisible();
  await expect(title).toHaveAttribute("aria-invalid", "true");
  const describedBy = (await title.getAttribute("aria-describedby")) ?? "";
  expect(describedBy.split(" ")).toContain(await msg.getAttribute("id"));
  await expectNoSeriousAxeIssues(page);
  await title.fill("Investors call to ask why a redemption was rejected");
  await expect(msg).toHaveCount(0);
});

test('C-FIELD, C-PROMPT.anatomy/2 (BLD-D029): a field\'s own "+" sits inside its frame at the foot of the trailing end, after the text in the tab order; the frame lights on focus', async ({
  page,
}) => {
  const field = page.getByRole("textbox", { name: "Your answer to question 1" });
  const frame = page.locator(".fld-frame").filter({ has: field });
  const plus = frame.getByRole("button", { name: "Attach files to this answer", exact: true });
  await expect(plus).toHaveAttribute("title", "Attach files");
  // The kit's arrival scales its cards in; measure once it has finished (CI 45117067515 caught it mid-way at 0.99)
  await settleMotion(page);
  const [f, p, t] = await Promise.all([frame.boundingBox(), plus.boundingBox(), field.boundingBox()]);
  // Inside the frame, 4px in from its right and bottom edges (1px border + 4px), right of the text, 44px
  expect(await plus.evaluate((el) => [getComputedStyle(el).width, getComputedStyle(el).height])).toEqual([
    "44px",
    "44px",
  ]);
  expect(p!.width).toBeCloseTo(44, 0);
  expect(f!.x + f!.width - (p!.x + p!.width)).toBeCloseTo(5, 0);
  expect(f!.y + f!.height - (p!.y + p!.height)).toBeCloseTo(5, 0);
  expect(p!.x).toBeGreaterThanOrEqual(t!.x + t!.width);
  // The text starts where a field's without tools does: the other text area on the page
  const plain = page.getByRole("textbox", { name: /Anything else the desk should know/ });
  const textLeft = (l: Locator) =>
    l.evaluate((el) => {
      const s = getComputedStyle(el);
      return el.getBoundingClientRect().left + parseFloat(s.borderLeftWidth) + parseFloat(s.paddingLeft);
    });
  const outerLeft = async (l: Locator) => (await l.boundingBox())!.x;
  expect((await textLeft(field)) - (await outerLeft(frame))).toBeCloseTo(
    (await textLeft(plain)) - (await outerLeft(plain)),
    0,
  );
  // At rest the frame has the field's border; focus in the text, then on the "+", lights it blue
  await expect(frame).toHaveCSS("border-top-color", "rgb(140, 140, 145)");
  await expect(field).toHaveCSS("border-top-width", "0px");
  await field.focus();
  await expect(frame).toHaveCSS("border-top-color", "rgb(57, 93, 237)");
  await page.keyboard.press("Tab");
  await expect(plus).toBeFocused();
  await expect(frame).toHaveCSS("border-top-color", "rgb(57, 93, 237)");
  await expectNoSeriousAxeIssues(page);
});

test("C-TRACK.anatomy: the stages are an ordered list that says each stage's state", async ({ page }) => {
  const track = page.getByRole("list", { name: "Where it is" });
  await expect(track.getByRole("listitem")).toHaveCount(5);
  await expect(track.getByRole("listitem").nth(2)).toContainText("Reviewed, now");
  await expect(track.getByRole("listitem").nth(0)).toContainText("Shared, done");
});

test("C-SEARCH.behaviour/1–2, /6: the panel opens on focus; Backspace removes the last filter; Escape keeps the text", async ({
  page,
}) => {
  const box = page.getByRole("searchbox", { name: "Search your ideas" });
  await box.focus();
  const panel = page.getByRole("group", { name: "Narrow your search" });
  await expect(panel).toBeVisible();
  await expectNoSeriousAxeIssues(page);
  await panel.getByRole("button", { name: /With the review desk/ }).click();
  await expect(page.getByRole("button", { name: "Remove the filter: With the review desk" })).toBeVisible();
  await box.focus();
  await page.keyboard.press("Backspace");
  await expect(page.getByRole("button", { name: "Remove the filter: With the review desk" })).toHaveCount(0);
  await box.fill("sms");
  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);
  await expect(box).toHaveValue("sms");
  // Escape inside the box moves no focus, so coming back to the box opens the panel again
  await box.blur();
  await box.focus();
  await expect(panel).toBeVisible();
});

test("C-DROPDOWN/2–5: None picked, then a title, then a count; Escape closes the list only", async ({
  page,
}) => {
  const field = page.getByRole("button", { name: /Bring your ideas along/ });
  await expect(field).toContainText("None picked");
  await field.click();
  await expect(field).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("checkbox", { name: /Rejection SMS codes/ }).check();
  await expect(field).toContainText("Rejection SMS codes confuse investors");
  await page.getByRole("checkbox", { name: /No script for calls/ }).check();
  await expect(field).toContainText("2 ideas picked");
  await expectNoSeriousAxeIssues(page);
  await page.keyboard.press("Escape");
  await expect(field).toHaveAttribute("aria-expanded", "false");
  await expect(field).toBeFocused();
});

test("C-FILE.row: a found detail is a warning under its row, with the row's own action", async ({ page }) => {
  const files = page.getByRole("list", { name: "Your files" });
  await expect(files.getByRole("listitem")).toHaveCount(3);
  await expect(files.getByRole("alert")).toContainText(
    "Only you, the review desk and the Ones Committee can open it.",
  );
  await expect(files.getByRole("button", { name: "Hide it for me" })).toBeVisible();
});

test("C-AVATAR.crew/2: each crew face takes focus and is named", async ({ page }) => {
  const face = page.getByRole("img", { name: "Imran Qureshi" });
  await face.focus();
  await expect(face).toBeFocused();
  await expect(page.getByText("Rahul Verma and 4 others on it")).toBeVisible();
});

test("C-CREW-DECK.behaviour/4: Next and ← → move the deck; only the front card is in the reading order", async ({
  page,
}) => {
  const deck = page.getByRole("region", { name: "Ideas close to yours" });
  await expect(deck.getByRole("heading", { level: 3 })).toHaveCount(1);
  await expect(deck.getByRole("button", { name: "Previous idea" })).toHaveAttribute("aria-disabled", "true");
  await deck.getByRole("button", { name: "Next idea" }).click();
  await expect(deck.getByText("Idea 2 of 3")).toBeAttached();
  await expect(deck.getByRole("heading", { level: 3 })).toHaveText("No script for calls about rejections");
  await page.keyboard.press("ArrowLeft");
  await expect(deck.getByRole("heading", { level: 3 })).toHaveText("Rejection SMS codes confuse investors");
  await expectNoSeriousAxeIssues(page);
});

test("C-ONES-FAN.behaviour: the fan spreads and moves by Next and ← →; 'Post 2 of 3'; a name only with consent", async ({
  page,
}) => {
  const fan = page.getByRole("region", { name: "Posts from the Ones" });
  await expect(fan.getByText("Post 1 of 3")).toBeVisible();
  await fan.getByRole("button", { name: "Next post" }).click();
  await expect(fan.getByText("Post 2 of 3")).toBeVisible();
  await expect(fan.getByRole("article")).toContainText("One No. 17");
  const cheer = fan.getByRole("button", { name: /^Cheer One No\. 17’s fix, 24 cheers/ });
  await expect(cheer).toHaveAttribute("aria-pressed", "false");
  // On a phone the posts are a snap row. A click's retry scrolls the row sideways with its own inline alignment, the
  // snap lands back on post 1 and post 2 turns inert, so the click never lands (run 44912206769). Bring it into
  // view once, then click without scrolling (BLD-D027).
  await cheer.scrollIntoViewIfNeeded();
  await cheer.click({ scroll: "none" });
  await expect(fan.getByRole("button", { name: /^Cheer One No\. 17’s fix, 25 cheers/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(fan.getByRole("link", { name: "Read the thread 6" })).toBeVisible();
  await page.keyboard.press("ArrowRight");
  await expect(fan.getByText("Post 3 of 3")).toBeVisible();
  await expect(fan.getByRole("button", { name: "Next post" })).toHaveAttribute("aria-disabled", "true");
  await expectNoSeriousAxeIssues(page);
});

test("C-ONES-FAN.states (BLD-D020): none, one with its companion and Cheer pressed, several stacked; See details spreads it; axe on each, 44px targets", async ({
  page,
}, info) => {
  const phone = info.project.name === "phone-360";
  const atLeast44 = async (target: Locator) => {
    const box = (await target.boundingBox())!;
    expect(box.height).toBeGreaterThanOrEqual(44);
    expect(box.width).toBeGreaterThanOrEqual(44);
  };
  await expect(page.getByText("No Ones yet", { exact: true })).toBeVisible();
  const one = page.getByRole("region", { name: "One post from the Ones" });
  await expect(one.getByText("The next One could be you", { exact: true })).toBeVisible();
  await expect(one.getByText("Post 1 of 1")).toBeVisible();
  await expect(one.getByRole("button", { name: "Next post" })).toHaveCount(0);
  const cheer = one.getByRole("button", { name: /^Cheer Neha Kapoor’s fix, 99 cheers$/ });
  await expect(cheer).toHaveAttribute("aria-pressed", "true");
  const fan = page.getByRole("region", { name: "Posts from the Ones" });
  const see = fan.getByRole("button", { name: "See details" });
  // PhoneHome draws no stack and no side panel: the row shows at rest
  if (phone) await expect(see).toHaveCount(0);
  else await expect(fan.getByText("3 fixes, 3 people")).toBeVisible();
  await expectNoSeriousAxeIssues(page); // at rest: several, the one post cheered, and none
  await atLeast44(cheer);
  await atLeast44(one.getByRole("link", { name: "Read the thread 12" }));
  await atLeast44(one.getByRole("link", { name: "Share a problem" }));
  if (phone) {
    await fan.getByRole("button", { name: "Next post" }).click();
    await expect(fan.getByText("Post 2 of 3")).toBeVisible();
  } else {
    await atLeast44(see);
    await see.click();
    await expect(see).toHaveCount(0);
    await expect(fan.getByRole("button", { name: "Next post" })).toBeFocused();
    await expect(fan.getByText("Post 1 of 3")).toBeVisible();
  }
  await atLeast44(fan.getByRole("button", { name: "Previous post" }));
  await atLeast44(fan.getByRole("button", { name: "Next post" }));
  await expectNoSeriousAxeIssues(page); // spread
});

test("C-ONES-FAN.behaviour/2, F-MOTION (BLD-D026): See details flies the stack out into the row; once the fly-out settles, axe passes on WCAG 2.1 AA", async ({
  page,
}, info) => {
  test.skip(info.project.name === "phone-360", "PhoneHome draws no stack, so nothing flies out on a phone");
  const fan = page.getByRole("region", { name: "Posts from the Ones" });
  // Count the arcs as they start: a card that is finished early still reports its start, so this holds on a slow run
  await fan.evaluate((el) => {
    const w = window as unknown as { onesArcs: number };
    w.onesArcs = 0;
    el.addEventListener("animationstart", (e) => {
      if ((e as AnimationEvent).animationName === "oFly") w.onesArcs++;
    });
  });
  await fan.getByRole("button", { name: "See details" }).click();
  await expect(fan.getByRole("button", { name: "Next post" })).toBeFocused();
  // Wait for the fly-out the way the arrival animations are waited for, then for the region to drop data-fly
  await settleMotion(page);
  await expect(fan).not.toHaveAttribute("data-fly");
  expect(await page.evaluate(() => (window as unknown as { onesArcs: number }).onesArcs)).toBe(3);
  await expect(fan.getByRole("button", { name: "See details" })).toHaveCount(0);
  await expect(fan.locator(".fan-side")).toHaveCount(0);
  await expect(fan.getByText("Post 1 of 3")).toBeVisible();
  await expectNoSeriousAxeIssues(page); // settles again, then axe on wcag2a, wcag2aa, wcag21a and wcag21aa
});

test("C-FIELD.kinds: paste fills the six code boxes; a wrong code is said under them", async ({ page }) => {
  const first = page.getByRole("textbox", { name: "Digit 1 of 6" });
  await first.focus();
  await page.evaluate(() => {
    const dt = new DataTransfer();
    dt.setData("text", "135 790");
    document.activeElement!.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true }));
  });
  await expect(page.getByRole("textbox", { name: "Digit 6 of 6" })).toHaveValue("0");
  const wrong = page.getByRole("alert").filter({ hasText: "That code didn’t match" });
  await expect(wrong).toBeVisible();
  await expectNoSeriousAxeIssues(page);
  // A second full code over the first is checked again, with no need to clear the boxes
  await page.evaluate(() => {
    const dt = new DataTransfer();
    dt.setData("text", "111111");
    document.activeElement!.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true }));
  });
  await expect(page.getByRole("textbox", { name: "Digit 1 of 6" })).toHaveValue("1");
  await expect(wrong).toBeVisible();
  await page.keyboard.press("Backspace");
  await expect(page.getByRole("textbox", { name: "Digit 6 of 6" })).toHaveValue("");
});

test("C-FIELD.kinds: the question box adds on Enter, pinned to the part chosen", async ({ page }) => {
  const box = page.getByRole("textbox", { name: "What would you like to ask Asha?" });
  await page.getByRole("combobox", { name: "Pinned to" }).selectOption("often");
  await box.fill("How many of the 40 calls are about R07?");
  await box.press("Enter");
  await expect(page.getByRole("list", { name: "Your questions" })).toContainText(
    "often: How many of the 40 calls are about R07?",
  );
  await expect(box).toHaveValue("");
});

/**
 * QA ONLY, lane D's branch d/qa-train24-1, never merged: train 24 (102c4d45) at the usual sizes, 1440, 1024, 640, 360
 * and 320. Screenshots and measures go to test-results/qa-shots for lane D to read. Synthetic data only.
 */
const QA_SHOTS = join(__dirname, "..", "test-results", "qa-shots");
const QA_SIZES = [
  [1440, 900],
  [1024, 768],
  [640, 900],
  [360, 740],
  [320, 640],
] as const;
type QaBox = { top: number; bottom: number; left: number; right: number; width: number; height: number };
type QaRow = {
  row: QaBox;
  inner: QaBox | null;
  name: QaBox | null;
  clipped: boolean;
  acts: QaBox | null;
  x: QaBox | null;
  msg: QaBox | null;
  isMsg: boolean;
  spin: boolean;
  status: string;
};
/** The file rows of the list `list` (inside `inSel`) and the page's sideways scroll, measured in the page. */
async function qaRows(page: Page, list: string, inSel: string) {
  return page.evaluate(
    ([listSel, boxSel]) => {
      const box = (el: Element | null | undefined) => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {
          top: r.top,
          bottom: r.bottom,
          left: r.left,
          right: r.right,
          width: r.width,
          height: r.height,
        };
      };
      const ul = document.querySelector(listSel);
      const rows: QaRow[] = [...(ul?.querySelectorAll(":scope > .frow") ?? [])].map((li) => {
        const n = li.querySelector<HTMLElement>(".frow-n");
        return {
          row: box(li)!,
          inner: box(li.querySelector(".frow-in")),
          name: box(n),
          clipped: n ? n.scrollWidth > n.clientWidth : false,
          acts: box(li.querySelector(".frow-a")),
          x: box(li.querySelector(".frow-x, .cfile-x")),
          msg: box(li.querySelector(".fmsg")),
          isMsg: li.classList.contains("frow-msg"),
          spin: !!li.querySelector(".spin"),
          status: li.querySelector(".frow-st")?.textContent ?? "",
        };
      });
      const html = document.documentElement;
      return {
        vw: window.innerWidth,
        sideways: html.scrollWidth - html.clientWidth,
        live: ul?.getAttribute("aria-live") ?? null,
        list: box(ul),
        within: box(ul?.closest(boxSel)),
        rows,
      };
    },
    [list, inSel] as const,
  );
}

type QaRows = Awaited<ReturnType<typeof qaRows>>;
/** The rows' checks at one size. Compact rows: 260px at most, one line, the name gives way, Remove 32px. */
function qaRowChecks(name: string, g: QaRows, compact: boolean) {
  expect.soft(g.sideways, `${name}: no sideways scroll`).toBeLessThanOrEqual(0);
  expect.soft(g.rows.length, `${name}: the rows are there`).toBeGreaterThan(0);
  for (const [i, r] of g.rows.entries()) {
    const at = `${name} row ${i + 1}`;
    if (g.list) {
      expect.soft(r.row.left, `${at}: starts inside the list`).toBeGreaterThanOrEqual(g.list.left - 0.5);
      expect.soft(r.row.right, `${at}: ends inside the list`).toBeLessThanOrEqual(g.list.right + 0.5);
    }
    if (g.within)
      expect.soft(r.row.right, `${at}: ends inside its box`).toBeLessThanOrEqual(g.within.right + 0.5);
    if (r.name && r.inner) {
      expect
        .soft(r.name.right, `${at}: the name stays inside the row`)
        .toBeLessThanOrEqual(r.inner.right + 0.5);
    }
    if (r.x) {
      expect.soft(r.x.right, `${at}: Remove ends inside the row`).toBeLessThanOrEqual(r.row.right + 0.5);
      expect.soft(r.x.width, `${at}: Remove is at least 24px`).toBeGreaterThanOrEqual(24);
    }
    if (!compact) continue;
    if (r.isMsg) {
      if (g.list)
        expect
          .soft(Math.abs(r.row.width - g.list.width), `${at}: a row with a message is the list's width`)
          .toBeLessThan(1);
      if (r.msg && r.inner)
        expect
          .soft(r.msg.top, `${at}: the message is under the row`)
          .toBeGreaterThanOrEqual(r.inner.bottom - 0.5);
    } else {
      expect.soft(r.row.width, `${at}: 260px at most`).toBeLessThanOrEqual(260.5);
    }
    if (r.x) {
      expect.soft(r.x.width, `${at}: Remove is 32px`).toBeCloseTo(32, 0);
      expect.soft(r.x.height, `${at}: Remove is 32px`).toBeCloseTo(32, 0);
    }
    if (r.name && r.acts) {
      expect
        .soft(r.name.right, `${at}: the name gives way before Remove`)
        .toBeLessThanOrEqual(r.acts.left + 0.5);
      expect.soft(r.acts.top, `${at}: Remove is on the row's line`).toBeLessThan(r.name.bottom);
    }
  }
}

test("QA (lane D, never merged): train 24 on the kit at 1440, 1024, 640, 360 and 320: BLD-D029's field with its own \"+\" and BLD-D030's compact rows", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "desktop", "the sizes are set here");
  test.setTimeout(240_000);
  mkdirSync(QA_SHOTS, { recursive: true });
  const log: Record<string, unknown> = {};
  const field = page.getByRole("textbox", { name: "Your answer to question 1" });
  const frame = page.locator(".fld-frame").filter({ has: field });
  const list = page.getByRole("list", { name: "Files in your message" });
  for (const [w, h] of QA_SIZES) {
    await page.setViewportSize({ width: w, height: h });
    await page.reload();
    await expect(page.getByRole("heading", { level: 1, name: "Components" })).toBeVisible();
    await settleMotion(page);
    // BLD-D029: the "+" inside the frame at its foot's trailing end, right of the words, 44px; the frame in its card
    const f = await frame.evaluate((el) => {
      const box = (e: Element | null) => {
        if (!e) return null;
        const r = e.getBoundingClientRect();
        return {
          top: r.top,
          bottom: r.bottom,
          left: r.left,
          right: r.right,
          width: r.width,
          height: r.height,
        };
      };
      const html = document.documentElement;
      return {
        sideways: html.scrollWidth - html.clientWidth,
        frame: box(el)!,
        text: box(el.querySelector("textarea"))!,
        plus: box(el.querySelector(".fld-tools button"))!,
        card: box(el.closest("section"))!,
      };
    });
    const at = `kit-field-${w}x${h}`;
    log[at] = f;
    await page
      .locator("section")
      .filter({ has: frame })
      .last()
      .screenshot({ path: join(QA_SHOTS, `${at}.png`) });
    expect.soft(f.sideways, `${at}: no sideways scroll`).toBeLessThanOrEqual(0);
    expect.soft(f.plus.width, `${at}: the "+" is 44px`).toBeCloseTo(44, 0);
    expect.soft(f.plus.height, `${at}: the "+" is 44px`).toBeCloseTo(44, 0);
    expect
      .soft(f.frame.right - f.plus.right, `${at}: the "+" is 5px in from the frame's right`)
      .toBeCloseTo(5, 0);
    expect
      .soft(f.frame.bottom - f.plus.bottom, `${at}: the "+" is 5px up from the frame's foot`)
      .toBeCloseTo(5, 0);
    expect
      .soft(f.plus.left, `${at}: the words stop before the "+"`)
      .toBeGreaterThanOrEqual(f.text.right - 0.5);
    expect.soft(f.text.width, `${at}: the words keep room`).toBeGreaterThanOrEqual(150);
    expect.soft(f.frame.left, `${at}: the frame starts inside its card`).toBeGreaterThanOrEqual(f.card.left);
    expect.soft(f.frame.right, `${at}: the frame ends inside its card`).toBeLessThanOrEqual(f.card.right);
    // BLD-D030: the compact rows (Checked, waiting with no spinner, too big with its message on its own line)
    const r = await qaRows(page, 'ul.flist.compact[aria-label="Files in your message"]', "section");
    const rn = `kit-rows-${w}x${h}`;
    log[rn] = r;
    await page
      .locator("section")
      .filter({ has: list })
      .last()
      .screenshot({ path: join(QA_SHOTS, `${rn}.png`) });
    qaRowChecks(rn, r, true);
    expect.soft(r.rows.length, `${rn}: three rows`).toBe(3);
    expect.soft(r.rows[1]?.spin, `${rn}: the waiting row has no spinner`).toBe(false);
    expect.soft(r.rows[2]?.isMsg, `${rn}: the too-big row has its message`).toBe(true);
    expect.soft(r.live, `${rn}: the list says its changes`).toBe("polite");
    await expectNoSeriousAxeIssues(page);
  }
  writeFileSync(join(QA_SHOTS, "kit.json"), JSON.stringify(log, null, 2));
});
