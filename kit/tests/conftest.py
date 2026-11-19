"""Every test has a runs/ folder of its own (CAMSET_RUNS) and a made-up camera (CAMSET_CAMERA), so no test, nor a kit
command a test starts, reads or writes the runs of the clone it runs in (the owner's runs are evidence). The a1 II's
frames some tests read are found by their own path (camkit.paths.a1ii_root()), and those
tests skip without them. Nor does any test change a file of the clone's own data/ or private/evidence/ (the
mapper's evidence: guard_the_clones_files), whatever folder it points the kit at. A test that reads the screen through
camkit.reading fakes both its eyes, OCR and the reader, in one place: the eyes fixture (Eyes). No test reaches a camera
or reads the owner's config either, whatever fakes it forgets (no_real_camera); a test that reads the owner's config on
purpose asks for it by name, with the owner_config fixture, and skips where there is none."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARDED = (ROOT / "data", ROOT / "private" / "evidence")

TEST_CAMERA = "TEST-CAM_fw9.99"          # made up: no camera's key
# the a1 II's runs from before kit2 (in runs/ILCE-1M2_fw4.00/) that the kit still reads, besides its kit2_* runs: the
# screen reader's tests' frames and files (kit/tests/test_core.py, kit/tests/score_screen.py) and the menu twin's
# explore_stills/graph.jsonl (kit/camkit/twin.py). A prune of the runs keeps them
READ_BY_THE_KIT = ("explore_stills", "explore_stills_pre20261027", "rip_stills", "iq_map", "dg_mydial", "dg_wheel",
                   "ck_keys1", "ck_play_keys", "ck_play_keys2", "fn_run1", "dial_ctrl3")


@pytest.fixture(autouse=True)
def own_runs(tmp_path_factory, monkeypatch):
    top = tmp_path_factory.mktemp("runs")
    monkeypatch.setenv("CAMSET_RUNS", str(top))
    monkeypatch.setenv("CAMSET_CAMERA", TEST_CAMERA)
    # the coverage ledger's private files (each camera's looks file among them) in a folder of the test's own, never
    # the mapper's private/evidence/ (camkit.coverage.looks_dir); and no ledger a test built kept for the next
    monkeypatch.setenv("CAMSET_LOOKS_DIR", str(tmp_path_factory.mktemp("looks")))
    import sys
    cov = sys.modules.get("camkit.coverage")
    if cov is not None:
        cov.forget()
    return top


# What every test gets for camlink (no_real_camera): it notes in its marker file that it was started, and answers a
# ready line saying it did not connect, so camkit.link raises; a test that swallows that still fails (the marker). It
# is started through a launcher of one path, as camlink is: a shell script, or a .cmd file on Windows
LINK_STUB = '''import json, sys
with open({marker!r}, "a", encoding="utf-8") as f:
    f.write(repr(sys.argv[1:]) + "\\n")
print(json.dumps({{"ok": False, "error": "a test started camlink (kit/tests/conftest.py's stub)"}}), flush=True)
sys.exit(3)
'''


@pytest.fixture(scope="session")
def link_stub(tmp_path_factory):
    """(the launcher that stands in for camlink, its marker file, a config path that is not there), once a session."""
    import os
    folder = tmp_path_factory.mktemp("no_camera")
    script, marker = folder / "camlink_stub.py", folder / "started.txt"
    script.write_text(LINK_STUB.format(marker=str(marker)), encoding="utf-8")
    if os.name == "nt":
        stub = folder / "camlink_stub.cmd"
        stub.write_text(f'@"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        stub = folder / "camlink_stub"
        stub.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        stub.chmod(0o755)
    return stub, marker, folder / "no_such_config.json"


@pytest.fixture(autouse=True)
def no_real_camera(link_stub, monkeypatch):
    """No test reaches the camera or reads the owner's private/config.json, whatever fakes it forgets: camkit.CONFIG is
    a file that is not there and camlink a stub (LINK_STUB), in this process and, through CAMSET_CONFIG and
    CAMSET_LINK_BIN (camkit/__init__.py), in every kit program a test starts. A test that started the stub fails, naming
    what it was started with. A test's own config (camkit.CONFIG set to a file of its own) and its own stand-in link
    (kit/tests/fake_camlink.py, or binary= given) are untouched."""
    import camkit
    import camkit.link
    stub, marker, config = link_stub
    real, owners = camkit.LINK_BIN, camkit.CONFIG
    monkeypatch.setattr(camkit, "CONFIG", config)
    monkeypatch.setattr(camkit, "LINK_BIN", stub)
    monkeypatch.setattr(camkit.link, "LINK_BIN", stub)
    # Link's binary= defaults to the camlink its module took when it was imported
    defaults = camkit.link.Link.__init__.__defaults__
    monkeypatch.setattr(camkit.link.Link.__init__, "__defaults__", tuple(stub if d is real else d for d in defaults))
    monkeypatch.setenv("CAMSET_CONFIG", str(config))
    monkeypatch.setenv("CAMSET_LINK_BIN", str(stub))
    seen = marker.read_text(encoding="utf-8") if marker.exists() else ""
    yield owners                        # the clone's own config (or CAMSET_CONFIG's): owner_config gives it back
    started = marker.read_text(encoding="utf-8")[len(seen):] if marker.exists() else ""
    if started:
        pytest.fail(f"the test started camlink (kit/tests/conftest.py's stub stood in for it), with {started.strip()}: "
                    "give it a stand-in link (kit/tests/fake_camlink.py, or the no_camera fixture)")


@pytest.fixture
def owner_config(no_real_camera, monkeypatch):
    """The owner's private/config.json back for a test that reads it on purpose (the HDMI crop it checks against the
    a1 II's saved frames), for that test alone and in the programs it starts; camlink stays the stub. The test skips
    where there is none (a fresh clone, CI). Returns its path."""
    import camkit
    if not no_real_camera.is_file():
        pytest.skip(f"no config of the owner's here ({no_real_camera})")
    monkeypatch.setattr(camkit, "CONFIG", no_real_camera)
    monkeypatch.setenv("CAMSET_CONFIG", str(no_real_camera))
    return no_real_camera


@pytest.fixture(autouse=True)
def no_scan_mode(monkeypatch):
    """No test inherits the shooting mode another test's page scan set (camkit.session.MODE, which runner.load_scan
    sets and the menu's lock after a download goes by)."""
    import sys
    s = sys.modules.get("camkit.session")
    if s is not None:
        monkeypatch.setattr(s, "MODE", None)


