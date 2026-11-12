"""Where a camera's runs go: runs/<model>_fw<fw>/, one folder per camera, as data/ keeps one per camera.

    runs/
      ILCE-1M2_fw4.00/   kit2_pass1/ kit2_pass2/ ... _viewer/ _cache/ downloads.jsonl calibration_*/
      ILCE-7M5_fw1.00/   kit2_pass1/ ...

A camera's folder (its run root) holds everything the kit makes for it: the run folders, the proof viewer
(_viewer/), the readers' answers (_cache/), the downloads manifest (downloads.jsonl, camkit.provenance). A second
body's runs never mix with the first's, and a download of one is never uploaded to the other.

The camera the kit works on, its key <model>_fw<firmware> as kit/tools/identify.py --camera prints it; the first
found wins:
  1. --camera <key> on the command line. Every kit command takes it: camkit takes it out of the command line when it
     is imported, before the command reads its own arguments, and the commands it starts inherit it (CAMSET_CAMERA);
  2. CAMSET_CAMERA=<key> in the environment;
  3. "camera" in private/config.json;
  4. the one entry of "cameras" in private/config.json, when it lists only one;
  5. the one camera folder in runs/ that holds runs, when there is only one (one camera mapped on this computer).
Without any of them run_root() stops and says how to name the camera. "cameras" entries are
{"model": ..., "firmware": ..., and any of the config's own keys for that camera alone (camera_ip, camera_model,
hdmi, eyes)}: camkit.config() lays the active camera's keys over the rest.

The kit's runs from before 2026-11-05 sat at the top of runs/ (kit2_*, _viewer, _cache, downloads.jsonl). One
there stops run_root() with the command that moves them under their camera's folder (kit/tools/migrate_runs.py):
they are never used where they are, nor silently.

CAMSET_RUNS names another folder to hold the camera folders (the tests use it; default: runs/ in the clone).
"""
import json
import os
import re
import sys
from pathlib import Path

KEY = re.compile(r"^(?P<model>[A-Za-z0-9][A-Za-z0-9-]*)_fw(?P<firmware>\d+\.\d+)$")
ENV = "CAMSET_CAMERA"
EXAMPLE = "ILCE-1M2_fw4.00"
A1II = "ILCE-1M2_fw4.00"           # the body the kit was built on: its runs are the tests' frames (a1ii_root())
MIGRATE = "python3 kit/tools/migrate_runs.py"
# what the kit makes in a camera's folder, which before 2026-11-05 it made at the top of runs/
LEFTOVER_DIRS = ("_viewer", "_cache")
LEFTOVER_FILES = ("downloads.jsonl",)
LEFTOVER_PREFIX = "kit2_"

_from_command_line = None          # the key --camera gave this process, if it did


class NoCamera(SystemExit):
    """Nothing names the camera the kit works on."""


class Leftovers(SystemExit):
    """The kit's runs from before per-camera folders sit at the top of runs/."""


def _pkg():
    return sys.modules[__package__]


def runs_top() -> Path:
    """The folder that holds the camera folders: runs/ in the clone, or CAMSET_RUNS."""
    return Path(os.environ.get("CAMSET_RUNS") or _pkg().RUNS)


def a1ii_root() -> Path:
    """The a1 II's run root in this clone (runs/ILCE-1M2_fw4.00, not CAMSET_RUNS'), where the tests and the menu twin
    find its frames (they skip without them), whichever camera the kit works on."""
    return _pkg().RUNS / A1II


def key(model: str, firmware: str) -> str:
    return f"{model}_fw{firmware}"


def split(camera: str) -> tuple[str, str]:
    """(model, firmware) of a key; ValueError when it is not one."""
    m = KEY.match(camera or "")
    if not m:
        raise ValueError(camera)
    return m.group("model"), m.group("firmware")


def checked(camera, where: str) -> str:
    camera = str(camera).strip()
    if not KEY.match(camera):
        raise NoCamera(f"{where} gives {camera!r}, which is not a camera's key: it is <model>_fw<firmware>, as "
                       f"kit/tools/identify.py --camera prints it, for example {EXAMPLE}")
    return camera


