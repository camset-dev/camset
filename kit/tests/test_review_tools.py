"""The 2026-11-18 engineering review's findings on the kit's tools, each shown by a test before its fix: the exit
statuses of kit/tools/chain.py and kit/tools/upload_check.py (finding 18), and what keeps every test off the real
camera and the owner's config (finding 21). No camera: a chain's steps here are this Python, an upload's link and its
restore check are stand-ins, and the files are the ILCE-1M2 definition's sample."""
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from camkit import ROOT, camset, provenance
from camkit.runs import Run
from exit_status import EXIT_RESTORE_BY_HAND, EXIT_UNRESTORED

CHAIN = ROOT / "kit" / "tools" / "chain.py"
UPLOAD_CHECK = ROOT / "kit" / "tools" / "upload_check.py"
SAMPLE = ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"
KNOWN = 0x1126           # a record no settings file sets back on the ILCE-1M2 (upload_check.KNOWN_LEFT)
OTHER = 0x0050           # a record a settings file does set back


# ---------------------------------------------------------------- finding 18: upload_check's exit status

def changed(cs, *rids) -> bytes:
    """The sample's bytes with the first byte of each record `rids` names changed."""
    out = {}
    for rid in rids:
        raw = bytearray(cs.get(0, rid).raw)
        raw[0] ^= 1
        out[(0, rid)] = bytes(raw)
    return camset.with_values(cs, out)


