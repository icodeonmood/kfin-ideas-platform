import { writeRoute } from "@/server/desk";

/** POST /api/committee/windows/{id}/extend — 30 more days, up to 3 months (L-COMMITTEE.rules/2). */
export const POST = writeRoute(
  "committee_window",
  "POST",
  (id) => `/internal/committee/windows/${id}/extend`,
);
