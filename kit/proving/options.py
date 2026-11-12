"""Which option the cursor is on: a list's slot checked against its label, a carousel's title, a rating by its stars,
Creative Look's slots by their icon against pass 1's pictures, and a picker's function by its place in the table
walk (kit/table_walk.py) where OCR reads twins alike."""
import difflib
import re
import time

import numpy as np

from camkit import ocr, screen
from camkit.frames import load

from . import base
from .base import frame_file
from .screens import _matches, bar_text, carousel_text, main_name, option_key, vlm_option


def option_index(cam, labels, kind: str = "list", table=None) -> int | None:
    """Which option the cursor is on: the slot in a list that does not scroll (checked against the
    label read), else the one label that matches (OCR, then the vision model)."""
    s = cam.read()
    if kind == "dialog":
        # the title line redraws a moment after the side strip (ISO, 2026-10-29): look again first
        time.sleep(0.4)
        cam.refresh("reread")
        t = re.sub(r":{2,}", ":", carousel_text(cam))          # "Fluor:: Day White": a dot read as a second colon
        hits = [i for i, l in enumerate(labels) if option_key(l) == option_key(t)]
        if not hits:          # the second-axis value differs from pass 1's ("Continuous Shooting: Hi")
            hits = [i for i, l in enumerate(labels)
                    if option_key(main_name(l, kind)) == option_key(main_name(t, kind))]
        if not hits and t and not re.search(r"\d", t):
            # a carousel of numbers with one word among them, the automatic position whose second axis is a
            # scale of words (ISO AUTO Min. SS: Fast's Slower to Faster; it opened on "Standard", 2026-11-07):
            # the one wordy option is that position, whatever word the camera shows there
            words = [i for i, l in enumerate(labels) if not re.search(r"\d", l)]
            hits = words if len(words) == 1 else hits
        if len(hits) != 1:    # still not one option: the vision model's reading of the title
            v = vlm_option(cam)
            vh = [i for i, l in enumerate(labels) if option_key(l) == option_key(v)] if v else []
            if v and not vh:
                # the reader gives the lit entry of the side strip with its icon's letters ("ISO ASS 2"" for the
                # title 2", which OCR drops as too short, 2026-11-07): the one label the reading ends with
                vh = [i for i, l in enumerate(labels) if len(option_key(l)) >= 2 and option_key(v).endswith(option_key(l))]
            hits = vh if len(vh) == 1 else hits
        return hits[0] if len(hits) == 1 else None
    if kind == "list" and any("★" in l for l in labels):
        # ratings by their star count (screen.count_stars), anything else by its text
        n = screen.count_stars(cam.frame.image, s.bar)
        if n:
            star = [i for i, l in enumerate(labels) if l.count("★") == n]
            return star[0] if len(star) == 1 else None
        t, plain = bar_text(cam), [l if "★" not in l else "\0" for l in labels]
        hits = _matches(t, plain)
        if not hits:     # the divider's arrow reads as "+" or "P" ("o Divider Frame (P)" with the saved
            # option's radio in front, 2026-10-29): without the radio and the brackets
            bare = option_key(re.sub(r"\(.*?\)", "", re.sub(r"^[oO0]\s+", "", t)))
            hits = [i for i, l in enumerate(plain) if l != "\0" and option_key(re.sub(r"\(.*?\)", "", l)) == bare]
        return hits[0] if len(hits) == 1 else None
    frames = (table or {}).get("frames")
    if kind == "picker" and table:
        # by place first: twins told apart only by an icon ("Fixed Speed STBY" for the zoom and the
        # remote zoom) read alike, and OCR garbles one of them now and then (Fn Menu, 2026-10-29)
        t = bar_text(cam)
        hits = by_position(cam, t, labels, frames, table.get("pages"))
        if len(hits) == 1:
            return hits[0]
        hits = _matches(t, labels)
        if len(hits) != 1:
            # icons read as marks, arrows as "+>", "+»" or "1" (My Dial): a single close reading on the
            # same row, the clearly closest function name, else the vision model's reading
            hits = by_place(cam, t, labels, frames) or closest_function(t, labels) or \
                closest_function(vlm_option(cam), labels)
        return hits[0] if len(hits) == 1 else None
    if kind == "list" and table and frames and s.scroll is None and s.row is not None:
        # a table's short list: the walk saw each option on a row of a list this long; OCR of its
        # icons varies ("Lossless Comp (M) KAW" / "RAW Lossless Comp (M) -M", "21м" / "21M", 2026-10-30)
        same = [i for i, f in enumerate(frames) if f and walk_row(f) == (s.kind, s.row, s.count)]
        if len(same) == 1:
            return same[0]
    hits = _matches(bar_text(cam), labels)
    if s.scroll is None and s.row is not None and s.count == len(labels) and frames is None:
        # pass 1's lists are in screen order; a table walk's are in Down order from the saved option
        # (Image Quality's File Format opens on JPEG, its second row, 2026-10-29): text only there
        return s.row if (not hits or s.row in hits) else None
    if len(hits) != 1:
        hits = _matches(vlm_option(cam), labels)
    return hits[0] if len(hits) == 1 else None


