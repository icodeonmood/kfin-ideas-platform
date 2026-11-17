"""Similar ideas (L-SIMILAR) and the idea preview (A-API.idea-preview), read from the database alone (DEC-106).

- `preview.idea_preview`: the IdeaPreview another person may see of a shared idea. Masked text only, never the
  sharer's raw words (DEC-104, non-negotiable 7); `compare` for the review desk and the committee only.
- `index`: one search chunk per shared idea, built from its database row (title and short summary), never from
  the company repo's idea files.
- `matching`: hybrid retrieval over those chunks, labelled by the `judge` agent through the gateway, or by code
  when the assistant is off; kept in `similar_links`.
"""
