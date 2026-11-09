-- Committee flow review fixes (BLD-221): a contributor's direct manager on the committee is flagged at round open
-- (§3.1), with its own reason so an admin can clear it.

-- migrate:up
ALTER TABLE coi_flags DROP CONSTRAINT coi_flags_reason_check;
ALTER TABLE coi_flags ADD CONSTRAINT coi_flags_reason_check CHECK (reason IN ('contributor', 'declared', 'manager'));

-- migrate:down
DELETE FROM coi_flags WHERE reason = 'manager';
ALTER TABLE coi_flags DROP CONSTRAINT coi_flags_reason_check;
ALTER TABLE coi_flags ADD CONSTRAINT coi_flags_reason_check CHECK (reason IN ('contributor', 'declared'));
