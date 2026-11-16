# Crew: copy and controls per state

Generated from the prototype board `reference/prototype/Crew.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Crew.jpg`

Headings: H1: Find your crew; H3: Rejection SMS codes confuse investors; H3: No script for calls about rejections; H3: Branch queue times are not tracked anywhere; H3: Nominee updates bounce between two teams; H3: Same KYC details typed into three screens; H2: Your crews

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
Home
Find your crew
Ideas close to yours. Team up, or pass.
Filters
5 ideas close to yours
With the review desk
Rejection SMS codes confuse investors
Investor service, Hyderabad
Same R07 SMS as your idea from Saturday
The problem, in their words
Investors get a code, not a reason, and then they call us.
They're looking for
Someone who takes these calls at a branch every day.
RN
AS
PK
Ravi Nair and 3 others on it
Team up
Picked
No script for calls about rejections
Operations, Mumbai
The calls your idea is about
The problem, in their words
Every agent explains a rejection differently, so investors call back.
They're looking for
Real examples of what investors ask on these calls.
SP
MD
Sanjay Pillai and 1 other on it
Team up
With the review desk
Branch queue times are not tracked anywhere
Investor service, Chennai
Your area, Investor service
The problem, in their words
We can't tell how long investors wait, so we can't staff for it.
They're looking for
A branch that will count queue times for two weeks.
DS
KR
AN
Divya Shah and 2 others on it
Team up
With the review desk
Nominee updates bounce between two teams
Operations, Pune
Investors call your branch about this too
The problem, in their words
A nominee change goes back and forth between two teams for days.
They're looking for
Someone who hears from investors when it stalls.
AR
GS
Arjun Rao and 1 other on it
Team up
Shared
Same KYC details typed into three screens
Operations, Hyderabad
Same office as you, Hyderabad
The problem, in their words
We key one investor's KYC into three systems, and they drift apart.
They're looking for
Anyone who has seen the three screens disagree.
NK
Neha Kulkarni on it
Team up
Idea 1 of 5
Your crews
Ideas you team up on show here.
None passed
All your crews in My ideas
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
| a | Home | href=Home.dc.html |
| button | Filters | type=button, expanded=false, popup=dialog |
| button | Team up on Rejection SMS codes confuse investors: send Ravi a note | type=button |
| button | Previous idea | type=button, disabled=true |
| button | Next idea | type=button, disabled=false |
| a | All your crews in My ideas | href=MyIdeas.dc.html |

## State: `view=Filters open`

Screenshot: `reference/shots/Crew__view-filters-open.jpg`

Dialogs open: Filter ideas

Announced (role=alert or status): status: Idea 1 of 2

Text added:

```
1
2 ideas match
Filter ideas
Location
Hyderabad
Mumbai
1
Chennai
1
Pune
1
Category
Investor service
1
Operations
1
Idea status
1
1
0
Team size
Just the lead
1
2 to 3 people
0
4 or more
1
Looking for
Branch staff
1
Investor service
0
Operations
1
Clear all
Show 2 ideas
Hyderabad
Clear all
Idea 1 of 2
```

Text removed:

```
5 ideas close to yours
No script for calls about rejections
Operations, Mumbai
The calls your idea is about
Every agent explains a rejection differently, so investors call back.
Real examples of what investors ask on these calls.
SP
MD
Sanjay Pillai and 1 other on it
Branch queue times are not tracked anywhere
Investor service, Chennai
Your area, Investor service
We can't tell how long investors wait, so we can't staff for it.
A branch that will count queue times for two weeks.
DS
KR
AN
Divya Shah and 2 others on it
Nominee updates bounce between two teams
Operations, Pune
Investors call your branch about this too
A nominee change goes back and forth between two teams for days.
Someone who hears from investors when it stalls.
AR
GS
Arjun Rao and 1 other on it
Idea 1 of 5
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Filters 1 | type=button, expanded=true, popup=dialog |
| button | Close filters | type=button |
| button | Hyderabad 2 | type=button, pressed=true |
| button | Mumbai 1 | type=button, pressed=false |
| button | Chennai 1 | type=button, pressed=false |
| button | Pune 1 | type=button, pressed=false |
| button | Investor service 1 | type=button, pressed=false |
| button | Operations 1 | type=button, pressed=false |
| button | Shared 1 | type=button, pressed=false |
| button | With the review desk 1 | type=button, pressed=false |
| button | Picked 0 | type=button, pressed=false |
| button | Just the lead 1 | type=button, pressed=false |
| button | 2 to 3 people 0 | type=button, pressed=false |
| button | 4 or more 1 | type=button, pressed=false |
| button | Branch staff 1 | type=button, pressed=false |
| button | Investor service 0 | type=button, pressed=false |
| button | Operations 1 | type=button, pressed=false |
| button | Clear all | type=button |
| button | Show 2 ideas | type=button |
| button | Remove filter: Hyderabad | type=button |
| button | Clear all | type=button |

## State: `view=Request`

Screenshot: `reference/shots/Crew__view-request.jpg`

Dialogs open: Team up with Ravi

Text added:

```
Team up with Ravi
Ravi leads “Rejection SMS codes confuse investors” and decides who joins. Tell Ravi what you bring.
Your note to Ravi
We drafted this from your idea. Change anything you like.
Bring your ideas along Optional
Bring your ideas along:
None picked
Ravi sees your name, your note.
Send to Ravi
```

Text removed:

```
With the review desk
Rejection SMS codes confuse investors
Investor service, Hyderabad
Same R07 SMS as your idea from Saturday
The problem, in their words
Investors get a code, not a reason, and then they call us.
They're looking for
Someone who takes these calls at a branch every day.
AS
PK
Ravi Nair and 3 others on it
Team up
Picked
No script for calls about rejections
Operations, Mumbai
The calls your idea is about
The problem, in their words
Every agent explains a rejection differently, so investors call back.
They're looking for
Real examples of what investors ask on these calls.
SP
MD
Sanjay Pillai and 1 other on it
Team up
With the review desk
Branch queue times are not tracked anywhere
Investor service, Chennai
Your area, Investor service
The problem, in their words
We can't tell how long investors wait, so we can't staff for it.
They're looking for
A branch that will count queue times for two weeks.
DS
KR
AN
Divya Shah and 2 others on it
Team up
With the review desk
Nominee updates bounce between two teams
Operations, Pune
Investors call your branch about this too
The problem, in their words
A nominee change goes back and forth between two teams for days.
They're looking for
Someone who hears from investors when it stalls.
AR
GS
Arjun Rao and 1 other on it
Team up
Shared
Same KYC details typed into three screens
Operations, Hyderabad
Same office as you, Hyderabad
The problem, in their words
We key one investor's KYC into three systems, and they drift apart.
They're looking for
Anyone who has seen the three screens disagree.
NK
Neha Kulkarni on it
Team up
… and 1 more lines
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Close without sending | type=button |
| textarea | (no label) |  |
| button | Bring your ideas along: None picked | type=button, expanded=false |
| button | Send to Ravi | type=button, disabled=false |

## State: `view=Request sent`

Screenshot: `reference/shots/Crew__view-request-sent.jpg`

Announced (role=alert or status): status: Sent to Ravi Ravi reads your note, then approves or declines. You’ll hear in your Inbox. Your note I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07. I can b

Text added:

```
Sent to Ravi
Ravi reads your note, then approves or declines. You’ll hear in your Inbox.
Your note
I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07. I can bring the call log and real examples of what investors ask.
Withdraw request
Keep looking
Ravi Nair, Investor service
Waiting for Ravi
```

Text removed:

```
With the review desk
Investor service, Hyderabad
Same R07 SMS as your idea from Saturday
The problem, in their words
Investors get a code, not a reason, and then they call us.
They're looking for
Someone who takes these calls at a branch every day.
RN
AS
PK
Ravi Nair and 3 others on it
Team up
Picked
No script for calls about rejections
Operations, Mumbai
The calls your idea is about
The problem, in their words
Every agent explains a rejection differently, so investors call back.
They're looking for
Real examples of what investors ask on these calls.
SP
MD
Sanjay Pillai and 1 other on it
Team up
With the review desk
Branch queue times are not tracked anywhere
Investor service, Chennai
Your area, Investor service
The problem, in their words
We can't tell how long investors wait, so we can't staff for it.
They're looking for
A branch that will count queue times for two weeks.
DS
KR
AN
Divya Shah and 2 others on it
Team up
With the review desk
Nominee updates bounce between two teams
Operations, Pune
Investors call your branch about this too
The problem, in their words
A nominee change goes back and forth between two teams for days.
They're looking for
Someone who hears from investors when it stalls.
AR
GS
Arjun Rao and 1 other on it
Team up
Shared
Same KYC details typed into three screens
Operations, Hyderabad
Same office as you, Hyderabad
The problem, in their words
We key one investor's KYC into three systems, and they drift apart.
They're looking for
Anyone who has seen the three screens disagree.
NK
Neha Kulkarni on it
Team up
… and 2 more lines
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Withdraw request | type=button |
| button | Keep looking | type=button |
| a | Rejection SMS codes confuse investors, waiting for Ravi. Open the idea. | href=Idea.dc.html |

## State: `view=Approved`

Screenshot: `reference/shots/Crew__view-approved.jpg`

Announced (role=alert or status): status: You're on this crew Say hello to Ravi // status: Idea 1 of 5

Text added:

```
With the review desk 
You're on it
You're on this crew
Say hello to Ravi
Ravi Nair, Investor service
On the crew
```

Text removed:

```
Ideas you team up on show here.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Say hello to Ravi | href=Messages.dc.html |
| a | Rejection SMS codes confuse investors, you’re on the crew. Open the idea. | href=Idea.dc.html |

