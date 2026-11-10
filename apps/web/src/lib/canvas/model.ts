/**
 * The idea canvas (ARCHITECTURE §4.1): its answers, the exact question wording and "why we ask" lines, and the
 * choices. One module for the browser and the server, so both validate and score the same way.
 */

export type Mode = "quick" | "full";
export type Kind = "problem" | "problem_with_solution" | "business_idea";
export type Segment =
  "investors" | "distributors" | "amc_clients" | "issuer_clients" | "kfin_teams" | "other";
export type Category = "cost_saving" | "new_revenue" | "both" | "not_sure";
export type Play = "process_improvement" | "upsell" | "cross_sell" | "new_product" | "other";
export type Basis = "own_data" | "document" | "conversation" | "hunch";
export type Solved = "yes" | "partly" | "no" | "dont_know";
export type Player = "rta" | "amc" | "fintech" | "bank" | "global" | "internal" | "other";
export type Provenance = "submitter" | "suggested" | "accepted";

export type Reference = { kind: "link" | "note"; value: string; player: Player | null };

export type Estimate = {
  hours_saved_per_month: number | null;
  inr_saved_per_year: number | null;
  inr_revenue_one_time: number | null;
  inr_revenue_per_year: number | null;
  clients_who_would_pay: number | null;
  note: string | null;
};

export type Canvas = {
  mode: Mode;
  kind: Kind | null;
  one_line: string;
  details: string;
  who: { segments: Segment[]; frequency_or_reach: string; today_alternative: string };
  value: { category: Category | null; play: Play | null; estimate: Estimate; basis: Basis | null };
  ecosystem: { solved_elsewhere: Solved | null; references: Reference[]; our_advantage: string };
  solution: { approach: string; needs: string; risks: string };
  visibility: "org" | "committee";
  visibility_reason: string;
  declarations: { no_personal_data: boolean; own_work_or_credited: boolean; ip_terms: boolean };
  provenance: Record<string, Provenance>;
};

export const ESTIMATE_FIELDS = [
  ["hours_saved_per_month", "Hours saved a month"],
  ["inr_saved_per_year", "₹ saved a year"],
  ["inr_revenue_one_time", "₹ one-time revenue"],
  ["inr_revenue_per_year", "₹ revenue a year"],
  ["clients_who_would_pay", "Clients who would pay"],
] as const;

export function emptyCanvas(mode: Mode): Canvas {
  return {
    mode,
    kind: null,
    one_line: "",
    details: "",
    who: { segments: [], frequency_or_reach: "", today_alternative: "" },
    value: {
      category: null,
      play: null,
      estimate: {
        hours_saved_per_month: null,
        inr_saved_per_year: null,
        inr_revenue_one_time: null,
        inr_revenue_per_year: null,
        clients_who_would_pay: null,
        note: null,
      },
      basis: null,
    },
    ecosystem: { solved_elsewhere: null, references: [], our_advantage: "" },
    solution: { approach: "", needs: "", risks: "" },
    visibility: "org",
    visibility_reason: "",
    declarations: { no_personal_data: false, own_work_or_credited: false, ip_terms: false },
    provenance: {},
  };
}

/** §4.1, word for word. `why` is the "why we ask" line under each question. */
export const QUESTIONS = {
  kind: {
    label: "Is this a problem you face, a fix you've thought of, or a new business idea?",
    why: "So the right people look at it",
  },
  one_line: {
    label: "Say it in one line, as you would to the CEO in a lift",
    why: "One clear line is what gets read first",
  },
  details: { label: "Tell us more", why: "Context helps us find others who said the same thing" },
  segments: {
    label: "Who feels this problem, or who would pay for this?",
    why: "Ideas that touch clients and investors are weighed differently from internal ones",
  },
  frequency_or_reach: {
    label: "How often does it happen? Or: how many clients could use it?",
    why: "Size of the pain, or size of the market",
  },
  today_alternative: {
    label: "What do people do today instead?",
    why: "Today's workaround shows the cost of doing nothing",
  },
  category: {
    label: "Will this save cost, create new revenue, or both?",
    why: "This is the idea's category: how committees first sort ideas",
  },
  play: { label: "How does KFintech benefit?", why: "Tells us who would own it" },
  estimate: {
    label: "Rough size, if you can guess",
    why: "A range is fine. Committees compare ideas on value, and a rough guess beats a blank",
  },
  basis: {
    label: "What is the guess based on?",
    why: "Data-backed ideas carry more weight. A hunch is a fine start; just say so",
  },
  solved_elsewhere: {
    label:
      "Is it solved anywhere: another RTA, an AMC, a fintech, a bank, abroad, or another team inside KFintech?",
    why: "If someone has, we can learn from it or adopt it instead of building",
  },
  our_advantage: {
    label: "Why should KFintech do this, or do it better?",
    why: "This is our right to win. Committees look for it first in business ideas",
    prompts:
      "Think about the data we hold, clients we already serve, our regulatory role, rails we already run, cost.",
  },
  approach: { label: "How would you solve it?", why: "" },
  needs: { label: "What would it need: people, systems, partners, money?", why: "Helps size effort early" },
  risks: {
    label: "What could go wrong, including any regulatory concern?",
    why: "Naming risks early builds trust. It never counts against the idea",
  },
  research: {
    label: "Attach what you've already done and add links",
    why: "Research you've done saves weeks later",
  },
  visibility: { label: "Who can see this?", why: "" },
  // Quick capture is one box (DEC-094): one visible question, files if the person has them, and an optional
  // category under "Add more if you like". `why` is shown as the hint under the box, not as "Why we ask".
  quick_noticed: {
    label: "What's getting in your way, or what would you change?",
    why: "Say it any way you like, in any language. We'll help you shape it.",
  },
  quick_value: {
    label: "Does it save cost or earn revenue?",
    why: 'This is how committees first sort ideas. If you don\'t choose, we save it as "Not sure yet".',
  },
} as const;

