"""camkit.menu_rows, the kit's copy of the editor's Menu "As on the camera": the cases of editor/src/menu_rows.rs's own
tests, made up the same way and expected the same, and the a1 II's public definition laid out whole.

Run: .venv/bin/python -m pytest kit/tests/test_menu_rows.py -q
"""
import json
from pathlib import Path

from camkit import definitions, menu_rows as mr, paths


def s(key, name, row, at, under=None, values=(), **more):
    """A setting as the editor's tests make one (menu_rows.rs, s())."""
    return {"key": key, "area": "global", "id": 1, "name": name, "tab": "Shooting", "group": "Drive Mode", "order": 46,
            "row": list(row), "row_at": list(at), "under_option": under, "in_sets": False,
            "values": [[i, lab] for i, lab in enumerate(values)], **more}


def rows(*settings):
    return [[x] for x in settings]


def row(index, depth):
    return ("row", index, depth)


def head(label, depth, path):
    return ("heading", label, depth, list(path))


def order(lines):
    return [x[1] for x in lines if x[0] == "row"]


def test_a_group_as_on_the_camera():
    """Drive Mode first, its sub-choices beside its options (no rows), the submenus as headings with their rows under
    them, a setting alone on its row that row, and what the definition does not place last."""
    r = rows(s("a", "Unplaced", [], []),
             s("b", "Hi(E-Shutter)", ["Cont. Shooting Speed", "Hi (E-Shutter)"], [28, 1]),
             s("c", "Speed", ["Drive Mode"], [26], "Continuous Shooting", ["Hi", "Lo"]),
             s("d", "Drive Mode", ["Drive Mode"], [26], None, ["Single Shooting", "Continuous Shooting", "Self-timer"]),
             s("e", "Hi+(E-Shutter)", ["Cont. Shooting Speed", "Hi+ (E-Shutter)"], [28, 0]),
             s("f", "Delay", ["Drive Mode"], [26], "Self-timer"),
             s("g", "Interval Rec Mode", ["Interval Shoot Func.", "Interval Shooting"], [33, 0]),
             s("h", "Limit: Lo", ["Drive Mode Limit"], [27]),
             s("i", "Limit: Hi", ["Drive Mode Limit"], [27]))
    lines = mr.lay_out(r)
    assert lines == [row(3, 0),
                     head("Drive Mode Limit", 0, ["Drive Mode Limit"]), row(7, 1), row(8, 1),
                     head("Cont. Shooting Speed", 0, ["Cont. Shooting Speed"]), row(4, 1), row(1, 1),
                     head("Interval Shoot Func.", 0, ["Interval Shoot Func."]), row(6, 1),
                     ("more",), row(0, 0)]
    assert order(lines) == [3, 7, 8, 4, 1, 6, 0]
    firsts = [x[0] for x in r]
    assert [(x["key"], o) for x, o in mr.sub_choices(r[3][0], firsts)] == [("c", "Continuous Shooting"), ("f", "Self-timer")]
    assert mr.owner(firsts, r[2][0])["key"] == "d" and mr.sub_choices(r[2][0], firsts) == []


def test_a_modes_rows_after_the_stills_rows():
    movie = lambda x: {**x, "row_mode": "Movie"}          # noqa: E731
    r = rows(movie(s("a", "Rec Frame Rate", ["S&Q Settings", "Frame Rate Settings", "Rec Frame Rate"], [5, 0, 1])),
             s("b", "Aspect Ratio", ["Aspect Ratio"], [2]),
             movie(s("c", "Log Shooting", ["Log Shooting Setting", "Log Shooting"], [7, 0])),
             s("d", "Unplaced", [], []),
             movie(s("e", "Frame Rate", ["S&Q Settings", "Frame Rate Settings", "Frame Rate"], [5, 0, 0])),
             s("f", "Shading Comp.", ["Lens Compensation", "Shading Comp."], [14, 0]))
    assert mr.lay_out(r) == [row(1, 0), head("Lens Compensation", 0, ["Lens Compensation"]), row(5, 1),
                             ("mode", "Movie"),
                             head("S&Q Settings", 0, ["Movie", "S&Q Settings"]),
                             head("Frame Rate Settings", 1, ["Movie", "S&Q Settings", "Frame Rate Settings"]),
                             row(4, 2), row(0, 2),
                             head("Log Shooting Setting", 0, ["Movie", "Log Shooting Setting"]), row(2, 1),
                             ("more",), row(3, 0)]


