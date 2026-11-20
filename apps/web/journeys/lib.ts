/**
 * Lane G's journey suite: every journey in `1pc-handoff/03-journeys/`, end to end, on `main`.
 *
 * One spec per journey (`J-SHARE.spec.ts`…), one test per row of the journey's table, named by the row's ID and its
 * screen ("J-SHARE/3 S-04 · …"). A test checks the hand-off only: the right screen in the right state, the data
 * carried from the step before, the exact copy from `1pc-handoff/reference/copy/<Board>.md`, and the way on to the
 * next step. The detail of each screen stays in its lane's `V-ACC` tests.
 *
 * A row whose screen or logic is not on `main` yet runs as `test.fixme`, naming the missing module. A module counts
 * as on `main` once a test outside this folder names it (lanes put module IDs in test names: "V-ACC.review/4 S-R2"),
 * unless FORCE_FIXME below says otherwise. So nobody has to keep a list up to date as screens land.
 *
 * Data: the 1% Club seed (`make demo DEMO_SET=1pc`, `services/worker/bootstrap/club_seed.py`). A step reads any
 * seeded record, but changes only the records SEED gives to its journey, so journeys never break each other.
 * Synthetic data only (non-negotiable 11).
 */
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";

import { expect, test, type Browser, type Locator, type Page, type TestInfo } from "@playwright/test";
import { Client } from "pg";

import { signIn } from "../e2e/helpers";

export type JourneyId =
  | "J-SHARE"
  | "J-RESUME"
  | "J-RECOVER"
  | "J-SIMILAR"
  | "J-TEAMUP"
  | "J-REVIEW"
  | "J-TRACK"
  | "J-COMMITTEE"
  | "J-ONE"
  | "J-BROWSE";

/** The order of the board and of the walkers' briefs. */
export const JOURNEYS: readonly JourneyId[] = [
  "J-SHARE",
  "J-RESUME",
  "J-RECOVER",
  "J-SIMILAR",
  "J-TEAMUP",
  "J-REVIEW",
  "J-TRACK",
  "J-COMMITTEE",
  "J-ONE",
  "J-BROWSE",
];

// --- People: the 1% Club seed's cast (club_seed.PEOPLE). Never the pack's demo cast. -------------------------------

export const CLUB = {
  tanvi: "SYN-10001", // sharer with ideas at every stage
  harish: "SYN-10002", // review desk
  lavanya: "SYN-10003", // review desk
  manoj: "SYN-10004", // Ones Committee
  shalini: "SYN-10005", // Ones Committee
  kunal: "SYN-10006", // admin
  office: "SYN-10007", // office display
  gopal: "SYN-10008", // build team lead, One No. 15
  rekha: "SYN-10009", // lead with a team-up request waiting
  varun: "SYN-10010", // One No. 11, shipped fix
  pallavi: "SYN-10011",
  siddharth: "SYN-10012", // new One, number still open
  aparna: "SYN-10013", // Founding One, being built
  naveen: "SYN-10014",
  zoya: "SYN-10015",
  bhavesh: "SYN-10016",
  charulata: "SYN-10017", // hides name on the Wall
  dinesh: "SYN-10018",
  esha: "SYN-10019",
  faisal: "SYN-10020",
  geetanjali: "SYN-10021",
  hemant: "SYN-10022",
  indira: "SYN-10023",
  jatin: "SYN-10024",
  kiran: "SYN-10025", // K1's sharer; the review desk asks first (lane E, 34249f1)
} as const;
export type Person = keyof typeof CLUB;

/** First names as copy shows them ("Send 2 answers to the review desk"). */
export function firstName(who: Person): string {
  return who.charAt(0).toUpperCase() + who.slice(1);
}

export async function signInAs(page: Page, who: Person): Promise<void> {
  await signIn(page, CLUB[who]);
}

/**
 * Sign in as a new synthetic employee, for steps that need someone with no drafts or ideas yet (a first share).
 * IDs SYN-18000 to SYN-19999 are outside the seed's range; the tag keeps two steps of one run apart.
 */
export async function signInFresh(page: Page, tag: string): Promise<{ emp: string; name: string }> {
  const n = 18000 + ((runSeconds() + hash(tag)) % 2000);
  const emp = `SYN-${n}`;
  const name = `Journey ${tag}`;
  await signIn(page, emp, { email: `journey.${n}.1pc@kfintech.example`, name });
  return { emp, name };
}

