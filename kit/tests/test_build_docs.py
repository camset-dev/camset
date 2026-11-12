"""Offline tests of kit/tools/build_docs.py: a commit never rewrites a definition (editor/definitions/*.json).

Before 2026-11-05 the pre-commit hook ran build_docs.py, which ran kit/schema_update.py --write wherever
runs/kit2_pass2/report.json existed, so a contributor mapping a second camera under that run name rewrote the a1 II's
definition from their own proofs on every commit. Now only --write-schema writes a definition, and the hook never
passes it; the runs are under their camera's folder (runs/<model>_fw<fw>/, camkit.paths), and since definitions are
files per model and firmware (2026-11-06, docs/decisions/0019) --write-schema writes the active camera's own
definition, never another's; --definitions brings every definition's parts from data/ up to date, and the hook never
passes it either. The viewer is built from the active camera's runs alone.
"""
import json
import subprocess
import sys

import pytest
import yaml

from camkit import ROOT, paths

import build_docs

A1 = "ILCE-1M2_fw4.00"


def hook_entries() -> dict:
    cfg = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    return {h["id"]: h["entry"] for repo in cfg["repos"] for h in repo["hooks"]}


def test_the_hook_never_writes_the_definition():
    hooks = hook_entries()
    assert "build_docs.py" in hooks["build-generated"]
    for hook, entry in hooks.items():
        assert "--write-schema" not in entry, hook
        assert "--definitions" not in entry, hook
        assert "schema_update" not in entry, hook


@pytest.fixture
def clone(tmp_path, own_runs, monkeypatch):
    """A clone whose one definition is the a1 II's, with proof runs for it in runs/ILCE-1M2_fw4.00/; subprocess.run
    is recorded, not run."""
    (own_runs / A1 / "kit2_pass2").mkdir(parents=True)
    (own_runs / A1 / "kit2_pass2" / "report.json").write_text("{}", encoding="utf-8")
    (tmp_path / "editor" / "definitions").mkdir(parents=True)
    (tmp_path / "editor" / "definitions" / f"{A1}.json").write_text(json.dumps(
        {"model": "ILCE-1M2", "layouts": [{"model": "ILCE-1M2", "firmware": "4.00"}]}), encoding="utf-8")
    calls = []
    monkeypatch.setattr(build_docs, "ROOT", tmp_path)
    monkeypatch.setattr(build_docs, "reference", lambda: json.loads(
        (tmp_path / "editor" / "definitions" / f"{A1}.json").read_text(encoding="utf-8")))
    monkeypatch.setattr(build_docs, "GENERATED", {})
    monkeypatch.setattr(build_docs, "parsers", lambda: None)

    def run(args, **kw):
        calls.append(([str(a) for a in args], (kw.get("env") or {}).get(paths.ENV)))
        return subprocess.CompletedProcess(args, 0, stdout=str(own_runs / A1 / "_viewer" / "index.html") + "\n")
    monkeypatch.setattr(subprocess, "run", run)
    return calls


def test_build_docs_writes_the_definition_only_when_asked(clone, tmp_path, monkeypatch):
    """With the a1 II's runs and that camera active, the plain build leaves every definition alone;
    --write-schema runs schema_update --write, for that camera."""
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    build_docs.main(["--no-viewer"])
    assert not any("schema_update.py" in " ".join(c) for c, _ in clone)
    build_docs.main(["--no-viewer", "--write-schema"])
    assert [c[1:] for c, _ in clone] == [[str(tmp_path / "kit" / "schema_update.py"), "--write"]]
    assert clone[0] == ([sys.executable, str(tmp_path / "kit" / "schema_update.py"), "--write"], A1)


