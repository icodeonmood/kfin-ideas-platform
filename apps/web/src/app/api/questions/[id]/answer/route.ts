import { writeRoute } from "@/server/desk";

/** PUT /api/questions/{id}/answer — the sharer's answer, saved as typed (L-QUESTIONS.answer/4). */
export const PUT = writeRoute("signed_in", "PUT", (id) => `/internal/questions/${id}/answer`, [
  "text",
  "file_ids",
]);
