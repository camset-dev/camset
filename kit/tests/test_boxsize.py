"""The Custom focus box size prover (kit/provers/boxsize_run.py) off the camera: its plan, the guards on SET, on the
dials and on the editor's Reset, a box's records, the sizes read from made-up registrations (a turn that changes
nothing, ends off each other's ladder), the travel rule's prediction (kit/writer/frames.box_limits), and the size put
back by clicks or by the editor's Reset. Every definition, record and value here is made up but the a1 II's record
names and what its camera showed (kit2_boxsize_c1_probe_w3, kit2_boxsize_c1_width, 2026-11-17); nothing talks to a
camera."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
import boxsize_run as B  # noqa: E402
import framepos_run as F  # noqa: E402
from camkit import paths  # noqa: E402
from writer import frames, hand_tables  # noqa: E402

A1_DEFINITION = ROOT / "editor" / "definitions" / f"{paths.A1II}.json"
WORDS = ["Camera Set. Memory", "Focus Area's SET"]


def a1_doc() -> dict:
    return json.loads(A1_DEFINITION.read_text(encoding="utf-8"))


def a1_custom() -> dict:
    return hand_tables.load(paths.A1II, evidence=False).FRAME_TRAVEL["Custom"]


RULE = B.rule_of(a1_custom())


# ---------------------------------------------------------------- the plan and the records (no camera)

def test_a_boxs_records_come_from_the_hand_tables_and_the_definitions_names():
    """Custom 1's width and height (FRAME_TRAVEL's size records), its defaults (by the definition's names), the box in
    use and every record of its place (FRAME_TRAVEL's places, the box in use's among them), each as a registration
    writes it (slot 1, set1)."""
    recs = B.box_records(a1_doc(), "Custom 1", a1_custom())
    assert (recs["width"], recs["height"]) == ("set1:0x14b6", "set1:0x14b4")
    assert (recs["default_width"], recs["default_height"]) == ("set1:0x14c2", "set1:0x14c0")
    assert (recs["in_use_width"], recs["in_use_height"]) == ("set1:0x148a", "set1:0x1488")
    assert ("set1:0x139f", "set1:0x13a1") in recs["places"] and ("set1:0x1327", "set1:0x1329") in recs["places"]
    assert "Tracking: Custom 1" in recs["areas"]
    c3 = B.box_records(a1_doc(), "Custom 3", a1_custom())
    assert (c3["width"], c3["height"], c3["default_width"]) == ("set1:0x14be", "set1:0x14bc", "set1:0x14ca")
    with pytest.raises(SystemExit, match="Custom 4"):
        B.box_records(a1_doc(), "Custom 4", a1_custom())


def test_the_rule_is_the_definitions_own_box_limits():
    """The prediction is kit/writer/frames.box_limits on FRAME_TRAVEL's rule for the box (rule_of: the bounds, the grid
    and each Aspect Ratio's picture), never a copy: at 3:2 Sony's default sizes, the camera's own ends (width 28: X
    60-580, as kit2_boxsize_c1_width measured; 548: the one place 320), each end to the nearest whole number; another
    Aspect Ratio by its picture; none where the rule has no picture for the value or the box does not fit."""
    assert B.predicted(RULE["x"], 402, 0) == [247, 393] and B.predicted(RULE["y"], 182, 0) == [133, 347]
    assert B.predicted(RULE["x"], 168, 0) == [130, 510] and B.predicted(RULE["y"], 318, 0) == [201, 279]
    assert B.predicted(RULE["x"], 28, 0) == [60, 580] and B.predicted(RULE["x"], 548, 0) == [320, 320]
    assert B.predicted(RULE["y"], 182, 2) == list(frames.box_limits(RULE["y"], 182, 2))
    assert B.predicted(RULE["x"], 402, 9) is None and B.predicted(RULE["x"], 600, 0) is None


def test_a_travel_check_says_match_or_the_difference_for_each_record_of_the_boxs_place():
    """Each measured record of the box's place (FRAME_TRAVEL's X and Y records) against the rule at the size the base
    registration read: a match, or each limit's difference; a measured record that is no place of the box is left out."""
    recs = B.box_records(a1_doc(), "Custom 1", a1_custom())
    edges = [{"key": "set1:0x139f", "low": 247, "high": 393}, {"key": "set1:0x13a1", "low": 135, "high": 347},
             {"key": "set1:0x9999", "low": 1, "high": 2}]
    got = {c["key"]: c for c in B.travel_check(edges, recs, RULE, {"width": 402, "height": 182}, 0)}
    assert set(got) == {"set1:0x139f", "set1:0x13a1"}
    assert got["set1:0x139f"] == {"key": "set1:0x139f", "axis": "x", "measured": [247, 393], "predicted": [247, 393],
                                  "match": True, "diff": [0, 0]}
    assert got["set1:0x13a1"]["match"] is False and got["set1:0x13a1"]["diff"] == [2, 0]
    assert B.travel_words(got["set1:0x13a1"]) == "measured 135 to 347, the rule 133 to 347: low +2"


def test_the_step_pattern_is_read_from_single_clicks_uneven_or_even():
    """The steps between registrations one click apart, and the pattern said: even ones as one step (the a1 II: 16 a
    click for the width, 12 for the height), uneven ones as they repeat, a click that changed nothing as 0."""
    assert B.steps_of([402, 418, 434, 450]) == [16, 16, 16]
    assert B.pattern_words([16, 16, 16]) == "16, 16, 16 (16 a click)"
    assert B.pattern_words([5, 5, 6, 5, 5, 6]) == "5, 5, 6, 5, 5, 6 (16 every 3 clicks)"
    assert B.pattern_words([-6, -5, -5]) == "-6, -5, -5 (-16 every 3 clicks)"
    assert B.pattern_words([16, 0]) == "16, 0 (a click changed nothing)"


@pytest.fixture
def listed(monkeypatch):
    monkeypatch.setattr(B, "read_definition", lambda: a1_doc())
    monkeypatch.setattr(B, "custom_table", lambda: a1_custom())
    monkeypatch.setattr(B, "prove", lambda *a, **k: pytest.fail("connected"))


