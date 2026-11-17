# Inbox templates

One per Inbox item kind (E-ENUMS.inbox, L-INBOX.kinds): the reader's kind line (`heading`), the row text after the sender (`line`), the reader's short note (`note`), and the email. Messages carry the idea's title, what happened, any date and a link, never hidden details, anyone's words or a decision's reason (L-NOTIFY/3). Drafts for HR sign-off.

- [questions.md](questions.md) — Questions from the review desk: "{sender} asked you {{count_words}}"
- [teamup_request.md](teamup_request.md) — Team-up or merge request: "{sender} {{#request.merge}}asks to team up and merge their idea into yours{{/request.merge}}{{#request.team_only}}asks to team up{{/request.team_only}}"
- [teamup_answer.md](teamup_answer.md) — Request answered: "{sender} {{#answer.approved}}approved your team-up request{{/answer.approved}}{{#answer.declined}}declined your team-up request, with a reason{{/answer.declined}}"
- [decision.md](decision.md) — Decision: "{sender} {{#choice.pick}}picked your idea{{/choice.pick}}{{#choice.not_picked}}didn't pick your idea, with a reason{{/choice.not_picked}}{{#choice.not_now}}said Not now to your idea, with a date it comes back{{/choice.not_now}}"
- [decision_reversed.md](decision_reversed.md) — Decision reversed: "{sender} {{#viewer.sharer}}reversed a decision on your idea{{/viewer.sharer}}{{#viewer.decided}}reversed your decision on this idea{{/viewer.decided}}"
- [desk_merge.md](desk_merge.md) — Ideas merged by the desk: "{sender} merged your idea with {{other.possessive}}"
- [worth_revised.md](worth_revised.md) — Worth revised: "{sender} revised what your idea is worth"
- [stage_moved.md](stage_moved.md) — Stage moved: "{sender} moved your idea to {{stage.words}}"
- [build_ask.md](build_ask.md) — A build team asks: "{sender} asked you to check new messages"
- [mention.md](mention.md) — Mention: "{sender} mentioned you"
- [crew_joined.md](crew_joined.md) — Joined your crew: "{sender} joined your crew"
- [comment.md](comment.md) — Comment on your idea: "{sender} commented on your idea"
- [draft_kept.md](draft_kept.md) — Draft kept: "{sender} kept your draft from {{#via.phone}}your phone{{/via.phone}}{{#via.email}}email{{/via.email}}{{#via.teams}}Teams{{/via.teams}}"
- [sent_to_desk.md](sent_to_desk.md) — Sent to the review desk: "{sender} sent your idea to the review desk"
- [answer_reminder.md](answer_reminder.md) — Answer reminder: "{sender} {{left}} left to answer {{asker.possessive}} questions"
