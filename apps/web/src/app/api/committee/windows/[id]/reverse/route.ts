import { writeRoute } from "@/server/desk";

/** POST /api/committee/windows/{id}/reverse — once, final, with a note the sharer reads (L-COMMITTEE.rules/3–5). */
export const POST = writeRoute(
  "committee_window",
  "POST",
  (id) => `/internal/committee/windows/${id}/reverse`,
  ["to", "note", "return_in"],
);
