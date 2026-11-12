"""Number fields: every field's value read (OCR, the vision reader where OCR left a box unread, the second engine,
pass 1's pictures for a lone "0"), and the prover that steps one field at a time to its sampled values and back."""
import json
import os
import re
import time
from pathlib import Path

import numpy as np

from camkit import camset, ocr, safety, screen
from camkit.frames import load
from camkit.vlm import PROMPTS
from runner import changes_of

from .base import Failed, frame_file, number
from .nav import after_download, to_row
from .screens import ask_second, option_key, place, refuse_or_fail, same_place, vlm_option


def field_values(cam) -> list:
    """OCR of every number field's value, left to right (pass 1's crop); a field the engine skipped is read again
    (field_again)."""
    s, f = cam.read(), cam.frame
    if s.kind != "fields" or not s.boxes or not s.bar:
        return []
    lines = ocr.read([f.path])[f.path]
    boxes = [(x0 + 2, s.bar[0] + 2, x1 - 2, s.bar[1] - 2) for x0, x1 in s.boxes]
    out = [ocr.text_in(lines, box).strip() for box in boxes]
    if not all(out):
        # the vision reader decides where OCR left a box unread (the owner, 2026-11-06: Apple Vision is the one that
        # misses, the reader has been right every time); the second engine and an enlarged crop when no reader answers
        again = fields_by_reader(f)
        if len(again) == len(out):
            out = [a or b for a, b in zip(out, again, strict=True)]
    return [a or field_again(f, box) for a, box in zip(out, boxes, strict=True)]


def fields_by_reader(f) -> list:
    """The vision reader's reading of every number box, left to right, units dropped ("11 sec" -> "11"); [] when it
    cannot be asked or answers in another shape."""
    try:
        v = ask_second(f.path.read_bytes(), PROMPTS["fields"], timeout=60)
    except Exception:
        return []
    vals = v.get("fields") if isinstance(v, dict) else None
    if not isinstance(vals, list):
        return []
    out = []
    for x in vals:
        m = re.search(r"[+-]?\d+(?:\.\d+)?", str(x))
        out.append(m.group(0) if m else str(x).strip())
    return out


def field_again(f, box) -> str:
    """A field's number neither the first engine nor the reader gave (Apple Vision skipped "11 sec" and "0 min" on a
    frame it read "10" on, 2026-11-06, and a lone "0" often): the second engine on the same frame, else the first
    engine on the field alone at three times its size. "" when neither reads it (field_at then tries the pass-1
    pictures)."""
    eng = ocr.second()
    if eng:
        text = ocr.text_in(ocr.read([f.path], eng=eng)[f.path], box).strip()
        if text:
            return text
    import tempfile
    from PIL import Image
    x0, y0, x1, y1 = box
    crop = Image.fromarray(f.image).crop((x0 - 2, y0 - 2, x1 + 2, y1 + 2))
    path = Path(tempfile.gettempdir()) / f"camkit_field_{os.getpid()}.png"      # one per process
    crop.resize((crop.width * 3, crop.height * 3)).save(path)
    try:
        lines = ocr.read([path])[path]
    finally:
        path.unlink(missing_ok=True)
    return " ".join(ln.text for ln in lines).strip()


def same_value(a: str, b: str) -> bool:
    na, nb = number(a), number(b)
    return na == nb if na is not None and nb is not None else option_key(a) == option_key(b)


_TEMPLATES: dict = {}


def box_bits(frame, s, k: int):
    """Field k's box as a small binary picture (its digits)."""
    x0, x1 = s.boxes[k]
    return np.unpackbits(screen._binarize_small(screen._grey(frame.image),
                                                (x0 + 2, s.bar[0] + 2, x1 - 2, s.bar[1] - 2), (32, 12), 150))


def templates(fld: dict, k: int) -> list:
    """Field k's box in pass 1's frame of each step (None where the frame is missing)."""
    key = (id(fld), k)
    if key not in _TEMPLATES:
        out = []
        for fr in fld.get("frames") or []:
            path = frame_file(fld.get("map_path"), fr)
            s = screen.read(load(path)) if path else None
            ok = s is not None and s.kind == "fields" and s.field == k and len(s.boxes) > k and s.bar
            out.append(box_bits(load(path), s, k) if ok else None)
        _TEMPLATES[key] = out
    return _TEMPLATES[key]


def match_box(cam, fld: dict, k: int, margin: int = 5) -> int | None:
    """The step whose pass-1 picture of field k is closest to the box on screen, when it is clearly
    closer than any step showing another value (OCR returns nothing for a lone "0", 2026-10-29)."""
    s = cam.read()
    if s.kind != "fields" or len(s.boxes) <= k or not s.bar:
        return None
    live = box_bits(cam.frame, s, k)
    d = sorted((int(np.count_nonzero(live != tp)), i) for i, tp in enumerate(templates(fld, k))
               if tp is not None and tp.shape == live.shape)
    if not d:
        return None
    best, i = d[0]
    other = next((x for x, j in d[1:] if not same_value(fld["values"][j], fld["values"][i])), None)
    return i if other is None or other - best >= margin else None


def field_at(cam, k: int, fld: dict) -> int | None:
    """Which step of field k's values is on screen: OCR, else the pass-1 pictures (the first match;
    looked at twice: OCR can catch a frame mid-redraw)."""
    values = fld["values"]
    for _ in range(2):
        vals = field_values(cam)
        if k < len(vals):
            hits = [i for i, v in enumerate(values) if same_value(v, vals[k])]
            if hits:
                return hits[0]
        i = match_box(cam, fld, k)
        if i is not None:
            return next(j for j, v in enumerate(values) if same_value(v, values[i]))
        time.sleep(0.4)
        cam.refresh("reread")
    return None