# The test modules whose kit/drive.py runs open, with Right or Enter and more presses after it, rows of a made-up
# camera that has no looks or crawls: on a real body each would be a first open (camkit.first_open), refused before it
# connects unless the press is Right alone (29 tests, 2026-11-15)
DRIVES_MADE_UP_ROWS = ("test_guards", "test_network_rows")


@pytest.fixture(autouse=True)
def rows_seen(request, monkeypatch):
    """In DRIVES_MADE_UP_ROWS every row reads as seen, as on a body the kit has crawled, so their runs test what they
    test; everywhere else the camera's own records decide (kit/tests/test_first_open.py)."""
    if request.module.__name__ not in DRIVES_MADE_UP_ROWS:
        return
    from camkit import first_open
    monkeypatch.setattr(first_open, "seen_record", lambda camera=None: _AllSeen())


class _AllSeen:
    """rows_seen's record: every row seen."""
    opened: set = set()

    def seen(self, path) -> bool:
        return bool(path)

    def unseen(self, path) -> list:
        return []

    def lit_row(self, parent, lit, known=()) -> tuple:
        return (*parent, lit)


@pytest.fixture(autouse=True)
def own_umask():
    """The process's umask and camkit.runs.UMASK_FLOOR as they were before the test, put back after it: a private run
    (camkit.runs.Run.make_private, a --network or --owner run's) sets both for its process, and no test's run reaches
    another's file modes."""
    import os
    import sys
    mask = os.umask(0o022)
    os.umask(mask)
    yield
    os.umask(mask)
    runs = sys.modules.get("camkit.runs")
    if runs is not None:
        runs.UMASK_FLOOR = 0


@pytest.fixture(autouse=True)
def fresh_budget():
    """camkit.budget's start phases cleared before and after every test (taken), and the ledgers being built in the
    background waited for (camkit.coverage.forget), so no test's start budget or ledger reaches another's. Only once
    some test has imported them."""
    import sys

    def forget():
        b = sys.modules.get("camkit.budget")
        if b is not None:
            b.taken()
    forget()
    yield
    cov = sys.modules.get("camkit.coverage")
    if cov is not None:
        cov.forget()
    forget()


@pytest.fixture(autouse=True)
def fresh_readers():
    """camkit.vlm's state for one run cleared before and after every test (vlm.forget: the start check's verdict, the
    readers it skipped, the stand-ins, the failures said and the run they are logged in), so that no test's run
    reaches another's. Only once some test has imported it: none is imported here."""
    import sys

    def forget():
        vlm = sys.modules.get("camkit.vlm")
        if vlm is not None:
            vlm.forget()
    forget()
    yield
    forget()


def _files(top: Path) -> dict:
    return {p: (st.st_size, st.st_mtime_ns) for p in top.rglob("*") if p.is_file() and (st := p.stat())} \
        if top.is_dir() else {}


@pytest.fixture(autouse=True)
def guard_the_clones_files():
    """Fails the test that added, changed, moved or deleted a file of the clone's data/ or private/evidence/: the
    tests work on folders of their own (a test that patches definitions.EVIDENCE_DIR alone must still never reach the
    real data/)."""
    before = {top: _files(top) for top in GUARDED}
    yield
    for top in GUARDED:
        after = _files(top)
        if after != before[top]:
            changed = sorted({str(p.relative_to(ROOT)) for p in set(after) ^ set(before[top])}
                             | {str(p.relative_to(ROOT)) for p in after if p in before[top] and after[p] != before[top][p]})
            pytest.fail(guard_words(changed))


