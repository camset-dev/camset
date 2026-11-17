"""The Custom focus box size prover (kit/provers/boxsize_run.py) off the camera: its plan, the guards on SET and on the
dials, a box's records, the sizes read from made-up registrations (uneven clicks, a turn that changes nothing), the
travel rule's prediction rounded inward, and the size put back. Every definition, record and value here is made up but
the a1 II's record names; nothing talks to a camera."""
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
from writer import hand_tables  # noqa: E402

A1_DEFINITION = ROOT / "editor" / "definitions" / f"{paths.A1II}.json"
INSIDE = {"x": [46, 594], "y": [42, 438]}


def a1_doc() -> dict:
    return json.loads(A1_DEFINITION.read_text(encoding="utf-8"))


def a1_custom() -> dict:
    return hand_tables.load(paths.A1II, evidence=False).FRAME_TRAVEL["Custom"]


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


def test_the_rule_predicts_each_limit_half_the_size_inside_the_cover_rounded_inward():
    """The box's centre stays inside X 46-594, Y 42-438 less half its size, each limit rounded inward: Sony's three
    default sizes land on whole numbers, an odd size rounds its low limit up and its high limit down."""
    assert B.predicted(INSIDE["x"], 402) == [247, 393] and B.predicted(INSIDE["y"], 182) == [133, 347]
    assert B.predicted(INSIDE["x"], 168) == [130, 510] and B.predicted(INSIDE["y"], 318) == [201, 279]
    assert B.predicted(INSIDE["x"], 401) == [247, 393] and B.predicted(INSIDE["y"], 183) == [134, 346]
    assert B.predicted(INSIDE["x"], 548) == [320, 320] and B.predicted(INSIDE["x"], 600) is None


def test_a_travel_check_says_match_or_the_difference_for_each_record_of_the_boxs_place():
    """Each measured record of the box's place (FRAME_TRAVEL's X and Y records) against the rule at the size the base
    registration read: a match, or each limit's difference; a measured record that is no place of the box is left out."""
    recs = B.box_records(a1_doc(), "Custom 1", a1_custom())
    edges = [{"key": "set1:0x139f", "low": 247, "high": 393}, {"key": "set1:0x13a1", "low": 135, "high": 347},
             {"key": "set1:0x9999", "low": 1, "high": 2}]
    got = {c["key"]: c for c in B.travel_check(edges, recs, INSIDE, {"width": 402, "height": 182})}
    assert set(got) == {"set1:0x139f", "set1:0x13a1"}
    assert got["set1:0x139f"] == {"key": "set1:0x139f", "axis": "x", "measured": [247, 393], "predicted": [247, 393],
                                  "match": True, "diff": [0, 0]}
    assert got["set1:0x13a1"]["match"] is False and got["set1:0x13a1"]["diff"] == [2, 0]
    assert B.travel_words(got["set1:0x13a1"]) == "measured 135 to 347, the rule 133 to 347: low +2"


def test_the_step_pattern_is_read_from_single_clicks_uneven_or_even():
    """The steps between registrations one click apart, and the pattern said: uneven clicks as they repeat ("16 every 3
    clicks"), even ones as one step, a click that changed nothing as 0."""
    assert B.steps_of([66, 71, 76, 82, 87, 92, 98]) == [5, 5, 6, 5, 5, 6]
    assert B.pattern_words([5, 5, 6, 5, 5, 6]) == "5, 5, 6, 5, 5, 6 (16 every 3 clicks)"
    assert B.pattern_words([4, 4, 4, 4]) == "4, 4, 4, 4 (4 a click)"
    assert B.pattern_words([-6, -5, -5]) == "-6, -5, -5 (-16 every 3 clicks)"
    assert B.pattern_words([5, 0]) == "5, 0 (a click changed nothing)"


