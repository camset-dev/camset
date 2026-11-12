"""Move a camera's private-whole files out of data/ into the private overlay, and make its reset file lean, once
(2026-11-11).

    .venv/bin/python kit/tools/move_evidence.py                              # the camera the kit works on
    .venv/bin/python kit/tools/move_evidence.py --camera ILCE-7M4_fw3.01     # another camera of this clone

The menu tree, the accepted rulings and the record shapes (menu_tree_, accepted_ and record_shapes_<model>_fw<fw>.json)
are the mapper's own, private whole (docs/decisions/0016, camkit.datafiles): the kit keeps them in
private/evidence/<model>_fw<fw>/ and no longer reads them in data/<model>_fw<fw>/, where a clone brought up to date in
the middle of a mapping still has them. This moves the three files of one camera (the one the kit works on: --camera,
CAMSET_CAMERA or private/config.json, camkit.paths) from the clone's data/ into the clone's own private/evidence/, and
prints one line per file. Nothing else in the kit moves them: reading a path never moves a file.

Each file is copied, the copy read back and compared byte for byte, and only then the data/ one deleted. Before
anything moves, every file is checked: one that is not readable JSON, in either place, stops it in plain words, and so
does a file that is in both places with different contents (both named: keep the right one by hand); a file in both
places with the same contents (byte for byte, or the same JSON) has its data/ copy removed. A destination that cannot
be written stops it in plain words and leaves no temporary file. It always moves into the clone's own
private/evidence/: with CAMSET_EVIDENCE_DIR set it says so, and that the kit, which looks there, finds the moved files
only once CAMSET_EVIDENCE_DIR points at the clone's private/evidence/ or the files are copied into that folder.

Fourth, the reset file (data/<model>_fw<fw>/settings_reset_<model>_fw<fw>.json): the public file is its one source
now, lean (camkit.datafiles.reset_not_lean). One in the older whole shape (the tests' own words, dates, a reading no
test could tell) is copied whole to private/evidence/<model>_fw<fw>/settings_reset_<model>_fw<fw>.json, an archive the
kit never reads again (the copy read back and compared first; when an archive of other contents is there already, the
copy takes a dated name beside it, so no archive is written over), and the lean projection (datafiles.lean_reset) is
written in its place, one line said. A lean file is left as it is.

git status then shows the files deleted from data/ (" D"; "AD" in a clone whose data/ folder was brought back with
git checkout and not committed since: added, then deleted), and the reset file changed (" M", or "AM"); the next
commit takes it. private/ is never committed. A --camera with no data/<model>_fw<fw>/ folder in this clone stops, saying so.
"""
import argparse
import contextlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

if sys.version_info < (3, 11):  # noqa: UP036 (says so under older Pythons)
    sys.exit(f"This needs Python 3.11 or newer (this is {sys.version.split()[0]}): run it as "
             ".venv/bin/python kit/tools/move_evidence.py")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, datafiles, paths  # noqa: E402


# where the move goes: the clone's own private/evidence/, whatever CAMSET_EVIDENCE_DIR says (main; the tests point it
# at a folder of their own, as they point camkit.datafiles.CLONE_DATA, the clone's data/)
CLONE_EVIDENCE = ROOT / "private" / "evidence"


class Refused(SystemExit):
    """The move stopped before anything moved, in plain words (a SystemExit: no traceback)."""


def _shown(p: Path) -> str:
    return paths.shown(p)


def _readable(p: Path) -> str | None:
    """Why the file at `p` is not readable JSON, in words, or None."""
    try:
        json.loads(p.read_text(encoding="utf-8"))
    except OSError as e:
        return f"it cannot be read ({e.strerror or e})"
    except UnicodeDecodeError:
        return "it is not text"
    except ValueError as e:
        return f"it is not valid JSON ({e})"
    return None


def _same(a: Path, b: Path) -> bool:
    """The two readable JSON files hold the same: byte for byte, or as JSON (another indent, another key order)."""
    return a.read_bytes() == b.read_bytes() or \
        json.loads(a.read_text(encoding="utf-8")) == json.loads(b.read_text(encoding="utf-8"))


