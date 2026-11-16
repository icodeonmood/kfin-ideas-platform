import { getRoute } from "@/server/desk";

/** GET /api/desk/ideas/{id}/suggested-questions — questions drawn from the idea's gaps (L-QUESTIONS.ask/3). */
export const GET = getRoute("work_review_queue", (id) => `/internal/desk/ideas/${id}/suggested-questions`);
