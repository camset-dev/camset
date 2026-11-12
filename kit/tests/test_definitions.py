"""What reaches a definition (K-01, K-10, K-11, K-15, K-21, K-22): proofs from the definition's own camera only,
finished attempts only, labels and values one to one; volatile records per body; a chain that stops when its start
file does not load; C4 only after the owner's recorded yes. And the definitions themselves (docs/decisions/0019,
0020): one per model and firmware, what the kit takes from data/ round-trips byte for byte, the container block read
as the editor reads it. Synthetic runs, made-up values; no camera.
"""
import collections
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, datafiles, definitions, jsonl, models, paths  # noqa: E402
from camkit.runs import Run  # noqa: E402
from writer import a1_tables as HAND_TABLES  # noqa: E402

A1 = paths.A1II
DOC = definitions.load(A1)
# the public file alone, as a fresh clone and CI read it: a check that needs no evidence reads this, so it runs there too
PUB = definitions.load_public(A1)
PUB_BY = {s["key"]: s for s in PUB["settings"]}
SAMPLE = definitions.sample(DOC)

# the mapping's evidence: the definition's (its proofs' rows, name sources, runs) and its hand tables' (the hand proofs,
# kit/writer/hand_evidence.py), both in the mapper's private overlay
EVIDENCE = definitions.evidence_path(definitions.path(A1)).exists() and HAND_TABLES.HAND_EVIDENCE is not None
# a test that reads the mapping's evidence, which only the mapper's private evidence files hold; without them (a fresh
# clone, CI) there is nothing to check
needs_evidence = pytest.mark.skipif(not EVIDENCE, reason="reads the mapping's evidence (private/evidence/, not here)")


def other_body(path: Path, model: bytes = b"ILCE-7M5"):
    """The sample with another model name in its header, written through its block (a test file; never uploaded)."""
    b = camset.block_of(A1)
    path.write_bytes(b.sealed(b.with_text(SAMPLE.read_bytes(), "model", model)))
    return path


def saved_on(path: Path, video: int = 1, firmware: bytes = None):
    """The sample with its video system byte at `video` (1: PAL in the a1 II's block) and, when given, other firmware
    bytes, written through its block (a test file; never uploaded)."""
    b = camset.block_of(A1)
    d = bytearray(SAMPLE.read_bytes())
    d[b.video_system[0].n] = video
    if firmware is not None:
        d[b.firmware[0].n:b.firmware[1].n] = firmware
    path.write_bytes(b.sealed(bytes(d)))
    return path


def a_run(tmp_path: Path, files=("sample",)) -> Path:
    run = tmp_path / "kit2_pass2"
    (run / "dat").mkdir(parents=True)
    for i, f in enumerate(files):
        dst = run / "dat" / f"{i + 1:05d}_x.DAT"
        shutil.copy(SAMPLE, dst) if f == "sample" else other_body(dst)
    return run


# ---------------------------------------------------------------- the proofs' camera

def test_proofs_from_another_body_are_refused(tmp_path):
    import schema_update as S
    assert S.model_refused(a_run(tmp_path / "a"), DOC) == ""
    why = S.model_refused(a_run(tmp_path / "b", ("other",)), DOC)
    assert "ILCE-7M5" in why and "editor/definitions/ILCE-7M5_fw4.00.json" in why and "0019" in why
    assert "editor/definitions/ILCE-1M2_fw4.00.json" in why                 # what it was to go into
    assert "more than one camera" in S.model_refused(a_run(tmp_path / "c", ("sample", "other")), DOC)
    empty = tmp_path / "d" / "kit2_pass2"
    empty.mkdir(parents=True)
    assert "cannot be told" in S.model_refused(empty, DOC)


def test_ntsc_and_pal_downloads_of_one_firmware_are_one_camera(tmp_path):
    """The camera wrote 04 00 00 on NTSC and 04 00 01 on PAL, nothing else changed (2026-11-06): its third byte is the
    video system, so a run holding both is one camera and firmware, and its proofs go into that firmware's definition.
    A second firmware is still refused, its files named with their video system."""
    import schema_update as S
    run = a_run(tmp_path / "a")
    pal = saved_on(run / "dat" / "00002_pal.DAT")
    assert models.header(pal) == models.header(SAMPLE) == ("ILCE-1M2", "4.00")
    assert (models.video_system(pal), models.video_system(saved_on(tmp_path / "n.DAT", 0))) == ("PAL", "NTSC")
    assert models.of_run(run) == ("ILCE-1M2", "4.00") and S.model_refused(run, DOC) == ""
    a, b = camset.read(SAMPLE), camset.read(pal)
    assert (b.firmware, b.video_system) == ("4.00", "PAL") and a.firmware == "4.00"
    assert a.signature() == b.signature() == DOC["layouts"][0]["signature"]
    assert camset.diff(a, b) == [], "the video system is in the header, not in a record"
    odd = camset.read(saved_on(tmp_path / "odd.DAT", 7))
    assert odd.video_system == "video system 7, which the block names nothing for"
    # another firmware (4.01, made up) beside them: refused, each file named with its video system
    saved_on(run / "dat" / "00003_other.DAT", 0, bytes([4, 1]))
    why = S.model_refused(run, DOC)
    assert "more than one camera or firmware" in why, why
    assert "ILCE-1M2 firmware 4.00 (00001_x.DAT, " in why and "ILCE-1M2 firmware 4.01 (00003_other.DAT, NTSC)" in why
    # the reading before 2026-11-06 took the PAL file for firmware 4.01
    d = block_json()
    d["firmware"] = {"at": "0x36", "to": "0x39", "decode": "major_minor3"}
    del d["video_system"]
    old = camset.Block.parse(d)
    assert old.firmware_text(pal.read_bytes()) == "4.01" and old.video_system_of(pal.read_bytes()) is None


def test_report_refuses_another_body_unless_told(tmp_path, monkeypatch):
    """The report compares a run with the definition of the camera the kit works on: another body's run is refused,
    and so is a camera with no definition yet, unless --no-schema says to compare with none."""
    run = a_run(tmp_path, ("other",))
    (run / "proofs.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(run)], capture_output=True,
                       text=True, timeout=120)
    assert r.returncode != 0 and "ILCE-7M5" in r.stderr and "--no-schema" in r.stderr
    monkeypatch.setenv("CAMSET_CAMERA", "ILCE-7M5_fw4.00")              # a camera with no definition yet
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(run)], capture_output=True,
                       text=True, timeout=120)
    assert r.returncode != 0 and "no definition of ILCE-7M5_fw4.00 yet" in r.stderr and "--no-schema" in r.stderr
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(run), "--no-schema"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert json.loads(Path(run / "report.json").read_text(encoding="utf-8")) == []


# ---------------------------------------------------------------- what counts

def proof(label, index, changes, attempt=None, base="00001_before.DAT", frame=0, path=("Drive Mode",), kind="list"):
    r = {"path": list(path), "kind": kind, "index": index, "label": label, "base": base,
         "chosen_frame": f"{frame:05d}_down.png", "dat": f"{frame + 1:05d}_x.DAT", "applied": True,
         "changes": [{"key": k, "before": b, "after": a} for k, b, a in changes]}
    if attempt:
        r["attempt"] = attempt
    return r


def write_run(tmp_path, proofs, failures=(), done=()):
    run = a_run(tmp_path)
    with open(run / "proofs.jsonl", "w", encoding="utf-8") as f:
        for p in proofs:
            f.write(json.dumps(p) + "\n")
    with open(run / "failures.jsonl", "w", encoding="utf-8") as f:
        for x in failures:
            f.write(json.dumps(x) + "\n")
    with open(run / "attempts.jsonl", "w", encoding="utf-8") as f:
        for a in done:
            f.write(json.dumps({"attempt": a, "row": "Drive Mode", "complete": True}) + "\n")
    return run


def made_base(run: Path, name: str, values: dict) -> str:
    """A base download in the run's dat/: the sample with the given records ({key: value}, one-byte records of section
    0) set, written through its block (a test file; never uploaded). Returns its name, as a proof's "base" says it."""
    cs = camset.read(SAMPLE)
    changes = {}
    for key, v in values.items():
        rid = int(key.split(":0x")[1], 16)
        changes[(0, rid)] = int(v).to_bytes(len(cs.get(0, rid).raw), "little")
    (run / "dat" / name).write_bytes(camset.with_values(cs, changes))
    return name


def counted(run):
    import pass2_report as R
    proofs = R.proofs_of(run)
    return R.rows_of(run, proofs, R.unfinished(proofs, R.attempts_done(run), R.failing_frames(run)))


def test_a_finished_attempt_counts_and_an_unfinished_one_does_not(tmp_path):
    good = [proof("Continuous", 1, [("global:0x0001", 0, 1)], "a1", frame=10),
            proof("Single", 0, [], "a1", frame=12)]
    cut = [proof("Continuous", 1, [("global:0x0002", 0, 1)], "a2", path=("ISO",), frame=20)]
    rows = counted(write_run(tmp_path, good + cut, done=["a1"]))
    assert set(rows) == {"Drive Mode"}


def test_a_sticky_side_effect_gives_no_mapping(tmp_path):
    """Option B left 0x0009 changed: it shows in every later diff, the row never ends as it began, so prove_run
    never records the attempt as finished, and nothing of it counts."""
    sticky = [proof("B", 1, [("global:0x0001", 0, 1), ("global:0x0009", 0, 7)], "s1", frame=10),
              proof("C", 2, [("global:0x0001", 0, 2), ("global:0x0009", 0, 7)], "s1", frame=12),
              proof("A", 0, [("global:0x0009", 0, 7)], "s1", frame=14)]
    assert counted(write_run(tmp_path, sticky)) == {}


def test_a_failed_rows_cut_short_attempt_is_left_out(tmp_path):
    """Proofs written before attempts were tagged: the attempt a standing failure cut short does not count, an
    earlier attempt of the same row that ended as it began does."""
    earlier = [proof("B", 1, [("global:0x0001", 0, 1)], base="00001_a.DAT", frame=10),
               proof("A", 0, [], base="00001_a.DAT", frame=12)]
    retry = [proof("B", 1, [("global:0x0001", 0, 5)], base="00020_b.DAT", frame=30)]
    failure = {"path": ["Drive Mode"], "why": "the cursor is not on 'C'", "frame": "00033_down.png"}
    rows = counted(write_run(tmp_path, earlier + retry, failures=[failure]))
    assert rows["Drive Mode"][1]["changes"][0]["after"] == 1          # the earlier attempt's, not the cut one's
    rows = counted(write_run(tmp_path / "x", retry, failures=[failure]))
    assert rows == {}


def test_every_failed_attempt_of_a_carousel_axis_is_left_out_back_to_its_start(tmp_path):
    """A carousel axis's proofs carry no attempt tag, and each diffs its visit with the download after the visit
    before (its base is that proof's file). Session A's two Focus Area / Custom 1 attempts each stopped at Custom 3
    (2026-11-08): every failure of an axis row, whether the row still fails or not, cuts its attempt, back through the
    chain to the attempt's start, never past a visit that put the row back (the end of an earlier attempt, which
    counts). Only the last failure's last proof used to go, so the Custom 2 visits counted. Made-up records."""
    def axis(label, index, changes, base, frame, final=False):
        r = proof(label, index, changes, base=base, frame=frame, path=("Focus Area",), kind="axis")
        return {**r, "option": "Custom 1", **({"final": True} if final else {})}
    finished = [axis("Custom 2", 1, [("global:0x0001", 0, 1)], "00001_before.DAT", 10),
                axis("Custom 3", 2, [("global:0x0001", 1, 2)], "00011_x.DAT", 12),
                axis("Custom 1", 0, [], "00013_x.DAT", 14, final=True)]
    first = [axis("Custom 2", 1, [("global:0x0001", 0, 5)], "00015_x.DAT", 20),
             axis("Custom 1", 0, [("global:0x0001", 5, 0)], "00021_x.DAT", 22)]
    second = [axis("Custom 2", 1, [("global:0x0001", 0, 7)], "00030_before.DAT", 31),
              axis("Custom 1", 0, [("global:0x0001", 7, 0)], "00032_x.DAT", 33)]
    fails = [{"path": ["Focus Area"], "kind": "axis", "option": "Custom 1", "why": "Custom 3's title read wrong",
              "frame": f"{n:05d}_reread.png"} for n in (25, 36)]
    rows = counted(write_run(tmp_path, finished + first + second, failures=fails))
    row = rows["Focus Area / Custom 1"]
    assert {i: o["changes"][0]["after"] if o["changes"] else None for i, o in row.items()} == {1: 1, 2: 2, 0: None}
    assert row[0].get("final")                    # the finished attempt's put-back, not a cut attempt's Custom 1
    # a retry proves Custom 3 alone (the camera notes' next step): the row no longer fails, and the cut attempts stay
    # out all the same, for an axis row's every failure counts (review 4)
    retry = [axis("Custom 3", 2, [("global:0x0001", 0, 2)], "00039_before.DAT", 40)]
    row = counted(write_run(tmp_path / "retry", finished + first + second + retry, failures=fails))["Focus Area / Custom 1"]
    assert row[1]["changes"][0]["after"] == 1 and row[2]["dat"] == "00041_x.DAT" and row[0].get("final")
    # a finished attempt whose put-back left a record differing (explained since 2026-11-07), then a failure with no
    # proof after it: the finished attempt counts whole, nothing of it is cut
    left = finished[:2] + [axis("Custom 1", 0, [("global:0x0009", 0, 4)], "00013_x.DAT", 14, final=True)]
    row = counted(write_run(tmp_path / "left", left, failures=fails[:1]))["Focus Area / Custom 1"]
    assert sorted(row) == [0, 1, 2] and row[1]["changes"][0]["after"] == 1


def test_two_values_for_one_label_is_a_conflict(tmp_path):
    import pass2_report as R
    proofs = [proof("B", 1, [("global:0x0001", 0, 1)], "a1", frame=10), proof("A", 0, [], "a1", frame=12),
              proof("B", 1, [("global:0x0001", 0, 3)], "a2", frame=20), proof("A", 0, [], "a2", frame=22)]
    run = write_run(tmp_path, proofs, done=["a1", "a2"])
    rows = counted(run)
    notes = R.not_one_to_one(R.proofs_of(run), "Drive Mode", "global:0x0001", {}, {"list"})
    assert notes and notes[0]["kind"] == "not one to one"
    import schema_update as S
    assert S.mixed({"notes": notes}) and not S.mixed({"notes": []})
    assert rows["Drive Mode"][1]["changes"][0]["after"] == 3


def test_the_report_lists_a_label_that_wrote_two_values(tmp_path, monkeypatch):
    """The console listing of a record whose label wrote two values: its "not one to one" note has no value (None),
    which the listing once formatted as a number and crashed on, after report.md was written (2026-11-09). It is now
    listed with no number, and the report ends normally. A made-up record, so the a1 II's definition calls it new."""
    proofs = [proof("B", 1, [("global:0x0001", 0, 1)], "a1", frame=10), proof("A", 0, [], "a1", frame=12),
              proof("B", 1, [("global:0x0001", 0, 3)], "a2", frame=20), proof("A", 0, [], "a2", frame=22)]
    run = write_run(tmp_path, proofs, done=["a1", "a2"])
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(run)], capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-600:]
    assert "not one to one" in r.stdout and "the label wrote 2 different values" in r.stdout


def test_two_labels_one_value_in_a_one_record_list(tmp_path):
    import pass2_report as R
    opts = {1: proof("B", 1, [("global:0x0001", 0, 4)]), 2: proof("C", 2, [("global:0x0001", 0, 4)]),
            0: proof("A", 0, [])}
    recs = R.values_of(opts)
    assert R.two_labels_one_value(opts, recs) == {"global:0x0001": ["B", "C"]}
    opts[2] = proof("C", 2, [("global:0x0001", 0, 5)])
    assert R.two_labels_one_value(opts, R.values_of(opts)) == {}



def test_a_display_proof_counts_as_a_seen_value_and_reaches_the_definition(tmp_path):
    """A single-option list's display proof (prove_run's "proof": "display", nothing chosen): pass2_report takes the
    value its row's record held as the one its label writes, seen and not inferred, its name backed by the readers
    that read it (never "held", which told the value a record held, decision 16), and schema_update's plain pass
    labels that value with it and counts it proved. Made-up value 99."""
    import pass2_report as R
    import schema_update as S
    shown = {"path": ["Movie Settings", "Rec Frame Rate"], "kind": "list", "proof": "display", "index": 0,
             "label": "25p", "shown": "25p", "vlm": "25p", "chosen_frame": "00002_right.png", "base": "00001_x.DAT",
             "dat": "00001_x.DAT", "changes": [], "held": [{"key": "global:0x0202", "value": 99}], "notice": None,
             "applied": True, "attempt": "d1", "context": "Movie mode, PAL, File Format XAVC HS 8K"}
    inferred = {}
    assert R.values_of({0: shown}, inferred=inferred) == {"global:0x0202": {"25p": 99}} and inferred == {}
    run = write_run(tmp_path, [shown], done=["d1"])
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(run), "--no-schema"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    report = json.loads(Path(run / "report.json").read_text(encoding="utf-8"))
    (entry,) = report
    assert entry["row"] == "Movie Settings > Rec Frame Rate [Movie mode, PAL, File Format XAVC HS 8K]"
    assert entry["records"]["global:0x0202"]["proved"] == {"25p": 99}
    assert entry["records"]["global:0x0202"]["names"] == {"25p": "two readers"}       # the map, the OCR, the reader
    doc = json.loads(json.dumps(DOC))
    S.generic(doc, report, run, "2026-11-06")
    s = next(x for x in doc["settings"] if x["key"] == "global:0x0202")
    assert [99, "25p"] in s["values"] and 99 in s["proved"]["values"]
    assert s["proved"]["names"]["99"] == "two readers" and "inferred" not in s["proved"]


def test_the_plain_pass_names_a_grids_ends_and_zero_and_keeps_it_sampled(tmp_path):
    """The plain pass (generic: a camera with no hand tables, so no range and step to name a grid from) on a White
    Balance grid row: each record is sampled (how many proofs, and whether they lie on a line), its proofs not
    listed, and the camera's readout of the points every grid walk visits, both ends and 0, names them; the point
    only the walk's put-back gave (the value the grid held when it began, made-up A2.5 here) is named nowhere
    (decision 16). A grid off its line keeps its names too. The review of 2026-11-08 found the grid losing every
    name."""
    import schema_update as S
    run = a_run(tmp_path)
    rec = lambda proved, linear: {"verdict": "new", "schema_name": None, "proved": proved, "linear": linear, "notes": []}
    report = [{"row": "White Balance / grid 0 [Movie mode]", "options": 7, "kinds": ["wbgrid"], "notices": [],
               "records": {"global:0x0c4d": rec({"A7": 7000, "B7": -7000, "0": 0, "A2.5": 2500}, True),
                           "global:0x0c6b": rec({"G7": 7000, "M7": -7000, "0": 0}, False)}}]
    doc = {"settings": [], "menu": [], "camera": {}}
    changed = S.generic(doc, report, run, "2026-11-08")
    by = {s["key"]: s for s in doc["settings"]}
    ab, gm = by["global:0x0c4d"], by["global:0x0c6b"]
    assert ab["values"] == [[-7000, "B7"], [0, "0"], [7000, "A7"]], "the ends and 0, never the start"
    assert ab["proved"]["sampled"] == {"proofs": 7, "linear": True} and "values" not in ab["proved"]
    assert set(ab["proved"]["names"].values()) == {"sampled"}
    assert gm["values"] == [[-7000, "M7"], [0, "0"], [7000, "G7"]] and gm["proved"]["sampled"]["linear"] is False
    assert not [c for c in changed if c[2] == 2500 or c[-1] == "A2.5"]

# ---------------------------------------------------------------- one body's files

def test_volatile_records_are_per_body_and_bodies_are_not_mixed(tmp_path):
    a1 = camset.read(SAMPLE)
    assert camset.volatile("ILCE-1M2") and camset.volatile("ILCE-7M5") == set()
    other = camset.read(other_body(tmp_path / "x.DAT"))
    assert other.model == "ILCE-7M5"
    with pytest.raises(ValueError, match="two bodies"):
        camset.diff(a1, other)
    rid = next(iter(camset.volatile("ILCE-1M2")))
    rec = a1.get(*rid)
    f = tmp_path / "v.DAT"
    f.write_bytes(camset.with_values(a1, {rid: bytes(len(rec.raw)) if any(rec.raw) else b"\1" * len(rec.raw)}))
    assert camset.diff(a1, camset.read(f)) == []                       # the a1 II's own volatile record
    assert camset.diff(a1, camset.read(f), include_volatile=True)


def test_models_header_and_current(tmp_path):
    assert models.header(SAMPLE) == ("ILCE-1M2", "4.00")
    assert models.current(tmp_path) is None
    run = Run("r", root=tmp_path)
    other_body(run.dat / "00001_before.DAT")
    assert models.current(tmp_path) == "ILCE-7M5"


# ---------------------------------------------------------------- a chain stops when its start file does not load

def test_chain_stops_after_a_failed_upload(tmp_path):
    chain = tmp_path / "c.toml"
    not_a_download = tmp_path / "start.DAT"
    shutil.copy(SAMPLE, not_a_download)
    chain.write_text(f'name = "t"\n[[step]]\ntitle = "start"\nupload = "{not_a_download.as_posix()}"\n'
                     f'[[step]]\ntitle = "next"\nrun = ["{Path(sys.executable).as_posix()}", "-c", "print(\'NEXT RAN\')"]\n',
                     encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "tools" / "chain.py"), str(chain), "--stop",
                        str(tmp_path / "STOP_CHAIN")], capture_output=True, text=True, timeout=120)
    assert "stopping the chain" in r.stdout and "NEXT RAN" not in r.stdout


# ---------------------------------------------------------------- the definitions: files, one per model and firmware

def test_every_definition_is_named_by_its_camera_and_has_its_data():
    """A definition's file is <model>_fw<firmware>.json of its one layout, with its data/ folder, its model page and
    its sample beside it; its format is the one the editor reads (DEFINITION_FORMAT in editor/src/schema.rs)."""
    rs = (ROOT / "editor" / "src" / "schema.rs").read_text(encoding="utf-8")
    editor_format = int(re.search(r"pub const DEFINITION_FORMAT: u32 = (\d+);", rs).group(1))
    assert editor_format == definitions.FORMAT
    found = definitions.every()
    assert [p.stem for p, _ in found] == sorted(definitions.key(d) for _, d in found) and found
    for p, doc in found:
        assert p.stem == definitions.key(doc) and len(doc["layouts"]) == 1
        assert doc["definition_format"] == definitions.FORMAT and list(doc)[:2] == ["$schema", "definition_format"]
        assert definitions.camera_file(p.stem).exists(), p.stem
        assert (ROOT / doc["layouts"][0]["doc"]).exists(), doc["layouts"][0]["doc"]
        s = definitions.sample(doc, p)
        assert s is None or (s.parent == p.parent and s.exists())


def test_the_definitions_round_trip_through_their_data():
    """What the kit takes from data/ (kit/schema_update.py's from_data: "$schema" and "definition_format", the camera
    section, the memory copies' names, the project's own help, the Expert marks, the notes' evidence apart) gives every
    committed definition back byte for byte: rewriting a definition from the same data changes nothing, and nothing in
    it was edited by hand."""
    import schema_update as S
    for p, doc in definitions.every():
        assert S.text(S.from_data(doc)) == p.read_text(encoding="utf-8"), p.name


def test_the_record_shapes_are_private_whole():
    """The value shapes of the records no setting covers were read off one body's downloads ("constant": what its
    files held, decision 16), so no camera's data folder holds them: they are the mapper's, private whole beside the
    definition's evidence (camkit.datafiles.record_shapes_file), and only the local proof viewer shows them. Nor do
    the docs read them (the memory map lists no shape)."""
    assert not list((ROOT / "data").glob("*/record_shapes_*.json"))
    assert datafiles.record_shapes_file(A1) == definitions.EVIDENCE_DIR / A1 / f"record_shapes_{A1}.json"
    built = Path(ROOT / "kit" / "tools" / "build_docs.py").read_text(encoding="utf-8")
    assert 'f"record_shapes_' not in built and "across the downloads" not in built
    assert not (ROOT / "schemas" / "record-shapes.schema.json").exists()


def picker_sample(n: int = 20, places=None, key: str = "global:0x042b") -> list:
    """A picker slot's proofs, places counted from the option its list opened on (the one the camera held), made-up
    codes 100 + place: by default a few made-up places of a list of n, the first (the held option) changing nothing."""
    places = sorted({0, 7, n - 3}) if places is None else places
    return [{"path": ["Custom Key/Dial Set."], "kind": "table", "option": "Custom Button 3 @0.key.2", "opens": "picker",
             "index": i, "label": f"Function {i}", "shown": f"Function {i}", "vlm": f"Function {i}",
             "chosen_frame": f"{i + 2:05d}_x.png", "base": "00001_x.DAT", "dat": f"{i + 2:05d}_x.DAT",
             "changes": [] if i == 0 else [{"key": key, "before": 100, "after": 100 + i}], "notice": None,
             "applied": True, "planned": True, "attempt": "s1"} for i in places]


