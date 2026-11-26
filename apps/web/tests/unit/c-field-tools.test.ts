// @vitest-environment jsdom
/**
 * C-FIELD with tools (BLD-D029, C-PROMPT.anatomy/2): the shared Field takes the field's own icon buttons at its
 * trailing end, inside its frame, as the Answer board draws the "+" and the mic in its field (S-R3 `.qfield`/`.qtools`).
 * The frame takes the field's border, fill and states and the control inside draws none; without tools the markup is
 * as before. Synthetic words only.
 */
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AttachButton } from "@/components/ui/attach-button";
import { Field } from "@/components/ui/field";

import { cssRules } from "./helpers/css-rules";

/** The Field as a browser would hold it. */
function draw(
  props: Partial<Parameters<typeof Field>[0]>,
  tag: "input" | "textarea" = "textarea",
): HTMLElement {
  const box = document.createElement("div");
  box.innerHTML = renderToStaticMarkup(
    h(Field, {
      label: "Your answer to question 1",
      ...props,
      children: (p) => h(tag, { ...p, placeholder: "Type your answer, or tap the mic and say it" }),
    }),
  );
  return box;
}
const plus = h(AttachButton, { label: "Attach files to this answer", tooltip: "Attach files" });

describe("C-FIELD, BLD-D029: a field's own tools sit inside its frame, after the control", () => {
  it("C-FIELD.anatomy: without tools the control follows its label straight in the field's wrapper, as before", () => {
    const box = draw({ multiline: true, help: "Press Enter to go on." });
    expect(box.querySelector(".fld-frame")).toBeNull();
    const wrap = box.querySelector(".fld-wrap")!;
    expect([...wrap.children].map((c) => c.tagName.toLowerCase())).toEqual(["label", "textarea", "p"]);
    expect(wrap.querySelector("textarea")!.className).toBe("fld textarea");
  });

  it('C-PROMPT.anatomy/2: with tools the frame holds the control and then the tools; the label still names the control, and the "+" keeps its own name', () => {
    const box = draw({ multiline: true, help: "Press Enter to go on.", tools: plus });
    const frame = box.querySelector<HTMLElement>(".fld-wrap > .fld-frame")!;
    expect(frame.className).toBe("fld-frame multi");
    const [control, tools] = [...frame.children];
    expect(control!.tagName).toBe("TEXTAREA");
    expect(control!.className).toBe("fld textarea");
    expect(box.querySelector("label")!.htmlFor).toBe(control!.id);
    expect(tools!.className).toBe("fld-tools");
    const button = tools!.querySelector("button")!;
    expect(button.getAttribute("aria-label")).toBe("Attach files to this answer");
    expect(button.getAttribute("title")).toBe("Attach files");
    // The help line stays under the frame and still describes the control
    const help = frame.nextElementSibling!;
    expect(help.className).toBe("help");
    expect(control!.getAttribute("aria-describedby")).toBe(help.id);
  });

  it("C-FIELD.states: an error marks the control invalid and the frame takes the invalid look; a one-line field centres its tools", () => {
    const bad = draw({ multiline: true, error: "Add a few more words.", tools: plus });
    expect(bad.querySelector(".fld-frame")!.className).toBe("fld-frame multi invalid");
    expect(bad.querySelector("textarea")!.getAttribute("aria-invalid")).toBe("true");
    const line = draw({ tools: plus }, "input");
    expect(line.querySelector(".fld-frame")!.className).toBe("fld-frame");
    expect(line.querySelector(".fld-frame > input.fld")).not.toBeNull();
  });
});

describe("C-FIELD, C-FIELD.states, BLD-D029: the frame draws the field and the control inside draws none", () => {
  const css = cssRules("app/components.css");
  const decl = (selector: string, prop: string) =>
    css
      .filter((r) => r.at === "" && r.selectors.includes(selector) && r.decls.has(prop))
      .at(-1)
      ?.decls.get(prop);
  const CONTROL = ".fld-frame > .fld";

  it("C-FIELD.anatomy/2: the frame has the field's border, radius and fill; a text area's tools sit at its foot", () => {
    expect(decl(".fld-frame", "border")).toBe("1px solid var(--fieldBorder)");
    expect(decl(".fld-frame", "border-radius")).toBe("var(--r-sm)");
    expect(decl(".fld-frame", "background")).toBe("var(--card)");
    expect(decl(".fld-frame", "display")).toBe("flex");
    expect(decl(".fld-frame.multi", "align-items")).toBe("flex-end");
    expect(decl(".fld-tools", "flex")).toBe("none");
    expect(decl(".fld-frame.multi > .fld-tools", "padding-bottom")).toBe("4px");
  });

  it("C-FIELD.states: focus anywhere in the frame gives the blue border and ring; an error gives the red ones", () => {
    expect(decl(".fld-frame:focus-within", "border-color")).toBe("var(--blue)");
    expect(decl(".fld-frame:focus-within", "box-shadow")).toBe("0 0 0 3px var(--focus-glow)");
    expect(decl(".fld-frame.invalid", "border-color")).toBe("var(--badT)");
    expect(decl(".fld-frame.invalid", "box-shadow")).toBe("0 0 0 3px var(--bad-glow)");
  });

  it("the control inside draws no border, fill or ring in any state, and its text starts where a field's without tools does (1px + 14px)", () => {
    for (const sel of [
      CONTROL,
      `${CONTROL}:focus`,
      `${CONTROL}[aria-invalid="true"]`,
      `${CONTROL}[readonly]`,
    ]) {
      expect(decl(sel, "border"), sel).toBe("0");
      expect(decl(sel, "background"), sel).toBe("transparent");
      expect(decl(sel, "box-shadow"), sel).toBe("none");
      expect(decl(sel, "padding"), sel).toBe("12px 0 12px 14px");
    }
    // The frame's 1px border plus the control's height is the field's own: 48px, or 112px for a text area
    expect(decl(CONTROL, "min-height")).toBe("calc(var(--ctl) - 2px)");
    expect(decl(".fld-frame > textarea.fld", "min-height")).toBe("110px");
  });
});
