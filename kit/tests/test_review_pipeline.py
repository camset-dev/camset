"""The engineering review of 2026-11-18, track 2 (the mapping pipeline, the provers, the readers): each finding fixed
here has its test, written first to show it. No camera: the provers run against fakes."""
import sys
import types
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# ------------------------------------------------------------------------------------------------ finding 2 (B1)

def test_the_report_never_takes_a_lost_decimal_point_or_fraction_slash_for_agreement():
    """pass2_report compared labels with norm(), which drops "." and "/": 1.3" and 13", F1.1 and F11, 1/250 and 1250
    were one label, so swapped labels passed as "agrees" and two such proofs merged at one index."""
    import pass2_report as R
    verdict, notes = R.judge({'1.3"': 5, '13"': 9, "F1.1": 1, "F11": 2}, {5: '13"', 9: '1.3"', 1: "F11", 2: "F1.1"})
    assert verdict == "conflict" and sorted(n["value"] for n in notes if n["kind"] == "conflict") == [1, 2, 5, 9]
    assert R.judge({'1.3"': 5}, {5: '13"'})[0] != "agrees"
    assert R.judge({"1/250": 7}, {7: "1250"})[0] != "agrees"
    assert R.option_key({"index": 5, "label": '13"'}, {5: {"label": '1.3"'}}) != 5
    assert R.option_key({"index": 5, "label": "1/250"}, {5: {"label": "1250"}}) != 5
    assert not R.alike("F1.1", "F11") and not R.alike('2.5"', '25"') and not R.alike("1/250", "1250")
    # what norm's leniency was for still holds: the same label, its case, spacing, a dot, a sign spelled out
    assert R.judge({"5 Img.": 3, "-(minus) -> 0 -> +(plus)": 4}, {3: "5 img", 4: "-→0→+"}) == ("agrees", [])
    assert R.option_key({"index": 2, "label": "ISO 100"}, {2: {"label": "ISO100"}}) == 2
    assert R.alike("FINE", "FINE Fine") and R.alike("4:3", "4:3 4:3") and R.alike("F1.1", "F1.1")


# ------------------------------------------------------------------------------------------------ finding 11 (B3)

class SwitchCam:
    """A LiveCamera for pass3_run.switch: every press recorded; after Enter the screen is `after` ("notice" or
    "menu")."""

    def __init__(self, after: str):
        self.after, self.presses, self.kind = after, [], "menu"
        self.frame = types.SimpleNamespace(path=Path("00042_enter.png"))

    def press(self, key, **kw):
        self.presses.append(key)
        if key == "right":
            self.kind = "list"
        elif key == "enter":
            self.kind = self.after
        elif key == "menu" and self.kind in ("notice", "list"):
            self.kind = "menu"

    def read(self):
        return types.SimpleNamespace(kind=self.kind)

    def cancel_to_menu(self):
        if self.kind not in ("menu", "shooting"):
            self.presses.append("menu")
            self.kind = "menu"


def switch_world(monkeypatch, after: str, notice: str = "", cur: int = 0):
    import pass3_run
    cam = SwitchCam(after)
    monkeypatch.setattr(pass3_run, "LiveCamera", lambda link, hdmi, run: cam)
    monkeypatch.setattr(pass3_run, "same_position", lambda a, b: True)
    monkeypatch.setattr(pass3_run, "go_to", lambda cam, cycle, model, j, label: 0)
    monkeypatch.setattr(pass3_run, "enter_any", lambda cam, path, i: None)
    monkeypatch.setattr(pass3_run, "labels_of",
                        lambda path, mp=None: (["Electronic Shutter", "Mechanical Shutter"], "list"))
    at = {"i": cur}
    monkeypatch.setattr(pass3_run, "option_index", lambda cam, labels, kind: at["i"])
    monkeypatch.setattr(pass3_run, "move_to", lambda cam, cur, k, n, kind: at.update(i=k))
    monkeypatch.setattr(pass3_run, "to_shooting", lambda link, hdmi, why: None)
    monkeypatch.setattr(pass3_run, "notice_text", lambda cam: notice)
    return pass3_run, cam


