"""Pass 1 on the camera: open every safe top-level row, walk its screen by type, back out with MENU.

    .venv/bin/python -u kit/crawl_run.py [--limit N] [--scan kit2_page_scan]

Uses the page scan's Down cycle and confirmed page model (camkit.crawl): before acting at any
position the screen must match what the scan recorded there. Presses: MENU, the arrows, never
Enter. Rows on the never-open list are skipped by their confirmed label.

Settings are downloaded before and after and diffed (pass 1 must change nothing); if anything changed, the
start file is uploaded and the restore checked (docs/decisions/0015). --limit stops
after opening N rows (for supervised tries). A STOP file (<run>/STOP) cancels any open
dialog with MENU and stops. It never disconnects with a menu open.

--network walks the Wi-Fi and Bluetooth settings and identity rows a dated owner decision in the reviewed scope names
({"lifts": "network", ...}: runner.network_decided_or_exit, docs/decisions/0008), looked at only: Down round the row's
list or carousel, never a second axis, a panel or a submenu (--panels too), and nothing chosen whatever options a
decision names; never an address screen (only kit/drive.py opens one), never a row the page model stored another
reason for (a model built before the class existed says "by hand only": build it again with kit/page_model.py). The run
asks local readers only (camkit.vlm.LOCAL_ONLY), marks its folder so (camkit.vlm.LOCAL_MARKER: the tools that read its
frames later ask local readers only too), and writes each such row's class in rows.jsonl ("network"); for a Wi-Fi or
Bluetooth setting (never an identity row) that answers Right with a notice the kit knows ("This function is currently
disabled.", "... not available as follows ...") naming no identity or credentials, the notice's text too ("notice":
safety.notice_kept), so why the row is greyed is recorded. From its start to its end such a run prints and keeps no text
read off the screen: a row's label only where it is a row label the kit knows (runner.known_labels, the decisions' own
rows, the decided row a lifted row was opened as), else "(withheld)", and the quoted texts of an outcome, a note or an
error withheld (kept_row); its folder is owner-only (camkit.runs: folders 0700, files 0600, on POSIX), checked at the
end.

A row whose opening the camera refuses because of the lit row itself (safety.RowRefused: the lit row read as one the
run may not open, or read by no reader) before any press went out on it is skipped, "skipped: refused (...)" with the
reason's quoted texts withheld, and the lap goes on (camkit.crawl.visit_row); any other refusal, and a refusal after a
press on the row, cancels the lap. Once its start file is back and checked, a run a refusal stopped exits EXIT_REFUSED
(7), and one stopped short by anything else (an error, a screen the scan does not know, the start label not reached,
the crawl lost or off the scan) EXIT_INCOMPLETE (8); a STOP, the lap complete or --limit reached exit 0; a restore that
did not check out exits EXIT_UNRESTORED (4) (kit/exit_status.py; kit/tools/chain.py stops on each).

Navigation guesses nothing: the lit group in the group column is read whole, by its letters and digits, whatever icon
glyph the bar or the scan glued on (group_near); where it cannot be read, it is read again once after a short settle,
then on the camera's own picture of its screen (the SDK's OSD image); if none names it, nothing more is pressed and the
row is not reached (jump, from_groups: lit_group). The menu found reopened with the cursor in the group column is stepped
into a group it may enter before the lap begins (find_position, as kit/drive.py finds it).

Results: kit2_crawl/rows.jsonl (one line per row), frames and presses in shots/ and events.jsonl. Every run folder
named here is in the camera's runs/<model>_fw<fw>/ (camkit.paths).
"""
import argparse
import contextlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import ocr, safety, screen  # noqa: E402
from camkit.screen import same_position  # noqa: E402
from camkit.crawl import crawl  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link, StopRequested  # noqa: E402
from camkit.live import lit_text, LiveCamera, submenu_labels, text_of  # noqa: E402
from camkit.vlm import check_readers  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.session import wait_for  # noqa: E402
from runner import (EXIT_INCOMPLETE, EXIT_REFUSED, EXIT_UNRESTORED, add_network_argument, add_scan_argument,  # noqa: E402
                    close_for_restore, end_session, known_groups, known_labels, label_readings, load_scan,
                    network_decided_or_exit, network_readings, network_values, restore_checked, row_readings,
                    row_values, values_withheld, wait_shooting)


