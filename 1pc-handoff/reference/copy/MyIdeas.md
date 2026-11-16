# MyIdeas: copy and controls per state

Generated from the prototype board `reference/prototype/MyIdeas.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/MyIdeas.jpg`

Headings: H1: My ideas; H3: Investors call to ask why a redemption was rejected; H3: Mandate forms rejected for a signature mismatch; H3: Distributors can’t see why an SIP registration is stuck; H3: Track couriered redemption forms; H3: Plain words for transaction rejections; H3: Cheque scans need re-uploading at month end

### Text, top to bottom

```
1% Club
Share a problem
P
Home
Find your crew
Wall
Inbox
2
Drafts
Distributors can’t see why an SIP registration is stuck
Friday, on your phone
Mandate forms rejected for a signature mismatch
Yesterday, on this laptop
Your ideas
View all
Investors call to ask why a redemption was rejected
Plain words for transaction rejections
Track couriered redemption forms
KM
Kavya Menon
Tier 2, Glow
My ideas
Everything you’ve shared or teamed up on, where it is and what happens next.
Search your ideas
Filter
Yours
6
Teamed up
3
Sort by
Latest activity
Date shared
Stage
Idea
Where it is
Next step
Investors call to ask why a redemption was rejected
IDEA-2026-001481, Shared Saturday 14 November
Needs you
The review desk asked you 3 questions on Monday.
Answer the questions
: Investors call to ask why a redemption was rejected
Mandate forms rejected for a signature mismatch
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Distributors can’t see why an SIP registration is stuck
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
Track couriered redemption forms
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
: Track couriered redemption forms
Plain words for transaction rejections
IDEA-2026-001471, Picked Monday 2 November
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
: Plain words for transaction rejections
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

### Controls

| Element | Label | Attributes |
|---|---|---|
| input | Fold the side bar | type=checkbox |
| a | 1% Club, Home | href=Home.dc.html |
| a | Share a problem P | href=Compose.dc.html |
| a | Home | href=Home.dc.html |
| a | Find your crew | href=Crew.dc.html |
| a | Wall | href=Wall.dc.html |
| a | Inbox, 2 unread | href=Inbox.dc.html |
| a | Distributors can’t see why an SIP registration is stuck Friday, on your phone | href=ComposeResume.dc.html |
| a | Mandate forms rejected for a signature mismatch Yesterday, on this laptop | href=Compose.dc.html |
| a | Search your ideas | href=MyIdeas.dc.html#find |
| a | View all | href=MyIdeas.dc.html |
| a | Investors call to ask why a redemption was rejected | href=Status.dc.html |
| a | Plain words for transaction rejections | href=MyIdeas.dc.html |
| a | Track couriered redemption forms | href=MyIdeas.dc.html |
| a | Your profile and settings, Kavya Menon, Tier 2, Glow | href=Profile.dc.html |
| input | Search your ideas, or ask a question | type=search, expanded=false, autocomplete=off |
| button | Filter | type=button, expanded=false |
| button[tab] | Yours 6 | type=button, selected=true |
| button[tab] | Teamed up 3 | type=button, selected=false |
| button | Latest activity | type=button, pressed=true |
| button | Date shared | type=button, pressed=false |
| button | Stage | type=button, pressed=false |
| a | Investors call to ask why a redemption was rejected | href=Status.dc.html |
| a | Answer the questions : Investors call to ask why a redemption was rejected | href=Answer.dc.html |
| a | Mandate forms rejected for a signature mismatch | href=Compose.dc.html |
| a | Carry on : Mandate forms rejected for a signature mismatch | href=Compose.dc.html |
| a | Distributors can’t see why an SIP registration is stuck | href=ComposeResume.dc.html |
| a | Carry on : Distributors can’t see why an SIP registration is stuck | href=ComposeResume.dc.html |
| a | Track couriered redemption forms | href=Status.dc.html |
| a | See where it is : Track couriered redemption forms | href=Status.dc.html |
| a | Plain words for transaction rejections | href=Status.dc.html |
| a | See where it is : Plain words for transaction rejections | href=Status.dc.html |
| a | Cheque scans need re-uploading at month end | href=Status.dc.html |
| a | Read the decision : Cheque scans need re-uploading at month end | href=Status.dc.html |

## State: `filter=Needs you`

Screenshot: `reference/shots/MyIdeas__filter-needs-you.jpg`

Text added:

```
1
0
```

Text removed:

```
6
3
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
: Track couriered redemption forms
IDEA-2026-001471, Picked Monday 2 November
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
: Plain words for transaction rejections
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Remove Needs you | type=button |
| input | Search in Needs you, or ask a question | type=search, expanded=false, autocomplete=off |
| button[tab] | Yours 1 | type=button, selected=true |
| button[tab] | Teamed up 0 | type=button, selected=false |

