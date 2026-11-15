"""kit/tools/leads.py, off the camera: it mines a camera's own downloads (its run folders' dat/ files, made here from
the a1 II's scrubbed sample with camset.with_values, as the other tests make camera files) for the records no setting of
its definition covers, and classes each NEVER, BETWEEN, SPECIFIC, SEVERAL or ALONE by the steps (two downloads one after
the other in one run folder, by the leading number of their names) it changed in and the rows those steps name. It never
writes or prints a record's value, writes the private leads file only with --write (whole, owner-only), and the
coverage ledger then reads it unchanged (docs/decisions/0016, 0023)."""
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import camkit  # noqa: E402
from camkit import camset, coverage, definitions, paths  # noqa: E402

CAM = paths.A1II                    # the sample's own model and firmware: the tool reads that camera's files alone
SAMPLE = definitions.sample(definitions.load_public(CAM), definitions.path(CAM))
# records of the sample (1-byte live and set records, one 4-byte live record), none of them volatile
G_ALPHA, G_BRAVO, G_CHARLIE = 0x0050, 0x0051, 0x0053          # mapped: Alpha, Bravo, Charlie (copied into the sets)
U_NEVER, U_BETWEEN, U_SPECIFIC, U_SEVERAL, U_PROOF = 0x0052, 0x0068, 0x006a, 0x006c, 0x006e
U_ALONE = 0x0101                    # 4 bytes: holds the planted value
S_X = 0x0018                        # a memory-set record no setting covers
PLANTED = 123456789                 # a value recognisable anywhere it might leak


def key(rid, area="global"):
    return f"{area}:0x{rid:04x}"


def setting(rid, name, row, **kw):
    return {"key": key(rid), "area": "global", "id": rid, "name": name, "tab": "Shooting", "group": "G1", "order": 1,
            "row": row, "values": [[0, "Off"], [1, "On"]], "note": "", "in_sets": False, "scalar": True, "size": 1,
            "count": 1, "modes": "", **kw}


# six more mapped rows, for the broad steps (run3), and the records no setting covers that run3 moves
G_MORE = dict(zip(("Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India"), (0x0076, 0x0078, 0x00de, 0x00e1, 0x00e6,
                                                                          0x00e8), strict=True))
V_ONE, V_SEV, V_SPEC_BROAD, V_BROAD, V_P6, V_N3, V_B4 = 0x00ec, 0x00ef, 0x00f2, 0x00f4, 0x00f6, 0x00f7, 0x00f9

SETTINGS = [setting(G_ALPHA, "Alpha", ["Alpha"]), setting(G_BRAVO, "Bravo", ["Bravo"]),
            setting(G_CHARLIE, "Charlie", ["Charlie"], in_sets=True)] + \
    [setting(rid, name, [name]) for name, rid in G_MORE.items()]


def one_byte(v: int) -> bytes:
    return v.to_bytes(1, "little", signed=True)


def write(path: Path, base: bytes, changes: dict) -> bytes:
    """A camera file: `base` with `changes` ({(section, record id): raw}) and both checksums sealed."""
    data = camset.with_values(camset.parse(base), changes) if changes else base
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


