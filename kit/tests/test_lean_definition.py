"""The public definition is lean (docs/decisions/0016): two owners mapping the same camera completely get the same file,
so nothing in it says how, when, in which run or from which state a thing was proved. That evidence goes to the private
evidence file (camkit.definitions: split, merge), and the kit reads the two back as one. Made-up values; no camera."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import definitions  # noqa: E402

def evidence_in(doc: dict, text: str) -> list:
    """Every place a public definition carries evidence (camkit.definitions.evidence_in_public)."""
    return definitions.evidence_in_public(doc, text)


def test_no_public_definition_carries_evidence():
    """Every definition in editor/definitions/ is lean: none of the evidence keys, no run, kit2_ run name or ISO date
    anywhere in it, and its format is the lean one."""
    found = list(definitions.DIR.glob("*.json"))
    assert found
    for p in found:
        text = p.read_text(encoding="utf-8")
        doc = json.loads(text)
        assert doc["definition_format"] == definitions.FORMAT == 2, p.name
        assert evidence_in(doc, text) == [], p.name


def full_definition() -> dict:
    """A small definition as the kit holds it whole, every kind of evidence on it (made-up values)."""
    return {
        "$schema": definitions.SCHEMA_REF, "definition_format": definitions.FORMAT, "model": "ILCE-0X0",
        "tabs": ["Shooting"],
        "layouts": [{"signature": "0123456789abcdef", "model": "ILCE-0X0", "firmware": "1.00", "note": "ILCE-0X0 firmware 1.00",
                     "note_evidence": "read via SDK, 2026-01-02", "doc": "docs/models/ILCE-0X0_fw1.00.md"}],
        "settings": [
            {"key": "global:0x0001", "area": "global", "id": 1, "name": "Dial", "source": "Menu", "tab": "Shooting",
             "group": "G", "order": 1, "values": [[0, "A"], [1, "B"], [2, "C"], [3, "D"], [4, "E"]],
             "note": "A dial.", "note_evidence": "runs/kit2_x, 2026-01-02", "in_sets": True,
             "in_sets_proved": {"run": "kit2_y", "date": "2026-01-03", "slot": 2}, "scalar": True,
             "proved": {"run": "kit2_x", "date": "2026-01-02", "menu": ["Dial [Shoot Mode M]"], "values": [0, 1],
                        "names": {"0": "two readers", "1": "one reader", "2": "derived", "3": "schema kept",
                                  "4": "counted"}},
             "menu_blocked": [{"value": 4, "label": "E", "reason": "not available as follows Mode", "menu": "Dial"}],
             "not_offered": [{"value": 3, "label": "D", "why": "Not on its list.", "menu": "Dial",
                              "evidence": "the list walked whole (runs/kit2_x)"}]},
            {"key": "global:0x0002", "area": "global", "id": 2, "name": "Level", "source": "SDK", "tab": "Shooting",
             "group": "G", "order": 2, "values": [], "range": [0, 31], "note": "", "in_sets": False, "scalar": True,
             "proved": {"run": "kit2_x", "date": "2026-01-02", "menu": ["Level"],
                        "sampled": {"proofs": 3, "linear": True}, "names": {"5": "sampled"}}},
            {"key": "global:0x0003", "area": "global", "id": 3, "name": "Key", "source": "Menu", "tab": "Shooting",
             "group": "G", "order": 3, "values": [[7, "X"], [8, "Y"]], "note": "", "in_sets": False, "scalar": True,
             "proved": {"run": "kit2_x", "date": "2026-01-02", "menu": ["Key / Fn"],
                        "sampled": {"proofs": 2, "linear": None, "from_start": True},
                        "names": {"7": "derived", "8": "derived"}}},
            {"key": "set:0x0004", "area": "set", "id": 4, "name": "Kept", "source": "Derived", "tab": "Shooting",
             "group": "G", "order": 4, "values": [], "note": "", "in_sets": True, "scalar": True,
             "unproved_reason": {"kind": "state", "date": "2026-01-04", "why": "The camera keeps it."},
             "unproved_sets": {"sets": [4, 5], "kind": "not_on_camera", "why": "Not written there.",
                               "date": "2026-01-04"}},
            {"key": "global:0x0005", "area": "global", "id": 5, "name": "Plain", "tab": "Shooting", "group": "G",
             "order": 5, "values": [[0, "Off"]], "note": "", "in_sets": False, "scalar": True,
             "proved": {"values": [0]}},
        ],
        "menu": [], "camera": {}}


def canon(doc) -> str:
    return json.dumps(doc, sort_keys=True)


def test_the_evidence_goes_private_and_comes_back(tmp_path):
    """definitions.write splits a whole definition: the public file lean (each proof the values it checked, a line's
    scale its "linear" alone), its evidence beside it in a file of its own; definitions.load puts them back together as
    they were, and writing what it gives changes neither file. load_public reads the lean file alone."""
    doc = full_definition()
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    ev = definitions.write(p, doc)
    assert ev == definitions.evidence_path(p) and ev.exists()
    text = p.read_text(encoding="utf-8")
    pub = json.loads(text)
    assert evidence_in(pub, text) == []
    by = {s["key"]: s for s in pub["settings"]}
    # chosen values and names from the camera's own word are checked; a name kept from an old schema or counted out is not
    assert by["global:0x0001"]["proved"] == {"values": [0, 1, 2]}
    assert by["global:0x0002"]["proved"] == {"sampled": {"linear": True}}
    assert by["global:0x0003"]["proved"] == {"values": [7, 8], "sampled": {"linear": None}}
    assert by["global:0x0005"]["proved"] == {"values": [0]}
    assert by["set:0x0004"]["unproved_reason"] == {"kind": "state", "why": "The camera keeps it."}
    assert by["global:0x0001"]["not_offered"] == [{"value": 3, "label": "D", "why": "Not on its list.", "menu": "Dial"}]
    private = json.loads(ev.read_text(encoding="utf-8"))
    assert set(private["settings"]) == {"global:0x0001", "global:0x0002", "global:0x0003", "set:0x0004"}
    assert private["settings"]["global:0x0001"]["menu_blocked"][0]["label"] == "E"
    assert private["layouts"] == {"0123456789abcdef": {"note_evidence": "read via SDK, 2026-01-02"}}
    whole = definitions.load(p)
    assert canon(whole) == canon(doc)
    assert definitions.load_public(p) == pub
    before = (text, ev.read_text(encoding="utf-8"))
    definitions.write(p, whole)
    assert (p.read_text(encoding="utf-8"), ev.read_text(encoding="utf-8")) == before
    # a lean file gives itself back, and with no evidence to keep no evidence file is made
    q = tmp_path / "lean" / "ILCE-0X0_fw1.00.json"
    assert definitions.write(q, pub) is None and not definitions.evidence_path(q).exists()
    assert q.read_text(encoding="utf-8") == text


def test_from_data_keeps_a_lean_definitions_places():
    """A definition read without its evidence (a fresh clone, CI) has no proof paths, so its places on the camera's
    menus stay as written (fromdata.places gives None); the Expert mark that rests on how the meaning was found keeps
    the mark the setting has."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from writer import fromdata
    doc = definitions.split(full_definition())[0]
    assert fromdata.places(doc) is None
    s = {"key": "global:0x0009", "area": "global", "id": 9, "name": "Thing (copy flag)", "expert": True}
    assert fromdata.expert(s) and not fromdata.expert({**s, "expert": False})
    assert fromdata.expert({**s, "source": "Derived", "expert": False})


