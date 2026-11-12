"""The proof viewer (kit/tools/proof_viewer.py), offline: --pack, the frames' copies beside the page; no page in a
clone with no runs; --open; the camera's own runs only (runs/<model>_fw<fw>/, camkit.paths); the help text with the
guide frames it was read from, My Menu and the Main page; a proof's pictures in reading order; the other shooting
modes' rows, from made-up runs, made-up menus and made-up text.

Run: .venv/bin/python -m pytest kit/tests/test_proof_viewer.py -q
A tmp_path runs/ILCE-1M2_fw4.00/ with two tiny PNGs stands in for the real runs, and a tmp clone holds only the
repository's a1 II definition and data/; nothing talks to a camera.
"""
import collections
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from camkit import datafiles, definitions, paths, placement

import proof_viewer as pv

A1 = "ILCE-1M2_fw4.00"          # the definition's camera (editor/definitions/ILCE-1M2_fw4.00.json)
# the placement rests on the proofs' rows (proved.menu), evidence in the mapper's private/evidence/ (camkit.definitions)
# and the menu tree they hang on, the mapper's own, private whole (camkit.datafiles)
needs_evidence = pytest.mark.skipif(not definitions.evidence_path(definitions.path(paths.A1II)).exists()
                                    or not datafiles.menu_tree_file(paths.A1II).exists(),
                                    reason="reads the proofs' rows and the menu tree, in private/evidence/ (not here)")


SAMPLE = definitions.path(A1).with_suffix(".DAT")          # its sample, beside it
A = "../kit2_a/shots/0001.png"
B = "../kit2_b/upright/0002.png"


@pytest.fixture
def runs(tmp_path):
    """A camera's run root: runs/ILCE-1M2_fw4.00/ with two runs' frames and its _viewer/."""
    runs = tmp_path / "runs" / A1
    for rel, color in (("kit2_a/shots/0001.png", (255, 0, 0)), ("kit2_b/upright/0002.png", (0, 0, 255))):
        p = runs / rel
        p.parent.mkdir(parents=True)
        Image.new("RGB", (8, 6), color).save(p)
    (runs / "_viewer").mkdir()
    return runs


def page_data():
    """Shaped like main()'s data: two records sharing one evidence list, a record with none, and a menu row whose
    child row has a pass 1 walk."""
    shared = [[A, "option lit"]]
    return {"records": {"global:0x0001": {"ev": [{"frames": shared}]},
                        "global:0x0002": {"ev": [{"frames": shared}, {"frames": [[B, "after OK"]]}]},
                        "global:0x0003": {"ev": []}},
            "menu": [{"tab": "Shooting", "others": [], "groups": [{"name": "G", "rows": [
                {"l": "Row", "walk": [], "kids": [{"l": "Sub", "walk": [[B, "On"]], "kids": []}]}]}]}]}


def links(data) -> list:
    return [shot[0] for shots in pv.frame_lists(data) for shot in shots]


PAGE = Path(pv.__file__).with_name("proof_viewer.html").read_text(encoding="utf-8")          # the template


def page_function(name: str) -> str:
    """A top-level function of the page's script, as the template holds it, for node to run on its own."""
    a = PAGE.index(f"function {name}(")
    return PAGE[a:PAGE.index("\n}\n", a) + 3]


def page_line(name: str) -> str:
    """A top-level `const NAME = ...` line of the page's script."""
    a = PAGE.index(f"const {name} = ")
    return PAGE[a:PAGE.index("\n", a) + 1]


# ---------------------------------------------------------------- the links

def test_linked_frames_reads_the_records_and_the_menu_walks():
    assert pv.linked_frames(page_data()) == {A, B}


def test_relink_mends_a_shared_list_once_and_keeps_the_captions():
    data = page_data()
    assert pv.relink(data, {A: "frames/kit2_a/shots/0001.jpg"}) == 1
    assert links(data) == ["frames/kit2_a/shots/0001.jpg"] * 2 + [B, B]
    assert data["records"]["global:0x0002"]["ev"][0]["frames"] == [["frames/kit2_a/shots/0001.jpg", "option lit"]]
    assert pv.relink(data, {}) == 0


def test_pack_plan_names_jpeg_copies_by_run_and_path(runs):
    viewer = runs / "_viewer"
    plan = pv.pack_plan({A, B}, viewer, runs)
    assert plan == {A: (runs / "kit2_a/shots/0001.png", "frames/kit2_a/shots/0001.jpg"),
                    B: (runs / "kit2_b/upright/0002.png", "frames/kit2_b/upright/0002.jpg")}
    assert pv.pack_plan({A}, viewer, runs, png=True)[A][1] == "frames/kit2_a/shots/0001.png"
    # a page elsewhere links by absolute path; the copy is named the same
    absolute = str(runs / "kit2_a/shots/0001.png")
    assert pv.pack_plan({absolute}, viewer, runs)[absolute][1] == "frames/kit2_a/shots/0001.jpg"
    # a frame already in JPEG keeps its name
    jpg = "../kit2_a/shots/0003.JPG"
    assert pv.pack_plan({jpg}, viewer, runs)[jpg][1] == "frames/kit2_a/shots/0003.JPG"


def test_frames_link_relative_to_the_page_through_a_linked_runs_folder(tmp_path, monkeypatch):
    """runs/ may be a link to another disk: the page's folder is resolved, the run root is not, and the two used to
    compare unequal, so every frame of the camera's own page was linked by absolute path. Links are written with
    forward slashes, as a page's are, on every OS."""
    real = tmp_path / "disk" / A1
    (real / "kit2_a" / "shots").mkdir(parents=True)
    Image.new("RGB", (8, 6)).save(real / "kit2_a" / "shots" / "0001.png")
    (real / "_viewer").mkdir()
    try:
        (tmp_path / "runs").symlink_to(tmp_path / "disk", target_is_directory=True)
    except OSError:
        pytest.skip("no symbolic links here")
    root = tmp_path / "runs" / A1
    monkeypatch.setattr(pv, "RUN_ROOT", root)
    assert pv.frame(root / "kit2_a", "0001.png", (root / "_viewer").resolve()) == A
    assert pv.frame(root / "kit2_a", "0001.png", tmp_path / "elsewhere") == (root / "kit2_a" / "shots" / "0001.png").as_posix()
    assert pv.frame(root / "kit2_a", "gone.png", root / "_viewer") is None


def test_a_torn_line_in_a_runs_log_leaves_the_rest_of_the_page(runs, monkeypatch, capsys):
    """A run stopped mid-write cuts a line of its log short, and a run resumed after it appends past it: the page reads
    every whole record around that line (it used to stop the whole build), and a damaged line before the end is
    counted and said (one left out without a word lowered the evidence unnoticed); a torn last line alone is the stop
    the log ends with, and says nothing."""
    monkeypatch.setattr(pv, "RUN_ROOT", runs)
    monkeypatch.setattr(pv, "DAMAGED", {})
    good = {"path": ["Row"], "label": "On", "row_frame": "0001.png", "changes": [{"key": "global:0x0001", "before": 0, "after": 1}]}
    log = runs / "kit2_a" / "proofs.jsonl"
    log.write_text(json.dumps(good) + "\n" + '{"path": ["Row"], "lab' + json.dumps(good) + "\n"
                   + json.dumps(dict(good, label="Off")) + "\n" + '{"path": ', encoding="utf-8")
    ev = pv.collect([{"key": "global:0x0001"}], runs / "_viewer")
    assert [(e["label"], e["frames"]) for e in ev["global:0x0001"]] == [("On", [[A, "after OK"]]), ("Off", [[A, "after OK"]])]
    err = capsys.readouterr().err
    assert "line 2 is not JSON" in err and "1 damaged line(s)" in err and "and its torn last line" in err
    assert list(pv.DAMAGED.values()) == [1]          # the middle one; the torn end is the stop, said apart
    pv.DAMAGED.clear()
    log.write_text(json.dumps(good) + "\n" + '{"path": ', encoding="utf-8")
    assert len(pv.collect([{"key": "global:0x0001"}], runs / "_viewer")["global:0x0001"]) == 1
    assert capsys.readouterr().err == "" and pv.DAMAGED == {}


def test_no_text_in_the_data_can_end_the_pages_script():
    """A note or a guide read off the screen with "<!--" and "<script" in it put the HTML parser in the script's
    double-escaped state, where the page's own </script> no longer ended the script; </ alone was escaped. Every <, >
    and & is written as a JSON escape, the same text to the script."""
    data = {"records": {"k": {"note": "<!--<script>x</script> & <b>", "n": "a > b"}}}
    text = pv.page_json(data)
    assert not set("<>&") & set(text)
    assert json.loads(text) == data


