# PhoneMyIdeas: copy and controls per state

Generated from the prototype board `reference/prototype/PhoneMyIdeas.dc.html`, rendered at 390px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/PhoneMyIdeas.jpg`

Headings: H1: My ideas; H3: Investors call to ask why a redemption was rejected; H3: Distributors can’t see why an SIP registration is stuck; H3: Track couriered redemption forms; H3: Plain words for transaction rejections; H3: Cheque scans need re-uploading at month end

### Text, top to bottom

```
1% Club
KM
My ideas
All
5
Needs you
1
Drafts
1
With the desk
0
Picked and building
3
Shipped
0
Closed
0
Sorted by latest activity
Copy link
Investors call to ask why a redemption was rejected
Needs you
Meera from the review desk asked you 3 questions on Monday.
Answer the questions
Distributors can’t see why an SIP registration is stuck
Draft
About a minute left. Your words and sorting are kept.
Carry on
Track couriered redemption forms
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
Plain words for transaction rejections
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
Cheque scans need re-uploading at month end
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
Home
My ideas
Share
Wall
2
Inbox
```

### Controls

| Element | Label | Attributes |
|---|---|---|
| a | 1% Club | href=PhoneHome.dc.html |
| button | Your account, Kavya Menon, Tier 2, Glow | type=button |
| button | All 5 | type=button, pressed=true |
| button | Needs you 1 | type=button, pressed=false |
| button | Drafts 1 | type=button, pressed=false |
| button | With the desk 0 | type=button, pressed=false |
| button | Picked and building 3 | type=button, pressed=false |
| button | Shipped 0 | type=button, pressed=false |
| button | Closed 0 | type=button, pressed=false |
| button | Sorted by latest activity | type=button |
| button | Copy link | type=button |
| a | Investors call to ask why a redemption was rejected Needs you Meera from the review desk asked you 3 questions on Monday. Answer the questio | href=PhoneAnswer.dc.html |
| a | Distributors can’t see why an SIP registration is stuck Draft About a minute left. Your words and sorting are kept. Carry on | href=PhoneCompose.dc.html |
| a | Track couriered redemption forms Being built Being tested at two branches, Hyderabad and Pune. See where it is | href=PhoneStatus.dc.html |
| a | Plain words for transaction rejections Picked A team is being chosen to build it. You’ll hear who by Friday 20 November. See where it is | href=PhoneStatus.dc.html |
| a | Cheque scans need re-uploading at month end Picked The committee reversed the review desk’s not picked: the January upgrade covers head-offi | href=PhoneStatus.dc.html |
| a | Home | href=PhoneHome.dc.html |
| a | My ideas | href=PhoneMyIdeas.dc.html |
| a | Share a problem | href=PhoneCompose.dc.html |
| a | Wall | href=PhoneWall.dc.html |
| a | Inbox, 2 new | href=PhoneInbox.dc.html |

## State: `filter=Needs you`

Screenshot: `reference/shots/PhoneMyIdeas__filter-needs-you.jpg`

Text removed:

```
Distributors can’t see why an SIP registration is stuck
Draft
About a minute left. Your words and sorting are kept.
Carry on
Track couriered redemption forms
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
Plain words for transaction rejections
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
Cheque scans need re-uploading at month end
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All 5 | type=button, pressed=false |
| button | Needs you 1 | type=button, pressed=true |

## State: `filter=Drafts`

Screenshot: `reference/shots/PhoneMyIdeas__filter-drafts.jpg`

Text removed:

```
Investors call to ask why a redemption was rejected
Meera from the review desk asked you 3 questions on Monday.
Answer the questions
Track couriered redemption forms
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
Plain words for transaction rejections
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
Cheque scans need re-uploading at month end
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All 5 | type=button, pressed=false |
| button | Drafts 1 | type=button, pressed=true |

## State: `filter=With the desk`

Screenshot: `reference/shots/PhoneMyIdeas__filter-with-the-desk.jpg`

Text added:

```
Nothing with the review desk right now.
Ideas wait here for up to 5 working days before a decision.
Show all ideas
```

Text removed:

```
Investors call to ask why a redemption was rejected
Meera from the review desk asked you 3 questions on Monday.
Answer the questions
Distributors can’t see why an SIP registration is stuck
Draft
About a minute left. Your words and sorting are kept.
Carry on
Track couriered redemption forms
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
Plain words for transaction rejections
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
Cheque scans need re-uploading at month end
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All 5 | type=button, pressed=false |
| button | With the desk 0 | type=button, pressed=true |
| button | Show all ideas | type=button |

## State: `filter=Picked and building`

Screenshot: `reference/shots/PhoneMyIdeas__filter-picked-and-building.jpg`

Text removed:

```
Investors call to ask why a redemption was rejected
Meera from the review desk asked you 3 questions on Monday.
Answer the questions
Distributors can’t see why an SIP registration is stuck
Draft
About a minute left. Your words and sorting are kept.
Carry on
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All 5 | type=button, pressed=false |
| button | Picked and building 3 | type=button, pressed=true |

## State: `filter=Shipped`

Screenshot: `reference/shots/PhoneMyIdeas__filter-shipped.jpg`

Text added:

```
Nothing shipped yet.
Ideas land here once they ship and their impact is measured.
Show all ideas
```

Text removed:

```
Investors call to ask why a redemption was rejected
Meera from the review desk asked you 3 questions on Monday.
Answer the questions
Distributors can’t see why an SIP registration is stuck
Draft
About a minute left. Your words and sorting are kept.
Carry on
Track couriered redemption forms
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
Plain words for transaction rejections
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
Cheque scans need re-uploading at month end
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All 5 | type=button, pressed=false |
| button | Shipped 0 | type=button, pressed=true |
| button | Show all ideas | type=button |

## State: `filter=Closed`

Screenshot: `reference/shots/PhoneMyIdeas__filter-closed.jpg`

Text added:

```
Nothing closed.
Ideas that weren’t picked or were withdrawn show here, with the reason.
Show all ideas
```

Text removed:

```
Investors call to ask why a redemption was rejected
Meera from the review desk asked you 3 questions on Monday.
Answer the questions
Distributors can’t see why an SIP registration is stuck
Draft
About a minute left. Your words and sorting are kept.
Carry on
Track couriered redemption forms
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
Plain words for transaction rejections
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
Cheque scans need re-uploading at month end
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All 5 | type=button, pressed=false |
| button | Closed 0 | type=button, pressed=true |
| button | Show all ideas | type=button |

## State: `view=Loading`

Screenshot: `reference/shots/PhoneMyIdeas__view-loading.jpg`

Text removed:

```
5
1
1
0
3
0
0
Investors call to ask why a redemption was rejected
Meera from the review desk asked you 3 questions on Monday.
Answer the questions
Distributors can’t see why an SIP registration is stuck
Draft
About a minute left. Your words and sorting are kept.
Carry on
Track couriered redemption forms
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
Plain words for transaction rejections
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
Cheque scans need re-uploading at month end
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All | type=button, pressed=true |
| button | Needs you | type=button, pressed=false |
| button | Drafts | type=button, pressed=false |
| button | With the desk | type=button, pressed=false |
| button | Picked and building | type=button, pressed=false |
| button | Shipped | type=button, pressed=false |
| button | Closed | type=button, pressed=false |

## State: `view=Empty (first time)`

Screenshot: `reference/shots/PhoneMyIdeas__view-empty-first-time.jpg`

Text added:

```
Nothing shared yet
Spot something that keeps going wrong? Say it in your own words, typed or spoken. It takes about two minutes.
Share your first problem
```

Text removed:

```
All
5
Needs you
1
Drafts
1
With the desk
0
Picked and building
3
Shipped
0
Closed
0
Sorted by latest activity
Copy link
Investors call to ask why a redemption was rejected
Needs you
Meera from the review desk asked you 3 questions on Monday.
Answer the questions
Distributors can’t see why an SIP registration is stuck
Draft
About a minute left. Your words and sorting are kept.
Carry on
Track couriered redemption forms
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
Plain words for transaction rejections
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
Cheque scans need re-uploading at month end
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Share your first problem | href=PhoneCompose.dc.html |

## State: `view=No results`

Screenshot: `reference/shots/PhoneMyIdeas__view-no-results.jpg`

Text added:

```
Nothing shipped yet.
Ideas land here once they ship and their impact is measured.
Show all ideas
```

Text removed:

```
Investors call to ask why a redemption was rejected
Meera from the review desk asked you 3 questions on Monday.
Answer the questions
Distributors can’t see why an SIP registration is stuck
Draft
About a minute left. Your words and sorting are kept.
Carry on
Track couriered redemption forms
Being built
Being tested at two branches, Hyderabad and Pune.
See where it is
Plain words for transaction rejections
Picked
A team is being chosen to build it. You’ll hear who by Friday 20 November.
See where it is
Cheque scans need re-uploading at month end
Picked
The committee reversed the review desk’s not picked: the January upgrade covers head-office scanners only, so branches would still re-upload.
Read the decision
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All 5 | type=button, pressed=false |
| button | Shipped 0 | type=button, pressed=true |
| button | Show all ideas | type=button |

## State: `arrival=Back from an idea`

Screenshot: `reference/shots/PhoneMyIdeas__arrival-back-from-an-idea.jpg`

Announced (role=alert or status): status: Back where you were: All, latest activity first.

Text added:

```
Back where you were: All, latest activity first.
```

