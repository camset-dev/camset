"""Pass 1 on the camera: open every safe top-level row, walk its screen by type, back out with MENU.

    .venv/bin/python -u kit/crawl_run.py [--limit N] [--scan kit2_page_scan]

Uses the page scan's Down cycle and confirmed page model (camkit.crawl): before acting at any
position the screen must match what the scan recorded there. Presses: MENU, the arrows, never
Enter, but the OK of an information notice that --info-ok names for its row. Rows on the never-open list are skipped
by their confirmed label.

--info-ok "ROW=PHRASE" (repeatable, one row each: runner.info_ok_or_exit, which refuses a row that is no label the
definition or the page model knows or is never-open, and a phrase of fewer than 3 words or 12 letters, with a question
mark or a pattern's sign such as * [ ] |) takes, after Right on ROW, the OK of the information notice whose whole text is
PHRASE, once, and walks the screen behind it where it is one the walkers know (the a1 II's Different Set for Still/Mv: a
notice, then its checklist). PHRASE is compared by its letters, digits and single spaces alone, punctuation and glyphs
ignored in it and in the notice (runner.notice_words). The OK goes out only on a notice that explains and asks nothing
(proving.screens.pass_named_notice): the lit bar before Right read as ROW; the phrase's words found in the notice in
order (a negation such as "isn't" one word; a letter or two glued on only to a line's first or last word, where an icon
sits), and at most 10 of the notice's letters and digits left over (an icon read as a letter or two, a slip), never a
word of three letters or more nor a line outside its text, its OK line and a line saying "Don't show this again." and
nothing else aside; no question mark; no confirmation (its words run together inside one word too), nothing
never-open, of identity or credentials; exactly one line a button's word alone, OK; no other line naming a second
button, a choice or an action, nor on or below the OK's band; and the lit button reading OK. Else nothing is pressed and
the row is recorded "notice (named, not passed: ...)"; where the phrase leaves more of the notice over, the notice's text
is printed, to give it whole. rows.jsonl keeps "info_ok": {"row", "frame"} for a row passed. Not with --network, whose
rows are looked at only.

Settings are downloaded before and after and diffed (pass 1 must change nothing); if anything changed, the
start file is uploaded and the restore checked (docs/decisions/0015). --limit stops
after opening N rows (for supervised tries). A STOP file (<run>/STOP) cancels any open
dialog with MENU and stops. It never disconnects with a menu open.

--network makes the lap a look lap (docs/decisions/0024): every never-open row opens too, no decision naming it, but
what safety.look_lap_refused refuses (OWNER_NEVER's rows and the Screen Reader, a row whose opening acts, and a format,
delete or reset this body's records have not shown opened, skipped with nothing pressed), and so do the Wi-Fi and
Bluetooth settings and identity rows a dated owner decision in the reviewed scope names ({"lifts": "network", ...}:
runner.network_decided_or_exit, docs/decisions/0008), looked at only: Down round the row's list or carousel, never a
second axis, a panel or a submenu (--panels is refused with --network), and nothing chosen whatever options a decision
names; a decided row never as an address screen, nor where the page model stored another reason for it (a model built
before the class existed says "by hand only": build it again with kit/page_model.py). A row whose frames the camera
blanks (what the owner route blanks: safety.look_blank), an address screen and a screen naming identity are left with
MENU alone, unwalked. The run
asks local readers only (camkit.vlm.LOCAL_ONLY), marks its folder so (camkit.vlm.LOCAL_MARKER: the tools that read its
frames later ask local readers only too), and writes each such row's class in rows.jsonl ("network"); for a Wi-Fi or
Bluetooth setting (never an identity row) that answers Right with a notice the kit knows ("This function is currently
disabled.", "... not available as follows ...") naming no identity or credentials, the notice's text too ("notice":
safety.notice_kept), so why the row is greyed is recorded. From its start to its end such a run prints and keeps no text
read off the screen: a row's own label only where the camera's definition names that row (runner.row_labels, a label
that is also a value the kit knows among them: a row's place in the menu is no value), where it is a row label the kit
knows (runner.known_labels), a decision's own row or the decided row a lifted row was opened as (row_names), else
"(withheld)", and the quoted texts of an outcome, a note or an error withheld (kept_row); a notice's text is judged by
runner.known_labels alone, which holds no label that is also a value. Its folder is owner-only (camkit.runs: folders
0700, files 0600, on POSIX), checked at the end.

A row whose opening the camera refuses because of the lit row itself (safety.RowRefused: the lit row read as one the
run may not open, or read by no reader) before any press went out on it is skipped, "skipped: refused (...)" with the
reason's quoted texts withheld, and the lap goes on (camkit.crawl.visit_row); any other refusal, and a refusal after a
press on the row, cancels the lap. Once its start file is back and checked, a run a refusal stopped exits EXIT_REFUSED
(7), and one stopped short by anything else (an error, a screen the scan does not know, the start label not reached,
the crawl lost or off the scan) EXIT_INCOMPLETE (8); a STOP, the lap complete or --limit reached exit 0; a restore that
did not check out exits EXIT_UNRESTORED (4) (kit/exit_status.py; kit/tools/chain.py stops on each).

A row this camera has not been seen to open (camkit.first_open) opens under the link-loss procedure: RESTORE_BY_HAND
before its Right, and after its top-level row's visit MENU, a download compared with the start file and MENU again; the
marker goes only when no record differs, else the run exits EXIT_RESTORE_BY_HAND (5) saying what the owner does.
Where that MENU opens the menu on another plain page the scan knows (a Playback row's view left), the lap goes back to
its row once, as the start goes to --start-label's (back_to_row; no long walk past a group the column never enters),
and stops short (EXIT_INCOMPLETE) where it is then not on that row or the screen is any other.
Without the owner's blank-cards statement (camkit.statements), or with --panels, each such row is skipped and recorded
(camkit.first_open.SKIPPED), as is a row whose first open failed, and the lap goes on. --first-open-check page checks
once per menu page. A camera other than the one the kit works on stops the run before anything is pressed.

Navigation guesses nothing: the lit group in the group column is read whole, by its letters and digits, whatever icon
glyph the bar or the scan glued on, and with the group's own number where the bar is read with it (group_near); where
it cannot be read, it is read again once after a short settle, then on the camera's own picture of its screen (the
SDK's OSD image); if none names it, nothing more is pressed and the row is not reached (jump, from_groups: lit_group).
The menu found reopened with the cursor in the group column is stepped into a group it may enter before the lap begins
(find_position, as kit/drive.py finds it).

Results: kit2_crawl/rows.jsonl (one line per row), frames and presses in shots/ and events.jsonl. Every run folder
named here is in the camera's runs/<model>_fw<fw>/ (camkit.paths).
"""
import argparse
import contextlib
import functools
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import match, ocr, safety, screen  # noqa: E402
from camkit import coverage, first_open  # noqa: E402
from camkit.screen import same_position  # noqa: E402
from camkit.crawl import LAP_TABS, crawl, lap_rows  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link, StopRequested  # noqa: E402
from camkit.live import lit_text, LiveCamera, PageLabels, reader_label, text_of  # noqa: E402
from camkit.vlm import check_readers  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.session import wait_for  # noqa: E402
from proving.base import LOCK_S, wait_lock  # noqa: E402
from runner import (EXIT_INCOMPLETE, EXIT_REFUSED, EXIT_RESTORE_BY_HAND, EXIT_UNRESTORED, LOOK_LAP,  # noqa: E402
                    add_network_argument, add_scan_argument, cards_statement_refused, close_for_restore, end_session,
                    known_groups,
                    known_labels, label_readings, load_scan, network_decided_or_exit, network_readings, network_values,
                    restore_checked, row_readings, row_values, values_withheld, wait_shooting)
