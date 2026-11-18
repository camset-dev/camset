"""optboxes_run: an option of a list row that draws a row of boxes of its own (the a1 II's Zebra Level > Custom 1 and
Custom 2, 2026-11-18): reading the screen, walking a box to its ends, the read-only probe, the proof run with its base,
the OK judged on the screen's own shape (camkit.live.OptionBoxes), the Standard 30 / Range ±5 rule on OSD eyes, and
the exit statuses. Stored frames where runs/ holds them (skipped otherwise); made-up cameras and sessions otherwise.
"""
import contextlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import optboxes_run as O  # noqa: E402
from camkit import live, ocr, paths, safety  # noqa: E402
from camkit.link import StopRequested  # noqa: E402
from exit_status import EXIT_INCOMPLETE, EXIT_REFUSED  # noqa: E402

RUNS = paths.a1ii_root()
# Custom 1 with its Standard box lit at 70 as OCR read it (kit2_look_zebra_a 00014_right.png, OSD eyes)
STD70 = [("& Zebra Level", 129, 10, 206, 38), ("Custom 1", 128, 67, 135, 34), ("100", 37, 85, 34, 22),
         ("100+", 33, 153, 44, 20), ("C1", 41, 217, 25, 21), ("C2", 41, 281, 28, 24), ("Standard", 313, 291, 134, 35),
         ("Std+Range", 173, 357, 169, 40), ("70", 419, 355, 42, 38), ("‡5", 537, 359, 50, 33), ("?", 319, 441, 13, 26),
         ("MENU Cancel", 387, 437, 126, 31), ("• OK", 561, 437, 64, 28)]


def stored(rel):
    p = RUNS / rel
    if not p.exists():
        pytest.skip(f"{p} not present")
    from camkit.frames import load
    return load(p)


def ocr_lines(rows):
    return [ocr.Line(t, 1.0, x, y, w, h) for t, x, y, w, h in rows]


# ---------------------------------------------------------------- reading the screen (stored frames)


@pytest.mark.parametrize("rel,word,lit,values", [
    ("kit2_look_zebra_a/shots/00012_down.png", "", None, ["Std+Range", "70", "±5"]),
    ("kit2_look_zebra_a/shots/00013_right.png", "Type", 0, ["Std+Range", "70", "±5"]),
    ("kit2_look_zebra_a/shots/00014_right.png", "Standard", 1, ["Std+Range", "70", "±5"]),
    ("kit2_zebra_split/shots/range6.png", "Range", 2, ["Std+Range", "29", "±6"]),
    ("kit2_zebra_split/shots/std29.png", "Standard", 1, ["Std+Range", "29", "±5"])])
def test_the_stored_frames_read_as_the_option_its_lit_box_and_values(rel, word, lit, values):
    """On the camera's own frames (OSD eyes): the title reads Custom 1, the word above the lit box names it, the lit
    box is found by its orange, each box's value reads with OCR's "‡" taken for "±" and its spaces out."""
    f = stored(rel)
    cam = SimpleNamespace(frame=f)
    assert O.title(cam) == "Custom 1" and O.word(cam) == word and O.lit_place(cam) == lit
    assert [O.read_at(cam, b) for b in range(3)] == values and O.drawn(cam) == 3


def test_a_box_value_keeps_its_words_and_closes_the_spaces_ocr_puts_by_a_sign(monkeypatch):
    """read_at: "Lower Limit" stays two words (a proof's label), while "Std +Range", "‡ 5" and "100 +" close up."""
    def reads(rows):
        return lambda cam, box, expect="text": ocr.text_in(ocr_lines(rows), box)
    monkeypatch.setattr(O, "_read", reads([("Lower Limit", 173, 357, 169, 40), ("100 +", 419, 359, 40, 33),
                                           ("‡ 5", 537, 359, 50, 33)]))
    assert [O.read_at(None, b) for b in range(3)] == ["Lower Limit", "100+", "±5"]
    monkeypatch.setattr(O, "_read", reads([("Std +Range", 173, 357, 169, 40)]))
    assert O.read_at(None, 0) == "Std+Range"


# OCR's readings of the Range box during the probe's walk (kit2_pass2 241424-241440, HDMI eyes, 2026-11-18): from ±5,
# Down five times (±1 stayed), then Up eleven times (±10 stayed); the ± read as "+", "÷", "¢", "‡", a 3 as Cyrillic З
RANGE_WALK = ["‡5", "÷4", "‡З", "+2", "‡1", "‡1", "+2", "‡З", "÷4", "¢5", "‡6", "‡7", "‡8", "‡9", "+10", "÷10", "÷10"]


