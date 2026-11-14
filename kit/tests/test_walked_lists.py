"""A picker's list walked whole (the hand tables' PICKER_LISTS, kit/writer/offered.py walked_lists): every setting the
list is for keeps exactly the codes its picker's walks wrote, judged by code, and the values a first kit listed from a
union of the camera's function codes go; each condition refuses rather than guesses, and a value the camera holds (in a
proof, the sample or one of its own downloads) is never dropped. Two lists are one where every label reads alike with the
same numbers, but at an icon place (icon_places: the reader gives an icon drawn by a function's name as differing
digits, so numbers are compared only where the function's code is read with the same numbers every time), and no label
reads nearer another place's than its own. A not-offered mark (NOT_OFFERED) on a key whose own row is a sample stands
on its twin's whole walk (twin_walks). A value the camera keeps for itself (UNPROVED kind "state") keeps no proof.
Made-up cameras for the rules; the a1 II's public data for its own entries. No camera, no runs."""
import copy
import difflib
import io
import json
import re
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, definitions, paths  # noqa: E402
from writer import hand_evidence, hand_facts, hand_tables  # noqa: E402
from camkit import match  # noqa: E402
from writer import offered as O  # noqa: E402
from writer.offered import icon_places, not_offered_marks, sample_values, twin_walks, walked_lists, walked_rows  # noqa: E402

A1 = paths.A1II
NAMES = {1: "Alpha", 2: "Bravo", 3: "Charlie", 4: "Delta", 7: "Fn code", 9: "Key only", 10: "Factory"}


def setting(key, codes, **more):
    return {"key": key, "name": key, "values": [[v, NAMES[v]] for v in codes], **more}


def cell(labels, **more):
    return {"opens": "picker", "wrapped": True, "options": [{"label": f"• {lab}"} for lab in labels], **more}


def rec(proved, **more):
    return {"verdict": "proved", "proved": proved, "notes": [], **more}


def change(key, before, after):
    """A proof line's change of `key` (a record, or one slot of an array record, "global:0x0100[0]")."""
    m = re.fullmatch(r"(.+)\[(\d+)\]", key)
    if not m:
        return [{"key": key, "before": before, "after": after}]
    was = [0] * (int(m[2]) + 1)
    now = list(was)
    was[int(m[2])], now[int(m[2])] = before, after
    return [{"key": m[1], "before": was, "after": now}]


def lines(row, n, labels=None, key=None, codes=None, start=0, **more):
    """The proof lines of a table row ("<path> / <cell>") choosing places 0 .. n-1, each planning its place's label
    (`labels`) and, with `key` and `codes`, writing its place's code there (the start's place changing nothing)."""
    path, _, option = row.partition(" / ")
    out = []
    for i in range(n):
        line = {"path": [path], "kind": "table", "option": option, "index": i, "applied": True, "planned": True, **more}
        if labels:
            line["label"] = labels[i]
        if key:
            line["changes"] = [] if i == start else change(key, codes[start], codes[i])
        out.append(line)
    return out


def labels_of(c, row):
    """The labels the table walk read on a row's cell (its screen the row's first part)."""
    return [o["label"] for o in O.walked_cells(c.tables, row.split(" / ")[0])[row][0]["options"]]


def relabel(c, row):
    """Each proof line of `row` planning the label the table walk now reads at its place."""
    for p in c.proofs:
        if " / ".join([" > ".join(p["path"]), p["option"]]) == row:
            p["label"] = labels_of(c, row)[p["index"]]


def camera():
    """A made-up camera: an array record of three Fn slots (slot 1 walked whole, the others a sample from the held
    option; slot 3 holds its factory value, which a NOT_OFFERED mark says the list cannot choose back) and two keys of
    one list (key 1 walked whole, key 2 a sample); each lists codes beyond its picker's list, as a first kit's union
    did. Its definition, report, table walk, entries (with their hand evidence), sample values, held values and the
    proof lines the report counts."""
    abc = ["Alpha", "Bravo", "Charlie"]
    return types.SimpleNamespace(
        doc={"settings": [setting("global:0x0100[0]", [1, 2, 3, 9, 10], proved={"values": [1, 2, 3]}),
                          setting("global:0x0100[1]", [1, 2, 3, 9, 10]),
                          setting("global:0x0100[2]", [1, 2, 3, 9, 10]),
                          setting("global:0x0200", [1, 2, 4, 7], proved={"values": [1, 2, 4]}),
                          setting("global:0x0201", [1, 2, 4, 7]),
                          setting("global:0x0300", [1, 2, 9])]},
        tables={"Fn": {"path": ["Fn"], "screen": "fnmenu", "cells": [
                    {"pos": [0, i], "row_label": "Still Upper", "col_label": str(i + 1), **cell(abc[i:] + abc[:i])}
                    for i in range(3)]},
                "Keys": {"path": ["Keys"], "screen": "keyset", "pages": [{"tab": 0, "title": "Page 1", "items": [
                    {"row": 0, "key": "Key 1", **cell(["Alpha", "Bravo", "Delta"])},
                    {"row": 1, "key": "Key 2", **cell(["Delta", "Alpha", "Bravo"])}]}]}},
        report=[{"row": "Fn / Still Upper / 1", "records": {"global:0x0100[0]": rec({"Alpha": 1, "Bravo": 2, "Charlie": 3})}},
                {"row": "Fn / Still Upper / 2", "records": {"global:0x0100[1]": rec({"Alpha": 1}, sampled_from_start=True)}},
                {"row": "Fn / Still Upper / 3", "records": {"global:0x0100[2]": rec({"Charlie": 3}, sampled_from_start=True)}},
                {"row": "Keys / Key 1 @0.key.0", "records": {"global:0x0200": rec({"Alpha": 1, "Bravo": 2, "Delta": 4})}},
                {"row": "Keys / Key 2 @0.key.1", "records": {"global:0x0201": rec({"Bravo": 2}, sampled_from_start=True)}}],
        entries={"Fn": {"keys": r"^global:0x0100\[", "walk": r"^Fn / Still Upper / 1$", "table": ("Fn", "Still"),
                        "why": "Walked full circle.", "evidence": "walked whole"},
                 "Keys": {"keys": r"^global:0x020[01]$", "walk": r"^Keys / Key 1 @", "table": ("Keys", None),
                          "why": "Walked full circle.", "evidence": "walked whole"}},
        factory={"global:0x0100[0]": 1, "global:0x0100[1]": 2, "global:0x0100[2]": 10, "global:0x0200": 4,
                 "global:0x0201": 1, "global:0x0300": 9},
        held={"global:0x0100[2]": {10}},
        proofs=lines("Fn / Still Upper / 1", 3, ["• Alpha", "• Bravo", "• Charlie"], "global:0x0100[0]", [1, 2, 3])
        + lines("Keys / Key 1 @0.key.0", 3, ["• Alpha", "• Bravo", "• Delta"], "global:0x0200", [1, 2, 4]))


def cut(c, only=None, **over):
    """walked_lists on camera `c` (its entries, or `only` of them, each field `over` given in their place)."""
    entries = {name: dict(e, **over) for name, e in c.entries.items() if only is None or name == only}
    return walked_lists(c.doc, entries, c.report, c.tables, c.factory, c.held, c.proofs)


def codes(doc):
    return {s["key"]: [v for v, _ in s["values"]] for s in doc["settings"]}


def refused(c, words, only=None, **over):
    before = codes(c.doc)
    out = io.StringIO()
    with redirect_stdout(out):
        got = cut(c, only, **over)
    assert got[:2] == (0, 1 if only else len(c.entries)) and codes(c.doc) == before, out.getvalue()
    assert words in out.getvalue(), out.getvalue()


def test_a_list_walked_whole_keeps_exactly_the_codes_its_walks_wrote(capsys):
    """Each setting an entry covers keeps the codes its picker's walk wrote: a code one slot's walk wrote stands for
    the record's other slots, and one key's walk for a key whose picker the table walk shows lists the same functions in
    the same order (each list turned round to its own function); a value the camera holds though the list cannot choose
    it (held) stays; a setting no entry covers is left alone; each setting is said with how many values went, and a
    second run takes nothing more out. With no runs here the camera's downloads are not checked, and it says so."""
    c = camera()
    assert cut(c) == (7, 0, {"global:0x0100[0]": 2, "global:0x0100[1]": 2, "global:0x0100[2]": 1, "global:0x0200": 1,
                             "global:0x0201": 1})
    assert codes(c.doc) == {"global:0x0100[0]": [1, 2, 3], "global:0x0100[1]": [1, 2, 3], "global:0x0100[2]": [1, 2, 3, 10],
                            "global:0x0200": [1, 2, 4], "global:0x0201": [1, 2, 4], "global:0x0300": [1, 2, 9]}
    out = capsys.readouterr().out
    assert "walked lists: 7 values the pickers never offer taken out of 5 settings, by 2 lists walked whole; 0 refused" in out
    assert "  walked list  global:0x0100[0] global:0x0100[0]: 2 taken out, 3 left (Fn)" in out
    assert "no camera downloads on this computer to check the cut lists against, not checked" in out
    assert cut(c)[:2] == (0, 0)


def test_a_list_not_walked_round_or_not_one_list_is_not_cut():
    """Every covered setting's picker must have gone round to its start in the table walk and list the same functions
    in the same order as the walked one: a list not walked round, or another list on one slot, leaves every list of the
    entry as it was, said."""
    c = camera()
    c.tables["Fn"]["cells"][2]["wrapped"] = False
    refused(c, "Fn / Still Upper / 3's list on 'Fn' was not walked round", "Fn")
    c = camera()
    c.tables["Keys"]["pages"][0]["items"][1]["options"][0]["label"] = "• Echo"
    refused(c, "is not the walked one", "Keys")


