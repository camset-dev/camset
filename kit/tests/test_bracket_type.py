"""The Bracket Type carousel (the a1 II's Shooting > Drive Mode > Bracket Settings > Bracket Type, open only with the drive
mode dial on BRK): the pixel reader tells a carousel option's lit field from the option lit. The camera's frames these
read are found by their own path (camkit.paths.a1ii_root()), and those tests skip without them."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
from camkit import paths, screen  # noqa: E402
from camkit.frames import Frame, load  # noqa: E402

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
