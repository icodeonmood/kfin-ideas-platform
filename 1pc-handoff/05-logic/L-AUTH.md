---
id: L-AUTH
title: Sign-in, session and keeping intent
rev: 1
status: baseline
source: reference/copy/SignIn.md
depends_on: [E-ENTITIES]
last_delta: none
---

# L-AUTH: Sign-in, session and keeping intent

## `L-AUTH.purpose` What it must do

Get an employee signed in with their KFintech account with as little interruption as possible, and return them to exactly what they were doing.

## `L-AUTH.rules` Rules

1. **Single sign-on first.** A "Share a problem" click by a signed-out person attempts silent single sign-on. If it succeeds, the person never sees the sign-in screen and lands on `S-04` with the cursor in the box.
2. **Email code as the other route.** The person enters their work email; only `@kfintech.com` addresses (and any other domains configured) are accepted. A 6-digit code is emailed.
3. Code rules (configurable): valid 10 minutes; 3 attempts per code; a new code can be requested 45 seconds after the last; requesting a new code invalidates the old one.
4. **Intent is kept.** The destination (and, for a draft, the draft id and step) is stored server-side against the sign-in attempt, not only in the browser, so it survives a redirect to the identity provider and back, and a switch from single sign-on to email code.
5. **Session length** follows KFintech policy: 8 hours. Expiry mid-task does not lose anything: the draft is saved (see `L-DRAFT.autosave`), and after signing in again the person returns to the same draft and step with sorting and hidden details intact.
6. A first-time person gets an employee record created from the directory: name, initials, department ("area"), city, manager. `OPEN:` the directory source and field mapping are for IT (`P-DECISIONS.signoff/5`).
7. Roles (reviewer, committee member, display operator) come from a role table managed by an admin, not from the directory.
8. Every sign-in failure gets a short reference ("SSO-7F3A, 9:42 am") that the person can read to the IT service desk, and that maps to the server log.

## `L-AUTH.states` States the screen must be able to show

| State | Cause | Screen shows |
|---|---|---|
| Enter email | Silent sign-on not possible, or the person chose "Sign in" | Work email field, "Send code", "Use single sign-on" |
| Enter code | Code sent | Six boxes, the address it went to with "Change email", resend countdown "You can ask for a new code in 0:45.", "Not in your inbox? Check Junk, or use single sign-on." |
| Wrong code | Mismatch | "That code didn't match. Check the latest email from 1% Club. 2 tries left." The count is from the server |
| Out of tries / expired | 3 wrong, or 10 minutes passed | `NOT DRAWN:` "That code has run out. We've sent a new one." and a fresh code is sent automatically, once |
| Signing you in | Silent sign-on in progress | "Signing you in. With your KFintech account, the same one you use for Outlook and Teams." "Next: Share a problem." "Usually under a second. Still here? Continue" |
| Could not sign in | Identity provider timeout or error | "We couldn't sign you in. Your KFintech account didn't answer in time." "Nothing you typed is lost." "Try again", "get a code by email instead", and the reference |
| Session expired mid-draft | 8-hour expiry while a draft is open | "Sign in again to carry on." The draft's title, when it was saved and on which device, what is kept; "Send a code to <email>" and "Use single sign-on instead" |

## `L-AUTH.errors` Errors

`NOT DRAWN:` these three cases; the wording is the default.

| Case | Response |
|---|---|
| Email not a work address | Field error: "Use your KFintech email, like name@kfintech.com." (`V-FIELDS.signin`) |
| Too many code requests (rate limit) | "Too many tries. Wait 10 minutes, or use single sign-on." |
| Account disabled in the directory | "This account can't sign in to 1% Club. Call the IT service desk on [EXTENSION]." |

Contract: `A-API.auth`.

## `L-AUTH.touchpoints` Where the front end depends on this

`S-02`, `S-01`
