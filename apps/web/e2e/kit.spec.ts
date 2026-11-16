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
