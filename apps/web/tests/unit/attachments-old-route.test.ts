import { afterEach, describe, expect, it, vi } from "vitest";

// The database is mocked: these tests are about which rows the old route (/api/attachments/:id and its status)
// still describes and serves (lane C review fix 3, A-API.files, DEC-107).
const row = vi.fn();
const chain: Record<string, unknown> = {};
for (const step of ["selectFrom", "innerJoin", "select", "where"]) chain[step] = () => chain;
chain.executeTakeFirst = () => Promise.resolve(row());
vi.mock("@/server/db", () => ({ getDb: () => chain }));
vi.mock("@/server/worker", () => ({ workerFetch: vi.fn() }));

const { accessible } = await import("@/server/attachments");

import type { CurrentUser } from "@/server/auth/current";

const owner = {
  id: "u-1",
  contributorCode: "CTR-0a1b2c",
  roles: new Set(["contributor"]),
} as unknown as CurrentUser;
const desk = {
  id: "u-2",
  contributorCode: "CTR-0d0e0f",
  roles: new Set(["reviewer"]),
} as unknown as CurrentUser;
const admin = {
  id: "u-3",
  contributorCode: "CTR-0a0a0a",
  roles: new Set(["admin"]),
} as unknown as CurrentUser;
const base = {
  id: "ATT-2026-000123",
  name: "branch-notes.pdf",
  bytes: "1024",
  state: "clean",
  rejection: null,
  mime: "application/pdf",
  contributor_code: "CTR-0a1b2c",
  stage: "scanned",
  file_state: null,
  answer_id: null,
};

afterEach(() => row.mockReset());

describe("A-API.files: the old /api/attachments route and the files pipeline", () => {
  it("still serves the old pipeline's clean file to its owner and the desk", async () => {
    row.mockReturnValue({ ...base });
    expect(await accessible(owner, base.id)).not.toBeNull();
    expect(await accessible(desk, base.id)).not.toBeNull();
  });

  it("refuses a checked file of the files pipeline, to everyone (it opens only through /api/files/:id/view)", async () => {
    row.mockReturnValue({ ...base, file_state: "checked" });
    for (const who of [owner, desk, admin]) expect(await accessible(who, base.id)).toBeNull();
  });

  it("refuses a file with a customer detail found, to everyone", async () => {
    row.mockReturnValue({ ...base, state: "quarantine", file_state: "personal_data_found" });
    for (const who of [owner, desk, admin]) expect(await accessible(who, base.id)).toBeNull();
  });

  it("refuses a checked file on an unsent answer, to the desk and admin as well as the sharer", async () => {
    row.mockReturnValue({ ...base, answer_id: "7d3f0c2a-1b2c-4d5e-8f90-123456789abc" });
    for (const who of [owner, desk, admin]) expect(await accessible(who, base.id)).toBeNull();
    row.mockReturnValue({
      ...base,
      file_state: "checked",
      answer_id: "7d3f0c2a-1b2c-4d5e-8f90-123456789abc",
    });
    for (const who of [owner, desk, admin]) expect(await accessible(who, base.id)).toBeNull();
  });

  it("refuses a link row of the files pipeline", async () => {
    row.mockReturnValue({ ...base, name: "example.org/report", mime: null, file_state: "ok" });
    expect(await accessible(owner, base.id)).toBeNull();
  });
});