def test_the_normaliser_alone_puts_the_runs_readings_in_the_boxs_shape():
    """camkit.live.box_value: in a box whose held value is a sign and digits, the sign is the box's (±, whatever glyph
    OCR read for it: +, ÷, ¢, ‡) and the digits are mapped from their look-alikes (Cyrillic З, О and O, l and I); a plain
    number box gets the digits mapped, its trailing "+" kept; a box of words (Type) is left as read."""
    shaped = [live.box_value(t, "±5") for t in RANGE_WALK]
    assert shaped == ["±5", "±4", "±3", "±2", "±1", "±1", "±2", "±3", "±4", "±5", "±6", "±7", "±8", "±9", "±10", "±10",
                      "±10"]
    assert live.box_value("¢5", "¢5") == "±5" and live.box_value("З0", "70") == "30" and live.box_value("7O", "70") == "70"
    assert live.box_value("1OO +", "100+") == "100+" and live.box_value("Lower Limit", "Std+Range") == "LowerLimit"
    assert live.box_number("÷10", "±5") == 10 and live.box_number("±?", "±5") is None
    assert live.box_value("±?", "±5") == "±?", "no clean digits: left as read, for the walk to judge"


def frames_cam(frames):
    """A camera replaying stored frames: each press shows the next one."""
    from camkit.frames import load
    cam = SimpleNamespace(frames=list(frames), i=0, hdmi=SimpleNamespace(name="hdmi"), presses=[])
    cam.frame = load(cam.frames[0])

    def press(key, **k):
        cam.presses.append(key)
        cam.i += 1
        cam.frame = load(cam.frames[cam.i])
    cam.press = press
    return cam


def test_the_range_walk_on_the_stored_frames_gives_1_to_10_with_5_held(monkeypatch):
    """The probe's Range walk replayed on its own frames (241424 lit on ±5, then 241425-241440): ±1 to ±10 with ±5 held,
    five Downs and ten Ups (the camera's run pressed eleven, taking "+10" and "÷10" for two values: read in the box's
    shape they are one, the end that stayed), and the second reader never needed (the normaliser alone fits)."""
    shots = RUNS / "kit2_pass2" / "shots"
    names = ["241424_right.png"] + [f"{n}_down.png" for n in range(241425, 241430)] + \
            [f"{n}_up.png" for n in range(241430, 241441)]
    frames = [shots / n for n in names]
    if not all(f.exists() for f in frames):
        pytest.skip(f"{shots} does not hold the probe's frames")
    asked = []
    monkeypatch.setattr(O, "vlm_option", lambda cam: asked.append(cam.frame.path.name) or "")
    cam = frames_cam(frames)
    vals, held = O.walk(cam, 2, ["Type", "Standard", "Range"])
    assert (vals, held) == ([f"±{v}" for v in range(1, 11)], "±5")
    assert cam.presses == ["down"] * 5 + ["up"] * 10 and asked == []


class Reads:
    """A made-up box whose OCR reads `ocr` in turn (one per frame) and whose second reader reads `vlm` in turn."""
    def __init__(self, ocr, vlm=None):
        self.ocr, self.vlm, self.i, self.presses, self.asked = list(ocr), list(vlm or []), 0, [], []
        self.hdmi = SimpleNamespace(name="hdmi")
        self.frame = SimpleNamespace(path=Path("00100_x.png"), image=None)
        self.logged = []
        self.run = SimpleNamespace(log=lambda kind, **f: self.logged.append((kind, f)))

    def press(self, key, **k):
        self.presses.append(key)
        self.i += 1
        self.frame = SimpleNamespace(path=Path(f"{100 + self.i:05d}_{key}.png"), image=None)


@pytest.fixture
def reads(monkeypatch):
    monkeypatch.setattr(O, "read_at", lambda cam, b: cam.ocr[min(cam.i, len(cam.ocr) - 1)])
    monkeypatch.setattr(O, "vlm_option", lambda cam: cam.asked.append(cam.i) or (cam.vlm[cam.i] if cam.i < len(cam.vlm)
                                                                                 else ""))
    return Reads


