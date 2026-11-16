# Resolved styles of shared components

What the browser paints for each part, measured on the prototype at 1440px (phone parts at 390px) with reduced motion on.
Build from these values, not from the layered CSS in `reference/css/`. `backgroundImage`, `boxShadow` and `backdropFilter` are given in full because they carry the glass look.

## C-AVATAR

### with tier ring

Measured on `Home`, element `span.av.sm.t2`, showing "KM".

| Property | Value |
|---|---|
| size | `36px × 36px` |
| font | `600 12px / 12px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0) ; linear-gradient(rgb(236, 236, 232), rgb(236, 236, 232)), conic-gradient(from 210deg, rgb(243, 85, 50), rgb(255, 154, 107), rgb(244, 116, 76), rgb(206, 67, 39), rgb(243, 85, 50))` |
| border | `3px rgba(0, 0, 0, 0)` |
| radius | `50%` |
| padding | `0px 0px 0px 0px` |
| shadow | `rgb(255, 255, 255) 0px 0px 0px 2px inset` |

## C-BUTTON

### primary (ink)

Measured on `DeskIdea`, element `button.btn.ink.full`, showing "Decide on this idea".

| Property | Value |
|---|---|
| size | `392px × 56px` |
| font | `500 16px / 16px, Inter` |
| colour | `rgb(255, 255, 255)` |
| background | `rgb(17, 17, 17)` |
| border | `0px rgb(255, 255, 255)` |
| radius | `12px` |
| padding | `0px 20px 0px 20px` |
| gap | `8px` |
| min-height | `56px` |

### primary, regular

Measured on `Crew`, element `button.btn.ink.full.pc-join`, showing "Team up".

| Property | Value |
|---|---|
| size | `396px × 56px` |
| font | `500 16px / 16px, Inter` |
| colour | `rgb(255, 255, 255)` |
| background | `rgb(17, 17, 17)` |
| border | `0px rgb(255, 255, 255)` |
| radius | `12px` |
| padding | `0px 20px 0px 20px` |
| gap | `8px` |
| shadow | `rgba(17, 17, 17, 0.6) 0px 12px 26px -14px` |
| min-height | `56px` |

### line

Measured on `Wall`, element `button.btn.line`, showing "Show 5 more".

