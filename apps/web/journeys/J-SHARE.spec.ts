/**
 * J-SHARE: share a problem for the first time (1pc-handoff/03-journeys/J-SHARE.md). Hand-offs only; the detail of
 * each screen is in V-ACC.share.
 * Copy: reference/copy/Landing.md (S-01), SignIn.md (S-02), Compose.md (S-04), ComposeResume.md (S-04B), Review.md
 * (S-05), Status.md (S-06 "Just shared"), Home.md (S-03 prompt). Teams is off (DEC-105): a line that names Teams or
 * email is checked up to the sentence before.
 * Cast: Kavya (sharer) is a new synthetic employee per run (SYN-18000 to SYN-19999, outside the seed), so nothing
 * seeded changes. Rows 1 to 3 are one person, who signs in and types; S-04 saves those words as they are typed, so
 * the same person back on S-04 would get "You have a draft from…" and "Continue that draft", which opens S-04B
 * (J-RESUME/4). Row 4 is therefore a second new person with an empty box, who types the same words and sends the
 * first message; their draft and idea carry from row 4 to row 12. Each variation has its own person too.
 * Sign-in is single sign-on only (BLD-E002): the email route is row 2b alone, waiting on `L-AUTH.email-code`.
 * Voice is on at launch (DEC-108); the "By voice" variation is still left out on S-04, as are the S1 and S2
 * experiments and the phone layouts (V-ACC), apart from v6's one look at the phone's dock and v7's at Home's hint.
 * v7 is Home's mic (WF-02, BLD-C220): a tone for a microphone, which CI's fake speech route hears as its sample.
 * Walk items of 20 Nov: v4 and v5 are the "+" in the prompt box (DEC-124, WF-01) on Home, Share a problem and the
 * draft page; v6 is the Capture first draft page (DEC-125, WF-04), which switches `ai.all` off on the admin page and
 * always back on. v8 is a file while the assistant is off (BLD-C225 to BLD-C227): it waits for the personal details
 * check, says so, and is checked once `ai.all` is back on. Each has its own new person, so the main path's draft is
 * not touched.
 */
import AxeBuilder from "@axe-core/playwright";
import { expect, type Locator, type Page } from "@playwright/test";

import { restoreSwitches, setSwitch, signIn, type SwitchState } from "../e2e/helpers";
import { withSwitchLock } from "../e2e/switch-lock";
import {
  addFile,
  carriedFor,
  expectNoSeriousAxeIssues,
  expectWithDesk,
  openPicker,
  PLUS,
  runSeconds,
  step,
} from "./lib";

// --- Run-time patterns ----------------------------------------------------------------------------------------------

const DAY = String.raw`[A-Z][a-z]+day \d{1,2} [A-Z][a-z]+`; // "Friday 20 November"
const REF = String.raw`IDEA-\d{4}-\d{6}`;
const WEB_HOST = new URL(process.env.E2E_BASE_URL || "http://localhost:3000").host;
const OIDC_AUTHORIZE = `${(process.env.OIDC_ISSUER || "http://localhost:8090/default").replace(/\/$/, "")}/authorize`;
const MAILPIT = (process.env.MAILPIT_URL || "http://localhost:8025").replace(/\/$/, "");

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// --- People: new synthetic employees, one per path, fixed for the run ------------------------------------------------

type Fresh = { emp: string; first: string; name: string; email: string };

function fresh(offset: number, last: string): Fresh {
  const n = 18000 + ((runSeconds() + offset) % 2000);
  return {
    emp: `SYN-${n}`,
    first: "Journey",
    name: `Journey ${last}`,
    email: `journey.${n}.1pc@kfintech.example`,
  };
}

const SHARER = fresh(0, "Sharer");
/** Row 4 on: S-04 with nothing saved yet, so "Start my draft" sends the first message (not J-RESUME's prompt). */
const SENDER = fresh(200, "Sender");
const FROM_HOME = fresh(700, "Homeprompt");
const SIGNED_IN = fresh(1400, "Signedin");
const AREA_WAITS = fresh(500, "Areawait");
const HOME_FILES = fresh(600, "Homefiles");
const BOX_FILES = fresh(800, "Boxfiles");
const CAPTURE = fresh(1600, "Capturefirst");
const HOME_VOICE = fresh(1800, "Homevoice");
const FILE_WAIT = fresh(1900, "Filewait");

async function signInAsFresh(page: Page, who: Fresh): Promise<void> {
  await signIn(page, who.emp, { email: who.email, name: who.name });
}

/** The mock identity provider's form, from S-02's "Use single sign-on" to back in the app (as e2e/helpers.signIn). */
async function singleSignOn(page: Page, who: Fresh): Promise<void> {
  await page.getByRole("button", { name: /^Use single sign-on/ }).click();
  await page.waitForURL((url) => url.href.startsWith(OIDC_AUTHORIZE));
  await page.locator('input[name="username"]').fill(who.emp);
  await page.locator('textarea[name="claims"]').fill(JSON.stringify({ email: who.email, name: who.name }));
  await page.locator('input[type="submit"]').click();
  await page.waitForURL((url) => url.host === WEB_HOST && !url.pathname.startsWith("/auth/"));
  if (new URL(page.url()).pathname === "/privacy-notice") {
    await page.getByRole("button", { name: /I have read this/ }).click();
    await page.waitForURL((url) => url.pathname !== "/privacy-notice");
  }
}

/** Landing → "Share a problem", signed out. Lands on S-02, or straight on S-04 when silent sign-on worked. */
async function shareFromLanding(page: Page): Promise<void> {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { level: 1, name: "Every fix starts with someone who noticed." }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Share a problem" }).first().click();
  await page.waitForURL(/\/(sign-in|share)(\?|$)/);
}

/** S-04's box: "Describe the problem" on the board, its placeholder the example (Compose.md Controls). */
function composeBox(page: Page) {
  return page.getByRole("textbox", { name: /^(Describe the problem|For example: )/ });
}

// --- What the main path carries from row to row ------------------------------------------------------------------------

