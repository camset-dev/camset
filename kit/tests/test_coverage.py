"""The coverage ledger (kit/camkit/coverage.py, kit/tools/coverage.py; docs/decisions/0023), off the camera: a made-up
camera (a definition, hand tables, a camera file, a Help Guide list, looks, a crawl row, proofs and leads in folders of
the test's own) gives every status at least once and each entry exactly one; a status that claims a test cites a look,
a crawl row or a proof line in the private form; the statuses generated from the definition agree with it; the public
form is built from the public sources and the allow-list alone, so no state seen reaches it, and is printed, never
kept: a tree with no runs/ and no private/ prints the a1 II's (kit/tools/coverage.py --print), public_problems refuses
one that holds a private key, a date, a hash or a word outside its closed vocabulary, and kit/tools/check_public.py any
copy of it in data/ (docs/decisions/0023); settled() never settles a row with values still to try, nor one
of another mode, nor anything when the ledger is missing or stale; the runs only print what it says unless given
--skip-settled (drive.py never skips), and a ledger error or a look that cannot be written never breaks a run."""
import contextlib
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from camkit import ROOT, coverage, definitions, paths  # noqa: E402
from conftest import TEST_CAMERA  # noqa: E402

CAM = TEST_CAMERA
A1 = paths.A1II


def setting(key, name, row=None, values=(), **kw):
    area, rid = key.split(":")
    out = {"key": key, "area": area, "id": int(rid[:6], 16), "name": name, "tab": kw.pop("tab", "Shooting"),
           "group": kw.pop("group", "G1"), "order": 1, "values": [list(v) for v in values], "note": "",
           "in_sets": kw.pop("in_sets", False), "scalar": True, "size": kw.pop("size", 1), "count": 1, "modes": ""}
    if row:
        out["row"] = list(row)
    out.update(kw)
    return out


ONOFF = ((0, "Off"), (1, "On"))
MENU = [("Shooting", "G1", "Alpha"), ("Shooting", "G1", "Bravo"), ("Shooting", "G1", "Charlie"),
        ("Shooting", "G1", "Delta"), ("Shooting", "G1", "Echo"), ("Shooting", "G1", "Foxtrot"),
        ("Shooting", "G1", "Golf"), ("Shooting", "G1", "Hotel"), ("Shooting", "G1", "India"),
        ("Shooting", "G1", "Juliet"), ("Shooting", "G1", "Kilo"), ("Shooting", "G3", "Alpha"),
        ("Network", "G4", "Display Wi-Fi Info."), ("Setup", "G2", "Setting Reset"), ("Setup", "G2", "IP Address Setting"),
        ("Setup", "G2", "Display Serial Number"), ("Setup", "G2", "Version"), ("Setup", "G2", "November")]
# one picker's list: November's slots store one table of codes (a shared list), slot 1 proved whole, slot 2 on two,
# its other three named from slot 1's proof by the writer ("derived", docs/decisions/0025): its public proof lists all
# five and is marked shared, its evidence (BASE_EVIDENCE) says which two were chosen on it
PICK = ((10, "Ant"), (11, "Bee"), (12, "Cat"), (13, "Dog"), (14, "Elk"))
SETTINGS = [
    setting("global:0x0100", "Alpha", ["Alpha"], ((0, "Off"), (1, "On"), (2, "Auto")), in_sets=True,
            proved={"values": [0, 1]}, not_offered=[{"value": 2, "label": "Auto", "why": "never offered"}]),
    setting("global:0x0106", "Alpha sub", ["Alpha", "Sub"], ONOFF, proved={"values": [0, 1]}),
    setting("global:0x0101", "Bravo", ["Bravo"], ONOFF),
    setting("global:0x0102", "Charlie", ["Charlie"], ((0, "0"), (10, "10"), (20, "20")),
            proved={"values": [0, 10], "sampled": {"linear": None}}),
    setting("global:0x0103", "Foxtrot", ["Foxtrot"], ONOFF),
    setting("global:0x0104", "Golf", ["Golf"], ONOFF,
            unproved_reason={"kind": "equipment", "why": "Greyed without a RAW recorder attached."}),
    setting("global:0x0105", "Hotel", ["Hotel"], ONOFF, unproved_reason={"kind": "state", "why": "The camera's own."}),
    setting("global:0x0107", "Mike", ["Mike"], ONOFF, row_mode="Movie", proved={"values": [0, 1]}),
    setting("global:0x0108", "My Menu 1: item 1", None, ONOFF, tab="Setup", group="My Menu", proved={"values": [0, 1]}),
    setting("global:0x0300@0", "Block field", None, (), size=320, proved={"sampled": {"linear": True}}),
    setting("global:0x0120", "November slot 1", ["November"], PICK, tab="Setup", group="G2",
            proved={"values": [10, 11, 12, 13, 14]}),
    setting("global:0x0121", "November slot 2", ["November"], PICK, tab="Setup", group="G2",
            proved={"values": [10, 11, 12, 13, 14], "shared": True}),
]
# the definition's private evidence: November slot 2's whole proof, as the writer leaves it
BASE_EVIDENCE = {"global:0x0121": {"proved": {"run": "kit2_pass2", "values": [10, 11], "names": {
    "10": "two readers", "11": "two readers", "12": "derived", "13": "derived", "14": "derived"}}}}
RECORDS = {f"global:0x{i:04x}": (1, 1) for i in (0x0100, 0x0101, 0x0102, 0x0103, 0x0104, 0x0105, 0x0106, 0x0107,
                                                  0x0108, 0x0120, 0x0121, 0x0200, 0x0201, 0x0202)}
RECORDS.update({"global:0x0300": (320, 1), "set:0x0100": (1, 1)})
HELP = [{"tab": "My Menu", "group": "My Menu Setting", "item": "Add Item", "modes": "still image, movie"},
        {"tab": "Shooting", "group": "G1", "item": "Alpha: Sub", "modes": "still image"}]
SHA = "ab" * 32


def look(path, **kw):
    out = {"t": "2026-11-14T10:00:00", "run": "kit2_drive_x", "kit": "abc1234", "by": "drive", "path": path,
           "did": "open", "result": "no_change", "records_changed": []}
    out.update(kw)
    return out


LOOKS = [look(["Delta"], did="choose", option="On", tab="Shooting"),
         look(["Echo"], screen="notice", fields=["IP Address", "MAC Address"]),
         look(["Foxtrot"], did="choose", option="On"),
         look(["India"], screen="notice", result="greyed", blocker={"row": "Alpha"}, start_sha256=SHA),
         look(["Kilo"], screen="list", result="looked", by="crawl", options=["Off", "On"]),
         look([], did="lap", by="crawl", result="no_change")]


@pytest.fixture
def camera(tmp_path, monkeypatch):
    """The made-up camera's files in the test's own folders; definitions.DIR and DATA pointed there."""
    ddir = tmp_path / "definitions"
    ddir.mkdir()
    doc = {"$schema": definitions.SCHEMA_REF, "definition_format": 2, "model": "TEST-CAM", "tabs": ["Shooting",
           "Exposure/Color", "Focus", "Playback", "Network", "Setup"],
           "layouts": [{"signature": "0" * 16, "model": "TEST-CAM", "firmware": "9.99"}], "settings": SETTINGS,
           "menu": [{"tab": t, "group": g, "label": lab, "order": i} for i, (t, g, lab) in enumerate(MENU)],
           "camera": {"model": "TEST-CAM", "section_counts": [1, 1], "tab_colors": {}}}
    (ddir / f"{CAM}.json").write_text(json.dumps(doc), encoding="utf-8")
    (ddir / f"{CAM}.evidence.json").write_text(json.dumps({"settings": BASE_EVIDENCE}), encoding="utf-8")
    data = tmp_path / "data" / CAM
    data.mkdir(parents=True)
    (data / f"camera_{CAM}.json").write_text(json.dumps({
        "model": "TEST-CAM", "section_counts": [1, 1], "tab_colors": {}, "volatile_records": [0x01ff],
        "my_menu": {"records": [0x0108]},
        "save_load_excluded": {"source": "the maker's list", "rows": [{"row": "Delta", "note": "its own file"},
                                                                      {"item": "a thing"}],
                               "header_rows": []}}), encoding="utf-8")
    (data / f"hand_tables_{CAM}.json").write_text(json.dumps({
        "camera": CAM, "FRAME_PROOFS": {"global:0x0101": {"values": [[0, "Off"], [1, "On"]], "note": "by hand"}},
        "MY_MENU_ROW": "My Menu Setting > Add Item"}), encoding="utf-8")
    (data / f"help_guide_menu_{CAM}.jsonl").write_text("".join(json.dumps(h) + "\n" for h in HELP), encoding="utf-8")
    monkeypatch.setattr(definitions, "DIR", ddir)
    monkeypatch.setattr(definitions, "DATA", tmp_path / "data")
    runs = paths.runs_top() / CAM
    crawl = runs / "kit2_crawl"
    crawl.mkdir(parents=True)
    (crawl / "rows.jsonl").write_text(json.dumps({"page": "3/9", "slot": 1, "label": "Juliet",
                                                  "outcome": "unknown screen", "kind": "unknown"}) + "\n",
                                      encoding="utf-8")
    lf = coverage.looks_file(CAM)
    lf.parent.mkdir(parents=True, exist_ok=True)
    lf.write_text("".join(json.dumps(x) + "\n" for x in LOOKS), encoding="utf-8")
    (lf.parent / f"leads_{CAM}.json").write_text(json.dumps({"live": [
        {"key": "global:0x0200", "cls": "SPECIFIC", "changes": 2}, {"key": "global:0x0201", "cls": "NEVER"}]}),
        encoding="utf-8")
    return SimpleNamespace(doc=doc, data=data, runs=runs, looks=lf, defn=ddir / f"{CAM}.json")


def ledger(public=False, validity=False):
    return coverage.build(CAM, src=coverage.load_sources(CAM, public=public, records=RECORDS), validity=validity)


def row(led, *path, tab=None, group=None, mode=None):
    es = led.find(list(path), mode, tab, group)
    assert es, path
    return es[0]


def add_looks(camera, *lks):
    with open(camera.looks, "a", encoding="utf-8") as f:
        for x in lks:
            f.write(json.dumps(x) + "\n")


def write_proofs(camera, run, proofs, attempts=()):
    d = camera.runs / run
    d.mkdir(exist_ok=True)
    (d / "proofs.jsonl").write_text("".join(json.dumps(x) + "\n" for x in proofs), encoding="utf-8")
    if attempts:
        (d / "attempts.jsonl").write_text("".join(json.dumps({"attempt": a, "complete": True}) + "\n"
                                                  for a in attempts), encoding="utf-8")
    return d


def public_text():
    return coverage.text(coverage.public_doc(ledger()))


# ---------------------------------------------------------------- every entry, one status; the private form's cites

def test_every_row_option_and_record_has_exactly_one_status(camera):
    led = ledger()
    assert led.rows and all(e["status"] in coverage.STATUS_NAMES for e in led.rows)
    keys = [(e["mode"], e["tab"], e["group"], tuple(e["path"]), e["nth"]) for e in led.rows]
    assert len(keys) == len(set(keys))
    for o in led.options:
        s = next(s for s in SETTINGS if s["key"] == o["key"])
        assert sorted(o["values"]) == sorted(v for v, _ in s["values"])
        assert all(st in coverage.STATUS_NAMES for st in o["values"].values())
    assert sorted(r["key"] for r in led.records) == sorted(RECORDS)
    assert all(r["status"] in coverage.RECORD_NAMES for r in led.records)
    doc = coverage.public_doc(led)
    for o in doc["options"]:
        vals = [v for vs in o["statuses"].values() for v in vs]
        assert len(vals) == len(set(vals))
    assert len({r["key"] for r in doc["records"]}) == len(doc["records"]) == len(RECORDS)


def test_the_made_up_camera_gives_each_status(camera):
    """Every row and option status at least once in the full (private) build, every record status once, each where the
    fixture puts it; but "proved or named from a shared list", which a proof read lean gives (the public build), and
    the private build reads every proof whole where its evidence is there."""
    led = ledger()
    want = {("Alpha",): "proved", ("Alpha", "Sub"): "proved", ("Bravo",): "proved by hand", ("Charlie",): "sampled",
            ("Delta",): "not in the settings file (Sony)", ("Echo",): "information screen",
            ("Foxtrot",): "tested, no record changes", ("Golf",): "needs equipment", ("Hotel",): "no proof possible",
            ("India",): "greyed in state", ("Juliet",): "kit cannot read", ("Kilo",): "not yet tried",
            ("Setting Reset",): "action, nothing to map", ("IP Address Setting",): "closed by rule",
            ("Display Wi-Fi Info.",): "information screen", ("Mike",): "proved", ("Add Item",): "proved"}
    for path, status in want.items():
        assert row(led, *path)["status"] == status, path
    seen = {e["status"] for e in led.rows} | {st for o in led.options for st in o["values"].values()}
    assert seen == set(coverage.STATUS_NAMES) - {coverage.PROVED_OR_SHARED}
    assert coverage.PROVED_OR_SHARED in {st for o in ledger(public=True).options for st in o["values"].values()}
    assert {r["status"] for r in led.records} == set(coverage.RECORD_NAMES)
    alpha2 = row(led, "Alpha", group="G3")
    assert alpha2["nth"] == 1 and alpha2["same_label_as"] == "G1" and alpha2["status"] == "proved"
    assert row(led, "Mike")["mode"] == "Movie" and row(led, "Add Item")["source"] == "help guide"
    assert row(led, "Add Item")["placement_missing"] == ["global:0x0108"]
    assert row(led, "Delta").get("confirmed") is True and row(led, "Delta")["sony_note"] == "its own file"
    assert row(led, "Echo")["fields"] == ["IP Address", "MAC Address"]
    assert row(led, "Display Wi-Fi Info.")["inferred"] == "class"
    assert row(led, "Golf")["equipment"] == "a RAW recorder"
    assert row(led, "India")["blocker"] == {"row": "Alpha"}
    lang = row(led, "IP Address Setting")
    assert lang["rule"] == "identity/by hand" and lang["opener"]
    alpha = {o["key"]: o for o in led.options}["global:0x0100"]["values"]
    assert alpha == {0: "proved", 1: "proved", 2: "not offered"}
    inferred = "inferred from a shared list"
    assert {o["key"]: o for o in led.options}["global:0x0121"]["values"] == {10: "proved", 11: "proved", 12: inferred,
                                                                            13: inferred, 14: inferred}
    nov = row(led, "November")
    assert nov["status"] == "proved" and nov["values_inferred"] == 3 and not nov.get("values_left")
    assert {o["key"]: o for o in led.options}["global:0x0102"]["values"] == {0: "sampled", 10: "sampled",
                                                                            20: "not yet tried"}
    assert {o["key"]: o for o in led.options}["global:0x0103"]["values"] == {0: "not yet tried",
                                                                            1: "tested, no record changes"}
    recs = {r["key"]: r for r in led.records}
    assert recs["global:0x0300"]["status"] == "partly named" and recs["global:0x0300"]["named_bytes"] == 2
    assert recs["set:0x0100"]["status"] == "proved"
    assert recs["global:0x0200"]["status"] == "changed, no row attributed"
    assert recs["global:0x0201"]["status"] == "unmapped, never seen to change"
    assert recs["global:0x0202"]["status"] == "unmapped, not examined"


def test_a_status_that_claims_a_test_cites_its_line(camera):
    """In the private form, every status resting on a look, a crawl row or a proof names it; one resting on a rule
    says so (inferred); the public form names none of them."""
    led = ledger()
    claims = {"information screen", "tested, no record changes", "greyed in state", "kit cannot read"}
    for e in led.rows:
        if e["status"] in claims and not e.get("inferred"):
            assert e.get("cites"), e["path"]
            assert all(any(k in c for k in ("look", "crawl", "proof", "failure", "scan")) for c in e["cites"])
        if e.get("confirmed"):
            assert e.get("cites")
    priv = coverage.private_doc(led)
    foxtrot = next(r for r in priv["rows"] if r["path"] == ["Foxtrot"])
    assert foxtrot["cites"][0]["look"] == 3 and foxtrot["cites"][0]["run"] == "kit2_drive_x"
    juliet = next(r for r in priv["rows"] if r["path"] == ["Juliet"])
    assert juliet["cites"][0]["crawl"] == 1 and juliet["kit_message"] == "unknown screen"
    pub = coverage.public_doc(led)
    assert not coverage.public_problems(pub, camera=CAM)
    assert "cites" not in json.dumps(pub) and "kit2_" not in json.dumps(pub)


def test_regenerating_gives_the_same_bytes(camera, tmp_path):
    a = coverage.text(coverage.public_doc(ledger()))
    b = coverage.text(coverage.public_doc(ledger()))
    assert a == b
    led = ledger(validity=True)
    out = coverage.write(led, private_path=tmp_path / "priv.json", seen_path=tmp_path / "seen.json")
    assert out == [tmp_path / "seen.json", tmp_path / "priv.json"]          # the public form is printed, never written
    first = [(tmp_path / n).read_bytes() for n in ("seen.json", "priv.json")]
    coverage.write(ledger(validity=True), private_path=tmp_path / "priv.json", seen_path=tmp_path / "seen.json")
    assert [(tmp_path / n).read_bytes() for n in ("seen.json", "priv.json")] == first
    assert not (camera.data / f"coverage_{CAM}.json").exists()
    if os.name != "nt":
        assert (tmp_path / "priv.json").stat().st_mode & 0o777 == 0o600