from runner import add_info_ok_argument, definition, info_ok_for, info_ok_or_exit, row_labels  # noqa: E402


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
        out["notice"] = r.notice                            # why the row is greyed: notice_kept, notice_named
    if getattr(r, "info_ok", None):
        out["info_ok"] = r.info_ok                          # the notice --info-ok named, taken with its OK (its frame)
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


def target_of(cycle, model, label, place=None) -> tuple:
    """(position, by another reading, why): the cycle position of the row labelled `label` that go_to steps to, whether
    it was found by another reading of the row (row_named, or a page model label that only page_model.same_text takes
    for it: go_to then reads the lit bar after travel), and, where there is none, why (position None). place: go_to's.
    Of the rows same_text finds, one whose page model label is `label` itself (safety.plain) is taken first ("Tv
    Auto/Manual Switch" is never its Av twin, which same_text also takes for it); where none is and they bear two labels,
    none is gone to (review 2026-11-18, B5)."""
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
        return None, fallback, (f"no row labelled {label!r} in the page model, and {len(real or matches)} rows read as "
                                "it: none is gone to")
    pool = real or matches
    if not fallback and pool:
        def named(i):
            return model[cycle[i]["page"]]["rows"][cycle[i]["row"]]["label"]
        exact = [i for i in pool if safety.plain(named(i)) == safety.plain(label)]
        if exact:
            pool = exact
        else:
            labels = sorted({named(i) for i in pool})
            if len({safety.plain(x) for x in labels}) > 1:
                return None, True, (f"no row labelled {label!r} in the page model, and {len(labels)} rows with other "
                                    f"labels read as it ({', '.join(repr(x) for x in labels[:4])}): none is gone to")
            fallback = True              # a reading of the row only: its lit bar is read after travel (go_to)
    target = (pool or [None])[0]
    return target, fallback, "" if target is not None else f"no row labelled {label!r} in the page model"


