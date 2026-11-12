"""Put the camera in another shooting mode through the menu, for the rows only that mode's menu offers (2026-11-07).

    .venv/bin/python -u kit/provers/mode_switch.py --to Movie [--mode P] --keep [--in Stills] [--scan RUN]
    ... the Movie-menu rows: kit/prove_run.py --scan kit2_page_scan_movie_dm_osd --map ... --context "Movie mode" ...
    .venv/bin/python -u kit/provers/mode_switch.py --restore
    .venv/bin/python kit/provers/mode_switch.py --forget --shows "Stills M"   # a stale record only: renamed, nothing sent

The Still/Movie/S&Q switch and the mode dial are physical, but the a1 II can be told to take both from the menu:
Mode Dial Control Set = Set with Menu, then Shoot Mode, a two-axis carousel (Up/Down the family: Stills, Movie, S&Q
Motion, Time-lapse; Left/Right the exposure mode within it, the orange title naming it). Choosing a Movie family mode
puts the whole camera in Movie mode, its own menu up. The memory-recall modes (MR, M1-M4) are never chosen: recalling
a memory rewrites dozens of settings.

The switch is a run of its own, bracketed as every run is (decision 15): the start file is downloaded first, and
   --keep     leaves the camera in the new mode, the start file's name kept in kit2_pass2/mode_switch.json; the
              prove runs that follow (--eyes osd-all) take the camera as they find it and put that back;
   --restore  uploads the kept start file (the camera restarts in its own mode, the dial's say restored) and
              checks it took, then forgets the switch. The start file is the camera's settings from before the
              switch: whatever was changed on the camera since is undone too;
   --forget   renames the kept record and sends nothing: for a record left over after the camera was put back
              another way (by hand, or by a later session's restore), which every run would otherwise stop on. It
              needs --shows MODE, what the camera's screen shows now (look, or ask the owner): the family first
              (Stills, Movie or S&Q), then the exposure mode when you say one (P, A, S, M or Auto): Movie,
              "Stills M", "Movie Auto"; a letter alone is refused, since Movie's and S&Q's screens show one too. It
              refuses while that is where the switch went (its family, and its --to or --mode when both say an
              exposure mode), the family it went to when that is not the one it started from, the bare Stills of a
              switch within Stills, or, on a record that does not say where it started, the family it went to (the
              switch may still be in effect: --restore); an empty or unreadable record is refused (remove it by hand
              only when sure, as the refusal says); the renamed record keeps the claim and its time, and renaming it
              back (the line it prints, its paths quoted) undoes it;
   neither    puts the start file back at once (a trial of the switch).
The switch navigates the menu of the mode the camera is in (--in, default Stills: its latest page scan by default,
runner.latest_scan); --set, with a switch waiting, the menu of the mode the switch left it in (the kept record's
"scan_mode", else its --to: a family, or P/A/S/M/Auto in Stills).
"""
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, ocr  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.live import LiveCamera, lit_text, open_refused  # noqa: E402
from camkit.match import clean  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.session import verify_restore  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import Failed, bar_text, enter_any, info_notice_ok, option_key, to_shooting  # noqa: E402
from runner import (EXIT_UNRESTORED, LATEST_SCAN, SHOWN_EXPOSURES, SHOWN_MODES, SWITCH_KEPT, add_in_argument,  # noqa: E402
                    close_screen, end_session, forget_refused, in_mode, load_scan, menu_from_shooting, read_json,
                    restore_checked, restoring, scan_arg, scan_mode, scan_position, shown_mode, switch_advice,
                    switch_left, write_json)
from shootmode_run import FAMILIES, mode_name  # noqa: E402

