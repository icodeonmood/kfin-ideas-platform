# States

Today error, empty, paused, "Coming soon" and warnings all look the same (a grey notice). People can't tell "something broke" from "nothing yet" from "switched off on purpose". Each state now has its own shape, glyph, role and words.

| State | Looks like | Glyph | Role | Words (today's, kept) |
|---|---|---|---|---|
| **Error** | White box, 2 px error-red border | Circle with "!" | `role="alert"`; a form's error summary also takes focus | "We couldn't share that just now. Your answers are saved; please try again." |
| **Check first** | Amber wash, amber border | Triangle with "!" | none (read in order) | "Check this first. The person said this is not personal data." |
| **Paused** (kill switch) | A Graphite band across the top of the page, under the header | Pause bars in a circle | `role="status"` | "Sharing and editing ideas is paused for a short while. You can still browse and track your ideas." |
| **Coming soon** | Dashed outline (a box, or a pill inline) | A zero with a dashed edge | none | "Coming soon: …" |
| **Empty** | No box at all: an isometric block drawing in greys, one sentence, the one action | none | none | "You haven't shared an idea yet." + "Share an idea" |
| **Success** | A Zed pill beside the action that caused it, which stays until the next action | Check in a circle | `role="status"` (it is the live region) | "Your brief is with the core committee." |

Rules:

1. **A paused feature says so before people try it.** Every switch that hides or stops something gets its banner text shown where the feature is, not only after a press fails. The server already sends `{error: "paused", banner}`; screens show that `banner` text instead of a generic failure.
2. **"Can't load" is never shown as "not for you".** A failed load uses the error state with "Please try again in a minute"; "This is for Ones" is only for people who are not Ones.
3. **Success is visible.** Today some confirmations exist only for screen readers; the success pill is both the visible message and the live region.
4. **Consequential actions confirm in place.** "Carry out and send", "Announce new Ones", "Approve as chair", "Reveal the scores", "Finish qualifying", "Turn down this proposal", "Approve and publish", removing a file: the first press opens a confirmation directly below (focus moves to its commit button), saying what will happen and to whom. No modal.
5. **Branded loading, error and not-found pages** replace Next's defaults (proposal; needs the product lead's yes as it adds three small files).
