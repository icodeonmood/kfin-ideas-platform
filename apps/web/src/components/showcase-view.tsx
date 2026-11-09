/**
 * The Showcase brief (DEC-086): 30 minutes per One in a fixed seven-part format. Each part shows the One's own
 * words if they wrote them, else what their record says. The committee reads it before the Showcase.
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

export function ShowcaseView({ brief }: { brief: ShowcaseBrief }) {
  return (
    <ol className="showcase-parts">
      {brief.parts.map((p) => {
        const record = recordText(brief, p.key, p.from_record);
        return (
          <li key={p.key}>
            <h2>{SHOWCASE_LABELS[p.key]?.title ?? p.key}</h2>
            {p.own ? <p>{p.own}</p> : null}
            {record ? (
              <p className="record">
                {p.own ? "From the record: " : ""}
                {record}
              </p>
            ) : null}
            {!p.own && !record ? <p className="record">Not filled in yet.</p> : null}
          </li>
        );
      })}
    </ol>
  );
}
