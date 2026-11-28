/**
 * J-BUSINESS: a new business idea, from the person's own words to the idea page (the product lead's item 3
 * of 26 Nov; DEC-118 (4), L-SORT, E-ENUMS.kind; lane C's BLD-C201 to BLD-C206). The pack draws a business
 * idea's kind and area on Check it, Edit and the Wall but has no journey table for it, so the rows follow
 * J-SHARE's main path: Tell it (S-04, S-04B), Check it (S-05), the idea page (S-06).
 * Words: `gateway.fakes.BUSINESS_SENTENCE` (BLD-C206), the one sentence the fake route (LLM_MODE=fake) reads
 * as a new business idea under New business, for AMC clients, with a quote of the person's words. With the
 * assistant off (Capture first, DEC-125; r7 launches so, DEC-141), New business picked by hand is the only
 * way to a business idea (BLD-C204), and with every part filled by hand it sends as one: row v1.
 * Not pinned: the business next prompts and the three S1 questions (BLD-C203), new words HR has yet to
 * confirm (DEC-123 (2)).
 * Cast: new synthetic employees (non-negotiable 11). The idea row 3 sends reaches the review desk before the
 * journeys after this one run; they find their records by title, so one more row moves nothing.
 */
import { expect, type Locator, type Page } from "@playwright/test";

import { restoreSwitches, setSwitch, signIn, type SwitchState } from "../e2e/helpers";
import { withSwitchLock } from "../e2e/switch-lock";
import { carriedFor, expectNoSeriousAxeIssues, expectWithDesk, ideaKind, runSeconds, step } from "./lib";

const REF = String.raw`IDEA-\d{4}-\d{6}`;

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** BLD-C206: the fake route's business sentence, word for word (gateway/fakes.py). Synthetic. */
const BUSINESS_SENTENCE =
  "KFintech could offer small AMCs a new product that checks factsheets before they go out.";

/** The kind's reason beside "What kind it is" (draft/parts.py): a problem's is drawn (Review.md, Edit.md); a
 * new business idea's is the NOT DRAWN default, shown for New business picked by hand (BLD-C204). */
const PROBLEM_LINE = "Suggested because you described something that goes wrong today.";
const BUSINESS_LINE = "Suggested because you described something new KFintech could offer.";

/** v1's title and what happens, typed by hand: with the assistant off no agent writes them (DEC-105).
 * Synthetic. */
const CAPTURE_TITLE = "Factsheet checks as a new product";
const CAPTURE_SUMMARY =
  "Factsheets go out before anyone checks them. A new product could check each one first.";

// --- People: new synthetic employees, one per path (offsets J-SHARE and J-RECOVER leave free) -------------

type Fresh = { emp: string; name: string; email: string };

function fresh(offset: number, last: string): Fresh {
  const n = 18000 + ((runSeconds() + offset) % 2000);
  return { emp: `SYN-${n}`, name: `Journey ${last}`, email: `journey.${n}.1pc@kfintech.example` };
}

const OFFERER = fresh(900, "Business");
const CAPTURE = fresh(1000, "Businesscapture");

async function signInAsFresh(page: Page, who: Fresh): Promise<void> {
  await signIn(page, who.emp, { email: who.email, name: who.name });
}

// --- Screens, as J-SHARE reads them ------------------------------------------------------------------------

/** S-04's box: "Describe the problem" on the board, its placeholder the example (Compose.md Controls). */
function composeBox(page: Page): Locator {
  return page.getByRole("textbox", { name: /^(Describe the problem|For example: )/ });
}

/** S-04 for a new person: the empty box ("Start a new one" if an earlier run left this ID a draft). */
async function emptyShare(page: Page): Promise<void> {
  await page.goto("/share");
  const startNew = page.getByRole("button", { name: "Start a new one" });
  await expect(startNew.or(composeBox(page)).first()).toBeVisible();
  if (await startNew.isVisible()) await startNew.click();
  await expect(composeBox(page)).toHaveValue("");
}

/** A part's value in a list of parts (S-04B's draft panel, S-06's What you shared): the visible <dd> after
 * its <dt>. */
function partValue(page: Page, label: string): Locator {
  return page
    .locator("dt", { hasText: new RegExp(`^${esc(label)}$`) })
    .locator("xpath=following-sibling::dd[1]")
    .filter({ visible: true })
    .first();
}

type Sorting = { kind: Locator; kindWhy: Locator; area: Locator; affects: Locator; brings: Locator };

