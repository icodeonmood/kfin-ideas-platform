/**
 * F-ICONS.mark (BLD-D022): SparkMark draws the pack's one mark at every size. The small cut (heavier zeros, no
 * ember below 32px) is gone, so the sidebar's 22px mark and Landing's large one share the same geometry: rings r34
 * at stroke 14, the slash polygon 34,236 146.9,27.2 169.1,40.8 and the ember dot r9 at 171.6,11.8. The rings take
 * currentColor; the slash and dot are spark. Synthetic data only.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SparkMark } from "@/components/spark-mark";

const render = (props: Parameters<typeof SparkMark>[0]) =>
  renderToStaticMarkup(createElement(SparkMark, props));

/** The svg's children, with the outer element (which carries the size) stripped. */
const inner = (html: string) => html.replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "");

/** The pack's mark (F-ICONS.mark), with the ink rings as currentColor and the spark as #F46835. */
const PACK = [
  '<circle class="mark-zero" cx="52" cy="58" r="34" fill="none" stroke="currentColor" stroke-width="14"></circle>',
  '<circle class="mark-zero" cx="148" cy="184" r="34" fill="none" stroke="currentColor" stroke-width="14"></circle>',
  '<polygon class="mark-spark" points="34,236 146.9,27.2 169.1,40.8" fill="#F46835"></polygon>',
  '<circle class="mark-ember" cx="171.6" cy="11.8" r="9" fill="#F46835"></circle>',
].join("");

describe("F-ICONS.mark, BLD-D022: one mark at every size", () => {
  it("F-ICONS.mark: SparkMark renders the same geometry at 22px and at 64px", () => {
    const small = render({ height: 22 });
    const large = render({ height: 64 });
    expect(inner(small)).toBe(PACK);
    expect(inner(large)).toBe(inner(small));
    // Only the size differs (the viewBox keeps the pack's 200×240 proportions).
    expect(small).toMatch(/^<svg width="18" height="22" viewBox="0 0 200 240"/);
    expect(large).toMatch(/^<svg width="53" height="64" viewBox="0 0 200 240"/);
  });

  it("F-ICONS.mark: the geometry matches the pack's own SVG, at every size the app draws", () => {
    const pack = readFileSync(
      resolve(__dirname, "../../../../1pc-handoff/01-foundations/F-ICONS.md"),
      "utf8",
    );
    const svg = pack.match(/```svg\n([\s\S]*?)```/)?.[1] ?? "";
    expect(svg).toContain('<circle cx="52" cy="58" r="34" fill="none" stroke="#111111" stroke-width="14"/>');
    expect(svg).toContain(
      '<circle cx="148" cy="184" r="34" fill="none" stroke="#111111" stroke-width="14"/>',
    );
    expect(svg).toContain('<polygon points="34,236 146.9,27.2 169.1,40.8" fill="#F46835"/>');
    expect(svg).toContain('<circle cx="171.6" cy="11.8" r="9" fill="#F46835"/>');
    for (const height of [14, 22, 26, 31, 32, 48, 96]) {
      const html = render({ height });
      expect(inner(html), `${height}px`).toBe(PACK);
      expect(html).not.toContain('stroke-width="24"');
    }
  });

  it("F-ICONS.mark: decorative by default, a named image when it stands alone", () => {
    expect(render({ height: 22 })).toContain('aria-hidden="true"');
    expect(render({ height: 22 })).toContain('focusable="false"');
    const named = render({ height: 22, label: "1% Club" });
    expect(named).toContain('role="img"');
    expect(named).toContain('aria-label="1% Club"');
    expect(named).not.toContain("aria-hidden");
  });

  it("keeps the class the caller passes", () =>
    expect(render({ height: 22, className: "sb-mark" })).toMatch(/^<svg class="sb-mark"/));
});
