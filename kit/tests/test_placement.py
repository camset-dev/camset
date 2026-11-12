"""Where each setting sits on the camera's menus (kit/camkit/placement.py): the placement the proof viewer hangs records
with and kit/schema_update.py writes into a definition ("row", "row_at", "under_option").

Run: .venv/bin/python -m pytest kit/tests/test_placement.py -q
A made-up camera's menu tree and settings, then the a1 II's committed definition and data/; nothing talks to a camera.
"""
import json
import re
from pathlib import Path

import pytest

from camkit import datafiles, definitions, placement

import proof_viewer as pv
import schema_update as S

A1 = "ILCE-1M2_fw4.00"


# the placement rests on the proofs' rows (proved.menu) and the menu tree, both the mapper's own, in private/evidence/
# (camkit.definitions, camkit.datafiles)
needs_evidence = pytest.mark.skipif(not (definitions.evidence_path(definitions.path(A1)).exists()
                                         and definitions.menu_tree_file(A1).exists()),
                                    reason="reads the proofs' rows and the menu tree, in private/evidence/ (not here)")


def row(label, *kids, options=()):
    return {"label": label, "options": list(options), "children": list(kids)}


TREE = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Shooting", "pages": [
    {"page": "1/2", "group": "Drive Mode", "rows": [
        row("Drive Mode", options=["Single Shooting", "Continuous Shooting: Mid", "Self-timer(Single): 5 sec"]),
        row("Cont. Shooting Speed", row("Hi+ (E-Shutter)"), row("Hi (E-Shutter)")),
    ]},
    {"page": "2/2", "group": "Drive Mode", "rows": [
        row("Bracket Settings", row("Selftimer during Bracket"), row("Focus Bracket Settings", row("Shooting Interval"))),
    ]},
    {"page": "3/3", "group": "Shutter/Silent", "rows": [row("Silent Mode")]},
]}]}


def setting(key, name, group="Drive Mode", menus=(), values=()):
    s = {"key": key, "area": "global", "id": 1, "name": name, "tab": "Shooting", "group": group, "order": 9000,
         "values": [list(v) for v in values]}
    if menus:
        s["proved"] = {"run": "kit2_pass2", "date": "2026-10-29", "menu": list(menus)}
    return s


DRIVE = [[0, "Single Shooting"], [1, "Continuous Shooting"], [5, "Self-timer"], [7, "Self-timer(Cont.)"]]


def doc(*settings):
    return {"model": "TEST", "tabs": ["Shooting"], "layouts": [{"model": "TEST", "firmware": "1.00"}],
            "menu": [{"tab": "Shooting", "group": "Drive Mode", "label": "Drive Mode", "order": 1},
                     {"tab": "Shooting", "group": "Drive Mode", "label": "Cont. Shooting Speed", "order": 2},
                     {"tab": "Shooting", "group": "Drive Mode", "label": "Bracket Settings", "order": 3},
                     {"tab": "Shooting", "group": "Shutter/Silent", "label": "Silent Mode", "order": 4}],
            "settings": list(settings)}


def test_a_setting_hangs_on_its_row_with_the_cameras_labels_and_order():
    d = doc(setting("global:0x0001", "Drive Mode", menus=["Drive Mode"], values=DRIVE),
            setting("global:0x0002", "Focus Bracket Interval", menus=["Bracket Settings > Focus Bracket Settings > Shooting Interval"]),
            setting("global:0x0003", "Selftimer during Bracket"),          # no proof: by its name in its group
            setting("global:0x0004", "Hi(E-Shutter)", menus=["Cont. Shooting Speed > Hi (E-Shutter)"]),
            setting("global:0x0005", "Hi+(E-Shutter)", menus=["Cont. Shooting Speed > Hi+ (E-Shutter)"]))
    got = placement.settings(d, TREE)
    assert got["global:0x0001"] == {"row": ["Drive Mode"], "row_at": [0]}
    assert got["global:0x0002"] == {"row": ["Bracket Settings", "Focus Bracket Settings", "Shooting Interval"], "row_at": [2, 1, 0]}
    assert got["global:0x0003"] == {"row": ["Bracket Settings", "Selftimer during Bracket"], "row_at": [2, 0]}
    # "Hi" and "Hi+" read alike once the signs are left out: the one written as read is taken
    assert got["global:0x0004"] == {"row": ["Cont. Shooting Speed", "Hi (E-Shutter)"], "row_at": [1, 1]}
    assert got["global:0x0005"] == {"row": ["Cont. Shooting Speed", "Hi+ (E-Shutter)"], "row_at": [1, 0]}


