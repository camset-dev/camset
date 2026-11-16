"""The coverage ledger (kit/camkit/coverage.py, kit/tools/coverage.py; docs/decisions/0023), off the camera: a made-up
camera (a definition, hand tables, a camera file, a Help Guide list, looks, a crawl row, proofs and leads in folders of
the test's own) gives every status at least once and each entry exactly one; a status that claims a test cites a look,
a crawl row or a proof line in the private form; the statuses generated from the definition agree with it (the a1 II's
committed public form is the public build, byte for byte); the public form is built from the public sources and the
allow-list alone, so no state seen reaches it, and kit/tools/check_public.py refuses one that holds a private key, a
date, a hash or a word outside its closed vocabulary; settled() never settles a row with values still to try, nor one
of another mode, nor anything when the ledger is missing or stale; the runs only print what it says unless given
--skip-settled (drive.py never skips), and a ledger error or a look that cannot be written never breaks a run."""
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
        ("Setup", "G2", "Display Serial Number"), ("Setup", "G2", "Version")]
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
]
RECORDS = {f"global:0x{i:04x}": (1, 1) for i in (0x0100, 0x0101, 0x0102, 0x0103, 0x0104, 0x0105, 0x0106, 0x0107,
                                                  0x0108, 0x0200, 0x0201, 0x0202)}
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
    fixture puts it."""
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
    assert seen == set(coverage.STATUS_NAMES)
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
    out = coverage.write(led, tmp_path / "pub.json", tmp_path / "priv.json", tmp_path / "seen.json")
    assert out == [tmp_path / "pub.json", tmp_path / "seen.json", tmp_path / "priv.json"]
    first = (tmp_path / "pub.json").read_bytes()
    coverage.write(ledger(validity=True), tmp_path / "pub.json", tmp_path / "priv.json", tmp_path / "seen.json")
    assert (tmp_path / "pub.json").read_bytes() == first
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
    confirmed go into the seen file, and the public form is the build of the public sources and that file: a fresh
    clone's build (no looks) gives its bytes again."""
    add_looks(camera,
              look(["Kilo"], screen="notice", fields=["Device Address", "My Camera", "Alpha"]),
              look(["Version"], result="acted"),
              look(["Foxtrot"], by="hand", did="choose", option="Off", result="changed",
                   records_changed=["global:0x0103"]))
    led = coverage.build(CAM)
    assert row(led, "Kilo")["fields"] == ["Device Address", "Alpha"]          # privately, the label too
    written = coverage.write(led)
    assert coverage.seen_file(CAM) in written and coverage.public_file(CAM) in written
    facts = {(x["kind"], tuple(x["path"])): x for x in seen_facts(camera)}
    assert facts[("info", ("Kilo",))]["fields"] == ["Device Address"]
    assert facts[("info", ("Echo",))]["fields"] == ["IP Address", "MAC Address"]
    assert ("acted", ("Version",)) in facts and ("confirmed", ("Delta",)) in facts
    assert facts[("hand_changed", ("Foxtrot",))]["values"] == {"global:0x0103": [0]}
    assert "option" not in json.dumps(seen_facts(camera))
    doc = json.loads(coverage.public_file(CAM).read_text(encoding="utf-8"))
    by = {tuple(r["path"]): r for r in doc["rows"]}
    assert by[("Kilo",)]["status"] == "information screen" and by[("Kilo",)]["fields"] == ["Device Address"]
    assert by[("Version",)]["status"] == "action, nothing to map" and "inferred" not in by[("Version",)]
    assert by[("Foxtrot",)]["status"] == "proved by hand" and by[("Delta",)]["confirmed"] is True
    assert {o["key"]: o for o in doc["options"]}["global:0x0103"]["statuses"]["proved by hand"] == [0]
    assert coverage.public_file(CAM).read_text(encoding="utf-8") == coverage.public_build_text(CAM)
    from camkit import datafiles
    assert datafiles.evidence_in_public(coverage.public_file(CAM)) == []
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
    by = {tuple(r["path"]): r for r in json.loads(coverage.public_file(CAM).read_text(encoding="utf-8"))["rows"]}
    assert by[("Kilo",)]["status"] == "not yet tried"


