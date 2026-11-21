"""grey_in and inactive_if (camkit.grey_rules): a row the camera greys in some shooting modes whatever the file holds,
and inactive_when's rule true only in some modes or only with a device on the HDMI socket; their shapes in the hand
tables, the definition and the hand evidence, the writer's handling of RECORD_FIXES (a null inactive_when takes the
rule out, the looks never reach the definition, the fields are the tables' alone), the looks each side needs, and what
kit/tools/check_public.py holds a definition to. Made-up entries throughout."""
import json
import types

import pytest

from camkit import grey_rules
from writer import hand_evidence, hand_facts, hand_tables
from writer.notes import apply_fix

CAMERA = {"live_mode": {"key": "global:0x13bf", "modes": {"0": "Stills", "1": "Movie", "2": "S&Q", "3": "Time-lapse"}},
          "menus": [{"name": "Still", "modes": ["Stills"]}, {"name": "Movie", "modes": ["Movie"]},
                    {"name": "S&Q", "modes": ["S&Q", "Time-lapse"]}]}
NAMES = ["Stills", "Movie", "S&Q", "Time-lapse"]
HDMI_RULE = {"record": 1180, "name": "HDMI Info. Display", "values": [0], "unlock": 1, "unlock_label": "Off",
             "hdmi_device": True}
FAMILY_RULE = {"record": 584, "name": "S&Q Frame Rate", "values": [0, 2], "unlock": 4, "unlock_label": "60fps",
               "family": ["S&Q"]}


def doc(*settings):
    return {"camera": CAMERA, "settings": [dict({"key": f"global:0x{i:04x}", "name": f"S{i}"}, **s)
                                            for i, s in enumerate(settings, 1)]}


def look(mode, drawn, blocker=None, kit=("mode",), **more):
    x = {"run": "made_up", "line": 1, "mode": mode, "drawn": drawn, "kit_set": list(kit), **more}
    if blocker is not None:
        x["blocker"] = blocker
    return x


def test_grey_in_holds_the_cameras_mode_names_within_the_rows_menus():
    """grey_in names the camera's own shooting modes (live_mode), never a menu: each a mode of a menu that lists the
    row, none twice, and never every one of them (the row is drawn white somewhere); a setting in no menu cannot have
    it. The S&Q menu serves two modes, so a fact of one of them names that one alone."""
    good = doc({"row_menus": ["Movie", "S&Q"], "grey_in": ["S&Q", "Time-lapse"]},
               {"row_menus": ["Movie", "S&Q"], "grey_in": ["S&Q"]})
    assert grey_rules.problems(good) == []
    bad = grey_rules.problems(doc({"row_menus": ["Movie", "S&Q"], "grey_in": ["S&Q Motion"]},
                                  {"row_menus": ["Movie", "S&Q"], "grey_in": ["Stills"]},
                                  {"row_menus": ["Movie", "S&Q"], "grey_in": ["Movie", "S&Q", "Time-lapse"]},
                                  {"row_menus": ["S&Q"], "grey_in": ["S&Q", "S&Q"]},
                                  {"grey_in": ["S&Q"]},
                                  {"row_menus": ["S&Q"], "grey_in": []}))
    assert bad == ["global:0x0001: grey_in names 'S&Q Motion', none of the camera's shooting modes (Stills, Movie, "
                   "S&Q, Time-lapse)",
                   "global:0x0002: grey_in names 'Stills', which no menu that lists the row serves (Movie, S&Q, Time-lapse)",
                   "global:0x0003: grey_in names every mode its menus serve: the row would be drawn white nowhere",
                   "global:0x0004: grey_in names 'S&Q' twice",
                   "global:0x0005: grey_in on a setting listed in no camera menu",
                   "global:0x0006: grey_in is not a list of the camera's shooting-mode names"]


