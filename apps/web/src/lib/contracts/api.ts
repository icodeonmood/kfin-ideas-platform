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
  MyIdeasFilter,
  MyIdeasList,
  MyIdeasSort,
  ReturnIn,
  ShowReason,
  StageStateValue,
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
  Message,
  OneCard,
  OnePost,
  Person,
  PersonRef,
  PersonSettings,
  QuestionSet,
  SimilarMatch,
  Sorting,
  StageState,
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
// A-API.ideas: lane E owns this section. `GET /ideas/:id` (S-06 for the sharer, S-09 for anyone else, a pointer
// to S-R2 for a reviewer, to S-04B for the owner's draft), withdraw and restore (L-SUBMIT.withdraw). These are what
// services/worker/ideapage returns; words are worked out on the server (A-API.conventions/6). The decision and the
// question set on an idea are lane B's (`GET /ideas/:id/decision`, `GET /ideas/:id/question-set`, below); S-06
// composes them. Ask lane E before changing.
// ---------------------------------------------------------------------------------------------------------------
export interface PillWords {
  status: IdeaStatus;
  label: string;
  variant: "neutral" | "blue" | "warn" | "ok" | "bad";
}
export interface LinkWords {
  label: string;
  to: string;
  accessible_name?: string;
}
export interface WindowCountdown {
  label: string; // "3 days left", "07:38 left", "Overdue"
  variant: "neutral" | "warn" | "bad";
  until: IsoDate;
}
/** An action the page carries out in place with a POST (withdraw, restore). */
export interface PostAction {
  label: string;
  op: "withdraw" | "restore";
  method: "POST";
  path: string;
  done: string;
  confirm?: {
    heading: string;
    line: string;
    reason_label: string;
    reason_hint: string;
    placeholder: string;
    confirm_label: string; // "Withdraw it"
    cancel_label: string;
  };
}
export interface CrewWords {
  lead: PersonRef | null;
  members: PersonRef[];
  count: number;
  ones_count: number;
}
/** E-ENTITIES `Idea`, the part anyone may see once it is shared (P-PRODUCT.privacy). */
export interface PublicIdea {
  id: string;
  ref: string | null;
  status: IdeaStatus;
  kind: Kind;
  title: string;
  summary: string;
  often?: string;
  affects: string[];
  brings: Brings[];
  area: string;
  city: string;
  sharer: PersonRef | null;
  credited: PersonRef[];
  shared_at: IsoDate | null;
  stages: StageState[];
  crew: CrewWords;
  linked_similar_count: number;
  wall: { shown: boolean; opened_7d: number };
  merged_into?: string;
}
export interface SharerAnswer {
  id: string;
  text: string;
  at?: IsoDate;
  line: string; // "From your answer to Meera, Monday 16 November"
  files: FileItem[];
}
export interface SharedRow {
  part: IdeaPart | "area";
  label: string;
  value: string;
  answers?: SharerAnswer[];
  figures?: Record<string, Record<string, string>>;
}
export interface SimilarTile {
  idea: {
    id: string;
    title: string;
    status: IdeaStatus;
    area: string;
    city: string;
    shared_at: IsoDate | null;
    lead: PersonRef | null;
    crew_faces: PersonRef[];
    crew_count: number;
    in_their_words: string; // the short summary, never raw words
  };
  strength: string;
  reason: string;
  meta: string;
  pill: PillWords;
  count_line: string;
  my_state: "none" | "request_sent" | "on_crew";
  to: string;
  actions: { label: string; op: "preview" | "team_up"; accessible_name: string }[];
}
export type SharerPageState =
  | "just_shared"
  | "questions"
  | "answers_sent"
  | "picked"
  | "not_now"
  | "not_picked"
  | "reversed"
  | "withdrawn"
  | "being_built"
  | "shipped"
  | "merged";
