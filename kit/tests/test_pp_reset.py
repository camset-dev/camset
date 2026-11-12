"""Offline tests of kit/provers/pp_reset_run.py (a Picture Profile's own Reset, a download after each profile) and of
kit/tools/make_sample.py --take/--from (the reset records taken into the sample), with made-up screens, sessions and
files. Nothing talks to a camera. The files are the public sample with made-up changes (a record's first byte moved by
one), never a camera's own values."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
for sub in ("provers", "tools"):
    if str(ROOT / "kit" / sub) not in sys.path:
        sys.path.insert(1, str(ROOT / "kit" / sub))
import make_sample as MS  # noqa: E402
import pp_reset_run as M  # noqa: E402
from camkit import camset, provenance, safety, session  # noqa: E402

SAMPLE = ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"
QUESTION = "Reset PP1 to the default setting? OK Cancel"
COMPLETE = "Complete. OK"              # the a1 II's notice after OK (kit2_pp_reset_trial 00043_enter.png, as OCR read it)
OTHER_NOTICE = "Picture Profile was reset. OK"


# ---------------------------------------------------------------- the plan, from a scan (no camera)

def made_scan(tmp_path) -> Path:
    scan = tmp_path / "kit2_page_scan"
    scan.mkdir()
    (scan / "model.json").write_text(json.dumps([
        {"page": "22/63", "rows": [{"slot": 0, "label": "Creative Look"}]},
        {"page": "23/63", "rows": [{"slot": 1, "label": "Shutter AWB Lock"}, {"slot": 2, "label": "Picture Profile"}]}]),
        encoding="utf-8")
    return scan


def made_tree(tmp_path) -> Path:
    tree = {"tabs": [{"pages": [{"rows": [{"label": "Picture Profile", "kind": "dialog",
                                           "options": ["Off", "PP1", "PP2", "PP4", "PP4", "PP10", "PP3"]}]}]}],
            "modes": [{"mode": "Movie", "tabs": [{"pages": [{"rows": [{"label": "Picture Profile", "options": [
                "Off", "PP1", "PP2", "User1: (No Import)"]}]}]}]}]}
    f = tmp_path / "menu_tree.json"
    f.write_text(json.dumps(tree), encoding="utf-8")
    return f


def test_the_plan_comes_from_the_scan_and_the_recorded_walk(tmp_path):
    scan, tree = made_scan(tmp_path), json.loads(made_tree(tmp_path).read_text(encoding="utf-8"))
    assert M.scan_row(scan) == {"page": "23/63", "slot": 2}
    assert M.scan_row(tmp_path) is None
    assert M.profiles_of(M.menu_tree_options(tree, "Stills")) == ["PP1", "PP2", "PP3", "PP4", "PP10"]
    assert M.profiles_of(M.menu_tree_options(tree, "Movie")) == ["PP1", "PP2"], "a LUT profile is never one to reset"
    assert M.menu_tree_options(tree, "S&Q") is None
    lines = M.plan_lines("TEST-CAM_fw9.99", "Stills", scan, M.scan_row(scan), ["PP1", "PP2"], "the tree", ["PP2", "PP7"],
                         tmp_path / "kit2_pp_reset_stills", False)
    text = "\n".join(lines)
    assert "page 23/63, row 3" in text and "PP1, PP2 (the tree)" in text and "PP2, PP7 only (PP7 not in" in text
    assert "kit2_pp_reset_stills/STOP" in text and "pp_reset.json" in text
    with pytest.raises(SystemExit, match="not a Picture Profile's name"):
        M.asked_profiles(["PP1,Gamma"])
    assert M.asked_profiles(["PP1, pp10", "PP1"]) == ["PP1", "PP10"]


def test_a_dry_run_prints_the_plan_and_opens_no_link(tmp_path, monkeypatch, capsys):
    import camkit.link
    import runner
    scan, tree = made_scan(tmp_path), made_tree(tmp_path)
    root = tmp_path / "TEST-CAM_fw9.99"

    def no_link(*a, **k):
        raise AssertionError("a dry run opened a link")
    monkeypatch.setattr(camkit.link, "Link", no_link)
    monkeypatch.setattr(runner, "Link", no_link)
    monkeypatch.setattr(M, "run_session", no_link)
    monkeypatch.setattr(M.paths, "run_root", lambda *a, **k: root)
    monkeypatch.setattr(M, "scan_dir", lambda scan_arg, mode=None: scan)
    monkeypatch.setattr(M.definitions, "menu_tree_file", lambda camera: tree)
    assert M.main(["--dry-run", "--allow", "Picture Profile Reset"]) == 0
    out = capsys.readouterr().out
    assert "PP1, PP2, PP3, PP4, PP10" in out and "nothing was sent to the camera" in out
    assert not (root / "kit2_pp_reset_stills").exists(), "a dry run makes no run folder"
    with pytest.raises(SystemExit, match="Stills or Movie"):
        M.main(["--dry-run", "--allow", "Picture Profile Reset", "--in", "S&Q"])


# ---------------------------------------------------------------- the owner's word, for this row only

@pytest.mark.parametrize("allow,said", [([], "owner's word"), (["Reset"], "owner's word"),
                                        (["Setting Reset"], "owner's word"),
                                        (["Picture Profile Reset", "Setting Reset"], "opens no never-open row but"),
                                        (["Picture Profile Reset", "Camera Settings Reset"], "opens no never-open row"),
                                        (["Picture Profile Reset", "Initialize"], "opens no never-open row but")])
def test_a_run_needs_the_owners_word_for_this_row_and_no_other(allow, said, monkeypatch):
    monkeypatch.setattr(M, "scan_dir", lambda *a, **k: (_ for _ in ()).throw(AssertionError("past the allowance")))
    argv = ["--dry-run"] + [x for a in allow for x in ("--allow", a)]
    with pytest.raises(SystemExit, match=said):
        M.main(argv)


@pytest.mark.parametrize("lit,title", [("Setting Reset", "PP1"), ("Camera Settings Reset", "PP1"),
                                       ("Reset Network Set.", "PP1"), ("Initialize", "PP1"), ("Copy", "PP1"),
                                       ("Reset", "PP10"), ("Reset", "Picture Profile"), ("Reset", ""), ("", "PP1"),
                                       ("Forced File Number Reset", "PP1"), ("Reset All", "PP1")])
def test_the_allowance_opens_no_other_reset_row(lit, title):
    """profile_reset_row lets only Reset alone under the profile's own title through; the allowance's words lift no row
    in a LiveCamera or drive.py, whose guards still refuse every reset (a bare Reset among them)."""
    import drive
    from camkit.live import open_refused
    assert safety.profile_reset_row(lit, title, "PP1") != ""
    assert safety.profile_reset_row("Reset", "PP1", "PP1") == "" and safety.profile_reset_row("Reset.", "PP 1", "PP1") == ""
    for row in ("Reset", "Setting Reset", "Camera Settings Reset", "Reset Network Set."):
        assert open_refused(row, {M.ALLOW}), row
        assert drive.press_refused("right", row, f"PP1 Copy {row}", "submenu", allow=[M.ALLOW]), row
        assert drive.press_refused("enter", row, f"PP1 Copy {row}", "submenu", confirm=True, allow=[M.ALLOW]), row
    assert safety.allow_refused(M.ALLOW) is None and safety.never_open("Reset")


@pytest.mark.parametrize("text", ["Reset PP10 to the default setting? OK Cancel", "Reset camera settings? Enter Cancel",
                                  "Initialize? OK Cancel", "Reset Network Set.? OK Cancel", "PP1 Black Level Copy Reset",
                                  "Reset all settings to the default? PP1 OK Cancel", "", "Copy PP1 to PP2? OK Cancel"])
def test_only_the_profiles_own_question_is_taken(text):
    assert safety.profile_reset_dialog(text, "PP1") != ""
    assert safety.profile_reset_dialog(QUESTION, "PP1") == ""
    assert safety.profile_reset_dialog("Reset PP 10 to the default setting? OK", "PP10") == ""


# ---------------------------------------------------------------- one profile's reset, on a made-up camera

class PanelCam:
    """A made-up camera on a profile's settings, Reset lit: Right opens the question, whose lit button Up and Down move
    (`moves`), MENU cancels it, Enter on it shows `after`: "panel", "complete" (the a1 II's completion notice,
    "Complete." and OK) or "notice" (`after_text`, `after_lit` lit). MENU or Enter on either notice shows `after_menu`
    ("panel"); `menu_refused`: the link refuses MENU on them (LinkError). The panel's title as OCR reads it is `title`,
    or a list of readings, one a frame (the last kept), and `after_title` (a reading or a list) once the question has
    closed. The vision model reads the title as `second` (None: not reachable), the question as `qsecond` and a notice
    after OK as `csecond` (an answer, or None). `moved_question`: the question's text after a move. Every press is
    kept, with whether one row was lifted for it (may_open_exact)."""
    def __init__(self, question=QUESTION, lit="OK", moves=None, after="panel", row="Reset", title="PP1",
                 after_title=None, second=None, qsecond=None, moved_question=None, after_text=OTHER_NOTICE,
                 after_lit="OK", csecond=None, after_menu="panel", menu_refused=False):
        self.state, self.question, self.button, self.moves, self.after = "panel", question, lit, moves or {}, after
        self.row, self.pressed, self.may_open, self.may_open_exact, self.n = row, [], frozenset(), None, 0
        self.titles, self.at, self.after_titles = self.listed(title), 0, after_title
        self.second, self.qsecond, self.moved_question, self.asked = second, qsecond, moved_question, []
        self.after_text, self.after_lit, self.csecond, self.after_menu = after_text, after_lit, csecond, after_menu
        self.menu_refused = menu_refused
        self.logged, self.refreshed = [], []
        self.run = SimpleNamespace(log=lambda kind, **f: self.logged.append((kind, f)))

    @staticmethod
    def listed(t):
        return list(t) if isinstance(t, (list, tuple)) else [t]

    @property
    def panel_title(self):
        return self.titles[min(self.at, len(self.titles) - 1)]

    def judged(self, kind):
        return [f for k, f in self.logged if k == kind]

    @property
    def frame(self):
        return SimpleNamespace(image=None, path=Path(f"{self.n:05d}_{self.state}.png"))

    def read(self):
        return SimpleNamespace(kind={"panel": "submenu", "question": "notice", "notice": "notice",
                                     "complete": "notice"}[self.state])

    def lit(self):
        return {"panel": self.row, "question": self.button, "notice": self.after_lit, "complete": "OK"}[self.state]

    def text(self):
        return {"panel": f"{self.panel_title} Saturation Color Phase Copy Reset", "question": self.question,
                "notice": self.after_text, "complete": COMPLETE}[self.state]

    def title(self):
        return self.panel_title if self.state == "panel" else ""

    def answer(self, prompt):
        self.asked.append((self.frame.path.name, prompt))
        if prompt == "notice":
            return self.qsecond if self.state == "question" else self.csecond if self.state != "panel" else None
        if self.second is None:
            return None
        s = self.listed(self.second)
        return {"title": s[min(self.at, len(s) - 1)] if self.state == "panel" else "", "selected": ""}

    def press(self, key, **kw):
        self.pressed.append((key, self.may_open_exact is not None))
        self.n += 1
        if self.state == "panel" and key in ("right", "enter"):
            self.state = "question"
        elif self.state == "question" and key in ("menu", "enter"):
            self.state = "panel" if key == "menu" else self.after
            if self.after_titles is not None:
                self.titles, self.at = self.listed(self.after_titles), 0
        elif self.state == "question":
            self.button = self.moves.get((self.button, key), self.button)
            if self.moved_question:
                self.question = self.moved_question
        elif self.state in ("complete", "notice") and key in ("menu", "enter"):
            if key == "menu" and self.menu_refused:
                from camkit.link import LinkError
                raise LinkError("the camera did not accept MENU")
            self.state = self.after_menu

    def refresh(self, tag):
        self.refreshed.append(tag)
        self.n += 1
        self.at += 1


@pytest.fixture
def panel(monkeypatch):
    import camkit.live
    cams = []

    def make(**kw):
        cam = PanelCam(**kw)
        cams.append(cam)
        return cam
    monkeypatch.setattr(camkit.live, "lit_text", lambda image, path: cams[-1].lit())
    monkeypatch.setattr(camkit.live, "text_of", lambda cam: cam.text())
    monkeypatch.setattr(M, "title", lambda cam: cam.title())
    monkeypatch.setattr(M, "ask_reader", lambda path, prompt: cams[-1].answer(prompt))
    monkeypatch.setattr(M, "to_reset_row", lambda cam, cycle, model, profile: None)
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    return make


def keys(cam):
    return [k for k, _ in cam.pressed]


def test_a_reset_opens_reset_lifted_for_that_press_alone_and_ends_back_on_the_profile(panel):
    cam = panel()
    got = M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert keys(cam) == ["right", "enter"]
    assert cam.pressed[0][1] is True and cam.pressed[1][1] is False, "lifted for Right alone"
    assert cam.may_open == frozenset() and cam.may_open_exact is None, "Reset is never a may_open name"
    assert got["question"] == QUESTION and got["profile"] == "PP1" and got["row_by"] == "title"
    later = panel(lit="Cancel", moves={("Cancel", "up"): "OK"})
    M.reset_one(later, None, None, "PP1", lambda m: None)
    assert keys(later) == ["right", "up", "enter"], "from Cancel Up, Enter on OK alone"
    assert later.refreshed == ["reset-question", "reset-question"], "a fresh frame before and after the move"


@pytest.mark.parametrize("kw,said", [({"question": "Reset PP10 to the default setting? OK Cancel"}, "not PP1 alone"),
                                     ({"question": "Reset camera settings? OK Cancel"}, "not a Picture Profile's own"),
                                     ({"question": "Copy PP1 to PP2? OK Cancel"}, "not read as a confirmation"),
                                     ({"lit": "Copy"}, "neither OK nor Cancel"),
                                     ({"lit": "Cancel"}, "OK never lit")])
def test_a_question_that_is_not_the_profiles_backs_out_with_menu(panel, kw, said):
    from prove_run import Failed
    cam = panel(**kw)
    with pytest.raises(Failed, match=said):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert keys(cam)[0] == "right" and keys(cam)[-1] == "menu" and "enter" not in keys(cam)
    assert cam.state == "panel" and cam.may_open_exact is None


def test_from_cancel_only_up_and_down_at_most_two_moves(panel):
    from prove_run import Failed
    cam = panel(lit="Cancel", moves={("Cancel", "left"): "OK", ("Cancel", "right"): "OK"})
    with pytest.raises(Failed, match="OK never lit"):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert keys(cam) == ["right", "up", "down", "menu"], "never Left or Right on the question"
    down = panel(lit="Cancel", moves={("Cancel", "down"): "OK"})
    M.reset_one(down, None, None, "PP1", lambda m: None)
    assert keys(down) == ["right", "up", "down", "enter"]


def test_the_question_is_judged_whole_again_after_a_move(panel):
    """A move that lights OK but leaves another question on screen backs out: the re-judge after each move is what
    stops it (without it Enter would go on OK)."""
    from prove_run import Failed
    cam = panel(lit="Cancel", moves={("Cancel", "up"): "OK"},
                moved_question="Reset PP10 to the default setting? OK Cancel")
    with pytest.raises(Failed, match="not PP1 alone"):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert "enter" not in keys(cam) and keys(cam)[-1] == "menu"


def test_enter_goes_only_where_drives_own_enter_guard_passes(panel, monkeypatch):
    import drive
    from prove_run import Failed
    seen = []

    def guard(key, lit, text, kind, confirm=False, **kw):
        seen.append((key, lit, text, kind, confirm))
        return "refused for the test"
    monkeypatch.setattr(drive, "press_refused", guard)
    cam = panel()
    with pytest.raises(Failed, match="Enter refused: refused for the test"):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert keys(cam) == ["right", "menu"] and seen == [("enter", "OK", QUESTION, "notice", True)]


@pytest.mark.parametrize("kw", [{"row": "Setting Reset"}, {"row": "Camera Settings Reset"}, {"title": "PP10"},
                                {"row": "Copy"}])
def test_no_press_opens_a_row_that_is_not_the_profiles_reset(panel, kw):
    from prove_run import Failed
    cam = panel(**kw)
    with pytest.raises(Failed, match="Reset not opened"):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert cam.pressed == []


def test_the_lift_the_tool_hands_the_camera_judges_the_row_and_the_title_on_the_same_frame(panel, monkeypatch):
    """open_reset's predicate (LiveCamera.may_open_exact): true only for the frame row_judged passed, the lit row Reset
    alone and the title the profile's on it."""
    cam = panel()
    lifts = []
    real = cam.press

    def press(key, **kw):
        if cam.may_open_exact is not None:
            lifts.append((cam.frame, cam.may_open_exact))
        real(key, **kw)
    cam.press = press
    M.open_reset(cam, "PP1")
    (frame, exact), = lifts
    cam.state, cam.n = "panel", 0                       # the frame the row was judged on, again
    assert exact(frame, "Reset") is True
    assert exact(frame, "Setting Reset") is False and exact(frame, "Reset Network Set.") is False
    assert exact(SimpleNamespace(path=Path("99999_other.png")), "Reset") is False
    cam.titles = ["PP10"]
    assert exact(frame, "Reset") is False


