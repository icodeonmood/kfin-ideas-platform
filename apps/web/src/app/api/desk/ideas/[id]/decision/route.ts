import { writeRoute } from "@/server/desk";

/** POST /api/desk/ideas/{id}/decision — Pick, Not now or Not picked with a reason (L-DECIDE). */
export const POST = writeRoute("work_review_queue", "POST", (id) => `/internal/desk/ideas/${id}/decision`, [
  "choice",
  "reason",
  "return_in",
  "joined_with",
  "wording_ok",
]);