| Property | Value |
|---|---|
| size | `134px × 48px` |
| font | `500 15px / 15px, Inter` |
| colour | `rgb(17, 17, 17)` |
| background | `rgb(255, 255, 255)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `12px` |
| padding | `0px 20px 0px 20px` |
| gap | `8px` |
| shadow | `rgb(208, 208, 203) 0px 0px 0px 1px inset` |
| min-height | `48px` |

### line small

Measured on `DeskIdea`, element `button.btn.line.sm`, showing "Merge".

| Property | Value |
|---|---|
| size | `78px × 44px` |
| font | `500 15px / 15px, Inter` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(255, 255, 255, 0.78)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `12px` |
| padding | `0px 16px 0px 16px` |
| gap | `8px` |
| shadow | `rgb(208, 208, 203) 0px 0px 0px 1px inset` |
| min-height | `44px` |

### text button

Measured on `DeskIdea`, element `a.tb.arlink`, showing "Open".

| Property | Value |
|---|---|
| size | `34px × 44px` |
| font | `500 13.5px / 13.5px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 0px 0px 0px` |
| gap | `6px` |
| min-height | `44px` |

### disabled

Measured on `SignIn`, element `button.btn.ink.big.dis`, showing "Send code".

| Property | Value |
|---|---|
| size | `390px × 56px` |
| font | `500 16px / 16px, Inter` |
| colour | `rgb(255, 255, 255)` |
| background | `rgb(220, 220, 216)` |
| border | `0px rgb(255, 255, 255)` |
| radius | `12px` |
| padding | `0px 20px 0px 20px` |
| gap | `10px` |
| min-height | `56px` |

## C-CARD

### card

Measured on `Status`, element `section.card`, showing "You and the review desk No messages yet.".

| Property | Value |
|---|---|
| size | `427px × 155px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(255, 255, 255, 0.78)` |
| border | `1px rgb(228, 228, 224)` |
| radius | `20px` |
| padding | `24px 26px 24px 26px` |
| shadow | `rgba(255, 255, 255, 0.9) 0px 1px 0px 0px inset, rgba(17, 17, 17, 0.28) 0px 18px 40px -30px` |
| backdrop-filter | `blur(18px) saturate(1.4)` |

### glass

Measured on `DeskIdea`, element `section.listen.glass`, showing "Listen to the whole idea 0:00 / 2:10".

| Property | Value |
|---|---|
| size | `601px × 152px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0) ; linear-gradient(rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.52))` |
| border | `0px rgb(17, 17, 17)` |
| radius | `20px` |
| padding | `18px 20px 14px 20px` |
| gap | `0px 16px` |
| shadow | `rgba(255, 255, 255, 0.95) 0px 1px 0px 0px inset, rgba(255, 255, 255, 0.6) 0px 0px 0px 1px inset, rgba(17, 17, 17, 0.07) 0px 0px 0px 1px, rgba(57, 93, 237, 0.34) 0px 34px 80px -40px, rgba(17, 17, 17, 0.14) 0px 12px 28px -18px` |
| backdrop-filter | `blur(26px) saturate(1.45)` |
| position / z-index | `relative / 6` |

### panel

Measured on `DeskIdea`, element `aside.panel.glass`, showing "Review this idea Clear enough? Decide no".

| Property | Value |
|---|---|
| size | `440px × 346px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0) ; linear-gradient(rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.52))` |
| border | `0px rgba(17, 17, 17, 0.07)` |
| radius | `20px` |
| padding | `24px 24px 0px 24px` |
| shadow | `rgba(255, 255, 255, 0.95) 0px 1px 0px 0px inset, rgba(255, 255, 255, 0.6) 0px 0px 0px 1px inset, rgba(17, 17, 17, 0.07) 0px 0px 0px 1px, rgba(57, 93, 237, 0.34) 0px 34px 80px -40px, rgba(17, 17, 17, 0.14) 0px 12px 28px -18px` |
| backdrop-filter | `blur(26px) saturate(1.45)` |
| position / z-index | `sticky / auto` |

## C-CHIP

### rest

Measured on `Wall`, element `button.chip`, showing "Problems".

| Property | Value |
|---|---|
| size | `95px × 40px` |
| font | `500 14px / 14px, Inter` |
| colour | `rgb(17, 17, 17)` |
| background | `rgb(255, 255, 255)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `999px` |
| padding | `0px 16px 0px 16px` |
| gap | `6px` |
| shadow | `rgb(208, 208, 203) 0px 0px 0px 1px inset` |
| min-height | `40px` |

### selected

Measured on `Wall`, element `button.chip`, showing "All".

| Property | Value |
|---|---|
| size | `49px × 40px` |
| font | `500 14px / 14px, Inter` |
| colour | `rgb(40, 72, 200)` |
| background | `rgb(238, 242, 255)` |
| border | `0px rgb(40, 72, 200)` |
| radius | `999px` |
| padding | `0px 16px 0px 16px` |
| gap | `6px` |
| shadow | `rgb(57, 93, 237) 0px 0px 0px 1.5px inset` |
| min-height | `40px` |

### radio selected

Measured on `Review` in state {"step": "Sorting"}, element `button.chip`, showing "Investors".

| Property | Value |
|---|---|
| size | `113px × 40px` |
| font | `500 14.5px / 14.5px, Inter` |
| colour | `rgb(41, 72, 198)` |
| background | `rgb(238, 241, 255)` |
| border | `0px rgb(41, 72, 198)` |
| radius | `999px` |
| padding | `0px 15px 0px 15px` |
| gap | `7px` |
| shadow | `rgb(57, 93, 237) 0px 0px 0px 1.5px inset` |
| min-height | `40px` |

## C-CREW-DECK

### card

Measured on `Crew`, element `article.pcard.cur`, showing "With the review desk Rejection SMS codes".

