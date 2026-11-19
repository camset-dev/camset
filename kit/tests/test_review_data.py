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