def test_the_camera_group_and_its_place():
    held = s("a", "Shoot Mode", ["Reg. Custom Shoot Set", "Recall Custom hold 1", "Shoot Mode"], [33, 0, 0],
             group="Recall Custom hold 1", row_group="Shooting Mode")
    assert mr.camera_group(held) == "Shooting Mode"
    unplaced = {**held, "row": [], "row_at": []}
    assert mr.camera_group(unplaced) == "Recall Custom hold 1"
    other = s("b", "Drive Mode", ["Drive Mode"], [34])
    keys = sorted([mr.group_key(1500, "My Menu", [unplaced]), mr.group_key(46, "Drive Mode", [other]),
                   mr.group_key(9000, "Shooting Mode", [held])])
    assert [k[3] for k in keys] == ["Shooting Mode", "Drive Mode", "My Menu"]


def test_a_row_in_another_tab():
    cell = s("a", "Custom Key (Movie): AEL Button", ["Custom Key/Dial Set."], [5], row_tab="Setup", row_group="Operation Customize")
    assert (mr.camera_tab(cell), mr.camera_group(cell)) == ("Setup", "Operation Customize")
    assert mr.camera_tab({**cell, "row": [], "row_at": []}) == "Shooting"


def test_sub_choices_beside_their_option_not_rows():
    b2 = s("b2", "B second", ["Look"], [5], "B", order=50)
    b1 = s("b1", "B first", ["Look"], [5], "B", order=49)
    b3 = s("b3", "Another B first", ["Look"], [5], "B", order=50)
    r = rows(b2, s("a1", "A only", ["Look"], [5], "A"), s("own", "Look", ["Look"], [5], None, ["A", "B"]), b1, b3,
             s("x", "Stray", ["Look"], [5], "C"))
    assert mr.lay_out(r) == [row(2, 0), row(5, 1)]
    firsts = [x[0] for x in r]
    assert [(x["key"], o) for x, o in mr.sub_choices(r[2][0], firsts)] == [("a1", "A"), ("b1", "B"), ("b3", "B"), ("b2", "B")]
    assert order(mr.lay_out(rows(s("a1", "A only", ["Look"], [5], "A")))) == [0], "without its owner, a row again"
    nested = [list(x) for x in r]
    nested[2] = [{**r[2][0], "values": [[0, "A"], [1, "B: 1"], [2, "B: 2"]],
                  "option_tree": [{"label": "A", "value": 0}, {"label": "B", "options": [[1, "1"], [2, "2"]]}]}]
    assert mr.nests_option(nested[2][0], "B")
    assert order(mr.lay_out(nested)) == [2, 0, 3, 4, 5]


def test_a_page_under_an_option():
    def on(key, name, row_, at, **more):
        return s(key, name, ["Profile", "P1", *row_], [29, 1, *at], "P1", group="Profile P1", row_group="Profile P1", **more)
    # a copy the camera keeps of a parameter (copy_of) is one row with it, whatever its name
    page = rows(on("bl", "Black Level", ["Black Level"], [0]), on("bls", "Black Level (stills)", ["Black Level"], [0], copy_of="bl"),
                on("bgl", "Black Gamma Level", ["Black Gamma", "Level"], [2, 1]), on("bgr", "Black Gamma Range", ["Black Gamma", "Range"], [2, 0]),
                on("km", "Knee Mode", ["Knee", "Mode"], [3, 0]), on("kmp", "Knee Auto Set Max Point", ["Knee", "Auto Set", "Max Point"], [3, 1, 0]),
                on("kmps", "Copy of the max point", ["Knee", "Auto Set", "Max Point"], [3, 1, 0], copy_of="kmp"))
    assert all(mr.on_page(x[0]) for x in page) and mr.page_prefix(page[0][0]) == 2
    assert mr.lay_out(page) == [row(0, 0), row(1, 0),
                                head("Black Gamma", 0, ["Black Gamma"]), row(3, 1), row(2, 1),
                                head("Knee", 0, ["Knee"]), row(4, 1), head("Auto Set", 1, ["Knee", "Auto Set"]), row(5, 2), row(6, 2)]
    two = page + [[{**page[0][0], "key": "p2", "under_option": "P2", "row": ["Profile", "P2", "Black Level"], "row_at": [29, 2, 0]}]]
    lines = mr.lay_out(two)
    assert lines[0] == head("P1", 0, ["P1"]) and lines[-1] == row(7, 1)