function hash(s: string): number {
  let h = 0;
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) % 2000;
  return h;
}

// --- Seeded ideas, and which journey may change each one ------------------------------------------------------------

/**
 * Every seeded idea by its seed key, with the journey allowed to change it (`null`: read only for everyone). A record
 * is shared only by journeys whose changes add to it and never undo each other (R1: crew joins from a merge and a
 * team-up). Steps that change state create their own data through the UI, or use a record given to their journey.
 */
export const SEED = {
  T1: { title: "Walk-in KYC updates queue twice at the branch", changedBy: "J-RESUME" }, // draft, check:3, voice, on the phone
  T2: { title: "SIP failure SMS gives no reason", changedBy: "J-SIMILAR" }, // draft, check:6, merge request waiting on Rekha
  T3: { title: "Nominee reminders for older folios", changedBy: null }, // archived draft
  T4: { title: "Change of address forms come back for one missing tick", changedBy: null }, // checking
  T5: { title: "Redemption status is not visible to the branch", changedBy: "J-TRACK" }, // with the desk, not opened (edit open)
  T6: { title: "PAN mismatch holds new folios for days", changedBy: "J-TRACK" }, // questions sent and seen (Needs you)
  T7: { title: "Plain words for transaction rejection codes", changedBy: null }, // picked 5 days ago, worth revised, conversation
  T8: { title: "A paid express change-of-bank service", changedBy: null }, // not now
  T9: { title: "Dividend bank mandate reminders go out too late", changedBy: null }, // not picked, reversed to picked (final)
  T10: { title: "Token slips at the branch run out by noon", changedBy: "J-TRACK" }, // withdrawn
  T11: { title: "Investors call twice about failed SIP debits", changedBy: null }, // merged by the desk into R2
  R1: { title: "Investors get no reason when a SIP debit fails", changedBy: ["J-SIMILAR", "J-TEAMUP"] }, // with the desk (Lavanya); crew grows, never decided
  R2: { title: "One clear message after a failed SIP debit", changedBy: null }, // with the desk; desk-merge lead
  V1: { title: "Flag likely-wrong bank details before a payout", changedBy: null }, // shipped 40 days ago (Varun, One)
  S1: { title: "Auto-fill pin code details on the online form", changedBy: "J-ONE" }, // shipped 100 days ago
  D1: { title: "Brokerage statements distributors can read", changedBy: null }, // shipped 200 days ago
  I1: { title: "One checklist for share transfer requests", changedBy: "J-ONE" }, // shipped 45 days ago
  A1: { title: "Pre-fill nominee details from CKYC", changedBy: null }, // being built (Founding One)
  H1: { title: "Retry failed mandate registrations overnight", changedBy: "J-ONE" }, // being built
  P1: { title: "Distributors re-send the same empanelment papers", changedBy: "J-REVIEW" }, // with the desk, not opened
  Z1: { title: "A paid portfolio review for distributors", changedBy: "J-REVIEW" }, // with Harish, questions overdue
  B1: { title: "Courier returns are logged on paper", changedBy: "J-REVIEW" }, // with Lavanya, answered
  C1: { title: "Two teams check the same FATCA declarations", changedBy: "J-COMMITTEE" }, // picked 10 days ago
  E1: { title: "Sell plain-language fund factsheets to AMCs", changedBy: null }, // checking
  F1: { title: "Separate queue for senior citizens at the branch", changedBy: "J-COMMITTEE" }, // not picked 3 days ago
  G1: { title: "Investors cannot download old account statements", changedBy: null }, // not now 2 days ago
  J1: { title: "Co-branded investor webinars with distributors", changedBy: null }, // picked 38 days ago
  N1: { title: "Rejection codes confuse investors at the counter", changedBy: null }, // draft merged into T7
  // Lane E's e/seed-more-4 (34249f1): records of their own for steps that were GAP-SEED.
  K1: { title: "Investors are sent to the wrong branch for their AMC", changedBy: "J-REVIEW" }, // to review, never opened; Lavanya's How often question queued, not sent
  F2: { title: "Change of bank waits for a cancelled cheque by post", changedBy: "J-REVIEW" }, // with Lavanya, opened; lists J2 as similar; leads a desk merge (shared first)
  J2: { title: "Clients wait a week for a bank change to go through", changedBy: "J-REVIEW" }, // with Lavanya, opened; lists F2 as similar
  N2: { title: "Branch staff see no reason when a SIP debit bounces", changedBy: "J-SIMILAR" }, // draft, check:6, merge request waiting on Rekha
  G2: { title: "Failed SIP debit notes show only a bank code", changedBy: "J-SIMILAR" }, // draft, check:6, merge request waiting on Rekha
  I2: { title: "Returned dividend letters go back to old addresses", changedBy: null }, // draft from a forwarded email, not opened; Inbox "kept your draft"
} as const satisfies Record<string, { title: string; changedBy: JourneyId | readonly JourneyId[] | null }>;
export type SeedKey = keyof typeof SEED;