def test_the_choice_beside_an_option_is_under_that_option():
    d = doc(setting("global:0x0001", "Drive Mode", menus=["Drive Mode"], values=DRIVE),
            setting("global:0x0002", "Continuous speed", menus=["Drive Mode / Continuous Shooting", "Drive Mode / Continuous Shooting [recheck]"]),
            setting("global:0x0003", "Self-timer delay", menus=["Drive Mode / Self-timer(Single)"]),          # the option "Self-timer"
            setting("global:0x0004", "Cont. self-timer", menus=["Drive Mode > Self-timer(Cont.)"]),           # " > " into an option
            setting("global:0x0005", "Drive Mode (third record)", menus=["Drive Mode / Continuous Shooting", "Drive Mode"]),
            setting("global:0x0006", "Two options", menus=["Drive Mode / Continuous Shooting", "Drive Mode / Single Shooting"]),
            setting("global:0x0007", "Grid", menus=["Drive Mode / grid 0"]))
    got = placement.settings(d, TREE)
    assert got["global:0x0002"] == {"row": ["Drive Mode"], "row_at": [0], "under_option": "Continuous Shooting"}
    assert got["global:0x0003"]["under_option"] == "Self-timer"
    assert got["global:0x0004"]["under_option"] == "Self-timer(Cont.)"
    # a path to the row itself, two options, or words no option has: on the row, under no option
    for key in ("global:0x0005", "global:0x0006"):
        assert got[key] == {"row": ["Drive Mode"], "row_at": [0]}, key
    # an option named by its place in the row's list (a grid, a panel) is that option (test_an_indexed_option...)
    assert got["global:0x0007"]["under_option"] == "Single Shooting"
    # a choice named as its row (D-Range Optimizer's level) is not the row's own setting, wherever the definition lists it
    d = doc(setting("global:0x0009", "Drive Mode", menus=["Drive Mode / Continuous Shooting"], values=[[0, "Lo"], [1, "Hi"]]),
            setting("global:0x0001", "Drive Mode", menus=["Drive Mode"], values=DRIVE))
    got = placement.settings(d, TREE)
    assert got["global:0x0009"]["under_option"] == "Continuous Shooting" and "under_option" not in got["global:0x0001"]


def test_a_row_the_tree_lacks_places_nothing():
    d = doc(setting("global:0x0001", "Audio Recording", menus=["Audio Recording [Movie mode]"]),
            setting("global:0x0003", "Silent", group="Shutter/Silent", menus=["Silent Mode"]),
            setting("global:0x0004", "Unproved"))
    got = placement.settings(d, TREE)
    assert set(got) == {"global:0x0003"}
    assert got["global:0x0003"] == {"row": ["Silent Mode"], "row_at": [3]}          # the tab's fourth top row


def test_another_groups_row_places_the_setting_in_that_group():
    """A screen the definition keeps as a group of its own sits on its row, wherever in the tab the row is: the
    camera's group is "row_group", by the definition's name for it; a group cut from the camera's ("Drive Mode ›
    Bracket Settings") is that group."""
    d = doc(setting("global:0x0002", "Bracket order", group="Other (from SDK)", menus=["Bracket Settings > Selftimer during Bracket"]),
            setting("global:0x0003", "Silent", group="Silent screen", menus=["Silent Mode"]),
            setting("global:0x0005", "Interval", group="Drive Mode › Bracket Settings", menus=["Bracket Settings > Focus Bracket Settings > Shooting Interval"]))
    got = placement.settings(d, TREE)
    assert got["global:0x0002"] == {"row": ["Bracket Settings", "Selftimer during Bracket"], "row_at": [2, 0], "row_group": "Drive Mode"}
    assert got["global:0x0003"] == {"row": ["Silent Mode"], "row_at": [3], "row_group": "Shutter/Silent"}
    assert got["global:0x0005"]["row_group"] == "Drive Mode"


def test_a_row_in_another_tab_places_the_setting_there():
    """Where the setting's own tab has no row its paths lead to, a row of another tab does, from that tab's top row:
    the Stills menu's tabs first, then a mode's (by the context, or a path with none); "row_tab" names the tab and
    "row_group" the group there, and a label met somewhere deep in another tab places nothing."""
    tree = {"model": "TEST", "firmware": "1.00", "tabs": [
        {"tab": "Shooting", "pages": [{"page": "1/1", "group": "Drive Mode", "rows": [row("Drive Mode"), row("Bracket Settings", row("Order"))]}]},
        {"tab": "Setup", "pages": [{"page": "1/1", "group": "Operation Customize", "rows": [row("Custom Key Set."), row("Deep", row("Lonely"))]}]}],
        "modes": [{"mode": "Movie", "tabs": [{"tab": "Shooting", "pages": [
            {"page": "1/1", "group": "Shooting Mode", "rows": [row("Exposure Ctrl Type")]},
            {"page": "1/2", "group": "Drive Mode", "rows": [row("Drive Mode")]}]}]}]}
    d = {"model": "TEST", "tabs": ["Shooting", "Setup", "Exposure"], "menu": [], "settings": [
        setting("global:0x0001", "Movie key: AEL", menus=["Custom Key Set. / movie: AEL Button @0.key.0"]),
        {**setting("global:0x0002", "Bracket order", group="Other (from SDK)", menus=["Bracket Settings > Order"]), "tab": "Focus"},
        {**setting("global:0x0003", "Exposure Ctrl Type", group="Other (from SDK)", menus=["Exposure Ctrl Type [Movie mode]"]), "tab": "Exposure"},
        {**setting("global:0x0004", "Lonely", group="Other (from SDK)", menus=["Lonely"]), "tab": "Exposure"},
        {**setting("global:0x0005", "Key in Setup", group="Operation Customize", menus=["Custom Key Set. / AEL Button"]), "tab": "Setup"},
    ]}
    got = placement.settings(d, tree)
    assert got["global:0x0001"] == {"row": ["Custom Key Set."], "row_at": [0], "row_tab": "Setup", "row_group": "Operation Customize"}
    assert got["global:0x0002"] == {"row": ["Bracket Settings", "Order"], "row_at": [2, 0], "row_tab": "Shooting", "row_group": "Drive Mode"}
    assert got["global:0x0003"] == {"row": ["Exposure Ctrl Type"], "row_at": [0], "row_tab": "Shooting", "row_group": "Shooting Mode", "row_mode": "Movie"}
    assert "global:0x0004" not in got, "a row named so deep in another tab is not the place"
    assert got["global:0x0005"] == {"row": ["Custom Key Set."], "row_at": [0]}, "in its own tab: no row_tab"


