# 11. The editor's schema is the contract, and it only grows

- **Date:** 2026-10-27; changed 2026-11-06
- **Status:** accepted
- **Rule:** The definition, the kit's contract with the editor, only grows: the kit adds fields first, and outside the
  file block the editor ignores those it does not know.

## Context

The kit and the editor change apart: a definition written today is opened the same day in an editor released earlier.

## Decision

The definition (first called the editor's schema) is their contract, and changes are additive: the kit adds fields
first, and the editor ignores those it does not know, except in the container block (`file`), where an unknown kind or
field refuses the definition: a container read in part would be misread, and written wrong. A change that is not
additive (a field removed, renamed or read another way) comes with a new `definition_format`, which an older editor
refuses.

Before 2026-11-06 the contract was `editor/schema.json`, compiled into the editor.

## Consequences

A new field needs no editor release; the full JSON Schema check is the commit hooks' and CI's.