const DATABASE_URL =
  process.env.E2E_DATABASE_URL || "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable";

export type SeededIdea = { uuid: string; ref: string | null; title: string; status: string };

/** A seeded idea as it is now (read only: one row). `ref` is `IDEA-YYYY-NNNNNN`, or null for a draft. */
export async function seeded(key: SeedKey): Promise<SeededIdea> {
  const client = new Client({ connectionString: DATABASE_URL });
  await client.connect();
  try {
    const { rows } = await client.query(
      "SELECT id, idea_id, title, status FROM ideas WHERE title = $1 ORDER BY created_at DESC LIMIT 1",
      [SEED[key].title],
    );
    const row = rows[0];
    if (!row) throw new Error(`seed idea ${key} is missing: load it with make demo DEMO_SET=1pc`);
    return {
      uuid: String(row.id),
      ref: row.idea_id ?? null,
      title: String(row.title),
      status: String(row.status),
    };
  } finally {
    await client.end();
  }
}

/**
 * The run's time base in seconds, the same in every worker (playwright.config.ts sets it once): a journey's synthetic
 * people are made from it, so they stay the same people after a failed step starts a new worker.
 */
export function runSeconds(): number {
  return Number(process.env.JOURNEYS_RUN_SECONDS) || Math.floor(Date.now() / 1000);
}

/** The session's cookie (src/server/auth/session.ts SESSION_COOKIE). */
const SESSION_COOKIE = "ideas_session";

/**
 * Ends the page's session on the server, as the 8 hours would (L-AUTH.rules/5), and leaves its cookie in the browser.
 * S-02 shows "Session expired mid-draft" only to the browser still holding the cookie of a session that ran out
 * (server/auth/session.ts expiredSession); a browser without the cookie has signed out and gets the plain sign-in.
 * The suite's one write outside the screens: the page's own session row, matched by the cookie's hash as the
 * server stores it (sessions.id_hash = sha256 of the token).
 */
export async function endSession(page: Page): Promise<void> {
  const cookie = (await page.context().cookies()).find((c) => c.name === SESSION_COOKIE);
  if (!cookie) throw new Error(`no ${SESSION_COOKIE} cookie: sign in before ending the session`);
  const idHash = createHash("sha256").update(cookie.value, "utf8").digest();
  const client = new Client({ connectionString: DATABASE_URL });
  await client.connect();
  try {
    // As the 8 hours leave it: begun 9 hours ago and ended a minute ago. sessions has CHECK (expires_at > created_at)
    // (20261109000100_sessions_privacy_hr.sql), so the start must move too. The proxy refreshes only a session that
    // readSession accepted, which this one no longer is.
    const { rowCount } = await client.query(
      `UPDATE sessions
          SET created_at = now() - interval '9 hours',
              expires_at = now() - interval '1 minute'
        WHERE id_hash = $1 AND revoked_at IS NULL`,
      [idHash],
    );
    if (rowCount !== 1) throw new Error(`the page's session was not found to end (${rowCount} rows)`);
  } finally {
    await client.end();
  }
}

/** Where a shared idea lives (P-ROUTES.screens: S-06 for its sharer, S-09 for anyone else). One place to change. */
export function ideaUrl(idea: { ref: string | null; uuid: string }, sub = ""): string {
  return `/ideas/${idea.ref ?? idea.uuid}${sub}`;
}

/** A draft on Tell it (`S-04B`) or Check it (`sub` = "/check", `S-05`). */
export function draftUrl(idea: { uuid: string }, sub = ""): string {
  return `/share/${idea.uuid}${sub}`;
}

