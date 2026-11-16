# PhoneReview: copy and controls per state

Generated from the prototype board `reference/prototype/PhoneReview.dc.html`, rendered at 390px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/PhoneReview.jpg`

Headings: H1: Check it, then send it; H2: Your problem; H2: Is this sorted right?; H2: Already raised?; H2: Anything that shows it?Optional; H2: Your fixOptional

### Text, top to bottom

```
Save and close
Saved at 1:40 pm
Step 2 of 3 Check it
Next: send it
Check it, then send it
Written only from your words. Change anything that isn’t right.
1
detail hidden
3
sortings
2
similar ideas
Back to your words
Your problem
Title
Change
title
Investors call to ask why a redemption was rejected
What happens
Change
what happens
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
Change
how often
About 40 calls a day at one branch
Hidden from everyone
Not personal? Show it
Folio ••••89
Is this sorted right?
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
Yes, that’s right
Already raised?
Two ideas look close to yours. Team up on one, or send yours linked to it so both are decided together. Sending yours on its own is fine too.
Rejection SMS codes confuse investors
IDEA-2026-001412, Investor service, Hyderabad
With the review desk
Close match: same SMS, same calls
RN
AS
PK
4 colleagues on it
Preview
Team up
No script for calls about rejections
IDEA-2026-001398, Operations, Mumbai
Picked
Related: the calls you describe
SP
MD
2 colleagues on it
Preview
Team up
None of these the same? Just carry on. Yours goes on its own.
Anything that shows it?Optional
It helps the review desk weigh it. Add screenshots, files or links that show the problem the way people meet it. We check each one for personal details before anyone else sees it.
Links to a report, dashboard or ticket
Your fixOptional
Got an idea how to solve it?
It helps the review desk weigh it. Skipping it is fine: problems on their own get picked too.
Add your fix
Submitting confirms there’s no customer personal data in it or its files, and it’s your own work or credited.
Submit
```

### Controls

| Element | Label | Attributes |
|---|---|---|
| a | Save and close | href=PhoneHome.dc.html |
| a | 1 detail hidden | href=#pr-hidden |
| a | 3 sortings | href=#pr-sort-h |
| a | 2 similar ideas | href=#pr-sim-h |
| a | Back to your words | href=PhoneCompose.dc.html |
| button | Change title | type=button |
| button | Change what happens | type=button |
| button | Change how often | type=button |
| button | Not personal? Show it | type=button |
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
| button | Yes, that’s right | type=button |
| button | Preview Rejection SMS codes confuse investors | type=button, popup=dialog |
| button | Team up on Rejection SMS codes confuse investors | type=button |
| button | Preview No script for calls about rejections | type=button, popup=dialog |
| button | Team up on No script for calls about rejections | type=button |
| input | Paste links, or attach files | type=text, inputmode=url, autocomplete=off |
| button | Attach files | type=button, expanded=false, popup=dialog |
| button | Add a link | type=button |
| button | Add your fix | type=button, popup=dialog |
| button | Submit | type=button |

## State: `simulatorS2=Check first`

Screenshot: `reference/shots/PhoneReview__simulators2-check-first.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm

Text added:

```
Is it one of these?
Something very close was shared on 9 November. Adding yours to it gets both decided together, and you’re credited.
Yours, not sent yet
IDEA-2026-001412, shared 9 November
Investors get an SMS with only a code when a transaction is rejected, and call the branch to ask what it means.
Investor service, Hyderabad, 4 colleagues
Also related: No script for calls about rejections, Operations, Mumbai. You’ll see it on the next part.
Mine is different
```

Text removed:

```
Written only from your words. Change anything that isn’t right.
1
detail hidden
3
sortings
2
similar ideas
Back to your words
Your problem
Title
Change
title
What happens
Change
what happens
How often
Change
how often
About 40 calls a day at one branch
Hidden from everyone
Not personal? Show it
Folio ••••89
Is this sorted right?
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
Yes, that’s right
Already raised?
Two ideas look close to yours. Team up on one, or send yours linked to it so both are decided together. Sending yours on its own is fine too.
IDEA-2026-001412, Investor service, Hyderabad
Close match: same SMS, same calls
RN
AS
PK
4 colleagues on it
… and 19 more lines
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Team up | type=button |
| button | Mine is different | type=button |

## State: `evidence=Added`

Screenshot: `reference/shots/PhoneReview__evidence-added.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: These are suggestions from your words. Not confirmed yet. // status: Checked // status: Checking for personal details

Text added:

```
PNG
rejection-sms-screenshot.png
84 KB
Checked
PDF
branch-call-log-nov.pdf
140 KB
Checking for personal details
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Remove rejection-sms-screenshot.png | type=button |
| button | Remove branch-call-log-nov.pdf | type=button |

## State: `evidence=Upload failed`

Screenshot: `reference/shots/PhoneReview__evidence-upload-failed.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: These are suggestions from your words. Not confirmed yet. // alert: Didn’t upload. Your other files are fine. // status: Checked

Text added:

```
PNG
rejection-sms-screenshot.png
84 KB
Didn’t upload. Your other files are fine.
Try again
PDF
branch-call-log-nov.pdf
140 KB
Checked
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Try again | type=button |
| button | Remove rejection-sms-screenshot.png | type=button |
| button | Remove branch-call-log-nov.pdf | type=button |

## State: `evidence=Personal data found`

Screenshot: `reference/shots/PhoneReview__evidence-personal-data-found.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: These are suggestions from your words. Not confirmed yet. // status: Checked // alert: Found a phone number on page 2. Nobody can open it until it’s hidden.

Text added:

```
PNG
rejection-sms-screenshot.png
84 KB
Checked
PDF
branch-call-log-nov.pdf
140 KB
Found a phone number on page 2. Nobody can open it until it’s hidden.
Hide it for me
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Remove rejection-sms-screenshot.png | type=button |
| button | Hide it for me | type=button |
| button | Remove branch-call-log-nov.pdf | type=button |

## State: `evidence=Link unreachable`

Screenshot: `reference/shots/PhoneReview__evidence-link-unreachable.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: These are suggestions from your words. Not confirmed yet. // status: Checked // alert: We couldn’t open this link. It may need a sign-in; the review desk can still try it.

Text added:

```
PNG
rejection-sms-screenshot.png
84 KB
Checked
Rejection codes list on the intranet
Link
We couldn’t open this link. It may need a sign-in; the review desk can still try it.
Keep it
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Remove rejection-sms-screenshot.png | type=button |
| button | Keep it | type=button |
| button | Remove Rejection codes list on the intranet | type=button |

## State: `fix=Sheet open`

Screenshot: `reference/shots/PhoneReview__fix-sheet-open.jpg`

Dialogs open: Your fix

Announced (role=alert or status): status: Saved at 1:40 pm // status: These are suggestions from your words. Not confirmed yet.

Text added:

```
You started a fix. It isn’t included yet.
Carry on with your fix
Cancel
Your fix
Done
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
Add my fix
```

Text removed:

```
Add your fix
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Carry on with your fix | type=button, popup=dialog |
| button | Cancel, and keep what you wrote | type=button |
| button | Done | type=button |
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
| button | Add my fix | type=button |

## State: `fix=Added`

Screenshot: `reference/shots/PhoneReview__fix-added.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: These are suggestions from your words. Not confirmed yet.

Text added:

```
Included, 5 of 5 ready
Send the reason in plain words in the SMS, with a link to what to do next.
70 to 150 hours a month, about ₹25,000 a month saved, solved elsewhere: partly
your fix
Remove
your fix
Submit with my fix
```

Text removed:

```
Got an idea how to solve it?
It helps the review desk weigh it. Skipping it is fine: problems on their own get picked too.
Add your fix
Submit
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Change your fix | type=button, popup=dialog |
| button | Remove your fix | type=button |
| button | Submit with my fix | type=button |

## State: `merge=Waiting for Ravi`

Screenshot: `reference/shots/PhoneReview__merge-waiting-for-ravi.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: These are suggestions from your words. Not confirmed yet. // status: Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own. Withdraw the request

Text added:

```
5 colleagues on it
Waiting for Ravi to accept the merge
Withdraw
Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own.
Withdraw the request
```

Text removed:

```
4 colleagues on it
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Withdraw | type=button |
| button | Withdraw the request | type=button |

## State: `merge=Ravi accepted`

Screenshot: `reference/shots/PhoneReview__merge-ravi-accepted.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: These are suggestions from your words. Not confirmed yet. // status: Ravi accepted. Yours is now part of IDEA-2026-001412, with credit to you. Nothing else to send.

Text added:

```
5 colleagues on it
Merged. Yours is part of it, credited to you
Ravi accepted. Yours is now part of IDEA-2026-001412, with credit to you. Nothing else to send.
See the merged idea
```

Text removed:

```
4 colleagues on it
Submit
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | See the merged idea | href=PhoneIdea.dc.html |

## State: `merge=Ravi declined`

Screenshot: `reference/shots/PhoneReview__merge-ravi-declined.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: These are suggestions from your words. Not confirmed yet. // status: Ravi kept that idea separate: “Mine is about the SMS wording, yours is about the calls it causes. Better as two.” Send yours on its own.

Text added:

```
5 colleagues on it
Ravi kept it separate
Ravi kept that idea separate: “Mine is about the SMS wording, yours is about the calls it causes. Better as two.” Send yours on its own.
Send mine on its own
```

Text removed:

```
4 colleagues on it
Submit
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Send mine on its own | type=button |

## State: `submit=Ready`

Screenshot: `reference/shots/PhoneReview__submit-ready.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: Confirmed. You can still change any of these.

Text added:

```
Confirmed. You can still change any of these.
```

Text removed:

```
These are suggestions from your words. Not confirmed yet.
Yes, that’s right
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Submit | href=PhoneStatus.dc.html |

## State: `submit=Tried without confirming`

Screenshot: `reference/shots/PhoneReview__submit-tried-without-confirming.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: These are suggestions from your words. Not confirmed yet. // alert: Confirm these, or change any of them, before you send. // alert: Confirm the sorting first, or change any of it. Go to the sorting

Text added:

```
Confirm these, or change any of them, before you send.
Confirm the sorting first, or change any of it.
Go to the sorting
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Go to the sorting | type=button |

## State: `submit=Send failed`

Screenshot: `reference/shots/PhoneReview__submit-send-failed.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: Confirmed. You can still change any of these. // alert: Couldn’t send. Your draft is safe. Check your connection, then try again.

Text added:

```
Confirmed. You can still change any of these.
Couldn’t send. Your draft is safe. Check your connection, then try again.
Try again
```

Text removed:

```
These are suggestions from your words. Not confirmed yet.
Yes, that’s right
Submit
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Try again | href=PhoneStatus.dc.html |

## State: `submit=Offline`

Screenshot: `reference/shots/PhoneReview__submit-offline.jpg`

Announced (role=alert or status): status: Unsaved, you’re offline // status: Confirmed. You can still change any of these. // status: You’re offline. Your draft is saved on this device. Submit now and it sends when you’re back online.

Text added:

```
Unsaved, you’re offline
Confirmed. You can still change any of these.
You’re offline. Your draft is saved on this device. Submit now and it sends when you’re back online.
```

Text removed:

```
Saved at 1:40 pm
These are suggestions from your words. Not confirmed yet.
Yes, that’s right
```

