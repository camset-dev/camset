"""The engineering review of 2026-11-18, track 2 (the mapping pipeline, the provers, the readers): each finding fixed
here has its test, written first to show it. No camera: the provers run against fakes."""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ------------------------------------------------------------------------------------------------ finding 2 (B1)

def test_the_report_never_takes_a_lost_decimal_point_or_fraction_slash_for_agreement():
    """pass2_report compared labels with norm(), which drops "." and "/": 1.3" and 13", F1.1 and F11, 1/250 and 1250
    were one label, so swapped labels passed as "agrees" and two such proofs merged at one index."""
    import pass2_report as R
    verdict, notes = R.judge({'1.3"': 5, '13"': 9, "F1.1": 1, "F11": 2}, {5: '13"', 9: '1.3"', 1: "F11", 2: "F1.1"})
    assert verdict == "conflict" and sorted(n["value"] for n in notes if n["kind"] == "conflict") == [1, 2, 5, 9]
    assert R.judge({'1.3"': 5}, {5: '13"'})[0] != "agrees"
    assert R.judge({"1/250": 7}, {7: "1250"})[0] != "agrees"
    assert R.option_key({"index": 5, "label": '13"'}, {5: {"label": '1.3"'}}) != 5
    assert R.option_key({"index": 5, "label": "1/250"}, {5: {"label": "1250"}}) != 5
    assert not R.alike("F1.1", "F11") and not R.alike('2.5"', '25"') and not R.alike("1/250", "1250")
    # what norm's leniency was for still holds: the same label, its case, spacing, a dot, a sign spelled out
    assert R.judge({"5 Img.": 3, "-(minus) -> 0 -> +(plus)": 4}, {3: "5 img", 4: "-→0→+"}) == ("agrees", [])
    assert R.option_key({"index": 2, "label": "ISO 100"}, {2: {"label": "ISO100"}}) == 2
    assert R.alike("FINE", "FINE Fine") and R.alike("4:3", "4:3 4:3") and R.alike("F1.1", "F1.1")


# ------------------------------------------------------------------------------------------------ finding 11 (B3)

class SwitchCam:
    """A LiveCamera for pass3_run.switch: every press recorded; after Enter the screen is `after` ("notice" or
    "menu")."""

    def __init__(self, after: str):
        self.after, self.presses, self.kind = after, [], "menu"
        self.frame = types.SimpleNamespace(path=Path("00042_enter.png"))

    def press(self, key, **kw):
        self.presses.append(key)
        if key == "right":
            self.kind = "list"
        elif key == "enter":
            self.kind = self.after
        elif key == "menu" and self.kind in ("notice", "list"):
            self.kind = "menu"

    def read(self):
        return types.SimpleNamespace(kind=self.kind)

    def cancel_to_menu(self):
        if self.kind not in ("menu", "shooting"):
            self.presses.append("menu")
            self.kind = "menu"


def switch_world(monkeypatch, after: str, notice: str = "", cur: int = 0):
    import pass3_run
    cam = SwitchCam(after)
    monkeypatch.setattr(pass3_run, "LiveCamera", lambda link, hdmi, run: cam)
    monkeypatch.setattr(pass3_run, "same_position", lambda a, b: True)
    monkeypatch.setattr(pass3_run, "go_to", lambda cam, cycle, model, j, label: 0)
    monkeypatch.setattr(pass3_run, "enter_any", lambda cam, path, i: None)
    monkeypatch.setattr(pass3_run, "labels_of",
                        lambda path, mp=None: (["Electronic Shutter", "Mechanical Shutter"], "list"))
    at = {"i": cur}
    monkeypatch.setattr(pass3_run, "option_index", lambda cam, labels, kind: at["i"])
    monkeypatch.setattr(pass3_run, "move_to", lambda cam, cur, k, n, kind: at.update(i=k))
    monkeypatch.setattr(pass3_run, "to_shooting", lambda link, hdmi, why: None)
    monkeypatch.setattr(pass3_run, "notice_text", lambda cam: notice)
    return pass3_run, cam