def test_numbered_look_alikes_are_two_lists():
    """OCR's tolerance takes "Hold 3" for "Hold 4" (a short label one character apart), so the lists must hold the same
    numbers place by place too: key 1 walked Hold 1, Hold 2, Hold 3; key 2's picker lists Hold 4 where key 1's lists
    Hold 3, and key 1's codes are not lent to it. The same before a twin's walk stands for a not-offered mark."""
    c = camera()
    c.tables["Keys"]["pages"][0]["items"][0]["options"] = cell(["Hold 1", "Hold 2", "Hold 3"])["options"]
    c.tables["Keys"]["pages"][0]["items"][1]["options"] = cell(["Hold 4", "Hold 1", "Hold 2"])["options"]
    relabel(c, "Keys / Key 1 @0.key.0")
    refused(c, "Keys / Key 2 @0.key.1's list on 'Keys' is not the walked one (other functions, numbers or order)", "Keys")
    assert match.same_functions(["• Hold 1", "• Hold 3"], ["• Hold 1", "• Hold 4"])            # the provers' tolerance
    assert not match.same_functions(["• Hold 1", "• Hold 3"], ["• Hold 1", "• Hold 4"], numbers=True)
    assert twin_walks(c.report, "global:0x0201", r"^Keys / ", c.tables, c.proofs) == []


# A Custom Key list as the a1 II's screens read it: each function's code (made up where it is not the a1 II's), its
# label on key 1's cell in the table walk, the menu's reading when key 1's walk chose it ("shown") and its label on key
# 2's cell. The camera draws an icon by some names, which the reader gives as differing digits or letters (the shapes
# the a1 II's lists hold); a name with a real number in it is read with that number every time.
ICONS = [(195, "• 8Var. Shutter", "S Var. Shutter", "• S Var. Shutter"),
         (2251, "• Recall Custom hold 1", "Recall Custom hold 1", "• Recall Custom hold 1"),
         (2252, "• Recall Custom hold 2", "Recall Custom hold 2", "• Recall Custom hold 2"),
         (2253, "• Recall Custom hold 3", "Recall Custom hold 3", "• Recall Custom hold 3"),
         (782, "• Add Rating (11)", "Add Rating (**)", "• Add Rating (**)"),
         (783, "• Add Rating (34)", "Add Rating (24)", "• Add Rating (24)"),
         (101, "SAPS-C S35Shooting", "APS-C S3SShooting", "• S APS-CS3SShooting"),
         (2201, "• Zoom Operation (T)", "Zoom Operation (T)", "• Zoom Operation (T)"),
         (2202, "• Zoom Operation (W)", "Zoom Operation (W)", "• Zoom Operation (W)"),
         (2499, "• Tracking On E + A54", "Tracking On E + Aw", "• Tracking On E + Aw"),
         # functions the camera also has outside this list, and functions under two codes, read alike
         (2810, "• Clip Flag OK", "Clip Flag OK", "• Clip Flag OK"),
         (271, "• Wireless Flash", "Wireless Flash", "• Wireless Flash"),
         (2110, "• Pre-Capture", "Pre-Capture", "• Pre-Capture"),
         # the readings that once tripped a guard on the a1 II: Fixed Speed STBY and REC each under two codes, told
         # apart only by an icon, and the rating stars, each code its own place in the list
         (222, "• Fixed Speedd Siy", "Fixed Speedd Siy", "• Fixed Speedd Siy"),
         (227, "• î Fixed Speed SBY", "î Fixed Speed SBY", "• î Fixed Speed SiY"),
         (223, "• Fixed Speed N", "Fixed Speed N", "• Fixed Speed Ré"),
         (228, "î Fixed Speed REC", "î Fixed Speed REC", "î Fixed Speed REC"),
         (779, "• Add Rating (*)", "Add Rating (*)", "• Add Rating (*)"),
         (780, "• Add Rating (*+)", "Add Rating (*+)", "• Add Rating (*+)"),
         (781, "• Add Rating (**)", "Add Rating (**)", "• Add Rating (**)")]
ICON_PLACES = {0, 4, 5, 6, 9}          # the places whose code the readings give with more than one set of numbers
TURN = 3                               # key 2's list starts at its own saved function, 3 places on
PLACE = {x[0]: i for i, x in enumerate(ICONS)}
# what the camera's Fn menu showed (another picker screen): (code, its label there, the menu's reading when chosen).
# Clip Flag KEEP and Wireless Test Flash are functions outside the keys' list; Clip Flag OK and Pre-Capture stand
# under another code there (2997, 2081) than in the keys' list (2810, 2110), one name under two codes
VOCAB = [(2812, "• Clip Flag KEEP", "Clip Flag KEEP"), (2997, "• Clip Flag OK", "Clip Flaq OK"),
         (812, "• Wireless Test Flash", "Wireless Test Flash"), (2081, "• Pre-Capture", "Pre-Captue")]


def icon_camera(start=7, shown=None, key2=None, key2_lines=()):
    """A made-up camera with the a1 II's icon readings: key 1 (a whole record) walked whole from its start (the place
    whose line changes nothing), key 2 a sample whose cell is the same list turned round (TURN), as the table walk read
    them; each lists the Fn menu's code 2081 too, a first kit's union. Its Fn menu (VOCAB) shows functions the keys'
    list does not offer. `shown` the menu's reading at each of key 1's choices (ICONS' by default), `key2` key 2's cell
    in ICONS' order, `key2_lines` [(its place in ICONS, the menu's reading)] of key 2's sample, each line writing that
    place's code."""
    codes = [x[0] for x in ICONS]
    walked = [x[1] for x in ICONS]
    shown = shown or [x[2] for x in ICONS]
    key2 = key2 or [x[3] for x in ICONS]
    turned = key2[TURN:] + key2[:TURN]
    values = [[v, f"F{v}"] for v in [*codes, 2081]]
    fn = [{"path": ["Fn"], "kind": "table", "option": "Upper / 1", "index": i, "label": label, "shown": text,
           "applied": True, "planned": True, "changes": [{"key": "global:0x0300", "before": 1, "after": code}]}
          for i, (code, label, text) in enumerate(VOCAB)]
    key1 = [{"path": ["Keys"], "kind": "table", "option": "Key 1 @0.key.0", "index": i, "label": walked[i],
             "shown": shown[i], "applied": True, "planned": True,
             "changes": [] if i == start else [{"key": "global:0x0200", "before": codes[start], "after": codes[i]}]}
            for i in range(len(codes))]
    key2_ = [{"path": ["Keys"], "kind": "table", "option": "Key 2 @0.key.1", "index": (i - TURN) % len(codes),
              "label": key2[i], "shown": text, "applied": True, "planned": True,
              "changes": [{"key": "global:0x0201", "before": codes[TURN], "after": codes[i]}]} for i, text in key2_lines]
    return types.SimpleNamespace(
        doc={"settings": [{"key": "global:0x0200", "name": "Key 1", "values": copy.deepcopy(values), "proved": {"values": codes}},
                          {"key": "global:0x0201", "name": "Key 2", "values": copy.deepcopy(values)}]},
        tables={"Keys": {"path": ["Keys"], "screen": "keyset", "pages": [{"tab": 0, "title": "Page 1", "items": [
            {"row": 0, "key": "Key 1", "opens": "picker", "wrapped": True, "options": [{"label": t} for t in walked]},
            {"row": 1, "key": "Key 2", "opens": "picker", "wrapped": True, "options": [{"label": t} for t in turned]}]}]},
                "Fn": {"path": ["Fn"], "screen": "fnmenu", "cells": [{"pos": [0, 0], "row_label": "Upper", "col_label": "1",
                                                                   "opens": "picker", "wrapped": True,
                                                                   "options": [{"label": x[1]} for x in VOCAB]}]}},
        report=[{"row": "Keys / Key 1 @0.key.0", "records": {"global:0x0200": rec(dict(zip(walked, codes, strict=True)))}},
                {"row": "Keys / Key 2 @0.key.1", "records": {"global:0x0201": rec(
                    {key2[i]: codes[i] for i in [TURN, *(i for i, _ in key2_lines)]}, sampled_from_start=True)}},
                {"row": "Fn / Upper / 1", "records": {"global:0x0300": rec({x[1]: x[0] for x in VOCAB})}}],
        entries={"Keys": {"keys": r"^global:0x020[01]$", "walk": r"^Keys / Key 1 @", "table": ("Keys", None),
                          "why": "Walked full circle.", "evidence": "walked whole"}},
        factory={"global:0x0200": codes[start], "global:0x0201": codes[TURN]}, held={}, proofs=key1 + key2_ + fn)


def places(c):
    return icon_places("Keys", "Keys / Key 1 @0.key.0", "global:0x0200", c.report, c.tables, c.proofs)


def key2(changed: dict) -> list:
    """Key 2's cell in ICONS' order, each place in `changed` read otherwise."""
    return [changed.get(i, x[3]) for i, x in enumerate(ICONS)]


