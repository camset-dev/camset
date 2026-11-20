"""kit/tools/label_audit.py: the definition's value names read again by every reader on their proof frames, with fake
readers and a small made-up camera (made-up labels, "Zqx ..."), as reader_census's tests do: the scope, one vote per
model family, the four verdicts, nothing asked twice, the hosted and local-only rules, no label on the console, and the
private file's place."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, reading, runs, safety, vlm  # noqa: E402

CAMERA = "TEST-CAM_fw9.99"
LIST = vlm.PROMPTS[reading.QUESTIONS["list"].prompt]
CHECKLIST = vlm.PROMPTS[reading.QUESTIONS["checklist"].prompt]
AXIS = vlm.PROMPTS[reading.QUESTIONS["axis"].prompt]
LOCAL = "http://127.0.0.1:9/v1"
FAR = "http://203.0.113.7/v1"            # a documentation address: no one's own network, so a hosted reader
QWEN_A, QWEN_B, GEMMA = "Org/Qwen9-27B-INT4", "Qwen9-27B-4bit", "gemma-9-12b"      # two builds of one model, another


def line(path, index, label, frame, **more) -> dict:
    return {"path": path, "kind": "list", "index": index, "label": label, "shown": label, "changes": [],
            "chosen_frame": frame, **more}


def record(proved: dict, word: str) -> dict:
    return {"verdict": "agrees", "notes": [], "proved": proved, "names": {lab: word for lab in proved}}


def setting(key: str, values: list, names: dict) -> dict:
    return {"key": key, "name": key, "values": values, "proved": {"values": [v for v, _ in values], "names": names}}


def frame(path: Path, level: int) -> None:
    import numpy as np
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.full((480, 640, 3), level, np.uint8)).save(path)


def proof_run(root: Path, name: str, lines: list, marker: str | None = None) -> Path:
    run = root / name
    (run / "shots").mkdir(parents=True)
    (run / runs.PROOF_RUN).write_text(json.dumps({"by": "test", "since": "2026-11-20"}) + "\n", encoding="utf-8")
    (run / "proofs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")
    if marker:
        (run / marker).write_text("test\n", encoding="utf-8")
    return run


def camera(top: Path, tmp_path: Path) -> tuple:
    """(the run root, the definition file) of a made-up camera: a list row of four options named by one reader or the
    vision model, a checklist box (its names the schema's, in scope by its kind), a row two readers named (out of the
    default scope, one of its frames black, another holding a second record's name no hosted reader is sent), an
    identity row's line, a frame not on disk, a carousel axis, and a proof run of each: one a --network run marked
    local-only, one an owner run no reader reads, one named for a network look (its name the vision model's)."""
    root = top / CAMERA
    main = root / runs.MAIN_RUN
    (main / "shots").mkdir(parents=True)
    mode = ["Zqx Alpha", "Zqx Beta", "Zqx Gamma", "Zqx Delta"]
    lines = [line(["Zqx Mode"], i, lab, f"0000{i + 1}.png") for i, lab in enumerate(mode)]
    lines.append({"path": ["Zqx Set"], "kind": "checklist", "index": 1, "label": "Zqx Two", "changes": [],
                  "chosen_frame": "00005.png", "boxes": [{"box": 0, "label": "Zqx One", "ticked": False},
                                                         {"box": 1, "label": "Zqx Two", "ticked": True}]})
    lines += [line(["Zqx Other"], 0, "Zqx On", "00006.png", vlm="Zqx On"),
              line(["Zqx Other"], 1, "Zqx Off", "00007.png", vlm="Zqx Off"),
              line(["Zqx Ident"], 0, "Zqx Name", "00008.png", network=safety.LIFT_IDENTITY),
              line(["Zqx Gone"], 0, "Zqx Lost", "00009.png")]
    # a carousel axis: in its own row Zqx Spot: S is proved by the put-back visit alone (its first visit taken over by
    # it), in a row of a context by a visit whose OCR at OK read "Zqx Spot: 5", which the report credits by its label
    axis = {"kind": "axis", "option": "Zqx Spot"}
    lines += [line(["Zqx Area"], 0, "Zqx Spot: S", "00012.png", **axis),
              line(["Zqx Area"], 1, "Zqx Spot: L", "00010.png", **axis),
              line(["Zqx Area"], 0, "Zqx Spot: S", "00011.png", final=True, **axis),
              line(["Zqx Area"], 0, "Zqx Spot: S", "00012.png", shown="Zqx Spot: 5", context="Zqx Ctx = On", **axis)]
    (main / "proofs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in lines), encoding="utf-8")
    for n in (1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12):           # 00009.png, Zqx Lost's, is not on disk
        frame(main / "shots" / f"{n:05d}.png", 0 if n == 7 else 60 + n)
    near = proof_run(root, "kit2_zqx_local", [line(["Zqx Local"], 0, "Zqx Near", "00001.png")], vlm.LOCAL_MARKER)
    held = proof_run(root, "kit2_zqx_held", [line(["Zqx Held"], 0, "Zqx Kept", "00001.png")], vlm.NO_READER_MARKER)
    wide = proof_run(root, "kit2_net_zqx", [line(["Zqx Net"], 0, "Zqx Wide", "00001.png")])
    for run, level in ((near, 90), (held, 91), (wide, 92)):
        frame(run / "shots" / "00001.png", level)
    report = [
        {"row": "Zqx Mode", "kinds": ["list"], "options": 4,
         "records": {"global:0x0001": record({lab: i for i, lab in enumerate(mode)}, "one reader (map)")}},
        {"row": "Zqx Set", "kinds": ["checklist"], "options": 1,
         "records": {"global:0x0002": record({"Zqx Two: ticked": 1, "Zqx Two: unticked": 0}, "box")}},
        {"row": "Zqx Other", "kinds": ["list"], "options": 2,
         "records": {"global:0x0003": record({"Zqx On": 1, "Zqx Off": 0}, "two readers"),
                     "global:0x000a": record({"Zqx On": 1}, "two readers")}},
        {"row": "Zqx Ident", "kinds": ["list"], "options": 1, "records": {"global:0x0004": record({"Zqx Name": 0}, "one reader (map)")}},
        {"row": "Zqx Gone", "kinds": ["list"], "options": 1, "records": {"global:0x0005": record({"Zqx Lost": 0}, "one reader (map)")}},
        {"row": "Zqx Local", "kinds": ["list"], "options": 1, "records": {"global:0x0006": record({"Zqx Near": 0}, "one reader (map)")}},
        {"row": "Zqx Held", "kinds": ["list"], "options": 1, "records": {"global:0x0007": record({"Zqx Kept": 0}, "one reader (map)")}},
        {"row": "Zqx Net", "kinds": ["list"], "options": 1, "records": {"global:0x0008": record({"Zqx Wide": 0}, "one reader (map)")}},
        {"row": "Zqx Area / Zqx Spot", "kinds": ["axis"], "options": 2,
         "records": {"global:0x000b": record({"Zqx Spot: S": 0, "Zqx Spot: L": 1}, "carousel")}},
        {"row": "Zqx Area / Zqx Spot [Zqx Ctx = On]", "kinds": ["axis"], "options": 1,
         "records": {"global:0x000b": record({"Zqx Spot: S": 0}, "carousel")}},
    ]
    (main / "report.json").write_text(json.dumps(report), encoding="utf-8")
    one = "one reader"
    doc = {"settings": [
        setting("global:0x0001", [[i, lab] for i, lab in enumerate(mode)], {"0": one, "1": one, "2": "vision model", "3": one}),
        setting("global:0x0002", [[0, "Not ticked"], [1, "Ticked"]], {"0": "schema kept", "1": "schema kept"}),
        setting("global:0x0003", [[0, "Zqx Off"], [1, "Zqx On"]], {"0": "two readers", "1": "two readers"}),
        setting("global:0x0004", [[0, "Zqx Name"]], {"0": one}),
        setting("global:0x0005", [[0, "Zqx Lost"]], {"0": one}),
        setting("global:0x0006", [[0, "Zqx Near"]], {"0": one}),
        setting("global:0x0007", [[0, "Zqx Kept"]], {"0": one}),
        setting("global:0x0008", [[0, "Zqx Wide"]], {"0": "vision model"}),
        setting("global:0x0009", [[0, "Zqx Unproved"]], {"0": one, "1": one}),     # no line; code 1 no name at all
        # a second record Zqx On's line wrote, named for a row no hosted reader is sent: its frame goes to none
        setting("global:0x000a", [[1, "Zqx Wi-Fi Direct"]], {"1": "two readers"}),
        setting("global:0x000b", [[0, "S"], [1, "L"]], {"0": one, "1": one}),      # the axis's values alone
    ]}
    definition = tmp_path / "definition" / f"{CAMERA}.json"
    definition.parent.mkdir()
    definition.write_text(json.dumps(doc), encoding="utf-8")
    return root, definition


# what each reader reads on each frame (by its run and file name), for the list's question and the checklist's
SAID = {
    ("kit2_pass2", "00001.png"): {"qa": "Zqx Alpha", "qb": "Zqx Delta", "gm": "Zqx Alpha"},   # qb: qa's family, unheard
    ("kit2_pass2", "00002.png"): {"qa": "Zqx Beta", "gm": "Zqx Gamma"},                      # some agree
    ("kit2_pass2", "00003.png"): {"qa": "Zqx Delta", "gm": "Zqx Delta"},                     # all on another reading
    ("kit2_pass2", "00004.png"): {"qa": "Zqx Alpha", "gm": "Zqx Beta"},                      # apart
    ("kit2_pass2", "00006.png"): {"qa": "Zqx On", "gm": "Zqx On"},
    ("kit2_zqx_local", "00001.png"): {"qa": "Zqx Near"},
    ("kit2_net_zqx", "00001.png"): {"qa": "Zqx Wide"},
    ("kit2_pass2", "00010.png"): {"qa": "Zqx Spot: L"},
    ("kit2_pass2", "00012.png"): {"qa": "Zqx Spot: S"},
}
BOXES = {"qa": True, "qb": True, "gm": False}          # each reader's tick for Zqx Two


class FakeReader:
    """A reader faked by its configured name: its answer by the frame and the question (SAID, BOXES); every question
    put to it noted in `asked` as (reader, run, frame, question)."""

    def __init__(self, cfg: dict, frames: dict, asked: list):
        self.name, self.model, self.frames, self.asked = cfg["name"], cfg["model"], frames, asked

    def answer(self, image: bytes, prompt: str, waits=None):
        where = self.frames[image]
        self.asked.append((self.name, *where, prompt))
        if prompt == CHECKLIST:
            return {"boxes": [{"label": "Zqx One", "ticked": False},
                              {"label": "Zqx Two", "ticked": BOXES.get(self.name, True)}]}
        said = SAID.get(where, {})
        return {"selected": said.get(self.name, said.get("qa", "none"))}       # a reader not listed reads as qa


def readers(monkeypatch, root: Path, asked: list, far: bool = False) -> None:
    listed = [{"name": "qa", "url": LOCAL, "model": QWEN_A, "parallel": 2},
              {"name": "qb", "url": LOCAL, "model": QWEN_B},
              {"name": "gm", "url": LOCAL, "model": GEMMA}]
    third = ["qb", "gm"]
    if far:
        listed.append({"name": "far", "url": FAR, "model": "far-9"})
        third.append("far")
    frames = {p.read_bytes(): (p.parent.parent.name, p.name) for p in root.glob("*/shots/*.png")}
    monkeypatch.setattr(vlm, "config", lambda: {"readers": listed, "roles": {"second": "qa", "third": third}})
    monkeypatch.setattr(vlm, "CACHE", None)
    monkeypatch.setattr(vlm, "make_reader", lambda cfg, **kw: FakeReader(cfg, frames, asked))


def files_of(top: Path) -> dict:
    return {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in top.rglob("*")}


def run_audit(args: list, capsys) -> tuple:
    import label_audit
    assert label_audit.main(args) == 0
    said = capsys.readouterr()
    return said, (json.loads(said.out) if "--json" in args else None)


def test_the_scope_is_the_sources_and_kinds_asked_for_or_every_name(own_runs, tmp_path, monkeypatch, capsys):
    root, definition = camera(own_runs, tmp_path)
    asked = []
    readers(monkeypatch, root, asked)
    base = ["--json", "--dry-run", "--definition", str(definition), "--cache", str(tmp_path / "answers")]
    _, got = run_audit(base, capsys)
    # one reader and the vision model: four list names, the identity row's, the lost frame's, three proof runs', the
    # unproved setting's two and the axis's two; the checklist's two by their kind
    assert got["by source"] == {"one reader": 11, "vision model": 2, "schema kept": 2} and got["in scope"] == 15
    assert got["by kind"] == {"list": 9, "no proof line": 2, "checklist": 2, "axis": 2}
    assert got["left out"] == {"the report credits no label with it": 1, "the definition lists no name for it": 1,
                               "an identity or connection row (decision 8)": 1, "frame not on disk": 1,
                               "a run no reader reads (decision 9)": 1}
    assert asked == [] and got["dry run"] is True
    a = got["asked"]
    # the four list frames, the checklist's one frame for its two names, the local-only and the network-named runs',
    # the axis's two (Zqx Spot: S on its context row's visit, never its own row's put-back)
    assert a["qa"] == {"would ask": 9, "seconds": a["qa"]["seconds"], "questions": 9}
    _, got = run_audit([*base, "--sources", "two readers", "--kinds", ""], capsys)
    assert got["by source"] == {"two readers": 3} and got["left out"] == {"a black frame": 1}
    _, got = run_audit([*base, "--kinds", "checklist", "--sources", ""], capsys)
    assert got["by kind"] == {"checklist": 2} and got["asked"]["qa"]["questions"] == 1
    _, got = run_audit([*base, "--all"], capsys)
    assert got["in scope"] == got["names"] == 18
    with pytest.raises(SystemExit):
        run_audit([*base, "--sources", "no such source"], capsys)
    with pytest.raises(SystemExit):
        run_audit([*base, "--kinds", "no such kind"], capsys)


def test_four_verdicts_one_vote_per_family_and_the_ledger_first_on_another_reading(own_runs, tmp_path, monkeypatch,
                                                                                  capsys):
    import label_audit
    root, definition = camera(own_runs, tmp_path)
    asked = []
    readers(monkeypatch, root, asked)
    before = files_of(root)
    said, got = run_audit(["--json", "--definition", str(definition), "--cache", str(tmp_path / "answers")], capsys)
    assert got["families"] == {"qa": "qwen9-27b", "qb": "qwen9-27b", "gm": "gemma-9-12b"}
    v = got["verdicts by source"]
    # Alpha: qa and gm right, qb (qa's model in another build) wrong but no vote of its own; Beta: some; Gamma (the
    # vision model's): both families on Delta; Delta: apart; the local-only and network-named runs' frames and the
    # axis's values, read on its whole line, all agree
    assert v["one reader"] == {"all agree": 4, "some agree": 1, "none agree, apart": 1}
    assert got["verdicts by kind"]["axis"] == {"all agree": 2}
    assert v["vision model"] == {"none agree, all on another reading": 1, "all agree": 1}
    # gm reads Zqx Two unticked where the visit ticked it: both its names, Ticked and Not ticked, some agree
    assert v["schema kept"] == {"some agree": 2}
    assert got["names by families that answered"] == {"2": 10}
    ledger = root / label_audit.LEDGER
    lines = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines()]
    assert [d["verdict"] for d in lines] == ["none agree, all on another reading", "none agree, apart", "some agree",
                                             "some agree", "some agree"]
    first = lines[0]
    assert first["key"] == "global:0x0001" and first["value"] == "2" and first["name"] == "Zqx Gamma"
    assert first["source"] == "vision model" and first["kind"] == "list" and first["row"] == "Zqx Mode"
    assert first["frame"] == "kit2_pass2/shots/00003.png" and first["families"] == 2
    assert [(r["reader"], r["reading"], r["verdict"]) for r in first["readers"]] == [
        ("qa", "Zqx Delta", "another option"), ("qb", "Zqx Delta", "another option"),
        ("gm", "Zqx Delta", "another option")]
    # the runs are only read: the ledger alone is new
    assert set(files_of(root)) - set(before) == {ledger.parent, ledger}
    assert all(files_of(root)[p] == before[p] for p in before)
    for out in (said.out, said.err):
        for word in ("Zqx", ".png", "00003", "Ticked", "Delta"):
            assert word not in out, word


def judge_name(kind, name, recorded, options, readings, fixes=None):
    """(each family's vote, the name's verdict) for a published name whose proof recorded `recorded` among the row's
    recorded `options` (fixes: on the name's record, {recorded label: {(value, published name)}})."""
    import label_audit as la
    import reader_census as rc
    n = la.Name("global:0x0001", "1", name, "one reader")
    n.kind, n.line = kind, {"label": recorded}
    n.item, why = la.judged(n, rc.Item(kind, Path("f.png"), recorded, options, extra={"expect": "label"}), fixes or {})
    assert why is None, why
    votes = {fam: la.reading_of(n, {"selected": text}) for fam, text in readings.items()}
    return [v for v, _, _ in votes.values()], la.verdict_of(votes)


def test_a_name_is_right_only_where_the_reading_spells_it_as_published():
    """The audit asks whether the name is spelled as drawn, not only whether a reader picks its option: a published
    name OCR garbled (a letter lost or changed, an icon's letter glued in front, a word left out) read exactly by every
    family is never "all agree", and goes first in the list."""
    two = {"qwen": None, "gemma": None}
    for name, drawn, others in (("Zqx Fixed SBY", "Zqx Fixed STBY", ["Zqx Fixed REC", "Zqx Var"]),
                                ("EZqx Frame Display", "Zqx Frame Display", ["Zqx Peaking", "Zqx Grid Line"]),
                                ("Shorest", "Shortest", ["Short", "Long"]),
                                ("8fs", "8fps", ["30fps", "60fps"]),
                                ("Record Setting", "S&Q Record Setting", ["Movie Zqx", "Time-lapse Zqx"])):
        votes, verdict = judge_name("list", name, name, [name, *others], dict.fromkeys(two, drawn))
        assert votes == ["spelled otherwise"] * 2 and verdict == "none agree, all on another reading", name
        # spelled alike but for case, spacing and a stop: right
        assert judge_name("list", drawn, drawn, [drawn, *others], dict.fromkeys(two, drawn.upper() + "."))[1] == \
            "all agree", drawn
    # each picks the option, spelled apart: a verdict of its own
    votes, verdict = judge_name("list", "Zqx Fixed SBY", "Zqx Fixed SBY", ["Zqx Fixed SBY", "Zqx Fixed REC", "Zqx Var"],
                                {"qwen": "Zqx Fixed STBY", "gemma": "Zqx Fixed SBYY"})
    assert votes == ["spelled otherwise"] * 2 and verdict == "picks the option, spelled otherwise"
    # a part of the line: the reading's part in the name's place, or the name alone held in it
    fixes = {"Zqx Mode: Hi": {("1", "Hi")}, "Zqx Mode: Hi+": {("2", "Hi+")}, "Zqx Mode: Lo": {("0", "Lo")}}
    opts = ["Zqx Mode: Hi", "Zqx Mode: Hi+", "Zqx Mode: Lo"]
    assert judge_name("axis", "Hi", "Zqx Mode: Hi", opts, dict.fromkeys(two, "Zqx Mode: Hi"), fixes)[1] == "all agree"
    assert judge_name("axis", "Hi", "Zqx Mode: Hi", opts, dict.fromkeys(two, "Zqx Mode: Hi+"), fixes) == \
        (["another option"] * 2, "none agree, all on another reading")
    # a look's base is its code, drawn before its long name; the code is compared character by character
    looks = ["PT", "NT", "P7"]
    assert judge_name("look base", "PT", "PT", looks, dict.fromkeys(two, "PT(Portrait)"))[1] == "all agree"
    assert judge_name("look base", "PT", "PT", looks, dict.fromkeys(two, "NT (Neutral)")) == \
        (["another option"] * 2, "none agree, all on another reading")
    assert judge_name("look base", "PT", "PT", looks, dict.fromkeys(two, "P7(Portrait)"))[0] == ["another option"] * 2
    held = {"Zqx 50M L: 50M": {("1", "L: 50M")}, "Zqx 21M M: 21M": {("2", "M: 21M")}}
    assert judge_name("table picker", "L: 50M", "Zqx 50M L: 50M", list(held), dict.fromkeys(two, "Zqx 50M L: 50M"),
                      held)[1] == "all agree"


def test_all_agree_needs_two_families():
    import label_audit as la
    right, wrong = ("right", "Zqx", None), ("another option", "Zqy", ("option", 0))
    assert la.verdict_of({"qwen": right}) == "one family, spelled as published"
    assert la.verdict_of({"qwen": wrong}) == "one family, not as published"
    assert la.verdict_of({"qwen": right, "gemma": right}) == "all agree"
    assert la.verdict_of({}) == "not read"
    assert "one family, not as published" in la.LISTED and la.VERDICTS.index("all agree") > len(la.LISTED)
    assert "all agree" not in la.LISTED and "one family, spelled as published" not in la.LISTED


def test_a_checklist_name_is_judged_by_the_state_its_box_shows():
    import label_audit as la
    import reader_census as rc
    # the report's own rule (pass2_report.TICKED, UNTICKED); a name neither says is left out
    said = {"Ticked": True, "Not ticked": False, "On": True, "Off": False, "Included in DISP cycle": True,
            "Not included": False, "Excluded": False, "Registered": True, "Not registered": False,
            "Allowed (ticked)": True, "None": None, "Unit": None, "Underwater": None, "Normal": None, "": None}
    assert {t: la.tick_state(t) for t in said} == said
    n = la.Name("k", 0, "Zqx Unit", "schema kept")
    n.kind, n.after, n.line = "checklist", True, {"label": "Zqx Two"}
    item = rc.Item("checklist", Path("f.png"), [("Zqx Two", True)], ["Zqx One", "Zqx Two"], extra={"label": "Zqx Two"})
    assert la.judged(n, item, {}) == (None, "a checklist name that says no tick state")
    # an answer whose boxes are no list (a string naming the box) says no state: no answer, never right
    n.name = "Not ticked"
    n.item, _ = la.judged(n, item, {})
    assert la.reading_of(n, {"boxes": "Zqx Two"})[0] == "no answer"
    assert la.reading_of(n, {"boxes": [{"label": "Zqx Two", "ticked": True}]})[0] == "another option"
    n = la.Name("k", 0, "Not ticked", "schema kept")
    n.kind, n.after, n.line = "checklist", False, {"label": "Zqx Two"}
    item = rc.Item("checklist", Path("f.png"), [("Zqx Two", True)], ["Zqx One", "Zqx Two"], extra={"label": "Zqx Two"})
    it, why = la.judged(n, item, {})
    # the visit ticked the box; the value it left behind is "Not ticked": the frame must show the box ticked
    assert why is None and it.truth == [("Zqx Two", True)]
    assert rc.judge(it, [{"label": "Zqx Two", "ticked": True}]) == "right"
    n.name = "Ticked"
    n.after = True
    assert la.judged(n, item, {})[0].truth == [("Zqx Two", True)]


def test_two_values_one_name_and_several_readings_of_one_option():
    import label_audit as la
    import reader_census as rc
    n = la.Name("k", 1, "Zqx Beta", "one reader")
    n.kind, n.line = "table picker", {"label": "• Zqx Beta"}
    item = rc.Item("table picker", Path("f.png"), "Zqx Beta", ["Zqx Alpha", "Zqx Beta", "Zqx Bta"],
                   extra={"expect": "label"})
    fixes = {"Zqx Alpha": {("0", "Zqx Alpha")}, "Zqx Beta": {("1", "Zqx Beta")}, "Zqx Bta": {("1", "Zqx Beta")}}
    it, why = la.judged(n, item, fixes)
    assert why is None and it.truth == "Zqx Beta" and it.options == ["Zqx Alpha", "Zqx Beta"]
    fixes["Zqx Bta"] = {("2", "Zqx Beta")}                 # another value under the same name: no reading tells them
    assert la.judged(n, item, fixes) == (None, "two values of its record share the name")


def test_a_name_published_as_part_of_the_line_drawn_is_named_by_a_reading_that_holds_it():
    """A carousel axis's value the definition names alone ("Hi" of "Zqx Bracket: Hi"): a reading of the whole line
    names it where it holds that option's name alone, never where it holds none or two alike."""
    import label_audit as la
    import reader_census as rc
    n = la.Name("k", 1, "Hi", "one reader")
    n.kind, n.line = "axis", {"label": "Zqx Bracket: Hi"}
    item = rc.Item("axis", Path("f.png"), "Zqx Bracket: Hi", ["Zqx Bracket: Lo", "Zqx Bracket: Hi"],
                   extra={"expect": "label"})
    n.item, why = la.judged(n, item, {"Zqx Bracket: Lo": {("0", "Lo")}, "Zqx Bracket: Hi": {("1", "Hi")}})
    assert why is None and n.part and n.item.options == ["Lo", "Hi"]
    assert la.reading_of(n, {"selected": "Zqx Bracket: Hi"})[0] == "right"
    assert la.reading_of(n, {"selected": "Zqx Bracket: Lo"}) == ("another option", "Zqx Bracket: Lo", ("option", 0))
    assert la.reading_of(n, {"selected": "Zqx Bracket"})[0] == "no option"
    assert la.within("Zqx Hi Lo", ["Lo", "Hi"]) is None and la.held("Hi", "Zqx Bracket: Hi") == 2


def test_the_line_behind_a_name_and_the_options_by_their_names_in_every_row(tmp_path):
    """Of the lines the report credits with a value, one with its frame on disk that is no carousel's put-back visit
    comes first, whatever row; each recorded label takes the name the report credits it with on the record in any row;
    a name with no line says whether the report credits it at all."""
    import label_audit as la
    root = tmp_path / CAMERA
    for f in ("p.png", "v.png", "lo.png"):
        frame(root / runs.MAIN_RUN / "shots" / f, 70)
    key = "global:0x0001"
    final = {"kind": "axis", "label": "Zqx B: Hi", "final": True, "chosen_frame": "p.png"}
    visit = {"kind": "axis", "label": "Zqx B: Hi", "chosen_frame": "v.png"}
    gone = {"kind": "axis", "label": "Zqx B: Hi", "chosen_frame": "gone.png"}
    lo = {"kind": "axis", "label": "Zqx B: Lo", "chosen_frame": "lo.png"}
    report = [{"row": "A", "records": {key: record({"Zqx B: Hi": 1}, "two readers")}},
              {"row": "B", "records": {key: record({"Zqx B: Hi": 1, "Zqx B: Mid": 2}, "carousel")}},
              {"row": "C", "records": {key: record({"Zqx B: Hi": 1, "Zqx B: Lo": 0}, "carousel")}}]
    lines = {"A": {"Zqx B: Hi": [(final, None)]}, "B": {"Zqx B: Hi": [(gone, None)]},
             "C": {"Zqx B: Hi": [(visit, None)], "Zqx B: Lo": [(lo, None)]}}
    names = [la.Name(key, v, name, "one reader") for v, name in ((1, "Hi"), (0, "Lo"), (2, "Mid"), (3, "Max"))]
    on_key = la.find_lines(names, root, report, lines)
    hi, low, mid, top = names
    # the put-back (with a source the definition's) and the visit with no frame on disk lose to row C's visit
    assert hi.line is visit and hi.row == "C" and low.line is lo
    assert mid.why == "a report label with no proof line under it" and top.why == "the report credits no label with it"
    assert on_key[key] == {"Zqx B: Hi": {("1", "Hi")}, "Zqx B: Lo": {("0", "Lo")}}


def test_nothing_is_asked_twice_and_the_census_cache_is_used(own_runs, tmp_path, monkeypatch, capsys):
    root, definition = camera(own_runs, tmp_path)
    asked = []
    readers(monkeypatch, root, asked)
    census = tmp_path / "census"
    census.mkdir()
    image = (root / runs.MAIN_RUN / "shots" / "00001.png").read_bytes()
    (census / f"{vlm.cache_key(image, LIST, QWEN_A)}.json").write_text('{"selected": "Zqx Alpha"}', encoding="utf-8")
    args = ["--json", "--definition", str(definition), "--cache", str(tmp_path / "answers"), "--census-cache", str(census)]
    _, got = run_audit(args, capsys)
    # one question per reader and frame, the checklist's two names one question; qa's first answered by the census
    for who in ("qa", "qb", "gm"):
        mine = [a for a in asked if a[0] == who]
        assert len(mine) == len(set(mine)), who
    assert ("qa", "kit2_pass2", "00001.png", LIST) not in asked
    assert got["asked"]["qa"] == {"asked": 8, "from a cache": 1, "seconds": got["asked"]["qa"]["seconds"], "questions": 9}
    assert {a[3] for a in asked} == {LIST, CHECKLIST, AXIS}             # the kinds' new questions, never an old one
    assert vlm.PROMPTS["option"] not in {a[3] for a in asked}
    n = len(asked)
    _, again = run_audit(args, capsys)
    assert len(asked) == n and again["asked"]["gm"]["from a cache"] == 9
    assert again["verdicts by source"] == got["verdicts by source"]


def test_a_local_only_run_in_scope_asks_local_readers_only_and_builds_no_other(own_runs, tmp_path, monkeypatch,
                                                                               capsys):
    """Where a frame asked about is in a run folder a --network run marked, camkit.vlm.local_only_runs is told and a
    reader that is not local is neither built nor asked about any frame (decision 8, as the census); a run that opened
    a row an owner decision names is never read, nor its frame sent anywhere; an identity row's line is left out."""
    root, definition = camera(own_runs, tmp_path)
    asked, built = [], []
    readers(monkeypatch, root, asked, far=True)
    make = vlm.make_reader
    monkeypatch.setattr(vlm, "make_reader", lambda cfg, **kw: built.append(cfg["name"]) or make(cfg, **kw))
    said, got = run_audit(["--json", "--definition", str(definition), "--cache", str(tmp_path / "answers")], capsys)
    assert vlm.LOCAL_ONLY and "far" not in built and not [a for a in asked if a[0] == "far"]
    assert got["readers"] == ["qa", "qb", "gm"] and set(got["readers left out"]) == {"far"}
    assert "'far'" in said.err and "decision" in said.err
    assert ("kit2_zqx_local", "00001.png") in {(a[1], a[2]) for a in asked if a[0] == "qa"}
    assert not {a for a in asked if a[1] == "kit2_zqx_held" or a[2] in ("00007.png", "00008.png")}
    # the only reader left being hosted, nothing is asked
    monkeypatch.setattr(vlm, "config", lambda: {"readers": [{"name": "far", "url": FAR, "model": "far-9"}],
                                                "roles": {"second": "far"}})
    vlm.forget()
    with pytest.raises(SystemExit):
        run_audit(["--json", "--definition", str(definition), "--cache", str(tmp_path / "answers")], capsys)


def test_a_hosted_reader_is_sent_no_frame_refused_for_any_reading_it_holds(own_runs, tmp_path, monkeypatch, capsys):
    """With no local-only run in scope, a hosted reader is asked, but never about a frame reader_census.hosted_refused
    refuses for any name asked about it (Zqx On's frame also holds a name of a row no hosted reader is sent) nor one of
    a run named for a network look; with no OCR to judge a frame by, about none (fails closed, as the census)."""
    import reader_census
    root, definition = camera(own_runs, tmp_path)
    asked = []
    readers(monkeypatch, root, asked, far=True)
    monkeypatch.setattr(reading, "screen_texts", lambda frames: {f: "Zqx Menu Page" for f in frames})
    monkeypatch.setattr(reader_census, "screen_kind", lambda f: "list")
    args = ["--json", "--definition", str(definition), "--sources", "two readers,vision model", "--kinds", ""]
    _, got = run_audit([*args, "--cache", str(tmp_path / "answers")], capsys)
    assert not vlm.LOCAL_ONLY and "readers left out" not in got
    far = {(a[1], a[2]) for a in asked if a[0] == "far"}
    near = {(a[1], a[2]) for a in asked if a[0] == "qa"}
    assert near == {("kit2_pass2", "00003.png"), ("kit2_pass2", "00006.png"), ("kit2_net_zqx", "00001.png")}
    assert far == {("kit2_pass2", "00003.png")}
    def no_ocr(frames):
        raise OSError("no OCR")
    monkeypatch.setattr(reading, "screen_texts", no_ocr)
    asked.clear()
    _, got = run_audit([*args, "--cache", str(tmp_path / "other")], capsys)
    assert not [a for a in asked if a[0] == "far"] and got["asked"]["far"]["questions"] == 0


def test_the_list_keeps_what_a_run_did_not_read_and_a_run_that_read_nothing_writes_none(own_runs, tmp_path,
                                                                                       monkeypatch, capsys):
    import label_audit
    root, definition = camera(own_runs, tmp_path)
    readers(monkeypatch, root, [])
    base = ["--json", "--definition", str(definition)]
    run_audit([*base, "--cache", str(tmp_path / "a1")], capsys)
    ledger = root / label_audit.LEDGER
    first = ledger.read_bytes()
    assert len(first.splitlines()) == 5
    # nothing answered (no answer kept, no time to ask): the list as it was
    _, got = run_audit([*base, "--cache", str(tmp_path / "a2"), "--minutes", "0"], capsys)
    assert ledger.read_bytes() == first and "listed" not in got
    # the checklist alone, now every family confirming it: its two lines go, the three others stay
    monkeypatch.setitem(BOXES, "gm", True)
    _, got = run_audit([*base, "--cache", str(tmp_path / "a3"), "--kinds", "checklist", "--sources", ""], capsys)
    lines = [json.loads(x) for x in ledger.read_text(encoding="utf-8").splitlines()]
    assert got["listed"] == {"this run": 0, "kept from before": 3}
    assert [(d["key"], d["verdict"]) for d in lines] == [("global:0x0001", "none agree, all on another reading"),
                                                         ("global:0x0001", "none agree, apart"),
                                                         ("global:0x0001", "some agree")]
    # a line whose name the definition no longer publishes as it was goes too
    doc = json.loads(definition.read_text(encoding="utf-8"))
    doc["settings"][0]["values"][2][1] = "Zqx Gamma Two"
    definition.write_text(json.dumps(doc), encoding="utf-8")
    _, got = run_audit([*base, "--cache", str(tmp_path / "a3"), "--kinds", "checklist", "--sources", ""], capsys)
    assert got["listed"] == {"this run": 0, "kept from before": 2}


def test_a_hand_table_name_comes_in_by_its_source_only():
    import label_audit as la
    n = la.Name("k", 1, "Zqx Fn", "hand table")
    n.kind = "table picker"
    assert not la.in_scope(n, la.SOURCES, la.KINDS, False)
    assert la.in_scope(n, ["hand table"], la.KINDS, False) and la.in_scope(n, [], [], True)
    n.source = "two readers"
    assert la.in_scope(n, la.SOURCES, la.KINDS, False)


def test_the_private_file_is_under_the_run_root_owner_only_ignored_and_refused(own_runs, tmp_path, monkeypatch,
                                                                              capsys):
    import check_public
    import label_audit
    root, definition = camera(own_runs, tmp_path)
    readers(monkeypatch, root, [])
    said, _ = run_audit(["--definition", str(definition), "--cache", str(tmp_path / "answers")], capsys)
    assert "some agree" in said.out and "_label_audit" in said.out
    for word in ("Zqx", ".png", "00003", "Ticked", "Delta"):
        assert word not in said.out and word not in said.err, word
    ledger = root / label_audit.LEDGER
    assert ledger.is_file() and ledger.parent.parent == root
    if os.name == "posix":
        assert ledger.stat().st_mode & 0o777 == runs.PRIVATE_FILE
        assert ledger.parent.stat().st_mode & 0o777 == runs.PRIVATE_DIR
    rel = f"runs/{CAMERA}/{label_audit.LEDGER.as_posix()}"
    assert check_public.never_published(rel) and check_public.path_problems([rel], [], published={})
    ignored = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "-q", "--no-index", rel], capture_output=True)
    assert ignored.returncode == 0                    # .gitignore covers it
    # a dry run asks nothing and writes nothing; the answers never go into the runs
    ledger.write_text("", encoding="utf-8")
    before = files_of(root)
    run_audit(["--dry-run", "--definition", str(definition), "--cache", str(tmp_path / "answers")], capsys)
    assert files_of(root) == before
    with pytest.raises(SystemExit):
        run_audit(["--definition", str(definition), "--cache", str(root / "answers")], capsys)
