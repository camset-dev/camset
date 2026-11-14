"""Run a chain of camera steps from a TOML file, unattended (2026-10-31).

    .venv/bin/python -u kit/tools/chain.py kit/chains/stills_brackets.toml --end kit2_pass2/dat/<owner>.DAT
    .venv/bin/python -u kit/tools/chain.py kit/chains/stills_brackets.toml --dry       # list the steps only

kit/chains/stills_brackets.toml is the worked example: the chain the a1 II's Recall Custom holds ran (2026-10-31).

The chains used to be shell scripts; one waited 2.5 hours on a blank HDMI feed and one lost its prover
calls to shell word splitting. Here:
- each step is an argument list (no shell), a `.py` first argument runs with this Python;
- an `upload` step loads a start file through kit/tools/upload_check.py; if it fails, the chain stops
  there (the next steps would run in the wrong state and tag their proofs with the wrong context);
- a step that exits with status 4 (EXIT_UNRESTORED, kit/exit_status.py: its restore did not check out, or the camera
  refused its last download) left the camera perhaps not on its start file: the chain stops there too, before the
  next step changes anything else, and the end file is uploaded (decision 15); a step that exits with status 5
  (EXIT_RESTORE_BY_HAND: its last press, which an owner decision allowed with "link_loss", may have dropped the link)
  stops the chain too, and then no end file is uploaded: the step's start file goes back by hand first
  (kit/tools/upload_check.py, the file the camera's RESTORE_BY_HAND.json names), and no link opens before that; a
  step that exits with status 6 (EXIT_NOT_CONFIRMED: that press only brought up its row's own question, which the step
  cancelled with MENU, its start file restored and checked) stops the chain as status 4 does, since nothing was
  confirmed; any other failure is listed and the chain goes on;
- a step over its `limit` (seconds) is asked to stop through its `stop` file (a run's STOP: the
  walkers cancel to the menu and close it). The runner never kills a step: a camera left in a
  dialog is worse than a late chain. A step with no `stop` file is only reported;
- touching the chain's `stop` file (default STOP_CHAIN in the camera's runs/<model>_fw<fw>/) ends the chain between
  steps;
- the `--end` file (or the chain's `end`) is uploaded last whatever happened, so the camera is left
  as its owner had it, but after a step that exited with status 5 (above). The owner's file is given on the command
  line, not kept in the chain file.

The chain runs on one camera, the one the kit works on when it starts (camkit.paths; --camera names another), and
every step is told which (CAMSET_CAMERA). A relative path in a chain file (upload, log, stop, end) is in that
camera's runs/<model>_fw<fw>/; one written from the clone's root (runs/...) is refused, since the runs moved under
their camera's folder on 2026-11-05. On the command line, --end and --stop are paths as given, else in the camera's
runs.

A chain file:

    name = "holds"
    end = "kit2_pass2/dat/owner.DAT"                 # optional; --end overrides
    [env]
    CAMSET_EYES = "osd"                              # optional, for every step

    [[step]]
    title = "quiet Stills start file"
    upload = "kit2_pass2/start_reg_stills_2026-10-30.DAT"

    [[step]]
    title = "hold 2"
    run = ["kit/provers/customshoot_values.py", "--allow", "Reg. Custom Shoot Set", "--hold", "2", "--items", "Shoot Mode,Drive Mode"]
    log = "kit2_pass2/customshoot_values2.log"       # the step's output (default: the chain's own log)
    show = "options|stopped|records differ|restore"  # lines of it to echo to the chain's output
    limit = 3600
    stop = "kit2_pass2/STOP"
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# camkit before tomllib (Python 3.11): an older Python is told so in plain words (camkit/start.py), not a traceback
from camkit import ROOT, paths  # noqa: E402
import tomllib  # noqa: E402
# a step's exit status when the camera may not be back on its start file, the runners' own: from kit/exit_status.py,
# which imports nothing (kit/runner.py would bring the camera's screen and frames along)
from exit_status import EXIT_NOT_CONFIRMED, EXIT_RESTORE_BY_HAND, EXIT_UNRESTORED  # noqa: E402

PY = sys.executable
RUN_ROOT = None          # the camera's runs, set in main()


def at(p) -> Path:
    """A chain file's path: absolute as it is, else in the camera's runs (runs/<model>_fw<fw>/)."""
    p = Path(p)
    if p.is_absolute():
        return p
    if p.parts[:1] == ("runs",):
        sys.exit(f"{p}: a chain file's paths are in the camera's runs folder, {paths.shown(RUN_ROOT)}/, since the "
                 f"runs moved under their camera's folder (2026-11-05): write {Path(*p.parts[1:]).as_posix()}")
    return RUN_ROOT / p


def rel(p: Path) -> str:
    """A path as the chain's output shows it: from the clone's root when under it, with forward slashes on every OS
    (camkit.paths.shown)."""
    return paths.shown(p)


def load(chain_file) -> dict:
    """The chain file read; a file TOML cannot read stops in plain words. A Windows path written in double quotes
    ("C:\\runs\\my.log") is the usual cause: TOML reads a backslash in them as an escape. A file saved in another
    encoding than UTF-8 (an older Notepad's "ANSI") is the other."""
    try:
        with open(chain_file, "rb") as f:
            return tomllib.load(f)
    except UnicodeDecodeError as e:
        sys.exit(f"{chain_file}: not a chain file TOML can read: it is not saved as UTF-8 text ({e}). Save it again "
                 "as UTF-8 (in Notepad: File, Save as, Encoding: UTF-8) and run the chain again")
    except tomllib.TOMLDecodeError as e:
        sys.exit(f"{chain_file}: not a chain file TOML can read ({e}). A path with backslashes (a Windows path) goes in "
                 "single quotes ('C:\\runs\\my.log') or with forward slashes (\"C:/runs/my.log\"). A relative path "
                 "(my.log) needs neither: the chain reads it from the camera's runs folder")


def say(msg: str):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def argv_of(step: dict) -> list:
    if "upload" in step:
        return [PY, "-u", str(ROOT / "kit" / "tools" / "upload_check.py"), str(at(step["upload"]))]
    run = [str(x) for x in step["run"]]
    return [PY, "-u", *run] if run[0].endswith(".py") else run


def run_step(step: dict, env: dict, chain_log) -> int:
    argv = argv_of(step)
    log_path = at(step["log"]) if step.get("log") else None
    out = open(log_path, "w", encoding="utf-8", newline="\n") if log_path else chain_log  # noqa: SIM115 (closed in the finally below)
    stop = at(step["stop"]) if step.get("stop") else None
    limit, asked = step.get("limit"), False
    t0 = time.monotonic()
    try:
        p = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out, stderr=subprocess.STDOUT)
    except OSError:
        if log_path:
            out.close()
        raise
    try:
        while p.poll() is None:
            time.sleep(2)
            if limit and not asked and time.monotonic() - t0 > limit:
                asked = True
                if stop:
                    stop.touch()
                    say(f"   over its {limit} s: asked it to stop ({rel(stop)})")
                else:
                    say(f"   over its {limit} s, and it has no stop file: still waiting")
    finally:
        # whatever stopped the loop (Ctrl-C, an error here), the step finishes before anything else
        # reaches the camera: the end file is never uploaded under a running step
        if p.poll() is None and stop:
            stop.touch()
            asked = True
        p.wait()
    if stop and asked and stop.exists():
        stop.unlink()                     # the step's STOP must not stop the next step as well
    if log_path:
        out.close()
        show = step.get("show")
        text = log_path.read_text(errors="replace", encoding="utf-8").splitlines()
        lines = [ln for ln in text if re.search(show, ln)] if show else text[-6:]
        for ln in lines[-int(step.get("tail", 12)):]:
            print(f"   {ln}", flush=True)
    return p.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chain")
    ap.add_argument("--end", type=paths.run_arg,
                    help="the file to leave on the camera (the owner's); overrides the chain's")
    ap.add_argument("--stop", default="STOP_CHAIN", type=paths.run_arg,
                    help="touch it to end the chain between steps (default: STOP_CHAIN in the camera's runs)")
    ap.add_argument("--dry", action="store_true", help="list the steps and the commands, run nothing")
    a = ap.parse_args()
    global RUN_ROOT
    RUN_ROOT = paths.run_root()
    chain = load(a.chain)
    steps = chain.get("step", [])
    # the end file as an absolute path now: --end names an existing file as given (relative to this folder), which the
    # upload step would otherwise take for one in the camera's runs, after every step had run
    end = str(Path(a.end).resolve()) if a.end else (str(at(chain["end"])) if chain.get("end") else None)
    stop_chain = Path(a.stop)
    # PYTHONUTF8: each step's Python reads and writes UTF-8 on Windows too (camkit refuses to run otherwise); every
    # step works on this chain's camera, whatever named it
    env = {**os.environ, "PYTHONUTF8": "1", **{k: str(v) for k, v in chain.get("env", {}).items()},
           paths.ENV: RUN_ROOT.name}
    if a.dry:
        for i, s in enumerate(steps, 1):
            extra = {k: s[k] for k in ("log", "limit", "stop", "env") if k in s}
            argv = argv_of(s)
            shown = [str(Path(x).relative_to(ROOT)) if x.startswith(str(ROOT)) else x for x in argv[2:]] \
                if argv[0] == PY else argv
            print(f"{i:2d}. {s.get('title', '')}\n    {' '.join(shown)}"
                  + (f"\n    {extra}" if extra else ""))
        print(f"camera: {RUN_ROOT.name} ({paths.shown(RUN_ROOT)}/)")
        print(f"end: {end or '(none: the camera keeps the state of the last step)'}")
        return
    if stop_chain.exists():
        sys.exit(f"{rel(stop_chain)} exists: remove it to run the chain")
    if end and not Path(end).is_file():          # found missing now, not after hours of steps
        sys.exit(f"the end file {end} is not there: the camera could not be left as its owner had it")
    say(f"chain {chain.get('name', Path(a.chain).stem)}: {len(steps)} steps"
        + (f", ending on {Path(end).name}" if end else ", no end file"))
    failed = []
    try:
        for i, s in enumerate(steps, 1):
            if stop_chain.exists():
                say(f"{rel(stop_chain)}: stopping before step {i}")
                break
            say(f"== {i}/{len(steps)} {s.get('title', '')}")
            step_env = {**env, **{k: str(v) for k, v in s.get("env", {}).items()}}
            rc = run_step(s, step_env, sys.stdout)
            if rc:
                failed.append(i)
                say(f"   step {i} exited {rc}")
                if "upload" in s:
                    say("   the start file did not load: stopping the chain (its next steps need that state)")
                    break
                if rc == EXIT_UNRESTORED:
                    say("   the camera may not be back on its start file (the step's restore did not check out, or its "
                        "last download was refused): stopping the chain before another step changes it")
                    break
                if rc == EXIT_RESTORE_BY_HAND:
                    # the step's last press, which an owner decision allowed with "link_loss", may have dropped the
                    # link: its start file goes back by hand (camkit.runs RESTORE_BY_HAND), and no link opens before
                    # that, so the end file is not uploaded either
                    say("   the step's last press may have dropped the link (its owner decision's link_loss): stopping the "
                        "chain; no end file is uploaded. Look at the camera first and cancel there by hand whatever it "
                        "still shows (a question, a pairing, search or connection screen), with MENU or Cancel, never "
                        "Enter or OK. Put the step's start file back by hand once the camera is reachable, with "
                        "kit/tools/upload_check.py and the file RESTORE_BY_HAND.json names, then upload the end file "
                        "the same way")
                    end = None
                    break
                if rc == EXIT_NOT_CONFIRMED:
                    # the step's last press brought up its row's own question, which it cancelled with MENU before it
                    # restored its start file: nothing was confirmed, so what the next steps expect did not happen
                    say("   the step's last press only brought up its row's question, cancelled with MENU: nothing was "
                        "confirmed (its drive.jsonl keeps the question's frame); stopping the chain")
                    break
    finally:
        if end:
            say(f"== the end file: {Path(end).name}")
            run_step({"upload": end}, env, sys.stdout)
        say(f"done{'; steps that failed: ' + str(failed) if failed else ''}")


if __name__ == "__main__":
    main()
