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
        # the consent the press carried to the camera's own check (LiveCamera.answer_once), used up by it
        self.consents = [*getattr(self, "consents", []), getattr(self, "answer_once", None)]
        self.answer_once = None
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
    monkeypatch.setattr(drive, "press_decision", lambda *a, **k: ("the made-up guard", False))
    later = SlotCam([blank, tab_frame(224, 273)])
    with pytest.raises(Failed, match="Enter on slot 1 refused: the made-up guard"):
        M.register_slot(later, None, None, "1", said.append, ("Camera Set. Memory",))
    assert later.pressed == ["enter"] and not said
    # drive.py's guard passes it: the slot screen, read as no known kind, gets its Enter with the run's --allow as consent,
    # in drive.py's judgement and at the camera's own check (answer_once); the row's opening carries none (review, P1)
    judged = []
    monkeypatch.setattr(drive, "press_decision", lambda *a, **k: judged.append(k.get("consent")) or ("", True))
    goes = SlotCam([blank, tab_frame(224, 273)])
    M.register_slot(goes, None, None, "1", said.append, ("Camera Set. Memory",))
    assert goes.pressed == ["enter", "enter"] and judged == ["--allow 'Camera Set. Memory'"]
    assert goes.consents == [None, "--allow 'Camera Set. Memory'"]


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


# ---------------------------------------------------------------- --aperture: each F-number registered into the slot

def aperture_file(section: int, value: int) -> Camset:
    """A made-up file whose set `section` and live copies' block for it hold the F-number `value` (F x 100)."""
    sets = [dict() for _ in range(12)]
    block = bytearray(320)
    block[288:290] = value.to_bytes(2, "little")
    sets[section - 1] = {0x0180: Record(0x0180, 320, 1, bytes(block), 0)}
    copies = bytearray(320 * 12)
    at = 288 + 320 * (section - 1)
    copies[at:at + 2] = value.to_bytes(2, "little")
    return Camset(model="TEST-CAM", saved="", sections=[{0x018c: Record(0x018c, 320, 12, bytes(copies), 0)}, *sets])


def test_the_aperture_keys_and_their_reading_for_a_slot(M):
    """A slot's F-number lives in its set's exposure record (byte 288) and in that set's block of the live copies'
    record (the definition's keys: Memory 1 at 288, Memory 3 at 928, each set 320 bytes on)."""
    assert M.aperture_keys(1) == ("set:0x0180@288", "global:0x018c@288")
    assert M.aperture_keys(3) == ("set:0x0180@288", "global:0x018c@928")
    assert M.slot_apertures(aperture_file(1, 560), 1) == {"set:0x0180@288": 560, "global:0x018c@288": 560}
    assert M.slot_apertures(aperture_file(3, 1100), 3)["global:0x018c@928"] == 1100


def test_the_lens_list_is_registered_once_each_the_held_one_last(M):
    assert M.aperture_order([400, 450, 560, 450, 800], 560) == [400, 450, 800, 560]
    assert M.aperture_order([400, 450, 560], 560, only={450, 560}) == [450, 560]
    assert M.aperture_order([400, 450], 999) == [400, 450], "a held value the lens does not list is not registered"


class ApertureLink:
    """The SDK's FNumber as camlink answers it: set, then read back; `refuse` values the camera will not take ("camera
    kept another value", the beyond-lens run's own refusal), `drift` ones it reads back otherwise. `window`: after each
    download (after_download()), FNumber reads display only with none listed and a set answers "not writable now" for
    that many reads and sets (2026-11-21: about 2 to 4 s after every settings download)."""

    def __init__(self, held=560, refuse=(), drift=(), window=0):
        self.current, self.refuse, self.drift, self.sets = held, set(refuse), set(drift), []
        self.window, self.left, self.gets = window, 0, 0

    def after_download(self):
        self.left = self.window

    def set(self, name, value):
        assert name == "FNumber"
        if self.left > 0:
            self.left -= 1
            raise RuntimeError(f"set FNumber {value}: not writable now")
        self.sets.append(value)
        if value in self.refuse:
            raise RuntimeError("camera kept another value")
        self.current = value + 10 if value in self.drift else value

    def get(self, name):
        self.gets += 1
        if self.left > 0:
            self.left -= 1
            return {"current": self.current, "enable": 2, "writable": False, "values": []}
        return {"current": self.current, "enable": 1, "writable": True, "values": [400, 450, 560]}


