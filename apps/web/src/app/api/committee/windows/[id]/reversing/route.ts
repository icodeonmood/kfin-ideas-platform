import { getRoute } from "@/server/desk";

/** GET /api/committee/windows/{id}/reversing — the reversal form's words (S-R4 Reversing). */
export const GET = getRoute("committee_window", (id) => `/internal/committee/windows/${id}/reversing`);