def test_two_sessions_giving_one_index_to_two_options_keep_both():
    """pass2_report.rows_of: a list's index is its place as the session that walked it numbered it, so two sessions
    can give one index to two options (hold 2's Shoot Mode: Aperture Priority and, in another session, Manual Exposure
    at place 3). Both are kept (option_key); the same option seen again is that option's latest proof; a number field's index is its value, one option whatever its label shows of the other fields."""
    import pass2_report as R
    line = lambda i, lab, kind="list", dat="d1": {"path": ["Hold", "Shoot Mode"], "kind": kind, "index": i,
                                                   "label": lab, "dat": dat}
    proofs = [line(3, "Aperture Priority"), line(2, "Program Auto"), line(3, "Manual Exposure", dat="d2"),
              line(3, "Aperture Priority", dat="d3")]
    opts = R.rows_of(None, proofs)["Hold > Shoot Mode"]
    labels = sorted(o["label"] for o in opts.values())
    assert labels == ["Aperture Priority", "Manual Exposure", "Program Auto"]
    assert next(o for o in opts.values() if o["label"] == "Aperture Priority")["dat"] == "d3", "its latest proof"
    fields = [line([0, 50], "50 | 02", "fields"), line([0, 50], "50 | ", "fields", dat="d2")]
    assert [o["dat"] for o in R.rows_of(None, fields)["Hold > Shoot Mode [field 0]"].values()] == ["d2"]


def test_written_values_leave_out_a_sample_from_the_held_option():
    """writer.proofs.written_values: the lines of a table row sampled from the option the camera held
    (pass2_report.sampled_from_start) credit nothing an older definition could keep: such a record's proof is a
    count, never its values (decision 16)."""
    from writer.proofs import written_values
    cell = lambda i: {"path": ["Keys"], "kind": "table", "option": "Fn", "index": i, "label": f"F{i}", "dat": f"d{i}",
                      "base": "d0", "applied": True, "changes": [{"key": "global:0x0001", "before": 0, "after": 100 + i}]}
    sampled = [cell(0), cell(7), cell(13)]                  # three places of fourteen: a sample from the start
    assert written_values(sampled, set()) == {}
    whole = [cell(i) for i in range(4)]
    assert written_values(whole, set()) == {"global:0x0001": {100, 101, 102, 103}}


# ---------------------------------------------------------------- the data files (camkit.datafiles)

def test_no_public_data_file_carries_evidence():
    """Every file of every camera's data folder is lean (camkit.datafiles.evidence_in_public, which
    kit/tools/check_public.py refuses with): no menu tree, accepted file nor record shapes (private whole), no run's
    folder, kit2_ run name or ISO date, no walk's state word, and the reset file as its writer writes it."""
    from camkit import datafiles
    folders = datafiles.camera_folders()
    assert folders
    for d in folders:
        files = [p for p in sorted(d.iterdir()) if p.suffix in (".json", ".jsonl")]
        assert files, d.name
        for p in files:
            assert datafiles.evidence_in_public(p) == [], p.name


def test_the_menu_tree_is_written_and_read_whole(tmp_path):
    """datafiles.write_menu_tree writes the tree whole, the walk's states and reasons, its source and the owner's My
    Menu pages with it, and load_menu_tree reads it back as it is: the file is the mapper's own, private whole (decision
    16), for which rows the walk found greyed or unread and where each list began are the state the camera stood in.
    Without it load_menu_tree stops in plain words."""
    from camkit import datafiles
    doc = {"$schema": "../../schemas/menu-tree.schema.json", "model": "ILCE-0X0", "firmware": "1.00",
           "source": "the crawl kit2_crawl, 2026-01-02",
           "tabs": [{"tab": "My Menu", "pages": [{"page": "1/2", "group": "My Menu1", "rows": [
                        {"label": "Speed", "state": "seen", "why": "not walked", "kind": ""}]}]},
                    {"tab": "Shooting", "pages": [{"page": "2/2", "group": "G", "rows": [
                        {"label": "Speed", "state": "walked", "why": "", "kind": "list", "options": ["3", "1", "2"]},
                        {"label": "Long NR", "state": "greyed", "why": "blocked by Shutter", "kind": "notice"}]}]}]}
    p = tmp_path / "menu_tree_ILCE-0X0_fw1.00.json"
    assert datafiles.write_menu_tree(p, doc) == p
    assert json.loads(p.read_text(encoding="utf-8")) == doc == datafiles.load_menu_tree(p)
    assert not datafiles.evidence_path(p).exists()
    with pytest.raises(datafiles.NoMenuTree, match="private"):
        datafiles.load_menu_tree(tmp_path / "none.json")


def test_the_reset_files_lean_projection_keeps_only_what_a_test_could_tell():
    """datafiles.lean_reset (what kit/tools/move_evidence.py writes once in place of an older whole reset file): what
    each reset does to the settings a test could tell, its name and tab; a setting with a reading no test could tell
    (a test value that was the reset's own value, which would say the camera held another before) is left out, as one
    not tested is, and so are the tests' words (days, counts). reset_not_lean names each part of the older shape."""
    from camkit import datafiles
    doc = {"test": "Reset by hand, 2026-01-02: 3 settings", "records": {
        "global:0x0001": {"name": "A", "tab": "T", "result": "resets", "initialize": "resets"},
        "global:0x0002": {"name": "B", "tab": "T", "result": "keeps", "initialize": "resets"},
        "global:0x0003": {"name": "C", "tab": "T", "result": "keeps",
                          "initialize": "keeps (test value looks like the default)"},
        "global:0x0004": {"name": "D", "tab": "T", "result": "keeps"}},
        "initialize": "Initialize by hand, 2026-01-02"}
    pub = datafiles.lean_reset(doc)
    assert pub == {"about": datafiles.RESET_ABOUT, "records": {
        "global:0x0001": {"name": "A", "tab": "T", "result": "resets", "initialize": "resets"},
        "global:0x0002": {"name": "B", "tab": "T", "result": "keeps", "initialize": "resets"},
        "global:0x0004": {"name": "D", "tab": "T", "result": "keeps"}}}
    assert datafiles.reset_not_lean(pub) == [] and datafiles.lean_reset(pub) == pub
    why = datafiles.reset_not_lean(doc)
    assert any("'test'" in w for w in why) and any("'initialize'" in w for w in why) and any("0x0003" in w for w in why)
    assert datafiles.reset_not_lean({**pub, "about": "My own words."}) == []           # the mapper's own about
    assert datafiles.reset_not_lean({"about": "A.", "records": {"global:0x0001": {"name": "A"}}}) == [
        "global:0x0001: neither result nor initialize"]


