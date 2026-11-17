import { postMessage } from "@/server/convo";

/** POST /api/ideas/{id}/conversation/messages — `{ text, file_ids?, mentions? }` (L-CONVO/5–7). */
export const POST = postMessage;