def test_list_prints_the_plan_and_sends_nothing(capsys, monkeypatch):
    """--list: the box, its records, the context's setup, each dial's walk and the travel sizes, how long, and what a
    failure can leave behind; nothing connects."""
    monkeypatch.setattr(B, "read_definition", lambda: a1_doc())
    monkeypatch.setattr(B, "custom_table", lambda: a1_custom())
    monkeypatch.setattr(B, "prove", lambda *a, **k: pytest.fail("connected"))
    assert B.main(["--box", "Custom 1", "--list"]) == 0
    out = capsys.readouterr().out
    assert "Custom 1: width set1:0x14b6 (rear_l), height set1:0x14b4 (front)" in out
    assert "edges measured at the start size, at each dial's smallest and largest, and at one odd size" in out
    assert "put back by counted clicks" in out and "--put-back" in out and "Reset" in out
    assert B.main(["--box", "Custom 1", "--probe", "rear_l", "--list"]) == 0
    out = capsys.readouterr().out
    assert "probe: rear_l 3 single clicks up, each registered, then 3 down" in out and "edges" not in out


def test_a_camera_run_needs_the_owners_two_words(monkeypatch):
    """Registering a memory slot and opening the box's editor with SET (C4) are the owner's words, given per run:
    without both, nothing connects."""
    monkeypatch.setattr(B, "read_definition", lambda: a1_doc())
    monkeypatch.setattr(B, "custom_table", lambda: a1_custom())
    monkeypatch.setattr(B, "prove", lambda *a, **k: pytest.fail("connected"))
    for allow in ([], ["--allow", "Camera Set. Memory"], ["--allow", "Focus Area's SET"]):
        with pytest.raises(SystemExit, match="Camera Set. Memory.*Focus Area's SET|Focus Area's SET.*Camera Set"):
            B.main(["--box", "Custom 1", *allow])
    with pytest.raises(SystemExit, match="Custom 1, Custom 2 or Custom 3"):
        B.main(["--box", "Spot: M", "--list"])


def test_the_aspect_ratio_is_read_from_the_start_download_and_only_3_2_is_measured():
    """The context names the Aspect Ratio the start download holds, by the definition's label; the rule is for 3:2."""
    index = {s["key"]: s for s in a1_doc()["settings"]}
    assert B.aspect_of(index, Download({"global:0x01fe": 0})) == "3:2"
    assert B.aspect_of(index, Download({"global:0x01fe": 2})) == "16:9"
    assert B.aspect_of(index, Download({})) is None
    assert B.context_of("3:2") == "Switch V/H AF Area Off, camera level, AF Frame Move Amt Standard, Aspect Ratio 3:2"


# ---------------------------------------------------------------- the guards on SET and on the dials

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


def test_a_dial_is_turned_only_on_the_editor_just_read_in_chunks(texts):
    """turn: each chunk of clicks (CHUNK at most) goes only once the screen read just before it is the box's own editor;
    on the shooting screen, another box's editor or any other screen nothing is turned and the walk fails."""
    from prove_run import Failed
    cam = EditorCam([("unknown", EDITOR)])
    B.turn(cam, "Custom 1", "rear_l", -25)
    assert cam.dialled == [("rear_l", -10, "unknown"), ("rear_l", -10, "unknown"), ("rear_l", -5, "unknown")]
    for screen in (("shooting", "F5.6 ISO AUTO"), ("unknown", EDITOR.replace("1", "3", 1)), ("dialog", CHOOSER)):
        cam = EditorCam([screen])
        with pytest.raises(Failed, match="no dial"):
            B.turn(cam, "Custom 1", "front", 3)
        assert cam.dialled == [], screen
    cam = EditorCam([("unknown", EDITOR), ("unknown", EDITOR), ("shooting", "F5.6")])
    with pytest.raises(Failed, match="no dial"):
        B.turn(cam, "Custom 1", "front", 25)              # the editor gone after the first chunk: no more turned
    assert cam.dialled == [("front", 10, "unknown")]
    with pytest.raises(Failed, match="wheel"):
        B.turn(EditorCam([("unknown", EDITOR)]), "Custom 1", "wheel", 1)


