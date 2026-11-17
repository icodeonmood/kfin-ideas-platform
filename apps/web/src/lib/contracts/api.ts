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
  OneCard,
  OnePost,
  Person,
  PersonSettings,
  SimilarMatch,
  Sorting,
  TeamUpRequest,
  WallStage,
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

// A-API.desk (S-R1)
export type DeskTab = "to_review" | "waiting" | "answered" | "decided";
export interface DeskQuery {
  tab?: DeskTab;
  sort?: DeskSort;
  q?: string;
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
  own_words: { seq: number; via: string; at: IsoDate; text: string | null }[];
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
  own_words: { seq: number; via: string; at: IsoDate; text: string | null }[];
  parts: ReviewerPart[];
  worth: { tiles: WorthTile[]; revised: boolean; revision: WorthRevision | null; line: string };
  similar: ReviewerSimilar[];
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
