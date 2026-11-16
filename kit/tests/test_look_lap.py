"""The look lap's predicate and the opening check's row (docs/decisions/0024): safety.look_lap_refused, safety.row_judged
and the crawl's own use of them, and each layer's look lock on its own; and the review of 604a87a's findings, on the
acceptance tests' harness (the camera knows the row it is opening, a look lap writes no label it does not keep, each 1
read as 1, i or l), and of 235b088's (a withheld row's failed first open stands, each reading judged by its own path).
The end-to-end behaviour is test_step3_acceptance.py's."""
from types import SimpleNamespace

import pytest

from camkit import crawl, live, safety
from camkit.runs import Run
from test_step3_acceptance import (BLANK, DAY, DRIVE_MODE, ISO, NETWORK, UNRELATED, assert_lap_went_on, crawl_lap,
                                   lap_with, srow)
from test_step3_acceptance import scope  # noqa: F401  (the fixture)


class Presses:
    def __init__(self):
        self.sent = []

    def press(self, key, hold_ms=60, allow=frozenset(), cleanup=False, screen=None, on_shooting=frozenset(),
              judged=False):
        self.sent.append(key)


@pytest.mark.parametrize("key", ["enter", "ms_enter", "right", "left"])
def test_the_camera_lets_out_no_key_but_up_down_and_menu_inside_a_row_a_look_lap_opened(tmp_path, monkeypatch, key):
    """The camera's own lock, whatever drive.py judged: inside a row a look lap opened (no decision, no option named),
    Enter, the multi-selector's centre, Right and Left are refused, nothing sent."""
    cam = live.LiveCamera.__new__(live.LiveCamera)
    cam.link, cam.run, cam.look = Presses(), Run("look", root=tmp_path), True
    cam.options = {live.WITHHELD_ROW: ["On"]}               # never a look row's: it names no option
    cam.network_open = {"row": live.WITHHELD_ROW, "bar": "Language  English", "look": True, "address": False,
                        "class": safety.LIFT_FIXED}
    cam.identity_open = cam.address_open = None
    cam.frame = SimpleNamespace(image=None, path=tmp_path / "00001_right.png")
    monkeypatch.setattr(live, "lit_text", lambda image, path: "On")
    with pytest.raises(safety.Refused):
        cam.inside_refused(key)
    assert cam.link.sent == []


def test_drive_lets_out_no_enter_inside_a_row_a_look_lap_opened(monkeypatch):
    """drive.py's own lock, whatever the camera judges: no option of a look lap's row is chosen, even one an options map
    names under its withheld name."""
    import drive
    monkeypatch.setattr(drive, "highlighted", lambda image, path: "On")
    inside = {"row": live.WITHHELD_ROW, "bar": "Language  English", "look": True, "address": False, "identity": False}
    cam = SimpleNamespace(frame=SimpleNamespace(image=None, path=None))
    assert drive.inside_refused("enter", cam, inside, {live.WITHHELD_ROW: ["On"]})
    assert drive.inside_refused("right", cam, inside, {})
    assert drive.inside_refused("down", cam, inside, {}) == ""


@pytest.mark.parametrize("label,seen,refused", [
    ("Version", True, "firmware"), ("Load Settings", True, "loads"), ("Cleaning Mode", True, "moves"),
    ("In1tialize", True, "Initialize"), ("Screen Reader", True, "Screen Reader"),
    ("WPS Push", True, "opening acts"), ("IP Address Setting", True, "opening acts"),
    ("Format", False, "owner's own run"), ("Reset Network Set.", False, "owner's own run"),
    ("Delete Paired Device", False, "owner's own run"),         # never-open by another class, a card word in its name
    ("Format", True, None), ("Setting Reset", True, None),
    ("Audio Signal Volume", False, None), ("SteadyShot", False, None), ("Language", False, None),
    ("Access Authen. Info", False, None), ("File Format", False, None), ("Delete confirm.", False, None),
])
def test_the_look_predicate_refuses_in_its_order(label, seen, refused):
    why = safety.look_lap_refused(label, seen)
    assert (why is None) if refused is None else (refused in (why or "")), (label, why)


def test_a_reading_kept_beside_the_label_refuses_the_row_on_a_look_lap():
    """The crawl judges every reading the page model keeps of a row, not its label alone: a reader's "Format" beside
    OCR's "Grid Line" leaves the row unopened on a look lap until this body has seen a Format there opened: Grid Line
    seen vouches for no other reading of the row."""
    row = {"label": "Grid Line", "never_open": None, "readings": {"label": {"ocr": "Grid Line", "vlm": "Format"}}}
    why, decided = crawl.closed_row({"breadcrumb": "Setup > G"}, row, look=True)
    assert decided is None and "owner's own run" in why
    why, _ = crawl.closed_row({"breadcrumb": "Setup > G"}, row, look=True, seen=lambda path: path == ("Grid Line",))
    assert "owner's own run" in why
    why, _ = crawl.closed_row({"breadcrumb": "Setup > G"}, row, look=True, seen=lambda path: True)
    assert not why
    assert crawl.closed_row({"breadcrumb": "Setup > G"}, row) == (None, None)       # an ordinary lap as before


def test_the_opening_check_judges_a_known_label_beside_a_known_value_and_nothing_else():
    values = {"Custom Key Setting": ["Voice Memo hold", "Off"], "File Number": ["Series", "Reset"]}
    assert safety.row_judged("Custom Key Setting  Voice Memo hold", values) == ("Custom Key Setting",)
    assert safety.row_judged("Custom Key Setting Voice Memo", values) == ("Custom Key Setting Voice Memo",)
    assert safety.row_judged("File Number  Reset", values) == ("File Number  Reset",)    # an action's word: whole
    assert safety.row_judged("Custom Key Setting  Voice Memo hold") == ("Custom Key Setting  Voice Memo hold",)
    known = {"Camera Settings": ["Keep"], "Del": ["ete"]}
    assert safety.row_judged("Camera Settings  Keep", known) == ("Camera Settings",)
    assert safety.row_judged("Del ete", known) == ("Del ete", "Del")                  # read run together: Delete


# ---- the review of 604a87a: H1, a row seen under one path stands in for a destructive row of the same label

@pytest.mark.parametrize("seen_path,bar", [(["Face Memory", "Delete"], "Delete"),
                                           (["Save/Load Settings", "Delete"], "Delete"),
                                           (["Picture Profile", "PP1", "Reset"], "Reset"),
                                           (["Some Submenu", "Format"], "Format")])
def test_h1_a_submenu_rows_seen_record_opens_no_top_level_destructive_bar(tmp_path, monkeypatch, scope, seen_path,  # noqa: F811 (the fixture)
                                                                          bar):
    """The crawl judges the page model's row by its path (Grid Line, seen); the lit bar reads Delete. This body's
    records show only Face Memory > Delete opened, never a top-level Delete: the bar is not the row the crawl is opening,
    so it is unseen, and a destructive row unseen stays the owner's (camkit.live.bar_is_row)."""
    scope(BLANK, UNRELATED)
    rows = [DRIVE_MODE, srow("Grid Line", "", bar=bar, options=("A", "B")), ISO]
    lap = crawl_lap(tmp_path, monkeypatch, rows, argv=NETWORK, seen=["Drive Mode", "Grid Line", "ISO", seen_path])
    assert lap.sim.opened(2), lap.keys
    assert not lap.sim.opened(1), (bar, lap.keys, lap.sim.marked_at_open(1))