def summary(r) -> dict:
    w = r.walk
    opts = None
    if w is not None and type(w).__name__ == "SubCrawl":    # a crawled submenu: its rows, nested
        return {"page": r.page, "slot": r.slot, "label": r.label, "outcome": r.outcome, "kind": r.kind,
                "presses": r.presses, "submenu": [summary(x) for x in w.rows], "note": w.stopped}
    if w is not None:
        opts = ([len(x.options) for x in w.rows] if type(w).__name__ == "GridWalk" else
                len(w.options) if hasattr(w, "options") else
                [len(f.options) for f in w.fields] if hasattr(w, "fields") else
                {k: len(v[0]) for k, v in w.axes.items()})
    out = {"page": r.page, "slot": r.slot, "label": r.label, "outcome": r.outcome, "kind": r.kind,
           "options": opts, "presses": r.presses, "note": getattr(w, "note", "") if w else ""}
    if getattr(r, "network", ""):
        out["network"] = r.network                          # opened under a network decision: safety.lift_class
    if getattr(r, "decided", ""):
        out["decided"] = r.decided                          # the decided row it was opened as (camkit.crawl.network_row)
    if getattr(r, "notice", ""):
        out["notice"] = r.notice                            # why a greyed network setting is unavailable (notice_kept)
    frames = option_frames(w)
    if frames:
        out["frames"] = frames                              # per option, the saved frame it was seen on
    if w is not None and hasattr(w, "details"):           # a deep carousel walk: per option, what Right did
        det = {}
        for k, v in w.details.items():
            det[k] = {}
            if "axis" in v:
                det[k]["axis"] = {key: (len(x[0]), x[1]) for key, x in v["axis"].axes.items()}
            if "panel" in v:
                det[k]["panel"] = v["panel"]
                pw = v.get("walk")
                if type(pw).__name__ == "SubCrawl":                  # a panel that is a submenu: its rows
                    det[k]["rows"] = [summary(x) for x in pw.rows]
                elif pw is not None:
                    det[k]["options"] = (len(pw.options) if hasattr(pw, "options") else None)
                    det[k]["frames"] = option_frames(pw)
        out["details"] = det
    return out


def option_frames(w):
    """The saved frame of every option a walk saw (for reading labels afterwards)."""
    def of(walk):
        return [getattr(walk.screens[sig], "frame_path", None) for sig in walk.options] if walk else []
    name = type(w).__name__
    if name == "Walk":
        return of(w)
    if name == "DeepWalk":
        return of(w.main)
    if name == "FieldsWalk":
        return [of(f) for f in w.fields]
    if name == "GridWalk":
        return [of(r) for r in w.rows]
    return None


def group_closed(cam, name: str, known=()) -> str | None:
    """Why the group column never steps into the group named `name` (safety.group_refused: never-open, or one letter
    from a never-open group's or action's name), or None; a name the run may open (the camera's may_open: drive.py
    --allow) lifts it where its words are in the name, compared as the guards fold them (live.open_refused), as before
    2026-11-13."""
    refused = safety.group_refused(name, known)
    seen = safety.clean_label(safety.fold(name))
    if refused and any(safety.clean_label(safety.fold(m)) and safety.clean_label(safety.fold(m)) in seen
                       for m in getattr(cam, "may_open", ())):
        return None
    return refused