# ---------------------------------------------------------------- 1: the public form, public sources and the allow-list

def test_states_seen_never_reach_the_public_form(camera):
    """Greyed, tested, kit and equipment looks, a page scan's greyed row, crawl failures, failures.jsonl and proofs
    (a network row's saved option changing nothing among them) change the private form and leave the public one as it
    was, byte for byte: it is built from the public sources and the allow-list alone (decision 16)."""
    before = public_text()
    add_looks(camera,
              look(["Kilo"], screen="notice", result="greyed", blocker={"row": "Alpha"}),
              look(["Bravo"], screen="notice", result="refused", blocker={"equipment": "a flash"}),
              look(["Kilo"], did="choose", option="On"),
              look(["Golf"], result="kit_failed", kit_message="unknown screen"),
              look(["Hotel", "Inner"], screen="list", result="looked", by="crawl"))
    scan = camera.runs / "kit2_page_scan_x"
    scan.mkdir()
    (scan / "scan_mode.json").write_text(json.dumps({"mode": "stills"}), encoding="utf-8")
    (scan / "model.json").write_text(json.dumps([{"key": "p1", "page": "1/1", "breadcrumb": "Shooting > G1",
                                                  "rows": [{"label": "Kilo", "greyed": True}]}]), encoding="utf-8")
    (camera.runs / "kit2_pass2").mkdir()
    (camera.runs / "kit2_pass2" / "failures.jsonl").write_text(json.dumps({"path": ["Charlie"], "why": "x",
                                                                           "blocked": "Alpha On"}) + "\n",
                                                               encoding="utf-8")
    write_proofs(camera, "kit2_network", [
        {"path": ["Hotel"], "kind": "list", "index": 0, "label": "Off", "shown": "Off", "changes": [], "attempt": "A",
         "network": "network setting"},
        {"path": ["Hotel"], "kind": "list", "index": 1, "label": "On", "shown": "On", "attempt": "A",
         "changes": [{"key": "global:0x0105", "before": 0, "after": 1}], "network": "network setting"}])
    led = ledger()
    assert row(led, "Kilo")["status"] == "tested, no record changes"      # privately the latest look's
    assert public_text() == before
    pub = coverage.public_doc(led)
    by = {tuple(r["path"]): r for r in pub["rows"]}
    assert by[("Kilo",)]["status"] == "not yet tried" and by[("India",)]["status"] == "not yet tried"
    assert by[("Juliet",)]["status"] == "not yet tried" and by[("Foxtrot",)]["status"] == "not yet tried"
    assert ("Hotel", "Inner") not in by
    statuses = {st for o in pub["options"] for st in o["statuses"]} | {r["status"] for r in pub["rows"]}
    assert not statuses & {"tested, no record changes", "kit cannot read", "greyed in state"}
    # the network row's saved option (Off, its proof changing nothing) is no "tested, no record changes" anywhere
    hotel = {o["key"]: o for o in led.options}["global:0x0105"]["values"]
    assert hotel[0] != "tested, no record changes"


def seen_facts(camera):
    return json.loads(coverage.seen_file(CAM).read_text(encoding="utf-8"))["facts"]


def test_the_allow_listed_facts_live_in_the_seen_file(camera):
    """An information screen (a notice with the kit's address fields: a row label beside them qualifies the look
    privately, never goes public), a row seen to act, a hand check that changed a record and a Sony-listed row
    confirmed go into the seen file, and the public form is the build of the public sources and that file: what a
    fresh clone prints (no looks) is this computer's public form, byte for byte, and no copy of it is written."""
    add_looks(camera,
              look(["Kilo"], screen="notice", fields=["Device Address", "My Camera", "Alpha"]),
              look(["Version"], result="acted"),
              look(["Foxtrot"], by="hand", did="choose", option="Off", result="changed",
                   records_changed=["global:0x0103"]))
    led = coverage.build(CAM)
    assert row(led, "Kilo")["fields"] == ["Device Address", "Alpha"]          # privately, the label too
    written = coverage.write(led)
    assert written == [coverage.seen_file(CAM), coverage.private_file(CAM)]
    assert not (camera.data / f"coverage_{CAM}.json").exists()
    facts = {(x["kind"], tuple(x["path"])): x for x in seen_facts(camera)}
    assert facts[("info", ("Kilo",))]["fields"] == ["Device Address"]
    assert facts[("info", ("Echo",))]["fields"] == ["IP Address", "MAC Address"]
    assert ("acted", ("Version",)) in facts and ("confirmed", ("Delta",)) in facts
    assert facts[("hand_changed", ("Foxtrot",))]["values"] == {"global:0x0103": [0]}
    assert "option" not in json.dumps(seen_facts(camera))
    printed = coverage.public_build_text(CAM)
    doc = json.loads(printed)
    by = {tuple(r["path"]): r for r in doc["rows"]}
    assert by[("Kilo",)]["status"] == "information screen" and by[("Kilo",)]["fields"] == ["Device Address"]
    assert by[("Version",)]["status"] == "action, nothing to map" and "inferred" not in by[("Version",)]
    assert by[("Foxtrot",)]["status"] == "proved by hand" and by[("Delta",)]["confirmed"] is True
    assert {o["key"]: o for o in doc["options"]}["global:0x0103"]["statuses"]["proved by hand"] == [0]
    assert coverage.text(coverage.public_doc(led)) == printed
    assert coverage.public_build_problems(CAM) == []
    from camkit import datafiles
    assert datafiles.evidence_in_public(coverage.seen_file(CAM)) == []


def test_a_look_qualified_by_a_label_alone_stays_private(camera):
    """L4: a notice whose fields hold a row label outside its path and no address field is an information screen in the
    private form only; the public form and the seen file say nothing of it."""
    add_looks(camera, look(["Kilo"], screen="notice", fields=["Alpha"]))
    led = coverage.build(CAM)
    assert row(led, "Kilo")["status"] == "information screen" and row(led, "Kilo")["fields"] == ["Alpha"]
    assert {tuple(r["path"]): r for r in coverage.public_doc(led)["rows"]}[("Kilo",)]["status"] == "not yet tried"
    assert not any(x["path"] == ["Kilo"] for x in coverage.public_seen(led))
    pub_src = coverage.load_sources(CAM, public=True, allowed=[])
    assert not any(x["path"] == ["Kilo"] for x in coverage.allowed_from_looks(led.src.looks, pub_src))


def test_a_write_keeps_committed_facts_and_a_local_retraction_takes_one_out(camera, monkeypatch):
    """L9: a computer whose looks file lacks a committed fact keeps it (the union of the seen file and the looks' own);
    a retraction in the looks takes the committed facts of that row and kind out."""
    add_looks(camera, look(["Kilo"], screen="notice", fields=["Device Address"]))
    coverage.write(coverage.build(CAM))
    lines = camera.looks.read_text(encoding="utf-8").splitlines()
    camera.looks.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")       # a computer without that look
    coverage.forget()
    coverage.write(coverage.build(CAM))
    assert any(x["path"] == ["Kilo"] and x["kind"] == "info" for x in seen_facts(camera))
    import coverage as tool
    monkeypatch.setattr(sys, "argv", ["coverage.py", "--record", "--path", "Shooting > G1 > Kilo", "--did", "open",
                                      "--result", "retract"])
    tool.main()
    coverage.forget()
    coverage.write(coverage.build(CAM))
    assert not any(x["path"] == ["Kilo"] for x in seen_facts(camera))
    assert any(x["path"] == ["Echo"] for x in seen_facts(camera))                # its own look still stands
    by = {tuple(r["path"]): r for r in json.loads(coverage.public_build_text(CAM))["rows"]}
    assert by[("Kilo",)]["status"] == "not yet tried"


def test_a_public_form_in_data_is_refused_and_an_edit_of_the_seen_file_shows_there(camera):
    """L1: no public form is kept in data/, so a copy there is refused whatever it says, the build itself or one edited
    by hand ("needs equipment" with a lens); the facts a look established live in the seen file alone, where an edit
    shows in review, words its sources do not know (a field that is no address field, a value no setting has, a group
    no source names) are refused, and a good fact is what the printed form says."""
    from camkit import datafiles
    coverage.write(coverage.build(CAM, public=True))
    seen = coverage.seen_file(CAM)
    assert datafiles.evidence_in_public(seen) == []
    pub = camera.data / f"coverage_{CAM}.json"
    clean = coverage.public_build_text(CAM)
    a = '"path": ["Kilo"], "status": "not yet tried"'
    assert clean.count(a) == 1
    for t in (clean, clean.replace(a, '"path": ["Kilo"], "status": "needs equipment", "equipment": "a lens"')):
        pub.write_text(t, encoding="utf-8")
        found = datafiles.evidence_in_public(pub)
        assert len(found) == 1 and "no longer kept" in found[0] and f"coverage.py --camera {CAM} --print" in found[0]
    pub.unlink()
    doc = json.loads(seen.read_text(encoding="utf-8"))
    for fact, said in (({"kind": "info", "mode": "Stills", "tab": "Shooting", "group": "G1", "path": ["Kilo"],
                         "fields": ["SSID", "Password", "Alpha"]}, "field 'Alpha'"),
                       ({"kind": "hand_changed", "mode": "Stills", "tab": "Shooting", "group": "G1",
                         "path": ["Foxtrot"], "values": {"global:0x0103": [9]}}, "value"),
                       ({"kind": "acted", "mode": "Stills", "tab": "Shooting", "group": "Home", "path": ["Kilo"]},
                        "group 'Home'")):
        seen.write_text(coverage.text(dict(doc, facts=[fact])), encoding="utf-8")
        assert any(said in x for x in datafiles.evidence_in_public(seen)), said
        assert any(said in x for x in coverage.public_build_problems(CAM)), said           # --check says it too
    # a good fact by hand shows in the seen file, and the printed form says it
    seen.write_text(coverage.text(dict(doc, facts=[{"kind": "acted", "mode": "Stills", "tab": "Shooting",
                                                    "group": "G1", "path": ["Kilo"]}])), encoding="utf-8")
    assert datafiles.evidence_in_public(seen) == [] and coverage.public_build_problems(CAM) == []
    by = {tuple(r["path"]): r for r in json.loads(coverage.public_build_text(CAM))["rows"]}
    assert by[("Kilo",)]["status"] == "action, nothing to map"


def test_the_public_form_validates_and_holds_no_private_key(camera, tmp_path):
    import jsonschema
    schema = json.loads((ROOT / "schemas" / "coverage.schema.json").read_text(encoding="utf-8"))
    doc = coverage.public_doc(ledger())
    jsonschema.Draft202012Validator(schema).validate(doc)
    assert coverage.public_problems(doc, camera=CAM) == []
    bad = json.loads(json.dumps(doc))
    bad["rows"][0]["run"] = "kit2_x"
    bad["records"][0]["sha256"] = SHA
    found = coverage.public_problems(bad, camera=CAM)
    assert any("'run'" in x for x in found) and any("'sha256'" in x for x in found) and any("kit2_" in x for x in found)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(bad)


def test_unmapped_says_what_it_means_and_never_which_changed(camera, monkeypatch, capsys):
    """Decision 27: the public form's about and the counts --public-only prints say what "unmapped" means, true of
    every record no setting covers (no menu row found that changes it, what it holds not known, a change to it not
    proved), and the public form never tells which of them changed: the one the leads saw change (0x0200), the one
    they call never seen to change (0x0201) and the one nothing examined (0x0202) are alike "unmapped" there, and the
    private build keeps them apart."""
    import coverage as tool
    doc = coverage.public_doc(ledger())
    assert coverage.UNMAPPED_MEANS in doc["about"] and "no menu row that changes it" in coverage.UNMAPPED_MEANS
    assert not any(c.isdigit() for c in coverage.UNMAPPED_MEANS)
    public = {r["key"]: r["status"] for r in doc["records"]}
    assert {public[k] for k in ("global:0x0200", "global:0x0201", "global:0x0202")} == {"unmapped"}
    private = {r["key"]: r["status"] for r in ledger().records}
    assert len({private[k] for k in ("global:0x0200", "global:0x0201", "global:0x0202")}) == 3
    monkeypatch.setattr(sys, "argv", ["coverage.py", "--public-only"])
    tool.main()
    assert f"unmapped: {coverage.UNMAPPED_MEANS}" in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["coverage.py"])
    tool.main()
    assert "unmapped: " not in capsys.readouterr().out, "the private counts name each status apart"


def test_the_checkers_refuse_a_state_word_a_date_a_run_a_commit_and_free_text(camera, tmp_path, monkeypatch):
    """The reviewer's probes: a blocker naming a row with its value, a remote blocker carrying a date with its time, a
    run and a short commit, field names that are no address field, a 12-hex prefix in a note; also a greyed row not
    inferred from an inactive_when, a value said tested, and "runs/". coverage.public_problems refuses each (what
    --print, --check and --write ask of the form); datafiles.evidence_in_public and check_public's commit check refuse
    a copy of the form in data/, the clean one too."""
    import check_public as C
    from camkit import datafiles
    add_looks(camera, look(["Kilo"], screen="notice", fields=["IP Address"]))
    coverage.write(coverage.build(CAM))
    doc = json.loads(coverage.public_build_text(CAM))
    assert not coverage.public_problems(doc, camera=CAM)
    rows = {tuple(r["path"]): i for i, r in enumerate(doc["rows"])}
    probes = {
        "blocker with a value": lambda d: d["rows"][rows[("Golf",)]].update(blocker={"row": "Wired LAN Connect On"}),
        "remote and a date": lambda d: d["rows"][rows[("Golf",)]].update(
            blocker={"remote": "seen 2026-11-14T05:41:07 in drive_network3 at kit 1dadd7b"}),
        "a date with its time": lambda d: d["rows"][rows[("Golf",)]].update(equipment="2026-11-14T05:41:07"),
        "a short commit": lambda d: d["rows"][rows[("Golf",)]].update(equipment="kit 1dadd7b"),
        "fields": lambda d: d["rows"][rows[("Kilo",)]].update(fields=["IP Address", "My Camera Name",
                                                                      "SSID HOME-NET"]),
        "a label as a field": lambda d: d["rows"][rows[("Kilo",)]].update(fields=["IP Address", "Alpha"]),
        "a hex prefix": lambda d: d["rows"][rows[("Delta",)]].update(sony_note="start file sha 3f9a8b7c6d5e"),
        "a run folder": lambda d: d["rows"][rows[("Delta",)]].update(sony_note="runs/x"),
        "greyed, seen": lambda d: d["rows"][rows[("Bravo",)]].update(status="greyed in state"),
        "kit cannot read": lambda d: d["rows"][rows[("Bravo",)]].update(status="kit cannot read"),
        "a value tested": lambda d: d["options"][0]["statuses"].update({"tested, no record changes": [7]}),
        "a label unknown": lambda d: d["rows"][rows[("Bravo",)]].update(path=["Bravo", "My Camera Name"]),
        "a group unknown": lambda d: d["rows"][rows[("Bravo",)]].update(group="Home Network"),
        "about changed": lambda d: d.update(about="seen on the owner's camera"),
    }
    for what, change in probes.items():
        bad = json.loads(json.dumps(doc))
        change(bad)
        t = coverage.text(bad)
        assert coverage.public_problems(json.loads(t), t, camera=CAM), what
    folder = tmp_path / "pubcheck" / "data" / CAM
    folder.mkdir(parents=True)
    f = folder / f"coverage_{CAM}.json"
    f.write_text(coverage.text(doc), encoding="utf-8")
    for found in (datafiles.evidence_in_public(f), C.blob_problems(f"data/{CAM}/coverage_{CAM}.json", coverage.text(doc))):
        assert len(found) == 1 and "no longer kept" in found[0], found
    # each text check stands on its own, beside the vocabulary: a date with its time, seven hex digits, a run folder
    for word, said in (("seen 2026-11-14T05:41:07", "a date"), ("kit 1dadd7b", "a hash or a kit commit"),
                       ("sha 3f9a8b7c6d5e", "a hash or a kit commit"), ("runs/x", "a run's folder")):
        assert any(x.startswith(said) for x in coverage.public_problems({"note": word}, camera=CAM)), word
        assert any(x.startswith(said) for x in coverage.seen_problems({"note": word}, camera=CAM)), word


def test_a_public_row_names_a_blocker_by_its_row_alone():
    """Whatever the full build kept of a blocker (an option, equipment, a remote session: what a look saw), a public
    row keeps its row label alone; the private form keeps it whole."""
    e = {"mode": "Stills", "tab": "Shooting", "group": "G1", "path": ["India"], "nth": 0, "status": "greyed in state",
         "blocker": {"row": "Alpha", "option": "On", "remote": coverage.REMOTE}}
    assert coverage._row_out(e, coverage.ROW_PUBLIC, private=False)["blocker"] == {"row": "Alpha"}
    assert coverage._row_out(e, coverage.ROW_PRIVATE, private=True)["blocker"] == e["blocker"]