# ---- M1: a first open's marker for one row lets another, unseen, never-open row open with no record of its own

def test_m1_a_pending_first_open_of_one_row_opens_no_other_unseen_never_open_bar(tmp_path, monkeypatch, scope):  # noqa: F811 (the fixture)
    """--first-open-check page: row 0 (unseen, ordinary) is pending, its RESTORE_BY_HAND written; row 1's page model
    label is a seen ordinary row, its lit bar reads Access Authen. Info, never seen opened and not the row under its
    first open: a marker on disk opens no bar but the very row the caller wrote it for."""
    scope(BLANK, UNRELATED)
    rows = [srow("Grid Unseen", "Off"), srow("Grid Line", "", bar="Access Authen. Info", options=("A", "B")), ISO]
    lap = crawl_lap(tmp_path, monkeypatch, rows, argv=[*NETWORK, "--first-open-check", "page"],
                    seen=["Grid Line", "ISO"])
    assert lap.sim.opened(0) and lap.sim.marked_at_open(0) is True, lap.keys
    assert not lap.sim.opened(1), (lap.keys, lap.sim.marked_at_open(1))


# ---- M2: a first open logs and records the page model's label as read, which can carry a value

def test_m2_a_look_laps_first_open_keeps_no_page_model_reading_with_a_value(tmp_path, monkeypatch, scope):  # noqa: F811 (the fixture)
    """The page model read Edit Device Name with the device's name glued on (runner.known_labels never keeps such a
    label, and rows.jsonl withholds it); its first open on a look lap writes no such reading in events.jsonl, the looks
    file or the console: the name kit/crawl_run.py kept_label gives, its placeholder."""
    from camkit import coverage
    scope(BLANK, UNRELATED)
    name = "ILCE-made-up-owner-name"
    target = srow(f"Edit Device Name {name}", "", options=("A", "B"))
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=False)
    assert lap.sim.opened(1), lap.keys
    events = (lap.run.dir / "events.jsonl").read_text(encoding="utf-8")
    looks = coverage.looks_file(lap.root.name)
    kept = events + (lap.run.dir / "rows.jsonl").read_text(encoding="utf-8") + lap.out + (
        looks.read_text(encoding="utf-8") if looks.exists() else "")
    assert name not in kept, [w for w in ("events", "looks", "out") if name in
                              {"events": events, "looks": looks.read_text(encoding="utf-8") if looks.exists() else "",
                               "out": lap.out}[w]]


# ---- M3: a 1 read for an l and another for an i in one word

@pytest.mark.parametrize("label", ["C1ean1ng Mode", "In1tia1ize", "Anti-dust Funct1on"])
def test_m3_a_look_lap_never_opens_an_owner_never_row_read_with_1_for_l_and_1_for_i(tmp_path, monkeypatch, scope,  # noqa: F811 (the fixture)
                                                                                     label):
    """safety._look_texts reads each 1 on its own as 1, i or l: "C1ean1ng Mode" (Cleaning Mode, which shakes the sensor
    as it opens) and "In1tia1ize" are refused by a look lap; the third, one slip, is a control that holds."""
    scope(BLANK, UNRELATED)
    lap = lap_with(tmp_path, monkeypatch, srow(label, "", options=("A", "B")), seen_target=True)
    assert lap.sim.opened(2), lap.keys
    assert not lap.sim.opened(1), (label, lap.keys)


def test_a_label_with_more_than_five_ones_is_not_read_by_a_look_lap():
    assert "not read" in safety.look_lap_refused("A1 B1 C1 D1 E1 F1", True)
    assert safety.look_lap_refused("A1 B1 C1 D1 E1", True) is None


class TellingCamera:
    """A menu row whose Right the camera refuses (safety.RowRefused), keeping what the crawl told it of the row."""
    def __init__(self):
        self.told, self.presses = [], 0

    def press(self, key, **kw):
        self.told.append(kw.get("row"))
        raise safety.RowRefused(f"{key}: refused in the test")

    def read(self):
        return SimpleNamespace(kind="menu", signature="row", struct=None, bits=None, row=0)


@pytest.mark.parametrize("opened,seen", [({("language",)}, False), ({("setup menu",), ("setup menu", "language")}, True)])
def test_the_crawl_tells_the_camera_a_rows_seen_by_its_whole_path(opened, seen):
    """A look lap tells the camera the row its Right opens, seen by the row's whole path: Language seen at the top
    level is no seen Setup Menu > Language (camkit.first_open.Seen.seen), and the one name it expects is the one Seen
    was asked about, never another reading the page model keeps of the row."""
    from camkit import first_open
    first = SimpleNamespace(seen=first_open.Seen(opened), pending=[], opening=lambda path: None,
                            not_opened=lambda path: None, skips=lambda path: False)
    cam = TellingCamera()
    row = {"label": "Language", "never_open": safety.never_open("Language"),
           "readings": {"label": {"ocr": "Language", "vlm": "Langauge"}}}
    r = crawl.visit_row(cam, cam.read(), {"page": "Setup Menu"}, 0, row, path=("Setup Menu",), first=first, look=True)
    assert r.outcome.startswith("skipped: refused") and len(cam.told) == 1
    assert cam.told[0]["seen"] is seen and cam.told[0]["first"] is False
    assert cam.told[0]["expected"] == ("Language",)


def test_a_path_a_look_lap_withheld_is_never_seen():
    """A first open whose row's name a look lap withholds is recorded under its placeholder (kit/crawl_run.py
    kept_label), and no such path is ever seen, so its first open runs again on the next lap."""
    from camkit import coverage, first_open
    assert coverage.append_look("cam", {"t": "2026-11-15T10:00:00", "by": "crawl", "path": ["(withheld)"],
                                        "did": "open", "result": "looked"})
    assert coverage.append_look("cam", {"t": "2026-11-15T10:00:00", "by": "crawl", "path": ["Grid Line"],
                                        "did": "open", "result": "looked"})
    seen = first_open.seen_record("cam")
    assert seen.seen(["Grid Line"]) and not seen.seen(["(withheld)"])