MENUS = [{"name": "Still", "modes": ["Stills"]}, {"name": "Movie", "modes": ["Movie"]}, {"name": "S&Q", "modes": ["S&Q", "Time-lapse"]}]


def test_a_setting_in_the_cameras_menus():
    """editor/src/schema.rs's a_setting_in_the_cameras_menus: the menus that hold a setting's row, and the setting as a
    menu lays it out."""
    doc = {"camera": {"menus": MENUS}, "settings": []}
    audio = s("a", "Audio", ["Audio"], [5], row_mode="Movie",
              row_places={"S&Q": {"row": ["Audio Settings", "Audio"], "row_at": [3, 0], "row_group": "Sound"}})
    assert mr.menus_of(doc, s("n", "Audio", ["Audio"], [5], row_menus=["Movie", "S&Q", "Gone"])) == ["Movie", "S&Q"]
    assert mr.menus_of(doc, audio) == ["Movie", "S&Q"]
    assert mr.menus_of(doc, s("p", "Audio", ["Audio"], [5])) == ["Still"]
    assert mr.menus_of(doc, s("u", "Audio", [], [])) == []
    p = mr.place_in(audio, "S&Q")
    assert (p["row"], p["row_at"], p.get("row_group"), p.get("row_tab"), p.get("row_mode")) == (["Audio Settings", "Audio"], [3, 0], "Sound", None, None)
    assert (p["row_menus"], p["shown_in"], mr.place_in(p, "S&Q")["row"]) == (["S&Q"], "S&Q", p["row"])
    assert mr.place_in(audio, "Movie")["row"] == ["Audio"] and "row_mode" not in mr.place_in(audio, "Movie")
    a, b = s("a", "Audio", ["Audio"], [5], row_menus=["Still"]), s("b", "Audio", ["Audio"], [5], row_menus=["Movie"])
    # one row whichever menus name them (what an edit writes together does not depend on the menus); laid out for two
    # menus, two rows (review finding 8)
    assert mr.same_row(a, b) and mr.links_with(a, b)
    assert not mr.same_row(mr.place_in(a, "Still"), mr.place_in(b, "Movie")) and mr.same_row(mr.place_in(a, "Still"), mr.place_in(b, "Still"))
    assert mr.menu_list({"camera": {"menus": MENUS[:1]}}) == []


def test_a_menus_place_with_no_option_above_it():
    """editor/src/schema.rs's a_setting_in_the_cameras_menus (page file, finding C1): an under_option given as null in
    a menu's row_places says that place has no option above it, where the setting's own place is under one; a field
    left out keeps the top-level one."""
    pp = s("pp", "Black Level", ["Picture Profile", "PP2", "Black Level"], [3, 1, 7], under="PP2",
           row_places={"S&Q": {"row": ["Black Level"], "row_at": [7], "under_option": None}, "Movie": {"row": ["Black Level"], "row_at": [7]}})
    assert [mr.place_in(pp, m)["under_option"] for m in ("S&Q", "Movie", "Still")] == [None, "PP2", "PP2"]


def test_what_one_menu_lists():
    """App::listed: the rows a menu holds; a setting the camera keeps a copy of per mode as its copy for the menu, in a
    menu not of the mode the file was saved in, under the setting's name; its copies no rows; a row alone on its place
    titled as the camera draws it; a setting placed nowhere with its group. Expert mode: every record a row, by name."""
    doc = {"tabs": ["Shooting"], "camera": {"menus": MENUS[:2]}, "settings": [
        s("iso", "ISO", ["ISO"], [2], row_menus=["Still", "Movie"], copies=["iso_s", "iso_m"], group="Exposure"),
        s("iso_s", "ISO (stills)", ["ISO"], [2], copy_of="iso", copy_for=["Stills"], group="Exposure"),
        s("iso_m", "ISO (movie)", ["ISO"], [2], copy_of="iso", copy_for=["Movie", "S&Q"], group="Exposure"),
        s("ss", "SteadyShot", ["SteadyShot"], [5], row_menus=["Still"], group="Stabilization"),
        s("ssm", "SteadyShot (Movie)", ["SteadyShot"], [5], row_menus=["Movie"], group="Stabilization"),
        s("loose", "Loose", [], [], group="Stabilization")]}
    menu = mr.Menu(doc)
    rows = lambda m, mode=None, expert=False: [(x["key"], x["name"]) for x in menu.listed(m, mode, expert)]          # noqa: E731
    assert rows("Movie", "Stills") == [("iso_m", "ISO"), ("ssm", "SteadyShot"), ("loose", "Loose")]
    assert rows("Still", "Stills") == [("iso", "ISO"), ("ss", "SteadyShot"), ("loose", "Loose")]
    assert rows("Still", "Movie")[0] == ("iso_s", "ISO") and rows("Movie", None)[0] == ("iso", "ISO")
    assert rows("Movie", "Stills", True) == [("iso", "ISO"), ("iso_s", "ISO (stills)"), ("iso_m", "ISO (movie)"), ("ssm", "SteadyShot (Movie)"), ("loose", "Loose")]
    listed = menu.listed("Movie", "Stills")
    assert [e for e, _ in menu.entries(listed, in_menu=True)] == ["Shooting"]
    assert all(x["row_menus"] == ["Movie"] for x in listed)


