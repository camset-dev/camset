"""A row's first open on a body (camkit.first_open), the owner's statements (camkit.statements,
kit/tools/owner_statement.py) and the one picture (kit/tools/take_picture.py, camkit.link's picture link), off the
camera: fakes stand in for it, and the stand-in camlink (fake_camlink.py) for the link where the protocol matters."""
import ast
import contextlib
import io
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fake_camlink  # noqa: E402
from camkit import camset, coverage, first_open, safety, statements  # noqa: E402
from camkit.link import Link, LinkError, StopRequested  # noqa: E402
from camkit.runs import RESTORE_BY_HAND, Run, restore_pending  # noqa: E402
from conftest import TEST_CAMERA  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DAY = "2026-11-15"
BLANK = {"date": DAY, "cards": "blank", "why": "typed"}
SKIPPED = first_open.SKIPPED


@pytest.fixture
def scope(own_runs, monkeypatch):
    """write(*decisions): the camera's reviewed scope with those decisions, where runner.reviewed_scope finds it."""
    from proving import base
    pass1 = own_runs / TEST_CAMERA / "kit2_pass1"
    monkeypatch.setattr(base, "PASS1", pass1)

    def write(*decisions):
        pass1.mkdir(parents=True, exist_ok=True)
        f = pass1 / "pass2_scope_draft.json"
        f.write_text(json.dumps({"prove": [], "exclude": {}, "decisions": list(decisions)}), encoding="utf-8")
        return f
    write.file = pass1 / "pass2_scope_draft.json"
    return write


def look(path, did="open", result="looked", **kw):
    return {"t": "2026-11-15T10:00:00", "by": "crawl", "path": list(path), "did": did, "result": result, **kw}


def looks_of(camera, *entries):
    for e in entries:
        assert coverage.append_look(camera, e)


def latest_open(camera, path):
    got = [lk for _, lk in coverage.read_looks(camera) if lk.get("did") == "open" and lk.get("path") == list(path)]
    return got[-1] if got else None


# ------------------------------------------------------------------------------------------------- the statements

def test_a_cards_statement_is_current_only_while_the_latest_says_blank():
    assert "owner_statement.py cards" in statements.cards_refused({})
    assert statements.cards_refused({"decisions": [BLANK]}) == ""
    withdrawn = {"date": DAY, "cards": "withdrawn", "why": "my own card is back"}
    assert "withdrew" in statements.cards_refused({"decisions": [BLANK, withdrawn]})
    assert statements.cards_refused({"decisions": [withdrawn, BLANK]}) == ""
    for bad in ({**BLANK, "rows": ["Format"]}, {**BLANK, "date": "2099-01-01"}, {**BLANK, "why": " "},
                {**BLANK, "cards": "yes"}):
        assert "no statement the kit reads" in statements.cards_refused({"decisions": [bad]}), bad


def test_a_statement_lifts_nothing_no_decision_reader_takes_it():
    scope = {"decisions": [BLANK, {"date": DAY, "picture": "once", "why": "typed"}]}
    assert safety.approved_rows(scope) == set()
    assert safety.network_decided(scope) == ({}, [])
    assert safety.owner_decided(scope)["rows"] == {} and safety.owner_decided(scope)["refusals"] == []


def test_the_question_is_answered_only_at_a_terminal_by_the_word():
    said = []
    assert statements.ask("Q?", "blank", read=lambda p: "Blank", tty=True, env={}) == ""
    assert "not 'blank'" in statements.ask("Q?", "blank", read=lambda p: "yes", tty=True, env={})
    assert "no terminal" in statements.ask("Q?", "blank", read=lambda p: said.append(p) or "blank", tty=False, env={})
    assert said == []                                       # a pipe is never read
    why = statements.ask("Q?", "blank", read=lambda p: said.append(p) or "blank", tty=True, env={"CLAUDECODE": "1"})
    assert "agent" in why and said == []                    # nor an agent's shell, a pseudo-terminal or not


def test_owner_statement_writes_the_answer_dated_and_withdraws_without_asking(scope, capsys):
    import owner_statement
    with pytest.raises(SystemExit) as e:
        owner_statement.main(["cards"], read=lambda p: "no", tty=True, env={})
    assert "nothing was written" in str(e.value) and not scope.file.exists()
    owner_statement.main(["cards"], read=lambda p: "blank", tty=True, env={})
    got = json.loads(scope.file.read_text(encoding="utf-8"))
    assert got["decisions"][-1]["cards"] == "blank" and "exclude" in got             # started from the template
    assert "only the camera's owner answers" in capsys.readouterr().out.lower()
    owner_statement.main(["cards", "--withdraw"], tty=False, env={"AI_AGENT": "x"})
    assert "withdrew" in statements.cards_refused(json.loads(scope.file.read_text(encoding="utf-8")))


def test_a_pipe_cannot_answer_owner_statement(own_runs):
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "owner_statement.py"), "cards"], input="blank\n",
                       capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and ("no terminal" in r.stderr or "agent" in r.stderr)
    assert not (own_runs / TEST_CAMERA / "kit2_pass1" / "pass2_scope_draft.json").exists()


# ------------------------------------------------------------------------------------------- seen opened on a body