def go_to(cam, cycle, model, j, label, place=None):
    """Step from cycle position j to the row labelled `label`, the short way round, checking every
    screen against the scan. Returns the new position, or None if a screen was not the expected one. place: (tab,
    group) the row must be in (kit/drive.py --owner: the owner decision's), its page's breadcrumb read so in the scan;
    none there, None."""
    from page_model import same_text
    tabs = ("Shooting", "Exposure/Color", "Focus", "Network", "Setup")

    def found(named) -> list:
        return [i for i, p in enumerate(cycle) if p["kind"] == "menu" and p["page"] in model
                and p["row"] is not None and p["row"] < len(model[p["page"]]["rows"])
                and named(model[p["page"]], model[p["page"]]["rows"][p["row"]])]
    matches = found(lambda page, row: same_text(row["label"], label))
    fallback = not matches
    if fallback:
        # the page model's label is one reading (OCR's "LANIP Address Setting", the Wired LAN page's icon glued on); the
        # row is found by any reading it keeps, or by that reading with an icon of its own page glued on (row_named): only
        # where exactly one row reads so, and only where its lit bar reads the row once there (bar_on_row, below)
        matches = found(lambda page, row: row_named(row, label, page_group(page)))
    if place is not None:
        def crumb(i):
            parts = [unglued(x.strip()) for x in (model[cycle[i]["page"]]["breadcrumb"] or "").split(" > ")]
            return [safety.plain(x) for x in parts[:2]]
        matches = [i for i in matches if crumb(i) == [safety.plain(x) for x in place]]
    # My Menu repeats rows from other tabs (Pre-Capture Settings is on My Menu 1): prefer the real one
    real = [i for i in matches if model[cycle[i]["page"]]["breadcrumb"].startswith(tabs)]
    if fallback and len({(cycle[i]["page"], cycle[i]["row"]) for i in (real or matches)}) > 1:
        print(f"no row labelled {label!r} in the page model, and {len(real or matches)} rows read as it: none is gone "
              "to", flush=True)
        return None
    target = (real or matches or [None])[0]
    if target is None:
        print(f"no row labelled {label!r} in the page model", flush=True)
        return None
    n = len(cycle)
    ahead = (target - j) % n
    groups = page_groups(cycle, model)
    here, there = groups.get(cycle[j]["page"]), groups.get(cycle[target]["page"])
    if min(ahead, n - ahead) > JUMP_MIN and here and there and here != there and cycle[j]["kind"] == "menu":
        # a group whose name is on the never-open list (the Network tab's "FTP Transfer" reads as the sending
        # action, Accessibility as the Screen Reader's) is never entered from the group column: the rows are
        # walked to instead, the long way, which passes no Right or Enter on it (2026-11-07). The name as the page model
        # read it is judged with its slips: one letter from a never-open group's or action's name ("FTP Transter",
        # 2026-11-13) refuses too (safety.group_refused), before any press
        group_name = (group_names(cycle, groups, model, there[0]) + [""] * (there[1] + 1))[there[1]]
        refused = group_closed(cam, group_name, known_groups(model))
        if refused:
            print(f"walking {min(ahead, n - ahead)} rows to {label!r}: its group {group_name!r} is never entered from "
                  f"the group column ({refused})", flush=True)
        else:
            print(f"jumping to {label!r} by the tab and group columns ({there[0]}, group {there[1] + 1}) "
                  f"instead of {min(ahead, n - ahead)} rows", flush=True)
            j = jump(cam, cycle, groups, target, model)
        if j is None:
            return None
        ahead = (target - j) % n
    key, step = ("down", 1) if ahead <= n - ahead else ("up", -1)
    print(f"stepping {min(ahead, n - ahead)} x {key} to {label!r}", flush=True)
    while j != target:
        cam.press(key)
        j = (j + step) % n
        if not same_position(cam.read(), cycle[j]["screen"]):
            return None
    if fallback:
        # a row found by another reading: its lit bar, read now, must be the row (safety.bar_on_row: its label, or the
        # reading with its page's icon glued on where another reader read the row exactly, or that icon as the live bar
        # shows it, a letter misread, glued on or set apart, forming no other label the kit knows), else nothing more
        row = model[cycle[j]["page"]]["rows"][cycle[j]["row"]]
        entry = {"group": page_group(model[cycle[j]["page"]]), "readings": [row.get("label") or "", *row_readings(row)]}
        lit = lit_text(cam.frame.image, cam.frame.path)
        if not safety.bar_on_row(lit, label, {label: [entry]}, label_readings(model)):
            print(f"the row the page model reads as {label!r} is lit, but its bar does not read it: "
                  f"{said(cam, lit)}", flush=True)
            return None
    return j


def page_group(page) -> str:
    """A page model page's group: its breadcrumb's second part ("Network > Wired LAN": Wired LAN), "" without one."""
    crumb = str((page or {}).get("breadcrumb") or "").split(" > ")
    return crumb[1].strip() if len(crumb) > 1 else ""


def row_named(row: dict, label: str, group: str) -> bool:
    """Whether the page model's row `row`, on a page of the group `group`, is the row `label` names, for go_to where its
    label as the page model voted it is no reading of `label`: one of the readings it keeps (runner.row_readings: its
    label, each reader's) is `label` exactly once plain (safety.plain), or is `label` with an icon of its page read as
    letters glued to its front (safety.glued_icon: a word of the page's own group name, of at most safety.ICON_MAX
    letters, naming nothing never-open or of identity, the label's class kept). "LANIP Address Setting" on the Wired LAN
    page is IP Address Setting; a word set before a label ("LAN IP Address Setting", "No Wi-Fi Connect") is another
    label. Only where to go: whether a row may be opened is judged at the press, as ever."""
    want = safety.plain(label)
    if not want:
        return False
    for t in row_readings(row):
        seen = safety.plain(t)
        if seen == want:
            return True
        if len(seen) > len(want) and seen.endswith(want) and safety.glued_icon(seen[:-len(want)], label, group) is None:
            return True
    return False


# The menu's tab column, top to bottom, below Main (never passed through: it is a tile page). From a
# page's rows Left moves to its group column and Left again to the tabs; in the tabs Up/Down moves a
# whole tab, and Right, Down by groups, Right lands in a group's rows (2026-11-02, the owner: "hitting
# left to get in to root sections quicker")
TABS = ["Shooting", "Exposure/Color", "Focus", "Playback", "Network", "Setup", "My Menu"]
JUMP_MIN = 8            # a walk this short is quicker than the columns


