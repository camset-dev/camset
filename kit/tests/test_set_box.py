"""mode_switch --set for a value in a row's two-box screen (S&Q and Time-lapse Frame Rate Settings, Movie mode,
2026-11-18): the box named as boxes_run names it (the row's path, then the box's name), told from a list row before
the link opens, set through boxes_run's own opening, reading, stepping and OK (its screen's consent), and checked by a
download that one record of that box moved. Made-up cameras, definitions, maps and downloads only: nothing here talks
to a camera, a reader or a network.
"""
import contextlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import boxes_run  # noqa: E402
import mode_switch  # noqa: E402
from camkit import live, safety  # noqa: E402
from test_enter_check import footer_picture, ocr_lines  # noqa: E402

SQ = ["S&Q Settings", "Frame Rate Settings"]
BOX = SQ + ["Rec Frame Rate"]
# the S&Q screen as OCR read it under XAVC HS 4K with the left box on each of its values (kit2_pass2 240066 60p,
# 240067 120p, 240068 24p; 2026-11-17): Up goes 60p, 120p, 24p and comes round, Down the other way (240066-240072)
READINGS = {
    "60p": [("Shooting > Image Qua... > S&0 Frame Rate Settings", 0, 3, 516, 33), ("Sad Rec Frame Rate", 115, 65, 218, 28),
            ("S&Q Frame Rate", 389, 67, 167, 28), ("60р", 191, 189, 53, 38), ("120fps", 425, 189, 95, 36),
            ("x2 Slow Motion", 65, 315, 152, 24),
            ("Shooting time required for 5-second movie recording.", 65, 349, 510, 28),
            ("0 h 00 min 02 s", 67, 383, 146, 24), ("?", 509, 441, 16, 24), ("• OK", 563, 437, 62, 28)],
    "120p": [("Shooting > Image Qua... > S&0 Frame Rate Settings", 0, 3, 516, 33), ("Sad Rec Frame Rate", 115, 65, 218, 28),
             ("Sæd Frame Rate", 389, 67, 167, 28), ("120p", 183, 189, 70, 37), ("120fps", 424, 184, 98, 46),
             ("Shooting time required for 5-second movie recording.", 65, 348, 510, 29),
             ("0 h 00 min 05 s", 67, 382, 146, 26), ("• OK", 563, 437, 62, 28)],
    "24p": [("Shooting > Image Qua... > S&0 Frame Rate Settings", 0, 3, 516, 33), ("Sad Rec Frame Rate", 115, 65, 218, 28),
            ("S&Q Frame Rate", 389, 67, 167, 28), ("24p", 191, 189, 53, 38), ("120fps", 424, 184, 98, 46),
            ("x5 Slow Motion", 65, 317, 150, 21),
            ("Shooting time required for 5-second movie recording.", 65, 349, 510, 28),
            ("0 h 00 min 01 s", 67, 383, 146, 25), ("• OK", 563, 437, 62, 28)]}
UP = {"60p": "120p", "120p": "24p", "24p": "60p"}
DOWN = {v: k for k, v in UP.items()}
# the Time-lapse screen (kit2_pass2 240575): Rec Frame Rate and Interval Time, the screen another row's
TL_READING = [("Shooting > Image Qua... > Frame Rate Settings", 0, 3, 514, 36), ("t Rec Frame Rate", 127, 65, 205, 28),
              ("tInterval Time", 381, 67, 185, 28), ("24p", 191, 189, 53, 38), ("1 s", 455, 189, 40, 30),
              ("Shooting time required for 5-second movie recording.", 65, 349, 510, 28),
              ("0 h 02 min 00 s", 67, 383, 146, 24), ("?", 509, 441, 13, 26)]


def dashes(picture) -> np.ndarray:
    """`picture` with a 7 x 3 px dash in each box, as XAVC HS 8K draws them (kit2_pass2 240050)."""
    a = picture.copy()
    for b, (x0, y0, x1, y1) in enumerate(boxes_run.LAYOUTS["framerate"]):
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        a[cy - 1:cy + 2, cx - 3:cx + 4] = (198, 130, 96) if b == 0 else (96, 96, 96)
    return a


