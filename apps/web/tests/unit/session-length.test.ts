/**
 * L-AUTH.rules/5 (BLD-A178): a session lasts `session.hours` from rules/promises.md (8, KFintech policy) from sign-in,
 * and activity never carries it past that. The database is a Kysely dummy that records the SQL it is given.
 */
import { DummyDriver, Kysely, PostgresAdapter, PostgresIntrospector, PostgresQueryCompiler } from "kysely";
import type { CompiledQuery } from "kysely";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const queries: CompiledQuery[] = [];
const promises = vi.fn();

vi.mock("@/server/db", () => {
  const db = new Kysely<never>({
    dialect: {
      createAdapter: () => new PostgresAdapter(),
      createDriver: () => new DummyDriver(),
      createIntrospector: (k) => new PostgresIntrospector(k),
      createQueryCompiler: () => new PostgresQueryCompiler(),
    },
    log: (event) => {
      if (event.level === "query") queries.push(event.query);
    },
  });
  return { getDb: () => db };
});
vi.mock("@/server/promises", () => ({ promises: () => promises() }));
vi.mock("@/server/log", () => ({ log: { warn: vi.fn(), error: vi.fn(), info: vi.fn() } }));

const hours = (h: number) => ({ session: { hours: h } });
const flat = (q: CompiledQuery) => q.sql.replace(/\s+/g, " ");

/** A fresh copy of the module each time, so the one-minute back-off of one test does not reach the next. */
async function session() {
  vi.resetModules();
  return import("@/server/auth/session");
}

beforeEach(() => {
  queries.length = 0;
  promises.mockReset();
  process.env.PRIVACY_NOTICE_VERSION = "pn-test-1";
});

afterEach(() => {
  vi.useRealTimers();
});

describe("L-AUTH.rules/5 session length comes from rules/promises.md", () => {
  it("is session.hours (8) and follows a change to it", async () => {
    const s = await session();
    promises.mockResolvedValue(hours(8));
    expect(await s.sessionTtlSeconds()).toBe(8 * 3600);
    promises.mockResolvedValue(hours(6));
    expect(await s.sessionTtlSeconds()).toBe(6 * 3600);
  });

  it("falls back to the policy's 8 hours when the worker cannot be read, and waits a minute before asking again", async () => {
    vi.useFakeTimers({ now: new Date("2026-11-20T04:00:00Z"), toFake: ["Date"] });
    const s = await session();
    promises.mockRejectedValue(new Error("promises_unavailable"));
    expect(await s.sessionTtlSeconds()).toBe(8 * 3600);
    expect(await s.sessionTtlSeconds()).toBe(8 * 3600);
    expect(promises).toHaveBeenCalledTimes(1); // a hanging worker does not hold up every page
    promises.mockResolvedValue(hours(7));
    vi.setSystemTime(new Date("2026-11-20T04:01:01Z"));
    expect(await s.sessionTtlSeconds()).toBe(7 * 3600);
  });

  it("ignores a value that is not a positive number of hours", async () => {
    const s = await session();
    promises.mockResolvedValue(hours(0));
    expect(await s.sessionTtlSeconds()).toBe(8 * 3600);
  });
});

describe("L-AUTH.rules/5 activity never extends a session past session.hours", () => {
  it("a new session ends session.hours after sign-in", async () => {
    vi.useFakeTimers({ now: new Date("2026-11-20T04:00:00Z"), toFake: ["Date"] });
    const s = await session();
    await s.createSession("00000000-0000-4000-8000-000000000017", 8 * 3600);
    const insert = queries.find((q) => /^insert into "sessions"/i.test(q.sql))!;
    expect(insert.parameters).toContainEqual(new Date("2026-11-20T12:00:00Z"));
  });

  it("recording activity moves the end to sign-in + session.hours, never to now + session.hours", async () => {
    const s = await session();
    await s.refreshSession("token-of-a-signed-in-browser", 8 * 3600);
    const update = queries.find((q) => /^update "sessions"/i.test(q.sql))!;
    expect(flat(update)).toMatch(/"expires_at" = created_at \+ make_interval\(secs => \$\d+\)/);
    expect(flat(update)).not.toMatch(/"expires_at" = now\(\)/);
    expect(update.parameters).toContain(8 * 3600);
    expect(update.parameters.some((p) => p instanceof Date && p.getTime() > Date.now() + 60_000)).toBe(false);
  });

  it("a session that began more than session.hours ago is over whatever its expires_at says", async () => {
    const s = await session();
    promises.mockResolvedValue(hours(8));
    expect(await s.readSession("token-of-a-signed-in-browser")).toBeNull(); // the dummy finds no row
    const read = queries.find((q) => /from sessions s/i.test(q.sql))!;
    expect(flat(read)).toMatch(/s\.expires_at > now\(\)/);
    expect(flat(read)).toMatch(/s\.created_at > now\(\) - make_interval\(secs => \$\d+\)/);
    expect(read.parameters).toContain(8 * 3600);
  });

  it("S-02 Session expired mid-draft finds a session that ran out by the clock, for a day after its end", async () => {
    const s = await session();
    promises.mockResolvedValue(hours(8));
    expect(await s.expiredSession("token-of-a-signed-in-browser")).toBeNull();
    const read = queries.find((q) => /from sessions s/i.test(q.sql))!;
    expect(flat(read)).toMatch(/s\.created_at <= now\(\) - make_interval\(secs => \$\d+\)/);
    expect(flat(read)).toMatch(/LEAST\(s\.expires_at, s\.created_at \+ make_interval\(secs => \$\d+\)\) > now\(\) - interval '1 day'/);
    expect(read.parameters.filter((p) => p === 8 * 3600)).toHaveLength(2);
  });
});
