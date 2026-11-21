// @vitest-environment jsdom
/**
 * The walk's three shared styles (lane D, BLD-D019; the product lead's DEC-124 and DEC-126 of 20 Nov): the quiet link
 * ("Withdraw"), the inactive "Requested" button and the "+" attach button in a prompt box's tool row. Each is checked
 * in its markup and in the stylesheet as written, with colours computed from the pack's tokens (as
 * foundation.test.ts does for pills). Synthetic content only.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { applied, cssRules, SRC, type CssRule } from "./helpers/css-rules";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));

const { Button, ButtonLink, buttonClass } = await import("@/components/ui/button");
const { AttachButton, ATTACH_NAME } = await import("@/components/ui/attach-button");

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// ---------------------------------------------------------------------------------------------------------------
// The sheets and the tokens

/** A selector list split at its top-level commas only, so `:is(a, b)` stays one selector. */
function splitSelectors(list: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let buf = "";
  for (const ch of list) {
    if (ch === "(") depth++;
    if (ch === ")") depth--;
    if (ch === "," && depth === 0) {
      out.push(buf.trim());
      buf = "";
    } else buf += ch;
  }
  out.push(buf.trim());
  return out;
}

/** A sheet's rules with each selector list split as a browser would. */
const sheet = (path: string): CssRule[] =>
  cssRules(path).map((r) => ({ ...r, selectors: splitSelectors(r.selectors.join(", ")) }));

const OFFER = sheet("app/offer.css");
const COMPONENTS = sheet("app/components.css");
const COMPOSE = sheet("app/share/compose.css");

/** The declarations of the rule whose selector list holds `selector` exactly. */
function rule(rules: CssRule[], selector: string): Map<string, string> {
  const found = rules.filter((r) => r.selectors.includes(selector));
  if (!found.length) throw new Error(`no rule for ${selector}`);
  return found[found.length - 1]!.decls;
}

/** Every custom property tokens.css and foundation.css declare, the first value of each. */
const TOKENS = (() => {
  const out = new Map<string, string>();
  for (const file of ["app/tokens.css", "app/foundation.css"]) {
    const css = readFileSync(resolve(SRC, file), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
    for (const m of css.matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g))
      if (!out.has(m[1]!)) out.set(m[1]!, m[2]!.trim());
  }
  return out;
})();

/** A value with its var() resolved through the tokens. */
function token(value: string | undefined): string {
  const m = value?.trim().match(/^var\((--[\w-]+)\)$/);
  if (!m) return (value ?? "").trim().toLowerCase();
  const v = TOKENS.get(m[1]!);
  if (v === undefined) throw new Error(`no token ${m[1]}`);
  return token(v);
}

function luminance(hex: string): number {
  const v = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(v.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r!) + 0.7152 * lin(g!) + 0.0722 * lin(b!);
}

function contrast(a: string, b: string): number {
  const hex = (c: string) => {
    const v = token(c);
    if (v === "#fff" || v === "white") return "#ffffff";
    if (!/^#[0-9a-f]{6}$/.test(v)) throw new Error(`not a solid colour: ${c} (${v})`);
    return v;
  };
  const [hi, lo] = [luminance(hex(a)), luminance(hex(b))].sort((x, y) => y - x);
  return (hi! + 0.05) / (lo! + 0.05);
}

const px = (value: string | undefined) => parseFloat(token(value));

/** An element with these classes and attributes, in a body, so selectors can be matched against it. */
function el(tag: string, cls: string, attrs: Record<string, string> = {}, parentCls?: string): HTMLElement {
  const node = document.createElement(tag);
  node.className = cls;
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parentCls) {
    const parent = document.createElement("div");
    parent.className = parentCls;
    parent.append(node);
    document.body.append(parent);
  } else document.body.append(node);
  return node;
}

const GROUNDS = ["var(--paper)", "var(--card)", "var(--sunk)"];

// ---------------------------------------------------------------------------------------------------------------
// Rendering

let host: HTMLElement;
let root: Root;

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = "";
});

async function render(node: ReturnType<typeof createElement>): Promise<HTMLElement> {
  await act(async () => root.render(node));
  return host.firstElementChild as HTMLElement;
}

async function click(target: HTMLElement): Promise<MouseEvent> {
  const e = new MouseEvent("click", { bubbles: true, cancelable: true });
  await act(async () => {
    target.dispatchEvent(e);
  });
  return e;
}

// ---------------------------------------------------------------------------------------------------------------

