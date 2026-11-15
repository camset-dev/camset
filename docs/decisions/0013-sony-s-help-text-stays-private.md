# 13. Sony's help text stays private

- **Date:** 2026-11-01; changed 2026-11-03 and 2026-11-14
- **Status:** accepted
- **Rule:** The camera's own help text and Sony's published Help Guide are Sony's: kept for private use and never
  published; the proof viewer, which shows it, stays local.

## Context

The kit reads the camera's In-Camera Guide text off the camera, for private use; it is Sony's.

## Decision

It stays in one's own `private/help/`, never in a definition, a data file or the docs. A definition's help fields hold
the project's own words, which the editor and the proof viewer replace with the private text where they find it.
Sony's published Help Guide is Sony's too: help is never copied from it, notes from it stay in `private/`, and `data/`
keeps only its menu list (each item's tab, group, name and modes).

Before 2026-11-14 the record named only the camera's own text; the Help Guide rule stood in the contribution rules;
before 2026-11-03 the schema carried that text, stripped before anything was published.

## Consequences

`kit/tools/check_public.py` refuses a commit whose help text stays too close to the camera's own, as far as the clone's
`private/help/` lets it compare.
