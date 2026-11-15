# 1. Record decisions as ADRs

- **Date:** 2026-11-03; changed 2026-11-13
- **Status:** accepted
- **Rule:** Each decision is one dated record here, stating it as it now stands; a changed decision's record is
  rewritten, with one line on what it said before.

## Context

The rules had drifted apart in three places, and records that amended one another could be read only together.

## Decision

Each decision is one record in Michael Nygard's form, stating it as it stands and reading true on its own (no record
amends another), its Rule the sentence the [decisions table](index.md) shows. A changed decision's record is rewritten
whole, its Date gaining "changed <date>" and its Decision ending with one line beginning "Before"; a rewrite that only
brings a record in line with the code says so there. A safety rule's record (the rules AGENTS.md lists as never broken)
changes only with the maintainer's decision; another camera's owner allows more on their own camera through the
playbook's rules, the defaults for someone else's camera, never by rewriting a record. A record keeps its number and
file name for good; a withdrawn one stays as a stub, its Status "withdrawn <date>", linking to what replaced it.

Before 2026-11-13 a changed decision got a new record superseding the old one.

## Consequences

Documents link to a record rather than restate it; its earlier wordings are in git from 0.2.0 (2026-11-11).