def take_command_line(argv: list = None) -> str | None:
    """Take --camera <key> (or --camera=<key>) out of the command line, for this process (CAMSET_CAMERA) and the
    commands it starts. A bare --camera, or one before another option or an existing file, is left for the command
    (identify.py's own --camera asks the connected camera)."""
    global _from_command_line
    argv = sys.argv if argv is None else argv
    i, found = 1, None
    while i < len(argv):
        a = argv[i]
        if a.startswith("--camera="):
            found = checked(a.split("=", 1)[1], "--camera")
            del argv[i]
            continue
        if a == "--camera" and i + 1 < len(argv) and not argv[i + 1].startswith("-") \
                and not Path(argv[i + 1]).exists():
            found = checked(argv[i + 1], "--camera")
            del argv[i:i + 2]
            continue
        i += 1
    if found:
        os.environ[ENV] = found
        _from_command_line = found
    return found


def named_on_command_line() -> str | None:
    return _from_command_line


def _config() -> dict:
    p = _pkg().CONFIG
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise SystemExit(f"private/config.json is not valid JSON: {e}") from None


def cameras(cfg: dict = None) -> dict:
    """{key: entry} of the config's "cameras" list."""
    cfg = _config() if cfg is None else cfg
    out = {}
    for i, e in enumerate(cfg.get("cameras") or []):
        if not isinstance(e, dict) or not e.get("model") or not e.get("firmware"):
            raise NoCamera(f"private/config.json: \"cameras\" entry {i + 1} needs \"model\" and \"firmware\", as "
                           f"identify.py --camera prints them (for example {{\"model\": \"ILCE-1M2\", \"firmware\": "
                           f"\"4.00\"}})")
        out[checked(key(e["model"], e["firmware"]), f"private/config.json's \"cameras\" entry {i + 1}")] = e
    return out


def mapped() -> list:
    """The camera folders in runs/ that hold runs (a kit2_* folder or a downloads manifest), by key."""
    top = runs_top()
    if not top.is_dir():
        return []
    out = []
    for p in sorted(top.iterdir()):
        if p.is_dir() and KEY.match(p.name) and ((p / LEFTOVER_FILES[0]).exists()
                                                 or any(q.name.startswith(LEFTOVER_PREFIX) for q in p.iterdir())):
            out.append(p.name)
    return out


def camera(cfg: dict = None) -> tuple[str, str] | None:
    """(key, where it came from) of the camera the kit works on, or None when nothing names it."""
    cfg = _config() if cfg is None else cfg
    listed = cameras(cfg)
    found = None
    if os.environ.get(ENV):
        where = "--camera" if _from_command_line and os.environ[ENV] == _from_command_line else ENV
        found = (checked(os.environ[ENV], where), where)
    elif cfg.get("camera"):
        found = (checked(cfg["camera"], "private/config.json's \"camera\""), "private/config.json")
    elif len(listed) == 1:
        found = (next(iter(listed)), "private/config.json's one camera")
    else:
        roots = mapped()
        if len(roots) == 1 and not listed:
            found = (roots[0], f"the one camera in {shown(runs_top())}/")
    if found and listed and found[0] not in listed:
        raise NoCamera(f"{found[1]} names {found[0]}, which private/config.json's \"cameras\" does not list "
                       f"({', '.join(listed)}): add it there, or name one of those")
    return found


def overlay(cfg: dict) -> dict:
    """The config with the active camera's own keys (its "cameras" entry) laid over the rest."""
    try:
        got = camera(cfg)
    except NoCamera:
        return cfg
    entry = cameras(cfg).get(got[0]) if got else None
    if not entry:
        return cfg
    return {**cfg, **{k: v for k, v in entry.items() if k not in ("model", "firmware")}}


def leftovers(top: Path = None) -> list:
    """The kit's runs at the top of runs/ (from before per-camera folders), by name."""
    top = runs_top() if top is None else Path(top)
    if not top.is_dir():
        return []
    return sorted(p.name for p in top.iterdir()
                  if (p.is_dir() and (p.name.startswith(LEFTOVER_PREFIX) or p.name in LEFTOVER_DIRS))
                  or (p.is_file() and p.name in LEFTOVER_FILES))


