# ComposeResume: copy and controls per state

Generated from the prototype board `reference/prototype/ComposeResume.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/ComposeResume.jpg`

Headings: H2: Your draft

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
Check it
Send it
Saved at 1:38 pm
Save and close
Picked up where you left off.
Last saved on your phone, Friday 8:42 pm.
Start a new one instead
Distributors ring the branch to ask why an SIP registration is stuck. IRIS shows Pending with no reason, so we raise a ticket and wait two or three days. This happens about 15 times a week at our branch.​
sip-pending-screen.jpg
Checked
You
Friday, 8:42 pm, on your phone
Edit
Drafted a title: “Distributors can’t see why an SIP registration is stuck”.
Sorted it under Distributor experience, affecting distributors and KFin teams.
Noted how often: about 15 times a week at one branch.
Marked it as saves time and saves cost.
Your draft is ready. Add a detail, or check it.
Add what you already tried
Change the title
Add to your draft
Add a detail any time. It goes straight into the draft.
Your draft
Up to date
Distributors can’t see why an SIP registration is stuck
From your first sentence.
Change
the title
IRIS shows an SIP registration as Pending with no reason, so distributors ring the branch to ask. The branch raises a ticket and waits two or three days for an answer. This happens about 15 times a week at one branch.
How often
About 15 times a week at one branch
From your words: “about 15 times a week”
Change
How often
Who it affects
Distributors, KFin teams
Suggested because you mentioned distributors and the branch.
Change
Who it affects
What it’s worth
Saves time, Saves cost
From your words: “about 15 times a week”.
Change
What it’s worth
Area
Distributor experience
Suggested because it’s about distributor experience.
Change
Area
Looks right? Check the sorting and send it.
Move to Review
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
| button | Start a new one instead | type=button |
| button | Edit | type=button |
| button | Add what you already tried | type=button |
| button | Change the title | type=button |
| textarea | Add a detail, like how often it happens or what you tried |  |
| button | Speak instead | type=button, pressed=false |
| button | Add to your draft | type=button |
| button | Change the title | type=button, expanded=false |
| button | Change How often | type=button, expanded=false |
| button | Change Who it affects | type=button, expanded=false |
| button | Change What it’s worth | type=button, expanded=false |
| button | Change Area | type=button, expanded=false |
| a | Move to Review | href=Review.dc.html |

## State: `simulatorS1=Interview`

Screenshot: `reference/shots/ComposeResume__simulators1-interview.jpg`

Announced (role=alert or status): status: Saved at 1:38 pm // status: Up to date

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `hidden=One`

Screenshot: `reference/shots/ComposeResume__hidden-one.jpg`

Announced (role=alert or status): status: Saved at 1:38 pm // status: Up to date

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `loader=Slow similar ideas`

Screenshot: `reference/shots/ComposeResume__loader-slow-similar-ideas.jpg`

Announced (role=alert or status): status: Saved at 1:38 pm // status: Up to date

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `loader=Held for review`

Screenshot: `reference/shots/ComposeResume__loader-held-for-review.jpg`

Announced (role=alert or status): status: Saved at 1:38 pm // status: Updating

Text added:

```
Updating
Building your draft
2 of 6 ready, about 2 seconds left
Updating
Updating
Still working through your words.
```

Text removed:

```
Drafted a title: “Distributors can’t see why an SIP registration is stuck”.
Sorted it under Distributor experience, affecting distributors and KFin teams.
Marked it as saves time and saves cost.
Your draft is ready. Add a detail, or check it.
Add what you already tried
Change the title
Up to date
From your first sentence.
the title
IRIS shows an SIP registration as Pending with no reason, so distributors ring the branch to ask. The branch raises a ticket and waits two or three days for an answer. This happens about 15 times a week at one branch.
Distributors, KFin teams
Suggested because you mentioned distributors and the branch.
Saves time, Saves cost
From your words: “about 15 times a week”.
Looks right? Check the sorting and send it.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Move to Review | type=button, disabled=true |