def test_check_public_refuses_a_public_form_or_a_looks_file_in_data(camera, tmp_path, monkeypatch):
    """No public form is kept in data/ (docs/decisions/0023): check_public's data check refuses a copy there, tracked or
    not, in one line, with the command that prints it and the fix that holds either way (delete it, with git rm where
    git tracks it, never git rm --cached), whether it holds private keys or is the build itself; the looks file too.
    A seen file of a camera with no definition is refused, as its words cannot be checked."""
    import check_public as C
    from camkit import datafiles
    d = camera.data
    monkeypatch.setattr(C, "ROOT", camera.data.parent.parent)
    assert C.data_problems() == []
    f = d / f"coverage_{CAM}.json"
    for t in (json.dumps({"rows": [{"path": ["Alpha"], "status": "proved", "t": "x", "start_sha256": SHA}],
                          "records": [{"key": "global:0x0001", "status": "unmapped", "cites": [{"run": "r"}]}]}),
              coverage.public_build_text(CAM)):
        f.write_text(t, encoding="utf-8")
        found = C.data_problems()
        assert found == [f"data/{CAM}/coverage_{CAM}.json: {datafiles.evidence_in_public(f)[0]}"], found
        assert f"kit/tools/coverage.py --camera {CAM} --print" in found[0] and "carries evidence" not in found[0]
        assert "Delete it, with git rm where git tracks it" in found[0] and "--cached" not in found[0]
    f.unlink()
    looks = d / f"looks_{CAM}.jsonl"
    looks.write_text("{}\n", encoding="utf-8")
    assert any("looks file" in x for x in datafiles.evidence_in_public(looks))
    looks.unlink()
    assert C.data_problems() == []
    other = tmp_path / "data" / "ILCE-0X0_fw1.00"
    other.mkdir(parents=True)
    g = other / "seen_ILCE-0X0_fw1.00.json"
    g.write_text(coverage.text(coverage.seen_doc("ILCE-0X0_fw1.00", [])), encoding="utf-8")
    assert any("no definition" in x for x in datafiles.evidence_in_public(g))


def test_the_a1_ii_public_form_agrees_with_its_definition():
    """The a1 II's public form as every clone prints it (its public sources and seen file): its schema, no private
    key, no word outside its vocabulary, every value it calls proved (or, of a setting whose list was proved partly on
    another setting, proved or named from a shared list) or not offered is so in the definition and the other way
    round, every top row and record of the definition's file is in it once."""
    import jsonschema
    t = coverage.public_build_text(A1)
    doc = json.loads(t)
    jsonschema.Draft202012Validator(json.loads((ROOT / "schemas" / "coverage.schema.json").read_text(
        encoding="utf-8"))).validate(doc)
    assert coverage.public_problems(doc, t, camera=A1) == []
    defn = definitions.load_public(A1)
    by_key = {o["key"]: o["statuses"] for o in doc["options"]}
    for s in defn["settings"]:
        if not s.get("values"):
            continue
        st = by_key.get(s["key"])
        assert st is not None, s["key"]
        p = s.get("proved") or {}
        linear = (p.get("sampled") or {}).get("linear") is True
        proved = {v for v, _ in s["values"]} if linear else (set() if "sampled" in p else set(p.get("values") or []))
        if p.get("shared") and not linear:      # the setting's mark: its listed values, never one of them "proved"
            proved = set()
            assert set(st.get(coverage.PROVED_OR_SHARED, [])) == set(p.get("values") or []), s["key"]
        assert set(st.get("proved", [])) == proved, s["key"]
        marks = {x["value"] for x in s.get("not_offered") or []} - proved - set(p.get("values") or [])
        assert set(st.get("not offered", [])) == marks, s["key"]
    tops = {(r["tab"], r["path"][0], r.get("nth", 0)) for r in doc["rows"] if len(r["path"]) == 1 and r["mode"] ==
            coverage.MENU_MODE}
    seen = {}
    for m in defn["menu"]:
        n = seen.get((m["tab"], m["label"]), 0)
        seen[(m["tab"], m["label"])] = n + 1
        assert (m["tab"], m["label"], n) in tops, m["label"]
    assert len(doc["records"]) == len({r["key"] for r in doc["records"]})
    serial = next(r for r in doc["rows"] if r["path"] == ["Display Serial Number"])
    assert serial["status"] == "information screen" and serial["inferred"] == "class"


def test_a_tree_without_runs_or_private_prints_the_a1_iis_public_form(tmp_path):
    """The gate of docs/decisions/0023's change of 2026-11-19, the public form no longer committed: a tree holding the
    kit's code (kit/camkit, kit/tools/coverage.py), schemas/, the a1 II's definition with its sample and its data
    folder, and no runs/ and no private/, prints the public form with kit/tools/coverage.py --print: a lean form (its
    schema, its words, no evidence), byte for byte this clone's own public build, and nothing written into the tree.
    A made-up looks file and run put into the tree's private/ and runs/ change none of those bytes, though --check
    reads the looks and says they would change the seen file."""
    import shutil
    import subprocess
    tree = tmp_path / "clone"
    shutil.copytree(ROOT / "kit" / "camkit", tree / "kit" / "camkit", ignore=shutil.ignore_patterns("__pycache__"))
    (tree / "kit" / "tools").mkdir()
    shutil.copy2(ROOT / "kit" / "tools" / "coverage.py", tree / "kit" / "tools" / "coverage.py")
    shutil.copytree(ROOT / "schemas", tree / "schemas")
    shutil.copytree(ROOT / "data" / A1, tree / "data" / A1)
    (tree / "editor" / "definitions").mkdir(parents=True)
    defn = ROOT / "editor" / "definitions" / f"{A1}.json"
    for p in (defn, definitions.sample(definitions.load_public(defn), defn)):
        shutil.copy2(p, tree / "editor" / "definitions" / p.name)
    assert not (tree / "data" / A1 / f"coverage_{A1}.json").exists()

    def files():
        return sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*") if "__pycache__" not in p.parts)
    before = files()
    env = {k: v for k, v in os.environ.items() if k not in ("CAMSET_RUNS", "CAMSET_LOOKS_DIR", "CAMSET_EVIDENCE_DIR",
                                                             "CAMSET_CAMERA")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    def tool(*argv):
        # the bytes as the program wrote them: no text layer here turns a CR LF back into a newline
        return subprocess.run([sys.executable, str(tree / "kit" / "tools" / "coverage.py"), "--camera", A1, *argv],
                              cwd=tree, env=env, capture_output=True, timeout=300)
    r = tool("--print")
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-2000:]
    assert files() == before and not (tree / "runs").exists() and not (tree / "private").exists()
    assert r.stdout == coverage.public_build_text(A1).encode("utf-8")
    text = r.stdout.decode("utf-8")
    doc = json.loads(text)
    assert coverage.public_problems(doc, text, camera=A1) == []
    assert doc["model"] == "ILCE-1M2" and doc["firmware"] == "4.00" and doc["rows"] and doc["options"] and doc["records"]
    # the mapper's own files, made up: a look that saw a row not yet tried act, and a crawl row the kit could not read
    row = next(x for x in doc["rows"] if x["status"] == "not yet tried" and len(x["path"]) == 1)
    looks = tree / "private" / "evidence" / A1 / f"looks_{A1}.jsonl"
    looks.parent.mkdir(parents=True)
    looks.write_text(json.dumps({"t": "2026-11-19T10:00:00", "run": "kit2_x", "kit": "abc1234", "by": "drive",
                                 "mode": row["mode"], "tab": row["tab"], "group": row["group"], "path": row["path"],
                                 "did": "open", "result": "acted", "records_changed": []}) + "\n", encoding="utf-8")
    crawl = tree / "runs" / A1 / "kit2_crawl_x"
    crawl.mkdir(parents=True)
    (crawl / "rows.jsonl").write_text(json.dumps({"page": "1/1", "slot": 1, "label": row["path"][0],
                                                  "outcome": "unknown screen", "kind": "unknown"}) + "\n",
                                      encoding="utf-8")
    before = files()
    again = tool("--print")
    assert again.returncode == 0 and again.stdout == r.stdout
    seen = tool("--check")
    assert seen.returncode == 1 and b"would change" in seen.stdout + seen.stderr, seen.stdout + seen.stderr
    assert files() == before


@pytest.mark.parametrize("key", sorted(p.stem for p in (ROOT / "editor" / "definitions").glob("*.json")
                                       if paths.KEY.fullmatch(p.stem)))
def test_every_definitions_public_form_is_lean_and_its_seen_file_clean(key):
    """What kit/tools/coverage.py --check asks in a clone, of every definition shipped: the public form its public
    sources and seen file give passes its schema and its closed vocabulary and holds no evidence, the seen file, where
    there is one, its own; and no copy of the form is in its data folder."""
    assert coverage.public_build_problems(key) == []
    assert not (definitions.data_dir(key) / f"coverage_{key}.json").exists(), "the public form is printed, never kept"


def test_git_shows_a_stray_copy_of_the_public_form():
    """.gitignore does not name the public form, so a copy printed into data/ shows in git status, beside check_public's
    one line refusing it (test_check_public_refuses_a_public_form_or_a_looks_file_in_data), and no path rule adds a
    second line ("ignored, yet tracked") whose git rm --cached would leave it on disk."""
    import shutil
    import subprocess
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("not a git clone")

    def ignored(f):
        return subprocess.run(["git", "check-ignore", "-q", "--no-index", f], cwd=ROOT).returncode == 0
    for f in (f"data/{A1}/coverage_{A1}.json", "data/ILCE-0X0_fw1.00/coverage_ILCE-0X0_fw1.00.json",
              f"data/{A1}/seen_{A1}.json"):
        assert not ignored(f), f


def test_print_writes_its_bytes_whatever_newline_the_console_turns_them_into(camera, monkeypatch):
    """--print writes the public form's bytes under the console's text layer, so a Windows console, whose text layer
    writes each newline as CR LF, gets the same bytes as every other clone (here a text layer that does so on any
    computer)."""
    import io
    import coverage as tool
    raw = io.BytesIO()
    console = io.TextIOWrapper(raw, encoding="utf-8", newline="\r\n")
    monkeypatch.setattr(sys, "stdout", console)
    monkeypatch.setattr(sys, "argv", ["coverage.py", "--print"])
    tool.main()
    console.flush()
    assert raw.getvalue() == coverage.public_build_text(CAM).encode("utf-8")


def test_the_tool_prints_the_public_form_and_checks_the_seen_file(camera, monkeypatch, capsys):
    """--print prints the public build (the public sources and the seen file as they stand, never this computer's
    looks) and writes nothing; --check exits 1 while this computer's looks would change the seen file (Echo's look is
    in no seen file yet), passes once --write has written it (no public form written into data/), and --print then
    says what the look found; a camera with no definition prints nothing."""
    import coverage as tool

    def run(*argv):
        monkeypatch.setattr(sys, "argv", ["coverage.py", *argv])
        tool.main()
        return capsys.readouterr().out
    listed = sorted(p.name for p in camera.data.iterdir())
    out = run("--print")
    assert out == coverage.public_build_text(CAM)
    assert {tuple(r["path"]): r for r in json.loads(out)["rows"]}[("Echo",)]["status"] == "not yet tried"
    assert sorted(p.name for p in camera.data.iterdir()) == listed
    with pytest.raises(SystemExit) as e:
        run("--check")
    assert "would change" in str(e.value) and "kit/tools/coverage.py --write" in str(e.value)
    run("--write")
    assert sorted(p.name for p in camera.data.iterdir()) == sorted([*listed, f"seen_{CAM}.json"])
    out = run("--check")
    assert "lean" in out and "would change" not in out
    out = run("--print")
    assert {tuple(r["path"]): r for r in json.loads(out)["rows"]}[("Echo",)]["status"] == "information screen"
    monkeypatch.setattr(tool, "camera_or_exit", lambda: "ILCE-0X0_fw1.00")
    with pytest.raises(SystemExit) as e:
        run("--print")
    assert "no definition" in str(e.value)


def test_a_definition_never_carries_the_camera_files_own_list():
    """L8: save_load_excluded is the camera file's alone; the definition schema refuses it in a definition's camera
    section."""
    import jsonschema
    from referencing import Registry, Resource

    def doc_of(p):
        return json.loads(Path(p).read_text(encoding="utf-8"))
    reg = Registry().with_resources((p.name, Resource.from_contents(doc_of(p))) for p in (ROOT / "schemas").glob("*.json"))
    v = jsonschema.Draft202012Validator(doc_of(ROOT / "schemas" / "definition.schema.json"), registry=reg)
    doc = doc_of(definitions.path(A1))
    assert not list(v.iter_errors(doc))
    cam = json.loads(definitions.camera_file(A1).read_text(encoding="utf-8"))
    bad = dict(doc, camera=dict(doc["camera"], save_load_excluded=cam["save_load_excluded"]))
    assert list(v.iter_errors(bad))


# ---------------------------------------------------------------- 2: values left, options, modes

def test_a_row_is_proved_only_when_every_setting_on_it_is(camera):
    """Mutation guard: a row with one proved setting and one with no proof is not "proved"."""
    led = ledger()
    e = row(led, "Alpha")
    led.src.definition["settings"].append(setting("global:0x0109", "Alpha two", ["Alpha", "Two"], ONOFF))
    by_key = {s["key"]: s for s in led.src.definition["settings"]}
    e["settings"].append("global:0x0109")
    coverage._one_row(e, {}, by_key, {}, set(), {})
    assert e["status"] != "proved"


def test_values_left_keeps_a_row_unsettled_and_todo_lists_it(camera):
    """A setting proved on some of its values is "proved", yet the row carries values_left, is never settled, and
    --todo lists it with the count (Fn Menu Settings' 5,940 untried values on the a1 II)."""
    SETTINGS.append(setting("global:0x0110", "Lima", ["Lima"], ((0, "A"), (1, "B"), (2, "C")),
                            proved={"values": [0]}))
    MENU.append(("Shooting", "G1", "Lima"))
    try:
        camera.doc["settings"], camera.doc["menu"] = SETTINGS, [{"tab": t, "group": g, "label": lab, "order": i}
                                                                for i, (t, g, lab) in enumerate(MENU)]
        camera.defn.write_text(json.dumps(camera.doc), encoding="utf-8")
        led = ledger()
        lima = row(led, "Lima")
        assert lima["status"] == "proved" and lima["values_left"] == 2
        v = coverage.settled(["Lima"], camera=CAM, ledger=led)
        assert not v.skip and "2 value(s) still to try" in v.reason
        assert coverage.settled(["Lima"], "A", camera=CAM, ledger=led).skip           # the proved value
        assert not coverage.settled(["Lima"], "B", camera=CAM, ledger=led).skip
        assert not coverage.settled(["Lima"], "Z", camera=CAM, ledger=led).skip       # names no value
        item = next(x for x in coverage.todo(led) if x["entry"]["path"] == ["Lima"])
        assert item["needs"] == "remote-proof"
        assert {tuple(r["path"]): r for r in coverage.public_doc(led)["rows"]}[("Lima",)]["values_left"] == 2
    finally:
        SETTINGS.pop()
        MENU.pop()


def test_settled_never_takes_another_modes_entry(camera):
    """A mode with no entry for the path is not settled (Mike is a Movie row: a Stills crawl does not skip it), and with
    no mode given the least settled of the modes' entries decides (mutation guard: the most settled never wins)."""
    led = ledger()
    assert coverage.settled(["Mike"], mode="Movie", camera=CAM, ledger=led).skip
    v = coverage.settled(["Mike"], mode="Stills", camera=CAM, ledger=led)
    assert not v.skip and "no ledger entry for it in Stills" in v.reason
    twin = dict(row(led, "Mike"), mode="Stills", status="not yet tried", settings=[], tied=[], path=["Mike"])
    led.rows.append(twin)
    led._by_path = None
    assert not coverage.settled(["Mike"], camera=CAM, ledger=led).skip
    assert coverage.settled(["Mike"], mode="Movie", camera=CAM, ledger=led).skip


def test_prove_filter_judges_each_planned_option_and_only_list_and_dialog_jobs(camera, capsys):
    """By default every job is kept and the ledger's word printed; with --skip-settled a list or dialog job goes only
    when every planned option is settled, never another kind, and never with --context, --first, --tables, --wb,
    --wb-corners, --looks, --look-base, --redo or --help-text."""
    jobs = [{"path": ["Alpha"], "kind": "list", "labels": ["Off", "On"]},
            {"path": ["Foxtrot"], "kind": "list", "labels": ["Off", "On"]},
            {"path": ["Alpha"], "kind": "list", "labels": ["Off", "On", "Auto"], "choose": [0, 1]},
            {"path": ["Alpha"], "kind": "axis", "option": "x", "values": ["1", "2"]},
            {"path": ["Alpha"], "kind": "table", "labels": ["Off"]}]
    a = SimpleNamespace(skip_settled=False, scan=None, start=None)
    assert coverage.prove_filter(jobs, a) == jobs
    out = capsys.readouterr().out
    assert "coverage: Alpha: proved; 2 of its 2 planned options settled; proved all the same" in out
    a.skip_settled = True
    kept = coverage.prove_filter(jobs, a)
    assert kept == [jobs[1], jobs[3], jobs[4]]
    out = capsys.readouterr().out
    assert "left out (--skip-settled)" in out
    assert "Foxtrot: tested, no record changes, 1 value(s) still to try; 1 of its 2 planned options settled" in out
    from proving.jobs import planned
    assert coverage.prove_filter([jobs[2]], a, planned) == []
    for flag in ("context", "first", "tables", "wb", "wb_corners", "looks", "look_base", "redo", "help_text"):
        b = SimpleNamespace(skip_settled=True, scan=None, start=None, **{flag: True})
        assert coverage.prove_filter(jobs, b) == jobs, flag
        assert "leaves nothing out on this run" in capsys.readouterr().out


