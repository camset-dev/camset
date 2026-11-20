"""kit/provers/greyrow_run.py: each --row gone to through the page scan and asked why it is grey (proving.greyrow), a
line a row in the run's folder, a row's one Right spent once per run folder, mode and context, the row and the context
compared as the kit resolves and folds them, a STOP's line written before the session's close, and another body refused
before anything is sent. The session and the camera's records are stood in for; tests/test_greyrow.py holds the
procedure's own."""
import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers", KIT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import greyrow_run as G  # noqa: E402
import test_greyrow as T  # noqa: E402   (its made-up camera)
from camkit import first_open, paths  # noqa: E402
from camkit.link import StopRequested  # noqa: E402
from proving import greyrow  # noqa: E402

FS = ("labels", "framing stabilizer")
LUT = ("labels", "select lut")
# a page scan of one row, "Proxy Settings": "Px Proxy Settings" (its icon read as letters) is that row too (target_of)
CYCLE = [{"kind": "menu", "page": "k1", "row": 0}]
MODEL = {"k1": {"key": "k1", "breadcrumb": "Shooting > Proxy", "rows": [{"label": "Proxy Settings"}]}}


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
        {"mode": "Movie", "context": "", "path": ["A"], "keys": [["labels", "a"], ["row", "k1", 0]], "spent": True},
        {"mode": "Movie", "context": "", "path": ["B"], "keys": [["labels", "b"]], "spent": False},
        {"mode": "Movie", "context": "Touch Off", "path": ["C"], "keys": [["labels", "c"]], "spent": True},
        {"mode": "Movie", "context": "Touch Off", "path": ["E"], "spent": True},      # no keys: its labels folded
        {"mode": "Movie", "context": "Touch Off", "path": ["F"], "kind": "look", "keys": [["labels", "f"]]},
        {"mode": "Stills", "context": "", "path": ["D"], "keys": [["labels", "d"]], "spent": True})) + "\n",
        encoding="utf-8")
    assert G.spent_rows(f, "Movie", "") == {("labels", "a"), ("row", "k1", 0)}
    assert G.spent_rows(f, "Movie", "touch  off") == {("labels", "c"), ("labels", "e")}, "the context folded"


def test_a_rows_keys_are_its_folded_labels_and_the_row_the_scan_leads_to():
    assert G.row_keys([], {}, ["Framing  Stabilizer"]) == (FS,)
    assert G.row_keys(CYCLE, MODEL, ["Px Proxy Settings"]) == (("labels", "px proxy settings"), ("row", "k1", 0))
    assert G.row_keys(CYCLE, MODEL, ["Proxy Settings", "Proxy  Format"]) == (
        ("labels", "proxy settings", "proxy format"), ("row", "k1", 0, "proxy format"))


def test_a_row_the_kit_may_not_open_is_passed_over_before_anything_is_pressed(monkeypatch):
    monkeypatch.setattr(G, "stored_reason", lambda cycle, model, path: None)
    monkeypatch.setattr(G, "reach", lambda *a: pytest.fail("reached a row the kit may not open"))
    line = G.one_row(None, [], {}, ["Format"], Seen(), set(), (("labels", "format"),), set(), say=lambda m: None)
    assert (line["outcome"], line["right"]) == (greyrow.PASSED, False)


def test_a_row_the_scan_does_not_lead_to_is_not_reached_and_asked_nothing(monkeypatch):
    monkeypatch.setattr(G, "stored_reason", lambda cycle, model, path: None)

    def reach(*a):
        raise greyrow.Failed("Framing Stabilizer: the page scan does not lead to 'Framing Stabilizer' from here")
    monkeypatch.setattr(G, "reach", reach)
    monkeypatch.setattr(greyrow, "ask_why", lambda *a, **k: pytest.fail("asked a row not reached"))
    line = G.one_row(None, [], {}, ["Framing Stabilizer"], Seen(), set(), (FS,), set(), say=lambda m: None)
    assert (line["outcome"], line["right"]) == (G.NOT_REACHED, False)


