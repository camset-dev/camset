"""Offline tests of the memory set twins: kit/tools/set_twins.py (the groups, the spot check's candidates and picks) and
kit/provers/memreg_run.py (the slot screen's lit tab, the rows read from the survey, the judgement and its proof lines),
with made-up definitions, menus and files; and the session's expected differences (camkit/session.py), which the
prover's restore check takes. Nothing talks to a camera, and no value here is a camera's."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, paths, session  # noqa: E402
from camkit.camset import Camset, Record  # noqa: E402

SAMPLE = ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"


def module(name: str, where: str):
    sys.path.insert(0, str(ROOT / "kit"))
    for sub in ("tools", "provers"):
        if str(ROOT / "kit" / sub) not in sys.path:
            sys.path.insert(1, str(ROOT / "kit" / sub))
    spec = importlib.util.spec_from_file_location(name, ROOT / "kit" / where / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def T():
    return module("set_twins", "tools")


@pytest.fixture(scope="module")
def M():
    return module("memreg_run", "provers")


def rec(rid: int, value: int) -> Record:
    return Record(rid, 1, 1, bytes([value]), 0)


def made_file(live: dict, sets: list) -> Camset:
    """A made-up file: section 0 from `live` ({id: value}), one section per dict of `sets`."""
    return Camset(model="TEST-CAM", saved="", sections=[{r: rec(r, v) for r, v in s.items()} for s in [live, *sets]])


# ---------------------------------------------------------------- set_twins: the groups

def test_the_groups_sort_every_set_record_once_as_the_definition_names_its_twin(T):
    """A twin a live setting names is flagged (the writer flags every such setting in_sets); one no setting names is
    unflagged, whatever the sets hold; a set: setting's record is set-defined, twin or not; the rest of the set records
    are set-only. A live record outside the sets is no twin."""
    doc = {"settings": [
        {"key": "global:0x0010", "area": "global", "id": 0x10, "in_sets": True, "name": "A"},
        {"key": "global:0x0011", "area": "global", "id": 0x11, "in_sets": True, "name": "B"},
        {"key": "global:0x0090", "area": "global", "id": 0x90, "in_sets": False, "name": "live only"},
        {"key": "set:0x0012", "area": "set", "id": 0x12, "name": "slot mark"},
        {"key": "set:0x0050", "area": "set", "id": 0x50, "name": "set only, named"}]}
    live = {0x10: 1, 0x11: 0, 0x12: 0, 0x13: 0, 0x90: 3}
    one = {0x10: 1, 0x11: 0, 0x12: 4, 0x13: 0, 0x50: 2, 0x51: 0}
    g = T.groups(doc, made_file(live, [one, dict(one)]))
    assert g["twins"] == [0x10, 0x11, 0x12, 0x13]
    assert (g["flagged"], g["unflagged"], g["set_defined"], g["set_only"]) == ([0x10, 0x11], [0x13], [0x12, 0x50], [0x51])
    assert g["flag_missing"] == []
    flagged_elsewhere = {"settings": doc["settings"] + [{"key": "global:0x0099", "area": "global", "id": 0x99,
                                                         "in_sets": True, "name": "flagged, no copy"}]}
    assert T.groups(flagged_elsewhere, made_file(live, [one]))["flag_missing"] == [0x99]


# ---------------------------------------------------------------- set_twins: the candidates and the picks

def tree_of(*pages) -> dict:
    """A made-up Stills menu tree: pages of (tab, group, rows)."""
    return {"tabs": [{"tab": tab, "pages": [{"page": "1/1", "group": group, "rows": rows}]} for tab, group, rows in pages]}


def lrow(label, options, state="walked", kind="list"):
    return {"label": label, "state": state, "why": "", "kind": kind, "options": options}


def setting(rid, row, values, **kw):
    return {"key": f"global:0x{rid:04x}", "area": "global", "id": rid, "name": row[-1], "row": row, "values": values,
            "in_sets": True, **kw}


OO = [[0, "On"], [1, "Off"]]


def candidate_world():
    rows = [
        (0x20, ["Color Space"], [lrow("Color Space", ["sRGB", "AdobeRGB"])], [[0, "sRGB"], [1, "AdobeRGB"]], {}),
        (0x21, ["Peaking Display"], [lrow("Peaking Display", ["On", "Off"])], OO, {}),
        (0x22, ["Red Eye Reduction"], [lrow("Red Eye Reduction", ["On", "Off"])], OO, {}),          # light
        (0x23, ["Audio Signals"], [lrow("Audio Signals", ["On", "Off"])], OO, {}),                  # never-open (sound)
        (0x24, ["High ISO NR"], [lrow("High ISO NR", ["Normal", "Low", "Off"])], [[0, "Normal"], [1, "Low"]], {}),
        (0x25, ["Grey Row"], [lrow("Grey Row", ["On", "Off"])], OO, {}),                           # greyed in the scan
        (0x26, ["Movie Row"], [lrow("Movie Row", ["On", "Off"])], OO, {"modes": "movie, S&Q"}),
        (0x27, ["Many"], [lrow("Many", [str(i) for i in range(9)])], [[i, str(i)] for i in range(9)], {}),
        (0x28, ["Top Image"], [lrow("Top Image", ["Off", "Rating (★)"])], [[0, "Off"], [1, "Rating (★)"]], {}),
        (0x29, ["Done Before"], [lrow("Done Before", ["On", "Off"])], OO, {}),                     # evidenced
        (0x2a, ["Sub", "Child"], [{"label": "Sub", "state": "submenu", "kind": "submenu",
                                   "children": [lrow("Child", ["A", "B"])]}], [[0, "A"], [1, "B"]], {}),
        (0x2b, ["Sub2", "Deeper", "Row"], [], OO, {}),
        (0x2c, ["Not Walked"], [lrow("Not Walked", ["On", "Off"], state="greyed", kind="notice")], OO, {}),
        (0x2d, ["Unflagged Twin"], [lrow("Unflagged Twin", ["On", "Off"])], OO, {}),
    ]
    doc = {"settings": [setting(rid, row, vals, **kw) for rid, row, _, vals, kw in rows]}
    tree = tree_of(*[("Focus" if rid in (0x21, 0x2d) else "Shooting", f"G{rid % 3}", tree_rows)
                     for rid, _, tree_rows, _, _ in rows if tree_rows])
    scanned = {T_key(r[1][0]): r[0] == 0x25 for r in rows}
    live = {rid: 0 for rid, *_ in rows}
    cs = made_file(live, [dict(live)])
    twin_of = {rid: "unflagged" if rid == 0x2d else "flagged" for rid, *_ in rows}
    return doc, tree, scanned, cs, twin_of


def T_key(label):
    from camkit import match
    return match.key(label)


def test_the_candidates_are_plain_list_rows_and_each_one_left_out_says_why(T):
    """A candidate is a walked list row of 2-8 plain options, top level or one submenu down, its values the row's
    options one to one, its top row in the page scan and not greyed, offered in Stills, never-open nowhere, nothing
    of light (or sound, motion, the mode, the cards, the screen), nor a twin a registration moved already."""
    doc, tree, scanned, cs, twin_of = candidate_world()
    got = {" > ".join(c["path"]): c for c in T.candidates(doc, cs, T.stills_rows(tree), scanned, twin_of, {0x29})}
    ok = sorted(k for k, c in got.items() if c["excluded"] is None)
    assert ok == ["Color Space", "Peaking Display", "Sub > Child", "Unflagged Twin"]
    why = {k: c["excluded"] for k, c in got.items()}
    assert why["Red Eye Reduction"] == "light or the flash"
    assert why["Audio Signals"].startswith("never-open")
    assert why["High ISO NR"] == "its values are not the row's options one to one"
    assert why["Grey Row"] == "greyed in the page scan"
    assert why["Movie Row"].startswith("not offered in Stills")
    assert why["Many"] == "9 options"
    assert why["Top Image"].startswith("an option drawn with symbols")
    assert why["Done Before"] == "a registration moved its copy already"
    assert why["Sub2 > Deeper > Row"] == "deeper than one submenu"
    assert why["Not Walked"].startswith("not a walked list")
    assert got["Sub > Child"]["codes"] == [0, 1] and got["Color Space"]["options"] == ["sRGB", "AdobeRGB"]
    assert T.excluded_by(["Zoom Ring Rotate"], "Zoom").startswith("motion")
    assert T.excluded_by(["Shutter Type"], "Shutter/Silent").startswith("motion")
    assert T.excluded_by(["Grid Line Display"], "Shooting Display") == "what the screen shows (the Shooting Display group)"
    assert T.excluded_by(["Release w/o Card"], "Shutter/Silent") == "the cards and files"
    assert T.excluded_by(["AF Lvl for Crossing"], "AF/MF") is None


def test_the_picks_put_the_unflagged_first_then_spread_over_tabs_and_groups(T):
    """pick: the unflagged twins first; then round robin over the tabs, within a tab over its groups, so no tab takes
    the count before another has had its turn."""
    def c(name, tab, group, twin="flagged"):
        return {"path": [name], "tab": tab, "group": group, "twin": twin}
    pool = [c("s1", "Shooting", "a"), c("s2", "Shooting", "a"), c("s3", "Shooting", "b"), c("f1", "Focus", "x"),
            c("f2", "Focus", "x"), c("e1", "Exposure/Color", "m"), c("u1", "Focus", "x", "unflagged")]
    assert [p["path"][0] for p in T.pick(pool, 5)] == ["u1", "s1", "f1", "e1", "s3"]
    assert len(T.pick(pool, 99)) == len(pool)


def test_the_option_is_the_first_of_the_menu_the_live_record_does_not_hold(T):
    cand = {"record": "0x0020", "options": ["sRGB", "AdobeRGB", "Other"], "codes": [0, 1, 2]}
    assert T.option_for(cand, made_file({0x20: 0}, [{0x20: 0}])) == ("AdobeRGB", 1)
    assert T.option_for(cand, made_file({0x20: 1}, [{0x20: 0}])) == ("sRGB", 0)
    assert T.option_for(cand, made_file({0x20: 7}, [{0x20: 0}])) == ("sRGB", 0), "an unknown code: the first option"


def test_the_survey_names_no_value_and_marks_its_picks(T, tmp_path):
    """survey: the counts, the groups (an unflagged twin's shape and whether its copy equals the live record, never
    the value), the candidates with their option, the picks by path."""
    doc, tree, scanned, cs, twin_of = candidate_world()
    model = [{"rows": [{"label": lab, "greyed": grey}
                       for lab, grey in [("Color Space", False), ("Peaking Display", False), ("Sub", False),
                                         ("Unflagged Twin", False), ("Grey Row", True)]]}]
    doc["settings"] = [s for s in doc["settings"] if s["id"] != 0x2d]        # 0x2d: a twin no setting names
    got = T.survey(doc, cs, tree, model, tmp_path, count=2, evidenced_run="", shapes={"global:0x002d": "boolean"})
    assert got["counts"]["unflagged"] == 1 and got["unflagged"] == [
        {"record": "0x002d", "live_setting": None, "shape": "boolean", "moved_by": [], "set_equals_live": True}]
    assert got["counts"]["candidates_unflagged"] == 0 and got["counts"]["picked"] == 2
    picked = [c for c in got["candidates"] if c.get("picked")]
    assert [c["path"] for c in picked] == got["picked"] and all(c["option"] for c in picked)


# ---------------------------------------------------------------- memreg_run: the plan

def test_the_rows_come_from_the_survey_and_an_unknown_or_excluded_row_stops_the_run(M):
    survey = {"candidates": [{"path": ["A"], "excluded": None}, {"path": ["B", "C"], "excluded": None},
                             {"path": ["D"], "excluded": "light or the flash"}], "picked": [["B", "C"], ["A"]]}
    assert [c["path"] for c in M.survey_rows(survey)] == [["B", "C"], ["A"]]
    assert [c["path"] for c in M.survey_rows(survey, ["A"])] == [["A"]]
    with pytest.raises(SystemExit, match="not among"):
        M.survey_rows(survey, ["Z"])
    with pytest.raises(SystemExit, match="left out by set_twins: light"):
        M.survey_rows(survey, ["D"])
    assert M.expected_keys("ILCE-1M2", 1) == {"set1:0x023c", "set1:0x11ab", "set1:0x11ad"}
    assert M.expected_keys("OTHER", 1) == frozenset()
    filled = made_file({0x23c: 0}, [{0x23c: 4}])
    assert M.slot_filled(filled, "ILCE-1M2", 1)
    assert not M.slot_filled(made_file({0x23c: 0}, [{0x23c: 2}]), "ILCE-1M2", 1), "an empty slot is never registered"


def tab_frame(x0: int, x1: int, y1: int = 50) -> np.ndarray:
    """A made-up slot screen: black, with an orange square (the a1 II's (158, 41, 3)) over the tab row from x0 to x1."""
    a = np.zeros((480, 640, 3), np.uint8)
    a[6:y1, x0:x1 + 1] = (158, 41, 3)
    return a


def test_the_lit_tab_is_placed_by_its_orange_square(M):
    """lit_tab: the square over 224-273 (the frames' tab 1) is tab 1; one tab along (60 px) is 2, the last M4;
    none, a bar too wide for a tab, or a square between two tabs is no tab: the run then sends no Enter."""
    assert M.lit_tab(tab_frame(224, 273)) == "1"
    assert M.lit_tab(tab_frame(284, 333)) == "2"
    assert M.lit_tab(tab_frame(584, 633)) == "M4"
    assert M.lit_tab(np.zeros((480, 640, 3), np.uint8)) is None
    assert M.lit_tab(tab_frame(100, 400)) is None
    assert M.lit_tab(tab_frame(254, 303)) is None
    low = np.zeros((480, 640, 3), np.uint8)
    low[200:240, 224:274] = (158, 41, 3)                                    # orange below the tab row: not a tab
    assert M.lit_tab(low) is None
    patchy = tab_frame(224, 273)                # a square with holes in its fill (the failing frame had a quarter)
    patchy[10:40:3, 230:268:2] = 0
    assert M.lit_tab(patchy) == "1"
    root = paths.a1ii_root()
    for rel, want, x in (("kit2_small_1109/shots/00021_enter.png", "1", (224, 273)),
                         ("kit2_small_1109/shots/00154_enter.png", "1", (224, 273)),
                         ("kit2_small_1109/shots/00282_enter.png", "1", (224, 273)),
                         ("kit2_memtwins/shots/00833_enter.png", "1", (224, 273)),
                         ("kit2_frame_reg/shots/00080_right.png", "2", (284, 333)),
                         ("kit2_frame_reg/shots/00081_right.png", "3", (344, 393))):
        if (root / rel).exists():               # the a1 II's own frames of the slot screen, where this clone has them
            from camkit.frames import load
            assert M.lit_tab(load(root / rel).image) == want, rel
            assert M.tab_box(load(root / rel).image) == x, rel


class SlotCam:
    """A made-up camera on Camera Set. Memory's row: Enter opens the slot screen, whose frames are `images` in turn
    (one per look); every press is kept."""
    def __init__(self, images: list):
        from types import SimpleNamespace
        self.images, self.n, self.pressed, self.kind = list(images), 0, [], "menu"
        self.run = SimpleNamespace(log=lambda *a, **k: None)

    @property
    def frame(self):
        from types import SimpleNamespace
        return SimpleNamespace(image=self.images[min(self.n, len(self.images) - 1)], path=Path(f"{self.n:05d}_x.png"))

    def read(self):
        from types import SimpleNamespace
        return SimpleNamespace(kind=self.kind)

    def press(self, key, **kw):
        self.pressed.append(key)
        self.kind = "unknown"

    def refresh(self, tag):
        self.n += 1


def test_a_lit_tab_that_cannot_be_measured_fails_the_registration_and_no_enter_is_sent(M, monkeypatch):
    """The slot screen's lit tab must be measured as the slot's: when it cannot be, on the first frame and on one fresh
    look, the registration fails and no Enter goes to the slot screen (never a tab assumed: Enter on M1-M4 registers
    to the card, which no settings file puts back); measured on the second look, the run goes on to its Enter."""
    import camkit.live
    import mode_switch
    from prove_run import Failed
    slots = "MR Memory 1 2 3 M1 M2 M3 M4 MENU OK"
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: None)
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(camkit.live, "lit_text", lambda image, path: "MR Camera Set. Memory")
    monkeypatch.setattr(camkit.live, "text_of", lambda cam: slots if cam.pressed else "MR Camera Set. Memory")
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    blank = np.zeros((480, 640, 3), np.uint8)
    said = []
    cam = SlotCam([blank, blank, blank])
    with pytest.raises(Failed, match="could not be measured"):
        M.register_slot(cam, None, None, "1", said.append, ("Camera Set. Memory",))
    assert cam.pressed == ["enter"], "the row's Enter only: none on the slot screen"
    import drive
    monkeypatch.setattr(drive, "highlighted", lambda image, path: "")
    monkeypatch.setattr(drive, "press_decision", lambda *a: ("the made-up guard", False))
    later = SlotCam([blank, tab_frame(224, 273)])
    with pytest.raises(Failed, match="Enter on slot 1 refused: the made-up guard"):
        M.register_slot(later, None, None, "1", said.append, ("Camera Set. Memory",))
    assert later.pressed == ["enter"] and not said