def test_seen_comes_from_the_looks_the_crawls_and_the_proofs(own_runs):
    looks_of(TEST_CAMERA, look(["Looked"]), look(["Greyed"], result="greyed"), look(["Chose"], "choose", "changed"),
             look(["Acted"]), look(["Acted"], result="changed"), look(["Gone"]), look(["Gone"], result="retract"),
             look(["A", "B"], result="no_change"), look(["Lapsed"]), look(["Lapsed"], result="not_reached"),
             look(["Pending"], result="not_reached", note=first_open.PENDING),
             look(["Paged"], result="not_reached", note=first_open.PAGE), look(["Acted"], result="greyed"))
    run = own_runs / TEST_CAMERA / "kit2_crawl"
    run.mkdir(parents=True)
    rows = [{"label": "Walked", "outcome": "walked"}, {"label": "Notice", "outcome": "notice"},
            {"label": "Lost", "outcome": "lost"}, {"label": "Silent", "outcome": "no response to Right"},
            {"label": "Partly", "outcome": "incomplete: KeyError"}, {"label": "Pending", "outcome": "walked"},
            {"label": "Sub", "outcome": "submenu crawled", "submenu": [{"label": "Child", "outcome": "walked"}]}]
    (run / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (run / "proofs.jsonl").write_text(json.dumps({"path": ["PP", "PP1", "Knee"]}) + "\n", encoding="utf-8")
    seen = first_open.seen_record(TEST_CAMERA)
    for p in (["Looked"], ["chose"], ["A"], ["A", "B"], ["Walked"], ["Sub"], ["Sub", "Child"], ["PP", "PP1"],
              ["Lapsed"]):
        assert seen.seen(p), p
    for p in (["Greyed"], ["Acted"], ["Gone"], ["Notice"], ["Lost"], ["Never"], ["Silent"], ["Partly"], ["Pending"],
              ["Paged"]):
        assert not seen.seen(p), p
    assert ("acted",) in seen.acting and seen.alone == {("paged",)} and {("greyed",), ("notice",)} <= seen.greyed
    assert seen.unseen(["Sub", "Other"]) == [("Sub", "Other")] and seen.unseen(["X", "Y"]) == [("X",), ("X", "Y")]


def test_a_row_whose_label_was_not_read_is_never_seen(tmp_path):
    """A page model row no vote named (label None: "BISO"/"RISO"/"ISO" in the a1 II's older scans) is crawled with an
    empty label: its clean first open never makes it, nor any other such row, seen (2026-11-15, a review)."""
    seen = first_open.Seen({("",), ("a",), ("a", "")})
    assert seen.seen(["A"]) and not seen.seen([""]) and not seen.seen(["A", ""])
    fo, sent, _ = first_opens(tmp_path)
    assert fo.opening(("",)) is None and fo.pending == [("",)]
    fo.settle(SimpleNamespace(press=lambda key: None))
    assert sent == ["first-open"] and fo.opening(("",)) is None and fo.pending == [("",)]     # the procedure again


def test_a_new_body_has_seen_nothing():
    assert not first_open.seen_record(TEST_CAMERA).seen(["Drive Mode"])
    assert not first_open.seen_record("NO-CAM_fw1.00").seen(["Drive Mode"])


def says(model="ILCE-1M2", firmware="4.00", ok=True):
    """A stand-in link whose props name `model` and `firmware` (None: not among them)."""
    props = [{"name": n, "text": t} for n, t in (("ModelName", model), ("CrDeviceProperty_SoftwareVersion", firmware))
             if t is not None]
    return SimpleNamespace(model="ILCE-1M2", call=lambda cmd, timeout=None, logged=None: {"ok": ok, "props": props})


def test_another_body_than_the_key_names_is_said_by_its_own_model_and_firmware(tmp_path, monkeypatch):
    assert first_open.other_body(says(), "ILCE-1M2_fw4.00") == ""
    assert "is ILCE-7M4_fw2.00" in first_open.other_body(says("ILCE-7M4", "2.00"), "ILCE-1M2_fw4.00")
    assert "is ILCE-1M2_fw3.00" in first_open.other_body(says(firmware="3.00"), "ILCE-1M2_fw4.00")     # firmware
    for link in (says(firmware=None), says(model=None), SimpleNamespace(model="ILCE-1M2")):
        assert "did not say its model and firmware" in first_open.other_body(link, "ILCE-1M2_fw4.00")
    assert first_open.other_body(SimpleNamespace(), "kit2_test_folder") == ""          # no camera's key: a test's
    # over the stand-in camlink: the log keeps neither the props nor any other property
    monkeypatch.setenv("FAKE_CAMLINK_PROPS", json.dumps([{"name": "ModelName", "text": "ILCE-1M2"},
                                                         {"name": "SoftwareVersion", "text": "4.00"},
                                                         {"name": "BodySerialNumber", "text": "00000000"}]))
    run = Run("kit2_crawl", root=tmp_path)
    with Link(run, ip="192.0.2.10", binary=fake_camlink.COMMAND, catch_signals=False) as link:
        assert first_open.other_body(link, "ILCE-1M2_fw4.00") == ""
        assert "is ILCE-1M2_fw4.00" in first_open.other_body(link, "ILCE-1M2_fw3.00")
    assert "00000000" not in (run.dir / "events.jsonl").read_text(encoding="utf-8")


# ------------------------------------------------------------------------------------------------ the crawl's way

class Marked:
    """test_core's FakeMenu, keeping at each Right whether RESTORE_BY_HAND was there and the row's latest open look."""

    def __init__(self, root: Path, refuse=(), astray=False):
        from test_core import FakeMenu
        self.menu, self.root, self.refuse, self.marks, self.astray = FakeMenu(True), root, refuse, [], astray
        self.looks = {}

    def press(self, key, **kw):
        if key == "right":
            label = self.label()
            if label in self.refuse:
                raise safety.RowRefused(f"refused {label}")
            self.marks.append((label, (self.root / RESTORE_BY_HAND).exists()))
            got = [lk for _, lk in coverage.read_looks(self.root.name) if lk.get("path", [""])[-1] == label]
            self.looks[label] = got[-1].get("note") if got else None
        if key == "menu" and self.astray and self.menu.where[0] == "shooting":
            self.menu.where = ("top", (self.menu.last_menu[1] + 1) % 3)      # the menu reopens on another row
            return
        self.menu.press(key)

    def label(self):
        w = self.menu.where
        return self.menu.TOP[w[1]] if w[0] == "top" else self.menu.SUB[w[1]] if w[0] == "sub" else None

    def read(self):
        return self.menu.read()

    def labels(self, cam):
        return self.menu.labels(cam)


CYCLE = [{"page": "P", "row": i, "signature": f"top{i}", "kind": "menu"} for i in range(3)]
MODEL = {"P": {"breadcrumb": "Shooting > Test", "page": "1/1",
               "rows": [{"label": x, "never_open": None} for x in ("A", "Sub", "B")]}}


def lap(root, first, refuse=(), astray=False, cycle=CYCLE):
    from camkit.crawl import crawl
    cam = Marked(root, refuse, astray)
    return cam, crawl(cam, cycle, MODEL, labels=cam.labels, first=first)


def first_opens(tmp_path, seen=None, skip_why="", download=None, gone="", per="row", ping=True):
    start = tmp_path / "start.DAT"
    shutil.copy(fake_camlink.SAMPLE, start)
    sent = []

    def fetch(tag):
        sent.append(tag)
        if download:
            return download(tag)
        out = tmp_path / f"{len(sent)}_{tag}.DAT"
        shutil.copy(fake_camlink.SAMPLE, out)
        return out
    link = SimpleNamespace(download=fetch, gone=lambda: gone,
                           call=lambda cmd, timeout=None: sent.append(cmd) or {"ok": ping, "connected": ping})
    run = Run("kit2_crawl", root=tmp_path)
    fo = first_open.FirstOpens(link, None, run, start, seen or first_open.Seen(), skip_why, 0,
                               wait=lambda *a, **k: None, per=per)
    return fo, sent, run


def test_a_first_open_is_marked_and_its_look_pending_before_its_right_and_checked_before_the_marker_goes(tmp_path):
    fo, sent, run = first_opens(tmp_path)
    cam, out = lap(tmp_path, fo)
    assert out.stopped == "" and {r.label: r.outcome for r in out.rows} == {"A": "walked", "Sub": "submenu crawled",
                                                                              "B": "walked"}
    # every Right went with the marker there (the submenu's way back into it after S2's notice too) and its row's
    # pending look written
    assert all(marked for _, marked in cam.marks) and {x for x, _ in cam.marks} == {"A", "Sub", "S1", "S2 greyed", "S4",
                                                                                     "B"}
    assert all(cam.looks[x] == first_open.PENDING for x in ("A", "Sub", "S1", "S4", "B"))
    assert sent == ["first-open"] * 3                       # one check per top-level row, the submenu's with its row
    assert not restore_pending(tmp_path) and fo.marker is None
    # the next lap: the rows are seen, so they open plainly
    cam, out = lap(tmp_path, fo)
    assert out.stopped == "" and sent == ["first-open"] * 3 and not any(marked for _, marked in cam.marks)


def test_a_crawl_killed_between_the_right_and_the_check_leaves_the_row_unseen(tmp_path):
    fo, _sent, run = first_opens(tmp_path)
    assert fo.opening(("A",)) is None
    (tmp_path / "kit2_crawl" / "rows.jsonl").write_text(json.dumps({"label": "A", "outcome": "walked"}) + "\n",
                                                        encoding="utf-8")
    looks_of(tmp_path.name, look(["B"]))                     # a look written meanwhile, of another row
    seen = first_open.seen_record(tmp_path.name)
    assert not seen.seen(["A"]) and ("a",) not in seen.acting and seen.seen(["B"])


def test_a_pending_rows_look_is_held_until_its_check_and_written_after_it(tmp_path):
    fo, _sent, run = first_opens(tmp_path)
    fo.opening(("A",))
    assert fo.takes(look(["A"])) and not fo.takes(look(["Other"]))
    assert latest_open(tmp_path.name, ["A"])["note"] == first_open.PENDING
    fo.settle(SimpleNamespace(press=lambda key: None))
    assert latest_open(tmp_path.name, ["A"])["result"] == "looked" and first_open.seen_record(tmp_path.name).seen(["A"])


def test_a_row_seen_before_opens_plainly(tmp_path):
    fo, sent, _ = first_opens(tmp_path, first_open.Seen({("a",), ("sub",), ("sub", "s1"), ("sub", "s2 greyed"),
                                                          ("sub", "s4")}))
    cam, out = lap(tmp_path, fo)
    assert sent == ["first-open"] and dict(cam.marks) == {"A": False, "Sub": False, "S1": False, "S2 greyed": False,
                                                          "S4": False, "B": True}


def test_without_the_statement_an_unseen_row_is_skipped_recorded_and_counted(tmp_path, monkeypatch):
    fo, sent, _ = first_opens(tmp_path, first_open.Seen({("a",), ("sub",)}), skip_why="no statement (do this)")
    cam, out = lap(tmp_path, fo)
    rows = {r.label: r.outcome for r in out.rows}
    assert rows["B"] == f"{SKIPPED} (no statement (do this))" and out.stopped == ""
    assert [x for x, _ in cam.marks] == ["A", "Sub"] and sent == [] and not restore_pending(tmp_path)
    assert all(r.outcome.startswith(SKIPPED) for r in out.rows[1].walk.rows if r.label != "Forced File Number Reset")
    import crawl_run
    assert sum(crawl_run.unseen_skips(r) for r in out.rows) == 4
    run = tmp_path / "counted"
    run.mkdir()
    (run / "rows.jsonl").write_text("".join(json.dumps(crawl_run.summary(r)) + "\n" for r in out.rows), encoding="utf-8")
    assert coverage.crawl_skipped(run, SKIPPED) == 4 and coverage.crawl_skipped(run) == 0


def test_a_row_whose_first_open_failed_is_skipped_and_named_for_drive(tmp_path):
    fo, sent, _ = first_opens(tmp_path, first_open.Seen({("a",), ("sub",), ("sub", "s1"), ("sub", "s2 greyed"),
                                                          ("sub", "s4")}, acting={("b",)}))
    cam, out = lap(tmp_path, fo)
    assert out.rows[2].outcome.startswith(SKIPPED) and "drive.py --path 'B' --press right" in out.rows[2].outcome
    assert sent == [] and "B" not in dict(cam.marks)


def test_a_refused_right_takes_its_marker_away_but_not_while_another_row_is_pending(tmp_path):
    fo, sent, _ = first_opens(tmp_path, first_open.Seen({("sub",), ("sub", "s1"), ("sub", "s2 greyed"), ("sub", "s4"),
                                                          ("b",)}))
    cam, out = lap(tmp_path, fo, refuse=("A",))
    assert out.rows[0].outcome.startswith("skipped: refused") and sent == [] and fo.marker is None
    assert not restore_pending(tmp_path)
    fo, sent, _ = first_opens(tmp_path)
    fo.opening(("A",))
    fo.opening(("B",))
    fo.not_opened(("B",))
    assert fo.pending == [("A",)] and restore_pending(tmp_path)


def test_a_marker_or_a_pending_look_not_written_opens_nothing(tmp_path, monkeypatch):
    fo, _sent, run = first_opens(tmp_path)
    calls = []

    def half(root, *a):
        (Path(root) / RESTORE_BY_HAND).write_text("{}", encoding="utf-8")
        raise OSError("the second place is read-only")
    real = first_open.mark_restore_by_hand
    monkeypatch.setattr(first_open, "mark_restore_by_hand", half)
    assert fo.opening(("A",)).startswith(f"{first_open.UNSEEN} (RESTORE_BY_HAND could not be written")
    assert not restore_pending(tmp_path) and fo.marker is None and fo.pending == []
    monkeypatch.setattr(first_open, "mark_restore_by_hand", real)
    monkeypatch.setattr(first_open, "failed_look", lambda *a, **k: calls.append(a) or False)
    assert "pending look could not be recorded" in fo.opening(("A",)) and not restore_pending(tmp_path)


def test_a_record_that_differs_keeps_the_marker_and_the_row_skipped_after(tmp_path, monkeypatch):
    from camkit import session
    monkeypatch.setattr(session, "compared", lambda a, b, say=None: [SimpleNamespace(key="global:0x0357")])
    fo, sent, run = first_opens(tmp_path)
    with pytest.raises(first_open.FirstOpenFailed) as e:
        lap(tmp_path, fo)
    assert e.value.changes == ["global:0x0357"] and restore_pending(tmp_path) and sent == ["first-open"]
    seen = first_open.seen_record(run.root.name)
    assert not seen.seen(["A"]) and ("a",) in seen.acting                    # its latest open look says "changed"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert fo.ended(True, SimpleNamespace(after=tmp_path / "x.DAT", changes=[]))      # the marker stays
    assert "upload_check.py start.DAT" in out.getvalue()


def test_a_lost_link_keeps_the_marker_and_says_the_row_acted(tmp_path):
    def fails(tag):
        raise LinkError("camera link exited")
    fo, _sent, run = first_opens(tmp_path, download=fails, gone="camlink has exited (status 3)")
    with pytest.raises(first_open.FirstOpenFailed):
        lap(tmp_path, fo)
    assert restore_pending(tmp_path)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        fo.lost("the link has gone")
    assert "never OK" in out.getvalue() and restore_pending(tmp_path)
    assert latest_open(run.root.name, ["A"])["result"] == "acted" and ("a",) in first_open.seen_record(
        run.root.name).acting


def test_a_lost_link_blames_only_the_row_open_when_it_went(tmp_path):
    fo, _sent, run = first_opens(tmp_path, per="page")
    for row in ("A", "B", "C"):
        fo.opening((row,))
    with contextlib.redirect_stdout(io.StringIO()):
        fo.lost("the link has gone")
    seen = first_open.seen_record(run.root.name)
    assert seen.acting == {("c",)} and seen.alone == {("a",), ("b",)}


def test_the_lap_stops_where_the_menu_is_not_back_on_its_row_after_the_check(tmp_path):
    fo, sent, _ = first_opens(tmp_path)
    cam, out = lap(tmp_path, fo, astray=True)
    assert "after a first open's check the menu is not back on its row" in out.stopped and sent == ["first-open"]


def test_a_greyed_row_greyed_again_is_no_first_open(tmp_path):
    fo, sent, _ = first_opens(tmp_path, first_open.Seen(greyed={("g",)}))
    fo.opening(("G",))
    assert restore_pending(tmp_path) and fo.takes(look(["G"], result="greyed"))
    pressed = []
    fo.settle(SimpleNamespace(press=pressed.append))
    assert sent == ["ping"] and pressed == [] and restore_pending(tmp_path)           # no download, the marker kept
    assert latest_open(tmp_path.name, ["G"])["result"] == "greyed" and not fo.seen.seen(["G"]) and fo.held == [("G",)]
    assert not fo.ended(True, SimpleNamespace(after=tmp_path / "e.DAT", changes=[])) and not restore_pending(tmp_path)
    # a record that differs at the end: each row held so is opened alone, with a download, next lap
    fo, sent, _ = first_opens(tmp_path, first_open.Seen(greyed={("g",)}))
    fo.opening(("G",))
    fo.takes(look(["G"], result="greyed"))
    fo.settle(SimpleNamespace(press=pressed.append))
    assert fo.ended(True, SimpleNamespace(after=tmp_path / "e.DAT", changes=[SimpleNamespace(key="global:0x0001")]))
    assert restore_pending(tmp_path) and ("g",) in first_open.seen_record(tmp_path.name).alone
    (tmp_path / RESTORE_BY_HAND).unlink()
    # a later row's check clears the held rows too: its download is theirs
    fo, sent, _ = first_opens(tmp_path, first_open.Seen(greyed={("g",)}))
    fo.opening(("G",))
    fo.takes(look(["G"], result="greyed"))
    fo.settle(SimpleNamespace(press=pressed.append))
    fo.opening(("K",))
    fo.settle(SimpleNamespace(press=pressed.append))
    assert sent == ["ping", "first-open"] and fo.held == [] and not restore_pending(tmp_path)
    fo, sent, _ = first_opens(tmp_path, first_open.Seen(greyed={("g",)}), ping=False)
    fo.opening(("G",))
    fo.takes(look(["G"], result="greyed"))
    fo.settle(SimpleNamespace(press=pressed.append))
    assert sent == ["ping", "first-open"]                   # the link did not answer: the whole check
    fo, sent, _ = first_opens(tmp_path)
    fo.opening(("H",))
    fo.takes(look(["H"], result="greyed"))                  # a notice, but the records never held the row greyed
    fo.settle(SimpleNamespace(press=pressed.append))
    assert sent == ["first-open"]


def test_a_stop_during_the_check_leaves_it_to_the_runs_end(tmp_path):
    fo, sent, _ = first_opens(tmp_path)
    fo.opening(("A",))

    def stopped(key):
        raise StopRequested("STOP")
    with pytest.raises(StopRequested):
        fo.settle(SimpleNamespace(press=stopped))
    assert fo.pending == [("A",)] and not fo.failure and restore_pending(tmp_path) and sent == []
    assert not fo.ended(True, SimpleNamespace(after=tmp_path / "a.DAT", changes=[])) and not restore_pending(tmp_path)


def test_pending_first_opens_at_the_end_go_only_with_a_clean_end(tmp_path):
    fo, _sent, _ = first_opens(tmp_path)
    fo.opening(("A",))
    assert restore_pending(tmp_path)
    assert fo.ended(True, SimpleNamespace(after=tmp_path / "a.DAT", changes=[SimpleNamespace(key="global:0x0001")]))
    fo, _sent, _ = first_opens(tmp_path)
    fo.opening(("A",))
    assert not fo.ended(True, SimpleNamespace(after=tmp_path / "a.DAT", changes=[])) and not restore_pending(tmp_path)


def test_per_page_one_check_and_a_difference_opens_the_page_alone_next(tmp_path, monkeypatch):
    fo, sent, run = first_opens(tmp_path, per="page")
    cam, out = lap(tmp_path, fo)
    assert out.stopped == "" and sent == ["first-open"] and all(m for _, m in cam.marks)   # one check for the page
    from camkit import session
    real = session.compared
    monkeypatch.setattr(session, "compared", lambda a, b, say=None: [SimpleNamespace(key="global:0x0357")])
    cam_dir = tmp_path / "again"
    cam_dir.mkdir()
    fo, sent, run = first_opens(cam_dir, per="page")
    with pytest.raises(first_open.FirstOpenFailed):
        lap(cam_dir, fo)
    seen = first_open.seen_record(cam_dir.name)
    assert {("a",), ("sub",), ("b",)} <= seen.alone and not seen.acting                # none can be blamed
    monkeypatch.setattr(session, "compared", real)
    fo, sent, _ = first_opens(cam_dir, seen=seen, per="page")
    (cam_dir / RESTORE_BY_HAND).unlink()
    cam, out = lap(cam_dir, fo)
    assert out.stopped == "" and sent == ["first-open"] * 3                         # each alone


def test_per_page_the_check_comes_as_the_lap_leaves_each_page(tmp_path):
    model = {"P1": MODEL["P"], "P2": MODEL["P"]}
    cycle = [{"page": pg, "row": i, "signature": f"top{i}", "kind": "menu"} for pg, i in (("P1", 0), ("P1", 1), ("P2", 2))]
    fo, sent, run = first_opens(tmp_path, per="page")
    from camkit.crawl import crawl
    checked = []
    real = fo.settle
    fo.settle = lambda cam: checked.append(list(fo.pending)) or real(cam)
    cam = Marked(tmp_path)
    out = crawl(cam, cycle, model, labels=cam.labels, first=fo)
    assert out.stopped == "" and sent == ["first-open"] * 2 and [len(c) for c in checked] == [5, 1]


def test_the_per_row_cost_over_the_link_is_three_commands(tmp_path, monkeypatch, capsys):
    """A first open's check over the stand-in camlink: MENU, a download, MENU, with LOCK_S waited between (0 here)."""
    log = tmp_path / "camlink.log"
    monkeypatch.setenv("FAKE_CAMLINK_LOG", str(log))
    run = Run("kit2_crawl", root=tmp_path)
    start = tmp_path / "start.DAT"
    shutil.copy(fake_camlink.SAMPLE, start)
    with Link(run, ip="192.0.2.10", binary=fake_camlink.COMMAND, catch_signals=False) as link:
        cam = SimpleNamespace(press=lambda k: link.press(k))
        fo = first_open.FirstOpens(link, None, run, start, first_open.Seen(), "", 0, wait=lambda *a, **k: None)
        times = []
        for i in range(5):
            fo.opening((f"Row {i}",))
            t = time.monotonic()
            fo.settle(cam)
            times.append(time.monotonic() - t)
    sent = [ast.literal_eval(x).decode().split()[1] for x in log.read_text(encoding="utf-8").splitlines()
            if x.startswith("b'@")]
    assert sent == ["press", "download", "press"] * 5 and not restore_pending(tmp_path)
    with capsys.disabled():
        print(f"\nfirst open, per row over the stand-in camlink: {len(sent) // 5} commands, "
              f"{1000 * sorted(times)[2]:.0f} ms median, besides the camera's own time and the menu's lock after the "
              "download (proving.base.LOCK_S)")


# ---------------------------------------------------------------------------------------------- crawl_run, pass 1

def crawl_main(tmp_path, monkeypatch, crawl=None, argv=(), restored=True, model_name=None, gone="", changes=(),
               root=None):
    """crawl_run.main() with its seams faked: `crawl(first)` runs as crawl_from_menu (returning True, or raising); the
    link names `model_name` and says `gone`; the end's download differs in `changes`. Returns (exit, console)."""
    import crawl_run as C
    run = Run("kit2_crawl", root=root or tmp_path)
    shutil.copy(fake_camlink.SAMPLE, tmp_path / "b.DAT")
    link = SimpleNamespace(download=lambda tag: tmp_path / "b.DAT", press=lambda *a, **k: None, gone=lambda: gone,
                           call=says(model_name).call)
    cycle = [{"page": "P", "row": 0, "signature": "top0", "kind": "menu"}]
    model = {"P": {"breadcrumb": "Shooting > Test", "page": "1/1", "rows": [{"label": "Drive Mode"}]}}
    for name, value in (("load_scan", lambda scan: (cycle, model)), ("Run", lambda name: run),
                        ("check_readers", lambda: None),
                        ("eyes_from_config", lambda r: SimpleNamespace(attach=lambda link: None, close=lambda: None,
                                                                       grab=lambda save=False: None)),
                        ("Link", lambda r, **k: contextlib.nullcontext(link)),
                        ("screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind="shooting"))),
                        ("wait_for", lambda *a, **k: None), ("time", SimpleNamespace(sleep=lambda s: None)),
                        ("LiveCamera", lambda *a, **k: SimpleNamespace()),
                        ("crawl_from_menu", lambda *a, first=None, **k: crawl(first) if crawl else True),
                        ("close_for_restore", lambda cam, link, start: None),
                        ("end_session", lambda *a, **k: SimpleNamespace(after=tmp_path / "e.DAT", uploaded=False,
                                                                        changes=[SimpleNamespace(key=x) for x in changes])),
                        ("restore_checked", lambda r, e, before, **kw: restored)):
        monkeypatch.setattr(C, name, value)
    monkeypatch.setattr(sys, "argv", ["crawl_run.py", *argv])
    out, code = io.StringIO(), 0
    with contextlib.redirect_stdout(out):
        try:
            C.main()
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


def test_crawl_run_goes_on_without_the_statement_and_says_how_many_it_skips(tmp_path, monkeypatch, scope):
    code, out = crawl_main(tmp_path, monkeypatch)
    assert code in (0, None) and "1 rows of this lap have not been seen opened" in out
    assert "each is skipped and recorded, since the camera's reviewed scope holds no blank-cards statement" in out
    scope(BLANK)
    code, out = crawl_main(tmp_path, monkeypatch, argv=["--panels"])
    assert code in (0, None) and "--panels commits options" in out
    code, out = crawl_main(tmp_path, monkeypatch, argv=["--first-open-check", "page"])
    assert "each opens under the link-loss procedure, checked once per page" in out and "the owner said on" in out
    scope.file.write_text("{", encoding="utf-8")                        # a scope that cannot be read: no first open
    code, out = crawl_main(tmp_path, monkeypatch)
    assert code in (0, None) and "each is skipped and recorded, since crawl_run.py: the reviewed scope" in out


def test_the_start_line_counts_the_rows_the_lap_reaches_or_says_the_whole_menu(tmp_path, monkeypatch, scope):
    """Before the link opens, the unseen rows of the lap --start-label and --limit make (a row a first open's rule skips
    counting toward no limit, a never-open row reached and counted for nothing), else the whole menu's, said so
    (2026-11-15, a camera session: '6 rows of this lap' on a three-row lap that held none)."""
    import crawl_run
    labels = ["A", "B", "Format", "C", "D", "E", "F"]          # B, D, E unseen; Format never opened
    cycle = [{"page": "P", "row": i, "signature": f"r{i}", "kind": "menu"} for i in range(len(labels))]
    cycle.append({"page": "Q", "row": 0, "signature": "q0", "kind": "menu"})     # Playback: off the lap's tabs
    model = {"P": {"breadcrumb": "Shooting > Test", "page": "1/1", "rows": [{"label": x} for x in labels]},
             "Q": {"breadcrumb": "Playback > Test", "page": "1/1", "rows": [{"label": "G"}]}}
    seen = first_open.Seen({("a",), ("c",), ("f",), ("g",)})

    def line(skip_why="no statement", seen=seen, **kw):
        a = SimpleNamespace(**{"tabs": None, "start_label": None, "limit": None, "skip_settled": False,
                               "first_open_check": "row", **kw})
        return crawl_run.unseen_line(cycle, model, seen, skip_why, a)
    assert line().startswith("3 rows of this lap have not been seen opened on this body: each is skipped")
    assert line(start_label="E").startswith("3 rows of this lap")                # the whole cycle from E round
    assert line(start_label="C", limit=1) == ""                                   # C alone: seen
    # without the statement D and E are skipped and count toward no limit: C, D, E, F; with it D opens: C, D
    assert line(start_label="C", limit=2).startswith("2 rows of this lap")
    assert line("", start_label="C", limit=2) == ("1 rows of this lap have not been seen opened on this body: each "
                                                  "opens under the link-loss procedure, checked once per row")
    # a row whose first open failed is skipped all the same: C, D, E
    acting = first_open.Seen(seen.opened, acting={("d",)})
    assert line("", acting, start_label="C", limit=2).startswith("2 rows of this lap")
    assert line(start_label="A", limit=1) == "" and line(start_label="B", limit=1).startswith("1 rows of this lap")
    for kw in ({"limit": 1}, {"start_label": "C", "limit": 1, "skip_settled": True},
               {"start_label": "Nowhere", "limit": 1}, {"start_label": "Nowhere"}):
        assert line(**kw) == ("3 rows of the whole menu (which of them this lap reaches is known only once the menu "
                              "opens) have not been seen opened on this body: each it reaches is skipped and recorded, "
                              "since no statement"), kw
    assert line(tabs="Playback") == "" and line(tabs="Shooting,Playback").startswith("3 rows")
    from camkit.crawl import lap_rows
    assert lap_rows(cycle, model, limit=1) is None and lap_rows(cycle, model, start=3, limit=1) == ["C"]
    # the start is go_to's: the real row before My Menu's copy of it (target_of)
    mine = [{"page": "M", "row": 0, "signature": "m0", "kind": "menu"}, *cycle]
    model["M"] = {"breadcrumb": "My Menu > Page 1", "page": "1/1", "rows": [{"label": "C"}]}
    assert crawl_run.target_of(mine, model, "C") == (4, False, "")
    assert crawl_run.target_of(mine, model, "Nowhere") == (None, True, "no row labelled 'Nowhere' in the page model")
    # crawl_run.main says it before anything connects
    code, out = crawl_main(tmp_path, monkeypatch, argv=["--limit", "1"])
    assert "1 rows of the whole menu" in out
    code, out = crawl_main(tmp_path, monkeypatch, argv=["--start-label", "Drive Mode", "--limit", "1"])
    assert "1 rows of this lap have not been seen opened" in out


def test_a_first_opens_skip_is_known_before_it_writes_anything(tmp_path):
    """FirstOpens.skips (camkit.crawl.left_unopened asks it before the coverage gate's line) says True exactly where
    opening() refuses with nothing written: an unseen row on a run that makes no first open, or one whose first open
    failed; a seen row, or an unseen one the run opens, is not skipped."""
    seen = first_open.Seen({("a",)}, acting={("b",)})
    fo, _sent, _run = first_opens(tmp_path, seen, skip_why="no statement")
    assert [fo.skips((x,)) for x in ("A", "B", "C")] == [False, True, True]
    assert all(fo.opening((x,)) for x in ("B", "C")) and not restore_pending(tmp_path)
    fo, _sent, _run = first_opens(tmp_path, seen)
    assert [fo.skips((x,)) for x in ("A", "B", "C")] == [False, True, False]
    assert fo.opening(("B",)) and fo.opening(("C",)) is None


def test_crawl_run_stops_on_another_body_before_anything_is_pressed(tmp_path, monkeypatch):
    code, out = crawl_main(tmp_path, monkeypatch, model_name="ILCE-7M4", crawl=lambda first: pytest.fail("crawled"),
                           root=tmp_path / TEST_CAMERA)
    assert "the camera connected is ILCE-7M4_fw4.00" in str(code) and "nothing was sent" in str(code)


def test_crawl_run_exits_5_on_a_gone_link_or_a_failed_check_with_the_marker(tmp_path, monkeypatch, scope):
    from exit_status import EXIT_RESTORE_BY_HAND
    scope(BLANK)

    def gone(first):
        first.opening(("Drive Mode",))
        raise LinkError("camera link exited")
    code, out = crawl_main(tmp_path, monkeypatch, crawl=gone, gone="camlink has exited")
    assert code == EXIT_RESTORE_BY_HAND and restore_pending(tmp_path) and "the link has gone" in out
    (tmp_path / RESTORE_BY_HAND).unlink()

    rows = iter(["Grid", "Zoom"])

    def pending(first):
        assert first.opening((next(rows),)) is None
        return True
    code, out = crawl_main(tmp_path, monkeypatch, crawl=pending, changes=["global:0x0357"])
    assert code == EXIT_RESTORE_BY_HAND and restore_pending(tmp_path) and "records differed" in out
    (tmp_path / RESTORE_BY_HAND).unlink()
    code, out = crawl_main(tmp_path, monkeypatch, crawl=pending)
    assert code in (0, None) and not restore_pending(tmp_path)


def test_crawl_from_menu_hands_the_coverage_gate_the_first_opens_hold_and_counts_the_skips(monkeypatch, capsys):
    import crawl_run
    from camkit.crawl import RowResult
    cam = SimpleNamespace(press=lambda key: None, read=lambda: SimpleNamespace(kind="menu", focus="rows"))
    monkeypatch.setattr(crawl_run, "same_position", lambda a, b: True)
    rows = [RowResult("p", 0, "A", "walked"), RowResult("p", 1, "B", f"{SKIPPED} (no statement)")]

    def fake(cam, cycle, model, on_row=None, **kw):
        for r in rows:
            on_row(r)
        return SimpleNamespace(stopped="", presses=0, rows=rows, recoveries=[])
    monkeypatch.setattr(crawl_run, "crawl", fake)
    given = []
    ledger = SimpleNamespace(after=lambda row, model, **kw: given.append(kw), skip=None)
    first = SimpleNamespace(takes=lambda lk: False, skip_why="no statement")
    crawl_run.crawl_from_menu(cam, SimpleNamespace(press=lambda *a, **k: None), [{"screen": None}], {}, None,
                              io.StringIO(), ledger=ledger, first=first)
    assert given == [{"hold": first.takes}] * 2
    assert "1 rows not seen opened on this body were skipped" in capsys.readouterr().out


def test_pass1_map_keeps_the_mapping_of_a_row_a_later_lap_only_skipped(own_runs, capsys):
    import pass1_map
    run = own_runs / TEST_CAMERA / "kit2_pass1"
    run.mkdir(parents=True)
    kept = {"path": ["Zoom"], "kind": "list", "options": [{"index": 0, "label": "On", "source": "ocr", "frame": "f"}]}
    (run / "map.json").write_text(json.dumps({"rows": [kept]}), encoding="utf-8")
    (run / "options.jsonl").write_text(json.dumps({"path": ["Grid"], "kind": "list", "index": 0, "frame": "g",
                                                   "ocr": "Off", "agreed": True}) + "\n", encoding="utf-8")
    (run / "rows.jsonl").write_text(json.dumps({"label": "Zoom", "outcome": f"{SKIPPED} (no statement)"}) + "\n",
                                    encoding="utf-8")
    got = pass1_map.main(["kit2_pass1", "--own"])
    assert [r["path"] for r in got["rows"]] == [["Grid"], ["Zoom"]] and "1 rows skipped as not seen" in capsys.readouterr().out


# ------------------------------------------------------------------------------------------------------ drive.py

def drive_run(tmp_path, monkeypatch, path=("Drive Mode",), presses=("right",), changes=(), fail=None, lit="Drive Mode",
              model_name=None, root=None, states=None, shown=(), values=None, live=None):
    """drive.py's main() with its seams faked: the lit row `lit` (or `states`, [(kind, lit)] after the opening MENU
    and after each press), the press raising `fail`, the end's download differing in `changes`, the link naming
    `model_name`. Returns (exit code, the presses with whether RESTORE_BY_HAND was there, the drive.jsonl line, the
    printed words)."""
    import drive
    run = Run("kit2_drive", root=root or tmp_path)
    pressed = []
    states = states or [("menu", lit)]

    def now():
        return states[min(max(len(pressed) - 1, 0), len(states) - 1)]

    class Cam:
        frame = SimpleNamespace(path=tmp_path / "00001_menu.png", image=None)

        def read(self):
            return SimpleNamespace(kind=now()[0])

        def press(self, key, **kw):
            pressed.append((key, (tmp_path / RESTORE_BY_HAND).exists()))
            if fail and key == "right":
                raise fail

        def refresh(self, tag):
            return self.read()

    ending = SimpleNamespace(after=tmp_path / "after.DAT", uploaded=bool(changes),
                             changes=[SimpleNamespace(key=k, before=0, after=1) for k in changes])
    link = SimpleNamespace(download=lambda tag: tmp_path / f"{tag}.DAT", press=lambda *a, **k: None,
                           call=says(model_name).call)
    for name, value in (("check_readers", lambda: None), ("load_scan", lambda scan: ([], {})), ("Run", lambda name: run),
                        ("eyes_from_config", lambda r: SimpleNamespace(attach=lambda link: None,
                                                                       grab=lambda save=False: None, close=lambda: None)),
                        ("screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind="shooting"))),
                        ("wait_for", lambda *a, **k: None), ("LiveCamera", lambda *a, **k: Cam()),
                        ("find_position", lambda cam, cycle, model: 0),
                        ("go_to", lambda *a, **k: True), ("enter_any", lambda cam, path, i: None),
                        ("screen_text", lambda cam, grip: "Drive Mode  Single Shooting"),
                        ("highlighted", lambda image, p: now()[1]), ("time", SimpleNamespace(sleep=lambda s: None)),
                        ("after_armed", lambda cam, grip: ("list", "Single Shooting", "")),
                        ("close_for_restore", lambda cam, link, start: None),
                        ("session", SimpleNamespace(ended=lambda link, before, **k: ending,
                                                    put_back=lambda link, e, before: e)),
                        ("restore_checked", lambda r, e, before, **k: True),
                        ("row_values", lambda model: values or {}),
                        ("Link", lambda r, **k: contextlib.nullcontext(link))):
        monkeypatch.setattr(drive, name, value)
    # the page's labels as drive.shown_labels reads them: a submenu page's live (`live`, else `shown`), a top-level
    # page's from the page model (`shown`)
    sub = list(live if live is not None else shown)
    monkeypatch.setattr(drive, "submenu_labels", lambda cam: ("page", [{"label": x, "readings": [x]} for x in sub]))
    monkeypatch.setattr(drive, "page_labels", lambda now, cycle, model: list(shown))
    monkeypatch.setattr(sys, "argv", ["drive.py", *[x for p in path for x in ("--path", p)],
                                      *[x for p in presses for x in ("--press", p)]])
    out, code = io.StringIO(), 0
    with contextlib.redirect_stdout(out):
        try:
            drive.main()
        except SystemExit as e:
            code = e.code
    lines = (run.dir / "drive.jsonl").read_text(encoding="utf-8").splitlines() if (run.dir / "drive.jsonl").exists() else []
    return code, pressed, (json.loads(lines[-1]) if lines else None), out.getvalue()


def test_drive_opens_an_unseen_row_only_with_the_statement_and_right_alone(tmp_path, monkeypatch, scope):
    import drive
    for path, presses, said in ((["Drive Mode"], ["right"], "owner_statement.py cards"),
                                (["Drive Mode"], ["right", "down"], "--press right alone"),
                                (["Drive Mode"], ["enter:Drive"], "--press right alone"),
                                (["Fn Menu", "Set"], ["down"], "open it first in a run of its own")):
        if said != "owner_statement.py cards":
            scope(BLANK)
        with pytest.raises(SystemExit) as e:
            drive.first_open_or_exit(SimpleNamespace(path=path, press=presses, owner=False))
        assert said in str(e.value), (path, presses)
    scope(BLANK)
    assert drive.first_open_or_exit(SimpleNamespace(path=["Drive Mode"], press=["right"], owner=False)) == "Drive Mode"
    # a run that opens no row (no Right or Enter), and an --owner run (its own route), make no first open
    assert drive.first_open_or_exit(SimpleNamespace(path=["Drive Mode"], press=["down", "left"], owner=False)) is None
    assert drive.first_open_or_exit(SimpleNamespace(path=["Format"], press=["right", "enter:x"], owner=True)) is None
    looks_of(TEST_CAMERA, look(["Drive Mode"], by="drive"))
    assert drive.first_open_or_exit(SimpleNamespace(path=["Drive Mode"], press=["right", "down", "enter:x"],
                                                    owner=False)) is None


def test_drive_marks_the_first_open_before_its_press_and_clears_it_after_a_clean_check(tmp_path, monkeypatch, scope):
    scope(BLANK)
    code, pressed, line, said = drive_run(tmp_path, monkeypatch)
    assert pressed == [("menu", False), ("right", True)] and code in (0, None)
    assert line["first_open"] is True and line["changes"] == [] and not restore_pending(tmp_path)
    assert "opens as any row from now on" in said and "the owner said on 2026-11-15" in said


def test_drive_keeps_the_marker_when_the_first_open_changed_a_record(tmp_path, monkeypatch, scope):
    from exit_status import EXIT_RESTORE_BY_HAND
    scope(BLANK)
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, changes=["global:0x0357"])
    assert code == EXIT_RESTORE_BY_HAND and restore_pending(tmp_path) and "global:0x0357" in said
    assert "upload_check.py before.DAT" in said


def test_drive_keeps_the_marker_when_the_link_goes_at_the_first_open(tmp_path, monkeypatch, scope):
    from exit_status import EXIT_RESTORE_BY_HAND
    scope(BLANK)
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, fail=LinkError("camera link exited"))
    assert code == EXIT_RESTORE_BY_HAND and restore_pending(tmp_path) and line["restore"] == "by hand"
    assert pressed[-1] == ("right", True)


def test_drive_refuses_the_first_open_on_another_lit_row(tmp_path, monkeypatch, scope):
    scope(BLANK)
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, lit="Shutter Type")      # a row never seen opened
    assert pressed == [("menu", False)] and "a row this camera has not been seen to open" in said
    looks_of(TEST_CAMERA, look(["Shutter Type"], by="drive"))                            # one seen opened
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, lit="Shutter Type")
    assert pressed == [("menu", False)] and "does not read 'Drive Mode'" in said and not restore_pending(tmp_path)