Q3 = "Reset PP3 to the default setting? OK Cancel"
LOOKALIKE = "PРЗ"              # what OCR read for the PP3 title on the second trial's 00110-00112 frames


def test_a_flaky_title_before_reset_passes_on_a_later_fresh_frame_judged_as_read(panel):
    """The second trial's PP3 title read "PP3" on one frame and "PРЗ" on the next: with the vision model unreachable
    the guard before Reset judges fresh frames while it refuses, no press between, and the press goes on the first
    frame it passes as it is."""
    cam = panel(question=Q3, title=[LOOKALIKE, LOOKALIKE, "PP3"])
    said = []
    got = M.reset_one(cam, None, None, "PP3", said.append)
    assert keys(cam) == ["right", "enter"] and cam.pressed[0][1] is True
    looks = cam.judged("pp_reset_row_judged")
    assert [x["look"] for x in looks] == [1, 2, 3] and [bool(x["why"]) for x in looks] == [True, True, False]
    assert all(x["title"] == LOOKALIKE and "not PP3 alone" in x["why"] for x in looks[:2])
    assert got["row_frame"] == looks[2]["frame"] == "00002_panel.png", "the press is judged on the frame that passed"
    assert got["back"] == "confirmed" and got["back_by"] == "title" and looks[2]["by"] == "title"


def test_a_look_alike_title_passes_when_the_vision_model_reads_the_profile(panel):
    cam = panel(question=Q3, title=LOOKALIKE, second="PP3", after_title="PP3")
    got = M.reset_one(cam, None, None, "PP3", lambda m: None)
    assert keys(cam) == ["right", "enter"] and got["row_by"] == "both readers"
    looks = cam.judged("pp_reset_row_judged")
    assert len(looks) == 1 and looks[0]["second"] == "PP3" and looks[0]["by"] == "both readers"
    assert [p for f, p in cam.asked if f == "00000_panel.png"] == ["option"], "one call a frame judged"


@pytest.mark.parametrize("title,second", [(LOOKALIKE, "PP8"), (LOOKALIKE, ""), (LOOKALIKE, None), ("PP4", "PP3"),
                                          ("PP 3 Gamma", "PP3"), ("PP33", "PP3"), ("", "PP3"), ("PP3", "PP8")])
def test_the_guard_before_reset_refuses_unless_the_title_is_the_profiles_by_one_way(panel, title, second):
    """A look-alike title with the vision model reading another profile, nothing, or unreachable: refused; a title of
    another profile, whatever the vision model reads: refused; a strict title the vision model reads as another
    profile: refused. Three fresh frames looked at, no press."""
    from prove_run import Failed
    cam = panel(question=Q3, title=title, second=second)
    with pytest.raises(Failed, match=r"the last of 4 frames looked at\): Reset not opened"):
        M.reset_one(cam, None, None, "PP3", lambda m: None)
    assert cam.pressed == [] and cam.may_open_exact is None
    assert [x["look"] for x in cam.judged("pp_reset_row_judged")] == [1, 2, 3, 4], "the first frame and three fresh"


def test_the_two_ways_in_safety():
    assert safety.profile_reset_title("PP3", "PP3") == ("", "title")
    assert safety.profile_reset_title(LOOKALIKE, "PP3", "PP3") == ("", "both readers")
    assert safety.profile_reset_title(LOOKALIKE, "PP3")[0] and safety.profile_reset_title(LOOKALIKE, "PP3", "")[0]
    assert "vision model reads" in safety.profile_reset_title("PP3", "PP3", "PP8")[0]
    assert safety.profile_reset_row("Reset", LOOKALIKE, "PP3", "PP3") == ""
    assert safety.profile_reset_row("Setting Reset", LOOKALIKE, "PP3", "PP3") != ""
    assert not safety.profile_title_agreed(LOOKALIKE, LOOKALIKE, "PP3"), "the vision reading is judged strictly"
    assert not safety.profile_title_agreed("PP8", "PP3", "PP3") and not safety.profile_title_agreed("PP3", "PP3", "X")


def test_the_guard_before_reset_judges_a_fresh_frame_of_another_kind_too(panel):
    cam = panel(question=Q3, title="PP3")
    kinds = iter(["dialog", "submenu"])
    real = cam.read
    cam.read = lambda: SimpleNamespace(kind=next(kinds, None) or real().kind)
    assert M.row_judged(cam, "PP3") == ("", "title") and cam.pressed == []
    assert [x["screen"] for x in cam.judged("pp_reset_row_judged")] == ["dialog", "submenu"]


@pytest.mark.parametrize("text,name", [(LOOKALIKE, "PP3"), ("PP 3", "PP3"), ("PPl0", "PP10"), ("PP3 Gamma", None),
                                       ("Picture Profile", None), ("User1", None), ("P#", None), ("", None)])
def test_a_title_names_a_profile_only_when_it_is_the_name_alone(text, name):
    assert M.title_names(text) == name == safety.profile_title_names(text)


@pytest.mark.parametrize("qsecond,ok", [({"text": "Reset PP3 to the default setting?", "buttons": ["OK", "Cancel"]}, True),
                                        (None, True), ({"text": "", "buttons": []}, True),
                                        ({"text": "Reset PP8 to the default setting?", "buttons": ["OK"]}, False)])
def test_the_vision_models_reading_of_the_question_is_kept_and_refuses_another_profile(panel, qsecond, ok):
    from prove_run import Failed
    cam = panel(question=Q3, title="PP3", qsecond=qsecond)
    if ok:
        got = M.reset_one(cam, None, None, "PP3", lambda m: None)
        assert keys(cam) == ["right", "enter"]
        assert got["question_second"] == (None if qsecond is None else qsecond["text"])
    else:
        with pytest.raises(Failed, match="vision model reads the question as naming PP8"):
            M.reset_one(cam, None, None, "PP3", lambda m: None)
        assert keys(cam) == ["right", "menu"]
    assert any(p == "notice" for _, p in cam.asked)


@pytest.mark.parametrize("after_title,second,by", [
    (LOOKALIKE, "PP3", "both readers"), (LOOKALIKE, None, "title with look-alikes"),
    (LOOKALIKE, "", "title with look-alikes"), (LOOKALIKE, "PP5", None), ("PP3", "PP5", None), ("PP3", None, "title"),
    ("P#", "PP3", "second reader"), ("", "PP 3", "second reader"), ("PP5", "PP3", None), ("PP33", "PP3", None),
    ("P#", "PP5", None), ("P#", "", None), ("P#", None, None), ("Picture Profile", "Picture Profile", None),
    ("PP3", "Picture Profile PP5", None), (LOOKALIKE, "PP3 PP5", None)])
def test_the_back_check_asks_the_vision_model_of_every_look(panel, after_title, second, by):
    cam = panel(question=Q3, title="PP3", after_title=after_title)
    cam.press("right")
    cam.press("enter")                                   # the question's OK: back on the panel
    cam.second = second
    got = M.back_on_panel(cam, "PP3")
    assert got["by"] == by and got["back"] == ("confirmed" if by else "unconfirmed")
    assert len(cam.asked) == len(got["looks"]), "the vision model asked once a look"
    if not by:
        assert len(got["looks"]) == 3 and got["frame"] == got["looks"][-1]["frame"]


CSECOND = {"text": "Complete.", "buttons": ["OK"]}     # the vision model's reading of the completion notice


@pytest.mark.parametrize("csecond", [CSECOND, None, {"text": "Complete. OK", "buttons": []}])
def test_the_completion_notice_is_kept_closed_with_menu_and_the_profile_is_back(panel, csecond):
    said = []
    cam = panel(after="complete", csecond=csecond)
    got = M.reset_one(cam, None, None, "PP1", said.append)
    assert keys(cam) == ["right", "enter", "menu"], "the notice closed with MENU, the kit's way for a notice"
    assert got["complete"] is True and got["complete_frame"] == "00002_complete.png" and got["complete_text"] == COMPLETE
    assert got["complete_closed_by"] == "menu" and got["back"] == "confirmed" and got["back_frame"] == "00003_panel.png"
    assert got["complete_second"] == (None if csecond is None else "Complete. OK")
    assert any("completion notice 00002_complete.png closed with MENU, back on its settings" in x for x in said)
    assert [x["why"] for x in cam.judged("pp_reset_complete_judged")] == [""] and not cam.judged("pp_reset_after_ok")


def test_the_settings_straight_back_after_ok_count_with_no_completion_notice(panel):
    said = []
    cam = panel()
    got = M.reset_one(cam, None, None, "PP1", said.append)
    assert keys(cam) == ["right", "enter"] and got["complete"] is False and got["complete_frame"] is None
    assert got["back"] == "confirmed" and any("no completion notice" in x for x in said)


@pytest.mark.parametrize("kw,said", [
    ({"after": "notice", "after_text": "This function is currently disabled. OK"}, "not 'Complete.' and OK alone"),
    ({"after": "notice", "after_text": "Unable to reset the profile. OK"}, "reads as a confirmation"),
    ({"after": "notice", "after_text": OTHER_NOTICE}, "reads as a confirmation"),
    ({"after": "notice", "after_text": QUESTION, "after_lit": "OK"}, "holds a question"),
    ({"after": "notice", "after_text": "Complete. OK Cancel"}, "offers Cancel"),
    ({"after": "notice", "after_text": "Complete. Copied to PP2. OK"}, "not 'Complete.' and OK alone"),
    ({"after": "notice", "after_text": "Complete?", "after_lit": "OK"}, "holds a question"),
    ({"after": "notice", "after_text": "Complete. OK", "after_lit": "Cancel"}, "the lit button reads 'Cancel'"),
    ({"after": "notice", "after_text": "Complete. OK", "after_lit": ""}, "the lit button reads ''"),
    ({"after": "complete", "csecond": {"text": "Unable to reset.", "buttons": ["OK"]}},
     "the vision model's reading reads as a confirmation"),
    ({"after": "complete", "csecond": {"text": "Complete. Saved.", "buttons": ["OK"]}}, "the vision model reads"),
    ({"after": "complete", "csecond": {"text": "Complete.", "buttons": ["OK", "Cancel"]}}, "offers Cancel"),
    ({"after": "complete", "csecond": {"text": "", "buttons": []}}, "the vision model read no text")])
def test_any_other_screen_after_ok_is_menu_only_and_stops(panel, kw, said):
    """Another notice, a question, an error, the completion notice with a word more, or the vision model reading
    something else than Complete on its frame: looked at on two frames, MENU and nothing else, the run stops."""
    from prove_run import Failed
    cam = panel(**kw)
    with pytest.raises(Failed, match="neither its completion notice nor PP1's settings") as e:
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert said in str(e.value) and "whether PP1 was reset is not known" in str(e.value)
    assert keys(cam) == ["right", "enter", "menu"], "MENU alone after OK"
    assert cam.refreshed == ["after-ok"], "two frames looked at, no press between"
    looks = cam.judged("pp_reset_complete_judged")
    assert [x["look"] for x in looks] == [1, 2] and all(x["why"] for x in looks)
    logged = cam.judged("pp_reset_after_ok")
    shown = kw.get("after_text", OTHER_NOTICE) if kw["after"] == "notice" else COMPLETE
    assert len(logged) == 1 and logged[0]["text"] == shown, "the words kept"
    assert logged[0]["why"] and logged[0]["frame"] == "00003_" + kw["after"] + ".png"


def test_a_panel_of_another_title_straight_after_ok_stops_with_no_press(panel):
    from prove_run import Failed
    cam = panel(title="PP1", after_title="PP10")
    with pytest.raises(Failed, match="a panel whose title is not PP1's"):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert keys(cam) == ["right", "enter"], "nothing pressed on a panel: the session's close takes it from there"


def test_a_completion_notice_then_no_profile_title_is_kept_as_unconfirmed_and_counts(panel):
    said = []
    cam = panel(after="complete", csecond=CSECOND, after_title="P#")
    got = M.reset_one(cam, None, None, "PP1", said.append)
    assert keys(cam) == ["right", "enter", "menu"], "no press after the notice closed: the download closes with MENU"
    assert got["complete"] is True and got["back"] == "unconfirmed" and got["back_by"] is None
    assert [x["kind"] for x in got["back_looks"]] == ["submenu"] * 3 and got["back_frame"] == "00005_panel.png"
    logged = cam.judged("pp_reset_after_ok")
    assert logged and logged[0]["complete_frame"] == "00002_complete.png" and logged[0]["looks"] == got["back_looks"]
    assert any("counted as reset, the camera said Complete; back unconfirmed" in x for x in said)


def test_menu_refused_on_the_completion_notice_closes_it_with_ok_through_drives_guard(panel, monkeypatch):
    import drive
    seen = []
    real = drive.press_refused

    def guard(key, lit, text, kind, confirm=False, **kw):
        seen.append((key, lit, text, kind, confirm))
        return real(key, lit, text, kind, confirm, **kw)
    monkeypatch.setattr(drive, "press_refused", guard)
    cam = panel(after="complete", csecond=CSECOND, menu_refused=True)
    got = M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert keys(cam) == ["right", "enter", "menu", "enter"] and got["complete_closed_by"] == "enter"
    assert seen[-1] == ("enter", "OK", COMPLETE, "notice", False), "judged as a notice, never as a confirmation"
    assert cam.refreshed == ["complete-notice"] and got["back"] == "confirmed"
    assert drive.press_refused("enter", "OK", COMPLETE, "notice") == ""


