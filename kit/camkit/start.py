"""How a kit program starts: the Python it needs, and what it says, in plain words, when the one that started it cannot
run it.

kit/setup.py makes the kit's own Python, .venv (.venv/bin/python; on Windows .venv\\Scripts\\python), with the packages
of kit/requirements.txt. A kit program started with another one, as python3 kit/tools/proof_viewer.py with the system's
Python (2026-11-12: Python 3.15 with no packages), died with a traceback ending "No module named 'numpy'", which tells
a lay person nothing. Every kit program imports camkit before any other package (kit/tests/test_start.py checks it),
and camkit calls watch() first: the program now stops with what happened and the command to run instead, built from the
one that was run (the kit's Python, the program's path from the camset folder, the same arguments).

What sets it off is what the program needs, never which Python it is: a Python older than 3.11, where the kit's code
does not load, or a package of kit/requirements.txt missing when the program imports it (the hook watch() installs).
A Python of the person's own with the packages runs the kit as well, and a program that needs none of them
(kit/tools/migrate_runs.py, which the docs run with python3) runs on the system's Python as before. No package is
looked for and kit/requirements.txt is read only once a program has failed, so importing camkit costs nothing more.
Standard library only, and readable by Python 3.9 (macOS's own /usr/bin/python3), so that it can say it is too old:
camkit/__init__.py, this file and every kit program parse there (kit/tests/test_start.py).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

OLDEST = (3, 11)        # the oldest Python the kit runs on, as kit/setup.py checks it (a test keeps the two alike)
# the packages of kit/requirements.txt whose import name is not their own name (lowercase, with _ for -)
IMPORT_NAMES = {"opencv-python-headless": "cv2", "pillow": "PIL", "pyyaml": "yaml"}
# Windows: the characters a word of a command may hold and be pasted as it is into both Command Prompt and PowerShell;
# any other (a space, & % ^ | < > , ; $ ` ( ) or a quote) and the word is put in double quotes
SAFE_WINDOWS = re.compile(r"[A-Za-z0-9_\-./\\:=+]+")


def watch(root: Path) -> None:
    """Stops at once on a Python older than OLDEST, and has a missing package of kit/requirements.txt end the program
    with words() rather than a traceback (any other error keeps its traceback). The command line and the program are
    taken now: camkit.paths takes --camera out of the command line next, and Python 3.15 takes __file__ off a program
    run from its file before the hook runs (seen 2026-11-12). python -m imports camkit before it makes the module the
    program, so there it is asked for when it fails (started())."""
    argv, early = list(sys.argv), started()
    if tuple(sys.version_info[:2]) < OLDEST:
        raise SystemExit(words(root, argv, early[0], module=early[1]))
    previous = sys.excepthook

    def hook(kind, err, tb):
        try:
            text = explain(err, root, argv, *(early if early[0] else started()))
        except Exception:                     # a fault here never hides the program's own error
            text = None
        if text is None:
            previous(kind, err, tb)
        else:
            print(text, file=sys.stderr)

    sys.excepthook = hook


def started() -> tuple:
    """(the program's file, its module name when it was started with python -m, else None): python -m gives the
    program a module spec, a file run as python file.py has none."""
    first = sys.modules.get("__main__")
    return getattr(first, "__file__", None), getattr(getattr(first, "__spec__", None), "name", None)


def explain(err: BaseException, root: Path, argv: list, main: str | None, module: str | None = None) -> str | None:
    """words() for an error that ended a kit program because a package of kit/requirements.txt is missing; None for
    any other error, for a program that is not a file of this camset folder's kit/ (python -c, the docs' builder
    in .venv, pytest), and for a missing package that was looked for while another error was being handled (a lazy
    import in an except or finally block): that one keeps its whole traceback, so the first error is never hidden."""
    if not isinstance(err, ModuleNotFoundError) or not main or not inside(Path(main), root / "kit"):
        return None
    if err.__context__ is not None or err.__cause__ is not None:
        return None
    wanted = requirements(root)
    if err.name not in wanted:
        return None
    package = wanted[err.name]
    return words(root, argv, main, package if package.lower() == err.name.lower() else f"{package} ({err.name})",
                 module=module)


def requirements(root: Path) -> dict:
    """kit/requirements.txt's packages, by the name a program imports each by: {import name: package name}."""
    try:
        text = (root / "kit" / "requirements.txt").read_text(encoding="utf-8")
    except OSError:
        return {}
    found = {}
    for line in text.splitlines():
        name = re.split(r"[\s;=<>!~\[#]", line.strip(), maxsplit=1)[0]
        if name:
            found[IMPORT_NAMES.get(name.lower(), name.lower().replace("-", "_"))] = name
    return found


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return False


def go_to(root: Path, windows: bool | None = None) -> str:
    """The step into the camset folder. On Windows in words for both of its terminals, so the person need not know which
    one they have: Command Prompt's cd changes to another drive (D:\\camset from C:\\) only with /d. kit/setup.py's
    go_to says the same (it runs before .venv exists and never imports camkit; a test keeps the two alike)."""
    if os.name == "nt" if windows is None else windows:
        return f'go to the camset folder (in Command Prompt: cd /d "{root}"; in PowerShell: cd "{root}")'
    import shlex
    return f"go to the camset folder (cd {shlex.quote(str(root))})"


