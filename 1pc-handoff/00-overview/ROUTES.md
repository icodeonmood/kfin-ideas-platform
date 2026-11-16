---
id: P-ROUTES
title: Screens, routes and navigation
rev: 1
status: baseline
source: reference/prototype/canvas.json
depends_on: []
last_delta: none
---

# Screens, routes and navigation

## `P-ROUTES.screens` Every screen

Routes are proposed. If the repo already has a route for a screen, keep the repo's route and record it in `REPO-MAPPING.md`; the screen ID is what the rest of this pack uses.

| ID | Screen | Desktop board | Phone board | Proposed route | Who |
|---|---|---|---|---|---|
| `S-01` | Landing | `Landing` | `PhoneLanding` | `/` | Anyone, signed out |
| `S-02` | Sign in | `SignIn` | `PhoneSignIn` | `/sign-in` | Anyone |
| `S-03` | Home | `Home` | `PhoneHome` | `/home` | Employee |
| `S-04` | Tell it (new) | `Compose` | `PhoneCompose` | `/share` | Employee |
| `S-04B` | Tell it (the conversation, or a saved draft) | `ComposeResume` | `PhoneComposeResume` | `/share/:draftId` | Sharer |
| `S-05` | Check it, then send it | `Review` | `PhoneReview` | `/share/:draftId/check` | Sharer |
| `S-06` | Status (your idea's page) | `Status` | `PhoneStatus` | `/ideas/:id` (when you are the sharer) | Sharer |
| `S-06B` | Edit after sharing | `Edit` | `PhoneEdit` | `/ideas/:id/edit` | Sharer |
| `S-07` | My ideas | `MyIdeas` | `PhoneMyIdeas` | `/my-ideas` | Employee |
| `S-08` | An idea's conversation | `Messages` | `PhoneMessages` | `/ideas/:id/conversation` | Sharer, crew, desk, build team |
| `S-09` | A colleague's idea | `Idea` | `PhoneIdea` | `/ideas/:id` (when you are not the sharer) | Employee |
| `S-WALL` | The Wall | `Wall` | `PhoneWall` | `/wall` | Employee |
| `S-ONE` | A One's dashboard | `OneDashboard` | none | `/one` | A One |
| `S-R1` | Review desk | `Desk` | none | `/desk` | Reviewer |
| `S-R2` | The idea, for the reviewer | `DeskIdea` | none | `/desk/ideas/:id` | Reviewer |
| `S-R3` | Answer the review desk | `Answer` | `PhoneAnswer` | `/ideas/:id/answer` | Sharer |
| `S-R4` | Ones Committee | `Committee` | none | `/committee` | Committee member |
| `S-H2` | Find your crew | `Crew` | `PhoneCrew` | `/crew` | Employee |
| `S-H2B` | A team-up or merge request, in the lead's Inbox | `CrewRequest` | none (uses the phone Inbox) | `/inbox/:itemId` | Lead |
| `S-H3` | Share another way | `Ways` | none (section on phone Home) | `/share/other-ways` | Employee |
| `S-H4` | What happens after you share | `How` | none | `/how-it-works` | Employee, first visit |
| `S-H5` | Inbox | `Inbox` | `PhoneInbox` | `/inbox` | Employee |
| `S-H6` | Profile and settings | `Profile` | none | `/profile` | Employee |
| `S-OFFICE` | Office screen (wall display) | `Office` | none | `/display/office` | Display |
| `S-LAUNCH` | Launch screen (inauguration) | `Launch` | none | `/display/launch` | Display operator |

Not screens: `Handoff` (a design record) and `Motion` (motion specimens, see `F-MOTION`). "H1 · Needs you" was retired: the Inbox's "Needs you" tab replaces it.

Screens without a phone board (`S-ONE`, `S-R1`, `S-R2`, `S-R4`, `S-H3`, `S-H4`, `S-H6`) must still work on a phone using `F-SPACE.breakpoints`. They were not drawn because their users work at a desk. `OPEN:` confirm whether the review side needs a designed phone layout.

`/ideas/:id` renders `S-06` for the sharer and `S-09` for anyone else. A reviewer following a link to an idea lands on `S-R2`.

## `P-ROUTES.nav` Navigation

Desktop sidebar (`C-SIDEBAR`), top to bottom:

1. Brand (to Home) and the fold button.
2. "Share a problem" with the `P` hint → `S-04`.
3. Home → `S-03`; Find your crew → `S-H2`; Wall → `S-WALL`; Inbox with unread count → `S-H5`.
4. For a reviewer, "Review desk" → `S-R1` is added, and the section below lists "Waiting on sharers". For a committee member, "Ones Committee" → `S-R4`, and the section lists "Closing soonest".
5. "Drafts" (up to 2, with when and where each was saved) → `S-04B`. "Your ideas" (up to 3) with "View all" → `S-07`.
6. At the foot: the account row (avatar with tier ring, name, tier) → `S-H6`.

Phone tab bar (`C-PHONE-TABS`): Home, My ideas, Share (centre, ink), Wall, Inbox (with count). Find your crew and Profile are reached from Home and the account button.

## `P-ROUTES.graph` Where each screen leads

| From | Action | To |
|---|---|---|
| `S-01` | Share a problem | `S-02` if signed out (intent kept), then `S-04` |
| `S-02` | Signed in | Wherever the person was going: `S-04` after "Share a problem", the draft after a session expiry, else `S-03` |
| `S-03` | Send from the prompt box | `S-04B` with the words as the first message (never back to the empty `S-04`) |
| `S-03` | A draft card "Carry on" | `S-04B` on that draft |
| `S-03` | "Answer the questions" | `S-R3` |
| `S-03` | Team up on a crew card | `C-SHEET-TEAMUP` in place |
| `S-04` | First message sent | becomes `S-04B` in place (same screen, draft panel appears) |
| `S-04B` | Move to Review | `S-05` |
| `S-05` | Back to your words | `S-04B` |
| `S-05` | Submit | `S-06` in state "Just shared" |
| `S-06` | Edit | `S-06B`; Save or Cancel returns to `S-06` |
| `S-06` | Answer the questions | `S-R3` |
| `S-06` | Open the conversation | `S-08` |
| `S-06` | Preview / Team up on a similar idea | `C-PREVIEW` / `C-SHEET-TEAMUP` in place |
| `S-07` | A row | `S-06` (yours), `S-09` (teamed up), `S-04B` (draft), `S-R3` (needs you) |
| `S-07` ← | Back from any of those | `S-07` with the same list, filter, sort, search and scroll |
| `S-08` | Answer the questions | `S-R3` |
| `S-09` | Team up | `C-SHEET-TEAMUP` in place; Back returns to where the person came from (Wall, My ideas, or their own idea) |
| `S-WALL` | An idea title | `S-09` (or `S-06` if it is yours) |
| `S-H2` | Team up | `C-SHEET-TEAMUP` in place |
| `S-H5` | An item | Opens in the reader pane; its action goes to `S-R3`, `S-08`, `S-06`, `S-04B` or stays (`S-H2B`) |
| `S-R1` | A row "Open" / "Read answers" | `S-R2` |
| `S-R2` | Decide | Stays on `S-R2`; the panel changes state |
| `S-R3` | Send | `S-R3` in state "Sent", then back to `S-06` |
| `S-R4` | Review | In place: the row opens; Reverse opens a form in place |

After submitting, Back from `S-06` never returns to an editable form.

## `P-ROUTES.state` State carried between screens

| What | When | Rule |
|---|---|---|
| Share intent | Landing or any "Share a problem" → sign-in → Tell it | Survives sign-in, including single sign-on redirects. The person lands in the box with the cursor ready |
| The words typed on Home | Home → Tell it | Become the first message of the conversation; the draft starts building at once |
| Draft id and step | Session expiry mid-draft | After signing in again the person returns to the same draft and step, with sorting and hidden details kept |
| List state | My ideas, Review desk, Inbox → detail → Back | Tab, filter, sort, search text and scroll position are restored. Keep them in the URL (query string) so a link reproduces the view |
| Where you came from | Wall / My ideas / your idea → a colleague's idea | The Back link names it: "Back to the Wall", "Back to My ideas", "Back to IDEA-2026-001481" |
| Which conversation | Inbox → conversation | Opens on that idea's thread |

The prototype passes some of these through `sessionStorage` (`oc-prompt`, `oc-thread`, `mo-nav`). Those keys are a prototype device; use the router and server state.
