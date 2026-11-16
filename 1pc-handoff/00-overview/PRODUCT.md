---
id: P-PRODUCT
title: What 1% Club is, who uses it and how an idea lives
rev: 1
status: baseline
source: reference/prototype/Handoff.dc.html
depends_on: []
last_delta: none
---

# 1% Club: product in one page

## `P-PRODUCT.arc` The arc

An employee who notices something broken says it in their own words, from wherever they are, sees it become a clear draft that hides customer details, confirms it in one check, and from then on always knows where it stands and what to do next, until it ships or gets a reasoned answer.

Three words run through the product: **Tell it** (say the problem), **Check it** (confirm the draft), **Send it** (share it). Tagline: "1% spark. 99% sweat."

1% Club is a sub-brand under KFintech's "The Garage" programme ("Part of The Garage" in the Landing footer). It goes live to the whole organisation on day one.

## `P-PRODUCT.roles` Roles

One person can hold several roles at once.

| Role | Who | Can |
|---|---|---|
| **Employee** | Anyone with a KFintech account | Share problems, see the Wall, team up on others' ideas, read their Inbox, manage their profile |
| **Sharer** | The employee who shared a given idea | Edit or withdraw it until the review desk opens it; answer the desk's questions; read the decision; restore a withdrawn idea |
| **Lead** | The sharer, in their role toward their idea's crew | Approve a team-up request three ways: merge it, team up only, or decline |
| **Crew member** | Anyone approved onto an idea's crew | See the idea's conversation, get its updates, help the review desk with detail, join the build if picked |
| **Reviewer** (review desk) | Named reviewers | Open ideas, revise what an idea is worth and its sorting, ask the sharer questions with a time to answer, decide (Pick, Not now, Not picked) with a reason, merge similar ideas and team the sharers up |
| **Committee member** (Ones Committee) | Core committee | See every decision for 30 days; extend the window 30 days at a time up to 3 months; reverse a decision once, with a note the sharer reads |
| **Build team** | The team given a picked idea | Post updates and ask the sharer to check things in the idea's conversation |
| **One** | An employee whose shipped idea made a measured difference | Has a number and a tier; gets the One dashboard; shows on the Wall and the office screen |
| **Display operator** | Whoever runs the launch screen | Starts the 30-second launch sequence |

Rules:

1. The review desk decides on the committee's behalf, and the sharer hears at once. The committee can only reverse inside its window.
2. There is no appeal flow of any kind.
3. A reviewer never reviews their own idea. `OPEN:` conflict-of-interest routing (who reviews a reviewer's idea) is not drawn; default: any other reviewer.
4. Points are private to the person and never decide who becomes a One.

## `P-PRODUCT.lifecycle` How an idea lives

**Five stages**, shown as a track on every idea: Shared → Checked and matched → Reviewed → Built → Shipped.

| Stage | What happens | Promise shown to the person |
|---|---|---|
| Shared | The idea gets a reference at once and is saved as written | "About two minutes" to share |
| Checked and matched | Personal details are hidden; similar ideas are linked | "Automatic, minutes" |
| Reviewed | The review desk reads it, may ask questions, decides with a reason | "Within 5 working days" |
| Built | If picked, a team builds it; the sharer and crew can join | "Depends on the fix" |
| Shipped | It is live; its effect is measured 30 and 90 days after | "After it's live" |

**Statuses** an idea can show (pill colours in `E-ENUMS.idea-status`): Draft, Checking, With the review desk, Needs you, Picked, Being built, Shipped, Not now, Not picked, Withdrawn, Merged.

Key moments:

1. **Before sending:** the idea is a draft, saved as the person types, on the account, visible only to them. Drafts follow the person across devices. Other channels (email forward, Teams) also land as drafts; nothing arrives already sent.
2. **Edit window:** after sending, the sharer can edit or withdraw until the review desk opens it, and at the latest 3 days after sharing. After the desk opens it, the idea itself is locked; the sharer writes in the conversation instead.
3. **Questions:** the desk asks questions pinned to parts of the idea, with a time to answer (1 day, 3 days or 1 week). The sharer answers one at a time on the Answer screen; each answer lands on its part and posts back to the conversation.
4. **Decision:** Pick, Not now (with a date it comes back) or Not picked, each with a reason of at least 30 characters that the sharer reads word for word.
5. **Committee window:** 30 days from the decision, extendable 30 days at a time to 3 months in all. A reversal is final and carries a note to the sharer. When the window closes, the decision stands.
6. **Merge:** a sharer can ask another idea's lead to merge theirs in (the lead decides); the review desk can merge two ideas directly and team the sharers up. Both sharers stay credited. The committee can reverse a desk merge within 30 days.
7. **Withdraw:** the sharer can withdraw before review; a withdrawn idea goes back to their drafts and can be restored.

Full rules: `05-logic/`.

## `P-PRODUCT.privacy` Who sees what

| Thing | Sharer | Crew | Review desk | Committee | Everyone |
|---|---|---|---|---|---|
| Their own words (raw text, voice) | Yes | No | Yes | Yes | No |
| The short summary, sorting, stage | Yes | Yes | Yes | Yes | Yes, on the Wall once shared |
| Hidden customer details (unmasked) | Only in their own text box | No | No | No | No |
| Attached files (after checking) | Yes | Yes | Yes | Yes | No |
| The idea's conversation | Yes | Yes | Yes | Yes | No |
| Questions and answers | Yes | Yes | Yes | Yes | No |
| The decision and its reason | Yes | Yes | Yes | Yes | Stage only |
| The sharer's name on the Wall | Their choice, in Profile | | | | If the sharer allows it |
| Points | Only the person | No | No | No | No |

Customer personal details (folio, PAN, phone, email, account numbers) are hidden automatically in text and in files before anyone else can see anything. See `L-HIDE`.

## `P-PRODUCT.promises` Numbers the product promises

Each is a business promise that the back end must be able to change without a release. Owners and sign-off state are in `P-DECISIONS`.

| Promise | Value |
|---|---|
| Minimum words before a draft can move to Check it | 30 characters |
| Voice clip length | Up to 3 minutes |
| Review decision | Within 5 working days of sharing |
| Edit and withdraw window | Until the desk opens it, at most 3 days |
| Time to answer questions | 1 day, 3 days (default) or 1 week |
| Reminders before a question is due | 1 day before and 2 hours before |
| Decision reason, reversal note | At least 30 characters |
| Team-up note | At least 30 characters |
| Merge note (review desk) | At least 20 characters |
| Committee window | 30 days, extendable by 30 days up to 3 months |
| "Not now" comes back in | 1 month, 3 months (default) or 6 months |
| Impact measured | 30 and 90 days after shipping |
| Drafts kept | 30 days, then archived, never deleted silently |
| Sign-in code | 6 digits, valid 10 minutes, 3 tries, resend after 45 seconds |
| Session length | 8 hours (KFintech policy) |
| A One may change their number | Any free number 1 to 999, for 30 days after becoming a One |

## `P-PRODUCT.cast` Demo cast (fictional; do not seed production)

| Person | Role on the boards |
|---|---|
| Kavya Menon (KM) | The signed-in employee. Investor service, Hyderabad. Tier 2, Glow. 340 points |
| Meera Iyer (MI) | Review desk |
| Ravi Nair (RN) | Lead of IDEA-2026-001412 "Rejection SMS codes confuse investors" |
| Sanjay Pillai (SP) | Lead of IDEA-2026-001398 "No script for calls about rejections" |
| Rohan Mehta (RM) | Ones Committee |
| Arjun Rao (AR) | Build team lead for "Plain words for transaction rejections" |
| Rohit Menon, Ananya Rao, Sneha Kulkarni, Arjun Nair, Priya Iyer, Farhan Nair, Deepa | The Ones (numbers 1, 17, 9, 5, 23, 3, 12) |

Today on the boards is the week of Saturday 14 to Monday 16 November 2026.