## State: `view=Nothing yet`

Screenshot: `reference/shots/Crew__view-nothing-yet.jpg`

Announced (role=alert or status): status: + No crews to join yet We look for ideas close to the problems you've shared. Share one and we'll show you people working on the same thing, or browse the Wall for ideas you can help with. Browse the 

Text added:

```
+
No crews to join yet
We look for ideas close to the problems you've shared. Share one and we'll show you people working on the same thing, or browse the Wall for ideas you can help with.
Browse the Wall
```

Text removed:

```
5 ideas close to yours
With the review desk
Rejection SMS codes confuse investors
Investor service, Hyderabad
Same R07 SMS as your idea from Saturday
The problem, in their words
Investors get a code, not a reason, and then they call us.
They're looking for
Someone who takes these calls at a branch every day.
RN
AS
PK
Ravi Nair and 3 others on it
Team up
Picked
No script for calls about rejections
Operations, Mumbai
The calls your idea is about
The problem, in their words
Every agent explains a rejection differently, so investors call back.
They're looking for
Real examples of what investors ask on these calls.
SP
MD
Sanjay Pillai and 1 other on it
Team up
With the review desk
Branch queue times are not tracked anywhere
Investor service, Chennai
Your area, Investor service
The problem, in their words
We can't tell how long investors wait, so we can't staff for it.
They're looking for
A branch that will count queue times for two weeks.
DS
KR
AN
Divya Shah and 2 others on it
Team up
With the review desk
Nominee updates bounce between two teams
Operations, Pune
Investors call your branch about this too
The problem, in their words
A nominee change goes back and forth between two teams for days.
They're looking for
Someone who hears from investors when it stalls.
AR
GS
Arjun Rao and 1 other on it
Team up
Shared
Same KYC details typed into three screens
Operations, Hyderabad
Same office as you, Hyderabad
The problem, in their words
We key one investor's KYC into three systems, and they drift apart.
They're looking for
Anyone who has seen the three screens disagree.
NK
… and 4 more lines
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Browse the Wall | href=Wall.dc.html |
| a | Share a problem | href=Compose.dc.html |

## State: `view=Everyone seen`

Screenshot: `reference/shots/Crew__view-everyone-seen.jpg`

Announced (role=alert or status): status: That's everyone for now You asked to team up on 1 idea. New ideas close to yours show up here. See them again

Text added:

```
That's everyone for now
You asked to team up on 1 idea. New ideas close to yours show up here.
See them again
Ravi Nair, Investor service
Waiting for Ravi
5 passed
Undo last pass
```

Text removed:

```
With the review desk
Investor service, Hyderabad
Same R07 SMS as your idea from Saturday
The problem, in their words
Investors get a code, not a reason, and then they call us.
They're looking for
Someone who takes these calls at a branch every day.
RN
AS
PK
Ravi Nair and 3 others on it
Team up
Picked
No script for calls about rejections
Operations, Mumbai
The calls your idea is about
The problem, in their words
Every agent explains a rejection differently, so investors call back.
They're looking for
Real examples of what investors ask on these calls.
SP
MD
Sanjay Pillai and 1 other on it
Team up
With the review desk
Branch queue times are not tracked anywhere
Investor service, Chennai
Your area, Investor service
The problem, in their words
We can't tell how long investors wait, so we can't staff for it.
They're looking for
A branch that will count queue times for two weeks.
DS
KR
AN
Divya Shah and 2 others on it
Team up
With the review desk
Nominee updates bounce between two teams
Operations, Pune
Investors call your branch about this too
The problem, in their words
A nominee change goes back and forth between two teams for days.
They're looking for
Someone who hears from investors when it stalls.
AR
GS
Arjun Rao and 1 other on it
Team up
Shared
Same KYC details typed into three screens
Operations, Hyderabad
Same office as you, Hyderabad
The problem, in their words
We key one investor's KYC into three systems, and they drift apart.
They're looking for
Anyone who has seen the three screens disagree.
NK
Neha Kulkarni on it
Team up
… and 3 more lines
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | See them again | type=button |
| a | Rejection SMS codes confuse investors, waiting for Ravi. Open the idea. | href=Idea.dc.html |
| button | Undo last pass | type=button |
