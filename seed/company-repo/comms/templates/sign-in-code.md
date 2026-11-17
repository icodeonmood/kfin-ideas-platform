---
type: comms-template
title: Your 1% Club sign-in code
description: Message template for auth.code, the email-code route of sign-in (L-AUTH.rules/2-3). Sent at once, never queued or stored.
tags:
- comms
- template
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-16T00:00:00+05:30'
kfin:
  id: TPL-sign-in-code
  version: '1.0'
  events:
  - auth.code
  subject: Your 1% Club sign-in code
  signed_as: 1% Club
  hr_signed_off: false
---

<!-- Mustache-style variables. The code is the whole point: keep it first and plain. HR signs off all wording. -->

Hi {{recipient.first_name}},

Your code to sign in to 1% Club is **{{code.value}}**. It works for {{code.valid_minutes}} minutes.

If you didn't ask for it, you can ignore this email. Nobody can sign in without it.

1% Club