def upload(monkeypatch, own_runs, differ, reconnects=True):
    """kit/tools/upload_check.py on a start file the camera wrote (in the made-up camera's downloads manifest), its
    link a stand-in, its restore check one that downloads a file differing from the start file in the records `differ`
    names (None when `reconnects` is False: the camera did not answer). Returns (the module, the start file)."""
    from tools import upload_check as U
    run = Run("kit2_pass2")
    start = run.dat / "00001_start.DAT"
    start.write_bytes(SAMPLE.read_bytes())
    provenance.record(start, run.root, run=run.dir.name)
    cs = camset.read(start)

    class Link:
        def __init__(self, run, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def upload(self, f):
            return {"ok": True}

    def verify(run, f, expected=frozenset(), **kw):
        if not reconnects:
            return None
        got = run.dat / "00002_restored.DAT"
        got.write_bytes(changed(cs, *differ))
        return len([c for c in camset.diff(cs, camset.read(got)) if c.key not in expected])
    monkeypatch.setattr(U, "Link", Link)
    monkeypatch.setattr(U, "verify_restore", verify)
    monkeypatch.setattr(U, "setting_names", lambda: {})
    monkeypatch.setattr(sys, "argv", ["upload_check.py", str(start)])
    return U, start


@pytest.mark.parametrize("differ,status", [((), 0), ((KNOWN,), 0), ((OTHER,), EXIT_UNRESTORED),
                                           ((KNOWN, OTHER), EXIT_UNRESTORED)])
def test_an_upload_whose_restore_does_not_check_out_exits_unrestored(monkeypatch, own_runs, capsys, differ, status):
    """Finding 18: the upload went, then records still differ from the file: exit 4 (EXIT_UNRESTORED), the records
    listed as before; one only no settings file sets back differing is a restore that checked out."""
    U, _ = upload(monkeypatch, own_runs, differ)
    assert U.main() == status
    out = capsys.readouterr().out
    assert f"differences: {len(differ)}" in out
    if OTHER in differ:
        assert f"global:0x{OTHER:04x}" in out and "did not check out" in out
    if differ == (KNOWN,):
        assert "only records no settings file sets back differ (global:0x1126)" in out


def test_an_upload_the_camera_never_answered_after_exits_unrestored(monkeypatch, own_runs, capsys):
    U, _ = upload(monkeypatch, own_runs, (), reconnects=False)
    assert U.main() == EXIT_UNRESTORED
    assert "the camera did not answer after its restart" in capsys.readouterr().out


def test_the_records_no_file_sets_back_come_from_a_library_and_no_import_error_is_hidden(monkeypatch):
    """Track 5's 10: known_left put kit/provers on sys.path at every call to import memreg_run's NOT_BY_FILE, and took
    any import error for "no such records". The constant is a library's now (camkit.not_by_file), memreg_run's the
    same object: the path stays as it was, and a prover that does not import changes nothing here."""
    from tools import upload_check as U
    before = list(sys.path)
    monkeypatch.setitem(sys.modules, "memreg_run", None)          # the prover cannot be imported
    got = U.known_left(SAMPLE)
    assert {"global:0x18cb", "global:0x1126", "set1:0x023c", "set2:0x11ab", "set3:0x11ad"} <= got
    assert sys.path == before
    import camkit.not_by_file
    monkeypatch.delitem(sys.modules, "memreg_run")
    import memreg_run
    assert memreg_run.NOT_BY_FILE is camkit.not_by_file.NOT_BY_FILE


def test_the_command_line_exits_with_the_uploads_status(monkeypatch, own_runs):
    """upload_check.py run as a program (its __main__ guard), the camkit seams it takes stood in: exit 4."""
    import camkit.link
    import camkit.session
    U, start = upload(monkeypatch, own_runs, (OTHER,))
    monkeypatch.setattr(camkit.link, "Link", U.Link)
    monkeypatch.setattr(camkit.session, "verify_restore", U.verify_restore)
    with pytest.raises(SystemExit) as e:
        runpy.run_path(str(UPLOAD_CHECK), run_name="__main__")
    assert e.value.code == EXIT_UNRESTORED


# ---------------------------------------------------------------- finding 18: the chain's exit status

def chain_toml(tmp_path: Path, *codes: int) -> Path:
    """A chain whose steps exit with `codes` in turn (this Python, no shell)."""
    py = Path(sys.executable).as_posix()
    c = tmp_path / "c.toml"
    c.write_text('name = "t"\n' + "".join(f'[[step]]\ntitle = "s{i}"\nrun = ["{py}", "-c", "raise SystemExit({rc})"]\n'
                                          for i, rc in enumerate(codes, 1)), encoding="utf-8")
    return c


def test_a_chain_with_a_failed_step_exits_non_zero(tmp_path):
    """Finding 18: a chain whose step failed (status 3, which now stops the chain there) used to exit 0."""
    r = subprocess.run([sys.executable, str(CHAIN), str(chain_toml(tmp_path, 3, 0)), "--stop", str(tmp_path / "STOP")],
                       capture_output=True, text=True, timeout=60)
    assert "steps that failed: [1]" in r.stdout and r.returncode == 1, r.stdout + r.stderr
    r = subprocess.run([sys.executable, str(CHAIN), str(chain_toml(tmp_path, 0)), "--stop", str(tmp_path / "STOP")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_chain_whose_end_file_did_not_go_back_exits_unrestored(tmp_path):
    """The end file's upload refused (no camera wrote it): every step ran, and the chain exits 4, saying so."""
    end = tmp_path / "owner.DAT"
    end.write_bytes(SAMPLE.read_bytes())
    r = subprocess.run([sys.executable, str(CHAIN), str(chain_toml(tmp_path, 0)), "--end", str(end),
                        "--stop", str(tmp_path / "STOP")], capture_output=True, text=True, timeout=120)
    assert "not a camera download" in r.stdout and "the end file did not go back" in r.stdout
    assert r.returncode == EXIT_UNRESTORED, r.stdout + r.stderr


def run_chain(tmp_path, monkeypatch, steps: list, codes: dict, end: bool = True, go_on: tuple = ()):
    """chain.main on a chain of `steps` (titles; "upload" an upload step), each step's status from `codes` (the end
    file's upload under "end"; a negative status a signal that killed the step, as Popen gives it), 0 when not named,
    the steps `go_on` names marked go_on_after_error. Returns (its status, what ran)."""
    from tools import chain
    owner = tmp_path / "owner.DAT"
    owner.write_bytes(b"x")
    f = tmp_path / "c.toml"
    f.write_text('name = "c"\n' + "".join('[[step]]\nupload = "start.DAT"\n' if s == "upload" else
                                          f'[[step]]\ntitle = "{s}"\nrun = ["kit/drive.py"]\n'
                                          + ("go_on_after_error = true\n" if s in go_on else "") for s in steps),
                 encoding="utf-8")
    ran = []

    def step(s, env, out):
        name = s.get("title") or ("end" if Path(s["upload"]) == owner.resolve() else "upload")
        ran.append(name)
        return codes.get(name, 0)
    monkeypatch.setattr(chain, "run_step", step)
    monkeypatch.setattr(chain.paths, "run_root", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["chain.py", str(f), "--stop", str(tmp_path / "STOP_CHAIN")]
                        + (["--end", str(owner)] if end else []))
    return chain.main(), ran


@pytest.mark.parametrize("steps,codes,end,status,ran,go_on", [
    (["a", "b"], {}, True, 0, ["a", "b", "end"], ()),
    (["a", "b"], {"a": 3}, True, 1, ["a", "end"], ()),                   # any failure stops the chain, the end file back
    (["a", "b"], {"a": 3}, False, 1, ["a"], ()),
    (["a", "b", "c"], {"b": 1}, True, 1, ["a", "b", "end"], ()),
    (["a", "b"], {"a": 3}, True, 1, ["a", "b", "end"], ("a",)),           # marked: the chain goes on after its error
    (["a", "b"], {"a": EXIT_UNRESTORED}, True, 1, ["a", "end"], ("a",)),  # ... never after a status the kit gives
    (["a", "b"], {"a": -9}, True, 1, ["a", "end"], ()),                  # killed by a signal: stopped, the end file back
    (["a", "b"], {"a": -9}, False, EXIT_UNRESTORED, ["a"], ("a",)),      # ... and with none, the camera unrestored
    (["a", "b"], {"end": 1}, True, EXIT_UNRESTORED, ["a", "b", "end"], ()),  # the end file did not go back
    (["upload", "a"], {"upload": EXIT_UNRESTORED}, True, 1, ["upload", "end"], ()),       # stopped, the end file back
    (["upload", "a"], {"upload": EXIT_UNRESTORED}, False, EXIT_UNRESTORED, ["upload"], ()),   # stopped, nothing back
    (["a", "b"], {"a": EXIT_UNRESTORED}, False, EXIT_UNRESTORED, ["a"], ()),
    (["a", "b"], {"a": EXIT_RESTORE_BY_HAND}, True, EXIT_RESTORE_BY_HAND, ["a"], ()),     # no end file uploaded
    (["a", "b"], {"a": EXIT_RESTORE_BY_HAND}, True, EXIT_RESTORE_BY_HAND, ["a"], ("a",)),
])
def test_the_chains_status_says_how_it_ended(tmp_path, monkeypatch, capsys, steps, codes, end, status, ran, go_on):
    assert run_chain(tmp_path, monkeypatch, steps, codes, end, go_on) == (status, ran)


def test_a_step_that_ends_at_once_costs_no_wait(tmp_path, monkeypatch):
    """Finding 18 (track 5's 11): the chain looked at its step every 2 s, so each step cost at least 2 s; now it waits
    on the process, which returns as soon as the step ends."""
    import time

    from tools import chain
    real = time.sleep

    def sleep(s):                       # subprocess's own wait sleeps a few ms at a time: those go on
        if s >= 1:
            pytest.fail(f"the chain slept {s} s on a step that had ended")
        real(s)
    monkeypatch.setattr(chain.time, "sleep", sleep)
    monkeypatch.setattr(chain, "RUN_ROOT", tmp_path)
    step = {"run": [sys.executable, "-c", "raise SystemExit(3)"], "log": "step.log"}
    assert chain.run_step(step, None, sys.stdout) == 3


# ---------------------------------------------------------------- the migration code retired

def test_a_private_file_in_data_is_refused_saying_to_move_it_by_hand(tmp_path, monkeypatch):
    """The migration tools served only the maintainer's history (the first public commit, b1a1d08, already had the
    per-camera runs, only public files in data/ and a lean reset file), so they are gone, with paths' leftovers check;
    the refusals that stay (check_public's of a private-whole file or a reset file not lean in data/, the commands'
    while a private-whole file is still there) say what to do by hand, naming no retired tool."""
    from camkit import datafiles, definitions, paths
    cam = "ILCE-0X0_fw1.00"
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    monkeypatch.setattr(datafiles, "CLONE_DATA", tmp_path / "data")
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path / "evidence")
    old = tmp_path / "data" / cam
    old.mkdir(parents=True)
    (old / f"accepted_{cam}.json").write_text("{}", encoding="utf-8")
    assert datafiles.evidence_in_public(old / f"accepted_{cam}.json") == [
        f"accepted_{cam}.json is private whole, kept in private/evidence/{cam}/: move it there by hand"]
    with pytest.raises(datafiles.Refused) as e:
        datafiles.stop_if_left(cam, "the pass-2 report")
    words = str(e.value.code)
    assert "move it by hand to" in words and str(tmp_path / "evidence" / cam / f"accepted_{cam}.json") in words
    reset = old / f"settings_reset_{cam}.json"
    reset.write_text('{"test": "Reset by hand, 2026-01-02", "records": {}}', encoding="utf-8")
    said = " ".join(datafiles.evidence_in_public(reset))
    assert "not lean" in said and "by hand" in said
    assert "by hand" in datafiles.not_lean_words(reset, ["the key 'test'"])
    for words in (said, str(e.value.code), datafiles.not_lean_words(reset, ["x"])):
        assert "move_evidence" not in words and "migrate_runs" not in words
    for gone in ("kit/tools/migrate_runs.py", "kit/tools/move_evidence.py", "kit/chains/stills_brackets.toml"):
        assert not (ROOT / gone).exists(), gone
    assert not hasattr(paths, "check_leftovers") and not hasattr(datafiles, "move_command")


# ---------------------------------------------------------------- finding 25: identify.py's docstring and its code

def test_identify_says_what_it_does_with_the_firmware_in_the_file():
    """Its docstring said both that a file's firmware bytes are read and that the firmware is not written in the file;
    the code reads them from the header (describe), and --camera names the folder by the SDK's SoftwareVersion, noting
    a header that says otherwise."""
    import identify
    assert "firmware 4.00 by the header" in identify.describe(SAMPLE)
    assert "not written in" not in " ".join(identify.__doc__.split())
    assert "SoftwareVersion" in identify.__doc__ and "header" in identify.__doc__.split("--camera reads")[1]


# ---------------------------------------------------------------- finding 21: no test reaches the real camera

def test_a_test_sees_neither_the_clones_config_nor_the_built_camlink(own_runs):
    """Finding 21: camkit.CONFIG was the clone's private/config.json and the link's camlink the built one in every test,
    so a test that forgot its fake would read the owner's camera address and connect. Now both are the conftest's
    (no_real_camera): a config that is not there, and a stub."""
    import camkit
    import camkit.link
    assert camkit.CONFIG != ROOT / "private" / "config.json" and not camkit.CONFIG.exists()
    assert camkit.config(required=False) == {}
    link = camkit.link.Link(Run("kit2_link"), ip="192.0.2.10", catch_signals=False)
    assert Path(link.args[0]).stem == "camlink_stub" and link.args[1:] == ["--ip", "192.0.2.10"], link.args


def test_a_kit_program_a_test_starts_sees_them_too(own_runs):
    """The same in a program a test starts, through the environment it inherits (CAMSET_CONFIG, CAMSET_LINK_BIN)."""
    code = "import sys; sys.path.insert(0, sys.argv[1]); import camkit; print(camkit.LINK_BIN); print(camkit.CONFIG)"
    r = subprocess.run([sys.executable, "-c", code, str(ROOT / "kit")], capture_output=True, text=True, timeout=60)
    link, config = r.stdout.splitlines()
    assert Path(link).stem == "camlink_stub" and config == os.environ.get("CAMSET_CONFIG"), r.stdout + r.stderr
    assert config != str(ROOT / "private" / "config.json")


def test_a_test_that_forgets_its_fake_fails(tmp_path):
    """A test that opens a link with no stand-in, and swallows the error, fails all the same: the stub notes that it was
    started. Run as a test session of its own with the kit's conftest."""
    t = tmp_path / "test_forgot.py"
    t.write_text("import contextlib\nfrom camkit.link import Link\nfrom camkit.runs import Run\n\n"
                 "def test_forgot(tmp_path):\n"
                 "    with contextlib.suppress(Exception):\n"
                 "        Link(Run('r', root=tmp_path), ip='192.0.2.10', catch_signals=False).open(timeout=20)\n",
                 encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "kit" / "tests"), str(ROOT / "kit")])}
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "conftest", "-p", "no:cacheprovider", str(t),
                        "--rootdir", str(tmp_path), "--basetemp", str(tmp_path / "inner")],
                       capture_output=True, text=True, timeout=120, env=env, cwd=tmp_path)
    assert r.returncode != 0 and "the test started camlink" in r.stdout and "192.0.2.10" in r.stdout, r.stdout[-3000:]


