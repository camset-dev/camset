"""The engineering review of 2026-11-18, track 3 (data, the writer, the ledger): each finding fixed here has the test
that showed it. Made-up cameras and values; the a1 II's committed public files where a test reads the shipped ones."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import definitions  # noqa: E402


# ---------------------------------------------------------------- 1. the definition written one setting a line

def _made_up() -> dict:
    return {"$schema": definitions.SCHEMA_REF, "definition_format": definitions.FORMAT, "model": "ILCE-0X0",
            "tabs": ["Shooting", "Setup"],
            "layouts": [{"signature": "0123456789abcdef", "model": "ILCE-0X0", "firmware": "1.00",
                         "note": "ILCE-0X0 firmware 1.00", "doc": "docs/models/ILCE-0X0_fw1.00.md"}],
            "settings": [{"key": "global:0x0001", "area": "global", "id": 1, "name": "Alpha \u03b1", "tab": "Shooting",
                          "values": [[0, "Off"], [1, "On"]], "note": "", "proved": {"values": [0, 1]}},
                         {"key": "set:0x0002", "name": "Beta", "values": [[i, f"Step {i}"] for i in range(60)],
                          "scalar": True}],
            "menu": [{"tab": "Shooting", "group": "G", "label": "Alpha", "order": 1}],
            "camera": {"model": "ILCE-0X0", "display_name": "\u03b10", "section_counts": [3, 2, 2],
                       "text": {f"k{i}": "a sentence long enough to need a line of its own" for i in range(4)},
                       "sample": "ILCE-0X0_fw1.00.DAT"}}


def test_the_public_file_is_one_setting_a_line_and_the_same_json():
    """Review step 1 (2026-11-18): the definition was written with one scalar a line (3.4 MB for the a1 II). It is now
    one setting a line, the head readable: the same JSON, key order included, ASCII, and a fixed point."""
    doc = _made_up()
    text = definitions.public_text(doc)
    back = json.loads(text)
    assert back == doc and json.dumps(back) == json.dumps(doc), "the same JSON, key order included"
    assert text.isascii() and text.endswith("}\n") and definitions.public_text(back) == text
    lines = text.split("\n")
    for s in doc["settings"]:
        line = next(x for x in lines if x.startswith(f'  {{"key":"{s["key"]}"'))
        assert json.loads(line.rstrip(",")) == s, "each setting whole on its one line"
    assert ' "tabs": ["Shooting", "Setup"],' in lines, "a short head value on one line"
    assert ' "camera": {' in lines and '  "section_counts": [3, 2, 2],' in lines, "a long one a key a line"
    assert all(len(x) <= definitions.HEAD_WIDTH for x in lines if not x.startswith('  {"key"'))
    assert definitions.text(doc) == text


def test_a_write_writes_the_public_file_as_public_text_and_its_marker_agrees(tmp_path):
    """write() writes the public file as public_text gives it (and text() says so), the evidence file apart with its
    one-space indent; the marker's sha256 (finish_write's check) is the public file's."""
    doc = _made_up()
    doc["settings"][0]["proved"] = {"values": [0, 1], "run": "kit2_x", "names": {"0": "two readers"}}
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    ev = definitions.write(p, doc)
    assert p.read_text(encoding="utf-8") == definitions.text(doc) == definitions.public_text(definitions.split(doc)[0])
    assert ev.read_text(encoding="utf-8") == json.dumps(definitions.split(doc)[1], indent=1)
    assert definitions.load(p) == doc


def test_every_committed_definition_is_written_one_setting_a_line():
    """The shipped definitions are as the writer writes them now (re-dumped 2026-11-18, nothing edited by hand)."""
    found = sorted(definitions.DIR.glob("*.json"))
    assert found
    for p in found:
        text = p.read_text(encoding="utf-8")
        doc = json.loads(text)
        assert definitions.public_text(doc) == text, p.name
        assert text.count("\n") < len(doc["settings"]) + 1500, p.name


# ---------------------------------------------------------------- 2. the ledger's label folds memoised for one build

