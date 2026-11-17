-- migrate:up
-- A One's proposed impact brief, waiting for the programme team (L-ONES.rules/5, S-ONE "Propose a new brief"; lane E).
-- It lives on the One's own record, not in the retired proposals table (DEC-106 retires the Ones console's
-- proposals; briefs stay), so the brief does not depend on a table the cleanup migration drops. Checked text,
-- encrypted with ones/text.py's sealing, context "one:<id>:brief_proposed". Approving copies it to brief_encrypted.
ALTER TABLE ones
  ADD COLUMN brief_proposed_encrypted bytea,
  ADD COLUMN brief_proposed_at        timestamptz,
  ADD CONSTRAINT ones_brief_proposed_pair CHECK ((brief_proposed_encrypted IS NULL) = (brief_proposed_at IS NULL));

-- migrate:down
ALTER TABLE ones
  DROP CONSTRAINT IF EXISTS ones_brief_proposed_pair,
  DROP COLUMN IF EXISTS brief_proposed_at,
  DROP COLUMN IF EXISTS brief_proposed_encrypted;