def test_drive_opens_no_unseen_row_the_presses_reach_and_walks_to_a_seen_one_plainly(tmp_path, monkeypatch, scope):
    looks_of(TEST_CAMERA, look(["Drive Mode"], by="drive"), look(["Parent"], by="drive"))
    # Down then Right on the --path's seen row's page: the row lit is another, never seen opened
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, presses=["down", "right"],
                                          states=[("menu", "Drive Mode  Single Shooting"),
                                                  ("menu", "Self-timer Type  10 sec")])
    assert [k for k, _ in pressed] == ["menu", "down"] and "'Self-timer Type  10 sec', a row this camera" in said
    assert "name it in --path" in said and not restore_pending(tmp_path)
    # into a seen submenu, then Down and Right on a row of it never seen opened
    walk = [("menu", "Parent"), ("submenu", "Child One  Off"), ("submenu", "Child Two  On")]
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, path=["Parent"], presses=["right", "down", "right"],
                                          states=walk)
    assert [k for k, _ in pressed] == ["menu", "right", "down"] and "'Child Two  On', a row this camera" in said
    # the same walk to a row seen opened is plain
    looks_of(TEST_CAMERA, look(["Parent", "Child Two"], by="drive"))
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, path=["Parent"], presses=["right", "down", "right"],
                                          states=walk, values={"child two": {"On"}})
    assert [k for k, _ in pressed] == ["menu", "right", "down", "right"] and not any(m for _, m in pressed)
    # after a MENU on a menu page the page cannot be placed: nothing more opens
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, path=["Parent"], presses=["menu", "right"],
                                          states=[("menu", "Parent"), ("menu", "Parent")])
    assert [k for k, _ in pressed] == ["menu", "menu"] and "is not one the run can place" in said