/** Check it's sorting part (S-05, L-SORT.fields): each field, and the kind's reason under it. */
function sortingOf(page: Page): Sorting {
  const kind = page.getByRole("radiogroup", { name: "What kind it is" });
  return {
    kind,
    kindWhy: page.locator(".ck-sf", { has: kind }).locator(".ck-why"),
    area: page.getByRole("radiogroup", { name: "Area" }),
    affects: page.getByRole("group", { name: "Who it affects" }),
    brings: page.getByRole("group", { name: "What it would bring" }),
  };
}

/** Check it from part 3 to the idea page, as J-SHARE/9 and /10 go: Next past the similar ideas, the three
 * optional parts skipped, then Submit on Send it, which shows the title from part 1. */
async function sendFromSimilar(page: Page, title: string): Promise<void> {
  await expect(
    page.getByRole("heading", { level: 1, name: "Has someone raised this already?" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Next", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Anything that shows it?" })).toBeVisible();
  await page.getByRole("button", { name: "Skip for now" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Got an idea how to solve it?" })).toBeVisible();
  await page.getByRole("button", { name: "Skip for now" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Who would help?" })).toBeVisible();
  await page.getByRole("button", { name: "Skip for now" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Ready to send?" })).toBeVisible();
  await expect(page.getByText(title, { exact: true }).first()).toBeVisible();
  await page
    .getByRole("button", { name: "Submit" })
    .or(page.getByRole("link", { name: "Submit" }))
    .click();
  await page.waitForURL(new RegExp(`/ideas/${REF}(?:\\?from=share)?$`));
}

/** S-06 straight after Send it: with the review desk, under New business and for AMC clients as the sorting
 * confirmed, and kept as a new business idea (E-ENUMS.kind, the kind the review desk reads; read only). */
async function expectSentAsBusiness(page: Page, title: string): Promise<void> {
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
  await expectWithDesk(page);
  await expect(partValue(page, "Area")).toContainText("New business");
  await expect(partValue(page, "Who it affects")).toContainText("AMC clients");
  const ref = new URL(page.url()).pathname.split("/").pop() ?? "";
  expect(await ideaKind(ref)).toBe("business_idea");
}

// --- What the main path carries from row to row ------------------------------------------------------------

const carried = carriedFor<{ draft: string; title: string }>("J-BUSINESS");

function need<K extends keyof typeof carried>(key: K, from: string): string {
  const v = carried[key];
  if (!v) throw new Error(`${from} did not leave ${key}; run the journey from the start`);
  return v;
}

// --- J-BUSINESS.steps --------------------------------------------------------------------------------------

step(
  "J-BUSINESS/1",
  "S-04B",
  "Tells a new offer in their own words: the draft forms under New business, for AMC clients, and Move to Review goes on to Check it",
  { needs: ["S-04", "S-04B", "C-DRAFT-PANEL", "L-DRAFT", "BLD-C201", "BLD-C206"] },
  async ({ page }) => {
    await signInAsFresh(page, OFFERER);
    await emptyShare(page);
    await composeBox(page).fill(BUSINESS_SENTENCE);
    await page.getByRole("button", { name: "Start my draft" }).click();
    await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
    const draft = new URL(page.url()).pathname;
    carried.draft = draft;
    await expect(page.getByText(BUSINESS_SENTENCE).first()).toBeVisible();

    // BLD-C206: on the fake route these words are a new offer under New business, for AMC clients.
    await expect(page.getByText("Up to date", { exact: true }).first()).toBeVisible({ timeout: 30_000 });
    await expect(partValue(page, "Area")).toContainText("New business");
    await expect(partValue(page, "Who it affects")).toContainText("AMC clients");
    await expectNoSeriousAxeIssues(page);

    const move = page
      .getByRole("link", { name: "Move to Review" })
      .or(page.getByRole("button", { name: "Move to Review" }));
    await expect(move).toBeEnabled();
    await move.click();
    await page.waitForURL(new RegExp(`${esc(draft)}/check$`));
    await expect(page.getByText("Check it, part 1 of 6")).toBeVisible();
  },
);

step(
  "J-BUSINESS/2",
  "S-05",
  "Check it: the title from their words, then the sorting suggests a new business idea, quoting them, under New business; Confirm sorting",
  { needs: ["S-05", "L-SORT", "V-FIELDS", "BLD-C201", "BLD-C206"], after: ["J-BUSINESS/1"] },
  async ({ page }) => {
    await signInAsFresh(page, OFFERER);
    await page.goto(`${need("draft", "J-BUSINESS/1")}/check`);
    await expect(page.getByText("Check it, part 1 of 6")).toBeVisible();
    const title = (await page.getByRole("heading", { level: 3 }).first().innerText()).trim();
    expect(title.length).toBeGreaterThan(0);
    carried.title = title;
    await page.getByRole("button", { name: "Looks right" }).click();

    // L-SORT, BLD-C201: the assistant's kind is a suggestion, with the person's own words as its reason.
    await expect(page.getByText("Check it, part 2 of 6")).toBeVisible();
    await expect(page.getByRole("heading", { level: 1, name: "Is it sorted right?" })).toBeVisible();
    const s = sortingOf(page);
    await expect(s.kind.getByRole("radio", { name: "A new business idea" })).toBeChecked();
    await expect(s.kind.getByRole("radio", { name: "A problem to fix" })).not.toBeChecked();
    await expect(s.kindWhy).toHaveText(/^Suggested because you said “.+”\.$/);
    const quote = (await s.kindWhy.innerText()).match(/“(.+)”/)?.[1] ?? "";
    expect(BUSINESS_SENTENCE, "the reason quotes the person's own words").toContain(quote);
    await expect(s.area.getByRole("radio", { name: "New business" })).toBeChecked();
    await expect(s.affects.getByRole("button", { name: "AMC clients" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(
      page.getByText("These are suggestions from your words. Not confirmed yet.").first(),
    ).toBeVisible();
    await expectNoSeriousAxeIssues(page);

    await page.getByRole("button", { name: "Confirm sorting" }).click();
    await expect(page.getByText("Check it, part 3 of 6")).toBeVisible();
    await expect(page.getByRole("button", { name: /Sorting Suggested, not confirmed yet/ })).toHaveCount(0);
  },
);

step(
  "J-BUSINESS/3",
  "S-06",
  "Sends it: the idea page has it with the review desk under New business, for AMC clients, kept as a new business idea",
  {
    needs: ["S-05", "L-SUBMIT", "S-06", "BLD-C201", "BLD-C206"],
    after: ["J-BUSINESS/1", "J-BUSINESS/2"],
  },
  async ({ page }) => {
    await signInAsFresh(page, OFFERER);
    await page.goto(`${need("draft", "J-BUSINESS/1")}/check`);
    await page.getByRole("button", { name: /^(?:\d )?Similar ideas\b/ }).click();
    const title = need("title", "J-BUSINESS/2");
    await sendFromSimilar(page, title);
    await expectSentAsBusiness(page, title);
  },
);

// --- J-BUSINESS.variants -----------------------------------------------------------------------------------

step(
  "J-BUSINESS/v1",
  "S-05",
  "Capture first (the assistant off): the same words stay a problem to fix until New business is picked by hand, which suggests a new business idea; another area takes it back; filled in by hand, it sends as a new business idea",
  { needs: ["S-04", "S-04B", "S-05", "L-SORT", "L-SUBMIT", "S-06", "BLD-C204"] },
  async ({ page, browser }, info) => {
    // Two admin visits, two waits of 11 s, the draft and Check it to the idea page: past the default 60 s,
    // and a step that times out must still reach its `finally` and put the assistant back on.
    info.setTimeout(180_000);
    // DEC-125 (1): Capture first is `ai.all` off. Switched on the admin page, as an admin would, and
    // always put back.
    await withSwitchLock("ai.all", async () => {
      // DEC-088: every switch starts on, so "on" is the state to put back if setSwitch fails half-way.
      let before: SwitchState = "on";
      try {
        before = await setSwitch(browser, "ai.all", "off");
        // The worker and the web read switches through 10 s caches (core/killswitch.py,
        // server/killswitch.ts): past them, no draft run sees the assistant on.
        await new Promise((resolve) => setTimeout(resolve, 11_000));
        await signInAsFresh(page, CAPTURE);
        await emptyShare(page);
        await expect(page.locator(".cz")).toHaveClass(/\bcapture\b/);
        await composeBox(page).fill(BUSINESS_SENTENCE);
        await page.getByRole("button", { name: "Start my draft" }).click();
        await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
        const draft = new URL(page.url()).pathname;
        const move = page.getByRole("link", { name: "Move to Review" });
        await expect(move).toHaveAttribute("href", new RegExp(`${esc(draft)}/check$`), { timeout: 30_000 });
        await move.click();
        await page.waitForURL(new RegExp(`${esc(draft)}/check$`));
        await expect(page.getByText("Check it, part 1 of 6")).toBeVisible();

        // DEC-105: no agent wrote the title or what happens, so the person writes both
        // (V-FIELDS.checkit/1-2).
        await page.getByRole("button", { name: "Change the title" }).click();
        const titleBox = page.getByRole("textbox", { name: "Title", exact: true });
        await titleBox.fill(CAPTURE_TITLE);
        await titleBox.press("Enter");
        await expect(page.getByRole("heading", { level: 3, name: CAPTURE_TITLE })).toBeVisible();
        await page.getByRole("button", { name: "Change what happens" }).click();
        const summaryBox = page.getByRole("textbox", { name: "What happens", exact: true });
        await summaryBox.fill(CAPTURE_SUMMARY);
        await summaryBox.press("Tab");
        await expect(page.getByText(CAPTURE_SUMMARY, { exact: true }).first()).toBeVisible();
        await page.getByRole("button", { name: "Looks right" }).click();
        await expect(page.getByText("Check it, part 2 of 6")).toBeVisible();
        await expect(page.getByRole("heading", { level: 1, name: "Is it sorted right?" })).toBeVisible();

        // DEC-141, BLD-C204: no agent runs, so words that would be a business idea stay a problem to fix.
        const s = sortingOf(page);
        await expect(s.kind.getByRole("radio", { name: "A problem to fix" })).toBeChecked();
        await expect(s.kindWhy).toHaveText(PROBLEM_LINE);
        await expect(s.area.getByRole("radio", { checked: true })).toHaveCount(0);

        // New business sits behind the area search (rules/sorting.md `more`); picked there by hand, it
        // suggests a new business idea, still a suggestion.
        const areaSearch = page.getByRole("combobox", { name: /^Another area\? Search all \d+$/ });
        await areaSearch.fill("New business");
        await page.getByRole("option", { name: "New business", exact: true }).click();
        await expect(s.area.getByRole("radio", { name: "New business" })).toBeChecked();
        await expect(s.kind.getByRole("radio", { name: "A new business idea" })).toBeChecked();
        await expect(s.kindWhy).toHaveText(BUSINESS_LINE);
        await expect(
          page.getByText("These are suggestions from your words. Not confirmed yet.").first(),
        ).toBeVisible();
        await expectNoSeriousAxeIssues(page);

        // Another area takes the kind back to what the draft says.
        await s.area.getByRole("radio", { name: "Operations" }).click();
        await expect(s.area.getByRole("radio", { name: "Operations" })).toBeChecked();
        await expect(s.kind.getByRole("radio", { name: "A problem to fix" })).toBeChecked();
        await expect(s.kindWhy).toHaveText(PROBLEM_LINE);

        // L-SUBMIT, the assistant still off: New business again, the two fields no agent filled picked by
        // hand (AMC clients from the search, "Not sure yet"), Confirm sorting, then Send it.
        await areaSearch.fill("New business");
        await page.getByRole("option", { name: "New business", exact: true }).click();
        await expect(s.kind.getByRole("radio", { name: "A new business idea" })).toBeChecked();
        await page.getByRole("combobox", { name: /^Someone else\? Search all \d+$/ }).fill("AMC clients");
        await page.getByRole("option", { name: "AMC clients", exact: true }).click();
        await expect(s.affects.getByRole("button", { name: "AMC clients" })).toHaveAttribute(
          "aria-pressed",
          "true",
        );
        await s.brings.getByRole("button", { name: "Not sure yet" }).click();
        await expect(s.brings.getByRole("button", { name: "Not sure yet" })).toHaveAttribute(
          "aria-pressed",
          "true",
        );
        await page.getByRole("button", { name: "Confirm sorting" }).click();
        await expect(page.getByText("Check it, part 3 of 6")).toBeVisible();
        await sendFromSimilar(page, CAPTURE_TITLE);
        await expectSentAsBusiness(page, CAPTURE_TITLE);
      } finally {
        await restoreSwitches(browser, [["ai.all", before]]);
        // The worker's own 10 s cache: wait it out, pass or fail, so the journeys after this one meet
        // the assistant on.
        await new Promise((resolve) => setTimeout(resolve, 11_000));
      }
    });
  },
);