from camkit import coverage, safety  # noqa: E402
from test_coverage import CAM, RECORDS  # noqa: E402
from test_coverage import camera  # noqa: E402, F401  (the made-up camera's fixture)


def test_a_build_folds_each_label_once_and_builds_the_same_ledger(camera, monkeypatch):  # noqa: F811 (the fixture)
    """Review B5 (2026-11-18): the ledger build spent most of its time folding the same labels again (996,805 calls of
    safety.plain on 1,641 strings for the a1 II). A build now memoises its folds and comparisons (coverage._memo) for
    its own length: each distinct label is folded once, the memo is gone after the build, and the ledger (both forms)
    is the one a build without the memo gives."""
    seen = []
    fold = safety.plain

    def counted(text):
        if sys._getframe(1).f_code.co_name in ("_memo", "plain"):          # the ledger's own folds, not the guards'
            seen.append(text)
        return fold(text)
    monkeypatch.setattr(safety, "plain", counted)

    def forms(led):
        return coverage.text(coverage.private_doc(led)), coverage.text(coverage.public_doc(led))
    led = coverage.build(CAM, src=coverage.load_sources(CAM, records=RECORDS), validity=True)
    assert coverage._MEMO is None, "the memo lasts one build"
    assert len(seen) == len(set(seen)) > 10, "each label folded once in a build"
    memoised = forms(led)
    def _memo(fn, *args):                                                       # no memo: the code as before
        return fn(*args)
    monkeypatch.setattr(coverage, "_memo", _memo)
    seen.clear()
    plain = coverage.build(CAM, src=coverage.load_sources(CAM, records=RECORDS), validity=True)
    assert len(seen) > len(set(seen)) and forms(plain) == memoised


# ---------------------------------------------------------------- 3. a closing proof changes nothing (finding 12, B9)

def test_a_block_cut_short_ends_on_no_closing_proof():
    """Review finding 12, the ledger's side (B9, 2026-11-18): _closing_proofs took the last line of each run of number
    field lines on one row and field for that field's closing proof, and the last line of each attempt for its own,
    even where a failure cut the block short and the line changed records. A closing proof chooses the start value
    again and changes nothing (the camera's volatile records aside): only such a last line is one. Shaped on the real
    case of 2026-11-18 (made-up names and codes): a whole block of four whose last line changes nothing; a block cut
    short after two samples; a block whose closing line failed with a leftover change; two attempts."""
    from types import SimpleNamespace

    def line(k, t, rec=None, applied=True, attempt=None, kind="fields"):
        return {"path": ["Tango"], "kind": kind, "index": [k, t] if kind == "fields" else t, "label": f"T {t}",
                "applied": applied, "changes": [{"key": rec, "before": 1, "after": 2}] if rec else [],
                **({"attempt": attempt} if attempt else {})}
    lines = [line(0, 0, "global:0x0b01"), line(0, 17, "global:0x0b01"), line(0, 33, "global:0x0b01"),
             line(0, 1),                                                         # 4: the whole block's closing line
             line(1, 0, "global:0x0b03"), line(1, 17, "global:0x0b03", applied=None),       # 6: cut short
             line(0, 17, "global:0x0b01"), line(0, 1, "global:0x0b03", applied=None),       # 8: closing line failed
             line(0, 1, "global:0x01ff"),                                        # 9: its only change volatile
             line(None, 2, "global:0x0c00", attempt="A", kind="list"),
             line(None, 1, "global:0x0c00", attempt="A", kind="list"),           # 11: attempt A cut short
             line(None, 2, "global:0x0c02", attempt="B", kind="list"),
             line(None, 0, attempt="B", kind="list")]                            # 13: attempt B's closing line
    src = SimpleNamespace(proofs=[("kit2_pass2", i + 1, p) for i, p in enumerate(lines)],
                          camera_file={"volatile_records": [0x01ff]})
    assert coverage._closing_proofs(src) == {("kit2_pass2", 4), ("kit2_pass2", 9), ("kit2_pass2", 13)}


# ---------------------------------------------------------------- 4. the writer's and the ledger's low ones