def test_rows_titled_alike_under_one_heading_keep_their_names():
    """editor/src/pages/menu.rs's test of the same name: a row alone on its place keeps its full name where another row
    under the same heading would be titled alike; a label told apart by `#n` is drawn without it, in a title and a
    heading, and told apart with it."""
    doc = {"tabs": ["Shooting"], "camera": {"menus": MENUS[:2]}, "settings": [
        s("rm", "Recording Media", ["Rec. Media Settings#1", "Recording Media"], [16, 0], row_menus=["Still", "Movie"], group="Media"),
        s("rmm", "Recording Media (Movie)", ["Rec. Media Settings#1", "Recording Media#1"], [16, 1], row_menus=["Movie"], group="Media"),
        s("adj", "SteadyShot Adjust", ["SteadyShot Adjust.#1"], [64], row_menus=["Still"], group="Media")]}
    menu = mr.Menu(doc)
    names = lambda m: {x["key"]: x["name"] for x in menu.listed(m, "Stills")}          # noqa: E731
    assert names("Movie") == {"rm": "Recording Media", "rmm": "Recording Media (Movie)"}
    assert names("Still") == {"rm": "Recording Media", "adj": "SteadyShot Adjust."}
    lines = mr.lay_out([[x] for x in menu.listed("Still", "Stills")])
    assert ("heading", "Rec. Media Settings", 0, ["Rec. Media Settings#1"]) in lines
    assert mr.drawn("Fn Menu Settings#12") == "Fn Menu Settings" and mr.drawn("#1") == "#1" and mr.drawn("A#b") == "A#b"


def test_rows_told_apart_by_an_icon_draw_its_words():
    """The case of editor/tests/data/menu_row_icons.json, which editor/src/menu_rows.rs's test of the same name lays out
    alike: a level is its label without its `#n`, then its words (row_icons) in brackets where every setting on or under
    the row agrees on them, the headings' paths keeping the labels; a menu's own place takes its own words, none where it
    gives its row and no words. And a row alone on its place titled with its words, so two rows titled alike without
    them are told apart (editor/src/pages/menu.rs, rows_told_apart_by_an_icon_draw_its_words_everywhere)."""
    case = json.loads((Path(__file__).resolve().parents[2] / "editor" / "tests" / "data" / "menu_row_icons.json").read_text(encoding="utf-8"))

    def made(v):
        return s(v["key"], v["name"], v["row"], v["row_at"], **{k: x for k, x in v.items() if k not in ("key", "name", "row", "row_at")})
    settings = [made(v) for v in case["settings"]]
    assert [list(x) for x in mr.lay_out(rows(*settings))] == case["lines"]
    assert mr.drawn_row(settings[5]) == "Fn Menu Settings (Playback) > Fn Row", "an empty word is none"
    placed = made(case["placed"])
    for c in case["places"]:
        p = mr.place_in(placed, c["menu"])
        assert [mr.row_words(p, i) for i in range(len(p["row"]))] == c["words"], c["menu"]
        assert mr.drawn_row(p) == c["drawn"]
    assert mr.drawn_row(s("a", "Delay", ["Drive Mode#2", "Self-timer"], [26, 0])) == "Drive Mode > Self-timer", "no words: as before"
    doc = {"tabs": ["Shooting"], "camera": {"menus": MENUS[:2]}, "settings": [
        s("rm", "Recording Media", ["Rec. Media Settings#1", "Recording Media"], [16, 0], row_menus=["Still", "Movie"], group="Media", row_icons=[None, "Still"]),
        s("rmm", "Recording Media (Movie)", ["Rec. Media Settings#1", "Recording Media#1"], [16, 1], row_menus=["Movie"], group="Media", row_icons=[None, "Movie"])]}
    names = {x["key"]: x["name"] for x in mr.Menu(doc).listed("Movie", "Stills")}
    assert names == {"rm": "Recording Media (Still)", "rmm": "Recording Media (Movie)"}


