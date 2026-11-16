/**
 * Request and response shapes per resource (1pc-handoff/06-contracts/A-API.md, draft 0, rev 1). Paths are the
 * pack's proposals; a lane that maps one to an existing route records it in 00-overview/REPO-MAPPING.md. Error
 * `message`s come from V-FIELDS copy; codes are listed per operation.
 */
import type {
  CommitteeSort,
  CommitteeTab,
  DecisionChoice,
  DeskSort,
  DraftPartKey,
  DraftStep,
  IdeaPart,
  InboxTab,
  Kind,
  MergeLead,
  MessageVia,
  MyIdeasList,
  MyIdeasSort,
  ReturnIn,
  ShowReason,
  TeamUpAnswer,
  TimeToAnswer,
  WallSort,
  Brings,
  Channel,
  OutsideTools,
} from "./enums";
import type {
  CrewCard,
  Decision,
  Draft,
  EmberIssue,
  FileItem,
  Fix,
  HiddenDetail,
  HiddenSpan,
  Idea,
  IdeaPreview,
  ImpactTotals,
  Impact,
  InboxItem,
  IsoDate,
  JustInRow,
  LiveFix,
  Merge,
  OneCard,
  OnePost,
  Person,
  PersonSettings,
  QuestionSet,
  SimilarMatch,
  Sorting,
  TeamUpRequest,
  WallStage,
  Worth,
  Conversation,
  ConversationEntry,
} from "./entities";

// ---------------------------------------------------------------------------------------------------------------
// A-API.conventions
// ---------------------------------------------------------------------------------------------------------------
/** Every error the UI reads (A-API.conventions/2). `message` is ready to show under `field`. */
export interface ApiError<C extends string = ErrorCode> {
  error: { code: C; message: string; field?: string; retry_after?: number } & Record<string, unknown>;
}

/** Lists (A-API.conventions/4). */
export interface ListOf<T, K extends string = string> {
  items: T[];
  total: number;
  counts?: Partial<Record<K, number>>;
  next?: string;
}

/** Writes that create something take this header (A-API.conventions/3). */
export const IDEMPOTENCY_HEADER = "Idempotency-Key";

/** A date the UI shows as a sentence: raw and labelled by the server (A-API.conventions/6). */
export interface DueLabel {
  due_at: IsoDate;
  label: string;
}

export type ErrorCode =
  // A-API.auth
  | "sso_unavailable"
  | "not_work_email"
  | "rate_limited"
  | "account_disabled"
  | "wrong_code"
  | "code_expired"
  | "expired"
  // A-API.drafts
  | "reason_required"
  | "note_too_short"
  | "sorting_unconfirmed"
  | "file_blocked"
  | "merge_waiting"
  | "not_ready"
  | "offline_queued"
  // A-API.files
  | "too_big"
  | "type_not_allowed"
  | "locked"
  | "not_a_link"
  // A-API.ideas
  | "edit_window_closed"
  // A-API.questions
  | "nothing_answered"
  // A-API.desk
  | "choice_required"
  | "reason_too_short"
  // A-API.committee
  | "at_limit"
  | "to_required"
  | "window_closed"
  | "already_reversed"
  // A-API.team-up
  | "already_requested"
  | "already_on_crew"
  | "idea_closed"
  // A-API.inbox
  | "needs_you"
  | "empty_message"
  // A-API.wall
  | "taken"
  | "out_of_range";

// ---------------------------------------------------------------------------------------------------------------
// A-API.auth
// ---------------------------------------------------------------------------------------------------------------
export interface SignInIntent {
  to: string;
  draft_id?: string;
  step?: DraftStep;
}
export interface SsoStartRequest {
  intent?: SignInIntent;
}
export type SsoStartResponse = { redirect_url: string } | { signed_in: true; to: string };
export interface CodeSendRequest {
  email: string;
  intent?: SignInIntent;
}
export interface CodeSendResponse {
  sent_to: string;
  valid_minutes: number;
  resend_in_seconds: number;
}
export interface CodeVerifyRequest {
  email: string;
  code: string;
}
export interface CodeVerifyResponse {
  signed_in: true;
  to: string;
}
export interface SessionResponse {
  person: Person;
  expires_at: IsoDate;
  intent?: SignInIntent;
}
/** `expired` carries the open draft so S-02 can say what is kept. */
export interface SessionExpiredError extends ApiError<"expired"> {
  error: ApiError<"expired">["error"] & {
    draft?: { id: string; title: string; saved_at: IsoDate; saved_on: Draft["saved_on"]; step: DraftStep };
  };
}

