# New wording in lane E, for HR's sign-off

Written 18 Nov 2026 for HR's review of launch-facing copy (SHIP_PLAN §8). Everything else on lane E's screens (the Wall, My ideas, an idea's page, your One dashboard and Profile) is the design pack's own copy (`1pc-handoff/reference/copy/`), used as it stands. These are the lines lane E had to add where no board draws them, each with where it shows and the file and line that holds it (paths under `apps/web/src/app/`, unless a row gives the full path from the repo root). Each is copied word for word from the code; words in braces, such as {n} or {tier}, are filled in at run time. In the code each line in sections 2 to 7 is marked `// NOT DRAWN (BLD-E0xx): HR sign-off`, and the same lines are listed in `docs/BUILD_LOG.md` (BLD-E041 to BLD-E046) and `1pc-handoff/00-overview/GAPS.md`.

## 1. When a screen cannot load

The boards draw no error state for these three screens. Each shows one line with the error style when the page's data cannot be read.

| Module | Where it shows | File and line | Wording |
|---|---|---|---|
| `S-WALL` | The Wall, when it cannot be read | `wall/wall-screen.tsx:47` | We can't load the Wall just now. Please try again in a minute. |
| `S-07` | My ideas, when the list cannot be read | `my-ideas/my-ideas-screen.tsx:49` | We can't load your ideas just now. Please try again in a minute. |
| `S-06`, `S-09` | An idea's page (your own, or a colleague's), when it cannot be read | `ideas/[id]/page.tsx:26` | We can't load this idea just now. Please try again in a minute. |

## 2. Your One dashboard (S-ONE, BLD-E041 and BLD-E042)

| Where it shows | File and line | Wording |
|---|---|---|
| Your impact brief, while a new brief waits for the programme team (`L-ONES.rules/5`) | `one/rules.ts:13` | Your new brief is with the programme team. It goes on the Wall once they approve it. |
| Your impact brief, with none on the Wall | `one/rules.ts:15` | No brief on the Wall yet. |
| "Propose a new brief", the field's label | `one/rules.ts:18` | Your new brief |
| The same field, its counter | `one/rules.ts:20` | {n} of 140 characters |
| The same field, its button | `one/rules.ts:22` | Send for approval |
| The same field, closing it | `one/rules.ts:24` | Cancel |
| Impact so far, a figure not in yet (`L-IMPACT/4`) | `one/rules.ts:27` | Being measured |
| The dashboard, when it cannot be read | `one/rules.ts:29` | We can't load your One dashboard just now. Please try again in a minute. |
| The same, the button under it | `one/rules.ts:32` | Try again |
| The Showcase brief sheet, when it cannot be read | `one/showcase-sheet.tsx:16` | We can't load your Showcase brief just now. Please try again in a minute. |
| The Showcase brief sheet, its close button | `one/showcase-sheet.tsx:18` | Close |

## 3. Profile (S-H6, BLD-E043)

| Where it shows | File and line | Wording |
|---|---|---|
| Profile, when it cannot be read | `profile/rules.ts:13` | We can't load your profile just now. Please try again in a minute. |
| The same, the button under it | `profile/rules.ts:16` | Try again |
| The Teams switch, while IT has not approved Teams (DEC-105) | `profile/rules.ts:19` | Coming soon |
| A One's link in the head (`S-H6.rules/4`) | `profile/rules.ts:22` | Your One dashboard |
| "How should we refer to you?", the four answers (DEC-108) | `profile/rules.ts:61`, `:63`, `:65`, `:67` | She / He / They / Prefer not to say |
| The same card, its heading | `profile/rules.ts:72` | How should we refer to you? |
| The same card, the line under it | `profile/rules.ts:74` | We use this only to word the English copy of your voice notes. |

## 4. An idea's page and the Wall (S-06, S-WALL, BLD-E044)