def test_a_picker_sample_from_the_held_option_is_written_as_a_count(tmp_path):
    """A table row that proved only a sample stepped from the option the camera held (its list numbered from the option
    it opened on) is marked "sampled_from_start" in the report, its
    values kept there, and the definition writes its proof as a count, {"proofs", "linear": null, "from_start": true},
    listing none of its values and naming none from its readings: the three would tell the held option to anyone who
    knows the camera's list (decision 16). A whole walk, which leaves out only a few functions with a screen of their
    own, keeps its values; so does a list row. Made-up codes."""
    import pass2_report as R
    import schema_update as S
    sample = {r["index"]: r for r in picker_sample()}
    assert R.sampled_from_start(sample)
    whole = {r["index"]: r for r in picker_sample(places=[i for i in range(20) if i not in (5, 11)])}
    assert not R.sampled_from_start(whole)
    assert not R.sampled_from_start({i: {**r, "kind": "list"} for i, r in sample.items()})
    put_back = {**sample, 3: {**sample[7], "index": 3, "planned": False}}         # a put-back is no visit
    assert R.sampled_from_start(put_back)
    run = write_run(tmp_path, picker_sample(), done=["s1"])
    r = subprocess.run([sys.executable, str(ROOT / "kit" / "pass2_report.py"), str(run), "--no-schema"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    (entry,) = json.loads(Path(run / "report.json").read_text(encoding="utf-8"))
    rec = entry["records"]["global:0x042b"]
    assert rec["sampled_from_start"] is True and set(rec["proved"].values()) == {100, 107, 117}   # kept in the report
    doc = json.loads(json.dumps(DOC))
    s = next(x for x in doc["settings"] if x["key"] == "global:0x042b")
    s["proved"] = {"run": "r", "date": "2026-11-01", "values": [100, 107, 117],
                   "names": {"100": "two readers", "107": "two readers", "117": "one reader"}}
    S.generic(doc, [entry], run, "2026-11-10")
    assert s["proved"]["sampled"] == {"proofs": 3, "linear": None, "from_start": True}
    assert "values" not in s["proved"]
    assert not set((s["proved"].get("names") or {}).values()) & {"two readers", "one reader", "vision model", "sampled"}


@needs_evidence
def test_no_shipped_proof_lists_the_values_of_a_sample_from_the_held_option():
    """The shipped definition: every proof written from a picker sample stepped from the option the camera held is a
    count (from_start) with no values, linear null, and no value of it is named by a reading, only by the slot its
    picker group proved in full ("derived") or a rule. A rewrite that listed their values again would drop the mark,
    and the count of marked settings, pinned here, with it."""
    marked = [s for s in DOC["settings"] if ((s.get("proved") or {}).get("sampled") or {}).get("from_start")]
    assert len(marked) == 78
    for s in marked:
        p = s["proved"]
        assert "values" not in p and p["sampled"]["linear"] is None and p["sampled"]["proofs"] >= 2, s["key"]
        assert not set((p.get("names") or {}).values()) & {"two readers", "one reader", "vision model", "sampled"}, s["key"]


def side_list(places, start: int, n: int, changed_by=lambda i: 200 + i) -> dict:
    """A side list's proofs in one session (one base), each place's line in download order: every place but `start`
    writes made-up code 200 + place; the line at `start` changes nothing (the option the camera held, chosen to put it
    back), and comes last."""
    order = [i for i in places if i != start] + [start]
    return {i: {"path": ["Picture Profile", "PP3", "Gamma"], "kind": "sidelist", "index": i, "label": f"G{i}",
                "shown": f"G{i}", "vlm": f"G{i}", "base": "00100_base.DAT", "dat": f"{101 + k:05d}_x.DAT",
                "applied": True, "changes": [] if i == start else [{"key": "global:0x0557[2]", "before": 200 + start,
                                                                     "after": changed_by(i)}]}
            for k, i in enumerate(order)}


def test_a_start_or_put_back_is_no_proof_in_a_list_walked_in_part(tmp_path):
    """pass2_report.start_lines: in a list or side list walked in part (places left out between the first and the
    farthest), the line that is its session's first sight or last choice and changes nothing (the option the camera
    held, chosen to start from or to put it back) credits nothing: its value is only what the start held, the odd one
    out among the options chosen (decision 16). The report keeps it apart ("start_only", held_back); a value some other
    line proved by a real change stays; a whole walk keeps its start, one option among all. The writer then keeps no
    such value from an older definition (kept_proof's `gone`, and no counted line wrote it). Made-up codes."""
    import pass2_report as R
    import schema_update as S
    part = side_list([0, 6, 12, 7], start=7, n=13)
    held = {}
    assert R.start_lines(part) == {0, 7}
    assert R.values_of(part, held_back=held) == {"global:0x0557[2]": {"G0": 200, "G6": 206, "G12": 212}}
    assert held == {"global:0x0557[2]": {"G7": 207}}
    whole = side_list(range(5), start=3, n=5)
    assert R.start_lines(whole) == frozenset()
    assert R.values_of(whole)["global:0x0557[2]"]["G3"] == 203
    assert R.start_lines({i: {**o, "kind": "axis"} for i, o in part.items()}) == frozenset()
    old = {"run": "r", "date": "d", "menu": ["A"], "values": [200, 206, 207, 212]}
    new = {"run": "r", "date": "d", "menu": ["A"], "values": [200, 206, 212]}
    assert S.kept_proof(old, new, frozenset({207}), frozenset({207}))[0]["values"] == [200, 206, 212]
    assert S.kept_proof(old, new)[0]["values"] == [200, 206, 212], "no counted line wrote it"
    assert S.kept_proof(old, new, written=frozenset({207}))[0]["values"] == [200, 206, 207, 212], "a line wrote it"
    # a sample from the held option counts this report's lines only, never an older, larger count
    old_count = {"run": "r", "date": "d", "menu": ["A"], "sampled": {"proofs": 4, "linear": None, "from_start": True}}
    new_count = {"run": "r", "date": "d", "menu": ["A"], "sampled": {"proofs": 3, "linear": None, "from_start": True}}
    assert S.kept_proof(old_count, new_count)[0]["sampled"]["proofs"] == 3


def test_a_holds_chosen_codes_leave_out_a_value_only_its_start_accounted_for():
    """schema_update.hold_chosen, which EV_DOWN_FROM_20's holds name "hand table" by (the rest "counted"): this run's
    proofs and the definition's earlier ones, but not a value only a start line accounted for (the hold's own, put back
    last) that no proof here holds; one a proof here holds stays. Made-up codes."""
    import schema_update as S
    assert S.hold_chosen({1, 5, 9}, [1, 5, 9, 14], {14}) == {1, 5, 9}
    assert S.hold_chosen({1, 5, 9, 14}, [1, 5, 9, 14], {14}) == {1, 5, 9, 14}
    assert S.hold_chosen({1, 5}, [1, 5, 9], set()) == {1, 5, 9}                # an old proof kept, as kept_proof does


def test_a_whole_table_credits_its_start_from_its_put_back():
    """A table walked whole but for its start, which only the put-back line chose ("planned": false), credits the
    start from that line, as a whole walk does its own start, so the start is named as its neighbours are; a sample
    from the start does not. Made-up codes."""
    import pass2_report as R
    whole = {r["index"]: r for r in picker_sample(n=6, places=[1, 2, 3, 4, 5])}
    whole[0] = {**picker_sample(n=6, places=[0])[0], "planned": False}
    assert R.values_of(whole)["global:0x042b"]["Function 0"] == 100
    sample = {r["index"]: r for r in picker_sample(n=20)}
    sample[0] = {**sample[0], "planned": False}
    assert "Function 0" not in R.values_of(sample)["global:0x042b"]


def test_no_context_says_a_state_was_found():
    """menu_row, for every camera (the plain pass's rows too): a proof context's "as found" goes, the rest of the
    context stays, and a context of nothing else goes whole; nothing says how a camera was found (decision 16)."""
    import schema_update as S
    assert S.menu_row("Monitor Brightness [stills, as found]", frozenset()) == "Monitor Brightness"
    assert S.menu_row("Monitor Brightness [as found]", frozenset()) == "Monitor Brightness"
    assert S.menu_row("A > B [as found, Movie mode]", frozenset()) == "A > B [Movie mode]"
    assert S.menu_row("A > B [Movie mode]", frozenset()) == "A > B [Movie mode]"
    # the item that says it goes with the state it names
    assert S.menu_row("A [Movie mode as found]", frozenset()) == "A"
    assert S.menu_row("A [as found: Recording Media Slot 2]", frozenset()) == "A"
    assert S.menu_row("A [stills, Brightness Setup Manual (as found)]", frozenset()) == "A [stills]"
    # any case, a hyphen, and words alone taking the state before them
    assert S.menu_row("A [Recording Media Slot 2, as found]", frozenset()) == "A"
    assert S.menu_row("A [Movie mode, Brightness Setup: Manual, as found]", frozenset()) == "A [Movie mode]"
    assert S.menu_row("A [stills, AS FOUND]", frozenset()) == "A"
    assert S.menu_row("A [Movie mode, Slot 1 as-found]", frozenset()) == "A [Movie mode]"
    assert not [m for s in DOC["settings"] for m in (s.get("proved") or {}).get("menu") or [] if "as found" in m]


@needs_evidence
def test_no_part_walk_lists_a_value_only_its_start_accounts_for():
    """Opt-in, where the camera's runs are on this computer: no setting of the shipped definition lists in proved.values
    a value that pass 2's report holds back as only a start line's (start_only) and that no line of the report proves
    by a real change. Each such value would be what the camera held when a part walk began (decision 16)."""
    report_file = ROOT / "runs" / A1 / "kit2_pass2" / "report.json"
    if not report_file.exists():
        pytest.skip("the a1 II's pass-2 report is not in this clone")
    report = json.loads(report_file.read_text(encoding="utf-8"))
    proved, start = collections.defaultdict(set), collections.defaultdict(set)
    for e in report:
        for k, r in e["records"].items():
            proved[k] |= {json.dumps(v) for v in r["proved"].values()}
            start[k] |= {json.dumps(v) for v in (r.get("start_only") or {}).values()}
    listed = [(k, v) for k, vs in start.items() for v in vs - proved[k]
              if json.loads(v) in ((DOC_BY.get(k) or {}).get("proved") or {}).get("values", [])]
    assert not listed, [k for k, _ in listed]


def test_a_refusal_names_the_blocking_setting_but_not_its_value():
    """fromdata.blocked_reason: a refused option's reason keeps the camera's words up to the blocking setting's name
    ("... not available as follows Gamma"), matched against the definition's setting names, and leaves out the value
    it stood on, the camera's own setting unless a run set it (decision 16); where the row's proof context names that
    setting (the run set it) the value stays; with no name to match everything from "as follows" goes; a reason without
    "as follows" is as the camera said it. In the shipped definition every "as follows" ends on a setting's name, or
    its row's context names it."""
    from writer.fromdata import blocked_reason
    names = sorted(["Gamma", "Gamma (stills)", "Shoot Mode", "Shoot Mode: registered"], key=len, reverse=True)
    why = "This operation or setting not available as follows Gamma X9 • OK"
    assert blocked_reason(why, "Picture Profile > PP1 > Color Mode", names) == \
        "This operation or setting not available as follows Gamma"
    assert blocked_reason(why, "Picture Profile > PP1 > Color Mode [PP1 Gamma: X9]", names).endswith("Gamma X9")
    assert blocked_reason("Not available as follows Shoot Mode d Intelligent Auto", "Flash Mode", names) == \
        "Not available as follows Shoot Mode"
    assert blocked_reason("Not available as follows Wired LAN On", "x", names) == "Not available"
    assert blocked_reason("Connected to Remote Shooting. Cannot be executed.", "x", names) == \
        "Connected to Remote Shooting. Cannot be executed."
    settings = {s["name"] for s in DOC["settings"]}
    for s in DOC["settings"]:
        for b in s.get("menu_blocked") or []:
            m = re.search(r"as follows:?\s+(.*)$", b.get("reason") or "")
            if m:
                ctx = re.search(r"\[([^\]]*)\]$", b["menu"])
                assert m[1] in settings or (ctx and any(n in ctx[1] for n in settings if m[1].startswith(n))), \
                    (s["key"], b["menu"])


def test_copies_are_written_only_where_the_downloads_bear_the_rule_out(tmp_path, capsys):
    """with_copies (kit/writer/copies.py): a hand table's family gets "copies" on the live setting and "copy_of" on each
    copy while every download read holds the live value equal to one of its copies; a setting the table no longer names
    loses old fields; a download that cannot be read is skipped and counted; a download where a family's live value
    equals none of its copies stops the write (exit 1, the family and the file named), never drops the family quietly,
    which would leave its copies editable; with no downloads the definition is left as it is. Files made from the
    sample, the live value moved off both copies by computing one neither holds (no value written down here)."""
    from camkit import camset
    from writer.copies import with_copies
    table = {"global:0x0053": ["global:0x0e12", "global:0x0e14"], "global:0x0350": ["global:0x0e06", "global:0x0e08"]}
    root = tmp_path / "runs"
    (root / "r" / "dat").mkdir(parents=True)
    shutil.copy(SAMPLE, root / "r" / "dat" / "00001_a.DAT")
    (root / "r" / "dat" / "00002_junk.DAT").write_bytes(b"not a settings file")
    log = root / "downloads.jsonl"
    log.write_text("".join(json.dumps({"path": f"r/dat/{n}"}) + "\n" for n in ("00001_a.DAT", "00002_junk.DAT")),
                   encoding="utf-8")
    doc = json.loads(json.dumps(DOC))
    by = {s["key"]: s for s in doc["settings"]}
    by["global:0x0367"]["copies"] = ["global:0x0e0e"]                       # a family the table does not name: goes
    assert with_copies(doc, table, root) == 2
    assert "1 that could not be read skipped" in capsys.readouterr().out
    assert by["global:0x0053"]["copies"] == ["global:0x0e12", "global:0x0e14"]
    assert by["global:0x0e14"]["copy_of"] == "global:0x0053" and by["global:0x0e08"]["copy_of"] == "global:0x0350"
    assert "copies" not in by["global:0x0367"] and "copy_of" not in by["global:0x0053"]
    cs = camset.read(SAMPLE)
    neither = max(cs.get(0, 0x0e12).value(), cs.get(0, 0x0e14).value()) + 1
    rec = cs.get(0, 0x0053)
    (root / "r" / "dat" / "00003_b.DAT").write_bytes(
        camset.with_values(cs, {(0, 0x0053): neither.to_bytes(rec.size, "little", signed=True)}))
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"path": "r/dat/00003_b.DAT"}) + "\n")
    with pytest.raises(SystemExit) as stop:
        with_copies(doc, table, root)
    assert "global:0x0053" in str(stop.value) and "00003_b.DAT" in str(stop.value)
    assert by["global:0x0053"]["copies"]                                    # nothing written over
    assert with_copies(doc, table, tmp_path / "none") is None and by["global:0x0350"]["copies"]
    schema = json.loads(Path(ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))
    import jsonschema
    # as the public file holds them (lean: definitions.split)
    lean = {s["key"]: s for s in definitions.split({"settings": [by["global:0x0350"], by["global:0x0e08"]]})[0]["settings"]}
    jsonschema.Draft202012Validator(schema["$defs"]["setting"]).validate(lean["global:0x0350"])
    jsonschema.Draft202012Validator(schema["$defs"]["setting"]).validate(lean["global:0x0e08"])


def test_each_main_page_reads_its_own_modes_copy():
    """The Main pages' tiles (camera.main_tiles) for a setting the camera keeps per mode (COPIES: the record in use, its
    Stills copy, its Movie copy) read the copy of the page's own mode: the Stills page the Stills copy, the Movie and
    S&Q pages the Movie copy. The record in use holds the values of the mode a file was saved in (the switch to Movie
    loads the Movie copies into it; Movie and S&Q choices write it and the Movie copy, Stills choices it and the Stills
    copy), so a page reading it would show another mode's values in a file saved in that mode. No page reads the
    record in use of such a setting, nor another mode's copy. A family whose copies' modes are not known yet
    (COPY_MODES_UNKNOWN: Exposure Comp.) is read through its setting."""
    import schema_update as S
    known = {live: cs for live, cs in S.COPIES.items() if live not in S.COPY_MODES_UNKNOWN}
    stills = {cs[0] for cs in known.values()}
    movie = {cs[1] for cs in known.values()}
    for page in DOC["camera"]["main_tiles"]:
        keys = {k for tile in page["tiles"] for k in tile.get("keys") or ()}
        own, other = (stills, movie) if page["name"] == "Stills" else (movie, stills)
        assert not keys & (other | set(known)), (page["name"], keys & (other | set(known)))
        assert keys & own, page["name"]


def test_the_video_system_values_are_checked_against_the_cameras_downloads(tmp_path, capsys):
    """check_video_systems (kit/writer/offered.py): a value a setting lists as one video system's only must not be held
    in the live settings of a download whose header says the other system; a contradiction stops the write (exit 1,
    the setting and the file named, never a value); a download that cannot be read is skipped and counted; a field the
    downloads bear out passes. Files made from the sample, the value read from it at run time."""
    from camkit import camset
    from writer.offered import check_video_systems
    root = tmp_path / "runs"
    (root / "r" / "dat").mkdir(parents=True)
    shutil.copy(SAMPLE, root / "r" / "dat" / "00001_n.DAT")
    saved_on(root / "r" / "dat" / "00002_p.DAT", video=1)
    (root / "r" / "dat" / "00003_junk.DAT").write_bytes(b"not a settings file")
    (root / "downloads.jsonl").write_text("".join(json.dumps({"path": f"r/dat/{n}"}) + "\n" for n in
                                                  ("00001_n.DAT", "00002_p.DAT", "00003_junk.DAT")), encoding="utf-8")
    held = camset.read(SAMPLE).get(0, 0x0202).value()
    setting = lambda vsv: {"settings": [{"key": "global:0x0202", "name": "Rate", "video_system_values": vsv}]}
    assert check_video_systems(setting({"NTSC": [held + 1], "PAL": [held + 2]}), root) == (2, 1)
    assert "1 that could not be read skipped" in capsys.readouterr().out
    for vsv, file in (({"NTSC": [held], "PAL": []}, "00002_p.DAT"), ({"NTSC": [], "PAL": [held]}, "00001_n.DAT")):
        with pytest.raises(SystemExit) as stop:
            check_video_systems(setting(vsv), root)
        said = str(stop.value)
        assert "global:0x0202" in said and file in said and not re.search(rf"(?<![\w.]){held}(?![\w.])", said)
    assert check_video_systems(setting({"NTSC": [held], "PAL": []}), tmp_path / "none") is None


def test_copy_for_is_the_hand_tables_and_every_section_is_checked(tmp_path, capsys):
    """with_copies with the hand table's modes: every copy of every family gets "copy_for", the modes the table names
    for its place, whatever the downloads or the proofs showed of that family; every section of every download read is
    checked (the live settings' mode by camera.live_mode, a memory set's by memory_sets.modes), a section where the
    setting is not the copy for its mode stopping the write (exit 1, the family, the file and the section named); a live
    section whose mode live_mode does not name is counted and printed. Files made from the sample, values computed at
    run time (none written down here)."""
    from camkit import camset
    from writer.copies import with_copies
    cs = camset.read(SAMPLE)
    raw = lambda rid, v: v.to_bytes(cs.get(0, rid).size, "little", signed=True)
    mode = DOC["camera"]["live_mode"]["modes"][str(cs.get(0, 0x13bf).value())]
    first, second = 41, 42                           # made-up values for the two copies, apart
    own = first if mode == "Stills" else second
    root = tmp_path / "runs"
    (root / "r" / "dat").mkdir(parents=True)
    keep = camset.with_values(cs, {(0, 0x0334): raw(0x0334, own), (0, 0x0df2): raw(0x0df2, first),
                                   (0, 0x0df4): raw(0x0df4, second)})
    (root / "r" / "dat" / "00001_a.DAT").write_bytes(keep)
    log = root / "downloads.jsonl"
    log.write_text(json.dumps({"path": "r/dat/00001_a.DAT"}) + "\n", encoding="utf-8")
    table = {"global:0x0334": ["global:0x0df2", "global:0x0df4"], "global:0x0350": ["global:0x0e06", "global:0x0e08"],
             "global:0x0367": ["global:0x0e0e", "global:0x0e10"], "global:0x0340": ["global:0x0e16", "global:0x13d6"]}
    modes = (["Stills"], ["Movie", "S&Q", "Time-lapse"])
    doc = json.loads(json.dumps(DOC))
    by = {s["key"]: s for s in doc["settings"]}
    by["global:0x0df2"]["proved"] = {**by["global:0x0df2"]["proved"], "menu": ["A > ISO", "B > ISO [Movie mode]"]}
    assert with_copies(doc, table, root, modes=modes, unknown=frozenset({"global:0x0340"})) == 4
    assert by["global:0x0df2"]["proved"]["menu"] == ["A > ISO"]                # another mode's row is not its proof
    assert "live sections whose mode" not in capsys.readouterr().out
    for live, copies in table.items():
        want = [None, None] if live == "global:0x0340" else [list(m) for m in modes]
        assert [by[c].get("copy_for") for c in copies] == want
    assert by["global:0x0e16"]["proved"] == by["global:0x0340"]["proved"] == by["global:0x13d6"]["proved"]  # with it
    unnamed = json.loads(json.dumps(doc))
    unnamed["camera"]["live_mode"]["modes"] = {}
    assert with_copies(unnamed, table, root, modes=modes, unknown=frozenset({"global:0x0340"})) == 4
    assert "1 live sections whose mode camera.live_mode does not name" in capsys.readouterr().out
    wrong = second if own == first else first
    (root / "r" / "dat" / "00002_b.DAT").write_bytes(camset.with_values(camset.parse(keep), {(0, 0x0334): raw(0x0334, wrong)}))
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"path": "r/dat/00002_b.DAT"}) + "\n")
    with pytest.raises(SystemExit) as stop:
        with_copies(doc, table, root, modes=modes, unknown=frozenset({"global:0x0340"}))
    said = str(stop.value)
    assert "global:0x0334" in said and "00002_b.DAT" in said and "section 0" in said


def test_the_shipped_copies_carry_their_modes_and_the_live_mode_is_named():
    """The shipped definition names the live settings' mode record (camera.live_mode, its values the memory sets'
    modes), and every copy of every family carries copy_for, the hand table's modes for that copy's place (COPY_MODES),
    PP7-PP9's included."""
    import schema_update as S
    live = DOC["camera"]["live_mode"]
    assert set(live["modes"].values()) <= set(DOC["camera"]["memory_sets"]["modes"])
    by = {s["key"]: s for s in DOC["settings"]}
    for live, copies in S.COPIES.items():
        want = [None] * len(copies) if live in S.COPY_MODES_UNKNOWN else [list(m) for m in S.COPY_MODES]
        assert [by[c].get("copy_for") for c in copies] == want, copies


def test_no_copy_shares_its_settings_name():
    """A copy never takes its setting's name: an editor shows a copy in a row of its own, so the rows are told apart
    by name ("… (stills)", "… (movie)", or a copy whose mode is not known yet named as a copy)."""
    import schema_update as S
    by = {s["key"]: s for s in DOC["settings"]}
    assert not [c for live, cs in S.COPIES.items() for c in cs if by[c]["name"] == by[live]["name"]]
    assert len({by[c]["name"] for live, cs in S.COPIES.items() if "[" not in live for c in (live, *cs)}) == \
        3 * sum(1 for live in S.COPIES if "[" not in live)


def test_no_setting_lists_the_records_a_proof_wrote_together():
    """No written_with in the shipped definition, nor in one the writer passes: which records a proof wrote together is
    the report's; in a definition it told how the camera was set when the proofs were made (which of a family's copies
    a choice wrote, decision 16). without_written_with takes an old list out (from_data), and the schema refuses it."""
    import jsonschema
    import schema_update as S
    assert not [s["key"] for s in DOC["settings"] if "written_with" in s]
    doc = {"settings": [{"key": "a", "written_with": ["b"]}, {"key": "b"}]}
    assert S.without_written_with(doc) == 1 and doc == {"settings": [{"key": "a"}, {"key": "b"}]}
    schema = json.loads(Path(ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))
    setting = jsonschema.Draft202012Validator(schema["$defs"]["setting"])
    one = {"key": "global:0x0001", "area": "global", "id": 1, "name": "n", "tab": "t", "group": "g"}
    errors = list(setting.iter_errors({**one, "written_with": ["global:0x0002"]}))
    assert errors and "written_with" in errors[0].message, [e.message for e in errors]


def test_the_shipped_copies_are_the_hand_tables_and_each_copy_names_its_setting():
    """The shipped definition's copies are a1_tables.COPIES (the Picture Profile parameters in use, PP1-PP11, and the
    profile in use among them, each with its Stills and Movie copy), and every copy_of names a setting that lists that
    copy: the two fields agree, as the editor's step that writes the copies needs."""
    import schema_update as S
    got = {s["key"]: s["copies"] for s in DOC["settings"] if "copies" in s}
    assert got == S.COPIES
    assert "global:0x04e9[0]" in got and got["global:0x0053"] == ["global:0x0e12", "global:0x0e14"]
    copy_of = {s["key"]: s["copy_of"] for s in DOC["settings"] if "copy_of" in s}
    assert copy_of == {c: live for live, cs in got.items() for c in cs}


def test_video_system_values_come_from_the_rows_walked_under_each_system(tmp_path, capsys):
    """with_video_systems (kit/writer/offered.py): a value proved only in rows whose downloads say NTSC is NTSC's, one
    proved only under PAL PAL's, one proved under both or never under neither; the system is each row's downloads'
    header, its context agreeing (a context saying PAL over NTSC downloads leaves its row out); a setting without values
    under each system gets none; the hand table gives a setting no proof speaks for. Made-up codes."""
    from writer.offered import with_video_systems
    run = tmp_path / "kit2_pass2"
    (run / "dat").mkdir(parents=True)
    shutil.copy(SAMPLE, run / "dat" / "00001_n.DAT")
    saved_on(run / "dat" / "00002_p.DAT", video=1)
    proof = lambda ctx, dat: {"path": ["Movie Settings", "Rec Frame Rate"], "kind": "list", "context": ctx, "dat": dat}
    proofs = [proof("Movie mode", "00001_n.DAT"), proof("Movie mode, PAL", "00002_p.DAT"),
              proof("Movie mode, PAL, wrong", "00001_n.DAT")]
    rec = lambda proved: {"records": {"global:0x0206": {"proved": proved}}}
    report = [{"row": "Movie Settings > Rec Frame Rate [Movie mode]", **rec({"60p": 0, "24p": 4, "1fps": 9})},
              {"row": "Movie Settings > Rec Frame Rate [Movie mode, PAL]", **rec({"50p": 1, "1fps": 9})},
              {"row": "Movie Settings > Rec Frame Rate [Movie mode, PAL, wrong]", **rec({"60p": 0, "77p": 7})}]
    doc = {"settings": [{"key": "global:0x0206", "values": [[0, "60p"], [1, "50p"], [2, "30p"], [4, "24p"], [7, "77p"],
                                                            [9, "1fps"]]},
                        {"key": "global:0x02b3", "values": [[0, "a"], [7, "b"], [8, "c"]]},
                        {"key": "global:0x0001", "values": [[0, "x"]], "video_system_values": {"NTSC": [0], "PAL": []}}]}
    table = {"global:0x02b3": {"NTSC": [0, 8], "PAL": [7]}, "global:0x0206": {"NTSC": [2], "PAL": []}}
    assert with_video_systems(doc, report, proofs, table, tmp_path, run) == 2
    out = capsys.readouterr().out
    assert "[Movie mode, PAL, wrong]" in out and "left out" in out and "hand table's entry is not used" in out
    s, h, old = doc["settings"]
    assert s["video_system_values"] == {"NTSC": [0, 4], "PAL": [1]} and list(s)[-1] == "video_system_values"
    # a list whose listed values are all one system's: the other's list is there, empty
    one = {"settings": [{"key": "global:0x0206", "values": [[0, "60p"], [4, "24p"], [9, "1fps"]]}]}
    assert with_video_systems(one, report, proofs, {}, tmp_path, run) == 1
    assert one["settings"][0]["video_system_values"] == {"NTSC": [0, 4], "PAL": []}
    assert h["video_system_values"] == {"NTSC": [0, 8], "PAL": [7]} and "video_system_values" not in old
    assert with_video_systems(doc, report, [], table, tmp_path, run) is None and s["video_system_values"]


def test_from_data_puts_the_camera_file_and_the_format_in_place_in_the_public_file():
    """The public definition alone (a fresh clone, CI), made old (no format, an old schema, the camera section stale),
    is brought up to date from data/: from_data gives the shipped public file byte for byte."""
    import schema_update as S
    old = json.loads(json.dumps(PUB))
    old.pop("definition_format")
    old["$schema"] = "../schemas/camset-schema.schema.json"
    old["camera"] = {"model": "ILCE-1M2"}
    assert S.text(S.from_data(old)) == (ROOT / "editor" / "definitions" / f"{A1}.json").read_text(encoding="utf-8")


@needs_evidence
def test_from_data_puts_the_camera_file_and_the_format_in_place():
    """An old definition (no format, the camera section stale, no Expert marks) is brought up to date from data/: the
    Expert marks that rest on how a meaning was found (source, evidence) come back from the whole."""
    import schema_update as S
    old = json.loads(json.dumps(DOC))
    old.pop("definition_format")
    old["$schema"] = "../schemas/camset-schema.schema.json"
    old["camera"] = {"model": "ILCE-1M2"}
    for s in old["settings"]:
        s.pop("expert", None)
    new = S.from_data(old)
    assert S.text(new) == S.text(DOC)


def test_a_definition_takes_only_its_own_cameras_help(tmp_path, monkeypatch, capsys):
    """The owner's rule ("a new user with a different camera shouldn't get the a1 II help"): from_data gives a made-up
    second camera's definition (the a1 II's settings under another model, their help taken out), and one of another
    firmware of the a1 II, none of the a1 II's help: not the a1 II's own file, which is not named for them, nor a copy
    of it renamed for them, refused for the model and firmware it carries inside, and said so. The a1 II's definition
    still takes its own."""
    import schema_update as S
    data = tmp_path / "data"
    shutil.copytree(ROOT / "data" / A1, data / A1)
    monkeypatch.setattr(definitions, "DATA", data)
    monkeypatch.setattr(S.help_files, "OWN", data)
    a1s = data / A1 / f"help_{A1}.json"
    assert S.text(S.from_data(json.loads(json.dumps(DOC)))) == S.text(DOC)          # the a1 II's own, as committed
    assert any(s.get("help") for s in DOC["settings"])
    for model, fw in (("ILCE-7M5", "4.00"), ("ILCE-1M2", "3.00")):
        cam = f"{model}_fw{fw}"
        doc = json.loads(json.dumps(DOC))
        doc["model"], doc["layouts"][0]["model"], doc["layouts"][0]["firmware"] = model, model, fw
        doc["camera"].pop("model", None)
        S.help_files.taken(doc)
        none = lambda d: not any(s.get("help") or s.get("option_help") for s in d["settings"])          # noqa: E731
        assert none(S.from_data(json.loads(json.dumps(doc)))), cam          # no help file of its own
        (data / cam).mkdir()
        shutil.copy(a1s, data / cam / f"help_{cam}.json")          # the a1 II's, renamed for this camera
        capsys.readouterr()
        assert none(S.from_data(json.loads(json.dumps(doc)))), cam
        assert capsys.readouterr().out == (f"help: {(data / cam / f'help_{cam}.json').as_posix()} is not used: it is for "
                                           f"the ILCE-1M2 firmware 4.00, not the {model} firmware {fw}\n")


def test_a_notes_evidence_is_apart_from_what_it_says_in_the_public_file():
    """split_evidence takes the runs and the days that prove a note out of what it says, and no public note holds any:
    no run's folder, no day in a parenthesis or a last clause, so splitting it again changes nothing."""
    import schema_update as S
    assert S.split_evidence("Off 0, On 1 (2026-11-02). View only.") == ("Off 0, On 1. View only.", "2026-11-02")
    assert S.split_evidence("Movie menu only; menu-verified 2026-10-23.") == ("Movie menu only.", "menu-verified 2026-10-23")
    said = "Only since the reset was run on 2026-10-30: before it, 0."
    assert S.split_evidence(said) == (said, "") and S.split_evidence("") == ("", "")
    for p, doc in definitions.every(evidence=False):
        for item in doc["layouts"] + doc["settings"]:
            note = item.get("note", "")
            assert "runs/" not in note and S.split_evidence(note) == (note, ""), (p.name, note)
            assert "note_evidence" not in item, (p.name, item.get("key"))


@needs_evidence
def test_a_notes_evidence_is_apart_from_what_it_says():
    """The runs and the days that prove a note go into "note_evidence" (shown in Expert mode only), right after
    "note", and the note keeps what it says: no run's folder in any note, and no day in a parenthesis or a last
    clause. Splitting again changes nothing, and a note written whole (as a run writes it) is split by from_data."""
    import schema_update as S
    assert S.split_evidence("Off 0, On 1 (2026-11-02). View only.") == ("Off 0, On 1. View only.", "2026-11-02")
    assert S.split_evidence("It writes HEIF 4 (RAW 0 and RAW & HEIF 2: runs/kit2_q, 2026-11-03).") == \
        ("It writes HEIF 4.", "RAW 0 and RAW & HEIF 2: runs/kit2_q, 2026-11-03")
    assert S.split_evidence("Lists (Aperture, ISO; runs/kit2_diffset), not more.") == ("Lists (Aperture, ISO), not more.",
                                                                                     "runs/kit2_diffset")
    assert S.split_evidence("Movie menu only; menu-verified 2026-10-23.") == ("Movie menu only.", "menu-verified 2026-10-23")
    said = "Only since the reset was run on 2026-10-30: before it, 0."
    assert S.split_evidence(said) == (said, "") and S.split_evidence("") == ("", "")
    for p, doc in definitions.every():
        for item in doc["layouts"] + doc["settings"]:
            note, evidence = item.get("note", ""), item.get("note_evidence", "")
            assert "runs/" not in note and S.split_evidence(note) == (note, ""), (p.name, note)
            if evidence:
                assert list(item)[list(item).index("note") + 1] == "note_evidence", item.get("key")
    one = json.loads(json.dumps(next(s for s in DOC["settings"] if "runs/" in s.get("note_evidence", ""))))
    whole = dict(one, note=one["note"].replace(" with it on HEIF; the switch writes HEIF 4 here from JPEG.",
                                               " with it on HEIF; the switch writes HEIF 4 here from JPEG (runs/kit2_x, 2026-11-09)."))
    assert whole["note"] != one["note"]
    split = S.with_evidence_apart(whole)
    assert split["note"] == one["note"] and split["note_evidence"] == "runs/kit2_x, 2026-11-09"
    assert S.with_evidence_apart(one) == one