| Property | Value |
|---|---|
| size | `440px × 540px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgb(255, 255, 255)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `28px` |
| padding | `0px 0px 0px 0px` |
| shadow | `rgba(17, 17, 17, 0.08) 0px 0px 0px 1px, rgba(17, 17, 17, 0.32) 0px 14px 26px -20px` |
| min-height | `540px` |
| position / z-index | `relative / 3` |

## C-DRAFT-LOADER

### box

Measured on `Compose` in state {"state": "Draft ready", "loader": "Held for review"}, element `div.dload`, showing "Building your draft 2 of 6 ready, about ".

| Property | Value |
|---|---|
| size | `452px × 64px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0) ; linear-gradient(rgba(255, 255, 255, 0.72), rgba(240, 243, 255, 0.9))` |
| border | `0px rgb(17, 17, 17)` |
| radius | `20px` |
| padding | `12px 14px 14px 14px` |
| shadow | `rgba(57, 93, 237, 0.12) 0px 0px 0px 1px inset, rgba(57, 93, 237, 0.55) 0px 8px 22px -14px` |

### track

Measured on `Compose` in state {"state": "Draft ready", "loader": "Held for review"}, element `div.dl-tube`.

| Property | Value |
|---|---|
| size | `424px × 10px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0) ; linear-gradient(rgba(17, 17, 17, 0.08), rgba(17, 17, 17, 0.03))` |
| border | `0px rgb(17, 17, 17)` |
| radius | `999px` |
| padding | `0px 0px 0px 0px` |
| shadow | `rgba(17, 17, 17, 0.14) 0px 1px 2px 0px inset, rgba(255, 255, 255, 0.95) 0px -1px 0px 0px inset` |
| position / z-index | `relative / auto` |

## C-FIELD

### text field

Measured on `SignIn`, element `input.em`.

| Property | Value |
|---|---|
| size | `328px × 56px` |
| font | `400 17px / 22.1px, Inter` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `1px 2px 1px 2px` |

### label

Measured on `SignIn`, element `label.fl`, showing "Work email".

| Property | Value |
|---|---|
| size | `390px × 18px` |
| font | `500 14px / 18.2px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 0px 0px 0px` |

## C-FIELD-MSG

### error

Measured on `SignIn` in state {"state": "Wrong code"}, element `p.cerr`, showing "That code didn’t match. Check the latest".

| Property | Value |
|---|---|
| size | `390px × 53px` |
| font | `500 13.5px / 19.575px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(180, 35, 24)` |
| background | `rgb(254, 243, 242)` |
| border | `0px rgb(180, 35, 24)` |
| radius | `12px` |
| padding | `7px 12px 7px 9px` |
| gap | `8px` |
| shadow | `rgba(180, 35, 24, 0.14) 0px 0px 0px 1px inset` |
| position / z-index | `relative / auto` |

### error under a group

Measured on `Review` in state {"submit": "Tried without confirming"}, element `p.bmsg.bad`, showing "Confirm the sorting first, or change any".

| Property | Value |
|---|---|
| size | `461px × 40px` |
| font | `500 13.5px / 19.575px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(180, 35, 24)` |
| background | `rgb(254, 243, 242)` |
| border | `0px rgb(180, 35, 24)` |
| radius | `12px` |
| padding | `8px 12px 8px 12px` |
| gap | `10px` |

## C-LISTEN

### player

Measured on `DeskIdea`, element `section.listen.glass`, showing "Listen to the whole idea 0:00 / 2:10".

| Property | Value |
|---|---|
| size | `601px × 152px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0) ; linear-gradient(rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.52))` |
| border | `0px rgb(17, 17, 17)` |
| radius | `20px` |
| padding | `18px 20px 14px 20px` |
| gap | `0px 16px` |
| shadow | `rgba(255, 255, 255, 0.95) 0px 1px 0px 0px inset, rgba(255, 255, 255, 0.6) 0px 0px 0px 1px inset, rgba(17, 17, 17, 0.07) 0px 0px 0px 1px, rgba(57, 93, 237, 0.34) 0px 34px 80px -40px, rgba(17, 17, 17, 0.14) 0px 12px 28px -18px` |
| backdrop-filter | `blur(26px) saturate(1.45)` |
| position / z-index | `relative / 6` |

### play

Measured on `DeskIdea`, element `button.lsave`.

| Property | Value |
|---|---|
| size | `44px × 44px` |
| font | `400 13.3333px / normal, Arial` |
| colour | `rgb(42, 42, 46)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(42, 42, 46)` |
| radius | `50%` |
| padding | `1px 6px 1px 6px` |

## C-ONES-FAN

### card

Measured on `Home`, element `li.ocard.t4`, showing "RM Rohit Menon One No. 1, Tier 4, Blaze ".

| Property | Value |
|---|---|
| size | `341px × 511px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(255, 255, 255)` |
| background | `rgb(24, 25, 29)` |
| border | `0px rgb(255, 255, 255)` |
| radius | `28px` |
| padding | `20px 20px 16px 20px` |
| shadow | `rgba(255, 255, 255, 0.1) 0px 0px 0px 1px inset, rgba(0, 0, 0, 0.85) 0px 46px 90px -34px` |
| position / z-index | `absolute / 20` |

## C-PHONE-TABS

### bar

Measured on `PhoneHome`, element `nav.tabs`, showing "Home My ideas Share Wall 2 Inbox".

| Property | Value |
|---|---|
| size | `390px × 83px` |
| font | `400 15px / normal, Inter` |
| letter-spacing | `-0.09px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(255, 255, 255, 0.72)` |
| border | `1px rgb(228, 228, 224)` |
| padding | `6px 6px 24px 6px` |
| backdrop-filter | `saturate(1.6) blur(16px)` |

### tab

Measured on `PhoneHome`, element `a.tab`, showing "My ideas".

| Property | Value |
|---|---|
| size | `76px × 52px` |
| font | `500 11.5px / 11.5px, Inter` |
| letter-spacing | `0.115px` |
| colour | `rgb(95, 95, 100)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(95, 95, 100)` |
| padding | `0px 0px 0px 0px` |
| gap | `4px` |
| min-height | `52px` |
| position / z-index | `relative / auto` |

### tab current

Measured on `PhoneHome`, element `a.tab`, showing "Home".

| Property | Value |
|---|---|
| size | `76px × 52px` |
| font | `600 11.5px / 11.5px, Inter` |
| letter-spacing | `0.115px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 0px 0px 0px` |
| gap | `4px` |
| min-height | `52px` |
| position / z-index | `relative / auto` |

### share

Measured on `PhoneHome`, element `span.t`.

| Property | Value |
|---|---|
| size | `46px × 32px` |
| font | `500 11.5px / 11.5px, Inter` |
| letter-spacing | `0.115px` |
| colour | `rgb(255, 255, 255)` |
| background | `rgb(17, 17, 17)` |
| border | `0px rgb(255, 255, 255)` |
| radius | `12px` |
| padding | `0px 0px 0px 0px` |

## C-PILL

### blue

Measured on `Status`, element `span.pill.blue`, showing "With the review desk".

| Property | Value |
|---|---|
| size | `162px × 26px` |
| font | `500 13px / 18.2px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(211, 219, 255)` |
| background | `rgba(57, 93, 237, 0.28)` |
| border | `0px rgb(211, 219, 255)` |
| radius | `999px` |
| padding | `4px 10px 4px 10px` |
| gap | `7px` |

### warn

Measured on `MyIdeas`, element `span.pill.warn`, showing "Needs you".

| Property | Value |
|---|---|
| size | `100px × 26px` |
| font | `500 13px / 18.2px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(181, 71, 8)` |
| background | `rgb(255, 250, 235)` |
| border | `0px rgb(181, 71, 8)` |
| radius | `999px` |
| padding | `4px 10px 4px 10px` |
| gap | `7px` |

### neutral

Measured on `MyIdeas`, element `span.pill`, showing "Draft".

| Property | Value |
|---|---|
| size | `64px × 26px` |
| font | `500 13px / 18.2px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgb(233, 233, 230)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `999px` |
| padding | `4px 10px 4px 10px` |
| gap | `7px` |

