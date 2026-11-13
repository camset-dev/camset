"""Pass 1 on the camera: open every safe top-level row, walk its screen by type, back out with MENU.

    .venv/bin/python -u kit/crawl_run.py [--limit N] [--scan kit2_page_scan]

Uses the page scan's Down cycle and confirmed page model (camkit.crawl): before acting at any
position the screen must match what the scan recorded there. Presses: MENU, the arrows, never
Enter. Rows on the never-open list are skipped by their confirmed label.

Settings are downloaded before and after and diffed (pass 1 must change nothing); if anything changed, the
start file is uploaded and the restore checked (docs/decisions/0015). --limit stops
after opening N rows (for supervised tries). A STOP file (<run>/STOP) cancels any open
dialog with MENU and stops. It never disconnects with a menu open.

Results: kit2_crawl/rows.jsonl (one line per row), frames and presses in shots/ and events.jsonl. Every run folder
named here is in the camera's runs/<model>_fw<fw>/ (camkit.paths).
"""
import argparse
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
from camkit.live import lit_text, LiveCamera, submenu_labels  # noqa: E402
from camkit.vlm import check_readers  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.session import wait_for  # noqa: E402
from runner import (EXIT_UNRESTORED, add_scan_argument, close_for_restore, end_session, load_scan,  # noqa: E402
                    restore_checked, wait_shooting)


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


def go_to(cam, cycle, model, j, label):
    """Step from cycle position j to the row labelled `label`, the short way round, checking every
    screen against the scan. Returns the new position, or None if a screen was not the expected one."""
    from page_model import same_text
    tabs = ("Shooting", "Exposure/Color", "Focus", "Network", "Setup")
    matches = [i for i, p in enumerate(cycle) if p["kind"] == "menu" and p["page"] in model
               and p["row"] is not None and p["row"] < len(model[p["page"]]["rows"])
               and same_text(model[p["page"]]["rows"][p["row"]]["label"], label)]
    # My Menu repeats rows from other tabs (Pre-Capture Settings is on My Menu 1): prefer the real one
    real = [i for i in matches if model[cycle[i]["page"]]["breadcrumb"].startswith(tabs)]
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
        # walked to instead, the long way, which passes no Right or Enter on it (2026-11-07)
        group_name = (group_names(cycle, groups, model, there[0]) + [""] * (there[1] + 1))[there[1]]
        seen = safety.clean_label(safety.fold(group_name))         # compared as the guards fold them (live.open_refused)
        if safety.never_open(group_name) and not any(
                safety.clean_label(safety.fold(m)) and safety.clean_label(safety.fold(m)) in seen
                for m in getattr(cam, "may_open", ())):
            print(f"walking {min(ahead, n - ahead)} rows to {label!r}: its group {group_name!r} is never entered from "
                  f"the group column ({safety.never_open(group_name)})", flush=True)
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
    the Shooting tab's first group, which does."""
    j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
    if j is not None or cam.read().kind != "menu" or cam.read().focus != "rows":
        return j
    groups = page_groups(cycle, model)
    first = next((i for i, p in enumerate(cycle) if groups.get(p["page"]) == ("Shooting", 0)), None)
    if first is None:
        return None
    print("the menu opened on a page the scan does not match: to the Shooting tab by the columns", flush=True)
    return jump(cam, cycle, groups, first, model)


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


