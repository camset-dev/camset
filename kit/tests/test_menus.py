"""Each camera menu's own places (camera.menus, row_menus, row_places): kit/camkit/placement.py by_menu, the camera's
MENUS and HAND_PLACES hand tables (kit/writer/hand_tables.py, kit/writer/fromdata.py) and check_public's refusals.

Run: .venv/bin/python -m pytest kit/tests/test_menus.py -q
Made-up menu trees and settings; nothing talks to a camera.
"""
import copy
import json

import pytest

from camkit import definitions, placement
from writer import fromdata, hand_tables

import check_public
import menu_tree


def row(label, *kids, options=(), state="", why=""):
    return {"label": label, "state": state, "why": why, "options": list(options), "children": list(kids)}


def page(n, group, *rows):
    return {"page": n, "group": group, "rows": list(rows)}


# a camera with three menus: Stills (the tree's top level), Movie and S&Q, as kit/tools/menu_tree.py writes them
STILLS = [{"tab": "Shooting", "pages": [
    page("1/4", "Rec", row("Rec. Media Settings", row("Recording Media"), row("Recording Media"), row("Auto Switch")),
         row("Lens Compensation", row("Shading Comp."), row("Distortion Comp."))),
    page("2/4", "Drive Mode", row("Drive Mode"), row("Anti-flicker Set.", row("Anti-flicker Shoot."), row("Var. Shutter"))),
    page("3/4", "Exposure", row("Exposure Comp."), row("Exposure Std. Adjust", row("Multi"), row("Spot"))),
    page("4/4", "Color", row("Picture Profile", row("PP1", row("Black Level"), row("Gamma"))),
         row("Anti-dust Function", state="never", why="moves the sensor")),
]}]
MOVIE = [{"tab": "Shooting", "pages": [
    page("1/4", "Rec", row("Rec. Media Settings", row("Recording Media"), row("Recording Media"), row("Auto Switch")),
         row("Lens Compensation", row("Shading Comp."), row("Distortion Comp."), row("Breathing Comp."))),
    page("2/4", "TC/UB", row("Time Code Format"), row("Anti-flicker Set.", row("Var. Shutter"))),
    page("3/4", "Exposure", row("Exposure Comp."), row("Exposure Std. Adjust")),           # its rows never read
    page("4/4", "Color", row("Picture Profile"),                                          # its pages never read
         row("Anti-dust Function", state="never", why="moves the sensor")),
]}]
SQ = [{"tab": "Shooting", "pages": [                     # a page scan alone: top rows, nothing under them read
    page("1/3", "Rec", row("Rec. Media Settings"), row("Lens Compensation")),
    page("2/3", "TC/UB", row("Time Code Format"), row("Anti-flicker Set.")),
    page("3/3", "Exposure", row("Exposure Comp."), row("Exposure Std. Adjust")),
    page("4/4", "Color", row("Picture Profile"), row("Anti-dust Function", state="never")),
]}]
TREE = {"model": "TEST", "firmware": "1.00", "tabs": STILLS, "modes": [{"mode": "Movie", "tabs": MOVIE}, {"mode": "S&Q", "tabs": SQ}]}
MENUS = [{"name": "Still", "modes": ["Stills"]}, {"name": "Movie", "modes": ["Movie"]},
         {"name": "S&Q", "modes": ["S&Q", "Time-lapse"]}]
PP = [[1, "PP1"], [2, "PP2"], [3, "PP3"]]


def setting(key, name, group, *menus, **more):
    s = {"key": key, "area": "global", "id": int(key[-4:], 16), "name": name, "tab": "Shooting", "group": group,
         "order": 9000, "values": [], **more}
    if menus:
        s["proved"] = {"menu": list(menus)}
    return s


def doc(*settings):
    return {"model": "TEST", "tabs": ["Shooting"], "layouts": [{"model": "TEST", "firmware": "1.00"}], "menu": [
        {"tab": "Shooting", "group": g, "label": lab, "order": i} for i, (g, lab) in enumerate([
            ("Rec", "Rec. Media Settings"), ("Rec", "Lens Compensation"), ("Drive Mode", "Drive Mode"),
            ("Drive Mode", "Anti-flicker Set."), ("Exposure", "Exposure Comp."), ("Exposure", "Exposure Std. Adjust"),
            ("Color", "Picture Profile")])], "settings": list(settings)}


SETTINGS = [
    setting("global:0x0001", "Drive Mode", "Drive Mode", "Drive Mode"),                                  # Stills only
    setting("global:0x0002", "Time Code Format", "TC/UB", "Time Code Format [Movie mode]"),              # Movie's
    setting("global:0x0003", "Breathing Comp.", "Rec", "Lens Compensation > Breathing Comp. [Movie mode]"),
    setting("global:0x0004", "Shading Comp.", "Rec", "Lens Compensation > Shading Comp."),
    setting("global:0x0005", "Recording Media", "Rec", "Rec. Media Settings > Recording Media"),
    setting("global:0x0006", "Recording Media (Movie)", "Rec", "Rec. Media Settings > Recording Media#1"),
    setting("global:0x0007", "Var. Shutter", "Drive Mode", "Anti-flicker Set. > Var. Shutter"),
    setting("global:0x0008", "Anti-flicker Shoot.", "Drive Mode", "Anti-flicker Set. > Anti-flicker Shoot."),
    # a family: the live setting and its copy for each mode (copy_for), the movie copy proved in Movie mode
    setting("global:0x0010", "Exposure Comp.", "Exposure", "Exposure Comp.", copies=["global:0x0011", "global:0x0012"]),
    setting("global:0x0011", "Exposure Comp. (stills)", "Exposure", "Exposure Comp.", copy_of="global:0x0010", copy_for=["Stills"]),
    setting("global:0x0012", "Exposure Comp. (movie)", "Exposure", "Exposure Comp. [Movie mode]", copy_of="global:0x0010",
            copy_for=["Movie", "S&Q", "Time-lapse"]),
    setting("global:0x0013", "Multi", "Exposure", "Exposure Std. Adjust > Multi", copies=["global:0x0014"]),
    setting("global:0x0014", "Multi (movie)", "Exposure", "Exposure Std. Adjust > Multi [Movie mode]",
            copy_of="global:0x0013", copy_for=["Movie", "S&Q", "Time-lapse"]),
    # an option's page: the row's own setting, the page the walk read (PP1's) and the pages it did not (PP2's)
    setting("global:0x0020", "Picture Profile", "Color", "Picture Profile", values=PP),
    setting("global:0x0021", "Black Level", "Color", "Picture Profile > PP2 > Black Level"),
    setting("global:0x0022", "Gamma", "Color", "Picture Profile > PP1 > Gamma [Movie mode]", "Picture Profile > PP1 > Gamma"),
]


def by_key(d, tree=TREE, menus=MENUS, hand=None):
    return placement.by_menu(d, tree, menus, hand=hand)


def test_each_menu_holds_the_rows_its_own_tree_holds():
    """A row only one menu has is in that menu alone (Drive Mode in Still, Time Code Format in Movie and S&Q, whose
    page scan read it, Breathing Comp. in Movie, whose walk read it), and a row the menus share is in each that read it;
    a menu whose tree never read the rows under a row (S&Q here) holds none of them unless its own mode's proofs reach
    them: another menu's rows place nothing in it."""
    got = by_key(doc(*copy.deepcopy(SETTINGS)))
    assert got["global:0x0001"] == {"row_menus": ["Still"]}
    assert got["global:0x0002"] == {"row_menus": ["Movie", "S&Q"]}
    assert got["global:0x0003"] == {"row_menus": ["Movie"]}
    assert got["global:0x0004"] == {"row_menus": ["Still", "Movie"]}
    assert got["global:0x0008"] == {"row_menus": ["Still"]}                  # Movie's Anti-flicker Set. read without it


def test_a_shared_row_in_another_place_gets_that_menus_place_only():
    """Var. Shutter is Movie's first row under Anti-flicker Set., Stills' second, and Movie draws that row on its TC/UB
    page: Movie's place differs in its order and its group, so row_places holds Movie's; Still's is the setting's own,
    so it has none. The merged numbering of the top rows serves both: Rec. Media Settings 0, Lens Compensation 1,
    Drive Mode 2 (Stills'), Time Code Format 3 (Movie's), Anti-flicker Set. 4, ..."""
    got = by_key(doc(*copy.deepcopy(SETTINGS)))
    top = placement.settings(doc(*copy.deepcopy(SETTINGS)), TREE)
    assert top["global:0x0007"] == {"row": ["Anti-flicker Set.", "Var. Shutter"], "row_at": [4, 1]}
    assert got["global:0x0007"] == {"row_menus": ["Still", "Movie"], "row_places": {"Movie": {
        "row": ["Anti-flicker Set.", "Var. Shutter"], "row_at": [4, 0], "row_group": "TC/UB"}}}


def test_one_label_twice_in_one_place_is_each_its_own_row():
    got = by_key(doc(*copy.deepcopy(SETTINGS)))
    top = placement.settings(doc(*copy.deepcopy(SETTINGS)), TREE)
    assert top["global:0x0005"]["row_at"] == [0, 0] and top["global:0x0006"]["row_at"] == [0, 1]
    assert got["global:0x0005"] == got["global:0x0006"] == {"row_menus": ["Still", "Movie"]}


def test_a_copy_family_is_in_each_menu_its_own_or_its_copys_proofs_reach():
    """The live setting of a family is in a menu whose rows hold its row, or whose own proofs of a copy for that menu's
    modes (copy_for) reach it where the menu never read the rows (Movie's Exposure Std. Adjust); its copies carry
    nothing, they follow it."""
    got = by_key(doc(*copy.deepcopy(SETTINGS)))
    assert got["global:0x0010"] == {"row_menus": ["Still", "Movie", "S&Q"]}
    assert got["global:0x0013"] == {"row_menus": ["Still", "Movie"]}         # S&Q: no proof of its own there
    assert not {"global:0x0011", "global:0x0012", "global:0x0014"} & set(got)


def test_an_options_page_is_in_a_menu_that_read_it_or_proved_a_row_on_it():
    """PP2's Black Level sits on the page PP2 opens (the shape the walk read on PP1's): in Still, whose walk read it,
    and not in Movie, which never read Picture Profile's pages; Gamma, proved on PP1's page in Movie mode too, is in
    Movie as well, in the definition's order (Movie never read the page's order)."""
    got = by_key(doc(*copy.deepcopy(SETTINGS)))
    top = placement.settings(doc(*copy.deepcopy(SETTINGS)), TREE)
    assert top["global:0x0021"] == {"row": ["Picture Profile", "PP2", "Black Level"], "row_at": [7, 1, 0], "under_option": "PP2"}
    assert got["global:0x0021"] == {"row_menus": ["Still"]}
    assert got["global:0x0022"] == {"row_menus": ["Still", "Movie"]}


def test_a_menu_with_no_tree_holds_nothing_and_a_menu_list_with_none_gives_nothing():
    no_sq = {**TREE, "modes": [TREE["modes"][0]]}
    got = by_key(doc(*copy.deepcopy(SETTINGS)), no_sq)
    assert not any("S&Q" in v["row_menus"] for v in got.values())
    assert by_key(doc(*copy.deepcopy(SETTINGS)), menus=[]) == {}


def test_states_options_my_menu_items_and_page_counters_change_nothing():
    """Two trees that differ only in what the walk found the camera in (a row's state and the walk's reason where they do
    not change what it read, the sub-choices an option list was read on) and in what the owner put there (My Menu's
    item pages), and in their page counters, give the same places and menus. (Whether the walk read a row at all, which
    the camera's state can stop, is what the tree knows: a row it never read holds nothing below it.)"""
    base = copy.deepcopy(TREE)
    base["tabs"][0]["pages"][1]["rows"][0]["options"] = ["Single Shooting", "Continuous Shooting: Hi"]
    base["tabs"][0]["pages"][1]["rows"][0]["state"] = "walked"
    other = copy.deepcopy(base)

    def stir(rows):
        for r in rows:
            r["why"] = "the camera's state"
            if r["children"]:
                r["state"] = "submenu" if r["state"] else "greyed"
            r["options"] = [o.replace(": Hi", ": Mid") for o in r["options"]]
            stir(r["children"])
    for menu in [other] + other["modes"]:
        for t in menu["tabs"]:
            for i, pg in enumerate(t["pages"]):
                pg["page"] = f"{i + 7}/63"
                stir(pg["rows"])
        menu["tabs"].insert(0, {"tab": "My Menu", "pages": [page("1/63", "My Menu1", row("Drive Mode"), row("Gamma")),
                                                          page("2/63", "My Menu Setting", row("Add Item")),
                                                          page("3/63", "MyMenu 2", row("Time Code Run"))]})
    # proved in S&Q mode on a row no menu's own pages hold, only the owner's item page
    d = doc(*copy.deepcopy(SETTINGS), setting("global:0x0040", "Time Code Run", "TC/UB", "Time Code Run [S&Q mode]"))
    assert placement.settings(d, other) == placement.settings(d, base)
    assert by_key(d, other) == by_key(d, base) and by_key(d, base) == by_key(d)
    assert "global:0x0040" not in placement.settings(d, other)


