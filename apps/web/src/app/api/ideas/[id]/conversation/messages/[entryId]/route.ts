import { deleteMessage } from "@/server/convo";

/** DELETE /api/ideas/{id}/conversation/messages/{entryId} — the sender's own message, within 5 minutes (L-CONVO/10). */
export const DELETE = deleteMessage;
