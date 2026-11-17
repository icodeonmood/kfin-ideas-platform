import { getRoute } from "@/server/desk";

/** GET /api/desk/ideas/{id}/listen — the masked script the browser reads aloud (L-LISTEN, BLD-B230). */
export const GET = getRoute("view_review_queue", (id) => `/internal/desk/ideas/${id}/listen`);
