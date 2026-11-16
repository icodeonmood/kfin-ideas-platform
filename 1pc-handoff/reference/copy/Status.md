# Status: copy and controls per state

Generated from the prototype board `reference/prototype/Status.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Status.jpg`

Headings: H1: Investors call to ask why a redemption was rejected; H2: Where it is; H2: What you shared; H2: You and the review desk; H2: Colleagues on something similar

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
My ideas
/
IDEA-2026-001481
With the review desk
Shared 14-Nov-26
Withdraw
Investors call to ask why a redemption was rejected
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email when anything changes.
Where it is
Shared
, done
Today, 10:05 am
Checked and matched
, done
Personal details hidden, 2 similar ideas found
Reviewed
, now
By Friday 20 November
Now
Built
, to come
If it’s picked
Shipped
, to come
Then we measure what changed
Open to changes until Tuesday 17 November. Edit or withdraw it any time before the review desk opens it. We tell you on Teams and by email when anything moves.
3 days left
What you shared
If the review desk puts it on the Wall, everyone at KFintech sees this short summary. Your own words stay with you and the review desk.
The problem
The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch. One branch takes about 40 of these calls a day, at 5 to 10 minutes each.
How often
About 40 calls a day at one branch
Who it affects
Investors, KFin teams
What it’s worth
Saves time and cost
Area
Investor service
Hidden
Folio ••••89
Phone ••••10
+2 more
Hidden from everyone
Attached
JPG
sms-on-investor-phone.jpg
Screenshot, 1.2 MB
Checked
View
PDF
branch-call-log-nov.pdf
PDF, 2 pages, 140 KB
Checked
View
Your fix
Send the reason in plain words in the SMS, with a link to what to do next. Map each rejection code, such as R07, to one sentence an investor understands, and add the branch helpline for anything that sentence can’t answer. Start with the five codes behind most calls, then cover the rest. Rough size: 70 to 150 hours and about ₹25,000 saved a month.
Read the full fix
You and the review desk
No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we tell you on Teams.
Colleagues on something similar
Matched when you shared. Team up to ask to join their crew, and bring this idea along if you like.
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
| a | My ideas | href=MyIdeas.dc.html |
| a | Edit it | href=Edit.dc.html |
| button | Withdraw | type=button |
| button | See all 4 hidden details | type=button, popup=dialog |
| button | View sms-on-investor-phone.jpg, opens a full preview | type=button, popup=dialog |
| button | View branch-call-log-nov.pdf, opens a full preview | type=button, popup=dialog |
| button | Read the full fix | type=button, popup=dialog |
| a | Rejection SMS codes confuse investors | href=Idea.dc.html |
| button | Preview Rejection SMS codes confuse investors | type=button, popup=dialog |
| button | Team up on Rejection SMS codes confuse investors | type=button |
| button | Preview No script for calls about rejections | type=button, popup=dialog |
| button | Team up on No script for calls about rejections | type=button |

## State: `state=Questions from the review desk`

Screenshot: `reference/shots/Status__state-questions-from-the-review-desk.jpg`

Text added:

```
My ideas, Needs you
Needs you
MI
Meera from the review desk, Monday 16 November, 11:20 am
Meera has 3 questions for you
1
Is it mostly R07, or all rejection codes?
Answer goes to
Is the 40 calls a day at one branch, or across Hyderabad?
Answer goes to
3
Can you add a screenshot of the SMS, with the folio hidden?
Answer goes to
Answer by Thursday 19 November, 6 pm. One at a time, typed or spoken.
Answer the questions
Saturday 14 November
3 questions for you since Monday 16 November
Open the conversation
The review desk opened it on Monday 16 November, so the idea itself can’t be changed now. Write to them in the conversation.
MI
Meera from the review desk, Monday 16 November, 11:20 am
I have 3 questions about your idea.
```

Text removed:

```
My ideas
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email when anything changes.
Today, 10:05 am
By Friday 20 November
Open to changes until Tuesday 17 November. Edit or withdraw it any time before the review desk opens it. We tell you on Teams and by email when anything moves.
No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we tell you on Teams.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | My ideas, Needs you | href=MyIdeas.dc.html |
| a | Answer the questions | href=Answer.dc.html |
| a | Open the conversation | href=Messages.dc.html |

## State: `state=Answers sent`

Screenshot: `reference/shots/Status__state-answers-sent.jpg`

Text added:

```
Sent. Meera has your answers.
Each answer was added to its part of your idea, under What you shared. The review desk decides by Friday 20 November, and you hear in your Inbox, on Teams and by email.
Saturday 14 November
Meera has your answers. By Friday 20 November
Open the conversation
The review desk opened it on Monday 16 November, so the idea itself can’t be changed now. Write to them in the conversation.
MI
Meera from the review desk, Monday 16 November, 11:20 am
I have 3 questions about your idea.
1
Is it mostly R07, or all rejection codes?
Is the 40 calls a day at one branch, or across Hyderabad?
3
Can you add a screenshot of the SMS, with the folio hidden?
You, Monday 16 November, 4:32 pm, from Answer
Answered all 3. Each answer was added to its part of the idea.
Write to the review desk
From your answer to Meera, Monday 16 November
All of them. R07 is about half the calls. R03 and R12 make up most of the rest.
From your answer to Meera, Monday 16 November
That’s our Hyderabad branch alone. Vizag and Vijayawada say they get about the same.
From your answer to Meera, Monday 16 November
Two more screenshots of the SMS, rejection-sms-1.png and rejection-sms-2.png, folio hidden.
```

Text removed:

```
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email when anything changes.
Today, 10:05 am
By Friday 20 November
Open to changes until Tuesday 17 November. Edit or withdraw it any time before the review desk opens it. We tell you on Teams and by email when anything moves.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we tell you on Teams.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Open the conversation | href=Messages.dc.html |
| a | Write to the review desk | href=Messages.dc.html |

## State: `state=Picked`

Screenshot: `reference/shots/Status__state-picked.jpg`

Text added:

```
My ideas, Picked and building
Picked. A team is being chosen to build it.
Meera from the review desk picked it on Monday 16 November and joined it with IDEA-2026-001412 from Hyderabad, so one team builds one fix. The build team is chosen by Friday 27 November.
The Ones Committee can review this decision until Wednesday 16 December. If they change it, their note comes to your Inbox. After that, it stands.
Ask to join the build team
Saturday 14 November
Done in 40 seconds
Picked, Monday 16 November
Team chosen by Friday 27 November
Open the conversation
The review desk has decided. The full conversation, with every answer, is one tap away.
MI
Meera from the review desk, Monday 16 November, 11:20 am
I have 3 questions about your idea.
1
Is it mostly R07, or all rejection codes?
Is the 40 calls a day at one branch, or across Hyderabad?
3
Can you add a screenshot of the SMS, with the folio hidden?
You, Monday 16 November, 4:32 pm, from Answer
Answered all 3. Each answer was added to its part of the idea.
MI
Meera from the review desk, Monday 16 November, 4:58 pm
Picked. A clear problem, a real number and a simple fix. We’ve joined it with IDEA-2026-001412, which found the same calls in Hyderabad, so one team builds one fix.
Write to the review desk
From your answer to Meera, Monday 16 November
All of them. R07 is about half the calls. R03 and R12 make up most of the rest.
From your answer to Meera, Monday 16 November
That’s our Hyderabad branch alone. Vizag and Vijayawada say they get about the same.
From your answer to Meera, Monday 16 November
Two more screenshots of the SMS, rejection-sms-1.png and rejection-sms-2.png, folio hidden.
```

Text removed:

```
My ideas
With the review desk
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email when anything changes.
Today, 10:05 am
Personal details hidden, 2 similar ideas found
By Friday 20 November
If it’s picked
Open to changes until Tuesday 17 November. Edit or withdraw it any time before the review desk opens it. We tell you on Teams and by email when anything moves.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we tell you on Teams.
Rejection SMS codes confuse investors
IDEA-2026-001412, Investor service, Hyderabad
With the review desk
Close match: same SMS, same calls
RN
AS
PK
4 colleagues on it
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | My ideas, Picked and building | href=MyIdeas.dc.html |
| button | Ask to join the build team | type=button |
| a | Open the conversation | href=Messages.dc.html |
| a | Write to the review desk | href=Messages.dc.html |

## State: `state=Not now`

Screenshot: `reference/shots/Status__state-not-now.jpg`

Text added:

```
Not now
Not now. The review desk looks at it again on Tuesday 16 February.
Right problem, wrong time: the SMS templates are frozen until the platform upgrade in January. Your idea stays open, with your answers and anyone who teams up, and comes back to the review desk first thing in February. Meera’s full reason is below.
The Ones Committee can review this decision until Wednesday 16 December. If they change it, their note comes to your Inbox. After that, it stands.
Saturday 14 November
Done in 40 seconds
Not now, Monday 16 November
Looked at again on Tuesday 16 February
Open the conversation
The review desk has decided. The full conversation, with every answer, is one tap away.
MI
Meera from the review desk, Monday 16 November, 11:20 am
I have 3 questions about your idea.
1
Is it mostly R07, or all rejection codes?
Is the 40 calls a day at one branch, or across Hyderabad?
3
Can you add a screenshot of the SMS, with the folio hidden?
You, Monday 16 November, 4:32 pm, from Answer
Answered all 3. Each answer was added to its part of the idea.
MI
Meera from the review desk, Monday 16 November, 4:58 pm
Not now. The SMS templates are frozen until the platform upgrade in January. We’ll look at it again first thing after, on Tuesday 16 February, with your answers.
Write to the review desk
From your answer to Meera, Monday 16 November
All of them. R07 is about half the calls. R03 and R12 make up most of the rest.
From your answer to Meera, Monday 16 November
That’s our Hyderabad branch alone. Vizag and Vijayawada say they get about the same.
From your answer to Meera, Monday 16 November
Two more screenshots of the SMS, rejection-sms-1.png and rejection-sms-2.png, folio hidden.
```

Text removed:

```
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email when anything changes.
Today, 10:05 am
Personal details hidden, 2 similar ideas found
, now
By Friday 20 November
Now
If it’s picked
Open to changes until Tuesday 17 November. Edit or withdraw it any time before the review desk opens it. We tell you on Teams and by email when anything moves.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we tell you on Teams.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Open the conversation | href=Messages.dc.html |
| a | Write to the review desk | href=Messages.dc.html |

## State: `state=Not picked, with the reason`

Screenshot: `reference/shots/Status__state-not-picked-with-the-reason.jpg`

Text added:

```
My ideas, Closed
Not picked
Not picked on its own. Your words carry on in IDEA-2026-001412.
It’s the same problem as an idea the review desk is taking forward. Your words and your figure of 40 calls a day were added to it, with credit to you, and you’ll get its updates. Meera’s full reason is below.
The Ones Committee can review this decision until Wednesday 16 December. If they change it, their note comes to your Inbox. After that, it stands.
Open IDEA-2026-001412
Saturday 14 November
Done in 40 seconds
Not picked, Monday 16 November
, not going ahead
Not going ahead on its own
, not going ahead
Carries on in IDEA-2026-001412
Open the conversation
The review desk has decided. The full conversation, with every answer, is one tap away.
MI
Meera from the review desk, Monday 16 November, 11:20 am
I have 3 questions about your idea.
1
Is it mostly R07, or all rejection codes?
Is the 40 calls a day at one branch, or across Hyderabad?
3
Can you add a screenshot of the SMS, with the folio hidden?
You, Monday 16 November, 4:32 pm, from Answer
Answered all 3. Each answer was added to its part of the idea.
MI
Meera from the review desk, Monday 16 November, 4:58 pm
Not picked on its own. It’s the same problem as IDEA-2026-001412, which we’re taking forward. We’ve added your words and your figure of 40 calls a day to it, with credit to you.
Write to the review desk
From your answer to Meera, Monday 16 November
All of them. R07 is about half the calls. R03 and R12 make up most of the rest.
From your answer to Meera, Monday 16 November
That’s our Hyderabad branch alone. Vizag and Vijayawada say they get about the same.
From your answer to Meera, Monday 16 November
Two more screenshots of the SMS, rejection-sms-1.png and rejection-sms-2.png, folio hidden.
Your words were added here
```

Text removed:

```
My ideas
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email when anything changes.
Today, 10:05 am
Personal details hidden, 2 similar ideas found
, now
By Friday 20 November
Now
, to come
If it’s picked
, to come
Then we measure what changed
Open to changes until Tuesday 17 November. Edit or withdraw it any time before the review desk opens it. We tell you on Teams and by email when anything moves.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we tell you on Teams.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | My ideas, Closed | href=MyIdeas.dc.html |
| a | Open IDEA-2026-001412 | href=Idea.dc.html |
| a | Open the conversation | href=Messages.dc.html |
| a | Write to the review desk | href=Messages.dc.html |

## State: `state=Reversed by the Ones Committee`

Screenshot: `reference/shots/Status__state-reversed-by-the-ones-committee.jpg`

Text added:

```
Not now
RM
Rohan Mehta from the Ones Committee, Tuesday 24 November, 5:40 pm
The Ones Committee changed the decision to not now
“The SMS templates are frozen until the platform upgrade in January, so a team picked now would wait two months. We’ve moved it to not now, and it comes back first in February. The review desk’s pick stays on record.”
The committee’s note to you
Was: Picked
by Meera from the review desk, Monday 16 November
This is final. It comes back to the review desk on Tuesday 16 February 2027, with your answers and crew.
Saturday 14 November
Done in 40 seconds
Picked, then moved to not now by the Ones Committee
Looked at again on Tuesday 16 February
Open the conversation
The Ones Committee has the last word on this decision. The full conversation is one tap away.
You, Monday 16 November, 4:32 pm, from Answer
Answered all 3. Each answer was added to its part of the idea.
MI
Meera from the review desk, Monday 16 November, 4:58 pm
Picked. A clear problem, a real number and a simple fix. We’ve joined it with IDEA-2026-001412, which found the same calls in Hyderabad, so one team builds one fix.
RM
Rohan Mehta from the Ones Committee, Tuesday 24 November, 5:40 pm
We’ve moved it to not now: the SMS templates are frozen until January. It comes back first in February.
Write to the review desk
From your answer to Meera, Monday 16 November
All of them. R07 is about half the calls. R03 and R12 make up most of the rest.
From your answer to Meera, Monday 16 November
That’s our Hyderabad branch alone. Vizag and Vijayawada say they get about the same.
From your answer to Meera, Monday 16 November
Two more screenshots of the SMS, rejection-sms-1.png and rejection-sms-2.png, folio hidden.
```

Text removed:

```
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email when anything changes.
Today, 10:05 am
Personal details hidden, 2 similar ideas found
, now
By Friday 20 November
Now
If it’s picked
Open to changes until Tuesday 17 November. Edit or withdraw it any time before the review desk opens it. We tell you on Teams and by email when anything moves.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we tell you on Teams.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Open the conversation | href=Messages.dc.html |
| a | Write to the review desk | href=Messages.dc.html |

## State: `state=Withdrawn`

Screenshot: `reference/shots/Status__state-withdrawn.jpg`

Text added:

```
My ideas, Closed
Withdrawn
Withdrawn. It’s back in your drafts.
Nobody else can see it now. No reason given. Restoring shares it again as it was, and the review desk gets it back.
Restore it
Saturday 14 November
Done in 40 seconds
, not going ahead
Withdrawn before review
, not going ahead
, not going ahead
```

Text removed:

```
My ideas
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email when anything changes.
Today, 10:05 am
Personal details hidden, 2 similar ideas found
, now
By Friday 20 November
Now
, to come
If it’s picked
, to come
Then we measure what changed
Open to changes until Tuesday 17 November. Edit or withdraw it any time before the review desk opens it. We tell you on Teams and by email when anything moves.
3 days left
You and the review desk
No messages yet. If the review desk has a question, it shows up here and in your Inbox, and we tell you on Teams.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | My ideas, Closed | href=MyIdeas.dc.html |
| button | Restore it | type=button |

## State: `fix=Without a fix`

Screenshot: `reference/shots/Status__fix-without-a-fix.jpg`

Text added:

```
No fix added. Add one until Tuesday 17 November
```

Text removed:

```
Send the reason in plain words in the SMS, with a link to what to do next. Map each rejection code, such as R07, to one sentence an investor understands, and add the branch helpline for anything that sentence can’t answer. Start with the five codes behind most calls, then cover the rest. Rough size: 70 to 150 hours and about ₹25,000 saved a month.
Read the full fix
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Add one until Tuesday 17 November | href=Edit.dc.html |

## State: `attached=A screenshot`

Screenshot: `reference/shots/Status__attached-a-screenshot.jpg`

Text added:

```
+1 more
```

Text removed:

```
+2 more
PDF
branch-call-log-nov.pdf
PDF, 2 pages, 140 KB
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | See all 3 hidden details | type=button, popup=dialog |

## State: `attached=None`

Screenshot: `reference/shots/Status__attached-none.jpg`

Text added:

```
+1 more
Nothing attached. Add one until Tuesday 17 November
```

Text removed:

```
+2 more
JPG
sms-on-investor-phone.jpg
Screenshot, 1.2 MB
Checked
View
PDF
branch-call-log-nov.pdf
PDF, 2 pages, 140 KB
Checked
View
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | See all 3 hidden details | type=button, popup=dialog |
| a | Add one until Tuesday 17 November | href=Edit.dc.html |

## State: `hidden=One`

Screenshot: `reference/shots/Status__hidden-one.jpg`

Text added:

```
1 folio number hidden, 2 similar ideas found
```

Text removed:

```
Personal details hidden, 2 similar ideas found
Phone ••••10
+2 more
```

