/**
 * S-WALL, the Wall (L-WALL; copy: reference/copy/Wall.md, PhoneWall.md): V-ACC.browse/2–6 and V-ACC.visual/4 on the
 * Wall. The first view is the real one from the worker; the kind chips, the sorts and "Show 5 more" fetch
 * `/api/wall/*` in place, so those steps answer from fixtures here (synthetic titles only) and each state the screen
 * lists can be reached on any database: twelve ideas with the desk, nothing of a kind, a part that cannot load. The
 * walk from the Wall to an idea and back on the 1% Club seed is lane G's J-BROWSE/5.
 */
import { expect, test, type Page, type Route } from "@playwright/test";

import { expectNoSeriousAxeIssues, PERSONAS, signIn } from "./helpers";

type Kind = "problem" | "fix" | "business_idea";
const KIND_LABEL: Record<Kind, string> = { problem: "Problem", fix: "Fix", business_idea: "Business idea" };
const AREAS = ["Investor service", "Operations", "Distributor experience"];

function idea(n: number, kind: Kind) {
  const id = `IDEA-2026-9${String(n).padStart(5, "0")}`;
  const area = AREAS[n % AREAS.length]!;
  return {
    id,
    title: `Synthetic wall idea ${n}: ${KIND_LABEL[kind].toLowerCase()} at the branch counter`,
    summary: "A synthetic summary for the Wall's screen test.",
    kind,
    area,
    crew_count: (n % 5) + 1,
    sharer: null,
    meta: `${KIND_LABEL[kind]}, ${area}`,
    to: `/ideas/${id}?from=wall`,
  };
}

/** Twelve problems with the desk, newest first: "2h ago", then a day apart. Popular is a different order. */
const JUST_IN = Array.from({ length: 12 }, (_, i) => {
  const base = idea(i + 1, "problem");
  return {
    ...base,
    shared_at: new Date(Date.UTC(2026, 10, 17 - i, 6)).toISOString(),
    shared_label: i === 0 ? "2h ago" : i === 1 ? "Yesterday" : `${i} days ago`,
    opened_7d: [142, 64, 211, 98, 176, 12, 40, 7, 233, 5, 60, 1][i]!,
    ones_count: i % 3,
    figure_label: i === 0 ? "Shared 2h ago" : i === 1 ? "Shared yesterday" : `Shared ${i} days ago`,
  };
});

function justIn(items: typeof JUST_IN, sort: string, offset: number, limit: number, kind = "problem") {
  const page = items.slice(offset, offset + limit);
  const next = offset + limit < items.length ? String(offset + limit) : null;
  const total = items.length;
  return {
    items: page.map((it) => ({
      ...it,
      figure_label: sort === "popular" ? `Opened by ${it.opened_7d} this week` : it.figure_label,
    })),
    total,
    counts: { all: total, problem: kind === "problem" ? total : 0, fix: 0, business_idea: 0 },
    sort,
    next,
    sub: `${total} with the review desk`,
    more: Math.min(limit, Math.max(0, total - offset - limit)),
    more_label: null,
  };
}

const KINDLING = [
  { stage: "picked", count: 3, items: [100, 101, 102].map((n) => ({ ...idea(n, "problem"), meta: "" })) },
  { stage: "being_built", count: 1, items: [103].map((n) => ({ ...idea(n, "problem"), meta: "" })) },
  { stage: "shipped", count: 0, items: [] },
].map((s) => ({
  ...s,
  items: s.items.map((it) => ({ ...it, meta: `Problem, ${it.area}, ${it.crew_count} colleagues on it` })),
}));

const EMPTY_KINDLING = ["picked", "being_built", "shipped"].map((stage) => ({ stage, count: 0, items: [] }));

