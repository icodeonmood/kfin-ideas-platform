import { writeRoute } from "@/server/desk";

/** POST /api/desk/ideas/{id}/merge — the desk merges two ideas and can team the sharers up (L-MERGE.desk). */
export const POST = writeRoute("work_review_queue", "POST", (id) => `/internal/desk/ideas/${id}/merge`, [
  "other_idea_id",
  "lead",
  "team_up",
  "note",
]);
