-- migrate:up
-- DEC-124 (walk item WF-01), BLD-C216: the "+" in the conversation's box (S-08) uploads through the one route,
-- `POST /api/files` with `for: "conversation"` beside `idea_id`. A file is either the idea's own (Proof, the edit
-- page, Send it, the idea page, the desk's files) or one added for the conversation, which lane F's composer then puts
-- on an entry. Every reader of an idea's own files reads `purpose = 'idea' AND conversation_entry_id IS NULL`, so a
-- conversation file never shows among them, sent or not. Files already on an entry are conversation files.
ALTER TABLE attachments
  ADD COLUMN purpose text NOT NULL DEFAULT 'idea' CHECK (purpose IN ('idea', 'conversation'));

UPDATE attachments SET purpose = 'conversation' WHERE conversation_entry_id IS NOT NULL;

-- migrate:down
-- BLD-C223: a conversation file not yet on an entry is its uploader's alone (DEC-127, BLD-C222). Without `purpose` it
-- would read as one of the idea's own files, so a down removes those rows first, with their hidden details (the
-- file's and its name's, `<id>:name`) and their queued checks. Their stored copies are left in the store, where no row
-- reaches them. Conversation files already on an entry stay: `conversation_entry_id` keeps them out of the idea's.
DELETE FROM jobs WHERE type = 'file.check' AND state = 'queued' AND payload->>'attachment_id' IN
  (SELECT id FROM attachments WHERE purpose = 'conversation' AND conversation_entry_id IS NULL);
DELETE FROM hidden_details WHERE source = 'file' AND split_part(source_id, ':', 1) IN
  (SELECT id FROM attachments WHERE purpose = 'conversation' AND conversation_entry_id IS NULL);
DELETE FROM attachments WHERE purpose = 'conversation' AND conversation_entry_id IS NULL;
ALTER TABLE attachments DROP COLUMN IF EXISTS purpose;