class ChooserCam:
    """A made-up camera for SET and OK: its screen (kind, text) and the lit axis value `lit`; C4 opens what `after`
    gives, Enter leaves for what `ok` gives, MENU for the shooting screen; each press kept with the consent it carried."""
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


def test_set_is_pressed_only_on_focus_areas_chooser_with_the_box_lit(texts, monkeypatch):
    """open_editor: SET (C4, allowed by name) only once the chooser reads as Focus Area's with the wanted box lit (the
    axis value read again) and SET on its trash button; and what it opens must read as that box's own editor."""
    import afreg_run
    import prove_run
    from prove_run import Failed
    monkeypatch.setattr(afreg_run, "choose_level", lambda *a: {})
    monkeypatch.setattr(prove_run, "axis_reading", lambda cam, vals: (cam.lit, {}))
    monkeypatch.setattr(afreg_run, "kept_notice", lambda cam, step, words=None, kind="": cam.frame.path.name)

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


def test_the_editors_ok_carries_its_consent_and_must_land_on_the_shooting_screen(texts, monkeypatch):
    """keep_size: OK only on the box's editor read just before, carrying the camera's consent for that one press
    (camkit.live.BoxEditor, named for the box); a notice after it is kept in the run's events, left with MENU, and fails
    the size; anything but the shooting screen after it fails it too."""
    import afreg_run
    from camkit import live
    from prove_run import Failed
    monkeypatch.setattr(afreg_run, "kept_notice", lambda cam, step, words=None, kind="": cam.frame.path.name)
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