class BoxCam:
    """A made-up camera on the S&Q row: Right opens its boxes (Rec Frame Rate lit), then moves to the right box, Left
    back; Up and Down step the lit left box round READINGS's values; OK leaves with the consent it was handed, kept;
    MENU (close_screen) leaves. `reading` gives the screen's OCR lines from the value shown; `picture` what it draws."""
    def __init__(self, held="60p", reading=None, picture=None):
        self.value, self.lit, self.open, self.presses, self.consents = held, 0, False, [], []
        self.reading = reading or (lambda v: READINGS[v])
        self.answer_once = None
        self.frame = SimpleNamespace(image=footer_picture() if picture is None else picture, path=Path("00001_x.png"))

    def lines(self):
        rows = self.reading(self.value) if self.open else []
        return ocr_lines(rows)

    def press(self, key, **k):
        self.presses.append(key)
        if key == "right":
            self.lit, self.open = (min(1, self.lit + 1), True) if self.open else (0, True)
        elif key == "left":
            self.lit = 0
        elif key in ("up", "down") and self.open and self.lit == 0:
            self.value = (UP if key == "up" else DOWN)[self.value]
        elif key == "enter":
            self.consents.append(self.answer_once)
            self.answer_once, self.open = None, False

    def close(self):
        self.open = False


@pytest.fixture
def boxcam(monkeypatch):
    """boxes_run's camera seams made up for a BoxCam: its OCR lines, which box is lit, the menu, the scan's route, the
    shooting screen and the second reader; nothing reached."""
    monkeypatch.setattr(boxes_run, "lines", lambda cam: cam.lines())
    monkeypatch.setattr(boxes_run, "focus", lambda cam: cam.lit if cam.open else None)
    monkeypatch.setattr(boxes_run, "menu_from_shooting", lambda cam: None)
    monkeypatch.setattr(boxes_run, "scan_position", lambda cam, cycle: 0)
    monkeypatch.setattr(boxes_run, "go_to", lambda *a: True)
    monkeypatch.setattr(boxes_run, "enter_any", lambda cam, path, i: None)
    monkeypatch.setattr(boxes_run, "close_screen", lambda cam, link: cam.close())
    monkeypatch.setattr(boxes_run, "vlm_option", lambda cam: None)
    return BoxCam


# ---------------------------------------------------------------- boxes_run.set_value: one box put on one value


def test_set_value_steps_its_box_to_the_value_and_leaves_with_the_screens_consent(boxcam):
    """Rec Frame Rate from 60p to 24p: the row opened by boxes_run's own opening, the boxes' names read where they are
    drawn (either order given), the box looked at (its values in Down order), then opened again, stepped Down once
    and left with OK under the screen's consent (TwoBoxes, the boxes left first); nothing pressed in the right box."""
    cam = boxcam()
    got = boxes_run.set_value(cam, None, None, None, SQ, ["Frame Rate", "Rec Frame Rate"], "Rec Frame Rate", "24p")
    assert cam.value == "24p" and got["values"] == ["60p", "24p", "120p"] and got["held"] == "60p"
    assert cam.presses == ["right", "up", "up", "up", "down", "down", "down", "right", "down", "enter"]
    [consent] = cam.consents
    assert consent == boxes_run.screen_consent(SQ, ["Rec Frame Rate", "Frame Rate"])
    assert live.two_boxes_refused(consent, ocr_lines(READINGS["24p"]), footer_picture()) == ""


@pytest.mark.parametrize("value,why", [("30p", "not one of its values"), ("60p", "already holds")])
def test_set_value_refuses_a_value_the_box_does_not_offer_or_already_holds(boxcam, value, why):
    """A value not in the box's list as the camera walks it, or the value it holds already: no OK, nothing chosen."""
    cam = boxcam()
    with pytest.raises(boxes_run.Failed, match=why):
        boxes_run.set_value(cam, None, None, None, SQ, ["Rec Frame Rate", "Frame Rate"], "Rec Frame Rate", value)
    assert "enter" not in cam.presses and cam.consents == []