def go_to(cam, cycle, model, j, label, place=None):
    """Step from cycle position j to the row labelled `label` (target_of), the short way round, checking every
    screen against the scan. Returns the new position, or None if a screen was not the expected one. place: (tab,
    group) the row must be in (kit/drive.py --owner: the owner decision's), its page's breadcrumb read so in the scan;
    none there, None. A row found by another reading (target_of's fallback) is reached only where its lit bar, as OCR
    reads it there, is the row (safety.bar_on_row), or, where it is not, where the vision reader, asked once about that
    very frame what the lit row's label is (camkit.live.reader_label: the "second" reader through camkit.vlm.ask_role,
    so a --network or --owner run asks a local reader only and a run with no reader asks none), reads it as `label`
    exactly once plain (safety.plain: nothing before it, nothing after it; the owner, 2026-11-06: the reader is right
    where OCR garbles short text or an icon, the a1 II's S&Q Settings in S&Q mode, 2026-11-16). That question is logged
    in the run's events.jsonl ("bar_by_reader": the frame, the row, the reader's label, withheld where said withholds,
    whether it took the row, and why the reader gave none); any other answer, none or a failure refuses as before, what
    the reader read said after the refusal, and on a --network or --owner run nothing read off the screen is printed."""
    target, fallback, why = target_of(cycle, model, label, place)
    if target is None:
        print(why, flush=True)
        return None
    j = travel(cam, cycle, model, j, target, label)
    if j is None:
        return None
    if fallback:
        # a row found by another reading: its lit bar, read now, must be the row (safety.bar_on_row: its label, or the
        # reading with its page's icon glued on where another reader read the row exactly, or that icon as the live bar
        # shows it, a letter misread, glued on or set apart, forming no other label the kit knows), else the reader's
        # reading of that frame's lit row, the row exactly, else nothing more
        row = model[cycle[j]["page"]]["rows"][cycle[j]["row"]]
        entry = {"group": page_group(model[cycle[j]["page"]]), "readings": [row.get("label") or "", *row_readings(row)]}
        frame = cam.frame
        lit = lit_text(frame.image, frame.path)
        known = label_readings(model)
        if not safety.bar_on_row(lit, label, {label: [entry]}, known) and not bar_reads_row(lit, label, entry, known):
            answer, why_not = reader_label(frame.path)
            taken = bool(safety.plain(label)) and (safety.plain(answer) == safety.plain(label)
                                                   or bar_reads_row(answer, label, entry, known))
            if getattr(cam, "run", None) is not None:
                withheld = said(cam, answer) == TEXT_WITHHELD and answer
                cam.run.log("bar_by_reader", frame=Path(frame.path).name, row=label,
                            label=WITHHELD_LABEL if withheld else answer, taken=taken, reader=why_not)
            if not taken:
                print(f"the row the page model reads as {label!r} is lit, but its bar does not read it: "
                      f"{said(cam, lit)}{f'; the reader read it as {said(cam, answer)}' if answer else ''}", flush=True)
                return None
            print(f"the lit bar read by the reader as {said(cam, answer)}", flush=True)
    return j