/** A decision's committee window as stored (read only): when it opened (the decision's time) and where it ends now. */
export async function decisionWindow(idea: { uuid: string }): Promise<{ opensAt: Date; closesAt: Date }> {
  const client = new Client({ connectionString: DATABASE_URL });
  await client.connect();
  try {
    const { rows } = await client.query(
      `SELECT w.opens_at, w.closes_at FROM idea_decisions d JOIN decision_windows w ON w.decision_id = d.id
        WHERE d.idea_uuid = $1 ORDER BY d.at DESC LIMIT 1`,
      [idea.uuid],
    );
    const row = rows[0];
    if (!row) throw new Error("the idea has no decision window: load the seed with make demo DEMO_SET=1pc");
    return { opensAt: new Date(row.opens_at), closesAt: new Date(row.closes_at) };
  } finally {
    await client.end();
  }
}

/** India's offset; it has no daylight saving. */
const IST_MS = 330 * 60_000;

/**
 * L-COMMITTEE.rules/2 (BLD-B258, desk/window.py add_months): the same India calendar day and wall time `months` later,
 * a day the month lacks becoming its last day. Worked out here, not read, so the step checks the rule.
 */
export function addMonthsIST(t: Date, months: number): Date {
  const local = new Date(t.getTime() + IST_MS); // its UTC fields read as India's wall clock
  const index = local.getUTCMonth() + months;
  const year = local.getUTCFullYear() + Math.floor(index / 12);
  const month = index % 12;
  const last = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
  const moved = Date.UTC(
    year,
    month,
    Math.min(local.getUTCDate(), last),
    local.getUTCHours(),
    local.getUTCMinutes(),
    local.getUTCSeconds(),
    local.getUTCMilliseconds(),
  );
  return new Date(moved - IST_MS);
}

const DAY_MS = 86_400_000;

/**
 * Where Extend moves a window's end (desk/window.py next_close, L-COMMITTEE.rules/2, BLD-B263): 30 days on, or the
 * 3-month limit itself when that step would leave less than 7 days before it; null once the end is at the limit.
 */
export function nextCloseIST(opensAt: Date, closesAt: Date): Date | null {
  const cap = addMonthsIST(opensAt, 3);
  if (closesAt.getTime() >= cap.getTime()) return null;
  const step = new Date(closesAt.getTime() + 30 * DAY_MS);
  return cap.getTime() - step.getTime() < 7 * DAY_MS ? cap : step;
}

/** desk/when.py day(): "Monday 8 February", with " 2027" only when the year in India is not this one. */
export function dayIST(t: Date, now: Date = new Date()): string {
  const parts = (d: Date) =>
    Object.fromEntries(
      new Intl.DateTimeFormat("en-GB", {
        timeZone: "Asia/Kolkata",
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      })
        .formatToParts(d)
        .map((p) => [p.type, p.value]),
    );
  const p = parts(t);
  return `${p.weekday} ${p.day} ${p.month}${p.year === parts(now).year ? "" : ` ${p.year}`}`;
}

/** wall/common.py day_label(): "1 Dec 2026" in India time, the month as Python's %b ("Sep", never "Sept"). */
export function dayLabelIST(t: Date): string {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Kolkata",
      day: "numeric",
      month: "long",
      year: "numeric",
    })
      .formatToParts(t)
      .map((x) => [x.type, x.value]),
  );
  return `${p.day} ${String(p.month).slice(0, 3)} ${p.year}`;
}

/**
 * S-06's own card: the article that holds the page's one h1 (ideas/[id]/sharer-screen.tsx). Its pill is the idea's
 * status; a similar idea's tile beside it carries a pill too ("With the review desk"), so a status is read in here.
 */
export function ideaCard(page: Page): Locator {
  return page.getByRole("article").filter({ has: page.getByRole("heading", { level: 1 }) });
}

/**
 * The idea is with the review desk (L-SUBMIT lifecycle): just sent or restored it reads Checking until the worker's
 * submit.check job hands it on, so Checking is allowed first and the page is read again until the card says so.
 */
export async function expectWithDesk(page: Page): Promise<void> {
  const pill = (label: string | RegExp) => ideaCard(page).getByText(label, { exact: true });
  await expect(pill(/^(?:Checking|With the review desk)$/)).toBeVisible();
  await expect
    .poll(
      async () => {
        if (await pill("With the review desk").isVisible()) return true;
        await page.reload();
        return pill("With the review desk").isVisible();
      },
      { timeout: 120_000, intervals: [2_000, 5_000] },
    )
    .toBe(true);
}