def aperture_world(link, stop_after=None, records=None):
    """register_apertures' seams: each registration recorded, each download the slot holding the live value (or what
    `records` says for it), a STOP file after `stop_after` registrations."""
    done, said = [], []

    def register():
        done.append(link.current)
        return {"slot_frame": f"{len(done):05d}_enter.png"}

    def download(tag):
        v = (records or {}).get(link.current, link.current)
        return f"{len(done):05d}_{tag}.DAT", aperture_file(1, v)
    return done, said, register, download, (lambda: stop_after is not None and len(done) >= stop_after)


def test_each_f_number_is_set_read_back_registered_and_checked_in_both_records(M):
    link = ApertureLink()
    done, said, register, download, stopped = aperture_world(link)
    lines, not_set, stop = M.register_apertures(link, [400, 450, 560], "1", 1, register, download, stopped, said.append)
    assert done == [400, 450, 560] and not not_set and not stop
    assert [(x["record"], x["index"], x["label"], x["applied"]) for x in lines] == [
        ("set:0x0180@288", 400, "F4", True), ("global:0x018c@288", 400, "F4", True),
        ("set:0x0180@288", 450, "F4.5", True), ("global:0x018c@288", 450, "F4.5", True),
        ("set:0x0180@288", 560, "F5.6", True), ("global:0x018c@288", 560, "F5.6", True)]
    assert all(x["kind"] == M.KIND and "live" not in x for x in lines), "mirror lines with no live record"
    assert lines[2]["base"] == lines[0]["dat"], "each proof against the download before it"


def test_a_value_the_camera_refuses_or_reads_back_otherwise_registers_nothing(M):
    link = ApertureLink(refuse={400}, drift={450})
    done, said, register, download, stopped = aperture_world(link)
    lines, not_set, _ = M.register_apertures(link, [400, 450, 560], "1", 1, register, download, stopped, said.append)
    assert done == [560] and [x["value"] for x in not_set] == [400, 450]


def test_a_record_that_does_not_take_the_value_is_not_applied(M):
    link = ApertureLink()
    done, said, register, download, stopped = aperture_world(link, records={450: 400})
    lines, _, _ = M.register_apertures(link, [400, 450], "1", 1, register, download, stopped, said.append)
    assert [x["applied"] for x in lines] == [True, True, False, False]
    assert "holds 400, not 450" in lines[2]["not_applied"]


def test_a_stop_falls_between_registrations_only(M):
    """The STOP file is read before each registration and never inside one: the loop ends with every registration
    begun also done, and says so."""
    link = ApertureLink()
    done, said, register, download, stopped = aperture_world(link, stop_after=2)
    lines, _, stop = M.register_apertures(link, [400, 450, 560], "1", 1, register, download, stopped, said.append)
    assert stop and done == [400, 450] and len(lines) == 4
    assert any("stopped before F-number F5.6" in s for s in said)


def test_the_live_aperture_is_put_back_and_read_back(M):
    said = []
    link = ApertureLink(held=400)
    assert M.put_back_aperture(link, 560, said.append) and link.current == 560
    link = ApertureLink(drift={560})
    assert not M.put_back_aperture(link, 560, said.append) and "sdk_set.py FNumber=560" in said[-1]


def test_an_empty_slot_is_registered_only_with_its_own_flag(M):
    """slot_refused: an empty slot is refused (a registration fills it for good: no settings file empties it) unless
    --fill-empty-slot, the owner's word of 2026-11-20 for the aperture run, which says the slot stays registered."""
    empty = made_file({}, [{0x023c: 2}])
    filled = made_file({}, [{0x023c: 4}])
    assert "empty in the start file" in M.slot_refused(empty, "ILCE-1M2", 1, "1", fill_empty=False)
    assert M.slot_refused(empty, "ILCE-1M2", 1, "1", fill_empty=True) == ""
    assert M.slot_refused(filled, "ILCE-1M2", 1, "1", fill_empty=False) == ""


def test_the_f_numbers_asked_but_not_offered_are_said_and_never_set(M):
    """--values names F-numbers; only those the lens offers (the camera's list at the run's start) are set, the rest
    recorded as not offered."""
    assert M.not_offered([400, 450, 560], {450, 1100, 3200}) == [1100, 3200]
    assert M.not_offered([400, 450, 560], None) == []


def test_beyond_the_lens_the_tables_other_f_numbers_are_tried_once_each(M):
    """--beyond-lens (the owner's word of 2026-11-20: "if you can get the camera to do f-numbers out the range go for
    it"): the definition table's F-numbers the lens does not offer, its "—" (0) aside, each tried once through the same
    SDK set; one the camera refuses or reads back otherwise (a clamp) is recorded as refused with what it answered,
    never forced, and no registration is made on it."""
    table = [0, 95, 100, 400, 450, 560, 2500, 3200]
    assert M.beyond_lens(table, [400, 450, 560]) == [95, 100, 2500, 3200]
    link = ApertureLink(held=560, refuse={95}, drift={100})
    done, said, register, download, stopped = aperture_world(link)
    lines, refused, _ = M.register_apertures(link, [95, 100, 2500], "1", 1, register, download, stopped, said.append,
                                             word="refused")
    assert done == [2500] and len(lines) == 2
    assert [(x["value"], x["why"].split(":")[0]) for x in refused] == [(95, "refused"), (100, "refused")]
    assert "read back 110" in refused[1]["why"], "what the camera answered is kept"