| Module | Where it shows | File and line | Wording |
|---|---|---|---|
| `S-06` | Your idea's page, when the decision or the questions part cannot be read | `ideas/[id]/sharer-screen.tsx:36` | We can't load this just now. Please try again in a minute. |
| `S-06` | On a phone, Copy reference, when the browser will not copy | `ideas/[id]/parts.tsx:179` | Couldn't copy the reference. It's {reference}. |
| `S-WALL` | A One who hides their name from the Wall | `wall/wall-screen.tsx:576` | One No. {n} |

**Changed by DEC-111 (BLD-E053).** These are the pack's drawn lines, not new ones: each named the reviewer, and now names the review desk for a sharer who is not on the review desk or the Ones Committee. A sharer on the desk or the committee still reads the drawn line with the name. The label comes from one constant (`apps/web/src/lib/review-desk.ts`), so a different label is a one-line change. {reviewer} is the reviewer's first name, {day} a date such as Monday 16 November.

| Module | Where it shows | File and line | Old → new |
|---|---|---|---|
| `S-06` | Your idea's page once picked, the line under "Picked. A team is being chosen to build it." (Status.md, PhoneStatus.md) | `ideas/[id]/decision.ts:47`, `:57` | {reviewer} from the review desk picked it on {day}. → The review desk picked it on {day}. (The rest of the line, "and joined it with …" and "The build team is chosen by …", is unchanged.) |
| `S-06` | Your idea's page, Not now and Not picked, the end of the line under the card (Status.md, PhoneStatus.md) | `ideas/[id]/decision.ts:48`, `:67`, `:75`, `:77` | {reviewer}’s full reason is below. → The review desk’s full reason is below. |

## 5. A few words for a One (`/ones/write/:id`, BLD-E044)

The page where a colleague writes to a One who is moving up a tier. No board draws it; S-ONE's "Messages for you" reads what it saves.

| Where it shows | File and line | Wording |
|---|---|---|
| The page's title | `ones/write/[id]/page.tsx:12` | A few words for a One |
| An invitation that is closed or not theirs | `ones/write/[id]/page.tsx:14` | This invitation isn't open, or isn't for you. |
| The same, the link under it | `ones/write/[id]/page.tsx:16` | Back to home |
| The heading | `ones/write/[id]/page.tsx:18` | A few words for {One} |
| The line under the heading | `ones/write/[id]/page.tsx:21` | They are moving to {tier}. They'll read your message, with your name, when they see their new tier. |
| After sending | `ones/write/[id]/page.tsx:23` | Thank you. Your message is saved. |
| The field's label | `ones/write/[id]/write-form.tsx:26` | Your message |
| The field's hint | `ones/write/[id]/write-form.tsx:28` | A few sentences. What did they do that mattered? No personal details. |
| The button | `ones/write/[id]/write-form.tsx:30` | Send your message |
| Under the field, a personal detail found | `ones/write/[id]/write-form.tsx:9` | Please take out any personal details (numbers, addresses, investor names). |
| Under the field, off-topic or unkind | `ones/write/[id]/write-form.tsx:11` | Please reword this: it reads as off-topic or unkind, so we can't save it as it is. |
| Under the field, a colleague's or client's name | `ones/write/[id]/write-form.tsx:13` | Leave out the names of colleagues and clients: everyone will see this. |
| Under the field, too short | `ones/write/[id]/write-form.tsx:15` | Please write at least a short sentence. |
| Under the field, too long | `ones/write/[id]/write-form.tsx:17` | Please keep it under 600 characters. |
| Under the field, a second message | `ones/write/[id]/write-form.tsx:19` | You've already written a message for this. |
| Under the field, the checks are down | `ones/write/[id]/write-form.tsx:21` | We can't check text just now. Please try again in a few minutes. |
| Under the field, any other failure | `ones/write/[id]/write-form.tsx:24` | That didn't save. Please try again. |

## 6. Showcase brief (`/ones/showcase/:id`, BLD-E044)

