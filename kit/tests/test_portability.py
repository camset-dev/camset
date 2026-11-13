"""Portability (K-12, K-23, K-24): commit hooks on every OS, no silent example config, UTF-8 text."""
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import camkit  # noqa: E402
from camkit import ROOT  # noqa: E402
import hook  # noqa: E402


RUFF_REPO = "https://github.com/astral-sh/ruff-pre-commit"


def test_hooks_run_through_the_wrapper():
    """No hook names .venv/bin (Windows has .venv\\Scripts): every one of the kit's own runs python kit/tools/hook.py.
    The one other is ruff's, at a pinned version, which pre-commit installs itself; it checks and never rewrites."""
    conf = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    ruff = [r for r in conf["repos"] if r["repo"] == RUFF_REPO]
    assert len(ruff) == 1 and re.fullmatch(r"v\d+\.\d+\.\d+", ruff[0]["rev"])
    assert [(h["id"], h["entry"]) for h in ruff[0]["hooks"]] == [("ruff-check", "ruff check --force-exclude")]
    assert "--fix" not in str(ruff[0]) and all(r["repo"] in ("local", RUFF_REPO) for r in conf["repos"])
    hooks = [h for r in conf["repos"] if r["repo"] == "local" for h in r["hooks"]]
    assert hooks
    for h in hooks:
        assert ".venv" not in h["entry"], h["id"]
        assert h["entry"].startswith("python kit/tools/hook.py "), h["id"]
        assert h["language"] == "python", h["id"]


@pytest.mark.parametrize("nt", [False, True])
def test_hook_finds_the_kits_venv_on_each_os(tmp_path, monkeypatch, nt):
    monkeypatch.setattr(hook.os, "name", "nt" if nt else "posix")
    folder = tmp_path / ".venv" / ("Scripts" if nt else "bin")
    with pytest.raises(SystemExit, match="kit/setup.py"):
        hook.command(["python", "x.py"], tmp_path)                 # no venv yet
    folder.mkdir(parents=True)
    exe = folder / ("python.exe" if nt else "python")
    exe.write_text("", encoding="utf-8")
    assert hook.command(["python", "kit/tools/check_public.py"], tmp_path) == [str(exe), "kit/tools/check_public.py"]
    with pytest.raises(SystemExit, match="missing"):
        hook.command(["zensical", "build"], tmp_path)


