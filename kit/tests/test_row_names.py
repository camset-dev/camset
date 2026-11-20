"""Older row names and the camera's, one row (camkit.row_names, the hand tables' ROW_NAMES): a row the records hold by
a name the kit once read with the camera's icon glued on ("Proxy Settings > Px Proxy Recording", "S&Q Settings > S&Q
Record Setting", proof lines 9425 and 9426 of the a1 II's kit2_pass2) is the row the camera draws ("Proxy Settings >
Proxy Recording"), wherever a row's name is compared: the rows seen opened, prove_run's --rows, pass 1's map, the menu
tree, each setting's place, the walk patterns, the definition's proof rows, the report's rows and the ledger. The
runs' lines stay as written. A made-up camera's hand tables in the test's own data folder; nothing talks to a camera,
and no file of the clone's data/ is read or written."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from camkit import datafiles, definitions, row_names  # noqa: E402
from conftest import TEST_CAMERA  # noqa: E402

NAMES = {"Proxy Settings > Px Proxy Recording": "Proxy Settings > Proxy Recording",
         "S with Shutter Button": "with Shutter Button",
         "S&Q Settings > S&Q Record Setting": "S&Q Settings > Record Setting",
         "Rec. Media Settings > Recording Media (Movie)": "Rec. Media Settings > Recording Media#1"}
# the a1 II's nine rows the records name otherwise than the camera draws them (the report of 2026-11-20)
A1II_ROWS = {"S with Shutter Button": "with Shutter Button",
             "Proxy Settings > Px Proxy Recording": "Proxy Settings > Proxy Recording",
             "Proxy Settings > Px Proxy Rec. Settings": "Proxy Settings > Proxy Rec. Settings",
             "Proxy Settings > Px Proxy File Format": "Proxy Settings > Proxy File Format",
             "MR Recall Camera Setting": "Recall Camera Setting",
             "MR Camera Set. Memory": "Camera Set. Memory",
             "MR Memory/Recall Media": "Memory/Recall Media",
             "S&Q Settings > S&Q Record Setting": "S&Q Settings > Record Setting",
             "Rec. Media Settings > Recording Media (Movie)": "Rec. Media Settings > Recording Media#1"}
SAFETY_LISTED = ("MR Recall Camera Setting", "MR Camera Set. Memory", "MR Memory/Recall Media")


def hand_tables(data: Path, **tables) -> Path:
    p = datafiles.hand_tables_file(TEST_CAMERA)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"$schema": "../../schemas/hand-tables.schema.json", "camera": TEST_CAMERA, **tables}),
                 encoding="utf-8")
    row_names.forget()                      # a table is read once a process: this one afresh
    return p


@pytest.fixture
def named(tmp_path, monkeypatch):
    """The made-up camera's hand tables with NAMES as its ROW_NAMES, in the test's own data folder."""
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    yield hand_tables(tmp_path / "data", ROW_NAMES=NAMES)
    row_names.forget()


@pytest.fixture
def unnamed(tmp_path, monkeypatch):
    """The made-up camera with hand tables holding no ROW_NAMES."""
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    yield hand_tables(tmp_path / "data")
    row_names.forget()


# ---------------------------------------------------------------- the table

def test_an_older_name_is_the_cameras_and_so_is_every_row_under_it(named):
    assert row_names.renamed(["Proxy Settings", "Px Proxy Recording"]) == ("Proxy Settings", "Proxy Recording")
    assert row_names.renamed(("S with Shutter Button", "Sub")) == ("with Shutter Button", "Sub")
    assert row_names.renamed(["s with  shutter button"]) == ("with Shutter Button",)         # compared plain
    assert row_names.renamed(["Proxy Settings"]) == ("Proxy Settings",)                      # none above the row
    assert row_names.renamed(["Proxy Settings", "Proxy File Format"]) == ("Proxy Settings", "Proxy File Format")
    assert row_names.renamed_name("S&Q Settings > S&Q Record Setting [Movie mode, 120p]") == \
        "S&Q Settings > Record Setting [Movie mode, 120p]"
    assert row_names.renamed_name("S with Shutter Button / Add Shot Mark1") == "with Shutter Button / Add Shot Mark1"
    assert row_names.renamed_name("Drive Mode [Movie mode]") == "Drive Mode [Movie mode]"
    assert row_names.same("Proxy Settings > Px Proxy Recording", ("Proxy Settings", "Proxy Recording"))
    assert not row_names.same("Proxy Settings > Px Proxy Recording", "Proxy Settings > Proxy File Format")


def test_a_pattern_written_with_either_name_finds_the_row(named):
    got = row_names.names("Proxy Settings > Proxy Recording [Movie mode]")
    assert got == ["Proxy Settings > Proxy Recording [Movie mode]", "Proxy Settings > Px Proxy Recording [Movie mode]"]
    assert set(row_names.names("Proxy Settings > Px Proxy Recording")) == {
        "Proxy Settings > Px Proxy Recording", "Proxy Settings > Proxy Recording"}
    assert row_names.names("Drive Mode") == ["Drive Mode"]


def test_a_run_asking_by_either_name_gets_the_maps_own(named):
    held = ["S&Q Settings > S&Q Record Setting", "Drive Mode"]
    assert row_names.as_in(["S&Q Settings > Record Setting", "Drive Mode", "Nowhere"], held) == \
        ["S&Q Settings > S&Q Record Setting", "Drive Mode", "Nowhere"]
    assert row_names.as_in(["S&Q Settings > S&Q Record Setting"], ["S&Q Settings > Record Setting"]) == \
        ["S&Q Settings > Record Setting"]
    assert row_names.as_in(["Proxy Settings > Proxy Recording / grid 1"], ["Proxy Settings > Px Proxy Recording"]) == \
        ["Proxy Settings > Proxy Recording / grid 1"]                     # what follows the path must be the same


def test_a_camera_with_no_table_has_every_name_as_it_is(unnamed):
    """No table: every name as it is, and a run's --rows compared exactly (as_in never takes a name plain-alike)."""
    assert row_names.table() == {}
    assert row_names.renamed(["Proxy Settings", "Px Proxy Recording"]) == ("Proxy Settings", "Px Proxy Recording")
    assert row_names.renamed_name("S with Shutter Button [x]") == "S with Shutter Button [x]"
    assert row_names.as_in(["S&Q Settings > Record Setting"], ["S&Q Settings > S&Q Record Setting"]) == \
        ["S&Q Settings > Record Setting"]
    assert row_names.as_in(["drive mode", "Exposure Comp"], ["Drive Mode", "Exposure Comp."]) == \
        ["drive mode", "Exposure Comp"]


