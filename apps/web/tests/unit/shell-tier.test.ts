/**
 * C-SIDEBAR.anatomy/5, L-ONES.rules/3–4: the account row's tier line is for everyone. `shellData` reads one row: an
 * active One's tier, else the person's own `users.tier`, and names it from E-ENUMS.tier ("Tier 1, Spark"), as the
 * worker's `tier_label` does. Nothing of points is read. No database: a fake Kysely driver records the query and
 * answers with the row a test sets. Synthetic people only.
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
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AccountMenu } from "@/components/shell/account-menu";
import type { CurrentUser } from "@/server/auth/current";
import type { DB } from "@/server/db-types";
import { shellData, type ShellData } from "@/server/shell";

const fake = vi.hoisted(() => ({
  seen: [] as Array<{ sql: string; parameters: readonly unknown[] }>,
  rows: [] as Array<{ tier: number }>,
  fail: false,
}));

const connection: DatabaseConnection = {
  async executeQuery<R>(q: CompiledQuery): Promise<QueryResult<R>> {
    if (fake.fail) throw new Error("connection refused");
    fake.seen.push({ sql: q.sql, parameters: q.parameters });
    return { rows: fake.rows as R[] };
  },
  streamQuery() {
    throw new Error("not used");
  },
};

const driver: Driver = {
  init: async () => undefined,
  acquireConnection: async () => connection,
  beginTransaction: async () => undefined,
  commitTransaction: async () => undefined,
  rollbackTransaction: async () => undefined,
  releaseConnection: async () => undefined,
  destroy: async () => undefined,
};

const db = new Kysely<DB>({
  dialect: {
    createAdapter: () => new PostgresAdapter(),
    createDriver: () => driver,
    createIntrospector: (k) => new PostgresIntrospector(k),
    createQueryCompiler: () => new PostgresQueryCompiler(),
  },
});

vi.mock("@/server/db", () => ({ getDb: () => db }));
vi.mock("@/server/ideas", () => ({ myIdeas: async () => ({ ideas: [] }) }));
vi.mock("@/server/inbox", () => ({ inboxCounts: async () => ({ unread: 0 }) }));
vi.mock("@/server/desk", () => ({ deskRead: async () => null }));
vi.mock("next/navigation", () => ({ usePathname: () => "/" }));

function person(id: string, name: string): CurrentUser {
  return {
    id,
    name,
    email: `${id}@example.test`,
    lobId: null,
    roleFamily: null,
    contributorCode: null,
    grants: [],
    roles: new Set(["signed_in"]),
    nav: [],
    privacyAccepted: true,
  };
}

const menu = (data: ShellData) =>
  renderToStaticMarkup(createElement(AccountMenu, { data, items: [], placement: "up" }));

const KAVYA = person("00000000-0000-4000-8000-000000000101", "Kavya Menon"); // a One, Tier 3
const RAVI = person("00000000-0000-4000-8000-000000000102", "Ravi Nair"); // not a One, users.tier 1

beforeEach(() => {
  fake.seen.length = 0;
  fake.rows = [];
  fake.fail = false;
});

describe("C-SIDEBAR.anatomy/5, L-ONES.rules/3–4: the tier line for everyone", () => {
  it("reads one row: the active One's tier, else users.tier, and nothing else", async () => {
    fake.rows = [{ tier: 3 }];
    await shellData(KAVYA);
    expect(fake.seen).toEqual([
      {
        sql:
          'select coalesce("o"."tier", "u"."tier") as "tier" from "users" as "u" left join "ones" as "o" on ' +
          '"o"."user_id" = "u"."id" and "o"."status" = $1 and "o"."number" is not null where "u"."id" = $2',
        parameters: ["active", KAVYA.id],
      },
    ]);
    expect(fake.seen[0]!.sql).not.toMatch(/points/);
  });

  it("L-ONES.rules/3: a One gets their One tier and its name", async () => {
    fake.rows = [{ tier: 3 }];
    const data = await shellData(KAVYA);
    expect([data.tier, data.tierName]).toEqual([3, "Flame"]);
    expect(menu(data)).toContain("Tier 3, Flame");
  });

  it("L-ONES.rules/4: a person who is not a One gets users.tier and its label", async () => {
    fake.rows = [{ tier: 1 }];
    const data = await shellData(RAVI);
    expect(fake.seen[0]!.parameters).toEqual(["active", RAVI.id]);
    expect([data.tier, data.tierName]).toEqual([1, "Spark"]);
    const html = menu(data);
    expect(html).toContain("Tier 1, Spark");
    expect(html).toContain("av-ring av-t1");
  });

  it("when the tier cannot be read, the shell still renders, with no tier line", async () => {
    fake.fail = true;
    const data = await shellData(RAVI);
    expect([data.tier, data.tierName]).toEqual([null, null]);
    expect(menu(data)).not.toContain("Tier ");
  });
});