def bar_reads_row(text, label: str, entry: dict, labels) -> bool:
    """Whether `text`, a lit bar as OCR read it or the reader's label of it, is on the row `label` once the icon read in
    front of it as a stray mark or a letter or two is left out, by the kit's rule for such an icon (camkit.match.ICON,
    which function_name leaves out too): "MR Memory/Recall Media Slot 1" and the reader's "MR Memory/Recall Media" are
    Memory/Recall Media, "S 5 after still img crt Maintain" is after still img crt (the a1 II's page scans, 2026-11-19).
    What is left must start with the label, its value maybe after (safety.bar_on_row); and neither the text as read nor
    what is left may start with another row the kit knows (`labels`, runner.label_readings; `entry`'s readings of the
    row itself aside), what is left not with a longer one: a bar that names another row stays refused."""
    text = str(text or "").strip()
    cut = match.ICON.sub("", text).strip()
    if not cut or cut == text or not safety.bar_on_row(cut, label):
        return False
    own = {safety.plain(t) for t in [label, *(entry.get("readings") or [])]}
    want = len(safety.plain(label))
    for other in labels or ():
        p = safety.plain(other)
        if p and p not in own and (safety.bar_on_row(text, other) or (len(p) > want and safety.bar_on_row(cut, other))):
            return False
    return True


def travel(cam, cycle, model, j, target, label, walk_closed: bool = True):
    """From cycle position j to the position `target`, the short way round (go_to's way, and back_to_row's): by the tab
    and group columns (jump) where it is more than JUMP_MIN rows away in another group, unless that group is one the
    column never enters (group_closed: then the rows are walked to, or, walk_closed False, nothing is pressed), then Down
    or Up to it, every screen checked against the scan. Returns `target`, or None where a screen was not the expected
    one or the jump went no further. label: the row's name as printed."""
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
        if refused and not walk_closed:
            print(f"no jump to {label!r}: its group {group_name!r} is never entered from the group column ({refused}); "
                  "nothing is pressed", flush=True)
            return None
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
    return j


def back_to_row(cam, pos, cycle, model, name=None):
    """camkit.crawl's refind: after a first open's check (camkit.first_open.FirstOpens.settle) that left the menu open on
    another page than the lap's position `pos` (one of `cycle`'s), the lap's own way there, once: travel, as the lap's
    start goes to --start-label's row (the tab and group columns where it is far, then Down or Up, every screen checked
    against the scan; no key on a row but those arrows), but where the jump is refused (a group the column never enters)
    nothing is pressed rather than the rows walked. Only from a plain menu page the scan knows: the menu shown, its
    focus on the rows, a menu position of the scan's cycle; any other screen (the shooting screen, the playback view,
    the cursor in a column, a page the scan does not know) presses nothing. Returns the position reached, or None; the
    crawl then checks the row as before and stops where it is not there. name(label): what is printed of the row's
    label (a withholding run's kept_label); None prints the page model's reading."""
    target = next((i for i, p in enumerate(cycle) if p is pos), None)
    s = cam.read()
    j = (next((i for i, p in enumerate(cycle) if same_position(s, p["screen"])), None)
         if s.kind == "menu" and s.focus == "rows" else None)
    if target is None or j is None or cycle[j].get("kind") != "menu":
        print(f"after a first open's check the menu is on no page of rows the scan knows ({s.kind}, focus {s.focus}): "
              "nothing is pressed to go back", flush=True)
        return None
    if j == target:
        return j                    # the scan's own position: nothing to go to (the crawl's check decides)
    rows = (model.get(pos.get("page")) or {}).get("rows") or []
    label = str((rows[pos["row"]] if pos.get("row") is not None and pos["row"] < len(rows) else {}).get("label") or "")
    print(f"after a first open's check the menu is on another page the scan knows (position {j}): back to the lap's "
          f"row (position {target}) the lap's own way", flush=True)
    return travel(cam, cycle, model, j, target, name(label) if name else label, walk_closed=False)


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
    if getattr(cam, "network", None) or getattr(cam, "owner", None) or getattr(cam, "look", False):
        return TEXT_WITHHELD
    return repr(str(text or "")[:60])


