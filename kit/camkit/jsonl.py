"""JSON Lines files, the kit's logs and records: a run's events.jsonl and proofs.jsonl, a camera's downloads.jsonl.

    read(path)            the objects in a file, in order; [] when there is none
    append(path, entry)   one object added as one line, written whole

A line cut short is what a crash or a power cut leaves at the end of a file being written: read() leaves the last line
out when it does not parse, and refuses one that does not parse anywhere else (a file damaged in the middle is said,
not half read), unless the caller takes what it can (bad="skip": the downloads manifest, whose other entries still
count). A line that parses but is not an object is no entry: it is left out with bad="skip" and refused otherwise.
append() after such a line starts a line of its own, so the next entry is not glued onto the cut one and lost too.
"""
import json
import os
from pathlib import Path


def read(path: Path, bad: str = "last") -> list[dict]:
    """The objects in a JSON Lines file, in order, blank lines left out; [] when the file is not there. bad: "last"
    leaves out a last line that does not parse (cut short) and raises ValueError on any other; "skip" leaves out every
    line that does not parse as an object."""
    p = Path(path)
    if not p.exists():
        return []
    out, cut = [], None             # cut: a line that did not parse, refused once another line follows it
    with open(p, encoding="utf-8", errors="replace") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            if cut:
                raise cut
            try:
                entry = json.loads(line)
            except ValueError as e:
                if bad != "skip":
                    cut = ValueError(f"{p}: line {n} is not JSON ({e})")
                continue
            if not isinstance(entry, dict):
                if bad == "skip":
                    continue
                raise ValueError(f"{p}: line {n} is not a JSON object")
            out.append(entry)
    return out


def append(path: Path, entry: dict) -> None:
    """One object as one line at the end of the file ("\\n" on every platform), in one write; after a last line cut
    short, on a line of its own."""
    lead = ""
    try:
        with open(path, "rb") as f:
            f.seek(-1, os.SEEK_END)
            lead = "" if f.read(1) == b"\n" else "\n"
    except OSError:                 # no file yet, or an empty one (no last byte to seek to)
        pass
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(lead + json.dumps(entry) + "\n")
