"""Move the kit's runs from the top of runs/ into their camera's folder, runs/<model>_fw<fw>/ (2026-11-05).

    python3 kit/tools/migrate_runs.py --dry-run                          # the plan only: nothing moves
    python3 kit/tools/migrate_runs.py --camera ILCE-1M2_fw4.00           # the plan, then the move

Before 2026-11-05 the kit kept one camera's runs at the top of runs/; now each camera has a folder of its own, as
data/ has (camkit.paths), and the kit stops while its runs sit at the top. Run this once. It moves, into the folder
of the camera named (--camera, else the one the config names, else the one the runs' own downloads name):
  - what the kit makes in a camera's folder: kit2_* (run folders and their logs), _viewer, _cache, downloads.jsonl,
    calibration*;
  - the a1 II's older runs whose frames the kit's tests and its menu twin read (READ_BY_THE_KIT).
Everything else at the top of runs/ is listed and left where it is (--all moves it too, once the list shows it is
all that camera's). The STOP files and the camera folders stay.

Each entry is renamed (os.rename: the same disk, nothing copied, nothing deleted), and nothing moves when any of
them is already in the camera's folder. The downloads manifest's absolute paths into the moved runs are made
relative to the camera's folder, as the kit writes them now. The runs' downloads must be the named camera's model:
a run whose files are another body's stops it before anything moves.
"""
import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path

if sys.version_info < (3, 11):  # noqa: UP036 (says so under older Pythons)
    sys.exit(f"This needs Python 3.11 or newer (this is {sys.version.split()[0]}): run it as "
             ".venv/bin/python kit/tools/migrate_runs.py")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import models, paths  # noqa: E402

# what the kit makes in a camera's run root (camkit.paths), which it made at the top of runs/ before 2026-11-05
KIT_MADE = ("kit2_*", "_viewer", "_cache", "downloads.jsonl", "calibration*")
# the a1 II's runs from before kit2 that the kit still reads: kit/tests/test_core.py and kit/tests/score_screen.py
# (frames and files for the screen reader's tests), kit/camkit/twin.py (the menu twin, explore_stills/graph.jsonl)
READ_BY_THE_KIT = ("explore_stills", "explore_stills_pre20261027", "rip_stills", "iq_map", "dg_mydial", "dg_wheel",
                   "ck_keys1", "ck_play_keys", "ck_play_keys2", "fn_run1", "dial_ctrl3")
STAY = ("STOP", "STOP_CHAIN")          # stop files: whatever reads them still looks at the top


def known(name: str) -> bool:
    return any(fnmatch.fnmatchcase(name, p) for p in KIT_MADE) or name in READ_BY_THE_KIT


def plan(top: Path, camera: str, everything: bool = False) -> dict:
    """{"move": [...], "unknown": [...], "stay": [...], "clash": [...]}: the names at the top of runs/ and what
    happens to each; clash: those already in the camera's folder."""
    out = {"move": [], "unknown": [], "stay": [], "clash": []}
    for p in sorted(Path(top).iterdir()):
        n = p.name
        if n in STAY or (p.is_dir() and paths.KEY.match(n)):
            out["stay"].append(n)
        elif known(n) or everything:
            out["move"].append(n)
        else:
            out["unknown"].append(n)
    target = Path(top) / camera
    out["clash"] = [n for n in out["move"] if (target / n).exists() or (target / n).is_symlink()]
    return out


def first_download(run: Path) -> Path | None:
    d = run / "dat"
    if not d.is_dir():
        return None
    with os.scandir(d) as it:
        return next((Path(e.path) for e in it if e.name.upper().endswith(".DAT") and e.is_file()), None)


def bodies(top: Path, names: list) -> dict:
    """{(model, firmware): [run names]} for the moving runs with a download (one file read per run)."""
    out = {}
    for n in names:
        f = first_download(Path(top) / n)
        if f is None:
            continue
        try:
            out.setdefault(models.header(f), []).append(n)
        except (OSError, ValueError):
            continue
    return out


