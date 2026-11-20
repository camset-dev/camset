"""The Bracket Type carousel (the a1 II's Shooting > Drive Mode > Bracket Settings > Bracket Type, open only with the drive
mode dial on BRK): the pixel reader tells a carousel option's lit field from the option lit; the axis walk and the axis
proofs take the BRK crawl's own map; kit/provers/carousel_fields_run.py proves an option's fields one value a download
on a made-up carousel, and kit/pass2_report.py credits its lines. The camera's frames some read are found by their own
path (camkit.paths.a1ii_root()), and those tests skip without them."""
import contextlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
from camkit import paths, screen  # noqa: E402
from camkit.frames import Frame, load  # noqa: E402
from test_definitions import needs_evidence  # noqa: E402

A1 = paths.a1ii_root()
ORANGE = (200, 80, 20)
CONT = ((137, 345), (353, 563))                         # Cont. Bracket's two boxes, as drawn at y 351-406
FOCUS = ((137, 382), (393, 449), (449, 506), (506, 562))  # Focus Bracket's Step Width and its three digits


def need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path} not present")
    return path


def carousel(lit=None, boxes=CONT, y=351, h=56) -> Frame:
    """A made-up carousel: the divider at x 112, the strip's option icon at the centre slot (orange while the option is
    lit, white once a field is), the option's boxes on one line, box `lit` filled orange and the others outlined in
    grey; digit boxes drawn side by side share a side."""
    a = np.zeros((480, 640, 3), np.uint8)
    a[5:420, 112] = 200
    a[195:230, 38:73] = ORANGE if lit is None else (230, 230, 230)
    for x0, x1 in boxes:
        for part in (a[y, x0:x1 + 1], a[y + h - 1, x0:x1 + 1], a[y:y + h, x0], a[y:y + h, x1]):
            part[...] = 85
    if lit is not None:
        x0, x1 = boxes[lit]
        a[y:y + h, x0:x1 + 1] = ORANGE
    return Frame(image=a, t=0.0)


def test_a_carousel_with_its_option_lit_reads_no_field():
    s = screen.read(carousel())
    assert s.kind == "dialog" and s.slots[screen.CENTRE] == "selected"
    assert s.field is None and s.boxes == [] and s.bar is None


@pytest.mark.parametrize("boxes, lit", [(CONT, 0), (CONT, 1), (FOCUS, 0), (FOCUS, 1), (FOCUS, 2), (FOCUS, 3)])
def test_a_lit_field_reads_its_index_among_the_boxes(boxes, lit):
    """Right from the option lights a box: the reader gives its index among the boxes on its line, and every box, the
    digit boxes that share their sides told apart."""
    s = screen.read(carousel(lit, boxes))
    assert s.kind == "dialog"
    assert s.field == lit and len(s.boxes) == len(boxes) and s.bar == (351, 406)
    assert s.boxes[lit] == boxes[lit]


def test_the_strip_and_the_title_are_never_a_field():
    """An orange block left of the divider (the strip's lit icon) or in the title band is no field."""
    f = carousel()
    f.image[60:110, 130:330] = ORANGE
    f.image[300:356, 20:100] = ORANGE
    s = screen.read(f)
    assert s.kind == "dialog" and s.field is None


BRK = [("kit2_fin_brtype_cont/shots/00005_right.png", None, 0),       # Cont. Bracket lit
       ("kit2_fin_brtype_cont/shots/00006_right.png", 0, 2),          # its Exposure Value lit
       ("kit2_fin_brtype_cont_img/shots/00007_right.png", 1, 2),      # its Number of Shots lit
       ("kit2_fin_brtype_cont_img/shots/00008_up.png", 1, 2),         # one Up on it: 5 Images
       ("kit2_fin_brtype_f_look/shots/00007_right.png", 0, 2),        # Single Bracket's Exposure Value
       ("kit2_fin_brtype_f_look/shots/00008_right.png", 1, 2),        # its Number of Shots
       ("kit2_fin_brtype_f_look/shots/00009_menu.png", None, 0),      # MENU in the fields: the option lit again
       ("kit2_fin_brtype_f_look2/shots/00007_down.png", None, 0),     # Focus Bracket lit
       ("kit2_fin_brtype_f_look2/shots/00008_right.png", 0, 4),       # its Step Width
       ("kit2_fin_brtype_f_look2/shots/00009_right.png", 1, 4),       # its Number of Shots' first digit
       ("kit2_fin_brtype_wbhi/shots/00009_right.png", None, 0)]       # White Balance Bracket: Hi, a second axis


@pytest.mark.parametrize("name, field, count", BRK)
def test_the_cameras_bracket_type_frames(name, field, count):
    s = screen.read(load(need(A1 / name)))
    assert s.kind == "dialog"
    assert s.field == field and len(s.boxes) == count


def long_value(lit=1, boxes=CONT, y=351, h=56) -> Frame:
    """carousel(lit) holding a long white value in its lit box, the ▲ and ▼ drawn white over the box's top and bottom
    edges: half the box left orange (Bracket Type's "2 Images (-)" left 59 %, kit2_pass2 265237), its sides whole."""
    f = carousel(lit, boxes, y, h)
    x0, x1 = boxes[lit]
    for x in range(x0 + 14, x1 - 14, 8):
        f.image[y + 8:y + h - 8, x:x + 6] = 230
    cx = (x0 + x1) // 2
    f.image[y - 3:y + 4, cx - 8:cx + 9] = 230
    f.image[y + h - 4:y + h + 3, cx - 8:cx + 9] = 230
    return f


def test_a_lit_box_holding_a_long_value_is_still_the_field():
    """A lit box under 60 % orange (_active_field's fill) is still the field where its own four sides are orange
    (screen._lit_box): the value's text takes from the box's middle, never from its sides."""
    f = long_value()
    x0, x1 = CONT[1]
    assert float(screen._orange(f.image)[351:407, x0:x1 + 1].mean()) < 0.6
    s = screen.read(f)
    assert s.kind == "dialog" and s.field == 1 and s.boxes == list(CONT) and s.bar == (351, 406)


def test_an_orange_outline_is_no_lit_box():
    """An orange frame round a box, its inside black, is no field: its sides are orange, but it is under 40 % orange."""
    f = carousel()
    x0, x1 = CONT[1]
    f.image[351:407, x0:x1 + 1] = ORANGE
    f.image[355:403, x0 + 4:x1 - 3] = 0
    s = screen.read(f)
    assert s.kind == "dialog" and s.field is None and s.boxes == []


@pytest.mark.parametrize("before, lit_before, after, boxes", [
    ("265236_fresh.png", 1, "265237_down.png", [(137, 345), (354, 563)]),  # Bracket Type: "2 Images (-)", 59 % orange
    ("233912_down.png", 1, "233914_down.png", [(137, 345), (354, 563)]),   # Drive Mode's Cont. Bracket: "2 Images (+)"
    ("177248_down-late.png", 0, "177249_right.png", [(137, 345), (354, 563), (573, 624)])])   # Single Bracket's, the › box
def test_the_cameras_lit_box_holding_2_images(before, lit_before, after, boxes):
    """The camera's own frames over HDMI, a lit Number of Shots box holding a long value under 60 % orange: box 1 lit, as
    the frame before it and the press between say (265237 is the failure of 2026-11-20: Down on "3 Images" drew "2 Images
    (-)"; 177249 is a Right from box 0)."""
    was, s = (screen.read(load(need(A1 / "kit2_pass2" / "shots" / n))) for n in (before, after))
    assert s.kind == "dialog" and s.field == 1 and s.boxes == boxes and s.bar == (351, 405)
    assert was.field == lit_before and len(was.boxes) == len(boxes) and was.bar == s.bar


# ------------------------------------------------------------------------------------- A: the second axis of this row

BRK_MAP = "kit2_fin_crawl_brk/map.json"
ROW = ["Bracket Settings", "Bracket Type"]
OPTIONS = ["Cont. Bracket", "Single Bracket", "Focus Bracket", "White Balance Bracket: Lo", "DRO Bracket: Lo"]
WB, DRO = ["White Balance Bracket: Lo", "White Balance Bracket: Hi"], ["DRO Bracket: Lo", "DRO Bracket: Hi"]


def brk_root(own_runs, monkeypatch) -> Path:
    """The made-up camera's runs (CAMSET_RUNS): the BRK crawl's own map (its one carousel, as kit2_fin_crawl_brk's map
    names it) and an axes.json holding pass 1's Drive Mode axis and the BRK walk's two, proving.base pointed at them."""
    import json

    import proving.base as base
    from conftest import TEST_CAMERA
    root = own_runs / TEST_CAMERA
    (root / "kit2_fin_crawl_brk").mkdir(parents=True)
    (root / BRK_MAP).write_text(json.dumps({"rows": [
        {"path": ROW, "kind": "dialog", "options": [{"index": i, "label": lab, "frame": f"{6 + i:05d}_down.png"}
                                                    for i, lab in enumerate(OPTIONS)]}]}), encoding="utf-8")
    (root / "kit2_axes").mkdir()
    (root / "kit2_axes" / "axes.json").write_text(json.dumps({
        "Drive Mode": {"White Balance Bracket": {"values": WB, "rights": 2, "back": WB[0]}},
        "Bracket Settings > Bracket Type": {
            "White Balance Bracket": {"values": WB, "rights": 2, "back": WB[0], "map": BRK_MAP},
            "DRO Bracket": {"values": DRO, "rights": 2, "back": DRO[0], "map": BRK_MAP}}}), encoding="utf-8")
    monkeypatch.setattr(base, "AXES", root / "kit2_axes" / "axes.json")
    monkeypatch.setattr(base, "PASS1", root / "kit2_pass1")
    monkeypatch.setattr(base, "MAP", root / "kit2_pass1" / "map_all.json")
    return root


def test_axis_jobs_are_the_map_in_uses_own(own_runs, monkeypatch):
    """On pass 1's map the axis jobs are the entries with no map, as before; on the BRK crawl's map those its own axis
    walk wrote, the row inside a submenu by its whole path; --rows narrows them by ROW / OPTION."""
    import proving.base as base
    from proving.jobs import axis_jobs, job_key
    root = brk_root(own_runs, monkeypatch)
    assert [(j["path"], j["option"]) for j in axis_jobs()] == [(["Drive Mode"], "White Balance Bracket")]
    monkeypatch.setattr(base, "MAP", root / BRK_MAP)
    got = axis_jobs()
    assert [(j["path"], j["kind"], j["option"], j["values"]) for j in got] == [
        (ROW, "axis", "White Balance Bracket", WB), (ROW, "axis", "DRO Bracket", DRO)]
    assert [job_key(j) for j in got] == ["Bracket Settings > Bracket Type / White Balance Bracket",
                                         "Bracket Settings > Bracket Type / DRO Bracket"]
    assert [j["option"] for j in axis_jobs({"Bracket Settings > Bracket Type / DRO Bracket"})] == ["DRO Bracket"]


def test_prove_run_with_the_map_plans_the_axis_values_of_this_row(own_runs, monkeypatch, capsys):
    """prove_run --map (the BRK crawl's map) --context --rows ROW / OPTION --list: the two axis jobs, two values each, and
    no job of pass 1's axes; before 2026-11-19 a --map run planned no axis job at all."""
    import prove_run
    from camkit import models
    root = brk_root(own_runs, monkeypatch)
    monkeypatch.setattr(prove_run.models, "current", lambda r: models.A1II)
    monkeypatch.setattr(prove_run, "load_scan", lambda scan, **k: ([], {}))
    monkeypatch.setattr(sys, "argv", ["prove_run.py", "--map", str(root / BRK_MAP), "--context", "Drive Mode dial on BRK",
                                      "--rows", "Bracket Settings > Bracket Type / White Balance Bracket",
                                      "--rows", "Bracket Settings > Bracket Type / DRO Bracket", "--list"])
    prove_run.main()
    out = capsys.readouterr().out
    assert "2 rows to prove, 4 options" in out
    assert "Bracket Settings > Bracket Type / White Balance Bracket" in out and "Drive Mode /" not in out


def test_axis_walk_reads_a_maps_rows_with_that_crawls_own_frames(own_runs, monkeypatch):
    """--map: the carousel's options with side arrows on its own crawl's frames (frame numbers repeat across runs:
    pass 1's folder is never looked in), the row keyed by its whole path."""
    import axis_walk
    root = brk_root(own_runs, monkeypatch)
    shots = root / "kit2_fin_crawl_brk" / "shots"
    shots.mkdir()
    for i in range(len(OPTIONS)):
        (shots / f"{6 + i:05d}_down.png").write_bytes(b"")
    (root / "kit2_pass1" / "shots").mkdir(parents=True)
    (root / "kit2_pass1" / "shots" / "00007_down.png").write_bytes(b"")
    sided = {"00009_down.png", "00010_down.png"}             # White Balance and DRO Bracket, as the crawl saw them
    monkeypatch.setattr(axis_walk, "load", lambda p: p)
    monkeypatch.setattr(axis_walk.screen, "read", lambda p: type("S", (), {"glyphs": dict.fromkeys(
        axis_walk.AXIS_GLYPHS, p.parent.parent.name == "kit2_fin_crawl_brk" and p.name in sided)})())
    monkeypatch.setattr(axis_walk, "MAP", str(root / BRK_MAP))
    assert axis_walk.axis_options() == {" > ".join(ROW): {"labels": OPTIONS, "axis": [WB[0], DRO[0]]}}


def test_axis_walk_reads_the_brk_crawls_frames(monkeypatch):
    """The camera's own BRK crawl (kit2_fin_crawl_brk): White Balance Bracket and DRO Bracket draw side arrows."""
    import axis_walk
    monkeypatch.setattr(axis_walk, "MAP", str(need(A1 / BRK_MAP)))
    assert axis_walk.axis_options() == {" > ".join(ROW): {"labels": OPTIONS, "axis": [WB[0], DRO[0]]}}


def test_a_maps_walk_leaves_the_rows_another_walk_wrote():
    import axis_walk
    found = {"Drive Mode": {"White Balance Bracket": {"values": WB}},
             "Bracket Settings > Bracket Type": {"DRO Bracket": {"values": DRO, "map": BRK_MAP}}}
    todo = {"Drive Mode": {}, "Bracket Settings > Bracket Type": {}, "Metering Mode": {}}
    assert axis_walk.held_elsewhere(todo, found, BRK_MAP) == ["Drive Mode"]
    assert axis_walk.held_elsewhere(todo, found, "kit2_other/map.json") == ["Drive Mode", "Bracket Settings > Bracket Type"]
    assert axis_walk.held_elsewhere(todo, found, None) == ["Bracket Settings > Bracket Type"]


