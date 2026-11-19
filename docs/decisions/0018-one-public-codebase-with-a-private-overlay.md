# 18. One public codebase, with a private overlay

- **Date:** 2026-11-03; changed 2026-11-11 and 2026-11-19
- **Status:** accepted
- **Rule:** All the code lives in one public repository; what must not be published is data, kept in `private/`, a
  repository of its own beside the code and ignored by it.

## Context

The project is kept in two forms, an internal one (with the camera's own help text and the owner's files) and an open
one. Two copies of the code would mean every change made twice; a cleaned export leaks whatever nobody adds to its
list of what to strip.

## Decision

The internal version is the same checkout with `private/` present, and nothing in the programs tells the two apart
but whether its files are there (the internal macOS app is built with `CAMSET_INTERNAL=1`, into a folder of its own,
never in CI). The code looks in six places there:
`private/config.json`, `private/help/` (the camera's own help text), `private/camsets/` (real settings files),
`private/data/` (from one's own SDK and camera), `private/evidence/` (a mapping's evidence) and `private/lut/` (the user
LUTs `kit/tools/lut_import.py` may import, [decision 26](0026-a-user-lut-reaches-the-camera-only-through-the-kit-s-import-tool.md)).

Before 2026-11-19 `private/lut/` was not among them; before 0.2.0 (2026-11-11), `private/evidence/`.

## Consequences

A change touching code and private data is two commits. `kit/tools/check_public.py` refuses a commit that would
publish what is private. `runs/` and Sony's SDK are in neither repository.
