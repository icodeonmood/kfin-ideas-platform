import { officeOrder, type OfficeData, type PublicOneInput } from "@/lib/display";

import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

/**
 * The office screen's data (S-OFFICE, L-DISPLAY.office, A-API `GET /display/office`): the active Ones with their
 * briefs and a headline figure, in induction order. The worker applies the `ones.public` switch, checks each brief
 * again and keeps money out until Finance confirms it. A name shows unless the person hid it from the Wall in
 * Profile (DEC-104, `person_settings.show_name_on_wall`).
 */
export async function officeScreen(): Promise<OfficeData> {
  const res = await workerFetch("/internal/display/office", { signal: AbortSignal.timeout(30_000) });
  const body = (await res.json().catch(() => ({ error: "ones_unavailable" }))) as {
    paused?: boolean;
    ones?: PublicOneInput[];
    error?: string;
  };
  if (!res.ok) throw new SubmissionError(res.status, String(body.error ?? "ones_unavailable"));
  if (body.paused) return { paused: true, ones: [] };
  return { paused: false, ones: officeOrder(body.ones ?? []) };
}