def test_drive_takes_no_longer_row_for_the_one_it_knows(tmp_path, monkeypatch, scope):
    looks_of(TEST_CAMERA, look(["Focus Area"], by="drive"), look(["Parent"], by="drive"),
             look(["Parent", "RAW Output"], by="drive"), look(["Parent", "Shutter Type"], by="drive"))
    # Focus Area Limit lit below the seen Focus Area (the --path's own row): known, or not, it is never Focus Area,
    # whose value Zone the kit knows
    for shown in (["Focus Area", "Focus Area Limit"], ()):
        code, pressed, line, said = drive_run(tmp_path, monkeypatch, path=["Focus Area"], presses=["down", "right"],
                                              states=[("menu", "Focus Area  Zone"), ("menu", "Focus Area Limit  On")],
                                              shown=shown, values={"focus area": {"Zone", "Wide"}})
        assert [k for k, _ in pressed] == ["menu", "down"] and "name it in --path" in said, shown
    # a body with no page model: RAW Output Setting, never seen, below a seen RAW Output in a seen submenu, whether
    # the page's labels read live hold it or not
    walk = [("menu", "Parent"), ("submenu", "RAW Output  On"), ("submenu", "RAW Output Setting  Off")]
    for kw in ({"live": ["RAW Output", "RAW Output Setting"]}, {"shown": ()}, {"live": ["RAW Output"]}):
        code, pressed, line, said = drive_run(tmp_path, monkeypatch, path=["Parent"], presses=["right", "down", "right"],
                                              states=walk, values={"raw output": {"On", "Off"}}, **kw)
        assert [k for k, _ in pressed] == ["menu", "right", "down"] and "name it in --path" in said, kw
    # where the words past the shorter label happen to be one of its values, the live labels alone tell the rows apart
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, path=["Parent"], presses=["right", "down", "right"],
                                          states=walk, values={"raw output": {"On", "Setting Off"}},
                                          live=["RAW Output", "RAW Output Setting"])
    assert [k for k, _ in pressed] == ["menu", "right", "down"] and "name it in --path" in said
    # a seen row with a value beside it the kit knows stays plain; one whose value it does not know is refused
    walk = [("menu", "Parent"), ("submenu", "RAW Output  On"), ("submenu", "Shutter Type  Auto")]
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, path=["Parent"], presses=["right", "down", "right"],
                                          states=walk, live=["RAW Output", "Shutter Type"],
                                          values={"shutter type": {"Auto", "Electronic Shutter"}})
    assert [k for k, _ in pressed] == ["menu", "right", "down", "right"]
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, path=["Parent"], presses=["right", "down", "right"],
                                          states=walk, live=["RAW Output", "Shutter Type"])
    assert [k for k, _ in pressed] == ["menu", "right", "down"] and "no value of it" in said
    # the --path's own row is taken only exactly: Grid Line Display lit and known, Grid named in --path and never seen
    # opened, is no first open of Grid
    scope(BLANK)
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, path=["Grid"], presses=["right"],
                                          states=[("menu", "Grid Line Display")], shown=["Grid Line Display"])
    assert [k for k, _ in pressed] == ["menu"] and not restore_pending(tmp_path)
    # a row known but never seen opened is refused; the --path's own label met deeper is no --path row
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, path=["Parent"], presses=["right", "down", "right"],
                                          states=[("menu", "Parent"), ("submenu", "Shutter Type"),
                                                  ("submenu", "Self-timer Type")], shown=["Self-timer Type"])
    assert [k for k, _ in pressed] == ["menu", "right", "down"] and "has not been seen to open" in said
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, path=["Parent"], presses=["right", "down", "right"],
                                          states=[("menu", "Parent"), ("submenu", "Shutter Type"),
                                                  ("submenu", "Parent")], shown=["Parent"])
    assert [k for k, _ in pressed] == ["menu", "right", "down"] and "has not been seen to open" in said


