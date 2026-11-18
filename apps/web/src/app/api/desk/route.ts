import { getRoute, searchRoute } from "@/server/desk";

/** GET /api/desk — the review desk's queue, counts and summary for a tab and sort (S-R1, A-API.desk). A `q` in the
 * query is never read or passed on (DEC-110). */
export const GET = getRoute("view_review_queue", () => "/internal/desk", ["tab", "sort"]);
/** POST /api/desk `{ tab, sort, q }` — the same read with a search, its words in the body and never in a URL (DEC-110). */
export const POST = searchRoute("view_review_queue", () => "/internal/desk", ["tab", "sort", "q"]);
