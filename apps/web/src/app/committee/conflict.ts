/** What a committee member with a conflict of interest on a group reads instead of the group (§3.1, BLD-221). */
export const CONFLICT_TEXT: Record<string, string> = {
  own_idea:
    "This group holds an idea you shared or joined, so you take no part in its review. The group and its scores are not shown to you.",
  recused: "You have stepped aside from this group's review. The group and its scores are not shown to you.",
  flagged:
    "Someone you manage shared or joined an idea in this group. Step aside below, or ask an admin to clear the flag with a reason.",
  manager:
    "Someone you manage shared or joined an idea in this group. Step aside below, or ask an admin to clear the flag with a reason.",
};

export const conflictText = (why: string): string =>
  CONFLICT_TEXT[why] ?? "You take no part in this group's review.";
