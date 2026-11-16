---
id: J-RECOVER
title: When something goes wrong
rev: 1
status: baseline
source: reference/prototype/Compose.dc.html
depends_on: [S-02, S-04, S-04B, S-05, S-06, S-06B, L-AUTH, L-DRAFT, L-HIDE, L-SUBMIT]
last_delta: none
---

# J-RECOVER: When something goes wrong

Every failure is drawn with plain words and one action, and a draft is never lost.

| # | What goes wrong | Where | What the person sees | What they can do |
|---|---|---|---|---|
| 1 | Sign-in fails | `S-02` | "We couldn't sign you in… Nothing you typed is lost." with a reference | Try again; get a code by email |
| 2 | Wrong code | `S-02` | "That code didn't match… 2 tries left." | Re-enter; ask for a new code after the countdown |
| 3 | Session expires mid-draft | `S-02` | "Sign in again to carry on… Your draft is safe, exactly as you left it." | Sign in; return to the same step |
| 4 | Microphone blocked | `S-04` | The warning under the box | Allow it, or type |
| 5 | Offline while writing | `S-04`, `S-04B`, `S-05` | "Unsaved, you're offline" | Keep going; it saves on reconnect |
| 6 | A draft part is slow or fails | `S-04B` | The loader names the slow part; a failed part offers manual entry | Wait, or fill it in |
| 7 | A file fails to upload | `S-05`, `S-06B` | "Didn't upload. Your other files are fine." | Try again; Remove |
| 8 | A file has personal data | `S-05`, `S-06B`, `S-R3` | "Found a phone number on page 2. Nobody can open it until it's hidden." | Hide it for me; Remove file |
| 9 | A link cannot be opened | `S-05`, `S-06B` | "We couldn't open this link. It may need a sign-in; the review desk can still try it." | Keep it; Remove |
| 10 | Wrong sorting | `S-05`, `S-06B` | The suggestion with its reason | Change it in two actions or fewer |
| 11 | A detail was hidden that is not personal | `S-04B`, `S-05` | "Show it" | Give one of three reasons |
| 12 | Tried to send without confirming the sorting | `S-05` | "Confirm the sorting first, or change any of it." | "Go to the sorting" |
| 13 | Send fails | `S-05` | "Couldn't send. Your draft is safe." | Try again |
| 14 | Offline at send | `S-05` | "You're offline. Your draft is saved on this device. Submit now and it sends when you're back online." | Submit; it sends itself on reconnect |
| 15 | Change of mind after sending | `S-06` | Edit and Withdraw until the desk opens it | Edit; withdraw; later restore |
| 16 | The lead does not answer a merge request | `S-05` | "Waiting for Ravi…" | Withdraw the request; send on their own |

Acceptance: `V-ACC.recover`.

## `J-RECOVER.boards` Boards to walk on the canvas

`Compose`, `Review`, `SignIn`, `Status`