DIAL_ROW = "Mode Dial Control Set"
BY_MENU = "Set with Menu"
# Mode Dial Control Set sits in Setup > Accessibility on firmware 4.00, under the Screen Reader row. The group is
# never-open for the Screen Reader's sake (decision 3); this run may step onto the group's page (Right on the group
# name), where the jump lands on the Screen Reader row and only presses Down past it: the Screen Reader row itself
# stays never-open (open_refused matches the names given against the lit row's own text)
MAY_OPEN = {"Accessibility"}
KEPT = SWITCH_KEPT                             # in the run folder: the switch waiting for --restore (runner reads it)
MODES = {"P": "Program Auto", "A": "Aperture Priority", "S": "Shutter Priority", "M": "Manual Exposure",
         "Auto": "Intelligent Auto"}            # Flash Mode's Autoflash and Flash Off are offered in Auto alone


def text(cam) -> str:
    return ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))


def find(cam, cycle, model, label: str):
    """The menu open on the row labelled `label`, by the scan."""
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, label) is None:
        raise Failed(f"could not reach {label!r} by the scan ({cam.read().kind}, {cam.frame.path.name})")


def open_menu(cam):
    menu_from_shooting(cam)              # MENU, once more if it went unanswered after a download
    if cam.read().kind == "menu" and cam.read().focus == "groups":
        # the menu reopens where a hand left it, the focus in the group column; a never-open group left lit there
        # (FTP Transfer, Accessibility) is stepped off first, since Right is refused on it (as prove_run's session)
        for key in ("up", "down", "down"):
            if not open_refused(lit_text(cam.frame.image, cam.frame.path), cam.may_open):
                break
            cam.press(key)
        cam.press("right")


def dial_by_menu(cam, cycle, model, say):
    """Mode Dial Control Set = Set with Menu: Right on the row shows a note about the setting first (its OK leads on,
    2026-11-01), then the two-option list."""
    find(cam, cycle, model, DIAL_ROW)
    cam.press("right")
    for _ in range(2):
        if cam.read().kind == "list":
            break
        t = text(cam)
        if not re.search(r"mode dial", t, re.I):
            raise Failed(f"Right on {DIAL_ROW!r} opened {cam.read().kind} ({cam.frame.path.name}): {t[:80]!r}")
        cam.press("enter")                      # the note's OK
    if cam.read().kind != "list":
        raise Failed(f"{DIAL_ROW!r}: no list came ({cam.read().kind}, {cam.frame.path.name})")
    for _ in range(3):
        if option_key(bar_text(cam)) == option_key(BY_MENU):
            break
        cam.press("down")
    else:
        raise Failed(f"{DIAL_ROW!r}: {BY_MENU!r} is not in its list ({bar_text(cam)!r})")
    say(f"{DIAL_ROW}: choosing {BY_MENU!r}")
    cam.press("enter")
    if cam.read().kind == "notice":
        say(f"   notice after OK: {text(cam)[:80]!r}")
        cam.press("menu")


def shoot_mode(cam, cycle, model, family: int, mode: str | None, say) -> str:
    """Shoot Mode's carousel: Down to the family, Right to the mode (or the family's remembered one), OK. Returns
    the title chosen."""
    find(cam, cycle, model, "Shoot Mode")
    cam.press("right")
    head = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 50))
    if cam.read().kind != "dialog" or "shoot mode" not in head.lower():
        raise Failed(f"Right on Shoot Mode opened {cam.read().kind} ({head!r}, {cam.frame.path.name})")
    for _ in range(family):
        cam.press("down")
    got = mode_name(cam)
    say(f"Shoot Mode: the {FAMILIES[family]} family is on {got!r}")
    if mode is not None:
        seen = [got]
        for _ in range(16):                     # stills: Auto, P, A, S, M and the memory recalls (MR 1-3, M1-M4)
            if option_key(got) == option_key(mode):
                break
            cam.press("right")
            got = mode_name(cam)
            seen.append(got)
        else:
            raise Failed(f"Shoot Mode: {mode!r} did not come round in the {FAMILIES[family]} family (saw {seen})")
    if got.startswith("MR"):
        raise Failed(f"Shoot Mode: the {FAMILIES[family]} family is on {got!r}, a memory recall: never chosen")
    say(f"Shoot Mode: {FAMILIES[family]} family, {got!r}: OK")
    cam.press("enter")
    if cam.read().kind == "notice":
        t = text(cam)
        cam.press("menu")
        raise Failed(f"Shoot Mode refused {got!r}: {t[:90]!r}")
    return got


