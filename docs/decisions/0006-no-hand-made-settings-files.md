# 6. No hand-made settings files

- **Date:** 2026-11-01
- **Status:** accepted

## Context

A file edited by hand boot-looped Movie mode on 2026-11-01.

## Decision

Settings are changed on the camera and watched; only files the camera wrote (downloads) are uploaded. Link.upload refuses anything outside a run's dat/ folder.

2026-11-05: the folder was not enough (pass 3's file switching wrote values into a file in `dat/` and uploaded it), so `Link.upload` now checks provenance: every download's SHA-256 goes into a manifest, `runs/downloads.jsonl` (`kit/camkit/provenance.py`), and `Link.upload` and `kit/tools/upload_check.py` send a file only when its bytes are a download's, wherever it sits. `upload_check.py --adopt` takes in older downloads that a run's log recorded, at the logged size and unchanged since. Pass 3's switching by file is retired.

## Consequences

Values a menu cannot reach stay unproved or are proved by what the camera itself writes (a reset, a registration).