def test_the_a1_iis_rows_that_fit_the_one_kind_and_the_three_a_safety_list_names():
    """The one kind (row_names.fault): the camera's path the older one with its last label less a leading token of at
    most ICON_LEAD characters, or the kit's "#n" form of it; the labels above the same; no label a safety list names.
    Six of the a1 II's nine rows fit; the three MR rows do not, as the never-open list (Recall Camera Setting, Camera
    Set. Memory) and OWNER_NEVER ("recall") name them."""
    fit = {o: n for o, n in A1II_ROWS.items() if o not in SAFETY_LISTED}
    assert len(row_names.read(fit)) == 6
    for old in SAFETY_LISTED:
        with pytest.raises(ValueError, match="a safety list names"):
            row_names.read({old: A1II_ROWS[old]})


@pytest.mark.parametrize("entries, words", [
    ({"Format": "File Format"}, "less a leading token"),                                   # a word added
    ({"Media Settings > Delete All": "Media Settings > Auto Switch Media"}, "less a leading token"),
    ({"Network Option > IP Address Setting": "Network Option > Airplane Mode"}, "less a leading token"),
    ({"Proxy Settings > Px Proxy Recording": "Network > Proxy Recording"}, "only its last label"),   # another parent
    ({"A": "B", "B > C": "D > E"}, "less a leading token|only its last label"),
    ({"X Proxy": "Proxy", "Proxy > Px Sub": "Proxy > Sub"}, "renamed twice"),               # a camera path starts another
    ({"Px Proxy > Px Sub": "Px Proxy > Sub", "Px Proxy": "Proxy"}, "renamed twice"),        # an older path starts another
    ({"Proxy Settings > Proxies Recording": "Proxy Settings > Recording"}, "less a leading token"),    # 7 characters
    ({"LANIP Address Setting": "IP Address Setting"}, "less a leading token"),              # glued, no space
    ({"Rec > Recording Media (Movie)": "Rec > Other#1"}, "less a leading token"),
    ({"Rec > Recording Media": "Rec > Recording Media#1"}, "less a leading token"),          # a bare label to its #n
    ({"Px Format": "Format"}, "a safety list names"),                                      # a destructive row
    ({"S Initialize": "Initialize"}, "a safety list names"),                                 # OWNER_NEVER
    ({"A > Px B": "A > Px b"}, "renames the row to itself"),
    ({"A >  > B": "A > C"}, "a row's path"),
    ({"A > B": 3}, "a row's path"),
    (["A > B"], "no object"),
])
def test_a_table_the_kit_cannot_use_is_refused(entries, words):
    with pytest.raises(ValueError, match=words):
        row_names.read(entries)