def test_aperture_needs_the_owners_word_and_lists_without_a_camera(M, monkeypatch, capsys):
    monkeypatch.setattr(M.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(M, "read_json", lambda path: {"model": "ILCE-1M2"})
    monkeypatch.setattr(M.definitions, "with_evidence", lambda doc, *a, **k: doc)
    assert M.main(["--aperture", "--list"]) == 0
    assert "set:0x0180@288 and global:0x018c@288 must hold it" in capsys.readouterr().out
    assert M.main(["--aperture", "--fill-empty-slot", "--list"]) == 0
    said = capsys.readouterr().out
    assert M.NOT_PUT_BACK in said
    for words in ("filled mark", "registration family", "exposure mode", "read M"):
        assert words in M.NOT_PUT_BACK, f"the upload does not put back {words!r}: the console says so"
    with pytest.raises(SystemExit, match="owner's word"):
        M.main(["--aperture"])
    with pytest.raises(SystemExit, match="--aperture"):
        M.main(["--fill-empty-slot", "--list"])


# ---------------------------------------------------------------- the twelve slots (2026-11-21)

def test_the_slots_are_the_camera_files_memory_sets(M):
    """SLOTS: each of the twelve slots --slot names, by its family, tab and file section, as the camera file's
    memory_sets has them (Stills 1-3, Movie 4-6, S&Q 7-9, Time-lapse 10-12)."""
    import json
    sets = json.loads((ROOT / "data" / "ILCE-1M2_fw4.00" / "camera_ILCE-1M2_fw4.00.json").read_text(
        encoding="utf-8"))["memory_sets"]
    got = {}
    for name, (family, tab, section) in M.SLOTS.items():
        got.setdefault(family, []).append(section)
        assert sets["names"][str(section)].endswith(f"Memory {tab}"), name
        assert M.section_of(name) == section
    assert got == sets["modes"]
    assert list(M.SLOTS)[:4] == ["1", "2", "3", "Movie 1"]


# the slot screen's frames the kit has of each slot's tab lit (SEEN_LIT): the run measures them as their slot's tab
SEEN_FRAMES = [("1", "kit2_memreg_tabs_stills/shots/00014_enter.png"), ("2", "kit2_frame_reg/shots/00265_right.png"),
               ("3", "kit2_frame_reg/shots/00266_right.png"), ("Movie 1", "kit2_memreg_tabs_movie/shots/00005_enter.png"),
               ("S&Q 1", "kit2_memreg_tabs_sq_look/shots/00005_enter.png"),
               ("Movie 1", "kit2_memreg_tabs3_mv_look/shots/00005_enter.png"),
               ("Movie 2", "kit2_memreg_tabs3_mv_look/shots/00006_right.png"),
               ("Movie 3", "kit2_memreg_tabs3_mv_look/shots/00007_right.png"),
               ("S&Q 1", "kit2_memreg_tabs3_sq_look/shots/00005_enter.png"),
               ("S&Q 2", "kit2_memreg_tabs3_sq_look/shots/00006_right.png"),
               ("S&Q 3", "kit2_memreg_tabs3_sq_look/shots/00007_right.png"),
               ("Time-lapse 1", "kit2_memreg_tabs3_tl_look/shots/00005_enter.png"),
               ("Time-lapse 2", "kit2_memreg_tabs3_tl_look/shots/00006_right.png"),
               ("Time-lapse 3", "kit2_memreg_tabs3_tl_look/shots/00007_right.png")]


@pytest.mark.parametrize("slot, rel", SEEN_FRAMES)
def test_each_slot_seen_lit_is_measured_as_its_own_tab_on_the_cameras_frame(M, slot, rel):
    from camkit.frames import load
    assert slot in M.SEEN_LIT and rel.split("/")[0] in M.SEEN_LIT[slot]
    f = paths.a1ii_root() / rel
    if not f.exists():
        pytest.skip(f"{rel} is not here")
    assert M.lit_tab(load(f).image) == M.SLOTS[slot][1]


def test_a_slot_whose_tab_has_not_been_seen_lit_is_refused_before_anything_connects(M, monkeypatch):
    """Since memreg_tab_looks3 (2026-11-21) every one of the twelve slots has its tab seen lit; a slot SEEN_LIT did not
    name would get no registration (never a tab assumed) until memreg_run --look-tabs recorded it, said before the
    link."""
    assert set(M.SEEN_LIT) == set(M.SLOTS)
    assert all(M.slot_unseen(s) == "" for s in M.SLOTS)
    monkeypatch.setattr(M, "SEEN_LIT", {k: v for k, v in M.SEEN_LIT.items() if k != "Time-lapse 1"})
    assert "--look-tabs" in M.slot_unseen("Time-lapse 1") and "has not been seen lit" in M.slot_unseen("Time-lapse 1")
    monkeypatch.setattr(M.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(M, "read_json", lambda path: {"model": "ILCE-1M2"})
    monkeypatch.setattr(M.definitions, "with_evidence", lambda doc, *a, **k: doc)
    monkeypatch.setattr(M, "prove_apertures", lambda *a, **k: pytest.fail("no session for an unseen slot"))
    with pytest.raises(SystemExit, match="has not been seen lit"):
        M.main(["--aperture", "--slot", "Time-lapse 1", "--allow", "Camera Set. Memory"])
    with pytest.raises(SystemExit, match="Stills slots only"):
        M.main(["--slot", "Movie 1", "--allow", "Camera Set. Memory"])


def test_the_family_the_camera_is_in_comes_from_the_start_file(M):
    """family_of: the start file's shooting family record (0x13bf on the a1 II: 0 Stills, 1 Movie, 2 S&Q, 3
    Time-lapse); family_refused: a slot of another family than the camera's is refused before any press, and so is
    one where the family cannot be read."""
    movie = made_file({0x13bf: 1}, [])
    assert M.family_of(movie, "ILCE-1M2") == "Movie"
    assert M.family_refused(movie, "ILCE-1M2", "Movie 1") == ""
    assert "in Movie" in M.family_refused(movie, "ILCE-1M2", "1") and "Stills" in M.family_refused(movie, "ILCE-1M2", "1")
    assert M.family_of(made_file({0x13bf: 3}, []), "ILCE-1M2") == "Time-lapse"
    assert "cannot be read" in M.family_refused(made_file({}, []), "ILCE-1M2", "1")
    assert "cannot be read" in M.family_refused(movie, "OTHER-1", "1")


class TabCam:
    """A made-up camera on Camera Set. Memory's row: the first Enter opens the slot screen on tab `start`, each Right
    lights the next tab (or none with stuck=True), the second Enter registers and the menu is back, MENU leaves the slot
    screen. Its frames are tab_frame squares for the lit tab; every press is kept."""
    PLACES = {"1": (224, 273), "2": (284, 333), "3": (344, 393), "M1": (404, 453)}

    def __init__(self, start="1", stuck=False):
        from types import SimpleNamespace
        self.tab, self.stuck, self.pressed, self.kind, self.n = start, stuck, [], "menu", 0
        self.run = SimpleNamespace(log=lambda *a, **k: None)

    @property
    def frame(self):
        from types import SimpleNamespace
        image = tab_frame(*self.PLACES[self.tab]) if self.kind == "unknown" else np.zeros((480, 640, 3), np.uint8)
        return SimpleNamespace(image=image, path=Path(f"{self.n:05d}_x.png"))

    def read(self):
        from types import SimpleNamespace
        return SimpleNamespace(kind=self.kind)

    def press(self, key, **kw):
        self.pressed.append(key)
        self.n += 1
        self.answer_once = None
        if key == "enter":
            self.kind = "menu" if self.kind == "unknown" else "unknown"
        elif key == "right" and not self.stuck:
            self.tab = list(self.PLACES)[list(self.PLACES).index(self.tab) + 1]
        elif key == "menu":
            self.kind = "menu"

    def refresh(self, tag):
        self.n += 1


@pytest.fixture
def slot_world(M, monkeypatch):
    import camkit.live
    import drive
    import mode_switch
    texts = {"screen": "MR Memory 1 2 3 M1 M2 M3 M4 ISO AUTO MENU OK"}
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: None)
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(camkit.live, "lit_text", lambda image, path: "MR Camera Set. Memory")
    monkeypatch.setattr(camkit.live, "text_of", lambda cam: texts["screen"] if cam.kind == "unknown" else
                        ("Registered." if cam.pressed.count("enter") > 1 else "MR Camera Set. Memory"))
    monkeypatch.setattr(drive, "highlighted", lambda image, path: "")
    monkeypatch.setattr(drive, "press_decision", lambda *a, **k: ("", True))
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    return texts


@pytest.mark.parametrize("slot, presses", [("1", ["enter", "enter"]), ("2", ["enter", "right", "enter"]),
                                           ("3", ["enter", "right", "right", "enter"]),
                                           ("Movie 1", ["enter", "enter"])])
def test_the_slot_is_reached_by_right_from_tab_1_each_tab_measured_before_enter(M, slot_world, slot, presses):
    """register_slot: the slot screen opens on tab 1 (every frame the kit has); a Right lights the next tab, measured
    after each (lit_tab), and Enter goes only once the slot's own tab is measured lit. A Movie slot's screen draws no
    word of its family (its icon only): the start file's family says it (family_refused, before the session's
    presses), and the Stills screen check (no Movie, S&Q or Time-lapse word) is a Stills slot's alone."""
    if slot == "Movie 1":
        slot_world["screen"] = "MR Memory 1 2 3 M1 M2 M3 M4 Movie XAVC S HD MENU OK"
    cam = TabCam()
    M.register_slot(cam, None, None, slot, lambda m: None, ("Camera Set. Memory",))
    assert cam.pressed == presses


def test_a_right_that_does_not_light_the_next_tab_stops_before_enter(M, slot_world):
    from prove_run import Failed
    cam = TabCam(stuck=True)
    with pytest.raises(Failed, match="Right from tab 1 lit tab 1, not 2"):
        M.register_slot(cam, None, None, "3", lambda m: None, ("Camera Set. Memory",))
    assert cam.pressed == ["enter", "right"], "no second Right and no Enter on the slot screen"


def test_a_slot_screen_opened_past_the_slots_tab_gets_no_press(M, slot_world):
    """Opened on tab 2 (never seen; a Left is never pressed), slot 1 is refused with no press on the slot screen."""
    from prove_run import Failed
    cam = TabCam(start="2")
    with pytest.raises(Failed, match="opened on tab 2, past tab 1"):
        M.register_slot(cam, None, None, "1", lambda m: None, ("Camera Set. Memory",))
    assert cam.pressed == ["enter"]


def test_the_stills_screen_check_still_refuses_another_familys_screen_for_a_stills_slot(M, slot_world):
    from prove_run import Failed
    slot_world["screen"] = "MR Memory 1 2 3 M1 M2 M3 M4 Movie XAVC S HD MENU OK"
    with pytest.raises(Failed, match="not the Stills memory slots"):
        M.register_slot(TabCam(), None, None, "2", lambda m: None, ("Camera Set. Memory",))


def test_look_tabs_lights_tab_2_and_3_with_right_and_leaves_with_menu_no_enter(M, slot_world):
    """--look-tabs (the frames the unseen slots wait for): the slot screen opened, its lit tab measured, Right twice
    with a measure after each, then MENU; no Enter on the slot screen, nothing registered. A Right that lights no next
    tab ends the look there, MENU still the last press."""
    cam = TabCam()
    looked = M.look_slot_tabs(cam, None, None, "Movie", ("Camera Set. Memory",))
    assert cam.pressed == ["enter", "right", "right", "menu"]
    assert [x["tab"] for x in looked] == ["1", "2", "3"] and all(x["frame"] for x in looked)
    assert [x["box"] for x in looked] == [[224, 273], [284, 333], [344, 393]]
    stuck = TabCam(stuck=True)
    looked = M.look_slot_tabs(stuck, None, None, "Movie", ("Camera Set. Memory",))
    assert stuck.pressed == ["enter", "right", "menu"] and [x["tab"] for x in looked] == ["1", "1"]


def filled_file(tmp_path, name: str, sections: list, also: list = ()) -> Path:
    """The sample (every slot empty: set n:0x023c = 2) with the slots of `sections` marked filled (4), and the records
    `also` names ((section, id)) moved by one, as changed_file moves them (made-up values)."""
    cs = camset.read(SAMPLE)
    out = {(n, 0x023c): bytes([4]) + cs.get(n, 0x023c).raw[1:] for n in sections}
    for section, rid in also:
        r = cs.get(section, rid)
        out[(section, rid)] = bytes([(r.raw[0] + 1) % 256]) + r.raw[1:]
    p = tmp_path / name
    p.write_bytes(camset.with_values(cs, out))
    return p


def test_every_memory_section_s_registration_records_and_s_q_and_time_lapse_s_fourth(tmp_path):
    """camkit.not_by_file.memory_left: NOT_BY_FILE's three records in each of the body's twelve memory sections, and in
    the S&Q and Time-lapse sets (7 to 12) 0x0170 too (the 2026-10-30 log: "0x023c, 0x11ab, 0x11ad and, in S&Q and
    Time-lapse sets, 0x0170"; kit2_memmirror 00316-00325 wrote set7:0x0170, 00427-00436 set10:0x0170). filled_left:
    those of a slot only where the download shows it filled (set n:0x023c = 4); a slot that reads empty tolerates
    nothing. memreg_run's own restore stays strict: its section's three alone."""
    from camkit import not_by_file
    left = not_by_file.memory_left("ILCE-1M2")
    assert len(left) == 12 * 3 + 6 and {"set1:0x023c", "set4:0x023c", "set7:0x11ab", "set12:0x11ad"} <= left
    assert {f"set{n}:0x0170" for n in range(7, 13)} <= left and not {f"set{n}:0x0170" for n in range(1, 7)} & left
    assert not_by_file.memory_left("OTHER-1") == frozenset()
    assert not_by_file.memory_left("ILCE-1M2", (7,)) == {"set7:0x023c", "set7:0x11ab", "set7:0x11ad", "set7:0x0170"}
    assert not_by_file.filled_left_of(SAMPLE) == frozenset(), "the sample's twelve slots read empty"
    both = filled_file(tmp_path, "both.DAT", [1, 7])
    assert not_by_file.filled_left_of(both) == not_by_file.memory_left("ILCE-1M2", (1, 7))
    assert not_by_file.filled_left_of(tmp_path / "missing.DAT") == frozenset()
    assert module("memreg_run", "provers").expected_keys("ILCE-1M2", 7) == {"set7:0x023c", "set7:0x11ab", "set7:0x11ad"}


def test_upload_check_tolerates_a_slot_s_records_only_where_the_camera_shows_it_filled(tmp_path):
    from tools import upload_check as U
    assert U.known_left(SAMPLE) == {"global:0x18cb", "global:0x1126"}, "no camera download: no slot's records"
    filled = filled_file(tmp_path, "filled.DAT", [4])
    got = U.known_left(SAMPLE, filled)
    assert {"global:0x18cb", "global:0x1126", "set4:0x023c", "set4:0x11ab", "set4:0x11ad"} <= got
    assert not any(k.startswith(("set1:", "set7:")) for k in got)


def test_the_restore_check_tolerates_a_filled_slot_s_records_and_nothing_of_an_empty_one(tmp_path, capsys):
    """camkit.session with expected a function of the download (filled_left_of): the restored download shows set 1
    filled and its registration records differ: left out of the count; the same records differing with the slot read
    empty (its mark moved to 3, not 4): every one counted. finish likewise, uploading only for what counts."""
    from camkit import not_by_file
    filled = filled_file(tmp_path, "filled.DAT", [1], also=[(1, 0x11ab)])
    empty = changed_file(tmp_path, "empty.DAT", [(1, 0x023c), (1, 0x11ab)])

    def linked(after):
        class Linked:
            def __init__(self, run):
                pass

            def __enter__(self):
                return FakeLink(after)

            def __exit__(self, *exc):
                return False
        return Linked
    kw = {"settle": 0, "ready": 0, "show": 0}
    assert session.verify_restore(None, SAMPLE, expected=not_by_file.filled_left_of, link_class=linked(filled), **kw) == 0
    assert "besides 2 no settings file sets" in capsys.readouterr().out
    assert session.verify_restore(None, SAMPLE, expected=not_by_file.filled_left_of, link_class=linked(empty), **kw) == 2
    lk = FakeLink(filled)
    assert session.finish(lk, SAMPLE, expected=not_by_file.filled_left_of, show=0).changes == [] and lk.uploaded == []
    lk = FakeLink(empty)
    ending = session.finish(lk, SAMPLE, expected=not_by_file.filled_left_of, show=0)
    assert [c.key for c in ending.changes] == ["set1:0x023c", "set1:0x11ab"] and lk.uploaded == [SAMPLE]


def test_a_prover_session_s_expected_function_reaches_the_session_whole():
    """runner.end_session and prover_session's restore check pass a function of the download through as it is (a set
    as a frozenset, as before: expected_arg)."""
    import runner
    from camkit import not_by_file
    assert runner.expected_arg(not_by_file.filled_left_of) is not_by_file.filled_left_of
    assert runner.expected_arg({"set1:0x023c"}) == frozenset({"set1:0x023c"})


def test_mode_switch_restore_leaves_the_memory_records_out_of_its_count(monkeypatch, tmp_path):
    """mode_switch --restore: its end compare and its restore check take not_by_file.filled_left_of as expected (a
    filled slot's registration records said by key, not counted; an empty slot's counted), so a slot the kept switch's
    session registered does not fail the switch's restore."""
    import json
    import contextlib
    from types import SimpleNamespace
    sys.path.insert(1, str(ROOT / "kit" / "provers"))
    import mode_switch as MS
    (tmp_path / MS.KEPT).write_text(json.dumps({"to": "Movie", "start": str(SAMPLE)}), encoding="utf-8")
    seen = {}
    monkeypatch.setattr(MS, "Run", lambda name: SimpleNamespace(dir=tmp_path))
    monkeypatch.setattr(MS, "eyes_from_config", lambda run: SimpleNamespace(attach=lambda lk: None, close=lambda: None))
    monkeypatch.setattr(MS, "Link", lambda run: contextlib.nullcontext(SimpleNamespace()))
    monkeypatch.setattr(MS, "end_session", lambda link, hdmi, start, why, tag, **kw: seen.setdefault("end", kw) and
                        SimpleNamespace(uploaded=True, after=start))
    monkeypatch.setattr(MS, "restore_checked", lambda run, ending, start, **kw: seen.setdefault("check", kw) or True)
    monkeypatch.setattr(sys, "argv", ["mode_switch.py", "--restore", "--run", "made_up"])
    MS.main()
    from camkit import not_by_file
    assert seen["end"]["expected"] is MS.restore_left and seen["check"]["expected"] is MS.restore_left
    filled = filled_file(tmp_path, "filled.DAT", [7])
    assert MS.restore_left(filled) == not_by_file.memory_left("ILCE-1M2", (7,)) and "set7:0x0170" in MS.restore_left(filled)
    assert MS.restore_left(SAMPLE) == frozenset(), "a slot that reads empty tolerates nothing"


class FNumberLink:
    """The SDK's FNumber and ExposureProgramMode as camlink answers a get: `replies` FNumber states in turn (the last
    repeated), each a dict of enable, writable and values; every read kept."""

    def __init__(self, replies, mode=1):
        self.replies, self.mode, self.reads = list(replies), mode, []

    def get(self, name):
        self.reads.append(name)
        if name == "ExposureProgramMode":
            return {"current": self.mode, "enable": 2, "writable": False, "values": []}
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return {"current": 560, **r}


SETTABLE = {"enable": 1, "writable": True, "values": [400, 450, 560]}
SHOWN_ONLY = {"enable": 2, "writable": False, "values": []}


def test_fnumber_is_read_again_before_the_run_gives_up_and_its_refusal_says_what_the_camera_reported(M, monkeypatch):
    """2026-11-21: both slot-1 chains stopped on "the camera does not take FNumber now (the shooting mode sets it:
    Stills A or M takes it)" with the camera in Stills M (the start file, the HDMI frame): camlink reported FNumber
    display-only (enable 2) with no F-number listed, where every earlier Stills M read had it settable with 16. The run
    reads it again for a while before it gives up (a camera still settling), and the refusal says what the camera
    reported: the flag in words, how many F-numbers it listed, the SDK's exposure mode; never the F-number it held."""
    from prove_run import Failed
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    late = FNumberLink([SHOWN_ONLY, SHOWN_ONLY, SETTABLE])
    assert M.fnumber_settable(late, tries=5)["values"] == [400, 450, 560]
    assert late.reads.count("FNumber") == 3
    never = FNumberLink([SHOWN_ONLY])
    with pytest.raises(Failed) as e:
        M.fnumber_settable(never, tries=4)
    why = str(e.value)
    assert never.reads.count("FNumber") == 4
    assert "display only" in why and "0 F-numbers listed" in why and "ExposureProgramMode reads 1" in why
    assert "aperture ring" in why and "560" not in why and "F5.6" not in why
    movie_p = FNumberLink([SHOWN_ONLY], mode=32848)
    with pytest.raises(Failed, match="ExposureProgramMode reads 32848"):
        M.fnumber_settable(movie_p, tries=1)
    assert M.fnumber_settable(FNumberLink([SETTABLE]), tries=1)["writable"] is True


def test_the_run_works_in_the_mode_it_is_given_so_a_kept_switch_does_not_refuse_it(M, monkeypatch):
    """2026-11-21: memreg_tab_looks2's three looks were refused before connecting ("left the camera in Movie mode, and
    this run works in Stills mode"): memreg_run took no --in. It takes the runner's --in now, and its page scan goes
    with that mode (run_scan: runner.in_mode); an aperture slot's family must be on that mode's menu (Movie on Movie,
    S&Q and Time-lapse on S&Q), refused before anything connects otherwise."""
    monkeypatch.setattr(M.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(M, "read_json", lambda path: {"model": "ILCE-1M2"})
    monkeypatch.setattr(M.definitions, "with_evidence", lambda doc, *a, **k: doc)
    seen = []
    monkeypatch.setattr(M, "prove_apertures", lambda a, doc, allowance: seen.append(("aperture", a.in_mode)) or 0)
    monkeypatch.setattr(M, "look_tabs", lambda a, doc: seen.append(("look", a.in_mode, M.run_scan(a).mode)) or 0)
    allow = ["--allow", "Camera Set. Memory"]
    assert M.main(["--aperture", "--slot", "Movie 1", "--in", "Movie"] + allow) == 0
    assert M.main(["--aperture", "--slot", "S&Q 1", "--in", "S&Q"] + allow) == 0
    assert M.main(["--look-tabs", "--in", "Movie", "--scan", "kit2_page_scan_movie_1118"] + allow) == 0
    assert seen == [("aperture", "Movie"), ("aperture", "S&Q"), ("look", "Movie", "Movie")]
    with pytest.raises(SystemExit, match="on the Movie menu: give --in Movie"):
        M.main(["--aperture", "--slot", "Movie 1"] + allow)
    with pytest.raises(SystemExit, match="on the Stills menu: give --in Stills"):
        M.main(["--aperture", "--slot", "2", "--in", "S&Q"] + allow)
    assert M.menu_of("Time-lapse") == "S&Q" and M.menu_of("Stills") == "Stills"


def test_each_set_waits_for_fnumber_after_a_download_and_none_is_lost_to_the_window(M, monkeypatch):
    """2026-11-21 08:52-09:28: after every settings download FNumber reads display only, and a set answers "not
    writable now", for about 2 to 4 s; the runs set the next F-number 2.0 s after a registration's download and
    counted fifteen values "not offered". Each set now goes after the run's way back to the shooting screen (`ready`)
    and fnumber_settable; a "not writable now" is waited out and tried again, never counted as refused."""
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    link = ApertureLink(held=560, window=3)
    done, said, register, download, stopped = aperture_world(link)

    def downloaded(tag):
        got = download(tag)
        link.after_download()
        return got
    readies = []
    lines, not_set, stop = M.register_apertures(link, [400, 450, 560], "1", 1, register, downloaded, stopped,
                                                said.append, ready=lambda: readies.append(1))
    assert done == [400, 450, 560] and not not_set and not stop
    assert len(lines) == 6 and all(x["applied"] for x in lines)
    assert len(readies) >= 3, "the way back to the shooting screen before each set"
    assert not any("not offered" in s for s in said)


def test_a_set_the_camera_refuses_is_still_a_refusal_but_a_window_that_never_ends_stops_the_run(M, monkeypatch):
    """A refusal other than "not writable" (the camera kept another value) is recorded as before. FNumber that stays not
    writable through every wait stops the registrations with the camera's report (fnumber_settable's Failed), never
    fifteen values counted not offered."""
    from prove_run import Failed
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    link = ApertureLink(held=560, refuse={450})
    done, said, register, download, stopped = aperture_world(link)
    lines, not_set, _ = M.register_apertures(link, [400, 450], "1", 1, register, download, stopped, said.append)
    assert done == [400] and [x["value"] for x in not_set] == [450] and "kept another value" in not_set[0]["why"]
    stuck = ApertureLink(held=560, window=10 ** 6)
    stuck.after_download()
    done, said, register, download, stopped = aperture_world(stuck)
    with pytest.raises(Failed, match="does not take FNumber now"):
        M.register_apertures(stuck, [400, 450], "1", 1, register, download, stopped, said.append)
    assert done == [] and stuck.sets == []


def test_the_put_back_waits_too_and_a_put_back_that_fails_stops_the_queue(M, monkeypatch, capsys):
    """put_back_aperture waits for FNumber as each set does; where it still fails, prove_apertures ends with
    EXIT_UNRESTORED (the live aperture is live state no settings file puts back: decision 15), so the chain and the queue
    stop, saying the one command that puts it back, rather than exit 1 that the queue rolls past."""
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    link = ApertureLink(held=400, window=3)
    link.after_download()
    said = []
    assert M.put_back_aperture(link, 560, said.append) is True and link.current == 560
    stuck = ApertureLink(held=400, window=10 ** 6)
    stuck.after_download()
    assert M.put_back_aperture(stuck, 560, said.append) is False
    assert any("kit/tools/sdk_set.py FNumber=560" in s and "the queue stops" in s for s in said)
    from runner import EXIT_UNRESTORED
    assert M.status_of(back=False, applied=2, lines=2, stopped=False, beyond=False, not_set=0) == EXIT_UNRESTORED
    assert M.status_of(back=True, applied=2, lines=2, stopped=False, beyond=False, not_set=0) == 0
    assert M.status_of(back=True, applied=2, lines=2, stopped=False, beyond=False, not_set=3) == 1
    assert M.status_of(back=True, applied=0, lines=0, stopped=False, beyond=True, not_set=3) == 0
