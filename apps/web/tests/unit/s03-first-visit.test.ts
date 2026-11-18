/**
 * S-03.hero/1, A-API.home `first_visit` (BLD-C148): `firstHomeVisit` is true only the first time Home is shown to the
 * person. The real Kysely statements run against a stand-in for `person_settings` that answers as Postgres does: the
 * upsert keeps a `home_seen_at` already set (`coalesce`), and `home_seen_at = now()` in RETURNING is true only when
 * this statement set it (each statement has its own `now()`). Synthetic IDs only.
 */
import {
  Kysely,
  PostgresAdapter,
  PostgresIntrospector,
  PostgresQueryCompiler,
  type CompiledQuery,
  type DatabaseConnection,
  type Driver,
  type QueryResult,
} from "kysely";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser } from "@/server/auth/current";
import type { DB } from "@/server/db-types";

/** user_id -> home_seen_at (null when the row is there but Home was never shown). */
const seen = new Map<string, Date | null>();
const statements: string[] = [];
let clock = Date.parse("2026-11-20T04:30:00.000Z");

function run(query: CompiledQuery): QueryResult<Record<string, unknown>> {
  const sql = query.sql.replace(/\s+/g, " ").trim();
  statements.push(sql);
  const userId = String(query.parameters[0]);
  if (sql.startsWith('select "home_seen_at" from "person_settings" where "user_id" = $1')) {
    return { rows: seen.has(userId) ? [{ home_seen_at: seen.get(userId) ?? null }] : [] };
  }
  if (sql.startsWith('insert into "person_settings"')) {
    // The statement this stand-in answers for; anything else would be a different statement.
    expect(sql).toContain("on conflict");
    expect(sql).toContain("coalesce(person_settings.home_seen_at, now())");
    expect(sql).toContain('returning home_seen_at = now() as "first"');
    const now = new Date((clock += 1000)); // a new statement, a new now()
    const kept = seen.get(userId) ?? null;
    const value = kept ?? now;
    seen.set(userId, value);
    return { rows: [{ first: value.getTime() === now.getTime() }] };
  }
  throw new Error(`unexpected statement: ${sql}`);
}

class Connection implements DatabaseConnection {
  async executeQuery<R>(query: CompiledQuery): Promise<QueryResult<R>> {
    await Promise.resolve(); // a round trip, so two tabs can interleave
    return run(query) as QueryResult<R>;
  }
  async *streamQuery<R>(): AsyncIterableIterator<QueryResult<R>> {
    throw new Error("not used");
  }
}

class StandIn implements Driver {
  async init() {}
  async acquireConnection() {
    return new Connection();
  }
  async beginTransaction() {}
  async commitTransaction() {}
  async rollbackTransaction() {}
  async releaseConnection() {}
  async destroy() {}
}

const db = new Kysely<DB>({
  dialect: {
    createAdapter: () => new PostgresAdapter(),
    createDriver: () => new StandIn(),
    createQueryCompiler: () => new PostgresQueryCompiler(),
    createIntrospector: (k) => new PostgresIntrospector(k),
  },
});

vi.mock("@/server/db", () => ({ getDb: () => db }));

const { firstHomeVisit } = await import("@/server/home");

const me = (id: string) => ({ id, name: "Sana Qureshi" }) as unknown as CurrentUser;
const SANA = "5a5a0000-0000-4000-8000-000000010026";

beforeEach(() => {
  seen.clear();
  statements.length = 0;
});

describe("firstHomeVisit (S-03.hero/1, BLD-C148)", () => {
  it("the first call is the first visit; the second is not, and writes nothing", async () => {
    expect(await firstHomeVisit(me(SANA))).toBe(true);
    const written = statements.length;
    expect(await firstHomeVisit(me(SANA))).toBe(false);
    expect(statements.slice(written).every((s) => s.startsWith("select"))).toBe(true);
  });

  it("a second tab opened after the first is not a first visit", async () => {
    const first = await firstHomeVisit(me(SANA));
    const secondTab = await firstHomeVisit(me(SANA));
    expect([first, secondTab]).toEqual([true, false]);
  });

  it("two tabs at once: only one of them gets the first visit", async () => {
    const both = await Promise.all([firstHomeVisit(me(SANA)), firstHomeVisit(me(SANA))]);
    expect(both.filter(Boolean)).toHaveLength(1);
    expect(statements.filter((s) => s.startsWith("insert"))).toHaveLength(2); // both read nothing, both upserted
  });

  it("a person with a settings row who never saw Home gets it once", async () => {
    seen.set(SANA, null); // person_settings exists (the name choice), home_seen_at empty
    expect(await firstHomeVisit(me(SANA))).toBe(true);
    expect(await firstHomeVisit(me(SANA))).toBe(false);
  });

  it("a seeded persona who has seen Home is never a first visit (the seed sets home_seen_at)", async () => {
    seen.set(SANA, new Date("2026-11-18T03:00:00.000Z"));
    expect(await firstHomeVisit(me(SANA))).toBe(false);
  });

  it("a router prefetch is not a visit, and reads nothing", async () => {
    expect(await firstHomeVisit(me(SANA), true)).toBe(false);
    expect(statements).toEqual([]);
    expect(await firstHomeVisit(me(SANA))).toBe(true);
  });
});
