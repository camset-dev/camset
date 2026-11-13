# 1. Record decisions as ADRs

- **Date:** 2026-11-03; changed 2026-11-13
- **Status:** accepted
- **Rule:** Each decision is one dated record here, stating it as it now stands; a changed decision's record is
  rewritten, with one line on what it said before.

## Context

The owner's rules and the project's choices were written in three places that had drifted apart: the kit plan's
standing rules (stale: they still forbade Auto Power OFF Temp.), the playbook and the agents' notes. Records that were
never rewritten then drifted from each other: several could be understood only beside later records, applying their
amendments in one's head.

## Decision

Each decision is one Architecture Decision Record here: a title, its Date, its Status and its Rule (the decision in
one plain sentence, which the [decisions table](index.md) shows), then context, decision and consequences, as in
Michael Nygard's form. A record states the decision as it stands and reads true on its own; where a reader needs a
neighbouring record, it links to it ("See also"). No record amends another.

When a decision changes, its record is rewritten in place to state the current decision whole, its Rule line
included: its Date gains "changed <date>", and one line at the end of its Decision, beginning "Before", says what it
said until then; a rewrite that only brings a record in line with the code says so there. Its Context keeps why the
rule exists and, where it changed, why. A safety rule's record (the rules AGENTS.md lists as never broken) changes
only with the maintainer's decision (the a1 II's owner, whose decisions these records hold); another camera's owner
allows more on their own camera through the playbook's rules, never by rewriting a record. A withdrawn decision keeps its file as a short stub, its Status "withdrawn <date>",
saying so and linking to what replaced it. A record keeps its number and its file name for good: other documents link
to them. Git keeps a record's earlier wordings from 0.2.0 (2026-11-11), where the public history begins, unless that
history is replaced again to take something private out.

This departs from Nygard's practice on purpose: there a record is never edited, and a changed decision gets a new
record that supersedes the old one; here each decision is read whole in one record, and the table gives each rule as
it stands.

Before 2026-11-13 a record was never rewritten: a changed decision got a new record that superseded the old one.

## Consequences

- Other documents link to a record instead of restating it. The playbook keeps its own rules: they are the defaults
  for someone else's camera, not this owner's decisions.
- A record's earlier wordings are read in git (`git log -p` on its file, from 0.2.0 on), not in the record, whose one
  "Before" line says only what changed and when.
