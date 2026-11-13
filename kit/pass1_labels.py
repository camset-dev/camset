"""Read the label of every option pass 1 walked, from the saved frames, off the camera loop.

    .venv/bin/python kit/pass1_labels.py [kit2_pass1]          # a run in the camera's runs/<model>_fw<fw>/, or a path

For each row in <run>/rows.jsonl with option frames (lists, carousels, checklists, grids, number
fields), reads the text under the cursor with Apple OCR, cropped where the pixel reader puts the
cursor (primary: the VLM took the saved radio item for the highlighted one, 2026-10-28), and asks
vLLM (8 in parallel; cached by image) the same question as a second opinion ("agreed"). Writes
<run>/options.jsonl: one line per option with its row path, index, frame and both readings.
"""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import jsonl, ocr, paths, screen  # noqa: E402
from camkit.frames import load  # noqa: E402
from camkit.vlm import PROMPTS, make_reader, readers, role  # noqa: E402
from runner import OcrUnavailable, read_frames  # noqa: E402
from page_model import same_text  # noqa: E402


def rows_with_frames(rows, path=()):
    """Every walked row with option frames: rows, submenu rows, and inside carousels the panels
    opened from an option (a submenu's rows, or a grid/look panel's own frames)."""
    for r in rows:
        here = path + (r.get("label") or f"#{r.get('slot')}",)
        if r.get("frames"):
            yield here, r
        yield from rows_with_frames(r.get("submenu") or [], here)
        for k, det in (r.get("details") or {}).items():
            opt = here + (f"option {k}",)
            if det.get("frames"):
                yield opt, {"kind": det.get("panel"), "frames": det["frames"]}
            yield from rows_with_frames(det.get("rows") or [], opt)


def main():
    run = paths.run_path(sys.argv[1] if len(sys.argv) > 1 else "kit2_pass1")
    shots = run / "shots"
    if not (run / "rows.jsonl").exists():          # nothing to read: never an empty options.jsonl over the old one
        sys.exit(f"{run}: no rows.jsonl (kit/crawl_run.py writes it); nothing read, options.jsonl left as it is")
    rows = jsonl.read(run / "rows.jsonl")
    jobs = []
    for path, r in rows_with_frames(rows, ()):
        frames = r["frames"]
        if frames and isinstance(frames[0], list):              # fields / grid: one list per field or row
            for fi, fl in enumerate(frames):
                for k, fr in enumerate(fl):
                    if fr:
                        jobs.append((path, r["kind"], (fi, k), fr))
        else:
            for k, fr in enumerate(frames):
                if fr:
                    jobs.append((path, r["kind"], k, fr))
    readers(stop=True)                        # none listed: its sentence, before any frame is read
    print(f"{len(jobs)} option frames to read", flush=True)
    cfg = role("second")
    reader = make_reader(cfg)
    # one torn frame must not end a batch of thousands, nor pass for a frame without text: it is named, its OCR
    # reading left empty with the reason beside it ("ocr_unread"), and it never agrees, so pass1_map lists it for review
    try:
        ocr_lines, unread = read_frames([shots / fr for *_, fr in jobs])
    except OcrUnavailable as e:                     # the engine, not a frame: options.jsonl left as it is
        sys.exit(f"{e}; nothing read, {run / 'options.jsonl'} left as it is")
    for p, why in unread.items():
        print(f"not read by OCR: {p.name}: {why}", flush=True)

    def count_stars(fr):
        f = load(shots / fr)
        return screen.count_stars(f.image, screen.read(f).bar)

    def box_stars(fr):
        f = load(shots / fr)
        return screen.box_stars(f.image, screen.read(f))

    def cursor_text(fr):
        """OCR of what the cursor is on, located by the pixel reader: the orange bar (lists, checklists,
        side lists), the orange line under a carousel's title, each number field's box."""
        s = screen.read(load(shots / fr))
        lines = ocr_lines.get(shots / fr)
        if lines is None:                           # not read (unread): no reading, which is not "no text"
            return ""
        if s.kind in ("list", "checklist", "sidelist", "submenu") and s.bar:
            # inside the panel only: past a popup's edge the dimmed menu behind shows through
            x0, x1 = {"list": (110, 556), "sidelist": (290, 612), "submenu": (55, 636)}.get(s.kind, (50, 612))
            if s.kind == "checklist" and s.boxes and s.boxes[0][1] - s.boxes[0][0] < 400:
                x0, x1 = max(x0, s.boxes[0][0] + 50), min(x1, s.boxes[0][1])     # one of two columns
            pad = 4 if s.kind == "sidelist" else -2           # side lists: OCR cut words at a tight crop
            return ocr.text_in(lines, (x0, s.bar[0] - pad, x1, s.bar[1] + pad)).strip(" •o")
        if s.kind == "dialog":
            return ocr.text_in(lines, (110, 60, 636, 112)).strip()
        if s.kind == "checkgrid":
            return ocr.text_in(lines, (0, 60, 640, 118)).strip()
        if s.kind == "fields" and s.boxes and s.bar:
            # every field's value, left to right (the active one is s.field)
            return " | ".join(ocr.text_in(lines, (x0 + 2, s.bar[0] + 2, x1 - 2, s.bar[1] - 2)).strip() for x0, x1 in s.boxes)
        return ocr.text_in(lines, (0, 52, 640, 420)).strip()

    def one(job):
        path, kind, idx, fr = job
        prompt = PROMPTS["fields" if kind == "fields" else "option"]
        try:
            v = reader.ask((shots / fr).read_bytes(), prompt)
        except Exception as e:
            v = {"_error": str(e)[:100]}
        o = cursor_text(fr)
        stars = count_stars(fr) if o.lower().startswith("rating") and kind in ("list", "checklist") else None
        if stars:
            o = "Rating (" + "★" * stars + ")"
        elif kind == "checklist" and not re.search(r"[A-Za-z0-9]", o):
            stars = box_stars(fr)                   # a box with only a star cluster (Rating Set(Custom Key))
            if stars:
                o = "★" * stars
        vsel = str(v.get("selected") or "") if isinstance(v, dict) else ""
        if kind == "fields" and isinstance(v, dict) and isinstance(v.get("fields"), list):
            vsel = " | ".join(str(x) for x in v["fields"])
        agree = (bool(o) and bool(vsel) and same_text(o, vsel)) or bool(stars)
        why = unread.get(shots / fr)
        return {"path": list(path), "kind": kind, "index": idx, "frame": fr, "label": o or vsel,
                "agreed": agree and why is None, "vlm": v, "ocr": o[:200], **({"ocr_unread": why} if why else {})}
    with ThreadPoolExecutor(cfg.get("parallel", 8)) as ex, open(run / "options.jsonl", "w", encoding="utf-8", newline="\n") as out:
        for n, rec in enumerate(ex.map(one, jobs), 1):
            out.write(json.dumps(rec) + "\n")
            if n % 100 == 0:
                print(f"  {n}/{len(jobs)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
