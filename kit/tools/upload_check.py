"""Upload a settings file, wait for the camera's restart, download and list what did not take.
Or, with --diff REF.DAT, download TAG from the camera and print the record diff against REF.DAT.

    .venv/bin/python -u kit/tools/upload_check.py kit2_pass2/start_2026-10-29b.DAT   # in the camera's runs/<model>_fw<fw>/
    .venv/bin/python kit/tools/upload_check.py --diff REFERENCE.DAT TAG [--run kit2_dial]
    CAMSET_USB=1 .venv/bin/python -u kit/tools/upload_check.py FILE      # over USB
    .venv/bin/python kit/tools/upload_check.py --adopt          # take in downloads made before the manifest

Only a file the camera wrote is uploaded: its bytes must be a download's in this camera's
runs/<model>_fw<fw>/downloads.jsonl (camkit.provenance, docs/decisions/0006), checked before any connection. A file
named by a path that is not there is looked for in the camera's runs (kit2_pass2/dat/00001_start.DAT); one in another
camera's folder is refused. --adopt adds the downloads the
runs' events.jsonl logged before the manifest existed (each one unchanged since its download).

While the camera's runs/<model>_fw<fw>/RESTORE_BY_HAND.json is there (a run's last press may have dropped the link:
kit/drive.py --owner, exit status 5) no link opens, this tool's included, but to upload the start file it names; once
that restore checks out (0 records differ, the records no settings file sets back left out and said) the file is
removed and runs may start again (camkit.runs). When records still differ it lists them and the file stays; the
owner, having looked at them on the camera, may accept them by naming them back, --accept 0x1126,0x18cb (or
set1:0x023c for one section's), which removes the file only when those are exactly the records that differ now. That is
the owner's step, never an agent's: the ids are the ones the run before printed, so the flag cannot be passed blind.

Needs no HDMI. An upload ends the session (the camera restarts); camkit.session.verify_restore
reconnects and counts the records that differ. Some never take from a file (0x18cb's fourth slot,
0x1126, the memory slots' registration records, Remote Shooting while it is the session in use):
they are listed by name so a person can tell them from a failed restore.
"""
import argparse
import functools
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, definitions, paths, provenance  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.runs import RESTORE_BY_HAND, Run, clear_restore_by_hand, restore_pending_any  # noqa: E402
from camkit.session import verify_restore  # noqa: E402

IN_USE = ("live", "stills", "movie")       # picture_profile_in_use's records: the profile in use, stills', movie's


def the_camera() -> str | None:
    """The key of the camera the kit works on (camkit.paths), or None when nothing names it."""
    try:
        got = paths.camera()
    except paths.NoCamera:
        return None
    return got[0] if got else None


def in_use_records(camera: str | None = None) -> dict | None:
    """{"model", "ids"} from the camera's data/<model>_fw<fw>/camera_<model>_fw<fw>.json (by default the camera the
    kit works on): its model, and picture_profile_in_use's live, stills and movie record ids, each holding the
    profile in use (1-11: PP1-PP11). None when the camera, its camera file or the field is missing."""
    camera = camera or the_camera()
    f = definitions.camera_file(camera) if camera else None
    if f is None or not f.exists():
        return None
    facts = json.loads(f.read_text(encoding="utf-8"))
    pp = facts.get("picture_profile_in_use")
    if not pp:
        return None
    return {"model": facts["model"], "ids": tuple(int(pp[k], 16) for k in IN_USE)}


def pp_param_ids(camera: str | None = None) -> set:
    """Every Picture Profile parameter record, all three copies (eleven profiles each), in the camera's definition (by
    default the camera the kit works on): the settings of its "Picture Profile PP..." and "Picture Profile third copy
    PP..." groups. Empty without a definition."""
    camera = camera or the_camera()
    if not camera or not definitions.path(camera).exists():
        return set()
    out = set()
    for e in definitions.load(camera)["settings"]:
        if e["group"].startswith(("Picture Profile PP", "Picture Profile third copy PP")):
            out.add(int(e["key"].split("0x")[1][:4], 16))
    return out