def test_a_public_data_file_with_evidence_is_refused(tmp_path, monkeypatch):
    """evidence_in_public (what kit/tools/check_public.py refuses with), for any camera's folder: a menu tree, an
    accepted file or record shapes at all, however bare, a reset file with a reading no test could tell, a date in any
    file."""
    from camkit import datafiles
    d = tmp_path / "ILCE-0X0_fw1.00"
    d.mkdir()
    for name in ("menu_tree_ILCE-0X0_fw1.00.json", "accepted_ILCE-0X0_fw1.00.json", "record_shapes_ILCE-0X0_fw1.00.json"):
        (d / name).write_text("{}", encoding="utf-8")
        assert "private whole" in datafiles.evidence_in_public(d / name)[0]
    reset = d / "settings_reset_ILCE-0X0_fw1.00.json"
    reset.write_text(json.dumps({"about": datafiles.RESET_ABOUT, "records": {"global:0x0003": {
        "result": "keeps", "initialize": "keeps (test value looks like the default)"}}}), encoding="utf-8")
    assert any("looks like the default" in w for w in datafiles.evidence_in_public(reset))
    cam = d / "camera_ILCE-0X0_fw1.00.json"
    cam.write_text(json.dumps({"note": "read in runs/kit2_x"}), encoding="utf-8")
    assert sorted(datafiles.evidence_in_public(cam)) == ["names 'kit2_'", "names 'runs/'"]


# ---------------------------------------------------------------- the reviewer's holes (2026-11-11)

def reset_folder(tmp_path, monkeypatch, public: dict = None):
    """A camera's data folder of the test's own, laid out as the clone's (datafiles.CLONE_DATA pointed at it), its
    evidence folder of its own, and its public reset file, lean (or `public`), as the mapper wrote it."""
    from camkit import datafiles
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    monkeypatch.setattr(datafiles, "CLONE_DATA", tmp_path / "data")
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path / "evidence")
    pub = public or {"about": datafiles.RESET_ABOUT, "records": {
        "global:0x0001": {"name": "A", "tab": "T", "result": "resets"}}}
    p = datafiles.reset_file("ILCE-0X0_fw1.00")
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(pub, indent=1) + "\n", encoding="utf-8")
    return p, pub


def test_a_mappers_hand_edits_to_the_reset_file_survive_the_next_write(tmp_path, monkeypatch):
    """The second review's hole (2026-11-11): since the split, the mapper's edits to the public reset file (Phase 5's
    hand-written file) were written over from the private whole on the next --write. Now the public file is the one
    source: after a first write, the mapper adds initialize readings and a record to it by hand, and the next write
    keeps every one, refreshing only names and tabs from the definition; an archived older whole in the private folder
    is never read nor written."""
    from camkit import datafiles
    from writer import fromdata
    p, pub = reset_folder(tmp_path, monkeypatch)
    archive = datafiles.evidence_path(p)                    # an older whole kept by kit/tools/move_evidence.py
    archive.parent.mkdir(parents=True)
    archive.write_text(json.dumps({"test": "Reset by hand, 2026-01-02", "records": {
        "global:0x0001": {"name": "A", "tab": "T", "result": "resets"}}}), encoding="utf-8")
    kept = archive.read_bytes()
    target = tmp_path / "defs" / "ILCE-0X0_fw1.00.json"
    target.parent.mkdir()
    doc = full_definition()
    fromdata.write_definition(target, doc)                  # a first write
    edited = json.loads(p.read_text(encoding="utf-8"))
    edited["records"]["global:0x0001"]["initialize"] = "resets"                    # the mapper's hand edits
    edited["records"]["global:0x0003"] = {"name": "wrong name", "result": "keeps", "initialize": "resets"}
    p.write_text(json.dumps(edited, indent=1), encoding="utf-8")
    fromdata.write_definition(target, definitions.load(target))                     # the next write
    got = json.loads(p.read_text(encoding="utf-8"))
    names = {s["key"]: s for s in doc["settings"]}
    assert got["records"]["global:0x0001"] == {"name": names["global:0x0001"]["name"], "tab": "Shooting",
                                               "result": "resets", "initialize": "resets"}
    assert got["records"]["global:0x0003"] == {"name": names["global:0x0003"]["name"], "result": "keeps",
                                               "initialize": "resets", "tab": names["global:0x0003"]["tab"]}
    assert got["about"] == edited["about"] and archive.read_bytes() == kept
    assert sorted(x.name for x in archive.parent.iterdir()) == [archive.name], "no private half written"


def test_a_reset_file_not_lean_stops_the_write_naming_the_move(tmp_path, monkeypatch, capsys):
    """A public reset file in the older whole shape (the tests' words, a reading no test could tell) is never
    rewritten: a write stops before anything is written, naming kit/tools/move_evidence.py; without --write it is said;
    the file stays as it is."""
    from camkit import datafiles
    from writer import fromdata
    p, pub = reset_folder(tmp_path, monkeypatch, {"test": "Reset by hand, 2026-01-02", "records": {
        "global:0x0001": {"name": "A", "tab": "T", "result": "resets"},
        "global:0x0002": {"name": "B", "tab": "T", "result": "keeps (test value looks like the default)"}}})
    before = p.read_bytes()
    target = tmp_path / "defs" / "ILCE-0X0_fw1.00.json"
    target.parent.mkdir()
    with pytest.raises(datafiles.Refused) as e:
        fromdata.write_definition(target, full_definition())
    words = str(e.value.code)
    assert "kit/tools/move_evidence.py --camera ILCE-0X0_fw1.00" in words and "lean" in words
    assert not target.exists() and p.read_bytes() == before
    assert fromdata.reset_names(full_definition(), False) == 0
    assert "move_evidence.py" in capsys.readouterr().out and p.read_bytes() == before
    with pytest.raises(datafiles.Refused, match="move_evidence.py"):
        fromdata.reset_names(full_definition(), True)
    assert p.read_bytes() == before


def old_files(tmp_path, monkeypatch, cam="ILCE-0X0_fw1.00"):
    """A clone of the test's own (definitions.DATA, datafiles.CLONE_DATA and definitions.EVIDENCE_DIR in tmp_path)
    whose camera still has its three private-whole files at their old public place, data/<cam>/."""
    from camkit import datafiles
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    monkeypatch.setattr(datafiles, "CLONE_DATA", tmp_path / "data")
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path / "evidence")
    old = tmp_path / "data" / cam
    old.mkdir(parents=True)
    docs = {"menu_tree": {"tabs": [{"tab": "T", "pages": []}]}, "accepted": {"accepted": [{"kind": "new", "key": "k"}]},
            "record_shapes": {"types": {}}}
    for kind, doc in docs.items():
        (old / f"{kind}_{cam}.json").write_text(json.dumps(doc), encoding="utf-8")
    return cam, old, tmp_path / "evidence" / cam, docs