def test_a_refusal_after_the_blockers_ok_fails_the_switch_in_plain_words(monkeypatch):
    """pass3_run.switch closed any notice after OK and went on: a refusal ("not available as follows ...") left the
    camera unswitched while the walk and the proofs were tagged with the blocker's state."""
    from proving.base import Failed
    b = {"row": ["Shutter Type"], "to": "Mechanical Shutter", "walk": "Long Exposure NR"}
    pass3_run, cam = switch_world(monkeypatch, "notice", "Not available as follows: Shoot Mode   OK")
    with pytest.raises(Failed, match=r"the camera refused 'Mechanical Shutter' \('Not available as follows: Shoot "
                                     r"Mode OK'; 00042_enter.png\): the blocker was not switched"):
        pass3_run.switch(None, None, None, [{"screen": None}], {}, b)
    assert cam.presses == ["menu", "right", "enter", "menu"] and cam.kind == "menu"
    # a question after OK: nothing answered, MENU cancels it before the link may drop
    pass3_run, cam = switch_world(monkeypatch, "notice", "Execute? Cancel OK")
    monkeypatch.setattr(pass3_run.safety, "confirmation", lambda text: "a question" if "?" in text else "")
    with pytest.raises(Failed, match="the camera asked a question"):
        pass3_run.switch(None, None, None, [{"screen": None}], {}, b)
    assert cam.presses == ["menu", "right", "enter", "menu"]
    # an information notice is closed with MENU and the switch goes on; it says the cursor moved
    pass3_run, cam = switch_world(monkeypatch, "notice", "Enters the state with Flash Effect dur Sht. applied OK")
    assert pass3_run.switch(None, None, None, [{"screen": None}], {}, b) is True
    assert cam.presses == ["menu", "right", "enter", "menu"]
    # the list opened on the option already: nothing to change, said so
    pass3_run, cam = switch_world(monkeypatch, "menu", cur=1)
    assert pass3_run.switch(None, None, None, [{"screen": None}], {}, b) is False


def test_a_switch_whose_download_shows_no_record_of_its_row_stops_the_blocker(monkeypatch, capsys):
    """The switched download was printed and never checked: now the blocker stops, nothing walked or proved, and the
    start file goes back on, where no record of a switched row differs from the start."""
    import pass3_run
    from camkit import camset, models
    monkeypatch.setattr(pass3_run, "definition", lambda: {"settings": [
        {"key": "global:0x02dd", "row": ["Shutter Type"], "copies": ["global:0x02df"]},
        {"key": "global:0x0288", "row": ["Long Exposure NR"]}]})

    def change(rid):
        return camset.Change(0, rid, 0, 1)
    assert pass3_run.row_records(["Shutter Type"]) == {"global:0x02dd", "global:0x02df"}
    moved = [(["Shutter Type"], "Mechanical Shutter")]
    assert pass3_run.switch_took([change(0x02df)], moved) == ""
    assert ("did not take: the download after it differs from the start in no record of that row (global:0x02dd, "
            "global:0x02df)") in pass3_run.switch_took([change(0x0288)], moved)
    assert "in no record at all" in pass3_run.switch_took([], [(["Unknown Row"], "On")])
    assert pass3_run.switch_took([], []) == ""                  # nothing moved: nothing to show

    class Link:
        def __init__(self, run):
            self.n = 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def download(self, tag):
            self.n += 1
            return Path(f"0000{self.n}_{tag}.DAT")
    eyes = types.SimpleNamespace(attach=lambda link: None, close=lambda: None)
    walked, restored = [], []
    monkeypatch.setattr(pass3_run, "Link", Link)
    monkeypatch.setattr(pass3_run, "eyes_from_config", lambda run: eyes)
    monkeypatch.setattr(pass3_run, "to_shooting", lambda link, eyes, why: None)
    monkeypatch.setattr(pass3_run.time, "sleep", lambda s: None)
    monkeypatch.setattr(pass3_run.camset, "read", lambda p: types.SimpleNamespace(model=models.A1II, get=lambda *a: None))
    monkeypatch.setattr(pass3_run.camset, "diff", lambda a, b: [change(0x0288)])
    monkeypatch.setattr(pass3_run, "enter_state", lambda link, hdmi, run, cycle, model, b: moved)
    monkeypatch.setattr(pass3_run, "walk_and_prove", lambda b, log: walked.append(b) or 0)
    monkeypatch.setattr(pass3_run, "restore", lambda run, start: restored.append(start.name) or 0)
    blocker = {"row": ["Shutter Type"], "to": "Mechanical Shutter", "walk": "Long Exposure NR"}
    assert pass3_run.run_blockers("run", [], {}, [blocker], None) is True
    assert walked == [] and restored == ["00001_p3-start.DAT"]
    assert "the switch failed: the switch of Shutter Type to 'Mechanical Shutter' did not take" in capsys.readouterr().out
    monkeypatch.setattr(pass3_run.camset, "diff", lambda a, b: [change(0x02dd)])
    restored.clear()
    assert pass3_run.run_blockers("run", [], {}, [blocker], None) is True
    assert walked == [blocker] and restored == ["00001_p3-start.DAT"]


