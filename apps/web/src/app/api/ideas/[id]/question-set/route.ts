import { getRoute } from "@/server/desk";

/** GET /api/ideas/{id}/question-set — the open set for its sharer, marked seen (S-R3); the worker checks it is theirs. */
export const GET = getRoute("signed_in", (id) => `/internal/ideas/${id}/question-set`);
