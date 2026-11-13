"""Read-only walk of the screens pass 1 could not read: setting tables and the function picker.

    .venv/bin/python -u kit/table_walk.py [--rows "Image Quality Settings"] [--max-options 400]

Screens (TABLES): Image Quality Settings (SLOT 1/2 cells, each opening a list), Mode Dial Control Set
(Shooting / Drive / Focus Mode Dial rows, each a Set with Dial / Set with Menu list), My Dial Settings
(dial x My Dial 1-3 cells) and Fn Menu Settings (2 x 6 tiles for stills, 2 x 6 for movies; the
second row of that name, 2 x 6 for playback), whose cells open the function picker; Custom Key/Dial Set. for stills and movies (walk_keyset: six page
tabs of keys and the Dial/Wheel grid, each opening the picker). Per table, from its menu row:
  1. Right opens the table; every (cell, arrow) is pressed once, travelling by moves already seen,
     so every cell and button the cursor can reach is found (screen.Screen.marker = its centre);
  2. per cell: its row and column labels (OCR), Enter opens its list or picker, Down runs through
     every option until the first comes round, each option's label read; MENU cancels (nothing is
     chosen). A cell that opens a notice ("not available as follows ...") is recorded and OKed only
     when the notice is information, never a confirmation;
  3. MENU leaves the screen: a table's OK button is never pressed.
Settings are downloaded before and after and must not differ. A STOP file cancels and stops.
Results: runs/<model>_fw<fw>/kit2_tables/tables.json {row: {"cells": [...], "buttons": [...], "moves": [...]}}.
"""
import argparse
import collections
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import ocr, safety, screen  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link, StopRequested  # noqa: E402
from camkit.live import LiveCamera  # noqa: E402
from camkit.vlm import check_readers  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.screen import same_position, same_state  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import Failed, at_label, bar_text, place, same_place, to_shooting  # noqa: E402
from runner import (EXIT_UNRESTORED, add_scan_argument, close_for_restore, end_session, load_scan,  # noqa: E402
                    read_json, restore_checked, write_json)

TABLES = {
    "Image Quality Settings": {"path": ["Image Quality Settings"], "screen": "table"},
    "My Dial Settings": {"path": ["My Dial Settings"], "screen": "table"},
    "Fn Menu Settings": {"path": ["Fn Menu Settings"], "screen": "fnmenu"},
    # the second row of that name: the playback Fn menu, one section of 2 x 6 tiles
    "Fn Menu Settings (playback)": {"path": ["Fn Menu Settings"], "screen": "fnmenu", "nth": 1,
                                    "fn_rows": ["Playback Upper", "Playback Lower"]},
    # three rows (Shooting / Drive / Focus Mode Dial), each Set with Dial or Set with Menu, taken at
    # once; its Set All buttons act at once too and are never pressed
    "Mode Dial Control Set": {"path": ["Mode Dial Control Set"], "screen": "table", "commit": "menu"},
    # two rows read "Custom Key/Dial Set.": stills first, then movies (their icons tell them apart)
    "Custom Key/Dial Set.": {"path": ["Custom Key/Dial Set."], "screen": "keyset"},
    "Custom Key/Dial Set. (movie)": {"path": ["Custom Key/Dial Set."], "screen": "keyset", "nth": 1},
    "Custom Key Setting": {"path": ["Custom Key Setting"], "screen": "keyset"},       # Playback: three pages
}
FN_ROWS = ["Still Upper", "Still Lower", "Movie Upper", "Movie Lower"]   # by the section icons (camera, movie)
ARROWS = ("down", "right", "up", "left")


def pos_of(s) -> tuple | None:
    """The cursor's place: a table's cell or button and its centre to 4 px (the grid never moves),
    or an Fn Menu tile by its row and column."""
    if s.kind == "fnmenu" and s.row is not None:
        return "cell", s.row, s.field
    if s.kind != "table" or s.marker is None:
        return None
    return s.focus, s.marker[0] // 4 * 4, s.marker[1] // 4 * 4


