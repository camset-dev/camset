# 13. Sony's help text stays private

- **Date:** 2026-11-01; changed 2026-11-03
- **Status:** accepted
- **Rule:** The camera's own help text is Sony's: kept for private use and never published; the proof viewer, which
  shows it, stays local.

## Context

The kit reads the camera's In-Camera Guide text off the camera, for private use; it is Sony's.

## Decision

It stays in one's own `private/help/`, never in a definition, a data file or the docs. A definition's help fields hold
the project's own words, which the editor and the proof viewer replace with the private text where they find it.

Before 2026-11-03 the schema carried that text, stripped before anything was published.

## Consequences

`kit/tools/check_public.py` refuses a commit whose help text stays too close to the camera's own, as far as the clone's
`private/help/` lets it compare.
