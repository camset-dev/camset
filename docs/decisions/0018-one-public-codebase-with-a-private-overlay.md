# 18. One public codebase, with a private overlay

- **Date:** 2026-11-03; changed 2026-11-11
- **Status:** accepted
- **Rule:** All the code lives in one public repository; what must not be published is data, kept in `private/`, a
  repository of its own beside the code and ignored by it.

## Context

The project is to be kept in two forms: an internal one, with the camera's own help text and the owner's
files, and an open-source one. Copying the code into two repositories would mean every change made twice.
Exporting a cleaned copy from a private repository depends on a list of what to strip, and anything new that
nobody adds to the list leaks.

## Decision

All the code lives in one repository, the public one. What must not be published is data, and it lives in
`private/`: a repository of its own, kept beside the code and ignored by it. The internal version is the same
checkout with that folder present; nothing in the programs tells the two apart but whether the files are there (the
internal macOS app is built with `CAMSET_INTERNAL=1`, into a folder of its own, and never in CI). The code looks in
five places there: `private/config.json` (the kit's settings, `kit/config.example.json` public), `private/help/` (the
camera's own help text, shown in place of the project's own when it is found), `private/camsets/` (real settings
files), `private/data/` (what comes from one's own SDK and camera) and `private/evidence/` (how a mapping proved each
thing: the definition's and the hand tables' evidence, the menu tree, the accepted rulings and the record shapes).

Before 0.2.0 (2026-11-11) the code looked in four places there, `private/evidence/` not among them; the record named
the fifth, and the internal build, from 2026-11-13.

## Consequences

- A code change is made once. A change touching code and private data is two commits, one in each repository.
- `kit/tools/check_public.py`, run by pre-commit and on every pull request, refuses a commit that would publish what
  is private.
- The public repository was published with a fresh history, its first commit 0.2.0's: the old one held the private
  files.
- `runs/` and the Sony Camera Remote SDK are in neither repository.

See also: [the data files' page](../DATA_CONTRACTS.md) (the help files and the evidence files),
`kit/tools/check_public.py`'s docstring (what the guard refuses) and
[decision 13](0013-sony-s-help-text-stays-private.md) (Sony's help text).
