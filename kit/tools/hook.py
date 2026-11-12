"""Run one commit hook (.pre-commit-config.yaml) with the kit's own venv, on macOS, Linux and Windows.

    python kit/tools/hook.py python kit/tools/check_public.py              # the kit's Python, running a script
    python kit/tools/hook.py check-jsonschema --schemafile S.json FILE     # a tool the kit's venv installed
    python kit/tools/hook.py check-jsonschema --schemafile S.json "editor/definitions/*.json"

pre-commit starts this with a Python of its own (the hooks' "language: python"), which every OS calls python. It
finds the kit's venv (.venv/bin on macOS and Linux, .venv\\Scripts on Windows, where the old ".venv/bin/..."
entries failed every commit) and runs the hook there, in UTF-8 mode, from the repository's root. An argument with a
wildcard is expanded against the repository's root here, the same on every OS (no shell runs the hook), so a hook
can check every file of a kind whatever changed; one that matches nothing is passed on as it is.
"""
import glob
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def venv_bin(root: Path = ROOT) -> Path:
    return root / ".venv" / ("Scripts" if os.name == "nt" else "bin")


def command(argv: list, root: Path = ROOT) -> list:
    """The hook's command line: argv's first word is a program in the kit's venv (python, check-jsonschema, ...)."""
    if not argv:
        raise SystemExit("usage: python kit/tools/hook.py PROGRAM [ARGS...] (a program in the kit's .venv)")
    folder = venv_bin(root)
    if not folder.is_dir():
        raise SystemExit(f"no kit venv at {folder}: run  python kit/setup.py  first (docs/QUICKSTART.md)")
    tool = folder / (argv[0] + (".exe" if os.name == "nt" else ""))
    if not tool.exists():
        raise SystemExit(f"{tool} is missing: run  python kit/setup.py  again to install the kit's requirements")
    return [str(tool), *[x for a in argv[1:] for x in expanded(a, root)]]


def expanded(arg: str, root: Path = ROOT) -> list:
    """The repository's files a wildcard argument names, relative to the root and sorted; the argument itself when it
    has no wildcard or matches nothing. The wildcard is matched inside the root (root_dir), so a clone whose own path
    holds [, * or ? (camset [copy]) is not read as a pattern too."""
    if not any(c in arg for c in "*?["):
        return [arg]
    found = sorted(Path(p).as_posix() for p in glob.glob(arg, root_dir=root))
    return found or [arg]


def main():
    env = {**os.environ, "PYTHONUTF8": "1"}
    sys.exit(subprocess.run(command(sys.argv[1:]), cwd=ROOT, env=env).returncode)


if __name__ == "__main__":
    main()
