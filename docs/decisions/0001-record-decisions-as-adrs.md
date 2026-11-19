# 1. Record decisions as ADRs

- **Date:** 2026-11-03; changed 2026-11-13 and 2026-11-19
- **Status:** accepted
- **Rule:** Each decision is one dated record here, stating it as it now stands; a changed decision's record is
  rewritten, with one line on what it said before.

## Context

The rules had drifted apart in three places, and records that amended one another could be read only together.

## Decision

Each decision is one record in Michael Nygard's form, stating it as it stands and reading true on its own (no record
amends another), its Rule what the [decisions table](index.md) shows: the decision in one sentence, or, for a rule
that is never broken, the whole rule as an agent obeys it, which AGENTS.md lists. A changed decision's record is
rewritten whole, its Date gaining "changed <date>" and its Decision ending with one line beginning "Before"; a rewrite
that only brings a record in line with the code says so there. A safety rule's record (one marked Never broken, whose
Rule AGENTS.md lists) changes only with the maintainer's decision; its Rule is the default for every camera, and another
camera's owner allows more on their own camera as the playbook's section 1 says, never by rewriting a record. A record
keeps its number and file name for good; a withdrawn one stays as a stub, its Status "withdrawn <date>", linking to
what replaced it.

Before 2026-11-19 every Rule was one sentence, the playbook's rules were the defaults for someone else's camera, and
AGENTS.md restated the safety rules by hand.
Before 2026-11-13 a changed decision got a new record superseding the old one.

## Consequences

Documents link to a record rather than restate it; its earlier wordings are in git from 0.2.0 (2026-11-11).