def setting_names() -> dict:
    """{key: name} of the settings of the camera the kit works on (its definition), or {} while it has none."""
    p = definitions.active()
    return {s["key"]: s["name"] for s in definitions.load(p)["settings"]} if p.exists() else {}


def in_use_changes(new: camset.Camset, ref: camset.Camset, camera: str | None = None) -> list | None:
    """(record, profile) pairs where `new` changes a parameter of a profile in use in either mode, by the camera's
    picture_profile_in_use (in_use_records; by default the camera the kit works on); None when its camera file names
    none, so the check cannot be made. Files of another model than the camera's are not checked ([]).
    2026-11-01: a test file that rewrote PP11's copies while Movie had PP11 in use boot-looped the
    camera in Movie mode until the owner ran Initialize."""
    camera = camera or the_camera()
    rec = in_use_records(camera)
    if rec is None:
        return None
    if new.model != rec["model"] or ref.model != rec["model"]:
        return []                              # the in-use records and the profile groups are the camera's own
    used = {v - 1 for cs in (new, ref) for rid in rec["ids"]
            if (r := cs.get(0, rid)) and isinstance(v := r.value(), int) and 1 <= v <= 11}
    return [(rid, i) for rid in sorted(pp_param_ids(camera)) for i in sorted(used)
            if new.get(0, rid) and ref.get(0, rid) and new.get(0, rid).values()[i] != ref.get(0, rid).values()[i]]


def read_noted(*files) -> list:
    """The settings files read (camset.read), with one warning line printed first when any frames a record id twice in
    a section (camset.duplicates_note): what this tool compares then sees the last copy only."""
    read = [camset.read(f) for f in files]
    note = camset.duplicates_note({Path(f).name: cs for f, cs in zip(files, read, strict=True)})
    if note:
        print(note, flush=True)
    return read


# The records a settings file never sets back, by model (the module docstring's list): Recall Custom's registration
# working copy (0x18cb, its fourth slot: kit/proving/tables.py) and 0x1126, which only Camera Settings Reset and
# Initialize change (data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json); and the memory slots' registration records,
# memreg_run's NOT_BY_FILE in each of Memory 1-3 (kit/provers/memreg_run.py). A restore by hand after an Initialize
# leaves them as it wrote them
KNOWN_LEFT = {"ILCE-1M2": ("global:0x18cb", "global:0x1126")}
MEMORY_SECTIONS = (1, 2, 3)


def known_left(f: Path) -> frozenset:
    """The keys of the records a settings file never sets back, for the model of the file `f` (KNOWN_LEFT and memreg_run's
    NOT_BY_FILE); empty for a model none names, or a file that cannot be read."""
    try:
        model = camset.read(f).model
    except Exception:
        return frozenset()
    keys = set(KNOWN_LEFT.get(model, ()))
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "provers"))
        from memreg_run import NOT_BY_FILE
    except Exception:
        NOT_BY_FILE = {}
    keys |= {f"set{n}:0x{rid:04x}" for n in MEMORY_SECTIONS for rid in NOT_BY_FILE.get(model, ())}
    return frozenset(keys)


