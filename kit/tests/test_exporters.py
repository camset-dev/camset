"""K-10: what a new camera's mapping hands in is written by the kit: pass 1's map_all.json (kit/pass1_map.py), which
prove_run, axis_walk, schema_update and the proof viewer read, and the menu tree (kit/tools/menu_tree.py), the
mapper's own, on whose rows schema_update places each setting. On a made-up page scan and two made-up crawls in the test's own runs (CAMSET_RUNS, a camera
of no one's); nothing talks to a camera, and nothing is written into data/.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from camkit import ROOT, datafiles, definitions, paths  # noqa: E402

import menu_tree  # noqa: E402
import pass1_map  # noqa: E402
import proof_viewer  # noqa: E402


def write_lines(path: Path, items):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(x) + "\n" for x in items), encoding="utf-8")


def option(path, kind, index, label, frame):
    return {"path": path, "kind": kind, "index": index, "frame": frame, "ocr": label, "vlm": {"selected": label},
            "agreed": True}


@pytest.fixture
def camera(own_runs):
    """runs/TEST-CAM_fw9.99/ with a page scan's model (three pages, out of order) and two crawls."""
    root = own_runs / "TEST-CAM_fw9.99"
    scan = root / "kit2_page_scan"
    scan.mkdir(parents=True)
    (scan / "model.json").write_text(json.dumps([
        {"page": "2/3", "breadcrumb": "Shooting > Drive", "rows": [
            {"slot": 0, "label": "Drive Mode", "greyed": False, "never_open": None, "value": "OWNER VALUE"},
            {"slot": 1, "label": "Format", "greyed": False, "never_open": "action: format"},
            {"slot": 2, "label": "ISO Range Limit", "greyed": False, "never_open": None}]},
        {"page": "1/3", "breadcrumb": "Shooting > Image Quality", "rows": [
            {"slot": 0, "label": "Aspect Ratio", "greyed": False, "never_open": None},
            {"slot": 1, "label": "Long Exposure NR", "greyed": True, "never_open": None},
            {"slot": 2, "label": "Lens Compensation", "greyed": False, "never_open": None}]},
        {"page": "3/3", "breadcrumb": "Setup > Sound Options", "rows": [
            {"slot": 0, "label": "Audio signals", "greyed": False, "never_open": None},
            {"slot": 1, "label": "Display Quality", "greyed": False, "never_open": None}]},
    ]), encoding="utf-8")
    crawl = root / "kit2_crawl"
    write_lines(crawl / "rows.jsonl", [
        {"page": "1/3", "slot": 0, "label": "Aspect Ratio", "outcome": "walked", "kind": "list", "options": 3},
        {"page": "1/3", "slot": 1, "label": "Long Exposure NR", "outcome": "notice", "kind": "notice"},
        {"page": "1/3", "slot": 2, "label": "Lens Compensation", "outcome": "submenu crawled", "kind": "submenu",
         "submenu": [{"page": "s", "slot": 0, "label": "Shading Comp.", "outcome": "walked", "kind": "list"}]},
        {"page": "2/3", "slot": 0, "label": "Drive Mode", "outcome": "walked", "kind": "dialog"},
        {"page": "2/3", "slot": 1, "label": "Format", "outcome": "skipped: action: format", "kind": ""},
        {"page": "2/3", "slot": 2, "label": "ISO Range Limit", "outcome": "walked", "kind": "fields"},
    ])
    write_lines(crawl / "options.jsonl", [
        *(option(["Aspect Ratio"], "list", i, lab, f"0001{i}_down.png") for i, lab in enumerate(["3:2", "4:3", "16:9"])),
        *(option(["Lens Compensation", "Shading Comp."], "list", i, lab, f"0002{i}_down.png")
          for i, lab in enumerate(["Auto", "Low", "Off"])),
        *(option(["Drive Mode"], "dialog", i, lab, f"0003{i}_right.png") for i, lab in enumerate(["Single", "Cont."])),
        *(option(["ISO Range Limit"], "fields", [f, i], lab, f"0004{f}{i}_up.png")
          for f in (0, 1) for i, lab in enumerate(["ISO 100", "ISO 200", "ISO 400"])),
    ])
    play = root / "kit2_crawl_play"
    write_lines(play / "options.jsonl", [
        *(option(["Rotate Display"], "list", i, lab, f"0005{i}_down.png") for i, lab in enumerate(["Auto", "Off"])),
        option(["Aspect Ratio"], "list", 0, "a second reading", "00099_down.png"),
    ])
    return root