def test_a_note_line_is_added_once_and_a_whole_note_compares_with_its_evidence_apart():
    """A line a pass adds to a note goes in once, with one space before it and none in front, also when the note was
    split before (its evidence then goes after the note's own); a note a table writes whole is the same note once its
    evidence is apart, and writing another drops the old evidence."""
    import schema_update as S
    line = "With it on, it writes only level (proved holding the camera each way, 2026-10-30)."
    s = {"key": "k", "note": ""}
    assert S.add_line(s, line) and s["note"] == line
    split = S.with_evidence_apart(s)
    assert (split["note"], split["note_evidence"]) == ("With it on, it writes only level.",
                                                      "proved holding the camera each way, 2026-10-30")
    assert not S.add_line(split, line) and not S.add_line(s, line)
    assert split["note"] == "With it on, it writes only level."
    old = {"key": "k", "note": "Earlier text.", "note_evidence": "runs/kit2_a"}
    assert S.add_line(old, line)
    assert old == {"key": "k", "note": "Earlier text. With it on, it writes only level.",
                   "note_evidence": "runs/kit2_a; proved holding the camera each way, 2026-10-30"}
    assert S.with_evidence_apart(old) == old
    bare = {"key": "k", "note": "Plain"}
    S.add_line(bare, "More.")
    assert bare["note"] == "Plain More."
    assert S.note_is(split, line) and S.note_is(s, line) and not S.note_is(split, "Another note (2026-10-30).")
    S.apply_fix(split, {"name": "N", "note": line})
    assert split["note_evidence"] == "proved holding the camera each way, 2026-10-30" and split["name"] == "N"
    S.apply_fix(split, {"note": "Another note."})
    assert split["note"] == "Another note." and "note_evidence" not in split



def test_a_note_never_starts_or_ends_with_a_space_nor_holds_two():
    """from_data tidies every note and its evidence: no space in front or after, none doubled (110 of the ILCE-1M2's
    notes began with one, from before the history was cut); a tidy item is left as it was, and every committed
    definition's notes are tidy, so --from-data --write strips them once and keeps them clean."""
    import schema_update as S
    assert S.with_tidy_note({"key": "k", "note": " Offers  the 95 functions. ", "note_evidence": "runs/kit2_a  "}) == \
        {"key": "k", "note": "Offers the 95 functions.", "note_evidence": "runs/kit2_a"}
    tidy = {"key": "k", "note": "Plain."}
    assert S.with_tidy_note(tidy) is tidy and S.with_tidy_note({"key": "k"}) == {"key": "k"}
    for p, doc in definitions.every():
        for item in doc["layouts"] + doc["settings"]:
            for k in ("note", "note_evidence"):
                t = item.get(k, "")
                assert t == t.strip() and "  " not in t, (p.name, item.get("key"), k)
    one = json.loads(json.dumps(DOC))
    s = next(x for x in one["settings"] if x.get("note"))
    want, s["note"] = s["note"], f" {s['note'].replace(' ', '  ', 1)} "
    again = S.from_data(one)
    assert next(x for x in again["settings"] if x["key"] == s["key"])["note"] == want
    assert S.text(S.from_data(json.loads(S.text(again)))) == S.text(again)

def test_the_expert_settings_are_the_78_the_editor_once_picked():
    """"expert": true is written by the kit on the settings the editor once hid by their names (decision 20), the
    a1 II's same 78 as before the rule moved, on My Menu's 42 places, which the My Menu page edits, on the 60 fields
    of the memories' live copy (each memory set holds its own), on the 3 more on no camera row whose name holds a
    mapping word and on the 4 JPEG/HEIF copies the camera writes with their main record."""
    import schema_update as S
    slots = S.mymenu_slots(DOC)
    mirror = S.mirror_of(DOC)
    flagged = [s["key"] for s in DOC["settings"] if s.get("expert")]
    assert flagged == [s["key"] for s in DOC["settings"] if S.expert(s, slots, mirror)]
    # + 27 on no camera row with a mapping word in their name (the memories' shutter numerators and denominators,
    # 2 of the sets' own and 24 of the live copy, and the SDK's "Unknown"), 2026-11-07
    # + 4 copies written together with their main record (JPEG/HEIF Quality and Image Size, Slot 1 and 2), 2026-11-07
    # + 1 the second copy of the Playback Filter Condition's ★OFF rating box (0x16c2, "(copy)" in its name, on no
    #   camera row; the ★-★★★★★ copies sit on Rating Set(Custom Key)'s row as its boxes), 2026-11-07
    # + 26 the Custom boxes' place records in the memory sets (kit2_framepos, 2026-11-09): derived copies, and the box in
    #   use, on no camera row, as the Zone's copies are
    assert len([s for s in DOC["settings"] if S.expert(s)]) == 78 + 27 + 4 + 1 + 26
    assert len([s for s in DOC["settings"] if S.expert(s, mirror=mirror)]) == 78 + 3 + 60 + 4 + 1 + 26   # + the live copy
    assert len(flagged) == 78 + 3 + 60 + 42 + 4 + 1 + 26
    assert {s["key"] for s in DOC["settings"] if s["name"].endswith("copy)")} <= set(flagged)
    assert {s.get("expert") for s in DOC["settings"]} == {True, None}            # true, or no key
    one = next(s for s in DOC["settings"] if s.get("expert"))
    assert list(one)[list(one).index("in_sets") + 1] == "expert"


# The words of the mapping work, which a photographer never reads: record numbers and keys, the passes, downloads, the
# owner, the SDK, the kit's guesses. The camera's own words that hold one are not: its Record Setting row, its record
# button, recording a movie, Auto Pixel Mapping, a group's "Reg. Flash Shooting Set:", a help's "is set: as ...".
MAPPING_TEXT = [re.compile(r"0x[0-9a-f]{4}", re.I), re.compile(r"\bpass \d\b", re.I), re.compile(r"\bdownload", re.I),
                re.compile(r"\bthe owner\b", re.I), re.compile(r"\bSDK\b"), re.compile(r"\(array element\)", re.I),
                re.compile(r"function code", re.I), re.compile(r"\bglobal:"), re.compile(r"\bset:(?!\s)"),
                re.compile(r"\binferred\b", re.I), re.compile(r"\bmapped\b", re.I),
                re.compile(r"(?<!pixel )\bmapping\b", re.I),
                re.compile(r"\brecord\b(?!\s+(?:button|an?\b|movies?|settings?\b))", re.I)]


def mapping_offenders(doc: dict) -> list:
    """(key, field, text) of every text a photographer reads that holds a mapping word: each setting not marked
    expert, by its name, group, help, options' help, display rule, refused options' reasons, why a value is not
    offered and why it is unproved
    (its note and note_evidence are shown in Expert mode only), and the tabs and the menu's groups."""
    out = []

    def check(key, field, text):
        if isinstance(text, str) and any(p.search(text) for p in MAPPING_TEXT):
            out.append((key, field, text))
    for i, tab in enumerate(doc.get("tabs") or []):
        check("tabs", f"[{i}]", tab)
    for m in doc.get("menu") or []:
        check("menu", m.get("label", ""), m.get("group"))
    for s in doc["settings"]:
        if s.get("expert"):
            continue
        for field in ("name", "group", "help", "display_rule"):
            check(s["key"], field, s.get(field))
        for v, text in s.get("option_help") or []:
            check(s["key"], f"option_help[{v}]", text)
        for i, b in enumerate(s.get("menu_blocked") or []):
            check(s["key"], f"menu_blocked[{i}].reason", b.get("reason"))
        for i, m in enumerate(s.get("not_offered") or []):
            check(s["key"], f"not_offered[{i}].why", m.get("why"))
        check(s["key"], "unproved_reason.why", (s.get("unproved_reason") or {}).get("why"))
    return out


def test_mapping_words_never_reach_a_non_expert_field():
    """What a photographer reads holds none of the mapping's words (2026-11-07: 113 names and a group did, "Drive Mode
    (third record)", "Other (from SDK)"). The kit makes it so (schema_update: MAPPING_WORDS marks a setting on no
    camera row Expert-only, SETTING_GROUPS and RECORD_FIXES name, with_plain_words tidies), never the definition by
    hand; and a dialog's button word never ends a refused option's reason."""
    import schema_update as S
    bad = mapping_offenders(DOC)
    assert not bad, "mapping words a photographer reads:\n" + "\n".join(f"  {k} {f}: {t!r}" for k, f, t in bad)
    made = {"key": "global:0x0001", "name": "Drive Mode (third record)", "group": "Other (from SDK)"}
    assert mapping_offenders({"settings": [made]}) and mapping_offenders({"settings": [S.with_plain_words(made)]})
    assert S.expert(made) and not S.expert(dict(made, row=["Drive Mode"]))
    assert S.with_plain_words(made)["group"] == "Other settings"
    assert not mapping_offenders({"settings": [dict(made, name="Record Setting (XAVC S HD, 60p)", group="Drive",
                                                    help="Lets the record button record a movie.")]})
    assert S.plain_reason("not available as follows Gamma HLG2 \u2022 OK") == "not available as follows Gamma HLG2"
    assert not [b for s in DOC["settings"] for b in s.get("menu_blocked") or [] if S.BUTTON_WORD.search(b["reason"])]


def test_my_menus_places_are_expert_by_its_records():
    """My Menu's places are marked by the records camera.my_menu names, not by their names: a camera without My Menu
    marks none, and a place's record elsewhere in the file (a memory's copy) is not one."""
    import schema_update as S
    slots = S.mymenu_slots(DOC)
    places = [s for s in DOC["settings"] if s["area"] == "global" and s["id"] in slots]
    assert len(slots) == 6 and len(places) == 42 and all(s.get("expert") for s in places)
    one = dict(places[0], name="Anything at all", source="Menu")
    one.pop("expert")
    assert S.expert(one, slots) and not S.expert(one)
    assert S.mymenu_slots({"camera": {}}) == frozenset() and not S.expert(dict(one, area="set"), slots)
    assert list(S.with_expert(one, slots))[list(one).index("in_sets") + 1] == "expert"


def test_the_mirror_stride_is_the_camera_files():
    """schema_update places the live copy's fields by the camera file's mirror (element_bytes), not a number of its
    own: global:0x018c@1248 is Movie Memory 1's field 288 on the a1 II."""
    import schema_update as S
    m = S.mirror_of(DOC)
    assert m["element_bytes"] == 320 and m == S.A1_MIRROR
    assert S.mirror_place("global:0x018c@1248", m) == (4, 288)
    assert S.mirror_key(m, 4, 288) == "global:0x018c@1248"
    assert S.mirror_place("global:0x018c@1248", {}) == (None, None)
    other = dict(m, element_bytes=100)
    assert S.mirror_place("global:0x018c@1248", other) == (13, 48)


# ---------------------------------------------------------------- the container block (docs/decisions/0020)

def block_json() -> dict:
    return json.loads(json.dumps(DOC["camera"]["file"]))


def test_the_kit_reads_the_container_through_the_block():
    """The sample through the a1 II's block: its header, its records and checksums, and the layout signature the
    editor computes (07a5b07a502c68f0)."""
    b = camset.Block.parse(block_json())
    assert b == camset.block_of(A1) and camset.blocks()[0] == b
    cs = camset.read(SAMPLE, block=b)
    assert (cs.model, cs.firmware, len(cs.sections), cs.checksums_ok) == ("ILCE-1M2", "4.00", 13, True)
    assert cs.signature() == DOC["layouts"][0]["signature"] == "07a5b07a502c68f0"
    import identify
    assert identify.signature(SAMPLE.read_bytes()) == cs.signature()
    assert camset.with_values(cs, {}) == SAMPLE.read_bytes()            # written back byte for byte


@pytest.mark.parametrize("where, value, words", [
    (("records", "endian"), "be", "endian"), (("header_checksum", "kind"), "crc32", "crc32"),
    (("records", "framing"), "x", "framing"), (("sections_start",), "0x3c ", "not an offset"),
    (("sections_start",), "60", "not an offset"), (("trailer_checksum", "at"), "end+4", "not an offset"),
    (("signature",), "md5", "md5"), (("magic", "colour"), "red", "colour")])
def test_an_unknown_kind_or_key_refuses_the_block_by_name(where, value, words):
    d = block_json()
    node = d
    for k in where[:-1]:
        node = node[k]
    node[where[-1]] = value
    with pytest.raises(camset.BlockError, match=re.escape(words)):
        camset.Block.parse(d)


def test_a_block_out_of_place_is_refused():
    d = block_json()
    d["header_checksum"]["at"] = "0x30"                       # inside the bytes it sums
    with pytest.raises(camset.BlockError, match="inside"):
        camset.Block.parse(d)
    d = block_json()
    d["firmware"]["to"] = "0x3a"
    with pytest.raises(camset.BlockError, match="major_minor reads two bytes"):
        camset.Block.parse(d)
    d = block_json()
    d["firmware"]["decode"] = "major_minor3"
    with pytest.raises(camset.BlockError, match="major_minor3 reads three bytes"):
        camset.Block.parse(d)


@pytest.mark.parametrize("value, words", [
    ({"at": "0x37", "names": {"0": "NTSC"}}, "inside the firmware"), ({"at": "0x39", "names": {"0": "NTSC"}}, "checksum's site"),
    ({"at": "0x3c", "names": {"0": "NTSC"}}, "past sections_start"), ({"at": "end-1", "names": {"0": "NTSC"}}, "start of the file"),
    ({"at": "0x38", "names": {}}, "names no value"), ({"at": "0x38", "names": {"256": "X"}}, "not a byte value"),
    ({"at": "0x38", "names": {"01": "X"}}, "not a byte value"), ({"at": "0x38", "names": {"1": " "}}, "gives 1 no name"),
    ({"at": "0x38", "names": {"0": "NTSC"}, "colour": "red"}, "colour"), ({"at": "0x38"}, "lacks names")])
def test_a_video_system_out_of_place_is_refused(value, words):
    """The video system's byte, as the editor's FileFormat::check has it: in the header, apart from the firmware and the
    header checksum's site, every value a byte with a name; a block without it reads as before."""
    d = block_json()
    d["video_system"] = value
    with pytest.raises(camset.BlockError, match=re.escape(words)):
        camset.Block.parse(d)
    d = block_json()
    del d["video_system"]
    b = camset.Block.parse(d)
    assert b.video_system is None and camset.parse(SAMPLE.read_bytes(), block=b).video_system == ""
    d = block_json()
    d["trailer_checksum"]["at"] = "0x40"
    with pytest.raises(camset.BlockError, match="end"):
        camset.Block.parse(d)


def test_a_wrong_site_fails_the_checksums_and_another_container_reads_through_its_own_block(tmp_path):
    """A block that names a wrong checksum site does not read the sample as checked; a made-up container (the
    header four bytes longer, every part moved) reads and writes back through a block of its own."""
    d = block_json()
    d["header_checksum"]["at"] = "0x3a"
    wrong = camset.Block.parse(d)
    with pytest.raises(ValueError, match="checksum mismatch"):
        camset.read(SAMPLE, block=wrong)
    assert not camset.read(SAMPLE, block=wrong, check=False).checksums_ok
    a1 = camset.block_of(A1)
    data = SAMPLE.read_bytes()
    moved = data[:0x39] + b"\0\0\0\0" + data[0x39:]                   # four reserved bytes before the checksum
    d = block_json()
    d["header_checksum"]["at"] = "0x3d"
    d["sections_start"] = "0x40"
    d["trailer_checksum"]["over"] = ["0x40", "end-4"]
    other = camset.Block.parse(d)
    moved = other.sealed(moved)
    assert not a1.describes(moved) or not a1.checksums_ok(moved)
    cs = camset.parse(moved, block=other)
    assert cs.checksums_ok and cs.model == "ILCE-1M2" and len(cs.sections) == 13
    assert cs.signature() == camset.read(SAMPLE).signature()           # the same records: the same layout
    assert camset.with_values(cs, {}) == moved


def test_identify_prints_a_draft_for_a_file_no_block_describes(tmp_path, capsys):
    import identify
    f = tmp_path / "x.DAT"
    data = SAMPLE.read_bytes()
    f.write_bytes(data[:0x3c] + bytes(range(1, 9)) + data[0x3c:])       # eight bytes no framing reads
    out = identify.describe(f)
    assert "no known container block describes this file" in out and "does NOT hold" in out
    assert '"sections_start": "0x3c"' in out
    assert not any(p.suffix == ".json" for p in tmp_path.iterdir())     # printed, never written
    good = identify.describe(SAMPLE)
    assert "KNOWN: ILCE-1M2 firmware 4.00: definition editor/definitions/ILCE-1M2_fw4.00.json" in good
    pal = identify.describe(saved_on(tmp_path / "pal.DAT"))
    assert "firmware bytes 0x36-0x37: 04 00 (firmware 4.00 by the header)" in pal
    assert "video system byte 0x38: 01 (PAL; not part of the camera's identity" in pal
    assert "KNOWN: ILCE-1M2 firmware 4.00: definition editor/definitions/ILCE-1M2_fw4.00.json" in pal


def test_the_ksy_describes_the_a1_block():
    """docs/formats/sony_camset.ksy, the container for people and Kaitai's tools, says what the a1 II's block says:
    the header's fields where the block puts them, the marker, the checksum's site; and the reader generated from it
    reads the sample to the same records as the block (decision 20's tie, until the .ksy is generated from the
    block)."""
    sys.path.insert(0, str(ROOT / "kit" / "tools"))
    from camset_ksy import format_spec, width
    b = camset.block_of(definitions.REFERENCE)
    spec = format_spec()
    at, where = 0, {}
    for f in spec["seq"]:
        if f["id"] == "sections":
            break
        where[f["id"]] = (at, at + width(spec, f))
        at += width(spec, f)
    assert at == b.sections_start.n
    assert where["magic"] == (b.magic_at.n, b.magic_at.n + len(b.magic)) and spec["seq"][0]["contents"] == b.magic.decode()
    assert where["model"] == (b.model[0].n, b.model[1].n) and where["saved"] == (b.saved[0].n, b.saved[1].n)
    assert where["firmware"] == (b.firmware[0].n, b.firmware[1].n)
    assert where["video_system"] == (b.video_system[0].n, b.video_system[0].n + 1)
    assert spec["seq"][[f["id"] for f in spec["seq"]].index("video_system")]["enum"] == "video_system"
    assert {int(k): v for k, v in spec["enums"]["video_system"].items()} == {v: n.lower() for v, n in b.video_system[1]}
    assert where["header_checksum"][0] == b.header_checksum.at.n and b.header_checksum.kind == "shift_sum"
    assert spec["types"]["record"]["seq"][1]["contents"] == list(b.marker.to_bytes(2, "little"))
    assert spec["seq"][-1]["id"] == "body_checksum" and b.trailer_checksum.at == camset.Offset(4, True)
    from camkit.formats.sony_camset import SonyCamset
    k = SonyCamset.from_bytes(SAMPLE.read_bytes())
    cs = camset.read(SAMPLE)
    assert k.model == cs.model and len(k.sections) == len(cs.sections)
    for ks, sec in zip(k.sections, cs.sections, strict=True):
        assert [(int(r.id), r.elem_size, r.num_elements) for r in ks.records] == [(r.id, r.size, r.count) for r in sec.values()]


# ---------------------------------------------------------------- a new camera's first definition

