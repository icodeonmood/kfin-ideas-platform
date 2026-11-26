/**
 * Capture first's trigger (DEC-125, BLD-C212; pinned by BLD-C224; DEC-143 (g), BLD-B281): `captureFirstOn()` in
 * server/drafts.ts is true exactly when `ai.all` or `agent.draft-part` is not "on" in the switch table, read as the
 * "The assistant is taking a break" banner reads it (components/banners.tsx: a missing row counts as off, as the
 * worker's `killswitch.is_on`). Nothing else turns it on: another switch off, with both on, keeps Full mode, and a
 * table that cannot be read keeps Full mode too. Both Share a problem pages (`/share` and
 * `/share/:id`) hand that answer to Compose as `captureFirst`. The switch table is mocked; synthetic ids only.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  me: { id: "u-kavya", name: "Kavya Menon", contributorCode: "CTR-0a1b2c" } as unknown,
  switches: new Map<string, string>() as Map<string, string> | null,
}));

vi.mock("next/navigation", () => ({
  redirect: (to: string) => {
    throw new Error(`redirect ${to}`);
  },
  notFound: () => {
    throw new Error("not found");
  },
}));
vi.mock("@/server/auth/current", () => ({ currentUser: async () => state.me }));
vi.mock("@/server/killswitch", () => ({
  switchStates: async () => {
    if (state.switches === null) throw new Error("the switch table cannot be read");
    return state.switches;
  },
}));
vi.mock("@/server/flag-events", () => ({
  composeFlags: async () => ({}),
  interviewPlace: async () => null,
}));
vi.mock("@/server/drafts", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/server/drafts")>()),
  isMergedDraft: async () => false,
}));
vi.mock("@/app/share/compose", () => ({ Compose: () => null }));

const DRAFT = "0b6f7a52-3c1e-4d7a-9f00-1a2b3c4d5e6f";

const { captureFirstOn } = await vi.importActual<typeof import("@/server/drafts")>("@/server/drafts");
const { default: TellIt } = await import("@/app/share/page");
const { default: TellItConversation } = await import("@/app/share/[id]/page");

const table = (rows: Record<string, string>) => new Map(Object.entries(rows));
const BOTH_ON = { "ai.all": "on", "agent.draft-part": "on" };

/** Each case: the switch table, and whether Capture first is on. */
const CASES: Array<[string, Map<string, string> | null, boolean]> = [
  [
    "ai.all and agent.draft-part on",
    table({ ...BOTH_ON, "agent.gatekeeper": "on", submissions: "on" }),
    false,
  ],
  ["ai.all off", table({ "ai.all": "off", "agent.draft-part": "on", "agent.gatekeeper": "on" }), true],
  ["no ai.all row (counts as off)", table({ "agent.draft-part": "on", "agent.gatekeeper": "on" }), true],
  [
    "agent.draft-part alone off",
    table({ "ai.all": "on", "agent.draft-part": "off", "agent.gatekeeper": "on" }),
    true,
  ],
  ["no agent.draft-part row (counts as off)", table({ "ai.all": "on", "agent.gatekeeper": "on" }), true],
  ["both off", table({ "ai.all": "off", "agent.draft-part": "off" }), true],
  ["an empty table (counts as off)", table({}), true],
  [
    "every other switch off, ai.all and agent.draft-part on",
    table({ ...BOTH_ON, "agent.gatekeeper": "off", "agent.canvas-assist": "off", submissions: "off" }),
    false,
  ],
  ["the table cannot be read", null, false],
];

beforeEach(() => {
  state.switches = table(BOTH_ON);
});

describe("DEC-125, DEC-143 (g): Capture first is ai.all or agent.draft-part off (BLD-C212, C224, B281)", () => {
  for (const [name, switches, on] of CASES) {
    it(`captureFirstOn() is ${on} when ${name}`, async () => {
      state.switches = switches;
      expect(await captureFirstOn()).toBe(on);
    });

    it(`/share and /share/:id give Compose captureFirst=${on} when ${name}`, async () => {
      state.switches = switches;
      const fresh = await TellIt({ searchParams: Promise.resolve({}) });
      expect(fresh.props).toMatchObject({ draftId: null, captureFirst: on });
      const resumed = await TellItConversation({ params: Promise.resolve({ id: DRAFT }) });
      expect(resumed.props).toMatchObject({ draftId: DRAFT, captureFirst: on });
    });
  }
});
