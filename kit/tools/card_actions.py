"""Card actions on the test SD cards: what each one shows, and whether it writes the settings file.

    .venv/bin/python -u kit/tools/card_actions.py peek "Create New Folder" --allow "Create New Folder"
    .venv/bin/python -u kit/tools/card_actions.py run "Create New Folder" --allow "Create New Folder" \\
        --press "right" --press "enter:REGEX"

The user put two SD cards in the camera for this on 2026-10-28 ("you can use for format, folder
creation, etc."); on 2026-11-01 they asked that nothing on the cards be deleted, so Format is
no longer offered. Only the rows in CARD_ROWS are opened, and only by this script: the walkers keep
them on safety's never-open list. Each is an action on the cards, so a run opens its row only when --allow names it,
the owner's word (as the provers' --allow: runner.allowed_or_exit), and refuses to start without it or with any other.

peek  goes to the row, presses Right once, saves the frame and its text, then cancels with MENU.
      It downloads before and after too: Right alone may already act.
run   goes to the row and sends the presses in order, each judged as kit/drive.py judges its own (drive.press_decision):
      the key as the guards read it (drive.canonical_key), menu keys only, each sent once; a press written "key:regex"
      only when the screen's text matches the regex (case-insensitive), so a screen nobody looked at with peek is
      cancelled with MENU; Enter (and the multi-selector's centre) only with a regex, only on a lit text the kit can
      read, never on Initialize or Reset Network Set., and never on a screen that reads like a confirmation unless
      --confirm is given; Right or Enter onto a never-open row only when --allow names it, never on the cards' Format
      or Delete, Initialize, Reset Network Set., credentials or the camera's identity (safety.never_lifted); no key but
      MENU on the shooting screen (decision 21).
Either way the session ends as every runner's does (kit/runner.py; docs/decisions/0015): the camera closed back to the
shooting screen with cleanup presses (close_for_restore), the settings downloaded again and diffed with the first
download, the start file uploaded when anything differs (end_session) and its restore checked (restore_checked); a
camera not known to be as the start file has it ends the run with exit EXIT_UNRESTORED.
It navigates by the Stills page scan the provers take (--scan, default the camera's latest page scan made in Stills
mode, as kit/provers/memreg_run.py's: runner.latest_scan).
Results: runs/<model>_fw<fw>/kit2_cards/results.jsonl; frames and downloads in the same run folder.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parent))
import drive  # noqa: E402
from camkit import safety, screen  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.live import LiveCamera, press, text_of  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.screen import same_position  # noqa: E402
from camkit.session import wait_for  # noqa: E402
from crawl_run import go_to  # noqa: E402
from runner import (EXIT_UNRESTORED, LATEST_SCAN, add_allow_argument, add_scan_argument, allowed_or_exit, changes_of,  # noqa: E402
                    close_for_restore, end_session, load_scan, restore_checked, restoring, wait_shooting)

# 2026-11-01 (user): "Please don't delete the cards." Format is off the list: nothing on the cards
# is deleted or formatted remotely (Delete was never on it)
CARD_ROWS = {"Create New Folder", "Select REC Folder", "Recover Image DB"}


def press_args_refused(presses: list) -> str:
    """Why the --press arguments are refused before anything connects, or "": each as kit/drive.py's own are
    (drive.press_args_refused: a key the guards name, Enter only with a regex), and a menu key sent once, "key" or
    "key:regex": no C4 press, no dial turn, no "key@y" and no vouched Enter, which this script has no use for."""
    why = drive.press_args_refused(presses)
    if why:
        return why
    for p in presses:
        key, y, _ = drive.parse_press(p)
        if key in drive.C4_PRESSES or key.startswith("dial.") or y is not None or drive.vouched_press(p):
            return f"{p!r}: card_actions.py sends menu keys only, each once (key, or key:regex)"
    return ""


def allowance_of(row: str, allow) -> str:
    """The results' allowance: exits before anything connects unless --allow names the card row the run opens, the
    owner's word, and nothing else (runner.allowed_or_exit then says it and gives its words)."""
    if not safety.named(row, allow):
        sys.exit(f"card_actions: {row} is an action on the cards and never-open; a run opens it only with the owner's "
                 f"word, --allow {row!r}")
    others = [x for x in allow if not safety.named(row, [x])]
    if others:
        sys.exit(f"card_actions: --allow names {others}: this run opens no never-open row but {row}")
    return allowed_or_exit(allow)