### ok

Measured on `DeskIdea` in state {"state": "Answered"}, element `span.pill.ok.st`, showing "Answered".

| Property | Value |
|---|---|
| size | `96px × 26px` |
| font | `500 13px / 18.2px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(6, 118, 71)` |
| background | `rgb(236, 253, 243)` |
| border | `0px rgb(6, 118, 71)` |
| radius | `999px` |
| padding | `4px 10px 4px 10px` |
| gap | `7px` |

## C-PROMPT

### box

Measured on `Home`, element `div.prompt`, showing "Describe what's getting in your way Sort".

| Property | Value |
|---|---|
| size | `720px × 122px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0) ; linear-gradient(rgba(255, 255, 255, 0.88), rgba(250, 250, 253, 0.7))` |
| border | `0px rgb(17, 17, 17)` |
| radius | `28px` |
| padding | `0px 0px 0px 0px` |
| shadow | `rgba(255, 255, 255, 0.96) 0px 1px 0px 0px inset, rgba(255, 255, 255, 0.7) 0px 0px 0px 1px inset, rgba(17, 17, 17, 0.08) 0px 0px 0px 1px, rgba(17, 17, 17, 0.05) 0px 2px 6px 0px, rgba(57, 93, 237, 0.4) 0px 44px 100px -28px, rgba(17, 17, 17, 0.18) 0px 18px 40px -18px` |
| backdrop-filter | `blur(30px) saturate(1.5)` |
| position / z-index | `relative / auto` |

