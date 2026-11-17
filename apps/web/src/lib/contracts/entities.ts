/**
 * The shapes the screens need (1pc-handoff/06-contracts/E-ENTITIES.md, draft 0, rev 1), as the API returns them.
 * They are wire shapes, not the database: `db/migrations/20261121500100_handoff_cutover.sql` stores them and the
 * server shapes each by who asks (P-PRODUCT.privacy, L-AUDIT.permissions). Dates are ISO 8601 strings in UTC.
 * Enum unions come from `enums.ts` (one JSON source with Python).
 */
import type {
  ActionStyle,
  Basis,
  Brings,
  Channel,
  ConversationAudience,
  CrewReason,
  DecisionChoice,
  Device,
  DraftStep,
  EmberState,
  FileKind,
  FileState,
  HiddenKind,
  HiddenState,
  IdeaPart,
  IdeaStatus,
  ImpactMeasured,
  InboxKind,
  Kind,
  LinkScope,
  LinkState,
  MatchStrength,
  MergeRequestState,
  MergeVia,
  MessageVia,
  OneFlag,
  OutsideTools,
  PartState,
  QuestionSetState,
  Role,
  ShowReason,
  SolvedAlready,
  SortingSource,
  Stage,
  StageStateValue,
  TeamUpState,
  Tier,
  TimeToAnswer,
  WallStageKey,
  WindowState,
} from "./enums";

export type IsoDate = string;

// ---------------------------------------------------------------------------------------------------------------
// E-ENTITIES.person
// ---------------------------------------------------------------------------------------------------------------
export interface PersonSettings {
  show_name_on_wall: boolean;
  teams: boolean;
  email: boolean;
  reminders: boolean;
  shortcut_p: boolean;
  sidebar_folded: boolean;
}

export interface OneRecord {
  number: number;
  flag: OneFlag;
  since: IsoDate;
  number_locked_at: IsoDate;
  brief: string;
}

export interface Person {
  id: string;
  name: string;
  first_name: string;
  initials: string;
  area: string;
  city: string;
  /** Never shown to others. */
  email: string;
  roles: Role[];
  tier: Tier;
  one?: OneRecord;
  /** Returned only to the person themselves. */
  points?: number;
  /** Self only. */
  settings?: PersonSettings;
}

export interface PersonRef {
  id: string;
  name: string;
  first_name: string;
  initials: string;
  area?: string;
  city?: string;
  /** "from the review desk", "from the Ones Committee". */
  role_label?: string;
}

// ---------------------------------------------------------------------------------------------------------------
// E-ENTITIES.files
// ---------------------------------------------------------------------------------------------------------------
export interface FileItem {
  id: string;
  kind: FileKind;
  name: string;
  type: string;
  size?: number;
  pages?: number;
  count?: number;
  state: FileState | LinkState;
  problem?: string;
  hidden_note?: string;
  link_scope?: LinkScope;
  url?: string;
  added_by: PersonRef;
  added_at: IsoDate;
  view_url?: string;
}

// ---------------------------------------------------------------------------------------------------------------
// E-ENTITIES.draft
// ---------------------------------------------------------------------------------------------------------------
export interface HiddenSpan {
  /** Positions in the owner's own text. */
  start: number;
  end: number;
  kind: HiddenKind;
}

export interface HiddenDetail {
  id: string;
  kind: HiddenKind;
  /** "Folio ••••89". */
  masked: string;
  state: HiddenState;
  reason?: ShowReason;
  shown_at?: IsoDate;
}

export interface Message {
  id: string;
  text: string;
  lang?: string;
  at: IsoDate;
  device: Device;
  via: MessageVia;
  files: FileItem[];
  spans: HiddenSpan[];
}

export interface Part<T> {
  state: PartState;
  value: T;
  why?: string;
  source_quote?: string;
  mean_ms?: number;
}

export interface Choice<T> {
  value: T;
  source: SortingSource;
  why?: string;
}

export interface Sorting {
  affects: Choice<string[]>;
  kind: Choice<Kind>;
  area: Choice<string>;
  brings: Choice<Brings[]>;
  confirmed: boolean;
}

export interface Range {
  low: number;
  high?: number;
  /** "70 to 150 hours a month". */
  text: string;
}

export interface Worth {
  hours_month?: Range;
  cost_month?: Range;
  revenue_month?: Range;
  outside_tools?: OutsideTools;
}

export interface Fix {
  how: string;
  needs?: string;
  solved_already?: SolvedAlready;
  solved_note?: string;
  worth?: Worth;
  basis?: Basis;
  risks?: string;
  ready_count: number;
  included: boolean;
}