The committee's printable copy of a One's Showcase brief. No board draws it.

| Where it shows | File and line | Wording |
|---|---|---|
| The page's title | `ones/showcase/[id]/page.tsx:14` | Showcase brief |
| A brief that is not there | `ones/showcase/[id]/page.tsx:16` | We can't find that Showcase brief. |
| The same, the link under it | `ones/showcase/[id]/page.tsx:18` | Back to the Wall |
| The heading ("retired" in place of the number for a retired One) | `ones/showcase/[id]/page.tsx:21` | Showcase brief: No. {number}, {name} |
| The tier line | `ones/showcase/[id]/page.tsx:23` | Tier {tier}, {tier name}. |
| When it was last changed | `ones/showcase/[id]/page.tsx:25` | The One last updated it {date}. |
| A brief with none of the One's own words | `ones/showcase/[id]/page.tsx:27` | The One hasn't added their own words yet. |

## 7. Withdrawing a team-up request on a colleague's idea (S-09, BLD-E046)

These words are lane F's, from the team-up sheet, and are already on HR's list in `docs/hr-wording/lane-f.md`. Lane E shows them in one more place: the Team up card on a colleague's idea, where "Withdraw request" now sits.

| Where it shows | File and line | Wording |
|---|---|---|
| "Withdraw request" on the card, while it runs | `ideas/[id]/colleague-screen.tsx:227` (word at `apps/web/src/components/teamup/teamup-sheet.tsx:91`) | Withdrawing… |
| Under the card, a withdraw with no answer from the server | `ideas/[id]/colleague-screen.tsx:197` (word at `apps/web/src/components/teamup/teamup-sheet.tsx:107`) | Check your connection, then try again. |
| Under the card, a withdraw the server refused | `ideas/[id]/colleague-screen.tsx:188` | The server's own line for that refusal, as the team-up sheet shows it (listed in `docs/hr-wording/lane-f.md`, section 2) |

## 8. Worker (`services/worker/ideapage/`)

The worker builds these lines and sends them to the page, so they are not in `apps/web/src/app/`: paths in this section are from the repo root. In the code each is marked `# NOT DRAWN`. Words in braces are filled in at run time: {lead_ref} is the reference of the idea it now belongs to, {q} the words searched for, {n} how many ideas the other list holds, {list} that list's name (Yours or Teamed up), {closes} the day changes closed, {name} the build team's name, {checks} the days after shipping when the effect is measured and {details} the line's first part about personal details ("Personal details hidden", "1 PAN hidden" or "No personal details found").

