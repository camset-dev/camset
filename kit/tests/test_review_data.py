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
            "settings": [{"key": "global:0x0001", "area": "global", "id": 1, "name": "Alpha α", "tab": "Shooting",
                          "values": [[0, "Off"], [1, "On"]], "note": "", "proved": {"values": [0, 1]}},
                         {"key": "set:0x0002", "name": "Beta", "values": [[i, f"Step {i}"] for i in range(60)],
                          "scalar": True}],
            "menu": [{"tab": "Shooting", "group": "G", "label": "Alpha", "order": 1}],
            "camera": {"model": "ILCE-0X0", "display_name": "α0", "section_counts": [3, 2, 2],
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
    assert coverage.excluded_under(("Wi‑Fi  Frequency Band",), sony, header) == ("Wi-Fi Frequency Band",)
    assert coverage.excluded_under(("ntsc/pal selector",), sony, header) == ("NTSC/PAL Selector",)
    assert coverage.excluded_under(("Wi-Fi Connect",), sony, header) is None