# ---------------------------------------------------------------- copy, convert, skip, remove

def test_pack_one_converts_then_skips_until_the_source_is_newer(runs, tmp_path):
    src, dst = runs / "kit2_a/shots/0001.png", tmp_path / "frames/kit2_a/shots/0001.jpg"
    assert pv.pack_one(src, dst) == "converted"
    with Image.open(dst) as im:
        assert im.format == "JPEG" and im.size == (8, 6) and im.mode == "RGB"
    assert not list(dst.parent.glob("*.part"))
    assert pv.pack_one(src, dst) == "skipped"
    later = dst.stat().st_mtime + 10
    os.utime(src, (later, later))
    assert pv.pack_one(src, dst) == "converted"


def test_pack_one_copies_a_png_as_it_is(runs, tmp_path):
    src, dst = runs / "kit2_b/upright/0002.png", tmp_path / "frames/kit2_b/upright/0002.png"
    assert pv.pack_one(src, dst) == "copied"
    assert dst.read_bytes() == src.read_bytes()
    assert pv.pack_one(src, dst) == "skipped"


def test_prune_removes_only_unlinked_files_under_frames(tmp_path):
    frames = tmp_path / "_viewer" / "frames"
    keep = frames / "kit2_a/shots/0001.jpg"
    stale = [frames / "kit2_a/shots/0002.jpg", frames / "kit2_gone/shots/0001.jpg", frames / "kit2_a/shots/0003.jpg.part"]
    beside = tmp_path / "_viewer" / "index.html"
    for p in [keep, beside] + stale:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
    assert pv.prune(frames, [keep]) == 3
    assert keep.exists() and beside.exists()
    assert not any(p.exists() for p in stale)
    assert not (frames / "kit2_gone").exists()          # the folder it left empty
    assert pv.prune(frames, [keep]) == 0
    assert pv.prune(tmp_path / "_viewer" / "nothing" / pv.FRAMES, []) == 0          # no frames/ yet
    with pytest.raises(ValueError):
        pv.prune(tmp_path / "_viewer", [])          # never a folder other than frames/


def test_pack_frames_counts_and_keeps_going_past_a_bad_frame(runs, tmp_path):
    bad = runs / "kit2_a/shots/bad.png"
    bad.write_bytes(b"not a picture")
    jobs = {runs / "kit2_a/shots/0001.png": tmp_path / "frames/a.jpg", runs / "kit2_b/upright/0002.png": tmp_path / "frames/b.png",
            bad: tmp_path / "frames/bad.jpg"}
    done, failed = pv.pack_frames(jobs, workers=2, say=lambda _: None)
    assert done == {"converted": 1, "copied": 1}
    assert list(failed) == [bad]
    assert not (tmp_path / "frames/bad.jpg").exists() and not (tmp_path / "frames/bad.jpg.part").exists()


# ---------------------------------------------------------------- the whole pack

def test_pack_links_the_copies_and_a_second_pack_skips_them(runs):
    viewer, said = runs / "_viewer", []
    data = page_data()
    line = pv.pack(data, viewer, runs, workers=2, say=said.append)
    assert "packed 2 frames: 2 converted to JPEG, 0 copied, 0 skipped" in line
    assert "0 removed" in line and line.endswith("is now self-contained: copy or zip the folder")
    assert links(data) == ["frames/kit2_a/shots/0001.jpg"] * 2 + ["frames/kit2_b/upright/0002.jpg"] * 2
    assert all((viewer / p).is_file() for p in links(data))
    assert (runs / "kit2_a/shots/0001.png").exists()          # the sources stay where they are

    again = page_data()
    assert "2 skipped (already there)" in pv.pack(again, viewer, runs, workers=2, say=said.append)
    assert links(again) == links(data)


def test_pack_png_replaces_the_jpegs_and_drops_what_is_no_longer_linked(runs):
    viewer = runs / "_viewer"
    pv.pack(page_data(), viewer, runs, workers=2, say=lambda _: None)
    data = page_data()
    line = pv.pack(data, viewer, runs, png=True, workers=2, say=lambda _: None)
    assert "0 converted to JPEG, 2 copied" in line and "2 removed (no longer linked)" in line
    assert sorted(p.relative_to(viewer).as_posix() for p in viewer.rglob("*.*")) == [
        "frames/kit2_a/shots/0001.png", "frames/kit2_b/upright/0002.png"]
    # a record gone from the page: its frame goes from frames/
    data = page_data()
    data["records"]["global:0x0002"]["ev"] = []
    data["records"]["global:0x0001"]["ev"] = []
    line = pv.pack(data, viewer, runs, png=True, workers=2, say=lambda _: None)
    assert "packed 1 frames" in line and "1 removed" in line
    assert not (viewer / "frames/kit2_a").exists()


def test_pack_leaves_a_frame_it_could_not_copy_linked_into_runs(runs):
    viewer = runs / "_viewer"
    (runs / "kit2_a/shots/0001.png").write_bytes(b"not a picture")
    data, said = page_data(), []
    line = pv.pack(data, viewer, runs, workers=2, say=said.append)
    assert "1 could not be packed" in line and "not self-contained" in line
    assert any("could not pack" in s for s in said)
    assert links(data) == [A, A, "frames/kit2_b/upright/0002.jpg", "frames/kit2_b/upright/0002.jpg"]


# ---------------------------------------------------------------- help text, My Menu and the Main page from the runs

def png(p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 6), (90, 90, 90)).save(p)


