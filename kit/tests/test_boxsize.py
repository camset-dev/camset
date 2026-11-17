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
