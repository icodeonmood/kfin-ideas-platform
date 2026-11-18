/**
 * S-06 after lane G's 23:00 walk (BLD-E060, BLD-E062). The dark card clips its glow without being a scroll box, so
 * focusing a line an action adds can't scroll its pill and title away (S-06.layout/2; J-REVIEW/6, J-RECOVER/15).
 * Attached: a link's badge reads "Link", a folder's "Folder", a file's its type, never a word cut from an address;
 * and the tile wraps a long name inside the list's column (C-FILE.row; J-RECOVER/14). Synthetic people only.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), replace: vi.fn(), push: vi.fn() }),
  useParams: () => ({ id: "IDEA-2026-000014" }),
  usePathname: () => "/ideas/IDEA-2026-000014",
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));
vi.mock("@/lib/motion/spark", () => ({ sparkBurst: vi.fn() }));
vi.mock("@/components/teamup/teamup-sheet", async (actual) => ({
  ...(await actual<typeof import("@/components/teamup/teamup-sheet")>()),
  useTeamUpSheet: () => ({ open: vi.fn(), close: vi.fn(), isOpen: false, sheet: null }),
}));

const { SharerScreen, fileTileBadge } = await import("@/app/ideas/[id]/sharer-screen");
type Props = Parameters<typeof SharerScreen>[0];

const REF = "IDEA-2026-000014";
const NEHA = { id: "p-n", name: "Neha Joshi", first_name: "Neha", initials: "NJ" };
const LINK_URL = "https://intranet.kfintech.example/branch-notes/redemption-holds-for-the-west-zone-review";

function file(id: string, kind: "file" | "link" | "folder", name: string, extra: Record<string, unknown> = {}) {
  return { id, kind, name, type: "", state: "checked", added_by: NEHA, added_at: "2026-11-16T06:00:00Z", ...extra };
}

const FILES = [
  file("ATT-1", "link", LINK_URL, { link_scope: "internal" }),
  file("ATT-2", "folder", "Branch notes", { count: 6 }),
  file("ATT-3", "file", "Redemption holds.pdf", { size: 1_200_000, pages: 3, view_url: "/api/files/ATT-3/view" }),
  file("ATT-4", "file", "Screenshot 16 Nov.jpeg", { size: 240_000 }),
  file("ATT-5", "file", "Holds notes.txt", { size: 4_000 }),
];

function props(): Props {
  return {
    view: {
      view: "sharer",
      screen: "S-06",
      idea: {
        id: REF,
        ref: REF,
        title: "Redemptions on hold need a reason the investor can read",
        status: "shared",
        stages: [{ stage: "shared", state: "now", detail: "" }],
        own_words: [],
        hidden: [],
        files: FILES,
        has_open_questions: false,
        kept_separate: false,
      },
      page: {
        state: "shared",
        state_label: "",
        pill: { status: "shared", label: "Shared", variant: "blue" },
        breadcrumb: { label: "My ideas", to: "/my-ideas", current: REF },
        shared_label: null,
        first_arrival: false,
        card: null,
        card_from: null,
        window: null,
        actions: {},
        lane_b: { question_set: "", decision: "" },
        shared: {
          intro: "",
          rows: [],
          hidden: { chips: [], more: 0, note: "", all: [] },
          attached: { label: "Attached", files: FILES, answers: [] },
          fix: { label: "Your fix", answers: [] },
        },
        conversation: null,
        similar: { heading: "", intro: "", tiles: [] },
        merged: null,
        own_words_unmasked: false,
      },
    },
    decision: null,
    questions: null,
    partFailed: false,
  } as unknown as Props;
}

const css = () =>
  readFileSync(resolve(__dirname, "../../src/app/ideas/[id]/idea-page.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");

/** The body of the first rule for `selector`. */
function rule(sheet: string, selector: string): string {
  const esc = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?:^|[}\\s])${esc} \\{([^}]*)\\}`).exec(sheet)?.[1] ?? "";
}

describe("S-06.layout/2: the dark card clips without scrolling (BLD-E060; J-REVIEW/6, J-RECOVER/15)", () => {
  it("S-06.layout/2: overflow is clip, with hidden only as the fallback before it", () => {
    const card = rule(css(), ".ip-card");
    expect(card).toMatch(/overflow: hidden;\s*overflow: clip;/);
    // The last overflow wins; no later rule makes the card a scroll box again
    const all = [...css().matchAll(/(?:^|[}\s])\.ip-card \{([^}]*)\}/g)].map((m) => m[1]);
    for (const body of all.slice(1)) expect(body).not.toMatch(/overflow(?:-[xy])?:/);
    expect(card).toMatch(/border-radius: 28px;/);
    expect(card).toMatch(/isolation: isolate;/);
  });
});

describe("C-FILE.row on S-06 Attached (BLD-E062; J-RECOVER/14, J-RECOVER/15)", () => {
  it("C-FILE.row: a link reads Link, a folder Folder, a file its type, an unlisted type File", () => {
    expect(fileTileBadge({ kind: "link", name: LINK_URL })).toBe("Link");
    expect(fileTileBadge({ kind: "link", name: "https://wiki.example" })).toBe("Link");
    expect(fileTileBadge({ kind: "folder", name: "Branch notes" })).toBe("Folder");
    expect(fileTileBadge({ kind: "file", name: "Redemption holds.pdf" })).toBe("PDF");
    expect(fileTileBadge({ kind: "file", name: "Screenshot 16 Nov.jpeg" })).toBe("JPG");
    expect(fileTileBadge({ kind: "file", name: "Holds notes.txt" })).toBe("File");
    expect(fileTileBadge({ kind: "file", name: "no ending" })).toBe("File");
  });

  it("C-FILE.row: the rendered tiles carry those badges, and no badge is cut from an address", () => {
    const html = renderToStaticMarkup(createElement(SharerScreen, props()));
    const badges = [...html.matchAll(/<span class="ip-badge" aria-hidden="true">([^<]*)<\/span>/g)].map((m) => m[1]);
    expect(badges).toEqual(["Link", "Folder", "PDF", "JPG", "File"]);
    expect(html).not.toMatch(/>EXAM<|>HTTP<|>BRAN</);
    expect(html).toContain(`<span class="ip-file-n">${LINK_URL}</span>`);
  });

  it("C-FILE.row: the tile stays inside the list's column and a long name wraps", () => {
    const sheet = css();
    expect(rule(sheet, ".ip-files")).toMatch(/grid-template-columns: minmax\(0, 1fr\);/);
    expect(rule(sheet, ".ip-file")).toMatch(/min-width: 0;/);
    expect(rule(sheet, ".ip-file-t")).toMatch(/min-width: 0;/);
    const name = rule(sheet, ".ip-file-n");
    expect(name).toMatch(/overflow-wrap: anywhere;/);
    expect(name).not.toMatch(/white-space: nowrap/);
  });
});