def group_near(text: str, names: list) -> int | None:
    """Which of a tab's groups a lit group's text names, judged whole: its letters and digits (safety.name_key), as read
    or with a glued icon glyph left off (unglued), the very group's name, or, for one of at least safety.GROUP_MIN, one
    letter from it (safety.one_apart: the scan read "FTP Transter" where the camera draws "FTP Transfer"). A text read
    with a number before or after it, set apart by a space (safety.group_number: the badge the column draws, read into
    the bar on the camera's own picture, "10 Shooting Display", 2026-11-15), names the group of that number (the
    column's i-th group, numbered i + 1) where the rest names it so and is not another group's very name ("2 Drive Mode"
    names no "Drive Made" beside a "Drive Mode"); a group of another number only where the whole text, number and all,
    is its very name: a number is never taken for a letter put in. None when no group, or more than one, is so named: a
    lit row's text ("File Format  RAW") names no group ("File"), so a focus read as the group column on a page of rows
    sends no Right onto that row."""
    number, rest = safety.group_number(text)

    def keys(t) -> set:
        return {k for k in (safety.name_key(t), safety.name_key(unglued(t))) if k}

    def near(found, name, slips=True) -> bool:
        key = safety.name_key(name)
        return any(k == key or (slips and len(k) >= safety.GROUP_MIN and safety.one_apart(k, key)) for k in found)
    whole, own = keys(text), keys(rest)

    def other(n) -> bool:
        # the rest is another group's very name: the number names none (a group named twice is told apart by it)
        return any(m and safety.name_key(m) != safety.name_key(n) and near(own, m, slips=False) for m in names)
    got = [i for i, n in enumerate(names) if n and (
        (number == i + 1 and near(own, n) and not other(n)) or near(whole, n, slips=number is None))]
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
        private = getattr(cam, "network", None) or getattr(cam, "owner", None) or getattr(cam, "look", False)
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


def row_names(model, network=()) -> set:
    """The names a look lap or a --network walk keeps a row's own name by (kept_label: rows.jsonl, the printed table, and
    what camkit.first_open writes of a row): every row label of the camera's definition (runner.row_labels: its menu and
    each setting's row path), one that is also a value the kit knows among them, since a row's place in the menu is no
    value (the page model says it is a row: Drive Mode, ISO and Focus Magnifier are a Custom Key's functions too on the
    a1 II); the row labels the kit knows (runner.known_labels); and the network decision's rows (`network`). Only a
    row's own name: what of a screen's text is kept (a notice's blocker, camkit.live's labels) stays judged by
    runner.known_labels, which holds no label that is also a value (docs/decisions/0016)."""
    return row_labels(definition()) | known_labels(model) | set(network)


def kept_label(label, known) -> str:
    """A row's label as a look lap or a --network walk writes it anywhere (rows.jsonl, events.jsonl, the looks file,
    RESTORE_BY_HAND, the console): the label where it is one the run keeps a row's name by (`known`: row_names, compared
    plain: a label read with a value glued on, "Edit Device Name ILCE-...", is none), else WITHHELD_LABEL, which
    camkit.first_open never counts as seen."""
    label = str(label or "")
    return label if not label or safety.plain(label) in known else WITHHELD_LABEL


