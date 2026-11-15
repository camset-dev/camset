# 6. No hand-made settings files

- **Date:** 2026-11-01; changed 2026-11-05 and 2026-11-08
- **Status:** accepted
- **Rule:** The kit, and whoever maps a camera, changes settings on the camera, never by editing a file, and uploads
  only files the camera wrote, checked by their bytes.

## Context

A file edited by hand boot-looped the a1 II in Movie mode on 2026-11-01, and pass 3's switching by file later uploaded
a file it had written values into.

## Decision

Settings are changed on the camera and watched. A file, wherever it sits, is uploaded only when its bytes are one of
that camera's downloads, whose SHA-256s `runs/<model>_fw<fw>/downloads.jsonl` keeps; pass 3's switching by file is
retired. The editor, made to write a file its user edited, is not bound by this; a mapping, or an agent working for an
owner, never writes one through it.

Before 2026-11-05 the kit checked a file's folder, not its bytes; camlink has checked them too since 2026-11-08.

## Consequences

Values a menu cannot reach stay unproved or are proved by what the camera itself writes (a reset, a registration).
