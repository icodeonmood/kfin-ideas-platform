# Motion: copy and controls per state

Generated from the prototype board `reference/prototype/Motion.dc.html`, rendered at 1440px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Motion.jpg`

Headings: H1: How everything moves; H2: Four rules; H3: Quick where people work; H3: Cinematic where it matters; H3: Every move says where; H3: Reduced motion means still; H2: Timing and easing; H2: From one screen to the next; H3: Grow from the card; H3: Flood from the button; H3: Fade through; H3: Slide forward; H3: Slide back; H2: Inside a screen

### Text, top to bottom

```
1% Club, motion v1, 15 November 2026
How everything moves
Cinematic where a moment matters, quick and quiet where people work. Every specimen on this board runs on the same engine the screens use, so what you see here is what ships.
Four rules
1
Quick where people work
Forms, lists and the review desk move in under half a second. Nothing makes anyone wait.
2
Cinematic where it matters
Landing, Home, the Wall and sharing an idea get the long, layered moves.
3
Every move says where
Things grow out of what you tapped and go back where they came from, so you never lose your place.
4
Reduced motion means still
With reduced motion on, nothing travels, nothing loops and every screen simply appears.
Timing and easing
Seven durations and five curves cover every move on the platform. Tokens live in CSS as --mo-press to --mo-hero and --mo-out to --mo-spring.
Token
Duration and curve
Used for
Curve
Press
110 ms, Snap
A button or chip going down under the finger
Quick
180 ms, Expo out
Hover, focus ring, small colour changes
State
260 ms, Snap
Selected, read, on or off
Move
460 ms, Expo out
Things changing place inside a screen (Flip), the next screen sliding in
Scene
720 ms, Expo out
A working screen arriving, block by block
Hero
1000 ms, Expo out
Showcase screens arriving, hero lines word by word
Spring
520 to 560 ms, Spring
Pop-ups, toasts, a selection landing, a press letting go
Expo out
cubic-bezier(.16,1,.3,1)
Emphasised in
cubic-bezier(.05,.7,.1,1)
Accelerate out
cubic-bezier(.3,0,.8,.15)
Snap
cubic-bezier(.2,0,0,1)
Spring
linear(…) with a 16% overshoot
From one screen to the next
Five hand-overs. The screen you leave remembers what you tapped; the screen you land on grows out of it. Press Play to see each one full size.
Grow from the card
The card you tapped opens into the next screen, and its title flies up to become the heading.
Rows and cards to their detail: My ideas to Status, Desk to the idea, Inbox to Answer
Play
Flood from the button
Ink spreads out of the button you pressed, then lifts like a curtain off the new screen.
Share a problem, the phone Share tab, every dark primary button that starts a flow
Play
Fade through
The page changes in place, with a small zoom; the side bar and tab bar never move.
Side bar, phone tab bar, top navigation
Play
Slide forward
The next step comes in from the right.
Next, Continue, the steps of Check it and sign-in
Play
Slide back
The previous step comes back from the left.
Back links and breadcrumbs
Play
Inside a screen
Layout changes morph with GSAP Flip: whatever moved glides to its new place, whatever is new fades in. Try each one.
Tabs slide
Waiting
To review
Decided
3 ideas are waiting on their sharers.
The underline travels from the old tab to the new one and stretches to fit. Used on the Desk, My ideas, the Inbox and Profile.
Choices land
My own research
A report
A conversation
A ring slides from the last choice to the new one, which pops into place on a spring. Used for sorting, the basis of an idea, filters and answers.
Lists re-sort
By time left
By name
Branch queue times are not tracked anywhere
Overdue
Nominee updates bounce between two teams
1 days left
Investors call to ask why a redemption was rejected
3 days left
Same KYC details typed into three screens
5 days left
Rows glide to their new order instead of jumping. Used on the Desk, My ideas and the Wall.
Things open and close
More
Archive one
Menus open from their button and close back into it; pop-ups and toasts arrive on a spring and leave faster than they came.
The 1% spark
Sending, sharing or teaming up throws a burst of slashes from the button. It only marks a commitment, never a click.
Send it
Progress draws itself
Shared
Checked
Reviewed
Built
Shipped
1,240
Replay
Hours saved, counted up
For the build
What runs where
GSAP 3.13 loads from jsDelivr, with cdnjs as the fallback: Flip for layout morphs, SplitText for hero lines, ScrollTrigger for scroll reveals and parallax, CustomEase for the curves.
The first frame of every screen, the hand-over between screens, presses and the spark use the browser's own animation engine, so nothing waits on a download.
If the CDN is blocked, screens still arrive, buttons still press and hand-overs still play; only Flip, word reveals and scroll scenes drop out.
Rules that keep it fast and safe
Only transform, opacity and a short blur on arrival. No layout-heavy animation in loops.
Flip measures at most 180 elements per change, and only around what you touched.
Reduced motion: nothing travels, loops stop, hand-overs are skipped, numbers show their final value.
GSAP's standard licence is free for commercial use but is not open source. One look from Legal before launch.
```

### Controls

| Element | Label | Attributes |
|---|---|---|
| button | Play | type=button |
| button | Play | type=button |
| button | Play | type=button |
| button | Play | type=button |
| button | Play | type=button |
| button[tab] | Waiting | type=button, selected=true |
| button[tab] | To review | type=button, selected=false |
| button[tab] | Decided | type=button, selected=false |
| button[radio] | My own research | type=button, checked=true |
| button[radio] | A report | type=button, checked=false |
| button[radio] | A conversation | type=button, checked=false |
| button | By time left | type=button |
| button | By name | type=button |
| button | More | type=button, expanded=false |
| button | Archive one | type=button |
| button | Send it | type=button |
| button | Replay | type=button |
