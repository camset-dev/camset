# 11. The editor's schema is the contract, and it only grows

- **Date:** 2026-10-27; changed 2026-11-06
- **Status:** accepted
- **Rule:** The definition, the kit's contract with the editor, only grows: the kit adds fields first, and outside the
  file block the editor ignores those it does not know.

## Context

The kit was rebuilt from scratch; the editor and the kit had to keep working together while both changed. They still
change apart: a definition the kit writes today is opened the same day in an editor released earlier.

## Decision

The camera definition is the contract between them (the editor's schema, as it was first called): one file per model
and firmware, `editor/definitions/<model>_fw<fw>.json`, its shape `schemas/definition.schema.json`. Changes are
additive: the kit adds fields first, and the editor ignores fields it does not know and catches up later. The camera
section's `file`, the container block, is the exception: there a kind or a field the editor does not know refuses the
definition instead of being ignored, since a container read with a part of it left out would be misread, and written
wrong. A change that is not additive (a field removed, renamed or read another way) comes with a new
`definition_format`.

Before 2026-11-06 the contract was one file compiled into the editor, `editor/schema.json`, its shape
`schemas/camset-schema.schema.json`, and the editor ignored every field it did not know.

## Consequences

- A new field needs no editor release: an older editor opens a definition that carries it, and shows what it knows.
- Removing or renaming a field needs an editor release and a new `definition_format`: an editor refuses a format newer
  than it reads, saying it needs a newer Camset Editor, and one that reads the lean format (2) refuses format 1,
  saying to write the definition again with the kit.
- The editor checks a definition as it loads it (its format, then the typed reading of its fields); the full JSON
  Schema check is the commit hooks' and CI's ([the data files' page](../DATA_CONTRACTS.md)).

See also: [decision 19](0019-definitions-are-files-one-per-model-and-firmware.md) (where the definitions live and how
the editor picks one) and [decision 20](0020-the-editor-holds-no-camera-facts.md) (what only the definition holds,
the container block among it).
