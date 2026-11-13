# 15. Every run starts from a known file and ends restoring it

- **Date:** 2026-10 (first kit)
- **Status:** accepted
- **Rule:** A run saves the camera's settings first and restores them at its end, checking nothing differs; it is
  stopped with a STOP file, never killed with a dialog open.

## Context

A run that crashes before its restore leaves the next run starting from its leftovers, and some state lives outside the file (the focus point, the zone's place).

## Decision

A run downloads a start file first and, at its end, uploads it and checks that 0 records differ; live state the file does not hold is put back by hand and checked. A run is never killed with a dialog open: it is stopped with a STOP file.

## Consequences

The owner's camera is as it was after every session.
