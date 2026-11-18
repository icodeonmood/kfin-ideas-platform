/**
 * S-WALL, the Wall (L-WALL; copy: reference/copy/Wall.md, PhoneWall.md): V-ACC.browse/2–6 and V-ACC.visual/4 on the
 * Wall. The first view is the real one from the worker; the kind chips, the sorts and "Show 5 more" fetch
 * `/api/wall/*` in place, so those steps answer from fixtures here (synthetic titles only) and each state the screen
 * lists can be reached on any database: twelve ideas with the desk, nothing of a kind, a part that cannot load. The
 * walk from the Wall to an idea and back on the 1% Club seed is lane G's J-BROWSE/5. Who sees what on the Wall
 * (P-PRODUCT.privacy, DEC-104) is checked on the 1% Club seed (e2e/club.ts), and skips without it.
 */
import { expect, test, type Page, type Route } from "@playwright/test";

import {
  CLUB,
  clubLoaded,
  esc,
  NO_SEED,
  ONES,
  OWN_WORDS,
  seededIdea,
  showNameOnWall,
  type IdeaKey,
} from "./club";
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
    // The figures stand at their value (no count-up), and each width is measured once its layout has settled
    await page.emulateMedia({ reducedMotion: "reduce" });
    await openWall(page);
    const widths = isPhone(info.project.name) ? [360] : [1440, 1100, 390];
    for (const width of widths) {
      await page.setViewportSize({ width, height: 900 });
      const tiles = page.locator(".wl-tile");
      await expect(tiles).toHaveCount(4);
      const measure = () =>
        tiles.evaluateAll((els) =>
          els.map((el) => {
            const big = el.querySelector<HTMLElement>(".wl-tbig")!;
            const line = parseFloat(getComputedStyle(big).fontSize) * 1.3;
            return {
              h: el.getBoundingClientRect().height,
              oneLine: big.getBoundingClientRect().height <= line,
            };
          }),
        );
      await expect
        .poll(async () => new Set((await measure()).map((b) => Math.round(b.h))).size, {
          message: `tile heights at ${width}px`,
        })
        .toBe(1);
      await expect
        .poll(async () => (await measure()).every((b) => b.oneLine), {
          message: `numbers on one line at ${width}px`,
        })
        .toBe(true);
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
    // The row's own line, found by its id: "Problem, {area}, {n} colleagues on it"
    const first = KINDLING[0]!.items[0]!;
    await expect(stages.nth(0).locator(`[data-row="kin-${first.id}"]`)).toContainText(
      `Problem, ${first.area}`,
    );
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
        .filter({ hasText: "We can't load the Wall just now. Please try again in a minute." }),
    ).not.toHaveCount(0);
    await expect(page.getByRole("heading", { level: 2, name: "The Ones" })).toBeVisible();
  });

  test("V-ACC.browse/2, S-WALL.rules/2: a re-sort glides the rows on screen up or down, never in from the corner; row ids are the section's own", async ({
    page,
  }, info) => {
    test.skip(isPhone(info.project.name), "the desktop table; the phone list uses the same rows() helper");
    await openWall(page);
    await mockWall(page, "twelve");
    await pickKind(page, "Problems");
    await expect(page.locator(".wl-jt [data-row]")).toHaveCount(5);
    // Each visible row's id is unique on the page and names its section
    const ids = await page
      .locator("[data-row]")
      .evaluateAll((els) =>
        els.filter((el) => el.getClientRects().length > 0).map((el) => el.getAttribute("data-row") ?? ""),
      );
    expect(new Set(ids).size, ids.join(" | ")).toBe(ids.length);
    expect(
      ids.every((id) => /^(kin|jin|imp)-/.test(id)),
      ids.join(" | "),
    ).toBe(true);
    // Press Popular and read where each row's glide starts: rows in one list move up or down only
    const starts = await page.evaluate(async () => {
      const btn = Array.from(document.querySelectorAll<HTMLButtonElement>("button")).find(
        (b) => b.textContent?.trim() === "Popular" && b.getClientRects().length > 0,
      );
      btn?.click();
      const until = performance.now() + 8_000;
      while (performance.now() < until) {
        const moves = Array.from(document.querySelectorAll<HTMLElement>(".wl-jt [data-flip]"))
          .flatMap((r) => r.getAnimations())
          .map((a) => String((a.effect as KeyframeEffect | null)?.getKeyframes()[0]?.transform ?? ""))
          .filter((t) => t.startsWith("translate"));
        if (moves.length) return moves;
        await new Promise((r) => requestAnimationFrame(r));
      }
      return [];
    });
    expect(starts.length, "rows glide to their new order").toBeGreaterThan(0);
    for (const t of starts) {
      const dx = Number(/^translate\((-?[\d.]+)px/.exec(t)?.[1] ?? "NaN");
      expect(Math.abs(dx), t).toBeLessThan(1);
    }
  });

  test("S-WALL error state, I2: a sort that cannot load puts the choice back, and the same choice tries again", async ({
    page,
  }, info) => {
    test.skip(isPhone(info.project.name), "the desktop sort buttons");
    await openWall(page);
    await mockWall(page, "twelve");
    await pickKind(page, "Problems");
    await expect(page.locator(".wl-jt [data-row]")).toHaveCount(5);
    let fail = true;
    await page.route("**/api/wall/just-in**", async (route: Route) => {
      if (fail) return route.fulfill({ status: 503, json: { error: { code: "try_again", message: "" } } });
      return route.fallback();
    });
    const popular = page.getByRole("button", { name: "Popular", exact: true });
    await popular.click();
    await expect(
      page.getByRole("alert").filter({ hasText: "We can't load the Wall just now." }).first(),
    ).toBeVisible();
    // The choice and the address are back to the view on screen
    await expect(popular).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByRole("button", { name: "Newest", exact: true })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    await expect(page).toHaveURL(/\/wall\?kind=problem$/);
    // The same choice again loads it
    fail = false;
    await popular.click();
    await expect(popular).toHaveAttribute("aria-pressed", "true");
    await expect(page).toHaveURL(/\/wall\?kind=problem&sort=popular$/);
    await expect(page.getByRole("alert").filter({ hasText: "We can't load the Wall just now." })).toHaveCount(
      0,
    );
    const top = [...JUST_IN].sort((a, b) => b.opened_7d - a.opened_7d)[0]!;
    await expect(page.locator(".wl-jt [data-row] h4").first()).toHaveText(top.title);
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

/** Just in's sort key for each sort (L-WALL.justin/3). */
const SORT_KEY: Record<
  string,
  (it: { opened_7d: number; crew_count: number; ones_count: number }) => number
> = {
  popular: (it) => it.opened_7d,
  crew: (it) => it.crew_count,
  ones: (it) => it.ones_count,
};

test.describe("S-WALL on the 1% Club seed", () => {
  test.describe.configure({ timeout: 90_000 });
  let seed = false;
  test.beforeAll(async () => {
    seed = await clubLoaded();
  });

  test("V-ACC.browse/4: each sort orders Just in by its figure and ties go to the newest (the real API)", async ({
    page,
  }) => {
    await openWall(page);
    for (const sort of ["popular", "newest", "crew", "ones"]) {
      const res = await page.request.get(`/api/wall/just-in?sort=${sort}&limit=50`);
      expect(res.ok(), sort).toBe(true);
      const items = ((await res.json()) as { items: (typeof JUST_IN)[number][] }).items;
      for (let i = 1; i < items.length; i++) {
        const a = items[i - 1]!;
        const b = items[i]!;
        const key = SORT_KEY[sort];
        const newer = Date.parse(a.shared_at) >= Date.parse(b.shared_at);
        if (!key) {
          expect(newer, `${sort}: ${a.id} before ${b.id}`).toBe(true);
        } else {
          expect(key(a), `${sort}: ${a.id} before ${b.id}`).toBeGreaterThanOrEqual(key(b));
          if (key(a) === key(b)) expect(newer, `${sort} tie: ${a.id} before ${b.id}`).toBe(true);
        }
      }
    }
  });

  test("P-PRODUCT.privacy, DEC-104: a colleague's own words never reach the Wall, only the short summary", async ({
    page,
  }) => {
    test.skip(!seed, NO_SEED);
    await signIn(page, CLUB.naveen);
    await page.goto("/wall");
    await expect(page.getByRole("heading", { level: 1, name: "Wall" })).toBeVisible();
    const kindling = (await (await page.request.get("/api/wall/kindling")).json()) as {
      items: { id: string; title: string; summary: string }[];
    }[];
    const justIn = (await (await page.request.get("/api/wall/just-in?limit=50")).json()) as {
      items: { id: string; title: string; summary: string }[];
    };
    const onWall = [...kindling.flatMap((s) => s.items), ...justIn.items];
    const html = await page.content();
    const payload = JSON.stringify({ kindling, justIn });
    let checked = 0;
    let drawn = 0;
    for (const key of Object.keys(OWN_WORDS) as IdeaKey[]) {
      const words = OWN_WORDS[key]!;
      expect(html, `${key}'s own words in the page`).not.toContain(words);
      expect(payload, `${key}'s own words from the Wall's API`).not.toContain(words);
      const idea = await seededIdea(key);
      const item = onWall.find((i) => i.id === idea.ref);
      if (!item) continue;
      // What the Wall carries is the short summary everyone sees, and the title
      expect(item.summary).toBe(idea.summary);
      checked++;
      // The API read above asks for 50; the page draws fewer at first (a phone shows fewer rows before "Show 5
      // more"), so only a row the page has drawn is checked for its link
      const link = page.getByRole("link", { name: new RegExp(`^${esc(idea.title)}`) });
      if ((await link.count()) > 0) {
        await expect(link.first()).toBeVisible();
        drawn++;
      }
    }
    expect(checked, "a seeded idea is on the Wall").toBeGreaterThan(0);
    expect(drawn, "a seeded idea is drawn on the Wall").toBeGreaterThan(0);
  });

  test("DEC-104, L-WALL.ones: a One's name shows on the Wall; a One who hides it is One No. N", async ({
    page,
  }) => {
    test.skip(!seed, NO_SEED);
    const one = ONES.indira;
    await signIn(page, CLUB.naveen);
    await page.goto("/wall?ones=leaderboard");
    const ones = page.getByRole("list", { name: "The Ones" });
    await expect(ones.getByRole("heading", { level: 3, name: one.name })).toBeVisible();
    const restore = await showNameOnWall(one.name, false);
    try {
      await page.reload();
      await expect(ones.getByRole("heading", { level: 3, name: `One No. ${one.number}` })).toBeVisible();
      await expect(ones.getByText(one.name)).toHaveCount(0);
      // The Ones' API sends no person for the card at all (the rest of the Wall follows within its cache, S-H6.rules/2)
      const cards = (await (await page.request.get("/api/wall/ones?order=leaderboard")).json()) as {
        number: number;
        person: { name: string } | null;
      }[];
      expect(cards.find((c) => c.number === one.number)?.person ?? null).toBeNull();
    } finally {
      await restore();
    }
  });
});
