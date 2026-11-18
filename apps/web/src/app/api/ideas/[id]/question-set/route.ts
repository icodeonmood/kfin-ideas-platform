import { getRoute } from "@/server/desk";

/** GET /api/ideas/{id}/question-set — the open set for its sharer, marked seen (S-R3); the worker checks it is theirs.
 * `?set_id=` (the Inbox reader opening one item): only that set, else a 404 and nothing marked seen (BLD-B248). */
export const GET = getRoute("signed_in", (id) => `/internal/ideas/${id}/question-set`, ["set_id"]);