def test_reading_a_path_never_moves_a_file(tmp_path, monkeypatch, capsys):
    """2026-11-11 review: a path getter moved a mapper's data/<cam>/ menu tree, accepted file and record shapes into
    whatever the evidence folder was (a test's temporary folder, or the maintainer's own private folder for a
    contributor's branch). Now the getters only name the private place; readers that only show take a file left in
    data/ as absent, saying the command that moves it; a command that writes or drives stops in plain words naming it
    (datafiles.stop_if_left)."""
    from camkit import datafiles
    from writer import gate
    cam, old, private, docs = old_files(tmp_path, monkeypatch)
    listing = sorted(x.name for x in old.iterdir())
    assert definitions.menu_tree_file(cam) == datafiles.menu_tree_file(cam) == private / f"menu_tree_{cam}.json"
    assert datafiles.accepted_file(cam) == gate.accepted_file(cam) == private / f"accepted_{cam}.json"
    assert datafiles.record_shapes_file(cam) == private / f"record_shapes_{cam}.json"
    assert gate.read_accepted(cam) == []                                  # as if absent
    with pytest.raises(datafiles.NoMenuTree) as e:
        datafiles.load_menu_tree(cam)
    assert datafiles.move_command(cam) in str(e.value)
    monkeypatch.setattr(datafiles, "_SAID_NO_TREE", set())
    datafiles.say_no_menu_tree(definitions.menu_tree_file(cam), "it goes on without")
    assert datafiles.move_command(cam) in capsys.readouterr().err
    assert sorted(x.name for x in old.iterdir()) == listing and not private.exists(), "nothing moved"
    with pytest.raises(datafiles.Refused) as stop:
        datafiles.stop_if_left(cam, "kit/schema_update.py --write")
    words = str(stop.value.code)
    assert "kit/schema_update.py --write" in words and f"kit/tools/move_evidence.py --camera {cam}" in words
    assert f"data/{cam}/menu_tree_{cam}.json" in words or f"menu_tree_{cam}.json" in words
    assert "Traceback" not in words
    # check_public's refusal of such a file prints the exact command
    assert datafiles.evidence_in_public(old / f"accepted_{cam}.json") == [
        f"accepted_{cam}.json is private whole, kept in private/evidence/{cam}/: move it there with "
        f".venv/bin/python kit/tools/move_evidence.py --camera {cam}"]


def test_move_evidence_moves_the_three_files_once_and_refuses_in_plain_words(tmp_path, monkeypatch, capsys):
    """kit/tools/move_evidence.py: the three files of one camera from data/<cam>/ to private/evidence/<cam>/, one line
    each, copied, read back and compared before the data/ copy goes; a copy in both places that is the same: the data/
    one removed, said; different: refused naming both, nothing moved; a file that is not valid JSON: refused in plain
    words, nothing moved; CAMSET_EVIDENCE_DIR set: the move still goes into the clone's own private/evidence/, said,
    with what to do so the kit finds the files there."""
    from tools import move_evidence as M
    cam, old, private, docs = old_files(tmp_path, monkeypatch)
    data, evidence = tmp_path / "data", tmp_path / "evidence"
    bad = old / f"record_shapes_{cam}.json"
    good = bad.read_bytes()
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(M.Refused) as e:
        M.move(cam, data, evidence)
    assert "not valid JSON" in str(e.value.code) and bad.name in str(e.value.code)
    assert len(list(old.iterdir())) == 3 and not private.exists(), "nothing moved"
    bad.write_bytes(good)
    said = []
    M.move(cam, data, evidence, said.append)
    assert len(said) == 3 and all(x.startswith("moved ") for x in said)
    assert not list(old.iterdir())
    for kind, doc in docs.items():
        assert json.loads((private / f"{kind}_{cam}.json").read_text(encoding="utf-8")) == doc
    said.clear()
    M.move(cam, data, evidence, said.append)                                     # again: nothing to do
    assert len(said) == 3 and all("already private" in x for x in said)
    (old / f"accepted_{cam}.json").write_text(json.dumps(docs["accepted"]), encoding="utf-8")       # the same
    said.clear()
    M.move(cam, data, evidence, said.append)
    assert not (old / f"accepted_{cam}.json").exists() and any(x.startswith("removed ") for x in said)
    (old / f"menu_tree_{cam}.json").write_text(json.dumps({"tabs": []}), encoding="utf-8")         # another
    with pytest.raises(M.Refused) as e:
        M.move(cam, data, evidence)
    words = str(e.value.code)
    assert f"data/{cam}/menu_tree_{cam}.json" in words and f"evidence/{cam}/menu_tree_{cam}.json" in words
    assert (old / f"menu_tree_{cam}.json").exists()
    assert json.loads((private / f"menu_tree_{cam}.json").read_text(encoding="utf-8")) == docs["menu_tree"]
    (old / f"menu_tree_{cam}.json").unlink()
    # CAMSET_EVIDENCE_DIR set: the move still goes into the clone's own private/evidence/, said with what to do next
    monkeypatch.setattr(M, "CLONE_EVIDENCE", evidence)
    monkeypatch.setenv("CAMSET_EVIDENCE_DIR", str(tmp_path / "elsewhere"))
    (old / f"accepted_{cam}.json").write_text(json.dumps(docs["accepted"]), encoding="utf-8")
    capsys.readouterr()
    M.main(["--camera", cam])
    out = capsys.readouterr().out
    assert "CAMSET_EVIDENCE_DIR is set" in out and "point it at" in out and "copy the moved files" in out
    assert not (old / f"accepted_{cam}.json").exists() and not (tmp_path / "elsewhere").exists()


def test_a_reader_without_the_menu_tree_says_what_that_means(tmp_path, monkeypatch, capsys):
    """Where the camera's menu tree is not on this computer, the readers that go on without it say so in one line
    each, once, with what it means for what they give: the definition's menu list and places (fromdata), a pass-2
    report's check of a reading against the menu's rows (pass2_report.menu_names), the proof viewer's menu."""
    from camkit import datafiles
    from writer import fromdata
    import pass2_report
    from tools import proof_viewer
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path)
    monkeypatch.setattr(datafiles, "_SAID_NO_TREE", set())
    doc = definitions.split(full_definition())[0]
    assert fromdata.menu_list(doc) is None
    whole = full_definition()
    assert fromdata.places(whole) is None and fromdata.places(whole) is None
    said = capsys.readouterr().err
    assert said.count("no menu tree at") == 1 and "menu list and each setting's place" in said
    assert pass2_report.menu_names(tmp_path / "none.json") == set()
    assert "no menu tree at" in capsys.readouterr().err
    assert proof_viewer.menu(doc, [], tmp_path) == []
    assert "not on the camera's own menu rows" in capsys.readouterr().err


