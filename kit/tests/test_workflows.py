"""Offline tests of the kit's CI workflow (.github/workflows/kit-ci.yml): what it runs agrees with the commit hooks'
pins and with kit/setup.py, which a contributor runs instead of it; and of the editor's release workflow
(.github/workflows/editor-release.yml), which can only run on a pushed tag: what its Windows package holds, and that
it carries the definition viewer as one file; and of
the editor's CI (.github/workflows/editor-ci.yml): that its Windows build is checked as the release's is."""
import ast
import re
import shlex

import yaml

from camkit import ROOT

WORKFLOW = ROOT / ".github" / "workflows" / "kit-ci.yml"
RELEASE = ROOT / ".github" / "workflows" / "editor-release.yml"
EDITOR_CI = ROOT / ".github" / "workflows" / "editor-ci.yml"

# The check on the built Windows program, the same lines in both editor workflows: its version details (which build.rs
# links with the icon, from one .res file; a build that cannot make it only warns) name Camset Editor and Cargo.toml's
# version, printed to the log, or the step fails.
DETAILS_CHECK = [
    "$v = (Select-String -Path Cargo.toml -Pattern '^version = \"(.*)\"').Matches[0].Groups[1].Value",
    "$info = (Get-Item target/release/camset_editor.exe).VersionInfo",
    '"ProductName: $($info.ProductName); FileDescription: $($info.FileDescription); ProductVersion: $($info.ProductVersion)"',
    "if ($info.ProductName -cne 'Camset Editor' -or $info.FileDescription -cne 'Camset Editor' -or $info.ProductVersion -cne $v) "
    '{ throw "camset_editor.exe lacks its icon and version details (Camset Editor $v): build.rs did not link them; '
    'its warning in the build\'s log says why" }',
]


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


def test_ci_runs_the_kits_tests_on_windows_in_utf8_mode():
    """The kit's tests run on Windows too (first run there 2026-11-12), with PYTHONUTF8 set for the job, as the kit
    needs on Windows, and with the actions pinned as the Linux job's are."""
    jobs = workflow()["jobs"]
    win = jobs["kit-windows"]
    assert win["runs-on"] == "windows-latest" and win["env"]["PYTHONUTF8"] == "1"
    assert step(win, "tests")["run"] == "python -m pytest -q kit/tests"
    # a hung test stops the job, rather than running for GitHub's default 6 hours
    assert win["timeout-minutes"] == 30 and 0 < jobs["kit"]["timeout-minutes"] <= 30
    pins = {s["uses"] for s in jobs["kit"]["steps"] if "uses" in s}
    assert {s["uses"] for s in win["steps"] if "uses" in s} <= pins


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


