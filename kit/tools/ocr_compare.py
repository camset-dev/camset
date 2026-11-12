"""How well each OCR engine reads menu pages, measured against a scan's settled labels.

    .venv/bin/python kit/tools/ocr_compare.py kit2_page_scan kit2_page_scan_movie ...   # runs in the camera's runs/<model>_fw<fw>/

For each scan (its model.json from kit/page_model.py, where every label and value was settled by
two sources), each engine reads the first frame of every page through the same boxes page_model
uses. A row counts as read when the engine's text matches the settled text by page_model's rule.
Prints, per engine, labels and values read, seconds per frame, and the rows each engine misses
alone. Needs no camera.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ocr, paths  # noqa: E402
from camkit.screen import MENU_ROW_PITCH, MENU_ROW_TOP  # noqa: E402
from page_model import same_text  # noqa: E402

ENGINES = ("apple", "rapidocr")


def measure(run: Path, engine: str) -> tuple[dict, list]:
    model = json.loads((run / "model.json").read_text(encoding="utf-8"))
    frames = [run / "shots" / p["frame"] for p in model]
    t0 = time.monotonic()
    lines = ocr.read(frames, engine)
    secs = time.monotonic() - t0
    got = {"labels": 0, "labels_of": 0, "values": 0, "values_of": 0, "frames": len(frames), "secs": secs}
    misses = []
    for p, f in zip(model, frames, strict=True):          # one frame per page, made from the model
        for r in p["rows"]:
            y0 = MENU_ROW_TOP + MENU_ROW_PITCH * r["slot"]
            label = ocr.text_in(lines[f], (140, y0, 470, y0 + 52)).strip()
            value = ocr.text_in(lines[f], (470, y0, 640, y0 + 52)).strip()
            if r["label"]:
                got["labels_of"] += 1
                if same_text(label, r["label"]):
                    got["labels"] += 1
                else:
                    misses.append((run.name, p["page"], r["slot"], r["label"], label))
            if r["value"]:
                got["values_of"] += 1
                got["values"] += same_text(value, r["value"])
    return got, misses


def main():
    runs = [paths.run_path(a) for a in sys.argv[1:] or ["kit2_page_scan"]]
    total = {e: {} for e in ENGINES}
    missed = {e: set() for e in ENGINES}
    for run in runs:
        for e in ENGINES:
            got, misses = measure(run, e)
            for k, v in got.items():
                total[e][k] = total[e].get(k, 0) + v
            missed[e] |= set(misses)
            print(f"{run.name:28s} {e:9s} labels {got['labels']}/{got['labels_of']}  values {got['values']}/{got['values_of']}"
                  f"  {got['secs'] / max(got['frames'], 1):.2f} s/frame")
    print()
    for e in ENGINES:
        t = total[e]
        print(f"{e:9s} labels {t['labels']}/{t['labels_of']} ({100 * t['labels'] / max(t['labels_of'], 1):.1f}%)  "
              f"values {t['values']}/{t['values_of']} ({100 * t['values'] / max(t['values_of'], 1):.1f}%)")
    keys = {e: {m[:4] for m in missed[e]} for e in ENGINES}
    for e in ENGINES:
        other = [o for o in ENGINES if o != e][0]
        alone = sorted(m for m in missed[e] if m[:4] not in keys[other])
        print(f"\nmissed by {e} alone: {len(alone)}")
        for run, page, slot, want, got in alone[:15]:
            print(f"  {run} {page} row {slot}: {want!r} read {got!r}")


if __name__ == "__main__":
    main()
