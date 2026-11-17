/**
 * J-RECOVER: when something goes wrong (1pc-handoff/03-journeys/J-RECOVER.md). Every failure has plain words and one
 * action, and a draft is never lost. Hand-offs only: the failure's words, the way out, and that the person's work is
 * still there after it. The detail is in V-ACC.recover.
 * Copy: reference/copy/SignIn.md, Compose.md ("Mic blocked", "Offline"), Review.md ("evidence=…", "submit=…", merge
 * states), Status.md ("Withdrawn"); C-DRAFT-LOADER.failure and C-HIDDEN for the lines the boards do not draw.
 * Failures are made in the browser: an identity provider that answers with an error, a microphone the browser refuses,
 * the network switched off, and a failing upload or send answered by `page.route` on its A-API path.
 * Switched off at launch, so not walked here: email-code sign-in (BLD-E002; only row 2 is the email route, and it
 * waits on `L-AUTH.email-code`) and the "couldn't open this link" state, because links are never fetched (BLD-E001).
 * Cast: a new synthetic employee per run for the draft that goes wrong and is sent in the end (rows 5 and 7 to 15), and
 * another for the empty composer (row 4); nothing seeded changes. Tanvi's T1 (failed part, J-RESUME's) and T2 (merge
 * request waiting on Rekha, J-SIMILAR's) are read only.
 */
import { expect, type FileChooser, type Page } from "@playwright/test";

import { signIn } from "../e2e/helpers";
import { CLUB, draftUrl, seeded, signInAs, step } from "./lib";

const DAY = String.raw`[A-Z][a-z]+day \d{1,2} [A-Z][a-z]+`;
const TIME = String.raw`\d{1,2}:\d{2} (?:am|pm)`;
const REF = String.raw`IDEA-\d{4}-\d{6}`;
const WEB_HOST = new URL(process.env.E2E_BASE_URL || "http://localhost:3000").host;
const OIDC_AUTHORIZE = `${(process.env.OIDC_ISSUER || "http://localhost:8090/default").replace(/\/$/, "")}/authorize`;
/** The session's cookie (src/server/auth/session.ts SESSION_COOKIE). */
const SESSION_COOKIE = "ideas_session";

function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// --- People and the draft that goes wrong -----------------------------------------------------------------------------

type Fresh = { emp: string; name: string; email: string };

function fresh(offset: number, last: string): Fresh {
  const n = 18000 + ((Math.floor(Date.now() / 1000) + offset) % 2000);
  return { emp: `SYN-${n}`, name: `Journey ${last}`, email: `journey.${n}.1pc@kfintech.example` };
}

const WRITER = fresh(1100, "Recover");
const MIC = fresh(1700, "Microphone");

async function signInFreshAs(page: Page, who: Fresh): Promise<void> {
  await signIn(page, who.emp, { email: who.email, name: who.name });
}

/** Synthetic words with a made-up folio number that the composer hides (L-HIDE). */
const WORDS =
  "Courier returns of redemption forms are logged in a paper register at the branch. One investor with folio " +
  "7700045612 asked four times where his form was. It happens about ten times a week.";
const FOLIO_MASKED = "Folio ••••12";

const carried: { draft?: string; idea?: string } = {};

/** The writer's draft, made once through S-04 and kept for the rows that follow. */
async function ensureDraft(page: Page): Promise<string> {
  await signInFreshAs(page, WRITER);
  if (carried.draft) return carried.draft;
  await page.goto("/share");
  await page.getByRole("textbox", { name: /^(Describe the problem|For example: )/ }).fill(WORDS);
  await page.getByRole("button", { name: "Start my draft" }).click();
  await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
  carried.draft = new URL(page.url()).pathname;
  return carried.draft;
}

/** Check it at a part, by its step button. */
async function checkPart(page: Page, part: string): Promise<void> {
  const draft = await ensureDraft(page);
  await page.goto(`${draft}/check`);
  await page.getByRole("button", { name: new RegExp(`^(?:\\d )?${part}\\b`) }).click();
}

/** The mock identity provider's form, for a seeded person signing in again. */
async function ssoForm(page: Page, emp: string): Promise<void> {
  await page.waitForURL((url) => url.href.startsWith(OIDC_AUTHORIZE));
  await page.locator('input[name="username"]').fill(emp);
  await page.locator('input[type="submit"]').click();
  await page.waitForURL((url) => url.host === WEB_HOST && !url.pathname.startsWith("/auth/"));
}

