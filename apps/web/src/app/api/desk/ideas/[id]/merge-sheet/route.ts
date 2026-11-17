import { getRoute } from "@/server/desk";

/** GET /api/desk/ideas/{id}/merge-sheet — the merge sheet's words and default lead (C-SHEET-MERGE). */
export const GET = getRoute("work_review_queue", (id) => `/internal/desk/ideas/${id}/merge-sheet`, ["other"]);