def leftover_camera(top: Path = None) -> str | None:
    """The key of the camera the runs at the top of runs/ downloaded from, when one of their files says; None when
    none does."""
    from . import models
    top = runs_top() if top is None else Path(top)
    try:
        lines = (top / LEFTOVER_FILES[0]).read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    tries = []
    for line in reversed(lines[-20:]):
        try:
            p = Path(json.loads(line).get("path", ""))
        except (ValueError, AttributeError):
            continue
        tries.append(p if p.is_absolute() else top / p)
    for d in sorted(top.glob(LEFTOVER_PREFIX + "*/dat")):
        with os.scandir(d) as it:
            tries += [Path(e.path) for e in it if e.name.endswith(".DAT")][:1]
    for p in tries:
        try:
            return key(*models.header(p))
        except (OSError, ValueError):
            continue
    return None


def leftover_message(names: list, top: Path = None) -> str:
    top = runs_top() if top is None else Path(top)
    cam = leftover_camera(top)
    first = sorted(names, key=lambda n: (n != "kit2_pass2", n))[0]
    more = f" (with {len(names) - 1} more of the kit's)" if len(names) > 1 else ""
    whose = f"the {cam}'s runs under {shown(top)}/{cam}/" if cam else \
        f"them under {shown(top)}/<model>_fw<firmware>/, the camera's they are"
    flag = f" --camera {cam}" if cam else " --camera <model>_fw<firmware>"
    return (f"{shown(top)}/{first} sits at the top of {shown(top)}/{more}; run `{MIGRATE}{flag}` to move {whose} "
            f"(--dry-run shows the plan first). Until then the kit does not use them.")


def check_leftovers(top: Path = None):
    names = leftovers(top)
    if names:
        raise Leftovers(leftover_message(names, top))


def run_root(camera_key: str = None, required: bool = True) -> Path | None:
    """runs/<model>_fw<fw>/ of the camera named (camera_key), else of the camera the kit works on (camera()). Stops
    when the kit's runs from before 2026-11-05 sit at the top of runs/, and when nothing names the camera (None
    instead with required=False)."""
    check_leftovers()
    if camera_key:
        return runs_top() / checked(camera_key, "the camera asked for")
    got = camera()
    if got:
        return runs_top() / got[0]
    if required:
        raise NoCamera(no_camera_message())
    return None


def module_root() -> Path:
    """run_root() for the paths a script sets when it is imported (by then the --camera hook has run): the camera's
    folder, or, with nothing naming the camera, a folder that is not there, so that reading it finds nothing and a
    run (camkit.runs.Run) stops with run_root()'s message."""
    return run_root(required=False) or runs_top() / "(no camera named)"


def no_camera_message() -> str:
    roots = mapped()
    have = f" {shown(runs_top())}/ holds {', '.join(roots)}." if len(roots) > 1 else ""
    return (f"Which camera? Nothing names the camera the kit works on.{have} Put \"camera\": \"<model>_fw<firmware>\" "
            f"in private/config.json (for example \"{EXAMPLE}\"; kit/tools/identify.py --camera prints the connected "
            f"camera's), or add --camera <model>_fw<firmware> to the command, or set {ENV}.")


def run_path(given) -> Path:
    """A run folder, or a file in one, as a command line names it: as given when it is there; else under the camera's
    run root (kit2_crawl/map.json, kit2_pass2/dat/00001_start.DAT). Stops on a path into the kit's runs at the top of
    runs/, or into another camera's folder than the one the kit works on."""
    p = Path(given)
    if not p.exists() and not p.is_absolute() and p.parts[:1] != ("runs",):
        root = run_root(required=False)
        if root is None:                   # a run's name, and no camera to look for it in
            raise NoCamera(f"{given} is not here, and a run of that name would be in the camera's runs: "
                           + no_camera_message())
        p = root / p                       # where the camera's runs are, there or not (the caller says so)
    top = runs_top().resolve()
    try:
        parts = p.resolve().relative_to(top).parts
    except ValueError:
        return p
    if not parts:
        return p
    if parts[0] in leftovers(top):
        raise Leftovers(leftover_message(leftovers(top), top))
    if KEY.match(parts[0]):
        got = camera()
        if got and got[0] != parts[0]:
            raise NoCamera(f"{given} is the {parts[0]}'s, and the kit works on the {got[0]} ({got[1]}): add "
                           f"--camera {parts[0]} to work on that one")
    return p


def run_arg(given) -> str:
    """run_path for argparse's type=: the path as a string, as the commands' arguments were before."""
    return str(run_path(given))


def shown(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(_pkg().ROOT.resolve()).as_posix()
    except ValueError:
        return Path(p).as_posix()
