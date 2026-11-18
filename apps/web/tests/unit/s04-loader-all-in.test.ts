// @vitest-environment jsdom
/**
 * "All 6 parts are in" only when all six are (S-04, S-04B; C-DRAFT-LOADER.maths/7–8, failure/1; L-DRAFT.parts/1, /7;
 * BLD-C157). Lane G's walk (J-SHARE/v1) saw the line while How often and Area read "Waiting for your words". A run that
 * ends with a part the words do not support: no all-in line, no fill to 100%, no pop, the strip folds quietly, the
 * header leaves "Updating", and Move to Review stays off with "Your draft needs a little more first.". A run where
 * every part fills, or fails and asks to be added, plays the drawn sequence. Desktop and phone. Synthetic words only.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DraftPanel, READINESS, readinessOf } from "@/components/compose/draft-panel";
import type { DraftPartKey, DraftStreamEvent } from "@/lib/contracts";
import { allIn, applyEvent, fromDraft, giveUp, partIn, type Live } from "@/lib/compose/live";
import { barValue, LOADER_ALL_IN, loaderLine, readyCount, type LoaderRun } from "@/lib/compose/loader";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
    createElement("a", { href, ...rest }, children as never),
}));

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.useRealTimers();
});

const MEANS = [
  { key: "similar" as const, mean_ms: 2600 },
  { key: "title" as const, mean_ms: 1800 },
  { key: "value" as const, mean_ms: 1500 },
  { key: "who" as const, mean_ms: 1200 },
  { key: "often" as const, mean_ms: 900 },
  { key: "area" as const, mean_ms: 700 },
];

const WORDS =
  "Branch staff retype the same nominee details into two screens for every new folio. It takes ten minutes each time.";

const FILLED: Record<DraftPartKey, unknown> = {
  title: {
    title: "Nominee details typed twice for every new folio",
    summary: "Branch staff enter the same nominee details on two screens for each new folio.",
  },
  often: "Every new folio",
  who: ["KFin teams"],
  value: ["saves_time"],
  area: "Operations",
  similar: [],
};

const part = (
  key: DraftPartKey,
  value: unknown,
  state: "filled" | "failed" = "filled",
): DraftStreamEvent => ({
  event: "part",
  data: { key, state, value, took_ms: 400 },
});

/** One run from its `run` event: each part lands with `values[key]` (null: the words do not support it), then done. */
function runOf(
  values: Partial<Record<DraftPartKey, unknown>>,
  { done = true, ready = false, start = fromDraft(null), id = "run-1", keys = MEANS.map((m) => m.key) } = {},
): Live {
  let live = applyEvent(
    start,
    { event: "run", data: { run_id: id, parts: MEANS.filter((m) => keys.includes(m.key)) } },
    0,
  );
  let t = 100;
  for (const k of keys) live = applyEvent(live, part(k, k in values ? values[k] : FILLED[k]), (t += 100));
  return done ? applyEvent(live, { event: "done", data: { ready } }, (t += 100)) : live;
}

function panel(live: Live, phone = false) {
  const readiness = readinessOf({
    chars: WORDS.length,
    minChars: 30,
    sending: false,
    running: live.running,
    ready: live.ready,
  });
  act(() =>
    root.render(
      createElement(DraftPanel, {
        live,
        readiness,
        moveHref: "/share/d-1/check",
        hidden: null,
        phone,
      }),
    ),
  );
}

const strip = () => host.querySelector(".dload") as HTMLElement;
const bar = () => host.querySelector('[role="progressbar"]') as HTMLElement;
const status = () => host.querySelector('.cvh [role="status"]')?.textContent;
const move = () =>
  [...host.querySelectorAll("button, a")].find(
    (b) => b.textContent?.trim() === "Move to Review",
  ) as HTMLElement;

