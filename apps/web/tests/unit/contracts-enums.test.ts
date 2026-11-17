import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { ONEPC } from "@/lib/contracts/enums.gen";
import {
  DB_CHECKS,
  DB_VALUES_OUTSIDE_THE_PACK,
  enumValues,
  isEnumValue,
  type EnumName,
} from "@/lib/contracts";

const repo = path.resolve(__dirname, "../../../..");
const source = JSON.parse(readFileSync(path.join(repo, "contracts/1pc/enums.json"), "utf8"));
const CUTOVER = "20261121500100_handoff_cutover.sql";
const migration = readFileSync(path.join(repo, "db/migrations", CUTOVER), "utf8");
/** Migrations after the cut-over that widen one of its CHECKs (lane C's `detail_hidden_by_desk`, BLD-C063). */
const later = readdirSync(path.join(repo, "db/migrations"))
  .filter((name) => name.endsWith(".sql") && name > CUTOVER)
  .sort()
  .map((name) => readFileSync(path.join(repo, "db/migrations", name), "utf8"));

/** Every `col IN (...)` and `col <@ ARRAY[...]` CHECK in the migration's up section, keyed "table.column". */
function checksInMigration(sql: string): Map<string, string[]> {
  const up = sql.split("-- migrate:down")[0]!;
  const tables = [...up.matchAll(/(?:CREATE|ALTER) TABLE (\w+)/g)].map((m) => ({
    at: m.index!,
    name: m[1]!,
  }));
  const tableAt = (i: number) => tables.filter((t) => t.at < i).at(-1)?.name;
  const out = new Map<string, string[]>();
  for (const m of up.matchAll(/CHECK \(\s*(\w+) IN \(([^)]*)\)|CHECK \(\s*(\w+) <@ ARRAY\[([^\]]*)\]/g)) {
    const table = tableAt(m.index!);
    if (table === undefined) continue;
    const column = m[1] ?? m[3]!;
    const list = m[2] ?? m[4]!;
    out.set(
      `${table}.${column}`,
      [...list.matchAll(/'([^']*)'/g)].map((v) => v[1]!),
    );
  }
  return out;
}

describe("E-ENUMS shared contract (contracts/1pc/enums.json, BLD-E006)", () => {
  it("enums.gen.ts matches contracts/1pc/enums.json exactly; run `npm run sync:shared`", () => {
    expect(ONEPC).toEqual(source);
  });

  it("the worker's copy (services/worker/onepc/enums.json) matches it too", () => {
    const copy = JSON.parse(readFileSync(path.join(repo, "services/worker/onepc/enums.json"), "utf8"));
    expect(copy).toEqual(source);
  });

  it("E-ENUMS.idea-status carries the pack's eleven values in order", () => {
    expect(enumValues("idea_status")).toEqual([
      "draft",
      "checking",
      "with_review_desk",
      "needs_you",
      "picked",
      "being_built",
      "shipped",
      "not_now",
      "not_picked",
      "withdrawn",
      "merged",
    ]);
    expect(isEnumValue("idea_status", "picked")).toBe(true);
    expect(isEnumValue("idea_status", "scanned")).toBe(false);
  });

  it("every database CHECK in the cut-over equals its enum (plus the old values a reused column keeps)", () => {
    const found = checksInMigration(migration);
    // A later migration that replaces one of these CHECKs wins, as it does in the database.
    for (const sql of later)
      for (const [key, values] of checksInMigration(sql)) if (found.has(key)) found.set(key, values);
    for (const [key, names] of Object.entries(DB_CHECKS)) {
      const expected = new Set<string>(names.flatMap((n) => enumValues(n as EnumName).map(String)));
      for (const extra of DB_VALUES_OUTSIDE_THE_PACK[key] ?? []) expected.add(extra);
      expect(found.has(key), `${key} has a CHECK in the migration`).toBe(true);
      expect(new Set(found.get(key)), key).toEqual(expected);
    }
  });

  it("promises stay out of SQL: no CHECK on the answer time or the return period (P-PRODUCT.promises)", () => {
    const found = checksInMigration(migration);
    expect(found.has("question_sets.time_to_answer")).toBe(false);
    expect(found.has("idea_decisions.return_in")).toBe(false);
    expect(found.has("decision_reversals.return_in")).toBe(false);
  });
});
