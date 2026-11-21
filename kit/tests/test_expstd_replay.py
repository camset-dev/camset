"""Exposure Std. Adjust's path behind its own question, replayed through the kit's real code in the camera's real order
on saved frames (2026-11-21). expstd_movie_sqc's crawl in Movie answered the question for the first time (the camera's
own check took the Enter), then left the screen behind it unwalked ("notice passed: a submenu screen after its OK, left
unwalked"), so the proofs had no map: camkit.crawl.visit_row walked only what WALKERS knows behind a passed notice, as an
--info-ok notice's screen is, never a submenu. Now the row's own question (pass_row_question's "by") opens the row's own
screen, crawled as any submenu is.

The frames: Movie's own up to the screen behind the question (kit2_crawl_expstd_mvc 00013 the row lit, 00014 its
question with Cancel lit, 00015 OK lit after Up, 00016 the five rows, Multi lit); behind that, frames of the same screens
from the Stills runs, the only ones that hold them (kit2_drive: the five rows lit, 01305 to 01308; Entire Screen
Average's list 01219 to 01231 and Highlight's 01309 to 01321, thirteen values each, Down at the last wrapping to the
first as every list does). Multi's, Center's and Spot's lists were never saved: Entire Screen Average's stands in for
them (a list walk asks only for a list). MENU on a list goes back to its row; MENU on the five rows goes back to the
row that opened them, as Movie's own frame shows (kit2_crawl_expstd_mvc 00017), and so does Left. The second reader answers the menu question with the row each frame lights. Nothing talks to a
camera."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kit"))
sys.path.insert(1, str(ROOT / "kit" / "tests"))
from replay_world import FrameWorld, camera, shot  # noqa: E402

ROW = "Exposure Std. Adjust"
FIVE = ["Multi", "Center", "Spot", "Entire Screen Average", "Highlight"]
MV, DR = "kit2_crawl_expstd_mvc/shots/", "kit2_drive/shots/"
LIT = {"00013_down.png": ROW, "00016_enter.png": "Multi", "01305_down.png": "Center", "01306_down.png": "Spot",
       "01307_down.png": "Entire Screen Average", "01308_down.png": "Highlight"}


def a_list(tag: str, first: int, row: str) -> dict:
    """A thirteen-value list's states, from its saved frames first..first+12, Down wrapping, MENU back to `row`."""
    n = [first + i for i in range(13)]
    out = {}
    for i, f in enumerate(n):
        name = next(Path(shot(f"{DR}{f:05d}_right.png" if i == 0 else f"{DR}{f:05d}_down.png")).parent.glob(f"{f:05d}_*.png"))
        out[f"{tag}{i}"] = (name, {"down": f"{tag}{(i + 1) % 13}", "up": f"{tag}{(i - 1) % 13}", "menu": row})
    return out


def world_graph() -> dict:
    g = {"row": (shot(MV + "00013_down.png"), {"right": "q_cancel"}),
         "q_cancel": (shot(MV + "00014_right.png"), {"up": "q_ok", "menu": "row"}),
         "q_ok": (shot(MV + "00015_up.png"), {"enter": "multi", "menu": "row"}),
         "multi": (shot(MV + "00016_enter.png"), {"down": "center", "right": "lm0", "left": "row", "menu": "row"}),
         "center": (shot(DR + "01305_down.png"), {"down": "spot", "right": "lc0", "left": "row", "menu": "row"}),
         "spot": (shot(DR + "01306_down.png"), {"down": "esa", "right": "ls0", "left": "row", "menu": "row"}),
         "esa": (shot(DR + "01307_down.png"), {"down": "highlight", "right": "le0", "left": "row", "menu": "row"}),
         "highlight": (shot(DR + "01308_down.png"), {"down": "multi", "right": "lh0", "left": "row", "menu": "row"})}
    for tag, row in (("lm", "multi"), ("lc", "center"), ("ls", "spot"), ("le", "esa")):
        g.update(a_list(tag, 1219, row))
    g.update(a_list("lh", 1309, "highlight"))
    return g


@pytest.fixture
def replay(monkeypatch, tmp_path):
    from camkit import live, vlm
    from proving import base, screens

    def ask_role(role, image, prompt, timeout=None, **kw):
        import hashlib
        h = hashlib.sha1(image).hexdigest()
        lit = next((v for k, v in KNOWN.items() if k == h), None)
        if lit is None:
            raise RuntimeError("the replay's reader knows no row on this frame")
        return {"rows": [{"label": lit, "highlighted": True}]}
    KNOWN = {}
    for name, label in LIT.items():
        p = shot((MV if name.startswith("000") else DR) + name)
        import hashlib
        KNOWN[hashlib.sha1(p.read_bytes()).hexdigest()] = label
    monkeypatch.setattr(vlm, "ask_role", ask_role)
    monkeypatch.setattr(live, "ask_role", ask_role, raising=False)
    monkeypatch.setattr(screens, "ask_role", ask_role, raising=False)
    monkeypatch.setattr(screens, "ROW_QUESTION", {ROW})
    monkeypatch.setattr(base, "ROW_BY", {})

    def make(start="row"):
        w = FrameWorld(world_graph(), start)
        return w, camera(w, tmp_path)
    return make


