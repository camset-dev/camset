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
    a menu whose tree never read the rows under a row (S&Q here) holds none of them: nothing is taken from another
    menu's rows."""
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
    ok = {"global:0x04a2": {"row": "Setup > Anti-dust Function > Shutter When Pwr OFF", "why": "seen on the camera by its owner"}}
    assert read(HAND_PLACES=ok)["HAND_PLACES"] == ok
    for bad, words in (({"0x04a2": ok["global:0x04a2"]}, "not a setting's key"),
                       ({"global:0x04a2": {"row": "Shutter When Pwr OFF", "why": "x"}}, "not its tab then"),
                       ({"global:0x04a2": {"row": "Setup > A", "why": " "}}, "says no why"),
                       ({"global:0x04a2": {"row": "Setup > A", "why": "x", "run": "kit2_x"}}, "'run'")):
        with pytest.raises(hand_tables.Refused) as e:
            read(HAND_PLACES=bad)
        assert words in str(e.value.code), words


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
                       ([{"name": "A", "modes": ["Movie"], "main_tiles": "S&Q"}], "tile set 'S&Q'")):
        with pytest.raises(hand_tables.Refused) as e:
            fromdata.camera_menus(d, bad)
        assert words in str(e.value.code), words
    assert list(fromdata.with_menus({"model": "X", "main_tiles": [], "my_menu": {}}, menus)) == ["model", "main_tiles", "menus", "my_menu"]
    assert "menus" not in fromdata.with_menus({"model": "X", "menus": menus}, None)


def test_without_the_menus_table_the_places_are_todays(tmp_path, monkeypatch):
    """With no MENUS table the definition's places are exactly what they were (no row_menus, no row_places, no
    camera.menus); with it, each placed setting gets its menus, its own place untouched."""
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
    # (a) Stills moved one record, Movie the other: each in its own mode's menu; S&Q, which no proof names, keeps both
    ((["D-Range Optimizer"], ["D-Range Optimizer [Movie mode]"]), (["Still", "S&Q"], ["Movie", "S&Q"])),
    # (b) both moved together in each mode: one row in every menu, as before
    ((["D-Range Optimizer", "D-Range Optimizer [Movie mode]"], ["D-Range Optimizer", "D-Range Optimizer [Movie mode]"]),
     (["Still", "Movie", "S&Q"], ["Still", "Movie", "S&Q"])),
])
def test_one_settings_records_proved_in_different_modes_are_each_kept_to_their_own(proofs, menus):
    """D-Range Optimizer kept in two records on one row: where Stills moved one and Movie the other, each keeps its own
    mode's menu (and the menus no proof names, which nothing tells apart); where both moved in each mode, both stay in
    every menu."""
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
    placed = [s for s in doc["settings"] if s.get("row") and not s.get("copy_of")]
    for i, s in enumerate(placed):
        s["row_menus"] = ["Still", "Movie"] if i % 2 else ["Still"]
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
    live_mode) in its base download, read once and kept in the camera's cache. A silent proof whose base download says
    Movie is its record's proof in the Movie menu too, where that menu never read the rows under the row; one whose
    base says Stills, or whose context names a mode, stays as it is. The report's rows, and so what they credit, stay
    as the contexts give them, and proofs.jsonl is not rewritten."""
    import pass2_report
    from camkit import camset, live_modes, paths
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
              "changes": [{"key": "global:0x0033", "before": 0, "after": 1}]}]
    text = "".join(json.dumps(x) + "\n" for x in lines)
    (run / "proofs.jsonl").write_text(text, encoding="utf-8")
    monkeypatch.setattr(live_modes, "CACHE", tmp_path / "live_mode.json")
    rows = [pass2_report.row_name(r) for r in pass2_report.report_proofs(run)[0]]
    assert rows == ["Exposure Std. Adjust > Spot", "Exposure Std. Adjust > Multi", "Exposure Std. Adjust > Spot [S&Q mode]"]
    modes = pass2_report.silent_modes(run)
    spot, multi = ("exposurestdadjust", "spot"), ("exposurestdadjust", "multi")
    assert modes == {("global:0x0031", spot): {"Movie"}, ("global:0x0032", multi): {"Stills"}}
    assert (run / "proofs.jsonl").read_text(encoding="utf-8") == text
    assert len(json.loads((tmp_path / "live_mode.json").read_text(encoding="utf-8"))["codes"]) == 2
    monkeypatch.setattr(camset, "parse", lambda *a, **k: (_ for _ in ()).throw(AssertionError("read again")))
    assert pass2_report.silent_modes(run) == modes                                         # from the cache
    d = doc(setting("global:0x0031", "Spot", "Exposure", "Exposure Std. Adjust > Spot"),
            setting("global:0x0032", "Multi", "Exposure", "Exposure Std. Adjust > Multi"))
    assert placement.with_modes(placement.proof_paths, modes)(d["settings"][0]) == ["Exposure Std. Adjust > Spot [Movie mode]"]
    assert by_key(d)["global:0x0031"] == {"row_menus": ["Still"]}                  # Movie never read Spot's row
    got = placement.by_menu(d, TREE, MENUS, modes=modes)
    assert got["global:0x0031"] == {"row_menus": ["Still", "Movie"]} and got["global:0x0032"] == {"row_menus": ["Still"]}
    from writer import copies
    assert [copies.row_mode(r) for r in rows] == ["Stills", "Stills", "S&Q"]          # the writer reads rows alike
    assert copies.row_mode("ISO [Movie mode (dial set with the menu)]") == "Movie"


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
