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
 * QA ONLY, lane D's branch d/qa-c244-1, never merged: BLD-C244 on Home and Share, the box's rows as lane D's compact
 * FileList and FileRemove. On a desk (1440, 1024): rows side by side at 260px at most, Remove beside the name, a row
 * with a message across the list with its message under it. On a phone (360, 320): the buttons under the name at the
 * right, as in lane D's train 24 pass. One file, two files, then a failed upload (Try again) and a file over the limit,
 * each with its message on its own line; Remove 32 x 32; axe. The good files really upload to this run's stack; the
 * failed one is refused here and the limit is lowered here, so nothing else changes. Synthetic files only.
 */
const QA_SHOTS = join(__dirname, "..", "test-results", "qa-shots");
const QA_LIST = '.cbox.prompt ul.flist[aria-label="Your files and links"]';

async function qaBoxRows(page: Page) {
  return page.evaluate((sel) => {
    const box = (el: Element | null | undefined) => {
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height };
    };
    const ul = document.querySelector(sel);
    const html = document.documentElement;
    return {
      sideways: html.scrollWidth - html.clientWidth,
      compact: !!ul?.classList.contains("compact"),
      live: ul?.getAttribute("aria-live") ?? null,
      list: box(ul),
      within: box(ul?.closest(".cbox.prompt")),
      rows: [...(ul?.querySelectorAll(":scope > .frow") ?? [])].map((li) => {
        const x = li.querySelector<HTMLElement>(".frow-x");
        return {
          cls: li.className,
          row: box(li)!,
          inner: box(li.querySelector(".frow-in")),
          name: box(li.querySelector(".frow-n")),
          nameText: li.querySelector(".frow-n")?.textContent ?? "",
          acts: box(li.querySelector(".frow-a")),
          x: box(x),
          xName: x?.getAttribute("aria-label") ?? "",
          xTitle: x?.getAttribute("title") ?? "",
          retry: box(li.querySelector(".frow-a button:not(.frow-x)")),
          msg: box(li.querySelector(".fmsg")),
          msgText: li.querySelector(".fmsg")?.textContent ?? "",
          isMsg: li.classList.contains("frow-msg"),
        };
      }),
    };
  }, QA_LIST);
}