/** Quick capture's single confirmation (DEC-094). Ticking it confirms all three declarations below. */
export const QUICK_DECLARATION =
  "I've left out investor and customer personal details, this is my own work or I've credited others, and I accept the IP terms.";

/** The keyboard-mic hint under the quick capture box (DEC-096), behind `capture.mic_hint`. */
export const MIC_HINT = "On your phone? Tap the mic on your keyboard and just talk, in any language.";

export const CHOICES = {
  kind: [
    ["problem", "A problem I face"],
    ["problem_with_solution", "A fix I've thought of"],
    ["business_idea", "A new business idea"],
  ],
  segments: [
    ["investors", "Investors"],
    ["distributors", "Distributors"],
    ["amc_clients", "AMC clients"],
    ["issuer_clients", "Issuer and corporate clients"],
    ["kfin_teams", "KFin teams"],
    ["other", "Others"],
  ],
  frequency: [
    ["daily", "Daily"],
    ["weekly", "Weekly"],
    ["monthly", "Monthly"],
    ["rarely", "Rarely"],
    ["unknown", "I don't know"],
  ],
  category: [
    ["cost_saving", "Cost saving"],
    ["new_revenue", "New revenue"],
    ["both", "Both"],
    ["not_sure", "Not sure yet"],
  ],
  play: [
    ["process_improvement", "Process improvement"],
    ["upsell", "Upsell to an existing client"],
    ["cross_sell", "Cross-sell to an existing client"],
    ["new_product", "New product or business line"],
    ["other", "Other"],
  ],
  basis: [
    ["own_data", "My own data"],
    ["document", "A document or report"],
    ["conversation", "A conversation with a client or colleague"],
    ["hunch", "A hunch"],
  ],
  solved: [
    ["yes", "Yes"],
    ["partly", "Partly"],
    ["no", "No"],
    ["dont_know", "I don't know"],
  ],
  player: [
    ["rta", "Another RTA"],
    ["amc", "An AMC"],
    ["fintech", "A fintech"],
    ["bank", "A bank"],
    ["global", "Abroad"],
    ["internal", "Another KFintech team"],
    ["other", "Other"],
  ],
  declarations: [
    ["no_personal_data", "There is no investor or customer personal data in this idea or its files."],
    ["own_work_or_credited", "This is my own work, or I have credited the people whose work it uses."],
    ["ip_terms", "I accept the terms for ideas shared on this platform, including intellectual property."],
  ],
} as const;

/** Every free-text field of a canvas, with its path: what the personal-data check scans. */
export function textFields(c: Canvas): Array<[string, string]> {
  const fields: Array<[string, string]> = [
    ["one_line", c.one_line],
    ["details", c.details],
    ["who.frequency_or_reach", c.who.frequency_or_reach],
    ["who.today_alternative", c.who.today_alternative],
    ["value.estimate.note", c.value.estimate.note ?? ""],
    ["ecosystem.our_advantage", c.ecosystem.our_advantage],
    ["solution.approach", c.solution.approach],
    ["solution.needs", c.solution.needs],
    ["solution.risks", c.solution.risks],
    ["visibility_reason", c.visibility_reason],
  ];
  c.ecosystem.references.forEach((r, i) => fields.push([`ecosystem.references.${i}.value`, r.value]));
  return fields.filter(([, v]) => v.trim().length > 0);
}

export const wordCount = (text: string) => text.trim().split(/\s+/).filter(Boolean).length;
