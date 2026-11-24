// @vitest-environment jsdom
/**
 * C-FILE.row, BLD-D030: the conversation box's compact rows (Messages.md `.cvfile`) are lane D's FileList `compact`
 * with FileRemove, styled in the shared sheet, so S-08 sets only their place; FileList's `live` lets a screen with its
 * own status line drop the list's aria-live (the prompt box's files, BLD-C224). Synthetic file names only.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FileList, FileRemove, FileRow } from "@/components/ui/file";
import { ConvoFileRows } from "@/components/convo/attach";

import { cssRules, SRC } from "./helpers/css-rules";

function draw(node: Parameters<typeof renderToStaticMarkup>[0]): HTMLElement {
  const box = document.createElement("div");
  box.innerHTML = renderToStaticMarkup(node);
  return box;
}
const row = (name: string, message?: { kind: "error" | "warn"; text: string }) =>
  h(FileRow, { key: name, name, status: "checked", statusText: "Checked", ...(message ? { message } : {}) });

describe("C-FILE.row, BLD-D030: FileList's live and compact, FileRow's message class, FileRemove", () => {
  it("a list announces changes politely by default; live={false} drops it and keeps the name and role", () => {
    const live = draw(h(FileList, { label: "Your files", children: row("a.md") })).querySelector("ul")!;
    expect(live.getAttribute("aria-live")).toBe("polite");
    const quiet = draw(
      h(FileList, { label: "Files in your box", live: false, children: row("a.md") }),
    ).querySelector("ul")!;
    expect(quiet.hasAttribute("aria-live")).toBe(false);
    expect(quiet.getAttribute("aria-label")).toBe("Files in your box");
    expect(quiet.getAttribute("role")).toBe("list");
    expect(quiet.className).toBe("flist");
  });

  it("compact adds the class; a row with a message under it is named frow-msg, so it takes its own line without :has()", () => {
    const box = draw(
      h(FileList, {
        label: "Your files",
        compact: true,
        children: [row("a.md"), row("b.png", { kind: "error", text: "Too big. Files can be up to 15 MB." })],
      }),
    );
    expect(box.querySelector("ul")!.className).toBe("flist compact");
    const [plain, msg] = [...box.querySelectorAll("li")];
    expect(plain!.className).toBe("frow frow-checked");
    expect(msg!.className).toBe("frow frow-checked frow-msg");
  });

  it("FileRemove is a named round button with the close icon, not a submit", () => {
    const b = draw(h(FileRemove, { label: "Remove a.md", onClick: () => undefined })).querySelector(
      "button",
    )!;
    expect(b.type).toBe("button");
    expect(b.className).toBe("frow-x");
    expect(b.getAttribute("aria-label")).toBe("Remove a.md");
    expect(b.getAttribute("title")).toBe("Remove a.md");
    expect(b.querySelector("svg")).not.toBeNull();
  });
});

describe("S-08, C-PROMPT.attach, BLD-D030: the conversation box and the prompt box use the shared list", () => {
  it("S-08's box files are a compact list with FileRemove on each row, named Remove {name}", () => {
    const box = draw(
      h(ConvoFileRows, {
        rows: [
          { key: "k1", item: null, name: "branch-notes.md", localState: "uploading" },
          { key: "k2", item: null, name: "rejection-sms-screens.png", localState: "too_big" },
        ],
        limitMb: 15,
        onRetry: () => undefined,
        onRemove: () => undefined,
      }),
    );
    const list = box.querySelector(".cv-files > ul.flist.compact")!;
    expect(list).not.toBeNull();
    expect(list.getAttribute("aria-live")).toBe("polite");
    const removes = [...list.querySelectorAll("button.frow-x")].map((b) => b.getAttribute("aria-label"));
    expect(removes).toEqual(["Remove branch-notes.md", "Remove rejection-sms-screens.png"]);
    expect(list.querySelector(".cv-file-x")).toBeNull();
    expect(list.querySelectorAll("li.frow-msg")).toHaveLength(1);
  });

  it("the prompt box's rows are lane D's FileList without aria-live, its status line saying what changed (BLD-C224)", () => {
    const src = readFileSync(resolve(SRC, "app/share/box-files.tsx"), "utf8");
    expect(src).toMatch(/<FileList label=\{BOX_FILES_COPY\.rows\} live=\{false\}>/);
    expect(src).not.toMatch(/<ul className="flist"/);
  });
});

describe("C-FILE.row, BLD-D030: the compact rows are styled in the shared sheet, and S-08 sets only their place", () => {
  const shared = cssRules("app/components.css");
  const decl = (selector: string, prop: string, at = "") =>
    shared.find((r) => r.at === at && r.selectors.includes(selector) && r.decls.has(prop))?.decls.get(prop);

  it("as S-08 drew them: rows that wrap, 260px at most, a row with a message on its own line, one line on a phone", () => {
    expect(decl(".flist.compact", "display")).toBe("flex");
    expect(decl(".flist.compact", "flex-wrap")).toBe("wrap");
    expect(decl(".flist.compact > .frow", "flex")).toBe("0 1 260px");
    expect(decl(".flist.compact > .frow-msg", "flex-basis")).toBe("100%");
    expect(decl(".flist.compact .frow-n", "text-overflow")).toBe("ellipsis");
    expect(decl(".flist.compact .frow-in", "flex-wrap", "@media (max-width: 640px)")).toBe("nowrap");
    expect(decl(".flist.compact .frow-a", "width", "@media (max-width: 640px)")).toBe("auto");
  });

  it("F-SPACE.targets: FileRemove is 32px, its focus ring 2px blue, and padded to 44px on touch", () => {
    expect(decl(".frow-x", "width")).toBe("32px");
    expect(decl(".frow-x", "height")).toBe("32px");
    expect(decl(".frow-x:focus-visible", "outline")).toBe("2px solid var(--blue)");
    const inset = (decl(".frow-x::after", "inset", "@media (pointer: coarse)") ?? "")
      .split(" ")
      .map(parseFloat);
    expect(inset).toEqual([-6, -8, -6, -4]);
    expect(32 - inset[0]! - inset[2]!).toBeGreaterThanOrEqual(44);
    expect(32 - inset[1]! - inset[3]!).toBeGreaterThanOrEqual(44);
  });

  it("conversation.css no longer restyles the shared row's insides or keeps its own remove button", () => {
    const convo = cssRules("components/convo/conversation.css");
    const selectors = convo.flatMap((r) => r.selectors);
    expect(selectors.filter((s) => /\.cv-files \.(flist|frow|fbadge)|\.cv-file-x/.test(s))).toEqual([]);
    expect(selectors).toContain(".cv-files");
  });
});