class BrkCarousel:
    """The Bracket Type row inside its submenu: Right opens the carousel on Cont. Bracket, Down and Up move between the
    options, Right and Left on White Balance or DRO Bracket step its Lo/Hi axis (it wraps), MENU cancels back to the
    submenu row, Left from the submenu goes back to the menu page."""
    AXES = {3: WB, 4: DRO}

    def __init__(self):
        self.where, self.opt, self.axis, self.keys, self.n = "page", 0, {3: 0, 4: 0}, [], 0
        self.frame = type("F", (), {"path": Path("00000_page.png")})()

    def press(self, key, **kw):
        self.keys.append(key)
        self.n += 1
        self.frame.path = Path(f"{self.n:05d}_{key}.png")
        if self.where == "row" and key == "right":
            self.where, self.opt = "dialog", 0
        elif self.where == "row" and key == "left":
            self.where = "page"
        elif self.where == "dialog" and key in ("down", "up"):
            self.opt = (self.opt + (1 if key == "down" else -1)) % len(OPTIONS)
        elif self.where == "dialog" and key in ("right", "left") and self.opt in self.AXES:
            self.axis[self.opt] = (self.axis[self.opt] + 1) % 2
        elif self.where == "dialog" and key == "menu":
            self.where, self.axis = "row", {3: 0, 4: 0}
        elif key == "enter":
            raise AssertionError("Enter in a read-only walk")

    def read(self):
        kind = {"page": "menu", "row": "submenu", "dialog": "dialog"}[self.where]
        return type("S", (), {"kind": kind, "glyphs": {"side_right": self.where == "dialog" and self.opt in self.AXES}})()

    def title(self):
        return self.AXES[self.opt][self.axis[self.opt]] if self.opt in self.AXES else OPTIONS[self.opt]


def test_axis_walk_walks_a_submenu_rows_axes_and_tags_them_with_its_map(own_runs, monkeypatch):
    """axis_walk --map on the BRK crawl's map: into the submenu to Bracket Type, Right, Down to the option, Right round
    its axis and Left back, MENU (back on the submenu row), Left to the menu page, for each option; axes.json keeps pass
    1's row and holds the BRK row's two axes, each naming the map; nothing is ever entered."""
    import contextlib
    import json

    import axis_walk
    root = brk_root(own_runs, monkeypatch)
    axes = root / "kit2_axes" / "axes.json"
    held = json.loads(axes.read_text(encoding="utf-8"))
    del held["Bracket Settings > Bracket Type"]
    axes.write_text(json.dumps(held), encoding="utf-8")
    cam, entered = BrkCarousel(), []

    @contextlib.contextmanager
    def session(run, eyes, **kw):
        yield type("S", (), {"cam": cam, "close": lambda self: entered.append("closed")})()

    def enter_any(c, path, start, at=None):
        assert c.where == "page" and path == ROW
        entered.append("enter")
        c.where = "row"
    for name, value in (("axis_options", lambda: {" > ".join(ROW): {"labels": OPTIONS, "axis": [WB[0], DRO[0]]}}),
                        ("load_scan", lambda scan: ([{"screen": "page"}], {})), ("eyes_from_config", lambda run: None),
                        ("prover_session", session), ("menu_from_shooting", lambda c, **k: None),
                        ("same_position", lambda a, b: a.kind == "menu"), ("go_to", lambda c, cycle, model, j, row: 0),
                        ("enter_any", enter_any), ("title", lambda c: c.title())):
        monkeypatch.setattr(axis_walk, name, value)
    monkeypatch.setattr(sys, "argv", ["axis_walk.py", "--map", str(root / BRK_MAP), "--scan", "made-up"])
    axis_walk.main()
    assert entered == ["enter", "enter"]
    one = ["right", "down", "down", "down", "right", "right", "left", "left", "menu", "left"]
    assert cam.keys == one + ["right", "down", "down", "down", "down", "right", "right", "left", "left", "menu", "left"]
    got = json.loads(axes.read_text(encoding="utf-8"))
    assert got["Drive Mode"] == held["Drive Mode"]
    assert got["Bracket Settings > Bracket Type"] == {
        "White Balance Bracket": {"values": WB, "rights": 2, "back": WB[0], "map": BRK_MAP},
        "DRO Bracket": {"values": DRO, "rights": 2, "back": DRO[0], "map": BRK_MAP}}


def test_an_axis_proof_on_a_submenu_row(monkeypatch):
    """prove_axis_row on a row inside a submenu: named by its whole path, its downloads by the row's own name, the lines
    the White Balance Bracket proofs make: Hi with the option's record and the axis's, then Lo back on Cont. Bracket
    changing nothing."""
    from test_core import FakeCarousel, _axis_camera, _Dat, _Lines

    class Brk(FakeCarousel):
        OPTIONS = ["Cont. Bracket", "Single Bracket", "Focus Bracket", "White Balance Bracket"]
        AXIS = 3
    cam = Brk(WB)
    P, link, downloads = _axis_camera(monkeypatch, cam)
    job = {"path": ROW, "kind": "axis", "option": "White Balance Bracket", "values": WB}
    out = _Lines()
    P.prove_axis_row(cam, link, None, job, _Dat("00001_before.DAT", {"option": 0, "axis": 0}), out)
    assert [d.name for d in downloads] == ["00002_Bracket Type-axis-1.DAT", "00003_Bracket Type-axis-0.DAT"]
    assert [(r["path"], r["kind"], r["option"], r["index"], r["label"], r["final"],
             [(c["key"], c["before"], c["after"]) for c in r["changes"]]) for r in out] == [
        (ROW, "axis", "White Balance Bracket", 1, WB[1], False, [("option", 0, 3), ("axis", 0, 1)]),
        (ROW, "axis", "White Balance Bracket", 0, WB[0], True, [])]


# ------------------------------------------------------------------------------------- B: a carousel option's fields

def box(label, values, held, wraps=False):
    return {"label": label, "values": values, "held": values.index(held), "wraps": wraps}


# Cont. Bracket's boxes as the camera drew them (kit2_fin_brtype_cont): its step stops at 0.3EV, the lowest; made-up ends
CONT_BOXES = [box("Exposure Value", ["0.3EV", "0.5EV", "0.7EV", "1.0EV"], "0.3EV"),
              box("Number of Shots", ["2 Images", "3 Images", "5 Images"], "3 Images")]
# Focus Bracket's: Step Width, then the number of shots in three digit boxes, each coming round (made-up spans)
FOCUS_BOXES = [box("Step Width", ["3", "4(Standard)", "5"], "4(Standard)"),
               box("Number of Shots", ["0", "1"], "0", wraps=True), box("Number of Shots", ["0", "1", "2"], "0", wraps=True),
               box("Number of Shots", ["1", "2", "3", "4"], "3", wraps=True)]


class FieldsCam:
    """Bracket Type in its submenu on the camera's default file (Cont. Bracket chosen): Right on the row opens the
    carousel on the option chosen, Up and Down move between options; Right on Cont. Bracket or Focus Bracket lights its
    first box, Right the next (never past the last: the camera's answer there was never seen, so it fails the test), Up
    and Down step the lit box (stopping at its ends, or coming round), MENU in the boxes goes back to the option, Enter
    chooses the option with what its boxes hold and goes back to the row. Each press and fresh look is a new frame. The
    records: Bracket Type, Cont. Bracket's step and count in one (a made-up code), its step alone in a made-up record,
    Focus Bracket's Step Width and its number."""

    def __init__(self, same_text=()):
        self.spec = {0: CONT_BOXES, 2: FOCUS_BOXES}
        self.at = {o: [b["held"] for b in bs] for o, bs in self.spec.items()}
        self.saved, self.where, self.opt, self.field, self.edit = 0, "shooting", 0, None, []
        self.keys, self.n, self.closes, self.lost = [], 0, [], None
        self.same_text = set(same_text)       # values the readers read alike ("2 Images" for two of them)
        self.extra = {}                       # records a test sets beside the boxes'
        self.drop = None                      # (key, n): the n-th press of key goes unanswered (a new frame, no change)
        self.correct = None                   # correct(option, edit) -> the boxes the camera keeps on Enter
        self.rule = None                      # rule(option, edit, field, key) -> the boxes after Up or Down on a field
        self.lit_moves = False                # an unlit box's picture changes with the box lit (the camera's digit
        #                                       boxes: the pixel reader finds their sides where the lit box beside them
        #                                       leaves them, kit2_pass2 269127/269128)
        self.shoot("start")

    def shoot(self, tag):
        self.n += 1
        self.frame = SimpleNamespace(path=Path(f"{self.n:05d}_{tag}.png"), image=None)

    def press(self, key, **kw):
        self.keys.append(key)
        boxes = self.spec.get(self.opt, [])
        if self.drop is not None and self.keys.count(self.drop[0]) == self.drop[1] and key == self.drop[0]:
            self.shoot(key)                      # the press the camera did not answer
            return
        if self.where == "row" and key == "right":
            self.where, self.opt, self.field = "dialog", self.saved, None
            self.edit = list(self.at.get(self.saved, []))
        elif self.where == "dialog" and self.field is None and key in ("up", "down"):
            self.opt = (self.opt + (1 if key == "down" else -1)) % len(OPTIONS)
            self.edit = list(self.at.get(self.opt, []))
        elif self.where == "dialog" and key == "right" and boxes:
            if self.field is not None and self.field + 1 >= len(boxes):
                raise AssertionError("Right on the last box")
            self.field = 0 if self.field is None else self.field + 1
        elif self.where == "dialog" and self.field is not None and key in ("up", "down") and self.rule:
            self.edit = list(self.rule(self.opt, self.edit, self.field, key))
        elif self.where == "dialog" and self.field is not None and key in ("up", "down"):
            b, n = boxes[self.field], len(boxes[self.field]["values"])
            i = self.edit[self.field] + (1 if key == "up" else -1)
            self.edit[self.field] = i % n if b["wraps"] else max(0, min(n - 1, i))
        elif self.where == "dialog" and key == "enter":
            self.saved, self.where, self.field = self.opt, "row", None
            if boxes:
                self.at[self.opt] = list(self.correct(self.opt, self.edit) if self.correct else self.edit)
        elif self.where == "dialog" and key == "menu":
            if self.field is not None:
                self.field = None
            else:
                self.where = "row"
        else:
            raise AssertionError(f"{key} on the {self.where} in the made-up camera")
        if self.lost is not None and self.keys.count(self.lost[0]) == self.lost[1]:
            self.where = "lost"                  # the screen stops reading as the carousel
        self.shoot(key)

    def refresh(self, tag):
        self.shoot(tag)

    def read(self):
        kind = {"shooting": "shooting", "menu": "menu", "row": "submenu", "dialog": "dialog", "lost": "unknown"}
        n = len(self.spec.get(self.opt, [])) if self.where == "dialog" and self.field is not None else 0
        return SimpleNamespace(kind=kind[self.where], field=self.field if self.where == "dialog" else None,
                               boxes=[(150 + 100 * i, 240 + 100 * i) for i in range(n)], bar=(351, 406) if n else None)

    def value(self, k):
        b = self.spec[self.opt][k]
        v = b["values"][self.edit[k]]
        return "2 Images" if v in self.same_text else v

    def records(self) -> dict:
        ev, img = self.at[0]
        step, *digits = self.at[2]
        number = int("".join(b["values"][i] for b, i in zip(self.spec[2][1:], digits, strict=True)))
        return {"global:0x02bf": self.saved, "global:0x13f9": 10 * ev + img + 1, "global:0x9001": ev,
                "global:0x9002": step, "global:0x9003": number, **self.extra}


def fields_world(monkeypatch, own_runs, cam):
    """kit/provers/carousel_fields_run.py's seams on a FieldsCam: the screen's readings from the made-up camera (the lit
    box's value, the name above it, the title, each box's picture), the way to the row, the session and the downloads
    (each holds the records as the camera holds them then)."""
    import carousel_fields_run as F
    root = brk_root(own_runs, monkeypatch)
    lit = lambda c: c.where == "dialog" and c.field is not None    # noqa: E731
    downloads = []

    def download(tag):
        downloads.append(tag)
        if getattr(cam, "downloaded", None):          # a test's own change of the camera at a download
            cam.downloaded(tag)
        return SimpleNamespace(name=f"{len(downloads) + 1:05d}_{tag}.DAT", values=cam.records())

    def diff(a, b):
        return [SimpleNamespace(key=k, before=a.values[k], after=b.values[k]) for k in a.values if a.values[k] != b.values[k]]

    @contextlib.contextmanager
    def session(run, eyes, **kw):
        s = SimpleNamespace(cam=cam, link=link, start=SimpleNamespace(name="00001_before.DAT", values=cam.records()))
        held = ({o: list(v) for o, v in cam.at.items()}, cam.saved, dict(cam.extra))
        try:
            yield s
        except Exception as e:                    # runner.prover_session: said, closed, then the restore
            print(f"stopped: {type(e).__name__}: {e}", flush=True)
            cam.closes.append(cam.frame.path.name)
            cam.where = "shooting"
        finally:                                  # the session's end: the start file back on
            cam.at, cam.saved, cam.extra = {o: list(v) for o, v in held[0].items()}, held[1], dict(held[2])

    def enter_any(c, path, start, at=None):
        assert c.where == "menu" and path == ROW
        c.where = "row"

    def to_shooting(link_, eyes, why):
        cam.where, cam.field = "shooting", None

    def close_screen(c, link_):
        c.closes.append(c.frame.path.name)
        c.where, c.field = "shooting", None
    link = SimpleNamespace(download=download)
    for name, value in (
            ("title_reads", lambda c, labels: labels[c.opt] if c.where == "dialog" else None),
            ("lit_read", lambda c, always: F.BoxRead(c.value(c.field), c.value(c.field), c.value(c.field), "made-up", "both")
             if lit(c) else (_ for _ in ()).throw(F.Failed("no box lit"))),
            ("word_read", lambda c: c.spec[c.opt][c.field]["label"]),
            ("box_pic", lambda c, k: (c.opt, k, c.edit[k], c.field == k, c.field if c.lit_moves else None)
             if lit(c) and k < len(c.edit) else None),
            ("same_pic", lambda a, b: a is not None and a == b),
            ("menu_from_shooting", lambda c, **k: setattr(c, "where", "menu")), ("scan_position", lambda c, cycle: 0),
            ("go_to", lambda c, cycle, model, j, row: 0), ("enter_any", enter_any),
            ("place", lambda c: c.read().kind), ("same_place", lambda a, b, tol=2: a == b),
            ("close_screen", close_screen), ("to_shooting", to_shooting), ("wait_lock", lambda since, eyes, clock: None),
            ("camset", SimpleNamespace(read=lambda d: d, diff=diff)), ("prover_session", session),
            ("load_scan", lambda scan: ([], {})), ("eyes_from_config", lambda run: None)):
        monkeypatch.setattr(F, name, value)
    return F, root, downloads


def fields_lines() -> list:
    from camkit.runs import Run
    f = Run("kit2_pass2").dir / "proofs.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def brief(lines) -> list:
    return [(x["index"], x["field"], x["value"], x["label"], x["final"],
             {c["key"]: (c["before"], c["after"]) for c in x["changes"]}) for x in lines]


def run_fields(F, root, *extra):
    F.main(["--row", "Bracket Settings > Bracket Type", "--option", extra[0], "--map", str(root / BRK_MAP),
            "--context", "Drive Mode dial on BRK", "--scan", "made-up", *extra[1:]])