def test_evidence_that_no_longer_fits_is_kept_aside_never_put_back(tmp_path, capsys):
    """The reviewer's hole: merge put a setting's whole proof back over its public one even where a contributor had
    changed or taken out the public proof since, and the next write published the old proof again. Now each piece of
    evidence is put back only onto what it is evidence of: a whole proof onto the public proof that is its lean form, a
    date onto a public unproved_reason, a not-offered mark's evidence onto the public mark of its value, and a
    setting's evidence onto a setting there. What no longer fits is said once (key and field), left out of the
    definition the kit reads, and kept in the evidence file's "stale" section on the next write: nothing published,
    nothing lost."""
    doc = full_definition()
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    ev = definitions.write(p, doc)
    old = json.loads(ev.read_text(encoding="utf-8"))
    pub = json.loads(p.read_text(encoding="utf-8"))
    by = {s["key"]: s for s in pub["settings"]}
    by["global:0x0001"]["proved"] = {"values": [0]}                 # a contributor took two values out
    by["global:0x0001"].pop("not_offered")                          # and the not-offered mark
    by["set:0x0004"].pop("unproved_reason")                         # a reason since taken out
    pub["settings"] = [s for s in pub["settings"] if s["key"] != "global:0x0003"]     # a setting since gone
    p.write_text(json.dumps(pub, indent=1), encoding="utf-8")
    capsys.readouterr()
    whole = definitions.load(p)
    said = capsys.readouterr().err
    for k, f in (("global:0x0001", "proved"), ("global:0x0001", "not_offered"), ("set:0x0004", "unproved_reason"),
                 ("global:0x0003", "proved")):
        assert f"{k}: its {f}" in said, (k, f)
    assert "2026-" not in said and "kit2_" not in said, "said by key and field only"
    w = {s["key"]: s for s in whole["settings"]}
    assert w["global:0x0001"]["proved"] == {"values": [0]} and "not_offered" not in w["global:0x0001"]
    assert w["global:0x0001"]["note_evidence"] == "runs/kit2_x, 2026-01-02"           # what fits is put back
    assert w["set:0x0004"]["unproved_sets"]["date"] == "2026-01-04"
    definitions.write(p, whole)
    again = json.loads(p.read_text(encoding="utf-8"))
    assert {s["key"]: s for s in again["settings"]}["global:0x0001"]["proved"] == {"values": [0]}, "not published again"
    assert definitions.evidence_in_public(again, p.read_text(encoding="utf-8")) == []
    kept = json.loads(ev.read_text(encoding="utf-8"))
    assert kept["stale"]["settings"]["global:0x0001"]["proved"] == old["settings"]["global:0x0001"]["proved"]
    assert kept["stale"]["settings"]["global:0x0001"]["not_offered"] == old["settings"]["global:0x0001"]["not_offered"]
    assert kept["stale"]["settings"]["set:0x0004"]["unproved_reason"] == old["settings"]["set:0x0004"]["unproved_reason"]
    assert kept["stale"]["settings"]["global:0x0003"] == old["settings"]["global:0x0003"]
    assert "proved" not in kept["settings"]["global:0x0001"]
    # read and written again: the same files, the stale section kept as it is
    before = (p.read_bytes(), ev.read_bytes())
    definitions.write(p, definitions.load(p))
    assert (p.read_bytes(), ev.read_bytes()) == before
    # a setting gone whole keeps every field of its evidence aside as it was, its not-offered marks one list
    gone = definitions.merge({**pub, "settings": [s for s in pub["settings"] if s["key"] != "global:0x0001"]}, old)
    assert gone[definitions.STALE]["settings"]["global:0x0001"] == old["settings"]["global:0x0001"]


def test_the_evidence_is_written_first_and_never_emptied_by_a_public_read(tmp_path, monkeypatch):
    """definitions.write writes the evidence file before the public file, so a public write that fails leaves this
    write's evidence in place; and a definition read without its evidence (load_public) is refused rather than written
    over the evidence file, which it would empty."""
    doc = full_definition()
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    ev = definitions.evidence_path(p)
    dump = definitions._dump

    def failing(where, d):
        if Path(where) == p:
            raise OSError("disk full")
        dump(where, d)
    monkeypatch.setattr(definitions, "_dump", failing)
    with pytest.raises(OSError):
        definitions.write(p, doc)
    assert ev.exists() and not p.exists()
    monkeypatch.setattr(definitions, "_dump", dump)
    with pytest.raises(definitions.CutShort, match="--finish-write"):     # its marker left: finished first
        definitions.write(p, doc)
    assert "never written" in definitions.finish_write(p)[1] and not definitions.writing_marker(p).exists()
    definitions.write(p, doc)
    before = ev.read_bytes()
    with pytest.raises(definitions.WouldLoseEvidence, match="load_public"):
        definitions.write(p, definitions.load_public(p))
    assert ev.read_bytes() == before


def test_a_relative_evidence_folder_is_the_repo_roots(tmp_path):
    """CAMSET_EVIDENCE_DIR, relative, names a folder of the repo root, wherever the command is run from."""
    import os
    import subprocess
    from camkit import ROOT
    got = subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); "
                          "from camkit import definitions; print(definitions.EVIDENCE_DIR)", str(ROOT / "kit")],
                         cwd=tmp_path, env={**os.environ, "CAMSET_EVIDENCE_DIR": "elsewhere/evidence"},
                         capture_output=True, text=True, check=True).stdout.strip()
    assert Path(got) == ROOT / "elsewhere" / "evidence"


def test_a_definition_lacking_part_of_its_evidence_is_refused(tmp_path):
    """WouldLoseEvidence also for a definition read without part of its evidence (definitions.lost_evidence): a lean
    proof whose whole form the evidence file holds, an unproved_reason without the date the file holds, a not-offered
    mark without its evidence; nothing written. A proof changed since is no loss (it is set aside as stale instead)."""
    doc = full_definition()
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    ev = definitions.write(p, doc)
    before = (p.read_bytes(), ev.read_bytes())
    for k, change in (("global:0x0001", lambda s: s.update(proved=definitions.lean_proof(s["proved"]))),
                      ("set:0x0004", lambda s: s["unproved_reason"].pop("date")),
                      ("global:0x0001", lambda s: [m.pop("evidence") for m in s["not_offered"]])):
        part = definitions.load(p)
        change(next(s for s in part["settings"] if s["key"] == k))
        with pytest.raises(definitions.WouldLoseEvidence, match=k):
            definitions.write(p, part)
        assert (p.read_bytes(), ev.read_bytes()) == before
    other = definitions.load(p)
    next(s for s in other["settings"] if s["key"] == "global:0x0001")["proved"] = {"values": [0]}
    definitions.write(p, other)                                  # another proof: not a loss


def test_evidence_gone_stale_in_this_run_stops_the_write_and_is_shown_and_dropped(tmp_path, capsys):
    """A key renamed or a public proof changed since (a merge) orphans the mapping's evidence: when this run's reading
    set aside a proof's evidence, or more than a handful of settings', that the evidence file did not hold aside
    before, the write stops before anything is written (definitions.stale_refusal; --accept-stale writes it, kept in
    the "stale" section). After a write one line says the file has a stale section; --drop-stale shows it by key and
    field and removes it, the rest of the file as it was."""
    from writer import fromdata
    doc = full_definition()
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    ev = definitions.write(p, doc)
    pub = json.loads(p.read_text(encoding="utf-8"))
    for s in pub["settings"]:
        if s["key"] == "global:0x0001":
            s["key"] = "global:0x0101"                              # renamed by a merge
    p.write_text(json.dumps(pub, indent=1), encoding="utf-8")
    capsys.readouterr()
    whole = definitions.load(p)
    assert ("settings", "global:0x0001", "proved") in definitions.newly_stale(whole, p)
    before = (p.read_bytes(), ev.read_bytes())
    with pytest.raises(definitions.StaleStop) as stop:
        fromdata.write_definition(p, whole, reset=False)
    words = str(stop.value.code)
    assert "global:0x0001: proved" in words and "--accept-stale" in words and "2026-" not in words
    assert (p.read_bytes(), ev.read_bytes()) == before
    fromdata.write_definition(p, whole, accept_stale=True, reset=False)
    fromdata.say_stale(p)
    line = capsys.readouterr().out
    assert line.count("\n") == 1 and "\"stale\" section" in line and "--drop-stale" in line
    kept = json.loads(ev.read_text(encoding="utf-8"))
    assert "global:0x0001" in kept["stale"]["settings"]
    again = definitions.load(p)                                     # held aside already: no stop now
    assert definitions.newly_stale(again, p) == []
    fromdata.write_definition(p, again, reset=False)
    assert definitions.drop_stale(p, write=False) == definitions.stale_items(kept["stale"])
    assert "stale" in json.loads(ev.read_text(encoding="utf-8"))
    got = definitions.drop_stale(p)
    assert ("settings", "global:0x0001", "proved") in got
    left = json.loads(ev.read_text(encoding="utf-8"))
    assert "stale" not in left and {k: v for k, v in kept.items() if k != "stale"} == left
    assert definitions.stale_summary(p) is None
    # a handful of settings other than proofs goes on, said; more stops
    few = [("settings", f"k{i}", "note_evidence") for i in range(definitions.STALE_STOP_SETTINGS)]
    assert definitions.stale_refusal(few, p) is None
    assert definitions.stale_refusal(few + [("settings", "k99", "source")], p)


