"""Offline tests of the Recall Custom provers: kit/provers/customshoot_values.py --follow (2026-11-20: a hold registered
as it stands with a live list row on each option in turn, in one session, to see a record the hold writes at Register
follow the row; the lead: 0x0c39 and the Exposure step), its --put-back, the notice after Register, and both provers'
end after a stop (customshoot_run.py's run_end and put_back, which customshoot_values.py shares): a STOP means no press
but cleanup MENU, the start file back and checked, and true words about the hold's working copy. Made-up definitions,
screens, sessions and files: the files are the public sample with made-up changes, never a camera's own values.
Nothing talks to a camera."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
if str(ROOT / "kit" / "provers") not in sys.path:
    sys.path.insert(1, str(ROOT / "kit" / "provers"))
import customshoot_run as CR  # noqa: E402
import customshoot_values as V  # noqa: E402
from camkit import camset, definitions, provenance, session  # noqa: E402
from camkit.link import StopRequested  # noqa: E402

SAMPLE = ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"
CAM = "TEST-CAM_fw9.99"                  # conftest's made-up camera
LIVE, HELD, COPY = 0x0344, 0x0c39, 0x18cb      # a one-byte record and two four-element ones of the sample's layout
ROW = "Made-up step"
FOLLOW = f"{ROW}=0.5EV,0.3EV"
KEY = f"global:0x{HELD:04x}"
COPY_KEY = f"global:0x{COPY:04x}"           # the a1 II's working copy record (customshoot_run.WORKING_COPY)


def definition(tmp_path, settings=None) -> Path:
    """A made-up definition named after the test camera: one setting at ROW, its values by code."""
    doc = {"model": "TEST-CAM", "layouts": [{"model": "TEST-CAM", "firmware": "9.99"}], "settings": settings or [
        {"key": f"global:0x{LIVE:04x}", "name": "Made-up step", "row": [ROW], "values": [[0, "0.5EV"], [1, "0.3EV"]]},
        {"key": "global:0x0b00", "name": "Elsewhere", "row": ["Drive Mode"], "values": [[0, "Single"]]}]}
    p = tmp_path / f"{CAM}.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def made(path: Path, live: int | None = None, held: list | None = None, copy: list | None = None) -> Path:
    """The sample with the live record, the hold's record and the working copy's record set as given: made-up values,
    never a camera's."""
    cs = camset.read(SAMPLE)
    out = {}
    if live is not None:
        out[(0, LIVE)] = bytes([live]) + cs.get(0, LIVE).raw[1:]
    if held is not None:
        out[(0, HELD)] = bytes(held)
    if copy is not None:
        out[(0, COPY)] = bytes(copy)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(camset.with_values(cs, out))
    return path


def test_the_plan_names_the_live_setting_by_its_row_and_each_option_by_its_code(tmp_path):
    p = definition(tmp_path)
    plan = V.follow_plan(FOLLOW, KEY, 1, where=p)
    assert plan == {"row": [ROW], "live": "global:0x0344", "options": [("0.5EV", 0), ("0.3EV", 1)], "record": KEY,
                    "element": 0}
    # hold 3's element is the third; a reading the matcher takes ("0.5 EV", a case slip) stands as the definition's
    assert V.follow_plan(f"{ROW}=0.3 ev,0.5EV", KEY, 3, where=p)["options"] == [("0.3EV", 1), ("0.5EV", 0)]
    assert V.follow_plan(FOLLOW, KEY, 3, where=p)["element"] == 2


@pytest.mark.parametrize("follow,record,said", [
    (ROW, KEY, "give the live row and its options"),
    ("=0.5EV", KEY, "give the live row and its options"),
    (f"{ROW}=", KEY, "give the live row and its options"),
    (FOLLOW, None, "needs --record"),
    (FOLLOW, "0x0c39", "needs --record"),
    (FOLLOW, "global:0x0c39[0]", "needs --record"),
    ("Other row=0.5EV", KEY, "holds no setting with values at that row"),
    (f"{ROW}=0.5EV,1.0EV", KEY, "'1.0EV' is not among"),
])
def test_the_plan_refuses_before_the_camera_is_touched(tmp_path, follow, record, said):
    with pytest.raises(SystemExit, match=said):
        V.follow_plan(follow, record, 1, where=definition(tmp_path))


def test_two_settings_at_the_row_are_refused_by_their_keys(tmp_path):
    two = [{"key": "global:0x0344", "row": [ROW], "values": [[0, "0.5EV"]]},
           {"key": "global:0x0345", "row": [ROW], "values": [[0, "0.5EV"]]}]
    with pytest.raises(SystemExit, match=r"2 settings \(global:0x0344, global:0x0345\)"):
        V.follow_plan(FOLLOW, KEY, 1, where=definition(tmp_path, two))


@pytest.mark.parametrize("argv,said", [
    ([], "give --items .* or --follow"),
    (["--items", "Shoot Mode", "--follow", FOLLOW, "--record", KEY], "give --items .* or --follow"),
    (["--follow", FOLLOW, "--record", KEY, "--prepare", "Shoot Mode=Manual Exposure"], "go with --items"),
    (["--follow", FOLLOW, "--record", KEY, "--counted"], "go with --items"),
    (["--follow", FOLLOW, "--record", KEY, "--labels", "F8"], "go with --items"),
    (["--follow", FOLLOW, "--record", KEY, "--sample", "3"], "go with --items"),
    (["--items", "Shoot Mode", "--record", KEY], "without --follow nothing checks it"),
    (["--follow", FOLLOW, "--record", KEY], "only with the owner's word"),
])
def test_the_run_refuses_a_wrong_pairing_before_anything_connects(tmp_path, monkeypatch, argv, said):
    monkeypatch.setattr(definitions, "DIR", tmp_path)
    definition(tmp_path)
    monkeypatch.setattr(V, "load_scan", lambda scan: (_ for _ in ()).throw(AssertionError("the scan was loaded")))
    monkeypatch.setattr(sys, "argv", ["customshoot_values", "--hold", "1", *argv])
    with pytest.raises(SystemExit, match=said):
        V.main()


def plan_for(tmp_path, hold=1):
    return V.follow_plan(FOLLOW, KEY, hold, where=definition(tmp_path))


