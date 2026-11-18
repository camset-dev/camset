"""An option named from a list row's reading where the row draws an icon OCR reads as text (camkit.match.icon_named) and
mode_switch.set_row choosing such an option: the a1 II's Aspect Ratio list draws a boxed ratio before each ratio, and
its lit bar reads "3:2 3:2" (runs/ILCE-1M2_fw4.00/kit2_a1fin_probe_keep 00082_down.png, 2026-11-17). Made-up cameras;
nothing talks to a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "provers"))
from camkit import match  # noqa: E402

RATIOS = ["3:2", "4:3", "16:9", "1:1"]          # pass 1's labels for Aspect Ratio


@pytest.mark.parametrize("i,label", list(enumerate(RATIOS)))
def test_a_ratio_read_twice_names_that_ratio(i, label):
    """The icon read as the label in front of it: the reading names the label, its radio ring in front or not."""
    assert match.icon_named(RATIOS, f"{label} {label}") == i
    assert match.icon_named(RATIOS, f"o {label} {label}") == i
    assert match.icon_named(RATIOS, label) == i


def test_a_near_miss_names_no_other_ratio():
    """Digits are compared exactly: "1:1" read twice is 1:1, never 16:9; "6:9" (a 1 lost) names no ratio, read once or
    twice; an icon and a label that name two ratios name none."""
    assert match.icon_named(RATIOS, "1:1 1:1") == 3
    assert match.icon_named(RATIOS, "6:9") is None and match.icon_named(RATIOS, "6:9 6:9") is None
    assert match.icon_named(RATIOS, "4:3 16:9") is None
    assert match.icon_named(RATIOS, "") is None


def test_a_plain_list_row_is_named_as_before():
    """A row with no icon: named whole as camkit.match.index_of names it, the radio ring left out; a reading that names
    one option whole is never cut ("Auto Manual" is that option, not Manual)."""
    dial = ["Set with Dial", "Set with Menu"]
    assert match.icon_named(dial, "o Set with Dial") == 0 and match.icon_named(dial, "Set with Menu") == 1
    assert match.icon_named(["Auto", "Manual", "Auto Manual"], "Auto Manual") == 2
    assert match.icon_named(dial, "Set with Wheel") is None


class ListCam:
    """A made-up camera on a menu row whose list holds `options`, its bar read as `bar(option)`; Right opens the list on
    `start`, Down moves the cursor round it, OK chooses and leaves for the menu page."""

    def __init__(self, options, start=0, bar=lambda o: f"{o} {o}"):
        self.options, self.at, self.bar, self.kind = options, start, bar, "menu"
        self.presses, self.logged, self.chosen, self.n = [], [], None, 0
        self.run = SimpleNamespace(log=lambda kind, **f: self.logged.append((kind, f)))

    @property
    def frame(self):
        return SimpleNamespace(path=Path(f"{self.n:05d}_x.png"), image=None)

    def read(self):
        return SimpleNamespace(kind=self.kind)

    def refresh(self, tag):
        return self.read()

    def press(self, key, **kw):
        self.presses.append(key)
        self.n += 1
        if key == "right":
            self.kind = "list"
        elif key == "down":
            self.at = (self.at + 1) % len(self.options)
        elif key == "enter":
            self.chosen, self.kind = self.options[self.at], "menu"


@pytest.fixture
def ms(monkeypatch):
    import mode_switch
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(mode_switch, "bar_text", lambda cam: cam.bar(cam.options[cam.at]))
    monkeypatch.setattr(mode_switch, "list_labels", lambda path, mode="Stills": RATIOS if path == ["Aspect Ratio"] else
                        MOVIE if (path, mode) == (["File Format"], "Movie") else None)
    return mode_switch


@pytest.mark.parametrize("want", RATIOS)
def test_set_row_chooses_a_ratio_its_bar_reads_twice(ms, want):
    """--set "Aspect Ratio=16:9": Down until the bar reading names the option by pass 1's labels for the row
    (list_labels), OK on it; a row already on it is found at once."""
    cam = ListCam(RATIOS)
    ms.set_row(cam, None, None, ["Aspect Ratio"], want, lambda m: None)
    assert cam.chosen == want and cam.presses == ["right"] + ["down"] * RATIOS.index(want) + ["enter"]
    cam = ListCam(RATIOS, start=RATIOS.index(want))
    ms.set_row(cam, None, None, ["Aspect Ratio"], want, lambda m: None)
    assert cam.chosen == want and cam.presses == ["right", "enter"]


def test_set_row_with_no_labels_for_the_row_matches_as_before_and_fails_closed(ms):
    """A row pass 1's map does not hold: the bar is compared with the option as before (the radio ring left out), so a
    doubled reading never comes round and the step stops as now, the bar's text in the run's events alone."""
    from prove_run import Failed
    cam = ListCam(RATIOS)
    with pytest.raises(Failed, match=r"'Made-up Ratio': '16:9' did not come round in its list") as got:
        ms.set_row(cam, None, None, ["Made-up Ratio"], "16:9", lambda m: None)
    assert "3:2" not in str(got.value) and cam.chosen is None
    assert [f["bar"] for k, f in cam.logged if k == "set_row_missed"] == ["3:2 3:2"]
    plain = ListCam(["Set with Dial", "Set with Menu"], bar=lambda o: f"o {o}" if o == "Set with Dial" else o)
    ms.set_row(plain, None, None, ["Made-up Dial"], "Set with Menu", lambda m: None)
    assert plain.chosen == "Set with Menu" and plain.presses == ["right", "down", "enter"]


def test_set_row_never_takes_a_near_miss_for_the_option(ms):
    """A list whose bars read "6:9" (a 1 lost) or "1:1 1:1" never names 16:9: the step goes round and stops."""
    from prove_run import Failed
    cam = ListCam(RATIOS, bar=lambda o: "6:9 6:9" if o == "16:9" else f"{o} {o}")
    with pytest.raises(Failed, match="did not come round"):
        ms.set_row(cam, None, None, ["Aspect Ratio"], "16:9", lambda m: None)
    assert cam.chosen is None


# ---------------------------------------------------------------- the Movie File Format list (2026-11-17)

# the Movie crawl's labels for File Format; each row draws a two-line boxed icon ("XAVC HS" over "8K") before its label,
# and the lit bar reads the icon garbled, then the label whole: "XAVES XAVC S HD" (kit2_breadth_fmt_XAVC_HS_8K
# 00098_down.png, its events' set_row_missed)
MOVIE = ["XAVC HS 8K", "XAVC HS 4K", "XAVC S 4K", "XAVC S HD", "XAVC S-I 4K", "XAVC S-I HD"]
ICON = {"XAVC HS": "XAVHS", "XAVC S": "XAVES", "XAVC S-I": "XAVSI"}      # each icon as garbled as the camera's reading
STILLS = ["RAW", "RAW & JPEG", "JPEG", "HEIF", "RAW & HEIF"]         # a made-up Stills File Format list


def camera_reading(label: str) -> str:
    """A bar as the camera reads it: the icon's top line garbled (ICON), then the label whole."""
    return f"{ICON[label.rsplit(' ', 1)[0]]} {label}"