export interface DraftOrigin {
  subject?: string;
  received_at: IsoDate;
  /** "Fwd: R07 rejections again". */
  note: string;
}

export interface DraftMergeRequest {
  other_idea_id: string;
  state: MergeRequestState;
  note: string;
  lead_reason?: string;
}

export interface Draft {
  id: string;
  owner_id: string;
  channel: Channel;
  origin?: DraftOrigin;
  messages: Message[];
  parts: {
    title: Part<string>;
    summary: Part<string>;
    often: Part<string | null>;
    who: Part<string[]>;
    value: Part<Brings[]>;
    area: Part<string>;
    similar: Part<SimilarMatch[]>;
  };
  hidden: HiddenDetail[];
  sorting: Sorting;
  files: FileItem[];
  fix?: Fix;
  helpers?: { picks: string[]; text?: string };
  merge_request?: DraftMergeRequest;
  step: DraftStep;
  saved_at: IsoDate;
  saved_on: { device: Device; this_device: boolean };
  /** L-DRAFT.parts/7: title, summary and area present. */
  ready: boolean;
  min_chars: number;
  char_count: number;
  receipt?: string[];
  suggestions?: string[];
}

// ---------------------------------------------------------------------------------------------------------------
// E-ENTITIES.review
// ---------------------------------------------------------------------------------------------------------------
export interface Answer {
  id: string;
  question_id: string;
  text: string;
  files: FileItem[];
  by: PersonRef;
  at: IsoDate;
  added_to: IdeaPart;
}

export interface Question {
  id: string;
  part: IdeaPart;
  text: string;
  suggested: boolean;
  answer?: Answer;
}

export interface QuestionSet {
  id: string;
  idea_id: string;
  by: PersonRef;
  state: QuestionSetState;
  sent_at?: IsoDate;
  seen_at?: IsoDate;
  due_at?: IsoDate;
  time_to_answer: TimeToAnswer;
  questions: Question[];
  overdue: boolean;
}

/** E-ENTITIES `Window` (renamed so it never shadows the DOM's `Window`). */
export interface DecisionWindow {
  state: WindowState;
  opens_at: IsoDate;
  closes_at: IsoDate;
  max_closes_at: IsoDate;
  extended_times: number;
}

export interface Reversal {
  to: DecisionChoice;
  note: string;
  by: PersonRef;
  at: IsoDate;
  return_at?: IsoDate;
}

export interface Decision {
  id: string;
  idea_id: string;
  choice: DecisionChoice;
  reason: string;
  by: PersonRef;
  at: IsoDate;
  joined_with?: string;
  return_at?: IsoDate;
  team_by?: IsoDate;
  window: DecisionWindow;
  reversal?: Reversal;
}

// ---------------------------------------------------------------------------------------------------------------
// E-ENTITIES.crew
// ---------------------------------------------------------------------------------------------------------------
export interface IdeaRef {
  id: string;
  title: string;
  status: IdeaStatus;
  /** "IDEA-2026-001481, with the review desk". */
  meta?: string;
}

export interface TeamUpRequest {
  id: string;
  idea_id: string;
  from: PersonRef;
  note: string;
  brought: IdeaRef[];
  state: TeamUpState;
  lead_reason?: string;
  sent_at: IsoDate;
  answered_at?: IsoDate;
}

export interface Merge {
  id: string;
  lead_idea_id: string;
  merged_idea_id: string;
  by: PersonRef;
  via: MergeVia;
  team_up: boolean;
  note: string;
  at: IsoDate;
  window?: DecisionWindow;
}

export interface IdeaPreview {
  id: string;
  title: string;
  status: IdeaStatus;
  area: string;
  city: string;
  shared_at: IsoDate;
  lead: PersonRef;
  crew_faces: PersonRef[];
  crew_count: number;
  /** One masked sentence, never raw words (non-negotiable 7). */
  in_their_words: string;
  looking_for?: string;
  hue: 1 | 2;
  /** Reviewers only. */
  compare?: { often?: string; who?: string; worth?: string };
  /** Reviewers only, with `?compare_with=<id>`: the same three rows for the idea they are looking at, for the
   * column "Next to Kavya's" (C-PREVIEW.anatomy/4, BLD-C090). */
  compare_with?: {
    id: string;
    title: string;
    owner: PersonRef;
    often?: string;
    who?: string;
    worth?: string;
  };
}

export interface SimilarMatch {
  idea: IdeaPreview;
  strength: MatchStrength;
  reason: string;
  my_request?: TeamUpRequest;
}

export interface CrewCard extends IdeaPreview {
  reason_kind: CrewReason;
  /** "Same R07 SMS as your idea from Saturday". */
  reason: string;
}