def command(root: Path, argv: list, main: str | None, windows: bool, module: str | None = None) -> str | None:
    """The command that runs the same program with the kit's Python from the camset folder: the program's path from
    there (its own path when it lies elsewhere) and the same arguments, quoted for this system's terminal. None when
    no program file was run (python -c), and for python -m, whose module is found from the folder it was started in
    (cd kit && python -m camkit.safety), not from the camset folder."""
    if not main or module:
        return None
    try:
        parts = Path(main).resolve().relative_to(root.resolve()).parts
        shown = ("\\" if windows else "/").join(parts)
    except (ValueError, OSError):
        shown = str(main)
    return " ".join([venv_python(windows)] + [quoted(a, windows) for a in [shown, *argv[1:]]])


def quoted(word: str, windows: bool) -> str:
    """One word of a command, quoted so that it can be pasted: shlex.quote on macOS and Linux; on Windows double quotes
    around a word with any character outside SAFE_WINDOWS, a quote in it doubled and a backslash at its end doubled
    (else it would escape the closing quote). Inside double quotes Command Prompt still expands %NAME% and PowerShell
    $name and `: quoting them does no harm but does not make them safe, and no argument the kit takes holds them."""
    if not windows:
        import shlex
        return shlex.quote(word)
    if SAFE_WINDOWS.fullmatch(word):
        return word
    body = word.replace('"', '""')
    return '"' + body + "\\" * (len(body) - len(body.rstrip("\\"))) + '"'


def full_python(root: Path, windows: bool) -> str:
    """The step that names the kit's Python by its full path, to type in place of the Python that was used: quoted where
    it must be, and on Windows then in words for both terminals, as PowerShell runs a quoted path only after &."""
    full = str(root).rstrip("\\/") + ("\\" if windows else "/") + venv_python(windows)
    word = quoted(full, windows)
    said = "Start the program as before, with the kit's Python in place of this one"
    if not windows or word == full:
        return f"{said}: {word}"
    return f"{said} (in Command Prompt: {word}; in PowerShell: & {word})"


def venv_python(windows: bool) -> str:
    """The kit's Python as typed in the camset folder (the docs' spelling)."""
    return ".venv\\Scripts\\python" if windows else ".venv/bin/python"


def words(root: Path, argv: list, main: str | None, missing: str = "", windows: bool | None = None,
          ours: bool | None = None, there: bool | None = None, version: tuple | None = None,
          module: str | None = None, gone: bool | None = None) -> str:
    """What a program says when it cannot run: missing names the package that is missing, else the Python is too old.
    Then what to do, as numbered steps: with no .venv yet, kit/setup.py first, which makes it; with one, the same
    command with its Python; when the Python that failed is .venv's own (ours), kit/setup.py, which installs the
    packages again; when .venv's Python is a link to a Python that is gone (gone), kit/setup.py, which says how to make
    .venv again. With no command to give (python -c, python -m: command()), the kit's Python by its full path.
    The tests give windows, ours, there (.venv has a Python), gone and version; else they are this run's."""
    windows = os.name == "nt" if windows is None else windows
    venv = root / ".venv"
    exe = venv / ("Scripts" if windows else "bin") / ("python.exe" if windows else "python")
    if there is None:
        there = exe.exists()
    if gone is None:
        # a link whose Python was removed or upgraded away. A Windows .venv's python.exe is a copied launcher, not a
        # link, so this case is not found there
        gone = not there and os.path.lexists(exe)
    if ours is None:
        ours = same(Path(sys.prefix), venv)
    here = ".".join(str(n) for n in tuple(version or sys.version_info)[:2])
    oldest = ".".join(str(n) for n in OLDEST)
    setup = "py kit\\setup.py" if windows else "python3 kit/setup.py"
    run = command(root, argv, main, windows, module)
    step = go_to(root, windows)
    steps = [step[0].upper() + step[1:]]
    then = f"Run: {run}" if run else full_python(root, windows)
    if ours:
        head = (f"The kit's own Python (.venv) is missing one of the kit's packages, {missing}, so this program cannot "
                f"start. kit/setup.py installs the packages again:" if missing else
                f"The kit's own Python (.venv) is Python {here}, and the kit needs {oldest} or newer. kit/setup.py says "
                f"what to do:")
        steps += [f"Run: {setup}   (it puts back what is missing, or says what to do; it can take several minutes)",
                  f"Then run the program again: {run}" if run else "Then " + then[0].lower() + then[1:]]
    else:
        need = (f"the kit's Python packages, and the Python that started it ({here}) does not have them: {missing} is "
                f"missing" if missing else f"Python {oldest} or newer, and the Python that started it is {here}")
        if there:
            head = (f"This program needs {need}. The kit's own Python is in .venv (kit/setup.py made it): run the "
                    f"program with that one:")
            steps = steps + [then] if run else [then]          # the full path needs no cd
        elif gone:
            head = (f"This program needs {need}. The kit's own Python in .venv does not start: the Python it was made "
                    f"with is gone (removed or upgraded):")
            steps += [f"Run: {setup}   (it says how to make .venv again; it can take several minutes)",
                      "Then " + then[0].lower() + then[1:]]
        else:
            head = (f"This program needs {need}. The kit's own Python, with its packages, is made by kit/setup.py, "
                    f"which has not made it in this folder yet:")
            steps += [f"Run: {setup}   (it makes the kit's own Python, in .venv, with its packages, or says what it "
                      f"needs first; it can take several minutes)",
                      "Then " + then[0].lower() + then[1:]]
    return "\n".join([head] + [f"  {i}. {s}" for i, s in enumerate(steps, 1)])