def set_row(cam, cycle, model, path: list, option: str, say):
    """A list row (a top-level row, or a submenu's: "Proxy Settings > Px Proxy Recording") put on `option` and left
    there: to the row by the scan, Right, Down through the list to the option (by the bar's text), OK; an
    information screen with buttons after the choice is taken with its OK (Exposure Ctrl Type), a notice closed with
    MENU. For the state a prove run needs; the switch's --restore puts the start file back over it. The bar is read
    without the radio ring OCR can put before the saved option ("o Set with Dial", kit2_tables 08452_enter.png), so a
    row already on `option` is found there too (camkit.match.clean). A row inside a panel ("Viewfinder Bright. >
    Brightness Setup"): OK brings the panel back, its title the panel's own, with its slider lit (an OK in its footer,
    kit2_hdmi_watch 02362 -> 02363), which is the choice made, no information to take. What a screen after the choice
    reads is never said nor put in a failure (it can show the owner's values: a panel's number, a notice): the frame is
    named and the words go to the run's events.jsonl."""
    find(cam, cycle, model, path[0])
    if len(path) > 1:
        enter_any(cam, path, 0)
    cam.press("right")
    if cam.read().kind != "list":
        raise Failed(f"Right on {' > '.join(path)!r} opened {cam.read().kind}, not a list ({cam.frame.path.name})")
    for _ in range(24):
        if option_key(clean(bar_text(cam))) == option_key(option):
            break
        cam.press("down")
    else:
        # the option the list was on can be the owner's: kept in the run's events, never in the message
        cam.run.log("set_row_missed", step=" > ".join(path), frame=cam.frame.path.name, bar=bar_text(cam))
        raise Failed(f"{' > '.join(path)!r}: {option!r} did not come round in its list ({cam.frame.path.name}; what "
                     "its bar read is in the run's events.jsonl)")
    say(f"{' > '.join(path)}: choosing {option!r}")
    cam.press("enter")
    kind = cam.read().kind
    if kind == "list":
        # OK went unanswered (the press already waited for a late one, camkit.live.OK_LATE): one fresh look, and
        # then the step stops, as prove_run stops a row whose OK leaves the list open; no second OK (no run of the
        # kit's has shown a list still open after OK on its option)
        kind = cam.refresh("after-ok").kind
        if kind == "list":
            raise Failed(f"{' > '.join(path)!r}: OK on {option!r} went unanswered, its list still open "
                         f"({cam.frame.path.name})")
    if len(path) > 1 and option_key(path[0]) in option_key(ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path],
                                                                       (0, 0, 640, 52))):
        return                                   # back in the panel (or submenu) the row is in: the choice is made
    if kind == "notice":
        cam.run.log("set_row_notice", step=" > ".join(path), frame=cam.frame.path.name, notice=" ".join(text(cam).split()))
        say(f"   notice after OK ({cam.frame.path.name}; its words are in the run's events.jsonl)")
        cam.press("menu")
    elif kind in ("table", "unknown"):
        info = info_notice_ok(cam, " > ".join(path), kinds=("table", "unknown"), words=False)
        if info:
            cam.run.log("set_row_information", step=" > ".join(path), frame=info["frame"], text=" ".join(info["text"].split()))
            say(f"   information after the choice, taken with its OK ({info['frame']}; its words are in the run's "
                "events.jsonl)")


def switched_mode(to: str) -> str:
    """The shooting mode whose menu the camera shows after a switch to `to` (runner.SCAN_MODES): a stills exposure
    mode (MODES: P, A, S, M, Auto) is Stills, a family its own (S&Q Motion and Time-lapse: S&Q)."""
    return "Stills" if to in MODES else scan_mode(to)


