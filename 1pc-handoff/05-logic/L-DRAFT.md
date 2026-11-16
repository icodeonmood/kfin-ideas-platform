---
id: L-DRAFT
title: Building the draft from the person's words
rev: 1
status: baseline
source: reference/css/draft-loader-module.js
depends_on: [L-HIDE, L-SORT, L-SIMILAR, E-ENTITIES]
last_delta: none
---

# L-DRAFT: Building the draft from the person's words

The engine behind "Tell it": turn free words (typed, spoken, forwarded) into a structured draft, live, without ever making the person wait or rewriting what they said.

## `L-DRAFT.input` Inputs

| Input | From |
|---|---|
| Messages | The person's own words, one message at a time, in any supported language, typed or transcribed |
| Attachments | Files and links added in the prompt box |
| Channel | Web (typed, voice), email forward, Teams message or voice note |
| Person context | Their area (department), city, role, and their other ideas |
| Direct changes | Parts the person edited by hand ("Your call") |

## `L-DRAFT.parts` The six parts (independent services)

Each part is its own service call, started together when a message arrives, and each returns on its own. The front end shows each as it lands (`C-DRAFT-LOADER`).

| Part | Returns | Also returns |
|---|---|---|
| Title and summary | A title of at most 70 characters, sentence case, no jargon; a summary of 2 to 3 sentences using only what the person said | Which sentence the title came from |
| How often | A frequency phrase ("About 40 calls a day at one branch") or null | The quoted source phrase |
| Who it affects | One or more groups from the configured list (Investors, KFin teams, Distributors, AMCs, …) | A reason: "because you mentioned investors and the branch" |
| What it's worth | One or more of: saves time, saves cost, earns revenue, cuts reliance on outside tools, or "not sure yet" | The quoted source phrase |
| Area | One area from the configured list (Investor service, Operations, Distributor experience, Corporate registry, Technology, …) | A reason |
| Similar ideas | Up to 8 matches with a match strength and a one-line reason each (`L-SIMILAR`) | |

Rules:

1. **Only from the person's words.** No part may introduce a fact, number or name the person did not give. If the words do not support a part, it returns null and the slot reads "Waiting for your words".
2. **Every suggested value carries its reason** (a quoted phrase or a short "because"), shown under the value. A value without a reason is not shown as a suggestion.
3. **Threshold.** The draft cannot move to Check it until the person's words total at least 30 characters (stated up front on phone: "At least 30 characters, and no fix needed", with a live "30 more characters" count). Parts start forming from about 25 characters; similar-idea matching starts at 50. Below the threshold the panel says "Your draft needs a little more first." The older design record mentions a 50-character minimum; 30 is current.
4. **Re-runs.** Each new message re-runs only the parts it could change; unchanged parts keep their value and do not flicker. Hidden-detail detection (`L-HIDE`) runs on every message before any part sees the text; parts only ever receive masked text.
5. `L-DRAFT.pins` **Pins.** A part the person changed by hand is pinned: later messages never overwrite it. The person can unpin by choosing "Suggest again".
6. **Latency reporting.** Each part reports its response time; the service keeps a rolling 7-day p50 per part and exposes it to the front end as the "mean" the loader uses (`C-DRAFT-LOADER.maths`).
7. **Draft is ready** when title, summary and area are present. How often, who and worth may be null; similar ideas may be empty or failed.
8. **Receipt.** After each run the service returns a short list of what changed, in plain sentences, for the conversation (`C-DRAFT-PANEL.behaviour/5`), and up to two suggested next prompts ("Add what you already tried").
9. **Language.** The draft is written in English whatever language the person used; their own words are kept as given, with the detected language recorded. `OPEN:` `P-DECISIONS.open/10`.
10. **Interview variant (flag S1).** After the first message, ask up to three short questions, each skippable: "How often does it happen?", "Who feels it most?", "Any rough size?". The answers are treated as further messages. Then the draft is built once.

## `L-DRAFT.autosave` Saving and cross-device

1. A draft exists on the server from the first keystroke that follows a 1-second pause. Every later change is saved within 2 seconds of the person stopping. The save status follows `C-TASKBAR.save`.
2. Saved: all messages, attachments, the six parts with their pins, sorting confirmations, the fix sheet, who would help, and which step the person is on.
3. A draft is private to its owner. Nothing in a draft is visible to anyone else, including reviewers.
4. A draft can be opened on any device. It records where it was last saved ("on your phone", "on this laptop": device class plus whether it is the current device) and when.
5. One active editor at a time: opening a draft on a second device takes over; the first shows "This draft is open on your phone. Carry on here?" `NOT DRAWN:` wording is the default.
6. Starting "Share a problem" while a recent draft exists offers: "You have a draft from Friday: … Last saved on your phone, 8:42 pm. Continue it here, or start a new one below." with "Continue that draft" and "Start a new one".
7. Offline: typing continues and is kept on the device; the status reads "Unsaved, you're offline"; on reconnect the device copy is sent and the status returns to "Saved at …". If the server copy changed meanwhile, the newer message set wins and nothing typed is discarded (both sets of messages are kept, in time order).
8. Retention: drafts untouched for 30 days are archived (not deleted) and can be restored from My ideas → Drafts. `P-DECISIONS.signoff/1`.
9. "Save and close" returns to Home; the draft shows under "Drafts" in the sidebar and in My ideas.

## `L-DRAFT.voice` Voice

1. Recording starts only on the person's action (except flag S3 "Voice first" on phone). Maximum 3 minutes per clip; the count is shown.
2. Words appear in the box as recognised. The final transcript replaces the interim text and is editable before sending.
3. Audio is used for transcription and then deleted; only the text is kept (`P-DECISIONS.open/11`).
4. A voice note in another language is kept as transcribed in that language as "your words", and the draft is in English. Other channels say so: "Voice message, 1 minute 12 seconds, in Telugu. Typed up in English."
5. Microphone permission denied → the blocked state in `C-PROMPT.voice`; typing always works.

## `L-DRAFT.channels` Other ways in

| Channel | How | Lands as |
|---|---|---|
| Email | Forward a thread to the 1% Club address. The person's note on top becomes their words; the thread becomes context; attachments come along | A draft marked "From your email, today at 9:14 am: "Fwd: R07 rejections again"". "We turned it into this draft. Nothing has been sent." |
| Teams | Chat with the 1% Club app; text, screenshots or a voice note | A draft marked "From Teams, yesterday 7:02 pm" |
| App | `OPEN:` coming soon | |

Rules: the sender is matched to an employee by their work address or Teams identity; unmatched senders get a polite bounce. Hidden-detail detection runs before the draft is stored. Arrivals are listed on `S-H3` under "Arrived from elsewhere" with "Check and send", and reach the Inbox as "kept your draft from your phone/email". Nothing arriving this way is ever shared without the person going through Check it.

## `L-DRAFT.errors` Failure handling

| Failure | Behaviour |
|---|---|
| One part fails or times out | That slot offers manual entry; the rest proceed (`C-DRAFT-LOADER.failure`) |
| All parts fail | `NOT DRAWN:` the words are saved. The panel says "We couldn't build the draft just now. Your words are saved. Try again." with a retry; the person can still fill parts by hand and move on |
| Save fails | `NOT DRAWN:` status "Couldn't save. Trying again." with automatic retry and back-off; words stay on the device |

Contract: `A-API.drafts`, `A-API.draft-stream`.

## `L-DRAFT.touchpoints` Where the front end depends on this

`S-04`, `S-04B`, `S-03`, `S-H3`
