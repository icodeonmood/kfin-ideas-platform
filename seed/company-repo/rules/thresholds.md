---
type: rule
title: Thresholds for checks, matching, clustering, canvas and autonomy
description: Numbers the platform uses for gatekeeper decisions, matching, clustering, the canvas strength meter, attachments, scans and kill-switch triggers.
tags:
- rules
- thresholds
status: draft
generated:
  by: human:product-team-draft
  at: '2026-11-08T00:00:00+05:30'
kfin:
  id: RULE-thresholds
  version: '1.1'
  approver: null
---

All tunable numbers live here so they can change without code. Changes go through a pull request approved by an admin.
The canvas strength meter is computed by code from `canvas_strength`, identically in the browser, the server and the review console.
A suggested answer counts towards strength only after the person accepts it.
`files` is the 1% Club's one file limit and type list (BLD-E007, L-HIDE.files/5): each file can be up to `limit_mb` (at most 25: a larger limit needs a release, BLD-C108), of a type in `types`, and the help line under every drop area is written from them. A link is an internal link when its domain is one of `internal_link_domains`, KFintech's own domains or the 1% Club's; it is never opened (BLD-E001).
`assumptions` is the fixed list of basic assumptions the assistant may use to turn a person's own figures into the canvas's units (DEC-097). Each one it uses is shown to the person and the review desk under "Assumptions we made", in the words of `says`. Add one only with the product lead's agreement.

```yaml
version: '1.1'
gatekeeper:
  personal_data_block: 0.5
  redirect_suggest: 0.8
  spam_hold: 0.9
match:
  cosine_floor: 0.45
  top_k_each: 50
  final_k: 20
  rrf_k: 60
  reserve_solved: 3
  reserve_declined: 3
  rerun_if_edit_share: 0.2
trust_boost:
  human: 1.15
  machine: 1.0
  unverified: 0.9
cluster:
  min_cluster_size: 3
  min_samples: 2
  small_pool_cutoff: 200
  small_pool_distance: 0.25
  pair_cosine: 0.85
  grow_overlap: 0.5
  new_max_centroid: 0.8
  merge_centroid: 0.9
  split_between: 0.75
  theme_distance: 0.35
working_group_trigger:
  min_contributors: 3
  min_lobs: 2
autonomy:
  enabled: false
  promote_at: 0.95
  demote_below: 0.9
  window: 200
  spot_check_rate: 0.05
consistency:
  similarity: 0.8
  score_gap: 20
canvas:
  one_line_max_words: 20
  details_min_chars: 50
  join_context_min_chars: 30
  draft_retention_days: 30
  nudge_days_after_quick_capture:
  - 2
  - 7
  nudge_max: 2
canvas_strength:
  what_it_is:
    one_line_required: true
    details_min_chars: 150
  who_it_touches:
    segments_min: 1
    plus_any_of:
    - frequency_or_reach
    - today_alternative
  whats_it_worth:
    category_not: not_sure
    play_required: true
    figure_any_of:
    - hours_saved_per_month
    - inr_saved_per_year
    - inr_revenue_one_time
    - inr_revenue_per_year
    - clients_who_would_pay
  evidence:
    basis_any_of:
    - own_data
    - document
    or_any_reference: true
    or_clean_attachment: true
  solved_elsewhere:
    answer_not: dont_know
    our_advantage_required: true
  suggested_counts_only_when_accepted: true
  strong_canvas_min: 4
  nudge_below: 3
attachments:
  max_files: 5
  max_mb_each: 20
  max_mb_per_idea: 50
  allowed:
  - pdf
  - docx
  - pptx
  - xlsx
  - csv
  - png
  - jpg
  day_one_checked:
  - pdf_text_layer
  - docx
  - pptx
  - xlsx
  - csv
  day_one_held:
  - png
  - jpg
  - pdf_scanned
  column_block_share: 0.2
  rejected_retention_hours: 24
files:
  limit_mb: 25
  types:
  - pdf
  - docx
  - pptx
  - xlsx
  - csv
  - md
  - html
  - zip
  - png
  - jpg
  internal_link_domains:
  - sharepoint.com
  - teams.microsoft.com
  - teams.cloud.microsoft
scan:
  budget_s_p95: 15
  fallback_after_s: 20
  async_retry_minutes:
  - 1
  - 5
  - 15
  - 60
  poll_interval_s: 2
assumptions:  # DEC-097: the only basic assumptions the assistant may use, to turn a person's own figures into the canvas's units
- id: working_days_per_month
  value: 22
  says: 22 working days in a month
- id: working_hours_per_day
  value: 8
  says: 8 working hours in a day
- id: months_per_year
  value: 12
  says: 12 months in a year
voice:
  # Voice notes in quick capture (DEC-096, BLD-C005, BLD-C008): recordings not yet text per draft, and new
  # recordings a person may send in an hour. Failed notes never count as waiting.
  max_waiting: 3
  max_per_hour: 10
kill_switch_triggers:
  leak_hits_per_hour_for_ai_all: 3
  agent_error_rate_15min: 0.2
  virus_scanner_down_minutes: 5
  email_bounce_rate_hour: 0.05
```
