"""The camera's memory of grey readings found wrong (proving.greyed: runs/<model>_fw<fw>/grey_misjudged.jsonl): which
rows the kit no longer enters on a reading no grey entry has measured, and the way to lift a mark.

    .venv/bin/python kit/tools/grey_memory.py --list
    .venv/bin/python kit/tools/grey_memory.py --measured "Drive Mode / Cont. Shooting" icon --why "calib_grey_looks: a greyed
        Hi+ read dim (frame 00042), the reading measured on a grey entry"

A mark is written by a prover when the camera refused an entry the kit's reading had read white (a carousel's lit column
icon, "icon"; a checklist item's band, "checklist"); from then on the provers refuse that row's entries on that reading,
in every run, before any press. --list prints the marks in force (and how many were lifted); --measured appends a
"measured" line for the row and the reading, with what measured it (`--why`, required: a calibration on a grey entry of
that row, a look that read it, the owner's word): the latest line for a row and a reading counts, and nothing is ever
taken out of the file. It opens no link and asks no reader; the file stays in runs/, never published.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import jsonl, paths  # noqa: E402
from proving import greyed  # noqa: E402


def marks(p: Path) -> tuple:
    """({(row, reading): its latest line} for those whose latest line marks them misjudged, the count lifted since)."""
    latest = {}
    for e in jsonl.read(p, bad="skip") if p.is_file() else ():
        if e.get("row") and e.get("reading"):
            latest[(e["row"], e["reading"])] = e
    held = {k: e for k, e in latest.items() if e.get("kind") == "misjudged"}
    return held, sum(1 for e in latest.values() if e.get("kind") == "measured")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 epilog="The camera: --camera <model>_fw<fw>, CAMSET_CAMERA or private/config.json.")
    ap.add_argument("--list", action="store_true", help="print the marks in force")
    ap.add_argument("--measured", nargs=2, metavar=("ROW", "READING"), help="lift ROW's mark for READING (icon or "
                                                                            "checklist)")
    ap.add_argument("--why", help="what measured it (required with --measured)")
    a = ap.parse_args(argv)
    got = paths.camera()
    if not got:
        sys.exit(paths.no_camera_message())
    p = greyed.memory_file(got[0])
    if a.measured:
        row, reading = a.measured
        if reading not in greyed.UNMEASURED:
            sys.exit(f"--measured: READING is one of {sorted(greyed.UNMEASURED)}, not {reading!r}")
        if not (a.why or "").strip():
            sys.exit("--measured needs --why: what measured the reading on a grey entry of that row")
        held, _ = marks(p)
        if (row, reading) not in held:
            sys.exit(f"{row!r} holds no {reading} mark in {paths.shown(p)}: nothing to lift (--list shows the marks)")
        greyed.mark_measured(row, reading, a.why.strip(), got[0])
        print(f"{row!r}: its {reading} mark lifted ({a.why.strip()})")
        return 0
    held, lifted = marks(p)
    if not held:
        print(f"no row is marked misjudged in {paths.shown(p)}" + (f" ({lifted} lifted)" if lifted else ""))
        return 0
    print(f"{len(held)} row(s) marked misjudged in {paths.shown(p)}, not entered on that reading alone:")
    for (row, reading), e in sorted(held.items()):
        print(f"  {row!r} ({reading}): run {e.get('run')}, frame {e.get('frame')}")
    if lifted:
        print(f"({lifted} lifted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
