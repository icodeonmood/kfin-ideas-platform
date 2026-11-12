import { Kysely, PostgresDialect } from "kysely";
import { Pool } from "pg";

import type { DB } from "./db-types";
import { log } from "./log";

let instance: Kysely<DB> | undefined;

/** One Kysely instance per server process. Types are generated from the migrated schema (`make db-types`). */
export function getDb(): Kysely<DB> {
  if (!instance) {
    const connectionString = process.env.DATABASE_URL;
    if (!connectionString) throw new Error("DATABASE_URL is not set");
    const pool = new Pool({ connectionString, max: 10 });
    // An idle connection the database or network drops is an error on the pool. Without a listener Node treats it
    // as uncaught; with one, the pool discards that connection and the next request gets a fresh one (BLD-A171).
    pool.on("error", (err: Error & { code?: string }) =>
      log.error("db.pool_error", { error_type: err.constructor.name, sqlstate: err.code ?? null }),
    );
    instance = new Kysely<DB>({ dialect: new PostgresDialect({ pool }) });
  }
  return instance;
}
