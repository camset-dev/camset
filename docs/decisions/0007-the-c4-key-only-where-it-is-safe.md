# 7. The C4 key only where it is safe

- **Date:** 2026-11-01 to 2026-11-03; amended 2026-11-06
- **Status:** accepted; amended 2026-11-06 (below)
- **Rule:** C4, the trash button, is sent only on menu, option, panel and editor screens, never in Playback or on the
  shooting screen; C1-C3 and C5-C7 never.

## Context

C4 is the trash button: in Playback and on the shooting screen it deletes or does what it is assigned. On some screens it is a harmless helper.

## Decision

C4 is sent only as guarded Help (the In-Camera Guide, on a screen whose footer draws the help button), as Focus Area's SET with Custom 1-3 lit and inside that size editor (2026-11-02), and as a Creative Look panel's Reset (2026-11-03). Never in Playback or on the shooting screen. C1-C3, C5-C7 and the multi-selector's centre are never sent.

## Consequences

drive.py's help, c4set and c4reset presses each check their screen first.

## Amendment, 2026-11-06

The owner: the guard on C4 belongs where it can delete, and the screen is that guard. The per-body consent added on
2026-11-05 (a recorded yes in `private/config.json` before C4 on a new body) is dropped. C4 deletes in Playback and
wherever a picture is displayed; on the shooting screen it does whatever the body assigns to it, a change the kit must
not make either (on the a1 II the owner saw it turn Touch Operation off and on: the model page). So `Link.press`
itself sends C4 only when the screen read last is a menu, option, panel or editor screen of the kinds drive.py's
checks allow, and refuses it on the shooting screen, in Playback (also when the camera's own operating mode says
so) and with a picture displayed, saying which screen it was. drive.py's help, c4set and c4reset checks stay. Delete
and Format stay never-opened actions; C1-C3 and C5-C7 are still never sent.