/** A one-page PDF whose text is `text`: small, valid, made here (synthetic content only). */
function pdfWith(text: string): Buffer {
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    "",
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  const stream = `BT /F1 14 Tf 72 760 Td (${text}) Tj ET`;
  objects[3] = `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`;
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((body, i) => {
    offsets.push(out.length);
    out += `${i + 1} 0 obj\n${body}\nendobj\n`;
  });
  const xref = out.length;
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const o of offsets) out += `${String(o).padStart(10, "0")} 00000 n \n`;
  out += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(out, "latin1");
}

/** A-API.files `POST /files` (multipart, with `draft_id`): every upload, a draft's or an answer's (lane C). */
const UPLOAD = (url: URL): boolean => url.pathname === "/api/files";
/** A-API.drafts `POST /drafts/:id/submit`. */
const SUBMIT = (url: URL): boolean => /^\/api\/drafts\/[^/]+\/submit$/.test(url.pathname);

type Upload = Parameters<FileChooser["setFiles"]>[0];

/**
 * Attaches a file the way a person does: "Attach files" (C-FILE.uploader), then the file picker. The control opens
 * the picker itself, or a drop area whose "browse" opens it (C-FILE.uploader/1, /5).
 */
async function attach(page: Page, file: Upload): Promise<void> {
  const picker = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Attach files" }).click();
  const browse = page
    .getByRole("button", { name: /\bbrowse\b/i })
    .or(page.getByText(/^browse$/i))
    .first();
  const opened = await Promise.race([
    picker,
    browse.waitFor({ timeout: 10_000 }).then(
      () => null,
      () => null,
    ),
  ]);
  if (!opened) await browse.click();
  await (opened ?? (await picker)).setFiles(file);
}

// --- J-RECOVER rows ----------------------------------------------------------------------------------------------------

step(
  "J-RECOVER/1",
  "S-02",
  "Sign-in fails: plain words, nothing lost, a reference for the IT desk, and Try again (single sign-on only, BLD-E002)",
  { needs: ["S-01", "S-02", "L-AUTH"] },
  async ({ page }) => {
    // The identity provider answers with an error (OIDC error response), as when it times out.
    await page.route(
      (url) => url.href.startsWith(OIDC_AUTHORIZE),
      async (route) => {
        const asked = new URL(route.request().url());
        const back = new URL(asked.searchParams.get("redirect_uri") ?? `http://${WEB_HOST}/`);
        back.searchParams.set("error", "temporarily_unavailable");
        back.searchParams.set("state", asked.searchParams.get("state") ?? "");
        await route.fulfill({ status: 302, headers: { location: back.href } });
      },
    );
    await page.goto("/");
    await page.getByRole("link", { name: "Share a problem" }).first().click();
    const sso = page.getByRole("button", { name: "Use single sign-on" });
    const failed = page.getByText("We couldn't sign you in", { exact: true });
    await expect(sso.or(failed)).toBeVisible();
    if (await sso.isVisible()) await sso.click();

    await expect(failed).toBeVisible();
    await expect(page.getByText("Your KFintech account didn't answer in time.")).toBeVisible();
    await expect(
      page.getByText(
        "This is usually a short network hiccup on the office Wi-Fi or VPN. Nothing you typed is lost.",
      ),
    ).toBeVisible();
    await expect(page.getByText(new RegExp(`SSO-[0-9A-F]{4}, ${TIME}`))).toBeVisible();
    // The intent is kept (L-AUTH.rules/4); the board's "Or get a code by email instead." waits on BLD-E002.
    await expect(page.getByText(/^You will still go straight to Share a problem\./)).toBeVisible();
    await expect(page.getByRole("link", { name: "Try again" })).toBeVisible();
  },
);

step(
  "J-RECOVER/2",
  "S-02",
  "Wrong code: That code didn't match, how many tries are left, and when a new code can be asked for",
  { needs: ["S-02", "L-AUTH", "L-AUTH.email-code"] },
  async ({ page }) => {
    const who = fresh(1300, "Wrongcode");
    await page.goto("/sign-in");
    await page.getByRole("textbox", { name: /Work email|name@/ }).fill(who.email);
    await page.getByRole("button", { name: "Send code" }).click();
    await page.getByRole("textbox", { name: "6-digit code" }).fill("000000");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(
      page.getByText("That code didn’t match. Check the latest email from 1% Club. 2 tries left."),
    ).toBeVisible();
    await expect(page.getByText(/^You can ask for a new code in \d:\d{2}\.$/)).toBeVisible();
    await expect(page.getByRole("textbox", { name: "6-digit code" })).toBeEditable();
  },
);

