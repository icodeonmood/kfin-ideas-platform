/**
 * C-CHIP.states: a selected chip is the wash, blueT words and a 1.5px blue ring, "and a leading tick on choice chips
 * (sorting, filters on phone)". A row passed `filter` keeps the ring, wash and aria-checked everywhere and shows the tick
 * only at 640px and narrower; without it nothing changes.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ChoiceChips, MultiChips, type ChipOption } from "@/components/ui/chips";

const CSS = readFileSync(
  fileURLToPath(new URL("../../src/app/components.css", import.meta.url)),
  "utf8",
).replace(/\/\*[\s\S]*?\*\//g, "");

const KINDS: ChipOption[] = [
  { value: "all", label: "All" },
  { value: "problem", label: "Problems" },
  { value: "fix", label: "Fixes" },
  { value: "business", label: "Business ideas" },
];

const choice = (props: { filter?: boolean; scroll?: boolean }) =>
  renderToStaticMarkup(
    createElement(ChoiceChips, {
      label: "Show",
      options: KINDS,
      value: "fix",
      onChange: () => undefined,
      ...props,
    }),
  );

const multi = (props: { filter?: boolean }) =>
  renderToStaticMarkup(
    createElement(MultiChips, {
      label: "Show",
      options: KINDS,
      values: ["fix"],
      onChange: () => undefined,
      ...props,
    }),
  );

describe("C-CHIP.states: the filter row's tick", () => {
  it("without `filter` nothing changes: the same classes and a tick in every chip", () => {
    expect(choice({ scroll: true })).toMatch(
      /^<div class="chips scroll" role="radiogroup" aria-label="Show">/,
    );
    expect(choice({})).toMatch(/^<div class="chips" role="radiogroup"/);
    expect(multi({})).toMatch(/^<div class="chips" role="group"/);
    expect(choice({}).match(/class="chip-tick"/g)).toHaveLength(4);
  });

  it("with `filter` the row is marked, and the selected chip keeps aria-checked (or aria-pressed)", () => {
    const html = choice({ filter: true, scroll: true });
    expect(html).toMatch(/^<div class="chips scroll filter" role="radiogroup"/);
    expect(html.match(/aria-checked="true"/g)).toHaveLength(1);
    expect(html).toMatch(/aria-checked="true"[^>]*><span class="chip-tick" aria-hidden="true">/);
    expect(multi({ filter: true })).toMatch(/^<div class="chips filter" role="group"/);
    expect(multi({ filter: true })).toContain('aria-pressed="true"');
  });

  it("the tick is hidden on a filter row only above 640px; the phone keeps it", () => {
    expect(CSS).toMatch(
      /@media \(min-width: 641px\) \{\s*\.chips\.filter \.chip \.chip-tick \{\s*display: none;\s*\}\s*\}/,
    );
    expect(CSS.match(/\.chips\.filter/g)).toHaveLength(1);
  });

  it("the ring and wash are not tied to the tick: every selected chip keeps them", () => {
    expect(CSS).toMatch(
      /\.chip\[aria-checked="true"\],\s*\.chip\[aria-pressed="true"\] \{\s*background: var\(--wash\);\s*color: var\(--blueT\);\s*box-shadow: inset 0 0 0 1\.5px var\(--blue\);\s*\}/,
    );
  });
});
