import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, settleMotion, signIn } from "./helpers";

/**
 * S-03 Home (`/home`, BLD-C143 to C147), against the local stack. The question and the box, the sections in order
 * with axe clean on desktop and phone; sending from the box makes the draft and opens S-04B on it with the words as
 * the first message, never the empty S-04 (P-ROUTES.graph, V-ACC.share/3, J-SHARE/v1); that draft is then under
 * Drafts in the side bar with when and where it was saved, and opens S-04B (C-SIDEBAR, J-RESUME/2). The Ones' fan
 * on Home: its arrows and the cheer toggle (C-ONES-FAN), cheered and taken back. A new synthetic person per run
 * (SYN-E…), so nothing seeded changes. Synthetic words only.
 */

const WORDS =
  "Synthetic: branch staff retype the same nominee details into two screens for every new folio. It takes ten minutes each time.";

function fresh(tag: string) {
  const id = `SYN-E${tag}${Date.now().toString(36).toUpperCase()}`;
  return {
    id,
    claims: { employeeId: id, email: `${id.toLowerCase()}@kfintech.example`, name: "Synthetic Homer" },
  };
}

async function signInFresh(page: Page, tag: string) {
  const who = fresh(tag);
  await signIn(page, who.id, who.claims);
  return who;
}

const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1280) <= 640;

test("S-03: signed in, / is Home at /home: first visit, then the question, the box, the sections, axe clean", async ({
  page,
}) => {
  // A new person lands on Home after signing in, for the first time: Start here (BLD-C148)
  await signInFresh(page, "H");
  await page.waitForURL((url) => url.pathname === "/home");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: isPhone(page) ? "What gets in your way?" : "What gets in your way at work, Synthetic?",
    }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Start here" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "What happens after you share" })).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Needs you" })).toHaveCount(0);
  await expectNoSeriousAxeIssues(page);

  // Every visit after that: the returning question and the sections
  await page.goto("/");
  await page.waitForURL((url) => url.pathname === "/home");
  await expect(
    page.getByRole("heading", {
      level: 1,
      name: isPhone(page) ? "What’s in your way?" : "What keeps getting in your way, Synthetic?",
    }),
  ).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Say it in your own words" })).toBeVisible();
  await expect(page.getByText("Say it in whichever language feels most natural to you.")).toBeVisible();
  // S-03.sections: Needs you, Your ideas, Find your crew, Or share from where you already are, The Ones
  const sections = ["Needs you", "Your ideas", "Find your crew"];
  for (const name of sections) await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
  await expect(
    page.getByRole("heading", {
      level: 2,
      name: isPhone(page) ? "Or share from where you are" : "Or share from where you already are",
    }),
  ).toBeVisible();
  // A new person: nothing needs them yet, and no ideas yet (Home.md, needsYou=None, yourIdeas=None)
  await expect(page.getByText("Nothing needs you right now.")).toBeVisible();
  await expect(page.getByRole("heading", { level: 3, name: "No ideas yet" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Share your first problem" })).toHaveAttribute(
    "href",
    "/share",
  );
  // The Home item is current on Home (C-SIDEBAR.states)
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.locator('a[href="/home"][aria-current="page"]:visible').first()).toBeVisible();
  await expectNoSeriousAxeIssues(page);
});

test("J-SHARE/v1, J-RESUME/2: sending from Home opens S-04B with the words; the draft is then under Drafts", async ({
  page,
}) => {
  await signInFresh(page, "S");
  await page.goto("/home");
  await page.getByRole("textbox", { name: "Say it in your own words" }).fill(WORDS);
  await expect(page.getByText("Enter starts your draft. Shift and Enter for a new line.")).toBeVisible();
  await page.getByRole("link", { name: "Continue to Share a problem" }).click();
  await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
  const draft = new URL(page.url()).pathname;
  await expect(page.getByText(WORDS).first()).toBeVisible();
  await expect(page.getByText("Picked up where you left off.")).toHaveCount(0);

  // The desktop's draft panel and side bar (C-DRAFT-PANEL, C-SIDEBAR); the phone opens the draft from a sheet and
  // reaches drafts from My ideas
  if (isPhone(page)) return;
  await expect(page.getByRole("heading", { level: 2, name: "Your draft" })).toBeVisible();
  await page.goto("/home");
  const section = page.getByRole("navigation", { name: "Main" }).getByRole("region", { name: "Drafts" });
  const link = section.getByRole("link").first();
  await expect(link).toHaveAttribute("href", draft);
  // The same browser reads the board's words: "on this laptop", never "on your laptop" (BLD-C147, the device cookie)
  await expect(link).toHaveAccessibleName(/(?:Today|Just now), on this laptop$/);
});