def test_an_icon_read_as_digits_does_not_make_two_lists():
    """Where the camera draws an icon by a function's name, the reader gives it differing digits or letters from screen
    to screen ("8Var. Shutter" and "S Var. Shutter"; the rating stars "(11)" and "(**)", "(34)" and "(24)"; a frame
    icon "A54" and "Aw"), so numbers are compared only at places whose code the camera's readings give with the same
    numbers every time: there key 2's list is key 1's, and both keys keep exactly the walked codes."""
    c = icon_camera()
    assert places(c) == ICON_PLACES
    assert cut(c) == (2, 0, {"global:0x0200": 1, "global:0x0201": 1})
    assert codes(c.doc)["global:0x0201"] == [x[0] for x in ICONS]
    walked, turned = (c.tables["Keys"]["pages"][0]["items"][k]["options"] for k in (0, 1))
    a, b = [o["label"] for o in turned], [o["label"] for o in walked]
    assert not match.same_functions(a, b, numbers=True)                   # the numbers rule alone refuses them
    assert match.same_functions(a, b, numbers=True, free=ICON_PLACES)


def test_a_code_read_with_one_set_of_numbers_is_no_icon_place():
    """A code the readings give with one set of numbers everywhere is no icon place: with the menu's readings the same
    as the cells', no place of key 1's walk is free, and key 2's icon readings make another list; the start, where no
    line of the walk wrote a code, is none either, though the code's readings elsewhere on the screen differ."""
    c = icon_camera(shown=[x[1] for x in ICONS])
    assert places(c) == frozenset()
    refused(c, "Keys / Key 2 @0.key.1's list on 'Keys' is not the walked one (other functions, numbers or order)")
    c = icon_camera(start=9, key2_lines=[(9, "Tracking On E + A54")])     # key 2's sample read the frame icon both ways
    assert places(c) == ICON_PLACES - {9}
    refused(c, "is not the walked one")
    c = icon_camera(start=9, key2=key2({9: "• Tracking On E + A54"}), key2_lines=[(9, "Tracking On E + A54")])
    assert cut(c)[:2] == (2, 0)


def test_a_real_number_misread_passes_only_where_its_code_is_read_both_ways():
    """The one real number the reader misread on the a1 II ("S35" read "S3S"): key 2's list passes only because that
    code's readings hold two sets of numbers; read "S35" every time it is refused."""
    lone = key2({i: x[1] for i, x in enumerate(ICONS) if i != 6})
    c = icon_camera(shown=[x[1] if i != 6 else "APS-C S3SShooting" for i, x in enumerate(ICONS)], key2=lone)
    assert places(c) == {6}
    assert cut(c)[:2] == (2, 0)
    c = icon_camera(shown=[x[1] for x in ICONS], key2=lone)
    refused(c, "is not the walked one")


def test_a_real_numbered_look_alike_is_still_refused():
    """A function whose name holds a real number is read with that number every time, so its place is never an icon
    place: key 2's list holding "Recall Custom hold 3" where key 1's walked list holds "hold 2" is another list, though
    OCR's tolerance takes one for the other and other places of the list are icon places."""
    c = icon_camera(key2=key2({2: "• Recall Custom hold 3"}), key2_lines=[(3, "Recall Custom hold 3")])
    assert places(c) == ICON_PLACES and not {1, 2, 3} & places(c)
    refused(c, "Keys / Key 2 @0.key.1's list on 'Keys' is not the walked one (other functions, numbers or order)")
    a = [o["label"] for o in c.tables["Keys"]["pages"][0]["items"][1]["options"]]
    assert match.same_functions(a, [x[1] for x in ICONS])                 # the tolerance alone takes them for one


def test_an_icon_place_does_not_excuse_another_function():
    """At an icon place only the numbers are excused: a label that does not read near the walked one there (another
    function) still makes another list."""
    c = icon_camera(key2=key2({0: "• S Grid Line Display"}))
    assert 0 in places(c)
    refused(c, "is not the walked one (other functions, numbers or order)")


OTHER_SET = "reads, at some place, nearer a function outside the walked list than the walked one there (it may offer " \
            "another set of functions)"


def test_a_cell_offering_a_function_outside_the_walked_list_is_refused():
    """OCR's tolerance takes "Clip Flag KEEP" for "Clip Flag OK" (0.818) and "Wireless Test Flash" for "Wireless Flash"
    (0.867), so a cell offering one of them in the other's place passes place by place; but the camera's screens show
    that function under a code outside the walked list, and the cell's label reads nearer it than the walked function
    there: the cell may offer another set of functions, and the entry is refused (judged by the readings of every
    picker screen, picker_readings)."""
    for place, label in ((2810, "• Clip Flag KEEP"), (271, "• Wireless Test Flash")):
        c = icon_camera(key2=key2({PLACE[place]: label}))
        a = [o["label"] for o in c.tables["Keys"]["pages"][0]["items"][1]["options"]]
        assert match.same_functions(a, [x[1] for x in ICONS], numbers=True, free=places(c)), label
        refused(c, f"Keys / Key 2 @0.key.1's list on 'Keys' {OTHER_SET}")
    assert {2812, 812, 2081, 2997} <= set(O.picker_readings(c.tables, c.report, c.proofs))


def test_a_swap_or_one_name_under_two_codes_passes_the_vocabulary_check():
    """What no label tells apart passes, for the codes say it: a list holding two look-alikes of the walked list the
    other way round ("Zoom Operation (T)" and "(W)") offers the same set of codes, a picker never listing a function
    twice, so the cut is the same; a label read nearer a function outside the list that shares the walked function's
    name under another code (Clip Flag OK, Pre-Capture: readings within SAME_NAME) is passed over, kept_codes and
    check_cut_downloads standing there; the a1 II's Fixed Speed and rating star readings, all functions of the walked
    list, pass (key 2's cell holds them by default)."""
    c = icon_camera(key2=key2({7: "• Zoom Operation (W)", 8: "• Zoom Operation (T)"}))
    assert cut(c)[:2] == (2, 0)
    c = icon_camera(key2=key2({PLACE[2810]: "• Clip Flaq OK", PLACE[2110]: "• Pre-Captue"}))
    assert cut(c)[:2] == (2, 0)
    c = icon_camera()
    assert cut(c)[:2] == (2, 0) and key2({})[PLACE[227]] != ICONS[PLACE[227]][1]


def test_the_same_name_rule_is_what_lets_a_shared_name_pass(monkeypatch):
    """Without the same-name rule (SAME_NAME out of reach) a label of Clip Flag OK read nearer the other code's
    reading would stand for another function; with it, it does not."""
    c = icon_camera(key2=key2({PLACE[2810]: "• Clip Flaq OK"}))
    readings = O.picker_readings(c.tables, c.report, c.proofs)
    walked = [x[1] for x in ICONS]
    codes_ = O.walk_codes("Keys / Key 1 @0.key.0", "global:0x0200", c.proofs, {x[0] for x in ICONS}, len(ICONS))
    assert codes_ == {i: x[0] for i, x in enumerate(ICONS)}                 # its start's code given by the others
    cell = key2({PLACE[2810]: "• Clip Flaq OK"})
    assert O.stands_for_other(cell, walked, 0, codes_, {x[0] for x in ICONS}, readings) is None
    monkeypatch.setattr(O, "SAME_NAME", 1.01)
    assert O.stands_for_other(cell, walked, 0, codes_, {x[0] for x in ICONS}, readings) == PLACE[2810]


def test_with_no_readings_an_entry_is_refused():
    """A camera whose table walk gave no function readings (no counted proof line wrote a code on a picker screen):
    nothing shows a cell offers no function outside the walked list, so the entry is refused, said, and so is a twin's
    walk; with readings the check runs and names the label that tripped it."""
    c = camera()
    for p in c.proofs:
        p.pop("changes")
    refused(c, "the table walk's picker screens gave no function readings (no counted proof line wrote a code on "
               "them), so nothing shows its cells offer no function outside the walked list")
    cell = [x[1] if i != PLACE[2810] else "• Clip Flag KEEP" for i, x in enumerate(ICONS)]
    walked, codes_ = [x[1] for x in ICONS], {i: x[0] for i, x in enumerate(ICONS)}
    readings = O.picker_readings(icon_camera().tables, icon_camera().report, icon_camera().proofs)
    assert "gave no function readings" in O.differs(cell, walked, ICON_PLACES, codes_, set(codes_.values()), {})
    assert O.differs(cell, walked, ICON_PLACES, codes_, set(codes_.values()), readings) == \
        f"{OTHER_SET}: '• Clip Flag KEEP' where the walked list reads '• Clip Flag OK'"


def test_each_entry_says_its_vocabulary_and_the_codes_taken_as_one_name(capsys):
    """Each entry cut says how many functions outside its walked list the picker screens showed and which codes were
    taken as one name (the same name under two codes, passed over)."""
    c = icon_camera(key2=key2({PLACE[2810]: "• Clip Flaq OK", PLACE[2110]: "• Pre-Captue"}))
    assert cut(c)[:2] == (2, 0)
    assert "  vocabulary  Keys: 4 functions the picker screens showed outside its walked list; codes taken as one " \
           "name: 2110 and 2081, 2810 and 2997" in capsys.readouterr().out
    assert cut(icon_camera())[:2] == (2, 0)
    out = capsys.readouterr().out
    assert "codes taken as one name: none" in out and "  icon numbers  Keys: excused as naming no other function: none" in out
    assert cut(icon_camera(key2=key2({0: "• 7Var. Shutter"})))[:2] == (2, 0)
    assert "  icon numbers  Keys: excused as naming no other function: '• 7Var. Shutter' where the walked list reads " \
           "'• 8Var. Shutter'" in capsys.readouterr().out


