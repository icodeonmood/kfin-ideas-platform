# Answer: copy and controls per state

Generated from the prototype board `reference/prototype/Answer.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Answer.jpg`

Headings: H1: Answer the review desk; H2: 2 Is the 40 calls a day at one branch, or across Hyderabad?

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
Home
Answer the review desk
Meera from the review desk has 3 questions about "Investors call to ask why a redemption was rejected". Answer them one at a time. Skip any you can’t answer yet and come back before you send.
3 days left to answer
Answer by Thursday 19 November, 6 pm
Question 1
Question 2
Question 3
Check and send
1 of 3 answered
Meera from the review desk asked, today 11:20 am
Added to
How often
2
Is the 40 calls a day at one branch, or across Hyderabad?
Your answer to question 2
Press Enter to go on. Shift + Enter adds a new line.
Back
Skip for now
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
| a | Home | href=Home.dc.html |
| button | Question 1, answered | type=button, disabled=false |
| button | Question 2, not answered yet | type=button, disabled=false |
| button | Question 3, not answered yet | type=button, disabled=false |
| button | Check your answers and send | type=button, disabled=false |
| textarea | Type your answer, or tap the mic and say it |  |
| button | Attach files to this answer | type=button |
| button | Say your answer | type=button, pressed=false |
| button | Back | type=button |
| button | Skip for now | type=button, disabled=false |

## State: `state=Checking`

Screenshot: `reference/shots/Answer__state-checking.jpg`

Text added:

```
Check your answers
1
Is it mostly R07, or all rejection codes?
Added to The problem
All of them. R07 is about half the calls. R03 and R12 make up most of the rest.
Change
Added to How often
Not answered. It stays open until the deadline.
Change
3
Can you add a screenshot of the SMS, with the folio hidden?
Added to Attached
Not answered. It stays open until the deadline.
Change
Send 1 answer to Meera
```

Text removed:

```
Meera from the review desk asked, today 11:20 am
Added to
How often
Your answer to question 2
Press Enter to go on. Shift + Enter adds a new line.
Skip for now
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Change your answer to question 1 | type=button |
| button | Change your answer to question 2 | type=button |
| button | Change your answer to question 3 | type=button |
| button | Send 1 answer to Meera | type=button, disabled=false |

## State: `state=Sent`

Screenshot: `reference/shots/Answer__state-sent.jpg`

Announced (role=alert or status): status: Sent to Meera, 4:32 pm Your answers are with the review desk Each answer is added to its part of your idea and posted in your conversation with the review desk. Meera decides by Friday 20 November, an

Text added:

```
Meera from the review desk had 3 questions about "Investors call to ask why a redemption was rejected". You answered all 3.
Answered with 3 days to spare
Meera decides by Friday 20 November
Sent
3 of 3 answered
Sent to Meera, 4:32 pm
Your answers are with the review desk
Each answer is added to its part of your idea and posted in your conversation with the review desk. Meera decides by Friday 20 November, and her decision comes to your Inbox.
1
Is it mostly R07, or all rejection codes?
Added to The problem
All of them. R07 is about half the calls. R03 and R12 make up most of the rest.
Added to How often
That’s our Hyderabad branch alone. Vizag and Vijayawada say they get about the same.
3
Can you add a screenshot of the SMS, with the folio hidden?
Added to Attached
Two screenshots attached, folio hidden.
See the conversation
See your idea
```

Text removed:

```
Meera from the review desk has 3 questions about "Investors call to ask why a redemption was rejected". Answer them one at a time. Skip any you can’t answer yet and come back before you send.
3 days left to answer
Answer by Thursday 19 November, 6 pm
Check and send
1 of 3 answered
Meera from the review desk asked, today 11:20 am
Added to
How often
Your answer to question 2
Press Enter to go on. Shift + Enter adds a new line.
Back
Skip for now
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Question 1, answered | type=button, disabled=true |
| button | Question 2, answered | type=button, disabled=true |
| button | Question 3, answered | type=button, disabled=true |
| button | Sent | type=button, disabled=true |
| a | See the conversation | href=Messages.dc.html |
| a | See your idea | href=Status.dc.html |

## State: `timeToAnswer=Under a day`

Screenshot: `reference/shots/Answer__timetoanswer-under-a-day.jpg`

Text added:

```
07:38 left to answer
Answer by 7 pm today
```

Text removed:

```
3 days left to answer
Answer by Thursday 19 November, 6 pm
```