def test_cont_brackets_fields_one_value_a_download(own_runs, monkeypatch, capsys):
    """Cont. Bracket: the look reads its two boxes, then Exposure Value Up from 0.3EV to its top end (one more Up
    changes nothing: no Enter, closed), Down from 0.3EV (its low end at once), and 0.3EV put back; then Number of Shots
    Up to 5 Images (its end), Down to 2 Images (its end), 3 Images put back. One value a download, each line naming the
    field changed, both fields as drawn and their label in the bracket lists' words; the put-backs change nothing."""
    cam = FieldsCam()
    F, root, downloads = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket")
    out = capsys.readouterr().out
    assert "box 0: Exposure Value = '0.3EV'" in out and "together '0.3 EV 3 Img.'" in out
    lines = fields_lines()
    assert brief(lines) == [
        ([0, 1], "Exposure Value", "0.5EV", "0.5 EV 3 Img.", False, {"global:0x13f9": (2, 12), "global:0x9001": (0, 1)}),
        ([0, 2], "Exposure Value", "0.7EV", "0.7 EV 3 Img.", False, {"global:0x13f9": (2, 22), "global:0x9001": (0, 2)}),
        ([0, 3], "Exposure Value", "1.0EV", "1.0 EV 3 Img.", False, {"global:0x13f9": (2, 32), "global:0x9001": (0, 3)}),
        ([0, 0], "Exposure Value", "0.3EV", "0.3 EV 3 Img.", True, {}),
        ([1, 1], "Number of Shots", "5 Images", "0.3 EV 5 Img.", False, {"global:0x13f9": (2, 3)}),
        ([1, -1], "Number of Shots", "2 Images", "0.3 EV 2 Img.", False, {"global:0x13f9": (2, 1)}),
        ([1, 0], "Number of Shots", "3 Images", "0.3 EV 3 Img.", True, {})]
    first = lines[0]
    assert first["path"] == [*ROW, "Cont. Bracket"] and first["kind"] == "list" and first["via"] == F.VIA
    assert first["fields"] == [{"label": "Exposure Value", "value": "0.5EV"}, {"label": "Number of Shots", "value": "3 Images"}]
    assert first["context"] == "Drive Mode dial on BRK" and first["base"] == "00002_Bracket-Type-Cont.-Bracket-base.DAT"
    assert first["read_by"] == "both" and first["applied"] is True and len({x["attempt"] for x in lines}) == 2
    assert len(downloads) == 1 + len(lines), "one download a value, and the base"
    assert "Up ['0.5EV', '0.7EV', '1.0EV']; Down []" in out and "Up ['5 Images']; Down ['2 Images']" in out
    assert cam.at[0] == [0, 1] and cam.saved == 0


def test_the_report_credits_a_record_of_both_fields_and_one_of_one(own_runs, monkeypatch, capsys):
    """kit/pass2_report.py on those lines: the record both fields' lines move is credited value by value with both
    fields together, in the Drive Mode bracket lists' words (the put-backs give the value held, the record's before);
    the record only Exposure Value's lines move with that field's value as drawn."""
    import pass2_report as R
    cam = FieldsCam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket")
    rows = R.rows_of(root / "kit2_pass2", fields_lines())
    name = "Bracket Settings > Bracket Type > Cont. Bracket [Drive Mode dial on BRK]"
    assert list(rows) == [name]
    sources = {}
    got = R.values_of(rows[name], sources=sources)
    assert got == {"global:0x13f9": {"0.5 EV 3 Img.": 12, "0.7 EV 3 Img.": 22, "1.0 EV 3 Img.": 32, "0.3 EV 3 Img.": 2,
                                     "0.3 EV 5 Img.": 3, "0.3 EV 2 Img.": 1},
                   "global:0x9001": {"0.5EV": 1, "0.7EV": 2, "1.0EV": 3, "0.3EV": 0}}
    assert set(sources["global:0x13f9"].values()) == {"two readers"}
    # each field walked from what the other held: 0x13f9's values cross at the pair held, which the definition must not
    # tell (decision 16), so it counts them; the step's own record, walked whole, lists its values
    assert R.option_fields_sampled(rows[name]) == {"global:0x13f9"}


def test_a_walk_the_deadline_cuts_credits_no_value_held(own_runs, monkeypatch, capsys):
    """--most 2: Exposure Value Up to 0.7EV, then the deadline; Down finds its low end; 0.3EV put back, its line saying the
    walk was not whole. The report credits 0.5EV's and 0.7EV's values, never the value held, and marks the records
    sampled; Number of Shots never walked, both records are credited with the fields together."""
    import pass2_report as R
    cam = FieldsCam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--box", "0", "--most", "2")
    lines = fields_lines()
    assert [(x["index"], x["value"], x["final"], x.get("whole")) for x in lines] == [
        ([0, 1], "0.5EV", False, None), ([0, 2], "0.7EV", False, None), ([0, 0], "0.3EV", True, False)]
    assert "the deadline (--most): its top end not reached" in capsys.readouterr().out
    opts = R.rows_of(root / "kit2_pass2", lines)["Bracket Settings > Bracket Type > Cont. Bracket [Drive Mode dial on BRK]"]
    assert R.values_of(opts) == {"global:0x13f9": {"0.5 EV 3 Img.": 12, "0.7 EV 3 Img.": 22},
                                 "global:0x9001": {"0.5 EV 3 Img.": 1, "0.7 EV 3 Img.": 2}}
    assert R.option_fields_sampled(opts) == {"global:0x13f9", "global:0x9001"}


def test_focus_brackets_digits_make_one_number(own_runs, monkeypatch, capsys):
    """Focus Bracket: Step Width, then the number of shots in three digit boxes, one field; each digit box walked Up
    until it comes round to the digit it held, which is then the put-back (no Down: it never stopped); each line's value
    the number the three digits make, the label both fields joined as drawn. The report credits Step Width's record and
    the number's record each with its own field's values."""
    import pass2_report as R
    cam = FieldsCam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Focus Bracket")
    lines = fields_lines()
    assert [(x["index"], x["value"], x["label"], x["final"]) for x in lines] == [
        ([0, 1], "5", "5 | 3", False), ([0, -1], "3", "3 | 3", False), ([0, 0], "4(Standard)", "4(Standard) | 3", True),
        ([1, 1], "103", "4(Standard) | 103", False), ([1, 0], "3", "4(Standard) | 3", True),
        ([2, 1], "13", "4(Standard) | 13", False), ([2, 2], "23", "4(Standard) | 23", False),
        ([2, 0], "3", "4(Standard) | 3", True),
        ([3, 1], "4", "4(Standard) | 4", False), ([3, 2], "1", "4(Standard) | 1", False),
        ([3, 3], "2", "4(Standard) | 2", False), ([3, 0], "3", "4(Standard) | 3", True)]
    assert all(x["field"] == "Number of Shots" for x in lines[3:])
    assert all(c["key"] != "global:0x02bf" for x in lines for c in x["changes"]), "the option's own record: the base's"
    assert all(x["base"] == "00002_Bracket-Type-Focus-Bracket-base.DAT" for x in lines)
    got = R.values_of(R.rows_of(root / "kit2_pass2", lines)[
        "Bracket Settings > Bracket Type > Focus Bracket [Drive Mode dial on BRK]"])
    assert got == {"global:0x9002": {"5": 2, "3": 0, "4(Standard)": 1},
                   "global:0x9003": {"103": 103, "3": 3, "13": 13, "23": 23, "4": 4, "1": 1, "2": 2}}


def test_a_screen_that_stops_reading_as_the_box_stops_the_row_before_the_next_key(own_runs, monkeypatch, capsys):
    """The screen reads as no known kind after the second Up: the row stops there, no key after it but the close's MENU,
    no Enter on it, the run exits as a failure once the session has restored."""
    import boxes_run
    cam = FieldsCam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.lost = ("up", 2)
    with pytest.raises(SystemExit) as stop:
        run_fields(F, root, "Cont. Bracket")
    assert stop.value.code == boxes_run.EXIT_INCOMPLETE
    out = capsys.readouterr().out
    assert "after Up on box 0: the screen reads as unknown, not the carousel" in out
    assert cam.keys[-1] == "up" and cam.keys.count("up") == 2 and cam.closes[-1] == cam.frame.path.name
    assert [x["index"] for x in fields_lines()] == [[0, 1]], "the one value chosen before it"


def test_the_fields_are_entered_only_on_the_option_named_and_never_past_the_last_box(own_runs, monkeypatch):
    cam = FieldsCam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.where, cam.opt = "dialog", 1                                   # Single Bracket lit, not Cont. Bracket
    with pytest.raises(F.Failed, match=r"Cont\. Bracket: no Right into its boxes: its title names 'Single Bracket'"):
        F.into_box(cam, "Cont. Bracket", OPTIONS, 0, 2)
    assert cam.keys == []
    cam.opt, cam.field = 0, 1                                          # a box lit: not the option
    with pytest.raises(F.Failed, match="box 1 is lit, not the option"):
        F.into_box(cam, "Cont. Bracket", OPTIONS, 0, 2)
    cam.field = None
    with pytest.raises(F.Failed, match="no Right to box 2: box 1 of 2 is lit"):
        F.into_box(cam, "Cont. Bracket", OPTIONS, 2, 2)
    assert cam.keys == ["right", "right"] and cam.field == 1


def test_enter_goes_only_on_the_value_read_and_a_value_read_twice_stops_the_row(own_runs, monkeypatch):
    """Enter on a box that no longer reads the value meant is refused, nothing pressed. Two values the readers read
    alike (a pair of 2 Images told apart only by an icon) stop the walk before any Enter on the second."""
    cam = FieldsCam(same_text={"2 Images", "5 Images"})
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.where, cam.opt, cam.field, cam.edit = "dialog", 0, 1, [0, 1]
    with pytest.raises(F.Failed, match="no Enter: box 1 no longer reads '5 Images'"):
        F.enter(cam, "Cont. Bracket", OPTIONS, 1, 2, "5 Images")
    assert "enter" not in cam.keys
    cam.where, cam.field = "shooting", None
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--box", "1")
    lines = fields_lines()
    assert [x["value"] for x in lines] == ["2 Images"], "5 Images (read '2 Images') chosen, the next read alike refused"


@pytest.mark.parametrize("ocr_text, said, always, got", [
    ("3 Images", None, False, ("3 Images", "ocr")),             # plain: OCR alone, no reader asked
    ("0.,ЗEV", "0.3EV", False, ("0.3EV", "reader")),           # OCR unsure (a Cyrillic Ze for the 3): the reader's
    ("0", "0", True, ("0", "reader")),                          # a lone digit is no plain reading
    ("5 Images", "5 Images", True, ("5 Images", "both")),       # a value a proof rides on: the reader always, agreeing
    ("5 mages", "5 Images", True, ("5 Images", "both")),        # OCR's dropped letter (kit2_fin_brtype_cont_img 00008)
    ("5 Images", "7 Images", True, "OCR read '5 Images' and the second reader '7 Images'"),
    ("0.", None, True, "did not answer")])
def test_the_lit_box_is_read_by_ocr_and_the_reader_where_ocr_is_unsure(monkeypatch, ocr_text, said, always, got):
    import carousel_fields_run as F
    from camkit.ocr import Line
    cam = SimpleNamespace(frame=SimpleNamespace(path=Path("00009_up.png"), image=None),
                          read=lambda: SimpleNamespace(kind="dialog", field=0, boxes=[(137, 345)], bar=(351, 406)))
    asked = []
    monkeypatch.setattr(F, "lines", lambda c: [Line(ocr_text, 1.0, 180, 360, 120, 30)])
    monkeypatch.setattr(F, "box_answer", lambda c: asked.append(1) or (said, "made-up", False))
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    if isinstance(got, str):
        with pytest.raises(F.Failed, match=got):
            F.lit_read(cam, always)
        return
    r = F.lit_read(cam, always)
    assert (r.text, r.by) == got and r.ocr == ocr_text
    assert bool(asked) == (got[1] != "ocr")


# the third role's readers where OCR's plain reading and the second reader's are two numbers (box_vote), and OCR's bullet
# for the minus sign, kit2_pass2 266268 (2026-11-20), a doubt (box_doubts); the models as the a1 II's readers name them,
# the first two families apart
SECOND, GEMMA, GLM = "RedHatAI/Qwen3.8-27B-INT4", "google/gemma-4-26b-it", "zai/GLM-4.6V-Flash"
MINUS, PLUS, BULLET = "2 Images (-)", "2 Images (+)", "2 Images (\u2022)"


def voting_cam(eyes, monkeypatch, ocr_text, second, voters):
    """lit_read's world for a vote: a frame with bytes of its own (the eyes fixture), OCR reading ocr_text in the lit box,
    the second reader reading second (box_answer), and the third role's readers `voters`, [(model, its reading, or an
    exception: no answer)], in the order private/config.json would give them."""
    import carousel_fields_run as F
    from camkit import vlm
    from camkit.ocr import Line
    cam = SimpleNamespace(frame=eyes.frame("266268_up.png"),
                          read=lambda: SimpleNamespace(kind="dialog", field=1, boxes=[(137, 345), (354, 563)],
                                                       bar=(351, 405)))
    monkeypatch.setattr(F, "lines", lambda c: [Line(ocr_text, 1.0, 380, 360, 160, 30)])
    monkeypatch.setattr(F, "box_answer", lambda c: (second, "vllm", False))
    monkeypatch.setattr(F.time, "sleep", lambda s: None)
    monkeypatch.setattr(vlm, "answered_by", lambda: None)
    eyes.models = {"second": SECOND}
    for k, (model, said) in enumerate(voters):
        eyes.models[vlm.voter_key(k)] = model
        eyes.answer("box", said if isinstance(said, BaseException) else {"value": said}, role=vlm.voter_key(k))
    return F, cam


def test_the_third_readers_settle_ocr_and_the_second_reader_apart(eyes, monkeypatch):
    """OCR's plain "2 Images (+)", the second reader "2 Images (-)": the third readers asked the second reader's own box
    question, in turn while no reading stands; the first agreeing with the second reader makes two model families against
    OCR's one, the kit's rule (camkit.reading.tally), so the second is not asked. The reading taken says so ("votes"), and
    the proof line keeps every vote with its reader's model."""
    F, cam = voting_cam(eyes, monkeypatch, PLUS, MINUS, [(GEMMA, MINUS), (GLM, MINUS)])
    r = F.lit_read(cam, True)
    assert (r.text, r.by, r.ocr, r.vlm, r.reader) == (MINUS, "votes", PLUS, MINUS, "vllm")
    assert [(v["eye"], v["model"], v["text"]) for v in r.votes] == [
        ("ocr", None, PLUS), ("reader", SECOND, MINUS), ("third", GEMMA, MINUS)]
    assert eyes.asked == ["third box"]
    assert F.votes_of(r) == {"box_votes": list(r.votes)} and F.votes_of(F.BoxRead(MINUS, MINUS)) == {}


def test_a_third_reader_that_does_not_answer_casts_no_vote(eyes, monkeypatch):
    from camkit import vlm
    F, cam = voting_cam(eyes, monkeypatch, PLUS, MINUS, [(GEMMA, vlm.NoReader("down")), (GLM, MINUS)])
    r = F.lit_read(cam, True)
    assert (r.text, r.by) == (MINUS, "votes") and eyes.asked == ["third box", "third.2 box"]
    assert r.votes[2]["text"] is None and r.votes[2]["why"] and r.votes[3]["model"] == GLM


@pytest.mark.parametrize("voters, asked", [
    ([(GEMMA, "3 Images"), (GLM, "2 Images")], ["third box", "third.2 box"]),   # split, each backing neither reading
    ([(GEMMA, "2 Images"), (GLM, "2 Images")], ["third box", "third.2 box"]),   # agreed on a reading neither gave
    ([("mlx-community/Qwen3.8-27B-4bit", MINUS)], []),                           # the second reader's family: never asked
    ([], [])])                                                                   # no third reader
def test_a_vote_that_settles_nothing_stops_the_row_as_before(eyes, monkeypatch, voters, asked):
    import re
    F, cam = voting_cam(eyes, monkeypatch, PLUS, MINUS, voters)
    with pytest.raises(F.Failed, match=re.escape(f"OCR read {PLUS!r} and the second reader {MINUS!r}: the kit does "
                                                 "not guess which")):
        F.lit_read(cam, True)
    assert eyes.asked == asked