def test_importing_the_writer_reads_no_hand_tables():
    """Review B7 (2026-11-18): kit/schema_update.py read the ILCE-1M2's hand tables and its private hand evidence when
    it was imported, and the proof viewer imports it for its help helpers, whatever the camera. Now nothing is read on
    import; a name read from outside (or main's ILCE-1M2 pass) reads them."""
    import subprocess
    code = ("import sys; sys.path[:0] = ['kit', 'kit/tools']\n"
            "from writer import hand_tables\n"
            "read = []\n"
            "real = hand_tables.load\n"
            "hand_tables.load = lambda *a, **k: read.append(a) or real(*a, **k)\n"
            "import schema_update as S\n"
            "from schema_update import DISABLED_RE, LOOKALIKES, counted_proofs, help_rows, proved_rows\n"
            "assert read == [] and 'HAND' not in vars(S), read\n"
            "assert isinstance(S.FRAME_PROOFS, dict) and len(read) == 1 and S.HAND.FRAME_PROOFS is S.FRAME_PROOFS\n"
            "assert all(n in vars(S) and getattr(S, n) is getattr(S.HAND, n) for n in S.HAND_TABLES)\n"
            "S.UNPROVED, S.COPIES\n"
            "assert len(read) == 1\n")
    got = subprocess.run([sys.executable, "-c", code], cwd=definitions.ROOT, capture_output=True, text=True)
    assert got.returncode == 0, got.stderr[-2000:]


def test_a_second_a1_pass_in_one_process_starts_from_the_tables_as_read(tmp_path, monkeypatch, capsys):
    """Review B7: main wrote into the module's tables (NEW_RECORDS' bracket copies, FRAME_PROOFS' Base Look copies),
    so a second main() in one process started from changed tables. Two looks (no --write) on a made-up run leave every
    hand table as it was read."""
    import copy

    import schema_update as S
    from test_definitions import A1_PROOFS, A1_REPORT, a1_run
    S._hand()
    before = {n: copy.deepcopy(getattr(S, n)) for n in S.HAND_TABLES}
    S, _target, _write = a1_run(tmp_path, monkeypatch, A1_REPORT, A1_PROOFS)
    monkeypatch.setattr(sys, "argv", ["schema_update.py"])
    S.main()
    first = capsys.readouterr().out
    assert {n for n in S.HAND_TABLES if getattr(S, n) != before[n]} == set()
    S.main()
    assert capsys.readouterr().out == first and {n for n in S.HAND_TABLES if getattr(S, n) != before[n]} == set()


def test_the_dial_runs_newest_download_is_found_by_the_manifest_or_its_number(tmp_path, monkeypatch):
    """Review B8: the ILCE-1M2's pass took sorted(glob)[-1] of runs/<camera>/kit2_dial/dat: an IndexError without that
    run, and the names sorted as text ("93438_x.DAT" after "239606_x.DAT"), which the fix of 2026-11-11 took out
    elsewhere. Now the downloads manifest's last of the run, else the highest number, and plain words without one."""
    import pytest

    import schema_update as S
    root = tmp_path / "runs" / "ILCE-1M2_fw4.00"
    monkeypatch.setattr(S, "RUN_ROOT", root)
    with pytest.raises(SystemExit) as e:
        S.dial_download()
    assert "kit2_dial" in str(e.value.code) and "holds none" in str(e.value.code)
    dat = root / "kit2_dial" / "dat"
    dat.mkdir(parents=True)
    for name in ("93438_x.DAT", "239606_x.DAT", "_camlink_upload_x.DAT", "notes.txt"):
        (dat / name).write_bytes(b"")
    assert S.dial_download() == dat / "239606_x.DAT", "by number, never as text"
    (root / "downloads.jsonl").write_text(json.dumps({"path": "kit2_dial/dat/93438_x.DAT"}) + "\n" +
                                          json.dumps({"path": "kit2_other/dat/00001_x.DAT"}) + "\n", encoding="utf-8")
    assert S.dial_download() == dat / "93438_x.DAT", "the manifest's order, where it lists the run"


