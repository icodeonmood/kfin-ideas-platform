# Review: copy and controls per state

Generated from the prototype board `reference/prototype/Review.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Review.jpg`

Headings: H1: Is this how you’d put it?; H3: Investors call to ask why a redemption was rejected

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
Share a problem
Tell it
, done
2
Check it
3
Send it
Saved at 1:38 pm
Save and close
1
Your words
Title, what happens, how often
2
Sorting
Suggested, not confirmed yet
3
Similar ideas
2 close ideas found
4
Proof
Optional
5
Your fix
Optional
6
Who would help
Optional
7
Send it
One last look, then submit
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
Investors call to ask why a redemption was rejected
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
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
| a | Save and close | href=Home.dc.html |
| button | 1 Your words Title, what happens, how often | type=button |
| button | 2 Sorting Suggested, not confirmed yet | type=button |
| button | 3 Similar ideas 2 close ideas found | type=button |
| button | 4 Proof Optional | type=button |
| button | 5 Your fix Optional | type=button |
| button | 6 Who would help Optional | type=button |
| button | 7 Send it One last look, then submit | type=button |
| button | Change the title | type=button |
| button | Change what happens | type=button |
| button | Change how often | type=button |
| button | Show it | type=button |
| a | Back to your words | href=Compose.dc.html |
| button | Looks right | type=button |

## State: `simulatorS2=Check first`

Screenshot: `reference/shots/Review__simulators2-check-first.jpg`

Announced (role=alert or status): status: Saved at 1:38 pm

Text added:

```
Has someone raised this already?
Two colleagues shared something close while you were writing. Team up with them, and bring yours along if you like, or keep yours separate.
Yours, not sent yet
With the review desk
Rejection SMS codes confuse investors
IDEA-2026-001412, Investor service, Hyderabad
Close match: same SMS, same calls
RN
AS
PK
4 colleagues on it
Preview
Team up
Picked
No script for calls about rejections
IDEA-2026-001398, Operations, Mumbai
Related: the calls you describe
SP
MD
2 colleagues on it
Preview
Team up
None of these the same? Just carry on. Yours goes on its own.
Next
```

Text removed:

```
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | 1 Similar ideas 2 close ideas found | type=button |
| button | 2 Your words Title, what happens, how often | type=button |
| button | 3 Sorting Suggested, not confirmed yet | type=button |
| button | Preview Rejection SMS codes confuse investors | type=button, popup=dialog |
| button | Team up on Rejection SMS codes confuse investors | type=button |
| button | Preview No script for calls about rejections | type=button, popup=dialog |
| button | Team up on No script for calls about rejections | type=button |
| button | Next | type=button |

## State: `evidence=Added`

Screenshot: `reference/shots/Review__evidence-added.jpg`

Announced (role=alert or status): status: Saved at 1:38 pm // status: Checked // status: Checking for personal details

Text added:

```
2 files
Check it, part 4 of 6
Anything that shows it?
Optional, but it helps the review desk weigh it. Add screenshots, files or links that show the problem the way people meet it. We check each one for personal details before anyone else sees it.
Links to a report, dashboard or ticket
PNG
rejection-sms-screenshot.png 84 KB
Checked
PDF
branch-call-log-nov.pdf 140 KB
Checking for personal details
Back
Next
```

Text removed:

```
1
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | 4 Proof 2 files | type=button |
| input | Paste a link, or attach files. Add several links at once with commas. | type=text, inputmode=url, autocomplete=off |
| button | Attach files | type=button, expanded=false, popup=dialog |
| button | Add a link | type=button |
| button | Remove rejection-sms-screenshot.png | type=button |
| button | Remove branch-call-log-nov.pdf | type=button |
| button | Back | type=button |
| button | Next | type=button |

## State: `evidence=Upload failed`

Screenshot: `reference/shots/Review__evidence-upload-failed.jpg`

Announced (role=alert or status): status: Saved at 1:38 pm // alert: Didn’t upload. Your other files are fine. // status: Checked

Text added:

```
2 files
Check it, part 4 of 6
Anything that shows it?
Optional, but it helps the review desk weigh it. Add screenshots, files or links that show the problem the way people meet it. We check each one for personal details before anyone else sees it.
Links to a report, dashboard or ticket
PNG
rejection-sms-screenshot.png 84 KB
Didn’t upload. Your other files are fine.
Try again
PDF
branch-call-log-nov.pdf 140 KB
Checked
Back
Next
```

