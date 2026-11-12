"""Every test has a runs/ folder of its own (CAMSET_RUNS) and a made-up camera (CAMSET_CAMERA), so no test, nor a kit
command a test starts, reads or writes the runs of the clone it runs in (docs/decisions/0015: the owner's runs are
evidence). The a1 II's frames some tests read are found by their own path (camkit.paths.a1ii_root()), and those
tests skip without them. Nor does any test change a file of the clone's own data/ or private/evidence/ (the
mapper's evidence: guard_the_clones_files), whatever folder it points the kit at."""
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