def test_a_registration_whose_element_takes_the_live_code_is_applied_both_ways(tmp_path):
    plan = plan_for(tmp_path)
    start = made(tmp_path / "00001_before.DAT", live=1, held=[1, 1, 1, 1])
    half = made(tmp_path / "00002_hold1-0-5EV-set.DAT", live=0, held=[1, 1, 1, 1])
    reg = made(tmp_path / "00003_hold1-at-0-5EV.DAT", live=0, held=[0, 1, 1, 0])
    line = V.follow_line(1, plan, "0.5EV", 0, start, half, reg, "00010_down.png", "Registered.")
    assert line["applied"] is True and "not_applied" not in line
    assert (line["kind"], line["record"], line["key"], line["element"], line["index"], line["label"]) == \
        ("registration mirror", KEY, KEY, 0, 0, "0.5EV")
    assert line["path"] == ["Reg. Custom Shoot Set", "Recall Custom hold 1"] and "live" not in line
    assert line["follows"] == {"row": [ROW], "key": "global:0x0344"}
    assert (line["base"], line["dat"], line["set_base"], line["set_dat"]) == \
        (half.name, reg.name, start.name, half.name)
    assert line["changes"] == [{"key": KEY, "before": [1, 1, 1, 1], "after": [0, 1, 1, 0]}]
    assert line["set_changes"] == [{"key": "global:0x0344", "before": 1, "after": 0}]
    third = made(tmp_path / "00004_hold1-0-3EV-set.DAT", live=1, held=[0, 1, 1, 0])
    back = made(tmp_path / "00005_hold1-at-0-3EV.DAT", live=1, held=[1, 1, 1, 1])
    line = V.follow_line(1, plan, "0.3EV", 1, reg, third, back, "00020_down.png", "Registered.")
    assert line["applied"] is True and line["index"] == 1 and (line["record"], line["element"]) == (KEY, 0)
    # hold 3's element is the third; a memory set's record is named as the definition keys it ("set:")
    held3 = made(tmp_path / "00006_hold3-at-0-5EV.DAT", live=0, held=[1, 1, 0, 0])
    line = V.follow_line(3, plan_for(tmp_path, 3), "0.5EV", 0, start, half, held3, "f.png", "")
    assert line["applied"] is True and line["element"] == 2 and line["path"][-1] == "Recall Custom hold 3"
    assert V.follow_line(1, {**plan, "record": "set1:0x0c39"}, "0.5EV", 0, start, half, reg, "f.png", "")["record"] \
        == "set:0x0c39"


@pytest.mark.parametrize("set_live,set_held,reg_held,why", [
    (0, [0, 1, 1, 1], [0, 1, 1, 0], "did not change at Register"),            # it held the code already
    (0, [1, 1, 1, 1], [2, 1, 1, 0], "not to the code of the option chosen"),
    (1, [1, 1, 1, 1], [0, 1, 1, 0], "does not hold the option chosen"),       # the live row did not take
    (0, [1, 1, 1, 1], [1, 0, 1, 0], "did not change at Register"),            # another hold's element moved
])
def test_a_registration_the_element_did_not_follow_is_kept_unapplied_with_why(tmp_path, set_live, set_held, reg_held,
                                                                             why):
    plan = plan_for(tmp_path)
    start = made(tmp_path / "a.DAT", live=1, held=[1, 1, 1, 1])
    s = made(tmp_path / "b.DAT", live=set_live, held=set_held)
    r = made(tmp_path / "c.DAT", live=set_live, held=reg_held)
    line = V.follow_line(1, plan, "0.5EV", 0, start, s, r, "f.png", "")
    assert line["applied"] is False and why in line["not_applied"]


@pytest.mark.parametrize("said,ok", [("Registered.", True), ("Registered", True), (" registered . ", True),
                                     ("Not registered.", False), ("Not Registered", False), ("Unregistered.", False),
                                     ("Registered. Slot 1", False), ("", False)])
def test_a_notice_after_register_counts_only_as_the_cameras_word_alone(said, ok):
    assert V.registered_said(said) is ok


def test_register_stops_on_a_notice_that_is_not_the_cameras_word_and_downloads_nothing(monkeypatch):
    """register(): a notice after Enter on Register that says anything but "Registered." alone ("Not registered.") stops
    with Failed, before any download; the Reg. Custom Shoot Set list again (what every frame on disk shows after Enter)
    goes on to the download."""
    downloads, seen = [], {}

    class Cam:
        frame = SimpleNamespace(path=Path("00041_down.png"))

        def press(self, key):
            assert key == "enter"
            self.frame = SimpleNamespace(path=Path("00042_enter.png"))

        def read(self):
            return SimpleNamespace(kind=seen["kind"])
    link = SimpleNamespace(download=lambda tag: downloads.append(tag) or Path(f"00043_{tag}.DAT"))
    monkeypatch.setattr(V, "to_register", lambda c: None)
    monkeypatch.setattr(V, "lines", lambda c: c.frame.path.name)
    monkeypatch.setattr(V.ocr, "text_in", lambda lines, box: seen["text"] if lines == "00042_enter.png" else "Register")
    monkeypatch.setattr(V, "to_shooting", lambda link, eyes, why: None)
    monkeypatch.setattr(V, "wait_lock", lambda since, eyes, clock=None: None)
    seen.update(kind="notice", text="Not registered.")
    with pytest.raises(V.Failed, match="after Register: 'Not registered.'"):
        V.register(Cam(), link, None, "hold1-at-0-5EV")
    assert downloads == []
    seen.update(kind="submenu", text="Reg. Custom Shoot Set 1/1 Recall Custom hold 1 Recall Custom hold 2")
    assert V.register(Cam(), link, None, "hold1-at-0-5EV")[1].name == "00043_hold1-at-0-5EV.DAT"
    seen.update(kind="notice", text="Registered.")
    assert V.register(Cam(), link, None, "hold1-at-0-3EV")[2] == "Registered." and len(downloads) == 2


class FakeEyes:
    closed = 0

    def attach(self, link):
        pass

    def close(self):
        self.closed += 1


