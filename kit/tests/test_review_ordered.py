"""The engineering review of 2026-11-18, finding 6 (track 4's finding 2): two limits the camera keeps in order, ISO
Range Limit's two ends and ISO AUTO's Minimum and Maximum, which the definition could not say, so an editor let a
lower limit be set above its upper one. The hand table's LIMIT_PAIRS names each pair and the directions in which a
proof showed the camera move the other limit; both writer passes put it on the two settings as at_most and at_least,
where the two list the same values and are kept in the same sets, checked against the camera's downloads. The lower
ISO Range Limit is named by its end, as the upper is. Made-up settings, keys and values, the a1 II's committed public
files where a test reads the shipped ones, and files made from its sample with made-up values."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import ROOT, camset, datafiles, definitions, paths  # noqa: E402
from writer import hand_evidence, hand_tables  # noqa: E402
# imported before any test points the kit at a data folder of its own: it binds the a1 II's tables as it is imported
import schema_update  # noqa: E402,F401
from test_plain_hand_tables import Cam, rec  # noqa: E402

A1 = paths.A1II
PUB = definitions.load_public(A1)
PUB_BY = {s["key"]: s for s in PUB["settings"]}
SAMPLE = definitions.sample(PUB)
CAM = "ILCE-0X0_fw1.00"             # a made-up camera
LOWERS = ("global:0x0b65", "global:0x0b69", "global:0x0b6d")
UPPERS = ("global:0x0b63", "global:0x0b67", "global:0x0b6b")
# the a1 II's pairs as its hand table names them: ISO Range Limit, both directions proved; ISO AUTO's Minimum and
# Maximum, and each mode's copies of the two, a Minimum chosen above the Maximum proved to raise it, and a Maximum
# chosen below the Minimum proved to pull it down (the live and stills pairs in Stills mode, the movie pair in Movie mode)
A1_PAIRS = {
    "global:0x0b65": {"upper": "global:0x0b63", "lower_moves_upper": True, "upper_moves_lower": True},
    "global:0x0dfa": {"upper": "global:0x0e00", "lower_moves_upper": True, "upper_moves_lower": True},
    "global:0x0dfc": {"upper": "global:0x0e02", "lower_moves_upper": True, "upper_moves_lower": True},
    "global:0x0dfe": {"upper": "global:0x0e04", "lower_moves_upper": True, "upper_moves_lower": True},
}
# what both passes write on the a1 II's settings from them
A1_FIELDS = {
    "global:0x0b65": ("at_most", {"setting": "global:0x0b63", "moves_it": True}),
    "global:0x0b63": ("at_least", {"setting": "global:0x0b65", "moves_it": True}),
    "global:0x0dfa": ("at_most", {"setting": "global:0x0e00", "moves_it": True}),
    "global:0x0e00": ("at_least", {"setting": "global:0x0dfa", "moves_it": True}),
    "global:0x0dfc": ("at_most", {"setting": "global:0x0e02", "moves_it": True}),
    "global:0x0e02": ("at_least", {"setting": "global:0x0dfc", "moves_it": True}),
    "global:0x0dfe": ("at_most", {"setting": "global:0x0e04", "moves_it": True}),
    "global:0x0e04": ("at_least", {"setting": "global:0x0dfe", "moves_it": True}),
}
UNSHOWN = "global:0x0dfe"           # the pair whose marked direction the a1 pass's made-up hand evidence leaves out


# ---------------------------------------------------------------- the hand table

def test_the_a1_hand_tables_name_both_pairs_and_the_lower_end_by_its_name():
    """The a1 II's LIMIT_PAIRS: ISO Range Limit (both directions proved, 2026-11-18), ISO AUTO's Minimum and Maximum
    and each mode's copies of the two (a Minimum chosen above the Maximum raised it, in Movie mode the movie copies
    and in Stills mode the stills copies; a Maximum chosen below the Minimum pulled it down, 2026-11-19, in Stills mode
    for the live and stills pairs and in Movie mode for the movie pair, so all three have upper_moves_lower).
    The lower ISO Range Limit's three records are named "ISO Range Limit (lower)", together, so they stay one row
    beside "ISO Range Limit (upper)". Each pair lists the same values in the committed definition and is kept in the
    same sets; the file fits its JSON Schema."""
    T = hand_tables.load(A1, evidence=False)
    assert T.LIMIT_PAIRS == A1_PAIRS
    assert [T.RECORD_FIXES[k]["name"] for k in LOWERS] == ["ISO Range Limit (lower)"] * 3
    assert [T.RECORD_FIXES[k]["name"] for k in UPPERS] == ["ISO Range Limit (upper)"] * 3
    for lower, e in A1_PAIRS.items():
        lo, up = PUB_BY[lower], PUB_BY[e["upper"]]
        assert lo["values"] == up["values"] and len(lo["values"]) > 2, lower
        assert (lo["area"], lo.get("in_sets")) == (up["area"], up.get("in_sets")), lower
    doc = json.loads(datafiles.hand_tables_file(A1).read_text(encoding="utf-8"))
    assert hand_evidence.schema_problems(doc, "hand-tables") == []


def a_camera(monkeypatch, tmp_path, tables) -> Path:
    """A made-up camera's tables file holding `tables`, in a data folder of the test's own."""
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path / "evidence")
    (tmp_path / "evidence").mkdir()
    p = datafiles.hand_tables_file(CAM)
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"camera": CAM, "LIMIT_PAIRS": tables}), encoding="utf-8")
    return p


PAIR = {"upper": "global:0x0002", "lower_moves_upper": True}


def test_a_limit_pairs_table_reads_as_the_file_has_it(monkeypatch, tmp_path):
    """LIMIT_PAIRS read as the file has it, by the lower limit's key; a camera without the table has it empty."""
    a_camera(monkeypatch, tmp_path, {"global:0x0001": PAIR, "global:0x0003": {"upper": "global:0x0004"}})
    assert hand_tables.load(CAM).LIMIT_PAIRS == {"global:0x0001": PAIR, "global:0x0003": {"upper": "global:0x0004"}}
    assert hand_tables.empty()["LIMIT_PAIRS"] == {}