/** S-06: everything the sharer's page shows that lane B's two endpoints do not. */
export interface SharerView {
  view: "sharer";
  screen: "S-06";
  idea: PublicIdea & {
    share_seconds?: number;
    own_words: Message[];
    hidden: {
      id: string;
      kind: string;
      masked: string;
      state: string;
      reason?: string;
      shown_at?: IsoDate;
    }[];
    files: FileItem[];
    edit_window?: { open: boolean; closes_at?: IsoDate; opened_by_desk_at?: IsoDate };
    review?: { decide_by: IsoDate; reviewer?: PersonRef; opened_at?: IsoDate };
    has_open_questions: boolean;
    kept_separate: boolean;
    next_step?: { sentence: string; action?: { label: string; to: string } };
    versions?: { count: number; summary: string };
  };
  page: {
    state: SharerPageState;
    state_label: string;
    pill: PillWords;
    breadcrumb: { label: string; to: string; current: string }; // "My ideas, Needs you" / IDEA-2026-001481
    shared_label: string | null; // "Shared 14-Nov-26"
    share_seconds_label?: string; // "Done in 40 seconds", first arrival only
    first_arrival: boolean;
    /** Null where the sentence names the decision or the questions: compose it from `card_from`'s endpoint. */
    card: { lead: string; rest: string } | null;
    card_from?: "decision" | "question_set";
    window: { open: boolean; line: string; countdown?: WindowCountdown } | null;
    actions: {
      conversation: LinkWords;
      edit?: LinkWords;
      withdraw?: PostAction;
      restore?: PostAction;
      open_other?: LinkWords;
    };
    lane_b: { question_set: string; decision: string };
    shared: {
      intro: string;
      rows: SharedRow[];
      hidden: {
        chips: string[];
        more: number;
        more_label?: string;
        more_accessible_name?: string;
        note: string;
        all: { masked: string; kind: string; where: string }[];
      };
      attached: {
        label: string;
        files: FileItem[];
        answers: SharerAnswer[];
        empty_line?: string;
        add?: LinkWords;
      };
      fix: {
        label: string;
        text?: string;
        needs?: string | null;
        more_label?: string;
        empty_line?: string;
        add?: LinkWords;
        answers: SharerAnswer[];
      };
    };
    conversation: {
      heading: string;
      count: number;
      link: LinkWords;
      empty_line?: string;
      sub_line?: string;
    } | null;
    similar: { heading: string; intro: string; tiles: SimilarTile[] };
    merged: { to: string; title: string; line: string; note: string; at: IsoDate; link: LinkWords } | null;
    own_words_unmasked: boolean;
  };
}
export type TeamUpCardState = "not_asked" | "request_sent" | "on_crew" | "closed" | "merged" | "withdrawn";
/** S-09: the short summary, where it is, and Team up. Never raw words, answers, files or a decision's reason. */
export interface ColleagueView {
  view: "colleague";
  screen: "S-09";
  /** A withdrawn idea (for a former crew member only) carries `id`, `ref` and `status` alone (BLD-E010). */
  idea: PublicIdea | { id: string; ref: string | null; status: "withdrawn" };
  page: {
    state?: "withdrawn";
    back: { from: string; label: string; to: string }; // "Back to the Wall" / "Back to My ideas" / "Back to IDEA-…"
    pill: PillWords;
    shared_line?: string;
    summary_heading?: string;
    summary_note?: string;
    about?: { label: string; value: string }[];
    team_up: {
      state: TeamUpCardState;
      line: string;
      heading?: string;
      count?: number;
      count_line?: string;
      faces?: PersonRef[];
      action?: { label: string; to?: string; op?: string; sheet?: string; request_id?: string };
      link?: LinkWords;
      can_team_up: boolean;
    };
  };
}
/** A reviewer lands on S-R2; the owner's draft opens where it was left (S-04B). */
export interface RedirectView {
  view: "desk" | "draft";
  to: string;
}
export type IdeaViewResponse = SharerView | ColleagueView | RedirectView;
export interface IdeaViewQuery {
  from?: string; // "wall", "my-ideas", "share" or an IDEA- reference
  back?: string; // the list state to go back to, a path on this site
}
export interface WithdrawRequest {
  reason?: string;
}
/** Withdraw and restore answer with the sharer's page in its new state. Errors: `edit_window_closed` with
 * `{ opened_by_desk_at }`, `not_withdrawn`, `not_found`. */
