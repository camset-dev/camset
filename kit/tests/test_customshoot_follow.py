"""Offline tests of kit/provers/customshoot_values.py --follow (2026-11-20): a Recall Custom hold registered as it
stands with a live list row on each option in turn, in one session, to see a record the hold writes at Register follow
the row (the lead: 0x0c39 and the Exposure step). Made-up definitions, screens, sessions and files: the files are the
public sample with made-up changes, never a camera's own values. Nothing talks to a camera."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
if str(ROOT / "kit" / "provers") not in sys.path:
    sys.path.insert(1, str(ROOT / "kit" / "provers"))
import customshoot_values as V  # noqa: E402
from camkit import camset, definitions, session  # noqa: E402
from camkit.link import StopRequested  # noqa: E402

SAMPLE = ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.DAT"
CAM = "TEST-CAM_fw9.99"                  # conftest's made-up camera
LIVE, HELD = 0x0344, 0x0c39              # a one-byte record and a four-element one of the sample's layout
ROW = "Made-up step"
FOLLOW = f"{ROW}=0.5EV,0.3EV"
KEY = f"global:0x{HELD:04x}"


def definition(tmp_path, settings=None) -> Path:
    """A made-up definition named after the test camera: one setting at ROW, its values by code."""
    doc = {"model": "TEST-CAM", "layouts": [{"model": "TEST-CAM", "firmware": "9.99"}], "settings": settings or [
        {"key": f"global:0x{LIVE:04x}", "name": "Made-up step", "row": [ROW], "values": [[0, "0.5EV"], [1, "0.3EV"]]},
        {"key": "global:0x0b00", "name": "Elsewhere", "row": ["Drive Mode"], "values": [[0, "Single"]]}]}
    p = tmp_path / f"{CAM}.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return p


def made(path: Path, live: int | None = None, held: list | None = None) -> Path:
    """The sample with the live record and the hold's record set as given: made-up values, never a camera's."""
    cs = camset.read(SAMPLE)
    out = {}
    if live is not None:
        out[(0, LIVE)] = bytes([live]) + cs.get(0, LIVE).raw[1:]
    if held is not None:
        out[(0, HELD)] = bytes(held)
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


def test_the_put_backs_link_skips_the_stop_check_alone(tmp_path, monkeypatch):
    """CleanupLink over the real link (the stand-in camlink, kit/tests/fake_camlink.py), its run's STOP file there: a
    plain press is refused by the STOP, the same press through CleanupLink goes out; every other guard of the link
    still holds (no key but MENU on the shooting screen, no C4 there), and what it does not change it hands through."""
    from camkit import link as L
    from camkit import safety
    from camkit.runs import Run
    monkeypatch.delenv("CAMSET_USB", raising=False)
    run = Run("kit2_pass2", root=tmp_path)
    fake = Path(__file__).resolve().parent / "fake_camlink.py"
    menu, shooting = SimpleNamespace(kind="menu"), SimpleNamespace(kind="shooting")
    with L.Link(run, ip="192.0.2.10", binary=[sys.executable, "-X", "utf8", str(fake)], catch_signals=False) as lk:
        (run.dir / "STOP").write_text("", encoding="utf-8")
        with pytest.raises(StopRequested):
            lk.press("down", screen=menu)
        up = V.CleanupLink(lk)
        assert up.press("down", screen=menu)["args"][0] == "down"
        with pytest.raises(safety.Refused, match="shooting screen"):
            up.press("down", screen=shooting)
        with pytest.raises(safety.Refused, match="C4 refused"):
            up.press("c4", allow={"c4"}, screen=shooting)
        assert up.moves == lk.moves and up.run is lk.run


class FakeEyes:
    closed = 0

    def attach(self, link):
        pass

    def close(self):
        self.closed += 1


@pytest.fixture
def world(tmp_path, monkeypatch):
    """customshoot_values.main over runner.prover_session as it is, a made-up link and camera: the start download, the
    live row set and the hold registered per option, the start file put back (session.finish) and checked, and the
    second session that puts the working copy back. The files the link hands out are made-up ones, in order."""
    import proving.nav
    import runner
    defs = tmp_path / "defs"
    defs.mkdir()
    monkeypatch.setattr(definitions, "DIR", defs)
    definition(defs)
    run = SimpleNamespace(dir=tmp_path / "kit2_pass2", root=tmp_path, log=lambda *a, **k: None,
                          stop_requested=lambda: False)
    run.dir.mkdir()
    log = {"events": [], "downloads": [], "finished": [], "checked": [], "closed": 0, "fail_on": None, "files": {}}
    dat = run.dir / "dat"
    files = {"before": made(dat / "src_before.DAT", live=1, held=[1, 1, 1, 1]),
             "hold1-0-5EV-set": made(dat / "src_half.DAT", live=0, held=[1, 1, 1, 1]),
             "hold1-at-0-5EV": made(dat / "src_reg_half.DAT", live=0, held=[0, 1, 1, 0]),
             "hold1-0-3EV-set": made(dat / "src_third.DAT", live=1, held=[0, 1, 1, 0]),
             "hold1-at-0-3EV": made(dat / "src_reg_third.DAT", live=1, held=[1, 1, 1, 1]),
             "end": made(dat / "src_end.DAT", live=1, held=[1, 1, 1, 1])}
    log["files"] = files

    events = log["events"]

    class Link:
        """The link: each download and press in the run's one list of events, in order. A press after a stop (the
        run's STOP: log["stop"]) raises StopRequested unless it is a cleanup press, as camkit.link refuses it."""
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
        """The camera layer over a link: its presses go out through the link it was made with, as LiveCamera's do."""
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

    run.stop_requested = lambda: log["stop"]
    log["stop"] = False
    monkeypatch.setattr(runner, "check_readers", lambda: None)
    monkeypatch.setattr(runner, "Link", Link)
    monkeypatch.setattr(runner, "LiveCamera", lambda link, eyes, r, may_open=(): Cam(link, may_open))
    monkeypatch.setattr(runner, "close", lambda c, link: log.__setitem__("closed", log["closed"] + 1))
    monkeypatch.setattr(proving.nav, "to_shooting", step(lambda link, eyes, why: f"session reaches shooting: {why}"))
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    monkeypatch.setattr(runner.session, "finish", lambda link, start, tag="after", **kw: log["finished"].append(start)
                        or events.append("restore") or session.Ending(Path("after.DAT"), ["a change"], True))
    monkeypatch.setattr(runner.session, "check_restore", lambda r, e, start, **kw: log["checked"].append(start) or 0)
    monkeypatch.setattr(V, "load_scan", lambda scan: ([], {}))
    monkeypatch.setattr(V, "Run", lambda name: run)
    monkeypatch.setattr(V, "check_readers", lambda: None)
    monkeypatch.setattr(V, "eyes_from_config", lambda r: FakeEyes())
    monkeypatch.setattr(V, "Link", Link)
    monkeypatch.setattr(V, "LiveCamera", lambda link, eyes, r, may_open=(): Cam(link, may_open))
    monkeypatch.setattr(V, "to_shooting", step(lambda link, eyes, why: f"to shooting: {why}"))
    monkeypatch.setattr(V, "wait_lock", step("wait lock"))
    monkeypatch.setattr(V, "close_screen", step("close"))
    monkeypatch.setattr(V, "open_menu", step("menu"))

    def set_row(c, cycle, model, path, option, say, mode="Stills"):
        if log["fail_on"] == option:
            raise V.Failed(f"{option!r} did not come round in its list")
        if log["stop_on"] == option:
            log["stop"] = True                  # the STOP file there from this set on
        c.press("right")                        # opening the row's list: refused once the STOP is there
        events.append(f"set {' > '.join(path)} = {option}")
    log["stop_on"] = None
    monkeypatch.setattr(V, "set_row", set_row)
    monkeypatch.setattr(V, "open_hold", step(lambda c, cycle, model, h: f"open hold {h}"))
    # register() itself runs: the cursor brought to Register, the screen's words (none that ask), Enter, the download
    monkeypatch.setattr(V, "to_register", step("to Register"))
    monkeypatch.setattr(V, "lines", lambda c: [])
    monkeypatch.setattr(V.ocr, "text_in", lambda lines, box: "")

    def cancel_hold(c, link, cycle, model, h):
        events.append(f"open hold {h} to cancel")
        c.press("menu")                         # its first press, menu_from_shooting's MENU: no cleanup press of its own
    monkeypatch.setattr(V, "cancel_hold", cancel_hold)

    def go(*extra):
        monkeypatch.setattr(sys, "argv", ["customshoot_values", "--allow", "Reg. Custom Shoot Set", "--hold", "1",
                                          "--follow", FOLLOW, "--record", KEY, "--context", "a made-up state", *extra])
        V.main()
    log["go"] = go
    log["lines"] = lambda: [json.loads(x) for x in (run.dir / "proofs.jsonl").read_text(encoding="utf-8").splitlines()]
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