## State: `filter=Drafts`

Screenshot: `reference/shots/MyIdeas__filter-drafts.jpg`

Text added:

```
0
```

Text removed:

```
6
3
IDEA-2026-001481, Shared Saturday 14 November
Needs you
The review desk asked you 3 questions on Monday.
Answer the questions
: Investors call to ask why a redemption was rejected
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
: Track couriered redemption forms
IDEA-2026-001471, Picked Monday 2 November
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
: Plain words for transaction rejections
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Remove Drafts | type=button |
| input | Search in Drafts, or ask a question | type=search, expanded=false, autocomplete=off |
| button[tab] | Yours 2 | type=button, selected=true |
| button[tab] | Teamed up 0 | type=button, selected=false |

## State: `filter=With the review desk`

Screenshot: `reference/shots/MyIdeas__filter-with-the-review-desk.jpg`

Text added:

```
With the review desk
0
1
Nothing with the review desk right now.
Ideas wait here for up to 5 working days before a decision.
See 1 in Teamed up
Show all ideas
```

Text removed:

```
6
3
Idea
Where it is
Next step
IDEA-2026-001481, Shared Saturday 14 November
Needs you
The review desk asked you 3 questions on Monday.
Answer the questions
: Investors call to ask why a redemption was rejected
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
: Track couriered redemption forms
IDEA-2026-001471, Picked Monday 2 November
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
: Plain words for transaction rejections
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Remove With the review desk | type=button |
| input | Search in With the review desk, or ask a question | type=search, expanded=false, autocomplete=off |
| button[tab] | Yours 0 | type=button, selected=true |
| button[tab] | Teamed up 1 | type=button, selected=false |
| button | See 1 in Teamed up | type=button |
| button | Show all ideas | type=button |

## State: `filter=Picked and building`

Screenshot: `reference/shots/MyIdeas__filter-picked-and-building.jpg`

Text added:

```
Picked and building
1
```

Text removed:

```
6
IDEA-2026-001481, Shared Saturday 14 November
Needs you
The review desk asked you 3 questions on Monday.
Answer the questions
: Investors call to ask why a redemption was rejected
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Remove Picked and building | type=button |
| input | Search in Picked and building, or ask a question | type=search, expanded=false, autocomplete=off |
| button[tab] | Yours 3 | type=button, selected=true |
| button[tab] | Teamed up 1 | type=button, selected=false |

## State: `filter=Shipped`

Screenshot: `reference/shots/MyIdeas__filter-shipped.jpg`

Text added:

```
Shipped
0
1
Nothing shipped yet.
Ideas land here once they ship and their effect is measured.
See 1 in Teamed up
Show all ideas
```

Text removed:

```
6
3
Idea
Where it is
Next step
IDEA-2026-001481, Shared Saturday 14 November
Needs you
The review desk asked you 3 questions on Monday.
Answer the questions
: Investors call to ask why a redemption was rejected
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
: Track couriered redemption forms
IDEA-2026-001471, Picked Monday 2 November
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
: Plain words for transaction rejections
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Remove Shipped | type=button |
| input | Search in Shipped, or ask a question | type=search, expanded=false, autocomplete=off |
| button[tab] | Yours 0 | type=button, selected=true |
| button[tab] | Teamed up 1 | type=button, selected=false |
| button | See 1 in Teamed up | type=button |
| button | Show all ideas | type=button |

## State: `filter=Closed`

Screenshot: `reference/shots/MyIdeas__filter-closed.jpg`

Text added:

```
Closed
0
0
Nothing closed.
Ideas that weren’t picked or were withdrawn show here, with the reason.
Show all ideas
```

Text removed:

```
6
3
Idea
Where it is
Next step
IDEA-2026-001481, Shared Saturday 14 November
Needs you
The review desk asked you 3 questions on Monday.
Answer the questions
: Investors call to ask why a redemption was rejected
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
: Track couriered redemption forms
IDEA-2026-001471, Picked Monday 2 November
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
: Plain words for transaction rejections
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Remove Closed | type=button |
| input | Search in Closed, or ask a question | type=search, expanded=false, autocomplete=off |
| button[tab] | Yours 0 | type=button, selected=true |
| button[tab] | Teamed up 0 | type=button, selected=false |
| button | Show all ideas | type=button |

## State: `search=Suggestions open`

Screenshot: `reference/shots/MyIdeas__search-suggestions-open.jpg`

Text added:

```
Narrow it to
1
With the review desk
0
Picked and building
Shipped
0
Closed
0
Or ask in your own words
Which of my ideas need me this week?
Ideas about the rejection SMS
What did the review desk say no to, and why?
Search reads your titles, your own words, your files and the review desk’s notes, so it finds ideas by meaning, not only exact words.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| input | Search your ideas, or ask a question | type=search, expanded=true, autocomplete=off |
| button | Filter | type=button, expanded=true |
| button | Needs you 1 | type=button, pressed=false |
| button | Drafts 2 | type=button, pressed=false |
| button | With the review desk 0 | type=button, pressed=false |
| button | Picked and building 3 | type=button, pressed=false |
| button | Shipped 0 | type=button, pressed=false |
| button | Closed 0 | type=button, pressed=false |
| button | Which of my ideas need me this week? | type=button |
| button | Ideas about the rejection SMS | type=button |
| button | What did the review desk say no to, and why? | type=button |

## State: `search=Typed: SMS`

Screenshot: `reference/shots/MyIdeas__search-typed-sms.jpg`

Announced (role=alert or status): status: Found 4 ideas about “sms”: 2 of yours and 2 you teamed up on. Closest: “Rejection SMS codes confuse investors”. Matched on meaning across titles, your own words, your files and the review desk’s notes

Text added:

```
Clear
Found 4 ideas about “sms”: 2 of yours and 2 you teamed up on. Closest: “Rejection SMS codes confuse investors”.
Matched on meaning across titles, your own words, your files and the review desk’s notes.
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they…
Rejection SMS and emails use codes. Replace each code with one plain sentence and what to do…
```

Text removed:

```
6
3
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
: Track couriered redemption forms
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Clear | type=button |
| button[tab] | Yours 2 | type=button, selected=true |
| button[tab] | Teamed up 2 | type=button, selected=false |

## State: `search=Asked a question`

Screenshot: `reference/shots/MyIdeas__search-asked-a-question.jpg`

Announced (role=alert or status): status: One idea needs you. The review desk asked you 3 questions on Monday. Answer them by Thursday 19 November. Read your question as “Needs you” and narrowed the list to it.

Text added:

```
Clear
One idea needs you. The review desk asked you 3 questions on Monday. Answer them by Thursday 19 November.
Read your question as “Needs you” and narrowed the list to it.
1
0
```

Text removed:

```
6
3
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
: Track couriered redemption forms
IDEA-2026-001471, Picked Monday 2 November
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
: Plain words for transaction rejections
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Remove Needs you, read from your question | type=button |
| button | Clear | type=button |
| button[tab] | Yours 1 | type=button, selected=true |
| button[tab] | Teamed up 0 | type=button, selected=false |

## State: `list=Teamed up`

Screenshot: `reference/shots/MyIdeas__list-teamed-up.jpg`

Text added:

```
Rejection SMS codes confuse investors
Arjun Rao’s idea, you teamed up Tuesday 10 November, IDEA-2026-001412
With the review desk
The review desk looks at it on Thursday 19 November. You’ll get a note either way.
Open the idea
: Rejection SMS codes confuse investors
No script for calls about rejections
Sanjay Pillai’s idea, you teamed up Monday 26 October, IDEA-2026-001398
Operations is writing the call script. First draft due Monday 23 November.
: No script for calls about rejections
KYC reminders go to old phone numbers
Deepak Nair’s idea, you teamed up Friday 9 October, IDEA-2026-001377
Shipped
Live since Monday 2 November. The team is measuring how many reminders now reach investors.
See the result
: KYC reminders go to old phone numbers
```