def test_ocr_and_the_second_reader_agreeing_ask_nobody_else(eyes, monkeypatch):
    F, cam = voting_cam(eyes, monkeypatch, "2 mages (-)", MINUS, [(GEMMA, PLUS), (GLM, PLUS)])
    r = F.lit_read(cam, True)
    assert (r.text, r.by, r.votes) == (MINUS, "both", ()) and eyes.asked == []


@pytest.mark.parametrize("ocr_text, second, asked, got", [
    (BULLET, MINUS, ["second"], (MINUS, "reader")),      # the bullet, a doubt: the second reader's reading, no vote
    ("2 mages (-)", MINUS, [], ("2 mages (-)", "ocr")),  # a clean reading: nobody asked
    (PLUS, MINUS, [], (PLUS, "ocr"))])                    # plain: OCR alone, as before
def test_a_read_with_ocr_alone_doubts_the_bullet(eyes, monkeypatch, ocr_text, second, asked, got):
    """OCR's bullet in a lit box is never what the camera draws there (BOX_MISREADS): a read with OCR alone (lit_read's
    False: the navigation checks) asks the second reader instead of taking "2 Images (bullet)" for another value."""
    F, cam = voting_cam(eyes, monkeypatch, ocr_text, second, [(GEMMA, MINUS)])
    called = []
    monkeypatch.setattr(F, "box_answer", lambda c: called.append("second") or (second, "vllm", False))
    r = F.lit_read(cam, False)
    assert (r.text, r.by) == got and called == asked and eyes.asked == []
    assert F.box_doubts(BULLET) and not F.box_doubts(MINUS)


@pytest.mark.parametrize("ocr_text, second, voter, pressed", [
    (BULLET, MINUS, MINUS, True),        # the bullet doubted: the second reader's "2 Images (-)" stands
    (PLUS, MINUS, MINUS, True),          # OCR's plain "(+)" outvoted
    (PLUS, MINUS, PLUS, False)])         # OCR and a voter on "(+)": the reading that stands is another value
def test_enter_goes_only_where_the_reading_that_stands_is_the_value_chosen(eyes, monkeypatch, ocr_text, second, voter,
                                                                           pressed):
    """The check before Enter on a box reads it by both readers (lit_read's True) and the vote where they differ: OCR
    alone refused an Enter on a misread frame. A reading that stands on another value refuses the Enter, as before."""
    F, cam = voting_cam(eyes, monkeypatch, ocr_text, second, [(GEMMA, voter)])
    keys = []
    cam.refresh = lambda tag, frame=None: None
    cam.press = keys.append
    pic = F.box_pic(cam, 1)
    if pressed:
        assert F.enter(cam, "Cont. Bracket", [], 1, 2, MINUS, pic) == "266268_up.png" and keys == ["enter"]
    else:
        with pytest.raises(F.Failed, match=r"no Enter: box 1 no longer reads '2 Images \(-\)'"):
            F.enter(cam, "Cont. Bracket", [], 1, 2, MINUS, pic)
        assert keys == []


@pytest.mark.parametrize("a, b, same", [("0.5EV", "0.5 EV", True), ("5 mages", "5 Images", True),
                                        ("4 (Standard)", "4(Standard)", True), ("2 Images +", "2 Images −", False),
                                        ("0.3EV", "0.5EV", False), ("0", "0", True), ("1", "10", False)])
def test_two_readings_of_a_value_are_one_by_its_number(a, b, same):
    import carousel_fields_run as F
    assert (F.key(a) == F.key(b)) is same


@pytest.mark.parametrize("labels, values, fields, label", [
    (["Exposure Value", "Number of Shots"], ["0.5EV", "3 Images"],
     [{"label": "Exposure Value", "value": "0.5EV"}, {"label": "Number of Shots", "value": "3 Images"}], "0.5 EV 3 Img."),
    (["Exposure Value", "Number of Shots"], ["1.0EV", "2 Images +"], None, "1.0 EV 2 Img. +"),
    (["Step Width", "Number of Shots", "Number of Shots", "Number of Shots"], ["10", "2", "9", "9"],
     [{"label": "Step Width", "value": "10"}, {"label": "Number of Shots", "value": "299"}], "10 | 299"),
    (["Step Width", "Number of Shots", "Number of Shots", "Number of Shots"], ["4(Standard)", "0", "0", "1"], None,
     "4(Standard) | 1")])
def test_fields_and_their_label(labels, values, fields, label):
    import carousel_fields_run as F
    got = F.fields_of(labels, values)
    assert fields is None or got == fields
    assert F.together(got) == label


# ------------------------------------------------------------------------------------- the review of 2026-11-19

CTX = "Drive Mode dial on BRK"


def shaped(option, box_, place, field, value, label, changes, final=False, attempt="kit2_pass2-a", n=1, **extra):
    """A carousel-fields line as kit/provers/carousel_fields_run.py writes it on the camera (kit2_pass2, 2026-11-19)."""
    other = {"Exposure Value": "Number of Shots", "Number of Shots": "Exposure Value"}
    fields = sorted([{"label": field, "value": value}, {"label": other.get(field, "Step Width"), "value": "3 Images"}],
                    key=lambda f: f["label"] != "Exposure Value")
    return {"path": [*ROW, option], "kind": "list", "via": "a carousel option's own fields", "index": [box_, place],
            "field": field, "value": value, "label": label, "fields": fields, "box": value, "read_by": "both",
            "shown": value, "box_vlm": value, "box_reader": "vllm", "chosen_frame": f"{263000 + n}_up.png",
            "row_frame": f"{263001 + n}_enter.png", "dat": f"{263002 + n:06d}_Bracket-Type-{box_}-{place}.DAT",
            "base": "262990_Bracket-Type-Cont.-Bracket-base.DAT", "applied": True, "final": final,
            **({"whole": True} if final else {}), "attempt": attempt,
            "changes": [{"key": k, "before": b, "after": a} for k, b, a in changes], "context": CTX, **extra}


def cont_lines() -> list:
    return [shaped("Cont. Bracket", 0, 1, "Exposure Value", "0.5EV", "0.5 EV 3 Img.", [("global:0x13f9", 3, 9)], n=1),
            shaped("Cont. Bracket", 0, 0, "Exposure Value", "0.3EV", "0.3 EV 3 Img.", [], True, n=4),
            shaped("Cont. Bracket", 1, 1, "Number of Shots", "5 Images", "0.3 EV 5 Img.", [("global:0x13f9", 3, 4)],
                   attempt="kit2_pass2-b", n=7),
            shaped("Cont. Bracket", 1, 0, "Number of Shots", "3 Images", "0.3 EV 3 Img.", [], True, attempt="kit2_pass2-b",
                   n=10)]


def test_schema_updates_refused_options_take_carousel_fields_lines(tmp_path):
    """schema_update.blocked keyed a line by its index, and a carousel-fields line's index is a list [box, place]: the
    whole pass stopped on TypeError, with or without --write. A line the camera did not keep ("kept") is no refusal of
    the menu's either."""
    import schema_update as S
    run = tmp_path / "kit2_pass2"
    run.mkdir()
    refused = shaped("Cont. Bracket", 1, 3, "Number of Shots", "9 Images", "0.3 EV 9 Img.", [], n=13,
                     notice={"text": "Not available as follows Drive Mode", "frame": "x.png"})
    refused["applied"] = False
    kept = shaped("Focus Bracket", 3, 7, "Number of Shots", "0", "4(Standard) | 0", [("global:0x10aa", 3, 2)], n=16,
                  asked="0", kept="2")
    kept["applied"] = False
    run.joinpath("proofs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in cont_lines() + [refused, kept]),
                                            encoding="utf-8")
    got = S.blocked(run)
    assert dict(got) == {"Bracket Settings > Bracket Type > Cont. Bracket": [
        ("0.3 EV 9 Img.", "Not available as follows Drive Mode")]}, "the refusal alone; the value kept as 2 is none"


@needs_evidence
def test_the_a1_pass_looks_over_carousel_fields_lines(tmp_path, monkeypatch, capsys):
    """schema_update's full pass for the a1 II, as a look (no --write), over a report and proofs holding Cont. Bracket's
    carousel-fields lines as the camera wrote them: the whole writer reads them, nothing stops."""
    import test_definitions as D
    report = D.A1_REPORT + [{"row": f"Bracket Settings > Bracket Type > Cont. Bracket [{CTX}]", "options": 4,
                             "kinds": ["list"], "notices": [], "records": {"global:0x13f9": {
                                 "verdict": "new", "schema_name": None, "linear": None, "notes": [],
                                 "proved": {"0.5 EV 3 Img.": 9, "0.3 EV 3 Img.": 3, "0.3 EV 5 Img.": 4},
                                 "names": {"0.5 EV 3 Img.": "two readers", "0.3 EV 3 Img.": "two readers",
                                           "0.3 EV 5 Img.": "two readers"},
                                 "sampled_from_start": True, "sample_proofs": 2}}}]
    S, target, write = D.a1_run(tmp_path, monkeypatch, report, D.A1_PROOFS + cont_lines())
    monkeypatch.setattr(sys, "argv", ["schema_update.py"])
    said = write(capsys)
    assert "Traceback" not in said and f"wrote {target}" not in said


def counted_rows(root: Path) -> dict:
    """The report's rows of the run's lines as the report counts them: the attempts that did not finish left out."""
    import pass2_report as R
    run = root / "kit2_pass2"
    proofs = fields_lines()
    return R.rows_of(run, proofs, R.unfinished(proofs, R.attempts_done(run), {}))


CONT_ROW = f"Bracket Settings > Bracket Type > Cont. Bracket [{CTX}]"
COUNTS_HELD_AT_03 = {"0.3 EV 5 Img.": 3, "0.3 EV 2 Img.": 1, "0.3 EV 3 Img.": 2}


def test_a_record_with_one_field_cut_and_the_other_finished_holds_both(own_runs, monkeypatch, capsys):
    """Single Bracket on the camera, 2026-11-19: Exposure Value's walk was cut before its put-back (its attempt never
    finished, its lines left out), and a later --box 1 run finished Number of Shots. The record moved only with Number
    of Shots' counted lines, but Exposure Value never had a finished walk, so nothing says the record leaves it out:
    it is credited with both fields together ("0.3 EV 5 Img.", the step held in every label) and marked sampled, never
    "5 Images" (the wrong names, and one arm of the cross that tells the step held, decision 16)."""
    import pass2_report as R
    cam = FieldsCam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.lost = ("up", 3)                          # the link stalls on Exposure Value's third value
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--box", "0")
    cam.lost = None
    run_fields(F, root, "Cont. Bracket", "--box", "1")
    rows = counted_rows(root)
    assert {x["field"] for x in rows[CONT_ROW].values()} == {"Number of Shots"}, "Exposure Value's lines left out"
    assert R.values_of(rows[CONT_ROW]) == {"global:0x13f9": COUNTS_HELD_AT_03}
    assert R.option_fields_sampled(rows[CONT_ROW]) == {"global:0x13f9"}


def test_a_record_of_one_field_alone_ever_walked_holds_both(own_runs, monkeypatch, capsys):
    """--box 1 alone: Exposure Value never walked, so the record Number of Shots moves holds both, as above."""
    import pass2_report as R
    cam = FieldsCam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--box", "1")
    rows = counted_rows(root)
    assert R.values_of(rows[CONT_ROW]) == {"global:0x13f9": COUNTS_HELD_AT_03}
    assert R.option_fields_sampled(rows[CONT_ROW]) == {"global:0x13f9"}


def test_the_reports_entry_counts_no_put_back_among_the_samples(tmp_path):
    """The report written whole (pass2_report.py --no-schema) over real-shaped lines of Number of Shots alone: the
    record holds both fields, marked sampled, its sample_proofs the one value chosen for its own sake, never the
    put-back."""
    import subprocess

    import test_definitions as D
    lines = cont_lines()[2:]
    run = D.write_run(tmp_path, lines, done=["kit2_pass2-b"])
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(run), "--no-schema"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    (entry,) = json.loads((run / "report.json").read_text(encoding="utf-8"))
    rec = entry["records"]["global:0x13f9"]
    assert entry["row"] == CONT_ROW and rec["proved"] == {"0.3 EV 5 Img.": 4, "0.3 EV 3 Img.": 3}
    assert rec["sampled_from_start"] is True and rec["sample_proofs"] == 1


def brk_axis_lines() -> list:
    """Bracket Type's lines as kit2_pass2 holds them (2026-11-19): its five options proved with the dial on BRK, then
    White Balance Bracket's and DRO Bracket's Lo/Hi, each Hi with the option's record and the axis's own."""
    main = [{"path": ROW, "kind": "dialog", "index": i, "label": lab, "shown": lab, "vlm": lab, "chosen_frame": "x.png",
             "row_frame": "y.png", "dat": f"{262940 + 9 * i}_Bracket-Type-{i}.DAT", "base": "262930_before.DAT",
             "changes": [{"key": "global:0x02bf", "before": 0, "after": i}] if i else [], "notice": None,
             "applied": True, "attempt": "kit2_pass2-main", "context": CTX}
            for i, lab in [(1, "Single Bracket"), (2, "Focus Bracket"), (3, WB[0]), (4, DRO[0]), (0, "Cont. Bracket")]]
    axes = []
    for opt, vals, code, key, n in (("White Balance Bracket", WB, 3, "global:0x13f3", 0),
                                    ("DRO Bracket", DRO, 4, "global:0x13f5", 2)):
        for k, final, changes in ((1, False, [("global:0x02bf", 0, code), (key, 1, 0)]), (0, True, [])):
            axes.append({"path": ROW, "kind": "axis", "option": opt, "index": k, "label": vals[k], "shown": vals[k],
                         "final": final, "chosen_frame": "x.png", "vlm": vals[k], "row_frame": "y.png",
                         "dat": f"{263500 + n + (1 - k)}_Bracket Type-axis-{k}.DAT", "base": "263490_before.DAT",
                         "notice": None, "applied": True, "context": CTX,
                         "changes": [{"key": a, "before": b, "after": c} for a, b, c in changes]})
    return main + axes


@pytest.mark.parametrize("option, key, vals, code", [("White Balance Bracket", "global:0x13f3", WB, 3),
                                                     ("DRO Bracket", "global:0x13f5", DRO, 4)])
def test_an_axis_of_a_submenu_row_with_a_context_credits_its_record(tmp_path, option, key, vals, code):
    """The axis row "Bracket Settings > Bracket Type / White Balance Bracket [Drive Mode dial on BRK]" found no carousel
    row of its own (own_records took the space before " [" with the option), and the row opens only on BRK, so no row
    without the context stood in: it credited nothing ("changed nothing ... (2 options)"). The carousel's row in the
    same context is found now: Bracket Type's record is the option's own, the axis's record is credited Hi and Lo."""
    import pass2_report as R
    lines = brk_axis_lines()
    rows = R.rows_of(tmp_path, lines)
    name = f"{' > '.join(ROW)} / {option} [{CTX}]"
    assert R.own_records(rows, name, rows[name]) == {"global:0x02bf": code}
    recs = R.row_values(rows, name, rows[name], {}, {}, frozenset(), frozenset(), frozenset())[0]
    assert recs == {key: {vals[1]: 0, vals[0]: 1}}