def wire(tmp_path, monkeypatch, files: dict, log: dict):
    """runner.prover_session as it is, over a made-up link and camera, for either prover: the run's folder under a
    camera's key (ILCE-1M2_fw4.00, so customshoot_run.WORKING_COPY names its working copy record), every press,
    shooting-screen wait, lock wait and download in log["events"], in order. A press while the run is told to stop
    (log["stop"]: its STOP) is refused unless it is a cleanup press, as camkit.link refuses it. The session's end
    downloads "after" (session.finish) and its check returns log["check"]; the files the link hands out are `files`, by
    tag. Both provers' names that put_back and their mains read are faked in both modules. Returns the run."""
    import proving.nav
    import runner
    events = log["events"]
    run = SimpleNamespace(dir=tmp_path / "ILCE-1M2_fw4.00" / "kit2_pass2", root=tmp_path, log=lambda *a, **k: None,
                          stop_requested=lambda: log["stop"], _left=[],
                          stop_reason=lambda: "STOP: the run's STOP file asks it to stop")
    dat = run.dir / "dat"
    dat.mkdir(parents=True)
    log.setdefault("stop", False)
    log.setdefault("check", 0)
    log.setdefault("expected", [])

    class Link:
        def __init__(self, r):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def download(self, tag):
            p = dat / f"{len(log['downloads']) + 1:05d}_{tag}.DAT"
            p.write_bytes(files[tag].read_bytes())
            log["downloads"].append(p.name)
            events.append(f"download {tag}")
            return p

        def press(self, key, hold_ms=60, allow=frozenset(), cleanup=False, **kw):
            if run.stop_requested() and not cleanup:
                events.append(f"refused {key}")
                raise StopRequested("STOP: the run's STOP file asks it to stop")
            events.append(f"press {key}" + (" (cleanup)" if cleanup else ""))
            return {"ok": True}

    class Cam:
        """The camera layer over a link: its presses go out through that link, as LiveCamera's do."""
        def __init__(self, link, may_open=()):
            self.link, self.may_open = link, frozenset(may_open)
            self.frame = SimpleNamespace(path=Path("00041_down.png"))

        def press(self, key, **kw):
            self.link.press(key)
            self.frame = SimpleNamespace(path=Path(f"00042_{key}.png"))

        def read(self):
            return SimpleNamespace(kind="submenu")         # after Enter on Register: the list again, as on disk

    def step(name):
        """A fake of one of the run's steps that records itself as an event, whatever arguments it gets."""
        return lambda *a, **k: events.append(name(*a, **k) if callable(name) else name)

    def finish(link, start, tag="after", **kw):
        log["expected"].append(kw.get("expected"))
        log["finished"].append(start)
        after = link.download(tag)
        events.append("restore")
        return session.Ending(after, ["a change"], True)

    def open_hold(c, cycle, model, h):
        events.append(f"open hold {h}")
        CR.OPENED["hold"] = h                   # as the real open_hold does once its Right went out

    def cancel_hold(c, link, cycle, model, h):
        events.append(f"open hold {h} to cancel")
        if log.get("stop_at_cancel"):
            log["stop"] = True                  # a STOP that comes while the put-back presses
        c.press("menu")                         # its first press, menu_from_shooting's MENU, no cleanup press
        CR.OPENED["hold"] = h

    monkeypatch.setattr(runner, "check_readers", lambda: None)
    monkeypatch.setattr(runner, "Link", Link)
    monkeypatch.setattr(runner, "LiveCamera", lambda link, eyes, r, may_open=(): Cam(link, may_open))
    monkeypatch.setattr(runner, "close", lambda c, link: log.__setitem__("closed", log["closed"] + 1)
                        or events.append("close after a stop"))
    monkeypatch.setattr(proving.nav, "to_shooting", step(lambda link, eyes, why: f"session reaches shooting: {why}"))
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    monkeypatch.setattr(runner.session, "finish", finish)
    def check_restore(r, e, start, **kw):
        """The restore's check: log["check"], plus, where files["restored"] stands for the camera after the upload, the
        records still differing from the start file there that the run did not name as ones no settings file sets back
        (prover_session's expected), as camkit.session.check_restore counts them."""
        log["checked"].append(start)
        after = files.get("restored")
        left = {c.key for c in camset.diff(camset.read(start), camset.read(after))} if after is not None else set()
        return log["check"] + len(left - set(kw.get("expected") or ()))
    monkeypatch.setattr(runner.session, "check_restore", check_restore)
    fakes = {"load_scan": lambda scan: ([], {}), "Run": lambda name: run, "check_readers": lambda: None,
             "eyes_from_config": lambda r: FakeEyes(), "Link": Link,
             "LiveCamera": lambda link, eyes, r, may_open=(): Cam(link, may_open),
             "to_shooting": step(lambda link, eyes, why: f"to shooting: {why}"), "wait_lock": step("wait lock"),
             "close_screen": step("close"), "open_hold": open_hold, "cancel_hold": cancel_hold,
             "to_register": step("to Register"), "lines": lambda c: []}
    for M in (V, CR):
        for name, fake in fakes.items():
            if hasattr(M, name):                # each module's own names: put_back and run_end read customshoot_run's
                monkeypatch.setattr(M, name, fake)
    monkeypatch.setattr(V.ocr, "text_in", lambda lines, box: "")
    monkeypatch.delenv("CAMSET_EYES", raising=False)
    CR.OPENED["hold"] = None
    log["lines"] = lambda: ([json.loads(x) for x in (run.dir / "proofs.jsonl").read_text(encoding="utf-8").splitlines()]
                            if (run.dir / "proofs.jsonl").exists() else [])
    log["run"] = run
    return run


@pytest.fixture
def world(tmp_path, monkeypatch):
    """customshoot_values.main --follow over the made-up session (wire): the start download, the live row set and the
    hold registered per option (register() runs as it is over faked screen reads), the start file put back and checked,
    and the session that puts the working copy back. log["stop_on"] names the option whose set finds the STOP there."""
    defs = tmp_path / "defs"
    defs.mkdir()
    monkeypatch.setattr(definitions, "DIR", defs)
    definition(defs)
    log = {"events": [], "downloads": [], "finished": [], "checked": [], "closed": 0, "fail_on": None, "stop_on": None}
    src = tmp_path / "src"
    files = {"before": made(src / "before.DAT", live=1, held=[1, 1, 1, 1]),
             "hold1-0-5EV-set": made(src / "half.DAT", live=0, held=[1, 1, 1, 1]),
             "hold1-at-0-5EV": made(src / "reg_half.DAT", live=0, held=[0, 1, 1, 0]),
             "hold1-0-3EV-set": made(src / "third.DAT", live=1, held=[0, 1, 1, 0]),
             "hold1-at-0-3EV": made(src / "reg_third.DAT", live=1, held=[1, 1, 1, 1]),
             "after": made(src / "after.DAT", live=1, held=[1, 1, 1, 1]),
             "end": made(src / "end.DAT", live=1, held=[1, 1, 1, 1])}
    log["files"] = files
    events = log["events"]
    run = wire(tmp_path, monkeypatch, files, log)
    monkeypatch.setattr(V, "open_menu", lambda c: events.append("menu"))

    def set_row(c, cycle, model, path, option, say, mode="Stills"):
        if log["fail_on"] == option:
            raise V.Failed(f"{option!r} did not come round in its list")
        if log["stop_on"] == option:
            log["stop"] = True                  # the STOP file there from this set on
        c.press("right")                        # opening the row's list: refused once the STOP is there
        events.append(f"set {' > '.join(path)} = {option}")
    monkeypatch.setattr(V, "set_row", set_row)

    def go(*extra):
        monkeypatch.setattr(sys, "argv", ["customshoot_values", "--allow", "Reg. Custom Shoot Set", "--hold", "1",
                                          "--follow", FOLLOW, "--record", KEY, "--context", "a made-up state", *extra])
        V.main()
    log["go"] = go
    log["run_dir"] = run.dir
    return log