def test_a_withheld_rows_clean_first_open_is_recorded_under_its_placeholder(tmp_path, monkeypatch, scope):  # noqa: F811 (the fixture)
    """The clean first open of a row whose name a look lap withholds is recorded, its pending look then its check, under
    the placeholder alone (camkit.first_open.FirstOpens.kept), and the row stays unseen."""
    import json
    from camkit import coverage, first_open
    scope(BLANK, UNRELATED)
    lap = lap_with(tmp_path, monkeypatch, srow("Edit Device Name ILCE-made-up-owner-name", "", options=("A", "B")),
                   seen_target=False)
    assert lap.code in (0, None) and lap.sim.opened(1) and lap.sim.marked_at_open(1) is True, lap.out[-1500:]
    looks = [json.loads(x) for x in coverage.looks_file(lap.root.name).read_text(encoding="utf-8").splitlines()]
    mine = [(lk["path"], lk["result"], lk.get("note")) for lk in looks if lk.get("run") == lap.run.dir.name]
    assert (["(withheld)"], "not_reached", first_open.PENDING) in mine
    assert (["(withheld)"], "looked", "first open checked") in mine
    assert not first_open.seen_record(lap.root.name).seen(["Edit Device Name ILCE-made-up-owner-name"])


# ---- the review of 235b088: a withheld row's failed first open forgotten, a seen row's reading vouching for a bar

def _record(*looks):
    from camkit import coverage
    for lk in looks:
        assert coverage.append_look("cam", lk)


def test_a_placeholders_failed_first_open_stands_whatever_clean_look_follows():
    """Rows share a placeholder, so a clean look under it says nothing of the row that failed (camkit.first_open's
    seen_record reads such looks in the file's order): the failure stands, and the path is never seen."""
    from camkit import first_open
    from test_step3_acceptance import look
    _record(look(["(withheld)"], result="changed"), look(["(withheld)"], result="looked"))
    s = first_open.seen_record("cam")
    assert first_open.key(["(withheld)"]) in s.acting and not s.seen(["(withheld)"])


def test_a_retraction_clears_a_placeholders_failed_first_open_and_a_later_failure_stands_again():
    from camkit import first_open
    from test_step3_acceptance import look
    _record(look(["(withheld)"], result="changed"), look(["(withheld)"], result="retract"))
    assert first_open.key(["(withheld)"]) not in first_open.seen_record("cam").acting
    _record(look(["(withheld)"], result="changed"))
    assert first_open.key(["(withheld)"]) in first_open.seen_record("cam").acting


def test_a_placeholders_page_check_that_could_not_clear_stands_whatever_clean_look_follows():
    from camkit import first_open
    from test_step3_acceptance import look
    _record(look(["(withheld)"], result="not_reached", note=first_open.PAGE), look(["(withheld)"], result="looked"))
    s = first_open.seen_record("cam")
    assert first_open.key(["(withheld)"]) in s.alone and not s.seen(["(withheld)"])


def test_a_placeholders_failure_under_one_parent_stays_under_it():
    from camkit import first_open
    from test_step3_acceptance import look
    _record(look(["Network", "(withheld)"], result="changed"))
    s = first_open.seen_record("cam")
    assert first_open.key(["Network", "(withheld)"]) in s.acting
    assert first_open.key(["(withheld)"]) not in s.acting and first_open.key(["Setup", "(withheld)"]) not in s.acting


def test_a_kept_names_latest_open_look_still_wins():
    from camkit import first_open
    from test_step3_acceptance import look
    _record(look(["Grid Line"], result="changed"), look(["Grid Line"], result="looked"))
    s = first_open.seen_record("cam")
    assert first_open.key(["Grid Line"]) not in s.acting and s.seen(["Grid Line"])


def test_a_look_laps_first_opens_ask_under_the_name_it_keeps_too():
    """FirstOpens asks the records under the label read and the name the lap keeps of it: a failure under the
    placeholder skips the row (skips agreeing with opening, whose message tells the owner to name the row themselves
    and holds neither the label as read nor the placeholder as a --path), and a page's check that could not clear it
    has the row checked alone (due)."""
    from camkit import first_open
    held = first_open.key(["(withheld)"])
    first = first_open.FirstOpens(None, None, None, "START.DAT", first_open.Seen(acting={held}, alone={held}), "", 0,
                                  wait=lambda *a, **k: None, per="page", name=lambda label: "(withheld)")
    path = ("Edit Device Name AAA-1",)
    assert first.skips(path)
    why = first.opening(path)
    assert why.startswith(first_open.UNSEEN) and "the row's own name" in why, why
    assert "AAA-1" not in why and "(withheld)" not in why, why
    first.pending.append(path)
    assert first.due({"page": "P"}, {"page": "P"})


@pytest.mark.parametrize("label", ["Language", "Wi-Fi Frequency Band"])
def test_a_row_whose_first_open_changed_a_record_is_not_opened_again_by_the_next_lap(tmp_path, monkeypatch, scope,  # noqa: F811 (the fixture)
                                                                                    label):
    """A crawl skips a row whose first open failed (camkit.first_open), whether the lap kept its name or withheld it:
    the owner put the start file back, and the next lap presses nothing on it."""
    from camkit import session
    from camkit.runs import RESTORE_BY_HAND
    from exit_status import EXIT_RESTORE_BY_HAND
    from test_step3_acceptance import LOOK_OPENS
    scope(BLANK)
    monkeypatch.setattr(session, "compared", lambda a, b, say=None: [SimpleNamespace(key="global:0x0357")])
    lap = lap_with(tmp_path / "one", monkeypatch, LOOK_OPENS[label], seen_target=False)
    assert lap.sim.opened(1) and lap.code == EXIT_RESTORE_BY_HAND, (lap.code, lap.out[-800:])
    (lap.root / RESTORE_BY_HAND).unlink()               # upload_check put the start file back
    monkeypatch.setattr(session, "compared", lambda a, b, say=None: [])
    lap2 = lap_with(tmp_path / "two", monkeypatch, LOOK_OPENS[label], seen_target=False)
    assert not lap2.sim.opened(1), (label, lap.row(1).get("label"), lap2.outcome(1), lap2.sim.marked_at_open(1))


def test_a_withheld_rows_failed_first_open_skips_another_withheld_row(tmp_path, monkeypatch, scope):  # noqa: F811 (the fixture)
    """The accepted cost of a name rows share: after one withheld row's first open changed a record, the next lap
    presses nothing on another withheld row under the same parent, its outcome skipped, naming neither row as read."""
    from camkit import session
    from camkit.runs import RESTORE_BY_HAND
    from exit_status import EXIT_RESTORE_BY_HAND
    from test_step3_acceptance import assert_lap_went_on
    scope(BLANK, UNRELATED)
    monkeypatch.setattr(session, "compared", lambda a, b, say=None: [SimpleNamespace(key="global:0x0357")])
    lap = lap_with(tmp_path / "one", monkeypatch, srow("Edit Device Name AAA-1", "", options=("A", "B")),
                   seen_target=False)
    assert lap.sim.opened(1) and lap.code == EXIT_RESTORE_BY_HAND, (lap.code, lap.out[-800:])
    assert lap.row(1)["label"] == "(withheld)", lap.row(1)
    (lap.root / RESTORE_BY_HAND).unlink()
    monkeypatch.setattr(session, "compared", lambda a, b, say=None: [])
    lap2 = lap_with(tmp_path / "two", monkeypatch, srow("Edit Device Name BBB-2", "", options=("A", "B")),
                    seen_target=False)
    assert_lap_went_on(lap2)
    assert not lap2.sim.opened(1) and not lap2.sim.inside(1), lap2.keys
    assert lap2.outcome(1).startswith("skipped") and lap2.row(1)["label"] == "(withheld)", lap2.row(1)
    assert not [w for w in ("AAA-1", "BBB-2") if w in lap2.outcome(1) + lap2.out + lap2.events], lap2.outcome(1)