/** Answers the Wall's in-place fetches from fixtures. `mode` picks the state. */
async function mockWall(page: Page, mode: "twelve" | "empty" | "broken") {
  await page.route("**/api/wall/kindling**", (route: Route) => {
    if (mode === "broken")
      return route.fulfill({ status: 503, json: { error: { code: "try_again", message: "" } } });
    return route.fulfill({ json: mode === "empty" ? EMPTY_KINDLING : KINDLING });
  });
  await page.route("**/api/wall/just-in**", (route: Route) => {
    if (mode === "broken")
      return route.fulfill({ status: 503, json: { error: { code: "try_again", message: "" } } });
    const q = new URL(route.request().url()).searchParams;
    const sort = q.get("sort") ?? "newest";
    const items =
      mode === "empty"
        ? []
        : sort === "popular"
          ? [...JUST_IN].sort((a, b) => b.opened_7d - a.opened_7d)
          : JUST_IN;
    return route.fulfill({
      json: justIn(items, sort, Number(q.get("offset") ?? 0), Number(q.get("limit") ?? 5)),
    });
  });
}

const isPhone = (name: string) => name.startsWith("phone");

async function openWall(page: Page) {
  await signIn(page, PERSONAS.contributor);
  await page.goto("/wall");
  await expect(page.getByRole("heading", { level: 1, name: "Wall" })).toBeVisible();
}

async function pickKind(page: Page, label: string) {
  await page.getByRole("radiogroup", { name: "Show" }).getByRole("radio", { name: label }).click();
}