@pytest.mark.parametrize("text,lit,second,ok", [
    ("Complete. OK", "OK", "Complete. OK", True), ("Complete.OK", "OK", None, True), ("Complete OK", "OK.", "Complete", True),
    ("  Complete .  OK ", " OK ", "complete.", True), ("Comp1ete. OK", "OK", None, False),
    ("Complete. OK", "OK", "", False), ("Complete. OK", "OK", "Completed. OK", False),
    ("Complete? OK", "OK", None, False), ("Complete. OK Cancel", "OK", None, False),
    ("Format complete. OK", "OK", None, False), ("Reset complete. OK", "OK", None, False),
    ("Complete. OK", "Enter", None, False), ("", "OK", "Complete.", False),
    ("Complete. OK", "OK", "Reset PP1 to the default setting? OK Cancel", False)])
def test_the_completion_notice_in_safety_is_complete_and_ok_alone(text, lit, second, ok):
    assert (safety.profile_reset_complete(text, lit, second) == "") is ok


def test_a_peek_opens_records_and_cancels_with_menu_never_enter(panel, monkeypatch):
    import memreg_run
    monkeypatch.setattr(memreg_run, "download", lambda c, link, hdmi, tag: Path(f"00116_{tag}.DAT"))
    monkeypatch.setattr(M, "changed_keys", lambda a, b: [])
    cam = panel(question=Q3, title="PP3", after_title=[LOOKALIKE] * 3)
    said = []
    got = M.peek(cam, None, None, None, None, "PP3", Path("start.DAT"), set(), said.append)
    assert keys(cam) == ["right", "menu"] and "enter" not in keys(cam) and cam.state == "panel", "MENU cancels"
    assert got["back_on_panel"] and got["back_by"] == "title with look-alikes" and got["button"] == "OK"
    assert got["accepted"] and got["text"] == Q3 and got["download"] == "00116_after-peek.DAT"
    assert got["back_frame"] == "00002_panel.png" and any("back on PP3's settings (title with look-alikes)" in s
                                                          for s in said)


# ---------------------------------------------------------------- the real LiveCamera.press, over a made-up link

class LiveWorld:
    """A made-up link and eyes under a real camkit.live.LiveCamera: the profile's panel (Reset lit, its title
    `title`) and the question Right opens on it (OK or Cancel lit); MENU cancels, Enter on the question resets.
    `stop_on_question`: a STOP file appears once the question is open, so the next press that is not a cleanup press
    raises StopRequested at the link, as Link.press does."""
    def __init__(self, tmp_path, lit="OK", title="PP1", row="Reset", stop_on_question=False, after="panel"):
        self.tmp, self.state, self.button, self.title, self.row = tmp_path, "panel", lit, title, row
        self.after = after
        self.stop_on_question, self.stop, self.sent, self.n, self.moves = stop_on_question, False, [], 0, 0

    # the link
    def press(self, key, hold_ms=60, allow=frozenset(), cleanup=False, screen=None, on_shooting=frozenset()):
        from camkit.link import StopRequested
        if self.stop and not cleanup:
            raise StopRequested("STOP: the run's STOP file asks it to stop")
        self.sent.append((key, cleanup))
        self.moves += 1
        if self.state == "panel" and key == "right":
            self.state = "question"
            self.stop = self.stop_on_question
        elif self.state == "question" and key in ("menu", "enter"):
            self.state = self.after if key == "enter" else "panel"
        elif self.state == "question" and key in ("up", "down"):
            self.button = "OK"
        elif self.state == "complete" and key in ("menu", "enter"):
            self.state = "panel"

    # the eyes
    timing = None

    def snapshot(self, tag):
        self.n += 1
        lit = {"panel": self.row, "question": self.button, "complete": "OK"}[self.state]
        text = {"panel": f"{self.title} Copy Reset", "question": QUESTION, "complete": COMPLETE}[self.state]
        return SimpleNamespace(image={"state": self.state, "lit": lit, "text": text, "title": self.title},
                               path=self.tmp / f"{self.n:05d}_{tag}.png", t=0.0)

    def grab(self, tag, save=True):
        return self.snapshot(tag)

    def settle(self, frame, key, expect_change=True, sent_at=None, **kw):
        return self.snapshot(key), True


@pytest.fixture
def live_world(tmp_path, monkeypatch):
    from camkit import live
    from camkit.runs import Run
    monkeypatch.setattr(live.screen, "read", lambda f: SimpleNamespace(
        kind={"panel": "submenu", "question": "notice", "complete": "notice"}[f.image["state"]], focus=None,
        frame_path=None))
    monkeypatch.setattr(live.screen, "same_state", lambda a, b: False)
    monkeypatch.setattr(live, "lit_text", lambda image, path: image["lit"])
    monkeypatch.setattr(live, "lit_box", lambda image, kind=None: (0, 0, 10, 10))
    monkeypatch.setattr(live, "text_of", lambda cam: cam.frame.image["text"])
    monkeypatch.setattr(M, "title", lambda cam: cam.frame.image["title"])
    monkeypatch.setattr(M, "ask_reader", lambda path, prompt: None)
    monkeypatch.setattr(M, "to_reset_row", lambda cam, cycle, model, profile: None)
    monkeypatch.setattr(M.time, "sleep", lambda s: None)

    def make(**kw):
        w = LiveWorld(tmp_path, **kw)
        cam = live.LiveCamera(w, w, Run("pp_live", root=tmp_path))
        return w, cam
    return make


