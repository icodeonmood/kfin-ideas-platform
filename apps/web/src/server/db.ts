import { Kysely, PostgresDialect } from "kysely";
import { Pool } from "pg";

import type { DB } from "./db-types";

let instance: Kysely<DB> | undefined;

/** One Kysely instance per server process. Types are generated from the migrated schema (`make db-types`). */
export function getDb(): Kysely<DB> {
  if (!instance) {
    const connectionString = process.env.DATABASE_URL;
    if (!connectionString) throw new Error("DATABASE_URL is not set");
    instance = new Kysely<DB>({
      dialect: new PostgresDialect({ pool: new Pool({ connectionString, max: 10 }) }),
    });
  }
  return instance;
}
