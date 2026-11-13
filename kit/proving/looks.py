"""Creative Look's panels: each look's eight parameters on their scales (the marker's place, checked against the
cell's number), and a custom slot's base look by the code in its title. A cell that does not read as the value chosen
is read by the vision reader before the row fails (look_checked; the owner, 2026-11-06)."""
import json
import re
import time
from pathlib import Path

from camkit import camset, ocr, screen
from camkit.vlm import PROMPTS
from runner import changes_of

from .base import Failed
from .nav import after_download, move_to, to_row
from .options import icon_index
from .screens import ask_second, place, same_place, vlm_option

LOOK_PARAMS = range(1, 9)          # the panel's cells after the look itself: Contrast ... Clarity


def scale_end(text: str) -> int | None:
    """A scale end's number. The camera draws each end as one digit, signed on a symmetric scale ("+9", "-9") and not
    on the others ("9", "0", "5", "1"), so the end is the last digit read: what OCR reads before it is the sign, a
    tick mark, or the plus itself read as a digit ("49" for "+9", Highlights 2026-11-08, which made the scale 9..49 and
    the walk press Down twenty times from 0)."""
    d = re.sub(r"\D", "", text or "")
    return int(d[-1]) if d else None


_SEEN: dict = {}       # run folder -> its scales_seen, for as long as the run's process lives


def scales_seen(run) -> dict | None:
    """The run's {(cell, tick count): every scale both ends of that cell's parameter were read as beside that many
    ticks} (look_cell gathers it, scale_from_ticks trusts it), kept for the run's process: prove_run.py makes one Run
    for all its jobs, so a look proved later can use what the earlier ones showed of the same parameter. A run resumed
    in a new process gathers it again. None for no run (a check off the camera): nothing is gathered, and the ticks
    never answer."""
    return None if run is None else _SEEN.setdefault(str(run.dir), {})


def scale_from_ticks(ticks: int | None, lo: int | None, hi: int | None, seen: set | None) -> tuple:
    """(low, high) of a scale whose end OCR missed, from its tick marks alone, or (lo, hi) as they came. The ticks
    answer only when all three hold:
    - their count alone leaves one scale on the a1 II's panel (this menu generation's: one tick a step, one digit an
      end, a scale below zero symmetric), so 19 ticks are -9..+9 and 10 are 0..9; 5 fit seven scales (0..4, 1..5 ...
      5..9, -2..+2) and never answer;
    - every end OCR read agrees with that scale (`hi` the top's number, `lo` the bottom's digit, its sign unread:
      scale_end). An end only vetoes, never chooses: a "5" read as "6" over five ticks would have made the scale 2..6;
    - this run has read both ends of this parameter beside that many ticks, as that scale and no other (`seen`, the
      scales look_cell kept for the cell and count): the body has shown it draws this scale so, and another parameter
      with as many ticks proves nothing of this one. Without that, the scale stays unread and the row stops, as before.
    Apple's OCR since macOS 27.2 misses an end on about half of the a1 II's look frames (2026-11-13). The marker's
    value on a scale an end chose is no second reading of it: the cell's number comes from the same OCR, in the same
    typeface, and at the scale's end shows the very digit the end shows."""
    if not ticks or not seen:
        return lo, hi
    span = ticks - 1
    fits = [(a, a + span) for a in range(-9, 10 - span) if a >= 0 or a == -(a + span)]
    if len(fits) != 1:
        return lo, hi
    (a, b), = fits
    if hi not in (None, b) or lo not in (None, abs(a)) or seen != {(a, b)}:
        return lo, hi
    return a, b