def test_set_value_on_a_dashed_box_presses_nothing_on_it(boxcam):
    """XAVC HS 8K's boxes draw a dash: not offered in this state (NotOffered), nothing but Right pressed."""
    cam = boxcam(reading=lambda v: [r for r in READINGS["60p"] if r[1] not in (191, 425)],
                 picture=dashes(footer_picture()))
    with pytest.raises(boxes_run.NotOffered):
        boxes_run.set_value(cam, None, None, None, SQ, ["Rec Frame Rate", "Frame Rate"], "Rec Frame Rate", "24p")
    assert cam.presses == ["right"]


def test_set_value_on_another_rows_screen_presses_nothing_but_right(boxcam):
    """The boxes' names drawn are not the two the row has (the Time-lapse screen, Interval Time where Frame Rate
    should be), or the footer draws no OK key: the row stops before any Up or Down."""
    cam = boxcam(reading=lambda v: TL_READING)
    with pytest.raises(boxes_run.Failed, match="names drawn above its boxes"):
        boxes_run.set_value(cam, None, None, None, SQ, ["Rec Frame Rate", "Frame Rate"], "Rec Frame Rate", "24p")
    assert cam.presses == ["right"]
    cam = boxcam(picture=footer_picture(keys=("help_only",)))
    with pytest.raises(boxes_run.Failed, match="no OK key drawn"):
        boxes_run.set_value(cam, None, None, None, SQ, ["Rec Frame Rate", "Frame Rate"], "Rec Frame Rate", "24p")
    assert cam.presses == ["right"]


def test_names_drawn_take_each_boxs_longest_name_and_refuse_any_other_pair():
    """camkit.live.names_drawn: the two names in the order the screen draws them, each box's text above it ending with
    its name ("Sad Rec Frame Rate" ends with Frame Rate too: the longer name is its); None where the two boxes do not
    give the two names once each."""
    at = boxes_run.LAYOUTS["framerate"]
    assert live.names_drawn(ocr_lines(READINGS["60p"]), at, ["Frame Rate", "Rec Frame Rate"]) == ["Rec Frame Rate",
                                                                                                   "Frame Rate"]
    assert live.names_drawn(ocr_lines(TL_READING), at, ["Rec Frame Rate", "Interval Time"]) == ["Rec Frame Rate",
                                                                                                "Interval Time"]
    assert live.names_drawn(ocr_lines(TL_READING), at, ["Rec Frame Rate", "Frame Rate"]) is None
    both_short = [r if r[1] != 115 else ("Sad Frame Rate", *r[1:]) for r in READINGS["60p"]]
    assert live.names_drawn(ocr_lines(both_short), at, ["Rec Frame Rate", "Frame Rate"]) is None


# ---------------------------------------------------------------- mode_switch: the box told from a list row


def definition() -> dict:
    """A made-up definition: the S&Q screen's two boxes (two Rec Frame Rate records, one per format, and Frame Rate),
    S&Q's Record Setting, and Time-lapse Settings' two list rows, all on the Movie menu."""
    rows = [("global:0x023e", BOX), ("global:0x0244", BOX), ("global:0x0248", SQ + ["Frame Rate"]),
            ("global:0x0250", ["S&Q Settings", "Record Setting"]),
            ("global:0x1150", ["Time-lapse Settings", "Record Setting"]),
            ("global:0x1160", ["Time-lapse Settings", "Video Light Setting"])]
    return {"settings": [{"key": k, "row": r, "row_mode": "Movie", "values": [[0, "60p"]]} for k, r in rows]}


@pytest.fixture
def maps(tmp_path):
    """boxes_run's proof run beside the run (kit2_pass2's proofs.jsonl): its proofs of the S&Q screen's two boxes (kind
    "list", "boxes": true), and a checklist's proof marked "boxes" (Time-lapse Settings > Record Setting, made up),
    which is no two-box screen's."""
    (tmp_path / boxes_run.PROOF_RUN).mkdir()
    lines = [{"path": BOX, "kind": "list", "index": 1, "label": "24p", "boxes": True},
             {"path": SQ + ["Frame Rate"], "kind": "list", "index": 1, "label": "60fps", "boxes": True},
             {"path": ["Time-lapse Settings", "Record Setting"], "kind": "checklist", "index": 0, "boxes": True}]
    (tmp_path / boxes_run.PROOF_RUN / "proofs.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines),
                                                                 encoding="utf-8")
    return tmp_path


