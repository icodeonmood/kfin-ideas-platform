-- migrate:up
-- L-SORT.rules/8 (BLD-C081): how often people change each suggested sorting field is a launch metric ("trust in
-- pre-filled sorting"). Counted from what shared ideas record per field in `ideas.sorting_sources`
-- ({affects|kind|area|brings: {source: suggested|confirmed|changed, why}}), by the day they were shared (India
-- time). Counts only, no text and no people (non-negotiable 3). Lane C writes the sources (services/worker/submit).
CREATE VIEW sorting_trust AS
SELECT (i.shared_at AT TIME ZONE 'Asia/Kolkata')::date AS shared_on,
       f.field,
       count(*)                                                              AS shared,
       count(*) FILTER (WHERE i.sorting_sources -> f.field ->> 'source' = 'confirmed') AS kept,
       count(*) FILTER (WHERE i.sorting_sources -> f.field ->> 'source' = 'changed')   AS changed
FROM ideas i
CROSS JOIN (VALUES ('affects'), ('kind'), ('area'), ('brings')) AS f (field)
WHERE i.shared_at IS NOT NULL AND i.status <> 'draft'
GROUP BY 1, 2;

-- migrate:down
DROP VIEW IF EXISTS sorting_trust;