def rewrite_manifest(root: Path, top: Path, moved: list) -> int:
    """Make the manifest's absolute paths into the moved runs relative to the camera's folder; the number of paths
    rewritten. Written beside it and renamed over it, so a stop leaves the old one whole."""
    f = Path(root) / "downloads.jsonl"
    if not f.exists():
        return 0
    top_r, moved, n, lines = Path(top).resolve(), set(moved), 0, []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            lines.append(line)               # a line cut short by a crash stays as it was
            continue
        for k in ("path", "adopted_from"):
            v = e.get(k)
            if not isinstance(v, str) or not Path(v).is_absolute():
                continue
            try:
                rel = Path(v).resolve().relative_to(top_r)
            except ValueError:
                continue                     # outside runs/: left absolute, as the kit writes it
            if rel.parts and rel.parts[0] in moved:
                e[k] = rel.as_posix()
                n += 1
        lines.append(json.dumps(e))
    if n:
        part = f.with_name(f.name + ".part")
        part.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        os.replace(part, f)
    return n


def camera_to_use(top: Path) -> tuple:
    """(key, where it came from): --camera or CAMSET_CAMERA, else the config's camera, else the runs' downloads."""
    got = paths.camera()
    if got:
        return got
    cam = paths.leftover_camera(top)
    if cam:
        return cam, "the runs' own downloads"
    sys.exit("Which camera are these runs? Nothing names it and no download in them says: add --camera "
             "<model>_fw<firmware> (for the a1 II's runs, --camera ILCE-1M2_fw4.00).")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--camera", metavar="MODEL_fwFW", help="the camera the runs are (default: the config's, else the "
                    "one the runs' downloads name), for example ILCE-1M2_fw4.00")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and move nothing")
    ap.add_argument("--all", action="store_true", help="also move the entries the kit does not know (listed in the "
                    "plan), when every one of them is this camera's")
    a = ap.parse_args(argv)
    if a.camera:                              # given as --camera=... after the import, or by a test's main([...])
        os.environ[paths.ENV] = paths.checked(a.camera, "--camera")
    top = paths.runs_top()
    if not top.is_dir():
        print(f"no {paths.shown(top)}/ here: nothing to move")
        return 0
    camera, where = camera_to_use(top)
    p = plan(top, camera, a.all)
    target = top / camera
    print(f"camera {camera} ({where}): {len(p['move'])} entries at the top of {paths.shown(top)}/ go into "
          f"{paths.shown(target)}/")
    for n in p["move"]:
        print(f"  move   {n}")
    for n in p["unknown"]:
        print(f"  leave  {n}  (not the kit's: --all moves it too)")
    for n in p["stay"]:
        print(f"  stay   {n}")
    if not p["move"]:
        print("nothing to move")
        return 0
    if p["clash"]:
        print(f"refused: already in {paths.shown(target)}/: {', '.join(p['clash'])}. Nothing moved: look at both, "
              "and move or merge them by hand first.", file=sys.stderr)
        return 1
    found = bodies(top, p["move"])
    model, _ = paths.split(camera)
    other = {k: v for k, v in found.items() if k[0] != model}
    if other:
        print("refused: these runs downloaded from another camera than " + camera + ": " + "; ".join(
            f"{m} firmware {fw}: {', '.join(v[:6])}{' ...' if len(v) > 6 else ''}" for (m, fw), v in sorted(other.items()))
              + ". Nothing moved: name their camera with --camera, or move them by hand.", file=sys.stderr)
        return 1
    for (m, fw), v in sorted(found.items()):
        if paths.key(m, fw) != camera:
            print(f"  note: {len(v)} runs downloaded at firmware {fw} ({', '.join(v[:4])}{' ...' if len(v) > 4 else ''}"
                  f"): they move with the rest; the pipeline refuses them for a firmware {paths.split(camera)[1]} "
                  "definition (camkit.models)")
    if a.dry_run:
        print("dry run: nothing moved (run it again without --dry-run to move)")
        return 0
    target.mkdir(exist_ok=True)
    for n in p["move"]:
        os.rename(top / n, target / n)
    print(f"moved {len(p['move'])} entries into {paths.shown(target)}/")
    n = rewrite_manifest(target, top, p["move"])
    if n:
        print(f"made {n} paths in {paths.shown(target / 'downloads.jsonl')} relative to {paths.shown(target)}/")
    if p["unknown"]:
        print(f"left at the top of {paths.shown(top)}/: {len(p['unknown'])} entries the kit does not know (above)")
    if where == "the runs' own downloads" or where.startswith("--camera"):
        print(f"next: the kit takes {camera} while runs/ holds only its runs; with a second camera, put "
              f"\"camera\": \"{camera}\" in private/config.json (docs/QUICKSTART.md, step 3)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
