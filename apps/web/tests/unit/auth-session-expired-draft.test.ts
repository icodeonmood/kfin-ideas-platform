/**
 * A-API.auth `GET /auth/session` → 401 `expired` with the open draft (S-02.states Session expired mid-draft,
 * L-AUTH.rules/5, BLD-A227): the draft's `saved_on` is E-ENTITIES.draft's `{ device, this_device }`, read from the
 * asking browser's side by its device id, as L-DRAFT's own reads say it. Synthetic ids only.
 */
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/server/auth/session", async (original) => ({
  ...(await original<typeof import("@/server/auth/session")>()),
  readSession: vi.fn(async () => null),
  expiredSession: vi.fn(async () => ({
    userId: "00000000-0000-4000-8000-0000000000a1",
    email: "asha.rao@kfintech.com",
  })),
}));
vi.mock("@/server/shell", () => ({
  askingDevice: vi.fn(async () => ({ kind: "laptop", id: "laptopdevice01" })),
}));

import { GET } from "@/app/auth/session/route";
import { pgDraftLookup, savedOn, setDraftLookup, type DraftCard } from "@/server/auth/drafts";

const DRAFT = "a1b2c3d4-0000-4000-8000-000000000001";
const asked: (string | null | undefined)[] = [];

function lookupSavedBy(device: "laptop" | "phone" | null, savedId: string | null) {
  setDraftLookup({
    async card(_owner, draftId, askingId) {
      asked.push(askingId);
      const card: DraftCard = {
        id: draftId,
        title: "Distributors can’t see why an SIP registration is stuck",
        savedAt: new Date("2026-11-20T04:11:00Z"),
        savedOn: savedOn(device, savedId, askingId ?? null),
        step: "tell",
        keptLine: null,
      };
      return card;
    },
  });
}

async function expiredDraft(): Promise<Record<string, unknown>> {
  const res = await GET(
    new NextRequest(new URL(`/auth/session?draft=/share/${DRAFT}`, "http://localhost:3000"), {
      headers: { cookie: "ideas_session=expiredtoken01" },
    }),
  );
  expect(res.status).toBe(401);
  const body = (await res.json()) as { error: string; draft?: Record<string, unknown> };
  expect(body.error).toBe("expired");
  return body.draft!;
}

describe("A-API.auth GET /auth/session expired: the draft's saved_on (S-02, BLD-A227)", () => {
  beforeEach(() => {
    asked.length = 0;
  });
  afterEach(() => setDraftLookup(pgDraftLookup));

  it("is this device when this browser saved it, and the lookup is asked with the browser's device id", async () => {
    lookupSavedBy("laptop", "laptopdevice01");
    const draft = await expiredDraft();
    expect(asked).toEqual(["laptopdevice01"]);
    expect(draft.saved_on).toEqual({ device: "laptop", this_device: true });
  });

  it("is not this device when a phone saved it, the contract's shape and never a bare device word", async () => {
    lookupSavedBy("phone", "phonedevice001");
    const draft = await expiredDraft();
    expect(draft.saved_on).toEqual({ device: "phone", this_device: false });
  });

  it("is left out when the draft does not say where it was saved", async () => {
    lookupSavedBy(null, null);
    const draft = await expiredDraft();
    expect(draft).not.toHaveProperty("saved_on");
    expect(draft).toMatchObject({ id: DRAFT, step: "tell" });
  });
});