def page_groups(cycle, model) -> dict:
    """{page key: (tab, group)}: a tab's groups numbered from 0 in the Down cycle's order, a group
    being a run of pages with one breadcrumb (Image Quality/Rec's two pages are one group)."""
    order = []
    for p in cycle:
        if p["kind"] == "menu" and p["page"] in model and p["page"] not in order:
            order.append(p["page"])
    crumb = lambda k: model[k]["breadcrumb"] or ""
    tab = lambda k: crumb(k).split(" > ")[0]
    # start at a tab's first page (the scan's cycle starts wherever the menu opened)
    s = next((i for i in range(len(order)) if tab(order[i]) != tab(order[i - 1])), 0)
    order = order[s:] + order[:s]
    out, seen = {}, {}
    for i, k in enumerate(order):
        names = seen.setdefault(tab(k), [])
        if not names or crumb(order[i - 1]) != crumb(k):
            names.append(crumb(k))
        if tab(k) in TABS:
            out[k] = (tab(k), len(names) - 1)
    return out


def tab_shown(text: str) -> str | None:
    """The tab named first in a menu screen's text (the breadcrumb leads it)."""
    hits = [(m.start(), t) for t in TABS
            for m in [re.search(re.escape(t).replace("/", r"\s*/\s*"), text[:40], re.I)] if m]
    return min(hits)[1] if hits else None


def find_position(cam, cycle, model):
    """The scan position the open menu shows. The menu opens on the page last used, and a value changed
    there since the scan (Bluetooth Function, 2026-11-02) matches no position: then by the columns to
    the Shooting tab's first group, which does. A menu that opens with the cursor in the group column (where a refused
    jump left it, 2026-11-13) is stepped into the rows of a group that may be entered first (from_groups), never by a
    Right on a group refused."""
    j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
    if j is not None or cam.read().kind != "menu":
        return j
    if cam.read().focus == "groups":
        j = from_groups(cam, cycle, model)
        if j is not None or cam.read().kind != "menu" or cam.read().focus != "rows":
            return j
    elif cam.read().focus != "rows":
        return None
    groups = page_groups(cycle, model)
    first = next((i for i, p in enumerate(cycle) if groups.get(p["page"]) == ("Shooting", 0)), None)
    if first is None:
        return None
    print("the menu opened on a page the scan does not match: to the Shooting tab by the columns", flush=True)
    return jump(cam, cycle, groups, first, model)


def menu_text(cam) -> str:
    """All the text OCR reads on the menu screen now (the breadcrumb leads it: the tab, in the tab and group columns)."""
    f = cam.frame
    return ocr.text_in(ocr.read([f.path])[f.path], (0, 0, 640, 480)).strip()


TEXT_WITHHELD = "(the text read withheld)"


def said(cam, text: str) -> str:
    """What a print shows of a text read off the screen now: the text, but on a --network or --owner run (the camera
    given a network decision's rows or an owner decision's row: LiveCamera.network, LiveCamera.owner) nothing of it,
    not even its length, which can tell a row's values apart (2026-11-14), since it may hold a device's name, an address
    or a value (drive.py's say() withholds alike)."""
    if getattr(cam, "network", None) or getattr(cam, "owner", None):
        return TEXT_WITHHELD
    return repr(str(text or "")[:60])


def group_near(text: str, names: list) -> int | None:
    """Which of a tab's groups a lit group's text names, judged whole: its letters and digits (safety.name_key), as read
    or with a glued icon glyph left off (unglued), the very group's name, or, for one of at least safety.GROUP_MIN, one
    letter from it (safety.one_apart: the scan read "FTP Transter" where the camera draws "FTP Transfer"). None when no
    group, or more than one, is so named: a lit row's text ("File Format  RAW") names no group ("File"), so a focus read
    as the group column on a page of rows sends no Right onto that row."""
    keys = {k for k in (safety.name_key(text), safety.name_key(unglued(text))) if k}
    got = [i for i, n in enumerate(names) if n and any(
        k == safety.name_key(n) or (len(k) >= safety.GROUP_MIN and safety.one_apart(k, safety.name_key(n))) for k in keys)]
    return got[0] if len(got) == 1 else None


