# 19. Definitions are files, one per model and firmware

- **Date:** 2026-11-04
- **Status:** accepted; amends [11](0011-the-editor-s-schema-is-the-contract-and-it-only-grows.md); carried out
  2026-11-06; trimmed 2026-11-08: its working notes moved to [the editor's guide](../EDITOR.md#definitions) and
  [the data files' page](../DATA_CONTRACTS.md)

## Context

The editor carries one definition, the ILCE-1M2's at firmware 4.00 (`editor/schema.json`), compiled into the program.
A lay person who maps their own camera with the kit must be able to use the result in the editor the same day,
without building or waiting for a release, and send it in later. With the definition compiled in, the binary carries
camera facts, a new camera needs a new release, and two contributions would edit the same file.

## Decision

Camera definitions are files, never compiled into the editor: `editor/definitions/<model>_fw<firmware>.json`, one
per model and firmware, with one layout (`schemas/definition.schema.json`) and a `definition_format` the editor
refuses when it is newer than it knows. The word is "definition"; `schemas/` keeps meaning JSON Schemas. The editor
reads the set shipped beside it, read-only, and the user's own folder, where Add definition… copies a checked file
and which overrides the shipped one of the same model and firmware. A file's header picks the definition by model
and firmware, else the nearest firmware of that model, the records it does not hold in the mapped shape view-only.
The kit writes the definition, lean, how each thing was proved kept in the mapper's private overlay
([decision 16](0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)); a contribution sends it with its data
folder.

## Consequences

- Decision 11 is amended: the contract is a file per model and firmware rather than `editor/schema.json`. It is
  still additive, and its shape is `schemas/definition.schema.json`.
- A camera mapped with the kit works in the editor through Add definition…, with no build and no release; a new
  camera or firmware needs no editor release. Contributions add their own files, so they never collide.
- An editor older than a definition's format refuses it instead of misreading it.
- An editor that reads the lean format refuses an older definition that carried the mapping's evidence, saying to
  write it again with the kit.
- The shipped set is never written, so the signed macOS app stays as it was signed.