def test_the_rows_under_a_row_never_opened_come_from_the_paths():
    """Under a row the tree knows no rows of (never opened, or read off a page scan alone), a path's submenu steps
    are the rows, in the order the definition lists the settings proved through them; a step past a screen the walk
    read is one of its options, and an option step (" / ") is never a row."""
    tree = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Shooting", "pages": [
        {"page": "1/1", "group": "Shooting Mode", "rows": [
            {"label": "Reg. Custom Shoot Set", "state": "never", "why": "by hand only"},
            {"label": "Drive Mode", "state": "walked", "options": ["Single Shooting", "Continuous Shooting"]},
            {"label": "Fn Menu Settings", "state": "unhandled"}]}]}]}
    hold = "Reg. Custom Shoot Set > Recall Custom hold {} > {}"
    d = {"model": "TEST", "tabs": ["Shooting"], "menu": [], "settings": [
        setting("global:0x0001", "Aperture", group="Recall Custom hold 2", menus=[hold.format(2, "Aperture")]),
        setting("global:0x0002", "Shoot Mode", group="Recall Custom hold 1", menus=[hold.format(1, "Shoot Mode")]),
        setting("global:0x0003", "Aperture", group="Recall Custom hold 1", menus=[hold.format(1, "Aperture") + " [by a file]"]),
        setting("global:0x0004", "Shoot Mode: registered", group="Recall Custom hold 1", menus=["Reg. Custom Shoot Set > Recall Custom hold 1"]),
        setting("global:0x0005", "Drive Mode", group="Shooting Mode", menus=["Drive Mode"], values=DRIVE),
        setting("global:0x0006", "Speed", group="Shooting Mode", menus=["Drive Mode > Continuous Shooting"]),
        setting("global:0x0007", "Fn 1", group="Fn Menu", menus=["Fn Menu Settings / Still Upper / 1"]),
    ]}
    got = placement.settings(d, tree)
    assert got["global:0x0001"] == {"row": ["Reg. Custom Shoot Set", "Recall Custom hold 2", "Aperture"], "row_at": [0, 0, 0], "row_group": "Shooting Mode"}
    assert got["global:0x0002"]["row"] == ["Reg. Custom Shoot Set", "Recall Custom hold 1", "Shoot Mode"]
    assert got["global:0x0002"]["row_at"] == [0, 1, 0]                     # hold 2's proof came first in the definition
    assert got["global:0x0003"]["row_at"] == [0, 1, 1]
    assert got["global:0x0004"]["row"] == ["Reg. Custom Shoot Set", "Recall Custom hold 1"]
    assert got["global:0x0006"] == {"row": ["Drive Mode"], "row_at": [1], "under_option": "Continuous Shooting"}
    assert got["global:0x0007"] == {"row": ["Fn Menu Settings"], "row_at": [2], "row_group": "Shooting Mode"}


MODES = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Shooting", "pages": [
    {"page": "1/3", "group": "Image Quality/Rec", "rows": [row("File Format"), row("Movie Settings")]},
    {"page": "2/3", "group": "Shutter/Silent", "rows": [row("Silent Mode"), row("Shutter Type")]},
    {"page": "3/3", "group": "Image Stabilization", "rows": [row("SteadyShot")]},
]}], "modes": [{"mode": "Movie", "tabs": [{"tab": "Shooting", "pages": [
    {"page": "1/4", "group": "Image Quality/Rec", "rows": [row("File Format"), row("Movie Settings"),
                                                           row("S&Q Settings", row("Frame Rate Settings"), row("Record Setting"))]},
    {"page": "2/4", "group": "0Shutter/Silent", "rows": [row("Silent Mode")]},           # an icon read as a letter
    {"page": "3/4", "group": "TC/UB", "rows": [row("Time Code Format"), row("Time Code Run")]},
    {"page": "4/4", "group": "Image Stabilization", "rows": [row("SteadyShot"), row("Framing Stabilizer")]},
]}]}]}