def from_groups(cam, cycle, model):
    """From the group column into a group's rows, for a menu that opened with the cursor there (a jump refused before
    its Right left it so, and MENU reopens where the cursor was, 2026-11-13): the tab read off the breadcrumb, the lit
    group off its bar (group_near, judged whole), then Up or Down to the nearest group of that tab whose name may be
    entered (the lit one first, if it may; safety.group_refused on the page model's name and on the lit bar as read
    there, each judged with its slips) and one Right into its rows, only on a screen still read as the menu with the
    focus in the group column and its lit bar naming that very group. Up and Down in the column only light another
    group. Returns the scan position landed on, or None; when the tab or the lit group cannot be read, or no group of the
    tab may be entered, it presses nothing (the caller's MENU closes the menu). On a --network or --owner run nothing it
    read off the screen is printed (said)."""
    groups = page_groups(cycle, model)
    known = known_groups(model)
    tab = tab_shown(menu_text(cam))
    if tab is None:
        print(f"the menu opened in the group column and its tab could not be read: {said(cam, menu_text(cam))}",
              flush=True)
        return None
    names = group_names(cycle, groups, model, tab)
    lit = lambda: lit_text(cam.frame.image, cam.frame.path)        # noqa: E731
    at = lit_group(cam, names, lit, group_near)
    if at is None:
        print(f"the menu opened in the group column and the lit group could not be read, nor on a second look or the "
              f"camera's own picture: {said(cam, lit())}; nothing is pressed", flush=True)
        return None
    order = sorted((i for i, n in enumerate(names) if n), key=lambda i: (abs(i - at), i))
    target = next((i for i in order if not safety.group_refused(names[i], known)
                   and not (i == at and safety.group_refused(lit(), known))), None)
    if target is None:
        print(f"the menu opened in the group column of {tab!r}, and none of its groups is entered from there: closing "
              "it with MENU", flush=True)
        return None
    print(f"the menu opened in the group column of {tab!r} on group {at + 1}: to group {target + 1} "
          f"({names[target]!r}) and into its rows", flush=True)
    for _ in range(abs(target - at)):
        cam.press("down" if target > at else "up")
    now, screen_now = lit(), cam.read()
    if screen_now.kind != "menu" or screen_now.focus != "groups":
        print(f"the screen no longer reads as the group column ({screen_now.kind}, focus {screen_now.focus}): no Right",
              flush=True)
        return None
    if group_near(now, names) != target or safety.group_refused(now, known):
        print(f"the group column did not reach group {target + 1} of {tab!r}, or reads as one never entered: "
              f"{said(cam, now)}", flush=True)
        return None
    cam.press("right")
    j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
    if j is None:
        print(f"the group's rows are not a screen the scan recorded ({cam.read().kind})", flush=True)
    return j


def group_names(cycle, groups, model, tab) -> list:
    """A tab's group names in column order, from the pages' breadcrumbs ("Setup > Operation Customize")."""
    out = {}
    for p in cycle:
        tg = groups.get(p.get("page"))
        if tg and tg[0] == tab and p["page"] in model:
            crumb = (model[p["page"]]["breadcrumb"] or "").split(" > ")
            out.setdefault(tg[1], crumb[1] if len(crumb) > 1 else "")
    return [out.get(i, "") for i in range(max(out, default=-1) + 1)]


def unglued(name: str) -> str:
    """A group's name without the icon glyph OCR glues to its front ("DCnct./Remote Sht.", "ICnct./Remote Sht.": one
    reading per reader, 2026-11-07): a lone capital before a capitalised word."""
    return re.sub(r"^[A-Z](?=[A-Z][a-z])", "", name or "")


def group_shown(text: str, names: list) -> int | None:
    """Which of a tab's groups the breadcrumb at the top of a menu screen names, or None. A name is looked for as
    the scan read it and without a glued icon glyph (unglued), since the lit text glues its own."""
    from page_model import same_text
    head = text[:80]
    loose = lambda n: re.escape(n).replace("/", r"\s*/\s*").replace("\\ ", r"\s*").replace(" ", r"\s*")
    hits = [(m.start(), i) for i, n in enumerate(names) if n
            for m in [re.search(loose(n), head, re.I) or re.search(loose(unglued(n)), head, re.I)] if m]
    if hits:
        return min(hits)[1]
    words = head.split(">")
    return next((i for i, n in enumerate(names) if n and len(words) > 1 and same_text(words[1].split("\n")[0], n)), None)


GROUP_SETTLE = 0.6          # s before the lit group, unread, is read again once (lit_group)


def osd_lit(cam) -> str:
    """The text the orange cursor lights on the camera's own picture of its screen (the SDK's OSD image, fetched into a
    file of this process's own and removed after, as camkit.live.osd_kind fetches it; into the camera's own folder while
    a row whose values are withheld is open), or "" when there is no link or it cannot be fetched or read."""
    import os
    import tempfile
    from camkit.frames import load
    link = getattr(cam, "link", None)
    if link is None or not hasattr(link, "osd"):
        return ""
    folder = getattr(cam, "osd_folder", lambda: None)()
    path = (Path(folder) / "group.png" if folder is not None
            else Path(tempfile.gettempdir()) / f"camkit_osd_{os.getpid()}_group.png")
    try:
        return lit_text(load(link.osd(path)).image, path)
    except Exception:
        return ""
    finally:
        for left in (path, path.with_name(path.name + ".part")):
            with contextlib.suppress(OSError):
                left.unlink()