def events(cam):
    return [json.loads(x) for x in (cam.run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_through_the_real_press_one_row_is_lifted_for_one_press(live_world):
    w, cam = live_world()
    got = M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert [k for k, _ in w.sent] == ["right", "enter"] and got["back"] == "confirmed"
    assert cam.may_open == frozenset() and cam.may_open_exact is None
    assert [e["kind"] for e in events(cam)].count("press_lifted_exact") == 1


def test_through_the_real_press_the_completion_notice_is_closed_with_menu(live_world):
    w, cam = live_world(after="complete")
    got = M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert w.sent == [("right", False), ("enter", False), ("menu", False)] and w.state == "panel"
    assert got["complete"] is True and got["back"] == "confirmed" and got["complete_closed_by"] == "menu"
    assert [e["kind"] for e in events(cam)].count("pp_reset_complete_judged") == 1


def test_the_lift_holds_only_for_the_frame_judged(live_world, monkeypatch):
    """The screen moved between the judgement and the press (the link's count moved: LiveCamera reads it afresh): the
    lift's frame is not the one the press is judged on, so the press is refused and nothing goes out."""
    w, cam = live_world()
    real = M.row_judged

    def judged_then_moved(c, profile, **kw):
        got = real(c, profile, **kw)
        w.moves += 1                                     # a press sent past the camera: the next press reads afresh
        return got
    monkeypatch.setattr(M, "row_judged", judged_then_moved)
    with pytest.raises(safety.Refused, match="never opened"):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert w.sent == [] and cam.may_open_exact is None


def test_the_camera_layer_lift_is_exact_used_up_and_never_lifts_what_no_allowance_opens(live_world):
    w, cam = live_world()
    with pytest.raises(safety.Refused, match="never opened"):
        cam.press("right")                               # unset: as before
    cam.may_open_exact = lambda frame, lit: True
    cam.press("right")
    assert w.sent == [("right", False)] and cam.may_open_exact is None, "used up by the press"
    cam.press("menu")
    with pytest.raises(safety.Refused, match="never opened"):
        cam.press("right")                               # the next press: nothing lifted
    w2, cam2 = live_world(row="Format")
    cam2.may_open_exact = lambda frame, lit: True
    with pytest.raises(safety.Refused, match="never opened"):
        cam2.press("right")
    assert w2.sent == []
    w3, cam3 = live_world(row="Setting Reset")
    cam3.may_open_exact = lambda frame, lit: lit.strip() == "Reset"
    with pytest.raises(safety.Refused, match="never opened"):
        cam3.press("right")
    assert w3.sent == []


def test_a_stop_while_the_question_is_open_ends_with_menu_never_enter(live_world):
    from camkit.link import StopRequested
    w, cam = live_world(lit="Cancel", stop_on_question=True)
    with pytest.raises(StopRequested):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert w.state == "question" and cam.may_open_exact is None
    cam.cancel_to_menu()                                     # the session's close: cleanup presses only
    assert ("enter", False) not in w.sent and ("enter", True) not in w.sent
    assert w.sent[-1] == ("menu", True) and w.state == "panel"


# ---------------------------------------------------------------- the session: every exit restores

class FakeEyes:
    closed = 0

    def attach(self, link):
        pass

    def close(self):
        self.closed += 1


@pytest.fixture
def world(tmp_path, monkeypatch):
    """runner.prover_session as it is, over a made-up link and camera: the start download, the body, the camera closed
    after a failure, the start file put back (session.finish) and checked."""
    import camkit.frames
    import camkit.runs
    import memreg_run
    import proving.nav
    import runner
    log = {"downloads": [], "closed": 0, "finished": [], "checked": [], "reset": [], "stop_after": None,
           "verified": [], "verify_changes": [], "control": [], "control_changes": ["global:0x04e9", "global:0x0053"],
           "first_reset_changes": ["global:0x04e9", "global:0x0053"], "stop_in_control": False}
    run = SimpleNamespace(dir=tmp_path / "kit2_pp_reset_stills", root=tmp_path, log=lambda *a, **k: None)
    run.dir.mkdir()
    run.stop_requested = lambda: log["stop_after"] is not None and len(log["reset"]) >= log["stop_after"]
    run.stop_reason = lambda: f"{run.dir / 'STOP'} asks the run to stop"

    class Link:
        def __init__(self, r):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def download(self, tag):
            p = run.dir / "dat" / f"{len(log['downloads']):05d}_{tag}.DAT"
            log["downloads"].append(p)
            return p
    cam = SimpleNamespace(may_open=frozenset())
    monkeypatch.setattr(runner, "Link", Link)
    monkeypatch.setattr(runner, "LiveCamera", lambda link, eyes, r, may_open=(): cam)
    monkeypatch.setattr(runner, "close", lambda c, link: log.__setitem__("closed", log["closed"] + 1))
    monkeypatch.setattr(proving.nav, "to_shooting", lambda link, eyes, why: None)
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    monkeypatch.setattr(runner.session, "finish", lambda link, start, tag="after", **kw: log["finished"].append(start)
                        or session.Ending(Path("after.DAT"), ["a change"], True))
    monkeypatch.setattr(runner.session, "check_restore", lambda r, e, start, **kw: log["checked"].append(start) or 0)
    monkeypatch.setattr(runner, "load_scan", lambda scan, mode=None: ([], {}))
    monkeypatch.setattr(camkit.runs, "Run", lambda name: run)
    monkeypatch.setattr(camkit.frames, "eyes_from_config", lambda r: FakeEyes())
    monkeypatch.setattr(memreg_run, "download", lambda c, link, hdmi, tag: link.download(tag))
    monkeypatch.setattr(M, "scan_dir", lambda *a, **k: Path("kit2_page_scan"))
    monkeypatch.setattr(M, "read_profiles", lambda c, link, cycle, model, say, **kw: ["Off", "PP1", "PP2", "PP3"])

    def changed_keys(a, b):
        if "verify" in b.name:
            return log["verify_changes"]
        if M.CONTROL_TAG in b.name:
            return log["control_changes"]
        if M.CONTROL_TAG in a.name:
            return log["first_reset_changes"]
        return ["global:0x04e9", "global:0x0053"]
    monkeypatch.setattr(M, "changed_keys", changed_keys)
    log["control_elements"] = {"changed": ["global:0x04e9"], "others": [], "missing": []}
    monkeypatch.setattr(M, "control_elements", lambda camera, a, b, p, mode: log["control_elements"])
    monkeypatch.setattr(M, "control_wrote", lambda camera, a, b, p, changed: [k for k in changed
                                                                             if k in changed_keys(a, b)])
    monkeypatch.setattr(M, "family_ids", lambda camera: {0x04e9})
    monkeypatch.setattr(M, "family_copies", lambda camera: {0x04e9: "live"})

    def control_change(c, cycle, model, p, say):
        from camkit.link import StopRequested
        log["control"].append(p)
        if log["stop_in_control"]:
            raise StopRequested("STOP: the run's STOP file asks it to stop")
        return {"moves": ["down"], "chosen_frame": "00010_down.png"}
    monkeypatch.setattr(M, "control_change", control_change)
    monkeypatch.setattr(M, "start_mode", lambda camera, start: log.get("start_mode"))

    def verify_pass(c, link, cycle, model, done, r, say, need_both=False):
        log["verified"].append(list(done))
        return {p: log.get("entered", {}).get(p, "confirmed") for p in done}
    monkeypatch.setattr(M, "verify_pass", verify_pass)

    def reset_one(c, cycle, model, p, say, open_key="right", **kw):
        log["need_both"] = kw.get("need_both")
        if log.get("fail_on") == p:
            raise RuntimeError(f"the eyes' feed went away during {p}")
        log["reset"].append(p)
        return {"profile": p}
    monkeypatch.setattr(M, "reset_one", reset_one)
    args = SimpleNamespace(scan="latest", run=None, peek=False, open_key="right", no_control=False,
                           control_profile=None, need_both_readers=False, ocr_alone_ok=False)
    log["args"] = args
    log["go"] = lambda asked=(), recorded=None: M.run_session(args, "TEST-CAM_fw9.99", "Stills", list(asked), recorded,
                                                              "the word")
    log["offer"] = lambda labels: monkeypatch.setattr(M, "read_profiles",
                                                      lambda c, link, cycle, model, say, **kw: list(labels))
    log["result"] = lambda: json.loads((run.dir / M.RESULT).read_text(encoding="utf-8"))
    return log


def test_a_whole_run_resets_each_profile_verifies_and_ends_restored(world, capsys):
    assert world["go"]() == 0
    r = world["result"]()
    assert world["reset"] == ["PP1", "PP2", "PP3"] and r["finished"] and r["restored"] and r["verified"] is True
    assert [p["profile"] for p in r["profiles"]] == ["PP1", "PP2", "PP3"] and r["asked"] is None
    assert r["last"] == "dat/00004_reset-PP3.DAT" and r["profiles"][0]["changed"] == ["global:0x04e9", "global:0x0053"]
    assert r["profiles"][0]["family_changed"] == ["global:0x04e9"] and r["family"] == M.FAMILY and r["mode"] == "Stills"
    assert world["verified"] == [["PP1", "PP2", "PP3"]] and r["verify"]["download"] == "dat/00005_verify.DAT"
    assert world["control"] == ["PP1"] and world["need_both"] is True, "a whole run needs both readers"
    c = r["control"]
    assert c["profile"] == "PP1" and c["parameter"] == "Black Level" and c["download"] == "dat/00001_control-set.DAT"
    assert c["changed"] == ["global:0x04e9"] and c["reset_wrote"] == ["global:0x04e9"] and c["ok"] is True
    assert c["reset_download"] == "dat/00002_reset-PP1.DAT" and r["need_both_readers"] is True
    assert c["copies_changed"] == {"in_use": 1, "stills": 0, "movie": 0} == c["copies_reset_wrote"]
    assert world["finished"] == [world["downloads"][0]] and world["checked"] == [world["downloads"][0]]
    out = capsys.readouterr().out
    assert "1 of the profiles' parameters, 1 others (global:0x0053)" in out
    assert "finished: the camera offered 3 profiles (PP1, PP2, PP3), 3 reset; control: PP1's Black Level changed 1 " \
           "records, its Reset wrote all of them back" in out and "; verified" in out
    assert r["offered_profiles"] == ["PP1", "PP2", "PP3"]


def test_a_verify_pass_that_moves_a_parameter_is_not_verified_and_exits_non_zero(world, capsys):
    world["verify_changes"] = ["global:0x04e9", "global:0x0053"]
    assert world["go"]() == 1
    r = world["result"]()
    assert r["finished"] and r["verified"] is False and r["verify"]["family_changed"] == ["global:0x04e9"]
    assert "NOT verified (global:0x04e9): make_sample refuses this result" in capsys.readouterr().out


def test_a_start_file_of_another_mode_stops_before_any_press(world, capsys):
    world["start_mode"] = "Movie"
    world["offer"](["Off", "PP1"])
    assert world["go"]() == 1
    r = world["result"]()
    assert world["reset"] == [] and "saved in Movie mode, not Stills" in r["stopped"] and world["finished"]
    assert "offered" not in r


def test_a_stop_between_profiles_restores(world, capsys):
    world["stop_after"] = 1
    assert world["go"]() == 1
    r = world["result"]()
    assert world["reset"] == ["PP1"] and not r["finished"] and "StopRequested" in r["stopped"]
    assert world["closed"] == 1 and world["finished"] == [world["downloads"][0]] and r["restored"]
    assert world["verified"] == [] and r["verified"] is None
    assert "stopped before PP2" in capsys.readouterr().out


def test_an_exception_mid_profile_restores(world, capsys):
    world["fail_on"] = "PP2"
    assert world["go"]() == 1
    r = world["result"]()
    assert [p["profile"] for p in r["profiles"]] == ["PP1"] and "RuntimeError" in r["stopped"]
    assert world["closed"] == 1 and world["finished"] == [world["downloads"][0]] and world["checked"]
    assert "the eyes' feed went away during PP2" in capsys.readouterr().out


def test_an_unconfirmed_back_is_kept_the_run_goes_on_and_the_summary_says_so(world, monkeypatch, capsys):
    def reset_one(c, cycle, model, p, say, open_key="right", **kw):
        world["reset"].append(p)
        return {"profile": p, "back": "unconfirmed" if p == "PP2" else "confirmed",
                "back_frame": f"0009{len(world['reset'])}_back-on-panel.png"}
    monkeypatch.setattr(M, "reset_one", reset_one)
    assert world["go"]() == 0, "an unconfirmed back does not fail the run"
    r = world["result"]()
    assert world["reset"] == ["PP1", "PP2", "PP3"] and r["finished"] and r["restored"]
    assert r["back_unconfirmed"] == ["PP2"] and [p["back"] for p in r["profiles"]] == ["confirmed", "unconfirmed",
                                                                                      "confirmed"]
    assert len(world["downloads"]) == 6, "the start file, control-set, a download after every profile, PP2's too, verify"
    out = capsys.readouterr().out
    assert "download 00003_reset-PP2.DAT (back unconfirmed)" in out
    assert "finished: the camera offered 3 profiles (PP1, PP2, PP3), 3 reset; control:" in out
    assert "all of them back; 1 not seen back" in out
    assert "PP2 00092_back-on-panel.png" in out


REAL_RESET_ONE = M.reset_one          # the world fixture stands a made-up reset_one in; these run the real one


@pytest.mark.parametrize("kw", [{"after": "notice", "after_text": "This function is currently disabled. OK"},
                                {"after": "notice", "after_text": QUESTION},
                                {"after": "complete", "csecond": {"text": "Unable to reset.", "buttons": ["OK"]}}])
def test_an_unknown_screen_after_ok_stops_the_run_and_the_start_file_goes_back(world, panel, monkeypatch, capsys, kw):
    """Through runner.prover_session as it is: MENU alone on the screen, the run stops (exit non-zero, not finished,
    no verify), the camera closed and the start file put back and checked."""
    cams = []

    def reset_one(c, cycle, model, p, say, open_key="right", **k):
        cams.append(panel(**kw))
        world["reset"].append(p)
        return REAL_RESET_ONE(cams[-1], cycle, model, p, say, open_key)
    monkeypatch.setattr(M, "reset_one", reset_one)
    assert world["go"]() == 1
    r = world["result"]()
    assert keys(cams[0]) == ["right", "enter", "menu"] and len(cams) == 1, "MENU alone, and no next profile"
    assert r["profiles"] == [] and not r["finished"] and r["verified"] is None and world["verified"] == []
    assert "Failed" in r["stopped"] and "neither its completion notice nor PP1's settings" in r["stopped"]
    assert world["closed"] == 1 and world["finished"] == [world["downloads"][0]] and world["checked"] and r["restored"]
    assert r["completion_notice"] == 0
    assert "the start file went back on the camera (checked)" in capsys.readouterr().out


def test_the_summary_and_the_result_count_the_completion_notices(world, monkeypatch, capsys):
    def reset_one(c, cycle, model, p, say, open_key="right", **kw):
        world["reset"].append(p)
        return {"profile": p, "back": "confirmed", "complete": p != "PP3"}
    monkeypatch.setattr(M, "reset_one", reset_one)
    assert world["go"]() == 0
    r = world["result"]()
    assert r["completion_notice"] == 2 and [p["complete"] for p in r["profiles"]] == [True, True, False]
    assert r["no_notice"] == 1
    out = capsys.readouterr().out
    assert "2 of 3 showed the camera's completion notice, 1 came straight back to their settings with none " \
           "(make_sample refuses this result unless --allow-no-notice)" in out
    assert "download 00004_reset-PP3.DAT (no completion notice: its settings came straight back)" in out


def test_a_profile_the_camera_does_not_offer_stops_before_any_reset(world):
    assert world["go"](["PP2", "PP7"]) == 1
    assert world["reset"] == [] and "PP7" in world["result"]()["stopped"] and world["finished"]


def test_a_profiles_run_records_what_was_asked(world):
    assert world["go"](["PP2"]) == 0
    r = world["result"]()
    assert r["asked"] == ["PP2"] and world["reset"] == ["PP2"] and r["offered_profiles"] == ["PP1", "PP2", "PP3"]


# ---------------------------------------------------------------- the camera's list, every label accounted for

TRIAL = ["Off", "PP1", "PP2", "PРЗ", "PP4", "PP5", "PP6", "PP10", "PP11"]   # the first trial's reading: PP3 as Cyrillic
WALK = ["PP1", "PP2", "PP3", "PP4", "PP6", "PP10", "PP11", "PP5"]          # the a1 II's recorded Stills walk's order


@pytest.mark.parametrize("label,kind", [("Off", ("off", "Off")), ("Оff", ("off", "Off")), ("PРЗ", ("profile", "PP3")),
                                        ("PP 3", ("profile", "PP3")), ("PPl0", ("profile", "PP10")),
                                        ("PP1O", ("profile", "PP10")), ("User1: (No Import)", ("other", "User1")),
                                        ("P#?", ("unread", None)), ("PP", ("unread", None)), ("PP0", ("unread", None)),
                                        ("PP3a", ("unread", None)), ("PP 1 0", ("unread", None)),
                                        ("Gamma", ("unread", None))])
def test_every_label_is_off_a_profile_a_kind_left_alone_or_unread(label, kind):
    assert M.label_kind(label) == kind


def test_the_first_trials_list_yields_eight_profiles_and_no_difference_from_the_walk(world, capsys):
    assert M.profiles_of(TRIAL) == ["PP1", "PP2", "PP3", "PP4", "PP5", "PP6", "PP10", "PP11"]
    todo, have, note = M.choose(TRIAL, [], WALK)
    assert len(todo) == len(have) == 8 and "PP3" in todo and note == ""
    world["offer"](TRIAL)
    assert world["go"](recorded=WALK) == 0
    out = capsys.readouterr().out
    assert world["reset"] == todo and "not the recorded walk" not in out and "differs" not in out
    assert "the camera offered 8 profiles" in out and "8 reset" in out


@pytest.mark.parametrize("labels,said", [(["Off", "PP1", "P#?", "PP2"], "'P#?'"),
                                         (["Off", "PP1", "PP2", "PP1"], "PP1 more than once"),
                                         (["Off", "PP1", "PP2", "PРЗ", "PP3"], "PP3 more than once")])
def test_an_unread_label_or_a_profile_twice_stops_before_any_reset(world, labels, said):
    world["offer"](labels)
    assert world["go"]() == 1
    r = world["result"]()
    assert world["reset"] == [] and said in r["stopped"] and not r["finished"] and world["finished"]


def test_a_list_unlike_the_recorded_walk_stops_without_profiles_and_runs_with_them(world, capsys):
    world["offer"](["Off", "PP1", "PP2", "PP3", "PP7"])
    walk = ["PP1", "PP2", "PP3", "PP4"]
    assert world["go"](recorded=walk) == 1
    r = world["result"]()
    assert world["reset"] == [] and not r["finished"]
    for words in ("not the recorded walk's", "the walk's PP4 not on the camera", "the camera's PP7 not in the walk",
                  "Another body or firmware", "--profiles PP1,PP2,PP3,PP7"):
        assert words in r["stopped"], words
    capsys.readouterr()
    assert world["go"](["PP1", "PP2", "PP3", "PP7"], recorded=walk) == 0
    out = capsys.readouterr().out
    assert world["reset"] == ["PP1", "PP2", "PP3", "PP7"] and world["result"]()["finished"]
    assert "--profiles names the ones to reset" in out and "(--profiles PP1, PP2, PP3, PP7)" in out


def test_fewer_profiles_reset_than_the_camera_offered_is_not_finished(world, monkeypatch, capsys):
    monkeypatch.setattr(M, "choose", lambda offered, asked, recorded=None: (["PP1"], ["PP1", "PP2", "PP3"], ""))
    assert world["go"]() == 1
    r = world["result"]()
    assert world["reset"] == ["PP1"] and not r["finished"] and world["finished"]
    assert "the camera offered 3 profiles (PP1, PP2, PP3), 1 reset" in capsys.readouterr().out


class CarouselCam:
    """A made-up camera on the Picture Profile row: Right opens its carousel (`labels` as OCR reads them, the cursor on
    the first), Down moves on round it, Right on an option opens that option's settings, MENU closes the carousel.
    The vision model reads an option as `second[label]` (a reading, or a list of readings one a call), or, when
    `second` is None, is not reachable."""
    def __init__(self, labels, second=None):
        self.labels, self.second, self.state, self.i, self.n, self.pressed = list(labels), second, "menu", 0, 0, []
        self.logged, self.asked = [], 0
        self.run = SimpleNamespace(log=lambda kind, **f: self.logged.append((kind, f)))

    @property
    def frame(self):
        return SimpleNamespace(image=None, path=Path(f"{self.n:05d}_{self.state}.png"))

    def read(self):
        return SimpleNamespace(kind={"menu": "menu", "carousel": "dialog", "panel": "submenu"}[self.state])

    def answer(self, prompt):
        self.asked += 1
        if self.second is None:
            return None
        v = self.second.get(self.labels[self.i], self.labels[self.i])
        if isinstance(v, list):
            v = v.pop(0) if len(v) > 1 else v[0]
        return {"title": "Picture Profile", "selected": v}

    def press(self, key, **kw):
        self.pressed.append(key)
        self.n += 1
        if self.state == "menu" and key == "right":
            self.state = "carousel"
        elif self.state == "carousel" and key == "down":
            self.i = (self.i + 1) % len(self.labels)
        elif self.state == "carousel" and key == "right":
            self.state, self.entered = "panel", self.i
        elif self.state == "carousel" and key == "menu":
            self.state = "menu"

    def refresh(self, tag):
        self.n += 1


@pytest.fixture
def carousel(monkeypatch):
    import mode_switch
    import prove_run
    import runner
    cams = []

    def make(labels, second=None):
        cams.append(CarouselCam(labels, second))
        return cams[-1]
    monkeypatch.setattr(prove_run, "carousel_text", lambda cam: cam.labels[cam.i])
    monkeypatch.setattr(M, "ask_reader", lambda path, prompt: cams[-1].answer(prompt))
    monkeypatch.setattr(prove_run, "at_label", lambda cam, kind, label: cam.read().kind == kind and label == M.ROW)
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: None)
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(runner, "close_screen", lambda cam, link: None)
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    return make


def test_the_carousel_is_read_by_both_readers_and_the_second_for_an_unread_label(carousel):
    cam = carousel(["Off", "PP1", "PРЗ", "P#?", "PP10"], second={"PРЗ": "PP3", "P#?": "PP4"})
    said = []
    got = M.read_profiles(cam, None, None, None, said.append)
    assert got == ["Off", "PP1", "PРЗ", "PP4", "PP10"] and cam.pressed[-1] == "menu"
    assert M.choose(got, [], ["PP1", "PP3", "PP4", "PP10"])[0] == ["PP1", "PP3", "PP4", "PP10"]
    ways = {f["ocr"]: f["by"] for k, f in cam.logged if k == "pp_reset_option"}
    assert ways == {"Off": "both", "PP1": "both", "PРЗ": "both", "P#?": "second", "PP10": "both"}
    assert any("'P#?'" in s and "'PP4'" in s for s in said) and any("read by one reader only: PP4" in s for s in said)
    assert cam.asked == 6, "one call a frame read (the first option twice: once on the way round, once to end it)"


def test_the_carousel_without_the_vision_model_reads_as_before(carousel):
    cam = carousel(["Off", "PP1", "PРЗ", "PP10"], second=None)
    said = []
    assert M.read_profiles(cam, None, None, None, said.append) == ["Off", "PP1", "PРЗ", "PP10"]
    assert {f["by"] for k, f in cam.logged if k == "pp_reset_option"} == {"ocr"}
    from prove_run import Failed
    with pytest.raises(Failed, match=r"reads 'P#\?'"):
        M.read_profiles(carousel(["Off", "PP1", "P#?"], second=None), None, None, None, lambda m: None)


def test_two_readers_reading_two_names_stop_the_run_unless_a_fresh_frame_agrees(carousel):
    from prove_run import Failed
    cam = carousel(["Off", "PP1", "PP3", "PP10"], second={"PP3": "PP8"})
    with pytest.raises(Failed, match=r"reads 'PP3' to OCR and 'PP8' to the vision model, two different names on 3"):
        M.read_profiles(cam, None, None, None, lambda m: None)
    assert cam.pressed[0] == "right" and cam.pressed.count("right") == 1, "never into a panel"
    fixed = carousel(["Off", "PP1", "PP3", "PP10"], second={"PP3": ["PP8", "PP3"]})
    assert M.read_profiles(fixed, None, None, None, lambda m: None) == ["Off", "PP1", "PP3", "PP10"]
    with pytest.raises(Failed, match="two different names"):
        M.to_profile(carousel(["Off", "PP1", "PP3"], second={"PP1": "PP7"}), "PP3")


def test_a_label_neither_reader_reads_stops_the_run_naming_it_and_its_frame(carousel):
    from prove_run import Failed
    cam = carousel(["Off", "PP1", "P#?", "PP10"], second={"P#?": "a dial"})
    with pytest.raises(Failed, match=r"reads 'P#\?' \(\d{5}_carousel\.png\).*stops before any reset"):
        M.read_profiles(cam, None, None, None, lambda m: None)
    assert "enter" not in cam.pressed and cam.state != "panel"


@pytest.mark.parametrize("labels,second", [(["Off", "PP1", "PP2", "PРЗ", "PP4"], {}),
                                           (["Off", "PP1", "PP2", "PРЗ", "PP4"], None),
                                           (["Off", "PP1", "PP2", "P?3#", "PP4"], {"P?3#": "PP3"})])
def test_the_way_to_a_profile_finds_it_read_with_look_alikes(carousel, labels, second):
    cam = carousel(labels, second=second)
    M.to_profile(cam, "PP3")
    assert cam.state == "panel" and cam.entered == 3 and cam.pressed == ["right", "down", "down", "down", "right"]
    from prove_run import Failed
    with pytest.raises(Failed, match="never showed PP7"):
        M.to_profile(carousel(labels, second=second), "PP7")


# ---------------------------------------------------------------- make_sample --take / --from

PREFIX_MADE = "Made Profile PP"
TRIPLES = ((0x04e9, 0x04ff, 0x0515), (0x056d, 0x0583, 0x0599))   # the sample's records: in use, stills, movie
LIVE_MODE = {"key": "global:0x13bf", "modes": {"0": "Stills", "1": "Movie", "2": "S&Q", "3": "Time-lapse"}}
MODE_REC = 0x13bf
ALL = [f"PP{n}" for n in range(1, 12)]


def definition(tmp_path, in_sets=True, name="def.json", live_mode=True) -> Path:
    """A made-up family over six of the sample's records: two parameters kept in use, "(stills)" and "(movie)", each
    one element per profile PP1-PP11 (element n-1), as the a1 II's definition lays the Picture Profiles out."""
    settings = []
    for k, (live, st, mv) in enumerate(TRIPLES):
        for n in range(1, 12):
            g = f"{PREFIX_MADE}{n}"
            settings += [
                {"area": "global", "id": live, "index": n - 1, "key": f"global:0x{live:04x}[{n - 1}]", "group": g,
                 "name": f"Param {k}", "in_sets": in_sets},
                {"area": "global", "id": st, "index": n - 1, "key": f"global:0x{st:04x}[{n - 1}]", "group": g,
                 "name": f"Param {k} (stills)", "copy_for": ["Stills"], "copy_of": f"global:0x{live:04x}[{n - 1}]",
                 "in_sets": in_sets},
                {"area": "global", "id": mv, "index": n - 1, "key": f"global:0x{mv:04x}[{n - 1}]", "group": g,
                 "name": f"Param {k} (movie)", "copy_for": ["Movie", "S&Q", "Time-lapse"],
                 "copy_of": f"global:0x{live:04x}[{n - 1}]", "in_sets": in_sets}]
    doc = {"camera": {"families": [{"prefix": PREFIX_MADE, "title": "Made-up profiles"}],
                      "memory_sets": {"names": {"1": "Memory 1", "2": "Memory 2"}}},
           "settings": settings + [{"area": "global", "id": 0x0489, "group": "Other"}]}
    if live_mode:
        doc["camera"]["live_mode"] = LIVE_MODE
    f = tmp_path / name
    f.write_text(json.dumps(doc), encoding="utf-8")
    return f


def made_file(path: Path, elems: dict, mode: int | None = None, by=1, base=SAMPLE) -> Path:
    """The base with, for each record id, the first byte of each named profile's element moved by `by` (by may be a
    {rid: n} map); `mode`, the live mode record's value. Never a camera's own values."""
    cs = camset.read(base)
    out = {}
    for rid, profs in elems.items():
        r = cs.get(0, rid)
        raw = bytearray(r.raw)
        step = by.get(rid, 1) if isinstance(by, dict) else by
        for p in profs:
            i = (int(p[2:]) - 1) * r.size
            raw[i] = (raw[i] + step) % 256
        out[(0, rid)] = bytes(raw)
    if mode is not None:
        out[(0, MODE_REC)] = bytes([mode]) + cs.get(0, MODE_REC).raw[1:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(camset.with_values(cs, out))
    return path


FAMILY_IDS = {x for t in TRIPLES for x in t}
COPY_OF = {rid: c for t in TRIPLES for rid, c in zip(t, ("live", "stills", "movie"), strict=True)}
BOTH = {"title": "both", "question": "both"}


def diff_keys(a: Path, b: Path) -> list:
    return [c.key for c in camset.diff(camset.read(a), camset.read(b))]


def fam_keys(keys) -> list:
    return [k for k in keys if k.startswith("global:") and int(k.split(":0x")[1], 16) in FAMILY_IDS]


def copies_made(keys) -> dict:
    out = {"in_use": 0, "stills": 0, "movie": 0}
    for k in keys:
        out[{"live": "in_use", "stills": "stills", "movie": "movie"}[COPY_OF[int(k.split(":0x")[1], 16)]]] += 1
    return out


def result_of(tmp_path, name: str, dat_elems: dict, mode="Stills", reset=("PP1", "PP2"), offered=None, root=None,
              by=1, says=None, held=None, held_by=1, control=None, reset_keeps_control=False, record=None,
              control_profiles=None, **fields) -> Path:
    """A pp_reset.json in its own run folder with every download a real run makes, each the public sample with
    made-up changes: the start file (00001_before: the base, `held` moved by `held_by`, the live mode record set for a
    Movie run), the control's control-set (00002: the start file with the first profile's element of `control`'s
    records, default the first parameter's in-use record and this mode's copy, moved by 3), the first profile's reset
    download (the start file with dat_elems moved by `by`: the Reset wrote the control's records; on control-set
    instead when `reset_keeps_control`), the other profiles' and verify's as copies of it. Every list in it is computed
    from those files as pp_reset_run computes it. `root`: each file noted as the camera's download, in the order
    `record` gives (the roles' indexes; default the order made); `says`: the mode the result says, when not the one
    its downloads were saved in; `fields`: top-level fields over the computed ones."""
    d = tmp_path / name
    dat = d / "dat"
    start = made_file(dat / "00001_before.DAT", held or {}, 1 if mode == "Movie" else None, by=held_by)
    ctrl = control if control is not None else [TRIPLES[0][0], TRIPLES[0][1] if mode == "Stills" else TRIPLES[0][2]]
    ctl = made_file(dat / "00002_control-set.DAT", dict.fromkeys(ctrl, control_profiles or [reset[0]]), None, by=3,
                    base=start)
    files = [made_file(dat / f"00003_reset-{reset[0]}.DAT", dat_elems, None, by=by,
                       base=ctl if reset_keeps_control else start)]
    for i, prof in enumerate(reset[1:]):
        files.append(dat / f"{4 + i:05d}_reset-{prof}.DAT")
        files[-1].write_bytes(files[0].read_bytes())
    ver = dat / f"{3 + len(reset):05d}_verify.DAT"
    ver.write_bytes(files[-1].read_bytes())
    made = [start, ctl, *files, ver]
    if root is not None:
        for i in (record or range(len(made))):
            provenance.record(made[i], root)
    rel = lambda f: f.relative_to(d).as_posix()          # noqa: E731
    entries, prev = [], ctl
    for prof, f in zip(reset, files, strict=True):
        keys = diff_keys(prev, f)
        entries.append({"profile": prof, "download": rel(f), "changed": keys, "family_changed": fam_keys(keys),
                        "complete": True, "readers": dict(BOTH)})
        prev = f
    cch = fam_keys(diff_keys(start, ctl))
    ctl_cs, first_cs = camset.read(ctl), camset.read(files[0])
    wrote = [k for k in cch if el(ctl_cs, int(k.split(":0x")[1], 16), reset[0])
             != el(first_cs, int(k.split(":0x")[1], 16), reset[0])]          # as pp_reset_run: the profile's element
    result = {"finished": True, "peek": False, "verified": True, "family": PREFIX_MADE, "mode": says or mode,
              "asked": None, "need_both_readers": True, "offered_profiles": list(offered or reset), "start": rel(start),
              "control": {"profile": reset[0], "parameter": "Black Level", "download": rel(ctl), "changed": cch,
                          "copies_changed": copies_made(cch), "reset_download": rel(files[0]), "reset_wrote": wrote,
                          "copies_reset_wrote": copies_made(wrote), "ok": bool(cch) and wrote == cch},
              "last": rel(files[-1]), "profiles": entries,
              "verify": {"download": rel(ver), "family_changed": fam_keys(diff_keys(files[-1], ver)),
                         "others_changed": 0, "entered": dict.fromkeys(dict.fromkeys(reset), "confirmed")}}
    result.update(fields)
    f = d / "pp_reset.json"
    f.write_text(json.dumps(result), encoding="utf-8")
    return f


def last_of(result: Path) -> Path:
    """A result's last reset download."""
    return result.parent / json.loads(result.read_text(encoding="utf-8"))["last"]


def edit(result: Path, change):
    """The result file changed in place by `change(dict)` (a forged result)."""
    r = json.loads(result.read_text(encoding="utf-8"))
    change(r)
    result.write_text(json.dumps(r), encoding="utf-8")
    return result


@pytest.fixture
def root(tmp_path, monkeypatch):
    r = tmp_path / "runs"
    r.mkdir()
    monkeypatch.setattr(MS.paths, "run_root", lambda *a, **k: r)
    monkeypatch.setattr(MS.definitions, "menu_tree_file", lambda camera: tmp_path / "no_menu_tree.json")
    return r


def el(cs, rid, p):
    r = cs.get(0, rid)
    i = int(p[2:]) - 1
    return r.raw[i * r.size:(i + 1) * r.size]


def two_runs(tmp_path, root, movie_by=1, **kw):
    """A Stills run resetting PP1, PP2 (the in-use and stills records change) and a Movie run resetting them (the
    in-use and movie records change), each from the owner's file; both downloads also hold PP8's elements moved, a
    profile neither run reset (the a1 II's PP7-PP9: on no menu), which are never taken."""
    st_ids = [x for t in TRIPLES for x in t[:2]]
    mv_ids = [t[0] for t in TRIPLES] + [t[2] for t in TRIPLES]
    s = result_of(tmp_path, "run_s", dict.fromkeys(st_ids, ["PP1", "PP2", "PP8"]), "Stills", root=root)
    m = result_of(tmp_path, "run_m", dict.fromkeys(mv_ids, ["PP1", "PP2", "PP8"]), "Movie", root=root, by=movie_by,
                  **kw)
    return s, m


def run_ms(*args):
    return MS.main([str(SAMPLE), *map(str, args)])


def test_take_composes_each_record_from_its_modes_run_profile_by_profile(tmp_path, root, capsys):
    s, m = two_runs(tmp_path, root)
    out = tmp_path / "out.DAT"
    run_ms("--take", PREFIX_MADE, "--from", s, "--from", m, "--definition", definition(tmp_path), "--out", out)
    base, got = camset.read(SAMPLE), camset.read(out)
    sd, md = camset.read(last_of(s)), camset.read(last_of(m))
    for live, st, mv in TRIPLES:
        for p in ("PP1", "PP2"):
            assert el(got, live, p) == el(sd, live, p) != el(base, live, p)
            assert el(got, st, p) == el(sd, st, p) and el(got, mv, p) == el(md, mv, p) != el(base, mv, p)
        for p in ALL[2:]:
            assert el(got, live, p) == el(base, live, p) and el(got, mv, p) == el(base, mv, p), "not reset: base's"
        assert el(sd, live, "PP8") != el(base, live, "PP8") and el(md, mv, "PP8") != el(base, mv, "PP8")
    assert got.get(0, MODE_REC).raw == base.get(0, MODE_REC).raw, "the mode record is never taken"
    assert got.get(1, 0x04e9).raw == got.get(0, 0x04e9).raw == got.get(2, 0x04e9).raw, "in_sets: the copies follow"
    changed = {c.key for c in camset.diff(base, got, include_volatile=True)}
    assert {"global:0x0489", "set1:0x0489"}.isdisjoint(changed) and "set1:0x0515" in changed
    said = capsys.readouterr().out
    assert "left as the base sample has them" in said and "PP3, PP4, PP5, PP6, PP7, PP8, PP9, PP10, PP11" in said
    assert "held by every reset download as in its run's start file" in said and "Reset does not write): 0 of 6" in said
    assert "memory sets (1, 2): 12" in said
    assert not list(tmp_path.glob(".out.DAT.*")), "written through a temp file, none left"


def test_a_record_comes_only_from_its_own_modes_run(tmp_path, root):
    """The Movie run's downloads hold the stills records moved and the Stills run's the movie records moved, from
    their start files on, so neither run's resets changed them: the stills records come from the Stills run, the movie
    records from the Movie run (a later file never gives what its run's mode does not write)."""
    st_ids = [x for t in TRIPLES for x in t[:2]]
    mv_ids = [t[0] for t in TRIPLES] + [t[2] for t in TRIPLES]
    s = result_of(tmp_path, "run_s", dict.fromkeys(st_ids, ["PP1"]), root=root, reset=("PP1",),
                  held={0x0515: ["PP1"]}, held_by=9)
    m = result_of(tmp_path, "run_m", dict.fromkeys(mv_ids, ["PP1"]), "Movie", root=root, reset=("PP1",),
                  held={0x04ff: ["PP1"]}, held_by=7)
    out = tmp_path / "out.DAT"
    run_ms("--take", PREFIX_MADE, "--from", m, "--from", s, "--definition", definition(tmp_path), "--out", out)
    got, sd = camset.read(out), camset.read(last_of(s))
    md = camset.read(last_of(m))
    assert el(got, 0x04ff, "PP1") == el(sd, 0x04ff, "PP1") != el(md, 0x04ff, "PP1")
    assert el(got, 0x0515, "PP1") == el(md, 0x0515, "PP1") != el(sd, 0x0515, "PP1")


def test_two_runs_that_disagree_on_a_record_both_changed_stop(tmp_path, root):
    s, m = two_runs(tmp_path, root, movie_by=2)          # the in-use records reset to other bytes in Movie
    with pytest.raises(SystemExit, match="disagree"):
        run_ms("--take", PREFIX_MADE, "--from", s, "--from", m, "--definition", definition(tmp_path), "--dry-run")


@pytest.mark.parametrize("fields,said", [({"peek": True}, "a stopped run or a peek"),
                                         ({"finished": False}, "did not finish"),
                                         ({"verified": False, "verify": {"family_changed": ["global:0x04e9"]}},
                                          r"not verified \(entering the panels again changed global:0x04e9\)"),
                                         ({"verified": None}, "not verified"),
                                         ({"family": "Creative Look "}, "reset the family"),
                                         ({"offered_profiles": ["PP1", "PP2", "PP3"]}, "offered PP3, which its run did "
                                                                                       "not reset"),
                                         ({"says": "S&Q"}, "neither Stills nor Movie"),
                                         ({"says": "Movie"}, "saved in Stills mode")])
def test_only_a_finished_verified_whole_result_is_taken(tmp_path, root, fields, said):
    s = result_of(tmp_path, "run_s", {0x04e9: ["PP1"]}, root=root, **fields)
    m = result_of(tmp_path, "run_m", {0x0515: ["PP1"]}, "Movie", root=root)
    with pytest.raises(SystemExit, match=said):
        run_ms("--take", PREFIX_MADE, "--from", s, "--from", m, "--definition", definition(tmp_path), "--dry-run")


def test_take_names_a_family_and_from_a_result_never_ids_or_downloads(tmp_path, root):
    deff = definition(tmp_path)
    s, m = two_runs(tmp_path, root)
    for take in ("0x04e9", "global:0x04e9", "set1:0x04e9", "Gamma"):
        with pytest.raises(SystemExit, match="not a family of the definition"):
            run_ms("--take", take, "--from", s, "--from", m, "--definition", deff, "--dry-run")
    with pytest.raises(SystemExit, match="one family"):
        run_ms("--take", f"{PREFIX_MADE},Made-up profiles", "--from", s, "--definition", deff, "--dry-run")
    download = last_of(s)
    with pytest.raises(SystemExit, match="never a download"):
        run_ms("--take", PREFIX_MADE, "--from", download, "--definition", deff, "--dry-run")
    with pytest.raises(SystemExit, match="go together"):
        run_ms("--take", PREFIX_MADE, "--dry-run")
    with pytest.raises(SystemExit, match="no live_mode"):
        run_ms("--take", PREFIX_MADE, "--from", s, "--from", m, "--definition",
               definition(tmp_path, name="nolm.json", live_mode=False), "--dry-run")


def test_a_peek_result_is_refused(tmp_path, root):
    """pp_reset_run's own peek result (pp_reset_peek.json: finished, peek, no last download) is never taken."""
    d = tmp_path / "kit2_pp_reset_stills"
    d.mkdir()
    peek = d / M.PEEK_RESULT
    peek.write_text(json.dumps({"peek": True, "finished": True, "last": None, "profiles": [], "mode": "Stills",
                                "offered_profiles": ["PP1"], "family": PREFIX_MADE}), encoding="utf-8")
    with pytest.raises(SystemExit, match="a peek"):
        run_ms("--take", PREFIX_MADE, "--from", peek, "--definition", definition(tmp_path), "--dry-run")


def test_both_modes_are_needed_unless_one_run_shows_it_writes_every_copy(tmp_path, root, capsys):
    deff = definition(tmp_path)
    st_ids = [x for t in TRIPLES for x in t[:2]]
    s = result_of(tmp_path, "run_s", dict.fromkeys(st_ids, ["PP1", "PP2"]), root=root)
    with pytest.raises(SystemExit, match="a Movie run's result is needed too"):
        run_ms("--take", PREFIX_MADE, "--from", s, "--definition", deff, "--dry-run")
    s2 = result_of(tmp_path, "run_s2", dict.fromkeys(st_ids, ["PP1"]), root=root)
    with pytest.raises(SystemExit, match="both Stills runs"):
        run_ms("--take", PREFIX_MADE, "--from", s, "--from", s2, "--definition", deff, "--dry-run")
    every = [x for t in TRIPLES for x in t]
    alone = result_of(tmp_path, "run_all", dict.fromkeys(every, ["PP1", "PP2"]), root=root)
    out = tmp_path / "alone.DAT"
    run_ms("--take", PREFIX_MADE, "--from", alone, "--definition", deff, "--out", out)
    got, ad = camset.read(out), camset.read(last_of(alone))
    assert el(got, 0x0515, "PP1") == el(ad, 0x0515, "PP1") != el(camset.read(SAMPLE), 0x0515, "PP1")


def test_a_family_no_reset_changed_stops_unless_allowed(tmp_path, root, capsys):
    deff = definition(tmp_path)
    s = result_of(tmp_path, "run_s", {}, root=root)
    m = result_of(tmp_path, "run_m", {}, "Movie", root=root)
    with pytest.raises(SystemExit, match="no reset download holds any of the family's 6 records unlike"):
        run_ms("--take", PREFIX_MADE, "--from", s, "--from", m, "--definition", deff, "--dry-run")
    run_ms("--take", PREFIX_MADE, "--from", s, "--from", m, "--definition", deff, "--dry-run", "--allow-unchanged")
    said = capsys.readouterr().out
    assert "Reset does not write): 6 of 6: 0x04e9" in said
    assert "dry run" in said


def test_the_layout_and_the_provenance_are_checked(tmp_path, root):
    deff = definition(tmp_path)
    s, m = two_runs(tmp_path, root)
    foreign = result_of(tmp_path, "run_f", {0x04e9: ["PP1"]})                # never noted as a download
    with pytest.raises(SystemExit, match="not a camera download"):
        run_ms("--take", PREFIX_MADE, "--from", foreign, "--from", m, "--definition", deff, "--dry-run")
    cs = camset.read(SAMPLE)
    d = bytearray(cs.data)
    d[0x36] = (d[0x36] + 1) % 256                                     # another firmware's header
    other = last_of(s)
    other.write_bytes(cs.block.sealed(d))
    provenance.record(other, root)
    with pytest.raises(SystemExit, match="firmware"):
        run_ms("--take", PREFIX_MADE, "--from", s, "--from", m, "--definition", deff, "--dry-run")


def test_take_stops_when_a_memory_copy_is_unlike_its_live_record_in_the_base(tmp_path, root):
    cs = camset.read(SAMPLE)
    base = tmp_path / "base.DAT"
    r = cs.get(1, 0x04e9)
    base.write_bytes(camset.with_values(cs, {(1, 0x04e9): bytes([(r.raw[0] + 1) % 256]) + r.raw[1:]}))
    s, m = two_runs(tmp_path, root)
    with pytest.raises(SystemExit, match="what a reset leaves in a memory set is not known"):
        MS.main([str(base), "--take", PREFIX_MADE, "--from", str(s), "--from", str(m), "--definition",
                 str(definition(tmp_path)), "--dry-run"])


def test_a_dry_run_writes_nothing(tmp_path, root, capsys):
    s, m = two_runs(tmp_path, root)
    out = tmp_path / "dry.DAT"
    run_ms("--take", PREFIX_MADE, "--from", s, "--from", m, "--definition", definition(tmp_path), "--out", out,
           "--dry-run")
    assert not out.exists() and not list(tmp_path.glob(".dry.DAT*"))
    assert "took the 6 records" in capsys.readouterr().out


def test_the_sample_is_made_as_before_without_take(tmp_path):
    out = tmp_path / "plain.DAT"
    MS.main([str(SAMPLE), "--out", str(out)])
    assert camset.diff(camset.read(SAMPLE), camset.read(out)) == [], "the sample is its own sample"


def test_the_real_definition_lays_the_profiles_out_one_element_each():
    """The ILCE-1M2's definition: the family's 75 records (25 parameters in use, stills and movie), each 11 elements,
    PPn at element n-1, PP7-PP9 among them although no menu offers them."""
    doc = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    lay = MS.family_layout(doc, M.FAMILY)
    assert len(lay["records"]) == 75
    assert {r["copy"] for r in lay["records"].values()} == {"live", "stills", "movie"}
    assert all(r["profiles"] == {f"PP{n}": n - 1 for n in range(1, 12)} for r in lay["records"].values())
    base = camset.read(SAMPLE)
    assert all(base.get(0, rid).count == 11 for rid in lay["records"])
    assert MS.file_mode(doc, base) == "Stills"


# ---------------------------------------------------------------- the positive control, the readers, round 6

def test_a_control_that_changes_no_profile_parameter_stops_before_any_reset(world, capsys):
    world["control_changes"] = ["global:0x0053"]                  # a record outside the family only
    assert world["go"]() == 1
    r = world["result"]()
    assert world["control"] == ["PP1"] and world["reset"] == [] and not r["finished"] and r["restored"]
    assert r["control"]["ok"] is False and r["control"]["changed"] == [] and "changed none" in r["stopped"]
    assert world["finished"] == [world["downloads"][0]] and world["checked"], "the start file put back and checked"
    out = capsys.readouterr().out
    assert "NOT shown (the change moved none of the profiles' parameters)" in out and "finished:" not in out


def test_a_reset_that_leaves_a_control_record_as_the_control_set_it_stops(world, capsys):
    world["first_reset_changes"] = ["global:0x0053"]              # PP1's Reset did not write 0x04e9 back
    assert world["go"]() == 1
    r = world["result"]()
    assert world["reset"] == ["PP1"] and not r["finished"] and world["verified"] == [] and r["restored"]
    c = r["control"]
    assert c["ok"] is False and c["changed"] == ["global:0x04e9"] and c["reset_wrote"] == []
    assert c["copies_reset_wrote"] == {"in_use": 0, "stills": 0, "movie": 0}
    assert "left PP1's element of global:0x04e9 as the control set it" in r["stopped"]
    assert "its Reset wrote 0 of 1" in capsys.readouterr().out


def test_a_stop_during_the_control_restores(world, capsys):
    world["stop_in_control"] = True
    assert world["go"]() == 1
    r = world["result"]()
    assert world["reset"] == [] and "StopRequested" in r["stopped"] and not r["finished"]
    assert world["closed"] == 1 and world["finished"] == [world["downloads"][0]] and r["restored"]
    assert len(world["downloads"]) == 1, "no control-set download after a STOP"
    assert "the change was not made" in capsys.readouterr().out


def test_a_stop_file_before_the_control_stops_with_nothing_pressed(world):
    world["stop_after"] = 0
    assert world["go"]() == 1
    assert world["control"] == [] and world["reset"] == [] and "before the control" in world["result"]()["stopped"]


def test_the_control_profile_is_reset_first_and_must_be_one_reset(world):
    world["args"].control_profile = "PP2"
    assert world["go"]() == 0
    assert world["control"] == ["PP2"] and world["reset"] == ["PP2", "PP1", "PP3"]
    assert world["result"]()["control"]["reset_download"] == "dat/00002_reset-PP2.DAT"
    world["args"].control_profile = "PP3"
    assert world["go"](["PP1"]) == 1
    assert "not among the profiles this run resets" in world["result"]()["stopped"]


def test_no_control_only_for_a_trial_and_the_result_says_so(world, capsys):
    world["args"].no_control = True
    assert world["go"](["PP2"]) == 0
    r = world["result"]()
    assert world["control"] == [] and r["control"] is None and "never feed the sample" in r["control_skipped"]
    assert world["need_both"] is False and r["need_both_readers"] is False, "a --profiles trial: OCR alone may judge"
    assert "no control (--no-control): make_sample refuses this result" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="--no-control only for a --peek or a --profiles trial"):
        M.main(["--dry-run", "--allow", "Picture Profile Reset", "--no-control"])
    with pytest.raises(SystemExit, match="makes no control"):
        M.main(["--dry-run", "--allow", "Picture Profile Reset", "--peek", "--control-profile", "PP1"])


@pytest.mark.parametrize("asked,peek,flags,need", [((), False, {}, True), (("PP1",), False, {}, False),
                                                   ((), True, {}, False), ((), False, {"ocr_alone_ok": True}, False),
                                                   (("PP1",), False, {"need_both_readers": True}, True)])
def test_both_readers_are_needed_by_default_for_a_run_meant_for_the_sample(asked, peek, flags, need):
    a = SimpleNamespace(**{"peek": peek, "need_both_readers": False, "ocr_alone_ok": False, **flags})
    assert M.need_both_of(a, list(asked)) is need


def test_a_failure_in_the_verify_pass_is_not_finished(world, monkeypatch, capsys):
    from prove_run import Failed

    def verify_pass(c, link, cycle, model, done, r, say, need_both=False):
        raise Failed("the carousel never showed PP2 in the verify pass")
    monkeypatch.setattr(M, "verify_pass", verify_pass)
    assert world["go"]() == 1
    r = world["result"]()
    assert not r["finished"] and "verify pass" in r["stopped"] and r["restored"]
    out = capsys.readouterr().out
    assert "finished:" not in out and "stopped (Failed: the carousel never showed PP2" in out


def test_the_plan_names_the_controls_profile_and_parameter(tmp_path, monkeypatch, capsys):
    scan, tree = made_scan(tmp_path), made_tree(tmp_path)
    monkeypatch.setattr(M.paths, "run_root", lambda *a, **k: tmp_path / "TEST-CAM_fw9.99")
    monkeypatch.setattr(M, "scan_dir", lambda scan_arg, mode=None: scan)
    monkeypatch.setattr(M.definitions, "menu_tree_file", lambda camera: tree)
    assert M.main(["--dry-run", "--allow", "Picture Profile Reset", "--control-profile", "pp2"]) == 0
    out = capsys.readouterr().out
    assert "positive control first: PP2's Black Level" in out and "download control-set" in out
    assert "both readers needed" in out
    assert M.main(["--dry-run", "--allow", "Picture Profile Reset", "--profiles", "PP1", "--no-control"]) == 0
    out = capsys.readouterr().out
    assert "no positive control (--no-control)" in out and "OCR alone may judge" in out
    with pytest.raises(SystemExit, match="not among --profiles"):
        M.main(["--dry-run", "--allow", "Picture Profile Reset", "--profiles", "PP1", "--control-profile", "PP2"])


# the control's presses, on a made-up side list

class SideCam:
    """A made-up camera on a profile's settings with Black Level lit: Right opens its side list (`value` under the
    cursor, -15..+15, Down one lower and Up one higher, the lap wrapping at the ends), Enter chooses and closes it
    (`after`: "panel", or "notice" for a refused value), MENU closes it with no choice. `unread`: the readers give no
    number."""
    def __init__(self, value=0, after="panel", unread=False):
        self.state, self.value, self.after, self.unread, self.pressed, self.n = "panel", value, after, unread, [], 0
        self.chosen = None
        self.logged = []
        self.run = SimpleNamespace(log=lambda kind, **f: self.logged.append((kind, f)))

    @property
    def frame(self):
        return SimpleNamespace(image=None, path=Path(f"{self.n:05d}_{self.state}.png"))

    def read(self):
        return SimpleNamespace(kind={"panel": "submenu", "sidelist": "sidelist", "notice": "notice"}[self.state])

    def press(self, key, **kw):
        self.pressed.append(key)
        self.n += 1
        if self.state == "panel" and key == "right":
            self.state = "sidelist"
        elif self.state == "sidelist" and key in ("down", "up"):
            v = self.value + (1 if key == "up" else -1)
            self.value = 15 if v < -15 else -15 if v > 15 else v
        elif self.state == "sidelist" and key == "enter":
            self.chosen, self.state = self.value, self.after
        elif self.state in ("sidelist", "notice") and key == "menu":
            self.state = "panel"

    def refresh(self, tag):
        self.n += 1


@pytest.fixture
def side(monkeypatch):
    import mode_switch
    import prove_run
    import proving.nav
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: None)
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(M, "to_profile", lambda cam, profile: None)
    monkeypatch.setattr(M, "back_on_panel", lambda cam, profile, **kw: {"back": "confirmed", "by": "title",
                                                                       "frame": "x", "looks": []})
    monkeypatch.setattr(M, "row_reads_as", lambda cam, label: None)
    monkeypatch.setattr(proving.nav, "find_row", lambda cam, label: label == M.CONTROL_ROW)
    monkeypatch.setattr(prove_run, "at_label", lambda cam, kind, label: label == M.CONTROL_ROW)
    monkeypatch.setattr(M, "list_value", lambda cam, fresh=2: None if cam.unread or cam.state != "sidelist"
                        else float(cam.value))
    return SideCam


