"""Score the pixel reader on archived screenshots against labels inferred from OCR text.

    .venv/bin/python kit/tests/score_screen.py [SHOTS_DIR] [--every N] [--sample K]

OCR labels are weak (inferred from text such as "MENU Close" or "n/65"), so disagreements are
listed for a human look rather than counted as errors outright. A frame that cannot be loaded, or that the OCR helper
cannot read (camkit.ocr.read raises, naming it), is listed with why and left out of the counts: never scored as a
frame with no text, and never the end of the run.
"""
import argparse
import random
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ocr, paths, screen  # noqa: E402
from camkit.frames import load  # noqa: E402


def ocr_label(lines) -> str:
    top = ocr.text_in(lines, (0, 0, 640, 45))
    foot = ocr.text_in(lines, (0, 425, 640, 480))
    allt = " ".join(ln.text for ln in lines)
    if re.search(r"not available|cannot be|invalid|not attached|please attach", allt, re.I):
        return "notice"
    if re.search(r"\d+\s*/\s*\d+", top) and re.search(r"close", foot, re.I):
        return "menu"
    if re.search(r"cancel", foot, re.I) and re.search(r"ok", foot, re.I):
        return "dialog-like"
    return "?"


OCR_FAILS = (RuntimeError, OSError, subprocess.CalledProcessError)          # what camkit.ocr.read raises for a frame


def ocr_each(frames: list) -> tuple[dict, dict]:
    """({frame: its OCR lines}, {frame: why it was not read}): the frames read in one batch, and when the helper
    cannot read one of them, each on its own (the ones it read are cached, so only the failures cost a second call)."""
    try:
        return ocr.read(frames), {}
    except OCR_FAILS:
        pass
    got, failed = {}, {}
    for f in frames:
        try:
            got.update(ocr.read([f]))
        except OCR_FAILS as e:
            failed[f] = str(e)
    return got, failed


def say_unread(what: str, failed: dict):
    if failed:
        print(f"{len(failed)} frames not read by {what}, left out of the counts:")
        for f, why in list(failed.items())[:10]:
            print(f"  {Path(f).name}: {why}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shots", nargs="?", default=str(paths.a1ii_root() / "explore_stills" / "shots"),
                    help="frames (default: the a1 II's old explorer run, runs/ILCE-1M2_fw4.00/explore_stills/shots)")
    ap.add_argument("--every", type=int, default=10)
    ap.add_argument("--sample", type=int, default=200)
    a = ap.parse_args()
    files = sorted(Path(a.shots).glob("*.png"))[:: a.every]
    kinds, reads, unloaded = Counter(), {}, {}
    for f in files:
        try:
            s = screen.read(load(f))
        except Exception as e:          # noqa: BLE001  a frame the reader cannot open: said, not the end of the run
            unloaded[f] = f"{type(e).__name__}: {e}"
            continue
        kinds[s.kind] += 1
        reads[f] = s
    print(f"{len(reads)} frames:", dict(kinds))
    say_unread("the pixel reader", unloaded)

    random.seed(1)
    sample = random.sample(sorted(reads), min(a.sample, len(reads)))
    labels, unread = ocr_each(sample)
    say_unread("the OCR", unread)
    pairs = Counter()
    odd = []
    for f in sample:
        if f not in labels:
            continue
        o = ocr_label(labels[f])
        k = reads[f].kind
        pairs[(k, o)] += 1
        if (o == "menu" and k != "menu") or (o == "notice" and k not in ("notice", "unknown")) or \
           (k == "menu" and o not in ("menu", "?")):
            odd.append((f.name, k, o))
    print("pixel kind  vs  OCR label:")
    for (k, o), n in sorted(pairs.items(), key=lambda x: -x[1]):
        print(f"  {k:9s} {o:12s} {n}")
    print("to look at:", odd[:20])


if __name__ == "__main__":
    main()
