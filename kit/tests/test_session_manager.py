"""The session every runner runs with the camera (decision 15): what each runner's session sends at its start and its
end, in order, against made-up parts (a link, eyes, a camera that record what reaches them), pinned runner by runner.
Each pin was written against the runner as it was before its session moved onto runner.prover_session (or its start
onto runner.session_start), and holds after the move but for the two changes the review of 2026-11-18 named: the
menu's lock after the start download is waited out by camkit.session.wait_lock ("lock wait", watched with HDMI eyes in
a mode measured) where a fixed sleep stood, and the fixed second after a cleanup MENU that camkit.session.wait_for's
grace covers is gone."""
import ast
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
KIT = ROOT / "kit"
for _p in (KIT / "tools", KIT / "provers", KIT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import fake_camlink  # noqa: E402
import runner  # noqa: E402
from camkit import session  # noqa: E402

# every runner a pin starts, and what one imports as it runs (mode_switch --set: boxes_run), imported here before any
# part is made up: a module first imported while a part is made up would keep the made-up part for the tests after
import axis_walk, boxes_run, card_actions, grid_run, help_run, mode_switch, mymenu_run, page_scan  # noqa: E402,F401,E401
import pass3_run, prove_run, shootmode_run, table_walk  # noqa: E402,F401,E401

CHANGE = SimpleNamespace(key="global:0x0001", before=0, after=1)


class Eyes:
    """Made-up eyes: OSD by name (the lock's watched wait does not apply), every grab a blank frame."""
    name = "osd"

    def __init__(self, world, run=None):
        self.world, self.run = world, run

    def attach(self, link):
        self.world.say("attach")

    def grab(self, tag="f", save=True):
        return SimpleNamespace(image=None, path=None, t=0)

    def close(self):
        self.world.say("eyes closed")


class Cam:
    """A made-up LiveCamera: a menu page on show, each press said."""

    def __init__(self, world, kw):
        self.world, self.hdmi = world, None
        self.may_open = kw.get("may_open", ())
        self.frame = SimpleNamespace(path=Path("00001_menu.png"), image=None)

    def read(self):
        return SimpleNamespace(kind="menu", focus=None)

    def refresh(self, tag="f", frame=None):
        return self.read()

    def press(self, key, **kw):
        self.world.say(f"cam {key}")


class World:
    """What a session's parts were asked, in order (said); `kind`, what the screen reads as before the start download
    (the cleanup MENU's check); `uploaded`, whether the session's end uploads the start file (so its check runs)."""

    def __init__(self, monkeypatch):
        self.mp, self.said, self.kind, self.uploaded, self.n = monkeypatch, [], "shooting", True, 0

    def say(self, what: str) -> None:
        self.said.append(what)

    def wire(self, *modules) -> "World":
        """The parts every session reaches, made up in runner, camkit.session, proving.nav, proving.base and each of
        `modules` (each name where that module holds it): so a pin holds whichever module runs the session."""
        import proving.base
        import proving.nav
        from camkit import screen
        mods = [runner, session, proving.nav, proving.base, *modules]
        w = self

        def put(name, value):
            for m in mods:
                if name in vars(m):
                    self.mp.setattr(m, name, value)
        put("check_readers", lambda: w.say("check readers"))
        put("Link", self.link_class())
        put("eyes_from_config", lambda run: Eyes(w, run))
        put("LiveCamera", lambda link, eyes, run, **kw: w.camera(kw))
        put("to_shooting", lambda link, eyes, why, **kw: w.say(f"to_shooting: {why}"))
        put("wait_for", lambda eyes, kinds, why, **kw: w.say(f"wait_for: {why}") or "shooting")
        put("wait_lock", lambda since, eyes=None, mode=None, clock=None, longest=session.LOCK_S, poll=0.05:
            w.say(f"lock wait ({longest:g} s at most)") or "lock")
        put("check_restore", lambda run, ending, start, **kw: w.say(f"check {sorted(kw)}") or 0)
        put("verify_restore", lambda run, start, **kw: w.say("verify") or 0)
        self.mp.setattr(runner, "close", lambda cam, link: w.say("close"))
        self.mp.setattr(session, "finish", lambda link, start, tag="after", **kw: w.finish(tag, kw))
        self.mp.setattr(screen, "read", lambda f: SimpleNamespace(kind=w.kind, focus=None))
        self.mp.setattr(time, "sleep", lambda s: w.say(f"sleep {s:g}"))
        return self

    def camera(self, kw):
        shown = {k: sorted(v) if isinstance(v, (set, frozenset)) else v for k, v in kw.items()
                 if v not in ((), None, False) and v != set() and v != frozenset()}
        self.say(f"camera {shown}" if shown else "camera")
        return Cam(self, kw)

    def finish(self, tag, kw):
        self.say(f"finish {tag} {sorted(kw.items())}")
        return session.Ending(Path("after.DAT"), [CHANGE], self.uploaded)

    def link_class(self):
        w = self

        class Link:
            def __init__(self, run, **kw):
                self.run = run
                w.say(f"link {sorted(kw)}" if kw else "link")

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                w.say("link closed")
                return False

            def press(self, key, **kw):
                w.say(f"press {key}" + (" (cleanup)" if kw.get("cleanup") else ""))

            def download(self, tag):
                w.n += 1
                p = Path(self.run.dir) / "dat" / f"{w.n:05d}_{tag}.DAT"
                p.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(fake_camlink.SAMPLE, p)
                w.say(f"download {tag}")
                return p

            def upload(self, path):
                w.say(f"upload {Path(path).name}")
                return "uploaded"

            def gone(self):
                return ""

            def in_playback(self):
                return False
        return Link


@pytest.fixture
def world(monkeypatch):
    return World(monkeypatch)


def run_main(monkeypatch, module, *argv):
    monkeypatch.setattr(sys, "argv", [f"{module.__name__}.py", *argv])
    module.main()


# ---------------------------------------------------------------- the manager itself, as the provers run it

def test_a_provers_session_as_the_provers_run_it(world, own_runs):
    from camkit.runs import Run
    world.wire()
    run = Run("kit2_pin")
    with runner.prover_session(run, Eyes(world, run)) as s:
        world.say("body")
    assert s.restored is True
    assert world.said == [
        "check readers", "link", "attach", "to_shooting: the start download", "download before",
        "lock wait (5 s at most)", "camera", "body", "to_shooting: the settings download after the rows",
        "finish after []", "link closed", "check ['eyes']", "eyes closed"]


def test_a_provers_session_whose_body_fails_closes_before_its_end(world, own_runs):
    from camkit.runs import Run
    world.wire()
    run = Run("kit2_pin")
    with runner.prover_session(run, Eyes(world, run), start_tag="bracket-before", settle=session.LOCK_S,
                               say_start=False, end_why="the restore", end_tag="end") as s:
        raise RuntimeError("a made-up failure")
    assert s.restored is True
    assert world.said == [
        "check readers", "link", "attach", "to_shooting: the start download", "download bracket-before",
        "lock wait (4.5 s at most)", "camera", "close", "to_shooting: the restore", "finish end []", "link closed",
        "check ['eyes']", "eyes closed"]


def test_the_managers_hooks_run_a_walkers_session_its_own_way(world, own_runs):
    """A walker's own way, each hook as it ran it by hand: no reader asked, no LiveCamera (a body that fails is said,
    and nothing closes it but the end's own reach), its own reach and lock watch at the start, its own reach at the
    end, the records said by key, what it writes once the start file is back on (before the link closes), and a check
    that does not watch the eyes for the restart."""
    from camkit.runs import Run
    world.wire()
    run = Run("kit2_pin")

    def reach(link, eyes, why):
        world.say(f"my reach: {why}")
    with runner.prover_session(run, Eyes(world, run), readers=False, camera=False, say_start=False,
                               reach=reach, start_why="the first download", lock=lambda eyes, since: world.say("my lock"),
                               end_reach=reach, end_why="the last download", show=0, keys=True,
                               on_end=lambda ending: world.say(f"on end {ending.after.name}"),
                               watch_restart=False) as s:
        assert s.cam is None
        raise RuntimeError("a made-up failure")
    assert s.restored is True and s.ending.after.name == "after.DAT"
    assert world.said == [
        "link", "attach", "my reach: the first download", "download before", "my lock", "my reach: the last download",
        "finish after [('keys', True), ('show', 0)]", "on end after.DAT", "link closed", "check ['keys', 'show']",
        "eyes closed"]


def test_a_walkers_body_closes_after_its_own_except(world, own_runs):
    """s.close(): the camera closed back to the shooting screen by the body itself (close_for_restore), then the end."""
    from camkit.runs import Run
    world.wire()
    run = Run("kit2_pin")
    with runner.prover_session(run, Eyes(world, run), say_start=False) as s:
        s.close()
    assert world.said[world.said.index("camera") + 1:] == [
        "close", "to_shooting: the settings download after the rows", "finish after []", "link closed",
        "check ['eyes']", "eyes closed"]


def test_a_start_whose_check_fails_ends_before_the_wait(world, tmp_path):
    """session_start's prepare(start): what a runner checks against the start file before anything is pressed; what it
    raises ends the start there, with no wait for the lock. Without it, the wait from the download's reply."""
    world.wire()
    link = world.link_class()(SimpleNamespace(dir=tmp_path))

    def wrong_body(start):
        world.say(f"check {start.name}")
        raise SystemExit("another camera")
    with pytest.raises(SystemExit, match="another camera"):
        runner.session_start(link, Eyes(world), tag="session", say=False, prepare=wrong_body)
    assert world.said == ["link", "to_shooting: the start download", "download session", "check 00001_session.DAT"]
    world.said.clear()
    start = runner.session_start(link, Eyes(world), "the settings download", say=False, settle=4.5)
    assert start.name == "00002_before.DAT"
    assert world.said == ["to_shooting: the settings download", "download before", "lock wait (4.5 s at most)"]


@pytest.mark.parametrize("kind", ["menu", "tiles", "shooting", "dialog"])
def test_a_walkers_reach_closes_a_plain_menu_page_alone_then_waits(world, tmp_path, kind):
    """close_menu_and_wait: MENU, a cleanup press, on a menu page or the Main tiles alone (on a dialog the wait asks for
    a hand), then the wait for the shooting screen, whose grace covers the menu closing: no fixed sleep between."""
    world.wire().kind = kind
    runner.close_menu_and_wait(world.link_class()(SimpleNamespace(dir=tmp_path)), Eyes(world), "the start download")
    menu = ["press menu (cleanup)"] if kind in ("menu", "tiles") else []
    assert world.said == ["link", *menu, "wait_for: the start download"]


# ---------------------------------------------------------------- the start download in one place

# the start tags the runners give their start downloads (and every tag given to the manager, collected below)
START_TAGS = {"before", "session", "p3-start", "before-set", "bracket-before"}
# runners whose session is still written out by hand, and why: each keeps the start downloads it had, no more
LEFT = {
    "kit/drive.py": "the owner's route (--owner, --network, the armed last press, a row's first open): its guard "
                    "tests fake the session's parts in drive.py itself, so a move could not be shown by them unchanged",
    "kit/crawl_run.py": "the first-open procedure: its guard tests (test_first_open, test_network_rows, "
                        "test_step3_acceptance) fake the session's parts in crawl_run.py itself",
    "kit/tools/take_picture.py": "the release: its guard tests (test_first_open) fake the session's parts in "
                                 "take_picture.py itself",
    "kit/provers/filter_run.py": "found after the review, outside this change's files: its own retrying download",
}

def kit_sources():
    for p in sorted(KIT.rglob("*.py")):
        if "tests" not in p.parts and "__pycache__" not in p.parts:
            yield p.relative_to(ROOT).as_posix(), ast.parse(p.read_text(encoding="utf-8"))


def called(node) -> str:
    f = node.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""


def literal_tags(node) -> set:
    """The string constants an argument can be: a constant, or either side of a conditional."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.IfExp):
        return literal_tags(node.body) | literal_tags(node.orelse)
    return set()


def given_tags(sources) -> set:
    """Every tag a runner gives the manager or its start (start_tag=, tag=, or in their places)."""
    tags = set()
    for _, tree in sources:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and called(node) in ("prover_session", "session_start"):
                for kw in node.keywords:
                    if kw.arg in ("start_tag", "tag"):
                        tags |= literal_tags(kw.value)
                place = 2 if called(node) == "prover_session" else 3
                if len(node.args) > place:
                    tags |= literal_tags(node.args[place])
    return tags


def test_no_runner_downloads_its_start_file_outside_the_session_manager():
    """The start download is made in one place, runner.session_start (runner.prover_session's start): a runner that
    downloads a start file of its own again (a download whose tag is one a session starts with: "before", "session",
    "p3-start", ...), and with it its own wait after it, fails here. The runners still written out by hand are named,
    each with why, and keep exactly the start downloads they had."""
    sources = list(kit_sources())
    tags = START_TAGS | given_tags(sources)
    found = {}
    for rel, tree in sources:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and called(node) == "download" and \
                    any(literal_tags(a) & tags for a in node.args):
                found.setdefault(rel, []).append(node.lineno)
    assert set(found) <= set(LEFT), {rel: lines for rel, lines in found.items() if rel not in LEFT}
    assert all(len(found.get(rel, ())) == 1 for rel in LEFT), {rel: found.get(rel) for rel in LEFT}


# ---------------------------------------------------------------- the walkers

def test_help_runs_session(world, monkeypatch):
    world.wire(help_run).kind = "menu"
    monkeypatch.setattr(help_run, "load_scan", lambda scan: ([], {}))
    monkeypatch.setattr(help_run, "walk", lambda cam, cycle, model, done, out, a: world.say("body"))
    run_main(monkeypatch, help_run, "--context", "Stills mode", "--run", "kit2_help_pin")
    assert world.said == [
        "check readers", "link", "attach", "press menu (cleanup)", "wait_for: the settings download",
        "download before", "lock wait (5 s at most)", "camera", "body", "close",
        "wait_for: the settings download after the walk", "finish after []", "link closed", "check []", "eyes closed"]


@pytest.mark.parametrize("found", [True, False])
def test_axis_walks_session(world, monkeypatch, found):
    world.wire(axis_walk)
    monkeypatch.setattr(axis_walk, "axis_options", lambda: {})
    monkeypatch.setattr(axis_walk, "load_scan", lambda scan: ([{"screen": "top"}] if found else [], {}))
    monkeypatch.setattr(axis_walk, "same_position", lambda a, b: True)
    monkeypatch.setattr(axis_walk, "menu_from_shooting", lambda cam, **k: world.say("menu"))
    run_main(monkeypatch, axis_walk)
    assert world.said == [
        "check readers", "link", "attach", "to_shooting: the settings download", "download before",
        "lock wait (5 s at most)", "camera", "menu", *([] if found else ["close"]),
        "to_shooting: the settings download after the walk",
        "finish after []", "link closed", "check []", "eyes closed"]


@pytest.mark.parametrize("stop", [False, True])
def test_table_walks_session(world, monkeypatch, stop):
    from camkit.link import StopRequested
    world.wire(table_walk)
    monkeypatch.setattr(table_walk, "load_scan", lambda scan: ([{"screen": "top"}], {}))
    monkeypatch.setattr(table_walk, "same_position", lambda a, b: True)

    def menu(cam, **k):
        world.say("menu")
        if stop:
            raise StopRequested("STOP file")
    monkeypatch.setattr(table_walk, "menu_from_shooting", menu)
    run_main(monkeypatch, table_walk, "--rows", "no such table")
    assert world.said == [
        "check readers", "link", "attach", "to_shooting: the settings download", "download before",
        "lock wait (5 s at most)", "camera", "menu", "close", "to_shooting: the settings download after the walk", "finish after []",
        "link closed", "check []", "eyes closed"]


def test_page_scans_session(world, monkeypatch):
    world.wire(page_scan)

    class Scan:
        def __init__(self, *a):
            pass

        def run_scan(self):
            world.say("body")
    monkeypatch.setattr(page_scan, "Scan", Scan)
    monkeypatch.setattr(page_scan, "after_download", lambda hdmi, done, mode=None: world.say(f"after_download {mode}"))
    run_main(monkeypatch, page_scan, "--mode", "Stills", "--run", "kit2_scan_pin")
    assert world.said == [
        "link", "attach", "to_shooting: the start download", "download before", "after_download Stills", "body",
        "to_shooting: the end of the scan", "finish after []", "link closed", "check []", "eyes closed"]


# ---------------------------------------------------------------- the tools and the provers

def test_card_actions_session(world, monkeypatch):
    world.wire(card_actions).kind = "menu"
    monkeypatch.setattr(card_actions, "load_scan", lambda scan: ([], {}))
    monkeypatch.setattr(card_actions, "to_row", lambda *a: (_ for _ in ()).throw(RuntimeError("off the scan")))
    run_main(monkeypatch, card_actions, "peek", "Create New Folder", "--allow", "Create New Folder")
    assert world.said == [
        "check readers", "link", "attach", "press menu (cleanup)", "wait_for: the settings download",
        "download before", "lock wait (5 s at most)", "camera {'may_open': ['Create New Folder']}", "close",
        "wait_for: the settings download after the action", "finish after [('show', 30)]", "link closed", "check []",
        "eyes closed"]


def test_my_menus_session(world, monkeypatch):
    from camkit import datafiles, definitions
    from proving.base import Failed
    world.wire(mymenu_run)
    doc = {"camera": {"my_menu": {"records": [f"r{i}" for i in range(mymenu_run.PAGES)]}}}
    monkeypatch.setattr(definitions, "active", lambda required=True: Path("made-up.json"))
    monkeypatch.setattr(definitions, "with_evidence", lambda d, p: doc)
    monkeypatch.setattr(definitions, "key", lambda d: "TEST-CAM_fw9.99")
    monkeypatch.setattr(datafiles, "stop_if_left", lambda key, who: None)
    monkeypatch.setattr(mymenu_run, "read_json", lambda p: {})
    monkeypatch.setattr(mymenu_run, "row_names", lambda camera: {})
    monkeypatch.setattr(mymenu_run, "load_scan", lambda scan: ([], {}))
    monkeypatch.setattr(mymenu_run, "menu_from_shooting", lambda cam, **k: world.say("menu"))
    monkeypatch.setattr(mymenu_run, "to_add_item", lambda *a: (_ for _ in ()).throw(Failed("off the scan")))
    run_main(monkeypatch, mymenu_run, "--allow", "Add Item")
    assert world.said == [
        "check readers", "link", "attach", "to_shooting: the start download", "download before",
        "lock wait (4.5 s at most)", "camera {'may_open': ['Add Item']}", "menu", "close",
        "to_shooting: the end of the fill", "finish after []", "link closed", "check []", "eyes closed"]


def prove_world(world, monkeypatch, kind="shooting", body=None, rows=1, status="done"):
    """prove_run's main over the made-up parts: `rows` list rows to prove, each session's body proving one row and
    returning `status` (all of them for "done"), the jobs made for `body` (the a1 II's by default). The tables and
    settings main() changes in place (another body's empties the a1 II's label tables) are the test's own copies."""
    import proving.jobs
    import proving.sidelists
    from camkit import coverage, models
    for name in ("LABELS", "ICON_ROWS", "DISP_MODES", "CYCLE", "MODEL", "FIRST"):
        monkeypatch.setattr(prove_run, name, type(getattr(prove_run, name))(getattr(prove_run, name)))
    for module, name in ((prove_run, "CONTEXT"), (prove_run, "LOOKS"), (proving.jobs, "HELP_TEXT"),
                         (proving.jobs, "OSD_ROWS"), (proving.sidelists, "SPREAD")):
        monkeypatch.setattr(module, name, getattr(module, name))
    world.wire(prove_run).kind = kind
    jobs = [{"kind": "list", "path": [f"Row {i}"], "labels": ["A", "B"]} for i in range(rows)]
    monkeypatch.setattr(prove_run.models, "current", lambda root: body or models.A1II)
    monkeypatch.setattr(prove_run, "jobs", lambda scope=None: [dict(j) for j in jobs])
    monkeypatch.setattr(prove_run, "axis_jobs", lambda scope=None: [])
    monkeypatch.setattr(prove_run, "load_scan", lambda scan, **k: ([], {}))
    monkeypatch.setattr(coverage, "prove_filter", lambda todo, a, planned: todo)
    monkeypatch.setattr(coverage, "prove_looks", lambda *a, **k: coverage.NO_LOOKS)

    def session(link, eyes, run, cycle, model, pending, start, out, failures):
        world.say("body")
        if status == "done":
            pending.clear()
        else:
            pending.pop(0)
        return status
    monkeypatch.setattr(prove_run, "session", session)


@pytest.mark.parametrize("kind", ["shooting", "menu"])
def test_prove_runs_session(world, monkeypatch, kind):
    prove_world(world, monkeypatch, kind)
    run_main(monkeypatch, prove_run)
    menu = ["press menu (cleanup)", "sleep 1"] if kind == "menu" else []
    assert world.said == [
        "check readers", "link", "attach", *menu, "to_shooting: the settings download", "download before",
        "lock wait (5 s at most)", "body", "to_shooting: the settings download after the rows", "finish after []",
        "link closed", "check ['eyes']", "eyes closed"]


def test_prove_run_stops_on_a_start_from_another_body_before_any_wait(world, monkeypatch, capsys):
    prove_world(world, monkeypatch, body="ILCE-7M4")
    run_main(monkeypatch, prove_run)
    assert world.said == ["check readers", "link", "attach", "to_shooting: the settings download", "download before",
                          "link closed", "eyes closed"]
    assert "the camera is a ILCE-1M2, the jobs were made for a ILCE-7M4: stopping" in capsys.readouterr().out


def test_prove_run_stops_on_a_later_session_off_its_start_file_before_any_wait(world, monkeypatch, capsys):
    from camkit import camset
    prove_world(world, monkeypatch, rows=2, status="failed")
    monkeypatch.setattr(camset, "diff", lambda a, b: [CHANGE])
    with pytest.raises(SystemExit) as stop:
        run_main(monkeypatch, prove_run)
    assert stop.value.code == runner.EXIT_UNRESTORED
    assert world.said == [
        "check readers", "link", "attach", "to_shooting: the settings download", "download before",
        "lock wait (5 s at most)", "body", "to_shooting: the settings download after the rows", "finish after []",
        "link closed", "check ['eyes']",
        "link", "attach", "to_shooting: the settings download", "download session", "link closed", "eyes closed"]
    assert "a new session does not start from the start file's settings: stopping" in capsys.readouterr().out


def test_pass_threes_switching_session(world, monkeypatch):
    world.wire(pass3_run)
    monkeypatch.setattr(pass3_run, "enter_state", lambda link, hdmi, run, cycle, model, b: world.say("switch") or [])
    monkeypatch.setattr(pass3_run, "switch_took", lambda ch, moved: "")
    monkeypatch.setattr(pass3_run, "walk_and_prove", lambda b, log: world.say("walk") or 0)
    monkeypatch.setattr(pass3_run, "restore", lambda run, start: world.say(f"restore {start.name}") or 0)
    from camkit.runs import Run
    blocker = {"row": ["Shutter Type"], "to": "Mechanical Shutter", "walk": "Long Exposure NR"}
    assert pass3_run.run_blockers(Run("kit2_pass3"), [], {}, [blocker], None) is True
    assert world.said == [
        "link", "attach", "to_shooting: the start download", "download p3-start", "lock wait (5 s at most)", "switch",
        "download p3-switched", "link closed", "eyes closed", "sleep 3", "walk", "sleep 3", "restore 00001_p3-start.DAT"]


def test_mode_switchs_session(world, monkeypatch):
    world.wire(mode_switch)
    monkeypatch.setattr(mode_switch, "load_scan", lambda scan: ([], {}))
    monkeypatch.setattr(mode_switch, "in_mode", lambda scan, mode: scan)
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: world.say("open menu"))
    monkeypatch.setattr(mode_switch, "dial_by_menu", lambda cam, cycle, model, say: world.say("dial by menu"))
    monkeypatch.setattr(mode_switch, "shoot_mode", lambda cam, cycle, model, f, m, say: world.say("shoot mode") or "P")
    monkeypatch.setattr(mode_switch, "close_screen", lambda cam, link: world.say("close screen"))
    monkeypatch.setattr(mode_switch.camset, "diff", lambda a, b: [CHANGE])
    run_main(monkeypatch, mode_switch, "--to", "Movie", "--run", "kit2_switch_pin")
    assert world.said == [
        "check readers", "link", "attach", "to_shooting: the start download", "download before",
        "lock wait (5 s at most)", "camera {'may_open': ['Accessibility']}", "open menu", "dial by menu", "close screen", "sleep 1", "open menu",
        "shoot mode", "close screen", "to_shooting: the download after the switch", "sleep 2", "download mode-Movie",
        "upload 00001_before.DAT", "link closed", "eyes closed", "verify"]


def test_mode_switchs_setting_session(world, monkeypatch, own_runs):
    from conftest import TEST_CAMERA
    world.wire(mode_switch)
    kept = own_runs / TEST_CAMERA / "kit2_switch_pin" / mode_switch.KEPT
    kept.parent.mkdir(parents=True)
    runner.write_json(kept, {"start": str(kept.parent / "00001_before.DAT"), "to": "Movie", "scan_mode": "Movie"})
    monkeypatch.setattr(mode_switch, "load_scan", lambda scan: ([], {}))
    monkeypatch.setattr(mode_switch, "in_mode", lambda scan, mode: scan)
    monkeypatch.setattr(mode_switch, "definition", lambda run=None: {})
    monkeypatch.setattr(mode_switch, "box_proofs", lambda run: {})
    monkeypatch.setattr(mode_switch, "set_plan", lambda sets, now, d, b: [(["Made-up Row"], "On", None)])
    monkeypatch.setattr(mode_switch, "open_menu", lambda cam: world.say("open menu"))
    monkeypatch.setattr(mode_switch, "set_row", lambda cam, cycle, model, path, option, say, mode=None:
                        world.say("set row"))
    monkeypatch.setattr(mode_switch, "close_screen", lambda cam, link: world.say("close screen"))
    monkeypatch.setattr(mode_switch.camset, "diff", lambda a, b: [CHANGE])
    run_main(monkeypatch, mode_switch, "--set", "Made-up Row=On", "--run", "kit2_switch_pin")
    assert world.said == [
        "check readers", "link", "attach", "to_shooting: the download before the settings", "download before-set",
        "lock wait (5 s at most)", "camera {'may_open': ['Accessibility']}", "open menu", "set row", "close screen", "sleep 1",
        "close screen", "to_shooting: the download after the settings", "sleep 2", "download after-set",
        "link closed", "eyes closed"]


def test_shoot_modes_first_session(world, monkeypatch, tmp_path):
    world.wire(shootmode_run)
    start = tmp_path / "00001_start.DAT"
    shutil.copy(fake_camlink.SAMPLE, start)
    monkeypatch.setattr(shootmode_run, "load_scan", lambda scan: ([], {}))
    monkeypatch.setattr(shootmode_run, "look", lambda cam, link, cycle, model, f: (_ for _ in ()).throw(
        RuntimeError("off the scan")))
    run_main(monkeypatch, shootmode_run, "--start", str(start), "--families", "0")
    assert world.said == [
        "check readers", "link", "attach", "to_shooting: the start download", "download before",
        "lock wait (5 s at most)", "camera", "close", "to_shooting: the restore after a stop", "finish stop []", "link closed", "check []", "eyes closed",
        "verify"]


def test_shoot_mode_stops_on_a_camera_off_its_start_file_before_any_wait(world, monkeypatch, tmp_path):
    from camkit import camset
    world.wire(shootmode_run)
    start = tmp_path / "00001_start.DAT"
    shutil.copy(fake_camlink.SAMPLE, start)
    monkeypatch.setattr(shootmode_run, "load_scan", lambda scan: ([], {}))
    monkeypatch.setattr(camset, "diff", lambda a, b: [CHANGE])
    with pytest.raises(SystemExit, match="the camera is not on 00001_start.DAT \\(1 records differ\\): load it first"):
        run_main(monkeypatch, shootmode_run, "--start", str(start), "--families", "0")
    assert world.said == ["check readers", "link", "attach", "to_shooting: the start download", "download before",
                          "link closed", "eyes closed"]


def test_the_grids_wait_after_its_download(world, monkeypatch, tmp_path):
    world.wire(grid_run)
    monkeypatch.setattr(grid_run, "open_grid", lambda cam, cycle, model, path: world.say("open grid"))
    monkeypatch.setattr(grid_run, "to_ok", lambda cam: None)
    monkeypatch.setattr(grid_run, "lines", lambda cam: [])
    monkeypatch.setattr(grid_run, "later", lambda f, cam: None)
    monkeypatch.setattr(grid_run, "after_ok", lambda cam, row, refusal=None: SimpleNamespace(notice=None, applied=True))
    link = world.link_class()(SimpleNamespace(dir=tmp_path))
    got = grid_run.visit(Cam(world, {}), link, Eyes(world), [], {}, ["Focus Area Limit"], ["A", "B"], [])
    assert got["applied"] is True
    assert world.said == ["link", "open grid", "cam enter", "to_shooting: the download after OK", "sleep 1",
                          "download Focus Area Limit-cells", "lock wait (4.5 s at most)"]
