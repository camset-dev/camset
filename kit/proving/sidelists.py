"""Picture Profile's side lists: a numeric lap rebuilt from its cycle where OCR misread a value, the value under the
cursor (OCR, the bar alone enlarged, the rows above and below, the vision model, pass 1's pictures), and the prover.

SPREAD is the run's (--spread: main() sets sidelists.SPREAD)."""
import collections
import json
import re
import time
from pathlib import Path

import numpy as np

from camkit import camset, ocr, safety, screen
from camkit.frames import load
from runner import changes_of

from .base import Failed, frame_file
from .nav import after_download, move_to, to_row
from .screens import option_key, place, refuse_or_fail, same_place, vlm_option

# --spread: a side list proves its lowest, middle and highest value (numbers already sample so; a long
# text list takes its first, middle and last), the owner's choice for rows whose codes are proved
# elsewhere (Picture Profile in Movie mode after Stills, 2026-11-01)
SPREAD = False


def signed(v: str):
    """A side list's number with its sign ("-5", "+15", "92.5%"), or None for text ("Type1", "Movie")."""
    m = re.fullmatch(r"\s*([+-]?)\s*(\d+(?:\.\d+)?)\s*%?\s*", str(v or ""))
    return None if not m else float(m.group(2)) * (-1 if m.group(1) == "-" else 1)


def fix_lap(labels: list) -> list:
    """A numeric side list is one cycle: a steady step that wraps at its lowest and highest value
    (Black Level -15..+15 by Down: 0, -1 ... -15, +15 ... +1). OCR misreads a few values ("5" for -5,
    "R" for -7 on Color Depth R): the lap is rebuilt from where most readings put its start. Text
    lists, and laps whose readings do not fit one cycle, are returned as read."""
    nums = [signed(v) for v in labels]
    n = len(labels)
    known = [(i, x) for i, x in enumerate(nums) if x is not None]
    if n <= 3 or len(known) < n - 2:
        return labels
    diffs = collections.Counter(round(nums[i + 1] - nums[i], 4) for i in range(n - 1)
                                if nums[i] is not None and nums[i + 1] is not None)
    step = diffs.most_common(1)[0][0]
    s, d = abs(step), (1 if step > 0 else -1)
    if s == 0:
        return labels
    best = None                       # the range from either end: an unread lowest or highest value
    for lo in {min(x for _, x in known), max(x for _, x in known) - (n - 1) * s}:
        fit = [(i, x) for i, x in known if lo - 1e-9 <= x <= lo + (n - 1) * s + 1e-9]
        starts = collections.Counter((round((x - lo) / s) - d * i) % n for i, x in fit)
        q0, votes = starts.most_common(1)[0]
        if best is None or votes > best[2]:
            best = (lo, q0, votes)
    lo, q0, votes = best
    if votes < n - 3:
        return labels
    plus = any(str(v).lstrip().startswith("+") for v in labels)
    pct = any(str(v).rstrip().endswith("%") for v in labels)
    out = []
    for i in range(n):
        v = lo + ((q0 + d * i) % n) * s
        out.append(f"{v:g}%" if pct else ("+" if plus and v > 0 else "") + f"{v:g}")
    return out


_SIDE: dict = {}


def side_bits(frame, s):
    """The value under a side list's cursor bar as a small binary picture."""
    return np.unpackbits(screen._binarize_small(screen._grey(frame.image), (300, s.bar[0] + 2, 600, s.bar[1] - 2),
                                                (48, 12), 150))


def side_templates(job) -> list:
    key = " > ".join(job["path"])
    if key not in _SIDE:
        out = []
        for fr in job["frames"]:
            path = frame_file(job.get("map_path"), fr)
            s = screen.read(load(path)) if path else None
            out.append(side_bits(load(path), s) if s is not None and s.kind == "sidelist" and s.bar else None)
        _SIDE[key] = out
    return _SIDE[key]


def side_text(cam) -> str:
    s, f = cam.read(), cam.frame
    if s.kind != "sidelist" or not s.bar:
        return ""
    return ocr.text_in(ocr.read([f.path])[f.path], (290, s.bar[0] - 4, 612, s.bar[1] + 4)).strip(" •o")