def test_no_refusal_comes_after_a_file_was_written(tmp_path, monkeypatch):
    """fromdata.write_definition: the stale stop and the evidence guard come first, then the reset file's refusal, then
    the reset file, then the definition, so a refusal never leaves the definition written and the reset file not
    (2026-11-11 review: the definition was written before reset_names)."""
    from camkit import datafiles
    from writer import fromdata
    p, pub = reset_folder(tmp_path, monkeypatch)
    target = tmp_path / "defs" / "ILCE-0X0_fw1.00.json"
    target.parent.mkdir()
    doc = full_definition()
    monkeypatch.setattr(fromdata, "reset_refusal", lambda d: "no")
    with pytest.raises(datafiles.Refused):
        fromdata.write_definition(target, doc)
    assert not target.exists() and not definitions.evidence_path(target).exists()


# ---------------------------------------------------------------- review 4 (2026-11-11): the stale holes

def test_a_change_to_the_lean_form_leaves_every_fitting_proof_in_place(tmp_path, monkeypatch, capsys):
    """merge compares lean_proof of the public proof with lean_proof of the evidence's, so a later change to what the
    lean form keeps does not set every proof aside as stale (it compared the evidence's lean form with the public
    proof as written)."""
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    definitions.write(p, full_definition())
    plain = definitions.lean_proof
    monkeypatch.setattr(definitions, "lean_proof", lambda proved: {**plain(proved), "kind": "menu"})
    whole = definitions.load(p)
    assert definitions.STALE not in whole and definitions.newly_stale(whole, p) == []
    assert {s["key"]: s for s in whole["settings"]}["global:0x0001"]["proved"]["run"] == "kit2_x", "put back whole"
    assert "no longer fits" not in capsys.readouterr().err


def test_a_newer_stale_proof_keeps_the_older_and_still_stops(tmp_path, capsys):
    """A setting whose proof is held aside in the "stale" section already: when a newer proof of it goes stale, the
    older one stays as it was, the newer one is kept beside it ("proved#2", definitions.stale_entry), and the write
    stops all the same (it counted as stale already, so nothing stopped and the older piece was written over)."""
    from writer import fromdata
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    ev = definitions.write(p, full_definition())
    first = json.loads(ev.read_text(encoding="utf-8"))["settings"]["global:0x0001"]["proved"]

    def public_proof(values):
        pub = json.loads(p.read_text(encoding="utf-8"))
        next(s for s in pub["settings"] if s["key"] == "global:0x0001")["proved"] = {"values": values}
        p.write_text(json.dumps(pub, indent=1), encoding="utf-8")
    public_proof([0])                                               # a contributor's change: the first proof aside
    fromdata.write_definition(p, definitions.load(p), accept_stale=True, reset=False)
    whole = definitions.load(p)
    newer = {"run": "kit2_z", "date": "2026-02-02", "menu": ["Dial"], "values": [0]}
    next(s for s in whole["settings"] if s["key"] == "global:0x0001")["proved"] = newer      # proved again
    fromdata.write_definition(p, whole, reset=False)
    public_proof([1])                                               # changed again: the newer proof goes stale too
    capsys.readouterr()
    again = definitions.load(p)
    assert ("settings", "global:0x0001", "proved#2") in definitions.newly_stale(again, p)
    with pytest.raises(definitions.StaleStop, match="global:0x0001: proved#2"):
        fromdata.write_definition(p, again, reset=False)
    fromdata.write_definition(p, again, accept_stale=True, reset=False)
    kept = json.loads(ev.read_text(encoding="utf-8"))["stale"]["settings"]["global:0x0001"]
    assert kept["proved"] == first and kept["proved#2"] == newer
    assert definitions.newly_stale(definitions.load(p), p) == []    # read again: nothing new, nothing doubled


def _proofs_changed() -> dict:
    """full_definition with two newer proofs (made-up values): what a later write would write."""
    done = full_definition()
    by = {s["key"]: s for s in done["settings"]}
    by["global:0x0001"]["proved"] = {"run": "kit2_z", "date": "2026-02-02", "menu": ["Dial"], "values": [3]}
    by["global:0x0003"]["proved"] = {"run": "kit2_z", "date": "2026-02-02", "menu": ["Key"], "values": [7, 8]}
    return done


def test_a_write_cut_short_is_its_marker_and_is_finished(tmp_path, monkeypatch, capsys):
    """Fix round 5 (2026-11-11): a write leaves a marker beside the evidence file (<evidence>.writing, the sha256 of
    the public file it is about to write) before the evidence and removes it once the public file is in place, so a
    write cut short is exactly one whose marker is left. A write cut short after its evidence file leaves it; the next
    write stops naming --finish-write, before anything is written, with --accept-stale too; finish_write writes the
    public file the marker names (the evidence's proofs' lean forms put in), nothing else, and removes the marker; with
    no marker it says there is nothing to finish."""
    from writer import fromdata
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    ev = definitions.write(p, full_definition())
    marker = definitions.writing_marker(p)
    assert marker == ev.with_name(ev.name + ".writing") and not marker.exists(), "a write that ends leaves none"
    done = _proofs_changed()
    real = definitions._dump

    def cut(path, doc):
        if Path(path) == p:
            raise OSError("cut short")
        real(path, doc)
    monkeypatch.setattr(definitions, "_dump", cut)
    with pytest.raises(OSError, match="cut short"):
        definitions.write(p, done)
    monkeypatch.setattr(definitions, "_dump", real)
    assert marker.exists() and json.loads(marker.read_text(encoding="utf-8"))["sha256"]
    before_pub, before_ev = p.read_bytes(), ev.read_bytes()
    with pytest.raises(definitions.CutShort, match="--finish-write"):
        definitions.write(p, done)
    capsys.readouterr()
    whole = definitions.load(p)
    words = definitions.stale_refusal(definitions.newly_stale(whole, p), p)
    assert "cut short" in words and "--finish-write" in words and "git restore" not in words
    with pytest.raises(definitions.CutShort, match="--finish-write"):
        fromdata.write_definition(p, whole, accept_stale=True, reset=False)
    assert p.read_bytes() == before_pub and ev.read_bytes() == before_ev
    keys, said = definitions.finish_write(p)
    assert keys == ["global:0x0001", "global:0x0003"] and "wrote" in said
    assert ev.read_bytes() == before_ev and p.read_text(encoding="utf-8") == definitions.text(done)
    assert not marker.exists() and definitions.newly_stale(definitions.load(p), p) == []
    with pytest.raises(definitions.Unfinished, match="nothing to finish"):
        definitions.finish_write(p)
    definitions.write(p, done)                                       # the next write goes on
    assert not marker.exists()