def test_a_new_camera_gets_its_own_definition_from_its_data_and_proofs(tmp_path, monkeypatch, capsys):
    """A camera with no definition yet (a made-up ILCE-7M5 firmware 4.00: the sample with another model name):
    schema_update starts one from its data/ folder and the run's downloads, with the settings the report proves named
    by their menu rows, and writes it as editor/definitions/ILCE-7M5_fw4.00.json; none of the a1 II's tables touch it,
    and the a1 II's definition is not written. A second run gives the same file."""
    import jsonschema
    from referencing import Registry, Resource
    import schema_update as S
    cam = "ILCE-7M5_fw4.00"
    data, defs = tmp_path / "data", tmp_path / "definitions"
    (data / cam).mkdir(parents=True)
    facts = {"$schema": "../../schemas/camera.schema.json", **json.loads(json.dumps(DOC["camera"]))}
    facts.update(model="ILCE-7M5", volatile_records=[], link_records=[])
    for k in ("sample", "main_tiles", "my_menu", "mirrors", "families", "exposure", "memory_sets"):
        facts.pop(k)
    (data / cam / f"camera_{cam}.json").write_text(json.dumps(facts), encoding="utf-8")
    monkeypatch.setattr(definitions, "DATA", data)
    monkeypatch.setattr(definitions, "DIR", defs)
    monkeypatch.setattr(S.help_files, "OWN", data)
    a1_text = (ROOT / "editor" / "definitions" / f"{A1}.json").read_bytes()
    run = a_run(tmp_path, ("other",))
    report = [{"row": "Shooting > Drive Mode", "options": 2, "notices": [],
               "records": {"global:0x01d8": {"verdict": "new", "proved": {"Single Shooting": 0, "Cont. Shooting": 1},
                                             "notes": [], "linear": None},
                           "set1:0x0180": {"verdict": "new", "proved": {"Single Shooting": 0}, "notes": [],
                                           "linear": None}}},
              {"row": "Exposure > Brightness [field 0]", "options": 3, "notices": [],
               "records": {"global:0x0340": {"verdict": "new", "proved": {"-1": -1, "0": 0, "+1": 1}, "notes": [],
                                             "linear": True}}},
              {"row": "Shooting > Twice", "options": 2, "notices": [],
               "records": {"global:0x0350": {"verdict": "conflict", "proved": {"A": 1, "B": 1}, "linear": None,
                                             "notes": [{"value": 1, "camera": "A, B", "schema": None,
                                                        "kind": "not one to one"}]}}},
              # an axis walked from the value it stood on, its row named after that value (made up): its setting is
              # named, noted and proved through its item alone (decision 16)
              {"row": "Shooting > Speed / Mid", "options": 3, "notices": [],
               "records": {"global:0x04d2": {"verdict": "new", "proved": {"Low": 0, "Mid": 2, "High": 4}, "notes": [],
                                             "linear": None}}}]
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (run / "proofs.jsonl").write_text("".join(json.dumps({"kind": "axis", "path": ["Shooting", "Speed"], "option": "Mid",
                                                          "label": lab}) + "\n" for lab in ("Low", "Mid", "High")),
                                      encoding="utf-8")
    # the a1 II's own help file copied in under this camera's name: refused for what it says inside, nothing taken
    shutil.copy(ROOT / "data" / A1 / f"help_{A1}.json", data / cam / f"help_{cam}.json")
    # the gate: the memory-set record the plain pass leaves out and the record not one to one, until accepted
    with pytest.raises(SystemExit):
        S.generic_main(definitions.path(cam), run, True)
    refused = capsys.readouterr().out
    assert not definitions.path(cam).exists() and "1 new, 1 not one to one" in refused
    S.accepted_file(cam).write_text(json.dumps({"model": "ILCE-7M5", "firmware": "4.00", "accepted": [
        {"kind": "new", "key": "set1:0x0180", "why": "a memory set's copy", "date": "2026-11-07"},
        {"kind": "not one to one", "key": "global:0x0350", "why": "to prove again", "date": "2026-11-07"}]}),
        encoding="utf-8")
    doc = S.generic_main(definitions.path(cam), run, True)
    said = refused + capsys.readouterr().out
    assert "has no definition yet" in said
    assert f"help_{cam}.json is not used: it is for the ILCE-1M2 firmware 4.00, not the ILCE-7M5 firmware 4.00" in said
    assert not any(s.get("help") or s.get("option_help") for s in doc["settings"])
    written = defs / f"{cam}.json"
    # the public file lean, its evidence beside it (the test's own folder: not the clone's private/evidence/)
    assert written.exists() and json.loads(written.read_text(encoding="utf-8")) == definitions.split(doc)[0]
    assert definitions.evidence_in_public(json.loads(written.read_text(encoding="utf-8"))) == []
    assert definitions.load(written) == json.loads(json.dumps(doc)) or \
        json.dumps(definitions.load(written), sort_keys=True) == json.dumps(doc, sort_keys=True)
    assert (ROOT / "editor" / "definitions" / f"{A1}.json").read_bytes() == a1_text
    assert list(doc)[:2] == ["$schema", "definition_format"] and doc["camera"]["model"] == "ILCE-7M5"
    assert doc["layouts"][0] == {"signature": camset.read(run / "dat" / "00001_x.DAT").signature(), "model": "ILCE-7M5",
                                 "firmware": "4.00", "note": "ILCE-7M5 firmware 4.00", "doc": f"docs/models/{cam}.md"}
    by = {s["key"]: s for s in doc["settings"]}
    assert set(by) == {"global:0x01d8", "global:0x0340", "global:0x04d2"}   # no memory-set key, nothing not one to one
    speed = by["global:0x04d2"]
    assert (speed["name"], speed["proved"]["menu"]) == ("Speed", ["Shooting > Speed"]) and "Mid" not in speed["note"]
    drive = by["global:0x01d8"]
    assert (drive["name"], drive["tab"], drive["group"]) == ("Drive Mode", "Shooting", "Shooting")
    assert drive["values"] == [[0, "Single Shooting"], [1, "Cont. Shooting"]] and drive["proved"]["values"] == [0, 1]
    assert drive["proved"]["names"] == {"0": "one reader", "1": "one reader"}        # no reader said more
    assert by["global:0x0340"]["values"] == [] and by["global:0x0340"]["proved"]["sampled"] == {"proofs": 3, "linear": True}
    reg = Registry().with_resources((p.name, Resource.from_contents(json.loads(Path(p).read_text(encoding="utf-8"))))
                                    for p in (ROOT / "schemas").glob("*.json"))
    schema = json.loads(Path(ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema, registry=reg).validate(definitions.split(doc)[0])
    again = S.generic_main(definitions.path(cam), run, False)
    assert S.text(again) == written.read_text(encoding="utf-8")       # a second run changes nothing


def test_the_a1_tables_run_for_the_a1_definition_only(monkeypatch):
    """schema_update's ILCE-1M2 tables and the runs they read are that definition's: any other camera, the a1 II at
    another firmware included, takes the plain pass (generic_main)."""
    import schema_update as S
    called = []
    monkeypatch.setattr(S, "generic_main", lambda target, run, write, force=False, accept_stale=False:
                        called.append(target.stem))
    monkeypatch.setattr(S, "RUN_ROOT", Path("/nowhere") / "ILCE-1M2_fw5.00")
    monkeypatch.setattr(sys, "argv", ["schema_update.py"])
    S.main()
    assert called == ["ILCE-1M2_fw5.00"]


def a1_run(tmp_path: Path, monkeypatch, report: list, proofs: list):
    """The a1 II's full pass (schema_update.main) on a made-up run: a copy of the committed definition in a definitions
    folder of the test's own, the run's camera folder with the sample as every download, pass 1's Focus Area Limit row
    as the definition names its areas, the given report and proofs, no help read and no private help file written. Returns
    (schema_update, the copy's path, a function that runs the pass with --write and returns what it printed)."""
    import schema_update as S
    root = tmp_path / "runs" / A1
    run = a_run(root)
    for d in ("kit2_dial/dat", "kit2_pass1", "kit2_help"):
        (root / d).mkdir(parents=True)
    shutil.copy(SAMPLE, root / "kit2_dial" / "dat" / "00001_x.DAT")
    areas = next(s for s in DOC["settings"] if s["key"] == "global:0x0f46")["values"]
    (root / "kit2_pass1" / "map_all.json").write_text(json.dumps({"rows": [{"path": ["Focus Area Limit"], "kind": "checklist",
        "options": [{"index": v, "label": lab} for v, lab in areas]}]}), encoding="utf-8")
    (run / "report.json").write_text(json.dumps(report), encoding="utf-8")
    (run / "proofs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in proofs), encoding="utf-8")
    defs = tmp_path / "definitions"
    defs.mkdir()
    target = defs / f"{A1}.json"
    shutil.copy(ROOT / "editor" / "definitions" / f"{A1}.json", target)
    # the definition whole, as the kit holds it on the mapper's computer: its private evidence beside the copy
    if EVIDENCE:
        shutil.copy(definitions.evidence_path(definitions.path(A1)), definitions.evidence_path(target))
    monkeypatch.setattr(definitions, "DIR", defs)
    monkeypatch.setattr(S.help_files, "PRIVATE", tmp_path / "private_help")
    monkeypatch.setattr(S.help_files, "write", lambda *a: None)          # the private help file is the owner's
    monkeypatch.setattr(S, "RUN_ROOT", root)
    monkeypatch.setattr(S, "RUN", run)
    monkeypatch.setattr(S, "HELP", root / "kit2_help")
    monkeypatch.setattr(sys, "argv", ["schema_update.py", "--write"])

    def write(capsys):
        S.main()
        return capsys.readouterr().out
    return S, target, write


# a made-up pass 2 of three rows: Metering Mode's carousel (its Spot read with the axis value, which the CAROUSEL table
# names), and Focus Area with Switch V/H AF Area on, the camera level, which proves only part of the kind memory's
# values (an earlier report proved them all)
A1_REPORT = [
    {"row": "Metering Mode", "options": 3, "notices": [],
     "records": {"global:0x0350": {"verdict": "conflict", "proved": {"Multi": 0, "Center": 1, "Spot: Standard": 2},
                                   "linear": None,
                                   "notes": [{"value": 2, "camera": "Spot: Standard", "schema": "Spot", "kind": "conflict"}]}}},
    {"row": "Focus Area [Switch V/H AF Area = AF Point + AF Area, camera level]", "options": 3, "notices": [],
     "records": {"global:0x0e68": {"verdict": "agrees", "proved": {"Wide": 0, "Zone": 1, "Center Fix": 2},
                                   "linear": None, "notes": []}}},
]
A1_PROOFS = [{"path": ["Metering Mode"], "kind": "dialog", "index": i, "label": lab, "applied": True, "changes": []}
             for i, lab in enumerate(["Multi", "Center", "Spot: Standard"])]


@needs_evidence
def test_the_a1_pass_runs_its_tables_on_a_made_up_run(tmp_path, monkeypatch, capsys):
    """schema_update's full pass for the a1 II (main) runs through every table on a made-up run: a table a later name
    shadowed (a note fragment bound to CAROUSEL crashed every --write at CAROUSEL.get, 2026-11-06) fails it. The
    carousel's Spot keeps its own name, without the axis value it was read with."""
    S, target, write = a1_run(tmp_path, monkeypatch, A1_REPORT, A1_PROOFS)
    said = write(capsys)
    assert f"wrote {target}" in said
    doc = definitions.load(target)
    metering = next(s for s in doc["settings"] if s["key"] == "global:0x0350")
    assert dict(metering["values"])[2] == "Spot"


def test_a_rerun_keeps_only_old_values_a_counted_line_still_wrote():
    """kept_proof: of the proof a definition held, a rerun keeps beside the report's only the values a line the report
    counts still wrote (written_values: a hold's option numbered apart in two sessions, whose later line takes its
    place in the report), each listed; never an old menu row (a row the report leaves out, a hand table's proof since
    replaced) nor an old count of samples, nor a value no counted line wrote (an older rule's credit of a start, the
    option a session found: decision 16); an old "inferred" is not kept, nor written from a new proof; a proof of
    another kind replaces the old one; nothing kept from nothing."""
    import schema_update as S
    old = {"run": "r", "date": "d", "menu": ["A", "B"], "values": [0, 1, 2, 5], "inferred": [5]}
    new = {"run": "r", "date": "d", "menu": ["A"], "values": [0, 1], "inferred": [1]}
    got, said = S.kept_proof(old, new, written=frozenset({2}))
    assert got == {"run": "r", "date": "d", "menu": ["A"], "values": [0, 1, 2]}
    assert said == ["1 values"]
    assert S.kept_proof(got, new, written=frozenset({2}))[0] == got      # again: the same
    assert S.kept_proof(old, new)[0]["values"] == [0, 1], "no line wrote 2 or 5"
    plain = {k: v for k, v in new.items() if k != "inferred"}
    assert S.kept_proof(None, new) == (plain, [])
    assert S.kept_proof(old, dict(new, menu=["A", "B"], values=[0, 1, 2, 5]))[1] == []
    samples = {"run": "r", "date": "d", "menu": ["A"], "sampled": {"proofs": 3, "linear": True}}
    assert S.kept_proof(old, samples) == (samples, [])                  # another kind of proof: the new one
    got, said = S.kept_proof(dict(samples, sampled={"proofs": 5, "linear": None}, menu=["A", "B"]), samples)
    assert got == samples and said == [], "no older count, no older row"


def test_no_name_in_schema_update_is_bound_twice():
    """Every table and function of schema_update.py and its parts (kit/writer/) is bound once at module level: a later
    binding shadows the first for every reader (a note fragment bound to CAROUSEL took the carousel table's place,
    2026-11-06), and schema_update.py, which gives every part's names under its old place, imports no name twice. Loop
    names with a leading underscore are a loop's own and are left out; updates in place (|=, [k] =) are not
    bindings."""
    import ast
    import collections

    def names(target):
        if isinstance(target, ast.Name):
            yield target.id
        elif isinstance(target, (ast.Tuple, ast.List)):
            for e in target.elts:
                yield from names(e.value if isinstance(e, ast.Starred) else e)

    def bound_in(path):
        bound = collections.Counter()
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    bound.update(names(target))
            elif isinstance(node, (ast.AnnAssign, ast.For)):
                bound.update(names(node.target))
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                bound[node.name] += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                bound.update((a.asname or a.name).split(".")[0] for a in node.names)
        return bound

    every = {p: bound_in(p) for p in [ROOT / "kit" / "schema_update.py", *sorted((ROOT / "kit" / "writer").glob("*.py"))]}
    assert "main" in every[ROOT / "kit" / "schema_update.py"] and "CAROUSEL" in every[ROOT / "kit" / "writer" / "a1_tables.py"]
    assert {p.name: [n for n, times in b.items() if times > 1 and not n.startswith("_")] for p, b in every.items()} == \
        {p.name: [] for p in every}


@needs_evidence
def test_the_a1_pass_gives_the_same_file_when_run_again(tmp_path, monkeypatch, capsys):
    """"Rerunning gives the same file": the full pass on a made-up run, run twice, writes the same bytes as once. A
    note line is added once, never again on a rerun and never with a stray space (the Focus Area memories' line, the
    Picture Profile stills copies' note: both were added again on every run once their evidence was apart); and of
    the proof the definition held, only a value a counted line still wrote stays when the report does not credit it
    (the kind memory proved all its values before; this report proves three, and a made-up line wrote a fourth), with
    the writer saying so; its other old values and its old menu rows go."""
    wrote = {"path": ["Focus Area"], "kind": "dialog", "index": 5, "label": "Spot: M", "applied": True,
             "changes": [{"key": "global:0x0e68", "before": 0, "after": 5}], "dat": "00001_x.DAT", "base": "00001_x.DAT"}
    S, target, write = a1_run(tmp_path, monkeypatch, A1_REPORT, A1_PROOFS + [wrote])
    before = {s["key"]: s for s in DOC["settings"]}
    said = write(capsys)
    once = (target.read_bytes(), definitions.evidence_path(target).read_bytes())
    assert write(capsys) and (target.read_bytes(), definitions.evidence_path(target).read_bytes()) == once
    doc = definitions.load(target)
    by = {s["key"]: s for s in doc["settings"]}
    for k in ("global:0x0e68", "global:0x05c5[0]"):
        assert by[k]["note"] == before[k]["note"], k
        assert by[k].get("note_evidence") == before[k].get("note_evidence"), k
    assert not [k for k, s in by.items() if s.get("note", "") != s.get("note", "").strip()
                and before[k].get("note") == before[k].get("note", "").strip()]
    kind = by["global:0x0e68"]["proved"]
    assert before["global:0x0e68"]["proved"]["values"] == [0, 1, 2, 3, 4, 5, 6] and kind["values"] == [0, 1, 2, 5]
    assert kind["menu"] == ["Focus Area [Switch V/H AF Area = AF Point + AF Area, camera level]"]
    assert "written_with" not in by["global:0x0e68"]         # the records its proof wrote with it: the report's
    assert "kept  global:0x0e68" in said


# ---------------------------------------------------------------- what --write refuses, and what backs each name

def test_snap_never_crosses_a_digit():
    """snap gives a reading the schema's name for it when the text is clearly the same, never one whose numbers differ:
    "Custom Look 1" and "Custom Look 2" are alike at 0.909 (2026-11-07, the reviewer's case)."""
    import schema_update as S
    assert S.snap("Custom Look 2", ["Custom Look 1"]) == "Custom Look 2"
    assert S.snap("Custom Look 2", ["Custom Look 1", "Custom Look 2"]) == "Custom Look 2"
    assert S.snap("My Menu 12", ["My Menu 1", "My Menu 2"]) == "My Menu 12"
    assert S.snap("Subject Reccgnition AF", ["Subject Recognition AF"]) == "Subject Recognition AF"


# a made-up report of one row, a KEEP_LABELS record whose label stands against the camera's reading (Proxy Rec.
# Settings, which the a1 II's accepted file does not list)
GATE_REPORT = [{"row": "Proxy Rec. Settings", "options": 2, "notices": [],
                "records": {"global:0x0284": {"verdict": "conflict", "proved": {"9M": 1, "16M": 2}, "linear": None,
                                              "notes": [{"value": 1, "camera": "9M", "schema": "XAVC HS HD 9M",
                                                         "kind": "conflict"}]}}}]


@needs_evidence
def test_the_gate_refuses_an_unaccepted_conflict_and_passes_an_accepted_one(tmp_path, monkeypatch, capsys):
    """--write refuses (exit 1, each question listed) while the report holds a conflict the writer leaves standing that
    the camera's accepted file does not list; with an entry for it, it writes; --force writes anyway, loudly."""
    S, target, write = a1_run(tmp_path, monkeypatch, GATE_REPORT, A1_PROOFS)
    accepted = tmp_path / "accepted.json"
    monkeypatch.setattr(S.writer.gate, "accepted_file", lambda camera: accepted)     # the gate reads it there
    before = target.read_bytes()
    with pytest.raises(SystemExit) as stop:
        write(capsys)
    said = capsys.readouterr().out
    assert "refused" in str(stop.value) and "conflict" in said and "global:0x0284" in said
    assert target.read_bytes() == before                                  # nothing written
    monkeypatch.setattr(sys, "argv", ["schema_update.py", "--write", "--force"])
    said = write(capsys)
    assert "--force" in said and f"wrote {target}" in said
    accepted.write_text(json.dumps({"model": "ILCE-1M2", "firmware": "4.00", "accepted": [
        {"kind": "conflict", "key": "global:0x0284", "value": 1, "why": "the format names it", "date": "2026-11-07"}]}),
        encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["schema_update.py", "--write"])
    said = write(capsys)
    assert "every one accepted" in said and f"wrote {target}" in said


def test_the_gate_lists_an_entry_that_answers_no_question(tmp_path, monkeypatch, capsys):
    """An accepted entry answers a question the report holds now; one that answers none (its question settled since)
    is listed to be taken out, so it hides no later question on its record. It does not stop the writer."""
    import schema_update as S
    accepted = tmp_path / "accepted.json"
    accepted.write_text(json.dumps({"model": "M", "firmware": "1.00", "accepted": [
        {"kind": "conflict", "key": "global:0x0001", "why": "a hand rule names it", "date": "2026-11-08"},
        {"kind": "name dispute", "key": "global:0x0002", "value": 20, "label": "I0.0", "why": "settled", "date": "2026-11-07"}]}),
        encoding="utf-8")
    monkeypatch.setattr(S.writer.gate, "accepted_file", lambda camera: accepted)
    assert S.gate([{"kind": "conflict", "key": "global:0x0001", "row": "R", "value": 1}], "M_fw1.00", False, False)
    said = capsys.readouterr().out
    assert "1 entries of" in said and "take them out" in said and "global:0x0002" in said and "global:0x0001 " not in said
    assert "every one accepted" in said


def test_the_gate_reads_every_kind_and_a_missing_section_as_empty():
    """questions(): the report's records not one to one, new records the writer did not add, name disputes and
    carried-over values outside a hand rule; a report without those sections (an older pass2_report) has none. An
    accepted entry covers its kind and key, and its value and label where it names them."""
    import schema_update as S
    report = [{"row": "R", "records": {
        "global:0x0001": {"verdict": "conflict", "proved": {}, "notes": [{"kind": "not one to one", "value": None}]},
        "global:0x0002": {"verdict": "new", "proved": {"A": 1}, "notes": []},
        "global:0x0003": {"verdict": "agrees", "proved": {"A": 1}, "notes": [],
                          "name_disputes": [{"value": 1, "label": "A", "shown": None, "vlm": "B", "frame": "f"}]}},
        "carried_over": [{"key": "global:0x0004", "label": "X", "value": 7, "hand_rule": False},
                         {"key": "global:0x0005", "label": "X", "value": 7, "hand_rule": True}]}]
    got = S.questions(report, [], frozenset())
    assert [(q["kind"], q["key"]) for q in got] == [("not one to one", "global:0x0001"), ("new", "global:0x0002"),
                                                    ("name dispute", "global:0x0003"), ("carried over", "global:0x0004")]
    assert [q["kind"] for q in S.questions(report, [], frozenset({"global:0x0002", "global:0x0003"}))].count("new") == 0
    # a proved record the definition lacks after the pass is new, whatever the report said against an older one
    assert ("new", "global:0x0003") in [(q["kind"], q["key"]) for q in S.questions(report, [], frozenset({"global:0x0002"}))]
    assert S.questions([{"row": "R", "records": {"global:0x0003": {"verdict": "agrees", "proved": {}, "notes": []}}}]) == []
    q = got[2]
    assert S.accepts({"kind": "name dispute", "key": "global:0x0003"}, q)
    assert S.accepts({"kind": "name dispute", "key": "global:0x0003", "value": 1, "label": "A"}, q)
    assert not S.accepts({"kind": "name dispute", "key": "global:0x0003", "value": 2}, q)
    assert not S.accepts({"kind": "conflict", "key": "global:0x0003"}, q)


def test_the_accepted_file_is_private_whole():
    """Each accepted entry is a ruling on one mapping's report, which another owner's mapping need not raise (decision
    16): the file is the mapper's, in private/evidence/<model>_fw<fw>/, never in a camera's data folder; the pull
    request carries the gate's count instead."""
    import schema_update as S
    assert not list((ROOT / "data").glob("*/accepted_*.json"))
    assert S.accepted_file(A1) == definitions.EVIDENCE_DIR / A1 / f"accepted_{A1}.json"


@pytest.mark.skipif(not (definitions.EVIDENCE_DIR / A1 / f"accepted_{A1}.json").exists(),
                    reason="the accepted file is the mapper's own, private whole (private/evidence/, not here)")
def test_the_accepted_file_matches_its_schema_and_explains_each_entry():
    """The a1 II's accepted file against its JSON Schema, each entry with why; it holds no carried-over value (the
    value a record kept may be the camera's own setting, decision 16)."""
    import jsonschema
    import schema_update as S
    p = S.accepted_file(A1)
    doc = json.loads(Path(p).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(json.loads(Path(ROOT / "schemas" / "accepted.schema.json").read_text(encoding="utf-8"))).validate(doc)
    assert doc["$schema"] == "../../../schemas/accepted.schema.json"
    assert all(e["why"].strip() for e in doc["accepted"])
    assert not [e for e in doc["accepted"] if e["kind"] == "carried over" and "value" in e]
    # Exposure Std. Adjust's five (0x0346-0x034e) went on 2026-11-08: its sixths are a scale sampled on a line now
    # (sampled_scale), whose proofs name no value, so no conflict of theirs is left to accept
    assert {e["key"] for e in doc["accepted"] if e["kind"] == "conflict"} == {
        "global:0x16ae", "global:0x0445[0]", "global:0x0451[0]",
        # the ratings' second copies, written by Rating Set(Custom Key)'s boxes and the Playback Filter Condition's
        # Rating grid alike (2026-11-07)
        "global:0x16bd", "global:0x16be", "global:0x16bf", "global:0x16c0", "global:0x16c1",
        # Playback Filter Condition's boxes, flags and star boxes, which its options tick and clear while naming the
        # condition's value (KEEP_LABELS): the report read them against the definition's words once they were in it
        # (2026-11-08)
        *(f"global:0x{r:04x}" for r in (*range(0x1282, 0x1288), 0x1290, *range(0x1293, 0x1299), 0x12ba,
                                        *range(0x12bd, 0x12c3), 0x16c2))}
    # the Registered AF area kinds' conflicts (0x0e7a, 0x0e7c, 0x0e7e) went on 2026-11-11: the report reads each area's
    # name against its kind's as wording now ("Spot: L" for "Spot"), no conflict, and KEEP_LABELS still keeps the kinds'
    # names. The hold Exposure Comp. disputes on slots 3 and 4 (0x0bf9[2], [3]) went on 2026-11-08, and the ISO readouts'
    # (0x0fde, 0x0fe0) on 2026-11-11: the report holds no such question now, and an entry that answers none is taken
    # out (the gate lists it)
    assert sorted({e["key"] for e in doc["accepted"] if e["kind"] == "name dispute"}) == [
        "global:0x0336", "global:0x0c25[2]", "global:0x0c25[3]"]


@needs_evidence
def test_a_record_not_one_to_one_loses_its_proof_and_is_disputed(tmp_path, monkeypatch, capsys):
    """A record the report finds not one to one keeps no proof from before (the reviewer's hole: it kept its old one
    silently): it is marked disputed, and a later report without the dispute takes the mark away."""
    assert DOC_BY["global:0x0350"].get("proved")
    report = [{"row": "Metering Mode", "options": 3, "notices": [],
               "records": {"global:0x0350": {"verdict": "conflict", "proved": {"Multi": 0, "Center": 0}, "linear": None,
                                             "notes": [{"value": None, "camera": "Multi, Center", "schema": None,
                                                        "kind": "not one to one"}]}}}]
    S, target, write = a1_run(tmp_path, monkeypatch, report, A1_PROOFS)
    monkeypatch.setattr(sys, "argv", ["schema_update.py", "--write", "--force"])
    write(capsys)
    got = next(s for s in definitions.load(target)["settings"] if s["key"] == "global:0x0350")
    assert "proved" not in got and got["disputed"] is True
    doc = {"settings": [dict(got), {"key": "global:0x0001", "name": "x", "disputed": True}]}
    S.disputed_out(doc, {"global:0x0350"})
    assert doc["settings"][0]["disputed"] and "disputed" not in doc["settings"][1]


DOC_BY = {s["key"]: s for s in DOC["settings"]}
IN_PROOF_ONLY = ("derived", "sampled", "schema kept", "hand table", "counted")
# name sources the kit no longer writes, which an editor may still know so that an older definition opens: "held"
# (2026-11-10, decision 16), until the editor drops it
RETIRED_SOURCES = {"held"}


def camera_sources() -> set:
    """The name sources the kit takes for the camera's word (camkit.definitions.ESTABLISHING): a value so named is
    among a lean proof's values, which is all the editor reads."""
    return set(definitions.ESTABLISHING)


def lay_offered(s: dict, camera: set = frozenset()) -> set:
    """The codes an editor offers outside Expert mode (Setting::offered(false)) from the setting as the public file
    holds it (its proof lean: definitions.lean_proof gives a whole proof's, or a lean one's own): every listed code but
    one the menus never offer, where the setting has no proof, or its scale is sampled on a line, or its lean proof
    lists the code."""
    p = definitions.lean_proof(s["proved"]) if s.get("proved") else None
    never = {n["value"] for n in s.get("not_offered") or [] if not n.get("held")}
    codes = [v for v, _ in s.get("values") or [] if v not in never]
    if not p or (p.get("sampled") or {}).get("linear") is True:
        return set(codes)
    return {v for v in codes if v in (p.get("values") or [])}


def test_the_name_sources_are_one_list():
    """The name sources (proved.names, evidence in the private file) are the kit's NAME_SOURCES: those it takes for the
    camera's word (definitions.ESTABLISHING), whose values a lean proof lists, and the two it does not ("schema kept",
    "counted"). The editor holds no list of them and the definition's schema names none: a public definition says
    which values a proof checked, never where a name came from (decision 16). A source the kit adds later fails here
    before it can hide values or offer them silently."""
    import schema_update as S
    assert set(S.NAME_SOURCES) == set(definitions.ESTABLISHING) | {"schema kept", "counted"}
    assert not set(definitions.ESTABLISHING) & ({"schema kept", "counted"} | RETIRED_SOURCES)
    rs = (ROOT / "editor" / "src" / "schema.rs").read_text(encoding="utf-8")
    assert "CAMERA_SOURCES" not in rs and "name_source_words" not in rs
    schema = (ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8")
    assert '"names"' not in json.dumps(json.loads(schema)["$defs"]["setting"])


def test_no_disputed_setting_keeps_a_proof():
    """A setting the report found not one to one (disputed) carries no proof in the public file either: an editor
    would offer what a disputed proof listed."""
    assert not [s["key"] for s in PUB["settings"] if s.get("disputed") and s.get("proved")]


@needs_evidence
def test_every_proved_value_says_what_backs_its_name():
    """proved.names in the shipped definition: every proved value of every setting has one of the sources, and a value
    no proof saw has one only where a rule, a hand table or a sampled scale named it."""
    import schema_update as S
    assert set(S.NAME_SOURCES) == {"two readers", "one reader", "vision model", "schema kept", "hand table", "counted",
                                   "derived", "sampled"}
    missing, wrong = [], []
    for s in DOC["settings"]:
        p = s.get("proved") or {}
        names = p.get("names") or {}
        for v in p.get("values") or []:
            if names.get(str(v)) not in S.NAME_SOURCES:
                missing.append((s["key"], v, names.get(str(v))))
        wrong += [(s["key"], v, src) for v, src in names.items()
                  if int(v) not in (p.get("values") or []) and src not in IN_PROOF_ONLY]
    assert not missing, missing[:10]
    assert not wrong, wrong[:10]
    assert not [s["key"] for s in DOC["settings"] if s.get("disputed") and s.get("proved")]
    counts = {src for s in DOC["settings"] for src in ((s.get("proved") or {}).get("names") or {}).values()}
    assert {"two readers", "one reader", "hand table", "derived"} <= counts


def test_with_names_ranks_its_sources():
    """with_names: a hand table's or a kept schema label over the readers; the readers over what the definition said;
    a rule's copy only where nothing read the value; a sampled scale's values as sampled. A value no option was seen
    to write (an old "inferred", a report's "inferred" label) is named by its readers like any other, and an old
    "held" is not kept: either told the value the record held when its proof began (decision 16)."""
    import schema_update as S
    s = {"key": "k", "values": [[0, "A"], [1, "B"], [2, "C"], [3, "D"], [4, "E"], [5, "F"]],
         "proved": {"run": "r", "date": "d", "values": [0, 1, 2, 3, 5], "inferred": [3, 5],
                    "names": {"2": "two readers", "5": "held"}}}
    S.with_names(s, {0: "one reader", 3: "two readers"}, {1: "hand table"}, {0: "derived", 4: "derived"})
    assert s["proved"]["names"] == {"0": "one reader", "1": "hand table", "2": "two readers", "3": "two readers",
                                    "4": "derived", "5": "one reader"}
    r = collections.defaultdict(dict)
    S.note_readers(r, "k", {"proved": {"A": 0, "B": 1, "C": 2, "D": 3}, "inferred": ["C", "D"],
                            "names": {"A": "two readers", "B": "one reader (map)", "C": "two readers", "D": "held"}})
    S.note_readers(r, "k", {"proved": {"B": 1}, "names": {"B": "disputed"}})
    assert r["k"] == {0: "two readers", 1: "one reader", 2: "two readers", 3: "one reader"}
    sampled = {"key": "n", "values": [[0, "0"], [5, "5"]], "proved": {"run": "r", "date": "d", "sampled": {"proofs": 2}}}
    S.with_names(sampled, {}, {}, {})
    assert sampled["proved"]["names"] == {"0": "sampled", "5": "sampled"}


def test_no_setting_says_which_values_no_option_wrote():
    """No `proved.inferred` and no name source "held" in the shipped definition, nor in one the writer passes: a
    definition never marks which values no option was seen to write (decision 16). without_held takes such a mark out
    on every write (from_data), the value
    staying proved and its name "one reader"; the definition's schema refuses both, naming the field or the source."""
    import jsonschema
    import schema_update as S
    assert not [s["key"] for s in DOC["settings"] if "inferred" in (s.get("proved") or {})]
    assert not [s["key"] for s in DOC["settings"] if "held" in ((s.get("proved") or {}).get("names") or {}).values()]
    doc = {"settings": [{"key": "a", "proved": {"run": "r", "date": "d", "values": [0, 1], "inferred": [1],
                                                "names": {"0": "two readers", "1": "held"}}},
                        {"key": "b", "proved": {"run": "r", "date": "d", "values": [0]}}, {"key": "c"}]}
    assert S.without_held(doc) == 1
    assert doc["settings"][0]["proved"] == {"run": "r", "date": "d", "values": [0, 1],
                                            "names": {"0": "two readers", "1": "one reader"}}
    assert S.without_held(doc) == 0                                       # again: nothing
    schema = json.loads(Path(ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))
    setting = jsonschema.Draft202012Validator(schema["$defs"]["setting"])
    one = {"key": "global:0x0001", "area": "global", "id": 1, "name": "n", "tab": "t", "group": "g",
           "proved": {"values": [0, 1]}}
    assert setting.is_valid(one)
    errors = list(setting.iter_errors({**one, "proved": {**one["proved"], "inferred": [1]}}))
    assert errors and "inferred" in errors[0].message, [e.message for e in errors]
    # a lean definition names no name source at all, "held" or other (they are evidence, in the private file)
    errors = list(setting.iter_errors({**one, "proved": {**one["proved"], "names": {"0": "two readers", "1": "held"}}}))
    assert errors and "names" in errors[0].message, [e.message for e in errors]


def test_no_setting_carries_a_list_of_the_values_camera_files_held(capsys):
    """No `observed` in the shipped definition, nor in one the writer passes: the old schema's lists came from the
    camera's downloads, so beside the proofs' values they held the owner's own settings (decision 16; until 2026-11-08,
    40 list settings held one or two such values, a dial's function and a memory's exposure mode among them). An
    editor reads what a proof established from `proved` (docs/DATA_CONTRACTS.md, "What the editor offers outside
    Expert mode"); without_observed takes an old list out on every write, and the definition's schema refuses a
    setting that carries one, naming the field."""
    import jsonschema
    import schema_update as S
    assert not [s["key"] for s in DOC["settings"] if "observed" in s]
    doc = {"settings": [{"key": "a", "observed": [1, 2]}, {"key": "b", "observed": []}, {"key": "c"}]}
    assert S.without_observed(doc) == 2 and doc == {"settings": [{"key": "a"}, {"key": "b"}, {"key": "c"}]}
    assert "observed: 2 settings' lists" in capsys.readouterr().out
    schema = json.loads(Path(ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))
    setting = jsonschema.Draft202012Validator(schema["$defs"]["setting"])
    one = {"key": "global:0x0001", "area": "global", "id": 1, "name": "n", "tab": "t", "group": "g"}
    assert setting.is_valid(one)
    errors = list(setting.iter_errors({**one, "observed": [0]}))
    assert errors and "observed" in errors[0].message, [e.message for e in errors]


FN_PICKERS = {"global:0x0445": ("Fn Menu Settings", 72), "global:0x0451": ("Fn Menu Settings", 72),
              "global:0x12e7": ("Fn Menu Settings (playback)", 33)}


def test_each_fn_menu_place_offers_the_functions_its_list_has_in_the_public_file():
    """The public file alone (what the editor reads): every Fn Menu place of a group offers outside Expert mode the
    same functions, as many as its picker lists on the camera (72 for stills and movie, 33 for playback), and "Regist.
    Face Priority" once."""
    for rec, (_screen, n) in FN_PICKERS.items():
        places = [s for k, s in PUB_BY.items() if k.startswith(rec + "[")]
        walked = set().union(*({v for v in (s.get("proved") or {}).get("values") or []} for s in places))
        assert len(places) == 12 and len(walked) == n, (rec, len(walked))
        for s in places:
            assert lay_offered(s) == walked, (s["key"], sorted(lay_offered(s) ^ walked))
            assert [lab for v, lab in s["values"] if v in walked].count("Regist. Face Priority") <= 1, s["key"]


@needs_evidence
def test_each_fn_menu_place_offers_the_functions_its_list_has():
    """A Fn Menu place offers outside Expert mode exactly the functions its picker lists on the camera: the codes the
    group's walks proved (the stills and movie lists 72, the playback list 33, its full slot's walk having proved 32
    and Upper 4's the 33rd, Send), named in every place of the group. Not the Custom Key codes a spelling fix once
    named "hand table" (767, 832, 847, 1008, 1171, 2499: 192 values no Fn place proved, 2026-11-08), so "Regist. Face
    Priority" is offered once, as 970. Where runs/ is on this computer, the table walk's lists say how many."""
    camera = camera_sources()
    by = {s["key"]: s for s in DOC["settings"]}
    for rec, (_screen, n) in FN_PICKERS.items():
        places = [s for k, s in by.items() if k.startswith(rec + "[")]
        walked = set().union(*({v for v in (s.get("proved") or {}).get("values") or []} for s in places))
        assert len(places) == 12 and len(walked) == n, (rec, len(walked))
        for s in places:
            assert lay_offered(s, camera) == walked, (s["key"], sorted(lay_offered(s, camera) ^ walked))
            labels = [lab for v, lab in s["values"] if v in walked]
            assert labels.count("Regist. Face Priority") <= 1, s["key"]
            assert all(s["proved"]["names"].get(str(v)) == "schema kept" for v in (767, 832, 847, 1008, 1171, 2499)
                       if v in dict(map(tuple, s["values"])) and v not in walked), s["key"]
    tables = ROOT / "runs" / A1 / "kit2_tables" / "tables.json"
    if tables.exists():
        t = json.loads(tables.read_text(encoding="utf-8"))
        for screen, n in set(FN_PICKERS.values()):
            cells = t[screen].get("cells") or [c for p in t[screen].get("pages") or [] for c in p.get("items") or []]
            assert cells and all(c.get("wrapped") and len(c["options"]) == n for c in cells), screen


PLAYBACK_KEYS = ("global:0x0441", "global:0x043a", "global:0x043b", "global:0x043c", "global:0x043d", "global:0x043e",
                 "global:0x0442", "global:0x1244")


def test_each_playback_custom_key_offers_the_functions_its_list_has_in_the_public_file():
    """The public file alone: each playback Custom Key (AEL, AF-ON, MOVIE, Custom 1-5) offers outside Expert mode the 38
    functions the AEL key's full walk proved, and Rating's copy holds only its own two values."""
    walked = set(PUB_BY["global:0x0441"]["proved"]["values"])
    assert len(walked) == 38
    for k in PLAYBACK_KEYS:
        assert lay_offered(PUB_BY[k]) == walked, (k, sorted(lay_offered(PUB_BY[k]) ^ walked))
    assert len(PUB_BY["global:0x16bd"]["values"]) == 2, "Rating's copy: ticked or not, no key function"


@needs_evidence
def test_each_playback_custom_key_offers_the_functions_its_list_has():
    """A playback Custom Key (AEL, AF-ON, MOVIE, Custom 1-5) offers outside Expert mode exactly the 38 functions its
    picker lists on the camera: the codes the group's walks proved, lent from the AEL key's full walk to the keys
    sampled against it. picker_groups once took a slot's record from one proof's first change, and the AEL key's
    Rating option writes Rating's copy (0x16bd) first, so the group was tied to Rating's copy and the keys took no
    lending; Rating's copy holds only its own two values. The keys sampled against the AEL key list none of their
    samples, which were stepped from the function each key held (proved.sampled.from_start, decision 16). Where runs/
    is on this computer, the table walk's lists say how many."""
    camera = camera_sources()
    keys = [DOC_BY[k] for k in PLAYBACK_KEYS]
    walked = set(DOC_BY["global:0x0441"]["proved"]["values"])
    assert len(walked) == 38
    for s in keys:
        assert s["key"] == "global:0x0441" or (s["proved"]["sampled"].get("from_start") and "values" not in s["proved"]), \
            s["key"]
    for s in keys:
        assert lay_offered(s, camera) == walked, (s["key"], sorted(lay_offered(s, camera) ^ walked))
    assert len(DOC_BY["global:0x16bd"]["values"]) == 2, "Rating's copy: ticked or not, no key function"
    tables = ROOT / "runs" / A1 / "kit2_tables" / "tables.json"
    if tables.exists():
        t = json.loads(tables.read_text(encoding="utf-8"))["Custom Key Setting"]
        cells = [c for p in t["pages"] for c in p["items"] if c.get("opens") == "picker"]
        named = {"AEL Button", "AF-ON Button", "MOVIE Button", *(f"Custom Button {i}" for i in range(1, 6))}
        mine = [c for c in cells if c.get("key") in named]
        assert len(mine) == 8 and all(c["wrapped"] and len(c["options"]) == 38 for c in mine)


def axis_rows_off_their_owner(doc: dict) -> list:
    """Every proved.menu row "<item> / <option> [ctx]" whose option is a value of a setting proved through that row
    (the camera's words: case and OCR slips aside, and a label "<option> (…)" counts) when nothing shows the option
    owns an axis there: no setting proved through the row labels a value "<option>: …" or has it as an option tree's
    main option with choices, and no setting proved through the row is a record of the axis's own, one that does not
    hold the option among its values (Drive Mode / DRO Bracket: the bracket's Hi and Lo are a record apart from Drive
    Mode's, placed under DRO Bracket or not yet). Such an option is the value the axis stood on when it was walked,
    the camera's own setting then (decision 16). On the definition alone the test cannot tell an axis that stood on a
    value and also wrote a record apart from an owner with a record of its own; the proofs can (the runs/ part)."""
    from writer.labels import clean

    def said(lab, x):
        a, b = clean(str(lab)).lower(), clean(x).lower()
        return a == b or a.startswith(b + " (")
    through = collections.defaultdict(list)
    for s in doc["settings"]:
        for r in (s.get("proved") or {}).get("menu") or []:
            m = re.fullmatch(r"(.*?) / ([^\[]*?)( \[.*\])?", r)
            if m:
                through[(m[1], m[2])].append(s)
    out = []
    for (item, x), ss in sorted(through.items()):
        holders = [s for s in ss if any(said(lab, x) for _, lab in s.get("values") or [])]
        if not holders:
            continue
        owns = any(any(clean(str(lab)).lower().startswith(clean(x).lower() + ":") for _, lab in s.get("values") or [])
                   or any(n.get("label") == x and n.get("options") for n in s.get("option_tree") or []) for s in ss)
        if not owns and len(holders) == len(ss):
            out.append(f"{item} / {x}")
    return out


def test_no_proof_row_is_named_after_the_value_its_axis_stood_on():
    """proved.menu names an axis row by the carousel option owning the axis (Focus Area / Spot, its sizes; Drive Mode /
    DRO Bracket, Hi and Lo), never by the value the axis stood on when it was walked: ISO AUTO Min. SS's speeds are one
    line of values, and its row was named after the one it stood on, the camera's own setting then (decision 16).
    The writer names such a row by its item alone (axis_value_rows, menu_row: from the proofs, an option that is one
    of its axis's own labels), before kept_proof compares a rerun's rows with the definition's. The first part states
    the rule on the definition alone, so it holds without runs/ (axis_rows_off_their_owner says what it cannot see);
    where runs/ is on this computer, the proofs' own axis rows are checked too."""
    from writer import proofs as S
    assert axis_rows_off_their_owner(DOC) == []
    proofs_file = ROOT / "runs" / A1 / "kit2_pass2" / "proofs.jsonl"
    if proofs_file.exists():
        stood = S.axis_value_rows(jsonl.read(proofs_file, bad="skip"))
        menus = [r for s in DOC["settings"] for r in (s.get("proved") or {}).get("menu") or []]
        assert stood and not [r for r in menus for item, x in stood if r == f"{item} / {x}" or r.startswith(f"{item} / {x} [")]
    proofs = [{"kind": "axis", "path": ["Speed"], "option": "Mid", "label": lab} for lab in ("Slow", "mid", "Fast")] + \
             [{"kind": "axis", "path": ["Area"], "option": "Spot", "label": f"Spot: {lab}"} for lab in ("S", "L")]
    rows = S.axis_value_rows(proofs)
    assert rows == {("Speed", "Mid")}, "a made-up line of values, its label spelled apart; Spot owns its sizes"
    assert S.menu_row("Speed / Mid [Mode A]", rows) == "Speed [Mode A]" and S.menu_row("Speed / Mid", rows) == "Speed"
    assert S.menu_row("Area / Spot [Mode A]", rows) == "Area / Spot [Mode A]"
    doc = {"settings": [{"key": "a", "values": [[0, "Slow"], [1, "Mid (default)"], [2, "Fast"]],
                         "proved": {"menu": ["Speed / Mid [Mode A]", "Speed [Mode A]"]}},
                        {"key": "b", "values": [[0, "Single"], [1, "Spot"]], "proved": {"menu": ["Meter / Spot"]}},
                        {"key": "c", "values": [[0, "Small"], [1, "Large"]], "proved": {"menu": ["Meter / Spot"]}}]}
    assert axis_rows_off_their_owner(doc) == ["Speed / Mid"], "Spot's sizes, a record apart, unplaced: no flag"
    assert S.with_menu_rows(doc, rows) == 1 and doc["settings"][0]["proved"]["menu"] == ["Speed [Mode A]"]
    assert axis_rows_off_their_owner(doc) == [] and S.with_menu_rows(doc, rows) == 0
    # a rerun: the report still names the row after the value, the definition by its item; renamed before kept_proof,
    # the two meet and nothing is "kept from the definition"
    new = {"run": "r", "date": "d", "menu": sorted({S.menu_row(r, rows) for r in ["Speed / Mid [Mode A]"]}), "values": [0]}
    out, kept = S.kept_proof({"run": "r", "date": "d", "menu": ["Speed [Mode A]"], "values": [0]}, new)
    assert kept == [] and out["menu"] == ["Speed [Mode A]"]


def test_a_context_the_runs_reworded_renames_the_row_the_definition_kept(monkeypatch):
    """A proof's context reworded in the runs (a state as found, decision 16: session B's hand-recorded line named the
    slot Recording Media was on, 2026-11-09) leaves the definition's old row kept beside the new one, for kept_proof
    keeps what a report does not show; menu_row puts every row in the new words (CONTEXT_WORDS, from the camera's
    tables), so with_menu_rows renames the kept one and the two meet. The shipped definition holds no row in the old
    words. Made-up rows."""
    from writer import a1_tables
    from writer import proofs as S
    monkeypatch.setattr(S, "CONTEXT_WORDS", dict(a1_tables.CONTEXT_WORDS))
    doc = {"settings": [{"key": "a", "proved": {"menu": ["Switch [Mode A, Recording Media Slot 2]",
                                                         "Switch [Mode A, Recording Media on one slot]"]}}]}
    assert S.with_menu_rows(doc, frozenset()) == 1
    assert doc["settings"][0]["proved"]["menu"] == ["Switch [Mode A, Recording Media on one slot]"]
    assert S.menu_row("Switch [Recording Media: Slot 2]", frozenset()) == "Switch [Recording Media: Slot 2]", \
        "a test state the tables name as such stays"
    assert S.menu_row("Balance [S&Q mode (S&Q Motion)]", frozenset()) == "Balance [S&Q mode]", "either family mode"
    assert S.menu_row("Balance [Movie mode, PAL]", frozenset()) == "Balance [Movie mode, PAL]"
    assert S.menu_row("Switch [Mode A, Recording Media Sort Recording]", frozenset()) == \
        "Switch [Mode A, Recording Media on both slots]", "either two-slot state"
    assert S.menu_row("Switch [Mode A, Recording Media Simult. Recording]", frozenset()) == \
        "Switch [Mode A, Recording Media on both slots]", "either two-slot state"
    menus = [r for s in DOC["settings"] for r in (s.get("proved") or {}).get("menu") or []]
    assert not [r for r in menus for p in a1_tables.CONTEXT_WORDS if re.search(p, r)]


def test_no_public_note_says_it_read_a_value_off_a_file():
    """No public note says it read a value off a file ("baseline value", as Image Jump's dials once did): such a value
    is the owner's own (decision 16)."""
    assert not [s["key"] for s in PUB["settings"] if "baseline value" in (s.get("note") or "")]


@needs_evidence
def test_no_proof_or_note_is_the_value_a_run_began_on():
    """Decision 16 on three older entries (review 5, 2026-11-09): the ISO readouts 0x0fde/0x0fe0 list the two ISOs set,
    not the one kit2_alone began on and put back; the holds' bracket copies 0x0e80/0x0e84 list the registrations of
    live settings set by a file, not the first ones, which copied the live settings as the camera was found; and no
    note says it read a value off a file ("baseline value", as Image Jump's dials once did). The run files are read
    where runs/ is on this computer."""
    from camkit import camset
    by = {s["key"]: s for s in DOC["settings"]}
    assert not [s["key"] for s in DOC["settings"] if "baseline value" in (s.get("note") or "")]
    alone = ROOT / "runs" / A1 / "kit2_alone" / "dat" / "00001_before.DAT"
    if alone.exists():
        start = camset.read(alone)
        for k in ("global:0x0fde", "global:0x0fe0"):
            assert start.get(0, int(k[-4:], 16)).value() not in by[k]["proved"]["values"], k
    proofs = ROOT / "runs" / A1 / "kit2_pass2" / "proofs.jsonl"
    if proofs.exists():
        first = {}
        for r in jsonl.read(proofs, bad="skip"):
            for c in r.get("changes") or []:
                first.setdefault(c["key"], c["before"])
        for hold, live in (("global:0x0e80", "global:0x04c6"), ("global:0x0e84", "global:0x04c8")):
            codes = sorted(v for v, _ in by[live]["values"])
            if first.get(live) in codes:
                assert codes.index(first[live]) not in by[hold]["proved"]["values"], (hold, "the live setting as found")


def test_the_hold_exposure_comp_offers_only_what_its_proofs_chose():
    """A Recall Custom hold's Exposure Comp. (0x0bf9[0..2]) offers outside Expert mode only the codes its proofs chose
    while the live Exposure Comp. (0x0340) is not proved in full: EV_DOWN_FROM_20 names the others by counting quarter
    stops, as the live list's thirds and halves are, which no line rule may infer (every value must be seen), so they
    are "counted", no camera's word. Once the live list is proved in full, hold_tables names them from it."""
    camera = camera_sources()
    by = {s["key"]: s for s in DOC["settings"]}
    live = by["global:0x0340"]
    if set(live["proved"].get("values") or []) >= {v for v, _ in live["values"]}:
        return                                                     # Session B done: the live table names them
    for i in range(3):
        s = by[f"global:0x0bf9[{i}]"]
        chose = set(s["proved"]["values"])
        assert lay_offered(s, camera) == chose, s["key"]
        assert {s["proved"]["names"][str(v)] for v, _ in s["values"] if v not in chose} == {"counted"}, s["key"]


def test_squashed_compares_without_case_or_spaces():
    """squashed: a menu's refusal names the option as the camera showed it, the list as a reader read it ("Black &
    White" refused, "Black&White" listed): compared without case or spaces they are one, another name is not."""
    import schema_update as S
    assert S.squashed("Black & White") == S.squashed("black&white") and S.squashed("B&W") != S.squashed("Black&White")


@needs_evidence
def test_a_refusal_matches_its_value_whatever_the_spaces():
    """A menu's refusal names the option as the camera showed it, the list as a reader read it: "Black & White"
    refused, "Black&White" listed (PP10's Color Mode). squashed compares them without case or spaces, so the refusal
    (menu_blocked, evidence) carries its value."""
    for k in ("global:0x073b[9]", "global:0x0751[9]"):
        s = DOC_BY[k]
        (b,) = [b for b in s["menu_blocked"] if b["label"] == "Black & White"]
        assert b["value"] == 6 and dict(map(tuple, s["values"]))[6] == "Black&White", (k, b)


def test_every_my_menu_slot_can_be_emptied_outside_expert_mode_in_the_public_file():
    """The public file alone: in every one of My Menu's 42 slots the camera file's empty code (camera.my_menu.empty) is
    "(empty)" and among the values its proof checked, so an editor offers it outside Expert mode and a person can empty
    a place; each slot's note says what shows it on the camera."""
    my = PUB["camera"]["my_menu"]
    slots = [s for s in PUB["settings"] if s.get("area") == "global" and s.get("id") in my["records"]
             and s.get("index") is not None]
    assert len(slots) == 42 and my["empty"] == 2
    for s in slots:
        assert [my["empty"], "(empty)"] in s["values"], s["key"]
        assert my["empty"] in lay_offered(s), s["key"]
        assert "An empty place stores 2." in s["note"], s["key"]


@needs_evidence
def test_every_my_menu_slot_can_be_emptied_outside_expert_mode():
    """My Menu's empty place (MY_MENU_EMPTY): in every one of the 42 slots the camera file's empty code
    (camera.my_menu.empty) is "(empty)", named by a hand table, a camera source, so an editor offers it outside
    Expert mode (docs/DATA_CONTRACTS.md, "What the editor offers outside Expert mode") and a person can empty a place.
    Each slot's note says what shows it on the camera; the Add Item proofs it rests on (runs/kit2_pass2) never put an
    item into a place that held anything but that code."""
    empty = DOC["camera"]["my_menu"]["empty"]
    slots = [s for s in DOC["settings"] if s.get("area") == "global" and s.get("id") in DOC["camera"]["my_menu"]["records"]
             and s.get("index") is not None]
    assert len(slots) == 42 and empty == 2
    for s in slots:
        assert [empty, "(empty)"] in s["values"], s["key"]
        assert (s.get("proved") or {}).get("names", {}).get(str(empty)) == "hand table", s["key"]
        assert "An empty place stores 2." in s["note"], s["key"]
        assert "every place an item was added to held 2 before" in s.get("note_evidence", ""), s["key"]
        assert "runs/kit2_pass2" in s.get("note_evidence", ""), s["key"]
    proofs = ROOT / "runs" / A1 / "kit2_pass2" / "proofs.jsonl"
    pages = {f"global:0x{r:04x}" for r in DOC["camera"]["my_menu"]["records"]}
    adds = [p for p in jsonl.read(proofs) if p.get("my_menu")] if proofs.exists() else []
    for p in adds:                                   # where the run is on this computer: each add went into an empty place
        (c,) = [c for c in p["changes"] if c["key"] in pages]
        assert c["before"][p["my_menu"]["slot"]] == empty, p["dat"]


def test_a_scaled_number_is_shown_as_the_camera_shows_it():
    """shown_as: Knee Point stores percent x 100 (7500 for 75%), found from the side-list proofs, not by record id, with
    the unit the camera's text shows; the whole family, the profiles off the menu (PP7-PP9) by their record's
    agreement. A number the camera shows as stored, or a label, gets none."""
    import schema_update as S
    knee = [s for s in DOC["settings"] if s["name"].startswith(("Knee Auto Set Max Point", "Knee Manual Set Point"))]
    assert len(knee) == 66 and all(s.get("shown_as") == {"divide": 100, "decimals": 0} and s["unit"] == "%"
                                   for s in knee)
    point = DOC_BY["global:0x06b7[0]"]
    assert S.shown(7500, point["shown_as"]) == "75" and S.shown(10500, point["shown_as"]) == "105"
    assert S.shown(560, {"divide": 100, "decimals": 1}) == "5.6"
    doc = {"settings": [{"key": "global:0x0001[0]", "name": "n", "range": [0, 900], "step": 10, "unit": ""},
                        {"key": "global:0x0001[1]", "name": "n", "range": [0, 900], "step": 10, "unit": ""},
                        {"key": "global:0x0002", "name": "m", "range": [0, 9]},
                        {"key": "global:0x0003", "name": "l", "range": [0, 9]}]}

    def side(key, shown, after, before):
        return {"kind": "sidelist", "shown": shown, "changes": [{"key": key, "after": after, "before": before}]}
    proofs = [side("global:0x0001", "4.5mm", [45, 0], [0, 0]), side("global:0x0001", "9.0mm", [90, 0], [0, 0]),
              side("global:0x0002", "3", 3, 0), side("global:0x0002", "5", 5, 0),
              side("global:0x0003", "Off", 0, 1), side("global:0x0003", "2", 20, 0)]
    got = S.scaled_numbers(proofs, doc)
    assert got == {"global:0x0001[0]": {"divide": 10, "decimals": 1, "unit": "mm"},
                   "global:0x0001[1]": {"divide": 10, "decimals": 1, "unit": "mm"}}
    s = S.with_shown_as(doc["settings"][0], got["global:0x0001[0]"])
    assert list(s) == ["key", "name", "range", "step", "unit", "shown_as"] and s["unit"] == "mm"
    assert "shown_as" not in S.with_shown_as(s, None)


def test_a_sub_choices_value_never_names_its_option():
    """An option read with its sub-choice's value at proof time ("Self-timer(Single): 5 sec") is named by the option
    alone when the row has a setting placed under that option or an axis proof for it; values the option itself tells
    apart ("Spot: XL", "Spot: L") and options with no sub-choice keep their tail (decision 16: the tail can be the
    camera's own setting)."""
    import schema_update as S
    drive = {"key": "global:0x0001", "row": ["Drive Mode"]}
    delay = {"key": "global:0x0002", "row": ["Drive Mode"], "under_option": "Self-timer(Single)",
             "values": [[0, "10 sec"], [1, "5 sec"], [2, "2 sec"]]}
    labels = {0: "Single Shooting", 5: "Self-timer(Single)", 7: "Self-timer(Cont.)"}
    assert S.axis_tail_out("Self-timer(Single): 5 sec", 5, drive, [delay], set(), "Drive Mode", labels) == "Self-timer(Single)"
    assert S.axis_tail_out("Self-timer(Single): 5 sec", 5, drive, [dict(delay, under_option="Self-timer(Single): 5 sec")],
                           set(), "Drive Mode", labels) == "Self-timer(Single)"
    assert S.axis_tail_out("DRO Bracket: Lo", 12, drive, [], {("Drive Mode", "DRO Bracket")},
                           "Drive Mode [recheck]", labels) == "DRO Bracket"
    assert S.axis_tail_out("Self-timer(Single): 5 sec", 5, drive, [], set(), "Drive Mode", labels) == "Self-timer(Single): 5 sec"
    area = {"key": "global:0x0003", "row": ["Focus Area"]}
    assert S.axis_tail_out("Spot: L", 4, area, [], {("Focus Area", "Spot")}, "Focus Area",
                           {3: "Spot: XL", 4: "Spot: L"}) == "Spot: L"
    shipped = {s["key"]: dict(s["values"]) for s in DOC["settings"] if s["key"] in ("global:0x02b5", "global:0x1486", "global:0x13d4")}
    assert all(v[5] == "Self-timer(Single)" for v in shipped.values()), shipped


def test_a_sub_choice_never_starts_with_its_options_name():
    """The tail rule the other way round: a sub-choice's label without its option's name before it, the option read
    word by word ("Cont. Shooting: Hi" under Continuous Shooting is "Hi"); another head stays. In the shipped
    definition the hold's continuous speed reads "Hi", not "Cont. Shooting: Hi"."""
    import schema_update as S
    assert S.same_option("Cont. Shooting", "Continuous Shooting") and not S.same_option("Cont. Bracket", "Continuous Shooting")
    assert S.option_prefix_out("Cont. Shooting: Hi", {"Continuous Shooting"}) == "Hi"
    assert S.option_prefix_out("Spot: L", {"Continuous Shooting"}) == "Spot: L"
    assert S.option_prefix_out("50M 4:2:2 10bit", {"50M 4"}) == "50M 4:2:2 10bit"
    assert all(dict(DOC_BY[f"global:0x0bf1[{i}]"]["values"])[1] == "Hi" for i in range(3))


def test_a_value_two_options_write_alike_gets_one_name():
    """A value two options write the same way gets their common start cut back to a word, two characters or more and
    not a bare number; else both names joined. The a1 II's one-slot File Format 4 is "HEIF", from HEIF(4:2:0) and
    HEIF(4:2:2)."""
    import schema_update as S
    assert S.one_name(["HEIF(4:2:0)", "HEIF(4:2:2)"]) == "HEIF"
    assert S.one_name(["Fixed Speed STBY", "Fixed Speed REC"]) == "Fixed Speed"
    assert S.one_name(["1 sec", "10 sec"]) == "1 sec / 10 sec"
    assert S.one_name(["Hi", "Lo"]) == "Hi / Lo" and S.one_name(["Lo"]) == "Lo"
    assert dict(DOC_BY["global:0x01da"]["values"])[4] == "HEIF"


def test_one_name_per_code_in_a_picker_family():
    """family_name: a head the camera never showed loses ("Remote Zoom: Fixed Speed STBY": the screen shows an icon),
    so do a name cut short and an OCR slip of a fuller one; then two readers, then a reading at all, then full slots.
    The shipped Custom Key families name each code alike in every slot."""
    import schema_update as S
    assert S.family_name({"Remote Zoom: Fixed Speed STBY": (8, 0), "Fixed Speed STBY": (6, 3)},
                         {"Fixed Speed STBY": "two readers"}) == "Fixed Speed STBY"
    assert S.family_name({"Fixed Speed SBY": (11, 3), "Fixed Speed STBY": (3, 1)}, {"Fixed Speed SBY": "one reader",
                         "Fixed Speed STBY": "two readers"}) == "Fixed Speed STBY"
    assert S.family_name({"Face Priority in Multi M": (6, 3), "Face Priority in Multi Metering": (8, 1)}, {}) \
        == "Face Priority in Multi Metering"
    assert S.family_name({"SteadyShot Adjust": (6, 3), "SteadyShot Adjust.": (8, 1)},
                         {"SteadyShot Adjust.": "two readers"}) == "SteadyShot Adjust."
    assert S.picker_family("Custom Key (Movie): AEL Button") == "Custom Key (Movie)" and not S.picker_family("Drive Mode")
    for fam in ("Custom Key (Still)", "Custom Key (Movie)"):
        named = collections.defaultdict(set)
        for s in DOC["settings"]:
            if S.picker_family(s["name"]) == fam:
                for v, lab in s.get("values") or []:
                    named[v].add(lab)
        assert not {v: n for v, n in named.items() if len(n) > 1}, fam


def test_a_value_shown_by_its_icon_or_without_its_unit_takes_the_cameras_words_in_the_public_file():
    """icon_word, and the public file alone: the JPEG/HEIF Quality records read Extra fine/Fine/Standard/Light, the S&Q
    rate 120fps beside 60fps, the movie mode record's M Manual Exposure, the one-slot File Format 4 HEIF."""
    import schema_update as S
    assert S.icon_word("X.FINE Extra fine") == ("X.FINE", "Extra fine") and S.clean("STD Standard") == "Standard"
    assert S.icon_word("RAW Compressed") is None and S.icon_word("AF ON") is None
    for k in ("global:0x01ea", "global:0x01ec", "global:0x01f6", "global:0x01f8"):
        assert [lab for _, lab in PUB_BY[k]["values"]] == ["Extra fine", "Fine", "Standard", "Light"], k
    assert dict(PUB_BY["global:0x0248"]["values"])[2] == "120fps"
    assert dict(PUB_BY["global:0x13e1"]["values"])[5] == "Manual Exposure"
    assert dict(PUB_BY["global:0x01f2"]["values"])[2] == "HEIF"


@needs_evidence
def test_a_value_shown_by_its_icon_or_without_its_unit_takes_the_cameras_words():
    """icon_word: an icon's capitals and the words they stand for ("X.FINE Extra fine", "STD Standard") are the words;
    "RAW Compressed" is a name. The shipped JPEG/HEIF Quality records read Extra fine/Fine/Standard/Light, the S&Q rate
    120fps beside 60fps, and the movie mode record's M Manual Exposure beside Program Auto (derived)."""
    import schema_update as S
    assert S.icon_word("X.FINE Extra fine") == ("X.FINE", "Extra fine") and S.clean("STD Standard") == "Standard"
    assert S.icon_word("RAW Compressed") is None and S.icon_word("AF ON") is None
    for k in ("global:0x01ea", "global:0x01ec", "global:0x01f6", "global:0x01f8"):
        assert [lab for _, lab in DOC_BY[k]["values"]] == ["Extra fine", "Fine", "Standard", "Light"], k
    assert dict(DOC_BY["global:0x0248"]["values"])[2] == "120fps"
    assert dict(DOC_BY["global:0x13e1"]["values"])[5] == "Manual Exposure"
    assert DOC_BY["global:0x13e1"]["proved"]["names"]["5"] == "derived"
    assert dict(DOC_BY["global:0x01f2"]["values"])[2] == "HEIF"


def test_the_settings_reset_file_takes_the_definitions_names(tmp_path, monkeypatch):
    """reset_names: the settings reset file's names and tabs follow the definition by key, nothing else in it changes;
    the shipped one already agrees. The public file is the reset file's one source: no private half is written."""
    import schema_update as S
    assert S.reset_names(DOC, False) == 0
    monkeypatch.setattr(definitions, "DATA", tmp_path)
    (tmp_path / A1).mkdir()
    f = tmp_path / A1 / f"settings_reset_{A1}.json"
    f.write_text(json.dumps({"about": "Mine.", "records": {"global:0x0e68": {"name": "old", "result": "keeps"},
                                                           "global:0xffff": {"name": "gone", "result": "resets"}}},
                            indent=1), encoding="utf-8")
    assert S.reset_names(DOC, True) == 2                     # its name, and the tab it lacked
    got = json.loads(f.read_text(encoding="utf-8"))
    assert got["records"]["global:0x0e68"] == {"name": DOC_BY["global:0x0e68"]["name"], "result": "keeps",
                                               "tab": DOC_BY["global:0x0e68"]["tab"]}
    assert got["records"]["global:0xffff"]["name"] == "gone" and got["about"] == "Mine."
    assert sorted(x.name for x in tmp_path.rglob("*") if x.is_file()) == [f.name]
    assert S.reset_names(DOC, True) == 0 and json.loads(f.read_text(encoding="utf-8")) == got


def test_an_add_item_proof_names_its_code_in_every_my_menu_slot():
    """My Menu Setting > Add Item (kit/provers/mymenu_run.py): the proof's page and slot took the code; the slots share
    one code table, so the code is named in every slot, as derived, and only the slot that took it is proved. A code
    the table lacks is added to all; a name the report's rule finds the same as the proof's stays."""
    import schema_update as S
    slots = [{"key": f"global:0x{rec:04x}[{i}]", "area": "global", "id": rec, "index": i, "name": f"My Menu {p}: item {i + 1}",
              "values": [[2, "(empty)"], [10, "Image Quality Settings"], [101, "APS-C/Super 35mm Shooting"]]}
             for p, rec in ((1, 0x0c8a), (2, 0x0c91)) for i in range(3)]
    doc = {"settings": slots}
    by_key = {s["key"]: s for s in slots}
    proofs = [{"kind": "list", "path": ["My Menu Setting", "Add Item"], "label": "S&Q Settings", "shown": "s&dS&Q Settings",
               "applied": True, "my_menu": {"page": 2, "slot": 1, "code": 61}},
              {"kind": "list", "path": ["My Menu Setting", "Add Item"], "label": "Image Quality Settings",
               "shown": "", "applied": True, "my_menu": {"page": 1, "slot": 0, "code": 10}},
              {"kind": "list", "label": "Not mine", "applied": False, "my_menu": {"page": 1, "slot": 2, "code": 99}}]
    items = S.my_menu_items(proofs, by_key, [0x0c8a, 0x0c91])
    assert items == [("global:0x0c91[1]", 61, "S&Q Settings", "two readers"),
                     ("global:0x0c8a[0]", 10, "Image Quality Settings", "one reader")]
    changed, readers, derived, proved = [], collections.defaultdict(dict), collections.defaultdict(dict), {}
    assert S.my_menu_tables(doc, items, [0x0c8a, 0x0c91], changed, readers, derived, proved) == 2
    assert all(dict(s["values"])[61] == "S&Q Settings" and dict(s["values"])[10] == "Image Quality Settings"
               for s in slots)
    assert [s["key"] for s in slots if s.get("proved")] == ["global:0x0c8a[0]", "global:0x0c91[1]"]
    assert by_key["global:0x0c91[1]"]["proved"]["values"] == [61] and readers["global:0x0c91[1]"] == {61: "two readers"}
    assert all(derived[s["key"]][61] == "derived" for s in slots)
    for s in slots:
        S.with_names(s, readers[s["key"]], {}, derived[s["key"]])
    assert by_key["global:0x0c91[1]"]["proved"]["names"]["61"] == "two readers"
    assert "proved" not in by_key["global:0x0c8a[1]"]


def test_the_my_menu_slots_share_one_code_table():
    """The 42 My Menu slots of the shipped definition hold one code table, so every code an Add Item proof wrote is
    named alike in all of them."""
    import schema_update as S
    records = S.mymenu_slots(DOC)
    slots = [s for s in DOC["settings"] if s["area"] == "global" and s["id"] in records and s.get("index") is not None]
    assert len(slots) == 42
    assert len({json.dumps(s["values"]) for s in slots}) == 1
    proofs = paths.module_root() / "kit2_pass2" / "proofs.jsonl"
    if proofs.exists():
        table = dict(slots[0]["values"])
        for r in jsonl.read(proofs, bad="skip"):
            if (r.get("my_menu") or {}).get("code") is not None and r.get("applied") is not False:
                assert r["my_menu"]["code"] in table, r["my_menu"]


def test_a_my_menu_name_the_table_holds_keeps_the_fuller_of_two_alike_readings():
    """The table's name and the proof's are two readings of one row when alike: the fuller stays ("Shot Mark with
    Shutter Button" over the OCR's "with Shutter Button"; "Fn Menu Settings" over "Menu Settings"), unless the
    table's is the proof's with an icon glyph glued on ("SISO Range Limit"); a name unlike the proof's gives way."""
    import schema_update as S
    slots = [{"key": f"global:0x0c8a[{i}]", "area": "global", "id": 0x0c8a, "index": i, "name": f"My Menu 1: item {i + 1}",
              "values": [[2, "(empty)"], [2589, "Shot Mark with Shutter Button"], [2497, "Menu Settings"],
                         [248, "SISO Range Limit"], [2330, "AF/MF"]]} for i in range(2)]
    doc = {"settings": slots}
    items = [("global:0x0c8a[0]", 2589, "with Shutter Button", "two readers"),
             ("global:0x0c8a[0]", 2497, "Fn Menu Settings", "two readers"),
             ("global:0x0c8a[1]", 248, "ISO Range Limit", "two readers"),
             ("global:0x0c8a[1]", 2330, "Preset Focus/Zoom", "two readers"),
             ("global:0x0c8a[1]", 61, "S&Q Settings", "one reader")]
    changed, readers, derived, proved = [], collections.defaultdict(dict), collections.defaultdict(dict), {}
    assert S.my_menu_tables(doc, items, [0x0c8a], changed, readers, derived, proved) == 5
    table = dict(slots[1]["values"])
    assert table[2589] == "Shot Mark with Shutter Button" and table[2497] == "Fn Menu Settings"
    assert table[248] == "ISO Range Limit" and table[2330] == "Preset Focus/Zoom" and table[61] == "S&Q Settings"
    assert dict(slots[0]["values"]) == table


# ---------------------------------------------------------------- unseen values: the writer's rules (K1-K7)

def scale_setting(key="global:0x0001", n=75, unit=" K", proved=None, **kw):
    """A setting listing a number scale, 2500-9900 K stored (K - 2500) / 100 by default (made-up record)."""
    s = {"key": key, "name": "Scale", "values": [[v, f"{2500 + 100 * v}{unit}"] for v in range(n)], **kw}
    return {**s, "proved": proved} if proved else s


def test_a_listed_scale_sampled_on_a_line_is_written_sampled():
    """sampled_scale (KIT_PLAN's line rule on a list, the camera's readings on the line already): every label a number
    of one unit, fewer values proved than listed, both ends among them, and every listed value on the line through
    them; then the definition keeps how many and that they lie on a line, never which (one is the camera's own
    setting, decision 16)."""
    import schema_update as S
    s = scale_setting()
    assert S.sampled_scale(s, {0, 7, 35, 74}), "the colour temperature's four proofs"
    assert not S.sampled_scale(s, {7, 35, 74}), "the low end not proved"
    assert not S.sampled_scale(s, {0, 74}), "two points make no line rule"
    ev = {"values": [[0, "-5.0 EV"], [1, "-4.7 EV"], [2, "-4.5 EV"], [3, "-4.3 EV"], [4, "-4.0 EV"], [5, "-3.7 EV"]]}
    assert not S.sampled_scale(ev, {0, 2, 4}), "Exposure Comp.'s thirds and halves between: the list is no line"
    assert not S.sampled_scale(scale_setting(n=4), {0, 1, 2, 3}), "a list proved whole is no sample"
    assert not S.sampled_scale({**s, "range": [0, 74]}, {0, 7, 35, 74}), "a range has its own rule"
    sixths = {"values": [[6 - k, f"{k:+d}/6 EV" if k else "±0 EV"] for k in range(6, -7, -1)]}
    assert S.sampled_scale(sixths, {0, 4, 6, 12}), "Exposure Std. Adjust: +6/6 0, +2/6 4, ±0 6, -6/6 12"
    mixed = {"values": [[0, "1 K"], [1, "2 EV"], [2, "3 K"], [3, "4 K"]]}
    assert not S.sampled_scale(mixed, {0, 1, 3}) and not S.sampled_scale({"values": [[0, "A"], [1, "B"]]}, {0, 1})
    twice = {"values": [[0, "2"], [1, "0"], [2, "1"], [3, "2"], [4, "3"], [5, "4"]]}
    assert not S.sampled_scale(twice, {1, 3, 5}), "the number 2 at codes 0 and 3: code 0 is off the line"


SCALES = ["global:0x0b91", "global:0x0b93", "global:0x0b95", "global:0x0346", "global:0x0348", "global:0x034a",
          "global:0x034c", "global:0x034e", "global:0x1476", "global:0x0018"]


def test_the_shipped_scales_list_no_proved_value_in_the_public_file():
    """The public file alone: the scales the line rule closes (colour temperature, Exposure Std. Adjust, Aspect Marker
    Level, Audio Rec Level 0x0018, the 73 White Balance fine-tune grids) are proved as on one line, listing no value
    (the value each held when its proofs began reaches no one, decision 16), every value of their list offered; and
    the notes of the scales name no start."""
    grids = [k for k, s in PUB_BY.items() if s["name"].startswith("WB fine-tune") and s.get("proved")]
    assert len(grids) == 73, len(grids)
    for k in SCALES + grids:
        assert PUB_BY[k]["proved"] == {"sampled": {"linear": True}}, (k, PUB_BY[k]["proved"])
    for k in ("global:0x0018", "global:0x0b95", "global:0x1479", "global:0x04e6", "global:0x0e29", "global:0x0f28"):
        note = PUB_BY[k].get("note", "")
        assert "(the start)" not in note and "owner's" not in note and "user's" not in note, (k, note)


@needs_evidence
def test_the_shipped_scales_list_no_proved_value():
    """The scales the line rule closes (colour temperature 0x0b91/0x0b93 and Movie's own 0x0b95, Exposure Std. Adjust,
    Aspect Marker Level, Audio Rec Level 0x0018, every White Balance fine-tune grid) are sampled on a line and list no
    proved value, so the value each held when its proofs began reaches no one (decision 16); their names are a
    scale's, every value of their list offered (proved.sampled.linear, which an editor reads). Movie's temperature
    took both ends in Movie mode on 2026-11-08 (runs/kit2_wbmovie2), beside 6000 K and 5000 K; the notes name no
    start."""
    by = {s["key"]: s for s in DOC["settings"]}
    keys = ["global:0x0b91", "global:0x0b93", "global:0x0b95", "global:0x0346", "global:0x0348", "global:0x034a",
            "global:0x034c", "global:0x034e", "global:0x1476", "global:0x0018"]
    grids = [k for k, s in by.items() if s["name"].startswith("WB fine-tune") and s.get("proved")]
    assert len(grids) == 73, len(grids)
    for k in keys + grids:
        p = by[k]["proved"]
        assert p.get("sampled", {}).get("linear") is True and "values" not in p, (k, p)
        assert set(p.get("names", {}).values()) <= {"sampled", "hand table"}, (k, set(p["names"].values()))
    assert by["global:0x0b95"]["proved"]["sampled"]["proofs"] == 4, "2500 K, 5000 K, 6000 K and 9900 K; not the start"
    both = [k for k, s in by.items() if "sampled" in (s.get("proved") or {}) and "values" in s["proved"]]
    assert not both, f"a setting proved by samples lists none of them (one is the start, decision 16): {both[:5]}"
    for k in ("global:0x0018", "global:0x0b95", "global:0x1479", "global:0x04e6", "global:0x0e29", "global:0x0f28"):
        note = by[k].get("note", "")
        assert "(the start)" not in note and "owner's" not in note and "user's" not in note, (k, note)


def test_an_arrays_slots_share_one_code_table():
    """one_slot_table: the slots of one array that carry one name share one code table when the camera shows them one
    list and their proofs never disagree: PP10 (HLG2) proved BT.2020 = 10 and 709 = 11, which PP1's list refused, so
    the two are linked though no value is proved in both; every linked slot is named so, the missing value added, as
    derived. Slots linked to none (no value proved alike, no refusal of another's label) lend and take nothing, slots
    without a proof (PP7-PP9) are left alone, and slots that disagree lend nothing. The count is of values named
    afresh: a rerun on what the definition then holds names none."""
    import schema_update as S
    slot = lambda i, vals, **kw: {"key": f"global:0x073b[{i}]", "area": "global", "id": 0x073b, "index": i,
                                  "name": "Color Mode", "values": [list(v) for v in vals], **kw}
    pp1 = [(0, "Movie"), (1, "Still"), (10, "BT.2020")]
    doc = {"settings": [slot(0, pp1), slot(9, [(0, "Movie"), (10, "BT.2020"), (11, "709")]),
                        slot(6, [(0, "Movie"), (11, "S-Gamut")])]}
    proved = {"global:0x073b[0]": {0, 1}, "global:0x073b[9]": {10, 11}}
    derived, changed = collections.defaultdict(dict), []
    before = json.loads(json.dumps(doc))
    assert S.one_slot_table(doc, proved, derived, changed) == 0, "no value proved alike and no refusal: not one list"
    assert doc == before and not derived and not changed
    refused = {"global:0x073b[0]": {"BT. 2020", "709"}}             # PP1's menu_blocked, spaces as a reader read them
    assert S.one_slot_table(doc, proved, derived, changed, refused) == 4
    by = {s["key"]: s for s in doc["settings"]}
    assert by["global:0x073b[0]"]["values"] == [[0, "Movie"], [1, "Still"], [10, "BT.2020"], [11, "709"]]
    assert derived["global:0x073b[0]"] == {10: "derived", 11: "derived"}
    assert derived["global:0x073b[9]"] == {0: "derived", 1: "derived"} and [1, "Still"] in by["global:0x073b[9]"]["values"]
    assert by["global:0x073b[6]"]["values"] == [[0, "Movie"], [11, "S-Gamut"]], "PP7: no proof, untouched"
    assert changed == [("global:0x073b[0]", "Color Mode", 11, None, "709"), ("global:0x073b[9]", "Color Mode", 1, None, "Still")]
    for x in doc["settings"][:2]:                                       # what --write then holds: the names derived
        x["proved"] = {"names": {str(v): src for v, src in derived[x["key"]].items()}}
    assert S.one_slot_table(doc, proved, collections.defaultdict(dict), [], refused) == 0, "a rerun names none afresh"
    doc["settings"][0]["proved"]["names"]["10"] = "hand table"            # a source that outranks derived: not counted
    assert S.one_slot_table(doc, proved, collections.defaultdict(dict), [], refused) == 0
    doc["settings"][1]["values"][0] = [0, "Cinema"]                      # PP10 now names 0 otherwise: they disagree
    proved["global:0x073b[9]"] = {0, 10}
    derived = collections.defaultdict(dict)
    assert S.one_slot_table(doc, proved, derived, [], refused) == 0 and not derived


def test_a_hold_takes_the_live_table_when_every_proof_fits(monkeypatch):
    """hold_tables (HOLD_TABLES): a Recall Custom hold's copy of a live setting, every proof's reading against the live
    table, the code itself (ISO) or mirrored (Exposure Comp.: 40 minus the live code). All fitting, the evidence goes
    into the hold's note (counts in note_evidence, kept current); with the live table proved in full the hold's values
    are named from it as derived, a mirrored copy taking the live labels; one proof that does not fit stops the rule."""
    import schema_update as S
    live_iso = {"key": "global:0x0334", "name": "ISO",
                "values": [[0, "AUTO"], [2, "ISO 50"], [4, "ISO 80"], [5, "ISO 100"], [6, "ISO 125"]]}
    hold_iso = {"key": "global:0x0c01[0]", "name": "ISO", "note": "Reg. Custom Shoot Set",
                "values": [[0, "AUTO"], [2, "ISO 50 (multi-frame NR)"], [4, "ISO 80 (multi-frame NR)"], [5, "ISO 100"],
                           [6, "ISO 125"]]}
    live_ev = {"key": "global:0x0340", "name": "Exposure Comp.",
               "values": [[v, f"{(v - 20) / 4:+.1f} EV"] for v in range(0, 41, 4)]}
    hold_ev = {"key": "global:0x0bf9[0]", "name": "Exposure Comp.", "values": [[v, "hand"] for v in range(0, 41, 4)]}
    by_key = {s["key"]: s for s in (live_iso, hold_iso, live_ev, hold_ev)}
    monkeypatch.setattr(S, "HOLD_TABLES", {"global:0x0c01[0]": {"live": "global:0x0334", "mirror": None},
                                           "global:0x0bf9[0]": {"live": "global:0x0340", "mirror": 40}})
    report = [{"row": "hold 1 > ISO", "records": {"global:0x0c01[0]": {"proved": {"ISO AUTO": 0, "ISO 50": 2}, "notes": []}}},
              {"row": "hold 1 > EV", "records": {"global:0x0bf9[0]": {"proved": {"+4.0": 4, "‡0.0": 20}, "notes": []}}}]
    proved = {"global:0x0334": {0, 2, 4, 5, 6}, "global:0x0c01[0]": {0, 2}, "global:0x0340": {20},
              "global:0x0bf9[0]": {4, 20}}
    over, derived = collections.defaultdict(dict), collections.defaultdict(dict)
    S.hold_tables(by_key, proved, report, over, derived, [])
    assert derived["global:0x0c01[0]"] == {5: "derived", 6: "derived"}, "the live ISO proved in full"
    assert hold_iso["values"][1:3] == [[2, "ISO 50 (multi-frame NR)"], [4, "ISO 80 (multi-frame NR)"]], \
        "the hold's own fuller names stay"
    assert over["global:0x0c01[0]"] == {4: "hand table"}, "a fuller name the live table lacks is the hand table's"
    assert hold_iso["note"].startswith("Reg. Custom Shoot Set. A hold stores the code of the live setting, 0x0334")
    assert "2 proofs of this hold, the live table proved in full, runs/" in hold_iso["note"]
    assert "derived" not in derived["global:0x0bf9[0]"].values(), "the live Exposure Comp. not proved in full: hand table"
    assert "the live table not yet proved in full" in hold_ev["note"]
    proved["global:0x0340"] = set(range(0, 41, 4))                    # the camera session proves the live table
    from writer.notes import split_evidence
    hold_ev["note"], hold_ev["note_evidence"] = split_evidence(hold_ev["note"])
    S.hold_tables(by_key, proved, report, over, derived, [])
    assert derived["global:0x0bf9[0]"] == {v: "derived" for v in range(0, 41, 4) if v not in (4, 20)}
    assert dict(map(tuple, hold_ev["values"]))[0] == "+5.0 EV", "hold 0 is live 40, +5.0 EV, mirrored"
    assert "the live table proved in full" in hold_ev["note_evidence"] and "not yet" not in hold_ev["note_evidence"]
    assert hold_ev["note"].count("A hold stores") == 1, "the line once, its evidence brought up to date"
    report[1]["records"]["global:0x0bf9[0]"]["proved"]["+1.0"] = 8      # a proof the mirror does not fit (40 - 24 = 16)
    hold_ev["values"] = [[v, "hand"] for v in range(0, 41, 4)]
    derived = collections.defaultdict(dict)
    S.hold_tables(by_key, proved, report, over, derived, [])
    assert not derived["global:0x0bf9[0]"] and dict(map(tuple, hold_ev["values"]))[0] == "hand"


def test_a_hold_proved_in_full_names_the_other_holds_that_agree():
    """hold_table_lines and hold_agrees, for any Reg. Custom Shoot Set item: a hold whose every value is proved (hold
    3's Aperture, 49 of 49; hold 3's Shutter Speed once the camera session proves its 62) names the other holds, each
    agreeing hold saying so in its note with the counts; a hold whose proofs disagree says nothing."""
    import schema_update as S
    vals = [[0, "F1"], [1, "F1.1"], [2, "F1.2"]]
    holds = {f"global:0x0bdd[{i}]": {"key": f"global:0x0bdd[{i}]", "name": "Aperture", "note": "Reg. Custom Shoot Set",
                                     "values": [list(v) for v in vals]} for i in range(3)}
    menus = {k: {f"Reg. Custom Shoot Set > Recall Custom hold {i + 1} > Aperture"} for i, k in enumerate(holds)}
    proved = {"global:0x0bdd[2]": {0, 1, 2}, "global:0x0bdd[0]": {1}, "global:0x0bdd[1]": {2}}
    holds["global:0x0bdd[1]"]["values"][2] = [2, "F1.4"]                 # its proof read another name
    assert S.hold_agrees(holds["global:0x0bdd[0]"], proved["global:0x0bdd[0]"], dict(map(tuple, vals)), {0, 1, 2})
    assert not S.hold_agrees(holds["global:0x0bdd[1]"], proved["global:0x0bdd[1]"], dict(map(tuple, vals)), {0, 1, 2})
    changed = []
    S.hold_table_lines(holds, proved, menus, changed)
    # how the names were found is evidence alone: the note says nothing of it (decision 16)
    assert holds["global:0x0bdd[0]"]["note"] == "Reg. Custom Shoot Set"
    assert holds["global:0x0bdd[0]"]["note_evidence"] == ("Its values are named by hold 3's table, which hold 3 proved "
                                                          "in full, the proofs of this hold agreeing with it: all 3 "
                                                          "values proved on hold 3, 1 on this one, runs/kit2_pass2.")
    assert holds["global:0x0bdd[1]"]["note"] == "Reg. Custom Shoot Set", "it disagrees: nothing said"
    assert holds["global:0x0bdd[2]"]["note"] == "Reg. Custom Shoot Set", "the hold proved in full itself"
    again = json.loads(json.dumps(holds))
    S.hold_table_lines(again, proved, menus, [])
    assert again == holds and [c[0] for c in changed] == ["global:0x0bdd[0]"], "a rerun adds nothing"
    # a note written before the heading took its full stop, its evidence apart, and a count moved on since
    line = "Its values are named by hold 3's table, which hold 3 proved in full: the proofs of this hold agree with it."
    old = {"note": f"Reg. Custom Shoot Set {line}", "note_evidence": "2026-10-30; all 3 values proved on hold 3, 0 on this one, runs/kit2_pass2"}
    assert S.renew_line(old, line[:-1] + " (all 3 values proved on hold 3, 1 on this one, runs/kit2_pass2).",
                        re.compile(r"values proved on hold \d"))
    assert old == {"note": f"Reg. Custom Shoot Set. {line}",
                   "note_evidence": "2026-10-30; all 3 values proved on hold 3, 1 on this one, runs/kit2_pass2"}


def test_a_value_is_marked_not_offered_only_where_its_evidence_holds(tmp_path):
    """not_offered_marks (writer/offered.py): a mark stands when every row it names (its walks of the list, whole as
    its evidence says) never wrote the value, or when every picker list of a table-walk screen went round to its start
    and none lists the function; a walk that wrote it, a list not walked round or one that lists it refuses the mark
    (printed), and a setting no mark names loses an old field. A held value (the factory one) needs the downloads it cites to hold it."""
    from writer.offered import not_offered_marks
    s = lambda key, vals, **kw: {"key": key, "name": key, "values": [list(v) for v in vals], **kw}
    doc = {"settings": [s("global:0x0e00", [(2, "ISO 50"), (5, "ISO 100"), (6, "ISO 125")]),
                        s("global:0x0407", [(198, "Audio Rec Level"), (247, "ISO")]),
                        s("global:0x0e10", [(9, "Flash")], not_offered=[{"value": 9}])]}
    report = [{"row": "ISO > ISO AUTO Maximum [Stills mode]", "records": {"global:0x0e00": {"proved": {"ISO 100": 5, "ISO 125": 6}}}}]
    cell = lambda labels, wrapped=True: {"opens": "picker", "wrapped": wrapped, "options": [{"label": f"• {lab}"} for lab in labels]}
    tables = {"Keys": {"pages": [{"title": "Dial/Wheel", "items": [cell(["ISO", "Exposure Comp."])] * 2}]}}
    entry = lambda key, values, **kw: {"key": key, "values": values, "why": "Not on its list.", "menu": "M", "evidence": "a walk", **kw}
    entries = [entry("global:0x0e00", [2], walk=r"^ISO > ISO AUTO Maximum"), entry("global:0x0e00", [6], walk=r"^ISO > ISO AUTO Maximum"),
               entry("global:0x0407", [198], table=("Keys", "Dial/Wheel")), entry("global:0x0407", [247], table=("Keys", "Dial/Wheel"))]
    assert not_offered_marks(doc, entries, report, tables, tmp_path) == (2, 2)
    by = {x["key"]: x for x in doc["settings"]}
    assert by["global:0x0e00"]["not_offered"] == [{"value": 2, "label": "ISO 50", "why": "Not on its list.", "menu": "M",
                                                   "evidence": "a walk"}]
    assert [m["value"] for m in by["global:0x0407"]["not_offered"]] == [198], "ISO is on the dials' list"
    assert "not_offered" not in by["global:0x0e10"], "no mark names it now"
    tables["Keys"]["pages"][0]["items"][1] = cell(["ISO"], wrapped=False)
    assert not_offered_marks(doc, entries[2:3], report, tables, tmp_path) == (0, 1), "a list not walked round"
    held = entry("global:0x0e00", [2], walk=r"^ISO > ISO AUTO Maximum", held=True, files=["none.DAT"])
    assert not_offered_marks(doc, [held], report, tables, tmp_path) == (0, 1), "the download it cites is not there"


def test_the_shipped_marks_of_values_the_menus_never_offer_in_the_public_file():
    """The public file alone: the a1 II's not_offered marks, 54 in all, ISO AUTO Minimum's factory ISO 64 held, twice;
    each says why in plain words and on which menu, each value is one of its setting's, and an editor offers none of
    the values a mark says the menus never offer (each a value no proof checked)."""
    marks = [(s, m) for s in PUB["settings"] for m in s.get("not_offered") or []]
    assert (len(marks), sum(1 for _, m in marks if m.get("held"))) == (54, 2)
    for s, m in marks:
        assert m["value"] in {v for v, _ in s["values"]} and m["why"].endswith(".") and m["menu"], (s["key"], m)
        assert "evidence" not in m, s["key"]
        if not m.get("held"):
            assert m["value"] not in (s.get("proved") or {}).get("values", []), (s["key"], m["value"])
    held = {s["key"]: m for s, m in marks if m.get("held")}
    assert set(held) == {"global:0x0dfa", "global:0x0dfc"} and all(m["value"] == 3 for m in held.values())


@needs_evidence
def test_the_shipped_marks_of_values_the_menus_never_offer():
    """The a1 II's not_offered (the unseen-values plan, route 3): the stills dials' Audio Rec Level and Follow Custom,
    the movie dials' Flash Comp., My Dial's Follow Custom, ISO AUTO's ISO 50/64/80, four Rec Frame Rates and Movie
    White Balance's Flash, 52 in all, and ISO AUTO Minimum's factory ISO 64, held, twice. No mark is a value a proof
    wrote, each says why in plain words, and each value is one of its setting's."""
    marks = [(s, m) for s in DOC["settings"] for m in s.get("not_offered") or []]
    assert (len(marks), sum(1 for _, m in marks if m.get("held"))) == (54, 2)
    for s, m in marks:
        assert m["value"] in {v for v, _ in s["values"]} and m["why"].endswith(".") and m["menu"], (s["key"], m)
        if not m.get("held"):
            assert m["value"] not in (s.get("proved") or {}).get("values", []), (s["key"], m["value"])
    held = {s["key"]: m for s, m in marks if m.get("held")}
    assert set(held) == {"global:0x0dfa", "global:0x0dfc"} and all(m["value"] == 3 for m in held.values())
    assert all((DOC_BY[k]["proved"]["names"] or {}).get("3") == "derived" for k in held), "named by the ISO table"


# ---------------------------------------------------------------- the camera's other proof runs (2026-11-09)

def test_the_main_runs_report_reads_the_cameras_other_proof_runs(tmp_path):
    """pass2_report reports the main run (kit2_pass2) with the run folders marked as proof runs (camkit.runs.PROOF_RUN,
    which afreg_run.py and filter_run.py --run write), never an unmarked run such as one made to check the kit, whatever
    its name; another run, or --alone, by itself. A side run's proofs name their files with their run (two runs'
    "00001_before.DAT" are never one, and a base is read from its own run), its unfinished attempts are left out by its
    own attempts file, and a proof found in two folders counts once. Made-up proofs."""
    import pass2_report as R
    from camkit import runs
    main = write_run(tmp_path, [proof("A", 0, [("global:0x0001", 0, 1)], "a1", frame=10)], done=["a1"])
    side = tmp_path / "kit2_afreg2"
    (side / "dat").mkdir(parents=True)
    assert runs.mark_proof_run(side, "made up") and not runs.mark_proof_run(main, "made up")
    assert not (main / runs.PROOF_RUN).exists()
    shutil.copy(SAMPLE, side / "dat" / "00001_before.DAT")
    kept = proof("B", 0, [("global:0x0002", 7, 0)], base="00001_before.DAT", frame=20, path=("Hold",))
    cut = proof("C", 1, [("global:0x0002", 0, 1)], "s2", base="00001_before.DAT", frame=30, path=("Hold",))
    (side / "proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in (kept, cut)), encoding="utf-8")
    review = tmp_path / "kit2_afreg_check"                  # a check run named as a prover's would be: not marked
    review.mkdir()
    (review / "proofs.jsonl").write_text(json.dumps(proof("B", 1, [("global:0x0002", 0, 1)])) + "\n", encoding="utf-8")
    empty = tmp_path / "kit2_filter_empty"                  # marked, no proofs yet
    empty.mkdir()
    runs.mark_proof_run(empty, "made up")
    assert R.proof_runs(main) == [main, side]
    assert R.proof_runs(main, alone=True) == [main] and R.proof_runs(side) == [side] and R.proof_runs(review) == [review]
    proofs, skip, _, _, _ = R.report_proofs(main)
    assert [p.get("run") for p in proofs] == [None, "kit2_afreg2", "kit2_afreg2"]
    assert proofs[1]["dat"] == "kit2_afreg2/00021_x.DAT" and proofs[1]["base"] == "kit2_afreg2/00001_before.DAT"
    assert proofs[0]["dat"] == "00011_x.DAT", "the main run's own files keep their names"
    assert skip == {2}, "the side run's attempt s2 has no completion line"
    assert R.frame_no(proofs[1]["chosen_frame"]) == 20
    R._RUNS_ROOT[:], R._BASE_DIRS[:] = [tmp_path], [main / "dat", main]
    try:
        assert R.base_file(proofs[1]["base"]) == side / "dat" / "00001_before.DAT"
        assert R.base_file("00001_before.DAT") is None, "the main run holds no file of that name"
    finally:
        R._RUNS_ROOT[:], R._BASE_DIRS[:] = [], []
    # the same proof recorded into the main run with its run named, and kept in the side run's folder: counted once
    with open(main / "proofs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(kept, run="kit2_afreg2")) + "\n")
    proofs, skip, _, _, _ = R.report_proofs(main)
    assert len(proofs) == 3 and [p["label"] for p in proofs] == ["A", "B", "C"] and skip == {2}


def test_a_panels_slider_proved_where_the_camera_stood_gives_way_to_the_proofs_that_set_its_setup_row(tmp_path):
    """pass2_report.stood_rows/stood_out: a panel's slider is there in one state of its setup row only, so its lines
    made where the camera stood ("stills, as found", which the writer strips to the bare row) told that state; once
    lines of the same row name the setup row set through the menu (scale_run.py --panel-row with its --set) and prove
    the same, the older row is left out of the report, and so of the definition's menu rows. A row whose lines prove
    something the setting lines do not is kept, and so is any row beside no setting line. Made-up proofs; and the
    ILCE-1M2's Monitor Brightness manual level, whose older row was such a one, lists only the row that names its
    setup."""
    import pass2_report as R
    import schema_update as S
    k, row, setup = "global:0x0052", ("Brightness",), "Brightness > Brightness Setup = Manual, stills"
    scale = [("-2", 0), ("-1", 1), ("+1", 3), ("±0", 2)]
    found = [dict(proof(lab, i, [(k, 2, i)] if i != 2 else [], "a1", frame=10 + 2 * n, path=row), context="stills, as found")
             for n, (lab, i) in enumerate(scale) if lab != "+1"]
    plain = [dict(proof("On", 1, [("global:0x0003", 0, 1)], "a3", frame=50, path=("Other",)), context="stills, as found")]
    later = [dict(proof(lab, i, [(k, 2, i)] if i != 2 else [], "a2", frame=30 + 2 * n, path=row), context=setup)
             for n, (lab, i) in enumerate(scale)]
    run = write_run(tmp_path, found + plain + later, done=["a1", "a2", "a3"])
    proofs, skip, _, _, _ = R.report_proofs(run)
    assert skip == set() and R.stood_on(proofs, skip) == {0, 1, 2}
    assert R.stood_out(run, proofs, skip, {}, set(), frozenset()) == {0, 1, 2}
    assert set(R.rows_of(run, proofs, R.stood_on(proofs, skip))) == {"Other [stills, as found]", f"Brightness [{setup}]"}
    assert R.stood_on(proofs, skip, {"Brightness [stills, as found]"}) == set(), "a row the report kept stays"
    # the writer: no older menu row is kept (the bare row, or a hand table's since replaced), and the lines left out
    # back no value it keeps (written_values)
    old = {"run": "kit2_pass2", "date": "d", "menu": ["Brightness", "Brightness [by hand]"], "values": [0, 1, 2, 9]}
    new = {"run": "kit2_pass2", "date": "d", "menu": [f"Brightness [{setup}]"], "values": [0, 1, 2, 3]}
    written = S.written_values(proofs, skip)
    assert written[k] == {0, 1, 3}
    assert S.kept_proof(old, new, written=frozenset(written[k]))[0] == new
    # an older line the setting lines do not prove (another code for one label): the older row stays, and counts
    odd = [dict(found[0], changes=[{"key": k, "before": 2, "after": 7}])] + found[1:]
    run.joinpath("proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in odd + plain + later), encoding="utf-8")
    proofs, skip, _, _, _ = R.report_proofs(run)
    assert R.stood_on(proofs, skip) == set() and 7 in S.written_values(proofs, skip)[k]
    # an unfinished setting attempt sets nothing: the older row stays
    run.joinpath("attempts.jsonl").write_text(json.dumps({"attempt": "a1", "row": "Brightness", "complete": True}) + "\n",
                                              encoding="utf-8")
    run.joinpath("proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in found + later), encoding="utf-8")
    proofs, skip, _, _, _ = R.report_proofs(run)
    assert skip == {3, 4, 5, 6} and R.stood_on(proofs, skip) == set()


@needs_evidence
def test_the_monitor_brightness_slider_lists_only_the_row_that_names_its_setup():
    """The ILCE-1M2's Monitor Brightness manual level, whose older row was proved where the camera stood: its proof's
    menu rows (evidence) each name its setup row (stood_out, above), or say how it was chosen ([by hand], ...)."""
    menus = {s["key"]: (s.get("proved") or {}).get("menu") or [] for s in DOC["settings"]}
    assert "Monitor Brightness" not in menus["global:0x0052"], menus["global:0x0052"]
    assert "Monitor Brightness [Monitor Brightness > Brightness Setup = Manual, stills]" in menus["global:0x0052"]


def test_a_row_that_names_less_state_gives_way_to_rows_of_the_same_row_that_name_more_and_prove_all_it_proves(tmp_path):
    """pass2_report.stood_rows/stood_out, beyond a panel's slider: a hold made where the camera stood (no context, no
    setup) can tell the state it depends on by the records it wrote (an AF area hold writes one orientation or all
    three, as Switch V/H AF Area says), so it gives way to holds proved again with the run's setup; an area whose kind
    record already held its kind leaves that record as it was, so "the same" is each option chosen with the same index
    and label and each record and value it changed changed by a line of the same option or held by that line's base
    download already (a base made up here). A row with a context naming another state ("Movie mode") gives way as well
    to rows that name the row it says nothing of ("Switch V/H AF Area = ..."). Kept: a row that says anything of that
    row ("Switch V/H AF Area Off" with no setup), one that proves a value the other rows do not, one whose name the
    other rows back with fewer readers, and a row beside lines naming fewer states than its own. Made-up proofs; and the
    ILCE-1M2's definition lists neither the bare registration row nor Focus Area's Movie mode row."""
    import pass2_report as R
    menu = ("AF Area Registration On, Fn held on the shooting screen",)
    kind, area, area_v, setup = "global:0x0e7a", "global:0x0f80", "global:0x0f82", ["Switch V/H AF Area = Off"]

    def hold(lab, i, changes, frame, **more):
        return dict(proof(lab, i, changes, frame=frame, path=menu), **more)
    bare = [hold("Center Fix", 2, [(kind, 3, 2), (area, 5, 2), (area_v, 5, 2)], 10),
            hold("Spot: M", 5, [(kind, 2, 3), (area, 2, 5), (area_v, 2, 5)], 12)]
    # the stated Spot: M leaves the kind record alone: its base download already holds Spot's kind (3)
    stated = [hold("Spot: XL", 3, [(kind, 0, 3), (area, 0, 3), (area_v, 0, 3)], 20, context="Switch V/H AF Area Off",
                   setup=setup),
              hold("Spot: M", 5, [(area, 3, 5), (area_v, 3, 5)], 22, context="Switch V/H AF Area Off", setup=setup,
                   base="00090_base.DAT"),
              hold("Center Fix", 2, [(kind, 3, 2), (area, 5, 2), (area_v, 5, 2)], 24, context="Switch V/H AF Area Off",
                   setup=setup)]
    said = [hold("Zone", 1, [(kind, 2, 1), (area, 2, 1)], 30, context="Switch V/H AF Area Off")]
    fa, level = ("Focus Area",), "Switch V/H AF Area = AF Point + AF Area, camera level"
    movie = [dict(proof(lab, i, [("global:0x0e68", 0, i)], frame=40 + 2 * i, path=fa, kind="dialog"), context="Movie mode")
             for lab, i in (("Wide", 0), ("Zone", 1))]
    still = [dict(proof(lab, i, [("global:0x0e68", 0, i)], frame=50 + 2 * i, path=fa, kind="dialog"), context=level)
             for lab, i in (("Wide", 0), ("Zone", 1), ("Center Fix", 2))]
    run = write_run(tmp_path, bare + stated + said + movie + still)
    made_base(run, "00090_base.DAT", {kind: 3})
    proofs, skip, _, _, _ = R.report_proofs(run)
    found = R.stood_rows(proofs, skip)
    assert set(found) == {menu[0], "Focus Area [Movie mode]"}, found
    assert found[menu[0]] == ({0, 1}, {f"{menu[0]} [Switch V/H AF Area Off]"})
    assert R.stood_out(run, proofs, skip, {}, set(), frozenset()) == {0, 1, 6, 7}
    rows = set(R.rows_of(run, proofs, R.stood_out(run, proofs, skip, {}, set(), frozenset())))
    assert f"{menu[0]} [Switch V/H AF Area Off]" in rows, "the line that says the row stays, unset or not"
    assert R.stood_on(proofs, skip, rows) == {0, 1, 6, 7}
    # a value no stated line proves: the bare row stays
    odd = [bare[0], hold("Spot: M", 5, [(kind, 2, 3), (area, 2, 9), (area_v, 2, 5)], 12)]
    run.joinpath("proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in odd + stated), encoding="utf-8")
    proofs, skip, _, _, _ = R.report_proofs(run)
    assert R.stood_rows(proofs, skip) == {} and R.stood_out(run, proofs, skip, {}, set(), frozenset()) == set()
    # the same option writing a record otherwise under the stated lines: a disagreement, never left out
    clash = [bare[0], hold("Spot: M", 5, [(kind, 2, 3), (area, 2, 3), (area_v, 2, 5)], 12)]
    run.joinpath("proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in clash + stated), encoding="utf-8")
    proofs, skip, _, _, _ = R.report_proofs(run)
    assert R.stood_rows(proofs, skip) == {}
    # a name the stated lines back with fewer readers: found by stood_rows, kept by stood_out
    read = [dict(bare[0], shown="Center Fix", vlm="Center Fix"), bare[1]]
    run.joinpath("proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in read + stated), encoding="utf-8")
    proofs, skip, _, _, _ = R.report_proofs(run)
    assert set(R.stood_rows(proofs, skip)) == {menu[0]} and R.stood_out(run, proofs, skip, {}, set(), frozenset()) == set()
    # lines that name fewer states than the row: no row stands for one naming more
    more = [dict(p, context="Movie mode, Focus Mode = AF-C") for p in movie]
    run.joinpath("proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in more + still), encoding="utf-8")
    proofs, skip, _, _, _ = R.report_proofs(run)
    assert R.stood_rows(proofs, skip) == {}


@needs_evidence
def test_the_definition_lists_neither_the_bare_registration_row_nor_focus_areas_movie_mode_row():
    """The ILCE-1M2's proofs' menu rows (evidence): neither the bare AF Area Registration row nor Focus Area's Movie
    mode row, which gave way to the rows that name the state (stood_out, above); the registrations list the row that
    says Switch V/H AF Area Off."""
    menu = ("AF Area Registration On, Fn held on the shooting screen",)
    menus = {s["key"]: (s.get("proved") or {}).get("menu") or [] for s in DOC["settings"]}
    assert not [k for k, m in menus.items() if menu[0] in m or "Focus Area [Movie mode]" in m]
    assert all(f"{menu[0]} [Switch V/H AF Area Off]" in menus[k] for k in ("global:0x0e7a", "global:0x0f80",
                                                                           "global:0x0e74", "global:0x0f8c"))


def test_a_stated_line_backs_a_change_only_under_the_same_option(tmp_path):
    """pass2_report.stood_rows checks each change of the row's lines against the lines that stand for it chosen with the
    same option: one writing that record to that value, or one leaving it alone while its base download already holds
    that value; never a value pooled from another option. Case A (made up): the bare row's option A writes K = 5; the
    stated rows' A leaves K alone where their base holds 3 and their C writes K = 5. Pooled, A's 5 would read as backed,
    the bare row would go and the report would give A the base's 3 and C the 5, hiding a disagreement; so the row
    stays, and with the stated base holding 5 it goes. Case D: a side record the bare A wrote (S = 7), which the stated A
    leaves alone where its base holds 7: backed; where the base holds 4, not."""
    import pass2_report as R
    k, side, ctx = "global:0x0e7a", "global:0x0f80", "Switch V/H AF Area = Off"
    row = ("Made Up Row",)

    def line(lab, i, changes, frame, **more):
        return dict(proof(lab, i, changes, frame=frame, path=row), **more)
    for stated_k, stays in ((3, True), (5, False)):
        bare = [line("A", 0, [(k, 3, 5)], 10), line("B", 1, [(k, 5, 1)], 12)]
        stated = [line("A", 0, [], 20, context=ctx, base="00090_base.DAT"),
                  line("B", 1, [(k, stated_k, 1)], 22, context=ctx, base="00090_base.DAT"),
                  line("C", 2, [(k, stated_k, 5)] if stated_k != 5 else [(k, 1, 5)], 24, context=ctx,
                       base="00090_base.DAT")]
        run = write_run(tmp_path / f"a{stated_k}", bare + stated)
        made_base(run, "00090_base.DAT", {k: stated_k})
        proofs, skip, _, _, _ = R.report_proofs(run)
        assert (R.stood_rows(proofs, skip) == {}) is stays, (stated_k, R.stood_rows(proofs, skip))
    for held, stays in ((7, False), (4, True)):
        bare = [line("A", 0, [(k, 3, 1), (side, 2, 7)], 10)]
        stated = [line("A", 0, [(k, 3, 1)], 20, context=ctx, base="00090_base.DAT")]
        run = write_run(tmp_path / f"d{held}", bare + stated)
        made_base(run, "00090_base.DAT", {side: held})
        proofs, skip, _, _, _ = R.report_proofs(run)
        assert (R.stood_rows(proofs, skip) == {}) is stays, (held, R.stood_rows(proofs, skip))


def test_a_context_in_words_names_the_state_of_a_row_the_proofs_walk(tmp_path):
    """pass2_report.state_row: a context item names a row's state as "Row = option", or in words, "Row option" or "Row:
    option", Row being a row the proofs walk (walked_rows), its option words holding no ":" of their own; an item naming
    no walked row names nothing. says_of: an item speaks of a row it names or a part of it, or, naming no row's state,
    holds its name as whole words that start no longer row's name; "Focus Area Limit = ..." says nothing of Focus Area.
    So a row with no context gives way to rows of the same row whose contexts name Recording Media's state in words, as
    pass 3's do, and prove all it proves; not where no proof walks a Recording Media row. Made-up proofs."""
    import pass2_report as R
    walked = {R.norm(n): n for n in ("Recording Media", "Shoot Mode", "Exposure step", "File Format", "Focus Area",
                                     "Focus Area Limit", "Switch V/H AF Area", "Mode Dial Control Set")}
    said = {"Recording Media Sort Recording": "Recording Media", "Recording Media on one slot": "Recording Media",
            "Shoot Mode A (dial set with the menu)": "Shoot Mode", "Exposure step 0.5EV": "Exposure step",
            "File Format: SLOT 1 JPEG": "File Format", "Switch V/H AF Area Off": "Switch V/H AF Area",
            "Monitor Brightness > Brightness Setup = Manual": "Monitor Brightness > Brightness Setup",
            "Movie mode": None, "camera level": None, "PAL": None, "Spot size last left: XL then M": None,
            "Focus Area Limit: Wide": "Focus Area Limit"}
    assert {w: R.state_row(w, walked) for w in said} == said
    assert R.named_states({"context": "Shoot Mode A (dial set with the menu), Recording Media Sort Recording"},
                          walked) == {"Shoot Mode", "Recording Media"}
    assert R.named_states({"context": "Recording Media Sort Recording"}) == frozenset(), "words need the walked rows"

    def speaks(ctx, row):
        return R.says_of({"context": ctx}, row, walked)
    assert speaks("Switch V/H AF Area Off", "Switch V/H AF Area")
    assert speaks("Mode Dial Control Set / Drive Mode Dial = Set with Menu", "Mode Dial Control Set")
    assert not speaks("Focus Area Limit = Wide", "Focus Area"), "a longer row's name"
    assert speaks("the hold's Focus Area Wide", "Focus Area"), "in words naming no row's state"
    assert not speaks("the hold's Focus Area Limit", "Focus Area")
    assert not speaks("Movie mode, PAL", "Recording Media")
    k1, k2, ka = "global:0x0001", "global:0x0002", "global:0x0004"
    path = ("Made Up Switch",)
    bare = [proof("HEIF", 1, [(k1, 0, 1), (k2, 1, 2)], frame=10, path=path), proof("JPEG", 0, [], frame=12, path=path)]
    words = "Shoot Mode A (dial set with the menu), Recording Media Sort Recording"
    stated = [dict(proof("HEIF", 1, [(k1, 0, 1), (k2, 1, 2), (ka, 1, 2)], frame=20, path=path), context=words),
              dict(proof("JPEG", 0, [(k1, 1, 0), (k2, 2, 1), (ka, 2, 1)], frame=22, path=path), context=words)]
    walks = [proof("On", 1, [("global:0x0003", 0, 1)], frame=30, path=("Recording Media",))]
    run = write_run(tmp_path, bare + stated + walks)
    proofs, skip, _, _, _ = R.report_proofs(run)
    assert set(R.stood_rows(proofs, skip)) == {"Made Up Switch"}
    proofs, skip, _, _, _ = R.report_proofs(write_run(tmp_path / "b", bare + stated))
    assert R.stood_rows(proofs, skip) == {}, "no walked Recording Media row: the words name nothing"


def test_a_setting_tables_cells_are_named_by_their_row_as_all_its_cells_read_it(tmp_path):
    """kit/table_walk.py reads a cell's row label from the screen's left edge to the cell, so a cell further right reads
    the values of the cells before it glued on ("File Format RAW" on Slot 2, "Rear Dial L -- --" on My Dial 3), and an
    icon before it as a letter or a mark: values the camera held (decision 16). match.table_row_label names a row by the
    stretch all its readings share, cleaned; table_jobs names new cells so, and match.cell_options renames the lines
    written before by the walked cell at their place (pass2_report.report_proofs). A record named for the cell's row (File Format (Slot 1)) is that row's
    though another row writes it too (own_name). The ILCE-1M2's definition names no table cell with a value glued on."""
    import pass2_report as R
    from camkit import match
    assert match.table_row_label(["dFile Format", "•File Format RAW"]) == "File Format"
    assert match.table_row_label(["Tir Rear Dial R", "T Rear Dial R --", "T Rear Dial R -- --"]) == "Rear Dial R"
    assert match.table_row_label(["mFront dial", "wFront dial --", "•Front dial --"]) == "Front dial"
    assert match.table_row_label(["JPEG Quality X.FINE"]) == "JPEG Quality X.FINE", "read once: as read, cleaned"
    assert match.table_row_label(["• Control Wheel -- --"]) == "Control Wheel"
    k = "global:0x01e6"
    cells = [dict(proof("JPEG", 1, [(k, 0, 1)], frame=10, path=("Image Quality Settings",), kind="table"),
                  option="dFile Format / SLOT 1", cell=[376, 120], screen="table"),
             dict(proof("RAW", 0, [], frame=12, path=("Image Quality Settings",), kind="table"),
                  option="dFile Format / SLOT 1", cell=[376, 120], screen="table"),
             dict(proof("RAW", 1, [("global:0x01f2", 1, 0)], frame=14, path=("Image Quality Settings",), kind="table"),
                  option="•File Format RAW / SLOT 2", cell=[548, 120], screen="table"),
             dict(proof("Not set", 3, [("global:0x045f", 1, 3)], frame=16, path=("Fn Menu Settings",), kind="table"),
                  option="Still Upper / 1", cell=[0, 1], screen="fnmenu")]
    walked = {"Image Quality Settings": {"path": ["Image Quality Settings"], "screen": "table", "nth": 0, "cells": [
        {"pos": [376, 120], "row_label": "dFile Format", "col_label": "SLOT 1"},
        {"pos": [548, 120], "row_label": "•File Format JPEG", "col_label": "SLOT 2"}]}}
    named, unwalked = match.cell_options(cells, walked)
    assert [c["option"] for c in named] == ["File Format / SLOT 1", "File Format / SLOT 1", "File Format / SLOT 2",
                                            "Still Upper / 1"] and unwalked == {}
    assert R.own_name(named[0]) == "File Format" and R.own_name(named[3]) == "Fn Menu Settings"
    other = dict(proof("HEIF", 2, [(k, 1, 2)], frame=30, path=("Made Up Switch",)), context="Recording Media = Slot 1")
    run = write_run(tmp_path, cells + [other])
    (tmp_path / "kit2_tables").mkdir()
    (tmp_path / "kit2_tables" / "tables.json").write_text(json.dumps(walked), encoding="utf-8")
    proofs, skip, _, _, _ = R.report_proofs(run)
    rows = R.rows_of(run, proofs, skip)
    assert "Image Quality Settings / File Format / SLOT 1" in rows
    owners = {row: {c["key"] for o in opts.values() for c in o.get("changes") or []} for row, opts in rows.items()}
    elsewhere = frozenset(x for row, keys in owners.items() if not row.startswith("Image Quality") for x in keys)
    got = R.values_of(rows["Image Quality Settings / File Format / SLOT 1"], elsewhere, {k: "File Format (Slot 1)"})
    assert got[k] == {"JPEG": 1, "RAW": 0}, "the cell's own record, another row's too"


@needs_evidence
def test_no_table_cells_proof_row_has_a_value_glued_on():
    """The ILCE-1M2's proofs' menu rows (evidence) name no table cell with a value glued on (match.table_row_label, as
    above)."""
    from camkit import match
    menus = [r for s in DOC["settings"] for r in (s.get("proved") or {}).get("menu") or []]
    tables = [r for r in menus if r.startswith(("Image Quality Settings / ", "My Dial Settings / "))]
    assert tables and all(match.table_row_label([r.split(" / ")[1]]) == r.split(" / ")[1] for r in tables), tables


def test_a_record_proved_in_another_run_names_that_run_and_the_day_of_its_latest_proof(tmp_path):
    """pass2_report: a proof of another run is dated by its own download in that run's link log (download_days), else
    by the day the run began (run_date); a main-run proof carries no day (the writer dates the main run as it always
    has). A record names the run of its latest proof (latest_run), the main run when only the main run proved it.
    Made-up runs and logs."""
    import datetime
    import pass2_report as R
    day = lambda d: datetime.datetime.fromisoformat(f"{d}T12:00:00").timestamp()
    side = tmp_path / "kit2_side"
    side.mkdir()
    (side / "events.jsonl").write_text("".join(json.dumps(x) + "\n" for x in (
        {"t": day("2026-11-03"), "kind": "link_open"},
        {"t": day("2026-11-05"), "kind": "cmd", "reply": {"ok": True, "path": "/x/kit2_side/dat/00009_after.DAT"}})),
        encoding="utf-8")
    assert R.proof_day({"run": "kit2_side", "dat": "kit2_side/00009_after.DAT"}, tmp_path) == "2026-11-05"
    assert R.proof_day({"run": "kit2_side", "dat": "kit2_side/00002_x.DAT"}, tmp_path) == "2026-11-03", "the run's start"
    assert R.proof_day({"dat": "00009_after.DAT"}, tmp_path) is None, "a main-run proof"
    opts = {0: dict(proof("A", 0, [("global:0x0001", 0, 1)]), run="kit2_side", dat="kit2_side/00009_after.DAT"),
            1: proof("B", 1, [("global:0x0001", 1, 2)])}
    came = R.record_runs(opts, {"A": 1, "B": 2}, {}, "kit2_pass2", tmp_path)
    assert came == {"kit2_pass2": None, "kit2_side": "2026-11-05"}
    assert R.record_runs(opts, {"B": 2}, {}, "kit2_pass2", tmp_path) == {"kit2_pass2": None}
    assert R.latest_run(came, "kit2_pass2", "2026-10-29") == ("kit2_side", "2026-11-05")
    assert R.latest_run({"kit2_pass2": None}, "kit2_pass2", "2026-10-29") == ("kit2_pass2", "2026-10-29")
    assert R.latest_run({}, "kit2_pass2", "2026-10-29") == ("kit2_pass2", "2026-10-29")


def test_a_box_unticked_on_its_own_is_its_items_row_in_the_state_it_needs():
    """filter_run.py --untick's proof (label "Not ticked", index 0) is its item's row with the box ticked, apart from the
    chooser's options (its index 0 would take the first option's place) and credited with the box alone."""
    import pass2_report as R
    untick = {"path": ["Playback Filter Condition", "Protect"], "kind": "list", "index": 0, "label": "Not ticked",
              "untick": True, "applied": True, "changes": [{"key": "global:0x0001", "before": 1, "after": 0}]}
    assert R.row_name(untick) == "Playback Filter Condition > Protect [box ticked]"
    assert R.row_name(dict(untick, context="Movie mode")) == "Playback Filter Condition > Protect [Movie mode, box ticked]"
    assert R.row_name({k: v for k, v in untick.items() if k != "untick"}) == "Playback Filter Condition > Protect"
    assert R.values_of({0: untick}) == {"global:0x0001": {"Not ticked": 0}}


def test_a_non_tracking_hold_is_credited_no_tracking_start_area():
    """AF Area Registration: a Tracking area's hold writes the Tracking start area copies; any other area's hold copies
    the start area in use, the camera's own setting, which the prover keeps out of its changes. The report credits a
    start area copy to Tracking areas only (WRITTEN_BY), never to another area from "nothing changed". Made-up values."""
    import pass2_report as R
    kind, start = "global:0x0e7a", "global:0x0e74"
    opts = {2: proof("Center Fix", 2, [(kind, 0, 2)], base="b1.DAT"),
            16: proof("Tracking: Spot L", 16, [(start, 7, 5), (kind, 2, 6)], base="b2.DAT")}
    got = R.values_of(opts)
    assert got[start] == {"Tracking: Spot L": 5} and got[kind] == {"Center Fix": 2, "Tracking: Spot L": 6}
    assert {start, "global:0x0e76", "global:0x0e78", "global:0x0f8c", "global:0x0f8e", "global:0x0f90"} <= set(R.WRITTEN_BY)


def test_a_record_a_proof_names_as_a_side_effect_is_never_credited_to_its_option(monkeypatch):
    """Any body (no hand rule: WRITTEN_BY empty, as for a camera other than the a1 II): a record a proof names in its
    "side_effects" (by key, as afreg_run writes them, or with its values, as a by-hand proof records them) is no value of
    that proof's option, whether the visit changed it or not, so "nothing changed" never credits what it held to the
    option; a proof that wrote the record is credited as ever. Made-up records and values."""
    import pass2_report as R
    monkeypatch.setattr(R, "WRITTEN_BY", {})
    kind, copy = "global:0x0101", "global:0x0201"
    held = dict(proof("A", 0, [(kind, 0, 1)], base="b1.DAT", path=("Hold",)), side_effects=[copy])
    wrote = proof("B", 1, [(kind, 1, 2), (copy, 3, 4)], base="b2.DAT", path=("Hold",))
    by_hand = dict(proof("C", 2, [(kind, 2, 3)], base="b3.DAT", path=("Hold",)),
                   side_effects=[{"key": copy, "before": 4, "after": 9}])
    got = R.values_of({0: held, 1: wrote, 2: by_hand})
    assert got[copy] == {"B": 4} and got[kind] == {"A": 1, "B": 2, "C": 3}
    plain = {k: v for k, v in held.items() if k != "side_effects"}
    assert R.values_of({0: plain, 1: wrote})[copy] == {"A": 3, "B": 4}, "named nowhere: nothing changed credits it"


def test_registered_af_areas_carry_no_hand_proof():
    """The Registered AF area records' hand table (REG in kit/writer/a1_tables.py), public or with its evidence: twelve
    records, none with a proof of the table's own (their proof is the report's), every name standing against the
    lines' labels (KEEP_LABELS)."""
    import schema_update as S
    reg = [k for k, fp in S.FRAME_PROOFS.items() if fp["note"].startswith(S.REG_NOTE)]
    assert len(reg) == 12 and all("proved" not in S.FRAME_PROOFS[k] for k in reg) and set(reg) <= S.KEEP_LABELS


@needs_evidence
def test_registered_af_areas_are_proved_by_their_proof_lines_alone(tmp_path, monkeypatch, capsys):
    """The Registered AF area records' hand table (REG in kit/writer/a1_tables.py) names them, their values and the
    note, and carries no proof (FRAME_PROOFS without "proved"): their proof is the report's, whole, so a value the table
    once listed that no proof line credits goes, and their names stand against the lines' labels (KEEP_LABELS). A
    record left out of the report keeps the proof it has. Made-up report."""
    import schema_update as S
    reg = [k for k, fp in S.FRAME_PROOFS.items() if fp.get("menu") == "AF Area Registration On, Fn held on the shooting screen"]
    assert len(reg) == 12 and all("proved" not in S.FRAME_PROOFS[k] for k in reg) and set(reg) <= S.KEEP_LABELS
    row = "AF Area Registration On, Fn held on the shooting screen [made-up state]"
    report = A1_REPORT + [{"row": row, "options": 1, "notices": [], "kinds": ["list"], "records": {
        "global:0x0e76": {"verdict": "agrees", "schema_name": "x", "proved": {"Tracking: Wide": 0}, "linear": None,
                          "notes": [], "names": {"Tracking: Wide": "two readers"}}}}]
    _, target, write = a1_run(tmp_path, monkeypatch, report, A1_PROOFS)
    before = {s["key"]: s for s in definitions.load(target)["settings"]}
    write(capsys)
    after = {s["key"]: s for s in definitions.load(target)["settings"]}
    assert after["global:0x0e76"]["proved"]["values"] == [0] and after["global:0x0e76"]["proved"]["menu"] == [row]
    assert dict(after["global:0x0e76"]["values"]) == dict(before["global:0x0e76"]["values"]), "the table's names stand"
    assert after["global:0x0e74"]["proved"] == before["global:0x0e74"]["proved"], "not in the report: kept as it was"


# ---------------------------------------------------------------- why no proof can reach a setting (2026-11-09)

def test_every_setting_no_proof_can_reach_says_why_in_a_kind_the_schema_knows():
    """Each setting without a proof that the a1 II's hand table names (UNPROVED) carries its reason, kind and why,
    and a reason is only ever on a setting with no proof; every kind is one the definition schema lists, each kind
    the table uses has words the editor shows, and the why is a photographer's (the mapping-words test reads it)."""
    import schema_update as S
    schema = json.loads((ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))
    props = schema["$defs"]["setting"]["properties"]
    kinds = props["unproved_reason"]["properties"]["kind"]["enum"]
    assert kinds == props["unproved_sets"]["properties"]["kind"]["enum"]
    assert {"not_on_camera", "skipped", "state", "camera_only", "equipment", "network", "unknown"} == set(kinds)
    assert {kind for kind, _, _ in S.UNPROVED.values()} <= set(kinds)
    for k, (kind, date, why) in S.UNPROVED.items():
        s = DOC_BY[k]
        if s.get("proved"):
            assert "unproved_reason" not in s, k
        else:
            got = s["unproved_reason"]        # its day is evidence: in the whole definition only (camkit.definitions)
            assert {f: v for f, v in got.items() if f != "date"} == {"kind": kind, "why": why} and \
                got.get("date", date) == date, k
        # the day is the hand evidence's (None in the public table, kit/writer/hand_evidence.py)
        assert (date is None if S.HAND_EVIDENCE is None else re.fullmatch(r"20\d\d-\d\d-\d\d", date)) and why.endswith("."), k
    with_reason = [s for s in DOC["settings"] if s.get("unproved_reason")]
    assert with_reason and not [s["key"] for s in with_reason if s.get("proved")]
    assert {s["unproved_reason"]["kind"] for s in with_reason} <= set(kinds)
    rust = (ROOT / "editor" / "src" / "schema.rs").read_text(encoding="utf-8")
    assert all(f'"{kind}" =>' in rust for kind in kinds), "the editor's words (unproved_words) for every kind"


def test_the_proof_viewer_says_each_reason_in_the_editors_words():
    """The proof viewer (kit/tools/proof_viewer.html, WHY) names each kind of reason no proof can reach a setting with
    the words the editor shows for it (editor/src/schema.rs, unproved_words; decision 14: one wording), for every kind
    the definition schema lists, and no kind the schema does not."""
    schema = json.loads((ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))
    kinds = schema["$defs"]["setting"]["properties"]["unproved_reason"]["properties"]["kind"]["enum"]
    rust = (ROOT / "editor" / "src" / "schema.rs").read_text(encoding="utf-8")
    body = rust[rust.index("pub fn unproved_words"):]
    body = body[:body.index("\n}\n")]
    editor = dict(re.findall(r'"(\w+)" => \("([^"]+)", "[^"]+"\)', body))
    html = (ROOT / "kit" / "tools" / "proof_viewer.html").read_text(encoding="utf-8")
    block = re.search(r"const WHY = \{(.*?)\};", html, re.S)
    assert block, "the viewer's WHY table"
    viewer = dict(re.findall(r'(\w+): "([^"]+)"', block.group(1)))
    assert set(editor) == set(kinds) and viewer == editor, {k: (viewer.get(k), editor.get(k)) for k in kinds}


def test_replay_takes_the_side_runs_and_leaves_a_proofs_side_effects_out(tmp_path, capsys):
    """replay_proofs on the main run replays the camera's other proof runs too, each with its own summary line; a
    record a proof names as a side effect (afreg_run's by key, a by-hand proof's with its values) is no difference.
    Made-up files written through the camera's block (never uploaded)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("replay_proofs", ROOT / "kit" / "tools" / "replay_proofs.py")
    RP = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RP)
    cs = camset.read(SAMPLE)
    a, b = cs.get(0, 0x0489), cs.get(0, 0x0350)
    two = {(0, 0x0489): bytes([(a.raw[0] + 1) % 4]) + a.raw[1:], (0, 0x0350): bytes([(b.raw[0] + 1) % 3]) + b.raw[1:]}
    main, side = tmp_path / "kit2_pass2", tmp_path / "kit2_afreg2"
    for run in (main, side):
        (run / "dat").mkdir(parents=True)
        (run / "dat" / "00001_base.DAT").write_bytes(SAMPLE.read_bytes())
        (run / "dat" / "00002_after.DAT").write_bytes(camset.with_values(cs, two))
    from camkit import runs
    runs.mark_proof_run(side, "made up")
    now = {c.key: c for c in camset.diff(cs, camset.read(side / "dat" / "00002_after.DAT"))}
    change = lambda k: {"key": k, "before": now[k].before, "after": now[k].after}
    line = lambda side_effects: {"path": ["Hold"], "label": "A", "base": "00001_base.DAT", "dat": "00002_after.DAT",
                                 "changes": [change("global:0x0489")], "side_effects": side_effects}
    (main / "proofs.jsonl").write_text(json.dumps(line([change("global:0x0350")])) + "\n", encoding="utf-8")
    (side / "proofs.jsonl").write_text(json.dumps(line(["global:0x0350"])) + "\n", encoding="utf-8")
    assert RP.main([str(main), "--quiet"]) == 0
    said = capsys.readouterr().out.splitlines()
    assert len(said) == 2 and all("1 proofs diffed again, 1 the same" in s for s in said), said
    assert RP.main([str(main), "--quiet", "--alone"]) == 0 and len(capsys.readouterr().out.splitlines()) == 1
    (side / "proofs.jsonl").write_text(json.dumps(line([])) + "\n", encoding="utf-8")
    assert RP.main([str(main), "--quiet"]) == 1, "a record no proof names is a difference"


def mirror(record, index, label, live=None, applied=True, slot="1", dat="00030_after.DAT", allowance=None):
    """A made-up registration mirror line (memreg_run.py's with `live`, framepos_run.py --zone-grid's without)."""
    key = record.replace("set:", "set1:", 1)
    return {"path": ["Camera Set. Memory", label], "menu": "Camera Set. Memory", "kind": "registration mirror",
            "record": record, **({"live": live} if live else {}), "key": key, "index": index, "label": label,
            "slot": slot, "base": "00020_before.DAT", "dat": dat, "after": dat,
            "changes": [{"key": key, "before": 0, "after": index}], "applied": applied,
            **({"allowance": allowance} if allowance else {})}


def test_registration_mirror_lines_are_no_rows_and_feed_the_writer(tmp_path):
    """A registration mirror line (memreg_run.py's, framepos_run.py --zone-grid's) is no row's proof: report_proofs
    leaves it out, registration_mirrors hands each live record its run, day, slot and allowance (keys only, never a
    value), mirrored_values the values registered into a memory record no live record holds; an unapplied line gives
    nothing, and an unmarked run is not read. Made-up lines."""
    import pass2_report as R
    from camkit import runs
    main = write_run(tmp_path, [proof("A", 0, [("global:0x0001", 0, 1)], "a1", frame=10)], done=["a1"])
    side = tmp_path / "kit2_memtwins"
    side.mkdir()
    words = "the owner allowed Camera Set. Memory remotely, 2026-01-02"
    lines = [mirror("set:0x0003", 1, "On", live="global:0x0003", allowance=words),
             mirror("set:0x0004", 2, "Upper", slot="2"),
             mirror("set:0x0004", 5, "Lower", dat="00031_after.DAT"),
             mirror("set:0x0005", 1, "Off", live="global:0x0005", applied=False)]
    (side / "proofs.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    assert R.registration_mirrors(main) == {} and R.mirrored_values(main) == {}, "an unmarked run is not read"
    runs.mark_proof_run(side, "made up")
    proofs, skip, _, _, _ = R.report_proofs(main)
    assert [p["label"] for p in proofs] == ["A"] and skip == set(), "the mirror lines are no row's proofs"
    lives = R.registration_mirrors(main)
    assert set(lives) == {"global:0x0003"}
    assert lives["global:0x0003"]["run"] == "kit2_memtwins" and lives["global:0x0003"]["slot"] == 1
    assert lives["global:0x0003"]["allowance"] == words and re.fullmatch(r"\d{4}-\d\d-\d\d", lives["global:0x0003"]["date"])
    held = R.mirrored_values(main)
    assert set(held) == {"set:0x0004"} and held["set:0x0004"]["values"] == {2: "Upper", 5: "Lower"}
    assert held["set:0x0004"]["run"] == "kit2_memtwins"


def test_a_proofs_allowance_reaches_the_records_it_proved():
    """record_allowances: the owner's word a proof line carries (prove_run.py and scale_run --allow) goes with the
    records its option's values come from; a row with none gives none. Made-up options."""
    import pass2_report as R
    words = "the owner allowed Audio Signal Volume remotely, 2026-01-02"
    opts = {0: dict(proof("1", 0, [("global:0x0001", 2, 1)]), allowance=words), 1: proof("2", 1, [("global:0x0001", 1, 0)])}
    assert R.record_allowances(opts, {"1": 1, "2": 0}, {}) == [words]
    assert R.record_allowances({1: opts[1]}, {"2": 0}, {}) == []


def test_an_allowance_goes_into_the_evidence_once():
    """add_evidence puts a part of evidence (the owner's allowance) after the note's evidence once, splitting a note a
    table has just written whole as from_data would; note_is reads a note with an allowance added as the table's, so
    a rerun writes nothing again; a part with no day or run is refused. Made-up notes."""
    from writer.notes import add_evidence, note_is, with_evidence_apart
    words = "the owner allowed Some Row(Its Part) remotely, 2026-01-02"
    s = {"key": "global:0x0001", "name": "A", "note": "", "in_sets": True}
    assert add_evidence(s, words) and list(s)[:4] == ["key", "name", "note", "note_evidence"]
    assert s["note"] == "" and s["note_evidence"] == words and not add_evidence(s, words)
    table = "It does a thing (runs/kit2_x, 2026-01-01)."
    t = {"key": "global:0x0002", "note": table}
    assert add_evidence(t, words) and t["note"] == "It does a thing." and with_evidence_apart(t) == t
    assert t["note_evidence"] == f"runs/kit2_x, 2026-01-01; {words}" and note_is(t, table) and not add_evidence(t, words)
    # a table's note written whole with the same words in it (its own "allowance"): taken apart, nothing added, the
    # evidence right after the note
    plain = "the owner allowed Some Row remotely, 2026-01-02"
    whole = f"It does a thing (2026-01-01; {plain})."
    u = {"key": "global:0x0003", "note": whole, "in_sets": True, "proved": {}}
    assert not add_evidence(u, plain) and list(u) == ["key", "note", "note_evidence", "in_sets", "proved"]
    assert u["note"] == "It does a thing." and u["note_evidence"] == f"2026-01-01; {plain}" and note_is(u, whole)
    v = {"key": "global:0x0004", "note": "It does a thing.", "in_sets": True, "note_evidence": plain}
    assert not add_evidence(v, plain) and list(v) == ["key", "note", "note_evidence", "in_sets"]
    with pytest.raises(ValueError):
        add_evidence(t, "no day here")


def test_a_registrations_proof_of_the_memory_copy_sits_after_in_sets():
    """with_in_sets_proved writes {"run", "date", "slot"} right after in_sets, in place (callers hold the settings by
    key), takes an old one off a setting no line names, and marks none where the definition keeps the setting out of
    the sets. Made-up settings."""
    from writer.proofs import with_in_sets_proved
    a = {"key": "global:0x0001", "name": "A", "note": "", "in_sets": True, "scalar": True}
    b = {"key": "global:0x0002", "name": "B", "note": "", "in_sets": False, "scalar": True}
    doc = {"settings": [a, b]}
    got = {"run": "kit2_x", "date": "2026-01-02", "slot": 1, "allowance": "the owner allowed X remotely, 2026-01-02"}
    assert with_in_sets_proved(doc, {"global:0x0001": got, "global:0x0002": got}) == 1
    assert doc["settings"][0] is a and list(a) == ["key", "name", "note", "in_sets", "in_sets_proved", "scalar"]
    assert a["in_sets_proved"] == {"run": "kit2_x", "date": "2026-01-02", "slot": 1} and "in_sets_proved" not in b
    assert with_in_sets_proved(doc, {}) == 0 and "in_sets_proved" not in a


FRAMEPOS = ["set:0x019a", "set:0x0f0b", "set:0x0f0d", "set:0x0f2c", "set:0x0f2e", "set:0x0f30", "set:0x019c",
            "set:0x019e", "set:0x01be", "set:0x01c0", "set:0x01c2", "set:0x01c4", "set:0x01c6", "set:0x01c8"]


def test_the_frame_steps_come_from_one_table_in_the_public_files():
    """The public half of the hand tables of 2026-11-09 and the public definition: the steps a press moved under AF
    Frame Move Amt Standard and Large come from one table (FRAME_STEPS) through its sentences (STEP_FACTS), which stand
    word for word in the public notes, AF Frame Move Amt's, the model page's row and the changelog's entry, and nowhere
    else a number does: no position, no size, the Custom 1 box's steps under Large twice Standard's; no word says where
    a frame stood. AF Frame Move Amt's hand entry is a note only, its proof the report's; the Custom boxes' place
    records are 26 new memory set records laid out like the spot's."""
    import schema_update as S
    from writer import a1_tables as T
    steps = {n for xy in T.FRAME_STEPS.values() for v in xy if v is not None for n in re.findall(r"\d+", str(v))}
    assert all(isinstance(v, int) for xy in T.FRAME_STEPS.values() for v in xy)
    assert T.FRAME_STEPS[("Large", "Custom 1")] == tuple(2 * v for v in T.FRAME_STEPS[("Standard", "Custom 1")])
    for phrase in T.STEP_FACTS.values():
        assert set(re.findall(r"\d+", phrase.replace("Custom 1", ""))) <= steps, phrase
    boxes = [k for k in S.NEW_RECORDS if k.startswith("set:0x13") and "box position" in S.NEW_RECORDS[k]["name"]]
    assert len(boxes) == 26 and all(S.NEW_RECORDS[k]["like"] == "set:0x019c" for k in boxes)
    amt_note = PUB_BY["global:0x03a3"]["note"]
    row = next(ln for ln in (ROOT / "docs" / "models" / "ILCE-1M2_fw4.00.md").read_text(encoding="utf-8").splitlines()
               if ln.startswith("| Focus frame position |"))
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = log[log.index("- The notes of the ILCE-1M2's focus point"):]
    entry = entry[:entry.index("\n- ")]
    assert T.STEP_FACTS["point"] in T.FRAMEPOS_POINT and T.STEP_FACTS["box"] in T.BOX_PLACE
    assert T.STEP_FACTS["all"] in amt_note and T.STEP_FACTS["all"] in row
    written = {k: PUB_BY[k] for k in FRAMEPOS + boxes + ["global:0x03a3"] if k in PUB_BY}
    for k, s in written.items():
        want = "all" if k == "global:0x03a3" else "box" if k in boxes else "point" if k not in FRAMEPOS[:6] else None
        assert want is None or T.STEP_FACTS[want] in s["note"], k
    forbidden = re.compile(r"\b(?:edge|limit|travel|near|side|stood|further)\b|\b(?:stop|short|border|boundar|clamp|corner)\w*"
                           r"|\b(?:less|more) than\b|on the way|from the centre", re.I)
    geometry = r"640 x 480|3 x 3|\(320, 240 = centre\)|\(0 centre, [^)]*\)|slot 1|Custom [123]|copy [1-4]|ILCE-1M2|0x[0-9a-f]{4}"

    def bare(text: str) -> str:
        for phrase in T.STEP_FACTS.values():
            text = text.replace(phrase, "")
        return re.sub(geometry, "", text)
    texts = [T.AF_NOTE, T.VERT, T.FRAMEPOS_POINT, T.BOX_PLACE, T.BOX_COPIES, amt_note, row, entry]
    texts += [s["note"] for k, s in written.items() if k not in FRAMEPOS[:6]]
    for text in texts:
        assert not re.search(r"\d", bare(text)) and not forbidden.search(text), (bare(text), text)
    for text in (T.FRAMEPOS_POINT, T.BOX_PLACE):
        assert "AF Frame Move Amt Standard" in text and "kit2_" not in text, text
    assert "a step AF Frame Move Amt sets, the same for Spot S, M, L and XL and Expand Spot and smaller for Spot XS" in T.FRAMEPOS_POINT
    assert "differ" not in T.BOX_PLACE and "moving with the presses" in T.BOX_PLACE and "moved Custom 1's box" in T.BOX_PLACE
    assert "Spot XS's step is smaller than Spot M's across (and, under Large, up and down too)" in entry
    assert not {"values", "proved", "sampled", "run", "date"} & set(S.FRAME_PROOFS["global:0x03a3"])
    assert "global:0x03a3" not in S.by_lines_of(S.FRAME_PROOFS)


@needs_evidence
def test_tonights_hand_tables_hold_proofs_only():
    """The ILCE-1M2's hand tables of 2026-11-09: a put-back is no sample, the camera's factory setting or not (a value a
    round started from and put back is the camera's own: docs/decisions/0016), so the volume and brightness rounds
    list only the values they chose, and none of those scales is on a line; their notes name no put-back; the four
    volume scales, the monitor's and the viewfinder's manual brightness and Finder Color Temp. proved on the camera
    since (runs/kit2_pass2, every value) keep a note alone in the hand tables (the two brightness rows' with their
    remote looks' allowance), and their proof is the report's, every code of the scale in table order, each named by
    its readers as pass2_report.name_of gives; the viewfinder's two notes say its rows open only with the finder in
    use; Custom slot last left is proved in full; the Custom boxes' place records are new memory set records laid out like the spot's, sampled from their two
    registrations; the steps a press moved under AF Frame Move Amt Standard and Large, which the step run set by the
    menu, come from one table (FRAME_STEPS) through its sentences (STEP_FACTS), which stand word for word in the notes,
    AF Frame Move Amt's, the model page's row and nowhere else a number does: no position, no size, the Custom 1 box's
    steps as one press each way measured them (Large's twice Standard's), none of the words that would say where a
    frame stood; AF Frame Move Amt's note leaves its proof to
    the report; the records whose notes took the frame positions run's facts carry its allowance, as the records its
    proof lines credit do."""
    import schema_update as S
    by_key = {s["key"]: s for s in DOC["settings"]}
    remote = {"global:0x0051": 16, "global:0x03c4": 16, "global:0x12c8": 6, "global:0x0479": 16, "global:0x0052": 5,
              "global:0x0c89": 5, "global:0x047d": 5}
    for k, n in remote.items():
        assert set(S.FRAME_PROOFS[k]) <= {"note", "allowance"}, k        # no values, no proof: the report's stand
        assert "every value since proved on the camera by the kit" in S.FRAME_PROOFS[k]["note"], k
        p = by_key[k]["proved"]
        assert p["run"] == "kit2_pass2" and p["values"] == list(range(n)), k
        assert not {"sampled", "inferred"} & set(p), k
        assert set(p["names"]) == {str(v) for v in range(n)}, k
        assert set(p["names"].values()) <= {"vision model", "two readers", "one reader"}, k
        assert not re.search(r"on (?:that|one) line|factory", S.FRAME_PROOFS[k]["note"]), k
    for k in ("global:0x0052", "global:0x0c89", "global:0x047d"):
        assert [lab for _, lab in by_key[k]["values"]] == ["-2", "-1", "±0", "+1", "+2"], k
        named = [int(code) for code in re.findall(r"[-+±]?\d+ (?:was|is) (\d+)", S.FRAME_PROOFS[k]["note"])]
        assert named == [0, 4], (k, S.FRAME_PROOFS[k]["note"])           # the ends only, no value a round held
    for k in ("global:0x0c89", "global:0x047d"):
        assert "opens only with the finder in use" in S.FRAME_PROOFS[k]["note"], k
    assert S.FRAME_PROOFS["global:0x0052"]["allowance"].startswith("the owner allowed Monitor Brightness remotely")
    assert S.FRAME_PROOFS["global:0x0c89"]["allowance"].startswith("the owner allowed Viewfinder Bright. remotely")
    framepos = ["set:0x019a", "set:0x0f0b", "set:0x0f0d", "set:0x0f2c", "set:0x0f2e", "set:0x0f30", "set:0x019c",
                "set:0x019e", "set:0x01be", "set:0x01c0", "set:0x01c2", "set:0x01c4", "set:0x01c6", "set:0x01c8"]
    from writer import a1_tables as T
    boxes = {k: S.NEW_RECORDS[k] for k in S.NEW_RECORDS if k.startswith("set:0x13") and "box position" in S.NEW_RECORDS[k]["name"]}
    # the steps: every number the sentences hold is the table's, the box's steps under Large twice Standard's both ways
    # as its sentence says (one press each way, runs/kit2_framepos_amt_one), and no other figure for the box
    steps = {n for xy in T.FRAME_STEPS.values() for v in xy if v is not None for n in re.findall(r"\d+", str(v))}
    assert all(isinstance(v, int) for xy in T.FRAME_STEPS.values() for v in xy)
    assert T.FRAME_STEPS[("Large", "Custom 1")] == tuple(2 * v for v in T.FRAME_STEPS[("Standard", "Custom 1")])
    for phrase in T.STEP_FACTS.values():
        assert set(re.findall(r"\d+", phrase.replace("Custom 1", ""))) <= steps, phrase
    # each sentence where it belongs, word for word
    amt_note = S.FRAME_PROOFS["global:0x03a3"]["note"]
    row = next(ln for ln in (ROOT / "docs" / "models" / "ILCE-1M2_fw4.00.md").read_text(encoding="utf-8").splitlines()
               if ln.startswith("| Focus frame position |"))
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    entry = log[log.index("- The notes of the ILCE-1M2's focus point"):]
    entry = entry[:entry.index("\n- ")]
    assert T.STEP_FACTS["point"] in T.FRAMEPOS_POINT and T.STEP_FACTS["box"] in T.BOX_PLACE
    assert T.STEP_FACTS["all"] in amt_note and T.STEP_FACTS["all"] in row
    written = {k: by_key[k] for k in framepos + list(boxes) + ["global:0x03a3"] if k in by_key}
    for k, s in written.items():                          # as the writer wrote them
        want = "all" if k == "global:0x03a3" else "box" if k in boxes else "point" if k not in framepos[:6] else None
        assert want is None or T.STEP_FACTS[want] in s["note"], k
    # with the sentences, the grid's geometry, the days, the slot, the boxes' and copies' numbers, the model, record ids
    # and run names taken out, no digit is left; no word says where a frame stood, nor how far it could go
    forbidden = re.compile(r"\b(?:edge|limit|travel|near|side|stood|further)\b|\b(?:stop|short|border|boundar|clamp|corner)\w*"
                           r"|\b(?:less|more) than\b|on the way|from the centre", re.I)
    geometry = (r"640 x 480|3 x 3|\(320, 240 = centre\)|\(0 centre, [^)]*\)|20\d\d-\d\d-\d\d|slot 1|Custom [123]|"
                r"copy [1-4]|ILCE-1M2|0x[0-9a-f]{4}|kit2_\w+")

    def bare(text: str) -> str:
        for phrase in T.STEP_FACTS.values():
            text = text.replace(phrase, "")
        return re.sub(geometry, "", text)
    texts = [T.AF_NOTE, T.VERT, T.FRAMEPOS_POINT, T.BOX_PLACE, T.BOX_COPIES, amt_note, row, entry]
    texts += [S.FRAME_PROOFS[k]["note"] for k in framepos[6:] + list(boxes)]
    texts += [f"{s['note']} ({s.get('note_evidence', '')})" for k, s in written.items() if k not in framepos[:6]]
    for text in texts:
        assert not re.search(r"\d", bare(text)) and not forbidden.search(text), (bare(text), text)
    # the public sentences (T.*) say the facts; the runs that show them are the hand evidence's, put back into the
    # entries' notes (S.FRAME_PROOFS: the spot's point records, a Custom box's place)
    for text in (T.FRAMEPOS_POINT, T.BOX_PLACE):
        assert "AF Frame Move Amt Standard" in text and "kit2_" not in text, text
    for text in (S.FRAME_PROOFS["set:0x019c"]["note"], S.FRAME_PROOFS[next(iter(boxes))]["note"]):
        assert "AF Frame Move Amt Standard" in text and "kit2_framepos_amt" in text, text
    assert ("a step AF Frame Move Amt sets, the same for Spot S, M, L and XL and Expand Spot and smaller for Spot XS"
            in T.FRAMEPOS_POINT) and "led to each of the nine places" in S.FRAME_PROOFS["set:0x019a"]["note"]
    assert "differ" not in T.BOX_PLACE and "moving with the presses" in T.BOX_PLACE
    assert "moved Custom 1's box" in T.BOX_PLACE and "Spot XS's step is smaller than Spot M's across (and, under Large, up and down too)" in entry
    # AF Frame Move Amt's note is a note only, its evidence a sentence of its own: its proof stays the report's (pass
    # 2's, by the menu), merged with the definition's (by_lines_of takes it not)
    assert not {"values", "proved", "sampled", "run", "date"} & set(S.FRAME_PROOFS["global:0x03a3"])
    assert "global:0x03a3" not in S.by_lines_of(S.FRAME_PROOFS)
    # the public note, then its evidence after it (the hand evidence's "note+")
    assert amt_note.endswith(". (set by the menu and measured through Stills slot 1's registrations, runs "
                             "kit2_framepos_amt and kit2_framepos_amt_one, 2026-11-09)")
    if "global:0x03a3" in by_key:
        proof = by_key["global:0x03a3"]["proved"]
        assert proof["values"] == [0, 1] and "AF Frame Move Amt" in proof["menu"] and proof["run"] == "kit2_pass2"
    for k in framepos:
        assert S.FRAME_PROOFS[k]["allowance"] == "the owner allowed Camera Set. Memory remotely, 2026-11-09", k
        if k in by_key:
            assert "the owner allowed Camera Set. Memory remotely, 2026-11-09" in by_key[k]["note_evidence"], k
    assert S.FRAME_PROOFS["global:0x12e1"]["proved"] == [0, 1, 2]
    assert len(boxes) == 26 and all(info["like"] == "set:0x019c" for info in boxes.values())
    for k in boxes:
        fp = S.FRAME_PROOFS[k]
        assert fp["sampled"] == 2 and fp["run"] == "kit2_framepos" and "Custom box" in fp["menu"], k
        assert T.STEP_FACTS["box"] in fp["note"], k        # the steps a press moved, no place (checked above)
    for k in boxes:
        if k in by_key:                                   # once the definition holds them, as the writer wrote them
            assert by_key[k]["in_sets"] and by_key[k]["area"] == "set" and by_key[k]["proved"]["sampled"]["proofs"] == 2
            assert "Camera Set. Memory" in by_key[k]["note_evidence"]
    mirrored = [s for s in DOC["settings"] if s.get("in_sets_proved")]
    assert all(s["in_sets"] and set(s["in_sets_proved"]) == {"run", "date", "slot"} for s in mirrored)


def test_a_note_only_hand_table_entry_leaves_the_definitions_proof_to_be_merged():
    """by_lines_of: a FRAME_PROOFS entry that lists values but gives no proof (the Registered AF area records) is proved
    by the report's lines alone; one with a note only (AF Frame Move Amt's, 2026-11-09) or with its own proof is not,
    so the proof a definition holds for it is merged with the report's (kept_proof): a value a counted line still
    wrote that a later report fails to show is kept, an old menu row never is."""
    import schema_update as S
    from writer.proofs import kept_proof
    made_up = {"a": {"note": "x", "values": [[0, "A"]], "menu": "M"}, "b": {"note": "y", "allowance": "z"},
               "c": {"note": "x", "values": [[0, "A"]], "proved": [0]}, "d": {"note": "x", "sampled": 2}}
    assert S.by_lines_of(made_up) == {"a"}
    real = S.by_lines_of(S.FRAME_PROOFS)
    assert "global:0x03a3" not in real and {"global:0x0e7a", "global:0x0f8c"} <= real
    assert all("values" in S.FRAME_PROOFS[k] for k in real)
    old = {"run": "kit2_x", "date": "2026-01-02", "menu": ["Row", "Row [Movie mode]"], "values": [0, 1]}
    new = {"run": "kit2_x", "date": "2026-01-03", "menu": ["Row"], "values": [1]}
    kept, said = kept_proof(old, new, written=frozenset({0, 1}))
    assert kept["values"] == [0, 1] and kept["menu"] == ["Row"] and said


def test_replay_reads_a_registration_mirror_by_what_its_record_holds_after(tmp_path, capsys):
    """replay_proofs checks a registration mirror line by the one record it claims: what that record holds in the
    download after the registration is its stored after (or the code it names, when it stored no change), whatever
    else the registration rewrote and whichever earlier download the line names as base (framepos_run.py's sweep of
    2026-11-09 named its first download for every place); a record holding another value is a difference. Made-up
    files written through the camera's block (never uploaded)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("replay_proofs", ROOT / "kit" / "tools" / "replay_proofs.py")
    RP = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RP)
    from camkit import runs
    cs = camset.read(SAMPLE)
    copy, other = cs.get(1, 0x037d), cs.get(1, 0x0354)
    bump = lambda rec, n: bytes([(rec.raw[0] + n) % 3]) + rec.raw[1:]
    main, side = tmp_path / "kit2_pass2", tmp_path / "kit2_memtwins"
    for run in (main, side):
        (run / "dat").mkdir(parents=True)
    (main / "proofs.jsonl").write_text("", encoding="utf-8")
    (side / "dat" / "00001_start.DAT").write_bytes(SAMPLE.read_bytes())
    (side / "dat" / "00002_one.DAT").write_bytes(camset.with_values(cs, {(1, 0x037d): bump(copy, 1)}))
    (side / "dat" / "00003_two.DAT").write_bytes(camset.with_values(cs, {(1, 0x037d): bump(copy, 2),
                                                                         (1, 0x0354): bump(other, 1)}))
    runs.mark_proof_run(side, "made up")
    two = camset.read(side / "dat" / "00003_two.DAT").get(1, 0x037d).value()
    one = camset.read(side / "dat" / "00002_one.DAT").get(1, 0x037d).value()
    line = lambda after, base: {"path": ["Camera Set. Memory", "A"], "kind": "registration mirror", "record": "set:0x037d",
                                "key": "set1:0x037d", "index": after, "label": "A", "slot": "1", "base": base,
                                "dat": "00003_two.DAT", "changes": [{"key": "set1:0x037d", "before": one, "after": after}],
                                "applied": True}
    (side / "proofs.jsonl").write_text(json.dumps(line(two, "00001_start.DAT")) + "\n"
                                       + json.dumps(dict(line(two, "00002_one.DAT"), changes=[])) + "\n", encoding="utf-8")
    assert RP.main([str(main), "--quiet"]) == 0
    assert "2 proofs diffed again, 2 the same" in capsys.readouterr().out
    (side / "proofs.jsonl").write_text(json.dumps(line(one, "00002_one.DAT")) + "\n", encoding="utf-8")
    assert RP.main([str(main), "--quiet"]) == 1, "the record holds another value after the registration"
