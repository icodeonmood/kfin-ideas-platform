import { getRoute } from "@/server/desk";

/** GET /api/desk/ideas/{id} — everything on the reviewer's page (S-R2). */
export const GET = getRoute("view_review_queue", (id) => `/internal/desk/ideas/${id}`);
