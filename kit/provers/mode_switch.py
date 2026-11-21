"""Put the camera in another shooting mode through the menu, for the rows only that mode's menu offers (2026-11-07).

    .venv/bin/python -u kit/provers/mode_switch.py --to Movie [--mode P] --keep [--in Stills] [--scan RUN]
    ... the Movie-menu rows: kit/prove_run.py --scan kit2_page_scan_movie_dm_osd --map ... --context "Movie mode" ...
    .venv/bin/python -u kit/provers/mode_switch.py --restore
    .venv/bin/python kit/provers/mode_switch.py --forget --shows "Stills M"   # a stale record only: renamed, nothing sent

The Still/Movie/S&Q switch and the mode dial are physical, but the a1 II can be told to take both from the menu:
Mode Dial Control Set = Set with Menu (Right on the row gives a two-option list, or, as on the a1 II, a table of one
cell per dial with Set All buttons below, where the Shooting Mode Dial's cell alone is put on Set with Menu and the
buttons are never pressed), then Shoot Mode, a two-axis carousel (Up/Down the family: Stills, Movie, S&Q
Motion, Time-lapse; Left/Right the exposure mode within it, the orange title naming it). Choosing a Movie family mode
puts the whole camera in Movie mode, its own menu up. The memory-recall modes (MR, M1-M4) are never chosen: recalling
a memory rewrites dozens of settings.

The switch is a run of its own, bracketed as every run is (decision 15): the start file is downloaded first, and
   --keep     leaves the camera in the new mode, the start file's name kept in kit2_pass2/mode_switch.json; the
              prove runs that follow (--eyes osd-all) take the camera as they find it and put that back. Refused
              while a switch waits in any run folder (one kept switch at a time);
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
--set takes a list row ("ROW=OPTION", set_row) or a two-box row's box ("S&Q Settings > Frame Rate Settings > Rec
Frame Rate=24p", 2026-11-18): a row the definition holds exactly two boxes under on that menu and boxes_run has proved
(two_box; anything else stops before the link opens when the definition and those proofs have the row on another
menu, or not that box). The box is set by boxes_run's own opening, look, stepping and OK (boxes_run.set_value: its
screen's consent, the drawn OK key, the dash check), and a download after it must show exactly one record moved, one
of that box's records in the definition (one for each movie format): the run says which records differ and stops
otherwise. Any stop exits 1, the switch waiting for --restore.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, match, ocr, paths, safety, session  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.live import LiveCamera, lit_text, open_refused  # noqa: E402
from camkit.vlm import check_readers  # noqa: E402
from camkit.match import clean  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.session import verify_restore  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import Failed, bar_text, enter_any, info_notice_ok, option_key, to_shooting  # noqa: E402
from proving.tables import (DIAL_ROW, cell_value, dial_cell, dial_option, dial_table, on_dial_cell,  # noqa: E402
                            to_dial_cell)
from runner import (EXIT_UNRESTORED, LATEST_SCAN, SHOWN_EXPOSURES, SHOWN_MODES, SWITCH_KEPT, add_in_argument,  # noqa: E402
                    add_info_ok_argument, close_screen, end_session, forget_refused, in_mode, load_scan,
                    menu_from_shooting, notes_named_or_exit, read_json, restore_checked, restoring, scan_arg, scan_mode,
                    scan_position, session_start, shown_mode, switch_advice, switch_left, switch_waiting, write_json)
from shootmode_run import FAMILIES, mode_name  # noqa: E402

BY_MENU, BY_DIAL = "Set with Menu", "Set with Dial"
SHOOTING_DIAL = "Shooting Mode Dial"           # the dial whose cell the table path puts on Set with Menu
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
    """Mode Dial Control Set = Set with Menu. Right on the row shows a note about the setting first (its OK leads on,
    2026-11-01), then one of two screens:
    - a two-option list: Down to Set with Menu, OK (choose_by_menu);
    - the table of one cell per dial with the Set All buttons below (the a1 II's: kit2_a1fin_movie_m
      00016_right.png), known as afreg_run knows it (proving.tables.dial_table): shooting_cell_by_menu puts the
      Shooting Mode Dial's cell alone on Set with Menu and never presses a Set All button.
    Any other screen stops the switch. The note's OK goes only as the run's --info-ok names it, or where the camera
    refuses MENU on it and OK is its only button (proving.screens.pass_note, since 2026-11-14): MENU on a note the camera
    takes cancels the row, and the switch stops there."""
    from proving.screens import pass_note
    find(cam, cycle, model, DIAL_ROW)
    lit = lit_text(cam.frame.image, cam.frame.path)     # the lit bar before Right: --info-ok's judgement reads it
    cam.press("right")
    for _ in range(2):
        if cam.read().kind == "list":
            break
        t = text(cam)
        if dial_table(cam.read().kind, t):
            break
        if not re.search(r"mode dial", t, re.I):
            raise Failed(f"Right on {DIAL_ROW!r} opened {cam.read().kind} ({cam.frame.path.name}): {t[:80]!r}")
        got = pass_note(cam, DIAL_ROW, lit)     # the note's OK
        if "refused" in got:
            raise Failed(f"Right on {DIAL_ROW!r} showed a note not passed: {got['refused']}")
    if cam.read().kind != "list" and dial_table(cam.read().kind, text(cam)):
        shooting_cell_by_menu(cam, say)
        return
    if cam.read().kind != "list":
        raise Failed(f"{DIAL_ROW!r}: no list came ({cam.read().kind}, {cam.frame.path.name})")
    choose_by_menu(cam, DIAL_ROW, say)
    if cam.read().kind == "notice":
        say(f"   notice after OK: {text(cam)[:80]!r}")
        cam.press("menu")


def choose_by_menu(cam, where: str, say):
    """The open two-option list put on Set with Menu: Down until the lit bar reads it (three presses at most), OK."""
    for _ in range(3):
        if option_key(bar_text(cam)) == option_key(BY_MENU):
            break
        cam.press("down")
    else:
        raise Failed(f"{where!r}: {BY_MENU!r} is not in its list ({bar_text(cam)!r})")
    say(f"{where}: choosing {BY_MENU!r}")
    cam.press("enter")


def shooting_cell_by_menu(cam, say):
    """Mode Dial Control Set's table (dial_by_menu): the Shooting Mode Dial's cell on Set with Menu, the other dials'
    cells and the Set All buttons untouched. The lit cell is brought to that dial's cell as the table walk found it and
    checked to be a cell whose dial, named at the right, is the Shooting Mode Dial (proving.tables.to_dial_cell, as
    afreg_run checks its dials), else the switch stops with nothing pressed but the close's MENU; that check is what keeps
    Enter off the Set All buttons (the playbook's rule 8). A cell already on Set with Menu gets no press: MENU back to the
    menu page. A cell on Set with Dial gets Enter, which must open the two-option list, chosen as the list path chooses
    (choose_by_menu); the table must then be back, its lit cell still that dial's and on Set with Menu, and MENU goes
    back to the menu page. A cell read as neither stops the switch, its reading (the camera's own setting) kept in the
    run's events.jsonl, never in the message; so does a menu page that MENU does not bring back."""
    where = f"{DIAL_ROW} / {SHOOTING_DIAL}"
    to_dial_cell(cam, dial_cell(SHOOTING_DIAL), SHOOTING_DIAL)
    shown = option_key(dial_option(cell_value(cam)))
    if shown == option_key(BY_MENU):
        say(f"{where}: already {BY_MENU!r}, nothing chosen")
        back_to_menu(cam, where)
        return
    if shown != option_key(BY_DIAL):
        cam.run.log("dial_cell_unread", step=where, frame=cam.frame.path.name, cell=cell_value(cam))
        raise Failed(f"{where}: its cell reads neither {BY_DIAL!r} nor {BY_MENU!r} ({cam.frame.path.name}; what it "
                     "read is in the run's events.jsonl)")
    if safety.confirmation(text(cam)):
        raise Failed(f"{DIAL_ROW}: the table reads like a confirmation ({cam.frame.path.name})")
    cam.press("enter")
    if cam.read().kind != "list":
        raise Failed(f"{where}: Enter opened {cam.read().kind}, not its list ({cam.frame.path.name})")
    choose_by_menu(cam, where, say)
    if not dial_table(cam.read().kind, text(cam)):
        raise Failed(f"{where}: after OK the screen is {cam.read().kind}, not the table ({cam.frame.path.name})")
    on_dial_cell(cam, SHOOTING_DIAL)
    if option_key(dial_option(cell_value(cam))) != option_key(BY_MENU):
        raise Failed(f"{where}: after OK its cell does not read {BY_MENU!r} ({cam.frame.path.name})")
    back_to_menu(cam, where)


def back_to_menu(cam, where: str):
    """MENU on Mode Dial Control Set's table, which must bring the menu page back (kit2_diffset_movie_switch_m
    00026_menu.png)."""
    cam.press("menu")
    if cam.read().kind != "menu":
        raise Failed(f"{where}: MENU on the table did not bring the menu page back ({cam.read().kind}, "
                     f"{cam.frame.path.name})")


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
    from proving.greyed import choice_refused
    refused = choice_refused(cam, "Shoot Mode", f"{FAMILIES[family]}, {got}")       # never OK on a greyed entry
    if refused:
        raise Failed(refused)
    say(f"Shoot Mode: {FAMILIES[family]} family, {got!r}: OK")
    cam.press("enter")
    if cam.read().kind == "notice":
        t = text(cam)
        cam.press("menu")
        raise Failed(f"Shoot Mode refused {got!r}: {t[:90]!r}")
    return got


def list_labels(path: list, mode: str = "Stills") -> list | None:
    """A list row's options as the map of the shooting `mode` names them (pass3_run.labels_of): pass 1's in Stills,
    another mode's crawl as framepos_run.mode_map finds it for the row (kit2_crawl_movie for Movie's File Format, the
    movie formats, a row pass 1's map has not); None where that map holds no list at `path` (or no map of the mode has
    the row): set_row then compares the bar with the option alone."""
    from pass3_run import labels_of
    mp = None
    if mode != "Stills":
        from framepos_run import mode_map
        mp = mode_map(mode, path=list(path))
        if mp is None:
            return None
    try:
        labels, kind = labels_of(list(path), mp)
    except (SystemExit, OSError, ValueError, KeyError):
        return None
    return labels if kind == "list" else None


def definition(run) -> dict:
    """The camera's definition (camkit.definitions, its public part), as filter_run reads it; {} where there is none
    (no definition file, or a run folder no camera's: its --set items are then list rows, as before)."""
    from camkit import definitions, paths
    try:
        p = definitions.path(run.dir.parent.name)
        return definitions.load_public(p) if p.exists() else {}
    except (OSError, ValueError, KeyError, paths.NoCamera):
        return {}


def box_proofs(run) -> set:
    """The paths boxes_run proved as boxes of a two-box screen: its proof lines (kind "list", "boxes": true; a
    checklist's carry "boxes" too, kind "checklist") in its run beside `run` (boxes_run.PROOF_RUN), each the row's path
    and a box's name; empty where there are none."""
    import boxes_run
    try:
        f = Path(run.dir).parent / boxes_run.PROOF_RUN / "proofs.jsonl"
        lines = f.read_text(encoding="utf-8").splitlines() if f.exists() else []
    except OSError:
        return set()
    out = set()
    for line in lines:
        if '"boxes": true' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("boxes") is True and r.get("kind") == "list" and isinstance(r.get("path"), list):
            out.add(tuple(r["path"]))
    return out


def _fits(s: dict, mode: str) -> bool:
    return s.get("row_mode") in (None, "", mode)


def _boxes_under(row: list, depth: int, doc: dict, mode: str | None) -> list:
    """The definition's settings one level under `row` (their row `depth` long), on the menu of `mode` (None: any)."""
    return [s for s in doc.get("settings") or [] if isinstance(s.get("row"), list) and len(s["row"]) == depth
            and s["row"][:-1] == row and (mode is None or _fits(s, mode))]


# The S&Q menu's own family of rows (2026-11-20): S&Q Settings and Time-lapse Settings, drawn on the S&Q menu whatever
# menu the definition names their two-box screens on (the a1 II's names the Movie menu for S&Q Settings > Frame Rate
# Settings, where the crawls first met it: row_mode Movie, row_menus Movie). On that menu two_box takes such a row only
# where the menu's own page scan draws its top label (family_row): the camera's own word, read from the scan.
FAMILY_ROWS = {"S&Q": ("S&Q Settings", "Time-lapse Settings")}


def family_row(path: list, mode: str, shown=None) -> bool:
    """Whether `path` is a row of the S&Q family (FAMILY_ROWS) on the menu of `mode`, whose own page scan draws its top
    label (`shown`: a callable giving the scan's row labels, called only here)."""
    return bool(path) and path[0] in FAMILY_ROWS.get(mode, ()) and shown is not None and path[0] in shown()


def two_box(path: list, mode: str, doc: dict, proved: set, shown=None) -> dict | None:
    """The two-box row `path` names a box of, on the menu of the shooting `mode` (S&Q Settings > Frame Rate Settings >
    Rec Frame Rate): the definition (`doc`) holds exactly two boxes under the row on that menu (settings whose row is the
    row's path and a box's name, their row_mode that mode or none), and boxes_run has proved the row's boxes (`proved`,
    box_proofs). The maps hold no such row (the crawl meets the screen as an unknown one, kit2_crawl_movie), and the
    definition alone does not tell a two-box screen from a submenu of two rows (Time-lapse Settings, BULB Timer Settings,
    40 rows of the a1 II's), so boxes_run's own proofs say which it is. {"row", "box", "names", "keys": the definition's
    records at that row and box, one for each movie format}, or None: a list row, set by set_row as before. A row of the
    S&Q family on the S&Q menu whose boxes the definition names on another menu only is taken where that menu's page
    scan draws it (family_row, `shown`)."""
    if len(path) < 2:
        return None
    row, box = list(path[:-1]), path[-1]
    under = _boxes_under(row, len(path), doc, mode)
    if not under and family_row(path, mode, shown):
        under = _boxes_under(row, len(path), doc, None)
    names = sorted({s["row"][-1] for s in under})
    if len(names) != 2 or not any((*row, n) in proved for n in names):
        return None
    return {"row": row, "box": box, "names": names, "keys": [s["key"] for s in under if s["row"][-1] == box]}


def set_plan(items: list, mode: str, doc: dict, proved: set, shown=None) -> list:
    """[(path, option, two_box or None)] for --set's items on the menu of `mode`; stops before the link opens on an
    item with no value, on a box its two-box row does not have, and on a two-box row the definition holds on another
    mode's menu only, unless it is the S&Q family's own and the menu's page scan draws it (two_box's `shown`)."""
    plan = []
    for item in items:
        row, _, option = item.partition("=")
        path, option = [x.strip() for x in row.split(" > ")], option.strip()
        if not option:
            sys.exit(f"--set {item!r} names no value (ROW=OPTION): nothing was sent to the camera")
        box = two_box(path, mode, doc, proved, shown)
        if box is not None and box["box"] not in box["names"]:
            sys.exit(f"--set {item!r}: {box['box']!r} is not one of its two boxes ({' and '.join(box['names'])}): "
                     "nothing was sent to the camera")
        anywhere = _boxes_under(path[:-1], len(path), doc, None) if box is None and len(path) > 1 else []
        names = {s["row"][-1] for s in anywhere}
        if len(names) == 2 and any((*path[:-1], n) in proved for n in names):
            menus = sorted({s.get("row_mode") or "" for s in anywhere} - {""})
            sys.exit(f"--set {item!r}: not a two-box row on the {mode} menu: the definition has it on the "
                     f"{', '.join(menus)} menu only. Nothing was sent to the camera")
        plan.append((path, option, box))
    return plan


def box_moved(box: dict, ch: list) -> str:
    """Why the records that differ (`ch`, camset.diff) after a box was set are not exactly one of that box's records
    (box["keys"], the definition's), or "" when they are."""
    if not ch:
        return f"no record of {box['box']} moved"
    if len(ch) > 1:
        return f"{len(ch)} records moved ({', '.join(c.key for c in ch)}), not one of {box['box']}'s alone"
    if ch[0].key not in box["keys"]:
        return f"{ch[0].key} moved, which the definition names no record of {box['box']} ({', '.join(box['keys'])})"
    return ""


def bar_names(reading, option: str, labels: list | None) -> bool:
    """Whether the lit bar's `reading` names `option`: as read, the radio ring left out (camkit.match.clean); else, where
    the mode's map gives the row's options (`labels`: list_labels) and names `option` among them once, by the one
    option camkit.match.icon_named names in the reading, an icon read as text before the label ("16:9 16:9", Aspect
    Ratio; "XAVES XAVC S HD", Movie's File Format)."""
    if option_key(clean(reading)) == option_key(option):
        return True
    want = match.index_of(labels, option) if labels else None
    return want is not None and match.icon_named(labels, reading) == want


def help_refused(kind: str, image) -> str:
    """drive.help_refused: why C4 may not be pressed here as Help, or "" (imported at the call: drive imports the
    provers)."""
    from drive import help_refused as refused
    return refused(kind, image)


def row_drawn(cam) -> tuple:
    """(whether the lit row of the menu or submenu page on show is drawn grey: True, False or None; the measure):
    proving.greyrow.row_grey, the reading kit/provers/greyrow_run.py judges a row by."""
    from proving.greyrow import row_grey
    return row_grey(cam)


def row_refused(cam, path: list) -> None:
    """Failed where the lit row (the last of `path`) is drawn grey: no Right on it, nothing pressed. Where its drawing
    cannot be told the row opens as before: a Right on a row that is grey after all brings the camera's notice, which
    set_row stops on, and chooses nothing."""
    grey, measure = row_drawn(cam)
    if grey:
        raise Failed(f"{' > '.join(path)}: the row is drawn grey (its label reads {measure:.0f}, {cam.frame.path.name}), "
                     "so it was not opened: kit/provers/greyrow_run.py asks the camera why; nothing was pressed on it")


def option_drawn(cam) -> tuple:
    """(whether the option under the cursor of the list on show is drawn grey: True, False, or None where neither eye
    can tell; the proving.greyed.Drawing it was judged by), by the provers' own reading (proving.greyed.drawing: a
    list's lit band by its pixels, as kit/prove_run.py --never-enter-grey judges a list's option; where the pixels
    cannot tell, the second reader's flag where it is asked, as greyed.judge takes it)."""
    from proving import greyed
    d = greyed.drawing(cam)
    if d.grey_by():
        return True, d
    if d.pixels is False or (d.pixels is None and d.reader is False):
        return False, d
    return None, d


def grey_refused(cam, path: list, option: str, labels) -> str:
    """Why `option`, under the cursor of the open list of the row at `path`, is not chosen, or "" where it is drawn
    white, judged on the frame on show, the one Enter would go on (option_drawn). Drawn grey: the camera's Help on it,
    through the kit's guarded Help alone where the screen allows it (proving.greyed.by_help: C4, the guide's OK, the
    list back on the option; drive.help_refused says where not), then MENU out of the list (proving.greyed.leave). A
    drawing neither eye can tell is no choice either (no guess): MENU alone. The words say what the option is, that it
    is drawn grey or not told, what Help named (its blocker only, never its text) and what was pressed."""
    from proving import greyed
    name = " > ".join(path)
    grey, d = option_drawn(cam)
    if grey is False:
        return ""
    frame = cam.frame.path.name
    level = f", its text reads {d.level:.0f}" if d.level is not None else ""
    if grey is None:
        greyed.leave(cam, name)
        return (f"{name}={option}: whether {option!r} is drawn grey cannot be told ({frame}{level}), so it was not "
                "chosen, no guess made: nothing was pressed on it but MENU, which closed its list")
    why = help_refused(cam.read().kind, cam.frame.image)
    if why:
        said, pressed = f"the camera's Help was not asked: {why}", "MENU"
    else:
        reason = greyed.by_help(cam, name, option, lambda: bar_names(bar_text(cam), option, labels))
        said = f"the camera's Help on it: {reason.said()}" if reason else "the camera's Help could not be asked"
        pressed = "Help (C4) and its guide's OK, then MENU"
    greyed.leave(cam, name)
    return (f"{name}={option}: {option!r} is drawn grey in its list (told by the {greyed.told(d.grey_by())}{level}, "
            f"{frame}), so it was not chosen; {said}; nothing was pressed on it but {pressed}, which closed its list")


def set_row(cam, cycle, model, path: list, option: str, say, mode: str = "Stills"):
    """A list row (a top-level row, or a submenu's: "Proxy Settings > Px Proxy Recording") put on `option` and left
    there: to the row by the scan, Right, Down through the list to the option (by the bar's text), OK; an
    information screen with buttons after the choice is taken with its OK where it reads as a table (Exposure Ctrl
    Type), and where it reads as no known kind left with MENU, its OK only where the camera refuses MENU and OK is its
    only button (proving.screens.info_notice_ok, 2026-11-14); a notice closed with MENU. For the state a prove run needs; the switch's --restore puts the start file back over it. The bar is read
    without the radio ring OCR can put before the saved option ("o Set with Dial", kit2_tables 08452_enter.png), so a
    row already on `option` is found there too (camkit.match.clean), and, by the labels the map of the shooting `mode`
    (the menu the camera shows) gives the row (list_labels), with an icon OCR reads as text before the label
    (bar_names: Aspect Ratio's "16:9 16:9", Movie's File Format "XAVES XAVC S HD"). A row inside a panel ("Viewfinder Bright. >
    Brightness Setup"): OK brings the panel back, its title the panel's own, with its slider lit (an OK in its footer,
    kit2_hdmi_watch 02362 -> 02363), which is the choice made, no information to take. What a screen after the choice
    reads is never said nor put in a failure (it can show the owner's values: a panel's number, a notice): the frame is
    named and the words go to the run's events.jsonl.
    Nothing drawn grey is entered to choose it (the owner's rule): a row the lit bar reads drawn grey is not opened
    (row_drawn; its notice is kit/provers/greyrow_run.py's to ask, after the camera's Help), and the option under the
    cursor is judged on the frame Enter would go on (grey_refused): drawn grey, or a drawing neither eye can tell, is
    no choice; the run stops with status 1, the switch waiting for its --restore."""
    find(cam, cycle, model, path[0])
    row_refused(cam, path[:1])
    if len(path) > 1:
        enter_any(cam, path, 0)
        row_refused(cam, path)
    cam.press("right")
    if cam.read().kind != "list":
        raise Failed(f"Right on {' > '.join(path)!r} opened {cam.read().kind}, not a list ({cam.frame.path.name})")
    labels = list_labels(path, mode)
    for _ in range(24):
        if bar_names(bar_text(cam), option, labels):
            break
        cam.press("down")
    else:
        # the option the list was on can be the owner's: kept in the run's events, never in the message
        cam.run.log("set_row_missed", step=" > ".join(path), frame=cam.frame.path.name, bar=bar_text(cam))
        raise Failed(f"{' > '.join(path)!r}: {option!r} did not come round in its list ({cam.frame.path.name}; what "
                     "its bar read is in the run's events.jsonl)")
    refused = grey_refused(cam, path, option, labels)
    if refused:
        raise Failed(refused)
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
            cam.run.log("set_row_information", step=" > ".join(path), frame=info["frame"], text=" ".join(info["text"].split()),
                        left_by=info.get("left_by"))
            how = "closed with MENU" if info.get("left_by") == "menu" else "taken with its OK"
            say(f"   information after the choice, {how} ({info['frame']}; its words are in the run's events.jsonl)")


def switched_mode(to: str) -> str:
    """The shooting mode whose menu the camera shows after a switch to `to` (runner.SCAN_MODES): a stills exposure
    mode (MODES: P, A, S, M, Auto) is Stills, a family its own (S&Q Motion and Time-lapse: S&Q)."""
    return "Stills" if to in MODES else scan_mode(to)


def restore_left(start: Path) -> frozenset:
    """The records --restore leaves out of its count for the start file `start`: the memory slots' registration records
    of its model (camkit.not_by_file.memory_left); none where the file cannot be read."""
    from camkit.not_by_file import memory_left
    try:
        return memory_left(camset.read(start).model)
    except Exception:
        return frozenset()


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
                         "run needs (a submenu's row as 'Proxy Settings > Px Proxy Recording=On'), or a two-box row's "
                         "box, named as boxes_run names it ('S&Q Settings > Frame Rate Settings > Rec Frame Rate=24p'), "
                         "checked by a download that one of that box's records moved; --restore covers it")
    ap.add_argument("--scan", default=LATEST_SCAN, type=scan_arg,
                    help="the page scan of the menu the camera shows now (a run in runs/<model>_fw<fw>/, or a path; "
                         "default: the camera's latest page scan made in that mode, runner.latest_scan)")
    add_in_argument(ap, default=None, said="Stills for a switch; with --set, the mode the waiting switch left")
    ap.add_argument("--run", default="kit2_pass2")
    add_info_ok_argument(ap)    # Mode Dial Control Set's note before its list (dial_by_menu: proving.screens.pass_note)
    a = ap.parse_args()
    notes_named_or_exit(a.info_ok, [DIAL_ROW])
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
        # a memory slot the switch's session registered (memreg_run in a Movie, S&Q or Time-lapse slot) stays filled:
        # its registration records no settings file sets back are said by key and left out of the count
        # (camkit.not_by_file.memory_left), as upload_check leaves them out; every other record counts
        left = restore_left(start)
        try:
            # the start file goes back when anything differs from it, even if the shooting screen does not come; a
            # restore that raises exits EXIT_UNRESTORED (runner.restoring) and the kept record stays
            with restoring("mode_switch --restore"), Link(run) as link:
                hdmi.attach(link)
                ending = end_session(link, hdmi, start, "the restore", tag="restore", expected=left)
        finally:
            hdmi.close()
        # checked after an upload (a reconnect, 40 s); with nothing to upload, the end download already said 0 differ
        if not restore_checked(run, ending, start, expected=left):
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
        scanned = []

        def shown() -> set:
            """The row labels this menu's page scan draws (two_box's word for the S&Q family's rows), read once."""
            if not scanned:
                scanned.append(load_scan(in_mode(a.scan, now)))
            return {r.get("label") for p in scanned[0][1].values() for r in p.get("rows") or [] if r.get("label")}
        # a box no two-box row here has: stopped before the link opens
        plan = set_plan(a.set, now, definition(run), box_proofs(run), shown)
        cycle, model = scanned[0] if scanned else load_scan(in_mode(a.scan, now))
        check_readers()     # no reader listed: stop before the link opens, nothing pressed
        import boxes_run
        hdmi = eyes_from_config(run)
        try:
            with Link(run) as link:
                hdmi.attach(link)
                # the session's start (runner.session_start): the shooting screen, the download, the menu's lock waited
                # out; the session leaves its settings for the waiting switch's --restore
                before = last = session_start(link, hdmi, "the download before the settings", "before-set",
                                              reach=to_shooting, say=False)
                cam = LiveCamera(link, hdmi, run, may_open=MAY_OPEN)
                try:
                    for path, option, box in plan:
                        if box is None:
                            open_menu(cam)
                            set_row(cam, cycle, model, path, option, say, mode=now)
                            close_screen(cam, link)
                            time.sleep(1.0)
                            continue
                        # a two-box row's box: boxes_run's own opening, look, stepping and OK (from the shooting
                        # screen), then a download that says the records that moved: exactly one of that box's
                        got = boxes_run.set_value(cam, link, cycle, model, box["row"], box["names"], box["box"], option)
                        say(f"{' > '.join(path)}: {option!r} chosen (its values {', '.join(got['values'])}; it held "
                            f"{got['held']!r})")
                        close_screen(cam, link)
                        to_shooting(link, hdmi, f"the download after {box['box']}")
                        time.sleep(2)
                        now_dat = link.download("after-box")
                        moved = camset.diff(camset.read(last), camset.read(now_dat))
                        say(f"   {len(moved)} records moved: {', '.join(f'{c.key} {c.before!r} -> {c.after!r}' for c in moved)}")
                        why = box_moved(box, moved)
                        if why:
                            raise Failed(f"{' > '.join(path)}={option}: {why}")
                        last = now_dat
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
        except (Failed, boxes_run.NotOffered, safety.Refused) as e:
            # the switch stays waiting: its --restore puts the start file back over whatever was set
            say(f"stopped: {type(e).__name__}: {e}")
            sys.exit(1)
        finally:
            hdmi.close()
        return
    if not a.to:
        sys.exit("--to names the mode (Movie, S&Q Motion, Time-lapse, Stills, or P/A/S/M), or --restore")
    if kept.exists():
        sys.exit(f"A switch is still waiting in {kept}; nothing was sent to the camera.\n{switch_advice(kept)}")
    if a.keep:
        # a second kept switch, in another run folder, would leave the kit's record saying the camera is in two modes,
        # and every run would then refuse to start (runner.refuse_switched): one waits at a time, whatever its folder
        for folder, left in switch_waiting():
            f = folder / KEPT
            where = f"{left} mode" if left else "a mode its record does not name"
            sys.exit(f"A switch is still waiting in {paths.shown(f)} (it left the camera in {where}): a second kept "
                     "switch would leave the kit's record naming two modes, and every run would then refuse to start. "
                     f"Nothing was sent to the camera.\n{switch_advice(f)}")
    if a.to in MODES:
        family, mode = 0, MODES[a.to]
    elif a.to in FAMILIES:
        if a.mode is not None and a.mode not in MODES:
            sys.exit(f"--mode {a.mode!r}: one of {sorted(MODES)}")
        family, mode = FAMILIES.index(a.to), MODES.get(a.mode)
    else:
        sys.exit(f"--to {a.to!r}: one of {FAMILIES} or {sorted(MODES)}")
    cycle, model = load_scan(in_mode(a.scan, a.in_mode or "Stills"))
    check_readers()     # no reader listed: stop before the link opens, nothing pressed
    from proving import greyed
    greyed.say_marks()  # the grey readings this run will not enter on alone (proving.greyed's memory)
    hdmi = eyes_from_config(run)
    start = after = None
    switch_failed = False           # a switch that did not happen exits 1, so --keep's chain does not go on in the old mode
    switched = False                # the switch made, so a failure after it is the upload's, not the switch's
    try:
        with Link(run) as link:
            hdmi.attach(link)
            # the session's start (runner.session_start): the shooting screen, the start download, the menu's lock
            # waited out; the session ends in the switch kept, or with the start file uploaded, its own
            start = session_start(link, hdmi, reach=to_shooting, say=False)
            cam = LiveCamera(link, hdmi, run, may_open=MAY_OPEN)
            try:
                open_menu(cam)
                dial_by_menu(cam, cycle, model, say)
                close_screen(cam, link)
                time.sleep(1.0)
                open_menu(cam)
                title = shoot_mode(cam, cycle, model, family, mode, say)
                # the camera's mode is the switch's from here: the menu's lock after a download goes by it
                # (camkit.session.MODE, which runner.load_scan set to the mode the run started in)
                session.MODE = switched_mode(a.to)
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
            session.MODE = a.in_mode or "Stills"        # the start file's mode again (the lock's rule with it)
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
                session.MODE = a.in_mode or "Stills"    # back on the start file, or as it was: the start's mode
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