test("QA (lane D, never merged): BLD-C244, the box's rows on Home and Share at 1440, 1024, 360 and 320: one, two, failed and too big", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "desktop", "the sizes are set here");
  test.setTimeout(900_000);
  mkdirSync(QA_SHOTS, { recursive: true });
  const log: Record<string, unknown> = {};
  await signInFresh(page, "R");
  await page.waitForURL((url) => url.pathname === "/home");
  // The limit is 1 MB here, so a 1.3 MB synthetic file is over it; everything else in the answer is the stack's own
  await page.route("**/api/config/uploads", async (route) => {
    const res = await route.fetch();
    const json = (await res.json()) as Record<string, unknown>;
    return route.fulfill({ response: res, json: { ...json, limit_mb: 1 } });
  });
  // The file named upload-fails-… is refused as a server error, so its row offers Try again
  await page.route("**/api/files", (route) => {
    const body = route.request().postDataBuffer();
    if (route.request().method() === "POST" && body && body.includes("upload-fails-"))
      return route.fulfill({
        status: 500,
        json: { error: { code: "internal", message: "Something went wrong." } },
      });
    return route.fallback();
  });

  const plus = page
    .locator(".cbox.prompt")
    .getByRole("button", { name: "Add files, a folder or a link", exact: true });
  const picker = page.locator(".fpick.cpick");
  const rows = page.locator(`${QA_LIST} > .frow`);
  const add = async (name: string, buffer: Buffer) => {
    const before = await rows.count();
    if (!(await picker.isVisible())) await plus.click();
    await expect(picker).toBeVisible();
    const chooser = page.waitForEvent("filechooser");
    await picker.getByRole("button", { name: "browse", exact: true }).click();
    await (await chooser).setFiles({ name, mimeType: "text/markdown", buffer });
    await expect(rows).toHaveCount(before + 1, { timeout: 30_000 });
  };
  const snap = async (name: string, phone: boolean) => {
    await settleMotion(page);
    await page.locator(QA_LIST).evaluate((el) => el.scrollIntoView({ block: "center" }));
    await settleMotion(page);
    const g = await qaBoxRows(page);
    log[name] = g;
    await page.screenshot({ path: join(QA_SHOTS, `${name}.png`) });
    expect.soft(g.sideways, `${name}: no sideways scroll`).toBeLessThanOrEqual(0);
    expect.soft(g.compact, `${name}: the list is lane D's compact list`).toBe(true);
    expect.soft(g.live, `${name}: the list is no live region (the status line speaks)`).toBeNull();
    for (const [i, r] of g.rows.entries()) {
      const at = `${name} row ${i + 1} (${r.nameText})`;
      if (g.list) {
        expect.soft(r.row.left, `${at}: starts inside the list`).toBeGreaterThanOrEqual(g.list.left - 0.5);
        expect.soft(r.row.right, `${at}: ends inside the list`).toBeLessThanOrEqual(g.list.right + 0.5);
      }
      if (g.within)
        expect.soft(r.row.right, `${at}: ends inside the box`).toBeLessThanOrEqual(g.within.right + 0.5);
      expect.soft(r.x, `${at}: has Remove`).not.toBeNull();
      if (r.x) {
        expect.soft(r.x.width, `${at}: Remove is 32px wide`).toBeCloseTo(32, 0);
        expect.soft(r.x.height, `${at}: Remove is 32px high`).toBeCloseTo(32, 0);
        expect.soft(r.x.right, `${at}: Remove ends inside the row`).toBeLessThanOrEqual(r.row.right + 0.5);
        expect.soft(r.xName, `${at}: Remove is named for its file`).toBe(`Remove ${r.nameText}`);
        expect.soft(r.xTitle, `${at}: Remove's tooltip`).toBe(`Remove ${r.nameText}`);
      }
      if (r.retry) {
        expect.soft(r.retry.height, `${at}: Try again is at least 24px high`).toBeGreaterThanOrEqual(24);
        expect
          .soft(r.retry.right, `${at}: Try again ends inside the row`)
          .toBeLessThanOrEqual(r.row.right + 0.5);
      }
      if (r.name && r.inner)
        expect
          .soft(r.name.right, `${at}: the name stays inside the row`)
          .toBeLessThanOrEqual(r.inner.right + 0.5);
      if (r.isMsg && r.msg && r.inner)
        expect
          .soft(r.msg.top, `${at}: the message is under the row`)
          .toBeGreaterThanOrEqual(r.inner.bottom - 0.5);
      if (phone) {
        if (r.acts && r.name)
          expect
            .soft(r.acts.top, `${at}: the buttons are under the name`)
            .toBeGreaterThanOrEqual(r.name.bottom - 0.5);
        if (r.x && r.inner)
          expect.soft(r.inner.right - r.x.right, `${at}: Remove is at the right`).toBeLessThanOrEqual(16);
      } else {
        if (r.isMsg) {
          if (g.list)
            expect
              .soft(Math.abs(r.row.width - g.list.width), `${at}: a row with a message is the list's width`)
              .toBeLessThan(1);
        } else {
          expect.soft(r.row.width, `${at}: 260px at most`).toBeLessThanOrEqual(260.5);
        }
        if (r.acts && r.name)
          expect
            .soft(r.acts.left, `${at}: the buttons are beside the name`)
            .toBeGreaterThanOrEqual(r.name.right - 0.5);
      }
    }
    return g;
  };

  for (const path of ["/home", "/share"] as const) {
    for (const [w, h] of [
      [1440, 900],
      [1024, 768],
      [360, 740],
      [320, 640],
    ] as const) {
      const phone = w <= 640;
      const at = `c244${path.replace("/", "-")}-${w}x${h}`;
      await page.setViewportSize({ width: w, height: h });
      await page.goto(path);
      await expect(page.locator(".cbox.prompt textarea")).toBeVisible();
      await settleMotion(page);

      await add("branch-notes.md", Buffer.from("Synthetic: 15 calls a week."));
      await snap(`${at}-1-one`, phone);
      await add(
        "branch-call-log-week-47-rejection-sms-codes-and-nominee-screens.md",
        Buffer.from("Synthetic: calls about R07, 40 a day."),
      );
      await snap(`${at}-2-two`, phone);
      await expectNoSeriousAxeIssues(page);

      await add("upload-fails-call-log.md", Buffer.from("Synthetic: this upload is refused by the test."));
      await expect(page.getByRole("button", { name: "Try again" }).first()).toBeVisible({ timeout: 30_000 });
      await add("rejection-sms-screens-scan.md", Buffer.alloc(1_300_000, "a"));
      const failed = await snap(`${at}-3-failed-and-too-big`, phone);
      const withMsg = failed.rows.filter((r) => r.isMsg);
      expect
        .soft(withMsg.length, `${at}: the failed and too-big rows carry their messages`)
        .toBeGreaterThanOrEqual(2);
      expect
        .soft(
          failed.rows.some((r) => r.retry),
          `${at}: the failed row offers Try again`,
        )
        .toBe(true);
      await expectNoSeriousAxeIssues(page);
    }
  }
  writeFileSync(join(QA_SHOTS, "c244.json"), JSON.stringify(log, null, 2));
});
