import { passRoute } from "@/server/crew";

/** POST /api/crew/pass/undo — "Undo last pass" brings the last passed card back (L-CREW/6). */
export const POST = passRoute("/internal/crew/pass/undo");
