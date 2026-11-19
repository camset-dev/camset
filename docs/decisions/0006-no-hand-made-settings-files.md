# 6. No hand-made settings files

- **Date:** 2026-11-01; changed 2026-11-05, 2026-11-08, 2026-11-14 and 2026-11-19
- **Status:** accepted
- **Never broken:** 5th in AGENTS.md's list
- **Rule:** No hand-made settings files: the kit, and whoever maps a camera, changes settings on the camera and watches,
  never by editing a file, and uploads only files that camera wrote, each checked by its bytes against that camera's own
  downloads, wherever it sits. The editor, which writes a file its user edited, is that user's: a mapping, or an agent
  working for an owner, never writes a file through it.

## Context

A file edited by hand boot-looped the a1 II in Movie mode on 2026-11-01, and pass 3's switching by file later uploaded
a file it had written values into.

## Decision

Settings are changed on the camera and watched. A file, wherever it sits, is uploaded only when its bytes are one of
that camera's downloads, whose SHA-256s `runs/<model>_fw<fw>/downloads.jsonl` keeps; pass 3's switching by file is
retired. The editor, made to write a file its user edited, is not bound by this; a mapping, or an agent working for an
owner, never writes one through it.

Before 2026-11-19 AGENTS.md and the playbook's rule 12 each stated the rule by hand beside a shorter Rule line.
Before 2026-11-05 the kit checked a file's folder, not its bytes; camlink has checked them too since 2026-11-08; before 2026-11-14 the record did not name those rows, which `kit/camkit/safety.py` already refused.

## Consequences

Values a menu cannot reach stay unproved or are proved by what the camera itself writes (a reset, a registration).