step(
  "J-RECOVER/3",
  "S-02",
  "The session expires mid-draft: the draft is named and safe, and signing in returns to it",
  { needs: ["S-02", "L-AUTH", "S-04B", "L-DRAFT"] },
  async ({ page }) => {
    const t1 = await seeded("T1");
    await signInAs(page, "tanvi");
    await page.goto(draftUrl(t1));
    // The session ends (L-AUTH.rules/5): only its cookie goes, so S-02 still knows whose draft it was.
    await page.context().clearCookies({ name: SESSION_COOKIE });
    await page.reload();
    await page.waitForURL(/\/sign-in/);
    await expect(page.getByText("Sign in again to carry on", { exact: true })).toBeVisible();
    await expect(
      page.getByText(
        "KFintech apps sign everyone out after 8 hours. Your draft is safe, exactly as you left it.",
      ),
    ).toBeVisible();
    await expect(page.getByText(t1.title, { exact: true })).toBeVisible();
    // Single sign-on only (BLD-E002): no "Send a code to …", so the button has nothing to be "instead" of.
    await page.getByRole("button", { name: "Use single sign-on", exact: true }).click();
    await ssoForm(page, CLUB.tanvi);
    await expect(page).toHaveURL(new RegExp(`${esc(draftUrl(t1))}$`));
  },
);