def test_another_camera_writes_its_own_definition(clone, own_runs, monkeypatch, capsys):
    """A second camera active, with proof runs of its own: --write-schema runs schema_update --write for that camera,
    which writes its own definition (editor/definitions/ILCE-7M5_fw1.00.json) and never the a1 II's; the viewer is
    built from that camera's runs, not the a1 II's."""
    (own_runs / "ILCE-7M5_fw1.00" / "kit2_pass2").mkdir(parents=True)
    (own_runs / "ILCE-7M5_fw1.00" / "kit2_pass2" / "report.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CAMSET_CAMERA", "ILCE-7M5_fw1.00")
    build_docs.main(["--write-schema"])
    assert [env for c, env in clone if "schema_update.py" in " ".join(c)] == ["ILCE-7M5_fw1.00"]
    assert "wrote editor/definitions/ILCE-7M5_fw1.00.json" in capsys.readouterr().out
    assert [env for c, env in clone if "proof_viewer.py" in " ".join(c)] == ["ILCE-7M5_fw1.00"]


def test_definitions_brings_every_definition_up_to_date_from_data(clone, monkeypatch, capsys):
    """--definitions runs schema_update --from-data --write (no runs needed); the plain build never does."""
    monkeypatch.delenv("CAMSET_CAMERA")
    build_docs.main(["--no-viewer"])
    assert not clone
    build_docs.main(["--no-viewer", "--definitions"])
    assert [c[0][1:] for c in clone] == [[str(build_docs.ROOT / "kit" / "schema_update.py"), "--from-data", "--write"]]


def test_the_viewer_is_built_for_the_active_camera(clone, own_runs, monkeypatch, capsys):
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    build_docs.main([])
    assert [env for c, env in clone if "proof_viewer.py" in " ".join(c)] == [A1]
    assert "wrote" in capsys.readouterr().out.splitlines()[-1]
    monkeypatch.setenv("CAMSET_CAMERA", "ILCE-7M5_fw1.00")              # no proof runs of its own: no viewer build
    clone.clear()
    build_docs.main([])
    assert not clone


def test_no_viewer_without_the_cameras_runs(clone, own_runs, monkeypatch, capsys):
    """As proof_viewer.py refuses a page without the camera's own runs, the build says the viewer is not built: with
    no proof runs, and when proof_viewer.py refuses (exit status 3, its reason on stderr)."""
    monkeypatch.setenv("CAMSET_CAMERA", "ILCE-7M5_fw1.00")
    build_docs.main([])
    assert capsys.readouterr().out.splitlines()[-1].startswith("proof viewer not built: no proof runs in ")
    monkeypatch.setenv("CAMSET_CAMERA", A1)
    monkeypatch.setattr(subprocess, "run", lambda args, **kw: subprocess.CompletedProcess(args, 3, stdout="", stderr="No proof viewer for X: why.\n"))
    build_docs.main([])
    assert capsys.readouterr().out.splitlines()[-1] == "proof viewer not built: No proof viewer for X: why."


def test_the_hook_path_never_looks_at_runs(clone, own_runs, monkeypatch):
    """The pre-commit hook's --no-viewer: the kit's runs from before per-camera folders, or no camera named, stop
    nothing (a commit in a clone that has not moved its runs yet still goes through)."""
    (own_runs / "kit2_pass2").mkdir()
    monkeypatch.delenv("CAMSET_CAMERA")
    build_docs.main(["--no-viewer"])
    assert not clone
    with pytest.raises(paths.Leftovers, match="migrate_runs.py"):
        build_docs.main(["--write-schema"])


def test_the_pages_render_per_definition_and_the_header_from_its_block():
    """The Status and Memory map pages render from a definition and its sample; the Memory map's header, sections and
    trailer come from the definition's container block (docs/decisions/0020), never from numbers of the kit's own."""
    from camkit import definitions
    doc = definitions.load(definitions.REFERENCE)
    md = build_docs.memory_map_md(doc)
    assert "## Header (0x00-0x3b)" in md and "| 0x39 | 1 | header checksum |" in md and "`u16 0x02CF`" in md
    assert "| 0 | 0x0003c | 1415 | live settings |" in md and "Each memory set (sections 1-12)" in md
    assert "editor/definitions/ILCE-1M2_fw4.00.json" in md
    status = build_docs.status_md(doc)
    assert status.startswith("# Status: ILCE-1M2, firmware 4.00") and "editor/definitions/ILCE-1M2_fw4.00.DAT" in status