@pytest.mark.parametrize("table, words", [
    ([PAIR], "LIMIT_PAIRS is not in its shape: the table is an array, not an object"),
    ({"global:0x0001": "global:0x0002"}, "'global:0x0001' is a string, not an object"),
    ({"global:0x0001": {"lower_moves_upper": True}}, "'global:0x0001' has no 'upper'"),
    ({"global:0x0001": {"upper": 2}}, "'global:0x0001''s 'upper' is a whole number, not a string"),
    ({"global:0x0001": {"upper": "global:0x0001"}}, "'global:0x0001' names itself as its upper limit"),
    ({"global:0x0001": {**PAIR, "lower_moves_upper": False}}, "'lower_moves_upper' is only ever true"),
    ({"global:0x0001": {**PAIR, "upper_moves_lower": "yes"}}, "'upper_moves_lower' is a string, not true or false"),
    ({"global:0x0001": PAIR, "global:0x0003": PAIR}, "LIMIT_PAIRS holds 'global:0x0002' twice"),
])
def test_a_limit_pairs_table_out_of_its_shape_is_refused(monkeypatch, tmp_path, table, words):
    """A LIMIT_PAIRS table or entry out of its shape: refused as the file is read, in plain words, the file and the
    table named and what was expected said, before the writer trips on it."""
    p = a_camera(monkeypatch, tmp_path, table)
    with pytest.raises(hand_tables.Refused) as got:
        hand_tables.load(CAM)
    said = str(got.value)
    assert words in said and p.name in said and "mend the file by hand" in said, said


# ---------------------------------------------------------------- the writer

def pairs_doc() -> dict:
    """A made-up definition: two settings listing the same five steps (0x0001, 0x0002), two more of them (0x0003,
    0x0004), one listing other names for the codes (0x0005), one whose memory sets keep it (0x0006), one read as a
    whole record (0x0007) and one with an old at_most a table no longer gives (0x0008)."""
    steps = [[c, f"Step {i}"] for i, c in enumerate((7, 3, 9, 1, 5))]       # codes in no order, on purpose

    def s(rid, **more):
        return {"key": f"global:0x{rid:04x}", "area": "global", "id": rid, "name": f"Setting {rid}", "tab": "T",
                "group": "G", "scalar": True, "values": steps, **more}
    return {"settings": [s(1), s(2), s(3), s(4), s(5, values=[[c, f"Other {c}"] for c, _ in steps]), s(6, in_sets=True),
                         s(7, scalar=False), s(8, at_most={"setting": "global:0x0001"})]}