def test_a_hand_edit_of_the_public_form_or_the_seen_file_is_refused(camera):
    """L1: the committed form must be the build of the public sources and the seen file. A row edited to "needs
    equipment" with a lens, an information screen, an action or a value proved by hand written into the form by hand
    are refused; an edit of the seen file shows there, and words its sources do not know (a field that is no address
    field, a value no setting has) are refused in it."""
    from camkit import datafiles
    coverage.write(coverage.build(CAM, public=True))
    pub, seen = coverage.public_file(CAM), coverage.seen_file(CAM)
    clean = pub.read_text(encoding="utf-8")
    assert datafiles.evidence_in_public(pub) == [] and datafiles.evidence_in_public(seen) == []
    edits = {
        "needs equipment": ('"path": ["Kilo"], "status": "not yet tried"',
                            '"path": ["Kilo"], "status": "needs equipment", "equipment": "a lens"'),
        "information screen": ('"path": ["Kilo"], "status": "not yet tried"',
                               '"path": ["Kilo"], "status": "information screen", "fields": ["SSID", "Password"]'),
        "action": ('"path": ["Kilo"], "status": "not yet tried"', '"path": ["Kilo"], "status": "action, nothing to map"'),
        "proved by hand": ('{"key": "global:0x0103", "statuses": {"not yet tried": [0, 1]}}',
                           '{"key": "global:0x0103", "statuses": {"proved by hand": [0], "not yet tried": [1]}}'),
    }
    for what, (a, b) in edits.items():
        assert clean.count(a) == 1, what
        pub.write_text(clean.replace(a, b), encoding="utf-8")
        found = datafiles.evidence_in_public(pub)
        assert any("not the public build" in x for x in found), what
    pub.write_text(clean, encoding="utf-8")
    doc = json.loads(seen.read_text(encoding="utf-8"))
    for fact, said in (({"kind": "info", "mode": "Stills", "tab": "Shooting", "group": "G1", "path": ["Kilo"],
                         "fields": ["SSID", "Password", "Alpha"]}, "field 'Alpha'"),
                       ({"kind": "hand_changed", "mode": "Stills", "tab": "Shooting", "group": "G1",
                         "path": ["Foxtrot"], "values": {"global:0x0103": [9]}}, "value"),
                       ({"kind": "acted", "mode": "Stills", "tab": "Shooting", "group": "Home", "path": ["Kilo"]},
                        "group 'Home'")):
        seen.write_text(coverage.text(dict(doc, facts=[fact])), encoding="utf-8")
        assert any(said in x for x in datafiles.evidence_in_public(seen)), said
    # a good fact by hand shows in the seen file, and the form must then be its build
    seen.write_text(coverage.text(dict(doc, facts=[{"kind": "acted", "mode": "Stills", "tab": "Shooting",
                                                    "group": "G1", "path": ["Kilo"]}])), encoding="utf-8")
    assert datafiles.evidence_in_public(seen) == []
    assert any("not the public build" in x for x in datafiles.evidence_in_public(pub))


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


def test_the_checkers_refuse_a_state_word_a_date_a_run_a_commit_and_free_text(camera, tmp_path, monkeypatch):
    """The reviewer's probes: a blocker naming a row with its value, a remote blocker carrying a date with its time, a
    run and a short commit, field names that are no address field, a 12-hex prefix in a note; also a greyed row not
    inferred from an inactive_when, a value said tested, and "runs/". coverage.public_problems,
    datafiles.evidence_in_public and check_public's commit check refuse each."""
    import check_public as C
    from camkit import datafiles
    add_looks(camera, look(["Kilo"], screen="notice", fields=["IP Address"]))
    coverage.write(coverage.build(CAM))
    folder = tmp_path / "pubcheck" / "data" / CAM
    folder.mkdir(parents=True)
    for n in (f"camera_{CAM}.json", f"help_guide_menu_{CAM}.jsonl", f"hand_tables_{CAM}.json", f"seen_{CAM}.json"):
        (folder / n).write_text((camera.data / n).read_text(encoding="utf-8"), encoding="utf-8")
    doc = json.loads(coverage.public_file(CAM).read_text(encoding="utf-8"))
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
    f = folder / f"coverage_{CAM}.json"
    for what, change in probes.items():
        bad = json.loads(json.dumps(doc))
        change(bad)
        t = coverage.text(bad)
        assert coverage.public_problems(json.loads(t), t, camera=CAM), what
        f.write_text(t, encoding="utf-8")
        assert datafiles.evidence_in_public(f), what
        assert C.blob_problems(f"data/{CAM}/coverage_{CAM}.json", t), what       # a commit's blob, the same checks
    f.write_text(coverage.text(doc), encoding="utf-8")
    assert datafiles.evidence_in_public(f) == []
    assert C.blob_problems(f"data/{CAM}/coverage_{CAM}.json", coverage.text(doc)) == []
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


