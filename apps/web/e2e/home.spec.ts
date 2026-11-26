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

test("BLD-D036, C-FILE.picker (C-FILE.uploader), S-03: at 320px Home's picker gives the link field its own row and puts Add link under it, full width and 44px tall", async ({
  page,
}, info) => {
  test.skip(info.project.name !== "phone-360", "the narrow picker is a phone's");
  await signInFresh(page, "L");
  await page.setViewportSize({ width: 320, height: 640 });
  await page.goto("/home");
  await page.getByRole("button", { name: "Add files, a folder or a link" }).first().click();
  await expect(page.getByRole("textbox", { name: "Or paste a link to a page, file or idea" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Add link" })).toBeVisible();
  await settleMotion(page);
  const m = await page.locator(".cpick .fpick-link").evaluate((row) => {
    const box = (e: Element | null) => {
      const r = e!.getBoundingClientRect();
      return { left: r.left, top: r.top, width: r.width, height: r.height, bottom: r.bottom };
    };
    return {
      row: box(row),
      field: box(row.querySelector("input")),
      add: box(row.querySelector(".btn")),
      icon: box(row.querySelector(".fpick-li")),
    };
  });
  // Home's box is 225px at 320 on CI and the picker 201px inside its 12px margins: the field had 79px beside Add link
  expect(m.field.width, "the field is wide enough to read a link").toBeGreaterThanOrEqual(170);
  expect(m.field.width, "the field takes the row").toBeGreaterThanOrEqual(m.row.width - 1);
  expect(m.add.top, "Add link is under the field").toBeGreaterThanOrEqual(m.field.bottom);
  expect(Math.abs(m.add.width - m.field.width), "Add link is full width").toBeLessThanOrEqual(1);
  expect(m.add.height, "Add link keeps its 44px target").toBeGreaterThanOrEqual(44);
  // The link icon sits on the field, centred on its height, not on the two rows
  expect(m.icon.left).toBeGreaterThan(m.field.left);
  expect(
    Math.abs(m.icon.top + m.icon.height / 2 - (m.field.top + m.field.height / 2)),
    "the icon is centred on the field",
  ).toBeLessThanOrEqual(1);
  await expectNoSeriousAxeIssues(page);
});

/**
 * QA ONLY, lane D's branch d/qa-narrow-1, never merged: BLD-D036 (the shared picker's link row) on Home and Share, and
 * BLD-D035 (the phone dock) on Share. The desktop project takes 1440 and 640, the phone project 360 and 320. The
 * picker under 300px stacks the field over a full-width Add link (44px), the icon centred on the field; over 300px
 * the two share a row. A fixed dock's buttons share one left edge. Screenshots and measures go to
 * test-results/qa-shots. Synthetic only.
 */
const QA_SHOTS = join(__dirname, "..", "test-results", "qa-shots");

test("QA (lane D, never merged): BLD-D036 picker link row on Home and Share, BLD-D035 Share's dock, at 1440, 640, 360 and 320", async ({
  page,
}, info) => {
  test.setTimeout(300_000);
  mkdirSync(QA_SHOTS, { recursive: true });
  const log: Record<string, unknown> = {};
  await signInFresh(page, "N");
  await page.waitForURL((url) => url.pathname === "/home");
  const sizes =
    info.project.name === "phone-360"
      ? ([
          [360, 740],
          [320, 640],
        ] as const)
      : ([
          [1440, 900],
          [640, 800],
        ] as const);
  for (const path of ["/home", "/share"] as const) {
    for (const [w, h] of sizes) {
      const at = `d036${path.replace("/", "-")}-${w}x${h}`;
      await page.setViewportSize({ width: w, height: h });
      await page.goto(path);
      await expect(page.locator(".cbox.prompt textarea")).toBeVisible();
      await page
        .locator(".cbox.prompt")
        .getByRole("button", { name: "Add files, a folder or a link", exact: true })
        .click();
      await expect(page.getByRole("button", { name: "Add link" })).toBeVisible();
      await settleMotion(page);
      await page.locator(".cpick .fpick-link").evaluate((el) => el.scrollIntoView({ block: "center" }));
      await settleMotion(page);
      const g = await page.evaluate(() => {
        const box = (e: Element | null | undefined) => {
          if (!e) return null;
          const r = e.getBoundingClientRect();
          return {
            left: r.left,
            right: r.right,
            top: r.top,
            bottom: r.bottom,
            width: r.width,
            height: r.height,
          };
        };
        const row = document.querySelector(".cpick .fpick-link");
        const dock = [...document.querySelectorAll<HTMLElement>(".dock")].find(
          (d) => getComputedStyle(d).position === "fixed",
        );
        return {
          sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          picker: box(document.querySelector(".cpick")),
          row: box(row),
          field: box(row?.querySelector("input")),
          add: box(row?.querySelector(".btn")),
          icon: box(row?.querySelector(".fpick-li")),
          dock: dock
            ? {
                box: box(dock)!,
                lefts: [...dock.querySelectorAll(":scope > .btn, :scope > button, :scope > a")].map(
                  (b) => box(b)!.left,
                ),
              }
            : null,
        };
      });
      log[at] = g;
      await page.screenshot({ path: join(QA_SHOTS, `${at}.png`) });
      expect.soft(g.sideways, `${at}: no sideways scroll`).toBeLessThanOrEqual(0);
      if (g.picker && g.row && g.field && g.add && g.icon) {
        const stacked = g.picker.width < 300;
        if (stacked) {
          expect
            .soft(g.add.top, `${at}: Add link under the field`)
            .toBeGreaterThanOrEqual(g.field.bottom - 0.5);
          expect
            .soft(Math.abs(g.add.width - g.field.width), `${at}: Add link full width`)
            .toBeLessThanOrEqual(1);
          expect
            .soft(g.field.width, `${at}: the field takes the row`)
            .toBeGreaterThanOrEqual(g.row.width - 1);
        } else {
          expect
            .soft(g.add.left, `${at}: Add link beside the field`)
            .toBeGreaterThanOrEqual(g.field.right - 0.5);
        }
        expect.soft(g.add.height, `${at}: Add link 44px`).toBeGreaterThanOrEqual(44);
        expect
          .soft(
            Math.abs(g.icon.top + g.icon.height / 2 - (g.field.top + g.field.height / 2)),
            `${at}: icon centred on the field`,
          )
          .toBeLessThanOrEqual(1);
      }
      if (g.dock && g.dock.lefts.length > 1) {
        const first = g.dock.lefts[0]!;
        for (const l of g.dock.lefts)
          expect.soft(Math.abs(l - first), `${at}: the dock is one column`).toBeLessThan(1);
      }
      await expectNoSeriousAxeIssues(page);
    }
  }
  writeFileSync(join(QA_SHOTS, `d036-${info.project.name}.json`), JSON.stringify(log, null, 2));
});
