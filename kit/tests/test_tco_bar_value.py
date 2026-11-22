"""Time Code Output's one Right, replayed through the real ask-why path on its recorded frames (2026-11-21).
ask_why_tl_tco asked HDMI Output Settings > Time Code Output in Time-lapse P and S&Q Motion P, over HDMI and OSD eyes:
drawn grey, its Help names no reason ("This function is currently disabled."), and every line ended "help only, no Right
sent" (kit2_greyrow greyrows.jsonl 52, 218 to 221): OCR reads the grey label lit as "Time Code Outputa" (one stray letter
glued on; its value "Off" a line of its own), so bar_label found no label and open_refused withheld the Right. Now the
row's label stands where OCR glued ONE letter onto it and the second reader reads the bar as that label exactly
(proving.greyrow.glued_label): two signs. The frames: kit2_greyrow 04405 the row lit and grey, 04406 and 04407 its
Help, 04409 back on the row after Help's OK (Time-lapse P, HDMI eyes); behind the one Right, the notice another grey row
brought up (00056, Focus Mode's), left with MENU. A white row (04400, Output Resolution) gets nothing pressed. A real
LiveCamera over those frames (replay_world); nothing talks to a camera."""
import hashlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "tests"))
from replay_world import FrameWorld, camera, shot  # noqa: E402

G = "kit2_greyrow/shots/"
PATH = ["HDMI Output Settings", "Time Code Output"]


def graph() -> dict:
    return {"row": (shot(G + "04405_grey-row.png"), {"c4": "help1"}),
            "help1": (shot(G + "04406_c4.png"), {"down": "help2", "enter": "back", "up": "help1"}),
            "help2": (shot(G + "04407_down.png"), {"down": "help2", "enter": "back", "up": "help1"}),
            "back": (shot(G + "04409_enter.png"), {"right": "notice"}),
            "notice": (shot(G + "00056_right.png"), {"menu": "back"}),
            "white": (shot(G + "04400_down.png"), {})}


@pytest.fixture
def ask(monkeypatch, tmp_path):
    from camkit import live, vlm

    def run(start="row", reads=None, path=PATH):
        said = {hashlib.sha1(shot(G + n).read_bytes()).hexdigest(): lab for n, lab in (reads or {}).items()}

        def ask_role(role, image, prompt, timeout=None, **kw):
            lab = said.get(hashlib.sha1(image).hexdigest())
            if lab is None:
                raise RuntimeError("the replay's reader says nothing on this frame")
            return {"rows": [{"label": lab, "highlighted": True}]}
        monkeypatch.setattr(vlm, "ask_role", ask_role)
        monkeypatch.setattr(live, "ask_role", ask_role, raising=False)
        from proving import greyrow
        w = FrameWorld(graph(), start)
        cam = camera(w, tmp_path)
        seen = SimpleNamespace(seen=lambda p: True, unseen=lambda p: ())
        line = greyrow.ask_why(cam, path, seen=seen, tried=set(), labels={"Focus Mode Dial"}, say=lambda m: None)
        return line, [k for k, _ in w.sent]
    return run


def test_the_grey_row_gets_its_one_right_where_the_second_reader_reads_its_label(ask):
    line, keys = ask(reads={"04409_enter.png": "Time Code Output"})
    assert keys[0] == "c4" and keys.count("right") == 1 and keys[-1] == "menu", keys
    assert line["right"] is True and line["outcome"] == "notice", line
    assert line["after"]["left_by"] == "menu" and line["notice"]["text"].startswith("This operation or setting")
    assert line["blocker"]["row"] == "Focus Mode Dial"                   # the notice's reading after the Right


@pytest.mark.parametrize("reads", [{"04409_enter.png": "Time Code Outputs"}, {}], ids=["another label", "silent"])
def test_without_the_reader_reading_the_label_no_right_goes(ask, reads):
    line, keys = ask(reads=reads)
    assert "right" not in keys and line["outcome"] == "help only" and line["right"] is False, (line, keys)


def test_a_row_drawn_white_gets_nothing_pressed(ask):
    line, keys = ask(start="white", reads={"04400_down.png": "Output Resolution"},
                     path=["HDMI Output Settings", "Output Resolution"])
    from proving import greyrow
    assert keys == [] and line["outcome"] == greyrow.NOT_GREY, (line, keys)


@pytest.mark.parametrize("lit, said, want", [
    ("Time Code Outputa Off", "Time Code Output", "Time Code Output"),
    ("Time Code Outputa", "Time Code Output", "Time Code Output"),
    ("Time Code Outputab Off", "Time Code Output", None),          # two letters glued: no slip of one
    ("Time Code Outputa Off", "Time Code Outputs", None),
    ("Time Code Outputa Off", "", None),
    ("Proxy Recordings", None, None),                             # no reader: another label, as bar_label says
    ("Proxy Recordings", "Proxy Recordings", None)])
def test_one_glued_letter_and_the_reader_agreeing(lit, said, want):
    from proving import greyrow
    label = "Proxy Recording" if lit.startswith("Proxy") else "Time Code Output"
    assert greyrow.glued_label(lit, label, None if said is None else (lambda: said)) == want
    assert greyrow.bar_label(lit, label) is None
