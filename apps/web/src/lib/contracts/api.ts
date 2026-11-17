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
  IdeaStatus,
  InboxTab,
  Kind,
  MergeLead,
  MessageVia,
  MyIdeasList,
  MyIdeasSort,
  ReturnIn,
  ShowReason,
  TeamUpAnswer,
  Tier,
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
  PersonRef,
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
  // A-API.wall, A-API.ones, A-API.ones-posts, A-API.me (lane E)
  | "taken"
  | "out_of_range"
  | "not_a_one"
  | "brief_invalid"
  | "personal_data"
  | "liked_required"
  | "bad_kind"
  | "bad_sort"
  | "bad_page"
  | "bad_order"
  | "bad_setting"
  | "teams_off"
  // Any route
  | "not_found"
  | "paused"
  | "try_again";

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
// A-API.me: profile, settings and points. Lane E owns this section.
// `GET /me` (Person with points and settings) is `GET /api/me/profile`; `GET /api/me` stays the session's own
// summary (roles, navigation, privacy notice) that the shell reads. Always the signed-in person's own.
// ---------------------------------------------------------------------------------------------------------------
/** The person with their private points and their settings (self only, P-PRODUCT.privacy). */
export type MeResponse = Person & Required<Pick<Person, "settings" | "points">>;
/** `GET /api/me/profile` (S-H6). */
export interface ProfileResponse {
  person: MeResponse;
  /** "Tier 2, Glow". */
  tier_label: string;
  /** "Investor service, Hyderabad. Tier 2, Glow." (S-H6.layout/1). */
  line: string;
  avatar: { initials: string; tier: Tier };
  /** "/one" for a One (S-H6.rules/4), otherwise null. */
  one_dashboard: "/one" | null;
  one_since_label: string | null;
  /** Teams messages stay off until IT approves them (DEC-105): the switch shows, cannot be turned on. */
  available: { teams: boolean };
}
/** `PATCH /api/me/settings`: any of the switches; each saves at once (S-H6.rules/1). */
export type SettingsPatch = Partial<PersonSettings>;
/** Every switch's state after the save. */
export interface SettingsResponse {
  settings: PersonSettings;
}
/**
 * A save that did not happen: `message` is "Couldn't save that. Try again." and `field` names the switch, so the
 * screen flips it back (V-FIELDS.one/5). Codes: `bad_setting`, `teams_off`, `try_again`.
 */
export type SettingsError = ApiError<"bad_setting" | "teams_off" | "try_again" | "not_found">;

// ---------------------------------------------------------------------------------------------------------------
// A-API.me (shell), A-API.home
// ---------------------------------------------------------------------------------------------------------------
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
// A-API.wall: the Wall (S-WALL, L-WALL). Lane E owns this section.
// Anyone signed in reads it. Every row is screen-ready: labels are computed on the server (A-API.conventions/6).
// The sharer is null when they hid their name from the Wall (DEC-104); never their own words, never points.
// ---------------------------------------------------------------------------------------------------------------
/** An idea as the Wall shows it. */
export interface WallIdea {
  id: string;
  title: string;
  summary: string;
  kind: Kind;
  area: string;
  crew_count: number;
  sharer: PersonRef | null;
  /** "Problem, Investor service" (Just in); Kindling adds ", 4 colleagues on it". */
  meta: string;
  /** The idea's page with its way back to the Wall: `/ideas/IDEA-…?from=wall&back=…` (J-BROWSE/5). */
  to: string;
}
export interface WallStageView extends Omit<WallStage, "items"> {
  items: WallIdea[];
}
/** `GET /api/wall/kindling?kind=`: Picked, Being built, Shipped. */
export type KindlingResponse = [WallStageView, WallStageView, WallStageView];
export interface JustInQuery {
  kind?: Kind | "all";
  /** Newest by default. */
  sort?: WallSort;
  /** 5 on desktop, 3 on the phone (L-WALL.justin/5); at most 50. */
  limit?: number;
  offset?: number;
}
export interface JustInItem extends WallIdea, Pick<JustInRow, "opened_7d" | "ones_count"> {
  shared_at: IsoDate | null;
  /** "2h ago", "Yesterday", "2 days ago" (the Shared column). */
  shared_label: string;
  /** The figure for the current sort, for the phone's second line: "Opened by 233 this week", "Shared 2h ago". */
  figure_label: string;
}
/** `GET /api/wall/just-in`. Ties go to the newest. */
export interface JustInResponse {
  items: JustInItem[];
  total: number;
  /** Per kind chip, and `all`. */
  counts: Record<Kind | "all", number>;
  sort: WallSort;
  /** The next offset, or null when this page is the last. */
  next: string | null;
  /** "12 with the review desk". */
  sub: string;
  /** How many the next page adds. */
  more: number;
  /** "Show 5 more", "Show 2 more", "Show fewer" (after the last page), or null when everything fits. */
  more_label: string | null;
}
/** A shipped fix in the impact table (L-WALL.impact/2). */
export interface LiveFixRow extends Omit<LiveFix, "due"> {
  id: string;
  /** "90 days", "30 days", "Due 18 Nov". */
  measured_label: string;
  due: IsoDate | null;
}
/** One impact tile: the number on one line, "lakh" as its suffix, the unit in the label (S-WALL.impact/4). */
export interface ImpactTile {
  key: "hours_month" | "money_year" | "fixes_measured" | "reached";
  value: string;
  suffix: string;
  label: string;
}
/** `GET /api/wall/impact`. */
export interface ImpactResponse {
  totals: ImpactTotals;
  tiles: [ImpactTile, ImpactTile, ImpactTile, ImpactTile];
  live: LiveFixRow[];
}
/** An Ember issue; `headline` is null until the issue's content record has one. */
export interface EmberIssueView extends Omit<EmberIssue, "headline"> {
  headline: string | null;
}
/** `GET /api/wall/ember`: the latest issue, then the next as "Coming soon". */
export type EmberResponse = EmberIssueView[];