def test_a_failed_first_open_of_a_withheld_row_writes_no_reading_anywhere(tmp_path, monkeypatch, scope):  # noqa: F811 (the fixture)
    from camkit import coverage, session
    from camkit.runs import RESTORE_BY_HAND
    from exit_status import EXIT_RESTORE_BY_HAND
    scope(BLANK, UNRELATED)
    monkeypatch.setattr(session, "compared", lambda a, b, say=None: [SimpleNamespace(key="global:0x0357")])
    name = "ILCE-made-up-owner-name"
    lap = lap_with(tmp_path, monkeypatch, srow(f"Edit Device Name {name}", "", options=("A", "B")), seen_target=False)
    assert lap.sim.opened(1) and lap.code == EXIT_RESTORE_BY_HAND, (lap.code, lap.out[-800:])
    marker = lap.root / RESTORE_BY_HAND
    texts = {"events": lap.events, "rows": (lap.run.dir / "rows.jsonl").read_text(encoding="utf-8"), "out": lap.out,
             "looks": coverage.looks_file(lap.root.name).read_text(encoding="utf-8"),
             "marker": marker.read_text(encoding="utf-8") if marker.exists() else ""}
    assert not [k for k, v in texts.items() if name in v]


def test_a_check_that_cannot_be_made_writes_no_reading_anywhere(tmp_path, monkeypatch, scope):  # noqa: F811 (the fixture)
    from camkit import coverage, session
    from camkit.runs import RESTORE_BY_HAND
    scope(BLANK, UNRELATED)

    def boom(a, b, say=None):
        raise OSError("download failed")
    monkeypatch.setattr(session, "compared", boom)
    name = "ILCE-made-up-owner-name"
    lap = lap_with(tmp_path, monkeypatch, srow(f"Edit Device Name {name}", "", options=("A", "B")), seen_target=False)
    assert lap.sim.opened(1), lap.keys
    marker, looks = lap.root / RESTORE_BY_HAND, coverage.looks_file(lap.root.name)
    texts = {"events": lap.events, "rows": (lap.run.dir / "rows.jsonl").read_text(encoding="utf-8"), "out": lap.out,
             "looks": looks.read_text(encoding="utf-8") if looks.exists() else "",
             "marker": marker.read_text(encoding="utf-8") if marker.exists() else ""}
    assert not [k for k, v in texts.items() if name in v]


def test_two_withheld_rows_on_one_page_one_failing_neither_seen(tmp_path, monkeypatch, scope):  # noqa: F811 (the fixture)
    """--first-open-check page: two withheld rows checked at once, a record differing; neither is seen, and their
    placeholder stays one a page's check could not clear."""
    from camkit import first_open, session
    from exit_status import EXIT_RESTORE_BY_HAND
    scope(BLANK, UNRELATED)
    monkeypatch.setattr(session, "compared", lambda a, b, say=None: [SimpleNamespace(key="global:0x0357")])
    rows = [srow("Edit Device Name AAA-1", "", options=("A", "B")), srow("Edit Device Name BBB-2", "", options=("A",)),
            ISO]
    lap = crawl_lap(tmp_path, monkeypatch, rows, argv=[*NETWORK, "--first-open-check", "page"], seen=["ISO"])
    assert lap.code == EXIT_RESTORE_BY_HAND, lap.out[-800:]
    s = first_open.seen_record(lap.root.name)
    assert not s.seen(["Edit Device Name AAA-1"]) and not s.seen(["Edit Device Name BBB-2"])
    assert first_open.key(["(withheld)"]) in s.alone


def test_a_seen_rows_other_reading_does_not_vouch_for_an_unseen_destructive_bar(tmp_path, monkeypatch, scope):  # noqa: F811 (the fixture)
    """Grid Line is seen; a second reader read the row as Delete, and the lit bar reads Delete, never seen opened here:
    the crawl tells the camera the one name it asked Seen about (Grid Line), and judges the reading Delete by its own
    path, so nothing vouches for the bar and its Right never goes out."""
    import test_step3_acceptance as A
    scope(BLANK, UNRELATED)
    rows = [DRIVE_MODE, srow("Grid Line", "", bar="Delete", options=("A", "B")), ISO]
    real_scan = A.Sim.scan

    def scan(self):
        cycle, model = real_scan(self)
        model["P"]["rows"][1]["readings"]["label"]["vlm"] = "Delete"
        return cycle, model
    monkeypatch.setattr(A.Sim, "scan", scan)
    lap = crawl_lap(tmp_path, monkeypatch, rows, argv=NETWORK, seen=["Drive Mode", "Grid Line", "ISO"])
    assert lap.sim.opened(2), lap.keys
    assert not lap.sim.opened(1), (lap.keys, lap.sim.marked_at_open(1), lap.outcome(1))


def test_an_ordinary_runs_failed_first_open_of_a_parenthesised_label_is_kept():
    """An ordinary run keeps every name, so a label read starting with "(" is only like a placeholder: never seen, and
    a failed first open under it kept."""
    from camkit import first_open
    from test_step3_acceptance import look
    _record(look(["(Card 1) Format"], result="changed"))
    s = first_open.seen_record("cam")
    assert first_open.key(["(Card 1) Format"]) in s.acting and not s.seen(["(Card 1) Format"])


# ---- a row's own name kept where the definition names the row, though it is a value too (2026-11-15, the a1 II: 74
# of its 268 top-level rows are also a Custom Key's function, and one's failed first open under the placeholder made a
# later lap skip every withheld row)

# a definition naming Focus Magnifier as a row of the menu and as a function Custom Key Setting can take (a value the
# kit knows, as on the a1 II), and two rows the page model can read with a value glued on
DEFINED = {"menu": [{"tab": "Setup", "group": "Test Group", "label": "Focus Magnifier"},
                    {"tab": "Network", "group": "Wi-Fi", "label": "Wi-Fi Connect"},
                    {"tab": "Network", "group": "Network Option", "label": "Edit Device Name"}],
           "settings": [{"row": ["Custom Key Setting"], "values": [[0, "Focus Magnifier"], [1, "Not Set"]]}]}
FOCUS_MAG = srow("Focus Magnifier", "", options=("Made-up Opt A", "Made-up Opt B"), current=1)
GLUED = srow("Edit Device Name AAA-1", "", options=("A", "B"))         # a label read with a value glued on


def defined(monkeypatch, doc=DEFINED):
    """The camera's definition the run reads (runner.definition, as kit/crawl_run.py imported it): `doc`."""
    import crawl_run
    import runner
    monkeypatch.setattr(runner, "definition", lambda: doc)
    monkeypatch.setattr(crawl_run, "definition", lambda: doc)


