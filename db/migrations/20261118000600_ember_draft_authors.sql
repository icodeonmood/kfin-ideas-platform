-- migrate:up
-- Ember draft authors (BLD-140). A draft or ready issue no longer keeps a person from being deleted: who opened it,
-- wrote the note or approved it becomes NULL (the author stays in audit_log as `ember.drafted`, `ember.note_saved`
-- and `ember.note_approved`). A sent issue still keeps every author: a trigger refuses to clear them, as RESTRICT
-- did, and `sent_by` stays RESTRICT. If the approver of a ready issue goes, the issue goes back to draft.
ALTER TABLE ember_issues
  DROP CONSTRAINT ember_issues_created_by_fkey,
  ADD CONSTRAINT ember_issues_created_by_fkey FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL,
  DROP CONSTRAINT ember_issues_chair_note_by_fkey,
  ADD CONSTRAINT ember_issues_chair_note_by_fkey FOREIGN KEY (chair_note_by) REFERENCES users (id) ON DELETE SET NULL,
  DROP CONSTRAINT ember_issues_note_approved_by_fkey,
  ADD CONSTRAINT ember_issues_note_approved_by_fkey
    FOREIGN KEY (note_approved_by) REFERENCES users (id) ON DELETE SET NULL;

CREATE OR REPLACE FUNCTION ember_keep_sent_authors() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.state = 'sent' AND (
       (OLD.created_by IS NOT NULL AND NEW.created_by IS NULL)
    OR (OLD.chair_note_by IS NOT NULL AND NEW.chair_note_by IS NULL)
    OR (OLD.note_approved_by IS NOT NULL AND NEW.note_approved_by IS NULL)) THEN
    RAISE EXCEPTION 'a sent issue of The Ember keeps its authors' USING ERRCODE = 'restrict_violation';
  END IF;
  IF OLD.state = 'ready' AND OLD.note_approved_by IS NOT NULL AND NEW.note_approved_by IS NULL THEN
    NEW.state := 'draft';
    NEW.ready_token := NULL;
    NEW.note_approved_at := NULL;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER ember_issues_keep_sent_authors
  BEFORE UPDATE OF created_by, chair_note_by, note_approved_by ON ember_issues
  FOR EACH ROW EXECUTE FUNCTION ember_keep_sent_authors();

-- migrate:down
DROP TRIGGER IF EXISTS ember_issues_keep_sent_authors ON ember_issues;
DROP FUNCTION IF EXISTS ember_keep_sent_authors();
ALTER TABLE ember_issues
  DROP CONSTRAINT ember_issues_created_by_fkey,
  ADD CONSTRAINT ember_issues_created_by_fkey FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE RESTRICT,
  DROP CONSTRAINT ember_issues_chair_note_by_fkey,
  ADD CONSTRAINT ember_issues_chair_note_by_fkey FOREIGN KEY (chair_note_by) REFERENCES users (id) ON DELETE RESTRICT,
  DROP CONSTRAINT ember_issues_note_approved_by_fkey,
  ADD CONSTRAINT ember_issues_note_approved_by_fkey
    FOREIGN KEY (note_approved_by) REFERENCES users (id) ON DELETE RESTRICT;
