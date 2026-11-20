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
         "MR Camera Set. Memory": "Camera Set. Memory",
         "S&Q Settings > S&Q Record Setting": "S&Q Settings > Record Setting",
         "Rec. Media Settings > Recording Media (Movie)": "Rec. Media Settings > Recording Media#1"}


def hand_tables(data: Path, **tables) -> Path:
    p = datafiles.hand_tables_file(TEST_CAMERA)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"$schema": "../../schemas/hand-tables.schema.json", "camera": TEST_CAMERA, **tables}),
                 encoding="utf-8")
    return p


@pytest.fixture
def named(tmp_path, monkeypatch):
    """The made-up camera's hand tables with NAMES as its ROW_NAMES, in the test's own data folder."""
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    return hand_tables(tmp_path / "data", ROW_NAMES=NAMES)


@pytest.fixture
def unnamed(tmp_path, monkeypatch):
    """The made-up camera with hand tables holding no ROW_NAMES."""
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    return hand_tables(tmp_path / "data")


# ---------------------------------------------------------------- the table

def test_an_older_name_is_the_cameras_and_so_is_every_row_under_it(named):
    assert row_names.renamed(["Proxy Settings", "Px Proxy Recording"]) == ("Proxy Settings", "Proxy Recording")
    assert row_names.renamed(("MR Camera Set. Memory", "Slot 1")) == ("Camera Set. Memory", "Slot 1")
    assert row_names.renamed(["mr camera set.  memory"]) == ("Camera Set. Memory",)          # compared plain
    assert row_names.renamed(["Proxy Settings"]) == ("Proxy Settings",)                      # none above the row
    assert row_names.renamed(["Proxy Settings", "Proxy File Format"]) == ("Proxy Settings", "Proxy File Format")
    assert row_names.renamed_name("S&Q Settings > S&Q Record Setting [Movie mode, 120p]") == \
        "S&Q Settings > Record Setting [Movie mode, 120p]"
    assert row_names.renamed_name("MR Camera Set. Memory / Slot 2") == "Camera Set. Memory / Slot 2"
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
    assert row_names.table() == {}
    assert row_names.renamed(["Proxy Settings", "Px Proxy Recording"]) == ("Proxy Settings", "Px Proxy Recording")
    assert row_names.renamed_name("MR Camera Set. Memory [x]") == "MR Camera Set. Memory [x]"
    assert row_names.as_in(["S&Q Settings > Record Setting"], ["S&Q Settings > S&Q Record Setting"]) == \
        ["S&Q Settings > Record Setting"]


@pytest.mark.parametrize("entries, words", [
    ({"A > B": "A > C", "A > C": "A > D"}, "also names as an older name"),
    ({"A > B": "a >  b"}, "a row's path"),
    ({"A > B": "A > b"}, "renames the row to itself"),
    ({"A >  > B": "A > C"}, "a row's path"),
    ({"A > B": 3}, "a row's path"),
    (["A > B"], "no object"),
])
def test_a_table_the_kit_cannot_use_is_refused(entries, words):
    with pytest.raises(ValueError, match=words):
        row_names.read(entries)


def test_the_hand_tables_reader_and_schema_take_row_names_and_refuse_a_chain(tmp_path, monkeypatch):
    from writer import hand_evidence, hand_facts, hand_tables as H
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    p = hand_tables(tmp_path / "data", ROW_NAMES=NAMES)
    tables = H.load(TEST_CAMERA, evidence=False)
    assert tables.ROW_NAMES == NAMES
    assert hand_evidence.schema_problems(json.loads(p.read_text(encoding="utf-8")), "hand-tables") == []
    assert not [x for x in hand_facts.refusals(tables) if "ROW_NAMES" in x]            # the plain pass takes it
    hand_tables(tmp_path / "data", ROW_NAMES={"A > B": "A > C", "A > C": "A > D"})
    with pytest.raises(H.Refused, match="ROW_NAMES"):
        H.load(TEST_CAMERA, evidence=False)


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
    assert menu_tree.camed({"label": "MR Camera Set. Memory", "submenu": [{"label": "x"}]})["label"] == "Camera Set. Memory"


def test_placement_reads_a_path_and_a_tree_written_with_older_names_as_the_cameras(named):
    from camkit import placement
    assert placement.split("Proxy Settings > Px Proxy Recording [Movie mode]") == ["Proxy Settings", "Proxy Recording"]
    assert placement.steps("MR Camera Set. Memory / Slot 1")[0] == ("", "Camera Set. Memory")
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