@pytest.mark.parametrize("i,label", list(enumerate(MOVIE)))
def test_a_movie_format_read_after_its_garbled_icon_names_that_format(i, label):
    """Each of the six as the bar reads it (the icon garbled, then the label whole), and clean, ring-prefixed and doubled
    (the icon read as the label) alike."""
    assert camera_reading(label).split(" ", 1)[1] == label
    for reading in (camera_reading(label), f"o {camera_reading(label)}", label, f"{label} {label}"):
        assert match.icon_named(MOVIE, reading) == i, reading
    assert match.icon_named(MOVIE, "XAVES XAVC S HD") == 3


def test_a_movie_format_never_names_a_near_miss():
    """Whole words, digits exactly: "... XAVC HS 4K" is never XAVC S 4K, "... XAVC S-I HD" never XAVC S HD, 8K never 4K;
    a reading no label ends names none; two labels that both end it name none (fail closed)."""
    assert match.icon_named(MOVIE, "XAVHS XAVC HS 4K") == 1 and match.icon_named(MOVIE, "XAVSI XAVC S-I HD") == 5
    assert match.icon_named(MOVIE, "XAVES XAVC S 8K") is None and match.icon_named(MOVIE, "XAVES XAVC S") is None
    assert match.ending_option(MOVIE, "XAVHS XAVC HS 4K") == 1 and match.ending_option(MOVIE, "XAVSI XAVC S-I HD") == 5
    assert match.ending_option(MOVIE, "XAVES XAVC S 8K") is None
    assert match.ending_option(["4K", "XAVC 4K"], "XAVES XAVC 4K") is None, "two labels end the reading"
    assert match.ending_option(["XAVC S HD"], "XAVC S HD") is None, "a label alone is no icon's leftovers and the label"
    assert match.icon_named(RATIOS, "4:3 16:9") is None and match.icon_named(RATIOS, "16:9 16:9") == 2