def lines(p: Path, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def help_run(root: Path, logs: dict, reads=()):
    """A camera's kit2_help with made-up guides: {log name: [lines]}, every frame they name kept, and help_reads'
    verdicts."""
    run = root / pv.HELP_RUN
    for name, rows in logs.items():
        lines(run / name, rows)
        for r in rows:
            for f in r.get("frames") or []:
                png(run / "shots" / f)
    lines(run / "help_reads.jsonl", list(reads))
    return run


GUIDES = {
    "help.jsonl": [{"context": "Stills mode", "breadcrumb": "Tab > Group", "label": "Row One", "title": "Row One",
                    "text": "row one helpz", "frames": ["00001.png"]}],
    "option_help.jsonl": [{"context": "Movie mode", "path": ["Row One"], "index": 0, "label": "On", "title": "On",
                           "text": "Turns it on. This function is currently disabled.", "frames": ["00002.png"]},
                          {"context": "Stills mode", "path": ["Row Two"], "index": -1, "label": None, "title": "Row Two",
                           "text": "Shared words.", "frames": ["00004.png"]},
                          {"context": "Stills mode", "path": ["Row One"], "index": 1, "label": "Off", "title": "Off",
                           "text": "Shared words.", "frames": ["gone.png"]}],
    "field_help.jsonl": [{"context": "Stills mode", "path": ["Row One"], "field": 0, "label": "Minimum", "title": "Minimum",
                          "text": "The least one.", "frames": ["00003.png"]}],
}
READS = [{"frame": "00001.png", "frames": ["00001.png"], "ocr": "Row one helpz.", "vlm": "Row one helps.", "text": "Row one helps.",
          "how": "two vision readers"},
         {"frame": "00002.png", "frames": ["00002.png"], "ocr": "Turns it on.", "vlm": "Turns  it on", "text": "Turns it on.",
          "how": "agreed"}]


@pytest.fixture
def camera_root(tmp_path, monkeypatch):
    root = tmp_path / "runs" / A1
    (root / "_viewer").mkdir(parents=True)
    monkeypatch.setattr(pv, "RUN_ROOT", root)
    return root


def test_guide_reads_take_the_settled_words_and_keep_both_readings_where_they_differ(camera_root):
    """A guide's text is the one help_reads settled on (else the OCR's), a greyed row's closing line cut off, as
    attach_help takes it; both readings come along only where their words differ, and a frame not kept is left out."""
    help_run(camera_root, GUIDES, READS)
    (camera_root / pv.HELP_RUN / "shots" / "gone.png").unlink()
    gs = pv.guide_reads(camera_root / "_viewer")
    assert [g["text"] for g in gs] == ["Row one helps.", "Turns it on.", "Shared words.", "Shared words.", "The least one."]
    row, opt, two, off, field = gs
    assert (row["how"], row["ocr"], row["vlm"]) == ("two vision readers", "Row one helpz.", "Row one helps.")
    assert opt["how"] == "agreed" and "ocr" not in opt and "vlm" not in opt          # the same words, other spacing
    assert two["how"] == "" and "ocr" not in two                                      # no second reader saw it
    assert row["frames"] == [["../kit2_help/shots/00001.png", "the camera's guide · Stills mode · Tab > Group > Row One"]]
    assert opt["where"] == "Row One > On" and opt["ctx"] == "Movie mode" and field["where"] == "Row One > Minimum"
    assert off["frames"] == []
    # no runs, no guides
    pv.RUN_ROOT = None
    assert pv.guide_reads(camera_root / "_viewer") == []


def test_a_text_finds_its_guides_and_the_settings_own_row_first(camera_root):
    help_run(camera_root, GUIDES, READS)
    gs = pv.guide_reads(camera_root / "_viewer")
    assert pv.text_guides("Row one helps.", gs) == [0]
    # a row's guide with its number field's own after it, as attach_help joins them
    assert pv.text_guides("Row one helps. Minimum: The least one.", gs) == [0, 4]
    assert pv.text_guides("Row one helps. Maximum: Not read.", gs) == [] and pv.text_guides("", gs) == []
    # the same words on two rows: the setting's own row (its proof's menu path), the row's guide for its help and the
    # option's for an option's; on no row of its own, every guide with those words
    shared = pv.text_guides("Shared words.", gs)
    assert shared == [2, 3]
    assert pv.on_row(shared, {"proved": {"menu": ["Row Two"]}}, gs) == [2]
    assert pv.on_row(shared, {"proved": {"menu": ["Row One"]}}, gs, "Off") == [3]
    assert pv.on_row(shared, {"proved": {"menu": ["Row One"]}}, gs) == [3]          # no row guide there: the option's
    assert pv.on_row(shared, {"proved": {"menu": ["Elsewhere"]}}, gs) == [2]       # the row guide among all
    assert pv.on_row(shared, {}, gs, "Off") == [3]


def test_a_row_takes_its_own_guide_in_the_menus_mode_first(camera_root):
    logs = {"help.jsonl": [{"context": "Movie mode", "breadcrumb": "Tab > Group", "label": "Do It", "text": "Movie words.",
                            "frames": ["m.png"]},
                           {"context": "Stills mode", "breadcrumb": "Tab > Group", "label": "Do It", "text": "Stills words.",
                            "frames": ["s.png"]},
                           {"context": "Movie mode", "breadcrumb": "Tab > Group", "label": "Only Movie", "text": "Only.",
                            "frames": ["o.png"]}],
            "option_help.jsonl": [{"context": "Stills mode", "path": ["Do It"], "index": 0, "label": "Yes", "text": "An option.",
                                   "frames": ["y.png"]}]}
    help_run(camera_root, logs)
    gs = pv.guide_reads(camera_root / "_viewer")
    rows = pv.row_guides(gs)
    assert [gs[i]["text"] for i in pv.row_help(["Do It"], rows)] == ["Stills words."]
    assert [gs[i]["text"] for i in pv.row_help(["Only  Movie"], rows)] == ["Only."]          # keyed as attach_help keys rows
    assert pv.row_help(["Yes"], rows) == [] and pv.row_help(["Nowhere"], rows) == []         # an option's guide is not a row's


def scan_line(frame, kind, row, page=None):
    return {"frame": frame, "kind": kind, "row": row, "page": page or frame, "signature": "s" + frame}


def test_main_pages_take_page_one_of_each_modes_page_scan(camera_root):
    """Each mode's Main page: the tile frames that follow a menu page in the scan's lap (a second Main page follows
    the first), the mode by the run's name, a page scan naming none the first mode's, the plainest name first."""
    first = scan_line("01.png", "menu", 3, "A")
    stills = [first, scan_line("02.png", "tiles", 0), scan_line("03.png", "tiles", 1), scan_line("04.png", "tiles", 0),
              scan_line("05.png", "menu", 0, "B"), dict(first)]
    movie = [scan_line("11.png", "tiles", 0, "M2"), scan_line("12.png", "tiles", 1), scan_line("13.png", "menu", 2, "X"),
             scan_line("14.png", "tiles", 0), scan_line("15.png", "tiles", 1), scan_line("16.png", "tiles", 2),
             scan_line("11.png", "tiles", 0, "M2")]
    partial = [scan_line("21.png", "tiles", 0), scan_line("22.png", "tiles", 1)]          # no lap: what came before is unknown
    for run, recs in (("kit2_page_scan", stills), ("kit2_page_scan_movie", movie), ("kit2_page_scan_movie_osd", stills),
                      ("kit2_page_scan_sq", partial)):
        lines(camera_root / run / "scan.jsonl", recs)
        for r in recs:
            png(camera_root / run / "shots" / r["frame"])
    got = pv.main_pages(camera_root / "_viewer", ["Stills", "Movie", "S&Q"])
    assert sorted(got) == ["Movie", "Stills"]
    assert got["Stills"]["run"] == "kit2_page_scan"
    assert [f for f, _ in got["Stills"]["frames"]] == ["../kit2_page_scan/shots/02.png", "../kit2_page_scan/shots/03.png"]
    assert got["Movie"]["run"] == "kit2_page_scan_movie"          # before kit2_page_scan_movie_osd
    assert [Path(f).name for f, _ in got["Movie"]["frames"]] == ["14.png", "15.png", "16.png"]
    assert got["Movie"]["frames"][0][1] == "Movie: the camera's Main page (kit2_page_scan_movie), row 1 of tiles lit"
    pv.RUN_ROOT = None
    assert pv.main_pages(camera_root / "_viewer", ["Stills"]) == {}


def test_my_menu_names_codes_and_the_pages_read_back(camera_root):
    doc = {"camera": {"my_menu": {"records": [0x0c8a, 0x0c91], "empty": 2, "max_items": 4, "packed": True},
                      "text": {"my_menu_name": "Fav"}},
           "settings": [{"key": "global:0x0c8a[0]", "values": [[2, "(empty)"], [9, "Thing A"]], "proved": {"run": "kit2_mm"}},
                        {"key": "global:0x0c91[1]", "values": [[9, "Thing A"], [10, "Thing B"]]},
                        {"key": "global:0x0001", "area": "global", "order": 5, "menu_code": 9},
                        {"key": "set:0x0001", "area": "set", "order": 1, "menu_code": 9},
                        {"key": "global:0x0002", "menu_code": 10}]}
    lines(camera_root / "kit2_mm" / "scan.jsonl", [])
    (camera_root / "kit2_mm" / "mymenu_readback.json").write_text(json.dumps(
        {"2": {"frame": "p2.png", "in_order": True, "slots": [[10, "Thing B"]]},
         "1": {"frame": "p1.png", "in_order": True, "slots": [[9, "Thing A"]]}}), encoding="utf-8")
    png(camera_root / "kit2_mm" / "shots" / "p1.png")
    mm = pv.my_menu(doc, camera_root / "_viewer")
    assert mm["title"] == "Fav" and mm["records"] == [0x0c8a, 0x0c91] and mm["empty"] == 2
    assert mm["names"] == [[2, "(empty)"], [9, "Thing A"], [10, "Thing B"]]
    assert mm["opens"] == {"9": ["global:0x0001", "set:0x0001"], "10": ["global:0x0002"]}          # live settings first
    assert [(p["page"], p["frames"]) for p in mm["read"]] == [(1, [["../kit2_mm/shots/p1.png", "kit2_mm · page 1 read back on the camera"]]),
                                                             (2, [])]          # a frame not kept is left out
    pv.RUN_ROOT = None
    assert pv.my_menu(doc, camera_root / "_viewer")["read"] == []
    assert pv.my_menu({"camera": {}, "settings": []}, camera_root) is None


def test_linked_frames_read_the_guides_my_menu_and_the_main_page():
    data = page_data()
    data.update(guides=[{"frames": [["g.png", "guide"]]}], my_menu={"read": [{"frames": [["m.png", "page"]]}]},
                main={"modes": [{"frames": [["t.png", "tiles"]]}, {"frames": []}]})
    assert pv.linked_frames(data) == {A, B, "g.png", "m.png", "t.png"}
    assert pv.relink(data, {"g.png": "frames/g.jpg"}) == 1 and data["guides"][0]["frames"] == [["frames/g.jpg", "guide"]]


# ---------------------------------------------------------------- the other shooting modes' rows

def mrow(label, *kids):
    return {"label": label, "state": "walked", "options": [], "children": list(kids)}


def mpage(n, group, *rows):
    return {"page": n, "group": group, "rows": list(rows)}


MODE_TREE = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Shooting", "pages": [
    mpage("1/2", "G1", mrow("A"), mrow("B")), mpage("2/2", "G2", mrow("C"))]}],
    "modes": [{"mode": "Movie", "tabs": [{"tab": "Shooting", "pages": [
        mpage("1/3", "G1", mrow("A"), mrow("X", mrow("X1"))), mpage("2/3", "Audio", mrow("Z")), mpage("3/3", "G2", mrow("C"))]}]},
        {"mode": "S&Q", "tabs": [{"tab": "Shooting", "pages": [
            mpage("1/2", "G1", mrow("A"), mrow("X"), mrow("Q")), mpage("2/2", "G2", mrow("C"))]}]}]}


