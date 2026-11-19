# 25. A proof says when its list was lent by another setting

- **Date:** 2026-11-19
- **Status:** accepted
- **Rule:** A public proof lists what was chosen on the camera and what was named from another setting's proof, marking
  the latter once per setting, never per value.

## Context

The review of 2026-11-18 found 16,900 of the a1 II's 24,687 public proved values named by a rule from another
setting's proof (one list of functions proved on one custom key and lent to the others), not chosen on their own
setting, and the editor called every one "checked on the camera". A name a rule gave once was carried from write to
write after the rule stopped giving it; the a1 II's own pass listed 457 names only a hand table gave; and the private
ledger, inferring by a rule of its own, called 11,277 of the same values inferred. Asked on 2026-11-19 for "a mark per
setting so the editor stops calling them 'checked on the camera'", the owner answered "ok". A mark per value would
publish the owner's settings: a setting's one value no proof chose can be the one their camera held
([decision 16](0016-the-owner-s-values-never-reach-the-schema-or-the-docs.md)).

## Decision

A setting's `proved.values` lists the values a proof chose on it, those its own samples or a held not-offered mark
establish, and those a rule named from another setting's proof: a picker's slots, one array's elements, a hold and its
live setting, a copy. Where it lists one of the last kind, the setting carries `proved.shared: true`; which values,
only the private evidence says. Every write names values afresh from that write's proofs and tables, and a value only
a hand table names, no proof and no shared list backing it, is counted, not proved, in both of the writer's passes.
The coverage ledger reads the writer's result (`camkit.definitions.inferred`) instead of inferring by its own rule: its
private form says value by value proved or inferred, its public form "proved or inferred from a shared list" for a
marked setting's listed values. The editor never says such a setting's values were checked on the camera: it says
part of its list was proved on another setting of the same kind.

## Consequences

An older editor ignores the mark ([decision 11](0011-the-editor-s-schema-is-the-contract-and-it-only-grows.md)) and
keeps its old words. A name no rule gives any more leaves the list at the next write, as a hand-table-only name does:
outside Expert mode such a value is hidden until a proof chooses it or a rule names it again. The ledger's shared-list
check ([decision 23](0023-a-ledger-says-what-is-settled-and-a-proof-is-made-once.md)) decides nothing now:
`kit/tools/coverage.py --shared` says where a list's own proof lines do not bear the writer out. The writer's rules
that name from another setting are still several, one per kind of list; one rule over named value sets is later work.