# ---------------------------------------------------------------- 3, 9, 10: the gates

def test_the_drive_gate_never_skips_and_records_its_look(camera, capsys):
    """drive.py's gate, made as the run starts, prints nothing then (its ledger is built meanwhile); once the link is
    open (say) it prints what the ledger says and goes on, settled or not; after the run it records one look."""
    a = SimpleNamespace(path=["Alpha"], run="kit2_drive_t", scan=None, network=False, owner=False)
    gate = coverage.drive_gate(a)
    assert "coverage:" not in capsys.readouterr().out
    gate.say()
    out = capsys.readouterr().out
    assert "coverage: settled: Alpha: proved" in out and "drive.py goes on (it never skips)" in out
    gate = coverage.drive_gate(SimpleNamespace(**{**vars(a), "path": ["Kilo"]}))
    gate.say()
    assert "coverage: Kilo: not yet tried" in capsys.readouterr().out
    (camera.runs / "kit2_drive_t").mkdir(parents=True)
    (camera.runs / "kit2_drive_t" / "drive.jsonl").write_text(json.dumps({
        "path": ["Kilo"], "presses": ["right", "menu"], "completed": True,
        "screens": [{"after": "right", "kind": "list", "text": "Kilo\nOff\nOn"}], "before": "00001_before.DAT",
        "after": "00004_after.DAT", "changes": []}) + "\n", encoding="utf-8")
    n = len(camera.looks.read_text(encoding="utf-8").splitlines())
    assert gate.after()
    lines = camera.looks.read_text(encoding="utf-8").splitlines()
    assert len(lines) == n + 1
    last = json.loads(lines[-1])
    assert last["by"] == "drive" and last["path"] == ["Kilo"] and last["result"] == "no_change"
    assert last["tab"] == "Shooting" and last["group"] == "G1" and "Off" not in last.get("fields", [])
    gate = coverage.drive_gate(a)
    assert not gate.after()                                                        # no new result line: no look


def test_a_ledger_warm_began_is_the_one_the_gates_get_built_once(camera, monkeypatch):
    """camkit.coverage.warm builds the made-up camera's real ledger on its own thread; ledger_for asked while it builds
    and again after gets that very ledger, built once (the lock in ledger_for), its rows those of a build in line."""
    builds = []
    real = coverage._build
    monkeypatch.setattr(coverage, "_build", lambda *a, **k: builds.append(1) or real(*a, **k))
    coverage.forget()
    coverage.warm(CAM)
    first = coverage.ledger_for(CAM)
    second = coverage.ledger_for(CAM)
    assert first is second and builds == [1]
    assert [e["status"] for e in first.rows] == [e["status"] for e in ledger().rows] and first.rows


def test_no_ledger_says_so_and_skips_nothing(camera, capsys):
    camera.looks.unlink()
    coverage.forget()
    gate = coverage.drive_gate(SimpleNamespace(path=["Alpha"], run="kit2_drive_t", scan=None, network=False,
                                               owner=False))
    gate.say()
    assert "no coverage ledger" in capsys.readouterr().out and gate.camera == CAM
    a = SimpleNamespace(skip_settled=True, scan=None, start=None)
    assert coverage.prove_filter([{"path": ["Alpha"], "kind": "list", "labels": ["On"]}], a) == \
        [{"path": ["Alpha"], "kind": "list", "labels": ["On"]}]
    assert "no row is left out" in capsys.readouterr().out


def test_a_ledger_error_never_breaks_a_run(camera, monkeypatch, capsys):
    """Every hook catches what the ledger raises, says it in one line and changes nothing: the drive gate, the crawl
    gate's skip, after and lap, prove_filter, the prove looks."""
    def boom(*a, **k):
        raise RuntimeError("broken ledger")
    monkeypatch.setattr(coverage, "settled", boom)
    gate = coverage.drive_gate(SimpleNamespace(path=["Alpha"], run="kit2_drive_t", scan=None, network=False,
                                               owner=False))
    gate.say()
    assert "the ledger failed (RuntimeError: broken ledger)" in capsys.readouterr().out
    monkeypatch.setattr(coverage, "drive_look", boom)
    (camera.runs / "kit2_drive_t").mkdir(parents=True)
    (camera.runs / "kit2_drive_t" / "drive.jsonl").write_text(json.dumps({"path": ["Alpha"]}) + "\n", encoding="utf-8")
    assert gate.after() is False
    jobs = [{"path": ["Alpha"], "kind": "list", "labels": ["On"]}]
    assert coverage.prove_filter(jobs, SimpleNamespace(skip_settled=True, scan=None, start=None)) == jobs
    crawl_gate = coverage.CrawlGate(SimpleNamespace(root=camera.runs, dir=camera.runs / "kit2_crawl"),
                                    SimpleNamespace(skip_settled=True, scan=None, network=False), None)
    assert crawl_gate.skip({"breadcrumb": "Shooting > G1"}, {"label": "Alpha"}) is None
    monkeypatch.setattr(coverage, "crawl_looks", boom)
    monkeypatch.setattr(coverage, "append_look", boom)
    crawl_gate.after({"label": "Alpha"}, {})
    crawl_gate.lap(None)
    looks = coverage.ProveLooks(SimpleNamespace(root=camera.runs, dir=camera.runs / "kit2_crawl"),
                                camera.runs / "p.jsonl", camera.runs / "f.jsonl")
    (camera.runs / "p.jsonl").write_text(json.dumps({"path": ["Alpha"]}) + "\n", encoding="utf-8")
    looks.after({"path": ["Alpha"]})
    monkeypatch.setattr(coverage, "ledger_for", boom)
    assert coverage.CrawlGate(SimpleNamespace(root=camera.runs, dir=camera.runs / "c"),
                              SimpleNamespace(skip_settled=True, scan=None, network=False), None).led is None
    said = capsys.readouterr().out
    assert said.count("coverage:") >= 6


def test_the_crawl_skips_a_settled_row_only_with_skip_settled(camera, capsys):
    from camkit import crawl
    presses = []

    class Cam:
        def read(self):
            return SimpleNamespace(signature="s", kind="menu")

        def press(self, key):
            presses.append(key)
    model = {"p": {"breadcrumb": "Shooting > G1", "page": "1/1", "rows": [{"label": "Alpha"}, {"label": "Kilo"}]}}
    cycle = [{"page": "p", "row": 0, "signature": "s", "kind": "menu"}]
    run = SimpleNamespace(root=camera.runs, dir=camera.runs / "kit2_crawl")
    gate = coverage.CrawlGate(run, SimpleNamespace(skip_settled=True, scan=None, network=False), None)
    out = crawl.crawl(Cam(), cycle, model, tabs=("Shooting",), skip=gate.skip)
    assert presses == [] and out.rows[0].outcome.startswith(coverage.CRAWL_SKIPPED + ": Alpha: proved")
    assert gate.skip(model["p"], {"label": "Kilo"}) is None
    quiet = coverage.CrawlGate(run, SimpleNamespace(skip_settled=False, scan=None, network=False), None)
    assert quiet.skip(model["p"], {"label": "Alpha"}) is None
    assert "settled: Alpha: proved; opened all the same" in capsys.readouterr().out
    # a row the lap leaves unopened all the same (a first open's rule, never-open): the skip wins, and the ledger's line
    # never says the row is opened (2026-11-15, a camera session: "opened all the same" printed before such a skip)
    from camkit import first_open

    class First:
        pending = []

        def skips(self, path):
            return path == ("Alpha",)

        def opening(self, path):
            return f"{first_open.UNSEEN} (no statement)" if self.skips(path) else None
    out = crawl.crawl(Cam(), cycle, model, tabs=("Shooting",), skip=quiet.skip, first=First())
    said = capsys.readouterr().out
    assert "settled: Alpha: proved" in said and "opened all the same" not in said
    assert presses == [] and out.rows[0].outcome == f"{first_open.SKIPPED} (no statement)"
    assert quiet.skip(model["p"], {"label": "Alpha"}, opened=False) is None
    said = capsys.readouterr().out
    assert "settled: Alpha: proved" in said and "opened all the same" not in said
    told = []
    never = {"p": {"breadcrumb": "Shooting > G1", "page": "1/1", "rows": [{"label": "Format"}]}}
    for m in (never, model):
        crawl.crawl(Cam(), cycle, m, tabs=("Shooting",), skip=lambda page, row, opened=True: told.append(opened))
    assert told == [False, True] and presses == ["right"]


