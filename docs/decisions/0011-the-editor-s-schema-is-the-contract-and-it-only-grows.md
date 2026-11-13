# 11. The editor's schema is the contract, and it only grows

- **Date:** 2026-10-27
- **Status:** accepted; amended by [19](0019-definitions-are-files-one-per-model-and-firmware.md) (the contract is a
  definition file per model and firmware, its shape `schemas/definition.schema.json`) and
  [20](0020-the-editor-holds-no-camera-facts.md) (inside `camera.file` a kind the editor does not know refuses the
  definition)
- **Rule:** The contract between kit and editor only grows: the kit adds fields first, and the editor ignores fields it
  does not know and catches up later.

## Context

The kit was rebuilt from scratch; the editor and the kit had to keep working together while both changed.

## Decision

editor/schema.json is the contract between them. Changes are additive: the kit adds fields first, the editor ignores fields it does not know and catches up later. Its shape is schemas/camset-schema.schema.json.

## Consequences

A new field needs no editor release; removing or renaming one does.
