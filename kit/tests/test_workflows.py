"""Offline tests of the kit's CI workflow (.github/workflows/kit-ci.yml): what it runs agrees with the commit hooks'
pins and with kit/setup.py, which a contributor runs instead of it."""
import ast
import re
import shlex

import yaml

from camkit import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "kit-ci.yml"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def step(job: dict, name_part: str) -> dict:
    found = [s for s in job["steps"] if name_part in (s.get("name") or "")]
    assert len(found) == 1, name_part
    return found[0]


def test_ci_runs_ruff_at_the_version_the_hook_pins():
    """kit CI runs uvx ruff check kit, ruff at the pre-commit hook's rev, so a commit made with --no-verify is held to
    the same rules (pyproject.toml's [tool.ruff]) as one the hook checked."""
    hooks = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    rev = next(r["rev"] for r in hooks["repos"] if r["repo"].endswith("/ruff-pre-commit"))
    run = step(workflow()["jobs"]["kit"], "ruff").get("run", "")
    assert f"uvx ruff@{rev.removeprefix('v')} check kit" in run.splitlines()
    assert re.search(r"^python -m pip install uv==\d+\.\d+\.\d+$", run, re.M)          # uv itself pinned


def test_ci_builds_the_ocr_helper_on_macos_as_setup_does():
    """The OCR helper (kit/ocr/ocr.swift) is built on macOS with the line kit/setup.py runs, into the runner's temp
    folder, when a change touches kit/ocr/ or this workflow (or by hand); the Linux job runs whatever changed."""
    jobs = workflow()["jobs"]
    assert jobs["kit"]["runs-on"] == "ubuntu-latest" and "needs" not in jobs["kit"] and "if" not in jobs["kit"]
    ocr = jobs["ocr"]
    assert ocr["runs-on"] == "macos-latest" and ocr["needs"] == "ocr-changed"
    assert ocr["if"] == "needs.ocr-changed.outputs.changed == 'true'"
    setup = (ROOT / "kit" / "setup.py").read_text(encoding="utf-8")
    want = ast.literal_eval(re.search(r'cmd = (\["swiftc".*?\])', setup).group(1))
    got = shlex.split(step(ocr, "builds").get("run", ""))
    assert got[:-1] == want[:-1] and want[-2] == "-o" and got[-1] == "$RUNNER_TEMP/ocr"
    diff = jobs["ocr-changed"]
    assert diff["outputs"]["changed"] == "${{ steps.diff.outputs.changed }}"
    script = next(s for s in diff["steps"] if s.get("id") == "diff")["run"]
    assert "-- kit/ocr .github/workflows/kit-ci.yml" in script and "workflow_dispatch" in script
    assert next(s for s in diff["steps"] if "uses" in s)["with"]["fetch-depth"] == 0