Text removed:

```
1
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | 4 Proof 2 files | type=button |
| input | Paste a link, or attach files. Add several links at once with commas. | type=text, inputmode=url, autocomplete=off |
| button | Attach files | type=button, expanded=false, popup=dialog |
| button | Add a link | type=button |
| button | Try again | type=button |
| button | Remove rejection-sms-screenshot.png | type=button |
| button | Remove branch-call-log-nov.pdf | type=button |
| button | Back | type=button |
| button | Next | type=button |

## State: `evidence=Personal data found`

Screenshot: `reference/shots/Review__evidence-personal-data-found.jpg`

Announced (role=alert or status): status: Saved at 1:38 pm // status: Checked // alert: Found a phone number on page 2. Nobody can open it until it’s hidden.

Text added:

```
2 files
Check it, part 4 of 6
Anything that shows it?
Optional, but it helps the review desk weigh it. Add screenshots, files or links that show the problem the way people meet it. We check each one for personal details before anyone else sees it.
Links to a report, dashboard or ticket
PNG
rejection-sms-screenshot.png 84 KB
Checked
PDF
branch-call-log-nov.pdf 140 KB
Found a phone number on page 2. Nobody can open it until it’s hidden.
Hide it for me
Back
Next
```

Text removed:

```
1
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | 4 Proof 2 files | type=button |
| input | Paste a link, or attach files. Add several links at once with commas. | type=text, inputmode=url, autocomplete=off |
| button | Attach files | type=button, expanded=false, popup=dialog |
| button | Add a link | type=button |
| button | Remove rejection-sms-screenshot.png | type=button |
| button | Hide it for me | type=button |
| button | Remove branch-call-log-nov.pdf | type=button |
| button | Back | type=button |
| button | Next | type=button |

## State: `evidence=Link unreachable`

Screenshot: `reference/shots/Review__evidence-link-unreachable.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm // status: Checked // alert: We couldn’t open this link. It may need a sign-in; the review desk can still try it.

Text added:

```
Saved at 1:39 pm
2 files
Check it, part 4 of 6
Anything that shows it?
Optional, but it helps the review desk weigh it. Add screenshots, files or links that show the problem the way people meet it. We check each one for personal details before anyone else sees it.
Links to a report, dashboard or ticket
PNG
rejection-sms-screenshot.png 84 KB
Checked
Rejection codes list on the intranet Link
We couldn’t open this link. It may need a sign-in; the review desk can still try it.
Keep it
Back
Next
```

Text removed:

```
Saved at 1:38 pm
1
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | 4 Proof 2 files | type=button |
| input | Paste a link, or attach files. Add several links at once with commas. | type=text, inputmode=url, autocomplete=off |
| button | Attach files | type=button, expanded=false, popup=dialog |
| button | Add a link | type=button |
| button | Remove rejection-sms-screenshot.png | type=button |
| button | Keep it | type=button |
| button | Remove Rejection codes list on the intranet | type=button |
| button | Back | type=button |
| button | Next | type=button |

## State: `fix=Sheet open`

Screenshot: `reference/shots/Review__fix-sheet-open.jpg`