def look_cell(cam, known=None, seen=None) -> tuple:
    """(value in the active cell or None, the parameter's name, the scale's (low, high), the value the ▶ marker shows,
    how the scale was read: "ends", "ticks", or None when it is unread or `known` stands in for it). The scale's ends
    on the a1 II's panel are "+9"/"-9", "9"/"0", "5"/"1" (a tick mark reads as "-" before an end that is not
    negative), one digit each (scale_end). Where the screen counted the scale's ticks (screen._look_ticks), ends that
    give a scale of another number of steps leave it unread (a tick read as "+" would make 1..5's "5" a -5..+5), both
    ends read are kept in `seen` (scales_seen) under the lit cell and the ticks beside them, and an end OCR missed may
    come from the ticks (scale_from_ticks). A frame with no cell lit names no parameter: it keeps nothing and takes no
    scale from the ticks (its ends alone may give one, still held to the ticks beside them)."""
    s, f = cam.read(), cam.frame
    lines = ocr.read([f.path])[f.path]
    c = screen.LOOK_CELLS
    txt = ocr.text_in(lines, (c[s.field], 350, c[s.field + 1], 404)).strip() if s.field is not None else ""
    m = re.search(r"([+\-±*]?)\s*(\d+)\s*$", txt)
    val = None if not m else int(m.group(2)) * (-1 if m.group(1) == "-" else 1)
    top, bot = (ocr.text_in(lines, b).strip() for b in ((586, 80, 640, 120), (586, 220, 640, 262)))
    hi, lo = scale_end(top), scale_end(bot)
    both = hi is not None and lo is not None
    # "+9" over "-9" is symmetric; OCR can drop the "+" ("9" over "-9", Shadows 2026-10-29): the same
    # number at both ends can only be a symmetric scale (the others run 0..9 and 1..5)
    if hi is not None and (top.lstrip().startswith("+") or (lo == hi and hi > 0)):
        lo = -hi
    how = None if lo is None or hi is None else "ends"
    here = (s.field, s.ticks)
    if s.field is None:
        seen = None                         # no cell lit: no parameter to keep evidence for, or to take it from
    if how and s.ticks:
        if both and seen is not None:
            seen.setdefault(here, set()).add((lo, hi))
        if s.ticks != hi - lo + 1:
            lo, hi, how = None, None, None
    elif not how:
        got = scale_from_ticks(s.ticks, lo, hi, seen.get(here) if seen is not None else None)
        if None not in got:
            (lo, hi), how = got, "ticks"
    if known and (lo is None or hi is None or (lo, hi) != tuple(known)):
        (lo, hi), how = known, None         # the scale this parameter showed first (its ends unread now)
    name = ocr.text_in(lines, (130, 285, 520, 335)).strip()
    mark = None
    if s.marker is not None and hi is not None and lo is not None:
        mark = round(lo + (240 - s.marker) / 140 * (hi - lo))
    return val, name, (lo, hi), mark, how


def look_value(cam, known=None, seen=None):
    """(the active cell's value, the parameter's name, the scale, how the scale was read: look_cell). The value is
    where the ▶ marker sits on the scale (geometry, not text), checked against the size of the number in the cell when
    OCR reads one; OCR loses the minus sign ("•9" for -9, Contrast 2026-10-29), so the sign is the marker's. Without
    a marker, the cell's text."""
    for _ in range(2):
        val, name, rng, mark, how = look_cell(cam, known, seen)
        if val is not None and None not in rng and not rng[0] <= val <= rng[1]:
            val = None                       # an icon read as a digit ("49" for 9): off the scale, ignored
        if mark is not None and (val is None or abs(abs(val) - abs(mark)) <= 1):
            return mark, name, rng, how
        if mark is None and val is not None:
            return val, name, rng, how
        time.sleep(0.4)
        cam.refresh("reread")
    return None, name, rng, how


def reader_cell(cam) -> int | None:
    """The active cell's number as the vision reader reads it: the panel asked as a row of number boxes
    (PROMPTS["fields"], through screens.ask_second as every prover asks it), the orange box's value with its sign,
    "±0" as 0. None when the reader cannot be asked or does not say."""
    try:
        v = ask_second(cam.frame.path.read_bytes(), PROMPTS["fields"], timeout=60)
    except Exception:
        return None
    fields, active = (v.get("fields"), v.get("active")) if isinstance(v, dict) else (None, None)
    if not isinstance(fields, list) or isinstance(active, bool) or not isinstance(active, int) \
            or not 0 <= active < len(fields):
        return None
    m = re.search(r"([+\-\u2212±]?)\s*(\d+)", str(fields[active]))
    if not m:
        return None
    return -int(m.group(2)) if m.group(1) in ("-", "\u2212") else int(m.group(2))


