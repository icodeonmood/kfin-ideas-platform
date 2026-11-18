/**
 * J-RESUME: start anywhere, finish anywhere (1pc-handoff/03-journeys/J-RESUME.md). Hand-offs only; the detail of each
 * screen is in V-ACC.resume.
 * Copy: reference/copy/PhoneCompose.md (S-04 on the phone), Home.md (sidebar Drafts), ComposeResume.md (S-04B),
 * Compose.md (S-04 "Existing draft prompt", "Forwarded from email"), Ways.md (S-H3), Inbox.md, SignIn.md (S-02
 * "Session expired mid-draft", single sign-on parts only: email-code sign-in is off, BLD-E002).
 * Cast: Kavya is a new synthetic employee per run (SYN-18000 to SYN-19999), so the draft she starts on the phone is
 * the only one she has and carries from row to row; nothing seeded changes. Row 1 types instead of speaking (the
 * voice variation is left to V-ACC; DEC-108). Rows 5 and 6 need email and Teams intake (L-DRAFT.channels, off until
 * IT, DEC-105); they read Indira's Inbox and Share another way, where I2, a forwarded email that landed as a
 * draft, shows (lane E, 34249f1). I2 is read only.
 */
import { devices, expect, type Page } from "@playwright/test";

import { signIn } from "../e2e/helpers";
import { carriedFor, endSession, runSeconds, seeded, signInAs, snap, step } from "./lib";

const TIME = String.raw`\d{1,2}:\d{2} (?:am|pm)`; // "8:42 pm"
const WEB_HOST = new URL(process.env.E2E_BASE_URL || "http://localhost:3000").host;
const OIDC_AUTHORIZE = `${(process.env.OIDC_ISSUER || "http://localhost:8090/default").replace(/\/$/, "")}/authorize`;
function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// --- The person, fixed for the run (a different offset from J-SHARE's people) ------------------------------------------

const N = 18000 + ((runSeconds() + 350) % 2000);
const ME = { emp: `SYN-${N}`, name: "Journey Resumer", email: `journey.${N}.1pc@kfintech.example` };

async function signInMe(page: Page): Promise<void> {
  await signIn(page, ME.emp, { email: ME.email, name: ME.name });
}

/** Synthetic words (non-negotiable 11). */
const WORDS =
  "Walk-in investors who update their address at the branch fill the same form twice, once for KYC and once for " +
  "the folio. It happens about ten times a day at our branch.";

const carried = carriedFor<{ saved: string; draft: string }>("J-RESUME");

function need<K extends keyof typeof carried>(key: K, from: string): string {
  const v = carried[key];
  if (!v) throw new Error(`${from} did not leave ${key}; run the journey from the start`);
  return v;
}

/** The sidebar's draft entry: "{title} {when}, on your phone" (Home.md Controls). */
function phoneDraftLink(page: Page) {
  return page.getByRole("link", { name: /, on your phone$/ });
}

// --- J-RESUME.steps --------------------------------------------------------------------------------------------------

step(
  "J-RESUME/1",
  "S-04",
  "Starts on the phone, then leaves: the words are saved on the account within moments of a pause",
  { needs: ["S-04", "L-DRAFT"] },
  async ({ browser }, info) => {
    // A phone as the server tells one: by its user agent (server/drafts.ts deviceOf), not by the window's width.
    const context = await browser.newContext({ ...devices["Pixel 7"] });
    const page = await context.newPage();
    try {
      await signInMe(page);
      await page.goto("/share");
      await expect(
        page.getByRole("heading", { level: 1, name: "What’s getting in your way?" }),
      ).toBeVisible();
      await expect(
        page.getByText("Nothing is shared until you send it. Saved as you go, here and on your computer."),
      ).toBeVisible();
      await page.getByRole("textbox", { name: /^(Describe the problem|For example: )/ }).fill(WORDS);
      // L-DRAFT.autosave: saved within 2 seconds of the pause; the time is what the desktop shows next (row 3).
      const saved = page.getByText(new RegExp(`^Saved at ${TIME}$`)).first();
      await expect(saved).toBeVisible({ timeout: 5_000 });
      carried.saved = (await saved.innerText()).replace(/^Saved at /, "").trim();
      // Leaving is the end of the step: the context closes with nothing sent.
    } finally {
      await snap(page, info, "J-RESUME/1", "S-04", "phone");
      await context.close();
    }
  },
);

step(
  "J-RESUME/2",
  "S-03",
  "On the desktop the draft is under Drafts with where it was saved: on your phone",
  { needs: ["S-03", "C-SIDEBAR", "L-DRAFT"] },
  async ({ page }) => {
    await signInMe(page);
    await page.goto("/home");
    await expect(page.getByText("Drafts", { exact: true }).first()).toBeVisible();
    const link = phoneDraftLink(page);
    await expect(link).toHaveCount(1);
    await expect(link).toHaveAccessibleName(
      /(?:Today|Just now|\d+ minutes? ago|[A-Z][a-z]+day), on your phone$/,
    );
    await expect(link).toHaveAttribute("href", /\/share\/[0-9a-f-]{36}$/);
  },
);