def test_lit_row_takes_the_longest_whole_label_it_knows():
    seen = first_open.Seen({("raw output",), ("focus area",)})
    assert seen.lit_row((), "RAW Outputs") is None                                  # no label inside a longer word
    assert seen.lit_row((), "RAW Output  On") == ("raw output",)
    assert seen.lit_row((), "Focus Area Limit On", {"Focus Area Limit"}) == ("focus area limit",)     # known, longest
    assert seen.lit_row((), "Focus Area Limit On", {"Focus Area", "Focus Area Limit"}) == ("focus area limit",)


def test_held_rows_are_kept_through_a_failed_check_and_a_lost_link(tmp_path):
    from camkit.link import LinkError

    def fails(tag):
        raise LinkError("camera link exited")
    fo, sent, run = first_opens(tmp_path, first_open.Seen(greyed={("g",)}), download=fails)
    fo.opening(("G",))
    fo.takes(look(["G"], result="greyed"))
    fo.settle(SimpleNamespace(press=lambda k: None))
    fo.opening(("K",))
    with pytest.raises(first_open.FirstOpenFailed):
        fo.settle(SimpleNamespace(press=lambda k: None))
    assert fo.failed == [("G",), ("K",)]
    other = tmp_path / "x"
    other.mkdir()
    fo, sent, run = first_opens(other,
                                first_open.Seen(greyed={("g",)}))
    fo.opening(("G",))
    fo.takes(look(["G"], result="greyed"))
    fo.settle(SimpleNamespace(press=lambda k: None))
    with contextlib.redirect_stdout(io.StringIO()):
        fo.lost("the link has gone")
    assert first_open.seen_record(run.root.name).alone == {("g",)}


