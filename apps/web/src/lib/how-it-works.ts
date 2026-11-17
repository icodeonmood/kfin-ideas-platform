/**
 * S-H4 "What happens after you share": the five stages, each with one or two sentences and its promise (S-H4/1).
 * Words from reference/copy/How.md. The review promise comes from configuration (rules/promises.md, BLD-A181), so
 * a change there changes the page with no release (S-H4/3); the other four are words, not numbers.
 */
export type Stage = { title: string; body: string; when: string };

export function stages(decideByWorkingDays: number): Stage[] {
  return [
    {
      title: "Shared",
      body: "You get a reference straight away, and your idea is saved as you wrote it.",
      when: "About two minutes",
    },
    {
      title: "Checked and matched",
      body: "Personal details are hidden. Ideas like yours are linked, so you can team up.",
      when: "Automatic, minutes",
    },
    {
      title: "Reviewed",
      body: "The review desk may ask you questions, each with a clear time to answer. You get a decision with a reason.",
      when: `Within ${decideByWorkingDays} working ${decideByWorkingDays === 1 ? "day" : "days"}`,
    },
    {
      title: "Built",
      body: "If it’s picked, a team builds it. You can join that team.",
      when: "Depends on the fix",
    },
    {
      title: "Shipped",
      body: "We measure what changed. Fixes that make a measured difference make you one of The Ones.",
      when: "After it’s live",
    },
  ];
}