def markers_at_right(monkeypatch) -> list:
    """RESTORE_BY_HAND's text at every Right on a menu row of the simulated camera ("" where there is none)."""
    import test_step3_acceptance as A
    from camkit.runs import RESTORE_BY_HAND
    seen, real = [], A.Sim.key

    def key(self, k):
        if k in A.OPENERS and self.mode == "menu":
            marker = self.root / RESTORE_BY_HAND
            seen.append(marker.read_text(encoding="utf-8") if marker.exists() else "")
        real(self, k)
    monkeypatch.setattr(A.Sim, "key", key)
    return seen


def test_k1_the_runs_names_for_a_rows_own_name_take_the_definitions_rows_and_nothing_else_widens(monkeypatch):
    """K1: a row's own name is kept where the definition names the row, a value the kit knows or not (a row's place in
    the menu is no value); the set a screen's text is judged by (runner.known_labels) still holds no such label. K3: a
    label read with a value glued on is no definition's row label, so it is withheld. K4: a submenu's rows alike."""
    import crawl_run
    import runner
    defined(monkeypatch)
    names = {safety.plain(x) for x in crawl_run.row_names({})}
    assert crawl_run.kept_label("Focus Magnifier", names) == "Focus Magnifier"
    assert crawl_run.kept_label("Edit Device Name", names) == "Edit Device Name"
    assert "Focus Magnifier" not in runner.known_labels({})              # a screen's text: withheld as ever
    for glued in ("Edit Device Name ILCE-made-up-owner-name", "Wi-Fi ConnectOn", "Wi-Fi Connect On", "Focus MagnifierOn"):
        assert crawl_run.kept_label(glued, names) == crawl_run.WITHHELD_LABEL, glued
    assert {safety.plain(x) for x in crawl_run.row_names({}, {"Bluetooth Function": DAY})} >= names | {"bluetooth function"}
    row = {"page": "P", "slot": 0, "label": "Custom Key Setting", "outcome": "submenu crawled", "kind": "submenu",
           "presses": 4, "note": "", "submenu": [
               {"page": "P", "slot": 0, "label": "Focus Magnifier", "outcome": "walked", "kind": "list", "options": 2,
                "presses": 2, "note": ""},
               {"page": "P", "slot": 1, "label": "Edit Device Name AAA-1", "outcome": "walked", "kind": "list",
                "options": 2, "presses": 2, "note": ""}]}
    kept = crawl_run.kept_row(row, crawl_run.row_names({}))
    assert [x["label"] for x in kept["submenu"]] == ["Focus Magnifier", crawl_run.WITHHELD_LABEL]


def test_k1_a_defined_rows_own_name_is_written_whole_and_its_clean_first_open_makes_it_seen(tmp_path, monkeypatch,
                                                                                           scope):  # noqa: F811 (the fixture)
    """A look lap writes the name of a row the definition names, though it is a value too, whole: rows.jsonl,
    events.jsonl (first_open, first_open_checked), the looks file and RESTORE_BY_HAND's text; after its clean first
    open it is seen, and the next lap opens it plainly. Its rows.jsonl line names no option, lit or not (K4)."""
    import json
    from camkit import coverage, first_open
    scope(BLANK, UNRELATED)
    defined(monkeypatch)
    at_right = markers_at_right(monkeypatch)
    lap = lap_with(tmp_path / "one", monkeypatch, FOCUS_MAG, seen_target=False)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1) and lap.sim.marked_at_open(1) is True, lap.out[-1500:]
    assert lap.row(1)["label"] == "Focus Magnifier", lap.row(1)
    events = [json.loads(x) for x in lap.events.splitlines()]
    assert [e["path"] for e in events if e["kind"] == "first_open"] == [["Focus Magnifier"]]
    assert [e["paths"] for e in events if e["kind"] == "first_open_checked"] == [[["Focus Magnifier"]]]
    looks = [json.loads(x) for x in coverage.looks_file(lap.root.name).read_text(encoding="utf-8").splitlines()]
    mine = [(lk["path"], lk["result"]) for lk in looks if lk.get("run") == lap.run.dir.name]
    assert (["Focus Magnifier"], "not_reached") in mine and (["Focus Magnifier"], "looked") in mine, mine
    assert not [p for p, _ in mine if crawl_run_withheld(p)], mine
    marked = [t for t in at_right if t]
    assert len(marked) == 1 and "Focus Magnifier" in marked[0] and "(withheld)" not in marked[0], marked
    assert first_open.seen_record(lap.root.name).seen(["Focus Magnifier"])
    assert "current" not in lap.row(1) and "Made-up Opt" not in json.dumps(lap.row(1)), lap.row(1)
    lap2 = lap_with(tmp_path / "two", monkeypatch, FOCUS_MAG, seen_target=False)
    assert_lap_went_on(lap2)
    assert lap2.sim.opened(1) and lap2.sim.marked_at_open(1) is False, lap2.keys
    assert "first_open" not in lap2.events


def crawl_run_withheld(path) -> bool:
    import crawl_run
    return crawl_run.WITHHELD_LABEL in path


@pytest.mark.parametrize("kind", ["playback", "unknown"])
def test_a_first_open_on_a_screen_the_crawl_calls_unknown_checked_clean_makes_the_row_seen(tmp_path, monkeypatch,
                                                                                         scope, kind):  # noqa: F811 (the fixture)
    """2026-11-15, the a1 II: Cont. Play for Interval's Right showed the playback view, which the crawl records as an
    unknown screen; its first open's check came out clean, yet every later look lap opened it under the procedure again.
    Its clean look now goes before the crawl's, so the row is seen and the next lap opens it plainly, no marker at its
    Right, while the crawl's kit failure stays the row's latest look."""
    import json
    from camkit import coverage, first_open
    scope(BLANK, UNRELATED)
    defined(monkeypatch, {**DEFINED, "menu": [*DEFINED["menu"], {"tab": "Playback", "group": "Playback Option",
                                                                  "label": "Cont. Play for Interval"}]})
    target = srow("Cont. Play for Interval", "", kind=kind, options=())
    at_right = markers_at_right(monkeypatch)
    lap = lap_with(tmp_path / "one", monkeypatch, target, seen_target=False)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1) and lap.sim.marked_at_open(1) is True, lap.out[-1500:]
    assert (lap.row(1)["label"], lap.outcome(1), lap.row(1)["kind"]) == ("Cont. Play for Interval", "unknown screen",
                                                                         kind), lap.row(1)
    kinds = [json.loads(x).get("kind") for x in lap.events.splitlines()]
    assert kinds.count("first_open") == 1 and kinds.count("first_open_checked") == 1, kinds
    looks = [json.loads(x) for x in coverage.looks_file(lap.root.name).read_text(encoding="utf-8").splitlines()]
    mine = [(lk["result"], lk.get("note")) for lk in looks if lk.get("path") == ["Cont. Play for Interval"]]
    assert mine == [("not_reached", first_open.PENDING), ("looked", "first open checked"), ("kit_failed", None)], mine
    assert first_open.seen_record(lap.root.name).seen(["Cont. Play for Interval"])
    lap2 = lap_with(tmp_path / "two", monkeypatch, target, seen_target=False)
    assert_lap_went_on(lap2)
    assert lap2.sim.opened(1) and lap2.sim.marked_at_open(1) is False, lap2.keys
    kinds = [json.loads(x).get("kind") for x in lap2.events.splitlines()]
    assert "first_open" not in kinds and "first_open_checked" not in kinds, kinds
    assert len([t for t in at_right if t]) == 1, at_right       # RESTORE_BY_HAND at the first lap's Right alone


