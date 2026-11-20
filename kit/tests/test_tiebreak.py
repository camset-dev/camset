"""kit/tiebreak.py and the pass-1 label vote (kit/pass1_map.py) with several third readers: each asked in turn while
no reading stands, one vote per model family, the line's readings and models kept; --revote asks today's third readers
about lines already there, the old third reader's reading kept as its model's. No reader is contacted: the readers are
fakes built where camkit.vlm builds them (vlm.Reader), so the local-only rule still applies."""
import json
import sys
from pathlib import Path

import pytest

KIT = Path(__file__).resolve().parents[1]
for p in (KIT, KIT / "provers"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

QWEN, QWEN_OLD = "ggml-org/Qwen3.8-27B-Q4_K_M", "Qwen3.8-27B-4bit"
GEMMA, GLM = "ggml-org/gemma-4-26B-A4B-it-Q4_0", "ggml-org/GLM-4.6V-Flash-Q4_K_M"


def lan(name, model, host="127.0.0.1"):
    return {"name": name, "url": f"http://{host}:8080/v1", "model": model, "parallel": 4}


@pytest.fixture
def bench(tmp_path, monkeypatch):
    """A run folder with option frames and its options.jsonl (write_options), a private/config.json (config), and the
    readers faked: said[(reader name, frame name)] is what each reads, asked lists (reader, frame) in order, built the
    readers built."""
    import camkit
    from camkit import vlm
    run = tmp_path / "kit2_crawl"
    (run / "shots").mkdir(parents=True)
    said, asked, built = {}, [], []

    class Fake:
        def __init__(self, name=None, model=None, **kw):
            built.append(name)
            self.name, self.model, self.served = name, model, None

        def ask(self, image, prompt):
            assert prompt == vlm.PROMPTS["option"]
            frame = image.decode()
            asked.append((self.name, frame))
            got = said.get((self.name, frame))
            if isinstance(got, BaseException):
                raise got
            return {"selected": got}
    monkeypatch.setattr(vlm, "Reader", Fake)
    monkeypatch.setattr(camkit, "CONFIG", tmp_path / "config.json")
    vlm.forget()
    import tiebreak as t
    monkeypatch.setattr(t, "_FAILS", {})

    def config(readers, roles=None):
        camkit.CONFIG.write_text(json.dumps({"readers": readers, **({"roles": roles} if roles else {})}),
                                 encoding="utf-8")

    def write_options(*rows):
        """rows: (frame, ocr, second reader's reading[, network])."""
        recs = []
        for i, (frame, o, v, *net) in enumerate(rows):
            (run / "shots" / frame).write_bytes(frame.encode())
            recs.append({"frame": frame, "path": ["Drive Mode"], "index": i, "kind": "list", "agreed": False, "ocr": o,
                         "vlm": {"selected": v}, **({"network": net[0]} if net else {})})
        (run / "options.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    yield types_ns(run=run, said=said, asked=asked, built=built, config=config, options=write_options)
    vlm.forget()


def types_ns(**kw):
    import types
    return types.SimpleNamespace(**kw)


def lines(run: Path) -> list:
    return [json.loads(x) for x in (run / "tiebreak.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]


def tiebreak(run: Path, *args):
    import tiebreak as t
    t.main([str(run), *args])


# ------------------------------------------------------------------------------------------------ the vote

def test_the_majority_counts_one_vote_per_family_and_no_majority_is_no_reading():
    """Four voices, OCR, the second reader and two third readers: a reading stands with two sources behind it and no
    other reading named as often; two readers of one family are one source, and none where they read two things (the
    review of 2026-11-19: one model reading two things was a vote on each side); a tie, or one source alone, is no
    reading. The reading kept is OCR's, else the second reader's, else a third reader's."""
    import pass1_map as M

    def line(o, v, m, *more, old=QWEN):
        return {"ocr": o, "vllm": v, "omlx": m, "models": {"vllm": QWEN, "omlx": old},
                "voters": [{"reader": n, "model": mod, "selected": s} for n, mod, s in more]}
    assert M.majority(M.voices(line("Single", "Cont.", "Cont."))) == (None, ())            # one family against OCR
    assert M.majority(M.voices(line("Single", "Cont.", "Single"))) == (None, ())            # one family, two readings
    gemma2 = ("gemma2", "unsloth/gemma-4-26B-A4B-it-Q8_0", "Single")                     # two gemma builds disagree
    assert M.majority(M.voices(line("Single", "Cont.", "Timer", gemma2, old=GEMMA))) == (None, ())
    assert M.majority(M.voices(line("Single", "Cont.", "Single", ("gemma", GEMMA, "Single")))) == (
        "Single", ("ocr", "gemma"))                                                         # OCR and another model
    assert M.majority(M.voices(line("Single", "Cont.", "Cont.", ("gemma", GEMMA, "Cont.")))) == (
        "Cont.", ("vllm", "omlx", "gemma"))
    assert M.majority(M.voices(line("Single", "Cont.", "Cont.", ("gemma", GEMMA, "Single")))) == (
        "Single", ("ocr", "gemma"))
    four = line("Single", "Cont.", "Timer", ("glm", GLM, "Cont."), old=GEMMA)              # 2 of 4, others one each
    assert M.majority(M.voices(four)) == ("Cont.", ("vllm", "glm"))
    split = line("Single", "Cont.", "Single", ("glm", GLM, "Cont."), old=GEMMA)           # two against two
    assert M.majority(M.voices(split)) == (None, ())
    assert M.majority(M.voices(line("Single", "Cont.", "Timer", ("glm", GLM, "Bracket"), old=GEMMA))) == (None, ())
    assert M.majority(M.voices(line("", "Cont.", "Cont.", ("glm", GLM, ""), old=GEMMA)))[0] == "Cont."
    assert M.tie_label(four) == ("Cont.", "majority of four")
    alone = line("Single", "Cont.", "Timer", ("glm", GLM, "Timer"), old=GEMMA)              # neither OCR nor the second
    assert M.majority(M.voices(alone)) == ("Timer", ("omlx", "glm"))
    assert M.tie_label(alone) == (None, "unresolved, third readers alone")                  # never on them alone
    assert M.settled(alone) is None and M.settled(four) == "Cont."
    # the second reader's own reading, carried by two third readers where its family read two things: not "alone"
    given = line("Single", "Cont.", "Single", ("gemma", GEMMA, "Cont."), ("glm", GLM, "Cont."))
    assert M.majority(M.voices(given)) == ("Cont.", ("gemma", "glm")) and M.tie_label(given) == ("Cont.", "majority of five")
    assert M.tie_label({"ocr": "a", "vllm": "b", "omlx": "b", "winner": "b"}) == ("b", "majority of three")  # as written
    assert M.tie_label({"ocr": "a", "vllm": "b", "omlx": "c", "winner": None}) == (None, "majority of three")


# ------------------------------------------------------------------------------------------------ new lines

def test_new_lines_ask_the_third_readers_in_turn_and_keep_each_reading_and_model(bench, capsys):
    """Each option the first two read apart: the third readers in turn while no reading stands by family, the first that
    answers under "omlx", the next under "voters"; each line names the models that read it, and its winner is the
    majority. A third reader of the second's family is never asked, for it could make no reading stand. A reading third
    readers alone carry is marked and listed, with no winner (decision 22: 7 of 10 such were wrong)."""
    b = bench
    b.config([lan("vllm", QWEN), lan("gemma", GEMMA), lan("glm", GLM), lan("omlx", QWEN_OLD)],
             roles={"second": "vllm", "third": ["gemma", "omlx", "glm"]})
    b.options(("00001_down.png", "Single", "Cont."), ("00002_down.png", "Single", "Cont."),
              ("00003_down.png", "Single", "Cont."), ("00004_down.png", "Single", "Cont."))
    b.said.update({("gemma", "00001_down.png"): "Single",                      # settles it: the rest not asked
                   ("gemma", "00002_down.png"): "Timer", ("glm", "00002_down.png"): "Cont.",
                   ("gemma", "00003_down.png"): "Timer", ("glm", "00003_down.png"): "Bracket",
                   ("gemma", "00004_down.png"): "Timer", ("glm", "00004_down.png"): "Timer"})
    tiebreak(b.run)
    got = lines(b.run)
    assert [t["winner"] for t in got] == ["Single", "Cont.", None, None]
    assert b.asked == [("gemma", "00001_down.png"), ("gemma", "00002_down.png"), ("glm", "00002_down.png"),
                       ("gemma", "00003_down.png"), ("glm", "00003_down.png"), ("gemma", "00004_down.png"),
                       ("glm", "00004_down.png")]                             # omlx is the second's family: never
    assert got[3]["third_only"] is True and not any("third_only" in t for t in got[:3])
    out = capsys.readouterr().out
    assert "1 lines third readers alone named" in out and "third readers alone: kit2_crawl 00004_down.png index 3" in out
    assert got[3]["omlx"] == "Timer" and got[3]["voters"] == [{"reader": "glm", "model": GLM, "selected": "Timer"}]
    assert got[0] == {"frame": "00001_down.png", "path": ["Drive Mode"], "index": 0, "ocr": "Single", "vllm": "Cont.",
                      "models": {"vllm": QWEN, "omlx": GEMMA}, "omlx": "Single", "winner": "Single"}
    assert got[1]["voters"] == [{"reader": "glm", "model": GLM, "selected": "Cont."}]
    assert "third readers, asked in turn: 'gemma' (gemma-4-26b-a4b-it), 'omlx' (qwen3.8-27b), 'glm'" in out
    b.asked.clear()
    tiebreak(b.run)                                                            # options already there: skipped
    assert b.asked == [] and len(lines(b.run)) == 4


def test_new_lines_with_one_third_reader(bench, capsys):
    """A config with no "roles": the second reader listed is the third. Of another model it is asked about every option
    apart, and the line holds what it held, with its models beside; of the second's own model (two builds of one) it is
    never asked, for it could make no reading stand, and nothing is written: a rerun with a third reader of another
    model asks those options."""
    b = bench
    b.config([lan("vllm", QWEN), lan("gemma", GEMMA)])
    b.options(("00001_down.png", "Single", "Cont."), ("00002_down.png", "Single", "Cont."))
    b.said.update({("gemma", "00001_down.png"): "Single", ("gemma", "00002_down.png"): "Cont."})
    tiebreak(b.run)
    got = lines(b.run)
    assert [(t["ocr"], t["vllm"], t["omlx"], "voters" in t) for t in got] == [("Single", "Cont.", "Single", False),
                                                                              ("Single", "Cont.", "Cont.", False)]
    assert b.built == ["gemma"] and [t["winner"] for t in got] == ["Single", "Cont."]
    (b.run / "tiebreak.jsonl").unlink()
    b.asked.clear()
    capsys.readouterr()
    b.config([lan("vllm", QWEN), lan("omlx", QWEN_OLD)])
    tiebreak(b.run)
    assert b.asked == [] and not (b.run / "tiebreak.jsonl").exists()
    assert "2 to tie-break: 0 written; left for a rerun, 0 that no third reader answered, 2 with no third reader of " \
        "another family" in capsys.readouterr().out


def test_a_third_reader_that_is_not_local_is_left_out_of_a_network_runs_frames(bench, capsys):
    """A --network run's frames go to local readers only: a third reader that is not local is left out, said, and the
    others asked; with none left, the tool stops, nothing written."""
    from camkit import vlm
    b = bench
    vlm.mark_local_only(b.run)
    hosted = {**lan("cloud", GEMMA), "url": "https://api.example.com/v1"}
    b.config([lan("vllm", QWEN), hosted, lan("glm", GLM)], roles={"second": "vllm", "third": ["cloud", "glm"]})
    b.options(("00001_down.png", "Single", "Cont."))
    b.said[("glm", "00001_down.png")] = "Single"
    tiebreak(b.run)
    assert "reader 'cloud' is not a local reader" in capsys.readouterr().out and b.built == ["glm"]
    assert lines(b.run)[0]["omlx"] == "Single" and lines(b.run)[0]["models"]["omlx"] == GLM
    b.config([lan("vllm", QWEN), hosted], roles={"second": "vllm", "third": ["cloud"]})
    (b.run / "tiebreak.jsonl").unlink()
    with pytest.raises(SystemExit, match="not a local reader"):
        tiebreak(b.run)
    assert not (b.run / "tiebreak.jsonl").exists()


# ------------------------------------------------------------------------------------------------ --revote

def old_lines(b, *rows):
    """tiebreak.jsonl as the kit wrote it before lines named their models: (frame, ocr, second, third, winner)."""
    b.options(*[(f, o, v) for f, o, v, *_ in rows])
    (b.run / "tiebreak.jsonl").write_text("".join(
        json.dumps({"frame": f, "path": ["Drive Mode"], "index": i, "ocr": o, "vllm": v, "omlx": m, "winner": w}) + "\n"
        for i, (f, o, v, m, w) in enumerate(rows)), encoding="utf-8")


def test_revote_asks_todays_third_readers_where_no_reading_stands_by_family_and_keeps_what_lines_held(bench, capsys):
    """Lines written when the second and third readers were one model in two builds: --revote needs the old third's
    model (--was), keeps its reading as that model's, and asks today's third readers, in turn, wherever no reading
    stands by family: two builds against OCR, and two builds that read two things (no vote at all) beside OCR. A
    reading third readers alone carry is marked, given no winner and listed by run, frame and index. The file is
    written afresh, the
    old one kept beside it; a second --revote asks only a third reader that gave no answer."""
    b = bench
    b.config([lan("vllm", QWEN), lan("gemma", GEMMA), lan("glm", GLM)],
             roles={"second": "vllm", "third": ["gemma", "glm"]})
    old_lines(b, ("00001_down.png", "Single", "Cont.", "Cont.", "Cont."),        # one family against OCR
              ("00002_down.png", "Single", "Cont.", "Single", "Single"),         # one family on two sides: no vote
              ("00003_down.png", "Single", "Cont.", "Cont.", "Cont."),
              ("00004_down.png", "Single", "Cont.", "Timer", None),              # no winner: asked too
              ("00005_down.png", "Single", "Cont.", "Cont.", "Cont."))
    before = (b.run / "tiebreak.jsonl").read_text(encoding="utf-8")
    with pytest.raises(SystemExit, match="5 lines of tiebreak.jsonl name no models.*give --was MODEL"):
        tiebreak(b.run, "--revote")
    assert b.asked == [] and (b.run / "tiebreak.jsonl").read_text(encoding="utf-8") == before
    with pytest.raises(SystemExit, match="--was goes with --revote"):
        tiebreak(b.run, "--was", QWEN_OLD)
    b.said.update({("gemma", "00001_down.png"): "Single",                           # sides with OCR: overturned
                   ("gemma", "00002_down.png"): "Single",
                   ("gemma", "00003_down.png"): "Timer", ("glm", "00003_down.png"): "Cont.",
                   ("gemma", "00004_down.png"): "Timer", ("glm", "00004_down.png"): "",   # an empty reading: no answer
                   ("gemma", "00005_down.png"): "Self-timer", ("glm", "00005_down.png"): "Self-timer"})
    tiebreak(b.run, "--revote", "--was", QWEN_OLD)
    got = lines(b.run)
    # line 4: Timer by gemma alone, the old third's Timer no vote now (its family read Cont. too)
    assert [t["winner"] for t in got] == ["Single", "Single", "Cont.", None, None]
    assert b.asked == [("gemma", "00001_down.png"), ("gemma", "00002_down.png"), ("gemma", "00003_down.png"),
                       ("glm", "00003_down.png"), ("gemma", "00004_down.png"), ("glm", "00004_down.png"),
                       ("gemma", "00005_down.png"), ("glm", "00005_down.png")]
    assert all(t["models"] == {"vllm": QWEN, "omlx": QWEN_OLD} for t in got)
    assert [t["omlx"] for t in got] == ["Cont.", "Single", "Cont.", "Timer", "Cont."]          # the old third's, kept
    assert got[2]["voters"] == [{"reader": "gemma", "model": GEMMA, "selected": "Timer"},
                                {"reader": "glm", "model": GLM, "selected": "Cont."}]
    assert got[3]["voters"] == [{"reader": "gemma", "model": GEMMA, "selected": "Timer"}]
    assert got[4]["third_only"] is True and not any("third_only" in t for t in got[:4])
    assert (b.run / "tiebreak.jsonl.before_revote").read_text(encoding="utf-8") == before
    out = capsys.readouterr().out
    assert ("5 lines: 5 answered by a third reader of today; kept as they were for a later --revote, 0 that none answered "
            "(0 of them with no frame under shots/) and 0 with no third reader of another family to ask; 2 with another "
            "winner than before") in out
    assert "1 lines third readers alone named" in out and "third readers alone: kit2_crawl 00005_down.png index 4" in out
    b.asked.clear()
    tiebreak(b.run, "--revote")                            # every line names its models now: --was not needed
    assert b.asked == [("glm", "00004_down.png")] and lines(b.run) == got     # only the reader that gave no answer
    assert (b.run / "tiebreak.jsonl.before_revote").read_text(encoding="utf-8") == before


def test_revote_keeps_a_line_no_third_reader_answered_as_it_was_and_stops_asking_one_that_keeps_failing(bench, capsys):
    """A third reader that fails (its server off) is no vote: a line none of today's third readers answered is kept as
    it was, its old winner with it, for a later --revote to ask again, never marked as voted and left with no
    majority; after FAIL_RUN failures in a row a reader is asked nothing more in the run. One that answers later
    adds its vote then."""
    import urllib.error

    import tiebreak as t
    b = bench
    b.config([lan("vllm", QWEN), lan("gemma", GEMMA), lan("glm", GLM)],
             roles={"second": "vllm", "third": ["gemma", "glm"]})
    rows = [(f"0000{n}_down.png", "Single", "Cont.", "Cont.", "Cont.") for n in range(1, 6)]
    old_lines(b, *rows)
    before = lines(b.run)
    off = urllib.error.URLError(ConnectionRefusedError("refused"))
    b.said.update({(r, f): off for r in ("gemma", "glm") for f, *_ in rows})
    tiebreak(b.run, "--revote", "--was", QWEN_OLD)
    assert lines(b.run) == before
    assert [a for a in b.asked if a[0] == "gemma"] == [("gemma", f) for f, *_ in rows[:t.FAIL_RUN]]
    out = capsys.readouterr().out
    assert f"reader 'gemma' failed {t.FAIL_RUN} times in a row" in out and "5 that none answered" in out
    t._FAILS.clear()
    b.asked.clear()
    b.said[("gemma", rows[0][0])] = "Single"               # the server back: asked again, and its vote counts
    tiebreak(b.run, "--revote", "--was", QWEN_OLD)
    got = lines(b.run)
    assert got[0]["winner"] == "Single" and got[0]["voters"] == [{"reader": "gemma", "model": GEMMA, "selected": "Single"}]
    assert got[1:] == before[1:] and ("gemma", rows[0][0]) in b.asked


def test_revote_never_asks_about_an_identity_rows_option(bench):
    from camkit import safety
    b = bench
    b.config([lan("vllm", QWEN), lan("gemma", GEMMA)], roles={"second": "vllm", "third": ["gemma"]})
    old_lines(b, ("00001_down.png", "Single", "Cont.", "Cont.", "Cont."))
    b.options(("00001_down.png", "Single", "Cont.", safety.LIFT_IDENTITY))
    tiebreak(b.run, "--revote", "--was", QWEN_OLD)
    assert b.asked == [] and lines(b.run)[0]["winner"] is None and "voters" not in lines(b.run)[0]


# ------------------------------------------------------------------------------------------------ the map

def test_the_map_takes_the_majority_by_family_and_lists_every_voice_for_review(bench, capsys):
    """pass1_map: a line that names its models is voted afresh, by family ("majority of four" with four voices); one
    with no majority goes on the review list with each third reader's reading; a line written before lines named
    models keeps the winner it was written with, said once per crawl. An option third readers alone named gets no label
    from the vote: it goes on the review list with every voice's reading, told apart in
    its source and listed by frame, for a look by eye."""
    import pass1_map
    b = bench
    b.options(("00001_down.png", "Single", "Cont."), ("00002_down.png", "Single", "Cont."),
              ("00003_down.png", "Single", "Cont."), ("00004_down.png", "Single", "Cont."))
    ties = [{"frame": "00001_down.png", "ocr": "Single", "vllm": "Cont.", "omlx": "Cont.", "winner": "Cont.",
             "models": {"vllm": QWEN, "omlx": QWEN_OLD},
             "voters": [{"reader": "gemma", "model": GEMMA, "selected": "Single"}]},
            {"frame": "00002_down.png", "ocr": "Single", "vllm": "Cont.", "omlx": "Timer", "winner": None,
             "models": {"vllm": QWEN, "omlx": GEMMA},
             "voters": [{"reader": "glm", "model": GLM, "selected": "Bracket"}]},
            {"frame": "00003_down.png", "ocr": "Single", "vllm": "Cont.", "omlx": "Cont.", "winner": "Cont."},
            {"frame": "00004_down.png", "ocr": "Single", "vllm": "Cont.", "omlx": "Timer", "winner": "Timer",
             "third_only": True, "models": {"vllm": QWEN, "omlx": GEMMA},
             "voters": [{"reader": "glm", "model": GLM, "selected": "Timer"}]}]
    (b.run / "tiebreak.jsonl").write_text("".join(json.dumps(t) + "\n" for t in ties), encoding="utf-8")
    m = pass1_map.build(b.run)
    opts = m["rows"][0]["options"]
    assert [(o["label"], o["source"]) for o in opts] == [("Single", "majority of four"), ("Cont.", "unresolved"),
                                                         ("Cont.", "majority of three"),
                                                         ("Cont.", "unresolved, third readers alone")]
    assert m["review"][-1] == {"path": ["Drive Mode"], "frame": "00004_down.png", "ocr": "Single", "vllm": "Cont.",
                               "omlx": "Timer", "voters": [{"reader": "glm", "selected": "Timer"}], "third_only": True}
    assert m["review"][0] == {"path": ["Drive Mode"], "frame": "00002_down.png", "ocr": "Single", "vllm": "Cont.",
                              "omlx": "Timer", "voters": [{"reader": "glm", "selected": "Bracket"}]}
    pass1_map.main([str(b.run), "--own", "--dry-run"])
    out = capsys.readouterr().out
    assert "glm='Bracket'" in out and "1 tiebreak lines name no models" in out
    assert "1 options third readers alone named" in out and "00004_down.png   index 3 Drive Mode" in out
    (b.run / "checked_labels.json").write_text(json.dumps({"00004_down.png": "Single"}), encoding="utf-8")
    m = pass1_map.build(b.run)                             # a label read by eye still wins
    assert m["rows"][0]["options"][3]["source"] == "checked by eye" and len(m["review"]) == 1


def test_third_readers_alone_ask_the_next_third_reader(bench):
    """Two third readers naming a reading neither OCR nor the second reader gave settle nothing, so the next third
    reader is asked: here it sides with the second reader, two against two, no winner and no mark."""
    b = bench
    b.config([lan("vllm", QWEN), lan("gemma", GEMMA), lan("glm", GLM), lan("pix", "mistralai/Pixtral-12B-2409")],
             roles={"second": "vllm", "third": ["gemma", "glm", "pix"]})
    b.options(("00001_down.png", "Single", "Cont."))
    b.said.update({("gemma", "00001_down.png"): "Timer", ("glm", "00001_down.png"): "Timer",
                   ("pix", "00001_down.png"): "Cont."})
    tiebreak(b.run)
    got = lines(b.run)[0]
    assert b.asked == [("gemma", "00001_down.png"), ("glm", "00001_down.png"), ("pix", "00001_down.png")]
    assert got["winner"] is None and "third_only" not in got


def test_a_plain_run_writes_no_line_no_third_reader_answered_so_a_rerun_asks_it(bench, capsys):
    """A third reader that fails FAIL_RUN times in a row (a server swapping models) is asked nothing more in the run, and
    the options it left unanswered are not written as done: a rerun asks every one of them."""
    import urllib.error

    import tiebreak as t
    b = bench
    b.config([lan("vllm", QWEN), lan("gemma", GEMMA)], roles={"second": "vllm", "third": "gemma"})
    frames = [f"0000{n}_down.png" for n in range(1, 7)]
    b.options(*[(f, "Single", "Cont.") for f in frames])
    off = urllib.error.URLError(ConnectionRefusedError("refused"))
    b.said.update({("gemma", f): off for f in frames[:3]})
    b.said.update({("gemma", f): "Single" for f in frames[3:]})
    tiebreak(b.run)
    assert b.asked == [("gemma", f) for f in frames[:t.FAIL_RUN]] and not (b.run / "tiebreak.jsonl").exists()
    assert ("6 to tie-break: 0 written; left for a rerun, 6 that no third reader answered" in capsys.readouterr().out)
    t._FAILS.clear()                                       # a new run, the server back
    b.asked.clear()
    b.said.update({("gemma", f): "Single" for f in frames})
    tiebreak(b.run)
    assert b.asked == [("gemma", f) for f in frames] and [x["winner"] for x in lines(b.run)] == ["Single"] * 6


def test_a_missing_frame_is_an_option_nobody_answered(bench, capsys):
    """A frame no longer under shots/ stops nothing: a plain run leaves its option for a rerun, --revote keeps its line
    as it was; both say which."""
    b = bench
    b.config([lan("vllm", QWEN), lan("gemma", GEMMA)], roles={"second": "vllm", "third": ["gemma"]})
    old_lines(b, ("00001_down.png", "Single", "Cont.", "Cont.", "Cont."), ("00002_down.png", "Single", "Cont.", "Cont.",
                                                                           "Cont."))
    (b.run / "shots" / "00002_down.png").unlink()
    b.said.update({("gemma", "00001_down.png"): "Single", ("gemma", "00002_down.png"): "Single"})
    before = lines(b.run)
    tiebreak(b.run, "--revote", "--was", QWEN_OLD)
    got = lines(b.run)
    assert got[0]["winner"] == "Single" and got[1] == before[1]
    out = capsys.readouterr().out
    assert "1 that none answered (1 of them with no frame under shots/)" in out
    assert "frame not under shots/: kit2_crawl 00002_down.png" in out
    (b.run / "tiebreak.jsonl").unlink()
    tiebreak(b.run)
    assert [x["frame"] for x in lines(b.run)] == ["00001_down.png"]
    out = capsys.readouterr().out
    assert "1 whose frame is not under shots/" in out and "frame not under shots/: kit2_crawl 00002_down.png" in out
