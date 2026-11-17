import { getConversation } from "@/server/convo";

/** GET /api/ideas/{id}/conversation — the idea's one conversation, as this person may read it (L-CONVO). */
export const GET = getConversation;