# ------------------------------------------------------------------------------------------------ finding 12

LOWER, UPPER = (0x0b65, 0x0b69, 0x0b6d), (0x0b63, 0x0b67, 0x0b6b)     # ISO Range Limit's records, as the definition has


class Lines(list):
    """A proofs file: each line written, as a dict; `context` as proving.base.Tagged has it."""
    context = None

    def write(self, line):
        self.append(__import__("json").loads(line))

    def flush(self):
        pass


class Settings:
    """A made-up camera's settings files: each download a snapshot of the records (a code per record), read and diffed
    as camkit.camset reads and diffs them."""

    def __init__(self):
        self.files = {}

    def keep(self, name: str, records: dict) -> Path:
        self.files[name] = dict(records)
        return Path(name)

    def read(self, path):
        return self.files[Path(path).name]

    def diff(self, a, b):
        from camkit import camset
        return [camset.Change(0, rid, a[rid], b[rid]) for rid in sorted(a) if a[rid] != b[rid]]


class LimitsCam:
    """ISO Range Limit as the a1 II keeps it (2026-11-18): two number fields, the lower and the upper limit, each a step
    of the ISO list (code = step + 2); OK on a lower limit above the upper pushes the upper up to it, on an upper below
    the lower pulls the lower down to it, and the moved one stays. factory: {field: code} a file holds that no step of
    the list writes, until that field is chosen."""

    def __init__(self, settings: Settings, lo: int, hi: int, factory=None):
        self.settings, self.at, self.factory = settings, [lo, hi], dict(factory or {})
        self.kind, self.field, self.pending, self.n = "menu", 0, None, 0
        self.frame = types.SimpleNamespace(path=Path("00001_right.png"))

    def records(self) -> dict:
        out = {}
        for f, rids in ((0, LOWER), (1, UPPER)):
            out.update(dict.fromkeys(rids, self.factory.get(f, self.at[f] + 2)))
        return out

    def press(self, key, **kw):
        if key == "right":
            if self.kind == "menu":
                self.kind, self.field, self.pending = "fields", 0, list(self.at)
            else:
                self.field += 1
        elif key in ("up", "down") and self.kind == "fields":
            self.pending[self.field] = max(0, min(33, self.pending[self.field] + (1 if key == "down" else -1)))
        elif key == "enter" and self.kind == "fields":
            f, t = self.field, self.pending[self.field]
            self.at[f] = t
            self.factory.pop(f, None)
            if f == 0 and t > self.at[1]:
                self.at[1] = t
                self.factory.pop(1, None)
            if f == 1 and t < self.at[0]:
                self.at[0] = t
                self.factory.pop(0, None)
            self.kind = "menu"
        elif key == "menu":
            self.kind = "menu"

    def read(self):
        return types.SimpleNamespace(kind=self.kind, field=self.field)

    def cancel_to_menu(self):
        self.kind = "menu"

    def download(self, tag):
        self.n += 1
        return self.settings.keep(f"{self.n:05d}_{tag}.DAT", self.records())


