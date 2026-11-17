import { writeRoute } from "@/server/desk";

/** POST /api/question-sets/{id}/extend — "Give 2 more days" (L-QUESTIONS.clock/3). */
export const POST = writeRoute("work_review_queue", "POST", (id) => `/internal/question-sets/${id}/extend`);
