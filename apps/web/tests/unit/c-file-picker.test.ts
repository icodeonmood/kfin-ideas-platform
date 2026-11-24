// @vitest-environment jsdom
/**
 * C-FILE.uploader, BLD-D031: lane D's one picker for the prompt box (lane C's box-files, `cpick`) and the conversation
 * box (lane F's ConvoPicker, `cv-pick`). The four controls in order with both file inputs `hidden` (S-08's focus carry,
 * BLD-F098), the focus on opening (or not), Escape, links taken at once or answered, a controlled link field, a dropped
 * folder read through its entries or the note to use "Choose a folder", and the look in the shared sheet only.
 * Synthetic file names only.
 */
import { act, createElement as h } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  FilePicker,
  NO_LINK,
  PICKER_COPY,
  type LinkDraft,
  type LinksAnswer,
} from "@/components/ui/file-picker";

import { cssRules } from "./helpers/css-rules";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

/** S-08's list of controls (conversation.tsx `CONTROLS`), which its focus carry counts by index. */
const CONTROLS = "button:not([disabled]), input:not([hidden]):not([disabled])";

let host: HTMLElement;
let root: Root;
beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});
afterEach(() => {
  act(() => root.unmount());
  host.remove();
});

type Props = Parameters<typeof FilePicker>[0];
const base = (more: Partial<Props> = {}): Props => ({
  id: "pick-1",
  className: "cpick",
  help: "PDF or images, up to 15 MB each.",
  onFiles: vi.fn(),
  onLinks: vi.fn(),
  onClose: vi.fn(),
  ...more,
});
const show = (p: Props) => act(() => root.render(h(FilePicker, p)));
const pick = () => host.querySelector<HTMLElement>(".fpick")!;
const field = () => host.querySelector<HTMLInputElement>("input[type=url]")!;
const named = (name: string) => [...host.querySelectorAll("button")].find((b) => b.textContent === name)!;
const flush = () => act(async () => await Promise.resolve());
function type(value: string) {
  const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
  act(() => {
    set.call(field(), value);
    field().dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("C-FILE.uploader, BLD-D031: one picker, as both boxes drew it", () => {
  it("the root keeps the screen's id and class; the controls are Choose a folder, browse, the link field and Add link, in that order, with both file inputs hidden", () => {
    show(base({ className: "cv-pick" }));
    expect(pick().id).toBe("pick-1");
    expect(pick().className).toBe("fpick cv-pick");
    const controls = [...pick().querySelectorAll<HTMLElement>(CONTROLS)].map(
      (c) => c.getAttribute("aria-label") ?? c.getAttribute("placeholder") ?? c.textContent,
    );
    expect(controls).toEqual([
      PICKER_COPY.folder,
      PICKER_COPY.browse,
      PICKER_COPY.linkInput,
      PICKER_COPY.addLink,
    ]);
    const inputs = [...pick().querySelectorAll<HTMLInputElement>("input[type=file]")];
    expect(inputs.map((i) => i.hidden)).toEqual([true, true]);
    expect(inputs.filter((i) => i.hasAttribute("webkitdirectory"))).toHaveLength(1);
    expect(pick().querySelector("input[type=file]:not([webkitdirectory])")).not.toBeNull();
    expect(pick().textContent).toContain(`PDF or images, up to 15 MB each. ${PICKER_COPY.folderLine}`);
  });

  it("WCAG 2.4.3: it opens with the focus on Choose a folder (Home); with autoFocus off the screen keeps it (S-08)", () => {
    show(base());
    expect(document.activeElement).toBe(host.querySelector(".fpick-folder"));
    act(() => root.render(null));
    (document.activeElement as HTMLElement | null)?.blur();
    show(base({ autoFocus: false }));
    expect(document.activeElement).not.toBe(host.querySelector(".fpick-folder"));
  });

  it("Escape anywhere inside closes it, and goes no further", () => {
    const p = base();
    show(p);
    const ev = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
    const outer = vi.fn();
    document.addEventListener("keydown", outer);
    act(() => field().dispatchEvent(ev));
    document.removeEventListener("keydown", outer);
    expect(p.onClose).toHaveBeenCalledOnce();
    expect(ev.defaultPrevented).toBe(true);
    expect(outer).not.toHaveBeenCalled();
  });

  it("not a link: the board's line under the field, marked and described; a link taken at once clears the field", () => {
    const p = base({ linkHelp: PICKER_COPY.linkLine });
    show(p);
    type("not a link");
    act(() => named(PICKER_COPY.addLink).click());
    expect(p.onLinks).not.toHaveBeenCalled();
    expect(field().getAttribute("aria-invalid")).toBe("true");
    const said = (field().getAttribute("aria-describedby") ?? "").split(" ");
    expect(said).toHaveLength(2);
    expect(host.querySelector(`[id="${said[0]}"]`)!.textContent).toContain("doesn");
    expect(host.querySelector(`[id="${said[1]}"]`)!.textContent).toBe(PICKER_COPY.linkLine);
    type("intranet.kfintech.com/branch-notes");
    expect(field().hasAttribute("aria-invalid")).toBe(false);
    act(() => named(PICKER_COPY.addLink).click());
    expect(p.onLinks).toHaveBeenCalledWith(
      ["https://intranet.kfintech.com/branch-notes"],
      "intranet.kfintech.com/branch-notes",
    );
    expect(field().value).toBe("");
  });

  it("links answered later (Home): Add link is busy meanwhile; those left stay in the field, with the failed line", async () => {
    let answer: (v: LinksAnswer) => void = () => undefined;
    const p = base({ onLinks: vi.fn(() => new Promise<LinksAnswer>((ok) => (answer = ok))) });
    show(p);
    type("intranet.kfintech.com/a, intranet.kfintech.com/b");
    act(() => named(PICKER_COPY.addLink).click());
    expect(named(PICKER_COPY.addLink).getAttribute("aria-busy")).toBe("true");
    await act(async () => answer({ left: ["https://intranet.kfintech.com/b"], problem: "failed" }));
    expect(named(PICKER_COPY.addLink).hasAttribute("aria-busy")).toBe(false);
    expect(field().value).toBe("intranet.kfintech.com/b");
    expect(pick().querySelectorAll(".fmsg")).toHaveLength(1);
  });

  it("BLD-F102: a field the screen keeps shows its words and hands every change back", () => {
    const changes: LinkDraft[] = [];
    show(base({ link: { text: "teams.microsoft.com/x", bad: false }, onLinkDraft: (d) => changes.push(d) }));
    expect(field().value).toBe("teams.microsoft.com/x");
    type("teams.microsoft.com/xy");
    expect(changes.at(-1)).toEqual({ text: "teams.microsoft.com/xy", bad: false });
    act(() => named(PICKER_COPY.addLink).click());
    expect(changes.at(-1)).toEqual(NO_LINK);
  });
});

describe("C-FILE.uploader/2, BLD-C224, BLD-D031: a dropped folder", () => {
  type Entry = Record<string, unknown>;
  const pdf = (name: string) => new File(["%PDF"], name, { type: "application/pdf" });
  const fileEntry = (f: File): Entry => ({
    isFile: true,
    isDirectory: false,
    file: (ok: (f: File) => void) => ok(f),
  });
  const dirEntry = (children: Entry[]): Entry => ({
    isFile: false,
    isDirectory: true,
    createReader: () => {
      let read = false;
      return {
        readEntries: (ok: (es: Entry[]) => void) => {
          ok(read ? [] : children);
          read = true;
        },
      };
    },
  });
  const drop = async (items: unknown[]) => {
    await act(async () => {
      const ev = new Event("drop", { bubbles: true, cancelable: true });
      Object.defineProperty(ev, "dataTransfer", { value: { items, files: [] } });
      pick().dispatchEvent(ev);
    });
    for (let i = 0; i < 4; i++) await flush();
  };

  it("every file in it, nested folders too, goes to the screen's onFiles (which leaves out dot files)", async () => {
    const p = base({ className: "cv-pick", autoFocus: false });
    show(p);
    const folder = dirEntry([
      fileEntry(pdf("Week 47 call log.pdf")),
      dirEntry([fileEntry(pdf("Week 48 call log.pdf"))]),
    ]);
    await drop([
      { kind: "file", getAsFile: () => new File([], "Branch notes"), webkitGetAsEntry: () => folder },
    ]);
    expect(p.onFiles).toHaveBeenCalledOnce();
    expect((p.onFiles as ReturnType<typeof vi.fn>).mock.calls[0]![0].map((f: File) => f.name)).toEqual([
      "Week 47 call log.pdf",
      "Week 48 call log.pdf",
    ]);
  });

  it("with no directory entries a folder is an empty file with no type: never handed on; the picker says to use Choose a folder (its own line on S-08, the screen's on Home)", async () => {
    const p = base({ className: "cv-pick", autoFocus: false });
    show(p);
    await drop([
      { kind: "file", getAsFile: () => new File([], "Branch notes") },
      { kind: "file", getAsFile: () => pdf("Week 47 call log.pdf") },
    ]);
    expect((p.onFiles as ReturnType<typeof vi.fn>).mock.calls[0]![0].map((f: File) => f.name)).toEqual([
      "Week 47 call log.pdf",
    ]);
    expect(pick().textContent).toContain(PICKER_COPY.useFolder);
    const onNote = vi.fn();
    show(base({ note: null, onNote }));
    await drop([{ kind: "file", getAsFile: () => new File([], "Branch notes") }]);
    expect(onNote.mock.calls.map((c) => c[0])).toEqual([null, PICKER_COPY.useFolder]);
  });
});

describe("C-FILE.uploader, BLD-D031: the look is the shared sheet's; each screen sets only its place", () => {
  const shared = cssRules("app/components.css");
  const decl = (selector: string, prop: string) =>
    shared.find((r) => r.at === "" && r.selectors.includes(selector) && r.decls.has(prop))?.decls.get(prop);

  it("the picker, the folder button over the drop area, and the link field with its icon, as both boxes drew them", () => {
    expect(decl(".fpick", "padding")).toBe("12px");
    expect(decl(".fpick", "box-shadow")).toBe("inset 0 0 0 1px var(--rule2)");
    expect(decl(".fpick-drop .fdrop", "padding-top")).toBe("64px");
    expect(decl(".fpick-folder", "width")).toBe("44px");
    expect(decl(".fpick-folder", "height")).toBe("44px");
    expect(decl(".fpick-folder:focus-visible", "outline")).toBe("2px solid var(--blue)");
    expect(decl(".fpick-link .fld", "padding-left")).toBe("38px");
    expect(decl(".fpick-h", "font-size")).toBe("12.5px");
  });

  it("compose.css and conversation.css keep the picker's place only", () => {
    const compose = cssRules("app/share/compose.css");
    const convo = cssRules("components/convo/conversation.css");
    const all = [...compose, ...convo].flatMap((r) => r.selectors);
    expect(all.filter((s) => /\.(cpick|cv-pick)-/.test(s))).toEqual([]);
    const own = (rules: typeof compose, sel: string) =>
      rules.filter((r) => r.selectors.includes(sel)).flatMap((r) => [...r.decls.keys()]);
    expect(own(compose, ".cz .cpick")).toEqual(["margin"]);
    expect(new Set(own(convo, ".cv-pick"))).toEqual(new Set(["grid-area", "margin"]));
  });
});