def limits_world(monkeypatch, cam):
    """proving.fields over LimitsCam: its fields read off the made-up screen, the menu's way back made up."""
    from proving import fields
    from proving.jobs import LABELS
    iso = LABELS["ISO"][1:]
    monkeypatch.setattr(fields, "camset", cam.settings)
    monkeypatch.setattr(fields, "field_at", lambda c, k, fld: c.pending[k] if c.kind == "fields" else None)
    monkeypatch.setattr(fields, "field_values", lambda c: [iso[i] for i in c.pending] if c.kind == "fields" else [])
    monkeypatch.setattr(fields, "to_row", lambda c, path, top=None, row_place=None: c.cancel_to_menu())
    monkeypatch.setattr(fields, "place", lambda c: "the row")
    monkeypatch.setattr(fields, "same_place", lambda a, b: True)
    monkeypatch.setattr(fields, "after_download", lambda c, done: None)
    monkeypatch.setattr(fields, "later", lambda read, c: None)
    job = {"path": ["ISO Range Limit"], "kind": "fields", "wrap": False, "inc": "down",
           "fields": [{"labels": iso, "values": iso, "plan": [0, 17, 33]} for _ in range(2)]}
    return fields, job


def own_only(lines):
    """Each line's changes but those it names as the other field's are its own field's records."""
    for r in lines:
        other = {c["key"] for c in (r.get("moved_other") or {}).get("changes") or []}
        mine = {c["key"] for c in r["changes"]} - other
        rids = LOWER if r["index"][0] == 0 else UPPER
        assert mine <= {f"global:0x{x:04x}" for x in rids}, r


def test_iso_range_limits_that_drag_each_other_are_put_back_and_no_line_carries_a_leftover(monkeypatch, tmp_path):
    """Both directions on one row (start: lower ISO 80, upper ISO 32000): a lower limit chosen above the upper pushes it
    up (field 0's ISO 102400), an upper chosen below the lower pulls it down (field 1's ISO 50). Each such line says so
    ("moved_other": the other field and its records' changes), the other field is put back on its start value through
    the menu and checked, and every later line carries only its own field's records; both closing proofs change
    nothing. Before, the other limit's change rode on every later line and the closing proof failed."""
    settings = Settings()
    cam = LimitsCam(settings, 2, 30)
    fields, job = limits_world(monkeypatch, cam)
    base = settings.keep("00000_before.DAT", cam.records())
    out, run = Lines(), types.SimpleNamespace(dir=tmp_path)
    fields.prove_fields_row(cam, cam, run, job, base, out)
    got = [(tuple(r["index"]), r["applied"], (r.get("moved_other") or {}).get("field")) for r in out]
    assert got == [((0, 0), True, None), ((0, 17), True, None), ((0, 33), True, 1), ((0, 2), True, None),
                   ((1, 0), True, 0), ((1, 17), True, None), ((1, 33), True, None), ((1, 30), True, None)]
    assert {c["key"] for c in out[2]["moved_other"]["changes"]} == {f"global:0x{x:04x}" for x in UPPER}
    assert {c["key"] for c in out[4]["moved_other"]["changes"]} == {f"global:0x{x:04x}" for x in LOWER}
    own_only(out)
    assert out[3]["changes"] == [] and out[7]["changes"] == []
    backs = [n for n in settings.files if n.endswith("-back.DAT")]
    assert backs == ["00004_ISO Range Limit-1-30-back.DAT", "00007_ISO Range Limit-0-2-back.DAT"]
    assert cam.at == [2, 30]
    # the report reads such a line without the other field's records (pass2_report.own_changes)
    import pass2_report as R
    assert {c["key"] for c in R.own_changes(out[2])["changes"]} == {f"global:0x{x:04x}" for x in LOWER}


def test_one_field_alone_learns_the_other_fields_records_from_the_proofs_file(monkeypatch, tmp_path, capsys):
    """prove_run --field 1 (only_field): with no earlier line telling the fields' records apart, an upper limit that
    pulled the lower down ends the row, nothing written for it; with the lower limit's earlier lines in the proofs file
    (the same state), the pull is told by its records, said, and put back."""
    import json
    settings = Settings()
    cam = LimitsCam(settings, 2, 30)
    fields, job = limits_world(monkeypatch, cam)
    job["only_field"] = 1
    base = settings.keep("00000_before.DAT", cam.records())
    out, run = Lines(), types.SimpleNamespace(dir=tmp_path)
    from proving.base import Failed
    with pytest.raises(Failed, match="also moved field 0 on the screen, and no proof has told the fields' records apart"):
        fields.prove_fields_row(cam, cam, run, job, base, out)
    assert [r["applied"] for r in out] == []
    earlier = {"path": ["ISO Range Limit"], "kind": "fields", "index": [0, 0], "applied": True,
               "changes": [{"key": f"global:0x{x:04x}", "before": 9, "after": 2} for x in LOWER]}
    (tmp_path / "proofs.jsonl").write_text(json.dumps(earlier) + "\n", encoding="utf-8")
    cam = LimitsCam(settings, 2, 30)
    fields, job = limits_world(monkeypatch, cam)
    job["only_field"] = 1
    out = Lines()
    fields.prove_fields_row(cam, cam, run, job, settings.keep("00100_before.DAT", cam.records()), out)
    assert [(tuple(r["index"]), (r.get("moved_other") or {}).get("field")) for r in out] == [
        ((1, 0), 0), ((1, 17), None), ((1, 33), None), ((1, 30), None)]
    own_only(out)
    assert "field 0 put back on 'ISO 80' through the menu" in capsys.readouterr().out