def test_drive_stops_on_another_body_before_anything_is_pressed(tmp_path, monkeypatch, scope):
    scope(BLANK)
    code, pressed, line, said = drive_run(tmp_path, monkeypatch, model_name="ILCE-7M4", root=tmp_path / TEST_CAMERA)
    assert "the camera connected is ILCE-7M4_fw4.00" in str(code) and pressed == []


# ------------------------------------------------------------------------------------------------- the one picture

def fake_link(picture=False, run=None, tmp_path=None):
    return Link(run or Run("kit2_picture", root=tmp_path), ip="192.0.2.10", binary=fake_camlink.COMMAND,
                catch_signals=False, picture=picture)


def test_only_a_picture_link_releases_and_it_presses_nothing_but_menu(tmp_path):
    plain = fake_link(tmp_path=tmp_path)
    with pytest.raises(safety.Refused, match="only by kit/tools/take_picture.py"):
        plain.call("release", screen="shooting")
    with fake_link(picture=True, tmp_path=tmp_path) as link:
        for send in (lambda: link.press("down", screen="menu"), lambda: link.dial("front", 1, screen="menu"),
                     lambda: link.set("ShutterSpeed", 1), lambda: link.release(screen="menu")):
            with pytest.raises(safety.Refused):
                send()
        link.press("menu")
        assert link.release(screen="shooting")["ok"]
        with pytest.raises(safety.Refused, match="once"):
            link.release(screen="shooting")


