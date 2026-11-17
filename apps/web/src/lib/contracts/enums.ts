/**
 * The 1% Club's enums (1pc-handoff/06-contracts/E-ENUMS.md), derived from the one JSON source
 * `contracts/1pc/enums.json` through the generated `enums.gen.ts` (`npm run sync:shared`). Never write a wire
 * value by hand elsewhere: import the union or the list from here. Python reads the same file (`onepc/enums.py`).
 */
import { ONEPC } from "./enums.gen";

type Enums = typeof ONEPC.enums;
export type EnumName = keyof Enums;
export type EnumValue<K extends EnumName> = Enums[K]["values"][number];

/** The values of one enum, in the pack's order. */
export function enumValues<K extends EnumName>(name: K): readonly EnumValue<K>[] {
  return ONEPC.enums[name].values as readonly EnumValue<K>[];
}

/** True when `value` is one of the enum's wire values (for parsing request bodies and query strings). */
export function isEnumValue<K extends EnumName>(name: K, value: unknown): value is EnumValue<K> {
  return (ONEPC.enums[name].values as readonly unknown[]).includes(value);
}

// E-ENUMS
export type IdeaStatus = EnumValue<"idea_status">;
export type Stage = EnumValue<"stage">;
export type StageStateValue = EnumValue<"stage_state">;
export type Kind = EnumValue<"kind">;
export type Brings = EnumValue<"brings">;
export type SortingSource = EnumValue<"sorting_source">;
export type IdeaPart = EnumValue<"part">;
export type DecisionChoice = EnumValue<"decision">;
export type ReturnIn = EnumValue<"return_in">;
export type WindowState = EnumValue<"window_state">;
export type QuestionSetState = EnumValue<"question_set_state">;
export type TimeToAnswer = EnumValue<"time_to_answer">;
export type TeamUpState = EnumValue<"teamup_state">;
export type MergeRequestState = EnumValue<"merge_request_state">;
export type FileState = EnumValue<"file_state">;
export type LinkState = EnumValue<"link_state">;
export type LinkScope = EnumValue<"link_scope">;
export type HiddenKind = EnumValue<"hidden_kind">;
export type HiddenState = EnumValue<"hidden_state">;
export type ShowReason = EnumValue<"show_reason">;
export type SolvedAlready = EnumValue<"solved_already">;
export type Basis = EnumValue<"basis">;
export type OutsideTools = EnumValue<"outside_tools">;
export type DraftPartKey = EnumValue<"draft_part">;
export type PartState = EnumValue<"part_state">;
export type Channel = EnumValue<"channel">;
export type DraftStep = EnumValue<"draft_step">;
export type InboxKind = EnumValue<"inbox_kind">;
export type Role = EnumValue<"role">;
export type IdeaRole = EnumValue<"idea_role">;
export type Tier = EnumValue<"tier">;
export type OneFlag = EnumValue<"one_flag">;
export type MatchStrength = EnumValue<"match_strength">;
export type CrewReason = EnumValue<"crew_reason">;

// E-ENTITIES literal unions
export type MessageVia = EnumValue<"message_via">;
export type Device = EnumValue<"device">;
export type ConversationType = EnumValue<"conversation_type">;
export type ConversationAudience = EnumValue<"conversation_audience">;
export type MergeVia = EnumValue<"merge_via">;
export type FileKind = EnumValue<"file_kind">;
export type ActionStyle = EnumValue<"action_style">;
export type WallStageKey = EnumValue<"wall_stage">;
export type ImpactMeasured = EnumValue<"impact_measured">;
export type EmberState = EnumValue<"ember_state">;

// A-API query and body values
export type TeamUpAnswer = EnumValue<"teamup_answer">;
export type MergeLead = EnumValue<"merge_lead">;
export type MyIdeasList = EnumValue<"my_ideas_list">;
export type MyIdeasSort = EnumValue<"my_ideas_sort">;
export type MyIdeasFilter = EnumValue<"my_ideas_filter">;
export type InboxTab = EnumValue<"inbox_tab">;
export type DeskSort = EnumValue<"desk_sort">;
export type CommitteeTab = EnumValue<"committee_tab">;
export type CommitteeSort = EnumValue<"committee_sort">;
export type WallSort = EnumValue<"wall_sort">;

// Repo-side values for the pack's tables (lane E)
export type CrewMemberRole = EnumValue<"crew_member_role">;
export type WorthSide = EnumValue<"worth_side">;
export type SimilarOutcome = EnumValue<"similar_outcome">;
export type HiddenFoundBy = EnumValue<"hidden_found_by">;
export type SealedSource = EnumValue<"sealed_source">;
export type FlagVariant = EnumValue<"flag_variant">;
export type ClockKind = EnumValue<"clock_kind">;

/** "Closed" in filters, and "Picked and building" (E-ENUMS.idea-status). */
export const CLOSED_STATUSES: readonly IdeaStatus[] = ONEPC.enums.idea_status.groups.closed;
export const PICKED_AND_BUILDING: readonly IdeaStatus[] = ONEPC.enums.idea_status.groups.picked_and_building;

export const IDEA_STATUS_LABEL: Readonly<Record<IdeaStatus, string>> = ONEPC.enums.idea_status.labels;
export const IDEA_STATUS_PILL: Readonly<Record<IdeaStatus, "neutral" | "blue" | "warn" | "ok">> =
  ONEPC.enums.idea_status.pill;
export const STAGE_LABEL: Readonly<Record<Stage, string>> = ONEPC.enums.stage.labels;
export const BRINGS_LABEL: Readonly<Record<Brings, string>> = ONEPC.enums.brings.labels;
export const PART_LABEL: Readonly<Record<IdeaPart, string>> = ONEPC.enums.part.labels;
export const DECISION_LABEL: Readonly<Record<DecisionChoice, string>> = ONEPC.enums.decision.labels;
export const SHOW_REASON_LABEL: Readonly<Record<ShowReason, string>> = ONEPC.enums.show_reason.labels;
export const BASIS_LABEL: Readonly<Record<Basis, string>> = ONEPC.enums.basis.labels;
export const WALL_KIND_LABEL: Readonly<Record<Kind, string>> = ONEPC.enums.kind.wall_labels;
export const TIER_NAME: Readonly<Record<`${Tier}`, string>> = ONEPC.enums.tier.labels;
export const DEFAULT_TIME_TO_ANSWER: TimeToAnswer = ONEPC.enums.time_to_answer.default;
export const DEFAULT_RETURN_IN: ReturnIn = ONEPC.enums.return_in.default;

/** Each database CHECK and the enum(s) it must equal; the migration test reads this (BLD-E006). */
export const DB_CHECKS: Readonly<Record<string, readonly EnumName[]>> = ONEPC.db_checks;
export const DB_VALUES_OUTSIDE_THE_PACK: Readonly<Record<string, readonly string[]>> =
  ONEPC.db_values_outside_the_pack;