def lit_group(cam, names: list, lit, named=None):
    """Which of a tab's groups (`names`) the group column's lit bar names (`named`: group_near by default, the name judged
    whole by its letters and digits, whatever icon glyph the bar or the scan glued on), or None: read as it is, then
    once more after GROUP_SETTLE s (the camera's own frame read afresh where the camera can: cam.refresh), then on the
    camera's own picture of its screen (osd_lit). Nothing is pressed here, and nothing guessed: None leaves the caller
    to press nothing more."""
    named = named or group_near
    at = named(lit(), names)
    if at is not None:
        return at
    time.sleep(GROUP_SETTLE)
    refresh = getattr(cam, "refresh", None)
    if callable(refresh):
        with contextlib.suppress(Exception):    # a read that fails is no reading
            refresh("group-again")
    at = named(lit(), names)
    if at is not None:
        return at
    seen = osd_lit(cam)
    return named(seen, names) if seen.strip() else None


def jump(cam, cycle, groups, target, model):
    """From a page's rows to the target row's group by the columns: Left twice to the tabs, Up/Down to
    its tab (read off the screen), Right, Down to its group, Right into its rows. Returns the position
    landed on, as the scan recorded it, or None. The lit group is read as from_groups reads it (lit_group, group_near:
    the name judged whole by its letters and digits, equal or, for one of at least safety.GROUP_MIN, one letter apart,
    exactly one group of the tab; a bar read with another icon glyph than the scan's, "(Cnct./Remote Sht." for the
    scan's "[Cnct./Remote Sht.", is the same group, 2026-11-14). The last Right goes out only where the lit group, as
    read there, is the target's and no group the column never enters (safety.group_refused, its slips judged), and the
    screen still reads as the menu with the focus in the group column: else nothing more is pressed, and the caller's
    MENU closes the menu with the cursor in the column, where find_position steps back into the rows from. On a
    --network or --owner run nothing it read off the screen is printed (said)."""
    tab, group = groups[cycle[target]["page"]]
    for _ in range(2):
        cam.press("left")
    now = tab_shown(menu_text(cam))
    if now is None:
        print(f"the tab column's tab could not be read: {said(cam, menu_text(cam))}", flush=True)
        return None
    d = TABS.index(tab) - TABS.index(now)
    for _ in range(abs(d)):
        cam.press("down" if d > 0 else "up")
    if d and tab_shown(menu_text(cam)) != tab:
        print(f"the tab column did not reach {tab!r}: {said(cam, menu_text(cam))}", flush=True)
        return None
    cam.press("right")
    # the group column opens on the group last used in that tab, not its first (three Downs from Operation
    # Customize reached Accessibility, 2026-11-07): the breadcrumb names the lit group, so the move is relative
    names = group_names(cycle, groups, model, tab)
    lit = lambda: lit_text(cam.frame.image, cam.frame.path)       # the breadcrumb says only the tab here
    # the lit bar judged as from_groups judges it (group_near, by default): whole, by its letters and digits, so an icon
    # glyph read otherwise than the scan read it ("0Cnct./Remote Sht.", "(Cnct./Remote Sht.") names the same group
    at = lit_group(cam, names, lit)
    if at is None:
        # never a guess before a Down or a Right (2026-11-14: "taking it as the first" moved from a group nobody read)
        print(f"the lit group could not be read in {said(cam, lit())}, nor on a second look or the camera's own picture: "
              "nothing more is pressed, and the row is not reached", flush=True)
        return None
    d = group - at
    for _ in range(abs(d)):
        cam.press("down" if d > 0 else "up")
    if d and lit_group(cam, names, lit) != group:
        # the group reached must be read as the one meant: one that cannot be read gets no Right either
        print(f"the group column did not reach group {group + 1} of {tab!r}, or its lit group could not be read: "
              f"{said(cam, lit())}", flush=True)
        return None
    refused = group_closed(cam, lit(), known_groups(model))
    if refused:
        private = getattr(cam, "network", None) or getattr(cam, "owner", None)
        refused = safety.quoted_withheld(refused) if private else refused
        print(f"the lit group reads as one never entered from the group column ({refused}): no Right", flush=True)
        return None
    screen_now = cam.read()
    if screen_now.kind != "menu" or screen_now.focus != "groups":
        # as from_groups: the Right goes out only on a screen still read as the group column
        print(f"the screen no longer reads as the group column ({screen_now.kind}, focus {screen_now.focus}): no Right",
              flush=True)
        return None
    cam.press("right")
    j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
    if j is None:
        print(f"the group's rows are not a screen the scan recorded ({cam.read().kind})", flush=True)
    elif groups.get(cycle[j]["page"]) != (tab, group):
        print(f"landed in {groups.get(cycle[j]['page'])}, not {(tab, group)}: walking from there", flush=True)
    return j


WITHHELD_LABEL = "(withheld)"


