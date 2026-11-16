# PhoneInbox: copy and controls per state

Generated from the prototype board `reference/prototype/PhoneInbox.dc.html`, rendered at 390px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/PhoneInbox.jpg`

Headings: H1: Inbox

### Text, top to bottom

```
1% Club
KM
Inbox
Mark all read
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
Meera from the review desk asked you 3 questions
Investors call to ask why a redemption was rejected
3 days left
11:20 am
RN
Ravi Nair approved your team-up request
Rejection SMS codes confuse investors
10:05 am
This week
AR
Arjun Rao asked you to check new messages
Plain words for transaction rejections
By Thu
Sun, 15 Nov
1%
1% Club kept your draft from your phone
Distributors can’t see why an SIP registration is stuck
Fri, 8:42 pm
RM
Rohan Mehta from the Ones Committee reversed a decision on your idea
Cheque scans need re-uploading at month end
Fri, 6:15 pm
SP
Sanjay Pillai mentioned you
No script for calls about rejections
Thu, 12 Nov
Earlier
MI
Meera from the review desk picked your idea
Plain words for transaction rejections
2 Nov
1%
1% Club moved your idea to Being built
Track couriered redemption forms
28 Oct
MI
Meera from the review desk didn’t pick your idea, with a reason
Cheque scans need re-uploading at month end
21 Oct
Swipe left on a row to archive it. Teams and email get the same updates.
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
| button | Mark all read | type=button |
| button | All 9 | type=button, pressed=true |
| button | Needs you 3 | type=button, pressed=false |
| button | Unread 2 | type=button, pressed=false |
| button | Archived 0 | type=button, pressed=false |
| a | MI Meera from the review desk asked you 3 questions Investors call to ask why a redemption was rejected 3 days left 11:20 am | href=PhoneAnswer.dc.html |
| a | RN Ravi Nair approved your team-up request Rejection SMS codes confuse investors 10:05 am | href=PhoneIdea.dc.html |
| a | AR Arjun Rao asked you to check new messages Plain words for transaction rejections By Thu Sun, 15 Nov | href=PhoneMessages.dc.html |
| a | 1% 1% Club kept your draft from your phone Distributors can’t see why an SIP registration is stuck Fri, 8:42 pm | href=PhoneComposeResume.dc.html |
| a | RM Rohan Mehta from the Ones Committee reversed a decision on your idea Cheque scans need re-uploading at month end Fri, 6:15 pm | href=PhoneMyIdeas.dc.html |
| a | SP Sanjay Pillai mentioned you No script for calls about rejections Thu, 12 Nov | href=PhoneMessages.dc.html |
| a | MI Meera from the review desk picked your idea Plain words for transaction rejections 2 Nov | href=PhoneStatus.dc.html |
| a | 1% 1% Club moved your idea to Being built Track couriered redemption forms 28 Oct | href=PhoneStatus.dc.html |
| a | MI Meera from the review desk didn’t pick your idea, with a reason Cheque scans need re-uploading at month end 21 Oct | href=PhoneStatus.dc.html |
| a | Home | href=PhoneHome.dc.html |
| a | My ideas | href=PhoneMyIdeas.dc.html |
| a | Share a problem | href=PhoneCompose.dc.html |
| a | Wall | href=PhoneWall.dc.html |
| a | Inbox, 2 new | href=PhoneInbox.dc.html |

## State: `filter=Needs you`

Screenshot: `reference/shots/PhoneInbox__filter-needs-you.jpg`

Text removed:

```
RN
Ravi Nair approved your team-up request
Rejection SMS codes confuse investors
10:05 am
RM
Rohan Mehta from the Ones Committee reversed a decision on your idea
Cheque scans need re-uploading at month end
Fri, 6:15 pm
SP
Sanjay Pillai mentioned you
No script for calls about rejections
Thu, 12 Nov
Earlier
Meera from the review desk picked your idea
2 Nov
1% Club moved your idea to Being built
Track couriered redemption forms
28 Oct
Meera from the review desk didn’t pick your idea, with a reason
Cheque scans need re-uploading at month end
21 Oct
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All 9 | type=button, pressed=false |
| button | Needs you 3 | type=button, pressed=true |

## State: `filter=Unread`

Screenshot: `reference/shots/PhoneInbox__filter-unread.jpg`

Text removed:

```
This week
AR
Arjun Rao asked you to check new messages
Plain words for transaction rejections
By Thu
Sun, 15 Nov
1%
1% Club kept your draft from your phone
Distributors can’t see why an SIP registration is stuck
Fri, 8:42 pm
RM
Rohan Mehta from the Ones Committee reversed a decision on your idea
Cheque scans need re-uploading at month end
Fri, 6:15 pm
SP
Sanjay Pillai mentioned you
No script for calls about rejections
Thu, 12 Nov
Earlier
Meera from the review desk picked your idea
Plain words for transaction rejections
2 Nov
1%
1% Club moved your idea to Being built
Track couriered redemption forms
28 Oct
Meera from the review desk didn’t pick your idea, with a reason
Cheque scans need re-uploading at month end
21 Oct
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All 9 | type=button, pressed=false |
| button | Unread 2 | type=button, pressed=true |

## State: `filter=Archived`

Screenshot: `reference/shots/PhoneInbox__filter-archived.jpg`

Text added:

```
Nothing archived.
Swipe left on a row to archive it. It stays searchable.
```

Text removed:

```
Today
MI
Meera from the review desk asked you 3 questions
Investors call to ask why a redemption was rejected
3 days left
11:20 am
RN
Ravi Nair approved your team-up request
Rejection SMS codes confuse investors
10:05 am
This week
AR
Arjun Rao asked you to check new messages
Plain words for transaction rejections
By Thu
Sun, 15 Nov
1%
1% Club kept your draft from your phone
Distributors can’t see why an SIP registration is stuck
Fri, 8:42 pm
RM
Rohan Mehta from the Ones Committee reversed a decision on your idea
Cheque scans need re-uploading at month end
Fri, 6:15 pm
SP
Sanjay Pillai mentioned you
No script for calls about rejections
Thu, 12 Nov
Earlier
MI
Meera from the review desk picked your idea
Plain words for transaction rejections
2 Nov
1%
1% Club moved your idea to Being built
Track couriered redemption forms
28 Oct
MI
Meera from the review desk didn’t pick your idea, with a reason
Cheque scans need re-uploading at month end
21 Oct
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All 9 | type=button, pressed=false |
| button | Archived 0 | type=button, pressed=true |
