# 17. The docs are built with Zensical

- **Date:** 2026-11-03
- **Status:** accepted
- **Rule:** The docs site is built with Zensical from mkdocs.yml; MkDocs, Material for MkDocs and mkdocs-macros are no
  longer used.

## Context

Material for MkDocs, which first built the site, reaches its end of life on 5 May 2027; Zensical, its successor, reads
mkdocs.yml as it is.

## Decision

mkdocs.yml stays the configuration; `zensical build --strict` builds the site.

## Consequences

Zensical runs define_env once per page, so a macro keeps no state between pages, and it sees less of the page (url,
path, title, meta) than under mkdocs-macros.
