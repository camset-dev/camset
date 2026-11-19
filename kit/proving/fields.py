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
from .screens import ask_second, later, option_key, place, refuse_or_fail, same_place, settled, vlm_option


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


class Limits:
    """What each of a row's fields (or boxes) writes, where a choice in one can move another: ISO Range Limit's lower and
    upper limit, ISO AUTO's Minimum and Maximum (the camera keeps them in order: an upper limit chosen below the lower
    pulls the lower down to it, a lower chosen above the upper pushes the upper up, and the moved one stays; 2026-11-18).
    A field's own records are those three of every four lines of it that changed anything changed, each to as many
    values as half the lines that changed it, two at least (a value the other field left behind keeps one value or
    two: kit2_pass2's ISO AUTO Maximum lines all carried the Minimum's, 2026-11-18), and that are not another field's
    own so (`history`, (field, changes) of the lines already in the proofs file, then this run's lines: learn). The
    live readouts the definition marks "view only" (`ignore`: ISO in use) are no field's."""

    def __init__(self, n: int, history=(), ignore=(), copies=None):
        self.lines = dict.fromkeys(range(n), 0)
        self.values = {k: {} for k in range(n)}         # field -> record -> the values its lines wrote there
        self.ignore, self.copies = set(ignore), copies or {}
        for k, changes in history:
            self.learn(k, changes)

    def learn(self, k: int, changes) -> None:
        """One line of field k that applied: its changes ({"key", "after"}), those named the other's left out first."""
        wrote = {c["key"]: json.dumps(c.get("after")) for c in changes if c["key"] not in self.ignore}
        if not wrote or k not in self.lines:
            return
        self.lines[k] += 1
        for key, v in wrote.items():
            self.values[k].setdefault(key, []).append(v)

    def _mine(self, k: int) -> set:
        n = self.lines.get(k, 0)
        return {key for key, vs in self.values.get(k, {}).items()
                if 4 * len(vs) >= 3 * n and (len(vs) < 2 or len(set(vs)) >= max(2, (len(vs) + 1) // 2))}

    def own(self, k: int) -> set:
        """Field k's own records, each with its copies (`copies`: record -> its setting's records, the definition's)."""
        others = set().union(*(self._mine(j) for j in self.lines if j != k))
        mine = self._mine(k) - others
        return mine.union(*(self.copies.get(key, ()) for key in mine)) - self.ignore

    def other(self, k: int, keys) -> dict:
        """{other field: its records among `keys`}, the keys a line of field k changed, by each other field's own records
        as known."""
        keys = set(keys)
        return {j: keys & self.own(j) for j in self.lines if j != k and keys & self.own(j)}

    def unknown(self, k: int, keys) -> set:
        """The records among `keys` that are not field k's own, where field k's own are known and no other field's are
        yet: another field's only where the screen shows that one moved (prove_fields_row)."""
        if not self.own(k) or any(self.own(j) for j in self.lines if j != k):
            return set()
        return set(keys) - self.own(k) - self.ignore


def _settings() -> list:
    try:
        from runner import definition
        return definition().get("settings") or []
    except Exception:            # noqa: BLE001 - no definition to read: nothing known of the records
        return []


def readouts() -> set:
    """The records the camera's definition marks "view only" (live readouts, as pass2_report takes them), each copy too:
    Limits leaves them out. Empty with no definition."""
    return {k.split("[")[0] for s in _settings() if "view only" in (s.get("note") or "").lower()
            for k in [s.get("key"), *(s.get("copies") or [])] if k}


def copies() -> dict:
    """{record: the records of its setting (it and its copies)} as the camera's definition has them: a copy moves with
    its record (Limits.own). Empty with no definition."""
    out = {}
    for s in _settings():
        keys = frozenset(k.split("[")[0] for k in [s.get("key"), *(s.get("copies") or [])] if k)
        for k in keys:
            out[k] = out.get(k, frozenset()) | keys
    return out


def field_history(run, path, context) -> list:
    """(field, changes) of each applied line of the row's number fields in the run's proofs file made in the same state
    (`context`), without the changes it names as another field's (moved_other): what Limits learns from first."""
    try:
        from camkit import jsonl
        lines = jsonl.read(Path(run.dir) / "proofs.jsonl")
    except Exception:            # noqa: BLE001 - no proofs file, or none readable: nothing learned before
        return []
    out = []
    for r in lines:
        if r.get("path") == list(path) and r.get("kind") == "fields" and r.get("applied") is True \
                and r.get("context") == context and r.get("changes") and isinstance(r.get("index"), list):
            other = {c["key"] for c in (r.get("moved_other") or {}).get("changes") or []}
            out.append((r["index"][0], [c for c in r["changes"] if c["key"] not in other]))
    return out


def step_of(fld: dict, text) -> int | None:
    """The step of the field's values a reading names (same_value), the first, or None."""
    return next((i for i, v in enumerate(fld["values"]) if same_value(v, text)), None)


def prove_fields_row(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    """Number fields, one field at a time: the sampled values (lowest, middle, highest), then back to
    the value it opened on, whose diff must be empty. Each value: Right into the fields, Right to the
    field, Up/Down the short way round (fields wrap), check the value, OK, download, diff. job["only_field"]: that field
    alone (prove_run --field), the others left as they are.

    A proof is written once the next opening shows what the camera kept: OK on a value past the
    limit keeps the old one (BULB Exposure Time "9 | 6 | 0" kept 560 s, 2026-10-29). Such a proof
    says "applied": false with the value kept, and the field carries on from there.

    A choice that moved another field (ISO Range Limit: a limit chosen past the other moves it, and the moved one stays;
    Limits) is said on its line, "moved_other": {"field": the other field, "changes": its records' changes}, which the
    report leaves out of the choice's own records; the other field is then put back on the value it showed when the row
    opened, chosen through the menu (put_back), and checked: no record of it may differ from the start after that, so no
    later line carries the leftover. A value the menu cannot bring back (a factory value no option of the list writes)
    ends the row there, said in plain words, before another line is written; the start file goes back on as after any
    failed row. Before 2026-11-18 the other limit's change was carried on every later line and the closing proof failed."""
    path, name = job["path"], " > ".join(job["path"])
    base = camset.read(base_path)
    row_place = place(cam)
    last, first, held = base_path, True, None
    fields = job["fields"]
    limits = Limits(len(fields), field_history(run, path, getattr(out, "context", None)), readouts(), copies())
    start = {}                    # each field's step as the row opened (its value on the screen then)

    def write(rec, applied, kept=None):
        rec.update(applied=applied, kept=kept)
        out.write(json.dumps(rec) + "\n")
        out.flush()

    def open_at(k):
        """The row's fields open at field k: back at the row (but the first time), Right, Right to field k."""
        nonlocal first
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

    def step_to(k, at, t):
        """Field k stepped from step `at` to step t; Failed where it does not show t after three laps."""
        fld = fields[k]
        values, n = fld["values"], len(fld["values"])
        inc = job.get("inc", "up")
        dec = "down" if inc == "up" else "up"
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

    def ok() -> dict | None:
        """OK on the fields, the screen after it read: a confirmation fails the row, a notice is kept and closed with
        MENU; anything but the row or the shooting screen fails it. Returns the notice, or None."""
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
        return notice

    def moved_on_screen(k, now) -> list:
        """The other fields the screen shows off the value they showed as the row opened (each read as one of its
        values; one not so read says nothing)."""
        out_ = []
        for j, fj in enumerate(fields):
            if j == k or start.get(j) is None or j >= len(now):
                continue
            s = step_of(fj, now[j])
            if s is not None and not same_value(fj["values"][s], fj["values"][start[j]]):
                out_.append(j)
        return out_

    def put_back(k, t, j, keys):
        """Field j, which the choice of step t in field k moved, back on its value as the row opened, chosen through the
        menu, OK, a download; Failed in plain words where a record of it still differs from the start (keys: its
        records the choice changed, with its own as Limits knows them)."""
        a, fj = start.get(j), fields[j]
        moved = f"choosing {fields[k]['values'][t]!r} in field {k} also moved field {j}"
        if a is None:
            raise Failed(f"{name}: {moved}, and the value field {j} showed as the row opened could not be read, so it "
                         "cannot be put back by a menu choice: the row ends here rather than write proofs with that "
                         "leftover, and the start file goes back on")
        cam.cancel_to_menu()                       # out of the fields at field k, nothing applied
        open_at(j)
        at = field_at(cam, j, fj)
        if at is None:
            raise Failed(f"{name}: field {j} shows {field_values(cam)!r}, not one of pass 1's values")
        step_to(j, at, a)
        ok()
        dat = link.download(f"{path[-1]}-{j}-{a}-back")
        done = time.monotonic()
        left = sorted({ch.key for ch in camset.diff(base, camset.read(dat))} & (set(keys) | limits.own(j)))
        after_download(cam, done)
        if left:
            raise Failed(f"{name}: {moved}, and choosing its start value {fj['values'][a]!r} again through the menu does "
                         f"not bring back what the start file holds in {', '.join(left)} ({dat.name}): a value the menu "
                         "cannot choose again (a factory value?). The row ends here rather than write proofs with that "
                         f"leftover, and the start file goes back on; prove field {k} from a start where field {j} holds "
                         "a value its list offers")
        print(f"   field {j} put back on {fj['values'][a]!r} through the menu, as the row opened ({dat.name})", flush=True)
        return dat

    try:
        for k, fld in enumerate(fields):
            if job.get("only_field") is not None and k != job["only_field"]:
                continue
            values, n = fld["values"], len(fld["values"])
            order, c, prev = None, None, None
            while True:
                open_at(k)
                cur = field_at(cam, k, fld)
                if cur is None:
                    raise Failed(f"{name}: field {k} shows {field_values(cam)!r}, not one of pass 1's values")
                now = field_values(cam) if len(fields) > 1 else []
                if not start:
                    start.update({j: step_of(fj, now[j]) if j < len(now) else None for j, fj in enumerate(fields)})
                    start[k] = cur
                if order is None:
                    c = cur
                    order = [s for s in fld["plan"] if s != c] + [c]
                    print(f"{name} field {k}: opened on {values[c]!r}; proving {[values[s] for s in order]}", flush=True)
                elif held is not None:
                    rec, held = held, None
                    keys = {ch["key"] for ch in rec["changes"]}
                    other = limits.other(k, keys) if cur == prev else {}
                    seen_moved = moved_on_screen(k, now) if cur == prev and not other else []
                    if seen_moved and not any(limits.own(j) for j in seen_moved):
                        # the screen shows another field moved, whose records no line has told apart yet: those not
                        # this field's own, once its own are known
                        rest = limits.unknown(k, keys)
                        if not rest:
                            raise Failed(f"{name}: choosing {values[prev]!r} in field {k} also moved field "
                                         f"{seen_moved[0]} on the screen, and no proof has told the fields' records "
                                         f"apart yet ({rec['dat']}): the row ends here rather than write a proof that "
                                         f"may carry the other field's change; prove field {k} alone (prove_run --field "
                                         f"{k}) from a start where its first choice moves nothing else")
                        other = {seen_moved[0]: rest}
                    if len(other) > 1:
                        raise Failed(f"{name}: choosing {values[prev]!r} in field {k} moved {len(other)} other fields "
                                     f"({rec['dat']}): one moved field is put back, never several; the row ends here")
                    if other:
                        (j, theirs), = other.items()
                        rec["moved_other"] = {"field": j, "changes": [ch for ch in rec["changes"] if ch["key"] in theirs]}
                        print(f"   field {j} moved with it: {', '.join(sorted(theirs))}", flush=True)
                    if cur == prev:
                        write(rec, True)
                        theirs_all = set().union(*other.values())
                        limits.learn(k, [ch for ch in rec["changes"] if ch["key"] not in theirs_all])
                    else:
                        write(rec, False, values[cur])
                        print(f"   the camera kept {values[cur]!r}, not {values[prev]!r} (past a limit?)", flush=True)
                    if other:
                        last = put_back(k, prev, j, theirs)
                        continue                   # opened again at field k, its next value from there
                t = order.pop(0)
                step_to(k, cur, t)
                chosen, shown, seen_vlm = cam.frame.path.name, " | ".join(field_values(cam)), later(vlm_option, cam)
                notice = ok()
                back = cam.frame.path.name
                dat = link.download(f"{path[-1]}-{k}-{t}")
                done = time.monotonic()
                changes = camset.diff(base, camset.read(dat))
                held = {"path": path, "kind": "fields", "index": [k, t], "label": fld["labels"][t], "value": values[t],
                        "shown": shown, "chosen_frame": chosen, "vlm": settled(seen_vlm), "row_frame": back, "dat": dat.name,
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
