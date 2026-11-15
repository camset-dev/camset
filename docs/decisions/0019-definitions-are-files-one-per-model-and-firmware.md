# 19. Definitions are files, one per model and firmware

- **Date:** 2026-11-04; carried out 2026-11-06; changed 2026-11-11
- **Status:** accepted
- **Rule:** Camera definitions are files, one per model and firmware, never built into the editor: a camera mapped with
  the kit works the same day, with no new release.

## Context

The editor carried one definition, compiled in: the binary held camera facts, a new camera needed a release, and two
contributions would edit the same file.

## Decision

Definitions are `editor/definitions/<model>_fw<firmware>.json`, with one layout (`schemas/definition.schema.json`) and
a `definition_format` the editor refuses when it does not read it. The editor reads the shipped set, read-only, and
the user's own folder, which Add definition… fills and which overrides a shipped definition of the same model and
firmware. A file's header, read through each definition's container block, picks the definition by model and
firmware, else that model's nearest firmware's, view-only. A sample is a file the camera wrote right after
Initialize, scrubbed by `kit/tools/make_sample.py`, never written to a camera. The kit writes the definition of the
camera it works on, never another's, lean
([decision 16](0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)).

Before 2026-11-11 a definition also carried its evidence (format 1, now refused).

## Consequences

Contributions never collide, and the editor never writes the shipped set, so the signed macOS app stays as signed.