def forget(kept: Path, shows: str, say) -> Path:
    """--forget --shows MODE: the kept record renamed mode_switch.forgotten-<date-time>.json beside it, nothing sent to
    the camera; runner.switch_waiting reads only the record's own name, so no run stops on it any more. `shows` is what
    the camera's screen shows now, as its owner or the mapper looked: refused while that is the mode the switch went to
    and not the one it started from (runner.forget_refused: the switch is still in effect, --restore puts it back). The
    renamed file keeps the record, with the claim and its time ("forgotten"), as the run's own note of the switch, and
    the way to undo it is said (rename it back)."""
    if not kept.exists():
        sys.exit(f"no switch is waiting ({kept}): nothing to forget")
    try:
        info = read_json(kept)
    except (OSError, ValueError):
        info = {}
    info = info if isinstance(info, dict) else {}
    if not info:
        sys.exit(f"not forgotten: {kept} is empty or cannot be read, so nothing says which mode the switch left the "
                 "camera in, and the kit cannot check what the screen shows against it. Nothing was sent to the camera "
                 "and the record stays. Only if you are sure the camera is in the mode it should be, remove the record "
                 f"by hand:\n  rm {_quoted(kept)}\n(Windows: del \"{kept}\")")
    why = forget_refused(info, shows, switch_left(info))
    if why:
        sys.exit(f"not forgotten: {why}, so the switch is still in effect. Nothing was sent to the camera and the record "
                 f"stays. Put the camera back with\n  .venv/bin/python kit/provers/mode_switch.py --restore --run "
                 f"{kept.parent.name}\n(it uploads the settings file from before the switch: whatever was changed on "
                 "the camera since is undone). If the screen shows another mode, say that one with --shows.")
    to = kept.with_name(f"{kept.stem}.forgotten-{time.strftime('%Y%m%d-%H%M%S')}{kept.suffix}")
    write_json(to, {**info, "forgotten": {"shows": shows, "t": time.strftime("%Y-%m-%d %H:%M:%S"),
                                          "said": "the camera's screen showed this mode when the record was forgotten"}},
               indent=1)
    kept.unlink()
    say(f"forgotten: {kept.name} renamed {to.name}, with what the screen shows ({shows}) and when; nothing was sent to "
        "the camera, and no run takes the camera for left in another mode by this record any more")
    say(f"to undo it, rename it back: mv {_quoted(to)} {_quoted(kept)}  (Windows: ren \"{to}\" \"{kept.name}\")")
    return to


