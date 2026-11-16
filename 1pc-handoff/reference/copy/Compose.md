# Compose: copy and controls per state

Generated from the prototype board `reference/prototype/Compose.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Compose.jpg`

Headings: H1: What keeps getting in your way, Kavya?; H2: Your draft

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
What keeps getting in your way, Kavya?
​
Describe the problem
Tap to start speaking
Not recording until you do
Say it in whichever language feels most natural to you.
A step customers keep calling about
Something we redo by hand every month
A screen that asks for the same thing twice
Your draft
Forms as you write
Your title appears here
How often
Waiting for your words
Who it affects
Waiting for your words
What it’s worth
Waiting for your words
Area
Waiting for your words
Your draft needs a little more first.
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
| textarea | For example: when a redemption is rejected, the SMS only gives a code, so investors call the branch to ask what it means. |  |
| button | Add a screenshot or file | type=button |
| button | Tap to start speaking | type=button |
| button | A step customers keep calling about | type=button |
| button | Something we redo by hand every month | type=button |
| button | A screen that asks for the same thing twice | type=button |
| button | Move to Review | type=button, disabled=true |

## State: `state=Typing, draft forming`

Screenshot: `reference/shots/Compose__state-typing-draft-forming.jpg`

Announced (role=alert or status): status: Saving… // status: Updating

Text added:

```
Saving…
Save and close
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week.​
Enter starts your draft. Shift and Enter for a new line.
Updating
From your first sentence.
Change
the title
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch.
Updating
Investors, KFin teams
Suggested because you mentioned investors and the branch.
Change
Updating
Investor service
Suggested because it’s about investors and the SMS they get.
Change
2 similar ideas
Colleagues raised something close
Looks right? Check the sorting and send it.
```

Text removed:

```
​
Tap to start speaking
Not recording until you do
A step customers keep calling about
Something we redo by hand every month
A screen that asks for the same thing twice
Forms as you write
Your title appears here
Waiting for your words
Waiting for your words
Waiting for your words
Waiting for your words
Your draft needs a little more first.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Save and close | href=Home.dc.html |
| button | Speak instead | type=button, pressed=false |
| button | Start my draft | type=button |
| button | Change the title | type=button, expanded=false |
| button | Change Who it affects | type=button, expanded=false |
| button | Change Area | type=button, expanded=false |
| button | 2 similar ideas Colleagues raised something close | type=button, expanded=false |

## State: `state=Draft ready`

Screenshot: `reference/shots/Compose__state-draft-ready.jpg`

Announced (role=alert or status): status: Saved at 1:38 pm // status: Updating

Text added:

```
Tell it
Check it
Send it
Saved at 1:38 pm
Save and close
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week from 9876543210 and read out his PAN, ABCPK1234F. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
You
Just now
Edit
Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10.
Add to your draft
Working through your words. You can already add more.
Updating
Building your draft
1 of 6 ready, about 2 seconds left
Updating
Updating
Updating
Investor service
Suggested because it’s about investors and the SMS they get.
Change
Hidden details
Personal details hidden
Folio number, PAN and phone number
3
Still working through your words.
```

Text removed:

```
What keeps getting in your way, Kavya?
​
Describe the problem
Tap to start speaking
Not recording until you do
Say it in whichever language feels most natural to you.
A step customers keep calling about
Something we redo by hand every month
A screen that asks for the same thing twice
Forms as you write
Your title appears here
Waiting for your words
Waiting for your words
Waiting for your words
Waiting for your words
Your draft needs a little more first.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Save and close | href=Home.dc.html |
| button | Edit | type=button |
| textarea | Add a detail, like how often it happens or what you tried |  |
| button | Speak instead | type=button, pressed=false |
| button | Add to your draft | type=button |
| button | Change Area | type=button, expanded=false |
| button | Personal details hidden Folio number, PAN and phone number 3 | type=button, expanded=false |

## State: `state=Speaking`

Screenshot: `reference/shots/Compose__state-speaking.jpg`

Announced (role=alert or status): status: Saving… // status: When a redemption is rejected, the SMS to the investor only says Rejected, R07. Nobody knows what R07 means, so they call the // status: Updating

Text added:

```
Saving…
Save and close
When a redemption is rejected, the SMS to the investor only says Rejected, R07. Nobody knows what R07 means, so they call the
Listening. Up to 3 minutes.
Updating
From your first sentence.
Change
the title
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch.
Updating
Investors
Suggested because you mentioned investors.
Change
Updating
Investor service
Suggested because it’s about investors and the SMS they get.
Change
2 similar ideas
Colleagues raised something close
```

Text removed:

```
​
Describe the problem
Tap to start speaking
Not recording until you do
A step customers keep calling about
Something we redo by hand every month
A screen that asks for the same thing twice
Forms as you write
Your title appears here
Waiting for your words
Waiting for your words
Waiting for your words
Waiting for your words
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Save and close | href=Home.dc.html |
| button | Stop, and use what you said | type=button, pressed=true |
| button | Type or speak first | type=button |
| button | Change the title | type=button, expanded=false |
| button | Change Who it affects | type=button, expanded=false |
| button | Change Area | type=button, expanded=false |
| button | 2 similar ideas Colleagues raised something close | type=button, expanded=false |

## State: `state=Mic blocked`

Screenshot: `reference/shots/Compose__state-mic-blocked.jpg`

Announced (role=alert or status): alert: Your browser has blocked the microphone. Allow it from the lock icon in the address bar, then try again. Or just type in the box above. // status: Forms as you write

Text added:

```
Your browser has blocked the microphone.
Allow it from the lock icon in the address bar, then try again. Or just type in the box above.
```

Text removed:

```
Tap to start speaking
Not recording until you do
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Microphone blocked | type=button, pressed=false |
| button | Type or speak first | type=button |

## State: `state=Offline`

Screenshot: `reference/shots/Compose__state-offline.jpg`

Announced (role=alert or status): status: Unsaved, you’re offline // status: Updating

Text added:

```
Tell it
Check it
Send it
Unsaved, you’re offline
Save and close
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week from 9876543210 and read out his PAN, ABCPK1234F. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
You
Just now
Edit
Drafted a title: “Investors call to ask why a redemption was rejected”.
Sorted it under Investor service, affecting investors and KFin teams.
Noted how often: about 40 calls a day at one branch.
Marked it as saves time and saves cost.
Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10.
Found 2 similar ideas from colleagues. You can team up on the next step.
Your draft is ready. Add a detail, or check it.
Add to your draft
Working through your words. You can already add more.
Updating
From your first sentence.
Change
the title
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
About 40 calls a day at one branch
From your words: “about 40 calls a day”
Change
Investors, KFin teams
Suggested because you mentioned investors and the branch.
Change
Saves time, Saves cost
From your words: “about 40 calls a day” and “5 to 10 minutes” each.
Change
Investor service
Suggested because it’s about investors and the SMS they get.
Change
Hidden details
Personal details hidden
Folio number, PAN and phone number
3
2 similar ideas
Colleagues raised something close
Still working through your words.
```

Text removed:

```
What keeps getting in your way, Kavya?
​
Describe the problem
Tap to start speaking
Not recording until you do
Say it in whichever language feels most natural to you.
A step customers keep calling about
Something we redo by hand every month
A screen that asks for the same thing twice
Forms as you write
Your title appears here
Waiting for your words
Waiting for your words
Waiting for your words
Waiting for your words
Your draft needs a little more first.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Save and close | href=Home.dc.html |
| button | Edit | type=button |
| textarea | Add a detail, like how often it happens or what you tried |  |
| button | Speak instead | type=button, pressed=false |
| button | Add to your draft | type=button |
| button | Change the title | type=button, expanded=false |
| button | Change How often | type=button, expanded=false |
| button | Change Who it affects | type=button, expanded=false |
| button | Change What it’s worth | type=button, expanded=false |
| button | Change Area | type=button, expanded=false |
| button | Personal details hidden Folio number, PAN and phone number 3 | type=button, expanded=false |
| button | 2 similar ideas Colleagues raised something close | type=button, expanded=false |

## State: `state=Existing draft prompt`

Screenshot: `reference/shots/Compose__state-existing-draft-prompt.jpg`

Announced (role=alert or status): status: Saves as you type // status: Forms as you write

Text added:

```
Saves as you type
Save and close
You have a draft from Friday: Distributors can’t see why an SIP registration is stuck.
Last saved on your phone, 8:42 pm. Continue it here, or start a new one below.
Continue that draft
Start a new one
```

Text removed:

```
What keeps getting in your way, Kavya?
Tap to start speaking
Not recording until you do
A step customers keep calling about
Something we redo by hand every month
A screen that asks for the same thing twice
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Save and close | href=Home.dc.html |
| button | Continue that draft | type=button |
| button | Start a new one | type=button |

## State: `state=Forwarded from email`

Screenshot: `reference/shots/Compose__state-forwarded-from-email.jpg`

Announced (role=alert or status): status: Saved at 1:38 pm // status: Updating

Text added:

```
Tell it
Check it
Send it
Saved at 1:38 pm
Save and close
From your email, today at 9:14 am: “Fwd: R07 rejections again”
We turned it into this draft. Nothing has been sent.
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week from 9876543210 and read out his PAN, ABCPK1234F. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
You
From your email, 9:14 am
Edit
Turned your email into a draft. Nothing has been sent.
Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10.
Add to your draft
Working through your words. You can already add more.
Updating
Building your draft
1 of 6 ready, about 2 seconds left
Updating
Updating
Updating
Investor service
Suggested because it’s about investors and the SMS they get.
Change
Hidden details
Personal details hidden
Folio number, PAN and phone number
3
Still working through your words.
```