def test_a_factory_value_the_menu_cannot_choose_again_ends_the_field_in_plain_words(monkeypatch, tmp_path):
    """The lower limit holds a factory code no step writes (as ISO AUTO's factory Minimum): an upper limit chosen below
    it pulls it down, and choosing its start step again writes another code, so the row ends there, said in plain
    words, the pulling line written (with moved_other) and no line after it."""
    import json
    settings = Settings()
    cam = LimitsCam(settings, 2, 30, factory={0: 99})
    fields, job = limits_world(monkeypatch, cam)
    job["only_field"] = 1
    earlier = {"path": ["ISO Range Limit"], "kind": "fields", "index": [0, 5], "applied": True,
               "changes": [{"key": f"global:0x{x:04x}", "before": 9, "after": 7} for x in LOWER]}
    (tmp_path / "proofs.jsonl").write_text(json.dumps(earlier) + "\n", encoding="utf-8")
    out = Lines()
    from proving.base import Failed
    with pytest.raises(Failed, match=r"choosing its start value 'ISO 80' again through the menu does not bring back "
                                     r"what the start file holds in global:0x0b65, global:0x0b69, global:0x0b6d .*a "
                                     r"value the menu cannot choose again"):
        fields.prove_fields_row(cam, cam, types.SimpleNamespace(dir=tmp_path), job,
                                settings.keep("00000_before.DAT", cam.records()), out)
    assert [(tuple(r["index"]), (r.get("moved_other") or {}).get("field")) for r in out] == [((1, 0), 0)]


class BoxesCam(LimitsCam):
    """ISO AUTO's Minimum and Maximum as two boxes (boxes_run), each a step of its list ISO100 ... ISO1600 (code = step
    + 5), the camera keeping Minimum <= Maximum; and choosing a Maximum rewrites a factory Minimum (2026-11-18)."""
    VALS = ["ISO100", "ISO125", "ISO160", "ISO200", "ISO250", "ISO320", "ISO400", "ISO500", "ISO640", "ISO800",
            "ISO1000", "ISO1250", "ISO1600"]
    MIN, MAX = (0x0dfa, 0x0dfc, 0x0dfe), (0x0e00, 0x0e02, 0x0e04)

    def records(self) -> dict:
        out = dict.fromkeys(self.MIN, self.factory.get(0, self.at[0] + 5))
        out.update(dict.fromkeys(self.MAX, self.at[1] + 5))
        return out

    def choose(self, b: int, t: int):
        self.at[b] = t
        self.factory.pop(0, None)              # any choice rewrites a factory Minimum into its list
        if b == 0 and t > self.at[1]:
            self.at[1] = t
        if b == 1 and t < self.at[0]:
            self.at[0] = t


def boxes_world(monkeypatch, cam, tmp_path, history=()):
    """boxes_run.prove over BoxesCam: the look and the choice made up on its boxes, the proofs file in tmp_path holding
    `history`."""
    import json

    import boxes_run
    names = ["ISO AUTO Minimum", "ISO AUTO Maximum"]

    def look(c, link, cycle, model, path, b, seen=None):
        if seen is not None:
            seen.setdefault(b, c.VALS[c.at[b]])
            seen.setdefault(1 - b, c.VALS[c.at[1 - b]])
        return list(c.VALS), c.VALS[c.at[b]]

    def choose(c, link, hdmi, cycle, model, path, b, vals, target, names_):
        c.choose(b, target)
        return {"dat": c.download(f"ISO-{b}-{target}"), "chosen_frame": "00002_down.png", "row_frame": "00003_enter.png",
                "vlm": None}
    monkeypatch.setattr(boxes_run, "look", look)
    monkeypatch.setattr(boxes_run, "choose", choose)
    monkeypatch.setattr(boxes_run, "camset", cam.settings)
    proofs = tmp_path / "proofs.jsonl"
    proofs.write_text("".join(json.dumps(h) + "\n" for h in history), encoding="utf-8")
    out = Lines()
    out.f = types.SimpleNamespace(name=str(proofs))
    return boxes_run, names, out


