# 23. A ledger says what is settled, and a proof is made once

- **Date:** 2026-11-14
- **Status:** accepted
- **Rule:** A ledger generated from what exists gives each row, value and record one status; runs only print it unless
  given --skip-settled; one valid proof is enough.

## Context

By 2026-11-14 the a1 II's mapping (89 crawls, 8,154 proof lines) had no place to ask what was known: a row found to
change nothing lived in a run's log, a kit failure looked like a camera fact, and work was done twice. The maintainer
asked for a list of what is mapped and what was tested and shows no mapping, and judged repeated proofs useless: "If
they are all bad it's not a prove." The hazards: a public ledger built from the mapper's looks would carry the owner's
state (a network row's saved option, whose proof changes nothing; a row greyed with its blocker as it stood; the lens
the owner had; a kit commit's failures), one edited by hand could not be told from its sources, a row "proved" on a few
values would hide thousands untried, and skipping by default would leave holes nobody asked for.

## Decision

The coverage ledger (`kit/camkit/coverage.py`) gives every menu row, setting value and file record one status, the
first that applies in a fixed order, generated each time from the sources that exist; what a look found goes into the
camera's private looks file, never with a value. Its public form is built from the public sources alone and the seen
file, which holds only what a look establishes for every camera of the model
([decision 16](0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)): two owners' public forms differ only
in which of those facts they looked for, never in what a fact says. Runs only print what it says unless
the crawl or the prover is given `--skip-settled`; `kit/drive.py` never skips. A row with values still to try is never
settled, and one valid proof of an option is enough.

## Consequences

`kit/tools/check_public.py` refuses a public form that is not, byte for byte, the build of the public sources and the
seen file. "Valid" claims only what the proof records; proofs are made as before; each is marked valid, inferred or
unchecked, and none is deleted, until the owner decides what to keep. The statuses, the files and the validity rule:
[the data files' page](../DATA_CONTRACTS.md#the-coverage-ledger-what-is-settled-and-what-a-proof-needs).