// ---------------------------------------------------------------------------------------------------------------
// E-ENTITIES.idea
// ---------------------------------------------------------------------------------------------------------------
export interface StageState {
  stage: Stage;
  state: StageStateValue;
  detail?: string;
  at?: IsoDate;
}

export interface Idea {
  /** "IDEA-2026-001481". */
  id: string;
  status: IdeaStatus;
  kind: Kind;
  title: string;
  /** The public short summary. */
  summary: string;
  often?: string;
  affects: string[];
  brings: Brings[];
  area: string;
  city: string;
  /** null to others when the sharer hides their name. */
  sharer: PersonRef | null;
  /** After a merge, both sharers. */
  credited: PersonRef[];
  shared_at: IsoDate;
  /** "Done in 40 seconds". */
  share_seconds?: number;
  /** Five, E-ENUMS.stage. */
  stages: StageState[];
  crew: { lead: PersonRef; members: PersonRef[]; count: number; ones_count: number };
  linked_similar_count: number;
  wall: { shown: boolean; opened_7d: number };
  merged_into?: string;
  // Below: only for the sharer, crew (not own_words), reviewers, committee and the build team.
  /** Masked for everyone but the sharer. */
  own_words?: Message[];
  hidden?: HiddenDetail[];
  files?: FileItem[];
  fix?: Fix;
  worth?: { sharer: Worth; reviewer?: Worth & { note?: string; by: PersonRef; at: IsoDate } };
  answers_by_part?: Partial<Record<IdeaPart, Answer[]>>;
  edit_window?: { open: boolean; closes_at: IsoDate; opened_by_desk_at?: IsoDate };
  review?: { decide_by: IsoDate; reviewer?: PersonRef; opened_at?: IsoDate };
  decision?: Decision;
  /** "3 versions. Title changed once, sorting confirmed." */
  versions?: { count: number; summary: string };
  kept_separate?: boolean;
  next_step: { sentence: string; action?: { label: string; to: string } };
}

// ---------------------------------------------------------------------------------------------------------------
// E-ENTITIES.inbox
// ---------------------------------------------------------------------------------------------------------------
export interface Action {
  label: string;
  to?: string;
  op?: string;
  style: ActionStyle;
}

export interface InboxItem {
  id: string;
  kind: InboxKind;
  from: PersonRef | "system";
  idea?: IdeaRef;
  line: string;
  at: IsoDate;
  unread: boolean;
  needs_you: boolean;
  due?: { at: IsoDate; label: string };
  archived: boolean;
  /** By kind. */
  body: Record<string, unknown>;
  actions: Action[];
}

export type ConversationEntry =
  | { type: "event"; text: string; at: IsoDate }
  | { type: "message"; from: PersonRef; text: string; files: FileItem[]; at: IsoDate; mentions: PersonRef[] }
  | { type: "questions"; set: QuestionSet }
  | { type: "answers"; set_id: string; answers: Answer[]; at: IsoDate };

export interface Conversation {
  idea: IdeaRef;
  audience: ConversationAudience;
  participants: { person: PersonRef; doing: string }[];
  entries: ConversationEntry[];
}

// ---------------------------------------------------------------------------------------------------------------
// E-ENTITIES.wall
// ---------------------------------------------------------------------------------------------------------------
export interface WallStage {
  stage: WallStageKey;
  count: number;
  items: { id: string; title: string; kind: Kind; area: string; crew_count: number }[];
}

export interface JustInRow {
  id: string;
  title: string;
  kind: Kind;
  area: string;
  shared_at: IsoDate;
  opened_7d: number;
  crew_count: number;
  ones_count: number;
}

export interface OneCard {
  number: number;
  person: PersonRef;
  tier: Tier;
  tier_name: string;
  flag: OneFlag;
  brief: string;
}

export interface OnePost {
  one: OneCard;
  text: string;
  ago: string;
  shipped: boolean;
  adopted_by?: number;
  figure: { value: string; line: string };
  likes: number;
  comments: number;
  thread_to: string;
}

export interface ImpactTotals {
  hours_month: number;
  money_year: number;
  fixes_measured: number;
  reached: { count: number; noun: string };
}

export interface LiveFix {
  what: string;
  change: string;
  measured: ImpactMeasured;
  due?: IsoDate;
  team: string;
}

export interface ImpactFigure {
  value: string;
  line: string;
}

export interface Impact {
  time?: ImpactFigure;
  money?: ImpactFigure & { finance_confirmed: boolean };
  effort?: ImpactFigure;
  scale?: ImpactFigure;
}

export interface EmberIssue {
  number: number;
  month: string;
  headline: string;
  items: string[];
  state: EmberState;
  to?: string;
}
