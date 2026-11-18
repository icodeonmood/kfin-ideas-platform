/**
 * J-SIMILAR/6a, L-MERGE.request/5 (BLD-C155): a draft merged into another idea opens on Check it (S-05), read-only,
 * whether it is opened at `/share/:id` (Tell it) or at `/share/:id/done`; it never reaches Done. A plain draft and a
 * shared idea go where they went before. `isMergedDraft` reads only the person's own row. Synthetic ids only.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  me: { id: "u-tanvi", name: "Tanvi Deshmukh", contributorCode: "CTR-0a1b2c" } as unknown,
  merged: false,
  stage: "draft",
  row: null as null | Record<string, unknown>,
}));

vi.mock("next/navigation", () => ({
  redirect: (to: string) => {
    throw new Error(`redirect ${to}`);
  },
  notFound: () => {
    throw new Error("not found");
  },
}));
vi.mock("next/link", () => ({ default: () => null }));
vi.mock("@/server/auth/current", () => ({ currentUser: async () => state.me }));
vi.mock("@/server/drafts", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/server/drafts")>()),
  isMergedDraft: async () => state.merged,
}));
vi.mock("@/server/submissions", () => ({
  SubmissionError: class extends Error {},
  getDraft: async () => ({ id: DRAFT, stage: state.stage, idea_id: "IDEA-2026-001412" }),
}));
vi.mock("@/server/scan", () => ({ scanStatus: async () => null }));
vi.mock("@/app/share/compose", () => ({ Compose: () => null }));
vi.mock("@/app/share/[id]/done/scan-status", () => ({ ScanStatus: () => null }));
vi.mock("@/server/db", () => ({
  getDb: () => ({
    selectFrom: () => ({
      select: () => ({ where: () => ({ executeTakeFirst: async () => state.row }) }),
    }),
  }),
}));

const DRAFT = "0b6f7a52-3c1e-4d7a-9f00-1a2b3c4d5e6f";
const params = Promise.resolve({ id: DRAFT });

const { default: TellIt } = await import("@/app/share/[id]/page");
const { default: Done } = await import("@/app/share/[id]/done/page");
const { isMergedDraft } = await vi.importActual<typeof import("@/server/drafts")>("@/server/drafts");

beforeEach(() => {
  state.merged = false;
  state.stage = "draft";
});

describe("J-SIMILAR/6a: a merged draft goes to Check it, never to Done (BLD-C155)", () => {
  it("/share/:id sends a merged draft to /share/:id/check; a plain draft stays on Tell it", async () => {
    state.merged = true;
    await expect(TellIt({ params })).rejects.toThrow(`redirect /share/${DRAFT}/check`);
    state.merged = false;
    const el = await TellIt({ params });
    expect(el.props).toMatchObject({ draftId: DRAFT, firstName: "Tanvi" });
  });

  it("/share/:id/done sends a merged draft to /share/:id/check; a draft still goes back to Tell it, a sent idea stays", async () => {
    state.merged = true;
    await expect(Done({ params })).rejects.toThrow(`redirect /share/${DRAFT}/check`);
    state.merged = false;
    await expect(Done({ params })).rejects.toThrow(new RegExp(`^redirect /share/${DRAFT}$`));
    state.stage = "scanning";
    await expect(Done({ params })).resolves.toBeTruthy();
  });
});

describe("isMergedDraft (BLD-C155)", () => {
  const me = state.me as Parameters<typeof isMergedDraft>[0];

  it("is true only for the person's own draft closed as merged, with no reference of its own", async () => {
    state.row = { status: "merged", idea_id: null, contributor_code: "CTR-0a1b2c" };
    expect(await isMergedDraft(me, DRAFT)).toBe(true);
    state.row = { status: "merged", idea_id: null, contributor_code: "CTR-ffffff" };
    expect(await isMergedDraft(me, DRAFT)).toBe(false); // someone else's
    state.row = { status: "merged", idea_id: "IDEA-2026-001398", contributor_code: "CTR-0a1b2c" };
    expect(await isMergedDraft(me, DRAFT)).toBe(false); // a shared idea the desk merged keeps its own page
    state.row = { status: "draft", idea_id: null, contributor_code: "CTR-0a1b2c" };
    expect(await isMergedDraft(me, DRAFT)).toBe(false);
    state.row = null;
    expect(await isMergedDraft(me, DRAFT)).toBe(false);
    expect(await isMergedDraft(me, "not-a-draft-id")).toBe(false);
  });
});