describe("C-DRAFT-LOADER.maths/7, L-DRAFT.parts/1: a part the words do not support is not in (BLD-C157)", () => {
  it("L-DRAFT.parts/1 a finished run with How often and Area null: no all-in line, no 'Updating', Move to Review off with the drawn line", () => {
    const live = runOf({ often: null, area: null });
    expect(live.running).toBe(false);
    expect(partIn(live.parts, "often")).toBe(false);
    expect(partIn(live.parts, "area")).toBe(false);
    expect(allIn(live)).toBe(false);

    panel(live);
    expect(host.textContent).not.toContain(LOADER_ALL_IN);
    expect(host.textContent!.match(/Waiting for your words/g)).toHaveLength(2);
    // The strip folds quietly: no fill to 100%, no pop (the `all` class), hidden from screen readers.
    expect(strip().classList.contains("fold")).toBe(true);
    expect(strip().classList.contains("all")).toBe(false);
    expect(strip().getAttribute("aria-hidden")).toBe("true");
    expect(Number(bar().getAttribute("aria-valuenow"))).toBeLessThanOrEqual(97);
    // The header leaves "Updating" once nothing is building; the drawn state for a draft with words.
    expect(status()).toBe("Up to date");
    expect(host.textContent).toContain(READINESS.more);
    expect(host.textContent).toContain("Your draft needs a little more first.");
    expect(move().getAttribute("aria-disabled")).toBe("true");
    expect(move().tagName).toBe("BUTTON");
  });

  it("J-SHARE/v1 while the run closes with both blank parts answered: '4 of 6 ready, almost there', never the all-in line", () => {
    const live = runOf({ often: null, area: null }, { done: false });
    expect(live.running).toBe(true);
    expect(loaderLine(live.loader!, 1000)).toBe("4 of 6 ready, almost there");
    panel(live);
    expect(host.textContent).not.toContain(LOADER_ALL_IN);
    expect(strip().classList.contains("fold")).toBe(false);
    expect(status()).toBe("Updating");
    expect(host.textContent).toContain(READINESS.working);
  });

  it("S-04B phone: the tube under the peek folds the same way, with no all-in line", () => {
    panel(runOf({ often: null, area: null }), true);
    expect(host.textContent).not.toContain(LOADER_ALL_IN);
    expect(strip().classList.contains("ph")).toBe(true);
    expect(strip().classList.contains("fold")).toBe(true);
    expect(strip().classList.contains("all")).toBe(false);
  });

  it("C-DRAFT-LOADER.maths/7 a finished run with all six: 'All 6 parts are in', the bar full, then the strip folds", () => {
    vi.useFakeTimers();
    const live = runOf({}, { ready: true });
    expect(allIn(live)).toBe(true);
    panel(live);
    expect(host.textContent).toContain(LOADER_ALL_IN);
    expect(strip().classList.contains("all")).toBe(true);
    expect(bar().getAttribute("aria-valuenow")).toBe("100");
    expect(strip().classList.contains("fold")).toBe(false); // a short hold first
    act(() => vi.advanceTimersByTime(900));
    expect(strip().classList.contains("fold")).toBe(true);
    expect(status()).toBe("Up to date");
    expect(host.textContent).toContain(READINESS.ready);
    expect(move().tagName).toBe("A");
  });

  it("C-DRAFT-LOADER.failure/1 a failed part counts as in: the all-in line plays", () => {
    // One part errors (`failed` from the stream), the other five fill.
    let live = applyEvent(fromDraft(null), { event: "run", data: { run_id: "run-1", parts: MEANS } }, 0);
    for (const m of MEANS)
      live = applyEvent(
        live,
        m.key === "often" ? part("often", null, "failed") : part(m.key, FILLED[m.key]),
        200,
      );
    live = applyEvent(live, { event: "done", data: { ready: true } }, 300);
    expect(partIn(live.parts, "often")).toBe(true);
    expect(allIn(live)).toBe(true);
    panel(live);
    expect(host.textContent).toContain(LOADER_ALL_IN);
    expect(host.textContent).toContain("Couldn't work this out. Add it yourself.");
  });

  it("C-DRAFT-LOADER.failure/1 a part given up past 10 × its mean counts as in", () => {
    let live = applyEvent(fromDraft(null), { event: "run", data: { run_id: "run-1", parts: MEANS } }, 0);
    for (const m of MEANS) if (m.key !== "area") live = applyEvent(live, part(m.key, FILLED[m.key]), 200);
    live = giveUp(live, 7001); // area: 10 × 700
    expect(live.parts.area.state).toBe("failed");
    expect(live.running).toBe(false);
    expect(allIn(live)).toBe(true);
    expect(loaderLine(live.loader!, 7001)).toBe(LOADER_ALL_IN);
  });

  it("C-DRAFT-LOADER.maths/9 the person adds words and every part fills: the next run plays the all-in sequence", () => {
    const first = runOf({ often: null, area: null });
    expect(allIn(first)).toBe(false);
    const second = runOf(
      { often: "About 30 new folios a day at one branch", area: "Operations" },
      { start: first, id: "run-2", keys: ["often", "area"], ready: true },
    );
    expect(second.loader!.waiting).toEqual([]);
    expect(allIn(second)).toBe(true);
    panel(second);
    expect(host.textContent).toContain(LOADER_ALL_IN);
    expect(strip().classList.contains("all")).toBe(true);
  });
});

