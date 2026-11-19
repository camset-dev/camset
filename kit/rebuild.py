"""One rebuild of a camera's definition and of what is built from it, its steps in the order they must go (review
2026-11-18: six commands and a bless, in an order kept in people's heads).

    .venv/bin/python kit/rebuild.py --camera ILCE-1M2_fw4.00            # a look: the report and the gate line
    .venv/bin/python kit/rebuild.py --camera ILCE-1M2_fw4.00 --write    # every step, everything written

Each step is a kit command of its own, run in turn with this Python and the camera (--camera, CAMSET_CAMERA or
private/config.json: camkit.paths), its output shown as it prints it:

  1. kit/pass2_report.py                  pass 2's report (it writes its report.json in the run folder, as always)
  2. kit/schema_update.py                 the writer as a look, which ends on its gate line ("gate: N open questions
                                          in the report, every one accepted ..."); without --write the rebuild ends
                                          here, and nothing of the definition, its evidence, the docs, the leads, the
                                          ledger or the editor's golden menu is written
  with --write, instead of 2:
  2. kit/schema_update.py --write         the definition and its private evidence, written again until a write
                                          changes neither (nor the reset file), at most WRITES times: a record first
                                          named in a write has its proofs credited by the next (the rebuild says how
                                          many it took, and stops when the third still changed something)
  3. kit/tools/build_docs.py --no-viewer  the generated files the definition gives
  4. kit/tools/leads.py --write           the mining's leads (private)
  5. kit/tools/coverage.py --write        the coverage ledger, its public form and its private one
  6. the editor's golden menu, re-blessed where the camera has one (editor/tests/data/menu_<model>_fw<fw>.json):
     CAMSET_BLESS=1 cargo test --release the_default_menu_is_the_golden_one, in editor/; where cargo is not on this
     computer the rebuild says that command instead

The first step that fails stops the rebuild: its own words are above, the rebuild names the step and exits with its
status (nothing after it runs). At the end it says what was written: the files the steps said they wrote, those of
the definition's files the writes changed (its private evidence among them), and the golden menu when the bless
changed it.
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import ROOT, datafiles, definitions, paths  # noqa: E402

WRITES = 3                  # the write run until it changes nothing, at most this many times
# each step's command, from the repository's root (argv: the camera passed on to each)
COMMANDS = {
    "report": ["kit/pass2_report.py"],
    "look": ["kit/schema_update.py"],
    "write": ["kit/schema_update.py", "--write"],
    "docs": ["kit/tools/build_docs.py", "--no-viewer"],
    "leads": ["kit/tools/leads.py", "--write"],
    "coverage": ["kit/tools/coverage.py", "--write"],
}
BLESS = ["cargo", "test", "--release", "the_default_menu_is_the_golden_one"]
BLESS_SAID = "cd editor && CAMSET_BLESS=1 cargo test --release the_default_menu_is_the_golden_one"
# a step's own line for a file it wrote ("wrote editor/definitions/....json", coverage's "written: data/...")
WROTE = re.compile(r"^\s*(?:wrote|written:)\s+(\S.*?)(?: \(.*)?$")


class Stop(SystemExit):
    """The rebuild stopped, in plain words; its code the failing step's exit status."""

    def __init__(self, words: str, code: int = 1):
        print(words, flush=True)
        super().__init__(code)


def argv(step: str, camera: str) -> list:
    """The command of a step (COMMANDS) with this Python, the camera passed on."""
    first, *rest = COMMANDS[step]
    return [sys.executable, str(ROOT / first), *rest, "--camera", camera]


def run(cmd: list, cwd: Path = ROOT, env: dict = None) -> tuple:
    """(exit status, the lines it printed): the command run, its output shown as it comes."""
    p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace")
    lines = []
    for line in p.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        lines.append(line.rstrip("\n"))
    return p.wait(), lines


def golden(camera: str) -> Path:
    """The editor's golden menu of the camera (only the shipped definition's has one)."""
    return ROOT / "editor" / "tests" / "data" / f"menu_{camera}.json"


