"""White Balance's fine-tune grid, one preset at a time: each axis at both ends and 0, and the corners, read off the
grid's own readout."""
import json
import re
import time
from pathlib import Path

from camkit import camset, ocr
from runner import changes_of

from .base import Failed
from .nav import after_download, move_to, to_row
from .options import option_index
from .screens import place, same_place, vlm_option

WB_AXES = {"A-B": ("right", "left", "A", "B", (230, 318, 420, 362)),
           "G-M": ("up", "down", "G", "M", (230, 362, 420, 408))}


def wb_reading(cam, axis: str):
    """The grid's own readout for one axis as the schema stores it: A and G negative, B and M
    positive, in thousandths ("A-B: A0.5" -> -500, "G-M: M1.25" -> 1250, "G-M: 0" -> 0)."""
    _, _, neg, pos, box = WB_AXES[axis]
    f = cam.frame
    txt = ocr.text_in(ocr.read([f.path])[f.path], box).replace(" ", "")
    num = r"([\dOo]+(?:[.,][\dOo]+)?)"                 # "MO.75": OCR reads a zero as O
    m = re.search(r"[:;]([AaBbGgMm]?)" + num + "$", txt) or re.search(r"([AaBbGgMm]?)" + num + "$", txt)
    if not m:
        return None
    v = round(float(m.group(2).replace(",", ".").replace("O", "0").replace("o", "0")) * 1000)
    side = m.group(1).upper()
    return 0 if v == 0 else (-v if side == neg else v if side == pos else None)