def prove_fields_row(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    """Number fields, one field at a time: the sampled values (lowest, middle, highest), then back to
    the value it opened on, whose diff must be empty. Each value: Right into the fields, Right to the
    field, Up/Down the short way round (fields wrap), check the value, OK, download, diff.

    A proof is written once the next opening shows what the camera kept: OK on a value past the
    limit keeps the old one (BULB Exposure Time "9 | 6 | 0" kept 560 s, 2026-10-29). Such a proof
    says "applied": false with the value kept, and the field carries on from there."""
    path, name = job["path"], " > ".join(job["path"])
    base = camset.read(base_path)
    row_place = place(cam)
    last, first, held = base_path, True, None

    def write(rec, applied, kept=None):
        rec.update(applied=applied, kept=kept)
        out.write(json.dumps(rec) + "\n")
        out.flush()

    try:
        for k, fld in enumerate(job["fields"]):
            values, n = fld["values"], len(fld["values"])
            order, c, prev = None, None, None
            while True:
                if not first:
                    to_row(cam, path, top, row_place)
                    if not same_place(place(cam), row_place):
                        raise Failed(f"{name}: back at the row, the page or cursor row is not the one proved before")
                first = False
                cam.press("right")
                if cam.read().kind != "fields":
                    refuse_or_fail(cam, name, "not number fields")
                if cam.read().field != 0:
                    raise Failed(f"{name}: the fields opened on field {cam.read().field}, not the first")
                for _ in range(k):
                    cam.press("right")
                if cam.read().kind != "fields" or cam.read().field != k:
                    raise Failed(f"{name}: Right did not reach field {k}")
                cur = field_at(cam, k, fld)
                if cur is None:
                    raise Failed(f"{name}: field {k} shows {field_values(cam)!r}, not one of pass 1's values")
                if order is None:
                    c = cur
                    order = [s for s in fld["plan"] if s != c] + [c]
                    print(f"{name} field {k}: opened on {values[c]!r}; proving {[values[s] for s in order]}", flush=True)
                elif held is not None:
                    if cur == prev:
                        write(held, True)
                    else:
                        write(held, False, values[cur])
                        print(f"   the camera kept {values[cur]!r}, not {values[prev]!r} (past a limit?)", flush=True)
                    held = None
                t = order.pop(0)
                inc = job.get("inc", "up")
                dec = "down" if inc == "up" else "up"
                at = cur
                for _ in range(3):
                    # the way there, then where the field really is: a press the OSD image showed late (it froze for
                    # 3 to 7 s twice on 2026-11-06, the camera working on) leaves the field one step short or, once
                    # the picture catches up, one past; the next lap corrects it rather than failing the row
                    if job.get("wrap", True):
                        d = (t - at) % n
                        key, steps = (inc, d) if d <= n - d else (dec, n - d)
                    else:                                   # fields that stop at their ends
                        key, steps = (inc, t - at) if t >= at else (dec, at - t)
                    for _ in range(steps):
                        cam.press(key)
                        if cam.read().kind != "fields":
                            raise Failed(f"{name}: {key} in the fields left them ({cam.read().kind})")
                    at = field_at(cam, k, fld)
                    if at == t or at is None:
                        break
                    print(f"   field {k} shows {values[at]!r} after the move to {values[t]!r}: correcting", flush=True)
                if at != t:
                    raise Failed(f"{name}: field {k} shows {field_values(cam)!r}, not {values[t]!r}")
                chosen, shown, seen_vlm = cam.frame.path.name, " | ".join(field_values(cam)), vlm_option(cam)
                cam.press("enter")
                s = cam.read()
                notice = None
                if s.kind == "fields":
                    raise Failed(f"{name}: OK left the number fields open ({cam.frame.path.name})")
                if s.kind == "notice":
                    text_n = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
                    why = safety.confirmation(text_n)
                    if why:
                        raise Failed(f"{name}: after OK a confirmation came up ({why}; {cam.frame.path.name})")
                    notice = {"text": text_n, "frame": cam.frame.path.name}
                    print(f"   notice after OK: {text_n[:90]!r}", flush=True)
                    cam.press("menu")
                elif s.kind != "shooting" and not same_place(place(cam), row_place):
                    raise Failed(f"{name}: after OK the screen is {s.kind} ({cam.frame.path.name}), not the row")
                back = cam.frame.path.name
                dat = link.download(f"{path[-1]}-{k}-{t}")
                done = time.monotonic()
                changes = camset.diff(base, camset.read(dat))
                held = {"path": path, "kind": "fields", "index": [k, t], "label": fld["labels"][t], "value": values[t],
                        "shown": shown, "chosen_frame": chosen, "vlm": seen_vlm, "row_frame": back, "dat": dat.name,
                        "base": base_path.name, "notice": notice, "sampled": fld["plan"] != list(range(n)),
                        "changes": changes_of(changes)}
                brief = ", ".join(f"{ch.key} {ch.before!r}->{ch.after!r}" for ch in changes[:6]) or "no change"
                print(f"   field {k} = {values[t]!r:10s} {brief}{' ...' if len(changes) > 6 else ''}", flush=True)
                last, prev = dat, t
                after_download(cam, done)
                if t == c:
                    if changes:
                        raise Failed(f"{name}: field {k} back on its value, {len(changes)} records still differ")
                    write(held, True)              # nothing differs from the start: the value applied
                    held = None
                    break
        to_row(cam, path, top, row_place)
        return last
    finally:
        if held is not None:                       # never seen again: what applied is not known
            write(held, None)