def test_a_reading_no_stepped_box_gives_goes_to_the_second_reader(reads):
    """A reading that breaks the walk (no clean value, or not one step from the last): the second reader is asked on
    that frame; its value is taken where it fits, the disagreement logged; OCR's clean readings never ask it."""
    cam = reads(["±3", "±2", "±?", "±1", "±2", "±3", "±3"], vlm=["", "", "±1", "", "", "", ""])
    vals, held = O.walk(cam, 2, ["Type", "Standard", "Range"])
    assert (vals, held) == (["±1", "±2", "±3"], "±3")
    assert cam.asked == [2] and [f["vlm"] for k, f in cam.logged if k == "box_reading"] == ["±1"]


def test_a_reading_that_fits_no_walk_stops_naming_its_frame(reads):
    """±3, ±2, then ±7 by OCR and by the second reader alike: no stepped box gives it, and the walk stops naming the
    frame, as before."""
    cam = reads(["±3", "±2", "±7"], vlm=["", "", "±7"])
    with pytest.raises(O.Failed, match=r"00102_down\.png"):
        O.walk(cam, 2, ["Type", "Standard", "Range"])


def test_the_ok_consent_passes_on_its_own_screen_and_refuses_any_other():
    """camkit.live.option_boxes_refused, the OK's judge (the prover's before every OK, the camera's on a screen of no
    known kind): the title holds the option, the word above the lit box is the box's, that box is lit and holds the
    value, the footer draws the OK key, no question mark or confirmation word above it."""
    f = stored("kit2_look_zebra_a/shots/00014_right.png")
    lines = ocr_lines(STD70)
    ok = live.OptionBoxes("made up", "Custom 1", "Standard", "70", O.PLACES[1])
    assert live.option_boxes_refused(ok, lines, f.image) == ""
    for consent, why in ((live.OptionBoxes("x", "Custom 2", "Standard", "70", O.PLACES[1]), "title"),
                         (live.OptionBoxes("x", "Custom 1", "Range", "70", O.PLACES[1]), "word above"),
                         (live.OptionBoxes("x", "Custom 1", "Standard", "71", O.PLACES[1]), "reads"),
                         (live.OptionBoxes("x", "Custom 1", "Standard", "70", O.PLACES[2]), "not lit")):
        assert why in live.option_boxes_refused(consent, lines, f.image)
    asks = [r if r[0] != "Std+Range" else ("Delete all settings?", *r[1:]) for r in STD70]
    assert "question mark" in live.option_boxes_refused(ok, ocr_lines(asks), f.image)
    no_ok = f.image.copy()
    no_ok[430:480, 540:640] = 0
    assert "OK key" in live.option_boxes_refused(ok, lines, no_ok)


# ---------------------------------------------------------------- a made-up camera on the option's boxes


class Cam:
    """A made-up camera on Zebra Level: Right on the menu row opens the list on `start`; Down/Up step the list (it comes
    round); with an option that draws boxes lit, Right enters them (box 0 first, then the next), Left goes back; Up/Down
    step the lit box (a number stops at its ends, Type comes round); OK keeps it all and closes; MENU (close) cancels
    the screen's changes. `records` is what a download holds: Zebra Level's option and each box's value."""
    LIST = ["70", "75", "80", "85", "90", "95", "100", "100+", "Custom 1", "Custom 2"]
    TYPES = ["Std+Range", "Lower Limit"]

    def __init__(self, start="70", eyes="hdmi"):
        self.level, self.at, self.lit, self.open = start, 0, None, False
        self.saved = {"Custom 1": {"Type": "Std+Range", "Standard": 70, "Range": 5, "Lower Limit": 100},
                      "Custom 2": {"Type": "Lower Limit", "Standard": 70, "Range": 5, "Lower Limit": 100}}
        self.edit = None
        self.presses, self.consents, self.shown = [], [], []
        self.hdmi = SimpleNamespace(name=eyes)
        self.frame = SimpleNamespace(path=Path("00001_x.png"), image=None)
        self.answer_once = None

    # what the screen shows
    def option(self):
        return self.LIST[self.at]

    def boxes(self):
        if not self.open or not self.option().startswith("Custom"):
            return []
        v = self.edit or self.saved[self.option()]
        if v["Type"] == "Std+Range":
            return [("Type", v["Type"]), ("Standard", str(v["Standard"])), ("Range", f"±{v['Range']}")]
        return [("Type", v["Type"]), ("Lower Limit", f"{v['Lower Limit']}+")]

    def press(self, key, **k):
        self.presses.append(key)
        if not self.open:
            if key == "right":
                self.open, self.at = True, self.LIST.index(self.level)
            return
        boxes = self.boxes()
        if key == "right":
            if self.lit is None and boxes:
                self.lit, self.edit = 0, dict(self.saved[self.option()])
            elif self.lit is not None and self.lit + 1 < len(boxes):
                self.lit += 1
        elif key == "left" and self.lit:
            self.lit -= 1
        elif key in ("up", "down"):
            if self.lit is None:
                self.at = (self.at + (1 if key == "down" else -1)) % len(self.LIST)
            else:
                name = boxes[self.lit][0]
                if name == "Type":
                    i = self.TYPES.index(self.edit["Type"])
                    self.edit["Type"] = self.TYPES[(i + 1) % 2]
                else:
                    lo, hi = {"Standard": (0, 109), "Range": (1, 10), "Lower Limit": (50, 109)}[name]
                    self.edit[name] = max(lo, min(hi, self.edit[name] + (1 if key == "up" else -1)))
        elif key == "enter":
            self.consents.append(self.answer_once)
            self.answer_once = None
            self.level = self.option()
            if self.edit:
                self.saved[self.option()] = dict(self.edit)
            self.close()
        self.shown.append((self.lit, tuple(self.boxes())))

    def close(self):
        self.open, self.lit, self.edit = False, None, None

    def records(self):
        out = {"global:0x0379": self.LIST.index(self.level)}
        for o, base in (("Custom 1", 0x0dde), ("Custom 2", 0x0de6)):
            v = self.saved[o]
            out.update({f"global:0x{base:04x}": self.TYPES.index(v["Type"]), f"global:0x{base + 2:04x}": v["Lower Limit"],
                        f"global:0x{base + 4:04x}": v["Standard"], f"global:0x{base + 6:04x}": v["Range"]})
        return out


