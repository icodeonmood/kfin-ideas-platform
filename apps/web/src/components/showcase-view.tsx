/**
 * The Showcase brief (DEC-086): 30 minutes per One in a fixed seven-part format. Each part shows the One's own
 * words if they wrote them, else what their record says. The committee reads it before the Showcase. The One writes
 * it in the sheet on S-ONE (app/one/showcase-sheet.tsx, BLD-E042).
 */
import { measureList } from "@/lib/measures";
import type { ShowcaseBrief } from "@/server/ones";

export const SHOWCASE_LABELS: Record<string, { title: string; ask: string }> = {
  idea: { title: "The idea", ask: "What you noticed and what you built, in a few lines." },
  proposed_impact: { title: "Proposed impact", ask: "What changes if it works." },
  progress: { title: "Current progress", ask: "Where it stands today." },
  impact_so_far: {
    title: "Impact created so far",
    ask: "What has changed already, in time, money, effort or scale.",
  },
  timelines: { title: "Delivery timelines", ask: "The next milestones and their dates." },
  team: {
    title: "The team, or your solo profile",
    ask: "Who is building it with you, or how you work on it.",
  },
  help: { title: "Help or sponsorship needed", ask: "Be specific: who, what and by when." },
};

export function recordText(brief: ShowcaseBrief, key: string, fromRecord: string | null): string | null {
  if (key === "impact_so_far") {
    const m = measureList(brief.measures);
    return m.length ? m.map(([label, words]) => `${label}: ${words}`).join(". ") : null;
  }
  return fromRecord;
}
