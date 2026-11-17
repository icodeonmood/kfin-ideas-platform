-- migrate:up
-- DEC-108 (BLD-A185): voice is on at launch through Sarvam. The two switches stay off until deploy sets the route
-- (SPEECH_MODE=sarvam, the Sarvam key in the worker's env, SPEECH_HOSTED_APPROVAL) and InfoSec switches them on.
-- Only their reasons change, which the Admin page shows, and only where nobody has touched them since the seed.
WITH changed AS (
  UPDATE kill_switches
     SET reason = CASE name
           WHEN 'capture.voice' THEN 'On at launch through Sarvam (DEC-108): switch on with speech.hosted once the Sarvam route is set'
           ELSE 'On at launch (DEC-108): switch on once SPEECH_HOSTED_APPROVAL and the Sarvam key are set in the worker'
         END,
         changed_at = now()
   WHERE name IN ('capture.voice', 'speech.hosted') AND state = 'off' AND changed_by = 'migration'
  RETURNING name, reason
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, '{"state": "off"}', '{"state": "off"}', reason
  FROM changed;

-- migrate:down
UPDATE kill_switches
   SET reason = CASE name
         WHEN 'capture.voice' THEN 'Off until IT deploys the isolated speech service and the memory, InfoSec agrees to the microphone and the model, and the DPO''s privacy notice covers voice notes (DEC-096)'
         ELSE 'Off until InfoSec and the DPO approve a hosted route (DEC-096)'
       END
 WHERE name IN ('capture.voice', 'speech.hosted') AND state = 'off' AND changed_by = 'migration';