def test_the_quick_bounds_change_no_answer():
    """nearer's bounds (real_quick_ratio, quick_ratio) only skip ratios that cannot beat the threshold: every pair of
    the fixtures' readings, at every threshold the pairs give, answers the same with them and without, and so does
    the vocabulary check on every cell the tests build."""
    labels = sorted({t for x in ICONS for t in x[1:]} | {t for x in VOCAB for t in x[1:]} | {"", "• Clip Flag KEEP"})
    names = [O._name(t) for t in labels]
    owns = sorted({difflib.SequenceMatcher(None, a[0], b[0]).ratio() for a in names for b in names})
    for own in owns[::7] + [0.0, 0.5, 0.8, 0.95, 1.0]:
        for a in names:
            for b in names:
                assert O.nearer(a, b, own) == O.nearer(a, b, own, quick=False), (a[0], b[0], own)
    c = icon_camera()
    readings = O.picker_readings(c.tables, c.report, c.proofs)
    walked, codes_ = [x[1] for x in ICONS], {i: x[0] for i, x in enumerate(ICONS)}
    for changed in ({}, {PLACE[2810]: "• Clip Flag KEEP"}, {PLACE[271]: "• Wireless Test Flash"},
                    {PLACE[2810]: "• Clip Flaq OK"}, {PLACE[2110]: "• Pre-Captue"}, {7: "• Zoom Operation (W)"}):
        cell = key2(changed)
        assert O.stands_for_other(cell, walked, 0, codes_, set(codes_.values()), readings) == \
            O.stands_for_other(cell, walked, 0, codes_, set(codes_.values()), readings, quick=False), changed


def key1_line(c, place):
    """Key 1's counted proof line at a place of its list."""
    return next(p for p in c.proofs if p["option"] == "Key 1 @0.key.0" and p["index"] == place)


def show_on_fn(c, code, label, shown=None):
    """The camera's Fn menu shows another function: a place of its cell, and a counted line writing its code."""
    c.tables["Fn"]["cells"][0]["options"].append({"label": label})
    c.report[-1]["records"]["global:0x0300"]["proved"][label] = code
    c.proofs.append({"path": ["Fn"], "kind": "table", "option": "Upper / 1",
                     "index": len(c.tables["Fn"]["cells"][0]["options"]) - 1, "label": label, "shown": shown or label,
                     "applied": True, "planned": True,
                     "changes": [{"key": "global:0x0300", "before": 1, "after": code}]})


def test_numbers_at_an_icon_place_matter_only_where_they_may_name_another_function():
    """At an icon place a cell label may hold numbers the camera never read for that code only where they cannot name
    another function: every function the camera showed under a name near the label's (digits aside) is in the walked
    list, and either there is only one ("7Var. Shutter" where Var. Shutter has no sibling) or the reader gives two of
    them the same numbers. A near name outside the list ("Var. Shutter Set.", shown on the Fn menu) or siblings each
    read with numbers of their own ("Recall Custom hold 7" where hold 2 was misread once: hold 1, 2 and 3 read their
    own digits) refuse it, the words naming the labels."""
    c = icon_camera(key2=key2({0: "• 7Var. Shutter"}))
    assert 0 in places(c) and cut(c)[:2] == (2, 0)
    c = icon_camera(key2=key2({0: "• 7Var. Shutter"}))
    show_on_fn(c, 196, "• Var. Shutter Set.")
    refused(c, "Keys / Key 2 @0.key.1's list on 'Keys' reads at an icon place numbers the camera never read for that "
               "function ('• 7Var. Shutter' where the walked list reads '• 8Var. Shutter')")
    shown = [x[2] for x in ICONS]
    shown[2] = "Recall Custom hoid Z"                                     # hold 2 misread once: its place is free
    c = icon_camera(shown=shown, key2=key2({2: "• Recall Custom hold 7"}))
    assert 2 in places(c)
    refused(c, "('• Recall Custom hold 7' where the walked list reads '• Recall Custom hold 2')")
    c = icon_camera(shown=shown)                                          # read as the walk read it: one list
    assert cut(c)[:2] == (2, 0)


# the a1 II's own readings of the two shapes the strict rule refused: a leading icon read "8" before Zebra Level (its
# other readings "9", "S", "f"), and the rating stars, read as asterisks, letters or digits, two, three and four
# stars alike "(**)", five stars "(14)", "(2)", "(24)", "(34)"
ZEBRA = {289: {"9Zebra Level", "SZebra Level", "fZebra Level", "• fZebra Level"},
         288: {"§ Zebra Display", "S Zebra Display", "SZebra Display", "&Zebra Display"},
         229: {"• 9Grid Line Display", "S Grid Line Display"}}
STARS = {779: {"Add Rating (*)", "• Add Rating (*)"},
         780: {"Add Rating (**)", "Add Rating (*+)", "• Add Rating (**)", "• Add Rating (*+)"},
         781: {"Add Rating (**)", "• Add Rating (**)"},
         782: {"Add Rating (#t)", "Add Rating (11)", "Add Rating (1t)", "• Add Rating (**)", "• Add Rating (11)"},
         783: {"Add Rating (14)", "Add Rating (2)", "Add Rating (24)", "Add Rating (34)", "• Add Rating (24)",
               "• Add Rating (34)"}}
STAR_LIST = ["• Add Rating (*)", "• Add Rating (**)", "• Add Rating (**)", "• Add Rating (**)", "• Add Rating (34)"]


def test_the_a1_iis_icon_and_star_readings_pass_where_no_other_function_can_hide():
    """The two refusals of the a1 II's real check: "8Zebra Level" where the walked list reads "fZebra Level" (no other
    Zebra Level, so the digit is the icon's), and "(3t)" where it reads "(34)" (every rating in the walked list, and the
    reader gives two, three and four stars the same "(**)": the stars' digits tell no rating from another). Both pass;
    the codes of the ratings are proved by the walk's place-by-place proofs and the code checks, not by their labels.
    Either is refused once a function of that name stands outside the walked list, and the stars are refused when each
    rating is read with numbers of its own."""
    b, codes_ = ["• fZebra Level", "• 9Grid Line Display"], {0: 289, 1: 229}
    assert O.differs(["8Zebra Level", "S Grid Line Display"], b, frozenset({0, 1}), codes_, {289, 229}, ZEBRA) is None
    assert "numbers the camera never read" in O.differs(["8Zebra Level", "S Grid Line Display"], b, frozenset({0, 1}),
                                                        codes_, {289, 229}, {**ZEBRA, 9289: {"Zebra Level"}})
    codes_ = {i: 779 + i for i in range(5)}
    cell = STAR_LIST[:4] + ["• Add Rating (3t)"]
    assert O.differs(cell, STAR_LIST, frozenset({3, 4}), codes_, set(STARS), STARS) is None
    assert not O.numbers_matter("• Add Rating (3t)", 783, set(STARS), STARS)
    assert O.numbers_matter("• Add Rating (3t)", 783, set(STARS) - {781}, STARS)       # a rating outside the list
    # a rating outside the list read with many digits is near once the digits are aside; with no readings of the
    # walked code at the place (or no code there), nothing shows the label names it
    assert O.numbers_matter("• Add Rating (3t)", 783, set(STARS), {**STARS, 9783: {"Add Rating (1234567)"}})
    assert O.numbers_matter("• Add Rating (3t)", None, set(STARS), STARS)
    far = {**STARS, 999: {"Zebra Level 1", "Zebra Level 2", "Zebra Level 3"}}     # the place's code named otherwise
    assert O.numbers_matter("• Add Rating (3t)", 999, set(far), far)
    assert O.numbers_matter("8Zebra Level", 289, {289}, {k: v for k, v in ZEBRA.items() if k != 289})
    told = {779: {"Add Rating (1)"}, 780: {"Add Rating (2)"}, 781: {"Add Rating (3)"}, 782: {"Add Rating (4)"},
            783: {"Add Rating (5)", "Add Rating (55)"}}                   # each rating read with its own digits
    assert O.numbers_matter("• Add Rating (3t)", 783, set(told), told)
    assert "('• Add Rating (3t)' where the walked list reads '• Add Rating (34)')" in \
        O.differs(cell, STAR_LIST, frozenset({3, 4}), codes_, set(told), told)
    # five stars read three ways itself ("(5)", "(55)", "(34)"): its digits name nothing at its place, so "(3t)" passes,
    # though three stars reads "(3)": every rating is in the walked list, so whichever the cell holds there the cut
    # keeps its code
    assert O.differs(cell, STAR_LIST, frozenset({3, 4}), codes_, set(told),
                     {**told, 783: told[783] | {"• Add Rating (34)"}}) is None


def test_a_shared_misreading_lifts_the_numbers_only_at_its_own_function_s_place():
    """The reader giving one sibling another's digits lifts the numbers check only at that function's own place, never
    across the family: hold 2 once read "hold 1" leaves hold 3's place, misread once without its digit, refusing "hold
    7" (a function no screen showed); hold 3 once read "hold 1" itself lifts it there. A reading without digits shared
    by two siblings tells nothing of their digits and lifts nothing."""
    h2, h3 = PLACE[2252], PLACE[2253]
    for misreads in ({h2: "Recall Custom hold 1", h3: "Recall Custom hoid Z"}, {h3: "Recall Custom hoid Z"}):
        shown = [x[2] for x in ICONS]
        for i, text in misreads.items():
            shown[i] = text
        c = icon_camera(shown=shown, key2=key2({h3: "• Recall Custom hold 7"}))
        assert h3 in places(c)
        refused(c, "('• Recall Custom hold 7' where the walked list reads '• Recall Custom hold 3')")
    shown = [x[2] for x in ICONS]
    shown[h3] = "Recall Custom hold 1"
    c = icon_camera(shown=shown, key2=key2({h3: "• Recall Custom hold 7"}))
    assert h3 in places(c) and cut(c)[:2] == (2, 0)
    holds = {2251: {"Recall Custom hold 1", "Recall Custom hoid"}, 2252: {"Recall Custom hold 2"},
             2253: {"Recall Custom hold 3", "Recall Custom hoid"}}
    assert O.numbers_matter("• Recall Custom hold 7", 2253, set(holds), holds)


