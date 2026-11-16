---
id: L-HIDE
title: Hiding customers' personal details
rev: 1
status: baseline
source: reference/copy/Compose.md
depends_on: [E-ENTITIES]
last_delta: none
---

# L-HIDE: Hiding customers' personal details

Nothing that identifies a customer may reach anyone but the person who typed it. This runs before any other service sees the text.

## `L-HIDE.detect` What is detected

| Kind | Label shown | Examples |
|---|---|---|
| Folio number | "Folio" | 1234567/89 |
| PAN | "PAN" | ABCPK1234F |
| Phone number | "Phone" | 10-digit mobile, with or without +91 |
| Email address | "Email" | a customer's address (work addresses of KFintech staff are not hidden) |
| Bank account, IFSC with account, UPI id | "Account" | |
| Aadhaar number | "Aadhaar" | 12 digits, with checksum |
| Customer name next to any of the above | "Name" | `OPEN:` names are hard to detect reliably; default: hide a name only when it sits in the same sentence as another detected detail |

The detector list and patterns are configuration, extendable without a release.

## `L-HIDE.rules` Rules

1. Detection runs on every message, on every edit of a message, on transcripts, on forwarded emails, and on the text content of every file (`L-HIDE.files`).
2. The person's own text is never rewritten in their text box. The detected span is marked (start, end, kind) so the front end can underline it.
3. A masked copy of the text is produced and is the only copy any other service, reviewer, crew member or log ever receives. Mask format: kind + "••••" + last two characters.
4. The unmasked value is stored only inside the owner's draft, encrypted, readable only by the owner's session. After the idea is shared it remains readable only by the sharer in their own "your words".
5. The count and kinds are reported back for the receipt ("Hid 3 personal details from everyone but you: …") and for the stage line ("Personal details hidden").
6. **"Show it".** The person may un-hide a detected item only by choosing a reason from: "it's a scheme or product code", "it's an internal reference", "it's made up for the example". The reason, the person and the time are logged with the idea and visible to the review desk ("Shown, because it's an internal reference"). "Hide it" reverses it.
7. A reviewer who spots a missed detail can hide it from `S-R2` (`NOT DRAWN:` a "Hide this" action on any selected text; default: reviewers can flag text, which masks it at once and notifies the sharer).
8. Hidden details are never written to application logs, analytics, search indexes or notification bodies.

## `L-HIDE.files` Files and links

1. Every uploaded file is scanned (text layer, OCR for images and scanned PDFs, cell contents for spreadsheets) before anyone but the uploader can open it. Until then its status is "Checking for personal details".
2. Clean → "Checked".
3. Found → "Found a phone number on page 2. Nobody can open it until it's hidden." with "Hide it for me" (produces a copy with the regions blacked out and replaces the original for everyone else) or "Remove file".
4. After hiding, the row says what was hidden ("Folio hidden", "A phone number on page 2 is hidden"); the reviewer sees the same line.
5. File limits: one configurable size limit per file and one configurable type list (`P-DECISIONS.open/12`: the boards state 15 MB in the prompt box and 25 MB on Check it). Types drawn: PDF, Word, PowerPoint, Excel, Markdown, HTML, ZIP, images; a folder uploads as a group; a screenshot can be pasted. ZIPs are unpacked and each file scanned; `NOT DRAWN:` password-protected files are refused with "We can't check a locked file. Remove the password and add it again."
6. Malware scan on every file before storage.
7. Links are not fetched for content. They are classified internal (SharePoint, Teams, 1% Club domains) or external, and checked for reachability only; an unreachable link can be kept.

## `L-HIDE.audit` Audit

Every detect, mask, show and hide event is recorded: idea or draft id, kind, who, when, reason. Never the value.

## `L-HIDE.touchpoints` Where the front end depends on this

`S-04`, `S-04B`, `S-05`, `S-06`, `S-R2`, `C-HIDDEN`, `C-FILE`