Dialogs open: Your fix

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
Check it, part 5 of 6
Got an idea how to solve it?
Optional. A fix helps the review desk weigh it, but problems on their own get picked too.
Say how you’d solve it
A few short questions: how, what it would need and what it’s worth. Only the first one is needed.
You started a fix. It isn’t included yet.
Carry on with your fix
Back
Skip for now
Optional. Answer what you can; nothing here stops you sending.
2 of 5 ready for the review desk
Most useful next: a rough size. A range is fine.
How would you solve it?
One or two sentences is plenty. The only part a fix needs.
What would it need? Optional
People, systems, partners or money. Helps size the effort early.
Has anyone solved this already?
Yes
Partly
No
I don’t know
Suggested, your call: distributors on IRIS already see the reason when a transaction is rejected. Investors don’t yet.
What it’s worth, roughly
Pick any that apply. A rough monthly figure is enough, and a range is fine, written any way: 2 lakh, 2L or 2,00,000.
Time saved
Hours a month
From your words: about 70 to 150 hours a month at one branch. Use this
Cost saved
₹ a month
New revenue
Less reliance on outside tools
What is that based on?
My own research
Verified documents
A report or document
A conversation
A hunch
What could go wrong, including anything regulatory? Optional
Naming risks early builds trust. It never counts against the idea.
Cancel
Add my fix
```

Text removed:

```
Saved at 1:38 pm
1
4
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | Proof Optional | type=button |
| button | Carry on with your fix | type=button, popup=dialog |
| button | Back | type=button |
| button | Skip for now | type=button |
| button | Close, and keep what you wrote | type=button |
| textarea | (no label) | invalid=false |
| textarea | (no label) |  |
| button[radio] | Yes | type=button, checked=false |
| button[radio] | Partly | type=button, checked=true |
| button[radio] | No | type=button, checked=false |
| button[radio] | I don’t know | type=button, checked=false |
| button[checkbox] | Time saved | type=button, checked=true |
| input | For example, 70 to 150 | type=text, inputmode=decimal |
| button | Use this | type=button |
| button[checkbox] | Cost saved | type=button, checked=true |
| input | 25,000 or 25k | type=text, inputmode=decimal |
| button[checkbox] | New revenue | type=button, checked=false |
| button[checkbox] | Less reliance on outside tools | type=button, checked=false |
| button[radio] | My own research | type=button, checked=false |
| button[radio] | Verified documents | type=button, checked=false |
| button[radio] | A report or document | type=button, checked=false |
| button[radio] | A conversation | type=button, checked=false |
| button[radio] | A hunch | type=button, checked=false |
| textarea | (no label) |  |
| button | Cancel | type=button |
| button | Add my fix | type=button |

## State: `fix=Added`

Screenshot: `reference/shots/Review__fix-added.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
Added
Check it, part 5 of 6
Got an idea how to solve it?
Optional. A fix helps the review desk weigh it, but problems on their own get picked too.
Included, 5 of 5 ready
Send the reason in plain words in the SMS, with a link to what to do next.
70 to 150 hours a month, about ₹25,000 a month saved, solved elsewhere: partly
Change
your fix
Remove
your fix
Back
Next
```

Text removed:

```
Saved at 1:38 pm
1
4
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | Proof Optional | type=button |
| button | 5 Your fix Added | type=button |
| button | Change your fix | type=button, popup=dialog |
| button | Remove your fix | type=button |
| button | Back | type=button |
| button | Next | type=button |

## State: `merge=Waiting for Ravi`

Screenshot: `reference/shots/Review__merge-waiting-for-ravi.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm // status: Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own. Withdraw the request

Text added:

```
Saved at 1:39 pm
Waiting on Ravi to merge
Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own.
Withdraw the request
```

Text removed:

```
Saved at 1:38 pm
2 close ideas found
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | 3 Similar ideas Waiting on Ravi to merge | type=button |
| button | Withdraw the request | type=button |

## State: `merge=Ravi accepted`

Screenshot: `reference/shots/Review__merge-ravi-accepted.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm // status: Ravi accepted. Yours is now part of IDEA-2026-001412, with credit to you. Nothing else to send.

Text added:

```
Saved at 1:39 pm
Merged into IDEA-2026-001412
Ravi accepted. Yours is now part of IDEA-2026-001412, with credit to you. Nothing else to send.
```

Text removed:

```
Saved at 1:38 pm
2 close ideas found
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | 3 Similar ideas Merged into IDEA-2026-001412 | type=button |

## State: `merge=Ravi declined`

Screenshot: `reference/shots/Review__merge-ravi-declined.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm // status: Ravi kept that idea separate: “Mine is about the SMS wording, yours is about the calls it causes. Better as two.” Send yours on its own.

Text added:

```
Saved at 1:39 pm
Ravi kept it separate
Ravi kept that idea separate: “Mine is about the SMS wording, yours is about the calls it causes. Better as two.” Send yours on its own.
```

Text removed:

```
Saved at 1:38 pm
2 close ideas found
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | 3 Similar ideas Ravi kept it separate | type=button |

## State: `submit=Ready`

Screenshot: `reference/shots/Review__submit-ready.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
Investor service, saves time, saves cost
Step 3 of 3
Ready to send?
One last look. You can still change it until the review desk opens it.
Title
Change
title
Investor service, affecting investors and KFin teams, saves time, saves cost
Change
sorting
Change
similar ideas
None added
Change
proof
None added
Change
your fix
Not said
Change
who would help
By submitting, you confirm there’s no customer personal data in it or its files, and it’s your own work or you’ve credited others.
Back
Submit
```

Text removed:

```
Saved at 1:38 pm
1
Suggested, not confirmed yet
4
5
6
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Investor service, saves time, saves cost | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | Proof Optional | type=button |
| button | Your fix Optional | type=button |
| button | Who would help Optional | type=button |
| button | Change title | type=button |
| button | Change sorting | type=button |
| button | Change similar ideas | type=button |
| button | Change proof | type=button |
| button | Change your fix | type=button |
| button | Change who would help | type=button |
| button | Back | type=button |
| a | Submit | href=Status.dc.html |

## State: `submit=Tried without confirming`

Screenshot: `reference/shots/Review__submit-tried-without-confirming.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm // alert: Confirm the sorting first, or change any of it. Go to the sorting

Text added:

```
Saved at 1:39 pm
Step 3 of 3
Ready to send?
One last look. You can still change it until the review desk opens it.
Title
Change
title
Not confirmed yet
Change
sorting
Change
similar ideas
None added
Change
proof
None added
Change
your fix
Not said
Change
who would help
By submitting, you confirm there’s no customer personal data in it or its files, and it’s your own work or you’ve credited others.
Back
Confirm the sorting first, or change any of it.
Go to the sorting
Submit
```

Text removed:

```
Saved at 1:38 pm
1
4
5
6
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | Proof Optional | type=button |
| button | Your fix Optional | type=button |
| button | Who would help Optional | type=button |
| button | Change title | type=button |
| button | Change sorting | type=button |
| button | Change similar ideas | type=button |
| button | Change proof | type=button |
| button | Change your fix | type=button |
| button | Change who would help | type=button |
| button | Back | type=button |
| button | Go to the sorting | type=button |
| button | Submit | type=button |

## State: `submit=Send failed`

Screenshot: `reference/shots/Review__submit-send-failed.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm // alert: Couldn’t send. Your draft is safe. Check your connection, then try again.

Text added:

```
Saved at 1:39 pm
Investor service, saves time, saves cost
Step 3 of 3
Ready to send?
One last look. You can still change it until the review desk opens it.
Title
Change
title
Investor service, affecting investors and KFin teams, saves time, saves cost
Change
sorting
Change
similar ideas
None added
Change
proof
None added
Change
your fix
Not said
Change
who would help
By submitting, you confirm there’s no customer personal data in it or its files, and it’s your own work or you’ve credited others.
Back
Couldn’t send. Your draft is safe. Check your connection, then try again.
Try again
```

Text removed:

```
Saved at 1:38 pm
1
Suggested, not confirmed yet
4
5
6
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Investor service, saves time, saves cost | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | Proof Optional | type=button |
| button | Your fix Optional | type=button |
| button | Who would help Optional | type=button |
| button | Change title | type=button |
| button | Change sorting | type=button |
| button | Change similar ideas | type=button |
| button | Change proof | type=button |
| button | Change your fix | type=button |
| button | Change who would help | type=button |
| button | Back | type=button |
| a | Try again | href=Status.dc.html |

## State: `submit=Offline`

Screenshot: `reference/shots/Review__submit-offline.jpg`

Announced (role=alert or status): status: Unsaved, you’re offline // status: You’re offline. Your draft is saved on this device. Submit now and it sends when you’re back online.

Text added:

```
Unsaved, you’re offline
Investor service, saves time, saves cost
Step 3 of 3
Ready to send?
One last look. You can still change it until the review desk opens it.
Title
Change
title
Investor service, affecting investors and KFin teams, saves time, saves cost
Change
sorting
Change
similar ideas
None added
Change
proof
None added
Change
your fix
Not said
Change
who would help
By submitting, you confirm there’s no customer personal data in it or its files, and it’s your own work or you’ve credited others.
Back
You’re offline. Your draft is saved on this device. Submit now and it sends when you’re back online.
Submit
```

Text removed:

```
Saved at 1:38 pm
1
Suggested, not confirmed yet
4
5
6
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Investor service, saves time, saves cost | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | Proof Optional | type=button |
| button | Your fix Optional | type=button |
| button | Who would help Optional | type=button |
| button | Change title | type=button |
| button | Change sorting | type=button |
| button | Change similar ideas | type=button |
| button | Change proof | type=button |
| button | Change your fix | type=button |
| button | Change who would help | type=button |
| button | Back | type=button |
| button | Submit | type=button |

## State: `similar=A full grid of eight`

Screenshot: `reference/shots/Review__similar-a-full-grid-of-eight.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
8 similar ideas found
```

Text removed:

```
Saved at 1:38 pm
2 close ideas found
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | 3 Similar ideas 8 similar ideas found | type=button |

## State: `step=Your words`

Screenshot: `reference/shots/Review__step-your-words.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
```

Text removed:

```
Saved at 1:38 pm
```


## State: `step=Sorting`

Screenshot: `reference/shots/Review__step-sorting.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm // status: These are suggestions from your words. Not confirmed yet.

Text added:

```
Saved at 1:39 pm
Check it, part 2 of 6
Is it sorted right?
Sorting decides who reviews it. We suggested these from your words. Confirm them, or change any of them.
Who it affects
Pick all that apply
Investors
KFin teams
Distributors
Search all groups
Suggested because you mentioned investors and the branch.
What kind it is
Pick one
A problem to fix
A new business idea
Suggested because you described something that goes wrong today.
Area
Pick one
Investor service
Operations
Distributor experience
Search all areas
Suggested because it’s about investors and the SMS they get.
What it would bring
Pick all that apply
Saves time
Saves cost
Earns revenue
Cuts reliance on outside tools
Not sure yet
Suggested because you said “about 40 calls a day” and “5 to 10 minutes each”. Add revenue or outside tools if it does those too.
These are suggestions from your words. Not confirmed yet.
Back
Confirm sorting
```

Text removed:

```
Saved at 1:38 pm
1
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button[checkbox] | Investors | type=button, checked=true |
| button[checkbox] | KFin teams | type=button, checked=true |
| button[checkbox] | Distributors | type=button, checked=false |
| input[combobox] | Someone else? Search all 6 | type=text, expanded=false, autocomplete=off |
| button[radio] | A problem to fix | type=button, checked=true |
| button[radio] | A new business idea | type=button, checked=false |
| button[radio] | Investor service | type=button, checked=true |
| button[radio] | Operations | type=button, checked=false |
| button[radio] | Distributor experience | type=button, checked=false |
| input[combobox] | Another area? Search all 12 | type=search, expanded=false, autocomplete=off |
| button[checkbox] | Saves time | type=button, checked=true |
| button[checkbox] | Saves cost | type=button, checked=true |
| button[checkbox] | Earns revenue | type=button, checked=false |
| button[checkbox] | Cuts reliance on outside tools | type=button, checked=false |
| button[checkbox] | Not sure yet | type=button, checked=false |
| button | Back | type=button |
| button | Confirm sorting | type=button |

## State: `step=Similar ideas`

Screenshot: `reference/shots/Review__step-similar-ideas.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
Check it, part 3 of 6
Has someone raised this already?
Two colleagues shared something close while you were writing. Team up with them, and bring yours along if you like, or keep yours separate.
Yours, not sent yet
With the review desk
Rejection SMS codes confuse investors
IDEA-2026-001412, Investor service, Hyderabad
Close match: same SMS, same calls
RN
AS
PK
4 colleagues on it
Preview
Team up
Picked
No script for calls about rejections
IDEA-2026-001398, Operations, Mumbai
Related: the calls you describe
SP
MD
2 colleagues on it
Preview
Team up
None of these the same? Just carry on. Yours goes on its own.
Back
Next
```

Text removed:

```
Saved at 1:38 pm
1
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Preview Rejection SMS codes confuse investors | type=button, popup=dialog |
| button | Team up on Rejection SMS codes confuse investors | type=button |
| button | Preview No script for calls about rejections | type=button, popup=dialog |
| button | Team up on No script for calls about rejections | type=button |
| button | Back | type=button |
| button | Next | type=button |

## State: `step=Proof`

Screenshot: `reference/shots/Review__step-proof.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
Check it, part 4 of 6
Anything that shows it?
Optional, but it helps the review desk weigh it. Add screenshots, files or links that show the problem the way people meet it. We check each one for personal details before anyone else sees it.
Links to a report, dashboard or ticket
What helps most
A screenshot of the SMS or screen
A call log or ticket count that shows how often
A report with the time or money it costs
Back
Skip for now
```

Text removed:

```
Saved at 1:38 pm
1
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| input | Paste a link, or attach files. Add several links at once with commas. | type=text, inputmode=url, autocomplete=off |
| button | Attach files | type=button, expanded=false, popup=dialog |
| button | Add a link | type=button |
| button | Back | type=button |
| button | Skip for now | type=button |