def reader_on_scale(cam, scale) -> tuple:
    """(the vision reader's value of the active cell, or None, and what it read in words): None as well when the value
    is off the scale (lo, hi), which no cell can show, so a reading such as 12 on -9..+9 never sets a walk's press
    count."""
    seen = reader_cell(cam)
    if seen is None:
        return None, "nothing"
    lo, hi = scale
    if None not in (lo, hi) and not lo <= seen <= hi:
        return None, f"{seen}, off the scale {lo}..{hi}"
    return seen, str(seen)


def look_checked(cam, read, want, what: str, scale) -> tuple:
    """(the cell's value, how it was read) when OCR and the marker give `read` and the walk wants `want` on `scale`:
    read itself when they agree; else, before the row fails, the vision reader's reading of the active cell, which
    decides when it gives one on the scale (the owner, 2026-11-06: ask the reader before failing a row; it reads the
    short digits OCR drops), else read. The words name both readings for the failure and the log."""
    if read == want:
        return read, ""
    seen, words = reader_on_scale(cam, scale)
    said = f"OCR and the marker read {read}, the vision reader {words}"
    print(f"   {what}: {said} (wanted {want}, {cam.frame.path.name})", flush=True)
    return (read if seen is None else seen), said


def open_look_panel(cam, job, top, row_place, name: str, again: bool):
    """From the Creative Look row (or back to it, `again`): Right into the carousel, Down to the job's
    look, Right into its parameter panel."""
    path, L, labels = job["path"], job["look"], job["labels"]
    if again:
        to_row(cam, path, top, row_place)
        if not same_place(place(cam), row_place):
            raise Failed(f"{name}: back at the row, the page or cursor row is not the one proved before")
    cam.press("right")
    if cam.read().kind != "dialog":
        raise Failed(f"{name}: Right opened {cam.read().kind}, not the carousel")
    # a custom slot's icon shows the look it is based on, so once its base has changed it can look
    # like a preset ("1 VV2" vs "VV2", 2026-10-30). The first opening committed the slot as the look in
    # use, and the carousel opens on the look in use: base-look jobs go straight in after that
    if not ((again and job["kind"] == "lookbase") or job.get("in_use")):
        cur = icon_index(cam, job)
        if cur is None:
            raise Failed(f"{name}: could not tell which look the carousel is on")
        move_to(cam, cur, L, len(labels), "dialog")
        if icon_index(cam, job) != L:
            raise Failed(f"{name}: the carousel is not on look {L}")
    cam.press("right")
    if cam.read().kind != "look":
        raise Failed(f"{name}: Right opened {cam.read().kind}, not the look's panel")


def look_to_cell(cam, p: int, name: str):
    for _ in range(12):
        f = cam.read().field
        if f == p:
            return
        cam.press("right" if f is None or f < p else "left")
    raise Failed(f"{name}: never reached cell {p}")


LOOK_CODES = ("ST", "PT", "NT", "VV", "VV2", "FL", "FL2", "FL3", "IN", "SH", "BW", "SE")   # base looks, Down order


def look_title(cam) -> str | None:
    """The base look a custom slot's panel shows: the code in its orange title ("SE(Sepia)")."""
    t = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 55, 640, 115)).replace(" ", "").upper()
    m = re.match(r"(VV2|FL2|FL3|ST|PT|NT|VV|FL|IN|SH|BW|SE)\b|(VV2|FL2|FL3|ST|PT|NT|VV|FL|IN|SH|BW|SE)\(", t)
    return (m.group(1) or m.group(2)) if m else None


