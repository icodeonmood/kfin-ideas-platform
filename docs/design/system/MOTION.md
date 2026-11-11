# Motion

Motion answers what a person does. Each screen gets **one** deliberate moment, and it is always the moment that matters on that screen. Nothing else moves.

## Timings and curves

| Token | Value | For |
|---|---|---|
| `t-press` | 100 ms | A press, a tick |
| `t-state` | 200 ms | Hover, focus, colour, a disclosure opening. Also the cap for every reduced-motion fade |
| `t-reveal` | 320 ms | A result arriving: match cards, a dialog, a confirmation |
| `t-scene` | 600 ms | The one moment on a brand screen |
| `t-glow` | 2400 ms | The glow-up only (DEC-084) |
| `ease-out` | cubic-bezier(0.16, 1, 0.3, 1) | Arrivals and answers. The expo-out curve Lenis scrolls with |
| `ease-move` | cubic-bezier(0.42, 0, 0.58, 1) | Cross-fades and colour heat (Astryx's `curves.move`) |
| `ease-in` | cubic-bezier(0.7, 0, 0.84, 0) | Exits, at 75% of the entrance time |

Only `transform`, `opacity`, colour and registered custom properties (`@property --heat`) animate. Never width, height, top, left or margins. No bounce, no elastic.

## The one moment per P0 screen

| Screen | The moment | What starts it | Reduced motion |
|---|---|---|---|
| Sign-in | The spark rises into the %, once (600 ms) | The page opening (a brand surface) | The finished mark |
| Home | The newest One's number heats from Ash to their tier colour as the Ones band comes into view | Scrolling the band into view, once | The tier colour at once |
| Quick capture and canvas | "Share your idea" draws a rising slash across the button before the checks page opens | The press | The checks page opens |
| Checks running | Each finished check fills its slash; the current one breathes | The worker's real progress | Filled or empty, no breathing |
| Find your crew | Match cards arrive one after another, 60 ms apart | The match result arriving | One 200 ms fade |
| My ideas, as a One | The glow-up: the spark heats from the old tier to the new over 2.4 s, then the story appears and is announced | First sign-in after a tier change | The end state, announced |
| Wall | The hundred fills dot by dot in stage order | The page opening (brand) | The filled hundred |
| Office screen | Ambient mode: one spark glows every 10 s (exists) | An admin switching ambient on | No glow; the rotation pauses |
| Launch | The 30-second reveal (exists, DEC-046) | The operator pressing Start | The final frame and the bell |

Working screens (review desk, committee, console, admin, delivery) get no moment beyond feedback: a press, a confirmation rising in place, a toast.

## Reduced motion

From Astryx's motion rules: under `prefers-reduced-motion: reduce`, any movement becomes a cross-fade of at most 200 ms (`t-state`, `ease-move`) straight to the end state. Loops stop (the recording pulse, the spinner, the breathing slash). Nothing advances on its own: the Ones strip and the office screen's cards wait for a press. The end state always appears, and anything announced in the animated version is still announced.

## Choreography without a library

Sequenced moments (the glow-up, the share slash, the launch) are written as timelines, GSAP's idea of labelled steps and offsets, using the browser's Web Animations API (`element.animate()` and `animation.finished`) and CSS. GSAP itself is not used: its licence is not MIT, Apache, BSD or OFL.

## Smooth scroll

Lenis (MIT) could smooth scrolling on brand pages only (Wall, Ones pages, journey, The Ember), never on working screens, and it switches itself off under reduced motion. It is a new dependency, so it waits for the product lead's yes.