def test_a_row_only_an_owners_item_page_holds_is_in_no_menu_by_it():
    """A setting proved in Movie and in S&Q mode, on a row the S&Q menu's own pages lack and only one of its My Menu
    item pages holds (an owner's item, decision 16): in the Movie menu alone, as with no item page."""
    tree = copy.deepcopy(TREE)
    sq = tree["modes"][1]["tabs"][0]["pages"]
    sq[1]["rows"] = [r for r in sq[1]["rows"] if r["label"] != "Time Code Format"]
    d = doc(setting("global:0x0002", "Time Code Format", "TC/UB", "Time Code Format [Movie mode]", "Time Code Format [S&Q mode]"))
    plain = by_key(copy.deepcopy(d), tree)
    assert plain["global:0x0002"] == {"row_menus": ["Movie"]}
    for name in ("My Menu1", "MyMenu1", "★My Menu1", "My Menu Page 1"):
        mine = copy.deepcopy(tree)
        mine["modes"][1]["tabs"].insert(0, {"tab": "My Menu", "pages": [page("1/9", name, row("Time Code Format"))]})
        assert by_key(copy.deepcopy(d), mine) == plain, name
    assert placement.item_page("My Menu1", "My Menu") and not placement.item_page("My Menu Setting", "My Menu")


def test_a_row_given_by_hand_is_placed_in_every_menu_that_has_it():
    """HAND_PLACES: a record a row's own function writes (here on Exposure Comp.'s row, another tab's row would do as
    well) and a row the walk can never read, seen on the camera (under Anti-dust Function, which no walk opens):
    placed there, in every menu whose tree has the row, the row under it taken from the hand row."""
    d = doc(*copy.deepcopy(SETTINGS), setting("global:0x0030", "Registered value", "Other settings", "Something 1"),
            setting("global:0x0031", "Seen by hand", "Other settings"))
    hand = {"global:0x0030": ["Shooting > Exposure Comp."], "global:0x0031": ["Shooting > Anti-dust Function > Shutter When Pwr OFF"]}
    top = placement.settings(d, TREE, None, placement.with_hand(hand))
    assert top["global:0x0030"] == {"row": ["Exposure Comp."], "row_at": [5], "row_group": "Exposure"}
    assert top["global:0x0031"] == {"row": ["Anti-dust Function", "Shutter When Pwr OFF"], "row_at": [8, 0], "row_group": "Color"}
    got = by_key(d, hand=hand)
    assert got["global:0x0030"] == {"row_menus": ["Still", "Movie", "S&Q"]}
    assert got["global:0x0031"] == {"row_menus": ["Still", "Movie", "S&Q"]}
    assert "global:0x0030" not in placement.settings(d, TREE)          # by its proof path alone: no row


def test_the_menus_table_and_hand_places_are_held_to_their_shape(tmp_path):
    def read(**tables):
        p = tmp_path / "t.json"
        p.write_text(json.dumps({"camera": "TEST_fw1.00", **tables}), encoding="utf-8")
        return hand_tables.read(p, "TEST_fw1.00")
    assert read(MENUS=MENUS)["MENUS"] == MENUS
    for bad, words in ((MENUS + [{"name": "Still", "modes": ["X"]}], "twice"), ([{"name": "A", "modes": []}], "names no mode"),
                       ([{"name": "A", "modes": ["Movie"], "tiles": "x"}], "'tiles'")):
        with pytest.raises(hand_tables.Refused) as e:
            read(MENUS=bad)
        assert words in str(e.value.code), words
    ok = {"global:0x04a2": {"row": "Setup > Anti-dust Function > Shutter When Pwr OFF"}}
    assert read(HAND_PLACES=ok)["HAND_PLACES"] == ok
    for bad, words in (({"0x04a2": ok["global:0x04a2"]}, "not a setting's key"),
                       ({"global:0x04a2": {"row": "Shutter When Pwr OFF"}}, "not its tab then"),
                       ({"global:0x04a2": {"row": "Setup > A", "why": "seen on the camera"}}, "private hand evidence"),
                       ({"global:0x04a2": {"row": "Setup > A", "run": "kit2_x"}}, "'run'")):
        with pytest.raises(hand_tables.Refused) as e:
            read(HAND_PLACES=bad)
        assert words in str(e.value.code), words


def test_a_hand_places_reason_is_the_private_hand_evidences(tmp_path, monkeypatch):
    """HAND_PLACES' public table holds the record and its row only; why a row is the record's (written by the row's own
    registration, seen on the camera) is evidence, kept in private/evidence/<model>_fw<fw>.hand.json under HAND_PLACES:
    the ILCE-1M2's pass puts it back beside the row, the plain pass takes it as its schema allows (a why, nothing else)."""
    from writer import hand_evidence
    key = "TEST_fw1.00"
    data, ev = tmp_path / "data", tmp_path / "evidence"
    (data / key).mkdir(parents=True)
    ev.mkdir()
    monkeypatch.setattr(definitions, "DATA", data)
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", ev)
    row = "Setup > Anti-dust Function > Shutter When Pwr OFF"
    (data / key / f"hand_tables_{key}.json").write_text(json.dumps({"camera": key, "HAND_PLACES": {"global:0x04a2": {"row": row}}}), encoding="utf-8")
    said = {"hand_format": 2, "camera": key, "tables": {"HAND_PLACES": {"global:0x04a2": {"why": "seen on the camera by its owner"}}}}
    (ev / f"{key}.hand.json").write_text(json.dumps(said), encoding="utf-8")
    whole, public = hand_tables.load(key), hand_tables.load(key, evidence=False)
    assert whole.HAND_PLACES["global:0x04a2"] == {"row": row, "why": "seen on the camera by its owner"}
    assert public.HAND_PLACES["global:0x04a2"] == {"row": row}
    assert hand_evidence.plain_problems(said, key, vars(public)) == []
    wrong = {**said, "tables": {"HAND_PLACES": {"global:0x04a2": {"why": "x", "row": "Setup > B"}}}}
    assert any("'row'" in x for x in hand_evidence.plain_problems(wrong, key, vars(public)))


CAMERA = {"memory_sets": {"modes": {"Stills": [1], "Movie": [2], "S&Q": [3], "Time-lapse": [4]}},
          "live_mode": {"key": "global:0x13bf", "modes": {"0": "Stills", "1": "Movie", "2": "S&Q", "3": "Time-lapse"}},
          "main_tiles": [{"name": "Stills", "tiles": []}, {"name": "Movie", "tiles": []}]}


def test_every_menu_names_modes_the_camera_has_and_tiles_it_holds():
    d = {**doc(), "camera": CAMERA}
    menus = [{**MENUS[0], "main_tiles": "Stills", "hover": "The menu with the switch on Still."}, MENUS[1], MENUS[2]]
    assert fromdata.camera_menus(d, menus) == menus
    assert fromdata.camera_menus(d, []) is None
    for bad, words in (([{"name": "A", "modes": ["Night"]}], "names the mode 'Night'"),
                       ([{"name": "A", "modes": ["Movie"]}, {"name": "B", "modes": ["Movie"]}], "in two menus"),
                       ([{"name": "A", "modes": ["Movie"], "main_tiles": "S&Q"}], "tile set 'S&Q'"),
                       ([MENUS[0], MENUS[1], {"name": "S&Q", "modes": ["S&Q"]}], "leaves the camera's mode 'Time-lapse' without a menu")):
        with pytest.raises(hand_tables.Refused) as e:
            fromdata.camera_menus(d, bad)
        assert words in str(e.value.code), words
    assert list(fromdata.with_menus({"model": "X", "main_tiles": [], "my_menu": {}}, menus)) == ["model", "main_tiles", "menus", "my_menu"]
    assert "menus" not in fromdata.with_menus({"model": "X", "menus": menus}, None)


def test_places_without_menus_are_todays_and_with_them_add_only_the_menus(tmp_path, monkeypatch):
    """fromdata.places with no menus gives exactly today's places (no row_menus, no row_places); with them, each placed
    setting gets its menus, its own place untouched. (camera.menus, and from_data's whole write with and without the
    MENUS table: test_from_data_writes_the_menus_from_the_tables_and_the_tree.)"""
    d = doc(*copy.deepcopy(SETTINGS))
    tree = tmp_path / "tree.json"
    tree.write_text(json.dumps(TREE), encoding="utf-8")
    monkeypatch.setattr(definitions, "menu_tree_file", lambda key: tree)
    monkeypatch.setattr(fromdata, "box_orders", lambda key: {})
    plain = fromdata.places(d)
    assert plain == placement.settings(d, TREE) and not any({"row_menus", "row_places"} & set(v) for v in plain.values())
    assert fromdata.places(d, None, {}) == plain
    with_menus = fromdata.places(d, MENUS)
    assert {k: {f: v[f] for f in v if f not in ("row_menus", "row_places")} for k, v in with_menus.items()} == plain
    assert with_menus["global:0x0001"]["row_menus"] == ["Still"]
    placed = fromdata.with_place(d["settings"][0], with_menus["global:0x0001"])
    at = list(placed).index("order")
    assert list(placed)[at + 1:at + 4] == ["row", "row_at", "row_menus"]


def test_check_public_refuses_what_a_menu_must_never_say():
    """camera.menus and each setting's row_menus and row_places hold names and places only: a row's state, an option
    list, a page counter or one of My Menu's item pages there is refused, as is a menu name no camera menu has."""
    d = {**doc(), "camera": {"menus": MENUS, "text": {}}, "settings": [
        {"key": "global:0x0001", "row": ["Drive Mode"], "row_at": [2], "row_menus": ["Still", "Movie"],
         "row_places": {"Movie": {"row": ["Drive Mode"], "row_at": [1]}}}]}
    assert check_public.menu_problems(d) == []
    bad = copy.deepcopy(d)
    bad["camera"]["menus"][0]["state"] = "walked"
    s = bad["settings"][0]
    s["row_menus"].append("Night")
    s["row_places"]["Movie"].update(options=["Off", "On"], state="greyed")
    s["row_places"]["Still"] = {"row": ["38/63"], "row_at": [0], "row_group": "My Menu1"}
    got = "\n".join(check_public.menu_problems(bad))
    for words in ("camera.menus[0] holds 'state'", "row_menus names 'Night'", "holds 'options'", "holds 'state'",
                  "'38/63' is a page counter", "'My Menu1' is one of My Menu's item pages"):
        assert words in got, words
    assert check_public.menu_problems({**doc(), "settings": [{"key": "k", "row_menus": ["Still"]}]}) == \
        ["k: row_menus or row_places without camera.menus", "k: row_menus names 'Still', no camera menu"]


def test_a_tree_takes_in_a_group_from_a_page_scan_never_the_owners_items(tmp_path, monkeypatch):
    """menu_tree.py --add: My Menu's own setting page from a page scan into a Stills menu written without it, a tab of
    its own where the scan has it, its rows as a page no crawl reached; the same group twice, a group the scan lacks
    and a page of the owner's items (its tab's name and a number) are refused."""
    scan = tmp_path / "scan"
    scan.mkdir()
    (scan / "model.json").write_text(json.dumps([
        {"page": "1/9", "breadcrumb": "My Menu > My Menu1", "rows": [{"slot": 0, "label": "Drive Mode"}]},
        {"page": "2/9", "breadcrumb": "My Menu > My Menu Setting", "rows": [{"slot": 0, "label": "Add Item"},
                                                                        {"slot": 1, "label": "Display From My Menu"}]},
        {"page": "3/9", "breadcrumb": "Shooting > Rec", "rows": [{"slot": 0, "label": "Rec. Media Settings"}]}]), encoding="utf-8")
    menu = copy.deepcopy({"tabs": STILLS})
    said = menu_tree.added(menu, scan, "My Menu", "My Menu Setting")
    assert [t["tab"] for t in menu["tabs"]] == ["My Menu", "Shooting"] and said
    assert [r["label"] for r in menu["tabs"][0]["pages"][0]["rows"]] == ["Add Item", "Display From My Menu"]
    assert menu["tabs"][0]["pages"][0]["rows"][1]["state"] == "seen"
    for group, words in (("My Menu Setting", "already"), ("Nothing", "holds no page"), ("My Menu1", "owner's own items")):
        with pytest.raises(SystemExit) as e:
            menu_tree.added(menu, scan, "My Menu", group)
        assert words in str(e.value.code), words