def test_a_newer_evidence_file_is_no_write_cut_short(tmp_path):
    """Fix round 5 (2026-11-11): "the evidence file is newer than the public file" misfired after a pull, a restored
    private/ or a hand edit, and --finish-write then reverted the upstream or hand correction of a proof. With no
    marker, a public proof changed under a newer evidence file is a stale proof (git restore or --accept-stale, as
    ever), and --finish-write says there is nothing to finish and writes nothing."""
    import os
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    ev = definitions.write(p, _proofs_changed())
    pub = json.loads(p.read_text(encoding="utf-8"))
    next(s for s in pub["settings"] if s["key"] == "global:0x0001")["proved"] = {"values": [0]}   # upstream's fix
    p.write_text(json.dumps(pub, indent=1), encoding="utf-8")
    os.utime(p, (1_000_000_000, 1_000_000_000))                     # the evidence file the newer, as after a pull
    fixed = p.read_bytes()
    changed = definitions.newly_stale(definitions.load(p), p)
    words = definitions.stale_refusal(changed, p)
    assert "cut short" not in words and "git restore" in words
    with pytest.raises(definitions.Unfinished, match="nothing to finish"):
        definitions.finish_write(p)
    assert p.read_bytes() == fixed and not definitions.writing_marker(p).exists()
    assert not ev.with_name(ev.name + ".writing").exists()


def test_finish_write_checks_the_marker_and_says_each_case(tmp_path):
    """finish_write writes only the public file whose sha256 the marker holds: a projection that is another file is
    refused in plain words, nothing written and the marker kept, saying how to go on; a marker left after the public
    file was written, or before the evidence changed anything, is only removed; an unreadable marker is refused."""
    p = tmp_path / "ILCE-0X0_fw1.00.json"
    ev = definitions.write(p, full_definition())
    marker = definitions.writing_marker(p)
    marker.write_text(json.dumps({"public": p.name, "sha256": "0" * 64}), encoding="utf-8")
    definitions._dump(ev, definitions.split(_proofs_changed())[1])
    before = p.read_bytes()
    with pytest.raises(definitions.Unfinished, match="changed more than proofs") as e:
        definitions.finish_write(p)
    assert "rm '" in str(e.value) and p.read_bytes() == before and marker.exists()
    marker.write_text("{not json", encoding="utf-8")
    with pytest.raises(definitions.Unfinished, match="cannot be read"):
        definitions.finish_write(p)
    import hashlib
    marker.write_text(json.dumps({"sha256": hashlib.sha256(p.read_bytes()).hexdigest()}), encoding="utf-8")
    keys, said = definitions.finish_write(p)                         # cut short after the public file
    assert keys == [] and "already" in said and not marker.exists() and p.read_bytes() == before
    q = tmp_path / "other" / "ILCE-0X0_fw1.00.json"
    q.parent.mkdir()
    definitions.write(q, full_definition())
    definitions.writing_marker(q).write_text(json.dumps({"sha256": "1" * 64}), encoding="utf-8")
    keys, said = definitions.finish_write(q)                         # cut short before the evidence changed anything
    assert keys == [] and "agree" in said and not definitions.writing_marker(q).exists()


def test_drop_stale_alone_only_lists_and_removes_with_write(tmp_path, monkeypatch, capsys):
    """kit/schema_update.py --drop-stale lists the "stale" section (keys and fields) and removes nothing; with --write
    it removes it. --finish-write runs finish_write."""
    import schema_update as S
    defs = tmp_path / "definitions"
    defs.mkdir()
    monkeypatch.setattr(definitions, "DIR", defs)
    monkeypatch.setattr(S, "RUN_ROOT", tmp_path / "runs" / "ILCE-0X0_fw1.00")
    p = defs / "ILCE-0X0_fw1.00.json"
    ev = definitions.write(p, full_definition())
    have = json.loads(ev.read_text(encoding="utf-8"))
    have["stale"] = {"settings": {"global:0x0009": {"proved": {"values": [1], "run": "kit2_q"}}}}
    ev.write_text(json.dumps(have, indent=1), encoding="utf-8")
    before = ev.read_bytes()
    monkeypatch.setattr(sys, "argv", ["schema_update.py", "--drop-stale"])
    S.main()
    out = capsys.readouterr().out
    assert "global:0x0009: proved" in out and "--drop-stale --write" in out and ev.read_bytes() == before
    monkeypatch.setattr(sys, "argv", ["schema_update.py", "--drop-stale", "--write"])
    S.main()
    assert "stale" not in json.loads(ev.read_text(encoding="utf-8"))
    monkeypatch.setattr(sys, "argv", ["schema_update.py", "--finish-write"])
    with pytest.raises(definitions.Unfinished, match="nothing to finish"):
        S.main()


# ---------------------------------------------------------------- review 4 (2026-11-11): move_evidence and the reset file

def test_move_evidence_makes_an_old_whole_reset_file_lean_keeping_the_whole(tmp_path, monkeypatch):
    """The fourth step of kit/tools/move_evidence.py: a public reset file in the older whole shape is copied whole into
    private/evidence/<cam>/ (an archive the kit never reads; an archive of other contents there already is kept and the
    copy takes a dated name beside it), then its lean projection written in its place, one line said; a lean file is
    left as it is; nothing for a camera with no reset file."""
    from camkit import datafiles
    from tools import move_evidence as M
    whole = {"test": "Reset by hand, 2026-01-02", "records": {
        "global:0x0001": {"name": "A", "tab": "T", "result": "resets"},
        "global:0x0002": {"name": "B", "tab": "T", "result": "keeps (test value looks like the default)"}}}
    p, _ = reset_folder(tmp_path, monkeypatch, whole)
    data, evidence = tmp_path / "data", tmp_path / "evidence"
    original = p.read_bytes()
    said = []
    archive = M.lean_reset_file("ILCE-0X0_fw1.00", data, evidence, said.append)
    assert archive == evidence / "ILCE-0X0_fw1.00" / p.name and archive.read_bytes() == original
    assert json.loads(p.read_text(encoding="utf-8")) == datafiles.lean_reset(whole)
    assert datafiles.reset_not_lean(json.loads(p.read_text(encoding="utf-8"))) == []
    assert len(said) == 1 and "made" in said[0] and "1 whose reading no test could tell left out" in said[0]
    lean = p.read_bytes()
    assert M.lean_reset_file("ILCE-0X0_fw1.00", data, evidence, said.append) is None and p.read_bytes() == lean
    other = dict(whole, test="Another test, 2026-02-02")             # a second old whole, the archive kept
    p.write_text(json.dumps(other), encoding="utf-8")
    again = M.lean_reset_file("ILCE-0X0_fw1.00", data, evidence, said.append)
    assert again != archive and again.name.startswith(p.stem + ".archived-") and archive.read_bytes() == original
    assert json.loads(again.read_text(encoding="utf-8")) == other
    p.unlink()
    assert M.lean_reset_file("ILCE-0X0_fw1.00", data, evidence, said.append) is None


