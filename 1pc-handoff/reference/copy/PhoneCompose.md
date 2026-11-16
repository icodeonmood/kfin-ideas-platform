# PhoneCompose: copy and controls per state

Generated from the prototype board `reference/prototype/PhoneCompose.dc.html`, rendered at 390px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/PhoneCompose.jpg`

Headings: H1: What’s getting in your way?

### Text, top to bottom

```
Save and close
Saved at 1:40 pm
Step 1 of 3 Tell it
Next: check it
What’s getting in your way?
What happens, who it affects, how often. Any language. At least 30 characters, and no fix needed.
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week from 9876543210 and read out his PAN, ABCPK1234F. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
Describe the problem
Enough to work with
Nothing is shared until you send it. Saved as you go, here and on your computer.
Investors call to ask why a redemption was rejected
Hid 3 details, 3 sortings, 2 similar ideas
Move to Review
```

### Controls

| Element | Label | Attributes |
|---|---|---|
| a | Save and close | href=PhoneHome.dc.html |
| textarea | For example: the rejection SMS only gives a code, so investors call the branch to ask what it means. |  |
| button | Investors call to ask why a redemption was rejected Hid 3 details, 3 sortings, 2 similar ideas | type=button, expanded=false |
| button | Say it instead | type=button |
| a | Move to Review | href=PhoneReview.dc.html |

## State: `state=Empty`

Screenshot: `reference/shots/PhoneCompose__state-empty.jpg`

Announced (role=alert or status): status: Saves as you type

Text added:

```
Saves as you type
​
30 more characters
Every day I have to…
Investors keep calling us about…
We find out too late when…
It takes too long to…
Your draft
Forms here as you write. Tap to see it.
```

Text removed:

```
Saved at 1:40 pm
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week from 9876543210 and read out his PAN, ABCPK1234F. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
Enough to work with
Investors call to ask why a redemption was rejected
Hid 3 details, 3 sortings, 2 similar ideas
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Every day I have to… | type=button |
| button | Investors keep calling us about… | type=button |
| button | We find out too late when… | type=button |
| button | It takes too long to… | type=button |
| button | Your draft Forms here as you write. Tap to see it. | type=button, expanded=false |
| button | Move to Review | type=button, disabled=true |

## State: `state=Typing, draft forming`

Screenshot: `reference/shots/PhoneCompose__state-typing-draft-forming.jpg`

Announced (role=alert or status): status: Saving…

Text added:

```
Saving…
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week.​
Updating your draft
```

Text removed:

```
Saved at 1:40 pm
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week from 9876543210 and read out his PAN, ABCPK1234F. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
Hid 3 details, 3 sortings, 2 similar ideas
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Investors call to ask why a redemption was rejected Updating your draft | type=button, expanded=false |

## State: `state=Speaking`

Screenshot: `reference/shots/PhoneCompose__state-speaking.jpg`

Announced (role=alert or status): status: Saving… // status: When a redemption is rejected, the SMS to the investor only says Rejected, R07. Nobody knows what R07 means, so they call the

Text added:

```
Saving…
When a redemption is rejected, the SMS to the investor only says Rejected, R07. Nobody knows what R07 means, so they call the
Listening. Up to 3 minutes.
Updating your draft
Type instead
Stop, 0:14
```

Text removed:

```
Saved at 1:40 pm
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week from 9876543210 and read out his PAN, ABCPK1234F. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
Describe the problem
Enough to work with
Hid 3 details, 3 sortings, 2 similar ideas
Move to Review
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Investors call to ask why a redemption was rejected Updating your draft | type=button, expanded=false |
| button | Type instead | type=button |
| button | Stop, 0:14 | type=button |

## State: `state=Mic blocked`

Screenshot: `reference/shots/PhoneCompose__state-mic-blocked.jpg`

Announced (role=alert or status): status: Saves as you type // alert: The microphone is off for this app. Turn it on in your phone’s settings, or type above. Your words save as you go.

Text added:

```
Saves as you type
​
The microphone is off for this app.
Turn it on in your phone’s settings, or type above. Your words save as you go.
30 more characters
Every day I have to…
Investors keep calling us about…
We find out too late when…
It takes too long to…
Your draft
Forms here as you write. Tap to see it.
```

Text removed:

```
Saved at 1:40 pm
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week from 9876543210 and read out his PAN, ABCPK1234F. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
Enough to work with
Investors call to ask why a redemption was rejected
Hid 3 details, 3 sortings, 2 similar ideas
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Every day I have to… | type=button |
| button | Investors keep calling us about… | type=button |
| button | We find out too late when… | type=button |
| button | It takes too long to… | type=button |
| button | Your draft Forms here as you write. Tap to see it. | type=button, expanded=false |
| button | Microphone blocked | type=button |
| button | Move to Review | type=button, disabled=true |

## State: `state=Offline`

Screenshot: `reference/shots/PhoneCompose__state-offline.jpg`

Announced (role=alert or status): status: Unsaved, you’re offline

Text added:

```
Unsaved, you’re offline
Paused while you’re offline
```

Text removed:

```
Saved at 1:40 pm
Hid 3 details, 3 sortings, 2 similar ideas
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Investors call to ask why a redemption was rejected Paused while you’re offline | type=button, expanded=false |

## State: `state=Existing draft prompt`

Screenshot: `reference/shots/PhoneCompose__state-existing-draft-prompt.jpg`

Announced (role=alert or status): status: Saves as you type

Text added:

```
Saves as you type
You have a draft from Friday: Distributors can’t see why an SIP registration is stuck.
Saved on this phone, 8:42 pm.
Continue it
Start a new one
​
30 more characters
Your draft
Forms here as you write. Tap to see it.
```

Text removed:

```
Saved at 1:40 pm
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week from 9876543210 and read out his PAN, ABCPK1234F. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
Enough to work with
Investors call to ask why a redemption was rejected
Hid 3 details, 3 sortings, 2 similar ideas
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Continue it | type=button |
| button | Start a new one | type=button |
| button | Your draft Forms here as you write. Tap to see it. | type=button, expanded=false |
| button | Move to Review | type=button, disabled=true |

## State: `state=Forwarded from email`

Screenshot: `reference/shots/PhoneCompose__state-forwarded-from-email.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm

Text added:

```
From your email, 9:14 am: “Fwd: R07 rejections again”
We made it into a draft. Nothing has been sent.
Check the draft from your email
The words from your email. Change anything, then review and submit.
```

Text removed:

```
What’s getting in your way?
What happens, who it affects, how often. Any language. At least 30 characters, and no fix needed.
```


## State: `simulatorS1=Interview`

Screenshot: `reference/shots/PhoneCompose__simulators1-interview.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm // status: Up to date

Text added:

```
3 quick questions, then your draft
Up to date
Done
So far we hid 3 personal details, suggested 3 sortings and found 2 similar ideas.
Question 1 of 3. Skip any of them.
How often does it happen, roughly?
Use “About 40 calls a day at one branch”
Your answer
Next question
Skip this one
```

Text removed:

```
Hid 3 details, 3 sortings, 2 similar ideas
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Close the draft | type=button |
| button | Investors call to ask why a redemption was rejected 3 quick questions, then your draft | type=button, expanded=true |
| button | Done | type=button |
| button | Use “About 40 calls a day at one branch” | type=button |
| input | For example, about 20 times a week | type=text |
| button | Next question | type=button |
| button | Skip this one | type=button |

## State: `simulatorS3=Voice first`

Screenshot: `reference/shots/PhoneCompose__simulators3-voice-first.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `hidden=One`

Screenshot: `reference/shots/PhoneCompose__hidden-one.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm

Text added:

```
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
Hid 1 detail, 3 sortings, 2 similar ideas
```

Text removed:

```
When a redemption is rejected, the SMS to the investor only says "Rejected, R07". Nobody knows what R07 means, so they call the branch. One investor, folio 1234567/89, called three times last week from 9876543210 and read out his PAN, ABCPK1234F. Our branch takes about 40 calls a day like this, and each one takes 5 to 10 minutes.​
Hid 3 details, 3 sortings, 2 similar ideas
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Investors call to ask why a redemption was rejected Hid 1 detail, 3 sortings, 2 similar ideas | type=button, expanded=false |

## State: `loader=Slow similar ideas`

Screenshot: `reference/shots/PhoneCompose__loader-slow-similar-ideas.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm

Text is the same as the default state (the difference is visual or in timing; see the screenshot).

## State: `loader=Held for review`

Screenshot: `reference/shots/PhoneCompose__loader-held-for-review.jpg`

Announced (role=alert or status): status: Saved at 1:40 pm

Text added:

```
Building your draft
2 of 6 ready, about 2 seconds left
```

Text removed:

```
Investors call to ask why a redemption was rejected
Hid 3 details, 3 sortings, 2 similar ideas
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Building your draft 2 of 6 ready, about 2 seconds left | type=button, expanded=false |
| button | Move to Review | type=button, disabled=true |
