"""Offline tests of the kit's CI workflow (.github/workflows/kit-ci.yml): what it runs agrees with the commit hooks'
pins and with kit/setup.py, which a contributor runs instead of it; and of the editor's release workflow
(.github/workflows/editor-release.yml), which can only run on a pushed tag: that it builds only a tag on main, what
its Windows packages hold (the zip, and the installer built from the same folder by
editor/packaging/windows/installer.iss, whose promises are checked here too), and that it carries the definition viewer
as one file; and of the editor's CI (.github/workflows/editor-ci.yml): that its Windows build is checked, and its
installer compiled, as the release's."""
import ast
import fnmatch
import os
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

INSTALLER = ROOT / "editor" / "packaging" / "windows" / "installer.iss"
# The id Windows knows the installed editor by, written once (2026-11-13): an upgrade finds the earlier install by it
# and replaces it in place. If this fails, the script's id was changed: put it back, or a newer version would install
# beside the older one instead of over it. (Inno Setup writes the opening brace doubled.)
APP_ID = "{{D085EF97-DFDB-47C5-8F43-2AA76E78B25D}"
# The lines that build the installer, the same in both editor workflows, after Cargo.toml's version is read (the
# first line of DETAILS_CHECK): the staged program, the first sentence of whose copyright detail goes into the
# installer's (Inno Setup keeps 100 characters of it); ISCC.exe in its own folder (on the runner, the one on the PATH
# is Chocolatey's stand-in) or on the PATH, or the step stops saying so (nothing is downloaded for it); its version in
# the log; the version and the copyright sentence passed in; a failed compile stops the step; the installer there, of
# a program's size; and its own version details (a signing service asks for the product's name and version on every
# file it signs), each trimmed of the spaces Inno Setup pads its slot with, printed and checked as the program's are:
# Camset Editor, the program's version as its product and file version, its description, publisher and copyright.
INSTALLER_BUILD = [
    '$exe = Get-Item "target/dist/camset-editor-$v-windows-x64/camset_editor.exe"',
    "$copyright = ($exe.VersionInfo.LegalCopyright -split '(?<=\\.) ', 2)[0]",
    '$iscc = @("${env:ProgramFiles(x86)}\\Inno Setup 6\\ISCC.exe", (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source) '
    "| Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1",
    'if (-not $iscc) { throw "Inno Setup (ISCC.exe) is not on this runner, neither on the PATH nor in C:\\Program Files (x86)\\Inno Setup 6: '
    "GitHub's Windows images have carried it (their list of installed software says which version). "
    'Install it here by a pinned version with its checksum, never a bare download." }',
    '"Inno Setup $((Get-Item $iscc).VersionInfo.ProductVersion): $iscc"',
    '& $iscc "/DAppVersion=$v" "/DAppCopyright=$copyright" packaging\\windows\\installer.iss',
    'if ($LASTEXITCODE) { throw "ISCC.exe stopped with exit code ${LASTEXITCODE}: its message above says why" }',
    '$setup = Get-Item "target/dist/camset-editor-$v-windows-x64-setup.exe" -ErrorAction SilentlyContinue',
    "if (-not $setup -or $setup.Length -lt 1MB) "
    '{ throw "ISCC.exe made no installer of a program\'s size at target/dist/camset-editor-$v-windows-x64-setup.exe" }',
    "$info = [ordered]@{}",
    "foreach ($k in 'ProductName', 'ProductVersion', 'FileVersion', 'FileDescription', 'CompanyName', 'LegalCopyright') "
    '{ $info[$k] = "$($setup.VersionInfo.$k)".TrimEnd() }',
    '"$($setup.Name): $($setup.Length) bytes; " + (($info.Keys | ForEach-Object { "$($_): $($info[$_])" }) -join \'; \')',
    "if ($info.ProductName -cne 'Camset Editor' -or $info.ProductVersion -cne $v -or $info.FileVersion -cne $v -or "
    "$info.FileDescription -cne 'Camset Editor Setup' -or $info.CompanyName -cne 'Camset contributors' -or "
    "$info.LegalCopyright -cne $copyright) "
    '{ throw "$($setup.Name) lacks its version details (Camset Editor $v and the copyright sentence of camset_editor.exe): '
    'the VersionInfo lines of installer.iss say what it carries" }',
]
# The width of each slot Inno Setup writes a version detail into (SetupLdr.version.rc): a longer text is cut, a
# shorter one padded with spaces, which .NET's FileVersionInfo keeps.
INNO_SLOTS = {"CompanyName": 60, "FileDescription": 60, "FileVersion": 20, "LegalCopyright": 100, "OriginalFileName": 50,
              "ProductName": 60, "ProductVersion": 50}


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def step(job: dict, name_part: str) -> dict:
    found = [s for s in job["steps"] if name_part in (s.get("name") or "")]
    assert len(found) == 1, name_part
    return found[0]