def test_a_setting_proved_in_a_mode_hangs_on_that_modes_row():
    """A row only the Movie menu has places a setting proved in Movie mode (its context says so), or one no context
    places in a mode, after the Stills rows of its gap; a row the Stills menu has stays the Stills menu's."""
    d = {"model": "TEST", "tabs": ["Shooting"], "menu": [
        {"tab": "Shooting", "group": "Image Quality/Rec", "label": "File Format", "order": 1},
        {"tab": "Shooting", "group": "Shutter/Silent", "label": "Silent Mode", "order": 3},
        {"tab": "Shooting", "group": "Image Stabilization", "label": "SteadyShot", "order": 5}], "settings": [
        setting("global:0x0001", "SQ Frame Rate", group="Image Quality/Rec", menus=["S&Q Settings > Frame Rate Settings > Frame Rate [Movie mode]"]),
        setting("global:0x0002", "Record Setting", group="Image Quality/Rec", menus=["S&Q Settings > Record Setting [Movie mode, File Format XAVC S 4K]"]),
        setting("global:0x0003", "Time Code Format", group="TC/UB", menus=["Time Code Format [movie]"]),
        setting("global:0x0004", "Framing Stabilizer", group="Image Stabilization", menus=["Framing Stabilizer"]),
        setting("global:0x0005", "File Format", group="Image Quality/Rec", menus=["File Format [Movie mode]"]),
        setting("global:0x0006", "Silent (movie)", group="Shutter/Silent", menus=["Silent Mode [Movie mode]"]),
        setting("global:0x0007", "Not in Movie", group="TC/UB", menus=["Time Code Run [S&Q mode]"]),
    ]}
    got = placement.settings(d, MODES)
    # the merged numbering: File Format 0, Movie Settings 1, S&Q Settings 2 (Movie's), Silent Mode 3, Shutter Type 4,
    # Time Code Format 5 and Time Code Run 6 (Movie's), SteadyShot 7, Framing Stabilizer 8 (Movie's)
    assert got["global:0x0001"] == {"row": ["S&Q Settings", "Frame Rate Settings", "Frame Rate"], "row_at": [2, 0, 0], "row_mode": "Movie"}
    assert got["global:0x0002"] == {"row": ["S&Q Settings", "Record Setting"], "row_at": [2, 1], "row_mode": "Movie"}
    assert got["global:0x0003"] == {"row": ["Time Code Format"], "row_at": [5], "row_mode": "Movie"}
    assert got["global:0x0004"] == {"row": ["Framing Stabilizer"], "row_at": [8], "row_mode": "Movie"}
    assert got["global:0x0005"] == {"row": ["File Format"], "row_at": [0]}           # the Stills menu has it
    assert got["global:0x0006"] == {"row": ["Silent Mode"], "row_at": [3]}
    assert "global:0x0007" not in got                                              # no S&Q menu in this tree
    assert placement.mode_of("Audio Rec Level [Movie mode]", ["Movie", "S&Q"]) == "Movie"
    assert placement.mode_of("Record Setting [Movie mode, S&Q Rec Frame Rate 30p]", ["Movie", "S&Q"]) == "Movie"
    assert placement.mode_of("Record Setting [S&Q Rec Frame Rate 30p]", ["Movie", "S&Q"]) is None
    assert placement.mode_of("Drive Mode", ["Movie"]) is None


def test_a_modes_own_rows_are_numbered_beside_their_group():
    """A mode's own rows come between the rows both menus have around them, after the last Stills row of their own
    group there, before them all when theirs is the group of the shared row before, after them all otherwise."""
    page = lambda n, g, *labels: {"page": n, "group": g, "rows": [row(x) for x in labels]}
    tree = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Shooting", "pages": [
        page("1/3", "G1", "A", "B"), page("2/3", "G2", "C"), page("3/3", "G3", "D", "E", "F")]}],
        "modes": [{"mode": "Movie", "tabs": [{"tab": "Shooting", "pages": [
            page("1/4", "G1", "A", "X"), page("2/4", "G2", "Y"), page("3/4", "New", "Z"), page("4/4", "G3", "D", "W", "F")]}]}]}
    d = {"model": "TEST", "tabs": ["Shooting"], "menu": [], "settings": []}
    stills, movie = placement.Tree(d, tree), placement.Tree(d, tree, mode="Movie")
    num = placement.merge_tops(stills, [("Movie", movie)])
    order = sorted((n, f"{m or 'S'}:{(stills if m is None else movie).tops[t][i][0]}") for (m, t, i), n in num.items())
    assert [x for _, x in order if not x.startswith("Movie:") or x[6:] in "XYZW"] == \
        ["S:A", "S:B", "Movie:X", "S:C", "Movie:Y", "Movie:Z", "S:D", "S:E", "Movie:W", "S:F"]
    assert num[("Movie", "Shooting", 0)] == num[(None, "Shooting", 0)]           # A: the row both menus have


def test_a_modes_group_is_named_as_the_definition_names_it():
    """A mode's group read with its icon as a letter ("0Shutter/Silent") is the definition's group; a group only
    that mode has keeps the menu's name."""
    d = {"model": "TEST", "tabs": ["Shooting"], "menu": [
        {"tab": "Shooting", "group": "Shutter/Silent", "label": "Silent Mode", "order": 3}], "settings": []}
    movie = placement.Tree(d, MODES, mode="Movie")
    assert [g["name"] for g in movie.by_tab["Shooting"]["groups"]] == ["Image Quality/Rec", "Shutter/Silent", "TC/UB", "Image Stabilization"]
    assert movie.where[movie.by_tab["Shooting"]["groups"][0]["rows"][0]["id"]][2] == [0]
    assert placement.Tree(d, MODES).by_tab["Shooting"]["groups"][0]["rows"][0]["id"] == "n1"          # the Stills ids as the viewer has them
    assert placement.steps("A > B / C › D [Movie mode]") == [("", "A"), (">", "B"), ("/", "C"), (">", "D")]