def _copy_checked(src: Path, dest: Path) -> None:
    """`src` copied to `dest` through `dest`.part, read back and compared byte for byte before it takes its name;
    Refused in plain words, the .part file removed and `dest` as it was, when the folder cannot be written or the copy
    does not read back the same."""
    tmp = dest.with_name(dest.name + ".part")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, tmp)
        if tmp.read_bytes() != src.read_bytes():
            raise Refused(f"the copy of {_shown(src)} did not read back the same; nothing of it moved, it stays where it "
                          "is. Look at the disk, then run this again.")
        tmp.replace(dest)
    except OSError as e:
        raise Refused(f"nothing of {_shown(src)} moved: {_shown(dest.parent)}/ cannot be written ({e.strerror or e}). "
                      "Make that folder writable (or free some space), then run this again.") from None
    finally:
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
    if dest.read_bytes() != src.read_bytes():
        raise Refused(f"{_shown(dest)} does not read back as {_shown(src)}; {_shown(src)} is kept. Look at the disk, "
                      "then run this again.")


def plan(camera: str, data: Path, evidence: Path) -> list:
    """[(kind, old, new, what)] for each private-whole file of `camera`: what is "move" (only at the old place),
    "same" (in both, the same contents: the old copy goes), "done" (already private only) or "none" (in neither).
    Refused, nothing moved, for a file that is not readable JSON or one in both places that differs."""
    out, wrong = [], []
    for kind in datafiles.PRIVATE_WHOLE:
        old = data / camera / f"{kind}_{camera}.json"
        new = evidence / camera / f"{kind}_{camera}.json"
        unreadable = False
        for p in (old, new):
            why = _readable(p) if p.exists() else None
            if why:
                unreadable = True
                wrong.append(f"{_shown(p)}: {why}. Mend it or put a good copy there, then run this again.")
        if old.exists() and new.exists():
            same = unreadable or _same(old, new)        # an unreadable one is refused above, never "different"
            if not same:
                wrong.append(f"two different copies of one private file: {_shown(old)} (its old public place) and "
                             f"{_shown(new)} (where the kit keeps it now). Keep the one that is right: move it to "
                             f"{_shown(new)} and delete the other by hand, then run this again.")
            out.append((kind, old, new, "same"))
        else:
            out.append((kind, old, new, "move" if old.exists() else "done" if new.exists() else "none"))
    if wrong:
        raise Refused("nothing moved:\n  " + "\n  ".join(wrong))
    return out


def _remove(old: Path, kept: Path) -> None:
    """The data/ copy deleted once the private one is kept; Refused in plain words when data/ cannot be written (the
    copy is kept, and the next run removes the data/ one as the same)."""
    try:
        old.unlink()
    except OSError as e:
        raise Refused(f"{_shown(kept)} is kept, but {_shown(old)} could not be deleted ({e.strerror or e}). Make "
                      f"{_shown(old.parent)}/ writable and run this again: it then removes the data/ copy.") from None


def move(camera: str, data: Path, evidence: Path, say=print) -> list:
    """The camera's private-whole files moved from `data`/<camera>/ to `evidence`/<camera>/ (plan first: nothing moves
    when one is refused), one line said per file; returns the plan as carried out. A move copies through a temporary
    file, reads the copy back and compares it byte for byte with the old file, and only then deletes the old one."""
    steps = plan(camera, Path(data), Path(evidence))
    for kind, old, new, what in steps:
        if what == "move":
            _copy_checked(old, new)
            _remove(old, new)
            say(f"moved {_shown(old)} to {_shown(new)} (git status shows it deleted from data/, or AD where it was only "
                "staged: that is right)")
        elif what == "same":
            _remove(old, new)
            say(f"removed {_shown(old)}: the same file is kept at {_shown(new)}")
        elif what == "done":
            say(f"{kind}: already private, at {_shown(new)}")
        else:
            say(f"{kind}: not in {_shown(old.parent)}/ nor in {_shown(new.parent)}/ (nothing to move)")
    return steps