def kept_row(row: dict, labels) -> dict:
    """What a --network walk prints and keeps in rows.jsonl of one row's summary (summary): its label only where it is
    one the run keeps a row's name by (`labels`: row_names, compared plain), or, for a row a network decision opened, the
    decided row it was opened as ("decided": "LANIP Address Setting" is kept as IP Address Setting); else WITHHELD_LABEL,
    since a page model's or a live page's reading can carry a value glued on ("Wi-Fi ConnectOn", a device's name). Its
    outcome and note keep no quoted text (safety.quoted_withheld); the rows of a submenu or a panel inside it alike. The
    counts, kinds, frames' names and the notice (safety.notice_kept) are kept; no option's name, nor which is lit."""
    known = {safety.plain(x) for x in labels or () if isinstance(x, str) and safety.plain(x)}
    out = dict(row)
    kept = kept_label(row.get("label"), known)
    out["label"] = row["decided"] if kept == WITHHELD_LABEL and row.get("decided") else kept
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
    ap.add_argument("--first-open-check", choices=("row", "page"), default="row",
                    help="check the rows this body has not been seen to open (camkit.first_open) after each top-level "
                         "row (the default), or once per menu page: a difference then stops the lap and every row of "
                         "that page is opened alone next time")
    add_network_argument(ap)
    add_info_ok_argument(ap)
    coverage.add_skip_argument(ap, crawl=True)
    a = ap.parse_args()
    if a.info_ok and a.network:
        sys.exit("--info-ok passes no notice on a --network run: its rows are looked at only")
    if a.panels and a.network:
        # a panel's Right commits its carousel's option, and a look lap commits nothing (2026-11-15, the maintainer)
        sys.exit("--panels opens no panel on a --network run, a look lap, which commits nothing: nothing was sent to the "
                 "camera")
    cycle, model = load_scan(a.scan)      # signatures from the current reader, not the one at scan time
    # before anything connects; a row is named by a label the definition or the page model knows
    named = info_ok_or_exit(a.info_ok, labels=known_labels(model) | row_labels(definition())) if a.info_ok else {}
    run = Run(a.run)
    if a.network:
        run.make_private()                # owner-only from here (camkit.runs), checked at the end (seal)
    network = network_settings_or_exit(run) if a.network else {}
    look = bool(a.network)                  # a look lap (docs/decisions/0024): no decision needed to look
    if look:
        print(LOOK_LAP, flush=True)
    # the rows this camera has not been seen to open: each opens the first time under the link-loss procedure
    # (camkit.first_open), only with the owner's blank-cards statement (camkit.statements) and never with --panels;
    # else each is skipped and recorded, and the lap goes on
    seen = first_open.seen_record(run.root.name)
    try:
        skip_why = cards_statement_refused("crawl_run.py")
    except SystemExit as e:
        skip_why = str(e.code)      # a scope that cannot be read makes no first open, and stops no lap
    if a.panels and not skip_why:
        skip_why = "--panels commits options, while a first open is a look: crawl without --panels first"
    said = unseen_line(cycle, model, seen, skip_why, a, network)
    if said:
        print(said, flush=True)
    check_readers()     # no reader listed: stop before the link opens, nothing pressed
    hdmi = eyes_from_config(run)
    results = open(run.dir / "rows.jsonl", "a", encoding="utf-8", newline="\n")  # noqa: SIM115 (closed in the finally below)
    ending, refused, complete, first = None, False, False, None
    try:
        with Link(run) as link:
            why = first_open.other_body(link, run.root.name)
            if why:
                sys.exit(f"{why}: nothing was sent to the camera")
            hdmi.attach(link)
            if screen.read(hdmi.grab(save=False)).kind in ("menu", "tiles"):
                link.press("menu", cleanup=True)           # a plain menu page: close it ourselves
                time.sleep(1.0)
            wait_for(hdmi, ("shooting",), "the first settings download", link=link)
            before = link.download("before")
            downloaded = time.monotonic()
            print(f"settings saved: {before.name}", flush=True)
            ledger = coverage.crawl_gate(run, a, before)    # the ledger's word on each row; --skip-settled skips
            # a look lap writes a row's name as rows.jsonl keeps it, the name it keeps or its placeholder (kept_label,
            # row_names: the definition's rows among them, a value or not)
            names = {safety.plain(x) for x in row_names(model, network)} if look else None
            first = first_open.FirstOpens(link, hdmi, run, before, seen, skip_why, LOCK_S, private=look,
                                          per=a.first_open_check,
                                          name=functools.partial(kept_label, known=names) if look else None)
            wait_lock(downloaded, hdmi, clock=time)     # the menu's lock after the download (camkit.session.wait_lock)
            # no options: inside a network row the camera lets nothing be chosen (camkit.live, safety.look_refused). The
            # row labels and the values the kit knows go to every run: an opening check judges the row, never a value
            # shown beside it (safety.row_judged); a look lap's camera knows the labels this body was seen to open
            cam = LiveCamera(link, hdmi, run, network=network,
                             values={**row_values(model), **network_values(network, model)},
                             readings=network_readings(network, model), labels=label_readings(model), look=look)
            try:
                complete = crawl_from_menu(cam, link, cycle, model, a.limit, results, a.start_label, a.panels,
                                           tuple(a.tabs.split(",")) if a.tabs else None, network=network,
                                           info_ok=info_ok_pass(named), ledger=ledger, first=first, look=look)
            except StopRequested:                           # a STOP: cancelled as ever, and no failure
                print("STOP file: cancelling", flush=True)
                complete = True
                close_for_restore(cam, link, before)
            except Exception as e:                          # never leave a dialog or the menu open
                said_e = f"{type(e).__name__}: {e}"
                print(f"error: {safety.quoted_withheld(said_e) if look else said_e}; cancelling", flush=True)
                if first.marker is not None and link.gone():
                    # a first open is pending or failed its check and the link has gone: nothing more is pressed or
                    # restored over the link; the start file goes back by hand (camkit.first_open)
                    first.lost(f"the link has gone ({link.gone()})")
                    sys.exit(EXIT_RESTORE_BY_HAND)
                # a refusal that stops the lap (after a press on its row, or on the way to a row): the run's work is
                # not done, whatever the restore says (EXIT_REFUSED below)
                refused = isinstance(e, safety.Refused)
                close_for_restore(cam, link, before)            # cleanup presses; when they fail too, the restore all the same
            # every run ends restoring its start file (decision 15), not only a --panels run, and even when the
            # shooting screen does not come back
            # a --network run says the records that differ by their keys alone (runner.values_withheld)
            ending = end_session(link, hdmi, before, "the final settings download", reach=wait_shooting,
                                 **values_withheld(look))
            ledger.lap(ending)                              # the lap's diff, by record keys, into the looks file
        # while a first open's marker is there, the check reconnects as kit/tools/upload_check.py does
        held = first is not None and first.marker is not None
        checking = {"link_class": functools.partial(Link, pending_restore=True)} if held else {}
        restored = restore_checked(run, ending, before, **values_withheld(look), **checking)
    finally:
        hdmi.close()
        results.close()
        run.seal()                            # a --network run's folder checked owner-only
    if first is not None and first.ended(restored, ending):
        sys.exit(EXIT_RESTORE_BY_HAND)       # a first open's check did not come out clean: the marker stays
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