/** S-06's "You and the review desk" card (S-06.layout/8): the heading and "Open the conversation". A merged idea
 * keeps it, with the merge line counted, so it never reads "No messages yet" (BLD-E069). */
export async function expectDeskCard(page: Page): Promise<void> {
  const side = page.getByRole("complementary", { name: "The conversation and similar ideas" });
  await expect(side.getByRole("heading", { level: 2, name: "You and the review desk" })).toBeVisible();
  await expect(side.getByRole("link", { name: "Open the conversation" })).toBeVisible();
  await expect(side.getByText(/^No messages yet\./)).toHaveCount(0);
}

// --- Which modules are on main ---------------------------------------------------------------------------------------

/** Off on purpose, so a step that needs them stays fixme even though code exists (reason shown on the board).
 * `L-AUTH.email-code` is not a pack anchor: it names the email-code route of `L-AUTH.rules` for this list. */
export const FORCE_FIXME: Readonly<Record<string, string>> = {
  "L-DRAFT.channels": "email and Teams intake off until IT (DEC-105)",
  "L-AUTH.email-code": "email-code sign-in off until InfoSec (BLD-E002)",
};

const WEB = path.resolve(__dirname, "..");
const REPO = path.resolve(WEB, "..", "..");
const E2E_DIRS = [path.join(WEB, "e2e")];
const TEST_DIRS = [...E2E_DIRS, path.join(WEB, "tests"), path.join(REPO, "services", "worker", "tests")];

const corpora = new Map<string, string>();
function corpusOf(dirs: readonly string[]): string {
  const key = dirs.join("|");
  const cached = corpora.get(key);
  if (cached !== undefined) return cached;
  const parts: string[] = [];
  const walk = (dir: string) => {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory() && entry.name !== "node_modules" && !entry.name.startsWith(".")) walk(p);
      else if (/\.(ts|tsx|py)$/.test(entry.name)) parts.push(fs.readFileSync(p, "utf8"));
    }
  };
  dirs.forEach(walk);
  const corpus = parts.join("\n");
  corpora.set(key, corpus);
  return corpus;
}

/**
 * A module is on main once a test outside this suite names it ("L-SORT", "S-R2.panel/3"…). A screen (`S-`) counts
 * only when an end-to-end test in apps/web/e2e names it: back-end and unit tests name the screens their data serves
 * before the screen is drawn (BLD-G003). `P-` modules are product rules, not code (P-ROUTES.state is kept by the
 * screens that use it), so they never hold a step back.
 */
export function onMain(id: string): boolean {
  if (id in FORCE_FIXME) return false;
  if (id.startsWith("P-")) return true;
  const base = id.split(".")[0]!;
  const corpus = corpusOf(id.startsWith("S-") ? E2E_DIRS : TEST_DIRS);
  const escaped = id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const exact = new RegExp(`(?<![\\w-])${escaped}(?![\\w-])`);
  return base === id ? exact.test(corpus) : exact.test(corpus) || onMain(base);
}

// --- Files -------------------------------------------------------------------------------------------------------------