def picker_text(cam) -> str:
    """OCR of the function under the picker's bar (right of the radio)."""
    s, f = cam.read(), cam.frame
    if s.kind != "picker" or not s.bar:
        return ""
    return ocr.text_in(ocr.read([f.path])[f.path], (370, s.bar[0] - 2, 636, s.bar[1] + 2)).strip()


def picker_where(cam) -> dict:
    """The picker's title (the slot or key), page counter and the selected group's name."""
    s, f = cam.read(), cam.frame
    lines = ocr.read([f.path])[f.path]
    group = ""
    if s.group is not None:
        t = screen.PICK_ROW_TOP + screen.PICK_ROW_PITCH * s.group
        group = ocr.text_in(lines, (95, t, 336, t + screen.PICK_ROW_PITCH))
    return {"title": ocr.text_in(lines, (0, 0, 520, 40)), "page": ocr.text_in(lines, (520, 0, 640, 40)).replace(" ", ""),
            "group": group, "tab": s.field}


def cell_labels(cam, fn_rows=FN_ROWS) -> dict:
    """The cursor cell's row label (text left of the grid on its line), column header (text over the
    grid in its column) and value, by OCR; the evidence frame goes with them. An Fn Menu tile is named
    by its section and place; its value is the function named at the top right."""
    s, f = cam.read(), cam.frame
    lines = ocr.read([f.path])[f.path]
    if s.kind == "fnmenu":
        return {"row_label": fn_rows[s.row], "col_label": str(s.field + 1),
                "value": ocr.text_in(lines, (330, 55, 640, 105)), "frame": f.path.name}
    (x0, x1), (y0, y1) = s.boxes[0], s.bar
    if s.focus == "cell" and x0 < 100:
        # a row bar (Mode Dial Control Set): the row is named in orange under the drawing
        under = sorted((ln for ln in lines if ln.inside((370, 300, 640, 424))), key=lambda ln: ln.y)
        return {"row_label": under[0].text if under else "", "col_label": "",
                "value": ocr.text_in(lines, (x0, y0, x1, y1)), "frame": f.path.name}
    return {"row_label": ocr.text_in(lines, (0, y0, x0 - 4, y1)) if s.focus == "cell" else "",
            "col_label": ocr.text_in(lines, (x0, 52, x1, 110)) if s.focus == "cell" else "",
            "value": ocr.text_in(lines, (x0, y0, x1, y1)), "frame": f.path.name}


class Grid:
    """What the walk knows of one table: each (place, arrow) -> place, and the travel between them.
    A place whose move once ended somewhere else is "unsure": My Dial's OK button keeps a column it
    does not show (Left/Right on it move that column; Up goes back up into it, 2026-10-29), so
    travel re-plans after every press from where the cursor really is, and routes round unsure places
    when it can."""

    def __init__(self, start):
        self.start, self.moves, self.seen, self.unsure = start, {}, {start}, set()

    def route(self, a, b) -> list | None:
        for avoid in (self.unsure - {a}, set()):
            prev, todo = {a: None}, collections.deque([a])
            while todo:
                p = todo.popleft()
                if p == b:
                    keys = []
                    while prev[p]:
                        p, k = prev[p]
                        keys.append(k)
                    return keys[::-1]
                for (q, k), r in self.moves.items():
                    if q == p and r not in prev and (q == a or q not in avoid):
                        prev[r] = (p, k)
                        todo.append(r)
        return None

    def record(self, here, key, to):
        if (here, key) in self.moves and self.moves[(here, key)] != to:
            self.unsure.add(here)
        self.moves[(here, key)] = to
        self.seen.add(to)

    def travel(self, cam, here, there, exploring=False):
        """Press by press to `there`; exploring, a place with no known way on yet is where it stops."""
        for _ in range(40):
            if here == there:
                return there
            keys = self.route(here, there)
            if keys is None:
                if exploring:
                    return here
                raise Failed(f"no known way from {here} to {there}")
            cam.press(keys[0])
            to = pos_of(cam.read())
            if to is None:
                raise Failed(f"{keys[0]} at {here} left the screen ({cam.read().kind}, {cam.frame.path.name})")
            self.record(here, keys[0], to)
            here = to
        raise Failed(f"travelling to {there} the cursor did not get there in 40 presses ({cam.frame.path.name})")