@pytest.mark.parametrize("value,keys,chosen", [(0, ["down"], -1), (-4, ["down"], -5), (7, ["up"], 8),
                                               (-15, ["down", "up", "up"], -14), (15, ["up", "down", "down"], 14)])
def test_the_control_moves_one_step_away_from_zero_and_chooses_it(side, value, keys, chosen):
    cam = side(value)
    said = []
    got = M.control_change(cam, None, None, "PP1", said.append)
    assert cam.pressed == ["right", *keys, "enter"] and cam.chosen == chosen and cam.state == "panel"
    assert got["moves"] == keys and got["chosen_frame"] and any("no value is said" in x for x in said)
    assert not any(str(chosen) in x.replace("PP1", "") for x in said), "the console names no value"


@pytest.mark.parametrize("kw,said", [({"unread": True}, "could not be read"), ({"after": "notice"}, "value refused")])
def test_a_control_that_cannot_be_made_backs_out_with_menu_and_stops(side, kw, said):
    from prove_run import Failed
    cam = side(0, **kw)
    with pytest.raises(Failed, match=said):
        M.control_change(cam, None, None, "PP1", lambda m: None)
    assert cam.pressed[-1] == "menu" and cam.state == "panel" and (cam.chosen is None or kw.get("after"))


def test_the_control_refuses_a_panel_that_is_not_the_profiles(side, monkeypatch):
    from prove_run import Failed
    monkeypatch.setattr(M, "back_on_panel", lambda cam, profile, **kw: {"back": "unconfirmed", "by": None,
                                                                       "frame": "x",
                                                                       "looks": [{"frame": "x", "kind": "submenu"}]})
    cam = side(0)
    with pytest.raises(Failed, match="not read as PP1's"):
        M.control_change(cam, None, None, "PP1", lambda m: None)
    assert cam.pressed == []


