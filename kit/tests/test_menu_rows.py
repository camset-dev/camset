"""camkit.menu_rows, the kit's copy of the editor's Menu "As on the camera": the cases of editor/src/menu_rows.rs's own
tests, made up the same way and expected the same, and the a1 II's public definition laid out whole.

Run: .venv/bin/python -m pytest kit/tests/test_menu_rows.py -q
"""
import json

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
    def on(key, name, row_, at):
        return s(key, name, ["Profile", "P1", *row_], [29, 1, *at], "P1", group="Profile P1", row_group="Profile P1")
    page = rows(on("bl", "Black Level", ["Black Level"], [0]), on("bls", "Black Level (stills)", ["Black Level"], [0]),
                on("bgl", "Black Gamma Level", ["Black Gamma", "Level"], [2, 1]), on("bgr", "Black Gamma Range", ["Black Gamma", "Range"], [2, 0]),
                on("km", "Knee Mode", ["Knee", "Mode"], [3, 0]), on("kmp", "Knee Auto Set Max Point", ["Knee", "Auto Set", "Max Point"], [3, 1, 0]),
                on("kmps", "Knee Auto Set Max Point (stills)", ["Knee", "Auto Set", "Max Point"], [3, 1, 0]))
    assert all(mr.on_page(x[0]) for x in page) and mr.page_prefix(page[0][0]) == 2
    assert mr.lay_out(page) == [row(0, 0), row(1, 0),
                                head("Black Gamma", 0, ["Black Gamma"]), row(3, 1), row(2, 1),
                                head("Knee", 0, ["Knee"]), row(4, 1), head("Auto Set", 1, ["Knee", "Auto Set"]), row(5, 2), row(6, 2)]
    two = page + [[{**page[0][0], "key": "p2", "under_option": "P2", "row": ["Profile", "P2", "Black Level"], "row_at": [29, 2, 0]}]]
    lines = mr.lay_out(two)
    assert lines[0] == head("P1", 0, ["P1"]) and lines[-1] == row(7, 1)


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
    for entry, settings in entries:
        held = {x["key"] for _, _, rows in menu.groups(entry, settings) for r in rows for x in r}
        assert held == {x["key"] for x in settings}, entry


GOLDEN = definitions.ROOT / "editor" / "tests" / "data" / "menu_ILCE-1M2_fw4.00.json"


def golden_shape(doc, expert: bool = False) -> list:
    """The Menu as editor/src/pages/menu.rs's the_default_menu_is_the_golden_one writes it: each entry the side bar
    lists (My Menu's tab has the My Menu page there), its groups, a family's table by its keys, every other group's
    lines (a row by its records' keys)."""
    menu = mr.Menu(doc)
    out = []
    for entry, settings in menu.entries(mr.shown(doc, expert)):
        if menu.has_my_menu and entry == menu.my_menu:
            continue
        groups = []
        for name, fam, rows in menu.groups(entry, settings):
            if fam:
                groups.append({"group": name, "family": True, "keys": [x["key"] for x in rows[0]]})
                continue
            lines = [["heading", x[1], x[2]] if x[0] == "heading" else ["row", [y["key"] for y in rows[x[1]]], x[2]] if x[0] == "row"
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
    got = golden_shape(definitions.load_public(paths.A1II))
    bless = ("cd editor && CAMSET_BLESS=1 cargo test the_default_menu_is_the_golden_one, then look at the diff and make "
             "kit/camkit/menu_rows.py agree")
    assert [e["entry"] for e in got] == [e["entry"] for e in want["entries"]], f"not the editor's entries (after a change on purpose: {bless})"
    for g, w in zip(got, want["entries"], strict=True):
        assert [x["group"] for x in g["groups"]] == [x["group"] for x in w["groups"]], f"{g['entry']} (after a change on purpose: {bless})"
        for a, b in zip(g["groups"], w["groups"], strict=True):
            assert a == b, f"{g['entry']} > {a['group']}: the kit's layout is not the editor's (after a change on purpose: {bless})"


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
