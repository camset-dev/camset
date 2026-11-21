"""The guard on a row found by its lit letter alone (2026-11-21): a proof line made after find_row found its row through
proving.screens.lit_letter carries "row_by": "lit letter" (proving.base.ROW_BY, written by Tagged), and pass2_report
takes such a line's change to a record another row's proofs own as a conflict ("not one to one": shown by key, not
applied by the writer, an open question at the gate), never as the row's own setting. No other line has the field, so
the report and the write on today's proofs come out as before. The field stays in proofs.jsonl and the private
evidence: how a thing was proved (decision 16). Nothing talks to a camera."""
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "tests"))
from proving import base  # noqa: E402

K = "global:0x9001"


def test_tagged_marks_a_line_of_a_row_found_by_its_lit_letter(monkeypatch):
    monkeypatch.setattr(base, "ROW_BY", {"M": "lit letter"})
    f = io.StringIO()
    t = base.Tagged(f, None)
    t.write(json.dumps({"path": ["Picture Profile", "PP4", "Color Depth", "M"], "label": "-7"}) + "\n")
    t.write(json.dumps({"path": ["Picture Profile", "PP4", "Color Depth", "Y"], "label": "-7"}) + "\n")
    t.write(json.dumps({"path": ["Picture Profile", "PP4", "Color Depth", "M [Movie]"], "label": "-7"}) + "\n")
    t.write(json.dumps({"path": ["Menu", "M", "Below"], "label": "On"}) + "\n")      # through the row, not ending on it
    m, y, tail, through = [json.loads(x) for x in f.getvalue().splitlines()]
    assert m["row_by"] == "lit letter" and "row_by" not in y
    assert tail["row_by"] == through["row_by"] == "lit letter"


def test_with_no_row_found_so_every_line_is_written_as_before(monkeypatch):
    monkeypatch.setattr(base, "ROW_BY", {})
    line = json.dumps({"path": ["Drive Mode"], "label": "Single Shooting", "changes": []}) + "\n"
    f = io.StringIO()
    base.Tagged(f, None).write(line)
    assert f.getvalue() == line                                     # byte for byte
    f = io.StringIO()
    base.Tagged(f, "Movie mode").write(line)
    assert json.loads(f.getvalue()) == {**json.loads(line), "context": "Movie mode"}


def test_at_label_keeps_how_the_row_was_found(monkeypatch):
    from proving import screens
    monkeypatch.setattr(base, "ROW_BY", {})
    cam = SimpleNamespace(read=lambda: SimpleNamespace(kind="submenu"))
    monkeypatch.setattr(screens, "bar_text", lambda c: "")
    monkeypatch.setattr(screens, "lit_letter", lambda c, prev: "M")
    assert screens.at_label(cam, "submenu", "M", prev=object())
    assert base.ROW_BY == {"M": "lit letter"}
    monkeypatch.setattr(screens, "bar_text", lambda c: "M")           # found by OCR the next time: no mark
    assert screens.at_label(cam, "submenu", "M", prev=object())
    assert base.ROW_BY == {}


def lines(lit_m: bool):
    from test_definitions import proof
    y = [proof(lab, i, [(K, 0, v)], frame=10 + i, path=("Color Depth", "Y")) for i, (lab, v) in
         enumerate([("-7", 249), ("0", 0), ("+7", 7)])]
    m = [proof(lab, i, [(K, 0, v)], frame=20 + i, path=("Color Depth", "M")) for i, (lab, v) in
         enumerate([("-7", 249), ("+7", 7), ("-3", 253)])]
    if lit_m:
        for r in m:
            r["row_by"] = "lit letter"
    return y + m


def report_of(tmp_path, proofs):
    import test_definitions as D
    run = D.write_run(tmp_path, proofs)
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(run), "--no-schema"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return {e["row"]: e for e in json.loads((run / "report.json").read_text(encoding="utf-8"))}


def test_a_lit_letter_rows_move_of_another_rows_record_is_a_conflict(tmp_path, own_runs):
    rep = report_of(tmp_path / "a", lines(lit_m=True))
    m = rep["Color Depth > M"]["records"][K]
    assert m["verdict"] == "conflict"
    assert any(n["kind"] == "not one to one" and "lit letter" in n.get("why", "") for n in m["notes"])


def test_without_the_mark_the_report_is_as_before(tmp_path, own_runs):
    rep = report_of(tmp_path / "b", lines(lit_m=False))
    m = rep["Color Depth > M"]["records"].get(K)
    assert m is None or not any("lit letter" in n.get("why", "") for n in m.get("notes") or [])
