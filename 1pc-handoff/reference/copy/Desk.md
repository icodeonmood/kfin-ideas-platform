# Desk: copy and controls per state

Generated from the prototype board `reference/prototype/Desk.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Desk.jpg`

Headings: H1: Review desk

### Text, top to bottom

```
1% Club
Share a problem
P
Home
Find your crew
Wall
Inbox
1
Review desk
Waiting on sharers
View all
Investors call to ask why a redemption was rejected
Nominee updates bounce between two teams
Branch queue times are not tracked anywhere
MI
Meera Iyer
Tier 3, Flame
Review desk
3 waiting on colleagues. One is overdue and one has under a day left. 2 answered and back with you.
Search the desk
Filter
To review
8
Waiting on the sharer
3
Answered, back to you
2
Decided this week
5
Sort by
Time left
Decide by
Area
Idea
Questions
Time left
Decide by
Action
Investors call to ask why a redemption was rejected
Kavya Menon, Investor service, Hyderabad
0 of 3 answered, seen 12:05 pm
3 days to answer
Friday 20 November
Open
Nominee updates bounce between two teams
Arjun Rao, Operations, Pune
1 of 2 answered
07:38 to answer
Thursday 19 November
Open
Branch queue times are not tracked anywhere
Divya Shah, Investor service, Chennai
Not seen yet
Overdue by 5 hours
Wednesday 18 November
Remind Divya
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
| a | Inbox, 1 unread | href=Inbox.dc.html |
| a | Review desk | href=Desk.dc.html |
| a | Search the desk | href=Desk.dc.html#dq |
| a | View all | href=Desk.dc.html |
| a | Investors call to ask why a redemption was rejected | href=DeskIdea.dc.html |
| a | Nominee updates bounce between two teams | href=DeskIdea.dc.html |
| a | Branch queue times are not tracked anywhere | href=DeskIdea.dc.html |
| a | Your profile and settings, Meera Iyer, Tier 3, Flame | href=Profile.dc.html |
| input | Search ideas, sharers or IDEA numbers, or ask: which ones are overdue? | type=search, autocomplete=off |
| button | Filter | type=button |
| button[tab] | To review 8 | type=button, selected=false |
| button[tab] | Waiting on the sharer 3 | type=button, selected=true |
| button[tab] | Answered, back to you 2 | type=button, selected=false |
| button[tab] | Decided this week 5 | type=button, selected=false |
| button | Time left | type=button, pressed=true |
| button | Decide by | type=button, pressed=false |
| button | Area | type=button, pressed=false |
| a | Investors call to ask why a redemption was rejected | href=DeskIdea.dc.html |
| a | Open: Investors call to ask why a redemption was rejected | href=DeskIdea.dc.html |
| a | Nominee updates bounce between two teams | href=DeskIdea.dc.html |
| a | Open: Nominee updates bounce between two teams | href=DeskIdea.dc.html |
| a | Branch queue times are not tracked anywhere | href=DeskIdea.dc.html |
| a | Remind Divya: Branch queue times are not tracked anywhere | href=DeskIdea.dc.html |

## State: `tab=To review`

Screenshot: `reference/shots/Desk__tab-to-review.jpg`

Announced (role=alert or status): status: 3 waiting on colleagues. One is overdue and one has under a day left. 2 answered and back with you.

Text added:

```
Distributor payouts show different totals in two reports
Rahul Verma, Distributor services, Mumbai
No questions asked
6 days to decide
Same KYC details typed into three screens
Neha Kulkarni, Operations, Hyderabad
No questions asked
5 days to decide
SIP mandate failures aren’t explained to distributors
Imran Sheikh, Distributor services, Kolkata
No questions asked
4 days to decide
Month-end batch delays redemption payouts
Lakshmi Iyer, Operations, Chennai
No questions asked
2 days to decide
Monday 16 November
```

Text removed:

```
Kavya Menon, Investor service, Hyderabad
0 of 3 answered, seen 12:05 pm
3 days to answer
Arjun Rao, Operations, Pune
1 of 2 answered
07:38 to answer
Divya Shah, Investor service, Chennai
Not seen yet
Overdue by 5 hours
Remind Divya
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button[tab] | To review 8 | type=button, selected=true |
| button[tab] | Waiting on the sharer 3 | type=button, selected=false |
| a | Distributor payouts show different totals in two reports | href=DeskIdea.dc.html |
| a | Open: Distributor payouts show different totals in two reports | href=DeskIdea.dc.html |
| a | Same KYC details typed into three screens | href=DeskIdea.dc.html |
| a | Open: Same KYC details typed into three screens | href=DeskIdea.dc.html |
| a | SIP mandate failures aren’t explained to distributors | href=DeskIdea.dc.html |
| a | Open: SIP mandate failures aren’t explained to distributors | href=DeskIdea.dc.html |
| a | Month-end batch delays redemption payouts | href=DeskIdea.dc.html |
| a | Open: Month-end batch delays redemption payouts | href=DeskIdea.dc.html |