export type WithdrawResponse = SharerView;
export type RestoreResponse = SharerView;

// ---------------------------------------------------------------------------------------------------------------
// A-API.my-ideas: lane E owns this section. `GET /me/ideas` (S-07). The whole list state is in the URL
// (P-ROUTES.state): `list`, `filter`, `sort`, `q` and `row`, the row to come back to. Search here is a plain text
// match on title, short summary and reference; asking in your own words is lane F's (L-SEARCH) on the same `q`.
// ---------------------------------------------------------------------------------------------------------------
export interface MyIdeasQuery {
  list?: MyIdeasList;
  filter?: MyIdeasFilter;
  sort?: MyIdeasSort;
  q?: string;
  row?: string;
}
export interface MyIdeaRow {
  id: string; // the reference, or a draft's row id
  ref: string | null;
  list: MyIdeasList;
  title: string;
  href: string; // carries `from=my-ideas&back=…` so Back returns to this exact view
  meta: string; // "IDEA-2026-001481, Shared Saturday 14 November" / "Saved yesterday, on this laptop"
  pill: PillWords;
  track: { segments: StageStateValue[]; label: string } | null; // drafts show the pill only
  next_step: {
    sentence: string;
    action: {
      label: string;
      to?: string;
      op?: "restore" | "draft.restore";
      method?: "POST";
      path?: string;
      style: "primary" | "line";
      accessible_name: string; // "Answer the questions: …"
    };
  };
  group: Exclude<MyIdeasFilter, "all">;
  activity_at: IsoDate;
  snippet?: string; // while searching: the short summary, cut at a word
  archived?: boolean; // drafts untouched for 30 days: kept, never deleted
  saved_on?: { device: "phone" | "laptop"; this_device: boolean };
}
export interface MyIdeasEmpty {
  kind: "first_time" | "filtered" | "no_results" | "list";
  title: string;
  line: string;
  actions: { label: string; to: string; style?: "primary" | "line" }[];
  hint?: string; // "or press P anywhere"
}
export interface MyIdeasResponse {
  items: MyIdeaRow[];
  total: number;
  counts: Record<MyIdeasFilter, number>; // per filter, for the current list
  lists: Record<MyIdeasList, number>; // per list, for the current filter
  state: { list: MyIdeasList; filter: MyIdeasFilter; sort: MyIdeasSort; q: string; row: string | null };
  query: string; // the canonical query string, defaults left out
  url: string; // "/my-ideas?list=teamed&sort=stage"
  tabs: { list: MyIdeasList; label: string; count: number; selected: boolean; to: string }[];
  filters: {
    filter: MyIdeasFilter;
    label: string;
    short_label: string; // the phone's chip: "With the desk"
    count: number;
    selected: boolean;
    to: string;
  }[];
  sorts: { sort: MyIdeasSort; label: string; selected: boolean; to: string }[];
  sort_cycle: { label: string; next: MyIdeasSort; to: string }; // "Sorted by latest activity"
  copy_link: { label: string; url: string; done: string };
  search?: {
    sentence: string; // "Found 4 ideas about “sms”: 2 of yours and 2 you teamed up on. Closest: “…”."
    matched_on: ("title" | "summary" | "reference")[];
    matched_line: string;
    closest: { id: string; title: string; href: string } | null;
    clear: { label: string; to: string };
  };
  empty?: MyIdeasEmpty;
  arrival?: { line: string; row: string }; // "Back where you were: Yours."
}

// ---------------------------------------------------------------------------------------------------------------
// A-API.ideas, lane C's operations: the edit page's save (S-06B), the preview (C-PREVIEW), versions, similar.
// ---------------------------------------------------------------------------------------------------------------
export type IdeaPreviewResponse = IdeaPreview;
export interface IdeaPatch {
  title?: string;
  summary?: string;
  often?: string;
  sorting?: SortingPatch;
  fix?: FixRequest;
  helpers?: HelpersRequest;
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
