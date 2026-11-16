# Profile: copy and controls per state

Generated from the prototype board `reference/prototype/Profile.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Profile.jpg`

Headings: H1: Kavya Menon; H2: Your points; H2: On the Wall; H2: How we reach you

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
KM
Kavya Menon
Investor service, Hyderabad. Tier 2, Glow.
Your points
340
Only you see your points. They never decide who becomes a One.
How points and tiers work
On the Wall
Show my name next to my ideas
Your name shows on the Wall next to your shared ideas. It applies to every idea you share, and you can change it here any time.
How we reach you
Teams messages
When the review desk asks you something, or one of your ideas moves a stage.
Email
The same updates, for your records.
Reminders before a question is due
A day before, and again two hours before.
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
| a | How points and tiers work | href=How.dc.html |
| button[switch] | (no label) | type=button, checked=true |
| button[switch] | (no label) | type=button, checked=true |
| button[switch] | (no label) | type=button, checked=true |
| button[switch] | (no label) | type=button, checked=true |

## State: `wall=Hidden`

Screenshot: `reference/shots/Profile__wall-hidden.jpg`

Announced (role=alert or status): status: Your ideas show on the Wall without your name. It applies to every idea you share, and you can change it here any time.

Text added:

```
Your ideas show on the Wall without your name. It applies to every idea you share, and you can change it here any time.
```

Text removed:

```
Your name shows on the Wall next to your shared ideas. It applies to every idea you share, and you can change it here any time.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button[switch] | (no label) | type=button, checked=false |
