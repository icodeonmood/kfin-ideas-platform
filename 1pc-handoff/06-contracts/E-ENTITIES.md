---
id: E-ENTITIES
title: Entities the screens need
rev: 1
status: baseline
source: reference/copy/
depends_on: [E-ENUMS]
last_delta: none
---

# Entities

These are the shapes the front end needs, derived from what the screens show. They are not a database design. If the repo's `contracts/` and `db/` already define an entity, keep it and add what is missing; record differences in `REPO-MAPPING.md`. Types are TypeScript-style; `?` means optional; dates are ISO 8601 in UTC, displayed in the person's time zone.

## `E-ENTITIES.person` Person

```ts
Person {
  id: string
  name: string                  // "Kavya Menon"
  first_name: string            // "Kavya" (used in copy: "Send to Ravi")
  initials: string              // "KM"
  area: string                  // department, e.g. "Investor service"
  city: string                  // "Hyderabad"
  email: string                 // never shown to others
  roles: Role[]                 // E-ENUMS.roles
  tier: 1..7                    // shown on own account button and Profile
  one?: { number: number, flag: 'founding'|'one', since: date, number_locked_at: date, brief: string }
  points?: number               // returned only to the person themselves
  settings?: { show_name_on_wall: boolean, teams: boolean, email: boolean, reminders: boolean, shortcut_p: boolean, sidebar_folded: boolean }  // self only
}
PersonRef { id, name, first_name, initials, area?, city?, role_label? }   // role_label: "from the review desk", "from the Ones Committee"
```

## `E-ENTITIES.draft` Draft

```ts
Draft {
  id: string
  owner_id: string
  channel: 'web'|'voice'|'email'|'teams'
  origin?: { subject?: string, received_at: date, note: string }     // "Fwd: R07 rejections again"
  messages: Message[]                // the person's own words, in order
  parts: {                           // E-ENUMS.draft
    title:   Part<string>            // + summary
    summary: Part<string>
    often:   Part<string|null>
    who:     Part<string[]>
    value:   Part<Brings[]>
    area:    Part<string>
    similar: Part<SimilarMatch[]>
  }
  hidden: HiddenDetail[]
  sorting: Sorting
  files: FileItem[]
  fix?: Fix
  helpers?: { picks: string[], text?: string }      // "Who would help"
  merge_request?: { other_idea_id, state, note, lead_reason? }   // E-ENUMS.teamup (draft merge request)
  step: string                       // where the person is
  saved_at: date
  saved_on: { device: 'phone'|'laptop', this_device: boolean }
  ready: boolean                     // L-DRAFT.parts/7
  min_chars: number, char_count: number
  receipt?: string[]                 // lines for the conversation after the last run
  suggestions?: string[]             // up to two next prompts
}
Message { id, text, lang?, at: date, device, via: 'typed'|'voice'|'email'|'teams', files: FileItem[], spans: HiddenSpan[] }
Part<T> { state: 'waiting'|'updating'|'filled'|'pinned'|'failed', value: T, why?: string, source_quote?: string, mean_ms?: number }
HiddenSpan { start: number, end: number, kind }        // positions in the owner's own text
HiddenDetail { id, kind, masked: string, state: 'hidden'|'shown', reason?, shown_at? }   // masked: "Folio ••••89"
Sorting { affects: Choice<string[]>, kind: Choice<string>, area: Choice<string>, brings: Choice<Brings[]>, confirmed: boolean }
Choice<T> { value: T, source: 'suggested'|'confirmed'|'changed', why?: string }
Fix { how: string, needs?: string, solved_already?: 'yes'|'partly'|'no'|'dont_know', solved_note?: string,
      worth?: Worth, basis?: string, risks?: string, ready_count: number, included: boolean }
Worth { hours_month?: Range, cost_month?: Range, revenue_month?: Range, outside_tools?: 'none'|'partly'|'fully' }
Range { low: number, high?: number, text: string }      // text: "70 to 150 hours a month"
```

## `E-ENTITIES.idea` Idea

```ts
Idea {
  id: string                         // "IDEA-2026-001481"
  status: IdeaStatus                 // E-ENUMS.idea-status
  kind: 'problem'|'fix'|'business_idea'
  title: string
  summary: string                    // the public short summary
  often?: string
  affects: string[]
  brings: Brings[]
  area: string
  city: string
  sharer: PersonRef | null           // null to others when the sharer hides their name
  credited: PersonRef[]              // after a merge, both sharers
  shared_at: date
  share_seconds?: number             // "Done in 40 seconds"
  stages: StageState[]               // five, E-ENUMS.stage
  crew: { lead: PersonRef, members: PersonRef[], count: number, ones_count: number }
  linked_similar_count: number
  wall: { shown: boolean, opened_7d: number }
  merged_into?: string
  // below: only for the sharer, crew (not own_words), reviewers, committee, build team
  own_words?: Message[]              // masked for everyone but the sharer
  hidden?: HiddenDetail[]
  files?: FileItem[]
  fix?: Fix
  worth?: { sharer: Worth, reviewer?: Worth & { note?: string, by: PersonRef, at: date } }
  answers_by_part?: Record<Part, Answer[]>
  edit_window?: { open: boolean, closes_at: date, opened_by_desk_at?: date }
  review?: { decide_by: date, reviewer?: PersonRef, opened_at?: date }
  decision?: Decision
  versions?: { count: number, summary: string }      // "3 versions. Title changed once, sorting confirmed."
  kept_separate?: boolean
  next_step: { sentence: string, action?: { label: string, to: string } }   // for list rows and the card sentence
}
StageState { stage, state: 'done'|'now'|'to_come'|'not_going_ahead', detail?: string, at?: date }
```

