"""Leftovers of the engineering review of 2026-11-18's fixes, each closed in a file its neighbour's fix did not own:
the hand evidence's part for the limit pairs (LIMIT_PAIRS); the proof viewer's option pages in the definition's order;
framepos's presses that went, never recorded as refused. Made-up cameras, settings, keys and words; no camera, no
private file."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import safety  # noqa: E402
from camkit.link import CameraRefused, Disconnected, LinkError, NetworkError  # noqa: E402
from writer import hand_evidence  # noqa: E402
# imported before any test points the kit at a data folder of its own: it binds the a1 II's tables as it is imported
import schema_update  # noqa: E402,F401
from test_plain_hand_tables import CAM, Cam, rec  # noqa: E402
from test_review_ordered import pairs_doc  # noqa: E402


# ---------------------------------------------------------------- 1. the limit pairs' hand evidence

PAIRS = {"global:0x0001": {"upper": "global:0x0002", "lower_moves_upper": True, "upper_moves_lower": True}}
SAID = "made-up words: what showed it"          # no run, no day: a test's evidence holds none of the owner's


def evidence_doc(tables: dict) -> dict:
    return {"$schema": hand_evidence.SCHEMA_REF, "hand_format": hand_evidence.FORMAT, "camera": CAM, "tables": tables}


def test_the_hand_evidence_takes_what_proved_each_direction_of_a_limit_pair():
    """schemas/hand-evidence.schema.json, which the plain pass holds the file to, has a LIMIT_PAIRS part: by the lower
    limit's key, its "evidence" by direction (the field the public table marks it with), words only; nothing else on a
    pair (no upper, no moves_it: the public table's alone), and a part for a pair the tables lack is refused."""
    tables = {"LIMIT_PAIRS": PAIRS}
    good = evidence_doc({"LIMIT_PAIRS": {"global:0x0001": {"evidence": {"lower_moves_upper": SAID,
                                                                         "upper_moves_lower": SAID}}}})
    assert hand_evidence.plain_problems(good, CAM, tables) == []
    for part in ({"upper": "global:0x0002"}, {"lower_moves_upper": True}, {"evidence": {"moves_it": SAID}},
                 {"evidence": {"lower_moves_upper": True}}, {"evidence": SAID}):
        bad = evidence_doc({"LIMIT_PAIRS": {"global:0x0001": part}})
        assert hand_evidence.plain_problems(bad, CAM, tables), part
    stale = evidence_doc({"LIMIT_PAIRS": {"global:0x0003": {"evidence": {"lower_moves_upper": SAID}}}})
    assert hand_evidence.plain_problems(stale, CAM, tables) == ["LIMIT_PAIRS 'global:0x0003': the tables have no such entry"]


def test_a_direction_marked_without_its_evidence_is_written_without_moves_it(capsys):
    """with_limit_pairs (kit/writer/limits.py): where the camera's hand evidence file is there (`evidence` a dict, the
    plain pass's LIMIT_PAIRS part read apart, or {} for the a1 II's pass, whose entries carry it put back), a direction
    the public table marks is written with moves_it only where the evidence shows it, said otherwise; without the file
    (None) moves_it is the table's, as before. The evidence never sets moves_it, and its words reach no field."""
    from writer.limits import with_limit_pairs

    def written(table, evidence):
        doc = pairs_doc()
        with_limit_pairs(doc, table, evidence=evidence)
        by = {s["key"]: s for s in doc["settings"]}
        return by["global:0x0001"]["at_most"], by["global:0x0002"]["at_least"], capsys.readouterr().out
    both = ({"setting": "global:0x0002", "moves_it": True}, {"setting": "global:0x0001", "moves_it": True})
    neither = ({"setting": "global:0x0002"}, {"setting": "global:0x0001"})
    assert written(PAIRS, None)[:2] == both                         # no evidence file: the table's
    lower, upper, said = written(PAIRS, {})                         # a file with nothing for the pair
    assert (lower, upper) == neither
    for flag in ("lower_moves_upper", "upper_moves_lower"):
        assert (f"limit pair global:0x0001 <= global:0x0002: nothing in the hand evidence shows {flag} (its "
                f"\"evidence\" in LIMIT_PAIRS); written without moves_it") in said, said
    # the plain pass: the part read apart, one direction shown
    part = {"global:0x0001": {"evidence": {"upper_moves_lower": SAID}}}
    assert written(PAIRS, part)[:2] == (neither[0], both[1])
    # the a1 II's pass: the evidence put back into the entry
    put_back = {"global:0x0001": {**PAIRS["global:0x0001"], "evidence": {"lower_moves_upper": SAID}}}
    lower, upper, said = written(put_back, {})
    assert (lower, upper) == (both[0], neither[1]) and SAID not in json.dumps([lower, upper])
    # evidence for a direction the table does not mark never sets moves_it
    unmarked = {"global:0x0001": {"upper": "global:0x0002"}}
    assert written(unmarked, {"global:0x0001": {"evidence": {"lower_moves_upper": SAID}}})[:2] == neither


@pytest.mark.parametrize("evidence, want", [
    (None, {"setting": "global:0x0b65", "moves_it": True}),                    # no file: the table's
    ({}, {"setting": "global:0x0b65"}),                                         # a file with nothing for it
    ({"LIMIT_PAIRS": {"global:0x0b65": {"evidence": {"upper_moves_lower": SAID}}}},
     {"setting": "global:0x0b65", "moves_it": True}),
], ids=["no file", "nothing for it", "shown"])
def test_the_plain_pass_holds_a_marked_direction_to_its_evidence(tmp_path, monkeypatch, capsys, evidence, want):
    """The plain pass (every camera's but the a1 II's) reads the LIMIT_PAIRS part of the hand evidence apart and gives
    it to the writer: a made-up camera whose table marks one direction, with no evidence file, with one holding nothing
    for the pair, and with one showing it. The evidence's words reach neither the public definition nor its evidence."""
    c = Cam(tmp_path, monkeypatch)
    steps = {"Step 1": 4, "Step 2": 6, "Step 3": 8}
    c.report([{"row": "Shooting > Low End", "options": 3, "notices": [], "records": {"global:0x0b65": rec(dict(steps))}},
              {"row": "Shooting > High End", "options": 3, "notices": [], "records": {"global:0x0b63": rec(dict(steps))}}])
    c.tables(LIMIT_PAIRS={"global:0x0b65": {"upper": "global:0x0b63", "upper_moves_lower": True}})
    if evidence is not None:
        c.hand_evidence(**evidence)
    _, said = c.write(capsys)
    public, private, text = c.written()
    by = {s["key"]: s for s in public["settings"]}
    assert by["global:0x0b63"]["at_least"] == want, said
    assert by["global:0x0b65"]["at_most"] == {"setting": "global:0x0b63"}
    assert ("written without moves_it" in said) is (evidence == {})
    assert SAID not in text and SAID not in json.dumps(private)


# ---------------------------------------------------------------- 2. the proof viewer's option pages

def test_the_viewer_shows_an_options_page_in_the_definitions_order(monkeypatch):
    """A row whose option opens a page of boxes the definition places in the order the camera draws them (a probe's,
    placement.box_orders: "Depth" before "Strength", as Zebra Level > Custom 1's Type before Standard), the settings
    listed the other way in the definition: the proof viewer's subsection for that option lists them as the
    definition places them (row_at), by placement's own order of the page (page_orders), not as the file lists them.
    A made-up camera's menu tree and settings."""
    import proof_viewer as pv
    from camkit import placement
    from test_placement import PAGES

    def s(key, name, menus, values=(), id_=1):
        return {"key": key, "area": "global", "id": id_, "name": name, "tab": "Color", "group": "Color/Tone",
                "order": 9000, "values": [list(v) for v in values],
                "proved": {"run": "kit2_pass2", "date": "2026-10-29", "menu": list(menus)}}
    d = {"model": "TEST", "tabs": ["Color"], "layouts": [{"model": "TEST", "firmware": "1.00"}], "camera": {},
         "menu": [{"tab": "Color", "group": "Color/Tone", "label": x, "order": i} for i, x in enumerate(["Tone", "Profile", "Look"])],
         "settings": [s("global:0x0002", "Look", ["Look"], [[0, "A"], [1, "B"]], 2),
                      s("global:0x0004", "Look > A > Strength", ["Look > A > Strength"], id_=4),
                      s("global:0x0003", "Look > A > Depth", ["Look > A > Depth"], id_=3)]}
    placed = placement.settings(d, PAGES, {("look", "a"): ["Depth", "Strength"]})       # as a probe read the boxes
    for x in d["settings"]:
        x.update(placed.get(x["key"], {}))
    assert [x.get("row_at") for x in d["settings"][1:]] == [[2, 0, 1], [2, 0, 0]]        # Depth first, listed last
    monkeypatch.setattr(pv.datafiles, "load_menu_tree", lambda cam: PAGES)
    monkeypatch.setattr(pv, "RUN_ROOT", None)
    look = next(x for x, _ in pv.menu_nodes(pv.menu(d, pv.records(d, {}), Path("."))) if x["l"] == "Look")
    assert look["subs"] == [{"name": "A", "keys": ["global:0x0003", "global:0x0004"]}]


# ---------------------------------------------------------------- 3. framepos: a press that went is no refusal

SHOOTING = {"kind": "shooting"}
# what a press raises when the key may have gone: a screen not read after it (camkit.live), a dropped session, the
# SDK's network error, a reply that never came
GONE = [LinkError("ms_left: the press went, and its screen could not be read afterwards (LinkError: no OSD image)"),
        Disconnected("disconnected"), NetworkError("the camera's remote link reported a network error"),
        LinkError("press ms_left: no reply")]
GONE_IDS = ["unread", "disconnected", "network", "no reply"]


@pytest.mark.parametrize("error", [CameraRefused("press ms_left 60: button not accepted"),
                                   safety.Refused("a made-up guard's refusal")], ids=["camera", "guard"])
def test_a_shooting_press_refused_before_it_went_is_recorded_refused(error):
    """framepos_run.press_moves: a press the camera refused (CameraRefused) or the kit's guards (safety.Refused),
    neither of which went, is recorded "refused", not counted, and the moves go on."""
    import framepos_run as F
    from test_framepos import Cam
    cam = Cam(SHOOTING, [error, SHOOTING])
    sent, done = [], []
    F.press_moves(cam, [["ms_left", 2]], sent, done)
    assert done == [["ms_left", 1]] and cam.pressed == ["ms_left"] * 2
    assert sent[0]["refused"].startswith(type(error).__name__) and "refused" not in sent[1]


@pytest.mark.parametrize("error", GONE, ids=GONE_IDS)
def test_a_shooting_press_that_may_have_gone_stops_the_run(error):
    """framepos_run.press_moves: any other link error of a press (the press went and its screen could not be read, a
    dropped session, a network error, no reply) is no refusal: nothing more is pressed and it reaches the run, which
    stops as on a lost link (its session's end restores), `done` holding the presses taken before it."""
    import framepos_run as F
    from test_framepos import Cam
    cam = Cam(SHOOTING, [SHOOTING, error, SHOOTING])
    sent, done = [], []
    with pytest.raises(type(error)):
        F.press_moves(cam, [["ms_left", 3]], sent, done)
    assert cam.pressed == ["ms_left"] * 2 and done == [["ms_left", 1]]
    assert not [x for x in sent if "refused" in x]


class PushCam:
    """A made-up camera for framepos_run.push: always on the shooting screen; its link press number n raises
    errors[n]."""

    def __init__(self, errors: dict):
        self.errors, self.presses, self.refreshed = errors, 0, []
        self.hdmi = SimpleNamespace(grab=lambda save=True: None)
        self.link = SimpleNamespace(press=self.link_press)
        self.frame = SimpleNamespace(path=Path("00001_frame.png"))

    def reading(self, f):
        return SimpleNamespace(kind="shooting")

    def refresh(self, tag):
        self.refreshed.append(tag)

    def link_press(self, key, on_shooting=frozenset(), screen=None):
        self.presses += 1
        if self.presses in self.errors:
            raise self.errors[self.presses]


def test_a_pushed_press_the_camera_refused_is_a_press_lost():
    """framepos_run.push: a press the camera refused (CameraRefused) did nothing: not counted, and the push goes on."""
    import framepos_run as F
    cam = PushCam({2: CameraRefused("press ms_left: button not accepted")})
    assert F.push(cam, [["ms_left", 3]], gap=0) == [["ms_left", 2]] and cam.presses == 3


@pytest.mark.parametrize("error", GONE, ids=GONE_IDS)
def test_a_pushed_press_that_may_have_gone_stops_the_run(error):
    """framepos_run.push: any other link error of a press is no press lost: nothing more is pushed and it reaches the
    run, which stops as on a lost link."""
    import framepos_run as F
    cam = PushCam({2: error})
    with pytest.raises(type(error)):
        F.push(cam, [["ms_left", 3]], gap=0)
    assert cam.presses == 2


# ---------------------------------------------------------------- 4. the Shoot Mode prover follows the mode it sets

@pytest.mark.parametrize("family, started, switched", [(0, "Movie", "Stills"), (1, "Stills", "Movie"),
                                                       (2, "Stills", "S&Q"), (3, "Movie", "S&Q")],
                         ids=["stills", "movie", "s&q", "time-lapse"])
def test_the_shoot_mode_prover_follows_the_mode_it_leaves_the_camera_in(monkeypatch, tmp_path, family, started,
                                                                        switched):
    """shootmode_run: a mode the camera applies after OK puts it in that family's shooting mode, so camkit.session.MODE
    (the mode the menu's lock after a download goes by) is that family's (runner.scan_mode: S&Q Motion and Time-lapse
    are S&Q) from there to the restore, and the start's again once the start file is back (as mode_switch.py does); a
    mode the camera refused leaves it in the start's. A made-up chooser (test_review_commit.ModeCam), its second mode
    refused."""
    import shootmode_run as S
    from camkit import session
    from test_review_commit import ModeCam, reads
    cam, seen = ModeCam(refuse={1}), []

    class Link:
        def __init__(self, run):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def download(self, tag):
            seen.append((tag, session.MODE))
            return Path(f"{len(seen):05d}_{tag}.DAT")

        def upload(self, path):
            seen.append(("upload", session.MODE))

    def load_scan(scan):
        session.MODE = started              # as runner.load_scan sets it: the mode the run's scan was made in
        return [], {}
    reads(monkeypatch, lambda f: cam.text)
    monkeypatch.setattr(S.camset, "read", lambda p: SimpleNamespace(path=Path(p)))
    monkeypatch.setattr(S.camset, "diff", lambda a, b: [SimpleNamespace(key="global:0x0001", before=0, after=1)]
                        if b.path.name.endswith(".DAT") and "shootmode" in b.path.name else [])
    for name, value in (("load_scan", load_scan), ("check_readers", lambda: None),
                        ("eyes_from_config", lambda run: SimpleNamespace(attach=lambda link: None, close=lambda: None)),
                        ("Link", Link), ("LiveCamera", lambda link, hdmi, run: cam),
                        ("look", lambda c, link, cycle, model, f: list(ModeCam.MODES)),
                        ("open_row", lambda c, cycle, model: c.open()), ("mode_name", lambda c: ModeCam.MODES[c.mode]),
                        ("vlm_option", lambda c: "made up"), ("close_screen", lambda c, link: None),
                        ("choice_refused", lambda c, name, label, auto_allowed=False: ""),   # its own tests judge it
                        ("to_shooting", lambda link, hdmi, why: None), ("verify_restore", lambda run, start: 0)):
        monkeypatch.setattr(S, name, value)
    monkeypatch.setattr(S.time, "sleep", lambda s: None)
    start = tmp_path / "00001_dialmenu.DAT"
    start.write_bytes(b"made up")
    monkeypatch.setattr(sys, "argv", ["shootmode_run.py", "--start", str(start), "--scan", "made-up",
                                      "--families", str(family)])
    S.main()
    order = [1, 2, 0] if family == 0 else [0, 1, 2]           # the stills family's remembered mode last
    want = [("before", started)]
    for m in order:
        now = started if m == 1 else switched                  # the refused mode left the camera as it was
        want += [(f"shootmode-{family}-{m}", now), ("upload", now)]
    left_in = session.MODE
    assert seen == want and left_in == started
