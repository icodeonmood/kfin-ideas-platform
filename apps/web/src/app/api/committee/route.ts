import { getRoute } from "@/server/desk";

/** GET /api/committee — every decision in its window (S-R4, A-API.committee). */
export const GET = getRoute("committee_window", () => "/internal/committee", ["tab", "sort"]);