def test_the_writer_puts_both_ends_on_their_settings(capsys):
    """with_limit_pairs (kit/writer/limits.py): each LIMIT_PAIRS entry goes on its two settings, at_most on the lower
    naming the upper and at_least on the upper naming the lower, each with moves_it where the table says the camera
    moved the other on a choice past it, never else; every other setting loses an old one. An entry that cannot take
    effect is printed, "not applied", and left out: a setting the definition lacks, a limit naming itself, two settings
    that do not list the same values in the same order (the order is the value lists' places, never the codes'), one
    read as a whole record, two kept in different sets, a setting already a limit of another pair. The fields fit the
    definition's JSON Schema."""
    import jsonschema
    from writer.limits import with_limit_pairs
    doc = pairs_doc()
    by = {s["key"]: s for s in doc["settings"]}
    table = {"global:0x0001": {"upper": "global:0x0002", "lower_moves_upper": True},
             "global:0x0004": {"upper": "global:0x0003", "upper_moves_lower": True}}
    assert with_limit_pairs(doc, table) == 2
    said = capsys.readouterr().out
    assert by["global:0x0001"]["at_most"] == {"setting": "global:0x0002", "moves_it": True}
    assert by["global:0x0002"]["at_least"] == {"setting": "global:0x0001"}
    assert by["global:0x0004"]["at_most"] == {"setting": "global:0x0003"}
    assert by["global:0x0003"]["at_least"] == {"setting": "global:0x0004", "moves_it": True}
    assert [k for k, s in by.items() if {"at_most", "at_least"} & set(s)] == [f"global:0x000{i}" for i in (1, 2, 3, 4)]
    assert "limit pairs: 2 pairs of limits the camera keeps in order" in said
    for entry, why in (
            ({"global:0x0001": {"upper": "global:0x0099"}}, "the definition lacks global:0x0099"),
            ({"global:0x0099": {"upper": "global:0x0001"}}, "the definition lacks global:0x0099"),
            ({"global:0x0001": {"upper": "global:0x0005"}}, "the two do not list the same values in the same order"),
            ({"global:0x0001": {"upper": "global:0x0007"}}, "global:0x0007 is not a setting with named values"),
            ({"global:0x0001": {"upper": "global:0x0006"}}, "the two are not kept in the same sets"),
            ({"global:0x0001": {"upper": "global:0x0002"}, "global:0x0003": {"upper": "global:0x0001"}},
             "global:0x0001 is a limit of another pair already")):
        doc = pairs_doc()
        with_limit_pairs(doc, entry)
        lower, upper = list(entry)[-1], entry[list(entry)[-1]]["upper"]
        assert f"limit pair {lower} <= {upper}: {why}; not applied" in capsys.readouterr().out, entry
    schema = json.loads(Path(ROOT / "schemas" / "definition.schema.json").read_text(encoding="utf-8"))
    one = {"key": "global:0x0001", "area": "global", "id": 1, "name": "n", "tab": "t", "group": "g"}
    check = jsonschema.Draft202012Validator(schema["$defs"]["setting"])
    check.validate({**one, "at_most": {"setting": "global:0x0002", "moves_it": True}})
    check.validate({**one, "at_least": {"setting": "global:0x0002"}})
    assert list(check.iter_errors({**one, "at_most": {"setting": "global:0x0002", "moves_it": False}}))
    assert list(check.iter_errors({**one, "at_least": {"setting": "global:0x0002", "evidence": "made up"}}))
    # an emptied table takes the fields out
    doc = pairs_doc()
    with_limit_pairs(doc, table)
    assert with_limit_pairs(doc, {}) == 0 and not [s["key"] for s in doc["settings"] if {"at_most", "at_least"} & set(s)]