@pytest.fixture
def fake(monkeypatch):
    """optboxes_run's camera seams on a Cam: its readers read the made-up state, the menu, the scan's route and the
    shooting screen made up; the OK judge passes on a screen whose state holds what the consent names."""
    monkeypatch.setattr(O, "title", lambda cam: cam.option() if cam.open else "")
    monkeypatch.setattr(O, "word", lambda cam: cam.boxes()[cam.lit][0] if cam.lit is not None else "")
    monkeypatch.setattr(O, "lit_place", lambda cam: cam.lit)
    monkeypatch.setattr(O, "read_at", lambda cam, b: cam.boxes()[b][1] if b < len(cam.boxes()) else "")
    monkeypatch.setattr(O, "drawn", lambda cam: len(cam.boxes()))
    monkeypatch.setattr(O, "menu_from_shooting", lambda cam: None)
    monkeypatch.setattr(O, "scan_position", lambda cam, cycle: 0)
    monkeypatch.setattr(O, "go_to", lambda *a: True)
    monkeypatch.setattr(O, "close_screen", lambda cam, link: cam.close())
    monkeypatch.setattr(O, "to_shooting", lambda *a, **k: None)
    monkeypatch.setattr(O.time, "sleep", lambda s: None)

    def judged(cam, consent, read=None):
        boxes = cam.boxes()
        ok = cam.option() == consent.option and cam.lit is not None and boxes[cam.lit] == (consent.word, consent.value)
        return "" if ok else "not that screen"
    monkeypatch.setattr(O, "ok_refused", judged)
    # the second reader reads the lit box as drawn, in its own words (a range with its sign): what a proof line keeps
    monkeypatch.setattr(O, "vlm_option", lambda cam: cam.boxes()[cam.lit][1] if cam.lit is not None else "")
    return Cam


def link_for(cam):
    """A link whose downloads hold the made-up camera's records at that moment."""
    downloads = []

    def download(tag):
        downloads.append(SimpleNamespace(name=f"{len(downloads) + 2:05d}_{tag}.DAT", values=cam.records()))
        return downloads[-1]
    return SimpleNamespace(download=download, downloads=downloads)


def test_a_number_box_is_walked_to_both_ends_and_type_once_round(fake):
    """walk: Down until a further press changes nothing (the low end) or comes round, then Up the same way, the values in
    Up order; Standard from 70 gives 0 to 109, Type (two options that come round) both, the held value kept."""
    cam = fake()
    O.open_option(cam, None, None, "Zebra Level", "Custom 1")
    O.enter_box(cam, 1, "Standard")
    vals, held = O.walk(cam, 1)
    assert held == "70" and vals == [str(v) for v in range(110)]
    cam = fake()
    O.open_option(cam, None, None, "Zebra Level", "Custom 1")
    O.enter_box(cam, 0, "Type")
    assert O.walk(cam, 0) == (["Std+Range", "Lower Limit"], "Std+Range")