def test_the_hand_tables_reader_and_schema_take_row_names_and_refuse_another_kind(tmp_path, monkeypatch):
    from writer import hand_evidence, hand_facts, hand_tables as H
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    p = hand_tables(tmp_path / "data", ROW_NAMES=NAMES)
    tables = H.load(TEST_CAMERA, evidence=False)
    assert tables.ROW_NAMES == NAMES
    assert hand_evidence.schema_problems(json.loads(p.read_text(encoding="utf-8")), "hand-tables") == []
    assert not [x for x in hand_facts.refusals(tables) if "ROW_NAMES" in x]            # the plain pass takes it
    hand_tables(tmp_path / "data", ROW_NAMES={"Format": "File Format"})
    with pytest.raises(H.Refused, match="ROW_NAMES"):
        H.load(TEST_CAMERA, evidence=False)
    row_names.forget()


# ---------------------------------------------------------------- no safety check sees a renamed name

def made_up_records(own_runs):
    """The made-up camera's crawl, its records showing File Format, Media Settings > Auto Switch Media, Network Option >
    Airplane Mode and Proxy Settings > Proxy Recording opened, never Format, Delete All or IP Address Setting."""
    run = own_runs / TEST_CAMERA / "kit2_crawl_seen"
    run.mkdir(parents=True)
    rows = [{"label": "File Format", "outcome": "walked"},
            {"label": "Media Settings", "outcome": "submenu crawled",
             "submenu": [{"label": "Auto Switch Media", "outcome": "walked"}]},
            {"label": "Network Option", "outcome": "submenu crawled",
             "submenu": [{"label": "Airplane Mode", "outcome": "walked"}]},
            {"label": "Proxy Settings", "outcome": "submenu crawled",
             "submenu": [{"label": "Proxy Recording", "outcome": "walked"}]}]
    (run / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


INJECTED = {"Format": "File Format", "Media Settings > Delete All": "Media Settings > Auto Switch Media",
            "Network Option > IP Address Setting": "Network Option > Airplane Mode",
            "Proxy Settings > Px Proxy Recording": "Network > Proxy Recording"}


@pytest.mark.parametrize("injected", [True, False], ids=["injected past the loader", "no table"])
def test_a_look_lap_still_refuses_a_destructive_row_whatever_table_is_handed_in(own_runs, unnamed, monkeypatch,
                                                                              injected):
    """Entries the loader refuses, handed in past it (camkit.row_names.table replaced): the seen records fold none of
    them (renamed applies an entry only of the one kind), the look lap's checks judge the records under the labels the
    camera draws now (Seen.seen_as_drawn), and Format and Delete All are still refused, IP Address Setting still a
    first open, and no parent counted seen for another's row; as with no table at all."""
    import drive
    from camkit import crawl, first_open
    made_up_records(own_runs)
    if injected:
        monkeypatch.setattr(row_names, "table", lambda camera=None: {
            row_names._key(row_names.labels(o)): (row_names.labels(o), row_names.labels(n)) for o, n in INJECTED.items()})
    seen = first_open.seen_record(TEST_CAMERA)
    assert seen.seen(("File Format",)) and seen.seen(("Media Settings", "Auto Switch Media"))
    for path in (("Format",), ("Media Settings", "Delete All"), ("Network Option", "IP Address Setting"),
                 ("Network",), ("Network", "Proxy Recording")):
        assert not seen.seen(path) and not seen.seen_as_drawn(path), path
    told = crawl.seen_of(SimpleNamespace(seen=seen))
    assert told is not None and not told(("Format",))
    assert crawl.look_open({"label": "Format"}, told, ()) and crawl.look_open({"label": "Delete All"}, told,
                                                                               ("Media Settings",))
    with pytest.raises(SystemExit, match="nothing was sent to the camera"):
        drive.look_path_or_exit(["Format"], seen)


def test_the_look_laps_seen_never_takes_an_older_name_even_of_the_one_kind(own_runs, tmp_path, monkeypatch):
    """A table of the one kind folds Proxy Recording's older name in the first-open procedure's seen (key), while the
    look lap's seen (seen_as_drawn) judges the records as written: "Px Proxy Recording" is seen there only where the
    records hold that very name."""
    from camkit import first_open
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    hand_tables(tmp_path / "data", ROW_NAMES={"Proxy Settings > Px Proxy Recording": "Proxy Settings > Proxy Recording"})
    made_up_records(own_runs)
    seen = first_open.seen_record(TEST_CAMERA)
    assert seen.seen(("Proxy Settings", "Px Proxy Recording"))                 # the first-open procedure: one row
    assert not seen.seen_as_drawn(("Proxy Settings", "Px Proxy Recording"))   # a safety check: as the camera draws it
    assert seen.seen_as_drawn(("Proxy Settings", "Proxy Recording"))
    row_names.forget()


def test_a_crawls_row_is_renamed_on_its_whole_path_at_once(named):
    """first_open._crawl_rows keys a row on its whole path as the crawl wrote it, renamed at once (as kit/pass1_map.py's
    unseen_only does), never a parent renamed and its rows then judged under the new parent."""
    from camkit import first_open
    opened, greyed = set(), set()
    first_open._crawl_rows({"label": "Proxy Settings", "outcome": "submenu crawled", "submenu": [
        {"label": "Px Proxy Recording", "outcome": "walked", "submenu": [{"label": "Deep", "outcome": "walked"}]}]},
        (), opened, greyed)
    assert ("proxy settings", "proxy recording", "deep") in opened
    drawn = set()
    first_open._crawl_rows({"label": "Proxy Settings", "outcome": "submenu crawled", "submenu": [
        {"label": "Px Proxy Recording", "outcome": "walked"}]}, (), drawn, set(), first_open.raw_key)
    assert ("proxy settings", "px proxy recording") in drawn


# ---------------------------------------------------------------- what compares a row's name

def test_a_row_seen_opened_under_its_older_name_is_seen_under_the_cameras(named):
    """camkit.first_open: a row the records hold opened as "Proxy Settings > Px Proxy Recording" is no row never opened
    on this body when a run reaches it as Proxy Recording, and the other way round; a row the table does not name is as
    it was."""
    from camkit import first_open
    assert first_open.key(["Proxy Settings", "Px Proxy Recording"]) == first_open.key(["Proxy Settings", "Proxy Recording"])
    seen = first_open.Seen(opened=first_open._with_parents(first_open.key(["Proxy Settings", "Px Proxy Recording"])))
    assert seen.seen(["Proxy Settings", "Proxy Recording"]) and seen.seen(["Proxy Settings", "Px Proxy Recording"])
    assert not seen.seen(["Proxy Settings", "Proxy File Format"])
    opened, greyed = set(), set()
    first_open._crawl_rows({"label": "Proxy Settings", "outcome": "submenu crawled", "submenu": [
        {"label": "Px Proxy Recording", "outcome": "walked"}]}, (), opened, greyed)
    assert first_open.Seen(opened=opened).seen(("Proxy Settings", "Proxy Recording"))


def test_prove_run_takes_a_row_asked_by_the_cameras_name_from_a_map_that_holds_the_older(own_runs, named, monkeypatch,
                                                                                        capsys):
    """prove_run --rows "S&Q Settings > Record Setting" on a map whose crawl read the S&Q box into the label: the row is
    the map's, where before 2026-11-20 the run stopped, "not provable rows in the scope"."""
    import prove_run
    import proving.base as base
    from camkit import models
    from runner import SCOPE_FILE
    root = own_runs / TEST_CAMERA / "kit2_pass1"
    root.mkdir(parents=True)
    (root / SCOPE_FILE).write_text(json.dumps({"prove": [], "exclude": {}}), encoding="utf-8")
    (root / "map_all.json").write_text(json.dumps({"rows": [
        {"path": ["S&Q Settings", "S&Q Record Setting"], "kind": "list",
         "options": [{"index": 0, "label": "100M 4:2:0 8bit", "frame": "00011_down.png"},
                     {"index": 1, "label": "60M 4:2:0 8bit", "frame": "00010_right.png"}]}]}), encoding="utf-8")
    monkeypatch.setattr(base, "PASS1", root)
    monkeypatch.setattr(base, "MAP", root / "map_all.json")
    monkeypatch.setattr(base, "AXES", root / "no_axes.json")
    monkeypatch.setattr(prove_run.models, "current", lambda r: models.A1II)
    monkeypatch.setattr(prove_run, "load_scan", lambda scan, **k: ([], {}))
    monkeypatch.setattr(prove_run, "Link", lambda run: pytest.fail("the link opened"))
    monkeypatch.setattr(sys, "argv", ["prove_run.py", "--rows", "S&Q Settings > Record Setting", "--list"])
    prove_run.main()
    assert "1 rows to prove, 2 options" in capsys.readouterr().out
    hand_tables(Path(definitions.DATA))                              # no ROW_NAMES: the run stops as it did
    with pytest.raises(SystemExit, match="not provable rows in the scope"):
        prove_run.main()


def test_pass1s_map_names_each_row_as_the_camera_draws_it(own_runs, named):
    import pass1_map
    run = own_runs / TEST_CAMERA / "kit2_crawl_x"
    run.mkdir(parents=True)
    (run / "options.jsonl").write_text("".join(json.dumps(o) + "\n" for o in [
        {"path": ["S&Q Settings", "S&Q Record Setting"], "kind": "list", "index": i, "frame": f, "ocr": lab,
         "vlm": {"selected": lab}, "agreed": True}
        for i, (lab, f) in enumerate([("100M 4:2:0 8bit", "00011_down.png"), ("60M 4:2:0 8bit", "00012_down.png")])]),
        encoding="utf-8")
    m = pass1_map.build(run)
    assert [r["path"] for r in m["rows"]] == [["S&Q Settings", "Record Setting"]]


def test_the_menu_tree_folds_an_older_name_into_the_cameras_row(own_runs, named, tmp_path, capsys):
    """kit/tools/menu_tree.py --fold: a tree written with "Px Proxy Recording" and a crawl that reads "Proxy Recording"
    are one row, named as the camera draws it, never a second row added."""
    import menu_tree
    out = tmp_path / "menu_tree.json"
    datafiles.write_menu_tree(out, {"model": "TEST-CAM", "firmware": "9.99", "source": "made up", "tabs": [{"tab": "Shooting", "pages": [
        {"page": "4/9", "group": "Image Quality", "rows": [
            {"label": "Proxy Settings", "state": "submenu", "kind": "submenu", "why": "", "children": [
                {"label": "Px Proxy Recording", "state": "seen", "why": "not walked", "kind": ""}]}]}]}]})
    crawl = own_runs / TEST_CAMERA / "kit2_crawl_px"
    crawl.mkdir(parents=True)
    (crawl / "rows.jsonl").write_text(json.dumps(
        {"page": "4/9", "slot": 5, "label": "Proxy Settings", "outcome": "submenu crawled", "kind": "submenu",
         "submenu": [{"page": "s", "slot": 0, "label": "Proxy Recording", "outcome": "walked", "kind": "list"}]}) + "\n",
        encoding="utf-8")
    menu_tree.main(["--fold", "kit2_crawl_px", "--out", str(out)])
    rows = datafiles.load_menu_tree(out)["tabs"][0]["pages"][0]["rows"][0]["children"]
    assert [(r["label"], r["state"]) for r in rows] == [("Proxy Recording", "walked")]
    assert menu_tree.camed({"label": "S with Shutter Button", "submenu": [{"label": "x"}]})["label"] == \
        "with Shutter Button"


def test_placement_reads_a_path_and_a_tree_written_with_older_names_as_the_cameras(named):
    from camkit import placement
    assert placement.split("Proxy Settings > Px Proxy Recording [Movie mode]") == ["Proxy Settings", "Proxy Recording"]
    assert placement.steps("S with Shutter Button / Add Shot Mark1")[0] == ("", "with Shutter Button")
    tree = {"tabs": [{"tab": "Shooting", "pages": [{"page": "4/9", "group": "Image Quality", "rows": [
        {"label": "Proxy Settings", "state": "submenu", "children": [{"label": "Px Proxy Recording", "state": "walked"}]}]}]}]}
    t = placement.Tree({"tabs": ["Shooting"], "menu": []}, tree)
    node = t.tabs[0]["groups"][0]["rows"][0]
    assert node["kids"][0]["l"] == "Proxy Recording"
    assert t.find("Shooting", ["Proxy Settings", "Proxy Recording"]) is node["kids"][0]


def test_the_report_the_walk_patterns_the_definitions_rows_and_the_ledger_take_either_name(named):
    """kit/pass2_report.py's row (and a failure's key), a NOT_OFFERED or PICKER_LISTS walk written with the older name
    (writer/offered.walk_matches), the definition's proof rows (writer/proofs.menu_row: the two proof rows the data pass
    of 2026-11-20 renamed through CONTEXT_WORDS, "S&Q Settings > S&Q Record Setting" and "Recording Media (Movie)",
    renamed so with no CONTEXT_WORDS at all) and the coverage ledger's find."""
    import pass2_report
    from camkit import coverage
    from writer import offered, proofs
    line = {"path": ["S&Q Settings", "S&Q Record Setting"], "kind": "list", "context": "Movie mode, 120p"}
    assert pass2_report.row_name(line) == "S&Q Settings > Record Setting [Movie mode, 120p]"
    assert pass2_report.fail_key(line) == "S&Q Settings > Record Setting"
    assert offered.walk_matches(r"^Proxy Settings > Px Proxy Rec", "Proxy Settings > Proxy Recording [Movie mode]")
    assert offered.walk_matches(r"^Proxy Settings > Proxy Rec", "Proxy Settings > Px Proxy Recording")
    assert not offered.walk_matches(r"^Proxy Settings > Proxy File", "Proxy Settings > Proxy Recording")
    with proofs.reworded({}):
        assert proofs.menu_row("S&Q Settings > S&Q Record Setting [Movie mode]", frozenset()) == \
            "S&Q Settings > Record Setting [Movie mode]"
        assert proofs.menu_row("Rec. Media Settings > Recording Media (Movie) [Movie mode]", frozenset()) == \
            "Rec. Media Settings > Recording Media#1 [Movie mode]"
    entry = {"path": ["Proxy Settings", "Proxy Recording"], "mode": "Movie", "tab": "Shooting", "group": "Image Quality"}
    led = SimpleNamespace(rows=[entry])
    assert coverage.Ledger.find(led, ["Proxy Settings", "Px Proxy Recording"]) == [entry]
    old = SimpleNamespace(rows=[{**entry, "path": ["Proxy Settings", "Px Proxy Recording"]}])
    assert coverage.Ledger.find(old, ["Proxy Settings", "Proxy Recording"]) == old.rows


def test_an_axis_row_named_after_its_value_loses_the_value_under_either_name(tmp_path, monkeypatch):
    """Decision 16: an axis row the report names after the value the axis stood on ("ISO > ISO AUTO Min. SS / 1/250",
    the camera's own setting when the row began) is named by its item alone in proved.menu, where its proof lines were
    written with an older name ("MR ISO"): writer/proofs.axis_value_rows and schema_update.proof_shapes key the rows
    as the camera draws them, as the report and menu_row name them (the review of 2026-11-20)."""
    import schema_update
    from writer import proofs
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    hand_tables(tmp_path / "data", ROW_NAMES={"MR ISO": "ISO"})
    lines = [{"kind": "axis", "path": ["MR ISO", "ISO AUTO Min. SS"], "option": "1/250", "label": lab}
             for lab in ("1/250", "1/125", "1/60")]
    axis = proofs.axis_value_rows(lines)
    assert axis == {("ISO > ISO AUTO Min. SS", "1/250")}
    with proofs.reworded({}):
        for row in ("ISO > ISO AUTO Min. SS / 1/250 [Stills mode]", "MR ISO > ISO AUTO Min. SS / 1/250 [Stills mode]"):
            assert proofs.menu_row(row, axis) == "ISO > ISO AUTO Min. SS [Stills mode]", row
    kinds, pickers, axes = schema_update.proof_shapes(lines + [
        {"kind": "table", "path": ["MR ISO", "Picker Row"], "option": "Cell", "opens": "picker"}])
    assert kinds["ISO > ISO AUTO Min. SS"] == "axis" and ("ISO > ISO AUTO Min. SS", "1/250") in axes
    assert pickers == {"ISO > Picker Row / Cell"}
    row_names.forget()


def test_a_lit_bar_is_measured_by_the_label_it_reads_never_by_its_renaming(tmp_path, monkeypatch):
    """kit/drive.py lit_refused measures what the bar reads past a row by the row's label as read (safety.plain), and
    compares rows by first_open.key only for seen and the --path's own row: a bar reading exactly "Px Proxy Recording",
    the older name of the --path's Proxy Recording, is that row, where the renamed label's length made it run on past
    the row ("ing"); with no table a longer row a seen row's label starts ("Face Priority Frame") still runs on past it
    (the review of 2026-11-20)."""
    import drive
    from camkit import first_open
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    hand_tables(tmp_path / "data")
    seen = first_open.Seen(opened=first_open._with_parents(first_open.key(("Setup", "Face Priority"))))
    why, row = drive.lit_refused("Face Priority Frame", ["Setup"], ["Setup", "Other Row"], seen,
                                 {"Face Priority", "Other Row"}, None, {}, None)
    assert "runs on past the row" in why and row is None
    hand_tables(tmp_path / "data", ROW_NAMES={"Proxy Settings > Px Proxy Recording": "Proxy Settings > Proxy Recording"})
    seen = first_open.Seen(opened=first_open._with_parents(first_open.key(("Proxy Settings", "Px Proxy Recording"))))
    why, row = drive.lit_refused("Px Proxy Recording", ["Proxy Settings"], ["Proxy Settings", "Proxy Recording"], seen,
                                 {"Px Proxy Recording", "Proxy Recording"}, None, {}, None)
    assert (why, row) == ("", ("Proxy Settings", "Proxy Recording"))
    row_names.forget()