@pytest.mark.parametrize("records, odd", [
    ([{"key": "global:0x0001", "result": "resets"}], '"records" is a list'),
    ({"global:0x0001": ["resets"]}, "record 'global:0x0001' is a list"),
    (None, '"records" is missing'),
], ids=["records-a-list", "a-record-a-list", "no-records"])
def test_move_evidence_refuses_a_reset_file_of_a_shape_it_does_not_know(tmp_path, monkeypatch, records, odd):
    """Fix round 5 (2026-11-11): an old reset file whose records are a list (or any shape lean_reset_file does not
    know) ended in an AttributeError; now it is refused in plain words, nothing copied or changed."""
    from tools import move_evidence as M
    whole = {"test": "Reset by hand", **({"records": records} if records is not None else {})}
    p, _ = reset_folder(tmp_path, monkeypatch, whole)
    data, evidence = tmp_path / "data", tmp_path / "evidence"
    original = p.read_bytes()
    with pytest.raises(M.Refused) as e:
        M.lean_reset_file("ILCE-0X0_fw1.00", data, evidence, print)
    words = str(e.value.code)
    assert "shape this does not know" in words and odd in words and "Traceback" not in words
    assert p.read_bytes() == original and not (evidence / "ILCE-0X0_fw1.00").exists()


def test_move_evidence_counts_entries_that_are_no_setting_key_apart(tmp_path, monkeypatch):
    """Fix round 5 (2026-11-11): entries left out because their key is not a definition's setting key are counted and
    said apart from the settings whose reading no test could tell."""
    from tools import move_evidence as M
    whole = {"test": "Reset by hand", "records": {
        "global:0x0001": {"name": "A", "tab": "T", "result": "resets"},
        "global:0x0002": {"name": "B", "tab": "T", "result": "keeps (test value looks like the default)"},
        "Dial": {"name": "Dial", "tab": "T", "result": "resets"},
        "note": {"result": "keeps"}}}
    reset_folder(tmp_path, monkeypatch, whole)
    said = []
    M.lean_reset_file("ILCE-0X0_fw1.00", tmp_path / "data", tmp_path / "evidence", said.append)
    assert "1 settings kept" in said[0] and "1 whose reading no test could tell left out" in said[0]
    assert "2 whose key is not a setting key of a definition" in said[0]


def test_move_evidence_rough_edges(tmp_path, monkeypatch, capsys):
    """Review 4 (2026-11-11): a destination that cannot be written ends in plain words and leaves no .part file; a
    --camera with no data/<cam>/ folder says so and exits non-zero; --help lists --camera; a pair the same as JSON
    beside a file that cannot be read is never called two different copies."""
    import os
    import stat
    from tools import move_evidence as M
    cam, old, private, docs = old_files(tmp_path, monkeypatch)
    data, evidence = tmp_path / "data", tmp_path / "evidence"
    evidence.mkdir()
    evidence.chmod(stat.S_IRUSR | stat.S_IXUSR)                     # read-only
    try:
        if os.access(evidence, os.W_OK):
            pytest.skip("this user can write a read-only folder (root)")
        with pytest.raises(M.Refused) as e:
            M.move(cam, data, evidence)
        assert "cannot be written" in str(e.value.code) and "Traceback" not in str(e.value.code)
    finally:
        evidence.chmod(stat.S_IRWXU)
    assert not list(evidence.rglob("*.part")) and len(list(old.iterdir())) == 3
    monkeypatch.setattr(M, "CLONE_EVIDENCE", evidence)
    with pytest.raises(M.Refused, match="no data/ILCE-0X9_fw1.00/ folder|no .*ILCE-0X9_fw1.00/ folder") as e:
        M.main(["--camera", "ILCE-0X9_fw1.00"])
    assert e.value.code and not isinstance(e.value.code, int)
    with pytest.raises(SystemExit):
        M.main(["--help"])
    assert "--camera" in capsys.readouterr().out
    private.mkdir(parents=True)
    (private / f"accepted_{cam}.json").write_text(json.dumps(docs["accepted"], indent=4), encoding="utf-8")  # same JSON
    (old / f"record_shapes_{cam}.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(M.Refused) as e:
        M.plan(cam, data, evidence)
    assert "not valid JSON" in str(e.value.code) and "two different copies" not in str(e.value.code)


def test_from_data_checks_every_definition_before_writing_any(tmp_path, monkeypatch):
    """fromdata.refresh_from_data --write: a refusal for one definition (here the second's reset file, not lean)
    comes before any definition is written, so the first is not left written and the second not."""
    from camkit import datafiles
    from writer import fromdata
    defs = tmp_path / "defs"
    defs.mkdir()
    monkeypatch.setattr(definitions, "DIR", defs)
    monkeypatch.setattr(definitions, "SHIPPED", defs)               # its evidence in the evidence folder, as a clone's
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    monkeypatch.setattr(datafiles, "CLONE_DATA", tmp_path / "data")
    monkeypatch.setattr(definitions, "EVIDENCE_DIR", tmp_path / "evidence")
    for model in ("ILCE-0A0", "ILCE-0B0"):
        doc = json.loads(json.dumps(full_definition()).replace("ILCE-0X0", model))
        definitions.write(defs / f"{model}_fw1.00.json", doc)
        (tmp_path / "data" / f"{model}_fw1.00").mkdir(parents=True)
    bad = datafiles.reset_file("ILCE-0B0_fw1.00")
    bad.write_text(json.dumps({"test": "Reset, 2026-01-02", "records": {}}), encoding="utf-8")
    monkeypatch.setattr(fromdata, "from_data", lambda d: {**d, "tabs": ["Shooting", "New"]})   # both would change
    before = {p: p.read_bytes() for p in defs.iterdir()}
    with pytest.raises(datafiles.Refused, match="move_evidence.py"):
        fromdata.refresh_from_data(True)
    assert {p: p.read_bytes() for p in defs.iterdir()} == before


def test_the_reset_files_schema_and_the_kits_lean_check_agree():
    """schemas/settings-reset.schema.json (the hook's and CI's check) and datafiles.reset_not_lean (the kit's and
    check_public's) take and refuse the same files."""
    import jsonschema
    from camkit import ROOT, datafiles
    schema = json.loads((ROOT / "schemas" / "settings-reset.schema.json").read_text(encoding="utf-8"))
    rec = {"name": "A", "tab": "T", "result": "resets"}
    cases = [{"about": "A.", "records": {"global:0x0001": rec}},
             {"$schema": "x", "about": "A.", "records": {"set:0x0001[2]": {"initialize": "keeps"}}},
             {"about": "A.", "records": {}},
             {"records": {"global:0x0001": rec}},
             {"about": "A.", "test": "t", "records": {}},
             {"about": "A.", "records": {"global:0x0001": {**rec, "date": "d"}}},
             {"about": "A.", "records": {"global:0x0001": {"name": "A"}}},
             {"about": "A.", "records": {"global:0x0001": {"result": "keeps (looks like the default)"}}},
             {"about": "A.", "records": {"Dial": rec}},
             {"about": 3, "records": {}}]
    for doc in cases:
        ok = jsonschema.Draft202012Validator(schema).is_valid(doc)
        assert ok == (datafiles.reset_not_lean(doc) == []), doc