def test_k1_a_defined_rows_failed_first_open_skips_that_row_alone(tmp_path, monkeypatch, scope):  # noqa: F811 (the fixture)
    """A failed first open of a row the definition names is recorded under its own name, RESTORE_BY_HAND naming it; the
    next lap skips that row only, while a row still withheld (a label read with a value glued on) opens under its own
    first open, its name withheld as ever."""
    from camkit import first_open, session
    from camkit.runs import RESTORE_BY_HAND
    from exit_status import EXIT_RESTORE_BY_HAND
    scope(BLANK, UNRELATED)
    defined(monkeypatch)
    monkeypatch.setattr(session, "compared", lambda a, b, say=None: [SimpleNamespace(key="global:0x0357")])
    lap = lap_with(tmp_path / "one", monkeypatch, FOCUS_MAG, seen_target=False)
    assert lap.sim.opened(1) and lap.code == EXIT_RESTORE_BY_HAND, (lap.code, lap.out[-800:])
    marker = lap.root / RESTORE_BY_HAND
    assert "Focus Magnifier" in marker.read_text(encoding="utf-8")
    assert lap.row(1)["label"] == "Focus Magnifier", lap.row(1)
    s = first_open.seen_record(lap.root.name)
    assert first_open.key(["Focus Magnifier"]) in s.acting and first_open.key(["(withheld)"]) not in s.acting
    marker.unlink()                                      # upload_check put the start file back
    monkeypatch.setattr(session, "compared", lambda a, b, say=None: [])
    lap2 = crawl_lap(tmp_path / "two", monkeypatch, [DRIVE_MODE, FOCUS_MAG, GLUED, ISO], argv=NETWORK,
                     seen=["Drive Mode", "ISO"])
    assert lap2.code in (0, None), lap2.out[-1500:]
    assert lap2.sim.opened(0) and lap2.sim.opened(3) and not set(lap2.keys) & {"enter", "ms_enter"}
    assert not lap2.sim.opened(1) and not lap2.sim.inside(1), lap2.keys
    assert lap2.outcome(1).startswith("skipped") and lap2.row(1)["label"] == "Focus Magnifier", lap2.row(1)
    assert lap2.sim.opened(2) and lap2.sim.marked_at_open(2) is True, (lap2.outcome(2), lap2.keys)
    assert lap2.row(2)["label"] == "(withheld)", lap2.row(2)
    rows_text = (lap2.run.dir / "rows.jsonl").read_text(encoding="utf-8")
    assert "AAA-1" not in lap2.events + lap2.out + rows_text


@pytest.mark.parametrize("tail,kept", [("Drive Mode", True), ("Focus Magnifier", False)])
def test_k2_a_notices_blocker_that_is_a_known_value_is_withheld_though_the_definition_names_it(tmp_path, monkeypatch,
                                                                                               scope, tail, kept):  # noqa: F811 (the fixture)
    """K2: what of a screen's text a look lap keeps stays judged by runner.known_labels: a Wi-Fi setting's blocker notice
    keeps the row it names after "as follows" where that is a row label the kit knows (Drive Mode), never one that is a
    value the kit knows too (Focus Magnifier, a Custom Key's function), though the definition names that row and the
    lap keeps it as a row's own name."""
    import crawl_run
    scope(UNRELATED)
    defined(monkeypatch)
    head = "This operation or setting not available as follows"
    monkeypatch.setattr(crawl_run, "text_of", lambda cam: f"{head} {tail} OK")
    target = srow("Wi-Fi Frequency Band", "", kind="notice", lines=(head, tail), options=("OK",))
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=True)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1), lap.keys
    assert lap.row(1).get("notice") == (f"{head} {tail}" if kept else head), lap.row(1)


def test_k1_on_the_a1_iis_scan_fewer_top_level_rows_are_withheld(monkeypatch):
    """The a1 II's definition and a page model of its whole menu (read only; skipped without them): fewer top-level rows
    have their own name withheld by a look lap, and each still withheld is a label the definition does not name and the
    kit does not know (a reading with something glued on). The test prints both counts."""
    import json
    from pathlib import Path

    import runner
    from camkit import paths
    root = Path(__file__).resolve().parents[2]
    scan = paths.a1ii_root() / "kit2_page_scan_1113b" / "model.json"
    definition = root / "editor" / "definitions" / "ILCE-1M2_fw4.00.json"
    if not scan.exists() or not definition.exists():
        pytest.skip("the a1 II's page scan is not in this clone")
    doc = json.loads(definition.read_text(encoding="utf-8"))
    model = {p["key"]: p for p in json.loads(scan.read_text(encoding="utf-8"))}
    defined(monkeypatch, doc)
    before, after = withheld_rows(model)
    print(f"top-level rows withheld: {len(before)} before, {len(after)} after")
    assert len(after) < len(before), (len(before), len(after))
    known = {safety.plain(x) for x in runner.row_labels(doc) | runner.known_labels(model)}
    assert not [x for x in after if safety.plain(x) in known]


def withheld_rows(model) -> tuple:
    """(before, after): the page model's rows whose own name a look lap withholds by runner.known_labels alone, as before
    2026-11-15, and by kit/crawl_run.py's row_names."""
    import crawl_run
    import runner
    rows = [r.get("label") or "" for p in model.values() for r in p.get("rows") or []]
    old = {safety.plain(x) for x in runner.known_labels(model)}
    new = {safety.plain(x) for x in crawl_run.row_names(model)}
    return ([x for x in rows if crawl_run.kept_label(x, old) == crawl_run.WITHHELD_LABEL],
            [x for x in rows if crawl_run.kept_label(x, new) == crawl_run.WITHHELD_LABEL])


# ---- after a first open's check that left the menu elsewhere, the lap finds its row again (2026-11-15, the a1 II: a
# Playback row's view left with its button, the check clean, MENU reopened the menu on the Focus tab)

def reopen_on(monkeypatch, at=None, swallow=(), stays_closed=False) -> dict:
    """The simulated camera's opening of the menu after a first open's check (the MENU from the shooting screen once
    the check took RESTORE_BY_HAND away: the key before it went with the marker there, this one without) lands on row
    `at` (None: where the cursor was), or, `stays_closed`, the MENU is taken and nothing opens; after it the first of
    each key in `swallow` is taken and moves nothing. Returns {"at": the trace's length just after that opening}."""
    import test_step3_acceptance as A
    from camkit.runs import RESTORE_BY_HAND
    real, state = A.Sim.key, {"at": None, "swallow": list(swallow)}

    def taken(self, k):
        self.trace.append((k, self.mode, self.pos, self.opt, (self.root / RESTORE_BY_HAND).exists()))

    def key(self, k):
        if state["at"] is not None and k in state["swallow"]:
            state["swallow"].remove(k)
            return taken(self, k)
        checked = (state["at"] is None and k == "menu" and self.mode == "shooting" and self.trace
                   and self.trace[-1][4] and not (self.root / RESTORE_BY_HAND).exists())
        if checked:
            state["at"] = len(self.trace) + 1
            if stays_closed:
                return taken(self, k)
            real(self, k)
            if at is not None:
                self.pos = at
            return
        real(self, k)
    monkeypatch.setattr(A.Sim, "key", key)
    return state