def test_the_probe_reads_every_box_under_each_type_and_chooses_nothing(fake, tmp_path):
    """--probe: the option lit, each Type's row of boxes named as drawn, each box walked to its ends (Range before
    Standard, so Standard never passes 30 with Range at ±5), MENU at the end; one line written, no OK pressed, the
    camera's saved values untouched."""
    cam = fake()
    got = O.probe(cam, None, None, None, "Zebra Level", "Custom 1")
    assert got["types"] == {"Std+Range": ["Type", "Standard", "Range"], "Lower Limit": ["Type", "Lower Limit"]}
    assert got["boxes"]["Type"]["values"] == ["Std+Range", "Lower Limit"]
    assert got["boxes"]["Standard"]["values"][0] == "0" and got["boxes"]["Standard"]["values"][-1] == "109"
    assert got["boxes"]["Range"] == {"values": [f"±{v}" for v in range(1, 11)], "held": "±5", "type": "Std+Range"}
    assert got["boxes"]["Lower Limit"]["values"][0] == "50+" and got["boxes"]["Lower Limit"]["type"] == "Lower Limit"
    assert "enter" not in cam.presses and cam.saved["Custom 1"]["Standard"] == 70
    assert not any(lit == 1 and boxes[1:] == (("Standard", "30"), ("Range", "±5")) for lit, boxes in cam.shown)


def test_the_proof_values_take_the_ends_the_neighbours_a_middle_and_the_held_last():
    """values_for: both ends, the held value's neighbours, one in the middle, then the held value, which must change
    nothing; Standard 30 is never among them while Range is ±5."""
    vals = [str(v) for v in range(110)]
    assert O.values_for("Standard", vals, "70", range_held="±6") == ["0", "109", "69", "71", "55", "70"]
    std = O.values_for("Standard", vals, "31", range_held="±5")
    assert "30" not in std and std[-1] == "31"
    assert O.values_for("Type", ["Std+Range", "Lower Limit"], "Std+Range") == ["Lower Limit", "Std+Range"]


def test_standard_30_with_range_5_is_refused_on_osd_eyes_and_crossed_safely_otherwise(fake):
    """The screen "Standard lit at 30, Range ±5" stalls the remote link while the kit reads the screen through it (OSD
    eyes): stepping onto it there is refused in plain words; with HDMI eyes it is stepped across as any value."""
    cam = fake(eyes="osd")
    cam.saved["Custom 1"]["Standard"] = 32
    O.open_option(cam, None, None, "Zebra Level", "Custom 1")
    O.enter_box(cam, 1, "Standard")
    with pytest.raises(O.Refused, match="stalls the camera's remote link"):
        O.step_to(cam, 1, [str(v) for v in range(110)], "20", names=["Type", "Standard", "Range"])
    assert O.read_at(cam, 1) == "31"
    cam = fake(eyes="hdmi")
    cam.saved["Custom 1"]["Standard"] = 32
    O.open_option(cam, None, None, "Zebra Level", "Custom 1")
    O.enter_box(cam, 1, "Standard")
    O.step_to(cam, 1, [str(v) for v in range(110)], "20", names=["Type", "Standard", "Range"])
    assert O.read_at(cam, 1) == "20"


def probe_of(cam):
    return O.probe(cam, None, None, None, "Zebra Level", "Custom 1")


class Lines(list):
    def write(self, line):
        self.append(json.loads(line))

    def flush(self):
        pass