def mode_doc():
    def setting(key, name, group, *menus):
        return {"key": key, "area": "global", "name": name, "tab": "Shooting", "group": group, "order": 1, "values": [],
                **({"proved": {"run": "kit2_pass2", "menu": list(menus)}} if menus else {})}
    return {"model": "TEST", "tabs": ["Shooting"], "layouts": [{"model": "TEST", "firmware": "1.00"}],
            "menu": [{"tab": "Shooting", "group": g, "label": x, "order": n} for n, (g, x) in enumerate([("G1", "A"), ("G1", "B"), ("G2", "C")])],
            "settings": [setting("global:0x0001", "B", "G1", "B"), setting("global:0x0002", "X1", "G1", "X > X1 [Movie mode]"),
                         setting("global:0x0003", "Z", "Audio", "Z [Movie mode]"), setting("global:0x0004", "Q", "G1", "Q [S&Q mode]"),
                         setting("global:0x0005", "Elsewhere", "Other (from SDK)")]}


def test_the_other_modes_rows_come_after_the_stills_rows(tmp_path, monkeypatch):
    """As the editor draws a setting's row_mode: a group's rows only Movie (or S&Q) has after its Stills rows, each
    mode's in its own order and marked with it, a row S&Q shares with Movie only once, a group only Movie has where
    its menu has it, and the records the shared placement hangs there with them; what no menu lists stays apart."""
    (tmp_path / "TEST_fw1.00").mkdir()
    (tmp_path / "TEST_fw1.00" / "menu_tree_TEST_fw1.00.json").write_text(json.dumps(MODE_TREE), encoding="utf-8")
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path)          # the tree is the mapper's own, there
    monkeypatch.setattr(pv, "RUN_ROOT", None)
    d = mode_doc()
    tabs = pv.menu(d, pv.records(d, {}), tmp_path)
    t = tabs[0]
    assert [(g["name"], g["num"], g.get("mode")) for g in t["groups"]] == [("G1", 1, None), ("Audio", "", "Movie"), ("G2", 2, None)]
    g1 = t["groups"][0]
    assert [(x["l"], x.get("mode")) for x in g1["rows"]] == [("A", None), ("B", None), ("X", "Movie"), ("Q", "S&Q")]
    x = g1["rows"][2]
    assert x["kids"][0]["l"] == "X1" and x["kids"][0]["mode"] == "Movie" and x["kids"][0]["recs"] == ["global:0x0002"]
    assert g1["rows"][1]["recs"] == ["global:0x0001"] and g1["rows"][3]["recs"] == ["global:0x0004"]
    assert t["groups"][1]["rows"][0]["recs"] == ["global:0x0003"]
    assert [o["keys"] for o in t["others"]] == [["global:0x0005"]]
    # the definition places each where the page hangs it
    got = placement.settings(d, MODE_TREE)
    assert {k: v.get("row_mode") for k, v in got.items()} == {"global:0x0001": None, "global:0x0002": "Movie",
                                                               "global:0x0003": "Movie", "global:0x0004": "S&Q"}


@needs_evidence
def test_the_a1s_movie_rows_hold_what_its_definition_places_there():
    """Every setting the a1 II's definition places on a Movie (or S&Q) row hangs on a row of that mode in the page."""
    d = definitions.load(A1)
    tabs = pv.menu(d, pv.records(d, {}), Path("."))
    where = {k: x.get("mode") for x, _ in pv.menu_nodes(tabs) for k in x["recs"]}
    moded = {s["key"]: s["row_mode"] for s in d["settings"] if s.get("row_mode")}
    assert moded and {k: where.get(k) for k in moded} == moded


# ---------------------------------------------------------------- the command line

TOOL = Path(pv.__file__)


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, timeout=60)


def test_help_names_pack():
    r = run("--help")
    assert r.returncode == 0 and "--pack" in r.stdout and "--png" in r.stdout


@pytest.mark.parametrize("args", [["--png"], ["--pack", "--out", "elsewhere/index.html"]])
def test_refused_before_anything_is_read(args, tmp_path):
    r = run(*[str(tmp_path / a) if a.endswith(".html") else a for a in args])
    assert r.returncode == 2
    assert not any(tmp_path.iterdir())


# ---------------------------------------------------------------- no page in a clone with no runs, and --open

def page_data_of(page: Path) -> dict:
    """The DATA a built page carries."""
    html = page.read_text(encoding="utf-8")
    at = html.index("const DATA = ") + len("const DATA = ")
    return json.JSONDecoder().raw_decode(html[at:])[0]


@pytest.fixture
def clone(tmp_path, monkeypatch):
    """A clone that has mapped nothing: the repository's a1 II definition and data/ copied, no runs/, nothing
    private, no camera named."""
    shutil.copy(definitions.path(A1), tmp_path / "schema.json")
    shutil.copytree(definitions.DATA, tmp_path / "data")
    monkeypatch.setattr(pv, "SCHEMA", tmp_path / "schema.json")
    monkeypatch.setattr(pv, "RUN_ROOT", None)
    monkeypatch.setenv("CAMSET_RUNS", str(tmp_path / "runs"))
    monkeypatch.delenv("CAMSET_CAMERA", raising=False)
    monkeypatch.setattr(sys.modules["camkit"], "CONFIG", tmp_path / "private" / "config.json")
    monkeypatch.setattr(pv.help_files, "OWN", tmp_path / "data")
    monkeypatch.setattr(pv.help_files, "PRIVATE", tmp_path / "private" / "help")
    monkeypatch.setattr(pv.webbrowser, "open", lambda url: pytest.fail("opened without --open"))
    return tmp_path


def build(monkeypatch, capsys, *args) -> list:
    monkeypatch.setattr(sys, "argv", ["proof_viewer.py", *args])
    pv.main()
    return capsys.readouterr().out.splitlines()


def refused(monkeypatch, capsys, *args) -> str:
    """What a refused build says (stderr), checked to be a refusal: exit status NO_RUNS, nothing on stdout."""
    monkeypatch.setattr(sys, "argv", ["proof_viewer.py", *args])
    with pytest.raises(SystemExit) as e:
        pv.main()
    out = capsys.readouterr()
    assert e.value.code == pv.NO_RUNS and out.out == ""
    return out.err.strip()


def test_a_clone_with_no_runs_gets_no_page(clone, monkeypatch, capsys):
    """The owner's rule (2026-11-06): no proof viewer where the kit has never run on a camera. The build says why and
    what would make it available, and writes nothing, --values, --pack and --open alike."""
    said = refused(monkeypatch, capsys)
    assert said == (f"No proof viewer for {A1}: no camera's runs are on this computer (no camera is named). The page "
                    "shows the camera's own screens from the kit's runs, so it is only for whoever ran the kit on their "
                    "camera; a submission carries the camera's definition, never its runs. To have it, map your camera "
                    "with the kit (docs/QUICKSTART.md), then run this again. A camera file's settings open in the editor "
                    "without it.")
    for args in (["--values", str(SAMPLE)], ["--pack"], ["--open"]):
        assert refused(monkeypatch, capsys, *args) == said
    assert not (clone / "runs").exists() and paths.mapped() == []
    # the camera named, its folder made, but the kit has not run on it: no page either
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    (clone / "runs" / A1 / "_cache").mkdir(parents=True)
    said = refused(monkeypatch, capsys).replace((clone / "runs").as_posix(), "runs")
    assert said.startswith(f"No proof viewer for {A1}: runs/{A1}/ holds no runs of the kit yet. The page shows ")
    assert said.endswith("Run the kit on the camera (docs/QUICKSTART.md), then run this again.")
    assert not (clone / "runs" / A1 / "_viewer").exists()