# ---------------------------------------------------------------- memreg_run: the judgement

def judged(M):
    """Three made-up downloads: 0x30 mirrored, 0x31 set but its copy kept the old value, 0x32's setting did not take;
    0x40 an unflagged twin that moved alongside, its copy taking it; 0x41 a live record outside the sets that moved;
    0x50 a set-only record the registration changed; 0x60 a live record only the registration changed; 0x70 in the
    second set, which nothing may change."""
    a_live = {0x30: 0, 0x31: 0, 0x32: 1, 0x40: 0, 0x41: 0, 0x60: 0, 0x70: 0}
    a_set = {0x30: 0, 0x31: 0, 0x32: 1, 0x40: 0, 0x50: 0, 0x70: 0}
    b_live = {**a_live, 0x30: 2, 0x31: 1, 0x40: 5, 0x41: 3}
    c_live = {**b_live, 0x60: 9}
    c_set = {**a_set, 0x30: 2, 0x40: 5, 0x50: 1}
    a = made_file(a_live, [a_set, {0x70: 0}])
    b = made_file(b_live, [dict(a_set), {0x70: 0}])
    c = made_file(c_live, [c_set, {0x70: 1}])
    rows = [{"record": "0x0030", "key": "global:0x0030", "setting": "Thirty", "path": ["Thirty"], "option": "Two",
             "code": 2, "status": "set"},
            {"record": "0x0031", "key": "global:0x0031", "setting": "Thirty-one", "path": ["Sub", "Thirty-one"],
             "option": "One", "code": 1, "status": "set"},
            {"record": "0x0032", "key": "global:0x0032", "setting": "Thirty-two", "path": ["Thirty-two"],
             "option": "Zero", "code": 0, "status": "refused", "notices": ["not available as follows"]}]
    groups = {0x30: "flagged", 0x31: "flagged", 0x32: "flagged", 0x40: "unflagged", 0x50: "set_only"}
    return M.judge(rows, a, b, c, 1, groups), a, c