## `E-ENTITIES.review` Questions, answers, decisions, windows

```ts
QuestionSet { id, idea_id, by: PersonRef, state, sent_at?, seen_at?, due_at?, time_to_answer: '1d'|'3d'|'1w', questions: Question[], overdue: boolean }
Question { id, part: Part, text: string, suggested: boolean, answer?: Answer }
Answer { id, question_id, text: string, files: FileItem[], by: PersonRef, at: date, added_to: Part }
Decision { id, idea_id, choice: 'pick'|'not_now'|'not_picked', reason: string, by: PersonRef, at: date,
           joined_with?: string, return_at?: date, team_by?: date, window: Window, reversal?: Reversal }
Window { state: 'open'|'extended'|'reversed'|'expired', opens_at, closes_at, max_closes_at, extended_times: number }
Reversal { to: 'pick'|'not_now'|'not_picked', note: string, by: PersonRef, at: date, return_at?: date }
```

## `E-ENTITIES.crew` Team-up, merge, crew cards

```ts
TeamUpRequest { id, idea_id, from: PersonRef, note: string, brought: IdeaRef[], state, lead_reason?: string, sent_at, answered_at? }
Merge { id, lead_idea_id, merged_idea_id, by: PersonRef, via: 'lead_accepted'|'review_desk', team_up: boolean, note: string, at: date, window?: Window }
IdeaRef { id, title, status, meta?: string }           // meta: "IDEA-2026-001481, with the review desk"
SimilarMatch { idea: IdeaPreview, strength: 'close'|'related', reason: string, my_request?: TeamUpRequest }
IdeaPreview { id, title, status, area, city, shared_at, lead: PersonRef, crew_faces: PersonRef[], crew_count: number,
              in_their_words: string, looking_for?: string, hue: 1|2,
              compare?: { often?: string, who?: string, worth?: string } }     // reviewers only
CrewCard extends IdeaPreview { reason_kind, reason: string }                   // "Same R07 SMS as your idea from Saturday"
```

## `E-ENTITIES.files` Files and links

```ts
FileItem { id, kind: 'file'|'link'|'folder', name: string, type: string, size?: number, pages?: number, count?: number,
           state, problem?: string, hidden_note?: string, link_scope?: 'internal'|'external', url?: string,
           added_by: PersonRef, added_at: date, view_url?: string }
```

## `E-ENTITIES.inbox` Inbox and conversation

```ts
InboxItem { id, kind, from: PersonRef | 'system', idea?: IdeaRef, line: string, at: date, unread: boolean, needs_you: boolean,
            due?: { at: date, label: string }, archived: boolean, body: object /* by kind */, actions: Action[] }
Action { label: string, to?: string, op?: string, style: 'primary'|'line'|'text' }
ConversationEntry = { type: 'event', text: string, at: date }
                  | { type: 'message', from: PersonRef, text: string, files: FileItem[], at: date, mentions: PersonRef[] }
                  | { type: 'questions', set: QuestionSet }
                  | { type: 'answers', set_id: string, answers: Answer[], at: date }
Conversation { idea: IdeaRef, audience: 'you_and_desk'|'crew_and_desk'|'build_team', participants: { person: PersonRef, doing: string }[], entries: ConversationEntry[] }
```

## `E-ENTITIES.wall` Wall, Ones, impact

```ts
WallStage { stage: 'picked'|'being_built'|'shipped', count: number, items: { id, title, kind, area, crew_count }[] }
JustInRow { id, title, kind, area, shared_at: date, opened_7d: number, crew_count: number, ones_count: number }
OneCard { number, person: PersonRef, tier, tier_name, flag, brief: string }
OnePost { one: OneCard, text: string, ago: string, shipped: boolean, adopted_by?: number, figure: { value: string, line: string }, likes: number, comments: number, thread_to: string }
ImpactTotals { hours_month: number, money_year: number, fixes_measured: number, reached: { count: number, noun: string } }
LiveFix { what: string, change: string, measured: '30d'|'90d'|'pending', due?: date, team: string }
Impact { time?: { value, line }, money?: { value, line, finance_confirmed: boolean }, effort?: { value, line }, scale?: { value, line } }
EmberIssue { number, month: string, headline: string, items: string[], state: 'latest'|'coming_soon', to?: string }
```