def test_a_test_asks_for_the_owners_config_by_name(tmp_path):
    """owner_config gives the owner's config (here a made-up one, through CAMSET_CONFIG as the session starts) back to
    the test that asks for it, and to the programs it starts; camlink stays the stub, and the next test has none
    again. Without a config of the owner's the test skips. Run as test sessions of their own with the kit's conftest."""
    made_up = tmp_path / "owners_config.json"
    made_up.write_text('{"camera_ip": "192.0.2.44"}', encoding="utf-8")
    t = tmp_path / "test_owner.py"
    t.write_text("import os, subprocess, sys\nimport pytest\nimport camkit, camkit.link\nfrom camkit.runs import Run\n\n"
                 "def test_asks(owner_config, tmp_path):\n"
                 "    assert camkit.config()['camera_ip'] == '192.0.2.44'\n"
                 "    code = 'import sys; sys.path.insert(0, sys.argv[1]); import camkit; print(camkit.config()[\"camera_ip\"])'\n"
                 "    r = subprocess.run([sys.executable, '-c', code, os.environ['KIT']], capture_output=True, text=True)\n"
                 "    assert r.stdout.strip() == '192.0.2.44', r.stderr\n"
                 "    assert camkit.link.Link(Run('r', root=tmp_path)).args[0].endswith(('camlink_stub', 'camlink_stub.cmd'))\n\n"
                 "def test_next():\n"
                 "    with pytest.raises(camkit.ConfigMissing):\n"
                 "        camkit.config()\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "kit" / "tests"), str(ROOT / "kit")]),
           "KIT": str(ROOT / "kit")}

    def session(config):
        return subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs", "-p", "conftest", "-p", "no:cacheprovider",
                               str(t), "--rootdir", str(tmp_path), "--basetemp", str(tmp_path / "inner")],
                              capture_output=True, text=True, timeout=120, cwd=tmp_path,
                              env={**env, "CAMSET_CONFIG": str(config)})
    r = session(made_up)
    assert r.returncode == 0 and "2 passed" in r.stdout, r.stdout[-3000:]
    r = session(tmp_path / "none.json")
    assert r.returncode == 0 and "1 passed, 1 skipped" in r.stdout and "no config of the owner's" in r.stdout, r.stdout[-3000:]