def test_the_judgement_says_per_row_whether_the_setting_took_and_the_copy_followed(M):
    v, _, _ = judged(M)
    by = {x["setting"]: x for x in v["rows"]}
    assert (by["Thirty"]["verdict"], by["Thirty"]["mirrored"]) == ("mirrored", True)
    assert (by["Thirty-one"]["verdict"], by["Thirty-one"]["live_changed"]) == ("no mirror", True)
    assert by["Thirty-two"]["verdict"] == "the setting did not take" and by["Thirty-two"]["notices"]
    assert by["Thirty"]["record"] == "set:0x0030" and by["Thirty"]["live"] == "global:0x0030"
    assert v["counts"] == {"rows": 3, "set": 2, "took": 2, "mirrored": 1, "no_mirror": 1, "did_not_take": 1,
                           "other_slot_records": 2, "other_slot_unflagged": 1, "live_side_effects": 2,
                           "other_sets_changed": 1}
    assert v["other_slot_records"] == [{"key": "set1:0x0040", "group": "unflagged", "equals_live_after": True},
                                       {"key": "set1:0x0050", "group": "set_only", "equals_live_after": None}]
    assert v["live_side_effects"] == [{"key": "global:0x0040", "twin": True, "mirrored": True},
                                      {"key": "global:0x0041", "twin": False, "mirrored": None}]
    assert v["live_changed_by_registration"] == ["global:0x0060"]
    assert v["other_sets_changed"] == ["set2:0x0070"]
    assert not any(isinstance(x, int) and not isinstance(x, bool) for row in v["other_slot_records"] for x in row.values())