def prove_wb_row(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    """One White Balance preset's fine-tune grid: per axis, both ends (7 either way) and 0, then back
    to where it was; OK, download, diff each. Opening the grid commits the preset: the job first
    downloads its own base. The grid's Pos. Reset is never pressed (a guarded key)."""
    path, P, labels = job["path"], job["preset"], job["labels"]
    name = f"White Balance {labels[P]!r}"
    row_place = place(cam)

    def open_grid(again: bool):
        if again:
            to_row(cam, path, top, row_place)
            if not same_place(place(cam), row_place):
                raise Failed(f"{name}: back at the row, the page or cursor row is not the one proved before")
        cam.press("right")
        if cam.read().kind != "dialog":
            raise Failed(f"{name}: Right opened {cam.read().kind}, not the carousel")
        cur = option_index(cam, labels, "dialog")
        if cur is None:
            raise Failed(f"{name}: could not tell which preset the carousel is on")
        move_to(cam, cur, P, len(labels), "dialog")
        if option_index(cam, labels, "dialog") != P:
            raise Failed(f"{name}: the carousel is not on the preset")
        cam.press("right")
        if cam.read().kind == "dialog" and (labels[P].lower().startswith("custom") or "temp" in labels[P].lower()):
            # a Custom preset: the first Right lands on SET (it captures a custom white: never
            # pressed), the second on the › box, which opens the grid (2026-10-29). C.Temp./Filter:
            # the first Right lands on the colour temperature, the second opens the grid (2026-10-30)
            cam.press("right")
        if cam.read().kind != "wbgrid":
            raise Failed(f"{name}: Right opened {cam.read().kind}, not the fine-tune grid")

    def read(axis):
        for _ in range(2):
            v = wb_reading(cam, axis)
            if v is not None:
                return v
            time.sleep(0.4)
            cam.refresh("reread")
        return None

    def go(axis, target):
        to_neg, to_pos = WB_AXES[axis][0], WB_AXES[axis][1]
        for _ in range(70):
            v = read(axis)
            if v is None:
                raise Failed(f"{name} {axis}: the readout cannot be read")
            if v == target:
                return
            cam.press(to_neg if target < v else to_pos)
            if cam.read().kind != "wbgrid":
                raise Failed(f"{name} {axis}: the press left the grid ({cam.read().kind})")
        raise Failed(f"{name} {axis}: never reached {target}")

    open_grid(False)
    base_path = link.download(f"wb{P}-base")              # the preset is committed now
    after_download(cam, time.monotonic())
    base = camset.read(base_path)
    last = base_path
    for axis in ([] if job.get("only_corners") else WB_AXES):
        open_grid(True)
        start = read(axis)
        if start is None:
            raise Failed(f"{name} {axis}: the readout cannot be read")
        order = [x for x in (-7000, 7000, 0) if x != start] + [start]
        print(f"{name} {axis}: at {start}; proving {order}", flush=True)
        cur = start                                     # where the grid is: each OK moves it to the target
        for n, target in enumerate(order):
            if n:
                open_grid(True)
                now = read(axis)
                if now != cur:
                    raise Failed(f"{name} {axis}: the grid shows {now}, the last OK chose {cur}")
            go(axis, target)
            chosen, seen_vlm = cam.frame.path.name, vlm_option(cam)
            cam.press("enter")
            s = cam.read()
            if s.kind == "notice":
                text_n = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
                raise Failed(f"{name} {axis}: after OK a notice came up ({text_n[:60]!r})")
            if s.kind != "shooting" and not same_place(place(cam), row_place):
                raise Failed(f"{name} {axis}: after OK the screen is {s.kind} ({cam.frame.path.name}), not the row")
            dat = link.download(f"wb{P}-{axis}-{target}")
            done = time.monotonic()
            changes = camset.diff(base, camset.read(dat))
            back = n == len(order) - 1
            rec = {"path": path, "kind": "wbgrid", "option": job["option"], "preset": P, "axis": axis,
                   "index": [P, axis, "back" if back else target], "label": f"{labels[P]} {axis} {target}",
                   "value": target, "chosen_frame": chosen, "vlm": seen_vlm, "dat": dat.name, "base": base_path.name,
                   "changes": changes_of(changes),
                   "sampled": True, "applied": True}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            brief = ", ".join(f"{ch.key} {ch.before!r}->{ch.after!r}" for ch in changes[:4]) or "no change"
            print(f"   {axis} = {target:<6} {brief}", flush=True)
            last, cur = dat, target
            after_download(cam, done)
            if back and changes:
                raise Failed(f"{name} {axis}: back on {start}, {len(changes)} records still differ")
    if job.get("corners"):
        # the grid is a square, not a cross: all four corners (G7 A7, G7 B7, M7 A7, M7 B7; in this
        # prover's convention A and G are -7000), then back. Each axis's records must take what that
        # axis alone gave (user, 2026-10-29: "you can have G7 A7, G7 B7, M7 A7, and M7 B7")
        open_grid(True)
        starts = {axis: read(axis) for axis in WB_AXES}
        # ... and one point inside the square on neither axis (A3.5 + M2.25): the 29 x 57 positions
        # in between are inferred from these when both axes are linear and independent
        corners = [(-7000, -7000), (7000, -7000), (-7000, 7000), (7000, 7000), (-3500, 2250),
                   (starts["A-B"], starts["G-M"])]
        for n, (ab, gm) in enumerate(corners):
            if n:
                open_grid(True)
            go("A-B", ab)
            go("G-M", gm)
            chosen = cam.frame.path.name
            cam.press("enter")
            s = cam.read()
            if s.kind != "shooting" and not same_place(place(cam), row_place):
                raise Failed(f"{name} corner: after OK the screen is {s.kind}, not the row")
            dat = link.download(f"wb{P}-corner-{n}")
            done = time.monotonic()
            changes = camset.diff(base, camset.read(dat))
            back = n == len(corners) - 1
            rec = {"path": path, "kind": "wbgrid", "option": job["option"], "preset": P, "axis": "corner",
                   "index": [P, "corner", "back" if back else f"{ab},{gm}"], "label": f"{labels[P]} corner {ab},{gm}",
                   "value": [ab, gm], "chosen_frame": chosen, "dat": dat.name, "base": base_path.name,
                   "changes": changes_of(changes),
                   "applied": True}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            print(f"   corner {ab},{gm}: " + (", ".join(f"{ch.key} {ch.before!r}->{ch.after!r}" for ch in changes[:6])
                                             or "no change"), flush=True)
            last = dat
            after_download(cam, done)
            if back and changes:
                raise Failed(f"{name} corner: back on the start, {len(changes)} records still differ")
    to_row(cam, path, top, row_place)
    return last