def test_a_path_to_a_box_is_told_from_a_list_rows(maps):
    """two_box: the row holds exactly two boxes in the definition on the menu of that mode, and boxes_run has proved
    them (box_proofs: its own proof lines, never a checklist's); a submenu's list row (Time-lapse Settings > Record
    Setting, two rows under it, the definition alone telling it from no two-box screen) is a list row, set as before.
    The box's records are the definition's at that row and box, every format's."""
    proved = mode_switch.box_proofs(SimpleNamespace(dir=maps / "made_up"))
    assert proved == {tuple(BOX), tuple(SQ + ["Frame Rate"])}
    got = mode_switch.two_box(BOX, "Movie", definition(), proved)
    assert (got["row"], got["box"], sorted(got["names"]), sorted(got["keys"])) == (
        SQ, "Rec Frame Rate", ["Frame Rate", "Rec Frame Rate"], ["global:0x023e", "global:0x0244"])
    assert mode_switch.two_box(["Time-lapse Settings", "Record Setting"], "Movie", definition(), proved) is None
    assert mode_switch.two_box(["S&Q Settings", "Record Setting"], "Movie", definition(), proved) is None
    assert mode_switch.two_box(["File Format"], "Movie", definition(), proved) is None
    assert mode_switch.two_box(BOX, "Movie", definition(), set()) is None, "boxes_run never proved it: no two-box row"


@pytest.mark.parametrize("item,mode,why", [
    ("S&Q Settings > Frame Rate Settings > Shutter=24p", "Movie", "'Shutter' is not one of its two boxes"),
    ("S&Q Settings > Frame Rate Settings > Rec Frame Rate=24p", "Stills", "not a two-box row on the Stills menu"),
    ("S&Q Settings > Frame Rate Settings > Rec Frame Rate=", "Movie", "names no value")])
def test_set_refuses_a_box_no_two_box_row_of_that_mode_has_before_the_link(maps, monkeypatch, tmp_path, no_camera,
                                                                         item, mode, why):
    """--set with a switch waiting in `mode`: a box the row does not have, a two-box row of another mode's menu, or no
    value, stops with what is wrong before the link opens (no_camera: nothing reached)."""
    run = tmp_path / "made_up"
    run.mkdir()
    (run / mode_switch.KEPT).write_text(json.dumps({"to": mode, "scan_mode": mode, "start": "x.DAT"}), encoding="utf-8")
    monkeypatch.setattr(mode_switch, "Run", lambda name: SimpleNamespace(dir=run))
    monkeypatch.setattr(mode_switch, "definition", lambda r: definition())
    monkeypatch.setattr(sys, "argv", ["mode_switch.py", "--set", item, "--run", "made_up"])
    with pytest.raises(SystemExit) as got:
        mode_switch.main()
    assert why in str(got.value.code)


# ---------------------------------------------------------------- mode_switch --set of a box, through a made-up session


class Dat:
    def __init__(self, name, values):
        self.name, self.values = name, values


# what boxes_run.set_value returns for Rec Frame Rate set to 24p from 60p (set_value's test above)
SET = {"values": ["60p", "24p", "120p"], "held": "60p", "box": 0, "names": ["Rec Frame Rate", "Frame Rate"]}


