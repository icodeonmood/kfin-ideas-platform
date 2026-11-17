import { writeRoute } from "@/server/desk";

/** PUT /api/desk/ideas/{id}/worth — the reviewer's revision of what it's worth (L-WORTH). */
export const PUT = writeRoute("work_review_queue", "PUT", (id) => `/internal/desk/ideas/${id}/worth`, [
  "hours_month",
  "cost_month",
  "revenue_month",
  "outside_tools",
  "kind",
  "area",
  "note",
]);
