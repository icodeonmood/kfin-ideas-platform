# SignIn: copy and controls per state

Generated from the prototype board `reference/prototype/SignIn.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/SignIn.jpg`

Headings: H1: Sign in to 1% Club

### Text, top to bottom

```
1% Club
Sign in to 1% Club
Work email
Use your official KFintech email ID to sign in.
Send code
or
Use single sign-on
1% Club, a KFintech programme
1% spark. 99% sweat.
```

### Controls

| Element | Label | Attributes |
|---|---|---|
| a | 1% Club | href=Landing.dc.html |
| input | name@kfintech.com | type=email, inputmode=email, autocomplete=email |
| button | Send code | type=button, disabled=true |
| button | Use single sign-on | type=button |

## State: `state=Enter code`

Screenshot: `reference/shots/SignIn__state-enter-code.jpg`

Text added:

```
Check your email
We sent a 6-digit code to kavya.menon@kfintech.com. It works for 10 minutes. Change email
You can ask for a new code in 0:45.
Sign in
Not in your inbox? Check Junk, or use single sign-on.
```

Text removed:

```
Sign in to 1% Club
Work email
Use your official KFintech email ID to sign in.
Send code
or
Use single sign-on
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Change email | type=button |
| input | 6-digit code | type=text, invalid=false, maxlength=6, inputmode=numeric, autocomplete=one-time-code |
| button | Sign in | type=button, disabled=true |
| button | use single sign-on | type=button |

## State: `state=Wrong code`

Screenshot: `reference/shots/SignIn__state-wrong-code.jpg`

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
Sign in
Not in your inbox? Check Junk, or use single sign-on.
```

Text removed:

```
Sign in to 1% Club
Work email
Use your official KFintech email ID to sign in.
Send code
or
Use single sign-on
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Change email | type=button |
| input | 6-digit code | type=text, invalid=true, maxlength=6, inputmode=numeric, autocomplete=one-time-code |
| button | Sign in | type=button, disabled=true |
| button | use single sign-on | type=button |

## State: `state=Signing you in`

Screenshot: `reference/shots/SignIn__state-signing-you-in.jpg`

Announced (role=alert or status): status: Next: Share a problem You land in the box with the cursor ready. Nothing to find again.

Text added:

```
Signing you in
With your KFintech account, the same one you use for Outlook and Teams.
Next: Share a problem
You land in the box with the cursor ready. Nothing to find again.
Usually under a second. Still here? Continue
```

Text removed:

```
Sign in to 1% Club
Work email
Use your official KFintech email ID to sign in.
Send code
or
Use single sign-on
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Continue | href=Compose.dc.html |

## State: `state=Could not sign in`

Screenshot: `reference/shots/SignIn__state-could-not-sign-in.jpg`

Announced (role=alert or status): alert: Your KFintech account didn't answer in time. This is usually a short network hiccup on the office Wi-Fi or VPN. Nothing you typed is lost.

Text added:

```
We couldn't sign you in
Your KFintech account didn't answer in time.
This is usually a short network hiccup on the office Wi-Fi or VPN. Nothing you typed is lost.
Try again
You will still go straight to Share a problem. Or get a code by email instead.
Still stuck? Call the IT service desk on [EXTENSION] and give them this reference: SSO-7F3A, 9:42 am
```

Text removed:

```
Sign in to 1% Club
Work email
Use your official KFintech email ID to sign in.
Send code
or
Use single sign-on
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| a | Try again | href=Compose.dc.html |
| button | get a code by email instead | type=button |

## State: `state=Session expired mid-draft`

Screenshot: `reference/shots/SignIn__state-session-expired-mid-draft.jpg`

Text added:

```
Sign in again to carry on
KFintech apps sign everyone out after 8 hours. Your draft is safe, exactly as you left it.
Draft, saved 9:41 am on this laptop
Investors call to ask why a redemption was rejected
You were checking it. Sorting and the folio you hid are kept.
Send a code to kavya.menon@kfintech.com
Use single sign-on instead
Trouble signing in? Call the IT service desk on [EXTENSION].
```

Text removed:

```
Sign in to 1% Club
Work email
Use your official KFintech email ID to sign in.
Send code
or
Use single sign-on
```

Controls new or changed in this state:

| Element | Label | Attributes |
|---|---|---|
| button | Send a code to kavya.menon@kfintech.com | type=button |
| button | Use single sign-on instead | type=button |

## State: `cameFrom=Sign in link`

Screenshot: `reference/shots/SignIn__camefrom-sign-in-link.jpg`

Text is the same as the default state (the difference is visual or in timing; see the screenshot).