def test_a_copy_that_moved_before_the_registration_is_noted(M):
    a = made_file({0x30: 0}, [{0x30: 0}])
    b = made_file({0x30: 1}, [{0x30: 1}])
    c = made_file({0x30: 1}, [{0x30: 1}])
    row = {"record": "0x0030", "key": "global:0x0030", "setting": "S", "path": ["S"], "option": "O", "status": "set"}
    x = M.judge([row], a, b, c, 1, {})["rows"][0]
    assert x["mirrored"] and "the copy moved before the second registration" in x["notes"]
    unlike = made_file({0x30: 0}, [{0x30: 3}])
    assert "after the baseline registration the copy is unlike the live record" in \
        M.judge([row], unlike, b, c, 1, {})["rows"][0]["notes"]


def test_a_proof_line_per_row_that_took_credits_the_copy_only_when_it_mirrored(M):
    v, a, c = judged(M)
    lines = M.proof_lines(v, 1, "1", {"A": "1_registered-a.DAT", "B": "2_changed-b.DAT", "C": "3_registered-c.DAT"},
                          {"a": {}, "c": {}}, a, c)
    assert [ln["label"] for ln in lines] == ["Two", "One"], "no line for a setting that did not take"
    first, second = lines
    assert first["path"] == [M.MEMORY_ROW, "Thirty"] and first["kind"] == "registration mirror"
    assert (first["record"], first["live"], first["key"], first["index"]) == ("set:0x0030", "global:0x0030",
                                                                              "set1:0x0030", 2)
    assert (first["base"], first["dat"], first["after"], first["changed"]) == ("1_registered-a.DAT",
                                                                               "3_registered-c.DAT",
                                                                               "3_registered-c.DAT",
                                                                               "2_changed-b.DAT")
    assert first["applied"] is True and "not_applied" not in first
    assert first["changes"] == [{"key": "set1:0x0030", "before": 0, "after": 2}]
    assert second["applied"] is False and second["changes"] == [] and "not_applied" in second
    assert M.scrub("'X': 'Y' did not come round in its list (on 'Held')") == "'X': 'Y' did not come round in its list"


