---
id: C-FILE
title: File and link rows, and the uploader
rev: 1
status: baseline
source: reference/css/boards/Review.css
depends_on: [C-FIELD-MSG, C-SKELETON]
last_delta: none
---

# C-FILE: File and link rows, and the uploader

## `C-FILE.row` A file row

A type badge (PNG, JPG, PDF, XLSX, DOC, PPT, Link: a small coloured tile with the type in caps), the file name, its size, a status, and one or two actions.

| Status | Shown as | Actions |
|---|---|---|
| Uploading | `NOT DRAWN:` a thin progress line in the row | Remove |
| Checking | Spinner + "Checking for personal details" | Remove |
| Checked | Green tick + "Checked" | View, Remove |
| Upload failed | Error under the row: "Didn't upload. Your other files are fine." | Try again, Remove |
| Personal data found | Warning under the row: "Found a phone number on page 2. Nobody can open it until it's hidden." | Hide it for me, Remove file |
| Hidden after check | "Checked", with what was hidden ("Folio hidden") | View |
| Too big | Error: "Too big. Files can be up to 15 MB." | Remove |
| Link unreachable | Warning: "We couldn't open this link. It may need a sign-in; the review desk can still try it." | Keep it, Remove |

## `C-FILE.uploader` The uploader

1. Drop area. In the Home and Tell it prompt box: "Drop files or a folder here, or browse" with "PDF, Word, PowerPoint, Excel, Markdown, HTML, ZIP, images or a whole folder, up to 15 MB each." On Check it (Proof) and Edit: "Drop files here, or browse" with "Screenshots, photos, PDFs or spreadsheets, up to 25 MB each. You can paste a screenshot too." `OPEN:` the two places state different limits and types (`P-DECISIONS.open/12`); build one configurable limit and one type list, and render the help line from them.
2. A folder adds as one row ("Branch notes, 6 files, 3.1 MB").
3. "Add a link" takes a URL. Links to SharePoint, Teams and 1% Club are marked "Internal link"; anything else "External link". A string that is not a URL shows: "That doesn't look like a link. A link looks like intranet.kfintech.com/page."
4. Every file is checked for personal details before anyone but the sharer can open it (`L-HIDE.files`). One failed file never blocks the others.
5. Drag and drop always has a "browse" alternative.

## `C-FILE.view` Viewing

`NOT DRAWN:` "View" opens the checked file in a viewer pop-up (images inline, PDFs paged), built like `C-PREVIEW`. Hidden regions are blacked out in the stored copy of the file, not overlaid in the viewer.

## `C-FILE.reference` Reference (generated)

- Source rules in the prototype: `reference/css/boards/Review.css` (classes: `.frow`, `.files`, `.file`)
- Used on: `S-05`, `S-06B`, `S-R2`