def test_a_copy_in_its_settings_row_sits_in_its_settings_tab_and_group():
    """editor/src/pages/menu.rs's test of the same name: a copy shown in its setting's row takes the setting's tab and
    group, whatever its own say (White Balance's fine-tune movie copy, its own place Shooting > Other settings)."""
    doc = {"tabs": ["Shooting", "Exposure/Color"], "camera": {"menus": MENUS[:2]}, "settings": [
        s("wb", "WB fine-tune", ["White Balance"], [22], row_menus=["Still", "Movie"], copies=["wb_m"], tab="Exposure/Color", group="White Balance"),
        s("wb_m", "WB fine-tune (movie)", ["White Balance"], [22], copy_of="wb", copy_for=["Movie"], tab="Shooting", group="Other settings")]}
    row = mr.Menu(doc).listed("Movie", "Stills")[0]
    assert (row["key"], row["tab"], row["group"]) == ("wb_m", "Exposure/Color", "White Balance")
    assert mr.camera_tab(row) == "Exposure/Color" and mr.camera_group(row) == "White Balance"


def test_a_row_without_its_own_setting_is_a_heading_and_nothing_placed_is_the_flat_list():
    assert mr.lay_out(rows(s("c", "Speed", ["Drive Mode"], [26], "Continuous Shooting"))) == [head("Drive Mode", 0, ["Drive Mode"]), row(0, 1)]
    assert mr.lay_out(rows(s("a", "A", [], []), s("b", "B", [], []))) == [row(0, 0), row(1, 0)]


def test_the_a1s_public_definition_has_every_setting_in_one_entry():
    """Laid out whole, the a1 II's public definition puts every setting in exactly one of the Menu's entries, and each
    entry's groups hold every one of its settings (a family's twice: its table and its page)."""
    doc = definitions.load_public(paths.A1II)
    menu = mr.Menu(doc)
    entries = menu.entries()
    keys = [x["key"] for _, settings in entries for x in settings]
    assert sorted(keys) == sorted(x["key"] for x in doc["settings"])
    assert [e for e, _ in entries][:len(doc["tabs"])] == [t for t in doc["tabs"] if t != "My Menu"]
    # My Menu's places are its page's (App::entry_here), never under the entry for what the menus do not hold
    records = set(doc["camera"]["my_menu"]["records"])
    places = {x["key"] for x in doc["settings"] if x["area"] == "global" and x["id"] in records}
    assert places and places <= {x["key"] for e, settings in entries if e == menu.my_menu for x in settings}
    for entry, settings in entries:
        held = {x["key"] for _, _, rows in menu.groups(entry, settings) for r in rows for x in r}
        assert held == {x["key"] for x in settings}, entry


GOLDEN = definitions.ROOT / "editor" / "tests" / "data" / "menu_ILCE-1M2_fw4.00.json"


def golden_shape(doc, expert: bool = False, in_menu: str | None = None, mode: str | None = None) -> list:
    """The Menu as editor/src/pages/menu.rs's the_default_menu_is_the_golden_one writes it (golden_entries): each entry
    the side bar lists (My Menu's tab has the My Menu page there), its groups, a family's table by its keys, every other
    group's lines (a row by its records' keys); in one of the camera's menus (`in_menu`, the live settings saved in
    `mode`), as that menu lists them, a row titled otherwise than its setting with that title last."""
    menu = mr.Menu(doc)
    if in_menu is None:
        entries = menu.entries(mr.shown(doc, expert))
    else:
        listed = [s for s in menu.listed(in_menu, mode, expert) if expert or (s.get("area") == "global" and not s.get("expert"))]
        entries = menu.entries(listed, in_menu=True)

    def row_line(x, rows):
        lead = rows[x[1]][0]
        line = ["row", [y["key"] for y in rows[x[1]]], x[2]]
        return line + [lead["name"]] if in_menu is not None and lead["name"] != menu.by_key[lead["key"]]["name"] else line
    out = []
    for entry, settings in entries:
        if menu.has_my_menu and entry == menu.my_menu:
            continue
        groups = []
        for name, fam, rows in menu.groups(entry, settings):
            if fam:
                groups.append({"group": name, "family": True, "keys": [x["key"] for x in rows[0]]})
                continue
            lines = [["heading", x[1], x[2]] if x[0] == "heading" else row_line(x, rows) if x[0] == "row"
                     else list(x) for x in mr.lay_out(rows)]
            groups.append({"group": name, "family": False, "lines": lines})
        out.append({"entry": entry, "groups": groups})
    return out