def ocr_labels(cam):
    """The crawl's label reader without the reader's call (camkit.live.PageLabels' OCR half): the page key and each
    visible row's name as OCR reads it."""
    from camkit import live, ocr, screen
    f, s = cam.frame, cam.read()
    return screen.rows_key(f.image), live.submenu_texts(ocr.read([f.path])[f.path], s)


def events(cam) -> list:
    import json
    p = cam.run.dir / "events.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def test_the_crawl_walks_the_five_rows_behind_the_answered_question(replay):
    import crawl_run
    from camkit import crawl
    w, live_cam = replay()
    cam = crawl.Counted(live_cam)
    s = cam.read()
    r = crawl.visit_row(cam, s, {"page": ""}, s.row or 0, {"label": ROW}, labels=ocr_labels, path=(),
                        info_ok=crawl_run.info_ok_pass({}, frozenset({ROW})))
    keys = [k for k, _ in w.sent]
    assert keys[:3] == ["right", "up", "enter"] and keys.count("enter") == 1          # the question's OK alone
    assert r.info_ok and r.outcome == "submenu crawled", r.outcome
    rows = [(x.label, x.outcome) for x in r.walk.rows]
    # OCR alone reads the rows' icons as a bullet ("•Center"): the crawl's label reader asks the second reader too, and
    # the labels pass (kit/pass1_labels.py) settles each label; the rows are the five
    assert [lab.lstrip("• ") for lab, _ in rows] == FIVE, rows
    assert all(out == "walked" for _, out in rows), rows
    assert keys[-1] == "left" and w.state == "row"                                    # back on the row that opened them
    passed = [e for e in events(live_cam) if e["kind"] == "enter_passed"]
    assert len(passed) == 1 and ROW in passed[0]["by"]


def test_an_info_ok_notice_still_leaves_a_submenu_behind_it_unwalked(replay, monkeypatch):
    from camkit import crawl
    w, live_cam = replay()
    cam = crawl.Counted(live_cam)
    s = cam.read()

    def info_ok(c, name, before):           # an --info-ok pass: no "by"
        from proving import screens
        got = screens.pass_row_question(c, name, ROW, before)
        return {k: v for k, v in got.items() if k != "by"}
    r = crawl.visit_row(cam, s, {"page": ""}, s.row or 0, {"label": ROW}, labels=ocr_labels, path=(), info_ok=info_ok)
    assert r.outcome.startswith("notice passed: a submenu screen after its OK, left unwalked")


@pytest.mark.parametrize("target, downs", [("Multi", 0), ("Highlight", 4)])
def test_the_proofs_way_in_answers_the_question_on_the_live_camera_and_finds_the_row(replay, target, downs):
    """prove_run's way to each row (proving.nav.enter_path on the unwrapped LiveCamera, as prove_run gives it): Right,
    the question passed by pass_row_question and judged again by the camera (row_question_passed on the frame read
    afresh), then find_row Down to the row."""
    from proving import nav
    w, cam = replay()
    nav.enter_path(cam, [ROW, target], 0)
    keys = [k for k, _ in w.sent]
    assert keys == ["right", "up", "enter"] + ["down"] * downs, keys
    assert w.state == ("multi" if target == "Multi" else "highlight")
    assert [e for e in events(cam) if e["kind"] == "enter_passed"][-1]["by"].startswith(f"--allow {ROW!r}")


def test_each_visit_meets_the_question_again_and_answers_it_once_each(replay):
    """A proof re-enters the row for every value: the question comes back each time, and each answer is its own,
    the way past spent by its press."""
    from proving import nav
    w, cam = replay()
    nav.enter_path(cam, [ROW, "Spot"], 0)
    cam.press("left")                                   # back on the row (the replay's stand-in for MENU and the walk back)
    assert w.state == "row"
    nav.enter_path(cam, [ROW, "Highlight"], 0)
    keys = [k for k, _ in w.sent]
    assert keys == ["right", "up", "enter", "down", "down", "left", "right", "up", "enter", "down", "down", "down", "down"]
    assert len([e for e in events(cam) if e["kind"] == "enter_passed"]) == 2
    assert cam.confirm_once is False                    # nothing left over for a later press
