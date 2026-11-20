# 27. What "unmapped" means, and what stays private

- **Date:** 2026-11-20
- **Status:** accepted
- **Rule:** Which records never changed stays in the mapper's private ledger: the public files say what "unmapped" means
  and never list or count them.

## Context

In the public files, the coverage ledger's public form and the editor's Unmapped records page, "unmapped" read as
"nobody looked", though the mapper's private ledger tells the records no setting covers that held one value in every
download it examined ("unmapped, never seen to change") from those seen to change. Asked "Records never seen to change:
give the 456 of them a truthful public status? I'd say yes, with a decision record.", one of four questions asked
together, the owner answered "Yes to the 4".

A public status per record could not stand. Which records never changed depends on which settings files a mapper kept,
so two owners who map the same model and firmware would get different definitions
([decision 16](0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)); and beside the published sample, a
record listed as never changing tells the value the camera held, the inference
[decision 25](0025-a-proof-says-when-its-list-was-lent-by-another-setting.md) refused for a mark per value. Asked again,
between keeping the status private with the public files saying in words what "unmapped" means (option A) and
publishing the list as an exception written into decision 16 (option B), the owner answered "Never seen to change
option A."

## Decision

Which records no setting covers never changed, and which changed, stays in the mapper's private ledger. The public
files say what "unmapped" means, true of every such record whether it changed or not: the mapping found no menu row that
changes it, so it does not know what the record holds, and a change to it is not proved on the camera and is at the
user's own risk. They never list such records by whether they changed, nor count them, nor say which files the mapping
kept. The editor says it in its own words, the same in the window and the page (`UNMAPPED_WORDS` and
`UNMAPPED_PAGE_WORDS` in `editor/src/schema.rs`), and the data files' page and the editor's guide say it for their
readers.

## Consequences

The definition and the public coverage ledger stay as they were: a record no setting covers is "unmapped" there. A
mapper prints the private status on the computer that holds the runs: `kit/tools/leads.py --write` examines the
downloads, then `kit/tools/coverage.py` prints the counts of each record status ("unmapped, never seen to change",
"changed, no row attributed", "unmapped, not examined"), `--todo` weighs the rows beside them, and `--write` writes the
private form, each record with its status, beside the looks file
(`private/evidence/<model>_fw<fw>/coverage_<model>_fw<fw>.json`). A public list would need decision 16 changed first.
