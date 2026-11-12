# 18. One public codebase, with a private overlay

- **Date:** 2026-11-03
- **Status:** accepted; trimmed 2026-11-08: its working notes moved to [the data files' page](../DATA_CONTRACTS.md)
  (the help files) and `kit/tools/check_public.py`'s docstring (what the guard refuses); its inventory of the
  maintainers' own files left the public record

## Context

The project is to be kept in two forms: an internal one, with the camera's own help text and the owner's
files, and an open-source one. Copying the code into two repositories would mean every change made twice.
Exporting a cleaned copy from a private repository depends on a list of what to strip, and anything new that
nobody adds to the list leaks.

## Decision

All the code lives in one repository, the public one. What must not be published is data, and it lives in
`private/`: a repository of its own, kept beside the code and ignored by it. The internal version is the same
checkout with that folder present; nothing in the code tells the two apart but whether the files are there. The code
looks in four places there: `private/config.json` (the kit's settings, `kit/config.example.json` public),
`private/help/` (the camera's own help text, shown in place of the project's own when it is found),
`private/camsets/` (real settings files) and `private/data/` (what comes from one's own SDK and camera).

## Consequences

- A code change is made once. A change touching code and private data is two commits, one in each repository.
- `kit/tools/check_public.py`, run by pre-commit and on every pull request, refuses a commit that would publish what
  is private.
- The public repository needs a fresh history before it is published: the old one holds the private files.
- `runs/` and the Sony Camera Remote SDK are in neither repository.
