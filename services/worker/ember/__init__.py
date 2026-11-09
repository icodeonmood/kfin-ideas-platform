"""The Ember, the 1% Club's monthly newsletter (DEC-062, DEC-070, DEC-079; BLD-128).

An admin drafts the month's issue; the core committee chair types a short note; the admin sends it to everyone
through the comms module. The issue is built only from what everyone may already see: the Ones' public view
(names only with consent, checked briefs, money only after Finance confirms), checked summaries of what shipped,
counts by line of business, and managers whose teams shared most (people who opted out are never counted).
Nothing is invented: a section with no data says so. `ember.send` stops sending; `ones.public` off stops it too,
because the issue names Ones.
"""