def test_a_stop_refuses_the_release(tmp_path):
    with fake_link(picture=True, tmp_path=tmp_path) as link:
        (link.run.dir / "STOP").write_text("", encoding="utf-8")
        with pytest.raises(StopRequested):
            link.release(screen="shooting")


def test_camlink_without_picture_refuses_release_itself():
    lines = b"@1 release\n@2 press down 60\nquit\n"
    out = subprocess.run(fake_camlink.COMMAND, input=lines, capture_output=True, timeout=60).stdout.decode().splitlines()
    assert json.loads(out[1])["cause"] == "refused" and json.loads(out[2])["ok"]
    out = subprocess.run([*fake_camlink.COMMAND, "--picture"], input=b"@1 press down 60\n@2 release\n@3 release\nquit\n",
                         capture_output=True, timeout=60).stdout.decode().splitlines()
    assert [json.loads(x)["ok"] for x in out[1:]] == [False, True, False]


def test_nothing_but_take_picture_reaches_the_release():
    import drive
    assert drive.canonical_key("release") is None and drive.canonical_key("shutter") is None
    for name in ("release", "shutter", "s1", "s2"):
        with pytest.raises(safety.Refused):
            safety.check_input(name)
    hits = []
    for f in sorted((ROOT / "kit").rglob("*.py")):
        if "tests" in f.parts or f.name in ("take_picture.py", "link.py"):
            continue
        text = f.read_text(encoding="utf-8")
        if any(w in text for w in ("picture=True", ".release(screen", "PICTURE_ONLY", 'call("release', "'release'")):
            hits.append(f.relative_to(ROOT).as_posix())
    assert hits == []


def test_facts_read_the_definitions_live_settings_and_else_the_sdk():
    import take_picture as tp
    defn = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    sample = camset.read(fake_camlink.SAMPLE)
    asked = []
    link = SimpleNamespace(get=lambda name: asked.append(name) or {"current": 1})
    f = tp.facts(link, defn, sample)
    assert f["flash"] == "no: Flash Mode reads Autoflash" and "Autoflash" in tp.refused(f) and asked == ["DriveMode", "Interval_Rec_Mode", "FlashMode"]
    assert {w: f[w] for w in ("drive", "interval", "precapture")} == {"drive": "ok", "interval": "ok",
                                                                       "precapture": "ok"}
    assert f["silent"] is False
    # no definition: the SDK's properties, and what neither tells is unknown
    for values, want in (({"DriveMode": 1, "Interval_Rec_Mode": 1, "FlashMode": 2}, ("ok", "ok", "ok")),
                         ({"DriveMode": 65537, "Interval_Rec_Mode": 2, "FlashMode": 1}, ("no", "no", "no")),
                         ({}, ("unknown", "unknown", "unknown"))):
        def get(name, values=values):
            if name not in values:
                raise LinkError(f"unknown property {name}")
            return {"current": values[name]}
        f = tp.facts(SimpleNamespace(get=get), {}, sample)
        assert tuple(f[w][:7].split(":")[0] for w in ("drive", "interval", "flash")) == want, values
        assert f["precapture"] == "unknown"
    q = tp.question(TEST_CAMERA, "Stills", f)
    assert "answer only if Drive Mode is Single Shooting and interval shooting is off" in q
    assert "no flash is attached or it is off" in q and "A shutter sound will be heard" in q


def test_live_values_read_the_live_record_alone_never_a_copy_or_a_slot():
    import take_picture as tp
    defn = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    live = next(s for s in defn["settings"] if s["key"] == "global:0x02b5")
    flash = [[1, "Continuous Shooting"]]                 # the sample's Flash Mode record holds 1
    doc = {"settings": [live, {**live, "key": "global:0x0357", "values": flash, "copy_for": "Movie"},
                        {**live, "key": "global:0x0357", "values": flash, "copy_of": "global:0x02b5"},
                        {**live, "key": "global:0x0357[0]", "values": flash},
                        {**live, "key": "set:0x0357", "values": flash}]}
    assert tp.live_values(doc, camset.read(fake_camlink.SAMPLE), "Drive Mode") == ["Single Shooting"]


