/**
 * QA ONLY, lane D's branch d/qa-train36-1, never merged: phone QA on main after train 36 (7f4bca4f: D034-D037,
 * B280, B281, F107/F110). The contributor's phone pages at 320 and 360: no sideways scroll; the phone bar's title and
 * Back label are not cut (C-PHONE-TABS.nav, BLD-D034); a fixed dock is one column (C-PHONE-TABS.dock, BLD-D035); a
 * shown picker under 276px of content stacks Add link under the field (C-FILE.picker, BLD-D036); a multi-line Field
 * under 300px puts its tools under the words, inside the frame (C-FIELD.tools, BLD-D037); axe. Screenshots and
 * measures go to test-results/qa-shots. Synthetic data only.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, settleMotion, shareQuickly, signIn } from "./helpers";

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
] as const) {
  test(`QA (lane D, never merged): train 36 on main, the contributor's phone pages at ${w} × ${h}`, async ({
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
      const at = `t36-${w}${path.replace(/[^a-z0-9]+/gi, "_")}`.replace(ideaId, "idea");
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
    writeFileSync(join(QA_SHOTS, `t36-${w}.json`), JSON.stringify(log, null, 2));
  });
}