### starter chip

Measured on `Home`, element `button.starter`, showing "A step customers keep calling about".

| Property | Value |
|---|---|
| size | `720px × 44px` |
| font | `400 15px / 19.5px, Inter` |
| colour | `rgb(42, 42, 46)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(42, 42, 46)` |
| radius | `12px` |
| padding | `0px 14px 0px 14px` |
| gap | `12px` |
| min-height | `44px` |

## C-SEARCH

### bar

Measured on `MyIdeas`, element `div.qbox`, showing "Search your ideas Filter".

| Property | Value |
|---|---|
| size | `1073px × 62px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0) ; linear-gradient(rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.84))` |
| border | `0px rgb(17, 17, 17)` |
| radius | `20px` |
| padding | `8px 8px 8px 20px` |
| gap | `8px` |
| shadow | `rgba(17, 17, 17, 0.08) 0px 0px 0px 1px, rgba(57, 93, 237, 0.42) 0px 22px 48px -30px, rgba(17, 17, 17, 0.2) 0px 8px 20px -16px` |
| backdrop-filter | `blur(20px)` |
| min-height | `62px` |

## C-SHEET-MERGE

### sheet

Measured on `DeskIdea` in state {"state": "Merging"}, element `section.mgsheet`, showing "Merge with IDEA-2026-001412? Kavya’s ide".

| Property | Value |
|---|---|
| size | `560px × 666px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgb(255, 255, 255)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `28px` |
| padding | `28px 28px 28px 28px` |
| shadow | `rgba(17, 17, 17, 0.45) 0px 30px 80px -30px, rgba(17, 17, 17, 0.06) 0px 0px 0px 1px` |
| position / z-index | `fixed / 41` |

### option

Measured on `DeskIdea` in state {"state": "Merging"}, element `label.mg-o`, showing "Ravi’s leads, IDEA-2026-001412 Shared 2 ".

| Property | Value |
|---|---|
| size | `504px × 66px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgb(238, 241, 255)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `12px` |
| padding | `12px 14px 12px 14px` |
| gap | `12px` |
| shadow | `rgb(57, 93, 237) 0px 0px 0px 1.5px inset` |

### scrim

Measured on `DeskIdea` in state {"state": "Merging"}, element `div.mgscrim`.

| Property | Value |
|---|---|
| size | `1425px × 1000px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(17, 17, 17, 0.32)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 0px 0px 0px` |
| backdrop-filter | `blur(2px)` |
| position / z-index | `fixed / 40` |

