# PhoneEdit: copy and controls per state

Generated from the prototype board `reference/prototype/PhoneEdit.dc.html`, rendered at 390px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/PhoneEdit.jpg`

Headings: H1: Edit your problem; H2: Your problem; H2: Is this sorted right?; H2: Anything that shows it?Optional; H2: Your fixOptional; H2: What happens when you save

### Text, top to bottom

```
Cancel
Unsaved changes
Edit IDEA-2026-001481
Shared Saturday 14 November. You can edit until the review desk opens it, at the latest Tuesday 17 November.
Edit your problem
Change anything that isn’t right. Nothing changes for anyone else until you save.
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
Confirmed when you shared it. You can still change any of these.
Anything that shows it?Optional
Add a photo or file
A screenshot of the SMS, a call log, or a report with the time or money it costs
Link to a report, dashboard or ticket
Add
Your fixOptional
Got an idea how to solve it?
It helps the review desk weigh it. Skipping it is fine: problems on their own get picked too.
Add your fix
What happens when you save
Straight away
The review desk sees the latest version. Earlier versions are kept on the timeline.
At the latest Tuesday 17 November
Editing closes when the review desk opens it. After that, you can add a note for them.
Cancel
Saving confirms there’s no customer personal data in it or its files, and it’s your own work or credited.
Save changes
```

### Controls

| Element | Label | Attributes |
|---|---|---|
| a | Cancel | href=PhoneStatus.dc.html |
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
| button | Add a photo or file A screenshot of the SMS, a call log, or a report with the time or money it costs | type=button |
| input | Or paste a link | type=url, inputmode=url |
| button | Add | type=button |
| button | Add your fix | type=button, popup=dialog |
| a | Cancel | href=PhoneStatus.dc.html |
| button | Save changes | type=button |

## State: `evidence=Added`

Screenshot: `reference/shots/PhoneEdit__evidence-added.jpg`

Announced (role=alert or status): status: Unsaved changes // status: Confirmed when you shared it. You can still change any of these. // status: Checked // status: Checking for personal details

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

Screenshot: `reference/shots/PhoneEdit__evidence-upload-failed.jpg`

Announced (role=alert or status): status: Unsaved changes // status: Confirmed when you shared it. You can still change any of these. // alert: Didn’t upload. Your other files are fine. // status: Checked

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

Screenshot: `reference/shots/PhoneEdit__evidence-personal-data-found.jpg`

Announced (role=alert or status): status: Unsaved changes // status: Confirmed when you shared it. You can still change any of these. // status: Checked // alert: Found a phone number on page 2. Nobody can open it until it’s hidden.

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

Screenshot: `reference/shots/PhoneEdit__evidence-link-unreachable.jpg`

Announced (role=alert or status): status: Unsaved changes // status: Confirmed when you shared it. You can still change any of these. // status: Checked // alert: We couldn’t open this link. It may need a sign-in; the review desk can still try it.

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

## State: `fix=Not added`

Screenshot: `reference/shots/PhoneEdit__fix-not-added.jpg`

Announced (role=alert or status): status: Unsaved changes // status: Confirmed when you shared it. You can still change any of these.

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `fix=Sheet open`

Screenshot: `reference/shots/PhoneEdit__fix-sheet-open.jpg`

Dialogs open: Your fix

Announced (role=alert or status): status: Unsaved changes // status: Confirmed when you shared it. You can still change any of these.

Text added:

```
You started a fix. It isn’t included yet.
Carry on with your fix
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

## State: `save=Saved`

Screenshot: `reference/shots/PhoneEdit__save-saved.jpg`

Announced (role=alert or status): status: Saved at 1:41 pm // status: Confirmed when you shared it. You can still change any of these. // status: Saved. The review desk will see the latest version.

Text added:

```
Saved at 1:41 pm
Back to your idea
Saved. The review desk will see the latest version.
```

Text removed:

```
Unsaved changes
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Back to your idea | href=PhoneStatus.dc.html |