def prove_look_base(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    """A custom Creative Look slot's base look, its panel's first cell: Up/Down step through the
    twelve looks (round) and the title follows. Each other look, then the one it had, OK, download,
    diff (that last diff must be empty). Opening the panel commits the slot as the Creative Look, so
    the job downloads its own base first."""
    path, L = job["path"], job["look"]
    name = f"Creative Look custom slot {L - 11}"
    row_place = place(cam)
    n = len(LOOK_CODES)
    open_look_panel(cam, job, top, row_place, name, False)
    base_path = link.download(f"look{L}-base-base")
    after_download(cam, time.monotonic())
    base = camset.read(base_path)
    open_look_panel(cam, job, top, row_place, name, True)
    look_to_cell(cam, 0, name)
    held = look_title(cam)
    if held is None:
        raise Failed(f"{name}: cannot read the base look ({cam.frame.path.name})")
    h = LOOK_CODES.index(held)
    order = [i for i in range(n) if i != h] + [h]
    print(f"{name}: base look {held}; proving {[LOOK_CODES[i] for i in order]}", flush=True)
    last, cur, first = base_path, h, True
    for t in order:
        if not first:
            open_look_panel(cam, job, top, row_place, name, True)
            look_to_cell(cam, 0, name)
            if look_title(cam) != LOOK_CODES[cur]:
                raise Failed(f"{name}: the panel shows {look_title(cam)}, the last OK chose {LOOK_CODES[cur]}")
        first = False
        move_to(cam, cur, t, n, "look")
        if look_title(cam) != LOOK_CODES[t]:
            raise Failed(f"{name}: the title reads {look_title(cam)}, not {LOOK_CODES[t]}")
        shown = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 55, 640, 115)).strip()
        chosen, seen_vlm = cam.frame.path.name, vlm_option(cam)
        cam.press("enter")
        s = cam.read()
        if s.kind == "notice":
            raise Failed(f"{name}: after OK a notice came up ({cam.frame.path.name})")
        if s.kind != "shooting" and not same_place(place(cam), row_place):
            raise Failed(f"{name}: after OK the screen is {s.kind} ({cam.frame.path.name}), not the row")
        dat = link.download(f"look{L}-base-{LOOK_CODES[t]}")
        done = time.monotonic()
        changes = camset.diff(base, camset.read(dat))
        rec = {"path": path, "kind": "lookbase", "option": job["option"], "look": L, "index": t,
               "label": LOOK_CODES[t], "shown": shown, "chosen_frame": chosen, "vlm": seen_vlm,
               "dat": dat.name, "base": base_path.name, "applied": True,
               "changes": changes_of(changes)}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        brief = ", ".join(f"{ch.key} {ch.before!r}->{ch.after!r}" for ch in changes[:5]) or "no change"
        print(f"   {LOOK_CODES[t]:4s} {brief}", flush=True)
        last, cur = dat, t
        after_download(cam, done)
        if t == h and changes:
            raise Failed(f"{name}: back on {held}, {len(changes)} records still differ")
    to_row(cam, path, top, row_place)
    return last


