"""Rules of pass 2's report (kit/pass2_report.py) that the proofs of 2026-11-19 turned into wrong results, each on
made-up proof lines (a row, a session or two, the lines that matter): a side list's put-back the camera would not let
back ends its attempt and re-arms no older failure (rule A); a line that changed nothing in a record is credited with
what its session started from only where that session's lines move the record (rule B); a put-back never takes the
place of the proof before it (rule C), and a refusal takes the place of an applied line that moved nothing of its own.
Beside them, two of the write's and the ledger's: a value of the other video system is no list one value short
(kit/writer/listgaps.py), and a view-only readout's value proved by choice on the setting it follows is inferred in the
ledger's private form (kit/camkit/coverage.py). Synthetic runs, made-up records and values; no camera."""
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


def test_a_choice_that_moved_nothing_of_its_own_keeps_no_later_refusal_out(tmp_path):
    """An older attempt, cut short by a real failure that no longer stands (the row was proved since), counts as such an
    attempt always has; but its last line, BT.2020, wrote exactly what S-Gamut3 had written before it (the camera
    refused it, and the next opening found the list on S-Gamut3: the failure). The later attempt's line refusing BT.2020
    takes its place: a line whose download is the line before's moved nothing of its own and says nothing of whether
    its choice took (2026-11-19: line 785 named PP1's Color Mode code 9 "BT.2020 / S-Gamut3"). A line that moved
    something keeps a later refusal out as before (02ec9a8)."""
    base, again = "00010_Color-Mode-base.DAT", "00030_Color-Mode-base.DAT"
    older = [side(8, "S-Gamut3", 11, base, [(KEY, 0, 9)]), side(9, "BT.2020", 13, base, [(KEY, 0, 9)])]
    cut = failure(16, "Picture Profile > PP1 > Color Mode: the side list opened on 'S-Gamut3', the last OK chose "
                      "'BT.2020'")
    finished = [side(8, "S-Gamut3", 31, again, [(KEY, 0, 9)]), side(9, "BT.2020", 33, again, applied=False),
                side(0, "Movie", 35, again)]
    run = a_run(tmp_path, older + finished, [cut])
    assert left_out(run) == set()
    row = R.rows_of(run, R.proofs_of(run), left_out(run))[" > ".join(PATH)]
    assert row[9]["applied"] is False and "BT.2020" not in R.values_of(row)[KEY]
    took = [side(8, "S-Gamut3", 11, base, [(KEY, 0, 9)]), side(9, "BT.2020", 13, base, [(KEY, 0, 10)])]
    row = R.rows_of(None, took + finished)[" > ".join(PATH)]
    assert row[9]["applied"] is True and row[9]["dat"] == "00015_Color-Mode-9.DAT"


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


# ---------------------------------------------------------------- rule C: a put-back and the proof before it

EV, EV_MOVIE = "global:0x0011", "global:0x0012"          # made up: Exposure Comp. and its movie copy


def ev(index, label, frame, base, changes=(), kind="list", **more):
    """An Exposure Comp. proof line (a list row; made-up records)."""
    return {"path": ["Exposure Comp."], "kind": kind, "index": index, "label": label, "base": base,
            "chosen_frame": f"{frame:05d}_down.png", "dat": f"{frame + 2:05d}_x.DAT", "applied": True,
            "changes": [{"key": k, "before": b, "after": a} for k, b, a in changes], **more}


