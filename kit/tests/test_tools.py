"""The kit's smaller tools (kit/tools/) that have no test file of their own, offline: what a chain leaves on the camera
at its end and after a step that left the camera unrestored, the reader reread_proofs.py asks, and score_screen.py's frames the OCR cannot read. No camera: a chain's steps here are this Python, and its end file a
made-up one, which upload_check.py refuses before any connection; no reader is asked anything.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from camkit import ROOT

CHAIN = ROOT / "kit" / "tools" / "chain.py"


def chain_file(tmp_path: Path, *steps: str) -> Path:
    c = tmp_path / "c.toml"
    py = Path(sys.executable).as_posix()
    c.write_text('name = "t"\n' + "".join(f'[[step]]\ntitle = "{s}"\nrun = ["{py}", "-c", "print(\'{s} RAN\')"]\n'
                                          for s in steps), encoding="utf-8")
    return c


def test_a_chains_end_file_named_from_here_is_the_one_uploaded(tmp_path):
    """--end names an existing file as it is given, relative to the folder the chain starts in; the end step used to
    take it for one in the camera's runs (or refuse it, written from runs/), so the owner's file was never put back
    after every step had run."""
    (tmp_path / "mine").mkdir()
    (tmp_path / "mine" / "owner.DAT").write_bytes(b"made up")
    r = subprocess.run([sys.executable, str(CHAIN), str(chain_file(tmp_path, "one")), "--end", "mine/owner.DAT",
                        "--stop", str(tmp_path / "STOP_CHAIN")], capture_output=True, text=True, timeout=120, cwd=tmp_path)
    assert "one RAN" in r.stdout and "== the end file: owner.DAT" in r.stdout
    # upload_check.py was given the file itself (and refused it: no camera wrote it)
    assert f"{(tmp_path / 'mine' / 'owner.DAT').resolve()}: not a camera download" in r.stdout


def exits(tmp_path: Path, status: int) -> Path:
    """A chain whose first step exits with status, and whose second says it ran."""
    c = tmp_path / f"exits{status}.toml"
    py = Path(sys.executable).as_posix()
    c.write_text(f'name = "t"\n[[step]]\ntitle = "first"\nrun = ["{py}", "-c", "import sys; sys.exit({status})"]\n'
                 f'[[step]]\ntitle = "next"\nrun = ["{py}", "-c", "print(\'NEXT RAN\')"]\n', encoding="utf-8")
    return c


def test_a_step_that_left_the_camera_unrestored_stops_the_chain(tmp_path):
    """Status 4 (EXIT_UNRESTORED, kit/exit_status.py): the camera may not be on the step's start file, so no next step
    changes anything else on it; any other failure is listed and the chain goes on (decision 15)."""
    run = [sys.executable, str(CHAIN), "--stop", str(tmp_path / "STOP_CHAIN")]
    r = subprocess.run(run[:2] + [str(exits(tmp_path, 4))] + run[2:], capture_output=True, text=True, timeout=60)
    assert "step 1 exited 4" in r.stdout and "may not be back on its start file" in r.stdout
    assert "NEXT RAN" not in r.stdout and "steps that failed: [1]" in r.stdout
    r = subprocess.run(run[:2] + [str(exits(tmp_path, 1))] + run[2:], capture_output=True, text=True, timeout=60)
    assert "step 1 exited 1" in r.stdout and "NEXT RAN" in r.stdout and "start file" not in r.stdout


def test_the_exit_status_is_kept_once_and_the_chain_takes_no_camera_code():
    """kit/exit_status.py holds EXIT_UNRESTORED for the runners (through kit/runner.py) and the chain, and imports
    nothing: the chain takes it without runner.py's camera code (its screen, frames and link)."""
    import ast
    tree = ast.parse((ROOT / "kit" / "exit_status.py").read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    code = ("import sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]; import chain, exit_status; "
            "assert chain.EXIT_UNRESTORED is exit_status.EXIT_UNRESTORED == 4; "
            "print(sorted(m for m in ('runner', 'camkit.screen', 'camkit.link', 'camkit.live') if m in sys.modules))")
    r = subprocess.run([sys.executable, "-c", code, str(ROOT / "kit" / "tools"), str(ROOT / "kit")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == "[]", r.stdout + r.stderr


def test_a_chain_without_its_end_file_does_not_start(tmp_path):
    r = subprocess.run([sys.executable, str(CHAIN), str(chain_file(tmp_path, "one")), "--end", str(tmp_path / "gone.DAT"),
                        "--stop", str(tmp_path / "STOP_CHAIN")], capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and "is not there" in r.stderr and "one RAN" not in r.stdout


def test_reread_proofs_gives_the_named_reader_the_second_role(monkeypatch):
    """--reader NAME: the configured reader of that name plays the "second" role for the process (camkit.vlm's
    assign_role, its public way; the tool used to write the module's private table)."""
    import reread_proofs
    from camkit import vlm
    readers = [{"name": "first", "url": "http://192.0.2.1/v1", "model": "m"},
               {"name": "local", "url": "http://127.0.0.1:8000/v1", "model": "m"}]
    monkeypatch.setattr(vlm, "config", lambda: {"readers": readers})
    monkeypatch.setattr(vlm, "_STANDING_IN", {})
    assert reread_proofs.use_reader("local") == "local" and vlm.playing("second")["name"] == "local"
    with pytest.raises(SystemExit, match="no reader of that name"):
        reread_proofs.use_reader("gone")


def test_score_screen_leaves_out_a_frame_the_ocr_cannot_read(monkeypatch):
    """camkit.ocr.read raises, naming the frame, when its helper cannot read one: score_screen reads the rest, one by
    one after the batch failed, and says which frame and why, never counting it as a frame with no text."""
    import score_screen
    asked = []

    def read(frames):
        asked.append(list(frames))
        if "bad.png" in frames:
            raise RuntimeError("the OCR helper could not read bad.png (unreadable image)")
        return {f: [] for f in frames}
    monkeypatch.setattr(score_screen.ocr, "read", read)
    got, failed = score_screen.ocr_each(["a.png", "bad.png", "b.png"])
    assert got == {"a.png": [], "b.png": []} and failed == {"bad.png": "the OCR helper could not read bad.png (unreadable image)"}
    assert asked == [["a.png", "bad.png", "b.png"], ["a.png"], ["bad.png"], ["b.png"]]
    assert score_screen.ocr_each(["a.png"]) == ({"a.png": []}, {})          # all read: one batch, as before


# ---------------------------------------------------------------- replay_proofs: a proof's own run

def test_replay_finds_a_proof_made_in_a_run_of_its_own(tmp_path):
    """replay_proofs.where: a proof recorded into kit2_pass2 by hand or through the SDK names its own run ("run":
    kit2_drive, kit2_sdk_ev), whose dat/ holds its files; the 89 such proofs were counted missing until 2026-11-08.
    Without a run the proof's files are in the run's dat/, else at its top; a name two runs share is the proof's
    own run's."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("replay_proofs", ROOT / "kit" / "tools" / "replay_proofs.py")
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    pass2, sdk = tmp_path / "kit2_pass2", tmp_path / "kit2_sdk_ev"
    for d in (pass2 / "dat", sdk / "dat"):
        d.mkdir(parents=True)
    for p in (pass2 / "dat" / "00002_base.DAT", sdk / "dat" / "00002_base.DAT", pass2 / "start.DAT"):
        p.write_bytes(b"x")
    assert R.where(pass2, "00002_base.DAT") == pass2 / "dat" / "00002_base.DAT"
    assert R.where(pass2, "00002_base.DAT", "kit2_sdk_ev") == sdk / "dat" / "00002_base.DAT", "the proof's own run first"
    assert R.where(pass2, "start.DAT", "kit2_sdk_ev") == pass2 / "start.DAT", "else the run's own, at its top"
    assert R.where(pass2, "gone.DAT", "kit2_sdk_ev") == sdk / "dat" / "gone.DAT", "missing: where it was looked for first"
    assert R.where(pass2, "00002_base.DAT", "kit2_pass2") == pass2 / "dat" / "00002_base.DAT"


# ---------------------------------------------------------------- the SDK prover (kit/provers/sdk_run.py), no camera

def sdk_run_module():
    import importlib.util
    sys.path.insert(0, str(ROOT / "kit"))
    spec = importlib.util.spec_from_file_location("sdk_run", ROOT / "kit" / "provers" / "sdk_run.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


EV_DOC = {"settings": [
    {"key": "global:0x0340", "name": "Exposure Comp.", "values": [[16, "-1.0 EV"], [19, "-0.3 EV"], [20, "+0.0 EV"],
                                                                   [21, "+0.3 EV"], [24, "+1.0 EV"], [18, "-0.5 EV"]],
     "proved": {"menu": ["Exposure Comp."], "values": [16, 20, 24]}},
    {"key": "global:0x0e16", "name": "Exposure Comp.", "values": [[16, "-1.0 EV"]], "proved": {"menu": ["Exposure Comp."]}}]}


def test_the_sdk_prover_plans_the_values_the_row_has_not_proved():
    """sdk_run.planned: "missing" is the row's own record's values its proofs have not covered, each as the SDK's EV x
    1000 (signed: -300, never 65236) with its label and code; "all" every value; a list the SDK's own values, named
    from the definition where it can. A property whose labels are no EV gives no plan from the definition."""
    S = sdk_run_module()
    assert S.sdk_value("ExposureBiasCompensation", "-0.3 EV") == -300 and S.sdk_value("FlashCompensation", "+4.7 EV") == 4700
    assert S.sdk_value("ExposureBiasCompensation", "±0.0 EV") == 0 and S.sdk_value("FNumber", "F5.6") is None
    assert [k["key"] for k in S.row_settings(EV_DOC, "Exposure Comp.")] == ["global:0x0340", "global:0x0e16"]
    missing = S.planned(EV_DOC, "ExposureBiasCompensation", "Exposure Comp.", "missing")
    assert missing == [(-300, "-0.3 EV", 19), (300, "+0.3 EV", 21), (-500, "-0.5 EV", 18)]
    assert len(S.planned(EV_DOC, "ExposureBiasCompensation", "Exposure Comp.", "all")) == 6
    assert S.planned(EV_DOC, "ExposureBiasCompensation", "Exposure Comp.", "-300,700") == [(-300, "-0.3 EV", 19),
                                                                                          (700, "+0.7 EV", None)]
    with pytest.raises(SystemExit):
        S.planned(EV_DOC, "ShutterSpeed", "Exposure Comp.", "missing")


class FakeSdkLink:
    """The link as sdk_run uses it: get, set, download and upload, each logged in order; the camera holds `current`.
    A refused set raises as Link._must does, the command in front ("set <name> <value>: <why>"); from the set numbered
    `stop_after` on, every set raises StopRequested, as a STOP file makes Link's guard do; `upload` may raise."""
    def __init__(self, offered, current, writable=True, refuse=(), stop_after=None, upload_error=None):
        self.offered, self.current, self.writable, self.refuse, self.log, self.n = offered, current, writable, refuse, [], 0
        self.stop_after, self.upload_error, self.sets = stop_after, upload_error, 0

    def get(self, name):
        self.log.append(("get", name))
        return {"current": self.current, "values": self.offered, "writable": self.writable}

    def set(self, name, value):
        from camkit.link import LinkError, StopRequested
        self.log.append(("set", value))
        self.sets += 1
        if self.stop_after is not None and self.sets > self.stop_after:
            raise StopRequested("STOP file")
        if value in self.refuse:
            raise LinkError(f"set {name} {value}: camera kept another value")
        self.current = value
        return {"ok": True, "current": value}

    def download(self, tag):
        self.n += 1
        self.log.append(("download", tag))
        return Path(f"{self.n:05d}_{tag}.DAT")

    def upload(self, path):
        self.log.append(("upload", path.name))
        if self.upload_error:
            raise self.upload_error
        return {"ok": True}


def test_the_sdk_prover_proves_each_value_puts_the_start_back_then_restores(monkeypatch, capsys):
    """sdk_run.prove with a fake link: the camera's answer first (its offered values and whether it takes a set,
    never its current value), the start download, each planned value it offers (set, read back, download, a proof
    line), a value it refuses a proof with applied false, the value held at the start set back last (its line
    "final"), then the session's restore (session.finish, listing no record). Nothing it does not offer is set, and the
    value held at the start is printed nowhere: only runs/ holds it (the final proof line, the link's own log). A
    planned value it equals has no line of its own, the set back proving it."""
    import io
    S = sdk_run_module()
    monkeypatch.setattr(S.camset, "read", lambda p: p)
    monkeypatch.setattr(S.camset, "diff", lambda a, b: [] if "back" in b.name else
                        [type("C", (), {"key": "global:0x0340", "before": 22, "after": int(b.name.split("n")[-1][:-4]) // 100 + 20})()])
    finished = []
    monkeypatch.setattr(S.session, "finish", lambda link, start, show=20: finished.append((start, list(link.log), show))
                        or "ending")
    plan = [(-300, "-0.3 EV", 19), (300, "+0.3 EV", 21), (-500, "-0.5 EV", 18), (500, "+0.5 EV", 22)]
    link = FakeSdkLink(offered=[-300, 0, 300, 500, 700], current=500, refuse=(300,))
    out = io.StringIO()
    ending, start = S.prove(link, "ExposureBiasCompensation", "Exposure Comp.", plan, out, plan)
    said = capsys.readouterr().out
    assert (ending, start.name) == ("ending", "00001_ExposureBiasCompensation-base.DAT")
    assert link.log[:2] == [("get", "ExposureBiasCompensation"), ("download", "ExposureBiasCompensation-base")]
    sets = [v for what, v in link.log if what == "set"]
    assert sets == [-300, 300, 500], "-0.5 EV is not offered now; the held +0.5 EV only as the start put back, last"
    assert finished and finished[0][1][-2:] == [("set", 500), ("download", "ExposureBiasCompensation-back")], \
        "the start's value set back, then the session's restore"
    assert finished[0][2] == 0, "the restore counts the records that differ and lists none"
    lines = [json.loads(x) for x in out.getvalue().splitlines()]
    assert [(r["label"], r["index"], r["applied"], r["final"]) for r in lines] == [
        ("-0.3 EV", 19, True, False), ("+0.3 EV", 21, False, False), ("+0.5 EV", 22, True, True)]
    assert lines[0] == {"path": ["Exposure Comp."], "kind": "list", "index": 19, "label": "-0.3 EV",
                        "via": "SDK ExposureBiasCompensation = -300", "dat": "00002_ExposureBiasCompensation-300.DAT",
                        "base": "00001_ExposureBiasCompensation-base.DAT", "changes": lines[0]["changes"],
                        "applied": True, "final": False}
    assert lines[-1]["changes"] == [] and lines[-1]["via"] == "SDK ExposureBiasCompensation = 500"
    assert "not offered now, left for another state: -0.5 EV" in said
    told = [ln for ln in said.splitlines() if "the camera offers" not in ln]       # the camera's list holds them all
    assert told and not [ln for ln in told if "+0.5" in ln or "500" in ln], f"the value held at the start printed: {told}"
    capsys.readouterr()
    shut = FakeSdkLink(offered=[0], current=0, writable=False)
    assert S.prove(shut, "FlashCompensation", "Flash Comp.", plan, io.StringIO(), plan) == (None, None)
    assert shut.log == [("get", "FlashCompensation")], "not writable: nothing downloaded or set"
    assert "flash on the shoe" in capsys.readouterr().out


def test_the_sdk_prover_prints_the_start_value_on_no_failure_path(monkeypatch, capsys):
    """sdk_run on the paths that stop it short, the session's real end (camkit.session.finish) run each time with a
    start file whose Exposure Comp. record (made-up stored value 4321) still differs: the camera refuses the set back
    (Link's error names the command, "set ExposureBiasCompensation 700"), a STOP file after the first value (every set
    refused from then, the set back too), and a restore whose upload fails (EXIT_UNRESTORED, runner.restoring). The
    value held at the start (SDK 700, "+0.7 EV", stored 4321) is in nothing printed: the records that differ are
    counted, not listed, and the refusals' words come without the command."""
    import io

    from camkit.link import LinkError
    S = sdk_run_module()
    monkeypatch.setattr(S.camset, "read", lambda p: p)
    monkeypatch.setattr(S.camset, "diff", lambda a, b: [])
    differs = [type("C", (), {"key": "global:0x0340", "before": 4321, "after": 4322})()]
    monkeypatch.setattr(S.session, "compared", lambda start, after, say=None: differs)
    plan = [(-300, "-0.3 EV", 19), (300, "+0.3 EV", 21)]
    labels = plan + [(700, "+0.7 EV", 23)]

    def said():
        got = capsys.readouterr()
        lines = [ln for ln in (got.out + got.err).splitlines() if "the camera offers" not in ln]   # every value
        assert lines and not [ln for ln in lines if any(w in ln for w in ("700", "+0.7", "4321"))], lines
        return "\n".join(lines)

    refused = FakeSdkLink(offered=[-300, 300, 700], current=700, refuse=(700,))
    ending, _ = S.prove(refused, "ExposureBiasCompensation", "Exposure Comp.", plan, io.StringIO(), labels)
    out = said()
    assert "the start's value was not set back (LinkError: camera kept another value)" in out
    assert ending.uploaded and "1 records differ from the start file" in out, "the restore's upload puts it back"
    stopped = FakeSdkLink(offered=[-300, 300, 700], current=700, stop_after=1)
    ending, _ = S.prove(stopped, "ExposureBiasCompensation", "Exposure Comp.", plan, io.StringIO(), labels)
    out = said()
    assert "stopped: StopRequested: STOP file" in out and "not set back (StopRequested: STOP file)" in out
    assert ending.uploaded, "the restore still runs after a STOP"
    broken = FakeSdkLink(offered=[-300, 300, 700], current=700, refuse=(700,),
                         upload_error=LinkError("upload: the camera did not answer"))
    with pytest.raises(SystemExit) as e:
        S.prove(broken, "ExposureBiasCompensation", "Exposure Comp.", plan, io.StringIO(), labels)
    assert e.value.code == S.EXIT_UNRESTORED, "a restore that raises stops a chain"
    assert "sdk_run's restore did not finish" in said()


def test_the_sdk_prover_exits_unrestored_when_its_restore_does_not_check_out(monkeypatch, tmp_path):
    """sdk_run.main's exit status, as kit/tools/chain.py reads it: 0 when the restore checked out, EXIT_UNRESTORED (a
    chain stops there, decision 15) when it did not or the camera refused the last download so nothing was restored,
    1 when the property was not writable and nothing was set. The restore's check lists no record (show=0)."""
    import contextlib
    import io

    import camkit.link
    S = sdk_run_module()
    doc = tmp_path / "definition.json"
    doc.write_text(json.dumps(EV_DOC), encoding="utf-8")
    monkeypatch.setattr(S.definitions, "active", lambda: doc)
    monkeypatch.setattr(S, "Run", lambda name: name)
    monkeypatch.setattr(S, "proofs_file", lambda run, context: contextlib.nullcontext(io.StringIO()))

    class NoLink:
        def __init__(self, run):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    monkeypatch.setattr(camkit.link, "Link", NoLink)
    args = ["--property", "ExposureBiasCompensation", "--row", "Exposure Comp."]
    checked, real = [], S.restore_checked
    monkeypatch.setattr(S, "prove", lambda *a: ("ending", Path("start.DAT")))
    for took, status in ((True, 0), (False, S.EXIT_UNRESTORED)):
        monkeypatch.setattr(S, "restore_checked", lambda run, ending, start, took=took, **kw: checked.append(kw) or took)
        assert S.main(args) == status
    assert checked == [{"show": 0}, {"show": 0}]
    monkeypatch.setattr(S, "restore_checked", real)
    monkeypatch.setattr(S, "prove", lambda *a: (S.session.Ending(None), Path("start.DAT")))
    assert S.main(args) == S.EXIT_UNRESTORED, "the last download refused: nothing restored"
    monkeypatch.setattr(S, "prove", lambda *a: (None, None))
    assert S.main(args) == 1, "not writable: nothing downloaded or set"


def test_an_sdk_refusal_is_no_menu_refusal_and_a_value_without_a_code_has_an_index_of_its_own(tmp_path):
    """A set the SDK's setter refused (sdk_run's proof: via "SDK ...", applied false) says nothing of the menu, so
    schema_update.blocked() leaves it out of what becomes menu_blocked, where a menu's refusal goes. A value the
    definition lacks is indexed "SDK <value>", which no code is, so pass2_report's latest proof per index keeps it
    beside the option whose code was its place in the run before."""
    import pass2_report as R
    import schema_update as SU
    S = sdk_run_module()
    base, dat = Path("00001_base.DAT"), Path("00002_x.DAT")
    lacking = S.proof_line("Exposure Comp.", None, "+0.7 EV", "ExposureBiasCompensation", 700, dat, base, [], False, False)
    coded = S.proof_line("Exposure Comp.", 0, "-5.0 EV", "ExposureBiasCompensation", -5000, dat, base, [], True, False)
    assert (lacking["index"], coded["index"]) == ("SDK 700", 0)
    run = tmp_path / "kit2_pass2"
    run.mkdir()
    menu = {"path": ["Color Mode"], "kind": "list", "index": 3, "label": "709", "applied": False,
            "notice": {"text": "Invalid with this gamma •OK"}}
    (run / "proofs.jsonl").write_text("".join(json.dumps(x) + "\n" for x in (menu, lacking, coded)), encoding="utf-8")
    got = SU.blocked(run)
    assert list(got) == ["Color Mode"] and [lab for lab, _ in got["Color Mode"]] == ["709"], dict(got)
    rows = R.rows_of(run, [lacking, coded])
    assert set(rows["Exposure Comp."]) == {"SDK 700", 0}


# ---------------------------------------------------------------- the AF Area Registration prover (kit/provers/afreg_run.py)

def afreg_module():
    import importlib.util
    sys.path.insert(0, str(ROOT / "kit"))
    sys.path.insert(1, str(ROOT / "kit" / "provers"))
    spec = importlib.util.spec_from_file_location("afreg_run", ROOT / "kit" / "provers" / "afreg_run.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def afreg_doc() -> dict:
    """A made-up definition with the REG table's names: three orientations, each its four records (keys and codes
    made up, the area record numbered unlike the camera's), the horizontal area proved at two codes, grip down's at one."""
    area = [[10, "Wide"], [11, "Zone"], [12, "Spot: L"], [13, "Spot: XS"], [14, "Custom 2"], [15, "Tracking: Wide"],
            [16, "Tracking: Spot S"]]
    kind = [[0, "Wide"], [1, "Zone"], [2, "Spot"], [3, "Custom"], [4, "Tracking"]]
    start, alt = [[0, "Wide"], [5, "Spot: S"]], [[0, "Wide"], [8, "Spot: S"]]
    settings = []
    for n, (o, proved) in enumerate((("horizontal", [10, 13]), ("vertical, grip down", [11]), ("vertical, grip up", []))):
        for m, (part, vals) in enumerate((("area", area), ("kind", kind), ("Tracking start area", start),
                                          ("Tracking start area, alt numbering", alt))):
            s = {"key": f"global:0x0{n}{m}0", "name": f"Registered AF area: {part} ({o})", "values": vals}
            if part == "area":
                s["proved"] = {"menu": ["AF Area Registration On, Fn held on the shooting screen"], "values": proved}
            settings.append(s)
    return {"settings": settings}


def test_the_afreg_prover_plans_each_area_and_the_codes_its_hold_must_write():
    """afreg_run.plan: "missing" is the area record's values its proofs have not covered, in its order; each area's
    hold must write its code into every orientation's area record (Switch V/H AF Area Off: one hold writes all three),
    its kind into the kind records, and, a Tracking area only, its start area in both numberings ("Tracking: Spot S" is
    the start records' "Spot: S"). A label is matched without case, spaces or colons; one not offered stops the plan."""
    A = afreg_module()
    doc = afreg_doc()
    missing = A.plan(doc, "missing")
    assert [(t["label"], t["code"]) for t in missing] == [("Zone", 11), ("Spot: L", 12), ("Custom 2", 14),
                                                           ("Tracking: Wide", 15), ("Tracking: Spot S", 16)]
    by = {t["label"]: t for t in A.plan(doc, "all")}
    assert len(by) == 7 and all(t["own_key"] == "global:0x0000" for t in by.values())
    assert by["Spot: L"]["expected"] == {"global:0x0000": 12, "global:0x0010": 2, "global:0x0100": 12,
                                          "global:0x0110": 2, "global:0x0200": 12, "global:0x0210": 2}
    assert by["Custom 2"]["expected"]["global:0x0010"] == 3, "Custom N is the kind Custom"
    tr = by["Tracking: Spot S"]["expected"]
    assert (tr["global:0x0000"], tr["global:0x0010"], tr["global:0x0020"], tr["global:0x0030"]) == (16, 4, 5, 8)
    assert tr["global:0x0220"] == 5 and tr["global:0x0230"] == 8 and len(tr) == 12
    assert [t["label"] for t in A.plan(doc, "tracking spot s, Spot: L")] == ["Spot: L", "Tracking: Spot S"]
    with pytest.raises(SystemExit):
        A.plan(doc, "Spot: XXL")
    # the camera held grip down (Switch V/H AF Area = AF Point + AF Area): that orientation's records alone, and its
    # own area record's proofs say what is missing
    down = A.plan(doc, "missing", "down")
    assert "Zone" not in [t["label"] for t in down] and "Wide" in [t["label"] for t in down]
    assert down[0]["own_key"] == "global:0x0100" and set(down[0]["expected"]) == {"global:0x0100", "global:0x0110"}
    assert down[0]["other_area_keys"] == ["global:0x0000", "global:0x0200"]
    assert A.context_of(None, None) == "Switch V/H AF Area Off"
    assert A.context_of("up", "Movie mode") == "Switch V/H AF Area = AF Point + AF Area, camera grip up, Movie mode"
    assert A.setup_rows(None, True) == [(["Focus Mode"], "Continuous AF"), (["AF Area Registration"], "On"),
                                        (["Switch V/H AF Area"], "Off")]
    assert A.setup_rows("down", False)[-1] == (["Switch V/H AF Area"], "AF Point + AF Area")
    # the setup: the Drive Mode Dial and Drive Mode = Single Shooting come before the Focus Mode Dial and Focus Mode
    assert A.setup_steps(None, True, True) == [
        ("dial", "Drive Mode Dial"), ("drive", "Drive Mode = Single Shooting"), ("dial", "Focus Mode Dial"),
        ("row", "Focus Mode = Continuous AF"), ("row", "AF Area Registration = On"), ("row", "Switch V/H AF Area = Off")]
    assert [k for k, _ in A.setup_steps(None, True, False)][:2] == ["dial", "row"]
    assert A.setup_steps(None, False, False) == [("row", "AF Area Registration = On"), ("row", "Switch V/H AF Area = Off")]
    assert A.step_name("dial", "Drive Mode Dial") == "Mode Dial Control Set / Drive Mode Dial = Set with Menu"
    assert A.step_name("drive", "Drive Mode = Single Shooting") == "Drive Mode = Single Shooting"


def test_the_afreg_list_shows_the_drive_steps_when_tracking_is_planned_and_leave_skips_them(capsys, monkeypatch):
    """--list prints the setup without a camera: Tracking areas bring the drive steps (auto), --drive-mode leave
    skips them, menu forces them for a plan without Tracking."""
    A = afreg_module()
    monkeypatch.setattr(A, "read_json", lambda path: {})
    monkeypatch.setattr(A.definitions, "active", lambda *a, **k: "none.json")
    monkeypatch.setattr(A, "plan", lambda doc, areas, grip=None: [
        {"label": areas, "code": 1, "expected": {"global:0x0100": 1}}])

    def listed(*argv):
        A.main(["--list", *argv])
        return capsys.readouterr().out.split("set through the menu first:")[-1]

    tracking = listed("--areas", "Tracking: Wide")
    assert "Drive Mode Dial = Set with Menu; Drive Mode = Single Shooting; " in tracking
    assert tracking.index("Drive Mode = Single Shooting") < tracking.index("Focus Mode Dial")
    assert "Drive Mode" not in listed("--areas", "Tracking: Wide", "--drive-mode", "leave")
    assert "Drive Mode" not in listed("--areas", "Wide")
    assert "Drive Mode = Single Shooting" in listed("--areas", "Wide", "--drive-mode", "menu")


def test_the_afreg_prover_orders_judges_and_credits_only_what_the_area_writes():
    """An area the registration holds already is registered last (alone: after another, non-Tracking, area), since its
    hold could show no change. A line is applied only when the plan's own area record moved to the area's code and every
    expected record holds its code; a hold that changed nothing never is. A record the area does not write is a side
    effect, by key only: one that changed, and the start area copies a non-Tracking area's hold makes from the live
    Tracking start area, changed or not (the report credits a side effect to no area). --proved credits the expected
    codes of applied lines alone."""
    A = afreg_module()
    doc = afreg_doc()
    every = A.plan(doc, "all")
    by = {t["label"]: t for t in every}
    todo = [by["Zone"], by["Spot: L"]]
    assert [t["label"] for t in A.ordered(todo, 11, every)] == ["Spot: L", "Zone"]
    assert [t["label"] for t in A.ordered(todo, 12, every)] == ["Zone", "Spot: L"]
    assert [t["label"] for t in A.ordered([by["Wide"]], 10, every)] == ["Zone", "Wide"]
    t = by["Spot: L"]
    copies = ["global:0x0020", "global:0x0030", "global:0x0120", "global:0x0130", "global:0x0220", "global:0x0230"]
    assert t["copied"] == copies and not set(copies) & set(t["expected"]), "every orientation's start copies"
    assert by["Tracking: Spot S"]["copied"] == [], "a Tracking area writes its own start area"
    moved = [{"key": k, "before": 0, "after": v} for k, v in t["expected"].items() if k.endswith("00")]
    moved.append({"key": "global:0x0020", "before": 0, "after": 5})          # the live Tracking start, copied
    moved.append({"key": "global:0x0500", "before": 0, "after": 1})          # a record the plan knows nothing of
    credited, side, applied, why = A.judge(t, moved, dict(t["expected"]))
    assert applied and why is None and side == copies + ["global:0x0500"] and len(credited) == 3
    assert A.judge(t, moved[:3], dict(t["expected"]))[1] == copies, "the copies named though none changed"
    assert A.judge(t, [], dict(t["expected"]))[2:] == (False, "nothing changed: the hold registered nothing")
    wrong = dict(t["expected"], **{"global:0x0110": 0})
    assert "global:0x0110" in A.judge(t, moved, wrong)[3]
    down = A.plan(doc, "Spot: L", "down")[0]
    other = [{"key": "global:0x0200", "before": 0, "after": 12}]             # grip up's copy moved, not grip down's
    _, _, applied, why = A.judge(down, other, {})
    assert not applied and "global:0x0200 did" in why
    line = A.proof_line(t, {"shown": "Spot: L", "vlm": "Spot: L", "chosen_frame": "1.png", "row_frame": "2.png"},
                        {"frames": ["3.png", "4.png"], "said": "Registered the focus area."}, Path("5_before.DAT"),
                        Path("6_after.DAT"), moved, dict(t["expected"]), None, ["AF Area Registration = On"])
    assert line["path"] == [A.MENU] and line["kind"] == "list" and line["index"] == 12 and line["applied"] is True
    assert line["side_effects"] == copies + ["global:0x0500"] and "not_applied" not in line
    refused = dict(line, label="Zone", applied=False, expected=[{"key": "global:0x0000", "value": 11}])
    assert A.proved_codes([line, refused]) == {k: [v] for k, v in sorted(t["expected"].items())}


def test_the_afreg_proof_says_when_the_strips_lit_cell_read_the_area():
    """An area whose axis value the strip's lit cell read (its title named none: Custom 3's box over the title,
    2026-11-09) carries how in its proof line ("read_by": "axis cell", with the cell readings), beside the title's and
    the vision model's readings; one read by its title carries neither."""
    A = afreg_module()
    t = {"label": "Custom 3", "code": 14, "expected": {"global:0x0000": 14}, "own_key": "global:0x0000"}
    got = {"shown": "Customß 7", "vlm": "", "chosen_frame": "1.png", "row_frame": "2.png", "read_by": "axis cell",
           "cell_readings": [{"reader": "apple", "text": "C2", "offset": -1}]}
    args = ({"frames": ["3.png", "4.png"], "said": ""}, Path("5_before.DAT"), Path("6_after.DAT"),
            [{"key": "global:0x0000", "before": 0, "after": 14}], {"global:0x0000": 14}, None, [])
    line = A.proof_line(t, got, *args)
    assert line["read_by"] == "axis cell" and line["cell_readings"] == got["cell_readings"] and line["applied"]
    assert (line["shown"], line["vlm"]) == ("Customß 7", ""), "the title's and the vision model's readings kept beside it"
    plain = A.proof_line(t, {k: got[k] for k in ("shown", "vlm", "chosen_frame", "row_frame")}, *args)
    assert "read_by" not in plain and "cell_readings" not in plain


def test_the_carousel_option_is_known_from_a_title_the_frames_corner_overdrew():
    """afreg_run.main_of: the Custom 3 box's corner over the carousel's title leaves "Customß 7" (kit2_framepos
    01244_reread.png, 2026-11-09), which names no value, so the one option whose axis values all begin "custom" is the
    Custom option; a reading of the lit cell alone ("C3") names nothing, since Tracking has Custom cells too; a size
    garbled after the colon still finds its option; an empty reading is no option."""
    A = afreg_module()
    labels = ["Wide", "Zone", "Spot: M", "Expand Spot", "Custom 1", "Tracking: Spot XL"]
    axes = {"Spot": {"values": ["Spot: XS", "Spot: S", "Spot: M", "Spot: L", "Spot: XL"]},
            "Custom 1": {"values": ["Custom 1", "Custom 2", "Custom 3"]},
            "Tracking": {"values": ["Tracking: Wide", "Tracking: Zone", "Tracking: Spot XL", "Tracking: Spot M",
                                    "Tracking: Expand Spot", "Tracking: Custom 1", "Tracking: Custom 3"]}}
    assert A.main_of("Customß 7", labels, axes) == 4
    assert A.main_of("Custom 3", labels, axes) == 4 and A.main_of("Custom 3 7", labels, axes) == 4
    assert A.main_of("C3", labels, axes) is None
    assert A.main_of("Spot: XI", labels, axes) == 2 and A.main_of("Tracking: Spot ?", labels, axes) == 5
    assert A.main_of("Expand Spot", labels, axes) == 3 and A.main_of("", labels, axes) is None
    # the same corner over a Tracking box's title: the Tracking option, never Custom's; a lead garbled too is no option
    assert A.main_of("Tracking: Customß 7", labels, axes) == 5 and A.main_of("Tracking: Customß", labels, axes) == 5
    assert A.main_of("Trackinq: Customß 7", labels, axes) is None


def test_a_setup_notice_is_kept_in_the_run_and_never_printed(capsys, monkeypatch):
    """afreg_run's setup (also framepos_run's): a notice after a row's OK can name another setting's value, the camera's
    own (docs/decisions/0016), so its words go to the run's events.jsonl only; a "not available as follows" notice is
    closed with its OK and fails the step, the message naming the step and the frame, but one that reads like a
    confirmation gets no Enter (camkit.safety); set_row's lit option ("(on '...')") is scrubbed from a failure. Drive
    Mode's notice: the test after this one."""
    from types import SimpleNamespace
    A = afreg_module()
    import mode_switch
    from prove_run import Failed
    words = "This operation or setting not available as follows: Made-up Row: Made-up Value"
    logged = []

    class Cam:
        frame = SimpleNamespace(path=Path("00042_enter.png"))
        run = SimpleNamespace(log=lambda kind, **f: logged.append((kind, f)))
        pressed = []

        def press(self, key):
            self.pressed.append(key)

        def read(self):
            return SimpleNamespace(kind="notice")
    cam = Cam()
    monkeypatch.setattr(mode_switch, "text", lambda c: words)
    said = []
    watch = A.refused_by_notice(cam, said.append, "Focus Mode = Continuous AF")
    watch("Focus Mode: choosing 'Continuous AF'")
    with pytest.raises(Failed) as got:
        watch(f"   notice after OK: {words!r}")
    assert "Made-up" not in str(got.value) and "Focus Mode = Continuous AF" in str(got.value) and "00042" in str(got.value)
    assert said == ["Focus Mode: choosing 'Continuous AF'"] and cam.pressed == ["enter"]
    assert logged == [("setup_notice", {"step": "Focus Mode = Continuous AF", "frame": "00042_enter.png", "notice": words})]
    monkeypatch.setattr(mode_switch, "text", lambda c: "Made-up information")
    A.refused_by_notice(cam, said.append, "X = Y")("   notice after OK: 'Made-up information'")
    assert "Made-up" not in said[-1] and "events.jsonl" in said[-1] and logged[-1][1]["notice"] == "Made-up information"
    asks = "Execute? This operation or setting not available as follows: Made-up Row: Made-up Value"
    monkeypatch.setattr(mode_switch, "text", lambda c: asks)
    cam.pressed.clear()
    with pytest.raises(Failed, match="reads like a confirmation") as got:
        A.refused_by_notice(cam, said.append, "X = Y")(f"   notice after OK: {asks!r}")
    assert cam.pressed == [] and "Made-up" not in str(got.value), "no Enter on a confirmation"
    assert A.scrub("'X': 'Y' did not come round in its list (on 'Held')") == "'X': 'Y' did not come round in its list"
    monkeypatch.setattr(mode_switch, "set_row", lambda *a: (_ for _ in ()).throw(Failed("'X': 'Y' did not come round (on 'Held')")))
    with pytest.raises(Failed, match=r"did not come round$"):
        A.set_setup_row(cam, None, None, ["X"], "Y")
    assert "Made-up" not in capsys.readouterr().out


def test_a_notice_after_an_areas_ok_is_kept_in_the_run_and_never_in_the_message(monkeypatch):
    """afreg_run.choose_area (framepos_run's too): a notice after Focus Area's OK can name the setting that blocks it
    and its value, the camera's own, so its words go to the run's events.jsonl and the failure, which framepos_run also
    stores in framepos.jsonl, names the area and the frame only. A made-up camera."""
    from types import SimpleNamespace
    A = afreg_module()
    import camkit.ocr
    import proving.screens
    from prove_run import Failed
    words = "This operation or setting not available as follows: Made-up Row: Made-up Value"
    logged = []

    class Cam:
        def __init__(self):
            self.kind, self.n, self.pressed = "dialog", 0, []
            self.run = SimpleNamespace(log=lambda kind, **f: logged.append((kind, f)))

        @property
        def frame(self):
            return SimpleNamespace(path=Path(f"{self.n:05d}_x.png"))

        def read(self):
            return SimpleNamespace(kind=self.kind)

        def press(self, key):
            self.pressed.append(key)
            self.n += 1
            self.kind = "notice" if self.kind == "dialog" else "menu"
    cam = Cam()
    monkeypatch.setattr(A, "choose_level", lambda *a: {})
    monkeypatch.setattr(proving.screens, "carousel_text", lambda c: "Spot")
    monkeypatch.setattr(proving.screens, "vlm_option", lambda c: "Spot: S")
    monkeypatch.setattr(camkit.ocr, "read", lambda paths: {p: None for p in paths})
    monkeypatch.setattr(camkit.ocr, "text_in", lambda r, box: words if cam.kind == "notice" else "Focus Area Spot: S")
    axes = {"Spot": {"values": ["Spot: XS", "Spot: S"]}}
    with pytest.raises(Failed, match="a notice refused Focus Area = Spot: S") as got:
        A.choose_area(cam, None, None, None, ["Wide", "Spot"], axes, (1, "Spot", 1), None)
    assert "Made-up" not in str(got.value) and "00001_x.png" in str(got.value) and cam.pressed == ["enter", "menu"]
    assert logged == [("area_notice", {"step": "Focus Area = Spot: S", "frame": "00001_x.png", "notice": words})]


@pytest.mark.parametrize("words,confirms", [
    ("This operation or setting not available as follows: Made-up Row: Made-up Value", False),
    ("Execute? Made-up Row: Made-up Value", True)])
def test_drive_modes_notice_is_kept_in_the_run_and_never_entered_when_it_confirms(words, confirms, capsys, monkeypatch):
    """afreg_run.drive_single: OK on Single Shooting answered by a notice keeps the notice's words in the run's
    events.jsonl and fails naming the step and the frame, never the words; the notice is closed with its OK, unless it
    reads like a confirmation, which gets no Enter. A made-up camera and map."""
    from types import SimpleNamespace
    A = afreg_module()
    import camkit.ocr
    import mode_switch
    import pass3_run
    import proving.screens
    from prove_run import Failed
    logged = []

    class Cam:
        def __init__(self):
            self.kind, self.pressed, self.n = "menu", [], 0
            self.run = SimpleNamespace(log=lambda kind, **f: logged.append((kind, f)))

        @property
        def frame(self):
            return SimpleNamespace(path=Path(f"{self.n:05d}_x.png"))

        def read(self):
            return SimpleNamespace(kind=self.kind)

        def press(self, key):
            self.pressed.append(key)
            self.n += 1
            self.kind = {"menu": "dialog", "dialog": "notice"}.get(self.kind, "menu")

        def refresh(self, tag):
            self.n += 1
    cam = Cam()
    monkeypatch.setattr(pass3_run, "labels_of", lambda path: (["Single Shooting", "Cont. Shooting: Hi"], "dialog"))
    monkeypatch.setattr(mode_switch, "find", lambda *a: None)
    monkeypatch.setattr(mode_switch, "text", lambda c: words if c.kind == "notice" else "Drive Mode Single Shooting")
    monkeypatch.setattr(camkit.ocr, "read", lambda paths: {p: None for p in paths})
    monkeypatch.setattr(camkit.ocr, "text_in", lambda r, box: "Drive Mode")
    monkeypatch.setattr(proving.screens, "carousel_text", lambda c: "Single Shooting")
    monkeypatch.setattr(A.time, "sleep", lambda s: None)
    with pytest.raises(Failed, match="reads like a confirmation" if confirms else "a notice refused Drive Mode") as got:
        A.drive_single(cam, None, None)
    assert "Made-up" not in str(got.value) and "00003_x.png" in str(got.value)
    assert cam.pressed == ["enter", "enter"] + ([] if confirms else ["enter"])
    assert logged == [("setup_notice", {"step": "Drive Mode = Single Shooting", "frame": "00003_x.png", "notice": words})]
    assert "Made-up" not in capsys.readouterr().out


def test_replay_tells_a_shared_download_from_a_proof_that_differs(tmp_path):
    """replay_proofs: two proofs of one download (Time Code Preset's fields, proved by hand), each storing only its own
    field's record, share it: today's diff holds both records, and each proof's extra record is the other's, as it
    stored it. A proof whose extra record no proof of its download stored still differs."""
    import importlib.util

    from camkit import camset
    spec = importlib.util.spec_from_file_location("replay_proofs", ROOT / "kit" / "tools" / "replay_proofs.py")
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    sample = ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"
    cs = camset.read(sample)
    run = tmp_path / "kit2_pass2"
    (run / "dat").mkdir(parents=True)
    (run / "dat" / "00001_base.DAT").write_bytes(sample.read_bytes())
    a, b = cs.get(0, 0x0489), cs.get(0, 0x0350)
    two = {(0, 0x0489): bytes([(a.raw[0] + 1) % 4]) + a.raw[1:], (0, 0x0350): bytes([(b.raw[0] + 1) % 3]) + b.raw[1:]}
    for name in ("00002_both.DAT", "00003_both.DAT"):
        (run / "dat" / name).write_bytes(camset.with_values(cs, two))
    now = {c.key: c for c in camset.diff(cs, camset.read(run / "dat" / "00002_both.DAT"))}
    change = lambda k: {"key": k, "before": now[k].before, "after": now[k].after}
    proof = lambda dat, keys, label: {"path": ["Time Code Preset"], "label": label, "base": "00001_base.DAT", "dat": dat,
                                      "changes": [change(k) for k in keys]}
    lines = [proof("00002_both.DAT", ["global:0x0489"], "01"), proof("00002_both.DAT", ["global:0x0350"], "02"),
             proof("00003_both.DAT", ["global:0x0489"], "03")]
    (run / "proofs.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    differing, shared, missing, unfiled, checked = R.replay(run)
    assert [(p["label"], extra) for p, extra in shared] == [("01", ["global:0x0350"]), ("02", ["global:0x0489"])]
    assert [(p["label"], only_now) for p, _, only_now, _ in differing] == [("03", ["global:0x0350"])]
    assert (missing, unfiled, checked) == ([], 0, 3)


# ---------------------------------------------------------------- the owner's word, per run, for the provers' own rows

def test_the_fn_hold_needs_the_owners_word(monkeypatch):
    """afreg_run holds Fn on the shooting screen, where the body does whatever its owner assigned to it (decision 21):
    a camera run starts only with --allow "Fn hold on the shooting screen" and no other --allow, and its proof lines
    carry the allowance; --list needs none."""
    from pathlib import Path as P
    A = afreg_module()
    monkeypatch.setattr(A, "read_json", lambda p: afreg_doc())
    monkeypatch.setattr(A.definitions, "active", lambda required=True: P("made-up.json"))
    monkeypatch.setattr(A, "prove", lambda a, doc, todo, focus, drive, context, allowance="": allowance)
    for extra, said in (([], "only with the owner's word"), (["--allow", "Camera Set. Memory"], "only with the owner's word"),
                        (["--allow", A.FN_HOLD, "--allow", "Format"], "allowed nothing but")):
        with pytest.raises(SystemExit, match=said):
            A.main(["--areas", "Spot: L", *extra])
    assert A.main(["--areas", "Spot: L", "--list"]) == 0
    got = A.main(["--areas", "Spot: L", "--allow", "FN HOLD on the  shooting screen"])
    assert got.startswith("the owner allowed FN HOLD on the  shooting screen remotely, ")


def test_the_fn_hold_is_named_for_the_shooting_screen_and_held_only_when_allowed(monkeypatch):
    from pathlib import Path as P
    from types import SimpleNamespace
    A = afreg_module()
    from camkit import live
    from prove_run import Failed
    pressed = []
    cam = SimpleNamespace(read=lambda: SimpleNamespace(kind="shooting"), frame=SimpleNamespace(path=P("00001_x.png")),
                          press=lambda key, **kw: pressed.append((key, kw)))
    monkeypatch.setattr(live, "text_of", lambda c: "Registered the focus area.")
    with pytest.raises(Failed, match="owner's word"):
        A.hold_fn(cam, None, None)
    assert pressed == []
    got = A.hold_fn(cam, None, None, allowed=True)
    assert pressed == [("fn", {"allow": frozenset({"fn"}), "hold_ms": A.HOLD_MS, "on_shooting": frozenset({"fn"})})]
    assert got["said"] == "Registered the focus area."


def prover(name: str):
    sys.path.insert(0, str(ROOT / "kit"))
    sys.path.insert(1, str(ROOT / "kit" / "provers"))
    import importlib
    return importlib.import_module(name)


@pytest.mark.parametrize("name,argv", [("customshoot_run", ["--hold", "1"]),
                                       ("customshoot_values", ["--hold", "1", "--items", "Shoot Mode"])])
def test_the_recall_custom_provers_open_their_row_only_with_the_owners_word(monkeypatch, name, argv):
    M = prover(name)
    for extra, said in (([], "only with the owner's word"), (["--allow", "Camera Set. Memory"], "only with the owner's word"),
                        (["--allow", "Reg. Custom Shoot Set", "--allow", "Add Item"], "opens no never-open row but"),
                        (["--allow", "Reg. Custom Shoot Set", "--allow", "Initialize"], "opens no never-open row but")):
        monkeypatch.setattr(sys, "argv", [name, *argv, *extra])
        with pytest.raises(SystemExit, match=said):
            M.main()
    monkeypatch.setattr(M, "load_scan", lambda scan: (_ for _ in ()).throw(RuntimeError("past the allowance")))
    monkeypatch.setattr(sys, "argv", [name, *argv, "--allow", "reg. custom shoot set"])
    with pytest.raises(RuntimeError, match="past the allowance"):
        M.main()


def test_my_menu_opens_add_item_only_with_the_owners_word(monkeypatch):
    M = prover("mymenu_run")
    from camkit import definitions
    for argv, said in (([], "only with the owner's word"), (["--lap-only"], "only with the owner's word"),
                       (["--allow", "Add Item", "--allow", "Format"], "opens no never-open row but")):
        monkeypatch.setattr(sys, "argv", ["mymenu_run", *argv])
        with pytest.raises(SystemExit, match=said):
            M.main()
    monkeypatch.setattr(definitions, "active", lambda required=True: (_ for _ in ()).throw(RuntimeError("past it")))
    for argv in (["--allow", "Add Item"], ["--relabel"]):              # --relabel touches no camera and needs none
        monkeypatch.setattr(sys, "argv", ["mymenu_run", *argv])
        with pytest.raises(RuntimeError, match="past it"):
            M.main()


# ---------------------------------------------------------------- card_actions.py: drive.py's judging, the runners' end

CARDS = ROOT / "kit" / "tools" / "card_actions.py"


@pytest.mark.parametrize("args,said", [
    (["peek", "Create New Folder"], "only with the owner's word"),
    (["peek", "Create New Folder", "--allow", "Select REC Folder"], "only with the owner's word"),
    (["peek", "Create New Folder", "--allow", "Create New Folder", "--allow", "Recover Image DB"], "no never-open row but"),
    (["run", "Create New Folder", "--allow", "Create New Folder", "--press", "enter"], "Enter needs a regex"),
    (["run", "Create New Folder", "--allow", "Create New Folder", "--press", "help"], "menu keys only"),
    (["run", "Create New Folder", "--allow", "Create New Folder", "--press", "down@200"], "menu keys only"),
    (["run", "Create New Folder", "--allow", "Create New Folder", "--press", "enter!:Folder"], "menu keys only"),
    (["run", "Create New Folder", "--allow", "Create New Folder", "--press", "dial.front.1:Folder"], "menu keys only"),
    (["run", "Create New Folder", "--allow", "Create New Folder", "--press", "movie"], "not a key"),
    (["run", "Format", "--allow", "Format", "--press", "right"], "not a card action")])
def test_card_actions_refuses_before_anything_connects(args, said):
    r = subprocess.run([sys.executable, str(CARDS), *args], capture_output=True, text=True, timeout=60)
    assert r.returncode != 0 and said in r.stderr


def cards_module():
    import importlib.util
    sys.path.insert(0, str(ROOT / "kit"))
    spec = importlib.util.spec_from_file_location("card_actions", CARDS)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def cards_world(tmp_path, monkeypatch, restored=True):
    """card_actions.main() made up around: a body that fails (a screen the scan did not record), the session's end and
    the restore's check recorded in the calls returned with the module and the run."""
    from types import SimpleNamespace
    from camkit import session
    from camkit.runs import Run
    C = cards_module()
    calls = []
    run = Run("kit2_cards", root=tmp_path)

    class Link:
        def __init__(self, r):
            self.run = r

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def press(self, *a, **k):
            calls.append(("press", a, k))

        def download(self, tag):
            return tmp_path / f"{tag}.DAT"
    eyes = SimpleNamespace(attach=lambda link: None, grab=lambda save=False: None, close=lambda: calls.append("eyes closed"))
    ending = session.Ending(tmp_path / "after.DAT", [SimpleNamespace(key="global:0x0001", before=0, after=1)], True)
    for name, value in (("check_readers", lambda: None), ("Link", Link), ("Run", lambda name: run),
                        ("eyes_from_config", lambda r: eyes),
                        ("load_scan", lambda scan: ([], {})), ("wait_for", lambda *a, **k: None),
                        ("screen", SimpleNamespace(read=lambda f: SimpleNamespace(kind="shooting"))),
                        ("time", SimpleNamespace(sleep=lambda s: None)),
                        ("LiveCamera", lambda link, eyes, run, may_open=(): calls.append(("may_open", set(may_open)))
                         or SimpleNamespace()),
                        ("to_row", lambda *a: (_ for _ in ()).throw(RuntimeError("a screen the scan did not record"))),
                        ("close_for_restore", lambda cam, link: calls.append("closed")),
                        ("end_session", lambda link, eyes, start, why, reach=None, show=None:
                         calls.append(("end", start.name, reach)) or ending),
                        ("restore_checked", lambda r, e, start: calls.append("checked") or restored)):
        monkeypatch.setattr(C, name, value)
    monkeypatch.setattr(sys, "argv", ["card_actions.py", "peek", "Create New Folder", "--allow", "Create New Folder"])
    return C, calls, run


@pytest.mark.parametrize("restored", [True, False])
def test_card_actions_ends_on_the_runners_path(tmp_path, monkeypatch, restored):
    """A body that fails (a screen the scan did not record) is said; the camera is closed with cleanup presses
    (close_for_restore), the session ends as every runner's does (end_session: the download, the diff, the start file
    put back) and the restore is checked; a camera not known to be as the start file exits EXIT_UNRESTORED. The
    result line carries the owner's word; the LiveCamera may open the row named and no other."""
    import runner
    C, calls, run = cards_world(tmp_path, monkeypatch, restored)
    if restored:
        C.main()
    else:
        with pytest.raises(SystemExit) as stop:
            C.main()
        assert stop.value.code == runner.EXIT_UNRESTORED
    assert ("may_open", {"Create New Folder"}) in calls
    assert calls.index("closed") < calls.index(("end", "before.DAT", C.wait_shooting)) < calls.index("checked")
    assert calls[-1] == "eyes closed"
    line = json.loads((run.dir / "results.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert line["completed"] is False and line["presses"] == ["right"]
    assert line["allowance"].startswith("the owner allowed Create New Folder remotely, ")
    assert line["changes"] == [{"key": "global:0x0001", "before": 0, "after": 1}] and line["after"] == "after.DAT"


def test_a_card_results_line_that_cannot_be_written_exits_unrestored_after_the_restore(tmp_path, monkeypatch, capsys):
    """The results line is written under restoring, after the session's end: a line that cannot be written (made up
    here) skips nothing of the restore and exits EXIT_UNRESTORED, as drive.py does, never 1 with a traceback."""
    import runner
    C, calls, _ = cards_world(tmp_path, monkeypatch)
    monkeypatch.setattr(C, "changes_of", lambda changes: (_ for _ in ()).throw(OSError("No space left on device")))
    with pytest.raises(SystemExit) as stop:
        C.main()
    assert stop.value.code == runner.EXIT_UNRESTORED
    assert calls.index("closed") < calls.index(("end", "before.DAT", C.wait_shooting)) and "checked" not in calls
    assert calls[-1] == "eyes closed" and "did not finish" in capsys.readouterr().out


def test_card_actions_judges_each_press_as_drive_does(monkeypatch):
    """The regex first, then no key but MENU on the shooting screen, then drive.press_decision: Enter on a confirmation
    only with --confirm, never on Initialize."""
    from pathlib import Path as P
    from types import SimpleNamespace
    C = cards_module()
    sent, now = [], {"kind": "dialog", "text": "Create a new folder? Execute OK Cancel", "lit": "OK"}
    cam = SimpleNamespace(read=lambda: SimpleNamespace(kind=now["kind"]), frame=SimpleNamespace(image=None, path=P("x.png")))
    monkeypatch.setattr(C, "text_of", lambda c: now["text"])
    monkeypatch.setattr(C.drive, "highlighted", lambda image, path: now["lit"])
    monkeypatch.setattr(C, "press", lambda c, key: sent.append(key))
    assert "confirmation text" in C.press_judged(cam, "enter:folder", False, ["Create New Folder"])
    assert "does not match" in C.press_judged(cam, "enter:no such words", True, ["Create New Folder"])
    assert C.press_judged(cam, "enter:folder", True, ["Create New Folder"]) == "" and sent == ["enter"]
    now.update(text="Setting Reset Camera Settings Reset Initialize", lit="Initialize")
    assert "Initialize" in C.press_judged(cam, "enter:reset", True, [])
    now.update(kind="shooting", text="", lit="")
    assert "shooting screen" in C.press_judged(cam, "down", False, [])
    assert sent == ["enter"]
