import { writeRoute } from "@/server/desk";

/** PUT /api/desk/ideas/{id}/question-sets/queued — the reviewer's queue, saved as it changes, masked by the worker
 * before it is stored, for their next visit (BLD-B272; S-R2.panel Asking, L-QUESTIONS.states "queued"). */
export const PUT = writeRoute(
  "work_review_queue",
  "PUT",
  (id) => `/internal/desk/ideas/${id}/question-sets/queued`,
  ["questions", "time_to_answer", "rev", "after"],
);