## State: `step=Your fix`

Screenshot: `reference/shots/Review__step-your-fix.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
Check it, part 5 of 6
Got an idea how to solve it?
Optional. A fix helps the review desk weigh it, but problems on their own get picked too.
Say how you’d solve it
A few short questions: how, what it would need and what it’s worth. Only the first one is needed.
Add your fix
Back
Skip for now
```

Text removed:

```
Saved at 1:38 pm
1
4
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | Proof Optional | type=button |
| button | Add your fix | type=button, popup=dialog |
| button | Back | type=button |
| button | Skip for now | type=button |

## State: `step=Who would help`

Screenshot: `reference/shots/Review__step-who-would-help.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
Check it, part 6 of 6
Who would help?
Optional. It shows on Find your crew as “They’re looking for”, so the right colleagues can team up with you.
Someone at a branch
Someone in operations
Someone from tech
Someone who knows the rules
Data or reports
Who would help, in your own words
Back
Skip for now
```

Text removed:

```
Saved at 1:38 pm
1
4
5
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | Proof Optional | type=button |
| button | Your fix Optional | type=button |
| button[checkbox] | Someone at a branch | type=button, checked=false |
| button[checkbox] | Someone in operations | type=button, checked=false |
| button[checkbox] | Someone from tech | type=button, checked=false |
| button[checkbox] | Someone who knows the rules | type=button, checked=false |
| button[checkbox] | Data or reports | type=button, checked=false |
| input | Or say it your way, for example someone who takes these calls at a branch | type=text |
| button | Back | type=button |
| button | Skip for now | type=button |

## State: `step=Send it`

Screenshot: `reference/shots/Review__step-send-it.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
Step 3 of 3
Ready to send?
One last look. You can still change it until the review desk opens it.
Title
Change
title
Not confirmed yet
Change
sorting
Change
similar ideas
None added
Change
proof
None added
Change
your fix
Not said
Change
who would help
By submitting, you confirm there’s no customer personal data in it or its files, and it’s your own work or you’ve credited others.
Back
Submit
```

Text removed:

```
Saved at 1:38 pm
1
4
5
6
Check it, part 1 of 6
Is this how you’d put it?
This is what the review desk reads first. We wrote it only from your words, so change anything that isn’t right.
What happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Hidden from everyone
Show it
Folio ••••89
Back to your words
Looks right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Your words Title, what happens, how often | type=button |
| button | Sorting Suggested, not confirmed yet | type=button |
| button | Similar ideas 2 close ideas found | type=button |
| button | Proof Optional | type=button |
| button | Your fix Optional | type=button |
| button | Who would help Optional | type=button |
| button | Change title | type=button |
| button | Change sorting | type=button |
| button | Change similar ideas | type=button |
| button | Change proof | type=button |
| button | Change your fix | type=button |
| button | Change who would help | type=button |
| button | Back | type=button |
| button | Submit | type=button |

## State: `attached=A screenshot`

Screenshot: `reference/shots/Review__attached-a-screenshot.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
Title, what happens, how often, 1 file
1 file
Attached
JPG
sms-on-investor-phone.jpg
```

Text removed:

```
Saved at 1:38 pm
Title, what happens, how often
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | 1 Your words Title, what happens, how often, 1 file | type=button |
| button | 4 Proof 1 file | type=button |
| button | Change the attached files | type=button |

## State: `attached=A screenshot and a PDF`

Screenshot: `reference/shots/Review__attached-a-screenshot-and-a-pdf.jpg`

Announced (role=alert or status): status: Saved at 1:39 pm

Text added:

```
Saved at 1:39 pm
Title, what happens, how often, 2 files
2 files
Attached
JPG
sms-on-investor-phone.jpg
PDF
branch-call-log-nov.pdf
```

Text removed:

```
Saved at 1:38 pm
Title, what happens, how often
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | 1 Your words Title, what happens, how often, 2 files | type=button |
| button | 4 Proof 2 files | type=button |
| button | Change the attached files | type=button |
