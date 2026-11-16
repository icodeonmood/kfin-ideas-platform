# Committee: copy and controls per state

Generated from the prototype board `reference/prototype/Committee.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Committee.jpg`

Headings: H1: Ones Committee

### Text, top to bottom

```
1% Club
Share a problem
P
Home
Find your crew
Wall
Inbox
Ones Committee
Closing soonest
View all
Distributor statements arrive after the SIP date
Investors call to ask why a redemption was rejected
Branch queue times are not tracked anywhere
RM
Rohan Mehta
Ones Committee
Ones Committee
3 decisions open to review. You reversed 1 this month.
The review desk decides on the committee’s behalf, and the sharer hears at once. For 30 days after, you can reverse a decision, with a note the sharer reads. Extend a window 30 days at a time, up to 3 months. Then it expires and the decision stands.
In the window
3
Reversed
1
Expired
2
Sort by
Closing soonest
Decided
Area
Idea
The review desk’s decision
Your window
Action
Distributor statements arrive after the SIP date
IDEA-2026-001433, Swati Kulkarni, Distributor services, Mumbai
Not picked
by Meera from the review desk, Monday 12 October
Not picked. Statements follow the registrar’s batch calendar, which we can’t move this year. We’ve passed your examples to the distributor services team.
Extended
17 days left
Until Friday 11 December. Extended once
Review
Investors call to ask why a redemption was rejected
IDEA-2026-001481, Kavya Menon, Investor service, Hyderabad
Picked
by Meera from the review desk, Monday 16 November
Picked. A clear problem, a real number and a simple fix. We’ve joined it with IDEA-2026-001412, which found the same calls in Hyderabad, so one team builds one fix.
22 days left
Until Wednesday 16 December
Review
Branch queue times are not tracked anywhere
IDEA-2026-001470, Divya Shah, Investor service, Chennai
Not now
by Meera from the review desk, Wednesday 18 November
Not now. Branch footfall tracking starts with the new token machines in February. We’ll look at it again then, with your counts.
24 days left
Until Friday 18 December
Review
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
| a | Inbox | href=Inbox.dc.html |
| a | Ones Committee | href=Committee.dc.html |
| a | View all | href=Committee.dc.html |
| a | Distributor statements arrive after the SIP date | href=Committee.dc.html |
| a | Investors call to ask why a redemption was rejected | href=Committee.dc.html |
| a | Branch queue times are not tracked anywhere | href=Committee.dc.html |
| a | Your profile and settings, Rohan Mehta, Ones Committee | href=Profile.dc.html |
| button[tab] | In the window 3 | type=button, selected=true |
| button[tab] | Reversed 1 | type=button, selected=false |
| button[tab] | Expired 2 | type=button, selected=false |
| button | Closing soonest | type=button, pressed=true |
| button | Decided | type=button, pressed=false |
| button | Area | type=button, pressed=false |
| button | Review the decision on Distributor statements arrive after the SIP date | type=button |
| button | Review the decision on Investors call to ask why a redemption was rejected | type=button |
| button | Review the decision on Branch queue times are not tracked anywhere | type=button |

## State: `tab=Reversed`

Screenshot: `reference/shots/Committee__tab-reversed.jpg`

Announced (role=alert or status): status: 3 decisions open to review. You reversed 1 this month.

Text added:

```
Cheque scans need re-uploading at month end
IDEA-2026-001455, Kavya Menon, Investor service, Hyderabad
by Meera from the review desk, Wednesday 21 October
Not picked. A fix is already planned in the scanning upgrade in January. We’ve added your notes to it.
Now: Picked
by Rohan Mehta, Friday 13 November
Reversed Friday 13 November
Final. Kavya has the note.
See it
```

Text removed:

```
IDEA-2026-001433, Swati Kulkarni, Distributor services, Mumbai
by Meera from the review desk, Monday 12 October
Not picked. Statements follow the registrar’s batch calendar, which we can’t move this year. We’ve passed your examples to the distributor services team.
Extended
17 days left
Until Friday 11 December. Extended once
Review
IDEA-2026-001481, Kavya Menon, Investor service, Hyderabad
Picked
by Meera from the review desk, Monday 16 November
Picked. A clear problem, a real number and a simple fix. We’ve joined it with IDEA-2026-001412, which found the same calls in Hyderabad, so one team builds one fix.
22 days left
Until Wednesday 16 December
Review
IDEA-2026-001470, Divya Shah, Investor service, Chennai
Not now
by Meera from the review desk, Wednesday 18 November
Not now. Branch footfall tracking starts with the new token machines in February. We’ll look at it again then, with your counts.
24 days left
Until Friday 18 December
Review
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button[tab] | In the window 3 | type=button, selected=false |
| button[tab] | Reversed 1 | type=button, selected=true |
| button | See the decision on Cheque scans need re-uploading at month end | type=button |