def test_inactive_if_is_inactive_when_with_a_family_or_an_hdmi_device_and_nothing_else():
    """inactive_if holds inactive_when's keys (record, name, values or except, unlock, unlock_label) and one or both
    conditions: a family, some of the camera's modes but never all, and hdmi_device, only ever true. Nothing else, so
    no run, line, date or note reaches the definition by it."""
    assert grey_rules.problems(doc({"inactive_if": FAMILY_RULE}, {"inactive_if": HDMI_RULE},
                                   {"inactive_if": dict(FAMILY_RULE, hdmi_device=True)},
                                   {"inactive_if": dict(HDMI_RULE, values=[], **{"except": [1]})})) == []
    no_cond = {k: v for k, v in HDMI_RULE.items() if k != "hdmi_device"}
    bad = grey_rules.problems(doc({"inactive_if": no_cond},
                                  {"inactive_if": dict(HDMI_RULE, hdmi_device=False)},
                                  {"inactive_if": dict(FAMILY_RULE, family=NAMES)},
                                  {"inactive_if": dict(FAMILY_RULE, family=["Slow"])},
                                  {"inactive_if": dict(HDMI_RULE, run="kit2_x")},
                                  {"inactive_if": {k: v for k, v in HDMI_RULE.items() if k != "unlock"}}))
    assert bad == [
        "global:0x0001: inactive_if names no condition (family, hdmi_device): a rule that holds always is inactive_when",
        "global:0x0002: inactive_if's hdmi_device is only ever true",
        "global:0x0003: inactive_if's family names every shooting mode: a rule that holds in all of them is inactive_when",
        "global:0x0004: inactive_if's family names 'Slow', none of the camera's shooting modes (Stills, Movie, S&Q, "
        "Time-lapse)",
        "global:0x0005: inactive_if holds 'run', which it does not have (inactive_when's keys, family, hdmi_device)",
        "global:0x0006: inactive_if has no unlock (a whole number)"]


def test_no_rule_stands_on_the_live_mode_record_and_no_look_reaches_the_definition():
    """A rule on the live-mode record (0x13bf, 5055) would grey the row in every menu's view whenever the file stands in
    that mode: refused in inactive_when and inactive_if alike, saying to write grey_in. A look is the hand evidence's,
    never a definition's field."""
    on_live = {"record": 5055, "name": "Shooting family", "values": [2], "unlock": 1, "unlock_label": "Movie"}
    assert grey_rules.problems(doc({"inactive_when": on_live}, {"inactive_if": dict(on_live, family=["S&Q"])},
                                   {"looks": [look("S&Q", "grey")]})) == [
        "global:0x0001: inactive_when stands on the live-mode record: write the modes it holds in as grey_in",
        "global:0x0002: inactive_if stands on the live-mode record: write the modes it holds in as grey_in, or as the "
        "family of a rule on another record",
        "global:0x0003: holds 'looks', the hand evidence's (a look), never the definition's"]


def test_grey_in_needs_a_grey_look_with_the_shoot_mode_named_in_each_mode_and_a_white_one_elsewhere():
    """A grey_in rests on the kit's looks: in each mode it names, the row read grey with Help (or the notice one Right
    opens) naming the shoot mode, the mode set by the kit's own switch; and the row read white in a mode it leaves
    out. Each missing side is said; a look out of its shape is said first."""
    fix = {"name": "Audio Recording", "grey_in": ["S&Q", "Time-lapse"]}
    whole = [look("S&Q", "grey", help="shoot mode"), look("Time-lapse", "grey", help="shoot mode"), look("Movie", "white")]
    assert grey_rules.look_problems(fix, whole, NAMES) == []
    assert grey_rules.look_problems(fix, [whole[0], look("Time-lapse", "grey", help="none")], NAMES) == [
        "grey_in: no look reads the row grey in Time-lapse with Help naming the shoot mode",
        "grey_in: no look reads the row white in a mode grey_in leaves out"]
    assert grey_rules.look_problems(fix, None, NAMES) == ["the hand evidence gives no looks"]
    assert grey_rules.look_problems(fix, [dict(whole[0], kit_set=["blocker"], seen="x")], NAMES) == [
        "looks[0] holds 'seen', which a look does not have",
        "looks[0]'s kit_set is not \"mode\", with \"blocker\" where the kit set the blocker's value"]
    assert grey_rules.look_problems({"name": "Plain"}, None, NAMES) == []


def test_a_family_rule_needs_both_values_set_by_the_kit_in_its_mode_and_white_in_a_mode_it_leaves_out():
    """inactive_if with a family: in a mode of the family, the row read grey at a value that greys it and white at one
    that does not, both values set by the kit; and white at a value that greys it in a mode the family leaves out
    (the value read from that look's start download). Zoom Range: grey at 120fps in S&Q Motion, white at 60fps there,
    white at 120fps in Movie."""
    fix = {"name": "Zoom Range", "inactive_if": FAMILY_RULE}
    both = ("mode", "blocker")
    whole = [look("S&Q", "grey", 2, both), look("S&Q", "white", 4, both), look("Movie", "white", 2)]
    assert grey_rules.look_problems(fix, whole, NAMES) == []
    assert grey_rules.look_problems(fix, [look("S&Q", "grey", 2), whole[1]], NAMES) == [
        "inactive_if: no look reads the row grey at a value that greys it, set by the kit in S&Q",
        "inactive_if: no look reads the row white at a value that greys it in a mode its family leaves out"]
    assert grey_rules.look_problems(fix, [whole[0], look("Movie", "white", 4, both), whole[2]], NAMES) == [
        "inactive_if: no look reads the row white at a value that does not grey it, set by the kit in S&Q"]