def test_a_camera_without_help_runs_gets_the_projects_own_help(clone, monkeypatch, capsys):
    """The camera's runs here but no help runs and no private help: the project's own help (its help file, else the
    definition's), said to be the project's, with no guide link and no readings mark; no row's own guide, no frame of
    My Menu or Main."""
    mapped_camera(clone / "runs" / A1, a_key(clone))
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    out = build(monkeypatch, capsys)
    page = (clone / "runs" / A1 / "_viewer" / "index.html").resolve()      # the definition's camera's folder
    assert out[-1] == str(page) and f"<title>Proof Viewer: {A1}</title>" in page.read_text(encoding="utf-8")
    data = page_data_of(page)
    assert len(data["records"]) > 1000 and data["menu"] and data["damaged"] == 0          # no damaged log line
    assert "/*DATA*/" not in page.read_text(encoding="utf-8")
    doc = json.loads((clone / "schema.json").read_text(encoding="utf-8"))
    own = pv.help_files.read(pv.help_files.own_path(doc), doc)
    have = {s["key"] for s in doc["settings"] if (own.get(s["key"]) or {}).get("help") or s.get("help")}
    helps = [r for r in data["records"].values() if r["help"]]
    assert {r["k"] for r in helps} == have and all(r["hs"] == "own" and r["hg"] == [] for r in helps)
    assert data["help_source"] == ({"own": len(have)} if have else {})
    opts = [o for r in data["records"].values() for o in r.get("oh") or []]
    assert all(o[3] == "own" and o[2] == [] for o in opts)
    assert len(opts) == len({(s["key"], v) for s in doc["settings"] for v, t in
                             (own.get(s["key"]) or {}).get("option_help") or s.get("option_help") or [] if t})
    assert data["guides"] == []
    assert not any(x.get("help") for x, _ in pv.menu_nodes(data["menu"]))
    assert data["my_menu"]["read"] == [] and len(data["my_menu"]["names"]) > 100
    assert [m["name"] for m in data["main"]["modes"]] == ["Stills", "Movie", "S&Q"] and not any(m["frames"] for m in data["main"]["modes"])


def test_the_cameras_page_shows_a_given_file_and_opens(clone, monkeypatch, capsys):
    opened = []
    monkeypatch.setattr(pv.webbrowser, "open", lambda url: opened.append(url) or True)
    mapped_camera(clone / "runs" / A1, a_key(clone))
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    out = build(monkeypatch, capsys, "--values", str(SAMPLE), "--open")
    page = (clone / "runs" / A1 / "_viewer" / "index.html").resolve()
    assert opened == [page.as_uri()] and out[-1] == str(page)
    assert f"values from {paths.shown(SAMPLE)}" in out[-2]
    data = page_data_of(page)
    assert data["file"]["name"] == SAMPLE.name and data["values"].endswith(SAMPLE.name)
    assert data["format"] == definitions.load(A1)["camera"]["file"]          # the block the page reads it through
    assert any(r["cur"] is not None for r in data["records"].values())


# ---------------------------------------------------------------- one camera's runs: runs/<model>_fw<fw>/

def mapped_camera(root, key: str):
    """A camera's runs with one proof (a frame and the record it changed) and a session start file."""
    run = root / "kit2_pass2"
    (run / "shots").mkdir(parents=True)
    (run / "dat").mkdir()
    Image.new("RGB", (8, 6), (0, 255, 0)).save(run / "shots" / "00001_chosen.png")
    shutil.copy(SAMPLE, run / "dat" / "reference_session_start.DAT")
    (run / "proofs.jsonl").write_text(json.dumps({"path": ["Some Row"], "label": "On", "chosen_frame": "00001_chosen.png",
                                                  "changes": [{"key": key, "before": 0, "after": 1}]}) + "\n",
                                      encoding="utf-8")


def a_key(clone) -> str:
    doc = json.loads((clone / "schema.json").read_text(encoding="utf-8"))
    return next(s["key"] for s in doc["settings"] if s["key"].startswith("global:") and "@" not in s["key"]
                and "[" not in s["key"])


def test_the_page_shows_the_active_cameras_frames(clone, monkeypatch, capsys):
    key = a_key(clone)
    mapped_camera(clone / "runs" / A1, key)
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    out = build(monkeypatch, capsys)
    page = (clone / "runs" / A1 / "_viewer" / "index.html").resolve()
    assert out[-1] == str(page) and "with pictures" in out[-2] and f"runs/{A1}/" in out[-2]
    data = page_data_of(page)
    assert data["camera"] == A1 and data["pictures"] >= 1
    assert data["values"] == "kit2_pass2/reference_session_start.DAT"
    assert ["../kit2_pass2/shots/00001_chosen.png", "option lit"] in data["records"][key]["ev"][0]["frames"]


def test_a_proofs_pictures_come_after_ok_first(runs):
    """The owner's case (2026-11-06: HEIF(4:2:0) chosen, a picture "with JPEG selected"): a proof's frames come in the
    order a person reads them, the screen after OK (the value set) first, then the option lit before OK, where the
    round dot still marks the value before."""
    run = runs / "kit2_a"
    Image.new("RGB", (8, 6), (0, 0, 0)).save(run / "shots" / "0002_menu.png")
    (run / "proofs.jsonl").write_text(json.dumps({"path": ["JPEG/HEIF Switch"], "label": "HEIF(4:2:0)", "chosen_frame": "0001.png",
                                                  "row_frame": "0002_menu.png", "changes": [{"key": "global:0x01d8", "before": 0, "after": 1}]}) + "\n",
                                      encoding="utf-8")
    ev = collections.defaultdict(list)
    old, pv.RUN_ROOT = pv.RUN_ROOT, runs
    try:
        pv.from_proofs(run, pv.Keys([{"key": "global:0x01d8"}]), runs / "_viewer", ev)
    finally:
        pv.RUN_ROOT = old
    assert ev["global:0x01d8"][0]["frames"] == [["../kit2_a/shots/0002_menu.png", "after OK"], ["../kit2_a/shots/0001.png", "option lit"]]


def test_a_table_proof_shows_the_options_its_list_showed(runs):
    """A table cell's proof keeps the options its list showed (options_seen), since the camera can offer options the
    walk never saw (RAW & JPEG with one slot, 2026-11-08): the evidence carries them as "seen", and the pictures keep
    their two steps' own captions, which the page reads word for word."""
    run = runs / "kit2_a"
    (run / "proofs.jsonl").write_text(json.dumps({"path": ["Image Quality Settings"], "kind": "table", "label": "RAW",
                                                  "chosen_frame": "0001.png", "options_seen": ["ORAW", "RAW & JPEG", "JPEG"],
                                                  "changes": [{"key": "global:0x01d8", "before": 3, "after": 0}]}) + "\n",
                                      encoding="utf-8")
    ev = collections.defaultdict(list)
    old, pv.RUN_ROOT = pv.RUN_ROOT, runs
    try:
        pv.from_proofs(run, pv.Keys([{"key": "global:0x01d8"}]), runs / "_viewer", ev)
    finally:
        pv.RUN_ROOT = old
    e = ev["global:0x01d8"][0]
    assert e["frames"] == [["../kit2_a/shots/0001.png", "option lit"]] and e["seen"] == ["ORAW", "RAW & JPEG", "JPEG"]


