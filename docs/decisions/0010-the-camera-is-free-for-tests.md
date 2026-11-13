# 10. The camera is free for tests

- **Date:** 2026-10 (first kit)
- **Status:** accepted
- **Rule:** Camera tests run without asking; the owner is asked only for physical actions (switches, dials, cables) and
  visual checks, and menu routes are tried first.

## Context

Asking before every camera test slowed the work, and the owner can rarely watch.

## Decision

Camera tests run without asking. The owner is asked only for physical actions (switches, dials, cables, turning the camera) and visual checks, and menu routes are tried first (Mode Dial Control Set before the dial).

## Consequences

Every run starts from a known file and ends by restoring it (0015).