def side_index(cam, job, margin: int = 5) -> int | None:
    """Which value is under the cursor: OCR when it names exactly one value; a number OCR read without
    its sign ("5": +5 or -5) by the rows above and below; pass 1's pictures only when OCR found
    nothing usable (a lone "0"). Pictures come last: two were caught mid-scroll at a lap's wrap and
    looked like other values (Knee Point 75%, Slope -5, 2026-10-29)."""
    s = cam.read()
    if s.kind != "sidelist" or not s.bar:
        return None
    vals = job["values"]
    t = side_text(cam)
    hits = [i for i, v in enumerate(vals) if option_key(v) == option_key(t)]
    if len(hits) == 1:
        return hits[0]
    if not hits:                                 # short numbers on the orange bar: read the bar alone
        t2 = bar_ocr(cam)
        hits2 = [i for i, v in enumerate(vals) if option_key(v) == option_key(t2)]
        if len(hits2) == 1:
            return hits2[0]
        t = t or t2
    if signed(t) is not None:                    # a number without its sign: the neighbours decide
        hits = [i for i, v in enumerate(vals) if signed(v) is not None and abs(signed(v)) == abs(signed(t))]
        if len(hits) > 1:
            hits = by_neighbours(cam, vals, hits)
        if len(hits) == 1:
            return hits[0]
    if not t:                                    # nothing read on the bar: the rows round it say where it is
        inferred = from_neighbours(cam, vals)
        if inferred is not None:
            return inferred
    v = vlm_option(cam)                          # OCR found nothing usable: the vision model, then
    vh = [i for i, x in enumerate(vals) if option_key(x) == option_key(v)] if v else []
    if len(vh) == 1:                             # pass 1's pictures
        return vh[0]
    live = side_bits(cam.frame, s)
    d = sorted((int(np.count_nonzero(live != tp)), i) for i, tp in enumerate(side_templates(job))
               if tp is not None and tp.shape == live.shape and (not hits or i in hits))
    if d:
        best, i = d[0]
        other = next((x for x, j in d[1:] if vals[j] != vals[i]), None)
        if other is None or other - best >= margin:
            return i
    return None


def bar_ocr(cam) -> str:
    """OCR of the side list's cursor bar alone, its white text made dark on white and enlarged three
    times: the whole frame's OCR returns nothing for "-7" on the bar (Color Phase, 2026-10-29)."""
    import tempfile
    from PIL import Image
    s, f = cam.read(), cam.frame
    g = screen._grey(f.image)[s.bar[0]:s.bar[1] + 1, 300:600]
    img = Image.fromarray(np.where(g > 170, 0, 255).astype(np.uint8))
    img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
    page = Image.new("L", (img.width + 120, img.height + 120), 255)
    page.paste(img, (60, 60))
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "bar.png"
        page.save(path)
        return ocr.text_in(ocr.read([path])[path], (0, 0, page.width, page.height)).strip(" •o")


def side_top(vals: list) -> int:
    """Index of the value at the top of the shown list: the one after the lap's wrap."""
    n, nums = len(vals), [signed(v) for v in vals]
    known = [round(nums[i + 1] - nums[i], 4) for i in range(n - 1) if nums[i] is not None and nums[i + 1] is not None]
    if not known:
        return 0
    step = collections.Counter(known).most_common(1)[0][0]
    return next(((j + 1) % n for j in range(n) if nums[j] is not None and nums[(j + 1) % n] is not None
                 and round(nums[(j + 1) % n] - nums[j], 4) != step), 0)


def from_neighbours(cam, vals: list) -> int | None:
    """The cursor's value from the rows above and below it, when each names exactly one value: the
    one after the row above, the one before the row below (the shown list does not wrap)."""
    s, f = cam.read(), cam.frame
    lines = ocr.read([f.path])[f.path]
    pitch = s.bar[1] - s.bar[0] + 4
    n, top = len(vals), side_top(vals)
    guesses = set()
    if s.bar[0] - pitch > 80:
        a = ocr.text_in(lines, (290, s.bar[0] - pitch, 612, s.bar[0] - 3)).strip(" •o")
        hits = [j for j, v in enumerate(vals) if option_key(v) == option_key(a)]
        if len(hits) == 1 and (hits[0] + 1) % n != top:
            guesses.add((hits[0] + 1) % n)
    if s.bar[1] + pitch < 392:
        b = ocr.text_in(lines, (290, s.bar[1] + 3, 612, s.bar[1] + pitch)).strip(" •o")
        hits = [j for j, v in enumerate(vals) if option_key(v) == option_key(b)]
        if len(hits) == 1 and hits[0] != top:
            guesses.add((hits[0] - 1) % n)
    return guesses.pop() if len(guesses) == 1 else None


