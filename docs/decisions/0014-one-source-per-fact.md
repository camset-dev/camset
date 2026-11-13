# 14. One source per fact

- **Date:** 2026-11-03
- **Status:** accepted; its docs builder superseded by [17](0017-the-docs-are-built-with-zensical.md)
- **Rule:** Each fact is edited in one place; documents are rendered from their sources, and the few generated files
  that are committed are regenerated before each commit.

## Context

The same facts had drifted in several places: the camera facts in two files, counts in four documents, generated documents from a retired kit, a README pointing at removed commands.

## Decision

Each fact is edited in one place (README, "Where each fact lives"; on the docs site's home page, `docs/index.md`, from 2026-11-04; on its own page, [Where each fact lives](../WHERE_FACTS_LIVE.md), since 2026-11-09). Documents are rendered from their sources with MkDocs (mkdocs-macros), the format's one source is the Kaitai spec, the data files have JSON Schemas, and pre-commit regenerates the few generated files that are committed.

## Consequences

No generated page is committed; a new generated file goes into kit/tools/build_docs.py and the pre-commit hook.