def test_limit_pairs_are_checked_against_the_cameras_downloads(tmp_path, capsys):
    """with_limit_pairs with the camera's downloads: a download holding the lower limit past the upper by their value
    lists' places, in a section both live in (the live settings, and each memory set for settings the memories keep),
    stops the write (exit 1, the pair, the file and the section named, never a value), as with_copies does; the two at
    one value, or the lower below, bear it out; a value neither lists is not judged; a download that cannot be read is
    skipped and counted; with no downloads that is said and the pair written. The a1 II's ISO Range Limit records as
    the definition keys them, files made from the sample with made-up values (none written down here)."""
    from writer.limits import with_limit_pairs
    cs = camset.read(SAMPLE)
    lower, upper = 0x0b65, 0x0b63
    codes = [v for v, _ in PUB_BY["global:0x0b65"]["values"]]
    memory = next(s for s in range(1, len(cs.sections)) if cs.get(s, lower) is not None and cs.get(s, upper) is not None)
    raw = lambda rid, v, s=0: v.to_bytes(cs.get(s, rid).size, "little", signed=True)

    def made(lo, up, in_memory=None):
        changes = {(0, lower): raw(lower, lo), (0, upper): raw(upper, up)}
        if in_memory:
            changes.update({(memory, lower): raw(lower, in_memory[0], memory), (memory, upper): raw(upper, in_memory[1], memory)})
        return camset.with_values(cs, changes)
    root = tmp_path / "runs"
    (root / "r" / "dat").mkdir(parents=True)
    files = {"00001_below.DAT": made(codes[2], codes[9]), "00002_level.DAT": made(codes[5], codes[5]),
             "00003_unnamed.DAT": made(max(codes) + 7, codes[1]), "00004_junk.DAT": b"not a settings file"}
    for name, data in files.items():
        (root / "r" / "dat" / name).write_bytes(data)
    log = root / "downloads.jsonl"
    log.write_text("".join(json.dumps({"path": f"r/dat/{n}"}) + "\n" for n in files), encoding="utf-8")
    table = {"global:0x0b65": {"upper": "global:0x0b63", "lower_moves_upper": True}}
    doc = json.loads(json.dumps(PUB))
    assert with_limit_pairs(doc, table, root) == 1
    said = capsys.readouterr().out
    assert re.search(r"limit pairs: the lower at or below the upper in each of \d+ sections, of 3 downloads read, 1 that could not be read skipped", said), said
    by = {s["key"]: s for s in doc["settings"]}
    assert by["global:0x0b65"]["at_most"] == {"setting": "global:0x0b63", "moves_it": True}
    for name, data in (("00005_memory_crossed.DAT", made(codes[1], codes[3], in_memory=(codes[8], codes[4]))),
                       ("00006_live_crossed.DAT", made(codes[6], codes[2]))):
        (root / "r" / "dat" / name).write_bytes(data)
        with log.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"path": f"r/dat/{name}"}) + "\n")
        with pytest.raises(SystemExit) as stop:
            with_limit_pairs(doc, table, root)
        said = str(stop.value).replace("\\", "/")
        section = memory if "memory" in name else 0
        assert said.startswith(f"limit pairs: r/dat/{name}, section {section}, holds global:0x0b65 above global:0x0b63"), said
        assert said.endswith("nothing written. Take the entry out of LIMIT_PAIRS, or prove the state that file shows, then write again."), said
        assert not re.search(r"(?<![\w:x])\d+(?![\w])", said.split(f"section {section}")[1].split("(")[0]), said
        log.write_text("".join(json.dumps({"path": f"r/dat/{n}"}) + "\n" for n in files), encoding="utf-8")
    assert with_limit_pairs(doc, table, tmp_path / "none") == 1
    assert "limit pairs: no downloads in" in capsys.readouterr().out


# ---------------------------------------------------------------- both passes

def test_the_plain_pass_writes_the_pairs_from_the_hand_table(tmp_path, monkeypatch, capsys):
    """The plain pass (every camera's but the a1 II's) reads LIMIT_PAIRS and writes at_most and at_least on the two
    settings it names, where its report gives both the same values; the public definition carries them, no evidence.
    A made-up camera, made-up proofs."""
    c = Cam(tmp_path, monkeypatch)
    steps = {"Step 1": 4, "Step 2": 6, "Step 3": 8}
    c.report([{"row": "Shooting > Low End", "options": 3, "notices": [], "records": {"global:0x0b65": rec(dict(steps))}},
              {"row": "Shooting > High End", "options": 3, "notices": [], "records": {"global:0x0b63": rec(dict(steps))}}])
    c.tables(LIMIT_PAIRS={"global:0x0b65": {"upper": "global:0x0b63", "upper_moves_lower": True}})
    _, said = c.write(capsys)
    public, _, text = c.written()
    by = {s["key"]: s for s in public["settings"]}
    assert by["global:0x0b65"]["at_most"] == {"setting": "global:0x0b63"}, said
    assert by["global:0x0b63"]["at_least"] == {"setting": "global:0x0b65", "moves_it": True}
    assert "limit pairs: 1 pairs of limits the camera keeps in order" in said
    # an emptied table takes them out again
    c.tables(LIMIT_PAIRS={})
    c.write(capsys)
    assert not [s["key"] for s in c.written()[0]["settings"] if {"at_most", "at_least"} & set(s)]