def run_main(monkeypatch, rows, one_row, context="Touch Off", scan=([], {}), extra=(), real_one_row=False):
    """greyrow_run.main with its session and the camera's records stood in for; returns (the lines written, the keys
    each row was asked with and the rows spent before it, what was closed). real_one_row: the runner's own one_row,
    whatever the test stood in for under it, `one_row` unused."""
    asked, closed = [], []
    monkeypatch.setattr(G, "load_scan", lambda s: scan)
    monkeypatch.setattr(G, "known_labels", lambda model: set())
    monkeypatch.setattr(first_open, "seen_record", lambda camera=None: Seen())
    monkeypatch.setattr(G, "eyes_from_config", lambda run: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(G, "close_screen", lambda cam, link: closed.append("menu"))

    @contextlib.contextmanager
    def session(run, eyes, **kw):
        assert set(kw) == {"reach"}
        yield SimpleNamespace(cam="cam", link="link", start=Path("00001_before.DAT"))
    monkeypatch.setattr(G, "prover_session", session)

    def one(cam, cycle, model, path, seen, tried, keys, labels, say=None):
        asked.append((keys, set(tried)))
        return one_row(path, tried, keys)
    if not real_one_row:
        monkeypatch.setattr(G, "one_row", one)
    argv = ["greyrow_run.py", "--in", "Movie", "--context", context, "--run", "kit2_greyrow_test", *extra]
    for r in rows:
        argv += ["--row", r]
    monkeypatch.setattr(sys, "argv", argv)
    with contextlib.redirect_stdout(io.StringIO()):
        G.main()
    return lines_written(), asked, closed


def lines_written() -> list:
    f = paths.run_root() / "kit2_greyrow_test" / G.LINES
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def spend(path, tried, keys):
    tried.update(keys)
    return {"path": path, "right": True, "outcome": greyrow.NOTICE}


def test_the_runner_writes_a_line_a_row_and_spends_each_rows_right_once(monkeypatch):
    lines, asked, closed = run_main(monkeypatch, ["Framing Stabilizer", "Select LUT"], spend)
    assert [(x["path"], x["mode"], x["context"], x["start"], x["spent"], x["keys"]) for x in lines] == [
        (["Framing Stabilizer"], "Movie", "Touch Off", "00001_before.DAT", True, [list(FS)]),
        (["Select LUT"], "Movie", "Touch Off", "00001_before.DAT", True, [list(LUT)])]
    assert closed == ["menu", "menu"] and asked[0][1] == set()
    # the same run folder, mode and context again: both rows' Rights are spent, as the run's file says
    lines, asked, closed = run_main(monkeypatch, ["Framing Stabilizer"], spend)
    assert asked[0][1] == {FS, LUT}


def test_two_spellings_of_one_row_in_one_run_are_asked_once(monkeypatch):
    lines, asked, closed = run_main(monkeypatch, ["Framing Stabilizer", "framing stabilizer", "Framing  Stabilizer"],
                                    spend)
    assert [k for k, _ in asked] == [(FS,)] and len(lines) == 1 and closed == ["menu"]


def test_two_readings_the_scan_leads_to_one_row_are_asked_once(monkeypatch):
    """"Px Proxy Settings" folds to other labels than "Proxy Settings", but the page scan leads both to its one row."""
    lines, asked, closed = run_main(monkeypatch, ["Proxy Settings", "Px Proxy Settings"], spend, scan=(CYCLE, MODEL))
    assert [k for k, _ in asked] == [(("labels", "proxy settings"), ("row", "k1", 0))]


def test_a_rerun_spelling_the_row_or_wording_the_context_otherwise_gets_no_second_right(monkeypatch):
    run_main(monkeypatch, ["Proxy Settings"], spend, context="Touch Off", scan=(CYCLE, MODEL))
    lines, asked, closed = run_main(monkeypatch, ["Px Proxy Settings"], spend, context="touch  off", scan=(CYCLE, MODEL))
    assert ("row", "k1", 0) in asked[0][1], "spent under the row the scan leads to"
    lines, asked, closed = run_main(monkeypatch, ["Proxy Settings"], spend, context="Touch On", scan=(CYCLE, MODEL))
    assert asked[0][1] == set(), "another context is another state, which asks again"


def test_two_spellings_get_one_right_on_the_made_up_camera(monkeypatch):
    """The review's probe: the real one_row and ask_why on one made-up camera reached by every spelling."""
    cam = T.GreyCam()
    T.world(monkeypatch, cam)
    monkeypatch.setattr(G, "load_scan", lambda s: ([], {}))
    monkeypatch.setattr(G, "known_labels", lambda model: {"Touch Operation"})
    monkeypatch.setattr(first_open, "seen_record", lambda camera=None: first_open.Seen(opened={("framing stabilizer",)}))
    monkeypatch.setattr(G, "eyes_from_config", lambda run: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(G, "stored_reason", lambda cycle, model, path: None)
    monkeypatch.setattr(G, "reach", lambda c, cycle, model, path: setattr(c, "where", "row"))
    monkeypatch.setattr(G, "close_screen", lambda c, link: None)

    @contextlib.contextmanager
    def session(run, eyes, **kw):
        yield SimpleNamespace(cam=cam, link="link", start=Path("00001_before.DAT"))
    monkeypatch.setattr(G, "prover_session", session)
    monkeypatch.setattr(sys, "argv", ["greyrow_run.py", "--in", "Movie", "--run", "kit2_greyrow_probe",
                                      "--row", "Framing Stabilizer", "--row", "framing stabilizer",
                                      "--row", "Framing  Stabilizer"])
    with contextlib.redirect_stdout(io.StringIO()):
        G.main()
    assert cam.keys.count("right") == 1, cam.keys


def test_a_stop_in_a_row_writes_its_line_and_goes_up_to_the_session(monkeypatch):
    """The session's close and restore (runner.prover_session) take it from there: the row's line says its Right was
    spent, so no later run in that folder, mode and context gives it a second."""
    def one(path, tried, keys):
        tried.update(keys)
        raise StopRequested("STOP file")
    with pytest.raises(StopRequested):
        run_main(monkeypatch, ["Framing Stabilizer", "Select LUT"], one)
    assert [(x["path"], x["outcome"], x["right"], x["spent"]) for x in lines_written()] == [
        (["Framing Stabilizer"], G.STOPPED, None, True)]


def test_a_playback_view_stops_the_run_with_its_line_written(monkeypatch):
    """The review's probe: after a Right brought up the playback view, no next row (its MENU would go out in Playback,
    then Downs and Rights in that menu): the row's line is written and the run goes up to the session's close, which
    leaves the view."""
    asked = []

    def ask_why(cam, path, **kw):
        asked.append(path)
        kw["tried"].update(kw["keys"])
        raise greyrow.StopsRun("the Right brought up the camera's playback view (00009_right.png)",
                               {"path": path, "right": True, "outcome": greyrow.PLAYBACK})
    monkeypatch.setattr(greyrow, "ask_why", ask_why)
    monkeypatch.setattr(G, "stored_reason", lambda cycle, model, path: None)
    monkeypatch.setattr(G, "reach", lambda *a: None)
    with pytest.raises(greyrow.StopsRun):
        run_main(monkeypatch, ["A", "B"], lambda path, tried, keys: None, real_one_row=True)
    assert asked == [["A"]]
    assert [(x["path"], x["outcome"], x["right"], x["spent"]) for x in lines_written()] == [
        (["A"], greyrow.PLAYBACK, True, True)]


def test_another_body_stops_the_session_before_anything_is_sent(monkeypatch):
    import proving.nav
    monkeypatch.setattr(first_open, "other_body", lambda link, camera: "the camera connected is ILCE-7M5_fw1.00")
    monkeypatch.setattr(proving.nav, "to_shooting", lambda *a: pytest.fail("a key was sent"))
    with pytest.raises(SystemExit, match="nothing was sent"):
        G.this_body_first("ILCE-1M2_fw4.00")("link", "eyes", "the start download")
    went = []
    monkeypatch.setattr(first_open, "other_body", lambda link, camera: "")
    monkeypatch.setattr(proving.nav, "to_shooting", lambda link, eyes, why: went.append(why))
    G.this_body_first("ILCE-1M2_fw4.00")("link", "eyes", "the start download")
    assert went == ["the start download"]