def registration(option: str, tag: str) -> list:
    """One --follow registration, every press, wait and download in its order: the live row set and the menu closed,
    the shooting screen before the download and the menu's lock after it, then the hold opened, Register and Enter,
    the shooting screen, the download and the lock again."""
    return ["menu", "press right", f"set {ROW} = {option}", "close",
            "to shooting: the download after the live row", f"download hold1-{tag}-set", "wait lock",
            "open hold 1", "to Register", "press enter",
            "to shooting: the download after Register", f"download hold1-at-{tag}", "wait lock"]


SESSION_END = ["session reaches shooting: the settings download after the hold", "download after", "restore"]
PUT_BACK = ["to shooting: before putting the working copy back", "wait lock", "open hold 3 to cancel", "press menu",
            "to shooting: the last download", "download end"]
NO_PUT_BACK = ["to shooting: before putting the working copy back", "wait lock", "to shooting: the last download",
               "download end"]


def exits(go) -> int:
    """The run's exit status: 0 where it returned."""
    try:
        go()
    except SystemExit as e:
        return e.code
    return 0


def test_a_whole_run_sets_the_row_and_registers_per_option_in_one_session_and_ends_restored(world, capsys):
    assert exits(world["go"]) == 0
    assert world["events"] == ["session reaches shooting: the start download", "download before",
                               *registration("0.5EV", "0-5EV"), *registration("0.3EV", "0-3EV"),
                               *SESSION_END, *PUT_BACK]
    assert world["downloads"][:6] == ["00001_before.DAT", "00002_hold1-0-5EV-set.DAT", "00003_hold1-at-0-5EV.DAT",
                                      "00004_hold1-0-3EV-set.DAT", "00005_hold1-at-0-3EV.DAT", "00006_after.DAT"]
    lines = world["lines"]()
    assert [(r["label"], r["index"], r["applied"]) for r in lines] == [("0.5EV", 0, True), ("0.3EV", 1, True)]
    assert all(r["kind"] == "registration mirror" and (r["record"], r["element"], r["hold"]) == (KEY, 0, 1)
               for r in lines)
    assert all(r["context"] == "a made-up state" and "Reg. Custom Shoot Set" in r["allowance"] for r in lines)
    assert lines[0]["set_base"] == "00001_before.DAT" and lines[1]["set_base"] == "00003_hold1-at-0-5EV.DAT"
    assert world["finished"] == [world["finished"][0]] and world["checked"] == world["finished"]
    out = capsys.readouterr().out
    assert f"{KEY}[0] 1 -> 0 at Register; applied" in out and f"{KEY}[0] 0 -> 1 at Register; applied" in out
    assert "at the end: 0 records differ from the start file" in out


def test_the_sessions_restore_check_leaves_out_the_working_copy_which_the_put_back_checks(world):
    """The run's session hands its end and its restore check the working copy's record as one no settings file sets
    back (prover_session's expected: said by key, not counted), since the put-back after it moves it; the last download,
    after the put-back, is compared whole."""
    world["go"]()
    assert world["expected"] == [frozenset({COPY_KEY})]


def test_pass_2s_report_reads_the_lines_as_values_a_registration_wrote_and_no_rows_proof(world):
    """The lines reach kit/schema_update.py as pass2_report's mirrored_values (a record no live record holds, each code
    with its label), never as a memory copy of a live setting (registration_mirrors: they name no "live") nor as a
    row's proofs (report_proofs leaves the kind out)."""
    import pass2_report
    world["go"]()
    run = world["run_dir"]
    got = pass2_report.mirrored_values(run)
    assert list(got) == [KEY] and got[KEY]["values"] == {0: "0.5EV", 1: "0.3EV"}
    assert "Reg. Custom Shoot Set" in got[KEY]["allowance"]
    assert pass2_report.registration_mirrors(run) == {}
    assert pass2_report.report_proofs(run)[0] == []


def test_a_failure_part_way_restores_puts_the_working_copy_back_and_exits_incomplete(world, capsys):
    from exit_status import EXIT_INCOMPLETE
    world["fail_on"] = "0.3EV"
    assert exits(world["go"]) == EXIT_INCOMPLETE
    assert [r["label"] for r in world["lines"]()] == ["0.5EV"]          # the first registration's line stands
    assert world["closed"] == 1 and world["finished"] and world["checked"] == world["finished"]
    assert world["events"][-len(PUT_BACK):] == PUT_BACK                # no stop: the copy goes back as ever
    out = capsys.readouterr().out
    assert "stopped: Failed" in out and "the start file is back and checked" in out and "not put back" not in out


def test_a_stop_file_there_before_the_run_presses_nothing_and_exits_4_naming_it(world, capsys):
    """A STOP file left from an earlier stop (Run._left): the run's first press is refused, its restore uploads
    nothing (nothing moved), and the put-back presses nothing; the run exits 4, as before 2026-11-20 (a chain stops),
    saying the file was there before the run and naming it."""
    left = world["run_dir"] / "STOP"
    world["run"]._left = [left]
    world["stop"] = True
    assert exits(world["go"]) == 4
    ev = world["events"]
    assert "refused right" in ev and ev[-len(NO_PUT_BACK):] == NO_PUT_BACK
    assert not any(e.startswith("press ") and "(cleanup)" not in e for e in ev)       # nothing pressed but MENU
    assert world["lines"]() == []
    out = capsys.readouterr().out
    assert (f"{left} was there before this run started (an earlier stop): the run pressed nothing but what closes a "
            "screen already open (a cleanup MENU, and one cleanup OK on a notice that has just refused MENU and shows OK "
            "alone) and registered nothing" in out)
    assert "back and checked" not in out



