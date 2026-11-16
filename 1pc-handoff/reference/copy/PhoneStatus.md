# PhoneStatus: copy and controls per state

Generated from the prototype board `reference/prototype/PhoneStatus.dc.html`, rendered at 390px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/PhoneStatus.jpg`

Headings: H1: Investors call to ask why a redemption was rejected; H2: Where it is; H2: Colleagues on something similar

### Text, top to bottom

```
My ideas
IDEA-2026-001481
With the review desk
Withdraw
Investors call to ask why a redemption was rejected
Reference IDEA-2026-001481, shared Saturday 14 November, Investor service
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email.
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
Open to changes until Tuesday 17 November. Edit or withdraw it before the review desk opens it.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox.
What you shared
Colleagues on something similar
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
Home
My ideas
Share
Wall
Inbox
```

### Controls

| Element | Label | Attributes |
|---|---|---|
| a | Back to My ideas | href=PhoneMyIdeas.dc.html |
| button | Copy reference IDEA-2026-001481 | type=button |
| a | Edit it | href=PhoneEdit.dc.html |
| button | Withdraw | type=button |
| summary | What you shared |  |
| button | See all 4 hidden details | type=button, popup=dialog |
| button | View sms-on-investor-phone.jpg, opens a full preview | type=button, popup=dialog |
| button | View branch-call-log-nov.pdf, opens a full preview | type=button, popup=dialog |
| button | (no label) | type=button, popup=dialog |
| a | Rejection SMS codes confuse investors | href=PhoneIdea.dc.html |
| button | Preview Rejection SMS codes confuse investors | type=button, popup=dialog |
| button | Team up on Rejection SMS codes confuse investors | type=button |
| button | Preview No script for calls about rejections | type=button, popup=dialog |
| button | Team up on No script for calls about rejections | type=button |
| a | Home | href=PhoneHome.dc.html |
| a | My ideas | href=PhoneMyIdeas.dc.html |
| a | Share a problem | href=PhoneCompose.dc.html |
| a | Wall | href=PhoneWall.dc.html |
| a | Inbox | href=PhoneInbox.dc.html |

## State: `state=Questions from the review desk`

Screenshot: `reference/shots/PhoneStatus__state-questions-from-the-review-desk.jpg`

Announced (role=alert or status): status: 

Text added:

```
Needs you
Needs you
MI
Meera from the review desk, Monday 16 November, 11:20 am
Meera has 3 questions for you
1
Is it mostly R07, or all rejection codes?
Answer goes to
The problem
2
Is the 40 calls a day at one branch, or across Hyderabad?
Answer goes to
How often
3
Can you add a screenshot of the SMS, with the folio hidden?
Answer goes to
Attached
Answer by Thursday 19 November, 6 pm. One at a time, typed or spoken.
Answer the questions
Saturday 14 November
3 questions for you since Monday 16 November
You and the review desk
Open the conversation
The review desk opened it on Monday 16 November, so the idea itself can’t be changed now. Write to them in the conversation.
MI
Meera from the review desk, Monday 16 November, 11:20 am
I have 3 questions about your idea.
2
```

Text removed:

```
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email.
Today, 10:05 am
By Friday 20 November
Open to changes until Tuesday 17 November. Edit or withdraw it before the review desk opens it.
No messages yet. If the review desk has a question, it shows up here and in your Inbox.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Back to My ideas, Needs you | href=PhoneMyIdeas.dc.html |
| a | Answer the questions | href=PhoneAnswer.dc.html |
| a | Open the conversation | href=PhoneMessages.dc.html |
| a | Inbox, 2 new | href=PhoneInbox.dc.html |

## State: `state=Answers sent`

Screenshot: `reference/shots/PhoneStatus__state-answers-sent.jpg`

Announced (role=alert or status): status: 

Text added:

```
Sent. Meera has your answers.
Each answer was added to its part of your idea, under What you shared. The review desk decides by Friday 20 November, and you hear in your Inbox, on Teams and by email.
Saturday 14 November
Meera has your answers. By Friday 20 November
You and the review desk
Open the conversation
The review desk opened it on Monday 16 November, so the idea itself can’t be changed now. Write to them in the conversation.
MI
Meera from the review desk, Monday 16 November, 11:20 am
I have 3 questions about your idea.
1
Is it mostly R07, or all rejection codes?
2
Is the 40 calls a day at one branch, or across Hyderabad?
3
Can you add a screenshot of the SMS, with the folio hidden?
KM
You, Monday 16 November, 4:32 pm, from Answer
Answered all 3. Each answer was added to its part of the idea.
Write to the review desk
```

