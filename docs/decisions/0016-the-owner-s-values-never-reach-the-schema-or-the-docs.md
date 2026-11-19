# 16. The owner's values never reach the schema or the docs

- **Date:** 2026-10-29; changed 2026-11-19
- **Status:** accepted
- **Never broken:** 13th in AGENTS.md's list
- **Rule:** The owner's values never reach a definition, the data files or the docs, which hold names and value meanings
  only: two owners who map the same model and firmware get the same definition. A value a camera held, and how, when, in
  which run or from which state each thing was proved, stay in the mapper's private evidence; a proof whose label would
  reveal the owner's choice (a picker's saved function) is not planned.

## Context

The definition and the docs are meant to be shared; the owner's settings are not.

## Decision

A label that would reveal the owner's choice is not planned. The test: two owners with different settings who map the
same model and firmware completely get the same public definition. Whatever would differ between them (a value a
camera held; how, when, in which run or from which state the camera was found each thing was proved) stays in the
mapper's private evidence file, beside their runs, never in the definition.

Before 2026-11-19 the Rule line named the definition and the docs but not the data files, and AGENTS.md and the
playbook's rule 10 each stated the rule by hand.

## Consequences

Docs show counts and layouts, never a value from the owner's files. `kit/tools/check_public.py` refuses a definition
whose proofs say more than which values they checked, or that a sampled scale lies on one line
([the data files' page](../DATA_CONTRACTS.md#the-mappings-evidence)).