def by_neighbours(cam, vals: list, hits: list) -> list:
    """Between values OCR cannot tell apart ("5": +5 or -5), the rows above and below the cursor
    decide: the list shows the lap in Down order from its top (the value after the wrap), so +5
    has nothing above and +4 below, -5 has -4 above and nothing below."""
    s, f = cam.read(), cam.frame
    lines = ocr.read([f.path])[f.path]
    pitch = s.bar[1] - s.bar[0] + 4
    above = ocr.text_in(lines, (290, s.bar[0] - pitch, 612, s.bar[0] - 3)).strip(" •o") if s.bar[0] - pitch > 80 else ""
    below = ocr.text_in(lines, (290, s.bar[1] + 3, 612, s.bar[1] + pitch)).strip(" •o") if s.bar[1] + pitch < 392 else ""
    n = len(vals)
    nums = [signed(v) for v in vals]
    step = collections.Counter(round(nums[i + 1] - nums[i], 4) for i in range(n - 1)
                               if nums[i] is not None and nums[i + 1] is not None).most_common(1)[0][0]
    top = next(((j + 1) % n for j in range(n) if nums[j] is not None and nums[(j + 1) % n] is not None
                and round(nums[(j + 1) % n] - nums[j], 4) != step), 0)

    def fits(text, i):
        if i is None:
            return not text
        return bool(text) and signed(text) is not None and abs(signed(text)) == abs(nums[i])

    score = {i: fits(above, None if i == top else (i - 1) % n) + fits(below, None if (i + 1) % n == top else (i + 1) % n)
             for i in hits}
    best = max(score.values())
    return [i for i in hits if score[i] == best]


def prove_side_row(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    """A PP side list: its sampled values (or every value, for text), then back to the value it opened
    on. Its own base is downloaded first: opening the PP1 panel committed PP1 as the Picture Profile."""
    path, name, vals = job["path"], " > ".join(job["path"]), job["values"]
    n = len(vals)
    row_place = place(cam)
    base_path = link.download(f"{path[-1]}-base")
    after_download(cam, time.monotonic())
    to_row(cam, path, top, row_place)
    base = camset.read(base_path)
    last, order, c, prev = base_path, None, None, None
    while True:
        if order is not None:
            to_row(cam, path, top, row_place)
            if not same_place(place(cam), row_place):
                raise Failed(f"{name}: back at the row, the page or cursor row is not the one proved before")
        cam.press("right")
        if cam.read().kind != "sidelist":
            if order is None:                   # the first opening: the row may be refused outright
                refuse_or_fail(cam, name, "not a side list")
            raise Failed(f"{name}: Right opened {cam.read().kind}, not a side list")
        cur = side_index(cam, job)
        if cur is None:
            raise Failed(f"{name}: could not tell which value the side list opened on ({side_text(cam)!r})")
        if order is None:
            c = cur
            plan = job["plan"]
            if SPREAD and len(plan) > 3:                    # a long text list: its first, middle and last
                plan = sorted({0, len(vals) // 2, len(vals) - 1})
            order = [s for s in plan if s != c] + [c]
            print(f"{name}: opened on {vals[c]!r}; proving {[vals[s] for s in order]}", flush=True)
        elif cur != prev:
            raise Failed(f"{name}: the side list opened on {vals[cur]!r}, the last OK chose {vals[prev]!r}")
        k = order.pop(0)
        move_to(cam, cur, k, n, "sidelist")
        if side_index(cam, job) != k:
            raise Failed(f"{name}: the cursor is not on {vals[k]!r} ({side_text(cam)!r})")
        chosen, shown, seen_vlm = cam.frame.path.name, side_text(cam), vlm_option(cam)
        cam.press("enter")
        s = cam.read()
        notice, refused = None, False
        if s.kind == "notice":
            text_n = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
            if safety.confirmation(text_n):
                raise Failed(f"{name}: after OK a confirmation came up ({cam.frame.path.name})")
            # "not available as follows Gamma Movie": the value is refused and stays (Color Mode
            # BT.2020 needs an HLG gamma, 2026-10-29)
            refused = bool(re.search(r"not available|invalid", text_n, re.I))
            notice = {"text": text_n, "frame": cam.frame.path.name}
            print(f"   {'refused' if refused else 'notice after OK'}: {text_n[:90]!r}", flush=True)
            cam.press("menu")
        elif not same_place(place(cam), row_place):
            raise Failed(f"{name}: after OK the screen is {s.kind} ({cam.frame.path.name}), not the row")
        dat = link.download(f"{path[-1]}-{k}")
        done = time.monotonic()
        changes = camset.diff(base, camset.read(dat))
        rec = {"path": path, "kind": "sidelist", "index": k, "label": vals[k], "shown": shown, "chosen_frame": chosen, "vlm": seen_vlm,
               "row_frame": cam.frame.path.name, "dat": dat.name, "base": base_path.name, "notice": notice,
               "changes": changes_of(changes),
               "sampled": job["plan"] != list(range(n)), "applied": not refused}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        brief = ", ".join(f"{ch.key} {ch.before!r}->{ch.after!r}" for ch in changes[:6]) or "no change"
        print(f"   {vals[k]!r:24s} {brief}{' ...' if len(changes) > 6 else ''}", flush=True)
        last, prev = dat, (cur if refused else k)
        after_download(cam, done)
        if k == c:
            if changes:
                raise Failed(f"{name}: back on its value, {len(changes)} records still differ")
            break
    to_row(cam, path, top, row_place)
    return last
