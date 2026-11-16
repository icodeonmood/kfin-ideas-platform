"""Lane E's reads for an idea's own pages: the sharer's page (S-06), a colleague's view (S-09), which of the two a
person gets at `/ideas/:id` (P-ROUTES.screens), My ideas (S-07), and the sharer's withdraw and restore
(L-SUBMIT.withdraw).

Everything is read from the handoff cut-over's tables (20261121500100). Lanes B (decisions, questions, the
committee's window), C (drafts, hidden details, the sharer's sealed words) and F (team-up, crew, the
conversation) own their tables; this package only reads them. Words a screen shows come from here, ready to
show (A-API.conventions/6), so every screen says a date the same way.
"""