def box_line(name: str, rids, index: int) -> dict:
    return {"path": ["ISO", name], "kind": "list", "index": index, "boxes": True, "applied": True,
            "changes": [{"key": f"global:0x{x:04x}", "before": 1, "after": index + 5} for x in rids]}


def test_iso_auto_boxes_that_push_each_other_are_put_back_and_the_last_proof_changes_nothing(monkeypatch, tmp_path):
    """boxes_run, the boxes' records known from earlier lines: a Minimum chosen above the Maximum pushes it up, a
    Maximum chosen below the Minimum pulls it down; each such line says so, the other box goes back on its value as the
    screen opened, through the menu, and no later line carries it."""
    settings = Settings()
    cam = BoxesCam(settings, 3, 6)                       # Minimum ISO200, Maximum ISO400
    history = [box_line("ISO AUTO Minimum", BoxesCam.MIN, 2), box_line("ISO AUTO Maximum", BoxesCam.MAX, 9)]
    boxes_run, names, out = boxes_world(monkeypatch, cam, tmp_path, history)
    start = settings.keep("00000_before.DAT", cam.records())
    assert boxes_run.prove(cam, cam, None, None, None, ["ISO"], names, None, None, start, out) is start
    moved = [(r["path"][-1], r["label"], r["moved_other"]["box"]) for r in out if r.get("moved_other")]
    assert moved == [("ISO AUTO Minimum", v, "ISO AUTO Maximum") for v in BoxesCam.VALS[7:]] + \
        [("ISO AUTO Maximum", v, "ISO AUTO Minimum") for v in BoxesCam.VALS[:3]]
    for r in out:
        other = {c["key"] for c in (r.get("moved_other") or {}).get("changes") or []}
        rids = BoxesCam.MIN if r["path"][-1] == "ISO AUTO Minimum" else BoxesCam.MAX
        assert {c["key"] for c in r["changes"]} - other <= {f"global:0x{x:04x}" for x in rids}, r
    assert [r["changes"] for r in out if r["label"] == BoxesCam.VALS[3] and r["path"][-1] == names[0]] == [[]]
    assert cam.at == [3, 6]


def test_a_maximum_that_rewrites_the_factory_minimum_ends_its_box_in_plain_words(monkeypatch, tmp_path):
    """kit2_pass2 8648-8678: every ISO AUTO Maximum line carried the Minimum's records (its factory value rewritten into
    the list) and the closing line failed. Now the first such line says so, the Minimum is chosen again through the
    menu, its records do not come back, and the box's proofs end there in plain words: one line written."""
    settings = Settings()
    cam = BoxesCam(settings, 0, 6, factory={0: 3})       # the factory Minimum, shown as the list's first step
    boxes_run, names, out = boxes_world(monkeypatch, cam, tmp_path, [box_line("ISO AUTO Minimum", BoxesCam.MIN, 2)])
    from proving.base import Failed
    with pytest.raises(Failed, match=r"choosing 'ISO100' in ISO AUTO Minimum again through the menu does not bring "
                                     r"back what the start held in global:0x0dfa, global:0x0dfc, global:0x0dfe .*a "
                                     r"value the menu cannot choose again"):
        boxes_run.prove(cam, cam, None, None, None, ["ISO"], names, "ISO AUTO Maximum", None,
                        settings.keep("00000_before.DAT", cam.records()), out)
    assert [(r["label"], r["moved_other"]["box"]) for r in out] == [("ISO100", "ISO AUTO Minimum")]


