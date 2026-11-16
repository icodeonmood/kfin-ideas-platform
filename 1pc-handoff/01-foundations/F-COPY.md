---
id: F-COPY
title: Words, voice and vocabulary
rev: 1
status: baseline
source: reference/copy/
depends_on: []
last_delta: none
---

# Words, voice and vocabulary

Exact wording for every screen and state is in `reference/copy/<Board>.md`. This module gives the rules those words follow, so new strings (errors, empty states, notifications) match.

## `F-COPY.voice` Voice

1. Plain, direct, warm. A colleague who knows the system, not the system talking.
2. Indian English spelling (colour, programme, recognise). Dates as "Friday 20 November" in sentences and "14-Nov-26" in compact rows. Times as "11:20 am". Money in rupees with Indian grouping ("₹3,00,000", "₹24 lakh").
3. Sentence case. No all-caps, no exclamation marks, no emoji.
4. Second person for the signed-in person ("your idea", "you asked"). Other people by first name once they have been introduced ("Ravi leads it").
5. Say what happened and what happens next, with a date where there is one: "The review desk will look at it by Friday 20 November."
6. Short. One idea per sentence. No "please", no "kindly", no "successfully".

## `F-COPY.buttons` Buttons and links

1. A button says exactly what it does: "Send 3 questions to Kavya", "Merge and tell both", "Send decision to Kavya". Not "Submit", "OK" or "Confirm".
2. The same action keeps the same name through the flow. "Team up" on the card, "Team up with Ravi" as the sheet title, "Send to Ravi" as the button, "Sent to Ravi" as the result.
3. Counts go in the label when they change what is sent: "Send 1 answer to Meera", "Show 5 more".
4. No arrows, no icons standing in for words on primary actions.
5. Links are underlined text ("Open the full idea"), never "click here".

## `F-COPY.states` Errors, warnings, empty states

1. An error names the problem and the fix, next to the field: "That code didn't match. Check the latest email from 1% Club. 2 tries left."
2. Errors do not apologise and do not blame. Never "Invalid input".
3. A failure says what is safe: "Couldn't send. Your draft is safe." Then one action: "Try again".
4. An empty state says what will appear here and offers the one action that fills it: "Nothing with the review desk right now. Ideas wait here for up to 5 working days before a decision."
5. Waiting states say who is being waited on and until when: "Waiting for Ravi to accept the merge."

## `F-COPY.vocabulary` Vocabulary (use these words, exactly)

| Term | Meaning | Never say |
|---|---|---|
| **1% Club** | The programme and the product | "the portal", "the tool" |
| **Share a problem** | The main action. The product is problem-first; a fix is optional | "Submit an idea", "Share an idea" as the main action |
| **idea** | Any shared item, once it exists, whether problem, fix or business idea | "ticket", "submission", "entry" |
| **Tell it, Check it, Send it** | The three steps of sharing | "Step 1 / 2 / 3" as labels |
| **your words** | What the person typed or said, unedited | "raw input", "transcript" |
| **draft** | The structured version the assistant builds from your words, and any idea not yet sent | "form" |
| **sorting** | Who it affects, what kind it is, area, what it would bring | "categorisation", "tagging", "classification" |
| **What it's worth** | The size of the benefit: time, cost, revenue, reliance on outside tools | "ROI", "business case" |
| **Hidden from everyone** | A customer's personal detail masked in text or files | "redacted", "PII" in the interface |
| **similar ideas** | Ideas matched as close to yours | "duplicates" |
| **Team up** | Ask to join the crew of someone else's idea | "collaborate", "join request" |
| **crew** | The people on an idea. One person leads it | "team" for the crew (a "team" is who builds it after it is picked) |
| **lead** | The person whose idea it is; decides who joins | "owner" |
| **merge** | One idea joins another, with credit to both | "duplicate of", "close as duplicate" |
| **review desk** | The reviewers who read and decide. "Meera from the review desk" when a reviewer speaks | "admin", "moderator", "committee" for the desk |
| **Ones Committee** | The group that can reverse a decision inside its window. Only named for its window and reversals | "appeals board" |
| **Picked / Not now / Not picked** | The three decisions | "approved", "rejected", "declined", "on hold" |
| **Needs you** | Something is waiting on the signed-in person | "action required", "pending" |
| **Shared, Checked and matched, Reviewed, Built, Shipped** | The five stages, in order | any other stage names |
| **The Ones / a One** | People whose shipped idea made a measured difference. Each keeps a number and a tier | "winners", "champions" |
| **tier** | Spark, Glow, Flame, Blaze, White heat, Blue flame, Star (1 to 7) | "level", "rank" |
| **points** | Private to the person; never decide who becomes a One | "score", "leaderboard points" |
| **the Wall** | Where everyone sees shared ideas, the Ones and what shipped | "feed", "dashboard" |
| **Kindling** | The Wall's section of ideas by stage | none |
| **The Ember** | The programme's newsletter | none |
| **Inbox** | The one list of what waits on you and what changed | "notifications" |
| **conversation** | The one message thread each idea has | "chat", "comments" |

Words the product never uses in its own voice: "duplicate", "rejected", "already solved", "appeal", "invalid", "error" as a heading.

## `F-COPY.placeholders` Run-time values in copy

Demo names in the prototype copy stand for run-time values. In module files they are written as:

| Placeholder | Demo value on the boards |
|---|---|
| `{me}` | Kavya (Kavya Menon, Investor service, Hyderabad, Tier 2) |
| `{lead}` | Ravi (Ravi Nair), the lead of the other idea |
| `{reviewer}` | Meera (Meera Iyer, review desk) |
| `{member}` | Rohan (Rohan Mehta, Ones Committee) |
| `{idea}` | IDEA-2026-001481 "Investors call to ask why a redemption was rejected" |
| `{other}` | IDEA-2026-001412 "Rejection SMS codes confuse investors" |

Idea references follow the pattern `IDEA-<year>-<six digits>`.

Placeholders still to be filled by the business (shown in square brackets on the boards): `[1% Club address]` (the email address that turns a forwarded mail into a draft), `[EXTENSION]` (IT service desk), `[SIGN-IN ADDRESS]` (the URL behind the launch QR code). See `P-DECISIONS.open`.

## `F-COPY.plurals` Counts and plurals

1. Always agree the noun: "1 question", "3 questions"; "1 One on the crew", "2 Ones on the crew"; "Ravi Nair and 3 others on it", "Sanjay Pillai and 1 other on it", "Neha Kulkarni on it".
2. Zero is written in words where a sentence reads better: "None picked", "No Ones on the crew yet", "Nothing attached".
3. Relative time: under an hour "12 min ago"; under a day "2h ago"; one day "Yesterday"; then "3 days ago"; over a week, the date. Countdowns: "3 days left"; under a day, hours and minutes "07:38 left to answer"; past due "Overdue by 5 hours".