## C-SHEET-TEAMUP

### sheet

Measured on `Crew` in state {"view": "Request"}, element `section.rq.glass`, showing "KM RN Team up with Ravi Ravi leads “Reje".

| Property | Value |
|---|---|
| size | `440px × 547px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0) ; linear-gradient(rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.52))` |
| border | `0px rgb(17, 17, 17)` |
| radius | `28px` |
| padding | `22px 24px 20px 24px` |
| shadow | `rgba(255, 255, 255, 0.95) 0px 1px 0px 0px inset, rgba(255, 255, 255, 0.6) 0px 0px 0px 1px inset, rgba(17, 17, 17, 0.07) 0px 0px 0px 1px, rgba(57, 93, 237, 0.34) 0px 34px 80px -40px, rgba(17, 17, 17, 0.14) 0px 12px 28px -18px` |
| backdrop-filter | `blur(26px) saturate(1.45)` |
| min-height | `540px` |

### note field

Measured on `Crew` in state {"view": "Request"}, element `textarea.rq-in`.

| Property | Value |
|---|---|
| size | `392px × 114px` |
| font | `400 15px / 22.5px, Inter` |
| colour | `rgb(17, 17, 17)` |
| background | `rgb(255, 255, 255)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `12px` |
| padding | `12px 14px 12px 14px` |
| shadow | `rgba(17, 17, 17, 0.12) 0px 0px 0px 1px inset` |

### dropdown

Measured on `Crew` in state {"view": "Request"}, element `div.rq-bring.rq-dd`, showing "Bring your ideas along Optional Bring yo".

| Property | Value |
|---|---|
| size | `392px × 74px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 0px 0px 0px` |

## C-SIDEBAR

### bar

Measured on `Home`, element `div.sb-in`, showing "1% Club Share a problem P Home Find your".

| Property | Value |
|---|---|
| size | `256px × 1000px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0) ; linear-gradient(rgba(255, 255, 255, 0.72), rgba(255, 255, 255, 0.45))` |
| border | `0px rgb(17, 17, 17)` |
| padding | `16px 12px 16px 12px` |
| gap | `4px` |
| shadow | `rgba(17, 17, 17, 0.08) 1px 0px 0px 0px` |
| backdrop-filter | `blur(22px) saturate(1.4)` |
| position / z-index | `relative / auto` |

### new (Share a problem)

Measured on `Home`, element `a.sb-new`, showing "Share a problem P".

| Property | Value |
|---|---|
| size | `232px × 46px` |
| font | `500 15px / 15px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(255, 255, 255)` |
| background | `rgb(17, 17, 17)` |
| border | `0px rgb(255, 255, 255)` |
| radius | `12px` |
| padding | `0px 12px 0px 12px` |
| gap | `12px` |
| shadow | `rgba(17, 17, 17, 0.7) 0px 10px 22px -14px` |
| min-height | `46px` |
| position / z-index | `relative / auto` |

### item

Measured on `Home`, element `a.sb-i`, showing "Find your crew".

| Property | Value |
|---|---|
| size | `232px × 44px` |
| font | `450 15px / 15px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(42, 42, 46)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(42, 42, 46)` |
| radius | `12px` |
| padding | `0px 12px 0px 12px` |
| gap | `12px` |
| min-height | `44px` |
| position / z-index | `relative / auto` |

### item current

Measured on `Home`, element `a.sb-i`, showing "Home".

| Property | Value |
|---|---|
| size | `232px × 44px` |
| font | `500 15px / 15px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgb(255, 255, 255)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `12px` |
| padding | `0px 12px 0px 12px` |
| gap | `12px` |
| shadow | `rgba(17, 17, 17, 0.07) 0px 0px 0px 1px, rgba(17, 17, 17, 0.3) 0px 6px 16px -10px` |
| min-height | `44px` |
| position / z-index | `relative / auto` |

### count badge

Measured on `Home`, element `span.sb-n`, showing "2".