# the lit bar of each row of the Movie File Format list as bar_text read it (kit2_breadth_fmt_XAVC_SI_HDb, 00075-00080,
# 2026-11-18): XAVC S-I HD's glued, "S-IHD", on all four passes (00077, 00083, 00089, 00095: the same picture, byte for
# byte), so the walk went round four times and stopped; XAVC S 4K's icon read "4K"
LIT_BARS = {"XAVC HS 8K": "XAVEHS XAVC HS 8K", "XAVC HS 4K": "XAVCHS XAVC HS 4K", "XAVC S 4K": "4K XAVC S 4K",
            "XAVC S HD": "XAVES XAVC S HD", "XAVC S-I 4K": "XAXES- XAVC S-I 4K", "XAVC S-I HD": "XANCS-I XAVC S-IHD"}


@pytest.mark.parametrize("label", MOVIE)
def test_each_lit_bar_as_the_camera_read_it_names_its_own_format(label):
    """The six lit bars as bar_text read them, XAVC S-I HD's with the space before HD lost: each names its own format.
    The label's words are compared joined, as index_of compares a label (spaces aside), from a word's start after the
    icon's leftovers: "XAVC S-IHD" is XAVC S-I HD."""
    assert match.icon_named(MOVIE, LIT_BARS[label]) == MOVIE.index(label)


def test_a_reading_with_a_space_lost_or_split_names_no_near_miss():
    """Spaces aside, letters and digits exactly: "... XAVC S-IHD" is never XAVC S HD nor XAVC S-I 4K, "... XAVC SHD" never
    XAVC S-I HD, "... XAVC S-I4K" never XAVC S-I HD, "... XAVC HS4K" never XAVC S 4K; the label still begins at a word's
    start ("... XAVCS-IHD", glued to its own first word, is the label; "XAVES-XAVC S HD", glued to the icon, names none
    by its ending); two labels that both end it still name none."""
    assert match.icon_named(MOVIE, "XANCS-I XAVC S-IHD") == 5
    assert match.icon_named(MOVIE, "XAVES XAVC SHD") == 3 and match.icon_named(MOVIE, "XAXES- XAVC S-I4K") == 4
    assert match.icon_named(MOVIE, "XAVHS XAVC HS4K") == 1 and match.icon_named(MOVIE, "XAVSI XA VC S-I HD") == 5
    assert match.icon_named(MOVIE, "XANCS-I XAVCS-IHD") == 5
    assert match.ending_option(MOVIE, "XAVES-XAVC S HD") is None
    assert match.icon_named(MOVIE, "XANCS-I XAVC S-IH D") == 5
    for reading in ("XANCS-I XAVC S-IHD", "XAVES XAVC SHD", "XAXES- XAVC S-I4K", "XAVHS XAVC HS4K"):
        assert match.icon_named(MOVIE, reading) == match.ending_option(MOVIE, reading), reading
    assert match.icon_named(MOVIE, "XANCS-I XAVC S-IHK") is None and match.icon_named(MOVIE, "XAVES XAVC S-HD") is None
    assert match.ending_option(["S-IHD", "XAVC S-I HD"], "XANCS-I XAVC S-IHD") is None, "two labels end the reading"
    # the leftovers are the words before where the label begins, however many words OCR made of it
    assert match.icon_named(MOVIE, "XAVC S HD XAVC S-IHD") is None, "its leftovers name XAVC S HD"
    assert match.icon_named(MOVIE, "XAVC HS 8K XA VC S-I HD") is None, "its leftovers name XAVC HS 8K"


