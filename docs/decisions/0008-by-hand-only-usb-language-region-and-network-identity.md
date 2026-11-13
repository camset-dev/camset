# 8. By hand only: USB, language, region and network identity

- **Date:** 2026-10 (first kit); changed 2026-11-02 and 2026-11-11
- **Status:** accepted
- **Rule:** USB, Language, NTSC/PAL, Area/Date and network identity are changed by the owner's hand, never remotely;
  Auto Power OFF Temp. remotely only when a run names it.

## Context

These settings can take the camera off the link or change what every other setting means (NTSC/PAL re-indexes frame rates).

## Decision

USB settings, Language, NTSC/PAL, Area/Date and network identity are changed by the owner, with the closed watcher
downloading after each. No `--allow` opens one of them, whatever the owner said: the kit refuses such a label before
anything connects and the row however a run named it (`kit/camkit/safety.py`, `allow_refused` and `never_lifted`).
Auto Power OFF Temp. may be changed remotely (the owner: "it causes no issues when in stills"); it stays on the kit's
by-hand list, so a run opens it only when it names the row with `--allow`.

Before 2026-11-02 Auto Power OFF Temp. was changed by hand only, as the rest; before 0.2.0 (2026-11-11) a run's
`--allow` could name one of the others.

## Consequences

Proofs of these rows come from the owner's hand changes. For someone else's camera the playbook's rule 3 keeps Auto
Power OFF Temp. by hand too, until its owner allows it.