def test_an_icon_place_takes_the_numbers_its_own_screen_read():
    """The numbers an icon place accepts, and whether its function's readings disagree, are those of the entry's own
    screen: another screen reading the same code "hold 7", "hold 5" and "hold 6" (the Fn menu's, say) lets no cell read
    "hold 7" where the keys' screen reads hold 2 its own way."""
    shown = [x[2] for x in ICONS]
    shown[PLACE[2252]] = "Recall Custom hoid Z"
    c = icon_camera(shown=shown, key2=key2({PLACE[2252]: "• Recall Custom hold 7"}))
    for n in (7, 5, 6):
        show_on_fn(c, 2252, f"• Recall Custom hold {n}")
    assert {"• Recall Custom hold 7"} < O.picker_readings(c.tables, c.report, c.proofs)[2252]
    refused(c, "('• Recall Custom hold 7' where the walked list reads '• Recall Custom hold 2')")


def test_one_name_under_two_codes_holds_the_same_numbers():
    """A long numbered name reads above SAME_NAME beside its neighbour ("Recall Shooting Set. Memory 2" and "Memory 4",
    0.958), yet the numbers tell them apart: they are never taken as one name, and a cell reading the other one where
    the walked list has its own stands for another function, its place an icon place or not."""
    readings = {2262: {"• Recall Shooting Set. Memory 2"}, 2264: {"• Recall Shooting Set. Memory 4"},
                2110: {"• Pre-Capture"}, 2081: {"Pre-Capture"}}
    assert match.nearness("Recall Shooting Set. Memory 2", "Recall Shooting Set. Memory 4") > O.SAME_NAME
    assert not O.same_name(2262, 2264, readings) and O.same_name(2110, 2081, readings)
    assert O.stands_for_other(["• Recall Shooting Set. Memory 4"], ["• Recall Shooting Set. Memory 2"], 0, {0: 2262},
                              {2262}, readings) == 0


def test_a_line_on_a_list_the_table_walk_read_again_is_refused_or_left_out():
    """A proof line's place is the table walk's only while the label it planned reads the cell's label there: a walk
    line planning another label, or one past the list's end, refuses the entry (the table walk was read again since
    the walk); another row's such line gives no readings, so it frees no place."""
    c = icon_camera()
    key1_line(c, 1)["label"] = "• Zoom Operation (W)"
    refused(c, "Keys / Key 1 @0.key.0 has 1 proof lines planning another label than the table walk's at their place "
               "('• Zoom Operation (W)' where the walk reads '• Recall Custom hold 1'): the table walk was read again "
               "since the walk")
    c = icon_camera()
    c.proofs.append({**key1_line(c, 1), "index": len(ICONS)})
    refused(c, f"Keys / Key 1 @0.key.0 has a proof line past its list's {len(ICONS)} places")
    c = icon_camera(shown=[x[1] for x in ICONS], key2_lines=[(0, "• S Var. Shutter")])
    assert places(c) == {0}                                               # key 2's line read Var. Shutter otherwise
    line = next(p for p in c.proofs if p["option"] == "Key 2 @0.key.1" and p.get("changes"))
    line["label"] = "• Zoom Operation (W)"                                # the same line, planned on another list
    assert places(c) == frozenset()


def test_each_reading_counts_and_only_a_counted_line_s():
    """A code's readings are the cell's label at the line's place, the label the line planned and the menu's reading
    when it chose, each on its own enough to show an icon read as differing digits; a put-back the run did not plan
    shows nothing, and neither does a place the walk wrote two codes at."""
    c = icon_camera(shown=[x[1] for x in ICONS])
    key1_line(c, 0)["label"] = "S Var. Shutter"                           # the planned label alone reads it otherwise
    assert places(c) == {0}
    c = icon_camera(shown=[x[1] for x in ICONS])
    key1_line(c, 0).update(label="S Var. Shutter", shown="S Var. Shutter")  # the cell's label alone reads it otherwise
    assert places(c) == {0}
    c = icon_camera(shown=[x[1] for x in ICONS])
    c.proofs.append({**key1_line(c, 0), "planned": False, "shown": "S Var. Shutter"})
    assert places(c) == frozenset()
    c = icon_camera()
    c.proofs.append({**key1_line(c, 0), "changes": change("global:0x0200", ICONS[7][0], 196)})
    assert 0 not in O.walk_codes("Keys / Key 1 @0.key.0", "global:0x0200", c.proofs) and 0 not in places(c)
    assert match.label_numbers("1 Focus Area") == () and match.label_numbers("• 1 Focus Area") == () \
        and match.label_numbers("Recall Custom hold 1") == ("1",)


def test_the_walked_code_s_names_come_from_the_entry_s_own_screen():
    """The walked function's readings are those of the entry's own screen: a reading of the same code on another
    screen (the Fn menu's misread "Clip Flag KEEP" of Clip Flag OK) does not excuse a cell offering Clip Flag KEEP;
    the functions outside the list come from every picker screen."""
    c = icon_camera(key2=key2({PLACE[2810]: "• Clip Flag KEEP"}))
    c.tables["Fn"]["cells"][0]["options"].append({"label": "• Clip Flag OK"})
    c.report[-1]["records"]["global:0x0300"]["proved"]["• Clip Flag OK"] = 2810
    c.proofs.append({"path": ["Fn"], "kind": "table", "option": "Upper / 1", "index": len(VOCAB), "label": "• Clip Flag OK",
                     "shown": "Clip Flag KEEP", "applied": True, "planned": True,
                     "changes": [{"key": "global:0x0300", "before": 1, "after": 2810}]})
    assert "Clip Flag KEEP" in O.picker_readings(c.tables, c.report, c.proofs)[2810]
    refused(c, OTHER_SET)


def test_the_vocabulary_check_reads_the_nearest_reading_of_the_walked_function():
    """The walked function's nearness is its nearest reading's (max, not min): a cell nearest a second reading of the
    walked code stands for no function outside the list read farther from it than that reading."""
    readings = {854: {"• Peaking Display", "Peaking Disp"}, 9854: {"Peaking Disp Hi"}}
    assert O.stands_for_other(["• Peaking Dispe"], ["• Peaking Display"], 0, {0: 854}, {854}, readings) is None
    assert O.stands_for_other(["• Peaking Dispe"], ["• Peaking Display"], 0, {0: 854}, {854},
                              {854: {"• Peaking Display"}, 9854: {"Peaking Disp Hi"}}) == 0


def test_a_list_matching_at_two_turns_stands_on_either_and_the_memo_keeps_places_apart():
    """Two look-alikes alone make a list that matches at two turns; it is the walked one when some turn has no label
    nearer a function outside the list (all turns must fail to refuse it). The memo keeps a label's answer per place:
    the same label at two places may read its own function at one and another's at the other."""
    b = ["• Zoom Operation (T)", "• Zoom Operation (W)"]
    codes_, walked = {0: 2201, 1: 2202}, {2201, 2202}
    readings = {2201: {"Zoom Operation (T)"}, 2202: {"Zoom Operation (W)"}, 9201: {"Zoom Operation (T)"}}
    assert list(match.turns(b, b, numbers=True)) == [0, 1]
    assert O.stands_for_other(b, b, 1, codes_, walked, readings) == 0
    assert O.stands_for_other(b, b, 0, codes_, walked, readings) is None
    assert O.differs(b, b, frozenset(), codes_, walked, readings) is None
    a = ["• Zoom Operation (T)", "• Zoom Operation (T)"]
    assert O.stands_for_other(a, b, 0, codes_, walked, readings, memo={}) == 1