def jump(cam, cycle, groups, target, model):
    """From a page's rows to the target row's group by the columns: Left twice to the tabs, Up/Down to
    its tab (read off the screen), Right, Down to its group, Right into its rows. Returns the position
    landed on, as the scan recorded it, or None."""
    def text_of(cam):
        f = cam.frame
        return ocr.text_in(ocr.read([f.path])[f.path], (0, 0, 640, 480)).strip()
    tab, group = groups[cycle[target]["page"]]
    for _ in range(2):
        cam.press("left")
    now = tab_shown(text_of(cam))
    if now is None:
        print(f"the tab column's tab could not be read: {text_of(cam)[:60]!r}", flush=True)
        return None
    d = TABS.index(tab) - TABS.index(now)
    for _ in range(abs(d)):
        cam.press("down" if d > 0 else "up")
    if d and tab_shown(text_of(cam)) != tab:
        print(f"the tab column did not reach {tab!r}: {text_of(cam)[:60]!r}", flush=True)
        return None
    cam.press("right")
    # the group column opens on the group last used in that tab, not its first (three Downs from Operation
    # Customize reached Accessibility, 2026-11-07): the breadcrumb names the lit group, so the move is relative
    names = group_names(cycle, groups, model, tab)
    lit = lambda: lit_text(cam.frame.image, cam.frame.path)       # the breadcrumb says only the tab here
    at = group_shown(lit(), names)
    if at is None:
        print(f"the lit group could not be read in {lit()[:60]!r}: taking it as the first", flush=True)
        at = 0
    d = group - at
    for _ in range(abs(d)):
        cam.press("down" if d > 0 else "up")
    if d and group_shown(lit(), names) not in (group, None):
        print(f"the group column did not reach group {group + 1} of {tab!r}: {lit()[:60]!r}", flush=True)
        return None
    cam.press("right")
    j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
    if j is None:
        print(f"the group's rows are not a screen the scan recorded ({cam.read().kind})", flush=True)
    elif groups.get(cycle[j]["page"]) != (tab, group):
        print(f"landed in {groups.get(cycle[j]['page'])}, not {(tab, group)}: walking from there", flush=True)
    return j


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
    a = ap.parse_args()
    cycle, model = load_scan(a.scan)      # signatures from the current reader, not the one at scan time
    run = Run(a.run)
    check_readers()     # no reader listed: stop before the link opens, nothing pressed
    hdmi = eyes_from_config(run)
    results = open(run.dir / "rows.jsonl", "a", encoding="utf-8", newline="\n")  # noqa: SIM115 (closed in the finally below)
    ending = None
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
            cam = LiveCamera(link, hdmi, run)
            try:
                crawl_from_menu(cam, link, cycle, model, a.limit, results, a.start_label, a.panels,
                                tuple(a.tabs.split(",")) if a.tabs else None)
            except Exception as e:                          # never leave a dialog or the menu open
                print(f"error: {type(e).__name__}: {e}; cancelling", flush=True)
                close_for_restore(cam, link)            # cleanup presses; when they fail too, the restore all the same
            # every run ends restoring its start file (decision 15), not only a --panels run, and even when the
            # shooting screen does not come back
            ending = end_session(link, hdmi, before, "the final settings download", reach=wait_shooting)
        restored = restore_checked(run, ending, before)
    finally:
        hdmi.close()
        results.close()
    if not restored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


def crawl_from_menu(cam, link, cycle, model, limit, results, start_label=None, panels=False, tabs=None):
    """MENU, find where it opened in the scan's cycle, crawl from there, close the menu."""
    cam.press("menu")
    s = cam.read()
    j = next((i for i, p in enumerate(cycle) if same_position(s, p["screen"])), None)
    if j is not None and start_label:
        j = go_to(cam, cycle, model, j, start_label)
    if j is None:
        print(f"the menu is on a screen the scan does not know ({cam.read().kind}); stopping", flush=True)
    else:
        print(f"at scan position {j}; crawling", flush=True)

        def on_row(r):
            results.write(json.dumps(summary(r)) + "\n")
            results.flush()
            show(summary(r))
        try:
            out = crawl(cam, cycle[j:] + cycle[:j], model, max_rows=limit, on_row=on_row, labels=submenu_labels,
                        **({"tabs": tabs} if tabs else {}),
                        panels=panels)
            print(f"crawl ended: {out.stopped or 'lap complete'}; {out.presses} presses, "
                  f"{len(out.rows)} rows; the menu closed by itself {len(out.recoveries)} times "
                  f"(reopened with MENU)", flush=True)
        except StopRequested:
            print("STOP file: cancelling to the menu", flush=True)
            cam.cancel_to_menu()
    if cam.read().kind in ("menu", "tiles"):
        link.press("menu", cleanup=True)


if __name__ == "__main__":
    main()