def test_a_start_download_not_at_3_2_stops_the_run_before_any_press(monkeypatch, tmp_path):
    """The rule is for Aspect Ratio 3:2: a start download that holds another, or none, stops the run before its setup
    and its first press, saying what it read."""
    from camkit import camset
    from prove_run import Failed
    monkeypatch.setattr(F, "slot_filled", lambda cs: True)
    monkeypatch.setattr(F, "prepare", lambda *a, **k: pytest.fail("set up"))
    index = {s["key"]: s for s in a1_doc()["settings"]}
    recs = B.box_records(a1_doc(), "Custom 1", a1_custom())
    s = SimpleNamespace(cam=SimpleNamespace(press=lambda *a, **k: pytest.fail("pressed")), link=None,
                        start=tmp_path / "00001_before.DAT")
    for held, said in (({"global:0x01fe": 2}, "16:9"), ({}, "nothing")):
        monkeypatch.setattr(camset, "read", lambda path, held=held: Download(held))
        with pytest.raises(Failed, match=f"Aspect Ratio reads {said}"):
            B.body(s, SimpleNamespace(probe="rear_l", tracking=False), SimpleNamespace(dir=tmp_path), None, None, None,
                   [], {}, index, recs, INSIDE, {"label": "Custom 1", "code": 109}, (5, "Custom 1", 0), None, {})


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
    """A made-up Custom 1 box behind its editor: the width steps over a lattice by value (66 + 16k/3 rounded down: 5, 5,
    6 units a click), the height 4 units a click, each stopping at its ends; a dial changes the size shown in the editor
    and OK keeps it (Cancel would drop it). `start` puts the box at a width off the lattice (a size set otherwise)."""
    W = [66 + (16 * k) // 3 for k in range(0, 91)]           # 66 ... 546
    H = list(range(42, 439, 4))                              # 42 ... 438

    def __init__(self, width=402, height=182, place=(320, 240)):
        self.width, self.height, self.place = width, height, place
        self.shown, self.turns, self.oks = None, [], 0

    def step(self, values, v, n):
        for _ in range(abs(n)):
            if n > 0:
                up = [x for x in values if x > v]
                v = up[0] if up else v
            else:
                down = [x for x in values if x < v]
                v = down[-1] if down else v
        return v

    def opened(self):
        self.shown = [self.width, self.height]

    def turned(self, dial, n):
        self.turns.append((dial, n))
        if dial == "rear_l":
            self.shown[0] = self.step(self.W, self.shown[0], n)
        else:
            self.shown[1] = self.step(self.H, self.shown[1], n)

    def ok(self):
        self.width, self.height = self.shown
        self.shown, self.oks = None, self.oks + 1

    def records(self) -> Download:
        return Download({"set1:0x14b6": self.width, "set1:0x14b4": self.height, "set1:0x14c2": 402, "set1:0x14c0": 182,
                         "set1:0x148a": self.width, "set1:0x1488": self.height, "set1:0x139f": self.place[0],
                         "set1:0x13a1": self.place[1], "set1:0x1327": self.place[0], "set1:0x1329": self.place[1]})


@pytest.fixture
def walk(monkeypatch, tmp_path):
    """A size walk of Custom 1 on BoxCam: opening the editor, turning, OK and registering made up on its model (each
    registration a download of its records), the edges at a size made up by the rule; returns (the walk, the box)."""
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
    monkeypatch.setattr(B, "editor_box", lambda image: None)
    measured = []

    def travel(sw, what):
        w, h = box.width, box.height
        measured.append((what, w, h))
        x, y = B.predicted(INSIDE["x"], w), B.predicted(INSIDE["y"], h)
        return {"area": "Custom 1", "edges": [{"key": "set1:0x139f", "low": x[0], "high": x[1]},
                                              {"key": "set1:0x13a1", "low": y[0], "high": y[1]}],
                "back": {"same": True}, "files": {"base": "x.DAT"}, "size": {"width": w, "height": h}}
    monkeypatch.setattr(B.Sizes, "measure_travel", travel)
    cam = SimpleNamespace(frame=SimpleNamespace(image=None, path=Path("00001_x.png")), read=lambda: None)
    a = SimpleNamespace(allow=["Camera Set. Memory", "Focus Area's SET"], edge_presses=40, grip=None, block=40,
                        confirm=2, pattern=6, put_back=None)
    recs = B.box_records(a1_doc(), "Custom 1", a1_custom())
    sw = B.Sizes(cam, None, None, SimpleNamespace(dir=tmp_path), None, None, a, {"label": "Custom 1", "code": 109},
                 (5, "Custom 1", 0), [], {}, recs, INSIDE, {"context": B.context_of("3:2")})
    sw.measured, sw.regs = measured, regs
    return sw, box


def lines_of(sw) -> list:
    return [json.loads(x) for x in (sw.run.dir / "boxsize.jsonl").read_text(encoding="utf-8").splitlines()]


def test_a_probe_walks_single_clicks_out_and_back_and_shows_the_steps(walk, capsys):
    """--probe rear_l: from the start, three single clicks up, each registered, then three down: the steps read (uneven,
    5, 5, 6), the box back at its start width; each registration a line in boxsize.jsonl with the context."""
    sw, box = walk
    sw.start()
    assert sw.probe("rear_l", 3) is True
    assert box.turns == [("rear_l", 1)] * 3 + [("rear_l", -1)] * 3 and box.width == 402
    said = capsys.readouterr().out
    assert "rear_l up: 5, 5, 6 (16 every 3 clicks)" in said and "rear_l down: -6, -5, -5" in said
    assert "back at its start size" in said
    lines = lines_of(sw)
    assert lines[0]["what"] == "start" and lines[0]["size"]["width"] == 402 and lines[0]["default"] is True
    assert all(ln["context"].endswith("Aspect Ratio 3:2") for ln in lines)
    assert [ln["size"]["width"] for ln in lines if ln.get("turns")] == [407, 412, 418, 412, 407, 402]
    assert [ln for ln in lines if ln["what"] == "probe steps"][0]["up"] == [5, 5, 6]


def test_a_dial_walk_finds_both_ends_by_a_turn_that_changes_nothing_and_comes_back(walk, capsys):
    """measure_dial rear_l: blocks down until a turn changes nothing (the smallest width, 66), the travel measured there,
    single clicks up from it (the pattern), blocks up until nothing changes (546), the travel there, single clicks down,
    then back to the start width by counted clicks, each landing registered; the ends, steps and travel said."""
    sw, box = walk
    sw.start()
    assert sw.measure_dial("rear_l") is True
    assert box.width == 402 and box.height == 182
    assert [m[0] for m in sw.measured] == ["rear_l smallest", "rear_l largest"]
    assert [(m[1], m[2]) for m in sw.measured] == [(66, 182), (546, 182)]
    said = capsys.readouterr().out
    assert "rear_l smallest: width 66" in said and "rear_l largest: width 546" in said
    assert "rear_l up from the smallest: 5, 5, 6, 5, 5, 6 (16 every 3 clicks)" in said
    assert "rear_l down from the largest: -6, -5, -5, -6, -5, -5 (-16 every 3 clicks)" in said
    assert "back at its start size" in said
    ends = [ln for ln in lines_of(sw) if ln.get("end")]
    assert [(ln["dial"], ln["end"], ln["size"]["width"]) for ln in ends] == [("rear_l", "smallest", 66),
                                                                           ("rear_l", "largest", 546)]
    travel = [ln for ln in lines_of(sw) if ln["what"] == "travel"]
    assert travel and all(all(c["match"] for c in ln["check"]) for ln in travel)


def test_a_start_off_the_lattice_the_clicks_walk_is_said_and_never_guessed(walk, capsys):
    """A start width the dial's clicks do not land on from where they walk (set otherwise): the walk back brackets it
    between two widths a click apart, stops, and says the difference, what to do by hand and --put-back; nothing more
    is turned."""
    sw, box = walk
    box.width = 400                                         # not 66 + 16k/3
    sw.start()
    assert sw.probe("rear_l", 1) is False
    said = capsys.readouterr().out
    assert "NOT PUT BACK" in said and "width" in said and "no click lands on it" in said
    assert "--put-back" in said and "400" not in said      # the owner's size: never printed (decision 16)


def test_from_an_owners_start_size_no_size_or_limit_reached_from_it_is_printed(walk, capsys):
    """A start size that is not the defaults' is the owner's (decision 16): neither it nor a size reached from it (the
    odd size), nor the limits at either, is printed: sizes by their difference from the start, limits by match or
    difference alone; the lines in the run keep the values, its own evidence."""
    sw, box = walk
    box.width = 418                                         # on the lattice, not the default 402
    sw.start()
    sw.travel("start")
    sw.point_turns(list(B.ODD), "the odd size")
    sw.travel("the odd size")
    said = capsys.readouterr().out
    assert box.width == 455 and box.height == 162
    for value in ("418", "455", "162", "255", "385", "274", "366", "123", "357"):
        assert value not in said, value
    assert "width +37 from the start, height -20 from the start" in said and "match" in said
    assert [ln["size"]["width"] for ln in lines_of(sw) if ln["what"] == "travel"] == [418, 455]


def test_a_size_left_behind_is_put_back_from_the_runs_own_start(walk, capsys):
    """--put-back RUN: the start size RUN's first line read, the box wherever a failed run left it: registered, turned
    back by counted clicks, each landing registered and checked; already there, nothing is turned."""
    sw, box = walk
    sw.start()
    start = lines_of(sw)[0]
    box.width, box.height = 450, 150                        # where a run that failed left it (on both lattices)
    assert 450 in BoxCam.W and 150 in BoxCam.H
    assert sw.put_back(start) is True
    assert (box.width, box.height) == (402, 182)
    box.turns.clear()
    assert sw.put_back(start) is True and box.turns == []
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
