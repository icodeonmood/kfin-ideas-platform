import { writeRoute } from "@/server/desk";

/** POST /api/question-sets/{id}/send — the sharer sends their answers (L-QUESTIONS.answer/5); the worker checks it is theirs. */
export const POST = writeRoute("signed_in", "POST", (id) => `/internal/question-sets/${id}/send`);
