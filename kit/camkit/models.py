"""Which camera a run's files came from, and the tables in the pipeline that are one camera's.

A settings file names its body and firmware in its header, where its container block says (camkit.camset; the
ILCE-1M2's: the model at 0x05, the firmware at 0x36-0x37, "4.00"). The proof pipeline checks them: kit/pass2_report.py
and kit/schema_update.py refuse a run whose downloads are another camera's than the definition they compare with or
write (a body's proofs land only in its own definition, editor/definitions/<model>_fw<fw>.json), and a run holding
two bodies' files is refused. The video system the camera was set to (the ILCE-1M2's byte 0x38: NTSC or PAL) is not
part of that identity: the same camera wrote 04 00 00 on NTSC and 04 00 01 on PAL with nothing else changed
(2026-11-06), so a run's NTSC and PAL downloads of one firmware are one camera and firmware here; video_system() names
it where a file's identity is printed.

A few lookup tables in the pipeline are the ILCE-1M2's own (firmware 4.00): record ids and label sequences proved on
that body (prove_run's LABELS, ICON_ROWS and DISP_MODES, pass2_report's DISP_MODES and WRITTEN_BY, pass3_run's
BLOCKERS, the fixes in schema_update's own pass). They apply to that body's files only; each carries a TODO to move
into data/<model>_fw<fw>/ (docs/decisions/0020), as upload_check's Picture Profile records moved into the camera
file's picture_profile_in_use (2026-11-08) and schema_update's hand tables into the camera's hand tables file,
data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json (kit/writer/hand_tables.py).
"""
from pathlib import Path

from . import paths

A1II = "ILCE-1M2"          # the body the pipeline's own tables were proved on (firmware 4.00)


def header(path: Path) -> tuple[str, str]:
    """(model, firmware) from a settings file's header, through the first known container block whose magic it starts
    with, without framing its records."""
    from . import camset
    with open(path, "rb") as f:
        d = f.read(4096)
    try:
        return camset.peek(d)
    except ValueError as e:
        raise ValueError(f"{path}: {e}") from None


def video_system(path: Path) -> str:
    """The video system a settings file was saved under, in words ("PAL"), through the block header() reads it with;
    "" when that block does not say where it is, or the file cannot be read."""
    from . import camset
    try:
        with open(path, "rb") as f:
            return camset.peek_video_system(f.read(4096))
    except (OSError, ValueError):
        return ""


def of_run(run_dir: Path) -> tuple[str, str] | None:
    """(model, firmware) of the settings files a run downloaded (its dat/ folder), or None when it has none. A run
    holding files from two bodies or firmware versions is refused (ValueError): its proofs cannot be told apart. Files
    of one firmware saved under NTSC and under PAL are not two: the video system is not part of (model, firmware)."""
    seen = {}
    for p in sorted(Path(run_dir).glob("dat/*.DAT")):
        try:
            seen.setdefault(header(p), p)
        except (OSError, ValueError):
            continue
    if len(seen) > 1:
        def one(m, fw, p):
            v = video_system(p)
            return f"{m} firmware {fw} ({p.name}{', ' + v if v else ''})"
        raise ValueError(f"{run_dir}: downloads from more than one camera or firmware "
                         f"({', '.join(one(m, fw, p) for (m, fw), p in sorted(seen.items()))})")
    return next(iter(seen), None)


def refused(run_dir: Path, model: str, firmware: str, what: str) -> str:
    """Why the proofs in run_dir may not be compared with or written into the definition of (model, firmware), or
    "" when they may."""
    try:
        got = of_run(run_dir)
    except ValueError as e:
        return str(e)
    if got is None:
        return (f"{run_dir}/dat holds no settings file, so which camera the proofs came from cannot be told; "
                f"{what} needs the run's downloads")
    if got != (model, firmware):
        return (f"the proofs in {run_dir} come from a {got[0]} firmware {got[1]}, and {what} is the "
                f"{model} firmware {firmware}'s. A camera's proofs go into its own definition, "
                f"editor/definitions/{got[0]}_fw{got[1]}.json, with its own data/<model>_fw<fw>/ folder: name that "
                f"camera (--camera {got[0]}_fw{got[1]}; docs/decisions/0019)")
    return ""


def current(root: Path = None) -> str | None:
    """The model of the camera the kit last downloaded from, in a camera's run root (default: the one the kit works
    on, camkit.paths): the newest entry of its downloads manifest (camkit.provenance), else the newest settings file
    in a run's dat/ folder; None when there is neither."""
    from . import provenance
    root = Path(root) if root is not None else paths.run_root()
    for e in reversed(provenance.entries(root)):
        p = Path(e.get("path", ""))
        p = p if p.is_absolute() else Path(root) / p
        try:
            return header(p)[0]
        except (OSError, ValueError):
            continue
    newest, when = None, 0.0
    for p in Path(root).glob("*/dat/*.DAT"):
        try:
            t = p.stat().st_mtime
        except OSError:
            continue
        if t > when:
            newest, when = p, t
    try:
        return header(newest)[0] if newest else None
    except (OSError, ValueError):
        return None
