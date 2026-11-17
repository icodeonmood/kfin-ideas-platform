-- migrate:up
-- S-05.fix, L-WORTH/1 (BLD-C140): a single figure typed with "about" ("about 25k") keeps the word, so Check it, Send
-- it and the edit page read "about ₹25,000 a month saved" as drawn (Review.md). One flag per figure, beside its low
-- and high: true when the sharer wrote "about" (or around, roughly, ~) before one figure; false for a plain figure or
-- a range; NULL when that figure is not given, and on every row written before this column (read as false).
-- Additive: lane C's submit writes it on the sharer's rows (services/worker/submit/fix.py). Lane B's revision reader
-- (desk/revise.py) and lane E's idea page select the columns they name and ignore it; a revision is a new reviewer
-- row, so it never changes the sharer's flag (L-WORTH/3).
ALTER TABLE idea_worth
  ADD COLUMN hours_about   boolean,
  ADD COLUMN cost_about    boolean,
  ADD COLUMN revenue_about boolean;

-- migrate:down
ALTER TABLE idea_worth
  DROP COLUMN IF EXISTS hours_about,
  DROP COLUMN IF EXISTS cost_about,
  DROP COLUMN IF EXISTS revenue_about;