def unseen_line(cycle, model, seen, skip_why: str, a, network=frozenset()) -> str:
    """The line said before the link opens of the top-level rows this body has not been seen to open (camkit.first_open)
    that the lap reaches, "" when none: from --start-label's row (target_of) as far as --limit (camkit.crawl.lap_rows,
    a row a first open's rule skips counting toward no limit); where that is known only once the menu opens (a --limit
    with no --start-label found, or with --skip-settled, whose rows left out count toward none), the whole menu's."""
    tabs = tuple(a.tabs.split(",")) if a.tabs else LAP_TABS
    start = target_of(cycle, model, a.start_label)[0] if a.start_label else None
    # a start label not found: go_to says so, and the lap does not start
    known = not (a.start_label and start is None) and (
        a.limit is None or (start is not None and not getattr(a, "skip_settled", False)))
    look = {"look": bool(getattr(a, "network", False)), "seen": getattr(seen, "seen", None)}      # a look lap's rows too
    rows = lap_rows(cycle, model, tabs, network, start, a.limit, lambda x: not seen.skips([x], skip_why),
                    **look) if known else None
    fresh = [x for x in (rows if rows is not None else lap_rows(cycle, model, tabs, network, **look))
             if not seen.seen([x])]
    if not fresh:
        return ""
    where = ("of this lap" if rows is not None else
             "of the whole menu (which of them this lap reaches is known only once the menu opens)")
    return (f"{len(fresh)} rows {where} have not been seen opened on this body: "
            + (f"each {'is' if rows is not None else 'it reaches is'} skipped and recorded, since {skip_why}"
               if skip_why else
               f"each {'opens' if rows is not None else 'it reaches opens'} under the link-loss procedure, checked "
               f"once per {a.first_open_check}"))


def network_settings_or_exit(run) -> dict:
    """--network for the walk: the Wi-Fi and Bluetooth settings a dated owner decision names ({row: date},
    runner.network_decided_or_exit, logged in the run), without the address screens, which no decision opens for the
    walk; none at all for a look lap no decision names a row on (docs/decisions/0024)."""
    rows, _, _ = network_decided_or_exit(run, look=True)     # the walk chooses nothing, whatever a decision names
    return {r: d for r, d in rows.items() if not safety.address_screen(r)}


def info_ok_pass(named: dict):
    """camkit.crawl's info_ok for --info-ok (`named`: runner.info_ok_or_exit's {row: phrase}), or None when it names
    none: for a row named, the lit bar read on the frame before Right (camkit.live.lit_text) and the notice judged and
    passed by proving.screens.pass_named_notice ({"row", "frame"}, or {"refused": why} with nothing pressed); None for a
    row not named, which is left as ever."""
    if not named:
        return None

    def passed(cam, name, before):
        from proving.screens import pass_named_notice       # here: runner and camkit stay free of the prover's parts
        phrase = info_ok_for(named, name)
        if phrase is None:
            return None
        lit = lit_text(before.image, before.path) if before is not None else ""
        return pass_named_notice(cam, name, phrase, lit)
    return passed