def test_prove_run_field_names_one_field_of_the_rows_named(monkeypatch):
    """prove_run --field K: only with --rows, only on a number-field row that has field K."""
    import prove_run
    todo = [{"path": ["ISO Range Limit"], "kind": "fields", "fields": [{}, {}]}, {"path": ["X"], "kind": "list"}]
    got = prove_run.only_field_or_exit(todo, 1, ["ISO Range Limit"])
    assert got[0]["only_field"] == 1 and "only_field" not in got[1]
    with pytest.raises(SystemExit, match="--rows only"):
        prove_run.only_field_or_exit(todo, 1, None)
    with pytest.raises(SystemExit, match="has no field 2"):
        prove_run.only_field_or_exit(todo, 2, ["ISO Range Limit"])
    with pytest.raises(SystemExit, match="none of the rows named is number fields"):
        prove_run.only_field_or_exit(todo[1:], 0, ["X"])


# ------------------------------------------------------------------------------------------------ finding 14 (B6, B7)

def test_a_vote_is_counted_per_model_family_not_per_configured_id():
    """The documented second and third readers are one model in two quantisations (RedHatAI/Qwen3.8-27B-INT4 on vLLM,
    Qwen3.8-27B-4bit on omlx): what only names a build (a quantisation, a weights format, the repository's owner) is
    left out of the vote's key, so they are one vote; another size, version or tune stays another model."""
    from camkit import reading
    one = ["RedHatAI/Qwen3.8-27B-INT4", "Qwen3.8-27B-4bit", "mlx-community/Qwen3.8-27B-4bit", "qwen3.8:27b-q4_K_M",
           "Qwen3.8-27B-Q4_K_M.gguf", "Qwen3.8-27B-AWQ", "Qwen3.8-27B-W4A16", "Qwen3.8-27B-FP8", " Qwen3.8-27B "]
    assert {reading.model_id(m) for m in one} == {"qwen3.8-27b"}
    others = ["Qwen3.8-8B-4bit", "Qwen3.7-27B-INT4", "Qwen3.8-27B-Instruct-INT4", "claude-opus-5-5", "gpt-4o"]
    assert len({reading.model_id(m) for m in others} | {"qwen3.8-27b"}) == len(others) + 1
    votes = [reading.Vote("reader", f"reader:{reading.model_id(one[0])}", "Auto"),
             reading.Vote("third", f"reader:{reading.model_id(one[1])}", "Auto")]
    assert reading.tally(votes, "label", ["Auto", "Manual"]) == (None, ())          # one model, one vote


def test_the_start_check_says_when_two_reader_roles_are_one_model_family(monkeypatch, capsys):
    """The start check names it, in plain words, when the second and third readers are one model in two builds."""
    import camkit
    from camkit import vlm
    monkeypatch.setattr(camkit, "config", lambda required=True: {
        "readers": [{"name": "vllm", "url": "http://127.0.0.1:8000/v1", "model": "RedHatAI/Qwen3.8-27B-INT4"},
                    {"name": "omlx", "url": "http://127.0.0.1:8001/v1", "model": "Qwen3.8-27B-4bit"}]})
    monkeypatch.setattr(vlm, "config", camkit.config)
    checks = [vlm.Check("vllm", "openai-compatible", "Qwen3.8-27B-INT4", False, ("second",), asked=True, ok=True,
                        seconds=1.0, said="MENU 42"),
              vlm.Check("omlx", "openai-compatible", "Qwen3.8-27B-4bit", False, ("third",), asked=True, ok=True,
                        seconds=1.0, said="MENU 42")]
    vlm._passed(checks)
    said = capsys.readouterr().out
    assert ("the second reader 'vllm' and the third reader 'omlx' are one model, qwen3.8-27b, in two builds: their "
            "answers are one vote, not two") in said


def png(level: int) -> bytes:
    import io

    import numpy as np
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(np.full((48, 64, 3), level, np.uint8)).save(buf, format="PNG")
    return buf.getvalue()


