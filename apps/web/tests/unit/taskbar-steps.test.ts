// @vitest-environment jsdom
/**
 * C-TASKBAR.steps (BLD-D024): the task bar always draws Check it's numbered nodes, on Tell it too. State shows by
 * shape: a ticked ring for a done step, an ink disc with the number for the current one, a hollow numbered ring for
 * one to come. The labels, "Tell it, done", `aria-current="step"` and the done-step links are as before. Synthetic
 * data only.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));

const { Taskbar } = await import("@/components/shell/taskbar");
type Props = Parameters<typeof Taskbar>[0];

const DRAFT = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";

function bar(props: Partial<Props> & Pick<Props, "step">): HTMLElement {
  const host = document.createElement("div");
  host.innerHTML = renderToStaticMarkup(createElement(Taskbar, { save: "idle", closeHref: "/", ...props }));
  return host;
}

/** Each step as its state, the node's mark (a number or "tick") and the words a screen reader hears. */
function steps(host: HTMLElement) {
  return [...host.querySelectorAll<HTMLLIElement>("ol.tsteps > li")].map((li) => {
    const node = li.querySelector(".tsn")!;
    return {
      state: li.className,
      current: li.getAttribute("aria-current"),
      node: node.querySelector("svg") ? "tick" : node.textContent,
      hidden: node.getAttribute("aria-hidden"),
      label: li.querySelector(".tsl")!.textContent,
      href: li.querySelector("a")?.getAttribute("href") ?? null,
      heard: [...li.querySelectorAll(".tsl, .vh")].map((e) => e.textContent).join(""),
    };
  });
}

describe("C-TASKBAR.steps, BLD-D024: the numbered nodes on every task screen", () => {
  it("C-TASKBAR.steps: Tell it draws the nodes, not bars: the current disc 1, then hollow rings 2 and 3", () => {
    const host = bar({ step: "tell" });
    const ol = host.querySelector("ol")!;
    expect(ol.className).toBe("tsteps tsteps-nodes");
    expect(ol.getAttribute("aria-label")).toBe("Progress");
    expect(steps(host)).toEqual([
      {
        state: "now",
        current: "step",
        node: "1",
        hidden: "true",
        label: "Tell it",
        href: null,
        heard: "Tell it",
      },
      {
        state: "next",
        current: null,
        node: "2",
        hidden: "true",
        label: "Check it",
        href: null,
        heard: "Check it",
      },
      {
        state: "next",
        current: null,
        node: "3",
        hidden: "true",
        label: "Send it",
        href: null,
        heard: "Send it",
      },
    ]);
  });

  it("C-TASKBAR.steps: Check it ticks Tell it, done, and links back to it", () => {
    const host = bar({ step: "check", stepHrefs: { tell: `/share?draft=${DRAFT}` } });
    expect(steps(host)).toEqual([
      {
        state: "done",
        current: null,
        node: "tick",
        hidden: "true",
        label: "Tell it",
        href: `/share?draft=${DRAFT}`,
        heard: "Tell it, done",
      },
      {
        state: "now",
        current: "step",
        node: "2",
        hidden: "true",
        label: "Check it",
        href: null,
        heard: "Check it",
      },
      {
        state: "next",
        current: null,
        node: "3",
        hidden: "true",
        label: "Send it",
        href: null,
        heard: "Send it",
      },
    ]);
  });

  it("C-TASKBAR.steps: Send it ticks both done steps; a done step without a link stays words", () => {
    const host = bar({ step: "send", stepHrefs: { check: `/share/${DRAFT}/check` } });
    expect(steps(host).map(({ state, node, href, heard }) => ({ state, node, href, heard }))).toEqual([
      { state: "done", node: "tick", href: null, heard: "Tell it, done" },
      { state: "done", node: "tick", href: `/share/${DRAFT}/check`, heard: "Check it, done" },
      { state: "now", node: "3", href: null, heard: "Send it" },
    ]);
  });

  it("C-TASKBAR.steps: every step and screen uses the one look; there is no bars look left", () => {
    for (const step of ["tell", "check", "send"] as const) {
      const host = bar({ step });
      expect(host.querySelectorAll(".tsteps-nodes")).toHaveLength(1);
      expect(host.querySelectorAll(".tsteps-bars")).toHaveLength(0);
      expect(host.querySelectorAll("ol.tsteps .tsn")).toHaveLength(3);
    }
    // Passing the old prop (a screen not yet tidied) changes nothing.
    const old = { step: "tell", look: "bars" } as unknown as Props;
    expect(bar(old).querySelector("ol")!.className).toBe("tsteps tsteps-nodes");
    const css = readFileSync(resolve(__dirname, "../../src/app/shell.css"), "utf8");
    expect(css).not.toContain(".tsteps-bars");
    expect(css).toContain(".tsteps-nodes li.now .tsn");
  });

  it("S-04.empty: steps={false} still hides the steps before the first message", () =>
    expect(bar({ step: "tell", steps: false }).querySelector(".tsteps")).toBeNull());
});