/** A one-page PDF whose text is `text`: small, valid, made here (synthetic content only). J-RECOVER and J-SHARE. */
export function pdfWith(text: string): Buffer {
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

// --- Steps -------------------------------------------------------------------------------------------------------------

export type StepRef = `${JourneyId}/${string}`;

export type StepOptions = {
  /** Every module the step relies on: its screen, the components it touches, the logic behind it. */
  needs: readonly string[];
  /** Seeded records this step changes; each must be given to this journey in SEED. */
  changes?: readonly SeedKey[];
  /** The seed has no record at the stage this step needs: fixme "GAP-SEED", and lane G tells lane E. */
  gapSeed?: string;
  /** Earlier steps of the same journey this one takes data from (a draft, a URL): fixme while any of them is. */
  after?: readonly StepRef[];
};

/** Steps collected as fixme so far, for `after`. Specs collect in file order, so an earlier step is already here. */
const FIXME_REFS = new Set<StepRef>();
/** Every step collected so far: an `after` ref must be one of these, so a typo or a later row fails collection. */
const DECLARED_REFS = new Set<StepRef>();

export type StepBody = (ctx: { page: Page; browser: Browser }, info: TestInfo) => Promise<void>;

/**
 * What a journey's steps hand on to later ones (a draft's address, a title), as `carried.draft = …` and
 * `carried.draft`. Kept in a file in the run's output folder, which Playwright empties when a run starts, so it
 * outlives the fresh worker Playwright starts after a failed step. Read and written only inside a running step.
 */
export function carriedFor<T extends Record<string, string>>(journey: JourneyId): Partial<T> {
  const file = () => path.join(test.info().project.outputDir, ".carried.json");
  const read = (): Partial<Record<JourneyId, Record<string, string>>> => {
    try {
      return JSON.parse(fs.readFileSync(file(), "utf8"));
    } catch {
      return {};
    }
  };
  return new Proxy({} as Partial<T>, {
    get: (_target, key) => (typeof key === "string" ? read()[journey]?.[key] : undefined),
    set: (_target, key, value) => {
      if (typeof key !== "string") return false;
      const all = read();
      all[journey] = { ...all[journey], [key]: String(value) };
      fs.mkdirSync(path.dirname(file()), { recursive: true });
      fs.writeFileSync(file(), JSON.stringify(all));
      return true;
    },
  });
}

/**
 * One row of a journey's table. `ref` is "J-SHARE/3"; `screen` the screen it lands on ("S-04"). The test is fixme
 * when a needed module is not on main or the seed lacks the record; otherwise it runs and a full-page screenshot is
 * taken at the end, pass or fail.
 */
export function step(ref: StepRef, screen: string, title: string, opts: StepOptions, body: StepBody): void {
  const journey = ref.split("/")[0] as JourneyId;
  for (const key of opts.changes ?? []) {
    const owners: readonly JourneyId[] = [SEED[key].changedBy ?? []].flat();
    if (!owners.includes(journey)) {
      throw new Error(
        `${ref} changes seed record ${key}, which SEED gives to ${owners.join(", ") || "nobody"}`,
      );
    }
  }
  for (const earlier of opts.after ?? []) {
    if (!earlier.startsWith(`${journey}/`) || !DECLARED_REFS.has(earlier)) {
      throw new Error(`${ref} waits for ${earlier}, which is not an earlier step of ${journey}`);
    }
  }
  DECLARED_REFS.add(ref);
  const name = `${ref} ${screen} · ${title}`;
  const fixme = (description: string) => {
    FIXME_REFS.add(ref);
    test.fixme(name, { annotation: { type: "fixme", description } }, () => {});
  };
  if (opts.gapSeed) return fixme(`GAP-SEED: ${opts.gapSeed}`);
  const missing = opts.needs.filter((m) => !onMain(m));
  if (missing.length) {
    const why = missing.map((m) => (m in FORCE_FIXME ? `${m} (${FORCE_FIXME[m]})` : m)).join(", ");
    return fixme(`not on main: ${why}`);
  }
  const waiting = (opts.after ?? []).filter((r) => FIXME_REFS.has(r));
  if (waiting.length) return fixme(`waits for ${waiting.join(", ")}`);
  test(
    name,
    { annotation: { type: "needs", description: opts.needs.join(", ") } },
    async ({ page, browser }, info) => {
      try {
        await body({ page, browser }, info);
      } finally {
        await snap(page, info, ref, screen);
      }
    },
  );
}

export const SHOTS_DIR = path.join(WEB, "test-results", "journeys", "shots");

/** "J-SHARE/3" + "S-04" → J-SHARE/03-S-04.png; "J-REVIEW/A1" → J-REVIEW/A1-S-R2.png. Extra shots add a label. */
export async function snap(
  page: Page,
  info: TestInfo,
  ref: StepRef,
  screen: string,
  label?: string,
): Promise<void> {
  const [journey, row = ""] = ref.split("/");
  const padded = row.replace(/^\d+/, (d) => d.padStart(2, "0")); // 3 → 03, 4a → 04a, A1 stays
  const file = path.join(SHOTS_DIR, journey!, `${padded}-${screen}${label ? `-${label}` : ""}.png`);
  try {
    if (page.isClosed() || page.url() === "about:blank") return; // closed, or never used by the step
    fs.mkdirSync(path.dirname(file), { recursive: true });
    // Animations finished, so a walker reads the screen as it settles, not a frame of a hand-over.
    await page.screenshot({ path: file, fullPage: true, timeout: 10_000, animations: "disabled" });
    await info.attach(path.basename(file), { path: file, contentType: "image/png" });
  } catch {
    // A crashed page has nothing to show; the failure itself is the report.
  }
}
