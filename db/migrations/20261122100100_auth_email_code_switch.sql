-- migrate:up
-- L-AUTH.rules/2-3 (lane A, BLD-E002, DEC-105): sign-in by email code is built but waits for InfoSec. Its switch
-- starts OFF BY DESIGN, like capture.voice and speech.hosted: the go/no-go report prints it as "off as expected",
-- the sign-in screen hides the email route while it is off, and the proxy refuses /auth/code/send and
-- /auth/code/verify with 503. Only InfoSec may switch it (policy/rbac.yaml). The insert is audited like any other
-- switch change (§7.6). It sorts after lane E's cut-over (20261121500100), which creates sign_in_codes.
WITH added AS (
  INSERT INTO kill_switches (name, state, reason, changed_by)
  VALUES ('auth.email_code', 'off', 'Off until InfoSec approves sign-in by email code (BLD-E002, DEC-105)',
          'migration')
  ON CONFLICT (name) DO NOTHING
  RETURNING name, reason
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, NULL, '{"state": "off"}', reason
  FROM added;

-- migrate:down
DELETE FROM kill_switches WHERE name = 'auth.email_code';
