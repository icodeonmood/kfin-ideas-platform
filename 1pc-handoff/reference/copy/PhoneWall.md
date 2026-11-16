# PhoneWall: copy and controls per state

Generated from the prototype board `reference/prototype/PhoneWall.dc.html`, rendered at 390px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/PhoneWall.jpg`

Headings: H1: Wall; H2: Kindling; H3: Just in; H3: Picked; H3: Being built; H3: Shipped; H2: The Ones; H2: What shipped ideas changed

### Text, top to bottom

```
1% Club
KM
Wall
Every idea from across KFintech, the people behind what shipped, and what it changed.
Kindling
Every idea and problem shared, and where it is now.
All
Problems
Fixes
Business ideas
Just in
12
Sorted by newest
Remind investors before an SIP mandate expires
Problem, Investor service. Shared 2h ago
Let branches book a courier pickup from the desk
Fix, Operations. Shared 5h ago
Show the cut-off time on every purchase screen
Fix, Distributor experience. Shared yesterday
Show 3 more
Picked
3
Explain transaction rejections to distributors
Problem, Distributor experience. 4 colleagues on it
Tell distributors on IRIS when an investor’s KYC lapses
Fix, Compliance. 2 colleagues on it
A one-page NFO kit for B30 branches
Business idea, Sales. 3 colleagues on it
Being built
2
Operations re-check every SIP mandate by hand
Problem, Operations. 5 colleagues on it
Track couriered redemption forms
Fix, Operations. 3 colleagues on it
Shipped
1
Flag likely-wrong bank details before the first SIP debit
Problem, Investor service. 4 colleagues on it
The Ones
Colleagues whose fixes shipped and made a measured difference. Each keeps a number.
Number
1
Rohit Menon
Tier 4, Blaze
Wrong bank details are caught before the first debit, not after it bounces.
Number
9
Sneha Kulkarni
Tier 5, White heat
One write-up of a fix that other teams can adopt.
Number
5
Arjun Nair
Tier 3, Flame
Redemption forms are tracked from branch to desk.
Number
23
Priya Iyer
Tier 1, Spark
Nominee changes now finish in one visit instead of three.
What shipped ideas changed
Measured 30 and 90 days after each fix ships. Finance confirms anything about money.
930
Hours saved a month
₹24 lakh
Saved a year, Finance confirmed
6
Fixes shipped and measured
58,600
Distributors reached by a shipped fix
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
| button | All | type=button, pressed=true |
| button | Problems | type=button, pressed=false |
| button | Fixes | type=button, pressed=false |
| button | Business ideas | type=button, pressed=false |
| button | Sorted by newest | type=button |
| a | Remind investors before an SIP mandate expires Problem, Investor service. Shared 2h ago | href=PhoneIdea.dc.html |
| a | Let branches book a courier pickup from the desk Fix, Operations. Shared 5h ago | href=PhoneIdea.dc.html |
| a | Show the cut-off time on every purchase screen Fix, Distributor experience. Shared yesterday | href=PhoneIdea.dc.html |
| button | Show 3 more | type=button |
| a | Explain transaction rejections to distributors Problem, Distributor experience. 4 colleagues on it | href=PhoneIdea.dc.html |
| a | Tell distributors on IRIS when an investor’s KYC lapses Fix, Compliance. 2 colleagues on it | href=PhoneIdea.dc.html |
| a | A one-page NFO kit for B30 branches Business idea, Sales. 3 colleagues on it | href=PhoneIdea.dc.html |
| a | Operations re-check every SIP mandate by hand Problem, Operations. 5 colleagues on it | href=PhoneIdea.dc.html |
| a | Track couriered redemption forms Fix, Operations. 3 colleagues on it | href=PhoneIdea.dc.html |
| a | Flag likely-wrong bank details before the first SIP debit Problem, Investor service. 4 colleagues on it | href=PhoneIdea.dc.html |
| a | Home | href=PhoneHome.dc.html |
| a | My ideas | href=PhoneMyIdeas.dc.html |
| a | Share a problem | href=PhoneCompose.dc.html |
| a | Wall | href=PhoneWall.dc.html |
| a | Inbox, 2 new | href=PhoneInbox.dc.html |