/** The sharer's own words, with a made-up PAN that S-04 hides (L-HIDE). Synthetic (non-negotiable 11). */
const WORDS =
  "Investors who change their bank mandate at the branch wait a week before the new mandate shows. " +
  "One investor with PAN AAAPZ8888Z called four times last week. It happens about 25 times a week at our branch.";
const PAN_MASKED = "PAN ••••8Z";
const DETAIL = "We raise a ticket for each one and wait two days for an answer.";

const carried = carriedFor<{ draft: string; title: string; idea: string }>("J-SHARE");

function need<K extends keyof typeof carried>(key: K, from: string): string {
  const v = carried[key];
  if (!v) throw new Error(`${from} did not leave ${key}; run the journey from the start`);
  return v;
}

/** Opens a part of Check it by its step button ("2 Sorting Suggested, not confirmed yet" on the board). */
async function openPart(page: Page, part: string): Promise<void> {
  await signInAsFresh(page, SENDER);
  await page.goto(`${need("draft", "J-SHARE/4")}/check`);
  await page.getByRole("button", { name: new RegExp(`^(?:\\d )?${part}\\b`) }).click();
}

// --- J-SHARE.steps ---------------------------------------------------------------------------------------------------

step(
  "J-SHARE/1",
  "S-01",
  "Share a problem on Landing keeps the intent and asks for sign-in only if single sign-on cannot happen silently",
  { needs: ["S-01", "S-02", "L-AUTH"] },
  async ({ page }) => {
    await shareFromLanding(page);
    if (new URL(page.url()).pathname === "/share") {
      // Silent single sign-on worked (L-AUTH.rules/1): straight into the box.
      await expect(composeBox(page)).toBeFocused();
      return;
    }
    // Single sign-on only (BLD-E002): the work email box and "Send code" are the email route (row 2b).
    await expect(page.getByRole("heading", { level: 1, name: "Sign in to 1% Club" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Use single sign-on", exact: true })).toBeEnabled();
  },
);

step(
  "J-SHARE/2",
  "S-02",
  "Single sign-on returns the person to the composer with the cursor in the box",
  { needs: ["S-01", "S-02", "L-AUTH", "S-04"] },
  async ({ page }) => {
    await shareFromLanding(page);
    if (new URL(page.url()).pathname !== "/share") await singleSignOn(page, SHARER);
    // L-AUTH.rules/4: the intent survived the trip to the identity provider.
    await expect(page).toHaveURL(/\/share$/);
    await expect(
      page.getByRole("heading", { level: 1, name: `What keeps getting in your way, ${SHARER.first}?` }),
    ).toBeVisible();
    await expect(composeBox(page)).toBeFocused();
  },
);

step(
  "J-SHARE/2b",
  "S-02",
  "Or by email code: the code arrives, Sign in, and the composer opens the same way",
  { needs: ["S-01", "S-02", "L-AUTH", "L-AUTH.email-code", "S-04"] },
  async ({ page }) => {
    const who = fresh(1000, "Emailcode");
    await shareFromLanding(page);
    await page.getByRole("textbox", { name: /Work email|name@/ }).fill(who.email);
    await page.getByRole("button", { name: "Send code" }).click();
    await expect(page.getByText("Check your email", { exact: true })).toBeVisible();
    await expect(
      page.getByText(
        new RegExp(`^We sent a 6-digit code to ${esc(who.email)}\\. It works for 10 minutes\\.`),
      ),
    ).toBeVisible();
    // The code, as the person reads it in their email (Mailpit in dev).
    const list = await (await page.request.get(`${MAILPIT}/api/v1/search?query=to:${who.email}`)).json();
    const id = String(list.messages?.[0]?.ID ?? "");
    const mail = await (await page.request.get(`${MAILPIT}/api/v1/message/${id}`)).json();
    const code = String(mail.Text ?? "").match(/\b\d{6}\b/)?.[0] ?? "";
    await page.getByRole("textbox", { name: "6-digit code" }).fill(code);
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.waitForURL(/\/share$/);
    await expect(composeBox(page)).toBeFocused();
  },
);

step(
  "J-SHARE/3",
  "S-04",
  "Types the problem in their own words: it saves, the draft starts forming, and Enter starts the draft",
  { needs: ["S-04", "C-DRAFT-PANEL", "L-DRAFT", "L-HIDE"] },
  async ({ page }) => {
    await signInAsFresh(page, SHARER);
    await page.goto("/share");
    await expect(composeBox(page)).toBeFocused();
    await expect(page.getByRole("heading", { level: 2, name: "Your draft" })).toBeVisible();
    await composeBox(page).fill(WORDS);
    await expect(page.getByText(/^(Saving…|Saved at \d{1,2}:\d{2} (am|pm))$/).first()).toBeVisible();
    await expect(page.getByText("Enter starts your draft. Shift and Enter for a new line.")).toBeVisible();
    // From about 25 characters the parts start forming (L-DRAFT.parts).
    await expect(page.getByText("From your first sentence.").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Start my draft" })).toBeEnabled();
  },
);

step(
  "J-SHARE/4",
  "S-04B",
  "Sends the first message: the screen becomes the conversation, the words are the first message, details hidden",
  { needs: ["S-04", "S-04B", "C-DRAFT-LOADER", "C-DRAFT-PANEL", "L-DRAFT", "L-HIDE"] },
  async ({ page }) => {
    // A person with nothing saved: the empty box of row 3, with the words row 3 typed (see the Cast note above).
    await signInAsFresh(page, SENDER);
    await page.goto("/share");
    // An ID an earlier run used may hold a draft; "Start a new one" gives the empty box (J-RESUME/4).
    const startNew = page.getByRole("button", { name: "Start a new one" });
    await expect(startNew.or(composeBox(page)).first()).toBeVisible();
    if (await startNew.isVisible()) await startNew.click();
    await expect(composeBox(page)).toHaveValue("");
    await composeBox(page).fill(WORDS);
    await page.getByRole("button", { name: "Start my draft" }).click();

    await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
    carried.draft = new URL(page.url()).pathname;
    for (const label of ["Tell it", "Check it", "Send it"]) {
      await expect(page.getByText(label, { exact: true }).first()).toBeVisible();
    }
    // The first message is the person's own words, unmasked for them alone (DEC-103).
    await expect(page.getByText(WORDS).first()).toBeVisible();
    await expect(
      page
        .getByText(
          new RegExp(`^Hid \\d+ personal details? from everyone but you: .*${esc(PAN_MASKED)}.*\\.$`),
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "Your draft" })).toBeVisible();
  },
);

step(
  "J-SHARE/5",
  "S-04B",
  "Adds a detail: it goes into the conversation and the draft updates",
  { needs: ["S-04B", "C-DRAFT-PANEL", "L-DRAFT"], after: ["J-SHARE/4"] },
  async ({ page }) => {
    await signInAsFresh(page, SENDER);
    await page.goto(need("draft", "J-SHARE/4"));
    await page
      .getByRole("textbox", { name: "Add a detail, like how often it happens or what you tried" })
      .fill(DETAIL);
    await page.getByRole("button", { name: "Add to your draft" }).click();
    await expect(page.getByText(DETAIL, { exact: true }).first()).toBeVisible();
    await expect(page.getByText(WORDS).first()).toBeVisible();
    await expect(page.getByText(/^(Updating|Up to date)$/).first()).toBeVisible();
    await expect(page.getByText("Add a detail any time. It goes straight into the draft.")).toBeVisible();
  },
);

step(
  "J-SHARE/6",
  "S-04B",
  "Move to Review once the six parts are in: it slides on to Check it, part 1",
  { needs: ["S-04B", "S-05", "C-DRAFT-PANEL", "L-DRAFT"], after: ["J-SHARE/4"] },
  async ({ page }) => {
    await signInAsFresh(page, SENDER);
    const draft = need("draft", "J-SHARE/4");
    await page.goto(draft);
    await expect(page.getByText("Looks right? Check the sorting and send it.").first()).toBeVisible();
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
  "J-SHARE/7",
  "S-05",
  "Part 1, Is this how you'd put it?: the title and parts from their words, the hidden detail, Looks right",
  { needs: ["S-05", "C-HIDDEN", "L-DRAFT", "L-HIDE"], after: ["J-SHARE/4"] },
  async ({ page }) => {
    await openPart(page, "Your words");
    await expect(page.getByRole("heading", { level: 1, name: "Is this how you’d put it?" })).toBeVisible();
    await expect(
      page.getByText(
        "This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.",
      ),
    ).toBeVisible();
    const title = (await page.getByRole("heading", { level: 3 }).first().innerText()).trim();
    expect(title.length).toBeGreaterThan(0);
    carried.title = title;
    await expect(page.getByText("Hidden from everyone").first()).toBeVisible();
    await expect(page.getByText(PAN_MASKED).first()).toBeVisible();
    await expect(page.getByRole("link", { name: "Back to your words" })).toHaveAttribute(
      "href",
      new RegExp(`${esc(need("draft", "J-SHARE/4"))}$`),
    );
    await page.getByRole("button", { name: "Looks right" }).click();
    await expect(page.getByText("Check it, part 2 of 6")).toBeVisible();
  },
);

step(
  "J-SHARE/8",
  "S-05",
  "Part 2, Is it sorted right?: suggestions until confirmed; Confirm sorting records it",
  { needs: ["S-05", "L-SORT"], after: ["J-SHARE/4"] },
  async ({ page }) => {
    await openPart(page, "Sorting");
    await expect(page.getByRole("heading", { level: 1, name: "Is it sorted right?" })).toBeVisible();
    await expect(
      page.getByText(
        "Sorting decides who reviews it. We suggested these from your words. Confirm them, or change any of them.",
      ),
    ).toBeVisible();
    await expect(
      page.getByText("These are suggestions from your words. Not confirmed yet.").first(),
    ).toBeVisible();
    await expect(page.getByRole("radio", { name: "A problem to fix" })).toBeChecked();
    await page.getByRole("button", { name: "Confirm sorting" }).click();
    await expect(page.getByText("Check it, part 3 of 6")).toBeVisible();
    // L-SORT.rules/2: confirmed, so the step no longer reads as a suggestion.
    await expect(page.getByRole("button", { name: /Sorting Suggested, not confirmed yet/ })).toHaveCount(0);
  },
);

step(
  "J-SHARE/9",
  "S-05",
  "Part 3, Has someone raised this already?: similar ideas or none, and Next keeps theirs separate",
  { needs: ["S-05", "C-SIMGRID", "L-SIMILAR"], after: ["J-SHARE/4"] },
  async ({ page }) => {
    await openPart(page, "Similar ideas");
    await expect(
      page.getByRole("heading", { level: 1, name: "Has someone raised this already?" }),
    ).toBeVisible();
    await expect(
      page
        .getByText("Yours, not sent yet")
        .or(page.getByText(/^None of these the same\?/))
        .first(),
    ).toBeVisible();
    await page.getByRole("button", { name: "Next", exact: true }).click();
    await expect(page.getByText("Check it, part 4 of 6")).toBeVisible();
  },
);

step(
  "J-SHARE/10",
  "S-05",
  "Parts 4 to 6 are optional: Skip for now through proof, fix and who would help, to Send it",
  { needs: ["S-05", "L-HIDE"], after: ["J-SHARE/4"] },
  async ({ page }) => {
    await openPart(page, "Proof");
    await expect(page.getByRole("heading", { level: 1, name: "Anything that shows it?" })).toBeVisible();
    await expect(
      page.getByText(/We check each one for personal details before anyone else sees it\.$/).first(),
    ).toBeVisible();
    await page.getByRole("button", { name: "Skip for now" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Got an idea how to solve it?" })).toBeVisible();
    await page.getByRole("button", { name: "Skip for now" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Who would help?" })).toBeVisible();
    await page.getByRole("button", { name: "Skip for now" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Ready to send?" })).toBeVisible();
  },
);

step(
  "J-SHARE/11",
  "S-05",
  "Part 7, Ready to send?: the title from part 1, the declaration, Submit creates the idea",
  { needs: ["S-05", "L-SUBMIT", "S-06"], after: ["J-SHARE/4", "J-SHARE/7"] },
  async ({ page }) => {
    await openPart(page, "Send it");
    await expect(page.getByRole("heading", { level: 1, name: "Ready to send?" })).toBeVisible();
    await expect(
      page.getByText("One last look. You can still change it until the review desk opens it."),
    ).toBeVisible();
    await expect(page.getByText(need("title", "J-SHARE/7"), { exact: true }).first()).toBeVisible();
    await expect(
      page.getByText(
        "By submitting, you confirm there’s no customer personal data in it or its files, and it’s your own work or you’ve credited others.",
      ),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Submit" })
      .or(page.getByRole("link", { name: "Submit" }))
      .click();
    await page.waitForURL(new RegExp(`/ideas/${REF}(?:\\?from=share)?$`));
    carried.idea = new URL(page.url()).pathname;
    // S-06 opens as the first arrival (from=share, S-06.rules/6, S-06.states "Just shared"; BLD-C084): the way back
    // is Home, and the shared date carries how long it took (ideapage/sharer.py: always in seconds).
    await expect(
      page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Home", exact: true }),
    ).toBeVisible();
    await expect(page.getByText(/^Done in \d+ seconds$/)).toBeVisible();
  },
);

step(
  "J-SHARE/12",
  "S-06",
  "Just shared: the reference, the title, when the desk looks, and the edit window",
  { needs: ["S-06", "C-TRACK", "L-SUBMIT"], after: ["J-SHARE/7", "J-SHARE/11"] },
  async ({ page }) => {
    await signInAsFresh(page, SENDER);
    const idea = need("idea", "J-SHARE/11");
    await page.goto(idea);
    await expect(page.getByRole("heading", { level: 1, name: need("title", "J-SHARE/7") })).toBeVisible();
    await expect(page.getByText(idea.split("/").pop() ?? "", { exact: true }).first()).toBeVisible();
    await expectWithDesk(page);
    await expect(
      page.getByText(new RegExp(`^The review desk will look at it by ${DAY}\\.`)).first(),
    ).toBeVisible();
    await expect(
      page
        .getByText(
          new RegExp(
            `^Open to changes until ${DAY}\\. Edit or withdraw it any time before the review desk opens it\\.`,
          ),
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Edit it" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Withdraw" })).toBeVisible();
  },
);

// --- J-SHARE.variants ------------------------------------------------------------------------------------------------

step(
  "J-SHARE/v1",
  "S-04B",
  "From Home's prompt: the words typed on Home arrive on Tell it as the first message",
  { needs: ["S-03", "C-PROMPT", "S-04B", "C-DRAFT-PANEL", "L-DRAFT"] },
  async ({ page }) => {
    const words =
      "Branch staff retype the same nominee details into two screens for every new folio. It takes ten minutes each time.";
    await signInAsFresh(page, FROM_HOME);
    await page.goto("/home");
    await expect(
      page.getByRole("heading", { level: 1, name: `What keeps getting in your way, ${FROM_HOME.first}?` }),
    ).toBeVisible();
    await page.getByRole("textbox", { name: "Say it in your own words" }).fill(words);
    await page.getByRole("link", { name: "Continue to Share a problem" }).click();
    // P-ROUTES.graph: S-04B with the words as the first message, never back to the empty S-04.
    await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
    await expect(page.getByText(words).first()).toBeVisible();
    await expect(page.getByText("Tell it", { exact: true }).first()).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "Your draft" })).toBeVisible();
  },
);

step(
  "J-SHARE/v2",
  "S-04",
  "Already signed in: Share a problem goes straight to the box, with no sign-in",
  { needs: ["S-03", "C-SIDEBAR", "S-04"] },
  async ({ page }) => {
    await signInAsFresh(page, SIGNED_IN);
    await page.goto("/home");
    await page
      .getByRole("link", { name: /^Share a problem/ })
      .first()
      .click();
    await page.waitForURL(/\/share$/);
    await expect(
      page.getByRole("heading", { level: 1, name: `What keeps getting in your way, ${SIGNED_IN.first}?` }),
    ).toBeVisible();
    await expect(composeBox(page)).toBeFocused();
    await expect(page.getByRole("heading", { level: 1, name: "Sign in to 1% Club" })).toHaveCount(0);
  },
);

/** Words the fake draft run (LLM_MODE=fake, BLD-C197) turns into a title and a summary but no area. Synthetic. */
const NO_AREA_WORDS = "Visitors wait at reception because no meeting room shows as free.";

/** A part's value in a list of parts (S-04B's draft panel, S-06's What you shared): the <dd> after its <dt>, the
 * visible one (the phone layout's sheet may hold a second, hidden copy). */
function partValue(page: Page, label: string) {
  return page
    .locator("dt", { hasText: new RegExp(`^${esc(label)}$`) })
    .locator("xpath=following-sibling::dd[1]")
    .filter({ visible: true })
    .first();
}

step(
  "J-SHARE/v3",
  "S-05",
  "The draft can't tell the area: Move to Review is on anyway, the sorting asks for the area, and it sends",
  { needs: ["S-04B", "C-DRAFT-PANEL", "L-DRAFT", "S-05", "L-SORT", "V-FIELDS", "L-SUBMIT", "S-06"] },
  async ({ page }) => {
    await signInAsFresh(page, AREA_WAITS);
    await page.goto("/share");
    const startNew = page.getByRole("button", { name: "Start a new one" });
    await expect(startNew.or(composeBox(page)).first()).toBeVisible();
    if (await startNew.isVisible()) await startNew.click();
    await composeBox(page).fill(NO_AREA_WORDS);
    await page.getByRole("button", { name: "Start my draft" }).click();
    await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
    const draft = new URL(page.url()).pathname;

    // DEC-118: once the run is done, Move to Review is on while the area still waits for words.
    await expect(page.getByText("Up to date", { exact: true }).first()).toBeVisible({ timeout: 30_000 });
    await expect(partValue(page, "Area")).toContainText("Waiting for your words");
    const move = page.getByRole("link", { name: "Move to Review" });
    await expect(move).toBeVisible();
    await expect(page.getByText("Looks right? Check the sorting and send it.")).toBeVisible();
    await expectNoSeriousAxeIssues(page);
    await move.click();
    await page.waitForURL(new RegExp(`${esc(draft)}/check$`));
    await expect(page.getByText("Check it, part 1 of 6")).toBeVisible();
    const title = (await page.getByRole("heading", { level: 3 }).first().innerText()).trim();
    expect(title.length).toBeGreaterThan(0);
    expect(title).not.toBe("Not given.");
    await page.getByRole("button", { name: "Looks right" }).click();

    // Part 2: the words name no area and no one it affects, so neither is suggested, and Confirm sorting keeps
    // part 2 until both are picked (V-FIELDS.sorting: Send needs every field; submit/sorting.py apply()).
    await expect(page.getByText("Check it, part 2 of 6")).toBeVisible();
    const areas = page.getByRole("radiogroup", { name: "Area" });
    const affects = page.getByRole("group", { name: "Who it affects" });
    await expect(areas.getByRole("radio")).not.toHaveCount(0);
    await expect(areas.getByRole("radio", { checked: true })).toHaveCount(0);
    await expect(affects.locator('button[aria-pressed="true"]')).toHaveCount(0);
    await expectNoSeriousAxeIssues(page);
    await page.getByRole("button", { name: "Confirm sorting" }).click();
    await expect(
      page.getByText("Confirm these, or change any of them, before you send.").first(),
    ).toBeVisible();
    await expect(page.getByText("Check it, part 2 of 6")).toBeVisible();
    const operations = areas.getByRole("radio", { name: "Operations" });
    await operations.click();
    await expect(operations).toBeChecked();
    const teams = affects.getByRole("button", { name: "KFin teams" });
    await teams.click();
    await expect(teams).toHaveAttribute("aria-pressed", "true");
    await page.getByRole("button", { name: "Confirm sorting" }).click();
    await expect(page.getByText("Check it, part 3 of 6")).toBeVisible();

    // Parts 3 to 6 as in J-SHARE/9 and /10, then Send it with the title from part 1.
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

    // S-06: the idea is with the review desk, under the area picked in the sorting.
    await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
    await expectWithDesk(page);
    await expect(partValue(page, "Area")).toContainText("Operations");
  },
);

// --- Walk items WF-01 and WF-04: the "+" in every prompt box (DEC-124) and the Capture first draft page (DEC-125) ---

const LINK_LINE =
  "SharePoint, Teams and 1% Club links are marked internal. Anything else is marked external.";
/** DEC-107's second sentence, as J-RECOVER/8 reads it on Check it. */
const FOUND_LINE =
  /^Found a phone number(?: on page \d+)?\. Only you, the review desk and the Ones Committee can open it\.$/;

/** The box's tool row (C-PROMPT.anatomy/2) and its controls from the left. */
function toolRow(page: Page): Locator {
  return page.locator(".cfoot", { has: page.getByRole("button", { name: PLUS }) });
}
function tools(page: Page): Locator {
  return toolRow(page).locator("button, a");
}

/** A file's row in the box (C-FILE.row): the list "Your files and links", one item per file. */
function boxRow(page: Page, name: string): Locator {
  return page
    .getByRole("list", { name: "Your files and links" })
    .getByRole("listitem")
    .filter({ hasText: name });
}

/** S-04 for a new person: the empty box ("Start a new one" if an earlier run left this ID a draft, as row 4). */
async function emptyShare(page: Page): Promise<void> {
  await page.goto("/share");
  const startNew = page.getByRole("button", { name: "Start a new one" });
  await expect(startNew.or(composeBox(page)).first()).toBeVisible();
  if (await startNew.isVisible()) await startNew.click();
  await expect(composeBox(page)).toHaveValue("");
}

step(
  "J-SHARE/v4",
  "S-03",
  'Home\'s "+": the picker, a file that makes the draft, then the same file on the draft page and under Proof',
  { needs: ["S-03", "C-PROMPT.attach", "C-FILE", "S-04B", "S-05"] },
  async ({ page }, info) => {
    info.setTimeout(120_000); // the file's checks can take up to 30 s of it
    const words =
      "Walk-in investors fill the same change form twice because the branch copy and the scanned copy never match.";
    const name = "branch-change-form.pdf";
    await signInAsFresh(page, HOME_FILES);
    await page.goto("/home");
    await expect(
      page.getByRole("heading", { level: 1, name: `What keeps getting in your way, ${HOME_FILES.first}?` }),
    ).toBeVisible();
    // DEC-124: the "+" comes first in the box's tool row.
    await expect(tools(page).first()).toHaveAttribute("aria-label", PLUS);
    await expect(page.getByRole("button", { name: PLUS })).toHaveAttribute("title", PLUS);

    // The picker the Home board draws (`attachments=Picker open`).
    const picker = await openPicker(page);
    await expect(picker.getByText(/^Drop files or a folder here, or/)).toBeVisible();
    for (const label of ["browse", "Choose a folder", "Add link"]) {
      await expect(picker.getByRole("button", { name: label, exact: true })).toBeVisible();
    }
    const link = picker.getByRole("textbox", { name: "Or paste a link to a page, file or idea" });
    await expect(link).toBeVisible();
    await expect(picker.getByText(LINK_LINE)).toBeVisible();
    await expectNoSeriousAxeIssues(page);
    // Escape closes it and focus goes back to the "+".
    await link.focus();
    await expect(link).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(picker).toHaveCount(0);
    await expect(page.getByRole("button", { name: PLUS })).toBeFocused();

    // The first file makes the draft; its row is in the box and the checks pass (DEC-107: scan, then the check).
    await addFile(page, name, "Change form, branch copy and scanned copy, week 47.");
    await expect(boxRow(page, name)).toBeVisible();
    await expect(boxRow(page, name).getByText("Checked", { exact: true })).toBeVisible({ timeout: 30_000 });
    await expect(boxRow(page, name).getByRole("button", { name: `Remove ${name}` })).toBeVisible();

    // Continue: the words go into THAT draft as its first message, and the file travels with it.
    await page.getByRole("textbox", { name: "Say it in your own words" }).fill(words);
    await page.getByRole("link", { name: "Continue to Share a problem" }).click();
    await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
    const draft = new URL(page.url()).pathname;
    await expect(page.getByText(words).first()).toBeVisible();
    await expect(boxRow(page, name).getByText("Checked", { exact: true })).toBeVisible();
    await expect(tools(page).first()).toHaveAttribute("aria-label", PLUS);

    // Check it, part 4: Proof lists the same file.
    await page.goto(`${draft}/check`);
    await page.getByRole("button", { name: /^(?:\d )?Proof\b/ }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Anything that shows it?" })).toBeVisible();
    await expect(page.getByText(name).first()).toBeVisible();
    await expectNoSeriousAxeIssues(page);
  },
);

step(
  "J-SHARE/v5",
  "S-04B",
  'Share a problem\'s "+": a file with a customer detail opens only for you, the review desk and the Ones Committee, and stays with the draft until Remove',
  { needs: ["S-04", "S-04B", "C-PROMPT.attach", "C-FILE", "L-HIDE"] },
  async ({ page }, info) => {
    info.setTimeout(120_000); // the file's checks can take up to 30 s of it
    const words =
      "Couriers call the branch to confirm investor addresses because the dispatch list has no landmark field.";
    const name = "courier-callback-notes.pdf";
    await signInAsFresh(page, BOX_FILES);
    await emptyShare(page);
    // DEC-124: the "+" comes first in the tool row on the empty box too, before the mic and the round button.
    await expect(tools(page).first()).toHaveAttribute("aria-label", PLUS);

    // A file before any words makes the draft (C-PROMPT.attach). Synthetic number, as J-RECOVER/8.
    await addFile(page, name, "Investor called back on 9800000012 about the courier.");
    await expect(boxRow(page, name).getByText(FOUND_LINE)).toBeVisible({ timeout: 30_000 });
    await expectNoSeriousAxeIssues(page);

    // The first message: the same draft, and the row is still in the box on the draft page.
    await composeBox(page).fill(words);
    await page.getByRole("button", { name: "Start my draft" }).click();
    await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
    await expect(page.getByText(words).first()).toBeVisible();
    await expect(tools(page).first()).toHaveAttribute("aria-label", PLUS);
    await expect(boxRow(page, name).getByText(FOUND_LINE)).toBeVisible();

    // Remove takes it out of the box and off the draft.
    await boxRow(page, name)
      .getByRole("button", { name: `Remove ${name}` })
      .click();
    await expect(boxRow(page, name)).toHaveCount(0);
    await page.reload();
    await expect(page.getByText(words).first()).toBeVisible();
    await expect(page.getByText(name)).toHaveCount(0);
  },
);

step(
  "J-SHARE/v6",
  "S-04B",
  'Capture first (the assistant off): no draft panel, the conversation and the box at most 960px wide and centred, "+" then Move to Review with its line; the phone keeps its dock, and Full mode brings the panel back',
  { needs: ["S-04", "S-04B", "C-PROMPT.attach", "C-DRAFT-PANEL", "L-DRAFT", "BLD-D032"] },
  async ({ page, browser }, info) => {
    // Two admin visits, three waits of up to 30 s and the 11 s below: the default 60 s is too short, and a step that
    // times out must still reach its `finally` and put the switch back.
    info.setTimeout(150_000);
    const words =
      "Every month-end the branch prints the same SIP report three times because the export drops the last page.";
    let draft = "";
    const root = page.locator(".cz");
    const moveButton = page.getByRole("button", { name: "Move to Review" });
    const moveLink = page.getByRole("link", { name: "Move to Review" });

    // DEC-125 (1): Capture first is `ai.all` off. Switched on the admin page, as an admin would, and always put back.
    await withSwitchLock("ai.all", async () => {
      // DEC-088: every switch starts on, so "on" is the state to put back if setSwitch fails half-way.
      let before: SwitchState = "on";
      try {
        before = await setSwitch(browser, "ai.all", "off");
        await signInAsFresh(page, CAPTURE);
        // The web reads switches through a 10-second cache, which a change clears (server/killswitch.ts).
        await expect(async () => {
          await emptyShare(page);
          await expect(root).toHaveClass(/\bcapture\b/, { timeout: 2_000 });
        }).toPass({ timeout: 30_000 });

        // DEC-125 (3) on the empty box: "+", then Move to Review, off until there is a draft to check.
        await expect(tools(page).first()).toHaveAttribute("aria-label", PLUS);
        await expect(tools(page).nth(1)).toHaveAccessibleName("Move to Review");
        await expect(moveButton).toHaveAttribute("aria-disabled", "true");
        await expect(page.getByRole("heading", { level: 2, name: "Your draft" })).toHaveCount(0);
        await expectNoSeriousAxeIssues(page);

        await composeBox(page).fill(words);
        await page.getByRole("button", { name: "Start my draft" }).click();
        await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
        draft = new URL(page.url()).pathname;
        await expect(page.getByText(words).first()).toBeVisible();
        await expect(root).toHaveClass(/\bcapture\b/);

        // DEC-130 (BLD-D032): at 1440 the conversation and the prompt box are at most 960px wide, centred in
        // the column the draft panel left (it amends DEC-125 (2), "the full width").
        const middle = async (sel: string) => {
          const box = await page.locator(sel).first().boundingBox();
          if (!box) throw new Error(`DEC-130: ${sel} has no box`);
          return { width: box.width, centre: box.x + box.width / 2 };
        };
        const column = await middle(".cz .cmain");
        for (const sel of [".cz .convo", ".cz .cdock .prompt"]) {
          const part = await middle(sel);
          const off = Math.abs(part.centre - column.centre);
          expect(part.width, `${sel} is at most 960px wide`).toBeLessThanOrEqual(960);
          expect(off, `${sel} is centred in the column`).toBeLessThanOrEqual(2);
        }

        // (2): no draft panel and nothing that forms.
        await expect(page.getByRole("heading", { level: 2, name: "Your draft" })).toHaveCount(0);
        await expect(page.getByText("Forms as you write")).toHaveCount(0);
        await expect(page.getByText(/^Couldn.t work this out\. Add it yourself\.$/)).toHaveCount(0);
        // (3): "+", then Move to Review; DEC-118: on once the words are saved and nothing is building, with its
        // readiness line tied to it for screen readers. Exactly one on the page.
        await expect(tools(page).first()).toHaveAttribute("aria-label", PLUS);
        await expect(tools(page).nth(1)).toHaveAccessibleName("Move to Review");
        await expect(moveLink).toHaveAttribute("href", new RegExp(`${esc(draft)}/check$`), {
          timeout: 30_000,
        });
        await expect(moveLink).toHaveAccessibleDescription("Looks right? Check the sorting and send it.");
        await expect(moveLink.or(moveButton)).toHaveCount(1);
        // (4): the rule-based hint chips stay.
        await expect(page.locator(".nexts .chip").first()).toBeVisible({ timeout: 30_000 });
        await expectNoSeriousAxeIssues(page);

        await moveLink.click();
        await page.waitForURL(new RegExp(`${esc(draft)}/check$`));
        await expect(page.getByText(/^Check it, part \d+ of \d+$/)).toBeVisible();

        // (5): the phone is unchanged: no Capture first layout, and Move to Review stays in its dock.
        await page.setViewportSize({ width: 390, height: 844 });
        await page.goto(draft);
        await expect(page.getByText(words).first()).toBeVisible();
        await expect(root).not.toHaveClass(/\bcapture\b/);
        await expect(moveLink.or(moveButton).filter({ visible: true }).first()).toBeVisible();
        await page.setViewportSize({ width: 1440, height: 900 });
      } finally {
        await restoreSwitches(browser, [["ai.all", before]]);
        // The worker reads switches through its own 10-second cache (core/killswitch.py): wait it out, pass or
        // fail, so the steps after this one meet the assistant on.
        await new Promise((resolve) => setTimeout(resolve, 11_000));
      }
    });

    // (6): Full mode brings today's design back.
    await page.goto(draft);
    await expect(root).not.toHaveClass(/\bcapture\b/);
    await expect(page.getByRole("heading", { level: 2, name: "Your draft" })).toBeVisible();
  },
);

// --- Walk item WF-02: the mic in Home's box (BLD-C220) ----------------------------------------------------------------

/** What CI's fake speech route hears for every 5 seconds of audio (services/worker/gateway/speech.py FAKE_SAMPLE). */
const HEARD =
  "Branch staff type every change of bank form twice because the scanned copy is hard to read, and it adds a day to each request.";

/** axe without the reflow check's 320 px resize, for a state a resize would end: Home's box crosses its phone layout
 * at 640 px (compose.tsx `useIsPhone`) and would remount mid-recording. The same tags and bar as e2e/helpers. */
async function axeInPlace(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
  expect(blocking, `axe on ${page.url()}`).toEqual([]);
}

type Rect = { x: number; y: number; width: number; height: number };

function overlaps(a: Rect, b: Rect): boolean {
  return a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height;
}

step(
  "J-SHARE/v7",
  "S-04B",
  'Home\'s mic: the round button in the empty box, its hint clear of the "+" and the first line on a phone; a tap makes the draft once, and the note lands on Share a problem',
  { needs: ["S-03", "C-PROMPT.voice", "L-DRAFT.voice", "S-04B", "BLD-C220"] },
  async ({ page }, info) => {
    info.setTimeout(120_000); // about 5 seconds of tone for the fake route to hear, then the note is finished
    // CI's browser has no microphone; this one plays a steady tone, which the fake route hears as HEARD. Synthetic.
    await page.addInitScript(() => {
      if (!navigator.mediaDevices) return;
      navigator.mediaDevices.getUserMedia = async () => {
        const ctx = new AudioContext();
        const tone = ctx.createOscillator();
        const out = ctx.createMediaStreamDestination();
        tone.connect(out);
        tone.start();
        return out.stream;
      };
    });
    // Reduced motion keeps the hint from fading after six seconds (compose.css), so nothing races it.
    await page.emulateMedia({ reducedMotion: "reduce" });
    const made: string[] = [];
    page.on("request", (r) => {
      if (r.method() === "POST" && new URL(r.url()).pathname === "/api/drafts") made.push(r.url());
    });
    await signInAsFresh(page, HOME_VOICE);
    await page.goto("/home");
    const box = page.getByRole("textbox", { name: "Say it in your own words" });
    const round = page.getByRole("button", { name: "Tap to start speaking", exact: true });
    const hint = page.locator(".hm-prompt .vhint");
    await expect(box).toHaveValue("");
    await expect(round).toBeVisible();
    await expect(hint).toContainText("Tap to start speaking");
    await expect(hint).toContainText("Not recording until you do");
    // DEC-128: Home lets its own origin use the microphone (where the browser can say).
    const allowed = await page.evaluate(() => {
      const d = document as Document & { featurePolicy?: { allowsFeature(feature: string): boolean } };
      return d.featurePolicy ? d.featurePolicy.allowsFeature("microphone") : null;
    });
    expect(allowed, "DEC-128: the microphone is allowed on Home").not.toBe(false);

    // Lane D's QA: on a phone the hint (about 200 px, two lines, above the round button) covers neither the "+" nor
    // the box's first line, where the placeholder sits.
    await page.setViewportSize({ width: 360, height: 780 });
    await expect(round).toBeVisible();
    await expect(hint).toBeVisible();
    const at = await page.evaluate((plusName) => {
      const prompt = document.querySelector(".hm-prompt");
      const rect = (el: Element | null | undefined) => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { x: r.x, y: r.y, width: r.width, height: r.height };
      };
      const words = prompt?.querySelector("textarea");
      let first: { x: number; y: number; width: number; height: number } | null = null;
      if (words) {
        const r = words.getBoundingClientRect();
        const s = getComputedStyle(words);
        const n = (v: string) => parseFloat(v) || 0;
        const left = n(s.borderLeftWidth) + n(s.paddingLeft);
        const right = n(s.borderRightWidth) + n(s.paddingRight);
        first = {
          x: r.x + left,
          y: r.y + n(s.borderTopWidth) + n(s.paddingTop),
          width: r.width - left - right,
          height: n(s.lineHeight) || n(s.fontSize) * 1.5,
        };
      }
      return {
        hint: rect(prompt?.querySelector(".vhint")),
        plus: rect(prompt?.querySelector(`button[aria-label="${plusName}"]`)),
        first,
      };
    }, PLUS);
    if (!at.hint || !at.plus || !at.first) throw new Error('Home\'s box has its hint, its "+" and its words');
    expect(overlaps(at.hint, at.plus), 'the hint covers the "+"').toBe(false);
    expect(overlaps(at.hint, at.first), "the hint covers the box's first line").toBe(false);
    await page.setViewportSize({ width: 1440, height: 900 });
    await expectNoSeriousAxeIssues(page);

    // A tap makes Home's draft, before any audio, and records (C-PROMPT.voice).
    await round.click();
    const stop = page.getByRole("button", { name: "Stop, and use what you said" });
    await expect(stop).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText("Listening. Up to 3 minutes.")).toBeVisible();
    await axeInPlace(page);
    // About 5 seconds of tone is heard as HEARD, and what is heard comes into the box.
    await expect(box).toHaveValue(new RegExp(esc(HEARD)), { timeout: 30_000 });
    await stop.click();

    // Once the note is finished the page goes on to Share a problem, with the note as the draft's message.
    await page.waitForURL(/\/share\/[0-9a-f-]{36}$/, { timeout: 30_000 });
    await expect(page.getByText(HEARD).first()).toBeVisible();
    expect(made, "Home makes one draft").toHaveLength(1);
    await expectNoSeriousAxeIssues(page);
  },
);

// --- A2: a file while the assistant is off (BLD-C225 to BLD-C227) -----------------------------------------------------

/** BLD-C227: a checking file's line while its personal details check waits for the assistant (check/model.ts
 * `rowView`, from the FileItem's `problem` while `checks.waiting_for` is "gatekeeper"), in the box and on Proof. */
const WAIT_LINE = "Waiting for the personal details check. It runs when the assistant is back.";

step(
  "J-SHARE/v8",
  "S-04B",
  "Capture first: a file waits for the personal details check, says so on the draft page and in Proof, never fails, and is checked once the assistant is back",
  { needs: ["S-04", "S-04B", "S-05", "C-PROMPT.attach", "C-FILE", "L-HIDE", "BLD-C225"] },
  async ({ page, browser }, info) => {
    // Two admin visits, the waits while off, the 11 s below and up to 80 s for the switch-on re-queue (the watch's
    // 60 s gate on a 20 s poll, BLD-C226), then the check itself. A step that times out must still put the switch back.
    info.setTimeout(300_000);
    const words =
      "Branch staff scan the same change of bank form twice because the first scan is too faint to read at the desk.";
    const name = `bank-form-scan-notes-${runSeconds().toString(36)}.pdf`;
    const waiting = boxRow(page, name).getByText(WAIT_LINE, { exact: true });
    const checked = boxRow(page, name).getByText("Checked", { exact: true });
    let draft = "";

    // DEC-125 (1): Capture first is `ai.all` off, switched on the admin page and always put back (BLD-G004).
    await withSwitchLock("ai.all", async () => {
      let before: SwitchState = "on";
      try {
        before = await setSwitch(browser, "ai.all", "off");
        await signInAsFresh(page, FILE_WAIT);
        // The web reads switches through a 10-second cache, which a change clears (server/killswitch.ts).
        await expect(async () => {
          await emptyShare(page);
          await expect(page.locator(".cz")).toHaveClass(/\bcapture\b/, { timeout: 2_000 });
        }).toPass({ timeout: 30_000 });

        // A file with no customer detail (synthetic words only). Its check waits for the gatekeeper without using
        // a try (BLD-C225; non-negotiable 4 keeps it closed to everyone else), and the row says why (BLD-C227).
        await addFile(page, name, "Scan settings for the branch copier: grey scale, one page per form.");
        await expect(waiting).toBeVisible({ timeout: 45_000 });
        await expect(checked).toHaveCount(0);
        await expectNoSeriousAxeIssues(page);

        // The draft page reads the same line from the server: the reason is kept with the file's checks.
        await composeBox(page).fill(words);
        await page.getByRole("button", { name: "Start my draft" }).click();
        await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
        draft = new URL(page.url()).pathname;
        await expect(page.getByText(words).first()).toBeVisible();
        await expect(waiting).toBeVisible();
        await expect(page.getByText(/^Didn.t upload\./)).toHaveCount(0);

        // Check it, part 4: Proof shows the file with the same line.
        await page.goto(`${draft}/check`);
        await page.getByRole("button", { name: /^(?:\d )?Proof\b/ }).click();
        await expect(page.getByRole("heading", { level: 1, name: "Anything that shows it?" })).toBeVisible();
        await expect(page.getByText(name).first()).toBeVisible();
        await expect(page.getByText(WAIT_LINE, { exact: true }).first()).toBeVisible();
        await expect(page.getByText(/^Didn.t upload\./)).toHaveCount(0);
        await expectNoSeriousAxeIssues(page);
      } finally {
        await restoreSwitches(browser, [["ai.all", before]]);
        // The worker reads switches through its own 10-second cache (core/killswitch.py): wait it out, pass or
        // fail, so the steps after this one meet the assistant on.
        await new Promise((resolve) => setTimeout(resolve, 11_000));
      }
    });

    // Back on: the watch queues the waiting check again (BLD-C226) and the file is checked. The draft page is
    // loaded again while it waits, so the row is read from the server each time.
    expect(draft, "the draft page was reached while the assistant was off").toBeTruthy();
    await expect(async () => {
      await page.goto(draft);
      await expect(checked).toBeVisible({ timeout: 5_000 });
    }).toPass({ timeout: 150_000, intervals: [10_000] });
    await expect(waiting).toHaveCount(0);
    await expect(page.getByText(/^Didn.t upload\./)).toHaveCount(0);
  },
);