step(
  "J-RESUME/3",
  "S-04B",
  "Carry on opens it where it was left: picked up, last saved on your phone at the same time, the words as they were",
  { needs: ["S-04B", "C-SIDEBAR", "L-DRAFT"], after: ["J-RESUME/1"] },
  async ({ page }) => {
    await signInMe(page);
    await page.goto("/home");
    await phoneDraftLink(page).click();
    await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
    carried.draft = new URL(page.url()).pathname;
    await expect(page.getByText("Picked up where you left off.")).toBeVisible();
    await expect(
      page.getByText(new RegExp(`^Last saved on your phone, .*${esc(need("saved", "J-RESUME/1"))}\\.$`)),
    ).toBeVisible();
    await expect(page.getByText(WORDS).first()).toBeVisible();
    await expect(page.getByRole("heading", { level: 2, name: "Your draft" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Start a new one instead" })).toBeVisible();
  },
);

step(
  "J-RESUME/4",
  "S-04",
  "Starting fresh while the draft exists: S-04 offers it back, and Continue that draft opens the same one",
  { needs: ["S-04", "S-04B", "L-DRAFT"], after: ["J-RESUME/3"] },
  async ({ page }) => {
    await signInMe(page);
    await page.goto("/share");
    await expect(page.getByText(/^You have a draft from [^:]+: .+\.$/).first()).toBeVisible();
    await expect(
      page
        .getByText(
          new RegExp(`^Last saved on your phone, ${TIME}\\. Continue it here, or start a new one below\\.$`),
        )
        .first(),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Start a new one" })).toBeVisible();
    await page.getByRole("button", { name: "Continue that draft" }).click();
    await page.waitForURL(new RegExp(`${esc(need("draft", "J-RESUME/3"))}$`));
    await expect(page.getByText(WORDS).first()).toBeVisible();
  },
);

step(
  "J-RESUME/5",
  "S-H5",
  "Sent in by email or Teams: it lands as a draft, and the Inbox says it was kept",
  { needs: ["S-H5", "L-INBOX", "L-DRAFT", "L-DRAFT.channels"] },
  async ({ page }) => {
    // Seed (lane E, 34249f1): Indira forwarded an email; it landed as I2, a draft Indira has not opened.
    const i2 = await seeded("I2");
    await signInAs(page, "indira");
    await page.goto("/inbox");
    const item = page
      .getByRole("button", { name: /^1% Club kept your draft from (?:email|Teams), / })
      .first();
    await expect(item).toBeVisible();
    await item.click();
    await expect(page.getByRole("link", { name: "Carry on" })).toHaveAttribute("href", `/share/${i2.uuid}`);
  },
);

step(
  "J-RESUME/6",
  "S-04B",
  "Check and send on Share another way opens that draft with a banner saying where it came from",
  { needs: ["S-H3", "S-04B", "L-DRAFT", "L-DRAFT.channels"] },
  async ({ page }) => {
    const i2 = await seeded("I2");
    await signInAs(page, "indira");
    await page.goto("/share/other-ways");
    await expect(page.getByText("Arrived from elsewhere", { exact: true })).toBeVisible();
    await page.getByRole("link", { name: "Check and send" }).first().click();
    await page.waitForURL(new RegExp(`/share/${i2.uuid}$`));
    await expect(page.getByText(i2.title).first()).toBeVisible();
    await expect(page.getByText(/^From your (?:email|Teams), /).first()).toBeVisible();
    await expect(
      page.getByText("We turned it into this draft. Nothing has been sent.").first(),
    ).toBeVisible();
  },
);

step(
  "J-RESUME/7",
  "S-02",
  "The session expires mid-draft: Sign in again to carry on, and back to the same draft",
  { needs: ["S-02", "L-AUTH", "S-04B", "L-DRAFT"], after: ["J-RESUME/3"] },
  async ({ page }) => {
    const draft = need("draft", "J-RESUME/3");
    await signInMe(page);
    await page.goto(draft);
    await expect(page.getByText(WORDS).first()).toBeVisible();
    // The session ends on the server (L-AUTH.rules/5), as after 8 hours, and the browser keeps its cookie, so S-02
    // knows whose draft it is.
    await endSession(page);
    await page.reload();
    await page.waitForURL(/\/sign-in/);
    await expect(page.getByText("Sign in again to carry on", { exact: true })).toBeVisible();
    await expect(
      page.getByText(
        "KFintech apps sign everyone out after 8 hours. Your draft is safe, exactly as you left it.",
      ),
    ).toBeVisible();
    await expect(page.getByText(new RegExp(`^Draft, saved ${TIME} on your phone$`))).toBeVisible();

    // Single sign-on only (BLD-E002): no "Send a code to …", so the button has nothing to be "instead" of.
    await page.getByRole("button", { name: "Use single sign-on", exact: true }).click();
    await page.waitForURL((url) => url.href.startsWith(OIDC_AUTHORIZE));
    await page.locator('input[name="username"]').fill(ME.emp);
    await page.locator('textarea[name="claims"]').fill(JSON.stringify({ email: ME.email, name: ME.name }));
    await page.locator('input[type="submit"]').click();
    await page.waitForURL((url) => url.host === WEB_HOST && url.pathname === draft);
    await expect(page.getByText(WORDS).first()).toBeVisible();
  },
);