def crawl_from_menu(cam, link, cycle, model, limit, results, start_label=None, panels=False, tabs=None,
                    network=frozenset(), info_ok=None, ledger=None, first=None, look: bool = False) -> bool:
    """MENU, find where it opened in the scan's cycle (find_position, kit/drive.py's way: a menu reopened with the
    cursor in the group column, where a refused jump left it, is stepped into the rows of a group it may enter
    (from_groups); one opened on a page the scan does not match goes by the columns to the Shooting tab's first group),
    crawl from there, close the menu. network: the Wi-Fi and Bluetooth settings a dated owner decision opens
    (camkit.crawl.network_open); look: a look lap (camkit.crawl's look, docs/decisions/0024), which keeps no text read
    off the screen. first: a row's first open on the body (camkit.first_open.FirstOpens). True when the
    lap ended as it should (complete, --limit reached, or a STOP); False when
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

        # a --network walk keeps no text read off the screen: a row's own name where the run keeps it (kept_row,
        # row_names); a notice's text below stays judged by runner.known_labels alone
        keep = row_names(model, network) if network or look else None

        def on_row(r):
            row = summary(r) if keep is None else kept_row(summary(r), keep)
            results.write(json.dumps(row) + "\n")
            results.flush()
            show(row)
            if ledger is not None:
                # one look per row opened (camkit.coverage), never a value; a first open's held until its check
                ledger.after(row, model, **({"hold": first.takes} if first is not None else {}))
        # after a first open's check that left the menu on another page the scan knows, the way back to the lap's row,
        # once (back_to_row), its label printed as the run keeps it
        shown = functools.partial(kept_label, known={safety.plain(x) for x in keep}) if keep is not None else None
        try:
            # a Wi-Fi or Bluetooth setting that answers Right with a notice keeps the notice's text where it is one the
            # kit knows and names no identity (camkit.crawl, safety.notice_kept); on a plain crawl every row's notice
            # keeps what it names, its blocker as a rule and nothing more (camkit.crawl.notice_named)
            out = crawl(cam, cycle[j:] + cycle[:j], model, max_rows=limit, on_row=on_row, labels=PageLabels(),
                        **({"tabs": tabs} if tabs else {}),
                        panels=panels, network=network,
                        notices=(text_of, known_labels(model), row_values(model)),
                        **({"info_ok": info_ok} if info_ok is not None else {}),
                        skip=ledger.skip if ledger is not None else None, first=first, look=look,
                        refind=functools.partial(back_to_row, cycle=cycle, model=model, name=shown))
            print(f"crawl ended: {(safety.quoted_withheld(out.stopped) if network or look else out.stopped) or 'lap complete'}; "
                  f"{out.presses} presses, "
                  f"{len(out.rows)} rows; the menu closed by itself {len(out.recoveries)} times "
                  f"(reopened with MENU)", flush=True)
            unseen = sum(unseen_skips(r) for r in out.rows)
            if unseen:
                print(f"{unseen} rows not seen opened on this body were skipped, each recorded in rows.jsonl: "
                      f"{first.skip_why if first is not None and first.skip_why else 'see their outcomes'}", flush=True)
            complete = not out.stopped or out.stopped.startswith(LAP_ENDS)
        except StopRequested:
            print("STOP file: cancelling to the menu", flush=True)
            cam.cancel_to_menu()
            complete = True
    if cam.read().kind in ("menu", "tiles"):
        link.press("menu", cleanup=True)
    return complete


def unseen_skips(r) -> int:
    """How many rows a first open's rule skipped (camkit.first_open.SKIPPED) in a crawl's row result, its submenu's
    rows included."""
    sub = getattr(r.walk, "rows", None) if type(r.walk).__name__ == "SubCrawl" else None
    return r.outcome.startswith(first_open.SKIPPED) + sum(unseen_skips(x) for x in sub or ())


# camkit.crawl's stops that end a lap as asked: --limit reached, a STOP; any other stop (off the scan, lost, an error)
# leaves the lap short (EXIT_INCOMPLETE)
LAP_ENDS = ("row limit", "stop requested")


if __name__ == "__main__":
    main()