def test_a_stop_after_a_hold_was_opened_presses_nothing_more_and_owes_nothing_where_the_copy_is_as_the_start(
        world, capsys):
    """The STOP there from the second set on (a chain's limit, or a first Ctrl-C, which asks the run to stop the same
    way): the open of the live row's list is refused, the session closes and restores, and the put-back sends no press.
    The working copy's record is as the start file has it at the end (D1's case: every hold holds the same), so the run
    exits 8 (never 0), saying the start file is back and checked and that nothing more is owed: no --put-back."""
    from exit_status import EXIT_INCOMPLETE
    world["stop_on"] = "0.3EV"
    assert exits(world["go"]) == EXIT_INCOMPLETE
    ev = world["events"]
    assert ev[ev.index("refused right") + 1:] == ["close after a stop", *SESSION_END, *NO_PUT_BACK]
    assert [r["label"] for r in world["lines"]()] == ["0.5EV"]
    out = capsys.readouterr().out
    assert "stopped: StopRequested" in out and "the start file is back and checked" in out
    assert (f"the hold's working copy ({COPY_KEY}'s fourth slot, which no settings file sets back) was not put back, "
            "because the run was told to stop, but its record is as the start file has it: nothing more is owed" in out)
    assert "--put-back" not in out


def test_a_stop_after_a_hold_was_opened_gives_put_back_against_the_start_file_where_hold_3_restores_it(
        world, capsys, monkeypatch):
    """The copy's record differs at the end and the start file's fourth slot holds what its hold-3 slot holds: opening
    hold 3 is what restores it, so the words give the exact command, with the run's eyes, scan and start file."""
    from exit_status import EXIT_INCOMPLETE
    monkeypatch.setenv("CAMSET_EYES", "hdmi")
    copies(world, start=[0, 0, 0, 0], end=[0, 0, 0, 2])
    world["stop_on"] = "0.3EV"
    assert exits(lambda: world["go"]("--scan", "kit2_page_scan_1118p")) == EXIT_INCOMPLETE
    out = capsys.readouterr().out
    assert (f"the hold's working copy ({COPY_KEY}'s fourth slot, which no settings file sets back) was not put back, "
            "because the run was told to stop; it differs from the start file. Opening hold 3 restores it: put it back "
            "with:\n  CAMSET_EYES=hdmi .venv/bin/python -u kit/provers/customshoot_values.py --allow 'Reg. Custom "
            "Shoot Set' --put-back --against kit2_pass2/dat/00001_before.DAT --scan kit2_page_scan_1118p" in out)


def test_a_stop_before_any_hold_was_opened_owes_nothing_more(world, capsys):
    from exit_status import EXIT_INCOMPLETE
    world["stop_on"] = "0.5EV"
    assert exits(world["go"]) == EXIT_INCOMPLETE
    assert world["events"][-len(NO_PUT_BACK):] == NO_PUT_BACK and world["lines"]() == []
    out = capsys.readouterr().out
    assert "the start file is back and checked" in out and "no hold's screen was opened, so nothing else is owed" in out
    assert "not put back" not in out



def test_a_stop_during_the_put_back_closes_with_menu_and_says_the_copy_was_not_put_back(world, capsys):
    """A STOP that comes while the put-back presses (its first press refused): closed with cleanup MENU, the last
    download compared, exit 8, the words on the copy (here as the start file has it: nothing more owed)."""
    from exit_status import EXIT_INCOMPLETE
    world["stop_at_cancel"] = True
    assert exits(world["go"]) == EXIT_INCOMPLETE
    ev = world["events"]
    assert ev[ev.index("open hold 3 to cancel"):] == ["open hold 3 to cancel", "refused menu", "close after a stop",
                                                      "to shooting: the last download", "download end"]
    out = capsys.readouterr().out
    assert "was not put back, because the run was told to stop, but its record is as the start file has it" in out


def test_a_stop_whose_restore_does_not_check_out_exits_4(world, capsys):
    world["stop_on"] = "0.3EV"
    world["check"] = 2                                                  # two records still differ after the upload
    assert exits(world["go"]) == 4
    assert "back and checked" not in capsys.readouterr().out



def test_the_working_copy_differing_after_a_put_back_fails_the_run_and_offers_no_put_back(world, capsys):
    """With no stop the put-back was done and the copy still differs at the end: exit 4, the words say so, and give no
    --put-back (it has just been done)."""
    copies(world, start=[0, 0, 0, 0], end=[0, 0, 0, 2])
    assert exits(world["go"]) == 4
    out = capsys.readouterr().out
    assert f"the working copy's record ({COPY_KEY}) still differs from the start file after hold 3's screen was " \
        "opened and left" in out
    assert "--put-back" not in out


def copies(world, start, end):
    """Every file of the run with the working copy's record at `start`, the last download's at `end`."""
    files = world["files"]
    for tag, f in list(files.items()):
        cs = camset.read(f)
        live, held = cs.get(0, LIVE).values()[0], cs.get(0, HELD).values()
        files[tag] = made(f.parent / f"{f.stem}_c.DAT", live=live, held=held, copy=end if tag == "end" else start)


def test_a_start_whose_fourth_slot_was_another_holds_owes_nothing_where_the_copy_is_as_it_was(world, capsys):
    """The reviewer's case: the start file's fourth slot holds holds 1 and 2's value, not hold 3's; a stop after hold 1
    was opened leaves the copy as the start file has it (0 records differ): nothing more is owed, no --put-back, which
    would open hold 3 and move the copy away from the start."""
    from exit_status import EXIT_INCOMPLETE
    copies(world, start=[2, 2, 0, 2], end=[2, 2, 0, 2])
    world["stop_on"] = "0.3EV"
    assert exits(world["go"]) == EXIT_INCOMPLETE
    out = capsys.readouterr().out
    assert "nothing more is owed" in out and "--put-back" not in out


def test_a_copy_off_that_hold_3_cannot_restore_names_the_hold_to_open_by_hand(world, capsys):
    """The copy differs and the start file's fourth slot holds what holds 1 and 2 hold, not hold 3: opening hold 1's
    (or hold 2's) screen and leaving it, by hand, restores it; no --put-back; exit 4 (not on its start file)."""
    copies(world, start=[2, 2, 0, 2], end=[2, 2, 0, 0])
    world["stop_on"] = "0.3EV"
    assert exits(world["go"]) == 4
    out = capsys.readouterr().out
    assert ("Opening hold 3 would not restore it: the start file's fourth slot holds what hold 1's slot holds (and "
            "hold 2's). Open Recall Custom hold 1's registration screen (Reg. Custom Shoot Set > Recall Custom hold 1) "
            "and leave it with MENU, by hand." in out)
    assert "--put-back" not in out