# ---------------------------------------------------------------- the session's expected differences

class FakeLink:
    def __init__(self, after: Path):
        self.after, self.uploaded = after, []

    def download(self, tag):
        return self.after

    def upload(self, path):
        self.uploaded.append(path)
        return "uploaded"


def changed_file(tmp_path, name: str, keys: list) -> Path:
    """The sample with records changed (made-up values: each one's first byte moved by one)."""
    cs = camset.read(SAMPLE)
    out = {}
    for section, rid in keys:
        r = cs.get(section, rid)
        out[(section, rid)] = bytes([(r.raw[0] + 1) % 256]) + r.raw[1:]
    p = tmp_path / name
    p.write_bytes(camset.with_values(cs, out))
    return p


def test_records_a_file_cannot_set_are_said_by_key_and_never_make_an_upload(tmp_path, capsys):
    """session.finish with expected: a change in those records alone is said by key, never by value, and uploads
    nothing (an upload could not put it back); with another record changed too, the start file goes up and the
    expected ones are still left out of the count."""
    marks = changed_file(tmp_path, "marks.DAT", [(1, 0x023c), (1, 0x11ad)])
    expected = {"set1:0x023c", "set1:0x11ab", "set1:0x11ad"}
    lk = FakeLink(marks)
    ending = session.finish(lk, SAMPLE, expected=expected, show=0)
    out = capsys.readouterr().out
    assert ending.changes == [] and not ending.uploaded and lk.uploaded == []
    assert "0 records differ" in out and "set1:0x023c, set1:0x11ad" in out
    more = changed_file(tmp_path, "more.DAT", [(1, 0x023c), (0, 0x0489)])
    lk = FakeLink(more)
    ending = session.finish(lk, SAMPLE, expected=expected, show=0)
    assert [c.key for c in ending.changes] == ["global:0x0489"] and ending.uploaded and lk.uploaded == [SAMPLE]
    assert [c.key for c in session.finish(FakeLink(marks), SAMPLE, show=0).changes] == ["set1:0x023c", "set1:0x11ad"]