def test_an_hdmi_device_rule_needs_both_values_with_the_cable_in_and_a_white_look_with_it_out():
    """inactive_if with hdmi_device: with the cable in, the row read grey at a value that greys it and white at one
    that does not, both set by the kit; with the cable out, white at a value that greys it, set by the kit. The cable's
    state is the chain's context line's (the owner's word); a look that does not say it proves neither side."""
    fix = {"name": "Touch Func. in Shooting", "inactive_if": HDMI_RULE}
    both = ("mode", "blocker")
    whole = [look("Stills", "grey", 0, both, hdmi="in"), look("Stills", "white", 1, both, hdmi="in"),
             look("Stills", "white", 0, both, hdmi="out")]
    assert grey_rules.look_problems(fix, whole, NAMES) == []
    assert grey_rules.look_problems(fix, whole[:2] + [look("Stills", "white", 0, both)], NAMES) == [
        "inactive_if: no look reads the row white at a value that greys it, set by the kit, with the HDMI cable out"]
    assert grey_rules.look_problems(fix, [dict(x, hdmi="out") for x in whole], NAMES) == [
        "inactive_if: no look reads the row grey at a value that greys it, set by the kit with the HDMI cable in",
        "inactive_if: no look reads the row white at a value that does not grey it, set by the kit with the HDMI cable in"]


def test_the_hand_tables_take_the_grey_fields_in_their_shapes(tmp_path):
    """A RECORD_FIXES entry may give inactive_when as null (the definition's rule taken out), an inactive_if and a
    grey_in; the loader refuses one out of its shape, in words, and the hand-tables schema holds the same shapes."""
    def read(entry):
        p = tmp_path / "hand.json"
        p.write_text(json.dumps({"camera": "TEST-CAM_fw1.00", "RECORD_FIXES": {"global:0x0001": dict({"name": "N"}, **entry)}}),
                     encoding="utf-8")
        return hand_tables.read(p, "TEST-CAM_fw1.00")
    for good in ({"inactive_when": None, "inactive_if": HDMI_RULE}, {"inactive_if": FAMILY_RULE},
                 {"grey_in": ["S&Q", "Time-lapse"]}):
        assert read(good)["RECORD_FIXES"]["global:0x0001"]["name"] == "N"
        assert hand_evidence.schema_problems({"camera": "TEST-CAM_fw1.00", "RECORD_FIXES": {"global:0x0001": dict(
            {"name": "N"}, **good)}}, "hand-tables") == []
    for bad, words in (({"inactive_if": {k: v for k, v in HDMI_RULE.items() if k != "hdmi_device"}}, "names no condition"),
                       ({"grey_in": ["S&Q", "S&Q"]}, "grey_in names 'S&Q' twice"),
                       ({"inactive_when": "On"}, "'inactive_when' is a string, not an object")):
        with pytest.raises(hand_tables.Refused) as e:
            read(bad)
        assert words in str(e.value)
    assert hand_evidence.schema_problems({"camera": "TEST-CAM_fw1.00", "RECORD_FIXES": {"global:0x0001": {
        "name": "N", "inactive_if": dict(HDMI_RULE, hdmi_device=False)}}}, "hand-tables") != []


def test_the_hand_evidence_schema_takes_looks_on_a_record_fix_and_nothing_else():
    """The hand evidence's RECORD_FIXES part holds a note's evidence and the looks; a look holds its run, line, mode,
    what was drawn and what the kit set (the mode always), with the blocker, the cable and the Help's reason where
    they apply, nothing else."""
    def part(p):
        return {"hand_format": 2, "camera": "TEST-CAM_fw1.00", "tables": {"RECORD_FIXES": {"global:0x0001": p}}}
    assert hand_evidence.schema_problems(part({"looks": [look("S&Q", "grey", 2, ("mode", "blocker"), hdmi="in",
                                                            help="shoot mode")]}), "hand-evidence") == []
    assert hand_evidence.schema_problems(part({"looks": [look("S&Q", "grey", kit=("blocker",))]}), "hand-evidence")
    assert hand_evidence.schema_problems(part({"looks": [dict(look("S&Q", "grey"), date="2026-11-21")]}), "hand-evidence")
    assert hand_evidence.schema_problems(part({"run": "kit2_x"}), "hand-evidence")