def test_records_that_differ_by_mode_on_one_row_are_kept_to_their_own_menus_by_the_help_guide():
    """The camera's Help Guide lists SteadyShot twice, a "still image" item and a "movie, slow&quick motion" one: of
    the records on that one row, the one proved in Movie mode goes to the Movie and S&Q menus, the one proved with no
    mode named (in the Still menu) to the Still menu; one proved both ways, from both rows, keeps every menu, as no item
    covers both; a row the guide lists once, or under one set of modes, is left as the trees give it."""
    rows = [page("1/1", "Image Stabilization", row("SteadyShot"), row("SteadyShot Adjust."))]
    tree = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Shooting", "pages": copy.deepcopy(rows)}],
            "modes": [{"mode": m, "tabs": [{"tab": "Shooting", "pages": copy.deepcopy(rows)}]} for m in ("Movie", "S&Q")]}
    d = {"model": "TEST", "tabs": ["Shooting"], "menu": [{"tab": "Shooting", "group": "Image Stabilization", "label": x, "order": i}
                                                         for i, x in enumerate(["SteadyShot", "SteadyShot Adjust."])],
         "settings": [setting("global:0x0001", "SteadyShot", "Image Stabilization", "SteadyShot"),
                      setting("global:0x0002", "SteadyShot (Movie)", "Image Stabilization", "SteadyShot [Movie mode]"),
                      setting("global:0x0003", "SteadyShot Adjust.", "Image Stabilization", "SteadyShot Adjust."),
                      setting("global:0x0004", "SteadyShot (both)", "Image Stabilization", "SteadyShot [Movie mode]", "SteadyShot")]}
    guide = [{"tab": "Shooting", "group": "Image Stabilization", "item": "SteadyShot", "modes": "still image"},
             {"tab": "Shooting", "group": "Image Stabilization", "item": "SteadyShot", "modes": "movie, slow&quick motion"},
             {"tab": "Shooting", "group": "Image Stabilization", "item": "SteadyShot Adjust.", "modes": "still image, movie, slow&quick motion"}]
    menus = [{**MENUS[0], "guide": ["still image"]}, {**MENUS[1], "guide": ["movie"]}, {**MENUS[2], "guide": ["slow&quick motion"]}]
    got = placement.by_menu(d, tree, menus, guide=guide)
    assert got["global:0x0001"] == {"row_menus": ["Still"]}
    assert got["global:0x0002"] == {"row_menus": ["Movie", "S&Q"]}
    assert got["global:0x0003"] == {"row_menus": ["Still", "Movie", "S&Q"]}
    assert got["global:0x0004"] == {"row_menus": ["Still", "Movie", "S&Q"]}
    assert placement.proof_modes(["SteadyShot", "SteadyShot [Movie mode]"], {"row": ["SteadyShot"]}, {"Stills", "Movie", "S&Q"}) == {"Stills", "Movie"}
    assert placement.by_menu(d, tree, menus)["global:0x0001"] == {"row_menus": ["Still", "Movie", "S&Q"]}       # no guide


def test_a_menus_place_says_what_differs_and_gives_the_settings_own_tab_back():
    """row_places holds what differs from the setting's own place, row and row_at together; where the setting's own place
    is in another tab or group and a menu's is in its own, that menu's place names its own tab and group (a field left
    out keeps the setting's own)."""
    s = {"tab": "Shooting", "group": "Drive Mode"}
    own = {"row": ["Custom Key/Dial Set."], "row_at": [5], "row_tab": "Setup", "row_group": "Operation Customize"}
    assert placement.place_differs(own, dict(own), s) == {}
    assert placement.place_differs(own, {**own, "row_at": [6]}, s) == {"row": ["Custom Key/Dial Set."], "row_at": [6]}
    assert placement.place_differs(own, {"row": ["Drive Mode"], "row_at": [2]}, s) == \
        {"row": ["Drive Mode"], "row_at": [2], "row_tab": "Shooting", "row_group": "Drive Mode"}


@pytest.mark.parametrize("proofs, menus", [
    # (a) Stills moved one record, Movie the other, and S&Q too: each in its own modes' menus, which never overlap
    ((["D-Range Optimizer"], ["D-Range Optimizer [Movie mode]", "D-Range Optimizer [S&Q mode]"]), (["Still"], ["Movie", "S&Q"])),
    # (a') the same with no proof in S&Q: a menu no proof names cannot be told apart, and the two stay one row in
    # every menu (one record's menus overlapping another's unequal would show the row twice there)
    ((["D-Range Optimizer"], ["D-Range Optimizer [Movie mode]"]), (["Still", "Movie", "S&Q"], ["Still", "Movie", "S&Q"])),
    # (b) both moved together in each mode: one row in every menu, as before
    ((["D-Range Optimizer", "D-Range Optimizer [Movie mode]"], ["D-Range Optimizer", "D-Range Optimizer [Movie mode]"]),
     (["Still", "Movie", "S&Q"], ["Still", "Movie", "S&Q"])),
])
def test_one_settings_records_proved_in_different_modes_are_each_kept_to_their_own(proofs, menus):
    """D-Range Optimizer kept in two records on one row: where each menu's mode moved one record alone, each keeps its
    own modes' menus; where a menu that holds them is named by no proof, or both moved in each mode, both stay in every
    menu, one row: their row_menus are equal, or apart, never overlapping."""
    rows = [page("1/1", "Color/Tone", row("D-Range Optimizer"))]
    tree = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Shooting", "pages": copy.deepcopy(rows)}],
            "modes": [{"mode": m, "tabs": [{"tab": "Shooting", "pages": copy.deepcopy(rows)}]} for m in ("Movie", "S&Q")]}
    d = {"model": "TEST", "tabs": ["Shooting"], "menu": [{"tab": "Shooting", "group": "Color/Tone", "label": "D-Range Optimizer", "order": 0}],
         "settings": [setting("global:0x0001", "D-Range Optimizer", "Color/Tone", *proofs[0]),
                      setting("global:0x0002", "D-Range Optimizer", "Color/Tone", *proofs[1])]}
    got = placement.by_menu(d, tree, MENUS)
    assert (got["global:0x0001"]["row_menus"], got["global:0x0002"]["row_menus"]) == menus


def test_a_row_given_by_hand_finds_the_second_of_two_rows_of_one_label_and_a_row_named_as_its_group():
    """Two rows of one label (Custom Key/Dial Set., a still and a movie row, in every menu): a record whose proofs went
    through the second takes it by "#1" in its row given by hand, and every menu shows both rows, each with its own
    record; a row named as its group ("Drive Mode") is found with its tab first."""
    rows = [page("1/2", "Operation Customize", row("Custom Key/Dial Set."), row("Custom Key/Dial Set."), row("Fn Menu Settings")),
            page("2/2", "Drive Mode", row("Drive Mode"))]
    tree = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Setup", "pages": copy.deepcopy(rows)}],
            "modes": [{"mode": m, "tabs": [{"tab": "Setup", "pages": copy.deepcopy(rows)}]} for m in ("Movie", "S&Q")]}
    s = lambda k, n, *m: {**setting(k, n, "Operation Customize", *m), "tab": "Setup"}          # noqa: E731
    d = {"model": "TEST", "tabs": ["Setup"], "menu": [], "settings": [
        s("global:0x0001", "Custom Key (Still): AEL Button", "Custom Key/Dial Set."),
        s("global:0x0002", "Custom Key (Movie): AEL Button", "Custom Key/Dial Set."),
        s("global:0x0003", "A record the row writes", "Something 1")]}
    hand = {"global:0x0002": ["Setup > Custom Key/Dial Set.#1"], "global:0x0003": ["Setup > Drive Mode"]}
    top = placement.settings(d, tree, None, placement.with_hand(hand))
    assert top["global:0x0001"]["row_at"] == [0] and top["global:0x0002"]["row_at"] == [1]
    assert top["global:0x0001"]["row"] == top["global:0x0002"]["row"] == ["Custom Key/Dial Set."]
    assert top["global:0x0003"]["row"] == ["Drive Mode"]
    got = placement.by_menu(d, tree, MENUS, hand=hand)
    assert all(got[k] == {"row_menus": ["Still", "Movie", "S&Q"]} for k in ("global:0x0001", "global:0x0002", "global:0x0003"))


def test_the_camera_file_may_word_the_menu_buttons_label():
    """camera.text.menus_label and menus_hover, the words before the editor's buttons for the camera's menus: optional,
    never empty."""
    from jsonschema import Draft202012Validator
    text = json.loads((definitions.ROOT / "schemas" / "camera.schema.json").read_text(encoding="utf-8"))["properties"]["text"]
    v = Draft202012Validator(text)
    assert not list(v.iter_errors({"menus_label": "Camera menu:", "menus_hover": "The camera's menu in each mode."}))
    assert list(v.iter_errors({"menus_label": ""}))


def test_one_reading_of_a_proofs_context_for_placement_and_the_report():
    """A proof's context is read one way across the kit: its items split at "," or ";" before a space, each with its
    trailing parenthetical left out; the mode a path was proved in is the one an item names, and the report's state
    items are the same items. A Movie proof written "[Movie mode; Log Shooting On]" or "[Movie mode (dial set with the
    menu)]" is a Movie proof, in the Movie menu alone, as "[Movie mode]" is."""
    import pass2_report
    every = ["Stills", "Movie", "S&Q", "Time-lapse"]
    assert placement.context_items("Movie mode (dial set with the menu); PP10 Gamma: Movie") == ["Movie mode", "PP10 Gamma: Movie"]
    assert placement.context_items("File Format: SLOT 1 JPEG, SLOT 2 RAW") == ["File Format: SLOT 1 JPEG", "SLOT 2 RAW"]
    for said, mode in (("Movie mode; Log Shooting On", "Movie"), ("Movie mode (dial set with the menu)", "Movie"),
                       ("Movie mode (dial set with the menu), Picture Profile copies apart", "Movie"),
                       ("S&Q mode (Time-lapse)", "S&Q"), ("Stills, Set with Menu", "Stills"),
                       ("Shoot Mode A (dial set with the menu)", None), ("PP10 Gamma: Movie", None)):
        assert placement.mode_of(f"Row [{said}]", every) == mode, said
        assert pass2_report.state_items({"context": said}) == placement.context_items(said), said
    for said in ("Movie mode", "Movie mode; Log Shooting On", "Movie mode (dial set with the menu)"):
        d = doc(setting("global:0x0003", "Breathing Comp.", "Rec", f"Lens Compensation > Breathing Comp. [{said}]"))
        assert by_key(d)["global:0x0003"] == {"row_menus": ["Movie"]}, said


