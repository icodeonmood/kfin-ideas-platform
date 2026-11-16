# Launch: copy and controls per state

Generated from the prototype board `reference/prototype/Launch.dc.html`, rendered at 1920px wide with reduced motion on.
Each state is one tweak option on the board, changed one at a time from the default. Text is exactly what the board shows.

## Default state

Screenshot: `reference/shots/Launch.jpg`

Headings: H1: Launch screen

### Text, top to bottom

```
1% CLUB · INAUGURATION, FRIDAY 20 NOVEMBER
Launch screen
For the lamp lighting on Friday 20 November. Put this page on the big screen, choose Full screen, then press Start the moment the lamp is lit.
It runs for about thirty seconds, with a bell and a spark sound at the start, and then stays on the invitation and its QR code.
Start
Full screen
0:00
Black, and the bell
0:04
The spark rises
0:08
The two zeros arrive
0:14
1% Club
0:16
The tagline
0:30
The invitation and QR code stay
```

### Controls

| Element | Label | Attributes |
|---|---|---|
| button | Start | type=button |
| button | Full screen | type=button |

## State: `frame=Reveal (plays the 30 seconds)`

Screenshot: `reference/shots/Launch__frame-reveal-plays-the-30-seconds.jpg`

Text added:

```
1% spark. 99% sweat.
QR code to the sign-in address, drawn by the app
You bring the spark.
Scan the code to share your idea.
[SIGN-IN ADDRESS]
Plays 0:00 to 0:30
```

Text removed:

```
1% CLUB · INAUGURATION, FRIDAY 20 NOVEMBER
Launch screen
For the lamp lighting on Friday 20 November. Put this page on the big screen, choose Full screen, then press Start the moment the lamp is lit.
It runs for about thirty seconds, with a bell and a spark sound at the start, and then stays on the invitation and its QR code.
Start
Full screen
0:00
Black, and the bell
0:04
The spark rises
0:08
The two zeros arrive
0:14
0:16
The tagline
0:30
The invitation and QR code stay
```


## State: `frame=Final frame (invitation)`

Screenshot: `reference/shots/Launch__frame-final-frame-invitation.jpg`

Text added:

```
1% spark. 99% sweat.
QR code to the sign-in address, drawn by the app
You bring the spark.
Scan the code to share your idea.
[SIGN-IN ADDRESS]
```

Text removed:

```
1% CLUB · INAUGURATION, FRIDAY 20 NOVEMBER
Launch screen
For the lamp lighting on Friday 20 November. Put this page on the big screen, choose Full screen, then press Start the moment the lamp is lit.
It runs for about thirty seconds, with a bell and a spark sound at the start, and then stays on the invitation and its QR code.
Start
Full screen
0:00
Black, and the bell
0:04
The spark rises
0:08
The two zeros arrive
0:14
0:16
The tagline
0:30
The invitation and QR code stay
```