def test_what_the_sdk_alone_says_is_asked_of_the_owner_too_and_logged_beside_the_definition(tmp_path, monkeypatch):
    import take_picture as tp
    sample = camset.read(fake_camlink.SAMPLE)
    values = {"DriveMode": 1, "Interval_Rec_Mode": 1, "FlashMode": 2}
    link = SimpleNamespace(get=lambda name: {"current": values[name]})
    f = tp.facts(link, {}, sample)
    assert {w: f[w] for w in ("drive", "interval", "flash")} == {"drive": "ok", "interval": "ok", "flash": "ok"}
    assert f["stated"] == ["drive", "interval", "flash"] and not tp.refused(f)
    q = tp.question(TEST_CAMERA, "Stills", f)
    assert "answer only if Drive Mode is Single Shooting and interval shooting is off" in q
    defn = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    f = tp.facts(link, defn, sample)
    assert f["read"]["drive"] == {"definition": ["Single Shooting", "Single Shooting"], "sdk": 1}
    assert f["read"]["flash"] == {"definition": ["Autoflash"], "sdk": 2} and f["stated"] == []
    run = Run("kit2_picture", root=tmp_path)
    link = SimpleNamespace(get=link.get, run=run)
    monkeypatch.setattr(tp, "camset", SimpleNamespace(read=lambda p: sample))
    monkeypatch.setattr(tp, "mode_of", lambda live, dat: "Stills")
    assert "Autoflash" in tp.picture(link, None, TEST_CAMERA, {}, defn, {}, tmp_path / "s.json", tmp_path / "b.DAT")
    logged = [json.loads(x) for x in (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert logged[-1]["kind"] == "picture_facts" and logged[-1]["read"]["drive"]["sdk"] == 1


@pytest.fixture
def picture_seams(tmp_path, monkeypatch, scope):
    """take_picture's seams: a camera file naming live_mode, a person at a terminal, no link expected."""
    import take_picture
    cam_file = tmp_path / "camera.json"
    cam_file.write_text(json.dumps({"live_mode": {"key": "global:0x13bf", "modes": {"0": "Stills", "1": "Movie"}}}),
                        encoding="utf-8")
    monkeypatch.setattr(take_picture.definitions, "camera_file", lambda camera: cam_file)
    monkeypatch.setattr(take_picture.statements, "agent_shell", lambda env=None: "")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(take_picture, "Link", lambda *a, **k: pytest.fail("a link was opened"))
    return take_picture


def test_take_picture_stops_before_connecting_without_each_need(picture_seams, scope, monkeypatch, tmp_path):
    tp = picture_seams
    with pytest.raises(SystemExit, match="blank-cards statement"):
        tp.main([])
    scope(BLANK)
    monkeypatch.setattr(tp.statements, "agent_shell", lambda env=None: "CLAUDECODE")
    with pytest.raises(SystemExit, match="only the camera's owner"):
        tp.main([])
    monkeypatch.setattr(tp.statements, "agent_shell", lambda env=None: "")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)
    with pytest.raises(SystemExit, match="no terminal"):
        tp.main([])
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    (tmp_path / "camera.json").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="no live_mode"):
        tp.main([])


OK = {"drive": "ok", "interval": "ok", "precapture": "ok", "flash": "ok", "silent": False}


def test_take_picture_releases_once_only_when_one_press_takes_one_picture_on_the_owners_word(picture_seams, scope,
                                                                                            monkeypatch, tmp_path):
    tp = picture_seams
    f = scope(BLANK)
    sent = []
    link = SimpleNamespace(release=lambda screen: sent.append(("release", screen)),
                           download=lambda tag: sent.append(("download", tag)) or tmp_path / "x.DAT")
    state = {}
    monkeypatch.setattr(tp, "mode_of", lambda live, dat: state["mode"].pop(0))
    monkeypatch.setattr(tp, "facts", lambda link, defn, cs: state["facts"].pop(0))
    monkeypatch.setattr(tp.camset, "read", lambda p: None)
    monkeypatch.setattr(tp, "shooting_now", lambda link, eyes: state["shooting"].pop(0))
    monkeypatch.setattr(tp.time, "sleep", lambda s: None)
    monkeypatch.setattr(tp.statements, "ask", lambda q, word: "" if state["answer"] == word else "not the word")
    scope_now = json.loads(f.read_text(encoding="utf-8"))

    def go(**kw):
        state.update({"mode": ["Stills", "Stills"], "facts": [dict(OK), dict(OK)], "shooting": [True, True],
                      "answer": "picture", **kw})
        sent.clear()
        return tp.picture(link, None, TEST_CAMERA, {}, {}, scope_now, f, tmp_path / "before.DAT")
    assert "not Stills" in go(mode=["Movie"]) and sent == []
    assert "S&Q" in go(mode=["S&Q"]) and sent == []
    for what in ("drive", "interval", "precapture", "flash"):
        assert "set them by hand first" in go(facts=[{**OK, what: f"no: {what} reads on"}]) and sent == [], what
    assert go(answer="no") == "not the word" and sent == []
    assert "picture" not in json.dumps(json.loads(f.read_text(encoding="utf-8"))["decisions"])  # nothing written
    assert "no longer reads as the shooting screen" in go(shooting=[False]) and ("release", "shooting") not in sent
    assert "no longer reads as the shooting screen" in go(shooting=[True, False]) and ("release", "shooting") not in sent
    assert "left Stills" in go(mode=["Stills", "Movie"]) and ("release", "shooting") not in sent
    for later in ({**OK, "flash": "no: Flash Mode reads Fill-flash"}, {**OK, "drive": "unknown"}):
        assert "has changed since the question" in go(facts=[dict(OK), later]) and ("release", "shooting") not in sent
    assert go() == "" and sent.count(("release", "shooting")) == 1
    assert json.loads(f.read_text(encoding="utf-8"))["decisions"][-1]["picture"] == "once"

    def held(screen):
        raise LinkError("release: release not accepted: its up was refused for 2 s")
    link.release = held
    with pytest.raises(tp.ShutterHeld):
        go()


def test_take_picture_stops_on_another_body_before_anything_is_pressed(picture_seams, scope, monkeypatch, tmp_path):
    tp = picture_seams
    scope(BLANK)
    link = SimpleNamespace(call=says("ILCE-7M4").call, press=lambda *a, **k: pytest.fail("pressed"),
                           download=lambda tag: pytest.fail("downloaded"))
    monkeypatch.setattr(tp, "Run", lambda name: Run("kit2_picture", root=tmp_path / TEST_CAMERA))
    monkeypatch.setattr(tp, "Link", lambda r, **k: contextlib.nullcontext(link))
    monkeypatch.setattr(tp, "eyes_from_config", lambda r: SimpleNamespace(close=lambda: None))
    with pytest.raises(SystemExit, match="the camera connected is ILCE-7M4_fw4.00"):
        tp.main([])


def test_a_release_not_answered_cleanly_sends_nothing_more_and_asks_for_the_camera_off(picture_seams, scope,
                                                                                         monkeypatch, tmp_path):
    from exit_status import EXIT_RESTORE_BY_HAND
    tp = picture_seams
    scope(BLANK)
    run = Run("kit2_picture", root=tmp_path)
    shutil.copy(fake_camlink.SAMPLE, tmp_path / "before.DAT")
    after = []
    link = SimpleNamespace(model=None, download=lambda tag: tmp_path / "before.DAT", press=lambda *a, **k: None)
    for name, value in (("Run", lambda name: run), ("Link", lambda r, **k: contextlib.nullcontext(link)),
                        ("eyes_from_config", lambda r: SimpleNamespace(attach=lambda l: None, close=lambda: None,
                                                                       grab=lambda save=False: None)),
                        ("screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind="shooting"))),
                        ("picture", lambda *a: (_ for _ in ()).throw(tp.ShutterHeld("no answer"))),
                        ("session", SimpleNamespace(wait_for=lambda *a, **k: after.append("wait"),
                                                    finish=lambda *a, **k: after.append("finish")))):
        monkeypatch.setattr(tp, name, value)
    out = io.StringIO()
    with contextlib.redirect_stdout(out), pytest.raises(SystemExit) as e:
        tp.main([])
    assert e.value.code == EXIT_RESTORE_BY_HAND and restore_pending(tmp_path) and after == ["wait"]
    assert "Switch the camera off now" in out.getvalue() and "no picture" not in out.getvalue()