## State: `tab=Expired`

Screenshot: `reference/shots/Committee__tab-expired.jpg`

Announced (role=alert or status): status: 3 decisions open to review. You reversed 1 this month.

Text added:

```
SMS for SIP pauses goes out a day late
IDEA-2026-001402, Harish Menon, Technology, Bengaluru
by Meera from the review desk, Monday 19 October
Not now. The SMS gateway moves to a new vendor in December, and this is fixed in that move. We’ll check it after.
Expired Wednesday 18 November
After 30 days. The decision stands.
See it
Same nominee form asked for twice
IDEA-2026-001391, Nikhil Joshi, Operations, Pune
by Meera from the review desk, Thursday 13 August
Picked. One form, one check, and the second request goes away. The operations tech team takes it in September.
Expired Wednesday 11 November
After 30 days. The decision stands.
See it
```

Text removed:

```
IDEA-2026-001433, Swati Kulkarni, Distributor services, Mumbai
Not picked
by Meera from the review desk, Monday 12 October
Not picked. Statements follow the registrar’s batch calendar, which we can’t move this year. We’ve passed your examples to the distributor services team.
17 days left
Until Friday 11 December. Extended once
Review
IDEA-2026-001481, Kavya Menon, Investor service, Hyderabad
by Meera from the review desk, Monday 16 November
Picked. A clear problem, a real number and a simple fix. We’ve joined it with IDEA-2026-001412, which found the same calls in Hyderabad, so one team builds one fix.
22 days left
Until Wednesday 16 December
Review
IDEA-2026-001470, Divya Shah, Investor service, Chennai
by Meera from the review desk, Wednesday 18 November
Not now. Branch footfall tracking starts with the new token machines in February. We’ll look at it again then, with your counts.
24 days left
Until Friday 18 December
Review
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button[tab] | In the window 3 | type=button, selected=false |
| button[tab] | Expired 2 | type=button, selected=true |
| button | See the decision on SMS for SIP pauses goes out a day late | type=button |
| button | See the decision on Same nominee form asked for twice | type=button |

## State: `view=Reviewing a decision`

Screenshot: `reference/shots/Committee__view-reviewing-a-decision.jpg`

Dialogs open: Investors call to ask why a redemption was rejected

Announced (role=alert or status): status: 3 decisions open to review. You reversed 1 this month.

Text added:

```
The review desk’s reason, as Kavya read it
Open until Wednesday 16 December. You can extend it 30 days at a time, up to Tuesday 16 February 2027. When it closes, the decision stands.
Extend to Friday 15 January 2027
Reverse the decision
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Close | type=button |
| button | Extend to Friday 15 January 2027 | type=button, disabled=false |
| button | Reverse the decision | type=button |

## State: `view=Reversing`

Screenshot: `reference/shots/Committee__view-reversing.jpg`

Dialogs open: Reverse the decision

Announced (role=alert or status): status: 3 decisions open to review. You reversed 1 this month.

Text added:

```
The decision
Reverse the decision
On “Investors call to ask why a redemption was rejected”. The review desk said picked it. Kavya reads your note at once, and Meera from the review desk sees it too.
Change it to
Right problem, wrong time. It comes back to the review desk in 3 months.
It won’t go ahead.
Your note to Kavya
Kavya reads this word for word.
This is final. The review desk’s decision stays on record, next to yours.
Back
Reverse and tell Kavya
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | The decision | type=button |
| button | Close | type=button |
| button[radio] | Not now Right problem, wrong time. It comes back to the review desk in 3 months. | type=button, checked=true |
| button[radio] | Not picked It won’t go ahead. | type=button, checked=false |
| textarea | Why the committee is changing it, in words Kavya will understand | invalid=false |
| button | Back | type=button |
| button | Reverse and tell Kavya | type=button, disabled=false |
