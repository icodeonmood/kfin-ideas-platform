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
  HiddenKind,
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
  Tier,
  TimeToAnswer,
  WallSort,
  Brings,
  Channel,
  OutsideTools,
  SortingSource,
} from "./enums";
import type {
  CrewCard,
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
  Message,
  OneCard,
  OnePost,
  Person,
  PersonRef,
  PersonSettings,
  Range,
  SimilarMatch,
  StageState,
  TeamUpRequest,
  WallStage,
  Conversation,
  ConversationEntry,
  SavedLabels,
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
  // Lane C's sorting and sending (L-SORT, L-SUBMIT; BLD-C081 to BLD-C085)
  | "sorting_incomplete"
  | "declaration_changed"
  | "idempotency_key_reused"
  | "idempotency_key_bad"
  | "not_a_draft"
  | "already_shared"
  | "merged"
  | "field_needed"
  | "fix_how_needed"
  | "worth_unclear"
  | "send_failed"
  | "unavailable"
  | "not_found"
  | "body_required"
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
  // "How should we refer to you?" is not here: lane C's `GET/PUT /api/me/refer-as` is its only source (BLD-C111,
  // `lib/refer-as.ts`).
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
  ideas: { id: string; title: string; status_dot: string; status_label: string }[];
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
  /** DEC-108: the English copy of a voice note or another language. */
  text_en?: string;
  via?: MessageVia;
  files?: string[];
  channel: Channel;
}
export interface CreateDraftResponse {
  draft: Draft;
  run_id: string | null;
}
export interface AddMessageRequest {
  text: string;
  via: MessageVia;
  /** DEC-108: the English copy of a voice note or another language; context only, never quoted. */
  text_en?: string;
  /** A voice note's stream (DEC-108): the message is taken from the voice service, its words and its English copy;
   * words changed before sending are kept without the copy. Without voice in this build: `voice_unavailable`. */
  stream_id?: string;
  /** When it was typed, for a message sent again after being offline (L-DRAFT.autosave/7). */
  at?: IsoDate;
  /** Keep the words without building (the S1 interview's answers until the last, L-DRAFT.parts/10). */
  defer_run?: boolean;
  files?: string[];
}
/** `run_id` is null when nothing was built: under the minimum, deferred, or every part pinned. */
export interface AddMessageResponse {
  run_id: string | null;
  message: Message;
  draft: Draft;
}
export interface EditMessageRequest {
  text: string;
  text_en?: string;
}
export interface PartResponse {
  run_id: string | null;
  draft: Draft;
}
/** One row of GET /drafts?recent=1 (L-DRAFT.autosave/6, /8). */
export interface DraftListItem {
  id: string;
  title: string;
  saved_at: IsoDate | null;
  saved_on: Draft["saved_on"];
  saved_labels: SavedLabels | null;
  step: DraftStep;
  char_count: number;
  channel: Channel;
  archived: boolean;
}
export type PartPatch = { value: unknown } | { pinned: false };
export type SortingPatch =
  { affects?: string[]; kind?: Kind; area?: string; brings?: Brings[] } | { confirm: true };
/** Lane C: one sorting field with the words beside it ("Suggested because …"); none for the person's own change. */
export interface SortingChoiceView<T> {
  value: T;
  source: SortingSource;
  why: string | null;
  why_line: string | null;
}
/** `Sorting` as lane C returns it (L-SORT): each field, plus the lines S-05 part 2, the rail and the Send row show. */
export interface SortingResponse {
  affects: SortingChoiceView<string[]>;
  kind: SortingChoiceView<Kind>;
  area: SortingChoiceView<string | null>;
  brings: SortingChoiceView<Brings[]>;
  confirmed: boolean;
  complete: boolean;
  confirmed_at: IsoDate | null;
  /** "Suggested, not confirmed yet" → "Investor service, saves time, saves cost". */
  rail: string;
  /** "Not confirmed yet" → "Investor service, affecting investors and KFin teams, saves time, saves cost". */
  summary: string;
  /** "These are suggestions from your words. Not confirmed yet." (S-05) or "Confirmed when you shared it. …" (S-06B). */
  note: string | null;
  problem: ApiError["error"] | null;
}
export interface ShowHiddenRequest {
  reason: ShowReason;
}
export type HiddenResponse = HiddenDetail;
/** One figure as typed ("2 lakh", "70 to 150", "25k"), a number, or a `Range` sent back; the worker reads it with
 * lane B's one quantity reader (L-WORTH/1) and returns it normalised in `Range.text`. */
export type WorthInput = string | number | Pick<Range, "text"> | Pick<Range, "low" | "high">;
/** `PUT /drafts/:id/fix` and the edit page's `fix`: the sheet's answers. `included: false` keeps a started fix
 * ("Close, and keep what you wrote"); otherwise `how` is needed, at least 20 characters (V-FIELDS.checkit/8). */
export type FixRequest = Omit<Fix, "ready_count" | "included" | "worth" | "how"> & {
  how?: string;
  included?: boolean;
  worth?: {
    hours_month?: WorthInput;
    cost_month?: WorthInput;
    revenue_month?: WorthInput;
    outside_tools?: OutsideTools;
  };
};
/** `Fix` with the words S-05 shows: "2 of 5 ready for the review desk", the most useful next answer, and on the
 * part "Included, 5 of 5 ready", the one-line fix and its size line, or the started-fix line. */
