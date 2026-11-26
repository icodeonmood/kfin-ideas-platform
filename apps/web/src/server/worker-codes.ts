import { ASSISTANT_OFF } from "@/lib/assistant-off";

/** The gateway's codes when it made no call because the assistant is off: `ai.all` or the agent's own switch
 * (`kill_switch`), or the day's model budget spent (`daily_budget`), both raised as `AgentSwitchedOff`
 * (services/worker/gateway/core.py). The worker's Ones, Ember and delivery calls answer them as 503
 * `{ error: "checks_unavailable", code }` (api/app.py `_ones_call`, `_delivery_call`). */
const SWITCHED_OFF = new Set(["switched_off", "daily_budget"]);

/** The code a worker refusal is shown by (DEC-143 (f), BLD-B282): `assistant_off` when the text check did not run
 * because the assistant is off, so the screen can say the words save once it is back; any other failure of the
 * checks (the model route down, the leak check) stays `checks_unavailable`, "try again in a few minutes". */
export function refusalCode(out: Record<string, unknown>, fallback: string): string {
  const code = String(out.error ?? fallback);
  return code === "checks_unavailable" && SWITCHED_OFF.has(String(out.code ?? "")) ? ASSISTANT_OFF : code;
}