def test_a_whole_run_sets_the_row_and_registers_per_option_in_one_session_and_ends_restored(world, capsys):
    world["go"]()
    assert world["events"] == [
        "session reaches shooting: the start download", "download before",
        *registration("0.5EV", "0-5EV"), *registration("0.3EV", "0-3EV"),
        "session reaches shooting: the settings download after the hold", "restore",
        "to shooting: before putting the working copy back", "wait lock", "open hold 3 to cancel",
        "press menu (cleanup)", "to shooting: the last download", "download end"]
    assert world["downloads"] == ["00001_before.DAT", "00002_hold1-0-5EV-set.DAT", "00003_hold1-at-0-5EV.DAT",
                                  "00004_hold1-0-3EV-set.DAT", "00005_hold1-at-0-3EV.DAT", "00006_end.DAT"]
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
    with pytest.raises(SystemExit) as stop:
        world["go"]()
    assert stop.value.code == EXIT_INCOMPLETE
    assert [r["label"] for r in world["lines"]()] == ["0.5EV"]          # the first registration's line stands
    assert world["closed"] == 1 and world["finished"] and world["checked"] == world["finished"]
    assert world["events"][-4:] == ["open hold 3 to cancel", "press menu (cleanup)", "to shooting: the last download",
                                    "download end"]
    assert "stopped: Failed" in capsys.readouterr().out