@pytest.fixture(scope="module")
def a1_written(tmp_path_factory):
    """The a1 II's full pass (main, --write --force) on a made-up run (test_definitions.a1_run: a copy of the committed
    definition, the sample as every download), with a copy of its data folder, so the settings reset file it writes
    follows the names in the copy and never in data/. The hand evidence is there (made up), put back into the pairs'
    entries for each direction the table marks but the last pair's (UNSHOWN). Returns (what it printed, the definition
    written by key, the reset file written)."""
    import contextlib
    import io
    import shutil

    from test_definitions import A1_PROOFS, A1_REPORT, a1_run
    import schema_update as S
    tmp = tmp_path_factory.mktemp("ordered_a1")
    with pytest.MonkeyPatch.context() as mp:
        shutil.copytree(ROOT / "data" / A1, tmp / "data" / A1)
        mp.setattr(definitions, "DATA", tmp / "data")
        _, target, _ = a1_run(tmp, mp, A1_REPORT, A1_PROOFS)
        mp.setattr(S, "HAND_EVIDENCE", tmp / "made-up hand evidence")
        # the clone's own hand evidence may already show every direction (the a1 II's does since 2026-11-19): the
        # unshown pair's is taken off, so the test does not depend on what the private overlay holds
        mp.setattr(S, "LIMIT_PAIRS", {k: {f: v for f, v in e.items() if f != "evidence"} if k == UNSHOWN else
                                      {**e, "evidence": {f: "made up" for f in ("lower_moves_upper", "upper_moves_lower")
                                                         if e.get(f)}}
                                      for k, e in S.LIMIT_PAIRS.items()})
        mp.setattr(sys, "argv", ["schema_update.py", "--write", "--force"])
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            S.main()
        written = json.loads(target.read_text(encoding="utf-8"))
        reset = json.loads(datafiles.reset_file(A1).read_text(encoding="utf-8"))
    return said.getvalue(), {s["key"]: s for s in written["settings"]}, reset


def test_the_a1_pass_writes_the_pairs_and_the_lower_name(a1_written):
    """The a1 II's own pass writes its LIMIT_PAIRS onto the definition (at_most and at_least, moves_it where the table
    says so and the hand evidence shows it: a marked direction it does not show is written without, said), and names
    the lower ISO Range Limit's three records by their end, as the settings reset file then does; nothing else carries
    either field."""
    said, by, reset = a1_written
    want = {**A1_FIELDS, UNSHOWN: ("at_most", {"setting": A1_PAIRS[UNSHOWN]["upper"]}),
            A1_PAIRS[UNSHOWN]["upper"]: ("at_least", {"setting": UNSHOWN})}
    assert {k: (f, by[k][f]) for k in A1_FIELDS for f in ("at_most", "at_least") if f in by[k]} == want
    for flag in ("lower_moves_upper", "upper_moves_lower"):
        assert (f"limit pair {UNSHOWN} <= {A1_PAIRS[UNSHOWN]['upper']}: nothing in the hand evidence shows {flag} "
                "(its \"evidence\" in LIMIT_PAIRS); written without moves_it") in said
    assert sorted(k for k, s in by.items() if {"at_most", "at_least"} & set(s)) == sorted(A1_FIELDS)
    assert [by[k]["name"] for k in LOWERS] == ["ISO Range Limit (lower)"] * 3
    assert [by[k]["name"] for k in UPPERS] == ["ISO Range Limit (upper)"] * 3
    assert [reset["records"][k]["name"] for k in LOWERS if k in reset["records"]] == ["ISO Range Limit (lower)"] * 3
    assert "limit pairs: 4 pairs of limits the camera keeps in order" in said