def test_list_prints_the_plan_and_sends_nothing(capsys, listed):
    """--list: the box, its records, the context's setup, each dial's walk and the travel sizes, how long, and how the
    size comes back (counted clicks, the editor's Reset under its word); nothing connects."""
    assert B.main(["--box", "Custom 1", "--list"]) == 0
    out = capsys.readouterr().out
    assert "Custom 1: width set1:0x14b6 (rear_l), height set1:0x14b4 (front)" in out
    assert "edges measured at the start size, at each dial's smallest and largest, and at one odd size" in out
    assert "kit/writer/frames.box_limits" in out
    assert "put back by counted clicks" in out and "--put-back" in out and "--allow 'Custom box Reset'" in out
    assert B.main(["--box", "Custom 1", "--allow", "Custom box Reset", "--list"]) == 0
    assert "the editor's Reset (the trash button) where the clicks cannot" in capsys.readouterr().out
    assert B.main(["--box", "Custom 1", "--probe", "rear_l", "--list"]) == 0
    out = capsys.readouterr().out
    assert "probe: rear_l 3 single clicks up, each registered, then 3 down" in out and "edges" not in out


def put_back_source(tmp_path, monkeypatch, default=True, edges=True) -> str:
    """A run of kit2_boxsize_c1_width's shape where paths.run_root finds it: its boxsize.jsonl's start line (Custom 1,
    402 x 182, the defaults'; with `default` False a size of the owner's, 418 wide) and the finish it left (388 wide),
    and its edges at the start size (`edges`); its name."""
    from camkit import jsonl
    monkeypatch.setattr(B.paths, "run_root", lambda *a, **k: tmp_path)
    run = tmp_path / "kit2_boxsize_c1_width"
    run.mkdir()
    size = {"width": 402 if default else 418, "height": 182, "default_width": 402, "default_height": 182,
            "in_use_width": 402 if default else 418, "in_use_height": 182}
    place = {"set1:0x139f": 320, "set1:0x13a1": 240, "set1:0x1327": 320, "set1:0x1329": 240}
    context = B.context_of("3:2")
    jsonl.append(run / "boxsize.jsonl", {"what": "start", "box": "Custom 1", "file": "00010_size-001-start-custom-1.DAT",
                                         "size": size, "place": place, "default": default, "context": context})
    jsonl.append(run / "boxsize.jsonl", {"what": "finish", "box": "Custom 1", "size": dict(size, width=388),
                                         "place": place, "context": context})
    if edges:
        jsonl.append(run / "edges.jsonl", {"area": "Custom 1", "code": 109, "at": "start", "size": size,
                                           "files": {"base": "00012_edge-base-custom-1.DAT"},
                                           "values": {"base": {"set1:0x139f": 320, "set1:0x13a1": 240}},
                                           "edges": [], "back": {"same": True}, "context": context})
    return run.name


def allowed(*words) -> list:
    return [x for w in words for x in ("--allow", w)]


def test_list_prints_the_plan_and_reaches_no_camera_in_any_mode(no_camera, listed, tmp_path, monkeypatch, capsys):
    """--list prints the plan and sends nothing, whatever else is given: a walk, a probe, --tracking, --put-back (for
    a run of kit2_boxsize_c1_width's shape), with no word, the owner's two, or all three: no link, no session, no eyes
    and no run folder (the no_camera guard)."""
    run = put_back_source(tmp_path, monkeypatch)
    for argv in (["--box", "Custom 1"], ["--box", "Custom 1", "--probe", "rear_l"], ["--box", "Custom 2", "--tracking"],
                 ["--put-back", run]):
        for words in ((), WORDS, (*WORDS, "Custom box Reset")):
            assert B.main(argv + allowed(*words) + ["--list"]) == 0, (argv, words)
            assert capsys.readouterr().out, (argv, words)
    assert not (tmp_path / "kit2_boxsize_putback").exists() and not (tmp_path / "kit2_boxsize").exists()


def test_the_put_back_plan_says_what_it_would_do_for_the_runs_box(no_camera, listed, tmp_path, monkeypatch, capsys):
    """--put-back RUN --list: for RUN's box, the start size it would return to (by value where it is the defaults'),
    how: registered where it is now, then counted clicks, then the editor's Reset under --allow "Custom box Reset" (given
    or not, said), its place from RUN's edges at the start size; an owner's start size by clicks alone, never said;
    a run that measured no edges at the start size has its place checked, not brought back."""
    run = put_back_source(tmp_path, monkeypatch)
    assert B.main(["--put-back", run, "--list"]) == 0
    out = capsys.readouterr().out
    assert "Custom 1: back to the start of kit2_boxsize_c1_width, width 402, height 182 (the default records')" in out
    assert "registered where it is now; then by counted clicks, each landing registered" in out
    assert "where no click lands on it, the editor's Reset only with --allow 'Custom box Reset' (not given)" in out
    assert "its place: back to the start's from kit2_boxsize_c1_width's edges at the start size" in out
    assert "set through the menu first: Switch V/H AF Area = Off; Circ. of Focus Point = Does Not Circulate" in out
    assert B.main(["--put-back", run, *allowed(*WORDS, "Custom box Reset"), "--list"]) == 0
    assert "where no click lands on it, the editor's Reset (the trash button), --allow 'Custom box Reset' given" in \
        capsys.readouterr().out


