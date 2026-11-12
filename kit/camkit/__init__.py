"""camkit: the Python side of the camset kit (see docs/KIT_PLAN.md)."""
import json
import os
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
ROOT = KIT.parent
RUNS = ROOT / "runs"          # the camera folders' parent: a camera's runs are in camkit.paths.run_root()

# Windows: Python 3.11-3.14 reads and writes text as cp1252 unless UTF-8 mode is on, and the kit's labels and data
# hold ★, →, Cyrillic look-alikes and Sony's names. kit/setup.py says how to turn it on (PYTHONUTF8=1).
if os.name == "nt" and not sys.flags.utf8_mode:
    raise SystemExit("The kit needs Python's UTF-8 mode on Windows: run  setx PYTHONUTF8 1  once, open a new "
                     "terminal, and run the command again (or run it as  python -X utf8 ...).")


def built(folder: Path, name: str) -> Path:
    """A helper the kit builds: folder/name on macOS and Linux, name.exe on Windows (in Release/ after
    a Visual Studio build)."""
    tries = [f"{name}.exe", f"Release/{name}.exe"] if os.name == "nt" else [name]
    return next((folder / t for t in tries if (folder / t).exists()), folder / tries[0])


LINK_BIN = built(KIT / "link" / "build", "camlink")
CONFIG = ROOT / "private" / "config.json"


class ConfigMissing(SystemExit):
    """No private/config.json: the kit does not guess the camera's address, the eyes or the readers."""


def config(required: bool = True) -> dict:
    """The kit's settings: the camera's address, the eyes, the capture dongle, the readers. Yours are in
    private/config.json (your own folder, never published: docs/decisions/0018). Without it, a setting that
    has no default (the camera's address, the HDMI crop, the readers) stops the run with a message saying
    so: the example file's addresses are someone else's network, so the kit never falls back to them.
    required=False gives {} instead, for settings that have a default. Never holds credentials.
    With more than one camera, "cameras" lists them and "camera" names the one the kit works on: that one's own keys
    are laid over the rest (camkit.paths)."""
    if CONFIG.exists():
        return paths.overlay(json.loads(CONFIG.read_text(encoding="utf-8")))
    if required:
        raise ConfigMissing("No private/config.json: copy kit/config.example.json to "
                            "private/config.json and set your camera's address, the eyes and the readers in it "
                            "(docs/QUICKSTART.md). The kit does not use the example's addresses: they are someone "
                            "else's network.")
    return {}


from . import paths  # noqa: E402  (after RUNS and CONFIG, which it reads)

paths.take_command_line()          # --camera <model>_fw<fw>, on any kit command: camkit.paths
