# PhoneComposeResume: copy and controls per state

Generated from the prototype board `reference/prototype/PhoneComposeResume.dc.html`, rendered at 390px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/PhoneComposeResume.jpg`

Headings: H1: What’s getting in your way?

### Text, top to bottom

```
Save and close
Saved at 1:40 pm
Step 1 of 3 Tell it
Next: check it
Picked up where you left off.
Last saved on your phone, Friday 8:42 pm.
Start a new one instead
What’s getting in your way?
What happens, who it affects, how often. Any language. At least 30 characters, and no fix needed.
Distributors ring the branch to ask why an SIP registration is stuck. IRIS shows Pending with no reason, so we raise a ticket and wait two or three days. This happens about 15 times a week at our branch.​
Describe the problem
Enough to work with
Already attached. You can add more on the next step.
sip-pending-screen.jpg
Checked
Nothing is shared until you send it. Saved as you go, here and on your computer.
Distributors can’t see why an SIP registration is stuck
3 sortings, 1 photo attached
Move to Review
```

### Controls

| Element | Label | Attributes |
|---|---|---|
| a | Save and close | href=PhoneHome.dc.html |
| button | Start a new one instead | type=button |
| textarea | For example: the rejection SMS only gives a code, so investors call the branch to ask what it means. |  |
| button | Distributors can’t see why an SIP registration is stuck 3 sortings, 1 photo attached | type=button, expanded=false |
| button | Say it instead | type=button |
| a | Move to Review | href=PhoneReview.dc.html |

## State: `simulatorS1=Interview`

Screenshot: `reference/shots/PhoneComposeResume__simulators1-interview.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `simulatorS3=Voice first`

Screenshot: `reference/shots/PhoneComposeResume__simulators3-voice-first.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `hidden=One`

Screenshot: `reference/shots/PhoneComposeResume__hidden-one.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `loader=Slow similar ideas`

Screenshot: `reference/shots/PhoneComposeResume__loader-slow-similar-ideas.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `loader=Held for review`

Screenshot: `reference/shots/PhoneComposeResume__loader-held-for-review.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm

Text added:

```
Building your draft
2 of 6 ready, about 2 seconds left
```

Text removed:

```
Distributors can’t see why an SIP registration is stuck
3 sortings, 1 photo attached
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Building your draft 2 of 6 ready, about 2 seconds left | type=button, expanded=false |
| button | Move to Review | type=button, disabled=true |