test("C-ONES-FAN on Home: the Ones' posts, the arrows and the cheer toggle, axe clean", async ({ page }) => {
  await signInFresh(page, "O");
  await page.waitForURL((url) => url.pathname === "/home");
  const fan = page.getByRole("region", { name: "The Ones", exact: true });
  await expect(fan).toBeVisible();
  const pos = fan.getByText(/^Post 1 of \d+$/);
  await expect(pos).toBeVisible(); // the 1% Club seed has posts
  const total = Number(/of (\d+)/.exec(await pos.innerText())![1]);
  const prev = fan.getByRole("button", { name: "Previous post" });
  const next = fan.getByRole("button", { name: "Next post" });
  await expect(prev).toHaveAttribute("aria-disabled", "true");
  if (total > 1) {
    await next.click();
    await expect(fan.getByText(`Post 2 of ${total}`)).toBeVisible();
    await prev.click();
    await expect(fan.getByText(`Post 1 of ${total}`)).toBeVisible();
  }
  // Cheer the front post, then take it back, so the seed's counts are as they were
  const cheer = fan.getByRole("button", { name: /^Cheer .+ fix, \d+ cheers?$/ }).first();
  await expect(cheer).toHaveAttribute("aria-pressed", "false");
  const liked = page.waitForResponse((r) =>
    /\/api\/ones\/posts\/[^/]+\/like$/.test(new URL(r.url()).pathname),
  );
  await cheer.click();
  expect((await liked).ok()).toBe(true);
  await expect(cheer).toHaveAttribute("aria-pressed", "true");
  await expectNoSeriousAxeIssues(page);
  const unliked = page.waitForResponse((r) =>
    /\/api\/ones\/posts\/[^/]+\/like$/.test(new URL(r.url()).pathname),
  );
  await cheer.click();
  expect((await unliked).ok()).toBe(true);
  await expect(cheer).toHaveAttribute("aria-pressed", "false");
});

/**
 * QA ONLY, lane D's branch d/qa-c245-1, never merged: BLD-C245 on Home and Share at 360 and 320. The picker open, the
 * "+" closes it (a tap, then Enter) and Escape closes it: each time the "+" keeps the focus and is on screen, clear of
 * the top bar and the tab bar; from the keyboard it shows its ring. Screenshots and measures go to
 * test-results/qa-shots. Synthetic data only.
 */
const QA_SHOTS = join(__dirname, "..", "test-results", "qa-shots");

async function qaPlus(page: Page) {
  return page.evaluate(() => {
    const b = document.querySelector<HTMLElement>(".cbox.prompt .attach-btn");
    const r = b?.getBoundingClientRect();
    const top = document.querySelector(".ptop, .pnav")?.getBoundingClientRect();
    const tabs = [...document.querySelectorAll<HTMLElement>(".ptabs, .dock")].filter(
      (e) => getComputedStyle(e).position === "fixed",
    );
    return {
      vh: window.innerHeight,
      plus: r ? { top: r.top, bottom: r.bottom } : null,
      focused: !!b && document.activeElement === b,
      ring: b ? getComputedStyle(b).outlineStyle : "",
      topBar: top ? top.bottom : 0,
      bottomBar: tabs.length
        ? Math.min(...tabs.map((t) => t.getBoundingClientRect().top))
        : window.innerHeight,
      scrollY: window.scrollY,
    };
  });
}

test('QA (lane D, never merged): BLD-C245, the "+" that closes the box\'s picker stays on screen with the focus, Home and Share at 360 and 320', async ({
  page,
}, info) => {
  test.skip(info.project.name !== "phone-360", "phone only");
  test.setTimeout(240_000);
  mkdirSync(QA_SHOTS, { recursive: true });
  const log: Record<string, unknown> = {};
  await signInFresh(page, "K");
  await page.waitForURL((url) => url.pathname === "/home");
  const plus = page
    .locator(".cbox.prompt")
    .getByRole("button", { name: "Add files, a folder or a link", exact: true });
  const picker = page.locator(".fpick.cpick");
  const seen = async (name: string, ring: boolean) => {
    await expect(picker).toHaveCount(0);
    await settleMotion(page);
    const g = await qaPlus(page);
    log[name] = g;
    await page.screenshot({ path: join(QA_SHOTS, `${name}.png`) });
    expect.soft(g.focused, `${name}: the "+" has the focus`).toBe(true);
    expect
      .soft(g.plus?.top ?? -1, `${name}: the "+" is below the top bar`)
      .toBeGreaterThanOrEqual(g.topBar - 0.5);
    expect
      .soft(g.plus?.bottom ?? 1e9, `${name}: the "+" is above the tab bar`)
      .toBeLessThanOrEqual(g.bottomBar + 0.5);
    if (ring) expect.soft(g.ring, `${name}: the "+" shows its ring`).toBe("solid");
  };
  const openPicker = async () => {
    await plus.click();
    await expect(picker).toBeVisible();
    await settleMotion(page);
  };

  for (const path of ["/home", "/share"] as const) {
    for (const [w, h] of [
      [360, 740],
      [320, 640],
    ] as const) {
      const at = `c245${path.replace("/", "-")}-${w}x${h}`;
      await page.setViewportSize({ width: w, height: h });
      await page.goto(path);
      await expect(page.locator(".cbox.prompt textarea")).toBeVisible();
      await settleMotion(page);

      // A tap on the "+" closes it
      await openPicker();
      log[`${at}-0-open`] = await qaPlus(page);
      await page.screenshot({ path: join(QA_SHOTS, `${at}-0-open.png`) });
      await plus.click();
      await seen(`${at}-1-tap`, false);

      // Enter on the "+" closes it, with the ring
      await openPicker();
      await plus.focus();
      await page.keyboard.press("Enter");
      await seen(`${at}-2-enter`, true);

      // Escape from inside the picker, as before
      await openPicker();
      await picker.getByRole("button", { name: "Choose a folder", exact: true }).focus();
      await page.keyboard.press("Escape");
      await seen(`${at}-3-escape`, true);
    }
  }
  writeFileSync(join(QA_SHOTS, "c245-box.json"), JSON.stringify(log, null, 2));
});
