# 13. Sony's help text stays private

- **Date:** 2026-11-01
- **Status:** accepted; how, since 2026-11-03: [18](0018-one-public-codebase-with-a-private-overlay.md)
- **Rule:** The camera's own help text is Sony's: kept for private use and never published; the proof viewer, which
  shows it, stays local.

## Context

The schema carries the camera's In-Camera Guide text per item and option, read off the camera for private use; it is Sony's.

## Decision

It is kept for private use and stripped before anything is published (docs/RELEASING.md). The proof viewer, which shows it, stays local.

## Consequences

The published schema and the .ksy carry no help text of Sony's. Since 2026-11-03 it is kept in the private
overlay's help file, and the schema's help fields hold the project's own words (decision 18).
