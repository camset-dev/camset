"""carousel_fields_run.title_reads with a short title (mv_selftimer_prove, 2026-11-20): the movie Self-timer's carousel
showed "On" (kit2_pass2 277154, 277160), OCR read it exactly, but its one doubt, a short word, sent it to the second
reader, which named no option of the carousel (the strip's "3s", as on 270328); the title was taken for none, Down went
round twice and the run stopped ("On never came up in the carousel ()"). OCR's exact reading now stands where its only
doubt is shortness and the reader names no option at all; a reader naming an option is taken as before (the owner's
rule: the reader is right where OCR mangles short text). The run's own frames read by the kit's OCR where this clone
has them, the reader made up. Nothing talks to a camera."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import carousel_fields_run as F  # noqa: E402
from camkit import paths, screen  # noqa: E402

LABELS = ["On", "Off"]                     # kit2_crawl_mv_selftimer/map.json's Self-timer carousel


def cam_of(name):
    f = paths.a1ii_root() / "kit2_pass2" / "shots" / name
    if not f.exists():
        pytest.skip(f"{name} is not here")
    from camkit.frames import load
    frame = load(f)
    return SimpleNamespace(frame=frame, read=lambda: screen.read(frame))


@pytest.fixture(autouse=True)
def settled(monkeypatch):
    monkeypatch.setattr(F, "title_settled", lambda cam: None)


@pytest.mark.parametrize("reader, named, by", [("3 s", "On", "ocr"), ("3s", "On", "ocr"), ("On", "On", "reader"),
                                              ("Off", "Off", "reader")])
def test_the_runs_short_on_stands_where_the_reader_names_no_option(monkeypatch, reader, named, by):
    cam = cam_of("277154_down.png")
    monkeypatch.setattr(F, "vlm_option", lambda c: reader)
    assert F.title_reads(cam, LABELS) == named
    assert F.TITLE_READ["title"] == named and F.TITLE_READ["by"] == by


def test_every_title_read_is_logged_with_both_readings(monkeypatch):
    cam = cam_of("277154_down.png")
    logged = []
    cam.run = SimpleNamespace(log=lambda kind, **kw: logged.append((kind, kw)))
    monkeypatch.setattr(F, "vlm_option", lambda c: "3 s")
    F.title_reads(cam, LABELS)
    assert logged == [("title_read", {"frame": "277154_down.png", "ocr": "On", "reader": "3 s", "taken": "On"})]


def test_a_reader_that_does_not_answer_leaves_a_short_title_unread(monkeypatch):
    cam = cam_of("277154_down.png")
    monkeypatch.setattr(F, "vlm_option", lambda c: None)
    assert F.title_reads(cam, LABELS) is None


def test_the_option_is_found_on_the_runs_frames(monkeypatch):
    """option_refused on the run's On frame: the option lit, no box lit, the title read as On."""
    cam = cam_of("277160_down.png")
    monkeypatch.setattr(F, "vlm_option", lambda c: "3 s")
    assert F.option_refused(cam, "On", LABELS) == ""
    assert F.option_refused(cam_of("277157_down.png"), "On", LABELS) != ""