def settled_files(camera: str) -> list:
    """The files a write may change and a write that changes nothing leaves as they were: the definition, its private
    evidence and the camera's reset file (its names and tabs)."""
    p = definitions.path(camera)
    return [p, definitions.evidence_path(p), datafiles.reset_file(camera)]


def fingerprint(files: list) -> list:
    return [hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None for f in files]


def said(cmd: list) -> str:
    """A command as the rebuild names it: a kit script by its path from the repository's root, without the Python."""
    parts = cmd[1:] if cmd and cmd[0] == sys.executable else cmd
    return " ".join(Path(c).relative_to(ROOT).as_posix() if Path(c).is_absolute() and Path(c).is_relative_to(ROOT)
                    else c for c in parts)


def step(n: int, cmd: list, what: str, cwd: Path = ROOT, env: dict = None) -> list:
    """A step run (run), stopping the rebuild on a failure; the lines it printed."""
    print(f"\n== {n}. {what}: {said(cmd)}", flush=True)
    code, lines = run(cmd, cwd, env)
    if code != 0:
        last = next((x.strip() for x in reversed(lines) if x.strip()), "")
        raise Stop(f"\nrebuild stopped at step {n} ({what}): it exited with status {code}"
                   + (f", saying: {last}" if last else "") + ". Its own words are above; nothing after it ran.", code)
    return lines


def written_in(lines: list) -> list:
    return [m[1] for m in (WROTE.match(x) for x in lines) if m]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true", help="every step, everything written (without it: the report and "
                                                         "the writer's look, its gate line, nothing written)")
    a = ap.parse_args()
    got = paths.camera()
    if not got:
        sys.exit(paths.no_camera_message())
    camera = got[0]
    step(1, argv("report", camera), "pass 2's report")
    if not a.write:
        step(2, argv("look", camera), "the writer, as a look")
        print(f"\nA look: the report and the writer's gate line above; nothing of the definition, its evidence, the "
              f"docs, the leads, the ledger or the golden menu was written. kit/rebuild.py --camera {camera} --write "
              "writes them all.")
        return
    wrote = []
    files = settled_files(camera)
    first = fingerprint(files)
    for n in range(1, WRITES + 1):
        before = fingerprint(files)
        wrote += written_in(step(2, argv("write", camera), f"the definition, write {n} of at most {WRITES}"))
        if fingerprint(files) == before:
            break
    else:
        raise Stop(f"\nrebuild stopped after step 2: the definition or its evidence still changed at write {WRITES}, "
                   "where a write should change nothing by then. Look at what the writer printed above (its lines for "
                   "the new records and the kept proofs), and run kit/rebuild.py --write again once you know why.")
    wrote += [paths.shown(f) for f, was, now in zip(files, first, fingerprint(files), strict=True) if was != now]
    took = (f"the definition settled in {n} write{'s' if n > 1 else ''}: "
            + ("the first changed nothing" if n == 1 else f"write {n} changed nothing"))
    print(f"\n{took}", flush=True)
    wrote += written_in(step(3, argv("docs", camera), "the generated files"))
    wrote += written_in(step(4, argv("leads", camera), "the leads"))
    wrote += written_in(step(5, argv("coverage", camera), "the coverage ledger"))
    menu = golden(camera)
    blessed = None
    if not menu.exists():
        blessed = f"no golden menu: the editor's tests hold none for {camera}"
    elif not shutil.which("cargo"):
        blessed = (f"the golden menu not re-blessed: cargo is not on this computer. Where it is, run\n  {BLESS_SAID}\n"
                   "and look at the diff of the menu file")
    else:
        had = fingerprint([menu])
        step(6, BLESS, "the editor's golden menu", cwd=ROOT / "editor", env={**os.environ, "CAMSET_BLESS": "1"})
        if fingerprint([menu]) != had:
            wrote.append(paths.shown(menu))
            blessed = "the golden menu re-blessed: look at its diff"
        else:
            blessed = "the golden menu re-blessed, unchanged"
    shown = list(dict.fromkeys(wrote))
    print(f"\nrebuild of {camera} done: {took}; {blessed}.")
    print(f"written ({len(shown)}):" + "".join(f"\n  {w}" for w in shown) if shown else "no step said it wrote a file.")


if __name__ == "__main__":
    main()