Text removed:

```
What keeps getting in your way, Kavya?
​
Describe the problem
Tap to start speaking
Not recording until you do
Say it in whichever language feels most natural to you.
A step customers keep calling about
Something we redo by hand every month
A screen that asks for the same thing twice
Forms as you write
Your title appears here
Waiting for your words
Waiting for your words
Waiting for your words
Waiting for your words
Your draft needs a little more first.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Save and close | href=Home.dc.html |
| button | Edit | type=button |
| textarea | Add a detail, like how often it happens or what you tried |  |
| button | Speak instead | type=button, pressed=false |
| button | Add to your draft | type=button |
| button | Change Area | type=button, expanded=false |
| button | Personal details hidden Folio number, PAN and phone number 3 | type=button, expanded=false |

## State: `state=Follow-ups queued`

Screenshot: `reference/shots/Compose__state-follow-ups-queued.jpg`

Announced (role=alert or status): status: Saved at 1:38 pm // status: Updating

Text added:

```
Tell it
Check it
Send it
Saved at 1:38 pm
Save and close
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week from 9876543210 and read out his PAN, ABCPK1234F. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
You
Just now
Edit
Drafted a title: “Investors call to ask why a redemption was rejected”.
Sorted it under Investor service, affecting investors and KFin teams.
Noted how often: about 40 calls a day at one branch.
Marked it as saves time and saves cost.
Hid 3 personal details from everyone but you: Folio ••••89, PAN ••••4F, Phone ••••10.
Found 2 similar ideas from colleagues. You can team up on the next step.
It also happens with SIP rejections, about 10 a day.
Read what you added.
It fits under “How often”.
Updating your draft on the right.
We tried a branch FAQ sheet, but investors still call.
Queued. Goes in once the one above is done.
Add to your draft
Adding your last detail. Keep typing, anything new waits its turn.
Updating
From your first sentence.
Change
the title
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
About 40 calls a day at one branch
From your words: “about 40 calls a day”
Change
Investors, KFin teams
Suggested because you mentioned investors and the branch.
Change
Saves time, Saves cost
From your words: “about 40 calls a day” and “5 to 10 minutes” each.
Change
Investor service
Suggested because it’s about investors and the SMS they get.
Change
Hidden details
Personal details hidden
Folio number, PAN and phone number
3
2 similar ideas
Colleagues raised something close
Adding your last detail.
```

Text removed:

```
What keeps getting in your way, Kavya?
​
Describe the problem
Tap to start speaking
Not recording until you do
Say it in whichever language feels most natural to you.
A step customers keep calling about
Something we redo by hand every month
A screen that asks for the same thing twice
Forms as you write
Your title appears here
Waiting for your words
Waiting for your words
Waiting for your words
Waiting for your words
Your draft needs a little more first.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Save and close | href=Home.dc.html |
| button | Edit | type=button |
| textarea | Add a detail, like how often it happens or what you tried |  |
| button | Speak instead | type=button, pressed=false |
| button | Queue it for your draft | type=button |
| button | Change the title | type=button, expanded=false |
| button | Change How often | type=button, expanded=false |
| button | Change Who it affects | type=button, expanded=false |
| button | Change What it’s worth | type=button, expanded=false |
| button | Change Area | type=button, expanded=false |
| button | Personal details hidden Folio number, PAN and phone number 3 | type=button, expanded=false |
| button | 2 similar ideas Colleagues raised something close | type=button, expanded=false |

## State: `simulatorS1=Interview`

Screenshot: `reference/shots/Compose__simulators1-interview.jpg`

Announced (role=alert or status): status: Forms as you write

Text added:

```
Tell it in your words first. Then three short questions, each one skippable.
How often does it happen?
Who feels it most?
Any rough size?
```

Text removed:

```
Your title appears here
How often
Waiting for your words
Who it affects
Waiting for your words
What it’s worth
Waiting for your words
Area
Waiting for your words
```


## State: `hidden=One`

Screenshot: `reference/shots/Compose__hidden-one.jpg`

Announced (role=alert or status): status: Forms as you write

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `loader=Slow similar ideas`

Screenshot: `reference/shots/Compose__loader-slow-similar-ideas.jpg`

Announced (role=alert or status): status: Forms as you write

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `loader=Held for review`

Screenshot: `reference/shots/Compose__loader-held-for-review.jpg`

Announced (role=alert or status): status: Forms as you write

Text is the same as the default state (the difference is visual or in timing; see the screenshot).