# 0x13f9's report entry as the camera's proofs give it: each field walked from the pair held, the values cross at 3
CROSS = {"0.5 EV 3 Img.": 9, "0.7 EV 3 Img.": 16, "1.0 EV 3 Img.": 23, "0.3 EV 3 Img.": 3, "0.3 EV 5 Img.": 4,
         "0.3 EV 7 Img.": 5, "0.3 EV 2 Img. -": 2}
CROSS_ENTRY = {"row": CONT_ROW, "options": 8, "kinds": ["list"], "notices": []}
CROSS_RECORD = {"verdict": "new", "schema_name": None, "linear": None, "notes": [], "proved": dict(CROSS),
                "names": dict.fromkeys(CROSS, "two readers"), "sampled_from_start": True, "sample_proofs": 6}


def sibling_04c6() -> dict:
    import test_definitions as D
    return next(s for s in D.DOC["settings"] if s["key"] == "global:0x04c6")


def test_a_sampled_record_laid_out_like_its_sibling_takes_the_siblings_names_alone():
    """hand_facts.like_setting named a record laid out like its sibling from the codes its proofs credited: 0x13f9 like
    0x04c6 would list 2, 3, 4, 5, 9, 16, 23, the cross centred on 3, the pair held (decision 16). A record marked
    sampled_from_start takes its names from the sibling's list alone; one not so marked is named from its proofs as
    before."""
    import test_definitions as D
    from writer import hand_facts
    sib = sibling_04c6()
    table = {"global:0x13f9": ("global:0x04c6", "Drive memory - continuous bracket setting (BRK)")}
    s = hand_facts.like_setting("global:0x13f9", {"global:0x04c6": sib}, CROSS_ENTRY, CROSS_RECORD, table, set(),
                                D.SAMPLE, "kit2_pass2")
    assert s["values"] == sib["values"] and len(s["values"]) > len(CROSS)
    plain = dict(CROSS_RECORD, sampled_from_start=False)
    named = hand_facts.like_setting("global:0x13f9", {"global:0x04c6": sib}, CROSS_ENTRY, plain, table, set(), D.SAMPLE,
                                    "kit2_pass2")
    assert {v for v, _ in named["values"]} == set(CROSS.values())


def test_the_plain_pass_lays_a_sampled_record_out_with_the_siblings_names_and_counts_its_proofs(tmp_path, monkeypatch):
    """writer/generic.lay_like (the plain pass's layout of a NEW_LIKE record, through like_setting and like_more): a
    sampled record of two rows keeps the sibling's names, never a label of either row's proofs, every value derived."""
    import collections

    import test_definitions as D
    from writer import generic, hand_facts
    sib = sibling_04c6()
    doc = {"settings": [json.loads(json.dumps(sib))]}
    by_key = {"global:0x04c6": doc["settings"][0]}
    tables = SimpleNamespace(NEW_LIKE={"global:0x13f9": ("global:0x04c6", "Drive memory - continuous bracket setting (BRK)")},
                             NEW_WHOLE_LABELS=set(), RECORD_FIXES={})
    monkeypatch.setattr(hand_facts, "run_start", lambda root, run: D.SAMPLE)
    other = dict(CROSS_RECORD, proved={"0.3 EV 9 Img.": 6, "0.3 EV 3 Img.": 3})
    rows = [(CROSS_ENTRY, CROSS_RECORD, CONT_ROW), (CROSS_ENTRY, other, CONT_ROW)]
    derived, changed = collections.defaultdict(dict), []
    generic.lay_like(doc, by_key, "global:0x13f9", rows, tables, tmp_path / "kit2_pass2", None, 0, derived, changed)
    s = by_key["global:0x13f9"]
    assert s["values"] == sib["values"]
    assert set(derived["global:0x13f9"]) == {v for v, _ in sib["values"]}, "no value named as proved by these lines"
    s["values"] = [[v, lab] for v, lab in s["values"] if v not in (6, 9)]
    generic.like_more(s, CROSS_ENTRY, other, False)
    assert {v for v, _ in s["values"]} == {v for v, _ in sib["values"]} - {6, 9}, "like_more names nothing from a sample"


@needs_evidence
def test_the_a1_pass_counts_a_sampled_new_like_record_and_lists_none_of_its_values(tmp_path, monkeypatch, capsys):
    """schema_update's a1 pass, its NEW_LIKE branch: 0x13f9 laid out like 0x04c6 from a sampled entry gets the sibling's
    names and a count of its proofs ("sampled", "from_start"), never the codes the cross proved."""
    import test_definitions as D
    report = D.A1_REPORT + [dict(CROSS_ENTRY, records={"global:0x13f9": dict(CROSS_RECORD)})]
    S, target, write = D.a1_run(tmp_path, monkeypatch, report, D.A1_PROOFS + cont_lines())
    # the committed definition holds 0x13f9 since the proofs of 2026-11-19: taken out of the copy and its evidence, so
    # the pass lays it out afresh from the entry above
    from camkit import definitions
    pub = json.loads(target.read_text(encoding="utf-8"))
    pub["settings"] = [x for x in pub["settings"] if x["key"] != "global:0x13f9"]
    target.write_text(json.dumps(pub, indent=1, ensure_ascii=False), encoding="utf-8")
    ev = json.loads(definitions.evidence_path(target).read_text(encoding="utf-8"))
    ev["settings"].pop("global:0x13f9", None)
    definitions.evidence_path(target).write_text(json.dumps(ev, indent=1), encoding="utf-8")
    S._hand()
    monkeypatch.setitem(S.NEW_LIKE, "global:0x13f9", ("global:0x04c6", "Drive memory - continuous bracket setting (BRK)"))
    monkeypatch.setattr(S, "run_start", lambda: D.SAMPLE)
    said = write(capsys)
    assert f"wrote {target}" in said
    doc = definitions_load(target)
    s = next(x for x in doc["settings"] if x["key"] == "global:0x13f9")
    assert s["values"] == sibling_04c6()["values"]
    assert s["proved"].get("sampled") == {"proofs": 6, "linear": None, "from_start": True} and "values" not in s["proved"]


def definitions_load(target):
    from camkit import definitions
    return definitions.load(target)


# ------------------------------------------------------------------------------------- the prover's guards, each pinned

def on_box(cam, opt=0, field=0, edit=(0, 1)):
    cam.where, cam.opt, cam.field, cam.edit = "dialog", opt, field, list(edit)


def test_no_up_or_down_unless_the_box_meant_is_lit(own_runs, monkeypatch):
    cam = FieldsCam()
    F, _, _ = fields_world(monkeypatch, own_runs, cam)
    on_box(cam, field=1)
    with pytest.raises(F.Failed, match="no Up: box 1 is lit, not box 0"):
        F.step(cam, "Cont. Bracket", 0, 2, "up")
    assert cam.keys == []


def test_no_enter_on_a_box_whose_title_no_longer_names_the_option(own_runs, monkeypatch):
    cam = FieldsCam()
    F, _, _ = fields_world(monkeypatch, own_runs, cam)
    on_box(cam, edit=(1, 1))
    monkeypatch.setattr(F, "title_reads", lambda c, labels: "Single Bracket")
    with pytest.raises(F.Failed, match="no Enter: its title no longer names 'Cont. Bracket'"):
        F.enter(cam, "Cont. Bracket", OPTIONS, 0, 2, "0.5EV", F.box_pic(cam, 0))
    assert "enter" not in cam.keys


def test_a_box_opening_on_another_value_than_the_last_ok_chose_stops_the_walk(own_runs, monkeypatch, capsys):
    """After the 0.5EV proof the camera holds 1.0EV (made up), and no record bears the box out: the next visit stops
    on opening, before any key in the box, and the 0.5EV line says what applied is not known."""
    cam = FieldsCam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.downloaded = lambda tag: tag == "Bracket-Type-0-1" and cam.at[0].__setitem__(0, 3)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--box", "0")
    assert "box 0 opened on '1.0EV', not '0.5EV', which the last OK chose" in capsys.readouterr().out
    assert cam.keys[-1] == "right" and [x.get("applied") for x in fields_lines()] == [None]


def test_a_put_back_that_leaves_a_record_changed_stops_the_row(own_runs, monkeypatch, capsys):
    cam = FieldsCam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.extra = {"global:0x9009": 0}
    cam.downloaded = lambda tag: tag == "Bracket-Type-0-0" and cam.extra.__setitem__("global:0x9009", 1)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--box", "0", "--most", "1")
    assert "box 0 back on '0.3EV', 1 records still differ from the base" in capsys.readouterr().out
    from camkit.runs import Run
    assert not (Run("kit2_pass2").dir / "attempts.jsonl").exists(), "the attempt never finished"


def test_a_press_that_stood_still_and_then_moved_stops_the_walk(own_runs, monkeypatch, capsys):
    """The first Up goes unanswered (a fresh look shows it so), the confirming Up moves the box: a press was lost, the
    walk stops before anything is chosen."""
    cam = FieldsCam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.drop = ("up", 1)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--box", "0")
    assert "box 0 stood still on one Up and moved on the next" in capsys.readouterr().out
    assert fields_lines() == [] and cam.keys.count("enter") == 1, "the base's Enter alone"


def test_the_title_is_read_once_it_has_settled(monkeypatch):
    """The title redraws after the strip: title_reads waits for it (proving.screens.title_settled) before reading."""
    import carousel_fields_run as F
    said = []
    monkeypatch.setattr(F, "title_settled", lambda cam: said.append("settled"))
    monkeypatch.setattr(F, "carousel_text", lambda cam: said.append("read") or "Single Bracket")
    assert F.title_reads(SimpleNamespace(), OPTIONS) == "Single Bracket" and said == ["settled", "read"]


def test_enter_judges_the_box_on_a_fresh_frame(own_runs, monkeypatch):
    """A dialog's signature cannot see what its lit box holds, so LiveCamera's fresh look before Enter passes 0.5EV lit
    for 0.3EV lit: enter() grabs a fresh frame itself and judges the box's picture and reading on it."""
    cam = FieldsCam()
    F, _, _ = fields_world(monkeypatch, own_runs, cam)
    on_box(cam, edit=(1, 1))
    want = F.box_pic(cam, 0)
    cam.edit[0] = 2                           # the box moved on after the walk read it (made up): 0.7EV on the fresh frame
    with pytest.raises(F.Failed, match=r"no Enter: box 0 no longer reads '0.5EV'"):
        F.enter(cam, "Cont. Bracket", OPTIONS, 0, 2, "0.5EV", want)
    assert "enter" not in cam.keys and cam.frame.path.name.endswith("_enter-check.png")
    cam.edit[0] = 1
    chosen = F.enter(cam, "Cont. Bracket", OPTIONS, 0, 2, "0.5EV", want)
    assert cam.keys == ["enter"] and chosen.endswith("_enter-check.png")


# ------------------------------------------------------------------------------------- a value the camera does not keep

SHOTS = [box("Step Width", ["3", "4(Standard)", "5"], "4(Standard)"),
         box("Number of Shots", ["0", "1", "2"], "0", wraps=True), box("Number of Shots", list("0123456789"), "0", wraps=True),
         box("Number of Shots", list("0123456789"), "3", wraps=True)]


def lowest_two(opt, edit):
    """Focus Bracket's number of shots below 2 is no number of shots: the camera keeps 2, its lowest (264148)."""
    if opt != 2:
        return edit
    digits = int("".join(b["values"][i] for b, i in zip(SHOTS[1:], edit[1:], strict=True)))
    return [edit[0], 0, 0, 2] if digits < 2 else edit


def shots_cam() -> FieldsCam:
    cam = FieldsCam()
    cam.spec = {0: CONT_BOXES, 2: SHOTS}
    cam.at[2] = [b["held"] for b in SHOTS]
    cam.correct = lowest_two
    return cam


def test_a_value_the_camera_does_not_keep_is_a_finding_and_the_walk_goes_on(own_runs, monkeypatch, capsys):
    """--option "Focus Bracket" --box 3 from the held 003: 4 to 9 proved; 0 asked, the camera keeps 2 (its record 2,
    as the box then shows): that line says what was asked and what was kept, applied false; from 2 the box is stepped
    back onto the 0 asked and on to 1, which the camera keeps as 2 too; then 2, kept as asked; then 3 comes round and is
    put back. Every line has a download, the walk's one attempt finishes, and the report credits no code to an asked
    value."""
    import pass2_report as R
    cam = shots_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Focus Bracket", "--box", "3")
    lines = fields_lines()
    assert [(x["index"], x["box"], x["applied"], x.get("asked"), x.get("kept"), x["final"]) for x in lines] == [
        ([3, 1], "4", True, None, None, False), ([3, 2], "5", True, None, None, False),
        ([3, 3], "6", True, None, None, False), ([3, 4], "7", True, None, None, False),
        ([3, 5], "8", True, None, None, False), ([3, 6], "9", True, None, None, False),
        ([3, 7], "0", False, "0", "2", False), ([3, 8], "1", False, "1", "2", False),
        ([3, 9], "2", True, None, None, False), ([3, 0], "3", True, None, None, True)]
    assert lines[6]["changes"] == [{"key": "global:0x9003", "before": 3, "after": 2}]
    out = capsys.readouterr().out
    assert "box 3: the camera kept '2', not '0'" in out
    rows = counted_rows(root)
    got = R.values_of(rows[f"Bracket Settings > Bracket Type > Focus Bracket [{CTX}]"])["global:0x9003"]
    # Step Width never walked: the record holds both fields (the review's rule); no label of an asked value, 0 or 1
    assert got == {f"4(Standard) | {n}": n for n in range(2, 10)}


def test_a_value_the_camera_does_not_keep_where_no_record_bears_the_box_out_stops(own_runs, monkeypatch, capsys):
    """The camera shows 2 after 0 was chosen, but its record holds 5 (made up): nothing says the camera kept 2, the walk
    stops on opening as before."""
    cam = shots_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.extra = {"global:0x9003": 0}
    real = cam.records

    def records():
        got = real()
        if got["global:0x9003"] == 2:
            got["global:0x9003"] = 5
        return got
    cam.records = records
    with pytest.raises(SystemExit):
        run_fields(F, root, "Focus Bracket", "--box", "3")
    assert "box 3 opened on '2', not '0', which the last OK chose" in capsys.readouterr().out


def test_each_box_of_a_run_is_its_own_attempt(own_runs, monkeypatch, capsys):
    """--box 1 --box 3, the walk of box 3 stopped: box 1's attempt finished and its lines count; box 3's are left out."""
    import pass2_report as R
    cam = shots_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.lost = ("up", 5)                       # box 1 takes three Ups (1, 2, round to 0); box 3's second Up is lost
    with pytest.raises(SystemExit):
        run_fields(F, root, "Focus Bracket", "--box", "1", "--box", "3")
    lines = fields_lines()
    assert {x["index"][0] for x in lines} == {1, 3} and len({x["attempt"] for x in lines}) == 2
    run = root / "kit2_pass2"
    counted = {x["index"][0] for i, x in enumerate(lines) if i not in R.unfinished(lines, R.attempts_done(run), {})}
    assert counted == {1}


# ------------------------------------------------------------------------------------- every pair of two fields (--grid)

