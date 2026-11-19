"""Rules of pass 2's report (kit/pass2_report.py) that the proofs of 2026-11-19 turned into wrong results, each on
made-up proof lines (a row, a session or two, the lines that matter): a side list's put-back the camera would not let
back ends its attempt and re-arms no older failure (rule A); a line that changed nothing in a record is credited with
what its session started from only where that session's lines move the record (rule B). Synthetic runs, made-up
records and values; no camera."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pass2_report as R  # noqa: E402

PATH = ["Picture Profile", "PP1", "Color Mode"]
KEY = "global:0x0751"                    # made up: the side list's one record here
# the side list prover's put-back failure (kit/proving/sidelists.py, prove_side_row), word for word
PUT_BACK = "Picture Profile > PP1 > Color Mode: back on its value, 1 records still differ"


def side(index, label, frame, base, changes=(), applied=True, context=None, attempt=None):
    """A side list's proof line as prove_side_row writes it (untagged; a refused one carries no diff)."""
    r = {"path": list(PATH), "kind": "sidelist", "index": index, "label": label, "base": base,
         "chosen_frame": f"{frame:05d}_down.png", "dat": f"{frame + 2:05d}_Color-Mode-{index}.DAT", "applied": applied,
         "changes": [{"key": k, "before": b, "after": a} for k, b, a in changes] if applied else []}
    if context:
        r["context"] = context
    if attempt:
        r["attempt"] = attempt
    return r


def failure(frame, why):
    return {"path": list(PATH), "why": why, "frame": f"{frame:05d}_menu.png"}


