import { writeRoute } from "@/server/desk";

/** POST /api/desk/ideas/{id}/open — the first open closes the edit window (L-REVIEW.open/1). */
export const POST = writeRoute("work_review_queue", "POST", (id) => `/internal/desk/ideas/${id}/open`);