def test_the_proof_run_proves_each_box_from_its_own_base(fake, monkeypatch):
    """prove: a base first (the option chosen as it stands: Zebra Level's own record moves there, never in a box's
    proof), then each box's values, the held one last; Lower Limit from a base with Type on Lower Limit; on OSD eyes
    Standard from a base with Range one step off ±5. Each proof line in boxes_run's shape (path row > option > box,
    kind list, its index among the probe's values), its changes the box's record alone."""
    for eyes in ("hdmi", "osd"):
        cam = fake(eyes=eyes)
        probed = probe_of(fake(eyes=eyes))
        link = link_for(cam)
        monkeypatch.setattr(O.camset, "read", lambda d: d.values)
        monkeypatch.setattr(O.camset, "diff", lambda a, b: [SimpleNamespace(key=k, before=a[k], after=b[k])
                                                            for k in a if a[k] != b[k]])
        out = Lines()
        start = SimpleNamespace(name="00001_before.DAT", values=cam.records())
        O.prove(cam, link, None, None, None, "Zebra Level", "Custom 1", probed, None, start, out)
        by_box = {}
        for r in out:
            assert r["path"][:2] == ["Zebra Level", "Custom 1"] and r["kind"] == "list" and r["boxes"] is True
            assert r["index"] == probed["boxes"][r["path"][2]]["values"].index(r["label"])
            assert "global:0x0379" not in [c["key"] for c in r["changes"]]
            by_box.setdefault(r["path"][2], []).append(r)
        assert set(by_box) == {"Type", "Standard", "Range", "Lower Limit"}
        assert all(r["vlm"] == r["shown"] == r["label"] for r in out), "OCR's reading and the second reader's, both kept"
        assert [c["key"] for c in by_box["Standard"][0]["changes"]] == ["global:0x0de2"]
        assert [c["key"] for c in by_box["Lower Limit"][0]["changes"]] == ["global:0x0de0"]
        assert all(r["changes"] == [] for r in (rows[-1] for rows in by_box.values())), "the held value changes nothing"
        bases = {r["base"] for r in by_box["Standard"]}
        assert len(bases) == 1 and (bases != {r["base"] for r in by_box["Range"]}) == (eyes == "osd")


def test_a_value_whose_records_did_not_move_is_kept_as_not_proved(fake, monkeypatch, capsys):
    """A value chosen whose download differs in no record from its base: the line keeps it with no changes (the report
    credits it nothing), and the run says it was not proved, never guessing a record."""
    cam = fake()
    probed = probe_of(fake())
    monkeypatch.setattr(O.camset, "read", lambda d: d.values)
    monkeypatch.setattr(O.camset, "diff", lambda a, b: [])
    out = Lines()
    start = SimpleNamespace(name="00001_before.DAT", values=cam.records())
    O.prove(cam, link_for(cam), None, None, None, "Zebra Level", "Custom 1", probed, "Range", start, out)
    assert out and all(r["changes"] == [] for r in out) and "not proved" in capsys.readouterr().out


def run_main(monkeypatch, tmp_path, body, args=()):
    @contextlib.contextmanager
    def session(run, eyes):
        try:
            yield SimpleNamespace(cam=None, link=None, start=tmp_path / "00001_before.DAT")
        except Exception as e:
            print(f"stopped: {type(e).__name__}: {e}")
    monkeypatch.setattr(O, "load_scan", lambda scan: (None, None))
    monkeypatch.setattr(O, "Run", lambda name: SimpleNamespace(dir=tmp_path))
    monkeypatch.setattr(O, "eyes_from_config", lambda run: None)
    monkeypatch.setattr(O, "prover_session", session)
    monkeypatch.setattr(O, "latest_probe", lambda run, row, option: {"boxes": {}, "types": {}})
    monkeypatch.setattr(O, "prove", body)
    monkeypatch.setattr(O, "probe", body)
    O.main(["--row", "Zebra Level", "--option", "Custom 1", "--scan", str(tmp_path), *args])


def raises(e):
    def body(*a, **k):
        raise e
    return body


@pytest.mark.parametrize("args", [(), ("--probe",)])
def test_a_stopped_run_exits_as_the_other_provers_do(monkeypatch, tmp_path, args):
    """Once the session has restored the start file: a refusal exits 7, any other stop 8, a run that ends or a STOP 0."""
    for e, code in ((safety.Refused("enter refused"), EXIT_REFUSED), (O.Failed("its title does not read Custom 1"),
                                                                      EXIT_INCOMPLETE)):
        with pytest.raises(SystemExit) as got:
            run_main(monkeypatch, tmp_path, raises(e), args)
        assert got.value.code == code
    run_main(monkeypatch, tmp_path, lambda *a, **k: None, args)
    run_main(monkeypatch, tmp_path, raises(StopRequested("STOP")), args)


def test_a_proof_run_with_no_probe_stops_before_the_link(monkeypatch, tmp_path, no_camera):
    """The proof run plans from the option's probe: with none in the run, it stops naming the probe command, nothing
    reached."""
    monkeypatch.setattr(O, "load_scan", lambda scan: (None, None))
    monkeypatch.setattr(O, "Run", lambda name: SimpleNamespace(dir=tmp_path))
    with pytest.raises(SystemExit, match="--probe"):
        O.main(["--row", "Zebra Level", "--option", "Custom 1", "--scan", str(tmp_path)])
