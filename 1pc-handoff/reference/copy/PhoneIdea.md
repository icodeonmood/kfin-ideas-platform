# PhoneIdea: copy and controls per state

Generated from the prototype board `reference/prototype/PhoneIdea.dc.html`, rendered at 390px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/PhoneIdea.jpg`

Headings: H1: Rejection SMS codes confuse investors; H2: Team up on this idea; H2: Where it is; H2: About this idea

### Text, top to bottom

```
Wall
IDEA-2026-001412
With the review desk
Rejection SMS codes confuse investors
Shared Monday 9 November by Ravi Nair, Investor service, Hyderabad
Investors get a rejection code by SMS with no explanation. Branches in Hyderabad take repeated calls from investors asking what the code means and what to do next.
The short summary everyone sees. Ravi’s own words stay with him and the review desk.
Team up on this idea
4 colleagues on it. Ravi leads it and decides who joins. The crew helps the review desk with detail and, if it’s picked, helps build it.
RN
AS
PK
SN
Send Ravi a note about what you bring. Raised the same thing? Bring your idea along, and if Ravi approves, it joins this one with credit to you.
Team up
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
| a | Back to the Wall | href=PhoneWall.dc.html |
| button | Team up | type=button |
| a | Home | href=PhoneHome.dc.html |
| a | My ideas | href=PhoneMyIdeas.dc.html |
| a | Share a problem | href=PhoneCompose.dc.html |
| a | Wall | href=PhoneWall.dc.html |
| a | Inbox, 2 new | href=PhoneInbox.dc.html |

## State: `from=My ideas`

Screenshot: `reference/shots/PhoneIdea__from-my-ideas.jpg`

Announced (role=alert or status): status: You’re on the crew. You’ll get its updates.

Text added:

```
5 colleagues on it. Ravi leads it and decides who joins. The crew helps the review desk with detail and, if it’s picked, helps build it.
KM
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
| a | Back to My ideas | href=PhoneMyIdeas.dc.html |
| a | Say hello | href=PhoneMessages.dc.html |

## State: `teamUp=Request sent`

Screenshot: `reference/shots/PhoneIdea__teamup-request-sent.jpg`

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

Screenshot: `reference/shots/PhoneIdea__teamup-on-the-crew.jpg`

Announced (role=alert or status): status: You’re on the crew. You’ll get its updates.

Text added:

```
5 colleagues on it. Ravi leads it and decides who joins. The crew helps the review desk with detail and, if it’s picked, helps build it.
KM
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
| a | Say hello | href=PhoneMessages.dc.html |