def test_pass1_map_refuses_a_crawl_that_skipped(camera, capsys):
    """A --skip-settled crawl's map has holes: kit/pass1_map.py refuses it for pass 1's map, and --own says so."""
    import pass1_map
    run = camera.runs / "kit2_crawl_skip"
    run.mkdir()
    (run / "rows.jsonl").write_text(json.dumps({"page": "1/1", "label": "Alpha",
                                                "outcome": "skipped: settled: Alpha: proved"}) + "\n", encoding="utf-8")
    (run / "options.jsonl").write_text(json.dumps({"path": ["Kilo"], "kind": "list", "index": 0, "frame": "f1.png",
                                                   "ocr": "Off", "agreed": True}) + "\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        pass1_map.main([str(run)])
    assert "skipped 1 rows" in str(e.value) and "holes" in str(e.value)
    pass1_map.main([str(run), "--own"])
    assert "has holes there" in capsys.readouterr().out
    assert coverage.crawl_skipped(camera.runs / "kit2_crawl") == 0


def test_the_skip_flags_say_what_they_do():
    import argparse
    for crawl, words in ((True, "holes"), (False, "--context")):
        ap = argparse.ArgumentParser()
        coverage.add_skip_argument(ap, crawl=crawl)
        assert words in ap.format_help().replace("\n", " ")
        assert ap.parse_args([]).skip_settled is False


def test_prove_looks_follow_the_rows(camera):
    run = SimpleNamespace(root=camera.runs, dir=camera.runs / "kit2_pass2")
    run.dir.mkdir()
    proofs, fails = run.dir / "proofs.jsonl", run.dir / "failures.jsonl"
    looks = coverage.ProveLooks(run, proofs, fails)
    job = {"path": ["Kilo"], "kind": "list"}
    proofs.write_text(json.dumps({"path": ["Kilo"], "label": "On", "changes": [{"key": "global:0x0200", "before": 0,
                                                                               "after": 1}]}) + "\n",
                      encoding="utf-8")
    looks.after(job)
    fails.write_text(json.dumps({"path": ["Kilo"], "why": "x", "blocked": "Alpha On"}) + "\n", encoding="utf-8")
    looks.after(job)
    looks.after(job)                       # nothing new: no look
    with open(fails, "a", encoding="utf-8") as f:
        f.write(json.dumps({"path": ["Kilo"], "why": "lost at 'Kilo'"}) + "\n")
    looks.after(job)
    got = [json.loads(x) for x in camera.looks.read_text(encoding="utf-8").splitlines()][-3:]
    assert got[0]["result"] == "changed" and got[0]["records_changed"] == ["global:0x0200"]
    assert got[1]["result"] == "refused" and got[1]["blocker"] == {"row": "Alpha"}
    assert "On" not in json.dumps(got[1]["blocker"])
    assert got[2]["result"] == "not_reached"                 # lost: tried again by any run
    ctx = coverage.ProveLooks(run, proofs, fails, context="held on Hi")
    with open(proofs, "a", encoding="utf-8") as f:
        f.write(json.dumps({"path": ["Kilo"], "label": "On", "changes": []}) + "\n")
    ctx.after(job)
    last = json.loads(camera.looks.read_text(encoding="utf-8").splitlines()[-1])
    assert last["result"] == "looked" and "Hi" not in json.dumps(last)


# ---------------------------------------------------------------- 4: what a look says

def test_an_unknown_or_field_screen_is_no_information_screen(camera):
    """A screen the kit could not classify, titled with the row's own label, and a number-field editor change nothing
    and are no information screen; the row is not settled."""
    line = {"path": ["Kilo"], "presses": ["right", "menu"], "completed": True,
            "screens": [{"after": "right", "kind": "unknown", "text": "Kilo\nx1.0"}],
            "before": "00001_before.DAT", "after": "00002_after.DAT", "changes": []}
    lk = coverage.drive_look(line, CAM, "Stills", "kit2_drive_zoom")
    assert lk["did"] == "open" and lk["result"] == "no_change"
    add_looks(camera, {k: v for k, v in lk.items() if v is not None})
    led = ledger()
    assert row(led, "Kilo")["status"] == "not yet tried"
    assert not coverage.settled(["Kilo"], camera=CAM, ledger=led).skip
    fields = dict(line, screens=[{"after": "right", "kind": "fields", "text": "Kilo\n10\n:\n30", "fields": ["Alpha"]}])
    add_looks(camera, {k: v for k, v in coverage.drive_look(fields, CAM, "Stills", "kit2_drive_x2").items()
                       if v is not None})
    assert row(ledger(), "Kilo")["status"] == "not yet tried"


def test_an_information_screen_comes_from_a_notice_alone(camera):
    """Mutation guard: the same fields on a list, a dialog or an unknown screen make no information screen; a notice
    with an address field and no refusal does, and drive_look keeps it unchanged rather than greyed."""
    for kind in ("list", "dialog", "unknown", "fields", "submenu"):
        add_looks(camera, look(["Kilo"], screen=kind, fields=["IP Address"]))
        assert row(ledger(), "Kilo")["status"] == "not yet tried", kind
    line = {"path": ["Kilo"], "presses": ["right", "menu"], "completed": True,
            "screens": [{"after": "right", "kind": "notice", "fields": ["Device Address"]}],
            "before": "a.DAT", "after": "b.DAT", "changes": []}
    lk = coverage.drive_look(line, CAM, None, "kit2_drive_x")
    assert lk["result"] == "no_change" and lk["fields"] == ["Device Address"]
    add_looks(camera, {k: v for k, v in lk.items() if v is not None})
    assert row(ledger(), "Kilo")["status"] == "information screen"
    refusal = dict(line, screens=[{"after": "right", "kind": "notice", "fields": ["Device Address"],
                                   "notice": "This function is currently disabled."}])
    assert coverage.drive_look(refusal, CAM, None, "r")["result"] == "greyed"


def test_the_enter_that_opens_a_row_is_no_choice(camera):
    line = {"path": ["Kilo"], "presses": ["enter:Kilo", "menu"], "completed": True,
            "screens": [{"after": "enter:Kilo", "kind": "list", "text": "Off\nOn"}],
            "before": "a.DAT", "after": "b.DAT", "changes": []}
    lk = coverage.drive_look(line, CAM, "Stills", "kit2_drive_x3")
    assert lk["did"] == "open"
    add_looks(camera, {k: v for k, v in lk.items() if v is not None})
    assert not coverage.settled(["Kilo"], camera=CAM, ledger=ledger()).skip
    for presses in (["right", "down", "enter:On"], ["enter!:Kilo", "down@3", "ms_enter:On"]):
        assert coverage.drive_look(dict(line, presses=presses), CAM, None, "r")["did"] == "choose", presses
    assert coverage.press_key("enter!:x") == "enter" and coverage.press_key(" Down@3") == "down"


def test_a_drive_run_that_presses_inside_the_row_is_a_choice(camera):
    """What a drive.py run did (drive_look, 2026-11-15): "open" only where every press after the opening one is a
    looking key (safety.LOOK_KEYS: up, down, MENU), or none follows it; any other press after it (left, right, a dial,
    Enter, C4) makes it "choose". kit2_a1fin_expcomp_cancel2: Right, Left, Left, MENU on a seen Exposure Comp. changed
    a record and was written as an open, which made the row unseen."""
    line = {"path": ["Kilo"], "completed": True, "screens": [{"after": "right", "kind": "slider"}],
            "before": "a.DAT", "after": "b.DAT", "changes": [{"key": "global:0x0100", "before": 0, "after": 1}]}

    def did(presses):
        return coverage.drive_look(dict(line, presses=presses), CAM, None, "r")["did"]
    for presses in (["right"], ["right", "menu"], ["right", "down", "up", "menu"], ["enter:Kilo"], ["enter!:Kilo"],
                    ["down@3", "right", "ms_down", "ms_up", "menu"], ["right", "down@367:Kilo", "menu"],
                    # a look-alike letter is the key drive.py sends (canonical_key): Down, a looking key
                    ["right", "dоwn", "menu"], [], ["menu"]):
        assert did(presses) == "open", presses
    for presses in (["right", "left", "left", "menu"], ["right", "dial.front.1"], ["right", "dial.wheel.-2:Kilo"],
                    ["right", "enter:On"], ["enter:Kilo", "left"], ["right", "right"], ["right", "ms_left"],
                    ["right", "help"], ["right", "c4set"], ["right", "down", "enter!:x"], ["enter:Kilo", "menu", "up",
                                                                                         "ms_right"]):
        assert did(presses) == "choose", presses


def test_the_latest_look_wins_and_a_retraction_leaves_nothing(camera, monkeypatch, capsys):
    """Echo's information screen holds until a later look of the same row and kind says otherwise, or until the owner
    retracts it (kit/tools/coverage.py --record --result retract), which the private and public forms then follow."""
    assert row(ledger(), "Echo")["status"] == "information screen"
    add_looks(camera, look(["Echo"], screen="unknown"))
    assert row(ledger(), "Echo")["status"] == "not yet tried"
    add_looks(camera, look(["Echo"], screen="notice", fields=["IP Address"]))
    assert row(ledger(), "Echo")["status"] == "information screen"
    import coverage as tool
    monkeypatch.setattr(sys, "argv", ["coverage.py", "--record", "--path", "Shooting > G1 > Echo", "--did", "open",
                                      "--result", "retract"])
    tool.main()
    assert row(ledger(), "Echo")["status"] == "not yet tried"
    by = {tuple(r["path"]): r for r in coverage.public_doc(ledger())["rows"]}
    assert by[("Echo",)]["status"] == "not yet tried"
    last = json.loads(camera.looks.read_text(encoding="utf-8").splitlines()[-1])
    assert last["result"] == "retract" and "start_sha256" not in last
    if os.name != "nt":
        assert camera.looks.stat().st_mode & 0o777 == 0o600


def test_every_look_the_kit_makes_is_one_the_schema_holds(camera):
    import jsonschema
    schema = jsonschema.Draft202012Validator(json.loads((ROOT / "schemas" / "looks.schema.json").read_text(
        encoding="utf-8")))
    for x in LOOKS:
        schema.validate(x)
        assert coverage.look_problems(x) == []
    line = {"path": ["Bluetooth Rmt Ctrl"], "presses": ["right"], "completed": True, "network": {"Bluetooth Rmt Ctrl":
            "2026-11-13"}, "screens": [{"after": "right", "frame": "00002_right.png", "kind": "notice", "fields": [],
            "notice": "This operation or setting is not available as follows Alpha", "withheld": 2}],
            "before": "00001_before.DAT", "after": "00003_after.DAT", "changes": []}
    lk = coverage.drive_look(line, CAM, "Stills", "kit2_drive_network3")
    lk = {k: v for k, v in lk.items() if v is not None}
    schema.validate(lk)
    assert lk["result"] == "greyed" and lk["blocker"] == {"row": "Alpha"} and lk["did"] == "open"
    assert lk["decision"] == "network 2026-11-13"
    info = dict(line, network=None, screens=[{"after": "right", "kind": "fields", "fields": ["IP Address"]}],
                changes=[{"key": "global:0x0100", "before": 0, "after": 1}], presses=["right", "enter:On"])
    lk = coverage.drive_look(info, CAM, None, "kit2_drive_x")
    assert lk["result"] == "changed" and lk["records_changed"] == ["global:0x0100"] and lk["did"] == "choose"
    assert lk["fields"] == ["IP Address"] and "before" not in json.dumps(lk["records_changed"])
    for x in coverage.crawl_looks({"page": "1/2", "label": "Kilo", "outcome": "submenu crawled", "kind": "submenu",
                                   "submenu": [{"label": "Inner", "outcome": "no response to Right"}]},
                                  ["Shooting", "G1"], "Stills", "kit2_crawl", CAM):
        schema.validate({k: v for k, v in x.items() if v is not None})
    schema.validate(look(["Echo"], by="hand", result="retract"))
    with pytest.raises(jsonschema.ValidationError):
        schema.validate(look(["Echo"], by="import"))
    bad = dict(LOOKS[0], records_changed=["0x0100 -> 3"])
    with pytest.raises(jsonschema.ValidationError):
        schema.validate(bad)
    assert coverage.look_problems(bad)
    assert coverage.crawl_looks({"label": "(withheld)", "outcome": "walked"}, [], None, "r", CAM) == []
    assert coverage.crawl_looks({"label": "Kilo", "outcome": "skipped: settled: Kilo"}, [], None, "r", CAM) == []


def test_a_look_that_is_not_one_is_refused_and_a_failed_write_breaks_nothing(camera, tmp_path, monkeypatch):
    said = []
    bad = look(["Alpha"], records_changed=["global:0x0100=1"])
    assert not coverage.append_look(CAM, bad, say=said.append) and "record keys" in said[-1]
    assert not coverage.append_look(CAM, look(["Alpha"], current="On"), say=said.append) and "'current'" in said[-1]
    blocker = tmp_path / "a-file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("CAMSET_LOOKS_DIR", str(blocker))       # a folder that cannot be made
    assert not coverage.append_look(CAM, look(["Alpha"]), say=said.append) and "the run goes on" in said[-1]
    monkeypatch.setenv("CAMSET_LOOKS_DIR", str(tmp_path / "priv"))
    assert coverage.append_look(CAM, look(["Alpha"]), private=True, say=said.append)
    p = coverage.looks_file(CAM)
    assert json.loads(p.read_text(encoding="utf-8").splitlines()[0])["path"] == ["Alpha"]
    if os.name != "nt":
        assert p.stat().st_mode & 0o777 == 0o600 and p.parent.stat().st_mode & 0o777 == 0o700


# ---------------------------------------------------------------- 5, 6: the kit's failures, no proof possible

def test_only_a_failure_that_comes_again_holds_a_row_back(camera, monkeypatch):
    """"kit cannot read" for an unknown screen or no response to Right alone; a lost row, an error, a walk cut short, a
    run that did not finish are tried again by any run (not_reached)."""
    crawl = camera.runs / "kit2_crawl"
    rows = [{"page": "3/9", "label": "Juliet", "outcome": o} for o in ("lost", "error: x", "incomplete: TimeoutError",
                                                                        "submenu: lost at 'x'")]
    (crawl / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (camera.runs / "kit2_pass2").mkdir()
    (camera.runs / "kit2_pass2" / "failures.jsonl").write_text(json.dumps({"path": ["Juliet"], "why": "error: x"})
                                                               + "\n", encoding="utf-8")
    add_looks(camera, look(["Juliet"], did="choose", option="On", result="not_reached",
                           kit_message="the run did not finish"),
              look(["Juliet", "Inner"], result="kit_failed", kit_message="lost"))
    led = ledger()
    assert row(led, "Juliet")["status"] == "not yet tried"
    assert row(led, "Juliet", "Inner")["status"] == "not yet tried"
    (crawl / "rows.jsonl").write_text(json.dumps({"page": "3/9", "label": "Juliet",
                                                  "outcome": "no response to Right"}) + "\n", encoding="utf-8")
    assert row(ledger(), "Juliet")["status"] == "kit cannot read"
    assert [x["result"] for x in coverage.crawl_looks({"label": "K", "outcome": "lost"}, [], None, "r", CAM)] == \
        ["not_reached"]
    unfinished = {"path": ["Kilo"], "presses": ["right"], "completed": False, "before": "a", "after": "b",
                  "changes": [], "screens": []}
    assert coverage.drive_look(unfinished, CAM, None, "r")["result"] == "not_reached"
    assert coverage.drive_look(dict(unfinished, outcome="unknown screen"), CAM, None, "r")["result"] == "kit_failed"


def test_a_first_open_checked_clean_keeps_the_rows_kit_failure(camera, tmp_path, monkeypatch):
    """camkit.first_open writes a row's clean look ("first open checked") before the crawl's held look of it: Juliet,
    which a crawl found on an unknown screen, is seen opened after its clean first open, and the ledger's latest look of
    it stays the crawl's kit failure, which is true (after it, the ledger would set the failure aside)."""
    import camkit
    from camkit import first_open
    from camkit.runs import restore_pending
    from test_first_open import crawl_look, first_opens, open_looks
    monkeypatch.setattr(camkit, "RUNS", paths.runs_top())     # a marker in the test's own runs/ alone, never the clone's
    juliet = ("Juliet",)
    assert row(ledger(), *juliet)["status"] == "kit cannot read"
    fo, _sent, _ = first_opens(tmp_path, root=camera.runs, run_name="kit2_first")
    assert fo.run.root.name == CAM and fo.opening(juliet) is None
    assert fo.takes(crawl_look(juliet, "unknown screen", "unknown"))
    fo.settle(SimpleNamespace(press=lambda key: None))
    assert not restore_pending(camera.runs)
    assert open_looks(CAM, juliet) == [("not_reached", first_open.PENDING, None),
                                       ("looked", "first open checked", None), ("kit_failed", None, "unknown")]
    assert first_open.seen_record(CAM).seen(juliet)
    assert row(ledger(), *juliet)["status"] == "kit cannot read"


def test_kit_newer_cannot_tell_on_a_changed_tree(monkeypatch):
    """An uncommitted change under kit/ may mend the failure: kit_newer says it cannot tell (None: tried again), and a
    look made on a changed tree names its commit "+dirty"."""
    calls = {"status": "", "head": "0123456789abcdef0123456789abcdef01234567"}

    def git(*args):
        if "status" in args:
            return calls["status"]
        if args[0] == "rev-parse" and args[-1] == "HEAD":
            return calls["head"] if "--short=7" not in args else calls["head"][:7]
        if args[0] == "rev-parse":
            return calls["head"] if args[1] == "0123456^{commit}" else None
        return None
    monkeypatch.setattr(coverage, "_git", git)
    assert coverage.kit_newer("0123456") is False
    calls["status"] = " M kit/camkit/crawl.py"
    assert coverage.kit_newer("0123456") is None
    monkeypatch.setattr(coverage, "_COMMIT", {})
    assert coverage.kit_commit() == "0123456+dirty"
    calls["status"] = ""
    assert coverage.kit_newer("0123456+dirty") is None


def test_no_proof_possible_needs_every_setting_known(camera):
    """A row with one setting no proof can reach and one never proved is still to prove, never settled."""
    led = ledger()
    e = row(led, "Hotel")
    led.src.definition["settings"].append(setting("global:0x0109", "Hotel two", ["Hotel", "Two"], ONOFF))
    by_key = {s["key"]: s for s in led.src.definition["settings"]}
    e["settings"].append("global:0x0109")
    coverage._one_row(e, {}, by_key, {}, set(), {})
    assert e["status"] == "not yet tried"
    assert not coverage.decide(led, e).skip


# ---------------------------------------------------------------- shared lists: one picker's slots, one table of codes

@contextlib.contextmanager
def extra_settings(camera, *settings, evidence=None):
    """The made-up camera with more settings (and, given, more of the private evidence of its definition: {key:
    {field}}, beside BASE_EVIDENCE), put back as it was after."""
    SETTINGS.extend(settings)
    ev = camera.defn.with_name(camera.defn.stem + ".evidence.json")
    try:
        camera.doc["settings"] = SETTINGS
        camera.defn.write_text(json.dumps(camera.doc), encoding="utf-8")
        ev.write_text(json.dumps({"settings": {**BASE_EVIDENCE, **(evidence or {})}}), encoding="utf-8")
        yield
    finally:
        del SETTINGS[len(SETTINGS) - len(settings):]
        ev.write_text(json.dumps({"settings": BASE_EVIDENCE}), encoding="utf-8")


def pick_proof(key, before, after, *reads, label=None, path=("November",)):
    """A picker proof line on November's row: the slot `key` from `before` to `after`, read as `reads` (the OCR
    reading under the cursor, then the reader's)."""
    out = {"path": list(path), "kind": "table", "opens": "picker", "label": label or reads[0],
           "changes": [{"key": key, "before": before, "after": after}]}
    out.update(dict(zip(("shown", "vlm"), reads, strict=False)))       # one reading or two
    return out


SLOTS = (setting("global:0x0122", "November slot 3", ["November"], PICK, tab="Setup", group="G2",
                 proved={"sampled": {"linear": None}}),
         setting("global:0x0124", "November slot 4", ["November"], PICK, tab="Setup", group="G2",
                 proved={"sampled": {"linear": None}}),
         setting("global:0x0125", "November slot 1 (movie)", ["November"], PICK, tab="Setup", group="G2",
                 copy_of="global:0x0120", proved={"values": [10]}),
         setting("global:0x0126", "November readout", ["November"], PICK, tab="Setup", group="G2", scalar=False,
                 proved={"values": [10]}),
         setting("global:0x0127", "November short", ["November"], PICK[:2], tab="Setup", group="G2",
                 proved={"values": [10, 11]}),
         setting("global:0x0128", "Oscar", ["Oscar"], PICK, tab="Setup", group="G2", proved={"values": [10, 11]}),
         setting("global:0x0129", "Papa 1", ["Papa"], ((0, "X"), (1, "Y"), (2, "Z")), tab="Setup", group="G2",
                 proved={"values": [0, 1]}),
         setting("global:0x012a", "Papa 2", ["Papa"], ((0, "X"), (1, "Y"), (2, "Z")), tab="Setup", group="G2"))
SLOT_PROOFS = [pick_proof("global:0x0122", 10, 12, "Cat", "Cat"),           # slot 3: its own two values, as the list
               pick_proof("global:0x0122", 10, 14, "• Elk", "Elk"),
               pick_proof("global:0x0124", 12, 10, "Ant"),                  # slot 4: one value of its own
               pick_proof("global:0x0124", 12, 11, "Dog", "Dog")]           # ... and 11 read twice as Dog (13)


def test_a_shared_list_is_one_rows_settings_listing_the_same_values(camera):
    """The settings placed on one row that list the same values under the same names, two at least, and neither a copy
    of another setting nor a readout: each with the values it is proved on, the proof lines that showed its own record
    agree with the list, and the proofs whose two independent readings name another value than the one written."""
    with extra_settings(camera, *SLOTS):
        write_proofs(camera, "kit2_pass2", SLOT_PROOFS)
        led = ledger()
        lists = {tuple(x["row"]["path"]): x for x in coverage.shared_lists(led)}
        assert set(lists) == {("November",), ("Papa",)}
        nov = lists[("November",)]
        assert nov["keys"] == ["global:0x0120", "global:0x0121", "global:0x0122", "global:0x0124"]
        assert nov["proved"][12] == ["global:0x0120"] and nov["proved"][10] == ["global:0x0120", "global:0x0121"]
        assert nov["own"]["global:0x0121"]["proved"] == [10, 11]
        assert [(c["run"], c["proof"]) for c in nov["own"]["global:0x0122"]["proofs"]] == [("kit2_pass2", 1),
                                                                                          ("kit2_pass2", 2)]
        assert [c["proof"] for c in nov["own"]["global:0x0124"]["proofs"]] == [3]
        assert [(c["key"], c["proof"], c["wrote"], c["reads_as"]) for c in nov["contradictions"]] == \
            [("global:0x0124", 4, 11, 13)]
        assert nov["never_proved"] == [] and nov["no_own"] == []
        papa = lists[("Papa",)]
        assert papa["never_proved"] == [2] and papa["no_own"] == ["global:0x012a"]
        lines = coverage.shared_view(led)
        assert any("November" in x and "4 settings" in x and "contradictions: 1" in x for x in lines)
        assert any("Papa" in x and "Z (2)" in x for x in lines)                      # never proved on any setting
        assert any("global:0x012a" in x for x in lines)                              # no value of its own shown
        # the public sources alone: the definition's proofs, no proof line
        pub = {tuple(x["row"]["path"]): x for x in coverage.shared_lists(ledger(public=True))}
        assert pub[("November",)]["own"]["global:0x0122"]["proofs"] == [] and not pub[("November",)]["contradictions"]


def test_a_reading_agrees_by_the_lists_names_or_a_reading_of_the_same_value(camera):
    """A slot's own proof agrees with the list when a reading names the value it wrote, as any setting of the row
    names it, or reads as another slot's proof of that value read (an icon OCR reads alike on both); a proof that changed
    two slots counts for the one it agrees with and contradicts nothing; one reading naming another value, or two that
    are one reader, contradict nothing."""
    proofs = [pick_proof("global:0x0120", 11, 12, "Ca7 icon", "Cat"),
              pick_proof("global:0x0122", 10, 12, "Ca7 icon"),
              {**pick_proof("global:0x0122", 10, 13, "Dog", "Dog"),
               "changes": [{"key": "global:0x0122", "before": 10, "after": 13},
                           {"key": "global:0x0124", "before": 10, "after": 11}]},
              pick_proof("global:0x0124", 10, 14, "Ant", "Elk"),
              {**pick_proof("global:0x0124", 10, 12, "Ant"), "votes": [{"source": "ocr:one", "text": "Ant"}]}]
    with extra_settings(camera, *SLOTS):
        write_proofs(camera, "kit2_pass2", proofs)
        nov = next(x for x in coverage.shared_lists(ledger()) if x["row"]["path"] == ["November"])
        assert [c["proof"] for c in nov["own"]["global:0x0122"]["proofs"]] == [2, 3]
        assert [c["proof"] for c in nov["own"]["global:0x0124"]["proofs"]] == [4]
        assert nov["contradictions"] == []


ARRAY = (setting("global:0x0130[0]", "Quebec", ["Quebec", "One", "Mode"], PICK, tab="Setup", group="G2", index=0,
                 proved={"values": [10, 11, 12]}),
         setting("global:0x0130[1]", "Quebec", ["Quebec", "Two", "Mode"], PICK, tab="Setup", group="G2", index=1,
                 proved={"values": [13, 14]}),
         setting("global:0x0130[2]", "Quebec", None, PICK[:4], tab="Setup", group="G2", index=2,
                 unproved_reason={"kind": "not_on_camera", "why": "No such profile on this body."}),
         setting("global:0x0131[0]", "Quebec (stills)", ["Quebec", "One", "Mode"], PICK, tab="Setup", group="G2",
                 index=0, copy_of="global:0x0130[0]", proved={"values": [10, 11, 12]}),
         setting("global:0x0131[1]", "Quebec (stills)", ["Quebec", "Two", "Mode"], PICK, tab="Setup", group="G2",
                 index=1, copy_of="global:0x0130[1]", proved={"values": [13, 14]}),
         setting("global:0x0132[0]", "Quebec (movie)", ["Quebec", "One", "Mode"], PICK, tab="Setup", group="G2",
                 index=0, copy_of="global:0x0130[0]", scalar=False, proved={"values": [10, 11, 12]}),
         setting("global:0x0132[1]", "Quebec (movie)", ["Quebec", "Two", "Mode"], PICK, tab="Setup", group="G2",
                 index=1, copy_of="global:0x0130[1]", scalar=False, proved={"values": [13, 14]}))


def test_an_array_records_elements_listing_the_same_values_are_one_list(camera):
    """A profile's parameter, one element a profile on a row of its own: the elements that list the same values are one
    list, a copy array's elements one of their own (never joined to the setting they copy), a copy the camera writes
    with another setting (scalar false) none."""
    with extra_settings(camera, *ARRAY):
        lists = {tuple(x["keys"]): x for x in coverage.shared_lists(ledger())}
        assert ("global:0x0130[0]", "global:0x0130[1]") in lists
        assert ("global:0x0131[0]", "global:0x0131[1]") in lists
        assert not any(k.startswith("global:0x0132") for ks in lists for k in ks)
        q = lists[("global:0x0130[0]", "global:0x0130[1]")]
        assert len(q["rows"]) == 2 and q["proved"][14] == ["global:0x0130[1]"] and q["never_proved"] == []


INFERRED = "inferred from a shared list"


def writers(settings, names: dict, sampled: dict = None) -> tuple:
    """(the settings with their proofs as the writer leaves them public, their evidence): for each key in `names`, its
    whole proof the values chosen on it (those named by a reading) and the values a rule named from another setting
    ("derived"), or a count of samples (`sampled`, a from_start one where given), its public proof that proof's lean
    form (definitions.lean_proof: the mark where a value is inferred)."""
    out, evidence = [], {}
    for s in settings:
        got = names.get(s["key"])
        if got is None:
            out.append(s)
            continue
        whole = {"run": "kit2_pass2", "names": {str(v): src for v, src in got.items()}}
        if s["key"] in (sampled or {}):
            whole["sampled"] = sampled[s["key"]]
        else:
            whole["values"] = sorted(v for v, src in got.items() if src != "derived")
        evidence[s["key"]] = {"proved": whole}
        out.append({**s, "proved": definitions.lean_proof(whole)})
    return out, evidence


def test_a_value_the_writer_named_from_another_setting_is_inferred_privately(camera):
    """November slot 2, as the writer leaves it (10 and 11 chosen on it, 12 to 14 named from slot 1's proof): the
    private form, which reads the whole proof, counts those three inferred, settled, never proved, and names the
    setting of its shared list each was proved on and the slot's own grounds; the public form, which has the marked
    lean proof alone, says of all five "proved or named from a shared list", none still to try, none inferred."""
    led = ledger()
    assert coverage.settled(["November"], camera=CAM, ledger=led).skip
    assert coverage.settled(["November"], "Cat", camera=CAM, ledger=led).skip
    priv = {o["key"]: o for o in coverage.private_doc(led)["options"]}["global:0x0121"]
    assert priv["statuses"] == {"proved": [10, 11], INFERRED: [12, 13, 14]}
    assert priv["cites"]["12"] == [{"proved_on": "global:0x0120"}]
    assert priv["shared_list"] == {"with": ["global:0x0120"], "own_proved": 2, "own_proofs": []}
    assert ("November",) not in [tuple(x["entry"]["path"]) for x in coverage.todo(led)]
    assert any("values_inferred: 3" in x for x in coverage.row_view(led, "November"))
    pub = coverage.public_doc(led)
    assert {o["key"]: o for o in pub["options"]}["global:0x0121"]["statuses"] == {
        coverage.PROVED_OR_SHARED: [10, 11, 12, 13, 14]}
    assert "values_left" not in {tuple(r["path"]): r for r in pub["rows"]}[("November",)]
    assert f'"{INFERRED}"' not in coverage.text(pub) and not coverage.public_problems(pub, camera=CAM)
    assert coverage.public_problems(json.loads(coverage.text(pub).replace(f'"{coverage.PROVED_OR_SHARED}": [10',
                                                                          f'"{INFERRED}": [10')), camera=CAM)


def test_the_ledger_infers_nothing_by_its_own_rule(camera, monkeypatch, capsys):
    """The ledger reads the writer's inference and makes none of its own (docs/decisions/0025): slot 3 (sampled from
    the option it held) and slot 4, each with the values the writer named from slot 1, are inferred there, slot 4 too,
    though a proof line of its own reads a value as another than it wrote, which kit/tools/coverage.py --shared says
    (slot 3's own two lines bear the list out, so of it nothing is said); a copy, a readout, a setting alone in its list
    and one with no value of its own, which the writer named nothing on, infer nothing."""
    import coverage as tool
    picker = {"proofs": 2, "linear": None, "from_start": True}
    slots, evidence = writers(SLOTS, {"global:0x0122": {10: "derived", 12: "derived", 14: "derived"},
                                      "global:0x0124": {v: "derived" for v, _ in PICK}},
                              {"global:0x0122": picker, "global:0x0124": picker})
    with extra_settings(camera, *slots, evidence=evidence):
        write_proofs(camera, "kit2_pass2", SLOT_PROOFS)
        led = ledger()
        vals = {o["key"]: o["values"] for o in led.options}
        nyt = "not yet tried"
        assert vals["global:0x0122"] == {10: INFERRED, 11: nyt, 12: INFERRED, 13: nyt, 14: INFERRED}
        assert vals["global:0x0124"] == {v: INFERRED for v, _ in PICK}
        assert vals["global:0x0121"] == {10: "proved", 11: "proved", 12: INFERRED, 13: INFERRED, 14: INFERRED}
        assert vals["global:0x0125"] == {10: "proved", 11: nyt, 12: nyt, 13: nyt, 14: nyt}     # a copy
        assert vals["global:0x0126"] == {10: "proved", 11: nyt, 12: nyt, 13: nyt, 14: nyt}     # a readout
        assert vals["global:0x0128"] == {10: "proved", 11: "proved", 12: nyt, 13: nyt, 14: nyt}  # alone on its row
        assert vals["global:0x0129"][2] == nyt and set(vals["global:0x012a"].values()) == {nyt}
        priv = {o["key"]: o for o in coverage.private_doc(led)["options"]}
        assert priv["global:0x0122"]["shared_list"]["own_proofs"] == [{"proof": 1, "run": "kit2_pass2"},
                                                                      {"proof": 2, "run": "kit2_pass2"}]
        lines = coverage.shared_view(led)
        assert any("global:0x0124" in x and "not borne out" in x and "reads a value as another" in x for x in lines)
        assert not any("global:0x0122" in x and "not borne out" in x for x in lines)
        nov = row(led, "November")
        assert nov["values_inferred"] == 11 and nov["values_left"] == 10
        coverage.forget()
        monkeypatch.setattr(sys, "argv", ["coverage.py", "--todo"])
        tool.main()
        assert "November: sampled; 11 values inferred from a shared list; 10 values still to try" in \
            capsys.readouterr().out


def test_a_greyed_value_is_inferred_from_another_element_and_keeps_why(camera):
    """A profile's value the camera greys in a state (refused with a notice naming the row that greys it), which the
    writer named from another element of its array that is proved on it, is inferred, the notice still cited after
    that element; a copy the camera writes with another setting (scalar false), on which the writer named nothing,
    keeps it greyed, so that option is no settled one."""
    refused = {"path": ["Quebec", "Two", "Mode"], "kind": "list", "label": "Ant", "applied": False,
               "notice": {"text": "This function is not available as follows: Bravo"}, "changes": []}
    array, evidence = writers(ARRAY, {
        "global:0x0130[1]": {10: "derived", 11: "derived", 12: "derived", 13: "two readers", 14: "two readers"},
        "global:0x0130[0]": {10: "two readers", 11: "two readers", 12: "two readers", 13: "derived", 14: "derived"},
        "global:0x0131[1]": {10: "derived", 11: "derived", 12: "derived", 13: "two readers", 14: "two readers"}})
    with extra_settings(camera, *array, evidence=evidence):
        write_proofs(camera, "kit2_pass2", [refused])
        led = ledger()
        vals = {o["key"]: o["values"] for o in led.options}
        assert vals["global:0x0130[1]"] == {10: INFERRED, 11: INFERRED, 12: INFERRED, 13: "proved", 14: "proved"}
        assert vals["global:0x0130[0]"][13] == INFERRED and vals["global:0x0131[1]"][10] == INFERRED
        assert vals["global:0x0132[1]"][10] == "greyed in state"
        cites = {o["key"]: o for o in led.options}["global:0x0130[1]"]["cites"][10]
        assert cites[0] == {"proved_on": "global:0x0130[0]"} and cites[1]["blocker"] == {"row": "Bravo"}
        assert not coverage.settled(["Quebec", "Two", "Mode"], "Ant", camera=CAM, ledger=led).skip


def test_a_row_a_proof_went_through_takes_the_setting_it_proved(camera):
    """The camera draws one setting under more than one page (a subject's own page and the Auto page): a row with no
    setting of its own that a proof of a setting placed elsewhere went through (the private evidence's proved.menu) takes
    that setting, as the rows above it that hold none do, so it is proved as the setting is, and its proofs are the
    row's own; a row that holds a setting of its own, or that no proof went through, keeps what it had; the public
    build, which has neither the evidence nor the looks, has no such row."""
    leaf = setting("global:0x0140", "Romeo leaf", ["Romeo", "Own", "Leaf"], ONOFF, tab="Setup", group="G2",
                   proved={"values": [0, 1]})
    busy = setting("global:0x0141", "Romeo busy", ["Romeo", "Busy", "Leaf"], ONOFF, tab="Setup", group="G2")
    menus = ["Romeo > Own > Leaf", "Romeo > Auto > Own > Leaf", "Romeo > Sister > Leaf [Movie mode]",
             "Romeo > Busy > Leaf"]
    evidence = {"global:0x0140": {"proved": {"values": [0, 1], "menu": menus, "run": "kit2_pass2"}}}
    through = {"path": ["Romeo", "Auto", "Own", "Leaf"], "kind": "list", "index": 1, "label": "On", "shown": "On",
               "vlm": "On", "changes": [{"key": "global:0x0140", "before": 0, "after": 1}]}
    with extra_settings(camera, leaf, busy, evidence=evidence):
        add_looks(camera, *(look(p, result="looked", by="crawl") for p in (
            ["Romeo", "Auto", "Own", "Leaf"], ["Romeo", "Sister", "Leaf"], ["Romeo", "Other"])))
        write_proofs(camera, "kit2_pass2", [through])
        led = ledger(validity=True)
        for path in (("Romeo", "Auto", "Own", "Leaf"), ("Romeo", "Auto", "Own"), ("Romeo", "Auto"),
                     ("Romeo", "Sister", "Leaf"), ("Romeo", "Sister")):
            e = row(led, *path)
            assert e["status"] == "proved" and e["through"] == ["global:0x0140"], path
        assert row(led, "Romeo", "Other")["status"] == "not yet tried"
        assert row(led, "Romeo", "Busy", "Leaf")["status"] == "not yet tried"
        assert row(led, "Romeo", "Busy", "Leaf")["through"] == []
        check = next(c for c in led.proof_checks if c["path"] == ["Romeo", "Auto", "Own", "Leaf"])
        assert check["a"] and check["b"]                                # the row's own record, two readings
        priv = {tuple(r["path"]): r for r in coverage.private_doc(led)["rows"]}
        assert priv[("Romeo", "Auto", "Own", "Leaf")]["through"] == ["global:0x0140"]
        assert not any(r["path"][:2] == ["Romeo", "Auto"] for r in coverage.public_doc(led)["rows"])


def test_the_tool_prints_the_shared_lists(camera, monkeypatch, capsys):
    import coverage as tool
    monkeypatch.setattr(sys, "argv", ["coverage.py", "--shared"])
    tool.main()
    out = capsys.readouterr().out
    assert "1 shared list" in out and "November" in out and "2 settings" in out


# ---------------------------------------------------------------- 8: a valid proof

def test_the_proofs_validity_repeats_and_bundles(camera):
    p2 = write_proofs(camera, "kit2_pass2", [])
    (p2 / "dat").mkdir()
    (p2 / "shots").mkdir()
    for n in ("00001_base.DAT", "00002_on.DAT", "00004_on.DAT"):
        (p2 / "dat" / n).write_bytes(b"x" * 10)
    for n in ("00002_c.png", "00003_r.png", "00009_other.png"):
        (p2 / "shots" / n).write_bytes(b"y" * 5)
    ch = [{"key": "global:0x0100", "before": 0, "after": 1}]
    proofs = [
        {"path": ["Alpha"], "kind": "list", "index": 1, "label": "On", "shown": "On", "vlm": "On", "changes": ch,
         "attempt": "A", "base": "00001_base.DAT", "dat": "00002_on.DAT", "chosen_frame": "00002_c.png",
         "row_frame": "00003_r.png"},
        {"path": ["Alpha"], "kind": "list", "index": 0, "label": "Off", "shown": "Off", "vlm": "Off", "changes": [],
         "attempt": "A"},
        {"path": ["Alpha"], "kind": "list", "index": 1, "label": "On", "shown": "On", "vlm": "On", "changes": ch,
         "attempt": "B", "dat": "00004_on.DAT"},
        {"path": ["Charlie"], "kind": "sidelist", "index": 0, "label": "10", "shown": "10", "changes": [
            {"key": "global:0x0102", "before": 0, "after": 10}]},
        {"path": ["Foxtrot"], "kind": "list", "index": 0, "label": "Off", "shown": "Off", "vlm": "Off",
         "changes": [{"key": "global:0x0103", "before": 1, "after": 0}, {"key": "global:0x0201", "before": 0,
                                                                         "after": 1}]},
    ]
    write_proofs(camera, "kit2_pass2", proofs, attempts=["A"])
    (camera.runs / "downloads.jsonl").write_text(json.dumps({"path": "kit2_pass2/dat/00002_on.DAT",
                                                             "sha256": SHA}) + "\n", encoding="utf-8")
    led = ledger(validity=True)
    s = led.proof_summary
    assert s["proofs"] == 5 and s["valid"] == 2 and s["inferred"] == 1 and s["repeats_of_a_valid_proof"] == 1
    assert s["one_reading"] == 1 and s["missing"] == {"b": 1, "a": 1}
    checks = {(tuple(c["path"]), c["line"]): c for c in led.proof_checks}
    assert checks[(("Alpha",), 2)]["state"] == "inferred" and not checks[(("Alpha",), 2)]["valid"]
    assert checks[(("Charlie",), 4)]["missing"] == ["b"] and checks[(("Charlie",), 4)]["one_reading"]
    assert checks[(("Foxtrot",), 5)]["missing"] == ["a"]           # a record beyond the row's own
    bundle = next(b for b in led.bundles if b["path"] == ["Alpha"] and b["option"] == "On")
    assert bundle["run"] == "kit2_pass2" and bundle["line"] == 1 and bundle["after"]["sha256"] == SHA
    assert bundle["frames"] == ["00002_c.png", "00003_r.png"]
    assert row(led, "Alpha")["proofs"]["repeats"] == 1 and row(led, "Alpha")["proofs"]["inferred"] == 1
    assert led.option_validity[("global:0x0100", 1)] == "valid"
    assert led.option_validity[("global:0x0100", 0)].startswith("inferred")
    assert led.option_validity[("global:0x0102", 10)] == "unchecked (b)"
    priv = {o["key"]: o for o in coverage.private_doc(led)["options"]}
    assert priv["global:0x0100"]["validity"]["1"] == "valid"
    pub = coverage.public_doc(led)
    assert "validity" not in json.dumps(pub)
    assert "bundles" not in pub and not coverage.public_problems(pub, camera=CAM)
    assert coverage.private_doc(led)["bundles"]
    rep = {r["run"]: r for r in coverage.bundles_report(led)}["kit2_pass2"]
    assert rep["frames"] == [2, 1, 10, 5] and rep["downloads"] == [2, 1, 20, 10]
    assert len(list((p2 / "shots").iterdir())) == 3                 # nothing deleted
    # c: two options of one row writing the same value into its own record; a side effect elsewhere makes them no
    # different
    proofs[4] = dict(proofs[4], changes=[{"key": "global:0x0103", "before": 1, "after": 0}])
    proofs.append(dict(proofs[4], index=1, label="On", shown="On", vlm="On",
                       changes=[{"key": "global:0x0103", "before": 1, "after": 0},
                                {"key": "global:0x0201", "before": 0, "after": 7}]))
    write_proofs(camera, "kit2_pass2", proofs, attempts=["A"])
    led = ledger(validity=True)
    assert all("c" in c["missing"] for c in led.proof_checks if c["path"] == ["Foxtrot"])


def test_a_fields_last_proof_puts_its_start_value_back_and_tests_nothing(camera):
    """A two-field row (ISO Range Limit's lower and upper fields) is proved field by field, each field's start value
    chosen last to put it back, which changes nothing by design and carries no attempt: it is that field's closing
    proof, so its value is "tested, no record changes" on no record of the row; a value the camera kept mid-field
    (no change, not the field's last line) still is."""
    iso = ((2, "ISO 50"), (3, "ISO 64"), (4, "ISO 80"))
    low = setting("global:0x0150", "Sierra (lower)", ["Sierra"], iso, tab="Setup", group="G2")
    high = setting("global:0x0151", "Sierra (upper)", ["Sierra"], iso, tab="Setup", group="G2")

    def field(k, t, label, key=None, before=None, after=None):
        return {"path": ["Sierra"], "kind": "fields", "index": [k, t], "label": label, "value": label, "shown": label,
                "vlm": label, "applied": True,
                "changes": [{"key": key, "before": before, "after": after}] if key else []}
    proofs = [field(0, 1, "ISO 64", "global:0x0150", 2, 3), field(0, 2, "ISO 80"), field(0, 0, "ISO 50"),
              field(1, 0, "ISO 50", "global:0x0151", 4, 2), field(1, 1, "ISO 64", "global:0x0151", 4, 3),
              field(1, 2, "ISO 80")]
    with extra_settings(camera, low, high):
        write_proofs(camera, "kit2_pass2", proofs)
        led = ledger(validity=True)
        vals = {o["key"]: o["values"] for o in led.options}
        assert vals["global:0x0150"][2] == "not yet tried" and vals["global:0x0151"][2] == "not yet tried"
        assert vals["global:0x0150"][4] == "tested, no record changes"           # line 2: kept mid-field
        states = {c["line"]: c["state"] for c in led.proof_checks if c["path"] == ["Sierra"]}
        assert states[3] == "inferred" and states[6] == "inferred" and states[2] != "inferred"


def test_two_readings_agree_only_whole_and_only_when_independent():
    """"On" is not "Continuous", "ISO 100" not "ISO 1000", "1/250" not "1/2500"; pass 1's map label is no reading;
    the OCR reading beside an OCR engine's vote is not two readings, two engines' votes are."""
    for a, b in (("On", "Continuous"), ("ISO 100", "ISO 1000"), ("1/250", "1/2500")):
        assert coverage.readings_agree({"shown": a, "vlm": b, "label": a}) == (2, False), (a, b)
    assert coverage.readings_agree({"shown": "Off", "label": "Off"}) == (1, False)
    assert coverage.readings_agree({"shown": "Hi+", "vlm": "Hi+"}) == (2, True)
    assert not coverage.readings_agree({"shown": "On", "votes": [{"source": "ocr:apple", "text": "On"}]})[1]
    assert coverage.readings_agree({"votes": [{"source": "ocr:apple", "text": "On"},
                                              {"source": "ocr:rapidocr", "text": "On"}]})[1]


# ---------------------------------------------------------------- what is left, the public sources, the tool

def test_a_look_counts_only_the_records_no_setting_maps(camera):
    """"A look saw N records change" names the records no setting covers (a lead to map), never one a setting already
    maps, its memory sets' copy included: a settled row whose look changed only mapped records leaves the to-do list."""
    add_looks(camera, look(["Alpha"], result="changed", records_changed=["global:0x0100", "set2:0x0100", "global:0x0200"]),
              look(["Bravo"], result="changed", records_changed=["global:0x0101"]))
    led = ledger()
    assert row(led, "Alpha")["changed_in_looks"] == ["global:0x0200"]
    assert "changed_in_looks" not in row(led, "Bravo") and "cites_changed" not in row(led, "Bravo")
    left = [tuple(x["entry"]["path"]) for x in coverage.todo(led)]
    assert ("Alpha",) in left and ("Bravo",) not in left


def test_a_record_a_look_saw_change_stays_seen_when_a_later_look_of_the_row_takes_its_place(camera, monkeypatch):
    """The latest look of a row, did and option gives the row its status, but what an earlier one saw change stays
    seen: the a1 II's Bracket Type looks, all with no option, the last changing 0x13f9 alone, hid the two that changed
    0x13f3 and 0x13f5, which stayed "never seen to change" (2026-11-19). A retraction still withdraws them."""
    rec = "global:0x0201"
    assert {r["key"]: r for r in ledger().records}[rec]["status"] == "unmapped, never seen to change"
    add_looks(camera, look(["Kilo"], did="choose", result="changed", records_changed=[rec]),
              look(["Kilo"], did="choose", result="changed", records_changed=["global:0x0200"]),
              look(["Kilo"], did="choose", result="no_change"))
    led = ledger()
    assert {r["key"]: r for r in led.records}[rec]["status"] == "changed, no row attributed"
    assert row(led, "Kilo")["changed_in_looks"] == ["global:0x0200", rec]
    assert row(led, "Kilo")["status"] == "tested, no record changes", "the latest look gives the row its status"
    import coverage as tool
    monkeypatch.setattr(sys, "argv", ["coverage.py", "--record", "--path", "Shooting > G1 > Kilo", "--did", "choose",
                                      "--result", "retract"])
    tool.main()
    led = ledger()
    assert {r["key"]: r for r in led.records}[rec]["status"] == "unmapped, never seen to change"
    assert "changed_in_looks" not in row(led, "Kilo")


def test_todo_counts_each_value_once_on_the_row_that_holds_its_setting(camera, monkeypatch, capsys):
    """A value still to try is listed on the row its setting is placed on, never again on each row above it (a
    profile's parameter under Picture Profile > PPn); those rows stay unsettled while a value below them is left, so a
    run given --skip-settled still goes down to it."""
    import coverage as tool
    leaf = setting("global:0x0160", "Tango leaf", ["Tango", "Sub", "Leaf"], ((0, "A"), (1, "B"), (2, "C")),
                   tab="Setup", group="G2", proved={"values": [0]})
    other = setting("global:0x0161", "Tango other", ["Tango", "Other"], ONOFF, tab="Setup", group="G2",
                    proved={"values": [0, 1]})
    with extra_settings(camera, leaf, other):
        led = ledger()
        items = {tuple(x["entry"]["path"]): x for x in coverage.todo(led)}
        assert ("Tango", "Sub", "Leaf") in items and items[("Tango", "Sub", "Leaf")]["left"] == 2
        assert ("Tango",) not in items and ("Tango", "Sub") not in items
        assert not coverage.settled(["Tango"], camera=CAM, ledger=led).skip
        assert not coverage.settled(["Tango", "Sub"], camera=CAM, ledger=led).skip
        assert row(led, "Tango")["values_left"] == 2                    # the subtree's, as the forms say
        coverage.forget()
        monkeypatch.setattr(sys, "argv", ["coverage.py", "--todo"])
        tool.main()
        out = capsys.readouterr().out
        assert "Tango > Sub > Leaf: proved; 2 values still to try" in out and "> Tango: " not in out


def test_a_withheld_label_named_by_a_sibling_crawl_is_no_row(camera):
    """A look lap keeps no label it does not know (decision 24: "(withheld)"), so a placeholder is no row the kit knows:
    where every position a placeholder stands at under its row is named in another crawl of that row (a submenu of the
    same length with a known label there), the ledger makes no row of it, nor of a look written under it; a placeholder
    no crawl names stays a row of its own, visible."""
    rows = {"kit2_look": [{"label": "Uniform", "outcome": "submenu", "submenu": [
                              {"label": "(withheld)", "outcome": "notice"}, {"label": "Two", "outcome": "ok"}]},
                          {"label": "Victor", "outcome": "submenu", "submenu": [{"label": "(withheld)"},
                                                                                {"label": "(withheld)"}]}],
            "kit2_named": [{"label": "Uniform", "outcome": "submenu", "submenu": [{"label": "One"}, {"label": "Two"}]},
                           {"label": "Victor", "outcome": "submenu", "submenu": [{"label": "A"}]}]}
    with extra_settings(camera, setting("global:0x0170", "Uniform", ["Uniform"], ONOFF, tab="Setup", group="G2"),
                        setting("global:0x0171", "Victor", ["Victor"], ONOFF, tab="Setup", group="G2")):
        for run, rs in rows.items():
            (camera.runs / run).mkdir()
            (camera.runs / run / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rs), encoding="utf-8")
        add_looks(camera, look(["Uniform", "(withheld)"], result="looked", by="crawl"),
                  look(["Victor", "(withheld)"], result="looked", by="crawl"))
        led = ledger()
        paths_ = {tuple(e["path"]) for e in led.rows}
        assert ("Uniform", "(withheld)") not in paths_ and ("Uniform", "One") in paths_
        assert ("Victor", "(withheld)") in paths_
        assert not any(u.get("path") == ["Uniform", "(withheld)"] for u in led.unresolved)


def test_a_row_under_a_row_the_makers_list_excludes_is_not_in_the_file_either(camera):
    """Sony's Save/Load list names a row (Delta, "its own file"; Kilo > Inner): each row below it takes "not in the
    settings file (Sony)" with the list's note, whatever a look found there (greyed, the kit failing), and so do the
    values of a setting placed below it; a row proved stays proved."""
    cam = json.loads((camera.data / f"camera_{CAM}.json").read_text(encoding="utf-8"))
    cam["save_load_excluded"]["rows"].append({"row": "Kilo > Inner"})
    (camera.data / f"camera_{CAM}.json").write_text(json.dumps(cam), encoding="utf-8")
    leaf = setting("global:0x0180", "Kilo leaf", ["Kilo", "Inner", "Leaf"], ONOFF)
    with extra_settings(camera, leaf):
        add_looks(camera, look(["Delta", "Inner"], result="greyed", screen="notice", blocker={"row": "Alpha"}),
                  look(["Delta", "Inner", "Deep"], result="kit_failed", kit_message="unknown screen"))
        led = ledger()
        sony = "not in the settings file (Sony)"
        for path in (("Delta", "Inner"), ("Delta", "Inner", "Deep"), ("Kilo", "Inner", "Leaf")):
            assert row(led, *path)["status"] == sony, path
        assert row(led, "Delta", "Inner")["sony_note"] == "its own file"
        assert row(led, "Kilo")["status"] != sony
        assert set({o["key"]: o for o in led.options}["global:0x0180"]["values"].values()) == {sony}


def test_todo_lists_what_is_left_by_need_and_yield(camera):
    led = ledger()
    items = coverage.todo(led)
    paths_left = [tuple(x["entry"]["path"]) for x in items]
    assert ("Kilo",) in paths_left and ("Alpha",) not in paths_left and ("Echo",) not in paths_left
    assert ("Charlie",) in paths_left                       # sampled, one value still to try
    assert {x["needs"] for x in items} <= set(coverage.NEEDS)
    assert [x["entry"]["path"] for x in coverage.todo(led, needs="kit")] == [["Juliet"]]
    # no option of IP Address Setting is ever chosen remotely, whatever a decision says: the owner's hand
    assert [x["entry"]["path"] for x in coverage.todo(led, needs="hand")] == [["IP Address Setting"]]
    assert all(x["entry"]["tab"] == "Setup" for x in coverage.todo(led, tab="Setup"))
    ys = [x["yield"] for x in items]
    assert ys == sorted(ys, reverse=True)
    lines = coverage.row_view(led, "Foxtrot")
    assert any("cites:" in x and "kit2_drive_x" in x for x in lines)
    assert not any("cites" in x for x in coverage.row_view(led, "Foxtrot", public=True))


def never_choose_entry(status, opener, looked=None, **kw) -> dict:
    """A made-up ledger entry as _one_row leaves a network row no remote run chooses in (safety.never_choose): its rule
    and opener from its never-open label, "never_choose", no settings, and "looked" (the private form's count of looks
    that opened it) when given."""
    e = {"path": ["Made-up Remote Row"], "status": status, "rule": "identity/by hand", "opener": list(opener),
         "never_choose": True, "settings": [], "tied": [], **kw}
    if looked:
        e["looked"] = looked
    return e


@pytest.mark.parametrize("status", ["not yet tried", "greyed in state"])
@pytest.mark.parametrize("opener", [["--network", "--owner"], ["--owner"]], ids=["look-lap", "owner-only"])
def test_a_never_choose_row_once_looked_at_needs_the_owners_hand_not_another_look(status, opener):
    """Remote Shoot Function, Manage Paired Device, Access Authen. Info, Wi-Fi Direct Settings and Pairing on the a1 II
    (2026-11-19): looked at as far as a look lap may go, several times, and no look lap chooses in them (decision 8): the
    to-do sends them to the owner's hand, never back to a look, whatever their status or blocker."""
    for e in (never_choose_entry(status, opener, looked=5),
              never_choose_entry(status, opener, looked=11, rule="credentials"),
              never_choose_entry(status, opener, looked=1, blocker={"row": "Some Row"})):
        assert coverage.needs_of(e) == "hand", e


@pytest.mark.parametrize("status", ["not yet tried", "greyed in state"])
def test_a_never_choose_row_nobody_looked_at_needs_a_look_where_a_look_lap_opens_it_else_the_owner(status):
    """Not yet looked at: a look first where a look lap may open it (its opener holds --network); where only the owner's
    own run opens it (--owner), nothing remote is left to do: the owner's hand."""
    assert coverage.needs_of(never_choose_entry(status, ["--network", "--owner"])) == "remote-look"
    assert coverage.needs_of(never_choose_entry(status, ["--owner"])) == "hand"
    assert coverage.needs_of(never_choose_entry(status, ["--network", "--owner"], looked=0)) == "remote-look"


def test_needs_of_is_as_before_for_rows_a_remote_run_may_choose_in_and_for_the_other_statuses():
    """Without never_choose, a looked-at row with no settings still needs a look, one with settings a proof, a greyed one
    a look unless its blocker is the owner's hand; a never-choose row a look saw change records still needs a proof (or
    the records named), and closed, equipment or kit rows answer as before."""
    plain = {k: v for k, v in never_choose_entry("not yet tried", ["--network", "--allow"], looked=8).items()
             if k != "never_choose"}
    assert coverage.needs_of(plain) == "remote-look"
    assert coverage.needs_of({**plain, "settings": ["global:0x0001"]}) == "remote-proof"
    assert coverage.needs_of({**plain, "status": "greyed in state", "blocker": {"row": "X"}}) == "remote-look"
    assert coverage.needs_of({**plain, "status": "greyed in state", "blocker": {"remote": True}}) == "hand"
    nc = never_choose_entry("not yet tried", ["--network", "--owner"], looked=3)
    assert coverage.needs_of({**nc, "changed_in_looks": ["global:0x0002"]}) == "remote-proof"
    assert coverage.needs_of({**nc, "status": "needs equipment"}) == "equipment"
    assert coverage.needs_of({**nc, "status": "kit cannot read"}) == "kit"
    assert coverage.needs_of({**nc, "status": "closed by rule"}) == "hand"
    assert coverage.needs_of({**plain, "status": "closed by rule", "opener": ["--owner"]}) == "decision"


def test_the_public_sources_alone_give_the_generated_statuses(camera):
    """Without the private overlay: no look, crawl or lead counts, the statuses that rest on them fall to the next."""
    led = ledger(public=True)
    assert row(led, "Echo")["status"] == "not yet tried" and row(led, "Juliet")["status"] == "not yet tried"
    assert row(led, "Delta")["status"] == "not in the settings file (Sony)" and not row(led, "Delta").get("confirmed")
    assert row(led, "Display Serial Number")["status"] == "information screen"     # before an action
    assert row(led, "Version")["status"] == "action, nothing to map"
    assert {r["status"] for r in led.records if r["key"].startswith("global:0x02")} == {"unmapped, not examined"}
    assert coverage.public_doc(led)["records"][-1]["status"] in coverage.PUBLIC_RECORD_NAMES


def test_a_blocker_is_a_row_label_before_any_equipment_word():
    labels = {"Flash Mode", "Release w/o Lens", "Red Eye Reduction", "Bluetooth Function"}
    assert coverage.blocker_of("This operation or setting is not available as follows Flash Mode Flash Off",
                               labels) == {"row": "Flash Mode"}
    assert coverage.blocker_of("Release w/o Lens Disable", labels) == {"row": "Release w/o Lens"}
    assert coverage.blocker_of("Attach a supported lens.", labels) == {"equipment": "a lens with a function ring"}
    assert coverage.blocker_of("Connected to Remote Shooting. Cannot be executed.", labels) == \
        {"remote": coverage.REMOTE}
    assert coverage.blocker_of("Something else", labels) is None


def test_the_tool_records_a_hand_check_from_two_camera_downloads(camera, monkeypatch, capsys):
    import coverage as tool
    from camkit import camset, provenance
    d = camera.runs / "kit2_hand" / "dat"
    d.mkdir(parents=True)
    for n in ("00001_before.DAT", "00002_after.DAT"):
        (d / n).write_bytes(n.encode())
    monkeypatch.setattr(provenance, "check", lambda p, root=None: {"path": str(p)})
    monkeypatch.setattr(camset, "read", lambda p: p.name)
    monkeypatch.setattr(camset, "diff", lambda a, b: [SimpleNamespace(key="global:0x0201", before=0, after=1)])
    monkeypatch.setattr(sys, "argv", ["coverage.py", "--record", "--path", "Shooting > G1 > Kilo", "--option", "On",
                                      "--start", str(d / "00001_before.DAT"), "--end", str(d / "00002_after.DAT")])
    os.chmod(camera.looks, 0o644)
    tool.main()
    last = json.loads(camera.looks.read_text(encoding="utf-8").splitlines()[-1])
    assert last["by"] == "hand" and last["tab"] == "Shooting" and last["path"] == ["Kilo"]
    assert last["records_changed"] == ["global:0x0201"] and last["result"] == "changed" and last["run"] == "kit2_hand"
    assert "global:0x0201" in capsys.readouterr().out
    if os.name != "nt":
        assert camera.looks.stat().st_mode & 0o777 == 0o600            # owner-only, as every private run's
    monkeypatch.setattr(provenance, "check", lambda p, root=None: (_ for _ in ()).throw(provenance.NotADownload("no")))
    with pytest.raises(SystemExit) as e:
        tool.main()
    assert "nothing recorded" in str(e.value)


def test_the_mappers_looks_file_where_present_holds_only_looks():
    """The a1 II's looks file in the mapper's private/evidence/ (definitions.EVIDENCE_DIR; the tests' own
    CAMSET_LOOKS_DIR aside), where this computer has it: every line one the schema holds, never a value."""
    import jsonschema
    p = definitions.EVIDENCE_DIR / A1 / f"looks_{A1}.jsonl"
    if not p.exists():
        pytest.skip("no looks file on this computer (the mapper's own)")
    schema = jsonschema.Draft202012Validator(json.loads((ROOT / "schemas" / "looks.schema.json").read_text(
        encoding="utf-8")))
    for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            entry = json.loads(line)
            assert not list(schema.iter_errors(entry)), f"line {n}"
            assert coverage.look_problems(entry) == [], f"line {n}"


def test_the_save_load_list_renders_for_the_model_page():
    import build_docs
    cam = json.loads(definitions.camera_file(A1).read_text(encoding="utf-8"))
    said = build_docs.save_load_md(cam)
    assert said.startswith("IPTC Information, Copyright Info, External Flash Set., custom white balances 1-3")
    assert "Remote Shoot Function's Connect without Pairing and Sync. Release Set." in said
    assert "FTP Transfer Func. (its own file)" in said and "\n" not in said
    assert build_docs.save_load_md({}) == ""
    page = (ROOT / "docs" / "models" / f"{A1}.md").read_text(encoding="utf-8")
    assert "{{ save_load_excluded() }}" in page
    doc = definitions.load_public(A1)
    assert "save_load_excluded" not in doc["camera"]           # the kit's alone: never copied into the definition


def test_settled_says_what_is_settled(camera, monkeypatch):
    led = ledger()
    v = coverage.settled(["Alpha"], camera=CAM, ledger=led)
    assert v.skip and v.reason.startswith("settled: Alpha: proved")
    v = coverage.settled(["Echo"], camera=CAM, ledger=led)
    assert v.skip and "information screen (2026-11-14 drive)" in v.reason
    assert not coverage.settled(["Kilo"], camera=CAM, ledger=led).skip
    v = coverage.settled(["IP Address Setting"], camera=CAM, ledger=led)
    assert not v.skip and "closed by rule" in v.reason and "--owner" in v.reason
    # an action or an information screen by its class alone: no look yet, so a run allowed to open it is not stopped
    for path in (["Setting Reset"], ["Display Wi-Fi Info."]):
        v = coverage.settled(path, camera=CAM, ledger=led)
        assert not v.skip and "by its class alone" in v.reason
    assert not coverage.settled(["Nowhere"], camera=CAM, ledger=led).skip
    # a greyed row: settled only while the start file greys it
    for got, skip in ((False, True), (True, False), (None, False)):
        monkeypatch.setattr(coverage, "ungreyed", lambda led, e, start, got=got: got)
        assert coverage.settled(["India"], camera=CAM, ledger=led).skip is skip
    # a row the kit could not read: settled only until a newer kit commit
    for newer, skip in ((False, True), (True, False), (None, False)):
        monkeypatch.setattr(coverage, "kit_newer", lambda than, newer=newer: newer)
        assert coverage.settled(["Juliet"], camera=CAM, ledger=led).skip is skip
    # an option: the least settled of the values its label names
    assert coverage.settled(["Alpha"], "Auto", camera=CAM, ledger=led).skip           # not offered
    assert not coverage.settled(["Foxtrot"], "Off", camera=CAM, ledger=led).skip      # not yet tried


def test_settled_never_settles_without_a_ledger_or_with_a_stale_one(camera):
    coverage.forget()
    lf = camera.looks
    saved = lf.read_text(encoding="utf-8")
    lf.unlink()
    v = coverage.settled(["Alpha"], camera=CAM)
    assert not v.skip and "no looks file yet" in v.reason and "nothing is settled" in v.reason
    lf.write_text(saved, encoding="utf-8")
    assert coverage.settled(["Alpha"], camera=CAM).skip
    v = coverage.settled(["Alpha"], camera="NONE-SUCH_fw1.00")
    assert not v.skip and "no definition" in v.reason
    led = coverage.ledger_for(CAM)
    for p in (camera.defn, camera.data / f"hand_tables_{CAM}.json", camera.data / f"camera_{CAM}.json"):
        led = coverage.ledger_for(CAM)
        st = p.stat()
        p.write_text(p.read_text(encoding="utf-8") + " ", encoding="utf-8")
        os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 10 ** 9))
        assert led.stale(), p.name
        v = coverage.settled(["Alpha"], camera=CAM, ledger=led)
        assert not v.skip and "stale" in v.reason
        assert not coverage.ledger_for(CAM).stale()          # built again