@pytest.fixture
def cam(tmp_path, monkeypatch):
    """The a1 II's key with a definition of three settings in the test's own folder, and two run folders of downloads:

        run1  00001_a  the sample
              00002_b  Alpha, U_SPECIFIC, U_SEVERAL changed             (a display proof names it: no download of its own)
              00003_c  Bravo, U_SEVERAL changed
              0009_d   U_ALONE changed to PLANTED                       (no mapped record, no proof)
              00010_e  Alpha and U_PROOF changed                        (a proof names it: "Setup > Proved Row")
              00011_x  a file the reader rejects (its checksum broken)
        run2  00001_a  the sample with U_BETWEEN changed                (only between the run folders)
              00002_b  set 3's S_X and set 5's Charlie changed          (Charlie covers the sets' record: in_sets)
    """
    monkeypatch.setenv("CAMSET_CAMERA", CAM)
    monkeypatch.setattr(camkit, "CONFIG", tmp_path / "no_config.json")
    ddir = tmp_path / "definitions"
    ddir.mkdir()
    doc = {"$schema": definitions.SCHEMA_REF, "definition_format": 2, "model": "ILCE-1M2", "tabs": ["Shooting", "Setup"],
           "layouts": [{"signature": "0" * 16, "model": "ILCE-1M2", "firmware": "4.00"}], "settings": SETTINGS,
           "menu": [{"tab": "Shooting", "group": "G1", "label": n, "order": i}
                    for i, n in enumerate(("Alpha", "Bravo", "Charlie"))],
           "camera": {"model": "ILCE-1M2", "section_counts": [1415] + [1057] * 12, "tab_colors": {},
                      "sample": SAMPLE.name}}
    (ddir / f"{CAM}.json").write_text(json.dumps(doc), encoding="utf-8")
    shutil.copy(SAMPLE, ddir / SAMPLE.name)
    monkeypatch.setattr(definitions, "DIR", ddir)
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    root = paths.runs_top() / CAM
    base = SAMPLE.read_bytes()
    four = PLANTED.to_bytes(4, "little", signed=True)
    d1 = root / "run1" / "dat"
    a = write(d1 / "00001_a.DAT", base, {})
    b = write(d1 / "00002_b.DAT", a, {(0, G_ALPHA): one_byte(1), (0, U_SPECIFIC): one_byte(3),
                                      (0, U_SEVERAL): one_byte(1)})
    c = write(d1 / "00003_c.DAT", b, {(0, G_BRAVO): one_byte(1), (0, U_SEVERAL): one_byte(2)})
    d = write(d1 / "0009_d.DAT", c, {(0, U_ALONE): four})
    write(d1 / "00010_e.DAT", d, {(0, G_ALPHA): one_byte(2), (0, U_PROOF): one_byte(1)})
    broken = bytearray(base)
    broken[len(broken) // 2] ^= 0xFF                  # a record's byte changed, the checksum not worked out again
    (d1 / "00011_x.DAT").write_bytes(bytes(broken))
    (d1 / "notes.txt").write_text("not a settings file", encoding="utf-8")
    (d1.parent / "proofs.jsonl").write_text("".join(json.dumps(x) + "\n" for x in (
        {"path": ["Display Row"], "dat": "00002_b.DAT", "base": "00002_b.DAT"},
        {"path": ["Setup", "Proved Row"], "dat": "00010_e.DAT", "base": "00001_a.DAT"})), encoding="utf-8")
    d2 = root / "run2" / "dat"
    a2 = write(d2 / "00001_a.DAT", base, {(0, U_BETWEEN): one_byte(5)})
    write(d2 / "00002_b.DAT", a2, {(3, S_X): one_byte(1), (5, G_CHARLIE): one_byte(7)})
    (root / "_cache").mkdir()                          # a folder of the camera's that is no run
    return root


def tool():
    import leads
    return leads


def mined():
    return tool().mine(CAM)


def entries(doc):
    return {x["key"]: x for part in ("live", "sets") for x in doc[part]}


def run_main(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["leads.py", *args])
    tool().main()


# ---------------------------------------------------------------- the classes, the steps, the rows

def test_each_class_where_the_downloads_put_it(cam):
    doc = mined()
    got = entries(doc)
    assert got[key(U_NEVER)] == {"key": key(U_NEVER), "cls": "NEVER", "values": 1}
    assert got[key(U_BETWEEN)] == {"key": key(U_BETWEEN), "cls": "BETWEEN", "changes": 0, "values": 2}
    assert got[key(U_SPECIFIC)] == {"key": key(U_SPECIFIC), "cls": "SPECIFIC", "changes": 1, "values": 2,
                                    "rows": {"Alpha": 1}, "runs": 1}
    assert got[key(U_SEVERAL)] == {"key": key(U_SEVERAL), "cls": "SEVERAL", "changes": 2, "values": 3,
                                   "rows": {"Alpha": 1, "Bravo": 1}, "runs": 1}
    assert got[key(U_ALONE)] == {"key": key(U_ALONE), "cls": "ALONE", "changes": 1, "values": 2, "runs": 1}
    # the proof naming the step's later file gives the step its row, in place of the mapped records' (Alpha)
    assert got[key(U_PROOF)]["cls"] == "SPECIFIC" and got[key(U_PROOF)]["rows"] == {"Setup > Proved Row": 1}


def test_files_steps_and_a_file_not_read(cam):
    doc = mined()
    # run1: five files read, four steps, the broken one not read (and notes.txt no settings file); run2: two, one step
    assert (doc["files"], doc["steps"], doc["not_read"]) == (7, 5, 1)
    assert doc["camera"] == CAM and isinstance(doc["about"], str) and doc["about"]


def test_a_step_never_spans_two_run_folders(cam):
    got = entries(mined())
    # run1's last file and run2's first differ in U_BETWEEN and back in Alpha, U_SPECIFIC...: no step joins them
    assert got[key(U_BETWEEN)]["cls"] == "BETWEEN" and got[key(U_SPECIFIC)]["changes"] == 1
    assert got[key(U_PROOF)]["changes"] == 1


def test_the_downloads_go_by_their_leading_number(cam):
    """0009_d comes before 00010_e, as the camera made them, though "00010" sorts first as text: read as text, U_ALONE
    would change in the proved step (SPECIFIC) and U_PROOF twice."""
    got = entries(mined())
    assert got[key(U_ALONE)]["cls"] == "ALONE" and got[key(U_PROOF)]["changes"] == 1
    order = [p.name for p in tool().downloads(cam / "run1")]
    assert order == ["00001_a.DAT", "00002_b.DAT", "00003_c.DAT", "0009_d.DAT", "00010_e.DAT", "00011_x.DAT"]


def test_a_name_with_no_number_comes_after_the_numbered(tmp_path):
    d = tmp_path / "r" / "dat"
    d.mkdir(parents=True)
    for n in ("b.DAT", "2_x.DAT", "a.DAT", "10_y.DAT"):
        (d / n).write_bytes(b"")
    assert [p.name for p in tool().downloads(tmp_path / "r")] == ["2_x.DAT", "10_y.DAT", "a.DAT", "b.DAT"]


def test_mapped_records_are_never_listed_and_a_set_record_lands_in_sets(cam):
    doc = mined()
    keys = set(entries(doc))
    for rid in (G_ALPHA, G_BRAVO, G_CHARLIE):
        assert key(rid) not in keys
    assert key(G_CHARLIE, "set") not in keys                     # Charlie, copied into the sets, covers theirs
    sets = {x["key"]: x for x in doc["sets"]}
    assert sets[key(S_X, "set")]["cls"] == "SPECIFIC" and sets[key(S_X, "set")]["rows"] == {"Charlie": 1}
    assert all(x["key"].startswith("global:") for x in doc["live"])
    assert all(x["key"].startswith("set:") for x in doc["sets"])
    # every key one the ledger names (records_of), each list in key order, the volatile records left out
    universe = coverage.records_of(SAMPLE)
    assert keys <= set(universe)
    for part in ("live", "sets"):
        nums = [int(x["key"].split(":")[1], 16) for x in doc[part]]
        assert nums == sorted(nums)
    volatile = {key(rid) for _, rid in camset.volatile("ILCE-1M2")}
    assert volatile and not volatile & keys
    covered = coverage.records_covered(SETTINGS)
    assert keys == set(universe) - set(covered) - volatile


def test_the_shared_rule_is_the_ledgers():
    on = coverage.records_covered(SETTINGS[:3] + [{"key": "set3:0x0200"}, {"key": "global:0x0300@4"}])
    assert set(on) == {key(G_ALPHA), key(G_BRAVO), key(G_CHARLIE), key(G_CHARLIE, "set"), "set:0x0200",
                       "global:0x0300"}


def test_at_most_eight_rows_the_rest_counted():
    lead = tool().entry("global:0x0001", 2, {"changes": 12, "runs": {"r"},
                                              "rows": {f"Row {i:02d}": 12 - i for i in range(10)}})
    assert lead["cls"] == "SEVERAL" and len(lead["rows"]) == 8 and lead["other_rows"] == 2
    assert list(lead["rows"]) == [f"Row {i:02d}" for i in range(8)]


# ---------------------------------------------------------------- broad steps: a restore, a reset, a mode switch

W_BROAD = 0x010f                    # 4 bytes: holds the planted value, moved only in a broad step


def broad_run(cam):
    """run3, after the fixture's two:

        00001  the sample
        00002  Delta..Hotel (5 rows), V_SPEC_BROAD, V_BROAD, W_BROAD (PLANTED)   broad
        00003  Delta..India (6 rows), V_SPEC_BROAD, V_P6                        a proof names it: "Setup > Proof Row"
        00004  Delta, Echo, Foxtrot (3 rows), V_N3                              narrow
        00005  Delta..Golf (4 rows), V_B4                                       broad
        00006  Alpha, V_SEV, V_ONE
        00007  Bravo, V_SEV
        00008  Alpha, V_ONE
    """
    rows = [G_MORE[n] for n in ("Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India")]
    steps = [rows[:5] + [V_SPEC_BROAD, V_BROAD], rows + [V_SPEC_BROAD, V_P6], rows[:3] + [V_N3], rows[:4] + [V_B4],
             [G_ALPHA, V_SEV, V_ONE], [G_BRAVO, V_SEV], [G_ALPHA, V_ONE]]
    d = cam / "run3" / "dat"
    data = write(d / "00001_s.DAT", SAMPLE.read_bytes(), {})
    for i, rids in enumerate(steps):
        changes = {(0, rid): one_byte(60 + i) for rid in rids}
        if i == 0:
            changes[(0, W_BROAD)] = PLANTED.to_bytes(4, "little", signed=True)
        data = write(d / f"{i + 2:05d}_s.DAT", data, changes)
    (d.parent / "proofs.jsonl").write_text(json.dumps({"path": ["Setup", "Proof Row"], "dat": "00003_s.DAT",
                                                       "base": "00001_s.DAT"}) + "\n", encoding="utf-8")


def test_a_broad_step_gives_no_rows(cam):
    broad_run(cam)
    got = entries(mined())
    # one proof-named step and one 5-row step: SPECIFIC on the proof's row, the broad step counted apart
    assert got[key(V_SPEC_BROAD)] == {"key": key(V_SPEC_BROAD), "cls": "SPECIFIC", "changes": 2, "broad": 1,
                                      "values": 3, "rows": {"Setup > Proof Row": 1}, "runs": 1}
    # moved only in broad steps (5 rows, 4 rows): BROAD, no rows
    assert got[key(V_BROAD)] == {"key": key(V_BROAD), "cls": "BROAD", "changes": 1, "broad": 1, "values": 2,
                                 "runs": 1}
    assert got[key(V_B4)]["cls"] == "BROAD" and "rows" not in got[key(V_B4)] and got[key(W_BROAD)]["cls"] == "BROAD"


def test_three_rows_are_narrow_four_are_broad_and_a_proof_is_never_broad(cam):
    broad_run(cam)
    got = entries(mined())
    assert got[key(V_N3)]["cls"] == "SEVERAL" and "broad" not in got[key(V_N3)]           # 3 rows: narrow
    assert got[key(V_N3)]["rows"] == {"Delta": 1, "Echo": 1, "Foxtrot": 1}
    assert got[key(V_B4)]["broad"] == 1 and got[key(V_B4)]["changes"] == 1                # 4 rows: broad
    assert got[key(V_P6)]["cls"] == "SPECIFIC" and "broad" not in got[key(V_P6)]          # 6 rows, a proof names it
    assert got[key(V_P6)]["rows"] == {"Setup > Proof Row": 1}
    assert tool().BROAD_ROWS == 3


def test_several_needs_two_rows_across_narrow_steps(cam):
    broad_run(cam)
    got = entries(mined())
    assert got[key(V_SEV)]["cls"] == "SEVERAL" and got[key(V_SEV)]["rows"] == {"Alpha": 1, "Bravo": 1}
    assert got[key(V_ONE)]["cls"] == "SPECIFIC" and got[key(V_ONE)]["rows"] == {"Alpha": 2}   # one row, twice
    # a record that only ever moved in steps with no row and no breadth stays ALONE
    assert tool().entry("global:0x0001", 2, {"changes": 3, "broad": 0, "rows": {}, "runs": {"r"}})["cls"] == "ALONE"


def test_the_top_leads_go_specific_several_broad(cam, monkeypatch, capsys):
    broad_run(cam)
    run_main(monkeypatch, "--top", "40")
    out = capsys.readouterr().out
    assert "BETWEEN 1, SPECIFIC 5, SEVERAL 3, BROAD 3, ALONE 1" in out
    lines = leads_in(out)
    classes = [ln.split()[1] for ln in lines]
    assert classes == ["SPECIFIC"] * 6 + ["SEVERAL"] * 3 + ["BROAD"] * 3
    assert lines[0].split()[0] == key(V_ONE)                     # SPECIFIC by narrow steps: two
    assert lines[6].split()[0] == key(V_N3)                      # SEVERAL by its top row's share: 1 of 1
    spec_broad = next(ln for ln in lines if ln.startswith(key(V_SPEC_BROAD)))
    assert spec_broad == f"{key(V_SPEC_BROAD)}  SPECIFIC  2  Setup > Proof Row (1)  [broad 1]"
    assert f"{key(V_BROAD)}  BROAD  1  [broad 1]" in lines


# ---------------------------------------------------------------- never a value; written only with --write

def test_no_value_is_written_or_printed(cam, monkeypatch, capsys):
    broad_run(cam)                                               # the planted value moves in a broad step too
    run_main(monkeypatch, "--write", "--top", "40")
    out = capsys.readouterr().out
    text = coverage.leads_file(CAM).read_text(encoding="utf-8")
    for said in (text, out):
        for v in (str(PLANTED), f"{PLANTED:x}", f"{PLANTED:X}", str(PLANTED.to_bytes(4, "little"))):
            assert v not in said
    doc = json.loads(text)
    assert set(doc) == {"about", "camera", "files", "steps", "not_read", "live", "sets"}
    for x in doc["live"] + doc["sets"]:
        assert set(x) <= {"key", "cls", "changes", "broad", "values", "rows", "other_rows", "runs"}
        assert all(isinstance(x[f], int) for f in ("changes", "broad", "values", "other_rows", "runs") if f in x)
        assert all(isinstance(n, int) for n in (x.get("rows") or {}).values())
        if x["cls"] == "NEVER":
            assert set(x) == {"key", "cls", "values"}


def test_the_summary_and_the_top_leads(cam, monkeypatch, capsys):
    run_main(monkeypatch)
    out = capsys.readouterr().out
    assert "7 files read, 5 steps, 1 not read" in out
    live = next(ln for ln in out.splitlines() if ln.startswith("live records"))
    sets = next(ln for ln in out.splitlines() if ln.startswith("memory sets"))
    assert "BETWEEN 1, SPECIFIC 2, SEVERAL 1, BROAD 0, ALONE 1" in live
    assert "BETWEEN 0, SPECIFIC 1, SEVERAL 0, BROAD 0, ALONE 0" in sets
    assert not leads_in(out)                                     # no keys without --top
    run_main(monkeypatch, "--top", "3")
    lines = leads_in(capsys.readouterr().out)
    # SPECIFIC first, by changes, then SEVERAL: each "key  cls  changes  row (steps)"
    assert [ln.split()[1] for ln in lines] == ["SPECIFIC", "SPECIFIC", "SPECIFIC"]
    run_main(monkeypatch, "--top", "9")
    lines = leads_in(capsys.readouterr().out)
    assert len(lines) == 4                                       # ALONE, BETWEEN and NEVER are no leads to list
    assert lines[-1].split()[:3] == [key(U_SEVERAL), "SEVERAL", "2"] and "Alpha (1); Bravo (1)" in lines[-1]
    assert any(ln.split()[0] == key(S_X, "set") and ln.rstrip().endswith("Charlie (1)") for ln in lines)


def leads_in(out: str) -> list:
    return [ln for ln in out.splitlines() if ln.startswith(("global:0x", "set:0x"))]


def test_without_write_nothing_is_written(cam, monkeypatch, capsys, tmp_path):
    tops = (paths.runs_top(), coverage.looks_dir(), tmp_path)

    def files():
        return sorted((p, p.stat().st_mtime_ns) for top in tops for p in top.rglob("*"))
    before = files()
    run_main(monkeypatch, "--top", "5")
    assert not coverage.leads_file(CAM).exists() and not coverage.leads_file(CAM).parent.exists()
    assert files() == before


def test_write_is_whole_and_owner_only(cam, monkeypatch, capsys):
    p = coverage.leads_file(CAM)
    run_main(monkeypatch, "--write")
    assert p.exists() and not list(p.parent.glob("*.part"))
    assert "written:" in capsys.readouterr().out
    if os.name != "nt":
        assert p.stat().st_mode & 0o777 == 0o600 and p.parent.stat().st_mode & 0o777 == 0o700
    first = p.read_bytes()
    run_main(monkeypatch, "--write")
    assert p.read_bytes() == first                               # the same downloads give the same bytes
    # a write that fails before the file is put in place leaves the one there whole
    p.write_text('{"live": [], "sets": []}\n', encoding="utf-8")

    def fail(self, target):
        raise OSError("disk full")
    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(SystemExit) as e:
        run_main(monkeypatch, "--write")
    assert "not written" in str(e.value) and "disk full" in str(e.value)
    assert p.read_text(encoding="utf-8") == '{"live": [], "sets": []}\n' and not list(p.parent.glob("*.part"))


def test_the_ledger_reads_the_leads_written(cam, monkeypatch, capsys):
    run_main(monkeypatch, "--write")
    led = coverage.build(CAM, src=coverage.load_sources(CAM, records=coverage.records_of(SAMPLE)))
    recs = {r["key"]: r["status"] for r in led.records}
    assert recs[key(U_NEVER)] == "unmapped, never seen to change"
    for rid in (U_BETWEEN, U_SPECIFIC, U_SEVERAL, U_ALONE, U_PROOF):
        assert recs[key(rid)] == "changed, no row attributed", hex(rid)
    assert recs[key(S_X, "set")] == "changed, no row attributed"
    assert recs[key(G_ALPHA)] != "unmapped, never seen to change"
    vol = next(rid for _, rid in camset.volatile("ILCE-1M2"))
    assert recs[key(vol)] == "unmapped, not examined"             # left out of the leads: nothing claimed of it