def test_an_option_is_matched_as_the_camera_wrote_it():
    assert placement.option_label("Continuous Shooting", DRIVE) == "Continuous Shooting"
    assert placement.option_label("Self-timer(Single)", DRIVE) == "Self-timer"
    assert placement.option_label("Self-timer(Cont.)", DRIVE) == "Self-timer(Cont.)"
    assert placement.option_label("С.Temp./Filter", [[1, "C.Temp./Filter"]]) == "C.Temp./Filter"         # a Cyrillic С read
    assert placement.option_label("grid 0", DRIVE) is None
    assert placement.option_label("", DRIVE) is None


def test_the_a1s_drive_mode_as_on_the_camera():
    """The owner's case (2026-11-06): Drive Mode's continuous shooting speed is the choice under its Continuous
    Shooting option, and the E-shutter speeds hang on their own rows under Cont. Shooting Speed."""
    d = definitions.load(A1)
    by = {}
    for s in d["settings"]:
        by.setdefault((s["group"], s["name"]), s)          # the first of a name, as the editor leads a row with it
    speed = by[("Drive Mode", "Drive memory - continuous shooting speed")]
    assert speed["row"] == ["Drive Mode"] and speed["under_option"] == "Continuous Shooting"
    assert "Continuous Shooting" in [lab for _, lab in by[("Drive Mode", "Drive Mode")]["values"]]
    assert by[("Drive Mode", "Hi+(E-Shutter)")]["row"] == ["Cont. Shooting Speed", "Hi+ (E-Shutter)"]
    assert by[("Drive Mode", "Hi(E-Shutter)")]["row"] == ["Cont. Shooting Speed", "Hi (E-Shutter)"]
    assert "under_option" not in by[("Drive Mode", "Drive Mode (menu choice)")]
    # every place is as long as its key, and every option one its row's own setting lists
    for s in d["settings"]:
        if "row" in s:
            assert len(s["row"]) == len(s["row_at"]), s["key"]
            assert list(s)[list(s).index("order") + 1] == "row", s["key"]
        if "under_option" in s and s["row"][-1] != s["under_option"] and s["under_option"] in s["row"]:
            # a page under the option (a Picture Profile's parameters): the row's own setting is the row before it
            i = s["row"].index(s["under_option"])
            own = next(o for o in d["settings"] if o.get("row_tab", o["tab"]) == s.get("row_tab", s["tab"])
                       and o.get("row") == s["row"][:i] and placement.norm(o["name"]) == placement.norm(s["row"][i - 1]))
            assert s["under_option"] in [lab for _, lab in own["values"]], s["key"]
        elif "under_option" in s:
            own = next(o for o in d["settings"] if o.get("row_group", o["group"]) == s.get("row_group", s["group"]) and o.get("row") == s["row"]
                       and placement.norm(o["name"]) == placement.norm(s["row"][-1]))
            assert s["under_option"] in [lab for _, lab in own["values"]], s["key"]


def test_the_a1s_sub_screens_and_movie_rows_as_on_the_camera():
    """The owner's case (2026-11-06): the screens the definition keeps as groups of their own sit on their camera
    rows (Recall Custom hold 1 under Reg. Custom Shoot Set, in Shooting Mode), and the Movie menu's rows hold what was
    proved on them (TC/UB, only the Movie menu has)."""
    d = definitions.load(A1)
    hold = [s for s in d["settings"] if s["group"] == "Recall Custom hold 1"]
    assert hold and all(s["row"][:2] == ["Reg. Custom Shoot Set", "Recall Custom hold 1"] and s["row_group"] == "Shooting Mode" for s in hold)
    fn = [s for s in d["settings"] if s["group"] == "Fn Menu"]
    assert fn and all(s["row"] == ["Fn Menu Settings"] and s["row_group"] == "Operation Customize" for s in fn)
    tc = [s for s in d["settings"] if s["group"] == "TC/UB" and not s.get("expert")]
    assert tc and all(s["row_mode"] == "Movie" and "row_group" not in s for s in tc)
    for s in d["settings"]:
        assert ("row_group" in s or "row_mode" in s) <= ("row" in s), s["key"]
        assert s.get("row_group") != s["group"], s["key"]


def test_with_place_puts_the_place_after_order_and_takes_an_old_one_away():
    s = {"key": "k", "name": "n", "order": 3, "row": ["Old"], "row_at": [9], "under_option": "x", "row_group": "G", "row_mode": "M", "values": []}
    assert list(S.with_place(s, {"row": ["A", "B"], "row_at": [1, 2]})) == ["key", "name", "order", "row", "row_at", "values"]
    assert S.with_place(s, {}) == {"key": "k", "name": "n", "order": 3, "values": []}


