# Idea: copy and controls per state

Generated from the prototype board `reference/prototype/Idea.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Idea.jpg`

Headings: H1: Rejection SMS codes confuse investors; H2: The problem; H2: Where it is; H2: About this idea; H2: Team up on this idea

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
Back to the Wall
With the review desk
Rejection SMS codes confuse investors
IDEA-2026-001412
Shared Monday 9 November by Ravi Nair, Investor service, Hyderabad
The problem
Investors get a rejection code by SMS with no explanation. Branches in Hyderabad take repeated calls from investors asking what the code means and what to do next.
This is the short summary everyone at KFintech sees. Ravi’s own words stay with him and the review desk.
Where it is
Shared
, done
Monday 9 November
Checked and matched
, done
3 similar ideas linked
Reviewed
, now
By Monday 16 November
Now
Built
, to come
If it’s picked
Shipped
, to come
Then we measure what changed
About this idea
Who it affects
Investors, branch teams
What it’s worth
Saves time and cost
Area
Investor service
Linked
3 similar ideas linked
Who can see it
Everyone at KFintech, as this short summary
Team up on this idea
4 colleagues on it. Ravi leads it and decides who joins. The crew helps the review desk with detail and, if it’s picked, helps build it.
RN
AS
PK
SN
Send Ravi a note about what you bring. Raised the same thing? Bring your idea along, and if Ravi approves, it joins this one with credit to you.
Team up
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
| a | Back to the Wall | href=Wall.dc.html |
| button | Team up | type=button |

## State: `from=My ideas`

Screenshot: `reference/shots/Idea__from-my-ideas.jpg`

Announced (role=alert or status): status: You’re on the crew. You’ll get its updates.

Text added:

```
Back to My ideas
5 colleagues on it. Ravi leads it and decides who joins. The crew helps the review desk with detail and, if it’s picked, helps build it.
You’re on the crew. You’ll get its updates.
Say hello
```

Text removed:

```
Back to the Wall
4 colleagues on it. Ravi leads it and decides who joins. The crew helps the review desk with detail and, if it’s picked, helps build it.
Send Ravi a note about what you bring. Raised the same thing? Bring your idea along, and if Ravi approves, it joins this one with credit to you.
Team up
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Back to My ideas | href=MyIdeas.dc.html |
| a | Say hello | href=Messages.dc.html |

## State: `from=Your idea IDEA-2026-001481`

Screenshot: `reference/shots/Idea__from-your-idea-idea-2026-001481.jpg`

Text added:

```
Back to IDEA-2026-001481
```

Text removed:

```
Back to the Wall
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Back to IDEA-2026-001481 | href=Status.dc.html |

## State: `teamUp=Request sent`

Screenshot: `reference/shots/Idea__teamup-request-sent.jpg`

Text added:

```
Waiting for Ravi
Withdraw
Ravi reads your note and decides. You’ll hear in your Inbox.
```

Text removed:

```
Send Ravi a note about what you bring. Raised the same thing? Bring your idea along, and if Ravi approves, it joins this one with credit to you.
Team up
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Withdraw | type=button |

## State: `teamUp=On the crew`

Screenshot: `reference/shots/Idea__teamup-on-the-crew.jpg`

Announced (role=alert or status): status: You’re on the crew. You’ll get its updates.

Text added:

```
5 colleagues on it. Ravi leads it and decides who joins. The crew helps the review desk with detail and, if it’s picked, helps build it.
You’re on the crew. You’ll get its updates.
Say hello
```

Text removed:

```
4 colleagues on it. Ravi leads it and decides who joins. The crew helps the review desk with detail and, if it’s picked, helps build it.
Send Ravi a note about what you bring. Raised the same thing? Bring your idea along, and if Ravi approves, it joins this one with credit to you.
Team up
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Say hello | href=Messages.dc.html |
