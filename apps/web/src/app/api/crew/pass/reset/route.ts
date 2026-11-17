import { passRoute } from "@/server/crew";

/** POST /api/crew/pass/reset — "See them again" undoes every pass (L-CREW/6). */
export const POST = passRoute("/internal/crew/pass/reset");
