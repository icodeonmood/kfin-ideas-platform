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
 * QA ONLY, lane D's branch d/qa-train24-1, never merged: train 24 (102c4d45) at the usual sizes, 1440, 1024, 640, 360
 * and 320. Screenshots and measures go to test-results/qa-shots for lane D to read. Synthetic data only.
 */
const QA_SHOTS = join(__dirname, "..", "test-results", "qa-shots");
const QA_SIZES = [
  [1440, 900],
  [1024, 768],
  [640, 900],
  [360, 740],
  [320, 640],
] as const;
type QaBox = { top: number; bottom: number; left: number; right: number; width: number; height: number };
type QaRow = {
  row: QaBox;
  inner: QaBox | null;
  name: QaBox | null;
  clipped: boolean;
  acts: QaBox | null;
  x: QaBox | null;
  msg: QaBox | null;
  isMsg: boolean;
  spin: boolean;
  status: string;
};
/** The file rows of the list `list` (inside `inSel`) and the page's sideways scroll, measured in the page. */
async function qaRows(page: Page, list: string, inSel: string) {
  return page.evaluate(
    ([listSel, boxSel]) => {
      const box = (el: Element | null | undefined) => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {
          top: r.top,
          bottom: r.bottom,
          left: r.left,
          right: r.right,
          width: r.width,
          height: r.height,
        };
      };
      const ul = document.querySelector(listSel);
      const rows: QaRow[] = [...(ul?.querySelectorAll(":scope > .frow") ?? [])].map((li) => {
        const n = li.querySelector<HTMLElement>(".frow-n");
        return {
          row: box(li)!,
          inner: box(li.querySelector(".frow-in")),
          name: box(n),
          clipped: n ? n.scrollWidth > n.clientWidth : false,
          acts: box(li.querySelector(".frow-a")),
          x: box(li.querySelector(".frow-x, .cfile-x")),
          msg: box(li.querySelector(".fmsg")),
          isMsg: li.classList.contains("frow-msg"),
          spin: !!li.querySelector(".spin"),
          status: li.querySelector(".frow-st")?.textContent ?? "",
        };
      });
      const html = document.documentElement;
      return {
        vw: window.innerWidth,
        sideways: html.scrollWidth - html.clientWidth,
        live: ul?.getAttribute("aria-live") ?? null,
        list: box(ul),
        within: box(ul?.closest(boxSel)),
        rows,
      };
    },
    [list, inSel] as const,
  );
}

/** The picker (C-FILE.uploader) inside `inSel`: its box, its controls and the page's sideways scroll. */
async function qaPicker(page: Page, inSel: string) {
  return page.evaluate((boxSel) => {
    const box = (el: Element | null | undefined) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height };
    };
    const p = document.querySelector(".fpick");
    const html = document.documentElement;
    return {
      vw: window.innerWidth,
      sideways: html.scrollWidth - html.clientWidth,
      within: box(p?.closest(boxSel)),
      picker: box(p),
      folder: box(p?.querySelector(".fpick-folder")),
      browse: box(p?.querySelector(".fpick-drop .tb")),
      drop: box(p?.querySelector(".fdrop")),
      input: box(p?.querySelector(".fpick-link .fld")),
      add: box(p?.querySelector(".fpick-link button")),
      help: box(p?.querySelector(".fpick-h")),
      helpText: p?.querySelector(".fpick-h")?.textContent ?? "",
    };
  }, inSel);
}

type QaPick = Awaited<ReturnType<typeof qaPicker>>;
/** The picker's checks at one size: inside its box, every control inside it, nothing sideways. */
function qaPickChecks(name: string, g: QaPick) {
  expect.soft(g.sideways, `${name}: no sideways scroll`).toBeLessThanOrEqual(0);
  expect.soft(g.picker, `${name}: the picker is there`).not.toBeNull();
  if (!g.picker || !g.within) return;
  expect
    .soft(g.picker.left, `${name}: the picker starts inside its box`)
    .toBeGreaterThanOrEqual(g.within.left - 0.5);
  expect
    .soft(g.picker.right, `${name}: the picker ends inside its box`)
    .toBeLessThanOrEqual(g.within.right + 0.5);
  expect.soft(g.picker.right, `${name}: the picker ends on the screen`).toBeLessThanOrEqual(g.vw);
  for (const [what, b] of [
    ["Choose a folder", g.folder],
    ["browse", g.browse],
    ["the link field", g.input],
    ["Add link", g.add],
  ] as const) {
    expect.soft(b, `${name}: ${what} is there`).not.toBeNull();
    if (!b) continue;
    expect
      .soft(b.left, `${name}: ${what} starts inside the picker`)
      .toBeGreaterThanOrEqual(g.picker.left - 0.5);
    expect.soft(b.right, `${name}: ${what} ends inside the picker`).toBeLessThanOrEqual(g.picker.right + 0.5);
    expect.soft(b.height, `${name}: ${what} is at least 24px high`).toBeGreaterThanOrEqual(24);
  }
  expect.soft(g.folder?.width, `${name}: Choose a folder is 44px`).toBeCloseTo(44, 0);
  expect.soft(g.folder?.height, `${name}: Choose a folder is 44px`).toBeCloseTo(44, 0);
  expect.soft(g.input?.width ?? 0, `${name}: the link field keeps room to type`).toBeGreaterThanOrEqual(120);
  if (g.folder && g.drop) {
    expect
      .soft(g.folder.top, `${name}: Choose a folder sits in the drop area`)
      .toBeGreaterThanOrEqual(g.drop.top - 0.5);
  }
}

