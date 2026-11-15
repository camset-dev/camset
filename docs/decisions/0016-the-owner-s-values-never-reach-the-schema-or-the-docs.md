# 16. The owner's values never reach the schema or the docs

- **Date:** 2026-10-29
- **Status:** accepted
- **Rule:** The definition and the docs hold names and meanings only, never the owner's values: two owners who map the
  same model and firmware get the same definition.

## Context

The definition and the docs are meant to be shared; the owner's settings are not.

## Decision

A label that would reveal the owner's choice is not planned. The test: two owners with different settings who map the
same model and firmware completely get the same public definition. Whatever would differ between them (a value a
camera held; how, when, in which run or from which state the camera was found each thing was proved) stays in the
mapper's private evidence file, beside their runs, never in the definition.

## Consequences

Docs show counts and layouts, never a value from the owner's files. `kit/tools/check_public.py` refuses a definition
whose proofs say more than which values they checked, or that a sampled scale lies on one line
([the data files' page](../DATA_CONTRACTS.md#the-mappings-evidence)).
