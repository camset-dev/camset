# 23. A ledger says what is settled, and a proof is made once

- **Date:** 2026-11-14; changed 2026-11-18 and 2026-11-19
- **Status:** accepted
- **Rule:** A generated ledger gives each row, value and record one status, an inferred value never proved; runs print
  it unless given --skip-settled; one proof is enough.

## Context

By 2026-11-14 the a1 II's mapping (89 crawls, 8,154 proof lines) had no place to ask what was known: a row found to
change nothing lived in a run's log, a kit failure looked like a camera fact, and work was done twice. The maintainer
asked for a list of what is mapped and what was tested and shows no mapping, and judged repeated proofs useless: "If
they are all bad it's not a prove." The hazards: a public ledger built from the mapper's looks would carry the owner's
state (a network row's saved option, whose proof changes nothing; a row greyed with its blocker as it stood; the lens
the owner had; a kit commit's failures), one edited by hand could not be told from its sources, a row "proved" on a few
values would hide thousands untried, and skipping by default would leave holes nobody asked for. On 2026-11-18 about
15,700 values were left, nearly all on slots sharing one list whose codes a proof had shown on another slot; proving
each would take hours of camera time, and the maintainer chose: "Skip the functions if we can infer, keep mapping".
On 2026-11-19 the ledger's inference and the definition writer's were found to be two rules with different criteria,
each inferring over the other's output, and the owner chose one rule and a mark per setting
([decision 25](0025-a-proof-says-when-its-list-was-lent-by-another-setting.md)).

## Decision

The coverage ledger (`kit/camkit/coverage.py`) gives every menu row, setting value and file record one status, the
first that applies in a fixed order, generated each time from the sources that exist; what a look found goes into the
camera's private looks file, never with a value. Its public form is built from the public sources alone and the seen
file, which holds only what a look establishes for every camera of the model
([decision 16](0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)): two owners' public forms differ only
in which of those facts they looked for, never in what a fact says. Runs only print what it says unless
the crawl or the prover is given `--skip-settled`; `kit/drive.py` never skips. A row with values still to try is never
settled, and one valid proof of an option is enough. A value no proof chose on its own setting counts as inferred, in
the private form alone and never as proved, where the definition's writer named it from another setting's proof, a
shared list (`camkit.definitions.inferred`): the ledger reads that and infers nothing by a rule of its own. The public
form, which has only the definition's mark on such a setting, calls each value its proof lists "proved or named from a
shared list". A row of no setting that a proof went through holds the setting that proof proved.

Before 2026-11-19 the ledger inferred a value itself (one proved on another setting listing the same values on its row
or array, two values on its own record as the list names them, no proof reading it as another), and before 2026-11-18
a value counted only once a proof chose it on its own setting, such a row not yet tried.

## Consequences

`kit/tools/check_public.py` refuses a public form that is not, byte for byte, the build of the public sources and the
seen file. "Valid" claims only what the proof records; proofs are made as before; each is marked valid, inferred or
unchecked, and none is deleted, until the owner decides what to keep. `kit/tools/coverage.py --shared` shows each
shared list's grounds, what no slot of it proves, and where the list's own proof lines do not bear the writer's
inference out, which decides nothing. The statuses, the files and the validity rule:
[the data files' page](../DATA_CONTRACTS.md#the-coverage-ledger-what-is-settled-and-what-a-proof-needs).