step(
  "J-RECOVER/4",
  "S-04",
  "Microphone blocked: the warning under the box, and typing still works",
  { needs: ["S-04", "L-DRAFT"] },
  async ({ page }) => {
    await page.addInitScript(() => {
      const refuse = () => Promise.reject(new DOMException("Permission denied", "NotAllowedError"));
      if (navigator.mediaDevices) navigator.mediaDevices.getUserMedia = refuse;
    });
    await signInFreshAs(page, MIC);
    await page.goto("/share");
    await page.getByRole("button", { name: "Tap to start speaking" }).click();
    await expect(page.getByText("Your browser has blocked the microphone.")).toBeVisible();
    await expect(
      page.getByText(
        "Allow it from the lock icon in the address bar, then try again. Or just type in the box above.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("textbox", { name: /^(Describe the problem|For example: )/ })).toBeEditable();
  },
);

step(
  "J-RECOVER/5",
  "S-04B",
  "Offline while writing: Unsaved, you're offline; back online, it saves and the detail is kept",
  { needs: ["S-04", "S-04B", "L-DRAFT"] },
  async ({ page }) => {
    const draft = await ensureDraft(page);
    await page.goto(draft);
    const detail = "We started a spreadsheet last month but nobody keeps it up to date.";
    await page.context().setOffline(true);
    await page
      .getByRole("textbox", { name: "Add a detail, like how often it happens or what you tried" })
      .fill(detail);
    await page.getByRole("button", { name: "Add to your draft" }).click();
    await expect(page.getByText("Unsaved, you’re offline").first()).toBeVisible();
    await page.context().setOffline(false);
    await expect(page.getByText(new RegExp(`^Saved at ${TIME}$`)).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(detail, { exact: true }).first()).toBeVisible();
  },
);

step(
  "J-RECOVER/6",
  "S-04B",
  "A draft part fails: its slot says Couldn't work this out. Add it yourself. with Change, and typing goes on",
  { needs: ["S-04B", "C-DRAFT-LOADER", "L-DRAFT"] },
  async ({ page }) => {
    const t1 = await seeded("T1");
    await signInAs(page, "tanvi");
    await page.goto(draftUrl(t1));
    const failed = page.getByText("Couldn't work this out. Add it yourself.").first();
    await expect(failed).toBeVisible();
    await expect(page.getByRole("button", { name: /^Change/ }).first()).toBeVisible();
    await expect(
      page.getByRole("textbox", { name: "Add a detail, like how often it happens or what you tried" }),
    ).toBeEditable();
  },
);

step(
  "J-RECOVER/7",
  "S-05",
  "A file fails to upload: Didn't upload. Your other files are fine., with Try again and Remove",
  { needs: ["S-05", "C-FILE"] },
  async ({ page }) => {
    await checkPart(page, "Proof");
    await page.route(UPLOAD, (route) =>
      route.request().method() === "POST" ? route.abort("failed") : route.fallback(),
    );
    const name = "courier-register-photo.png";
    await attach(page, { name, mimeType: "image/png", buffer: Buffer.from("89504e470d0a1a0a", "hex") });
    await expect(page.getByText("Didn’t upload. Your other files are fine.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
    await page.unroute(UPLOAD);
    await page.getByRole("button", { name: `Remove ${name}` }).click();
    await expect(page.getByText(name)).toHaveCount(0);
  },
);

step(
  "J-RECOVER/8",
  "S-05",
  "A file has personal data: nobody can open it until it is hidden; Hide it for me or Remove",
  { needs: ["S-05", "C-FILE", "L-HIDE"] },
  async ({ page }) => {
    await checkPart(page, "Proof");
    const name = "courier-call-log.pdf";
    await attach(page, {
      name,
      mimeType: "application/pdf",
      buffer: pdfWith("Investor called back on 9800000012 about the courier."),
    });
    await expect(
      page.getByText(/^Found a phone number(?: on page \d+)?\. Nobody can open it until it’s hidden\.$/),
    ).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Hide it for me" })).toBeVisible();
    await page.getByRole("button", { name: `Remove ${name}` }).click();
    await expect(page.getByText(name)).toHaveCount(0);
  },
);

step(
  "J-RECOVER/9",
  "S-05",
  "A link is kept as typed and never opened (BLD-E001)",
  { needs: ["S-05", "C-FILE"] },
  async ({ page }) => {
    const host = "intranet.kfintech.example";
    const opened: string[] = [];
    page.on("request", (request) => {
      if (new URL(request.url()).host === host) opened.push(request.url());
    });
    await checkPart(page, "Proof");
    await page
      .getByRole("textbox", { name: "Paste a link, or attach files. Add several links at once with commas." })
      .fill(`https://${host}/courier-returns`);
    await page.getByRole("button", { name: "Add a link" }).click();

    // C-FILE.row: the address or its domain, with Remove. Nothing tried to open it, so nothing says it failed.
    const row = page.getByRole("button", { name: new RegExp(`^Remove .*${esc(host)}`) });
    await expect(row).toBeVisible();
    await expect(page.getByText(new RegExp(esc(host))).first()).toBeVisible();
    await expect(page.getByText(/couldn[’']t open this link/)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Keep it" })).toHaveCount(0);

    // Kept with the draft: still there when the part is opened again.
    await page.reload();
    await page.getByRole("button", { name: /^(?:\d )?Proof\b/ }).click();
    await expect(row).toBeVisible();
    await expect(page.getByText(/couldn[’']t open this link/)).toHaveCount(0);
    expect(opened).toEqual([]);
  },
);

step(
  "J-RECOVER/10",
  "S-05",
  "Wrong sorting: each suggestion shows its reason, and one choice changes it",
  { needs: ["S-05", "L-SORT"] },
  async ({ page }) => {
    await checkPart(page, "Sorting");
    await expect(page.getByRole("heading", { level: 1, name: "Is it sorted right?" })).toBeVisible();
    await expect(page.getByText(/^Suggested because /).first()).toBeVisible();
    const operations = page.getByRole("radio", { name: "Operations", exact: true });
    const other = (await operations.isChecked())
      ? page.getByRole("radio", { name: "Investor service", exact: true })
      : operations;
    await other.click();
    await expect(other).toBeChecked();
    await expect(page.getByRole("button", { name: "Confirm sorting" })).toBeEnabled();
  },
);

step(
  "J-RECOVER/11",
  "S-05",
  "A hidden detail that is not personal: Show it asks for one of three reasons and notes it",
  { needs: ["S-05", "C-HIDDEN", "L-HIDE"] },
  async ({ page }) => {
    await checkPart(page, "Your words");
    await expect(page.getByText(FOLIO_MASKED).first()).toBeVisible();
    await page.getByRole("button", { name: "Show it" }).first().click();
    // C-HIDDEN/1–3 write straight apostrophes; a lane may set them curly. Either is the same words.
    await expect(
      page.getByText(/^Only show it if it isn[’']t about a real customer\. What is it\?$/),
    ).toBeVisible();
    await expect(page.getByText("We note your reason with the idea.")).toBeVisible();
    for (const reason of [/^it[’']s a scheme or product code$/, /^it[’']s an internal reference$/]) {
      await expect(page.getByRole("radio", { name: reason })).toBeVisible();
    }
    await page.getByRole("radio", { name: /^it[’']s made up for the example$/ }).click();
    await page.getByRole("button", { name: "Show it" }).last().click();
    await expect(page.getByText(/^Shown, because it[’']s made up for the example\.?$/).first()).toBeVisible();
  },
);

step(
  "J-RECOVER/12",
  "S-05",
  "Submit before the sorting is confirmed: Confirm the sorting first, with Go to the sorting",
  { needs: ["S-05", "L-SUBMIT", "L-SORT"] },
  async ({ page }) => {
    await checkPart(page, "Send it");
    await page.getByRole("button", { name: "Submit" }).click();
    await expect(page.getByText("Confirm the sorting first, or change any of it.")).toBeVisible();
    await page.getByRole("button", { name: "Go to the sorting" }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Is it sorted right?" })).toBeVisible();
  },
);

step(
  "J-RECOVER/13",
  "S-05",
  "Send fails: Couldn't send. Your draft is safe., with Try again, and the draft is still here",
  { needs: ["S-05", "L-SUBMIT", "L-SORT"] },
  async ({ page }) => {
    await checkPart(page, "Sorting");
    await page.getByRole("button", { name: "Confirm sorting" }).click();
    await page.getByRole("button", { name: /^(?:\d )?Send it\b/ }).click();
    await page.route(SUBMIT, (route) =>
      route.request().method() === "POST"
        ? route.fulfill({
            status: 503,
            contentType: "application/json",
            body: JSON.stringify({ error: { code: "unavailable", message: "Service unavailable" } }),
          })
        : route.fallback(),
    );
    await page.getByRole("button", { name: "Submit" }).click();
    await expect(
      page.getByText("Couldn’t send. Your draft is safe. Check your connection, then try again."),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Try again" }).or(page.getByRole("button", { name: "Try again" })),
    ).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`${esc(carried.draft ?? "")}/check$`));
    await page.unroute(SUBMIT);
  },
);

step(
  "J-RECOVER/14",
  "S-05",
  "Offline at send: it says it will send when back online, and once online it lands on the idea's page",
  { needs: ["S-05", "L-SUBMIT", "S-06"] },
  async ({ page }) => {
    await checkPart(page, "Send it");
    await page.context().setOffline(true);
    await expect(
      page.getByText(
        "You’re offline. Your draft is saved on this device. Submit now and it sends when you’re back online.",
      ),
    ).toBeVisible();
    await page.getByRole("button", { name: "Submit" }).click();
    await page.context().setOffline(false);
    await page.waitForURL(new RegExp(`/ideas/${REF}$`), { timeout: 20_000 });
    carried.idea = new URL(page.url()).pathname;
    await expect(page.getByText("With the review desk", { exact: true }).first()).toBeVisible();
  },
);

step(
  "J-RECOVER/15",
  "S-06",
  "Change of mind after sending: Edit and Withdraw until the desk opens it; withdrawn, then restored",
  { needs: ["S-06", "L-SUBMIT"], after: ["J-RECOVER/14"] },
  async ({ page }) => {
    await signInFreshAs(page, WRITER);
    const idea = carried.idea;
    if (!idea) throw new Error("J-RECOVER/14 did not leave the idea; run the journey from the start");
    await page.goto(idea);
    await expect(
      page.getByText(new RegExp(`^Open to changes until ${DAY}\\. Edit or withdraw it any time`)).first(),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Edit it" })).toBeVisible();
    await page.getByRole("button", { name: "Withdraw" }).click();
    await page.getByRole("button", { name: "Withdraw it" }).click();
    await expect(page.getByText("Withdrawn. It’s back in your drafts.").first()).toBeVisible();
    await page.getByRole("button", { name: "Restore it" }).click();
    await expect(page.getByText("With the review desk", { exact: true }).first()).toBeVisible();
  },
);

step(
  "J-RECOVER/16",
  "S-05",
  "The lead has not answered a merge request: the draft waits, with Withdraw the request",
  { needs: ["S-05", "L-MERGE"] },
  async ({ page }) => {
    const t2 = await seeded("T2");
    await signInAs(page, "tanvi");
    await page.goto(draftUrl(t2, "/check"));
    await page.getByRole("button", { name: /^(?:\d )?Similar ideas\b/ }).click();
    await expect(
      page.getByText(
        "Waiting for Rekha to accept the merge. If Rekha declines, you can send yours on its own.",
      ),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Withdraw the request" })).toBeEnabled();
  },
);