def test_a_copy_off_that_no_hold_restores_says_so(world, capsys):
    copies(world, start=[1, 2, 0, 3], end=[1, 2, 0, 0])
    world["stop_on"] = "0.3EV"
    assert exits(world["go"]) == 4
    out = capsys.readouterr().out
    assert "No hold's screen restores it: no hold's slot in the start file holds what its fourth slot holds." in out
    assert "--put-back" not in out


def test_a_failure_whose_put_back_left_the_copy_differing_exits_4_and_says_how_it_goes_back(world, capsys):
    """A failure (no stop) at 0.3EV, the start's copy on hold 1's value: the put-back is done (hold 3's screen opened and
    left) and the copy differs at the end, so the run exits 4, as before 2026-11-20, never the failure's 8, and says how
    the copy goes back (by hand: hold 1's screen), no --put-back; the start file is not called back and checked."""
    copies(world, start=[2, 2, 0, 2], end=[2, 2, 0, 0])
    world["fail_on"] = "0.3EV"
    assert exits(world["go"]) == 4
    assert world["events"][-len(PUT_BACK):] == PUT_BACK
    out = capsys.readouterr().out
    assert (f"the working copy's record ({COPY_KEY}) still differs from the start file after hold 3's screen was opened "
            "and left. Opening hold 3 would not restore it: the start file's fourth slot holds what hold 1's slot holds"
            in out)
    assert "--put-back" not in out and "back and checked" not in out


# ---------------------------------------------------------------- --put-back: the working copy put back alone


@pytest.mark.parametrize("extra,said", [
    (["--items", "Shoot Mode"], "--put-back is a run of its own"),
    (["--follow", FOLLOW, "--record", KEY], "--put-back is a run of its own"),
    (["--hold", "1"], "--put-back is a run of its own"),
    (["--prepare", "Shoot Mode=Manual Exposure"], "--put-back is a run of its own"),
    (["--counted"], "--put-back is a run of its own"),
    (["--labels", "F8"], "--put-back is a run of its own"),
    (["--sample", "3"], "--put-back is a run of its own"),
    (["--record", KEY], "--put-back is a run of its own"),
])
def test_put_back_goes_alone_and_is_refused_before_anything_connects(monkeypatch, extra, said):
    monkeypatch.setattr(V, "load_scan", lambda scan: (_ for _ in ()).throw(AssertionError("the scan was loaded")))
    monkeypatch.setattr(sys, "argv", ["customshoot_values", "--allow", "Reg. Custom Shoot Set", "--put-back", *extra])
    with pytest.raises(SystemExit, match=said):
        V.main()


def test_against_goes_with_put_back_alone(monkeypatch):
    monkeypatch.setattr(V, "load_scan", lambda scan: (_ for _ in ()).throw(AssertionError("the scan was loaded")))
    monkeypatch.setattr(sys, "argv", ["customshoot_values", "--allow", "Reg. Custom Shoot Set", "--hold", "1",
                                      "--items", "ISO", "--against", "x.DAT"])
    with pytest.raises(SystemExit, match="--against goes with --put-back"):
        V.main()


def test_put_back_needs_the_owners_word_and_a_hold_is_needed_without_it(monkeypatch):
    monkeypatch.setattr(V, "load_scan", lambda scan: (_ for _ in ()).throw(AssertionError("the scan was loaded")))
    monkeypatch.setattr(sys, "argv", ["customshoot_values", "--put-back"])
    with pytest.raises(SystemExit, match="only with the owner's word"):
        V.main()
    monkeypatch.setattr(sys, "argv", ["customshoot_values", "--allow", "Reg. Custom Shoot Set", "--items", "ISO"])
    with pytest.raises(SystemExit, match="--hold"):
        V.main()


@pytest.fixture
def lone(tmp_path, monkeypatch):
    """customshoot_values.main --put-back over the made-up session (wire): its own start download's copy off (fourth
    slot holding holds 1 and 2's value), the file to compare with (log["ref"], recorded as one of this camera's
    downloads) holding hold 3's in its fourth slot, and the end download as hold 3's screen leaves it."""
    log = {"events": [], "downloads": [], "finished": [], "checked": [], "closed": 0}
    src = tmp_path / "src"
    files = {"before": made(src / "before.DAT", copy=[2, 2, 0, 2]),
             "after": made(src / "after.DAT", copy=[2, 2, 0, 0])}
    log["files"] = files
    log["ref"] = made(src / "start_of_the_stopped_run.DAT", copy=[2, 2, 0, 0])
    provenance.record(log["ref"])
    wire(tmp_path, monkeypatch, files, log)

    def go(*extra):
        monkeypatch.setattr(sys, "argv", ["customshoot_values", "--allow", "Reg. Custom Shoot Set", "--put-back", *extra])
        V.main()
    log["go"] = go
    return log


def test_put_back_against_a_download_opens_hold_3_and_checks_the_copy_equals_that_files(lone, capsys):
    """--against FILE, a download of this camera whose fourth slot holds its hold-3 slot's value: its start download,
    hold 3's screen opened and left with MENU (cancel_hold), its end download compared with its start file with the
    working copy's record left out (it is what the run moves) and checked instead: equal to FILE's."""
    assert exits(lambda: lone["go"]("--against", str(lone["ref"]))) == 0
    assert lone["events"] == ["session reaches shooting: the start download", "download before",
                              "open hold 3 to cancel", "press menu",
                              "session reaches shooting: the settings download after the put-back", "download after",
                              "restore"]
    assert lone["expected"] == [frozenset({COPY_KEY})]
    out = capsys.readouterr().out
    assert f"comparing the working copy with {lone['ref'].name} (--against)" in out
    assert f"the working copy's record ({COPY_KEY}) equals {lone['ref'].name}'s: put back" in out


def test_put_back_refuses_before_anything_connects_a_file_not_downloaded_or_whose_copy_hold_3_cannot_restore(
        lone, monkeypatch):
    monkeypatch.setattr(V, "load_scan", lambda scan: (_ for _ in ()).throw(AssertionError("the scan was loaded")))
    stray = made(lone["ref"].parent / "stray.DAT", live=0, copy=[2, 2, 0, 0])    # never recorded as a download
    with pytest.raises(SystemExit, match="not a camera download"):
        lone["go"]("--against", str(stray))
    off = made(lone["ref"].parent / "off.DAT", copy=[2, 2, 0, 2])
    provenance.record(off)
    with pytest.raises(SystemExit, match="fourth slot is not its hold-3 slot"):
        lone["go"]("--against", str(off))
    assert lone["events"] == []