def test_set_row_finds_the_glued_lit_bar_on_its_first_pass(ms):
    """The walk of kit2_breadth_fmt_XAVC_SI_HDb, its bars as bar_text read them, the list on XAVC S HD: --set "File
    Format=XAVC S-I HD" goes Down twice and chooses it on the first pass, where it went round four times and stopped."""
    cam = ListCam(MOVIE, start=3, bar=LIT_BARS.get)
    ms.set_row(cam, None, None, ["File Format"], "XAVC S-I HD", lambda m: None, mode="Movie")
    assert cam.chosen == "XAVC S-I HD" and cam.presses == ["right", "down", "down", "enter"]
    for want in MOVIE:
        cam = ListCam(MOVIE, start=3, bar=LIT_BARS.get)
        ms.set_row(cam, None, None, ["File Format"], want, lambda m: None, mode="Movie")
        assert cam.chosen == want


def maps(tmp_path, monkeypatch) -> None:
    """A made-up pass 1 map (a Stills File Format list, STILLS) and a Movie crawl's map (File Format the movie
    formats), where pass3_run and framepos_run's mode_map find them."""
    import json

    import framepos_run
    import pass3_run
    for run, name, labels in (("kit2_pass1", "map_all.json", STILLS), ("kit2_crawl_movie", "map.json", MOVIE)):
        (tmp_path / run).mkdir()
        (tmp_path / run / name).write_text(json.dumps({"rows": [
            {"path": ["File Format"], "kind": "list", "options": [{"index": i, "label": x} for i, x in enumerate(labels)]}]}),
            encoding="utf-8")
    monkeypatch.setattr(pass3_run, "RUN_ROOT", tmp_path)
    monkeypatch.setattr(pass3_run, "PASS1", tmp_path / "kit2_pass1")
    monkeypatch.setattr(framepos_run.paths, "run_root", lambda *a, **k: tmp_path)


def test_a_rows_labels_come_from_the_map_of_the_mode_its_scan_is_in(tmp_path, monkeypatch):
    """list_labels: Stills from pass 1's map, as before (File Format the still image formats); Movie from that mode's
    crawl (framepos_run.mode_map, its row named), so --set "File Format=XAVC HS 8K" on a Movie scan matches the movie
    formats; a mode no crawl maps the row in gives none, and set_row compares as before."""
    import framepos_run
    import mode_switch
    maps(tmp_path, monkeypatch)
    assert mode_switch.list_labels(["File Format"]) == STILLS == mode_switch.list_labels(["File Format"], "Stills")
    assert mode_switch.list_labels(["File Format"], "Movie") == MOVIE
    assert framepos_run.mode_map("Movie", tmp_path, ["File Format"]) == str(tmp_path / "kit2_crawl_movie" / "map.json")
    assert framepos_run.mode_map("Movie", tmp_path) is None, "Focus Area, its own row, is in no made-up crawl"
    assert mode_switch.list_labels(["File Format"], "S&Q") is None
    # the a1 II's pass 1 has no File Format row (Stills' formats sit elsewhere): none in Stills, Movie's still found
    (tmp_path / "kit2_pass1" / "map_all.json").write_text('{"rows": []}', encoding="utf-8")
    assert mode_switch.list_labels(["File Format"]) is None
    assert mode_switch.list_labels(["File Format"], "Movie") == MOVIE