def test_the_definition_schema_describes_grey_in_and_inactive_if():
    """The definition's schema holds a setting's grey_in and inactive_if in the shapes the writer writes them."""
    import jsonschema
    from camkit import ROOT
    s = json.loads((ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))
    setting = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": s["$defs"],
               "$ref": "#/$defs/setting"}
    v = jsonschema.Draft202012Validator(setting)
    base = {"key": "global:0x0001", "area": "global", "id": 1, "name": "N", "tab": "Shooting", "group": "G"}
    assert not list(v.iter_errors(base))
    assert not list(v.iter_errors(dict(base, grey_in=["S&Q"], inactive_if=FAMILY_RULE)))
    assert list(v.iter_errors(dict(base, inactive_if=dict(HDMI_RULE, hdmi_device=False))))
    assert list(v.iter_errors(dict(base, inactive_if={k: x for k, x in HDMI_RULE.items() if k != "hdmi_device"})))
    assert list(v.iter_errors(dict(base, grey_in=[])))


def test_the_writer_puts_the_fields_on_and_takes_out_what_the_tables_no_longer_give(capsys):
    """RECORD_FIXES puts grey_in and inactive_if on the setting, never the entry's looks (put back into the entry by
    the ILCE-1M2's pass); a null inactive_when takes the setting's rule out; a grey_in or inactive_if the tables no
    longer give goes, said (they are the tables' alone), while an inactive_when no entry names stays (12 of the a1
    II's have no entry)."""
    by_key = {"global:0x0001": {"key": "global:0x0001", "name": "A", "inactive_when": {"record": 1180, "values": [0]}},
              "global:0x0002": {"key": "global:0x0002", "name": "B", "grey_in": ["S&Q"], "inactive_if": HDMI_RULE},
              "global:0x0003": {"key": "global:0x0003", "name": "C", "inactive_when": {"record": 9, "values": [1]}}}
    fixes = {"global:0x0001": {"name": "A", "inactive_when": None, "inactive_if": HDMI_RULE,
                               "looks": [look("Stills", "grey", 0, ("mode", "blocker"), hdmi="in")]}}
    changed = []
    hand_facts.record_fixes(by_key, types.SimpleNamespace(RECORD_FIXES=fixes), {}, changed)
    a, b, c = by_key.values()
    assert a == {"key": "global:0x0001", "name": "A", "inactive_if": HDMI_RULE}
    assert b == {"key": "global:0x0002", "name": "B"} and "inactive_when" in c
    out = capsys.readouterr().out
    assert "  record fix  global:0x0002 grey_in: taken out, RECORD_FIXES no longer gives it" in out
    assert "  record fix  global:0x0002 inactive_if: taken out, RECORD_FIXES no longer gives it" in out
    item = {"name": "A", "range": [0, 1]}
    apply_fix(item, {"name": "A", "range": None})
    assert item == {"name": "A"}


def test_the_looks_are_read_from_the_entry_or_the_evidence_apart():
    """grey_look_gaps reads each entry's looks from the hand evidence by table and key: the plain pass's file read
    apart, or the ILCE-1M2's tables with the evidence put back (the entry itself); an entry with neither field needs
    none."""
    fix = {"name": "Audio Recording", "grey_in": ["S&Q"]}
    looks = [look("S&Q", "grey", help="shoot mode"), look("Movie", "white")]
    assert hand_facts.grey_look_gaps({"k": fix}, {"RECORD_FIXES": {"k": {"looks": looks}}}, NAMES) == []
    merged = {"k": dict(fix, looks=looks), "j": {"name": "Plain"}}
    assert hand_facts.grey_look_gaps(merged, {"RECORD_FIXES": merged}, NAMES) == []
    assert hand_facts.grey_look_gaps({"k": fix}, {}, NAMES) == ["k the hand evidence gives no looks"]
    assert "add the looks that prove the missing side" in hand_facts.grey_look_stop("TEST-CAM_fw1.00", ["k x"])


def test_check_public_holds_a_definition_to_the_grey_rules():
    """check_public's menu check says what grey_rules.problems says of a definition: a mode the camera lacks, a rule on
    the live-mode record, a look."""
    import check_public
    d = doc({"row_menus": ["S&Q"], "grey_in": ["Slow"]}, {"looks": []})
    assert check_public.menu_problems(d) == [
        "global:0x0001: grey_in names 'Slow', none of the camera's shooting modes (Stills, Movie, S&Q, Time-lapse)",
        "global:0x0002: holds 'looks', the hand evidence's (a look), never the definition's"]