# ---------------------------------------------------------------- one source per fact: the drift test

def test_every_generated_file_is_current():
    """The committed generated files (the record names, the C++ safety lists, the decisions table, the nav's model
    pages) are what their sources give now: a source edited without build_docs.py fails here, as in CI."""
    assert build_docs.stale() == []


@pytest.fixture
def docs_tree(tmp_path, monkeypatch):
    """A clone's docs with two decision records, two model pages, the decisions index and mkdocs.yml with markers."""
    d = tmp_path / "docs"
    (d / "decisions").mkdir(parents=True)
    (d / "models").mkdir()
    (d / "decisions" / "0001-first.md").write_text(
        "# 1. The first, with a | in it\n\n- **Date:** 2026-10 (first kit)\n- **Status:** accepted\n\n## Context\n",
        encoding="utf-8")
    (d / "decisions" / "0002-second.md").write_text(
        "# 2. The second\n\n- **Date:** 2026-11-04\n- **Status:** accepted; amends [1](0001-first.md); carried out\n"
        "  2026-11-06\n\n## Context\n", encoding="utf-8")
    (d / "decisions" / "index.md").write_text(
        f"# Decisions\n\nWritten by hand.\n\n{build_docs.DECISIONS_START}\nSTALE ROW\n{build_docs.DECISIONS_END}\n",
        encoding="utf-8")
    for name in ("ILCE-1M2_fw4.00", "ILCE-7M5_fw1.00", "notes"):
        (d / "models" / f"{name}.md").write_text("# a page\n", encoding="utf-8")
    (tmp_path / "mkdocs.yml").write_text(
        f"nav:\n  - Reference:\n      - Status: STATUS.md\n      {build_docs.NAV_START}\n      - old: x.md\n"
        f"      {build_docs.NAV_END}\n  - Decisions: decisions/index.md\n", encoding="utf-8")
    monkeypatch.setattr(build_docs, "DOCS", d)
    monkeypatch.setattr(build_docs, "ROOT", tmp_path)
    return tmp_path


def test_the_decisions_table_comes_from_the_records(docs_tree):
    text = build_docs.decisions_index()
    assert text.startswith("# Decisions\n\nWritten by hand.\n\n")                       # outside the markers: as written
    assert "| 1 | [The first, with a \\| in it](0001-first.md) | 2026-10 (first kit) |" in text
    assert "| 2 | [The second](0002-second.md) | 2026-11-04; carried out 2026-11-06 |" in text
    assert "STALE ROW" not in text and text.endswith(build_docs.DECISIONS_END + "\n")


def test_the_decisions_table_has_each_records_status(docs_tree):
    """The Status column: each record's Status line, its links' text without their targets, its asides in brackets
    and its "carried out" clause (the Date column's) left out, then whole clauses while they fit in STATUS_CHARS, with
    "; …" for the rest; a first clause too long alone is cut after a whole word."""
    d = docs_tree / "docs" / "decisions"
    (d / "0003-third.md").write_text(
        "# 3. The third\n\n- **Date:** 2026-11-08\n- **Status:** accepted; amends [1](0001-first.md) and\n"
        "  [2](0002-second.md) (the second's rule, in brief); trimmed 2026-11-08: its working notes moved to\n"
        "  [the guide](../GUIDE.md#a-part)\n\n## Context\n", encoding="utf-8")
    (d / "0004-fourth.md").write_text(
        "# 4. The fourth\n\n- **Date:** 2026-11-08\n- **Status:** superseded by a record that says at some length "
        "why it had to go, and when\n\n## Context\n", encoding="utf-8")
    text = build_docs.decisions_index()
    assert "\n| # | Decision | Date | Status |\n|---|---|---|---|\n| 1 |" in text
    assert "| 1 | [The first, with a \\| in it](0001-first.md) | 2026-10 (first kit) | accepted |\n" in text
    assert "| 2 | [The second](0002-second.md) | 2026-11-04; carried out 2026-11-06 | accepted; amends 1 |\n" in text
    assert "| 3 | [The third](0003-third.md) | 2026-11-08 | accepted; amends 1 and 2; … |\n" in text
    cut = "superseded by a record that says at some length why it had…"
    assert len(cut) <= build_docs.STATUS_CHARS and f"| 4 | [The fourth](0004-fourth.md) | 2026-11-08 | {cut} |\n" in text