def test_a_greyed_row_with_a_rule_is_tried_once_the_start_file_ungreys_it(camera, monkeypatch, tmp_path):
    """inactive_when tells it: the record's value in the start file among those that grey the row, or not."""
    led = ledger()
    e = row(led, "India")
    led.src.definition["settings"].append(setting("global:0x0109", "India", ["India"], ONOFF,
                                                  inactive_when={"record": 0x0100, "name": "Alpha", "values": [0]}))
    e["settings"].append("global:0x0109")
    from camkit import camset

    class File:
        def __init__(self, v):
            self.v = v

        def get(self, section, rid):
            return SimpleNamespace(value=lambda: self.v) if rid == 0x0100 else None
    monkeypatch.setattr(camset, "read", lambda p: File(int(Path(p).name)))
    assert coverage.ungreyed(led, e, tmp_path / "0") is False
    assert coverage.ungreyed(led, e, tmp_path / "1") is True
    assert coverage.ungreyed(led, e, None) is None
    # no rule: the blocker's records in the start file against the file the look started from (by its SHA-256)
    e["settings"].remove("global:0x0109")
    looked_from = tmp_path / "looked-from"
    monkeypatch.setattr(coverage, "_download_by_sha", lambda src, sha: looked_from if sha == SHA else None)
    monkeypatch.setattr(coverage, "_record_raw", lambda p, key: b"\x00" if Path(p) == looked_from or
                        Path(p).name == "same" else b"\x01")
    assert coverage.ungreyed(led, e, tmp_path / "same") is False
    assert coverage.ungreyed(led, e, tmp_path / "other") is True
    e["cites"] = [dict(c, start_sha256=None) for c in e["cites"]]
    assert coverage.ungreyed(led, e, tmp_path / "other") is None