# Cont. Bracket as the Drive Mode bracket lists word its pairs (0x04c6's codes), on a made-up span: up to 9 Images at
# 0.3 to 1.0EV, up to 7 at 1.3EV; Down from 3 Images gives 2 Images (-), then (+), its low end (kit2_pass2, 2026-11-19)
EVS = ["0.3EV", "0.5EV", "0.7EV", "1.0EV", "1.3EV"]
SHOTS_OF = ["2 Images (+)", "2 Images (-)", "3 Images", "5 Images", "7 Images", "9 Images"]
TOPS, CODES = [5, 5, 5, 5, 4], [1, 7, 14, 21, 27]
PAIRS = {f"{ev[:3]} EV {'2 Img. +' if s == 0 else '2 Img. -' if s == 1 else SHOTS_OF[s].split()[0] + ' Img.'}":
         CODES[e] + s for e, ev in enumerate(EVS) for s in range(TOPS[e] + 1)}


def grid_cam(held=(0, 2), strict=True, clamp=True, apart=False, drift=False, jump=False, wrap=False, lose=False,
             lose0=False, tops=None) -> FieldsCam:
    """Bracket Type with Cont. Bracket's pairs: box 1 offers what box 0's step allows. `strict`: box 0 moving while box
    1 stands off its low end fails the test (the grid moves box 0 only from there); else the camera clamps box 1 to what
    the new step allows (`clamp`) or box 0 stands still (a camera whose step refuses the count held). `apart`: beside the
    pair's record, one of the step alone and one of the count alone (made-up: every camera's rule, not the a1 II's).
    `drift`: the first Up on box 1 moves box 0 one step on too. `jump`: once 0.3 EV 9 Img. is chosen, the first Down on
    box 1 from 9 Images skips 7 Images. `wrap`: box 1 comes round at both ends. `lose`: the first two Ups on box 1 from
    0.5 EV 3 Img. go unanswered; `lose0`, the first two Ups on box 0 from 0.7EV. `tops`: box 1's top at each step, in
    place of TOPS."""
    cam = FieldsCam()
    cam.spec = {0: [box("Exposure Value", EVS, EVS[held[0]]), box("Number of Shots", SHOTS_OF, SHOTS_OF[held[1]])],
                2: FOCUS_BOXES}
    cam.at[0] = list(held)
    once = []
    top = tops or TOPS

    def rule(opt, edit, field, key):
        ev, sh = edit
        d = 1 if key == "up" else -1
        if field == 1 and lose and key == "up" and (ev, sh) == (1, 2) and once.count("lost") < 2:
            once.append("lost")
            cam.unanswered = once.count("lost")
            return [ev, sh]
        if field == 0 and lose0 and key == "up" and ev == 2 and once.count("lost0") < 2:
            once.append("lost0")
            cam.unanswered = once.count("lost0")
            return [ev, sh]
        if field == 1 and drift and key == "up" and "drift" not in once:
            once.append("drift")
            return [ev + 1, max(0, min(top[ev + 1], sh + d))]
        if field == 1 and jump and key == "down" and sh == 5 and cam.at[0] == [0, 5] and "jump" not in once:
            once.append("jump")
            return [ev, 3]
        if field == 1 and wrap:
            return [ev, (sh + d) % (top[ev] + 1)]
        if field == 1:
            return [ev, max(0, min(top[ev], sh + d))]
        to = max(0, min(len(EVS) - 1, ev + d))
        if to != ev and sh:
            assert not strict, f"box 0 moved from {EVS[ev]} with box 1 on {SHOTS_OF[sh]}, off its low end"
            if sh > top[to] and not clamp:
                return [ev, sh]
        return [to, min(sh, top[to])]
    cam.rule = rule
    cam.records = lambda: {"global:0x02bf": cam.saved, "global:0x13f9": CODES[cam.at[0][0]] + cam.at[0][1],
                           **({"global:0x9001": cam.at[0][0], "global:0x9004": cam.at[0][1]} if apart else {})}
    return cam


def test_a_grid_chooses_every_pair_once_and_puts_the_pair_held_back_last(own_runs, monkeypatch, capsys):
    """--grid on Cont. Bracket held on 0.3 EV 3 Img.: box 1 scanned at 0.3EV (Down to its low end, Up to its top, nothing
    chosen), its pairs chosen from the top down, 3 Images left to the put-back; box 0 then Up one value at a time, box 1
    on its low end each time (the made-up camera fails the test otherwise), each step's pairs chosen likewise; box 0's
    top end, then its low end at once, found in one visit; 0.3 EV 3 Img. put back last, whole. One download a pair,
    every pair the boxes offer once, never Right on the last box, one attempt finished."""
    cam = grid_cam()
    F, root, downloads = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--grid")
    lines = fields_lines()
    assert [x["label"] for x in lines[:5]] == ["0.3 EV 9 Img.", "0.3 EV 7 Img.", "0.3 EV 5 Img.", "0.3 EV 2 Img. -",
                                               "0.3 EV 2 Img. +"]
    assert {x["label"]: (x["changes"][0]["after"] if x["changes"] else None) for x in lines} == \
        {**PAIRS, "0.3 EV 3 Img.": None}
    assert len(lines) == len(PAIRS) and len(downloads) == 1 + len(PAIRS), "one download a pair, and the base"
    assert all(x["walk"] == "grid" and x["via"] == F.VIA and x["applied"] is True for x in lines)
    assert len({json.dumps(x["index"]) for x in lines}) == len(lines) and lines[0]["index"] == ["grid", 0, 5]
    last = lines[-1]
    assert (last["label"], last["final"], last["whole"], last["changes"]) == ("0.3 EV 3 Img.", True, True, [])
    assert not any(x["final"] for x in lines[:-1]) and len({x["attempt"] for x in lines}) == 1
    assert cam.keys.count("enter") == 1 + len(PAIRS) and cam.at[0] == [0, 2]
    from camkit.runs import Run
    assert [a["attempt"] for a in map(json.loads, (Run("kit2_pass2").dir / "attempts.jsonl").read_text(
        encoding="utf-8").splitlines())] == [last["attempt"]]
    out = capsys.readouterr().out
    assert "box 0: '1.3EV' is its top end" in out and "box 0: '0.3EV' is its low end" in out


def test_the_report_lists_a_whole_grids_pairs_and_samples_none(own_runs, monkeypatch, capsys):
    """kit/pass2_report.py: a record a whole grid moved is credited every pair, the one held among them by the put-back,
    and is not marked sampled: every value is listed, so the pair the camera held stands out nowhere (decision 16). The
    cross the fields' own walks made beside it changes nothing of that."""
    import pass2_report as R
    cam = grid_cam(strict=False)
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket")                     # each field walked from the pair held: a cross
    rows = counted_rows(root)
    assert R.option_fields_sampled(rows[CONT_ROW]) == {"global:0x13f9"}
    run_fields(F, root, "Cont. Bracket", "--grid")
    rows = counted_rows(root)
    assert R.values_of(rows[CONT_ROW]) == {"global:0x13f9": PAIRS}
    assert R.option_fields_sampled(rows[CONT_ROW]) == set()


def test_a_record_only_some_pairs_move_stays_sampled_beside_a_whole_grid(own_runs, monkeypatch, tmp_path, capsys):
    """The review of 2026-11-19: held on 0.7 EV 5 Img., a record of the step alone and one of the count alone beside the
    pair's. The pairs at 0.7EV leave the step's record as it was, those of 5 Images the count's, so neither is moved by
    every pair: credited, the put-back would name the pair held as its step's (or count's) one value. Both stay sampled,
    in the report written whole too; the pair's record, which every pair moved, is listed."""
    import subprocess

    import pass2_report as R
    import test_definitions as D
    cam = grid_cam((2, 3), apart=True)
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--grid")
    rows = counted_rows(root)
    assert R.option_fields_sampled(rows[CONT_ROW]) == {"global:0x9001", "global:0x9004"}
    assert R.values_of(rows[CONT_ROW])["global:0x13f9"] == PAIRS
    lines = fields_lines()
    run = D.write_run(tmp_path, lines, done=[lines[-1]["attempt"]])
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(run), "--no-schema"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    (entry,) = json.loads((run / "report.json").read_text(encoding="utf-8"))
    assert {k: x.get("sampled_from_start", False) for k, x in entry["records"].items()} == \
        {"global:0x13f9": False, "global:0x9001": True, "global:0x9004": True}


def test_the_writer_lists_every_pair_of_a_whole_grid(own_runs, monkeypatch, tmp_path, capsys):
    """The report written whole (pass2_report.py --no-schema) over a whole grid's lines, then the plain pass over it with
    the record laid out as the definition holds it (0x13f9, the sibling's names, a count of its proofs): its proof is
    the codes the grid chose, each named, no longer a count."""
    import subprocess

    import schema_update as S
    import test_definitions as D
    cam = grid_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--grid")
    lines = fields_lines()
    run = D.write_run(tmp_path, lines, done=[lines[-1]["attempt"]])
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(run), "--no-schema"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    report = json.loads((run / "report.json").read_text(encoding="utf-8"))
    (entry,) = report
    rec = entry["records"]["global:0x13f9"]
    assert entry["row"] == CONT_ROW and rec["proved"] == PAIRS and "sampled_from_start" not in rec
    setting = json.loads(json.dumps(sibling_04c6()))
    setting.update(key="global:0x13f9", id=0x13f9, proved={"sampled": {"proofs": 6, "linear": None, "from_start": True}})
    doc = {"settings": [setting], "menu": [], "camera": {}}
    S.generic(doc, report, run, "2026-11-19")
    s = doc["settings"][0]
    assert s["proved"]["values"] == sorted(PAIRS.values()) and "sampled" not in s["proved"]
    assert {v: lab for v, lab in s["values"] if v in PAIRS.values()} == {v: lab for lab, v in PAIRS.items()}


@pytest.mark.parametrize("held", [(0, 0), (2, 3), (4, 4)])
def test_a_grid_from_any_pair_held_proves_the_same_pairs(own_runs, monkeypatch, held):
    """Held on its low end (0.3 EV 2 Img. +: chosen at its place too, so box 0 moves from there, and put back last), in
    the middle (0.7 EV 5 Img.: Up, then Down past it) or on box 0's top end: every pair once, the same codes."""
    cam = grid_cam(held)
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--grid")
    lines = fields_lines()
    credited = {x["label"]: x["changes"][0]["after"] for x in lines if x["changes"]}
    held_label = next(lab for lab, v in PAIRS.items() if v == CODES[held[0]] + held[1])
    assert credited == {lab: v for lab, v in PAIRS.items() if lab != held_label}
    assert lines[-1]["label"] == held_label and lines[-1]["final"] and lines[-1]["whole"] is True
    assert cam.at[0] == list(held)


@pytest.mark.parametrize("clamp", [True, False])
def test_a_grid_is_the_same_whatever_box_0_does_with_a_count_its_step_refuses(own_runs, monkeypatch, clamp):
    """Box 0 moves only with box 1 on its low end, so a camera that clamps the count to the new step and one whose step
    stands still on a count it refuses give the same pairs."""
    cam = grid_cam(strict=False, clamp=clamp)
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--grid")
    assert {x["label"] for x in fields_lines()} == set(PAIRS)


def test_two_presses_lost_in_a_row_never_pass_for_an_end(own_runs, monkeypatch, capsys):
    """The review of 2026-11-19: at 0.5EV the first two Ups from 3 Images go unanswered, a fresh frame between, which
    took 3 Images for box 1's top: 0.5 EV 5, 7 and 9 Img. went unproved and the put-back still said whole. An end is
    taken only once a step back and on again were both seen and one more press stood still: here that press moves on
    to 5 Images, so the scan goes on and every pair is proved."""
    cam = grid_cam(lose=True)
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--grid")
    lines = fields_lines()
    assert {x["label"] for x in lines} == set(PAIRS) and lines[-1]["whole"] is True
    assert cam.unanswered == 2, "the two Ups from 0.5 EV 3 Img. went unanswered"


def test_two_presses_lost_in_a_row_on_box_0_never_pass_for_its_end(own_runs, monkeypatch, capsys):
    """The same on box 0: the first two Ups from 0.7EV go unanswered; the press after the step back and on again
    moves to 1.0EV, so 1.0 and 1.3EV are walked and no end but 1.3EV is said."""
    cam = grid_cam(lose0=True)
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--grid")
    lines = fields_lines()
    assert {x["label"] for x in lines} == set(PAIRS) and lines[-1]["whole"] is True and cam.unanswered == 2
    out = capsys.readouterr().out
    assert "box 0: '0.7EV' is its top end" not in out and "box 0: '1.3EV' is its top end" in out


def test_an_end_no_answered_press_confirms_leaves_the_grid_not_whole(own_runs, monkeypatch, capsys):
    """At 1.3EV box 1 offers 2 Images (+) alone (made up): it moves neither way, so no press the camera answered says
    its end is one; the grid goes on, but its put-back does not say whole, and the record stays sampled."""
    import pass2_report as R
    cam = grid_cam(tops=[5, 5, 5, 5, 0])
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--grid")
    lines = fields_lines()
    assert "1.3 EV 2 Img. +" in {x["label"] for x in lines} and lines[-1]["whole"] is False
    assert "moves neither way: an end no answered press confirms" in capsys.readouterr().out
    assert R.option_fields_sampled(counted_rows(root)[CONT_ROW]) == {"global:0x13f9"}


def test_a_grid_the_deadline_cuts_is_not_whole_and_stays_sampled(own_runs, monkeypatch, capsys):
    """--most 2: box 0 two values Up at most; the put-back says "whole": false, and the report keeps the record
    sampled."""
    import pass2_report as R
    cam = grid_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--grid", "--most", "2")
    lines = fields_lines()
    assert {x["fields"][0]["value"] for x in lines} == {"0.3EV", "0.5EV", "0.7EV"}
    assert lines[-1]["final"] and lines[-1]["whole"] is False
    assert "the deadline (--most): its top end not reached" in capsys.readouterr().out
    assert R.option_fields_sampled(counted_rows(root)[CONT_ROW]) == {"global:0x13f9"}


def test_a_later_grid_cut_short_takes_nothing_from_a_whole_one(own_runs, monkeypatch, capsys):
    """The review of 2026-11-19: a whole grid, then one from the same pair held that --most 2 cut short. Its put-back,
    which wrote nothing, took the whole grid's place in the report's row (the put-back rule keeps only a line that
    wrote), so no whole grid was left and the record went back to a count. Each grid's lines are kept apart now: the
    record is still every pair, listed."""
    import pass2_report as R
    cam = grid_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket", "--grid")
    run_fields(F, root, "Cont. Bracket", "--grid", "--most", "2")
    assert [x["whole"] for x in fields_lines() if x["final"]] == [True, False]
    rows = counted_rows(root)
    assert R.option_fields_sampled(rows[CONT_ROW]) == set()
    assert R.values_of(rows[CONT_ROW]) == {"global:0x13f9": PAIRS}


