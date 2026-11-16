/**
 * The core components on the kit page (lane D; C-BUTTON, C-PILL, C-FIELD, C-FIELD-MSG, C-CHIP, C-TABS, C-SORTS,
 * C-TRACK, C-SKELETON, C-EMPTY, C-CARD). axe at both widths, then each component's keyboard and state rules.
 * The kit exists in dev and test only.
 */
import { expect, test } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

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

  const send = page.getByRole("button", { name: "Send it" });
  const before = (await send.boundingBox())!.width;
  await send.click();
  const busy = page.getByRole("button", { name: "Sending…" });
  await expect(busy).toHaveAttribute("aria-busy", "true");
  expect(Math.abs((await busy.boundingBox())!.width - before)).toBeLessThanOrEqual(1);
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
  await expect(files.getByRole("alert")).toContainText("Nobody can open it until it’s hidden");
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
  await page.keyboard.press("ArrowRight");
  await expect(fan.getByText("Post 3 of 3")).toBeVisible();
  await expect(fan.getByRole("button", { name: "Next post" })).toHaveAttribute("aria-disabled", "true");
  await expectNoSeriousAxeIssues(page);
});