def explore(cam, grid: Grid, row_place=None):
    """Press every arrow once at every place the cursor can reach (fails closed off the table). An
    arrow that leaves for the table's own menu row (Left on Mode Dial Control Set, 2026-10-29) is
    noted as an exit, never used again, and Right goes back in."""
    here = grid.start
    for _ in range(1000):
        untried = [(p, k) for p in sorted(grid.seen) for k in ARROWS if (p, k) not in grid.moves]
        if not untried:
            return here
        # the nearest untried place first
        best = min(untried, key=lambda pk: len(r) if (r := grid.route(here, pk[0])) is not None else 99)
        here = grid.travel(cam, here, best[0], exploring=True)
        if here != best[0]:                 # a move went elsewhere this time: choose again from here
            continue
        cam.press(best[1])
        to = pos_of(cam.read())
        if to is None and row_place is not None and same_place(place(cam), row_place):
            grid.moves[best] = ("exit",)
            print(f"   {best[1]} at {best[0][1:]} leaves for the menu row: back in with Right", flush=True)
            cam.press("right")
            to = pos_of(cam.read())
            if to is None:
                raise Failed(f"Right from the menu row did not go back into the table ({cam.read().kind}, "
                             f"{cam.frame.path.name})")
            grid.seen.add(to)
            here = to
            continue
        if to is None:
            raise Failed(f"{best[1]} at {best[0]} left the screen ({cam.read().kind}, {cam.frame.path.name})")
        grid.record(*best, to)
        here = to
    raise Failed(f"exploring the table did not finish in 1000 steps ({len(grid.seen)} places seen)")


def walk_options(cam, kind: str, limit: int) -> dict:
    """Down through a list or picker until its first state comes round; labels and frames per option."""
    first = cam.read()
    opts = []
    for _ in range(limit):
        s = cam.read()
        if kind == "picker":
            opts.append({"label": picker_text(cam), "frame": cam.frame.path.name, "saved": s.current == s.row,
                         **picker_where(cam)})
        else:
            opts.append({"label": bar_text(cam), "frame": cam.frame.path.name, "saved": s.current == s.row})
        cam.press("down")
        if cam.read().kind != kind:
            raise Failed(f"Down in the {kind} left it ({cam.read().kind}, {cam.frame.path.name})")
        if same_state(cam.read(), first):
            return {"options": opts, "wrapped": True}
    return {"options": opts, "wrapped": False}


def open_and_walk(cam, info: dict, limit: int):
    """Enter on the cell or key under the cursor: walk the list or picker it opens and cancel it with
    MENU. A notice is recorded and closed (OK only when it is information, never a confirmation)."""
    cam.press("enter")
    s = cam.read()
    if s.kind in ("list", "picker"):
        info.update(opens=s.kind, **walk_options(cam, s.kind, limit))
        cam.press("menu")                           # cancel: nothing chosen
    elif s.kind == "notice":
        text = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
        info.update(opens="notice", notice=text, notice_frame=cam.frame.path.name)
        if safety.confirmation(text):
            cam.press("menu")
        else:
            cam.press("enter" if re.search(r"not available|invalid", text, re.I) else "menu")
    else:
        info.update(opens=s.kind, frame_opened=cam.frame.path.name)
        cam.press("menu")


