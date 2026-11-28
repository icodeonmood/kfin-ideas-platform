/**
 * QA ONLY, lane D's branch d/qa-train40-1, never merged: phone QA on main after trains 38 to 40 (c90c3bb9: A255,
 * cbiz, C249 with C203's business questions on Tell it's question card, G011, F112). Two parts. (1) Tell it's S1
 * question card (S-04B; the flag forced for a new synthetic person, rows removed after): questions 1 and 2 at each
 * width, no sideways scroll, the card and its buttons inside the screen, no line cut, axe. (2) The train 37c checks
 * again. The contributor's phone pages at 320, 360, 390 and 640: no sideways scroll; the phone bar's title and Back
 * label are not cut, the two keep the bar's 8px, and the title is centred whenever both sides fit (C-PHONE-TABS.nav,
 * BLD-D034, BLD-D041 at every phone width); a fixed dock is one column (C-PHONE-TABS.dock, BLD-D035); a
 * shown picker under 276px of content stacks Add link under the field (C-FILE.picker, BLD-D036); a multi-line Field
 * under 300px puts its tools under the words, inside the frame (C-FIELD.tools, BLD-D037); axe. Screenshots and
 * measures go to test-results/qa-shots. Synthetic data only.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, settleMotion, shareQuickly, signIn } from "./helpers";
import { personWithFlag, removeFlagRows } from "./variants-lib";

const QA_SHOTS = join(__dirname, "..", "test-results", "qa-shots");

async function measure(page: Page) {
  return page.evaluate(() => {
    const r = (e: Element) => {
      const b = e.getBoundingClientRect();
      return { left: b.left, right: b.right, top: b.top, bottom: b.bottom, width: b.width, height: b.height };
    };
    const shown = (e: Element) => {
      const b = e.getBoundingClientRect();
      return b.width > 0 && b.height > 0 && getComputedStyle(e).visibility !== "hidden";
    };
    const title = document.querySelector<HTMLElement>(".pnav .pnav-t");
    const backLabel = document.querySelector<HTMLElement>(".pnav .pback span");
    const bar = document.querySelector<HTMLElement>(".pnav");
    const back = bar?.querySelector<HTMLElement>(".pback");
    const right = bar?.querySelector<HTMLElement>(".pnav-r");
    const dock = document.querySelector<HTMLElement>("main#main > .dock-root > .dock");
    const dockKids = dock
      ? [...dock.children].filter((c) => getComputedStyle(c).position !== "absolute" && shown(c))
      : [];
    return {
      sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      title:
        title && shown(title)
          ? { text: title.textContent, scroll: title.scrollWidth, client: title.clientWidth }
          : null,
      back:
        backLabel && shown(backLabel)
          ? { text: backLabel.textContent, scroll: backLabel.scrollWidth, client: backLabel.clientWidth }
          : null,
      bar:
        bar && title && back && shown(bar) && shown(title)
          ? (() => {
              const cs = getComputedStyle(bar);
              const gap = Number.parseFloat(cs.columnGap) || 0;
              const inner =
                bar.clientWidth -
                Number.parseFloat(cs.paddingLeft) -
                Number.parseFloat(cs.paddingRight) -
                2 * gap;
              const b = bar.getBoundingClientRect();
              const t = title.getBoundingClientRect();
              const titleW = Math.min(title.scrollWidth, 180);
              const sideNeed = Math.max(Math.min(back.scrollWidth, 128), right ? right.scrollWidth : 0);
              return {
                gapBackTitle: t.left - back.getBoundingClientRect().right,
                centreOff: t.left + t.width / 2 - (b.left + b.width / 2),
                bothFit: (inner - titleW) / 2 >= sideNeed,
                inner,
                titleW,
                sideNeed,
              };
            })()
          : null,
      dock:
        dock && shown(dock)
          ? {
              box: r(dock),
              count: dockKids.length,
              lefts: [...new Set(dockKids.map((c) => Math.round(c.getBoundingClientRect().left)))],
            }
          : null,
      fields: [...document.querySelectorAll(".fld-frame.multi")].filter(shown).map((f) => ({
        frame: r(f),
        text: f.querySelector("textarea") ? r(f.querySelector("textarea")!) : null,
        tools: [...f.querySelectorAll(".fld-tools button")].filter(shown).map(r),
      })),
      pickers: [...document.querySelectorAll(".fpick")].filter(shown).map((p) => {
        const cs = getComputedStyle(p);
        const content =
          p.clientWidth - Number.parseFloat(cs.paddingLeft) - Number.parseFloat(cs.paddingRight);
        const row = p.querySelector(".fpick-link");
        return {
          content,
          field: row?.querySelector("input") ? r(row.querySelector("input")!) : null,
          add: row?.querySelector(".btn") ? r(row.querySelector(".btn")!) : null,
        };
      }),
    };
  });
}

for (const [w, h] of [
  [320, 640],
  [360, 740],
  [390, 844],
  [640, 800],
] as const) {
  test(`QA (lane D, never merged): train 40 on main, the contributor's phone pages at ${w} × ${h}`, async ({
    page,
  }, info) => {
    test.skip(info.project.name !== "phone-360", "phone QA");
    test.setTimeout(300_000);
    mkdirSync(QA_SHOTS, { recursive: true });
    await signIn(page, PERSONAS.contributor);
    const ideaId = await shareQuickly(page, `QA lane D: branch SMS gives a code only (${w} ${Date.now()})`);
    await page.setViewportSize({ width: w, height: h });
    const paths = [
      "/",
      "/share?new=1",
      "/my-ideas",
      "/wall",
      "/inbox",
      "/crew",
      `/ideas/${ideaId}`,
      "/kit",
      "/kit/conversation?view=questions",
    ];
    const log: Record<string, unknown> = {};
    for (const path of paths) {
      const at = `t40-${w}${path.replace(ideaId, "idea").replace(/[^a-z0-9]+/gi, "_")}`;
      await page.goto(path);
      await expect(page.locator("main#main")).toBeVisible();
      await settleMotion(page);
      const m = await measure(page);
      log[at] = { path: path.replace(ideaId, "<idea>"), ...m };
      await page.screenshot({ path: join(QA_SHOTS, `${at}.png`), fullPage: true });
      expect.soft(m.sideways, `${at}: no sideways scroll`).toBeLessThanOrEqual(0);
      if (m.title)
        expect.soft(m.title.scroll, `${at}: the bar's title is not cut`).toBeLessThanOrEqual(m.title.client);
      if (m.back)
        expect.soft(m.back.scroll, `${at}: Back's label is not cut`).toBeLessThanOrEqual(m.back.client);
      if (m.bar) {
        expect.soft(m.bar.gapBackTitle, `${at}: Back and the title keep 8px`).toBeGreaterThanOrEqual(7.5);
        if (m.bar.bothFit)
          expect.soft(Math.abs(m.bar.centreOff), `${at}: the title is centred`).toBeLessThanOrEqual(1);
      }
      if (m.dock && m.dock.count > 1)
        expect.soft(m.dock.lefts, `${at}: the dock is one column`).toHaveLength(1);
      for (const [i, f] of m.fields.entries()) {
        expect.soft(f.frame.right, `${at}: field ${i} inside the screen`).toBeLessThanOrEqual(w);
        if (f.text && f.frame.width < 300)
          for (const t of f.tools)
            expect
              .soft(t.top, `${at}: field ${i}'s tools under the words`)
              .toBeGreaterThanOrEqual(f.text.bottom - 0.5);
        for (const t of f.tools) {
          expect
            .soft(t.left, `${at}: field ${i}'s tool inside the frame`)
            .toBeGreaterThanOrEqual(f.frame.left);
          expect
            .soft(t.right, `${at}: field ${i}'s tool inside the frame`)
            .toBeLessThanOrEqual(f.frame.right);
        }
      }
      for (const [i, p] of m.pickers.entries()) {
        if (!p.field || !p.add) continue;
        if (p.content < 276)
          expect
            .soft(p.add.top, `${at}: picker ${i} stacks Add link under the field`)
            .toBeGreaterThanOrEqual(p.field.bottom - 0.5);
        else
          expect
            .soft(p.add.left, `${at}: picker ${i} keeps Add link beside the field`)
            .toBeGreaterThanOrEqual(p.field.right - 0.5);
        expect.soft(p.add.height, `${at}: picker ${i}'s Add link 44px`).toBeGreaterThanOrEqual(44);
      }
      await expectNoSeriousAxeIssues(page);
    }
    writeFileSync(join(QA_SHOTS, `t40-${w}.json`), JSON.stringify(log, null, 2));
  });
}

const WORDS =
  "Synthetic: the redemption SMS only gives a code, so investors call the branch to ask what it means.";

// Question 1 and 2 as drawn, or C203's business-idea pair if the draft's sorting says a new business idea
const CARDS = [
  { n: 1, name: /^(How often does it happen, roughly\?|How many would use it, roughly\?)$/ },
  { n: 2, name: /^(Who feels it most\?|Who is it for\?)$/ },
] as const;

for (const [w, h] of [
  [320, 640],
  [360, 740],
  [390, 844],
  [640, 800],
] as const) {
  test.describe(`QA (lane D, never merged): train 40 on main, Tell it's question card at ${w} × ${h}`, () => {
    let userId: string | null = null;
    test.afterEach(async () => {
      await removeFlagRows(userId);
      userId = null;
    });

    test(`QA (lane D, never merged): S-04B question card, S1 forced, at ${w} × ${h}`, async ({
      page,
    }, info) => {
      test.skip(info.project.name !== "phone-360", "phone QA");
      test.setTimeout(180_000);
      mkdirSync(QA_SHOTS, { recursive: true });
      userId = await personWithFlag(page, "s1", info);
      await page.setViewportSize({ width: w, height: h });
      await page.goto("/share?new=1");
      const box = page.getByRole("textbox", { name: /^(Describe the problem|For example: )/ });
      await box.fill(WORDS);
      await box.press("Enter");
      await page.waitForURL(/\/share\/[0-9a-f-]{36}$/);
      const log: Record<string, unknown> = {};
      for (const { n, name } of CARDS) {
        const card = page.getByRole("group", { name });
        await expect(card).toBeVisible();
        await settleMotion(page);
        const at = `t40-${w}_s1_q${n}`;
        const m = await card.evaluate((c) => {
          const shown = (e: Element) => {
            const b = e.getBoundingClientRect();
            return b.width > 0 && b.height > 0 && getComputedStyle(e).visibility !== "hidden";
          };
          const b = c.getBoundingClientRect();
          const input = c.querySelector("input");
          return {
            question: c.querySelector("h2, h3")?.textContent ?? null,
            sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
            card: { left: b.left, right: b.right, width: b.width, height: b.height },
            input: input
              ? { left: input.getBoundingClientRect().left, right: input.getBoundingClientRect().right }
              : null,
            buttons: [...c.querySelectorAll("button")].filter(shown).map((e) => {
              const r = e.getBoundingClientRect();
              return { text: (e.textContent ?? "").trim(), left: r.left, right: r.right, height: r.height };
            }),
            cut: [...c.querySelectorAll<HTMLElement>("h2, h3, p, button")]
              .filter(shown)
              .filter((e) => e.scrollWidth > e.clientWidth + 0.5)
              .map((e) => (e.textContent ?? "").trim().slice(0, 48)),
          };
        });
        log[at] = m;
        await page.screenshot({ path: join(QA_SHOTS, `${at}.png`), fullPage: true });
        expect.soft(m.sideways, `${at}: no sideways scroll`).toBeLessThanOrEqual(0);
        expect.soft(m.card.left, `${at}: the card inside the screen`).toBeGreaterThanOrEqual(0);
        expect.soft(m.card.right, `${at}: the card inside the screen`).toBeLessThanOrEqual(w);
        if (m.input)
          expect
            .soft(m.input.right, `${at}: the answer box inside the card`)
            .toBeLessThanOrEqual(m.card.right + 0.5);
        for (const bt of m.buttons) {
          expect
            .soft(bt.left, `${at}: "${bt.text}" inside the card`)
            .toBeGreaterThanOrEqual(m.card.left - 0.5);
          expect
            .soft(bt.right, `${at}: "${bt.text}" inside the card`)
            .toBeLessThanOrEqual(m.card.right + 0.5);
        }
        expect.soft(m.cut, `${at}: no line cut`).toEqual([]);
        await expectNoSeriousAxeIssues(page);
        if (n === 1) {
          await card.getByRole("textbox", { name }).fill("About 20 times a week at one branch");
          await card.getByRole("button", { name: "Next question" }).click();
        }
      }
      writeFileSync(join(QA_SHOTS, `t40-${w}_s1.json`), JSON.stringify(log, null, 2));
    });
  });
}