def test_put_back_whose_copy_does_not_end_as_the_files_exits_4(lone, capsys):
    lone["files"]["after"] = made(lone["files"]["after"].parent / "after_off.DAT", copy=[2, 2, 0, 2])
    assert exits(lambda: lone["go"]("--against", str(lone["ref"]))) == 4
    assert f"the working copy's record ({COPY_KEY}) does not equal {lone['ref'].name}'s" in capsys.readouterr().out


def test_put_back_without_against_takes_its_own_start_only_where_hold_3_holds_its_copy(lone, capsys):
    """No --against: the run's own start download is the reference only where its fourth slot already holds its hold-3
    slot's value (opening hold 3 should leave it so), and it says so; where it does not (the copy off, which is when a
    put-back is wanted), it presses nothing and asks for the file to compare with."""
    lone["files"]["before"] = made(lone["files"]["before"].parent / "before_ok.DAT", copy=[2, 2, 0, 0])
    assert exits(lone["go"]) == 0
    out = capsys.readouterr().out
    assert "no --against: comparing the working copy with this run's own start download" in out
    lone["files"]["before"] = made(lone["files"]["before"].parent / "before_off.DAT", copy=[2, 2, 0, 2])
    lone["events"].clear()
    with pytest.raises(SystemExit, match="name the file it must equal with --against"):
        lone["go"]()
    assert "open hold 3 to cancel" not in lone["events"]






def test_a_stop_stops_put_back_like_any_run(lone, capsys):
    """A STOP: its first press refused, the session restored; the copy still off from the file's, which hold 3
    restores: exit 8 and the command again; a STOP file there before it: exit 4."""
    from exit_status import EXIT_INCOMPLETE
    lone["stop"] = True
    lone["files"]["after"] = lone["files"]["before"]                   # nothing moved
    assert exits(lambda: lone["go"]("--against", str(lone["ref"]))) == EXIT_INCOMPLETE
    assert "refused menu" in lone["events"]
    out = capsys.readouterr().out
    assert "was not put back, because the run was told to stop; it differs from the start file" in out
    assert f"--put-back --against {lone['ref'].as_posix()}" in out      # shown with forward slashes (paths.shown)
    lone["run"]._left = [Path("STOP")]
    assert exits(lambda: lone["go"]("--against", str(lone["ref"]))) == 4



def test_put_back_that_fails_says_what_failed_not_that_it_was_told_to_stop(lone, capsys, monkeypatch):
    """--put-back whose hold 3 did not open (its title another screen's): no stop was asked for, so the words name the
    failure, never "because the run was told to stop"."""
    from exit_status import EXIT_INCOMPLETE

    def cancel_hold(c, link, cycle, model, h):
        CR.OPENED["hold"] = h
        raise V.Failed("Right on hold 3 opened unknown ('x'), not its items")
    monkeypatch.setattr(CR, "cancel_hold", cancel_hold)
    monkeypatch.setattr(V, "cancel_hold", cancel_hold)
    lone["files"]["after"] = lone["files"]["before"]
    assert exits(lambda: lone["go"]("--against", str(lone["ref"]))) == EXIT_INCOMPLETE
    out = capsys.readouterr().out
    assert "told to stop" not in out
    assert "was not put back, because Failed: Right on hold 3 opened unknown ('x'), not its items" in out


def test_a_stop_during_the_sessions_restore_counts_as_a_stop(world, capsys, monkeypatch):
    """The body done, a STOP arriving during the session's end (a chain's limit while it restores): the put-back
    presses nothing, and the run ends as a stopped one: exit 8, never 0 or 4, with the words on the copy."""
    import runner
    from exit_status import EXIT_INCOMPLETE
    finish = runner.session.finish

    def finish_then_stop(link, start, tag="after", **kw):
        world["stop"] = True
        return finish(link, start, tag, **kw)
    monkeypatch.setattr(runner.session, "finish", finish_then_stop)
    assert exits(world["go"]) == EXIT_INCOMPLETE                        # the copy as the start file has it
    assert world["events"][-len(NO_PUT_BACK):] == NO_PUT_BACK
    assert "nothing more is owed" in capsys.readouterr().out
    world["stop"] = False
    world["events"].clear()
    copies(world, start=[0, 0, 0, 0], end=[0, 0, 0, 2])
    assert exits(world["go"]) == EXIT_INCOMPLETE                        # the copy differs: the words say so
    out = capsys.readouterr().out
    assert "because the run was told to stop; it differs from the start file" in out and "--put-back --against" in out


def test_a_stop_before_any_hold_was_opened_with_the_copy_differing_is_never_nothing_owed(world, capsys):
    world["stop_on"] = "0.5EV"
    world["files"]["end"] = made(world["files"]["end"].parent / "end_copy.DAT", live=1, held=[1, 1, 1, 1],
                                 copy=[0, 0, 0, 2])
    assert exits(world["go"]) == 4
    out = capsys.readouterr().out
    assert "nothing else is owed" not in out
    assert f"the working copy's record ({COPY_KEY}) differs from the start file though this run opened no hold's " \
        "screen" in out


def test_open_hold_marks_the_hold_opened_once_its_right_went_out(monkeypatch):
    """customshoot_run.open_hold sets OPENED once its Right on the hold went out (the working copy may follow that hold
    from then on), and not when a press before it was refused."""
    pressed = []

    class Cam:
        frame = SimpleNamespace(path=Path("f.png"))

        def press(self, key):
            if key in pressed_refused:
                raise StopRequested("STOP")
            pressed.append(key)

        def read(self):
            return SimpleNamespace(kind="checklist")
    pressed_refused = set()
    for name, fake in (("menu_from_shooting", lambda c: None), ("scan_position", lambda c, cycle: 0),
                       ("go_to", lambda *a: 0), ("enter_path", lambda *a: None), ("item_now", lambda c: 0),
                       ("lines", lambda c: []), ("option_key", lambda t: "recallcustomhold2")):
        monkeypatch.setattr(CR, name, fake)
    monkeypatch.setattr(CR.ocr, "text_in", lambda lines, box: "Recall Custom hold 2")
    CR.OPENED["hold"] = None
    pressed_refused.add("right")
    with pytest.raises(StopRequested):
        CR.open_hold(Cam(), [], {}, 2)
    assert CR.OPENED["hold"] is None
    pressed_refused.clear()
    CR.open_hold(Cam(), [], {}, 2)
    assert CR.OPENED["hold"] == 2 and pressed == ["right"]