def test_pass1_map_writes_map_all_from_the_crawls(camera, capsys):
    target = camera / "kit2_pass1" / "map_all.json"
    pass1_map.main(["kit2_crawl", "kit2_crawl_play", "--dry-run"])
    assert not target.exists() and not (camera / "kit2_crawl" / "map.json").exists()          # --dry-run: nothing
    assert "--dry-run: nothing written" in capsys.readouterr().out
    got = pass1_map.main(["kit2_crawl", "kit2_crawl_play"])
    assert json.loads(target.read_text(encoding="utf-8")) == got
    rows = {tuple(r["path"]): r for r in got["rows"]}
    assert [o["label"] for o in rows[("Aspect Ratio",)]["options"]] == ["3:2", "4:3", "16:9"]     # the first's kept
    assert rows[("Aspect Ratio",)]["run"] == "kit2_crawl" and rows[("Rotate Display",)]["run"] == "kit2_crawl_play"
    assert "Aspect Ratio: in kit2_crawl and kit2_crawl_play; kit2_crawl's kept" in capsys.readouterr().out
    assert (camera / "kit2_crawl" / "map.json").exists() and (camera / "kit2_crawl_play" / "map.json").exists()
    pass1_map.main(["kit2_crawl", "kit2_crawl_play"])
    assert "is current" in capsys.readouterr().out
    # a map_all that differs (one crawl only now) is left as it is, unless --replace
    with pytest.raises(SystemExit, match="--replace"):
        pass1_map.main(["kit2_crawl"])
    assert "gone Rotate Display" in capsys.readouterr().out
    pass1_map.main(["kit2_crawl", "--replace"])
    assert {tuple(r["path"]) for r in json.loads(target.read_text(encoding="utf-8"))["rows"]} == set(rows) - {("Rotate Display",)}


def test_pass1_map_own_writes_the_crawls_map_and_leaves_map_all_alone(camera, capsys):
    """--own (kit/pass3_run.py's walk of one row in one state): the crawl's own map.json is written and returned, and
    kit2_pass1/map_all.json is neither written nor compared, so a small map that differs from it is no failure (before
    --own the walk's map exited 1 against map_all.json and pass 3 skipped every proof). Without --own, as before."""
    target = camera / "kit2_pass1" / "map_all.json"
    pass1_map.main(["kit2_crawl", "kit2_crawl_play"])
    whole = target.read_bytes()
    capsys.readouterr()
    got = pass1_map.main(["kit2_crawl_play", "--own"])                  # exits 0: no SystemExit
    assert json.loads((camera / "kit2_crawl_play" / "map.json").read_text(encoding="utf-8")) == got
    assert [r["path"] for r in got["rows"]] == [["Rotate Display"], ["Aspect Ratio"]] and "run" not in got["rows"][0]
    assert target.read_bytes() == whole
    assert "map_all.json" not in capsys.readouterr().out
    target.unlink()
    pass1_map.main(["kit2_crawl", "--own"])
    assert not target.exists()                                          # nor started where there is none
    pass1_map.main(["kit2_crawl", "kit2_crawl_play"])
    with pytest.raises(SystemExit, match="--replace"):                  # without it, the old rule stands
        pass1_map.main(["kit2_crawl_play"])