def walk_table(cam, name: str, limit: int, only=None, had=None) -> dict:
    """only: the cells (their pos, as recorded) to open this time; the others keep what `had` holds."""
    row_place = place(cam)
    cam.press("right")
    start = pos_of(cam.read())
    if start is None or cam.read().kind != TABLES[name]["screen"]:
        raise Failed(f"Right on {name!r} opened {cam.read().kind}, not a {TABLES[name]['screen']} ({cam.frame.path.name})")
    grid = Grid(start)
    here = explore(cam, grid, row_place)
    print(f"{name}: {sum(p[0] == 'cell' for p in grid.seen)} cells, "
          f"{sum(p[0] == 'button' for p in grid.seen)} buttons, {len(grid.moves)} moves", flush=True)
    cells, buttons = [], []
    kept = {tuple(c["pos"]): c for c in (had or {}).get("cells", [])} if only else {}
    for p in sorted(grid.seen, key=lambda q: (q[0], q[2], q[1])):
        if only and p[0] == "cell" and tuple(p[1:]) not in only:
            if tuple(p[1:]) in kept:
                cells.append(kept[tuple(p[1:])])
            continue
        here = grid.travel(cam, here, p)
        info = {"pos": list(p[1:]), **cell_labels(cam, TABLES[name].get("fn_rows", FN_ROWS))}
        if p[0] == "button":
            buttons.append(info)
            print(f"   button {info['value']!r}", flush=True)
            continue
        if TABLES[name]["screen"] == "table" and re.search(r"set\s*all|rec\.?\s*media|^\s*ok\s*$", info["value"], re.I):
            # reads like a button (they act at once): never Enter, whatever the shape said. Not on
            # the Fn Menu, whose tiles show functions ("Rec. Media Settings" is one, 2026-10-29)
            info["reads_as_button"] = True
            buttons.append(info)
            print(f"   cell {p[1:]} reads like a button ({info['value']!r}): not entered", flush=True)
            continue
        open_and_walk(cam, info, limit)
        if pos_of(cam.read()) != p:
            raise Failed(f"{name}: after the {info['opens']} the cursor is not back on its cell "
                         f"({cam.read().kind}, {cam.frame.path.name})")
        n = len(info.get("options", []))
        print(f"   {info['row_label']!r} / {info['col_label']!r} = {info['value']!r}: {info['opens']}"
              + (f", {n} options{'' if info.get('wrapped', True) else ' (did not come round)'}" if n else ""), flush=True)
        cells.append(info)
    cam.press("menu")                                   # leave without OK (Fn Menu: back to the row)
    if not same_place(place(cam), row_place):
        raise Failed(f"MENU on {name!r} did not go back to its row ({cam.read().kind}, {cam.frame.path.name})")
    return {"path": TABLES[name]["path"], "screen": TABLES[name]["screen"], "commit": TABLES[name].get("commit", "ok"),
            "nth": TABLES[name].get("nth", 0), "start": list(start[1:]),
            "cells": cells, "buttons": buttons,
            "moves": [[list(a[0]), a[1], list(b)] for a, b in grid.moves.items()]}


def key_tabs(cam, g: int):
    """On the Custom Key tabs: Down (the tabs wrap round their six pages) to page tab g."""
    for _ in range(7):
        s = cam.read()
        if s.kind != "keyset" or s.focus != "tabs":
            raise Failed(f"not on the Custom Key tabs ({s.kind}, {cam.frame.path.name})")
        if s.group == g:
            return
        cam.press("down")
    raise Failed(f"Custom Key page tab {g} not reached")


def reopen(cam, row_place, g: int, focus: str, step=None):
    """Back where the walk was after MENU left the screen for the menu row: Right, the page's tab,
    Enter, then `step` (moves along the keys or grid cells) checked by the caller."""
    if not same_place(place(cam), row_place):
        raise Failed(f"not on the Custom Key row ({cam.read().kind}, {cam.frame.path.name})")
    cam.press("right")
    key_tabs(cam, g)
    cam.press("enter")
    if cam.read().kind != "keyset" or cam.read().focus != focus:
        raise Failed(f"Enter on page tab {g} did not go into its {focus} ({cam.read().focus}, {cam.frame.path.name})")
    for k in step or []:
        cam.press(k)


def key_info(cam) -> dict:
    """The key or dial under the cursor: its name (orange, under the drawing; a dial's function under
    it), the function in its row or cell, and on the Dial/Wheel grid the column header (M / Other)."""
    s, f = cam.read(), cam.frame
    lines = ocr.read([f.path])[f.path]
    (x0, x1), (y0, y1) = s.boxes[0], s.bar
    # the name is the first line there: on the Dial/Wheel page the dial's function follows on the next
    # line, and that is the user's own setting, not a name
    under = sorted((ln for ln in lines if ln.inside((370, 300, 640, 424))), key=lambda ln: ln.y)
    name = " ".join(ln.text for ln in sorted((ln for ln in under if abs(ln.y - under[0].y) <= 12),
                                             key=lambda ln: ln.x)) if under else ""
    out = {"key": name, "value": ocr.text_in(lines, (x0, y0, x1, y1)), "frame": f.path.name}
    if s.focus == "cell":
        out["col_label"] = ocr.text_in(lines, (x0, 140, x1, 190))
    return out


