"""Every test has a runs/ folder of its own (CAMSET_RUNS) and a made-up camera (CAMSET_CAMERA), so no test, nor a kit
command a test starts, reads or writes the runs of the clone it runs in (docs/decisions/0015: the owner's runs are
evidence). The a1 II's frames some tests read are found by their own path (camkit.paths.a1ii_root()), and those
tests skip without them. Nor does any test change a file of the clone's own data/ or private/evidence/ (the
mapper's evidence: guard_the_clones_files), whatever folder it points the kit at. A test that reads the screen through
camkit.reading fakes both its eyes, OCR and the reader, in one place: the eyes fixture (Eyes)."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GUARDED = (ROOT / "data", ROOT / "private" / "evidence")

TEST_CAMERA = "TEST-CAM_fw9.99"          # made up: no camera's key


@pytest.fixture(autouse=True)
def own_runs(tmp_path_factory, monkeypatch):
    top = tmp_path_factory.mktemp("runs")
    monkeypatch.setenv("CAMSET_RUNS", str(top))
    monkeypatch.setenv("CAMSET_CAMERA", TEST_CAMERA)
    return top


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
            "writes them running at the same time as the tests can cause it (kit/schema_update.py --write, "
            "kit/tools/move_evidence.py or a prover in another terminal): run the tests again once it has finished.")


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
