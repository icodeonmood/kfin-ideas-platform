import { postIdeaAction } from "@/server/idea-page";

/** POST /api/ideas/{id}/withdraw `{ reason? }` — the sharer only, inside the edit window (L-SUBMIT.withdraw). */
export const POST = postIdeaAction("withdraw");