// ---------------------------------------------------------------------------------------------------------------
// A-API.me, A-API.home
// ---------------------------------------------------------------------------------------------------------------
export type MeResponse = Person & Required<Pick<Person, "settings">>;
export type SettingsPatch = Partial<PersonSettings>;
export interface ShellResponse {
  inbox_unread: number;
  drafts: { id: string; title: string; saved_label: string }[];
  ideas: { id: string; title: string; status_dot: string }[];
  desk?: { waiting: { id: string; title: string; label: string }[] };
  committee?: { closing: { id: string; title: string; label: string }[] };
}
export interface HomeResponse {
  first_visit: boolean;
  needs_you: { total: number; top: InboxItem[] };
  ideas: { total: number; top: Idea[] };
  crew: { total: number; top: CrewCard[] };
  ones: OnePost[];
  ways: { arrived: number };
}

// ---------------------------------------------------------------------------------------------------------------
// A-API.drafts, A-API.draft-stream
// ---------------------------------------------------------------------------------------------------------------
export interface CreateDraftRequest {
  text?: string;
  files?: string[];
  channel: Channel;
}
export interface AddMessageRequest {
  text: string;
  via: MessageVia;
  files?: string[];
}
export interface AddMessageResponse {
  run_id: string;
}
export type PartPatch = { value: unknown } | { pinned: false };
export type SortingPatch =
  { affects?: string[]; kind?: Kind; area?: string; brings?: Brings[] } | { confirm: true };
export type SortingResponse = Sorting;
export interface ShowHiddenRequest {
  reason: ShowReason;
}
export type HiddenResponse = HiddenDetail;
export type FixRequest = Omit<Fix, "ready_count">;
export type FixResponse = Fix;
export interface HelpersRequest {
  picks: string[];
  text?: string;
}
export interface DraftStepPatch {
  step: DraftStep;
}
export interface MergeRequestCreate {
  other_idea_id: string;
  note: string;
}
export interface SubmitRequest {
  declaration_version: string;
}
export interface SubmitResponse {
  idea_id: string;
}

/** Server-sent events on GET /drafts/:id/stream, one run per message. */
export type DraftStreamEvent =
  | { event: "run"; data: { run_id: string; parts: { key: DraftPartKey; mean_ms: number }[] } }
  | { event: "hidden"; data: { spans: HiddenSpan[]; details: HiddenDetail[] } }
  | {
      event: "part";
      data: {
        key: DraftPartKey;
        state: "filled" | "failed";
        value: unknown;
        why?: string;
        source_quote?: string;
        took_ms: number;
      };
    }
  | { event: "receipt"; data: { lines: string[]; suggestions: string[] } }
  | { event: "done"; data: { ready: boolean } };

// ---------------------------------------------------------------------------------------------------------------
// A-API.files
// ---------------------------------------------------------------------------------------------------------------
export interface CreateLinkRequest {
  url: string;
  draft_id?: string;
  idea_id?: string;
  answer_id?: string;
}
export type FileResponse = FileItem;
export interface UploadConfig {
  limit_mb: number;
  types: string[];
  help_text: string;
}

// ---------------------------------------------------------------------------------------------------------------
// A-API.ideas
// ---------------------------------------------------------------------------------------------------------------
export type IdeaResponse = Idea;
export type IdeaPreviewResponse = IdeaPreview;
export interface MyIdeasQuery {
  list?: MyIdeasList;
  filter?: string;
  sort?: MyIdeasSort;
  q?: string;
}
export interface MyIdeasResponse extends ListOf<Idea> {
  lists?: Partial<Record<MyIdeasList, number>>;
  search?: { sentence: string; matched_on: string[]; closest: Idea[] };
}
export interface IdeaPatch {
  title?: string;
  summary?: string;
  often?: string;
  sorting?: SortingPatch;
  fix?: FixRequest;
  helpers?: HelpersRequest;
}
export interface WithdrawRequest {
  reason?: string;
}
export interface IdeaVersion {
  n: number;
  changed_fields: string[];
  at: IsoDate;
}
export type SimilarResponse = SimilarMatch[];

// ---------------------------------------------------------------------------------------------------------------
// A-API.questions
// ---------------------------------------------------------------------------------------------------------------
export type SuggestedQuestionsResponse = { part: IdeaPart; text: string }[];
export interface SendQuestionSetRequest {
  questions: { part: IdeaPart; text: string }[];
  time_to_answer: TimeToAnswer;
}
export type QuestionSetResponse = QuestionSet & { due?: DueLabel };
export interface ExtendQuestionSetRequest {
  days: number;
}
export interface SaveAnswerRequest {
  text: string;
  file_ids?: string[];
}