SEEN = """
const caps = proofShots([["a.png", "option lit"], ["b.png", "after OK"]], "RAW").map((x) => x[2]);
console.log(JSON.stringify({ caps, lost: proofLost([["b.png", "after OK"], ["a.png", "option lit"]]),
  lostOne: proofLost([["b.png", "after OK"]]), seen: listSeen({ seen: ["ORAW", "RAW & JPEG", "JPEG"] }), none: listSeen({}) }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_page_keeps_a_proofs_captions_and_writes_the_list_it_showed():
    """The page's own functions on a table proof with the list's options: both pictures keep their "1 of 2 · after OK"
    and "2 of 2 · before OK" captions, none is counted missing, and the options are a line of their own."""
    r = subprocess.run(["node", "-e", "".join(page_function(n) for n in ("proofShots", "proofLost", "listSeen")) + SEEN],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert got["caps"][0].startswith("1 of 2 · after OK: RAW is set") and got["caps"][1].startswith("2 of 2 · before OK")
    assert got["lost"] == [] and got["lostOne"] == ["before OK"]
    assert got["seen"] == "The list showed: ORAW · RAW & JPEG · JPEG" and got["none"] == ""


@pytest.mark.skipif(not definitions.evidence_path(definitions.path(A1)).exists() or not datafiles.menu_tree_file(A1).exists(),
                    reason="My Menu's read-back is found by its proof's run and a row never opened in the menu tree, "
                           "both in private/evidence/ (not here)")
def test_the_page_carries_help_my_menu_and_main_with_their_frames(clone, monkeypatch, capsys):
    """With the camera's runs (and the definition whole, its evidence with it, as the viewer reads it on the mapper's
    computer): a setting's help (the private file's, made up here) links the guide it was read from,
    an option's too, a row no setting belongs to gets its own guide, My Menu's read-back and each mode's Main page
    their frames; --pack carries every one of them."""
    (clone / "schema.json").write_text(json.dumps(definitions.load(A1)), encoding="utf-8")
    doc = json.loads((clone / "schema.json").read_text(encoding="utf-8"))
    for x in doc["settings"]:          # the definition's own words out: the made-up help files below are the only help
        x.pop("help", None), x.pop("option_help", None)
    (clone / "schema.json").write_text(json.dumps(doc), encoding="utf-8")
    key = a_key(clone)
    s = next(x for x in doc["settings"] if x["key"] == key)
    v = (s.get("values") or [[0, "Zero"]])[0][0]
    key2 = next(x["key"] for x in doc["settings"] if x["key"].startswith("global:") and x["key"] != key and "@" not in x["key"]
                and "[" not in x["key"] and x.get("values"))
    root = clone / "runs" / A1
    mapped_camera(root, key)
    tree = datafiles.load_menu_tree(A1)          # the mapper's own, private whole: a row the walk never opened
    bare = next(r["label"] for t in tree["tabs"] for p in t["pages"] for r in p["rows"] if r.get("state") == "never")
    help_run(root, {"help.jsonl": [{"context": "Stills mode", "label": bare, "text": "A made-up action guide.", "frames": ["a.png"]}],
                    "option_help.jsonl": [{"context": "Stills mode", "path": ["Some Row"], "index": -1, "label": None,
                                           "text": "Made-up setting help.", "frames": ["r.png"]},
                                          {"context": "Stills mode", "path": ["Some Row"], "index": 0, "label": "x",
                                           "text": "Made-up option help.", "frames": ["o.png"]}]},
             [{"frame": "r.png", "ocr": "Made-up setting halp.", "vlm": "Made-up setting help.", "text": "Made-up setting help.",
               "how": "two vision readers"}])
    private = clone / "private" / "help"
    private.mkdir(parents=True)
    (private / f"help_{A1}.json").write_text(json.dumps(
        {"model": "ILCE-1M2", "firmware": "4.00", "source": "made up",
         "settings": {key: {"help": "Made-up setting help.", "option_help": [[v, "Made-up option help."]]},
                      key2: {"option_help": [[0, "A camera option no guide shows."]]}}}), encoding="utf-8")
    (clone / "data" / A1 / f"help_{A1}.json").write_text(json.dumps(
        {"model": "ILCE-1M2", "firmware": "4.00", "source": "made up",
         "settings": {key: {"help": "Own words one.", "option_help": [[v, "Own option one."], [v + 1, "Own option two."]]},
                      key2: {"help": "Own words two."}}}), encoding="utf-8")
    lines(root / "kit2_page_scan" / "scan.jsonl", [scan_line("m.png", "menu", 0, "A"), scan_line("t.png", "tiles", 0),
                                                    scan_line("m.png", "menu", 0, "A")])
    png(root / "kit2_page_scan" / "shots" / "t.png")
    first = doc["camera"]["my_menu"]["records"][0]
    code, name = next((c, n) for c, n in next(x for x in doc["settings"] if x["key"] == f"global:0x{first:04x}[0]")["values"] if c != 2)
    run = (root / "kit2_mymenu_scan")
    run.mkdir()
    (run / "mymenu_readback.json").write_text(json.dumps({"1": {"frame": "p.png", "in_order": True, "slots": [[code, name]]}}),
                                               encoding="utf-8")
    png(run / "shots" / "p.png")
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    out = build(monkeypatch, capsys)
    # only the camera's texts are offered a guide, and only they count as linked or not
    assert out[-3].startswith("help: 2 settings (1 the camera's guide, 1 the project's own words), 3 option texts (2 the "
                              "camera's guide, 1 the project's own words); 2 of 3 texts from the camera's guide linked to a "
                              "guide frame, 1 whose two readings differed; 1 of ")
    assert "My Menu: 1 of " in out[-3] and "Main: 1 of 3 modes with a frame" in out[-3]
    data = page_data_of(Path(out[-1]))
    r, gs = data["records"][key], data["guides"]
    assert r["help"] == "Made-up setting help." and r["hs"] == "camera"
    assert [gs[i]["frames"][0][0] for i in r["hg"]] == ["../kit2_help/shots/r.png"]
    assert gs[r["hg"][0]]["ocr"] == "Made-up setting halp." and gs[r["hg"][0]]["vlm"] == "Made-up setting help."
    assert r["oh"] == [[v, "Made-up option help.", [r["oh"][0][2][0]], "camera"], [v + 1, "Own option two.", [], "own"]]
    assert gs[r["oh"][0][2][0]]["frames"][0][0].endswith("/o.png")
    r2 = data["records"][key2]          # the project's words for the setting, the camera's for an option: each says whose
    assert (r2["help"], r2["hs"], r2["hg"], r2["oh"]) == ("Own words two.", "own", [], [[0, "A camera option no guide shows.", [], "camera"]])
    rows = [x for x, _ in pv.menu_nodes(data["menu"]) if x.get("help")]
    assert [(x["l"], x["help"], x["hs"]) for x in rows] == [(bare, "A made-up action guide.", "camera")]
    assert data["help_source"] == {"camera": 2, "own": 1}          # the row's guide and key's help; key2's help
    assert data["my_menu"]["read"][0]["frames"] == [["../kit2_mymenu_scan/shots/p.png", "kit2_mymenu_scan · page 1 read back on the camera"]]
    assert [m["frames"] for m in data["main"]["modes"]][1:] == [[], []] and data["main"]["modes"][0]["run"] == "kit2_page_scan"
    # packed, every one of those frames is copied beside the page and linked there
    n = len(pv.linked_frames(data))
    out = build(monkeypatch, capsys, "--pack")
    data = page_data_of(Path(out[-1]))
    assert out[-2].startswith(f"packed {n} frames") and n == 6          # the proof's, three guides', My Menu's, Main's
    assert all(f.startswith("frames/") for f in pv.linked_frames(data))
    assert (root / "_viewer" / "frames" / "kit2_help" / "shots" / "a.jpg").is_file()


def test_another_cameras_page_gets_none_of_the_a1s_help(clone, monkeypatch, capsys):
    """The owner's rule ("a new user with a different camera shouldn't get the a1 II help"): the page of a made-up
    second camera's definition (the a1 II's settings under another model, their help taken out) shows none of the a1
    II's help: not the a1 II's files, which are not named for it, nor copies of them renamed for it, the camera's text
    and the project's own, refused for the model they carry inside and said so; nor a file of another firmware."""
    other = "ILCE-7M5_fw4.00"
    doc = json.loads((clone / "schema.json").read_text(encoding="utf-8"))
    doc["model"] = doc["layouts"][0]["model"] = "ILCE-7M5"
    doc["camera"].pop("model", None)
    for x in doc["settings"]:
        x.pop("help", None), x.pop("option_help", None)
    (clone / "schema.json").write_text(json.dumps(doc), encoding="utf-8")
    camera = {"model": "ILCE-1M2", "firmware": "4.00", "source": "made up",
              "settings": {s["key"]: {"help": "The a1 II's guide.", "option_help": [[0, "An a1 II option."]]} for s in doc["settings"]}}
    private = clone / "private" / "help"
    private.mkdir(parents=True)
    (private / f"help_{A1}.json").write_text(json.dumps(camera), encoding="utf-8")
    (private / f"help_{other}.json").write_text(json.dumps(camera), encoding="utf-8")          # renamed for the other
    (clone / "data" / other).mkdir()
    shutil.copy(clone / "data" / A1 / f"help_{A1}.json", clone / "data" / other / f"help_{other}.json")
    mapped_camera(clone / "runs" / other, a_key(clone))          # the page is the camera's whose runs are here
    monkeypatch.setenv("CAMSET_CAMERA", other)

    def no_help(out):
        data = page_data_of(Path(out[-1]))
        assert data["camera"] == other or Path(out[-1]).parent.parent.name == other
        assert not any(r["help"] or r.get("oh") for r in data["records"].values())
        assert data["help_source"] == {}
    out = build(monkeypatch, capsys)
    for p in (private / f"help_{other}.json", clone / "data" / other / f"help_{other}.json"):
        assert f"help: {p.as_posix()} is not used: it is for the ILCE-1M2 firmware 4.00, not the ILCE-7M5 firmware 4.00" in out
    no_help(out)
    # the camera's text for this model, but another firmware: refused too
    (private / f"help_{other}.json").write_text(json.dumps(dict(camera, model="ILCE-7M5", firmware="3.00")), encoding="utf-8")
    out = build(monkeypatch, capsys)
    assert (f"help: {(private / f'help_{other}.json').as_posix()} is not used: it is for the ILCE-7M5 firmware 3.00, "
            "not the ILCE-7M5 firmware 4.00") in out
    no_help(out)


