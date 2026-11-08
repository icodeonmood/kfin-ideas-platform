/** The canvas configuration from the company repo (limits, rubric, examples), cached for a minute. */
import type { CanvasLimits, StrengthRubric } from "@/lib/canvas/rules";

import { workerJson } from "./worker";

export type CanvasExample = {
  slug: string;
  section: string;
  question: string;
  weak: string;
  strong: string;
  why: string;
};

export type CanvasConfig = {
  rules_version: Record<string, string>;
  commit: string | null;
  canvas: CanvasLimits & {
    join_context_min_chars: number;
    draft_retention_days: number;
    nudge_days_after_quick_capture: number[];
    nudge_max: number;
  };
  canvas_strength: StrengthRubric;
  attachments: {
    max_files: number;
    max_mb_each: number;
    max_mb_per_idea: number;
    allowed: string[];
    day_one_checked: string[];
    day_one_held: string[];
  };
  scan: { poll_interval_s: number };
  examples: CanvasExample[];
};

let cache: { at: number; value: CanvasConfig } | undefined;

export async function canvasConfig(): Promise<CanvasConfig> {
  if (cache && Date.now() - cache.at < 60_000) return cache.value;
  const value = await workerJson<CanvasConfig>("/internal/canvas-config");
  cache = { at: Date.now(), value };
  return value;
}

export function kfinDomains(): string[] {
  return (process.env.KFIN_EMAIL_DOMAINS ?? "")
    .split(",")
    .map((d) => d.trim().toLowerCase())
    .filter(Boolean);
}
