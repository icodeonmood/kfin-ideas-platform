/**
 * The associated-data context for a `*_encrypted` column added by the handoff cut-over (BLD-E006), so a row written
 * by one side opens on the other: `encrypt_json({ text }, "<table>.<column>:<row id>")` in Python
 * (`onepc.context.sealed_context`) and the same string here with `src/server/crypto.ts`.
 * Example: `sealedContext("idea_decisions", "reason_encrypted", id)` -> "idea_decisions.reason_encrypted:<id>".
 */
export function sealedContext(table: string, column: string, rowId: string | number): string {
  return `${table}.${column}:${rowId}`;
}
