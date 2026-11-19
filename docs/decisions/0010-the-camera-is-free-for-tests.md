# 10. The camera is free for tests

- **Date:** 2026-10 (first kit); changed 2026-11-19
- **Status:** accepted
- **Never broken:** 11th in AGENTS.md's list
- **Rule:** The camera is free for tests, which run without asking: the owner is asked only for physical actions
  (switches, dials, turning the camera, cables, opening the screen, by-hand menu actions and resets) and visual checks,
  and menu routes are tried first.

## Context

Asking before every camera test slowed the work, and the owner can rarely watch.

## Decision

Camera tests run without asking. The owner is asked only for physical actions (switches, dials, cables, turning the camera) and visual checks, and menu routes are tried first (Mode Dial Control Set before the dial).

Before 2026-11-19 AGENTS.md and the playbook's rule 11 each stated the rule by hand beside a shorter Rule line.

## Consequences

Every run starts from a known file and ends by restoring it (0015).
