---
id: L-CONVO
title: An idea's conversation
rev: 1
status: baseline
source: reference/copy/Messages.md
depends_on: [L-INBOX, L-HIDE]
last_delta: none
---

# L-CONVO: An idea's conversation

1. `L-CONVO/1` Each idea has exactly one conversation. It shows on the idea's page (a short view) and on its own screen.
2. `L-CONVO/2` Who sees it: the sharer and the review desk from the start ("Only you and the review desk see this conversation."); the crew once there is one ("The crew and the review desk see this conversation."); the build team once chosen.
3. `L-CONVO/3` It is a timeline of two kinds of entry: system events (single lines: "You shared it. Saturday 14 November, 10:05 am", "Checked and matched. 1 folio number hidden, 2 similar ideas found. 10:06 am", "Meera from the review desk opened it.", "Ravi Nair approved your team-up request.") and messages from people (avatar, name with role, time, text, files).
4. `L-CONVO/4` Question sets appear in the timeline as a `C-QCARD`, and the answers as one message ("Your answers to Meera's 3 questions", each with "Added to <part>"). The message box is for everything else; while questions are open a line above it says: "Answer Meera's 3 questions with Answer the questions, so each answer lands on its part of your idea. Write here for anything else."
5. `L-CONVO/5` The box: text plus files; placeholder by audience ("Message the review desk", "Message the crew", "Message the build team", "Reply to Sanjay"). Send with nothing typed or attached: "Write a message or attach a file first."
6. `L-CONVO/6` Mentions with @name notify the person and give them read access to that message's thread only if they are not already in the conversation.
7. `L-CONVO/7` Messages and files go through hidden-detail detection (`L-HIDE`) before anyone else can see them.
8. `L-CONVO/8` A side panel lists "In this conversation": each participant with what they are doing ("Reviewing it", "Shared the idea").
9. `L-CONVO/9` After the desk opens an idea, the conversation is where the sharer writes to the desk (the idea itself is locked).
10. `L-CONVO/10` Messages are not editable after sending. `NOT DRAWN:` default: a sender can delete their own message within 5 minutes; a deleted message leaves "Message removed".

## `L-CONVO.touchpoints` Where the front end depends on this

`S-08`, `S-06`
