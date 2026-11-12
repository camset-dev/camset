# 17. The docs are built with Zensical

- **Date:** 2026-11-03
- **Status:** accepted; supersedes the builder named in [14](0014-one-source-per-fact.md)

## Context

The site was first built with MkDocs and Material for MkDocs, which reaches its end of life on 5 May 2027.
Zensical is its successor from the same team. It reads mkdocs.yml as it is and has the macros the rendered
pages need (module_name, define_env, render_by_default and a page's own override, since 0.0.40).

## Decision

The docs are built with Zensical (`zensical serve`, `zensical build --strict`). mkdocs.yml stays the
configuration; MkDocs, Material for MkDocs and mkdocs-macros are no longer used.

## Consequences

Zensical runs define_env once per page, not once per build, so a macro keeps no state between pages; ours keep
none. Its macros expose less of the page (url, path, title, meta) than mkdocs-macros did.
