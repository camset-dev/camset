"""A kit program started with a Python that cannot run it (camkit/start.py): the system's python3 rather than the kit's
own .venv, a Python older than 3.11, or a .venv that lost a package. It stops with what happened and the command to
run instead, in plain words and with no traceback (2026-11-12: python3 proof_viewer.py died with "No module named
'numpy'"). Every expectation is built for the system it runs on, or for both, so the tests pass on Windows too."""
import ast
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import types
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, start  # noqa: E402
from conftest import TEST_CAMERA  # noqa: E402

KIT = ROOT / "kit"
PROGRAMS = sorted([*KIT.glob("*.py"), *(KIT / "tools").glob("*.py"), *(KIT / "provers").glob("*.py")])


def venv_python(windows: bool) -> str:
    return ".venv\\Scripts\\python" if windows else ".venv/bin/python"


def test_a_program_started_without_the_packages_says_what_to_run_instead():
    """-S starts this Python without its site-packages: a Python with none of the kit's packages, as the system's
    python3 is. Started from kit/tools/ as the owner did, the command it gives runs from the camset folder, with the
    program's path from there and the same arguments, --camera too (camkit.paths takes it out of sys.argv)."""
    env = {**{k: v for k, v in os.environ.items() if k != "PYTHONPATH"}, "PYTHONUTF8": "1"}
    r = subprocess.run([sys.executable, "-S", str(Path("..") / "pass2_report.py"), "--help", "--camera", TEST_CAMERA],
                       cwd=KIT / "tools", env=env, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 1 and r.stdout == ""
    assert "Traceback" not in r.stderr and "ModuleNotFoundError" not in r.stderr
    windows = os.name == "nt"
    assert f"{venv_python(windows)} {Path('kit', 'pass2_report.py')} --help --camera {TEST_CAMERA}" in r.stderr
    assert start.go_to(ROOT)[1:] in r.stderr
    assert any(package in r.stderr.splitlines()[0] for package in start.requirements(ROOT).values())


@pytest.mark.parametrize("windows", [False, True])
def test_with_no_venv_yet_the_setup_comes_first(tmp_path, windows):
    main = str(tmp_path / "kit" / "tools" / "proof_viewer.py")
    text = start.words(tmp_path, ["proof_viewer.py", "--open", "a b"], main, "numpy", windows=windows, ours=False,
                       there=False, version=(3, 15))
    head, *steps = text.splitlines()
    assert "the Python that started it (3.15) does not have them: numpy is missing" in head
    assert "kit/setup.py, which has not made it in this folder yet" in head
    assert steps[0] == "  1. G" + start.go_to(tmp_path, windows)[1:]
    if windows:
        assert steps[1].startswith("  2. Run: py kit\\setup.py   (")
        assert steps[2] == '  3. Then run: .venv\\Scripts\\python kit\\tools\\proof_viewer.py --open "a b"'
        assert f'in Command Prompt: cd /d "{tmp_path}"; in PowerShell: cd "{tmp_path}"' in steps[0]
    else:
        assert steps[1].startswith("  2. Run: python3 kit/setup.py   (")
        assert steps[2] == "  3. Then run: .venv/bin/python kit/tools/proof_viewer.py --open 'a b'"
    assert len(steps) == 3


@pytest.mark.parametrize("windows", [False, True])
def test_with_a_venv_the_same_command_with_its_python(tmp_path, windows):
    """The trigger is the missing package, not which Python ran: a .venv there, another Python started the program."""
    main = str(tmp_path / "kit" / "pass2_report.py")
    text = start.words(tmp_path, ["pass2_report.py", "kit2_pass2"], main, "opencv-python-headless (cv2)",
                       windows=windows, ours=False, there=True, version=(3, 15))
    head, *steps = text.splitlines()
    assert "opencv-python-headless (cv2) is missing" in head and "is in .venv (kit/setup.py made it)" in head
    assert "setup.py" not in "".join(steps) and len(steps) == 2
    script = "kit\\pass2_report.py" if windows else "kit/pass2_report.py"
    assert steps[1] == f"  2. Run: {venv_python(windows)} {script} kit2_pass2"


@pytest.mark.parametrize("windows", [False, True])
def test_a_venv_that_lost_a_package_is_repaired_by_the_setup(tmp_path, windows):
    """.venv's own Python without a package (a pip install stopped half way): kit/setup.py installs the packages again
    (its packages step runs pip install -r kit/requirements.txt on every run)."""
    main = str(tmp_path / "kit" / "tools" / "build_docs.py")
    text = start.words(tmp_path, ["build_docs.py", "--check"], main, "pyyaml (yaml)", windows=windows, ours=True,
                       there=True)
    head, *steps = text.splitlines()
    assert head.startswith("The kit's own Python (.venv) is missing one of the kit's packages, pyyaml (yaml)")
    assert steps[1].startswith("  2. Run: " + ("py kit\\setup.py" if windows else "python3 kit/setup.py"))
    assert steps[2].startswith(f"  3. Then run the program again: {venv_python(windows)} kit")
    assert steps[2].endswith("build_docs.py --check")


def test_a_python_too_old_is_told_so(tmp_path, monkeypatch):
    """The macOS system's /usr/bin/python3 is 3.9, where camkit itself does not load: it stops before trying."""
    text = start.words(tmp_path, ["x.py"], str(tmp_path / "kit" / "x.py"), windows=False, ours=False, there=True,
                       version=(3, 9))
    assert text.startswith("This program needs Python 3.11 or newer, and the Python that started it is 3.9.")
    assert text.endswith("  2. Run: .venv/bin/python kit/x.py")
    monkeypatch.setattr(sys, "version_info", (3, 9, 6, "final", 0))
    with pytest.raises(SystemExit, match=r"Python 3\.11 or newer, and the Python that started it is 3\.9"):
        start.watch(tmp_path)


PROBE_S = 20           # seconds for each run of another Python: a probe that takes longer counts as no old Python


def answers(cmd: list) -> str | None:
    """What a probe printed, or None when it failed or took longer than PROBE_S."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=PROBE_S)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def old_python() -> str | None:
    """A Python older than start.OLDEST on this computer, or None: macOS's own /usr/bin/python3 (3.9), asked only where
    the developer tools are there (without them it opens a dialog that offers to install them), else a python3.9 or
    python3.10 on the PATH."""
    found = [shutil.which(n) for n in ("python3.9", "python3.10")]
    if sys.platform == "darwin" and Path("/usr/bin/python3").exists() and shutil.which("xcode-select") and \
            answers(["xcode-select", "-p"]) is not None:
        found.insert(0, "/usr/bin/python3")
    for exe in filter(None, found):
        said = answers([exe, "-c", "import sys; print('%d %d' % sys.version_info[:2])"])
        if said and tuple(int(n) for n in said.split()) < start.OLDEST:
            return exe
    return None


@pytest.mark.parametrize("program", ["tools/proof_viewer.py", "pass2_report.py", "tools/chain.py"])
def test_an_old_python_is_told_so_by_the_programs_themselves(program):
    """The real thing, where an old Python is there (macOS's own python3 is 3.9): the program and camkit must load far
    enough on it to say so, so new syntax in camkit/__init__.py, camkit/start.py or a program, or a module newer than
    3.9 imported before camkit (chain.py's tomllib), brings back the traceback. --help only: it stops at camkit."""
    exe = old_python()
    if exe is None:
        pytest.skip("no Python older than 3.11 on this computer")
    env = {**{k: v for k, v in os.environ.items() if k != "PYTHONPATH"}, "PYTHONUTF8": "1"}
    try:
        r = subprocess.run([exe, str(KIT / program), "--help"], cwd=ROOT, env=env, capture_output=True, text=True,
                           encoding="utf-8", timeout=PROBE_S)
    except subprocess.TimeoutExpired:
        pytest.fail(f"{exe} {program} --help did not stop within {PROBE_S} s: it should stop at camkit at once")
    assert r.returncode != 0 and "Traceback" not in r.stderr, r.stderr
    assert "This program needs Python 3.11 or newer, and the Python that started it is 3." in r.stderr


def test_camkit_and_every_program_parse_as_python_3_9():
    """A cheap guard that runs everywhere, beside the real run above (which needs an old Python): camkit/__init__.py,
    camkit/start.py and every kit program parse with the grammar of Python 3.9, so an old Python gets far enough to say
    it is too old. ast's feature_version is best effort: it refuses match, except* and type statements, but takes the
    f-strings of 3.12 (quotes reused inside, a backslash in the braces) and some other newer forms, which only the run
    on an old Python catches."""
    wrong = []
    for p in [KIT / "camkit" / "__init__.py", KIT / "camkit" / "start.py", *PROGRAMS]:
        try:
            ast.parse(p.read_text(encoding="utf-8"), str(p), feature_version=(3, 9))
        except SyntaxError as e:
            wrong.append(f"{p.relative_to(ROOT).as_posix()}:{e.lineno}: {e.msg}")
    assert wrong == []


def test_the_oldest_python_is_the_same_everywhere():
    """start.OLDEST, the checks the kit's programs make before they can import camkit (kit/setup.py, which never
    imports it, kit/tools/migrate_runs.py and kit/tools/move_evidence.py; start.py stays on its own), and ruff's
    target in pyproject.toml say the same Python. Every such check in a program or in camkit is found, not listed."""
    want = ".".join(str(n) for n in start.OLDEST)
    checks = {}
    for p in [*PROGRAMS, *(KIT / "camkit").glob("*.py")]:
        text = p.read_text(encoding="utf-8")
        said = re.findall(r"(?:version_info|version_key\(ver\))\s*<\s*\((\d+),\s*(\d+)\)", text)
        if said:
            checks[p.relative_to(ROOT).as_posix()] = said
            assert {f"{a}.{b}" for a, b in said} == {want}, p
            assert f"Python {want} or newer" in text, p
    assert {"kit/setup.py", "kit/tools/migrate_runs.py", "kit/tools/move_evidence.py"} <= set(checks)
    assert re.search(r'^target-version = "py(\d)(\d+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
                     re.M).groups() == tuple(str(n) for n in start.OLDEST)


# fixed camset folders, one per system's wording, so that no expectation rests on this computer's temp folder (on a
# Windows PC under a home folder whose name may hold a space, which shlex quotes in the macOS and Linux wording)
POSIX_ROOT, WINDOWS_ROOT = PurePosixPath("/srv/camset"), PureWindowsPath("C:/camset")


@pytest.mark.parametrize("windows", [False, True])
def test_python_c_and_python_m_get_the_kits_python_by_its_full_path(windows):
    """python -c has no program file, and python -m finds its module from the folder it was started in (cd kit &&
    python -m camkit.safety): a command from the camset folder would not run, so the kit's Python is named in full."""
    root = WINDOWS_ROOT if windows else POSIX_ROOT
    full = "C:\\camset\\.venv\\Scripts\\python" if windows else "/srv/camset/.venv/bin/python"
    text = start.words(root, ["-c"], None, "numpy", windows=windows, ours=False, there=False, gone=False, version=(3, 15))
    assert text.splitlines()[-1] == f"  3. Then start the program as before, with the kit's Python in place of this one: {full}"
    main = str(root / "kit" / "camkit" / "frames.py")
    text = start.words(root, ["-m", "--demo"], main, "numpy", windows=windows, ours=False, there=True,
                       module="camkit.frames")
    assert text.splitlines()[1:] == [f"  1. Start the program as before, with the kit's Python in place of this one: {full}"]


def test_a_full_path_with_a_space_is_quoted_for_each_terminal():
    """A camset folder whose path holds a space: the path is quoted, and PowerShell runs a quoted path only after &."""
    root = PurePosixPath("/srv/my camera/camset")
    text = start.words(root, ["-c"], None, "numpy", windows=False, ours=False, there=True, version=(3, 15))
    assert text.splitlines()[-1].endswith("in place of this one: '/srv/my camera/camset/.venv/bin/python'")
    root = PureWindowsPath("C:/My Camera/camset")
    text = start.words(root, ["-c"], None, "numpy", windows=True, ours=False, there=True, version=(3, 15))
    full = '"C:\\My Camera\\camset\\.venv\\Scripts\\python"'
    assert text.splitlines()[-1].endswith(f"in place of this one (in Command Prompt: {full}; in PowerShell: & {full})")


def test_a_windows_argument_is_quoted_unless_every_character_is_safe():
    """subprocess.list2cmdline quoted only spaces and tabs: & ^ | < > , ; ( ) and quotes run or split a command in
    Command Prompt or PowerShell when pasted bare, and are taken as they are inside double quotes. $ ` and % are quoted
    too, which is harmless but no more: inside double quotes PowerShell still expands $name and `, and Command Prompt
    %NAME%. No argument the kit takes holds them."""
    assert start.quoted("kit\\tools\\proof_viewer.py", True) == "kit\\tools\\proof_viewer.py"
    assert start.quoted("--camera=ILCE-1M2_fw4.00", True) == "--camera=ILCE-1M2_fw4.00"
    assert start.quoted("C:/runs/a+b", True) == "C:/runs/a+b"
    for word in ("a b", "a&b", "a^b", "a|b", "<a>", "a,b", "a;b", "(a)", "it's", ""):
        assert start.quoted(word, True) == f'"{word}"', word
    for word in ("$a", "a`b", "50%"):                   # quoted, though not made safe for every terminal (above)
        assert start.quoted(word, True) == f'"{word}"', word
    assert start.quoted('say "hi"', True) == '"say ""hi"""'
    assert start.quoted("C:\\My Runs\\", True) == '"C:\\My Runs\\\\"'       # the closing quote stays a quote
    text = start.command(Path("C:/camset"), ["x", "--rows", "Grid Line & More"], "C:/camset/kit/prove_run.py", True)
    assert text == '.venv\\Scripts\\python kit\\prove_run.py --rows "Grid Line & More"'
    assert start.command(Path("/camset"), ["x", "a&b", "it's"], "/camset/kit/x.py", False) == \
        ".venv/bin/python kit/x.py 'a&b' 'it'\"'\"'s'"


def test_a_missing_package_while_another_error_was_handled_keeps_its_traceback():
    """A lazy import in an except or finally block that fails: the first error is in the traceback's chain, and the
    plain words would hide it."""
    main = str(KIT / "tools" / "proof_viewer.py")
    try:
        try:
            raise KeyError("settings")
        except KeyError:
            raise ModuleNotFoundError("No module named 'numpy'", name="numpy")  # noqa: B904 (the case: no "from")
    except ModuleNotFoundError as e:
        during = e
    assert during.__context__ is not None and start.explain(during, ROOT, [main], main) is None
    caused = ModuleNotFoundError("No module named 'numpy'", name="numpy")
    caused.__cause__ = OSError("disk")
    assert start.explain(caused, ROOT, [main], main) is None
    assert start.explain(ModuleNotFoundError("No module named 'numpy'", name="numpy"), ROOT, [main], main)


@pytest.mark.parametrize("windows", [False, True])
def test_a_venv_whose_python_is_gone_is_said_truthfully(tmp_path, windows):
    """.venv/bin/python is a link to the Python .venv was made with: once that one is removed or upgraded away the link
    leads nowhere, and "kit/setup.py has not made it" would be untrue."""
    main = str(tmp_path / "kit" / "pass2_report.py")
    text = start.words(tmp_path, ["pass2_report.py"], main, "numpy", windows=windows, ours=False, there=False, gone=True,
                       version=(3, 15))
    head, *steps = text.splitlines()
    assert "The kit's own Python in .venv does not start: the Python it was made with is gone" in head
    assert "has not made it" not in text and "it says how to make .venv again" in steps[1] and len(steps) == 3


def test_a_dangling_link_is_found(tmp_path):
    exe = tmp_path / ".venv" / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
    exe.parent.mkdir(parents=True)
    try:
        exe.symlink_to(tmp_path / "no-such-python")
    except OSError:
        pytest.skip("this computer does not let the tests make a link")
    text = start.words(tmp_path, ["x.py"], str(tmp_path / "kit" / "x.py"), "numpy", ours=False, version=(3, 15))
    assert "does not start: the Python it was made with is gone" in text


def test_only_a_missing_package_of_the_kit_from_a_kit_program_is_explained():
    """Any other error keeps its traceback: a module of the kit's own that is missing (a bug, not a setup), another
    error, a program that is not a file of this folder (python -c, the docs' builder)."""
    main = str(KIT / "tools" / "proof_viewer.py")

    def gone(name):
        return ModuleNotFoundError(f"No module named {name!r}", name=name)

    assert "numpy" in start.explain(gone("numpy"), ROOT, [main], main).splitlines()[0]
    assert "pillow (PIL)" in start.explain(gone("PIL"), ROOT, [main], main).splitlines()[0]
    assert start.explain(gone("runer"), ROOT, [main], main) is None
    assert start.explain(ValueError("numpy"), ROOT, [main], main) is None
    assert start.explain(gone("numpy"), ROOT, ["-c"], None) is None
    assert start.explain(gone("numpy"), ROOT, ["x"], str(Path(sys.executable).parent / "zensical")) is None


def test_the_hook_explains_a_missing_package_and_passes_anything_else_on(tmp_path, monkeypatch, capsys):
    (tmp_path / "kit").mkdir()
    (tmp_path / "kit" / "requirements.txt").write_text("numpy==2.5.4; python_version >= \"3.12\"\n", encoding="utf-8")
    main = tmp_path / "kit" / "tools" / "proof_viewer.py"
    seen = []
    monkeypatch.setattr(sys, "excepthook", lambda kind, err, tb: seen.append(err))
    monkeypatch.setattr(sys, "argv", [str(main), "--camera", TEST_CAMERA])
    monkeypatch.setitem(sys.modules, "__main__", types.SimpleNamespace(__file__=str(main)))
    start.watch(tmp_path)
    sys.argv[1:] = []                         # camkit.paths takes --camera out after watch(): the command keeps it
    monkeypatch.setitem(sys.modules, "__main__", types.SimpleNamespace())   # Python 3.15 takes __file__ off first
    err = ModuleNotFoundError("No module named 'numpy'", name="numpy")
    sys.excepthook(ModuleNotFoundError, err, None)
    assert seen == [] and f"{Path('kit', 'tools', 'proof_viewer.py')} --camera {TEST_CAMERA}" in capsys.readouterr().err
    other = KeyError("x")
    sys.excepthook(KeyError, other, None)
    assert seen == [other]


def test_requirements_are_named_as_programs_import_them():
    """Each package of kit/requirements.txt by its import name (IMPORT_NAMES where it differs), as Python names it in
    the error: each one is there in the Python the tests run with, which has the kit's packages."""
    wanted = start.requirements(ROOT)
    assert {"numpy", "cv2", "PIL", "yaml", "kaitaistruct", "anthropic"} <= set(wanted)
    assert wanted["cv2"] == "opencv-python-headless" and wanted["PIL"] == "pillow" and wanted["yaml"] == "pyyaml"
    assert [n for n in wanted if importlib.util.find_spec(n) is None] == []


def top_level_imports(path: Path) -> list:
    """The top names a file imports at its top level (not in a function), in order, into if/try/with blocks too."""
    found = []

    def walk(body):
        for node in body:
            if isinstance(node, ast.Import):
                found.extend(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level:
                found.append(node.module.split(".")[0])
            elif isinstance(node, (ast.If, ast.Try, ast.With)):
                for part in ("body", "handlers", "orelse", "finalbody"):
                    for sub in getattr(node, part, []):
                        walk(sub.body if isinstance(sub, ast.ExceptHandler) else [sub])

    walk(ast.parse(path.read_text(encoding="utf-8")).body)
    return found


def imports_anywhere(path: Path) -> list:
    return [n for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            for n in ([a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else
                      [node.module.split(".")[0]] if isinstance(node, ast.ImportFrom) and not node.level else [])]


# standard-library modules newer than Python 3.9, the oldest start.py speaks to (macOS's own python3): 3.11 tomllib,
# 3.14 annotationlib and compression, 3.15 profiling. sys.stdlib_module_names is the running Python's, so it has them.
NOT_IN_39 = {"tomllib", "annotationlib", "compression", "profiling"}


def test_every_kit_program_imports_camkit_before_any_other_package():
    """camkit installs the plain words (camkit/start.py) when it is imported: a program that imported numpy, yaml or
    PIL first still died with a traceback (build_docs.py, camset_ksy.py, hdmi_watch.py, orient_run.py, until
    2026-11-12), and one that imported tomllib first did so on Python 3.9 and 3.10 (chain.py). Before camkit, or a kit
    program that imports it, a program imports only the standard library of Python 3.9 and the kit's own programs; one
    that never imports camkit imports none of kit/requirements.txt, anywhere (kit/setup.py, which runs before .venv
    exists)."""
    siblings = {p.stem: p for p in PROGRAMS}
    tops = {p.stem: top_level_imports(p) for p in PROGRAMS}
    std = set(sys.stdlib_module_names) - NOT_IN_39
    memo = {}

    def watched(name, seen=()):
        if name not in memo:
            memo[name] = any(t == "camkit" or (t in siblings and t not in seen and watched(t, (*seen, name)))
                             for t in tops[name])
        return memo[name]

    wanted = set(start.requirements(ROOT))
    wrong = []
    for p in PROGRAMS:
        for t in tops[p.stem]:
            if t == "camkit" or (t in siblings and watched(t)):
                break
            if t not in std and t not in siblings:      # NOT_IN_39 too, in a program that never imports camkit
                wrong.append(f"{p.relative_to(ROOT).as_posix()} imports {t} before camkit")
        if not watched(p.stem):
            wrong += [f"{p.relative_to(ROOT).as_posix()} imports {t} and never camkit"
                      for t in imports_anywhere(p) if t in wanted]
    assert wrong == []