type QaRows = Awaited<ReturnType<typeof qaRows>>;
/** The rows' checks at one size. Compact rows: 260px at most, one line, the name gives way, Remove 32px. */
function qaRowChecks(name: string, g: QaRows, compact: boolean) {
  expect.soft(g.sideways, `${name}: no sideways scroll`).toBeLessThanOrEqual(0);
  expect.soft(g.rows.length, `${name}: the rows are there`).toBeGreaterThan(0);
  for (const [i, r] of g.rows.entries()) {
    const at = `${name} row ${i + 1}`;
    if (g.list) {
      expect.soft(r.row.left, `${at}: starts inside the list`).toBeGreaterThanOrEqual(g.list.left - 0.5);
      expect.soft(r.row.right, `${at}: ends inside the list`).toBeLessThanOrEqual(g.list.right + 0.5);
    }
    if (g.within)
      expect.soft(r.row.right, `${at}: ends inside its box`).toBeLessThanOrEqual(g.within.right + 0.5);
    if (r.name && r.inner) {
      expect
        .soft(r.name.right, `${at}: the name stays inside the row`)
        .toBeLessThanOrEqual(r.inner.right + 0.5);
    }
    if (r.x) {
      expect.soft(r.x.right, `${at}: Remove ends inside the row`).toBeLessThanOrEqual(r.row.right + 0.5);
      expect.soft(r.x.width, `${at}: Remove is at least 24px`).toBeGreaterThanOrEqual(24);
    }
    if (!compact) continue;
    if (r.isMsg) {
      if (g.list)
        expect
          .soft(Math.abs(r.row.width - g.list.width), `${at}: a row with a message is the list's width`)
          .toBeLessThan(1);
      if (r.msg && r.inner)
        expect
          .soft(r.msg.top, `${at}: the message is under the row`)
          .toBeGreaterThanOrEqual(r.inner.bottom - 0.5);
    } else {
      expect.soft(r.row.width, `${at}: 260px at most`).toBeLessThanOrEqual(260.5);
    }
    if (r.x) {
      expect.soft(r.x.width, `${at}: Remove is 32px`).toBeCloseTo(32, 0);
      expect.soft(r.x.height, `${at}: Remove is 32px`).toBeCloseTo(32, 0);
    }
    if (r.name && r.acts) {
      expect
        .soft(r.name.right, `${at}: the name gives way before Remove`)
        .toBeLessThanOrEqual(r.acts.left + 0.5);
      expect.soft(r.acts.top, `${at}: Remove is on the row's line`).toBeLessThan(r.name.bottom);
    }
  }
}

test("QA (lane D, never merged): train 24 on Home at 1440, 1024, 640, 360 and 320: BLD-D031's shared picker and the box's rows (BLD-D030, live off)", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "desktop", "the sizes are set here");
  test.setTimeout(300_000);
  mkdirSync(QA_SHOTS, { recursive: true });
  const log: Record<string, unknown> = {};
  await signInFresh(page, "Q");
  await page.waitForURL((url) => url.pathname === "/home");
  for (const [w, h] of QA_SIZES) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto("/home");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await settleMotion(page);
    const plus = page
      .locator(".cbox.prompt")
      .getByRole("button", { name: "Add files, a folder or a link", exact: true });
    await plus.click();
    await expect(plus).toHaveAttribute("aria-expanded", "true");
    const picker = page.locator(".fpick.cpick");
    await expect(picker.getByRole("button", { name: "Choose a folder", exact: true })).toBeVisible();
    await settleMotion(page);
    const pn = `home-picker-${w}x${h}`;
    const p = await qaPicker(page, ".cbox.prompt");
    log[pn] = p;
    await page.screenshot({ path: join(QA_SHOTS, `${pn}.png`) });
    qaPickChecks(pn, p);
    expect.soft(p.helpText, `${pn}: the link line is Home's`).toContain("marked internal");
    await expectNoSeriousAxeIssues(page);

    const chooser = page.waitForEvent("filechooser");
    await picker.getByRole("button", { name: "browse", exact: true }).click();
    await (
      await chooser
    ).setFiles({
      name: "branch-call-log-week-47-rejection-sms-codes-and-nominee-screens.md",
      mimeType: "text/markdown",
      buffer: Buffer.from("Synthetic: calls about R07, 40 a day."),
    });
    const list = page.getByRole("list", { name: "Your files and links" });
    await expect(list.getByRole("listitem")).toHaveCount(1, { timeout: 20_000 });
    await settleMotion(page);
    const rn = `home-rows-${w}x${h}`;
    const r = await qaRows(page, '.cbox.prompt ul.flist[aria-label="Your files and links"]', ".cbox.prompt");
    log[rn] = r;
    await page.screenshot({ path: join(QA_SHOTS, `${rn}.png`) });
    qaRowChecks(rn, r, false);
    expect.soft(r.live, `${rn}: the box's own status line speaks, not the list (live off)`).toBeNull();
    await expectNoSeriousAxeIssues(page);
  }
  writeFileSync(join(QA_SHOTS, "home.json"), JSON.stringify(log, null, 2));
});
