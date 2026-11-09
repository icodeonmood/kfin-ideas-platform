-- migrate:up
-- Two more pseudonym-vault scopes (BLD-204, BLD-210): a weekly clustering proposal (its text becomes the
-- cluster's on approval) and the throwaway scope of one research file's gatekeeper check (purged at once).
ALTER TABLE pseudonym_vault DROP CONSTRAINT pseudonym_vault_scope_id_check;
ALTER TABLE pseudonym_vault ADD CONSTRAINT pseudonym_vault_scope_id_check CHECK (scope_id ~ (
  '^(IDEA-[0-9]{4}-[0-9]{6}|CL-[0-9]{4}|CLP-RUN-[0-9]{4}-W[0-9]{2}(-[0-9]+)?-[0-9]+'
  || '|ATTCHK-ATT-[0-9]{4}-[0-9]{6}|DRAFT-[0-9a-f-]{36})$'));

-- migrate:down
DELETE FROM pseudonym_vault WHERE scope_id LIKE 'CLP-%' OR scope_id LIKE 'ATTCHK-%';
ALTER TABLE pseudonym_vault DROP CONSTRAINT pseudonym_vault_scope_id_check;
ALTER TABLE pseudonym_vault ADD CONSTRAINT pseudonym_vault_scope_id_check
  CHECK (scope_id ~ '^(IDEA-[0-9]{4}-[0-9]{6}|CL-[0-9]{4}|DRAFT-[0-9a-f-]{36})$');
