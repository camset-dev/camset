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

Needs no HDMI. An upload ends the session (the camera restarts); camkit.session.verify_restore
reconnects and counts the records that differ. Some never take from a file (0x18cb's fourth slot,
0x1126, the memory slots' registration records, Remote Shooting while it is the session in use):
they are listed by name so a person can tell them from a failed restore.
"""
import argparse
import glob
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, definitions, paths, provenance  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.runs import Run  # noqa: E402
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
    with Link(run) as link:
        print(link.upload(f), flush=True)
    n = verify_restore(run, f)
    print("differences:", n, flush=True)
    if n:
        names = setting_names()
        got = max(glob.glob(str(run.dat / "*restored.DAT")), key=os.path.getmtime)
        for c in camset.diff(*read_noted(f, got)):
            name = names.get(c.key) or names.get("set:" + c.key.split(":")[1]) or "?"
            print(f"   {c.key} {name}", flush=True)


if __name__ == "__main__":
    main()