def test_a_put_back_never_takes_the_place_of_the_proof_before_it():
    """+2.7 EV chosen from +0.0 EV wrote both records; a later session started on +2.7 EV, chose +0.0 EV and put +2.7
    EV back, a line that changes nothing against its own start. The put-back is no proof of +2.7 EV, and it does not
    unmake the one that is: +2.7 EV stays credited with what it wrote (the report of 2026-11-19: line 9129 hid line
    8930). A table's put-back ("planned": false) holds back alike."""
    first = [ev(31, "+2.7 EV", 11, "00010_base.DAT", [(EV, 20, 31), (EV_MOVIE, 20, 31)]),
             ev(20, "+0.0 EV", 13, "00010_base.DAT")]
    later = [ev(20, "+0.0 EV", 21, "00020_base.DAT", [(EV, 31, 20), (EV_MOVIE, 31, 20)]),
             ev(31, "+2.7 EV", 23, "00020_base.DAT")]
    (name, opts), = R.rows_of(None, first + later).items()
    assert opts[31]["dat"] == "00013_x.DAT" and opts[20]["dat"] == "00023_x.DAT"
    got = R.values_of(opts)
    assert got[EV] == got[EV_MOVIE] == {"+2.7 EV": 31, "+0.0 EV": 20}
    table = [dict(r, kind="table", option="Exposure Comp.", planned=True) for r in first] + \
        [ev(31, "+2.7 EV", 21, "00020_base.DAT", kind="table", option="Exposure Comp.", planned=False),
         ev(20, "+0.0 EV", 23, "00020_base.DAT", [(EV, 31, 20)], kind="table", option="Exposure Comp.", planned=True)]
    (_, opts), = R.rows_of(None, table).items()
    assert opts[31]["dat"] == "00013_x.DAT"


def test_a_later_proof_that_wrote_still_takes_the_options_place():
    """What stays as it was: a later line that changed something is its option's latest, whatever the earlier one
    wrote; a put-back takes the place of an earlier line of its option that wrote nothing (a put-back of an earlier
    session); and a session's line that changed nothing but is not its last choice is no put-back."""
    first = [ev(31, "+2.7 EV", 11, "00010_base.DAT", [(EV, 20, 31)]), ev(20, "+0.0 EV", 13, "00010_base.DAT")]
    again = [ev(31, "+2.7 EV", 31, "00030_base.DAT", [(EV, 20, 31)]), ev(20, "+0.0 EV", 33, "00030_base.DAT")]
    (_, opts), = R.rows_of(None, first + again).items()
    assert opts[31]["dat"] == "00033_x.DAT" and opts[20]["dat"] == "00035_x.DAT"
    missed = [ev(31, "+2.7 EV", 41, "00040_base.DAT"), ev(20, "+0.0 EV", 43, "00040_base.DAT", [(EV, 25, 20)])]
    (_, opts), = R.rows_of(None, first + missed).items()
    assert opts[31]["dat"] == "00043_x.DAT"


# ---------------------------------------------------------------- the write's lists one value short

def test_a_value_of_the_other_video_system_is_no_gap(tmp_path):
    """writer/listgaps.py: USB Streaming's Output Res/Frame Rate (made-up codes) lists its PAL rate, which its menus
    offer under PAL only, as its public video_system_values say, the same for every owner. A proof made under NTSC
    lists every NTSC value and stops short of the PAL one: no gap, as a value a not_offered mark names is none. A gap
    stays where the proof's values are of both systems (the missing one is a system's whose values the proof chose),
    where no mark lists the missing value, and where the proof chose another value of the missing one's system."""
    from writer import listgaps

    def s(key, proved, systems=None, extra=()):
        vals = [[0, "4K 30p"], [2, "HD 60p"], *extra, [7, "HD 25p (PAL)"]]
        return {"key": key, "area": "global", "id": int(key[-4:], 16), "name": "Output Res/Frame Rate", "values": vals,
                "proved": {"values": proved}, **({"video_system_values": systems} if systems else {})}
    doc = {"settings": [
        s("global:0x02b3", [0, 2], {"NTSC": [0, 2], "PAL": [7]}),                          # made under NTSC: no gap
        s("global:0x02b4", [0, 7], {"NTSC": [0, 2], "PAL": [7]}),                          # both systems: 2 short
        s("global:0x02b5", [0, 2]),                                                        # no mark: 7 short
        s("global:0x02b6", [0, 2, 9], {"NTSC": [0, 2], "PAL": [7, 9]}, [[9, "HD 50p (PAL)"]])]}  # PAL's 9 chosen
    assert {x["key"]: v for x, v in listgaps.one_short(doc)} == \
        {"global:0x02b4": 2, "global:0x02b5": 7, "global:0x02b6": 7}
    assert {q["key"] for q in listgaps.questions(doc, tmp_path)} == {"global:0x02b4", "global:0x02b5", "global:0x02b6"}


# ---------------------------------------------------------------- the ledger: a view-only readout's values

ISO_LIKE = [(0, "AUTO"), (2, "ISO 50"), (3, "ISO 64"), (5, "ISO 100")]