def _quoted(p) -> str:
    """A path in single quotes for a POSIX shell, a quote inside it written so the shell reads it back."""
    return "'" + str(p).replace("'", "'\\''") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", help="Stills, Movie, S&Q Motion or Time-lapse (the family's remembered mode), or P, A, S, M "
                                 "(a stills exposure mode) or Auto (Intelligent Auto)")
    ap.add_argument("--mode", default=None, help="with a family (--to Movie): its exposure mode, P, A, S, M or Auto, "
                                                 "instead of the one the family remembers")
    ap.add_argument("--keep", action="store_true", help="leave the camera in the new mode for the runs that follow")
    ap.add_argument("--restore", action="store_true",
                    help="put the kept start file back and check it took: the settings from before the switch, so "
                         "whatever was changed on the camera since is undone too")
    ap.add_argument("--forget", action="store_true",
                    help="rename the kept record and send nothing: for a stale record, the camera put back since by "
                         "hand or by a later session's restore; needs --shows")
    ap.add_argument("--shows", default=None, metavar="MODE",
                    help=f"with --forget: the mode the camera's screen shows now, looked at on the camera or asked of "
                         f"its owner: the family ({', '.join(SHOWN_MODES)}), then the exposure mode when you say one "
                         f"({', '.join(SHOWN_EXPOSURES)}): Movie, \"Stills M\", \"Movie Auto\"")
    ap.add_argument("--set", action="append", default=[], metavar="ROW=OPTION",
                    help="with a switch waiting (--keep): put this list row on OPTION and leave it, for the state a prove "
                         "run needs (a submenu's row as 'Proxy Settings > Px Proxy Recording=On'); --restore covers it")
    ap.add_argument("--scan", default=LATEST_SCAN, type=scan_arg,
                    help="the page scan of the menu the camera shows now (a run in runs/<model>_fw<fw>/, or a path; "
                         "default: the camera's latest page scan made in that mode, runner.latest_scan)")
    add_in_argument(ap, default=None, said="Stills for a switch; with --set, the mode the waiting switch left")
    ap.add_argument("--run", default="kit2_pass2")
    a = ap.parse_args()
    run = Run(a.run)
    say = lambda m: print(m, flush=True)
    kept = run.dir / KEPT
    if a.forget:
        if a.restore or a.to or a.set:
            sys.exit("--forget only renames the kept record: give it alone (with --shows and --run)")
        if not a.shows:
            sys.exit("--forget needs --shows MODE, what the camera's screen shows now (look at it, or ask its owner): "
                     f"the family ({', '.join(SHOWN_MODES)}), then the exposure mode when you say one "
                     f"({', '.join(SHOWN_EXPOSURES)}), as in --shows Movie or --shows \"Stills M\". Nothing was changed.")
        try:
            shows = shown_mode(a.shows)
        except ValueError as e:
            sys.exit(f"--shows {e}. Nothing was changed.")
        forget(kept, shows, say)
        return
    if a.shows:
        sys.exit("--shows goes with --forget only")
    if a.restore:
        if not kept.exists():
            sys.exit(f"no switch is waiting ({kept})")
        info = read_json(kept)
        start = Path(info["start"])
        hdmi = eyes_from_config(run)
        try:
            # the start file goes back when anything differs from it, even if the shooting screen does not come; a
            # restore that raises exits EXIT_UNRESTORED (runner.restoring) and the kept record stays
            with restoring("mode_switch --restore"), Link(run) as link:
                hdmi.attach(link)
                ending = end_session(link, hdmi, start, "the restore", tag="restore")
        finally:
            hdmi.close()
        # checked after an upload (a reconnect, 40 s); with nothing to upload, the end download already said 0 differ
        if not restore_checked(run, ending, start):
            sys.exit(EXIT_UNRESTORED)        # the kept record stays for another --restore (runner.EXIT_UNRESTORED)
        kept.unlink()
        return
    if a.set and not a.to:
        if not kept.exists():
            sys.exit(f"--set wants a switch waiting for --restore ({kept}), whose start file covers what it changes")
        info = read_json(kept)
        now = info.get("scan_mode") or switched_mode(info["to"])
        if a.in_mode and a.in_mode != now:
            sys.exit(f"--in {a.in_mode}: the switch waiting in {kept} left the camera in {now} mode; nothing was sent")
        cycle, model = load_scan(in_mode(a.scan, now))
        hdmi = eyes_from_config(run)
        try:
            with Link(run) as link:
                hdmi.attach(link)
                to_shooting(link, hdmi, "the download before the settings")
                before = link.download("before-set")
                time.sleep(5)
                cam = LiveCamera(link, hdmi, run, may_open=MAY_OPEN)
                try:
                    for item in a.set:
                        row, _, option = item.partition("=")
                        open_menu(cam)
                        set_row(cam, cycle, model, [x.strip() for x in row.split(" > ")], option.strip(), say)
                        close_screen(cam, link)
                        time.sleep(1.0)
                finally:
                    close_screen(cam, link)
                to_shooting(link, hdmi, "the download after the settings")
                time.sleep(2)
                after = link.download("after-set")
                ch = camset.diff(camset.read(before), camset.read(after))
                say(f"{len(ch)} records differ after the settings:")
                for c in ch[:12]:
                    say(f"   {c.key}: {c.before!r} -> {c.after!r}")
                if not ch:
                    raise Failed("the settings changed nothing")
        except Failed as e:
            say(f"stopped: {e}")
            sys.exit(1)
        finally:
            hdmi.close()
        return
    if not a.to:
        sys.exit("--to names the mode (Movie, S&Q Motion, Time-lapse, Stills, or P/A/S/M), or --restore")
    if kept.exists():
        sys.exit(f"A switch is still waiting in {kept}; nothing was sent to the camera.\n{switch_advice(kept)}")
    if a.to in MODES:
        family, mode = 0, MODES[a.to]
    elif a.to in FAMILIES:
        if a.mode is not None and a.mode not in MODES:
            sys.exit(f"--mode {a.mode!r}: one of {sorted(MODES)}")
        family, mode = FAMILIES.index(a.to), MODES.get(a.mode)
    else:
        sys.exit(f"--to {a.to!r}: one of {FAMILIES} or {sorted(MODES)}")
    cycle, model = load_scan(in_mode(a.scan, a.in_mode or "Stills"))
    hdmi = eyes_from_config(run)
    start = after = None
    switch_failed = False           # a switch that did not happen exits 1, so --keep's chain does not go on in the old mode
    switched = False                # the switch made, so a failure after it is the upload's, not the switch's
    try:
        with Link(run) as link:
            hdmi.attach(link)
            to_shooting(link, hdmi, "the start download")
            start = link.download("before")
            time.sleep(5)
            cam = LiveCamera(link, hdmi, run, may_open=MAY_OPEN)
            try:
                open_menu(cam)
                dial_by_menu(cam, cycle, model, say)
                close_screen(cam, link)
                time.sleep(1.0)
                open_menu(cam)
                title = shoot_mode(cam, cycle, model, family, mode, say)
            finally:
                close_screen(cam, link)
            to_shooting(link, hdmi, "the download after the switch")
            time.sleep(2)
            after = link.download(f"mode-{re.sub(r'[^A-Za-z0-9]+', '-', a.to)}")
            ch = camset.diff(camset.read(start), camset.read(after))
            say(f"{len(ch)} records differ after the switch to {a.to} ({title}):")
            for c in ch[:12]:
                say(f"   {c.key}: {c.before!r} -> {c.after!r}")
            if not ch:
                raise Failed("the switch changed nothing: the camera is as it was")
            if a.keep:
                write_json(kept, {"start": str(start), "after": str(after), "to": a.to, "title": title,
                                  **({"mode": a.mode} if a.mode else {}),   # a family's exposure mode (runner.is_auto)
                                  "scan_mode": switched_mode(a.to),        # the menu now up (runner.switch_waiting)
                                  "from": a.in_mode or "Stills",           # the menu it started in (runner.forget_refused)
                                  "t": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=1)     # whole: --restore reads it
                say(f"kept: the camera stays in {a.to}; {kept.name} holds the start file for --restore")
                return
            say(f"restoring the start file {start.name} (the camera restarts)")
            switched = True
            link.upload(start)
    except Exception as e:      # a Failed switch, and anything else after it (a press refused, the feed, a STOP)
        if switched:            # the switch was made and shown; the upload that puts the start file back failed
            say(f"the switch to {a.to} was made; putting the start file back failed: {type(e).__name__}: {e}")
        else:
            say(f"stopped: {e}" if isinstance(e, Failed) else f"stopped: {type(e).__name__}: {e}")
            switch_failed = True
        if start is not None and not kept.exists():
            try:
                with Link(run) as link:
                    hdmi.attach(link)
                    # the start file goes back when anything differs from it, even if the shooting screen does not come
                    ending = end_session(link, hdmi, start, "the restore after a stop", tag="check")
                if ending.after is not None and not ending.uploaded:
                    say("the camera is as it was")
                    sys.exit(1 if switch_failed else 0)     # as it was; exit 1 when the switch did not happen
            except Exception as e2:
                say(f"the restore could not start: {e2}")
    finally:
        hdmi.close()
    if start is not None:
        n = verify_restore(run, start)
        say(f"after the restore: {n} records differ from the start file")
        if n != 0:
            sys.exit(EXIT_UNRESTORED)        # the camera is not known to be as the start file (runner)
    if switch_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