def test_a_twin_row_is_held_to_every_place_chosen_and_its_records_icon_places_meet():
    """With the proof lines a twin's row is held to what a walk is: every place chosen (one left out loses the twin,
    though its record names as many options as its list has places). A twin row writing two records whole frees only
    the places both records' codes read with differing numbers (the intersection)."""
    c = icon_camera()
    c.proofs = [p for p in c.proofs if not (p["option"] == "Key 1 @0.key.0" and p["index"] == 3)]
    assert twin_walks(c.report, "global:0x0201", r"^Keys / Key 1 @", c.tables, c.proofs) == []
    lone = key2({i: x[1] for i, x in enumerate(ICONS) if i})              # key 2 reads Var. Shutter otherwise, alone
    c = icon_camera(key2=lone, key2_lines=[(0, "• 8Var. Shutter")])
    assert twin_walks(c.report, "global:0x0201", r"^Keys / Key 1 @", c.tables, c.proofs)
    # key 1's row writes a second record whole (its codes 5000 on), whose code at Var. Shutter's place key 3's row
    # reads one way only: that place is free for the first record, not for the second, so not for the twin
    first = c.report[0]["records"]["global:0x0200"]
    c.report[0]["records"]["global:0x0210"] = rec({k: v + 5000 for k, v in first["proved"].items()})
    for p in c.proofs:
        if p["option"] == "Key 1 @0.key.0" and p["changes"]:
            p["changes"] = p["changes"] + change("global:0x0210", p["changes"][0]["before"] + 5000,
                                                 p["changes"][0]["after"] + 5000)
    c.tables["Keys"]["pages"][0]["items"].append({"row": 2, "key": "Key 3", "opens": "picker", "wrapped": True,
                                                  "options": [{"label": t} for t in lone[TURN:] + lone[:TURN]]})
    c.report.append({"row": "Keys / Key 3 @0.key.2", "records": {"global:0x0210": rec({lone[0]: 5195},
                                                                                     sampled_from_start=True)}})
    c.proofs.append({"path": ["Keys"], "kind": "table", "option": "Key 3 @0.key.2", "index": (0 - TURN) % len(ICONS),
                     "label": lone[0], "shown": "S Var. Shutter", "applied": True, "planned": True,
                     "changes": change("global:0x0210", ICONS[TURN][0] + 5000, 5195)})
    assert 0 in icon_places("Keys", "Keys / Key 1 @0.key.0", "global:0x0200", c.report, c.tables, c.proofs)
    assert 0 not in icon_places("Keys", "Keys / Key 1 @0.key.0", "global:0x0210", c.report, c.tables, c.proofs)
    assert twin_walks(c.report, "global:0x0201", r"^Keys / Key 1 @", c.tables, c.proofs) == []


def test_the_camera_s_download_sample_is_read_once_while_its_log_stays(monkeypatch, tmp_path):
    """check_cut_downloads and check_video_systems share one sample of the camera's downloads (downloads_by_system):
    each download's header is read once while the download log stays as it is, again once it grows."""
    calls = []
    monkeypatch.setattr(O, "_sample_by_system", lambda root, most: calls.append(root) or ({}, 0))
    log = tmp_path / "downloads.jsonl"
    log.write_text('{"path": "dat/00001_x.DAT"}\n', encoding="utf-8")
    O.check_cut_downloads({"settings": []}, [], tmp_path)
    O.check_video_systems({"settings": []}, tmp_path)
    assert len(calls) == 1
    log.write_text('{"path": "dat/00001_x.DAT"}\n{"path": "dat/00002_x.DAT"}\n', encoding="utf-8")
    O.downloads_by_system(tmp_path)
    assert len(calls) == 2


def test_a_twin_walk_with_an_icon_place_stands_for_a_mark():
    """A not-offered mark on a key whose own row is a sample stands on its twin's whole walk where the two lists differ
    only at the twin's icon places (from the twin's row, its whole record and its screen, by the proof lines the report
    counts); without the proof lines no place is an icon place, the numbers differ and the twin stands for nothing. A
    swap of two look-alikes of the twin's list keeps the twin (the same set of codes); a label read nearer a function
    outside the twin's list loses it."""
    c = icon_camera()
    assert [row for row, _ in twin_walks(c.report, "global:0x0201", r"^Keys / Key 1 @", c.tables, c.proofs)] == \
        ["Keys / Key 1 @0.key.0"]
    assert twin_walks(c.report, "global:0x0201", r"^Keys / Key 1 @", c.tables) == []
    mark = {"key": "global:0x0201", "values": [2081], "walk": r"^Keys / Key 1 @", "why": "Not on its list.", "menu": "Keys"}
    assert not_offered_marks(copy.deepcopy(c.doc), [mark], c.report, c.tables, ROOT, c.proofs) == (1, 0)
    assert not_offered_marks(copy.deepcopy(c.doc), [mark], c.report, c.tables, ROOT) == (0, 1)
    c = icon_camera(key2=key2({7: "• Zoom Operation (W)", 8: "• Zoom Operation (T)"}))
    assert len(twin_walks(c.report, "global:0x0201", r"^Keys / Key 1 @", c.tables, c.proofs)) == 1
    c = icon_camera(key2=key2({PLACE[2810]: "• Clip Flag KEEP"}))
    assert twin_walks(c.report, "global:0x0201", r"^Keys / Key 1 @", c.tables, c.proofs) == []


def test_a_slot_s_code_is_read_from_its_own_slot():
    """A proof line's code for a slot of an array record is the value it changed in that slot (line_code), none where
    it chose the option the slot held; a row that proves more than one record gives no readings (code_readings)."""
    line = {"changes": [{"key": "global:0x0100", "before": [1, 1, 1], "after": [1, 3, 1]}]}
    assert O.line_code(line, "global:0x0100[1]") == 3 and O.line_code(line, "global:0x0100[0]") is None
    assert O.line_code({"changes": [{"key": "global:0x0200", "before": 1, "after": 4}]}, "global:0x0200") == 4
    assert O.line_code({"index": 0}, "global:0x0200") is None
    c = icon_camera()
    c.report[0]["records"]["global:0x0300"] = rec({"Alpha": 1})                # key 1's row writes another record too
    assert O.code_readings("Keys", c.report, c.tables, c.proofs) == {} and places(c) == frozenset()


def test_a_slot_is_cut_only_on_a_row_of_its_own():
    """A covered setting's picker is found through a row that proves it and no other covered setting: a row that writes
    another slot along with its own stands for that slot's list no more than a row of another screen or section does,
    and a slot with no row of its own keeps the entry's lists as they are; a walk that proves two covered settings walks
    no one setting's list."""
    c = camera()
    c.report[0]["records"]["global:0x0100[2]"] = rec({"Charlie": 3})           # slot 1's walk writes slot 3 too
    del c.report[2]                                                            # and slot 3 has no row of its own
    refused(c, "proves global:0x0100[0] alone (its own cell)", "Fn")          # that row is neither slot's own
    c = camera()
    c.report[2]["records"]["global:0x0100[1]"] = rec({"Alpha": 1})            # slot 3's row writes slot 2 too
    del c.report[1]                                                            # and slot 2 has no row of its own
    refused(c, "no row of the report on 'Fn''s 'Still' proves global:0x0100[1] alone (its own cell)", "Fn")
    c = camera()
    c.report[3]["records"]["global:0x0201"] = rec({"Bravo": 2})                # key 1's walk writes key 2 too: no
    refused(c, "proves global:0x0200 alone (its own cell)", "Keys")             # walk of one setting's list
    c = camera()
    c.report.append({"row": "Keys / Both @0.key.2", "records": {"global:0x0200": rec({"Alpha": 1}),
                                                               "global:0x0201": rec({"Bravo": 2})}})
    refused(c, "Keys / Both @0.key.2 proves 2 of the settings it covers, so it walks no one setting's list", "Keys",
            walk=r"^Keys / Both @")
    c = camera()
    c.report[3]["records"]["global:0x0100[1]"] = rec({"Bravo": 2})            # a row of another screen writes a slot
    c.tables["Fn"]["cells"].append({"pos": [1, 0], "row_label": "Movie Upper", "col_label": "1", **cell(["Echo"])})
    c.report.append({"row": "Fn / Movie Upper / 1", "records": {"global:0x0100[2]": rec({"Charlie": 3})}})
    assert cut(c, "Fn")[:2] == (5, 0), "a row of another screen or section stands for no slot's list"
    c = camera()
    refused(c, "no row of the report on 'Fn''s 'Movie' proves global:0x0100[0] alone", "Fn", table=("Fn", "Movie"))


def test_a_walk_chose_every_place_of_its_list():
    """The rows the walk names must each have chosen every place of the walked cell (by its proof lines' places, a
    put-back counted only where it was planned), named as many options and written as many distinct codes as the list
    has places, none a sample from the held option, all walks the same codes: a place never chosen though a stray code
    makes the count, two walks that wrote different codes, a sample, a walk that proves none of the settings, or no
    proof lines at all, refuse the entry."""
    c = camera()
    c.proofs = [p for p in c.proofs if not (p["option"] == "Still Upper / 1" and p["index"] == 2)]
    refused(c, "Fn / Still Upper / 1 chose 2 of its list's 3 places: not every place", "Fn")
    c = camera()
    c.proofs[2]["planned"] = False                                             # the put-back of an unplanned place
    refused(c, "chose 2 of its list's 3 places", "Fn")
    c = camera()
    del c.report[0]["records"]["global:0x0100[0]"]["proved"]["Charlie"]
    refused(c, "names 2 options and wrote 2 distinct codes, and its list has 3 places", "Fn")
    c = camera()
    c.report[1]["records"]["global:0x0100[1]"] = rec({"Alpha": 1, "Bravo": 2, "Key only": 9})
    c.proofs += lines("Fn / Still Upper / 2", 3, labels_of(c, "Fn / Still Upper / 2"))
    refused(c, "the walks it names wrote different codes", "Fn", walk=r"^Fn / Still Upper / [12]$")
    c = camera()
    refused(c, "Fn / Still Upper / 2 chose a sample of its list, not every place", "Fn", walk=r"^Fn / Still Upper / 2$")
    c = camera()
    refused(c, "Fn / Still Upper / 1 proves none of the settings it covers", "Keys", walk=r"^Fn / Still Upper / 1$")
    c = camera()
    c.proofs = None
    refused(c, "no proof lines to show that its walks chose every place")