_ICONS: dict = {}


def icon_bits(frame):
    """The selected option's icon in a carousel's strip (orange counts as ink), as a small picture."""
    lit = np.where(screen._orange(frame.image), 255, screen._grey(frame.image))
    return np.unpackbits(screen._binarize_small(lit, (14, 185, 104, 240), (36, 22), 150))


def icon_index(cam, job, margin: int = 3) -> int | None:
    """The option whose pass-1 icon picture is clearly closest (Creative Look: same option across two
    laps 0 cells apart, different options 4 or more)."""
    key = " > ".join(job["path"])
    if key not in _ICONS:
        _ICONS[key] = [icon_bits(load(frame_file(job["path"], fr))) for fr in job["icon_frames"]]
    time.sleep(0.4)
    cam.refresh("reread")
    live = icon_bits(cam.frame)
    d = sorted((int(np.count_nonzero(live != tp)), i) for i, tp in enumerate(_ICONS[key]))
    if len(d) == 1 or d[1][0] - d[0][0] >= margin:
        return d[0][1]
    # not clear by the icon alone (ST 3 cells, SE 5, 2026-10-29): the title names a look, which leaves
    # that look and the custom slots (whose title is the look each is based on); the icon picks
    t = carousel_text(cam)
    labels = job["labels"]
    cand = {i for i, l in enumerate(labels) if option_key(l) == option_key(t) or l.startswith("Custom Look")}
    dd = [x for x in d if x[1] in cand]
    return dd[0][1] if dd and (len(dd) == 1 or dd[1][0] - dd[0][0] >= 2) else None


def which_option(cam, job) -> int | None:
    if job.get("icon_frames"):
        return icon_index(cam, job)
    return option_index(cam, job["labels"], job["kind"])


def function_name(label: str) -> str:
    """A picker label without the function's icon, which OCR reads as a stray mark or letter or two
    ("• S Creative Look", "R Focus Area", "% Focus Area"), compared like option_key."""
    return option_key(re.sub(r"^(?:\S{1,2}\s+)+", "", label))


_WALKED: dict = {}                 # walk frame -> (cursor row, rows on the page)


def walk_row(frame: str) -> tuple:
    if frame not in _WALKED:
        w = screen.read(load(base.TABLES.parent / "shots" / frame))
        _WALKED[frame] = (w.kind, w.row, w.count)
    return _WALKED[frame]


def by_position(cam, t: str, labels: list, frames, pages) -> list:
    """[i] for the one option the walk saw on this page (the picker's n/N, read now) at this cursor
    row of a page this long, when its label is at least loosely like the reading; else []."""
    if not frames or not pages:
        return []
    s, f = cam.read(), cam.frame
    page = ocr.text_in(ocr.read([f.path])[f.path], (520, 0, 640, 40)).replace(" ", "")
    if not re.fullmatch(r"\d+/\d+", page):
        return []
    hits = [i for i in range(len(labels)) if pages[i] == page and frames[i]
            and walk_row(frames[i]) == (s.kind, s.row, s.count)]
    if len(hits) == 1 and (not t or difflib.SequenceMatcher(
            None, function_name(t), function_name(labels[hits[0]])).ratio() >= 0.5):
        return hits
    return []


def by_place(cam, t: str, labels: list, frames) -> list:
    """[i] for the one close reading (function names at least 0.8 alike) whose walk frame shows the
    picker's cursor on the same row of a page as long as this one: near twins such as Move AF Frame
    with the left-right or the up-down arrow sit on different rows."""
    if not t or not frames:
        return []
    s = cam.read()
    near_ = [i for i, l in enumerate(labels)
             if difflib.SequenceMatcher(None, function_name(t), function_name(l)).ratio() >= 0.8 and frames[i]]
    same = []
    for i in near_:
        if walk_row(frames[i]) == (s.kind, s.row, s.count):
            same.append(i)
    return same if len(same) == 1 else []


def closest_function(t: str, labels: list, least: float = 0.8, margin: float = 0.06) -> list:
    """[i] for the one label whose function name is clearly the closest to `t`, else []."""
    if not t:
        return []
    r = sorted(((difflib.SequenceMatcher(None, function_name(t), function_name(l)).ratio(), i)
                for i, l in enumerate(labels)), reverse=True)
    if r and r[0][0] >= least and (len(r) == 1 or r[0][0] - r[1][0] >= margin):
        return [r[0][1]]
    return []


def same_functions(a: list, b: list) -> bool:
    """Two pickers list the same functions in the same order, allowing OCR's slips in each label
    (My Dial's twelve cells, 2026-10-29: "Move AF Frame +> : L" / "Move AF Frame+ : L"). A walk
    starts each list at the slot's saved function, so b may be a's list turned round (Fn Menu)."""
    if len(a) != len(b):
        return False
    alike = lambda x, y: difflib.SequenceMatcher(None, function_name(x), function_name(y)).ratio() >= 0.8
    return any(alike(a[0], b[r]) and all(alike(x, y) for x, y in zip(a, b[r:] + b[:r], strict=True)) for r in range(len(b)))
