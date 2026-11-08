# Client organisations

Names and aliases of KFin's client organisations (AMCs, issuers, fund managers, pension entities, partners). The gateway uses them **only to replace each name with a typed tag** (`[[CLIENT_AMC_1]]`, `[[CLIENT_ISSUER_1]]`) before any model call, and the review desk sees real names restored.

**Before launch (product team):** add one file per client as `CLI-<slug>.md` with this header:

```yaml
---
type: client-org
title: <Legal or common name>
description: <AMC | issuer | fund manager | pension | partner>
tags: [client]
status: stable
verified: human:<staff code>
kfin:
  id: CLI-<slug>
  client_type: amc            # amc | issuer | fund_manager | pension | partner
  aliases: [<short names, abbreviations, common misspellings>]
  partner_sensitive: false    # true for joint ventures and shared industry platforms
---
```

No contacts, contract terms or pricing here: names and aliases only.

No entries yet.
