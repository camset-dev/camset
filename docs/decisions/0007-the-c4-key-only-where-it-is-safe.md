# 7. The C4 key only where it is safe

- **Date:** 2026-11-01 to 2026-11-03; changed 2026-11-06 and 2026-11-11
- **Status:** accepted
- **Rule:** C4 only as guarded Help or a per-run go-ahead on menu, option, panel or editor screens; never in Playback,
  with a picture shown or shooting; C1-C3, C5-C7 never.

## Context

C4 is the trash button: in Playback, and wherever a picture is displayed, it deletes the picture; on the shooting
screen it does whatever the body assigns to it, a change the kit must not make either (on the a1 II the owner saw it
turn Touch Operation off and on). On some menu screens it is a harmless helper, which the screen's footer draws.
Focus Area's SET and a Creative Look's Reset are one owner's go-aheads for their own body, never a default, so a run
sends one only with that owner's word for it.

## Decision

The guard on C4 belongs where it can delete, and the screen is that guard. `Link.press` itself sends C4 only when the
screen read last is a menu, option, panel or editor screen of the kinds drive.py's checks allow, and refuses it on the
shooting screen, in Playback (also when the camera's own operating mode says so) and with a picture displayed, saying
which screen it was. There C4 is sent only as guarded Help (the In-Camera Guide, on a screen whose footer draws the
help button), as Focus Area's SET with Custom 1-3 lit and inside that size editor (2026-11-02), and as a Creative Look
panel's Reset (2026-11-03); the last two are the a1 II's owner's go-aheads for that body, sent only when a run names
them, the owner's word for that run (`kit/drive.py --c4-press`). Delete and Format stay never-opened actions
([decision 4](0004-never-delete-or-format-the-cards.md)); C1-C3 and C5-C7 are never sent.

Before 2026-11-06 C4 also needed a recorded yes in `private/config.json` on each new body (added 2026-11-05) and
`Link.press` did not judge the screen itself; before 0.2.0 (2026-11-11) Focus Area's SET and a Creative Look's Reset
needed no word per run; the record also named the multi-selector's centre among the keys never sent (never so: it is a
menu key, as Enter).

## Consequences

drive.py checks each press on its own screen first: help, the footer's help button on a menu or option screen;
c4set, a screen whose text reads Focus Area and Custom 1-3 (a regex the run gives with the press may say which is
lit), or that box's size editor (Custom 1-3 with Reset and Cancel); c4reset, a screen whose text reads Creative Look
with Reset, Cancel and OK (a panel's footer), and neither Playback nor Delete; c4set and c4reset never on the shooting
screen or the Main tiles. `Link.press` checks the screen's kind under them, so a caller that skips drive.py's
checks is still refused off those screens. Where the body lists its operating mode, C4 goes only when the camera gives
one that is not Playback (the playbook's rule 13 says how).

See also: [decision 21](0021-on-the-shooting-screen-no-key-but-menu-unless-it-is-named.md) (on the shooting screen
no key but MENU unless the run names it; the multi-selector's centre there is whatever the body assigns to it, and
naming C4 never sends it there).