def test_the_save_load_rows_are_compared_folded():
    """Review B11: excluded_under compared the row's labels raw where every other ledger comparison folds them, so a
    label spelled with another dash or without the list's full stop missed silently. Folded now, giving the row as the
    list writes it (its note and the header flag are looked up by it)."""
    sony = {("FTP Transfer Func.",): "its own file", ("Wi-Fi Frequency Band",): ""}
    header = {("NTSC/PAL Selector",), ("FTP Transfer Func.",)}
    assert coverage.excluded_under(("FTP Transfer Func", "Upload Settings"), sony, header) == ("FTP Transfer Func.",)
    assert coverage.excluded_under(("Wi\u2011Fi  Frequency Band",), sony, header) == ("Wi-Fi Frequency Band",)
    assert coverage.excluded_under(("ntsc/pal selector",), sony, header) == ("NTSC/PAL Selector",)
    assert coverage.excluded_under(("Wi-Fi Connect",), sony, header) is None


# ---------------------------------------------------------------- 5. an option's own boxes in the order drawn

def _boxes_camera():
    """A made-up row whose option opens a row of boxes the walk never entered, its four boxes' settings listed in the
    definition before the first box's (as the a1 II's Zebra Level > Custom 1 and Custom 2 were)."""
    tree = {"model": "TEST", "firmware": "1.00", "tabs": [{"tab": "Shooting", "pages": [
        {"page": "1/1", "group": "Display", "rows": [
            {"label": "Tango Level", "options": ["70", "Custom 1", "Custom 2"], "children": []}]}]}]}

    def s(key, name, path, values=()):
        return {"key": key, "area": "global", "id": int(key[-4:], 16), "name": name, "tab": "Shooting",
                "group": "Display", "order": 1, "values": [list(v) for v in values],
                "proved": {"run": "kit2_pass2", "date": "2026-11-18", "menu": [path]}}
    settings = [s("global:0x0100", "Tango Level", "Tango Level", ((0, "70"), (8, "Custom 1"), (9, "Custom 2")))]
    for n, base in ((1, 0x0110), (2, 0x0120)):
        for i, box in enumerate(("Standard", "Range", "Lower Limit", "Type")):
            settings.append(s(f"global:0x{base + i:04x}", f"Tango Level > Custom {n} > {box}",
                              f"Tango Level > Custom {n} > {box} [Tango Level Custom {n}]"))
    doc = {"model": "TEST", "tabs": ["Shooting"], "layouts": [{"model": "TEST", "firmware": "1.00"}],
           "menu": [{"tab": "Shooting", "group": "Display", "label": "Tango Level", "order": 1}], "settings": settings}
    return doc, tree


def test_an_options_own_boxes_take_the_order_the_camera_draws_them_in():
    """Review 2026-11-18, item 5: an option of a list row that draws a row of boxes of its own (the a1 II's Zebra Level
    > Custom 1, Custom 2) had its boxes placed in the order its settings entered the definition, Type last; the camera
    draws Type first ("Type | Standard | Range", or "Type | Lower Limit"). The probe line of that option
    (optboxes_run.py --probe) gives the drawn order: placement takes it, generally (no row or camera named), the rows of
    boxes merged the longest first, a Cyrillic letter in a box name folded, and the order the probe met them in no
    matter."""
    from camkit import placement
    doc, tree = _boxes_camera()
    before = placement.settings(doc, tree)
    by = {s["key"]: s["name"].split(" > ")[-1] for s in doc["settings"]}
    order = [by[k] for k in sorted((k for k in before if "Custom 1" in before[k]["row"]), key=lambda k: before[k]["row_at"])]
    assert order == ["Standard", "Range", "Lower Limit", "Type"], "the definition's order, as before"
    probe = [{"row": "Tango Level", "option": "Custom 1", "t": 2.0,
              "types": {"Std+Range": ["Tyрe", "Standard", "Range"], "Lower Limit": ["Tyрe", "Lower Limit"]}},
             {"row": "Tango Level", "option": "Custom 2", "t": 1.0,
              "types": {"Lower Limit": ["Type", "Lower Limit"], "Std+Range": ["Type", "Standard", "Range"]}},
             {"row": "Tango Level", "option": "Custom 2", "t": 0.5, "types": {"x": ["Range", "Type"]}}]   # older
    boxes = placement.box_orders(probe)
    assert boxes == {("tangolevel", "custom1"): ["Type", "Standard", "Range", "Lower Limit"],
                     ("tangolevel", "custom2"): ["Type", "Standard", "Range", "Lower Limit"]}
    after = placement.settings(doc, tree, boxes)
    for n in (1, 2):
        got = {by[k]: after[k]["row_at"] for k in after if f"Custom {n}" in after[k]["row"]}
        assert got == {"Type": [0, n, 0], "Standard": [0, n, 1], "Range": [0, n, 2], "Lower Limit": [0, n, 3]}, n
    assert {k: v for k, v in after.items() if k not in by or "Custom" not in str(v["row"])} == \
        {k: v for k, v in before.items() if k not in by or "Custom" not in str(v["row"])}
    assert all(after[k]["row"] == before[k]["row"] for k in before)
    for s in doc["settings"]:                   # written so, then placed again where no probe is (a clone, the tests)
        s.update(after.get(s["key"], {}))
    assert placement.settings(doc, tree) == after, "a page placed from a probe once stays so"