# ---------------------------------------------------------------- the second review's low items

def test_a_look_that_did_not_reach_the_row_never_erases_one_that_did(camera):
    """L2: a not_reached look (an unfinished run, a lost row) after Echo's information screen says nothing of the row:
    Echo stays an information screen; a not_reached look alone is kept as it is."""
    add_looks(camera, look(["Echo"], result="not_reached", kit_message="the run did not finish"))
    assert row(ledger(), "Echo")["status"] == "information screen"
    add_looks(camera, look(["Kilo"], did="choose", option="On", result="not_reached"))
    last, _laps = coverage._last_looks(coverage.read_looks(CAM))
    assert last[(("kilo",), "choose", "on")][1]["result"] == "not_reached"


def test_a_retraction_names_what_it_withdraws(camera, monkeypatch):
    """L3: --result retract must name --did, so it never withdraws a choice when an opening was meant."""
    import coverage as tool
    monkeypatch.setattr(sys, "argv", ["coverage.py", "--record", "--path", "Shooting > G1 > Echo", "--result",
                                      "retract"])
    with pytest.raises(SystemExit) as e:
        tool.main()
    assert "needs --did" in str(e.value)
    assert row(ledger(), "Echo")["status"] == "information screen"


def test_a_reader_and_a_vote_of_that_reader_are_one_reading():
    """L5: "reader" beside "reader:<model>" is one source, as "ocr" beside "ocr:<engine>"; two models' votes are two."""
    assert not coverage._independent("reader", "reader:qwen")
    assert not coverage._independent("ocr:apple", "ocr")
    assert coverage._independent("reader:a", "reader:b") and coverage._independent("ocr", "reader:a")
    assert not coverage.readings_agree({"vlm": "On", "votes": [{"source": "reader:qwen", "text": "On"}]})[1]


