import { getRoute } from "@/server/desk";

/** GET /api/desk — the review desk's queue, counts and summary (S-R1, A-API.desk). */
export const GET = getRoute("view_review_queue", () => "/internal/desk", ["tab", "sort", "q"]);
