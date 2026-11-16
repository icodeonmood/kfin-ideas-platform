import { writeRoute } from "@/server/desk";

/** POST /api/question-sets/{id}/remind — "Send a reminder" (L-QUESTIONS.clock/3). */
export const POST = writeRoute("work_review_queue", "POST", (id) => `/internal/question-sets/${id}/remind`);