def test_the_box_probes_file_is_the_provers_own():
    """fromdata reads the probes by the file name the option boxes prover writes them under."""
    import optboxes_run
    from writer import fromdata
    assert fromdata.BOX_PROBES == optboxes_run.PROBES


# ---------------------------------------------------------------- 6. one record, one row in a memory set

def test_a_live_setting_whose_record_a_sets_own_setting_describes_is_kept_out_of_the_sets(capsys):
    """Review 2026-11-18, item 6: global:0x0b8d (the exposure mode last registered) was marked kept in the memory sets
    (in_sets, carried from the first kit) while set:0x0b8d is the sets' own setting of that record, so a set showed two
    rows for one value. The registrations (2026-11-09) wrote the mode in use into the set and into the live record
    alike, whatever the live record held before: the set never takes the live value. Both passes keep such a live
    setting out of the sets (writer.proofs.without_set_twins), but one a registration was seen to copy, which is said;
    made-up settings."""
    from writer import proofs
    doc = {"settings": [
        {"key": "global:0x0100", "area": "global", "id": 0x100, "name": "Last registered", "in_sets": True, "scalar": True},
        {"key": "set:0x0100", "area": "set", "id": 0x100, "name": "Stored in the memory", "in_sets": True},
        {"key": "global:0x0101", "area": "global", "id": 0x101, "name": "Kept", "in_sets": True},
        {"key": "global:0x0102", "area": "global", "id": 0x102, "name": "Copied", "in_sets": True,
         "in_sets_proved": {"run": "r", "date": "d", "slot": "1"}},
        {"key": "set:0x0102", "area": "set", "id": 0x102, "name": "Also its own", "in_sets": True}]}
    assert proofs.without_set_twins(doc) == ["global:0x0100"]
    by = {s["key"]: s for s in doc["settings"]}
    assert by["global:0x0100"]["in_sets"] is False and list(by["global:0x0100"]) == ["key", "area", "id", "name",
                                                                                      "in_sets", "scalar"]
    assert by["global:0x0101"]["in_sets"] is True and by["global:0x0102"]["in_sets"] is True
    said = capsys.readouterr().out
    assert "global:0x0100" in said and "set:0x0100" in said and "described twice" in said
    assert proofs.without_set_twins(doc) == [], "again: nothing"


def test_the_a1_pass_keeps_0x0b8d_out_of_the_memory_sets(tmp_path, monkeypatch, capsys):
    """The ILCE-1M2's pass applies it: on a made-up run, the committed definition's global:0x0b8d is kept out of the
    sets (said where the committed definition still had it in them; written so since 2026-11-19), its sets' own
    setting set:0x0b8d as it is."""
    from test_definitions import A1_PROOFS, A1_REPORT, DOC, a1_run
    was_in = next(s for s in DOC["settings"] if s["key"] == "global:0x0b8d").get("in_sets")
    S, _target, _write = a1_run(tmp_path, monkeypatch, A1_REPORT, A1_PROOFS)
    got = []
    real = S.from_data
    monkeypatch.setattr(S, "from_data", lambda doc: got.append(real(doc)) or got[-1])
    monkeypatch.setattr(sys, "argv", ["schema_update.py"])
    S.main()
    assert ("global:0x0b8d" in capsys.readouterr().out) == bool(was_in)
    by = {s["key"]: s for s in got[-1]["settings"]}
    assert by["global:0x0b8d"]["in_sets"] is False and by["set:0x0b8d"]["in_sets"] is True