def test_a_label_fixed_by_hand_in_map_json_is_kept(camera):
    """The playbook: a label that came off a wrong frame is fixed by hand in map.json, with "by"; making the map
    again keeps it, and map_all carries it."""
    pass1_map.main(["kit2_crawl"])
    mp = camera / "kit2_crawl" / "map.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    row = next(r for r in m["rows"] if r["path"] == ["Drive Mode"])
    row["options"][1].update(label="Cont. Shooting", by="read off the frame by eye")
    mp.write_text(json.dumps(m), encoding="utf-8")
    got = pass1_map.main(["kit2_crawl", "--replace"])
    again = next(r for r in got["rows"] if r["path"] == ["Drive Mode"])["options"][1]
    assert (again["label"], again["source"], again["by"]) == ("Cont. Shooting", "by hand", "read off the frame by eye")


def test_the_viewer_finds_a_row_frames_in_its_own_crawl(camera, monkeypatch):
    pass1_map.main(["kit2_crawl", "kit2_crawl_play"])
    for name in ("00010_down.png", "00011_down.png", "00050_down.png"):
        crawl = "kit2_crawl_play" if name.startswith("0005") else "kit2_crawl"
        (camera / crawl / "shots").mkdir(parents=True, exist_ok=True)
        (camera / crawl / "shots" / name).write_bytes(b"png")
    monkeypatch.setattr(proof_viewer, "RUN_ROOT", camera)
    walks = proof_viewer.walk_frames(camera / "elsewhere")
    assert [Path(f).parent.parent.name for f, _ in walks[("aspectratio",)]] == ["kit2_crawl", "kit2_crawl"]
    assert [lab for _, lab in walks[("rotatedisplay",)]] == ["Auto"]


def test_menu_tree_from_the_scan_and_the_crawls(camera, tmp_path, capsys):
    pass1_map.main(["kit2_crawl"])
    out = tmp_path / "menu_tree.json"
    doc = menu_tree.main(["--crawl", "kit2_crawl", "--out", str(out), "--dry-run"])
    assert not out.exists() and "nothing written" in capsys.readouterr().out
    assert menu_tree.check(doc) == []                                   # the shape schemas/menu-tree.schema.json asks
    assert (doc["model"], doc["firmware"]) == ("TEST-CAM", "9.99")
    assert [t["tab"] for t in doc["tabs"]] == ["Shooting", "Setup"]
    shooting = doc["tabs"][0]["pages"]
    assert [(p["page"], p["group"]) for p in shooting] == [("1/3", "Image Quality"), ("2/3", "Drive")]
    rows = {r["label"]: r for p in shooting for r in p["rows"]}
    assert rows["Aspect Ratio"] == {"label": "Aspect Ratio", "state": "walked", "why": "", "kind": "list",
                                    "options": ["3:2", "4:3", "16:9"]}
    assert rows["Long Exposure NR"]["state"] == "greyed" and rows["Long Exposure NR"]["kind"] == "notice"
    lens = rows["Lens Compensation"]
    assert lens["state"] == "submenu" and lens["children"][0]["options"] == ["Auto", "Low", "Off"]
    assert rows["Drive Mode"]["options"] == ["Single", "Cont."]
    assert rows["Format"]["state"] == "never" and "format" in rows["Format"]["why"]
    assert rows["ISO Range Limit"]["fields"] == [{"count": 3, "first": "ISO 100", "last": "ISO 400"}] * 2
    setup = {r["label"]: r for r in doc["tabs"][1]["pages"][0]["rows"]}
    assert setup["Audio signals"]["state"] == "never"                  # not crawled: the never-open list names it
    assert setup["Display Quality"]["state"] == "seen"
    assert "OWNER VALUE" not in json.dumps(doc)                         # no value the camera held (decision 16)
    menu_tree.main(["--crawl", "kit2_crawl", "--out", str(out)])
    # written whole, the walk's states and reasons with it: the file is the mapper's own, private (decision 16)
    assert datafiles.load_menu_tree(out) == json.loads(out.read_text(encoding="utf-8")) == doc
    assert not datafiles.evidence_path(out).exists()
    with pytest.raises(SystemExit, match="--replace"):
        menu_tree.main(["--crawl", "kit2_crawl", "--out", str(out)])
    menu_tree.main(["--crawl", "kit2_crawl", "--out", str(out), "--replace"])


