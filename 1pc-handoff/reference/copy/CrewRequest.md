# CrewRequest: copy and controls per state

Generated from the prototype board `reference/prototype/CrewRequest.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/CrewRequest.jpg`

Headings: H1: Inbox; H2: Rejection SMS codes confuse investors

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
Your ideas
View all
Rejection SMS codes confuse investors
RN
Ravi Nair
Tier 2, Glow
Inbox
2 unread
All
4
Needs you
1
Unread
2
Archived
0
Today
KM
Kavya Menon
Just now
Rejection SMS codes confuse investors
asks to team up and merge her idea into yours
1%
1% Club
9:10 am
Rejection SMS codes confuse investors
sent your idea to the review desk
This week
AS
Asha Sen
Thu, 12 Nov
Rejection SMS codes confuse investors
joined your crew
Earlier
PK
Pradeep Kumar
10 Nov
Rejection SMS codes confuse investors
commented on your idea
1 of 4
Merge request
Rejection SMS codes confuse investors
KM
Kavya Menon asks to team up and merge her idea into yours
Just now
Her note
I take these calls at our Hyderabad branch every day, about 40 a day, and most are about R07. I can bring the call log and real examples of what investors ask.
The idea she asks you to merge into yours
With the review desk
Investors call to ask why a redemption was rejected
Kavya Menon, Investor service, Hyderabad. Shared Saturday.
About 40 investors a day call her branch to ask why a redemption was rejected. The SMS only says R07.
Open her idea
Merge it, and her idea joins yours: she is on your crew and credited on it. Team up only puts her on your crew and keeps her idea separate. Decline, and she sends hers on its own, with your reason if you give one.
Decline
Team up only
Merge it
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
| a | View all | href=MyIdeas.dc.html |
| a | Rejection SMS codes confuse investors | href=Idea.dc.html |
| a | Your profile and settings, Ravi Nair, Tier 2, Glow | href=Profile.dc.html |
| button | Mark all read | type=button |
| input | Search your inbox | type=search |
| button[tab] | All 4 | type=button, selected=true |
| button[tab] | Needs you 1 | type=button, selected=false |
| button[tab] | Unread 2 | type=button, selected=false |
| button[tab] | Archived 0 | type=button, selected=false |
| button | Kavya Menon asks to team up and merge her idea into yours, Rejection SMS codes confuse investors, Just now, unread | type=button, pressed=true |
| button | 1% Club sent your idea to the review desk, Rejection SMS codes confuse investors, 9:10 am, unread | type=button, pressed=false |
| button | Asha Sen joined your crew, Rejection SMS codes confuse investors, Thu, 12 Nov | type=button, pressed=false |
| button | Pradeep Kumar commented on your idea, Rejection SMS codes confuse investors, 10 Nov | type=button, pressed=false |
| button | Archive | type=button |
| button | Mark unread | type=button |
| button | Previous | type=button, disabled=true |
| button | Next | type=button, disabled=false |
| a | With the review desk Investors call to ask why a redemption was rejected Kavya Menon, Investor service, Hyderabad. Shared Saturday. About 40 | href=Idea.dc.html |
| button | Decline | type=button |
| button | Team up only | type=button |
| button | Merge it | type=button |

## State: `state=Merged`

Screenshot: `reference/shots/CrewRequest__state-merged.jpg`

Announced (role=alert or status): status: Merged. Kavya’s idea is now part of yours, and she is on your crew, credited. We’ve told her.

Text added:

```
Merged. Kavya’s idea is now part of yours, and she is on your crew, credited. We’ve told her.
Say hello to Kavya
```

Text removed:

```
Merge it, and her idea joins yours: she is on your crew and credited on it. Team up only puts her on your crew and keeps her idea separate. Decline, and she sends hers on its own, with your reason if you give one.
Decline
Team up only
Merge it
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Say hello to Kavya | href=Messages.dc.html |

## State: `state=Teamed up only`

Screenshot: `reference/shots/CrewRequest__state-teamed-up-only.jpg`

Announced (role=alert or status): status: Teamed up. Kavya is on your crew. Her idea stays separate, and she sends it on its own. We’ve told her.

Text added:

```
Teamed up. Kavya is on your crew. Her idea stays separate, and she sends it on its own. We’ve told her.
Say hello to Kavya
```

Text removed:

```
Merge it, and her idea joins yours: she is on your crew and credited on it. Team up only puts her on your crew and keeps her idea separate. Decline, and she sends hers on its own, with your reason if you give one.
Decline
Team up only
Merge it
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Say hello to Kavya | href=Messages.dc.html |

## State: `state=Declined`

Screenshot: `reference/shots/CrewRequest__state-declined.jpg`

Announced (role=alert or status): status: Declined. Kavya sees your reason: “The crew is full for now”. She can send hers on its own.

Text added:

```
Declined. Kavya sees your reason: “The crew is full for now”. She can send hers on its own.
Next
```

Text removed:

```
Merge it, and her idea joins yours: she is on your crew and credited on it. Team up only puts her on your crew and keeps her idea separate. Decline, and she sends hers on its own, with your reason if you give one.
Decline
Team up only
Merge it
```

