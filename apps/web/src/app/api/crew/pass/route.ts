import { passRoute } from "@/server/crew";

/** POST /api/crew/pass `{ idea_id }` — "Next" passes the front card (L-CREW/6). */
export const POST = passRoute("/internal/crew/pass", true);