def test_a_modes_menu_goes_beside_the_stills_menu(camera, tmp_path, capsys):
    """--mode writes another shooting mode's menu into the tree's "modes" from that mode's own scan (a scan alone:
    each page's top rows, "seen") and crawls, leaving the Stills menu as it is; a mode there already, or the Stills
    menu, is replaced only with --replace, and replacing the Stills menu keeps the modes."""
    pass1_map.main(["kit2_crawl"])
    scan = camera / "kit2_page_scan_movie"
    scan.mkdir()
    (scan / "model.json").write_text(json.dumps([
        {"page": "1/2", "breadcrumb": "Shooting > Image Quality", "rows": [
            {"slot": 0, "label": "File Format", "greyed": False, "never_open": None, "value": "OWNER VALUE"},
            {"slot": 1, "label": "S&Q Settings", "greyed": False, "never_open": None}]},
        {"page": "2/2", "breadcrumb": "Shooting > TC/UB", "rows": [
            {"slot": 0, "label": "Time Code Format", "greyed": False, "never_open": None}]},
    ]), encoding="utf-8")
    write_lines(camera / "kit2_crawl_movie" / "rows.jsonl", [
        {"page": "1/2", "slot": 1, "label": "S&Q Settings", "outcome": "submenu crawled", "kind": "submenu",
         "submenu": [{"page": "s", "slot": 0, "label": "Frame Rate Settings", "outcome": "unknown screen", "kind": "unknown"}]}])
    out = tmp_path / "menu_tree.json"
    with pytest.raises(SystemExit, match="--scan"):
        menu_tree.main(["--mode", "Movie", "--out", str(out)])
    menu_tree.main(["--crawl", "kit2_crawl", "--out", str(out)])
    stills = datafiles.load_menu_tree(out)
    doc = menu_tree.main(["--mode", "Movie", "--scan", "kit2_page_scan_movie", "--crawl", "kit2_crawl_movie", "--out", str(out)])
    assert "(Movie mode)" in capsys.readouterr().out and menu_tree.check(doc) == []
    got = datafiles.load_menu_tree(out)
    assert got["tabs"] == stills["tabs"] and [m["mode"] for m in got["modes"]] == ["Movie"]
    movie = {r["label"]: r for p in got["modes"][0]["tabs"][0]["pages"] for r in p["rows"]}
    assert movie["File Format"]["state"] == "seen" and movie["Time Code Format"]["state"] == "seen"
    assert movie["S&Q Settings"]["children"][0]["label"] == "Frame Rate Settings"
    assert "OWNER VALUE" not in out.read_text(encoding="utf-8")
    with pytest.raises(SystemExit, match="--replace"):
        menu_tree.main(["--mode", "Movie", "--scan", "kit2_page_scan_movie", "--out", str(out)])
    menu_tree.main(["--mode", "S&Q", "--scan", "kit2_page_scan_movie", "--out", str(out)])
    menu_tree.main(["--mode", "Movie", "--scan", "kit2_page_scan_movie", "--out", str(out), "--replace"])
    got = datafiles.load_menu_tree(out)
    assert [m["mode"] for m in got["modes"]] == ["Movie", "S&Q"]                    # replaced where it was
    assert "children" not in {r["label"]: r for p in got["modes"][0]["tabs"][0]["pages"] for r in p["rows"]}["S&Q Settings"]
    menu_tree.main(["--crawl", "kit2_crawl", "--out", str(out), "--replace"])
    assert [m["mode"] for m in json.loads(out.read_text(encoding="utf-8"))["modes"]] == ["Movie", "S&Q"]


