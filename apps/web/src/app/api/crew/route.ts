import { CREW_FILTERS, signedInRead } from "@/server/crew";

/** GET /api/crew — Find your crew: the deck, filters with live counts, passes and "Your crews" (L-CREW, S-H2). */
export const GET = signedInRead("/internal/crew", CREW_FILTERS, ["limit"]);
