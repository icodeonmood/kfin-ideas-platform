import { getMyIdeas, postMyIdeas } from "@/server/idea-page";

/** GET /api/me/ideas — My ideas in the list state the query names, never with a search (S-07, A-API.my-ideas, lane E). */
export const GET = getMyIdeas;
/** POST /api/me/ideas — the same read with the search in the body, so its words are in no URL (DEC-110). */
export const POST = postMyIdeas;