| Property | Value |
|---|---|
| size | `22px × 22px` |
| font | `600 12px / 22px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(255, 255, 255)` |
| background | `rgb(57, 93, 237)` |
| border | `0px rgb(255, 255, 255)` |
| radius | `999px` |
| padding | `0px 7px 0px 7px` |

### section head

Measured on `Home`, element `p.sb-h`, showing "Drafts".

| Property | Value |
|---|---|
| size | `232px × 16px` |
| font | `500 12.5px / 16.25px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(95, 95, 100)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(95, 95, 100)` |
| padding | `0px 12px 0px 12px` |

### row

Measured on `Home`, element `a.sb-r.sb-dr`, showing "Distributors can’t see why an SIP regist".

| Property | Value |
|---|---|
| size | `232px × 49px` |
| font | `400 14px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(42, 42, 46)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(42, 42, 46)` |
| radius | `12px` |
| padding | `7px 12px 7px 12px` |
| gap | `10px` |

### me

Measured on `Home`, element `a.sb-me`, showing "KM Kavya Menon Tier 2, Glow".

| Property | Value |
|---|---|
| size | `232px × 68px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `12px` |
| padding | `6px 8px 6px 8px` |
| gap | `12px` |
| min-height | `56px` |
| position / z-index | `relative / auto` |

## C-SIMGRID

### tile

Measured on `Review` in state {"step": "Similar ideas"}, element `li.sgt`, showing "With the review desk Rejection SMS codes".

| Property | Value |
|---|---|
| size | `226px × 293px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgb(255, 255, 255)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `20px` |
| padding | `18px 18px 16px 18px` |
| shadow | `rgba(17, 17, 17, 0.06) 0px 0px 0px 1px, rgba(17, 17, 17, 0.35) 0px 24px 50px -36px` |
| min-height | `236px` |

### yours

Measured on `Review` in state {"step": "Similar ideas"}, element `li.sgt.yours`, showing "Yours, not sent yet Investors call to as".

| Property | Value |
|---|---|
| size | `226px × 293px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgb(247, 247, 245)` |
| border | `1px rgb(201, 201, 197)` |
| radius | `20px` |
| padding | `18px 18px 16px 18px` |
| shadow | `rgba(17, 17, 17, 0.08) 0px 0px 0px 1px inset` |
| min-height | `236px` |

## C-SORTS

### group

Measured on `MyIdeas`, element `div.sorts`, showing "Sort by Latest activity Date shared Stag".

| Property | Value |
|---|---|
| size | `321px × 40px` |
| font | `400 13px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(95, 95, 100)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(95, 95, 100)` |
| padding | `0px 0px 8px 0px` |
| gap | `2px` |

### option

Measured on `MyIdeas`, element `button.`, showing "Date shared".

| Property | Value |
|---|---|
| size | `98px × 32px` |
| font | `500 13.5px / 13.5px, Inter` |
| colour | `rgb(74, 74, 80)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(74, 74, 80)` |
| radius | `8px` |
| padding | `0px 10px 0px 10px` |
| min-height | `32px` |

### option on

Measured on `MyIdeas`, element `button.`, showing "Latest activity".

| Property | Value |
|---|---|
| size | `110px × 32px` |
| font | `500 13.5px / 13.5px, Inter` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(17, 17, 17, 0.06)` |
| border | `0px rgb(17, 17, 17)` |
| radius | `8px` |
| padding | `0px 10px 0px 10px` |
| min-height | `32px` |

## C-TABS

### tab

Measured on `Desk`, element `button.mtab`, showing "To review 8".

| Property | Value |
|---|---|
| size | `108px × 46px` |
| font | `500 16px / 16px, Inter` |
| colour | `rgb(74, 74, 80)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(74, 74, 80)` |
| padding | `0px 2px 0px 2px` |
| gap | `8px` |
| min-height | `46px` |
| position / z-index | `relative / auto` |

### tab on

Measured on `Desk`, element `button.mtab`, showing "Waiting on the sharer 3".

| Property | Value |
|---|---|
| size | `197px × 46px` |
| font | `500 16px / 16px, Inter` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 2px 0px 2px` |
| gap | `8px` |
| min-height | `46px` |
| position / z-index | `relative / auto` |