def lean_reset_file(camera: str, data: Path, evidence: Path, say=print) -> Path | None:
    """The fourth step: the camera's public reset file made lean when it is not (datafiles.reset_not_lean): its whole
    copied first to `evidence`/<camera>/<its name>, an archive the kit never reads again (read back and compared; one
    of other contents there already is kept, and the copy takes a dated name beside it), then the lean projection
    (datafiles.lean_reset) written in its place; one line said, counting apart the settings left out because no test
    could tell their reading and the entries left out because their key is not a definition's setting key. Returns the
    archive, or None when there was nothing to do (no reset file, or a lean one). Refused, nothing written, for a file
    that is not readable JSON or of a shape it does not know (not an object, "records" not an object of objects, as an
    old file whose records are a list)."""
    pub = data / camera / f"settings_reset_{camera}.json"
    if not pub.exists():
        say(f"settings_reset: no {_shown(pub)} (nothing to make lean)")
        return None
    why = _readable(pub)
    if why:
        raise Refused(f"nothing written: {_shown(pub)}: {why}. Mend it by hand, then run this again.")
    doc = json.loads(pub.read_text(encoding="utf-8"))
    if not datafiles.reset_not_lean(doc):
        say(f"settings_reset: {_shown(pub)} is lean already")
        return None
    if not isinstance(doc, dict):
        raise Refused(f"nothing written: {_shown(pub)} is not a JSON object; mend it by hand, then run this again.")
    records = doc.get("records")
    odd = (f"its \"records\" is {_a_json(records)}, not an object of settings by key" if not isinstance(records, dict)
           else next((f"its record {k!r} is {_a_json(r)}, not an object" for k, r in records.items()
                      if not isinstance(r, dict)), None))
    if odd:
        raise Refused(f"nothing written: {_shown(pub)} is a reset file of a shape this does not know ({odd}), so it "
                      "cannot tell what each reset does from it. Nothing was copied or changed. Mend it by hand into "
                      "the lean shape (docs/DATA_CONTRACTS.md, \"The reset file\"; keep a copy of the old one in "
                      f"private/evidence/{camera}/ first if you want it), then run this again.")
    archive = evidence / camera / pub.name
    if archive.exists() and (_readable(archive) or not _same(pub, archive)):
        archive = archive.with_name(f"{pub.stem}.archived-{time.strftime('%Y%m%d-%H%M%S')}.json")
    if not archive.exists():
        _copy_checked(pub, archive)
    lean = datafiles.lean_reset(doc)
    try:
        datafiles.write_reset(pub, lean)
    except OSError as e:
        raise Refused(f"{_shown(pub)} could not be written ({e.strerror or e}); its whole is kept at {_shown(archive)}. "
                      "Make it writable, then run this again.") from None
    not_keys = sum(1 for k in records if not datafiles.RESET_KEY.fullmatch(str(k)))
    untold = len(records) - not_keys - len(lean["records"])
    say(f"made {_shown(pub)} lean ({len(lean['records'])} settings kept"
        f"{f', {untold} whose reading no test could tell left out' if untold > 0 else ''}"
        f"{f', {not_keys} whose key is not a setting key of a definition (global:0x0123 or set:0x0123) left out' if not_keys else ''}"
        f"); the whole file is kept at {_shown(archive)}, which the kit never reads again (git shows the reset file "
        "changed: that is right)")
    return archive


def _a_json(v) -> str:
    """What kind of JSON value `v` is, in words."""
    return ("missing" if v is None else "a list" if isinstance(v, list) else "words" if isinstance(v, str)
            else "a number" if isinstance(v, (int, float)) and not isinstance(v, bool) else "true or false"
            if isinstance(v, bool) else "an object")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Move one camera's menu tree, accepted rulings and record shapes from "
                                             "data/<model>_fw<fw>/ to private/evidence/<model>_fw<fw>/, and make its "
                                             "reset file lean (its whole kept there as an archive).")
    ap.add_argument("--camera", metavar="<model>_fw<fw>",
                    help="the camera whose files to move (default: the camera the kit works on: CAMSET_CAMERA or "
                         "private/config.json's \"camera\")")
    a = ap.parse_args(argv)     # camkit takes --camera off sys.argv already (camkit.paths.take_command_line)
    got = (paths.checked(a.camera, "--camera"), "--camera") if a.camera else paths.camera()
    if got is None:
        raise paths.NoCamera(paths.no_camera_message())
    camera = got[0]
    data, evidence = datafiles.CLONE_DATA, CLONE_EVIDENCE
    if not (data / camera).is_dir():
        raise Refused(f"nothing moved: this clone has no {_shown(data / camera)}/ folder, so {camera} has no files "
                      "here to move. Check the camera's name (--camera <model>_fw<fw>, as data/ names its folder).")
    print(f"{camera} ({got[1]}):")
    env = os.environ.get("CAMSET_EVIDENCE_DIR")
    if env:
        print(f"note: CAMSET_EVIDENCE_DIR is set ({env}), but this moves into this clone's own {_shown(evidence)}/ "
              "only. The kit looks for your private files where CAMSET_EVIDENCE_DIR points, so afterwards point it at "
              f"{evidence} or copy the moved files from {_shown(evidence / camera)}/ into that folder.")
    move(camera, data, evidence)
    lean_reset_file(camera, data, evidence)


if __name__ == "__main__":
    main()
