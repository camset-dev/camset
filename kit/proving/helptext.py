"""prove_run --help-text: the camera's own help (In-Camera Guide) for a row and each of its options, read with C4
on screens whose footer draws the help button; nothing is chosen."""
import json
from pathlib import Path

from .base import Failed
from .nav import cancel, move_to, to_row
from .options import which_option
from .screens import place, refuse_or_fail, same_place


def help_row(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    """The camera's help for the row, then for each option: the cursor moved as for a proof, C4 for
    the guide, OK closes it back onto the option, and MENU leaves the screen with nothing chosen
    (Grid Line Display's list, 2026-11-01: 0 records changed). Returns base_path: no download."""
    from drive import help_refused             # drive imports this module: here, not at the top
    from help_run import guide
    path, labels, kind = job["path"], job["labels"], job["kind"]
    name, n = " > ".join(path), len(labels)
    row_place = place(cam)
    if not help_refused(cam.read().kind, cam.frame.image):
        r = guide(cam, name)
        if not same_place(place(cam), row_place):
            raise Failed(f"{name}: after the row's guide the cursor is not on the row")
        out.write(json.dumps({"path": path, "kind": kind, "index": -1, "label": None, **r}) + "\n")
        out.flush()
        print(f"{name}: {r['text'][:100]!r}", flush=True)
    cam.press("right")
    if cam.read().kind != kind:
        refuse_or_fail(cam, name, f"not a {kind}")
    c = which_option(cam, job)
    if c is None:
        cancel(cam, link)
        raise Failed(f"{name}: could not tell which option the {kind} opened on")
    cur = c
    for k in [(c + i) % n for i in range(n)]:
        move_to(cam, cur, k, n, kind)
        cur = k
        if which_option(cam, job) != k:
            cancel(cam, link)
            raise Failed(f"{name}: the cursor is not on {labels[k]!r}")
        why = help_refused(cam.read().kind, cam.frame.image)
        if why:                                 # one option without help (Focus Area's Custom 1, 2026-11-01)
            print(f"   {labels[k][:28]!r:30s} (no help: {why})", flush=True)
            continue
        r = guide(cam, f"{name}: {labels[k]}")
        if cam.read().kind != kind or which_option(cam, job) != k:
            cancel(cam, link)
            raise Failed(f"{name}: after the guide of {labels[k]!r} the {kind} is not back on it")
        out.write(json.dumps({"path": path, "kind": kind, "index": k, "label": labels[k], **r}) + "\n")
        out.flush()
        print(f"   {labels[k][:28]!r:30s} {r['text'][:90]!r}", flush=True)
    cancel(cam, link)                           # MENU: out of the list, nothing chosen
    to_row(cam, path, top, row_place)
    return base_path
