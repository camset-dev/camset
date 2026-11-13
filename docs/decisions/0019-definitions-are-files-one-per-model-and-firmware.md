# 19. Definitions are files, one per model and firmware

- **Date:** 2026-11-04; carried out 2026-11-06; changed 2026-11-11
- **Status:** accepted
- **Rule:** Camera definitions are files, one per model and firmware, never built into the editor: a camera mapped with
  the kit works the same day, with no new release.

## Context

The editor carried one definition, the ILCE-1M2's at firmware 4.00 (`editor/schema.json`), compiled into the program.
A lay person who maps their own camera with the kit must be able to use the result in the editor the same day,
without building or waiting for a release, and send it in later. With the definition compiled in, the binary carried
camera facts, a new camera needed a new release, and two contributions would edit the same file.

## Decision

Camera definitions are files, never compiled into the editor: `editor/definitions/<model>_fw<firmware>.json`, one
per model and firmware, with one layout (`schemas/definition.schema.json`) and a `definition_format` the editor
refuses when it does not read it. The word is "definition"; `schemas/` keeps meaning JSON Schemas. A definition's
sample, when it has one, is a settings file beside it (`<model>_fw<firmware>.DAT`), made from a file the camera wrote
right after Initialize and scrubbed by `kit/tools/make_sample.py`; neither the editor nor the kit writes it to a
camera. The editor reads the set shipped beside it, read-only, and the user's own folder, where Add definition… copies
a checked file and which overrides the shipped one of the same model and firmware. A file's header, read through each definition's
container block, picks the definition by model and firmware, else the nearest firmware of that model, the records it
does not hold in the mapped shape view-only. The kit writes the definition (`kit/schema_update.py --write`, for the
camera the kit works on, never another's), lean: what the camera is, the same for every owner who maps it, while how
each thing was proved stays in the mapper's private overlay
([decision 16](0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)). A contribution sends it with its data
folder.

Before 2026-11-06 the record left a file's header and the sample to the editor; before 2026-11-11 a definition also
carried how each thing was proved (definition format 1).

## Consequences

- A camera mapped with the kit works in the editor through Add definition…, with no build and no release; a new
  camera or firmware needs no editor release. Contributions add their own files, so they never collide.
- An editor that does not read a definition's format refuses it instead of misreading it: an older editor asks for a
  newer one, and an editor that reads the lean format refuses format 1, saying to write it again with the kit.
- The editor never writes the shipped set, so the signed macOS app stays as it was signed.

See also: [the editor's guide, "Definitions"](../EDITOR.md#definitions) (the two folders, the nearest firmware, Add
definition…), [the data files' page](../DATA_CONTRACTS.md#what-a-mapping-delivers) (what a mapping sends) and
[decision 11](0011-the-editor-s-schema-is-the-contract-and-it-only-grows.md) (a definition only grows).