def back_on(cam, row_place, g, focus, test, step) -> None:
    """After a list or picker was cancelled: on the same key or cell again (MENU may have left the
    whole screen, in which case the walk goes back in the same way)."""
    if test(cam.read()):
        return
    if cam.read().kind == "keyset" and cam.read().focus == "tabs":
        cam.press("enter")
        for k in step:
            cam.press(k)
    elif same_place(place(cam), row_place):
        reopen(cam, row_place, g, focus, step)
    if not test(cam.read()):
        raise Failed(f"after the picker the cursor is not back where it was ({cam.read().kind}, {cam.frame.path.name})")


def walk_keyset(cam, name: str, limit: int) -> dict:
    """Custom Key/Dial Set.: per page tab (they wrap round six pages), Enter goes into its keys (or, on
    Dial/Wheel, its grid); each key or cell opens the function picker, walked and cancelled. The
    grid is walked as a snake (Right, Down, Left, Down...): each move must land on a new cell. Its
    checkbox ("Separate M mode and other modes") is never pressed. MENU leaves to the row."""
    row_place = place(cam)
    cam.press("right")
    s = cam.read()
    if s.kind != "keyset" or s.focus != "tabs":
        raise Failed(f"Right on {name!r} opened {s.kind} ({s.focus}), not the Custom Key tabs ({cam.frame.path.name})")
    pages, order = [], []
    for _ in range(6):
        g = cam.read().group
        if g in order:
            break
        order.append(g)
        lines = ocr.read([cam.frame.path])[cam.frame.path]
        page = {"tab": g, "title": ocr.text_in(lines, (60, 50, 365, 105)),
                "counter": ocr.text_in(lines, (520, 0, 640, 40)).replace(" ", ""), "frame": cam.frame.path.name}
        cam.press("enter")
        s = cam.read()
        if s.kind != "keyset" or s.focus not in ("keys", "cell"):
            raise Failed(f"Enter on page tab {g} opened {s.kind} ({s.focus}, {cam.frame.path.name})")
        page["focus"], items, step = s.focus, [], []
        if s.focus == "keys":
            while True:
                r = cam.read().row
                info = {"row": r, **key_info(cam)}
                open_and_walk(cam, info, limit)
                back_on(cam, row_place, g, "keys",
                        lambda x, r=r: x.kind == "keyset" and x.focus == "keys" and x.row == r, step)
                items.append(info)
                print(f"   page {g} key {r} {info['key']!r} = {info['value']!r}: {info['opens']}, "
                      f"{len(info.get('options', []))} options", flush=True)
                cam.press("down")
                step = step + ["down"]
                s = cam.read()
                if s.kind != "keyset" or s.focus != "keys" or s.row is None or s.row <= r:
                    break                                  # round to the first key, or out of the keys
        else:
            # a snake through the grid: along the row, then Down and back. Left is never pressed in
            # the first column, where it could take the focus out to the tabs
            seen, direction, left_x = [], "right", cam.read().marker[0]
            while True:
                here = cam.read().marker
                seen.append(here)
                info = {"pos": list(here), **key_info(cam)}
                open_and_walk(cam, info, limit)
                back_on(cam, row_place, g, "cell",
                        lambda x, h=here: x.kind == "keyset" and x.focus == "cell" and x.marker == h, step)
                items.append(info)
                print(f"   page {g} cell {here} = {info['value']!r}: {info['opens']}, "
                      f"{len(info.get('options', []))} options", flush=True)

                def new_cell(x, seen=seen):
                    return x.kind == "keyset" and x.focus == "cell" and x.marker not in seen
                moved = False
                if direction == "right" or here[0] > left_x + 6:
                    cam.press(direction)
                    step = step + [direction]
                    s = cam.read()
                    if s.kind != "keyset" or s.focus != "cell":
                        raise Failed(f"{direction} in the Dial/Wheel grid left it ({s.kind}, {s.focus}, {cam.frame.path.name})")
                    moved = new_cell(s) and abs(s.marker[1] - here[1]) <= 6
                if not moved:
                    cam.press("down")
                    step = step + ["down"]
                    s = cam.read()
                    if not new_cell(s) or s.marker[1] <= here[1]:
                        break                              # the bottom row: the grid is done
                    direction = "left" if direction == "right" else "right"
        page["items"] = items
        pages.append(page)
        cam.press("menu")                                  # out of the keys: the camera goes back to the row
        if same_place(place(cam), row_place):
            cam.press("right")
            key_tabs(cam, g)
        elif not (cam.read().kind == "keyset" and cam.read().focus == "tabs"):
            raise Failed(f"MENU from page {g}'s keys went to {cam.read().kind} ({cam.frame.path.name})")
        cam.press("down")                                  # the next page
    for _ in range(3):
        if cam.read().kind != "keyset":
            break
        cam.press("menu")
    if not same_place(place(cam), row_place):
        raise Failed(f"MENU on {name!r} did not go back to its row ({cam.read().kind}, {cam.frame.path.name})")
    return {"path": TABLES[name]["path"], "screen": "keyset", "nth": TABLES[name].get("nth", 0), "pages": pages}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", action="append", default=None, help="tables to walk (default: all)")
    ap.add_argument("--max-options", type=int, default=400, help="Down presses at most per list or picker")
    ap.add_argument("--cell", action="append", default=None,
                    help="with one --rows table: open only this cell (its pos as in tables.json, e.g. 1,5) and "
                         "keep the others' earlier walk")
    add_scan_argument(ap)
    a = ap.parse_args()
    todo = [t for t in TABLES if not a.rows or t in a.rows]
    cycle, model = load_scan(a.scan)
    run = Run("kit2_tables")
    out_path = run.dir / "tables.json"
    found = read_json(out_path) if out_path.exists() else {}
    check_readers()     # no reader listed: stop before the link opens, nothing pressed
    hdmi = eyes_from_config(run)
    try:
        with Link(run) as link:
            hdmi.attach(link)
            to_shooting(link, hdmi, "the settings download")
            before = link.download("before")
            time.sleep(5)
            cam = LiveCamera(link, hdmi, run)
            try:
                cam.press("menu")
                j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
                if j is None:
                    raise Failed(f"the menu opened on a screen the scan does not know ({cam.read().kind})")
                for name in todo:
                    t = TABLES[name]
                    j = go_to(cam, cycle, model, j, t["path"][0])
                    for _ in range(t.get("nth", 0)):            # the next row with the same label
                        cam.press("down")
                        j = (j + 1) % len(cycle)
                        if not same_position(cam.read(), cycle[j]["screen"]):
                            j = None
                            break
                    if j is None or not at_label(cam, "menu", t["path"][0]):
                        raise Failed(f"on the way to {name!r} a screen was not the one the scan recorded")
                    if t["screen"] == "keyset":
                        found[name] = walk_keyset(cam, name, a.max_options)
                    else:
                        only = {tuple(int(v) for v in c.split(",")) for c in a.cell} if a.cell else None
                        found[name] = walk_table(cam, name, a.max_options, only, found.get(name))
                    write_json(out_path, found, indent=1, ensure_ascii=False)     # whole: the earlier tables' walks stay
                    if not same_position(cam.read(), cycle[j]["screen"]):
                        raise Failed(f"back on {name!r}, the row does not look as the scan recorded it")
            except StopRequested:
                print("STOP file: cancelling", flush=True)
            except Exception as e:
                print(f"error: {type(e).__name__}: {e}; cancelling", flush=True)
            close_for_restore(cam, link)            # cleanup presses; when they fail too, the restore all the same
            # a read-only walk; if anything changed, the start goes back
            ending = end_session(link, hdmi, before, "the settings download after the walk")
        restored = restore_checked(run, ending, before)
    finally:
        hdmi.close()
    if not restored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


if __name__ == "__main__":
    main()