def test_the_default_menu_is_the_editors():
    """The a1 II's default Menu laid out here is the one the editor lays out, as its test writes it: the same entries,
    groups and lines. When the definition or the editor's layout changed on purpose, the editor's test writes the file
    again (CAMSET_BLESS=1 cargo test the_default_menu_is_the_golden_one, in editor/) and this one must then agree."""
    want = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert want["definition"] == paths.A1II
    compare_with_golden(definitions.load_public(paths.A1II), want)


def compare_with_golden(doc, want: dict) -> None:
    """The kit's Menu of `doc` is the golden one `want`: without the camera's menus its entries; with them, each menu's
    in the definition's order, laid out for the live settings saved in the golden's mode."""
    bless = ("cd editor && CAMSET_BLESS=1 cargo test the_default_menu_is_the_golden_one, then look at the diff and make "
             "kit/camkit/menu_rows.py agree")
    menus = mr.menu_list(doc)
    if "menus" not in want:
        assert not menus, f"the definition lists the camera's menus, the golden file none (after a change on purpose: {bless})"
        plans = [(None, None, want["entries"])]
    else:
        assert [m["name"] for m in menus] == [m["menu"] for m in want["menus"]], f"not the editor's menus (after a change on purpose: {bless})"
        plans = [(m["menu"], m["mode"], m["entries"]) for m in want["menus"]]
    for in_menu, mode, entries in plans:
        got = golden_shape(doc, in_menu=in_menu, mode=mode)
        where = f"{in_menu} > " if in_menu else ""
        assert [e["entry"] for e in got] == [e["entry"] for e in entries], f"{where}not the editor's entries (after a change on purpose: {bless})"
        for g, w in zip(got, entries, strict=True):
            assert [x["group"] for x in g["groups"]] == [x["group"] for x in w["groups"]], f"{where}{g['entry']} (after a change on purpose: {bless})"
            for a, b in zip(g["groups"], w["groups"], strict=True):
                assert a == b, f"{where}{g['entry']} > {a['group']}: the kit's layout is not the editor's (after a change on purpose: {bless})"


def test_a_definition_that_places_nothing_keeps_its_tabs_and_groups():
    """The editor lays rows out as on the camera only when the definition places a setting (camera_layout): one that
    places none has no entry for what the menus do not hold, and every setting stays in its own tab and group, in the
    definition's order."""
    doc = definitions.load_public(paths.A1II)
    for s in doc["settings"]:
        for f in ("row", "row_at", "under_option", "row_tab", "row_group", "row_mode"):
            s.pop(f, None)
    menu = mr.Menu(doc)
    entries = menu.entries(mr.shown(doc))
    assert not menu.camera and menu.off not in [e for e, _ in entries]
    for entry, settings in entries:
        assert all(x["tab"] == entry for x in settings) or entry in (mr.OTHER_TAB, menu.my_menu)
        groups = menu.groups(entry, settings)
        assert all(x["group"] == name for name, fam, rows in groups if not fam for r in rows for x in r)
        assert all(mr.lay_out(rows) == [("row", i, 0) for i in range(len(rows))] for _, fam, rows in groups if not fam)


def test_the_default_menu_is_the_live_settings_without_the_expert_ones():
    doc = definitions.load_public(paths.A1II)
    default, every = mr.shown(doc), mr.shown(doc, expert=True)
    assert {x["key"] for x in default} == {x["key"] for x in doc["settings"] if x["area"] == "global" and not x.get("expert")}
    assert len(every) == len(doc["settings"]) > len(default)