def prove_look_row(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    """One Creative Look's eight parameters: for each, the range its scale shows, then the lowest,
    middle and highest values (Up raises), OK, download, diff, and back to the value it had (that
    last diff must be empty). Opening a look's panel commits the look, so the job first downloads
    its own base. A cell with no arrows (BW Saturation) cannot move and is noted as fixed. The panel's
    Reset is never pressed (a guarded key). Each proof says how the scale was read ("range_from": "ends" or "ticks",
    look_cell)."""
    path, L, labels = job["path"], job["look"], job["labels"]
    name = f"Creative Look {labels[L]!r}"
    row_place = place(cam)
    scales = scales_seen(run)

    def open_panel(again: bool):
        open_look_panel(cam, job, top, row_place, name, again)

    def to_cell(p):
        look_to_cell(cam, p, name)

    open_panel(False)
    base_path = link.download(f"look{L}-base")            # the look is committed now
    after_download(cam, time.monotonic())
    base = camset.read(base_path)
    last = base_path
    for p in LOOK_PARAMS:
        open_panel(True)
        to_cell(p)
        g = cam.read().glyphs
        start, pname, (lo, hi), range_from = look_value(cam, seen=scales)
        unread = ""
        if start is None and None not in (lo, hi):
            start, words = reader_on_scale(cam, (lo, hi))     # OCR read no value: the vision reader before the row fails
            unread = f" (the vision reader: {words})" if start is None else ""
        if not (g.get("up") or g.get("down")):
            print(f"{name} {pname or p}: fixed at {start}", flush=True)
            out.write(json.dumps({"path": path, "kind": "look", "option": job["option"], "look": L, "field": p,
                                  "param": pname, "index": [L, p, "back"], "fixed": True, "value": start,
                                  "changes": [], "applied": True}) + "\n")
            out.flush()
            # MENU from the panel steps back to the carousel, a second MENU cancels that (the look
            # itself is committed already): BW's greyed Saturation, 2026-10-29
            for _ in range(3):
                if cam.read().kind not in ("look", "dialog"):
                    break
                cam.press("menu")
            continue
        if start is None or lo is None or hi is None:
            raise Failed(f"{name} cell {p}: value {start}, range {lo}..{hi} not readable{unread}")
        targets = sorted({lo, (lo + hi) // 2, hi} - {start})      # -9/0/+9, 0/4/9, 1/3/5
        order = targets + [start]
        print(f"{name} {pname}: {start} in {lo}..{hi} (read by its {range_from}); proving {order}", flush=True)
        cur, first = start, True
        for t in order:
            if not first:
                open_panel(True)
                to_cell(p)
                now = look_value(cam, (lo, hi), scales)[0]
                now, said = look_checked(cam, now, cur, f"{name} {pname}", (lo, hi))
                if now != cur:
                    raise Failed(f"{name} {pname}: the cell shows {now}, the last OK chose {cur}" + (f" ({said})" if said else ""))
            first = False
            key, steps = ("up", t - cur) if t >= cur else ("down", cur - t)
            for _ in range(steps):
                cam.press(key)
                if cam.read().kind != "look":
                    raise Failed(f"{name} {pname}: {key} left the panel ({cam.read().kind})")
            got = look_value(cam, (lo, hi), scales)[0]
            got, said = look_checked(cam, got, t, f"{name} {pname}", (lo, hi))
            if got != t:
                raise Failed(f"{name} {pname}: the cell shows {got}, not {t}" + (f" ({said})" if said else ""))
            chosen, seen_vlm = cam.frame.path.name, vlm_option(cam)
            cam.press("enter")
            s = cam.read()
            if s.kind == "notice":
                text_n = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
                raise Failed(f"{name} {pname}: after OK a notice came up ({text_n[:60]!r})")
            if s.kind != "shooting" and not same_place(place(cam), row_place):
                raise Failed(f"{name} {pname}: after OK the screen is {s.kind} ({cam.frame.path.name}), not the row")
            dat = link.download(f"look{L}-{p}-{t}")
            done = time.monotonic()
            changes = camset.diff(base, camset.read(dat))
            back = t == start
            rec = {"path": path, "kind": "look", "option": job["option"], "look": L, "field": p, "param": pname,
                   "index": [L, p, "back" if back else t], "label": f"{pname} {t:+d}" if lo < 0 else f"{pname} {t}",
                   "value": t, "range": [lo, hi], "range_from": range_from, "chosen_frame": chosen, "vlm": seen_vlm, "dat": dat.name, "base": base_path.name,
                   "changes": changes_of(changes),
                   "sampled": True, "applied": True}
            out.write(json.dumps(rec) + "\n")
            out.flush()
            brief = ", ".join(f"{ch.key} {ch.before!r}->{ch.after!r}" for ch in changes[:4]) or "no change"
            print(f"   {pname} = {t:<4} {brief}", flush=True)
            last, cur = dat, t
            after_download(cam, done)
            if back and changes:
                raise Failed(f"{name} {pname}: back on {start}, {len(changes)} records still differ")
    to_row(cam, path, top, row_place)
    return last