def test_check_public_refuses_a_public_form_with_private_keys(camera, tmp_path, monkeypatch):
    import check_public as C
    from camkit import datafiles
    d = camera.data
    f = d / f"coverage_{CAM}.json"
    f.write_text(json.dumps({"rows": [{"path": ["Alpha"], "status": "proved", "t": "x", "start_sha256": SHA}],
                             "records": [{"key": "global:0x0001", "status": "unmapped", "cites": [{"run": "r"}]}]}),
                 encoding="utf-8")
    monkeypatch.setattr(C, "ROOT", camera.data.parent.parent)
    found = C.data_problems()
    assert found and any(x.startswith(f"data/{CAM}/coverage_{CAM}.json: ") for x in found)
    said = datafiles.evidence_in_public(f)
    assert any("'t'" in x for x in said) and any("start_sha256" in x for x in said) and any("'cites'" in x for x in said)
    assert any("schema" in x for x in said)
    assert any("kit/tools/coverage.py --write" in x for x in found)
    looks = d / f"looks_{CAM}.jsonl"
    looks.write_text("{}\n", encoding="utf-8")
    assert any("looks file" in x for x in datafiles.evidence_in_public(looks))
    looks.unlink()
    f.write_text(coverage.public_build_text(CAM), encoding="utf-8")
    assert datafiles.evidence_in_public(f) == []
    assert C.data_problems() == []
    # a camera with no definition: its words cannot be checked, so it is refused
    other = tmp_path / "data" / "ILCE-0X0_fw1.00"
    other.mkdir(parents=True)
    g = other / "coverage_ILCE-0X0_fw1.00.json"
    g.write_text(coverage.text(dict(coverage.public_doc(ledger()), model="ILCE-0X0", firmware="1.00")),
                 encoding="utf-8")
    assert any("no definition" in x for x in datafiles.evidence_in_public(g))