def run_set(monkeypatch, tmp_path, item, set_value, changes, extra=()):
    """mode_switch --set `item` (and `extra`) with a switch waiting in Movie, the link, eyes and camera made up:
    boxes_run.set_value stands in by `set_value`, each download after the start holding the records `changes` names
    for it, in turn ({key: value}); returns (the sets made, the downloads)."""
    run = tmp_path / "made_up"
    run.mkdir(exist_ok=True)
    (run / mode_switch.KEPT).write_text(json.dumps({"to": "Movie", "scan_mode": "Movie", "start": "x.DAT"}),
                                        encoding="utf-8")
    state, downloads, sets = {}, [], []

    def download(tag):
        state.update(changes[min(len(downloads), len(changes) - 1)] if downloads else {})
        downloads.append(Dat(f"{len(downloads):05d}_{tag}.DAT", dict(state)))
        return downloads[-1]
    link = SimpleNamespace(download=download)
    for name, value in (("Run", lambda name: SimpleNamespace(dir=run)), ("definition", lambda r: definition()),
                        ("load_scan", lambda scan: (None, None)), ("check_readers", lambda: None),
                        ("eyes_from_config", lambda r: SimpleNamespace(attach=lambda lk: None, close=lambda: None)),
                        ("Link", lambda r: contextlib.nullcontext(link)), ("to_shooting", lambda *a: None),
                        ("LiveCamera", lambda *a, **k: SimpleNamespace()), ("open_menu", lambda cam: None),
                        ("close_screen", lambda cam, lk: None),
                        ("set_row", lambda cam, cycle, model, path, option, say, mode="Stills":
                            sets.append(("row", path, option)))):
        monkeypatch.setattr(mode_switch, name, value)

    def fake_set(cam, link, cycle, model, path, names, box, value):
        sets.append(("box", path, box, value))
        return set_value(path, names, box, value)
    monkeypatch.setattr(boxes_run, "set_value", fake_set)
    monkeypatch.setattr(mode_switch.time, "sleep", lambda s: None)
    monkeypatch.setattr(mode_switch.camset, "read", lambda d: d.values)
    monkeypatch.setattr(mode_switch.camset, "diff", lambda a, b: [SimpleNamespace(key=k, before=a.get(k), after=v)
                                                                  for k, v in b.items() if a.get(k) != v])
    monkeypatch.setattr(sys, "argv", ["mode_switch.py", "--set", item, *extra, "--run", "made_up"])
    mode_switch.main()
    return sets, downloads


def test_set_puts_the_box_on_its_value_and_checks_that_one_of_its_records_moved(maps, monkeypatch, tmp_path, capsys):
    """--set "S&Q Settings > Frame Rate Settings > Rec Frame Rate=24p", a switch waiting in Movie: boxes_run.set_value
    sets it, then a download says the records that differ, and exactly one moved, one of that box's records (here
    the HS 4K one, global:0x023e); a list row in the same call is set as before."""
    sets, downloads = run_set(monkeypatch, tmp_path, " > ".join(BOX) + "=24p", lambda *a: dict(SET),
                              [{"global:0x023e": 4}], extra=("--set", "S&Q Settings > Record Setting=60M 4:2:0 8bit"))
    assert sets == [("box", SQ, "Rec Frame Rate", "24p"), ("row", ["S&Q Settings", "Record Setting"], "60M 4:2:0 8bit")]
    assert "global:0x023e" in capsys.readouterr().out


@pytest.mark.parametrize("changes,why", [
    ([{}], "no record of Rec Frame Rate moved"),
    ([{"global:0x0248": 3}], "global:0x0248"),
    ([{"global:0x023e": 4, "global:0x0248": 3}], "2 records moved")])
def test_set_of_a_box_stops_when_not_exactly_one_of_its_records_moved(maps, monkeypatch, tmp_path, capsys, changes, why):
    """None moved, another record moved (Frame Rate's), or more than the one: the set stops, exit status 1, the switch
    left waiting for --restore."""
    with pytest.raises(SystemExit) as got:
        run_set(monkeypatch, tmp_path, " > ".join(BOX) + "=24p", lambda *a: dict(SET), changes)
    assert got.value.code == 1 and why in capsys.readouterr().out


@pytest.mark.parametrize("stop", [boxes_run.NotOffered("00050_right.png"), boxes_run.Failed("did not open its boxes"),
                                  safety.Refused("enter: its footer offers no OK")])
def test_a_set_of_a_box_that_stops_exits_1(maps, monkeypatch, tmp_path, capsys, stop):
    """A box not offered (a dash), a row that did not open, a refused OK: said, exit status 1, the switch waiting."""
    def raises(*a):
        raise stop
    with pytest.raises(SystemExit) as got:
        run_set(monkeypatch, tmp_path, " > ".join(BOX) + "=24p", raises, [{}])
    assert got.value.code == 1 and "stopped" in capsys.readouterr().out
