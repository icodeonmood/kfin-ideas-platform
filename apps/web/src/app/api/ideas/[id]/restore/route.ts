import { postIdeaAction } from "@/server/idea-page";

/** POST /api/ideas/{id}/restore — the sharer only; shares it again with the same reference (L-SUBMIT.withdraw/3). */
export const POST = postIdeaAction("restore");
