/**
 * Kill switches (§7.6), web side. Read on every request with a 10-second cache (BLD-006); same table and
 * same rules as services/worker/core/killswitch.py. "on" = the feature runs; "off" = it is killed.
 * A switch the table does not know counts as off (fail closed). Every change needs a reason and is audited.
 */
import { getDb } from "./db";
import { log } from "./log";

export type SwitchState = "on" | "off";
export const CACHE_MS = 10_000;
export const REASON_MIN_CHARS = 10;

let cache: { at: number; states: Map<string, SwitchState> } | undefined;

export function clearKillSwitchCache(): void {
  cache = undefined;
}

export async function switchStates(now: number = Date.now()): Promise<Map<string, SwitchState>> {
  if (cache && now - cache.at < CACHE_MS) return cache.states;
  const rows = await getDb().selectFrom("kill_switches").select(["name", "state"]).execute();
  const states = new Map(rows.map((r) => [r.name, r.state === "on" ? "on" : "off"] as const));
  cache = { at: now, states };
  return states;
}

export function isOn(states: Map<string, SwitchState>, name: string): boolean {
  return states.get(name) === "on";
}

export class KillSwitchError extends Error {}

export async function setKillSwitch(input: {
  name: string;
  state: SwitchState;
  reason: string;
  actor: string;
  ip?: string | null;
}): Promise<void> {
  const reason = input.reason.trim();
  if (input.state !== "on" && input.state !== "off") throw new KillSwitchError("state must be on or off");
  if (reason.length < REASON_MIN_CHARS) {
    throw new KillSwitchError(`a reason of at least ${REASON_MIN_CHARS} characters is required`);
  }
  if (!input.actor.trim()) throw new KillSwitchError("actor is required");
  await getDb()
    .transaction()
    .execute(async (trx) => {
      const before = await trx
        .selectFrom("kill_switches")
        .select("state")
        .where("name", "=", input.name)
        .forUpdate()
        .executeTakeFirst();
      if (!before) throw new KillSwitchError(`unknown kill switch ${input.name}`);
      await trx
        .updateTable("kill_switches")
        .set({ state: input.state, reason, changed_by: input.actor, changed_at: new Date() })
        .where("name", "=", input.name)
        .execute();
      await trx
        .insertInto("audit_log")
        .values({
          actor: input.actor,
          action: "kill_switch.set",
          entity: `kill_switch:${input.name}`,
          before: JSON.stringify({ state: before.state }),
          after: JSON.stringify({ state: input.state }),
          reason,
          ip: input.ip ?? null,
        })
        .execute();
    });
  clearKillSwitchCache();
  // Alerting to the product lead and InfoSec goes through the comms module (B6); this line is the alert until then.
  // The change is already committed and audited, so a log refusal must not turn it into a failed request
  // (BLD-A183: a random user UUID could trip the value scan and the switch changed behind a 500).
  try {
    log.warn("killswitch.changed", { switch: input.name, state: input.state, actor_code: input.actor });
  } catch {
    // the audit_log row above is the record
  }
}
