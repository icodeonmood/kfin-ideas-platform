import { getRoute } from "@/server/desk";

/** GET /api/ideas/{id}/decision — the decision, its reason and the committee's window (S-06, S-R2). */
export const GET = getRoute("signed_in", (id) => `/internal/ideas/${id}/decision`);