describe("C-BUTTON.variants, DEC-126: the quiet link, Withdraw (BLD-D019)", () => {
  it("C-BUTTON, DEC-126: buttonClass('quiet') is link-quiet at any size; Button draws a <button>, ButtonLink an <a>", async () => {
    expect(buttonClass("quiet")).toBe("link-quiet");
    expect(buttonClass("quiet", "full")).toBe("link-quiet");
    expect(buttonClass("quiet", "sm", "crew-withdraw")).toBe("link-quiet crew-withdraw");

    const button = await render(createElement(Button, { variant: "quiet" }, "Withdraw"));
    expect(button.tagName).toBe("BUTTON");
    expect(button.getAttribute("type")).toBe("button");
    expect(button.className).toBe("link-quiet");
    expect(button.textContent).toBe("Withdraw");

    const link = await render(createElement(ButtonLink, { variant: "quiet", href: "/crew" }, "How it works"));
    expect(link.tagName).toBe("A");
    expect(link.className).toBe("link-quiet");
  });

  it("F-COLOR.contrast, DEC-126: its words reach 4.5:1 on the page and card grounds, at rest and on hover", () => {
    for (const tag of ["a", "button"]) {
      const words = applied(OFFER, el(tag, "link-quiet"), "color", 1440);
      expect(token(words), `${tag}.link-quiet colour`).toBe(token("var(--mute)"));
      for (const ground of GROUNDS)
        expect(contrast(words!, ground), `${tag}.link-quiet on ${ground}`).toBeGreaterThanOrEqual(4.5);
    }
    const hover = rule(OFFER, ".link-quiet:hover").get("color");
    for (const ground of GROUNDS)
      expect(contrast(hover!, ground), `hover on ${ground}`).toBeGreaterThanOrEqual(4.5);
  });

  it("F-TYPE.scale meta, DEC-126: grey sub-text weight, underlined in its own colour, and hover keeps the underline", () => {
    const quiet = el("button", "link-quiet");
    expect(applied(OFFER, quiet, "font", 1440)).toBe("400 13.5px/1.45 var(--ft)");
    expect(applied(OFFER, quiet, "text-decoration", 1440)).toBe("underline");
    expect(applied(OFFER, quiet, "text-decoration-color", 1440)).toBe("currentColor");
    const hover = rule(OFFER, ".link-quiet:hover");
    expect(hover.get("text-decoration")).toBeUndefined();
    expect(hover.get("text-decoration-line")).toBeUndefined();
  });

  it("F-A11Y.rules/2, DEC-126: a visible focus ring, 2px solid blue, off its edge, and nothing takes it away", () => {
    const focus = rule(OFFER, ".link-quiet:focus-visible");
    expect(focus.get("outline")).toBe("2px solid var(--blue)");
    expect(px(focus.get("outline-offset"))).toBeGreaterThanOrEqual(2);
    for (const rules of [OFFER, COMPONENTS])
      for (const r of rules)
        if (r.selectors.some((s) => s.includes("link-quiet")))
          expect(["none", "0"], r.selectors.join(", ")).not.toContain(r.decls.get("outline"));
  });

  it("WCAG 2.5.8, DEC-126: its target is at least 24px on an <a> and on a <button>", () => {
    for (const tag of ["a", "button"]) {
      const quiet = el(tag, "link-quiet");
      expect(applied(OFFER, quiet, "display", 1440)).toBe("inline-flex");
      expect(px(applied(OFFER, quiet, "min-height", 1440)), `${tag} height`).toBeGreaterThanOrEqual(24);
      expect(px(applied(OFFER, quiet, "min-width", 1440)), `${tag} width`).toBeGreaterThanOrEqual(24);
      expect(px(applied(OFFER, quiet, "min-height", 360)), `${tag} height on a phone`).toBeGreaterThanOrEqual(
        24,
      );
    }
  });

  it("C-BUTTON.states/5, DEC-126: busy works on Withdraw as on the other buttons: aria-busy, the spinner, no click", async () => {
    const onClick = vi.fn();
    const button = await render(createElement(Button, { variant: "quiet", busy: true, onClick }, "Withdraw"));
    expect(button.getAttribute("aria-busy")).toBe("true");
    expect(button.querySelector(".spin")).not.toBeNull();
    await click(button);
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe("C-BUTTON.states, DEC-126: Requested, the inactive button (BLD-D019)", () => {
  it("C-BUTTON, DEC-126: Requested is aria-disabled and focusable", async () => {
    const button = await render(createElement(Button, { size: "full", inactive: true }, "Requested"));
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.hasAttribute("disabled")).toBe(false);
    expect(button.tabIndex).toBe(0);
    expect(button.className).toBe("btn btn-primary btn-full is-inactive");
    button.focus();
    expect(document.activeElement).toBe(button);
  });

  it("C-BUTTON, DEC-126: a click on Requested does nothing: no onClick, no onDisabledClick, no form sent", async () => {
    const onClick = vi.fn();
    const onDisabledClick = vi.fn();
    const button = await render(
      createElement(Button, { inactive: true, disabled: true, onClick, onDisabledClick }, "Requested"),
    );
    const e = await click(button);
    expect(onClick).not.toHaveBeenCalled();
    expect(onDisabledClick).not.toHaveBeenCalled();
    expect(e.defaultPrevented).toBe(true);
  });

  it("C-BUTTON.states/4: a disabled button is unchanged: aria-disabled, focusable, and its click calls onDisabledClick", async () => {
    const onClick = vi.fn();
    const onDisabledClick = vi.fn();
    const button = await render(
      createElement(Button, { disabled: true, onClick, onDisabledClick }, "Move to Review"),
    );
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.className).not.toContain("is-inactive");
    await click(button);
    expect(onDisabledClick).toHaveBeenCalledTimes(1);
    expect(onClick).not.toHaveBeenCalled();
  });

  it.each(["primary", "line", "soft", "text", "text-blue", "quiet"] as const)(
    "C-BUTTON, DEC-126: inactive works with the %s variant and keeps the caller's class",
    async (variant) => {
      const button = await render(
        createElement(Button, { variant, inactive: true, className: "crew-join" }, "Requested"),
      );
      expect(button.className).toBe(`${buttonClass(variant)} is-inactive crew-join`);
      expect(button.getAttribute("aria-disabled")).toBe("true");
    },
  );

  it.each([
    ["btn btn-primary btn-full is-inactive"],
    ["btn btn-secondary is-inactive"],
    ["btn btn-soft btn-sm is-inactive"],
  ])("F-COLOR.contrast/3, DEC-126: %s is the disabled grey and keeps its words at 3:1 or better", (cls) => {
    for (const attrs of [{ "aria-disabled": "true" }, {}] as Record<string, string>[]) {
      const button = el("button", cls, attrs);
      const fill = applied(OFFER, button, "background", 1440);
      const words = applied(OFFER, button, "color", 1440);
      expect(token(fill)).toBe(token("var(--rule2)"));
      expect(token(words)).toBe(token("var(--placeholder)"));
      expect(contrast(words!, fill!)).toBeGreaterThanOrEqual(3);
    }
  });

  it("C-BUTTON, DEC-126: hover and press change nothing on Requested, and its cursor is the plain one", () => {
    const still = rule(OFFER, '.btn.is-inactive:is(:hover, :active, [aria-disabled="true"])');
    expect(still.get("background")).toBe("var(--rule2)");
    expect(still.get("color")).toBe("var(--placeholder)");
    expect(still.get("box-shadow")).toBe("none");
    expect(still.get("transform")).toBe("none");
    expect(still.get("cursor")).toBe("default");
  });

  it("F-COLOR.contrast/3, DEC-126: an inactive text or quiet button keeps its words at 3:1 on the page and card grounds", () => {
    for (const cls of ["tb is-inactive", "link-quiet is-inactive"]) {
      const words = applied(OFFER, el("button", cls, { "aria-disabled": "true" }), "color", 1440);
      expect(token(words)).toBe(token("var(--placeholder)"));
      for (const ground of GROUNDS) expect(contrast(words!, ground)).toBeGreaterThanOrEqual(3);
    }
  });
});

describe("C-PROMPT.anatomy/2, DEC-124: the “+” attach button (BLD-D019)", () => {
  it("C-PROMPT.anatomy/2, DEC-124: its accessible name and its tooltip are exactly “Add files, a folder or a link”", async () => {
    expect(ATTACH_NAME).toBe("Add files, a folder or a link");
    const button = await render(createElement(AttachButton));
    expect(button.tagName).toBe("BUTTON");
    expect(button.getAttribute("type")).toBe("button");
    expect(button.getAttribute("aria-label")).toBe("Add files, a folder or a link");
    expect(button.getAttribute("title")).toBe("Add files, a folder or a link");
    expect(button.textContent).toBe("");
    expect(button.className).toBe("attach-btn");
    expect(button.hasAttribute("aria-expanded")).toBe(false);
  });

  it("C-PROMPT.anatomy/2, S-R3, BLD-B275: `label` and `tooltip` set the name and the title; by default both stay ATTACH_NAME", async () => {
    const plain = await render(createElement(AttachButton, { label: undefined, tooltip: undefined }));
    expect(plain.getAttribute("aria-label")).toBe(ATTACH_NAME);
    expect(plain.getAttribute("title")).toBe(ATTACH_NAME);
    const answer = await render(
      createElement(AttachButton, { label: "Attach files to this answer", tooltip: "Attach files" }),
    );
    expect(answer.getAttribute("aria-label")).toBe("Attach files to this answer");
    expect(answer.getAttribute("title")).toBe("Attach files");
    expect(answer.className).toBe("attach-btn");
  });

  it("F-ICONS.style/1–5, DEC-124: a “+” at stroke 2 in the text's colour, hidden from screen readers, not the paperclip", async () => {
    const button = await render(createElement(AttachButton));
    const svg = button.querySelector("svg")!;
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(svg.getAttribute("viewBox")).toBe("0 0 24 24");
    expect(svg.getAttribute("fill")).toBe("none");
    expect(svg.getAttribute("stroke")).toBe("currentColor");
    expect(svg.getAttribute("stroke-width")).toBe("2");
    expect(svg.getAttribute("stroke-linecap")).toBe("round");
    const paths = Array.from(svg.querySelectorAll("path")).map((p) => p.getAttribute("d"));
    expect(paths).toEqual(["M12 5v14M5 12h14"]);
  });

  it("F-SPACE.targets, DEC-124: its target is 44px, the size of the mic beside it in the tool row", () => {
    const plus = el("button", "attach-btn", {}, "cz");
    const mic = el("button", "mic2", {}, "cz");
    for (const prop of ["width", "height"]) {
      expect(token(applied(COMPONENTS, plus, prop, 1440)), prop).toBe("44px");
      expect(token(applied(COMPONENTS, plus, prop, 360)), `${prop} on a phone`).toBe("44px");
      expect(token(applied(COMPOSE, mic, prop, 1440)), `the mic's ${prop}`).toBe("44px");
    }
  });

  it("C-PROMPT.anatomy/2, DEC-124: the tool row's look: no fill in --ink2 at rest, the mic's hover fill and ring, ink when open", () => {
    const plus = el("button", "attach-btn", {}, "cz");
    const mic = el("button", "mic2", {}, "cz");
    for (const prop of ["background", "color", "border-radius"])
      expect(applied(COMPONENTS, plus, prop, 1440), prop).toBe(applied(COMPOSE, mic, prop, 1440));
    expect(rule(COMPONENTS, ".attach-btn:hover").get("background")).toBe(
      rule(COMPOSE, ".cz .mic2:hover").get("background"),
    );
    expect(rule(COMPONENTS, ".attach-btn:focus-visible").get("outline")).toBe(
      rule(COMPOSE, ".cz :is(.mic2, .send):focus-visible").get("outline"),
    );
    expect(rule(COMPONENTS, ".attach-btn:active").get("transform")).toBe("scale(0.94)");
    const open = rule(COMPONENTS, '.attach-btn[aria-expanded="true"]');
    expect(open.get("background")).toBe("var(--ink)");
    expect(contrast(open.get("color")!, open.get("background")!)).toBeGreaterThanOrEqual(4.5);
    // WCAG 1.4.11: the "+" stands out from the prompt box's white glass at rest
    expect(contrast(applied(COMPONENTS, plus, "color", 1440)!, "var(--card)")).toBeGreaterThanOrEqual(3);
  });

  it("C-PROMPT.anatomy/2, DEC-124: aria-expanded and aria-controls pass through, and a click calls onClick", async () => {
    const onClick = vi.fn();
    const button = await render(
      createElement(AttachButton, {
        onClick,
        "aria-expanded": true,
        "aria-controls": "picker",
        className: "cz-attach",
      }),
    );
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(button.getAttribute("aria-controls")).toBe("picker");
    expect(button.className).toBe("attach-btn cz-attach");
    await click(button);
    expect(onClick).toHaveBeenCalledTimes(1);

    const closed = await render(createElement(AttachButton, { "aria-expanded": false }));
    expect(closed.getAttribute("aria-expanded")).toBe("false");
  });

  it("C-BUTTON.states/4, DEC-124: switched off, it is aria-disabled, stays focusable and a click does nothing", async () => {
    const onClick = vi.fn();
    const button = await render(createElement(AttachButton, { onClick, disabled: true }));
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(button.hasAttribute("disabled")).toBe(false);
    button.focus();
    expect(document.activeElement).toBe(button);
    const e = await click(button);
    expect(onClick).not.toHaveBeenCalled();
    expect(e.defaultPrevented).toBe(true);
  });
});