def test_release_builds_a_windows_zip_of_one_folder_the_editor_runs_from():
    """The release builds on Windows too (since 2026-11-12), and its zip is one folder, as the Linux tarball is:
    camset_editor.exe with definitions/ beside it (where shipped_dirs looks), the licence as LICENSE.txt (as on the
    macOS disk image) and the licences page beside the program (where licences_page looks), each staged before the
    folder is zipped; a failed build stops the step; the release attaches the zip with the other packages."""
    wf = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
    build = wf["jobs"]["build"]
    assert build["strategy"]["matrix"]["os"] == ["macos-latest", "ubuntu-latest", "windows-latest"]
    assert build["defaults"]["run"]["working-directory"] == "editor"
    # every step written in sh syntax runs only on macOS or Linux, or in bash: Windows runs pwsh by default
    for s in build["steps"]:
        if "run" in s and s.get("shell") not in ("bash", "pwsh"):
            assert s.get("if") in ("runner.os == 'macOS'", "runner.os == 'Linux'") or s["run"] == "cargo test --release", s
    win = step(build, "Windows zip")
    assert win["if"] == "runner.os == 'Windows'" and win["shell"] == "pwsh"
    lines = win["run"].splitlines()
    want = [
        "cargo build --release",
        "if ($LASTEXITCODE) { exit $LASTEXITCODE }",
        '$name = "camset-editor-$v-windows-x64"',
        '$dir = "target/dist/$name"',
        "if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }",
        'if (-not (Test-Path definitions/*.json)) { throw "definitions/ holds no camera definition" }',
        "Copy-Item target/release/camset_editor.exe $dir",
        'Copy-Item -Recurse definitions "$dir/definitions"',
        'Copy-Item ../LICENSE "$dir/LICENSE.txt"',
        "Copy-Item target/dist/THIRD_PARTY_LICENSES.html $dir",
        'Compress-Archive -LiteralPath $dir -DestinationPath "target/dist/$name.zip" -Force',
    ]
    at = [lines.index(w) for w in want]
    assert at == sorted(at), "staged in this order, and zipped last"
    # the program's details are checked after the build and before anything is staged
    check = [lines.index(w) for w in DETAILS_CHECK]
    assert check == list(range(check[0], check[0] + len(check))) and at[1] < check[0] and check[-1] < at[2]
    # the licences page is written before any package is made
    steps = [s.get("name") or "" for s in build["steps"]]
    assert steps.index(next(n for n in steps if n.startswith("Third-party licences"))) < steps.index("Windows zip")
    upload = next(s for s in build["steps"] if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["with"]["name"] == "camset-editor-${{ runner.os }}"           # Linux, macOS, Windows: one each
    assert "editor/target/dist/*.zip" in upload["with"]["path"].split()
    release = wf["jobs"]["release"]
    download = next(s for s in release["steps"] if s.get("uses", "").startswith("actions/download-artifact@"))
    assert download["with"]["pattern"] == "camset-editor-*" and download["with"]["merge-multiple"] is True
    attach = next(s for s in release["steps"] if s.get("uses", "").startswith("softprops/action-gh-release@"))
    assert attach["with"]["files"].split()[:3] == ["dist/*.dmg", "dist/*.tar.gz", "dist/*.zip"]


def test_release_carries_the_definition_viewer_as_one_file():
    """Each release carries the definition viewer as one file (the owner's, 2026-11-12; never committed): the test job
    builds it from the public definitions after the tests and check_public, with the tool's own command, under site/;
    uploads it with the build job's pinned action, failing when it is not there; the release job downloads it by name
    with its own pinned action and attaches it under its one name, so releases/latest/download/camset-viewer.html is
    a stable address."""
    wf = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
    test = wf["jobs"]["test"]
    names = [s.get("name") or "" for s in test["steps"]]
    built = step(test, "The definition viewer as one file")
    assert built["run"] == "python kit/tools/proof_viewer.py --public --single --out site/camset-viewer.html"
    assert names.index("Python tests") + 1 == names.index(built["name"]), "right after the tests and check_public"
    upload = test["steps"][names.index(built["name"]) + 1]
    pinned = next(s["uses"] for s in wf["jobs"]["build"]["steps"] if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["uses"] == pinned and re.fullmatch(r"actions/upload-artifact@[0-9a-f]{40}", upload["uses"])
    assert upload["with"] == {"name": "camset-viewer", "path": "site/camset-viewer.html", "if-no-files-found": "error"}
    assert test["permissions"] == {"contents": "read"}
    release = wf["jobs"]["release"]
    downloads = [s for s in release["steps"] if s.get("uses", "").startswith("actions/download-artifact@")]
    assert len(downloads) == 2 and downloads[0]["uses"] == downloads[1]["uses"]
    assert downloads[1]["with"] == {"name": "camset-viewer", "path": "dist"}
    assert release["needs"] == "build" and wf["jobs"]["build"]["needs"] == "test", "the release needs the job that built the viewer"
    attach = next(s for s in release["steps"] if s.get("uses", "").startswith("softprops/action-gh-release@"))
    assert attach["with"]["files"].split() == ["dist/*.dmg", "dist/*.tar.gz", "dist/*.zip", "dist/camset-viewer.html"]
    assert [s.get("uses", "").split("@")[0] for s in release["steps"]] == ["actions/download-artifact", "actions/download-artifact",
                                                                           "softprops/action-gh-release"]


def test_editor_ci_checks_the_windows_program_s_details():
    """Editor CI builds the program in release mode on Windows too, and checks on Windows, after that build and before
    the tests, that the program carries its version details (and so its icon), as the release's Windows zip step does."""
    job = yaml.safe_load(EDITOR_CI.read_text(encoding="utf-8"))["jobs"]["editor"]
    assert "windows-latest" in job["strategy"]["matrix"]["os"] and job["defaults"]["run"]["working-directory"] == "editor"
    names = [s.get("name") or "" for s in job["steps"]]
    assert step(job, "Build")["run"] == "cargo build --release"
    check = step(job, "Windows program's version details")
    assert check["if"] == "runner.os == 'Windows'" and check["shell"] == "pwsh"
    assert check["run"].splitlines() == DETAILS_CHECK
    at = names.index(check["name"])
    assert names.index("Build") < at < names.index("Test")