| Module | Where it shows | File and line | Wording |
|---|---|---|---|
| `S-09` | A colleague's idea that is now part of another, on its Team up card | `services/worker/ideapage/colleague.py:74` | This idea is now part of {lead_ref}. Team up there. |
| `S-09` | A colleague's idea that was not picked or was withdrawn, on its Team up card | `services/worker/ideapage/colleague.py:82` | This idea isn’t going ahead, so it isn’t taking a crew. |
| `S-07` | My ideas, "Needs you" with nothing in it, the line under the heading (the heading, "Nothing needs you right now.", is the Home board's) | `services/worker/ideapage/mine.py:401` | When the review desk asks you something, it shows here. |
| `S-07` | My ideas, "Drafts" with nothing in it, the heading | `services/worker/ideapage/mine.py:402` | No drafts. |
| `S-07` | The same, the line under it | `services/worker/ideapage/mine.py:402` | Drafts you start are kept here, saved as you type. |
| `S-07` | My ideas, "Picked and building" with nothing in it, the heading | `services/worker/ideapage/mine.py:408` | Nothing picked yet. |
| `S-07` | The same, the line under it | `services/worker/ideapage/mine.py:409` | Ideas the review desk picks show here while a team builds them. |
| `S-07` | My ideas, a search that finds nothing | `services/worker/ideapage/mine.py:524`, `:558` | Nothing found for “{q}”. |
| `S-07` | My ideas, under a search's answer, what it looked at | `services/worker/ideapage/mine.py:528` | Matched on titles, short summaries and references. |
| `S-07` | My ideas, a search that finds nothing, the line under its heading | `services/worker/ideapage/mine.py:559` | Try other words, or clear the search. |
| `S-07` | My ideas on a computer, when the list on show has nothing for the filter or search and the other list has some, the button (the board draws “See 1 in Teamed up”; the count, and “Yours” for the other list, are filled in) | `services/worker/ideapage/mine.py:550` | See {n} in {list} |
| `S-07` | My ideas, "Teamed up" with nothing in it, the heading | `services/worker/ideapage/mine.py:577` | You haven’t teamed up on an idea yet. |
| `S-07` | The same, the line under it | `services/worker/ideapage/mine.py:580` | Find your crew to join colleagues on something similar. |
| `S-06`, `S-09` | An idea's track, the “Checked and matched” line when similar ideas could not be checked and none are linked (the sentence is the pack's, from Check it; on the track it is not drawn, BLD-E052). On your own idea's page it follows the personal details part; a colleague sees the sentence alone | `services/worker/ideapage/track.py:100` | {details}. Couldn’t check for similar ideas. The review desk will. |
| `S-06` | Your idea's page, when questions came before the review desk opened it | `services/worker/ideapage/sharer.py:247` | The idea itself can’t be changed now. Write to the review desk in the conversation. |
| `S-06` | Your idea's page, when the time for changes ran out before the review desk opened it | `services/worker/ideapage/sharer.py:249`, `:250` | The time for changes ended on {closes}, so the idea itself can’t be changed now. Write to the review desk in the conversation. |
| `S-06` | Your idea's page while it is being built, the card's first line | `services/worker/ideapage/sharer.py:315` | Being built. |
| `S-06` | The same, the line under it (the first sentence only when a build team is named) | `services/worker/ideapage/sharer.py:316`, `:317` | {name} is building it. The build team writes to you in the conversation. |
| `S-06` | Your idea's page once it has shipped, the card's first line | `services/worker/ideapage/sharer.py:322` | Shipped. It’s live. |
| `S-06` | The same, the line under it | `services/worker/ideapage/sharer.py:323` | We measure what changed {checks} days after it shipped. |
| `S-06` | Your idea's page, What you shared, How often or Who it affects when the sharer left it empty (the words are S-R2's for the same part, BLD-E057) | `services/worker/ideapage/sharer.py:390`, used at `:447`, `:454` | Not given. |

**Changed by DEC-111 (BLD-E053).** Each of these lines named the reviewer by first name ({reviewer}). For a sharer who is not on the review desk or the Ones Committee it now names the review desk; a sharer on the desk or the committee still reads the old line. The label comes from one constant (`services/worker/onepc/words.py`), so a different label is a one-line change. In the code each is marked `DEC-111`. {day} is a date such as Monday 16 November, {questions} a count such as "3 questions", {when} "today", "yesterday" or "on Monday".

| Module | Where it shows | File and line | Old → new |
|---|---|---|---|
| `S-06` | Your idea's page once the answers are sent, the card's first line (Status.md, PhoneStatus.md) | `services/worker/ideapage/sharer.py:288`, `:295` | Sent. {reviewer} has your answers. → Sent. The review desk has your answers. |
| `S-06` | The same, the track's Reviewed line (Status.md, PhoneStatus.md) | `services/worker/ideapage/sharer.py:562`, `services/worker/ideapage/track.py:194` | {reviewer} has your answers. By {day} → The review desk has your answers. By {day} |
| `S-06` | Your idea's page, What you shared, the line over each answer under its part (Status.md) | `services/worker/ideapage/sharer.py:351`, `:357` | From your answer to {reviewer}, {day} → From your answer to the review desk, {day} |
| `S-06` | Your idea's page, What it's worth, over the review desk's revised figures (not drawn before DEC-111) | `services/worker/ideapage/sharer.py:423` | Revised by {reviewer} → Revised by the review desk |
| `S-07` | My ideas on a phone, an idea with questions waiting (PhoneMyIdeas.md). The phone now shows the computer's sentence (MyIdeas.md) | `services/worker/ideapage/mine.py:242`, `:250` | {reviewer} from the review desk asked you {questions} {when}. → The review desk asked you {questions} {when}. |
| `S-07` | My ideas, an idea whose answers are with the review desk (not drawn) | `services/worker/ideapage/mine.py:264`, `:265`, `:268` | {reviewer} has your answers. The review desk decides by {day}. → The review desk has your answers. It decides by {day}. |