def test_a_list_proved_in_a_state_no_walk_names_is_not_cut():
    """A list that may change with the camera's state is cut only on walks in every state it was proved in: a row that
    proves a covered setting in a context no walk names ("[Movie mode]") refuses the entry; a walk in that state too,
    named in the entry's walk and writing the same codes, lets it be cut."""
    c = camera()
    c.report.append({"row": "Keys / Key 2 @0.key.1 [Movie mode]", "records": {"global:0x0201": rec({"Delta": 4})}})
    refused(c, "Keys / Key 2 @0.key.1 [Movie mode] proves global:0x0201 in a state no walk names (Movie mode)", "Keys")
    c.report.append({"row": "Keys / Key 1 @0.key.0 [Movie mode]",
                     "records": {"global:0x0200": rec({"Alpha": 1, "Bravo": 2, "Delta": 4})}})
    c.proofs += lines("Keys / Key 1 @0.key.0", 3, labels_of(c, "Keys / Key 1 @0.key.0"), context="Movie mode")
    assert cut(c, "Keys")[:2] == (2, 0)


def test_without_the_hand_evidence_or_the_sample_a_list_stays_as_it_is():
    """An entry the hand evidence says nothing of (no "evidence" put back: a clone without the private overlay) keeps
    its settings' lists, said, as a not-offered mark without its walks would be refused; and with no sample the
    factory values cannot be seen to be on the list, so no list is cut. (kit/schema_update.py --write stops before
    anything is read when the hand evidence file is not there: test_the_plain_pass_cuts_a_list_with_the_evidence_apart.)"""
    c = camera()
    refused(c, "the hand evidence says nothing of the walks", evidence=None)
    c.factory = None
    refused(c, "the definition has no sample")
    c.factory = {}
    refused(c, "the definition's sample does not hold global:0x0100[0]", "Fn")


def test_a_value_the_camera_holds_outside_the_walked_list_stops_the_write():
    """The sample's factory value, or a code any proof wrote for a covered setting, outside the walked codes (and not
    held) stops the write, nothing changed: the walks and the camera disagree, and a value the camera holds is never
    dropped. The words name the setting and the row, never the value."""
    c = camera()
    c.factory["global:0x0201"] = 7
    with pytest.raises(SystemExit) as got:
        cut(c)
    assert "global:0x0201" in str(got.value) and "the definition's sample" in str(got.value) and "nothing written" in str(got.value)
    assert codes(c.doc)["global:0x0201"] == [1, 2, 4, 7]
    c = camera()
    c.report.append({"row": "Elsewhere > Key 2", "records": {"global:0x0201": rec({"Fn code": 7})}})
    with pytest.raises(SystemExit) as got:
        cut(c)
    assert "a proof (Elsewhere > Key 2)" in str(got.value) and " 7" not in str(got.value)
    c = camera()
    c.held = {}
    with pytest.raises(SystemExit):
        cut(c, "Fn")                                                            # slot 3's factory value, not held


def download(path: Path, values: dict) -> Path:
    """The a1 II's sample written as a camera download whose live Fn Menu (Still) places hold `values` ({place: code})."""
    cs = camset.read(definitions.sample(definitions.load(A1, evidence=False)))
    rec_ = cs.get(0, 0x0445)
    raw = bytearray(rec_.raw)
    for i, v in values.items():
        raw[i * rec_.size:(i + 1) * rec_.size] = v.to_bytes(rec_.size, "little", signed=True)
    path.write_bytes(camset.with_values(cs, {(0, 0x0445): bytes(raw)}))
    return path


def test_a_cut_list_is_checked_against_the_cameras_own_downloads(monkeypatch, tmp_path, capsys):
    """After the cut, the camera's own downloads (downloads_by_system, as check_video_systems reads them) must hold no
    code a cut setting's list leaves out in its live record: one that does stops the write, naming the setting and the
    file, never the value; a list the downloads agree with is said checked; with no runs here it says so."""
    doc = {"settings": [setting("global:0x0445[4]", [1, 2, 3])]}
    (tmp_path / "dat").mkdir()
    good = download(tmp_path / "dat" / "00001_x.DAT", {4: 2})
    monkeypatch.setattr(O, "downloads_by_system", lambda root, most: ({"NTSC": [good]}, 0))
    assert O.check_cut_downloads(doc, ["global:0x0445[4]"], tmp_path) == (1, 0)
    assert "1 cut settings checked against 1 of the camera's downloads" in capsys.readouterr().out
    bad = download(tmp_path / "dat" / "00002_x.DAT", {4: 9})
    monkeypatch.setattr(O, "downloads_by_system", lambda root, most: ({"NTSC": [good, bad]}, 0))
    with pytest.raises(SystemExit) as got:
        O.check_cut_downloads(doc, ["global:0x0445[4]"], tmp_path)
    words = str(got.value)
    assert "global:0x0445[4]" in words and "dat/00002_x.DAT" in words.replace("\\", "/") and " 9" not in words
    assert O.check_cut_downloads(doc, ["global:0x0445[4]"], None) is None


def test_sample_values_reads_a_slot_or_a_whole_record():
    """sample_values: each key's value in the definition's sample, a whole record's or one element's; a key the sample
    does not hold left out; None without a sample."""
    doc = definitions.load(A1, evidence=False)
    got = sample_values(definitions.sample(doc), ["global:0x0445[4]", "global:0x0412", "global:0xfffe", "set:0x0180@1"])
    assert set(got) == {"global:0x0445[4]", "global:0x0412"} and all(isinstance(v, int) for v in got.values())
    assert sample_values(None, ["global:0x0412"]) is None


def test_a_mark_on_a_sampled_key_stands_on_its_twins_whole_walk():
    """A not-offered mark's walk proves a key by its own rows, never by a sample from the held option; where no row of
    the walk proves the key, a row that walked whole a picker the table walk shows lists the same functions in the same
    order stands for it (twin_walks), judged by code; a twin of another list, one walked in part, or one whose row also
    wrote the key (no cell of the key's own then), stands for nothing."""
    c = camera()
    assert walked_rows(c.report, "global:0x0201", r"^Keys / Key 2 @") == []
    assert [row for row, _ in twin_walks(c.report, "global:0x0201", r"^Keys / ", c.tables, c.proofs)] == \
        ["Keys / Key 1 @0.key.0"]
    mark = {"key": "global:0x0201", "values": [7], "walk": r"^Keys / Key 1 @", "why": "Not on its list.", "menu": "Keys"}
    assert not_offered_marks(c.doc, [mark], c.report, c.tables, ROOT, c.proofs) == (1, 0)
    assert [m["value"] for m in next(s for s in c.doc["settings"] if s["key"] == "global:0x0201")["not_offered"]] == [7]
    assert not_offered_marks(c.doc, [dict(mark, walk=r"^Keys / Key 2 @")], c.report, c.tables, ROOT, c.proofs) == (0, 1)
    other = copy.deepcopy(c.tables)
    other["Keys"]["pages"][0]["items"][1]["options"].pop()
    assert twin_walks(c.report, "global:0x0201", r"^Keys / ", other, c.proofs) == []
    part = copy.deepcopy(c.report)
    del part[3]["records"]["global:0x0200"]["proved"]["Delta"]
    assert twin_walks(part, "global:0x0201", r"^Keys / ", c.tables, c.proofs) == []
    alone = copy.deepcopy(c.report)
    del alone[4]
    alone.append({"row": "Elsewhere > Key 2", "records": {"global:0x0201": rec({"Bravo": 2}), "global:0x0200": rec({"Bravo": 2})}})
    assert twin_walks(alone, "global:0x0201", r"^Keys / ", c.tables, c.proofs) == []


def test_a_value_the_camera_keeps_for_itself_keeps_no_proof(capsys):
    """A setting the hand table says the camera keeps or computes for itself (UNPROVED kind "state": how the camera is
    held) keeps no proof, whatever a run read there: one an earlier write left (a view-only readout's) is taken out,
    said, and the reason written in its place, in the plain pass as in the a1 II's; a reason of another kind takes
    nothing out, and a hand proof with no state reason stands (the a1 II's "ISO in use (movie)" records, proved by hand:
    a run fixed the ISO at known values and downloaded the file each time)."""
    by_key = {"global:0x0ccc": setting("global:0x0ccc", [1, 2], proved={"values": [1, 2]}),
              "global:0x0fde": setting("global:0x0fde", [1], proved={"values": [1]}),
              "global:0x0bbb": setting("global:0x0bbb", [1], proved={"values": [1]})}
    reasons = {"global:0x0ccc": ("state", None, "How the camera is held."),
               "global:0x0bbb": ("equipment", None, "A recorder.")}
    changed = []
    assert hand_facts.state_proofs_out(by_key, reasons, {"global:0x0fde"}, changed) == ["global:0x0ccc"]
    assert "proved" not in by_key["global:0x0ccc"] and by_key["global:0x0fde"]["proved"] and by_key["global:0x0bbb"]["proved"]
    assert "global:0x0ccc: a value the camera keeps for itself (state): its proof taken out" in capsys.readouterr().out
    doc = {"settings": list(by_key.values())}
    by_key["global:0x0ccc"]["proved"] = {"values": [1, 2]}
    T = hand_tables.Tables(**{**hand_tables.empty(), "UNPROVED": reasons}, HAND_EVIDENCE=None)
    hand_facts.unproved(doc, by_key, T, {"FRAME_PROOFS": {"global:0x0fde": {"proved": [1]}}}, [])
    assert "proved" not in by_key["global:0x0ccc"] and by_key["global:0x0fde"]["proved"]
    assert by_key["global:0x0ccc"]["unproved_reason"] == {"kind": "state", "why": "How the camera is held."}
    T = hand_tables.load(A1, evidence=False)
    assert not {"global:0x0fde", "global:0x0fe0"} & set(T.UNPROVED) and {"global:0x0fde", "global:0x0fe0"} <= set(T.FRAME_PROOFS)


