# 7. The C4 key only where it is safe

- **Date:** 2026-11-01 to 2026-11-03; changed 2026-11-06, 2026-11-11, 2026-11-17 and 2026-11-19
- **Status:** accepted
- **Never broken:** 6th in AGENTS.md's list
- **Rule:** C4 only as guarded Help, on a menu or option screen whose footer draws the help button: never in Playback or
  with a picture displayed, where it deletes, nor on the shooting screen, where it does whatever the body assigns to it;
  where the body lists its operating mode, C4 also needs the camera to give one that is not Playback, and it never goes
  where that mode, or whether the body lists it, cannot be read; C1-C3 and C5-C7 never.

## Context

C4 is the trash button: in Playback, and wherever a picture is displayed, it deletes the picture; on the shooting
screen it does whatever the body assigns to it, for example switching a setting off and on, a change
the kit must not make either. On some menu screens it is a harmless helper, which the screen's footer draws.
Focus Area's SET, a Creative Look's Reset and a Custom box editor's Reset are one owner's go-aheads for their own body,
never a default, so a run sends one only with that owner's word for it.

## Decision

The guard on C4 belongs where it can delete, and the screen is that guard. `Link.press` itself sends C4 only when the
screen read last is a menu, option, panel or editor screen of the kinds drive.py's checks allow, and refuses it on the
shooting screen, in Playback (also when the camera's own operating mode says so) and with a picture displayed, saying
which screen it was. There C4 is sent only as guarded Help (the In-Camera Guide, on a screen whose footer draws the
help button), as Focus Area's SET with Custom 1-3 lit (2026-11-02), as a Creative Look panel's Reset (2026-11-03), and
as the Reset of a Custom box's size editor, which puts that box back to its default size (2026-11-17: "yes kit can hit
reset for custom box editor"); the last three are the a1 II's owner's go-aheads for that body, sent only when a run
names them, the owner's word for that run (`kit/drive.py --c4-press` for the first two;
`kit/provers/boxsize_run.py --allow "Custom box Reset"` for the third, only where the box's start size is its default).
Delete and Format stay never-opened actions ([decision 4](0004-never-delete-or-format-the-cards.md)); C1-C3 and C5-C7
are never sent.

Before 2026-11-19 the Rule line also let C4 go as a per-run go-ahead on panel and editor screens on any camera, and
AGENTS.md, which stated the rule by hand, put guarded Help on panel screens too; the playbook's rule 13 named the
screens as they now stand and needed a mode that is not Playback where the body lists one, and only `Link.c4_refused`
said, by refusing it, that C4 never goes where that mode, or whether it is listed, cannot be read.
Before 2026-11-06 C4 also needed a recorded yes in `private/config.json` on each new body (added 2026-11-05) and
`Link.press` did not judge the screen itself; before 0.2.0 (2026-11-11) Focus Area's SET and a Creative Look's Reset
needed no word per run; the record also named the multi-selector's centre among the keys never sent (never so: it is a
menu key, as Enter). From 2026-11-06 to 2026-11-17 the record named the size editor's Reset under Focus Area's SET,
but `Link.press` refused it there: the editor reads as no known kind.

## Consequences

drive.py checks each press on its own screen first: help, the footer's help button on a menu or option screen;
c4set, a screen whose text reads Focus Area and Custom 1-3 (a regex the run gives with the press may say which is
lit); c4reset, a screen whose text reads Creative Look with Reset, Cancel and OK (a panel's footer), and neither
Playback nor Delete; c4set and c4reset never on the shooting screen or the Main tiles. `Link.press` checks the screen's
kind under them, so a caller that skips drive.py's checks is still refused off those screens. The size editor reads as
no known kind, which the link refuses: there `camkit.live` judges the screen as that box's own editor (its title, its
footer Reset, MENU Cancel and OK, no question mark) under boxsize_run's consent (`BoxReset`) and hands the link the
kind `safety.C4_BOX_EDITOR` names for that one press; a screen after the Reset that is not the editor stops the run,
nothing answered. Where the body lists its operating mode, C4 goes only when the camera gives one that is not
Playback (`Link.c4_refused` says how).

On a menu row drawn grey, guarded Help comes first: only where its guide gives no reason ("This function is currently
disabled.") does `kit/provers/greyrow_run.py` press Right once on the row for the camera's notice, judged as any
opening press, never on a row the kit may not open nor twice in a run, then MENU, or the notice's lone OK where it
refuses MENU (`proving.greyrow`; the a1 II's owner, 2026-11-20).

See also: [decision 21](0021-on-the-shooting-screen-no-key-but-menu-unless-it-is-named.md) (on the shooting screen
no key but MENU unless the run names it; the multi-selector's centre there is whatever the body assigns to it, and
naming C4 never sends it there).