AFTER_CHECK = "after a first open's check the menu is not back on its row"


def refind_keys(lap, state) -> list:
    """The keys sent from the menu's opening after the check to the lap's next Right (or its end)."""
    out = []
    for k, m, *_ in lap.sim.trace[state["at"]:]:
        if k in ("right", "ms_right") and m == "menu":
            break
        out.append((k, m))
    return out


@pytest.mark.parametrize("target", [srow("Grid Line", "", options=("A", "B")), GLUED], ids=["kept", "withheld"])
def test_after_the_check_reopened_the_menu_on_another_row_the_lap_finds_its_row_and_finishes(tmp_path, monkeypatch,
                                                                                           scope, target):  # noqa: F811 (the fixture)
    """The first open's check comes out clean and MENU reopens the menu on another row of a page the scan knows: the lap
    goes to its row once by its own way there (Down, checked against the scan), finds it the row it expected, and goes
    on to the end; no Right or Enter goes out on the way, and nothing of a label the lap withholds is printed."""
    scope(BLANK, UNRELATED)
    state = reopen_on(monkeypatch, at=0)
    lap = lap_with(tmp_path, monkeypatch, target, seen_target=False)
    assert_lap_went_on(lap)
    assert lap.sim.opened(1) and lap.sim.marked_at_open(1) is True and state["at"] is not None
    keys = refind_keys(lap, state)
    assert ("down", "menu") in keys and not [k for k, _ in keys if k in ("right", "ms_right", "enter", "ms_enter")], keys
    assert AFTER_CHECK not in lap.out and "back to the lap's row" in lap.out, lap.out[-1500:]
    assert "AAA-1" not in lap.out + lap.events


@pytest.mark.parametrize("how", ["a step that lands elsewhere", "the menu not reopened"])
def test_after_the_check_a_way_back_that_fails_or_no_menu_stops_the_lap_as_before(tmp_path, monkeypatch, scope, how):  # noqa: F811 (the fixture)
    """Where the way back to the row lands elsewhere (a Down the camera did not take: the screen is not the scan's next),
    or the menu did not reopen at all (nothing pressed then), the lap stops as before: its message, exit 8, its start
    file back."""
    from exit_status import EXIT_INCOMPLETE
    scope(BLANK, UNRELATED)
    state = (reopen_on(monkeypatch, at=0, swallow=("down",)) if how.startswith("a step") else
             reopen_on(monkeypatch, stays_closed=True))
    lap = lap_with(tmp_path, monkeypatch, srow("Grid Line", "", options=("A", "B")), seen_target=False)
    assert lap.code == EXIT_INCOMPLETE, (lap.code, lap.out[-1500:])
    assert f"position 1: {AFTER_CHECK}" in lap.out, lap.out[-1500:]
    assert not lap.sim.opened(2), lap.keys
    keys = refind_keys(lap, state)
    assert not [k for k, _ in keys if k in ("right", "ms_right", "enter", "ms_enter")], keys
    if how.startswith("a step"):
        assert keys[:1] == [("down", "menu")], keys
    else:
        assert keys == [], keys                              # after the MENU the camera did not answer, nothing


# A menu of three tabs of three groups of three rows each, as the tab column, the group column and the rows show it
TAB_GROUPS = {"Focus": ["Focus Assistant", "Face/Eye AF", "Peaking Display"],
              "Playback": ["Magnification", "Playback Option", "Selection/Search"],
              "Network": ["Wi-Fi", "Bluetooth", "Network Option"]}


class TabsCamera:
    """TAB_GROUPS as the camera shows it, each group one page of `rows` rows in the scan's Down cycle (tab by tab, in the
    menu's order): Left from the rows to the group column and on to the tab column; Up and Down there a tab or a group;
    Right from the tab column into the group column, on the group last used in that tab, and from there into the
    group's first row (or `astray`: a page the scan does not know); Up and Down in the rows a step of the Down cycle;
    MENU closes the menu and opens it where it was. The first of each key in `stuck` is taken and does nothing. Every
    key is kept with the focus it went out in ("shooting" with the menu closed)."""

    def __init__(self, rows=3, groups=None):
        self.names = list((groups or TAB_GROUPS).items())
        self.order = [(t, g, r) for t, (_, gs) in enumerate(self.names) for g in range(len(gs)) for r in range(rows)]
        self.rows, self.shown, self.focus, self.at, self.tab, self.group, self.last = rows, False, "rows", 0, 0, 0, {}
        self.sent, self.stuck, self.astray = [], [], False
        self.may_open = frozenset()
        self.frame = SimpleNamespace(image=None, path=None)

    def press(self, key, **kw):
        self.sent.append((key, self.focus if self.shown else "shooting"))
        if key in self.stuck:
            self.stuck.remove(key)
            return
        if key == "menu":
            self.shown = not self.shown
        elif not self.shown:
            return
        elif self.focus == "rows" and key in ("up", "down") and self.at is not None:
            self.at = (self.at + (1 if key == "down" else -1)) % len(self.order)
        elif self.focus == "rows" and key == "left":
            self.focus = "groups"
            if self.at is not None:
                self.tab, self.group, _ = self.order[self.at]
        elif self.focus == "groups" and key in ("up", "down"):
            self.group = max(0, min(len(self.names[self.tab][1]) - 1, self.group + (1 if key == "down" else -1)))
        elif self.focus == "groups" and key == "left":
            self.focus = "tabs"
        elif self.focus == "groups" and key == "right":
            self.last[self.tab] = self.group
            self.focus, self.at = "rows", None if self.astray else self.order.index((self.tab, self.group, 0))
        elif self.focus == "tabs" and key in ("up", "down"):
            self.tab = max(0, min(len(self.names) - 1, self.tab + (1 if key == "down" else -1)))
        elif self.focus == "tabs" and key == "right":
            self.focus, self.group = "groups", self.last.get(self.tab, 0)

    def read(self):
        if not self.shown:
            return SimpleNamespace(kind="shooting", focus=None, where=("shooting",))
        if self.focus == "rows":
            return SimpleNamespace(kind="menu", focus="rows",
                                   where=("rows", *self.order[self.at]) if self.at is not None else ("rows", "unknown"))
        return SimpleNamespace(kind="menu", focus=self.focus, where=(self.focus, self.tab, self.group))

    def place(self) -> tuple:
        return self.order[self.at][:2] if self.focus == "rows" and self.at is not None else (self.tab, self.group)

    def lit(self) -> str:
        t, g = self.place()
        if self.focus == "tabs":
            return self.names[t][0]
        if self.focus == "groups":
            return self.names[t][1][g]
        return f"{self.names[t][1][g]} row {self.order[self.at][2]}" if self.at is not None else "Made-up Row"

    def text(self) -> str:
        t, g = self.place()
        return f"{self.names[t][0]} > {self.names[t][1][g]}"

    def scan(self) -> tuple:
        cycle = [{"kind": "menu", "page": f"p{t}{g}", "row": r,
                  "screen": SimpleNamespace(kind="menu", focus="rows", where=("rows", t, g, r))} for t, g, r in self.order]
        model = {f"p{t}{g}": {"breadcrumb": f"{tab} > {gs[g]}", "page": f"{3 * t + g + 1}/9",
                              "rows": [{"label": f"{gs[g]} row {r}", "never_open": None} for r in range(self.rows)]}
                 for t, (tab, gs) in enumerate(self.names) for g in range(len(gs))}
        return cycle, model