def test_the_a1_ii_public_form_agrees_with_its_definition():
    """The committed form (data/ILCE-1M2_fw4.00/coverage_ILCE-1M2_fw4.00.json): its schema, no private key, no word
    outside its vocabulary, every value it calls proved or not offered is so in the definition and the other way round,
    every top row and record of the definition's file is in it once. A definition written since needs
    kit/tools/coverage.py --write."""
    import jsonschema
    f = coverage.public_file(A1)
    doc = json.loads(f.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(json.loads((ROOT / "schemas" / "coverage.schema.json").read_text(
        encoding="utf-8"))).validate(doc)
    assert coverage.public_problems(doc, f.read_text(encoding="utf-8"), camera=A1) == []
    defn = definitions.load_public(A1)
    by_key = {o["key"]: o["statuses"] for o in doc["options"]}
    again = "; run kit/tools/coverage.py --write"
    for s in defn["settings"]:
        if not s.get("values"):
            continue
        st = by_key.get(s["key"])
        assert st is not None, s["key"] + again
        p = s.get("proved") or {}
        linear = (p.get("sampled") or {}).get("linear") is True
        proved = {v for v, _ in s["values"]} if linear else (set() if "sampled" in p else set(p.get("values") or []))
        assert set(st.get("proved", [])) == proved, s["key"] + again
        marks = {x["value"] for x in s.get("not_offered") or []} - proved - set(p.get("values") or [])
        assert set(st.get("not offered", [])) == marks, s["key"] + again
    tops = {(r["tab"], r["path"][0], r.get("nth", 0)) for r in doc["rows"] if len(r["path"]) == 1 and r["mode"] ==
            coverage.MENU_MODE}
    seen = {}
    for m in defn["menu"]:
        n = seen.get((m["tab"], m["label"]), 0)
        seen[(m["tab"], m["label"])] = n + 1
        assert (m["tab"], m["label"], n) in tops, m["label"] + again
    assert len(doc["records"]) == len({r["key"] for r in doc["records"]})
    serial = next(r for r in doc["rows"] if r["path"] == ["Display Serial Number"])
    assert serial["status"] == "information screen" and serial["inferred"] == "class"


def test_the_a1_ii_public_form_is_the_public_build():
    """kit/tools/coverage.py --check and check_public, as CI runs them: the committed form is, byte for byte, what the
    public sources give with its seen file's facts (no runs, no looks file here), and the seen file is clean."""
    from camkit import datafiles
    assert coverage.public_build_text(A1) == coverage.public_file(A1).read_text(encoding="utf-8"), \
        "run kit/tools/coverage.py --write"
    assert datafiles.evidence_in_public(coverage.public_file(A1)) == []
    assert datafiles.evidence_in_public(coverage.seen_file(A1)) == []


def test_the_tool_checks_the_committed_form(camera, monkeypatch, capsys):
    import coverage as tool
    want = coverage.public_build_text(CAM)
    coverage.public_file(CAM).write_text(want, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["coverage.py", "--check"])
    tool.main()
    out = capsys.readouterr().out
    assert "is the public build" in out and "would change" in out          # Echo's look is not in a seen file yet
    coverage.public_file(CAM).write_text(want.replace('"Alpha"', '"Alpha "', 1), encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        tool.main()
    assert "differs from the public build" in str(e.value)


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
    """drive.py's gate prints what the ledger says and goes on, settled or not (no exit before connecting); after the
    run it records one look."""
    a = SimpleNamespace(path=["Alpha"], run="kit2_drive_t", scan=None, network=False, owner=False)
    coverage.drive_gate(a)
    out = capsys.readouterr().out
    assert "coverage: settled: Alpha: proved" in out and "drive.py goes on (it never skips)" in out
    gate = coverage.drive_gate(SimpleNamespace(**{**vars(a), "path": ["Kilo"]}))
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


def test_no_ledger_says_so_and_skips_nothing(camera, capsys):
    camera.looks.unlink()
    coverage.forget()
    gate = coverage.drive_gate(SimpleNamespace(path=["Alpha"], run="kit2_drive_t", scan=None, network=False,
                                               owner=False))
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


def test_a_commit_range_builds_each_commits_public_form_from_that_commit(camera, tmp_path):
    """check_public --commits: a commit that edits the public form by hand ("needs equipment" with a lens) is refused
    by the build check, made from that SAME commit's definition, data folder and seen file taken out of git, even when
    a later commit of the range puts the form right; a clean commit and the commit that mends it pass."""
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
    (data / f"seen_{CAM}.json").write_text(coverage.text(coverage.seen_doc(CAM, [])), encoding="utf-8")
    clean = coverage.public_build_text(CAM)
    (data / f"coverage_{CAM}.json").write_text(clean, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "--no-verify", "-m", "the ledger")
    first = git("rev-parse", "HEAD")[:12]
    a = '"path": ["Kilo"], "status": "not yet tried"'
    (data / f"coverage_{CAM}.json").write_text(
        clean.replace(a, '"path": ["Kilo"], "status": "needs equipment", "equipment": "a lens"'), encoding="utf-8")
    git("commit", "-q", "--no-verify", "-am", "an edit by hand")
    edited = git("rev-parse", "HEAD")[:12]
    (data / f"coverage_{CAM}.json").write_text(clean, encoding="utf-8")
    git("commit", "-q", "--no-verify", "-am", "put right")
    mended = git("rev-parse", "HEAD")[:12]
    found = [x for x in C.commit_problems(f"{base}..HEAD", repo=repo) if "not the public build" in x]
    assert any(x.startswith(f"{edited} data/{CAM}/coverage_{CAM}.json: ") for x in found), found
    assert not any(x.startswith((first, mended)) for x in found), found
    # the commit's own files, not the tree's: a seen file changed in a commit is built with that commit's form
    assert C.coverage_commit_problems(git("rev-parse", "HEAD"), [f"data/{CAM}/seen_{CAM}.json"], C._Objects(repo),
                                      repo) == []


def test_a_map_whose_options_sit_on_a_panel_is_counted(camera):
    """A panel's option holds its place as a list (row, column): the map's count takes it as it takes a number."""
    d = camera.runs / "kit2_pass1"
    d.mkdir()
    (d / "map_all.json").write_text(json.dumps({"rows": [
        {"path": ["Alpha"], "options": [{"index": [0, 0]}, {"index": [0, 1]}, {"index": [0, 1]}]},
        {"path": ["Bravo"], "options": [{"index": 0}, {"index": 1}]}]}), encoding="utf-8")
    src = coverage.load_sources(CAM, records=RECORDS)
    assert src.maps[("Alpha",)] == 2 and src.maps[("Bravo",)] == 2