@pytest.mark.parametrize("ocr,bar,second,got", [("-3", "", "-3", -3.0), ("", "", "+4", 4.0), ("2", "", "", 2.0),
                                                ("", "-6", "", -6.0), ("2", "", "3", None), ("", "", "", None)])
def test_a_side_lists_number_is_taken_where_the_readers_agree_or_one_reads(monkeypatch, ocr, bar, second, got):
    import proving.screens
    import proving.sidelists
    cam = SideCam(0)
    cam.state = "sidelist"
    monkeypatch.setattr(cam, "read", lambda: SimpleNamespace(kind="sidelist", bar=(100, 120)))
    monkeypatch.setattr(proving.sidelists, "side_text", lambda c: ocr)
    monkeypatch.setattr(proving.sidelists, "bar_ocr", lambda c: bar)
    monkeypatch.setattr(proving.screens, "vlm_option", lambda c: second)
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    assert M.list_value(cam) == got
    logged = [f for k, f in cam.logged if k == "pp_reset_control_value"]
    assert all(set(f) == {"frame", "look", "ocr_read", "second_read", "agree", "taken"} for f in logged), "no value"
    assert len(logged) == (1 if got is not None else 3)


# the readers each guard was judged by

def test_each_profile_keeps_which_readers_judged_its_title_and_question(panel):
    cam = panel()                                               # the vision model not reachable
    assert M.reset_one(cam, None, None, "PP1", lambda m: None)["readers"] == {"title": "ocr", "question": "ocr"}
    both = panel(second="PP1", qsecond={"text": "Reset PP1 to the default setting?", "buttons": ["OK", "Cancel"]})
    assert M.reset_one(both, None, None, "PP1", lambda m: None)["readers"] == {"title": "both", "question": "both"}
    assert keys(both) == ["right", "enter"]


