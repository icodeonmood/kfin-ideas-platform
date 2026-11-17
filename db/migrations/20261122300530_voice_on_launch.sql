-- migrate:up
-- DEC-108 (lane C, BLD-C115): voice is on at launch through Sarvam. The product lead confirmed it on 17 Nov 2026 with
-- the DPO's approval, as non-negotiable 2's voice exception (audio goes to Sarvam untagged; all text is masked first,
-- and every transcript as it returns). `capture.voice` and `speech.hosted` go on, each with an audited reason.
-- Only switches still as a migration left them are touched (`state = 'off' AND changed_by = 'migration'`), and only
-- with one of the reasons a migration gave them: DEC-096's "off by design" (20261121300110) or lane A's DEC-108
-- wording (20261122100500, BLD-A185), whichever ran last. A switch someone or something has switched off since (the
-- watch, the error rate, a person with a reason) stays off: an automatic or deliberate switch-off never comes back
-- on by itself.
WITH changed AS (
  UPDATE kill_switches
     SET state = 'on',
         reason = CASE name
           WHEN 'capture.voice' THEN 'On at launch through Sarvam (DEC-108): confirmed by the product lead with the DPO''s approval on 17 Nov 2026'
           ELSE 'On at launch (DEC-108): Sarvam is the voice route under non-negotiable 2''s voice exception, approval DEC-108'
         END,
         changed_by = 'migration',
         changed_at = now()
   WHERE state = 'off' AND changed_by = 'migration'
     AND ((name = 'capture.voice' AND reason IN (
            'Off until IT deploys the isolated speech service and the memory, InfoSec agrees to the microphone and the model, and the DPO''s privacy notice covers voice notes (DEC-096)',
            'On at launch through Sarvam (DEC-108): switch on with speech.hosted once the Sarvam route is set'))
       OR (name = 'speech.hosted' AND reason IN (
            'Off until InfoSec and the DPO approve a hosted route (DEC-096)',
            'On at launch (DEC-108): switch on once SPEECH_HOSTED_APPROVAL and the Sarvam key are set in the worker')))
  RETURNING name, reason
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, '{"state": "off"}', '{"state": "on"}', reason
  FROM changed;

-- migrate:down
-- Back to the DEC-096 position, only where this migration's reasons still stand.
WITH changed AS (
  UPDATE kill_switches
     SET state = 'off',
         reason = CASE name
           WHEN 'capture.voice' THEN 'Off until IT deploys the isolated speech service and the memory, InfoSec agrees to the microphone and the model, and the DPO''s privacy notice covers voice notes (DEC-096)'
           ELSE 'Off until InfoSec and the DPO approve a hosted route (DEC-096)'
         END,
         changed_by = 'migration',
         changed_at = now()
   WHERE name IN ('capture.voice', 'speech.hosted') AND state = 'on' AND changed_by = 'migration'
     AND reason LIKE 'On at launch%(DEC-108)%'
  RETURNING name, reason
)
INSERT INTO audit_log (actor, action, entity, before, after, reason)
SELECT 'migration', 'kill_switch.set', 'kill_switch:' || name, '{"state": "on"}', '{"state": "off"}', reason
  FROM changed;