def a_run(tmp_path, proofs, failures=(), done=()):
    run = tmp_path / "kit2_pass2"
    (run / "dat").mkdir(parents=True)
    for name, lines in (("proofs", proofs), ("failures", failures),
                        ("attempts", [{"attempt": a, "row": " > ".join(PATH), "complete": True} for a in done])):
        (run / f"{name}.jsonl").write_text("".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")
    return run


def left_out(run):
    """The indices of the run's proofs the report leaves out as unfinished, as report_proofs reads one run."""
    proofs = R.proofs_of(run)
    return R.unfinished(proofs, R.attempts_done(run), R.failing_frames(run), frozenset(R.camera_kept(run).values()))


# ---------------------------------------------------------------- rule A: an expected put-back failure

HLG = "PP1 Gamma: HLG"
# a session made where the profile's Gamma greys the Color Mode the row held (Movie, 0): the list opens on BT.2020, which
# the prover chooses last to put the row back; it writes 10, so the put-back "still differs" (2026-11-19)
HLG_SESSION = [side(0, "Movie", 101, "00100_Color-Mode-base.DAT", applied=False, context=HLG),
               side(10, "709", 110, "00100_Color-Mode-base.DAT", [(KEY, 0, 11)], context=HLG),
               side(9, "BT.2020", 120, "00100_Color-Mode-base.DAT", [(KEY, 0, 10)], context=HLG)]
HLG_FAILURE = failure(123, PUT_BACK)


def test_a_side_lists_put_back_the_camera_greys_ends_its_attempt(tmp_path):
    """The start value greyed, the put-back writes what the list opened on and the attempt ends with the side list's
    put-back failure, then the session's restore by upload: the camera's doing. Every line of the attempt counts, the
    put-back's among them, and the row is no row that still fails."""
    run = a_run(tmp_path, HLG_SESSION, [HLG_FAILURE])
    assert left_out(run) == set()
    rows = R.rows_of(run, R.proofs_of(run), left_out(run))
    assert sorted(rows[f"Picture Profile > PP1 > Color Mode [{HLG}]"]) == [0, 9, 10]
    assert " > ".join(PATH) not in R.still_failing(run)[1]


def test_an_expected_put_back_failure_re_arms_no_older_failure(tmp_path):
    """An older attempt of the same path, in no context, cut short by a real failure, then finished by a later attempt:
    the old failure no longer stands, and its attempt counts as the report has always read such a row. A put-back
    failure in another context, the camera's doing, makes the row fail again no more than a finished attempt would, so
    the old attempt's lines count all the same."""
    older = [side(1, "Still", 11, "00010_Color-Mode-base.DAT", [(KEY, 0, 1)]),
             side(2, "S-Cinetone", 13, "00010_Color-Mode-base.DAT", [(KEY, 0, 2)])]
    cut = failure(16, "Picture Profile > PP1 > Color Mode: the side list opened on 'Still', the last OK chose "
                      "'S-Cinetone'")
    finished = [side(1, "Still", 31, "00030_Color-Mode-base.DAT", [(KEY, 0, 1)]),
                side(2, "S-Cinetone", 33, "00030_Color-Mode-base.DAT", [(KEY, 0, 2)]),
                side(0, "Movie", 35, "00030_Color-Mode-base.DAT")]
    assert left_out(a_run(tmp_path / "before", older + finished, [cut])) == set()
    run = a_run(tmp_path / "after", older + finished + HLG_SESSION, [cut, HLG_FAILURE])
    assert left_out(run) == set()
    assert " > ".join(PATH) not in R.still_failing(run)[1]


def test_a_put_back_that_went_wrong_still_cuts_its_attempt(tmp_path):
    """A put-back failure whose leftover is no doing of the camera's: a record the put-back left at a value no line
    held before (not kept), whose start value a line the camera applied held (offered). The attempt never ended as the
    camera allows: every line of it is left out, and the row still fails."""
    base = "00040_Color-Mode-base.DAT"
    lines = [side(2, "S-Cinetone", 41, base, [(KEY, 0, 2), ("global:0x0009", 0, 7)]),
             side(1, "Still", 43, base, [(KEY, 0, 1)]),
             side(0, "Movie", 45, base, [("global:0x0009", 0, 5)])]
    run = a_run(tmp_path, lines, [failure(48, PUT_BACK)])
    assert left_out(run) == {0, 1, 2}
    assert " > ".join(PATH) in R.still_failing(run)[1]


def test_an_attempt_that_never_ended_is_still_left_out(tmp_path):
    """The other ways an attempt ends short stay as they were: a real failure after a line that changed something cuts
    its attempt while the row still fails; a tagged attempt with no completion line (a run cut short: no failure, no
    restore) is left out whatever its lines; a put-back failure whose put-back the camera refused cuts too."""
    base = "00050_Color-Mode-base.DAT"
    lines = [side(1, "Still", 51, base, [(KEY, 0, 1)]), side(2, "S-Cinetone", 53, base, [(KEY, 0, 2)])]
    run = a_run(tmp_path / "cut", lines, [failure(56, "Picture Profile > PP1 > Color Mode: the cursor is not on 'Pro'")])
    assert left_out(run) == {0, 1}
    tagged = [dict(x, attempt="t1") for x in lines]
    assert left_out(a_run(tmp_path / "tagged", tagged)) == {0, 1}
    assert left_out(a_run(tmp_path / "tagged_done", tagged, done=["t1"])) == set()
    refused = lines + [side(0, "Movie", 55, base, applied=False)]
    assert left_out(a_run(tmp_path / "refused", refused, [failure(58, PUT_BACK)])) == {0, 1, 2}


# ---------------------------------------------------------------- rule B: "nothing changed" across camera states

LIVE, STILLS, MOVIE = "global:0x0001", "global:0x0002", "global:0x0003"      # made up: a setting and its two copies


def iso(index, label, frame, base, changes=()):
    """A list row's proof line (ISO AUTO Minimum in Stills mode, made-up records)."""
    return {"path": ["ISO", "ISO AUTO Minimum"], "context": "Stills mode", "kind": "list", "index": index,
            "label": label, "base": base, "chosen_frame": f"{frame:05d}_down.png", "dat": f"{frame + 2:05d}_x.DAT",
            "applied": True, "changes": [{"key": k, "before": b, "after": a} for k, b, a in changes]}


def credit(proofs):
    """values_of over the row's latest line per option (rows_of), what each session moves read from all its lines
    (session_moves), as the report credits a row."""
    (name, opts), = R.rows_of(None, proofs).items()
    return R.values_of(opts, moves=R.session_moves(proofs).get(name))


def test_nothing_changed_says_nothing_of_a_record_its_session_never_moves(monkeypatch):
    """The older session was made with Different Set for Still/Mv's box ticked for the row: a choice moves the live
    setting and the stills copy, never the movie copy, which holds its factory value (3, a value the list never offers).
    The later session, the box unticked, moves all three. ISO100 was chosen in the older session only: it is credited
    with what it wrote, and on the movie copy with nothing, never with the 3 its session started from (the report of
    2026-11-19: line 6751 named 0x0dfe's 3 "ISO100")."""
    held = {("00010_before.DAT", MOVIE): 3, ("00020_before.DAT", MOVIE): 3}
    monkeypatch.setattr(R, "base_value", lambda base, key: held.get((base, key)))
    older = [iso(1, "ISO125", 11, "00010_before.DAT", [(LIVE, 35, 6), (STILLS, 35, 6)]),
             iso(0, "ISO100", 13, "00010_before.DAT", [(LIVE, 35, 5), (STILLS, 35, 5)])]
    later = [iso(1, "ISO125", 21, "00020_before.DAT", [(LIVE, 3, 6), (STILLS, 3, 6), (MOVIE, 3, 6)]),
             iso(2, "ISO160", 23, "00020_before.DAT", [(LIVE, 3, 7), (STILLS, 3, 7), (MOVIE, 3, 7)])]
    got = credit(older + later)
    assert got[MOVIE] == {"ISO125": 6, "ISO160": 7}
    assert got[LIVE] == got[STILLS] == {"ISO125": 6, "ISO100": 5, "ISO160": 7}


def test_nothing_changed_within_a_session_that_moves_the_record_is_credited_as_before(monkeypatch):
    """Within one session whose other lines wrote the record, a line that changed nothing in it holds what the session
    started from, as the report has always read it (the saved option chosen back last). So it is where the session's
    line that wrote the record was later replaced by another session's line of the same option: every line of a session
    tells what it moves, not only each option's latest. A session that moved nothing at all (a saved option put back in
    a session of its own) still takes its own start."""
    held = {("00030_before.DAT", MOVIE): 5, ("00040_before.DAT", MOVIE): 5, ("00050_before.DAT", MOVIE): 9}
    monkeypatch.setattr(R, "base_value", lambda base, key: held.get((base, key)))
    one = [iso(1, "ISO125", 31, "00030_before.DAT", [(MOVIE, 5, 6)]), iso(0, "ISO100", 33, "00030_before.DAT")]
    assert credit(one)[MOVIE] == {"ISO125": 6, "ISO100": 5}
    replaced = [iso(1, "ISO125", 41, "00040_before.DAT", [(MOVIE, 5, 6)]),
                iso(0, "ISO100", 43, "00040_before.DAT", [(LIVE, 6, 5)]),
                iso(1, "ISO125", 51, "00050_before.DAT", [(MOVIE, 9, 6)])]
    assert credit(replaced)[MOVIE] == {"ISO125": 6, "ISO100": 5}
    alone = [iso(0, "ISO100", 61, "00060_before.DAT", [(MOVIE, 7, 5)]),
             iso(1, "ISO125", 63, "00060_before.DAT", [(MOVIE, 7, 6)]), iso(2, "ISO160", 71, "00050_before.DAT")]
    assert credit(alone)[MOVIE] == {"ISO100": 5, "ISO125": 6, "ISO160": 9}
