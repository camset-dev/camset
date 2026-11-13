# 6. No hand-made settings files

- **Date:** 2026-11-01; changed 2026-11-05 and 2026-11-08
- **Status:** accepted
- **Rule:** The kit, and whoever maps a camera, changes settings on the camera, never by editing a file, and uploads
  only files the camera wrote, checked by their bytes.

## Context

A file edited by hand boot-looped Movie mode on 2026-11-01. A check by folder was then not enough: pass 3's switching
by file wrote values into a file in a run's `dat/` folder and uploaded it.

## Decision

This binds the kit and whoever maps a camera. Settings are changed on the camera and watched; only files the camera
wrote (its downloads) are uploaded, known by their bytes. Every download's SHA-256 goes into the camera's manifest,
`runs/<model>_fw<fw>/downloads.jsonl` (`kit/camkit/provenance.py`), and `Link.upload` and `kit/tools/upload_check.py`
send a file only when its bytes are a download of that camera's, wherever it sits; camlink sends the bytes only when
they have the SHA-256 the kit checked, so a file swapped in after the check is never sent. `upload_check.py --adopt`
takes in older downloads that a run's log recorded, at the logged size and unchanged since. Pass 3's switching by file
is retired. The editor, which exists to write a file its user edited, is not bound by it: its user writes such a file
by their own hand, at their own risk, as the README's warning and its write window say; it never writes its sample. A
mapping, or an agent working for an owner, never writes an edited file through the editor either.

Before 2026-11-05 `Link.upload` refused only a file outside a run's `dat/` folder; before 2026-11-08 camlink sent the
file without checking its bytes against the kit's SHA-256; the manifest began as one file for every camera,
`runs/downloads.jsonl`, and was per camera by 0.1.0 (2026-11-09); the record named the per-camera manifest, and said
where the editor stands, from 2026-11-13.

## Consequences

Values a menu cannot reach stay unproved or are proved by what the camera itself writes (a reset, a registration).