// ---------------------------------------------------------------------------------------------------------------
// A-API.ones: the Ones' cards and a One's own dashboard (S-WALL.ones, S-ONE, L-ONES). Lane E owns this section.
// The cards are for everyone signed in; `/api/one` and its writes are the One's alone (403 `not_a_one`).
// ---------------------------------------------------------------------------------------------------------------
/** A One's card; `person` is null when they hid their name from the Wall (DEC-104). */
export interface OneCardView extends Omit<OneCard, "person"> {
  person: PersonRef | null;
  /** "Tier 4, Blaze". */
  tier_label: string;
  /** "Founding One" / "One". */
  flag_label: string;
}
/** `GET /api/wall/ones?order=wall|leaderboard`: in the order they became Ones, or by tier then hours saved. */
export type OnesResponse = OneCardView[];
/** The number card (S-ONE.layout/3, V-FIELDS.one/3). */
export interface NumberWindow {
  open: boolean;
  until: IsoDate | null;
  /** "1 Dec 2026". */
  until_label: string;
  number: number;
  /** While open: "Keep No. 1, or choose any free number from 1 to 999 until 1 Dec 2026. …". */
  keep_label?: string;
  /** Once closed, in place of the field: "No. 1 is yours for good.". */
  locked_label?: string;
}
/** The glow-up waiting to play once (S-ONE.states `showGlowUp`). */
export interface TierMoment {
  id: number;
  from: Tier;
  to: Tier;
  from_label: string;
  to_label: string;
  /** "No. 17, your spark is hotter". */
  title: string;
  /** "From Tier 1, Spark to Tier 2, Glow". */
  line: string;
  story: { shared: number; picked: number; shipped: number };
  /** `from_label`: "From the core committee: Vivek Shenoy". */
  messages: { text: string; from_label: string }[];
}
/** `GET /api/one`. Reading it changes nothing; the moment is marked seen by its own call. */
export interface OneDashboardResponse {
  one: OneCardView;
  since: IsoDate;
  since_label: string;
  /** "You're No. 1". */
  headline: string;
  /** "Tier 4, Blaze. Founding One since 1 Nov 2026.". */
  since_line: string;
  idea: { id: string | null; title: string; status: IdeaStatus | null } | null;
  impact: Impact;
  number_window: NumberWindow;
  /** The live brief, and whether a new one waits for the programme team. */
  brief: { text: string | null; pending: boolean };
  tier_moment: TierMoment | null;
}
/** `PUT /api/one/number`. Errors: `out_of_range`, `taken` (with `near`), `window_closed`, `not_a_one`. */
export interface NumberRequest {
  number: number;
}
export interface NumberResponse {
  number_window: NumberWindow;
}
/** "No. 7 is taken. Free numbers near it: 6, 8, 11." */
export interface NumberTakenError extends ApiError<"taken"> {
  error: ApiError<"taken">["error"] & { near: number[] };
}
/** `POST /api/one/brief`: one sentence, 20 to 140 characters. Errors: `brief_invalid`, `personal_data`. */
export interface BriefRequest {
  text: string;
}
export interface BriefResponse {
  brief: { text: string | null; pending: true };
}
/** `POST /api/one/glow-up/{id}/seen`. */
export interface GlowUpSeenResponse {
  seen: true;
}

// ---------------------------------------------------------------------------------------------------------------
// A-API.ones-posts: what the Ones post, for Home's fan (C-ONES-FAN, L-ONES.rules/7). Lane E owns this section.
// ---------------------------------------------------------------------------------------------------------------
export interface OnePostView extends Omit<OnePost, "one"> {
  id: string;
  one: OneCardView;
  /** Whether the person asking liked it. */
  liked: boolean;
}
/** `GET /api/ones/posts`: newest first. */
export type OnePostsResponse = OnePostView[];
/** `PUT /api/ones/posts/{id}/like`. Saying the same twice changes nothing. Error: `liked_required`. */
export interface LikeRequest {
  liked: boolean;
}
export interface LikeResponse {
  id: string;
  liked: boolean;
  likes: number;
}

// ---------------------------------------------------------------------------------------------------------------
// A-API.search, A-API.config
// ---------------------------------------------------------------------------------------------------------------
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
