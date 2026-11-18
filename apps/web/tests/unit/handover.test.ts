// @vitest-environment jsdom
/**
 * F-MOTION.handover (lane D, BLD-D015): after a hand-over the new screen arrives once. The hand-over's class on <html>
 * stays until the next navigation, because taking it off changes the arrival blocks' animation-name and a new name
 * plays the arrival again (lane G's 13:00 walk caught screens rising out of the blur a second time, 1.6 s in). Only
 * the wait, "mo-a-wait", comes off on a timer, since a new delay never restarts an animation.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

let pathname = "/home";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

import { ARRIVAL_WAIT, ARRIVAL_WAIT_MS, Handover } from "@/components/motion/handover";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const html = () => document.documentElement.classList;
let root: Root;
let host: HTMLDivElement;

function go(to: string) {
  pathname = to;
  act(() => root.render(createElement(Handover)));
}

/** A left click on a plain link, as a person makes it. jsdom does not navigate, so the test moves the path itself. */
function tap(cls: string, href: string) {
  const a = document.createElement("a");
  a.href = href;
  a.className = cls;
  a.textContent = "Open";
  a.addEventListener("click", (e) => e.preventDefault());
  document.body.appendChild(a);
  a.dispatchEvent(
    new MouseEvent("click", { bubbles: true, cancelable: true, button: 0, clientX: 10, clientY: 10 }),
  );
  a.remove();
}

beforeEach(() => {
  vi.useFakeTimers();
  pathname = "/home";
  document.documentElement.className = "";
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  act(() => root.render(createElement(Handover)));
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.useRealTimers();
});

describe("F-MOTION.handover, BLD-D015: the arrival plays once", () => {
  it("sets the hand-over's class and the wait on the new screen", () => {
    tap("", "/wall");
    go("/wall");
    expect(html().contains("mo-a-fwd")).toBe(true);
    expect(html().contains(ARRIVAL_WAIT)).toBe(true);
  });

  it("takes only the wait off on the timer; the hand-over's class stays, so nothing arrives twice", () => {
    tap("back", "/wall");
    go("/wall");
    expect(html().contains("mo-a-back")).toBe(true);
    act(() => vi.advanceTimersByTime(ARRIVAL_WAIT_MS + 50));
    expect(html().contains(ARRIVAL_WAIT)).toBe(false);
    expect(html().contains("mo-a-back")).toBe(true);
    act(() => vi.advanceTimersByTime(10_000));
    expect(html().contains("mo-a-back")).toBe(true);
  });

  it("the next navigation clears both, so a Back with nothing recorded never inherits a direction", () => {
    tap("", "/wall");
    go("/wall");
    go("/home");
    expect(html().contains("mo-a-fwd")).toBe(false);
    expect(html().contains(ARRIVAL_WAIT)).toBe(false);
  });

  it("a navigation before the timer ends drops the old wait with the old class", () => {
    tap("back", "/wall");
    go("/wall");
    tap("", "/ideas/IDEA-2026-900001");
    go("/ideas/IDEA-2026-900001");
    expect(html().contains("mo-a-back")).toBe(false);
    expect(html().contains("mo-a-fwd")).toBe(true);
    act(() => vi.advanceTimersByTime(ARRIVAL_WAIT_MS + 50));
    expect(html().contains(ARRIVAL_WAIT)).toBe(false);
    expect(html().contains("mo-a-fwd")).toBe(true);
  });

  it("the wait outlasts the slowest arrival: a showcase screen's last block (420 + 6 × 80 + 1,000 ms)", () => {
    expect(ARRIVAL_WAIT_MS).toBeGreaterThanOrEqual(420 + 6 * 80 + 1_000);
  });
});

describe("F-MOTION.handover, BLD-D015: motion.css waits only under mo-a-wait", () => {
  const css = readFileSync(resolve(__dirname, "../../src/app/motion.css"), "utf8");
  const setters = [...css.matchAll(/([^{}]+)\{[^{}]*--mo-base:\s*([^;]+);/g)].map((m) => ({
    sel: m[1]!.replace(/\/\*[\s\S]*?\*\//g, "").trim(),
    value: m[2]!.trim(),
  }));

  it("the grow and the flood set their wait only together with mo-a-wait", () => {
    expect(setters).toContainEqual({ sel: ".mo-a-expand.mo-a-wait", value: "380ms" });
    expect(setters).toContainEqual({ sel: ".mo-a-portal.mo-a-wait", value: "420ms" });
  });

  it("no other rule sets a wait above zero", () => {
    const others = setters.filter((s) => !s.sel.endsWith(".mo-a-wait"));
    expect(others.map((s) => s.value)).toEqual(others.map(() => "0ms"));
  });
});