# ---------------------------------------------------------------- customshoot_run.py: the same notice, end and exits

def test_the_ticks_visit_takes_a_notice_after_register_only_as_the_cameras_word_alone(monkeypatch):
    """customshoot_run.visit: "Not registered." after Enter on Register stops it before any download, as
    customshoot_values.register does (registered_said, shared)."""
    downloads, said = [], {}

    class Cam:
        frame = SimpleNamespace(path=Path("00041_down.png"))

        def press(self, key):
            self.frame = SimpleNamespace(path=Path(f"00042_{key}.png"))

        def read(self):
            return SimpleNamespace(kind=said["kind"])
    link = SimpleNamespace(download=lambda tag: downloads.append(tag) or Path(f"00043_{tag}.DAT"))
    for name, fake in (("open_hold", lambda *a: None), ("on_ticks", lambda c: True), ("to_register", lambda c: None),
                       ("lines", lambda c: c.frame.path.name), ("later", lambda fn, c: None),
                       ("to_shooting", lambda *a: None), ("wait_lock", lambda *a, **k: None)):
        monkeypatch.setattr(CR, name, fake)
    monkeypatch.setattr(CR.ocr, "text_in", lambda lines, box: said["text"] if lines == "00042_enter.png" else "")
    said.update(kind="notice", text="Not registered.")
    with pytest.raises(CR.Failed, match="after Register: 'Not registered.'"):
        CR.visit(Cam(), link, None, None, None, 1, [])
    assert downloads == []
    said.update(kind="notice", text="Registered.")
    assert CR.visit(Cam(), link, None, None, None, 1, [])["dat"].name == "00043_hold1-ticks.DAT"


@pytest.fixture
def ticks(tmp_path, monkeypatch):
    """customshoot_run.main over the made-up session (wire), its visits faked: each opens the hold (OPENED) and
    downloads; log["stop_on_visit"] names the visit whose start finds the STOP there."""
    log = {"events": [], "downloads": [], "finished": [], "checked": [], "closed": 0, "visits": 0}
    src = tmp_path / "src"
    files = {"before": made(src / "before.DAT"), "after": made(src / "after.DAT"), "end": made(src / "end.DAT"),
             "visit": made(src / "visit.DAT")}
    log["files"] = files
    wire(tmp_path, monkeypatch, files, log)

    def visit(cam, link, hdmi, cycle, model, h, cells):
        log["visits"] += 1
        if log.get("stop_on_visit") == log["visits"]:
            log["stop"] = True
        if log.get("fail_on_visit") == log["visits"]:
            CR.OPENED["hold"] = h
            raise CR.Failed("cannot tell which item the cursor is on (00123_left.png)")
        cam.press("left")                       # the visit's first press after the hold opens: refused once stopped
        CR.OPENED["hold"] = h
        log["events"].append(f"visit {cells}")
        return {"boxes": [], "refused": [], "chosen_frame": "f.png", "row_frame": "r.png", "vlm": None,
                "dat": link.download("visit"), "said": ""}
    monkeypatch.setattr(CR, "visit", visit)
    monkeypatch.setattr(CR, "settled", lambda v: v)

    def go():
        monkeypatch.setattr(sys, "argv", ["customshoot_run", "--allow", "Reg. Custom Shoot Set", "--hold", "1",
                                          "--count", "1"])
        CR.main()
    log["go"] = go
    return log


def test_the_ticks_run_puts_the_copy_back_and_hands_its_check_the_copy_as_expected(ticks):
    assert exits(ticks["go"]) == 0
    assert ticks["events"][-len(PUT_BACK):] == PUT_BACK and ticks["expected"] == [frozenset({COPY_KEY})]



def test_the_ticks_run_stopped_presses_nothing_more_and_says_what_is_owed(ticks, capsys):
    from exit_status import EXIT_INCOMPLETE
    ticks["stop_on_visit"] = 2
    assert exits(ticks["go"]) == EXIT_INCOMPLETE
    assert ticks["events"][-len(NO_PUT_BACK):] == NO_PUT_BACK
    out = capsys.readouterr().out
    assert "the start file is back and checked" in out and "was not put back, because the run was told to stop" in out
    assert "nothing more is owed" in out


def test_the_ticks_run_with_a_stop_file_there_before_it_exits_4_naming_it(ticks, capsys):
    ticks["run"]._left = [Path("runs/ILCE-1M2_fw4.00/kit2_pass2/STOP")]
    ticks["stop"] = True
    assert exits(ticks["go"]) == 4
    assert ticks["events"][-len(NO_PUT_BACK):] == NO_PUT_BACK
    assert "was there before this run started (an earlier stop)" in capsys.readouterr().out


def test_the_ticks_run_that_fails_part_way_exits_8_where_it_exited_0(ticks, capsys):
    """A hold whose visit failed part way (kit2_pass2/customshoot_ticks.log, 2026-10-30: "cannot tell which item the
    cursor is on") is incomplete: the start file back and checked, the copy put back (no stop), exit 8, so a chain
    stops; it exited 0 before 2026-11-20 and the next hold ran."""
    from exit_status import EXIT_INCOMPLETE
    ticks["fail_on_visit"] = 2
    assert exits(ticks["go"]) == EXIT_INCOMPLETE
    assert ticks["events"][-len(PUT_BACK):] == PUT_BACK
    out = capsys.readouterr().out
    assert "stopped: Failed: cannot tell which item the cursor is on" in out and "back and checked" in out


def test_a_copy_that_differed_after_the_restore_and_was_put_back_ends_0_where_it_ended_4(ticks, monkeypatch):
    """The camera after the session's upload still holding another value in the working copy's fourth slot (no settings
    file sets it back), the put-back then bringing it back: the session's check leaves that record out (expected) and
    the last download finds it as the start file has it, exit 0. Without the record left out (as before 2026-11-20) the
    check counted it and the run exited 4."""
    ticks["files"]["restored"] = made(ticks["files"]["end"].parent / "restored.DAT", copy=[0, 0, 0, 2])
    assert exits(ticks["go"]) == 0
    monkeypatch.setattr(CR, "working_copy_keys", lambda run: frozenset())
    assert exits(ticks["go"]) == 4