def kept_row(row: dict, labels) -> dict:
    """What a --network walk prints and keeps in rows.jsonl of one row's summary (summary): its label only where it is a
    row label the kit knows (`labels`: runner.known_labels and the decisions' own rows, compared plain), or, for a row a
    network decision opened, the decided row it was opened as ("decided": "LANIP Address Setting" is kept as IP Address
    Setting); else WITHHELD_LABEL, since a page model's or a live page's reading can carry a value glued on ("Wi-Fi
    ConnectOn", a device's name). Its outcome and note keep no quoted text (safety.quoted_withheld); the rows of a
    submenu or a panel inside it alike. The counts, kinds, frames' names and the notice (safety.notice_kept) are kept."""
    known = {safety.plain(x) for x in labels or () if isinstance(x, str) and safety.plain(x)}
    out = dict(row)
    label = str(row.get("label") or "")
    out["label"] = (label if not label or safety.plain(label) in known
                    else row["decided"] if row.get("decided") else WITHHELD_LABEL)
    for k in ("outcome", "note"):
        if isinstance(out.get(k), str):
            out[k] = safety.quoted_withheld(out[k])
    if isinstance(out.get("submenu"), list):
        out["submenu"] = [kept_row(x, labels) for x in out["submenu"]]
    if isinstance(out.get("details"), dict):
        out["details"] = {k: ({**v, "rows": [kept_row(x, labels) for x in v["rows"]]}
                              if isinstance(v, dict) and isinstance(v.get("rows"), list) else v)
                          for k, v in out["details"].items()}
    return out


def show(row: dict, depth: int = 0):
    print(f"  {'    ' * depth}{row['page'][-16:]:>16s} {row['slot']} {row['label'][:30]:30s} {row['outcome'][:38]:38s} "
          f"{row['kind']:9s} {row.get('options', '')} ({row['presses']} presses)", flush=True)
    for k, v in (row.get("details") or {}).items():
        brief = {x: y for x, y in v.items() if x not in ("rows", "frames")}
        print(f"  {'    ' * depth}{'':16s}   option {k}: {brief}", flush=True)
        for sub in v.get("rows", []):
            show(sub, depth + 2)
    for sub in row.get("submenu", []):
        show(sub, depth + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="stop after opening this many rows")
    ap.add_argument("--start-label", default=None, help="step to this top-level row first (the short way round)")
    add_scan_argument(ap)
    ap.add_argument("--run", default="kit2_crawl",
                    help="run folder in the camera's runs/<model>_fw<fw>/ (evidence numbering continues in it)")
    ap.add_argument("--tabs", default=None, help="comma-separated menu tabs to crawl (default: all but Playback "
                                                "and My Menu), e.g. Playback")
    ap.add_argument("--panels", action="store_true",
                    help="open carousel › panels (commits the option); the start file is uploaded afterwards")
    add_network_argument(ap)
    a = ap.parse_args()
    cycle, model = load_scan(a.scan)      # signatures from the current reader, not the one at scan time
    run = Run(a.run)
    if a.network:
        run.make_private()                # owner-only from here (camkit.runs), checked at the end (seal)
    network = network_settings_or_exit(run) if a.network else {}
    check_readers()     # no reader listed: stop before the link opens, nothing pressed
    hdmi = eyes_from_config(run)
    results = open(run.dir / "rows.jsonl", "a", encoding="utf-8", newline="\n")  # noqa: SIM115 (closed in the finally below)
    ending, refused, complete = None, False, False
    try:
        with Link(run) as link:
            hdmi.attach(link)
            if screen.read(hdmi.grab(save=False)).kind in ("menu", "tiles"):
                link.press("menu", cleanup=True)           # a plain menu page: close it ourselves
                time.sleep(1.0)
            wait_for(hdmi, ("shooting",), "the first settings download", link=link)
            before = link.download("before")
            print(f"settings saved: {before.name}", flush=True)
            time.sleep(5)                                  # MENU within ~3 s of a download locks the menu
            # no options: inside a network row the camera lets nothing be chosen (camkit.live, safety.look_refused)
            cam = LiveCamera(link, hdmi, run, network=network, values=network_values(network, model),
                             readings=network_readings(network, model),
                             labels=label_readings(model) if network else None)
            try:
                complete = crawl_from_menu(cam, link, cycle, model, a.limit, results, a.start_label, a.panels,
                                           tuple(a.tabs.split(",")) if a.tabs else None, network=network)
            except StopRequested:                           # a STOP: cancelled as ever, and no failure
                print("STOP file: cancelling", flush=True)
                complete = True
                close_for_restore(cam, link)
            except Exception as e:                          # never leave a dialog or the menu open
                # a refusal that stops the lap (after a press on its row, or on the way to a row): the run's work is
                # not done, whatever the restore says (EXIT_REFUSED below)
                refused = isinstance(e, safety.Refused)
                said_e = f"{type(e).__name__}: {e}"
                print(f"error: {safety.quoted_withheld(said_e) if network else said_e}; cancelling", flush=True)
                close_for_restore(cam, link)            # cleanup presses; when they fail too, the restore all the same
            # every run ends restoring its start file (decision 15), not only a --panels run, and even when the
            # shooting screen does not come back
            # a --network run says the records that differ by their keys alone (runner.values_withheld)
            ending = end_session(link, hdmi, before, "the final settings download", reach=wait_shooting,
                                 **values_withheld(bool(network)))
        restored = restore_checked(run, ending, before, **values_withheld(bool(network)))
    finally:
        hdmi.close()
        results.close()
        run.seal()                            # a --network run's folder checked owner-only
    if not restored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)
    if refused:
        print("the lap was stopped by a refusal: its start file is back and checked, but the rows after it were not "
              f"crawled (exit status {EXIT_REFUSED})", flush=True)
        sys.exit(EXIT_REFUSED)               # a chain stops there (kit/exit_status.py)
    if not complete:
        print("the lap stopped short: its start file is back and checked, but the rows after where it stopped were not "
              f"crawled (exit status {EXIT_INCOMPLETE})", flush=True)
        sys.exit(EXIT_INCOMPLETE)            # a chain stops there too


