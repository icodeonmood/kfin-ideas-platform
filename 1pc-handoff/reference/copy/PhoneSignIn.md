# PhoneSignIn: copy and controls per state

Generated from the prototype board `reference/prototype/PhoneSignIn.dc.html`, rendered at 390px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/PhoneSignIn.jpg`

Headings: H1: Sign in to 1% Club

### Text, top to bottom

```
Use single sign-on
Sign in to 1% Club
Use your work email
Send code
```

### Controls

| Element | Label | Attributes |
|---|---|---|
| button | Use single sign-on | type=button |
| input | name@kfintech.com | type=email, inputmode=email, autocomplete=email |
| button | Send code | type=button, disabled=true |

## State: `state=Enter code`

Screenshot: `reference/shots/PhoneSignIn__state-enter-code.jpg`

Text added:

```
Check your email
We sent a 6-digit code to kavya.menon@kfintech.com. It works for 10 minutes. Change email
You can ask for a new code in 0:45.
Not in your inbox? Check Junk, or use single sign-on.
Sign in
```

Text removed:

```
Use single sign-on
Sign in to 1% Club
Use your work email
Send code
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Change email | type=button |
| input | 6-digit code | type=text, invalid=false, maxlength=6, inputmode=numeric, autocomplete=one-time-code |
| button | use single sign-on | type=button |
| button | Sign in | type=button, disabled=true |

## State: `state=Wrong code`

Screenshot: `reference/shots/PhoneSignIn__state-wrong-code.jpg`

Announced (role=alert or status): alert: That code didn’t match. Check the latest email from 1% Club. 2 tries left.

Text added:

```
Check your email
We sent a 6-digit code to kavya.menon@kfintech.com. It works for 10 minutes. Change email
4
8
1
9
0
2
That code didn’t match. Check the latest email from 1% Club. 2 tries left.
You can ask for a new code in 0:45.
Not in your inbox? Check Junk, or use single sign-on.
Sign in
```

Text removed:

```
Use single sign-on
Sign in to 1% Club
Use your work email
Send code
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Change email | type=button |
| input | 6-digit code | type=text, invalid=true, maxlength=6, inputmode=numeric, autocomplete=one-time-code |
| button | use single sign-on | type=button |
| button | Sign in | type=button, disabled=true |

## State: `state=Signing you in`

Screenshot: `reference/shots/PhoneSignIn__state-signing-you-in.jpg`

Announced (role=alert or status): status: Next: Share a problem. You land in the box with the cursor ready. Nothing to find again.

Text added:

```
Signing you in
With your KFintech account, the same one you use for Outlook and Teams.
Next: Share a problem. You land in the box with the cursor ready. Nothing to find again.
Still here? Continue
```

Text removed:

```
Use single sign-on
Sign in to 1% Club
Use your work email
Send code
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Still here? Continue | href=PhoneCompose.dc.html |

## State: `state=Could not sign in`

Screenshot: `reference/shots/PhoneSignIn__state-could-not-sign-in.jpg`

Announced (role=alert or status): alert: Your KFintech account didn't answer in time. Usually a short network hiccup. Nothing you typed is lost.

Text added:

```
We couldn’t sign you in
Your KFintech account didn't answer in time.
Usually a short network hiccup. Nothing you typed is lost.
Still stuck? Call the IT service desk on [EXTENSION] with reference SSO-7F3A, 9:42 am.
Try again
Get a code by email instead
```

Text removed:

```
Use single sign-on
Sign in to 1% Club
Use your work email
Send code
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Try again | href=PhoneCompose.dc.html |
| button | Get a code by email instead | type=button |

## State: `state=Session expired mid-draft`

Screenshot: `reference/shots/PhoneSignIn__state-session-expired-mid-draft.jpg`

Text added:

```
Sign in again to carry on
KFintech apps sign everyone out after 8 hours. Your draft is safe.
Draft, saved 9:41 am on this phone
Investors call to ask why a redemption was rejected
You were checking it. Sorting and the folio you hid are kept.
Send a code and carry on
Use single sign-on instead
```

Text removed:

```
Use single sign-on
Sign in to 1% Club
Use your work email
Send code
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Send a code and carry on | type=button |
| button | Use single sign-on instead | type=button |

## State: `cameFrom=Sign in link`

Screenshot: `reference/shots/PhoneSignIn__camefrom-sign-in-link.jpg`

Text is the same as the default state (the difference is visual or in timing; see the screenshot).
