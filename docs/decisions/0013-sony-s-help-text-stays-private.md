# 13. Sony's help text stays private

- **Date:** 2026-11-01; changed 2026-11-03
- **Status:** accepted
- **Rule:** The camera's own help text is Sony's: kept for private use and never published; the proof viewer, which
  shows it, stays local.

## Context

The kit reads the camera's In-Camera Guide text per item and option off the camera, for private use; it is Sony's.

## Decision

It is kept in one's own `private/help/`, never in a definition, a data file or the docs. A definition's help fields
hold the project's own words (`data/<model>_fw<fw>/help_<model>_fw<fw>.json`), and the editor and the proof viewer show
the private text in their place where they find it. The proof viewer, which shows it, stays local.

Before 2026-11-03 the schema carried that text itself, stripped before anything was published.

## Consequences

The published definitions and the .ksy carry no help text of Sony's, and `kit/tools/check_public.py` refuses a commit
whose help text stays too close to the camera's own, as far as the clone's `private/help/` lets it compare.

See also: [decision 18](0018-one-public-codebase-with-a-private-overlay.md) (the private overlay) and
[RELEASING](../RELEASING.md) (what the project publishes under the SDK's terms).
