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
ALTER TABLE attachments DROP COLUMN IF EXISTS purpose;
