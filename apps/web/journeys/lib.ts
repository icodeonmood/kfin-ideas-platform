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
import fs from "node:fs";
import path from "node:path";

import { test, type Browser, type Page, type TestInfo } from "@playwright/test";
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
} as const;
export type Person = keyof typeof CLUB;

/** First names as copy shows them ("Send 2 answers to Harish"). */
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
  const n = 18000 + (((Date.now() / 1000 + hash(tag)) % 2000) | 0);
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
 * Every seeded idea by its seed key, with the one journey allowed to change it (`null`: read only for everyone).
 * Steps that change state create their own data through the UI, or use a record given to their journey here.
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
  R1: { title: "Investors get no reason when a SIP debit fails", changedBy: "J-REVIEW" }, // with the desk (Lavanya)
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
} as const satisfies Record<string, { title: string; changedBy: JourneyId | null }>;
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

/** Where a shared idea lives (P-ROUTES.screens: S-06 for its sharer, S-09 for anyone else). One place to change. */
export function ideaUrl(idea: { ref: string | null; uuid: string }, sub = ""): string {
  return `/ideas/${idea.ref ?? idea.uuid}${sub}`;
}

/** A draft on Tell it (`S-04B`) or Check it (`sub` = "/check", `S-05`). */
export function draftUrl(idea: { uuid: string }, sub = ""): string {
  return `/share/${idea.uuid}${sub}`;
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
const TEST_DIRS = [
  path.join(WEB, "e2e"),
  path.join(WEB, "tests"),
  path.join(REPO, "services", "worker", "tests"),
];

let corpus: string | undefined;
function testCorpus(): string {
  if (corpus !== undefined) return corpus;
  const parts: string[] = [];
  const walk = (dir: string) => {
    if (!fs.existsSync(dir)) return;
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory() && entry.name !== "node_modules" && !entry.name.startsWith(".")) walk(p);
      else if (/\.(ts|tsx|py)$/.test(entry.name)) parts.push(fs.readFileSync(p, "utf8"));
    }
  };
  TEST_DIRS.forEach(walk);
  corpus = parts.join("\n");
  return corpus;
}

/** A module is on main once a test outside this suite names it ("S-05", "L-SORT", "S-R2.panel/3"…). */
export function onMain(id: string): boolean {
  if (id in FORCE_FIXME) return false;
  const base = id.split(".")[0]!;
  const escaped = id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const exact = new RegExp(`(?<![\\w-])${escaped}(?![\\w-])`);
  return base === id ? exact.test(testCorpus()) : exact.test(testCorpus()) || onMain(base);
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
};

export type StepBody = (ctx: { page: Page; browser: Browser }, info: TestInfo) => Promise<void>;

/**
 * One row of a journey's table. `ref` is "J-SHARE/3"; `screen` the screen it lands on ("S-04"). The test is fixme
 * when a needed module is not on main or the seed lacks the record; otherwise it runs and a full-page screenshot is
 * taken at the end, pass or fail.
 */
export function step(ref: StepRef, screen: string, title: string, opts: StepOptions, body: StepBody): void {
  const journey = ref.split("/")[0] as JourneyId;
  for (const key of opts.changes ?? []) {
    if (SEED[key].changedBy !== journey) {
      throw new Error(
        `${ref} changes seed record ${key}, which SEED gives to ${SEED[key].changedBy ?? "nobody"}`,
      );
    }
  }
  const name = `${ref} ${screen} · ${title}`;
  if (opts.gapSeed) {
    test.fixme(name, { annotation: { type: "fixme", description: `GAP-SEED: ${opts.gapSeed}` } }, () => {});
    return;
  }
  const missing = opts.needs.filter((m) => !onMain(m));
  if (missing.length) {
    const why = missing.map((m) => (m in FORCE_FIXME ? `${m} (${FORCE_FIXME[m]})` : m)).join(", ");
    test.fixme(name, { annotation: { type: "fixme", description: `not on main: ${why}` } }, () => {});
    return;
  }
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
    if (page.isClosed()) return;
    fs.mkdirSync(path.dirname(file), { recursive: true });
    await page.screenshot({ path: file, fullPage: true, timeout: 10_000 });
    await info.attach(path.basename(file), { path: file, contentType: "image/png" });
  } catch {
    // A crashed page has nothing to show; the failure itself is the report.
  }
}