class Check:
    """camkit.crawl's `first` with one top-level row's first open pending (the cycle's position `due_at`): its check
    closes the menu with MENU, `reopen(cam)` says where the camera then holds its menu, and MENU opens it there; `after`,
    how many keys the camera had had once the check was done."""

    def __init__(self, cam, due_at, reopen):
        self.cam, self.due_at, self.reopen = cam, due_at, reopen
        self.pending, self.seen, self.skip_why, self.after = [("the row",)], None, "", None

    def skips(self, path) -> bool:
        return False

    def takes(self, look) -> bool:
        return False

    def due(self, pos, nxt) -> bool:
        return pos is self.due_at

    def settle(self, cam) -> None:
        cam.press("menu")
        self.reopen(self.cam)
        cam.press("menu")
        self.pending, self.after = [], len(self.cam.sent)


def tabs_lap(monkeypatch, reopen, stuck=(), astray=False, groups=None, target=(1, 2, 1)):
    """kit/crawl_run.py's crawl_from_menu over a TabsCamera (of `groups`), every row settled by the ledger (none opened),
    the first open of the row at `target` (tab, group, row: Playback > Selection/Search row 1) pending there. Returns
    (camera, complete, console, its first, position)."""
    import crawl_run
    from camkit import crawl as crawling
    cam = TabsCamera(groups=groups)
    cycle, model = cam.scan()
    same = lambda a, b: getattr(a, "where", None) == getattr(b, "where", None)       # noqa: E731
    monkeypatch.setattr(crawl_run, "same_position", same)
    monkeypatch.setattr(crawling, "same_position", same)
    monkeypatch.setattr(crawl_run, "lit_text", lambda image, path: cam.lit())
    monkeypatch.setattr(crawl_run, "menu_text", lambda c: cam.text())
    at = cam.order.index(target)
    first = Check(cam, cycle[at], lambda c: (reopen(c), c.stuck.extend(stuck), setattr(c, "astray", astray)))
    ledger = SimpleNamespace(after=lambda row, model, **kw: None, skip=lambda page, row, opened=True: "settled: here")
    link = SimpleNamespace(press=lambda key, **kw: cam.press(key))
    import contextlib
    import io
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        complete = crawl_run.crawl_from_menu(cam, link, cycle, model, None, io.StringIO(), ledger=ledger, first=first,
                                             tabs=tuple(TAB_GROUPS))
    return cam, complete, out.getvalue(), first, at


def on_focus_page(cam):
    """The camera holds its menu on the Focus tab's second page (the page last used before a Playback row's view)."""
    cam.focus, cam.at = "rows", cam.order.index((0, 1, 1))


def test_after_the_check_reopened_the_menu_on_another_tabs_page_the_lap_jumps_back_and_finishes(monkeypatch):
    """The menu reopens on the Focus tab after the check of a Playback row: the lap goes back once by its own way (the
    tab and group columns, jump, then Down), finds the very row, and crawls on to the end; no Right on a row and no
    Enter go out on the way, only the columns' Rights the jump sends."""
    cam, complete, out, first, at = tabs_lap(monkeypatch, on_focus_page)
    assert complete and "lap complete" in out and first.after is not None, out
    back = cam.sent[first.after:]
    assert back[:8] == [("left", "rows"), ("left", "groups"), ("down", "tabs"), ("right", "tabs"),
                        ("down", "groups"), ("down", "groups"), ("right", "groups"), ("down", "rows")], back
    assert not [k for k in cam.sent if k == ("right", "rows") or k[0] in ("enter", "ms_enter")], cam.sent
    assert AFTER_CHECK not in out


@pytest.mark.parametrize("how", ["astray", "stuck"])
def test_after_the_check_a_jump_that_lands_elsewhere_stops_the_lap_as_before(monkeypatch, how):
    """The jump lands on a page the scan does not know, or a column's step is not taken: the lap goes back once, is not
    on its row, and stops with the message it stopped with before (crawl_from_menu says the lap incomplete: exit 8)."""
    cam, complete, out, first, at = tabs_lap(monkeypatch, on_focus_page, **(
        {"astray": True} if how == "astray" else {"stuck": ("down",)}))
    assert not complete and f"position {at}: {AFTER_CHECK}" in out, out
    back = cam.sent[first.after:]
    assert back.count(("left", "rows")) == 1, back                       # once, never a second try
    assert not [k for k in cam.sent if k == ("right", "rows") or k[0] in ("enter", "ms_enter")], cam.sent


def in_group_column(cam):
    cam.focus, cam.tab, cam.group = "groups", 0, 1


def on_unknown_page(cam):
    cam.focus, cam.at = "rows", None


def menu_stays_closed(cam):
    cam.stuck.append("menu")


@pytest.mark.parametrize("reopen", [in_group_column, on_unknown_page, menu_stays_closed])
def test_after_the_check_a_screen_that_is_no_plain_menu_page_the_scan_knows_stops_as_before(monkeypatch, reopen):
    """The cursor in the group column, a page the scan does not know, the menu not reopened: nothing is pressed to go
    back (but the closing MENU on a menu), and the lap stops with its message as before."""
    cam, complete, out, first, at = tabs_lap(monkeypatch, reopen)
    assert not complete and f"position {at}: {AFTER_CHECK}" in out, out
    assert set(cam.sent[first.after:]) <= {("menu", "groups"), ("menu", "rows")}, cam.sent[first.after:]


def test_after_the_check_no_jump_into_a_group_the_column_never_enters_and_no_long_walk(monkeypatch):
    """The lap's row is in a group the group column never enters (FTP Transfer): the way back makes no jump and, unlike
    --start-label's, walks no rows the long way either; nothing is pressed and the lap stops as before."""
    groups = {**TAB_GROUPS, "Network": ["Wi-Fi", "FTP Transfer", "Network Option"]}
    cam, complete, out, first, at = tabs_lap(monkeypatch, on_focus_page, groups=groups, target=(2, 1, 1))
    assert not complete and f"position {at}: {AFTER_CHECK}" in out and "no jump to" in out, out
    assert set(cam.sent[first.after:]) <= {("menu", "rows")}, cam.sent[first.after:]