def readout_camera(tmp_path, monkeypatch):
    """test_coverage's made-up camera; given(readout values, the ISO-like setting's whole proof as {value: name source},
    the readout's note) puts two settings on its row Kilo, an ISO-like setting a proof chose on (its whole proof in
    the evidence) and a readout of the ISO the camera uses, and returns build(public=False): (ledger, {key: values'
    statuses}, the row Kilo)."""
    import test_coverage as T
    from camkit import coverage
    cam = T.camera.__wrapped__(tmp_path, monkeypatch)
    doc0 = json.loads(cam.defn.read_text(encoding="utf-8"))
    ev = cam.defn.with_name(f"{T.CAM}.evidence.json")
    ev0 = json.loads(ev.read_text(encoding="utf-8"))
    records = dict(T.RECORDS, **{"global:0x0110": (1, 1), "global:0x0111": (1, 1)})

    def given(readout_values, follows_proof, note="The value the camera is using; it holds Kilo's own codes. View only."):
        chosen = sorted(int(v) for v, src in follows_proof.items() if src != "derived")
        doc = dict(doc0, settings=doc0["settings"] + [
            T.setting("global:0x0110", "Kilo", ["Kilo"], ISO_LIKE, proved={"values": chosen}),
            T.setting("global:0x0111", "Kilo in use", ["Kilo"], readout_values, scalar=False, note=note)])
        cam.defn.write_text(json.dumps(doc), encoding="utf-8")
        ev.write_text(json.dumps({"settings": dict(ev0["settings"], **{"global:0x0110": {"proved": {
            "run": "kit2_pass2", "values": chosen, "names": {str(v): s for v, s in follows_proof.items()}}}})}),
            encoding="utf-8")

        def build(public=False):
            led = coverage.build(T.CAM, src=coverage.load_sources(T.CAM, public=public, records=records))
            return led, {o["key"]: o["values"] for o in led.options}, T.row(led, "Kilo")
        return build
    return given


def test_a_readouts_value_proved_by_choice_on_the_setting_it_follows_is_inferred(tmp_path, monkeypatch):
    """A view-only readout (the camera writes it: no choice tries it) on the row of the setting whose codes it holds
    (its names at the same codes there, AUTO aside, which the readout never lists): each of its values a proof chose
    on that setting is "inferred from a shared list", in the private form alone; a value no proof chose there stays
    "not yet tried", and so does every value in the public form. Never "proved": the definition is not touched."""
    build = readout_camera(tmp_path, monkeypatch)(ISO_LIKE[1:], {"0": "two readers", "2": "two readers",
                                                                  "5": "one reader"})
    led, values, kilo = build()
    assert values["global:0x0111"] == {2: "inferred from a shared list", 3: "not yet tried",
                                       5: "inferred from a shared list"}
    assert kilo["values_left"] == 2 and kilo["values_inferred"] == 2      # 3, on the setting and on the readout
    assert led.options[-1]["cites"][2] == [{"proved_on": "global:0x0110"}]
    led, values, kilo = build(public=True)
    assert set(values["global:0x0111"].values()) == {"not yet tried"} and kilo["values_left"] == 4


def test_a_readouts_value_stays_as_it_was_without_a_proved_namesake_at_its_code(tmp_path, monkeypatch):
    """No inference where the readout does not hold the setting's codes (a name of its own at another code there), where
    the setting's value was named from another setting's proof and not chosen on it, or where the setting is no readout
    (its note says nothing of view only)."""
    given = readout_camera(tmp_path, monkeypatch)
    every = {"2": "two readers", "3": "two readers", "5": "two readers"}
    _, values, _ = given([(2, "ISO 50"), (3, "ISO 100"), (5, "ISO 64")], every)()
    assert set(values["global:0x0111"].values()) == {"not yet tried"}
    _, values, _ = given(ISO_LIKE[1:], {"2": "two readers", "3": "derived", "5": "derived"})()
    assert values["global:0x0111"] == {2: "inferred from a shared list", 3: "not yet tried", 5: "not yet tried"}
    _, values, _ = given(ISO_LIKE[1:], every, note="The value the camera is using.")()
    assert set(values["global:0x0111"].values()) == {"not yet tried"}
