# 23. A ledger says what is settled, and a proof is made once

- **Date:** 2026-11-14
- **Status:** accepted
- **Rule:** A ledger generated from what exists gives each row, value and record one status; runs only print it unless
  given --skip-settled; one valid proof is enough.

## Context

By 2026-11-14 the a1 II's mapping had 89 crawls, 8,154 proof lines, 2,789 downloads and sessions of looks on the
Network tab, and no place a later session could ask what was already known. A row tested and found to change nothing
lived in one crawl lap's "0 records differ", in a run's own `drive.jsonl` or in the log's prose; a row refused in a
state kept its blocker only in old runs or prose; a kit failure looked like a camera fact; Sony's Save/Load list was
prose in a table cell of the model page. Work was done twice: rows looked at again, options proved again in the same
state. The maintainer asked for "a list of values that are mapped, values that have been tested and show no mapping,
plus whatever else makes sense so we aren't going back and doing double work", and of repeated proofs: "Multiple
proves don't really provide a benefit do they? If they are all bad it's not a prove."

Such a ledger has its own hazards. Built from the mapper's looks, scans, crawls and proofs, a public form would carry
the owner's state: a network row's saved option (its proof changes nothing), a row greyed with its blocker as it stood,
the lens the owner had, a kit commit's failures. A row "proved" on a few of its values would hide thousands untried;
a look at an unclassified screen, or the Enter that opens a row, would pass for an answer; a run that skipped by
default would leave holes where nobody asked for them, and a public form edited by hand could not be told from one
the sources give.

## Decision

The coverage ledger (`kit/camkit/coverage.py`, `kit/tools/coverage.py`) gives every menu row, every value of every
setting and every record of the file exactly one status, the first that applies in a fixed order of precedence
(proved, proved by hand, sampled, not offered, not in the settings file (Sony), information screen, action, tested
with no record changes, needs equipment, no proof possible, greyed in state, kit cannot read, closed by rule, not yet
tried; a record's from proved to unmapped). It is generated each time from the sources that exist, so it cannot
drift. What no source held, what a look found, is recorded in one private, append-only file, the camera's looks file,
which `kit/drive.py`, `kit/crawl_run.py`, `kit/prove_run.py` and `kit/tools/coverage.py --record` write, never with a
value; the latest look of a row, what was done and the option wins (a look that did not reach the row never takes the
place of one that did), and `--record --result retract --did <what>` withdraws one. Sony's Save/Load list is data in
the camera file (`save_load_excluded`, which a definition never carries).

It has two forms. The public one, in the camera's data folder, is built from the public sources alone (the definition,
the hand tables, the camera file, the Help Guide's list, `camkit.safety`) and a short allow-list of what a look
establishes that holds for every camera of the model: that a row opens an information screen, and the kit's address
field names it showed (a row label beside them qualifies a look privately only); that a row acted when opened; that a
hand check changed a record; that a row on Sony's list was seen to change nothing ("confirmed"). Those facts are kept
in a small public file of their own, the seen file, which `--write` writes where the looks file is (its facts with the
looks' own, a retraction of the looks taking one out); the public form is always, byte for byte, the build of the
public sources and that file. Nothing observed of the camera's state goes public: no "tested, no record changes", no
"greyed in state" but the definition's own `inactive_when`, no "needs equipment" but an `unproved_reason`'s, no "kit
cannot read". Two owners who map the body therefore differ only in which allow-listed facts they have looked for,
never in what a fact says, as [decision 16](0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md) asks. The
private one, beside the looks file, is the full build: each status's citations, the proofs' validity and their
evidence bundles.

Runs ask it before they press on a row and, by default, only print what it says, from one build a run, reading no
download and asking git nothing for a row they will not skip. `kit/crawl_run.py` and
`kit/prove_run.py` given `--skip-settled` leave a settled row out (a prover only a list or dialog row whose every
planned option is settled, and never in a switched state, a table, a grid, a look or a `--redo`); `kit/drive.py` never
skips. A row with values still to try is never settled; a row greyed before is settled only while the start file
still greys it, a row the kit could not read only for a failure that comes again (an unknown screen, no response to
Right) and only on the same kit commit; nothing is settled while the ledger cannot be built or is stale, and a ledger
error never breaks a run. A proof counts as valid when its diff is the row's own records, two independent readings
recorded in it name the option alike, and across the row each option writes its own value into the row's records, as
many as the walked list offers; the proof that chooses the saved option again is inferred, never valid. One valid
proof of an option is enough: its evidence is kept as one bundle, and a repeat adds nothing.

## Consequences

- A session starts from `kit/tools/coverage.py --todo` (the playbook's section 7), which lists every row in a status
  still to work and every row with values still to try. What the three runners do by default is unchanged: they print
  the ledger's word on each row they handle, and skip only when told to. A crawl given `--skip-settled` has holes in
  its own `map.json`, so a crawl meant to build pass 1's map never skips (`kit/pass1_map.py` refuses such a crawl).
- After `kit/schema_update.py --write`, `kit/tools/coverage.py --write` brings the public form in step.
  `kit/tools/check_public.py` (and a test, and `--check`) refuses a public form that is not, byte for byte, the build of
  the public sources and the seen file, so an edit by hand of a status, an equipment or a field is refused, and an
  edit of a fact shows in review as a change to the seen file alone; it refuses either file where it breaks its schema,
  holds a run, a date, a hash or a key of evidence, or a word outside its closed vocabulary.
- A run that only prints pays for one private build before it connects (about half a second at the a1 II's scale) and
  next to nothing a row; a `--skip-settled` run judges a greyed row by reading two downloads and a row the kit could
  not read by asking git.
- "Valid" claims only what the proof records: its diff, its readings, the values beside its row's other proofs. It
  does not claim the option's meaning in another state, that no other record moves elsewhere, or anything of the
  saved option's value beyond the start file's. The proofs are not made differently yet: the rule reads what proofs
  already record, marks each proof valid, inferred or unchecked (naming the condition missing), counts repeats, and
  `--bundles` shows which frames and downloads back a valid proof, deleting nothing, for a later decision of the
  owner's on what to keep.

See also: [the data files' page, "The coverage ledger"](../DATA_CONTRACTS.md#the-coverage-ledger-what-is-settled-and-what-a-proof-needs)
(the files, the statuses, the proof-validity rule), [decision 14](0014-one-source-per-fact.md) (one source per fact)
and [decision 18](0018-one-public-codebase-with-a-private-overlay.md) (the private overlay).