def iss() -> dict[str, list[str]]:
    """installer.iss by section, comments and blank lines left out: under "" the preprocessor's lines before the first
    section, then each section's lines, stripped."""
    sections: dict[str, list[str]] = {"": []}
    name = ""
    for line in INSTALLER.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if not t or t.startswith(";"):
            continue
        if m := re.fullmatch(r"\[(\w+)\]", t):
            name = m.group(1)
            assert name not in sections, f"[{name}] twice"
            sections[name] = []
        else:
            sections[name].append(t)
    return sections


def iss_setup() -> dict[str, str]:
    """The [Setup] section's directives, each written once."""
    pairs = [line.split("=", 1) for line in iss()["Setup"]]
    assert len({k for k, _ in pairs}) == len(pairs), "a directive written twice"
    return dict(pairs)


def iss_entries(section: str) -> list[dict[str, str]]:
    """An entry section's lines as their parameters (Name: "value"; Flags: a b), quotes taken off."""
    out = []
    for line in iss()[section]:
        params = re.findall(r'(\w+):\s*("[^"]*"|[^;]*?)\s*(?:;|$)', line)
        assert params and "; ".join(f"{k}: {v}" for k, v in params) == line, line
        out.append({k: v.strip('"') for k, v in params})
    return out


def zip_names(lines: list[str]) -> set[str]:
    """What a staging step's Copy-Item lines put into the package's folder ($dir), by the name each has there."""
    names = set()
    for line in lines:
        if line.startswith("Copy-Item "):
            src, dest = shlex.split(line.removeprefix("Copy-Item -Recurse ").removeprefix("Copy-Item "))
            names.add(src.rsplit("/", 1)[-1] if dest == "$dir" else dest.removeprefix("$dir/"))
    return names


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
            assert s.get("if") in ("runner.os == 'macOS'", "runner.os == 'Linux'") \
                or s["run"] == "cargo test --release --locked", s
    win = step(build, "Windows zip")
    assert win["if"] == "runner.os == 'Windows'" and win["shell"] == "pwsh"
    lines = win["run"].splitlines()
    want = [
        "cargo build --release --locked",
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
    assert attach["with"]["files"].split() == ["dist/*.dmg", "dist/*.tar.gz", "dist/*.zip", "dist/*.exe", "dist/camset-viewer.html"]
    assert [s.get("uses", "").split("@")[0] for s in release["steps"]] == ["actions/download-artifact", "actions/download-artifact",
                                                                           "softprops/action-gh-release"]


def test_release_builds_only_a_tag_on_main():
    """A pushed tag builds only when the commit it names is on main (2026-11-13; docs/CODE_SIGNING_POLICY.md says so):
    the test job's checkout fetches the whole history and every branch (fetch-depth: 0) and keeps no credentials; its
    first step, before anything is installed or built, runs on a push (a tag: the workflow's only push) and fails with
    a sentence unless main was fetched and holds the tagged commit; run by hand it is skipped. Every later job needs
    the test job, so after it fails nothing is built or released."""
    wf = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
    on = wf.get("on", wf.get(True))                                   # YAML 1.1 reads the key on as true
    assert list(on["push"]) == ["tags"] and "workflow_dispatch" in on
    checkout, check = wf["jobs"]["test"]["steps"][:2]
    assert re.fullmatch(r"actions/checkout@[0-9a-f]{40}", checkout["uses"])
    assert checkout["with"] == {"persist-credentials": False, "fetch-depth": 0}
    assert check["name"] == "The tagged commit is on main" and check["if"] == "github.event_name == 'push'"
    lines = check["run"].splitlines()
    assert lines.index("if ! git rev-parse --verify --quiet refs/remotes/origin/main >/dev/null; then") \
        < lines.index("if ! git merge-base --is-ancestor HEAD refs/remotes/origin/main; then")
    errors = [ln for ln in lines if "::error::" in ln]
    assert len(errors) == 2 == lines.count("  exit 1") and all("Nothing was built" in ln for ln in errors)
    assert "push main first, then re-run this job" in errors[1]                   # a tag pushed before main was
    assert wf["jobs"]["build"]["needs"] == "test" and wf["jobs"]["release"]["needs"] == "build"


def test_the_released_program_is_built_from_the_locked_crates():
    """Every cargo build and test of the release workflow, and of the packaging scripts it runs, takes --locked: the
    crates are editor/Cargo.lock's, or the build stops (docs/CODE_SIGNING_POLICY.md says so), as cargo about already
    does; editor-ci.yml checks pull requests as before."""
    packaging = ROOT / "editor" / "packaging"
    scripts = [RELEASE, packaging / "build_macos_app.sh", packaging / "build_linux.sh"]
    runs = [ln.strip().removeprefix("run: ") for p in scripts for ln in p.read_text(encoding="utf-8").splitlines()
            if re.match(r"\s*(run: )?cargo (build|test|about)\b", ln)]
    assert len(runs) == 6 and all("--locked" in r.split() for r in runs), runs


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


def test_the_installer_installs_the_zips_four_for_this_user_alone():
    """editor/packaging/windows/installer.iss (Inno Setup 6.3 or later, which the script checks): installs for the user
    alone, with no administrator rights, under %LOCALAPPDATA%\\Programs\\Camset Editor, the four things the zip holds,
    from the very folder the zip step staged, in its layout; Windows' installed apps list it as Camset Editor with its
    version, the publisher Camset contributors, the program's own icon and the project's page (Cargo.toml's
    repository); its id is the one written once, so a newer version upgrades the older in place; and the version is
    passed in from Cargo.toml, never written in the script."""
    text = INSTALLER.read_text(encoding="utf-8")
    assert INSTALLER.read_bytes().isascii(), "plain ASCII: Inno Setup reads a script without a BOM in the system's code page"
    s, setup = iss(), iss_setup()
    assert setup["AppId"] == APP_ID and text.count(APP_ID.strip("{}")) == 1
    assert setup["PrivilegesRequired"] == "lowest" and "PrivilegesRequiredOverridesAllowed" not in setup
    assert setup["DefaultDirName"] == "{localappdata}\\Programs\\Camset Editor"
    assert setup["AppName"] == setup["UninstallDisplayName"] == "Camset Editor"
    assert setup["AppPublisher"] == "Camset contributors"
    assert setup["UninstallDisplayIcon"] == "{app}\\camset_editor.exe"
    cargo = (ROOT / "editor" / "Cargo.toml").read_text(encoding="utf-8")
    repo = re.search(r'^repository = "(.*)"$', cargo, re.M).group(1)
    assert (setup["AppPublisherURL"], setup["AppSupportURL"], setup["AppUpdatesURL"]) == (repo, f"{repo}/issues", f"{repo}/releases")
    # the version: passed in (the compile stops without it), never written here
    version = re.search(r'^version = "(.*)"$', cargo, re.M).group(1)
    assert setup["AppVersion"] == setup["VersionInfoVersion"] == "{#AppVersion}"
    assert version not in text and not re.search(r"\d+\.\d+\.\d+", text)
    pre = s[""]
    assert pre[pre.index("#ifndef AppVersion") + 1].startswith("#error ")
    assert pre[pre.index("#if VER < EncodeVer(6,3,0)") + 1].startswith("#error ")
    assert setup["ArchitecturesAllowed"] == setup["ArchitecturesInstallIn64BitMode"] == "x64compatible"
    # from the folder the zip step staged and zipped, written beside it, under the name the workflows look for
    stage = re.fullmatch(r'#define Stage "(.*)" \+ AppVersion \+ "(.*)"', next(p for p in pre if p.startswith("#define Stage ")))
    here, dist = INSTALLER.parent, ROOT / "editor" / "target" / "dist"
    staged = (stage.group(1) + version + stage.group(2)).replace("\\", "/")
    assert os.path.normpath(here / staged) == str(dist / f"camset-editor-{version}-windows-x64")
    zip_lines = step(yaml.safe_load(RELEASE.read_text(encoding="utf-8"))["jobs"]["build"], "Windows zip")["run"].splitlines()
    assert '$name = "camset-editor-$v-windows-x64"' in zip_lines and '$dir = "target/dist/$name"' in zip_lines
    assert os.path.normpath(here / setup["OutputDir"].replace("\\", "/")) == str(dist)
    assert setup["OutputBaseFilename"] == "camset-editor-{#AppVersion}-windows-x64-setup"
    made = next(ln for ln in INSTALLER_BUILD if ln.startswith("$setup = Get-Item "))
    assert f'"target/dist/{setup["OutputBaseFilename"].replace("{#AppVersion}", "$v")}.exe"' in made
    # the zip's four, in its layout: the program, the definitions (each with its sample) beside it, the licence and
    # the licences page, where the editor looks for them
    files = iss_entries("Files")
    assert [(f["Source"], f["DestDir"]) for f in files] == [
        ("{#Stage}\\camset_editor.exe", "{app}"),
        ("{#Stage}\\definitions\\*", "{app}\\definitions"),
        ("{#Stage}\\LICENSE.txt", "{app}"),
        ("{#Stage}\\THIRD_PARTY_LICENSES.html", "{app}"),
    ]
    assert all("ignoreversion" in f["Flags"].split() for f in files)
    assert {"recursesubdirs", "createallsubdirs"} <= set(files[1]["Flags"].split())
    assert {f["Source"].removeprefix("{#Stage}\\").split("\\")[0] for f in files} == zip_names(zip_lines)
    # the licence shown to read, with nothing to accept (MIT)
    assert setup["InfoBeforeFile"] == "{#Stage}\\LICENSE.txt" and "LicenseFile" not in setup


def test_the_installer_never_touches_the_users_files_nor_claims_anything():
    """Neither an upgrade nor the uninstaller removes or replaces the user's own files: the editor keeps them in its own
    folder (schema::config_dir: camset_editor in %APPDATA% on Windows, the definitions added beside the preferences),
    which the script never names. It writes only into the program's folder, and all it deletes are the built-in
    definitions there, files named as the shipped ones (never a folder: on the first install the user may choose one of
    their own), replaced as a set by each install; the uninstaller removes only what was installed.
    It claims no file types, starts nothing with Windows and holds no code (so it downloads and sends nothing); the
    editor starts only from the last page, ticked, and never after a silent install; the desktop shortcut is unticked."""
    s, setup = iss(), iss_setup()
    # no [Code], [Registry], [UninstallDelete], [UninstallRun], [Dirs] or [INI]
    assert set(s) == {"", "Setup", "Languages", "Tasks", "InstallDelete", "Files", "Icons", "Run"}
    # deleted before each install: only files named as the shipped definitions and their samples are, in the program's
    # definitions folder, never a folder (the user may have chosen a folder of their own on the first install)
    deletes = iss_entries("InstallDelete")
    assert deletes == [{"Type": "files", "Name": "{app}\\definitions\\*_fw*.json"}, {"Type": "files", "Name": "{app}\\definitions\\*_fw*.DAT"}]
    shipped = sorted(p.name for p in (ROOT / "editor" / "definitions").iterdir() if p.is_file())
    patterns = [d["Name"].removeprefix("{app}\\definitions\\") for d in deletes]
    assert shipped and all(any(fnmatch.fnmatchcase(n, p) for p in patterns) for n in shipped), shipped
    assert {n.rsplit(".", 1)[-1] for n in shipped} == {"json", "DAT"}, "as shipped, the case kept"
    assert all(f["DestDir"].split("\\")[0] == "{app}" for f in iss_entries("Files"))
    body = "\n".join(line for name, lines in s.items() if name for line in lines)
    # the only places named: the program's folder, its parent for this user, and the Start menu and desktop
    assert set(re.findall(r"\{(\w+)\}", body)) == {"app", "localappdata", "autoprograms", "autodesktop"}
    assert [line for line in s["Setup"] if "{localappdata}" in line] == ["DefaultDirName={localappdata}\\Programs\\Camset Editor"]
    assert not re.search(r"camset_editor(?!\.exe)|appdata%|\{app\}\\\.\.", body, re.I), "the editor's own folder, or out of the program's"
    assert not {"ChangesAssociations", "ChangesEnvironment", "AlwaysRestart", "RestartIfNeededByRun"} & set(setup)
    links = ("AppPublisherURL", "AppSupportURL", "AppUpdatesURL")
    assert not re.search(r"https?:", "\n".join(v for k, v in setup.items() if k not in links))
    assert not re.search(r"https?:|download", "\n".join(line for name in ("Files", "Icons", "Run", "Tasks") for line in s[name]), re.I)
    icons = iss_entries("Icons")
    assert [(i["Name"], i["Filename"], i.get("Tasks")) for i in icons] == [
        ("{autoprograms}\\Camset Editor", "{app}\\camset_editor.exe", None),
        ("{autodesktop}\\Camset Editor", "{app}\\camset_editor.exe", "desktopicon"),
    ]
    assert [(t["Name"], t["Flags"]) for t in iss_entries("Tasks")] == [("desktopicon", "unchecked")]
    run = iss_entries("Run")
    assert len(run) == 1 and run[0]["Filename"] == "{app}\\camset_editor.exe" and "Parameters" not in run[0]
    assert set(run[0]["Flags"].split()) == {"postinstall", "skipifsilent", "nowait"}


def test_the_installer_carries_version_details_the_workflows_check():
    """The installer file carries version details of its own (Properties > Details), as camset_editor.exe does, since a
    signing service asks for the product's name and version on every file it signs: the product Camset Editor (the
    program's product name, as DETAILS_CHECK checks it) at the program's version, as text and as numbers, both for the
    product and the file; the description Camset Editor Setup, so Task Manager tells it from the program; the publisher;
    and the copyright sentence, the first of the program's copyright detail, passed in from camset_editor.exe as the
    version is from Cargo.toml (the compile stops without either, or when either is longer than its slot), never
    written in the script. The workflows' lines check on the built file the very values the script sets, each trimmed
    of the spaces Inno Setup pads its slot with."""
    s, setup = iss(), iss_setup()
    assert setup["VersionInfoProductName"] == setup["AppName"] == "Camset Editor"
    assert "$info.ProductName -cne 'Camset Editor'" in DETAILS_CHECK[3]                 # the program's product name too
    versions = ("VersionInfoProductVersion", "VersionInfoProductTextVersion", "VersionInfoVersion", "VersionInfoTextVersion")
    assert [setup[k] for k in versions] == ["{#AppVersion}"] * 4
    assert setup["VersionInfoDescription"] == "Camset Editor Setup"
    assert setup["VersionInfoCompany"] == setup["AppPublisher"] == "Camset contributors"
    assert setup["VersionInfoCopyright"] == "{#AppCopyright}" and "AppCopyright" not in setup
    pre = s[""]
    assert pre[pre.index("#ifndef AppCopyright") + 1].startswith("#error ")
    assert pre[pre.index("#if Len(AppCopyright) > 100") + 1].startswith("#error ")
    assert pre[pre.index("#if Len(AppVersion) > 20") + 1].startswith("#error ")
    lines = "\n".join(line for part in s.values() for line in part)                 # the script without its comments
    assert not re.search(r"copyright \(c\)|\b20\d\d\b", lines, re.I), "the copyright is passed in, never written here"
    # the workflows' lines: the copyright sentence taken from the staged program and passed in, and on the built
    # installer each value the script sets, trimmed of its slot's padding, printed to the log, then checked with the
    # case kept
    assert INSTALLER_BUILD[:2] == ['$exe = Get-Item "target/dist/camset-editor-$v-windows-x64/camset_editor.exe"',
                                   "$copyright = ($exe.VersionInfo.LegalCopyright -split '(?<=\\.) ', 2)[0]"]
    call = next(ln for ln in INSTALLER_BUILD if ln.startswith("& $iscc "))
    assert '"/DAppCopyright=$copyright"' in call and '"/DAppVersion=$v"' in call
    want = {"ProductName": f"'{setup['VersionInfoProductName']}'", "ProductVersion": "$v", "FileVersion": "$v",
            "FileDescription": f"'{setup['VersionInfoDescription']}'", "CompanyName": f"'{setup['VersionInfoCompany']}'",
            "LegalCopyright": "$copyright"}
    assert INSTALLER_BUILD[-4] == "$info = [ordered]@{}"
    trimmed = re.fullmatch(r"foreach \(\$k in (.*)\) \{ \$info\[\$k\] = \"\$\(\$setup\.VersionInfo\.\$k\)\"\.TrimEnd\(\) \}", INSTALLER_BUILD[-3])
    assert trimmed and re.findall(r"'(\w+)'", trimmed.group(1)) == list(want), "every value trimmed, in the order printed"
    assert INSTALLER_BUILD[-2] == '"$($setup.Name): $($setup.Length) bytes; " + (($info.Keys | ForEach-Object { "$($_): $($info[$_])" }) -join \'; \')'
    check = INSTALLER_BUILD[-1]
    assert re.findall(r"\$info\.(\w+) -cne ('[^']*'|\$[\w.]+)", check) == list(want.items())
    assert check.startswith("if (") and check.count(" -or ") == len(want) - 1 and ") { throw " in check and check.endswith('" }')
    assert ".VersionInfo" not in check, "only the trimmed values are compared"


def test_the_installers_details_fit_inno_setups_slots():
    """Inno Setup writes each version detail into a slot of fixed width and cuts a longer text (INNO_SLOTS), so each
    one the installer carries fits its slot: the copyright sentence passed in (the first sentence of the program's
    copyright detail, as build.rs and resources.rs form it from LICENSE: the whole detail, with the words that the
    project is not Sony's, is longer than 100) at most 100 characters, which the script checks too; the product name,
    description and publisher at most 60; the version at most 20 (the script checks it); and the installer's file name,
    its OriginalFileName, at most 50 for a version as long as 10.20.30. Inno Setup also turns an uppercase "(C)" into
    the copyright sign, so LICENSE's line has the lowercase "(c)" the program's detail and the sentence keep."""
    setup = iss_setup()
    license_line = next(ln for ln in (ROOT / "LICENSE").read_text(encoding="utf-8").splitlines() if ln.lower().startswith("copyright"))
    assert "(C)" not in license_line and license_line.startswith("Copyright (c) ")
    # as resources.rs forms the program's detail: copyright_holders, then version_strings
    resources = (ROOT / "editor" / "packaging" / "windows" / "resources.rs").read_text(encoding="utf-8")
    assert 'l.strip_prefix("Copyright (c) ")' in resources and 'format!("Copyright (c) {h}. {NOT_SONY}")' in resources
    not_sony = re.search(r'^pub const NOT_SONY: &str = "(.*)";$', resources, re.M).group(1)
    holders = license_line.removeprefix("Copyright (c) ").strip()
    detail = f"Copyright (c) {holders}. {not_sony}"
    sentence = re.split(r"(?<=\.) ", detail, maxsplit=1)[0]                # the workflows' -split '(?<=\.) ', 2
    assert sentence == f"Copyright (c) {holders}." and len(sentence) <= INNO_SLOTS["LegalCopyright"] and "(C)" not in sentence
    for key, slot in (("VersionInfoProductName", "ProductName"), ("AppName", "ProductName"),
                      ("VersionInfoDescription", "FileDescription"), ("VersionInfoCompany", "CompanyName")):
        assert len(setup[key]) <= INNO_SLOTS[slot], key
    version = re.search(r'^version = "(.*)"$', (ROOT / "editor" / "Cargo.toml").read_text(encoding="utf-8"), re.M).group(1)
    for v in (version, "10.20.30"):
        assert len(v) <= INNO_SLOTS["FileVersion"] <= INNO_SLOTS["ProductVersion"]
        name = setup["OutputBaseFilename"].replace("{#AppVersion}", v) + ".exe"
        assert len(name) <= INNO_SLOTS["OriginalFileName"], name
    # the script refuses what would not fit, as wide as the slots
    pre = iss()[""]
    assert f"#if Len(AppCopyright) > {INNO_SLOTS['LegalCopyright']}" in pre and f"#if Len(AppVersion) > {INNO_SLOTS['FileVersion']}" in pre
    # and the workflows compare every detail trimmed of the padding
    loop = next(ln for ln in INSTALLER_BUILD if ln.startswith("foreach ($k in "))
    assert ".TrimEnd()" in loop and all(f"'{k}'" in loop for k in ("ProductName", "ProductVersion", "FileVersion", "FileDescription",
                                                                     "CompanyName", "LegalCopyright"))


def test_release_builds_the_windows_installer_from_the_zips_folder():
    """On Windows, right after the zip, the release builds the installer with Inno Setup from the folder the zip step
    staged (installer.iss reads it): ISCC.exe from its own folder or the PATH, the step stopping with a plain message
    when the runner has none (nothing is downloaded for it); the version passed in from Cargo.toml; a failed compile
    stops it; the installer checked to be there and of a program's size, and named in the log. The Windows artifact
    carries it and the release attaches it with the other packages."""
    wf = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
    build = wf["jobs"]["build"]
    names = [s.get("name") or "" for s in build["steps"]]
    inst = step(build, "Windows installer")
    assert inst["if"] == "runner.os == 'Windows'" and inst["shell"] == "pwsh"
    upload = next(i for i, s in enumerate(build["steps"]) if s.get("uses", "").startswith("actions/upload-artifact@"))
    assert names.index("Windows zip") + 1 == names.index(inst["name"]) < upload
    assert inst["run"].splitlines() == [DETAILS_CHECK[0], *INSTALLER_BUILD]
    assert not re.search(r"https?:|Invoke-WebRequest|\biwr\b|curl|wget|choco|winget|BitsTransfer", inst["run"], re.I)
    call = next(ln for ln in INSTALLER_BUILD if ln.startswith("& $iscc "))
    script = call.rsplit(" ", 1)[-1]                                                # the script ISCC is given, from editor/
    assert ROOT / "editor" / script.replace("\\", "/") == INSTALLER and INSTALLER.is_file()
    assert "editor/target/dist/*.exe" in build["steps"][upload]["with"]["path"].split()
    attach = next(s for s in wf["jobs"]["release"]["steps"] if s.get("uses", "").startswith("softprops/action-gh-release@"))
    assert "dist/*.exe" in attach["with"]["files"].split()


def test_editor_ci_compiles_the_windows_installer_as_the_release_builds_it():
    """Editor CI compiles the installer on Windows for every pull request and push to main, so a broken script or a
    runner without Inno Setup shows there, not on the day of a release: after the build and the program's details
    check, before the tests; from a folder staged as the release's zip step stages it (the licences page, which only
    the release writes, a stand-in); with the release's own lines; and what it made is removed after, so the build
    cache never holds it."""
    job = yaml.safe_load(EDITOR_CI.read_text(encoding="utf-8"))["jobs"]["editor"]
    names = [s.get("name") or "" for s in job["steps"]]
    ci = step(job, "Windows installer compiles")
    assert ci["if"] == "runner.os == 'Windows'" and ci["shell"] == "pwsh"
    assert names.index(step(job, "Windows program's version details")["name"]) < names.index(ci["name"]) < names.index("Test")
    lines = ci["run"].splitlines()
    assert lines[0] == DETAILS_CHECK[0] and lines[-1] == "Remove-Item -Recurse -Force target/dist"
    at = lines.index(INSTALLER_BUILD[0])
    assert lines[at:at + len(INSTALLER_BUILD)] == INSTALLER_BUILD and at + len(INSTALLER_BUILD) == len(lines) - 1
    staged = lines[1:at]
    release = step(yaml.safe_load(RELEASE.read_text(encoding="utf-8"))["jobs"]["build"], "Windows zip")["run"].splitlines()
    assert staged[0] == '$dir = "target/dist/camset-editor-$v-windows-x64"'
    folder = ("if (Test-Path $dir)", "New-Item")
    assert [ln for ln in staged if ln.startswith(folder)] == [ln for ln in release if ln.startswith(folder)]
    page = "Copy-Item target/dist/THIRD_PARTY_LICENSES.html $dir"
    assert [ln for ln in staged if ln.startswith("Copy-Item")] == [ln for ln in release if ln.startswith("Copy-Item") and ln != page]
    assert zip_names(staged) | {"THIRD_PARTY_LICENSES.html"} == zip_names(release)
    assert [ln for ln in staged if ln.startswith("Set-Content")] == [
        'Set-Content "$dir/THIRD_PARTY_LICENSES.html" "<!doctype html><title>Stand-in</title><p>The release writes this page with cargo about."']
