# 4. Never delete or format the cards

- **Date:** 2026-11-01
- **Status:** accepted
- **Rule:** No Format or Delete is ever sent remotely, and Playback > Delete is never opened: card actions are the
  owner's, by hand.

## Context

The owner: "Please don't delete the cards." Format and Delete cannot be undone, and Playback's C4 deletes.

## Decision

No Format or Delete is ever sent remotely, and Playback > Delete is never opened. drive.py refuses a Format or Delete label even with --allow.

## Consequences

Card actions are the owner's, by hand.