# ---------------------------------------------------------------- 7. one rebuild command

def _stand_ins(tmp_path, monkeypatch, changes=1, fail=None, cargo=True):
    """kit/rebuild.py with each step a stand-in (python -c) that logs its name and prints as the real one does: the
    write changes the evidence stand-in on its first `changes` runs; `fail` names a step that refuses; cargo there or
    not, the bless a stand-in that rewrites a golden menu stand-in. Returns (the module, the log, the golden menu)."""
    import rebuild
    tmp_path.mkdir(parents=True, exist_ok=True)
    log, count = tmp_path / "steps.txt", tmp_path / "writes.txt"
    defn, ev, reset, menu = (tmp_path / n for n in ("def.json", "ev.json", "reset.json", "menu.json"))
    for f in (defn, ev, menu):
        f.write_text("0", encoding="utf-8")

    def logged(name, body):
        return (f"import os, sys\nfrom pathlib import Path\n"
                f"open({str(log)!r}, 'a', encoding='utf-8').write({name!r} + '\\n')\n{body}")
    write = (f"c = Path({str(count)!r})\nn = int(c.read_text(encoding='utf-8')) + 1 if c.exists() else 1\n"
             f"c.write_text(str(n), encoding='utf-8')\n"
             f"if n <= {changes}:\n    Path({str(ev)!r}).write_text(str(n), encoding='utf-8')\n"
             "print('gate: 0 open questions in the report, every one accepted in x')\n"
             "print('wrote editor/definitions/TEST-CAM_fw9.99.json')")
    bodies = {"report": "print('12 rows proved, 30 options')",
              "look": "print('gate: 2 open questions in the report, every one accepted in x')",
              "write": write, "docs": "print('wrote docs/formats/sony_camset_ids_TEST-CAM_fw9.99.ksy')",
              "leads": "print('written: private/evidence/TEST-CAM_fw9.99/leads_TEST-CAM_fw9.99.json')",
              "coverage": "print('written: data/TEST-CAM_fw9.99/coverage_TEST-CAM_fw9.99.json')"}
    if fail:
        bodies[fail] = "print('nothing written: a made-up refusal, in the step own words'); sys.exit(3)"
    monkeypatch.setattr(rebuild, "argv", lambda step, cam: [sys.executable, "-c", logged(step, bodies[step])])
    monkeypatch.setattr(rebuild, "settled_files", lambda cam: [defn, ev, reset])
    monkeypatch.setattr(rebuild, "golden", lambda cam: menu)
    monkeypatch.setattr(rebuild, "BLESS", [sys.executable, "-c", logged(
        "bless", f"assert os.environ['CAMSET_BLESS'] == '1' and Path.cwd().name == 'editor'\n"
                 f"Path({str(menu)!r}).write_text('blessed', encoding='utf-8')")])
    monkeypatch.setattr(rebuild.shutil, "which", lambda name: "/made/up/cargo" if cargo else None)
    return rebuild, log, menu


def _ran(log) -> list:
    return log.read_text(encoding="utf-8").split() if log.exists() else []


def test_the_rebuild_is_a_look_by_default(tmp_path, monkeypatch, capsys):
    """Review 2026-11-18, item 7: kit/rebuild.py --camera X, without --write: the report and the writer as a look (its
    gate line), nothing else run and nothing written."""
    rebuild, log, menu = _stand_ins(tmp_path, monkeypatch)
    monkeypatch.setattr(sys, "argv", ["rebuild.py"])
    rebuild.main()
    out = capsys.readouterr().out
    assert _ran(log) == ["report", "look"] and "gate: 2 open questions" in out and "A look" in out
    assert "--write" in out and menu.read_text(encoding="utf-8") == "0"