def test_another_cameras_runs_are_never_read(clone, monkeypatch, capsys):
    """The kit works on a second camera: there is no page of the a1 II's definition (its runs are not that camera's),
    it says what would make one, and nothing is written into either camera's folder."""
    key = a_key(clone)
    mapped_camera(clone / "runs" / A1, key)
    mapped_camera(clone / "runs" / "ILCE-7M5_fw1.00", key)
    monkeypatch.setenv("CAMSET_CAMERA", "ILCE-7M5_fw1.00")
    assert refused(monkeypatch, capsys) == (
        f"No proof viewer for {A1}: the kit works on ILCE-7M5_fw1.00 (CAMSET_CAMERA), and another camera's runs are "
        "never shown on this definition (docs/decisions/0019). ILCE-7M5_fw1.00 has no definition yet: "
        "kit/schema_update.py --write writes it from its runs, and its own page can then be built.")
    assert not (clone / "runs" / "ILCE-7M5_fw1.00" / "_viewer").exists() and not (clone / "runs" / A1 / "_viewer").exists()


def test_runs_at_the_top_stop_the_build_with_the_move(clone, monkeypatch, capsys):
    """Runs from before per-camera folders are never read where they are: the build stops and names the command."""
    mapped_camera(clone / "runs", a_key(clone))                     # runs/kit2_pass2 at the top of runs/
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    monkeypatch.setattr(sys, "argv", ["proof_viewer.py"])
    with pytest.raises(paths.Leftovers) as e:
        pv.main()
    said = str(e.value).replace(str(clone / "runs"), "runs")
    assert said == (f"runs/kit2_pass2 sits at the top of runs/; run `python3 kit/tools/migrate_runs.py --camera {A1}` "
                    f"to move the {A1}'s runs under runs/{A1}/ (--dry-run shows the plan first). Until then the kit "
                    "does not use them.")
    assert not (clone / "runs" / A1).exists() and not (clone / "runs" / "_viewer").exists()


def test_the_page_is_the_active_cameras_definition(clone, monkeypatch, capsys):
    """With no definition given, the page is the active camera's definition when it has one, else the reference
    (the a1 II's); --definition names one, and an unknown one stops with what is missing."""
    monkeypatch.setattr(pv, "SCHEMA", None)
    assert pv.pick_definition() == definitions.path(definitions.REFERENCE)       # no camera named
    monkeypatch.setenv("CAMSET_CAMERA", "ILCE-7M5_fw1.00")
    assert pv.pick_definition() == definitions.path(definitions.REFERENCE)       # a camera with none of its own
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    assert pv.pick_definition() == definitions.path(A1)
    assert pv.pick_definition(A1) == definitions.path(A1)
    with pytest.raises(SystemExit, match="no definition of ILCE-7M5_fw1.00"):
        pv.pick_definition("ILCE-7M5_fw1.00")


def test_the_page_reads_the_file_through_the_block_it_carries():
    """The page carries no reader of its own: no Kaitai runtime, no offsets of the a1 II's; its file layout view reads
    the download through DATA.format, the definition's container block (docs/decisions/0020)."""
    assert "KaitaiStream" not in PAGE and "SonyCamset" not in PAGE and "/*KAITAI*/" not in PAGE
    script = PAGE[PAGE.index("// ---- the file layout view"):]
    code = "\n".join(ln for ln in script.splitlines() if not ln.strip().startswith("//"))
    for constant in ("0x3c", "0x39", "0x36", "0x02cf", "f.size - 4", "SONY1"):
        assert constant not in code, constant
    assert "const FMT = DATA.format" in PAGE


PAGE_PARTS = """
const R = { "k:a": { vals: [[1, "One"]] }, "k:b": { vals: [], rg: true, u: "mm" }, "k:c": { vals: [] }, "k:n": { vals: [] }, "k:d": { vals: [] },
  "set:0x0180@290": { vals: [], size: 2 }, "set:0x0180@292": { vals: [] } };
const file = { 0: { "k:a": 1, "k:b": 35, "k:c": 7 }, 1: { "k:a": 1, "k:n": 1, "k:d": 250 }, 2: { "k:n": 4, "k:d": 1 }, 3: { "k:n": 4, "k:d": 0 } };
const valueIn = (f, sec, k) => (R[k] && f[sec] ? f[sec][k] : undefined);
const frac = { kind: "fraction", numerator_key: "k:n", denominator_key: "k:d", live_text: "set on the camera" };
const lom = { kind: "live_or_memory", keys: ["k:a"], memory_keys: ["k:gone"] };
const DATA = { guides: [{ frames: [["a.png", "A"]], how: "agreed" }, { frames: [["b.png", "B"], ["c.png", "C"]], how: "two vision readers", ocr: "x", vlm: "y" }] };
const keysFor = () => ["set:0x0180@290"], elemKey = (r, i) => `element ${i}`, rec = { off: 100, end: 708, size: 300, count: 2, sec: 1, id: 0x180 };
const parts = (ids) => { const p = helpParts(ids); return [p.seq.map((s) => s.src), p.differ.length]; };
// a help block drawn as a plain tree: what it offers besides its text (a guide link, a readings fold) and its hover
const el = (tag, attrs = {}, ...kids) => ({ tag, attrs, kids: kids.flat().filter((k) => k !== null && k !== undefined && k !== false) });
const offers = (b) => [b.attrs.title, ...b.kids.filter((k) => typeof k === "object").map((k) => k.tag)];
const source = (s) => { DATA.help_source = s; return helpSource(); };
const READ_HOW = {};          // the readings' verdicts in words (not checked here)
console.log(JSON.stringify({
  keys: tileText({ kind: "keys", keys: ["k:a", "k:b", "k:c", "k:gone"] }, file, 0), none: tileText({ kind: "keys", keys: ["k:gone"] }, file, 0),
  missing: tileText({ kind: "keys", keys: ["k:a"] }, file, 2), frac_live: tileText(frac, file, 0), frac: tileText(frac, file, 1),
  whole: tileText(frac, file, 2), zero: tileText(frac, file, 3), lom_live: tileText(lom, file, 0), lom_mem: tileText(lom, file, 1),
  nofile: tileText(lom, null, 0), keys_for: [tileKeys(lom, 0), tileKeys(lom, 1), tileKeys(frac, 0), tileKeys(frac, 2)],
  help: [parts([0, 1]), parts([]), parts(undefined), parts([5])],
  at: [keyAt(rec, 108 + 291), keyAt(rec, 108 + 292), keyAt(rec, 108 + 5), keyAt(rec, 108 + 305), keyAt(rec, 102), keyAt(rec, 708)],
  camera: offers(helpBlock("Words.", [0, 1], "camera")), own: offers(helpBlock("Words.", [0, 1], "own")), blank: helpBlock("", [0], "camera"),
  tips: [helpTip("Words.", "own"), helpTip("Words.", "camera"), helpTip("Words.", undefined)],
  sources: [source({ camera: 3, own: 2 }), source({ own: 2 }), source({ camera: 1 }), source({})],
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_main_tiles_the_help_frames_and_the_setting_at_the_cursor():
    """The page's own functions on made-up records: a Main tile's value as the editor's tile_text gives it (its
    settings' values joined, a number with its unit, a fraction n/d or n" from a memory set, the definition's words
    where the section holds none), the guide frames and differing readings of a help text (the camera's words only),
    whose words each text is, and the setting whose bytes hold the file layout's cursor (a 16-bit field's, else its
    element's, none in a record's header)."""
    code = ("".join(page_function(n) for n in ("tileKeys", "describeV", "tileText", "helpParts", "keyAt", "helpBlock", "helpSource"))
            + page_line("HELP_FROM") + page_line("helpTip") + PAGE_PARTS)
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert got["keys"] == "One · 35 mm · 7 (no name yet)" and got["none"] == "on the camera" and got["missing"] == "—"
    assert (got["frac_live"], got["frac"], got["whole"], got["zero"]) == ("set on the camera", "1/250", '4"', "—")
    assert (got["lom_live"], got["lom_mem"], got["nofile"]) == ("One", "on the camera", "")
    assert got["keys_for"] == [["k:a"], ["k:gone"], [], ["k:n", "k:d"]]
    assert got["help"] == [[["a.png", "b.png", "c.png"], 1], [[], 0], [[], 0], [[], 0]]
    assert got["at"] == ["set:0x0180@290", "set:0x0180@292", "element 0", "element 1", None, None]
    # whose words a text is: the camera's link their guide screens and say when the readings differed; the project's own
    # never do, and each says whose it is on hover; the top bar says once where the help comes from
    assert got["camera"] == ["The camera's own In-Camera Guide, read off its screen", "button", "details"]
    assert got["own"] == ["Camset's own words, not the camera's guide"] and got["blank"] is None
    assert got["tips"] == ["Words.\n\n(Camset's own words, not the camera's guide)",
                           "Words.\n\n(The camera's own In-Camera Guide, read off its screen)", "Words."]
    assert got["sources"] == [" · help: the camera's own guide, read off its screen, and Camset's own words where it has none",
                              " · help: Camset's own words", " · help: the camera's own guide, read off its screen", ""]


PROOF_SETS = """
const r = { k: "k", run: "kit2_pass2", vals: [[0, "A"], [1, "B"]] };
const e = (v, run, n, tag) => ({ v, run, frames: Array.from({ length: n }, (_, i) => ["f" + i, i ? "option lit" : "after OK"]), label: tag });
const sets = proofSets(r, [e(1, "kit2_pass2", 2, "old"), e(0, "kit2_pass2", 2, "a-old"), e(1, "kit2_pass2", 2, "new"),
                           e(1, "kit2_pass2", 1, "newest-one-frame"), e(0, "kit2_other", 2, "other-run")]);
