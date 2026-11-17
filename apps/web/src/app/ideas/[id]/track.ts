import type { StageKey, TrackStage } from "@/components/ui/track";

/** A stage as the idea page's API sends it (E-ENTITIES `StageState`, with the words worked out on the server). */
export type StageWords = { stage: string; state: string; detail?: string | null; label?: string };

const KEY: Record<string, StageKey> = {
  shared: "shared",
  checked_matched: "checked",
  checked: "checked",
  reviewed: "reviewed",
  built: "built",
  shipped: "shipped",
};

const STATE: Record<string, TrackStage["state"]> = {
  done: "done",
  now: "now",
  to_come: "next",
  not_going_ahead: "off",
};

const KEYS: StageKey[] = ["shared", "checked", "reviewed", "built", "shipped"];

/** C-TRACK's five stages from the API's (S-06.layout/3, S-09.layout/4); null when the idea has none (merged). A stage
 * the API did not send, or sent under a name this page does not know, is drawn as still to come with no line, so the
 * stages that did arrive are always shown. */
export function toTrack(stages: StageWords[] | undefined): Record<StageKey, TrackStage> | null {
  if (!stages?.length) return null;
  const out: Partial<Record<StageKey, TrackStage>> = {};
  for (const s of stages) {
    const key = KEY[s.stage];
    if (!key) continue;
    out[key] = { state: STATE[s.state] ?? "next", line: s.detail ?? undefined };
  }
  if (!KEYS.some((k) => out[k])) return null;
  return Object.fromEntries(KEYS.map((k) => [k, out[k] ?? { state: "next" }])) as Record<
    StageKey,
    TrackStage
  >;
}