def test_menu_tree_goes_to_the_private_evidence_folder_by_default(camera, tmp_path, monkeypatch):
    """Without --out the tree is private/evidence/<model>_fw<fw>/menu_tree_<model>_fw<fw>.json of the camera the kit
    works on (definitions.menu_tree_file, here a folder of the test's own), never a file in data/; one there already is
    replaced only with --replace."""
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path / "evidence")
    key = paths.run_root().name
    assert key == "TEST-CAM_fw9.99"
    menu_tree.main(["--crawl", "kit2_crawl"])
    want = tmp_path / "evidence" / key / f"menu_tree_{key}.json"
    assert definitions.menu_tree_file(key) == datafiles.menu_tree_file(key) == want and want.exists()
    assert not (ROOT / "data" / key).exists()
    with pytest.raises(SystemExit, match="--replace"):
        menu_tree.main(["--crawl", "kit2_crawl"])
    with pytest.raises(datafiles.NoMenuTree, match="private"):
        datafiles.load_menu_tree("ILCE-0X0_fw1.00")


A1_TREE = definitions.menu_tree_file(paths.A1II)
needs_tree = pytest.mark.skipif(not A1_TREE.exists(), reason="the menu tree is the mapper's own (private/evidence/, not here)")


@needs_tree
def test_the_a1_ii_tree_still_matches_the_schema():
    assert menu_tree.check(datafiles.load_menu_tree(paths.A1II)) == []


def test_no_data_folder_holds_a_menu_tree():
    """A menu tree is private whole (decision 16): what the walk found greyed, unread or listed from the held option
    is the state the camera stood in, so no camera's data folder carries one."""
    assert sorted((ROOT / "data").glob("*/menu_tree_*.json")) == []


def test_a_carousels_options_are_named_by_their_own_names_never_by_a_sub_choice():
    """menu_tree.carousel_names: a carousel option the walk read with the sub-choice it was left on (the camera's own
    setting, decision 16) is named by its own name: "Name: choice" when no other option has that name, "Name N" when
    no other option has that name numbered; options that share a name are options of their own and stay whole. Made-up
    carousels."""
    got = menu_tree.carousel_names(["Wide", "Area: Small", "Expand", "Slot 2", "Follow: Box B", "Plain"])
    assert got == ["Wide", "Area", "Expand", "Slot", "Follow", "Plain"]
    assert menu_tree.carousel_names(["Lamp: Warm", "Lamp: Cool", "Preset 1", "Preset 2", "ISO 100"]) == \
        ["Lamp: Warm", "Lamp: Cool", "Preset 1", "Preset 2", "ISO 100"]
    assert menu_tree.carousel_names(["70", "100+", "Mode: Auto"]) == ["70", "100+", "Mode"]


def test_a_tree_from_a_walk_names_no_sub_choice(camera, tmp_path):
    """A carousel row of a crawl's map whose option the walk read on its sub-choice ("Cont.: Mid", made up) is written
    by its own name ("Cont."); held_choices finds what a tree would still carry, and --carousel-names names an
    existing tree's options by the rule, the rest as it was."""
    pass1_map.main(["kit2_crawl"])
    out = tmp_path / "menu_tree.json"
    doc = menu_tree.main(["--crawl", "kit2_crawl", "--out", str(out)])
    assert menu_tree.held_choices(doc) == []
    doc["tabs"][0]["pages"][1]["rows"][0]["options"] = ["Single", "Cont.: Mid"]       # as a hand-made tree held it
    datafiles.write_menu_tree(out, doc)
    assert menu_tree.held_choices(doc) == [("Stills", "Drive Mode", "Cont.: Mid")]
    menu_tree.main(["--carousel-names", "--out", str(out)])
    again = datafiles.load_menu_tree(out)
    assert again["tabs"][0]["pages"][1]["rows"][0]["options"] == ["Single", "Cont."]
    assert menu_tree.held_choices(again) == [] and again["tabs"][1] == doc["tabs"][1]


@needs_tree
def test_the_a1_ii_tree_carries_no_sub_choice_the_camera_was_left_on():
    """The mapper's tree names each carousel option by its own name (carousel_names), as the definition's places are
    taken from it: the a1 II's carried Focus Area's Spot by its size, Custom by its slot and Tracking by the area the
    camera held, and the Drive Mode, Metering Mode, D-Range Optimizer and Pixel Shift options by theirs, once."""
    assert menu_tree.held_choices(datafiles.load_menu_tree(paths.A1II)) == []
