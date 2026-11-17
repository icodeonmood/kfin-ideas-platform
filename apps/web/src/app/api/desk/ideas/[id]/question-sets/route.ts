import { writeRoute } from "@/server/desk";

/** POST /api/desk/ideas/{id}/question-sets — send questions with a time to answer (L-QUESTIONS.ask). */
export const POST = writeRoute(
  "work_review_queue",
  "POST",
  (id) => `/internal/desk/ideas/${id}/question-sets`,
  ["questions", "time_to_answer", "move_decide_by"],
);
