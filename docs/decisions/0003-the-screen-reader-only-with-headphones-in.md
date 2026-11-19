# 3. The Screen Reader only with headphones in

- **Date:** 2026-11-01; changed 2026-11-19
- **Status:** accepted
- **Never broken:** 2nd in AGENTS.md's list
- **Rule:** The camera's Screen Reader is changed remotely only with headphones in and its volume at the lowest first,
  and only with the owner's word each time: turned On only so, its other settings changed with it Off, and the owner's
  value put back last.

## Context

The Screen Reader speaks every screen aloud, which a remote run cannot hear or stop in time.

## Decision

It is turned On remotely only with headphones plugged in and its Volume at the lowest first. Its other settings are changed with the reader Off, Volume down first, and the owner's value put back last.

Before 2026-11-19 the Rule line named turning the reader On alone, and AGENTS.md and the playbook's rule 1 each stated
the rule by hand, the playbook's leaving the reader free to change while its volume stayed at 0.

## Consequences

Screen Reader runs need the owner's word each time.