## 9. Asking to join the build team (S-06, BLD-E055)

The Status and PhoneStatus boards draw the first line below in the Picked state, but `1pc-handoff/reference/copy/Status.md` and `PhoneStatus.md` leave it out, because it shows only after "Ask to join the build team" is pressed. It is the boards' wording, used as drawn, and needs HR's sign-off like the rest. The second line is lane E's, for a Pick with no team-chosen-by date, which should not happen (L-DECIDE/6 sets one on every Pick). Words in braces are filled in at run time: {day month} is the date the build team is chosen by, such as 27 November. The board's "Undo" beside the line is not built (BLD-E055).

| Module | Where it shows | File and line | Wording |
|---|---|---|---|
| `S-06` | Your idea's page after a Pick, in place of "Ask to join the build team" once you have asked (drawn at `1pc-handoff/reference/prototype/Status.dc.html:899` and `PhoneStatus.dc.html:889`) | `ideas/[id]/join-build.tsx:39` | Asked. The build lead replies by {day month}. |
| `S-06` | The same, when the Pick has no team-chosen-by date | `ideas/[id]/join-build.tsx:39` | Asked. The build lead replies. |

**Changed by DEC-105 while Teams is off (BLD-E054).** Teams is built but switched off until IT approves it (DEC-105), so these drawn lines named a channel nobody receives. While the `comms.teams` switch is off, each names only email; when IT approves Teams and the switch is turned on, the drawn line (old) shows again, word for word. Lane F does the same on S-08 with the same switch.

| Module | Where it shows | File and line | Old → new |
|---|---|---|---|
| `S-06` | Your idea's page while it is open to changes, the window line under the track (Status.md) | `services/worker/ideapage/sharer.py:226`, `:231` | Open to changes until {day}. Edit or withdraw it any time before the review desk opens it. We tell you on Teams and by email when anything moves. → Open to changes until {day}. Edit or withdraw it any time before the review desk opens it. We tell you by email when anything moves. |
| `S-06` | Your idea's page just after sharing, the card's line under the first clause (Status.md) | `services/worker/ideapage/sharer.py:279` | We’ll tell you on Teams and by email when anything changes. → We’ll tell you by email when anything changes. |
| `S-06` | The same on a phone (PhoneStatus.md) | `services/worker/ideapage/sharer.py:282` | We’ll tell you on Teams and by email. → We’ll tell you by email. |
| `S-06` | Your idea's page once the answers are sent, the card's line under "Sent." (Status.md, PhoneStatus.md) | `services/worker/ideapage/sharer.py:297`, `:299` | Each answer was added to its part of your idea, under What you shared. The review desk decides by {day}, and you hear in your Inbox, on Teams and by email. → Each answer was added to its part of your idea, under What you shared. The review desk decides by {day}, and you hear in your Inbox and by email. |
| `S-06` | Your idea's page, You and the review desk with no messages yet (Status.md; the phone's line, PhoneStatus.md, never named Teams and is unchanged) | `services/worker/ideapage/sharer.py:632` | No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we tell you on Teams. → No messages yet. If the review desk has a question, it shows up here and in your Inbox. |