def test_the_nav_lists_every_model_page(docs_tree):
    import yaml
    nav = yaml.safe_load(build_docs.mkdocs_nav())["nav"]
    assert nav[0]["Reference"] == [{"Status": "STATUS.md"},
                                   {"ILCE-1M2, firmware 4.00": "models/ILCE-1M2_fw4.00.md"},
                                   {"ILCE-7M5, firmware 1.00": "models/ILCE-7M5_fw1.00.md"}]
    (docs_tree / "mkdocs.yml").write_text("nav:\n  - Reference: []\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="markers"):
        build_docs.mkdocs_nav()


def test_the_model_pages_are_in_their_names_order_on_every_os(monkeypatch):
    """The nav lists the model pages by their names' own characters: Windows sorts paths case-folded, which put
    ILCE-7RM4_fw before ILCE-7RM4A_fw there ("_" sorts before "a" but after "A"), so its nav differed from the
    committed one and --check called mkdocs.yml stale. The pages come here as Windows paths, so the order is the sort
    key's on every OS the suite runs on."""
    from pathlib import PureWindowsPath

    class WindowsDocs(PureWindowsPath):
        def glob(self, pattern):          # the model pages, in no particular order
            return [self / f"{n}.md" for n in ("ILCE-7RM4_fw1.00", "ILCE-1M2_fw4.00", "ILCE-7RM4A_fw1.00")]
    docs = WindowsDocs("C:/camset/docs")
    assert sorted(docs.glob("*")) != sorted(docs.glob("*"), key=lambda p: p.name)          # what Windows did
    monkeypatch.setattr(build_docs, "DOCS", docs)
    assert [(m, page) for m, _, page in build_docs.model_pages()] == [
        ("ILCE-1M2", "models/ILCE-1M2_fw4.00.md"), ("ILCE-7RM4A", "models/ILCE-7RM4A_fw1.00.md"),
        ("ILCE-7RM4", "models/ILCE-7RM4_fw1.00.md")]


# ---------------------------------------------------------------- the record names, one file per definition

def test_the_record_names_are_one_file_per_definition():
    """docs/formats/sony_camset_ids_<model>_fw<fw>.ksy for every definition (2026-11-08: one sony_camset_ids.ksy was
    named as if generic and held the a1 II's names), its Kaitai id a valid identifier; the hand-written container
    imports the a1 II's by its file name and reads its enum by that id, and the reader kaitai-struct-compiler wrote is
    the module and class named after it."""
    import importlib
    import re
    import camset_ksy
    from camkit import definitions
    files = build_docs.record_name_files()
    assert set(files) == {camset_ksy.ids_path(p.stem) for p in definitions.DIR.glob("*.json")}
    assert set(files) <= set(build_docs.GENERATED)
    a1 = build_docs.DOCS / "formats" / f"sony_camset_ids_{A1}.ksy"
    assert a1 in files and camset_ksy.ids_id(A1) == "sony_camset_ids_ilce_1m2_fw4_00"
    spec = yaml.safe_load(files[a1](None))
    assert spec["meta"]["id"] == "sony_camset_ids_ilce_1m2_fw4_00" and re.fullmatch(r"[a-z][a-z0-9_]*", spec["meta"]["id"])
    assert "imported by sony_camset.ksy" in spec["doc"]
    container = camset_ksy.format_spec()
    assert container["meta"]["imports"] == [a1.stem]
    assert container["types"]["record"]["seq"][0]["enum"] == f"{spec['meta']['id']}::setting"
    module = importlib.import_module(f"camkit.formats.{spec['meta']['id']}")
    assert int(module.SonyCamsetIdsIlce1m2Fw400.Setting.jpeg_heif_switch) == 0x01D8
    assert not (build_docs.DOCS / "formats" / "sony_camset_ids.ksy").exists()
    assert not (build_docs.READER / "sony_camset_ids.py").exists()


def test_a_second_camera_gets_its_own_record_names(tmp_path, monkeypatch):
    """A definition added beside the a1 II's gets its own file, named and identified by its key, which no container
    spec imports yet; the a1 II's is not touched."""
    import camset_ksy
    from camkit import definitions
    cam = "ILCE-7M5_fw1.00"
    (tmp_path / f"{cam}.json").write_text(json.dumps({
        "model": "ILCE-7M5", "layouts": [{"model": "ILCE-7M5", "firmware": "1.00", "signature": "0123456789abcdef"}],
        "settings": [{"key": "global:0x0018", "name": "Audio Level", "tab": "Shooting", "group": "Audio",
                      "values": [[0, "Off"], [1, "On"]], "proved": True}]}), encoding="utf-8")
    monkeypatch.setattr(definitions, "DIR", tmp_path)
    files = build_docs.record_name_files()
    assert list(files) == [build_docs.DOCS / "formats" / "sony_camset_ids_ILCE-7M5_fw1.00.ksy"]
    text = next(iter(files.values()))(None)
    spec = yaml.safe_load(text)
    assert spec["meta"]["id"] == "sony_camset_ids_ilce_7m5_fw1_00"
    assert "no container spec imports it yet" in spec["doc"]
    assert spec["enums"]["setting"][0x18]["id"] == "audio_level"
    assert text.startswith(f"# Generated by kit/tools/build_docs.py (kit/tools/camset_ksy.py) from editor/definitions/{cam}.json")
    assert camset_ksy.ids_id("DSC-RX1RM3_fw1.00") == "sony_camset_ids_dsc_rx1rm3_fw1_00"


def test_check_names_record_names_no_definition_gives(tmp_path, monkeypatch):
    """A record names file whose definition is gone (renamed or removed) is not left behind unseen: --check says to
    delete it."""
    import camset_ksy
    (tmp_path / "docs" / "formats").mkdir(parents=True)
    (tmp_path / "docs" / "formats" / "sony_camset_ids_ILCE-7M5_fw1.00.ksy").write_text("meta: {}\n", encoding="utf-8")
    monkeypatch.setattr(camset_ksy, "FORMATS", tmp_path / "docs" / "formats")
    monkeypatch.setattr(build_docs, "ROOT", tmp_path)
    monkeypatch.setattr(build_docs, "GENERATED", {})
    monkeypatch.setattr(build_docs, "reader_stale", lambda: [])
    assert build_docs.stale() == ["docs/formats/sony_camset_ids_ILCE-7M5_fw1.00.ksy: no definition gives it now: delete it"]


def test_the_submission_lists_name_the_record_names():
    """A camera's pull request needs its record names (CI's --check fails without them): the bundle's lists name the
    file, and docs/DATA_CONTRACTS.md, the one the others link to, says what writes it."""
    ids = "docs/formats/sony_camset_ids_<model>_fw<fw>.ksy"
    for f in (".github/PULL_REQUEST_TEMPLATE.md", "docs/DATA_CONTRACTS.md", "AGENTS.md", "docs/REMAPPING_PLAYBOOK.md"):
        text = (ROOT / f).read_text(encoding="utf-8")
        assert ids in text, f
        assert f == "docs/DATA_CONTRACTS.md" or "what-a-mapping-delivers" in text or "What a mapping delivers" in text, f
    contracts = (ROOT / "docs" / "DATA_CONTRACTS.md").read_text(encoding="utf-8")
    assert "`kit/tools/build_docs.py --no-viewer` writes from it (the pre-commit hook runs it" in " ".join(contracts.split())


# ---------------------------------------------------------------- the reader's .ksy hashes (no compiler needed)

# record names as camset_ksy writes them: each value's doc ends with its proof count, which the reader leaves out
IDS = ("# Generated by kit/tools/build_docs.py\nmeta:\n  id: sony_camset_ids_x_1_fw1_00\ndoc: The record ids X-1 uses.\n"
       "enums:\n  setting:\n    0x0018:\n      id: audio_level\n      doc: Audio Level. {proved} of 1 settings on it proved.\n")
REBUILD = ("rebuild the reader (kaitai-struct-compiler 0.11: brew install kaitai-struct-compiler on macOS, or the package "
           "for your system at kaitai.io; then kit/tools/build_docs.py --no-viewer)")


@pytest.fixture
def ksy_tree(tmp_path, monkeypatch):
    """A clone's docs/formats with the container and its record names, and a reader built from them (SOURCES.json);
    no kaitai-struct-compiler on the PATH."""
    formats, reader = tmp_path / "docs" / "formats", tmp_path / "kit" / "camkit" / "formats"
    formats.mkdir(parents=True)
    reader.mkdir(parents=True)
    (formats / "sony_camset.ksy").write_text(
        "meta:\n  id: sony_camset\n  imports:\n    - sony_camset_ids_X-1_fw1.00\nseq: []\n", encoding="utf-8")
    (formats / "sony_camset_ids_X-1_fw1.00.ksy").write_text(IDS.format(proved=1), encoding="utf-8")
    monkeypatch.setattr(build_docs, "ROOT", tmp_path)
    monkeypatch.setattr(build_docs, "CONTAINER", formats / "sony_camset.ksy")
    monkeypatch.setattr(build_docs, "READER", reader)
    monkeypatch.setattr(build_docs, "SOURCES", reader / "SOURCES.json")
    monkeypatch.setattr(build_docs.shutil, "which", lambda name: None)
    (reader / "SOURCES.json").write_text(json.dumps(build_docs.source_hashes()), encoding="utf-8")
    return formats


def test_check_sees_a_ksy_changed_since_the_reader_was_built(ksy_tree, capsys):
    """--check needs no compiler to see that a .ksy changed after the reader was compiled from it: SOURCES.json holds
    the SHA-256 of what each source gives the reader (2026-11-08: with the compiler optional, a changed .ksy whose
    reader was not rebuilt passed). A comment, \\r\\n line ends or a record's proof count (a value's doc, which the
    reader leaves out) do not stale it; a record's name does, and the hook's build without a compiler says so."""
    rebuild = REBUILD
    assert set(json.loads(build_docs.SOURCES.read_text(encoding="utf-8"))) == {
        "sony_camset.ksy", "sony_camset_ids_X-1_fw1.00.ksy"}
    assert build_docs.reader_stale() == []
    ids = ksy_tree / "sony_camset_ids_X-1_fw1.00.ksy"
    ids.write_bytes(ids.read_bytes().replace(b"\n", b"\r\n"))          # a checkout with \r\n: the same text
    assert build_docs.reader_stale() == []
    ids.write_text(IDS.format(proved=0).replace("# Generated", "# Written"), encoding="utf-8")   # a proof count, a comment
    assert build_docs.reader_stale() == []
    ids.write_text(IDS.format(proved=0).replace("audio_level", "audio_input_level"), encoding="utf-8")   # a record's name
    assert build_docs.reader_stale() == [f"docs/formats/sony_camset_ids_X-1_fw1.00.ksy changed: {rebuild}"]
    build_docs.parsers()                                               # no compiler: the reader and its hashes stay
    assert capsys.readouterr().out == ("kaitai-struct-compiler not found: the generated reader left as it is\n"
                                       f"the reader is stale: docs/formats/sony_camset_ids_X-1_fw1.00.ksy changed: {rebuild}\n")
    assert build_docs.reader_stale() == [f"docs/formats/sony_camset_ids_X-1_fw1.00.ksy changed: {rebuild}"]
    (ksy_tree / "sony_camset.ksy").write_text("meta:\n  id: sony_camset\nseq: []\n", encoding="utf-8")   # no import now
    assert build_docs.reader_stale() == [
        f"docs/formats/sony_camset.ksy changed: {rebuild}",
        f"docs/formats/sony_camset_ids_X-1_fw1.00.ksy is no longer one the reader is compiled from: {rebuild}"]
    build_docs.SOURCES.unlink()
    assert build_docs.reader_stale() == [f"kit/camkit/formats/SOURCES.json is missing or unreadable: {rebuild}"]


def test_the_compiler_rewrites_the_hashes(ksy_tree, monkeypatch, capsys):
    """With kaitai-struct-compiler present the reader is compiled from the container (its import with it) and
    SOURCES.json rewritten from the .ksy files as they are now; a compile that fails leaves SOURCES.json as it was."""
    calls = []
    monkeypatch.setattr(build_docs.shutil, "which", lambda name: "/bin/ksc")
    monkeypatch.setattr(build_docs.subprocess, "run",
                        lambda args, **kw: calls.append(args) or subprocess.CompletedProcess(args, 0, "", ""))
    ids = ksy_tree / "sony_camset_ids_X-1_fw1.00.ksy"
    ids.write_text("meta:\n  id: sony_camset_ids_x_1_fw1_00\nenums: {}\n", encoding="utf-8")
    assert build_docs.reader_stale()
    build_docs.parsers()
    assert calls == [["/bin/ksc", "--target", "python", "--python-package", "camkit.formats", "--outdir",
                      str(build_docs.READER), str(ksy_tree / "sony_camset.ksy")]]
    assert build_docs.reader_stale() == []
    assert json.loads(build_docs.SOURCES.read_text(encoding="utf-8"))["sony_camset_ids_X-1_fw1.00.ksy"] == build_docs.sha256(ids)
    assert "SOURCES.json" in capsys.readouterr().out
    was = build_docs.SOURCES.read_text(encoding="utf-8")
    ids.write_text("meta:\n  id: sony_camset_ids_x_1_fw1_00\nenums: {broken\n", encoding="utf-8")
    monkeypatch.setattr(build_docs.subprocess, "run", lambda args, **kw: subprocess.CompletedProcess(args, 2, "", "bad yaml"))
    with pytest.raises(SystemExit, match="could not compile"):
        build_docs.parsers()
    assert build_docs.SOURCES.read_text(encoding="utf-8") == was
    [why] = build_docs.reader_stale()                                   # --check says which file, with no traceback
    assert why.startswith("docs/formats/sony_camset_ids_X-1_fw1.00.ksy does not read as YAML (") and why.endswith(
        f": correct it, then {REBUILD}")


def test_the_cpp_header_matches_by_case():
    """never_touch.h's rules are matched as the SDK spells its names, as camkit.safety matches them (2026-11-08): the
    header compiled with std::regex::icase still refused 23 of the a1 II's names by accident (guards_test.cpp checks
    them)."""
    header = build_docs.never_touch_h()
    assert "icase" not in header and '"CrDeviceProperty_"), case ignored' not in header
    assert "Case matters: the SDK's names are CamelCase" in header
    assert "std::regex(r.pattern, std::regex::ECMAScript)" in header