def test_with_both_readers_needed_an_unread_title_opens_no_reset(panel):
    from prove_run import Failed
    cam = panel(second=None)
    with pytest.raises(Failed, match="need-both-readers refuses") as e:
        M.reset_one(cam, None, None, "PP1", lambda m: None, need_both=True)
    assert cam.pressed == [] and "Reset not opened" in str(e.value)
    assert len(cam.judged("pp_reset_row_judged")) == M.ROW_FRESH + 1, "fresh frames looked at first"
    empty = panel(second="")
    with pytest.raises(Failed, match="need-both-readers refuses"):
        M.reset_one(empty, None, None, "PP1", lambda m: None, need_both=True)
    assert empty.pressed == []


@pytest.mark.parametrize("qsecond", [None, {"text": "", "buttons": []}, {"text": "Reset to the default setting?"}])
def test_with_both_readers_needed_an_unread_question_is_cancelled_with_menu(panel, qsecond):
    from prove_run import Failed
    cam = panel(second="PP1", qsecond=qsecond)
    with pytest.raises(Failed, match="question naming PP1"):
        M.reset_one(cam, None, None, "PP1", lambda m: None, need_both=True)
    assert keys(cam) == ["right", "menu"] and "enter" not in keys(cam)


@pytest.mark.parametrize("title,second", [("PP1", "Picture Profile PP10"), ("PP1", "PP1 PP2"), ("PP1", "PРЗ"),
                                          ("PP1 PP10", "PP1"), ("PP1", "Picture Profile PP1O")])
def test_a_title_naming_another_profile_anywhere_refuses(panel, title, second):
    from prove_run import Failed
    cam = panel(title=title, second=second)
    with pytest.raises(Failed, match="Reset not opened"):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert cam.pressed == []
    assert "naming" in safety.profile_reset_title(title, "PP1", second)[0]


@pytest.mark.parametrize("text", ["Reset PP1O to the default setting?", "Reset PРЗ to the default setting?",
                                  "Reset PP1 to the default setting? PPl2"])
def test_the_question_names_are_read_with_digit_look_alikes(panel, text):
    from prove_run import Failed
    assert any(n != "PP1" for n in M.question_names({"text": text}))
    cam = panel(second="PP1", qsecond={"text": text, "buttons": ["OK", "Cancel"]})
    with pytest.raises(Failed, match="vision model reads the question as naming"):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert "enter" not in keys(cam)
    assert safety.profile_reset_dialog(text + " OK Cancel", "PP1") != ""


def test_the_carousels_single_reader_labels_are_kept(carousel):
    cam = carousel(["Off", "PP1", "PРЗ", "P#?", "PP10"], second={"PРЗ": "PP3", "P#?": "PP4"})
    kept = {}
    M.read_profiles(cam, None, None, None, lambda m: None, kept=kept)
    assert kept == {"single": ["PP4"]}


# the three mutations a reviewer found surviving

def test_menu_refused_on_the_notice_then_another_screen_is_never_okd(panel, monkeypatch):
    """dismiss_complete judges the notice afresh before the OK fallback: a plain notice drive.py would OK ("This
    function is currently disabled.") stops the run with no Enter."""
    from prove_run import Failed
    cam = panel(after="complete", csecond=CSECOND, menu_refused=True)
    real = cam.refresh

    def refresh(tag):
        real(tag)
        if tag == "complete-notice":
            cam.state, cam.after_text, cam.menu_refused = "notice", "This function is currently disabled. OK", False
    cam.refresh = refresh
    import drive
    assert drive.press_refused("enter", "OK", "This function is currently disabled. OK", "notice") == "", \
        "drive.py alone would OK it"
    with pytest.raises(Failed, match="MENU refused on the completion notice, and then"):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert keys(cam).count("enter") == 1, "the question's OK alone"


def test_enter_goes_only_on_the_frame_the_question_was_judged_on(panel, monkeypatch):
    from prove_run import Failed
    real = M.to_ok

    def stale(cam, d, profile, need_both=False):
        got = real(cam, d, profile, need_both)
        return {**got, "frame": "00000_old.png"}
    monkeypatch.setattr(M, "to_ok", stale)
    cam = panel()
    with pytest.raises(Failed, match="not the frame on screen"):
        M.reset_one(cam, None, None, "PP1", lambda m: None)
    assert keys(cam) == ["right", "menu"]


# make_sample: a result is taken only as far as its own downloads bear it out

def take(tmp_path, *results, extra=()):
    return run_ms("--take", PREFIX_MADE, *[x for r in results for x in ("--from", r)], "--definition",
                  definition(tmp_path), "--dry-run", *extra)


def test_a_whole_checked_pair_of_results_is_taken(tmp_path, root, capsys):
    s, m = two_runs(tmp_path, root)
    take(tmp_path, s, m)
    assert "took the 6 records" in capsys.readouterr().out


@pytest.mark.parametrize("forge,said", [
    (lambda r: r.__setitem__("last", r["start"]), "is not its last profile's"),
    (lambda r: r.__setitem__("last", "/tmp/elsewhere/00009_reset-PP2.DAT"), "is not its last profile's"),
    (lambda r: r.update(asked=["PP1"], offered_profiles=["PP1"]), "limited to"),
    (lambda r: r.update(offered_profiles=["PP1"]), "which the camera's list it read did not offer"),
    (lambda r: r["profiles"][0].__setitem__("download", "/tmp/elsewhere/00003_reset-PP1.DAT"), "absolute path"),
    (lambda r: r.__setitem__("start", "../run_m/dat/00001_before.DAT"), "outside the result's own folder"),
    (lambda r: r.update(start=r["control"]["download"]), "is not a before download"),
    (lambda r: r["profiles"][0]["changed"].pop(), "which the result does not name"),
    (lambda r: r["profiles"][1]["changed"].append("global:0x0489"), "names global:0x0489, which its downloads do not"),
    (lambda r: r["profiles"][0]["family_changed"].pop(0), "PP1's family_changed"),
    (lambda r: r["control"]["changed"].pop(), "the control's changed"),
    (lambda r: r["control"]["reset_wrote"].pop(), "the control's reset_wrote"),
    (lambda r: r["control"]["copies_changed"].__setitem__("movie", 1), "the control's copies_changed"),
    (lambda r: r["verify"].__setitem__("family_changed", ["global:0x04e9"]), "the verify pass's family_changed"),
    (lambda r: r.__setitem__("control", None), "no positive control"),
    (lambda r: r["control"].__setitem__("profile", "PP2"), "not on the first profile reset"),
    (lambda r: r["control"].__setitem__("ok", False), "positive control does not hold"),
    (lambda r: r["profiles"][1].__setitem__("complete", False), "PP2 showed no completion notice"),
    (lambda r: r["profiles"][0]["readers"].__setitem__("question", "ocr"), "question before its Reset was not judged"),
    (lambda r: r["profiles"][1].pop("readers"), "title and the question before its Reset were not judged"),
    (lambda r: r["verify"].pop("entered"), "a run made before that check. Run it again on the camera"),
    (lambda r: r["verify"]["entered"].__setitem__("PP2", "unconfirmed"), "entered PP2 without confirming the panel"),
    (lambda r: r["verify"]["entered"].pop("PP1"), "entered PP1 without confirming the panel"),
    (lambda r: r.__setitem__("need_both_readers", False), "did not need both readers"),
    (lambda r: r["control"].__setitem__("reset_download", r["profiles"][1]["download"]),
     "control's reset_download .* is not its first profile's download"),
    (lambda r: r["control"].pop("reset_download"), "control's reset_download"),
    (lambda r: r["verify"].__setitem__("others_changed", 3), "the verify pass's others_changed"),
    (lambda r: r["verify"].__setitem__("others_changed", None), "the verify pass's others_changed")])
def test_a_forged_result_is_refused(tmp_path, root, forge, said):
    s, m = two_runs(tmp_path, root)
    edit(s, forge)
    with pytest.raises(SystemExit, match=said):
        take(tmp_path, s, m)


@pytest.mark.parametrize("download", [
    "/tmp/elsewhere/00003_reset-PP1.DAT", "\\elsewhere\\00003_reset-PP1.DAT", "C:\\Users\\you\\00003_reset-PP1.DAT",
    "C:/Users/you/00003_reset-PP1.DAT", "C:00003_reset-PP1.DAT", "\\\\server\\share\\00003_reset-PP1.DAT",
    "//server/share/00003_reset-PP1.DAT", "\\\\?\\C:\\elsewhere\\00003_reset-PP1.DAT"],
    ids=["posix", "backslash", "drive", "drive-slashes", "drive-relative", "unc", "unc-slashes", "long-path"])
def test_a_download_named_by_an_absolute_path_of_any_os_is_refused(tmp_path, root, download):
    """A result may be written on one OS and read on another: a download named by a path that is absolute on either
    (a POSIX one, a drive, a network share, a leading slash or backslash) is refused as one, on every OS, before its
    folder is looked at."""
    s, m = two_runs(tmp_path, root)
    edit(s, lambda r: r["profiles"][0].__setitem__("download", download))
    with pytest.raises(SystemExit, match="absolute path"):
        take(tmp_path, s, m)


def test_a_name_windows_reads_as_a_drive_is_refused_in_true_words(tmp_path, root):
    """"C:x" is a plain file name to macOS and Linux, though Windows reads it as on drive C: refused there too, with
    words that are true there."""
    s, m = two_runs(tmp_path, root)
    edit(s, lambda r: r["profiles"][0].__setitem__("download", "C:00003_reset-PP1.DAT"))
    with pytest.raises(SystemExit) as e:
        take(tmp_path, s, m)
    said = str(e.value)
    assert "is an absolute path" in said and "C:00003_reset-PP1.DAT" in said
    assert ("or a name Windows reads as a drive" in said) == (sys.platform != "win32")


@pytest.mark.parametrize("start", ["..\\run_m\\dat\\00001_before.DAT", "dat\\..\\..\\run_m\\dat\\00001_before.DAT"],
                         ids=["up", "down-and-up"])
def test_a_download_reached_by_backslashes_out_of_the_folder_is_refused(tmp_path, root, start):
    """`..` between backslashes leaves the folder on Windows; it is refused as outside on every OS (the kit writes
    a result's paths with forward slashes, camkit's in_run)."""
    s, m = two_runs(tmp_path, root)
    edit(s, lambda r: r.__setitem__("start", start))
    with pytest.raises(SystemExit, match="outside the result's own folder"):
        take(tmp_path, s, m)


def test_last_pointing_outside_the_folder_is_refused_even_when_it_is_the_last_profiles(tmp_path, root):
    s, m = two_runs(tmp_path, root)
    out = str(last_of(m))

    def forge(r):
        r["last"] = out
        r["profiles"][-1]["download"] = out
    edit(s, forge)
    with pytest.raises(SystemExit, match="absolute path"):
        take(tmp_path, s, m)


def test_a_profile_reset_twice_is_refused(tmp_path, root):
    s = result_of(tmp_path, "run_s", {0x04e9: ["PP1"], 0x04ff: ["PP1"]}, root=root, reset=("PP1", "PP2", "PP1"),
                  offered=("PP1", "PP2"))
    with pytest.raises(SystemExit, match="reset twice"):
        take(tmp_path, s, extra=("--allow-unchanged",))


@pytest.mark.parametrize("kw,said", [({"reset_keeps_control": True}, "left 2 of the 2 records the control changed"),
                                     ({"control": []}, "moved none of the family's records"), ({}, None),
                                     ({"record": [0, 2, 1, 3, 4]}, "not made in the order"),
                                     ({"record": [0, 2, 3, 4]}, "control: .*not a camera download")])
def test_a_result_whose_downloads_do_not_bear_it_out_is_refused(tmp_path, root, kw, said):
    """The resets move the second parameter's records; the control the first's (left as the control set them when
    `reset_keeps_control`)."""
    s = result_of(tmp_path, "run_s", {0x056d: ["PP1"], 0x0583: ["PP1"]}, root=root, **kw)
    m = result_of(tmp_path, "run_m", {0x056d: ["PP1"], 0x0599: ["PP1"]}, "Movie", root=root)
    if said is None:                                       # the same, borne out: taken
        take(tmp_path, s, m)
        return
    with pytest.raises(SystemExit, match=said):
        take(tmp_path, s, m)


