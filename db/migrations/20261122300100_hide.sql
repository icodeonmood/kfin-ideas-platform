-- migrate:up
-- L-HIDE (lane C, BLD-C060 to BLD-C064). Additive only.
-- 1. A hidden detail can sit in text the desk wrote (`desk`), in the idea's title, summary or how-often line
--    (`title`) and in a part of the draft (`part`), as well as in messages, answers, the conversation, edits and
--    files. The reviewer's "Hide this" (L-HIDE.rules/7) works on all of them.
ALTER TABLE hidden_details DROP CONSTRAINT IF EXISTS hidden_details_source_check;
ALTER TABLE hidden_details ADD CONSTRAINT hidden_details_source_check
  CHECK (source IN ('message', 'answer', 'conversation', 'edit', 'file', 'desk', 'title', 'part'));

-- 2. "Hide it for me" (a blacked-out copy of a PDF or image, L-HIDE.files/3) has its own switch. It starts off:
--    until black-out passes review, a file with a detail found opens only for the sharer, the review desk and the
--    Ones Committee (DEC-107). Audited like any other switch change (§7.6).
WITH added AS (
  INSERT INTO kill_switches (name, state, reason, changed_by)
  VALUES ('files.blackout', 'off', 'Off until black-out passes review (DEC-107)', 'migration')
  ON CONFLICT (name) DO NOTHING
  RETURNING name
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, NULL, '{"state": "off"}',
       'Off until black-out passes review (DEC-107)'
  FROM added;

-- 3. The sharer's Inbox item when the review desk hides a detail the checks missed (L-HIDE.rules/7; lane A agreed the
--    kind, 17 Nov; BLD-C063). E-ENUMS.inbox in contracts/1pc/enums.json carries it too. The item never holds the value.
ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_kind_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_kind_check CHECK (kind IN (
  'questions', 'teamup_request', 'teamup_answer', 'decision', 'decision_reversed',
  'desk_merge', 'worth_revised', 'stage_moved', 'build_ask', 'mention', 'crew_joined',
  'comment', 'draft_kept', 'sent_to_desk', 'answer_reminder', 'detail_hidden_by_desk'));

-- migrate:down
DELETE FROM notifications WHERE kind = 'detail_hidden_by_desk';
ALTER TABLE notifications DROP CONSTRAINT IF EXISTS notifications_kind_check;
ALTER TABLE notifications ADD CONSTRAINT notifications_kind_check CHECK (kind IN (
  'questions', 'teamup_request', 'teamup_answer', 'decision', 'decision_reversed',
  'desk_merge', 'worth_revised', 'stage_moved', 'build_ask', 'mention', 'crew_joined',
  'comment', 'draft_kept', 'sent_to_desk', 'answer_reminder'));
DELETE FROM kill_switches WHERE name = 'files.blackout';
DELETE FROM hidden_details WHERE source IN ('desk', 'title', 'part');
ALTER TABLE hidden_details DROP CONSTRAINT IF EXISTS hidden_details_source_check;
ALTER TABLE hidden_details ADD CONSTRAINT hidden_details_source_check
  CHECK (source IN ('message', 'answer', 'conversation', 'edit', 'file'));
