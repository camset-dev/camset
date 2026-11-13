# 5. Settings resets for proofs: the narrowest, never Initialize

- **Date:** 2026-11-01
- **Status:** accepted
- **Rule:** For a proof, only the narrowest reset (Camera Settings Reset), the owner's file put back after; Initialize
  and Reset Network Set. are never pressed.

## Context

Some records only a reset writes. Initialize and Reset Network Set. also wipe the network setup and access authentication, which takes the camera off the link.

## Decision

Camera Settings Reset, the narrowest reset that does the job, is allowed for proofs, with the owner's file put back after. Initialize and Reset Network Set. are never pressed: drive.py refuses Enter while either is lit.

## Consequences

A reset run ends with the start file uploaded and checked (0 records differ).
