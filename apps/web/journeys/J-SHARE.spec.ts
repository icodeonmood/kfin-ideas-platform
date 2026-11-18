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
 * Voice is on at launch (DEC-108); the "By voice" variation is still left out, as are the S1 and S2 experiments and
 * the phone layouts (V-ACC).
 */
import { expect, type Page } from "@playwright/test";

import { signIn } from "../e2e/helpers";
import { carriedFor, runSeconds, step } from "./lib";

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
    await page.waitForURL(new RegExp(`/ideas/${REF}$`));
    carried.idea = new URL(page.url()).pathname;
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
    await expect(page.getByText("With the review desk", { exact: true }).first()).toBeVisible();
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