export type FixResponse = Omit<Fix, "how"> & {
  how?: string;
  ready_of: 5;
  readiness: string;
  next: { key: "how" | "needs" | "solved_already" | "worth" | "basis"; line: string } | null;
  part:
    | { rail: "Added"; line: string; fix_line: string; size_line?: string }
    | { rail: "Optional"; line: string; action: string };
};
/** `DELETE /drafts/:id/fix`. */
export interface FixRemoved {
  fix: null;
  part: { rail: "Optional" };
}
export interface HelpersRequest {
  picks: string[];
  text?: string;
}
/** `PUT /drafts/:id/helpers`: the picks in the list's spelling, the masked own words and the Send part's row. */
export interface HelpersResponse {
  picks: string[];
  text: string | null;
  /** "Not said", or "Someone at a branch and a branch head". */
  line: string;
  part: { rail: "Added" | "Optional" };
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
/** `GET /drafts/:id/send` (lane C): the Send part's rows, the declaration, the button and what stops Submit. */
export interface SendViewResponse {
  id: string;
  rows: {
    key: "title" | "sorting" | "similar" | "proof" | "fix" | "helpers";
    label: string;
    value: string | null;
    ok: boolean;
    step: DraftStep;
  }[];
  declaration: { version: string; text: string };
  button: "Submit" | "Submit with my fix";
  ready: boolean;
  problems: ApiError["error"][];
  submit_says?: ApiError["error"];
  go_to?: { label: "Go to the sorting"; step: DraftStep };
}
/** What S-06 "Just shared" shows at once (L-SUBMIT.send, V-ACC.share/12), as server-computed words. 201 when sent
 * now, 200 for a draft sent before (a retry never creates two ideas). */
export interface SubmitResponse {
  idea_id: string;
  id: string;
  ref: string;
  status: IdeaStatus;
  pill: { status: IdeaStatus; label: string; variant: string };
  title: string;
  shared_at: IsoDate;
  shared_label: string;
  stages: (StageState & { label: string; suffix: string })[];
  next: { to: string; replace: true; state: "just_shared" };
  review?: { decide_by: IsoDate; by_label: string; line: string };
  edit_window?: {
    open: boolean;
    closes_at: IsoDate;
    line?: string;
    countdown?: { label: string; variant: "neutral" | "warn" | "bad"; until: IsoDate };
    edit?: { label: string; to: string };
  };
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
    // `reviewer` only for a sharer on the review desk or the Ones Committee (DEC-111, BLD-E053)
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
    reference_line?: string; // the phone's "Reference IDEA-…, shared Saturday 14 November, Investor service"
    share_seconds_label?: string; // "Done in 40 seconds", first arrival only
    first_arrival: boolean;
    /** Null where the sentence names the decision or the questions: compose it from `card_from`'s endpoint. */
    card: { lead: string; rest: string; phone_rest?: string } | null; // phone_rest: PhoneStatus.md's shorter rest
    card_from?: "decision" | "question_set";
    window: { open: boolean; line: string; phone_line?: string; countdown?: WindowCountdown } | null;
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
      phone_empty_line?: string; // PhoneStatus.md's shorter line
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
  /** A withdrawn idea (for a former crew member only) carries `id`, `ref` and `status` alone (BLD-E011). */
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
// A-API.my-ideas: lane E owns this section. `GET /me/ideas` (S-07): `list`, `filter`, `sort` and `row`, the row to come
// back to, in the URL (P-ROUTES.state). `POST /me/ideas` with a `MyIdeasQuery` body is the same read with the search
// `q`, whose words go in no URL (DEC-110). Search here is a plain text match on title, short summary and reference;
// asking in your own words is lane F's (L-SEARCH) on the same `q`.
// ---------------------------------------------------------------------------------------------------------------
export interface MyIdeasQuery {
  list?: MyIdeasList;
  filter?: MyIdeasFilter;
  sort?: MyIdeasSort;
  q?: string; // POST body only (DEC-110); at most 200 characters
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
    phone_sentence?: string; // the phone board's wording where it differs: "Meera from the review desk asked you…", for the review desk and the Ones Committee only (DEC-111)
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
  phone_line?: string; // the phone board's wording where it differs ("…their impact is measured.")
  // desk_only: the desktop board's action only ("See 1 in Teamed up"); the phone offers "Show all ideas" alone
  actions: { label: string; to: string; style?: "primary" | "line"; desk_only?: boolean }[];
  hint?: string; // "or press P anywhere"
}
export interface MyIdeasResponse {
  items: MyIdeaRow[];
  total: number;
  counts: Record<MyIdeasFilter, number>; // per filter, for the current list
  lists: Record<MyIdeasList, number>; // per list, for the current filter
  state: { list: MyIdeasList; filter: MyIdeasFilter; sort: MyIdeasSort; q: string; row: string | null };
  query: string; // the canonical query string, defaults left out; never the search (DEC-110)
  url: string; // "/my-ideas?list=teamed&sort=stage"; no link in this response carries the search
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
/** The edit page's Save: only what changed. `often: null` empties "How often"; `fix: null` is "Remove". */
export interface IdeaPatch {
  title?: string;
  summary?: string;
  often?: string | null;
  sorting?: SortingPatch;
  fix?: FixRequest | null;
  helpers?: HelpersRequest;
  /** S-06B (BLD-C161): the files and links the edit page added or removed since it was loaded or last saved. They
   * acted at once; Save records them in the version (`changed_fields` gets `files`). Attachment IDs only. */
  files?: { added: string[]; removed: string[] };
}
export interface IdeaVersion {
  n: number;
  changed_fields: string[];
  at: IsoDate;
}
/** `GET /ideas/:id/edit` (lane C, S-06B): the edit page for the sharer. */
export interface EditPageResponse {
  screen: "S-06B";
  id: string;
  ref: string;
  status: IdeaStatus;
  kind: Kind;
  bar: { title: string; line: string; back: { label: string; to: string } };
  window: {
    open: boolean;
    closes_at?: IsoDate;
    opened_by_desk_at?: IsoDate;
    countdown?: { label: string; variant: "neutral" | "warn" | "bad"; until: IsoDate };
    line?: string;
  };
  fields: { title: string; summary: string; often: string | null };
  hidden: Pick<HiddenDetail, "id" | "kind" | "masked" | "state">[];
  sorting: SortingResponse;
  fix: (FixResponse & { included: true }) | null;
  helpers: HelpersResponse;
  files: Pick<FileItem, "id" | "kind" | "name" | "state" | "hidden_note" | "link_scope">[];
  prompts: { fix?: string; files?: string };
  side: { when: string; line: string }[];
  declaration: { version: string; text: string };
  versions: { count: number; summary: string };
  saved_label?: string;
}
/** The edit page's Save (`PATCH /ideas/:id/edit`): the new version, or nothing when nothing changed. */
export interface EditSaveResponse {
  version: IdeaVersion | null;
  changed_fields: string[];
  saved_label?: string;
  message: string;
  next: { to: string; replace: true };
}
/** `GET /ideas/:id/versions`: "Draft history" for the sharer, the review desk and the Ones Committee. */
export interface VersionsResponse {
  count: number;
  summary: string;
  items: (IdeaVersion & { label: string; at_label: string; before?: unknown; after?: unknown })[];
}
export type SimilarResponse = SimilarMatch[];

// ---------------------------------------------------------------------------------------------------------------
// A-API.questions, A-API.desk, A-API.committee: the review side. Lane B owns these shapes (they are what the
// worker's desk/*.py return, words worked out on the server per A-API.conventions/6); ask lane B before changing.
// ---------------------------------------------------------------------------------------------------------------
export type CountdownVariant = "normal" | "warn" | "bad";
export interface Countdown {
  label: string; // "3 days to answer", "07:38 left", "Overdue by 5 hours"
  variant: CountdownVariant;
}
/** A person as the desk and the committee see them (DEC-104). */
export interface DeskPerson {
  id: string | null;
  name: string;
  first_name: string;
  initials: string;
  city: string | null;
  area: string | null;
}

// A-API.questions
export type SuggestedQuestionsResponse = { part: IdeaPart; text: string }[];
export interface SendQuestionSetRequest {
  questions: { part: IdeaPart; text: string; suggested?: boolean }[];
  time_to_answer?: TimeToAnswer;
  move_decide_by?: boolean;
}
export interface AnswerFile {
  id: string;
  kind: string;
  name: string;
  type: string | null;
  size: number;
  pages: number | null;
  state: string | null;
  hidden_note: string | null;
  /** DEC-107: the scan found a customer detail. Only the sharer, the review desk and the Ones Committee get it. */
  customer_detail: boolean;
}
export interface SetAnswer {
  id: string;
  question_id: string;
  text: string;
  files: AnswerFile[];
  by: DeskPerson;
  at: IsoDate | null;
  added_to: IdeaPart;
  added_to_name: string;
  saved_at: IsoDate | null;
  sent_at: IsoDate | null;
  sent: boolean;
}
export interface SetQuestion {
  id: string;
  seq: number;
  part: IdeaPart;
  part_name: string;
  text: string;
  suggested: boolean;
  answer: SetAnswer | null;
}
export interface QuestionSetView {
  id: string;
  idea_id: string;
  by: DeskPerson;
  state: "queued" | "sent" | "seen" | "partly_answered" | "answered" | "closed";
  time_to_answer: TimeToAnswer | null;
  sent_at: IsoDate | null;
  seen_at: IsoDate | null;
  due_at: IsoDate | null;
  answered_at: IsoDate | null;
  extended_times: number;
  reminded_at: IsoDate | null;
  count: number;
  answered: number;
  overdue: boolean;
  questions: SetQuestion[];
}
export type QuestionSetResponse = QuestionSetView & {
  due_label: string; // "Kavya has until Thursday 19 November, 6 pm."
  countdown: Countdown;
  after_decide_by: boolean;
  after_decide_by_line: string | null;
  decide_by: IsoDate | null;
};
export interface ExtendQuestionSetResponse {
  id: string;
  due_at: IsoDate;
  extended_times: number;
  due_label: string;
  countdown: Countdown;
}
export interface RemindResponse {
  id: string;
  reminded_at: IsoDate;
}
/** S-R3: the sharer's open set, with their own saved answers. Null when nothing is open. */
export type SharerQuestionSetResponse =
  | (QuestionSetView & {
      idea: { id: string; title: string };
      countdown: Countdown;
      deadline: string; // "Answer by Thursday 19 November, 6 pm"
      progress: string; // "1 of 3 answered"
      send_label: string; // "Send 1 answer to Meera", or "Answer at least one question"
    })
  | null;
export interface SaveAnswerRequest {
  text: string;
  file_ids?: string[];
}
export interface SaveAnswerResponse {
  id: string;
  question_id: string;
  text: string;
  hidden: number;
  files: AnswerFile[];
  added_to: IdeaPart;
  added_to_name: string;
  saved_at: IsoDate;
  sent: false;
}
export interface SendAnswersResponse {
  set_id: string;
  state: "partly_answered" | "answered";
  sent: number;
  answered: number;
  count: number;
  sent_at: IsoDate;
  progress: string;
  sent_line: string; // "Sent to Meera, 4:32 pm"
  spare: string; // "Answered with 3 days to spare"
  reviewer_first_name: string;
  decides_by: string | null; // "Meera decides by Friday 20 November"
}

// A-API.desk (S-R1): `GET /desk?tab=&sort=`, or `POST /desk` with a `DeskQuery` body when there is a search, whose
// words go in no URL (DEC-110)
export type DeskTab = "to_review" | "waiting" | "answered" | "decided";
export interface DeskQuery {
  tab?: DeskTab;
  sort?: DeskSort;
  q?: string; // POST body only (DEC-110); at most 200 characters
}
export interface DeskRow {
  idea_id: string;
  title: string;
  who: string; // "Kavya Menon, Investor service, Hyderabad"
  questions: string; // "0 of 3 answered, seen 12:05 pm"
  time_left: string | null; // "3 days to answer"
  variant: CountdownVariant | null;
  due_at: IsoDate | null; // the clock behind time_left, for the live countdown
  decide_by: string; // "Friday 20 November"
  action: string; // "Open", "Read answers", "Remind Divya"
  action_kind: "open" | "read_answers" | "remind";
  decision: string | null; // "Picked, 2 November" / "Reversed: picked"
  committee: string | null; // "Ones Committee can review it until Wednesday 2 December"
  area: string;
  asked: number; // the dots: one per question
  answered: number; // filled once answered
  set_id: string | null; // the latest question set, for "Remind {sharer}"
}
export interface DeskResponse {
  items: DeskRow[];
  total: number;
  counts: Record<DeskTab, number>;
  summary: string;
  tab: DeskTab;
  sort: DeskSort;
  waiting_on_sharers: { idea_id: string; title: string; dot: "blue" | "amber" | "red" }[];
  now: IsoDate;
}

// A-API.desk (S-R2): the reviewer's page
export interface ReviewerQuestion {
  id: string;
  text: string | null;
  asked_at: IsoDate;
  asked_by: string;
  asked_line: string; // "You asked, today 11:20 am"; another reviewer's: "Meera asked, today 11:20 am"
  state: "Answered" | "Not answered yet";
  answer: {
    id: string; // the answer row: S-R2 "Hide this" source { kind: "answer", id } (L-HIDE.rules/7)
    text: string | null;
    at: IsoDate;
    by: string;
    line: string; // "Kavya answered, today 4:32 pm"
    files: { id: string; name: string; hidden: string | null; customer_detail: boolean }[]; // DEC-107
  } | null;
}
export interface ReviewerPart {
  part: IdeaPart;
  name: string;
  text: string;
  questions: ReviewerQuestion[];
}
export interface WorthTile {
  measure: "hours_month" | "cost_month" | "revenue_month" | "outside_tools";
  label: string;
  value: string;
  was: string | null; // "was 70 to 150 hours a month"
  changed: boolean;
}
export interface WorthRevision {
  id: number;
  note: string | null;
  by: DeskPerson;
  at: IsoDate;
  kind: Kind | null;
  area: string | null;
}
export interface ReviewerArtefact {
  kind: "file" | "own_words" | "similar_found" | "versions";
  id?: string;
  title: string;
  line: string;
  action: string; // "Open", "Read", "Compare", "See changes"
  customer_detail?: boolean; // a file: the scan found a customer detail (DEC-107); the desk opens it, marked
}
export interface ReviewerSimilar {
  idea_id: string;
  title: string;
  status: string;
  strength: "close" | "related";
  reason: string;
  merged: boolean;
  meta: string; // "IDEA-2026-001412, Ravi Nair, Investor service, Hyderabad. 4 on its crew"
}
/** L-MERGE.effects/3: an idea merged into this one (through the whole `merged_into` chain), under its sharer's
 * first name: its parts with the answers its sharer sent, its words and its files, gated as the lead's are. */
export interface ReviewerContribution {
  idea_id: string;
  title: string;
  into: string; // the idea it joined: this one, or one merged into it
  merged_at: IsoDate | null;
  sharer: DeskPerson;
  label: string; // "Ravi’s idea, IDEA-2026-001412"
  parts: ReviewerPart[];
  files: ReviewerArtefact[]; // kind "file" only
  own_words: ReviewerOwnWords[];
}
/** One of the sharer's messages, the masked copy; `id` is the "Hide this" source { kind: "message", id }. */
export interface ReviewerOwnWords {
  id: string;
  seq: number;
  via: string;
  at: IsoDate;
  text: string | null;
}
/** A detail the sharer chose to show, as the review desk reads it (L-HIDE.rules/6, `desk.reads._shown`): one per
 * value, never the value itself. */
export interface ReviewerShown {
  kind: HiddenKind;
  kind_label: string; // "Folio"
  reason: ShowReason;
  because: string; // "it’s an internal reference"
  by: string; // the first name of who showed it
  at: IsoDate;
  line: string; // "Folio shown, because it’s an internal reference."
}
/** The reviewer's words for their decision (S-R2 Decided; reference/copy/DeskIdea.md). */
export interface ReviewerDecisionLines {
  title: string; // "Decision sent to Kavya"
  // "Today, 4:58 pm. Kavya has it now." for the reviewer who decided; "Today, 4:58 pm. Meera sent it." for any other
  sent_line: string;
  // "Your reason, as Kavya reads it" for the reviewer who decided; "The review desk’s reason, as Kavya read it" else
  reason_heading: string;
  committee_heading: string; // "Ones Committee review"
  window_state: string | null; // "Open, 30 days left", "Extended once, 52 days left", "Reversed Friday 20 November"
  // "Open until Wednesday 16 December. The committee can extend it, up to 3 months in all, to …"; at the limit
  // "Open until … At the 3-month limit. If they reverse it, …"; null once closed
  window_line: string | null;
}
/** The question set this reviewer queued and has not sent (S-R2.panel Asking; J-REVIEW/A1). Theirs alone: another
 * reviewer's queued set is never on the page. */
export interface ReviewerQueuedSet {
  set_id: string;
  questions: { id: string; part: string; part_name: string; text: string | null; suggested: boolean }[];
  time_to_answer: string | null; // null until chosen; the panel defaults to 3 days
  ready_line: string; // "3 questions ready"
  send_label: string; // "Send 3 questions to Kavya"
}
export type ReviewerPanel =
  | { state: "reviewing"; decision: CommitteeRow | null; queued: ReviewerQueuedSet | null }
  | {
      state: "decided";
      decision: CommitteeRow & { decided_at: IsoDate; return_at: IsoDate | null };
      lines: ReviewerDecisionLines;
    }
  | { state: "merged" }
  | {
      state: "sent" | "answered";
      title: string; // "Waiting on Kavya" / "All 3 answered"
      spare_line?: string | null;
      set_id: string;
      count: number;
      answered: number;
      due_at: IsoDate;
      countdown: string;
      variant: CountdownVariant;
      sent_line: string; // "Sent today, 11:20 am. Seen 12:05 pm."
      decide_by_line: string | null;
      queued?: ReviewerQueuedSet | null; // "answered" only: a follow-up the reviewer queued
    };
export interface ReviewerIdeaResponse {
  idea: {
    id: string;
    title: string;
    status: string;
    status_label: string;
    pill: "blue" | "warn" | "ok" | "neutral";
    heading: string;
    kind: Kind;
    area: string | null;
  };
  sharer: DeskPerson;
  own: boolean; // the reviewer's own idea: read only (V-ACC.review/14)
  can_act: boolean;
  decide_by: { at: IsoDate | null; label: string | null; left: string | null };
  artefacts: ReviewerArtefact[];
  own_words: ReviewerOwnWords[];
  parts: ReviewerPart[];
  worth: { tiles: WorthTile[]; revised: boolean; revision: WorthRevision | null; line: string };
  similar: ReviewerSimilar[];
  shown: ReviewerShown[]; // L-HIDE.rules/6: the desk and the committee only; empty for anyone else
  contributions: ReviewerContribution[];
  panel: ReviewerPanel;
}
export interface WorthRequest {
  hours_month?: string; // as typed: "70 to 150", "about ₹25,000", "2.5 lakh"
  cost_month?: string;
  revenue_month?: string;
  outside_tools?: OutsideTools;
  kind?: Kind;
  area?: string;
  note?: string;
}
/** One measure as the worker writes it (`desk.worth.Range.as_json`): `high` is null for a single figure. */
export interface WorthFigure {
  low: number;
  high: number | null;
  text: string; // "70 to 150 hours a month"
}
/** `desk.worth.Worth.as_json`: only the measures given, and outside tools when chosen. */
export interface WorthFigures {
  hours_month?: WorthFigure;
  cost_month?: WorthFigure;
  revenue_month?: WorthFigure;
  outside_tools?: OutsideTools;
}
/** PUT /desk/ideas/:id/worth (`revise.revise_worth`): the sharer's figures and the revision that now counts, with
 * its note (masked), who revised it and when. Pinned against services/worker/desk/worth_response_sample.json. */
export interface WorthResponse {
  idea_id: string;
  worth_id: number;
  tiles: WorthTile[];
  sharer: WorthFigures;
  reviewer: WorthFigures & { note: string | null; by: DeskPerson; at: IsoDate };
  kind: Kind;
  area: string | null;
}
export interface DecisionRequest {
  choice: DecisionChoice;
  reason: string;
  joined_with?: string;
  return_in?: ReturnIn;
  wording_ok?: boolean; // send anyway after the wording check (L-DECIDE.rules/4)
}
/** 422 `wording_check` (L-DECIDE.rules/4, BLD-B236): the reason holds a word the product never says to a sharer. It
 * warns and never blocks: show `message` under the reason, then send again with `wording_ok: true` to send it as
 * written. `words` are as found in the reason; `suggestions` give a plainer way to say each. */
export interface WordingCheckError {
  error: {
    code: "wording_check";
    message: string;
    field: "reason";
    words: string[]; // ["duplicate"]
    suggestions: { word: string; suggestion: string }[];
  };
}
export interface DecisionResponse {
  id: string;
  idea_id: string;
  choice: DecisionChoice;
  label: string;
  reason: string; // masked, as the sharer reads it
  at: IsoDate;
  return_at: IsoDate | null;
  team_by: IsoDate | null;
  window: { state: "open"; opens_at: IsoDate; closes_at: IsoDate; max_closes_at: IsoDate; extended_times: 0 };
  joined_with: string | null; // a Pick that joined a similar idea (L-MERGE.desk/5): that idea's reference
  merge: DeskMergeResponse | null; // the desk merge it ran, the picked idea leading (BLD-B235)
}
export interface MergeSheetResponse {
  idea_id: string;
  other_idea_id: string;
  title: string; // "Merge with IDEA-2026-001412?"
  line: string;
  default_lead: MergeLead;
  options: { lead: MergeLead; label: string; meta: string; selected: boolean }[];
  by_lead: Record<MergeLead, { line: string; team_up: string }>;
  refusal: Record<MergeLead, string | null>;
  team_up: { label: string; line: string; default: boolean };
  note: { label: string; prefill: string; min: number; max: number };
  small_print: string;
  button: string;
}
export interface DeskMergeRequest {
  other_idea_id: string;
  lead: MergeLead;
  team_up: boolean;
  note: string;
}
export interface DeskMergeResponse {
  id: string;
  lead_idea_id: string;
  merged_idea_id: string;
  by: DeskPerson;
  via: "review_desk";
  team_up: boolean;
  note: string;
  at: IsoDate;
  window: {
    state: string;
    opens_at: IsoDate;
    closes_at: IsoDate;
    max_closes_at: IsoDate;
    extended_times: number;
  };
  banner: string; // C-SHEET-MERGE.after
}
/** BLD-B230: the browser speaks the masked script with a local voice; there is no audio file. */
export interface ListenAudioResponse {
  parts: { part: IdeaPart; title: string; text: string; seconds: number }[];
  chapters: { part: IdeaPart; at: number }[];
  total_seconds: number;
  version: string; // changes with the content, so a copy saved for offline is replaced
}

// A-API.committee (S-R4). Actions are keyed by window: a window covers a desk decision or a desk merge.
export interface CommitteeQuery {
  tab?: CommitteeTab;
  sort?: CommitteeSort;
}
export interface CommitteeRow {
  window_id: string;
  kind: "decision" | "merge";
  idea: { id: string; title: string; meta: string };
  sharer: DeskPerson;
  decision: {
    choice: DecisionChoice | null;
    label: string;
    merged_into: string | null;
    by_line: string; // "by Meera from the review desk, Monday 12 October"
    reason: string | null;
    reason_heading: string; // "The review desk's reason, as Kavya read it"
  };
  window: {
    state: "open" | "extended" | "reversed" | "expired";
    opens_at: IsoDate;
    closes_at: IsoDate;
    max_closes_at: IsoDate;
    extended_times: number;
    left: string | null; // "22 days left"
    until: string; // "Until Wednesday 16 December"
    extended: string | null; // "Extended once"
    extend_to: string | null; // "Extend to Friday 15 January 2027"
    limit_line: string | null; // "At the 3-month limit"
    closed_line: string | null; // "Expired Wednesday 18 November. After 30 days. The decision stands."
    open_line: string | null;
  };
  reversal: {
    to: DecisionChoice | null;
    note: string | null;
    by: DeskPerson;
    at: IsoDate;
    now_line: string; // "Now: Picked"
    now_by_line: string; // "by Rohan Mehta, Friday 13 November"
    reversed_line: string; // "Reversed Friday 13 November"
    final_line: string; // "Final. Kavya has the note."
  } | null;
  can_extend: boolean;
  can_reverse: boolean; // false on a member's own idea (L-COMMITTEE.rules/9)
  action: "Review" | "See it";
  area: string;
}
export interface CommitteeResponse {
  items: CommitteeRow[];
  total: number;
  counts: Record<CommitteeTab, number>;
  summary: string; // "3 decisions open to review. You reversed 1 this month."
  explanation: string;
}
export interface ReversingWordsResponse {
  title: string;
  intro: string;
  options: { to: DecisionChoice; label: string; line: string }[];
  note_label: string;
  note_help: string;
  final_line: string;
  send_label: string; // "Reverse and tell Kavya"
}
export interface ReverseRequest {
  to?: DecisionChoice; // none for a desk merge
  note: string;
  return_in?: ReturnIn;
}
/** The sharer's words for a decision (S-06; reference/copy/Status.md), for the sharer and the crew. */
export interface SharerDecisionLines {
  // The Picked card when the Pick joined a similar idea (L-MERGE.desk/5): "Meera from the review desk picked it on
  // Monday 16 November and joined it with IDEA-2026-001412 from Hyderabad, so one team builds one fix." On the
  // joined idea's page it names the lead. null for any other decision.
  joined_line: string | null;
  // "The Ones Committee can review this decision until Wednesday 16 December. If they change it, their note comes to
  // your Inbox. After that, it stands." While the window is open; it follows an extension. null once it closes.
  committee_line: string | null;
  reversal: {
    from_line: string; // "Rohan Mehta from the Ones Committee, Tuesday 24 November, 5:40 pm"
    title: string; // "The Ones Committee changed the decision to not now"
    note_heading: string; // "The committee’s note to you" (the note itself is `reversal.note` on the row)
    was_line: string; // "Was: Picked"
    was_by_line: string; // "by Meera from the review desk, Monday 16 November"
    final_line: string; // "This is final. It comes back to the review desk on Tuesday 16 February 2027, with your answers and crew."
    track_line: string; // "Picked, then moved to not now by the Ones Committee"
  } | null;
}
/** GET /ideas/:id/decision: in full for the sharer, crew, desk and committee; the stage only for anyone else.
 * `lines` is the sharer's words for the sharer and the crew, null for the desk and the committee. */
export type DecisionForViewerResponse =
  | (CommitteeRow & {
      decided_at: IsoDate;
      return_at: IsoDate | null;
      lines: SharerDecisionLines | null;
      joined_into: string | null; // on an idea a Pick joined (status merged): the lead, whose Pick this is
    })
  | { stage_only: true; decision: { choice: DecisionChoice; label: string } }
  | null;

// ---------------------------------------------------------------------------------------------------------------
// A-API.team-up
// ---------------------------------------------------------------------------------------------------------------
export interface TeamUpDraftNote {
  note: string;
  own_ideas: { id: string; title: string; status: string; meta?: string }[];
  /** The idea asked about and its lead, for the sheet's title and line (C-SHEET-TEAMUP.compose/2). */
  idea?: { id: string; title: string };
  lead?: import("./entities").PersonRef;
  /** 30 (`notes.teamup_note_min_chars`) and 600 (BLD-F021). */
  min_chars?: number;
  max_chars?: number;
}
export interface TeamUpCreate {
  note: string;
  brought_idea_ids: string[];
  /** "Keep mine separate" from Check it: the person's own draft (BLD-F020). */
  draft_id?: string;
}
/** What the screen that opened the sheet shows now (C-SHEET-TEAMUP.after; L-MERGE.request/4–8 on Check it). */
export interface TeamUpAfter {
  state: string;
  line: string;
  label?: string;
  detail?: string;
  action?: { label: string; op?: string; to?: string } | null;
  can_submit?: boolean;
}
/** POST /ideas/:id/team-up and DELETE /team-up/:id: the request, its kind, and what the opener shows now. */
export type TeamUpSendResponse = TeamUpRequest & { request?: "teamup" | "merge"; after: TeamUpAfter | null };
/** GET /ideas/:id/team-up (BLD-F015): the signed-in person's team-up state on one idea. */
export interface TeamUpMine {
  idea_id: string;
  lead: import("./entities").PersonRef;
  /** "lead" or "member" when on the crew. */
  me: string | null;
  crew_count: number;
  can_request: boolean;
  why_not: "already_on_crew" | "idea_closed" | "already_requested" | null;
  request: (TeamUpRequest & { request?: "teamup" | "merge" }) | null;
  after: TeamUpAfter | null;
}
/** GET and POST /drafts/:id/merge-request: the draft's latest merge request (`{state: 'none'}` when none). */
export interface DraftMergeRequestState {
  id?: string;
  other_idea_id?: string;
  state: string;
  note?: string;
  lead?: import("./entities").PersonRef;
  lead_reason?: string;
  after: TeamUpAfter | null;
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
/** L-CREW/5: the deck's filters, in the filter panel's order. */
export type CrewFilterKey = "location" | "category" | "status" | "team_size" | "looking_for";
export interface CrewFilterGroup {
  key: CrewFilterKey;
  label: string;
  /** Each option's count is what it would show with the other filters as they are. */
  options: { value: string; label: string; count: number; active: boolean }[];
}
/** L-CREW/9: an idea in "Your crews". `label` is "Waiting for Ravi" or "On the crew". */
export interface YourCrew {
  id: string;
  title: string;
  status: IdeaStatus;
  lead: PersonRef;
  state: "waiting" | "on_crew";
  label: string;
  request_id: string | null;
  at: IsoDate;
}
/**
 * What `GET /crew` returns (lane F, `services/worker/crew/deck.py`): `CrewResponse` plus the filter panel, the
 * active chips, the deck's state (L-CREW/7–8), `asked` for "You asked to team up on 1 idea", the last pass for
 * "Undo last pass", and "Your crews". `counts` keys are "<filter>:<value>".
 */
export interface CrewDeckResponse extends CrewResponse {
  filters: CrewFilterGroup[];
  active: { key: CrewFilterKey; value: string; label: string }[];
  deck_total: number;
  state: "cards" | "everyone_seen" | "nothing_yet";
  asked: number;
  last_passed: string | null;
  your_crews?: { items: YourCrew[]; teamed_link: string };
}
export interface CrewPassRequest {
  idea_id: string;
}
export interface CrewPassResponse {
  passed: number;
  last_passed: string | null;
}
/** "Undo last pass": the card comes back when it is still one the person could join. */
export interface CrewUndoResponse extends CrewPassResponse {
  restored: string | null;
  card: CrewCard | null;
}
export interface CrewResetResponse extends CrewPassResponse {
  reset: number;
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
  /** users.id of each person mentioned with @name (L-CONVO/6). */
  mentions?: string[];
}

/**
 * What `GET /ideas/:id/conversation` returns (lane F, `services/worker/convo/reads.py`): the pack's `Conversation`
 * with each entry's `id`, and the words S-08 shows around the timeline worked out on the server
 * (A-API.conventions/6). Event `text` is the whole line, time included ("You shared it. Saturday 14 November,
 * 10:05 am"). Question sets come by reference: the card is lane B's `C-QCARD`, filled from
 * `GET /ideas/:id/question-set` (L-CONVO/4).
 *
 * DEC-111: a reader outside the review desk and the Ones Committee never gets the name, initials or users.id of the
 * person at the review desk. In their place every person field carries the desk itself, `{id: "", name: "The review
 * desk", first_name: "The review desk", initials: ""}` (a mention: "the review desk"), and S-08 draws no face for it.
 */
type ConvoPerson = import("./entities").PersonRef;
export type ConversationEntryView =
  | {
      type: "event";
      id: string;
      code: string;
      text: string;
      at: IsoDate;
      /** The merged idea's closing line links to the idea it joined (L-MERGE.effects/6). */
      link?: { label: string; to: string };
    }
  | {
      type: "message";
      id: string;
      from: ConvoPerson;
      /** "Meera from the review desk" (to the desk and the committee), "The review desk" (DEC-111), "Ravi Nair",
       * "You". */
      from_label: string;
      you: boolean;
      /** The masked copy (L-CONVO/7); "Message removed" once removed (L-CONVO/10). */
      text: string;
      files: FileItem[];
      at: IsoDate;
      at_label: string;
      mentions: ConvoPerson[];
      mentions_you: boolean;
      removed: boolean;
      /** Only on the reader's own message, while it can still be removed. */
      can_remove_until?: IsoDate;
    }
  | {
      type: "questions";
      id: string;
      set_id: string;
      state: import("./enums").QuestionSetState;
      by: ConvoPerson;
      by_label: string;
      count: number;
      answered: number;
      due_at: IsoDate | null;
      /** The card's title in plain words: "The review desk has 3 questions about your idea" for the sharer, "The
       * review desk asked 3 questions." for the crew and the build team (DEC-111), "Meera from the review desk asked
       * 3 questions." for the desk and the committee (BLD-F065). */
      title: string;
      /** The sharer's, while open: "Answer by Thursday 19 November, 6 pm. One at a time, typed or spoken, and each
       * answer is added to its part of your idea." */
      deadline?: string;
      /** The sharer's, while open: S-R3 (S-08.rules/1). */
      answer_url?: string;
      at: IsoDate;
      at_label: string;
    }
  | {
      type: "answers";
      id: string;
      set_id: string;
      from: ConvoPerson;
      /** "Your answers to the review desk’s 3 questions" (DEC-111; "Kavya’s answers to your 3 questions" for the
       * reviewer). */
      title: string;
      answers: {
        id: string;
        question_id: string;
        text: string;
        added_to: string;
        /** "The problem", "How often" … ("Added to <part>"). */
        added_to_label: string;
        at: IsoDate;
        files: FileItem[];
      }[];
      /** For the sharer while the desk decides: "Each answer was added to its part of your idea. The review desk
       * decides by Friday 20 November." (S-08 "Answers sent", DEC-111). */
      footer?: string;
      at: IsoDate;
      at_label: string;
    };
export interface ConversationView extends Omit<Conversation, "entries" | "participants"> {
  /** "Your idea" / "The idea", and the line under the header (S-08.layout/1). */
  header: { whose: string; line: string };
  participants: { person: ConvoPerson; label: string; doing: string; you: boolean }[];
  entries: ConversationEntryView[];
  composer: {
    /** By audience (L-CONVO/5): "Message the review desk", "Message the crew", "Reply to Sanjay". */
    placeholder: string;
    /** "Only you and the review desk see this conversation." */
    visibility: string;
    /** For the sharer while questions are open (L-CONVO/4). */
    questions_line?: string;
    /** A merged idea's conversation takes no new messages: why, and where to write. */
    closed?: string;
    /** Whether the reader may add files: the sharer, the review desk and the core committee (BLD-F063). S-08
     * shows the attach control only then. */
    can_attach: boolean;
  };
  /** For the sharer before anyone has written ("No messages yet"). */
  empty?: { title: string; body: string };
}
export interface ConversationMessageResponse {
  entry: ConversationEntryView;
  /** How many details were hidden from the words as sent. */
  hidden: number;
}
/** Error codes: `empty_message`, `too_long`, `too_many_files`, `too_many_mentions`, `files_not_allowed`,
 * `hide_unavailable`, `file_unavailable`, `file_not_checked`, `file_has_detail`, `conversation_closed`, `idempotency_key_reused`,
 * `not_yours`, `too_late`, `not_found`. */
export type ConversationErrorCode =
  | "empty_message"
  | "too_long"
  | "too_many_files"
  | "too_many_mentions"
  | "files_not_allowed"
  | "hide_unavailable"
  | "file_unavailable"
  | "file_not_checked"
  | "file_has_detail"
  | "conversation_closed"
  | "idempotency_key_reused"
  | "in_progress"
  | "not_yours"
  | "too_late"
  | "not_found";

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
  promises: Record<string, number | string | string[] | number[]>;
  sorting: {
    affects: string[];
    areas: string[];
    brings: Brings[];
    helpers: string[];
    /** Lane C: the chips shown first, the search words and the choice rules (S-05 part 2, S-06B). */
    controls?: {
      affects: { shown: string[]; all: string[]; search_link: string; search_label: string; rule: string };
      area: { shown: string[]; all: string[]; search_link: string; search_label: string; rule: string };
      kind: { options: { value: Kind; label: string }[]; rule: string };
      brings: { options: { value: Brings; label: string }[]; exclusive: Brings; rule: string };
      helpers: string[];
    };
  };
  /** Lane C: the declaration beside Submit and Save (L-SUBMIT.pre/5). */
  declaration?: { version: string; submit: string; save: string };
  /** From their lanes as they land (A-API.config). */
  uploads?: UploadConfig;
  placeholders?: [string, string, string];
  flags?: Record<string, "default" | "alternative" | "off">;
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