def test_every_question_refuses_a_black_frame_and_a_reader_down_costs_one_timeout(monkeypatch):
    """The black-frame refusal and the reader-down latch lived in camkit.reading.ask, which no prover calls: a hung
    reader cost its timeout on every question, and a black frame could be asked about. Both are now in vlm.ask_role,
    the call every question passes: a black frame is refused before anything is sent (and counts as no failure), and
    after DOWN_AFTER failures in a row the role is not asked for DOWN_FOR seconds."""
    from camkit import vlm
    sent = []

    class Reader:
        served = None

        def __init__(self, **cfg):
            pass

        def ask(self, image, prompt):
            sent.append(prompt)
            raise TimeoutError("timed out")
    monkeypatch.setattr(vlm, "playing", lambda name: {"name": "slow", "url": "http://127.0.0.1:8000/v1", "model": "m"})
    monkeypatch.setattr(vlm, "make_reader", lambda cfg, **kw: Reader())
    monkeypatch.setattr(vlm, "stand_in", lambda name, failed: None)
    with pytest.raises(vlm.BlackFrame, match="black frame"):
        vlm.ask_role("second", png(0), "a question", 5)
    assert sent == [] and not vlm.reader_down("second")
    for _ in range(vlm.DOWN_AFTER):
        with pytest.raises(TimeoutError):
            vlm.ask_role("second", png(40), "a question", 5)
    assert len(sent) == vlm.DOWN_AFTER and vlm.reader_down("second")
    with pytest.raises(vlm.ReaderDown, match="did not answer just before"):
        vlm.ask_role("second", png(40), "a question", 5)
    assert len(sent) == vlm.DOWN_AFTER                     # nothing sent while it is down: no timeout spent
    assert not vlm.reader_down("third")
    vlm.forget()
    assert not vlm.reader_down("second")
    assert vlm.ask_role.__doc__ and "BlackFrame" in vlm.ask_role.__doc__


# ------------------------------------------------------------------------------------------------ B5

def page_world(*labels):
    """A page scan of one Exposure/Color page whose rows the page model reads as `labels`, the cycle one position per
    row."""
    model = {"p": {"key": "p", "breadcrumb": "Exposure/Color > Exposure", "rows": [{"label": x} for x in labels]}}
    cycle = [{"kind": "menu", "page": "p", "row": i} for i in range(len(labels))]
    return cycle, model


def test_target_of_takes_the_row_named_exactly_and_never_one_of_two_it_only_reads_as_the_label():
    """crawl_run.target_of took the first of several rows page_model.same_text reads as the label, which leaves out a
    leading word of one or two letters: "Tv Auto/Manual Switch" went to the Av row when that came first. Now a row
    whose page model label is the label itself is taken; rows only read as it that bear two labels are none; one only
    read as it is found by another reading, so go_to reads its lit bar after travel."""
    import crawl_run
    cycle, model = page_world("Av Auto/Manual Switch", "Tv Auto/Manual Switch")
    assert crawl_run.target_of(cycle, model, "Tv Auto/Manual Switch") == (1, False, "")
    assert crawl_run.target_of(cycle, model, "Av Auto/Manual Switch") == (0, False, "")
    target, _, why = crawl_run.target_of(cycle, model, "Auto/Manual Switch")
    assert target is None and "2 rows with other labels read as it ('Av Auto/Manual Switch', 'Tv Auto/Manual " \
        "Switch'): none is gone to" in why
    cycle, model = page_world("Shutter Type", "SDrive Mode")
    assert crawl_run.target_of(cycle, model, "Drive Mode") == (1, True, "")         # its bar read after travel
    assert crawl_run.target_of(cycle, model, "Shutter Type") == (0, False, "")


# ------------------------------------------------------------------------------------------------ B11

def test_the_ocr_cache_keeps_the_frames_used_last_and_a_long_batch_still_reads_whole(monkeypatch, tmp_path):
    """camkit.ocr kept every frame's reading for the life of the process (a night's run: tens of thousands); it keeps
    the CACHE_MAX used last, and a batch longer than that still gives every frame its own lines."""
    from camkit import ocr
    recent = ocr.Recent(2)
    recent["a"], recent["b"] = 1, 2
    assert recent["a"] == 1
    recent["c"] = 3
    assert list(recent) == ["a", "c"]                    # "b", used least lately, went
    monkeypatch.setattr(ocr, "_cache", ocr.Recent(2))
    monkeypatch.setattr(ocr, "_rapidocr", lambda p: [{"text": p.name, "conf": 1.0, "x": 0, "y": 0, "w": 1, "h": 1}])
    frames = []
    for i in range(5):
        frames.append(tmp_path / f"{i:05d}.png")
        frames[-1].write_bytes(f"frame {i}".encode())
    got = ocr.read(frames, eng="rapidocr")
    assert [got[p][0].text for p in frames] == [p.name for p in frames] and len(ocr._cache) == 2
