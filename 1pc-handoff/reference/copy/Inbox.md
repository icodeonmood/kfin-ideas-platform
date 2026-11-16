# Inbox: copy and controls per state

Generated from the prototype board `reference/prototype/Inbox.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Inbox.jpg`

Headings: H1: Inbox; H2: Investors call to ask why a redemption was rejected

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
Inbox
2 unread
All
9
Needs you
3
Unread
2
Archived
0
Today
MI
Meera from the review desk
11:20 am
Investors call to ask why a redemption was rejected
asked you 3 questions
3 days left
RN
Ravi Nair
10:05 am
Rejection SMS codes confuse investors
approved your team-up request
This week
AR
Arjun Rao
Sun, 15 Nov
Plain words for transaction rejections
asked you to check new messages
By Thu, 19 Nov
1%
1% Club
Fri, 8:42 pm
Distributors can't see why an SIP registration is stuck
kept your draft from your phone
RM
Rohan Mehta from the Ones Committee
Fri, 6:15 pm
Cheque scans need re-uploading at month end
reversed a decision on your idea
SP
Sanjay Pillai
Thu, 12 Nov
No script for calls about rejections
mentioned you
Earlier
MI
Meera from the review desk
2 Nov
Plain words for transaction rejections
picked your idea
1%
1% Club
28 Oct
Track couriered redemption forms
moved your idea to Being built
MI
Meera from the review desk
21 Oct
Cheque scans need re-uploading at month end
didn't pick your idea, with a reason
1 of 9
Questions from the review desk
Investors call to ask why a redemption was rejected
MI
Meera from the review desk asked you 3 questions
11:20 am
3 days left
Question 1
Is it mostly R07, or all rejection codes?
Question 2
Is the 40 calls a day at one branch, or across Hyderabad?
Question 3
Can you add a screenshot of the SMS, with the folio hidden?
Answer by Thursday 19 November, 6 pm.
Open the conversation
Answer the questions
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
| button | Mark all read | type=button |
| input | Search your inbox | type=search |
| button[tab] | All 9 | type=button, selected=true |
| button[tab] | Needs you 3 | type=button, selected=false |
| button[tab] | Unread 2 | type=button, selected=false |
| button[tab] | Archived 0 | type=button, selected=false |
| button | Meera from the review desk asked you 3 questions, Investors call to ask why a redemption was rejected, 11:20 am, unread | type=button, pressed=true |
| button | Ravi Nair approved your team-up request, Rejection SMS codes confuse investors, 10:05 am, unread | type=button, pressed=false |
| button | Arjun Rao asked you to check new messages, Plain words for transaction rejections, Sun, 15 Nov | type=button, pressed=false |
| button | 1% Club kept your draft from your phone, Distributors can't see why an SIP registration is stuck, Fri, 8:42 pm | type=button, pressed=false |
| button | Rohan Mehta from the Ones Committee reversed a decision on your idea, Cheque scans need re-uploading at month end, Fri, 6:15 pm | type=button, pressed=false |
| button | Sanjay Pillai mentioned you, No script for calls about rejections, Thu, 12 Nov | type=button, pressed=false |
| button | Meera from the review desk picked your idea, Plain words for transaction rejections, 2 Nov | type=button, pressed=false |
| button | 1% Club moved your idea to Being built, Track couriered redemption forms, 28 Oct | type=button, pressed=false |
| button | Meera from the review desk didn't pick your idea, with a reason, Cheque scans need re-uploading at month end, 21 Oct | type=button, pressed=false |
| button | Archive | type=button |
| button | Mark unread | type=button |
| button | Previous | type=button, disabled=true |
| button | Next | type=button, disabled=false |
| a | Open the conversation | href=Messages.dc.html |
| a | Answer the questions | href=Answer.dc.html |

## State: `filter=Needs you`

Screenshot: `reference/shots/Inbox__filter-needs-you.jpg`

Text added:

```
1 of 3
```

Text removed:

```
RN
Ravi Nair
10:05 am
Rejection SMS codes confuse investors
approved your team-up request
RM
Rohan Mehta from the Ones Committee
Fri, 6:15 pm
Cheque scans need re-uploading at month end
reversed a decision on your idea
SP
Sanjay Pillai
Thu, 12 Nov
No script for calls about rejections
mentioned you
Earlier
2 Nov
picked your idea
28 Oct
moved your idea to Being built
21 Oct
Cheque scans need re-uploading at month end
didn't pick your idea, with a reason
1 of 9
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button[tab] | All 9 | type=button, selected=false |
| button[tab] | Needs you 3 | type=button, selected=true |

## State: `filter=Unread`

Screenshot: `reference/shots/Inbox__filter-unread.jpg`

Text added:

```
1 of 2
```

Text removed:

```
This week
AR
Arjun Rao
Sun, 15 Nov
asked you to check new messages
By Thu, 19 Nov
1%
Fri, 8:42 pm
Distributors can't see why an SIP registration is stuck
kept your draft from your phone
RM
Rohan Mehta from the Ones Committee
Fri, 6:15 pm
Cheque scans need re-uploading at month end
reversed a decision on your idea
SP
Sanjay Pillai
Thu, 12 Nov
No script for calls about rejections
mentioned you
Earlier
2 Nov
picked your idea
1%
28 Oct
moved your idea to Being built
21 Oct
Cheque scans need re-uploading at month end
didn't pick your idea, with a reason
1 of 9
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button[tab] | All 9 | type=button, selected=false |
| button[tab] | Unread 2 | type=button, selected=true |

## State: `filter=Archived`

Screenshot: `reference/shots/Inbox__filter-archived.jpg`

Text added:

```
Nothing here.
Pick something on the left to read it here.
```

Text removed:

```
Today
MI
Meera from the review desk
11:20 am
asked you 3 questions
3 days left
RN
Ravi Nair
10:05 am
Rejection SMS codes confuse investors
approved your team-up request
This week
AR
Arjun Rao
Sun, 15 Nov
asked you to check new messages
By Thu, 19 Nov
1%
Fri, 8:42 pm
Distributors can't see why an SIP registration is stuck
kept your draft from your phone
RM
Rohan Mehta from the Ones Committee
Fri, 6:15 pm
Cheque scans need re-uploading at month end
reversed a decision on your idea
SP
Sanjay Pillai
Thu, 12 Nov
No script for calls about rejections
mentioned you
Earlier
MI
Meera from the review desk
2 Nov
picked your idea
1%
28 Oct
moved your idea to Being built
MI
Meera from the review desk
21 Oct
Cheque scans need re-uploading at month end
didn't pick your idea, with a reason
1 of 9
Questions from the review desk
MI
Meera from the review desk asked you 3 questions
11:20 am
3 days left
Question 1
Is it mostly R07, or all rejection codes?
Question 2
Is the 40 calls a day at one branch, or across Hyderabad?
Question 3
Can you add a screenshot of the SMS, with the folio hidden?
Answer by Thursday 19 November, 6 pm.
Open the conversation
Answer the questions
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button[tab] | All 9 | type=button, selected=false |
| button[tab] | Archived 0 | type=button, selected=true |