def test_hook_expands_a_wildcard_against_the_repository(tmp_path, monkeypatch):
    """A hook checks every definition and every data folder's files whatever changed: its wildcards are expanded by
    hook.py, the same on every OS (no shell runs a hook)."""
    folder = tmp_path / ".venv" / ("Scripts" if hook.os.name == "nt" else "bin")
    folder.mkdir(parents=True)
    (folder / ("check-jsonschema.exe" if hook.os.name == "nt" else "check-jsonschema")).write_text("", encoding="utf-8")
    for rel in ("editor/definitions/A_fw1.00.json", "editor/definitions/B_fw2.00.json", "data/A_fw1.00/camera_A_fw1.00.json"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("{}", encoding="utf-8")
    got = hook.command(["check-jsonschema", "--schemafile", "schemas/definition.schema.json", "editor/definitions/*.json"],
                       tmp_path)
    assert got[1:] == ["--schemafile", "schemas/definition.schema.json", "editor/definitions/A_fw1.00.json",
                       "editor/definitions/B_fw2.00.json"]
    assert hook.expanded("data/*/camera_*_fw*.json", tmp_path) == ["data/A_fw1.00/camera_A_fw1.00.json"]
    assert hook.expanded("data/*/help_*_fw*.json", tmp_path) == ["data/*/help_*_fw*.json"]       # none: as given
    # a clone whose own path looks like a pattern: only the argument is one
    odd = tmp_path / "camset [copy]"
    (odd / "editor" / "definitions").mkdir(parents=True)
    (odd / "editor" / "definitions" / "A_fw1.00.json").write_text("{}", encoding="utf-8")
    assert hook.expanded("editor/definitions/*.json", odd) == ["editor/definitions/A_fw1.00.json"]
    conf = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    entries = {h["id"]: h for r in conf["repos"] for h in r["hooks"]}
    assert "editor/definitions/*.json" in entries["definition-json"]["entry"]
    assert entries["definition-json"]["pass_filenames"] is False


def test_no_silent_fallback_to_the_example_config(tmp_path, monkeypatch):
    monkeypatch.setattr(camkit, "CONFIG", tmp_path / "private" / "config.json")
    with pytest.raises(camkit.ConfigMissing, match="private/config.json"):
        camkit.config()
    assert camkit.config(required=False) == {}
    from camkit import frames
    monkeypatch.setattr(frames, "config", camkit.config)
    assert frames.eyes_default() == "osd"                         # no config: the baseline eyes
    (tmp_path / "private").mkdir()
    camkit.CONFIG.write_text('{"camera_ip": "192.0.2.10"}', encoding="utf-8")
    assert camkit.config()["camera_ip"] == "192.0.2.10"
    assert frames.eyes_default() == "hdmi"                        # a config that leaves it out: as before


def test_link_needs_a_config_only_for_the_address(tmp_path, monkeypatch):
    from camkit import link
    from camkit.runs import Run
    monkeypatch.setattr(camkit, "CONFIG", tmp_path / "none.json")
    monkeypatch.setattr(link, "config", camkit.config)
    monkeypatch.delenv("CAMSET_USB", raising=False)
    run = Run("cfg", root=tmp_path)
    with pytest.raises(camkit.ConfigMissing):
        link.Link(run)
    assert link.Link(run, ip="192.0.2.10").args[1:] == ["--ip", "192.0.2.10"]
    assert link.Link(run, usb=True).args[1:] == ["--usb"]


def test_a_copy_of_the_example_config_contacts_nothing(tmp_path, monkeypatch):
    """kit/config.example.json copied as it is (docs/QUICKSTART.md, step 3) gives the kit nothing to contact: no camera
    address, so a camera run stops and asks for one, and no reader. A camera run that asks a reader stops on that
    before it opens the link (check_readers: ConfigMissing, its sentence); inside a run a missing reader is an
    ordinary exception (NoReader, never a SystemExit), which every caller takes as a reader that could not answer, so
    the run's cleanup and restore go on. Until 2026-11-13 its first reader was a server at an example address on the
    local network, to which a copy left as it was sent pictures of the camera's screen. The readers it shows are under
    "readers_examples", which the kit does not read: one of each kind "Choosing a reader" names."""
    import json
    from camkit import link, vlm
    from camkit.runs import Run
    example = json.loads((ROOT / "kit" / "config.example.json").read_text(encoding="utf-8"))
    assert example["camera_ip"] == "" and example["readers"] == []
    (tmp_path / "private").mkdir()
    monkeypatch.setattr(camkit, "CONFIG", tmp_path / "private" / "config.json")
    camkit.CONFIG.write_text(json.dumps(example), encoding="utf-8")
    monkeypatch.setattr(link, "config", camkit.config)
    monkeypatch.setattr(vlm, "config", camkit.config)
    monkeypatch.setattr(vlm, "_STANDING_IN", {})
    monkeypatch.delenv("CAMSET_USB", raising=False)
    with pytest.raises(camkit.ConfigMissing, match="camera_ip"):
        link.Link(Run("cfg", root=tmp_path))
    with pytest.raises(camkit.ConfigMissing, match="lists no reader: copy the ones you choose from \"readers_examples\""):
        vlm.check_readers()
    for asked in (lambda: vlm.role("second"), lambda: vlm.stand_in("second", {"name": "gone"}),
                  lambda: vlm.ask_role("second", b"frame", "prompt", 5)):
        with pytest.raises(vlm.NoReader, match="lists no reader") as got:
            asked()
        assert isinstance(got.value, Exception) and not isinstance(got.value, SystemExit)
    assert {r["name"] for r in example["readers_examples"]} == {"vllm", "omlx", "ollama", "claude", "openai", "gemini"}
    # no private/config.json at all: the start check says so in config()'s own sentence; mid-run it is a NoReader
    camkit.CONFIG.unlink()
    with pytest.raises(camkit.ConfigMissing, match="No private/config.json"):
        vlm.check_readers()
    with pytest.raises(vlm.NoReader):
        vlm.role("second")
    # filled in: the one reader listed plays the second role and the check passes; the third role asks for another,
    # an ordinary exception as the IndexError before it was
    camkit.CONFIG.write_text(json.dumps({**example, "readers": example["readers_examples"][1:2]}), encoding="utf-8")
    vlm.check_readers()
    assert vlm.role("second")["name"] == "omlx"
    with pytest.raises(vlm.NoReader, match="the third role needs another"):
        vlm.role("third")


def test_kit_python_writes_utf8_explicitly():
    """Every text open()/read_text()/write_text() in kit/ names its encoding (cp1252 is Windows' default)."""
    import ast
    missing = []
    for p in sorted((ROOT / "kit").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(("kit/vendor/", "kit/camkit/formats/", "kit/sdk/", "kit/tests/test_core", "kit/tests/test_setup")):
            continue
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or any(k.arg in ("encoding", None) for k in node.keywords):
                continue
            f = node.func
            if isinstance(f, ast.Name) and f.id == "open":
                mode = node.args[1].value if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) else "r"
                if isinstance(mode, str) and "b" not in mode and len(node.args) <= 2:
                    missing.append(f"{rel}:{node.lineno}")
            elif isinstance(f, ast.Attribute) and f.attr in ("read_text", "write_text") and len(node.args) <= 1 \
                    and not (f.attr == "read_text" and node.args):
                missing.append(f"{rel}:{node.lineno}")
    assert missing == []
