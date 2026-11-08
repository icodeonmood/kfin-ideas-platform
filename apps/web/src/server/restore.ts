/**
 * Restore on view (§3.2 step 8, §3.1 `see_restored_values`, AT-B4-05): who sees real values behind the tags of
 * an idea, and who sees neutral labels ("a colleague", "an AMC client"). The worker's restore service does the
 * swap; this decides the mode, from the same policy file as every other permission.
 *
 * Day one: the owner of the idea; the reviewer handling it (its review item is assigned to them, or not yet
 * assigned, since the desk works one shared queue); the core committee. Admins see real values only with a
 * reason, which is audited. Everyone else: neutral. LOB committees, appeal panels, working groups and sponsors
 * join with their screens (B6/B7 and later).
 */
export type RestoreMode = "real" | "neutral";

export type Viewer = { id: string; contributorCode: string | null; roles: readonly string[] };
export type IdeaForView = {
  contributorCode: string;
  reviewItem: { assignedTo: string | null; state: string } | null;
};

const OPEN_DESK_STATES = new Set(["open", "in_progress", "awaiting_second_reviewer"]);

export function restoreMode(
  viewer: Viewer,
  idea: IdeaForView,
  opts: { adminReason?: string } = {},
): RestoreMode {
  if (viewer.contributorCode && viewer.contributorCode === idea.contributorCode) return "real";
  if (viewer.roles.includes("core_committee") || viewer.roles.includes("core_chair")) return "real";
  if (viewer.roles.includes("reviewer") && idea.reviewItem) {
    const item = idea.reviewItem;
    if (item.assignedTo === viewer.id) return "real";
    if (item.assignedTo === null && OPEN_DESK_STATES.has(item.state)) return "real";
  }
  if (viewer.roles.includes("admin") && (opts.adminReason ?? "").trim().length >= 10) return "real";
  return "neutral";
}
