"""kit/provers/greyrow_run.py: each --row gone to through the page scan and asked why it is grey (proving.greyrow), a
line a row in the run's folder, a row's one Right spent once per run folder, mode and context, a STOP's line written
before the session's close, and another body refused before anything is sent. The session and the camera's records
are stood in for; tests/test_greyrow.py holds the procedure's own."""
import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import greyrow_run as G  # noqa: E402
from camkit import paths  # noqa: E402
from camkit.link import StopRequested  # noqa: E402
from proving import greyrow  # noqa: E402


class Seen:
    """camkit.first_open.Seen's two questions: every row seen opened."""

    def seen(self, path) -> bool:
        return True

    def unseen(self, path) -> list:
        return []


def test_row_paths_and_spent_rows(tmp_path):
    assert G.row_paths(["Framing Stabilizer", " Auto Framing Settings >  Framing Tracking Speed ", " "]) == [
        ["Framing Stabilizer"], ["Auto Framing Settings", "Framing Tracking Speed"]]
    f = tmp_path / G.LINES
    f.write_text("\n".join(json.dumps(x) for x in (
        {"mode": "Movie", "context": "", "path": ["A"], "spent": True},
        {"mode": "Movie", "context": "", "path": ["B"], "spent": False},
        {"mode": "Movie", "context": "Touch Off", "path": ["C"], "spent": True},
        {"mode": "Stills", "context": "", "path": ["D"], "spent": True})) + "\n", encoding="utf-8")
    assert G.spent_rows(f, "Movie", "") == {("Movie", "", ("A",))}
    assert G.spent_rows(f, "Movie", "Touch Off") == {("Movie", "Touch Off", ("C",))}


def test_a_row_the_kit_may_not_open_is_passed_over_before_anything_is_pressed(monkeypatch):
    monkeypatch.setattr(G, "stored_reason", lambda cycle, model, path: None)
    monkeypatch.setattr(G, "reach", lambda *a: pytest.fail("reached a row the kit may not open"))
    line = G.one_row(None, [], {}, ["Format"], Seen(), set(), ("Stills", "", ("Format",)), set(), say=lambda m: None)
    assert (line["outcome"], line["right"]) == (greyrow.PASSED, False)


def test_a_row_the_scan_does_not_lead_to_is_not_reached_and_asked_nothing(monkeypatch):
    monkeypatch.setattr(G, "stored_reason", lambda cycle, model, path: None)

    def reach(*a):
        raise greyrow.Failed("Framing Stabilizer: the page scan does not lead to 'Framing Stabilizer' from here")
    monkeypatch.setattr(G, "reach", reach)
    monkeypatch.setattr(greyrow, "ask_why", lambda *a, **k: pytest.fail("asked a row not reached"))
    line = G.one_row(None, [], {}, ["Framing Stabilizer"], Seen(), set(), ("Movie", "", ("Framing Stabilizer",)),
                     set(), say=lambda m: None)
    assert (line["outcome"], line["right"]) == (G.NOT_REACHED, False)


def run_main(monkeypatch, rows, one_row):
    """greyrow_run.main with its session and the camera's records stood in for; returns (the lines written, the key each
    row was asked with and the rows spent before it, what was closed)."""
    import camkit.first_open
    asked, closed = [], []
    monkeypatch.setattr(G, "load_scan", lambda scan: ([], {}))
    monkeypatch.setattr(G, "known_labels", lambda model: set())
    monkeypatch.setattr(camkit.first_open, "seen_record", lambda camera=None: Seen())
    monkeypatch.setattr(G, "eyes_from_config", lambda run: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(G, "close_screen", lambda cam, link: closed.append("menu"))

    @contextlib.contextmanager
    def session(run, eyes, **kw):
        assert set(kw) == {"reach"}
        yield SimpleNamespace(cam="cam", link="link", start=Path("00001_before.DAT"))
    monkeypatch.setattr(G, "prover_session", session)

    def one(cam, cycle, model, path, seen, tried, key, labels, say=None):
        asked.append((key, set(tried)))
        return one_row(path, tried, key)
    monkeypatch.setattr(G, "one_row", one)
    argv = ["greyrow_run.py", "--in", "Movie", "--context", "Touch Off", "--run", "kit2_greyrow_test"]
    for r in rows:
        argv += ["--row", r]
    monkeypatch.setattr(sys, "argv", argv)
    with contextlib.redirect_stdout(io.StringIO()):
        G.main()
    return lines_written(), asked, closed


def lines_written() -> list:
    f = paths.run_root() / "kit2_greyrow_test" / G.LINES
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def test_the_runner_writes_a_line_a_row_and_spends_each_rows_right_once(monkeypatch):
    def one(path, tried, key):
        tried.add(key)
        return {"path": path, "right": True, "outcome": greyrow.NOTICE}
    lines, asked, closed = run_main(monkeypatch, ["Framing Stabilizer", "Select LUT"], one)
    assert [(x["path"], x["mode"], x["context"], x["start"], x["spent"]) for x in lines] == [
        (["Framing Stabilizer"], "Movie", "Touch Off", "00001_before.DAT", True),
        (["Select LUT"], "Movie", "Touch Off", "00001_before.DAT", True)]
    assert closed == ["menu", "menu"] and asked[0][1] == set()
    # the same run folder, mode and context again: both rows' Rights are spent, as the run's file says
    lines, asked, closed = run_main(monkeypatch, ["Framing Stabilizer"], one)
    assert asked[0][1] == {("Movie", "Touch Off", ("Framing Stabilizer",)), ("Movie", "Touch Off", ("Select LUT",))}


def test_a_stop_in_a_row_writes_its_line_and_goes_up_to_the_session(monkeypatch):
    """The session's close and restore (runner.prover_session) take it from there: the row's line says its Right was
    spent, so no later run in that folder, mode and context gives it a second."""
    def one(path, tried, key):
        tried.add(key)
        raise StopRequested("STOP file")
    with pytest.raises(StopRequested):
        run_main(monkeypatch, ["Framing Stabilizer", "Select LUT"], one)
    assert [(x["path"], x["outcome"], x["right"], x["spent"]) for x in lines_written()] == [
        (["Framing Stabilizer"], G.STOPPED, None, True)]


def test_another_body_stops_the_session_before_anything_is_sent(monkeypatch):
    import camkit.first_open
    import proving.nav
    monkeypatch.setattr(camkit.first_open, "other_body", lambda link, camera: "the camera connected is ILCE-7M5_fw1.00")
    monkeypatch.setattr(proving.nav, "to_shooting", lambda *a: pytest.fail("a key was sent"))
    with pytest.raises(SystemExit, match="nothing was sent"):
        G.this_body_first("ILCE-1M2_fw4.00")("link", "eyes", "the start download")
    went = []
    monkeypatch.setattr(camkit.first_open, "other_body", lambda link, camera: "")
    monkeypatch.setattr(proving.nav, "to_shooting", lambda link, eyes, why: went.append(why))
    G.this_body_first("ILCE-1M2_fw4.00")("link", "eyes", "the start download")
    assert went == ["the start download"]
