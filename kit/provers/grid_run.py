"""Prove a checkbox grid: Focus Area Limit (24 focus areas in 7 columns, two rows in view; 2026-10-30).

    .venv/bin/python -u kit/provers/grid_run.py [--row "Focus Area Limit"] [--scan kit2_page_scan]

Like kit/prove_run.py's checklists: one visit per cell puts the previous cell back and flips the next
(neighbours are one Right apart), OK, a settings download, a diff with the start; a last visit puts
the last cell back and must leave nothing changed. The pixel reader gives the cursor's cell and every
cell's tick ("checkgrid"); the cell's name is the subtitle over the grid (OCR), checked against pass 1's
labels before Enter. Down from the grid reaches the buttons; OK is the left one. A cell the camera
will not untick (a notice comes up) is recorded as refused, as checklists do. Proofs go to
runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl as kind "checklist", so the report and schema_update read them unchanged;
the start file goes back on at the end and is checked.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, ocr, safety, screen  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.runs import Run  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import LOCK_S, PASS1, Failed, enter_any, option_key, to_shooting, vlm_option  # noqa: E402
from runner import (add_scan_argument, changes_of, load_scan, menu_from_shooting, proofs_file,  # noqa: E402
                    prover_session, read_json, scan_position)

SUBTITLE = (0, 60, 640, 118)
OK_BOX = (73, 362, 313, 418)             # the OK button under the grid; Cancel is right of it
COLS = 7


def lines(cam):
    return ocr.read([cam.frame.path])[cam.frame.path]


def subtitle(cam) -> str:
    return ocr.text_in(lines(cam), SUBTITLE).strip()


def ok_lit(cam) -> bool:
    x0, y0, x1, y1 = OK_BOX
    return float(screen._orange(cam.frame.image)[y0:y1, x0:x1].mean()) > 0.5


def tick(cam) -> bool | None:
    s = cam.read()
    if s.kind != "checkgrid" or s.focus != "rows" or s.row is None or s.field is None:
        return None
    i = s.row * COLS + s.field
    return s.slots[i] == "ticked" if i < len(s.slots) else None


def labels_of(path: list) -> list:
    row = next(r for r in read_json(PASS1 / "map.json")["rows"] if r["path"] == path)
    if row["kind"] != "checkgrid":
        sys.exit(f"{' > '.join(path)} is a {row['kind']}, not a checkbox grid")
    return [o["label"] for o in sorted(row["options"], key=lambda o: tuple(o["index"]))]


def open_grid(cam, cycle, model, path):
    menu_from_shooting(cam)              # MENU, once more if it went unanswered after a download
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, path[0]) is None:
        raise Failed(f"could not reach {path[0]!r} by the scan")
    enter_any(cam, path, 0)
    cam.press("right")
    title = ocr.text_in(lines(cam), (0, 0, 640, 52))
    if cam.read().kind != "checkgrid" or option_key(path[-1]) not in option_key(title):
        raise Failed(f"Right on {path[-1]!r} opened {cam.read().kind} ({title!r}), not its grid")


def cell_now(cam, labels: list) -> int | None:
    keys = [option_key(x) for x in labels]
    sub = option_key(subtitle(cam))
    return keys.index(sub) if tick(cam) is not None and sub in keys else None


def to_cell(cam, labels: list, k: int):
    """To cell k by rows and columns: the subtitle says which cell the cursor is on; Left/Right stay in
    a grid row, Up/Down change rows (2026-10-30: Right from a row's last cell does not go on)."""
    for _ in range(12):
        at = cell_now(cam, labels)
        if at is None:
            raise Failed(f"cannot tell which cell the cursor is on (subtitle {subtitle(cam)!r})")
        if at == k:
            return
        (r, c), (tr, tc) = divmod(at, COLS), divmod(k, COLS)
        # along the row first: the last row is short (3 cells), and Down where no cell lies below goes
        # to the buttons (2026-10-30)
        key, steps = (("right" if tc > c else "left"), abs(tc - c)) if c != tc else (("down" if tr > r else "up"), abs(tr - r))
        for _ in range(steps):
            cam.press(key)
    raise Failed(f"cell {labels[k]!r} never took the cursor (subtitle {subtitle(cam)!r})")


def to_ok(cam):
    for _ in range(6):
        if cam.read().focus == "button":
            break
        cam.press("down")
    if cam.read().focus == "button" and not ok_lit(cam):
        cam.press("left")                         # Down from a right-hand column lands on Cancel
    word = ocr.text_in(lines(cam), OK_BOX)
    if cam.read().focus != "button" or not ok_lit(cam) or option_key(word) != option_key("OK"):
        raise Failed(f"the cursor is not on OK ({word!r}, {cam.frame.path.name})")


def visit(cam, link, hdmi, cycle, model, path, labels, cells: list) -> dict:
    """Flip `cells` in order, OK, download. Returns what the proof record needs."""
    open_grid(cam, cycle, model, path)
    flipped = []
    for k in sorted(cells):
        to_cell(cam, labels, k)
        before = tick(cam)
        cam.press("enter")
        after = tick(cam)
        if before is None or after is None or after == before:
            raise Failed(f"Enter did not flip {labels[k]!r} ({before} -> {after})")
        flipped.append({"box": k, "label": labels[k], "ticked": after})
    to_ok(cam)
    full = ocr.text_in(lines(cam), (0, 0, 640, 480))
    if safety.confirmation(full):
        raise Failed(f"the grid reads like a confirmation ({safety.confirmation(full)}): no OK")
    chosen, seen_vlm = cam.frame.path.name, vlm_option(cam)
    cam.press("enter")
    notice = None
    if cam.read().kind == "notice":
        text = ocr.text_in(lines(cam), (0, 0, 640, 480))
        if safety.confirmation(text):
            raise Failed(f"after OK a confirmation came up ({cam.frame.path.name})")
        notice = {"text": text, "frame": cam.frame.path.name}
        print(f"   refused: {text[:90]!r}", flush=True)
        cam.cancel_to_menu()
    row_frame = cam.frame.path.name
    to_shooting(link, hdmi, "the download after OK")
    time.sleep(1)
    dat = link.download(f"{path[-1]}-cells{'-'.join(map(str, sorted(cells)))}")
    time.sleep(LOCK_S)
    return {"boxes": flipped, "chosen_frame": chosen, "row_frame": row_frame, "vlm": seen_vlm,
            "dat": dat, "notice": notice}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--row", default="Focus Area Limit", help="the grid row's path, ' > ' between submenus")
    add_scan_argument(ap)
    ap.add_argument("--context", default=None, help="the state these proofs are made in")
    ap.add_argument("--first", type=int, default=0, help="start at this cell (the cells before it proved already)")
    a = ap.parse_args()
    path = a.row.split(" > ")
    if any(safety.never_open(p) for p in path):
        sys.exit("that row is on the never-open list")
    labels = labels_of(path)
    n = len(labels)
    cycle, model = load_scan(a.scan)
    run = Run("kit2_pass2")
    hdmi = eyes_from_config(run)
    with proofs_file(run, a.context) as out, \
            prover_session(run, hdmi, say_start=False, end_why="the settings download after the grid") as s:
        cam, link, start = s.cam, s.link, s.start
        base = camset.read(start)
        print(f"start file: {start.name}; {n} cells: {labels}", flush=True)
        flipped = []
        for i in range(a.first, n + 1):
            got = visit(cam, link, hdmi, cycle, model, path, labels, flipped + ([i] if i < n else []))
            ch = camset.diff(base, camset.read(got["dat"]))
            label = labels[i] if i < n else "(all back)"
            rec = {"path": path, "kind": "checklist", "index": i, "label": label, "boxes": got["boxes"],
                   "chosen_frame": got["chosen_frame"], "vlm": got["vlm"], "row_frame": got["row_frame"],
                   "dat": got["dat"].name, "base": start.name, "notice": got["notice"],
                   "applied": got["notice"] is None, "grid": True, "changes": changes_of(ch)}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            what = ", ".join(f"{b['label']!r} {'ticked' if b['ticked'] else 'unticked'}" for b in got["boxes"])
            brief = ", ".join(f"{c.key} {c.before!r}->{c.after!r}" for c in ch[:6]) or "no change"
            print(f"   {what:52s} {brief}", flush=True)
            flipped = [] if got["notice"] or i >= n else [i]
            if i == n and ch:
                # unticking the area in use moves the focus area (and spot size) in use, and
                # ticking it again leaves them: the start file puts them back below
                print(f"   every cell back; {len(ch)} records moved with the area in use: "
                      f"{[c.key for c in ch][:8]}", flush=True)


if __name__ == "__main__":
    main()
