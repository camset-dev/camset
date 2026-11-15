"""The kit's scripts end the way a script must: every file of kit/, kit/tools/ and kit/provers/ that defines `main` calls
it under `if __name__ == "__main__":` (kit/tools/take_picture.py once did not, so it printed nothing and exited 0), and
every one of them answers `--help` with its usage and exit 0 before it reads, connects or asks anything (the playbook
tells an agent to read each tool's --help first; kit/help_reads.py once took it for a run to ask the readers about).
No camera, no network: each script runs in a subprocess with no private/config.json, and anything it tries to start
(a link, any child process) or to connect to (a reader) is recorded in a marker file and refused."""
import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from camkit import ROOT

KIT = ROOT / "kit"
FOLDERS = (KIT, KIT / "tools", KIT / "provers")
SCRIPTS = sorted(p for d in FOLDERS for p in d.glob("*.py") if any(
    isinstance(n, ast.FunctionDef) and n.name == "main" for n in ast.parse(p.read_text(encoding="utf-8")).body))

# Scripts that do not answer --help with usage and exit 0, each with its reason. They are not left unchecked: --help
# must still start nothing, connect to nothing and write nothing, and each fails closed, refusing it as a bad argument
# before it reads, connects or asks (the test below). Teaching them --help is a change of their argument handling.
EXEMPT: dict[str, str] = {
    "hook.py": "a shim whose first argument is the program of the kit's venv to run (the pre-commit hook's); --help is "
               "refused as a program that is not there",
    "ocr_compare.py": "takes only run names; --help is refused as a run that is not there (it reads saved frames and "
                      "asks no reader, but it starts nothing and connects to nothing either way)",
    "sdk_set.py": "takes only NAME=VALUE pairs; --help is refused as one that is not, before any link is opened",
}

# Runs a script as `python script ARGS` would, with the kit's config pointed at a file that is not there, and every
# child process and every socket connection refused after writing the marker file: a link (camlink) is a child process,
# a reader (a vision model) a connection.
WRAPPER = r"""
import runpy, socket, subprocess, sys
from pathlib import Path
kit, script, marker = sys.argv[1:4]
sys.path.insert(0, kit)
sys.path.insert(0, str(Path(script).parent))       # as `python script` has it (runpy does not)
import camkit
camkit.CONFIG = Path(marker).with_name("no_such_config.json")
def tripped(*a, **k):
    with open(marker, "a", encoding="utf-8") as f:
        f.write("started or connected: %r\n" % (a[1:2] or a[:1],))
    raise RuntimeError("the test refuses a child process or a connection")
subprocess.Popen.__init__ = tripped
socket.socket.connect = tripped
socket.create_connection = tripped
sys.argv = [script] + sys.argv[4:]
runpy.run_path(script, run_name="__main__")
"""


def run_script(script: Path, args: list, tmp_path: Path, camera: str | None = None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("CAMSET_")}
    env.update(CAMSET_RUNS=str(tmp_path / "runs"), PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    if camera:
        env["CAMSET_CAMERA"] = camera
    marker = tmp_path / "marker.txt"
    r = subprocess.run([sys.executable, "-c", WRAPPER, str(KIT), str(script), str(marker), *args],
                       capture_output=True, text=True, timeout=60, cwd=tmp_path, env=env, stdin=subprocess.DEVNULL)
    return r, (marker.read_text(encoding="utf-8") if marker.exists() else "")


def has_main_guard(path: Path) -> bool:
    """Whether the file's top level has `if __name__ == "__main__":` whose body calls main()."""
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.If) and "__main__" in ast.dump(node.test) \
                and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == "main"
                        for stmt in node.body for c in ast.walk(stmt)):
            return True
    return False


def test_the_sweep_finds_the_scripts():
    assert len(SCRIPTS) > 40 and KIT / "tools" / "take_picture.py" in SCRIPTS


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: str(p.relative_to(KIT)))
def test_every_script_with_a_main_calls_it_under_a_main_guard(script):
    assert has_main_guard(script), f"{script.relative_to(ROOT)} defines main() but never runs it as a script"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: str(p.relative_to(KIT)))
def test_every_script_answers_help_before_it_reads_connects_or_asks(script, tmp_path):
    r, marker = run_script(script, ["--help"], tmp_path)
    assert marker == "", f"--help started a process or a connection: {marker}"
    assert not (tmp_path / "runs").exists() or not any((tmp_path / "runs").iterdir()), "--help wrote into the runs"
    if script.name in EXEMPT:                     # fails closed, and says why
        assert r.returncode != 0 and "Traceback" not in r.stderr and (r.stdout + r.stderr).strip(), EXEMPT[script.name]
        return
    assert r.returncode == 0, (r.stdout + r.stderr)[-600:]
    assert r.stdout.strip(), "--help printed nothing"


def test_take_picture_help_is_usage_and_exit_0(tmp_path):
    r, marker = run_script(KIT / "tools" / "take_picture.py", ["--help"], tmp_path)
    assert r.returncode == 0 and "usage:" in r.stdout and "--run" in r.stdout and marker == ""


def test_take_picture_says_what_is_missing_instead_of_exiting_0_silently(tmp_path):
    """With no camera named, it says so and exits nonzero; with one named but no owner statement it says that. Either
    way nothing is started and nothing is sent."""
    r, marker = run_script(KIT / "tools" / "take_picture.py", [], tmp_path)
    assert r.returncode != 0 and "camera" in (r.stdout + r.stderr).lower() and marker == ""
    r, marker = run_script(KIT / "tools" / "take_picture.py", [], tmp_path, camera="TEST-CAM_fw9.99")
    out = r.stdout + r.stderr
    assert r.returncode != 0 and out.strip() and marker == ""
    assert "take_picture.py" in out