def network_settings_or_exit(run) -> dict:
    """--network for the walk: the Wi-Fi and Bluetooth settings a dated owner decision names ({row: date},
    runner.network_decided_or_exit, logged in the run), without the address screens, which only kit/drive.py opens;
    a stop before anything connects when the decision names only those."""
    rows, _, _ = network_decided_or_exit(run)       # the walk chooses nothing, whatever options a decision names
    settings = {r: d for r, d in rows.items() if not safety.address_screen(r)}
    if not settings:
        sys.exit("--network: the decision names only address screens, which the walk never opens (kit/drive.py does): "
                 "nothing was sent to the camera")
    return settings


def crawl_from_menu(cam, link, cycle, model, limit, results, start_label=None, panels=False, tabs=None,
                    network=frozenset()) -> bool:
    """MENU, find where it opened in the scan's cycle (find_position, kit/drive.py's way: a menu reopened with the
    cursor in the group column, where a refused jump left it, is stepped into the rows of a group it may enter
    (from_groups); one opened on a page the scan does not match goes by the columns to the Shooting tab's first group),
    crawl from there, close the menu. network: the Wi-Fi and Bluetooth settings a dated owner decision opens
    (camkit.crawl.network_open). True when the lap ended as it should (complete, --limit reached, or a STOP); False when
    the menu opened on a screen the scan does not know and none of those ways reached one it does, the start label was
    not reached, or the crawl stopped short (off the scan, lost, an error)."""
    cam.press("menu")
    j = find_position(cam, cycle, model)
    complete, reached = False, True
    if j is not None and start_label:
        j = go_to(cam, cycle, model, j, start_label)
        reached = j is not None
    if not reached:
        print(f"the start label {start_label!r} could not be reached by the scan; stopping", flush=True)
    elif j is None:
        print(f"the menu is on a screen the scan does not know ({cam.read().kind}); stopping", flush=True)
    else:
        print(f"at scan position {j}; crawling", flush=True)

        # a --network walk keeps no text read off the screen: its labels as the kit knows them (kept_row)
        keep = (known_labels(model) | set(network)) if network else None

        def on_row(r):
            row = summary(r) if keep is None else kept_row(summary(r), keep)
            results.write(json.dumps(row) + "\n")
            results.flush()
            show(row)
        try:
            # a Wi-Fi or Bluetooth setting that answers Right with a notice keeps the notice's text where it is one the
            # kit knows and names no identity (camkit.crawl, safety.notice_kept)
            out = crawl(cam, cycle[j:] + cycle[:j], model, max_rows=limit, on_row=on_row, labels=submenu_labels,
                        **({"tabs": tabs} if tabs else {}),
                        panels=panels, network=network,
                        notices=(text_of, known_labels(model), row_values(model)) if network else None)
            print(f"crawl ended: {(safety.quoted_withheld(out.stopped) if network else out.stopped) or 'lap complete'}; "
                  f"{out.presses} presses, "
                  f"{len(out.rows)} rows; the menu closed by itself {len(out.recoveries)} times "
                  f"(reopened with MENU)", flush=True)
            complete = not out.stopped or out.stopped.startswith(LAP_ENDS)
        except StopRequested:
            print("STOP file: cancelling to the menu", flush=True)
            cam.cancel_to_menu()
            complete = True
    if cam.read().kind in ("menu", "tiles"):
        link.press("menu", cleanup=True)
    return complete


# camkit.crawl's stops that end a lap as asked: --limit reached, a STOP; any other stop (off the scan, lost, an error)
# leaves the lap short (EXIT_INCOMPLETE)
LAP_ENDS = ("row limit", "stop requested")


if __name__ == "__main__":
    main()