def test_a_refusal_after_the_blockers_ok_fails_the_switch_in_plain_words(monkeypatch):
    """pass3_run.switch closed any notice after OK and went on: a refusal ("not available as follows ...") left the
    camera unswitched while the walk and the proofs were tagged with the blocker's state."""
    from proving.base import Failed
    b = {"row": ["Shutter Type"], "to": "Mechanical Shutter", "walk": "Long Exposure NR"}
    pass3_run, cam = switch_world(monkeypatch, "notice", "Not available as follows: Shoot Mode   OK")
    with pytest.raises(Failed, match=r"the camera refused 'Mechanical Shutter' \('Not available as follows: Shoot "
                                     r"Mode OK'; 00042_enter.png\): the blocker was not switched"):
        pass3_run.switch(None, None, None, [{"screen": None}], {}, b)
    assert cam.presses == ["menu", "right", "enter", "menu"] and cam.kind == "menu"
    # a question after OK: nothing answered, MENU cancels it before the link may drop
    pass3_run, cam = switch_world(monkeypatch, "notice", "Execute? Cancel OK")
    monkeypatch.setattr(pass3_run.safety, "confirmation", lambda text: "a question" if "?" in text else "")
    with pytest.raises(Failed, match="the camera asked a question"):
        pass3_run.switch(None, None, None, [{"screen": None}], {}, b)
    assert cam.presses == ["menu", "right", "enter", "menu"]
    # an information notice is closed with MENU and the switch goes on; it says the cursor moved
    pass3_run, cam = switch_world(monkeypatch, "notice", "Enters the state with Flash Effect dur Sht. applied OK")
    assert pass3_run.switch(None, None, None, [{"screen": None}], {}, b) is True
    assert cam.presses == ["menu", "right", "enter", "menu"]
    # the list opened on the option already: nothing to change, said so
    pass3_run, cam = switch_world(monkeypatch, "menu", cur=1)
    assert pass3_run.switch(None, None, None, [{"screen": None}], {}, b) is False


def test_a_switch_whose_download_shows_no_record_of_its_row_stops_the_blocker(monkeypatch, capsys):
    """The switched download was printed and never checked: now the blocker stops, nothing walked or proved, and the
    start file goes back on, where no record of a switched row differs from the start."""
    import pass3_run
    from camkit import camset, models
    monkeypatch.setattr(pass3_run, "definition", lambda: {"settings": [
        {"key": "global:0x02dd", "row": ["Shutter Type"], "copies": ["global:0x02df"]},
        {"key": "global:0x0288", "row": ["Long Exposure NR"]}]})

    def change(rid):
        return camset.Change(0, rid, 0, 1)
    assert pass3_run.row_records(["Shutter Type"]) == {"global:0x02dd", "global:0x02df"}
    moved = [(["Shutter Type"], "Mechanical Shutter")]
    assert pass3_run.switch_took([change(0x02df)], moved) == ""
    assert ("did not take: the download after it differs from the start in no record of that row (global:0x02dd, "
            "global:0x02df)") in pass3_run.switch_took([change(0x0288)], moved)
    assert "in no record at all" in pass3_run.switch_took([], [(["Unknown Row"], "On")])
    assert pass3_run.switch_took([], []) == ""                  # nothing moved: nothing to show

    class Link:
        def __init__(self, run):
            self.n = 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def download(self, tag):
            self.n += 1
            return Path(f"0000{self.n}_{tag}.DAT")
    eyes = types.SimpleNamespace(attach=lambda link: None, close=lambda: None)
    walked, restored = [], []
    monkeypatch.setattr(pass3_run, "Link", Link)
    monkeypatch.setattr(pass3_run, "eyes_from_config", lambda run: eyes)
    monkeypatch.setattr(pass3_run, "to_shooting", lambda link, eyes, why: None)
    monkeypatch.setattr(pass3_run.time, "sleep", lambda s: None)
    monkeypatch.setattr(pass3_run.camset, "read", lambda p: types.SimpleNamespace(model=models.A1II, get=lambda *a: None))
    monkeypatch.setattr(pass3_run.camset, "diff", lambda a, b: [change(0x0288)])
    monkeypatch.setattr(pass3_run, "enter_state", lambda link, hdmi, run, cycle, model, b: moved)
    monkeypatch.setattr(pass3_run, "walk_and_prove", lambda b, log: walked.append(b) or 0)
    monkeypatch.setattr(pass3_run, "restore", lambda run, start: restored.append(start.name) or 0)
    blocker = {"row": ["Shutter Type"], "to": "Mechanical Shutter", "walk": "Long Exposure NR"}
    assert pass3_run.run_blockers("run", [], {}, [blocker], None) is True
    assert walked == [] and restored == ["00001_p3-start.DAT"]
    assert "the switch failed: the switch of Shutter Type to 'Mechanical Shutter' did not take" in capsys.readouterr().out
    monkeypatch.setattr(pass3_run.camset, "diff", lambda a, b: [change(0x02dd)])
    restored.clear()
    assert pass3_run.run_blockers("run", [], {}, [blocker], None) is True
    assert walked == [blocker] and restored == ["00001_p3-start.DAT"]