// ---------------------------------------------------------------------------------------------------------------
// A-API.desk, A-API.committee
// ---------------------------------------------------------------------------------------------------------------
export interface DeskQuery {
  tab?: string;
  sort?: DeskSort;
  q?: string;
}
export interface DeskRow {
  idea: Idea;
  questions_state: string;
  time_left: { label: string; variant: string };
  decide_by: DueLabel;
  action: { label: string; to: string };
}
export interface DeskResponse extends ListOf<DeskRow> {
  sentence: string;
}
export interface WorthRequest {
  worth: Worth & { outside_tools?: OutsideTools };
  kind?: Kind;
  area?: string;
  note?: string;
}
export interface DecisionRequest {
  choice: DecisionChoice;
  reason: string;
  joined_with?: string;
  return_in?: ReturnIn;
}
export type DecisionResponse = Decision;
export interface DeskMergeRequest {
  other_idea_id: string;
  lead: MergeLead;
  team_up: boolean;
  note: string;
}
export type DeskMergeResponse = Merge;
export interface ListenAudioResponse {
  url: string;
  total_seconds: number;
  chapters: { part: IdeaPart; at: number }[];
}
export interface CommitteeQuery {
  tab?: CommitteeTab;
  sort?: CommitteeSort;
}
export interface CommitteeRow {
  idea: Idea;
  decision: Decision;
}
export interface CommitteeResponse extends ListOf<CommitteeRow, CommitteeTab> {
  sentence: string;
}
export interface ReverseRequest {
  to: DecisionChoice;
  note: string;
  return_in?: ReturnIn;
}

// ---------------------------------------------------------------------------------------------------------------
// A-API.team-up
// ---------------------------------------------------------------------------------------------------------------
export interface TeamUpDraftNote {
  note: string;
  own_ideas: { id: string; title: string; status: string }[];
}
export interface TeamUpCreate {
  note: string;
  brought_idea_ids: string[];
}
export type TeamUpResponse = TeamUpRequest;
export interface TeamUpAnswerRequest {
  answer: TeamUpAnswer;
  reason?: string;
}
export interface CrewResponse extends ListOf<CrewCard> {
  joined: number;
  pending: number;
  passed: number;
}

// ---------------------------------------------------------------------------------------------------------------
// A-API.inbox
// ---------------------------------------------------------------------------------------------------------------
export interface InboxQuery {
  tab?: InboxTab;
}
export interface InboxResponse extends ListOf<InboxItem, InboxTab> {
  unread: number;
}
export type ConversationResponse = Conversation;
export interface ConversationMessageCreate {
  text: string;
  file_ids?: string[];
  mentions?: string[];
}

// ---------------------------------------------------------------------------------------------------------------
// A-API.wall, A-API.ones, A-API.search, A-API.config
// ---------------------------------------------------------------------------------------------------------------
export type KindlingResponse = [WallStage, WallStage, WallStage];
export interface JustInQuery {
  kind?: Kind;
  sort?: WallSort;
  limit?: number;
  offset?: number;
}
export type JustInResponse = ListOf<JustInRow>;
export type OnesResponse = OneCard[];
export interface ImpactResponse {
  totals: ImpactTotals;
  live: LiveFix[];
}
export type EmberResponse = EmberIssue[];
export type OnePostsResponse = OnePost[];
export interface OneDashboardResponse {
  one: OneCard;
  idea: Idea | null;
  impact: Impact;
  number_window: { open: boolean; until?: IsoDate };
  tier_moment?: { from: number; to: number; story: { shared: number; picked: number; shipped: number } };
}
export interface NumberRequest {
  number: number;
}
export interface BriefRequest {
  text: string;
}
export interface SearchSuggestResponse {
  counts: Record<string, number>;
  examples: [string, string, string];
}
export interface ConfigResponse {
  promises: Record<string, number | string | string[]>;
  sorting: { affects: string[]; areas: string[]; brings: Brings[]; helpers: string[] };
  uploads: UploadConfig;
  placeholders: [string, string, string];
  flags: Record<string, "default" | "alternative" | "off">;
}

// ---------------------------------------------------------------------------------------------------------------
// A-API.events: one stream per signed-in person
// ---------------------------------------------------------------------------------------------------------------
export type LiveEvent =
  | { event: "shell"; data: ShellResponse }
  | { event: "inbox.item"; data: InboxItem }
  | { event: "idea.changed"; data: { id: string; fields: string[] } }
  | { event: "file.state"; data: Pick<FileItem, "id" | "state"> & Partial<FileItem> }
  | { event: "conversation.message"; data: { idea_id: string; entry: ConversationEntry } }
  | { event: "teamup.changed"; data: { id: string; idea_id: string } }
  | { event: "desk.row"; data: { idea_id: string; refetch: true } }
  | { event: "committee.row"; data: { decision_id: string; refetch: true } };