def test_the_restore_check_leaves_the_expected_records_out_of_its_count(tmp_path, capsys):
    marks = changed_file(tmp_path, "marks.DAT", [(1, 0x023c), (1, 0x11ab)])

    class Linked:
        def __init__(self, run):
            pass

        def __enter__(self):
            return FakeLink(marks)

        def __exit__(self, *exc):
            return False
    kw = {"settle": 0, "ready": 0, "link_class": Linked, "show": 0}
    assert session.verify_restore(None, SAMPLE, expected={"set1:0x023c", "set1:0x11ab"}, **kw) == 0
    assert "besides 2 no settings file sets" in capsys.readouterr().out
    assert session.verify_restore(None, SAMPLE, **kw) == 2


def test_a_camera_run_needs_the_owners_word_for_the_memory_row_and_no_other(M, monkeypatch, tmp_path, capsys):
    """--list needs no allowance; a camera run stops before connecting without --allow "Camera Set. Memory", or with
    an --allow naming any other row, and goes on to prove() with the allowance's words when given it alone."""
    survey = {"camera": "ILCE-1M2_fw4.00", "file": "x.DAT", "picked": [["A"]],
              "candidates": [{"path": ["A"], "excluded": None, "tab": "Shooting", "group": "g", "twin": "flagged",
                              "record": "0x0020", "option": "On"}],
              "counts": {"twins": 1, "flagged": 1, "unflagged": 0, "candidates_unflagged": 0, "set_only": 0,
                         "set_defined": 0}}
    f = tmp_path / "set_twins.json"
    f.write_text(__import__("json").dumps(survey), encoding="utf-8")
    monkeypatch.setattr(M.paths, "run_root", lambda *a, **k: tmp_path)
    monkeypatch.setattr(M.definitions, "active", lambda *a, **k: "def.json")
    monkeypatch.setattr(M, "read_json", lambda p: {"model": "ILCE-1M2", "layouts": [
        {"model": "ILCE-1M2", "firmware": "4.00"}]} if str(p) == "def.json" else survey)
    called = []
    monkeypatch.setattr(M, "prove", lambda a, doc, todo, s, allowance: called.append(allowance) or 0)
    base = ["--survey", str(f)]
    assert M.main(base + ["--list"]) == 0 and not called
    assert "set1:0x023c, set1:0x11ab, set1:0x11ad" in capsys.readouterr().out
    with pytest.raises(SystemExit, match="owner's word"):
        M.main(base)
    with pytest.raises(SystemExit, match="opens no never-open row but"):
        M.main(base + ["--allow", "Camera Set. Memory", "--allow", "Audio Signals"])
    assert M.main(base + ["--allow", "Camera Set. Memory"]) == 0
    assert called and "the owner allowed Camera Set. Memory remotely" in called[0]


def test_the_watcher_notes_an_information_screen_by_its_frame(M):
    """set_row says an information screen after the choice by its frame only (its words go to the run's events.jsonl,
    set_row_information): the spot check's note names the frame and where the words are."""
    from types import SimpleNamespace
    notes, said = [], []
    watch = M.watcher(SimpleNamespace(), notes, said.append)
    watch("   information after the choice, taken with its OK (00042_enter.png; its words are in the run's events.jsonl)")
    assert notes == ["an information screen after the choice (00042_enter.png), taken with its OK: its words are in "
                     "events.jsonl under set_row_information"]
    assert said == ["   an information screen after the choice, taken with its OK"]