def test_no_notice_is_taken_only_with_allow_no_notice(tmp_path, root, capsys):
    s, m = two_runs(tmp_path, root)
    edit(m, lambda r: [e.__setitem__("complete", False) for e in r["profiles"]])
    with pytest.raises(SystemExit, match="PP1, PP2 showed no completion notice"):
        take(tmp_path, s, m)
    take(tmp_path, s, m, extra=("--allow-no-notice",))
    assert "took the 6 records" in capsys.readouterr().out


def test_two_results_must_offer_the_same_profiles(tmp_path, root):
    s = result_of(tmp_path, "run_s", {0x04e9: ["PP1"], 0x04ff: ["PP1"]}, root=root)
    m = result_of(tmp_path, "run_m", {0x04e9: ["PP1"], 0x0515: ["PP1"]}, "Movie", root=root, reset=("PP1",))
    with pytest.raises(SystemExit, match="must reset the same profiles"):
        take(tmp_path, s, m)


def test_the_controls_copies_are_counted_by_the_definition(tmp_path, root):
    s, m = two_runs(tmp_path, root)
    rs, rm = (json.loads(x.read_text(encoding="utf-8"))["control"] for x in (s, m))
    assert rs["copies_changed"] == {"in_use": 1, "stills": 1, "movie": 0} == rs["copies_reset_wrote"]
    assert rm["copies_changed"] == {"in_use": 1, "stills": 0, "movie": 1}
    lay = MS.family_layout(json.loads(definition(tmp_path).read_text(encoding="utf-8")), PREFIX_MADE)
    cmap = {rid: r["copy"] for rid, r in lay["records"].items()}
    assert MS.copies_of(rs["changed"], cmap) == rs["copies_changed"] and MS.copies_of(["set1:0x04e9"], cmap) == \
        {"in_use": 0, "stills": 0, "movie": 0} and MS.copies_of([], None) is None


def test_the_control_stops_when_the_way_back_from_the_scales_end_shows_no_neighbour(side, monkeypatch):
    from prove_run import Failed
    seen = iter([-15.0, 15.0, None])                 # the end, the wrap, then nothing readable
    monkeypatch.setattr(M, "list_value", lambda cam, fresh=2: next(seen))
    cam = side(-15)
    with pytest.raises(Failed, match="did not show a number one step from the first after down, up, up"):
        M.control_change(cam, None, None, "PP1", lambda m: None)
    assert cam.pressed == ["right", "down", "up", "up", "menu"] and cam.chosen is None


def test_the_lift_needs_both_readers_on_the_press_frame_too(panel):
    """open_reset's predicate (LiveCamera.may_open_exact) judges the readers again on the frame the press is judged
    on: a reading the vision model no longer gives there lifts nothing."""
    cam = panel(second="PP1", qsecond={"text": "Reset PP1 to the default setting?", "buttons": ["OK"]})
    lifts = []
    real = cam.press

    def press(key, **kw):
        if cam.may_open_exact is not None:
            lifts.append((cam.frame, cam.may_open_exact))
        real(key, **kw)
    cam.press = press
    M.open_reset(cam, "PP1", need_both=True)
    (frame, exact), = lifts
    cam.state, cam.n = "panel", 0
    assert exact(frame, "Reset") is True
    cam._pp_second[(str(frame.path), "option")] = None             # the reading gone on that frame
    assert exact(frame, "Reset") is False


@pytest.mark.parametrize("kw", [{"reset_keeps_control": True}, {"control": []}])
def test_a_control_forged_to_hold_is_judged_by_its_downloads(tmp_path, root, kw):
    """"ok" true in the result, its lists as the downloads give them: the control's own downloads say it does not
    hold, and that is what counts."""
    s = result_of(tmp_path, "run_s", {0x056d: ["PP1"], 0x0583: ["PP1"]}, root=root, **kw)
    m = result_of(tmp_path, "run_m", {0x056d: ["PP1"], 0x0599: ["PP1"]}, "Movie", root=root)
    edit(s, lambda r: r["control"].__setitem__("ok", True))
    with pytest.raises(SystemExit, match="positive control does not hold"):
        take(tmp_path, s, m)


# fix round 7: the control element by element, one session's downloads, the verify pass's panels, the menu walk

def forge_control_holds(r):
    """The control's lists as a per-record check gave them: every changed record "written" back."""
    c = r["control"]
    c.update(reset_wrote=list(c["changed"]), copies_reset_wrote=dict(c["copies_changed"]), ok=True)


def test_a_reset_that_moves_another_profiles_element_is_not_the_controls_reset(tmp_path, root):
    """The reviewer's case (fix round 7): PP1's Reset download holds the control's records unlike control-set, but in
    PP2's element; PP1's element is where the control put it. Per record the control "held"; per element it does
    not."""
    s = result_of(tmp_path, "run_s", {TRIPLES[0][0]: ["PP2"], TRIPLES[0][1]: ["PP2"]}, root=root,
                  reset_keeps_control=True)
    m = result_of(tmp_path, "run_m", {0x056d: ["PP1"], 0x0599: ["PP1"]}, "Movie", root=root)
    edit(s, forge_control_holds)
    with pytest.raises(SystemExit, match="PP1's Reset left 2 of the 2 records the control changed as the control set "
                                         r"them \(PP1's element\)"):
        take(tmp_path, s, m)


@pytest.mark.parametrize("kw,said", [
    ({"control_profiles": ["PP1", "PP2"]}, "moved more than PP1's element of global:0x04e9"),
    ({"control": [TRIPLES[0][0]]}, "moved no stills record"),
    ({"control": [TRIPLES[0][1]]}, "moved no in-use record"),
    ({"control": [TRIPLES[0][2]]}, "moved no in-use and no stills record")])
def test_a_control_moves_one_profiles_element_in_use_and_in_its_modes_copy(tmp_path, root, kw, said):
    """Fix round 7: a control that moved another profile's element too, or missed the record in use or the copy of
    its run's mode, shows nothing about one profile's Reset; refused though its Reset wrote every record back."""
    s = result_of(tmp_path, "run_s", {0x056d: ["PP1"], 0x0583: ["PP1"]}, root=root, **kw)
    m = result_of(tmp_path, "run_m", {0x056d: ["PP1"], 0x0599: ["PP1"]}, "Movie", root=root)
    with pytest.raises(SystemExit, match=said):
        take(tmp_path, s, m)


def _session(tmp_path, root, name, extra):
    """A Stills result whose downloads are recorded with `extra` (role index -> made-up downloads in the same folder,
    each a copy of the start file under its own name) recorded before that role's download."""
    r = result_of(tmp_path, name, {0x04e9: ["PP1"], 0x04ff: ["PP1"]})
    made = [r.parent / x for x in ("dat/00001_before.DAT", "dat/00002_control-set.DAT", "dat/00003_reset-PP1.DAT",
                                   "dat/00004_reset-PP2.DAT", "dat/00005_verify.DAT")]
    for i, f in enumerate(made):
        for other in extra.get(i, ()):
            q = r.parent / "dat" / other
            q.write_bytes(made[0].read_bytes())
            provenance.record(q, root)
        provenance.record(f, root)
    return r


@pytest.mark.parametrize("extra,said", [
    ({1: ["00090_before.DAT"]}, "is not the session start nearest before its control-set"),
    ({2: ["00091_reset-PP1.DAT", "00092_after.DAT", "00093_before.DAT"]}, "not one session's"),
    ({4: ["00094_after.DAT"]}, "where 00005_verify.DAT belongs the manifest holds .*00094_after.DAT"),
    ({}, None), ({0: ["00095_after.DAT"]}, None)])
def test_two_sessions_downloads_in_one_folder_are_never_spliced(tmp_path, root, extra, said):
    """The reviewer's splice (fix round 7): one run folder holding two sessions' downloads; the result names the
    first session's start file and control-set and the second session's resets and verify, every list computed from
    those files, the manifest's order increasing. Only the consecutive entries of one session, from its own _before,
    are one result's; entries before the start file (an earlier session's _after) do not matter."""
    s = _session(tmp_path, root, "run_s", extra)
    m = result_of(tmp_path, "run_m", {0x04e9: ["PP1"], 0x0515: ["PP1"]}, "Movie", root=root)
    if said is None:
        take(tmp_path, s, m)
        return
    with pytest.raises(SystemExit, match=said):
        take(tmp_path, s, m)


@pytest.mark.parametrize("stills,said", [(["Off", "PP1", "PP2", "PP3"], "it leaves out PP3"),
                                         (["Off", "PP1"], "it names PP2, which the walk does not"),
                                         (["Off", "PP1", "PP2", "User1"], None)])
def test_the_offered_profiles_are_the_recorded_walks_when_the_tree_is_here(tmp_path, root, monkeypatch, stills, said):
    """Fix round 7: a result's offered_profiles is checked against the menu tree's list for its mode, as
    pp_reset_run.choose checks the camera's list; no tree, no check (the other tests)."""
    tree = tmp_path / "tree.json"
    tree.write_text(json.dumps({"tabs": [{"label": "Picture Profile", "options": stills}],
                                "modes": [{"mode": "Movie", "tabs": [{"label": "Picture Profile",
                                                                       "options": ["Off", "PP1", "PP2"]}]}]}),
                    encoding="utf-8")
    monkeypatch.setattr(MS.definitions, "menu_tree_file", lambda camera: tree)
    s, m = two_runs(tmp_path, root)
    if said is None:
        take(tmp_path, s, m)
        return
    with pytest.raises(SystemExit, match=said):
        take(tmp_path, s, m)


def test_the_run_checks_its_control_element_by_element(tmp_path, monkeypatch):
    """pp_reset_run's own control checks (fix round 7), over made files: the Reset moving PP2's element of the
    control's records writes none of them back for PP1; a control moving two profiles' elements moves "others"."""
    lay = MS.family_layout(json.loads(definition(tmp_path).read_text(encoding="utf-8")), PREFIX_MADE)
    monkeypatch.setattr(M, "family_layout_of", lambda camera: lay)
    r = result_of(tmp_path, "run_s", {TRIPLES[0][0]: ["PP2"], TRIPLES[0][1]: ["PP2"]}, reset_keeps_control=True)
    d = r.parent / "dat"
    start, ctl, first = d / "00001_before.DAT", d / "00002_control-set.DAT", d / "00003_reset-PP1.DAT"
    got = M.control_elements("X", start, ctl, "PP1", "Stills")
    assert got == {"changed": ["global:0x04e9", "global:0x04ff"], "others": [], "missing": []}
    assert M.control_wrote("X", ctl, first, "PP1", got["changed"]) == []
    good = result_of(tmp_path, "run_g", {TRIPLES[0][0]: ["PP3"]})
    gd = good.parent / "dat"
    assert M.control_wrote("X", gd / "00002_control-set.DAT", gd / "00003_reset-PP1.DAT", "PP1",
                           got["changed"]) == got["changed"]
    two = result_of(tmp_path, "run_t", {}, control_profiles=["PP1", "PP2"])
    td = two.parent / "dat"
    assert M.control_elements("X", td / "00001_before.DAT", td / "00002_control-set.DAT", "PP1", "Movie") == \
        {"changed": ["global:0x04e9", "global:0x04ff"], "others": ["global:0x04e9", "global:0x04ff"],
         "missing": ["movie"]}


@pytest.mark.parametrize("el,said", [({"changed": ["global:0x04e9"], "others": ["global:0x04e9"], "missing": []},
                                      "moved more than PP1's element of global:0x04e9"),
                                     ({"changed": ["global:0x04e9"], "others": [], "missing": ["stills"]},
                                      "moved no stills record")])
def test_a_control_that_moves_more_than_its_element_stops_before_any_reset(world, el, said):
    world["control_elements"] = el
    assert world["go"]() == 1
    r = world["result"]()
    assert world["reset"] == [] and r["control"]["ok"] is False and said in r["stopped"] and r["restored"]


def test_a_verify_pass_entry_not_confirmed_is_not_verified(world, capsys):
    """Fix round 7: the verify pass confirms each panel it enters as the profile's; one it cannot confirm leaves the
    run not verified (what that pass shows is not known to be that profile's)."""
    world["entered"] = {"PP2": "unconfirmed"}
    assert world["go"]() == 1
    r = world["result"]()
    assert r["finished"] and r["verified"] is False and r["verify"]["family_changed"] == []
    assert r["verify"]["entered"] == {"PP1": "confirmed", "PP2": "unconfirmed", "PP3": "confirmed"}
    assert "NOT verified (panel not confirmed: PP2): make_sample refuses this result" in capsys.readouterr().out


@pytest.mark.parametrize("second,need,want", [("PP1", True, "confirmed"), (None, True, "unconfirmed"),
                                              ("", True, "unconfirmed"), (None, False, "confirmed"),
                                              ("PP2", False, "unconfirmed")])
def test_the_verify_pass_confirms_each_panel_by_its_title(panel, monkeypatch, second, need, want):
    """verify_pass reads each panel's title as the reset path does (back_on_panel), both readers needed under
    --need-both-readers, and returns what each entry showed."""
    import mode_switch
    import runner
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: None)
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(M, "to_profile", lambda cam, profile: None)
    closed = []
    monkeypatch.setattr(runner, "close_screen", lambda cam, link: closed.append(cam.frame.path.name))
    cam = panel(title="PP1", second=second)
    run = SimpleNamespace(stop_requested=lambda: False)
    said = []
    assert M.verify_pass(cam, None, None, None, ["PP1"], run, said.append, need_both=need) == {"PP1": want}
    assert len(closed) == 1 and cam.judged("pp_reset_verify_entered")[0]["back"] == want
    assert keys(cam) == [], "the verify pass opens nothing on the panel"


def test_the_control_moves_no_row_whose_name_is_not_the_parameter(side, monkeypatch):
    """Fix round 7: find_row may land on the closest reading of the panel's rows and remember it, so at_label passes
    it; the control stops unless the lit row's own reading is Black Level."""
    from prove_run import Failed
    monkeypatch.setattr(M, "row_reads_as", lambda cam, label: "Black Gamma")
    cam = side(0)
    with pytest.raises(Failed, match="reads 'Black Gamma', not Black Level"):
        M.control_change(cam, None, None, "PP1", lambda m: None)
    assert cam.pressed == [] and cam.chosen is None


def test_the_row_is_read_as_its_own_name(monkeypatch):
    import proving.screens
    for text, want in (("Black Level", None), ("Black Gamma", "Black Gamma"), ("Black Leve1", None)):
        monkeypatch.setattr(proving.screens, "bar_text", lambda cam, t=text: t)
        got = M.row_reads_as(None, "Black Level")
        assert (got is None) == (want is None), (text, got)


def test_the_controls_panel_after_enter_is_confirmed_by_its_title(side, monkeypatch):
    """Fix round 7: after Enter on the side list the panel is checked to be the profile's by its title, not only to be
    a panel."""
    from prove_run import Failed
    looks = iter([{"back": "confirmed", "by": "title", "frame": "x", "looks": []},
                  {"back": "unconfirmed", "by": None, "frame": "y", "looks": [{"frame": "y", "kind": "submenu",
                                                                                "title": "PP2"}]}])
    monkeypatch.setattr(M, "back_on_panel", lambda cam, profile, **kw: next(looks))
    cam = side(0)
    with pytest.raises(Failed, match="after Enter on Black Level's side list the panel is not read as PP1's"):
        M.control_change(cam, None, None, "PP1", lambda m: None)
    assert cam.chosen == -1