def press_judged(cam, p: str, confirm: bool, allow) -> str:
    """Why the press `p` may not go out on the screen now, or "" once it has gone: the regex first (the screen's text
    must match it), then the shooting screen (no key but MENU there), then drive.press_decision on the lit text and the
    whole screen's, as kit/drive.py judges its own."""
    key, _, want = drive.parse_press(p)
    t = text_of(cam)
    if want and not re.search(want, t, re.I):
        return f"the screen does not match {want!r}: {t[:160]!r}"
    kind = cam.read().kind
    why = drive.shooting_press_refused(key, kind, ())
    if not why:
        lit = drive.highlighted(cam.frame.image, cam.frame.path) if key in drive.ENTERS + drive.RIGHTS else ""
        why, _ = drive.press_decision(p, key, lit, t, kind, confirm, allow)
    if why:
        return f"{key} refused: {why}"
    press(cam, key)
    return ""


def to_row(cam, cycle, model, label):
    cam.press("menu")
    j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
    if j is None:
        raise RuntimeError(f"the menu opened on a screen the scan does not know ({cam.read().kind})")
    if go_to(cam, cycle, model, j, label) is None:
        raise RuntimeError(f"on the way to {label!r} a screen was not the one the scan recorded")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["peek", "run"])
    ap.add_argument("row")
    ap.add_argument("--press", action="append", default=[], help="key, or key:regex the screen must match first")
    ap.add_argument("--confirm", action="store_true", help="allow Enter on a screen that reads like a confirmation")
    ap.add_argument("--wait", type=float, default=2.0, help="seconds after the last press (formatting takes a while)")
    add_scan_argument(ap, default=LATEST_SCAN, mode="Stills")    # the Stills page scan the camera's provers navigate by
    add_allow_argument(ap)
    a = ap.parse_args()
    if a.row not in CARD_ROWS:
        sys.exit(f"{a.row!r} is not a card action this script may open ({sorted(CARD_ROWS)})")
    presses = ["right"] if a.what == "peek" else a.press
    why = press_args_refused(presses)
    if why:
        sys.exit(why)
    allowance = allowance_of(a.row, a.allow)
    cycle, model = load_scan(a.scan)
    run = Run("kit2_cards")
    hdmi = eyes_from_config(run)
    log = open(run.dir / "results.jsonl", "a", encoding="utf-8", newline="\n")  # noqa: SIM115 (closed in the finally below)
    ending, restored = None, False
    try:
        with Link(run) as link:
            hdmi.attach(link)
            if screen.read(hdmi.grab(save=False)).kind in ("menu", "tiles"):
                link.press("menu", cleanup=True)
                time.sleep(1.0)
            wait_for(hdmi, ("shooting",), "the settings download", link=link)
            before = link.download("before")       # peek too: Right alone may act (Create New Folder)
            time.sleep(5)
            cam = LiveCamera(link, hdmi, run, may_open=set(a.allow))    # the owner's word for the row, no other
            screens, ok = [], True
            try:
                to_row(cam, cycle, model, a.row)
                for p in presses:
                    why = press_judged(cam, p, a.confirm, a.allow)
                    if why:
                        print(f"{why}; cancelling", flush=True)
                        ok = False
                        break
                    t = text_of(cam)
                    screens.append({"after": p, "frame": cam.frame.path.name, "kind": cam.read().kind, "text": t})
                    print(f"{p:28s} -> {cam.read().kind:9s} {cam.frame.path.name}  {t[:150]!r}", flush=True)
                if ok and a.what == "run":
                    time.sleep(a.wait)
                    cam.refresh("after-action")
                    t = text_of(cam)
                    screens.append({"after": "wait", "frame": cam.frame.path.name, "kind": cam.read().kind, "text": t})
                    print(f"{'(after ' + str(a.wait) + ' s)':28s} -> {cam.read().kind:9s} {cam.frame.path.name}  {t[:150]!r}",
                          flush=True)
            except Exception as e:
                print(f"error: {type(e).__name__}: {e}; cancelling", flush=True)
                ok = False
            # the standard end (runner), as drive.py's: cleanup presses, which go out after a STOP too; then the download,
            # the diff and the start file put back when anything differs, and only then the results line (a line that
            # cannot be written skips nothing). Whatever ends it early, the line's write too, exits EXIT_UNRESTORED
            with restoring("card_actions.py's restore"):
                close_for_restore(cam, link)
                ending = end_session(link, hdmi, before, "the settings download after the action", reach=wait_shooting,
                                     show=30)
                log.write(json.dumps({"what": a.what, "row": a.row, "presses": presses, "completed": ok,
                                      "screens": screens, "allowance": allowance, "before": before.name,
                                      "after": ending.after.name if ending.after else None,
                                      "changes": changes_of(ending.changes)}) + "\n")
                log.flush()
        restored = restore_checked(run, ending, before)
    finally:
        hdmi.close()
        log.close()
    if not restored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


if __name__ == "__main__":
    main()