test.describe("S-WALL", () => {
  test.describe.configure({ timeout: 60_000 });
  test("S-WALL.layout, V-ACC.visual/4: the real Wall reads in its sections, axe clean and no sideways scroll", async ({
    page,
  }, info) => {
    await openWall(page);
    for (const name of ["Kindling", "The Ones", "The Ember"]) {
      await expect(page.getByRole("heading", { level: 2, name })).toBeVisible();
    }
    await expect(
      page.getByRole("heading", {
        level: 2,
        name: isPhone(info.project.name)
          ? "What shipped ideas changed"
          : "What shipped ideas have changed so far.",
      }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { level: 3, name: "Just in" })).toBeVisible();
    if (isPhone(info.project.name)) {
      await expect(
        page.getByText(
          "Every idea from across KFintech, the people behind what shipped, and what it changed.",
        ),
      ).toBeVisible();
      await expect(page.getByRole("navigation", { name: "On the Wall" })).toBeHidden();
    } else {
      await expect(
        page.getByText(
          "Every idea from across KFintech, the people behind what shipped, what it changed, and the Ember to round it up.",
        ),
      ).toBeVisible();
      await expect(page.getByRole("navigation", { name: "On the Wall" }).getByRole("link")).toHaveText([
        "01KindlingEvery idea and problem",
        "02RecognitionThe Ones",
        "03ImpactWhat shipped ideas changed",
        "04The EmberThe newsletter",
      ]);
    }
    await expect(page.getByText("Every issue lands in your inbox too.")).toBeVisible();
    await expect(page.getByRole("contentinfo").or(page.locator(".wl-foot"))).toContainText(
      "A KFintech programme",
    );
    await expectNoSeriousAxeIssues(page);
  });

  test("V-ACC.browse/5: the four impact tiles are one height, no number wraps, the unit is in the label", async ({
    page,
  }, info) => {
    await openWall(page);
    const widths = isPhone(info.project.name) ? [360] : [1440, 1100, 390];
    for (const width of widths) {
      await page.setViewportSize({ width, height: 900 });
      const tiles = page.locator(".wl-tile");
      await expect(tiles).toHaveCount(4);
      const boxes = await tiles.evaluateAll((els) =>
        els.map((el) => {
          const big = el.querySelector<HTMLElement>(".wl-tbig")!;
          const line = parseFloat(getComputedStyle(big).fontSize) * 1.3;
          return {
            h: el.getBoundingClientRect().height,
            oneLine: big.getBoundingClientRect().height <= line,
          };
        }),
      );
      expect(new Set(boxes.map((b) => Math.round(b.h))).size, `tile heights at ${width}px`).toBe(1);
      expect(
        boxes.every((b) => b.oneLine),
        `numbers on one line at ${width}px`,
      ).toBe(true);
      await expect(tiles.locator(".wl-tlabel")).toHaveText([
        "Hours saved a month",
        "Saved a year, Finance confirmed",
        "Fixes shipped and measured",
        /reached by a shipped fix$/,
      ]);
    }
  });

  test("V-ACC.browse/6, /3: Problems filters Kindling and Just in together; 5, Show 5 more, 10, Show 2 more, 12, Show fewer", async ({
    page,
  }, info) => {
    test.skip(isPhone(info.project.name), "the phone pages three at a time: next test");
    await openWall(page);
    await mockWall(page, "twelve");
    const asked: string[] = [];
    page.on("request", (r) => {
      if (r.url().includes("/api/wall/")) asked.push(r.url());
    });
    await pickKind(page, "Problems");
    await expect(page).toHaveURL(/\/wall\?kind=problem$/);
    await expect.poll(() => asked.filter((u) => u.includes("kind=problem")).length).toBe(2);

    const stages = page.locator(".wl-stage");
    await expect(stages.nth(0).getByRole("link")).toHaveText(KINDLING[0]!.items.map((i) => i.title));
    await expect(stages.nth(0)).toContainText("Problem, Investor service");
    await expect(stages.nth(2).getByRole("link")).toHaveCount(0);

    const jin = page.locator(".wl-jt");
    await expect(page.getByText("12 with the review desk")).toBeVisible();
    await expect(jin.locator("[data-row]")).toHaveCount(5);
    await page.getByRole("button", { name: "Show 5 more" }).click();
    await expect(jin.locator("[data-row]")).toHaveCount(10);
    // Focus moves to the first row the button added
    await expect(jin.getByRole("link", { name: JUST_IN[5]!.title })).toBeFocused();
    await expect(page).toHaveURL(/more=1/);
    await page.getByRole("button", { name: "Show 2 more" }).click();
    await expect(jin.locator("[data-row]")).toHaveCount(12);
    await page.getByRole("button", { name: "Show fewer" }).click();
    await expect(jin.locator("[data-row]")).toHaveCount(5);
    await expect(page.getByRole("button", { name: "Show 5 more" })).toBeVisible();
  });

  test("V-ACC.browse/4, /2: each sort orders by its column and emphasises it; the choice is in the URL", async ({
    page,
  }, info) => {
    test.skip(isPhone(info.project.name), "the phone's cycler: next test");
    await openWall(page);
    await mockWall(page, "twelve");
    await pickKind(page, "Problems");
    const jin = page.locator(".wl-jt");
    await expect(jin.locator("[data-row]")).toHaveCount(5);
    await expect(page.getByRole("button", { name: "Newest", exact: true })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(jin.locator(".wl-jhd .on")).toHaveText("Shared");

    await page.getByRole("button", { name: "Popular", exact: true }).click();
    await expect(page.getByRole("button", { name: "Popular", exact: true })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page).toHaveURL(/\/wall\?kind=problem&sort=popular$/);
    const popular = [...JUST_IN].sort((a, b) => b.opened_7d - a.opened_7d).slice(0, 5);
    await expect(jin.locator("[data-row] h4")).toHaveText(popular.map((i) => i.title));
    await expect(jin.locator(".wl-jhd .on")).toHaveText("Opened this week");
    // Each row keeps all four figures across sorts; only the sorted column is ink
    await expect(jin.locator("[data-row]").first().locator(".wl-jv")).toHaveText([
      "Opened this week: 233",
      /^Shared: /,
      /^Crew: \d$/,
      /^Ones on the crew: \d$/,
    ]);
    await expect(jin.locator("[data-row]").first().locator(".wl-jv.on")).toHaveText("Opened this week: 233");

    // An idea's link carries the way back to this exact view (J-BROWSE/5)
    const href = await jin.getByRole("link", { name: popular[0]!.title }).getAttribute("href");
    const back = new URL(href!, "http://x").searchParams.get("back");
    expect(back).toBe("/wall?kind=problem&sort=popular");

    // A reload keeps the sort and the chip (the state is in the URL). The first view after it is the real one from
    // the worker: with problems at the desk the sort shows Popular pressed; with none (CI's stack), Just in says so
    // and shows no sort, and the address still carries it.
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/wall\?kind=problem&sort=popular$/);
    await expect(page.getByRole("radio", { name: "Problems" })).toHaveAttribute("aria-checked", "true");
    const sortAfter = page.getByRole("button", { name: "Popular", exact: true });
    await expect(
      sortAfter.or(page.getByText("Nothing of this kind with the review desk right now.")),
    ).toBeVisible();
    if (await sortAfter.count()) await expect(sortAfter).toHaveAttribute("aria-pressed", "true");
  });

  test("S-WALL.phone: Just in shows three, Show 3 more, a sort cycler, and each row's line carries its sort's figure", async ({
    page,
  }, info) => {
    test.skip(!isPhone(info.project.name), "the phone layout");
    await openWall(page);
    await mockWall(page, "twelve");
    await pickKind(page, "Problems");
    const list = page.locator(".wl-jp");
    await expect(list.locator("[data-row]")).toHaveCount(3);
    await expect(list.getByRole("link").first()).toHaveAccessibleName(
      `${JUST_IN[0]!.title} Problem, ${JUST_IN[0]!.area}. Shared 2h ago`,
    );
    await page.getByRole("button", { name: "Show 3 more" }).click();
    await expect(list.locator("[data-row]")).toHaveCount(6);
    await page.getByRole("button", { name: "Sorted by newest" }).click();
    await expect(page.getByRole("button", { name: "Sorted by popular" })).toBeVisible();
    await expect(page).toHaveURL(/sort=popular/);
    await expect(list.getByRole("link").first()).toContainText("Opened by 233 this week");
    await expectNoSeriousAxeIssues(page);
  });

  test("S-WALL.rules/1, S-WALL.phone: nothing of a kind says so, and the phone offers Show everything", async ({
    page,
  }, info) => {
    await openWall(page);
    await mockWall(page, "empty");
    await pickKind(page, "Business ideas");
    if (isPhone(info.project.name)) {
      await expect(page.getByText("Nothing here for this filter yet")).toBeVisible();
      await expect(page.getByRole("button", { name: "Show everything" })).toBeVisible();
    }
    await expect(page.getByText("Nothing of this kind with the review desk right now.")).toBeVisible();
    await expectNoSeriousAxeIssues(page);
    await page.unrouteAll({ behavior: "ignoreErrors" });
    if (isPhone(info.project.name)) {
      await page.getByRole("button", { name: "Show everything" }).click();
      await expect(page.getByRole("radio", { name: "All" })).toHaveAttribute("aria-checked", "true");
    }
  });

  test("S-WALL error state: a part that cannot load says so in its place and the rest of the Wall stays", async ({
    page,
  }) => {
    await openWall(page);
    await mockWall(page, "broken");
    await pickKind(page, "Fixes");
    await expect(
      page
        .getByRole("alert")
        .filter({ hasText: "We can't load the wall just now. Please try again in a minute." }),
    ).not.toHaveCount(0);
    await expect(page.getByRole("heading", { level: 2, name: "The Ones" })).toBeVisible();
  });

  test("V-ACC.visual/4 keyboard: the section index, then one stop for the kind chips, arrows choose, then the ideas", async ({
    page,
  }, info) => {
    test.skip(isPhone(info.project.name), "the section index is the desktop board's");
    await openWall(page);
    await mockWall(page, "twelve");
    const index = page.getByRole("navigation", { name: "On the Wall" }).getByRole("link");
    await index.first().focus();
    for (let i = 1; i < 4; i++) {
      await page.keyboard.press("Tab");
      await expect(index.nth(i)).toBeFocused();
    }
    await page.keyboard.press("Tab");
    await expect(page.getByRole("radio", { name: "All" })).toBeFocused();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("radio", { name: "Problems" })).toBeFocused();
    await expect(page.getByRole("radio", { name: "Problems" })).toHaveAttribute("aria-checked", "true");
    await expect(page.locator(".wl-stage").first().getByRole("link").first()).toHaveText(
      KINDLING[0]!.items[0]!.title,
    );
    await page.keyboard.press("Tab");
    await expect(page.locator(".wl-stage").first().getByRole("link").first()).toBeFocused();
  });
});
