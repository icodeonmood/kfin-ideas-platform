# New wording in lane E, for HR's sign-off

Written 18 Nov 2026 for HR's review of launch-facing copy (SHIP_PLAN §8). Everything else on lane E's screens (the Wall, My ideas, an idea's page, your One dashboard and Profile) is the design pack's own copy (`1pc-handoff/reference/copy/`), used as it stands. These are the lines lane E had to add where no board draws them, each with where it shows and the file and line that holds it (paths under `apps/web/src/app/`). Each is copied word for word from the code; words in braces, such as {n} or {tier}, are filled in at run time. In the code each line from section 2 on is marked `// NOT DRAWN (BLD-E0xx): HR sign-off`, and the same lines are listed in `docs/BUILD_LOG.md` (BLD-E041 to BLD-E046) and `1pc-handoff/00-overview/GAPS.md`.

## 1. When a screen cannot load

The boards draw no error state for these three screens. Each shows one line with the error style when the page's data cannot be read.

| Module | Where it shows | File and line | Wording |
|---|---|---|---|
| `S-WALL` | The Wall, when it cannot be read | `wall/wall-screen.tsx:47` | We can't load the wall just now. Please try again in a minute. |
| `S-07` | My ideas, when the list cannot be read | `my-ideas/my-ideas-screen.tsx:49` | We can't load your ideas just now. Please try again in a minute. |
| `S-06`, `S-09` | An idea's page (your own, or a colleague's), when it cannot be read | `ideas/[id]/page.tsx:26` | We can't load this idea just now. Please try again in a minute. |

The Wall's line says "the wall" in lower case, as written. Every other screen calls it "the Wall". HR may want the capital.

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
| "Withdraw request" on the card, while it runs | `ideas/[id]/colleague-screen.tsx:227` (word at `components/teamup/teamup-sheet.tsx:91`) | Withdrawing… |
| Under the card, a withdraw with no answer from the server | `ideas/[id]/colleague-screen.tsx:197` (word at `components/teamup/teamup-sheet.tsx:107`) | Check your connection, then try again. |
| Under the card, a withdraw the server refused | `ideas/[id]/colleague-screen.tsx:188` | The server's own line for that refusal, as the team-up sheet shows it (listed in `docs/hr-wording/lane-f.md`, section 2) |