def test_a_run_that_only_prints_reads_no_download_and_asks_git_nothing(camera, monkeypatch, capsys):
    """L6: without --skip-settled, a greyed row and a row the kit could not read are said by their status alone: no
    download is read (ungreyed) and git is not asked (kit_newer), in the crawl's gate, the prover's and drive.py's;
    with --skip-settled they are judged. Git's status takes no lock on the index."""
    def boom(*a, **k):
        raise AssertionError("judged on a run that only prints")
    monkeypatch.setattr(coverage, "ungreyed", boom)
    monkeypatch.setattr(coverage, "kit_newer", boom)
    led = ledger()
    for path, said in ((["India"], "greyed in state (blocker Alpha)"), (["Juliet"], "kit cannot read")):
        v = coverage.settled(path, camera=CAM, ledger=led, judge=False)
        assert not v.skip and said in v.reason
    gate = coverage.CrawlGate(SimpleNamespace(root=camera.runs, dir=camera.runs / "kit2_crawl"),
                              SimpleNamespace(skip_settled=False, scan=None, network=False), None)
    assert gate.skip({"breadcrumb": "Shooting > G1"}, {"label": "India"}) is None
    jobs = [{"path": ["Juliet"], "kind": "list", "labels": ["Off", "On"]}]
    assert coverage.prove_filter(jobs, SimpleNamespace(skip_settled=False, scan=None, start=None)) == jobs
    coverage.drive_gate(SimpleNamespace(path=["India"], run="kit2_drive_t", scan=None, network=False, owner=False))
    out = capsys.readouterr().out
    assert "India: greyed in state (blocker Alpha)" in out and "Juliet: kit cannot read" in out
    assert "the ledger failed" not in out
    with pytest.raises(AssertionError):
        coverage.settled(["India"], camera=CAM, ledger=led, judge=True)
    asked = []
    monkeypatch.setattr(coverage, "_git", lambda *args: asked.append(args) or "")
    coverage._kit_dirty()
    assert asked[0][:2] == ("--no-optional-locks", "status")


def test_the_prove_looks_never_break_a_run(camera, capsys):
    """L10: a ProveLooks that cannot be made is NO_LOOKS, said in one line."""
    got = coverage.prove_looks(SimpleNamespace(), camera.runs / "p.jsonl", camera.runs / "f.jsonl")
    assert got is coverage.NO_LOOKS and "prove_run.py's looks: the ledger failed" in capsys.readouterr().out
    ok = coverage.prove_looks(SimpleNamespace(root=camera.runs, dir=camera.runs / "x"), camera.runs / "p.jsonl",
                              camera.runs / "f.jsonl")
    assert isinstance(ok, coverage.ProveLooks)


# ---------------------------------------------------------------- the final check's two notes

def test_a_notice_info_ok_did_not_pass_is_greyed_and_one_it_passed_is_looked_at(camera):
    """--info-ok's crawl outcomes: "notice (named, not passed: ...)" stopped the row, as a plain notice does (greyed);
    "notice passed: ..." reached the screen behind it (looked at). Both in the crawl's looks and in its rows.jsonl."""
    def result(outcome):
        return coverage.crawl_looks({"label": "Kilo", "outcome": outcome}, [], None, "r", CAM)[0]["result"]
    assert result("notice") == "greyed"
    assert result("notice (named, not passed: a second button)") == "greyed"
    assert result("notice passed: a checklist screen after its OK, left unwalked") == "looked"
    (camera.runs / "kit2_crawl" / "rows.jsonl").write_text(json.dumps({
        "page": "3/9", "label": "Juliet", "outcome": "notice (named, not passed: a second button)"}) + "\n",
        encoding="utf-8")
    assert row(ledger(), "Juliet")["status"] == "greyed in state"
    (camera.runs / "kit2_crawl" / "rows.jsonl").write_text(json.dumps({
        "page": "3/9", "label": "Juliet", "outcome": "notice passed: a checklist screen after its OK, left unwalked"})
        + "\n", encoding="utf-8")
    led = ledger()
    assert row(led, "Juliet")["status"] == "not yet tried" and row(led, "Juliet")["looked"] == 1


def test_a_commit_range_refuses_a_public_form_in_any_commit_and_judges_the_seen_file(camera, tmp_path):
    """check_public --commits: a commit that adds the public form to data/ is refused, whatever it holds (the clean
    build here), even when a later commit of the range takes it out again, in one line saying what to do (take it out
    of every commit: one commit of the final files on a fresh branch), as the form is printed, never kept
    (docs/decisions/0023). A commit that changes the seen file is held to the seen file's own rules: a clean one
    passes, one naming a group no public source has is refused."""
    import shutil
    import subprocess
    import check_public as C
    if shutil.which("git") is None:
        pytest.skip("git is not installed")
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*a):
        return subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    git("config", "core.autocrlf", "false")
    git("config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("x\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "base")
    base = git("rev-parse", "HEAD")
    (repo / "editor" / "definitions").mkdir(parents=True)
    (repo / "editor" / "definitions" / f"{CAM}.json").write_text(camera.defn.read_text(encoding="utf-8"),
                                                                 encoding="utf-8")
    data = repo / "data" / CAM
    data.mkdir(parents=True)
    for n in (f"camera_{CAM}.json", f"hand_tables_{CAM}.json", f"help_guide_menu_{CAM}.jsonl"):
        (data / n).write_text((camera.data / n).read_text(encoding="utf-8"), encoding="utf-8")
    seen = data / f"seen_{CAM}.json"
    seen.write_text(coverage.text(coverage.seen_doc(CAM, [])), encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "the data")
    (data / f"coverage_{CAM}.json").write_text(coverage.public_build_text(CAM), encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "the form, printed into data/")
    added = git("rev-parse", "HEAD")[:12]
    git("rm", "-q", f"data/{CAM}/coverage_{CAM}.json")
    git("commit", "-q", "--no-verify", "-m", "taken out again")
    fact = {"kind": "acted", "mode": "Stills", "tab": "Shooting", "group": "G1", "path": ["Kilo"]}
    seen.write_text(coverage.text(coverage.seen_doc(CAM, [fact])), encoding="utf-8")
    git("commit", "-q", "--no-verify", "-am", "a good fact")
    seen.write_text(coverage.text(coverage.seen_doc(CAM, [dict(fact, group="Home")])), encoding="utf-8")
    git("commit", "-q", "--no-verify", "-am", "a group no source names")
    bad = git("rev-parse", "HEAD")[:12]
    found = C.commit_problems(f"{base}..HEAD", repo=repo)
    form = [x for x in found if f"data/{CAM}/coverage_{CAM}.json" in x]
    assert len(form) == 1 and form[0].startswith(f"{added} data/{CAM}/coverage_{CAM}.json: "), found
    assert "no longer kept" in form[0] and "take it out of every commit" in form[0], form
    assert "one commit of the final files" in form[0] and "Delete it" not in form[0], form
    said = [x for x in found if f"data/{CAM}/seen_{CAM}.json" in x]
    assert said and all(x.startswith(bad) for x in said) and any("group 'Home'" in x for x in said), found


def test_a_map_whose_options_sit_on_a_panel_is_counted(camera):
    """A panel's option holds its place as a list (row, column): the map's count takes it as it takes a number."""
    d = camera.runs / "kit2_pass1"
    d.mkdir()
    (d / "map_all.json").write_text(json.dumps({"rows": [
        {"path": ["Alpha"], "options": [{"index": [0, 0]}, {"index": [0, 1]}, {"index": [0, 1]}]},
        {"path": ["Bravo"], "options": [{"index": 0}, {"index": 1}]}]}), encoding="utf-8")
    src = coverage.load_sources(CAM, records=RECORDS)
    assert src.maps[("Alpha",)] == 2 and src.maps[("Bravo",)] == 2


def test_the_ledger_reads_a_rows_n_th_label_as_placement_does():
    """A proof path's "#n" names the n-th of the rows bearing a label (camkit.placement.nth: the a1 II's second
    Recording Media row, "Recording Media#1"): the ledger reads it as placement does, the label alone, and on a top row
    the n-th of the tab's rows of that label (an entry's "nth"); two labels naming different places are never one
    row's. Made-up rows."""
    assert coverage.same_label("Recording Media#1", "Recording Media")
    assert coverage.same_label("Recording Media", "Recording Media#0")
    assert not coverage.same_label("Recording Media#1", "Recording Media#2")
    led = coverage.Ledger.__new__(coverage.Ledger)
    led.rows = [coverage._entry("Stills", "Setup", "Operation Customize", ["Custom Key/Dial Set."], "menu", (0, 0, 0), 0),
                coverage._entry("Stills", "Setup", "Operation Customize", ["Custom Key/Dial Set."], "menu", (0, 0, 1), 1),
                coverage._entry("Stills", "Shooting", "Media", ["Rec. Media Settings", "Recording Media"], "setting", (1, 0, 0))]
    assert led.find(["Rec. Media Settings", "Recording Media#1"]) == [led.rows[2]]
    assert led.find(["Custom Key/Dial Set.#1"]) == [led.rows[1]]
    assert led.find(["Custom Key/Dial Set."]) == led.rows[:2]
    assert led.find(["Custom Key/Dial Set.#2"]) == []