## C-TASKBAR

### bar

Measured on `Review`, element `header.tbar`, showing "Share a problem Tell it , done 2 Check i".

| Property | Value |
|---|---|
| size | `1169px × 64px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(246, 246, 244, 0.55)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 0px 0px 0px` |
| position / z-index | `sticky / 20` |

### save status

Measured on `Review`, element `span.saved`, showing "Saved at 1:44 pm".

| Property | Value |
|---|---|
| size | `139px × 17px` |
| font | `400 14px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(95, 95, 100)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(95, 95, 100)` |
| padding | `0px 0px 0px 0px` |
| gap | `7px` |

## C-TRACK

### track

Measured on `Status`, element `ol.trk`, showing "Shared , done Today, 10:05 am Checked an".

| Property | Value |
|---|---|
| size | `1073px × 115px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 0px 0px 0px` |
| gap | `0px 16px` |
| position / z-index | `relative / auto` |

### node now

Measured on `Status`, element `span.nd`.

| Property | Value |
|---|---|
| size | `24px × 24px` |
| font | `400 16px / normal, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(255, 255, 255)` |
| background | `rgb(243, 243, 241)` |
| border | `0px rgb(255, 255, 255)` |
| radius | `50%` |
| padding | `0px 0px 0px 0px` |
| shadow | `rgb(57, 93, 237) 0px 0px 0px 2px inset, rgba(57, 93, 237, 0.16) 0px 0px 0px 4px` |
| position / z-index | `relative / 1` |

## F-TYPE

### d1 display

Measured on `PhoneHome`, element `h1.hello`, showing "What’s in your way?".

| Property | Value |
|---|---|
| size | `207px × 26px` |
| font | `500 23.046px / 25.8115px, Inter Tight` |
| letter-spacing | `-0.69138px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 0px 0px 0px` |

### h1

Measured on `DeskIdea`, element `h1.h1`, showing "Investors call to ask why a redemption w".

| Property | Value |
|---|---|
| size | `601px × 86px` |
| font | `500 40px / 43.2px, Inter Tight` |
| letter-spacing | `-1.2px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 0px 0px 0px` |

### h2

Measured on `MyIdeas`, element `h1.mi-t`, showing "My ideas".

| Property | Value |
|---|---|
| size | `1073px × 44px` |
| font | `500 40px / 44px, Inter Tight` |
| letter-spacing | `-1.2px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 0px 0px 0px` |

### h3

Measured on `DeskIdea`, element `h2.h3`, showing "Attachments and artefacts".

| Property | Value |
|---|---|
| size | `233px × 25px` |
| font | `500 19px / 24.7px, Inter Tight` |
| letter-spacing | `-0.266px` |
| colour | `rgb(17, 17, 17)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(17, 17, 17)` |
| padding | `0px 0px 0px 0px` |

### body

Measured on `Wall`, element `p.body`, showing "Every idea and problem shared at KFintec".

| Property | Value |
|---|---|
| size | `460px × 48px` |
| font | `400 15px / 24px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(95, 95, 100)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(95, 95, 100)` |
| padding | `0px 0px 0px 0px` |

### meta

Measured on `DeskIdea`, element `span.meta.num`, showing "IDEA-2026-001481".

| Property | Value |
|---|---|
| size | `137px × 16px` |
| font | `400 13.5px / 19.575px, Inter` |
| letter-spacing | `0.054px` |
| colour | `rgb(95, 95, 100)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(95, 95, 100)` |
| padding | `0px 0px 0px 0px` |

### lead

Measured on `Landing`, element `p.lead`, showing "1% Club is where you share the problems ".

| Property | Value |
|---|---|
| size | `600px × 93px` |
| font | `400 20px / 31px, Inter` |
| letter-spacing | `-0.096px` |
| colour | `rgb(74, 74, 80)` |
| background | `rgba(0, 0, 0, 0)` |
| border | `0px rgb(74, 74, 80)` |
| padding | `0px 0px 0px 0px` |