@pytest.mark.parametrize("table", ["renamed", "none"])
def test_with_no_menu_tree_the_definitions_menus_stay_as_they_are(tmp_path, monkeypatch, table):
    """A fresh clone or CI (no private menu tree): from_data cannot rebuild a setting's menus, so it touches none of
    them, camera.menus included, whatever the MENUS table says now (a menu renamed, or the table gone): the
    definition's menus, row_menus and row_places stay exactly as they were, and check_public finds nothing."""
    import shutil
    import schema_update as S
    key = definitions.key(json.loads((definitions.ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8")))
    data = tmp_path / "data"
    shutil.copytree(definitions.data_dir(key), data / key)
    monkeypatch.setattr(definitions, "DATA", data)
    monkeypatch.setattr(S.help_files, "OWN", data)
    monkeypatch.setattr(definitions, "menu_tree_file", lambda k: tmp_path / "no_tree.json")
    hand = data / key / f"hand_tables_{key}.json"
    tables = json.loads(hand.read_text(encoding="utf-8")) if hand.exists() else {"camera": key}
    if table == "renamed":
        tables["MENUS"] = [{"name": "Photo", "modes": ["Stills"]}, {"name": "Movie", "modes": ["Movie"]},
                           {"name": "S&Q", "modes": ["S&Q", "Time-lapse"]}]
    else:
        tables.pop("MENUS", None)
    hand.write_text(json.dumps(tables), encoding="utf-8")
    doc = json.loads((definitions.ROOT / "editor" / "definitions" / f"{key}.json").read_text(encoding="utf-8"))
    menus = [{"name": "Still", "modes": ["Stills"]}, {"name": "Movie", "modes": ["Movie"]}, {"name": "S&Q", "modes": ["S&Q", "Time-lapse"]}]
    doc["camera"]["menus"] = menus
    for s in doc["settings"]:          # the definition's own menus out, with menus or without: the made-up ones below
        s.pop("row_menus", None), s.pop("row_places", None)
    placed = [s for s in doc["settings"] if s.get("row") and not s.get("copy_of")]
    rows = {}                                  # one row in the editor (one name, one place): one set of menus
    for s in placed:
        k = rows.setdefault((s["name"], tuple(s["row"]), tuple(s["row_at"]), s.get("under_option")), len(rows))
        s["row_menus"] = ["Still", "Movie"] if k % 2 else ["Still"]
    placed[0]["row_places"] = {"Still": {"row": placed[0]["row"], "row_at": [0] + placed[0]["row_at"][1:]}}
    placed[0]["proved"] = {"menu": [" > ".join(placed[0]["row"])]}          # evidence there, the tree not
    was = {s["key"]: {f: s.get(f) for f in ("row_menus", "row_places")} for s in doc["settings"]}
    got = S.from_data(doc)
    assert got["camera"]["menus"] == menus
    assert {s["key"]: {f: s.get(f) for f in ("row_menus", "row_places")} for s in got["settings"]} == was
    assert check_public.menu_problems(got) == []


def test_a_menus_place_always_carries_its_row_and_row_at():
    """A menu's place that differs from the setting's own only in its group (a top row Movie draws on its TC/UB page)
    still names its row and row_at, as the definition's schema and the editor's reader require: a written definition
    the hooks would refuse is never made."""
    from jsonschema import Draft202012Validator
    s = {"tab": "Shooting", "group": "Drive Mode"}
    own = {"row": ["Anti-flicker Set."], "row_at": [4]}
    assert placement.place_differs(own, {**own, "row_group": "TC/UB"}, s) == {"row": ["Anti-flicker Set."], "row_at": [4], "row_group": "TC/UB"}
    assert placement.place_differs(own, {**own, "under_option": "Var. Shutter"}, s) == \
        {"row": ["Anti-flicker Set."], "row_at": [4], "under_option": "Var. Shutter"}
    d = doc(setting("global:0x0009", "Anti-flicker Set.", "Drive Mode", "Anti-flicker Set."))
    got = by_key(d)["global:0x0009"]
    assert got["row_places"]["Movie"] == {"row": ["Anti-flicker Set."], "row_at": [4], "row_group": "TC/UB"}
    schema = json.loads((definitions.ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))
    v = Draft202012Validator(schema["$defs"]["setting"]["properties"]["row_places"])
    for m, p in got["row_places"].items():
        assert not list(v.iter_errors({m: p})), (m, p)


def test_a_proof_whose_context_is_silent_takes_the_cameras_own_mode_for_placement_alone(tmp_path, monkeypatch):
    """Where a proof's context names no mode, placement takes the camera's own: the live-mode record (the camera file's
    live_mode) in its base download, read once and kept in the camera's cache, written by the writer into the proof's
    evidence (proved.menu_modes, writer/proofs.with_menu_modes) and read from there alone. A silent proof whose base
    download says Movie is its record's proof in the Movie menu too, where that menu never read the rows under the row;
    one whose base says Stills, or whose context names a mode, gives none; one whose base download is gone gives
    no mode at all (an empty list). The report's
    rows, and so what they credit, stay as the contexts give them, and proofs.jsonl is not rewritten."""
    import pass2_report
    from camkit import camset, live_modes, paths
    from writer import proofs as writer_proofs
    key = paths.A1II
    lm = json.loads(definitions.camera_file(key).read_text(encoding="utf-8"))["live_mode"]
    section, rid = (0, int(lm["key"].split("0x")[1], 16))
    code = {v: int(k) for k, v in lm["modes"].items()}
    cs = camset.read(definitions.sample(definitions.load(key)))
    run = tmp_path / key / "kit2_pass2"
    (run / "dat").mkdir(parents=True)
    for name, mode in (("00001_movie.DAT", "Movie"), ("00002_stills.DAT", "Stills")):
        raw = code[mode].to_bytes(cs.get(section, rid).size, "little", signed=True)
        (run / "dat" / name).write_bytes(camset.with_values(cs, {(section, rid): raw}))
    line = {"kind": "list", "index": [0], "label": "x", "dat": "00009_after.DAT"}
    lines = [{**line, "path": ["Exposure Std. Adjust", "Spot"], "base": "00001_movie.DAT",
              "changes": [{"key": "global:0x0031", "before": 0, "after": 1}]},
             {**line, "path": ["Exposure Std. Adjust", "Multi"], "base": "00002_stills.DAT",
              "changes": [{"key": "global:0x0032", "before": 0, "after": 1}]},
             {**line, "path": ["Exposure Std. Adjust", "Spot"], "base": "00001_movie.DAT", "context": "S&Q mode",
              "changes": [{"key": "global:0x0033", "before": 0, "after": 1}]},
             {**line, "path": ["Exposure Std. Adjust", "Center"], "base": "00003_gone.DAT",
              "changes": [{"key": "global:0x0034", "before": 0, "after": 1}]}]
    text = "".join(json.dumps(x) + "\n" for x in lines)
    (run / "proofs.jsonl").write_text(text, encoding="utf-8")
    monkeypatch.setattr(live_modes, "CACHE", tmp_path / "live_mode.json")
    rows = [pass2_report.row_name(r) for r in pass2_report.report_proofs(run)[0]]
    assert rows == ["Exposure Std. Adjust > Spot", "Exposure Std. Adjust > Multi", "Exposure Std. Adjust > Spot [S&Q mode]",
                    "Exposure Std. Adjust > Center"]
    assert pass2_report.silent_modes(run, save=False) == {("global:0x0031", ("Exposure Std. Adjust", "Spot")): {"Movie"},
                                                           ("global:0x0032", ("Exposure Std. Adjust", "Multi")): {"Stills"},
                                                           ("global:0x0034", ("Exposure Std. Adjust", "Center")): set()}
    assert not (tmp_path / "live_mode.json").exists()                                    # a dry run keeps nothing
    assert pass2_report.silent_modes(run) and len(json.loads((tmp_path / "live_mode.json").read_text(encoding="utf-8"))["codes"]) == 2
    monkeypatch.setattr(camset, "parse", lambda *a, **k: (_ for _ in ()).throw(AssertionError("read again")))
    assert pass2_report.silent_modes(run)                                                 # from the cache
    assert (run / "proofs.jsonl").read_text(encoding="utf-8") == text
    d = doc(setting("global:0x0031", "Spot", "Exposure", "Exposure Std. Adjust > Spot"),
            setting("global:0x0032", "Multi", "Exposure", "Exposure Std. Adjust > Multi"),
            setting("global:0x0034", "Center", "Exposure", "Exposure Std. Adjust > Center"))
    assert writer_proofs.with_menu_modes(d, run) == 2
    by = {s["key"]: s for s in d["settings"]}
    assert by["global:0x0031"]["proved"]["menu_modes"] == {"Exposure Std. Adjust > Spot": ["Movie"]}
    assert "menu_modes" not in by["global:0x0032"]["proved"]                           # the Still menu's: nothing to keep
    assert by["global:0x0034"]["proved"]["menu_modes"] == {"Exposure Std. Adjust > Center": []}          # gone: no mode
    from camkit import definitions as D
    assert D.lean_proof(by["global:0x0031"]["proved"]).keys() <= {"values", "shared", "sampled"}          # never public
    assert by_key(copy.deepcopy(d))["global:0x0031"] == {"row_menus": ["Still"]}         # the menus as by the paths alone
    modes = placement.menu_modes_of(d)
    assert placement.with_modes(placement.proof_paths, modes)(by["global:0x0031"]) == ["Exposure Std. Adjust > Spot [Movie mode]"]
    got = placement.by_menu(d, TREE, MENUS, modes=modes)
    assert got["global:0x0031"] == {"row_menus": ["Still", "Movie"]} and got["global:0x0032"] == {"row_menus": ["Still"]}
    from writer import copies
    assert [copies.row_mode(r) for r in rows[:3]] == ["Stills", "Stills", "S&Q"]          # the writer reads rows alike
    assert copies.row_mode("ISO [Movie mode (dial set with the menu)]") == "Movie"


def test_a_definition_written_with_proofs_modes_is_rebuilt_alike_without_the_runs(tmp_path, monkeypatch):
    """The modes of the proofs whose context names none are evidence, in each proof: a definition written with them is
    rebuilt from data/ and private/ alone, with an empty runs folder and never a look at the runs, the same text twice,
    through the split into public file and evidence and back; and the top-level place takes them too (a row only
    Movie's and S&Q's menus have, proved silently in S&Q, is S&Q's, not the first mode's that has it)."""
    import pass2_report
    import schema_update as S
    monkeypatch.setattr(pass2_report, "silent_modes", lambda *a, **k: (_ for _ in ()).throw(AssertionError("read the runs")))
    key = "TEST_fw1.00"
    data = tmp_path / "data"
    (data / key).mkdir(parents=True)
    camera = {"model": "TEST", **CAMERA, "main_tiles": [{"name": "Stills", "tiles": []}, {"name": "Movie", "tiles": []}]}
    (data / key / f"camera_{key}.json").write_text(json.dumps(camera), encoding="utf-8")
    (data / key / f"hand_tables_{key}.json").write_text(json.dumps({"camera": key, "MENUS": MENUS}), encoding="utf-8")
    tree = tmp_path / "tree.json"
    tree.write_text(json.dumps(TREE), encoding="utf-8")
    monkeypatch.setattr(definitions, "DATA", data)
    monkeypatch.setattr(S.help_files, "OWN", data)
    monkeypatch.setattr(definitions, "menu_tree_file", lambda k: tree)
    monkeypatch.setattr(fromdata, "box_orders", lambda k: {})
    spot = setting("global:0x0031", "Spot", "Exposure", "Exposure Std. Adjust > Spot")
    spot["proved"]["menu_modes"] = {"Exposure Std. Adjust > Spot": ["Movie"]}
    tc = setting("global:0x0035", "Time Code Format", "TC/UB", "Time Code Format")
    tc["proved"]["menu_modes"] = {"Time Code Format": ["S&Q"]}
    d = doc(*copy.deepcopy(SETTINGS), spot, tc)
    first = S.from_data(copy.deepcopy(d))
    by = {s["key"]: s for s in first["settings"]}
    assert by["global:0x0031"]["row_menus"] == ["Still", "Movie"]
    assert by["global:0x0035"]["row_mode"] == "S&Q" and by["global:0x0035"]["row_menus"] == ["Movie", "S&Q"]
    public, evidence = definitions.split(first)
    assert not any("menu_modes" in (s.get("proved") or {}) for s in public["settings"])
    again = S.from_data(definitions.merge(json.loads(json.dumps(public)), json.loads(json.dumps(evidence))))
    assert definitions.text(again) == definitions.text(first)
    plain = copy.deepcopy(d)
    for s in plain["settings"]:
        (s.get("proved") or {}).pop("menu_modes", None)
    by = {s["key"]: s for s in S.from_data(plain)["settings"]}
    assert by["global:0x0031"]["row_menus"] == ["Still"] and by["global:0x0035"]["row_mode"] == "Movie"

def test_a_main_tile_never_shows_an_expert_only_setting_but_a_fractions_parts():
    """The editor's Compare lists Main's settings among those shown outside Expert mode: a tile's own key (keys,
    memory_keys) naming an Expert-only setting is refused in one plain sentence; a fraction tile's two parts may be
    Expert-only (the a1 II's Shutter Speed tile, the shutter speed's numerator and denominator), and the a1 II's own
    Main tiles stand."""
    d = {"settings": [{"key": "global:0x0001", "name": "ISO"}, {"key": "set:0x0002", "name": "Shutter speed: numerator", "expert": True},
                      {"key": "set:0x0003", "name": "Shutter speed: denominator (1/x)", "expert": True}],
         "camera": {"main_tiles": [{"name": "Stills", "tiles": [
             {"caption": "ISO", "kind": "keys", "keys": ["global:0x0001"]},
             {"caption": "Shutter Speed", "kind": "fraction", "numerator_key": "set:0x0002", "denominator_key": "set:0x0003"}]}]}}
    assert fromdata.main_tile_refusal(d) is None
    d["camera"]["main_tiles"][0]["tiles"].append({"caption": "Raw", "kind": "live_or_memory", "keys": [], "memory_keys": ["set:0x0002"]})
    why = fromdata.main_tile_refusal(d)
    assert "the Stills page's tile 'Raw' shows set:0x0002 (Shutter speed: numerator)" in why and "Expert mode only" in why
    pub = json.loads((definitions.ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    assert fromdata.main_tile_refusal(pub) is None


def test_the_writer_stops_on_a_main_tile_that_shows_an_expert_only_setting(tmp_path, monkeypatch):
    """Through from_data: a camera file whose Main tile shows an Expert-only setting as its own key stops the write in
    one plain sentence naming the camera file, the tile and the setting, and what to do."""
    import shutil
    import schema_update as S
    pub = json.loads((definitions.ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    key = definitions.key(pub)
    data = tmp_path / "data"
    shutil.copytree(definitions.data_dir(key), data / key)
    monkeypatch.setattr(definitions, "DATA", data)
    monkeypatch.setattr(S.help_files, "OWN", data)
    cam = data / key / f"camera_{key}.json"
    c = json.loads(cam.read_text(encoding="utf-8"))
    c["main_tiles"][0]["tiles"].append({"caption": "Numerator", "kind": "keys", "keys": ["set:0x0180@290"]})
    cam.write_text(json.dumps(c), encoding="utf-8")
    with pytest.raises(hand_tables.Refused) as e:
        S.from_data(pub)
    said = str(e.value.code)
    assert f"camera_{key}.json" in said and "tile 'Numerator' shows set:0x0180@290" in said and "take the key off the tile" in said
    # on no row, or on Camera Set. Memory's row given by hand (HAND_PLACES), which counts as none
    assert "it stands on no camera row" in said and "its name holds 'numerator'" in said and "RECORD_FIXES" in said


def _test_camera(tmp_path, monkeypatch, tiles=()):
    """A made-up camera TEST_fw1.00 in data/ of the test's own, its MENUS, the made-up tree TREE on this computer, and
    the given Movie Main tiles; returns schema_update."""
    import schema_update as S
    key = "TEST_fw1.00"
    data = tmp_path / "data"
    (data / key).mkdir(parents=True)
    camera = {"model": "TEST", **CAMERA, "main_tiles": [{"name": "Stills", "tiles": []}, {"name": "Movie", "tiles": list(tiles)}]}
    (data / key / f"camera_{key}.json").write_text(json.dumps(camera), encoding="utf-8")
    (data / key / f"hand_tables_{key}.json").write_text(json.dumps({"camera": key, "MENUS": MENUS}), encoding="utf-8")
    tree = tmp_path / "tree.json"
    tree.write_text(json.dumps(TREE), encoding="utf-8")
    monkeypatch.setattr(definitions, "DATA", data)
    monkeypatch.setattr(S.help_files, "OWN", data)
    monkeypatch.setattr(definitions, "menu_tree_file", lambda k: tree)
    monkeypatch.setattr(fromdata, "box_orders", lambda k: {})
    return S


def places_of(d):
    return {s["key"]: {f: s.get(f) for f in fromdata.PLACE_KEYS} for s in d["settings"]}


def test_a_definition_read_without_its_proof_paths_keeps_every_place_whatever_proofs_the_pass_adds(tmp_path, monkeypatch):
    """With a menu tree on the computer, a write from a definition read without its proof paths (its evidence not
    there) keeps every setting's place and the camera's menus as the definition has them, though the pass gives a few
    settings proof paths: the writer never takes a place from a setting for want of evidence it cannot see (2026-11-20:
    a made-up pass of three rows took the row off 1,676 settings). The places are rebuilt where the definition as read
    held proof paths, and a row no path places then goes (a stale one, on the mapper's computer), or where it held no
    place at all (a new camera's first pass places what its proofs reach)."""
    S = _test_camera(tmp_path, monkeypatch)
    whole = S.from_data(doc(*copy.deepcopy(SETTINGS)))                  # the mapper's write: places from the paths
    assert fromdata.places_rebuilt(whole)
    public, _ = definitions.split(whole)                                  # read without its evidence: no path
    assert not fromdata.places_rebuilt(public) and places_of(public) == places_of(whole)
    read = copy.deepcopy(public)
    read["settings"][0]["proved"] = {"menu": ["Drive Mode"]}             # the pass proves one row
    kept = S.from_data(copy.deepcopy(read), fromdata.places_rebuilt(public))
    assert places_of(kept) == places_of(whole) and kept["camera"]["menus"] == whole["camera"]["menus"]
    # the same read with its evidence: every place rebuilt, a row neither a path nor the tree reaches gone (Breathing
    # Comp., Movie's alone, whose path was its only way there)
    rebuilt = {s["key"]: s for s in S.from_data(copy.deepcopy(read), True)["settings"]}
    assert rebuilt["global:0x0001"]["row"] == ["Drive Mode"] and "row" not in rebuilt["global:0x0003"]
    # a new camera's first pass: no place and no path as read, the pass's one proof placed
    first = doc(*[{k: v for k, v in s.items() if k != "proved"} for s in copy.deepcopy(SETTINGS)])
    assert fromdata.places_rebuilt(first)
    first["settings"][0]["proved"] = {"menu": ["Drive Mode"]}
    got = {s["key"]: s for s in S.from_data(first, True)["settings"]}
    assert got["global:0x0001"]["row"] == ["Drive Mode"] and got["global:0x0001"]["row_menus"] == ["Still"]


def test_a_main_tile_whose_setting_lost_its_row_in_this_write_says_so_not_to_take_the_key_off(tmp_path, monkeypatch):
    """Where a Main tile's setting is Expert-only because it has no row in this write (no proof path of it here) and its
    name holds the camera's word "Record", which reads as a mapping word on no row, the refusal says that and what to
    do, never "take the key off the tile": the camera file is not the cause. With its proof path the write stands."""
    tile = {"caption": "Record Setting", "kind": "keys", "keys": ["global:0x0030"]}
    S = _test_camera(tmp_path, monkeypatch, [tile])
    rec = setting("global:0x0030", "Record Setting (XAVC S 4K, 60p)", "Rec", row=["Rec. Media Settings"], row_at=[0])
    with pytest.raises(hand_tables.Refused) as e:
        S.from_data(doc(*copy.deepcopy(SETTINGS), copy.deepcopy(rec)))
    said = str(e.value.code)
    assert said.startswith("TEST_fw1.00: the Movie page's tile 'Record Setting' shows global:0x0030")
    assert "no proof path of it is here" in said and "'Record'" in said and "take the key off" not in said
    rec["proved"] = {"menu": ["Rec. Media Settings"]}
    got = {s["key"]: s for s in S.from_data(doc(*copy.deepcopy(SETTINGS), rec))["settings"]}
    assert got["global:0x0030"]["row"] == ["Rec. Media Settings"] and not got["global:0x0030"].get("expert")


def test_a_camera_section_without_its_menus_takes_them_from_menus_while_the_places_stay(tmp_path, monkeypatch):
    """Where the places stay as they are (read without the proof paths, or no menu tree here) and the camera section
    comes without its menus (rebuilt from the camera file: an old definition brought up to date) while the settings
    keep their row_menus, the menus come from the MENUS table, which is public: never settings naming menus the
    definition lists none of. A menu the settings name and MENUS does not stops the write, in plain words."""
    S = _test_camera(tmp_path, monkeypatch)
    whole = S.from_data(doc(*copy.deepcopy(SETTINGS)))
    public = copy.deepcopy(definitions.split(whole)[0])          # split shares the camera section with the whole
    public["camera"].pop("menus")
    got = S.from_data(copy.deepcopy(public))
    assert got["camera"]["menus"] == whole["camera"]["menus"] and places_of(got) == places_of(whole)
    public["settings"][0]["row_menus"] = ["Photo"]
    with pytest.raises(hand_tables.Refused) as e:
        S.from_data(public)
    said = str(e.value.code)
    assert said.startswith("TEST_fw1.00: ") and "'Photo'" in said and "MENUS" in said


def test_a_row_the_walk_found_a_notice_on_takes_no_options_from_its_twins_walk(tmp_path):
    """menu_tree.py: the crawl's map keeps one row per label path, so of two top rows of one label (the S&Q menu's two
    Shoot Mode rows) a row the walk found a notice on, never opening it, takes none of the options its twin's walk read;
    the walked one keeps them."""
    scan, crawl = tmp_path / "scan", tmp_path / "crawl"
    scan.mkdir()
    crawl.mkdir()
    (scan / "model.json").write_text(json.dumps([{"page": "8/59", "breadcrumb": "Shooting > Shooting Mode",
                                                   "rows": [{"slot": 3, "label": "Shoot Mode"}, {"slot": 4, "label": "Shoot Mode"}]}]),
                                     encoding="utf-8")
    (crawl / "rows.jsonl").write_text(
        json.dumps({"page": "8/59", "slot": 3, "label": "Shoot Mode", "outcome": "walked", "kind": "list"}) + "\n" +
        json.dumps({"page": "8/59", "slot": 4, "label": "Shoot Mode", "outcome": "notice", "kind": "notice"}) + "\n", encoding="utf-8")
    (crawl / "map.json").write_text(json.dumps({"rows": [{"path": ["Shoot Mode"], "kind": "list", "options": [
        {"index": 0, "label": "Program Auto"}, {"index": 1, "label": "Manual Exposure"}]}]}), encoding="utf-8")
    menu = menu_tree.tree(scan, [crawl], "TEST_fw1.00", "S&Q")
    first, second = menu["tabs"][0]["pages"][0]["rows"]
    assert first["options"] == ["Program Auto", "Manual Exposure"] and first["state"] == "walked"
    assert second["state"] == "info" and "options" not in second and second["kind"] == "notice"


def test_two_rows_the_camera_tells_apart_by_an_icon_alone_are_labelled_with_its_words(tmp_path, monkeypatch, capsys):
    """Setup's two Custom Key/Dial Set. rows (a still camera's icon, a movie camera's) read alike everywhere but on the
    camera: ROW_ICONS gives each icon's words by the row's path ("#1" the second), and the definition's label for such
    a row is "label (words)", in its own place and in every menu's, a row under it named as before. The tree's matching
    by label and place is untouched (the movie records still hang on "#1"); a row of a label no other row stands
    beside keeps its label whatever the table says, and an entry that named no such row is said."""
    S = _test_camera(tmp_path, monkeypatch)
    key = "TEST_fw1.00"
    hand = tmp_path / "data" / key / f"hand_tables_{key}.json"
    tables = json.loads(hand.read_text(encoding="utf-8"))
    tables["HAND_PLACES"] = {"global:0x0042": {"row": "Setup > Custom Key/Dial Set.#1"}}
    tables["ROW_ICONS"] = {"Setup > Custom Key/Dial Set.": "Still", "Setup > Custom Key/Dial Set.#1": "Movie",
                           "Setup > Fn Menu Settings": "Still"}
    hand.write_text(json.dumps(tables), encoding="utf-8")
    setup = [page("1/1", "Operation Customize", row("Custom Key/Dial Set.", row("Dial/Wheel")), row("Custom Key/Dial Set.", row("Dial/Wheel")),
                  row("Fn Menu Settings"))]
    tree = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Setup", "pages": copy.deepcopy(setup)}],
            "modes": [{"mode": m, "tabs": [{"tab": "Setup", "pages": copy.deepcopy(setup)}]} for m in ("Movie", "S&Q")]}
    (tmp_path / "tree.json").write_text(json.dumps(tree), encoding="utf-8")
    d = {**doc(), "tabs": ["Setup"], "menu": [{"tab": "Setup", "group": "Operation Customize", "label": lab, "order": i}
                                                for i, lab in enumerate(["Custom Key/Dial Set.", "Custom Key/Dial Set.", "Fn Menu Settings"])],
         "settings": [{**setting(k, name, "Operation Customize", *paths), "tab": "Setup"} for k, name, paths in (
             ("global:0x0041", "Dial/Wheel (Still)", ["Custom Key/Dial Set. > Dial/Wheel"]),
             ("global:0x0042", "Custom Key (Movie)", ["Custom Key/Dial Set."]),
             ("global:0x0043", "Fn Menu (Still)", ["Fn Menu Settings"]))]}
    got = {s["key"]: s for s in S.from_data(d)["settings"]}
    said = capsys.readouterr().out
    assert got["global:0x0041"]["row"] == ["Custom Key/Dial Set. (Still)", "Dial/Wheel"]
    assert got["global:0x0042"]["row"] == ["Custom Key/Dial Set. (Movie)"] and got["global:0x0042"]["row_at"] == [1]
    assert got["global:0x0043"]["row"] == ["Fn Menu Settings"]                       # no row of its label beside it
    assert "ROW_ICONS: 'Setup > Fn Menu Settings' names no row that another row of its label stands beside" in said


def test_an_options_icon_letters_are_left_out_only_where_another_reading_of_it_did(tmp_path):
    """menu_tree.py: an option whose leading token (at most row_names.ICON_LEAD characters) another reading of that
    same option left out (the crawl's options.jsonl: OCR read "W Rating", the vision reader "Rating") has its label as
    the camera draws it in the row's drawn_options, the evidence placement.option_names takes; one every reading gives
    whole ("Shot Mark") has none, whatever its first word's length. A fold takes it in as the tree's own walk does."""
    scan, crawl = tmp_path / "scan", tmp_path / "crawl"
    scan.mkdir()
    crawl.mkdir()
    (scan / "model.json").write_text(json.dumps([{"page": "30/59", "breadcrumb": "Playback > Selection/Search",
                                                   "rows": [{"slot": 0, "label": "Playback Filter Condition"}]}]), encoding="utf-8")
    (crawl / "rows.jsonl").write_text(json.dumps({"page": "30/59", "slot": 0, "label": "Playback Filter Condition",
                                                  "outcome": "walked", "kind": "checklist"}) + "\n", encoding="utf-8")
    (crawl / "map.json").write_text(json.dumps({"rows": [{"path": ["Playback Filter Condition"], "kind": "checklist", "options": [
        {"index": 0, "label": "Date"}, {"index": 1, "label": "W Rating"}, {"index": 2, "label": "Shot Mark"}]}]}), encoding="utf-8")
    (crawl / "options.jsonl").write_text("".join(json.dumps(x) + "\n" for x in [
        {"path": ["Playback Filter Condition"], "index": 0, "label": "Date", "ocr": "Date", "vlm": {"selected": "Date"}},
        {"path": ["Playback Filter Condition"], "index": 1, "label": "W Rating", "ocr": "W Rating", "vlm": {"selected": "Rating"}},
        {"path": ["Playback Filter Condition"], "index": 2, "label": "Shot Mark", "ocr": "Shot Mark", "vlm": {"selected": "Shot Mark"}}]),
        encoding="utf-8")
    menu = menu_tree.tree(scan, [crawl], "TEST_fw1.00", "Movie")
    pfc = menu["tabs"][0]["pages"][0]["rows"][0]
    assert pfc["options"] == ["Date", "W Rating", "Shot Mark"] and pfc["drawn_options"] == {"W Rating": "Rating"}
    folded = {"mode": "Movie", "tabs": [{"tab": "Playback", "pages": [{"page": "30/59", "group": "Selection/Search", "rows": [
        {"label": "Playback Filter Condition", "state": "seen", "why": "not walked", "kind": ""}]}]}]}
    menu_tree.fold(folded, crawl)
    assert folded["tabs"][0]["pages"][0]["rows"][0]["drawn_options"] == {"W Rating": "Rating"}
    assert menu_tree.check({"$schema": "x", "model": "TEST", "firmware": "1.00", "source": "made up", "tabs": [],
                            "modes": [menu]}) == []


def test_rows_a_menu_read_from_its_held_row_keep_the_settings_own_order():
    """A list of rows another menu's walk read from the row the camera held (the S&Q crawl of 2026-11-20 read
    Recognition Target's rows from Human round to Auto, where the Stills walk read Auto first): the same rows in a
    turned order are the same rows, so the setting keeps its own place there and no row_places rests on where the
    camera stood (decision 16). The same rows in an order no turn gives are that menu's own order."""
    kids = ["Auto", "Human", "Animal/Bird", "Insect"]
    turned = kids[1:] + kids[:1]

    def tree_of(order):
        return [{"tab": "Focus", "pages": [page("1/1", "Subject Recog.", row("Recognition Target", *[
            row(x, row("Recognition Priority Set.")) for x in order]))]}]
    d = {"model": "TEST", "tabs": ["Focus"], "menu": [{"tab": "Focus", "group": "Subject Recog.", "label": "Recognition Target", "order": 0}],
         "settings": [{**setting("global:0x0001", "Recognition Priority Set.", "Subject Recog.",
                                 "Recognition Target > Animal/Bird > Recognition Priority Set."), "tab": "Focus"}]}
    for order, places in ((turned, None), (["Animal/Bird", "Auto", "Human", "Insect"], {"row": ["Recognition Target", "Animal/Bird", "Recognition Priority Set."], "row_at": [0, 0, 0]})):
        tree = {"model": "TEST", "firmware": "1.00", "tabs": tree_of(kids), "modes": [{"mode": "S&Q", "tabs": tree_of(order)}]}
        got = placement.by_menu(copy.deepcopy(d), tree, [MENUS[0], MENUS[2]])["global:0x0001"]
        assert got.get("row_menus") == ["Still", "S&Q"]
        assert got.get("row_places", {}).get("S&Q") == places, order


def test_a_menus_table_that_misses_the_trees_menus_is_refused():
    """MENUS names its modes as the camera file does, and the menu tree names its menus so (menu_tree.py --mode): a
    table whose menus hold none of the tree's top-level menu (its "tabs": the Stills menu), or a menu whose modes
    match no menu of the tree, is refused in one sentence naming the tree's names and the table's, never left to give a
    menu that holds nothing."""
    assert placement.menus_refusal(TREE, MENUS) is None
    why = placement.menus_refusal(TREE, [{"name": "Photo", "modes": ["Photo"]}, {"name": "Movie", "modes": ["Movie"]}])
    assert "'Stills'" in why and "'Photo'" in why and "top-level" in why
    why = placement.menus_refusal(TREE, MENUS + [{"name": "Night", "modes": ["Night"]}])
    assert "'Night'" in why and "Movie" in why and "S&Q" in why


def test_the_writer_stops_on_a_menus_table_the_tree_does_not_match(tmp_path, monkeypatch):
    """Through fromdata.places: a MENUS table naming the stills mode otherwise than the tree ("Photo") stops the write,
    naming the hand tables file and what to do; the a1 II's own names write."""
    d = doc(*copy.deepcopy(SETTINGS))
    tree = tmp_path / "tree.json"
    tree.write_text(json.dumps(TREE), encoding="utf-8")
    monkeypatch.setattr(definitions, "menu_tree_file", lambda key: tree)
    monkeypatch.setattr(fromdata, "box_orders", lambda key: {})
    assert fromdata.places(d, MENUS)["global:0x0001"]["row_menus"] == ["Still"]
    with pytest.raises(hand_tables.Refused) as e:
        fromdata.places(d, [{"name": "Photo", "modes": ["Photo"]}, MENUS[1], MENUS[2]])
    assert "'Photo'" in str(e.value.code) and "menu_tree.py --mode" in str(e.value.code)


def test_a_menus_place_says_no_option_here_with_null():
    """Where the setting's own place is under an option of its row and a menu's place is under none, that menu's place
    says so: "under_option": null, which the definition's schema allows there (a field left out keeps the setting's
    own, so leaving it out would keep the option)."""
    from jsonschema import Draft202012Validator
    s = {"tab": "Shooting", "group": "Drive Mode"}
    own = {"row": ["Drive Mode"], "row_at": [2], "under_option": "Continuous Shooting"}
    got = placement.place_differs(own, {"row": ["Shutter Type"], "row_at": [9]}, s)
    assert got == {"row": ["Shutter Type"], "row_at": [9], "under_option": None}
    assert placement.place_differs(own, dict(own), s) == {}
    assert placement.place_differs({"row": ["A"], "row_at": [1]}, {"row": ["A"], "row_at": [2]}, s) == {"row": ["A"], "row_at": [2]}
    schema = json.loads((definitions.ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))
    v = Draft202012Validator(schema["$defs"]["setting"]["properties"]["row_places"])
    assert not list(v.iter_errors({"Movie": got}))
    d = {**doc(), "camera": {"menus": MENUS, "text": {}}, "settings": [
        {"key": "global:0x0001", "row": ["Drive Mode"], "row_at": [2], "under_option": "Continuous Shooting",
         "row_menus": ["Still", "Movie"], "row_places": {"Movie": got}}]}
    assert check_public.menu_problems(d) == []


def test_check_public_holds_the_menus_to_names_and_places_in_every_form(tmp_path, monkeypatch):
    """check_public refuses, through lean_problems with a message of its own (what is wrong and what to do, never
    "carries evidence"): My Menu's item pages however written ("MyMenu1", "★My Menu1", "My Menu Page 1"), a page
    counter with its word ("Page 38/63") or alone with a menu's two-digit total ("38/63"), a row on My Menu's tab
    outside its setting page (an owner's item), and row_menus on a copy. A label that is no page counter stands: a
    fraction with a one-digit total ("1/3", a step's name), and any option's name ("1/60" under_option, a shutter
    speed)."""
    def place(**more):
        return {"key": "global:0x0001", "row": ["Drive Mode"], "row_at": [2], "row_menus": ["Still"], **more}
    good = {**doc(), "camera": {"menus": MENUS, "text": {}}, "settings": [
        place(), place(key="global:0x0002", row=["Bracket Settings", "1/3"], row_at=[3, 0]),
        place(key="global:0x0003", under_option="1/60"),
        place(key="global:0x0004", row=["Add Item"], row_at=[0], row_tab="My Menu", row_group="My Menu Setting"),
        {"key": "global:0x0005", "row": ["Drive Mode"], "row_at": [2], "copy_of": "global:0x0001"}]}
    assert check_public.menu_problems(good) == []
    bad = copy.deepcopy(good)
    bad["settings"] += [place(key="global:0x0011", row_group="MyMenu1"), place(key="global:0x0012", row_group="★My Menu1"),
                        place(key="global:0x0013", row_group="My Menu Page 1"), place(key="global:0x0014", row=["Page 38/63"]),
                        place(key="global:0x0015", row=["38/63"]),
                        place(key="global:0x0016", row=["Drive Mode"], row_tab="My Menu", row_group="Favourites"),
                        {"key": "global:0x0017", "row": ["Drive Mode"], "row_at": [2], "copy_of": "global:0x0001", "row_menus": ["Still"]}]
    got = "\n".join(check_public.menu_problems(bad))
    for words in ("global:0x0011: row: 'MyMenu1' is one of My Menu's item pages", "'★My Menu1' is one of My Menu's item pages",
                  "'My Menu Page 1' is one of My Menu's item pages", "'Page 38/63' is a page counter", "'38/63' is a page counter",
                  "global:0x0016: a row on My Menu's tab outside its setting page ('Favourites')", "global:0x0017: row_menus on a copy"):
        assert words in got, words
    assert not [x for x in check_public.menu_problems(bad) if x.startswith(("global:0x0002", "global:0x0003", "global:0x0004"))]
    defs = tmp_path / "editor" / "definitions"
    defs.mkdir(parents=True)
    (defs / "TEST_fw1.00.json").write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setattr(check_public, "ROOT", tmp_path)
    said = check_public.lean_problems()
    menus = [x for x in said if "say more than names and places" in x]
    assert any(x.endswith("places its camera menus say more in all") for x in said)
    assert menus and all("carries evidence" not in x for x in menus)
    assert all(x.startswith("editor/definitions/TEST_fw1.00.json: its camera menus say more than names and places") for x in menus)
    assert "MENUS or HAND_PLACES" in menus[0]
    blob = check_public.blob_problems("editor/definitions/TEST_fw1.00.json", json.dumps(bad))          # a commit's copy
    assert blob and all(x.startswith("its camera menus say more than names and places") for x in blob)


def test_from_data_writes_the_menus_from_the_tables_and_the_tree(tmp_path, monkeypatch):
    """Through from_data, on a made-up camera with its own data folder and menu tree: the MENUS table read from the
    hand tables becomes camera.menus, each placed setting gets its row_menus from the tree's menus, and a HAND_PLACES
    row places its record in every menu that has the row; with no MENUS table there is no camera.menus and no
    row_menus, the places as they were."""
    import schema_update as S
    key = "TEST_fw1.00"
    data = tmp_path / "data"
    (data / key).mkdir(parents=True)
    camera = {"model": "TEST", **CAMERA, "main_tiles": [{"name": "Stills", "tiles": []}, {"name": "Movie", "tiles": []}]}
    (data / key / f"camera_{key}.json").write_text(json.dumps(camera), encoding="utf-8")
    tree = tmp_path / "tree.json"
    tree.write_text(json.dumps(TREE), encoding="utf-8")
    monkeypatch.setattr(definitions, "DATA", data)
    monkeypatch.setattr(S.help_files, "OWN", data)
    monkeypatch.setattr(definitions, "menu_tree_file", lambda k: tree)
    monkeypatch.setattr(fromdata, "box_orders", lambda k: {})
    hand = {"global:0x0031": {"row": "Shooting > Anti-dust Function > Shutter When Pwr OFF"}}

    def written(**tables):
        (data / key / f"hand_tables_{key}.json").write_text(json.dumps({"camera": key, **tables}), encoding="utf-8")
        d = doc(*copy.deepcopy(SETTINGS), setting("global:0x0031", "Seen by hand", "Other settings"))
        return S.from_data(d)
    got = written(MENUS=MENUS, HAND_PLACES=hand)
    assert got["camera"]["menus"] == MENUS
    by = {s["key"]: s for s in got["settings"]}
    assert by["global:0x0001"]["row_menus"] == ["Still"] and by["global:0x0002"]["row_menus"] == ["Movie", "S&Q"]
    assert by["global:0x0031"]["row"] == ["Anti-dust Function", "Shutter When Pwr OFF"]
    assert by["global:0x0031"]["row_menus"] == ["Still", "Movie", "S&Q"]
    plain = written(HAND_PLACES=hand)
    assert "menus" not in plain["camera"] and not any("row_menus" in s or "row_places" in s for s in plain["settings"])
    assert {s["key"]: s.get("row") for s in plain["settings"]} == {s["key"]: s.get("row") for s in got["settings"]}
    assert "row" not in {s["key"]: s for s in written()["settings"]}["global:0x0031"]          # no hand row, no row


def test_a_hand_place_that_cannot_be_placed_says_what_is_wrong_with_it(tmp_path, monkeypatch, capsys):
    """fromdata.places says why a HAND_PLACES entry placed nothing: a key the definition does not hold (mistyped), a
    family's setting (its column follows its record's copies, never a row given by hand), or a row the menu tree lacks."""
    d = doc(*copy.deepcopy(SETTINGS), setting("global:0x0040", "Black Level", "Picture Profile PP2"),
            setting("global:0x0041", "Unrowed", "Other settings"))
    d["camera"] = {"families": [{"prefix": "Picture Profile PP"}]}
    tree = tmp_path / "tree.json"
    tree.write_text(json.dumps(TREE), encoding="utf-8")
    monkeypatch.setattr(definitions, "menu_tree_file", lambda key: tree)
    monkeypatch.setattr(fromdata, "box_orders", lambda key: {})
    fromdata.places(d, None, {"global:0x9999": ["Shooting > Drive Mode"], "global:0x0040": ["Shooting > Drive Mode"],
                              "global:0x0041": ["Shooting > No Such Row"]})
    said = capsys.readouterr().out
    assert "HAND_PLACES: global:0x9999 is no setting of the definition (a mistyped key" in said
    assert "HAND_PLACES: global:0x0040 (Black Level) is a setting of the family 'Picture Profile PP'" in said
    assert "HAND_PLACES: global:0x0041's row (Shooting > No Such Row) is not in the camera's menu tree" in said


def test_where_an_option_list_began_shapes_no_place():
    """An option list the walk read from the option the camera held (the tree's "options", turned round by where it
    began: the owner's value) never shapes a public place. An option page's column, where the row's own setting lists
    no values, comes from the tree's options turned to start at their first label in order, so two owners who held
    different options get the same row_at; an option named by its place in the list ("White Balance / grid 2") is read
    against the list turned to start at the row's own setting's first value, the camera's first option."""
    settings = [s for s in copy.deepcopy(SETTINGS) if s["key"] in ("global:0x0020", "global:0x0021", "global:0x0022")]
    for s in settings:
        s.pop("values", None)
    d = doc(*settings)

    def tree_with(label, opts, kids=None):
        t = copy.deepcopy(TREE)
        for menu in [t] + t["modes"]:
            for pg in menu["tabs"][0]["pages"]:
                for r in pg["rows"]:
                    if r["label"] == label:
                        r["options"] = list(opts)
        return t
    a, b = tree_with("Picture Profile", ["PP1", "PP2", "PP3"]), tree_with("Picture Profile", ["PP3", "PP1", "PP2"])
    for k in ("global:0x0021", "global:0x0022"):
        assert placement.settings(copy.deepcopy(d), a).get(k) == placement.settings(copy.deepcopy(d), b).get(k), k
        assert placement.by_menu(copy.deepcopy(d), a, MENUS).get(k) == placement.by_menu(copy.deepcopy(d), b, MENUS).get(k), k
    wb = [[0, "Auto"], [1, "Daylight"], [2, "Shade"], [3, "Cloudy"]]
    e = doc(setting("global:0x0050", "Exposure Comp.", "Exposure", "Exposure Comp.", values=wb),
            setting("global:0x0051", "Fine-tune (Shade)", "Exposure", "Exposure Comp. / grid 2"))
    got = [placement.settings(copy.deepcopy(e), tree_with("Exposure Comp.", o))["global:0x0051"].get("under_option")
           for o in (["Auto", "Daylight", "Shade", "Cloudy"], ["Shade", "Cloudy", "Auto", "Daylight"])]
    assert got == ["Shade", "Shade"]


def test_records_one_row_in_the_editor_carry_equal_or_apart_menus():
    """The editor shows records of one name in one place (its linked records, the records a proof writes together) as
    one row only where their row_menus and row_places are equal; records of one row kept to their own modes' menus
    (split by mode) have menus apart. The writer refuses any other: menus that overlap unequal, or equal menus with
    places that differ, would show the row twice in a menu."""
    def s(key, menus, places=None, **more):
        return {"key": key, "name": "D-Range Optimizer", "row": ["D-Range Optimizer"], "row_at": [3], "row_menus": menus,
                **({"row_places": places} if places else {}), **more}
    ok = {"settings": [s("global:0x0001", ["Still", "Movie"]), s("global:0x0002", ["Still", "Movie"]),
                       s("global:0x0003", ["S&Q"], name="Other"), s("global:0x0004", ["Still"], row_at=[4]), s("global:0x0005", ["Movie"], row_at=[4]),
                       s("global:0x0006", ["Still", "S&Q"], copy_of="global:0x0001")]}
    assert fromdata.linked_refusal(ok) is None
    overlap = {"settings": [s("global:0x0001", ["Still", "S&Q"]), s("global:0x0002", ["Movie", "S&Q"])]}
    why = fromdata.linked_refusal(overlap)
    assert "global:0x0001" in why and "global:0x0002" in why and "twice" in why
    places = {"settings": [s("global:0x0001", ["Still", "Movie"], {"Movie": {"row": ["D-Range Optimizer"], "row_at": [2]}}),
                           s("global:0x0002", ["Still", "Movie"])]}
    assert "row_places" in fromdata.linked_refusal(places)


def test_rows_read_turned_round_keep_the_own_place_one_unread_level_deeper():
    """The S&Q tree after pass 10: Recognition Target's target rows read turned round (from Human, round to Auto) with
    nothing read below them, and a setting under Animal/Bird with a proof made in S&Q. The menu's own paths reach it
    through a row S&Q never read; the rows S&Q did read keep the setting's own order there too, so no S&Q place rests
    on where its walk began."""
    kids = ["Auto", "Human", "Animal/Bird", "Insect"]
    stills = [{"tab": "Focus", "pages": [page("1/1", "Subject Recog.", row("Recognition Target", *[
        row(x, row("Recognition Priority Set.")) for x in kids]))]}]
    sq = [{"tab": "Focus", "pages": [page("1/1", "Subject Recog.", row("Recognition Target", *[row(x) for x in kids[1:] + kids[:1]]))]}]
    tree = {"model": "TEST", "firmware": "1.00", "tabs": stills, "modes": [{"mode": "S&Q", "tabs": sq}]}
    path = "Recognition Target > Animal/Bird > Recognition Priority Set."
    d = {"model": "TEST", "tabs": ["Focus"], "menu": [{"tab": "Focus", "group": "Subject Recog.", "label": "Recognition Target", "order": 0}],
         "settings": [{**setting("global:0x0001", "Recognition Priority Set.", "Subject Recog.", path, f"{path} [S&Q mode]"), "tab": "Focus"}]}
    got = placement.by_menu(copy.deepcopy(d), tree, [MENUS[0], MENUS[2]])["global:0x0001"]
    assert got == {"row_menus": ["Still", "S&Q"]}, got


def test_the_writer_says_which_settings_are_in_fewer_menus_than_their_row(tmp_path, monkeypatch, capsys):
    """A mapping is not done while a setting is listed in fewer menus than the menus whose tree holds its top row:
    fromdata.places says, on the console only, how many settings below how many rows, and each row with the menus it
    lacks, so the open work is seen at every pass (never a stop)."""
    d = doc(*copy.deepcopy(SETTINGS))
    tree = tmp_path / "tree.json"
    tree.write_text(json.dumps(TREE), encoding="utf-8")
    monkeypatch.setattr(definitions, "menu_tree_file", lambda key: tree)
    monkeypatch.setattr(fromdata, "box_orders", lambda key: {})
    got = fromdata.places(d, MENUS)
    said = capsys.readouterr().out
    short = placement.fewer_menus(d, TREE, MENUS, got)
    assert ("global:0x0008", "Shooting", "Anti-flicker Set.", ["S&Q"]) in short          # Movie read the rows, none of it
    assert ("global:0x0004", "Shooting", "Lens Compensation", ["S&Q"]) in short
    assert not [x for x in short if x[0] == "global:0x0001"]                       # Drive Mode: the Still menu's alone
    rows = {(tab, row) for _, tab, row, _ in short}
    assert f"menus: {len(short)} settings below {len(rows)} rows are listed in fewer menus than their row stands in: " \
           "prove or crawl them there" in said
    assert ("global:0x0003", "Shooting", "Lens Compensation", ["S&Q"]) in short          # Still read the rows, none of it
    assert "  Shooting > Anti-flicker Set.: 2 settings, not in S&Q" in said
    # records of one row kept to their own modes' menus (the Help Guide's SteadyShot twins): the row is in every menu,
    # each by its own record, so none of them is open work
    rows = [page("1/1", "Image Stabilization", row("SteadyShot"))]
    tw = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Shooting", "pages": copy.deepcopy(rows)}],
          "modes": [{"mode": m, "tabs": [{"tab": "Shooting", "pages": copy.deepcopy(rows)}]} for m in ("Movie", "S&Q")]}
    placed = {"global:0x0001": {"row": ["SteadyShot"], "row_at": [0], "row_menus": ["Still"]},
              "global:0x0002": {"row": ["SteadyShot"], "row_at": [0], "row_menus": ["Movie", "S&Q"]}}
    two = {"model": "TEST", "tabs": ["Shooting"], "menu": [{"tab": "Shooting", "group": "Image Stabilization", "label": "SteadyShot", "order": 0}],
           "settings": [setting("global:0x0001", "SteadyShot", "Image Stabilization"), setting("global:0x0002", "SteadyShot (Movie)", "Image Stabilization")]}
    assert placement.fewer_menus(two, tw, MENUS, placed) == []


def test_a_row_that_opens_nothing_in_a_menu_keeps_the_settings_below_it_out_of_that_menus_count():
    """The S&Q walk's Right on Recognition Target's target rows changed nothing (the rows draw no ›: kit2_crawl_sq_1120
    00914, 00929, 00948), which the tree keeps as "unhandled: no response to Right": such a row opens nothing in that
    menu, so the Still settings below the Still menu's targets are no open work there, with nobody proving a negative.
    A target row the walk never opened (seen, never, a notice) still leaves them listed."""
    def target(state, why):
        return {"label": "Human", "state": state, "why": why, "kind": "submenu", "options": [], "children": []}

    def tree(human):
        rt = lambda h: row("Recognition Target", h)          # noqa: E731
        return {"model": "TEST", "firmware": "1.00",
                "tabs": [{"tab": "Focus", "pages": [page("1/1", "Subject Recognition", rt(row("Human", row("Tracking Shift Range"))))]}],
                "modes": [{"mode": "S&Q", "tabs": [{"tab": "Focus", "pages": [page("1/1", "Subject Recognition", rt(human))]}]}]}
    d = {"model": "TEST", "tabs": ["Focus"], "menu": [{"tab": "Focus", "group": "Subject Recognition", "label": "Recognition Target", "order": 0}],
         "settings": [{**setting("global:0x0001", "Tracking Shift Range", "Subject Recognition"), "tab": "Focus",
                       "row": ["Recognition Target", "Human", "Tracking Shift Range"], "row_at": [0, 0, 0]}]}
    placed = {"global:0x0001": {"row": ["Recognition Target", "Human", "Tracking Shift Range"], "row_at": [0, 0, 0], "row_menus": ["Still"]}}
    menus = [MENUS[0], MENUS[2]]
    assert placement.fewer_menus(d, tree(target("unhandled", placement.OPENS_NOTHING)), menus, placed) == []
    for state, why in (("seen", "not walked"), ("never", "action: x"), ("info", "an information notice comes first"),
                       ("unhandled", "unknown screen")):
        assert placement.fewer_menus(d, tree(target(state, why)), menus, placed) == [
            ("global:0x0001", "Focus", "Recognition Target", ["S&Q"])], state


def test_a_menu_whose_walk_read_a_row_as_a_list_holds_the_rows_its_options_name():
    """Movie's Playback crawl read Playback Filter Condition as a checklist of its items, while the Stills menu holds
    those items as rows under it, grown from their proofs' paths. Where a menu's row at the setting's last level has no
    rows read below it but its options name that last label (exactly, or as the camera draws the option where the tree
    has the evidence that its leading token is an icon's letters: "W Rating", which another reading gave as "Rating",
    names Rating), the menu holds the setting there, at the setting's own place. A token is never an icon by its length
    alone: without that evidence "W Rating" names no Rating, "Shot Mark" no Mark, and of "Front Dial" and "Rear Dial"
    neither names Dial. An option naming another label gives nothing; two options that both name it as drawn give
    nothing (no guess, unless one names it exactly); a row with rows read below it is decided by those rows, as before."""
    def trees(movie_row):
        stills = [{"tab": "Playback", "pages": [page("1/1", "Selection/Search", row("Playback Filter Condition"))]}]
        return {"model": "TEST", "firmware": "1.00", "tabs": stills,
                "modes": [{"mode": "Movie", "tabs": [{"tab": "Playback", "pages": [page("1/1", "Selection/Search", movie_row)]}]}]}
    d = {"model": "TEST", "tabs": ["Playback"], "menu": [{"tab": "Playback", "group": "Selection/Search", "label": "Playback Filter Condition", "order": 0}],
         "settings": [{**setting("global:0x0001", "Protect", "Selection/Search", "Playback Filter Condition > Protect"), "tab": "Playback"},
                      {**setting("global:0x0002", "Rating", "Selection/Search", "Playback Filter Condition > Rating"), "tab": "Playback"},
                      {**setting("global:0x0003", "Folder", "Selection/Search", "Playback Filter Condition > Folder"), "tab": "Playback"}]}
    menus = [MENUS[0], MENUS[1]]
    checklist = row("Playback Filter Condition", options=["Date", "Still Images/Movies", "W Rating", "Protect", "Cancel Filter"],
                    state="walked")
    bare = placement.by_menu(copy.deepcopy(d), trees(checklist), menus)
    assert bare["global:0x0002"] == {"row_menus": ["Still"]}                          # no evidence: "W" is no icon
    checklist["drawn_options"] = {"W Rating": "Rating"}                                  # another reading: "Rating"
    got = placement.by_menu(copy.deepcopy(d), trees(checklist), menus)
    assert got["global:0x0001"] == {"row_menus": ["Still", "Movie"]}                  # named exactly
    assert got["global:0x0002"] == {"row_menus": ["Still", "Movie"]}                  # "W Rating", drawn "Rating"
    assert got["global:0x0003"] == {"row_menus": ["Still"]}                           # no option names Folder
    twice = row("Playback Filter Condition", options=["W Rating", "X Rating", "Protect"], state="walked")
    twice["drawn_options"] = {"W Rating": "Rating", "X Rating": "Rating"}
    assert placement.by_menu(copy.deepcopy(d), trees(twice), menus)["global:0x0002"] == {"row_menus": ["Still"]}
    # the reviewer's cases: a word of four letters or fewer is no icon without the evidence
    assert not placement.option_names({"opts": ["Date", "Shot Mark"], "kids": []}, "Mark")
    assert not placement.option_names({"opts": ["Front Dial", "Rear Dial"], "kids": []}, "Dial")
    assert placement.option_names({"opts": ["Front Dial", "Rear Dial"], "kids": [], "drawn": {"Rear Dial": "Dial"}}, "Dial")
    exact = row("Playback Filter Condition", options=["W Rating", "Rating"], state="walked")
    assert placement.by_menu(copy.deepcopy(d), trees(exact), menus)["global:0x0002"] == {"row_menus": ["Still", "Movie"]}
    rows_too = row("Playback Filter Condition", row("Still Images/Movies"), row("Folder"), options=["Protect", "W Rating"], state="walked")
    got = placement.by_menu(copy.deepcopy(d), trees(rows_too), menus)
    assert got["global:0x0001"] == {"row_menus": ["Still"]} and got["global:0x0002"] == {"row_menus": ["Still"]}   # the rows decide
    assert got["global:0x0003"]["row_menus"] == ["Still", "Movie"]


def test_the_writer_stops_on_records_of_one_row_with_overlapping_menus(tmp_path, monkeypatch):
    """Through from_data: two records of one name in one place, one placed by its proofs (in the Still menu alone: Movie
    and S&Q never read the rows under Exposure Std. Adjust) and one by a row given by hand (in every menu with the top
    row), would show the row twice in the Still menu: the write stops, naming both records."""
    import schema_update as S
    key = "TEST_fw1.00"
    data = tmp_path / "data"
    (data / key).mkdir(parents=True)
    camera = {"model": "TEST", **CAMERA, "main_tiles": [{"name": "Stills", "tiles": []}, {"name": "Movie", "tiles": []}]}
    (data / key / f"camera_{key}.json").write_text(json.dumps(camera), encoding="utf-8")
    (data / key / f"hand_tables_{key}.json").write_text(json.dumps({"camera": key, "MENUS": MENUS, "HAND_PLACES": {
        "global:0x0041": {"row": "Shooting > Exposure Std. Adjust > Spot"}}}), encoding="utf-8")
    tree = tmp_path / "tree.json"
    tree.write_text(json.dumps(TREE), encoding="utf-8")
    monkeypatch.setattr(definitions, "DATA", data)
    monkeypatch.setattr(S.help_files, "OWN", data)
    monkeypatch.setattr(definitions, "menu_tree_file", lambda k: tree)
    monkeypatch.setattr(fromdata, "box_orders", lambda k: {})
    d = doc(setting("global:0x0040", "Spot", "Exposure", "Exposure Std. Adjust > Spot"), setting("global:0x0041", "Spot", "Exposure"))
    with pytest.raises(hand_tables.Refused) as e:
        S.from_data(d)
    said = str(e.value.code)
    assert "global:0x0040 and global:0x0041 (Spot) are one row in the editor" in said and "twice" in said


def test_where_the_own_menu_never_read_the_rows_another_menus_order_is_not_written():
    """The setting's own menu never read the rows under its top row (its place grown from its proof, in the definition's
    order), and another menu read them, turned or not: that menu's order is not written as its place there. The setting
    keeps its own, so no place rests on where another menu's walk began."""
    kids = ["Auto", "Human", "Animal/Bird", "Insect"]
    stills = [{"tab": "Focus", "pages": [page("1/1", "Subject Recog.", row("Recognition Target"))]}]
    sq = [{"tab": "Focus", "pages": [page("1/1", "Subject Recog.", row("Recognition Target", *[
        row(x, row("Recognition Priority Set.")) for x in kids[1:] + kids[:1]]))]}]
    tree = {"model": "TEST", "firmware": "1.00", "tabs": stills, "modes": [{"mode": "S&Q", "tabs": sq}]}
    d = {"model": "TEST", "tabs": ["Focus"], "menu": [{"tab": "Focus", "group": "Subject Recog.", "label": "Recognition Target", "order": 0}],
         "settings": [{**setting("global:0x0001", "Recognition Priority Set.", "Subject Recog.",
                                 "Recognition Target > Animal/Bird > Recognition Priority Set."), "tab": "Focus"}]}
    assert placement.settings(copy.deepcopy(d), tree)["global:0x0001"]["row_at"] == [0, 0, 0]
    got = placement.by_menu(copy.deepcopy(d), tree, [MENUS[0], MENUS[2]])["global:0x0001"]
    assert got == {"row_menus": ["Still", "S&Q"]}, got


def test_check_public_refuses_a_place_field_that_is_no_label_in_plain_words():
    """A row_places entry or a setting whose row_tab, row_group or under_option is not a label (an object, a number) is
    refused in plain words, never a crash."""
    d = {**doc(), "camera": {"menus": MENUS, "text": {}}, "settings": [
        {"key": "global:0x0001", "row": ["Drive Mode"], "row_at": [2], "row_menus": ["Still", "Movie"],
         "row_places": {"Movie": {"row": ["Drive Mode"], "row_at": [1], "row_tab": {"x": 1}, "under_option": 3}}},
        {"key": "global:0x0002", "row": ["Drive Mode"], "row_at": [2], "row_group": ["G"], "row_menus": ["Still"]}]}
    got = "\n".join(check_public.menu_problems(d))
    for words in ("global:0x0001: row_places['Movie']: row_tab is no label", "global:0x0001: row_places['Movie']: under_option is no label",
                  "global:0x0002: row_group is no label"):
        assert words in got, words


def test_a_silent_proof_whose_base_download_is_gone_adds_no_mode_not_even_stills():
    """A proof whose context names no mode and whose base download is gone gives no mode: the writer keeps its row with
    no mode in the evidence (menu_modes: []), and placement reads it as a proof of no menu's mode, never the Still
    menu's: it adds no menu by its mode and counts in no split by mode, while its record and row are placed as
    before. D-Range Optimizer's movie record proved in Movie and by such a proof is the Movie record alone, apart from
    the still one proved in Stills (an unknown mode read as Stills would have kept the two one row)."""
    rows = [page("1/1", "Color/Tone", row("D-Range Optimizer"))]
    tree = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Shooting", "pages": copy.deepcopy(rows)}],
            "modes": [{"mode": "Movie", "tabs": [{"tab": "Shooting", "pages": copy.deepcopy(rows)}]}]}
    still = setting("global:0x0001", "D-Range Optimizer", "Color/Tone", "D-Range Optimizer")
    movie = setting("global:0x0002", "D-Range Optimizer", "Color/Tone", "D-Range Optimizer [Movie mode]", "D-Range Optimizer")
    movie["proved"]["menu_modes"] = {"D-Range Optimizer": []}                        # its silent proof: its base download gone
    d = {"model": "TEST", "tabs": ["Shooting"], "menu": [{"tab": "Shooting", "group": "Color/Tone", "label": "D-Range Optimizer", "order": 0}],
         "settings": [still, movie]}
    menus = [MENUS[0], MENUS[1]]
    modes = placement.menu_modes_of(d)
    every = ["Stills", "Movie", "S&Q", "Time-lapse"]
    assert placement.with_modes(placement.proof_paths, modes, every)(movie) == ["D-Range Optimizer [Movie mode]", "D-Range Optimizer [no mode known]"]
    got = placement.by_menu(copy.deepcopy(d), tree, menus, modes=modes)
    assert (got["global:0x0001"]["row_menus"], got["global:0x0002"]["row_menus"]) == (["Still"], ["Movie"])
    assert placement.settings(copy.deepcopy(d), tree, None, placement.with_modes(placement.proof_paths, modes, every))["global:0x0002"]["row"] == ["D-Range Optimizer"]
