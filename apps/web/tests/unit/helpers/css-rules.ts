/**
 * A stylesheet as written, read into its rules, for unit tests that check what a browser would apply (lane F's
 * V-ACC tests, BLD-F077). Each style rule keeps its enclosing at-rules (`@media (…)`, `@keyframes name`), its
 * selectors and its declarations; comments are dropped. Small on purpose: no nesting, no `@import`.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

export type CssRule = { at: string; selectors: string[]; decls: Map<string, string> };

/** The app's source folder (`apps/web/src`). */
export const SRC = resolve(__dirname, "../../../src");

/** Every style rule in the sheet at `path` (relative to `apps/web/src`). */
export function cssRules(path: string): CssRule[] {
  const css = readFileSync(resolve(SRC, path), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  const out: CssRule[] = [];
  const stack: string[] = [];
  let buf = "";
  let current: CssRule | null = null;
  const take = () => {
    const m = buf.trim().match(/^([\w-]+)\s*:\s*([\s\S]+)$/);
    if (m && current) current.decls.set(m[1]!, m[2]!.trim());
    buf = "";
  };
  for (const ch of css) {
    if (ch === "{") {
      const head = buf.trim().replace(/\s+/g, " ");
      buf = "";
      if (head.startsWith("@")) stack.push(head);
      else {
        current = { at: stack.join(" "), selectors: head.split(",").map((s) => s.trim()), decls: new Map() };
        stack.push("");
        out.push(current);
      }
    } else if (ch === "}") {
      if (stack.pop() === "" && current) {
        take();
        current = null;
      }
      buf = "";
    } else if (ch === ";" && current) take();
    else buf += ch;
  }
  return out;
}

/** Whether `el` matches the selector; false for selectors the DOM cannot test (keyframe stops, odd syntax). */
export function matches(el: Element, selector: string): boolean {
  try {
    return el.matches(selector);
  } catch {
    return false;
  }
}

/** Whether every media condition in `at` holds at a viewport `width` px wide (min-width, max-width, the range form
 * `(width > 640px)` with >, >=, < or <=, and prefers-reduced-motion only; anything else is taken not to hold). An
 * empty `at` always holds. */
export function holdsAt(at: string, width: number, reducedMotion = false): boolean {
  for (const media of at.match(/@media [^@]*/g) ?? []) {
    // The range form (BLD-D027): no colon, so the feature pass below never sees it.
    for (const [, op, value] of media.matchAll(/\(\s*width\s*(<=|>=|<|>)\s*([\d.]+)px\s*\)/g)) {
      const px = parseFloat(value!);
      if (op === ">" && !(width > px)) return false;
      if (op === ">=" && !(width >= px)) return false;
      if (op === "<" && !(width < px)) return false;
      if (op === "<=" && !(width <= px)) return false;
    }
    for (const [, feature, value] of media.matchAll(/\(\s*([\w-]+)\s*:\s*([^)]+)\)/g)) {
      const px = parseFloat(value!);
      if (feature === "min-width" && !(width >= px)) return false;
      if (feature === "max-width" && !(width <= px)) return false;
      if (feature === "prefers-reduced-motion" && (value!.trim() === "reduce") !== reducedMotion)
        return false;
      if (!["min-width", "max-width", "prefers-reduced-motion"].includes(feature!)) return false;
    }
  }
  return !/@(supports|container)/.test(at);
}

/** The value a property takes on `el` from the sheet at that width: the last matching rule wins (same-specificity
 * reading, which is how these sheets are written). */
export function applied(
  rules: CssRule[],
  el: Element,
  prop: string,
  width: number,
  reducedMotion = false,
): string | undefined {
  let value: string | undefined;
  for (const r of rules) {
    if (r.at.startsWith("@keyframes") || !holdsAt(r.at, width, reducedMotion)) continue;
    if (r.decls.has(prop) && r.selectors.some((s) => matches(el, s))) value = r.decls.get(prop);
  }
  return value;
}

/** A keyframes block's stops, by percentage (`from` is 0, `to` is 100), each with its declarations. */
export function keyframes(rules: CssRule[], name: string): Array<{ at: number; decls: Map<string, string> }> {
  const out: Array<{ at: number; decls: Map<string, string> }> = [];
  for (const r of rules) {
    if (r.at !== `@keyframes ${name}`) continue;
    for (const s of r.selectors)
      out.push({ at: s === "from" ? 0 : s === "to" ? 100 : parseFloat(s), decls: r.decls });
  }
  return out.sort((a, b) => a.at - b.at);
}

/** The names of every `@keyframes` block in the rules. */
export function keyframeNames(rules: CssRule[]): string[] {
  return [...new Set(rules.filter((r) => r.at.startsWith("@keyframes ")).map((r) => r.at.slice(11).trim()))];
}
