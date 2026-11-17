import { getIdeaView } from "@/server/idea-page";

/** GET /api/ideas/{id} — S-06 for the sharer, S-09 for anyone else, S-R2 for a reviewer (A-API.ideas, lane E). */
export const GET = getIdeaView;
