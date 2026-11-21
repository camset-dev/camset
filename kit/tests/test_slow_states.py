"""No press at S&Q Frame Rate 1fps (2026-11-21): there the a1 II moved two menu tabs for one press sent (kit2_greyrow
04496, 04497), so an Enter could count twice. camkit.slow_states names the state by the definition (the live mode's
name, the setting's name, the value's label), never by bare numbers; runner.session_start refuses before any press of
the run's own; filter_run and take_picture, which make their own start, the same; mode_switch --to refuses a switch
that would land there and --set never sets it. A body whose definition names none of it: silent. Nothing talks to a
camera."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
from camkit import slow_states  # noqa: E402

DOC = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
LIVE, RATE = (0, 0x13bf), (0, 0x0248)          # as the a1 II's definition names them (asserted below)


def reader(live, rate):
    return lambda section, rid: {LIVE: live, RATE: rate}.get((section, rid))


def test_the_a1_iis_definition_names_the_state():
    (st,) = slow_states.states(DOC)
    assert (st["mode"], st["setting"], st["label"]) == ("S&Q", "S&Q Frame Rate", "1fps")
    assert (st["live"], st["live_code"], st["where"], st["code"]) == (LIVE, 2, RATE, 15)
    assert st["row"] == "S&Q Settings > Frame Rate Settings > Frame Rate"


@pytest.mark.parametrize("live, rate, mode, held", [
    (2, 15, None, True),            # S&Q, 1fps
    (2, 2, None, False),            # S&Q, 120fps
    (0, 15, None, False),           # Stills with the file's S&Q rate at 1fps: not in that state now
    (0, 15, "S&Q", True),           # ... but a switch to S&Q would land there
    (0, 15, "Movie", False),
    (3, 15, None, False),           # Time-lapse: the S&Q rate is not its rate (nothing known of its own)
])
def test_the_state_is_held_by_the_mode_and_the_rate(live, rate, mode, held):
    assert (slow_states.held(DOC, reader(live, rate), mode) is not None) is held


def test_a_definition_that_names_none_of_it_is_silent():
    no_live = {**DOC, "camera": {**DOC["camera"], "live_mode": {}}}
    renamed = {**DOC, "settings": [{**s, "name": "Frame Rate"} if s["key"] == "global:0x0248" else s
                                   for s in DOC["settings"]]}
    no_label = {**DOC, "settings": [{**s, "values": [v for v in s["values"] if v[1] != "1fps"]}
                                    if s["key"] == "global:0x0248" else s for s in DOC["settings"]]}
    for doc in (no_live, renamed, no_label, {}):
        assert slow_states.states(doc) == []
        assert slow_states.held(doc, reader(2, 15)) is None


def test_a_file_that_cannot_be_read_is_silent(tmp_path):
    f = tmp_path / "00001_before.DAT"
    f.write_bytes(b"not a settings file")
    assert slow_states.refusal(DOC, f) == ""
    assert slow_states.refusal(DOC, tmp_path / "gone.DAT") == ""


def test_the_message_says_what_was_seen_why_and_what_to_do(monkeypatch):
    monkeypatch.setattr(slow_states, "file_reader", lambda path: reader(2, 15))
    why = slow_states.refusal(DOC, "x.DAT", doing="greyrow_run.py")
    assert why.startswith("greyrow_run.py found the camera in S&Q mode with S&Q Frame Rate at 1fps.")
    for words in ("act on one button press twice", "Nothing was pressed",
                  "set S&Q Frame Rate to any other rate on the camera by hand",
                  "MENU > S&Q Settings > Frame Rate Settings > Frame Rate", "kit/tools/upload_check.py FILE"):
        assert words in why
    monkeypatch.setattr(slow_states, "file_reader", lambda path: reader(0, 15))
    assert "would put the camera in S&Q mode" in slow_states.refusal(DOC, "x.DAT", mode="S&Q")
    assert slow_states.refusal(DOC, "x.DAT") == ""


def test_set_never_sets_the_state():
    path = ["S&Q Settings", "Frame Rate Settings", "Frame Rate"]
    assert "the kit never sets it" in slow_states.sets_state(DOC, path, "1fps")
    assert slow_states.sets_state(DOC, path, "2fps") == ""
    assert slow_states.sets_state(DOC, ["Movie Settings", "Frame Rate"], "1fps") == ""


# ---------------------------------------------------------------- where it is judged

class Link:
    def __init__(self, path):
        self.path, self.downloads = path, 0

    def download(self, tag):
        self.downloads += 1
        return self.path


def test_session_start_refuses_before_any_press_of_the_run(monkeypatch, capsys):
    import runner
    monkeypatch.setattr(runner, "definition", lambda: DOC)
    monkeypatch.setattr(slow_states, "file_reader", lambda path: reader(2, 15))
    seen = []
    with pytest.raises(SystemExit) as e:
        runner.session_start(Link(Path("00001_before.DAT")), None, reach=lambda link, eyes, why: seen.append("reach"),
                             prepare=lambda start: seen.append("prepare"), lock=lambda eyes, since: seen.append("lock"))
    assert e.value.code == runner.EXIT_REFUSED
    assert seen == ["reach"]                        # nothing after the download: no prepare, no wait, no press
    assert "S&Q Frame Rate at 1fps" in capsys.readouterr().out
    monkeypatch.setattr(slow_states, "file_reader", lambda path: reader(2, 2))
    start = runner.session_start(Link(Path("00002_before.DAT")), None, reach=lambda link, eyes, why: None,
                                 lock=lambda eyes, since: None, say=False)
    assert start.name == "00002_before.DAT"


def test_every_entry_that_makes_its_own_start_judges_it():
    """The entries that open a link and press without runner.session_start (the rest pass it): each judges its start
    download (shootmode_run, whose later links press with none, its --start file for every family it proves, before
    the link opens); upload_check, identify, sdk_set, sdk_run and hdmi_watch press nothing; selftest presses MENU
    alone."""
    for rel in ("kit/provers/filter_run.py", "kit/tools/take_picture.py", "kit/provers/shootmode_run.py"):
        assert "slow_or_exit(" in (ROOT / rel).read_text(encoding="utf-8"), rel


def test_mode_switch_refuses_a_switch_that_would_land_there_and_a_set_of_it(monkeypatch):
    import mode_switch
    monkeypatch.setattr(slow_states, "file_reader", lambda path: reader(0, 15))
    assert "would put the camera in S&Q mode" in mode_switch.switch_refused(DOC, Path("x.DAT"), "S&Q Motion")
    assert mode_switch.switch_refused(DOC, Path("x.DAT"), "Movie") == ""
    monkeypatch.setattr(slow_states, "file_reader", lambda path: reader(0, 2))
    assert mode_switch.switch_refused(DOC, Path("x.DAT"), "S&Q Motion") == ""
    assert "the kit never sets it" in mode_switch.set_refused(DOC, ["S&Q Settings > Frame Rate Settings > Frame Rate=1fps"])
    assert mode_switch.set_refused(DOC, ["S&Q Settings > Frame Rate Settings > Frame Rate=2fps"]) == ""