## State: `filter=Problems`

Screenshot: `reference/shots/PhoneWall__filter-problems.jpg`

Text added:

```
4
Distributors can’t see why a switch was rejected
Problem, Distributor experience. Shared 2 days ago
Branch staff key in the same KYC details twice
Problem, Operations. Shared 3 days ago
Show 1 more
```

Text removed:

```
12
Let branches book a courier pickup from the desk
Fix, Operations. Shared 5h ago
Show the cut-off time on every purchase screen
Fix, Distributor experience. Shared yesterday
Show 3 more
3
Tell distributors on IRIS when an investor’s KYC lapses
Fix, Compliance. 2 colleagues on it
A one-page NFO kit for B30 branches
Business idea, Sales. 3 colleagues on it
Track couriered redemption forms
Fix, Operations. 3 colleagues on it
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All | type=button, pressed=false |
| button | Problems | type=button, pressed=true |
| a | Distributors can’t see why a switch was rejected Problem, Distributor experience. Shared 2 days ago | href=PhoneIdea.dc.html |
| a | Branch staff key in the same KYC details twice Problem, Operations. Shared 3 days ago | href=PhoneIdea.dc.html |
| button | Show 1 more | type=button |

## State: `filter=Fixes`

Screenshot: `reference/shots/PhoneWall__filter-fixes.jpg`

Text added:

```
Pre-fill the nominee form from the investor’s last folio
Fix, Investor service. Shared 2 days ago
Show 2 more
```

Text removed:

```
12
Remind investors before an SIP mandate expires
Problem, Investor service. Shared 2h ago
Show 3 more
3
Explain transaction rejections to distributors
Problem, Distributor experience. 4 colleagues on it
A one-page NFO kit for B30 branches
Business idea, Sales. 3 colleagues on it
Operations re-check every SIP mandate by hand
Problem, Operations. 5 colleagues on it
Shipped
Flag likely-wrong bank details before the first SIP debit
Problem, Investor service. 4 colleagues on it
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All | type=button, pressed=false |
| button | Fixes | type=button, pressed=true |
| a | Pre-fill the nominee form from the investor’s last folio Fix, Investor service. Shared 2 days ago | href=PhoneIdea.dc.html |
| button | Show 2 more | type=button |

## State: `filter=Business ideas`

Screenshot: `reference/shots/PhoneWall__filter-business-ideas.jpg`

Text added:

```
A paid data feed of anonymised SIP trends for AMCs
Business idea, New business. Shared yesterday
White-label the SIP calculator for AMC partner sites
Business idea, New business. Shared 4 days ago
A monthly digest of investor complaints by scheme, for AMCs
Business idea, Sales. Shared 6 days ago
```

Text removed:

```
12
Remind investors before an SIP mandate expires
Problem, Investor service. Shared 2h ago
Let branches book a courier pickup from the desk
Fix, Operations. Shared 5h ago
Show the cut-off time on every purchase screen
Fix, Distributor experience. Shared yesterday
Show 3 more
Explain transaction rejections to distributors
Problem, Distributor experience. 4 colleagues on it
Tell distributors on IRIS when an investor’s KYC lapses
Fix, Compliance. 2 colleagues on it
Being built
Operations re-check every SIP mandate by hand
Problem, Operations. 5 colleagues on it
Track couriered redemption forms
Fix, Operations. 3 colleagues on it
Shipped
Flag likely-wrong bank details before the first SIP debit
Problem, Investor service. 4 colleagues on it
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | All | type=button, pressed=false |
| button | Business ideas | type=button, pressed=true |
| a | A paid data feed of anonymised SIP trends for AMCs Business idea, New business. Shared yesterday | href=PhoneIdea.dc.html |
| a | White-label the SIP calculator for AMC partner sites Business idea, New business. Shared 4 days ago | href=PhoneIdea.dc.html |
| a | A monthly digest of investor complaints by scheme, for AMCs Business idea, Sales. Shared 6 days ago | href=PhoneIdea.dc.html |
