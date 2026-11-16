/**
 * Sign-in storage before lane E's cut-over (BLD-A173). `sign_in_intents` and `sign_in_codes` arrive in the
 * cut-over migration (20261121500100). Until that is on a database, a store whose table is missing (SQLSTATE
 * 42P01) carries on in process memory, so sign-in keeps working on a branch built before the cut-over. Once the
 * table exists, nothing here is used. The switch is logged once, with no request data.
 */
import { log } from "../log";

const UNDEFINED_TABLE = "42P01";

export const isMissingTable = (err: unknown) =>
  typeof err === "object" && err !== null && (err as { code?: unknown }).code === UNDEFINED_TABLE;

/**
 * Wraps a database store and an in-memory one with the same interface. Every method goes to the database store
 * until it reports a missing table; from then on, for the life of the process, to the memory store.
 */
export function withTableFallback<T extends object>(name: string, db: T, memory: T): T {
  let useMemory = false;
  return new Proxy(db, {
    get(target, prop, receiver) {
      const fromDb = Reflect.get(target, prop, receiver) as unknown;
      if (typeof fromDb !== "function") return fromDb;
      return async (...args: unknown[]) => {
        if (!useMemory) {
          try {
            return await (fromDb as (...a: unknown[]) => Promise<unknown>).apply(target, args);
          } catch (err) {
            if (!isMissingTable(err)) throw err;
            useMemory = true;
            log.warn("auth.store_in_memory", { store: name });
          }
        }
        const fromMemory = Reflect.get(memory, prop) as (...a: unknown[]) => Promise<unknown>;
        return fromMemory.apply(memory, args);
      };
    },
  });
}
