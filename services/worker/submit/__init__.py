"""Lane C's sorting and sending (L-SORT, L-SUBMIT): the sharer confirms the sorting the draft suggested, sends the
idea, and may change it in the edit window. Withdraw and restore are lane E's (`ideapage.withdraw`), reached through
`submit.adapters` only.

Everything here reads and writes the handoff cut-over's tables (20261121500100): `ideas.status` and the pack's
columns, never `ideas.stage`. Text that others read is the masked copy; logs carry IDs only (non-negotiable 3);
every action a person takes on their idea is written to `audit_log` with IDs and codes (non-negotiable 9).
"""
