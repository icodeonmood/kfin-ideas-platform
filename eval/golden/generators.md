# Placeholder generators for synthetic test data

Golden sets and tests use placeholders that are filled at run time. Implement these once (Python in `eval/golden/generators.py`, mirrored in TypeScript for browser tests) and use a fixed seed (`GOLDEN_SEED`, default 42). Never store generated values in the repo.

| Placeholder | Generates | Rule |
|---|---|---|
| `{{PAN}}` | PAN-shaped string | 5 letters, 4 digits, 1 letter; 4th letter `P` (individual). Random letters, so it is not a known real PAN |
| `{{AADHAAR}}` | 12 digits | First digit 2–9, last digit a valid **Verhoeff** checksum; random spacing (none, spaces or hyphens) |
| `{{AADHAAR_MASKED}}` | `XXXX XXXX NNNN` | Must **not** block |
| `{{MOBILE}}` | Indian mobile | Optional `+91`/`0`, first digit 6–9, 9 more digits; mixed spacing |
| `{{EXT_EMAIL}}` | External personal email | Random local part at `example.com`, `example.in` (reserved domains) |
| `{{KFIN_EMAIL}}` | KFin email | Random local part at the KFin domain set in `.env` (`KFIN_EMAIL_DOMAINS`); must warn only |
| `{{ACCOUNT}}` | Bank account | 9–18 digits, placed within 30 characters of "a/c" or "account" by the case text |
| `{{ACCOUNT_IN_WORDS}}` | Account number spelled out | 10–12 digits written as words ("five six two …"); patterns miss it, the gatekeeper must catch it |
| `{{CARD}}` | Card number | 16 digits with a valid **Luhn** checksum, using a test prefix (for example `4000 00…`) |
| `{{FOLIO}}` | Folio | 6–15 digits, optional `/NN` |
| `{{DEMAT}}` | Demat ID | `IN` + 14 digits, or 16 digits |
| `{{PRAN}}` | PRAN | 12 digits |
| `{{DOB}}` | Date of birth | Random date 1940–2005 in one of `DD/MM/YYYY`, `DD-Mon-YYYY`, `YYYY-MM-DD` |
| `{{IFSC}}` | IFSC | 4 letters, `0`, 6 alphanumerics |
| `{{ARN}}` | Distributor ARN | `ARN-` + 4–6 digits |
| `{{EUIN}}` | Distributor employee code (EUIN) | `E` + 6 digits; a business identifier that warns only, never blocks |
| `{{PERSON_NAME}}` | Person name | From an Indian-locale fake-name generator; never a real public figure |
| `{{COLLEAGUE_NAME}}` | Colleague | A name drawn from the synthetic `users` table, so the tagger tags it as `KFIN_EMPLOYEE` |
| `{{CLIENT_AMC_NAME}}` | Client organisation | A **fictional** AMC from `eval/fixtures/clients.yaml`, loaded into the test taxonomy so the tagger tags it as `CLIENT_AMC`; never a real AMC |
| `{{ADDRESS}}` | Individual address | Flat or house number, building, street and locality from a fake-address generator |
| `{{LAST4}}` | 4 digits | Used inside masked values |

Each generator also has a "near miss" mode used by false-block tests: values that look similar but must not block (10-digit numbers starting 1–5, scheme codes, ISINs, invoice numbers, dates without birth context).
