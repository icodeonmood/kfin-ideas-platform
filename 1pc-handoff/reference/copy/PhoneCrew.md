# PhoneCrew: copy and controls per state

Generated from the prototype board `reference/prototype/PhoneCrew.dc.html`, rendered at 390px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/PhoneCrew.jpg`

Headings: H3: Rejection SMS codes confuse investors; H3: No script for calls about rejections; H3: Branch queue times are not tracked anywhere; H3: Nominee updates bounce between two teams; H3: Same KYC details typed into three screens

### Text, top to bottom

```
Home
Find your crew
With the review desk
Rejection SMS codes confuse investors
Investor service, Hyderabad
RN
AS
PK
Ravi Nair and 3 others on it
Same R07 SMS as your idea from Saturday
The problem, in their words
Investors get a code, not a reason, and then they call us.
Picked
No script for calls about rejections
Operations, Mumbai
SP
MD
Sanjay Pillai and 1 other on it
The calls your idea is about
The problem, in their words
Every agent explains a rejection differently, so investors call back.
With the review desk
Branch queue times are not tracked anywhere
Investor service, Chennai
DS
KR
AN
Divya Shah and 2 others on it
Your area, Investor service
The problem, in their words
We can't tell how long investors wait, so we can't staff for it.
With the review desk
Nominee updates bounce between two teams
Operations, Pune
AR
GS
Arjun Rao and 1 other on it
Investors call your branch about this too
The problem, in their words
A nominee change goes back and forth between two teams for days.
Shared
Same KYC details typed into three screens
Operations, Hyderabad
NK
Neha Kulkarni on it
Same office as you, Hyderabad
The problem, in their words
We key one investor's KYC into three systems, and they drift apart.
See details
Team up
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
| a | Back to Home | href=PhoneHome.dc.html |
| button | See details of Rejection SMS codes confuse investors | type=button |
| button | Team up on Rejection SMS codes confuse investors, with Ravi Nair | type=button |
| a | Home | href=PhoneHome.dc.html |
| a | My ideas | href=PhoneMyIdeas.dc.html |
| a | Share a problem | href=PhoneCompose.dc.html |
| a | Wall | href=PhoneWall.dc.html |
| a | Inbox, 2 new | href=PhoneInbox.dc.html |

## State: `view=Request sent`

Screenshot: `reference/shots/PhoneCrew__view-request-sent.jpg`

Text added:

```
Waiting for Ravi
```

Text removed:

```
Team up
```


## State: `view=Teamed up`

Screenshot: `reference/shots/PhoneCrew__view-teamed-up.jpg`

Text added:

```
You're on it
You’re on it
```

Text removed:

```
Team up
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | See details of No script for calls about rejections | type=button |
| button | You’re on the crew for No script for calls about rejections. Tap to leave. | type=button |

## State: `view=Everyone seen`

Screenshot: `reference/shots/PhoneCrew__view-everyone-seen.jpg`

Announced (role=alert or status): status: That's everyone for now You teamed up on 1 idea. New ideas close to yours show up here. See them again

Text added:

```
That's everyone for now
You teamed up on 1 idea. New ideas close to yours show up here.
See them again
```

Text removed:

```
With the review desk
Rejection SMS codes confuse investors
Investor service, Hyderabad
RN
AS
PK
Ravi Nair and 3 others on it
Same R07 SMS as your idea from Saturday
The problem, in their words
Investors get a code, not a reason, and then they call us.
Picked
No script for calls about rejections
Operations, Mumbai
SP
MD
Sanjay Pillai and 1 other on it
The calls your idea is about
The problem, in their words
Every agent explains a rejection differently, so investors call back.
With the review desk
Branch queue times are not tracked anywhere
Investor service, Chennai
DS
KR
AN
Divya Shah and 2 others on it
Your area, Investor service
The problem, in their words
We can't tell how long investors wait, so we can't staff for it.
With the review desk
Nominee updates bounce between two teams
Operations, Pune
AR
GS
Arjun Rao and 1 other on it
Investors call your branch about this too
The problem, in their words
A nominee change goes back and forth between two teams for days.
Shared
Same KYC details typed into three screens
Operations, Hyderabad
NK
Neha Kulkarni on it
Same office as you, Hyderabad
The problem, in their words
We key one investor's KYC into three systems, and they drift apart.
See details
Team up
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | See them again | type=button |

## State: `details=Open`

Screenshot: `reference/shots/PhoneCrew__details-open.jpg`

Text added:

```
IDEA-2026-001412
They’re looking for
Someone who takes these calls at a branch every day.
The crew
Open the full idea
```

Text removed:

```
See details
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Close details | type=button |
| a | Open the full idea | href=PhoneIdea.dc.html |

## State: `teamUp=Icon only`

Screenshot: `reference/shots/PhoneCrew__teamup-icon-only.jpg`

Text is the same as the default state (the difference is visual or in timing; see the screenshot).