def test_set_row_in_stills_reads_pass_1s_labels_as_before(tmp_path, monkeypatch):
    """A Stills row, the labels pass 1's (list_labels as before): the saved one ring-prefixed, and "RAW & JPEG" never
    names JPEG (its label ends the reading, but the reading is another label whole)."""
    import mode_switch
    maps(tmp_path, monkeypatch)
    monkeypatch.setattr(mode_switch, "find", lambda cam, cycle, model, label: None)
    monkeypatch.setattr(mode_switch, "bar_text", lambda cam: cam.bar(cam.options[cam.at]))
    for want in STILLS:
        cam = ListCam(STILLS, bar=lambda o: f"o {o}" if o == "RAW" else o)
        mode_switch.set_row(cam, None, None, ["File Format"], want, lambda m: None)
        assert cam.chosen == want and cam.presses == ["right"] + ["down"] * STILLS.index(want) + ["enter"]


def test_set_row_chooses_the_movie_format_its_bar_reads_after_the_icon(ms):
    """set_row in Movie: Down until the bar names the option by the Movie map's labels, OK on it; in Stills the same
    readings never name it (the still image formats), and the step stops as before."""
    from prove_run import Failed
    for want in MOVIE:
        cam = ListCam(MOVIE, bar=camera_reading)
        ms.set_row(cam, None, None, ["File Format"], want, lambda m: None, mode="Movie")
        assert cam.chosen == want and cam.presses == ["right"] + ["down"] * MOVIE.index(want) + ["enter"]
    cam = ListCam(MOVIE, bar=camera_reading)
    with pytest.raises(Failed, match="did not come round"):
        ms.set_row(cam, None, None, ["File Format"], "XAVC HS 8K", lambda m: None)


def test_set_hands_set_row_the_mode_the_waiting_switch_left(monkeypatch, tmp_path):
    """mode_switch --set with a switch waiting in Movie (its record's scan_mode): each row is set with the labels of
    that mode (set_row's mode), the scan loaded in it; no camera (every call made up)."""
    import contextlib
    import json

    import mode_switch as M
    (tmp_path / M.KEPT).write_text(json.dumps({"to": "Movie", "scan_mode": "Movie", "start": "x.DAT"}),
                                   encoding="utf-8")
    seen, scans = [], []
    link = SimpleNamespace(download=lambda tag: tmp_path / f"{tag}.DAT")
    for name, value in (("Run", lambda name: SimpleNamespace(dir=tmp_path)),
                        ("in_mode", lambda scan, mode: scans.append(mode) or scan),
                        ("load_scan", lambda scan: (None, None)), ("check_readers", lambda: None),
                        ("eyes_from_config", lambda run: SimpleNamespace(attach=lambda lk: None, close=lambda: None)),
                        ("Link", lambda run: contextlib.nullcontext(link)), ("to_shooting", lambda *a: None),
                        ("LiveCamera", lambda *a, **k: SimpleNamespace()), ("open_menu", lambda cam: None),
                        ("close_screen", lambda cam, lk: None),
                        ("set_row", lambda cam, cycle, model, path, option, say, mode="Stills":
                            seen.append((path, option, mode)))):
        monkeypatch.setattr(M, name, value)
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    monkeypatch.setattr(M.camset, "read", lambda path: {})
    monkeypatch.setattr(M.camset, "diff", lambda a, b: [SimpleNamespace(key="global:0x0200", before=1, after=2)])
    monkeypatch.setattr(sys, "argv", ["mode_switch.py", "--set", "File Format=XAVC HS 8K", "--run", "made_up"])
    M.main()
    assert seen == [(["File Format"], "XAVC HS 8K", "Movie")] and scans == ["Movie"]