def test_the_put_back_plan_for_an_owners_start_or_a_run_without_edges(no_camera, listed, tmp_path, monkeypatch, capsys):
    """An owner's start size: said as the owner's, never by value, brought back by clicks alone (a Reset would not give
    it); a run with no edges at its start size: the place checked at the finish, not brought back; a run with no start
    line: nothing to put back to, before anything connects."""
    run = put_back_source(tmp_path, monkeypatch, default=False, edges=False)
    assert B.main(["--put-back", run, *allowed(*WORDS, "Custom box Reset"), "--list"]) == 0
    out = capsys.readouterr().out
    assert "a size that is not the defaults' (the owner's, not said)" in out and "418" not in out
    assert "by counted clicks alone: an owner's size is never reset" in out
    assert "measured no edges at the start size: its place is checked at the finish, not brought back" in out
    (tmp_path / run / "boxsize.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(SystemExit, match="holds no start line"):
        B.main(["--put-back", run, "--list"])


def test_a_camera_run_needs_the_owners_two_words_and_the_reset_its_own(listed):
    """Registering a memory slot and opening the box's editor with SET (C4) are the owner's words, given per run:
    without both, nothing connects. The editor's Reset is a third word, never needed and never implied; any other
    --allow is refused."""
    for allow in ([], ["--allow", "Camera Set. Memory"], ["--allow", "Focus Area's SET"],
                  ["--allow", "Custom box Reset"]):
        with pytest.raises(SystemExit, match="Camera Set. Memory.*Focus Area's SET"):
            B.main(["--box", "Custom 1", *allow])
    with pytest.raises(SystemExit, match="allowed nothing but"):
        B.main(["--box", "Custom 1", "--allow", "Camera Set. Memory", "--allow", "Focus Area's SET", "--allow",
                "Format"])
    assert B.reset_allowed(["Custom box Reset"]) and not B.reset_allowed(WORDS)
    with pytest.raises(SystemExit, match="Custom 1, Custom 2 or Custom 3"):
        B.main(["--box", "Spot: M", "--list"])


def test_the_aspect_ratio_is_read_from_the_start_download_by_code_and_label():
    """The context names the Aspect Ratio the start download holds, by the definition's label; the rule takes its
    code."""
    index = {s["key"]: s for s in a1_doc()["settings"]}
    assert B.aspect_of(index, Download({"global:0x01fe": 0})) == (0, "3:2")
    assert B.aspect_of(index, Download({"global:0x01fe": 2})) == (2, "16:9")
    assert B.aspect_of(index, Download({})) == (None, None)
    assert B.context_of("3:2") == "Switch V/H AF Area Off, camera level, AF Frame Move Amt Standard, Aspect Ratio 3:2"


# ---------------------------------------------------------------- the guards on SET, the dials and the Reset

EDITOR = "Custom 1 Reset MENU Cancel OK"
CHOOSER = "Focus Area Custom 1 SET C1 C2 C3 MENU Cancel OK"


def test_set_goes_only_on_focus_areas_chooser_with_the_box_lit():
    assert B.chooser_refused("dialog", CHOOSER, "Custom 1", "Custom 1") == ""
    assert "Custom 2" in B.chooser_refused("dialog", CHOOSER, "Custom 2", "Custom 1")
    assert B.chooser_refused("dialog", CHOOSER.replace("SET ", ""), "Custom 1", "Custom 1")
    assert B.chooser_refused("shooting", CHOOSER, "Custom 1", "Custom 1")
    assert B.chooser_refused("dialog", "Drive Mode Custom 1 SET", "Custom 1", "Custom 1")


def test_a_dial_goes_only_on_the_boxs_own_editor():
    assert B.editor_refused("unknown", EDITOR, "Custom 1") == ""
    assert "Custom 1's size editor" in B.editor_refused("unknown", EDITOR.replace("1", "2", 1), "Custom 1")
    for kind in ("shooting", "playback", "notice", "menu"):
        assert B.editor_refused(kind, EDITOR, "Custom 1"), kind
    assert B.editor_refused("dialog", CHOOSER, "Custom 1")
    assert B.editor_refused("unknown", "Custom 1 MENU Cancel OK", "Custom 1")      # no Reset: not the editor


class EditorCam:
    """A made-up camera for the dial guard: its screen as `screens` gives it in turn on each read, every dial turned
    recorded with the screen it went on."""
    def __init__(self, screens):
        self.screens, self.dialled, self.n = list(screens), [], 0
        self.now = self.screens[0]

    @property
    def frame(self):
        return SimpleNamespace(path=Path(f"{self.n:05d}_x.png"), image=None)

    def read(self):
        return SimpleNamespace(kind=self.now[0])

    def refresh(self, tag):
        self.n += 1
        if len(self.screens) > 1:
            self.screens.pop(0)
        self.now = self.screens[0]
        return self.read()

    def dial(self, name, steps, on_shooting=frozenset()):
        assert not on_shooting
        self.dialled.append((name, steps, self.now[0]))
        return self.refresh("dial")


@pytest.fixture
def texts(monkeypatch):
    import camkit.live
    monkeypatch.setattr(camkit.live, "text_of", lambda cam: cam.now[1])
    monkeypatch.setattr(B.time, "sleep", lambda s: None)


def test_a_dial_is_turned_one_click_a_command_each_on_the_editor_just_read(texts):
    """turn: one dial command a click, a step of one (the a1 II moves the box one click a command, whatever its steps:
    kit2_boxsize_c1_width, "dial rear_l -10" moved 16 units), each only once the screen read just before it is the
    box's own editor; on the shooting screen, another box's editor or any other screen nothing is turned."""
    from prove_run import Failed
    cam = EditorCam([("unknown", EDITOR)])
    B.turn(cam, "Custom 1", "rear_l", -25)
    assert cam.dialled == [("rear_l", -1, "unknown")] * 25
    for screen in (("shooting", "F5.6 ISO AUTO"), ("unknown", EDITOR.replace("1", "3", 1)), ("dialog", CHOOSER)):
        cam = EditorCam([screen])
        with pytest.raises(Failed, match="no dial"):
            B.turn(cam, "Custom 1", "front", 3)
        assert cam.dialled == [], screen
    cam = EditorCam([("unknown", EDITOR), ("unknown", EDITOR), ("unknown", EDITOR), ("shooting", "F5.6")])
    with pytest.raises(Failed, match="no dial"):
        B.turn(cam, "Custom 1", "front", 5)               # the editor gone after the second click: no more turned
    assert cam.dialled == [("front", 1, "unknown")] * 2
    with pytest.raises(Failed, match="wheel"):
        B.turn(EditorCam([("unknown", EDITOR)]), "Custom 1", "wheel", 1)


class ChooserCam:
    """A made-up camera for SET, OK and Reset: its screen (kind, text) and the lit axis value `lit`; C4 opens what
    `after` gives, Enter leaves for what `ok` gives, MENU for the shooting screen; each press kept with the consent it
    carried."""
    def __init__(self, kind, text, lit=0, after=("unknown", EDITOR), ok=("shooting", "F5.6 ISO AUTO")):
        self.now, self.lit, self.after, self.ok, self.pressed, self.answer_once, self.n = (kind, text), lit, after, ok, \
            [], None, 0
        self.run = SimpleNamespace(log=lambda kind, **f: None)

    @property
    def frame(self):
        return SimpleNamespace(path=Path(f"{self.n:05d}_x.png"), image=None)

    def read(self):
        return SimpleNamespace(kind=self.now[0])

    def refresh(self, tag):
        return self.read()

    def press(self, key, **kw):
        self.pressed.append((key, kw, self.answer_once))
        self.answer_once, self.n = None, self.n + 1
        self.now = {"c4": self.after, "enter": self.ok}.get(key, ("shooting", ""))


@pytest.fixture
def kept(monkeypatch):
    import afreg_run
    monkeypatch.setattr(afreg_run, "kept_notice", lambda cam, step, words=None, kind="": cam.frame.path.name)


def test_set_is_pressed_only_on_focus_areas_chooser_with_the_box_lit(texts, kept, monkeypatch):
    """open_editor: SET (C4, allowed by name) only once the chooser reads as Focus Area's with the wanted box lit (the
    axis value read again) and SET on its trash button; and what it opens must read as that box's own editor."""
    import afreg_run
    import prove_run
    from prove_run import Failed
    monkeypatch.setattr(afreg_run, "choose_level", lambda *a: {})
    monkeypatch.setattr(prove_run, "axis_reading", lambda cam, vals: (cam.lit, {}))

    def sw(cam):
        return SimpleNamespace(cam=cam, box="Custom 1", r=(5, "Custom 1", 0), cycle=None, model=None, labels=[],
                               axes={"Custom 1": {"values": ["Custom 1", "Custom 2", "Custom 3"]}})
    cam = ChooserCam("dialog", CHOOSER)
    B.open_editor(sw(cam))
    assert [(k, kw) for k, kw, _ in cam.pressed] == [("c4", {"allow": frozenset({"c4"})})]
    for cam, why in ((ChooserCam("dialog", CHOOSER, lit=1), "Custom 2"), (ChooserCam("shooting", "F5.6"), "shooting"),
                     (ChooserCam("dialog", CHOOSER.replace("SET ", "")), "SET")):
        with pytest.raises(Failed, match=f"SET not pressed.*{why}"):
            B.open_editor(sw(cam))
        assert cam.pressed == [], why
    cam = ChooserCam("dialog", CHOOSER, after=("unknown", "Custom 2 Reset MENU Cancel OK"))
    with pytest.raises(Failed, match="opened no editor of its own"):
        B.open_editor(sw(cam))


def test_the_editors_ok_carries_its_consent_and_must_land_on_the_shooting_screen(texts, kept):
    """keep_size: OK only on the box's editor read just before, carrying the camera's consent for that one press
    (camkit.live.BoxEditor, named for the box); a notice after it is kept in the run's events, left with MENU, and fails
    the size; anything but the shooting screen after it fails it too."""
    from camkit import live
    from prove_run import Failed
    cam = ChooserCam("unknown", EDITOR)
    B.keep_size(cam, "Custom 1")
    ((key, kw, consent),) = cam.pressed
    assert key == "enter" and isinstance(consent, live.BoxEditor) and consent.box == "Custom 1"
    assert "Focus Area's SET" in consent.name
    cam = ChooserCam("dialog", CHOOSER)
    with pytest.raises(Failed, match="no OK"):
        B.keep_size(cam, "Custom 1")
    assert cam.pressed == []
    cam = ChooserCam("unknown", EDITOR, ok=("notice", "Made-up notice"))
    with pytest.raises(Failed, match="a notice after OK"):
        B.keep_size(cam, "Custom 1")
    assert [k for k, _, _ in cam.pressed] == ["enter", "menu"]
    with pytest.raises(Failed, match="not the shooting screen"):
        B.keep_size(ChooserCam("unknown", EDITOR, ok=("menu", "Shooting Mode")), "Custom 1")


def test_the_editors_reset_goes_only_on_that_editor_and_must_leave_it_open(texts, kept):
    """press_reset: C4, allowed by name, only on the box's editor read just before, carrying the camera's Reset consent
    (camkit.live.BoxReset, named for the box and the owner's word of 2026-11-17); the screen after it must read as the
    same editor (kit2_freesize 00563 -> 00564: the editor, the box at its default size); a question or any other screen
    stops it there, nothing pressed after the C4, what showed kept in the run's events."""
    from camkit import live
    from prove_run import Failed
    cam = ChooserCam("unknown", EDITOR, after=("unknown", EDITOR))
    B.press_reset(cam, "Custom 1")
    ((key, kw, consent),) = cam.pressed
    assert key == "c4" and kw == {"allow": frozenset({"c4"})} and isinstance(consent, live.BoxReset)
    assert consent.box == "Custom 1" and "Custom box Reset" in consent.name and "2026-11-17" in consent.name
    for before in (("dialog", CHOOSER), ("shooting", "F5.6"), ("unknown", EDITOR.replace("1", "2", 1))):
        cam = ChooserCam(*before)
        with pytest.raises(Failed, match="no Reset"):
            B.press_reset(cam, "Custom 1")
        assert cam.pressed == [], before
    for after in (("dialog", "Reset to the default size? OK Cancel"), ("notice", "Made-up notice"),
                  ("shooting", "F5.6")):
        cam = ChooserCam("unknown", EDITOR, after=after)
        with pytest.raises(Failed, match="not the editor.*nothing answered"):
            B.press_reset(cam, "Custom 1")
        assert [k for k, _, _ in cam.pressed] == ["c4"], after


def test_a_start_download_whose_aspect_ratio_the_rule_has_no_picture_for_stops_before_any_press(monkeypatch, tmp_path):
    """The rule covers the Aspect Ratios FRAME_TRAVEL gives a picture for (3:2, 4:3, 16:9, 1:1 on the a1 II): one it
    has none for, or a download that holds none, stops the run before its setup and its first press, saying what it
    read; 16:9 goes on to the setup."""
    from camkit import camset
    from prove_run import Failed

    class SetUp(Exception):
        pass
    monkeypatch.setattr(F, "slot_filled", lambda cs: True)
    monkeypatch.setattr(F, "prepare", lambda *a, **k: (_ for _ in ()).throw(SetUp()))
    index = {s["key"]: s for s in a1_doc()["settings"]}
    recs = B.box_records(a1_doc(), "Custom 1", a1_custom())
    s = SimpleNamespace(cam=SimpleNamespace(press=lambda *a, **k: pytest.fail("pressed")), link=None,
                        start=tmp_path / "00001_before.DAT")
    args = (s, SimpleNamespace(probe="rear_l", tracking=False), SimpleNamespace(dir=tmp_path), None, None, None, [], {},
            index, recs, RULE, {"label": "Custom 1", "code": 109}, (5, "Custom 1", 0), None, {})
    for held, said in (({"global:0x01fe": 9}, "no picture for it"), ({}, "Aspect Ratio reads nothing")):
        monkeypatch.setattr(camset, "read", lambda path, held=held: Download(held))
        with pytest.raises(Failed, match=said):
            B.body(*args)
    monkeypatch.setattr(camset, "read", lambda path: Download({"global:0x01fe": 2}))
    with pytest.raises(SetUp):
        B.body(*args)


# ---------------------------------------------------------------- the size walk on a made-up camera

class Download(dict):
    """A made-up download: its records by key, each as camset's get(section, id) gives it (prove_run.held_value)."""
    def get(self, *args):
        if len(args) == 2 and isinstance(args[0], int):
            section, rid = args
            key = f"global:0x{rid:04x}" if section == 0 else f"set{section}:0x{rid:04x}"
            return SimpleNamespace(value=lambda: self[key]) if key in self else None
        return super().get(*args)


class BoxCam:
    """A made-up Custom 1 box behind its editor, as the a1 II's showed (kit2_boxsize_c1_width): the width 16 a click
    from 28 to 548, the height 12 a click, each click from the size the box has and stopping at an end, so the default
    402 lies on neither end's ladder; a dial changes the size shown in the editor, Reset puts the defaults (402 x 182)
    there, and OK keeps it."""
    W, H = (28, 548, 16), (26, 470, 12)                     # lowest, highest, a click

    def __init__(self, width=402, height=182, place=(320, 240)):
        self.width, self.height, self.place = width, height, place
        self.shown, self.turns, self.oks, self.resets = None, [], 0, 0

    @staticmethod
    def step(ends, v, n):
        lo, hi, d = ends
        return max(lo, min(hi, v + d * n)) if abs(n) <= 1 else BoxCam.step(ends, BoxCam.step(ends, v, n // abs(n)),
                                                                            n - n // abs(n))

    def opened(self):
        self.shown = [self.width, self.height]

    def turned(self, dial, n):
        self.turns.append((dial, n))
        i, ends = (0, self.W) if dial == "rear_l" else (1, self.H)
        self.shown[i] = self.step(ends, self.shown[i], n)

    def reset(self):
        self.shown, self.resets = [402, 182], self.resets + 1

    def ok(self):
        self.width, self.height = self.shown
        self.shown, self.oks = None, self.oks + 1

    def records(self) -> Download:
        return Download({"set1:0x14b6": self.width, "set1:0x14b4": self.height, "set1:0x14c2": 402, "set1:0x14c0": 182,
                         "set1:0x148a": self.width, "set1:0x1488": self.height, "set1:0x139f": self.place[0],
                         "set1:0x13a1": self.place[1], "set1:0x1327": self.place[0], "set1:0x1329": self.place[1]})


@pytest.fixture
def walk(monkeypatch, tmp_path):
    """A size walk of Custom 1 on BoxCam: opening the editor, turning, Reset, OK and registering made up on its model
    (each registration a download of its records), the edges at a size made up by the rule; returns (the walk, the
    box). sw.a.reset: whether the run has the owner's word for the editor's Reset (False)."""
    box = BoxCam()
    regs = []

    def reg(self, tag):
        self.files[tag] = f"{len(regs):05d}_{tag}.DAT"
        self.cs[tag] = box.records()
        regs.append(tag)
    monkeypatch.setattr(F.Walk, "reg", reg)
    monkeypatch.setattr(B, "open_editor", lambda sw: box.opened())
    monkeypatch.setattr(B, "turn", lambda cam, name, dial, n: box.turned(dial, n))
    monkeypatch.setattr(B, "keep_size", lambda cam, name: box.ok())
    monkeypatch.setattr(B, "press_reset", lambda cam, name: box.reset())
    monkeypatch.setattr(B, "editor_box", lambda image: None)
    measured = []

    def travel(sw, what):
        w, h = box.width, box.height
        measured.append((what, w, h))
        x, y = B.predicted(RULE["x"], w, 0), B.predicted(RULE["y"], h, 0)
        return {"area": "Custom 1", "edges": [{"key": "set1:0x139f", "low": x[0], "high": x[1]},
                                              {"key": "set1:0x13a1", "low": y[0], "high": y[1]}],
                "back": {"same": True}, "files": {"base": "x.DAT"}, "size": {"width": w, "height": h}}
    monkeypatch.setattr(B.Sizes, "measure_travel", travel)
    cam = SimpleNamespace(frame=SimpleNamespace(image=None, path=Path("00001_x.png")), read=lambda: None)
    a = SimpleNamespace(allow=list(WORDS), edge_presses=40, grip=None, block=40, confirm=2, pattern=6, put_back=None,
                        reset=False)
    recs = B.box_records(a1_doc(), "Custom 1", a1_custom())
    sw = B.Sizes(cam, None, None, SimpleNamespace(dir=tmp_path), None, None, a, {"label": "Custom 1", "code": 109},
                 (5, "Custom 1", 0), [], {}, recs, RULE, {"context": B.context_of("3:2")}, aspect=0)
    sw.measured, sw.regs = measured, regs
    return sw, box


def lines_of(sw) -> list:
    return [json.loads(x) for x in (sw.run.dir / "boxsize.jsonl").read_text(encoding="utf-8").splitlines()]


def test_a_probe_walks_single_clicks_out_and_back_and_shows_the_steps(walk, capsys):
    """--probe rear_l: from the start, three single clicks up, each registered, then three down: the steps read (16 a
    click, as kit2_boxsize_c1_probe_w3 showed), the box back at its start width; each registration a line in
    boxsize.jsonl with the context."""
    sw, box = walk
    sw.start()
    assert sw.probe("rear_l", 3) is True
    assert box.turns == [("rear_l", 1)] * 3 + [("rear_l", -1)] * 3 and box.width == 402 and box.resets == 0
    said = capsys.readouterr().out
    assert "rear_l up: 16, 16, 16 (16 a click)" in said and "rear_l down: -16, -16, -16 (-16 a click)" in said
    assert "back at its start size" in said
    lines = lines_of(sw)
    assert lines[0]["what"] == "start" and lines[0]["size"]["width"] == 402 and lines[0]["default"] is True
    assert all(ln["context"].endswith("Aspect Ratio 3:2") for ln in lines)
    assert [ln["size"]["width"] for ln in lines if ln.get("turns")] == [418, 434, 450, 434, 418, 402]


def test_a_dial_walk_whose_ladder_misses_the_start_says_so_without_the_resets_word(walk, capsys):
    """measure_dial rear_l as kit2_boxsize_c1_width ran: the ends found by a turn that changes nothing (28, 548), the
    travel at each, single clicks from each; the way back from 548's ladder lands on 404 and 388, never 402: without the
    owner's word for the editor's Reset the walk says the difference and the word that would put it back."""
    sw, box = walk
    sw.start()
    assert sw.measure_dial("rear_l") is False
    assert box.width == 388 and box.resets == 0
    assert [(m[0], m[1]) for m in sw.measured] == [("rear_l smallest", 28), ("rear_l largest", 548)]
    said = capsys.readouterr().out
    assert "rear_l smallest: width 28" in said and "rear_l largest: width 548" in said
    assert "rear_l up from the smallest: 16, 16, 16, 16, 16, 16 (16 a click)" in said
    assert "NOT PUT BACK: Custom 1's width is -14 off its start, no click lands on it from here" in said
    assert "--allow 'Custom box Reset'" in said and "--put-back" in said
    travel = [ln for ln in lines_of(sw) if ln["what"] == "travel"]
    assert travel and all(all(c["match"] for c in ln["check"]) for ln in travel)


def test_a_dial_walk_with_the_resets_word_puts_a_default_start_back_by_reset(walk, capsys):
    """The same walk under the owner's word for the editor's Reset (--allow "Custom box Reset"), the start size the
    defaults': where no click lands on the start, the editor's Reset, OK, slot 1 registered, the size judged against the
    default records and the start: back exactly."""
    sw, box = walk
    sw.a.reset = True
    sw.start()
    assert sw.measure_dial("rear_l") is True
    assert (box.width, box.height) == (402, 182) and box.resets == 1
    said = capsys.readouterr().out
    assert "NOT PUT BACK" not in said
    assert "Custom 1 put back by its editor's Reset: width 402, height 182, the default records' and the start's" in said
    (line,) = [ln for ln in lines_of(sw) if ln["what"] == "reset"]
    assert line["size"]["width"] == line["size"]["default_width"] == 402 and line["back"] is True


def test_an_owners_start_size_is_never_reset(walk, capsys):
    """A start size that is not the defaults' is the owner's: Reset would not bring it back, so it is never pressed,
    the word given or not; the difference is said, the size never printed."""
    sw, box = walk
    sw.a.reset = True
    box.width = 418                                         # on 402's ladder, not the default
    sw.start()
    assert sw.measure_dial("rear_l") is False
    assert box.resets == 0
    said = capsys.readouterr().out
    assert "NOT PUT BACK: Custom 1's width is" in said and "Custom box Reset" not in said
    assert "418" not in said


def test_a_reset_that_does_not_give_the_defaults_is_said_and_never_tried_again(walk, capsys):
    """A Reset whose registration does not read the default records (or the start) puts nothing back: said with the
    difference, and the run tries no other Reset; a Reset that met a screen other than the editor (press_reset's
    Failed) leaves the Reset unused for the rest of the run."""
    from prove_run import Failed
    sw, box = walk
    sw.a.reset = True
    sw.start()
    box.width = 388
    sw.size = dict(sw.size, width=388)
    box.reset = lambda: setattr(box, "shown", [404, 182])
    assert sw.back_to_start() is False
    said = capsys.readouterr().out
    assert "the editor's Reset did not put it back" in said and "width +2" in said
    assert not sw.can_reset()
    sw.reset_failed = False

    def stuck():
        raise Failed("Reset in Custom 1's size editor brought a screen that is not the editor")
    box.reset = stuck
    with pytest.raises(Failed):
        sw.back_to_start()
    assert not sw.can_reset()


def test_from_an_owners_start_size_no_size_or_limit_reached_from_it_is_printed(walk, capsys):
    """A start size that is not the defaults' is the owner's (decision 16): neither it nor a size reached from it (the
    odd size), nor the limits at either, is printed: sizes by their difference from the start, limits by match or
    difference alone; the lines in the run keep the values, its own evidence."""
    sw, box = walk
    box.width = 418
    sw.start()
    sw.travel("start")
    sw.point_turns(list(B.ODD), "the odd size")
    sw.travel("the odd size")
    said = capsys.readouterr().out
    assert box.width == 530 and box.height == 122
    for value in ("418", "530", "122", "255", "385", "311", "329", "103", "377"):
        assert value not in said, value
    assert "width +112 from the start, height -60 from the start" in said and "match" in said
    assert [ln["size"]["width"] for ln in lines_of(sw) if ln["what"] == "travel"] == [418, 530]


def test_the_box_kit2_boxsize_c1_width_left_is_put_back_by_reset(walk, capsys):
    """--put-back kit2_boxsize_c1_width as the camera holds it now: the run's start 402 x 182, the defaults'; Custom 1
    388 wide. One click lands on 404, a click from 388: no click lands on 402, so, under the Reset's word, the editor's
    Reset, OK, registered: back exactly, and the finish checks size and place. Without the word it is said, with the
    word to give; already at the start, nothing is turned."""
    sw, box = walk
    sw.start()
    start = lines_of(sw)[0]
    assert start["size"]["width"] == start["size"]["default_width"] == 402 and start["default"] is True
    box.width = 388
    assert sw.put_back(start) is False and box.width == 404
    assert "--allow 'Custom box Reset'" in capsys.readouterr().out
    box.width, box.turns = 388, []
    sw.a.reset = True
    assert sw.put_back(start) is True and sw.finish() is True
    assert box.turns == [("rear_l", 1)] and box.resets == 1 and (box.width, box.height) == (402, 182)
    box.turns.clear()
    assert sw.put_back(start) is True and box.turns == [] and box.resets == 1
    assert "already at its start size" in capsys.readouterr().out


def test_a_size_change_that_moves_the_boxs_place_is_a_finding(walk, capsys):
    """Each size registration's place records against the one before it: a place that moved with the size (a box near
    an edge kept inside) is kept in the line by delta and said, never by value."""
    sw, box = walk
    sw.start()
    real = box.turned

    def turned(dial, n):
        real(dial, n)
        box.place = (box.place[0] + 3, box.place[1])
    box.turned = turned
    sw.point("rear_l", 1, "probe")
    (line,) = [ln for ln in lines_of(sw) if ln["what"] == "probe"]
    assert {"key": "set1:0x139f", "delta": 3} in line["place_moved"]
    assert "the box's place moved with its size: set1:0x139f +3" in capsys.readouterr().out


# ---------------------------------------------------------------- Custom 2 left out of place (2026-11-17)

# Custom 2's place records (FRAME_TRAVEL's own places and the box in use's), as a registration writes them, at a start
# made up at the grid's centre
C2_PLACE = {"set1:0x13a3": 320, "set1:0x13a5": 240, "set1:0x133f": 320, "set1:0x1345": 240, "set1:0x1341": 320,
            "set1:0x1347": 240, "set1:0x1343": 320, "set1:0x1349": 240, "set1:0x1327": 320, "set1:0x1329": 240}
C2_DEFAULT = {"width": 402, "height": 132, "default_width": 402, "default_height": 132, "in_use_width": 402,
              "in_use_height": 132}


def c2_runs(tmp_path, monkeypatch, cleaned=False) -> None:
    """The three runs of 2026-11-17 in their real shape, where paths.run_root finds them (the sizes Sony's defaults and
    the dials' ends, the places made up): kit2_boxsize_c2, a walk of Custom 2 from its defaults, stopped by its STOP file
    after "front smallest: height 32" (no finish line; its edges at the start size kept); kit2_boxsize_c2_putback, which
    stopped before writing a line (no boxsize.jsonl); kit2_boxsize_c2_height, a walk that took 402 x 32 for the owner's
    size and finished with its place 3 off. `cleaned`: a later put-back of kit2_boxsize_c2 that brought it back."""
    from camkit import jsonl
    monkeypatch.setattr(B.paths, "run_root", lambda *a, **k: tmp_path)
    ctx = B.context_of("3:2")

    def size(w, h, default=C2_DEFAULT):
        return dict(default, width=w, height=h, in_use_width=w, in_use_height=h)

    def write(run, *lines, t0=1000.0):
        (tmp_path / run).mkdir(exist_ok=True)
        for i, ln in enumerate(lines):
            jsonl.append(tmp_path / run / "boxsize.jsonl", {"t": t0 + i, "box": "Custom 2", **ln, "context": ctx})
    write("kit2_boxsize_c2", {"what": "start", "file": "00010_size-001-start-custom-2.DAT", "size": size(402, 132),
                              "place": C2_PLACE, "default": True},
          {"what": "travel", "at": "start", "size": size(402, 132), "check": [], "back": True},
          {"what": "rear_l toward its smallest", "turns": [["rear_l", -40]], "size": size(28, 132), "place": C2_PLACE},
          {"what": "end", "dial": "rear_l", "end": "smallest", "size": size(28, 132)},
          {"what": "rear_l back to its start", "turns": [["rear_l", -1]], "size": size(388, 132), "place": C2_PLACE},
          {"what": "reset", "size": size(402, 132), "place": C2_PLACE, "back": True},
          {"what": "front toward its smallest", "turns": [["front", -40]], "size": size(402, 32), "place": C2_PLACE},
          {"what": "front toward its smallest, checked", "turns": [["front", -2]], "size": size(402, 32),
           "place": C2_PLACE},
          {"what": "end", "dial": "front", "end": "smallest", "size": size(402, 32)})
    keys = list(C2_PLACE)
    jsonl.append(tmp_path / "kit2_boxsize_c2" / "edges.jsonl",
                 {"area": "Custom 2", "code": 110, "at": "start", "size": size(402, 132), "context": ctx,
                  "files": {"base": "00012_edge-base-custom-2.DAT"}, "edges": [{"key": k} for k in keys],
                  "values": {"base": dict(C2_PLACE), "high": {k: v + 100 for k, v in C2_PLACE.items()}},
                  "back": {"same": True}, "moved": True})
    (tmp_path / "kit2_boxsize_c2_putback").mkdir()
    (tmp_path / "kit2_boxsize_c2_putback" / "setup.jsonl").write_text("{}\n", encoding="utf-8")
    off = dict(C2_PLACE, **{"set1:0x1329": 243})
    write("kit2_boxsize_c2_height", {"what": "start", "size": size(402, 32), "place": C2_PLACE, "default": False},
          {"what": "travel", "at": "start", "size": size(402, 32), "check": [], "back": False},
          {"what": "finish", "size": size(402, 32), "place": off, "size_off": {}, "place_off": {"set1:0x1329": 3}},
          t0=3000.0)
    if cleaned:
        write("kit2_boxsize_c2_putback2", {"what": "now", "size": size(402, 32), "place": off, "source": "kit2_boxsize_c2"},
              {"what": "finish", "size": size(402, 132), "place": C2_PLACE, "size_off": {}, "place_off": {},
               "source": "kit2_boxsize_c2"}, t0=4000.0)


def test_a_walk_refuses_to_start_on_a_box_an_earlier_run_left_out_of_place(no_camera, listed, tmp_path, monkeypatch,
                                                                         capsys):
    """kit2_boxsize_c2 stopped with Custom 2 at 402 x 32, and nothing since brought it back (the put-back stopped
    before a line; kit2_boxsize_c2_height began from that state and ended with the place off): a walk of Custom 2 is
    refused before anything connects, naming the put-back to run first, never taking 402 x 32 for the owner's size;
    --list says so in its plan. A put-back of the run that began from the displaced state is refused too, naming the run
    whose start is owed. Another box, with no such run behind it, is not refused."""
    c2_runs(tmp_path, monkeypatch)
    for argv in (["--box", "Custom 2"], ["--box", "Custom 2", "--dials", "front"]):
        with pytest.raises(SystemExit, match=r"kit2_boxsize_c2 left Custom 2 out of place.*--put-back kit2_boxsize_c2\b"):
            B.main(argv + allowed(*WORDS, "Custom box Reset"))
    with pytest.raises(SystemExit, match=r"kit2_boxsize_c2_height began.*--put-back kit2_boxsize_c2\b"):
        B.main(["--put-back", "kit2_boxsize_c2_height", *allowed(*WORDS, "Custom box Reset")])
    assert B.main(["--box", "Custom 2", "--list"]) == 0
    assert "a camera run is refused: kit2_boxsize_c2 left Custom 2 out of place" in capsys.readouterr().out
    assert B.main(["--put-back", "kit2_boxsize_c2", "--list"]) == 0
    assert "refused" not in capsys.readouterr().out
    called = []
    monkeypatch.setattr(B, "prove", lambda *a, **k: called.append(a) or 0)
    assert B.main(["--box", "Custom 3", *allowed(*WORDS)]) == 0 and called


def test_a_put_back_that_brought_the_box_back_lifts_the_refusal(no_camera, listed, tmp_path, monkeypatch):
    """Once a put-back of kit2_boxsize_c2 has finished with the size and place back, a walk of Custom 2 starts."""
    c2_runs(tmp_path, monkeypatch, cleaned=True)
    called = []
    monkeypatch.setattr(B, "prove", lambda *a, **k: called.append(a) or 0)
    assert B.main(["--box", "Custom 2", *allowed(*WORDS)]) == 0 and called
    assert B.left_out("Custom 2") is None


class Box2(BoxCam):
    """BoxCam as Custom 2: its records' keys, its defaults 402 x 132 and the height's ladder from its smallest (32, 12 a
    click: 132 lies on no click from 32); its place where kit2_boxsize_c2_height left it (Y 3 off)."""
    H = (32, 470, 12)

    def __init__(self):
        super().__init__(402, 32)
        self.place2 = dict(C2_PLACE, **{"set1:0x1329": 243})

    def reset(self):
        self.shown, self.resets = [402, 132], self.resets + 1

    def records(self) -> Download:
        return Download({"set1:0x14ba": self.width, "set1:0x14b8": self.height, "set1:0x14c6": 402, "set1:0x14c4": 132,
                         "set1:0x148a": self.width, "set1:0x1488": self.height, **self.place2})


@pytest.fixture
def c2_session(monkeypatch, tmp_path, listed):
    """--put-back kit2_boxsize_c2 run through its whole session on Box2: the session, setup, choosing, the editor,
    registering and the place's put-back (framepos_run.put_back_area, its source kept) made up; the session's own end
    (prover_session's except) kept as the real one keeps it. Returns (the box, what the session saw)."""
    import contextlib

    import afreg_run
    import camkit.frames
    import camkit.runs
    import prove_run
    import runner
    from camkit import camset
    c2_runs(tmp_path, monkeypatch)
    box, seen = Box2(), {"stopped": [], "put_back_area": []}
    regs = []

    def reg(self, tag):
        self.files[tag] = f"{len(regs):05d}_{tag}.DAT"
        self.cs[tag] = box.records()
        regs.append(tag)

    @contextlib.contextmanager
    def session(run, eyes, **kw):
        try:
            yield SimpleNamespace(cam=SimpleNamespace(frame=SimpleNamespace(image=None)), link=None,
                                  start=tmp_path / "00001_before.DAT")
        except Exception as e:
            seen["stopped"].append(f"{type(e).__name__}: {e}")
            print(f"stopped: {type(e).__name__}: {e}", flush=True)

    def put_back_area(cam, link, hdmi, run, cycle, model, labels, axes, t, r, a, index, turned, src, m):
        seen["put_back_area"].append(src)
        box.place2 = dict(box.place2, **src["values"]["base"])
        return {"area": t["label"], "back": {"same": True, "off": []}}
    monkeypatch.setattr(runner, "prover_session", session)
    monkeypatch.setattr(runner, "load_scan", lambda scan: (None, None))
    def run_of(name):
        (tmp_path / name).mkdir(exist_ok=True)
        return SimpleNamespace(dir=tmp_path / name, dat=tmp_path)
    monkeypatch.setattr(camkit.runs, "Run", run_of)
    monkeypatch.setattr(camkit.frames, "eyes_from_config", lambda run: None)
    monkeypatch.setattr(camset, "read", lambda path: Download({"global:0x01fe": 0}))
    monkeypatch.setattr(B, "session_parts", lambda a, doc, name: ([], {}, (5, name, 1), None, {"label": name,
                                                                                               "code": 110}))
    monkeypatch.setattr(F, "prepare", lambda *a, **k: ["Switch V/H AF Area = Off"])
    monkeypatch.setattr(afreg_run, "choose_area", lambda *a, **k: {})
    monkeypatch.setattr(prove_run, "to_shooting", lambda *a, **k: None)
    monkeypatch.setattr(F.Walk, "reg", reg)
    monkeypatch.setattr(B, "open_editor", lambda sw: box.opened())
    monkeypatch.setattr(B, "turn", lambda cam, name, dial, n: box.turned(dial, n))
    monkeypatch.setattr(B, "keep_size", lambda cam, name: box.ok())
    monkeypatch.setattr(B, "press_reset", lambda cam, name: box.reset())
    monkeypatch.setattr(B, "editor_box", lambda image: None)
    monkeypatch.setattr(F, "put_back_plan", lambda line, table=None, index=None: ({"h": {}, "v": {}}, ""))
    monkeypatch.setattr(F, "put_back_area", put_back_area)
    return box, seen


def test_the_put_back_of_a_stopped_walk_brings_size_and_place_back_to_its_start(c2_session, capsys):
    """--put-back kit2_boxsize_c2 as Custom 2 stands (402 x 32, its place 3 off since kit2_boxsize_c2_height): the size
    by clicks (32 to 128, then 140: no click lands on 132) and the editor's Reset under its word, registered at the
    defaults; then the place back to kit2_boxsize_c2's START place (its start line's place records), from wherever the
    box is, through the far corner (framepos_run.put_back_area with the start as its target), checked at the finish.
    The start is the grid's centre, which the plan says (the centre stop reaches it at any size)."""
    box, seen = c2_session
    assert B.main(["--put-back", "kit2_boxsize_c2", *allowed(*WORDS, "Custom box Reset")]) == 0
    assert (box.width, box.height) == (402, 132) and box.resets == 1 and box.turns == [("front", 8), ("front", 1)]
    ((src,),) = [seen["put_back_area"]]
    assert src["values"]["base"] == C2_PLACE and box.place2 == C2_PLACE
    out = capsys.readouterr().out
    assert "its start place is the grid's centre, which the centre stop reaches at any size" in out
    assert "Custom 2 put back by its editor's Reset: width 402, height 132" in out
    assert "Custom 2 back at its start size and place (registered)" in out and not seen["stopped"]


def test_an_error_in_a_put_back_prints_its_traceback_and_the_session_still_ends(c2_session, capsys, monkeypatch):
    """An exception that is no Failed (a KeyError, as "stopped: KeyError: 0" said on 2026-11-17 and nothing more)
    prints its traceback to the console before the session's own end (the restore) takes over."""
    box, seen = c2_session

    def broken(self, start_line):
        return {}[0]
    monkeypatch.setattr(B.Sizes, "put_back", broken)
    assert B.main(["--put-back", "kit2_boxsize_c2", *allowed(*WORDS, "Custom box Reset")]) == 1
    out = capsys.readouterr().out
    assert "Traceback (most recent call last)" in out and "KeyError: 0" in out and "in broken" in out
    assert seen["stopped"] == ["KeyError: 0"]