def test_a_stop_part_way_restores_puts_the_working_copy_back_as_cleanup_and_exits_0(world, capsys):
    """A STOP (the run's STOP file, there from the second set on: a chain's limit, or a first Ctrl-C, which asks the run
    to stop the same way) refuses the next press, the open of the live row's list; the session closes and puts its
    start file back; then the hold's working copy is put back all the same, every press of it a cleanup press, which
    the STOP does not refuse, and the last download is compared with the start file. The run exits 0, as the module's
    stopped runs do (a failure 8, a refusal 7); before, the put-back's first press was refused and the run exited 4,
    saying the camera might not be on its start file."""
    world["stop_on"] = "0.3EV"
    world["go"]()                                                      # no SystemExit: status 0
    ev = world["events"]
    assert ev[ev.index("refused right") + 1:] == [
        "session reaches shooting: the settings download after the hold", "restore",
        "to shooting: before putting the working copy back", "wait lock", "open hold 3 to cancel",
        "press menu (cleanup)", "to shooting: the last download", "download end"]
    assert [r["label"] for r in world["lines"]()] == ["0.5EV"]
    assert world["finished"] and world["checked"] == world["finished"]
    out = capsys.readouterr().out
    assert "stopped: StopRequested" in out and "at the end: 0 records differ from the start file" in out
    assert "did not finish" not in out