describe("C-DRAFT-LOADER.maths with parts waiting for words (BLD-C157)", () => {
  const run = (over: Partial<LoaderRun> = {}): LoaderRun => ({
    parts: MEANS,
    startedAt: 0,
    answered: Object.fromEntries(MEANS.map((m) => [m.key, 100])),
    ...over,
  });

  it("maths/4 every part answered but one blank: the bar stays at 97%, never full, and never moves back", () => {
    expect(barValue(run(), 1000)).toBe(1);
    expect(barValue(run({ waiting: ["area"] }), 1000)).toBe(0.97);
    const pending = { ...run().answered };
    delete pending.area;
    expect(barValue(run({ answered: pending }), 650)).toBeLessThanOrEqual(
      barValue(run({ waiting: ["area"] }), 650),
    );
  });

  it("maths/5 the count leaves out blank parts; the all-in line needs all six", () => {
    expect(readyCount(run({ waiting: ["often", "area"] }), 1000)).toBe(4);
    expect(loaderLine(run({ waiting: ["often", "area"] }), 1000)).toBe("4 of 6 ready, almost there");
    expect(loaderLine(run(), 1000)).toBe(LOADER_ALL_IN);
  });

  it("L-DRAFT.parts/3 similar ideas left out of a short draft's run: still not all six in", () => {
    const live = runOf({}, { keys: ["title", "often", "who", "value", "area"], ready: true });
    expect(live.loader!.waiting).toEqual(["similar"]);
    expect(loaderLine(live.loader!, 1000)).toBe("5 of 5 ready, almost there");
    expect(allIn(live)).toBe(false);
    panel(live);
    expect(host.textContent).not.toContain(LOADER_ALL_IN);
    expect(strip().classList.contains("fold")).toBe(true);
    // L-DRAFT.parts/7: title, summary and area are there, so Move to Review is on.
    expect(move().tagName).toBe("A");
  });

  it("L-DRAFT.parts/7 Move to Review: How often, Who and Worth may wait; a missing area holds it", () => {
    const base = { chars: WORDS.length, minChars: 30, sending: false, running: false };
    expect(readinessOf({ ...base, ready: true })).toBe("ready");
    expect(readinessOf({ ...base, ready: false })).toBe("more");
    expect(readinessOf({ ...base, running: true, ready: true })).toBe("working");
    expect(readinessOf({ ...base, sending: true, ready: true })).toBe("finishing");
    expect(readinessOf({ ...base, chars: 12, ready: true })).toBe("more");
  });
});