## State: `tab=Answered, back to you`

Screenshot: `reference/shots/Desk__tab-answered-back-to-you.jpg`

Announced (role=alert or status): status: 3 waiting on colleagues. One is overdue and one has under a day left. 2 answered and back with you.

Text added:

```
Courier tracking for physical redemption forms
Farhan Nair, Investor service, Bengaluru
Both answered, 1 hour ago
4 days to decide
Read answers
Bank mandate rejections need plain reasons
Pooja Menon, Operations, Hyderabad
Answered yesterday, 6:10 pm
2 days to decide
Monday 16 November
Read answers
```

Text removed:

```
Kavya Menon, Investor service, Hyderabad
0 of 3 answered, seen 12:05 pm
3 days to answer
Friday 20 November
Open
Arjun Rao, Operations, Pune
1 of 2 answered
07:38 to answer
Thursday 19 November
Open
Divya Shah, Investor service, Chennai
Not seen yet
Overdue by 5 hours
Remind Divya
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button[tab] | Waiting on the sharer 3 | type=button, selected=false |
| button[tab] | Answered, back to you 2 | type=button, selected=true |
| a | Courier tracking for physical redemption forms | href=DeskIdea.dc.html |
| a | Read answers: Courier tracking for physical redemption forms | href=DeskIdea.dc.html |
| a | Bank mandate rejections need plain reasons | href=DeskIdea.dc.html |
| a | Read answers: Bank mandate rejections need plain reasons | href=DeskIdea.dc.html |

## State: `tab=Decided this week`

Screenshot: `reference/shots/Desk__tab-decided-this-week.jpg`

Announced (role=alert or status): status: 3 waiting on colleagues. One is overdue and one has under a day left. 2 answered and back with you.

Text added:

```
Decision
Ones Committee
Plain words for transaction rejections
1 question, answered
Picked, 2 November
Ones Committee can review it until Wednesday 2 December
Cheque scans need re-uploading at month end
No questions asked
Reversed: picked
The Ones Committee picked it on 13 November, with a note to Kavya
No script for calls about rejections
Sanjay Pillai, Operations, Mumbai
Both answered
Picked, 12 November
Ones Committee can review it until Saturday 12 December
```

Text removed:

```
0 of 3 answered, seen 12:05 pm
3 days to answer
Friday 20 November
Arjun Rao, Operations, Pune
1 of 2 answered
07:38 to answer
Thursday 19 November
Divya Shah, Investor service, Chennai
Not seen yet
Overdue by 5 hours
Wednesday 18 November
Remind Divya
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button[tab] | Waiting on the sharer 3 | type=button, selected=false |
| button[tab] | Decided this week 5 | type=button, selected=true |
| a | Plain words for transaction rejections | href=DeskIdea.dc.html |
| a | Open: Plain words for transaction rejections | href=DeskIdea.dc.html |
| a | Cheque scans need re-uploading at month end | href=DeskIdea.dc.html |
| a | Open: Cheque scans need re-uploading at month end | href=DeskIdea.dc.html |
| a | No script for calls about rejections | href=DeskIdea.dc.html |
| a | Open: No script for calls about rejections | href=DeskIdea.dc.html |