@needs_evidence
def test_the_viewer_hangs_a_record_where_the_definition_places_it():
    """The proof viewer and the definition share the placement: a record proved through an option of a row named
    as its group (Drive Mode / Continuous Shooting) hangs on that row in the viewer too."""
    d = definitions.load(A1)
    recs = pv.records(d, {})
    tabs = pv.menu(d, recs, Path("."))
    drive = next(g for t in tabs if t["tab"] == "Shooting" for g in t["groups"] if g["name"] == "Drive Mode")
    top = next(x for x in drive["rows"] if x["l"] == "Drive Mode")
    speed = next(s["key"] for s in d["settings"] if s["name"] == "Drive memory - continuous shooting speed")
    assert speed in top["recs"] and speed not in drive["extra"]
    hi = next(s["key"] for s in d["settings"] if s["name"] == "Hi(E-Shutter)")
    speeds = next(x for x in drive["rows"] if x["l"] == "Cont. Shooting Speed")
    assert [x["l"] for x in speeds["kids"] if hi in x["recs"]] == ["Hi (E-Shutter)"]


def test_the_a1s_rows_in_another_tab_as_on_the_camera():
    """The owner's case (2026-11-06): the Custom Key cells the definition keeps in Shooting, Focus and Playback hang on
    Setup's key settings' rows, Movie's Exposure Ctrl Type on the Movie menu's Shooting tab, Time Code Preset's parts
    on TC/UB there; what no path leads to a row of stays unplaced (the SDK's own setters, Preset Focus/Zoom)."""
    d = definitions.load(A1)
    by = {s["key"]: s for s in d["settings"]}
    assert {k: (by[k]["row_tab"], by[k]["row_group"], by[k]["row"]) for k in ("global:0x0436", "global:0x0441")} == {
        "global:0x0436": ("Setup", "Operation Customize", ["Custom Key/Dial Set."]),
        "global:0x0441": ("Setup", "Operation Customize", ["Custom Key Setting"])}
    assert (by["global:0x02b0"]["row_tab"], by["global:0x02b0"]["row_mode"], by["global:0x02b0"]["row"]) == ("Shooting", "Movie", ["Exposure Ctrl Type"])
    assert (by["global:0x0c48"]["row_tab"], by["global:0x0c48"]["row_group"]) == ("Shooting", "TC/UB")
    for k in ("global:0x10ff", "global:0x167c", "global:0x04e5"):
        assert "row" not in by[k], k
    for s in d["settings"]:
        assert ("row_tab" in s) <= ("row" in s) and s.get("row_tab") != s["tab"], s["key"]
        if "row_tab" in s:
            assert s["row_tab"] in d["tabs"] and "row_group" in s, s["key"]


@needs_evidence
def test_the_viewer_and_the_definition_hang_every_record_on_the_same_row():
    """One placement: every setting the definition places is on the same row of the same tab in the proof viewer, the
    sub-rows it grows from the proofs' paths (Recall Custom hold 1 under Reg. Custom Shoot Set, which the walk never
    opened) and the rows in another tab included, a Creative Look's parameters in the row's subsections, a Picture
    Profile's in the Picture Profile row's subsections (one per profile, the page under its option); a grown row is a
    heading of its own, with no walk frames."""
    d = definitions.load(A1)
    tabs = pv.menu(d, pv.records(d, {}), Path("."))
    where, made = {}, []

    def walk(nodes, path, tab):
        for n in nodes:
            for k in n["recs"]:
                where[k] = (tab, path + [n["l"]])
            for k in [k for sub in n.get("subs") or [] for k in sub["keys"]]:
                where[k] = (tab, path + [n["l"]], "sub")          # a family's records: the row's subsections
            if n.get("made"):
                made.append(n)
            walk(n["kids"], path + [n["l"]], tab)
    for t in tabs:
        for g in t["groups"]:
            walk(g["rows"], [], t["tab"])
    placed = [s for s in d["settings"] if "row" in s]

    def same(s, w):            # a family's subsection holds the row's own place, or the page under one of its options
        if not w or w[0] != s.get("row_tab", s["tab"]):
            return False
        if len(w) == 2:
            return w[1] == s["row"]
        return s["row"] == w[1] or (s["row"][:len(w[1])] == w[1] and s["row"][len(w[1])] == s.get("under_option"))
    assert placed and all(same(s, where.get(s["key"])) for s in placed)
    assert made and all(n["walk"] == [] and n["st"] == "proof" for n in made)
    hold = next(x for t in tabs if t["tab"] == "Shooting" for g in t["groups"] for x in g["rows"] if x["l"] == "Reg. Custom Shoot Set")
    assert "Recall Custom hold 1" in [k["l"] for k in hold["kids"]]


def test_the_tree_file_is_the_mappers_own():
    """The menu tree is private whole, beside the definition's evidence (decision 16), never in data/."""
    assert definitions.menu_tree_file(A1) == definitions.EVIDENCE_DIR / A1 / f"menu_tree_{A1}.json"
    assert not (definitions.data_dir(A1) / f"menu_tree_{A1}.json").exists()
    if definitions.menu_tree_file(A1).exists():
        assert json.loads(Path(definitions.menu_tree_file(A1)).read_text(encoding="utf-8"))["tabs"]