def test_a_whole_grid_beside_the_fields_own_walks_is_one_to_one(own_runs, monkeypatch, tmp_path, capsys):
    """Bracket Type on the camera, 2026-11-20: each field walked along the grid's edges, a grid that did not finish, then
    a whole grid. option_key keys a grid's line by its attempt, so the row held each edge pair twice and the report
    counted 78 options of 60 and called the record not one to one ("0.5 EV 3 Img." writing 9 twice). A label that wrote
    one value is one option whatever its index: every pair once, one to one, every pair listed, while the row still
    holds every counted line, the grid whole, and the unfinished grid's lines count for nothing. An edge line that wrote
    another value is still a conflict, and two labels writing one value are still not one to one."""
    import copy
    import subprocess

    import pass2_report as R
    import test_definitions as D
    cam = grid_cam(strict=False)
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Cont. Bracket")                      # the fields' own walks: the grid's edges, a cross
    run_fields(F, root, "Cont. Bracket", "--grid")
    walked = fields_lines()
    done = sorted({x["attempt"] for x in walked if x["final"]})
    edges = [x for x in walked if x.get("walk") != "grid"]
    cut = [dict(x, attempt="a grid stopped midway", base="50000_base.DAT", dat=f"{50001 + i:05d}_grid.DAT")
           for i, x in enumerate(x for x in walked if x.get("walk") == "grid" and not x["final"])]
    lines = edges + cut[:len(cut) // 2] + [x for x in walked if x.get("walk") == "grid"]
    shared = {x["label"] for x in edges} & set(PAIRS)
    assert len(shared) > 5 and all(x["changes"][0]["after"] == PAIRS[x["label"]] for x in edges if x["changes"])
    opts = R.rows_of(None, lines, R.unfinished(lines, set(done), {}))[CONT_ROW]
    assert len(opts) == len(walked) and R.every_pair_moved(R.fields_lines(opts)) == {"global:0x13f9"}
    assert R.proved_options(opts) == len(PAIRS) and R.two_labels_one_value(opts, R.values_of(opts)) == {}
    assert R.not_one_to_one(lines, CONT_ROW, "global:0x13f9", {}, {"list"}) == []
    run = D.write_run(tmp_path, lines, done=done)
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(run), "--no-schema"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    (entry,) = json.loads((run / "report.json").read_text(encoding="utf-8"))
    rec = entry["records"]["global:0x13f9"]
    assert (entry["options"], rec["proved"], rec["notes"]) == (len(PAIRS), PAIRS, []) and "sampled_from_start" not in rec
    # an edge line of 0.5 EV 3 Img. that wrote another value than the grid's: one label, two values
    other = copy.deepcopy(lines)
    next(x for x in other if x.get("walk") != "grid" and x["label"] == "0.5 EV 3 Img.")["changes"][0]["after"] = 99
    assert [n["why"] for n in R.not_one_to_one(other, CONT_ROW, "global:0x13f9", {}, {"list"})] == \
        ["the label wrote 2 different values"]
    # 0.5 EV 3 Img. writing, on its edge line and in the grid alike, what 0.7 EV 3 Img. writes: two labels, one value
    twice = copy.deepcopy(lines)
    for x in twice:
        if x["label"] == "0.5 EV 3 Img." and x["changes"]:
            x["changes"][0]["after"] = PAIRS["0.7 EV 3 Img."]
    opts = R.rows_of(None, twice, R.unfinished(twice, set(done), {}))[CONT_ROW]
    assert R.two_labels_one_value(opts, R.values_of(opts)) == {"global:0x13f9": ["0.5 EV 3 Img.", "0.7 EV 3 Img."]}
    assert R.not_one_to_one(twice, CONT_ROW, "global:0x13f9", {}, {"list"}) == []


def test_a_grid_stopped_midway_counts_none_of_its_pairs(own_runs, monkeypatch, capsys):
    """The screen stops reading as the carousel on the second visit's Right into box 0 (the ninth Right: the look's
    three, the base's, the first visit's three, the row's): the walk stops before the next key, the first pair's line is
    written saying what applied is not known, and its one attempt never finishes, so the report counts none of its
    lines."""
    cam = grid_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.lost = ("right", 9)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--grid")
    assert [(x["label"], x["applied"]) for x in fields_lines()] == [("0.3 EV 9 Img.", None)]
    assert CONT_ROW not in counted_rows(root)


def test_a_grid_stops_on_a_box_opening_on_another_pair_than_the_last_ok_chose(own_runs, monkeypatch, capsys):
    cam = grid_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.downloaded = lambda tag: tag == "Bracket-Type-grid-0-4" and cam.at[0].__setitem__(1, 3)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--grid")
    assert "box 1 opened on '5 Images', not '7 Images', which the last OK chose" in capsys.readouterr().out


def test_no_enter_where_box_0_moved_during_the_first_scan(own_runs, monkeypatch, capsys):
    """The review of 2026-11-19: box 0's picture, which the check before Enter compares with, was taken after the first
    visit's scan of box 1, so a camera that stepped box 0 in that scan passed it, and Enter went on 0.5 EV 9 Img. where
    the line would say 0.3 EV 9 Img. It is taken as Right reaches box 1: nothing is chosen."""
    cam = grid_cam(drift=True)
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--grid")
    assert "box 0 changed while box 1 moved" in capsys.readouterr().out
    assert cam.keys.count("enter") == 1 and fields_lines() == [], "the base's Enter alone"


def test_a_grid_stops_on_box_0_opening_on_another_step_than_the_last_ok_chose(own_runs, monkeypatch, capsys):
    """After 0.3 EV 9 Img. the camera holds 0.5 EV 9 Img. (made up): box 0 is checked on opening, before box 1, which
    shows 9 Images either way; nothing more is chosen."""
    cam = grid_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.downloaded = lambda tag: tag == "Bracket-Type-grid-0-5" and cam.at[0].__setitem__(0, 1)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--grid")
    assert "box 0 opened on '0.5EV', not '0.3EV', which the last OK chose" in capsys.readouterr().out
    assert cam.keys.count("enter") == 2, "the base's and the first pair's"


def test_a_step_onto_a_value_seen_before_must_show_it(own_runs, monkeypatch, capsys):
    """Down from 9 Images onto 7 Images, seen there by the scan, shows 5 Images (the camera skipped one, made up): the
    grid stops before any Enter on it."""
    cam = grid_cam(jump=True)
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--grid")
    assert "box 1 reads '5 Images' where it read '7 Images' before" in capsys.readouterr().out
    assert cam.keys.count("enter") == 2, "the base's and the first pair's"


def test_a_scan_stops_on_a_box_that_comes_round(own_runs, monkeypatch, capsys):
    """Box 1 comes round past its low end to 9 Images and on down to 3 Images again: a value seen before on the scan's
    way stops the row, nothing chosen (the grid walks boxes with two ends only)."""
    cam = grid_cam(strict=False, wrap=True)
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--grid")
    assert "box 1 reads '3 Images' (" in capsys.readouterr().out
    assert cam.keys.count("enter") == 1 and fields_lines() == []


def test_a_grid_takes_two_fields_of_one_box_each(own_runs, monkeypatch, capsys):
    cam = FieldsCam()
    F, root, downloads = fields_world(monkeypatch, own_runs, cam)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Focus Bracket", "--grid")
    assert "--grid: Focus Bracket draws 4 boxes in 2 fields" in capsys.readouterr().out and downloads == []


@pytest.mark.parametrize("extra, said", [(["--grid", "--box", "1"], "--box and --grid"),
                                         (["--look", "--grid"], "--look and --grid"),
                                         (["--look", "--number", "3"], "--look and --number"),
                                         (["--number", "-1"], "a number of zero or more")])
def test_one_way_of_proving_a_run(own_runs, monkeypatch, extra, said):
    cam = FieldsCam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    with pytest.raises(SystemExit, match=said):
        run_fields(F, root, "Focus Bracket", *extra)
    assert cam.keys == []


# ------------------------------------------------------------------------------------- a named number (--number)

def capped(opt, edit):
    """Focus Bracket's number of shots kept as 2 below 2 (264148), and as 250 above it (a made-up top)."""
    edit = lowest_two(opt, edit)
    n = int("".join(b["values"][i] for b, i in zip(SHOTS[1:], edit[1:], strict=True))) if opt == 2 else 0
    return [edit[0], 2, 5, 0] if n > 250 else edit


def number_cam(own_top=False) -> FieldsCam:
    """Focus Bracket on 003 as the a1 II answers its digit boxes (kit2_pass2 268989-269285, 2026-11-20): each Up or Down
    moves the lit box alone, coming round, and any three digits stand while stepping (000 among them, 264137); the
    camera corrects the number only on OK, below 2 to 2; and an unlit box's picture changes with the box lit. Above a
    made-up top of 250 it keeps 250 (capped); with `own_top`, every number the boxes show, up to 299 (the SDK's range
    for it, [2, 299, 1])."""
    cam = shots_cam()
    cam.correct = lowest_two if own_top else capped
    cam.lit_moves = True
    return cam


def test_a_named_number_is_put_in_with_no_enter_on_the_way_one_download_each(own_runs, monkeypatch, capsys):
    """--number 299 --number 2 --number 7 on Focus Bracket held on 003: each number's digits stepped box by box, Enter
    once on the last box, one download; 299 is kept as 250 (the boxes and the record say so on the next opening: a
    finding, "applied": false), 2 and 7 kept as asked; 003 put back last, its download the base's."""
    cam = number_cam()
    F, root, downloads = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Focus Bracket", "--number", "299", "--number", "2", "--number", "7")
    lines = fields_lines()
    assert [(x["index"], x["value"], x["label"], x["applied"], x.get("asked"), x.get("kept"), x["final"],
             [(c["key"], c["after"]) for c in x["changes"]]) for x in lines] == [
        (["number", 299], "299", "4(Standard) | 299", False, "299", "250", False, [("global:0x9003", 250)]),
        (["number", 2], "2", "4(Standard) | 2", True, None, None, False, [("global:0x9003", 2)]),
        (["number", 7], "7", "4(Standard) | 7", True, None, None, False, [("global:0x9003", 7)]),
        (["number", 3], "3", "4(Standard) | 3", True, None, None, True, [])]
    assert all(x["walk"] == "number" and x["field"] == "Number of Shots" for x in lines)
    assert len(downloads) == 5 and cam.keys.count("enter") == 5, "the base and one a number, no Enter on the way"
    assert "the camera kept 250, not 299" in capsys.readouterr().out
    assert cam.at[2] == [1, 0, 0, 3]


def test_the_ends_299_and_2_then_4_and_7_from_a_held_3(own_runs, monkeypatch, capsys):
    """--number 299 --number 2 --number 4 --number 7, the runs of 2026-11-20, on a camera that keeps 299: each number put
    in box by box with its other boxes' pictures judged with the box lit as before its stepping (where the old check,
    across two lit boxes, passed every number over), chosen once, its download holding it, kept as asked on the next
    opening; 003 put back last with Right alone, its download the base's."""
    cam = number_cam(own_top=True)
    F, root, downloads = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Focus Bracket", "--number", "299", "--number", "2", "--number", "4", "--number", "7")
    assert "not put in" not in capsys.readouterr().out
    lines = fields_lines()
    assert [(x["index"], x["value"], x["applied"], x.get("kept"), x["final"],
             [(c["key"], c["before"], c["after"]) for c in x["changes"]]) for x in lines] == [
        (["number", n], str(n), True, None, False, [("global:0x9003", 3, n)]) for n in (299, 2, 4, 7)] + [
        (["number", 3], "3", True, None, True, [])]
    assert len(downloads) == 6 and cam.keys.count("enter") == 6, "the base and one a number, no Enter on the way"
    assert cam.at[2] == [1, 0, 0, 3]


def test_a_number_below_the_bottom_is_kept_as_2(own_runs, monkeypatch, capsys):
    """--number 1 --number 2: the boxes show 001 and OK is taken, the camera keeps 2 (264137, 000 kept as 2): the next
    opening shows 002 and the download holds 2, so 1's line says what was asked and what was kept, "applied": false;
    2 then needs no press in the boxes and is kept as asked."""
    cam = number_cam(own_top=True)
    F, root, downloads = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Focus Bracket", "--number", "1", "--number", "2")
    assert "the camera kept 2, not 1" in capsys.readouterr().out
    assert [(x["value"], x["applied"], x.get("asked"), x.get("kept"), [c["after"] for c in x["changes"]], x["final"])
            for x in fields_lines()] == [("1", False, "1", "2", [2], False), ("2", True, None, None, [2], False),
                                         ("3", True, None, None, [], True)]
    assert len(downloads) == 4


@pytest.mark.parametrize("fault, said", [
    ("drop", "box 2 stood still on one Up and moved on the next"),       # the tens box's third Up went unanswered
    ("lost", "after Up on box 2: the screen reads as unknown")])         # the screen stopped reading as the carousel
def test_a_failure_in_the_middle_of_a_number_leaves_nothing_chosen(own_runs, monkeypatch, capsys, fault, said):
    """--number 299 stopped while the tens box is stepped: the run stops there, no Enter after the base's, no proof
    line, no download but the base's; the session puts the start file back."""
    import boxes_run
    cam = number_cam(own_top=True)
    F, root, downloads = fields_world(monkeypatch, own_runs, cam)
    setattr(cam, fault, ("up", 5))
    with pytest.raises(SystemExit) as stop:
        run_fields(F, root, "Focus Bracket", "--number", "299", "--number", "2")
    assert stop.value.code == boxes_run.EXIT_INCOMPLETE
    assert said in capsys.readouterr().out
    assert fields_lines() == [] and cam.keys.count("enter") == 1 and len(downloads) == 1
    assert cam.at[2] == [1, 0, 0, 3]


def test_a_box_outside_the_field_not_as_the_first_visit_saw_it_passes_the_number_over(own_runs, monkeypatch, capsys):
    """Step Width moves after 299's download (made up): the next visit compares it, the digit field's first box lit as
    on the first visit, and passes 2 over, nothing chosen; the put-back cannot be made so and stops the run."""
    cam = number_cam(own_top=True)
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.downloaded = lambda tag: tag == "Bracket-Type-number-299" and cam.at[2].__setitem__(0, 2)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Focus Bracket", "--number", "299", "--number", "2")
    out = capsys.readouterr().out
    assert "2: not put in: box 0 is not as the first visit saw it" in out
    assert "the number held, 3, cannot be put back: box 0 is not as the first visit saw it" in out
    assert [(x["value"], x["applied"]) for x in fields_lines()] == [("299", True)] and cam.keys.count("enter") == 2


# The two runs that failed on 2026-11-20 (logs kit2_fin_logs/brk_whole_05_focus_numbers.log over HDMI and
# brk_focus_osd_01_numbers.log over OSD), --number 299 2 4 7 on Focus Bracket held on 003: each visit's frames from the
# option lit to the last press before the old check passed the number over, the put-back's last
SHOTS_DIR = ("kit2_pass2", "shots")
VISITS = {"hdmi": [(269026, 269067), (269075, 269081), (269089, 269095), (269103, 269115), (269123, 269128)],
          "osd": [(269173, 269213), (269222, 269228), (269237, 269243), (269252, 269264), (269273, 269278)]}


def shot(name: str) -> Path:
    return need(A1.joinpath(*SHOTS_DIR, name))


def frame_numbered(n: int) -> Path:
    """kit2_pass2's frame number n, whatever it was taken after (the test skips without it)."""
    found = next((p for p in (A1.joinpath(*SHOTS_DIR, f"{n}_{t}.png") for t in ("right", "up", "down", "reread", "fresh"))
                  if p.exists()), None)
    return need(found or A1.joinpath(*SHOTS_DIR, f"{n}_*.png"))


class ReplayCam:
    """The camera's own frames of one visit replayed press by press: a press must be the key the next frame was taken
    after (its name's tag), the fresh looks the run took on the way passed over; a fresh look takes the next frame where
    it is one, else shows the frame on show again (the screen did not change). The lit box's digit as the frames show
    it, each Up one more and each Down one less from the 003 the look read (269034 shows 2, 269054 9, 269067 9), stands
    in for the readers, who are not what is tested."""
    LOOKS = ("reread", "fresh")

    def __init__(self, lo, hi):
        need(A1.joinpath(*SHOTS_DIR))
        self.paths = [frame_numbered(n) for n in range(lo, hi + 1)]
        self.keys, self.digits = [], []
        lit, held = None, ["4(Standard)", "0", "0", "3"]
        for p in self.paths:
            t = self.tag(p)
            if t == "right":
                lit = 0 if lit is None else lit + 1
            elif t in ("up", "down"):
                held[lit] = str((int(held[lit]) + (1 if t == "up" else -1)) % 10)
            self.digits.append(None if lit is None else held[lit])
        self.show(0)

    @staticmethod
    def tag(p: Path) -> str:
        return p.stem.split("_", 1)[1]

    def show(self, i):
        self.i, self.frame = i, load(self.paths[i])
        self.screen = screen.read(self.frame)

    def press(self, key, **kw):
        self.keys.append(key)
        j = self.i + 1
        while j < len(self.paths) and self.tag(self.paths[j]) in self.LOOKS:
            j += 1
        assert j < len(self.paths) and self.tag(self.paths[j]) == key, \
            f"{key} after {self.frame.path.name}, where the run pressed {self.tag(self.paths[j]) if j < len(self.paths) else 'nothing'}"
        self.show(j)

    def refresh(self, tag):
        if self.i + 1 < len(self.paths) and self.tag(self.paths[self.i + 1]) in self.LOOKS:
            self.show(self.i + 1)

    def read(self):
        return self.screen

    def said(self) -> str:
        return self.digits[self.i]


@pytest.mark.parametrize("eyes", ["hdmi", "osd"])
def test_the_failed_runs_frames_take_every_number_and_the_put_back(eyes, monkeypatch):
    """put_number on the camera's own frames of both failed runs, each visit in turn as the run made them (299, 2, 4, 7,
    then the 003 put back with Right alone): every number stands in the boxes, Enter would go on the last box, and no
    press but those the camera answered, where the old check said "box 1 changed while the boxes after it were set" on
    each (box 1's picture cut with box 2 lit and again with box 3 lit)."""
    import carousel_fields_run as F
    monkeypatch.setattr(F, "title_reads", lambda c, labels: "Focus Bracket" if c.read().kind == "dialog" else None)
    monkeypatch.setattr(F, "lit_read", lambda c, always: F.BoxRead(c.said(), c.said(), c.said(), "made-up", "both"))
    look_ = F.Look(["Step Width"] + ["Number of Shots"] * 3, ["4(Standard)", "0", "0", "3"])
    n, opened = F.Named(), {}
    for (lo, hi), digits in zip(VISITS[eyes], ["299", "002", "004", "007", "003"], strict=True):
        cam = ReplayCam(lo, hi)
        first = None if opened else "003"
        why, r = F.put_number(cam, "Focus Bracket", OPTIONS, look_, (1, 3), digits, n, opened, "Focus Bracket", first)
        assert (why, r and r.text) == ("", digits[-1]), f"{digits} on {cam.frame.path.name}"
        assert cam.i == len(cam.paths) - 1, f"{digits}: every press the camera answered, and no other"
        assert "enter" not in cam.keys


def frame_cam(name: str):
    """One of the camera's frames on show, as box_pic reads it (the screen and the image of the frame on show)."""
    f = load(shot(name))
    s = screen.read(f)
    return SimpleNamespace(frame=f, read=lambda: s)


@pytest.mark.parametrize("before, after", [("269127_right.png", "269128_right.png"),      # HDMI, the put-back
                                           ("269277_right.png", "269278_right.png")])     # OSD, the put-back
def test_an_unlit_digit_boxs_picture_changes_with_the_box_lit(before, after):
    """What passed every number over on 2026-11-20: box 1 holds 0 on both frames, box 2 lit on the first and box 3 on the
    second, nothing pressed between but Right. The pixel reader finds box 1's right side where the lit box beside it
    leaves it (x 446 beside box 2, 449 or 450 with box 3 lit), so its two pictures are two shapes, one digit's lit pixels
    each: an unlit box is never compared across two lit boxes."""
    import carousel_fields_run as F
    a, b = frame_cam(before), frame_cam(after)
    assert (a.read().field, b.read().field) == (2, 3)
    pa, pb = F.box_pic(a, 1), F.box_pic(b, 1)
    assert pa.shape != pb.shape and not F.same_pic(pa, pb) and int(pa.sum()) == int(pb.sum())


@pytest.mark.parametrize("before, after, lit", [
    ("269036_fresh.png", "269054_fresh.png", 2),    # HDMI: the tens box stepped 0 to 9 (203 to 293)
    ("269056_fresh.png", "269067_up.png", 3),       # HDMI: the units box 3 to 9 (293 to 299)
    ("269182_fresh.png", "269200_fresh.png", 2),    # OSD
    ("269202_fresh.png", "269213_up.png", 3)])
def test_with_one_box_lit_the_other_boxes_pictures_stand(before, after, lit):
    """The same runs' frames: while one box is stepped, each other box's picture, cut with that box lit, is the same
    before its first press and after its last (no pixel apart on these frames), the box stepped's is not."""
    import carousel_fields_run as F
    a, b = frame_cam(before), frame_cam(after)
    assert a.read().field == b.read().field == lit
    assert [F.same_pic(F.box_pic(a, k), F.box_pic(b, k)) for k in range(4)] == [k != lit for k in range(4)]


def test_a_number_the_boxes_will_not_hold_is_said_and_nothing_is_chosen(own_runs, monkeypatch, capsys):
    """--number 300: the hundreds box comes round after 2 without showing 3: said, closed with MENU, no Enter, no line;
    the put-back goes on."""
    cam = number_cam()
    F, root, downloads = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Focus Bracket", "--number", "300")
    assert "300: not put in: box 1 came round to 0 without showing 3" in capsys.readouterr().out
    assert [(x["value"], x["final"]) for x in fields_lines()] == [("3", True)]
    assert cam.keys.count("enter") == 2 and len(downloads) == 2


def test_a_number_wider_than_its_boxes_or_an_option_with_no_digit_field_is_refused(own_runs, monkeypatch, capsys):
    cam = number_cam()
    F, root, downloads = fields_world(monkeypatch, own_runs, cam)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Focus Bracket", "--number", "1000")
    with pytest.raises(SystemExit):
        run_fields(F, root, "Cont. Bracket", "--number", "3")
    out = capsys.readouterr().out
    assert "--number [1000]: Number of Shots has 3 digit boxes" in out
    assert "--number: Cont. Bracket draws no one field of digit boxes" in out and downloads == []


def test_the_report_credits_named_numbers_by_their_field_and_never_the_put_back(own_runs, monkeypatch, capsys):
    """Step Width walked whole, then --number 2 --number 7: the record of the number alone is credited 2 and 7 by the
    field's value; the number held, put back last, is credited to nothing (it would stand out among numbers a run named),
    and the record is not marked sampled for it."""
    import pass2_report as R
    cam = number_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Focus Bracket", "--box", "0")
    run_fields(F, root, "Focus Bracket", "--number", "2", "--number", "7")
    opts = counted_rows(root)[f"Bracket Settings > Bracket Type > Focus Bracket [{CTX}]"]
    assert R.values_of(opts)["global:0x9003"] == {"2": 2, "7": 7}
    assert R.option_fields_sampled(opts) == set()


def test_named_numbers_alone_are_credited_by_their_value_though_the_other_field_was_never_walked(own_runs, monkeypatch):
    """--number 2 --number 7 with Step Width never walked in the row: the record moved to each number named, so it
    holds the number alone, credited 2 and 7 by the field's value, never by the label that carries Step Width as it
    stood, and not marked sampled; the put-back credits nothing."""
    import pass2_report as R
    cam = number_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    run_fields(F, root, "Focus Bracket", "--number", "2", "--number", "7")
    opts = counted_rows(root)[f"Bracket Settings > Bracket Type > Focus Bracket [{CTX}]"]
    assert R.values_of(opts)["global:0x9003"] == {"2": 2, "7": 7}
    assert R.option_fields_sampled(opts) == set()


def drive_number(n: int, changes, final=False, k=0) -> dict:
    """A named number's line as Drive Mode > Focus Bracket's run wrote it on the camera (kit2_pass2, 2026-11-20): Step
    Width never walked in that row, the number's record moved to the number."""
    return {"path": ["Drive Mode", "Focus Bracket"], "kind": "list", "via": "a carousel option's own fields",
            "walk": "number", "index": ["number", n], "field": "Number of Shots", "value": str(n),
            "label": f"4(Standard) | {n}", "fields": [{"label": "Step Width", "value": "4(Standard)"},
                                                      {"label": "Number of Shots", "value": str(n)}],
            "box": str(n)[-1], "read_by": "reader", "shown": str(n)[-1], "box_vlm": str(n)[-1], "box_reader": "vllm",
            "dat": f"{269500 + k}_Drive-Mode-number-{n}.DAT", "base": "269449_Drive-Mode-Focus-Bracket-base.DAT",
            "applied": True, "final": final, "attempt": "kit2_pass2-d", "context": "Drive Mode dial on *",
            "changes": [{"key": key, "before": b, "after": a} for key, b, a in changes]}


DRIVE_NUMBERS = [drive_number(299, [("global:0x10aa", 3, 299)], k=0), drive_number(2, [("global:0x10aa", 3, 2)], k=1),
                 drive_number(4, [("global:0x10aa", 3, 4)], k=2), drive_number(7, [("global:0x10aa", 3, 7)], k=3),
                 drive_number(3, [], final=True, k=4)]


def test_the_drive_mode_rows_numbers_credit_the_number_record_by_value():
    """The five lines of Drive Mode > Focus Bracket (2026-11-20): 0x10aa took 299, 2, 4 and 7, each the number named, so
    it is credited by the field's value, read by the vision model, not sampled (where the old rule, Step Width never
    walked there, held it with Step Width and its labels named no number); the put-back credits nothing."""
    import pass2_report as R
    opts = dict(enumerate(DRIVE_NUMBERS))
    sources = {}
    assert R.option_fields_values(opts, sources) == {"global:0x10aa": {"299": 299, "2": 2, "4": 4, "7": 7}}
    assert set(sources["global:0x10aa"].values()) == {"vision model"}
    assert not R.held_together(DRIVE_NUMBERS, "global:0x10aa") and R.option_fields_sampled(opts) == set()


@pytest.mark.parametrize("why, lines", [
    ("a record not holding the number named", [drive_number(299, [("global:0x9005", 0, 1)]),     # a made-up flag
                                                drive_number(7, [("global:0x10aa", 3, 7)], k=1)]),
    ("a line of another walk moved it too", [drive_number(299, [("global:0x10aa", 3, 299)]),
                                             {**drive_number(5, [("global:0x10aa", 3, 5)], k=1), "walk": None,
                                              "index": [1, 2]}]),
    ("lines of two fields moved it", [drive_number(299, [("global:0x10aa", 3, 299)]),
                                      {**drive_number(299, [("global:0x10aa", 3, 299)], k=1), "field": "Step Width"}])])
def test_named_numbers_hold_the_fields_together_otherwise(why, lines):
    """Where the record does not hold each number named, or other lines move it too, the old rule stands: Step Width
    never walked, the record holds the fields together, credited by the label and marked sampled."""
    import pass2_report as R
    key = next(c["key"] for c in lines[0]["changes"])
    assert R.held_together(lines, key), why
    assert key in R.option_fields_sampled(dict(enumerate(lines)))


def stepped(cam, opt, edit, field, key) -> list:
    """FieldsCam's own Up or Down on a field, for a rule that adds to it."""
    b = cam.spec[opt][field]
    n, i = len(b["values"]), edit[field] + (1 if key == "up" else -1)
    out = list(edit)
    out[field] = i % n if b["wraps"] else max(0, min(n - 1, i))
    return out


def carry_units_to_tens(cam, opt, edit, field, key):
    """Each Up on the units box sets the tens box to 5 (made up)."""
    out = stepped(cam, opt, edit, field, key)
    return [out[0], out[1], 5, out[3]] if opt == 2 and field == 3 and key == "up" else out


def carry_tens_to_units(cam, opt, edit, field, key):
    """Each Up on the tens box moves the units box one on too (made up)."""
    out = stepped(cam, opt, edit, field, key)
    return [*out[:3], (out[3] + 1) % 10] if opt == 2 and field == 2 and key == "up" else out


def clamp_at_250(cam, opt, edit, field, key):
    """A number above a made-up top of 250 pulled back to it while stepping, the other boxes changed with it."""
    out = stepped(cam, opt, edit, field, key)
    return [out[0], 2, 5, 0] if opt == 2 and int("".join(map(str, out[1:]))) > 250 else out


@pytest.mark.parametrize("rule, number, said", [
    (carry_units_to_tens, "7", "7: not put in: box 2 changed while box 3 was stepped"),
    (carry_tens_to_units, "40", "40: not put in: box 3 changed while box 2 was stepped"),
    (clamp_at_250, "255", "255: not put in: box 3 changed while box 2 was stepped"),     # 253 pulled back to 250
    (clamp_at_250, "299", "299: not put in: box 2 stands still on 5, its top end, short of 9")])
def test_a_number_whose_stepping_moves_another_box_is_not_chosen(own_runs, monkeypatch, capsys, rule, number, said):
    """A camera that carries between its digit boxes or pulls a number back into its range while stepping (made up;
    the a1 II does neither): each box's stepping is judged by every other box's picture before its first press and
    after its last, box lit as it was, so the number is said and passed over, no Enter; the put-back goes on."""
    cam = number_cam()
    F, root, downloads = fields_world(monkeypatch, own_runs, cam)
    cam.rule = lambda *a: rule(cam, *a)
    run_fields(F, root, "Focus Bracket", "--number", number)
    assert said in capsys.readouterr().out
    assert [(x["value"], x["final"]) for x in fields_lines()] == [("3", True)] and cam.keys.count("enter") == 2


def test_boxes_opening_on_another_number_with_no_record_to_bear_it_out_stop_the_walk(own_runs, monkeypatch, capsys):
    """--number 299: the camera shows 250 on the next opening, but its record holds 260 (made up): nothing says the
    camera kept 250, so the walk stops before any key steps the boxes, the 299 line saying what applied is not known."""
    cam = number_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    real = cam.records

    def records():
        got = real()
        if got["global:0x9003"] == 250:
            got["global:0x9003"] = 260
        return got
    cam.records = records
    with pytest.raises(SystemExit):
        run_fields(F, root, "Focus Bracket", "--number", "299", "--number", "2")
    assert "the boxes opened on 250, not 299, which the last OK chose, and its download does not bear them out" in \
        capsys.readouterr().out
    assert [(x["value"], x["applied"]) for x in fields_lines()] == [("299", None)] and cam.keys.count("enter") == 2


def test_the_first_number_starts_only_from_the_boxes_the_look_read(own_runs, monkeypatch, capsys):
    """The camera holds 005 once the base is chosen, where the look read 003 (made up): the first visit stops on the
    units box, before any key steps it, nothing chosen but the base."""
    cam = number_cam()
    F, root, _ = fields_world(monkeypatch, own_runs, cam)
    cam.downloaded = lambda tag: tag == "Bracket-Type-Focus-Bracket-base" and cam.at[2].__setitem__(3, 5)
    with pytest.raises(SystemExit):
        run_fields(F, root, "Focus Bracket", "--number", "7")
    assert "box 3 holds '5', the look read '3'" in capsys.readouterr().out
    assert cam.keys.count("enter") == 1 and fields_lines() == []
