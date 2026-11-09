/**
 * Measured impact in plain words (DEC-071): time, money, effort and scale. Money only appears once Finance has
 * confirmed it (the worker leaves it out of everything public until then). Indian digit grouping for rupees.
 */
export type Measure = { value: number; unit: string; finance_confirmed?: boolean };
export type MeasureSet = Partial<Record<"time" | "money" | "effort" | "scale", Measure>>;

export const MEASURE_LABELS = { time: "Time", money: "Money", effort: "Effort", scale: "Scale" } as const;
const ORDER = ["time", "money", "effort", "scale"] as const;

const grouped = (n: number) => new Intl.NumberFormat("en-IN").format(n);

export function measureText(key: keyof typeof MEASURE_LABELS, m: Measure): string {
  if (key === "money") return `₹${grouped(m.value)} ${m.unit.replace(/^rupees /, "")}`;
  if (key === "time") return `${grouped(m.value)} ${m.unit} given back`;
  return `${grouped(m.value)} ${m.unit}`;
}

/** [label, words] for each measure present, in the fixed order. */
export function measureList(measures: MeasureSet | null | undefined): [string, string][] {
  const out: [string, string][] = [];
  for (const key of ORDER) {
    const m = measures?.[key];
    if (m) out.push([MEASURE_LABELS[key], measureText(key, m)]);
  }
  return out;
}

/** "No. 17, Ananya Rao" when they said yes to showing their name, else "One No. 17". */
export const oneName = (number: number | null, name: string | null) =>
  name ? name : number ? `One No. ${number}` : "A One";