def guard_words(changed: list) -> str:
    """What guard_the_clones_files fails a test with: the files, and the other cause than the test itself."""
    return (f"the test changed the clone's own files: {changed}. If this test does not write them, a kit command that "
            "writes them running at the same time as the tests can cause it (kit/schema_update.py --write, or a prover "
            "in another terminal): run the tests again once it has finished.")


class Eyes:
    """camkit.reading's eyes, faked in one place (the eyes fixture): what each OCR engine reads on each frame (see),
    what each reader answers to each question (answer), the readers configured and their models (models: role ->
    model; a role missing has no reader), and every question asked (asked: the camkit.vlm.PROMPTS keys in order, the
    "third" reader's as "third <key>"). A question with no answer given raises camkit.vlm.NoReader, as a config listing
    no reader does."""

    def __init__(self, folder: Path):
        self.folder, self.lines, self.answers, self.asked = folder, {}, {}, []
        self.engine = "apple"       # the configured OCR engine (camkit.ocr.engine)
        self.second = None          # the second OCR engine's name (camkit.ocr.second), None: not installed
        self.models = {"second": "fake-model"}

    def frame(self, name: str, bar=None, dark: bool = False):
        """A 640 x 480 frame saved as `name` (bytes of its own, so two frames never share an answer), black when dark,
        with the cursor's orange bar at bar (x0, y0, x1, y1) when given."""
        import types

        import numpy as np
        a = np.full((480, 640, 3), 0 if dark else 24, np.uint8)
        if bar:
            x0, y0, x1, y1 = bar
            a[y0:y1, x0:x1] = (235, 90, 20)          # the cursor's orange (camkit.screen._planes)
        path = self.folder / name
        path.write_bytes(f"frame {name}".encode())
        return types.SimpleNamespace(image=a, path=path)

    def see(self, frame, text: str, box=(0, 0, 640, 480), conf: float = 1.0, eng=None):
        """OCR (eng: the second engine's name; None: the configured one) reads text on frame, filling box."""
        from camkit import ocr
        x0, y0, x1, y1 = box
        self.lines.setdefault((frame.path.name, eng), []).append(ocr.Line(text, conf, x0, y0, x1 - x0, y1 - y0))

    def answer(self, prompt: str, reply, role: str = "second"):
        """The answer of role's reader to camkit.vlm.PROMPTS[prompt]: a dict, an exception to raise, or a function of
        the frame's bytes giving either."""
        self.answers[(role, prompt)] = reply

    def ocr_lines(self, frame, eng=None):
        return list(self.lines.get((frame.path.name, eng), []))

    def reader_model(self, role: str):
        return self.models.get(role)

    def reader_answer(self, image: bytes, question: str, timeout: float, role: str = "second"):
        from camkit import vlm
        key = next(k for k, v in vlm.PROMPTS.items() if v == question)
        self.asked.append(key if role == "second" else f"{role} {key}")
        if role not in self.models:
            raise vlm.NoReader(f"no reader for the {role} role")
        reply = self.answers.get((role, key))
        reply = reply(image) if callable(reply) else reply
        if reply is None:
            raise vlm.NoReader(f"no answer given for {key!r}")
        if isinstance(reply, BaseException):
            raise reply
        return reply, f"fake {role}", self.models[role]


@pytest.fixture
def no_camera(monkeypatch):
    """Every way a kit program reaches the camera made to fail the test: the link (camkit.link.Link), a prover's
    session (runner.prover_session), the eyes (camkit.frames.eyes_from_config) and a run's folder (camkit.runs.Run),
    where they are defined and in every kit module already holding them by name (one imported later takes the failing
    one from where it is defined). What a --list must never touch: it prints the plan and sends nothing."""
    import sys
    for p in (ROOT / "kit", ROOT / "kit" / "provers"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import camkit.frames
    import camkit.link
    import camkit.runs
    import runner

    def reached(*a, **k):
        pytest.fail("the camera was reached (a link, a session, the eyes or a run's folder) where nothing may be sent")
    real = {"Link": camkit.link.Link, "prover_session": runner.prover_session,
            "eyes_from_config": camkit.frames.eyes_from_config, "Run": camkit.runs.Run}
    for mod in list(sys.modules.values()):
        if not str(getattr(mod, "__file__", "") or "").startswith(str(ROOT / "kit")):
            continue
        for name, obj in real.items():
            if getattr(mod, name, None) is obj:
                monkeypatch.setattr(mod, name, reached)


@pytest.fixture
def eyes(tmp_path, monkeypatch):
    """camkit.reading's OCR and reader seams faked (Eyes), its memo and latches cleared before and after."""
    from camkit import ocr, reading
    e = Eyes(tmp_path)
    monkeypatch.setattr(reading, "_ocr_lines", e.ocr_lines)
    monkeypatch.setattr(reading, "_reader_answer", e.reader_answer)
    monkeypatch.setattr(reading, "_reader_model", e.reader_model)
    monkeypatch.setattr(ocr, "engine", lambda: e.engine)
    monkeypatch.setattr(ocr, "second", lambda: e.second)
    reading.forget()
    yield e
    reading.forget()