console.log(JSON.stringify(sets.map((s) => [s.v, s.lead.label, s.others.map((o) => o.label)])));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_a_value_proved_again_shows_its_newest_proof():
    """proofSets: of a value's proofs, the lead is the one with both frames kept and from the definition's run, and among
    those the last in the data's order (the proofs file is in the order they were made): a value proved again after a
    prover fix shows the new proof, the old ones folded under it in their order. A one-frame newer proof does not
    displace a two-frame one, nor does another run's."""
    r = subprocess.run(["node", "-e", page_function("byValue") + page_function("proofSets") + PROOF_SETS], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [[0, "a-old", ["other-run"]], [1, "new", ["old", "newest-one-frame"]]]


SELECTIONS = """
const L = { f: { size: 0x2000, start: 0x3c, end: 0x1ffc, sections: [{ off: 0x3c, end: 0x1000 }, { off: 0x1000, end: 0x1ffc }] } };
const rec = { off: 0x1100, end: 0x1100 + 8 + 12 * 4, size: 12, count: 4, sec: 1 };
const block = { kind: "range", a: 0x1004, b: 0x1400, sec: 1, lab: "records 0x0100\\u20130x01ff" };
console.log(JSON.stringify({
  file: selRange({ kind: "file" }), section: selRange({ kind: "section", sec: 1 }), block: selRange(block),
  record: selRange({ kind: "rec", rec }), every_element: selRange({ kind: "rec", rec, part: [0, 48] }),
  elements: selRange({ kind: "range", a: rec.off + 8, b: rec.end, sec: 1, rec, lab: "elements" }),
  element: selRange({ kind: "rec", rec, part: [12, 24] }), field16: selRange({ kind: "rec", rec, part: [14, 16], key: "set:0x0100@14" }),
  same_block: sameSel(block, { ...block }), other_name: sameSel(block, { ...block, lab: "every record" }),
  other_end: sameSel(block, { ...block, b: 0x1300 }), not_a_record: sameSel(block, { kind: "rec", rec }),
}));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_every_kind_of_selection_has_its_bytes():
    """Each row of the file layout view's structure chooses bytes, which the map outlines and the hex lights: the
    page's selRange gives every kind its range (the whole file and a section as well, a block of records, a record's
    elements, one element, a 16-bit field in one), and a block is the same choice only with the same bounds and name.
    node runs the page's own two functions on a made-up file."""
    r = subprocess.run(["node", "-e", page_function("selRange") + page_function("sameSel") + SELECTIONS], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got, rec = json.loads(r.stdout), 0x1100
    assert got["file"] == [0, 0x2000] and got["section"] == [0x1000, 0x1ffc] and got["block"] == [0x1004, 0x1400]
    assert got["record"] == got["every_element"] == [rec, rec + 8 + 48]
    assert got["elements"] == [rec + 8, rec + 56] and got["element"] == [rec + 20, rec + 32] and got["field16"] == [rec + 22, rec + 24]
    assert got["same_block"] and not got["other_name"] and not got["other_end"] and not got["not_a_record"]
    # the map takes every selection's bytes, the whole file's and a section's too
    assert "const range = selRange(L.sel)" in PAGE


LINES = """
const state = { filter: "all", q: "" }, R = { "k:1": { n: "B", k: "k:1" }, "k:2": { n: "X1", k: "k:2" } };
const keepRec = () => true;
const node = (id, l, mode, recs = [], kids = []) => ({ id, l, mode, recs, kids, subs: [], opts: [] });
const group = { rows: [node("n1", "A"), node("n2", "B", undefined, ["k:1"]), node("Movie:n1", "X", "Movie", [], [node("Movie:n2", "X1", "Movie", ["k:2"])]),
  node("S&Q:n1", "Q", "S&Q")], extra: [] };
const shots = proofShots([["a.png", "option lit"], ["b.png", "after OK"], ["c.png", "a step"]], "HEIF(4:2:0)");
console.log(JSON.stringify({ lines: linesOf(group).map((x) => x.head ? "# " + x.head : x.id),
  shots, none: proofShots([["a.png", "option lit"]], "") }));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_page_heads_each_modes_rows_and_reads_a_proof_after_ok_first():
    """The page's own functions: a group's lines with "In Movie mode" (and "In S&Q mode") over that mode's rows after
    the Stills rows; a proof's two pictures with the one after OK first, each caption saying in a plain sentence what
    the orange bar and the round dot show."""
    code = page_line("modeWords") + "".join(page_function(n) for n in ("recsOf", "keepNode", "rowsOf", "linesOf", "proofShots")) + LINES
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert got["lines"] == ["n1", "n2", "# In Movie mode", "Movie:n1", "Movie:n2", "# In S&Q mode", "S&Q:n1"]
    assert got["shots"] == [["b.png", "after OK", "1 of 2 · after OK: HEIF(4:2:0) is set, so the row shows it or the round dot is on it"],
                            ["a.png", "option lit", "2 of 2 · before OK: the orange bar is on HEIF(4:2:0), and the round dot still marks the value before"],
                            ["c.png", "a step", "a step"]]
    assert got["none"] == [["a.png", "option lit", "2 of 2 · before OK: the orange bar is on the option being chosen, and the round dot still marks the value before"]]
    assert "The orange bar is the cursor" in page_line("BAR_DOT") and "The round dot marks the value the camera holds" in page_line("BAR_DOT")


FIT = """
const out = [];
for (const [show, wth, set, n] of [[12, 3, 12, 4], [2, 3, 3, 4], [0, "base", 5, 13], [3, 0, 3, 13], [5, "none", 1, 1]]) {
  globalThis.CMP = { show, with: wth }; globalThis.L = { set };
  fitSections(n);
  out.push([CMP.show, CMP.with, L.set]);
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_another_file_with_fewer_sections_keeps_the_page_within_them():
    """Opening a file with fewer sections than the one shown or compared with (another body's) left the map and the
    comparison reaching past its last section: fitSections brings them back within it, and the page's drag ends with
    one window listener per drag, not one more for every hex dump ever drawn."""
    code = page_function("fitSections") + FIT
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == [[0, 3, 3], [2, 3, 3], [0, "base", 5], [3, 0, 3], [0, "none", 0]]
    assert "fitSections(f.sections.length);" in PAGE
    script = PAGE[PAGE.index("function hexScroller("):]
    assert script.count('window.addEventListener("pointerup"') == 1 and "}, { once: true });" in script


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_pages_script_parses(tmp_path):
    """node --check of the page's whole script, as the template holds it."""
    script = tmp_path / "page.js"
    script.write_text(PAGE[PAGE.index("<script>") + len("<script>"):PAGE.rindex("</script>")], encoding="utf-8")
    r = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