def test_an_option_named_by_its_place_in_the_list_is_that_option():
    """A path that names the row's option by its place (the White Balance grid "White Balance / grid 11", a Creative
    Look's "Creative Look / panel 12 / Shadows") puts the setting under that option of the row's own setting; a place
    past the options the menu names (a custom look the walk read by its base look's name) is the setting's first label
    no option names, then the next: Custom Look 1, 2."""
    looks = [[0, "ST(Standard)"], [1, "PT(Portrait)"], [10, "Custom Look 1"], [11, "Custom Look 2"]]
    opts = ["ST(Standard)", "PT (Portrait)", "PT(Portrait))", "ST(Standard)"]
    assert placement.indexed_option("Creative Look / panel 1 / Shadows", opts, looks) == "PT(Portrait)"
    assert placement.indexed_option("Creative Look / panel 2 / Shadows", opts, looks) == "Custom Look 1"
    assert placement.indexed_option("Creative Look / base 3 [Movie mode]", opts, looks) == "Custom Look 2"
    assert placement.indexed_option("Creative Look / panel 9", opts, looks) is None
    assert placement.indexed_option("Creative Look > Contrast", opts, looks) is None
    wb = [[0, "Auto"], [11, "C.Temp./Filter"], [13, "Custom 1"]]
    assert placement.indexed_option("White Balance / grid 1 [Movie mode]", ["Auto", "С.Temp./Filter", "Custom 1"], wb) \
        == "C.Temp./Filter"                                    # a Cyrillic C read for the Latin one


def test_the_a1s_white_balance_fine_tunes_and_creative_looks_sit_under_their_option_in_the_public_file():
    """The public definition alone (a fresh clone, CI), whose places are what is public of the menus: every WB
    fine-tune sits under its preset on the White Balance row ("AWB" being Auto), and every Creative Look parameter
    placed on the Creative Look row under its look (C1-C6 under Custom Look 1-6), stills and movie copies alike."""
    d = definitions.load_public(A1)
    wb = [s for s in d["settings"] if s["name"].startswith("WB fine-tune")]
    assert len(wb) == 73 and all(s.get("row") == ["White Balance"] for s in wb)
    for s in wb:
        preset = re.search(r"\(([^,)]+(?:: [^,)]+)?)", s["name"])[1]
        assert s["under_option"] == {"AWB": "Auto"}.get(preset, preset), s["name"]
    looks = [s for s in d["settings"] if s.get("group", "").startswith("Creative Look ") and s.get("row") == ["Creative Look"]]
    assert len(looks) >= 148
    for s in looks:
        want = s["group"].split()[-1]
        want = f"Custom Look {want[1]}" if re.fullmatch(r"C\d", want) else want
        assert s["under_option"].startswith(want), s["key"]


@needs_evidence
def test_the_a1s_white_balance_fine_tunes_and_creative_looks_sit_under_their_option():
    """On the a1 II: every WB fine-tune sits under its preset on the White Balance row (the one its name says, "AWB"
    being Auto), and every Creative Look parameter with a panel proof under its look on the Creative Look row (C1-C6
    under Custom Look 1-6), stills and movie copies alike."""
    d = definitions.load(A1)
    tree = datafiles.load_menu_tree(A1)                 # the mapper's own, as fromdata.places reads it
    got = placement.settings(d, tree)
    wb = [s for s in d["settings"] if s["name"].startswith("WB fine-tune")]
    assert len(wb) == 73 and all(got[s["key"]]["row"] == ["White Balance"] for s in wb)
    for s in wb:
        preset = re.search(r"\(([^,)]+(?:: [^,)]+)?)", s["name"])[1]
        assert got[s["key"]]["under_option"] == {"AWB": "Auto"}.get(preset, preset), s["name"]
    looks = [s for s in d["settings"] if s.get("group", "").startswith("Creative Look ") and s["key"] in got]
    assert len(looks) >= 148
    for s in looks:
        want = s["group"].split()[-1]
        want = f"Custom Look {want[1]}" if re.fullmatch(r"C\d", want) else want
        assert got[s["key"]]["row"] == ["Creative Look"] and got[s["key"]]["under_option"].startswith(want), s["key"]


PAGES = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Color", "pages": [
    {"page": "1/1", "group": "Color/Tone", "rows": [
        row("Tone"),
        row("Profile", row("P1", row("Gamma"), row("Knee", row("Mode"), row("Point"))), options=["Off", "P2", "P1"]),
        row("Look", options=["A", "B"]),
    ]}]}]}


