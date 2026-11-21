"""The readings no real grey entry has calibrated (the reviewer of grey-before-enter, 2026-11-20): a carousel's lit
column icon, which the camera draws with the axis value, and a checklist item's band, read by the lists' threshold.
A proof line chosen on either says how it was judged and that a greyed entry of that kind has not been measured; the
first camera refusal after an Enter on an entry either read white marks that row "misjudged" in the camera's memory
(runs/<model>_fw<fw>/grey_misjudged.jsonl), and from then on, in that run and every later one, its entries are not
entered on that reading alone, until a "measured" line says otherwise. Nothing talks to a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT))
from camkit import screen  # noqa: E402
from proving import greyed  # noqa: E402

CAMERA = "TEST-CAM_fw9.99"


@pytest.fixture
def memory(tmp_path, monkeypatch):
    """The camera's memory in a run root of the test's own."""
    from camkit import paths
    monkeypatch.setattr(paths, "runs_top", lambda: tmp_path)
    monkeypatch.setattr(paths, "camera", lambda cfg=None: (CAMERA, "the test"))
    (tmp_path / CAMERA).mkdir()
    return tmp_path / CAMERA / greyed.MISJUDGED


def dialog_cam(name="00007_down.png", kind="dialog", picture=True):
    frame = SimpleNamespace(path=Path(name), image=np.zeros((480, 640, 3), np.uint8) if picture else None)
    return SimpleNamespace(frame=frame, read=lambda: screen.Screen(kind=kind))


def test_a_row_marked_misjudged_stays_so_until_a_measurement_says_otherwise(memory):
    assert greyed.misjudged("Drive Mode / Cont. Shooting", "icon") is None
    greyed.mark_misjudged("Drive Mode / Cont. Shooting", "icon", "kit2_x", "00012_enter.png",
                          {"text": "Invalid with this setting", "frame": "00013_enter.png"})
    got = greyed.misjudged("Drive Mode / Cont. Shooting", "icon")
    assert got and got["run"] == "kit2_x" and got["frame"] == "00012_enter.png"
    assert greyed.misjudged("Drive Mode / Cont. Shooting", "checklist") is None, "one reading at a time"
    assert greyed.misjudged("Metering Mode / Spot", "icon") is None
    greyed.mark_measured("Drive Mode / Cont. Shooting", "icon", "calib_grey_looks: a greyed axis value measured")
    assert greyed.misjudged("Drive Mode / Cont. Shooting", "icon") is None
    lines = memory.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2, "nothing is ever taken out: the latest line counts"


def test_a_misjudged_rows_entry_read_white_is_refused_before_its_enter(memory, monkeypatch):
    monkeypatch.setattr(greyed, "choice_drawing", lambda cam: (False, 214.0, "its lit icon"))
    cam = dialog_cam()
    assert greyed.choice_refused(cam, "Drive Mode / Cont. Shooting", "Hi+") == ""
    greyed.mark_misjudged("Drive Mode / Cont. Shooting", "icon", "kit2_x", "00012_enter.png", None)
    why = greyed.choice_refused(cam, "Drive Mode / Cont. Shooting", "Hi+")
    assert "misjudged" in why and "kit2_x" in why and "nothing was pressed" in why
    # a list's band is no reading the memory holds: a list on the same row's name is judged as before
    assert greyed.choice_refused(dialog_cam(kind="list"), "Drive Mode / Cont. Shooting", "Hi+") == ""


def test_the_readings_a_proof_line_names():
    assert greyed.reading_of(dialog_cam()) == "icon"
    assert greyed.reading_of(dialog_cam(kind="checklist")) == "checklist"
    assert greyed.reading_of(dialog_cam(kind="list")) is None
    assert "lit column icon" in greyed.UNMEASURED["icon"] and "not been measured" in greyed.UNMEASURED["icon"]
    assert "threshold" in greyed.UNMEASURED["checklist"] and "not been measured" in greyed.UNMEASURED["checklist"]


# ------------------------------------------------------------------ an axis value prove_run judged, then the camera refused

class Refuses:
    """test_axis_after_ok's Framing Stabilizer, but OK on On: Manual brings a refusal notice ("Invalid ..."), which MENU
    leaves for the row, nothing committed."""

    def __init__(self):
        import test_axis_after_ok as T
        self.T = T

        class Cam(T.FramingStabilizer):
            def press(cam, key, **kw):
                if cam.where == "dialog" and key == "enter" and cam.opt == "On" and cam.value == 1:
                    cam.keys.append(key)
                    cam.where = "refusal"
                    cam._show(key)
                    cam.texts[cam.frame.path] = ["Invalid with this setting.", "OK"]
                    return
                if cam.where == "refusal":
                    cam.keys.append(key)
                    cam.where = "menu"
                    cam._show(key)
                    return
                super().press(key, **kw)

            def read(cam):
                return screen.Screen(kind="notice") if cam.where == "refusal" else super().read()
        self.Cam = Cam


@pytest.mark.real_grey
def test_a_refusal_after_an_axis_value_read_white_marks_the_row_and_a_later_run_refuses_it(memory, monkeypatch):
    R = Refuses()
    T = R.T
    monkeypatch.setattr(greyed, "choice_drawing", lambda cam: (False, 214.0, "its lit icon"))
    monkeypatch.setattr(greyed, "NEVER_ENTER", True)
    cam = R.Cam()
    P, link, downloads = T.proof_seams(monkeypatch, cam)
    out = T.Lines()
    P.prove_axis_row(cam, link, None, T.axis_job(), T.Dat("00001_start.DAT", cam.records()), out)
    manual = next(r for r in out if r["label"] == "On: Manual")
    assert manual["applied"] is False and manual["grey_judged"] == greyed.UNMEASURED["icon"]
    assert all("grey_judged" not in r for r in out if r["final"]), "the put-back is no choice judged"
    assert greyed.misjudged(T.JOB_KEY, "icon")
    # a later run: the value is not entered on the icon alone
    again = R.Cam()
    P, link, downloads = T.proof_seams(monkeypatch, again)
    with pytest.raises(P.Failed, match="misjudged"):
        P.prove_axis_row(again, link, None, T.axis_job(), T.Dat("00001_start.DAT", again.records()), T.Lines())
    assert again.keys.count("enter") == 0, "nothing was pressed on it"


def test_an_axis_value_taken_after_a_white_reading_marks_nothing(memory, monkeypatch):
    import test_axis_after_ok as T
    monkeypatch.setattr(greyed, "choice_drawing", lambda cam: (False, 214.0, "its lit icon"))
    monkeypatch.setattr(greyed, "NEVER_ENTER", True)
    cam = T.FramingStabilizer()
    P, link, downloads = T.proof_seams(monkeypatch, cam)
    out = T.Lines()
    P.prove_axis_row(cam, link, None, T.axis_job(), T.Dat("00001_start.DAT", cam.records()), out)
    assert out[0]["applied"] and out[0]["grey_judged"] == greyed.UNMEASURED["icon"]
    assert not memory.exists() or greyed.misjudged(T.JOB_KEY, "icon") is None


# ------------------------------------------------------------------ a checklist box ticked on, then the OK refused

class Checklist:
    """A made-up checklist of two boxes, none ticked: Right opens it on the first row, Down moves down the rows and from
    the last onto the OK button, Enter on a row flips its box, Enter on OK applies, except with the first box ticked
    on, which the camera refuses with a notice ("Invalid ..."); MENU on the notice goes back to the row."""

    def __init__(self):
        self.where, self.focus, self.row, self.ticks, self.keys, self.n = "menu", "rows", 0, [False, False], [], 0
        self.frame = None
        self._show("start")

    def _show(self, tag):
        self.n += 1
        self.frame = SimpleNamespace(path=Path(f"{self.n:05d}_{tag}.png"), image=np.zeros((480, 640, 3), np.uint8))

    def press(self, key, **kw):
        self.keys.append(key)
        if self.where == "menu" and key == "right":
            self.where, self.focus, self.row = "checklist", "rows", 0
        elif self.where == "checklist" and key == "down":
            if self.focus == "rows" and self.row < 1:
                self.row += 1
            else:
                self.focus = "button"
        elif self.where == "checklist" and key == "enter":
            if self.focus == "rows":
                self.ticks[self.row] = not self.ticks[self.row]
            elif self.ticks[0]:
                self.where = "notice"
            else:
                self.where = "menu"
        elif key == "menu":
            self.where = "menu"
        self._show(key)

    def read(self):
        return screen.Screen(kind=self.where, focus=self.focus if self.where == "checklist" else None)

    def cancel_to_menu(self):
        self.where = "menu"


def checklist_seams(monkeypatch, cam):
    from proving import checklists as C
    import test_axis_after_ok as T
    downloads = []

    def download(name):
        dat = T.Dat(f"{len(downloads) + 2:05d}_{name}.DAT", {"global:0x0100": int(cam.ticks[0]),
                                                              "global:0x0101": int(cam.ticks[1])})
        downloads.append(dat)
        return dat

    def diff(a, b):
        return [SimpleNamespace(key=k, before=a[k], after=b[k]) for k in a if a[k] != b[k]]
    monkeypatch.setattr(C, "read_boxes", lambda cam, name, labels: (set(), set()))
    monkeypatch.setattr(C, "on_box", lambda cam, labels, box: cam.row == box)
    monkeypatch.setattr(C, "check_state", lambda cam: cam.ticks[cam.row] if cam.focus == "rows" else None)
    monkeypatch.setattr(C, "focused_button", lambda cam: "OK")
    monkeypatch.setattr(C, "place", lambda cam: "the row")
    monkeypatch.setattr(C, "same_place", lambda a, b, tol=2: True)
    monkeypatch.setattr(C, "to_row", lambda cam, path, top, row_place: setattr(cam, "where", "menu"))
    monkeypatch.setattr(C, "later", lambda fn, cam: None)
    monkeypatch.setattr(C, "settled", lambda seen: None)
    monkeypatch.setattr(C, "after_download", lambda cam, done: None)
    monkeypatch.setattr(C, "camset", SimpleNamespace(read=lambda d: d.values, diff=diff))
    monkeypatch.setattr(C, "ocr", SimpleNamespace(read=lambda frames, eng=None: {f: [] for f in frames},
                                                  text_in=lambda lines, box: "Invalid with this setting."))
    link = SimpleNamespace(download=download)
    run = SimpleNamespace(dir=Path("kit2_checklist_test"))
    return C, link, run, T.Dat("00001_start.DAT", {"global:0x0100": 0, "global:0x0101": 0})


@pytest.mark.real_grey
def test_a_box_ticked_on_by_a_white_band_and_the_ok_refused_marks_the_row(memory, monkeypatch):
    monkeypatch.setattr(greyed, "choice_drawing", lambda cam: (False, 210.0, "its label's text on the row's band"))
    monkeypatch.setattr(greyed, "NEVER_ENTER", True)
    cam = Checklist()
    C, link, run, start = checklist_seams(monkeypatch, cam)
    out = []
    sink = SimpleNamespace(write=lambda line: out.append(__import__("json").loads(line)), flush=lambda: None)
    with pytest.raises(C.Failed, match="misjudged"):
        C._prove_check_row(cam, link, run, {"path": ["Playback Filter"], "labels": ["Date", "Rating"]}, start, sink)
    assert out[0]["applied"] is False and out[0]["grey_judged"] == greyed.UNMEASURED["checklist"]
    marked = greyed.misjudged("Playback Filter", "checklist")
    assert marked and marked["run"] == "kit2_checklist_test"


def test_the_other_checklist_tickers_mark_only_a_refusal_notice_after_a_tick_on():
    """customshoot_run and filter_run's grid tick mark the row as prove_run's checklists do, right after their
    judgement's Enter, and only where the camera answered a tick put on with a refusal notice (commit.REFUSED_WORDS: an
    unrelated notice, or a tick that did not flip with no notice, which could be a misread tick, marks nothing);
    customshoot_run keys its mark by hold and item, so one refusal never blocks every item of every hold."""
    for rel in ("provers/customshoot_run.py", "provers/filter_run.py"):
        src = (KIT / rel).read_text(encoding="utf-8")
        at = src.index("greyed.mark_misjudged(")
        before = src[max(0, at - 700):at]
        assert "greyed.reading_of(cam)" in src[:at] and "REFUSED_WORDS.search(" in before, rel
        assert '"notice"' in before, rel
    cs = (KIT / "provers" / "customshoot_run.py").read_text(encoding="utf-8")
    assert 'f"Recall Custom hold {h} / {ITEMS[k]}"' in cs and 'choice_refused(cam, "Recall Custom hold",' not in cs


@pytest.mark.real_grey
def test_a_notice_that_is_no_refusal_marks_no_checklist_row(memory, monkeypatch):
    monkeypatch.setattr(greyed, "choice_drawing", lambda cam: (False, 210.0, "its label's text on the row's band"))
    monkeypatch.setattr(greyed, "NEVER_ENTER", True)
    cam = Checklist()
    C, link, run, start = checklist_seams(monkeypatch, cam)
    monkeypatch.setattr(C, "ocr", SimpleNamespace(read=lambda frames, eng=None: {f: [] for f in frames},
                                                  text_in=lambda lines, box: "Recording to the card."))
    out = []
    sink = SimpleNamespace(write=lambda line: out.append(__import__("json").loads(line)), flush=lambda: None)
    with __import__("contextlib").suppress(C.Failed):
        C._prove_check_row(cam, link, run, {"path": ["Playback Filter"], "labels": ["Date", "Rating"]}, start, sink)
    assert greyed.misjudged("Playback Filter", "checklist") is None


# ------------------------------------------------------------------ the memory's tool, and every run saying the marks

def test_the_tool_lists_the_marks_and_lifts_one_only_with_a_why(memory, capsys):
    sys.path.insert(0, str(KIT / "tools"))
    import grey_memory as M
    assert M.main(["--list"]) == 0 and "no row is marked" in capsys.readouterr().out
    greyed.mark_misjudged("Drive Mode / Cont. Shooting", "icon", "kit2_x", "00012_enter.png", None)
    capsys.readouterr()
    M.main(["--list"])
    said = capsys.readouterr().out
    assert "1 row(s) marked misjudged" in said and "'Drive Mode / Cont. Shooting' (icon): run kit2_x" in said
    with pytest.raises(SystemExit, match="needs --why"):
        M.main(["--measured", "Drive Mode / Cont. Shooting", "icon"])
    with pytest.raises(SystemExit, match="one of"):
        M.main(["--measured", "Drive Mode / Cont. Shooting", "band", "--why", "x"])
    with pytest.raises(SystemExit, match="holds no icon mark"):
        M.main(["--measured", "Metering Mode / Spot", "icon", "--why", "x"])
    assert M.main(["--measured", "Drive Mode / Cont. Shooting", "icon", "--why", "a grey Hi+ measured"]) == 0
    assert greyed.misjudged("Drive Mode / Cont. Shooting", "icon") is None
    capsys.readouterr()
    M.main(["--list"])
    assert "no row is marked" in capsys.readouterr().out


def test_the_refusal_names_the_tool(memory, monkeypatch):
    monkeypatch.setattr(greyed, "choice_drawing", lambda cam: (False, 214.0, "its lit icon"))
    greyed.mark_misjudged("Drive Mode / Cont. Shooting", "icon", "kit2_x", "00012_enter.png", None)
    why = greyed.choice_refused(dialog_cam(), "Drive Mode / Cont. Shooting", "Hi+")
    assert "kit/tools/grey_memory.py --measured" in why and "--list" in why


def test_every_run_says_the_marks_it_will_apply(memory, capsys):
    greyed.say_marks()
    assert capsys.readouterr().out == "", "no mark: nothing said"
    greyed.mark_misjudged("Drive Mode / Cont. Shooting", "icon", "kit2_x", "00012_enter.png", None)
    capsys.readouterr()
    greyed.say_marks()
    said = capsys.readouterr().out
    assert "'Drive Mode / Cont. Shooting' (icon)" in said and "grey_memory.py" in said
    # said at the start of every run that judges an entry: the provers' session, prove_run, filter_run, mode_switch
    for rel, before in (("runner.py", "with Link(run) as link:"), ("prove_run.py", None),
                        ("provers/filter_run.py", None), ("provers/mode_switch.py", None)):
        src = (KIT / rel).read_text(encoding="utf-8")
        if rel == "runner.py":
            src = src.split("def prover_session", 1)[1]
        assert "greyed.say_marks()" in src, rel
        if before:
            assert src.index("greyed.say_marks()") < src.index(before), rel


# ------------------------------------------------------------------ the conftest fixture's opt-out is a marker

def test_without_the_marker_a_made_up_frame_reads_white():
    assert greyed.choice_drawing(dialog_cam(picture=False))[0] is False, "conftest's made_up_entries_white"


@pytest.mark.real_grey
def test_with_the_marker_the_reading_is_the_kits_own():
    """The same frame with no picture, the marker on: the kit's own reading, which cannot tell it."""
    assert greyed.choice_drawing(dialog_cam(picture=False))[0] is None