Text removed:

```
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email.
Today, 10:05 am
By Friday 20 November
Open to changes until Tuesday 17 November. Edit or withdraw it before the review desk opens it.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Back to My ideas, Closed | href=PhoneMyIdeas.dc.html |
| a | Open the conversation | href=PhoneMessages.dc.html |
| a | Write to the review desk | href=PhoneMessages.dc.html |

## State: `state=Picked`

Screenshot: `reference/shots/PhoneStatus__state-picked.jpg`

Announced (role=alert or status): status: 

Text added:

```
Picked. A team is being chosen to build it.
Meera from the review desk picked it on Monday 16 November and joined it with IDEA-2026-001412 from Hyderabad, so one team builds one fix. The build team is chosen by Friday 27 November.
The Ones Committee can review this decision until Wednesday 16 December. If they change it, their note comes to your Inbox. After that, it stands.
Ask to join the build team
Saturday 14 November
Done in 40 seconds
Picked, Monday 16 November
Team chosen by Friday 27 November
You and the review desk
Open the conversation
The review desk has decided. The full conversation, with every answer, is one tap away.
MI
Meera from the review desk, Monday 16 November, 11:20 am
I have 3 questions about your idea.
1
Is it mostly R07, or all rejection codes?
2
Is the 40 calls a day at one branch, or across Hyderabad?
3
Can you add a screenshot of the SMS, with the folio hidden?
KM
You, Monday 16 November, 4:32 pm, from Answer
Answered all 3. Each answer was added to its part of the idea.
MI
Meera from the review desk, Monday 16 November, 4:58 pm
Picked. A clear problem, a real number and a simple fix. We’ve joined it with IDEA-2026-001412, which found the same calls in Hyderabad, so one team builds one fix.
Write to the review desk
```

Text removed:

```
With the review desk
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email.
Today, 10:05 am
Personal details hidden, 2 similar ideas found
By Friday 20 November
If it’s picked
Open to changes until Tuesday 17 November. Edit or withdraw it before the review desk opens it.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox.
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
| a | Back to My ideas, Picked and building | href=PhoneMyIdeas.dc.html |
| button | Ask to join the build team | type=button |
| a | Open the conversation | href=PhoneMessages.dc.html |
| a | Write to the review desk | href=PhoneMessages.dc.html |

## State: `state=Not now`

Screenshot: `reference/shots/PhoneStatus__state-not-now.jpg`

Announced (role=alert or status): status: 

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
You and the review desk
Open the conversation
The review desk has decided. The full conversation, with every answer, is one tap away.
MI
Meera from the review desk, Monday 16 November, 11:20 am
I have 3 questions about your idea.
1
Is it mostly R07, or all rejection codes?
2
Is the 40 calls a day at one branch, or across Hyderabad?
3
Can you add a screenshot of the SMS, with the folio hidden?
KM
You, Monday 16 November, 4:32 pm, from Answer
Answered all 3. Each answer was added to its part of the idea.
MI
Meera from the review desk, Monday 16 November, 4:58 pm
Not now. The SMS templates are frozen until the platform upgrade in January. We’ll look at it again first thing after, on Tuesday 16 February, with your answers.
Write to the review desk
```

Text removed:

```
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email.
Today, 10:05 am
Personal details hidden, 2 similar ideas found
, now
By Friday 20 November
Now
If it’s picked
Open to changes until Tuesday 17 November. Edit or withdraw it before the review desk opens it.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Back to My ideas, Closed | href=PhoneMyIdeas.dc.html |
| a | Open the conversation | href=PhoneMessages.dc.html |
| a | Write to the review desk | href=PhoneMessages.dc.html |

## State: `state=Not picked, with the reason`

Screenshot: `reference/shots/PhoneStatus__state-not-picked-with-the-reason.jpg`

Announced (role=alert or status): status: 

Text added:

```
Closed
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
You and the review desk
Open the conversation
The review desk has decided. The full conversation, with every answer, is one tap away.
MI
Meera from the review desk, Monday 16 November, 11:20 am
I have 3 questions about your idea.
1
Is it mostly R07, or all rejection codes?
2
Is the 40 calls a day at one branch, or across Hyderabad?
3
Can you add a screenshot of the SMS, with the folio hidden?
KM
You, Monday 16 November, 4:32 pm, from Answer
Answered all 3. Each answer was added to its part of the idea.
MI
Meera from the review desk, Monday 16 November, 4:58 pm
Not picked on its own. It’s the same problem as IDEA-2026-001412, which we’re taking forward. We’ve added your words and your figure of 40 calls a day to it, with credit to you.
Write to the review desk
Your words were added here
```

Text removed:

```
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email.
Today, 10:05 am
Personal details hidden, 2 similar ideas found
, now
By Friday 20 November
Now
, to come
If it’s picked
, to come
Then we measure what changed
Open to changes until Tuesday 17 November. Edit or withdraw it before the review desk opens it.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Back to My ideas, Closed | href=PhoneMyIdeas.dc.html |
| a | Open IDEA-2026-001412 | href=PhoneIdea.dc.html |
| a | Open the conversation | href=PhoneMessages.dc.html |
| a | Write to the review desk | href=PhoneMessages.dc.html |

## State: `state=Reversed by the Ones Committee`

Screenshot: `reference/shots/PhoneStatus__state-reversed-by-the-ones-committee.jpg`

Announced (role=alert or status): status: 

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
You and the review desk
Open the conversation
The Ones Committee has the last word on this decision. The full conversation is one tap away.
KM
You, Monday 16 November, 4:32 pm, from Answer
Answered all 3. Each answer was added to its part of the idea.
MI
Meera from the review desk, Monday 16 November, 4:58 pm
Picked. A clear problem, a real number and a simple fix. We’ve joined it with IDEA-2026-001412, which found the same calls in Hyderabad, so one team builds one fix.
RM
Rohan Mehta from the Ones Committee, Tuesday 24 November, 5:40 pm
We’ve moved it to not now: the SMS templates are frozen until January. It comes back first in February.
Write to the review desk
```

Text removed:

```
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email.
Today, 10:05 am
Personal details hidden, 2 similar ideas found
, now
By Friday 20 November
Now
If it’s picked
Open to changes until Tuesday 17 November. Edit or withdraw it before the review desk opens it.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Back to My ideas, Closed | href=PhoneMyIdeas.dc.html |
| a | Open the conversation | href=PhoneMessages.dc.html |
| a | Write to the review desk | href=PhoneMessages.dc.html |

## State: `state=Withdrawn`

Screenshot: `reference/shots/PhoneStatus__state-withdrawn.jpg`

Announced (role=alert or status): status: 

Text added:

```
Closed
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
Withdraw
The review desk will look at it by Friday 20 November. We’ll tell you on Teams and by email.
Today, 10:05 am
Personal details hidden, 2 similar ideas found
, now
By Friday 20 November
Now
, to come
If it’s picked
, to come
Then we measure what changed
Open to changes until Tuesday 17 November. Edit or withdraw it before the review desk opens it.
3 days left
No messages yet. If the review desk has a question, it shows up here and in your Inbox.
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Back to My ideas, Closed | href=PhoneMyIdeas.dc.html |
| button | Restore it | type=button |

## State: `fix=Without a fix`

Screenshot: `reference/shots/PhoneStatus__fix-without-a-fix.jpg`

Announced (role=alert or status): status: 

Text is the same as the default state (the difference is visual or in timing; see the screenshot).
Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | (no label) | href=PhoneEdit.dc.html |

## State: `attached=A screenshot`

Screenshot: `reference/shots/PhoneStatus__attached-a-screenshot.jpg`

Announced (role=alert or status): status: 

Text is the same as the default state (the difference is visual or in timing; see the screenshot).
Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | See all 3 hidden details | type=button, popup=dialog |

## State: `attached=None`

Screenshot: `reference/shots/PhoneStatus__attached-none.jpg`

Announced (role=alert or status): status: 

Text is the same as the default state (the difference is visual or in timing; see the screenshot).
Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | See all 3 hidden details | type=button, popup=dialog |
| a | (no label) | href=PhoneEdit.dc.html |

## State: `hidden=One`

Screenshot: `reference/shots/PhoneStatus__hidden-one.jpg`

Announced (role=alert or status): status: 

Text added:

```
1 folio number hidden, 2 similar ideas found
```

Text removed:

```
Personal details hidden, 2 similar ideas found
```