Text removed:

```
IDEA-2026-001481, Shared Saturday 14 November
Needs you
The review desk asked you 3 questions on Monday.
Answer the questions
: Investors call to ask why a redemption was rejected
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
: Track couriered redemption forms
IDEA-2026-001471, Picked Monday 2 November
A team is being chosen to build it. You’ll hear who by Friday 20 November.
: Plain words for transaction rejections
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button[tab] | Yours 6 | type=button, selected=false |
| button[tab] | Teamed up 3 | type=button, selected=true |
| a | Rejection SMS codes confuse investors | href=Idea.dc.html |
| a | Open the idea : Rejection SMS codes confuse investors | href=Idea.dc.html |
| a | No script for calls about rejections | href=Idea.dc.html |
| a | See where it is : No script for calls about rejections | href=Idea.dc.html |
| a | KYC reminders go to old phone numbers | href=Idea.dc.html |
| a | See the result : KYC reminders go to old phone numbers | href=Idea.dc.html |

## State: `view=Loading`

Screenshot: `reference/shots/MyIdeas__view-loading.jpg`

Text removed:

```
6
3
Idea
Where it is
Next step
IDEA-2026-001481, Shared Saturday 14 November
Needs you
The review desk asked you 3 questions on Monday.
Answer the questions
: Investors call to ask why a redemption was rejected
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
: Track couriered redemption forms
IDEA-2026-001471, Picked Monday 2 November
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
: Plain words for transaction rejections
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button[tab] | Yours | type=button, selected=true |
| button[tab] | Teamed up | type=button, selected=false |

## State: `view=Empty (first time)`

Screenshot: `reference/shots/MyIdeas__view-empty-first-time.jpg`

Text added:

```
Nothing shared yet
Spot something that keeps going wrong? Say it in your own words. It takes about two minutes, and you’ll see it here with where it is and what happens next.
or press P anywhereShare your first problem
```

Text removed:

```
Search your ideas
Filter
Yours
6
Teamed up
3
Sort by
Latest activity
Date shared
Stage
Idea
Where it is
Next step
IDEA-2026-001481, Shared Saturday 14 November
Needs you
The review desk asked you 3 questions on Monday.
Answer the questions
: Investors call to ask why a redemption was rejected
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
: Track couriered redemption forms
IDEA-2026-001471, Picked Monday 2 November
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
: Plain words for transaction rejections
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Share your first problem | href=Compose.dc.html |

## State: `view=No results`

Screenshot: `reference/shots/MyIdeas__view-no-results.jpg`

Text added:

```
Shipped
0
1
Nothing shipped yet.
Ideas land here once they ship and their effect is measured.
See 1 in Teamed up
Show all ideas
```

Text removed:

```
6
3
Idea
Where it is
Next step
IDEA-2026-001481, Shared Saturday 14 November
Needs you
The review desk asked you 3 questions on Monday.
Answer the questions
: Investors call to ask why a redemption was rejected
Saved yesterday, on this laptop
Draft
Two lines so far. Your words are kept.
Carry on
: Mandate forms rejected for a signature mismatch
Saved 8:42 pm Friday, on your phone
Draft
About a minute left. Your words and sorting are kept.
Carry on
: Distributors can’t see why an SIP registration is stuck
IDEA-2026-001468, Shared Wednesday 28 October
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
: Track couriered redemption forms
IDEA-2026-001471, Picked Monday 2 November
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
: Plain words for transaction rejections
Cheque scans need re-uploading at month end
IDEA-2026-001455, Picked by the Ones Committee, Friday 13 November
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
: Cheque scans need re-uploading at month end
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Remove Shipped | type=button |
| input | Search in Shipped, or ask a question | type=search, expanded=false, autocomplete=off |
| button[tab] | Yours 0 | type=button, selected=true |
| button[tab] | Teamed up 1 | type=button, selected=false |
| button | See 1 in Teamed up | type=button |
| button | Show all ideas | type=button |

## State: `arrival=Back from an idea`

Screenshot: `reference/shots/MyIdeas__arrival-back-from-an-idea.jpg`

Announced (role=alert or status): status: Back where you were: Yours.

Text added:

```
Back where you were: Yours.
```