def test_an_option_that_opens_a_page_places_its_rows_on_every_options_page():
    """A path that names an option of a row and steps below it ("Profile > P2 > Knee > Point") puts the setting on
    the page that option opens: the row, the option, the page's rows; row_at the row's number, the option's index (a
    family's column, P2 at 1), the page rows' places. Every option's page has the shape of the one the walk opened
    (P1's); a family's copy no path proved (P3) takes its proved copy's place under its own option, but not one whose
    option the row never offers (P4, unplaced); the setting keeps
    its group (no row_group). Where the tree opened no page (Look), the paths' rows make one shape, in their order, and
    the option's index is its place in the row's own setting's labels."""
    def s(key, name, group, menus=(), values=(), id_=1):
        x = {"key": key, "area": "global", "id": id_, "name": name, "tab": "Color", "group": group, "order": 9000,
             "values": [list(v) for v in values]}
        if menus:
            x["proved"] = {"run": "kit2_pass2", "date": "2026-10-29", "menu": list(menus)}
        return x
    d = {"model": "TEST", "tabs": ["Color"], "layouts": [{"model": "TEST", "firmware": "1.00"}],
         "camera": {"families": [{"prefix": "Profile P", "kind": "table"}]},
         "menu": [{"tab": "Color", "group": "Color/Tone", "label": x, "order": i} for i, x in enumerate(["Tone", "Profile", "Look"])],
         "settings": [s("global:0x0001", "Profile", "Color/Tone", ["Profile"], [[0, "Off"], [1, "P1"], [2, "P2"], [3, "P3"]], 1),
                      s("global:0x0010[0]", "Knee Point", "Profile P1", ["Profile > P1 > Knee > Point"], id_=16),
                      s("global:0x0010[1]", "Knee Point", "Profile P2", ["Profile > P2 > Knee > Point [Movie mode]"], id_=16),
                      s("global:0x0010[2]", "Knee Point", "Profile P3", id_=16),
                      s("global:0x0010[3]", "Knee Point", "Profile P4", id_=16),
                      s("global:0x0011[1]", "Gamma", "Profile P2", ["Profile > P2 > Gamma"], id_=17),
                      s("global:0x0002", "Look", "Color/Tone", ["Look"], [[0, "A"], [1, "B"]], 2),
                      s("global:0x0003", "Look Depth", "Color/Tone", ["Look > B > Depth"], id_=3),
                      s("global:0x0004", "Look Strength", "Color/Tone", ["Look > A > Strength"], id_=4)]}
    got = placement.settings(d, PAGES)
    assert got["global:0x0010[0]"] == {"row": ["Profile", "P1", "Knee", "Point"], "row_at": [1, 0, 1, 1], "under_option": "P1"}
    assert got["global:0x0010[1]"] == {"row": ["Profile", "P2", "Knee", "Point"], "row_at": [1, 1, 1, 1], "under_option": "P2"}
    assert got["global:0x0010[2]"] == {"row": ["Profile", "P3", "Knee", "Point"], "row_at": [1, 2, 1, 1], "under_option": "P3"}
    assert "global:0x0010[3]" not in got
    assert got["global:0x0011[1]"] == {"row": ["Profile", "P2", "Gamma"], "row_at": [1, 1, 0], "under_option": "P2"}
    assert got["global:0x0001"] == {"row": ["Profile"], "row_at": [1]}
    assert got["global:0x0003"] == {"row": ["Look", "B", "Depth"], "row_at": [2, 1, 0], "under_option": "B"}
    assert got["global:0x0004"] == {"row": ["Look", "A", "Strength"], "row_at": [2, 0, 1], "under_option": "A"}
    assert placement.option_page(placement.Tree(d, PAGES), "Color", "Profile > Tone > Gamma", lambda n: []) is None


def test_the_a1s_picture_profiles_sit_on_each_profiles_page():
    """On the a1 II every Picture Profile parameter, PP1 to PP11, sits on its profile's page under the Picture Profile
    row (Color/Tone): row ["Picture Profile", "PPn", the page's rows...], row_at the row's number, n - 1, the page's
    places, under_option "PPn", its group kept; the stills and movie copies of a parameter in one place. PP7-PP9,
    which the row never offers, stay unplaced."""
    d = definitions.load(A1)
    by = {s["key"]: s for s in d["settings"]}
    top = next(s for s in d["settings"] if s["name"] == "Picture Profile" and s["group"] == "Color/Tone")
    pp = [s for s in d["settings"] if re.fullmatch(r"Picture Profile PP\d+", s.get("group") or "")]
    offered = {lab for _, lab in top["values"]}
    assert len(pp) == 825
    assert all(("row" in s) == (s["group"].split()[-1] in offered) for s in pp)
    pp = [s for s in pp if "row" in s]
    assert len(pp) == 600
    page = {}
    for s in pp:
        n = int(s["group"].rsplit("PP", 1)[1])
        assert s["row"][:2] == ["Picture Profile", f"PP{n}"] and s["under_option"] == f"PP{n}", s["key"]
        assert s["row_at"][:2] == [top["row_at"][0], n - 1] and len(s["row_at"]) == len(s["row"]) >= 3, s["key"]
        assert "row_group" not in s and "row_tab" not in s, s["key"]
        base = re.sub(r" \((stills|movie)\)$", "", s["name"])
        page.setdefault(base, set()).add((tuple(s["row"][2:]), tuple(s["row_at"][2:])))
    assert all(len(v) == 1 for v in page.values()), {k: v for k, v in page.items() if len(v) > 1}
    for k in ("global:0x05af[0]", "global:0x05c5[0]", "global:0x05db[0]"):          # movie, stills, movie copy
        assert by[k]["row"] == ["Picture Profile", "PP1", "Black Gamma", "Level"] and by[k]["row_at"][2:] == [2, 1]
    assert all(k not in by["global:0x0b19[7]"] for k in ("row", "row_at", "under_option"))          # PP8: not offered
    assert by["global:0x0b19[9]"]["row"] == ["Picture Profile", "PP10", "Detail", "Adjust", "Hi-Light Detail"]
    assert by["global:0x0b19[9]"]["row_at"][1:] == [9, 8, 1, 5]
    order = sorted(page, key=lambda b: next(iter(page[b]))[1])
    assert order[:3] == ["Black Level", "Gamma", "Black Gamma Range"] and order[-1] == "Detail Adjust Hi Light Detail"