def pending_file(pending: dict, f: Path, root: Path) -> bool:
    """Whether `f` is the start file a RESTORE_BY_HAND (`pending`, camkit.runs.restore_pending) names: the same file,
    or the same bytes (its path in the camera's runs as the record writes it, or as given)."""
    named = pending.get("start")
    if not isinstance(named, str) or not named.strip():
        return False
    want = Path(named) if Path(named).is_absolute() else Path(root) / named
    try:
        return want.resolve() == Path(f).resolve() or (
            want.is_file() and Path(f).is_file() and provenance.sha256(want) == provenance.sha256(Path(f)))
    except OSError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", help="settings file to upload, or download tag when used with --diff")
    ap.add_argument("--diff", metavar="REF.DAT", default=None, type=paths.run_arg,
                    help="download FILE as a tag and print record diff against REF.DAT")
    ap.add_argument("--run", default="kit2_pass2",
                    help="run folder for the evidence (downloads), in the camera's runs/<model>_fw<fw>/")
    ap.add_argument("--ref", default=None, type=paths.run_arg,
                    help="with --check-in-use: the download to compare with (default: the newest)")
    ap.add_argument("--check-in-use", action="store_true", help="say whether the file changes the Picture Profile in use")
    ap.add_argument("--adopt", action="store_true",
                    help="record the downloads the runs' events.jsonl logged before the manifest existed, and stop")
    ap.add_argument("--accept", metavar="IDS", default=None,
                    help="the owner's step, with a restore by hand pending: the records that still differ from the "
                         "start file after the upload, named back as the run before listed them, comma-separated "
                         "(0x1126,0x18cb; set1:0x023c names one section's): RESTORE_BY_HAND.json is removed only when "
                         "they are exactly the records that differ now")
    a = ap.parse_args()
    if a.adopt:
        added = provenance.adopt(Run(a.run).root)
        for e in added:
            print(f"adopted {e['path']} ({e['adopted_from']})")
        print(f"{len(added)} downloads adopted into {provenance.manifest_path(Run(a.run).root)}")
        return
    if not a.file:
        ap.error("give the settings file to upload (or --adopt)")
    if not a.diff:
        a.file = paths.run_arg(a.file)           # a file to upload (with --diff, FILE is the download's tag)
    if a.diff:
        with Link(Run(a.run)) as link:
            got = link.download(a.file)
        names = setting_names()
        ch = camset.diff(*read_noted(a.diff, got))
        print(got.name, len(ch), "records differ from", Path(a.diff).name)
        for c in ch:
            name = names.get(c.key) or names.get("set:" + c.key.split(":")[1]) or "?"
            if isinstance(c.before, list):
                idx = [i for i, (x, y) in enumerate(zip(c.before, c.after, strict=True)) if x != y]
                print(f"  {c.key} {name} [{len(idx)} elements] " +
                      ", ".join(f"[{i}] {c.before[i]}->{c.after[i]}" for i in idx[:8]) + (" ..." if len(idx) > 8 else ""))
            else:
                print(f"  {c.key} {name} {c.before} -> {c.after}")
        return
    f, run = Path(a.file), Run(a.run)
    # 2026-11-01 (owner): "we should never set settings outside boundaries, we should be setting settings on
    # the camera and seeing changes". Only files the camera wrote (their bytes a download's in the manifest)
    # go back to it, to put a state back; nothing built or edited by hand is uploaded
    try:
        provenance.check(f, run.root)
    except provenance.NotADownload as e:
        sys.exit(str(e))
    # and a download that would change the Picture Profile in use is checked against the newest one
    downloads = [d for d in glob.glob(str(run.dat / "*.DAT")) if not Path(d).name.startswith("_camlink_upload")]
    ref = Path(a.ref) if a.ref else (max(downloads, key=os.path.getmtime) if downloads else None)
    if ref and a.check_in_use:
        bad = in_use_changes(*read_noted(f, ref))
        if bad is None:
            print(f"note: the Picture Profile in-use check is skipped: {the_camera() or 'the camera'}'s camera file "
                  f"names no picture_profile_in_use (data/<model>_fw<fw>/camera_<model>_fw<fw>.json)", flush=True)
        elif bad:
            print(f"note: {len(bad)} parameters of a Picture Profile in use differ from {Path(ref).name}", flush=True)
    # a run that may have dropped its link left RESTORE_BY_HAND naming its start file (camkit.runs): no link opens but to
    # put that very file back (Link's pending_restore), and the file is removed once the restore checks out
    found = restore_pending_any(run.root)
    marked_at, pending = found if found is not None else (None, None)
    if pending is not None and not pending_file(pending, f, marked_at):
        sys.exit(f"{marked_at / RESTORE_BY_HAND} says a run ({pending.get('run')}) may have dropped the link: put its "
                 f"start file back first ({pending.get('start')}), then this one (docs/decisions/0015); nothing was sent")
    restoring = {"pending_restore": True} if pending is not None else {}
    # the records a file never sets back (KNOWN_LEFT), said by key and left out of the count, while a restore by hand
    # is pending: an Initialize or a registration leaves them as it wrote them, whatever the start file holds
    left = known_left(f) if pending is not None else frozenset()
    with Link(run, **restoring) as link:
        print(link.upload(f), flush=True)
    n = verify_restore(run, f, **({"link_class": functools.partial(Link, **restoring)} if restoring else {}),
                       **({"expected": left} if left else {}))
    print("differences:", n, flush=True)
    differ = []
    if n:
        names = setting_names()
        got = max(glob.glob(str(run.dat / "*restored.DAT")), key=os.path.getmtime)
        for c in camset.diff(*read_noted(f, got)):
            name = names.get(c.key) or names.get("set:" + c.key.split(":")[1]) or "?"
            print(f"   {c.key} {name}", flush=True)
            if c.key not in left:
                differ.append(c.key)
    if pending is not None:
        if left:
            print(f"left out of the count, as no settings file sets them back: {', '.join(sorted(left))}", flush=True)
        why = ("" if n == 0 else "no reconnection counted the records" if n is None
               else "the records that still differ could not be listed" if not differ
               else "records still differ, and --accept does not name them" if a.accept is None
               else accept_refused(a.accept, differ))
        if not why:
            if n:
                print(f"--accept: the owner names the {len(set(differ))} records that still differ "
                      f"({', '.join(sorted(set(differ)))}) and accepts them", flush=True)
            clear_restore_by_hand(run.root)
            print(f"the start file of {pending.get('run')} is back on the camera and checked: "
                  f"{RESTORE_BY_HAND} removed, runs may start again", flush=True)
        else:
            print(f"the restore did not check out ({why}): {RESTORE_BY_HAND} stays, and no run starts until it does",
                  flush=True)
            if n:
                print(f"records that still differ: {', '.join(sorted(set(differ)))}. If the owner, having looked at "
                      "them on the camera, accepts them, they name them back with --accept "
                      f"{','.join(sorted({k.split(':')[-1] for k in differ}))} (the owner's step, never an agent's)",
                      flush=True)
    elif a.accept is not None:
        print("--accept is for a restore by hand pending, and none is: it changed nothing", flush=True)


def accept_refused(given: str, differ) -> str:
    """Why --accept's record ids (`given`, comma-separated: 0x1126, or set1:0x023c for one section's) are not exactly the
    records that still differ (`differ`: their keys, as "global:0x1126" or "set1:0x023c"), or "": an id names every
    record of that id that differs, a section's key that one alone; each must name one that differs, and every one that
    differs must be named. So the marker cannot be cleared blind: the ids are the ones the run before printed."""
    differ, named = set(differ), set()
    for item in (x.strip().lower() for x in str(given).split(",")):
        if not item:
            continue
        section, _, rid = item.rpartition(":")
        try:
            rid = f"0x{int(rid, 16):04x}"
        except ValueError:
            return f"{item!r} is no record id (0x1126, or set1:0x023c for one section's)"
        hits = {k for k in differ if k.split(":")[-1] == rid and (not section or k.split(":")[0] == section)}
        if not hits:
            return f"{item!r} names no record that differs now"
        named |= hits
    if differ - named:
        return f"--accept does not name {', '.join(sorted(differ - named))}, which still differ"
    return ""


if __name__ == "__main__":
    main()