def test_the_rebuild_writes_until_the_write_changes_nothing_then_builds_and_blesses(tmp_path, monkeypatch, capsys):
    """With --write: the report, the write again until it changes nothing (here the first two change the evidence, the
    third does not: three writes, said), the docs, the leads, the ledger and the golden menu's bless (CAMSET_BLESS=1,
    in editor/), then what was written, each file once."""
    rebuild, log, menu = _stand_ins(tmp_path, monkeypatch, changes=2)
    monkeypatch.setattr(sys, "argv", ["rebuild.py", "--write"])
    rebuild.main()
    out = capsys.readouterr().out
    assert _ran(log) == ["report", "write", "write", "write", "docs", "leads", "coverage", "bless"]
    assert "settled in 3 writes: write 3 changed nothing" in out and menu.read_text(encoding="utf-8") == "blessed"
    tail = out[out.index("written ("):]
    for f in ("editor/definitions/TEST-CAM_fw9.99.json", "docs/formats/sony_camset_ids_TEST-CAM_fw9.99.ksy",
              "private/evidence/TEST-CAM_fw9.99/leads_TEST-CAM_fw9.99.json",
              "data/TEST-CAM_fw9.99/coverage_TEST-CAM_fw9.99.json", str(menu), str(tmp_path / "ev.json")):
        assert tail.count(f) == 1, f
    assert str(tmp_path / "def.json") not in tail, "a file no write changed is not listed"


def test_one_write_that_changes_nothing_is_enough(tmp_path, monkeypatch, capsys):
    rebuild, log, _menu = _stand_ins(tmp_path, monkeypatch, changes=0)
    monkeypatch.setattr(sys, "argv", ["rebuild.py", "--write"])
    rebuild.main()
    assert _ran(log).count("write") == 1 and "settled in 1 write: the first changed nothing" in capsys.readouterr().out


def test_the_rebuild_stops_on_a_write_that_never_settles(tmp_path, monkeypatch, capsys):
    """A write that still changes the definition or its evidence at the third run stops the rebuild, in plain words,
    before the docs."""
    import pytest
    rebuild, log, _menu = _stand_ins(tmp_path, monkeypatch, changes=5)
    monkeypatch.setattr(sys, "argv", ["rebuild.py", "--write"])
    with pytest.raises(SystemExit) as e:
        rebuild.main()
    assert e.value.code == 1 and _ran(log) == ["report", "write", "write", "write"]
    assert "still changed at write 3" in capsys.readouterr().out


def test_the_rebuild_stops_at_the_first_step_that_refuses_in_its_own_words(tmp_path, monkeypatch, capsys):
    """A step that fails stops the rebuild with its exit status, its own words shown and quoted, the step named;
    nothing after it runs."""
    import pytest
    for fail, ran in (("report", ["report"]), ("write", ["report", "write"]),
                      ("leads", ["report", "write", "write", "docs", "leads"])):
        rebuild, log, menu = _stand_ins(tmp_path / fail, monkeypatch, fail=fail)
        monkeypatch.setattr(sys, "argv", ["rebuild.py", "--write"])
        with pytest.raises(SystemExit) as e:
            rebuild.main()
        out = capsys.readouterr().out
        assert e.value.code == 3 and _ran(log) == ran, fail
        assert "rebuild stopped at step" in out and "a made-up refusal, in the step own words" in out
        assert "nothing after it ran" in out and menu.read_text(encoding="utf-8") == "0"


def test_without_cargo_the_rebuild_says_the_bless_command(tmp_path, monkeypatch, capsys):
    rebuild, log, menu = _stand_ins(tmp_path, monkeypatch, cargo=False)
    monkeypatch.setattr(sys, "argv", ["rebuild.py", "--write"])
    rebuild.main()
    out = capsys.readouterr().out
    assert "bless" not in _ran(log) and rebuild.BLESS_SAID in out and "cargo is not on this computer" in out
    assert menu.read_text(encoding="utf-8") == "0"
    assert rebuild.BLESS_SAID == "cd editor && CAMSET_BLESS=1 cargo test --release the_default_menu_is_the_golden_one"
