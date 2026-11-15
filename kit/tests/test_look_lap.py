"""The look lap's predicate and the opening check's row (docs/decisions/0024): safety.look_lap_refused, safety.row_judged
and the crawl's own use of them, and each layer's look lock on its own; and the review of 604a87a's findings, on the
acceptance tests' harness (the camera knows the row it is opening, a look lap writes no label it does not keep, each 1
read as 1, i or l), and of 235b088's (a withheld row's failed first open stands, each reading judged by its own path).
The end-to-end behaviour is test_step3_acceptance.py's."""
from types import SimpleNamespace

import pytest

from camkit import crawl, live, safety
from camkit.runs import Run
from test_step3_acceptance import BLANK, DRIVE_MODE, ISO, NETWORK, UNRELATED, crawl_lap, lap_with, srow
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
