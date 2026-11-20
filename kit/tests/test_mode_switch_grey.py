"""mode_switch --set never chooses an option drawn grey (the owner's rule: a greyed entry is never entered to choose it;
the camera's Help says why, under the C4 guard; never Enter): set_row reads the option under the cursor on the frame it
is about to press Enter on, by the provers' own reading (proving.greyed.drawing), and refuses an option drawn grey or
one whose drawing cannot be told, leaving the list with MENU and nothing else pressed on it. A row drawn grey is not
opened at all. Made-up cameras (test_icon_named's ListCam) and two of the camera's own frames; nothing talks to a
camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
sys.path.insert(2, str(ROOT / "kit" / "tests"))
from camkit import paths, screen  # noqa: E402
from camkit.frames import load  # noqa: E402
from test_icon_named import MOVIE, ListCam, LIT_BARS  # noqa: E402

A1 = paths.a1ii_root()


class MenuListCam(ListCam):
    """ListCam whose MENU closes the list back onto the menu page."""

    def press(self, key, **kw):
        super().press(key, **kw)
        if key == "menu":
            self.kind = "menu"


@pytest.fixture
def ms(monkeypatch):
    import mode_switch
    from proving import greyed
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(mode_switch, "bar_text", lambda cam: cam.bar(cam.options[cam.at]))
    monkeypatch.setattr(mode_switch, "list_labels", lambda path, mode="Stills": MOVIE)
    monkeypatch.setattr(mode_switch, "row_drawn", lambda cam: (False, 240.0))
    asked = []

    def by_help(cam, name, label, back):
        asked.append((name, label, back()))
        return greyed.Reason({"row": "Proxy Recording"}, "help", "00009_c4.png", label)
    monkeypatch.setattr(greyed, "by_help", by_help)
    monkeypatch.setattr(mode_switch, "help_refused", lambda kind, image: "")
    mode_switch.ASKED = asked
    return mode_switch


def drawn(grey_of):
    """option_drawn for a MenuListCam: grey_of(option) is True, False or None (cannot be told)."""
    from proving import greyed

    def option_drawn(cam):
        g = grey_of(cam.options[cam.at])
        return g, greyed.Drawing(g, {True: 120.0, False: 240.0, None: 170.0}[g], None, {"not_asked": "a list"})
    return option_drawn


def test_an_option_drawn_grey_is_not_chosen_help_says_why_and_menu_closes_the_list(ms, monkeypatch):
    """--set "File Format=XAVC S-I HD" with that option drawn grey: the cursor reaches it as before, the camera's Help
    is asked on it (the list back on it after), then MENU; no Enter at all, and the refusal says what it is, that it is
    drawn grey, what Help said, and what was pressed."""
    from prove_run import Failed
    monkeypatch.setattr(ms, "option_drawn", drawn(lambda o: o == "XAVC S-I HD"))
    cam = MenuListCam(MOVIE, start=3, bar=LIT_BARS.get)
    with pytest.raises(Failed) as e:
        ms.set_row(cam, None, None, ["File Format"], "XAVC S-I HD", lambda m: None, mode="Movie")
    why = str(e.value)
    assert cam.presses == ["right", "down", "down", "menu"] and cam.chosen is None
    assert "'XAVC S-I HD' is drawn grey in its list" in why and "not chosen" in why
    assert "blocked by Proxy Recording" in why and "nothing was pressed on it but" in why and "MENU" in why
    assert ms.ASKED == [("File Format", "XAVC S-I HD", True)]


def test_an_option_whose_drawing_cannot_be_told_is_refused_with_no_guess(ms, monkeypatch):
    """Neither eye can tell (the pixels between the lines, no reader on a list): refused like a grey one, no Help (it is
    not known grey), MENU only."""
    from prove_run import Failed
    monkeypatch.setattr(ms, "option_drawn", drawn(lambda o: None if o == "XAVC HS 4K" else False))
    cam = MenuListCam(MOVIE, start=3, bar=LIT_BARS.get)
    with pytest.raises(Failed, match="whether 'XAVC HS 4K' is drawn grey cannot be told"):
        ms.set_row(cam, None, None, ["File Format"], "XAVC HS 4K", lambda m: None, mode="Movie")
    assert "enter" not in cam.presses and cam.presses[-1] == "menu" and ms.ASKED == []


def test_where_the_screen_draws_no_help_button_help_is_not_asked(ms, monkeypatch):
    from prove_run import Failed
    monkeypatch.setattr(ms, "option_drawn", drawn(lambda o: o == "XAVC S-I HD"))
    monkeypatch.setattr(ms, "help_refused", lambda kind, image: "the footer shows no help button")
    cam = MenuListCam(MOVIE, start=3, bar=LIT_BARS.get)
    with pytest.raises(Failed, match="the camera's Help was not asked: the footer shows no help button"):
        ms.set_row(cam, None, None, ["File Format"], "XAVC S-I HD", lambda m: None, mode="Movie")
    assert ms.ASKED == [] and "enter" not in cam.presses and cam.presses[-1] == "menu"


def test_an_option_drawn_white_is_chosen_as_before(ms, monkeypatch):
    monkeypatch.setattr(ms, "option_drawn", drawn(lambda o: o == "XAVC S-I HD"))
    cam = MenuListCam(MOVIE, start=3, bar=LIT_BARS.get)
    ms.set_row(cam, None, None, ["File Format"], "XAVC S-I 4K", lambda m: None, mode="Movie")
    assert cam.chosen == "XAVC S-I 4K" and cam.presses == ["right", "down", "enter"] and ms.ASKED == []


def test_a_row_drawn_grey_is_not_opened(ms, monkeypatch):
    """The lit row read drawn grey on the menu page (proving.greyrow.row_grey): no Right on it (the camera's notice is
    greyrow_run's to ask, after its Help), nothing pressed; a row whose drawing cannot be told opens as before."""
    from prove_run import Failed
    monkeypatch.setattr(ms, "option_drawn", drawn(lambda o: False))
    monkeypatch.setattr(ms, "row_drawn", lambda cam: (True, 118.3))
    cam = MenuListCam(MOVIE, start=3, bar=LIT_BARS.get)
    with pytest.raises(Failed, match="the row is drawn grey"):
        ms.set_row(cam, None, None, ["File Format"], "XAVC S-I 4K", lambda m: None, mode="Movie")
    assert cam.presses == []
    monkeypatch.setattr(ms, "row_drawn", lambda cam: (None, None))
    cam = MenuListCam(MOVIE, start=3, bar=LIT_BARS.get)
    ms.set_row(cam, None, None, ["File Format"], "XAVC S-I 4K", lambda m: None, mode="Movie")
    assert cam.chosen == "XAVC S-I 4K"


@pytest.mark.parametrize("name, grey", [("14373_down.png", True), ("14389_up.png", False)])
def test_option_drawn_reads_the_cameras_frames_as_the_provers_do(name, grey):
    """Flash Sync Spd. Prty.'s list on the camera (kit2_pass2): On drawn grey with Electronic Shutter, Off white, as
    test_finish_kit's drawn_grey test reads them; option_drawn gives the same through proving.greyed.drawing."""
    import mode_switch
    f = A1 / "kit2_pass2" / "shots" / name
    if not f.exists():
        pytest.skip(f"{f.name} is not here")
    frame = load(f)
    got, d = mode_switch.option_drawn(SimpleNamespace(frame=frame, read=lambda: screen.read(frame)))
    assert got is grey and d.pixels is grey


def test_a_refused_option_stops_the_set_with_status_1_and_no_after_set_download(monkeypatch, tmp_path):
    """The run's own exit: a refusal is a Failed, so --set says it, exits 1 (the chains' check then finds no
    after-set download: the set did not take) and leaves the switch waiting for its --restore."""
    import contextlib
    import json

    import mode_switch as M
    (tmp_path / M.KEPT).write_text(json.dumps({"to": "Movie", "scan_mode": "Movie", "start": "x.DAT"}),
                                   encoding="utf-8")
    downloads, said = [], []
    link = SimpleNamespace(download=lambda tag: downloads.append(tag) or tmp_path / f"{tag}.DAT")

    def refused(cam, cycle, model, path, option, say, mode="Stills"):
        raise M.Failed("File Format=XAVC S-I HD: 'XAVC S-I HD' is drawn grey in its list, so it was not chosen")
    for name, value in (("Run", lambda name: SimpleNamespace(dir=tmp_path)), ("in_mode", lambda scan, mode: scan),
                        ("load_scan", lambda scan: (None, None)), ("check_readers", lambda: None),
                        ("eyes_from_config", lambda run: SimpleNamespace(attach=lambda lk: None, close=lambda: None)),
                        ("Link", lambda run: contextlib.nullcontext(link)), ("to_shooting", lambda *a: None),
                        ("LiveCamera", lambda *a, **k: SimpleNamespace()), ("open_menu", lambda cam: None),
                        ("close_screen", lambda cam, lk: None), ("set_row", refused),
                        ("session_start", lambda link, hdmi, *a, **k: tmp_path / "before-set.DAT")):
        monkeypatch.setattr(M, name, value)
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    monkeypatch.setattr(sys, "argv", ["mode_switch.py", "--set", "File Format=XAVC S-I HD", "--run", "made_up"])
    monkeypatch.setattr("builtins.print", lambda *a, **k: said.append(" ".join(map(str, a))))
    with pytest.raises(SystemExit) as e:
        M.main()
    assert e.value.code == 1 and "after-set" not in downloads and (tmp_path / M.KEPT).exists()
    assert any("is drawn grey in its list" in s for s in said)