def test_a_state_reason_and_a_hand_proof_of_one_key_stop_the_write():
    """UNPROVED saying the camera keeps a value for itself and FRAME_PROOFS' hand evidence proving it are opposite
    claims: either pass stops the write, nothing written, naming the key and both tables (the a1 II's pass calls
    state_proofs_out with its FRAME_PROOFS' hand proofs, the plain pass with the hand evidence's)."""
    reasons = {"global:0x0fde": ("state", None, "A working value.")}
    by_key = {"global:0x0fde": setting("global:0x0fde", [1], proved={"values": [1]})}
    with pytest.raises(SystemExit) as stop:
        hand_facts.state_proofs_out(by_key, reasons, {"global:0x0fde"}, [])
    assert "global:0x0fde" in str(stop.value) and "UNPROVED" in str(stop.value) and "FRAME_PROOFS" in str(stop.value)
    T = hand_tables.Tables(**{**hand_tables.empty(), "UNPROVED": reasons}, HAND_EVIDENCE=None)
    with pytest.raises(SystemExit, match="take one out"):
        hand_facts.unproved({"settings": list(by_key.values())}, by_key, T,
                            {"FRAME_PROOFS": {"global:0x0fde": {"proved": [1]}}}, [])
    assert by_key["global:0x0fde"]["proved"] == {"values": [1]}


def test_the_plain_pass_cuts_a_list_with_the_evidence_apart(monkeypatch, tmp_path):
    """The plain pass, every camera's but the a1 II's, reads PICKER_LISTS (hand_facts.PLAIN) and takes each entry's
    walks' evidence from the hand evidence by the entry's name (never put into the tables), the proof lines from its
    run: with it the list is cut, without it the list stays and is said; --write stops without the hand evidence file
    (hand_evidence.missing)."""
    c = camera()
    public = {name: {f: v for f, v in e.items() if f != "evidence"} for name, e in c.entries.items()}
    T = hand_tables.Tables(**{**hand_tables.empty(), "PICKER_LISTS": public,
                              "NOT_OFFERED": [{"key": "global:0x0100[2]", "values": [10], "held": True}]}, HAND_EVIDENCE=None)
    assert "PICKER_LISTS" in hand_facts.PLAIN and hand_facts.refusals(T) == []
    run = tmp_path / "kit2_pass2"
    (tmp_path / "kit2_tables").mkdir()
    (tmp_path / "kit2_tables" / "tables.json").write_text(json.dumps(c.tables), encoding="utf-8")
    import pass2_report
    monkeypatch.setattr(O, "sample_values", lambda path, keys: c.factory)
    monkeypatch.setattr(pass2_report, "report_proofs", lambda r: (c.proofs, set()))
    run.mkdir()
    (run / "proofs.jsonl").write_text("", encoding="utf-8")
    hand_facts.walked_lists(c.doc, T, {}, c.report, run, None)
    assert codes(c.doc)["global:0x0200"] == [1, 2, 4, 7], "no evidence: not cut"
    hand_facts.walked_lists(c.doc, T, {"PICKER_LISTS": {"Keys": {"evidence": "walked whole"}}}, c.report, run, None)
    assert codes(c.doc)["global:0x0200"] == [1, 2, 4] and codes(c.doc)["global:0x0100[0]"] == [1, 2, 3, 9, 10]
    assert hand_evidence.missing("ILCE-0X0_fw1.00", None, {"PICKER_LISTS": public})
    assert hand_evidence.missing("ILCE-0X0_fw1.00", Path("x"), {"PICKER_LISTS": public}) is None


def test_hand_evidence_for_a_picker_list_is_put_back_by_its_name(monkeypatch, tmp_path):
    """The a1 II's pass reads its tables with the hand evidence put back: a PICKER_LISTS entry takes its walks'
    evidence by its name; a name the tables lack, or any field but the evidence (in the schema), is refused."""
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path)
    cam = "ILCE-0X0_fw1.00"
    tables = {"PICKER_LISTS": {"Fn": {"keys": "^k", "walk": "^w", "table": ("Fn", None), "why": "W."}}}

    def put(patch):
        hand_evidence.path(cam).write_text(json.dumps({"hand_format": hand_evidence.FORMAT, "camera": cam,
                                                       "tables": {"PICKER_LISTS": patch}}), encoding="utf-8")
        return hand_evidence.put_back(tables, cam)
    put({"Fn": {"evidence": "walked whole"}})
    assert tables["PICKER_LISTS"]["Fn"]["evidence"] == "walked whole"
    with pytest.raises(ValueError, match="no entry 'Movie'"):
        put({"Movie": {"evidence": "x"}})
    doc = {"hand_format": 2, "camera": cam, "tables": {"PICKER_LISTS": {"Fn": {"evidence": "x", "walk": "^other"}}}}
    assert hand_evidence.schema_problems(doc, "hand-evidence") == \
        ["'tables' 'PICKER_LISTS' 'Fn' holds 'walk', which it may not hold (it may hold 'evidence')"]


# the a1 II's own entries, on its public data

def a1_doc():
    return definitions.load(A1, evidence=False)


def test_the_a1_iis_picker_lists_cover_the_fn_slots_and_the_keys_the_walks_settle():
    """The a1 II's PICKER_LISTS: the 36 Fn Menu places (12 per mode) and the 14 stills Custom Keys the first kit gave
    the Fn menu's codes for Pre-Capture and Subject Recog in AF, each family of one list; the public file names no run,
    no day and no evidence (test_lean_tables), and its walks and keys compile."""
    T = hand_tables.load(A1, evidence=False)
    doc = a1_doc()
    covered = {name: [s["key"] for s in doc["settings"] if re.search(e["keys"], s["key"])] for name, e in T.PICKER_LISTS.items()}
    assert {name: len(keys) for name, keys in covered.items()} == {
        "Fn Menu (Still)": 12, "Fn Menu (Movie)": 12, "Fn Menu (Playback)": 12, "Custom Key (Still): AEL Button's list": 8,
        "Custom Key (Still): Custom Button 4's list": 1, "Custom Key (Still): Multi-Slc Center Btn's list": 2,
        "Custom Key (Still): Left Button's list": 3}
    keys = [k for ks in covered.values() for k in ks]
    assert len(keys) == len(set(keys)), "a setting in two lists"
    for name, e in T.PICKER_LISTS.items():
        assert e["why"].endswith(".") and "full circle" in e["why"] and set(e) == {"keys", "walk", "table", "why"}, name
    # the playback list's walk is Upper 4, which chose every place; Upper 1's own function was only put back
    playback = T.PICKER_LISTS["Fn Menu (Playback)"]
    assert re.search(playback["walk"], "Fn Menu Settings / Playback Upper / 4") and \
        not re.search(playback["walk"], "Fn Menu Settings / Playback Upper / 1") and "Upper 4" in playback["why"]


def test_the_a1_iis_lists_cut_to_their_proofs_keep_the_factory_values():
    """What a write gives, as the public definition already shows it: in each family every covered setting's proved
    values are one set (the walked list, lent to the sampled slots), the sample's factory value of each is inside it,
    and the values left over beyond it are the first kit's union (the Fn menus' 150, 149 and 196 codes a place, the
    keys' Fn codes 2081 and 314), none of them a proved value; after a write the lists are those sets, and nothing is
    left over."""
    T = hand_tables.load(A1, evidence=False)
    doc = a1_doc()
    factory = sample_values(definitions.sample(doc), [s["key"] for s in doc["settings"]
                                                      if any(re.search(e["keys"], s["key"]) for e in T.PICKER_LISTS.values())])
    for name, e in T.PICKER_LISTS.items():
        covered = [s for s in doc["settings"] if re.search(e["keys"], s["key"])]
        sets = {frozenset(s["proved"]["values"]) for s in covered}
        assert len(sets) == 1, name
        (walked,) = sets
        for s in covered:
            listed = {v for v, _ in s["values"]}
            assert walked <= listed and factory[s["key"]] in walked, s["key"]
            extra = listed - walked
            if name.startswith("Custom Key") and extra:
                assert extra <= {2081, 314}, (s["key"], extra)


def test_the_custom_key_notes_say_the_count_of_their_proved_lists():
    """The hand table's notes for the Custom Keys ("Offers the N functions this key's picker lists.") say the length of
    each key's proved list (its picker's whole list, walked full circle), never the first kit's partial counts; the
    playback Fn Menu's places say no more that their codes were inferred."""
    T = hand_tables.load(A1, evidence=False)
    by = {s["key"]: s for s in a1_doc()["settings"]}
    said = {k: fix["note"] for k, fix in T.RECORD_FIXES.items() if fix.get("note", "").startswith("Offers the ")}
    assert len(said) == 37
    for k, note in said.items():
        n = int(re.fullmatch(r"Offers the (\d+) functions this key's picker lists\.", note)[1])
        assert n == len(by[k]["proved"]["values"]) and T.RECORD_FIXES[k]["name"] == by[k]["name"], k
    assert {T.RECORD_FIXES[f"global:0x12e7[{i}]"]["note"] for i in range(12)} == {"Playback Fn Menu slot (function code)"}
    assert T.LABEL_FIXES["ErAspect Marker Disp."] == "Aspect Marker Disp."
